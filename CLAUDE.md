# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWAPI is a read-only REST API serving Star Wars universe data. Built with Django 5.2 and Django REST Framework, served by Gunicorn with WhiteNoise for static assets.

**Key constraint**: The API is read-only by design. All viewsets extend `ReadOnlyModelViewSet`. Write operations return HTTP 405.

## Development Commands

### Environment Setup

All Django commands require `SECRET_KEY` and optionally `DEBUG` environment variables:

```bash
# Development (uses SQLite)
SECRET_KEY=any-local-secret DEBUG=True python manage.py <command>

# Production (requires DATABASE_URL for PostgreSQL)
SECRET_KEY=<real-secret> python manage.py <command>
```

### Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Load Star Wars fixture data (required for fresh database)
python manage.py loaddata planets people species transport starships vehicles films

# Run development server
python manage.py runserver

# Run full test suite (160 tests)
python manage.py test

# Run specific test class
python manage.py test resources.tests.PeopleModelTests

# Run specific test method
python manage.py test resources.tests.PeopleModelTests.test_people_model

# Create superuser for /admin/ access
python manage.py createsuperuser
```

### Data Management

```bash
# Export database back to fixtures (after editing via /admin/)
make dump_data

# Reload all fixtures
make load_data

# Flush database (keeps schema)
make drop_db
```

### Docker Development

```bash
# Build and start with Docker Compose (Postgres + web)
docker compose up --build

# First run: seed data automatically
LOAD_FIXTURES=true docker compose up --build

# Or seed manually after stack is up
docker compose exec web python manage.py loaddata planets people species transport starships vehicles films

# View logs
docker compose logs -f web
```

## Architecture

### Directory Structure

```
swapi/                      Django project (settings, URLs, web views)
resources/                  API application (models, serializers, viewsets)
├── models.py               ORM models with multi-table inheritance
├── serializers.py          HyperlinkedModelSerializer for each resource
├── views.py                ReadOnlyModelViewSet for each endpoint
├── renderers.py            WookieeRenderer (custom JSON encoder)
├── fixtures/               Star Wars seed data (JSON)
└── tests.py                API endpoint tests (160 tests)
```

### Multi-Table Inheritance Pattern

`Starship` and `Vehicle` share common fields via `Transport` parent:

- **`Transport`** (abstract parent): name, model, manufacturer, crew, passengers, cargo_capacity, consumables, etc.
  - **`Starship`** (child): adds hyperdrive_rating, MGLT, starship_class
  - **`Vehicle`** (child): adds vehicle_class

Django creates separate tables for each but joins automatically on queries. When adding fields:
- Shared transport fields → add to `Transport` model
- Starship-specific → add to `Starship` model
- Vehicle-specific → add to `Vehicle` model

### Hypermedia API Design

All serializers use `HyperlinkedModelSerializer`, not `ModelSerializer`. Related resources are represented as absolute URLs:

```json
{
  "name": "Luke Skywalker",
  "homeworld": "http://localhost:8000/api/planets/1/",
  "films": ["http://localhost:8000/api/films/1/", ...]
}
```

Never change serializers to return IDs instead of URLs — this breaks the hypermedia contract.

### Renderer Pipeline

Three renderers are configured (REST_FRAMEWORK.DEFAULT_RENDERER_CLASSES):
1. **JSONRenderer**: Standard JSON (default)
2. **BrowsableAPIRenderer**: HTML browsable API
3. **WookieeRenderer**: Custom format activated via `?format=wookiee`

The WookieeRenderer translates lowercase letters using a lookup table while preserving JSON structure. To modify the translation, edit the `lookup` dict in `resources/renderers.py:9-36`.

### Configuration Philosophy

All settings are driven by environment variables (12-factor app). Never hardcode secrets.

**DEBUG mode toggle** (`DEBUG=True` vs `DEBUG=False`):
- **True**: SQLite database, relaxed security, verbose errors
- **False**: PostgreSQL (via DATABASE_URL), HTTPS redirect, secure cookies, HSTS headers

Production security settings auto-activate when `DEBUG=False`:
- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000`

### Static File Handling

WhiteNoise serves static files directly from Gunicorn (no separate reverse proxy needed):

