"""
ai_layer/ladder_generator.py — Converts User Input to a LadderProgram
======================================================================

This is the brain of the AI layer.  It:

  1. Receives a text description (already parsed by InputParser).
  2. Sends it to the LLM with a structured system prompt.
  3. Parses the JSON response back into a LadderProgram model.
  4. Validates the result (basic sanity checks before automation).

FALLBACK CHAIN:
    LLM call succeeds → parse JSON → validate → return LadderProgram
    LLM call fails    → try rule-based keyword matching → return LadderProgram
    Rule-based fails  → raise an informative error

RULE-BASED FALLBACK:
    For the MVP we include simple keyword detection so the system works
    even without an LLM API key configured.  This handles the most common
    patterns ("start stop", "motor", "timer") directly.
"""

from __future__ import annotations
import json
import logging
from typing import Union

from models.ladder_logic import (
    LadderProgram,
    LadderRung,
    LadderElement,
    ElementType,
    Position,
    create_start_stop_circuit,
    create_simple_contact_coil,
)
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class LadderGenerator:
    """
    Generates a LadderProgram from a natural language description.

    Usage:
        gen = LadderGenerator()
        program = gen.generate("Create a start-stop motor circuit")
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    def generate(self, description: str) -> LadderProgram:
        """
        Convert a natural language description to a LadderProgram.

        Args:
            description: User's text description of the required automation.

        Returns:
            A validated LadderProgram object.

        Raises:
            ValueError: If neither the LLM nor the rule-based fallback
                        can produce a valid program.
        """
        logger.info("Generating ladder program for: %r", description[:100])

        # ── Try LLM first ─────────────────────────────────────
        try:
            raw_json  = self.llm.ask(description)
            program   = self._parse_llm_response(raw_json)
            if program and program.rungs:
                logger.info(
                    "LLM generated %d rung(s) successfully.", len(program.rungs)
                )
                return program
        except Exception as exc:
            logger.warning("LLM generation failed: %s — trying rule-based …", exc)

        # ── Rule-based fallback ───────────────────────────────
        program = self._rule_based_generate(description)
        if program and program.rungs:
            logger.info(
                "Rule-based generator produced %d rung(s).", len(program.rungs)
            )
            return program

        raise ValueError(
            "Could not generate a ladder program from the given description. "
            "Please provide more detail or use JSON/structured input."
        )

    # ── LLM response parsing ──────────────────────────────────

    def _parse_llm_response(self, raw: str) -> LadderProgram | None:
        """
        Parse the LLM's JSON response into a LadderProgram.

        The LLM is instructed to return pure JSON, but occasionally wraps
        it in markdown fences.  We strip those before parsing.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines   = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])   # remove first/last fence lines

        try:
            data    = json.loads(cleaned)
            program = LadderProgram.model_validate(data)
            return program
        except json.JSONDecodeError as exc:
            logger.error("LLM response is not valid JSON: %s", exc)
            logger.debug("Raw LLM response: %s", raw)
            return None
        except Exception as exc:
            logger.error("LadderProgram schema mismatch: %s", exc)
            return None

    # ── Rule-based generator ──────────────────────────────────

    def _rule_based_generate(self, description: str) -> LadderProgram | None:
        """
        Keyword-based ladder logic generation for common patterns.

        This acts as a safety net when no LLM is configured or the LLM fails.
        Recognises patterns like "start stop", "motor", "timer", etc.
        """
        d = description.lower()

        # ── Pattern 1: Start-Stop Motor Circuit ───────────────
        if any(kw in d for kw in ["start", "stop", "motor", "latch"]):
            logger.info("Rule-based: matched 'start-stop' pattern.")
            program = LadderProgram(
                name        = "MAIN",
                description = "Start-Stop Motor Control (rule-based generated)",
            )
            program.add_rung(
                create_start_stop_circuit(
                    start_contact = "X0",
                    stop_contact  = "X1",
                    output_coil   = "Y0",
                    rung_id       = 1,
                )
            )
            return program

        # ── Pattern 2: Simple ON/OFF control ──────────────────
        if any(kw in d for kw in ["turn on", "activate", "enable", "switch"]):
            logger.info("Rule-based: matched 'simple contact-coil' pattern.")
            program = LadderProgram(
                name        = "MAIN",
                description = "Simple input-output (rule-based generated)",
            )
            program.add_rung(
                create_simple_contact_coil("X0", "Y0", rung_id=1)
            )
            return program

        # ── Pattern 3: Timer circuit ──────────────────────────
        if any(kw in d for kw in ["timer", "delay", "after", "seconds", "wait"]):
            logger.info("Rule-based: matched 'timer' pattern.")
            program = LadderProgram(
                name        = "MAIN",
                description = "Timer circuit (rule-based generated)",
            )
            # Rung 1: Input triggers timer
            rung1 = LadderRung(id=1, comment="Input triggers 5-second delay timer")
            rung1.add_element(LadderElement(
                type=ElementType.CONTACT_NO,
                address="X0", label="TRIGGER",
                position=Position(row=0, col=0),
            ))
            rung1.add_element(LadderElement(
                type=ElementType.TIMER_ON,
                address="T0", label="DELAY_5S",
                preset=50,   # 5 seconds in 100 ms units
                position=Position(row=0, col=1),
            ))
            # Rung 2: Timer contact drives output
            rung2 = LadderRung(id=2, comment="Timer done → output")
            rung2.add_element(LadderElement(
                type=ElementType.CONTACT_NO,
                address="T0", label="TIMER_DONE",
                position=Position(row=0, col=0),
            ))
            rung2.add_element(LadderElement(
                type=ElementType.COIL,
                address="Y0", label="OUTPUT",
                position=Position(row=0, col=1),
            ))
            program.add_rung(rung1)
            program.add_rung(rung2)
            return program

        return None
