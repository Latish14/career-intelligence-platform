"""
pdf_reader.py
─────────────────────────────────────────────────────────────────────────────
Extracts raw text from PDF resumes.

Strategy
--------
1. PRIMARY  — pdfplumber  : layout-aware extraction; handles multi-column PDFs.
2. FALLBACK — pypdf       : used when pdfplumber yields an empty/whitespace-only
                            result or raises an unrecoverable error.
3. PAGE-LEVEL ISOLATION   : a failure on one page never aborts the full job;
                            the page is skipped and logged.

Public API
----------
    extract_text_from_pdf(file_path: str | Path) -> PDFResult

    PDFResult  (TypedDict)
    ├── success   : bool
    ├── text      : str          # joined page text (empty string on failure)
    ├── pages     : int          # total pages detected (0 on failure)
    ├── method    : str          # "pdfplumber" | "pypdf" | "none"
    └── error     : str | None   # human-readable message on failure
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import PdfReadError

# ── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())   # caller configures handlers


# ── Return type ──────────────────────────────────────────────────────────────
class PDFResult(TypedDict):
    success: bool
    text: str
    pages: int
    method: str
    error: str | None


# ── Internal helpers ─────────────────────────────────────────────────────────

def _validate_path(file_path: str | Path) -> tuple[Path, PDFResult | None]:
    """
    Resolve and validate the file path before any IO.

    Returns (Path, None) on success or (Path, PDFResult) with an error result
    that the caller should return immediately.
    """
    path = Path(file_path).resolve()

    if not path.exists():
        return path, _error_result(f"File not found: {path}")

    if not path.is_file():
        return path, _error_result(f"Path is not a file: {path}")

    if path.suffix.lower() != ".pdf":
        return path, _error_result(
            f"Unsupported file extension '{path.suffix}'. Expected .pdf"
        )

    if path.stat().st_size == 0:
        return path, _error_result(f"File is empty: {path}")

    return path, None


def _error_result(message: str) -> PDFResult:
    logger.error(message)
    return PDFResult(
        success=False,
        text="",
        pages=0,
        method="none",
        error=message,
    )


def _is_blank(text: str | None) -> bool:
    return not text or not text.strip()


# ── Primary extractor: pdfplumber ────────────────────────────────────────────

def _extract_pdfplumber(path: Path) -> tuple[str, int] | None:
    """
    Extract text using pdfplumber.

    Returns (joined_text, page_count) or None if the library raises a
    fatal error (corrupt file, encrypted, etc.).

    Individual page failures are logged and skipped.
    """
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            page_texts: list[str] = []

            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    raw = page.extract_text(
                        x_tolerance=2,       # tighter glyph grouping
                        y_tolerance=3,
                        layout=True,         # preserve reading order
                        x_density=7.25,
                        y_density=13,
                    )
                    if not _is_blank(raw):
                        page_texts.append(raw.strip())
                    else:
                        logger.debug("pdfplumber: page %d yielded no text.", idx)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "pdfplumber: skipping page %d due to error: %s", idx, exc
                    )

            return "\n\n".join(page_texts), page_count

    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber failed for %s: %s", path.name, exc)
        return None


# ── Fallback extractor: pypdf ─────────────────────────────────────────────────

def _extract_pypdf(path: Path) -> tuple[str, int] | None:
    """
    Fallback text extraction using pypdf.

    Returns (joined_text, page_count) or None on fatal error.
    """
    try:
        reader = PdfReader(str(path))

        # Encrypted PDFs without a known password cannot be parsed.
        if reader.is_encrypted:
            logger.warning("pypdf: file is encrypted and cannot be read: %s", path.name)
            return None

        page_count = len(reader.pages)
        page_texts: list[str] = []

        for idx, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text()
                if not _is_blank(raw):
                    page_texts.append(raw.strip())
                else:
                    logger.debug("pypdf: page %d yielded no text.", idx)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pypdf: skipping page %d due to error: %s", idx, exc
                )

        return "\n\n".join(page_texts), page_count

    except PdfReadError as exc:
        logger.warning("pypdf PdfReadError for %s: %s", path.name, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("pypdf unexpected error for %s: %s", path.name, exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str | Path) -> PDFResult:
    """
    Extract all text from a PDF file.

    Parameters
    ----------
    file_path : str | Path
        Absolute or relative path to a .pdf file.

    Returns
    -------
    PDFResult
        A typed dict with keys:
        - success (bool)   : True if text was extracted.
        - text    (str)    : Extracted text joined across all pages.
        - pages   (int)    : Number of pages in the PDF.
        - method  (str)    : Which library was used.
        - error   (str|None): Error message if success is False.

    Notes
    -----
    - pdfplumber is tried first for its superior layout-awareness.
    - pypdf is used as a fallback when pdfplumber returns blank text or errors.
    - Encrypted/password-protected PDFs return success=False.
    - Image-only (scanned) PDFs may return text="" with success=False;
      integrate an OCR step (e.g. pytesseract) upstream if needed.
    """
    path, validation_error = _validate_path(file_path)
    if validation_error is not None:
        return validation_error

    logger.info("Starting PDF extraction: %s", path.name)

    # ── Attempt 1: pdfplumber ─────────────────────────────────────────────────
    plumber_result = _extract_pdfplumber(path)

    if plumber_result is not None:
        text, pages = plumber_result
        if not _is_blank(text):
            logger.info(
                "pdfplumber succeeded (%d pages, %d chars).", pages, len(text)
            )
            return PDFResult(
                success=True,
                text=text,
                pages=pages,
                method="pdfplumber",
                error=None,
            )
        logger.info("pdfplumber returned blank text; trying pypdf fallback.")
    else:
        logger.info("pdfplumber raised an error; trying pypdf fallback.")

    # ── Attempt 2: pypdf fallback ─────────────────────────────────────────────
    pypdf_result = _extract_pypdf(path)

    if pypdf_result is not None:
        text, pages = pypdf_result
        if not _is_blank(text):
            logger.info(
                "pypdf fallback succeeded (%d pages, %d chars).", pages, len(text)
            )
            return PDFResult(
                success=True,
                text=text,
                pages=pages,
                method="pypdf",
                error=None,
            )
        # Both engines extracted nothing — likely a scanned/image-only PDF.
        page_count = pages  # still report the page count
        msg = (
            f"No text layer found in '{path.name}'. "
            "The file may be a scanned (image-only) PDF. "
            "Consider running an OCR pre-processing step."
        )
        logger.warning(msg)
        return PDFResult(
            success=False,
            text="",
            pages=page_count,
            method="none",
            error=msg,
        )

    # Both engines failed fatally.
    msg = (
        f"All extraction methods failed for '{path.name}'. "
        "The file may be corrupt, encrypted, or in an unsupported format."
    )
    return _error_result(msg)