# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/deps -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=swapi.settings

WORKDIR /app

# Copy only the installed packages from the builder — no pip or build tools
COPY --from=builder /deps /usr/local

# Copy application source
COPY . .

# Collect static files at build time.
# SECRET_KEY is required by Django settings; the runtime SECRET_KEY must be
# injected via environment variables at deploy time.
ARG COLLECTSTATIC_SECRET_KEY=collectstatic-placeholder-not-used-at-runtime
RUN SECRET_KEY=${COLLECTSTATIC_SECRET_KEY} \
    python manage.py collectstatic --noinput

# Drop to non-root for runtime — principle of least privilege
RUN useradd --system --no-create-home --shell /bin/false swapi && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R swapi:swapi /app

USER swapi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/')" \
    || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Override workers at runtime via GUNICORN_WORKERS env var (default 4)
CMD ["sh", "-c", \
  "gunicorn swapi.wsgi:application \
     --bind 0.0.0.0:8000 \
     --workers ${GUNICORN_WORKERS:-4} \
     --timeout 30 \
     --access-logfile - \
     --error-logfile -"]
