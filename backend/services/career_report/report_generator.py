"""
report_generator.py
─────────────────────────────────────────────────────────────────────────────
Orchestration layer that connects all platform modules and produces a
single, unified career intelligence report.

Workflow
--------
    Resume Path
         ↓  resume_parser.extract_resume()
    ResumeData (name, email, phone, raw_text)
         ↓  gap_analysis.resume_skills.extract_resume_skills()
    list[ResumeSkill]  — skills extracted from the resume
         ↓  gap_analysis.job_skills.aggregate_job_skills()
    JobSkillsResult    — market demand from pre-collected job data
         ↓  gap_analysis.gap_detector.detect_gaps()
    GapReport          — missing / present / extra skills with scores
         ↓  gap_analysis.priority_ranker.rank_gaps()
    RankResult         — priority-ranked gap with explanations
         ↓  services.roadmap.roadmap_builder.build_roadmap()
    RoadmapOutput      — ordered weekly learning plan
         ↓
    CareerReport       — single unified output object

Output schema
-------------
{
  "candidate_name":   str,
  "target_role":      str,
  "detected_skills":  [{"skill": str, "confidence": float, "source": str}],
  "market_skills":    [{"skill": str, "demand_pct": float, "category": str}],
  "missing_skills":   [{"skill": str, "tier": str, "demand_pct": float,
                         "priority_score": float, "explanation": str}],
  "priority_skills":  [{"rank": int, "skill": str, "final_score": float,
                         "phase": str, "tier": str, "explanation": str}],
  "roadmap":          [{"week": int, "skill": str, "priority": str,
                         "reason": str, "duration_weeks": int}],
  "coverage_pct":     float,
  "placement_score":  float,
  "success":          bool,
  "error":            str | None
}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from services.resume_parser.extract_resume        import parse_resume
from services.gap_analysis.resume_skills          import extract_resume_skills
from services.gap_analysis.job_skills             import aggregate_job_skills, JobRecord
from services.gap_analysis.gap_detector           import detect_gaps
from services.gap_analysis.priority_ranking        import rank_gaps
from services.roadmap.roadmap_builder    import build_roadmap
from services.job_analysis.jd_parser import parse_jd
from services.job_analysis.skill_counter import count_corpus
from services.job_analysis.market_trends import (
    generate_trends,
    role_alignment_for_user,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())




# ── Output type ───────────────────────────────────────────────────────────────

class CareerReport(TypedDict):
    candidate_name:  str
    target_role:     str
    detected_skills: list[dict]
    market_skills:   list[dict]
    missing_skills:  list[dict]
    priority_skills: list[dict]
    roadmap:         list[dict]
    trending_skills: list[dict]
    role_alignments: list[dict]
    coverage_pct:    float
    placement_score: float
    success:         bool
    error:           str | None


# ── Step dataclass (Open/Closed: add steps without touching orchestrator) ──────

@dataclass
class PipelineContext:
    """Carries state between pipeline stages."""
    resume_path:     str
    target_role:     str
    job_records:     list[JobRecord]
    min_confidence:  float  = 0.40
    min_demand_pct:  float  = 0.0
    max_roadmap_steps: int  = 15

    # Populated as pipeline runs
    candidate_name:  str          = ""
    raw_text:        str          = ""
    detected_skills: list[dict]   = field(default_factory=list)
    market_skills:   list[dict]   = field(default_factory=list)
    missing_skills:  list[dict]   = field(default_factory=list)
    priority_skills: list[dict]   = field(default_factory=list)
    roadmap:         list[dict]   = field(default_factory=list)
    trending_skills: list[dict] = field(default_factory=list)
    role_alignments: list[dict] = field(default_factory=list)
    coverage_pct:    float        = 0.0
    placement_score: float        = 0.0


# ── Individual pipeline stages (Single Responsibility) ───────────────────────

class ResumeParsingStage:
    """Stage 1: Parse the resume file and extract raw text."""

    def run(self, ctx: PipelineContext) -> None:
        """
        Parse the resume at ctx.resume_path.

        Populates ctx.raw_text and ctx.candidate_name.

        Raises
        ------
        FileNotFoundError : If the resume path does not exist.
        ValueError        : If parsing fails.
        """
        path = Path(ctx.resume_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {ctx.resume_path}")

        logger.info("[1/5] Parsing resume: %s", path.name)
        result = parse_resume(ctx.resume_path)

        if not result["success"]:
            raise ValueError(f"Resume parsing failed: {result['error']}")

        ctx.raw_text       = result["raw_text"]
        ctx.candidate_name = result.get("name") or path.stem
        logger.info("[1/5] Parsed OK  name=%r  chars=%d",
                    ctx.candidate_name, len(ctx.raw_text))


class SkillExtractionStage:
    """Stage 2: Extract skills from the parsed resume text."""

    def run(self, ctx: PipelineContext) -> None:
        """
        Extract skills from ctx.raw_text.

        Populates ctx.detected_skills as list of ResumeSkill dicts.

        Raises
        ------
        ValueError : If skill extraction fails.
        """
        logger.info("[2/5] Extracting skills from resume text.")
        result = extract_resume_skills(ctx.raw_text, min_confidence=ctx.min_confidence)

        if not result["success"]:
            raise ValueError(f"Skill extraction failed: {result['error']}")

        ctx.detected_skills = [dict(s) for s in result["skills"]]
        logger.info("[2/5] Extracted %d skills  (explicit=%d  inferred=%d)",
                    result["skill_count"],
                    len(result["by_source"].get("explicit", [])),
                    len(result["by_source"].get("inferred", [])))


class MarketAnalysisStage:
    """Stage 3: Aggregate market skill demand from job records."""

    def run(self, ctx: PipelineContext) -> None:
        """
        Aggregate job skill demand from ctx.job_records.

        Populates ctx.market_skills as list of MarketSkill dicts.

        Raises
        ------
        ValueError : If aggregation fails or no job records provided.
        """
        if not ctx.job_records:
            logger.warning("[3/5] No job records provided — market data will be empty.")
            ctx.market_skills = []
            return

        logger.info("[3/5] Aggregating market skills from %d job records.",
                    len(ctx.job_records))
        result = aggregate_job_skills(ctx.job_records)

        if not result["success"]:
            raise ValueError(f"Market analysis failed: {result['error']}")

        # Filter by min_demand_pct and convert to dicts
        ctx.market_skills = [
            ms for ms in result["market_skills"]
            if ms["demand_pct"] >= ctx.min_demand_pct
        ]
        logger.info("[3/5] Market analysis: %d skills  top=%r (%.1f%%)",
                    len(ctx.market_skills),
                    ctx.market_skills[0]["skill"]      if ctx.market_skills else "none",
                    ctx.market_skills[0]["demand_pct"] if ctx.market_skills else 0.0)


class MarketTrendStage:
    """
    Generates market intelligence insights from job descriptions.

    Produces:
    - trending_skills
    - role_alignments
    """

    def run(self, ctx: PipelineContext) -> None:

        if not ctx.job_records:
            logger.warning(
                "[MarketTrendStage] No job records available."
            )
            return
        print("FIRST JOB:")
        print(ctx.job_records[0])
        logger.info(
            "[MarketTrendStage] Processing %d job records.",
            len(ctx.job_records)
        )

        parsed_jds = []

        for job in ctx.job_records:

            try:
                parsed = parse_jd(
                    job.get("description", "")
                )

                if parsed.get("success"):
                    parsed_jds.append(
                        parsed.get("parsed")
                    )

            except Exception as exc:
                logger.warning(
                    "[MarketTrendStage] JD parse failed: %s",
                    exc
                )

        logger.info(
            "[MarketTrendStage] Parsed %d job descriptions.",
            len(parsed_jds)
        )

        if not parsed_jds:
            logger.warning(
                "[MarketTrendStage] No parsed JDs generated."
            )
            return

        corpus = count_corpus(
            parsed_jds,
            min_count=1,
        )

        trends = generate_trends(
            corpus
        )

        ctx.trending_skills = [
            dict(item)
            for item in trends.get("top_skills", [])[:10]
        ]

        user_skill_names = [
            skill["skill"]
            for skill in ctx.detected_skills
        ]

        ctx.role_alignments = role_alignment_for_user(
            user_skill_names
        )[:5]

        logger.info(
            "[MarketTrendStage] Generated %d trending skills and %d role alignments.",
            len(ctx.trending_skills),
            len(ctx.role_alignments),
        )

        print("\n=== MARKET TREND STAGE ===")
        print("TRENDING:", ctx.trending_skills)
        print("ROLES:", ctx.role_alignments)
        print("==========================\n")



class GapAnalysisStage:
    """Stage 4: Detect skill gaps and rank them by priority."""

    def run(self, ctx: PipelineContext) -> None:
        """
        Detect gaps and produce ranked priority skills.

        Populates ctx.missing_skills, ctx.priority_skills,
        ctx.coverage_pct, ctx.placement_score.

        Raises
        ------
        ValueError : If gap detection or ranking fails.
        """
        logger.info("[4/5] Running gap analysis.")

        gap_report = detect_gaps(
            resume_skills  = ctx.detected_skills,
            market_skills  = ctx.market_skills,
            partial_match  = True,
            min_demand_pct = ctx.min_demand_pct,
        )

        if not gap_report["success"]:
            raise ValueError(f"Gap detection failed: {gap_report['error']}")

        user_skill_names = [s["skill"] for s in ctx.detected_skills]
        rank_result      = rank_gaps(
            gap_report  = gap_report,
            user_skills = user_skill_names,
            max_ranking = ctx.max_roadmap_steps,
        )

        if not rank_result["success"]:
            raise ValueError(f"Priority ranking failed: {rank_result['error']}")

        ctx.missing_skills  = [dict(m) for m in gap_report["missing_skills"]]
        ctx.priority_skills = [dict(r) for r in rank_result["ranked_skills"]]
        ctx.coverage_pct    = gap_report["coverage_pct"]
        ctx.placement_score = gap_report["placement_score"]

        logger.info(
            "[4/5] Gap analysis: %d missing  coverage=%.1f%%  placement=%.1f",
            len(ctx.missing_skills), ctx.coverage_pct, ctx.placement_score,
        )


class RoadmapGenerationStage:
    """Stage 5: Build the ordered learning roadmap."""

    def run(self, ctx: PipelineContext) -> None:
        """
        Generate a learning roadmap from ranked missing skills.

        Populates ctx.roadmap.
        """
        logger.info("[5/5] Generating roadmap for role=%r.", ctx.target_role)

        user_skill_names = [s["skill"] for s in ctx.detected_skills]
        roadmap_out      = build_roadmap(
            missing_skills = ctx.missing_skills,
            user_skills    = user_skill_names,
            target_role    = ctx.target_role,
        )

        ctx.roadmap = roadmap_out["roadmap"]
        logger.info("[5/5] Roadmap: %d steps  %d weeks",
                    len(ctx.roadmap),
                    roadmap_out["estimated_duration_weeks"])


# ── Orchestrator ──────────────────────────────────────────────────────────────

class ReportGenerator:
    """
    Orchestrates the full career intelligence pipeline.

    Each stage is independently replaceable (Open/Closed). Inject
    custom stage instances to override individual steps without
    touching this class.

    Usage
    -----
        generator = ReportGenerator()
        report    = generator.generate(
            resume_path = "/path/to/resume.pdf",
            job_records = [{"job_id": 1, "skills": ["Python", "SQL"]}, ...],
            target_role = "Data Analyst",
        )
    """

    def __init__(
        self,
        parsing_stage:    ResumeParsingStage    | None = None,
        extraction_stage: SkillExtractionStage  | None = None,
        market_stage:     MarketAnalysisStage   | None = None,
        gap_stage:        GapAnalysisStage      | None = None,
        roadmap_stage:    RoadmapGenerationStage| None = None,
    ) -> None:
        self._stages = [
            parsing_stage    or ResumeParsingStage(),
            extraction_stage or SkillExtractionStage(),
            market_stage     or MarketAnalysisStage(),
            MarketTrendStage(),
            gap_stage        or GapAnalysisStage(),
            roadmap_stage    or RoadmapGenerationStage(),
        ]

    def generate(
        self,
        resume_path:       str,
        job_records:       list[JobRecord],
        target_role:       str   = "Software Engineer",
        min_confidence:    float = 0.40,
        min_demand_pct:    float = 0.0,
        max_roadmap_steps: int   = 15,
    ) -> CareerReport:
        """
        Run the full pipeline and return a unified CareerReport.

        Parameters
        ----------
        resume_path       : Absolute or relative path to the resume file
                            (.pdf or .docx).
        job_records       : Pre-collected job data from job_engine or
                            job_analysis. Each record:
                            {"job_id": str|int, "skills": list[str]}
        target_role       : Target job role label for roadmap framing.
        min_confidence    : Minimum skill extraction confidence (0–1).
        min_demand_pct    : Only include market skills above this % demand.
        max_roadmap_steps : Cap on roadmap entries.

        Returns
        -------
        CareerReport
            {
              "candidate_name":  str,
              "target_role":     str,
              "detected_skills": [...],
              "market_skills":   [...],
              "missing_skills":  [...],
              "priority_skills": [...],
              "roadmap":         [...],
              "coverage_pct":    float,
              "placement_score": float,
              "success":         bool,
              "error":           None
            }

        On any stage failure, success=False and error contains the message.
        Partial results accumulated before the failure are still returned.
        """
        ctx = PipelineContext(
            resume_path       = resume_path,
            target_role       = target_role,
            job_records       = job_records,
            min_confidence    = min_confidence,
            min_demand_pct    = min_demand_pct,
            max_roadmap_steps = max_roadmap_steps,
        )

        logger.info(
            "ReportGenerator.generate: resume=%r  role=%r  jobs=%d",
            resume_path, target_role, len(job_records),
        )

        for stage in self._stages:
            try:
                stage.run(ctx)
            except (FileNotFoundError, ValueError) as exc:
                logger.error("%s failed: %s", type(stage).__name__, exc)
                return self._build_report(ctx, error=str(exc))
            except Exception as exc:                    # noqa: BLE001
                logger.error("%s unexpected error: %s", type(stage).__name__, exc,
                             exc_info=True)
                return self._build_report(ctx, error=f"Unexpected error: {exc}")

        logger.info(
            "generate complete: detected=%d  missing=%d  roadmap=%d  "
            "coverage=%.1f%%  placement=%.1f",
            len(ctx.detected_skills), len(ctx.missing_skills),
            len(ctx.roadmap), ctx.coverage_pct, ctx.placement_score,
        )
        return self._build_report(ctx, error=None)

    @staticmethod
    def _build_report(ctx: PipelineContext, error: str | None) -> CareerReport:
        return CareerReport(
            candidate_name  = ctx.candidate_name,
            target_role     = ctx.target_role,
            detected_skills = ctx.detected_skills,
            market_skills   = ctx.market_skills,
            missing_skills  = ctx.missing_skills,
            priority_skills = ctx.priority_skills,
            roadmap         = ctx.roadmap,
            coverage_pct    = ctx.coverage_pct,
            placement_score = ctx.placement_score,
            trending_skills=ctx.trending_skills,
            role_alignments=ctx.role_alignments,
            success         = error is None,
            error           = error,
        )


# ── Public convenience function ───────────────────────────────────────────────

def generate_career_report(
    resume_path:       str,
    job_records:       list[JobRecord],
    target_role:       str   = "Software Engineer",
    min_confidence:    float = 0.40,
    min_demand_pct:    float = 0.0,
    max_roadmap_steps: int   = 15,
) -> CareerReport:
    """
    Generate a full career intelligence report. Single-call convenience wrapper.

    Parameters
    ----------
    resume_path       : Path to resume (.pdf or .docx).
    job_records       : Job skill data from job_engine.
    target_role       : Target role for roadmap generation.
    min_confidence    : Minimum skill confidence threshold.
    min_demand_pct    : Minimum market demand to include a skill.
    max_roadmap_steps : Maximum roadmap entries.

    Returns
    -------
    CareerReport dict matching the platform output spec.
    """
    return ReportGenerator().generate(
        resume_path       = resume_path,
        job_records       = job_records,
        target_role       = target_role,
        min_confidence    = min_confidence,
        min_demand_pct    = min_demand_pct,
        max_roadmap_steps = max_roadmap_steps,
    )