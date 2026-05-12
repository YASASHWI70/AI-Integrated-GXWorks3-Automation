"""
parsers/nlp_parser.py — Natural Language → Structured Ladder Intent
====================================================================

This parser does lightweight NLP (no ML model required) to extract
key signals from a text description before passing it to the LLM.

WHY BOTH THIS AND THE LLM?
    The NLPParser adds a preprocessing step that:
    1. Normalises terminology (e.g. "pushbutton" → "contact")
    2. Extracts addresses explicitly mentioned in the text
    3. Tags the circuit type for the rule-based fallback
    4. Enriches the prompt sent to the LLM with structured context

    Result: the LLM receives a cleaner prompt and produces better JSON.

FUTURE IMPROVEMENT:
    Replace this with a fine-tuned NER model or a dedicated PLC-domain
    tokeniser once enough training data is collected.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# INTENT / ENTITY DATACLASSES
# ──────────────────────────────────────────────────────────────

@dataclass
class ExtractedAddress:
    """A PLC address explicitly mentioned in the user text."""
    raw:    str            # Original text: "input X0", "coil Y1"
    prefix: str            # "X", "Y", "M", "T", "C"
    number: str            # "0", "100", etc.
    role:   Optional[str]  # "start", "stop", "motor", "timer", etc.

    @property
    def address(self) -> str:
        return f"{self.prefix}{self.number}"


@dataclass
class ParsedIntent:
    """
    Structured intent extracted from a natural-language description.
    """
    circuit_type:   str               = "unknown"  # "start_stop", "timer", "simple", …
    description:    str               = ""
    addresses:      List[ExtractedAddress] = field(default_factory=list)
    enriched_prompt: str              = ""


# ──────────────────────────────────────────────────────────────
# PARSER
# ──────────────────────────────────────────────────────────────

# Regex to find PLC addresses like X0, Y10, M100, T5, C3
_ADDRESS_RE = re.compile(r"\b([XYMTCDxymtcd])(\d+)\b")

# Role keyword maps — maps lowercase keywords to semantic roles
_ROLE_KEYWORDS = {
    "start":   ["start", "on button", "run", "start button", "pushbutton start"],
    "stop":    ["stop", "off button", "halt", "stop button", "pushbutton stop", "e-stop", "emergency"],
    "motor":   ["motor", "pump", "conveyor", "fan", "actuator", "output"],
    "timer":   ["timer", "delay", "after", "wait", "seconds", "timeout"],
    "counter": ["count", "counter", "product", "cycle"],
    "safety":  ["safety", "guard", "interlock", "overload"],
}

_CIRCUIT_PATTERNS = {
    "start_stop": ["start", "stop", "motor", "latch", "self-hold", "seal"],
    "timer":      ["timer", "delay", "on delay", "off delay", "timed", "after", "seconds"],
    "counter":    ["count", "counter", "pulse", "cycle"],
    "simple":     ["turn on", "activate", "switch", "enable", "basic"],
}


class NLPParser:
    """
    Keyword-based NLP parser for PLC ladder logic descriptions.

    Does NOT require any ML model or internet connection.
    """

    def parse(self, text: str) -> ParsedIntent:
        """
        Analyse text and return a ParsedIntent with extracted information.

        Args:
            text: Raw user input string.

        Returns:
            ParsedIntent with detected circuit type, addresses, and
            an enriched prompt ready for the LLM.
        """
        intent = ParsedIntent(description=text)

        # 1. Detect circuit type
        intent.circuit_type = self._detect_circuit_type(text)

        # 2. Extract explicitly mentioned PLC addresses
        intent.addresses = self._extract_addresses(text)

        # 3. Build an enriched prompt
        intent.enriched_prompt = self._build_enriched_prompt(intent)

        logger.info(
            "NLPParser: circuit_type=%s, addresses=%s",
            intent.circuit_type,
            [a.address for a in intent.addresses],
        )
        return intent

    # ── Private helpers ───────────────────────────────────────

    def _detect_circuit_type(self, text: str) -> str:
        lower = text.lower()
        scores = {circuit: 0 for circuit in _CIRCUIT_PATTERNS}
        for circuit, keywords in _CIRCUIT_PATTERNS.items():
            for kw in keywords:
                if kw in lower:
                    scores[circuit] += 1
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "simple"

    def _extract_addresses(self, text: str) -> List[ExtractedAddress]:
        """Find all PLC addresses in the text and infer their roles."""
        found = []
        for match in _ADDRESS_RE.finditer(text):
            prefix = match.group(1).upper()
            number = match.group(2)
            raw    = match.group(0)

            # Look at the surrounding words for a role hint
            start = max(0, match.start() - 30)
            context = text[start: match.end() + 30].lower()
            role = self._infer_role(context, prefix)

            found.append(ExtractedAddress(
                raw=raw, prefix=prefix, number=number, role=role,
            ))
        return found

    def _infer_role(self, context: str, prefix: str) -> Optional[str]:
        """Guess the functional role of an address from surrounding text."""
        for role, keywords in _ROLE_KEYWORDS.items():
            for kw in keywords:
                if kw in context:
                    return role
        # Default role by prefix convention
        defaults = {"X": "input", "Y": "output", "M": "internal",
                    "T": "timer", "C": "counter"}
        return defaults.get(prefix.upper())

    def _build_enriched_prompt(self, intent: ParsedIntent) -> str:
        """
        Construct a more detailed prompt from the parsed intent.
        This gives the LLM more structured context.
        """
        lines = [
            f"User request: {intent.description}",
            f"Detected circuit type: {intent.circuit_type}",
        ]
        if intent.addresses:
            addr_info = ", ".join(
                f"{a.address} ({a.role})" for a in intent.addresses
            )
            lines.append(f"Mentioned PLC addresses: {addr_info}")
        lines.append(
            "Generate the complete ladder logic JSON for the above requirements."
        )
        return "\n".join(lines)
