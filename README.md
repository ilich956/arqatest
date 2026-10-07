# Driver Shift Diary

A small web app for a taxi driver: pick a day, see the summary (trips, revenue, commission,
take-home, cash/card split) and the list of trips, and add new trips.

**Stack:** Python 3.11+, FastAPI, Pydantic v2, PostgreSQL, vanilla JS client (no build step), pytest.

## Run

Docker Compose is the primary launch path. It starts the app and PostgreSQL:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000 (the client) or http://127.0.0.1:8000/docs (interactive API docs).
PostgreSQL data is stored in the `postgres_data` Docker volume.

For local development without Docker you can still use the JSON repository:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

The app starts with sample trips for 2026-10-01, 02, 06 and 07 from `data/trips.json` only when the
JSON repository is used.

## Tests

```bash
pytest
```

| File | What it covers |
|---|---|
| `tests/test_summary.py` | summary calculation, empty day, cash/card split, timezone day boundaries, day filtering |
| `tests/test_deduplication.py` | repeat submit, conflicting id, 64 concurrent submits, restart with file storage |
| `tests/test_api.py` | endpoints, status codes (201/200/409/422), every validation rule |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/trips?date=YYYY-MM-DD` | Trips of the day ordered by start (default: today) |
| GET | `/api/summary?date=YYYY-MM-DD` | `trips`, `revenue`, `commission`, `net`, `by_payment.{cash,card}` |
| POST | `/api/trips` | Add a trip (see below) |
| GET | `/api/days` | Days that have trips |
| GET | `/api/config` | Today's date and the driver's UTC offset (used by the client) |

`POST /api/trips` body:

```json
{"id": "t3", "start": "2026-10-01T10:00:00+05:00", "end": "2026-10-01T10:20:00+05:00",
 "amount": 2000, "payment": "cash", "commission": 300}
```

Validation: `amount > 0`, `end > start`, `commission` between 0 and `amount`, `payment` is `cash` or `card`,
timestamps must carry a timezone offset, amounts are whole numbers. Invalid input → `422`.

Duplicate protection (idempotency by `id`):

| Situation | Response |
|---|---|
| New trip | `201 Created` |
| Same `id`, identical data (a retry) | `200 OK`, existing trip returned, nothing created |
| Same `id`, different data | `409 Conflict`, nothing changed |

## Architecture

```
app/
  domain.py       Trip (validation rules), DaySummary, PaymentMethod  — no I/O
  summary.py      pure functions: trip_day(), summarize()
  repository.py   TripRepository protocol; in-memory, JSON-file and PostgreSQL implementations
  service.py      DiaryService use cases: trips_for_day, summary_for_day, add_trip
  api.py          FastAPI routes and status codes
  application.py  create_app(): wiring (settings → repository → service → routes)
  config.py       Settings from environment variables
  static/         client: index.html, app.js, styles.css
data/trips.json   sample data / storage file
tests/
```

Dependencies point one way: `api → service → repository / summary → domain`. The service only knows
the `TripRepository` protocol, so replacing the JSON file with a database means writing one class.

## Design decisions

- **Money is `int`** (whole tenge): sums are exact, no float rounding. Float and string amounts are rejected.
- **A trip belongs to the day it starts, in the driver's timezone** (`DIARY_UTC_OFFSET_HOURS`, default `5`).
  A trip at 00:30+05:00 is on that day, not on the previous UTC day.
- **Duplicate protection is atomic.** The "exists? → insert" step runs under one lock, so parallel retries
  can't both succeed. The data file is written to a temp file and swapped in with `os.replace`,
  so it is never left half-written.
- **The client generates the trip `id`** once per form fill and keeps it until the server accepts the trip,
  so a double click or a retry after a network error is harmless.
- **The client never injects data as HTML** (`textContent` only).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DIARY_STORAGE` | `auto` | `auto`, `json`, or `postgres` |
| `DIARY_DATA_FILE` | `data/trips.json` | JSON storage file |
| `DIARY_DATABASE_URL` | unset | PostgreSQL connection URL |
| `DIARY_UTC_OFFSET_HOURS` | `5` | driver's timezone offset |
| `DIARY_LOG_LEVEL` | `INFO` | Python logging level |

## Limitations / next steps

PostgreSQL enforces duplicate protection with a primary key on `trips.id`. There is no authentication,
and no edit/delete of trips.

## AI tools

This project was built with Claude (Anthropic): architecture, code and tests were generated with it
and then run and reviewed. (Edit this section to describe your own use of AI tools.)
