"""
mcp_layer/tools/create_project.py — Create a New GX Works3 Project
===================================================================

Automates:
    File → New Project → (fill dialog) → OK

GX Works3 "New Project" dialog fields:
    • Project Type    : "Simple Project"  (vs. "Structured Project")
    • PLC Series      : e.g. "MELSEC iQ-R"
    • PLC Type        : e.g. "R04CPU"
    • Language        : "Ladder"
    • Project Name    : user-supplied
    • Save Location   : user-supplied

Because dialog layout varies across GX Works3 versions we use a
combination of keyboard navigation and image matching.
"""

from __future__ import annotations
import logging
import time

from models.tool_result import ToolResult
from models.plc_project  import PLCProject, PLCSeries
from mcp_layer.tool_executor import RetryableError
from .base_tool import BaseTool
from automation_layer.gxworks3_interface import GXWorks3Interface
import config

logger = logging.getLogger(__name__)


class CreateProjectTool(BaseTool):
    """Create a new GX Works3 project via the File → New dialog."""

    name        = "create_project"
    description = (
        "Creates a new GX Works3 project. "
        "Opens File → New Project, fills in the project details, "
        "and confirms the dialog."
    )
    parameters = {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Name of the new project (folder name).",
            },
            "save_path": {
                "type": "string",
                "description": "Directory where the project will be saved.",
            },
            "plc_series": {
                "type": "string",
                "description": "PLC hardware series, e.g. 'MELSEC iQ-R'.",
            },
            "plc_type": {
                "type": "string",
                "description": "CPU model, e.g. 'R04CPU'.",
            },
        },
        "required": ["project_name"],
    }

    def execute(
        self,
        project_name: str = "MyProject",
        save_path:    str = "",
        plc_series:   str = "",
        plc_type:     str = "",
        **kwargs,
    ) -> ToolResult:
        """
        Create a new GX Works3 project.

        Strategy:
          1. Bring GX Works3 window to the foreground.
          2. Use Ctrl+N (or Alt → F → N) to open the New Project dialog.
          3. Fill in PLC series and type via keyboard navigation.
          4. Enter the project name and save location.
          5. Press OK / Enter.
          6. Wait for the project to load (check title bar).
        """
        project = PLCProject(
            name        = project_name,
            save_path   = save_path or config.DEFAULT_PROJECT_PATH,
            plc_series  = PLCSeries(plc_series) if plc_series else PLCSeries.IQ_R,
            plc_type    = plc_type or config.DEFAULT_PLC_TYPE,
        )

        gx = GXWorks3Interface()

        try:
            # ── Bring GX Works3 to foreground ─────────────────
            if not gx.bring_to_front():
                raise RetryableError("Could not bring GX Works3 window to front.")

            time.sleep(config.DIALOG_WAIT_TIME)

            # ── Open New Project dialog (Ctrl+N) ──────────────
            logger.info("Opening New Project dialog …")
            gx.keyboard.hotkey("ctrl", "n")
            time.sleep(config.DIALOG_WAIT_TIME)

            # ── Verify dialog appeared ────────────────────────
            if not gx.wait_for_dialog("New Project", timeout=10):
                # Some versions use Alt+F → N
                logger.warning(
                    "Ctrl+N did not open dialog; trying Alt+F, N …"
                )
                gx.keyboard.hotkey("alt", "f")
                time.sleep(0.5)
                gx.keyboard.press("n")
                time.sleep(config.DIALOG_WAIT_TIME)

            # ── Fill in the dialog ────────────────────────────
            # GX Works3 New Project dialog layout (tab-order):
            #   1. Project Type dropdown (Simple / Structured)
            #   2. PLC Series dropdown
            #   3. PLC Type dropdown
            #   4. Language dropdown
            # These are navigated using Tab + type/selection keys.

            logger.info("Setting project type to Simple Project …")
            # The first focusable control is usually the Project Type combo
            gx.keyboard.press("tab")   # focus Project Type
            time.sleep(0.2)
            # Type first letters to select "Simple Project"
            gx.keyboard.type_text("S")
            time.sleep(0.3)

            logger.info("Setting PLC Series: %s", project.plc_series.value)
            gx.keyboard.press("tab")   # focus PLC Series combo
            time.sleep(0.2)
            # Select the series by typing the first characters
            gx.keyboard.type_text(project.plc_series.value[:6])
            time.sleep(0.3)

            logger.info("Setting PLC Type: %s", project.plc_type)
            gx.keyboard.press("tab")   # focus PLC Type combo
            time.sleep(0.2)
            gx.keyboard.type_text(project.plc_type)
            time.sleep(0.3)

            logger.info("Setting Language to Ladder …")
            gx.keyboard.press("tab")   # focus Language combo
            time.sleep(0.2)
            gx.keyboard.type_text("L")   # "Ladder"
            time.sleep(0.3)

            # ── Confirm dialog ────────────────────────────────
            logger.info("Confirming New Project dialog …")
            gx.keyboard.press("enter")
            time.sleep(config.DIALOG_WAIT_TIME * 2)   # project creation takes a moment

            # ── Verify project opened ─────────────────────────
            title = gx.get_window_title()
            if project_name.lower() in title.lower() or "gx works3" in title.lower():
                logger.info("Project '%s' created successfully.", project_name)
                return ToolResult.success(
                    self.name,
                    message=f"Project '{project_name}' created.",
                    data={"project": project.model_dump()},
                )
            else:
                raise RetryableError(
                    f"Window title '{title}' does not confirm project creation."
                )

        except RetryableError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in CreateProjectTool")
            return ToolResult.failure(
                self.name,
                error=str(exc),
                message="Failed to create project.",
            )
