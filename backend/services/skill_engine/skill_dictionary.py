"""
skill_dictionary.py
─────────────────────────────────────────────────────────────────────────────
Master skill dictionary for the skill_engine module.

Structure
---------
Each skill entry in SKILL_CATALOG is a dict with:

    canonical   : str          Authoritative display name ("Python")
    aliases     : list[str]    All known surface forms, abbreviations,
                               alternate spellings, and common typos.
                               Matching is case-insensitive.
    category    : str          Broad domain bucket (see CATEGORIES).
    weight      : float        Base confidence weight [0.0 – 1.0].
                               Higher = more unambiguous the term.
                               Used as the prior by skill_extractor.py.

Public API
----------
    SkillEntry            — TypedDict for a single catalog record.
    CATEGORIES            — frozenset of valid category strings.
    SKILL_CATALOG         — list[SkillEntry], the master dictionary.
    ALIAS_INDEX           — dict[str, str]  alias (lowercased) → canonical.
                            Pre-built at import time; O(1) lookup.
    CANONICAL_SET         — frozenset[str]  all canonical names (lowercased).
    get_entry(name)       — Return SkillEntry | None for any alias or canonical.
    list_by_category(cat) — Return list[SkillEntry] filtered by category.
    all_categories()      — Return sorted list of available category strings.

Design notes
------------
- Aliases are the single source of truth for normalisation.
  skill_normalizer.py only needs to call get_entry(); no separate map needed.
- Weights reflect lexical ambiguity:
    1.0  — term is unique to the skill domain (e.g. "XGBoost")
    0.95 — standard full name with minimal ambiguity ("Python", "React")
    0.90 — common abbreviation that's industry-standard ("ML", "NLP")
    0.80 — short abbreviation that appears in other contexts ("JS", "TS")
    0.70 — very short / highly ambiguous ("R", "C", "Go")
- The catalog is intentionally flat (no versioning logic). Version suffixes
  like "Python 3", "ES6" are treated as aliases that resolve to the base
  canonical; version discrimination is left to the extractor layer.
"""

from __future__ import annotations

from typing import TypedDict


# ── Types ─────────────────────────────────────────────────────────────────────

class SkillEntry(TypedDict):
    canonical: str
    aliases: list[str]
    category: str
    weight: float


# ── Valid categories ──────────────────────────────────────────────────────────

CATEGORIES: frozenset[str] = frozenset({
    "programming_language",
    "web_frontend",
    "web_backend",
    "database",
    "cloud",
    "devops",

    "data_science",
    "machine_learning",
    "nlp",
    "computer_vision",
    "data_engineering",

    "security",
    "networking",

    "finance",
    "business",

    "mobile",
    "testing",
    "soft_skill",
    "other",
})


# ── Master catalog ────────────────────────────────────────────────────────────

