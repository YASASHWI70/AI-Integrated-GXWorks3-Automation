"""
mcp_layer/tools/insert_contact.py — Insert a Contact into the Ladder Editor
============================================================================

In GX Works3 ladder editor:
    • F5 key inserts a Normally-Open (NO) contact    [ ]
    • F6 key inserts a Normally-Closed (NC) contact  [/]

After pressing the hotkey a small dialog/inline entry asks for the
device address (e.g. "X0").  Type the address and press Enter.

Navigation between cells is done with arrow keys or by clicking.
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


class InsertContactTool(BaseTool):
    """Insert a contact element (NO or NC) at a specific grid position."""

    name        = "insert_contact"
    description = (
        "Inserts a normally-open (NO) or normally-closed (NC) contact "
        "at the specified column/row in the GX Works3 ladder editor. "
        "Hotkey: F5 for NO, F6 for NC."
    )
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "PLC device address, e.g. 'X0', 'M100'.",
            },
            "col": {
                "type": "integer",
                "description": "0-based column position in the ladder grid.",
            },
            "row": {
                "type": "integer",
                "description": "0-based row (parallel branch). 0 = main rung.",
            },
            "normally_closed": {
                "type": "boolean",
                "description": "True → NC contact (F6). False → NO contact (F5).",
            },
        },
        "required": ["address"],
    }

    def execute(
        self,
        address:         str  = "X0",
        col:             int  = 0,
        row:             int  = 0,
        normally_closed: bool = False,
        **kwargs,
    ) -> ToolResult:
        """
        Insert a contact at the specified grid position.

        Steps:
          1. Navigate to the target cell (row, col).
          2. Press F5 (NO) or F6 (NC) to trigger the insertion dialog.
          3. Type the device address and press Enter.
          4. Verify the contact was placed (OCR or image check).
        """
        gx          = GXWorks3Interface()
        contact_key = "f6" if normally_closed else "f5"
        contact_sym = "NC" if normally_closed else "NO"

        try:
            if not gx.is_ladder_editor_open():
                raise RetryableError("Ladder editor is not open.")

            # ── Navigate to cell ──────────────────────────────
            logger.info(
                "Navigating to cell (row=%d, col=%d) …", row, col
            )
            gx.navigate_to_cell(row=row, col=col)
            time.sleep(config.CLICK_DELAY)

            # ── Trigger contact insertion ─────────────────────
            logger.info("Inserting %s contact at address '%s' …", contact_sym, address)
            gx.keyboard.press(contact_key)
            time.sleep(config.DIALOG_WAIT_TIME)

            # ── Enter address ─────────────────────────────────
            gx.keyboard.type_text(address)
            time.sleep(0.3)
            gx.keyboard.press("enter")
            time.sleep(config.CLICK_DELAY)

            # ── Verify insertion ──────────────────────────────
            # Simple heuristic: confirm no error dialog appeared.
            if gx.is_error_dialog_open():
                error_text = gx.read_dialog_text()
                return ToolResult.failure(
                    self.name,
                    error=f"GX Works3 reported an error: {error_text}",
                    message="Contact insertion failed — GX Works3 error dialog.",
                )

            logger.info(
                "Contact %s [%s] inserted at (row=%d, col=%d).",
                contact_sym, address, row, col,
            )
            return ToolResult.success(
                self.name,
                message=f"Inserted {contact_sym} contact '{address}' at col={col}, row={row}.",
                data={
                    "address":         address,
                    "type":            "contact_nc" if normally_closed else "contact_no",
                    "col":             col,
                    "row":             row,
                },
            )

        except RetryableError:
            raise
        except Exception as exc:
            logger.exception("Error in InsertContactTool")
            return ToolResult.failure(
                self.name,
                error=str(exc),
                message="Failed to insert contact.",
            )
