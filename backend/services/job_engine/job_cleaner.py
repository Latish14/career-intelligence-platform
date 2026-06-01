"""
job_cleaner.py
─────────────────────────────────────────────────────────────────────────────
Cleans, deduplicates, and validates raw job records from job_scraper.py.

Pipeline (applied in order)
----------------------------
1.  SCHEMA VALIDATION     — every RawJob must have required fields;
                            malformed records are rejected with reason logged.

2.  FIELD NORMALISATION   — title/company/location trimmed, lowercased for
                            comparison only (display values preserved);
                            salary cast to float; URL schemes enforced.

3.  EXACT DEDUPLICATION   — hash on (source, job_id) — O(1) set lookup.
                            Catches the same job fetched twice from one source.

4.  CROSS-SOURCE FUZZY DEDUP — title + company trigram similarity (rapidfuzz).
                            Catches the same role posted on Adzuna AND JSearch.
                            Configurable threshold (default 0.85).
                            When a duplicate is found, the record with the
                            most complete data (non-null salary, longer desc)
                            is kept.

5.  URL VALIDATION        — checks URL is non-empty and starts with http/https.
                            Does NOT make an HTTP request (no latency hit).

6.  DESCRIPTION FLOOR     — rejects records whose description is below
                            min_description_chars (default 20).
                            Avoids passing empty shells to job_processor.py.

Public API
----------
    CleanJob            — TypedDict: cleaned + validated output record.
    CleanResult         — TypedDict: envelope returned by clean_jobs().

    clean_jobs(
        raw_jobs,               list[RawJob]
        *,
        fuzzy_threshold,        float  default 0.85
        min_description_chars,  int    default 20
        allowed_sources,        list[str] | None
    ) -> CleanResult

    CleanResult
    ├── jobs            : list[CleanJob]
    ├── success         : bool
    ├── input_count     : int
    ├── output_count    : int
    ├── duplicates_removed : int
    ├── rejected        : list[str]    (reason strings)
    └── error           : str | None
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TypedDict
from urllib.parse import urlparse

from rapidfuzz import fuzz

from job_engine.job_scraper import RawJob

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_FUZZY_THRESHOLD   = 0.85     # title+company similarity to call "duplicate"
_DEFAULT_MIN_DESC_CHARS    = 20       # reject descriptions shorter than this
_REQUIRED_FIELDS           = {"job_id", "title", "company", "url", "source"}

# Noise words stripped before fuzzy comparison to reduce false negatives
_TITLE_NOISE_RE = re.compile(
    r"\b("
    r"senior|junior|sr|jr|lead|principal|staff|associate|mid|entry.level|"
    r"remote|contract|full.time|part.time|intern|internship|"
    r"engineer|developer|specialist|consultant|analyst|scientist|manager|"
    r"i{1,3}|iv|v{1,2}|\d+"           # level suffixes (I, II, III, IV)
    r")\b",
    re.IGNORECASE,
)


# ── Types ─────────────────────────────────────────────────────────────────────

class CleanJob(TypedDict):
    job_id:      str
    title:       str
    company:     str
    location:    str
    description: str
    url:         str
    salary_min:  float | None
    salary_max:  float | None
    currency:    str | None
    posted_at:   str | None
    source:      str
    fingerprint: str    # stable hash used by job_processor for storage dedup


class CleanResult(TypedDict):
    jobs:               list[CleanJob]
    success:            bool
    input_count:        int
    output_count:       int
    duplicates_removed: int
    rejected:           list[str]
    error:              str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(message: str) -> CleanResult:
    logger.error("clean_jobs failed: %s", message)
    return CleanResult(
        jobs=[], success=False, input_count=0,
        output_count=0, duplicates_removed=0,
        rejected=[], error=message,
    )


def _safe_str(val: object, default: str = "") -> str:
    return str(val).strip() if val is not None else default


def _safe_float(val: object) -> float | None:
    try:
        return float(val) if val is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _completeness_score(job: RawJob) -> int:
    """
    Higher = more complete record. Used to pick the keeper when deduplicating.
    One point per non-empty optional field.
    """
    score = 0
    score += 1 if _safe_float(job.get("salary_min")) is not None else 0
    score += 1 if _safe_float(job.get("salary_max")) is not None else 0
    score += 1 if job.get("currency") else 0
    score += 1 if job.get("posted_at") else 0
    score += len(_safe_str(job.get("description"))) // 100  # longer desc = better
    return score


def _fingerprint(job_id: str, title: str, company: str, source: str) -> str:
    """
    Stable 12-char hex fingerprint — used as a storage dedup key downstream.
    """
    blob = f"{job_id}|{title.lower()}|{company.lower()}|{source}".encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def _normalize_for_compare(text: str) -> str:
    """
    Lowercase, strip noise words and punctuation for fuzzy comparison.
    The display value is NOT changed — only the comparison key.
    """
    text = text.lower().strip()
    text = _TITLE_NOISE_RE.sub(" ", text)
    text = re.sub(r"[^\w\s]", " ", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(raw: RawJob, min_desc_chars: int) -> str | None:
    """
    Return an error reason string if invalid, else None.
    """
    # Required field presence
    for field in _REQUIRED_FIELDS:
        if not _safe_str(raw.get(field)):   # type: ignore[arg-type]
            return f"missing required field '{field}' (job_id={raw.get('job_id', '?')})"

    # URL format
    url = _safe_str(raw.get("url"))
    if not _is_valid_url(url):
        return f"invalid URL '{url[:60]}' (job_id={raw.get('job_id')})"

    # Description floor
    desc_len = len(_safe_str(raw.get("description")))
    if desc_len < min_desc_chars:
        return (
            f"description too short ({desc_len} < {min_desc_chars} chars) "
            f"(job_id={raw.get('job_id')})"
        )

    return None


# ── Normalisation ─────────────────────────────────────────────────────────────

def _normalise(raw: RawJob) -> CleanJob:
    """
    Map a validated RawJob to a CleanJob with normalised fields.
    """
    job_id  = _safe_str(raw["job_id"])
    title   = _safe_str(raw.get("title"))
    company = _safe_str(raw.get("company"))
    source  = _safe_str(raw.get("source"))

    return CleanJob(
        job_id      = job_id,
        title       = title,
        company     = company,
        location    = _safe_str(raw.get("location")),
        description = _safe_str(raw.get("description")),
        url         = _safe_str(raw.get("url")).rstrip("/"),
        salary_min  = _safe_float(raw.get("salary_min")),
        salary_max  = _safe_float(raw.get("salary_max")),
        currency    = _safe_str(raw.get("currency")) or None,
        posted_at   = _safe_str(raw.get("posted_at")) or None,
        source      = source,
        fingerprint = _fingerprint(job_id, title, company, source),
    )


# ── Deduplication ─────────────────────────────────────────────────────────────

def _exact_dedup(
    raws: list[RawJob],
    rejected: list[str],
) -> tuple[list[RawJob], int]:
    """
    Pass 1: remove exact duplicates by (source, job_id).
    Returns (deduped_list, count_removed).
    """
    seen: set[str] = set()
    out:  list[RawJob] = []
    removed = 0

    for raw in raws:
        key = f"{raw.get('source', '')}::{raw.get('job_id', '')}"
        if key in seen:
            logger.debug("Exact dup removed: %s", key)
            rejected.append(f"exact duplicate: {key}")
            removed += 1
        else:
            seen.add(key)
            out.append(raw)

    logger.info("Exact dedup: %d removed, %d remain.", removed, len(out))
    return out, removed


def _fuzzy_dedup(
    raws: list[RawJob],
    threshold: float,
    rejected: list[str],
) -> tuple[list[RawJob], int]:
    """
    Pass 2: cross-source fuzzy dedup on normalised title + company.

    Uses rapidfuzz token_sort_ratio (handles word-order differences):
        "Engineer Python Senior" == "Senior Python Engineer"

    For each pair of records whose similarity exceeds the threshold,
    the less complete record is dropped.

    O(n²) — acceptable for typical batch sizes (< 500 jobs per run).
    For larger datasets, consider LSH or blocked comparison.
    """
    removed = 0
    dropped: set[int] = set()   # indices already marked for removal

    # Pre-compute comparison keys once
    keys = [
        _normalize_for_compare(
            f"{r.get('title', '')} {r.get('company', '')}"
        )
        for r in raws
    ]

    for i in range(len(raws)):
        if i in dropped:
            continue
        for j in range(i + 1, len(raws)):
            if j in dropped:
                continue

            sim = fuzz.token_sort_ratio(keys[i], keys[j]) / 100.0

            if sim >= threshold:
                # Keep the more complete record
                score_i = _completeness_score(raws[i])
                score_j = _completeness_score(raws[j])
                loser   = j if score_i >= score_j else i
                winner  = i if loser == j else j

                logger.debug(
                    "Fuzzy dup (%.2f): '%s' @ %s  vs  '%s' @ %s → keep %s",
                    sim,
                    raws[i].get("title"), raws[i].get("source"),
                    raws[j].get("title"), raws[j].get("source"),
                    raws[winner].get("source"),
                )
                rejected.append(
                    f"fuzzy duplicate (sim={sim:.2f}): "
                    f"'{raws[loser].get('title')}' [{raws[loser].get('source')}] "
                    f"dropped in favour of [{raws[winner].get('source')}]"
                )
                dropped.add(loser)
                removed += 1

    out = [r for idx, r in enumerate(raws) if idx not in dropped]
    logger.info("Fuzzy dedup (threshold=%.2f): %d removed, %d remain.",
                threshold, removed, len(out))
    return out, removed


# ── Public API ────────────────────────────────────────────────────────────────

def clean_jobs(
    raw_jobs: list[RawJob],
    *,
    fuzzy_threshold: float = _DEFAULT_FUZZY_THRESHOLD,
    min_description_chars: int = _DEFAULT_MIN_DESC_CHARS,
    allowed_sources: list[str] | None = None,
) -> CleanResult:
    """
    Clean and deduplicate a list of raw job records.

    Parameters
    ----------
    raw_jobs : list[RawJob]
        Output of JobScraper.scrape_all() or any individual scraper.
    fuzzy_threshold : float  [0.0 – 1.0]
        Title+company similarity above which two records are considered
        duplicates. 0.85 is conservative; lower to catch more near-dupes.
    min_description_chars : int
        Records with shorter descriptions are rejected.
    allowed_sources : list[str] | None
        If set, only records from these sources are kept.
        E.g. ["adzuna", "remoteok"]

    Returns
    -------
    CleanResult
        {
          "jobs":               [CleanJob, ...],
          "success":            True,
          "input_count":        47,
          "output_count":       31,
          "duplicates_removed": 12,
          "rejected":           ["exact duplicate: ...", ...],
          "error":              None
        }

    Notes
    -----
    - The `fingerprint` field on each CleanJob is a 12-char SHA-256 prefix
      suitable for use as a storage/database dedup key in job_processor.py.
    - Fuzzy dedup is O(n²) — for > 500 jobs consider running per-source first.
    - No HTTP calls are made; all validation is structural.
    """
    if not isinstance(raw_jobs, list):
        return _error(f"raw_jobs must be a list, got {type(raw_jobs).__name__}")

    if not (0.0 <= fuzzy_threshold <= 1.0):
        return _error(f"fuzzy_threshold must be in [0.0, 1.0], got {fuzzy_threshold}")

    input_count = len(raw_jobs)
    logger.info(
        "clean_jobs: input=%d  fuzzy_threshold=%.2f  min_desc=%d",
        input_count, fuzzy_threshold, min_description_chars,
    )

    rejected: list[str] = []
    total_dups = 0

    # ── Step 1: source filter ─────────────────────────────────────────────────
    if allowed_sources:
        allowed_set = set(allowed_sources)
        before = len(raw_jobs)
        raw_jobs = [r for r in raw_jobs if r.get("source") in allowed_set]
        dropped = before - len(raw_jobs)
        if dropped:
            rejected.extend([f"source not allowed" for _ in range(dropped)])
            logger.info("Source filter: %d records removed.", dropped)

    # ── Step 2: schema validation + collect valid records ─────────────────────
    valid_raws: list[RawJob] = []
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            rejected.append(f"non-dict record skipped: {type(raw).__name__}")
            continue
        reason = _validate(raw, min_description_chars)
        if reason:
            rejected.append(reason)
            logger.debug("Validation failed: %s", reason)
        else:
            valid_raws.append(raw)

    logger.info(
        "Validation: %d/%d passed, %d rejected.",
        len(valid_raws), len(raw_jobs), len(raw_jobs) - len(valid_raws),
    )

    # ── Step 3: exact dedup ───────────────────────────────────────────────────
    valid_raws, exact_removed = _exact_dedup(valid_raws, rejected)
    total_dups += exact_removed

    # ── Step 4: fuzzy dedup ───────────────────────────────────────────────────
    valid_raws, fuzzy_removed = _fuzzy_dedup(valid_raws, fuzzy_threshold, rejected)
    total_dups += fuzzy_removed

    # ── Step 5: normalise to CleanJob ─────────────────────────────────────────
    clean: list[CleanJob] = []
    for raw in valid_raws:
        try:
            clean.append(_normalise(raw))
        except Exception as exc:     # noqa: BLE001
            reason = f"normalise error for {raw.get('job_id', '?')}: {exc}"
            rejected.append(reason)
            logger.warning(reason)

    logger.info(
        "clean_jobs complete: input=%d  output=%d  dups_removed=%d  rejected=%d",
        input_count, len(clean), total_dups, len(rejected),
    )

    return CleanResult(
        jobs               = clean,
        success            = True,
        input_count        = input_count,
        output_count       = len(clean),
        duplicates_removed = total_dups,
        rejected           = rejected,
        error              = None,
    )