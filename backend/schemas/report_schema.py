"""
schemas/report_schema.py
─────────────────────────────────────────────────────────────────────────────
Pydantic response models for the AI-Powered Student Career Intelligence
Platform API.

Models (public API)
-------------------
    SkillResponse           — one detected skill from a resume
    MarketSkillResponse     — one skill with its market demand statistics
    MissingSkillResponse    — one gap skill with priority score + explanation
    GapAnalysisResponse     — full gap detection result
    RoadmapStepResponse     — one week-slot in a learning roadmap
    RoadmapResponse         — full generated roadmap
    CareerReportResponse    — top-level unified report (all sections combined)

Design principles
-----------------
- Every field has a description for OpenAPI documentation auto-generation.
- Validators enforce business invariants (score ranges, non-empty strings,
  valid tier/priority/phase labels) at the schema layer — not in route handlers.
- Optional fields with sensible defaults keep the API backwards-compatible
  as the pipeline evolves.
- All models use `model_config = ConfigDict(from_attributes=True)` so they
  can be constructed from ORM objects or TypedDicts without `.model_validate`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal


# ── Shared literals ───────────────────────────────────────────────────────────

DemandTier     = Literal["CRITICAL", "HIGH", "MODERATE", "EMERGING"]
SkillSource    = Literal["explicit", "inferred", "education"]
PriorityLabel  = Literal["High", "Medium", "Low"]
LearningPhase  = Literal[
    "Phase 1 — Foundation",
    "Phase 2 — Core",
    "Phase 3 — Advanced",
]


# ══════════════════════════════════════════════════════════════════════════════
# SkillResponse
# ══════════════════════════════════════════════════════════════════════════════

class SkillResponse(BaseModel):
    """
    One skill detected from a user's resume.

    Produced by resume_skills.extract_resume_skills() and
    skill_extractor.extract_skills().
    """

    model_config = ConfigDict(from_attributes=True)

    skill: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Canonical skill name as resolved by the skill dictionary.",
        examples=["Python", "Scikit-learn", "Apache Spark"],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Extraction confidence in [0.0, 1.0]. "
            "Explicit Skills-section entries ≥ 0.90; "
            "inferred mentions ≥ 0.40."
        ),
        examples=[1.0, 0.85, 0.60],
    )
    source: SkillSource = Field(
        ...,
        description=(
            "Where the skill was found in the resume. "
            "'explicit' = Skills section, "
            "'inferred' = experience/projects body, "
            "'education' = coursework."
        ),
        examples=["explicit"],
    )
    category: str = Field(
        default="other",
        description="Skill category from the platform skill dictionary.",
        examples=["programming_language", "machine_learning", "devops"],
    )

    @field_validator("skill")
    @classmethod
    def skill_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("skill must not be blank or whitespace-only.")
        return v.strip()

    @field_validator("category")
    @classmethod
    def category_lowercase(cls, v: str) -> str:
        return v.lower().strip() or "other"


# ══════════════════════════════════════════════════════════════════════════════
# MarketSkillResponse
# ══════════════════════════════════════════════════════════════════════════════

class MarketSkillResponse(BaseModel):
    """
    One skill extracted from the job market corpus with demand statistics.

    Produced by job_skills.aggregate_job_skills().
    """

    model_config = ConfigDict(from_attributes=True)

    skill: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Canonical skill name.",
        examples=["Docker", "AWS", "SQL"],
    )
    demand_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description=(
            "Percentage of analysed job postings that require this skill. "
            "100.0 means every job in the corpus mentions it."
        ),
        examples=[100.0, 78.5, 42.0],
    )
    count: int = Field(
        ...,
        ge=0,
        description="Raw number of job postings that mention this skill.",
        examples=[50, 39, 21],
    )
    category: str = Field(
        default="other",
        description="Skill category.",
        examples=["database", "cloud", "devops"],
    )
    tier: DemandTier = Field(
        default="EMERGING",
        description=(
            "Demand tier derived from demand_pct. "
            "CRITICAL ≥ 60% | HIGH 40–59% | MODERATE 20–39% | EMERGING < 20%"
        ),
        examples=["CRITICAL", "HIGH"],
    )

    @field_validator("demand_pct")
    @classmethod
    def round_demand_pct(cls, v: float) -> float:
        return round(v, 1)


# ══════════════════════════════════════════════════════════════════════════════
# MissingSkillResponse
# ══════════════════════════════════════════════════════════════════════════════

class MissingSkillResponse(BaseModel):
    """
    One skill that is demanded by the market but absent from the user's resume.

    Produced by gap_detector.detect_gaps() and priority_ranker.rank_gaps().
    """

    model_config = ConfigDict(from_attributes=True)

    skill: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Canonical skill name.",
        examples=["Kubernetes", "AWS", "TensorFlow"],
    )
    category: str = Field(
        default="other",
        description="Skill category.",
    )
    demand_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Market demand percentage for this skill.",
        examples=[80.0, 60.0, 25.0],
    )
    tier: DemandTier = Field(
        ...,
        description="Demand tier: CRITICAL / HIGH / MODERATE / EMERGING.",
        examples=["CRITICAL"],
    )
    priority_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Composite gap priority score [0.0 – 1.0] combining market demand, "
            "category importance, and how much of the category the user lacks. "
            "Higher = learn sooner."
        ),
        examples=[0.91, 0.78, 0.55],
    )
    rank: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Final priority rank after prerequisite and quick-win signals. "
            "1 = learn first. Populated by priority_ranker."
        ),
        examples=[1, 2, 5],
    )
    phase: LearningPhase | None = Field(
        default=None,
        description="Learning phase assigned by priority_ranker.",
        examples=["Phase 1 — Foundation"],
    )
    is_partial: bool = Field(
        default=False,
        description=(
            "True when the user has a related skill in the same category "
            "(e.g. has TensorFlow, market wants PyTorch). "
            "Partial gaps have a reduced priority score."
        ),
    )
    partial_match: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Name of the resume skill that partially covers this gap. "
            "None when is_partial is False."
        ),
        examples=["TensorFlow", "Docker"],
    )
    is_prerequisite: bool = Field(
        default=False,
        description=(
            "True when learning this skill first unlocks faster progress "
            "on other missing skills (e.g. Docker before Kubernetes)."
        ),
    )
    quick_win: bool = Field(
        default=False,
        description=(
            "True for high-demand skills with a relatively low learning curve. "
            "Prioritised for early momentum."
        ),
    )
    explanation: str = Field(
        ...,
        min_length=10,
        description=(
            "Human-readable explanation of why this skill is prioritised. "
            "Suitable for display in the platform UI or RAG chatbot context."
        ),
        examples=["Docker is required in 80% of roles. No devops skills found in your resume."],
    )

    @model_validator(mode="after")
    def partial_match_requires_is_partial(self) -> "MissingSkillResponse":
        if self.partial_match and not self.is_partial:
            raise ValueError(
                "partial_match may only be set when is_partial is True."
            )
        if self.is_partial and self.partial_match is None:
            raise ValueError(
                "partial_match must be provided when is_partial is True."
            )
        return self


# ══════════════════════════════════════════════════════════════════════════════
# GapAnalysisResponse
# ══════════════════════════════════════════════════════════════════════════════

class GapAnalysisSummary(BaseModel):
    """Aggregate metrics from the gap detection stage."""

    model_config = ConfigDict(from_attributes=True)

    total_market_skills:  int   = Field(..., ge=0, description="Total market skills analysed.")
    total_present_skills: int   = Field(..., ge=0, description="Market skills the user already has.")
    total_missing_skills: int   = Field(..., ge=0, description="Market skills absent from the resume.")
    total_extra_skills:   int   = Field(..., ge=0, description="Resume skills not in market demand.")
    coverage_pct:         float = Field(
        ..., ge=0.0, le=100.0,
        description="Percentage of market skills covered by the resume.",
        examples=[62.5],
    )
    placement_score: float = Field(
        ..., ge=0.0, le=100.0,
        description=(
            "Weighted placement readiness score (0–100). "
            "CRITICAL gaps penalise more than EMERGING gaps."
        ),
        examples=[68.0],
    )
    top_missing_skill: str | None = Field(
        default=None,
        description="Highest-priority missing skill (rank 1).",
        examples=["AWS"],
    )


class GapAnalysisResponse(BaseModel):
    """
    Full result of the skill gap detection and priority ranking stages.

    Produced by gap_detector.detect_gaps() + priority_ranker.rank_gaps().
    """

    model_config = ConfigDict(from_attributes=True)

    summary:         GapAnalysisSummary        = Field(description="Aggregate gap metrics.")
    missing_skills:  list[MissingSkillResponse] = Field(
        default_factory=list,
        description="Prioritised list of missing skills (rank 1 = learn first).",
    )
    present_skills:  list[SkillResponse]        = Field(
        default_factory=list,
        description="Market-demanded skills the user already has.",
    )
    extra_skills:    list[str]                  = Field(
        default_factory=list,
        description=(
            "Skills on the resume that are not in market demand for the target role. "
            "May indicate niche expertise or transferable skills."
        ),
        examples=[["SHAP", "BG/NBD", "Streamlit"]],
    )
    by_category: dict[str, dict] = Field(
        default_factory=dict,
        description=(
            "Per-category coverage breakdown. "
            "Keys are category names; values include required_count, "
            "present_count, missing_count, and coverage_pct."
        ),
    )

    @field_validator("missing_skills")
    @classmethod
    def missing_sorted_by_priority(
        cls, v: list[MissingSkillResponse]
    ) -> list[MissingSkillResponse]:
        """Ensure missing_skills is ordered by priority_score descending."""
        return sorted(v, key=lambda s: (
            s.rank if s.rank is not None else 999,
            -s.priority_score,
        ))


# ══════════════════════════════════════════════════════════════════════════════
# RoadmapStepResponse / RoadmapResponse
# ══════════════════════════════════════════════════════════════════════════════

class RoadmapStepResponse(BaseModel):
    """One week-slot in the personalised learning roadmap."""

    model_config = ConfigDict(from_attributes=True)

    week: int = Field(
        ...,
        ge=1,
        description="Calendar week number in the roadmap (1-indexed, no gaps).",
        examples=[1, 3, 5],
    )
    skill: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Skill to study during this week.",
        examples=["SQL", "Docker", "AWS"],
    )
    priority: PriorityLabel = Field(
        ...,
        description="Learning priority: High / Medium / Low.",
        examples=["High"],
    )
    reason: str = Field(
        ...,
        min_length=5,
        description="One-sentence justification for why this skill is scheduled here.",
        examples=["Required in 90% of analysed job postings."],
    )
    category: str = Field(
        default="other",
        description="Skill category.",
        examples=["database", "devops", "cloud"],
    )
    duration_weeks: int = Field(
        ...,
        ge=1,
        le=8,
        description=(
            "Number of weeks allocated to this skill. "
            "High-priority skills receive 2 weeks; others receive 1."
        ),
        examples=[2, 1],
    )
    milestone: str | None = Field(
        default=None,
        description=(
            "Portfolio milestone to complete by the end of this skill block. "
            "Set only on the final week of a multi-week skill block."
        ),
        examples=["Build a working REST API using FastAPI from scratch."],
    )
    daily_hours: float | None = Field(
        default=None,
        ge=0.0,
        le=12.0,
        description="Estimated daily study hours for this week.",
        examples=[2.5, 2.0, 1.5],
    )


class RoadmapResponse(BaseModel):
    """
    Complete personalised learning roadmap.

    Produced by roadmap_builder.build_roadmap() and optionally enriched
    by timeline_generator and course_finder.
    """

    model_config = ConfigDict(from_attributes=True)

    target_role: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Job role this roadmap is designed for.",
        examples=["Data Engineer", "ML Engineer", "Backend Developer"],
    )
    estimated_duration_weeks: int = Field(
        ...,
        ge=0,
        description="Total calendar weeks from start to roadmap completion.",
        examples=[8, 12, 6],
    )
    steps: list[RoadmapStepResponse] = Field(
        default_factory=list,
        description="Ordered week-by-week learning plan.",
    )
    phase_summary: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Skills grouped by learning phase. "
            "Keys: 'Phase 1 — Foundation', 'Phase 2 — Core', 'Phase 3 — Advanced'."
        ),
        examples=[{"Phase 1 — Foundation": ["SQL", "Docker"], "Phase 2 — Core": ["AWS"]}],
    )

    @field_validator("steps")
    @classmethod
    def steps_sequential(cls, v: list[RoadmapStepResponse]) -> list[RoadmapStepResponse]:
        """Validate that week numbers are sequential with no gaps."""
        if len(v) <= 1:
            return v
        for i in range(1, len(v)):
            expected = v[i - 1].week + v[i - 1].duration_weeks
            if v[i].week != expected:
                raise ValueError(
                    f"Week gap detected between step {i} (week {v[i-1].week}) "
                    f"and step {i+1} (week {v[i].week}). Expected week {expected}."
                )
        return v

    @field_validator("estimated_duration_weeks")
    @classmethod
    def duration_matches_steps(cls, v: int) -> int:
        # Cross-field validation via model_validator below
        return v

    @model_validator(mode="after")
    def duration_consistent_with_steps(self) -> "RoadmapResponse":
        if not self.steps:
            return self
        last = self.steps[-1]
        computed = last.week + last.duration_weeks - 1
        if self.estimated_duration_weeks != computed:
            raise ValueError(
                f"estimated_duration_weeks ({self.estimated_duration_weeks}) "
                f"does not match final step end week ({computed})."
            )
        return self


# ══════════════════════════════════════════════════════════════════════════════
# CareerReportResponse
# ══════════════════════════════════════════════════════════════════════════════

class CareerReportMeta(BaseModel):
    """Metadata about the report generation process."""

    model_config = ConfigDict(from_attributes=True)

    candidate_name:  str         = Field(default="", description="Name extracted from resume.")
    target_role:     str         = Field(...,  description="Target job role for the analysis.")
    total_jobs_analysed: int     = Field(default=0, ge=0, description="Job postings in the market corpus.")
    processing_ms:   int | None  = Field(default=None, ge=0, description="Server-side processing time (ms).")


class CareerReportResponse(BaseModel):
    """
    Top-level unified career intelligence report.

    This is the canonical output of the platform pipeline:

        Resume → parse → skill extraction
               → job analysis → gap detection → roadmap generation
               → CareerReportResponse

    All four sub-reports are nested here for a single API response.
    """

    model_config = ConfigDict(from_attributes=True)

    meta: CareerReportMeta = Field(
        description="Report metadata: candidate name, role, corpus size.",
    )
    detected_skills: list[SkillResponse] = Field(
        default_factory=list,
        description="Skills extracted from the uploaded resume.",
    )
    market_skills: list[MarketSkillResponse] = Field(
        default_factory=list,
        description="Skills demanded by the market, sorted by demand_pct descending.",
    )
    gap_analysis: GapAnalysisResponse = Field(
        description="Full gap analysis: missing skills, coverage, placement score.",
    )
    roadmap: RoadmapResponse = Field(
        description="Personalised week-by-week learning roadmap.",
    )

    @field_validator("market_skills")
    @classmethod
    def market_sorted_by_demand(
        cls, v: list[MarketSkillResponse]
    ) -> list[MarketSkillResponse]:
        """Enforce market_skills are sorted by demand_pct descending."""
        return sorted(v, key=lambda s: -s.demand_pct)

    @field_validator("detected_skills")
    @classmethod
    def detected_sorted_by_confidence(
        cls, v: list[SkillResponse]
    ) -> list[SkillResponse]:
        """Enforce detected_skills are sorted by confidence descending."""
        return sorted(v, key=lambda s: -s.confidence)

    @model_validator(mode="after")
    def gap_skills_subset_of_market(self) -> "CareerReportResponse":
        """
        Soft-validate: every missing skill should exist in market_skills.
        Logs a warning rather than raising to avoid breaking the API
        when pipeline data is partially stale.
        """
        import logging
        _log = logging.getLogger(__name__)
        market_names = {ms.skill.lower() for ms in self.market_skills}
        for ms in self.gap_analysis.missing_skills:
            if ms.skill.lower() not in market_names:
                _log.warning(
                    "Missing skill %r not found in market_skills — "
                    "data may be from different pipeline runs.",
                    ms.skill,
                )
        return self