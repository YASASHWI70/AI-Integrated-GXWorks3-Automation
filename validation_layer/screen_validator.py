"""
validation_layer/screen_validator.py — Post-Automation Screen Validator
=======================================================================

After each automation step, it's worth verifying that the screen state
looks as expected.  This prevents cascading errors where the automation
continues even though a previous step silently failed.

CHECKS:
  • GX Works3 is still the foreground window.
  • No unexpected error dialogs are open.
  • The ladder editor is open (after open_ladder_editor step).
  • The project title bar shows the expected project name.

DESIGN NOTE:
    Screen validation is intentionally lightweight in the MVP.
    For production use, expand this with:
      - Image-based element detection (did the contact actually appear?)
      - OCR address verification (read back address from the cell)
      - Color-coded status indicators
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List

import config

logger = logging.getLogger(__name__)


@dataclass
class ScreenCheck:
    """Result of a single screen validation check."""
    name:    str
    passed:  bool
    message: str


@dataclass
class ScreenValidationResult:
    """Aggregated result of all screen checks."""
    checks: List[ScreenCheck] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        lines = []
        for c in self.checks:
            icon = "✓" if c.passed else "✗"
            lines.append(f"  {icon} {c.name}: {c.message}")
        return "\n".join(lines)


class ScreenValidator:
    """
    Validates the GX Works3 screen state after automation actions.

    Usage:
        sv     = ScreenValidator()
        result = sv.check_editor_ready()
        if not result.all_passed:
            raise RuntimeError(f"Screen state invalid:\n{result.summary()}")
    """

    def check_gxworks3_open(self) -> ScreenValidationResult:
        """Verify that the GX Works3 window is visible."""
        from automation_layer.screen_manager import ScreenManager
        sm     = ScreenManager()
        result = ScreenValidationResult()
        win    = sm.get_window(config.GXW3_WINDOW_TITLE)

        result.checks.append(ScreenCheck(
            name    = "GX Works3 window visible",
            passed  = win is not None,
            message = (
                f"Window found: {win.title!r}" if win
                else "No GX Works3 window found on screen."
            ),
        ))
        return result

    def check_no_error_dialog(self) -> ScreenValidationResult:
        """Verify that no error/warning dialog is currently open."""
        from automation_layer.gxworks3_interface import GXWorks3Interface
        gx     = GXWorks3Interface()
        result = ScreenValidationResult()

        error_open = gx.is_error_dialog_open()
        result.checks.append(ScreenCheck(
            name    = "No error dialog",
            passed  = not error_open,
            message = (
                "Error dialog is open — manual intervention may be required."
                if error_open else "No error dialogs detected."
            ),
        ))
        return result

    def check_ladder_editor_open(self) -> ScreenValidationResult:
        """Verify the ladder editor is the active view."""
        from automation_layer.gxworks3_interface import GXWorks3Interface
        gx     = GXWorks3Interface()
        result = ScreenValidationResult()

        editor_open = gx.is_ladder_editor_open()
        result.checks.append(ScreenCheck(
            name    = "Ladder editor active",
            passed  = editor_open,
            message = (
                "Ladder editor is open and ready."
                if editor_open
                else "Ladder editor does not appear to be active."
            ),
        ))
        return result

    def check_project_title(self, expected_name: str) -> ScreenValidationResult:
        """Verify the window title contains the expected project name."""
        from automation_layer.gxworks3_interface import GXWorks3Interface
        gx     = GXWorks3Interface()
        result = ScreenValidationResult()

        title  = gx.get_window_title()
        passed = expected_name.lower() in title.lower()
        result.checks.append(ScreenCheck(
            name    = "Project title matches",
            passed  = passed,
            message = (
                f"Title '{title}' contains '{expected_name}'."
                if passed
                else f"Expected '{expected_name}' in title but got '{title}'."
            ),
        ))
        return result

    def check_all(self, project_name: str = "") -> ScreenValidationResult:
        """Run all available screen checks and return a combined result."""
        combined = ScreenValidationResult()

        for partial in [
            self.check_gxworks3_open(),
            self.check_no_error_dialog(),
            self.check_ladder_editor_open(),
        ]:
            combined.checks.extend(partial.checks)

        if project_name:
            combined.checks.extend(
                self.check_project_title(project_name).checks
            )

        return combined
