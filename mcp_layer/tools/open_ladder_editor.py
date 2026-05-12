"""
mcp_layer/tools/open_ladder_editor.py — Open the Ladder Editor
===============================================================

After a new project is created GX Works3 shows the Project Tree.
This tool navigates to the main ladder POU and opens the editor window.

Navigation path in Project Tree:
    Program → MAIN (double-click to open)

GX Works3 keyboard shortcuts:
    • Alt+1     — show Project window (if hidden)
    • Enter / double-click on "MAIN" POU — open ladder editor
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


class OpenLadderEditorTool(BaseTool):
    """Open the GX Works3 ladder program editor."""

    name        = "open_ladder_editor"
    description = (
        "Opens the ladder logic editor in GX Works3 by navigating the "
        "Project Tree to Program → MAIN and double-clicking to open it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pou_name": {
                "type": "string",
                "description": "Name of the POU to open (default: 'MAIN').",
            },
        },
        "required": [],
    }

    def execute(self, pou_name: str = "MAIN", **kwargs) -> ToolResult:
        """
        Open the ladder editor for the specified POU.

        Strategy:
          1. Ensure Project Tree is visible (Alt+1).
          2. Use image matching to locate the MAIN POU icon,
             OR use keyboard navigation (expand tree → navigate to MAIN).
          3. Double-click (or press Enter) to open the editor.
          4. Verify the editor opened (check for ladder grid in screenshot).
        """
        gx = GXWorks3Interface()

        try:
            if not gx.bring_to_front():
                raise RetryableError("GX Works3 window not available.")

            # ── Show Project Tree ─────────────────────────────
            logger.info("Ensuring Project Tree is visible …")
            gx.keyboard.hotkey("alt", "1")
            time.sleep(config.DIALOG_WAIT_TIME)

            # ── Try image-based navigation first ──────────────
            opened_via_image = self._open_via_image_match(gx, pou_name)

            if not opened_via_image:
                # Fall back: keyboard-only navigation
                logger.info(
                    "Image match failed; using keyboard navigation to open '%s' …",
                    pou_name,
                )
                self._open_via_keyboard(gx, pou_name)

            time.sleep(config.DIALOG_WAIT_TIME)

            # ── Verify editor is open ─────────────────────────
            if gx.is_ladder_editor_open():
                logger.info("Ladder editor is now open.")
                return ToolResult.success(
                    self.name,
                    message=f"Ladder editor for '{pou_name}' opened.",
                    data={"pou_name": pou_name},
                )
            else:
                raise RetryableError("Ladder editor did not open after navigation.")

        except RetryableError:
            raise
        except Exception as exc:
            logger.exception("Error in OpenLadderEditorTool")
            return ToolResult.failure(
                self.name,
                error=str(exc),
                message="Failed to open ladder editor.",
            )

    # ── private helpers ───────────────────────────────────────

    def _open_via_image_match(self, gx: GXWorks3Interface, pou_name: str) -> bool:
        """Try to find and double-click the POU in the project tree by image."""
        from automation_layer.image_matcher import ImageMatcher
        from pathlib import Path
        import config as cfg

        matcher = ImageMatcher()
        template = cfg.ASSETS_DIR / "project_tree_main_pou.png"

        if not template.exists():
            logger.debug("Asset '%s' not found; skipping image match.", template)
            return False

        loc = matcher.find_on_screen(str(template))
        if loc:
            gx.mouse.double_click(loc[0], loc[1])
            logger.info("Double-clicked MAIN POU at %s via image match.", loc)
            return True

        return False

    def _open_via_keyboard(self, gx: GXWorks3Interface, pou_name: str) -> None:
        """
        Keyboard-only fallback: navigate the Project Tree using arrow keys.

        Typical tree layout in a fresh Simple Project:
            ▼ Project
              ▼ Program
                  MAIN     ← target
        """
        # Click somewhere in the project tree pane to give it focus
        # (heuristic: top-left area of GX Works3 contains the tree)
        win = gx.get_window_rect()
        if win:
            tree_x = win["left"] + 100
            tree_y = win["top"]  + 150
            gx.mouse.click(tree_x, tree_y)
            time.sleep(0.3)

        # Expand tree and navigate to MAIN
        gx.keyboard.press("home")          # go to top of tree
        time.sleep(0.2)
        gx.keyboard.press("right")         # expand Project
        time.sleep(0.2)
        gx.keyboard.press("down")          # move to Program folder
        time.sleep(0.2)
        gx.keyboard.press("right")         # expand Program folder
        time.sleep(0.2)
        gx.keyboard.press("down")          # move to MAIN POU
        time.sleep(0.2)
        gx.keyboard.press("enter")         # open it
        time.sleep(config.DIALOG_WAIT_TIME)
