"""
job_scheduler.py
─────────────────────────────────────────────────────────────────────────────
Orchestrates the full job collection pipeline on a configurable schedule.

Pipeline per run
----------------
    JobScraper.scrape_all()
        ↓  list[RawJob]
    clean_jobs()
        ↓  list[CleanJob]
    JobProcessor.process_batch()
        ↓  ProcessResult
    (optional) purge_old()

Schedule modes
--------------
    INTERVAL   — run every N minutes/hours (e.g. every 2 hours)
    DAILY      — run once per day at a fixed time (e.g. "08:00")
    MANUAL     — run once immediately and exit (CLI / testing)

Features
--------
- Every pipeline stage is wrapped in try/except; one bad run never kills the loop.
- Full run metrics logged: fetched / cleaned / inserted / skipped / duration.
- Graceful shutdown on SIGINT / SIGTERM — finishes the current run, then exits.
- Optional auto-purge of records older than N days after each successful run.
- Run history kept in memory (last 100 entries) for health monitoring.
- Human-readable next-run timestamp logged after every completed run.

Public API
----------
    RunRecord           — TypedDict: metrics for one completed pipeline run.
    SchedulerConfig     — TypedDict: all tunable settings in one place.
    JobScheduler        — Main class.

    JobScheduler(config).start()          # blocking loop
    JobScheduler(config).run_once()       # single run, returns RunRecord

CLI
---
    python -m job_engine.job_scheduler --query "data engineer" --location "London"
    python -m job_engine.job_scheduler --query "ml engineer" --interval 120
    python -m job_engine.job_scheduler --query "python developer" --daily "07:00"
    python -m job_engine.job_scheduler --once
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone
from typing import TypedDict

import schedule

from job_engine.job_scraper  import JobScraper
from job_engine.job_cleaner  import clean_jobs
from job_engine.job_processor import JobProcessor

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_LOG_FORMAT  = "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── Types ─────────────────────────────────────────────────────────────────────

class RunRecord(TypedDict):
    run_id:          str          # ISO timestamp of run start
    success:         bool
    duration_secs:   float
    fetched:         int          # raw jobs from all sources
    after_clean:     int          # jobs surviving cleaner
    inserted:        int          # new jobs written to DB
    skipped:         int          # fingerprint duplicates
    duplicates_removed: int       # removed by cleaner
    error:           str | None


class SchedulerConfig(TypedDict, total=False):
    # Search
    query:           str          # job search keywords  (required)
    location:        str          # location hint
    max_per_source:  int          # default 50

    # Sources
    sources:         list[str]    # default all three

    # Schedule
    mode:            str          # "interval" | "daily" | "manual"
    interval_mins:   int          # used when mode="interval"
    daily_time:      str          # "HH:MM" used when mode="daily"

    # Storage
    db_path:         str

    # Maintenance
    purge_after_days: int | None  # None = no auto-purge

    # Cleaning
    fuzzy_threshold:          float
    min_description_chars:    int


# ── Defaults ──────────────────────────────────────────────────────────────────

_DEFAULTS: SchedulerConfig = {
    "query":                  "software engineer",
    "location":               "",
    "max_per_source":         50,
    "sources":                ["adzuna", "jsearch", "remoteok"],
    "mode":                   "interval",
    "interval_mins":          120,
    "daily_time":             "08:00",
    "db_path":                "job_engine/jobs.json",
    "purge_after_days":       None,
    "fuzzy_threshold":        0.85,
    "min_description_chars":  20,
}

_MAX_HISTORY = 100


# ── JobScheduler ──────────────────────────────────────────────────────────────

class JobScheduler:
    """
    Runs the scrape → clean → process pipeline on a schedule.

    Usage
    -----
        config = SchedulerConfig(
            query="machine learning engineer",
            location="London",
            mode="interval",
            interval_mins=60,
        )
        scheduler = JobScheduler(config)
        scheduler.start()           # blocks until SIGINT/SIGTERM

    Or for a single run (testing / CLI):
        record = scheduler.run_once()
    """

    def __init__(self, config: SchedulerConfig | None = None) -> None:
        self.cfg: SchedulerConfig = {**_DEFAULTS, **(config or {})}   # type: ignore[misc]
        self._history: deque[RunRecord] = deque(maxlen=_MAX_HISTORY)
        self._running  = False
        self._run_count = 0

        self._processor = JobProcessor(self.cfg.get("db_path", _DEFAULTS["db_path"]))
        self._scraper   = JobScraper(
            sources=self.cfg.get("sources", _DEFAULTS["sources"])
        )

        # Graceful shutdown hooks
        signal.signal(signal.SIGINT,  self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        logger.info(
            "JobScheduler init: query=%r  mode=%s  sources=%s  db=%s",
            self.cfg["query"], self.cfg["mode"],
            self.cfg["sources"], self.cfg["db_path"],
        )

    # ── Signal handling ───────────────────────────────────────────────────────

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info("Received %s — shutting down after current run.", sig_name)
        self._running = False

    # ── Core pipeline ─────────────────────────────────────────────────────────

    def run_once(self) -> RunRecord:
        """
        Execute one full scrape → clean → process cycle.

        Returns a RunRecord with metrics regardless of success or failure.
        Safe to call directly for ad-hoc or test runs.
        """
        run_id    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        t_start   = time.monotonic()
        self._run_count += 1

        logger.info(
            "── RUN #%d START  id=%s ──────────────────────────────────",
            self._run_count, run_id,
        )

        fetched = after_clean = inserted = skipped = dups_removed = 0
        error: str | None = None

        try:
            # ── Stage 1: Scrape ───────────────────────────────────────────────
            logger.info("[1/3] Scraping: query=%r  location=%r  max_per_source=%d",
                        self.cfg["query"], self.cfg.get("location", ""),
                        self.cfg.get("max_per_source", 50))

            raw_jobs = self._scraper.scrape_all(
                query          = self.cfg.get("query", ""),
                location       = self.cfg.get("location", ""),
                max_per_source = self.cfg.get("max_per_source", 50),
            )
            fetched = len(raw_jobs)
            logger.info("[1/3] Scrape complete: %d raw jobs fetched.", fetched)

            if not raw_jobs:
                logger.warning("[1/3] No jobs fetched — skipping clean + process.")
                return self._record(run_id, t_start, True,
                                    fetched, 0, 0, 0, 0, None)

            # ── Stage 2: Clean ────────────────────────────────────────────────
            logger.info("[2/3] Cleaning %d raw jobs …", fetched)

            clean_result = clean_jobs(
                raw_jobs,
                fuzzy_threshold       = self.cfg.get("fuzzy_threshold", 0.85),
                min_description_chars = self.cfg.get("min_description_chars", 20),
            )

            if not clean_result["success"]:
                raise RuntimeError(f"clean_jobs failed: {clean_result['error']}")

            after_clean   = clean_result["output_count"]
            dups_removed  = clean_result["duplicates_removed"]
            logger.info(
                "[2/3] Clean complete: %d → %d jobs  dups_removed=%d  rejected=%d",
                fetched, after_clean, dups_removed,
                len(clean_result["rejected"]),
            )

            # ── Stage 3: Process / Store ──────────────────────────────────────
            logger.info("[3/3] Processing %d clean jobs …", after_clean)

            proc_result = self._processor.process_batch(clean_result["jobs"])

            if not proc_result["success"]:
                raise RuntimeError(f"process_batch failed: {proc_result['error']}")

            inserted = proc_result["inserted"]
            skipped  = proc_result["skipped"]
            logger.info(
                "[3/3] Process complete: inserted=%d  skipped=%d  failed=%d",
                inserted, skipped, proc_result["failed"],
            )

            # ── Optional: auto-purge ──────────────────────────────────────────
            purge_days = self.cfg.get("purge_after_days")
            if purge_days is not None:
                purged = self._processor.purge_old(days=purge_days)
                logger.info("Auto-purge: removed %d records older than %d days.",
                            purged, purge_days)

        except Exception as exc:        # noqa: BLE001
            error = str(exc)
            logger.error("Pipeline error: %s", error, exc_info=True)

        return self._record(run_id, t_start, error is None,
                            fetched, after_clean, inserted, skipped,
                            dups_removed, error)

    def _record(
        self,
        run_id: str,
        t_start: float,
        success: bool,
        fetched: int,
        after_clean: int,
        inserted: int,
        skipped: int,
        dups_removed: int,
        error: str | None,
    ) -> RunRecord:
        duration = round(time.monotonic() - t_start, 2)
        record   = RunRecord(
            run_id             = run_id,
            success            = success,
            duration_secs      = duration,
            fetched            = fetched,
            after_clean        = after_clean,
            inserted           = inserted,
            skipped            = skipped,
            duplicates_removed = dups_removed,
            error              = error,
        )
        self._history.append(record)

        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(
            "── RUN #%d END %s  duration=%.1fs  "
            "fetched=%d  clean=%d  inserted=%d  skipped=%d ──",
            self._run_count, status, duration,
            fetched, after_clean, inserted, skipped,
        )
        return record

    # ── Scheduling ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Start the scheduler loop (blocking).

        Runs until SIGINT (Ctrl-C) or SIGTERM is received.
        Call run_once() directly for non-blocking / single-shot use.
        """
        mode = self.cfg.get("mode", "interval")
        self._running = True

        if mode == "manual":
            logger.info("Mode=manual: running once then exiting.")
            self.run_once()
            self._processor.close()
            return

        if mode == "interval":
            mins = self.cfg.get("interval_mins", 120)
            logger.info("Mode=interval: every %d minutes.", mins)
            # Run immediately on startup, then on schedule
            self.run_once()
            schedule.every(mins).minutes.do(self.run_once)

        elif mode == "daily":
            t = self.cfg.get("daily_time", "08:00")
            logger.info("Mode=daily: at %s every day.", t)
            self.run_once()
            schedule.every().day.at(t).do(self.run_once)

        else:
            logger.error("Unknown mode: %r — defaulting to interval=120min.", mode)
            schedule.every(120).minutes.do(self.run_once)

        logger.info("Scheduler loop started. Press Ctrl-C to stop.")

        while self._running:
            schedule.run_pending()
            next_run = schedule.next_run()
            if next_run:
                logger.debug("Next run at: %s", next_run.strftime(_DATE_FORMAT))
            time.sleep(30)   # poll every 30 seconds

        logger.info("Scheduler loop exited cleanly.")
        self._processor.close()
        schedule.clear()

    # ── Monitoring helpers ────────────────────────────────────────────────────

    @property
    def history(self) -> list[RunRecord]:
        """Return run history (newest last)."""
        return list(self._history)

    @property
    def last_run(self) -> RunRecord | None:
        """Return the most recent RunRecord or None."""
        return self._history[-1] if self._history else None

    def print_summary(self) -> None:
        """Print a human-readable summary of the last N runs to stdout."""
        if not self._history:
            print("No runs recorded yet.")
            return
        print(f"\n{'─'*70}")
        print(f"  Job Engine — Run Summary ({len(self._history)} runs)")
        print(f"{'─'*70}")
        for r in self._history:
            status = "✓" if r["success"] else "✗"
            print(
                f"  {status}  {r['run_id']}  "
                f"fetched={r['fetched']:>3}  "
                f"clean={r['after_clean']:>3}  "
                f"inserted={r['inserted']:>3}  "
                f"skipped={r['skipped']:>3}  "
                f"{r['duration_secs']:.1f}s"
                + (f"  ERR: {r['error'][:40]}" if r["error"] else "")
            )
        print(f"{'─'*70}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="job_engine.job_scheduler",
        description="Job collection pipeline scheduler.",
    )
    p.add_argument("--query",        default="software engineer",
                   help="Job search keywords")
    p.add_argument("--location",     default="",
                   help="Location hint (not used by RemoteOK)")
    p.add_argument("--sources",      nargs="+",
                   default=["adzuna", "jsearch", "remoteok"],
                   choices=["adzuna", "jsearch", "remoteok"],
                   help="Sources to scrape")
    p.add_argument("--max-per-source", type=int, default=50,
                   dest="max_per_source")

    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument("--interval", type=int, metavar="MINS",
                            help="Run every N minutes")
    mode_group.add_argument("--daily",    metavar="HH:MM",
                            help="Run once daily at this time")
    mode_group.add_argument("--once",     action="store_true",
                            help="Run once and exit")

    p.add_argument("--db",           default="job_engine/jobs.json",
                   help="Path to TinyDB JSON file")
    p.add_argument("--purge-days",   type=int, default=None,
                   dest="purge_days",
                   help="Auto-purge records older than N days after each run")
    p.add_argument("--log-level",    default="INFO",
                   choices=["DEBUG","INFO","WARNING","ERROR"],
                   dest="log_level")
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_cli()
    args   = parser.parse_args(argv)

    logging.basicConfig(
        level   = getattr(logging, args.log_level),
        format  = _LOG_FORMAT,
        datefmt = _DATE_FORMAT,
        stream  = sys.stdout,
    )

    if args.once:
        mode, interval_mins, daily_time = "manual", 120, "08:00"
    elif args.interval:
        mode, interval_mins, daily_time = "interval", args.interval, "08:00"
    elif args.daily:
        mode, interval_mins, daily_time = "daily", 120, args.daily
    else:
        mode, interval_mins, daily_time = "interval", 120, "08:00"

    config = SchedulerConfig(
        query               = args.query,
        location            = args.location,
        max_per_source      = args.max_per_source,
        sources             = args.sources,
        mode                = mode,
        interval_mins       = interval_mins,
        daily_time          = daily_time,
        db_path             = args.db,
        purge_after_days    = args.purge_days,
        fuzzy_threshold     = 0.85,
        min_description_chars = 20,
    )

    scheduler = JobScheduler(config)
    scheduler.start()
    scheduler.print_summary()


if __name__ == "__main__":
    main()