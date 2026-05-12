"""
automation_layer/ocr_engine.py — Tesseract OCR Wrapper
=======================================================

Used to read text from screenshots when we need to:
  • Verify the window title matches what we expect
  • Read error messages from dialog boxes
  • Detect text in the ladder editor (addresses, comments)
  • Confirm that a contact/coil was inserted with the correct address

INSTALLATION:
    1. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
    2. Set TESSERACT_PATH in .env  (default: C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
    3. pip install pytesseract

NOTE: OCR is used as a fallback / verification layer.  The primary
automation flow uses keyboard shortcuts, not OCR.  OCR is slower and
less reliable, so minimise its use in the hot path.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, Tuple

import pytesseract
from PIL import Image
import numpy as np
import cv2

import config
from .screen_manager import ScreenManager

logger = logging.getLogger(__name__)

# Point pytesseract at the Tesseract binary
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH


class OCREngine:
    """
    Reads text from screen regions using Tesseract OCR.

    Usage:
        ocr = OCREngine()
        text = ocr.read_screen_region(left=100, top=50, width=400, height=80)
        if "Error" in text:
            handle_error()
    """

    def __init__(self) -> None:
        self._screen = ScreenManager()

    # ── Public API ────────────────────────────────────────────

    def read_screen_region(
        self,
        left:   int,
        top:    int,
        width:  int,
        height: int,
        preprocess: bool = True,
    ) -> str:
        """
        Capture a screen region and return its text content.

        Args:
            left, top, width, height: Region in screen pixels.
            preprocess: If True, applies image enhancement before OCR.

        Returns:
            Recognised text string (may include newlines).
        """
        region    = (left, top, width, height)
        image     = self._screen.capture(region=region)
        if preprocess:
            image = self._preprocess(image)
        text = self._run_ocr(image)
        logger.debug("OCR region (%d,%d,%d,%d) → %r", left, top, width, height, text)
        return text

    def read_full_screen(self, preprocess: bool = False) -> str:
        """Run OCR on the entire screen.  Slow — use for debugging only."""
        image = self._screen.capture()
        if preprocess:
            image = self._preprocess(image)
        return self._run_ocr(image)

    def read_image_file(self, path: str, preprocess: bool = True) -> str:
        """Run OCR on a saved image file."""
        try:
            image = Image.open(path)
            if preprocess:
                image = self._preprocess(image)
            return self._run_ocr(image)
        except Exception as exc:
            logger.error("OCR failed on '%s': %s", path, exc)
            return ""

    def find_text_on_screen(
        self,
        text:       str,
        region: Optional[Tuple[int, int, int, int]] = None,
        case_sensitive: bool = False,
    ) -> bool:
        """
        Return True if the given text is visible on screen (or in region).

        Useful for dialog confirmation:
            if ocr.find_text_on_screen("Save"):
                keyboard.press("enter")
        """
        if region:
            found = self.read_screen_region(*region)
        else:
            found = self.read_full_screen()

        if not case_sensitive:
            return text.lower() in found.lower()
        return text in found

    # ── Preprocessing ─────────────────────────────────────────

    def _preprocess(self, image: Image.Image) -> Image.Image:
        """
        Improve OCR accuracy by:
        1. Converting to grayscale
        2. Upscaling 2× (Tesseract works better at higher DPI)
        3. Applying Otsu thresholding (binarize)
        4. Removing noise (median blur)
        """
        # Convert PIL → OpenCV
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

        # Upscale
        h, w = cv_img.shape[:2]
        cv_img = cv2.resize(cv_img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        # Binarize
        _, cv_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Light denoise
        cv_img = cv2.medianBlur(cv_img, 3)

        # Convert back to PIL
        return Image.fromarray(cv_img)

    # ── OCR call ──────────────────────────────────────────────

    def _run_ocr(self, image: Image.Image) -> str:
        """Call Tesseract and return cleaned text."""
        try:
            text = pytesseract.image_to_string(
                image,
                config="--psm 6",    # Assume uniform block of text
            )
            return text.strip()
        except Exception as exc:
            logger.warning("Tesseract OCR error: %s", exc)
            return ""
