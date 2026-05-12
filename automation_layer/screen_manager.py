"""
automation_layer/screen_manager.py — Screenshot & Window Management
====================================================================

Provides utilities for:
  • Taking screenshots (full screen or region)
  • Listing and focusing windows by title
  • Waiting for a window to appear
  • Querying window position / size

All screen operations are wrapped in try/except so a missing window
causes a clean exception rather than a cryptic pygetwindow error.
"""

from __future__ import annotations
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict

import pyautogui
import pygetwindow as gw
from PIL import Image

import config

logger = logging.getLogger(__name__)


class ScreenManager:
    """
    Wraps pyautogui and pygetwindow for stable screen interaction.

    Usage:
        sm = ScreenManager()
        sm.bring_window_to_front("GX Works3")
        screenshot = sm.capture()
        sm.save_screenshot(screenshot, "before_insert.png")
    """

    def __init__(self) -> None:
        # Apply global pyautogui safety settings
        pyautogui.PAUSE      = config.PYAUTOGUI_PAUSE
        pyautogui.FAILSAFE   = config.PYAUTOGUI_FAILSAFE

    # ── Screenshots ───────────────────────────────────────────

    def capture(
        self,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Image.Image:
        """
        Take a screenshot and return it as a PIL Image.

        Args:
            region: Optional (left, top, width, height) in pixels.
                    If None, captures the entire screen.

        Returns:
            PIL Image object.
        """
        time.sleep(config.SCREENSHOT_DELAY)
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()
        return screenshot

    def save_screenshot(self, image: Image.Image, filename: str) -> str:
        """
        Save a PIL Image to the logs directory.

        Returns the full path of the saved file.
        """
        path = config.LOGS_DIR / filename
        image.save(str(path))
        logger.debug("Screenshot saved: %s", path)
        return str(path)

    def capture_and_save(
        self,
        filename: str,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> str:
        """Capture and immediately save a screenshot.  Returns the file path."""
        img = self.capture(region)
        return self.save_screenshot(img, filename)

    # ── Window management ─────────────────────────────────────

    def get_window(self, title_fragment: str) -> Optional[gw.Win32Window]:
        """
        Find the first window whose title contains title_fragment.

        Case-insensitive match.  Returns None if no window found.
        """
        try:
            windows = gw.getWindowsWithTitle(title_fragment)
            if windows:
                return windows[0]
        except Exception as exc:
            logger.debug("get_window('%s') error: %s", title_fragment, exc)
        return None

    def bring_to_front(self, title_fragment: str) -> bool:
        """
        Bring the first matching window to the foreground.

        Returns:
            True if the window was found and activated.
            False if no window with that title exists.
        """
        win = self.get_window(title_fragment)
        if win is None:
            logger.warning("bring_to_front: no window titled '%s'", title_fragment)
            return False
        try:
            if win.isMinimized:
                win.restore()
                time.sleep(0.3)
            win.activate()
            time.sleep(0.5)
            logger.debug("Window '%s' brought to front.", win.title)
            return True
        except Exception as exc:
            logger.warning("Could not activate window '%s': %s", win.title, exc)
            # Try win32 API fallback
            return self._activate_via_win32(title_fragment)

    def _activate_via_win32(self, title_fragment: str) -> bool:
        """Use win32gui to force-activate a window (fallback)."""
        try:
            import win32gui, win32con
            def _callback(hwnd, _):
                if title_fragment.lower() in win32gui.GetWindowText(hwnd).lower():
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    return False    # stop enumeration
                return True
            win32gui.EnumWindows(_callback, None)
            return True
        except Exception as exc:
            logger.warning("win32 activate fallback failed: %s", exc)
            return False

    def wait_for_window(
        self,
        title_fragment: str,
        timeout: float = config.MAX_WAIT_TIME,
    ) -> bool:
        """
        Block until a window with the given title appears or timeout expires.

        Returns:
            True if the window appeared within the timeout.
            False if the timeout was reached.
        """
        deadline = time.time() + timeout
        logger.info("Waiting for window '%s' (timeout=%.0fs) …", title_fragment, timeout)
        while time.time() < deadline:
            if self.get_window(title_fragment):
                logger.info("Window '%s' appeared.", title_fragment)
                return True
            time.sleep(0.5)
        logger.warning("Timeout waiting for window '%s'.", title_fragment)
        return False

    def get_window_rect(self, title_fragment: str) -> Optional[Dict[str, int]]:
        """
        Return the position and size of the first matching window.

        Returns:
            Dict with keys: left, top, width, height
            or None if the window is not found.
        """
        win = self.get_window(title_fragment)
        if win is None:
            return None
        try:
            return {
                "left":   win.left,
                "top":    win.top,
                "width":  win.width,
                "height": win.height,
            }
        except Exception as exc:
            logger.debug("get_window_rect error: %s", exc)
            return None

    def get_window_title(self, title_fragment: str) -> str:
        """Return the full title of the first matching window, or empty string."""
        win = self.get_window(title_fragment)
        if win:
            return win.title
        return ""

    # ── Screen info ───────────────────────────────────────────

    def screen_size(self) -> Tuple[int, int]:
        """Return (width, height) of the primary screen."""
        return pyautogui.size()

    def screen_center(self) -> Tuple[int, int]:
        """Return the pixel coordinates of the screen center."""
        w, h = self.screen_size()
        return w // 2, h // 2
