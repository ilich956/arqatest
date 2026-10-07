"""Trip storage. The service depends only on the `TripRepository` protocol."""
import json
import os
import tempfile
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from app.domain import Trip


class TripRepository(Protocol):
    def add_if_absent(self, trip: Trip) -> tuple[Trip, bool]:
        """Atomically store `trip` unless its id exists.

        Returns (stored_trip, created). When created is False, stored_trip is the
        previously stored trip with that id.
        """
        ...

    def all(self) -> list[Trip]: ...


class InMemoryTripRepository:
    """Thread-safe in-memory repository (also the base of the file-backed one)."""

    def __init__(self, trips: Iterable[Trip] = ()) -> None:
        self._lock = threading.Lock()
        self._trips: dict[str, Trip] = {t.id: t for t in trips}

    def add_if_absent(self, trip: Trip) -> tuple[Trip, bool]:
        # The check and the insert happen under one lock: concurrent retries
        # of the same trip cannot both succeed.
        with self._lock:
            existing = self._trips.get(trip.id)
            if existing is not None:
                return existing, False
            # Persist first, so a failed write leaves memory untouched.
            self._persist([*self._trips.values(), trip])
            self._trips[trip.id] = trip
            return trip, True

    def all(self) -> list[Trip]:
        with self._lock:
            return list(self._trips.values())

    def _persist(self, trips: list[Trip]) -> None:
        """Hook for subclasses; nothing to do in memory."""


class JsonFileTripRepository(InMemoryTripRepository):
    """Keeps trips in memory and writes the whole list to a JSON file on every change."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        super().__init__(self._load())

    def _load(self) -> list[Trip]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [Trip.model_validate(item) for item in raw]

    def _persist(self, trips: list[Trip]) -> None:
        payload = json.dumps([t.model_dump(mode="json") for t in trips], ensure_ascii=False, indent=2)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file and atomically swap it in: no half-written data file.
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(payload)
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise


class PostgresTripRepository:
    """PostgreSQL-backed repository with idempotency enforced by the primary key."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_schema()

    def add_if_absent(self, trip: Trip) -> tuple[Trip, bool]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO trips (id, start_time, end_time, amount, payment, commission)
                    VALUES (%(id)s, %(start)s, %(end)s, %(amount)s, %(payment)s, %(commission)s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id, start_time, end_time, amount, payment, commission
                    """,
                    self._params(trip),
                )
                row = cursor.fetchone()
                if row is not None:
                    return self._trip_from_row(row), True

                cursor.execute(
                    """
                    SELECT id, start_time, end_time, amount, payment, commission
                    FROM trips
                    WHERE id = %(id)s
                    """,
                    {"id": trip.id},
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise RuntimeError("trip insert conflicted, but existing trip was not found")
                return self._trip_from_row(existing), False

    def all(self) -> list[Trip]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, start_time, end_time, amount, payment, commission
                    FROM trips
                    ORDER BY start_time, id
                    """
                )
                return [self._trip_from_row(row) for row in cursor.fetchall()]

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trips (
                        id text PRIMARY KEY,
                        start_time timestamptz NOT NULL,
                        end_time timestamptz NOT NULL,
                        amount integer NOT NULL CHECK (amount > 0),
                        payment text NOT NULL CHECK (payment IN ('cash', 'card')),
                        commission integer NOT NULL CHECK (commission >= 0),
                        CHECK (end_time > start_time),
                        CHECK (commission <= amount)
                    )
                    """
                )

    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self._database_url, row_factory=dict_row)

    @staticmethod
    def _params(trip: Trip) -> dict[str, object]:
        return {
            "id": trip.id,
            "start": trip.start,
            "end": trip.end,
            "amount": trip.amount,
            "payment": trip.payment.value,
            "commission": trip.commission,
        }

    @staticmethod
    def _trip_from_row(row: dict[str, object]) -> Trip:
        return Trip.model_validate(
            {
                "id": row["id"],
                "start": row["start_time"],
                "end": row["end_time"],
                "amount": row["amount"],
                "payment": row["payment"],
                "commission": row["commission"],
            }
        )
