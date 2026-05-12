"""
ai_layer/input_parser.py — Multi-Format Input Parser
=====================================================

Accepts user input in four formats and normalises it to a plain text
description that can be passed to the LLM or the rule-based generator.

Supported formats:
  • "text"   — Natural language string
  • "json"   — JSON string / dict matching LadderProgram schema
  • "pdf"    — Path to a PDF file
  • "struct" — A pre-built LadderProgram (pass-through)

The AI layer only sees the normalised text; it never knows what format
the original input arrived in.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Union, Dict, Any

import config
from models.ladder_logic import LadderProgram

logger = logging.getLogger(__name__)


class InputParser:
    """
    Detects the format of the incoming user input and extracts its content.

    Returns either:
      • A plain-text description → send to LLM for ladder generation
      • A LadderProgram object   → skip the LLM, go straight to automation

    Usage:
        parser = InputParser()
        result = parser.parse(user_input)
        if isinstance(result, LadderProgram):
            # Already structured — run automation directly
        else:
            # Text description — feed to LadderGenerator
    """

    def parse(
        self,
        user_input: Union[str, Dict, LadderProgram],
        hint: str = "auto",
    ) -> Union[str, LadderProgram]:
        """
        Parse user input and return either a text description or a LadderProgram.

        Args:
            user_input: The raw input — string, dict, or LadderProgram.
            hint:       Format hint: "text", "json", "pdf", "struct", or "auto".

        Returns:
            str            — plain text ready for the LLM
            LadderProgram  — fully parsed program, bypass LLM
        """
        # Already a LadderProgram — pass through
        if isinstance(user_input, LadderProgram):
            logger.info("Input is already a LadderProgram — bypassing LLM.")
            return user_input

        # Dict → try JSON parse
        if isinstance(user_input, dict):
            return self._parse_json_dict(user_input)

        if not isinstance(user_input, str):
            raise TypeError(f"Unsupported input type: {type(user_input)}")

        # Detect format
        if hint == "auto":
            hint = self._detect_format(user_input)

        logger.info("Input format detected/hinted as: %s", hint)

        if hint == "json":
            return self._parse_json_str(user_input)
        elif hint == "pdf":
            return self._parse_pdf(user_input)
        else:
            # "text" or anything else → return as-is for LLM processing
            return user_input.strip()

    # ── Format detection ──────────────────────────────────────

    def _detect_format(self, text: str) -> str:
        """Heuristically decide which format the input string is."""
        stripped = text.strip()

        # JSON detection
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"

        # PDF file path detection
        if stripped.endswith(".pdf") and Path(stripped).exists():
            return "pdf"

        # Default: natural language text
        return "text"

    # ── JSON parsing ──────────────────────────────────────────

    def _parse_json_str(self, json_str: str) -> Union[str, LadderProgram]:
        """Parse a JSON string.  If it matches the schema, return LadderProgram."""
        try:
            data = json.loads(json_str)
            return self._parse_json_dict(data)
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed (%s); treating as text.", exc)
            return json_str

    def _parse_json_dict(self, data: Dict[str, Any]) -> Union[str, LadderProgram]:
        """
        Try to deserialise a dict into a LadderProgram.
        Falls back to a string description if the schema doesn't match.
        """
        try:
            program = LadderProgram.model_validate(data)
            logger.info(
                "Parsed JSON into LadderProgram: %d rung(s).", len(program.rungs)
            )
            return program
        except Exception as exc:
            # Dict is not a LadderProgram — convert to description text
            logger.warning(
                "JSON does not match LadderProgram schema (%s); converting to text.", exc
            )
            return f"Create a ladder program from this specification: {json.dumps(data)}"

    # ── PDF parsing ───────────────────────────────────────────

    def _parse_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF and return it as a natural language description.

        Requires pdfplumber.  Falls back to PyPDF2 if pdfplumber is unavailable.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                text  = "\n".join(pages)
            logger.info("Extracted %d chars from PDF via pdfplumber.", len(text))
        except ImportError:
            logger.warning("pdfplumber not installed; trying PyPDF2 …")
            try:
                import PyPDF2
                with open(str(path), "rb") as fh:
                    reader = PyPDF2.PdfReader(fh)
                    text   = "\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                logger.info("Extracted %d chars from PDF via PyPDF2.", len(text))
            except ImportError:
                raise ImportError(
                    "No PDF library available. "
                    "Install pdfplumber: pip install pdfplumber"
                )

        if not text.strip():
            raise ValueError(f"Could not extract any text from PDF: {pdf_path}")

        # Prepend a task instruction so the LLM knows what to do with the text
        return (
            "The following is extracted from a technical specification document. "
            "Extract the automation requirements and create the appropriate ladder logic:\n\n"
            + text
        )
