"""
job_scraper.py
─────────────────────────────────────────────────────────────────────────────
Collects raw job listings from three public APIs:

    1. Adzuna      — REST API, requires app_id + app_key (free tier available)
    2. JSearch     — RapidAPI-hosted, requires X-RapidAPI-Key
    3. RemoteOK    — Public JSON feed, no auth required

Design principles
-----------------
- Every source is isolated: a failure in one never aborts the others.
- All pagination is handled internally; callers just set max_results.
- Raw API responses are normalised into a common RawJob schema before
  returning, so job_cleaner.py only deals with one shape.
- No scraping, no Selenium, no LinkedIn. API calls only.
- Structured logging on every operation (request, response, error, retry).
- Exponential back-off with jitter on transient HTTP errors (429, 5xx).
- API credentials come from environment variables — never hardcoded.

Environment variables required
-------------------------------
    ADZUNA_APP_ID       — Adzuna application ID
    ADZUNA_APP_KEY      — Adzuna API key
    JSEARCH_API_KEY     — RapidAPI key for JSearch

    RemoteOK needs no credentials.

Public API
----------
    RawJob              — TypedDict: one normalised job record.
    ScrapeResult        — TypedDict: result envelope from one source.
    JobScraper          — Main class. Instantiate once, call scrape_all().

    scrape_all(query, location, max_per_source) -> list[RawJob]
        Calls all three sources concurrently and returns merged raw jobs.

    scrape_adzuna(...)  → ScrapeResult
    scrape_jsearch(...) → ScrapeResult
    scrape_remoteok(...)→ ScrapeResult
        Individual source scrapers (useful for testing / selective runs).

Output schema (RawJob)
----------------------
    {
        "job_id"       : str,   # source-prefixed unique ID
        "title"        : str,
        "company"      : str,
        "location"     : str,
        "description"  : str,
        "url"          : str,
        "salary_min"   : float | None,
        "salary_max"   : float | None,
        "currency"     : str | None,
        "posted_at"    : str | None,   # ISO-8601 or raw string from API
        "source"       : str,          # "adzuna" | "jsearch" | "remoteok"
        "raw"          : dict,         # original API payload (unmodified)
    }
"""

from __future__ import annotations

import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, TypedDict

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Types ─────────────────────────────────────────────────────────────────────

class RawJob(TypedDict):
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
    raw:         dict


class ScrapeResult(TypedDict):
    source:    str
    success:   bool
    jobs:      list[RawJob]
    total:     int           # total available on source (may exceed max_results)
    fetched:   int           # actually fetched in this run
    error:     str | None


# ── Constants ─────────────────────────────────────────────────────────────────

_DEFAULT_TIMEOUT   = 15          # seconds per HTTP request
_DEFAULT_MAX_JOBS  = 50          # per source
_PAGE_SIZE_ADZUNA  = 20          # Adzuna results per page (max 50, kept lower)
_PAGE_SIZE_JSEARCH = 10          # JSearch results per page
_PAGE_SIZE_REMOTE  = 300         # RemoteOK returns everything in one call

_RETRY_STATUSES   = {429, 500, 502, 503, 504}
_MAX_RETRIES      = 3
_BACKOFF_BASE     = 1.5          # seconds (× attempt number + jitter)
_BACKOFF_JITTER   = 0.5

# API base URLs
_ADZUNA_BASE   = "https://api.adzuna.com/v1/api/jobs"
_JSEARCH_BASE  = "https://jsearch.p.rapidapi.com/search"
_REMOTEOK_BASE = "https://remoteok.com/api"


# ── HTTP session factory ──────────────────────────────────────────────────────

