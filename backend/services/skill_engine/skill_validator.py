"""
skill_validator.py
─────────────────────────────────────────────────────────────────────────────
Final validation layer for the skill_engine pipeline.

Responsibility
--------------
Takes the output of skill_extractor + skill_normalizer and produces a clean,
validated, deduplicated list of skills with final confidence scores.

Validation checks (applied in order)
--------------------------------------
1.  CATALOG MEMBERSHIP    — skill must exist in SKILL_CATALOG as a canonical.
                            Rejects anything not in the master dictionary.

2.  CONFIDENCE FLOOR      — final confidence must meet min_confidence.
                            Default: 0.50.

3.  CATEGORY ALLOWLIST    — optional list of allowed categories.
                            If provided, skills outside those categories
                            are rejected. Useful for role-specific parsing
                            (e.g. only "machine_learning" + "data_science").

4.  BLOCKLIST             — optional set of canonical names to exclude.
                            Caller can pass known false-positives per resume.

5.  CROSS-SIGNAL MERGE    — when both extractor and normalizer produce a
                            result for the same canonical, the scores are
                            merged:
                            final = min(1.0, extractor_conf × norm_multiplier)

6.  DUPLICATE COLLAPSE    — canonicals appearing more than once are merged
                            to the highest final confidence.

7.  SOFT-SKILL GATE       — soft skills require confidence ≥ 0.80 to pass
                            (they are inherently noisier to detect).

Output
------
    [
        {"skill": "Python",       "confidence": 0.95},
        {"skill": "XGBoost",      "confidence": 1.00},
        {"skill": "Scikit-learn", "confidence": 1.00},
        ...
    ]
    Sorted: confidence descending, then alphabetical.

Public API
----------
    ValidSkill          — TypedDict for final output record.
    ValidationResult    — TypedDict returned by validate_skills().

    validate_skills(
        extracted,          # list[SkillMatch]   from skill_extractor
        normalized,         # list[NormResult]   from skill_normalizer
        *,
        min_confidence,     # float  default 0.50
        allowed_categories, # list[str] | None
        blocklist,          # set[str] | None
    ) -> ValidationResult
"""

from __future__ import annotations

import logging
from typing import TypedDict

from skill_engine.skill_dictionary import CANONICAL_SET, get_entry
from skill_engine.skill_extractor import SkillMatch
from skill_engine.skill_normalizer import NormResult

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_MIN_CONFIDENCE = 0.50
_SOFT_SKILL_MIN_CONFIDENCE = 0.80   # higher bar for inherently noisy category


# ── Return types ──────────────────────────────────────────────────────────────

class ValidSkill(TypedDict):
    skill: str
    confidence: float


class ValidationResult(TypedDict):
    skills: list[ValidSkill]
    success: bool
    total_found: int        # count before filtering
    total_valid: int        # count after all filters
    rejected: list[str]     # canonical names that were rejected + reason
    error: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(message: str) -> ValidationResult:
    logger.error(message)
    return ValidationResult(
        skills=[], success=False,
        total_found=0, total_valid=0,
        rejected=[], error=message,
    )


def _is_valid_canonical(name: str) -> bool:
    """Check canonical membership (case-insensitive)."""
    return name.lower() in CANONICAL_SET


def _merge_confidence(
    extractor_conf: float | None,
    norm_multiplier: float | None,
    base_weight: float,
) -> float:
    """
    Compute final confidence from available signals.

    Priority:
    1. Both extractor + normalizer  → extractor_conf × norm_multiplier
    2. Extractor only               → extractor_conf (already has base weight)
    3. Normalizer only              → base_weight × norm_multiplier
    4. Neither (catalog lookup only)→ base_weight
    """
    if extractor_conf is not None and norm_multiplier is not None:
        score = extractor_conf * norm_multiplier
    elif extractor_conf is not None:
        score = extractor_conf
    elif norm_multiplier is not None:
        score = base_weight * norm_multiplier
    else:
        score = base_weight

    return round(min(1.0, max(0.0, score)), 2)


# ── Public API ────────────────────────────────────────────────────────────────

