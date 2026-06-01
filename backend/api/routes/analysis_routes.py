"""
api/routes/analysis_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI router exposing skill gap and market analysis endpoints.

Endpoints
---------
    POST /analysis/generate
        Accept a list of job records + user skills.
        Run the full analysis pipeline (market aggregation → gap detection
        → priority ranking → roadmap generation).
        Return a structured AnalysisReport.

    GET  /analysis/status
        Return the health and configuration status of the analysis engine.
        Useful for frontend polling and ops monitoring.

Design
------
- APIRouter with prefix="/analysis" and tag="Analysis"
- Pydantic request / response models with field-level documentation
- Dependency injection for pipeline config (overridable in tests)
- All exceptions surfaced as typed HTTP errors
- No database code — stateless per request
"""

from __future__ import annotations

import logging
import os
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from services.gap_analysis.job_skills     import aggregate_job_skills
from services.gap_analysis.gap_detector   import detect_gaps, ResumeSkill, MarketSkill
from services.gap_analysis.priority_ranking import rank_gaps
from services.roadmap.roadmap_builder import build_roadmap

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ── Constants ─────────────────────────────────────────────────────────────────

_ENGINE_VERSION  = "1.0.0"
_MAX_JOB_RECORDS = 500
_MAX_USER_SKILLS = 200


# ══════════════════════════════════════════════════════════════════════════════
# Request models
# ══════════════════════════════════════════════════════════════════════════════

class JobRecordRequest(BaseModel):
    """One job posting with its required skills."""

    job_id: str | int = Field(..., description="Unique job identifier")
    skills: list[str] = Field(
        ...,
        min_length=1,
        description="Raw skill names required for this job (aliases resolved automatically)",
    )

    @field_validator("skills")
    @classmethod
    def skills_non_empty_strings(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s.strip()]
        if not cleaned:
            raise ValueError("skills list must contain at least one non-empty string.")
        return cleaned


class AnalysisRequest(BaseModel):
    """Request body for POST /analysis/generate."""

    job_records:  list[JobRecordRequest] = Field(
        ...,
        min_length=1,
        description="Job postings to analyse (1 – 500 records)",
    )
    user_skills:  list[str] = Field(
        default_factory=list,
        description="Canonical skill names the user already has",
    )
    target_role:  str = Field(
        default="Software Engineer",
        max_length=100,
        description="Target job role for roadmap framing",
    )
    min_demand_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Exclude market skills below this demand percentage",
    )
    max_roadmap_steps: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Maximum number of steps in the learning roadmap",
    )

    @field_validator("job_records")
    @classmethod
    def check_record_limit(cls, v: list) -> list:
        if len(v) > _MAX_JOB_RECORDS:
            raise ValueError(
                f"job_records exceeds maximum of {_MAX_JOB_RECORDS} entries."
            )
        return v

    @field_validator("user_skills")
    @classmethod
    def check_user_skill_limit(cls, v: list[str]) -> list[str]:
        if len(v) > _MAX_USER_SKILLS:
            raise ValueError(
                f"user_skills exceeds maximum of {_MAX_USER_SKILLS} entries."
            )
        return [s.strip() for s in v if s.strip()]


# ══════════════════════════════════════════════════════════════════════════════
# Response models
# ══════════════════════════════════════════════════════════════════════════════

class MarketSkillResponse(BaseModel):
    skill:      str   = Field(description="Canonical skill name")
    demand_pct: float = Field(description="Percentage of jobs requiring this skill")
    category:   str   = Field(description="Skill category")
    count:      int   = Field(description="Number of job postings that mention this skill")


class MissingSkillResponse(BaseModel):
    skill:          str   = Field(description="Canonical skill name")
    tier:           str   = Field(description="Demand tier: CRITICAL / HIGH / MODERATE / EMERGING")
    demand_pct:     float = Field(description="Market demand percentage")
    priority_score: float = Field(description="Priority score [0.0 – 1.0]")
    is_partial:     bool  = Field(description="True if user has a related skill in the same category")
    partial_match:  str | None = Field(None, description="Related skill the user already has")
    explanation:    str   = Field(description="Human-readable priority justification")


class PrioritySkillResponse(BaseModel):
    rank:            int   = Field(description="Priority rank (1 = highest)")
    skill:           str
    category:        str
    demand_pct:      float
    tier:            str
    final_score:     float = Field(description="Composite priority score after all signals [0.0 – 1.0]")
    phase:           str   = Field(description="Learning phase: Foundation / Core / Advanced")
    is_prerequisite: bool  = Field(description="True if other missing skills depend on this one")
    quick_win:       bool  = Field(description="True if high demand with low learning curve")
    explanation:     str


