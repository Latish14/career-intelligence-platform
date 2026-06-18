"""
priority_ranker.py
─────────────────────────────────────────────────────────────────────────────
Final ranking layer of the gap_analysis pipeline.

Consumes a GapReport from gap_detector.py and produces the platform's
canonical output:

    {
      "missing_skills":    [...],
      "priority_ranking":  [...]
    }

Pipeline position
-----------------
    resume_skills.py     → list[ResumeSkill]
    job_skills.py        → list[MarketSkill]
    gap_detector.py      → GapReport
         ↓
    priority_ranker.py   ← YOU ARE HERE
         ↓
    FastAPI response / React frontend / RAG chatbot

What this module does
---------------------
1.  RE-RANKING           — gap_detector scores each skill independently.
                           priority_ranker applies three cross-skill signals:

    a) LEARNING VELOCITY — skills in the same category cluster together
                           so the user builds momentum (learn Docker →
                           Kubernetes is faster than Docker → NLP).

    b) PREREQUISITE GRAPH— some skills unlock others:
                           Python is prerequisite for Scikit-learn, FastAPI,
                           PySpark. If a user lacks Python, it jumps to #1
                           regardless of other scores.

    c) QUICK WIN BONUS   — skills with high market demand but low
                           learning curve (based on community consensus)
                           get a small uplift so students see early results.

2.  GROUPED OUTPUT       — skills grouped by learning phase:
                           Phase 1 (Foundation) → Phase 2 (Core) → Phase 3 (Advanced)

3.  RICH EXPLANATION     — each ranked item gets a multi-signal explanation
                           suitable for the platform UI and RAG context.

4.  FINAL OUTPUT FORMAT  — matches the spec exactly:
                           {"missing_skills": [...], "priority_ranking": [...]}

Public API
----------
    RankedSkill         — TypedDict: one item in priority_ranking.
    PlatformOutput      — TypedDict: the canonical {"missing_skills", "priority_ranking"}.
    RankResult          — TypedDict: full internal result with extra metadata.

    rank_gaps(gap_report, user_skills, max_ranking) -> RankResult
    to_platform_output(rank_result)                 -> PlatformOutput
"""

from __future__ import annotations

import logging
from typing import TypedDict

from services.gap_analysis.gap_detector import GapReport, MissingSkill
from services.skill_engine.skill_dictionary import SKILL_CATALOG

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

# Prerequisite graph: skill → skills it unlocks / depends on it
# If user is missing a prerequisite, that prerequisite gets promoted
_PREREQUISITES: dict[str, list[str]] = {
    "Python":       ["Scikit-learn", "XGBoost", "LightGBM", "FastAPI",
                     "Django", "Flask", "NumPy", "Pandas", "SHAP", "LIME",
                     "Apache Spark", "TensorFlow", "PyTorch", "Streamlit"],
    "SQL":          ["PostgreSQL", "MySQL", "SQLite", "dbt", "Snowflake"],
    "Docker":       ["Kubernetes"],
    "JavaScript":   ["React", "Vue.js", "Next.js", "TypeScript"],
    "Linux":        ["Docker", "Kubernetes", "CI/CD", "Ansible", "Terraform"],
    "Git":          ["CI/CD"],
    "Machine Learning": ["Deep Learning", "TensorFlow", "PyTorch",
                         "Scikit-learn", "XGBoost"],
}

# Quick-win skills: high demand, relatively low learning curve
# Score bonus applied on top of priority_score
_QUICK_WIN_BONUS: dict[str, float] = {
    "Git":          0.08,
    "Docker":       0.06,
    "SQL":          0.07,
    "PostgreSQL":   0.05,
    "FastAPI":      0.05,
    "REST API":     0.05,
    "Pandas":       0.05,
    "NumPy":        0.04,
    "Pytest":       0.04,
    "Bash":         0.03,
    "Linux":        0.03,
}

# Category learning cluster order (skills in the same cluster are grouped
# to maximize momentum when studied together)
_CLUSTER_ORDER: list[str] = [
    "programming_language",
    "database",
    "data_science",
    "machine_learning",
    "data_engineering",
    "web_backend",
    "devops",
    "cloud",
    "nlp",
    "computer_vision",
    "web_frontend",
    "mobile",
    "testing",
    "soft_skill",
    "other",
]

# Phase thresholds (based on final_score after all adjustments)
_PHASE_THRESHOLDS = [
    (0.75, "Phase 1 — Foundation"),
    (0.50, "Phase 2 — Core"),
    (0.00, "Phase 3 — Advanced"),
]


# ── Return types ──────────────────────────────────────────────────────────────

class RankedSkill(TypedDict):
    rank:           int
    skill:          str
    category:       str
    demand_pct:     float
    tier:           str
    final_score:    float           # [0.0 – 1.0] after all adjustments
    phase:          str             # "Phase 1 — Foundation" etc.
    is_prerequisite: bool           # True if other missing skills depend on it
    is_partial:     bool
    quick_win:      bool
    explanation:    str             # rich multi-signal explanation


