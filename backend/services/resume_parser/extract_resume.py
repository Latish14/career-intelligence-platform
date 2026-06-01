"""
extract_resume.py
─────────────────────────────────────────────────────────────────────────────
Top-level orchestrator for the services.resume_parser module.

Workflow
--------
1. Detect format (.pdf / .docx)
2. Extract raw text  →  pdf_reader  or  docx_reader
3. Clean text        →  text_cleaner
4. Extract entities  →  name, email, phone  (regex + heuristics)
5. Return structured output

Public API
----------
    parse_resume(file_path: str | Path) -> ResumeData

    ResumeData  (TypedDict)
    ├── name       : str         # "" if not found
    ├── email      : str         # "" if not found
    ├── phone      : str         # "" if not found
    ├── raw_text   : str         # cleaned full text; "" on failure
    ├── success    : bool
    └── error      : str | None  # human-readable on failure

Entity extraction strategy
---------------------------
EMAIL   — RFC-5321-ish regex; takes the first match.

PHONE   — Covers the most common international and Indian formats:
            +91-XXXXX-XXXXX  |  +1 (XXX) XXX-XXXX  |  XXX.XXX.XXXX
            10-digit runs     |  numbers with country codes
          Takes the first match found.

NAME    — No ML model; pure heuristic (avoids heavy dependencies):
          1. Look for a line labelled "Name:" anywhere in the first 30 lines.
          2. Scan the first 15 lines for the first line that:
             • contains only capitalised words (Title Case or ALL CAPS)
             • has 2–5 tokens
             • contains no email / URL / digit sequences
             • is not a known section heading (EDUCATION, SKILLS, …)
          3. Fallback: first non-empty line in the document.
          Returns "" when confidence is too low.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TypedDict

from services.resume_parser.pdf_reader import extract_text_from_pdf
from services.resume_parser.docx_reader import extract_text_from_docx
from services.resume_parser.text_cleaner import clean_text

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Return type ───────────────────────────────────────────────────────────────
class ResumeData(TypedDict):
    name: str
    email: str
    phone: str
    raw_text: str
    success: bool
    error: str | None


# ── Regex patterns ────────────────────────────────────────────────────────────

# Email — handles sub-domains, plus-addressing, dots in local part
_RE_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone — covers:
#   +91-98765-43210   +91 98765 43210   +1 (555) 123-4567
#   (555) 123-4567    555-123-4567      555.123.4567
#   9876543210        +919876543210
_RE_PHONE = re.compile(
    r"""
    (?:
        \+?[\d\s\-().]{7,20}\d   # general international / local pattern
    )
    """,
    re.VERBOSE,
)

# Stricter phone — used to validate candidates from the broad pattern above.
# Must contain 7–15 digits after stripping non-numeric chars.
_RE_DIGITS_ONLY = re.compile(r"\d")

# Known section headings to skip during name detection
_SECTION_HEADINGS = frozenset({
    "education", "experience", "skills", "summary", "objective",
    "profile", "projects", "certifications", "achievements",
    "awards", "publications", "interests", "hobbies", "languages",
    "references", "contact", "work", "employment", "career",
    "technical", "professional", "personal", "details", "information",
    "resume", "curriculum", "vitae", "cv",
})

# Tokens that disqualify a line from being a name
_RE_DISQUALIFY_NAME = re.compile(
    r"""
    @                   |   # email
    https?://           |   # URL
    www\.               |   # URL without scheme
    \d{4,}              |   # long digit run (year / phone fragment)
    [|/\\<>{}()\[\]]        # structural punctuation
    """,
    re.VERBOSE | re.IGNORECASE,
)

# A "name token": starts with a letter (including accented), may contain
# hyphens or apostrophes (O'Brien, Jean-Paul), must be >= 2 chars.
_RE_NAME_TOKEN = re.compile(
    r"^[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f'\-]{1,}$"
)


# ── Entity extractors ─────────────────────────────────────────────────────────

def _extract_email(text: str) -> str:
    m = _RE_EMAIL.search(text)
    return m.group(0).lower() if m else ""


def _extract_phone(text: str) -> str:
    """
    Find the first plausible phone number.
    1. Run broad regex to find candidate substrings.
    2. Count digits; accept only if 7–15 digits present.
    3. Return the match stripped of surrounding whitespace.
    """
    for m in _RE_PHONE.finditer(text):
        candidate = m.group(0).strip()
        digit_count = len(_RE_DIGITS_ONLY.findall(candidate))
        if 7 <= digit_count <= 15:
            return candidate
    return ""


def _is_name_line(line: str) -> bool:
    """
    Return True when *line* looks like a person's name.

    Criteria (all must hold):
    - 2 to 5 whitespace-separated tokens
    - No disqualifying patterns (email, URL, long digit run, brackets)
    - Every token matches the name-token pattern
    - Not a lone known section heading
    """
    stripped = line.strip()
    if not stripped:
        return False
    if _RE_DISQUALIFY_NAME.search(stripped):
        return False

    tokens = stripped.split()
    if not (2 <= len(tokens) <= 5):
        return False

    lower_tokens = [t.lower().rstrip(",:") for t in tokens]
    if lower_tokens[0] in _SECTION_HEADINGS:
        return False

    return all(_RE_NAME_TOKEN.match(t) for t in tokens)


def _extract_name(text: str) -> str:
    """
    Three-pass name heuristic over the first portion of the document.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    search_lines = lines[:30]

    # Pass 1: explicit "Name:" label
    for line in search_lines:
        m = re.match(r"(?i)^name\s*[:\-]\s*(.+)$", line)
        if m:
            candidate = m.group(1).strip()
            if _is_name_line(candidate):
                logger.debug("Name found via label: %r", candidate)
                return candidate

    # Pass 2: first Title-Case or ALL-CAPS name line in first 15 lines
    for line in lines[:15]:
        if _is_name_line(line):
            logger.debug("Name found via heuristic: %r", line)
            return line

    # Pass 3: fallback — first non-empty line (low confidence; log it)
    if lines:
        logger.debug("Name fallback to first line: %r", lines[0])
        # Only return it if it's short enough to plausibly be a name
        if len(lines[0].split()) <= 5:
            return lines[0]

    return ""


