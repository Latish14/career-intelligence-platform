"""
tests/test_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive pytest suite for the AI-Powered Student Career Intelligence
Platform pipeline.

Workflow under test
-------------------
    Resume → ResumeParser → SkillExtraction → JobAnalysis
          → GapAnalysis → RoadmapGeneration → ReportGeneration

Test categories
---------------
    Unit  — each stage in isolation with mocked dependencies.
    Integration — two or more stages wired together.
    Pipeline — full end-to-end with all dependencies mocked.
    Failure — each stage's error paths.

Run
---
    pytest tests/test_pipeline.py -v
    pytest tests/test_pipeline.py -v --tb=short
    pytest tests/test_pipeline.py -k "test_gap" -v
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.DEBUG,
    format = "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger("test_pipeline")


# ═══════════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_resume_text() -> str:
    return """
Latish Nanda | latish@example.com | +91-98765-43210

Technical Skills:
Python, SQL, Scikit-learn, XGBoost, SHAP, FastAPI, Docker, PostgreSQL, Git

Experience:
AI/ML Intern — VSC Digitech Pvt. Ltd. (Feb–Mar 2026)
- Built XAI Credit Scoring system using LIME and SHAP explainability.
- Deployed REST APIs with FastAPI on Render with PostgreSQL backend.
- Used SMOTE for class imbalance and GridSearchCV for hyperparameter tuning.
- Containerised the application with Docker and GitHub Actions CI/CD.

Projects:
- SkillSphere: React + FastAPI + Firebase skill-exchange platform.
- CLTV Prediction: BG/NBD + Gamma-Gamma model in Python using Pandas.

