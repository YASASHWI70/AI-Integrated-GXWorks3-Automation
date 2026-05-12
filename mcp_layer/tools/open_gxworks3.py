"""
mcp_layer/tools/open_gxworks3.py — Launch GX Works3
=====================================================

This tool finds the GX Works3 executable, launches it as a sub-process,
and waits until the main application window is visible and ready for input.

RETRY LOGIC:
    The tool raises RetryableError if the window is not yet visible,
    which causes the executor to retry with exponential back-off.
"""

from __future__ import annotations
import os
import subprocess
import time
import logging
from pathlib import Path

from models.tool_result import ToolResult
from mcp_layer.tool_executor import RetryableError
from .base_tool import BaseTool
import config

logger = logging.getLogger(__name__)


class OpenGXWorks3Tool(BaseTool):
    """Launch GX Works3 and wait until it is ready for interaction."""

    name        = "open_gxworks3"
    description = (
        "Launches the Mitsubishi GX Works3 application and waits until "
        "the main window is visible and ready for automation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "exe_path": {
                "type": "string",
                "description": (
                    "Optional explicit path to GXW3.exe. "
                    "If omitted the system searches common install locations."
                ),
            },
            "wait_seconds": {
                "type": "number",
                "description": "Seconds to wait for the window to appear (default 15).",
            },
        },
        "required": [],
    }

    # ── main execute ──────────────────────────────────────────

    def execute(
        self,
        exe_path:     str   = "",
        wait_seconds: float = 15.0,
        **kwargs,
    ) -> ToolResult:
        """
        Launch GX Works3.

        Steps:
        1. Locate the executable.
        2. Check if already running (skip launch if so).
        3. Start the process.
        4. Poll for the main window to appear.
        """
        # ── Step 1: locate the executable ───────────────────
        resolved_path = self._resolve_exe(exe_path)
        if resolved_path is None:
            return ToolResult.failure(
                self.name,
                error=(
                    "GX Works3 executable not found. "
                    "Set GXW3_EXE_PATH in your .env file or pass exe_path."
                ),
                message="Could not locate GXW3.exe.",
            )

        # ── Step 2: check if already running ────────────────
        if self._is_running():
            logger.info("GX Works3 is already running — skipping launch.")
            return ToolResult.success(
                self.name,
                message="GX Works3 is already running.",
                data={"already_running": True},
            )

        # ── Step 3: launch the process ───────────────────────
        logger.info("Launching GX Works3 from: %s", resolved_path)
        try:
            subprocess.Popen(
                [resolved_path],
                creationflags=subprocess.DETACHED_PROCESS,
            )
        except OSError as exc:
            return ToolResult.failure(
                self.name,
                error=str(exc),
                message=f"Failed to launch GX Works3: {exc}",
            )

        # ── Step 4: wait for window ───────────────────────────
        logger.info("Waiting up to %.0f s for GX Works3 window …", wait_seconds)
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self._is_running():
                time.sleep(1.5)   # let the UI finish drawing
                logger.info("GX Works3 is ready.")
                return ToolResult.success(
                    self.name,
                    message="GX Works3 launched successfully.",
                    data={"exe_path": resolved_path},
                )
            time.sleep(1.0)

        # Window never appeared — signal executor to retry
        raise RetryableError(
            f"GX Works3 window not visible after {wait_seconds:.0f} s."
        )

    # ── private helpers ───────────────────────────────────────

    def _resolve_exe(self, override: str) -> str | None:
        """Return the first valid path to GXW3.exe, or None."""
        candidates = [override] + config.GXW3_POSSIBLE_PATHS
        for path in candidates:
            if path and Path(path).is_file():
                return path
        return None

    def _is_running(self) -> bool:
        """Return True if a GX Works3 window currently exists on screen."""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(config.GXW3_WINDOW_TITLE)
            return len(windows) > 0
        except Exception:
            # Fall back to psutil process check
            try:
                import psutil
                for proc in psutil.process_iter(["name"]):
                    if "gxw3" in proc.info["name"].lower():
                        return True
            except Exception:
                pass
            return False
