# SWAPI — The Star Wars API

A read-only REST API serving structured data from the Star Wars universe. Built with Django 5.2 and Django REST Framework; served by Gunicorn behind WhiteNoise for static assets.

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [API reference](#api-reference)
- [Local development](#local-development)
- [Running tests](#running-tests)
- [Container build](#container-build)
- [CI / CD](#ci--cd)
- [Configuration](#configuration)
- [Data management](#data-management)

---

## What it does

SWAPI exposes six Star Wars resources as a hypermedia JSON API:

| Resource | Count | Description |
|---|---|---|
| People | 82 | Characters (Luke Skywalker, Darth Vader, …) |
| Planets | 61 | Planets and planetoids (Tatooine, Hoth, …) |
| Films | 6 | The seven episodic films |
| Species | 37 | Alien and human species (Wookiee, Twi'lek, …) |
| Starships | 36 | Hyperdrive-capable craft (Millennium Falcon, …) |
| Vehicles | 39 | Non-hyperdrive transport (Sand Crawler, AT-AT, …) |

Every resource supports listing, detail lookup, case-insensitive partial search, and JSON Schema introspection. All responses are paginated at 10 items per page and rate-limited to 10,000 requests per day per IP. The API is publicly accessible with no authentication required.

A bonus **Wookiee encoding** (`?format=wookiee`) translates every lowercase letter in JSON responses into Wookiee syllables.

---

## Architecture

```
swapi/                      Django project package
├── settings.py             All configuration, driven by environment variables
├── urls.py                 URL routing (DRF DefaultRouter + web views)
├── views.py                Web views: home, documentation, about, stats, donation
├── wsgi.py                 WSGI entry point
└── templates/              Jinja-style Django templates (Bootstrap 3)

resources/                  Django application — the API itself
├── models.py               ORM models: Planet, People, Transport, Starship,
│                           Vehicle, Species, Film
├── serializers.py          HyperlinkedModelSerializer for each resource
├── views.py                ReadOnlyModelViewSet for each resource
├── renderers.py            WookieeRenderer (extends JSONRenderer)
├── schemas/                Static JSON Schema files served at /api/<resource>/schema
├── fixtures/               Seed data (JSON, loaded with loaddata)
└── tests.py                160-test suite
```

**Key design choices:**

- **Read-only API.** All viewsets extend `ReadOnlyModelViewSet`. Write operations return HTTP 405.
- **Hypermedia links.** Related resources are represented as absolute URLs (`HyperlinkedModelSerializer`), making the API self-describing.
- **Transport / Starship / Vehicle inheritance.** `Starship` and `Vehicle` extend `Transport` via Django multi-table inheritance, sharing common fields (name, model, manufacturer, crew, …) while adding type-specific ones.
- **WhiteNoise.** Static files are compressed and fingerprinted at build time by `CompressedManifestStaticFilesStorage` and served directly by the Gunicorn process without a reverse proxy.
- **ConditionalGetMiddleware.** ETag headers are generated for every response; browsers and clients receive HTTP 304 on cache hits.
- **CORS.** `django-cors-headers` allows any origin to make GET requests to `/api/*`. Non-API routes are not exposed.

---

## API reference

Full interactive documentation is available at `/documentation` when the server is running. Quick reference:

### Endpoints

Every resource follows the same pattern:

```
GET /api/                          API root — lists all resource URLs
GET /api/<resource>/               Paginated list (10 per page)
GET /api/<resource>/<id>/          Single resource detail
GET /api/<resource>/?search=<q>    Case-insensitive partial match
GET /api/<resource>/schema         JSON Schema for the resource
```

Search fields per resource:

| Resource | Search fields |
|---|---|
| People | `name` |
| Planets | `name` |
| Films | `title` |
| Species | `name` |
| Vehicles | `name`, `model` |
| Starships | `name`, `model` |

### Response format

```json
GET /api/people/1/

{
  "name": "Luke Skywalker",
  "height": "172",
  "mass": "77",
  "hair_color": "blond",
  "homeworld": "http://localhost:8000/api/planets/1/",
  "films": ["http://localhost:8000/api/films/1/", "..."],
  "url": "http://localhost:8000/api/people/1/",
  "created": "2014-12-09T13:50:51.644000Z",
  "edited": "2014-12-20T21:17:56.891000Z"
}
```

### Pagination

```json
GET /api/people/

{
  "count": 82,
  "next": "http://localhost:8000/api/people/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

### Wookiee encoding

Append `?format=wookiee` to any endpoint. Every lowercase letter is translated into a Wookiee syllable; JSON structure characters (`{`, `}`, `"`, `:`) pass through unchanged, so the result remains valid JSON.

```
GET /api/people/1/?format=wookiee
```

---

## Local development

### Prerequisites

- Python 3.12
- pip

### Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/ACN-APPSAS/swapi.git
cd swapi

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply database migrations (uses SQLite in dev)
SECRET_KEY=any-local-secret DEBUG=True python manage.py migrate

# 4. Load Star Wars data
SECRET_KEY=any-local-secret DEBUG=True python manage.py loaddata \
    planets people species transport starships vehicles films

# 5. Start the development server
SECRET_KEY=any-local-secret DEBUG=True python manage.py runserver
```

The API is available at `http://localhost:8000/api/` and the web UI at `http://localhost:8000/`.

> **Note:** `SECRET_KEY` and `DEBUG` must be set as environment variables. `DEBUG=True` uses SQLite and disables HTTPS enforcement. Never run with `DEBUG=True` in production.

---

## Running tests

```bash
SECRET_KEY=test-secret DEBUG=True python manage.py test
```

The test suite (`resources/tests.py` and `swapi/tests.py`) contains **160 tests** across 21 test classes:

| Area | Classes | What is covered |
|---|---|---|
| Models | `PlanetModelTests`, `PeopleModelTests`, `FilmModelTests`, `SpeciesModelTests` | Field persistence, `__str__`, FK / M2M relations, optional fields |
| Renderer | `WookieeRendererTests` | Full lookup coverage, passthrough chars, `render()` returns valid UTF-8 bytes |
| Utils | `UtilsTests` | `get_resource_stats()` keys, counts match DB |
| API root | `APIRootTests` | 200, all resource keys, values are URLs, POST → 405 |
| Resource endpoints | `People/Planet/Film/Species/Vehicle/StarshipEndpointTests` | List 200, pagination shape, detail 200, all serializer fields present, 404, 405 on all write methods, search by name and model, empty search |
| Schema endpoints | Per resource | 200, valid JSON object |
| Wookiee format | Per resource | 200, translated key / value match |
| Pagination | `PaginationTests` | Page size ≤ 10, `next` / `previous` links |
| ETag | `ETagTests` | Header present, `If-None-Match` → 304, stale tag → 200 |
| CORS | `CORSTests` | Header present on `/api/*`, absent elsewhere |
| Web views | `IndexViewTests`, `DocumentationViewTests`, `AboutViewTests` | 200, correct templates, context variables |
| Auth | `StatsViewTests` | Unauthenticated → 302 with `login` + `next`; authenticated → 200 |
| Stripe | `StripeDonationViewTests` | GET → redirect, POST → redirect, `Customer.create` / `Charge.create` called with correct args (mocked), failed charge logs and redirects, CSRF enforced (403 without token) |

---

## Container build

The `Dockerfile` uses a **two-stage build**:

| Stage | Base | Purpose |
|---|---|---|
| `builder` | `python:3.12-slim` | Runs `pip install --prefix=/deps`; produces compiled wheel tree only |
| `runtime` | `python:3.12-slim` | Copies `/deps → /usr/local`, runs `collectstatic`, drops to non-root user `swapi` |

Build tools (`gcc`, `pip`, cache) stay in the builder and never reach the runtime image.

### Build and run with Docker Compose

```bash
# 1. Create your environment file
cp .env.example .env
# Edit .env: set SECRET_KEY and DB_PASSWORD at minimum

# 2. Build and start (web + postgres:16-alpine)
docker compose up --build

# 3. On first run, seed the Star Wars data
LOAD_FIXTURES=true docker compose up --build
# or after the stack is up:
docker compose exec web python manage.py loaddata \
    planets people species transport starships vehicles films
```

The web service is available at `http://localhost:8000`.

### docker-compose.yml overview

```
services:
  db   — postgres:16-alpine with healthcheck (pg_isready)
  web  — built from Dockerfile; waits for db healthy before starting
```

The `web` service container start sequence (`docker-entrypoint.sh`):

1. **Wait for database** — retries the DB connection every 2 s (skipped when `DATABASE_URL` is not set, i.e. SQLite)
2. **Migrate** — `manage.py migrate --noinput`
3. **Seed** — `manage.py loaddata ...` if `LOAD_FIXTURES=true`
4. **Serve** — hands off to `gunicorn`

### Build the image standalone

```bash
docker build \
  --build-arg COLLECTSTATIC_SECRET_KEY=build-only \
  -t swapi:latest .
```

> The `COLLECTSTATIC_SECRET_KEY` build argument is a **disposable placeholder** used only during the `collectstatic` build step. The real `SECRET_KEY` must be injected at runtime via environment variable and never baked into the image.

---

## CI / CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every pull request and push to `main` / `master`:

### `test` job (every PR and push)

1. Sets up Python 3.12
2. `pip install -r requirements.txt` (pip cache enabled)
3. `python manage.py test --verbosity=2`

### `build-and-push` job (push to `main` / `master` only)

1. Logs in to GitHub Container Registry (`ghcr.io`)
2. Runs a multi-stage Docker build with BuildKit layer cache (`type=gha`) shared between workflow runs to keep the `pip install` stage fast
3. Pushes two tags:
   - `ghcr.io/<owner>/swapi:latest` — always the most recent build on the default branch
   - `ghcr.io/<owner>/swapi:sha-<commit>` — immutable per-commit tag for rollback

The build-and-push job will not run on pull requests, only on merges.

---

## Configuration

All configuration is driven by environment variables. No secrets are hardcoded.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | Django secret key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | No | `False` | Set to `True` in development only. Enables debug pages and SQLite. |
| `ALLOWED_HOSTS` | No | `*` | Comma-separated list of valid hostnames. Example: `swapi.example.com,www.swapi.example.com` |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string. Example: `postgres://user:pass@host:5432/db` |
| `GUNICORN_WORKERS` | No | `4` | Number of Gunicorn worker processes |
| `LOAD_FIXTURES` | No | `false` | Set to `true` to seed Star Wars data on container start |
| `STRIPE_SECRET_KEY` | No | — | Stripe secret key (production) |
| `STRIPE_PUBLISHABLE_KEY` | No | — | Stripe publishable key (production) |
| `STRIPE_TEST_SECRET_KEY` | No | — | Stripe secret key (development) |
| `STRIPE_TEST_PUBLISHABLE_KEY` | No | — | Stripe publishable key (development) |
| `KEEN_PROJECT_ID` | No | — | Keen.io project ID for analytics |
| `KEEN_WRITE_KEY` | No | — | Keen.io write key |
| `DB_PASSWORD` | No | `swapi` | PostgreSQL password (docker-compose only) |

Production security settings activated automatically when `DEBUG=False`:

- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000`

---

## Data management

Star Wars data lives in Django JSON fixtures under `resources/fixtures/`.

### Load all data

```bash
python manage.py loaddata planets people species transport starships vehicles films
```

### Update fixtures from the database

Use the `Makefile` targets after editing data through the Django admin (`/admin/`):

```bash
make dump_data    # exports all resources back to fixtures/
make load_data    # loads all fixtures into the database
make drop_db      # flushes all data (keeps schema)
```

### Admin interface

Create a superuser to access `/admin/`:

```bash
python manage.py createsuperuser
```
