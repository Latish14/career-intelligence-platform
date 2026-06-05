import json
import random
from pathlib import Path

skills_by_role = {
    "Backend Engineer": [
        "Python", "FastAPI", "Django", "Flask",
        "PostgreSQL", "MySQL", "Docker",
        "Git", "REST API", "AWS"
    ],
    "Frontend Engineer": [
        "React", "Next.js", "JavaScript",
        "TypeScript", "HTML", "CSS",
        "Redux", "Git", "REST API"
    ],
    "Full Stack Engineer": [
        "React", "Node.js", "Express",
        "MongoDB", "PostgreSQL",
        "Docker", "AWS", "Git"
    ],
    "Data Engineer": [
        "Python", "SQL", "Spark",
        "Airflow", "Kafka",
        "AWS", "Azure", "ETL"
    ],
    "Machine Learning Engineer": [
        "Python", "Scikit-learn",
        "TensorFlow", "PyTorch",
        "MLOps", "Docker",
        "AWS", "Feature Engineering"
    ]
}

companies = [
    "Google", "Microsoft", "Amazon",
    "Netflix", "Uber", "Airbnb",
    "Infosys", "TCS", "Wipro",
    "Accenture"
]

jobs = {"jobs": {}}

job_id = 1

for role, skills in skills_by_role.items():

    for _ in range(50):

        selected = random.sample(
            skills,
            min(5, len(skills))
        )

        description = (
            f"We are hiring a {role}. "
            f"Required skills: "
            + ", ".join(selected)
        )

        jobs["jobs"][str(job_id)] = {
            "job_id": f"seed_{job_id}",
            "title": role,
            "company": random.choice(companies),
            "location": "Remote",
            "description": description,
            "source": "seed"
        }

        job_id += 1

output_path = Path("job_engine/jobs_seed.json")

with open(
    output_path,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        jobs,
        f,
        indent=2,
        ensure_ascii=False
    )

print(
    f"Created {job_id - 1} jobs at {output_path}"
)