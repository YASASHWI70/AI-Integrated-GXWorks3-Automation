"""
automation_layer/gxworks3_interface.py — High-Level GX Works3 Facade
=====================================================================

This is the central object used by all MCP tools to interact with
GX Works3.  It composes ScreenManager, MouseController,
KeyboardController, ImageMatcher, and OCREngine into one coherent API
specific to GX Works3.

DESIGN PHILOSOPHY:
  The MCP tools (one layer up) describe WHAT to do ("insert contact X0").
  This class knows HOW to do it inside GX Works3 specifically.
  If Mitsubishi releases an API in the future, only this file needs updating.

GX WORKS3 LADDER EDITOR CELL NAVIGATION:
  The ladder editor uses a grid.  Each cell is approximately 50×30 pixels.
  The editor starts at a fixed offset from the application window's top-left.
  We navigate between cells using arrow keys, which is more reliable than
  pixel-coordinate clicking.

  Cell (row=0, col=0) is the first position on the first (empty) rung.
  Press Right arrow → move one column right.
  Press Down arrow  → move one row down (into a parallel branch).
"""

from __future__ import annotations
import time
import logging
from typing import Optional, Dict, Tuple

import config
from .screen_manager    import ScreenManager
from .mouse_keyboard    import MouseController, KeyboardController
from .image_matcher     import ImageMatcher
from .ocr_engine        import OCREngine

logger = logging.getLogger(__name__)

# ── Ladder editor grid constants ──────────────────────────────────────────────
# These values work for GX Works3 at 100% DPI scaling.
# Adjust if your screen uses a different DPI setting.
LADDER_CELL_WIDTH_PX  = 50    # Approximate horizontal cell spacing in pixels
LADDER_CELL_HEIGHT_PX = 30    # Approximate vertical cell spacing in pixels

# How many right/down arrow presses equate to one grid step
COL_KEY_STEPS = 1
ROW_KEY_STEPS = 1


class GXWorks3Interface:
    """
    Provides a GX Works3-specific high-level automation API.

    Every MCP tool gets a fresh instance of this class.
    All lower-level controllers (mouse, keyboard, …) are stateless and
    cheap to construct, so this pattern is fine for the MVP.
    """

    WINDOW_TITLE = config.GXW3_WINDOW_TITLE

    def __init__(self) -> None:
        self.screen  = ScreenManager()
        self.mouse   = MouseController()
        self.keyboard = KeyboardController()
        self.matcher = ImageMatcher()
        self.ocr     = OCREngine()

    # ── Window management ─────────────────────────────────────

    def bring_to_front(self) -> bool:
        """Activate the GX Works3 main window.  Returns True on success."""
        return self.screen.bring_to_front(self.WINDOW_TITLE)

    def get_window_title(self) -> str:
        """Return the full window title (includes project name when open)."""
        return self.screen.get_window_title(self.WINDOW_TITLE)

    def get_window_rect(self) -> Optional[Dict[str, int]]:
        """Return the window bounding rect as {left, top, width, height}."""
        return self.screen.get_window_rect(self.WINDOW_TITLE)

    def is_open(self) -> bool:
        """Return True if a GX Works3 window exists."""
        return self.screen.get_window(self.WINDOW_TITLE) is not None

    # ── Dialog detection ──────────────────────────────────────

    def wait_for_dialog(self, title_fragment: str, timeout: float = 10.0) -> bool:
        """
        Wait for a dialog whose title contains title_fragment.
        Uses pygetwindow — dialogs are child windows with their own titles.

        Returns True if the dialog appeared within timeout.
        """
        import pygetwindow as gw
        deadline = time.time() + timeout
        while time.time() < deadline:
            windows = gw.getAllTitles()
            for w in windows:
                if title_fragment.lower() in w.lower():
                    return True
            time.sleep(0.3)
        return False

    def is_error_dialog_open(self) -> bool:
        """
        Heuristic check for an error/warning dialog.
        Looks for common GX Works3 error window titles.
        """
        import pygetwindow as gw
        error_keywords = ["error", "warning", "invalid", "cannot"]
        titles = [t.lower() for t in gw.getAllTitles()]
        return any(
            kw in title
            for title in titles
            for kw in error_keywords
        )

    def read_dialog_text(self) -> str:
        """
        Attempt to read the text of the topmost dialog via OCR.
        Returns the extracted text string.
        """
        # Take a screenshot and OCR a central region (where dialogs appear)
        w, h = self.screen.screen_size()
        region = (w // 4, h // 4, w // 2, h // 2)
        return self.ocr.read_screen_region(*region)

    def dismiss_dialog(self) -> None:
        """Press Enter to confirm (or Escape to cancel) any open dialog."""
        self.keyboard.press("enter")
        time.sleep(config.CLICK_DELAY)

    # ── Ladder editor state ───────────────────────────────────

    def is_ladder_editor_open(self) -> bool:
        """
        Return True if the ladder editor is currently the active inner window.

        Strategy: check for the presence of characteristic UI elements via
        image matching, then fall back to window title heuristic.
        """
        from pathlib import Path
        template = config.ASSETS_DIR / "ladder_editor_active.png"

        if template.exists():
            return self.matcher.is_visible(str(template))

        # Fallback: title should contain the POU name or "Ladder"
        title = self.get_window_title()
        return "ladder" in title.lower() or "main" in title.lower()

    # ── Ladder editor navigation ──────────────────────────────

    def navigate_to_cell(self, row: int = 0, col: int = 0) -> None:
        """
        Move the cursor to a specific cell in the ladder editor grid.

        Strategy:
          1. Press Ctrl+Home to jump to cell (0, 0).
          2. Press Right arrow `col` times to move to the target column.
          3. Press Down  arrow `row` times to move to the target row.

        This is more reliable than absolute pixel clicking because:
          - The grid scroll position may vary.
          - DPI scaling affects pixel coordinates.
        """
        logger.debug("navigate_to_cell(row=%d, col=%d)", row, col)

        # Home position
        self.keyboard.hotkey("ctrl", "home")
        time.sleep(0.3)

        # Move right to target column
        for _ in range(col * COL_KEY_STEPS):
            self.keyboard.press("right")
            time.sleep(0.05)

        # Move down to target row (parallel branch)
        for _ in range(row * ROW_KEY_STEPS):
            self.keyboard.press("down")
            time.sleep(0.05)

        time.sleep(0.2)

    def go_to_new_rung(self) -> None:
        """
        Move the cursor to the start of a new empty rung below the current one.
        In GX Works3, pressing End then Down takes you to the next rung.
        """
        self.keyboard.hotkey("ctrl", "end")   # last cell in current rung
        time.sleep(0.2)
        self.keyboard.press("down")           # move to next rung
        self.keyboard.hotkey("ctrl", "home")  # go to col 0
        time.sleep(0.3)

    # ── Screenshot helpers ─────────────────────────────────────

    def take_debug_screenshot(self, label: str = "debug") -> str:
        """Save a labelled screenshot to the logs directory."""
        filename = f"{label}_{int(time.time())}.png"
        return self.screen.capture_and_save(filename)