def _make_session(retries: int = _MAX_RETRIES) -> Session:
    """
    Build a requests Session with:
    - Connection pooling
    - Automatic retry on connection errors (not on HTTP errors — those are
      handled manually for logging and jitter control)
    - 15-second timeout default
    """
    session = Session()
    adapter = HTTPAdapter(
        max_retries=Retry(
            total=retries,
            backoff_factor=0.3,
            status_forcelist=[],    # manual retry loop handles HTTP errors
            allowed_methods=["GET"],
        )
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ── Retry helper ──────────────────────────────────────────────────────────────

def _get_with_retry(
    session: Session,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    source: str = "unknown",
    timeout: int = _DEFAULT_TIMEOUT,
) -> Response:
    """
    GET with exponential back-off + jitter on retryable HTTP status codes.

    Raises requests.HTTPError on non-retryable failures.
    Raises requests.RequestException on network failures after retries.
    """
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 2):   # +1 for the first attempt
        try:
            logger.debug(
                "[%s] GET %s  params=%s  attempt=%d",
                source, url, params, attempt,
            )
            resp = session.get(
                url, params=params, headers=headers, timeout=timeout
            )

            if resp.status_code in _RETRY_STATUSES:
                wait = _BACKOFF_BASE * attempt + random.uniform(0, _BACKOFF_JITTER)
                logger.warning(
                    "[%s] HTTP %d — retrying in %.1fs (attempt %d/%d)",
                    source, resp.status_code, wait, attempt, _MAX_RETRIES + 1,
                )
                time.sleep(wait)
                last_exc = requests.HTTPError(
                    f"HTTP {resp.status_code}", response=resp
                )
                continue

            resp.raise_for_status()
            logger.debug("[%s] HTTP %d — OK", source, resp.status_code)
            return resp

        except requests.RequestException as exc:
            wait = _BACKOFF_BASE * attempt + random.uniform(0, _BACKOFF_JITTER)
            logger.warning(
                "[%s] Request error on attempt %d/%d: %s — retrying in %.1fs",
                source, attempt, _MAX_RETRIES + 1, exc, wait,
            )
            last_exc = exc
            if attempt <= _MAX_RETRIES:
                time.sleep(wait)

    raise last_exc or requests.RequestException(
        f"[{source}] All {_MAX_RETRIES + 1} attempts exhausted for {url}"
    )


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    return str(val).strip() or default


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _error_result(source: str, message: str) -> ScrapeResult:
    logger.error("[%s] Scrape failed: %s", source, message)
    return ScrapeResult(
        source=source, success=False, jobs=[],
        total=0, fetched=0, error=message,
    )


# ── Source 1: Adzuna ──────────────────────────────────────────────────────────

def _normalise_adzuna(item: dict) -> RawJob:
    """Map one Adzuna result dict to RawJob."""
    salary      = item.get("salary_min"), item.get("salary_max")
    location    = item.get("location", {})
    area        = location.get("display_name", "") if isinstance(location, dict) else ""
    company     = item.get("company", {})
    company_str = company.get("display_name", "") if isinstance(company, dict) else ""

    return RawJob(
        job_id      = f"adzuna_{item.get('id', '')}",
        title       = _safe_str(item.get("title")),
        company     = _safe_str(company_str),
        location    = _safe_str(area),
        description = _safe_str(item.get("description")),
        url         = _safe_str(item.get("redirect_url")),
        salary_min  = _safe_float(salary[0]),
        salary_max  = _safe_float(salary[1]),
        currency    = None,           # Adzuna doesn't always return currency
        posted_at   = _safe_str(item.get("created")) or None,
        source      = "adzuna",
        raw         = item,
    )


