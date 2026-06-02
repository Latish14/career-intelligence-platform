"""
job_processor.py
─────────────────────────────────────────────────────────────────────────────
Stores, queries, and manages CleanJob records produced by job_cleaner.py.

Responsibilities
----------------
1.  STORAGE          — persists CleanJob records to a JSON file via TinyDB.
                       TinyDB is embedded, zero-config, and requires no server.
                       For production scale swap the backend to PostgreSQL or
                       MongoDB by replacing the _store_* methods only.

2.  DEDUP-ON-WRITE   — checks fingerprint before INSERT; already-stored jobs
                       are skipped, never overwritten. Idempotent by design.

3.  BATCH PROCESSING — accepts a list[CleanJob] (direct output of clean_jobs)
                       and processes atomically as a batch, logging every step.

4.  QUERY API        — filter by source, title keyword, salary range, date
                       range, and location. Returns list[CleanJob].

5.  STATS            — total stored, per-source counts, salary min/max/avg.

6.  EXPORT           — dump all or filtered records to a JSON file.

7.  PURGE            — delete records older than N days (for scheduler use).

Storage schema (TinyDB document)
---------------------------------
Each document = CleanJob fields + internal metadata:
    _inserted_at : ISO-8601 UTC timestamp of insertion
    _batch_id    : UUID of the process_batch() call that inserted it

Public API
----------
    ProcessResult       — TypedDict: result of process_batch().
    QueryResult         — TypedDict: result of query_jobs().
    StatsResult         — TypedDict: result of get_stats().
    JobProcessor        — Main class.

    JobProcessor(db_path)
        .process_batch(jobs)              -> ProcessResult
        .query_jobs(**filters)            -> QueryResult
        .get_stats()                      -> StatsResult
        .export_json(path, **filters)     -> int   (count exported)
        .purge_old(days)                  -> int   (count deleted)
        .close()
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict

from tinydb import Query, TinyDB
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from services.job_engine.job_cleaner import CleanJob

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_DB_PATH  = "job_engine/jobs.json"
_TABLE_NAME       = "jobs"
_TS_FORMAT        = "%Y-%m-%dT%H:%M:%SZ"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime(_TS_FORMAT)


def _days_ago(n: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return dt.strftime(_TS_FORMAT)


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ── Return types ──────────────────────────────────────────────────────────────

class ProcessResult(TypedDict):
    success:       bool
    batch_id:      str
    total_input:   int
    inserted:      int
    skipped:       int       # fingerprint already in DB
    failed:        int       # unexpected errors per record
    error:         str | None


class QueryResult(TypedDict):
    success:  bool
    jobs:     list[CleanJob]
    count:    int
    error:    str | None


class StatsResult(TypedDict):
    success:       bool
    total_jobs:    int
    by_source:     dict[str, int]
    salary_min:    float | None
    salary_max:    float | None
    salary_avg:    float | None
    oldest_job:    str | None
    newest_job:    str | None
    error:         str | None


# ── JobProcessor ─────────────────────────────────────────────────────────────

class JobProcessor:
    """
    Stores and queries CleanJob records using an embedded TinyDB JSON store.

    Usage
    -----
        processor = JobProcessor("job_engine/jobs.json")
        result    = processor.process_batch(clean_jobs)
        jobs      = processor.query_jobs(source="adzuna", keyword="python")
        stats     = processor.get_stats()
        processor.close()

    Thread safety
    -------------
    TinyDB with CachingMiddleware is NOT thread-safe for concurrent writes.
    For multi-threaded use, wrap process_batch() calls with a threading.Lock
    or switch the storage backend to a proper database.
    """

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._db = TinyDB(
            str(self._path),
            storage=JSONStorage,
            indent=2,
            ensure_ascii=False,
        )
        self._table = self._db.table(_TABLE_NAME)
        logger.info(
            "JobProcessor initialised: db=%s  existing_records=%d",
            self._path, len(self._table),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fingerprint_exists(self, fingerprint: str) -> bool:
        Job = Query()
        return bool(self._table.search(Job.fingerprint == fingerprint))

    def _to_document(self, job: CleanJob, batch_id: str) -> dict:
        doc = dict(job)
        doc["_inserted_at"] = _utc_now()
        doc["_batch_id"]    = batch_id
        return doc

    def _to_cleanjob(self, doc: dict) -> CleanJob:
        """Strip internal metadata fields before returning to caller."""
        return CleanJob(
            job_id      = doc.get("job_id", ""),
            title       = doc.get("title", ""),
            company     = doc.get("company", ""),
            location    = doc.get("location", ""),
            description = doc.get("description", ""),
            url         = doc.get("url", ""),
            salary_min  = _safe_float(doc.get("salary_min")),
            salary_max  = _safe_float(doc.get("salary_max")),
            currency    = doc.get("currency"),
            posted_at   = doc.get("posted_at"),
            source      = doc.get("source", ""),
            fingerprint = doc.get("fingerprint", ""),
        )

    # ── process_batch ─────────────────────────────────────────────────────────

    def process_batch(self, jobs: list[CleanJob]) -> ProcessResult:
        """
        Persist a batch of CleanJob records.

        Skips any job whose fingerprint already exists in the database
        (idempotent — safe to call multiple times with the same data).

        Parameters
        ----------
        jobs : list[CleanJob]
            Direct output of job_cleaner.clean_jobs()["jobs"].

        Returns
        -------
        ProcessResult with inserted / skipped / failed counts.
        """
        
        
        
        
        if not isinstance(jobs, list):
            msg = f"process_batch expects list, got {type(jobs).__name__}"
            logger.error(msg)
            return ProcessResult(
                success=False, batch_id="", total_input=0,
                inserted=0, skipped=0, failed=0, error=msg,
            )

        batch_id    = str(uuid.uuid4())
        total_input = len(jobs)
        inserted    = 0
        skipped     = 0
        failed      = 0

        logger.info(
            "process_batch START: batch_id=%s  total=%d",
            batch_id, total_input,
        )

        for job in jobs:
            try:
                fp = job.get("fingerprint", "")
    
                if not fp:
                    logger.warning(
                        "Job missing fingerprint, skipping: %s", job.get("job_id")
                    )
                    failed += 1
                    continue

                if self._fingerprint_exists(fp):
                    logger.debug(
                        "Skipping duplicate: fingerprint=%s  job_id=%s",
                        fp, job.get("job_id"),
                    )
                    skipped += 1
                    continue

                doc = self._to_document(job, batch_id)
        
                self._table.insert(doc)
            
                inserted += 1
                logger.debug(
                    "Inserted: job_id=%s  title=%r  source=%s",
                    job.get("job_id"), job.get("title"), job.get("source"),
                )

            except Exception as exc:        # noqa: BLE001
                failed += 1
                logger.error(
                    "Failed to insert job_id=%s: %s",
                    job.get("job_id", "?"), exc,
                )

        # Flush CachingMiddleware writes to disk
        if hasattr(self._db.storage, "flush"):
            self._db.storage.flush()

        logger.info(
            "process_batch END: batch_id=%s  inserted=%d  skipped=%d  failed=%d",
            batch_id, inserted, skipped, failed,
        )

        return ProcessResult(
            success    = True,
            batch_id   = batch_id,
            total_input= total_input,
            inserted   = inserted,
            skipped    = skipped,
            failed     = failed,
            error      = None,
        )

    # ── query_jobs ────────────────────────────────────────────────────────────

    def query_jobs(
        self,
        *,
        source:       str | None = None,
        keyword:      str | None = None,
        location:     str | None = None,
        salary_min:   float | None = None,
        salary_max:   float | None = None,
        posted_after: str | None = None,    # ISO-8601 string "2026-01-01T00:00:00Z"
        limit:        int | None = None,
    ) -> QueryResult:
        """
        Query stored jobs with optional filters.

        All filters are ANDed. Unset filters match all records.

        Parameters
        ----------
        source       : Filter by source name ("adzuna", "jsearch", "remoteok").
        keyword      : Case-insensitive substring match on title + description.
        location     : Case-insensitive substring match on location field.
        salary_min   : Only return jobs with salary_min >= this value.
        salary_max   : Only return jobs with salary_max <= this value.
        posted_after : ISO-8601 string; only jobs posted on or after this date.
        limit        : Cap result count (most recently inserted first).

        Returns
        -------
        QueryResult with matching CleanJob list.
        """
        try:
            Job  = Query()
            docs = self._table.all()

            # Apply filters in Python (TinyDB supports lambda tests)
            if source:
                docs = [d for d in docs if d.get("source") == source]

            if keyword:
                kw = keyword.lower()
                docs = [
                    d for d in docs
                    if kw in d.get("title", "").lower()
                    or kw in d.get("description", "").lower()
                ]

            if location:
                loc = location.lower()
                docs = [d for d in docs if loc in d.get("location", "").lower()]

            if salary_min is not None:
                docs = [
                    d for d in docs
                    if _safe_float(d.get("salary_min")) is not None
                    and _safe_float(d.get("salary_min")) >= salary_min
                ]

            if salary_max is not None:
                docs = [
                    d for d in docs
                    if _safe_float(d.get("salary_max")) is not None
                    and _safe_float(d.get("salary_max")) <= salary_max
                ]

            if posted_after:
                docs = [
                    d for d in docs
                    if d.get("posted_at") and d["posted_at"] >= posted_after
                ]

            # Sort: most recently inserted first
            docs.sort(key=lambda d: d.get("_inserted_at", ""), reverse=True)

            if limit:
                docs = docs[:limit]

            jobs = [self._to_cleanjob(d) for d in docs]

            logger.info(
                "query_jobs: filters={source=%r, keyword=%r, location=%r} → %d results",
                source, keyword, location, len(jobs),
            )

            return QueryResult(success=True, jobs=jobs, count=len(jobs), error=None)

        except Exception as exc:        # noqa: BLE001
            msg = f"query_jobs failed: {exc}"
            logger.error(msg)
            return QueryResult(success=False, jobs=[], count=0, error=msg)

    # ── get_stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> StatsResult:
        """
        Return aggregate statistics over all stored jobs.

        Returns
        -------
        StatsResult with total count, per-source breakdown, and salary stats.
        """
        try:
            docs = self._table.all()
            total = len(docs)

            if total == 0:
                return StatsResult(
                    success=True, total_jobs=0, by_source={},
                    salary_min=None, salary_max=None, salary_avg=None,
                    oldest_job=None, newest_job=None, error=None,
                )

            # Per-source counts
            by_source: dict[str, int] = {}
            for d in docs:
                src = d.get("source", "unknown")
                by_source[src] = by_source.get(src, 0) + 1

            # Salary stats (only over records that have salary data)
            salaries = [
                _safe_float(d.get("salary_min"))
                for d in docs
                if _safe_float(d.get("salary_min")) is not None
            ]
            sal_min = round(min(salaries), 2) if salaries else None
            sal_max = round(max(salaries), 2) if salaries else None
            sal_avg = round(sum(salaries) / len(salaries), 2) if salaries else None

            # Date range (posted_at field)
            dates = sorted(
                d["posted_at"] for d in docs
                if d.get("posted_at")
            )
            oldest = dates[0]  if dates else None
            newest = dates[-1] if dates else None

            logger.info(
                "get_stats: total=%d  sources=%s  salary_avg=%s",
                total, list(by_source.keys()), sal_avg,
            )

            return StatsResult(
                success    = True,
                total_jobs = total,
                by_source  = by_source,
                salary_min = sal_min,
                salary_max = sal_max,
                salary_avg = sal_avg,
                oldest_job = oldest,
                newest_job = newest,
                error      = None,
            )

        except Exception as exc:        # noqa: BLE001
            msg = f"get_stats failed: {exc}"
            logger.error(msg)
            return StatsResult(
                success=False, total_jobs=0, by_source={},
                salary_min=None, salary_max=None, salary_avg=None,
                oldest_job=None, newest_job=None, error=msg,
            )

    # ── export_json ───────────────────────────────────────────────────────────

    def export_json(
        self,
        output_path: str,
        **query_filters: Any,
    ) -> int:
        """
        Export matching jobs to a JSON file.

        Parameters
        ----------
        output_path : Destination file path (.json).
        **query_filters : Same keyword arguments as query_jobs().

        Returns
        -------
        int : Number of records exported.
        """
        result = self.query_jobs(**query_filters)
        if not result["success"]:
            logger.error("export_json: query failed: %s", result["error"])
            return 0

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result["jobs"], f, indent=2, ensure_ascii=False)

        logger.info(
            "export_json: %d records written to %s",
            result["count"], out_path,
        )
        return result["count"]

    # ── purge_old ─────────────────────────────────────────────────────────────

    def purge_old(self, days: int = 30) -> int:
        """
        Delete records inserted more than `days` ago.

        Parameters
        ----------
        days : Records older than this many days are removed.

        Returns
        -------
        int : Number of records deleted.
        """
        cutoff = _days_ago(days)
        Job    = Query()

        try:
            removed_ids = self._table.search(
                Job._inserted_at < cutoff
            )
            count = len(removed_ids)
            self._table.remove(Job._inserted_at < cutoff)
            if hasattr(self._db.storage, "flush"):
                self._db.storage.flush()

            logger.info(
                "purge_old: removed %d records older than %d days (cutoff=%s)",
                count, days, cutoff,
            )
            return count

        except Exception as exc:        # noqa: BLE001
            logger.error("purge_old failed: %s", exc)
            return 0

    # ── close ────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Flush and close the database."""
        try:
            if hasattr(self._db.storage, "flush"):
                self._db.storage.flush()
        except Exception:               # noqa: BLE001
            pass
        self._db.close()
        logger.info("JobProcessor closed: db=%s", self._path)

    def __enter__(self) -> "JobProcessor":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()