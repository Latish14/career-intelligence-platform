"""
text_cleaner.py
─────────────────────────────────────────────────────────────────────────────
Cleans and normalises raw text extracted from PDF or DOCX resumes.

Pipeline (applied in order)
----------------------------
1.  Decode / normalise Unicode          — smart quotes → ASCII, ligatures
                                          expanded, accented chars normalised.
2.  Strip null bytes & control chars    — \x00–\x08, \x0b, \x0c, \x0e–\x1f
                                          (keeps \t, \n, \r).
3.  Normalize line endings              — \r\n and \r → \n.
4.  Remove soft hyphens & zero-width    — \u00ad, \u200b–\u200d, \ufeff (BOM).
5.  Collapse horizontal whitespace      — multiple spaces/tabs on one line
                                          → single space.
6.  Fix broken hyphenated words         — "data-\nscientist" → "data-scientist"
                                          (PDF line-wrap artefact).
7.  Remove junk-only lines              — lines that contain no letter or digit
                                          (pure symbol rows from PDF tables).
8.  Collapse blank lines                — 3+ consecutive blank lines → 2.
9.  Strip leading/trailing whitespace   — per line and for the whole document.

What is deliberately NOT removed
----------------------------------
- Email addresses, URLs, phone numbers — entity extractors need these intact.
- Single special chars inside words     — hyphens, slashes, dots, @ signs.
- Unicode letters / accented names      — Résumé, José, etc. are kept.
- Bullet characters (•, ·, ◦, ▪, –)   — kept; normalised to "- " if desired
                                          via optional flag.

Public API
----------
    clean_text(raw: str, *, normalize_bullets: bool = False) -> CleanResult

    CleanResult  (TypedDict)
    ├── success          : bool
    ├── text             : str       # cleaned text, "" on failure / empty input
    ├── original_chars   : int
    ├── cleaned_chars    : int
    └── error            : str | None
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import TypedDict

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Return type ───────────────────────────────────────────────────────────────
class CleanResult(TypedDict):
    success: bool
    text: str
    original_chars: int
    cleaned_chars: int
    error: str | None


# ── Unicode normalisation map ─────────────────────────────────────────────────
# Expand common ligatures and typographic characters that pdfplumber / pypdf
# sometimes emit verbatim instead of their ASCII equivalents.
_UNICODE_REPLACEMENTS: list[tuple[str, str]] = [
    # Ligatures
    ("\ufb01", "fi"),   # ﬁ
    ("\ufb02", "fl"),   # ﬂ
    ("\ufb03", "ffi"),  # ﬃ
    ("\ufb04", "ffl"),  # ﬄ
    ("\ufb00", "ff"),   # ﬀ
    ("\ufb05", "st"),   # ﬅ
    ("\ufb06", "st"),   # ﬆ
    # Typographic quotes → straight ASCII
    ("\u2018", "'"), ("\u2019", "'"),   # ' '
    ("\u201c", '"'), ("\u201d", '"'),   # " "
    ("\u201a", "'"), ("\u201e", '"'),   # ‚  „
    # Dashes → hyphen-minus (keep en-dash/em-dash as-is by default;
    # only replace the ones that break word tokenisation)
    ("\u2013", "-"),   # en-dash  –
    ("\u2014", "-"),   # em-dash  —
    ("\u2015", "-"),   # horizontal bar ―
    # Ellipsis
    ("\u2026", "..."),
    # Non-breaking space and thin space → regular space
    ("\u00a0", " "),
    ("\u202f", " "),
    ("\u2009", " "),
    ("\u2002", " "),
    ("\u2003", " "),
    # Bullet variants — handled separately via normalize_bullets flag
]

# Build a single translation table for O(1) replacement
_UNICODE_TABLE = str.maketrans(dict(_UNICODE_REPLACEMENTS))

# ── Compiled regexes ──────────────────────────────────────────────────────────

# Control characters: 0x00–0x08, 0x0b, 0x0c, 0x0e–0x1f  (keep \t \n \r)
_RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Zero-width and invisible formatting characters
_RE_ZERO_WIDTH = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff]")

# Horizontal whitespace (space + tab) runs → single space
_RE_HSPACE = re.compile(r"[ \t]{2,}")

# Hyphenated line-break artefact: "word-\nrest" or "word-\n rest"
# Requires a word character before the hyphen so it doesn't fire on
# separator lines like "--------\nNextSection".
_RE_BROKEN_HYPHEN = re.compile(r"(?<=\w)(-)\n\s*(?=[a-zA-Z])")

# Lines that contain zero alphanumerics (junk separator lines from PDF tables)
_RE_JUNK_LINE = re.compile(r"^[^a-zA-Z0-9\u00c0-\u024f]+$")

# Three or more consecutive blank lines → 2 blank lines
_RE_MULTI_BLANK = re.compile(r"\n{3,}")

# Bullet characters to normalise (when normalize_bullets=True)
_RE_BULLETS = re.compile(r"^[\u2022\u00b7\u25e6\u25aa\u2023\u2043\u204c\u204d]\s*",
                          re.MULTILINE)


# ── Pipeline steps ────────────────────────────────────────────────────────────

def _unicode_normalise(text: str) -> str:
    """
    1. NFC normalisation (combines base + combining chars where possible).
    2. Expand ligatures + typographic punctuation via translation table.
    """
    text = unicodedata.normalize("NFC", text)
    return text.translate(_UNICODE_TABLE)


def _strip_control_chars(text: str) -> str:
    return _RE_CONTROL.sub("", text)


def _normalise_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strip_zero_width(text: str) -> str:
    return _RE_ZERO_WIDTH.sub("", text)


def _collapse_hspace(text: str) -> str:
    # Apply per line to avoid crossing line boundaries
    return "\n".join(
        _RE_HSPACE.sub(" ", line) for line in text.split("\n")
    )


def _fix_broken_hyphens(text: str) -> str:
    return _RE_BROKEN_HYPHEN.sub(r"\1", text)


def _remove_junk_lines(text: str) -> str:
    return "\n".join(
        line for line in text.split("\n")
        if not _RE_JUNK_LINE.match(line)
    )


def _collapse_blank_lines(text: str) -> str:
    return _RE_MULTI_BLANK.sub("\n\n", text)


def _strip_whitespace(text: str) -> str:
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _normalise_bullets(text: str) -> str:
    """Replace leading bullet symbols with '- ' for uniform downstream parsing."""
    return _RE_BULLETS.sub("- ", text)


# ── Public API ────────────────────────────────────────────────────────────────

def clean_text(raw: str, *, normalize_bullets: bool = False) -> CleanResult:
    """
    Clean raw resume text through a deterministic multi-step pipeline.

    Parameters
    ----------
    raw : str
        Raw text as returned by pdf_reader or docx_reader.
    normalize_bullets : bool, default False
        When True, leading bullet symbols (•, ·, ◦, ▪…) on any line are
        replaced with '- ' for uniform downstream parsing.

    Returns
    -------
    CleanResult
        - success        (bool) : False only if raw is not a string.
        - text           (str)  : Cleaned text; "" for empty input.
        - original_chars (int)  : len(raw) before cleaning.
        - cleaned_chars  (int)  : len(text) after cleaning.
        - error          (str)  : None on success.

    Notes
    -----
    - The pipeline never removes email addresses, URLs, or phone numbers.
    - Accented / Unicode name characters (é, ñ, ü…) are preserved.
    - An empty string input is valid and returns success=True, text="".
    """
    if not isinstance(raw, str):
        msg = f"clean_text expects str, got {type(raw).__name__}"
        logger.error(msg)
        return CleanResult(
            success=False, text="", original_chars=0,
            cleaned_chars=0, error=msg,
        )

    original_chars = len(raw)

    if not raw.strip():
        logger.debug("clean_text received blank/empty input.")
        return CleanResult(
            success=True, text="", original_chars=original_chars,
            cleaned_chars=0, error=None,
        )

    try:
        text = _unicode_normalise(raw)
        text = _strip_control_chars(text)
        text = _normalise_line_endings(text)
        text = _strip_zero_width(text)
        text = _collapse_hspace(text)
        text = _fix_broken_hyphens(text)
        text = _remove_junk_lines(text)
        text = _collapse_blank_lines(text)
        if normalize_bullets:
            text = _normalise_bullets(text)
        text = _strip_whitespace(text)

    except Exception as exc:  # noqa: BLE001
        msg = f"text_cleaner pipeline error: {exc}"
        logger.error(msg)
        return CleanResult(
            success=False, text="", original_chars=original_chars,
            cleaned_chars=0, error=msg,
        )

    cleaned_chars = len(text)
    logger.debug(
        "clean_text: %d → %d chars (%.1f%% reduction).",
        original_chars, cleaned_chars,
        100 * (1 - cleaned_chars / original_chars) if original_chars else 0,
    )
    return CleanResult(
        success=True, text=text, original_chars=original_chars,
        cleaned_chars=cleaned_chars, error=None,
    )