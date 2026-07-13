#!/bin/sh
set -e

# ── Support PORT env var (Railway, Render, Fly.io set this) ──────────────────
if [ -n "$PORT" ] && [ "$PORT" != "80" ]; then
    sed -i "s/listen 80;/listen ${PORT};/" /etc/nginx/conf.d/default.conf
fi

# ── Start the FastAPI backend in the background ──────────────────────────────
cd /app
uvicorn main:app --host 127.0.0.1 --port 8000 &

# ── Start nginx in the foreground (PID 1) ────────────────────────────────────
nginx -g 'daemon off;'
