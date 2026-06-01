"""
jd_parser.py
─────────────────────────────────────────────────────────────────────────────
Parses raw job description text into structured sections and extracts
skill-bearing content for downstream analysis.

This module sits at the top of the job_analysis pipeline:

    jd_parser.py          ← YOU ARE HERE
        ↓  ParsedJD
    skill_counter.py      ← consumes skill_text + sections
        ↓  SkillFrequency
    market_trends.py      ← consumes batches of SkillFrequency

What this module does
---------------------
1.  INPUT VALIDATION      — rejects empty, non-string, or too-short inputs.

2.  SECTION SEGMENTATION  — splits the JD into labelled sections:
                            requirements / responsibilities / nice_to_have /
                            about_role / about_company / benefits / other.
                            Uses regex header detection; gracefully falls back
                            to treating the full text as a single section.

3.  NOISE STRIPPING       — removes HTML tags, email addresses, phone numbers,
                            URLs, boilerplate legal text, and excessive
                            whitespace.  Preserves technical terms including
                            dots (Node.js), hyphens (scikit-learn), and
                            special chars (C++, C#).

4.  SKILL ZONE EXTRACTION — joins the highest-signal sections
                            (requirements + nice_to_have + responsibilities)
                            into a single `skill_text` string that
                            skill_counter.py can scan without noise from
                            "About Company" / "Benefits" blocks.

5.  METADATA EXTRACTION   — title, seniority level, employment type, remote
                            flag — derived from the full text via regex.

6.  SENTENCE TOKENISATION — via spaCy (en_core_web_sm) for sections where
                            sentence boundaries matter.  Falls back to a
                            simple period/newline split if spaCy is unavailable.

Public API
----------
    ParsedJD            — TypedDict: full structured output.
    ParseResult         — TypedDict: envelope with success/error.

    parse_jd(text: str) -> ParseResult

    ParseResult
    ├── success    : bool
    ├── parsed     : ParsedJD | None
    └── error      : str | None

    ParsedJD
    ├── raw_text         : str     original input (stripped)
    ├── clean_text       : str     noise-free full text
    ├── skill_text       : str     high-signal zone for skill extraction
    ├── sections         : dict[str, str]   keyed by section label
    ├── sentences        : list[str]        from skill_text
    ├── title            : str | None
    ├── seniority        : str | None       "junior"|"mid"|"senior"|"lead"|"principal"
    ├── employment_type  : str | None       "full_time"|"part_time"|"contract"|"internship"
    ├── is_remote        : bool
    ├── word_count       : int     (clean_text)
    └── char_count       : int     (clean_text)
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ── spaCy (optional — graceful fallback) ──────────────────────────────────────
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm", disable=["ner", "tagger", "parser"])
    _nlp.enable_pipe("senter")   # lightweight sentence segmenter
    _SPACY_AVAILABLE = True
    logger.debug("spaCy en_core_web_sm loaded.")
except Exception:
    _SPACY_AVAILABLE = False
    _nlp = None
    logger.warning("spaCy not available — using fallback sentence tokeniser.")


# ── Constants ─────────────────────────────────────────────────────────────────

_MIN_CHARS = 30          # reject JDs shorter than this
_MAX_CHARS = 50_000      # truncate absurdly long inputs

# Section labels (ordered: later labels are lower priority in skill_text)
_SKILL_SECTIONS  = {"requirements", "nice_to_have", "responsibilities"}
_ALL_SECTIONS    = _SKILL_SECTIONS | {"about_role", "about_company", "benefits", "other"}

# Section header patterns  →  label
_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(
        r"(?i)^\s*(?:key\s+)?(?:requirements?|qualifications?|"
        r"what\s+(?:we|you)\s+(?:need|require|look\s+for)|"
        r"must[\s-]have|technical\s+requirements?|"
        r"skills?\s+(?:required|needed)|required\s+skills?)\s*[:\-]?\s*$",
        re.MULTILINE), "requirements"),

    (re.compile(
        r"(?i)^\s*(?:nice[\s-]to[\s-]have|preferred\s+qualifications?|"
        r"bonus\s+(?:points?|skills?)|good[\s-]to[\s-]have|"
        r"desirable\s+skills?|optional\s+skills?)\s*[:\-]?\s*$",
        re.MULTILINE), "nice_to_have"),

    (re.compile(
        r"(?i)^\s*(?:responsibilities?|what\s+you(?:'ll)?\s+do|"
        r"role\s+(?:overview|description|summary)|key\s+responsibilities?|"
        r"your\s+(?:role|responsibilities?)|duties|job\s+duties)\s*[:\-]?\s*$",
        re.MULTILINE), "responsibilities"),

    (re.compile(
        r"(?i)^\s*(?:about\s+(?:the\s+)?role|position\s+(?:overview|summary)|"
        r"job\s+(?:summary|overview|description))\s*[:\-]?\s*$",
        re.MULTILINE), "about_role"),

    (re.compile(
        r"(?i)^\s*(?:about\s+(?:us|the\s+company|our\s+company)|"
        r"who\s+we\s+are|company\s+(?:overview|description))\s*[:\-]?\s*$",
        re.MULTILINE), "about_company"),

    (re.compile(
        r"(?i)^\s*(?:benefits?|perks?|what\s+we\s+offer|"
        r"compensation|salary\s+and\s+benefits?|we\s+offer)\s*[:\-]?\s*$",
        re.MULTILINE), "benefits"),
]

# Noise patterns to strip (order matters)
_HTML_TAG_RE    = re.compile(r"<[^>]+>")
_URL_RE         = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE       = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE       = re.compile(r"\+?[\d\s\-().]{7,15}\d")
_LEGAL_RE       = re.compile(
    r"(?i)(?:equal\s+opportunity\s+employer|eeo|"
    r"we\s+are\s+committed\s+to\s+diversity|"
    r"all\s+qualified\s+applicants|"
    r"without\s+regard\s+to\s+race|affirmative\s+action)[^.]*\.",
    re.DOTALL,
)
_BULLET_RE      = re.compile(r"^[\s]*[•·▪▸◦\-\*➤➢→]\s*", re.MULTILINE)
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_CONTROL_RE     = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\r]")

# Metadata extraction patterns
_SENIORITY_RE = re.compile(
    r"(?i)\b(principal|staff|lead|senior|sr\.?|junior|jr\.?|mid[\s-]?level|associate|entry[\s-]?level|intern)\b"
)
_SENIORITY_MAP = {
    "principal": "principal", "staff": "lead",
    "lead": "lead",
    "senior": "senior",  "sr": "senior",
    "junior": "junior",  "jr": "junior",
    "mid": "mid",        "mid-level": "mid", "midlevel": "mid",
    "associate": "mid",
    "entry": "junior",   "entry-level": "junior", "entrylevel": "junior",
    "intern": "intern",
}
_EMPLOYMENT_RE = re.compile(
    r"(?i)\b(full[\s-]?time|part[\s-]?time|contract(?:or)?|freelance|internship|temporary|temp)\b"
)
_EMPLOYMENT_MAP = {
    "full-time": "full_time",   "fulltime": "full_time",   "full time": "full_time",
    "part-time": "part_time",   "parttime": "part_time",   "part time": "part_time",
    "contract": "contract",     "contractor": "contract",  "freelance": "contract",
    "internship": "internship", "temporary": "contract",   "temp": "contract",
}
_REMOTE_RE = re.compile(
    r"(?i)\b(remote|work[\s-]from[\s-]home|wfh|distributed\s+team|fully\s+remote|hybrid)\b"
)
_TITLE_LINE_RE = re.compile(
    r"(?i)^(?:job\s+)?(?:title|position|role)\s*[:\-]\s*(.+)$",
    re.MULTILINE,
)


# ── Return types ──────────────────────────────────────────────────────────────

class ParsedJD(TypedDict):
    raw_text:        str
    clean_text:      str
    skill_text:      str
    sections:        dict[str, str]
    sentences:       list[str]
    title:           str | None
    seniority:       str | None
    employment_type: str | None
    is_remote:       bool
    word_count:      int
    char_count:      int


class ParseResult(TypedDict):
    success: bool
    parsed:  ParsedJD | None
    error:   str | None


# ── Noise cleaning ────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """
    Remove HTML, URLs, emails, phone numbers, legal boilerplate,
    bullet symbols, control characters, and excess whitespace.
    Preserve technical terms (Node.js, C++, scikit-learn, AWS).
    """
    text = _CONTROL_RE.sub("", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _LEGAL_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    text = _PHONE_RE.sub(" ", text)
    text = _BULLET_RE.sub("", text)          # strip bullet symbols, keep text
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()


# ── Section segmentation ──────────────────────────────────────────────────────

def _segment_sections(clean_text: str) -> dict[str, str]:
    """
    Split clean_text into labelled sections using header pattern matching.

    Strategy:
    1. Find all header matches with their positions.
    2. Sort by position.
    3. Slice text between consecutive headers.
    4. Anything before the first header → "about_role" (or "other").
    5. If no headers found → entire text under "requirements" as best guess.
    """
    lines = clean_text.splitlines()
    # Test each line against section patterns
    boundaries: list[tuple[int, str]] = []   # (line_index, label)

    for idx, line in enumerate(lines):
        for pattern, label in _SECTION_PATTERNS:
            if pattern.match(line):
                boundaries.append((idx, label))
                break

    sections: dict[str, str] = {}

    if not boundaries:
        # No recognisable headers — treat whole text as requirements
        logger.debug("No section headers found; treating full text as requirements.")
        sections["requirements"] = clean_text
        return sections

    # Content before the first header
    if boundaries[0][0] > 0:
        preamble = "\n".join(lines[:boundaries[0][0]]).strip()
        if preamble:
            sections["about_role"] = preamble

    # Content between consecutive headers
    for i, (start_line, label) in enumerate(boundaries):
        end_line = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
        content  = "\n".join(lines[start_line + 1: end_line]).strip()
        if content:
            # Merge duplicate labels (some JDs repeat headers)
            if label in sections:
                sections[label] = sections[label] + "\n" + content
            else:
                sections[label] = content

    return sections


# ── Skill zone builder ────────────────────────────────────────────────────────

def _build_skill_text(sections: dict[str, str]) -> str:
    """
    Concatenate high-signal sections in priority order.
    Falls back to full clean_text if no skill sections found.
    """
    priority = ["requirements", "nice_to_have", "responsibilities"]
    parts    = [sections[k] for k in priority if k in sections and sections[k]]

    if not parts:
        # Fall back to everything except company/benefits noise
        parts = [v for k, v in sections.items()
                 if k not in ("about_company", "benefits")]

    return "\n\n".join(parts).strip()


# ── Sentence tokeniser ────────────────────────────────────────────────────────

def _tokenise_sentences(text: str) -> list[str]:
    """
    Split text into sentences using spaCy if available, else simple split.
    Returns non-empty stripped sentences only.
    """
    if _SPACY_AVAILABLE and _nlp is not None:
        doc   = _nlp(text[:_MAX_CHARS])
        sents = [s.text.strip() for s in doc.sents if s.text.strip()]
    else:
        # Fallback: split on period + newline or double newline
        raw   = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
        sents = [s.strip() for s in raw if s.strip()]

    return [s for s in sents if len(s) > 5]


# ── Metadata extractors ───────────────────────────────────────────────────────

def _extract_title(text: str) -> str | None:
    m = _TITLE_LINE_RE.search(text)
    if m:
        return m.group(1).strip() or None
    # Try: first non-empty line that's short enough to be a title
    for line in text.splitlines():
        line = line.strip()
        if 3 < len(line) <= 80 and not line.endswith(":"):
            return line
    return None


def _extract_seniority(text: str) -> str | None:
    m = _SENIORITY_RE.search(text)
    if not m:
        return None
    raw = m.group(1).lower().replace(" ", "-").replace(".", "")
    return _SENIORITY_MAP.get(raw, None)


def _extract_employment_type(text: str) -> str | None:
    m = _EMPLOYMENT_RE.search(text)
    if not m:
        return None
    raw = m.group(1).lower().replace(" ", "-").replace("-", "")
    raw_with_dash = m.group(1).lower().replace(" ", "-")
    return _EMPLOYMENT_MAP.get(raw_with_dash) or _EMPLOYMENT_MAP.get(raw)


def _is_remote(text: str) -> bool:
    return bool(_REMOTE_RE.search(text))


# ── Public API ────────────────────────────────────────────────────────────────

def parse_jd(text: str) -> ParseResult:
    """
    Parse a raw job description string into structured output.

    Parameters
    ----------
    text : str
        Raw job description — may contain HTML, bullet symbols, URLs,
        boilerplate text, or mixed formatting.

    Returns
    -------
    ParseResult
        {
          "success": True,
          "parsed": {
            "raw_text":        "...",
            "clean_text":      "...",
            "skill_text":      "...",   ← feed this to skill_counter.py
            "sections":        {"requirements": "...", ...},
            "sentences":       ["...", ...],
            "title":           "Senior Data Engineer",
            "seniority":       "senior",
            "employment_type": "full_time",
            "is_remote":       True,
            "word_count":      312,
            "char_count":      1847,
          },
          "error": None
        }

    The key output for skill_counter.py is `parsed["skill_text"]` —
    the cleaned, high-signal zone containing requirements and responsibilities.

    Notes
    -----
    - HTML tags, URLs, emails, phone numbers are stripped.
    - spaCy sentence tokenisation is used when available.
    - Input is truncated at 50,000 characters before processing.
    """
    # ── Validation ────────────────────────────────────────────────────────────
    if not isinstance(text, str):
        msg = f"parse_jd expects str, got {type(text).__name__}"
        logger.error(msg)
        return ParseResult(success=False, parsed=None, error=msg)

    raw = text.strip()

    if not raw:
        return ParseResult(success=False, parsed=None, error="Input text is empty.")

    if len(raw) < _MIN_CHARS:
        return ParseResult(
            success=False, parsed=None,
            error=f"Input too short ({len(raw)} chars; minimum {_MIN_CHARS}).",
        )

    if len(raw) > _MAX_CHARS:
        logger.warning("Input truncated from %d to %d chars.", len(raw), _MAX_CHARS)
        raw = raw[:_MAX_CHARS]

    logger.info("parse_jd: input length=%d chars", len(raw))

    try:
        # ── Clean ─────────────────────────────────────────────────────────────
        clean = _clean(raw)

        # ── Segment ───────────────────────────────────────────────────────────
        sections = _segment_sections(clean)
        logger.debug("Sections found: %s", list(sections.keys()))

        # ── Skill zone ────────────────────────────────────────────────────────
        skill_text = _build_skill_text(sections)

        # ── Sentences ─────────────────────────────────────────────────────────
        sentences = _tokenise_sentences(skill_text)

        # ── Metadata ──────────────────────────────────────────────────────────
        title           = _extract_title(raw)
        seniority       = _extract_seniority(raw)
        employment_type = _extract_employment_type(raw)
        remote          = _is_remote(raw)

        parsed = ParsedJD(
            raw_text        = raw,
            clean_text      = clean,
            skill_text      = skill_text,
            sections        = sections,
            sentences       = sentences,
            title           = title,
            seniority       = seniority,
            employment_type = employment_type,
            is_remote       = remote,
            word_count      = len(clean.split()),
            char_count      = len(clean),
        )

        logger.info(
            "parse_jd OK: sections=%s  words=%d  sentences=%d  remote=%s  seniority=%s",
            list(sections.keys()), parsed["word_count"],
            len(sentences), remote, seniority,
        )

        return ParseResult(success=True, parsed=parsed, error=None)

    except Exception as exc:   # noqa: BLE001
        msg = f"parse_jd internal error: {exc}"
        logger.error(msg, exc_info=True)
        return ParseResult(success=False, parsed=None, error=msg)