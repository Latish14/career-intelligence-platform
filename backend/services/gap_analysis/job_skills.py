"""
job_skills.py
─────────────────────────────────────────────────────────────────────────────
Aggregates, normalises, and calculates demand statistics for skills
extracted from job descriptions. Produces MarketSkill records ready
for gap_detector.detect_gaps().

Responsibilities
----------------
1. Accept raw skill lists from multiple job postings.
2. Normalise skill names via skill_engine.ALIAS_INDEX.
3. Count per-skill occurrences (binary per job — not raw mention count).
4. Calculate demand percentage = count / total_jobs × 100.
5. Deduplicate canonicals.
6. Sort by demand percentage descending.
7. Return structured output for gap_detector.py.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TypedDict

from services.skill_engine.skill_dictionary import ALIAS_INDEX, get_entry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Input type ────────────────────────────────────────────────────────────────

class JobRecord(TypedDict):
    job_id: int | str
    skills: list[str]


# ── Output types ──────────────────────────────────────────────────────────────

class SkillDemand(TypedDict):
    count:             int
    demand_percentage: float


class JobSkillsResult(TypedDict):
    skills:       dict[str, SkillDemand]   # canonical → {count, demand_percentage}
    market_skills: list[dict]              # list[MarketSkill] for gap_detector
    total_jobs:   int
    total_unique_skills: int
    success:      bool
    error:        str | None


# ── Internal dataclass ────────────────────────────────────────────────────────

@dataclass
class _SkillAccumulator:
    """Tracks per-skill state during aggregation."""
    canonical:  str
    category:   str  = "other"
    base_weight: float = 0.85
    job_ids:    set[str] = field(default_factory=set)

    @property
    def count(self) -> int:
        return len(self.job_ids)

    def demand_pct(self, total_jobs: int) -> float:
        if total_jobs == 0:
            return 0.0
        return round(self.count / total_jobs * 100, 1)


# ── Normaliser (Single Responsibility) ───────────────────────────────────────

class SkillNormaliser:
    """Resolves raw skill strings to canonical names via ALIAS_INDEX."""

    def resolve(self, raw: str) -> str | None:
        """
        Resolve a raw skill string to its canonical form.

        Parameters
        ----------
        raw : str
            Raw skill name — may be an alias, abbreviation, or canonical.

        Returns
        -------
        str | None
            Canonical skill name, or None if unrecognised.
        """
        key = raw.strip().lower()
        if not key:
            return None
        return ALIAS_INDEX.get(key)

    def resolve_many(self, raws: list[str]) -> list[str]:
        """
        Resolve a list of raw skill strings, silently dropping unknowns.

        Parameters
        ----------
        raws : list[str]
            Raw skill names from one job posting.

        Returns
        -------
        list[str]
            Deduplicated list of canonical names recognised in the dictionary.
        """
        seen:   set[str] = set()
        result: list[str] = []
        for raw in raws:
            canonical = self.resolve(raw)
            if canonical and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
        return result


# ── Aggregator (Single Responsibility) ───────────────────────────────────────

class JobSkillAggregator:
    """
    Aggregates normalised skills across multiple job records.
    Counts occurrences (binary per job) and calculates demand percentages.
    """

    def __init__(self, normaliser: SkillNormaliser | None = None) -> None:
        self._normaliser = normaliser or SkillNormaliser()

    def aggregate(self, job_records: list[JobRecord]) -> JobSkillsResult:
        """
        Aggregate skills from a list of job records.

        Each skill is counted once per job (binary frequency), preventing
        jobs that mention a skill multiple times from inflating demand.

        Parameters
        ----------
        job_records : list[JobRecord]
            List of dicts with 'job_id' and 'skills' keys.
            Example: [{"job_id": 1, "skills": ["Python", "SQL"]}]

        Returns
        -------
        JobSkillsResult
            {
              "skills": {
                "Python": {"count": 2, "demand_percentage": 100.0},
                "SQL":    {"count": 2, "demand_percentage": 100.0},
                ...
              },
              "market_skills": [MarketSkill dicts for gap_detector],
              "total_jobs":    2,
              "total_unique_skills": 4,
              "success":       True,
              "error":         None
            }
        """
        if not isinstance(job_records, list):
            msg = f"job_records must be list, got {type(job_records).__name__}"
            logger.error(msg)
            return self._error_result(msg)

        if not job_records:
            logger.info("aggregate: empty job_records list.")
            return JobSkillsResult(
                skills={}, market_skills=[], total_jobs=0,
                total_unique_skills=0, success=True, error=None,
            )

        logger.info("aggregate: processing %d job records.", len(job_records))

        accumulators: dict[str, _SkillAccumulator] = {}
        valid_jobs = 0

        for record in job_records:
            if not isinstance(record, dict):
                logger.warning("Skipping non-dict record: %s", type(record))
                continue

            job_id = str(record.get("job_id", ""))
            raw_skills = record.get("skills", [])

            if not isinstance(raw_skills, list):
                logger.warning("job_id=%s: 'skills' is not a list — skipping.", job_id)
                continue

            valid_jobs += 1
            canonicals = self._normaliser.resolve_many(raw_skills)

            for canonical in canonicals:
                if canonical not in accumulators:
                    entry = get_entry(canonical)
                    accumulators[canonical] = _SkillAccumulator(
                        canonical   = canonical,
                        category    = entry["category"]    if entry else "other",
                        base_weight = entry["weight"]      if entry else 0.85,
                    )
                accumulators[canonical].job_ids.add(job_id)

        if valid_jobs == 0:
            msg = "No valid job records found in input."
            logger.error(msg)
            return self._error_result(msg)

        # ── Build demand dict (sorted by demand_pct desc) ──────────────────
        sorted_accs = sorted(
            accumulators.values(),
            key=lambda a: (-a.demand_pct(valid_jobs), a.canonical),
        )

        skills_dict: dict[str, SkillDemand] = {
            acc.canonical: SkillDemand(
                count             = acc.count,
                demand_percentage = acc.demand_pct(valid_jobs),
            )
            for acc in sorted_accs
        }

        # ── Build MarketSkill list for gap_detector ────────────────────────
        market_skills = [
            {
                "skill":       acc.canonical,
                "demand_pct":  acc.demand_pct(valid_jobs),
                "category":    acc.category,
                "base_weight": acc.base_weight,
            }
            for acc in sorted_accs
        ]

        logger.info(
            "aggregate complete: %d jobs  %d unique skills  "
            "top=%r (%.1f%%)",
            valid_jobs, len(skills_dict),
            sorted_accs[0].canonical if sorted_accs else "none",
            sorted_accs[0].demand_pct(valid_jobs) if sorted_accs else 0.0,
        )

        return JobSkillsResult(
            skills              = skills_dict,
            market_skills       = market_skills,
            total_jobs          = valid_jobs,
            total_unique_skills = len(skills_dict),
            success             = True,
            error               = None,
        )

    @staticmethod
    def _error_result(message: str) -> JobSkillsResult:
        return JobSkillsResult(
            skills={}, market_skills=[], total_jobs=0,
            total_unique_skills=0, success=False, error=message,
        )


# ── Public convenience function ───────────────────────────────────────────────

def aggregate_job_skills(job_records: list[JobRecord]) -> JobSkillsResult:
    """
    Aggregate and calculate demand statistics for skills across job postings.

    Convenience wrapper around JobSkillAggregator for single-call usage.

    Parameters
    ----------
    job_records : list[JobRecord]
        Raw job skill data. Each record must have 'job_id' and 'skills'.

    Returns
    -------
    JobSkillsResult
        Structured demand statistics and MarketSkill list.

    Example
    -------
    >>> records = [
    ...     {"job_id": 1, "skills": ["Python", "SQL", "Docker"]},
    ...     {"job_id": 2, "skills": ["Python", "AWS", "SQL"]},
    ... ]
    >>> result = aggregate_job_skills(records)
    >>> result["skills"]
    {
        "Python": {"count": 2, "demand_percentage": 100.0},
        "SQL":    {"count": 2, "demand_percentage": 100.0},
        "Docker": {"count": 1, "demand_percentage": 50.0},
        "AWS":    {"count": 1, "demand_percentage": 50.0},
    }
    """
    return JobSkillAggregator().aggregate(job_records)