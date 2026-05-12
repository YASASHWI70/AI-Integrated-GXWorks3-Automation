"""
mcp_layer/tools/save_project.py — Save the GX Works3 Project
=============================================================

Saves the currently open project using Ctrl+S (Save) or Ctrl+Shift+S
(Save As).  If a "Save As" dialog appears (first save of a new project)
it types the project name and selects the save path.
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


class SaveProjectTool(BaseTool):
    """Save the currently open GX Works3 project."""

    name        = "save_project"
    description = (
        "Saves the current GX Works3 project using Ctrl+S. "
        "Handles the 'Save As' dialog for new unsaved projects."
    )
    parameters = {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Project name to use if a Save As dialog appears.",
            },
            "save_path": {
                "type": "string",
                "description": "Folder path to save into (for Save As dialog).",
            },
        },
        "required": [],
    }

    def execute(
        self,
        project_name: str = "",
        save_path:    str = "",
        **kwargs,
    ) -> ToolResult:
        """
        Save the project.

        Steps:
          1. Press Ctrl+S.
          2. If a Save/Save-As dialog appears, fill it in.
          3. Wait for the dialog to close.
          4. Verify the title bar no longer shows an asterisk (*) indicating
             unsaved changes.
        """
        gx = GXWorks3Interface()

        try:
            if not gx.bring_to_front():
                raise RetryableError("GX Works3 window not available for save.")

            # ── Save ──────────────────────────────────────────
            logger.info("Pressing Ctrl+S to save project …")
            gx.keyboard.hotkey("ctrl", "s")
            time.sleep(config.DIALOG_WAIT_TIME)

            # ── Handle Save As dialog (new unsaved project) ───
            if gx.wait_for_dialog("Save", timeout=5):
                logger.info("Save As dialog detected; filling in project details …")
                self._handle_save_as_dialog(
                    gx,
                    project_name or config.DEFAULT_PROJECT_PATH.split("\\")[-1],
                    save_path    or config.DEFAULT_PROJECT_PATH,
                )
                time.sleep(config.DIALOG_WAIT_TIME)

            # ── Handle overwrite confirmation ─────────────────
            if gx.wait_for_dialog("Confirm", timeout=3):
                logger.info("Overwrite confirmation dialog — pressing Yes …")
                gx.keyboard.press("enter")    # Yes / OK
                time.sleep(config.CLICK_DELAY)

            # ── Verify save was successful ────────────────────
            title = gx.get_window_title()
            if "*" in title:
                # Asterisk in title bar means unsaved changes remain
                logger.warning(
                    "Window title still shows unsaved marker: '%s'", title
                )
                raise RetryableError("Project still appears unsaved after Ctrl+S.")

            logger.info("Project saved successfully.  Title: %s", title)
            return ToolResult.success(
                self.name,
                message="Project saved successfully.",
                data={"window_title": title},
            )

        except RetryableError:
            raise
        except Exception as exc:
            logger.exception("Error in SaveProjectTool")
            return ToolResult.failure(
                self.name,
                error=str(exc),
                message="Failed to save project.",
            )

    # ── private ───────────────────────────────────────────────

    def _handle_save_as_dialog(
        self,
        gx:           GXWorks3Interface,
        project_name: str,
        save_path:    str,
    ) -> None:
        """Fill in the Save As dialog fields."""
        import pyautogui

        # Ensure the project save folder exists
        from pathlib import Path
        Path(save_path).mkdir(parents=True, exist_ok=True)

        # Clear and type the save path in the file location field
        # Most Windows Save dialogs focus the filename field first.
        gx.keyboard.hotkey("ctrl", "a")    # select all in current field
        gx.keyboard.type_text(save_path)
        gx.keyboard.press("enter")         # navigate to folder
        time.sleep(config.CLICK_DELAY)

        # Now type the project/file name
        gx.keyboard.hotkey("ctrl", "a")
        gx.keyboard.type_text(project_name)
        time.sleep(0.2)
        gx.keyboard.press("enter")         # confirm Save