def scrape_adzuna(
    query: str,
    location: str = "",
    max_results: int = _DEFAULT_MAX_JOBS,
    country: str = "gb",
) -> ScrapeResult:
    """
    Scrape jobs from Adzuna API with automatic pagination.

    Parameters
    ----------
    query      : Job search keywords ("data engineer", "ML engineer")
    location   : City or region string (optional)
    max_results: Cap on total jobs to fetch
    country    : Two-letter country code (gb, us, in, au, …)

    Credentials (env vars)
    ----------------------
    ADZUNA_APP_ID, ADZUNA_APP_KEY
    """
    app_id  = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()

    if not app_id or not app_key:
        return _error_result(
            "adzuna",
            "Missing env vars: ADZUNA_APP_ID and/or ADZUNA_APP_KEY",
        )

    session   = _make_session()
    jobs: list[RawJob] = []
    page      = 1
    total_api = 0
    url       = f"{_ADZUNA_BASE}/{country}/search/{page}"

    logger.info("[adzuna] Starting scrape: query=%r location=%r max=%d",
                query, location, max_results)

    while len(jobs) < max_results:
        page_size = min(_PAGE_SIZE_ADZUNA, max_results - len(jobs))
        params: dict[str, Any] = {
            "app_id":          app_id,
            "app_key":         app_key,
            "results_per_page": page_size,
            "what":            query,
            "content-type":    "application/json",
        }
        if location:
            params["where"] = location

        url = f"{_ADZUNA_BASE}/{country}/search/{page}"

        try:
            resp = _get_with_retry(session, url, params=params, source="adzuna")
            data = resp.json()
        except Exception as exc:
            logger.error("[adzuna] Page %d failed: %s", page, exc)
            break

        results  = data.get("results", [])
        total_api = int(data.get("count", 0))

        if not results:
            logger.info("[adzuna] No more results at page %d.", page)
            break

        for item in results:
            if len(jobs) >= max_results:
                break
            try:
                jobs.append(_normalise_adzuna(item))
            except Exception as exc:
                logger.warning("[adzuna] Normalise error (skipping): %s", exc)

        logger.info(
            "[adzuna] Page %d: got %d items  total_so_far=%d  api_total=%d",
            page, len(results), len(jobs), total_api,
        )

        if len(results) < page_size or len(jobs) >= total_api:
            break   # no more pages

        page += 1

    logger.info("[adzuna] Scrape complete: %d jobs fetched.", len(jobs))
    return ScrapeResult(
        source="adzuna", success=True, jobs=jobs,
        total=total_api, fetched=len(jobs), error=None,
    )


# ── Source 2: JSearch (via RapidAPI) ─────────────────────────────────────────

def _normalise_jsearch(item: dict) -> RawJob:
    """Map one JSearch result dict to RawJob."""
    return RawJob(
        job_id      = f"jsearch_{item.get('job_id', '')}",
        title       = _safe_str(item.get("job_title")),
        company     = _safe_str(item.get("employer_name")),
        location    = ", ".join(filter(None, [
                          _safe_str(item.get("job_city")),
                          _safe_str(item.get("job_state")),
                          _safe_str(item.get("job_country")),
                      ])),
        description = _safe_str(item.get("job_description")),
        url         = _safe_str(item.get("job_apply_link")),
        salary_min  = _safe_float(item.get("job_min_salary")),
        salary_max  = _safe_float(item.get("job_max_salary")),
        currency    = _safe_str(item.get("job_salary_currency")) or None,
        posted_at   = _safe_str(item.get("job_posted_at_datetime_utc")) or None,
        source      = "jsearch",
        raw         = item,
    )


