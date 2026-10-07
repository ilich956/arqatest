# CLAUDE.md

This file is a project handoff for AI coding assistants working on Driver Shift Diary.

## Project Summary

Driver Shift Diary is a small Python backend application for tracking a driver's trips by shift/day.
It exposes an HTTP API for:

- listing trips for a selected day;
- calculating a daily summary;
- adding a validated trip;
- preventing duplicate trip creation on repeated submit.

The current production-style launch path is Docker Compose with PostgreSQL.
The original JSON trip file remains as sample data and as a local fallback storage mode.

## Tech Stack

- Python 3.11+ / 3.12 tested locally.
- FastAPI for HTTP API.
- Pydantic v2 for domain validation.
- PostgreSQL for Docker Compose storage.
- `psycopg` v3 for PostgreSQL access.
- `pytest` for tests.

There are static files under `app/static`, but treat this project primarily as a backend/API project.
Do not expand UI behavior unless explicitly requested.

## Main Commands

Run with Docker Compose:

```bash
docker compose up --build
```

Run tests:

```bash
python -m pytest
```

Create and activate a local virtual environment on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Run locally without Docker:

```bash
uvicorn app.main:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

## Configuration

Settings are read from environment variables in `app/config.py`.

| Variable | Default | Meaning |
|---|---|---|
| `DIARY_STORAGE` | `auto` | Storage backend: `auto`, `json`, or `postgres`. |
| `DIARY_DATABASE_URL` | unset | PostgreSQL connection URL. Required when `DIARY_STORAGE=postgres`. |
| `DIARY_DATA_FILE` | `data/trips.json` | JSON storage file used by JSON mode. |
| `DIARY_UTC_OFFSET_HOURS` | `5` | Driver timezone as UTC offset. |
| `DIARY_LOG_LEVEL` | `INFO` | Python logging level. |

Storage selection:

- `DIARY_STORAGE=postgres`: always use PostgreSQL.
- `DIARY_STORAGE=json`: always use JSON file storage.
- `DIARY_STORAGE=auto`: use PostgreSQL if `DIARY_DATABASE_URL` exists, otherwise JSON.

Docker Compose sets:

```text
DIARY_STORAGE=postgres
DIARY_DATABASE_URL=postgresql://diary:diary@db:5432/driver_shift_diary
```

## API Behavior

Endpoints live in `app/api.py` under `/api`.

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/api/config` | Returns today's date and configured UTC offset. |
| `GET` | `/api/days` | Returns all days that have stored trips. |
| `GET` | `/api/trips?date=YYYY-MM-DD` | Returns trips for the selected day. Defaults to today. |
| `GET` | `/api/summary?date=YYYY-MM-DD` | Returns daily totals and cash/card breakdown. Defaults to today. |
| `POST` | `/api/trips` | Adds one trip. Idempotent by `id`. |

Successful `POST /api/trips` outcomes:

- New trip: `201 Created`.
- Same `id` with identical trip data: `200 OK`.
- Same `id` with different data: `409 Conflict`.
- Invalid body: `422 Unprocessable Entity`.

Example trip:

```json
{
  "id": "t1",
  "start": "2026-10-01T08:10:00+05:00",
  "end": "2026-10-01T08:32:00+05:00",
  "amount": 2400,
  "payment": "card",
  "commission": 360
}
```

## Domain Rules

Domain models are in `app/domain.py`.

Trip validation:

- `id` must be a non-empty string, max 64 characters.
- `start` and `end` must be timezone-aware datetimes.
- `end` must be later than `start`.
- `amount` must be a strict integer greater than zero.
- `commission` must be a strict integer greater than or equal to zero.
- `commission` cannot exceed `amount`.
- `payment` must be `cash` or `card`.

Money values are integers to avoid floating point rounding issues.

## Summary Rules

Summary logic is in `app/summary.py`.

A trip belongs to the day of its `start` time in the driver's configured timezone.
The daily summary includes:

- total trip count;
- total revenue;
- total commission;
- net amount, calculated as `revenue - commission`;
- breakdown by `cash` and `card`.

## Persistence

Repository abstractions live in `app/repository.py`.

Implementations:

- `InMemoryTripRepository`: test/local memory storage.
- `JsonFileTripRepository`: reads/writes the JSON trip file.
- `PostgresTripRepository`: stores trips in PostgreSQL.

The service depends only on the `TripRepository` protocol.
Keep it that way.

PostgreSQL schema is created automatically by `PostgresTripRepository`.
The `trips.id` column is the primary key and enforces idempotency.

PostgreSQL columns:

- `id text primary key`
- `start_time timestamptz not null`
- `end_time timestamptz not null`
- `amount integer not null`
- `payment text not null`
- `commission integer not null`

Database checks enforce basic storage-level validity:

- `amount > 0`
- `payment in ('cash', 'card')`
- `commission >= 0`
- `end_time > start_time`
- `commission <= amount`

## Application Wiring

`app/application.py` is the composition root.

It is responsible for:

- reading settings;
- configuring logging;
- selecting the repository;
- creating `DiaryService`;
- registering API routes;
- serving static files after API routes.

Dependency direction should stay:

```text
api -> service -> repository / summary -> domain
```

Avoid making domain or service code depend on FastAPI, PostgreSQL, files, or environment variables.

## Logging

Logging is configured in `app/application.py`.

Current logging includes:

- application startup/storage selection;
- one log line per HTTP request;
- exception logs for failed requests.

Log level is controlled by `DIARY_LOG_LEVEL`.

## Docker Compose

`docker-compose.yml` defines:

- `app`: builds the local Dockerfile and runs Uvicorn.
- `db`: PostgreSQL 16 Alpine.
- `postgres_data`: persistent database volume.

The app waits for the database healthcheck before starting.

Useful commands:

```bash
docker compose up --build
docker compose down
docker compose down -v
```

Use `docker compose down -v` only when intentionally deleting the local database volume.

## Data Folder

`data/trips.json` is not deprecated.

It exists because the original assignment used a JSON file as the trip data source.
In the current project it serves as:

- sample data;
- local JSON storage;
- fallback storage when `DIARY_STORAGE=auto` and no database URL is configured.

Docker Compose uses PostgreSQL and does not rely on `data/trips.json`.

## Tests

Tests are under `tests/`.

Current coverage includes:

- API response behavior and validation;
- daily summary calculation;
- duplicate protection;
- concurrent duplicate submission behavior;
- JSON repository persistence across restart;
- repository selection config.

Run:

```bash
python -m pytest
```

Known current result:

```text
33 passed, 1 warning
```

The warning is from FastAPI/Starlette test client dependency behavior and is not an app failure.

## Files Of Interest

```text
app/domain.py       Domain models and validation.
app/summary.py      Pure summary/date logic.
app/repository.py   Repository protocol plus memory, JSON, PostgreSQL storage.
app/service.py      Use cases and conflict behavior.
app/api.py          FastAPI routes.
app/application.py  App factory, logging, repository wiring.
app/config.py       Environment-based settings.
app/main.py         ASGI entry point.
data/trips.json     Sample/local JSON trip data.
Dockerfile          App image.
docker-compose.yml  App plus PostgreSQL runtime.
tests/              Test suite.
```

## Change Guidelines

- Keep business rules in `domain.py`, `summary.py`, and `service.py`.
- Keep HTTP details in `api.py`.
- Keep storage-specific details in `repository.py`.
- Preserve idempotency by trip `id`.
- Preserve strict integer validation for money fields.
- Add or update tests for behavior changes.
- Prefer small, focused changes over broad refactors.
- Do not remove JSON support unless the assignment requirements are explicitly changed.
