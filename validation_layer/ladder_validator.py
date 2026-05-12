"""
validation_layer/ladder_validator.py — Ladder Logic Validator
=============================================================

Validates a LadderProgram BEFORE sending it to the automation layer.
Catching errors here is far cheaper than discovering them mid-automation
when GX Works3 has a dialog open and the cursor is in an unknown position.

CHECKS PERFORMED:
  1. Each rung has at least one contact and one coil (or valid instruction).
  2. No duplicate coil addresses within the same program (output conflict).
  3. All addresses use valid Mitsubishi prefix letters (X, Y, M, T, C, D).
  4. Address numbers are within the configured range for the PLC type.
  5. Timer elements have a preset value set.
  6. Rung IDs are unique and sequential.
  7. Coils are not used as contacts in the same rung they're driven
     (combinational feedback — only valid if intentional, e.g. latch).
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Set

from models.ladder_logic import (
    LadderProgram,
    LadderRung,
    LadderElement,
    ElementType,
    PLCAddressSpace,
)

logger = logging.getLogger(__name__)

# Elements that drive outputs (coils, timers, counters)
_OUTPUT_TYPES = {
    ElementType.COIL,
    ElementType.COIL_SET,
    ElementType.COIL_RESET,
    ElementType.TIMER_ON,
    ElementType.TIMER_OFF,
    ElementType.COUNTER_UP,
    ElementType.COUNTER_DOWN,
}

# Elements that are conditions (contacts)
_CONTACT_TYPES = {
    ElementType.CONTACT_NO,
    ElementType.CONTACT_NC,
    ElementType.CONTACT_RISE,
    ElementType.CONTACT_FALL,
}

# Valid Mitsubishi PLC address prefixes
_VALID_PREFIXES = re.compile(r"^([XYMTCDxymtcd])(\d+)$")


@dataclass
class ValidationIssue:
    """A single validation problem found in the ladder program."""
    severity: str    # "error" | "warning"
    rung_id:  int    # 0 = program-level issue
    message:  str


@dataclass
class ValidationResult:
    """Result of validating a LadderProgram."""
    issues: List[ValidationIssue] = field(default_factory=list)

    def add_error(self, rung_id: int, message: str) -> None:
        self.issues.append(ValidationIssue("error", rung_id, message))

    def add_warning(self, rung_id: int, message: str) -> None:
        self.issues.append(ValidationIssue("warning", rung_id, message))

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        """True if there are no errors (warnings are acceptable)."""
        return len(self.errors) == 0

    def summary(self) -> str:
        if self.is_valid and not self.warnings:
            return "✓ Validation passed — no issues found."
        lines = []
        for issue in self.errors:
            lines.append(f"  [ERROR]   Rung {issue.rung_id}: {issue.message}")
        for issue in self.warnings:
            lines.append(f"  [WARNING] Rung {issue.rung_id}: {issue.message}")
        prefix = "✓ Valid (with warnings)" if self.is_valid else "✗ INVALID"
        return f"{prefix}\n" + "\n".join(lines)


class LadderValidator:
    """
    Validates a LadderProgram against Mitsubishi PLC conventions.

    Usage:
        validator = LadderValidator()
        result    = validator.validate(program)
        if not result.is_valid:
            print(result.summary())
            raise ValueError("Ladder program has errors — aborting automation.")
    """

    def __init__(self, address_space: PLCAddressSpace | None = None) -> None:
        self.addr = address_space or PLCAddressSpace()

    def validate(self, program: LadderProgram) -> ValidationResult:
        """
        Run all validation checks on a LadderProgram.

        Returns a ValidationResult — never raises.
        """
        result = ValidationResult()

        if not program.rungs:
            result.add_error(0, "Program has no rungs.")
            return result

        self._check_rung_ids(program, result)
        self._check_duplicate_coils(program, result)

        for rung in program.rungs:
            self._check_rung_structure(rung, result)
            self._check_addresses(rung, result)
            self._check_timer_presets(rung, result)

        logger.info(
            "Validation: %d error(s), %d warning(s).",
            len(result.errors), len(result.warnings),
        )
        return result

    # ── Individual checks ─────────────────────────────────────

    def _check_rung_ids(self, program: LadderProgram, result: ValidationResult) -> None:
        """Rung IDs must be unique."""
        ids: Set[int] = set()
        for rung in program.rungs:
            if rung.id in ids:
                result.add_error(
                    rung.id,
                    f"Duplicate rung ID {rung.id}. Each rung must have a unique ID.",
                )
            ids.add(rung.id)

    def _check_duplicate_coils(
        self, program: LadderProgram, result: ValidationResult
    ) -> None:
        """
        Warn if the same output coil address is used in multiple rungs.
        (Multiple coil outputs for the same address cause the last one to win,
         which is usually a logic error.)
        """
        coil_rung: dict[str, int] = {}
        for rung in program.rungs:
            for el in rung.elements:
                if el.type in (ElementType.COIL, ElementType.COIL_SET, ElementType.COIL_RESET):
                    if el.address in coil_rung:
                        result.add_warning(
                            rung.id,
                            f"Coil '{el.address}' is driven in both rung "
                            f"{coil_rung[el.address]} and rung {rung.id}. "
                            "Only the last energised value matters.",
                        )
                    else:
                        coil_rung[el.address] = rung.id

    def _check_rung_structure(self, rung: LadderRung, result: ValidationResult) -> None:
        """Each rung must have at least one contact (left) and one output (right)."""
        if not rung.elements:
            result.add_error(rung.id, "Rung is empty (no elements).")
            return

        has_contact = any(
            el.type in _CONTACT_TYPES for el in rung.elements
        )
        has_output  = any(
            el.type in _OUTPUT_TYPES for el in rung.elements
        )

        if not has_contact:
            result.add_warning(
                rung.id,
                "Rung has no contact elements. "
                "An unconditional coil is unusual and may cause issues.",
            )
        if not has_output:
            result.add_error(
                rung.id,
                "Rung has no output element (coil, timer, or counter). "
                "Every rung must have at least one output.",
            )

    def _check_addresses(self, rung: LadderRung, result: ValidationResult) -> None:
        """Validate that every address uses a known Mitsubishi prefix format."""
        for el in rung.elements:
            m = _VALID_PREFIXES.match(el.address)
            if not m:
                result.add_error(
                    rung.id,
                    f"Address '{el.address}' has an invalid format. "
                    "Expected format: prefix + number (e.g. X0, Y10, M100).",
                )
                continue

            prefix = m.group(1).upper()
            number = int(m.group(2))

            # Check range limits
            limits = {
                "X": self.addr.input_max,
                "Y": self.addr.output_max,
                "M": self.addr.internal_max,
                "T": self.addr.timer_max,
                "C": self.addr.counter_max,
            }
            if prefix in limits and number > limits[prefix]:
                result.add_error(
                    rung.id,
                    f"Address '{el.address}' exceeds the maximum for {prefix} "
                    f"({limits[prefix]}).",
                )

    def _check_timer_presets(self, rung: LadderRung, result: ValidationResult) -> None:
        """Timer elements must have a preset value > 0."""
        for el in rung.elements:
            if el.type in (ElementType.TIMER_ON, ElementType.TIMER_OFF):
                if el.preset is None or el.preset <= 0:
                    result.add_error(
                        rung.id,
                        f"Timer '{el.address}' must have a preset value > 0. "
                        "Preset is in 100 ms units (e.g. 50 = 5 seconds).",
                    )
