"""
skill_extractor.py
─────────────────────────────────────────────────────────────────────────────
Detects skills from cleaned resume text using a multi-pass matching pipeline.

Detection Strategy
------------------
Pass 1 — EXACT / ALIAS MATCH (highest confidence)
    Tokenise text into n-grams (1–4 words). Look each up in ALIAS_INDEX.
    Uses word-boundary anchored matching to avoid false positives
    (e.g. "R" inside "React" should not match the R skill).

Pass 2 — CONTEXTUAL BOOST for short / ambiguous tokens
    Tokens with weight < 0.85 (single letters, 2-char abbreviations) are
    only accepted when at least one other confirmed skill from the same
    or a related category appears in a ±50-word context window.
    Example: "R" is accepted when "ggplot", "tidyverse", or "statistics"
    are nearby; rejected when isolated in a generic sentence.

Pass 3 — SECTION-AWARE WEIGHTING
    Skills found inside a recognised skill section header
    (Skills, Technical Skills, Technologies, Tools, Competencies …)
    receive a +0.05 confidence boost (capped at 1.0).
    Skills found only in the body text receive no penalty; their base
    weight is used as-is.

Confidence formula
------------------
    base_confidence  = entry["weight"]          # from skill_dictionary
    section_boost    = +0.05 if in skill block
    context_penalty  = –0.10 if ambiguous token not contextually confirmed
    raw_score        = base_confidence + section_boost – context_penalty
    final_confidence = round(min(1.0, max(0.0, raw_score)), 2)

Public API
----------
    SkillMatch          — TypedDict for a single detected skill.
    ExtractResult       — TypedDict returned by extract_skills().
    extract_skills(text, min_confidence) -> ExtractResult

    ExtractResult
    ├── skills    : list[SkillMatch]   # sorted by confidence desc
    ├── success   : bool
    └── error     : str | None
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

from services.skill_engine.skill_dictionary import (
    ALIAS_INDEX,
    get_entry,
    SkillEntry,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Return types ──────────────────────────────────────────────────────────────

class SkillMatch(TypedDict):
    skill: str          # canonical name
    confidence: float   # [0.0 – 1.0]
    category: str
    matched_text: str   # surface form that triggered the match


class ExtractResult(TypedDict):
    skills: list[SkillMatch]
    success: bool
    error: str | None


# ── Constants ─────────────────────────────────────────────────────────────────

# N-gram window: try up to 4-word phrases  ("Apache Spark Streaming Jobs" = 3)
_MAX_NGRAM = 4

# Ambiguous token threshold — entries below this weight get context validation
_AMBIGUITY_THRESHOLD = 0.85

# Context window (in words) around an ambiguous token
_CONTEXT_WINDOW = 50

# Boost applied when skill is found inside a skill-section block
_SECTION_BOOST = 0.05

# Penalty applied when an ambiguous token has no supporting context
_CONTEXT_PENALTY = 0.10

# Regex patterns that signal a "skills section" header
_SKILL_SECTION_RE = re.compile(
    r"""
    (?i)                        # case-insensitive
    ^\s*                        # start of line
    (?:
        technical\s+skills?     |
        skills?\s+(?:summary|profile|set)?  |
        core\s+(?:skills?|competencies?)    |
        competencies            |
        technologies            |
        tools?\s+(?:and\s+technologies?)?   |
        expertise               |
        proficiencies           |
        key\s+skills?           |
        programming\s+languages?|
        frameworks?\s+(?:and\s+tools?)?     |
        tech\s+stack
    )
    \s*[:\-]?\s*$               # optional colon/dash at end
    """,
    re.VERBOSE,
)

# Word tokeniser — keeps letters, digits, dots, plus, hash, slash, hyphen
_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]"             # must start with alnum
    r"[A-Za-z0-9#\-]*"         # middle: alnum, hash, hyphen
    r"(?:"
        r"[.+][A-Za-z0-9]"     # dot or plus followed by alnum (Node.js, C++)
        r"[A-Za-z0-9#\-]*"     # rest of sub-token
    r")*"
    r"\+*"                      # optional trailing ++ (C++)
)

# Boundary check: a match is only valid if NOT preceded/followed by a word char
# This prevents "C" matching inside "React", "Go" inside "MongoDB", etc.
_WORD_CHAR_RE = re.compile(r"\w")

# Related-category pairs for contextual validation
_RELATED_CATEGORIES: dict[str, set[str]] = {
    "programming_language": {"data_science", "machine_learning", "web_frontend",
                              "web_backend", "devops"},
    "data_science":         {"machine_learning", "nlp", "programming_language"},
    "machine_learning":     {"data_science", "nlp", "computer_vision"},
    "nlp":                  {"machine_learning", "data_science"},
    "computer_vision":      {"machine_learning", "data_science"},
    "web_frontend":         {"web_backend", "programming_language"},
    "web_backend":          {"web_frontend", "programming_language", "database"},
    "database":             {"web_backend", "data_engineering"},
    "devops":               {"cloud", "programming_language"},
    "cloud":                {"devops", "data_engineering"},
    "data_engineering":     {"data_science", "database", "cloud"},
    "mobile":               {"programming_language"},
    "testing":              {"programming_language", "web_backend"},
    "soft_skill":           set(),
    "other":                set(),
}


# ── Text preprocessing ────────────────────────────────────────────────────────

def _split_lines(text: str) -> list[str]:
    return text.splitlines()


def _tokenize(text: str) -> list[str]:
    """Extract word tokens preserving case."""
    return _TOKEN_RE.findall(text)


def _is_boundary_safe(text: str, start: int, end: int) -> bool:
    """
    Return True when the match at [start:end] is not embedded inside a
    larger word — prevents "C" matching inside "React" etc.
    """
    if start > 0 and _WORD_CHAR_RE.match(text[start - 1]):
        return False
    if end < len(text) and _WORD_CHAR_RE.match(text[end]):
        return False
    return True


# ── Section detection ─────────────────────────────────────────────────────────

def _build_skill_block_set(lines: list[str]) -> set[int]:
    """
    Return the set of line indices that are inside a skill section block.

    A skill block starts at a recognised section header and ends when
    another ALL-CAPS or Title-Case section header appears (or EOF).
    """
    in_skill_block = False
    skill_lines: set[int] = set()

    # Detect generic section-end: line that looks like another section header
    _other_section_re = re.compile(
        r"""
        (?i)^\s*
        (?:
            education|experience|work\s+history|employment|
            projects?|certifications?|awards?|achievements?|
            publications?|summary|objective|profile|
            interests?|hobbies|references?|contact
        )
        \s*[:\-]?\s*$
        """,
        re.VERBOSE,
    )

    for i, line in enumerate(lines):
        if _SKILL_SECTION_RE.match(line):
            in_skill_block = True
            continue
        if in_skill_block and _other_section_re.match(line):
            in_skill_block = False
        if in_skill_block:
            skill_lines.add(i)

    return skill_lines


# ── N-gram matching ───────────────────────────────────────────────────────────

def _ngrams_from_tokens(tokens: list[str], n: int) -> list[str]:
    """Generate space-joined n-grams from a token list."""
    return [" ".join(tokens[i: i + n]) for i in range(len(tokens) - n + 1)]


def _find_matches_in_text(
    text: str,
    in_skill_block: bool,
) -> list[tuple[str, SkillEntry, str, bool]]:
    """
    Scan *text* for skill aliases using n-gram sliding window.

    Returns list of (canonical, entry, matched_surface, in_skill_block).
    """
    tokens = _tokenize(text)
    found: list[tuple[str, SkillEntry, str, bool]] = []
    matched_positions: set[int] = set()   # token indices already consumed

    # Try longest n-grams first so "Machine Learning" beats "Machine"
    for n in range(_MAX_NGRAM, 0, -1):
        for i, ngram in enumerate(_ngrams_from_tokens(tokens, n)):
            # Skip if any token in this window already matched
            span = set(range(i, i + n))
            if span & matched_positions:
                continue

            key = ngram.lower()
            canonical = ALIAS_INDEX.get(key)
            if canonical is None:
                continue

            entry = get_entry(canonical)
            if entry is None:
                continue

            # Boundary check in the original text
            # (rebuild match position via case-insensitive search)
            pattern = re.compile(
                r"(?<!\w)" + re.escape(ngram) + r"(?!\w)",
                re.IGNORECASE,
            )
            if not pattern.search(text):
                continue

            matched_positions |= span
            found.append((canonical, entry, ngram, in_skill_block))

    return found


# ── Context validation for ambiguous tokens ───────────────────────────────────

def _build_word_list(text: str) -> list[str]:
    return text.lower().split()


def _context_confirms(
    ambiguous_canonical: str,
    ambiguous_entry: SkillEntry,
    full_word_list: list[str],
    confirmed_canonicals: set[str],
) -> bool:
    """
    Return True when an ambiguous skill has supporting evidence:
    - Another confirmed skill from the same or related category is present
      in the global confirmed set, OR
    - The alias itself appears near (within ±50 words of) another
      data-domain keyword.
    """
    related_cats = (
        {ambiguous_entry["category"]}
        | _RELATED_CATEGORIES.get(ambiguous_entry["category"], set())
    )

    for confirmed in confirmed_canonicals:
        c_entry = get_entry(confirmed)
        if c_entry and c_entry["category"] in related_cats:
            return True

    # Lightweight proximity check using word list
    domain_keywords = set(ALIAS_INDEX.keys()) - {
        ambiguous_canonical.lower()
    }
    for i, word in enumerate(full_word_list):
        if word == ambiguous_canonical.lower() or word in {
            a.lower() for a in get_entry(ambiguous_canonical)["aliases"]
        }:
            window = full_word_list[
                max(0, i - _CONTEXT_WINDOW): i + _CONTEXT_WINDOW
            ]
            for w in window:
                if w in domain_keywords:
                    nbr = get_entry(ALIAS_INDEX[w])
                    if nbr and nbr["category"] in related_cats:
                        return True

    return False


# ── Confidence calculation ────────────────────────────────────────────────────

def _calculate_confidence(
    entry: SkillEntry,
    in_skill_block: bool,
    context_confirmed: bool,
) -> float:
    score = entry["weight"]
    if in_skill_block:
        score += _SECTION_BOOST
    if entry["weight"] < _AMBIGUITY_THRESHOLD and not context_confirmed:
        score -= _CONTEXT_PENALTY
    return round(min(1.0, max(0.0, score)), 2)


# ── Public API ────────────────────────────────────────────────────────────────

def extract_skills(
    text: str,
    min_confidence: float = 0.50,
) -> ExtractResult:
    """
    Extract skills from cleaned resume text.

    Parameters
    ----------
    text : str
        Cleaned resume text (output of text_cleaner.clean_text).
    min_confidence : float, default 0.50
        Skills with final confidence below this threshold are excluded.

    Returns
    -------
    ExtractResult
        {
          "skills": [
            {"skill": "Python", "confidence": 0.95,
             "category": "programming_language", "matched_text": "Python"},
            ...
          ],
          "success": True,
          "error":   None
        }
        Skills are sorted by confidence (descending), then alphabetically.
        Duplicate canonicals are collapsed; the highest-confidence instance
        for each canonical is kept.

    Notes
    -----
    - Input must be a non-empty string; returns success=False otherwise.
    - Very short ambiguous tokens (R, Go, C) are only included when
      contextually supported by nearby domain-relevant skills.
    """
    if not isinstance(text, str):
        msg = f"extract_skills expects str, got {type(text).__name__}"
        logger.error(msg)
        return ExtractResult(skills=[], success=False, error=msg)

    if not text.strip():
        return ExtractResult(skills=[], success=True, error=None)

    lines = _split_lines(text)
    skill_block_lines = _build_skill_block_set(lines)
    full_word_list = _build_word_list(text)

    # ── Pass 1: collect all raw matches ──────────────────────────────────────
    raw_matches: list[tuple[str, SkillEntry, str, bool]] = []

    for line_idx, line in enumerate(lines):
        in_block = line_idx in skill_block_lines
        matches = _find_matches_in_text(line, in_block)
        raw_matches.extend(matches)

    if not raw_matches:
        logger.debug("No skill matches found in text.")
        return ExtractResult(skills=[], success=True, error=None)

    # ── Pass 2: contextual validation for ambiguous tokens ────────────────────
    # First, collect all unambiguous canonicals as the confirmed set.
    confirmed_canonicals: set[str] = {
        canonical
        for canonical, entry, _, _ in raw_matches
        if entry["weight"] >= _AMBIGUITY_THRESHOLD
    }

    # ── Pass 3: compute confidence & build final list ─────────────────────────
    # Use a dict to deduplicate: keep highest confidence per canonical.
    best: dict[str, SkillMatch] = {}

    for canonical, entry, matched_text, in_block in raw_matches:
        is_ambiguous = entry["weight"] < _AMBIGUITY_THRESHOLD
        context_ok = (
            _context_confirms(
                canonical, entry, full_word_list, confirmed_canonicals
            )
            if is_ambiguous
            else True
        )

        confidence = _calculate_confidence(entry, in_block, context_ok)

        if confidence < min_confidence:
            logger.debug(
                "Skipping %r (confidence %.2f < threshold %.2f)",
                canonical, confidence, min_confidence,
            )
            continue

        if canonical not in best or confidence > best[canonical]["confidence"]:
            best[canonical] = SkillMatch(
                skill=canonical,
                confidence=confidence,
                category=entry["category"],
                matched_text=matched_text,
            )

    skills = sorted(
        best.values(),
        key=lambda s: (-s["confidence"], s["skill"]),
    )

    logger.info(
        "extract_skills: %d unique skills detected (min_confidence=%.2f).",
        len(skills), min_confidence,
    )

    return ExtractResult(skills=skills, success=True, error=None)