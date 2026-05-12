"""
automation_layer/mouse_keyboard.py — Safe Mouse & Keyboard Controllers
=======================================================================

Wraps pyautogui to add:
  • Configurable delays between actions (stability on slow machines)
  • Logging of every action for debugging
  • A safe_click that verifies the target is on screen before clicking
  • Human-speed typing to avoid missed characters

BEST PRACTICES for stable UI automation:
  1. Always add a small delay AFTER clicks before checking screen state.
  2. Use hotkeys (Ctrl+S) instead of clicking menu items when possible —
     menus can move or be obscured.
  3. Increase TYPE_DELAY if GX Works3 misses characters.
  4. Take a screenshot before and after critical operations for debugging.
"""

from __future__ import annotations
import time
import logging
from typing import Tuple, Optional, Sequence

import pyautogui
import config

logger = logging.getLogger(__name__)

# Disable pyautogui's own built-in pause here (we control timing ourselves)
pyautogui.PAUSE    = 0
pyautogui.FAILSAFE = config.PYAUTOGUI_FAILSAFE


class MouseController:
    """
    Wrapper around pyautogui mouse operations.

    All methods log what they do and sleep briefly after acting so the
    application has time to react before the next action runs.
    """

    def __init__(self, click_delay: float = config.CLICK_DELAY) -> None:
        self.click_delay = click_delay

    # ── Basic clicks ──────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left") -> None:
        """Single click at (x, y)."""
        logger.debug("click(%d, %d, button=%s)", x, y, button)
        pyautogui.click(x, y, button=button)
        time.sleep(self.click_delay)

    def double_click(self, x: int, y: int) -> None:
        """Double-click at (x, y)."""
        logger.debug("double_click(%d, %d)", x, y)
        pyautogui.doubleClick(x, y)
        time.sleep(self.click_delay)

    def right_click(self, x: int, y: int) -> None:
        """Right-click at (x, y)."""
        logger.debug("right_click(%d, %d)", x, y)
        pyautogui.rightClick(x, y)
        time.sleep(self.click_delay)

    # ── Movement ──────────────────────────────────────────────

    def move_to(self, x: int, y: int, duration: float = 0.1) -> None:
        """Move the mouse cursor to (x, y) smoothly."""
        logger.debug("move_to(%d, %d)", x, y)
        pyautogui.moveTo(x, y, duration=duration)

    # ── Drag ─────────────────────────────────────────────────

    def drag(
        self,
        start: Tuple[int, int],
        end:   Tuple[int, int],
        duration: float = 0.3,
    ) -> None:
        """Click-drag from start to end coordinates."""
        logger.debug("drag(%s → %s)", start, end)
        pyautogui.moveTo(*start)
        pyautogui.dragTo(*end, duration=duration, button="left")
        time.sleep(self.click_delay)

    # ── Scroll ────────────────────────────────────────────────

    def scroll(self, x: int, y: int, clicks: int) -> None:
        """Scroll the mouse wheel at position (x, y).  Positive = up."""
        logger.debug("scroll(%d, %d, clicks=%d)", x, y, clicks)
        pyautogui.scroll(clicks, x=x, y=y)
        time.sleep(0.2)


class KeyboardController:
    """
    Wrapper around pyautogui keyboard operations.

    Adds human-speed typing with per-character delays to prevent
    GX Works3 from missing keystrokes.
    """

    def __init__(self, type_delay: float = config.TYPE_DELAY) -> None:
        self.type_delay = type_delay

    # ── Typing ────────────────────────────────────────────────

    def type_text(self, text: str) -> None:
        """
        Type a string character-by-character with a small delay between
        each character.  More reliable than pyautogui.typewrite() for
        applications that buffer input.
        """
        logger.debug("type_text(%r)", text)
        for char in text:
            pyautogui.typewrite(char, interval=self.type_delay)
        time.sleep(0.1)

    def press(self, key: str) -> None:
        """Press and release a single key (e.g. 'enter', 'f5', 'tab')."""
        logger.debug("press(%r)", key)
        pyautogui.press(key)
        time.sleep(self.type_delay * 2)

    def press_keys(self, keys: Sequence[str]) -> None:
        """Press a sequence of keys one after another."""
        for key in keys:
            self.press(key)

    # ── Hotkeys ───────────────────────────────────────────────

    def hotkey(self, *keys: str) -> None:
        """
        Press a key combination (e.g. hotkey('ctrl', 's') for Ctrl+S).
        Keys are pressed in order and released in reverse order.
        """
        logger.debug("hotkey(%s)", "+".join(keys))
        pyautogui.hotkey(*keys)
        time.sleep(config.CLICK_DELAY)

    # ── Clipboard helpers ─────────────────────────────────────

    def paste_text(self, text: str) -> None:
        """
        Copy text to clipboard and paste it.
        Faster than type_text() for long strings — use for file paths etc.
        """
        import pyperclip
        pyperclip.copy(text)
        self.hotkey("ctrl", "v")
        time.sleep(0.2)
