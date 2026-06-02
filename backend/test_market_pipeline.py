import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from services.job_engine.job_scheduler import JobScheduler

scheduler = JobScheduler(
    {
        "query": "",
        "mode": "manual",
        "sources": ["remoteok"],
        "max_per_source": 20,
    }
)

result = scheduler.run_once()

print(result)