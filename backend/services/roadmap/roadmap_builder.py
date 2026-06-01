"""
roadmap_builder.py
─────────────────────────────────────────────────────────────────────────────
Main orchestration layer for generating personalised learning roadmaps.

Inputs
------
- Missing skills       (from gap_detector.GapReport)
- Market demand stats  (from job_skills.JobSkillsResult or skill_counter.CorpusStats)
- Current user skills  (canonical names)
- Target job role      (optional string)

Output
------
{
  "target_role":              "Data Analyst",
  "estimated_duration_weeks": 6,
  "roadmap": [
    {
      "week":     1,
      "skill":    "SQL",
      "priority": "High",
      "reason":   "Required in 90% of analysed jobs"
    },
    ...
  ]
}

Design
------
- SkillScheduler   — assigns week numbers respecting prerequisites + demand.
- PriorityClassifier — labels each skill HIGH / MEDIUM / LOW.
- RoadmapBuilder   — orchestrates inputs → RoadmapOutput (public API).
- build_roadmap()  — convenience one-call function.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

# Weeks allocated per skill based on its demand tier
_WEEKS_BY_TIER: dict[str, int] = {
    "HIGH":   2,    # CRITICAL / HIGH demand skills get two weeks
    "MEDIUM": 1,
    "LOW":    1,
}

# Prerequisite graph: skill → must be learned before these dependents
_PREREQUISITES: dict[str, list[str]] = {
    "Python":           ["Scikit-learn", "FastAPI", "Flask", "Django",
                          "NumPy", "Pandas", "XGBoost", "TensorFlow",
                          "PyTorch", "Apache Spark", "SHAP", "LIME"],
    "SQL":              ["PostgreSQL", "MySQL", "SQLite", "dbt", "Snowflake"],
    "Docker":           ["Kubernetes"],
    "JavaScript":       ["React", "Vue.js", "Next.js", "TypeScript"],
    "Machine Learning": ["Deep Learning", "TensorFlow", "PyTorch",
                          "Scikit-learn", "XGBoost"],
    "Linux":            ["Docker", "Kubernetes", "CI/CD"],
    "Git":              ["CI/CD"],
}

PriorityLabel = Literal["High", "Medium", "Low"]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class SkillInput:
    """One missing skill with its market demand context."""
    skill:       str
    demand_pct:  float          # 0–100
    category:    str = "other"

    def __post_init__(self) -> None:
        if not 0.0 <= self.demand_pct <= 100.0:
            raise ValueError(
                f"demand_pct must be 0–100, got {self.demand_pct} for '{self.skill}'"
            )


@dataclass
class RoadmapEntry:
    """One week-slot in the generated roadmap."""
    week:     int
    skill:    str
    priority: PriorityLabel
    reason:   str
    category: str  = "other"
    duration_weeks: int = 1


class RoadmapOutput(TypedDict):
    """Canonical output structure matching the platform spec."""
    target_role:              str
    estimated_duration_weeks: int
    roadmap:                  list[dict]


# ── Priority classifier (Single Responsibility) ───────────────────────────────

class PriorityClassifier:
    """
    Classifies a skill's learning priority based on market demand percentage.

    Thresholds
    ----------
    High   : demand_pct >= 60
    Medium : demand_pct >= 30
    Low    : demand_pct <  30
    """

    _THRESHOLDS: list[tuple[float, PriorityLabel]] = [
        (60.0, "High"),
        (30.0, "Medium"),
        (0.0,  "Low"),
    ]

    def classify(self, demand_pct: float) -> PriorityLabel:
        """
        Return the priority label for a given demand percentage.

        Parameters
        ----------
        demand_pct : float
            Market demand (0–100).

        Returns
        -------
        PriorityLabel
            "High", "Medium", or "Low".
        """
        for threshold, label in self._THRESHOLDS:
            if demand_pct >= threshold:
                return label
        return "Low"

    def weeks_for(self, label: PriorityLabel) -> int:
        """Return the number of weeks allocated for a given priority label."""
        return _WEEKS_BY_TIER.get(label.upper(), 1)


# ── Skill scheduler (Single Responsibility) ───────────────────────────────────

class SkillScheduler:
    """
    Orders skills into a week-by-week schedule respecting:
    1. Market demand (highest demand first).
    2. Prerequisite dependencies (prereqs always scheduled before dependents).
    3. Priority duration (High-priority skills get more weeks).
    """

    def __init__(self, user_skills: list[str]) -> None:
        self._user_skills_lower = {s.lower() for s in user_skills}

    def _has_prereq_gap(
        self, skill: str, scheduled: set[str]
    ) -> list[str]:
        """
        Return prerequisites of `skill` that are neither in user_skills
        nor yet scheduled.
        """
        prereqs_needed = []
        for prereq, dependents in _PREREQUISITES.items():
            if skill in dependents:
                if (
                    prereq.lower() not in self._user_skills_lower
                    and prereq not in scheduled
                ):
                    prereqs_needed.append(prereq)
        return prereqs_needed

    def schedule(
        self,
        skills: list[SkillInput],
        classifier: PriorityClassifier,
    ) -> list[RoadmapEntry]:
        """
        Produce an ordered list of RoadmapEntry items.

        Algorithm
        ---------
        1. Sort by demand_pct descending.
        2. For each skill, check if any prerequisite is unscheduled —
           if so, insert the prerequisite first (recursively).
        3. Assign sequential week numbers based on accumulated duration.

        Parameters
        ----------
        skills     : Ordered list of SkillInput (missing skills).
        classifier : PriorityClassifier instance.

        Returns
        -------
        list[RoadmapEntry]
            Ordered roadmap entries with week assignments.
        """
        # Sort by demand descending; stable sort preserves category grouping
        sorted_skills = sorted(skills, key=lambda s: -s.demand_pct)

        scheduled:   set[str]          = set()
        entries:     list[RoadmapEntry] = []
        skill_index: dict[str, SkillInput] = {s.skill: s for s in skills}

        def _add(si: SkillInput, depth: int = 0) -> None:
            """Recursively schedule prerequisites before the skill itself."""
            if si.skill in scheduled or depth > 10:
                return

            # Insert any unmet prerequisites first
            for prereq_name in self._has_prereq_gap(si.skill, scheduled):
                # If the prereq is also in our missing list, use its demand_pct
                prereq_si = skill_index.get(
                    prereq_name,
                    SkillInput(skill=prereq_name, demand_pct=50.0,
                               category="other"),
                )
                _add(prereq_si, depth + 1)

            priority = classifier.classify(si.demand_pct)
            duration = classifier.weeks_for(priority)
            week_start = (
                entries[-1].week + entries[-1].duration_weeks
                if entries else 1
            )

            reason = (
                f"Required in {si.demand_pct:.0f}% of analysed jobs"
                if si.demand_pct > 0
                else "Recommended prerequisite skill"
            )

            entries.append(RoadmapEntry(
                week           = week_start,
                skill          = si.skill,
                priority       = priority,
                reason         = reason,
                category       = si.category,
                duration_weeks = duration,
            ))
            scheduled.add(si.skill)

        for si in sorted_skills:
            _add(si)

        return entries


# ── RoadmapBuilder — main orchestrator (Open/Closed) ─────────────────────────

class RoadmapBuilder:
    """
    Orchestrates skill inputs into a complete personalised learning roadmap.

    Follows Open/Closed: extend by subclassing or injecting custom
    PriorityClassifier / SkillScheduler without modifying this class.

    Usage
    -----
        builder = RoadmapBuilder()
        output  = builder.build(
            missing_skills = [{"skill": "SQL",    "demand_pct": 90.0},
                               {"skill": "Docker", "demand_pct": 75.0}],
            user_skills    = ["Python", "Pandas"],
            target_role    = "Data Analyst",
        )
    """

    def __init__(
        self,
        classifier: PriorityClassifier | None = None,
    ) -> None:
        self._classifier = classifier or PriorityClassifier()

    def build(
        self,
        missing_skills: list[dict],
        user_skills:    list[str],
        target_role:    str = "Software Engineer",
    ) -> RoadmapOutput:
        """
        Generate a personalised learning roadmap.

        Parameters
        ----------
        missing_skills : list[dict]
            Each dict must have at minimum:
              - "skill"      : str   (canonical skill name)
              - "demand_pct" : float (market demand 0–100)
            Optional:
              - "category"   : str

            Accepts output from gap_detector.GapReport["missing_skills"]
            or job_skills.JobSkillsResult["market_skills"] directly.

        user_skills : list[str]
            Skills the user already has (canonical names).
            Used to avoid re-scheduling skills the user knows and
            to evaluate prerequisite fulfilment.

        target_role : str
            The job role the user is targeting.
            Included in output for display purposes.

        Returns
        -------
        RoadmapOutput
            {
              "target_role":              "Data Analyst",
              "estimated_duration_weeks": 6,
              "roadmap": [
                {"week": 1, "skill": "SQL", "priority": "High",
                 "reason": "Required in 90% of analysed jobs",
                 "duration_weeks": 2},
                ...
              ]
            }

        Raises
        ------
        TypeError  : If missing_skills is not a list.
        ValueError : If any skill entry is missing required fields.
        """
        if not isinstance(missing_skills, list):
            raise TypeError(
                f"missing_skills must be list, got {type(missing_skills).__name__}"
            )
        if not isinstance(user_skills, list):
            raise TypeError(
                f"user_skills must be list, got {type(user_skills).__name__}"
            )

        logger.info(
            "build: target_role=%r  missing=%d  user_skills=%d",
            target_role, len(missing_skills), len(user_skills),
        )

        if not missing_skills:
            logger.info("No missing skills — roadmap is empty.")
            return RoadmapOutput(
                target_role              = target_role,
                estimated_duration_weeks = 0,
                roadmap                  = [],
            )

        # ── Parse inputs into SkillInput dataclasses ──────────────────────
        skill_inputs: list[SkillInput] = []
        user_lower   = {s.lower() for s in user_skills}

        for item in missing_skills:
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict skill entry: %s", type(item))
                continue

            skill = item.get("skill", "").strip()
            if not skill:
                logger.warning("Skipping entry with empty skill name.")
                continue

            # Skip skills the user already has
            if skill.lower() in user_lower:
                logger.debug("Skipping user-present skill: %s", skill)
                continue

            raw_pct = item.get("demand_pct", item.get("demand_percentage", 0.0))
            try:
                demand_pct = float(raw_pct)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid demand_pct %r for %r — defaulting to 0.0", raw_pct, skill
                )
                demand_pct = 0.0

            try:
                skill_inputs.append(SkillInput(
                    skill      = skill,
                    demand_pct = demand_pct,
                    category   = str(item.get("category", "other")),
                ))
            except ValueError as exc:
                logger.warning("Skipping %r: %s", skill, exc)

        if not skill_inputs:
            logger.info("All missing skills already present in user profile.")
            return RoadmapOutput(
                target_role              = target_role,
                estimated_duration_weeks = 0,
                roadmap                  = [],
            )

        # ── Schedule ──────────────────────────────────────────────────────
        scheduler = SkillScheduler(user_skills)
        entries   = scheduler.schedule(skill_inputs, self._classifier)

        total_weeks = (
            entries[-1].week + entries[-1].duration_weeks - 1
            if entries else 0
        )

        roadmap_list = [
            {
                "week":           e.week,
                "skill":          e.skill,
                "priority":       e.priority,
                "reason":         e.reason,
                "category":       e.category,
                "duration_weeks": e.duration_weeks,
            }
            for e in entries
        ]

        logger.info(
            "build complete: %d skills  %d weeks  role=%r",
            len(entries), total_weeks, target_role,
        )

        return RoadmapOutput(
            target_role              = target_role,
            estimated_duration_weeks = total_weeks,
            roadmap                  = roadmap_list,
        )


# ── Public convenience function ───────────────────────────────────────────────

def build_roadmap(
    missing_skills: list[dict],
    user_skills:    list[str],
    target_role:    str = "Software Engineer",
) -> RoadmapOutput:
    """
    Generate a learning roadmap. Convenience wrapper for single-call usage.

    Parameters
    ----------
    missing_skills : list[dict]
        Each dict: {"skill": str, "demand_pct": float, "category": str}
    user_skills    : list[str]   Skills the user already has.
    target_role    : str         Target job role label.

    Returns
    -------
    RoadmapOutput
        {"target_role": ..., "estimated_duration_weeks": ..., "roadmap": [...]}
    """
    return RoadmapBuilder().build(missing_skills, user_skills, target_role)