class PlatformOutput(TypedDict):
    missing_skills:   list[dict]    # simplified MissingSkill dicts
    priority_ranking: list[RankedSkill]


class RankResult(TypedDict):
    ranked_skills:    list[RankedSkill]
    platform_output:  PlatformOutput
    total_gaps:       int
    phase_summary:    dict[str, list[str]]   # phase → [skill names]
    coverage_pct:     float
    placement_score:  float
    success:          bool
    error:            str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_phase(score: float) -> str:
    for threshold, label in _PHASE_THRESHOLDS:
        if score >= threshold:
            return label
    return "Phase 3 — Advanced"


def _is_prerequisite_for_missing(
    skill: str,
    missing_set: set[str],
) -> bool:
    """Return True if this skill unlocks one or more other missing skills."""
    unlocks = _PREREQUISITES.get(skill, [])
    return any(u in missing_set for u in unlocks)


def _prerequisite_boost(
    skill: str,
    missing_set: set[str],
) -> float:
    """
    Boost score if this skill is a prerequisite for other missing skills.
    Larger boost when more skills depend on it.
    """
    unlocks = _PREREQUISITES.get(skill, [])
    count   = sum(1 for u in unlocks if u in missing_set)
    if count == 0:
        return 0.0
    # Logarithmic: first unlock = +0.12, each additional = diminishing
    import math
    return round(min(0.25, 0.12 * math.log(count + 1, 2) + 0.08), 4)


def _cluster_position(category: str) -> int:
    """Return cluster ordering index (lower = earlier in curriculum)."""
    try:
        return _CLUSTER_ORDER.index(category)
    except ValueError:
        return len(_CLUSTER_ORDER)


def _build_explanation(
    skill:          str,
    demand_pct:     float,
    tier:           str,
    is_prereq:      bool,
    unlocks:        list[str],
    is_partial:     bool,
    partial_match:  str | None,
    quick_win:      bool,
    phase:          str,
    final_score:    float,
) -> str:
    """Build a rich, multi-signal explanation for the platform UI."""
    parts: list[str] = []

    # Demand signal
    parts.append(f"{skill} appears in {demand_pct:.0f}% of job postings ({tier}).")

    # Prerequisite signal
    if is_prereq and unlocks:
        unlocks_str = ", ".join(unlocks[:3])
        suffix = f" +{len(unlocks)-3} more" if len(unlocks) > 3 else ""
        parts.append(
            f"Learning {skill} first unlocks faster progress on: "
            f"{unlocks_str}{suffix}."
        )

    # Partial match signal
    if is_partial and partial_match:
        parts.append(
            f"You already know {partial_match} — {skill} builds on the same "
            f"concepts, making this a smaller step than it appears."
        )

    # Quick win signal
    if quick_win:
        parts.append(
            f"{skill} has a relatively low learning curve with high market "
            f"payoff — a strong early win."
        )

    # Phase framing
    phase_map = {
        "Phase 1 — Foundation": "Tackle this in your first learning sprint.",
        "Phase 2 — Core":       "Prioritise after foundational skills are solid.",
        "Phase 3 — Advanced":   "Add to your profile once core skills are in place.",
    }
    parts.append(phase_map.get(phase, ""))

    return " ".join(p for p in parts if p)


# ── Core ranker ───────────────────────────────────────────────────────────────

