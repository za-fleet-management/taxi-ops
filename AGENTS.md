# TaxiOps — Agent Instructions

South African taxi fleet management platform.

**Canonical build spec:** `taxi-ops-build-python.md` (read first before any coding).
**Status:** Phase 0 (Foundation) complete. Phases 1–3 pending.

## Commands

```bash
pip install -e ".[dev]"    # install deps (run after any pyproject.toml change)
alembic revision --autogenerate -m "msg"   # create migration
alembic upgrade head        # apply pending migrations
python -m pytest tests/ -v  # run all tests
uvicorn app.main:app --reload  # dev server
```

## Build Order

Implement strictly in phase order. Do not skip ahead.

1. **Phase 0** ✅ — FastAPI scaffold, SQLAlchemy + Alembic + SQLite, Organisation/User migrations, JWT auth with row-level tenant isolation. *Test that org A cannot read/write org B's data before moving on.*
2. **Phase 1** — Auth flows (signup/login/invite), Taxi/Driver CRUD, DailyIncome/Breakdown entry, offline IndexedDB queue.
3. **Phase 2** — Reporting dashboard (income aggregation, driver performance, downtime cost).
4. **Phase 3** — Fuel/Route tracking, route profitability, cost-of-operations reports.

## Non-Negotiable Rules

- **Multi-tenancy by row-level `organisation_id`.** Every tenant-scoped query must include `WHERE organisation_id = ?`. The `organisation_id` comes from JWT claims, never from request body/query/headers.
- **Money is integer cents.** Store `total_cash`, `cost_total` as INTEGER (ZAR cents). Display divide by 100 with `R` prefix. Never use float for currency.
- **Login by phone number**, not email.
- **SQLite only.** No Redis, no Postgres, no external services. Single file.
- **FastAPI serves both HTML (Jinja2) and JSON (`/api/*`).** No separate frontend app, no Node/npm build step. Tailwind via CDN, htmx for partial updates, vanilla JS for offline queue.
- **UUID v4 TEXT primary keys** — no auto-increment IDs.
- **JWT stateless auth.** Access token TTL 12h, refresh token 30d (httpOnly cookie). bcrypt cost 12.
- **One user belongs to exactly one organisation** in v1.

## Testing

- Multi-tenant isolation test exists at `tests/test_tenant_isolation.py` — must keep passing.
- Every phase ends with a "Definition of Done" checklist in the build spec — do not start the next phase until every item is checked.

## Stack

Python, FastAPI, SQLAlchemy (sync), Alembic, SQLite, Jinja2, htmx, Pydantic v2, bcrypt, python-jose. Single Uvicorn/Gunicorn process behind Nginx on one EC2 instance.

## Project Structure

```
app/
  main.py           # FastAPI app + HTML page routes
  config.py         # Settings from env
  database.py       # SQLAlchemy engine + session
  core/security.py  # JWT + bcrypt (not passlib — bcrypt lib directly)
  api/auth.py       # /api/auth/* routes
  api/deps.py       # get_current_user, require_owner
  models/           # SQLAlchemy ORM models
  schemas/          # Pydantic v2 schemas
  templates/        # Jinja2 (Tailwind CDN)
```

## If Ambiguous

Stop and flag it. Do not guess silently.
