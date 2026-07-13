# =============================================================================
# Career Intelligence Platform — Root Dockerfile (Full Stack)
# =============================================================================
# Single-container production image for platforms like Railway, Render, Fly.io.
# Serves the React frontend via nginx and proxies API requests to uvicorn.
#
# ----------  Required environment variables  ----------
#   DATABASE_URL          PostgreSQL connection string
#
# ----------  Optional environment variables  ----------
#   ADZUNA_APP_ID         Adzuna API application ID   (job scraping)
#   ADZUNA_APP_KEY        Adzuna API application key   (job scraping)
#   JSEARCH_API_KEY       RapidAPI key for JSearch      (job scraping)
#   DEFAULT_TARGET_ROLE   Target role for analysis      (default: Software Engineer)
#   MIN_SKILL_CONFIDENCE  Minimum skill confidence      (default: 0.40)
#   MIN_DEMAND_PCT        Minimum demand percentage     (default: 0.0)
#   PARTIAL_MATCH         Enable partial skill matching (default: true)
#   PORT                  Override listening port       (default: 80)
#
# ----------  Build & run  ----------
#   docker build -t cip .
#   docker run --rm -p 3000:80 --env-file backend/.env cip
#   Open http://localhost:3000  (frontend + API)
# =============================================================================


# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci --prefer-offline

COPY frontend/ .

# Empty VITE_API_URL so axios uses relative URLs (nginx proxies to backend)
ENV VITE_API_URL=""
RUN npm run build


# ── Stage 2: Production image (Python + Nginx) ──────────────────────────────
FROM python:3.12-slim

# --- System dependencies ----------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        nginx \
    && rm -rf /var/lib/apt/lists/*

# --- Python dependencies (cached layer) -------------------------------------
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- Backend source ----------------------------------------------------------
COPY backend/ ./

# --- Job engine data (backend references /job_engine/ via Path.parents[3]) ---
COPY job_engine/ /job_engine/

# --- Frontend built assets ---------------------------------------------------
COPY --from=frontend-build /build/dist /usr/share/nginx/html

# --- Nginx config ------------------------------------------------------------
# Remove default nginx site, add our reverse-proxy config
RUN rm -f /etc/nginx/sites-enabled/default
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# --- Entrypoint --------------------------------------------------------------
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
