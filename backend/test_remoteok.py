# test_scheduler_debug.py

from services.job_engine.job_scraper import JobScraper

scraper = JobScraper(
    sources=["remoteok"]
)

jobs = scraper.scrape_all(
    query="",
    max_per_source=20,
)

print("TOTAL JOBS:", len(jobs))

if jobs:
    print(jobs[0]["title"])