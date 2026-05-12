"""
mcp_layer/tools/insert_coil.py — Insert an Output Coil
=======================================================

In GX Works3 ladder editor:
    • F7 key inserts a standard output coil   ( )
    • Set coil   (S)  — latches output ON
    • Reset coil (R)  — latches output OFF

This tool handles all three coil variants via the `coil_type` parameter.
"""

from __future__ import annotations
import logging
import time

from models.tool_result import ToolResult
from mcp_layer.tool_executor import RetryableError
from .base_tool import BaseTool
from automation_layer.gxworks3_interface import GXWorks3Interface
import config

logger = logging.getLogger(__name__)

# Map coil_type string → keyboard shortcut in GX Works3
_COIL_HOTKEYS = {
    "coil":        "f7",    # Standard output coil
    "coil_set":    "f7",    # Set coil — same dialog, different symbol
    "coil_reset":  "f7",    # Reset coil — same dialog, different symbol
}


class InsertCoilTool(BaseTool):
    """Insert a coil (output) element at a specific position in the ladder editor."""

    name        = "insert_coil"
    description = (
        "Inserts a coil (output element) at the specified column in the "
        "GX Works3 ladder editor. "
        "Supports standard coil ( ), set coil (S), and reset coil (R). "
        "Hotkey: F7."
    )
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "PLC device address, e.g. 'Y0', 'M0'.",
            },
            "col": {
                "type": "integer",
                "description": "0-based column position (usually last column in the rung).",
            },
            "row": {
                "type": "integer",
                "description": "0-based row (parallel branch). 0 = main rung.",
            },
            "coil_type": {
                "type": "string",
                "enum": ["coil", "coil_set", "coil_reset"],
                "description": "Coil variant: 'coil' (default), 'coil_set', 'coil_reset'.",
            },
        },
        "required": ["address"],
    }

    def execute(
        self,
        address:   str = "Y0",
        col:       int = 2,
        row:       int = 0,
        coil_type: str = "coil",
        **kwargs,
    ) -> ToolResult:
        """
        Insert a coil at the specified grid position.

        Steps:
          1. Navigate to the target cell.
          2. Press F7 to open the coil insertion dialog.
          3. If coil_type is set/reset, select the appropriate variant.
          4. Type the device address and press Enter.
          5. Verify no error dialog appeared.
        """
        gx = GXWorks3Interface()

        try:
            if not gx.is_ladder_editor_open():
                raise RetryableError("Ladder editor is not open.")

            # ── Navigate to cell ──────────────────────────────
            logger.info("Navigating to coil position (row=%d, col=%d) …", row, col)
            gx.navigate_to_cell(row=row, col=col)
            time.sleep(config.CLICK_DELAY)

            # ── Open insertion dialog (F7) ────────────────────
            logger.info("Inserting coil type='%s' at address '%s' …", coil_type, address)
            gx.keyboard.press("f7")
            time.sleep(config.DIALOG_WAIT_TIME)

            # ── For set/reset coils: select variant ───────────
            # In GX Works3 the coil dialog has a type selector.
            # Tab to it and press the first letter to jump to the right option.
            if coil_type == "coil_set":
                gx.keyboard.press("tab")         # focus type selector
                gx.keyboard.type_text("S")       # "Set coil"
                gx.keyboard.press("tab")         # back to address field
                time.sleep(0.3)
            elif coil_type == "coil_reset":
                gx.keyboard.press("tab")
                gx.keyboard.type_text("R")       # "Reset coil"
                gx.keyboard.press("tab")
                time.sleep(0.3)

            # ── Type the device address ───────────────────────
            gx.keyboard.type_text(address)
            time.sleep(0.3)
            gx.keyboard.press("enter")
            time.sleep(config.CLICK_DELAY)

            # ── Check for errors ──────────────────────────────
            if gx.is_error_dialog_open():
                error_text = gx.read_dialog_text()
                return ToolResult.failure(
                    self.name,
                    error=f"GX Works3 error: {error_text}",
                    message="Coil insertion failed — GX Works3 error dialog.",
                )

            logger.info(
                "Coil '%s' [%s] inserted at (row=%d, col=%d).",
                address, coil_type, row, col,
            )
            return ToolResult.success(
                self.name,
                message=f"Inserted {coil_type} '{address}' at col={col}, row={row}.",
                data={
                    "address":   address,
                    "type":      coil_type,
                    "col":       col,
                    "row":       row,
                },
            )

        except RetryableError:
            raise
        except Exception as exc:
            logger.exception("Error in InsertCoilTool")
            return ToolResult.failure(
                self.name,
                error=str(exc),
                message="Failed to insert coil.",
            )