class RoadmapStepResponse(BaseModel):
    week:           int
    skill:          str
    priority:       str   = Field(description="High / Medium / Low")
    reason:         str
    category:       str
    duration_weeks: int   = Field(description="Number of weeks allocated to this skill")


class AnalysisSummary(BaseModel):
    total_jobs_analysed:  int
    total_market_skills:  int
    total_missing_skills: int
    coverage_pct:         float = Field(description="Percentage of market skills the user has")
    placement_score:      float = Field(description="Weighted placement readiness score 0–100")
    estimated_weeks:      int   = Field(description="Total weeks in the learning roadmap")
    top_missing_skill:    str | None = Field(None, description="Highest-priority missing skill")


class AnalysisReportResponse(BaseModel):
    target_role:     str
    summary:         AnalysisSummary
    market_skills:   list[MarketSkillResponse]
    missing_skills:  list[MissingSkillResponse]
    priority_skills: list[PrioritySkillResponse]
    roadmap:         list[RoadmapStepResponse]
    processing_ms:   int = Field(description="Server-side processing time in milliseconds")


class EngineStatusResponse(BaseModel):
    status:          str   = Field(description="'healthy' or 'degraded'")
    version:         str   = Field(description="Analysis engine version")
    max_job_records: int
    max_user_skills: int
    capabilities:    list[str] = Field(description="Active pipeline stages")


class ErrorResponse(BaseModel):
    detail: str
    code:   str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# Dependency
# ══════════════════════════════════════════════════════════════════════════════

class AnalysisConfig:
    """Injected config for the analysis pipeline. Override in tests."""

    def __init__(
        self,
        min_confidence:    float = 0.40,
        partial_match:     bool  = True,
    ) -> None:
        self.min_confidence = min_confidence
        self.partial_match  = partial_match


