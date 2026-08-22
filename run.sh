#!/usr/bin/env bash
# Starts the Two Worlds API server.
# Usage: ./run.sh [uvicorn args...]   e.g. ./run.sh --port 8001

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  echo "OPENAI_API_KEY=" > .env
  echo "OPENAI_MODEL=gpt-5.2" >> .env
  echo "Created .env — add your OPENAI_API_KEY before calling /chat."
fi

exec uvicorn app.main:app --reload --port 8000 "$@"
