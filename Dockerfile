# =============================================================================
# Career Intelligence Platform — Root Dockerfile (backend API)
# =============================================================================
# Single-container production image for platforms like Railway, Render, Fly.io,
# or any host that builds from ./Dockerfile at the repo root.
#
# ----------  Required environment variables  ----------
#   DATABASE_URL          PostgreSQL connection string
#                         e.g. postgresql://user:pass@host:5432/dbname?sslmode=require
#
# ----------  Optional environment variables  ----------
#   ADZUNA_APP_ID         Adzuna API application ID   (job scraping)
#   ADZUNA_APP_KEY        Adzuna API application key   (job scraping)
#   JSEARCH_API_KEY       RapidAPI key for JSearch      (job scraping)
#   DEFAULT_TARGET_ROLE   Target role for analysis      (default: Software Engineer)
#   MIN_SKILL_CONFIDENCE  Minimum skill confidence      (default: 0.40)
#   MIN_DEMAND_PCT        Minimum demand percentage     (default: 0.0)
#   PARTIAL_MATCH         Enable partial skill matching (default: true)
#   PORT                  Override listening port       (default: 8000)
#
# ----------  Build & run  ----------
#   docker build -t cip .
#   docker run --rm -p 8000:8000 --env-file backend/.env cip
# =============================================================================

FROM python:3.12-slim

# --- System dependencies (PostgreSQL client libs, C compiler for wheels) -----
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Working directory -------------------------------------------------------
WORKDIR /app

# --- Python dependencies (cached layer — changes only when requirements.txt changes)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- Application code --------------------------------------------------------
# Copy the backend source
COPY backend/ ./

# Copy the job_engine data directory (referenced by backend via parents[3])
# In Docker, parents[3] from /app/api/routes/resume_routes.py is "/" so we
# place job_engine at /job_engine to match the resolved path.
COPY job_engine/ /job_engine/

# --- Port --------------------------------------------------------------------
EXPOSE 8000

# --- Entrypoint --------------------------------------------------------------
# Bind to 0.0.0.0 so the container is reachable from outside.
# PORT env var override is supported by many PaaS providers.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