def validate_skills(
    extracted: list[SkillMatch],
    normalized: list[NormResult],
    *,
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
    allowed_categories: list[str] | None = None,
    blocklist: set[str] | None = None,
) -> ValidationResult:
    """
    Validate, merge, and deduplicate skills from extractor + normalizer.

    Parameters
    ----------
    extracted : list[SkillMatch]
        Output of skill_extractor.extract_skills() — may be empty list.
    normalized : list[NormResult]
        Output of skill_normalizer.normalize_skills() — may be empty list.
    min_confidence : float
        Minimum confidence to include a skill. Default 0.50.
    allowed_categories : list[str] | None
        If provided, only skills in these categories are kept.
        E.g. ["machine_learning", "data_science", "programming_language"]
    blocklist : set[str] | None
        Canonical names to forcibly exclude (e.g. known false positives).

    Returns
    -------
    ValidationResult
        {
          "skills": [{"skill": "Python", "confidence": 0.95}, ...],
          "success": True,
          "total_found": 14,
          "total_valid": 10,
          "rejected": ["Communication (low confidence: 0.42)", ...],
          "error": None
        }
        Skills sorted by confidence desc, then alphabetically.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    if not isinstance(extracted, list):
        return _error(f"'extracted' must be a list, got {type(extracted).__name__}")
    if not isinstance(normalized, list):
        return _error(f"'normalized' must be a list, got {type(normalized).__name__}")
    if not (0.0 <= min_confidence <= 1.0):
        return _error(f"min_confidence must be in [0.0, 1.0], got {min_confidence}")

    blocklist = blocklist or set()
    allowed_cats = set(allowed_categories) if allowed_categories else None

    # ── Build lookup maps ─────────────────────────────────────────────────────

    # canonical → extractor confidence
    ext_map: dict[str, float] = {
        m["skill"]: m["confidence"]
        for m in extracted
        if isinstance(m, dict) and "skill" in m
    }

    # canonical → normalizer confidence_multiplier
    norm_map: dict[str, float] = {
        n["canonical"]: n["confidence_multiplier"]
        for n in normalized
        if isinstance(n, dict) and "canonical" in n
    }

    # Union of all candidate canonicals
    all_canonicals: set[str] = set(ext_map.keys()) | set(norm_map.keys())
    total_found = len(all_canonicals)

    # ── Validate each candidate ───────────────────────────────────────────────
    final: dict[str, float] = {}   # canonical → final confidence
    rejected: list[str] = []

    for canonical in sorted(all_canonicals):

        # 1. Catalog membership
        if not _is_valid_canonical(canonical):
            reason = f"{canonical} (not in catalog)"
            rejected.append(reason)
            logger.debug("Rejected: %s", reason)
            continue

        entry = get_entry(canonical)
        if entry is None:
            reason = f"{canonical} (entry lookup failed)"
            rejected.append(reason)
            continue

        base_weight = entry["weight"]
        category    = entry["category"]

        # 2. Blocklist
        if canonical in blocklist or canonical.lower() in {b.lower() for b in blocklist}:
            reason = f"{canonical} (blocklisted)"
            rejected.append(reason)
            logger.debug("Rejected: %s", reason)
            continue

        # 3. Category allowlist
        if allowed_cats and category not in allowed_cats:
            reason = f"{canonical} (category '{category}' not in allowlist)"
            rejected.append(reason)
            logger.debug("Rejected: %s", reason)
            continue

        # 4. Compute merged confidence
        ext_conf  = ext_map.get(canonical)
        norm_mult = norm_map.get(canonical)
        confidence = _merge_confidence(ext_conf, norm_mult, base_weight)

        # 5. Soft-skill gate
        if category == "soft_skill" and confidence < _SOFT_SKILL_MIN_CONFIDENCE:
            reason = (
                f"{canonical} (soft skill below gate: "
                f"{confidence:.2f} < {_SOFT_SKILL_MIN_CONFIDENCE})"
            )
            rejected.append(reason)
            logger.debug("Rejected: %s", reason)
            continue

        # 6. Confidence floor
        if confidence < min_confidence:
            reason = f"{canonical} (low confidence: {confidence:.2f})"
            rejected.append(reason)
            logger.debug("Rejected: %s", reason)
            continue

        # 7. Dedup — keep highest confidence
        if canonical not in final or confidence > final[canonical]:
            final[canonical] = confidence

    # ── Assemble output ───────────────────────────────────────────────────────
    skills: list[ValidSkill] = sorted(
        [ValidSkill(skill=k, confidence=v) for k, v in final.items()],
        key=lambda s: (-s["confidence"], s["skill"]),
    )

    total_valid = len(skills)
    logger.info(
        "validate_skills: %d found → %d valid, %d rejected.",
        total_found, total_valid, len(rejected),
    )

    return ValidationResult(
        skills=skills,
        success=True,
        total_found=total_found,
        total_valid=total_valid,
        rejected=rejected,
        error=None,
    )