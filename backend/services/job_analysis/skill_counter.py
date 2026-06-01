"""
skill_counter.py
─────────────────────────────────────────────────────────────────────────────
Counts skill frequency across a corpus of parsed job descriptions and
produces demand statistics ready for market_trends.py.

Pipeline position
-----------------
    jd_parser.py          → ParsedJD
        ↓  ParsedJD.skill_text
    skill_counter.py      ← YOU ARE HERE
        ↓  CorpusStats
    market_trends.py      ← consumes CorpusStats

What this module does
---------------------
1.  SINGLE-JD EXTRACTION  — scans one ParsedJD.skill_text for skill matches
                            using the skill_engine ALIAS_INDEX (n-gram, boundary-
                            safe, longest-match-first). Returns list[SkillHit].

2.  CORPUS AGGREGATION    — accepts a list of ParsedJDs (one per job posting)
                            and counts how many JDs mention each skill.
                            Frequency = (JDs mentioning skill / total JDs) × 100

3.  DEMAND STATISTICS     — for each skill: count, percentage, category,
                            seniority breakdown, remote ratio.

4.  CO-OCCURRENCE         — optional: which skills appear together most often
                            (used by market_trends.py for roadmap generation).

5.  RANKING               — skills sorted by demand percentage descending.

Output example (from market_trends.py consumer)
-------------------------------------------------
    Python        : 78%
    SQL           : 71%
    AWS           : 42%
    Docker        : 38%
    ...

Public API
----------
    SkillHit        — TypedDict: one skill found in one JD.
    JDSkillSet      — TypedDict: all skills from one JD.
    SkillStat       — TypedDict: aggregated stat for one skill across corpus.
    CorpusStats     — TypedDict: full result of count_corpus().

    extract_skills_from_jd(parsed_jd)           -> JDSkillSet
    count_corpus(parsed_jds, min_count)          -> CorpusStats
    count_single(skill_text)                     -> JDSkillSet  (convenience)
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from itertools import combinations
from typing import TypedDict

from job_analysis.jd_parser import ParsedJD
from skill_engine.skill_dictionary import ALIAS_INDEX, get_entry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_NGRAM          = 4          # max phrase length for skill matching
_MIN_CORPUS_COUNT   = 2          # default: skill must appear in ≥ 2 JDs
_COOCCUR_TOP_N      = 20         # top N co-occurring pairs to track

# Boundary-safe pattern: word char must NOT surround the match
_WORD_CHAR_RE = re.compile(r"\w")

# Token extractor — same as skill_extractor.py for consistency
_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]"
    r"[A-Za-z0-9#\-]*"
    r"(?:[.+][A-Za-z0-9][A-Za-z0-9#\-]*)*"
    r"\+*"
)


# ── Return types ──────────────────────────────────────────────────────────────

class SkillHit(TypedDict):
    canonical:    str        # "Python", "XGBoost", …
    matched_text: str        # surface form that triggered match
    category:     str
    base_weight:  float      # from skill_dictionary


class JDSkillSet(TypedDict):
    skill_text:   str        # the input text that was scanned
    hits:         list[SkillHit]
    unique_skills: list[str] # deduplicated canonical names


class SkillStat(TypedDict):
    skill:          str
    category:       str
    count:          int      # number of JDs mentioning this skill
    percentage:     float    # count / total_jds * 100, rounded to 1 dp
    base_weight:    float    # lexical confidence from dictionary
    demand_score:   float    # percentage × base_weight (weighted rank signal)


class CorpusStats(TypedDict):
    success:        bool
    total_jds:      int
    total_unique_skills: int
    skills:         list[SkillStat]          # sorted by percentage desc
    by_category:    dict[str, list[SkillStat]]
    cooccurrence:   dict[str, dict[str, int]] # skill → {co_skill: count}
    error:          str | None


# ── Token + n-gram helpers ────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i: i + n]) for i in range(len(tokens) - n + 1)]


def _boundary_ok(text: str, surface: str) -> bool:
    """True if `surface` appears in `text` with word boundaries."""
    pattern = re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", re.IGNORECASE)
    return bool(pattern.search(text))


# ── Single-JD skill extraction ────────────────────────────────────────────────

def extract_skills_from_jd(parsed_jd: ParsedJD) -> JDSkillSet:
    """
    Extract all skills from one ParsedJD's skill_text.

    Uses longest-match-first n-gram scanning against ALIAS_INDEX.
    Consumed token positions are marked to avoid double-counting
    ("Machine Learning" should not also match "Machine" or "Learning").

    Parameters
    ----------
    parsed_jd : ParsedJD
        Output of jd_parser.parse_jd()["parsed"].

    Returns
    -------
    JDSkillSet with hits (may contain duplicates from multiple mentions)
    and unique_skills (deduplicated canonical list).
    """
    skill_text = parsed_jd.get("skill_text", "") or ""

    if not skill_text.strip():
        return JDSkillSet(skill_text=skill_text, hits=[], unique_skills=[])

    tokens          = _tokenize(skill_text)
    hits:  list[SkillHit] = []
    seen_canonicals: set[str] = set()
    consumed:        set[int] = set()   # token indices already matched

    # Longest match first
    for n in range(_MAX_NGRAM, 0, -1):
        for i, phrase in enumerate(_ngrams(tokens, n)):
            span = set(range(i, i + n))
            if span & consumed:
                continue

            canonical = ALIAS_INDEX.get(phrase.lower())
            if canonical is None:
                continue

            if not _boundary_ok(skill_text, phrase):
                continue

            entry = get_entry(canonical)
            if entry is None:
                continue

            consumed |= span
            hits.append(SkillHit(
                canonical    = canonical,
                matched_text = phrase,
                category     = entry["category"],
                base_weight  = entry["weight"],
            ))
            seen_canonicals.add(canonical)

    unique_skills = sorted(seen_canonicals)
    logger.debug(
        "extract_skills_from_jd: %d hits, %d unique skills.",
        len(hits), len(unique_skills),
    )

    return JDSkillSet(
        skill_text    = skill_text,
        hits          = hits,
        unique_skills = unique_skills,
    )


def count_single(skill_text: str) -> JDSkillSet:
    """
    Convenience wrapper: extract skills from a raw skill_text string
    without needing a full ParsedJD object.

    Useful for quick ad-hoc analysis or testing.
    """
    dummy: ParsedJD = {   # type: ignore[typeddict-item]
        "skill_text": skill_text,
        "raw_text": skill_text, "clean_text": skill_text,
        "sections": {}, "sentences": [],
        "title": None, "seniority": None,
        "employment_type": None, "is_remote": False,
        "word_count": 0, "char_count": 0,
    }
    return extract_skills_from_jd(dummy)


# ── Corpus aggregation ────────────────────────────────────────────────────────

def count_corpus(
    parsed_jds: list[ParsedJD],
    min_count: int = _MIN_CORPUS_COUNT,
) -> CorpusStats:
    """
    Count skill demand across a corpus of parsed job descriptions.

    Parameters
    ----------
    parsed_jds : list[ParsedJD]
        List of ParsedJD dicts (from jd_parser.parse_jd()["parsed"]).
        Each represents one job posting.
    min_count : int
        Skills appearing in fewer than this many JDs are excluded from output.
        Default 2 (removes singleton noise in large corpora).
        Set to 1 to include all detected skills.

    Returns
    -------
    CorpusStats
        {
          "success":             True,
          "total_jds":           50,
          "total_unique_skills": 34,
          "skills": [
            {"skill": "Python",  "category": "programming_language",
             "count": 39, "percentage": 78.0, "base_weight": 0.95,
             "demand_score": 74.1},
            {"skill": "SQL",     "count": 35, "percentage": 70.0, ...},
            ...
          ],
          "by_category": {
            "machine_learning": [...],
            "programming_language": [...],
            ...
          },
          "cooccurrence": {
            "Python": {"SQL": 31, "Docker": 28, ...},
            ...
          },
          "error": None
        }

    Notes
    -----
    - Frequency = (JDs that mention skill ≥ 1 time) / total_jds × 100.
      A skill mentioned 5 times in one JD counts as 1 for frequency.
    - demand_score = percentage × base_weight.  Provides a tie-breaker
      between skills at the same percentage: "XGBoost" (weight 1.0)
      ranks above "R" (weight 0.7) at equal raw counts.
    - Co-occurrence is symmetric: if Python co-occurs with SQL, both
      Python→SQL and SQL→Python are recorded.
    """
    if not isinstance(parsed_jds, list):
        msg = f"count_corpus expects list, got {type(parsed_jds).__name__}"
        logger.error(msg)
        return CorpusStats(
            success=False, total_jds=0, total_unique_skills=0,
            skills=[], by_category={}, cooccurrence={}, error=msg,
        )

    total = len(parsed_jds)
    if total == 0:
        return CorpusStats(
            success=True, total_jds=0, total_unique_skills=0,
            skills=[], by_category={}, cooccurrence={}, error=None,
        )

    logger.info("count_corpus: processing %d JDs  min_count=%d", total, min_count)

    # skill → number of JDs that mention it (each JD counted once)
    mention_count:   dict[str, int]   = defaultdict(int)
    # skill → SkillHit metadata (keep last seen; all hits have same category)
    skill_meta:      dict[str, SkillHit] = {}
    # co-occurrence: skill_a → skill_b → count of JDs where both appear
    cooccur:         dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for jd in parsed_jds:
        if not isinstance(jd, dict):
            logger.warning("Skipping non-dict JD entry: %s", type(jd))
            continue

        jd_skills = extract_skills_from_jd(jd)
        unique     = jd_skills["unique_skills"]

        for canonical in unique:
            mention_count[canonical] += 1

        # Store metadata from hits
        for hit in jd_skills["hits"]:
            if hit["canonical"] not in skill_meta:
                skill_meta[hit["canonical"]] = hit

        # Co-occurrence (pairs within this JD)
        for a, b in combinations(sorted(unique), 2):
            cooccur[a][b] += 1
            cooccur[b][a] += 1

    # ── Build SkillStat list ──────────────────────────────────────────────────
    stats: list[SkillStat] = []

    for canonical, count in mention_count.items():
        if count < min_count:
            continue

        meta       = skill_meta.get(canonical)
        category   = meta["category"]   if meta else "other"
        base_weight= meta["base_weight"]if meta else 0.85
        pct        = round(count / total * 100, 1)
        demand     = round(pct * base_weight, 2)

        stats.append(SkillStat(
            skill        = canonical,
            category     = category,
            count        = count,
            percentage   = pct,
            base_weight  = base_weight,
            demand_score = demand,
        ))

    # Sort by percentage desc, then demand_score desc as tie-breaker
    stats.sort(key=lambda s: (-s["percentage"], -s["demand_score"]))

    # ── Group by category ─────────────────────────────────────────────────────
    by_category: dict[str, list[SkillStat]] = defaultdict(list)
    for s in stats:
        by_category[s["category"]].append(s)

    # ── Trim co-occurrence to top-N per skill ─────────────────────────────────
    cooccur_trimmed: dict[str, dict[str, int]] = {}
    for skill, partners in cooccur.items():
        if skill in mention_count and mention_count[skill] >= min_count:
            top = dict(sorted(partners.items(), key=lambda x: -x[1])[:_COOCCUR_TOP_N])
            cooccur_trimmed[skill] = top

    logger.info(
        "count_corpus complete: %d unique skills (after min_count=%d filter), "
        "top skill=%r at %.1f%%",
        len(stats), min_count,
        stats[0]["skill"] if stats else "none",
        stats[0]["percentage"] if stats else 0.0,
    )

    return CorpusStats(
        success             = True,
        total_jds           = total,
        total_unique_skills = len(stats),
        skills              = stats,
        by_category         = dict(by_category),
        cooccurrence        = cooccur_trimmed,
        error               = None,
    )