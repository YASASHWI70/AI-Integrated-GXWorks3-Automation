"""
parsers/pdf_parser.py — PDF Document Parser
============================================

Extracts text from PDF documents (technical specs, wiring diagrams,
P&ID documents) and converts the content into a usable description
for the LLM.

LIMITATIONS (MVP):
  - Only extracts text, not images or vector drawings.
  - For scanned PDFs (image-only), OCR would be needed (pytesseract).
  - Complex table extraction is a future enhancement.

FUTURE:
  - Vision-language model to understand P&ID diagrams.
  - Automatic address extraction from I/O lists.
  - Table parsing for PLC I/O assignment sheets.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Extracts text from a PDF file for use as input to the LLM.

    Usage:
        parser = PDFParser()
        text   = parser.extract_text("spec.pdf")
    """

    def extract_text(self, pdf_path: str, max_chars: int = 8000) -> str:
        """
        Extract all text from a PDF and return it as a string.

        Args:
            pdf_path:  Path to the PDF file.
            max_chars: Maximum characters to return (avoids overwhelming the LLM).

        Returns:
            Extracted text string.

        Raises:
            FileNotFoundError: If the PDF does not exist.
            ImportError:       If no PDF library is installed.
            ValueError:        If the PDF contains no extractable text.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        text = self._try_pdfplumber(path) or self._try_pypdf2(path)

        if not text or not text.strip():
            raise ValueError(
                f"No text could be extracted from '{pdf_path}'. "
                "The PDF may be scanned (image-only). "
                "OCR support is planned for a future version."
            )

        logger.info(
            "PDF '%s': extracted %d characters.", path.name, len(text)
        )

        # Trim to max_chars to avoid token limits
        if len(text) > max_chars:
            logger.warning(
                "PDF text truncated from %d to %d chars.", len(text), max_chars
            )
            text = text[:max_chars] + "\n[... truncated ...]"

        return text

    def extract_pages(self, pdf_path: str) -> List[str]:
        """
        Extract text page-by-page and return a list of strings.

        Useful for very long documents where only certain pages are relevant.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                return [page.extract_text() or "" for page in pdf.pages]
        except ImportError:
            pass

        try:
            import PyPDF2
            with open(str(path), "rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                return [page.extract_text() or "" for page in reader.pages]
        except ImportError:
            raise ImportError(
                "No PDF library found. Install: pip install pdfplumber"
            )

    # ── Private helpers ───────────────────────────────────────

    def _try_pdfplumber(self, path: Path) -> Optional[str]:
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                return "\n\n".join(pages)
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("pdfplumber failed: %s", exc)
            return None

    def _try_pypdf2(self, path: Path) -> Optional[str]:
        try:
            import PyPDF2
            with open(str(path), "rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                pages  = [page.extract_text() or "" for page in reader.pages]
                return "\n\n".join(pages)
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("PyPDF2 failed: %s", exc)
            return None