1. `CompressedManifestStaticFilesStorage` compresses and fingerprints files at build time
2. `WhiteNoiseMiddleware` serves from `STATIC_ROOT` with cache headers
3. `python manage.py collectstatic` runs during Docker build (requires `COLLECTSTATIC_SECRET_KEY` build arg)

### Rate Limiting & Caching

- **Rate limit**: 10,000 requests/day per IP (`DEFAULT_THROTTLE_RATES.anon`)
- **Pagination**: 10 items per page (`PAGE_SIZE`)
- **ETag caching**: `ConditionalGetMiddleware` generates ETags; browsers get HTTP 304 on cache hits
- **Server-side cache**: `LocMemCache` with 60s timeout (used for resource stats in about page)

### CORS Policy

`django-cors-headers` allows any origin to make GET requests to `/api/*` only:

```python
CORS_ALLOW_ALL_ORIGINS = True
CORS_URLS_REGEX = r'^/api/.*$'
CORS_ALLOW_METHODS = ['GET']
```

Non-API routes (web views) are not exposed to cross-origin requests.

## Testing Strategy

Test suite location: `resources/tests.py` and `swapi/tests.py` (160 tests total)

**Coverage areas**:
- Models: field persistence, `__str__`, FK/M2M relations, optional fields
- Renderer: WookieeRenderer character translation, valid UTF-8 output
- API endpoints: 200 responses, pagination shape, all serializer fields present, 404, 405 on write methods, search functionality
- Schema endpoints: 200 responses, valid JSON objects
- Middleware: ETag headers, If-None-Match → 304, CORS headers on `/api/*`
- Web views: template rendering, auth requirements, Stripe integration (mocked)

When adding new fields to models:
1. Add field to model
2. Create and run migration
3. Add field to serializer's `fields` tuple
4. Add test in corresponding test class verifying field appears in API response
5. Update fixture data if needed

## Container Build

Two-stage Dockerfile:
- **builder stage**: Runs `pip install --prefix=/deps`, produces compiled wheel tree
- **runtime stage**: Copies `/deps`, runs `collectstatic`, drops to non-root user `swapi`

Build tools (gcc, pip cache) never reach runtime image.

The `docker-entrypoint.sh` performs startup sequence:
1. Wait for database (retries PostgreSQL connection if `DATABASE_URL` is set)
2. Run migrations (`manage.py migrate --noinput`)
3. Load fixtures if `LOAD_FIXTURES=true`
4. Hand off to Gunicorn

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):

**On every PR and push**:
- Job `test`: Python 3.12, pip install, `manage.py test --verbosity=2`

**On push to main/master only**:
- Job `build-and-push`: Builds Docker image with BuildKit cache (`type=gha`), pushes to `ghcr.io/<owner>/swapi:latest` and `ghcr.io/<owner>/swapi:sha-<commit>`

The build uses a disposable `COLLECTSTATIC_SECRET_KEY` build arg. Real `SECRET_KEY` is injected at runtime.

## Web Views vs API

This project has two surfaces:

1. **API endpoints** (`/api/*`): Django REST Framework viewsets, JSON responses, CORS-enabled
2. **Web views** (`/`, `/documentation`, `/about`, `/stats`, `/stripe/donation`): Django templates (Bootstrap 3), server-side rendered HTML

Web view locations: `swapi/views.py` + templates in `swapi/templates/`

The `/stats` view requires authentication (`@login_required`) — all others are public.

## Common Pitfalls

- **Don't add write operations**: All viewsets are `ReadOnlyModelViewSet` by design. Adding POST/PUT/DELETE breaks the API contract.
- **Don't use ModelSerializer**: Serializers must be `HyperlinkedModelSerializer` to maintain hypermedia links.
- **Don't skip migrations**: After model changes, always `makemigrations` and `migrate` before testing.
- **Don't commit without SECRET_KEY**: Test commands will fail. Always set `SECRET_KEY=test-secret DEBUG=True` for test runs.
- **Don't edit Transport directly**: When modifying shared vehicle fields, remember that `Transport` is a parent class — changes affect both `Starship` and `Vehicle`.
