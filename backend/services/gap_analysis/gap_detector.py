"""
gap_detector.py
─────────────────────────────────────────────────────────────────────────────
Detects skill gaps between a user's resume skills and market-demanded skills.

Pipeline position
-----------------
    resume_skills.py   → list[ResumeSkill]   (user's current skills)
    job_skills.py      → list[MarketSkill]   (market demand data)
         ↓  both feed into
    gap_detector.py    ← YOU ARE HERE
         ↓  GapReport
    priority_ranker.py ← consumes GapReport.missing_skills for final ranking

What this module does
---------------------
1.  NORMALISATION       — both resume and market skill names are lowercased
                          and alias-resolved via skill_engine.ALIAS_INDEX so
                          "sklearn" == "Scikit-learn" and "JS" == "JavaScript".

2.  GAP DETECTION       — set subtraction:
                          missing = market_skills − resume_skills
                          present = market_skills ∩ resume_skills
                          extra   = resume_skills − market_skills (niche/rare)

3.  PARTIAL MATCH       — catches near-misses where a user has a related skill
                          in the same category (e.g. has TensorFlow, market
                          wants PyTorch → partial match, not hard gap).
                          Partial matches get a reduced priority score.

4.  PRIORITY SCORE      — each missing skill gets a composite priority score:
                              demand_weight   × market_demand_pct   (50%)
                            + category_weight × category_priority    (25%)
                            + rarity_weight   × (1 – user_coverage)  (25%)
                          Score normalised to [0.0 – 1.0].

5.  EXPLANATION         — every missing skill has a human-readable reason
                          string explaining why it is prioritised, ready for
                          display in the platform UI or RAG context.

6.  COVERAGE METRICS    — overall skill coverage percentage, per-category
                          coverage, and a placement readiness score.

Public API
----------
    ResumeSkill         — TypedDict: one skill from the user's resume.
    MarketSkill         — TypedDict: one skill from market/JD analysis.
    MissingSkill        — TypedDict: one detected gap with score + explanation.
    GapReport           — TypedDict: full output of detect_gaps().

    detect_gaps(
        resume_skills,      list[ResumeSkill]
        market_skills,      list[MarketSkill]
        *,
        partial_match,      bool  default True
        min_demand_pct,     float default 0.0
    ) -> GapReport

    Output shape
    ------------
    {
      "missing_skills": [
        {
          "skill":         "Docker",
          "category":      "devops",
          "demand_pct":    80.0,
          "priority_score": 0.91,
          "tier":          "CRITICAL",
          "is_partial":    False,
          "partial_match": None,
          "explanation":   "Docker is required in 80% of roles. No related
                            devops skill found in your resume. Highest
                            priority gap to close."
        },
        ...
      ],
      "present_skills":  [...],
      "extra_skills":    [...],
      "coverage_pct":    38.5,
      "by_category":     {"devops": {...}, ...},
      "placement_score": 42.1,
      "success":         True,
      "error":           None
    }
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TypedDict

from services.skill_engine.skill_dictionary import ALIAS_INDEX, get_entry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

# Demand tier thresholds (same as market_trends.py for consistency)
_TIER_MAP: list[tuple[float, str]] = [
    (60.0, "CRITICAL"),
    (40.0, "HIGH"),
    (20.0, "MODERATE"),
    (0.0,  "EMERGING"),
]

# Category priority weights (higher = more impactful for placement)
_CATEGORY_PRIORITY: dict[str, float] = {
    "programming_language": 1.0,
    "machine_learning":     0.95,
    "data_science":         0.90,
    "data_engineering":     0.90,
    "database":             0.85,
    "cloud":                0.85,
    "devops":               0.80,
    "web_backend":          0.80,
    "nlp":                  0.80,
    "computer_vision":      0.75,
    "web_frontend":         0.70,
    "mobile":               0.65,
    "testing":              0.60,
    "soft_skill":           0.40,
    "other":                0.50,
}

# Score component weights (must sum to 1.0)
_W_DEMAND   = 0.50    # market demand percentage
_W_CATEGORY = 0.25    # category strategic importance
_W_RARITY   = 0.25    # how few resume skills cover this category

# Partial match score multiplier (reduces priority for near-miss gaps)
_PARTIAL_MULTIPLIER = 0.60


# ── Input types (consumed from resume_skills.py / job_skills.py) ──────────────

class ResumeSkill(TypedDict):
    skill:       str           # canonical or raw skill name
    confidence:  float         # how confident the parser is [0–1]
    source:      str           # "explicit" | "inferred" | "project"


class MarketSkill(TypedDict):
    skill:       str           # canonical or raw skill name
    demand_pct:  float         # percentage of JDs requiring this skill
    category:    str           # from skill_dictionary
    base_weight: float         # lexical confidence weight


# ── Output types ──────────────────────────────────────────────────────────────

class MissingSkill(TypedDict):
    skill:          str
    category:       str
    demand_pct:     float
    priority_score: float      # [0.0 – 1.0]  higher = learn sooner
    tier:           str        # CRITICAL | HIGH | MODERATE | EMERGING
    is_partial:     bool       # True if user has a related skill
    partial_match:  str | None # name of the related skill they DO have
    explanation:    str        # human-readable priority justification


class PresentSkill(TypedDict):
    skill:      str
    category:   str
    demand_pct: float
    tier:       str


class CategoryCoverage(TypedDict):
    category:        str
    required_count:  int       # market skills in this category
    present_count:   int       # user skills matching market in this category
    missing_count:   int
    coverage_pct:    float


class GapReport(TypedDict):
    missing_skills:  list[MissingSkill]    # sorted by priority_score desc
    present_skills:  list[PresentSkill]    # skills user has that market wants
    extra_skills:    list[str]             # user skills not in market demand
    coverage_pct:    float                 # overall coverage (0–100)
    by_category:     dict[str, CategoryCoverage]
    placement_score: float                 # weighted placement readiness (0–100)
    success:         bool
    error:           str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve(name: str) -> str:
    """Resolve a raw skill name to its canonical form via ALIAS_INDEX."""
    key = name.lower().strip()
    return ALIAS_INDEX.get(key, name.strip())   # fallback to original if not found


def _get_tier(pct: float) -> str:
    for threshold, tier in _TIER_MAP:
        if pct >= threshold:
            return tier
    return "EMERGING"


def _category_priority(category: str) -> float:
    return _CATEGORY_PRIORITY.get(category, 0.50)


def _priority_score(
    demand_pct:    float,
    category:      str,
    user_cat_coverage: float,   # fraction of this category user already has
    is_partial:    bool,
) -> float:
    """
    Composite priority score [0.0 – 1.0].

    Components
    ----------
    demand_score    : demand_pct / 100           (0–1)
    category_score  : _CATEGORY_PRIORITY[cat]    (0–1)
    rarity_score    : 1 – user_cat_coverage      (0–1, high when user lacks the category)

    Weighted sum, then penalised by _PARTIAL_MULTIPLIER if is_partial.
    """
    demand_score   = demand_pct / 100.0
    category_score = _category_priority(category)
    rarity_score   = 1.0 - user_cat_coverage

    raw = (
        _W_DEMAND   * demand_score
        + _W_CATEGORY * category_score
        + _W_RARITY   * rarity_score
    )

    if is_partial:
        raw *= _PARTIAL_MULTIPLIER

    return round(min(1.0, max(0.0, raw)), 4)


def _explanation(
    skill:         str,
    demand_pct:    float,
    tier:          str,
    category:      str,
    is_partial:    bool,
    partial_match: str | None,
    user_cat_coverage: float,
    priority_score: float,
) -> str:
    """Build a concise, human-readable explanation for the gap."""
    cat_display = category.replace("_", " ")

    # Demand statement
    demand_str = f"{skill} is required in {demand_pct:.0f}% of job postings."

    # Coverage context
    if user_cat_coverage == 0.0:
        coverage_str = (
            f"You have no {cat_display} skills in your profile — "
            f"this entire category is a gap."
        )
    elif user_cat_coverage < 0.5:
        pct_have = round(user_cat_coverage * 100)
        coverage_str = (
            f"You cover {pct_have}% of the {cat_display} skills "
            f"employers expect."
        )
    else:
        pct_have = round(user_cat_coverage * 100)
        coverage_str = (
            f"You already cover {pct_have}% of {cat_display} skills, "
            f"adding {skill} will complete the picture."
        )

    # Partial match context
    if is_partial and partial_match:
        partial_str = (
            f"You have {partial_match} which is related, but {skill} is "
            f"specifically requested in this market."
        )
    else:
        partial_str = f"This skill is absent from your resume."

    # Priority framing
    if tier == "CRITICAL" and priority_score >= 0.80:
        priority_str = "Highest priority gap to close."
    elif tier == "CRITICAL":
        priority_str = "Critical gap — address this before applying."
    elif tier == "HIGH":
        priority_str = "High-value addition for your profile."
    elif tier == "MODERATE":
        priority_str = "Moderate impact — useful for differentiation."
    else:
        priority_str = "Emerging demand — good for future-proofing."

    return " ".join([demand_str, coverage_str, partial_str, priority_str])


# ── Normalisation ─────────────────────────────────────────────────────────────

def _normalise_resume(skills: list[ResumeSkill]) -> dict[str, ResumeSkill]:
    """
    Resolve all resume skill names to canonicals.
    Returns dict[canonical_lower → ResumeSkill].
    Keeps the highest-confidence entry per canonical.
    """
    out: dict[str, ResumeSkill] = {}
    for rs in skills:
        canonical = _resolve(rs["skill"])
        key       = canonical.lower()
        if key not in out or rs["confidence"] > out[key]["confidence"]:
            out[key] = ResumeSkill(
                skill      = canonical,
                confidence = rs["confidence"],
                source     = rs["source"],
            )
    return out


def _normalise_market(skills: list[MarketSkill]) -> dict[str, MarketSkill]:
    """
    Resolve all market skill names to canonicals.
    Returns dict[canonical_lower → MarketSkill].
    """
    out: dict[str, MarketSkill] = {}
    for ms in skills:
        canonical = _resolve(ms["skill"])
        key       = canonical.lower()

        # Resolve category from dictionary if not set
        category = ms.get("category", "")
        if not category or category == "other":
            entry    = get_entry(canonical)
            category = entry["category"] if entry else "other"

        base_weight = ms.get("base_weight", 0.85)
        if not base_weight:
            entry      = get_entry(canonical)
            base_weight= entry["weight"] if entry else 0.85

        if key not in out or ms["demand_pct"] > out[key]["demand_pct"]:
            out[key] = MarketSkill(
                skill       = canonical,
                demand_pct  = ms["demand_pct"],
                category    = category,
                base_weight = base_weight,
            )
    return out


# ── Partial match detection ───────────────────────────────────────────────────

def _find_partial_match(
    market_skill:   str,
    market_category: str,
    resume_map:     dict[str, ResumeSkill],
    market_map:     dict[str, MarketSkill],
) -> str | None:
    """
    Check whether the user has a *related* skill in the same category
    that partially satisfies this market demand.

    Returns the canonical name of the matching resume skill, or None.
    """
    for resume_key, rs in resume_map.items():
        # Must be in the same category
        rs_entry = get_entry(rs["skill"])
        if not rs_entry:
            continue
        if rs_entry["category"] != market_category:
            continue
        # Must not be the exact skill we're looking for
        if resume_key == market_skill.lower():
            continue
        return rs["skill"]   # found a same-category sibling

    return None


# ── Category coverage map ─────────────────────────────────────────────────────

def _build_category_coverage(
    market_map: dict[str, MarketSkill],
    resume_map: dict[str, ResumeSkill],
) -> dict[str, CategoryCoverage]:
    """
    For each market category, count how many skills the user has vs. total.
    """
    # Group market skills by category
    cat_market: dict[str, list[str]] = defaultdict(list)
    for key, ms in market_map.items():
        cat_market[ms["category"]].append(key)

    # Group resume skills by category
    cat_resume: set[str] = set()
    for key, rs in resume_map.items():
        entry = get_entry(rs["skill"])
        if entry:
            cat_resume.add(entry["category"])

    coverage: dict[str, CategoryCoverage] = {}
    for cat, market_keys in cat_market.items():
        present = [k for k in market_keys if k in resume_map]
        total   = len(market_keys)
        pcount  = len(present)
        coverage[cat] = CategoryCoverage(
            category       = cat,
            required_count = total,
            present_count  = pcount,
            missing_count  = total - pcount,
            coverage_pct   = round(pcount / total * 100, 1) if total else 0.0,
        )
    return coverage


# ── Public API ────────────────────────────────────────────────────────────────

def detect_gaps(
    resume_skills: list[ResumeSkill],
    market_skills: list[MarketSkill],
    *,
    partial_match: bool = True,
    min_demand_pct: float = 0.0,
) -> GapReport:
    """
    Detect skill gaps between a user's resume and market demand.

    Parameters
    ----------
    resume_skills : list[ResumeSkill]
        Skills extracted from the user's resume (from resume_skills.py).
        Each entry: {"skill": str, "confidence": float, "source": str}

    market_skills : list[MarketSkill]
        Skills required by the market (from job_skills.py / skill_counter.py).
        Each entry: {"skill": str, "demand_pct": float,
                     "category": str, "base_weight": float}

    partial_match : bool  (default True)
        When True, if the user has a skill in the same category as a missing
        skill, it is flagged as a partial match (lower priority, not a hard gap).

    min_demand_pct : float  (default 0.0)
        Only include market skills with demand_pct ≥ this value.
        Set to 20.0 to skip EMERGING skills, 40.0 for HIGH+ only.

    Returns
    -------
    GapReport
        {
          "missing_skills":  [MissingSkill, ...],   sorted by priority_score desc
          "present_skills":  [PresentSkill, ...],   sorted by demand_pct desc
          "extra_skills":    [str, ...],             resume skills not in market
          "coverage_pct":    float,                 0–100
          "by_category":     {cat: CategoryCoverage},
          "placement_score": float,                 0–100 weighted readiness
          "success":         bool,
          "error":           str | None
        }

    Notes
    -----
    - Skill names are resolved to canonical forms before comparison.
    - A skill present in resume with confidence < 0.30 is treated as absent
      (low-confidence inferences from resume_skills.py are not reliable enough).
    - placement_score weights CRITICAL gaps more heavily than EMERGING ones.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    if not isinstance(resume_skills, list):
        msg = f"resume_skills must be list, got {type(resume_skills).__name__}"
        logger.error(msg)
        return GapReport(
            missing_skills=[], present_skills=[], extra_skills=[],
            coverage_pct=0.0, by_category={}, placement_score=0.0,
            success=False, error=msg,
        )
    if not isinstance(market_skills, list):
        msg = f"market_skills must be list, got {type(market_skills).__name__}"
        logger.error(msg)
        return GapReport(
            missing_skills=[], present_skills=[], extra_skills=[],
            coverage_pct=0.0, by_category={}, placement_score=0.0,
            success=False, error=msg,
        )

    logger.info(
        "detect_gaps: %d resume skills  %d market skills  "
        "partial_match=%s  min_demand_pct=%.1f",
        len(resume_skills), len(market_skills),
        partial_match, min_demand_pct,
    )

    # ── Normalise ─────────────────────────────────────────────────────────────
    resume_map = _normalise_resume(resume_skills)

    # Filter low-confidence resume skills
    resume_map = {
        k: v for k, v in resume_map.items()
        if v["confidence"] >= 0.30
    }

    market_map = _normalise_market(market_skills)

    # Apply min_demand_pct filter
    if min_demand_pct > 0:
        market_map = {
            k: v for k, v in market_map.items()
            if v["demand_pct"] >= min_demand_pct
        }

    if not market_map:
        return GapReport(
            missing_skills=[], present_skills=[], extra_skills=[],
            coverage_pct=100.0, by_category={}, placement_score=100.0,
            success=True, error=None,
        )

    # ── Category coverage ─────────────────────────────────────────────────────
    cat_coverage = _build_category_coverage(market_map, resume_map)

    # Precompute user's category coverage fraction per category
    cat_fractions: dict[str, float] = {
        cat: (cc["present_count"] / cc["required_count"]
              if cc["required_count"] else 0.0)
        for cat, cc in cat_coverage.items()
    }

    # ── Gap detection ─────────────────────────────────────────────────────────
    missing: list[MissingSkill] = []
    present: list[PresentSkill] = []
    market_keys = set(market_map.keys())
    resume_keys = set(resume_map.keys())

    for key, ms in market_map.items():
        tier = _get_tier(ms["demand_pct"])

        if key in resume_keys:
            # User has this skill
            present.append(PresentSkill(
                skill      = ms["skill"],
                category   = ms["category"],
                demand_pct = ms["demand_pct"],
                tier       = tier,
            ))
        else:
            # Skill is missing — check for partial match
            pm_name: str | None = None
            is_pm   = False

            if partial_match:
                pm_name = _find_partial_match(
                    ms["skill"], ms["category"], resume_map, market_map
                )
                is_pm = pm_name is not None

            # Category coverage fraction (how much of this category user has)
            cat_frac = cat_fractions.get(ms["category"], 0.0)

            score = _priority_score(
                demand_pct          = ms["demand_pct"],
                category            = ms["category"],
                user_cat_coverage   = cat_frac,
                is_partial          = is_pm,
            )

            explanation = _explanation(
                skill              = ms["skill"],
                demand_pct         = ms["demand_pct"],
                tier               = tier,
                category           = ms["category"],
                is_partial         = is_pm,
                partial_match      = pm_name,
                user_cat_coverage  = cat_frac,
                priority_score     = score,
            )

            missing.append(MissingSkill(
                skill          = ms["skill"],
                category       = ms["category"],
                demand_pct     = ms["demand_pct"],
                priority_score = score,
                tier           = tier,
                is_partial     = is_pm,
                partial_match  = pm_name,
                explanation    = explanation,
            ))

    # ── Extra skills (resume has, market doesn't mention) ─────────────────────
    extra = sorted(
        resume_map[k]["skill"]
        for k in (resume_keys - market_keys)
    )

    # ── Sort missing by priority_score desc ───────────────────────────────────
    missing.sort(key=lambda m: (-m["priority_score"], -m["demand_pct"]))

    # ── Sort present by demand_pct desc ──────────────────────────────────────
    present.sort(key=lambda p: -p["demand_pct"])

    # ── Coverage metrics ──────────────────────────────────────────────────────
    total_market = len(market_map)
    total_present= len(present)
    coverage_pct = round(total_present / total_market * 100, 1) if total_market else 0.0

    # ── Placement score ───────────────────────────────────────────────────────
    # Weighted by tier: CRITICAL gaps penalise most, EMERGING least
    tier_penalty = {"CRITICAL": 1.0, "HIGH": 0.7, "MODERATE": 0.4, "EMERGING": 0.2}
    max_penalty  = sum(tier_penalty.get(_get_tier(ms["demand_pct"]), 0.2)
                       for ms in market_map.values())
    gap_penalty  = sum(tier_penalty.get(m["tier"], 0.2) * (1 - m["is_partial"] * 0.4)
                       for m in missing)

    placement_score = round(
        max(0.0, (1 - gap_penalty / max_penalty) * 100) if max_penalty else 100.0,
        1,
    )

    logger.info(
        "detect_gaps complete: missing=%d  present=%d  extra=%d  "
        "coverage=%.1f%%  placement_score=%.1f",
        len(missing), total_present, len(extra),
        coverage_pct, placement_score,
    )

    return GapReport(
        missing_skills  = missing,
        present_skills  = present,
        extra_skills    = extra,
        coverage_pct    = coverage_pct,
        by_category     = cat_coverage,
        placement_score = placement_score,
        success         = True,
        error           = None,
    )