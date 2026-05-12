"""
automation_layer/image_matcher.py — OpenCV Template Matching
=============================================================

Used to locate UI elements (buttons, icons, dialog titles) on screen
by comparing a pre-saved reference screenshot ("template") against
the live screen capture.

HOW TEMPLATE MATCHING WORKS:
    OpenCV slides the template image over the screen image and computes
    a similarity score at each position.  We report a match when the
    maximum score exceeds the confidence threshold.

BEST PRACTICES:
  • Capture template images at the same display resolution/scale as the
    target machine (DPI scaling matters!).
  • Crop templates tightly around the element — no extra whitespace.
  • Use grayscale matching for speed; only use colour if elements are
    hard to distinguish in grayscale.
  • Keep template images in assets/ and commit them to source control.
  • If the same button appears in multiple places, prefer keyboard
    shortcuts over image matching.
"""

from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np
from PIL import Image

import config
from .screen_manager import ScreenManager

logger = logging.getLogger(__name__)


class ImageMatcher:
    """
    Finds UI elements on screen using OpenCV template matching.

    Usage:
        matcher = ImageMatcher()
        location = matcher.find_on_screen("assets/ok_button.png")
        if location:
            mouse.click(*location)
    """

    def __init__(
        self,
        confidence: float = config.IMAGE_MATCH_CONFIDENCE,
        grayscale:  bool  = config.IMAGE_MATCH_GRAYSCALE,
    ) -> None:
        self.confidence = confidence
        self.grayscale  = grayscale
        self._screen    = ScreenManager()

    # ── Core matching ─────────────────────────────────────────

    def find_on_screen(
        self,
        template_path: str,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Search for a template image on the current screen.

        Args:
            template_path: Path to the template PNG file.
            region: Optional (left, top, width, height) search area.
                    Searches the whole screen if None.

        Returns:
            (x, y) pixel coordinates of the template's centre, or None.
        """
        template = self._load_template(template_path)
        if template is None:
            return None

        screenshot = np.array(self._screen.capture(region=region))

        if self.grayscale:
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
            template_gray   = cv2.cvtColor(template,   cv2.COLOR_RGB2GRAY) \
                              if len(template.shape) == 3 else template
            haystack = screenshot_gray
            needle   = template_gray
        else:
            haystack = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            needle   = cv2.cvtColor(template,   cv2.COLOR_RGB2BGR)

        result  = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= self.confidence:
            h, w = needle.shape[:2]
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2

            # If region-relative, convert to screen coordinates
            if region:
                cx += region[0]
                cy += region[1]

            logger.debug(
                "Found '%s' at (%d, %d) confidence=%.2f",
                Path(template_path).name, cx, cy, max_val,
            )
            return cx, cy

        logger.debug(
            "Template '%s' not found (best=%.2f, threshold=%.2f)",
            Path(template_path).name, max_val, self.confidence,
        )
        return None

    def find_all_on_screen(
        self,
        template_path: str,
        region: Optional[Tuple[int, int, int, int]] = None,
        max_results: int = 20,
    ) -> List[Tuple[int, int]]:
        """
        Find ALL occurrences of a template on screen.

        Returns a list of (x, y) centre coordinates.  Useful for
        detecting multiple instances of the same element (e.g. all
        rungs in a ladder view).
        """
        template = self._load_template(template_path)
        if template is None:
            return []

        screenshot = np.array(self._screen.capture(region=region))

        if self.grayscale:
            haystack = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
            needle   = cv2.cvtColor(template,   cv2.COLOR_RGB2GRAY) \
                       if len(template.shape) == 3 else template
        else:
            haystack = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            needle   = cv2.cvtColor(template,   cv2.COLOR_RGB2BGR)

        h, w  = needle.shape[:2]
        result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)

        # Threshold
        locations = np.where(result >= self.confidence)
        points    = list(zip(*locations[::-1]))   # (x, y) pairs

        # Non-maximum suppression: deduplicate nearby matches
        deduplicated: List[Tuple[int, int]] = []
        for pt in points[:max_results]:
            cx = pt[0] + w // 2
            cy = pt[1] + h // 2
            # Skip if too close to an existing match
            if all(abs(cx - ex) > w // 2 or abs(cy - ey) > h // 2
                   for ex, ey in deduplicated):
                if region:
                    cx += region[0]
                    cy += region[1]
                deduplicated.append((cx, cy))

        return deduplicated

    def wait_for_image(
        self,
        template_path: str,
        timeout:       float = config.MAX_WAIT_TIME,
        poll_interval: float = 0.5,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Block until the template appears on screen or timeout expires.

        Returns:
            (x, y) coordinates if found, else None.
        """
        deadline = time.time() + timeout
        logger.info(
            "Waiting for '%s' (timeout=%.0fs) …",
            Path(template_path).name, timeout,
        )
        while time.time() < deadline:
            loc = self.find_on_screen(template_path, region)
            if loc:
                return loc
            time.sleep(poll_interval)
        logger.warning("Timed out waiting for '%s'.", Path(template_path).name)
        return None

    def is_visible(self, template_path: str) -> bool:
        """Return True if the template is currently visible on screen."""
        return self.find_on_screen(template_path) is not None

    # ── Private helpers ───────────────────────────────────────

    def _load_template(self, path: str) -> Optional[np.ndarray]:
        """Load a template image from disk as a NumPy array (RGB)."""
        try:
            img = Image.open(path).convert("RGB")
            return np.array(img)
        except FileNotFoundError:
            logger.warning("Template image not found: %s", path)
            return None
        except Exception as exc:
            logger.error("Failed to load template '%s': %s", path, exc)
            return None