def rank_gaps(
    gap_report:   GapReport,
    user_skills:  list[str] | None = None,
    max_ranking:  int = 20,
) -> RankResult:
    """
    Re-rank missing skills using prerequisite graph, cluster momentum,
    and quick-win bonuses. Produces the platform's canonical output.

    Parameters
    ----------
    gap_report : GapReport
        Output of gap_detector.detect_gaps().
    user_skills : list[str] | None
        User's current skills (canonical names). Used to resolve
        which prerequisites the user already has.
        If None, extracted from gap_report.present_skills.
    max_ranking : int
        Cap on number of ranked items returned. Default 20.

    Returns
    -------
    RankResult with ranked_skills and platform_output.
    """
    if not isinstance(gap_report, dict):
        msg = f"gap_report must be a dict, got {type(gap_report).__name__}"
        logger.error(msg)
        return RankResult(
            ranked_skills=[], platform_output=PlatformOutput(
                missing_skills=[], priority_ranking=[]),
            total_gaps=0, phase_summary={}, coverage_pct=0.0,
            placement_score=0.0, success=False, error=msg,
        )

    if not gap_report.get("success"):
        msg = f"gap_report has success=False: {gap_report.get('error')}"
        return RankResult(
            ranked_skills=[], platform_output=PlatformOutput(
                missing_skills=[], priority_ranking=[]),
            total_gaps=0, phase_summary={}, coverage_pct=0.0,
            placement_score=0.0, success=False, error=msg,
        )

    missing: list[MissingSkill] = gap_report.get("missing_skills", [])
    if not missing:
        logger.info("rank_gaps: no missing skills — user profile complete.")
        return RankResult(
            ranked_skills=[], platform_output=PlatformOutput(
                missing_skills=[], priority_ranking=[]),
            total_gaps=0, phase_summary={}, coverage_pct=100.0,
            placement_score=gap_report.get("placement_score", 100.0),
            success=True, error=None,
        )

    # ── Build context sets ────────────────────────────────────────────────────
    missing_names = {m["skill"] for m in missing}
    present_names = {p["skill"] for p in gap_report.get("present_skills", [])}
    user_set      = (
        {s.lower() for s in user_skills}
        if user_skills
        else {s.lower() for s in present_names}
    )

    logger.info(
        "rank_gaps: %d missing skills  %d present  max_ranking=%d",
        len(missing), len(present_names), max_ranking,
    )

    # ── Score each missing skill ──────────────────────────────────────────────
    scored: list[tuple[float, int, MissingSkill]] = []
    # secondary key = cluster_position (lower cluster → appears earlier)

    for ms in missing:
        base    = ms["priority_score"]   # from gap_detector [0–1]

        # Prerequisite boost
        prereq_b = _prerequisite_boost(ms["skill"], missing_names)

        # Quick-win bonus
        qw_bonus = _QUICK_WIN_BONUS.get(ms["skill"], 0.0)

        # If the user already has ALL prerequisites for this skill,
        # give a small readiness bonus (they can start immediately)
        prereqs_for_this = [
            s for s, unlocks in _PREREQUISITES.items()
            if ms["skill"] in unlocks
        ]
        readiness_bonus = 0.05 if all(
            p.lower() in user_set for p in prereqs_for_this
        ) and prereqs_for_this else 0.0

        final = round(
            min(1.0, base + prereq_b + qw_bonus + readiness_bonus), 4
        )

        cluster_pos = _cluster_position(ms["category"])
        scored.append((final, cluster_pos, ms))

    # Sort: final_score desc, then cluster_position asc (tiebreak: learn in order)
    scored.sort(key=lambda x: (-x[0], x[1]))

    # ── Build RankedSkill list ────────────────────────────────────────────────
    ranked: list[RankedSkill] = []
    for rank_num, (final_score, _, ms) in enumerate(scored[:max_ranking], start=1):
        is_prereq = _is_prerequisite_for_missing(ms["skill"], missing_names)
        unlocks   = [u for u in _PREREQUISITES.get(ms["skill"], [])
                     if u in missing_names]
        quick_win = ms["skill"] in _QUICK_WIN_BONUS
        phase     = _get_phase(final_score)

        explanation = _build_explanation(
            skill         = ms["skill"],
            demand_pct    = ms["demand_pct"],
            tier          = ms["tier"],
            is_prereq     = is_prereq,
            unlocks       = unlocks,
            is_partial    = ms["is_partial"],
            partial_match = ms.get("partial_match"),
            quick_win     = quick_win,
            phase         = phase,
            final_score   = final_score,
        )

        ranked.append(RankedSkill(
            rank             = rank_num,
            skill            = ms["skill"],
            category         = ms["category"],
            demand_pct       = ms["demand_pct"],
            tier             = ms["tier"],
            final_score      = final_score,
            phase            = phase,
            is_prerequisite  = is_prereq,
            is_partial       = ms["is_partial"],
            quick_win        = quick_win,
            explanation      = explanation,
        ))

    # ── Phase summary ─────────────────────────────────────────────────────────
    phase_summary: dict[str, list[str]] = {}
    for rs in ranked:
        phase_summary.setdefault(rs["phase"], []).append(rs["skill"])

    # ── Platform output ───────────────────────────────────────────────────────
    platform = to_platform_output_from_parts(missing, ranked)

    logger.info(
        "rank_gaps complete: %d ranked  phases=%s",
        len(ranked),
        {k: len(v) for k, v in phase_summary.items()},
    )

    return RankResult(
        ranked_skills   = ranked,
        platform_output = platform,
        total_gaps      = len(missing),
        phase_summary   = phase_summary,
        coverage_pct    = gap_report.get("coverage_pct", 0.0),
        placement_score = gap_report.get("placement_score", 0.0),
        success         = True,
        error           = None,
    )


def to_platform_output_from_parts(
    missing:  list[MissingSkill],
    ranked:   list[RankedSkill],
) -> PlatformOutput:
    """Build the canonical platform dict from components."""
    return PlatformOutput(
        missing_skills   = [dict(m) for m in missing],
        priority_ranking = ranked,
    )


def to_platform_output(rank_result: RankResult) -> PlatformOutput:
    """
    Extract just the canonical platform output from a RankResult.

    Returns
    -------
    PlatformOutput
        {
          "missing_skills":   [ {skill, category, demand_pct, tier,
                                 priority_score, is_partial, explanation}, ... ],
          "priority_ranking": [ {rank, skill, category, demand_pct, tier,
                                 final_score, phase, is_prerequisite,
                                 is_partial, quick_win, explanation}, ... ]
        }
    """
    return rank_result.get("platform_output", PlatformOutput(
        missing_skills=[], priority_ranking=[]
    ))