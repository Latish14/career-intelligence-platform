"""
timeline_generator.py
─────────────────────────────────────────────────────────────────────────────
Converts a RoadmapOutput (from roadmap_builder.py) into a detailed,
week-by-week study timeline with milestones, daily hour estimates,
and phase labels.

Pipeline position
-----------------
    roadmap_builder.py   → RoadmapOutput
         ↓
    timeline_generator.py  ← YOU ARE HERE
         ↓  TimelineOutput
    course_finder.py     ← attaches course recommendations per week

Responsibilities
----------------
1. Accept a RoadmapOutput dict.
2. Expand each roadmap entry into one TimelineWeek per week slot.
3. Attach a milestone to the final week of each skill block.
4. Assign a study phase label (Foundation / Core / Advanced).
5. Estimate daily study hours based on priority tier.
6. Generate a concise summary string per week.
7. Return a structured TimelineOutput.

Output shape
------------
{
  "target_role":    "Data Analyst",
  "total_weeks":    7,
  "phases": {
    "Foundation": ["SQL", "Docker"],
    "Core":       ["AWS"],
    "Advanced":   []
  },
  "timeline": [
    {
      "week":            1,
      "skill":           "SQL",
      "phase":           "Foundation",
      "topic":           "SQL — Week 1 of 2",
      "milestone":       None,
      "daily_hours":     2.5,
      "is_milestone_week": False,
      "summary":         "Begin SQL. Focus: core concepts and hands-on practice."
    },
    {
      "week":            2,
      "skill":           "SQL",
      "phase":           "Foundation",
      "topic":           "SQL — Week 2 of 2",
      "milestone":       "Complete SQL fundamentals and build a portfolio project.",
      "daily_hours":     2.5,
      "is_milestone_week": True,
      "summary":         "Finish SQL. Milestone: Complete SQL fundamentals and build a portfolio project."
    },
    ...
  ]
}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TypedDict

from services.roadmap.roadmap_builder import RoadmapOutput

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

# Daily study hours by priority
_DAILY_HOURS: dict[str, float] = {
    "High":   2.5,
    "Medium": 2.0,
    "Low":    1.5,
}

# Phase assignment by priority
_PRIORITY_TO_PHASE: dict[str, str] = {
    "High":   "Foundation",
    "Medium": "Core",
    "Low":    "Advanced",
}

# Milestone templates per skill category
_MILESTONE_TEMPLATES: dict[str, str] = {
    "database":           "Complete {skill} fundamentals and write 5 production-quality queries.",
    "programming_language": "Build a working project using {skill} from scratch.",
    "machine_learning":   "Train, evaluate, and explain a {skill} model on real data.",
    "devops":             "Containerise and deploy a personal project using {skill}.",
    "cloud":              "Deploy a cloud-hosted application using {skill} services.",
    "data_science":       "Complete an end-to-end EDA notebook using {skill}.",
    "data_engineering":   "Build and run a data pipeline using {skill}.",
    "web_backend":        "Build and document a REST API using {skill}.",
    "web_frontend":       "Build and deploy a responsive UI component using {skill}.",
    "nlp":                "Fine-tune or apply a {skill} model on a text dataset.",
    "other":              "Complete {skill} fundamentals and build a portfolio project.",
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TimelineWeek:
    """One week slot in the expanded timeline."""
    week:              int
    skill:             str
    phase:             str
    topic:             str
    milestone:         str | None
    daily_hours:       float
    is_milestone_week: bool
    summary:           str
    category:          str = "other"
    priority:          str = "Medium"


class TimelineOutput(TypedDict):
    """Full structured output returned by generate_timeline()."""
    target_role:  str
    total_weeks:  int
    phases:       dict[str, list[str]]     # phase → [skill names]
    timeline:     list[dict]               # list of TimelineWeek as dicts


# ── Milestone builder (Single Responsibility) ─────────────────────────────────

class MilestoneBuilder:
    """Generates milestone strings for the final week of each skill block."""

    def build(self, skill: str, category: str) -> str:
        """
        Build a milestone statement for completing a skill.

        Parameters
        ----------
        skill    : Canonical skill name.
        category : Skill category from skill_dictionary.

        Returns
        -------
        str — human-readable milestone statement.
        """
        template = _MILESTONE_TEMPLATES.get(category, _MILESTONE_TEMPLATES["other"])
        return template.format(skill=skill)


# ── Week expander (Single Responsibility) ─────────────────────────────────────

class WeekExpander:
    """
    Expands a single roadmap entry (which may span multiple weeks)
    into one TimelineWeek per calendar week.
    """

    def __init__(self, milestone_builder: MilestoneBuilder | None = None) -> None:
        self._milestone_builder = milestone_builder or MilestoneBuilder()

    def expand(self, entry: dict) -> list[TimelineWeek]:
        """
        Expand one roadmap entry into per-week TimelineWeek records.

        Parameters
        ----------
        entry : dict
            One item from RoadmapOutput["roadmap"]. Expected keys:
            week, skill, priority, reason, category, duration_weeks.

        Returns
        -------
        list[TimelineWeek]
            One record per week in the entry's duration_weeks span.
        """
        skill          = entry.get("skill", "Unknown")
        start_week     = int(entry.get("week", 1))
        duration       = max(1, int(entry.get("duration_weeks", 1)))
        priority       = entry.get("priority", "Medium")
        category       = entry.get("category", "other")
        phase          = _PRIORITY_TO_PHASE.get(priority, "Core")
        daily_hours    = _DAILY_HOURS.get(priority, 2.0)
        milestone_text = self._milestone_builder.build(skill, category)

        weeks: list[TimelineWeek] = []
        for offset in range(duration):
            week_num          = start_week + offset
            is_last           = offset == duration - 1
            week_label        = f"Week {offset + 1} of {duration}"
            topic             = f"{skill} — {week_label}" if duration > 1 else skill

            if is_last:
                milestone = milestone_text
                summary   = f"Finish {skill}. Milestone: {milestone_text}"
            else:
                milestone = None
                if offset == 0:
                    summary = (
                        f"Begin {skill}. "
                        f"Focus: core concepts and hands-on practice."
                    )
                else:
                    summary = (
                        f"Continue {skill}. "
                        f"Focus: applied projects and deeper understanding."
                    )

            weeks.append(TimelineWeek(
                week              = week_num,
                skill             = skill,
                phase             = phase,
                topic             = topic,
                milestone         = milestone,
                daily_hours       = daily_hours,
                is_milestone_week = is_last,
                summary           = summary,
                category          = category,
                priority          = priority,
            ))

        return weeks


# ── TimelineGenerator — orchestrator (Open/Closed) ───────────────────────────

class TimelineGenerator:
    """
    Converts a RoadmapOutput into a detailed week-by-week timeline.

    Inject custom MilestoneBuilder or WeekExpander for specialised behaviour
    without modifying this class (Open/Closed principle).
    """

    def __init__(self, expander: WeekExpander | None = None) -> None:
        self._expander = expander or WeekExpander()

    def generate(self, roadmap: RoadmapOutput) -> TimelineOutput:
        """
        Generate a detailed timeline from a roadmap.

        Parameters
        ----------
        roadmap : RoadmapOutput
            Output of roadmap_builder.build_roadmap().

        Returns
        -------
        TimelineOutput
            Structured timeline with per-week detail, phases, and milestones.

        Raises
        ------
        TypeError  : If roadmap is not a dict.
        ValueError : If roadmap["roadmap"] is not a list.
        """
        if not isinstance(roadmap, dict):
            raise TypeError(
                f"roadmap must be a dict, got {type(roadmap).__name__}"
            )

        entries = roadmap.get("roadmap", [])
        if not isinstance(entries, list):
            raise ValueError("roadmap['roadmap'] must be a list.")

        target_role = roadmap.get("target_role", "Unknown Role")
        logger.info(
            "generate: target_role=%r  entries=%d",
            target_role, len(entries),
        )

        if not entries:
            return TimelineOutput(
                target_role = target_role,
                total_weeks = 0,
                phases      = {},
                timeline    = [],
            )

        # ── Expand each entry into per-week records ───────────────────────
        all_weeks: list[TimelineWeek] = []
        for entry in entries:
            if not isinstance(entry, dict):
                logger.warning("Skipping non-dict roadmap entry: %s", type(entry))
                continue
            try:
                all_weeks.extend(self._expander.expand(entry))
            except Exception as exc:          # noqa: BLE001
                logger.error("Failed to expand entry %r: %s", entry, exc)

        total_weeks = max((w.week for w in all_weeks), default=0)

        # ── Build phase summary ───────────────────────────────────────────
        phases: dict[str, list[str]] = {}
        seen_skills: set[str] = set()
        for w in all_weeks:
            if w.skill not in seen_skills:
                phases.setdefault(w.phase, []).append(w.skill)
                seen_skills.add(w.skill)

        # ── Serialise to dicts ────────────────────────────────────────────
        timeline_dicts = [
            {
                "week":              tw.week,
                "skill":             tw.skill,
                "phase":             tw.phase,
                "topic":             tw.topic,
                "milestone":         tw.milestone,
                "daily_hours":       tw.daily_hours,
                "is_milestone_week": tw.is_milestone_week,
                "summary":           tw.summary,
                "category":          tw.category,
                "priority":          tw.priority,
            }
            for tw in all_weeks
        ]

        logger.info(
            "generate complete: %d weeks  phases=%s",
            total_weeks, list(phases.keys()),
        )

        return TimelineOutput(
            target_role = target_role,
            total_weeks = total_weeks,
            phases      = phases,
            timeline    = timeline_dicts,
        )


# ── Public convenience function ───────────────────────────────────────────────

def generate_timeline(roadmap: RoadmapOutput) -> TimelineOutput:
    """
    Generate a week-by-week timeline from a RoadmapOutput.

    Convenience wrapper for single-call usage.

    Parameters
    ----------
    roadmap : RoadmapOutput
        Output of roadmap_builder.build_roadmap().

    Returns
    -------
    TimelineOutput
        Full timeline with phases, milestones, and daily hour estimates.
    """
    return TimelineGenerator().generate(roadmap)