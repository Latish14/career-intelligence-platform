"""
skill_normalizer.py
─────────────────────────────────────────────────────────────────────────────
Normalises raw skill surface forms into their canonical representations.

Responsibility
--------------
This module sits between raw text detection and validation.
Given a raw skill string (extracted or user-supplied), it:

1.  ALIAS RESOLUTION      — looks up the exact alias in ALIAS_INDEX.
                            "JS" → "JavaScript", "sklearn" → "Scikit-learn"

2.  CASE FOLDING FALLBACK — if exact lookup fails, tries lowercased + stripped
                            version before giving up.

3.  FUZZY MATCH           — if alias lookup misses, runs a lightweight
                            character-trigram similarity against all known
                            aliases (no external deps). Accepts matches above
                            a configurable threshold (default 0.72).
                            Catches: "Pyhon" → "Python", "Tenserflow" → "TensorFlow"

4.  COMPOUND SPLIT        — "Python/FastAPI", "React & Redux", "JS/TS"
                            are split on  / | & + ,  then each part normalised
                            independently. Results are flattened and deduped.

5.  CONFIDENCE ADJUSTMENT — normalisation method affects confidence:
                            exact     →  ×1.00  (no change)
                            fold/trim →  ×1.00  (no change; same alias)
                            fuzzy     →  ×0.85  (slight penalty for uncertainty)
                            split     →  inherited from each part's method

Public API
----------
    NormResult           — TypedDict for a single normalised skill.
    NormalizeResult      — TypedDict returned by normalize_skills().

    normalize_skill(raw, min_fuzzy_score) -> NormResult | None
        Normalise one raw string.  Returns None if no match found.

    normalize_skills(raw_list, min_fuzzy_score) -> NormalizeResult
        Normalise a list, handling compound splits, dedup, confidence merge.

    NormalizeResult
    ├── skills   : list[NormResult]   # unique canonicals, sorted by confidence
    ├── success  : bool
    └── error    : str | None
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

from services.skill_engine.skill_dictionary import ALIAS_INDEX, SKILL_CATALOG, get_entry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

# Confidence multiplier for fuzzy-matched results
_FUZZY_MULTIPLIER = 0.85

# Default minimum trigram similarity to accept a fuzzy match
_DEFAULT_FUZZY_THRESHOLD = 0.65

# Separators that signal a compound skill string  ("Python/JS", "React & Vue")
_COMPOUND_SEP_RE = re.compile(r"\s*[/|&+,]\s*")

# Chars to strip from the edges of a raw token before lookup
_STRIP_CHARS = " \t\n\r.,;:!?\"'()[]{}—–-"


# ── Return types ──────────────────────────────────────────────────────────────

class NormResult(TypedDict):
    canonical: str          # authoritative skill name
    original: str           # raw input that produced this result
    method: str             # "exact" | "fold" | "fuzzy" | "split"
    confidence_multiplier: float  # apply to base weight from dictionary
    category: str


class NormalizeResult(TypedDict):
    skills: list[NormResult]
    success: bool
    error: str | None


# ── Trigram similarity ────────────────────────────────────────────────────────

def _trigrams(s: str) -> set[str]:
    """Character-level trigrams with padding."""
    padded = f"  {s}  "
    return {padded[i: i + 3] for i in range(len(padded) - 2)}


def _trigram_similarity(a: str, b: str) -> float:
    """
    Dice coefficient over character trigrams.
    Returns a float in [0.0, 1.0].  1.0 = identical.
    """
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))


# Pre-compute lowercased alias list once at import time for fuzzy lookup.
# Each entry: (alias_lower, canonical)
_ALIAS_PAIRS: list[tuple[str, str]] = [
    (alias, canonical)
    for alias, canonical in ALIAS_INDEX.items()
]


def _fuzzy_lookup(raw_lower: str, threshold: float) -> tuple[str, float] | None:
    """
    Find the closest alias using trigram similarity.

    Returns (canonical, similarity_score) if score >= threshold, else None.
    Only considers aliases of length >= 3 to avoid noise on very short strings.
    """
    if len(raw_lower) < 3:
        return None

    best_score = 0.0
    best_canonical: str | None = None

    for alias, canonical in _ALIAS_PAIRS:
        if abs(len(alias) - len(raw_lower)) > max(len(raw_lower) * 0.5, 4):
            continue  # length filter — skip obviously different lengths
        score = _trigram_similarity(raw_lower, alias)
        if score > best_score:
            best_score = score
            best_canonical = canonical

    if best_score >= threshold and best_canonical is not None:
        return best_canonical, best_score
    return None


# ── Core normaliser ───────────────────────────────────────────────────────────

def normalize_skill(
    raw: str,
    min_fuzzy_score: float = _DEFAULT_FUZZY_THRESHOLD,
) -> NormResult | None:
    """
    Normalise a single raw skill string to its canonical form.

    Parameters
    ----------
    raw : str
        A raw skill token, e.g. "JS", "sklearn", "Pyhon", "scikit learn"
    min_fuzzy_score : float
        Minimum trigram similarity (0–1) to accept a fuzzy match.

    Returns
    -------
    NormResult | None
        None if no match found (exact, fold, or fuzzy all failed).

    Examples
    --------
    >>> normalize_skill("JS")["canonical"]
    'JavaScript'
    >>> normalize_skill("sklearn")["canonical"]
    'Scikit-learn'
    >>> normalize_skill("Tenserflow")["canonical"]
    'TensorFlow'
    >>> normalize_skill("completelymadeup") is None
    True
    """
    if not isinstance(raw, str) or not raw.strip():
        return None

    clean = raw.strip(_STRIP_CHARS)
    if not clean:
        return None

    # ── Step 1: exact alias lookup ────────────────────────────────────────────
    canonical = ALIAS_INDEX.get(clean)
    if canonical:
        entry = get_entry(canonical)
        return NormResult(
            canonical=canonical,
            original=raw,
            method="exact",
            confidence_multiplier=1.0,
            category=entry["category"] if entry else "other",
        )

    # ── Step 2: case-fold + strip lookup ─────────────────────────────────────
    lower = clean.lower()
    canonical = ALIAS_INDEX.get(lower)
    if canonical:
        entry = get_entry(canonical)
        return NormResult(
            canonical=canonical,
            original=raw,
            method="fold",
            confidence_multiplier=1.0,
            category=entry["category"] if entry else "other",
        )

    # ── Step 3: whitespace-collapsed lookup ───────────────────────────────────
    # Handles "scikit learn" vs "scikit-learn", "node js" vs "node.js"
    collapsed = re.sub(r"[\s\-_.]+", " ", lower).strip()
    canonical = ALIAS_INDEX.get(collapsed)
    if canonical:
        entry = get_entry(canonical)
        return NormResult(
            canonical=canonical,
            original=raw,
            method="fold",
            confidence_multiplier=1.0,
            category=entry["category"] if entry else "other",
        )

    # Also try with common separator replacements
    for sep_replacement in ("-", ".", ""):
        variant = re.sub(r"[\s\-_.]+", sep_replacement, lower)
        canonical = ALIAS_INDEX.get(variant)
        if canonical:
            entry = get_entry(canonical)
            return NormResult(
                canonical=canonical,
                original=raw,
                method="fold",
                confidence_multiplier=1.0,
                category=entry["category"] if entry else "other",
            )

    # ── Step 4: fuzzy trigram match ───────────────────────────────────────────
    fuzzy = _fuzzy_lookup(lower, min_fuzzy_score)
    if fuzzy:
        canonical, score = fuzzy
        entry = get_entry(canonical)
        logger.debug(
            "Fuzzy match: %r → %r (score=%.2f)", raw, canonical, score
        )
        return NormResult(
            canonical=canonical,
            original=raw,
            method="fuzzy",
            confidence_multiplier=_FUZZY_MULTIPLIER,
            category=entry["category"] if entry else "other",
        )

    logger.debug("normalize_skill: no match for %r", raw)
    return None


# ── Compound split handler ────────────────────────────────────────────────────

def _split_compound(raw: str) -> list[str]:
    """
    Split a compound skill string on / | & + , separators.
    Returns a list of stripped parts (≥ 1 element; original if no separator).
    """
    parts = _COMPOUND_SEP_RE.split(raw.strip())
    return [p.strip() for p in parts if p.strip()]


# ── Public batch normaliser ───────────────────────────────────────────────────

def normalize_skills(
    raw_list: list[str],
    min_fuzzy_score: float = _DEFAULT_FUZZY_THRESHOLD,
) -> NormalizeResult:
    """
    Normalise a list of raw skill strings.

    Handles:
    - Exact and case-fold resolution
    - Whitespace / separator variant resolution ("scikit learn" → "Scikit-learn")
    - Fuzzy typo correction ("Pyhon" → "Python")
    - Compound splitting ("Python/FastAPI" → ["Python", "FastAPI"])
    - Deduplication (highest confidence_multiplier kept per canonical)

    Parameters
    ----------
    raw_list : list[str]
        Raw skill strings. May be aliases, abbreviations, typos, or compounds.
    min_fuzzy_score : float
        Trigram similarity floor for fuzzy matching (default 0.72).

    Returns
    -------
    NormalizeResult
        {
          "skills": [
            {
              "canonical": "Python",
              "original":  "Py",
              "method":    "exact",
              "confidence_multiplier": 1.0,
              "category":  "programming_language"
            },
            ...
          ],
          "success": True,
          "error":   None
        }
        Skills sorted by canonical name alphabetically.

    Notes
    -----
    - Unrecognised strings are silently skipped (logged at DEBUG).
    - Duplicates resolved by highest confidence_multiplier, then "exact" > "fold" > "fuzzy".
    """
    if not isinstance(raw_list, list):
        msg = f"normalize_skills expects list, got {type(raw_list).__name__}"
        logger.error(msg)
        return NormalizeResult(skills=[], success=False, error=msg)

    # Method priority for dedup resolution
    _METHOD_RANK = {"exact": 3, "fold": 2, "split": 1, "fuzzy": 0}

    best: dict[str, NormResult] = {}

    for raw in raw_list:
        if not isinstance(raw, str):
            logger.debug("Skipping non-string item: %r", raw)
            continue

        # Detect and split compound skills first
        parts = _split_compound(raw)
        is_compound = len(parts) > 1

        for part in parts:
            result = normalize_skill(part, min_fuzzy_score)
            if result is None:
                continue

            if is_compound:
                result = NormResult(
                    canonical=result["canonical"],
                    original=raw,          # keep original compound for traceability
                    method="split",
                    confidence_multiplier=result["confidence_multiplier"],
                    category=result["category"],
                )

            canonical = result["canonical"]

            # Dedup: keep best by (confidence_multiplier desc, method rank desc)
            if canonical not in best:
                best[canonical] = result
            else:
                existing = best[canonical]
                if (
                    result["confidence_multiplier"] > existing["confidence_multiplier"]
                    or (
                        result["confidence_multiplier"] == existing["confidence_multiplier"]
                        and _METHOD_RANK.get(result["method"], 0)
                        > _METHOD_RANK.get(existing["method"], 0)
                    )
                ):
                    best[canonical] = result

    skills = sorted(best.values(), key=lambda s: s["canonical"].lower())

    logger.info(
        "normalize_skills: %d input → %d unique canonicals.",
        len(raw_list), len(skills),
    )
    return NormalizeResult(skills=skills, success=True, error=None)