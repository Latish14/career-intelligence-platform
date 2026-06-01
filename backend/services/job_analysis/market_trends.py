"""
market_trends.py
─────────────────────────────────────────────────────────────────────────────
Generates market intelligence from CorpusStats produced by skill_counter.py.

Pipeline position
-----------------
    jd_parser.py          → ParsedJD
    skill_counter.py      → CorpusStats
    market_trends.py      ← YOU ARE HERE
        ↓  TrendReport

What this module does
---------------------
1.  DEMAND TIERS          — classifies skills into tiers:
                            CRITICAL  ≥ 60%   | must-have
                            HIGH      40–59%  | strongly preferred
                            MODERATE  20–39%  | nice-to-have
                            EMERGING  < 20%   | growing signal

2.  CATEGORY DOMINANCE    — which skill categories dominate this corpus
                            (e.g. "devops heavy", "ML-focused").

3.  ROLE-BASED SKILL PROFILE — maps common role titles to their expected
                            skill clusters and scores the corpus against them
                            (e.g. "This corpus is 78% aligned with Data Engineer roles").

4.  SKILL GAP SCORING     — given a user's skill set, scores how many
                            high-demand skills are missing (the gap).

5.  LEARNING ROADMAP      — ordered list of skills to learn based on:
                            (a) demand percentage, (b) co-occurrence with
                            skills the user already has, (c) category priority.

6.  TREND SNAPSHOT        — human-readable summary text for display or RAG.

Public API
----------
    DemandTier          — Literal type for tier labels.
    SkillTrend          — TypedDict: one skill enriched with tier + context.
    RoleAlignment       — TypedDict: corpus alignment score for a role.
    GapAnalysis         — TypedDict: per-skill gap result.
    RoadmapStep         — TypedDict: one step in a learning roadmap.
    TrendReport         — TypedDict: full output.

    generate_trends(corpus_stats, role_filter, top_n) -> TrendReport
    skill_gap(corpus_stats, user_skills)             -> list[GapAnalysis]
    learning_roadmap(corpus_stats, user_skills,
                     max_steps)                      -> list[RoadmapStep]
    trend_snapshot(trend_report)                     -> str
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Literal, TypedDict

from job_analysis.skill_counter import CorpusStats, SkillStat

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

DemandTier = Literal["CRITICAL", "HIGH", "MODERATE", "EMERGING"]

_TIER_THRESHOLDS: list[tuple[float, DemandTier]] = [
    (60.0, "CRITICAL"),
    (40.0, "HIGH"),
    (20.0, "MODERATE"),
    (0.0,  "EMERGING"),
]

# Role → expected skill categories (in priority order)
_ROLE_PROFILES: dict[str, dict[str, object]] = {
    "Data Engineer": {
        "must_categories": ["programming_language", "database", "data_engineering"],
        "strong_categories": ["cloud", "devops"],
        "must_skills": ["Python", "SQL", "Apache Spark"],
        "bonus_skills": ["dbt", "Airflow", "Kafka"],
    },
    "ML Engineer": {
        "must_categories": ["machine_learning", "programming_language"],
        "strong_categories": ["cloud", "devops", "data_science"],
        "must_skills": ["Python", "TensorFlow", "PyTorch"],
        "bonus_skills": ["Scikit-learn", "XGBoost", "Docker", "Kubernetes"],
    },
    "Data Scientist": {
        "must_categories": ["machine_learning", "data_science", "programming_language"],
        "strong_categories": ["database", "nlp"],
        "must_skills": ["Python", "Machine Learning", "SQL"],
        "bonus_skills": ["SHAP", "Scikit-learn", "XGBoost", "R"],
    },
    "Backend Engineer": {
        "must_categories": ["programming_language", "web_backend", "database"],
        "strong_categories": ["devops", "cloud"],
        "must_skills": ["Python", "SQL", "REST API"],
        "bonus_skills": ["Docker", "PostgreSQL", "Redis", "FastAPI"],
    },
    "DevOps Engineer": {
        "must_categories": ["devops", "cloud"],
        "strong_categories": ["programming_language"],
        "must_skills": ["Docker", "Kubernetes", "CI/CD"],
        "bonus_skills": ["Terraform", "Ansible", "AWS", "Python"],
    },
    "Full Stack Engineer": {
        "must_categories": ["web_frontend", "web_backend", "programming_language"],
        "strong_categories": ["database", "devops"],
        "must_skills": ["JavaScript", "React", "SQL"],
        "bonus_skills": ["TypeScript", "Node.js", "Docker", "PostgreSQL"],
    },
}

# Category display order for the trend report
_CATEGORY_ORDER = [
    "programming_language", "machine_learning", "data_science",
    "data_engineering", "database", "web_backend", "web_frontend",
    "cloud", "devops", "nlp", "computer_vision", "mobile",
    "testing", "soft_skill", "other",
]


# ── Return types ──────────────────────────────────────────────────────────────

class SkillTrend(TypedDict):
    skill:          str
    category:       str
    percentage:     float
    count:          int
    tier:           DemandTier
    demand_score:   float
    top_co_skills:  list[str]   # top 5 skills that appear alongside this one


class RoleAlignment(TypedDict):
    role:           str
    alignment_pct:  float       # 0–100: how well corpus matches this role
    matched_must:   list[str]   # must-have skills present in corpus
    missing_must:   list[str]   # must-have skills absent from corpus
    matched_bonus:  list[str]


class GapAnalysis(TypedDict):
    skill:          str
    category:       str
    percentage:     float       # demand in market
    tier:           DemandTier
    in_user_set:    bool
    priority:       int         # 1 = highest priority to learn


class RoadmapStep(TypedDict):
    step:           int
    skill:          str
    category:       str
    reason:         str         # human-readable explanation
    market_demand:  float       # percentage
    tier:           DemandTier


class TrendReport(TypedDict):
    success:            bool
    total_jds:          int
    top_skills:         list[SkillTrend]      # all skills with tier
    by_tier:            dict[str, list[SkillTrend]]
    by_category:        dict[str, list[SkillTrend]]
    category_dominance: list[tuple[str, int]] # (category, skill_count) sorted
    role_alignments:    list[RoleAlignment]
    error:              str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tier(pct: float) -> DemandTier:
    for threshold, tier in _TIER_THRESHOLDS:
        if pct >= threshold:
            return tier
    return "EMERGING"


def _skills_set(corpus: CorpusStats) -> set[str]:
    return {s["skill"] for s in corpus["skills"]}


# ── Core: generate_trends ─────────────────────────────────────────────────────

def generate_trends(
    corpus_stats: CorpusStats,
    role_filter: str | None = None,
    top_n: int | None = None,
) -> TrendReport:
    """
    Generate a full trend report from CorpusStats.

    Parameters
    ----------
    corpus_stats : CorpusStats
        Output of skill_counter.count_corpus().
    role_filter : str | None
        If set, role alignment is computed only for this role name.
        Must match a key in _ROLE_PROFILES (e.g. "Data Engineer").
        If None, all role profiles are scored.
    top_n : int | None
        Cap on number of skills in top_skills. None = all skills.

    Returns
    -------
    TrendReport
        Full structured market intelligence report.
    """
    if not isinstance(corpus_stats, dict):
        msg = f"generate_trends expects CorpusStats dict, got {type(corpus_stats).__name__}"
        logger.error(msg)
        return TrendReport(
            success=False, total_jds=0, top_skills=[], by_tier={},
            by_category={}, category_dominance=[], role_alignments=[], error=msg,
        )

    if not corpus_stats.get("success"):
        msg = f"CorpusStats has success=False: {corpus_stats.get('error')}"
        return TrendReport(
            success=False, total_jds=0, top_skills=[], by_tier={},
            by_category={}, category_dominance=[], role_alignments=[], error=msg,
        )

    raw_skills: list[SkillStat] = corpus_stats.get("skills", [])
    cooccur    = corpus_stats.get("cooccurrence", {})
    total_jds  = corpus_stats.get("total_jds", 0)

    if not raw_skills:
        return TrendReport(
            success=True, total_jds=total_jds, top_skills=[], by_tier={},
            by_category={}, category_dominance=[], role_alignments=[], error=None,
        )

    # ── Build SkillTrend list ─────────────────────────────────────────────────
    trends: list[SkillTrend] = []
    for stat in raw_skills:
        tier      = _get_tier(stat["percentage"])
        co_skills = list(cooccur.get(stat["skill"], {}).keys())[:5]

        trends.append(SkillTrend(
            skill        = stat["skill"],
            category     = stat["category"],
            percentage   = stat["percentage"],
            count        = stat["count"],
            tier         = tier,
            demand_score = stat["demand_score"],
            top_co_skills= co_skills,
        ))

    if top_n:
        trends = trends[:top_n]

    # ── By tier ───────────────────────────────────────────────────────────────
    by_tier: dict[str, list[SkillTrend]] = defaultdict(list)
    for t in trends:
        by_tier[t["tier"]].append(t)

    # ── By category (ordered) ─────────────────────────────────────────────────
    by_cat_raw: dict[str, list[SkillTrend]] = defaultdict(list)
    for t in trends:
        by_cat_raw[t["category"]].append(t)

    by_category: dict[str, list[SkillTrend]] = {}
    for cat in _CATEGORY_ORDER:
        if cat in by_cat_raw:
            by_category[cat] = by_cat_raw[cat]
    # Add any categories not in the order list
    for cat, items in by_cat_raw.items():
        if cat not in by_category:
            by_category[cat] = items

    # ── Category dominance ────────────────────────────────────────────────────
    cat_counts = [(cat, len(items)) for cat, items in by_category.items()]
    cat_counts.sort(key=lambda x: -x[1])

    # ── Role alignments ───────────────────────────────────────────────────────
    corpus_skill_set = {t["skill"] for t in trends}
    profiles_to_score = (
        {role_filter: _ROLE_PROFILES[role_filter]}
        if role_filter and role_filter in _ROLE_PROFILES
        else _ROLE_PROFILES
    )

    alignments: list[RoleAlignment] = []
    for role, profile in profiles_to_score.items():
        must_skills  = profile["must_skills"]
        bonus_skills = profile["bonus_skills"]
        must_cats    = set(profile["must_categories"])
        strong_cats  = set(profile["strong_categories"])

        matched_must  = [s for s in must_skills  if s in corpus_skill_set]
        missing_must  = [s for s in must_skills  if s not in corpus_skill_set]
        matched_bonus = [s for s in bonus_skills if s in corpus_skill_set]

        # Alignment: weighted score
        # must skills = 60% of score, bonus = 20%, category coverage = 20%
        must_score  = (len(matched_must) / len(must_skills) * 60) if must_skills else 0
        bonus_score = (len(matched_bonus) / len(bonus_skills) * 20) if bonus_skills else 0

        present_cats = {t["category"] for t in trends}
        cat_score    = (
            len(must_cats & present_cats) / len(must_cats) * 20
        ) if must_cats else 0

        alignment_pct = round(must_score + bonus_score + cat_score, 1)

        alignments.append(RoleAlignment(
            role          = role,
            alignment_pct = alignment_pct,
            matched_must  = matched_must,
            missing_must  = missing_must,
            matched_bonus = matched_bonus,
        ))

    alignments.sort(key=lambda a: -a["alignment_pct"])

    logger.info(
        "generate_trends: %d skills  top_role=%r (%.1f%%)  tiers=%s",
        len(trends),
        alignments[0]["role"] if alignments else "none",
        alignments[0]["alignment_pct"] if alignments else 0.0,
        {k: len(v) for k, v in by_tier.items()},
    )

    return TrendReport(
        success            = True,
        total_jds          = total_jds,
        top_skills         = trends,
        by_tier            = dict(by_tier),
        by_category        = by_category,
        category_dominance = cat_counts,
        role_alignments    = alignments,
        error              = None,
    )


# ── Skill gap analysis ────────────────────────────────────────────────────────

def skill_gap(
    corpus_stats: CorpusStats,
    user_skills: list[str],
) -> list[GapAnalysis]:
    """
    Compare user's skills against market demand from CorpusStats.

    Parameters
    ----------
    corpus_stats : CorpusStats
        Market demand data from skill_counter.count_corpus().
    user_skills : list[str]
        Canonical skill names the user already has.
        (Run through skill_normalizer first for best results.)

    Returns
    -------
    list[GapAnalysis]
        All market skills with in_user_set flag and priority ranking.
        Sorted: missing CRITICAL skills first, then missing HIGH, etc.
        Skills the user has appear at the bottom.

    Example output
    --------------
        [
          {"skill": "Docker",  "tier": "CRITICAL", "in_user_set": False, "priority": 1},
          {"skill": "AWS",     "tier": "CRITICAL", "in_user_set": False, "priority": 2},
          {"skill": "Python",  "tier": "CRITICAL", "in_user_set": True,  "priority": 9},
          ...
        ]
    """
    user_set = {s.lower() for s in user_skills}
    _tier_rank = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "EMERGING": 3}

    gap_list: list[GapAnalysis] = []
    for stat in corpus_stats.get("skills", []):
        tier       = _get_tier(stat["percentage"])
        in_user    = stat["skill"].lower() in user_set

        gap_list.append(GapAnalysis(
            skill       = stat["skill"],
            category    = stat["category"],
            percentage  = stat["percentage"],
            tier        = tier,
            in_user_set = in_user,
            priority    = 0,   # filled below
        ))

    # Sort: missing skills first by tier, then by percentage desc
    gap_list.sort(key=lambda g: (
        g["in_user_set"],            # False (missing) before True (have)
        _tier_rank[g["tier"]],       # CRITICAL before HIGH before …
        -g["percentage"],
    ))

    # Assign priority ranks
    for i, g in enumerate(gap_list):
        g["priority"] = i + 1

    logger.info(
        "skill_gap: %d market skills  user_has=%d  missing=%d",
        len(gap_list),
        sum(1 for g in gap_list if g["in_user_set"]),
        sum(1 for g in gap_list if not g["in_user_set"]),
    )
    return gap_list


# ── Learning roadmap ──────────────────────────────────────────────────────────

def learning_roadmap(
    corpus_stats: CorpusStats,
    user_skills: list[str],
    max_steps: int = 10,
) -> list[RoadmapStep]:
    """
    Generate an ordered learning roadmap for a user based on market demand
    and co-occurrence with skills they already have.

    Scoring per candidate skill (missing from user set)
    ----------------------------------------------------
        base_score     = demand percentage (0–100)
        cooccur_bonus  = +5 for each skill the user HAS that co-occurs
                         with this candidate (max +25)
        final_score    = base_score + cooccur_bonus

    Parameters
    ----------
    corpus_stats : CorpusStats
        Market data.
    user_skills : list[str]
        Skills the user currently has (canonical names).
    max_steps : int
        Maximum number of roadmap steps to return.

    Returns
    -------
    list[RoadmapStep]
        Ordered learning plan (step 1 = highest priority).

    Example
    -------
        Step 1 — Docker        (CRITICAL 80.0%)  "High demand + pairs with Python, SQL"
        Step 2 — Kubernetes    (CRITICAL 80.0%)  "High demand + pairs with Docker, AWS"
        Step 3 — AWS           (CRITICAL 80.0%)  "High demand + pairs with Python"
        ...
    """
    user_set  = {s.lower() for s in user_skills}
    cooccur   = corpus_stats.get("cooccurrence", {})

    candidates: list[tuple[float, SkillStat]] = []

    for stat in corpus_stats.get("skills", []):
        if stat["skill"].lower() in user_set:
            continue   # user already has this

        # Co-occurrence bonus
        co_partners = cooccur.get(stat["skill"], {})
        bonus = sum(
            5 for partner in co_partners
            if partner.lower() in user_set
        )
        bonus = min(bonus, 25)   # cap at 25

        final_score = stat["percentage"] + bonus
        candidates.append((final_score, stat))

    # Sort by final_score desc
    candidates.sort(key=lambda x: -x[0])

    roadmap: list[RoadmapStep] = []
    for step_num, (score, stat) in enumerate(candidates[:max_steps], start=1):
        tier         = _get_tier(stat["percentage"])
        co_partners  = cooccur.get(stat["skill"], {})
        paired_with  = [p for p in co_partners if p.lower() in user_set][:3]

        if paired_with:
            reason = (
                f"High market demand ({stat['percentage']:.0f}%) "
                f"— pairs with your existing: {', '.join(paired_with)}"
            )
        else:
            reason = (
                f"High market demand ({stat['percentage']:.0f}%) "
                f"— foundational {stat['category'].replace('_', ' ')} skill"
            )

        roadmap.append(RoadmapStep(
            step          = step_num,
            skill         = stat["skill"],
            category      = stat["category"],
            reason        = reason,
            market_demand = stat["percentage"],
            tier          = tier,
        ))

    logger.info(
        "learning_roadmap: %d steps generated for user with %d skills.",
        len(roadmap), len(user_skills),
    )
    return roadmap


# ── Trend snapshot (human-readable summary) ───────────────────────────────────

def trend_snapshot(report: TrendReport) -> str:
    """
    Generate a concise human-readable market summary from a TrendReport.

    Suitable for:
    - Displaying to users in the platform UI
    - Feeding as context into the RAG chatbot
    - Logging / monitoring

    Returns
    -------
    str — multi-line plain-text summary.
    """
    if not report.get("success"):
        return f"Trend report unavailable: {report.get('error')}"

    lines: list[str] = []
    total  = report["total_jds"]
    skills = report["top_skills"]

    lines.append(f"Market Trends — {total} Job Descriptions Analysed")
    lines.append("=" * 55)

    # Tier summary
    for tier in ("CRITICAL", "HIGH", "MODERATE", "EMERGING"):
        tier_skills = report["by_tier"].get(tier, [])
        if tier_skills:
            names = ", ".join(s["skill"] for s in tier_skills[:6])
            suffix = f" +{len(tier_skills)-6} more" if len(tier_skills) > 6 else ""
            lines.append(f"\n[{tier}] {names}{suffix}")

    # Top 10 demand table
    lines.append("\nTop Skills by Demand:")
    lines.append(f"  {'Skill':<28} {'Demand':>7}  Tier")
    lines.append(f"  {'─'*48}")
    for s in skills[:10]:
        lines.append(f"  {s['skill']:<28} {s['percentage']:>6.1f}%  {s['tier']}")

    # Role alignment
    if report["role_alignments"]:
        top_role = report["role_alignments"][0]
        lines.append(
            f"\nBest Role Match: {top_role['role']} "
            f"({top_role['alignment_pct']:.0f}% aligned)"
        )
        if top_role["missing_must"]:
            lines.append(f"  Missing must-haves: {', '.join(top_role['missing_must'])}")

    # Category dominance
    if report["category_dominance"]:
        top_cats = report["category_dominance"][:3]
        cat_str  = " | ".join(
            f"{c.replace('_',' ')} ({n})" for c, n in top_cats
        )
        lines.append(f"\nDominant Categories: {cat_str}")

    return "\n".join(lines)