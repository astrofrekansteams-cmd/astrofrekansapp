# Astrofrekans Backend

FastAPI service behind the Astrofrekans mobile app: accounts, birth data and
the astrology engine. The Flutter app is a pure client - it never computes a
chart and never holds an AI key.

* **Stack**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic,
  PostgreSQL, Redis, Skyfield (JPL DE421 ephemeris).
* **Docs** (repository root `docs/`): `platform_architecture.md` (automated /
  expert / hybrid service model and the marketplace design),
  `backend_architecture.md`, `api_contracts.md`, `astrology_engine.md`,
  `transit_engine.md`, `horary_engine.md`, `synastry_engine.md`,
  `composite_davison.md`.

---

## Quick start (local)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate           # Windows;  source .venv/bin/activate on Unix
pip install -r requirements-dev.txt
python scripts/download_ephemeris.py      # ~16 MB, one time
cp .env.example .env                      # then fill in the secrets
docker compose up -d postgres redis
alembic upgrade head
python scripts/seed_services.py           # service catalogue (idempotent)
uvicorn app.main:app --reload
```

OpenAPI UI: <http://127.0.0.1:8000/docs> · probes: `/health`, `/ready`.

Generate the JWT secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Everything in Docker

```bash
cd backend
cp .env.example .env     # JWT_SECRET and JWT_REFRESH_SECRET are required
docker compose up --build
```

`api` waits for healthy `postgres` and `redis`, runs `alembic upgrade head`,
then serves on `http://localhost:8000`. The ephemeris kernel is baked into the
image, so the container needs no network access at boot.

## Migrations

```bash
alembic upgrade head                        # apply
alembic downgrade -1                        # roll back one
alembic revision --autogenerate -m "..."    # new revision from model changes
alembic check                               # fail if models and schema differ
```

`alembic check` is the guard against schema drift; run it in CI.

## Tests

```bash
pytest                       # whole suite
pytest tests/test_astrology_engine.py -q    # engine regressions only
```

The suite is offline and needs no services: SQLite replaces Postgres, an
in-process cache replaces Redis, and the geocoder is the mock provider. The
astrology engine is **not** mocked - the point of those tests is that real
positions come out right.

## Environment

See `.env.example` for the full list. The ones that matter:

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `local` / `test` / `staging` / `production`. Production boots only with real secrets and an explicit CORS list. |
| `DATABASE_URL` | `postgresql+asyncpg://…` |
| `REDIS_URL` | Cache and rate limiting. Empty falls back to an in-process cache (single worker only). |
| `JWT_SECRET`, `JWT_REFRESH_SECRET` | Must differ, and must not be the development defaults in production. |
| `CORS_ORIGINS` | Comma separated. Empty is correct for a mobile-only deployment; `*` is never used. |
| `EPHEMERIS_PATH` | Path to `de421.bsp`. |
| `GEOCODING_PROVIDER` | `mock` (offline table) or `nominatim`. |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Server side only, used from phase B6. Never shipped to the app. |

`.env` is git-ignored. No secret belongs in the repository, in a log line or
in a client build.

## API overview

All routes are under `/api/v1`. Errors always look like:

```json
{"error": {"code": "invalid_credentials", "message": "…", "details": {}}}
```

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/register` | Optional birth data; returns a token pair |
| POST | `/auth/login` | Rate limited |
| POST | `/auth/refresh` | Rotates the refresh token |
| POST | `/auth/logout`, `/auth/logout-all` | |
| POST | `/auth/forgot-password`, `/auth/reset-password` | Same answer for unknown addresses |
| POST | `/auth/change-password` | Revokes every session |
| GET | `/auth/me`, `/users/me` | |
| PATCH | `/users/me` | Name, language, timezone, avatar |
| DELETE | `/users/me` | Soft delete + session revocation |
| GET/PUT | `/birth-profiles/me` | Primary birth profile |
| GET | `/birth-profiles` | |
| GET/POST/DELETE | `/saved-people` | Partner / friend / family charts |
| GET | `/geocode?query=` | Place -> coordinates + IANA timezone |
| GET | `/astrology/natal-chart/me` | Cached; `?house_system=`, `?refresh=` |
| POST | `/astrology/natal-chart` | Arbitrary birth data |
| GET | `/astrology/positions` | Current or given instant |
| GET | `/astrology/moon-phase` | Phase, illumination, age, next phase |
| POST/GET | `/horary/questions` | Ask a horary question, list them |
| POST | `/horary/questions/{id}/calculate` | Cast the chart |
| GET | `/horary/questions/{id}/analysis` | Structured analysis, no verdict |
| POST | `/compatibility/synastry` | Inter-aspects, directional house overlays, theme scores |
| POST | `/compatibility/composite` | Midpoint composite chart |
| POST | `/compatibility/davison` | Real chart for the midpoint time and place |
| GET | `/compatibility/reports`, `/compatibility/reports/{id}` | Stored snapshots |
| GET | `/services` | Service catalogue; filter by `category`, `fulfillment_mode` |
| GET | `/services/{code}` | One service definition |
| GET | `/health`, `/ready` | Unversioned probes |

## Conventions

* Every instant crossing the API is UTC ISO-8601. Birth data additionally
  carries the IANA zone of the birth place; the local wall-clock time and the
  UTC instant are always both available and never conflated.
* Enum values are `snake_case` strings (`north_node`, `whole_sign`,
  `waxing_gibbous`) and match the Flutter client's enums.
* Longitudes are degrees `0-360`; `degree`/`minute` are the astrologer-facing
  split inside the sign.
* Nothing astrological is computed by an LLM.
* Money is integer minor units plus an ISO-4217 code (`Money` in
  `app/domain/marketplace.py`); floats never touch prices or commission.
* A chart is cast for a `subject` - an instant, a place, a house system. Natal
  uses the birth moment, horary the moment the question was asked.
* Scores are astrological factor indices, never probabilities; the API says so
  in `score_semantics`. Horary returns no verdict at all.
* Techniques the engine cannot detect reliably are declared in
  `not_implemented` rather than omitted silently.