def scrape_jsearch(
    query: str,
    location: str = "",
    max_results: int = _DEFAULT_MAX_JOBS,
) -> ScrapeResult:
    """
    Scrape jobs from JSearch API (RapidAPI) with pagination.

    Credentials (env vars)
    ----------------------
    JSEARCH_API_KEY   — RapidAPI key
    """
    api_key = os.environ.get("JSEARCH_API_KEY", "").strip()

    if not api_key:
        return _error_result(
            "jsearch",
            "Missing env var: JSEARCH_API_KEY",
        )

    headers = {
        "X-RapidAPI-Key":  api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    session   = _make_session()
    jobs: list[RawJob] = []
    page      = 1
    total_api = 0

    search_query = f"{query} {location}".strip()
    logger.info("[jsearch] Starting scrape: query=%r max=%d", search_query, max_results)

    while len(jobs) < max_results:
        params: dict[str, Any] = {
            "query":       search_query,
            "page":        page,
            "num_pages":   1,
        }

        try:
            resp = _get_with_retry(
                session, _JSEARCH_BASE,
                params=params, headers=headers, source="jsearch",
            )
            data = resp.json()
        except Exception as exc:
            logger.error("[jsearch] Page %d failed: %s", page, exc)
            break

        # JSearch wraps results under "data"
        results = data.get("data") or []
        if not isinstance(results, list):
            logger.warning("[jsearch] Unexpected response shape: %s", type(results))
            break

        # JSearch doesn't always expose a total count
        total_api = max(total_api, data.get("total", len(results) + len(jobs)))

        if not results:
            logger.info("[jsearch] No more results at page %d.", page)
            break

        for item in results:
            if len(jobs) >= max_results:
                break
            try:
                jobs.append(_normalise_jsearch(item))
            except Exception as exc:
                logger.warning("[jsearch] Normalise error (skipping): %s", exc)

        logger.info(
            "[jsearch] Page %d: got %d items  total_so_far=%d",
            page, len(results), len(jobs),
        )

        if len(results) < _PAGE_SIZE_JSEARCH:
            break   # last page

        page += 1

    logger.info("[jsearch] Scrape complete: %d jobs fetched.", len(jobs))
    return ScrapeResult(
        source="jsearch", success=True, jobs=jobs,
        total=total_api, fetched=len(jobs), error=None,
    )


# ── Source 3: RemoteOK ────────────────────────────────────────────────────────

def _normalise_remoteok(item: dict) -> RawJob:
    """Map one RemoteOK item to RawJob."""
    tags     = item.get("tags") or []
    tag_str  = ", ".join(str(t) for t in tags)

    return RawJob(
        job_id      = f"remoteok_{item.get('id', item.get('slug', ''))}",
        title       = _safe_str(item.get("position")),
        company     = _safe_str(item.get("company")),
        location    = _safe_str(item.get("location")) or "Remote",
        description = _safe_str(item.get("description")) or tag_str,
        url         = _safe_str(item.get("url")),
        salary_min  = _safe_float(item.get("salary_min")),
        salary_max  = _safe_float(item.get("salary_max")),
        currency    = "USD" if (item.get("salary_min") or item.get("salary_max")) else None,
        posted_at   = _safe_str(item.get("date")) or None,
        source      = "remoteok",
        raw         = item,
    )


def scrape_remoteok(
    query: str = "",
    max_results: int = _DEFAULT_MAX_JOBS,
) -> ScrapeResult:
    """
    Fetch jobs from RemoteOK public JSON API.

    No credentials required. RemoteOK returns all listings in one response;
    optional `query` is used for client-side keyword filtering.

    RemoteOK API etiquette: set a descriptive User-Agent header.
    """
    session = _make_session()
    headers = {
        "User-Agent": "job_engine/1.0 (job collection bot; contact: your@email.com)",
        "Accept":     "application/json",
    }

    logger.info("[remoteok] Starting scrape: query=%r max=%d", query, max_results)

    try:
        resp = _get_with_retry(
            session, _REMOTEOK_BASE,
            headers=headers, source="remoteok",
        )
        raw_data = resp.json()
    except Exception as exc:
        return _error_result("remoteok", f"Request failed: {exc}")

    # RemoteOK prepends a legal notice dict as the first element
    if isinstance(raw_data, list) and raw_data and "legal" in raw_data[0]:
        raw_data = raw_data[1:]

    if not isinstance(raw_data, list):
        return _error_result("remoteok", f"Unexpected response type: {type(raw_data)}")

    total_api = len(raw_data)
    logger.info("[remoteok] Received %d listings from API.", total_api)

    # Client-side keyword filter (case-insensitive substring match)
    query_lower = query.lower().strip()
    if query_lower:
        filtered = []
        for item in raw_data:
            title   = _safe_str(item.get("position")).lower()
            company = _safe_str(item.get("company")).lower()
            desc    = _safe_str(item.get("description")).lower()
            tags    = " ".join(str(t) for t in (item.get("tags") or [])).lower()

            if any(
                query_lower in field
                for field in (title, company, desc, tags)
            ):
                filtered.append(item)
        logger.info("[remoteok] After query filter %r: %d/%d listings.",
                    query, len(filtered), total_api)
        raw_data = filtered

    jobs: list[RawJob] = []
    for item in raw_data:
        if len(jobs) >= max_results:
            break
        # Skip the legal notice dict if still present
        if not isinstance(item, dict) or "position" not in item:
            continue
        try:
            jobs.append(_normalise_remoteok(item))
        except Exception as exc:
            logger.warning("[remoteok] Normalise error (skipping): %s", exc)

    logger.info("[remoteok] Scrape complete: %d jobs fetched.", len(jobs))
    return ScrapeResult(
        source="remoteok", success=True, jobs=jobs,
        total=total_api, fetched=len(jobs), error=None,
    )


# ── Orchestrator ──────────────────────────────────────────────────────────────

class JobScraper:
    """
    Orchestrates concurrent scraping from all configured sources.

    Usage
    -----
        scraper = JobScraper()
        jobs = scraper.scrape_all("machine learning engineer", location="London")

    Each source runs in its own thread; failures are isolated.
    """

    def __init__(
        self,
        sources: list[str] | None = None,
        max_workers: int = 3,
    ) -> None:
        """
        Parameters
        ----------
        sources    : Subset of ["adzuna", "jsearch", "remoteok"].
                     Defaults to all three.
        max_workers: Thread pool size for concurrent source calls.
        """
        valid = {"adzuna", "jsearch", "remoteok"}
        self.sources    = [s for s in (sources or list(valid)) if s in valid]
        self.max_workers = max_workers
        logger.info("JobScraper initialised with sources=%s", self.sources)

    # ── Source dispatch ───────────────────────────────────────────────────────

    def _dispatch(
        self,
        source: str,
        query: str,
        location: str,
        max_results: int,
    ) -> ScrapeResult:
        try:
            if source == "adzuna":
                return scrape_adzuna(query, location, max_results)
            if source == "jsearch":
                return scrape_jsearch(query, location, max_results)
            if source == "remoteok":
                return scrape_remoteok(query, max_results)
        except Exception as exc:  # noqa: BLE001
            return _error_result(source, f"Unhandled exception: {exc}")

        return _error_result(source, f"Unknown source: {source}")

    # ── Public methods ────────────────────────────────────────────────────────

    def scrape_all(
        self,
        query: str,
        location: str = "",
        max_per_source: int = _DEFAULT_MAX_JOBS,
    ) -> list[RawJob]:
        """
        Scrape all configured sources concurrently.

        Parameters
        ----------
        query          : Job search keywords.
        location       : Location hint (not used by RemoteOK).
        max_per_source : Max jobs to fetch from each source.

        Returns
        -------
        list[RawJob]
            Merged raw jobs from all successful sources, in arrival order.
            Deduplication is handled downstream by job_cleaner.py.
        """
        logger.info(
            "scrape_all: query=%r location=%r max_per_source=%d sources=%s",
            query, location, max_per_source, self.sources,
        )

        all_jobs: list[RawJob] = []
        results:  list[ScrapeResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(
                    self._dispatch, src, query, location, max_per_source
                ): src
                for src in self.sources
            }

            for future in as_completed(futures):
                src = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result["success"]:
                        all_jobs.extend(result["jobs"])
                        logger.info(
                            "[%s] ✓ fetched=%d  total_available=%d",
                            src, result["fetched"], result["total"],
                        )
                    else:
                        logger.error(
                            "[%s] ✗ scrape failed: %s", src, result["error"]
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.error("[%s] Future raised: %s", src, exc)

        # Summary log
        success_count = sum(1 for r in results if r["success"])
        logger.info(
            "scrape_all complete: %d/%d sources OK  total_jobs=%d",
            success_count, len(self.sources), len(all_jobs),
        )

        return all_jobs

    def scrape_source(
        self,
        source: str,
        query: str,
        location: str = "",
        max_results: int = _DEFAULT_MAX_JOBS,
    ) -> ScrapeResult:
        """
        Scrape a single named source. Useful for debugging or selective runs.

        Parameters
        ----------
        source : "adzuna" | "jsearch" | "remoteok"
        """
        if source not in {"adzuna", "jsearch", "remoteok"}:
            return _error_result(source, f"Unknown source '{source}'")
        return self._dispatch(source, query, location, max_results)