# ── Format detection ──────────────────────────────────────────────────────────

def _detect_format(path: Path) -> str | None:
    """Return 'pdf', 'docx', or None for unsupported."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".docx", ".docm"):
        return "docx"
    return None


# ── Error result helper ───────────────────────────────────────────────────────

def _error(message: str) -> ResumeData:
    logger.error(message)
    return ResumeData(
        name="", email="", phone="",
        raw_text="", success=False, error=message,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def parse_resume(file_path: str | Path) -> ResumeData:
    """
    Parse a resume file and return structured extracted data.

    Parameters
    ----------
    file_path : str | Path
        Path to a .pdf, .docx, or .docm resume file.

    Returns
    -------
    ResumeData
        {
            "name"     : str,        # candidate's name, "" if not detected
            "email"    : str,        # email address,   "" if not found
            "phone"    : str,        # phone number,    "" if not found
            "raw_text" : str,        # full cleaned text
            "success"  : bool,
            "error"    : str | None
        }

    The function never raises; all failures are captured in the return value.
    """
    # ── Resolve path ──────────────────────────────────────────────────────────
    path = Path(file_path).resolve()

    if not path.exists():
        return _error(f"File not found: {path}")
    if not path.is_file():
        return _error(f"Not a file: {path}")

    fmt = _detect_format(path)
    if fmt is None:
        return _error(
            f"Unsupported format '{path.suffix}'. "
            "Supported: .pdf, .docx, .docm"
        )

    logger.info("Parsing resume: %s (format=%s)", path.name, fmt)

    # ── Step 1: Extract raw text ──────────────────────────────────────────────
    if fmt == "pdf":
        extraction = extract_text_from_pdf(path)
        raw_text   = extraction["text"]
        ext_ok     = extraction["success"]
        ext_error  = extraction.get("error")
    else:
        extraction = extract_text_from_docx(path)
        raw_text   = extraction["text"]
        ext_ok     = extraction["success"]
        ext_error  = extraction.get("error")

    if not ext_ok:
        return _error(f"Text extraction failed: {ext_error}")

    # ── Step 2: Clean text ────────────────────────────────────────────────────
    clean_result = clean_text(raw_text, normalize_bullets=True)
    if not clean_result["success"]:
        return _error(f"Text cleaning failed: {clean_result['error']}")

    cleaned = clean_result["text"]
    logger.info(
        "Cleaning: %d → %d chars.",
        clean_result["original_chars"],
        clean_result["cleaned_chars"],
    )

    # ── Step 3: Extract entities ──────────────────────────────────────────────
    email = _extract_email(cleaned)
    phone = _extract_phone(cleaned)
    name  = _extract_name(cleaned)

    logger.info(
        "Entities — name=%r  email=%r  phone=%r",
        name or "(not found)",
        email or "(not found)",
        phone or "(not found)",
    )

    return ResumeData(
        name=name,
        email=email,
        phone=phone,
        raw_text=cleaned,
        success=True,
        error=None,
    )