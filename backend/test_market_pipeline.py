import sys
import logging

logging.basicConfig(
    level=logging.INFO
)

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from services.job_engine.job_scheduler import JobScheduler

scheduler = JobScheduler(
    {
        "query": "software engineer",
        "mode": "manual",
        "sources": [
            "jsearch",
        ],
        "max_per_source": 50,
    }
)

result = scheduler.run_once()

print(result)