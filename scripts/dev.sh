#!/usr/bin/env bash
# Convenience script: run backend + frontend together for local development.
set -euo pipefail
cd "$(dirname "$0")/.."

( cd backend && [ -d .venv ] || python3 -m venv .venv )
( cd backend && . .venv/bin/activate && pip install -q -r requirements.txt )
( cd frontend && [ -d node_modules ] || npm install )

trap 'kill 0' EXIT
( cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) &
( cd frontend && npm run dev ) &
wait
