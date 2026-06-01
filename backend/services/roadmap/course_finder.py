"""
course_finder.py
─────────────────────────────────────────────────────────────────────────────
Matches skills from a TimelineOutput to curated learning resources and
returns an enriched timeline with course recommendations per week.

Pipeline position
-----------------
    roadmap_builder.py    → RoadmapOutput
    timeline_generator.py → TimelineOutput
         ↓
    course_finder.py      ← YOU ARE HERE
         ↓  EnrichedTimeline

Responsibilities
----------------
1. Maintain a curated internal resource catalogue (no external API calls).
2. Match each skill in the timeline to relevant resources by skill name,
   category, and learning phase.
3. Filter resources by difficulty level aligned to the week's phase.
4. Return an enriched timeline with resources attached per week.
5. Deduplicate resources across weeks for the same skill.
6. Support free and paid resource filtering.

Resource catalogue structure
-----------------------------
Each resource entry:
  - title       : str
  - provider    : str   (e.g. "freeCodeCamp", "Coursera", "Official Docs")
  - url         : str
  - is_free     : bool
  - difficulty  : str   ("Beginner" | "Intermediate" | "Advanced")
  - skills      : list[str]  (canonical skill names this resource covers)
  - format      : str   ("Video" | "Article" | "Interactive" | "Documentation")

Output shape
------------
{
  "target_role": "Data Analyst",
  "total_weeks": 7,
  "enriched_timeline": [
    {
      "week":    1,
      "skill":   "SQL",
      "summary": "Begin SQL...",
      "resources": [
        {
          "title":      "SQL Tutorial — Full Course",
          "provider":   "freeCodeCamp",
          "url":        "https://www.freecodecamp.org/learn/relational-database/",
          "is_free":    true,
          "difficulty": "Beginner",
          "format":     "Interactive"
        }
      ]
    },
    ...
  ]
}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from services.roadmap.timeline_generator import TimelineOutput

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ── Types ─────────────────────────────────────────────────────────────────────

Difficulty = Literal["Beginner", "Intermediate", "Advanced"]
Format     = Literal["Video", "Article", "Interactive", "Documentation", "Course"]

_PHASE_TO_DIFFICULTY: dict[str, list[Difficulty]] = {
    "Foundation": ["Beginner", "Intermediate"],
    "Core":       ["Intermediate", "Advanced"],
    "Advanced":   ["Advanced"],
}


# ── Resource dataclass ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Resource:
    """One curated learning resource."""
    title:      str
    provider:   str
    url:        str
    is_free:    bool
    difficulty: Difficulty
    skills:     tuple[str, ...]     # canonical skill names
    format:     Format
    duration_hours: float = 0.0    # estimated completion time

    def matches(self, skill: str, difficulties: list[str]) -> bool:
        """Return True if this resource covers the skill and fits difficulty."""
        return (
            skill in self.skills
            and self.difficulty in difficulties
        )

    def to_dict(self) -> dict:
        return {
            "title":          self.title,
            "provider":       self.provider,
            "url":            self.url,
            "is_free":        self.is_free,
            "difficulty":     self.difficulty,
            "format":         self.format,
            "duration_hours": self.duration_hours,
        }


# ── Curated resource catalogue ────────────────────────────────────────────────

_CATALOGUE: list[Resource] = [

    # ── SQL ──────────────────────────────────────────────────────────────────
    Resource("SQL Tutorial — Full Database Course", "freeCodeCamp",
             "https://www.freecodecamp.org/learn/relational-database/",
             True, "Beginner", ("SQL", "PostgreSQL", "SQLite"), "Interactive", 40.0),

    Resource("Learning SQL (Book)", "O'Reilly",
             "https://www.oreilly.com/library/view/learning-sql-3rd/9781492057604/",
             False, "Beginner", ("SQL",), "Article", 20.0),

    Resource("Mode SQL Tutorial", "Mode Analytics",
             "https://mode.com/sql-tutorial/",
             True, "Intermediate", ("SQL",), "Interactive", 8.0),

    Resource("Advanced SQL for Query Tuning", "Coursera",
             "https://www.coursera.org/learn/advanced-sql",
             False, "Advanced", ("SQL", "PostgreSQL"), "Course", 15.0),

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    Resource("PostgreSQL Official Tutorial", "PostgreSQL.org",
             "https://www.postgresql.org/docs/current/tutorial.html",
             True, "Beginner", ("PostgreSQL",), "Documentation", 5.0),

    Resource("PostgreSQL for Everybody", "University of Michigan / Coursera",
             "https://www.coursera.org/specializations/postgresql-for-everybody",
             False, "Intermediate", ("PostgreSQL", "SQL"), "Course", 30.0),

    # ── Python ───────────────────────────────────────────────────────────────
    Resource("Python for Everybody", "University of Michigan / Coursera",
             "https://www.coursera.org/specializations/python",
             False, "Beginner", ("Python",), "Course", 40.0),

    Resource("Official Python Tutorial", "Python.org",
             "https://docs.python.org/3/tutorial/",
             True, "Beginner", ("Python",), "Documentation", 10.0),

    Resource("Python Data Science Handbook", "Jake VanderPlas",
             "https://jakevdp.github.io/PythonDataScienceHandbook/",
             True, "Intermediate", ("Python", "NumPy", "Pandas", "Matplotlib"), "Article", 20.0),

    Resource("Real Python Tutorials", "Real Python",
             "https://realpython.com/",
             True, "Intermediate", ("Python", "FastAPI", "Flask", "Django"), "Article", 0.0),

    # ── Machine Learning ──────────────────────────────────────────────────────
    Resource("Machine Learning Specialization", "DeepLearning.AI / Coursera",
             "https://www.coursera.org/specializations/machine-learning-introduction",
             False, "Beginner", ("Machine Learning", "Scikit-learn"), "Course", 60.0),

    Resource("Hands-On Machine Learning (Book)", "O'Reilly",
             "https://www.oreilly.com/library/view/hands-on-machine-learning/9781098125967/",
             False, "Intermediate", ("Machine Learning", "Scikit-learn", "TensorFlow"), "Article", 35.0),

    Resource("fast.ai Practical Deep Learning", "fast.ai",
             "https://course.fast.ai/",
             True, "Intermediate", ("Deep Learning", "PyTorch"), "Course", 30.0),

    Resource("Kaggle ML Micro-Courses", "Kaggle",
             "https://www.kaggle.com/learn",
             True, "Beginner", ("Machine Learning", "Scikit-learn", "Pandas",
                                "NumPy", "XGBoost"), "Interactive", 15.0),

    # ── Scikit-learn / XGBoost ────────────────────────────────────────────────
    Resource("Scikit-learn Official User Guide", "Scikit-learn",
             "https://scikit-learn.org/stable/user_guide.html",
             True, "Intermediate", ("Scikit-learn",), "Documentation", 10.0),

    Resource("XGBoost Documentation", "XGBoost",
             "https://xgboost.readthedocs.io/en/stable/",
             True, "Intermediate", ("XGBoost",), "Documentation", 5.0),

    Resource("SHAP Documentation & Examples", "SHAP",
             "https://shap.readthedocs.io/en/latest/",
             True, "Intermediate", ("SHAP", "Explainable AI"), "Documentation", 4.0),

    # ── Deep Learning / PyTorch / TensorFlow ─────────────────────────────────
    Resource("Deep Learning Specialization", "DeepLearning.AI / Coursera",
             "https://www.coursera.org/specializations/deep-learning",
             False, "Intermediate", ("Deep Learning", "TensorFlow"), "Course", 80.0),

    Resource("PyTorch Official Tutorials", "PyTorch.org",
             "https://pytorch.org/tutorials/",
             True, "Intermediate", ("PyTorch",), "Documentation", 8.0),

    Resource("TensorFlow for Beginners", "Google / Coursera",
             "https://www.coursera.org/professional-certificates/tensorflow-in-practice",
             False, "Beginner", ("TensorFlow",), "Course", 50.0),

    # ── Docker / Kubernetes ───────────────────────────────────────────────────
    Resource("Docker Official Get Started Guide", "Docker Docs",
             "https://docs.docker.com/get-started/",
             True, "Beginner", ("Docker",), "Documentation", 3.0),

    Resource("Docker & Kubernetes: The Practical Guide", "Udemy",
             "https://www.udemy.com/course/docker-kubernetes-the-practical-guide/",
             False, "Intermediate", ("Docker", "Kubernetes"), "Course", 23.0),

    Resource("Play with Docker", "Docker",
             "https://labs.play-with-docker.com/",
             True, "Beginner", ("Docker",), "Interactive", 5.0),

    Resource("Kubernetes Official Tutorial", "Kubernetes.io",
             "https://kubernetes.io/docs/tutorials/",
             True, "Intermediate", ("Kubernetes",), "Documentation", 5.0),

    # ── AWS / GCP / Azure ─────────────────────────────────────────────────────
    Resource("AWS Cloud Practitioner Essentials", "AWS Training",
             "https://explore.skillbuilder.aws/learn/course/external/view/elearning/134/aws-cloud-practitioner-essentials",
             True, "Beginner", ("AWS",), "Course", 6.0),

    Resource("AWS Solutions Architect — Associate (A Cloud Guru)", "A Cloud Guru",
             "https://acloudguru.com/course/aws-certified-solutions-architect-associate-saa-c03",
             False, "Intermediate", ("AWS",), "Course", 40.0),

    Resource("Google Cloud Skills Boost", "Google Cloud",
             "https://cloudskillsboost.google/",
             True, "Beginner", ("Google Cloud Platform",), "Interactive", 10.0),

    Resource("Microsoft Azure Fundamentals (AZ-900)", "Microsoft Learn",
             "https://learn.microsoft.com/en-us/training/paths/azure-fundamentals/",
             True, "Beginner", ("Microsoft Azure",), "Course", 10.0),

    # ── DevOps / CI/CD / Terraform ────────────────────────────────────────────
    Resource("HashiCorp Terraform Learn", "HashiCorp",
             "https://developer.hashicorp.com/terraform/tutorials",
             True, "Beginner", ("Terraform",), "Interactive", 8.0),

    Resource("GitHub Actions Quickstart", "GitHub Docs",
             "https://docs.github.com/en/actions/quickstart",
             True, "Beginner", ("CI/CD", "Git"), "Documentation", 2.0),

    Resource("Linux Command Line Basics", "Udacity",
             "https://www.udacity.com/course/linux-command-line-basics--ud595",
             True, "Beginner", ("Linux", "Bash"), "Course", 5.0),

    # ── Web Backend ───────────────────────────────────────────────────────────
    Resource("FastAPI Official Tutorial", "Tiangolo / FastAPI",
             "https://fastapi.tiangolo.com/tutorial/",
             True, "Beginner", ("FastAPI", "REST API"), "Documentation", 4.0),

    Resource("Django for Beginners", "William Vincent",
             "https://djangoforbeginners.com/",
             False, "Beginner", ("Django",), "Article", 10.0),

    # ── Web Frontend ──────────────────────────────────────────────────────────
    Resource("React Official Docs", "React.dev",
             "https://react.dev/learn",
             True, "Beginner", ("React",), "Documentation", 10.0),

    Resource("The Odin Project — JavaScript", "The Odin Project",
             "https://www.theodinproject.com/paths/full-stack-javascript",
             True, "Beginner", ("JavaScript", "React"), "Interactive", 60.0),

    # ── Data Engineering ──────────────────────────────────────────────────────
    Resource("Apache Spark with Python (PySpark)", "Databricks Academy",
             "https://academy.databricks.com/",
             True, "Intermediate", ("Apache Spark",), "Course", 12.0),

    Resource("dbt Learn", "dbt Labs",
             "https://courses.getdbt.com/",
             True, "Beginner", ("dbt",), "Interactive", 5.0),

    Resource("Apache Airflow Documentation", "Apache",
             "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html",
             True, "Intermediate", ("Airflow",), "Documentation", 4.0),

    # ── NLP ───────────────────────────────────────────────────────────────────
    Resource("Hugging Face NLP Course", "Hugging Face",
             "https://huggingface.co/learn/nlp-course/",
             True, "Intermediate", ("Natural Language Processing", "Transformers", "BERT"), "Course", 15.0),

    Resource("spaCy 101", "Explosion AI",
             "https://spacy.io/usage/spacy-101",
             True, "Beginner", ("spaCy", "Natural Language Processing"), "Documentation", 3.0),

    # ── Data Science / Pandas ─────────────────────────────────────────────────
    Resource("Pandas Official Getting Started", "Pandas",
             "https://pandas.pydata.org/docs/getting_started/index.html",
             True, "Beginner", ("Pandas",), "Documentation", 3.0),

    Resource("Data Analysis with Python", "freeCodeCamp / Coursera",
             "https://www.freecodecamp.org/learn/data-analysis-with-python/",
             True, "Beginner", ("Pandas", "NumPy", "Python"), "Interactive", 20.0),
]


# ── Resource catalogue (Single Responsibility) ────────────────────────────────

class ResourceCatalogue:
    """
    Holds all curated resources and answers skill-based lookup queries.
    Extend by subclassing and overriding _build_catalogue().
    """

    def __init__(self) -> None:
        self._resources = _CATALOGUE

    def find(
        self,
        skill:       str,
        phase:       str,
        free_only:   bool = False,
        max_results: int  = 3,
    ) -> list[Resource]:
        """
        Find resources matching a skill and learning phase.

        Parameters
        ----------
        skill       : Canonical skill name.
        phase       : "Foundation" | "Core" | "Advanced"
        free_only   : If True, return only free resources.
        max_results : Maximum number of resources to return.

        Returns
        -------
        list[Resource]
            Matched resources sorted by difficulty asc then is_free desc.
        """
        difficulties = _PHASE_TO_DIFFICULTY.get(phase, ["Beginner", "Intermediate"])
        matches = [
            r for r in self._resources
            if r.matches(skill, difficulties)
            and (not free_only or r.is_free)
        ]

        # Sort: free first, then by difficulty index asc
        diff_order = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
        matches.sort(key=lambda r: (not r.is_free, diff_order.get(r.difficulty, 1)))
        return matches[:max_results]


# ── Output types ──────────────────────────────────────────────────────────────

class EnrichedWeek(TypedDict):
    week:      int
    skill:     str
    phase:     str
    topic:     str
    milestone: str | None
    summary:   str
    resources: list[dict]


class EnrichedTimeline(TypedDict):
    target_role:       str
    total_weeks:       int
    enriched_timeline: list[EnrichedWeek]


# ── CourseFinder — orchestrator (Open/Closed) ─────────────────────────────────

class CourseFinder:
    """
    Attaches curated learning resources to each week of a TimelineOutput.

    Inject a custom ResourceCatalogue to change the resource pool
    without modifying this class.
    """

    def __init__(
        self,
        catalogue:   ResourceCatalogue | None = None,
        free_only:   bool = False,
        max_per_week: int = 3,
    ) -> None:
        self._catalogue    = catalogue or ResourceCatalogue()
        self._free_only    = free_only
        self._max_per_week = max_per_week

    def enrich(self, timeline: TimelineOutput) -> EnrichedTimeline:
        """
        Attach resources to each week in a TimelineOutput.

        Parameters
        ----------
        timeline : TimelineOutput
            Output of timeline_generator.generate_timeline().

        Returns
        -------
        EnrichedTimeline
            Timeline with resources attached per week.

        Raises
        ------
        TypeError : If timeline is not a dict.
        """
        if not isinstance(timeline, dict):
            raise TypeError(
                f"timeline must be a dict, got {type(timeline).__name__}"
            )

        target_role = timeline.get("target_role", "Unknown Role")
        total_weeks = timeline.get("total_weeks", 0)
        weeks       = timeline.get("timeline", [])

        logger.info(
            "enrich: target_role=%r  weeks=%d  free_only=%s",
            target_role, len(weeks), self._free_only,
        )

        # Track per-skill week offset for pagination across multi-week skills
        skill_week_index: dict[str, int] = {}

        enriched: list[EnrichedWeek] = []
        for week in weeks:
            if not isinstance(week, dict):
                logger.warning("Skipping non-dict week entry.")
                continue

            skill = week.get("skill", "")
            phase = week.get("phase", "Foundation")

            # Fetch a larger pool and paginate by week index
            pool = self._catalogue.find(
                skill       = skill,
                phase       = phase,
                free_only   = self._free_only,
                max_results = self._max_per_week * 4,
            )

            idx    = skill_week_index.get(skill, 0)
            start  = idx * self._max_per_week
            slice_ = pool[start: start + self._max_per_week] or pool[: self._max_per_week]
            skill_week_index[skill] = idx + 1

            unique_resources = [res.to_dict() for res in slice_]

            enriched.append(EnrichedWeek(
                week      = week.get("week", 0),
                skill     = skill,
                phase     = phase,
                topic     = week.get("topic", skill),
                milestone = week.get("milestone"),
                summary   = week.get("summary", ""),
                resources = unique_resources,
            ))

        logger.info(
            "enrich complete: %d weeks enriched.", len(enriched)
        )

        return EnrichedTimeline(
            target_role       = target_role,
            total_weeks       = total_weeks,
            enriched_timeline = enriched,
        )


# ── Public convenience function ───────────────────────────────────────────────

def find_courses(
    timeline:    TimelineOutput,
    free_only:   bool = False,
    max_per_week: int = 3,
) -> EnrichedTimeline:
    """
    Attach curated learning resources to a TimelineOutput.

    Parameters
    ----------
    timeline     : TimelineOutput from timeline_generator.generate_timeline().
    free_only    : If True, only return free resources.
    max_per_week : Max resources to attach per week slot.

    Returns
    -------
    EnrichedTimeline with resources attached per week.
    """
    return CourseFinder(
        free_only    = free_only,
        max_per_week = max_per_week,
    ).enrich(timeline)