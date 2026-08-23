#!/usr/bin/env bash
# Starts the Prototype API server, setting up the database every run.
# Usage: ./run.sh [--reseed] [uvicorn args...]   e.g. ./run.sh --port 8001
#
#   --reseed  Also force chat message/embedding regeneration even though
#             chat_data/embeddings.json already exists (e.g. to reset demo
#             chat data). Must come before any uvicorn args if used.
#
# One-time setup: create an empty Postgres database (e.g. `createdb two_worlds`)
# and, if you didn't use that exact name, set DATABASE_URL in .env to match.
# Every run then: drops + recreates the schema from scratch (schema.sql +
# knowledge_base.sql) and reseeds both tenants -- always a clean slate, since
# these are cheap and fully deterministic. Chat messages + embeddings are the
# one step that stays cached (skipped once chat_data/embeddings.json exists)
# since that's a real, billed OpenAI API call.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

RESEED=false
if [ "${1:-}" = "--reseed" ]; then
  RESEED=true
  shift
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  echo "OPENAI_API_KEY=" > .env
  echo "OPENAI_MODEL=gpt-5.2" >> .env
  echo "DATABASE_URL=postgresql:///two_worlds" >> .env
  echo "Created .env — add your OPENAI_API_KEY before calling /chat."
fi

# .env is simple KEY=value lines (no quoting/spaces), so it's safe to source
# directly and export everything it sets -- this is the only place DATABASE_URL
# needs to reach the shell itself (app/config.py loads it separately, via
# python-dotenv, for the actual running process).
set -a
source .env
set +a
DATABASE_URL="${DATABASE_URL:-postgresql:///two_worlds}"

if ! command -v psql > /dev/null 2>&1; then
  echo "psql not found -- install the PostgreSQL client tools first (e.g. 'brew install postgresql')." >&2
  exit 1
fi

if ! psql "$DATABASE_URL" -c 'select 1' > /dev/null 2>&1; then
  echo "Could not connect to $DATABASE_URL." >&2
  echo "Create the database first (e.g. 'createdb two_worlds'), or set a different DATABASE_URL in .env." >&2
  exit 1
fi

echo "Resetting schema..."
psql "$DATABASE_URL" -c 'drop schema public cascade; create schema public;' > /dev/null 2>&1
psql "$DATABASE_URL" -f db/schema.sql -f db/knowledge_base.sql

echo "Seeding tenant_a and tenant_b..."
python db/seed_tenant_a.py
python db/seed_tenant_b.py

if [ "$RESEED" = true ] || [ ! -f chat_data/embeddings.json ]; then
  echo "Generating chat messages and embeddings..."
  python chat_data/generate_messages.py
  python chat_data/seed_messages.py
fi

exec uvicorn app.main:app --reload --port 8000 "$@"
