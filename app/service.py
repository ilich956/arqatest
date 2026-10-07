"""Use cases of the diary. No HTTP and no storage details here."""
import datetime as dt
from dataclasses import dataclass

from app.domain import DaySummary, Trip
from app.repository import TripRepository
from app.summary import summarize, trip_day


class TripConflictError(Exception):
    """A trip with the same id but different data already exists."""


@dataclass(frozen=True)
class AddResult:
    trip: Trip
    created: bool  # False means an identical trip was already stored (idempotent retry)


class DiaryService:
    def __init__(self, repository: TripRepository, tz: dt.tzinfo) -> None:
        self._repository = repository
        self._tz = tz

    def today(self) -> dt.date:
        return dt.datetime.now(self._tz).date()

    def trips_for_day(self, day: dt.date) -> list[Trip]:
        trips = [t for t in self._repository.all() if trip_day(t, self._tz) == day]
        return sorted(trips, key=lambda t: t.start)

    def summary_for_day(self, day: dt.date) -> DaySummary:
        return summarize(day, self.trips_for_day(day))

    def days_with_trips(self) -> list[dt.date]:
        return sorted({trip_day(t, self._tz) for t in self._repository.all()})

    def add_trip(self, trip: Trip) -> AddResult:
        """Store a trip. Re-sending the same trip is safe and creates no duplicate."""
        stored, created = self._repository.add_if_absent(trip)
        if not created and stored != trip:
            raise TripConflictError(f"Trip '{trip.id}' already exists with different data")
        return AddResult(trip=stored, created=created)