SKILL_CATALOG: list[SkillEntry] = [

    # ── Programming Languages ─────────────────────────────────────────────────
    {
        "canonical": "Python",
        "aliases": ["python", "py", "python3", "python 3", "python2", "python 2",
                    "cpython", "python programming"],
        "category": "programming_language",
        "weight": 0.95,
    },
    {
        "canonical": "JavaScript",
        "aliases": ["javascript", "js", "es6", "es2015", "es2020", "ecmascript",
                    "vanilla js", "vanillajs", "javascript es6"],
        "category": "programming_language",
        "weight": 0.80,
    },
    {
        "canonical": "TypeScript",
        "aliases": ["typescript", "ts", "typed javascript"],
        "category": "programming_language",
        "weight": 0.80,
    },
    {
        "canonical": "Java",
        "aliases": ["java", "java se", "java ee", "java 8", "java 11", "java 17",
                    "core java", "j2ee", "j2se"],
        "category": "programming_language",
        "weight": 0.90,
    },
    {
        "canonical": "C",
        "aliases": ["c programming", "c language", "ansi c", "c99", "c11"],
        "category": "programming_language",
        "weight": 0.70,
    },
    {
        "canonical": "C++",
        "aliases": ["c++", "cpp", "c plus plus", "cplusplus", "c++11", "c++14",
                    "c++17", "c++20"],
        "category": "programming_language",
        "weight": 0.90,
    },
    {
        "canonical": "C#",
        "aliases": ["c#", "csharp", "c sharp", "c# .net", "dotnet c#"],
        "category": "programming_language",
        "weight": 0.90,
    },
    {
        "canonical": "R",
        "aliases": ["r language", "r programming", "r statistical", "r stats",
                    "rlang"],
        "category": "programming_language",
        "weight": 0.70,
    },
    {
        "canonical": "Go",
        "aliases": ["go", "golang", "go language", "go programming"],
        "category": "programming_language",
        "weight": 0.70,
    },
    {
        "canonical": "Rust",
        "aliases": ["rust", "rust lang", "rustlang", "rust programming"],
        "category": "programming_language",
        "weight": 0.95,
    },
    {
        "canonical": "Kotlin",
        "aliases": ["kotlin", "kotlin jvm", "kotlin android"],
        "category": "programming_language",
        "weight": 0.95,
    },
    {
        "canonical": "Swift",
        "aliases": ["swift", "swift ui", "swiftui", "swift programming", "swift ios"],
        "category": "programming_language",
        "weight": 0.90,
    },
    {
        "canonical": "PHP",
        "aliases": ["php", "php7", "php8", "php 7", "php 8", "hypertext preprocessor"],
        "category": "programming_language",
        "weight": 0.95,
    },
    {
        "canonical": "Ruby",
        "aliases": ["ruby", "ruby programming", "ruby language"],
        "category": "programming_language",
        "weight": 0.90,
    },
    {
        "canonical": "Scala",
        "aliases": ["scala", "scala jvm", "scala programming"],
        "category": "programming_language",
        "weight": 0.95,
    },
    {
        "canonical": "Bash",
        "aliases": ["bash", "shell scripting", "shell script", "bash scripting",
                    "sh", "zsh", "unix shell", "linux shell"],
        "category": "programming_language",
        "weight": 0.85,
    },
    {
        "canonical": "MATLAB",
        "aliases": ["matlab", "mat lab", "matlab programming"],
        "category": "programming_language",
        "weight": 0.95,
    },

    # ── Web Frontend ──────────────────────────────────────────────────────────
    {
        "canonical": "React",
        "aliases": ["react", "reactjs", "react.js", "react js", "react hooks",
                    "react native", "react dom"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "Vue.js",
        "aliases": ["vue", "vuejs", "vue.js", "vue js", "vue 3", "vue 2",
                    "vue router", "vuex"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "Angular",
        "aliases": ["angular", "angularjs", "angular.js", "angular 2",
                    "angular js", "ng", "angular cli"],
        "category": "web_frontend",
        "weight": 0.90,
    },
    {
        "canonical": "Next.js",
        "aliases": ["next.js", "nextjs", "next js", "next"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "Svelte",
        "aliases": ["svelte", "sveltejs", "svelte.js", "sveltekit"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "HTML",
        "aliases": ["html", "html5", "html 5", "hypertext markup language"],
        "category": "web_frontend",
        "weight": 0.90,
    },
    {
        "canonical": "CSS",
        "aliases": ["css", "css3", "css 3", "cascading style sheets"],
        "category": "web_frontend",
        "weight": 0.90,
    },
    {
        "canonical": "Tailwind CSS",
        "aliases": ["tailwind", "tailwindcss", "tailwind css"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "Redux",
        "aliases": ["redux", "redux toolkit", "react redux", "rtk"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "Webpack",
        "aliases": ["webpack", "webpack 5", "web pack"],
        "category": "web_frontend",
        "weight": 0.95,
    },
    {
        "canonical": "Vite",
        "aliases": ["vite", "vitejs", "vite.js"],
        "category": "web_frontend",
        "weight": 0.95,
    },

    # ── Web Backend ───────────────────────────────────────────────────────────
    {
        "canonical": "FastAPI",
        "aliases": ["fastapi", "fast api", "fastapi python"],
        "category": "web_backend",
        "weight": 1.0,
    },
    {
        "canonical": "Flask",
        "aliases": ["flask", "flask python", "flask framework", "flask api"],
        "category": "web_backend",
        "weight": 0.95,
    },
    {
        "canonical": "Django",
        "aliases": ["django", "django python", "django rest", "drf",
                    "django rest framework", "django orm"],
        "category": "web_backend",
        "weight": 0.95,
    },
    {
        "canonical": "Node.js",
        "aliases": ["node", "nodejs", "node.js", "node js", "expressjs",
                    "express.js", "express js", "express"],
        "category": "web_backend",
        "weight": 0.90,
    },
    {
        "canonical": "Spring Boot",
        "aliases": ["spring boot", "springboot", "spring", "spring framework",
                    "spring mvc", "spring security", "spring data"],
        "category": "web_backend",
        "weight": 0.90,
    },
    {
        "canonical": "FastAPI",
        "aliases": [],   # already defined above; duplicate guard at index build
        "category": "web_backend",
        "weight": 1.0,
    },
    {
        "canonical": "GraphQL",
        "aliases": ["graphql", "graph ql", "gql", "apollo graphql", "apollo"],
        "category": "web_backend",
        "weight": 0.95,
    },
    {
        "canonical": "REST API",
        "aliases": ["rest", "rest api", "restful", "restful api", "rest apis",
                    "restful apis", "rest services", "http api"],
        "category": "web_backend",
        "weight": 0.85,
    },

    # ── Databases ─────────────────────────────────────────────────────────────
    {
        "canonical": "PostgreSQL",
        "aliases": ["postgresql", "postgres", "psql", "pg", "postgre sql"],
        "category": "database",
        "weight": 0.95,
    },
    {
        "canonical": "MySQL",
        "aliases": ["mysql", "my sql", "mysql db"],
        "category": "database",
        "weight": 0.95,
    },
    {
        "canonical": "MongoDB",
        "aliases": ["mongodb", "mongo", "mongo db", "mongoose"],
        "category": "database",
        "weight": 0.95,
    },
    {
        "canonical": "SQLite",
        "aliases": ["sqlite", "sqlite3", "sql lite"],
        "category": "database",
        "weight": 0.95,
    },
    {
        "canonical": "Redis",
        "aliases": ["redis", "redis cache", "redis db"],
        "category": "database",
        "weight": 0.95,
    },
    {
        "canonical": "Elasticsearch",
        "aliases": ["elasticsearch", "elastic search", "elastic", "es", "elk",
                    "elk stack"],
        "category": "database",
        "weight": 0.90,
    },
    {
        "canonical": "Cassandra",
        "aliases": ["cassandra", "apache cassandra", "cassandra db"],
        "category": "database",
        "weight": 0.95,
    },
    {
        "canonical": "SQL",
        "aliases": ["sql", "structured query language", "t-sql", "tsql",
                    "pl/sql", "plsql", "sql queries", "advanced sql"],
        "category": "database",
        "weight": 0.85,
    },
    {
        "canonical": "Firebase",
        "aliases": ["firebase", "firestore", "firebase realtime", "firebase db",
                    "google firebase"],
        "category": "database",
        "weight": 0.95,
    },

    # ── Cloud ─────────────────────────────────────────────────────────────────
    {
        "canonical": "AWS",
        "aliases": ["aws", "amazon web services", "amazon aws",
                    "ec2", "s3", "lambda", "aws lambda", "aws ec2",
                    "aws s3", "aws rds", "cloudformation", "aws cloud"],
        "category": "cloud",
        "weight": 0.90,
    },
    {
        "canonical": "Google Cloud Platform",
        "aliases": ["gcp", "google cloud", "google cloud platform",
                    "bigquery", "gke", "cloud run", "google cloud run",
                    "vertex ai"],
        "category": "cloud",
        "weight": 0.90,
    },
    {
        "canonical": "Microsoft Azure",
        "aliases": ["azure", "microsoft azure", "azure cloud", "azure devops",
                    "azure ml", "azure functions"],
        "category": "cloud",
        "weight": 0.90,
    },

    # ── DevOps ────────────────────────────────────────────────────────────────
    {
        "canonical": "Docker",
        "aliases": ["docker", "dockerfile", "docker compose", "docker-compose",
                    "containerization", "containers"],
        "category": "devops",
        "weight": 0.95,
    },
    {
        "canonical": "Kubernetes",
        "aliases": ["kubernetes", "k8s", "kubectl", "helm", "kubernetes cluster",
                    "k8s cluster"],
        "category": "devops",
        "weight": 0.95,
    },
    {
        "canonical": "CI/CD",
        "aliases": ["ci/cd", "cicd", "ci cd", "continuous integration",
                    "continuous deployment", "continuous delivery",
                    "github actions", "gitlab ci", "jenkins", "circleci",
                    "travis ci"],
        "category": "devops",
        "weight": 0.90,
    },
    {
        "canonical": "Git",
        "aliases": ["git", "git version control", "github", "gitlab",
                    "bitbucket", "version control", "git flow"],
        "category": "devops",
        "weight": 0.85,
    },
    {
        "canonical": "Terraform",
        "aliases": ["terraform", "terraform iac", "infrastructure as code",
                    "iac", "hashicorp terraform"],
        "category": "devops",
        "weight": 0.95,
    },
    {
        "canonical": "Ansible",
        "aliases": ["ansible", "ansible playbook", "ansible automation"],
        "category": "devops",
        "weight": 0.95,
    },
    {
        "canonical": "Linux",
        "aliases": ["linux", "unix", "ubuntu", "centos", "debian",
                    "rhel", "linux administration", "linux server"],
        "category": "devops",
        "weight": 0.85,
    },

    # ── Data Science ──────────────────────────────────────────────────────────
    {
        "canonical": "Pandas",
        "aliases": ["pandas", "pandas python", "pd", "python pandas"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "NumPy",
        "aliases": ["numpy", "np", "python numpy", "numerical python"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "Matplotlib",
        "aliases": ["matplotlib", "matplotlib python", "plt"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "Seaborn",
        "aliases": ["seaborn", "seaborn python", "sns"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "Plotly",
        "aliases": ["plotly", "plotly express", "plotly dash", "dash plotly"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "Jupyter",
        "aliases": ["jupyter", "jupyter notebook", "jupyter lab", "jupyterlab",
                    "ipython", "ipynb"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "Streamlit",
        "aliases": ["streamlit", "streamlit python", "streamlit app"],
        "category": "data_science",
        "weight": 1.0,
    },
    {
        "canonical": "Statistics",
        "aliases": ["statistics", "statistical analysis", "stats",
                    "descriptive statistics", "inferential statistics",
                    "hypothesis testing", "a/b testing"],
        "category": "data_science",
        "weight": 0.80,
    },

    # ── Machine Learning ──────────────────────────────────────────────────────
    {
        "canonical": "Machine Learning",
        "aliases": ["machine learning", "ml", "ml algorithms",
                    "supervised learning", "unsupervised learning",
                    "semi-supervised learning", "reinforcement learning",
                    "rl", "classical ml"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "Scikit-learn",
        "aliases": ["scikit-learn", "sklearn", "scikit learn", "scikitlearn",
                    "scikit-learn python"],
        "category": "machine_learning",
        "weight": 1.0,
    },
    {
        "canonical": "XGBoost",
        "aliases": ["xgboost", "xgb", "extreme gradient boosting",
                    "gradient boosting"],
        "category": "machine_learning",
        "weight": 1.0,
    },
    {
        "canonical": "LightGBM",
        "aliases": ["lightgbm", "lgbm", "light gbm", "light gradient boosting"],
        "category": "machine_learning",
        "weight": 1.0,
    },
    {
        "canonical": "CatBoost",
        "aliases": ["catboost", "cat boost", "categorical boosting"],
        "category": "machine_learning",
        "weight": 1.0,
    },
    {
        "canonical": "Random Forest",
        "aliases": ["random forest", "rf", "random forests", "random forest classifier",
                    "random forest regressor"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "SHAP",
        "aliases": ["shap", "shapley", "shapley values", "shap values",
                    "shap explainability", "shap analysis"],
        "category": "machine_learning",
        "weight": 1.0,
    },
    {
        "canonical": "LIME",
        "aliases": ["lime", "local interpretable model", "lime explainability",
                    "lime explanations"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "Explainable AI",
        "aliases": ["xai", "explainable ai", "explainability", "model interpretability",
                    "interpretable ml", "model explainability"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "Feature Engineering",
        "aliases": ["feature engineering", "feature selection", "feature extraction",
                    "rfe", "recursive feature elimination"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "Cross-Validation",
        "aliases": ["cross-validation", "cross validation", "k-fold",
                    "k fold", "stratified k-fold", "stratified kfold",
                    "kfold", "cv"],
        "category": "machine_learning",
        "weight": 0.85,
    },
    {
        "canonical": "Hyperparameter Tuning",
        "aliases": ["hyperparameter tuning", "hyperparameter optimization",
                    "gridsearchcv", "grid search", "randomizedsearchcv",
                    "random search", "optuna", "bayesian optimization",
                    "hyperopt"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "SMOTE",
        "aliases": ["smote", "synthetic minority oversampling",
                    "oversampling", "class imbalance", "imbalanced data",
                    "imbalanced-learn", "imblearn"],
        "category": "machine_learning",
        "weight": 0.95,
    },

    # ── Deep Learning ─────────────────────────────────────────────────────────
    {
        "canonical": "Deep Learning",
        "aliases": ["deep learning", "dl", "neural networks", "neural network",
                    "ann", "dnn", "deep neural network"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "TensorFlow",
        "aliases": ["tensorflow", "tf", "tensorflow 2", "tensorflow keras",
                    "tf2"],
        "category": "machine_learning",
        "weight": 0.95,
    },
    {
        "canonical": "PyTorch",
        "aliases": ["pytorch", "torch", "py torch", "pytorch lightning",
                    "lightning"],
        "category": "machine_learning",
        "weight": 0.95,
    },
    {
        "canonical": "Keras",
        "aliases": ["keras", "keras api", "tf.keras"],
        "category": "machine_learning",
        "weight": 0.95,
    },
    {
        "canonical": "CNN",
        "aliases": ["cnn", "convolutional neural network",
                    "convolutional network", "convnet"],
        "category": "machine_learning",
        "weight": 0.90,
    },
    {
        "canonical": "RNN",
        "aliases": ["rnn", "recurrent neural network", "lstm", "gru",
                    "long short-term memory", "sequence model"],
        "category": "machine_learning",
        "weight": 0.90,
    },

    # ── NLP ───────────────────────────────────────────────────────────────────
    {
        "canonical": "Natural Language Processing",
        "aliases": ["nlp", "natural language processing", "text mining",
                    "text analytics", "computational linguistics"],
        "category": "nlp",
        "weight": 0.90,
    },
    {
        "canonical": "Transformers",
        "aliases": ["transformers", "huggingface", "hugging face",
                    "huggingface transformers", "hf transformers"],
        "category": "nlp",
        "weight": 0.95,
    },
    {
        "canonical": "BERT",
        "aliases": ["bert", "bert model", "google bert", "bert nlp",
                    "roberta", "distilbert", "albert"],
        "category": "nlp",
        "weight": 1.0,
    },
    {
        "canonical": "spaCy",
        "aliases": ["spacy", "spacy nlp", "spacy python", "en_core_web"],
        "category": "nlp",
        "weight": 1.0,
    },
    {
        "canonical": "NLTK",
        "aliases": ["nltk", "natural language toolkit", "nltk python"],
        "category": "nlp",
        "weight": 1.0,
    },
    {
        "canonical": "Word Embeddings",
        "aliases": ["word2vec", "word embeddings", "glove", "fasttext",
                    "embeddings", "sentence embeddings"],
        "category": "nlp",
        "weight": 0.90,
    },
    {
        "canonical": "LLM",
        "aliases": ["llm", "large language model", "large language models",
                    "gpt", "gpt-4", "chatgpt", "openai", "claude",
                    "llama", "mistral", "gemini"],
        "category": "nlp",
        "weight": 0.90,
    },
    {
        "canonical": "LangChain",
        "aliases": ["langchain", "lang chain", "langchain python"],
        "category": "nlp",
        "weight": 1.0,
    },

    # ── Computer Vision ───────────────────────────────────────────────────────
    {
        "canonical": "Computer Vision",
        "aliases": ["computer vision", "cv", "image recognition",
                    "object detection", "image classification",
                    "image processing"],
        "category": "computer_vision",
        "weight": 0.85,
    },
    {
        "canonical": "OpenCV",
        "aliases": ["opencv", "open cv", "cv2", "opencv python"],
        "category": "computer_vision",
        "weight": 1.0,
    },
    {
        "canonical": "YOLO",
        "aliases": ["yolo", "yolov5", "yolov8", "you only look once"],
        "category": "computer_vision",
        "weight": 1.0,
    },

    # ── Data Engineering ──────────────────────────────────────────────────────
    {
        "canonical": "Apache Spark",
        "aliases": ["spark", "apache spark", "pyspark", "py spark",
                    "spark sql", "spark streaming"],
        "category": "data_engineering",
        "weight": 0.90,
    },
    {
        "canonical": "Apache Kafka",
        "aliases": ["kafka", "apache kafka", "kafka streams", "kafka consumer"],
        "category": "data_engineering",
        "weight": 0.95,
    },
    {
        "canonical": "Airflow",
        "aliases": ["airflow", "apache airflow", "airflow dag", "dag"],
        "category": "data_engineering",
        "weight": 0.90,
    },
    {
        "canonical": "dbt",
        "aliases": ["dbt", "data build tool", "dbt core", "dbt cloud"],
        "category": "data_engineering",
        "weight": 1.0,
    },
    {
        "canonical": "ETL",
        "aliases": ["etl", "etl pipeline", "extract transform load",
                    "data pipeline", "data pipelines", "elt"],
        "category": "data_engineering",
        "weight": 0.85,
    },
    {
        "canonical": "Snowflake",
        "aliases": ["snowflake", "snowflake sql", "snowflake db"],
        "category": "data_engineering",
        "weight": 1.0,
    },

    # ── Mobile ────────────────────────────────────────────────────────────────
    {
        "canonical": "Android",
        "aliases": ["android", "android development", "android studio",
                    "android sdk", "android app"],
        "category": "mobile",
        "weight": 0.90,
    },
    {
        "canonical": "iOS",
        "aliases": ["ios", "ios development", "ios app", "xcode",
                    "iphone development"],
        "category": "mobile",
        "weight": 0.90,
    },
    {
        "canonical": "Flutter",
        "aliases": ["flutter", "flutter dart", "flutter sdk",
                    "flutter app"],
        "category": "mobile",
        "weight": 0.95,
    },
    {
        "canonical": "Dart",
        "aliases": ["dart", "dart language", "dart programming"],
        "category": "mobile",
        "weight": 0.95,
    },

    # ── Testing ───────────────────────────────────────────────────────────────
    {
        "canonical": "Pytest",
        "aliases": ["pytest", "py.test", "pytest python", "unit testing python"],
        "category": "testing",
        "weight": 1.0,
    },
    {
        "canonical": "Unit Testing",
        "aliases": ["unit testing", "unit tests", "tdd", "test driven development",
                    "test-driven development", "bdd", "behaviour driven"],
        "category": "testing",
        "weight": 0.85,
    },
    {
        "canonical": "Selenium",
        "aliases": ["selenium", "selenium webdriver", "selenium python",
                    "browser automation"],
        "category": "testing",
        "weight": 0.95,
    },

    # ── Customer / Business Analytics ─────────────────────────────────────────
    {
        "canonical": "Customer Lifetime Value",
        "aliases": ["cltv", "clv", "customer lifetime value",
                    "ltv", "lifetime value", "bg/nbd", "bgnbd",
                    "gamma-gamma", "btyd"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "RFM Analysis",
        "aliases": ["rfm", "rfm analysis", "recency frequency monetary",
                    "customer segmentation"],
        "category": "data_science",
        "weight": 0.95,
    },
    {
        "canonical": "A/B Testing",
        "aliases": ["a/b testing", "ab testing", "split testing",
                    "experimentation"],
        "category": "data_science",
        "weight": 0.90,
    },
    # ── Cyber Security ──────────────────────────────────────────────

    {
        "canonical": "SIEM",
        "aliases": ["siem", "security information and event management"],
        "category": "security",
        "weight": 0.95,
    },
    {
        "canonical": "Splunk",
        "aliases": ["splunk", "splunk enterprise"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Wazuh",
        "aliases": ["wazuh"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Suricata",
        "aliases": ["suricata"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Zeek",
        "aliases": ["zeek", "bro ids"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Penetration Testing",
        "aliases": ["penetration testing", "pentesting", "pen test"],
        "category": "security",
        "weight": 0.95,
    },
    {
        "canonical": "Threat Hunting",
        "aliases": ["threat hunting", "threat hunter"],
        "category": "security",
        "weight": 0.95,
    },
    {
        "canonical": "Incident Response",
        "aliases": ["incident response", "security incident response"],
        "category": "security",
        "weight": 0.95,
    },
    {
        "canonical": "OWASP",
        "aliases": ["owasp", "owasp top 10"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Network Security",
        "aliases": ["network security", "firewall security"],
        "category": "security",
        "weight": 0.95,
    },
    {
        "canonical": "pfSense",
        "aliases": ["pfsense"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Kali Linux",
        "aliases": ["kali", "kali linux"],
        "category": "security",
        "weight": 1.0,
    },
    {
        "canonical": "Wireshark",
        "aliases": ["wireshark"],
        "category": "security",
        "weight": 1.0,
    },
    
    # ── Finance ──────────────────────────────────────────────

    {
        "canonical": "Financial Modeling",
        "aliases": ["financial modeling", "financial models"],
        "category": "finance",
        "weight": 1.0,
    },
    {
        "canonical": "Valuation",
        "aliases": ["valuation", "company valuation"],
        "category": "finance",
        "weight": 0.95,
    },
    {
        "canonical": "Risk Analysis",
        "aliases": ["risk analysis", "risk management"],
        "category": "finance",
        "weight": 0.95,
    },
    {
        "canonical": "Corporate Finance",
        "aliases": ["corporate finance"],
        "category": "finance",
        "weight": 0.95,
    },
    {
        "canonical": "Financial Analysis",
        "aliases": ["financial analysis"],
        "category": "finance",
        "weight": 0.95,
    },
    {
        "canonical": "Investment Analysis",
        "aliases": ["investment analysis", "equity research"],
        "category": "finance",
        "weight": 0.95,
    },
    {
        "canonical": "Bloomberg",
        "aliases": ["bloomberg terminal", "bloomberg"],
        "category": "finance",
        "weight": 1.0,
    },
    {
        "canonical": "Forecasting",
        "aliases": ["forecasting", "financial forecasting"],
        "category": "finance",
        "weight": 0.90,
    },
    {
        "canonical": "Excel",
        "aliases": ["excel", "microsoft excel"],
        "category": "finance",
        "weight": 0.85,
    },

    {
        "canonical": "Power BI",
        "aliases": ["power bi", "powerbi"],
        "category": "business",
        "weight": 0.95,
    },
    {
        "canonical": "Tableau",
        "aliases": ["tableau"],
        "category": "business",
        "weight": 0.95,
    },
    {
        "canonical": "Market Research",
        "aliases": ["market research"],
        "category": "business",
        "weight": 0.90,
    },
    {
        "canonical": "Requirements Gathering",
        "aliases": ["requirements gathering", "business requirements"],
        "category": "business",
        "weight": 0.90,
    },
    {
        "canonical": "Stakeholder Management",
        "aliases": ["stakeholder management"],
        "category": "business",
        "weight": 0.90,
    },

    {
    "canonical": "RAG",
    "aliases": ["rag", "retrieval augmented generation"],
    "category": "nlp",
    "weight": 1.0,
    },
    {
        "canonical": "Vector Database",
        "aliases": ["vector database", "pinecone", "weaviate", "qdrant", "chromadb"],
        "category": "nlp",
        "weight": 1.0,
    },
    {
        "canonical": "Prompt Engineering",
        "aliases": ["prompt engineering"],
        "category": "nlp",
        "weight": 0.95,
    },
    {
        "canonical": "MLOps",
        "aliases": ["mlops"],
        "category": "machine_learning",
        "weight": 1.0,
    },

    # ── Soft Skills ───────────────────────────────────────────────────────────
    {
        "canonical": "Communication",
        "aliases": ["communication", "verbal communication",
                    "written communication", "presentation skills"],
        "category": "soft_skill",
        "weight": 0.75,
    },
    {
        "canonical": "Team Leadership",
        "aliases": ["leadership", "team leadership", "team lead",
                    "people management", "mentoring"],
        "category": "soft_skill",
        "weight": 0.75,
    },
    {
        "canonical": "Problem Solving",
        "aliases": ["problem solving", "analytical thinking",
                    "critical thinking", "problem-solving"],
        "category": "soft_skill",
        "weight": 0.75,
    },
]


# ── Remove duplicate canonical entries (defensive dedup at module load) ───────
_seen_canonicals: set[str] = set()
_deduped_catalog: list[SkillEntry] = []
for _entry in SKILL_CATALOG:
    if _entry["canonical"] not in _seen_canonicals:
        _seen_canonicals.add(_entry["canonical"])
        _deduped_catalog.append(_entry)
SKILL_CATALOG = _deduped_catalog
del _seen_canonicals, _deduped_catalog, _entry


# ── Pre-built indexes (O(1) lookup) ───────────────────────────────────────────

# alias (lowercased) → canonical name
ALIAS_INDEX: dict[str, str] = {}

for _entry in SKILL_CATALOG:
    # The canonical name itself is always resolvable
    ALIAS_INDEX[_entry["canonical"].lower()] = _entry["canonical"]
    for _alias in _entry["aliases"]:
        key = _alias.lower().strip()
        if key and key not in ALIAS_INDEX:
            ALIAS_INDEX[key] = _entry["canonical"]

del _entry, _alias, key   # type: ignore[possibly-undefined]


# All canonical names (lowercased) for fast membership tests
CANONICAL_SET: frozenset[str] = frozenset(
    e["canonical"].lower() for e in SKILL_CATALOG
)


# ── Helper functions ──────────────────────────────────────────────────────────

def get_entry(name: str) -> SkillEntry | None:
    """
    Return the SkillEntry for any alias or canonical name (case-insensitive).
    Returns None if the name is not in the catalog.

    Examples
    --------
    >>> get_entry("js")["canonical"]
    'JavaScript'
    >>> get_entry("sklearn")["canonical"]
    'Scikit-learn'
    >>> get_entry("unknown tool") is None
    True
    """
    canonical = ALIAS_INDEX.get(name.lower().strip())
    if canonical is None:
        return None
    return next(
        (e for e in SKILL_CATALOG if e["canonical"] == canonical), None
    )


def list_by_category(category: str) -> list[SkillEntry]:
    """
    Return all SkillEntry records belonging to *category*.
    Returns an empty list for unknown categories.

    Examples
    --------
    >>> names = [e["canonical"] for e in list_by_category("machine_learning")]
    >>> "XGBoost" in names
    True
    """
    return [e for e in SKILL_CATALOG if e["category"] == category]


def all_categories() -> list[str]:
    """Return a sorted list of all category strings present in the catalog."""
    return sorted({e["category"] for e in SKILL_CATALOG})