"""
parsers/json_parser.py — JSON Input Parser
==========================================

Handles JSON inputs in two forms:

Form A — Full LadderProgram JSON (matches the schema exactly):
    {
      "name": "MAIN",
      "rungs": [ { "id": 1, "elements": [...] } ]
    }
    → Returns a LadderProgram directly.

Form B — Simplified shorthand JSON:
    {
      "type": "start_stop",
      "start": "X0",
      "stop": "X1",
      "output": "Y0"
    }
    → Expands to a full LadderProgram using the factory helpers.

Form B is useful for REST API integrations or batch job files where
users want a compact notation without writing full element arrays.
"""

from __future__ import annotations
import json
import logging
from typing import Union, Dict, Any

from models.ladder_logic import (
    LadderProgram,
    create_start_stop_circuit,
    create_simple_contact_coil,
)

logger = logging.getLogger(__name__)


class JSONParser:
    """
    Parse JSON input into a LadderProgram.

    Supports both full schema and shorthand notation.
    """

    def parse(self, data: Union[str, Dict]) -> LadderProgram:
        """
        Parse a JSON string or dict into a LadderProgram.

        Args:
            data: JSON string or already-parsed dict.

        Returns:
            LadderProgram object.

        Raises:
            ValueError: If the JSON cannot be parsed into a LadderProgram.
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON input: {exc}") from exc

        # Try full schema first
        if "rungs" in data:
            return self._parse_full_schema(data)

        # Try shorthand
        if "type" in data:
            return self._parse_shorthand(data)

        raise ValueError(
            "JSON input must have either 'rungs' (full schema) "
            "or 'type' (shorthand notation)."
        )

    # ── Full schema ───────────────────────────────────────────

    def _parse_full_schema(self, data: Dict[str, Any]) -> LadderProgram:
        """Validate and deserialise using the Pydantic model."""
        try:
            program = LadderProgram.model_validate(data)
            logger.info(
                "Parsed full-schema JSON: %d rung(s).", len(program.rungs)
            )
            return program
        except Exception as exc:
            raise ValueError(f"JSON schema validation error: {exc}") from exc

    # ── Shorthand ─────────────────────────────────────────────

    def _parse_shorthand(self, data: Dict[str, Any]) -> LadderProgram:
        """
        Expand shorthand notation into a full LadderProgram.

        Supported shorthand types:
            "start_stop" — start-stop motor circuit
            "simple"     — single contact → coil
        """
        circuit_type = data.get("type", "").lower()
        logger.info("Expanding shorthand type: '%s'", circuit_type)

        if circuit_type == "start_stop":
            rung = create_start_stop_circuit(
                start_contact = data.get("start",  "X0"),
                stop_contact  = data.get("stop",   "X1"),
                output_coil   = data.get("output", "Y0"),
                comment       = data.get("comment", "Start-Stop Circuit"),
            )
            return LadderProgram(
                name=data.get("name", "MAIN"),
                rungs=[rung],
            )

        if circuit_type in ("simple", "basic"):
            rung = create_simple_contact_coil(
                contact = data.get("input",   "X0"),
                coil    = data.get("output",  "Y0"),
                comment = data.get("comment", "Simple circuit"),
            )
            return LadderProgram(
                name=data.get("name", "MAIN"),
                rungs=[rung],
            )

        raise ValueError(
            f"Unknown shorthand type: '{circuit_type}'. "
            "Supported: 'start_stop', 'simple'."
        )
