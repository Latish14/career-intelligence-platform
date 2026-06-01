"""
resume_skills.py
─────────────────────────────────────────────────────────────────────────────
Extracts skills from a parsed resume and produces ResumeSkill records
ready for gap_detector.detect_gaps().

Pipeline position
-----------------
    resume_parser/extract_resume.py   → ResumeData
    services.skill_engine/skill_extractor.py   → list[SkillMatch]
         ↓
    resume_skills.py                  ← YOU ARE HERE
         ↓  list[ResumeSkill]
    gap_detector.py

What this module does
---------------------
1.  SKILL EXTRACTION      — wraps services.skill_engine to extract skills from the
                            resume's raw_text, producing SkillMatch records.

2.  SOURCE TAGGING        — tags each skill with how it was found:
                            "explicit"  — appears in a Skills section
                            "inferred"  — appears in experience/project text
                            "education" — appears in education section

3.  CONFIDENCE ADJUSTMENT — base confidence from skill_extractor is adjusted:
                            +0.05 if found in a skill section (explicit)
                            −0.10 if only inferred from body text
                            ×0.80 if only found once in the whole resume

4.  DEDUPLICATION         — same canonical skill from multiple sources is
                            merged; highest confidence wins, source priority:
                            explicit > inferred > education

5.  SECTION DETECTION     — lightweight header-based section splitter (no
                            dependency on jd_parser) to separate Skills /
                            Experience / Education blocks.

Public API
----------
    ResumeSkill         — TypedDict (imported by gap_detector)
    ResumeSkillResult   — TypedDict: envelope returned by extract_resume_skills()

    extract_resume_skills(resume_text, min_confidence) -> ResumeSkillResult

    ResumeSkillResult
    ├── skills          : list[ResumeSkill]
    ├── skill_count     : int
    ├── by_source       : dict[str, list[str]]   source → [skill names]
    ├── success         : bool
    └── error           : str | None
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

from services.skill_engine.skill_extractor  import extract_skills
from services.skill_engine.skill_normalizer import normalize_skills
from services.gap_analysis.gap_detector     import ResumeSkill

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_MIN_CONFIDENCE = 0.40

# Source priority for dedup (higher = preferred)
_SOURCE_RANK = {"explicit": 3, "education": 2, "inferred": 1}

# Confidence adjustments
_EXPLICIT_BOOST    = +0.05
_INFERRED_PENALTY  = -0.10
_SINGLE_MENTION_MX =  0.80   # multiplier when skill only appears once

# Section header patterns → source label
_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(
        r"(?i)^\s*(?:technical\s+)?skills?(?:\s+(?:summary|profile|set))?"
        r"(?:\s*[&/]\s*(?:tools?|technologies?))?(?:\s*and\s+technologies?)?"
        r"\s*[:\-]?\s*$", re.MULTILINE), "explicit"),

    (re.compile(
        r"(?i)^\s*(?:core\s+)?(?:competencies|proficiencies|expertise|"
        r"tech(?:nical)?\s+stack|technologies|tools)\s*[:\-]?\s*$",
        re.MULTILINE), "explicit"),

    (re.compile(
        r"(?i)^\s*(?:work\s+)?(?:experience|employment|career|history|"
        r"professional\s+background|positions?\s+held)\s*[:\-]?\s*$",
        re.MULTILINE), "inferred"),

    (re.compile(
        r"(?i)^\s*(?:projects?|personal\s+projects?|key\s+projects?|"
        r"notable\s+projects?|side\s+projects?)\s*[:\-]?\s*$",
        re.MULTILINE), "inferred"),

    (re.compile(
        r"(?i)^\s*(?:education|academic|qualifications?|degrees?|"
        r"coursework)\s*[:\-]?\s*$",
        re.MULTILINE), "education"),
]

# Generic "next section" boundary detector
_SECTION_END_RE = re.compile(
    r"(?i)^\s*(?:certifications?|awards?|achievements?|publications?|"
    r"references?|interests?|hobbies|summary|objective|profile|contact|"
    r"languages?|volunteering)\s*[:\-]?\s*$",
    re.MULTILINE,
)


# ── Return types ──────────────────────────────────────────────────────────────

class ResumeSkillResult(TypedDict):
    skills:      list[ResumeSkill]
    skill_count: int
    by_source:   dict[str, list[str]]
    success:     bool
    error:       str | None


# ── Section splitter ──────────────────────────────────────────────────────────

def _split_sections(text: str) -> dict[str, str]:
    """
    Split resume text into labelled sections.

    Returns dict[label → content].
    Unmatched content is tagged "inferred" (experience body is the default).
    """
    lines      = text.splitlines()
    boundaries: list[tuple[int, str]] = []

    for idx, line in enumerate(lines):
        for pattern, label in _SECTION_PATTERNS:
            if pattern.match(line):
                boundaries.append((idx, label))
                break
        else:
            # Also detect generic section ends
            if _SECTION_END_RE.match(line) and boundaries:
                boundaries.append((idx, "__end__"))

    sections: dict[str, str] = {}

    if not boundaries:
        sections["inferred"] = text
        return sections

    # Preamble before first header → inferred (summary / contact area)
    if boundaries[0][0] > 0:
        pre = "\n".join(lines[:boundaries[0][0]]).strip()
        if pre:
            sections["inferred"] = sections.get("inferred", "") + "\n" + pre

    for i, (start, label) in enumerate(boundaries):
        if label == "__end__":
            continue
        end = next(
            (boundaries[j][0] for j in range(i + 1, len(boundaries))),
            len(lines),
        )
        content = "\n".join(lines[start + 1: end]).strip()
        if content:
            sections[label] = sections.get(label, "") + "\n" + content

    return {k: v.strip() for k, v in sections.items() if v.strip()}


# ── Core extractor ────────────────────────────────────────────────────────────

def extract_resume_skills(
    resume_text: str,
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
) -> ResumeSkillResult:
    """
    Extract skills from a resume text and return ResumeSkill records.

    Parameters
    ----------
    resume_text : str
        Raw or cleaned resume text. Accepts output from
        resume_parser.extract_resume()["raw_text"] directly.
    min_confidence : float
        Minimum confidence threshold for including a skill.
        Default 0.40 — filters weak inferences while keeping
        well-supported skills.

    Returns
    -------
    ResumeSkillResult
        {
          "skills": [
            {"skill": "Python",  "confidence": 1.00, "source": "explicit"},
            {"skill": "Docker",  "confidence": 0.85, "source": "inferred"},
            ...
          ],
          "skill_count": 12,
          "by_source": {
            "explicit":  ["Python", "SQL", "FastAPI"],
            "inferred":  ["Docker", "AWS"],
            "education": ["Machine Learning"]
          },
          "success": True,
          "error":   None
        }

    Notes
    -----
    - Skills are alias-resolved before returning (js → JavaScript).
    - A skill found in multiple sections keeps the highest-confidence
      occurrence and the highest-priority source label.
    - Low-confidence (< 0.30 after adjustment) skills are always filtered
      regardless of min_confidence setting.
    """
    if not isinstance(resume_text, str):
        msg = f"resume_text must be str, got {type(resume_text).__name__}"
        logger.error(msg)
        return ResumeSkillResult(
            skills=[], skill_count=0, by_source={}, success=False, error=msg
        )

    if not resume_text.strip():
        return ResumeSkillResult(
            skills=[], skill_count=0, by_source={}, success=True, error=None
        )

    logger.info("extract_resume_skills: input=%d chars", len(resume_text))

    try:
        # ── Step 1: split into sections ───────────────────────────────────────
        sections = _split_sections(resume_text)
        logger.debug("Sections: %s", list(sections.keys()))

        # ── Step 2: extract skills per section ────────────────────────────────
        # canonical_lower → (ResumeSkill, mention_count)
        skill_map: dict[str, tuple[ResumeSkill, int]] = {}

        for source_label, section_text in sections.items():
            if not section_text.strip():
                continue

            # Extract via services.skill_engine
            ext_result  = extract_skills(section_text, min_confidence=0.30)
            norm_result = normalize_skills(
                [s["skill"] for s in ext_result["skills"]]
            )
            norm_map    = {n["canonical"].lower(): n for n in norm_result["skills"]}

            for sm in ext_result["skills"]:
                norm      = norm_map.get(sm["skill"].lower())
                canonical = norm["canonical"] if norm else sm["skill"]
                key       = canonical.lower()

                # Confidence adjustment by source
                raw_conf = sm["confidence"]
                if source_label == "explicit":
                    conf = min(1.0, raw_conf + _EXPLICIT_BOOST)
                elif source_label == "inferred":
                    conf = max(0.0, raw_conf + _INFERRED_PENALTY)
                else:
                    conf = raw_conf   # education — no adjustment

                # Apply normaliser multiplier
                if norm:
                    conf = round(conf * norm["confidence_multiplier"], 4)

                new_rs = ResumeSkill(
                    skill      = canonical,
                    confidence = conf,
                    source     = source_label,
                )
                new_count = 1

                if key in skill_map:
                    existing_rs, existing_count = skill_map[key]
                    new_count = existing_count + 1

                    # Keep higher confidence; prefer higher-priority source
                    keep_new = (
                        conf > existing_rs["confidence"]
                        or (
                            conf == existing_rs["confidence"]
                            and _SOURCE_RANK.get(source_label, 0)
                            > _SOURCE_RANK.get(existing_rs["source"], 0)
                        )
                    )
                    if keep_new:
                        skill_map[key] = (new_rs, new_count)
                    else:
                        skill_map[key] = (existing_rs, new_count)
                else:
                    skill_map[key] = (new_rs, new_count)

        # ── Step 3: single-mention penalty ────────────────────────────────────
        final: list[ResumeSkill] = []
        for key, (rs, count) in skill_map.items():
            conf = rs["confidence"]
            if count == 1 and rs["source"] == "inferred":
                conf = round(conf * _SINGLE_MENTION_MX, 4)

            if conf < 0.30:
                logger.debug("Filtered (low conf=%.2f): %s", conf, rs["skill"])
                continue

            if conf < min_confidence:
                logger.debug(
                    "Filtered (below threshold=%.2f conf=%.2f): %s",
                    min_confidence, conf, rs["skill"],
                )
                continue

            final.append(ResumeSkill(
                skill      = rs["skill"],
                confidence = round(conf, 4),
                source     = rs["source"],
            ))

        # ── Step 4: sort by confidence desc ───────────────────────────────────
        final.sort(key=lambda r: (-r["confidence"], r["skill"]))

        # ── Step 5: by_source index ───────────────────────────────────────────
        by_source: dict[str, list[str]] = {}
        for rs in final:
            by_source.setdefault(rs["source"], []).append(rs["skill"])

        logger.info(
            "extract_resume_skills: %d skills extracted  "
            "explicit=%d  inferred=%d  education=%d",
            len(final),
            len(by_source.get("explicit",  [])),
            len(by_source.get("inferred",  [])),
            len(by_source.get("education", [])),
        )

        return ResumeSkillResult(
            skills      = final,
            skill_count = len(final),
            by_source   = by_source,
            success     = True,
            error       = None,
        )

    except Exception as exc:        # noqa: BLE001
        msg = f"extract_resume_skills error: {exc}"
        logger.error(msg, exc_info=True)
        return ResumeSkillResult(
            skills=[], skill_count=0, by_source={},
            success=False, error=msg,
        )