def get_analysis_config() -> AnalysisConfig:
    return AnalysisConfig(
        min_confidence = float(os.getenv("MIN_SKILL_CONFIDENCE", "0.40")),
        partial_match  = os.getenv("PARTIAL_MATCH", "true").lower() == "true",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _to_resume_skills(user_skills: list[str]) -> list[ResumeSkill]:
    """Convert plain skill name strings into ResumeSkill dicts."""
    return [
        ResumeSkill(skill=s, confidence=1.0, source="explicit")
        for s in user_skills if s.strip()
    ]


def _coerce_roadmap_step(entry: dict) -> RoadmapStepResponse:
    return RoadmapStepResponse(
        week           = int(entry.get("week", 1)),
        skill          = entry.get("skill", ""),
        priority       = entry.get("priority", "Medium"),
        reason         = entry.get("reason", ""),
        category       = entry.get("category", "other"),
        duration_weeks = int(entry.get("duration_weeks", 1)),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Router
# ══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ── POST /analysis/generate ───────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model = AnalysisReportResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Run full skill gap and market analysis",
    responses      = {
        400: {"model": ErrorResponse, "description": "Invalid request payload"},
        422: {"model": ErrorResponse, "description": "Analysis pipeline error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def generate_analysis(
    body:   AnalysisRequest,
    config: Annotated[AnalysisConfig, Depends(get_analysis_config)],
) -> AnalysisReportResponse:
    """
    Run the complete skill gap analysis and roadmap generation pipeline.

    **Pipeline stages:**
    1. Aggregate job skill demand from provided job records
    2. Detect skill gaps between user's skills and market demand
    3. Rank missing skills by priority (demand + prerequisites + quick-wins)
    4. Generate an ordered week-by-week learning roadmap

    **Returns** a structured report with:
    - `market_skills`   — demand statistics for each skill in the job corpus
    - `missing_skills`  — gaps with tier, priority score, and explanation
    - `priority_skills` — re-ranked gaps with prerequisite and phase signals
    - `roadmap`         — ordered learning plan with week assignments
    - `summary`         — aggregate metrics (coverage %, placement score)
    """
    t_start = time.monotonic()
    logger.info(
        "POST /analysis/generate  jobs=%d  user_skills=%d  role=%r",
        len(body.job_records), len(body.user_skills), body.target_role,
    )

    try:
        # ── Stage 1: market aggregation ───────────────────────────────────
        raw_records = [{"job_id": r.job_id, "skills": r.skills}
                       for r in body.job_records]
        market_result = aggregate_job_skills(raw_records)

        if not market_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Market aggregation failed: {market_result['error']}",
            )

        market_skills_raw = [
            ms for ms in market_result["market_skills"]
            if ms["demand_pct"] >= body.min_demand_pct
        ]
        logger.info("Stage 1 complete: %d market skills", len(market_skills_raw))

        # ── Stage 2: gap detection ────────────────────────────────────────
        resume_skills = _to_resume_skills(body.user_skills)
        gap_report    = detect_gaps(
            resume_skills  = resume_skills,
            market_skills  = market_skills_raw,
            partial_match  = config.partial_match,
            min_demand_pct = body.min_demand_pct,
        )

        if not gap_report["success"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Gap detection failed: {gap_report['error']}",
            )
        logger.info(
            "Stage 2 complete: missing=%d  coverage=%.1f%%",
            len(gap_report["missing_skills"]), gap_report["coverage_pct"],
        )

        # ── Stage 3: priority ranking ─────────────────────────────────────
        rank_result = rank_gaps(
            gap_report  = gap_report,
            user_skills = body.user_skills,
            max_ranking = body.max_roadmap_steps,
        )

        if not rank_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Priority ranking failed: {rank_result['error']}",
            )
        logger.info("Stage 3 complete: %d ranked skills", len(rank_result["ranked_skills"]))

        # ── Stage 4: roadmap generation ───────────────────────────────────
        roadmap_out = build_roadmap(
            missing_skills = [dict(m) for m in gap_report["missing_skills"]],
            user_skills    = body.user_skills,
            target_role    = body.target_role,
        )
        logger.info(
            "Stage 4 complete: %d roadmap steps  %d weeks",
            len(roadmap_out["roadmap"]),
            roadmap_out["estimated_duration_weeks"],
        )

        # ── Build market_skills with count from skills dict ───────────────
        skills_dict = market_result.get("skills", {})
        market_response = [
            MarketSkillResponse(
                skill      = ms["skill"],
                demand_pct = ms["demand_pct"],
                category   = ms["category"],
                count      = skills_dict.get(ms["skill"], {}).get("count", 0),
            )
            for ms in market_skills_raw
        ]

        # ── Assemble summary ──────────────────────────────────────────────
        top_missing = (
            rank_result["ranked_skills"][0]["skill"]
            if rank_result["ranked_skills"] else None
        )
        summary = AnalysisSummary(
            total_jobs_analysed  = market_result["total_jobs"],
            total_market_skills  = len(market_skills_raw),
            total_missing_skills = len(gap_report["missing_skills"]),
            coverage_pct         = gap_report["coverage_pct"],
            placement_score      = gap_report["placement_score"],
            estimated_weeks      = roadmap_out["estimated_duration_weeks"],
            top_missing_skill    = top_missing,
        )

        processing_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "Analysis complete in %dms  coverage=%.1f%%  placement=%.1f",
            processing_ms, summary.coverage_pct, summary.placement_score,
        )

        return AnalysisReportResponse(
            target_role     = body.target_role,
            summary         = summary,
            market_skills   = market_response,
            missing_skills  = [
                MissingSkillResponse(
                    skill          = m["skill"],
                    tier           = m["tier"],
                    demand_pct     = m["demand_pct"],
                    priority_score = m["priority_score"],
                    is_partial     = m["is_partial"],
                    partial_match  = m.get("partial_match"),
                    explanation    = m["explanation"],
                )
                for m in gap_report["missing_skills"]
            ],
            priority_skills = [
                PrioritySkillResponse(
                    rank            = r["rank"],
                    skill           = r["skill"],
                    category        = r["category"],
                    demand_pct      = r["demand_pct"],
                    tier            = r["tier"],
                    final_score     = r["final_score"],
                    phase           = r["phase"],
                    is_prerequisite = r["is_prerequisite"],
                    quick_win       = r["quick_win"],
                    explanation     = r["explanation"],
                )
                for r in rank_result["ranked_skills"]
            ],
            roadmap         = [_coerce_roadmap_step(e) for e in roadmap_out["roadmap"]],
            processing_ms   = processing_ms,
        )

    except HTTPException:
        raise

    except Exception as exc:                       # noqa: BLE001
        logger.exception("Unexpected error in /analysis/generate: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during analysis.",
        ) from exc


# ── GET /analysis/status ──────────────────────────────────────────────────────

@router.get(
    "/status",
    response_model = EngineStatusResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Health and configuration status of the analysis engine",
)
def analysis_status() -> EngineStatusResponse:
    """
    Return the health status and active capabilities of the analysis engine.

    Useful for:
    - Frontend polling before submitting an analysis request
    - Ops monitoring and readiness checks
    - CI smoke tests

    Always returns `200 OK` when the engine is importable and configured.
    """
    logger.debug("GET /analysis/status")
    return EngineStatusResponse(
        status          = "healthy",
        version         = _ENGINE_VERSION,
        max_job_records = _MAX_JOB_RECORDS,
        max_user_skills = _MAX_USER_SKILLS,
        capabilities    = [
            "market_aggregation",
            "gap_detection",
            "priority_ranking",
            "roadmap_generation",
        ],
    )