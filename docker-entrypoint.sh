#!/bin/sh
set -e

# ── Wait for the database ──────────────────────────────────────────────────────
# Only needed when DATABASE_URL is set (i.e. PostgreSQL, not SQLite).
if [ -n "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] Waiting for database..."
    RETRIES=30
    until python - <<'PYEOF'
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swapi.settings')
django.setup()
from django.db import connections
try:
    connections['default'].cursor()
except Exception as e:
    sys.exit(1)
PYEOF
    do
        RETRIES=$((RETRIES - 1))
        if [ "$RETRIES" -le 0 ]; then
            echo "[entrypoint] ERROR: database never became ready."
            exit 1
        fi
        echo "[entrypoint] Database not ready — retrying in 2s (${RETRIES} attempts left)..."
        sleep 2
    done
    echo "[entrypoint] Database is ready."
fi

# ── Migrations ─────────────────────────────────────────────────────────────────
echo "[entrypoint] Applying migrations..."
python manage.py migrate --noinput

# ── Optional fixture load (first-run seeding) ──────────────────────────────────
# Set LOAD_FIXTURES=true to seed the Star Wars dataset on startup.
if [ "${LOAD_FIXTURES:-false}" = "true" ]; then
    echo "[entrypoint] Loading Star Wars fixtures..."
    python manage.py loaddata \
        planets people species transport starships vehicles films
    echo "[entrypoint] Fixtures loaded."
fi

# ── Hand off to the container CMD ─────────────────────────────────────────────
echo "[entrypoint] Starting: $*"
exec "$@"