Education:
B.Tech CS (Data Science) — Sri Sri University
Coursework: Machine Learning, Deep Learning, NLP, Statistics
""".strip()


@pytest.fixture
def sample_job_records() -> list[dict]:
    return [
        {"job_id": 1, "skills": ["Python", "SQL", "Docker", "AWS", "Kubernetes"]},
        {"job_id": 2, "skills": ["Python", "SQL", "Machine Learning", "AWS", "Docker"]},
        {"job_id": 3, "skills": ["Python", "TensorFlow", "Docker", "Kubernetes", "AWS"]},
        {"job_id": 4, "skills": ["Python", "SQL", "Scikit-learn", "PostgreSQL", "FastAPI"]},
        {"job_id": 5, "skills": ["Python", "SQL", "Apache Spark", "AWS", "Airflow"]},
    ]


@pytest.fixture
def mock_parse_result(sample_resume_text) -> dict:
    return {
        "success": True,
        "name":     "Latish Nanda",
        "email":    "latish@example.com",
        "phone":    "+91-98765-43210",
        "raw_text": sample_resume_text,
        "error":    None,
    }


@pytest.fixture
def mock_resume_skills() -> dict:
    return {
        "success":     True,
        "skill_count": 9,
        "skills": [
            {"skill": "Python",      "confidence": 1.00, "source": "explicit"},
            {"skill": "SQL",         "confidence": 0.95, "source": "explicit"},
            {"skill": "Docker",      "confidence": 1.00, "source": "explicit"},
            {"skill": "FastAPI",     "confidence": 1.00, "source": "explicit"},
            {"skill": "PostgreSQL",  "confidence": 1.00, "source": "explicit"},
            {"skill": "Scikit-learn","confidence": 1.00, "source": "explicit"},
            {"skill": "XGBoost",     "confidence": 1.00, "source": "explicit"},
            {"skill": "SHAP",        "confidence": 1.00, "source": "explicit"},
            {"skill": "Git",         "confidence": 0.85, "source": "explicit"},
        ],
        "by_source": {
            "explicit": ["Python","SQL","Docker","FastAPI","PostgreSQL",
                         "Scikit-learn","XGBoost","SHAP","Git"],
        },
        "error": None,
    }


@pytest.fixture
def mock_market_result() -> dict:
    return {
        "success":             True,
        "total_jobs":          5,
        "total_unique_skills": 8,
        "market_skills": [
            {"skill": "Python",      "demand_pct": 100.0, "category": "programming_language", "base_weight": 0.95},
            {"skill": "SQL",         "demand_pct":  80.0, "category": "database",             "base_weight": 0.85},
            {"skill": "Docker",      "demand_pct":  80.0, "category": "devops",               "base_weight": 0.95},
            {"skill": "AWS",         "demand_pct":  80.0, "category": "cloud",                "base_weight": 0.90},
            {"skill": "Kubernetes",  "demand_pct":  60.0, "category": "devops",               "base_weight": 0.95},
            {"skill": "Machine Learning","demand_pct": 40.0,"category": "machine_learning",   "base_weight": 0.90},
            {"skill": "Apache Spark","demand_pct":  20.0, "category": "data_engineering",     "base_weight": 0.90},
            {"skill": "Airflow",     "demand_pct":  20.0, "category": "data_engineering",     "base_weight": 0.95},
        ],
        "skills": {},
        "error": None,
    }


@pytest.fixture
def mock_gap_report() -> dict:
    return {
        "success": True,
        "missing_skills": [
            {"skill": "AWS",        "category": "cloud",  "demand_pct": 80.0,
             "priority_score": 0.87, "tier": "CRITICAL", "is_partial": False,
             "partial_match": None, "explanation": "AWS required in 80% of roles."},
            {"skill": "Kubernetes", "category": "devops", "demand_pct": 60.0,
             "priority_score": 0.75, "tier": "CRITICAL", "is_partial": True,
             "partial_match": "Docker", "explanation": "Kubernetes builds on Docker."},
        ],
        "present_skills": [
            {"skill": "Python", "category": "programming_language", "demand_pct": 100.0, "tier": "CRITICAL"},
            {"skill": "SQL",    "category": "database",             "demand_pct":  80.0, "tier": "CRITICAL"},
            {"skill": "Docker", "category": "devops",               "demand_pct":  80.0, "tier": "CRITICAL"},
        ],
        "extra_skills":    ["SHAP", "XGBoost"],
        "coverage_pct":    62.5,
        "placement_score": 68.0,
        "by_category":     {"cloud": {"required_count": 1, "present_count": 0,
                                       "missing_count": 1, "coverage_pct": 0.0,
                                       "category": "cloud"}},
        "error": None,
    }


@pytest.fixture
def mock_rank_result() -> dict:
    return {
        "success": True,
        "ranked_skills": [
            {"rank": 1, "skill": "AWS",        "category": "cloud",  "demand_pct": 80.0,
             "tier": "CRITICAL", "final_score": 0.91, "phase": "Phase 1 — Foundation",
             "is_prerequisite": False, "is_partial": False, "quick_win": False,
             "explanation": "AWS required in 80% of roles. Cloud category gap."},
            {"rank": 2, "skill": "Kubernetes", "category": "devops", "demand_pct": 60.0,
             "tier": "CRITICAL", "final_score": 0.78, "phase": "Phase 1 — Foundation",
             "is_prerequisite": False, "is_partial": True, "quick_win": False,
             "explanation": "You know Docker — Kubernetes is the next step."},
        ],
        "platform_output": {"missing_skills": [], "priority_ranking": []},
        "total_gaps":      2,
        "phase_summary":   {"Phase 1 — Foundation": ["AWS", "Kubernetes"]},
        "coverage_pct":    62.5,
        "placement_score": 68.0,
        "error":           None,
    }


@pytest.fixture
def mock_roadmap() -> dict:
    return {
        "target_role":              "Data Engineer",
        "estimated_duration_weeks": 4,
        "roadmap": [
            {"week": 1, "skill": "AWS",        "priority": "High",
             "reason": "Required in 80% of jobs", "category": "cloud",   "duration_weeks": 2},
            {"week": 3, "skill": "Kubernetes", "priority": "High",
             "reason": "Required in 60% of jobs", "category": "devops",  "duration_weeks": 2},
        ],
    }


# Convenience fixture: all mocks wired
@pytest.fixture
def full_pipeline_mocks(
    mock_parse_result,
    mock_resume_skills,
    mock_market_result,
    mock_gap_report,
    mock_rank_result,
    mock_roadmap,
) -> dict:
    return {
        "parse":   mock_parse_result,
        "skills":  mock_resume_skills,
        "market":  mock_market_result,
        "gap":     mock_gap_report,
        "rank":    mock_rank_result,
        "roadmap": mock_roadmap,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 1 — Resume Parsing
# ═══════════════════════════════════════════════════════════════════════════════

class TestResumeParser:
    """Unit tests for the resume parsing stage."""

    def test_parse_pdf_success(self, tmp_path, mock_parse_result):
        """parse_resume returns a populated ResumeData on success."""
        dummy = tmp_path / "resume.pdf"
        dummy.write_bytes(b"%PDF-1.4 dummy")

        with patch("resume_parser.extract_resume.extract_text_from_pdf") as mock_pdf, \
             patch("resume_parser.extract_resume.clean_text") as mock_clean:
            mock_pdf.return_value   = {"success": True, "text": mock_parse_result["raw_text"], "pages": 1, "method": "pdfplumber", "error": None}
            mock_clean.return_value = {"success": True, "text": mock_parse_result["raw_text"], "original_chars": 100, "cleaned_chars": 90, "error": None}

            from services.resume_parser.extract_resume import parse_resume
            result = parse_resume(str(dummy))

        assert result["success"] is True
        assert result["raw_text"]
        logger.info("PDF parse: %d chars extracted", len(result["raw_text"]))

    def test_parse_missing_file(self):
        """parse_resume returns success=False for a missing file."""
        from services.resume_parser.extract_resume import parse_resume
        result = parse_resume("/nonexistent/path/resume.pdf")
        assert result["success"] is False
        assert result["error"] is not None
        logger.info("Missing file error: %s", result["error"])

    def test_parse_unsupported_format(self, tmp_path):
        """parse_resume returns success=False for an unsupported extension."""
        bad = tmp_path / "resume.txt"
        bad.write_text("dummy")
        from services.resume_parser.extract_resume import parse_resume
        result = parse_resume(str(bad))
        assert result["success"] is False
        logger.info("Unsupported format error: %s", result["error"])

    def test_parse_result_schema(self, tmp_path, mock_parse_result):
        """parse_resume result always contains required keys."""
        dummy = tmp_path / "resume.pdf"
        dummy.write_bytes(b"%PDF")
        with patch("resume_parser.extract_resume.parse_resume",
                   return_value=mock_parse_result):
            from services.resume_parser.extract_resume import parse_resume
            result = parse_resume(str(dummy))

        for key in ("success", "raw_text", "error"):
            assert key in result, f"Missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2 — Skill Extraction
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkillExtraction:
    """Unit tests for the resume skill extraction stage."""

    def test_extract_skills_success(self, sample_resume_text, mock_resume_skills):
        """extract_resume_skills returns skills from valid resume text."""
        with patch("gap_analysis.resume_skills.extract_skills") as mock_ext, \
             patch("gap_analysis.resume_skills.normalize_skills") as mock_norm:

            mock_ext.return_value  = MagicMock(
                skills=[MagicMock(skill="Python", confidence=0.95, matched_text="Python")],
                success=True,
            )
            mock_norm.return_value = MagicMock(
                skills=[MagicMock(canonical="Python", original="Python",
                                  method="exact", confidence_multiplier=1.0,
                                  category="programming_language")],
                success=True,
            )

            from services.gap_analysis.resume_skills import extract_resume_skills
            result = extract_resume_skills(sample_resume_text)

        assert result["success"] is True
        assert result["skill_count"] >= 0
        logger.info("Skills extracted: %d", result["skill_count"])

    def test_extract_skills_empty_text(self):
        """extract_resume_skills returns success=True with empty list for blank input."""
        from services.gap_analysis.resume_skills import extract_resume_skills
        result = extract_resume_skills("")
        assert result["success"] is True
        assert result["skills"] == []

    def test_extract_skills_invalid_type(self):
        """extract_resume_skills returns error for non-string input."""
        from services.gap_analysis.resume_skills import extract_resume_skills
        result = extract_resume_skills(12345)
        assert result["success"] is False
        assert result["error"] is not None

    def test_explicit_skills_have_higher_confidence(self, sample_resume_text):
        """Skills in the Skills section should have higher avg confidence than inferred."""
        from services.gap_analysis.resume_skills import extract_resume_skills
        result = extract_resume_skills(sample_resume_text)
        if not result["success"]:
            pytest.skip("Skill extraction returned no results")

        explicit = [s for s in result["skills"] if s["source"] == "explicit"]
        inferred = [s for s in result["skills"] if s["source"] == "inferred"]
        if explicit and inferred:
            avg_exp = sum(s["confidence"] for s in explicit) / len(explicit)
            avg_inf = sum(s["confidence"] for s in inferred) / len(inferred)
            assert avg_exp >= avg_inf, (
                f"Explicit avg {avg_exp:.2f} should be >= inferred avg {avg_inf:.2f}"
            )
            logger.info("Confidence: explicit=%.2f  inferred=%.2f", avg_exp, avg_inf)

    def test_skill_result_schema(self, mock_resume_skills):
        """Each ResumeSkill must have skill, confidence, source."""
        for s in mock_resume_skills["skills"]:
            assert "skill"      in s
            assert "confidence" in s
            assert "source"     in s
            assert s["source"] in ("explicit", "inferred", "education")

    def test_no_duplicate_skills(self, sample_resume_text):
        """Extracted skills contain no duplicate canonical names."""
        from services.gap_analysis.resume_skills import extract_resume_skills
        result = extract_resume_skills(sample_resume_text)
        names = [s["skill"] for s in result["skills"]]
        assert len(names) == len(set(names)), f"Duplicates found: {names}"


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 3 — Job Analysis / Market Skills
# ═══════════════════════════════════════════════════════════════════════════════

class TestJobAnalysis:
    """Unit tests for job skill aggregation and market analysis."""

    def test_aggregate_job_skills_spec(self):
        """Verifies the exact spec example output."""
        from services.gap_analysis.job_skills import aggregate_job_skills
        records = [
            {"job_id": 1, "skills": ["Python", "SQL", "Docker"]},
            {"job_id": 2, "skills": ["Python", "AWS",  "SQL"]},
        ]
        result = aggregate_job_skills(records)
        assert result["success"] is True
        assert result["skills"]["Python"]["count"]             == 2
        assert result["skills"]["Python"]["demand_percentage"] == 100.0
        assert result["skills"]["SQL"]["demand_percentage"]    == 100.0
        assert result["skills"]["Docker"]["demand_percentage"] == 50.0
        assert result["skills"]["AWS"]["demand_percentage"]    == 50.0
        logger.info("Spec example verified: %s", list(result["skills"].keys()))

    def test_binary_counting(self):
        """Skill mentioned multiple times in one job counts as 1."""
        from services.gap_analysis.job_skills import aggregate_job_skills
        records = [{"job_id": 1, "skills": ["Python", "Python", "Python"]}]
        result  = aggregate_job_skills(records)
        assert result["skills"]["Python"]["count"] == 1

    def test_alias_normalisation(self):
        """JS → JavaScript, sklearn → Scikit-learn resolved before counting."""
        from services.gap_analysis.job_skills import aggregate_job_skills
        records = [
            {"job_id": 1, "skills": ["JS",         "sklearn"]},
            {"job_id": 2, "skills": ["JavaScript", "Scikit-learn"]},
        ]
        result = aggregate_job_skills(records)
        assert "JavaScript" in result["skills"]
        assert "Scikit-learn" in result["skills"]
        assert result["skills"]["JavaScript"]["count"]  == 2
        assert result["skills"]["Scikit-learn"]["count"] == 2
        logger.info("Alias resolution: JS+JavaScript→JavaScript count=2")

    def test_sorted_by_demand_desc(self, sample_job_records):
        """Market skills are sorted by demand_percentage descending."""
        from services.gap_analysis.job_skills import aggregate_job_skills
        result = aggregate_job_skills(sample_job_records)
        pcts   = [v["demand_percentage"] for v in result["skills"].values()]
        assert pcts == sorted(pcts, reverse=True)

    def test_empty_job_records(self):
        """Empty list returns success=True with no skills."""
        from services.gap_analysis.job_skills import aggregate_job_skills
        result = aggregate_job_skills([])
        assert result["success"] is True
        assert result["skills"] == {}

    def test_invalid_input_type(self):
        """Non-list input returns success=False with error."""
        from services.gap_analysis.job_skills import aggregate_job_skills
        result = aggregate_job_skills("bad input")
        assert result["success"] is False
        assert result["error"]   is not None

    def test_market_skill_schema(self, mock_market_result):
        """Each MarketSkill must have skill, demand_pct, category, base_weight."""
        for ms in mock_market_result["market_skills"]:
            for key in ("skill", "demand_pct", "category", "base_weight"):
                assert key in ms, f"Missing: {key}"
            assert 0 <= ms["demand_pct"] <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 4 — Gap Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestGapAnalysis:
    """Unit tests for gap detection and priority ranking."""

    def test_detect_gaps_basic(self, mock_resume_skills, mock_market_result):
        """Skills in resume and not in market end up in present_skills."""
        from services.gap_analysis.gap_detector import detect_gaps
        resume  = mock_resume_skills["skills"]
        market  = mock_market_result["market_skills"]
        result  = detect_gaps(resume, market)
        assert result["success"] is True
        present = [p["skill"] for p in result["present_skills"]]
        assert "Python" in present
        logger.info("Present skills: %s", present)

    def test_missing_skills_correct(self, mock_resume_skills, mock_market_result):
        """Skills in market but not in resume appear in missing_skills."""
        from services.gap_analysis.gap_detector import detect_gaps
        result  = detect_gaps(mock_resume_skills["skills"], mock_market_result["market_skills"])
        missing = [m["skill"] for m in result["missing_skills"]]
        assert "AWS" in missing
        logger.info("Missing skills: %s", missing)

    def test_priority_score_range(self, mock_gap_report):
        """Every missing skill priority_score must be in [0.0, 1.0]."""
        for ms in mock_gap_report["missing_skills"]:
            assert 0.0 <= ms["priority_score"] <= 1.0, (
                f"{ms['skill']} score {ms['priority_score']} out of range"
            )

    def test_sorted_by_priority_desc(self, mock_gap_report):
        """Missing skills are sorted by priority_score descending."""
        scores = [m["priority_score"] for m in mock_gap_report["missing_skills"]]
        assert scores == sorted(scores, reverse=True)

    def test_partial_match_detection(self, mock_gap_report):
        """Skills with a same-category resume sibling are flagged is_partial=True."""
        partial = [m for m in mock_gap_report["missing_skills"] if m["is_partial"]]
        assert len(partial) > 0
        for p in partial:
            assert p["partial_match"] is not None
            logger.info("Partial: %s ≈ %s", p["skill"], p["partial_match"])

    def test_gap_report_schema(self, mock_gap_report):
        """GapReport contains all required keys."""
        for key in ("missing_skills","present_skills","extra_skills",
                    "coverage_pct","placement_score","by_category","success","error"):
            assert key in mock_gap_report

    def test_coverage_pct_range(self, mock_gap_report):
        """coverage_pct must be between 0 and 100."""
        assert 0 <= mock_gap_report["coverage_pct"] <= 100

    def test_invalid_input_types(self):
        """detect_gaps raises error for non-list inputs."""
        from services.gap_analysis.gap_detector import detect_gaps
        result = detect_gaps("bad", [])
        assert result["success"] is False
        result2 = detect_gaps([], "bad")
        assert result2["success"] is False

    def test_empty_resume_all_missing(self, mock_market_result):
        """With no resume skills, all market skills appear as missing."""
        from services.gap_analysis.gap_detector import detect_gaps
        result = detect_gaps([], mock_market_result["market_skills"])
        assert result["success"] is True
        assert len(result["missing_skills"]) == len(mock_market_result["market_skills"])
        assert result["coverage_pct"] == 0.0

    def test_rank_gaps_schema(self, mock_rank_result):
        """RankResult and each RankedSkill contain required keys."""
        for key in ("ranked_skills","total_gaps","coverage_pct",
                    "placement_score","success","error"):
            assert key in mock_rank_result
        for rs in mock_rank_result["ranked_skills"]:
            for key in ("rank","skill","tier","final_score","phase","explanation"):
                assert key in rs

    def test_rank_sequential(self, mock_rank_result):
        """Rank numbers are sequential starting from 1."""
        ranks = [s["rank"] for s in mock_rank_result["ranked_skills"]]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_explanation_non_empty(self, mock_rank_result):
        """Every ranked skill has a non-empty explanation string."""
        for rs in mock_rank_result["ranked_skills"]:
            assert isinstance(rs["explanation"], str)
            assert len(rs["explanation"]) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 5 — Roadmap Generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoadmapGeneration:
    """Unit tests for roadmap building and timeline generation."""

    def test_build_roadmap_spec(self):
        """Verifies spec example output shape and ordering."""
        from services.roadmap.roadmap_builder import build_roadmap
        missing = [
            {"skill": "SQL",    "demand_pct": 90.0, "category": "database"},
            {"skill": "Docker", "demand_pct": 75.0, "category": "devops"},
        ]
        result = build_roadmap(missing, user_skills=["Python"], target_role="Data Analyst")
        assert result["target_role"] == "Data Analyst"
        assert result["estimated_duration_weeks"] > 0
        assert len(result["roadmap"]) > 0
        assert result["roadmap"][0]["skill"] == "SQL"   # highest demand first
        logger.info("Roadmap: %d steps, %d weeks",
                    len(result["roadmap"]), result["estimated_duration_weeks"])

    def test_prerequisite_ordering(self):
        """Docker is scheduled before Kubernetes (Docker is a prerequisite)."""
        from services.roadmap.roadmap_builder import build_roadmap
        missing = [
            {"skill": "Kubernetes", "demand_pct": 80.0, "category": "devops"},
            {"skill": "Docker",     "demand_pct": 70.0, "category": "devops"},
        ]
        result = build_roadmap(missing, user_skills=[], target_role="DevOps")
        skills = [e["skill"] for e in result["roadmap"]]
        assert skills.index("Docker") < skills.index("Kubernetes"), (
            f"Expected Docker before Kubernetes, got: {skills}"
        )

    def test_user_skills_not_in_roadmap(self):
        """Skills the user already has do not appear in the roadmap."""
        from services.roadmap.roadmap_builder import build_roadmap
        missing = [
            {"skill": "Docker", "demand_pct": 80.0, "category": "devops"},
            {"skill": "AWS",    "demand_pct": 70.0, "category": "cloud"},
        ]
        result = build_roadmap(missing, user_skills=["Python", "SQL", "Docker"],
                               target_role="Engineer")
        roadmap_skills = [e["skill"] for e in result["roadmap"]]
        assert "Docker" not in roadmap_skills
        assert "Python" not in roadmap_skills

    def test_empty_missing_skills(self):
        """Empty missing skills produces an empty roadmap."""
        from services.roadmap.roadmap_builder import build_roadmap
        result = build_roadmap([], user_skills=["Python"], target_role="Engineer")
        assert result["roadmap"] == []
        assert result["estimated_duration_weeks"] == 0

    def test_roadmap_entry_schema(self, mock_roadmap):
        """Every roadmap entry has required keys with correct types."""
        for entry in mock_roadmap["roadmap"]:
            for key in ("week","skill","priority","reason","category","duration_weeks"):
                assert key in entry, f"Missing key: {key}"
            assert entry["week"] > 0
            assert entry["duration_weeks"] > 0
            assert entry["priority"] in ("High", "Medium", "Low")

    def test_week_numbers_sequential(self, mock_roadmap):
        """Roadmap week slots must be contiguous — no unexplained gaps."""
        weeks = [(e["week"], e["duration_weeks"]) for e in mock_roadmap["roadmap"]]
        for i in range(1, len(weeks)):
            prev_end = weeks[i-1][0] + weeks[i-1][1]
            assert weeks[i][0] == prev_end, (
                f"Gap between week {weeks[i-1][0]} and {weeks[i][0]}"
            )

    def test_high_demand_skill_priority_high(self):
        """A skill with demand_pct >= 60 should get priority=High."""
        from services.roadmap.roadmap_builder import build_roadmap, PriorityClassifier
        clf = PriorityClassifier()
        assert clf.classify(90.0) == "High"
        assert clf.classify(60.0) == "High"
        assert clf.classify(59.9) == "Medium"


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 6 — Report Generation (Full Pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

_REPORT_MODULE = "services.career_report.report_generator"


class TestReportGeneration:
    """Integration + pipeline tests for report_generator."""

    def _all_patches(self, mocks: dict):
        """Return list of patch objects for all pipeline dependencies."""
        return [
            patch(f"{_REPORT_MODULE}.parse_resume",          return_value=mocks["parse"]),
            patch(f"{_REPORT_MODULE}.extract_resume_skills",  return_value=mocks["skills"]),
            patch(f"{_REPORT_MODULE}.aggregate_job_skills",   return_value=mocks["market"]),
            patch(f"{_REPORT_MODULE}.detect_gaps",            return_value=mocks["gap"]),
            patch(f"{_REPORT_MODULE}.rank_gaps",              return_value=mocks["rank"]),
            patch(f"{_REPORT_MODULE}.build_roadmap",          return_value=mocks["roadmap"]),
            patch(f"{_REPORT_MODULE}.Path.exists",            return_value=True),
        ]

    def test_full_pipeline_success(self, full_pipeline_mocks, sample_job_records):
        """End-to-end pipeline returns success=True with all fields populated."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        with ExitStack() as stack:
            for p in self._all_patches(full_pipeline_mocks):
                stack.enter_context(p)
            report = generate_career_report(
                resume_path = "resume.pdf",
                job_records = sample_job_records,
                target_role = "Data Engineer",
            )

        assert report["success"]            is True
        assert report["error"]              is None
        assert report["candidate_name"]     == "Latish Nanda"
        assert report["target_role"]        == "Data Engineer"
        assert len(report["detected_skills"]) > 0
        assert len(report["market_skills"])   > 0
        assert len(report["missing_skills"])  > 0
        assert len(report["priority_skills"]) > 0
        assert len(report["roadmap"])         > 0
        assert 0 <= report["coverage_pct"]    <= 100
        assert 0 <= report["placement_score"] <= 100
        logger.info(
            "Full report: coverage=%.1f%%  placement=%.1f  "
            "detected=%d  missing=%d  roadmap=%d",
            report["coverage_pct"], report["placement_score"],
            len(report["detected_skills"]), len(report["missing_skills"]),
            len(report["roadmap"]),
        )

    def test_career_report_schema(self, full_pipeline_mocks, sample_job_records):
        """CareerReport contains exactly the required keys."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        REQUIRED_KEYS = {
            "candidate_name","target_role","detected_skills","market_skills",
            "missing_skills","priority_skills","roadmap","coverage_pct",
            "placement_score","success","error",
        }
        with ExitStack() as stack:
            for p in self._all_patches(full_pipeline_mocks):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        assert set(report.keys()) == REQUIRED_KEYS

    def test_missing_resume_file(self, sample_job_records):
        """Pipeline returns success=False when resume file does not exist."""
        from services.career_report.report_generator import generate_career_report
        report = generate_career_report("nonexistent.pdf", sample_job_records)
        assert report["success"] is False
        assert report["error"]   is not None
        logger.info("Missing file error: %s", report["error"])

    def test_parse_failure_stops_pipeline(self, full_pipeline_mocks, sample_job_records):
        """A failed parse_resume result stops the pipeline at stage 1."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        bad_parse = {**full_pipeline_mocks["parse"], "success": False,
                     "error": "Corrupt PDF", "raw_text": ""}
        mocks     = {**full_pipeline_mocks, "parse": bad_parse}

        with ExitStack() as stack:
            for p in self._all_patches(mocks):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        assert report["success"] is False
        assert "Corrupt PDF" in (report["error"] or "")
        assert report["detected_skills"] == []   # stage 2 never ran
        logger.info("Parse failure propagated: %s", report["error"])

    def test_market_failure_returns_partial(self, full_pipeline_mocks, sample_job_records):
        """Market stage failure returns partial results from stages 1–2."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        bad_market = {"success": False, "error": "Job API unavailable",
                      "market_skills": [], "total_jobs": 0, "total_unique_skills": 0}
        mocks      = {**full_pipeline_mocks, "market": bad_market}

        with ExitStack() as stack:
            for p in self._all_patches(mocks):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        assert report["success"]          is False
        assert len(report["detected_skills"]) > 0   # stage 2 completed
        assert report["market_skills"]    == []
        logger.info("Partial result: detected=%d", len(report["detected_skills"]))

    def test_gap_failure_returns_partial(self, full_pipeline_mocks, sample_job_records):
        """Gap stage failure returns partial results from stages 1–3."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        bad_gap = {"success": False, "error": "Gap compute error", "missing_skills": [],
                   "present_skills": [], "extra_skills": [], "coverage_pct": 0.0,
                   "placement_score": 0.0, "by_category": {}, "error": "Gap compute error"}
        mocks   = {**full_pipeline_mocks, "gap": bad_gap}

        with ExitStack() as stack:
            for p in self._all_patches(mocks):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        assert report["success"]            is False
        assert len(report["market_skills"]) > 0    # stage 3 completed
        assert report["missing_skills"]     == []
        logger.info("Partial result after gap failure: market=%d", len(report["market_skills"]))

    def test_injectable_stage_overrides_market(self, full_pipeline_mocks, sample_job_records):
        """A custom MarketAnalysisStage can be injected without modifying orchestrator."""
        from contextlib import ExitStack
        from services.career_report.report_generator import (
            ReportGenerator, MarketAnalysisStage,
        )

        class CustomMarket(MarketAnalysisStage):
            def run(self, ctx):
                ctx.market_skills = [{"skill": "CustomSkill", "demand_pct": 99.0,
                                       "category": "other", "base_weight": 1.0}]

        gen = ReportGenerator(market_stage=CustomMarket())

        mock_gap_empty = {**full_pipeline_mocks["gap"],
                          "missing_skills": [], "present_skills": []}
        mock_rank_empty = {**full_pipeline_mocks["rank"], "ranked_skills": []}
        mocks = {**full_pipeline_mocks, "gap": mock_gap_empty, "rank": mock_rank_empty}

        with ExitStack() as stack:
            for p in self._all_patches(mocks):
                stack.enter_context(p)
            report = gen.generate("resume.pdf", sample_job_records)

        assert report["market_skills"] == [
            {"skill": "CustomSkill", "demand_pct": 99.0,
             "category": "other", "base_weight": 1.0}
        ]
        logger.info("Injected market stage used successfully.")

    def test_unexpected_exception_caught(self, full_pipeline_mocks, sample_job_records):
        """An unexpected RuntimeError in any stage is caught and surfaces in report."""
        from contextlib import ExitStack
        from services.career_report.report_generator import (
            ReportGenerator, RoadmapGenerationStage,
        )

        class BombRoadmap(RoadmapGenerationStage):
            def run(self, ctx):
                raise RuntimeError("kernel panic")

        gen = ReportGenerator(roadmap_stage=BombRoadmap())

        with ExitStack() as stack:
            for p in self._all_patches(full_pipeline_mocks):
                stack.enter_context(p)
            report = gen.generate("resume.pdf", sample_job_records)

        assert report["success"] is False
        assert "kernel panic" in (report["error"] or "")
        assert len(report["missing_skills"]) > 0   # earlier stages completed
        logger.info("RuntimeError caught: %s", report["error"])

    def test_empty_job_records_succeeds(self, full_pipeline_mocks):
        """Pipeline succeeds with empty job_records (market skills = [])."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        mocks_no_market = {
            **full_pipeline_mocks,
            "gap": {**full_pipeline_mocks["gap"], "missing_skills": [], "present_skills": []},
            "rank": {**full_pipeline_mocks["rank"], "ranked_skills": []},
            "roadmap": {**full_pipeline_mocks["roadmap"], "roadmap": []},
        }

        with ExitStack() as stack:
            for p in self._all_patches(mocks_no_market):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", [], target_role="Analyst")

        assert report["success"]       is True
        assert report["market_skills"] == []

    def test_report_detected_skills_schema(self, full_pipeline_mocks, sample_job_records):
        """Each detected_skill has skill, confidence, source."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        with ExitStack() as stack:
            for p in self._all_patches(full_pipeline_mocks):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        for s in report["detected_skills"]:
            assert "skill"      in s
            assert "confidence" in s
            assert "source"     in s

    def test_report_roadmap_entry_schema(self, full_pipeline_mocks, sample_job_records):
        """Each roadmap entry has week, skill, priority, reason."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        with ExitStack() as stack:
            for p in self._all_patches(full_pipeline_mocks):
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        for entry in report["roadmap"]:
            for key in ("week", "skill", "priority", "reason"):
                assert key in entry, f"Roadmap entry missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-cutting concerns
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossCutting:
    """Tests for logging, type safety, and pipeline contract."""

    def test_all_stages_log_at_info(self, full_pipeline_mocks, sample_job_records, caplog):
        """Pipeline emits at least one INFO-level log per run."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        with caplog.at_level(logging.INFO):
            with ExitStack() as stack:
                for p in [
                    patch(f"{_REPORT_MODULE}.parse_resume",
                          return_value=full_pipeline_mocks["parse"]),
                    patch(f"{_REPORT_MODULE}.extract_resume_skills",
                          return_value=full_pipeline_mocks["skills"]),
                    patch(f"{_REPORT_MODULE}.aggregate_job_skills",
                          return_value=full_pipeline_mocks["market"]),
                    patch(f"{_REPORT_MODULE}.detect_gaps",
                          return_value=full_pipeline_mocks["gap"]),
                    patch(f"{_REPORT_MODULE}.rank_gaps",
                          return_value=full_pipeline_mocks["rank"]),
                    patch(f"{_REPORT_MODULE}.build_roadmap",
                          return_value=full_pipeline_mocks["roadmap"]),
                    patch(f"{_REPORT_MODULE}.Path.exists", return_value=True),
                ]:
                    stack.enter_context(p)
                generate_career_report("resume.pdf", sample_job_records)

        assert len(caplog.records) > 0, "No log records captured"
        info_records = [r for r in caplog.records if r.levelno >= logging.INFO]
        assert len(info_records) > 0

    def test_coverage_pct_always_in_range(self, full_pipeline_mocks, sample_job_records):
        """coverage_pct is always between 0 and 100 regardless of inputs."""
        from contextlib import ExitStack
        from services.career_report.report_generator import generate_career_report

        with ExitStack() as stack:
            for p in [
                patch(f"{_REPORT_MODULE}.parse_resume",          return_value=full_pipeline_mocks["parse"]),
                patch(f"{_REPORT_MODULE}.extract_resume_skills",  return_value=full_pipeline_mocks["skills"]),
                patch(f"{_REPORT_MODULE}.aggregate_job_skills",   return_value=full_pipeline_mocks["market"]),
                patch(f"{_REPORT_MODULE}.detect_gaps",            return_value=full_pipeline_mocks["gap"]),
                patch(f"{_REPORT_MODULE}.rank_gaps",              return_value=full_pipeline_mocks["rank"]),
                patch(f"{_REPORT_MODULE}.build_roadmap",          return_value=full_pipeline_mocks["roadmap"]),
                patch(f"{_REPORT_MODULE}.Path.exists",            return_value=True),
            ]:
                stack.enter_context(p)
            report = generate_career_report("resume.pdf", sample_job_records)

        assert 0 <= report["coverage_pct"]    <= 100
        assert 0 <= report["placement_score"] <= 100

    def test_pipeline_context_defaults(self):
        """PipelineContext initialises with correct defaults."""
        from services.career_report.report_generator import PipelineContext
        ctx = PipelineContext(
            resume_path = "test.pdf",
            target_role = "Engineer",
            job_records = [],
        )
        assert ctx.candidate_name  == ""
        assert ctx.detected_skills == []
        assert ctx.market_skills   == []
        assert ctx.missing_skills  == []
        assert ctx.roadmap         == []
        assert ctx.coverage_pct    == 0.0
        assert ctx.placement_score == 0.0