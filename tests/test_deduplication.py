import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.repository import InMemoryTripRepository, JsonFileTripRepository
from app.service import DiaryService, TripConflictError
from tests.factories import make_trip

TZ = dt.timezone(dt.timedelta(hours=5))
DAY = dt.date(2026, 10, 1)


@pytest.fixture
def service() -> DiaryService:
    return DiaryService(InMemoryTripRepository(), TZ)


def test_first_submission_creates_the_trip(service):
    result = service.add_trip(make_trip())

    assert result.created is True
    assert len(service.trips_for_day(DAY)) == 1


def test_resubmitting_the_same_trip_creates_no_duplicate(service):
    service.add_trip(make_trip())
    second = service.add_trip(make_trip())

    assert second.created is False
    assert len(service.trips_for_day(DAY)) == 1
    assert service.summary_for_day(DAY).revenue == 2400  # counted once


def test_same_moment_in_another_offset_is_the_same_trip(service):
    service.add_trip(make_trip())
    retry = make_trip(start="2026-10-01T03:10:00+00:00", end="2026-10-01T03:32:00+00:00")

    assert service.add_trip(retry).created is False


def test_same_id_with_different_data_is_a_conflict_and_changes_nothing(service):
    service.add_trip(make_trip())

    with pytest.raises(TripConflictError):
        service.add_trip(make_trip(amount=9999, commission=1))

    assert [t.amount for t in service.trips_for_day(DAY)] == [2400]


def test_concurrent_submissions_of_one_trip_create_exactly_one(service):
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: service.add_trip(make_trip()), range(64)))

    assert sum(r.created for r in results) == 1
    assert len(service.trips_for_day(DAY)) == 1


def test_no_duplicate_after_restart_when_data_is_stored_in_a_file(tmp_path):
    path = tmp_path / "trips.json"
    DiaryService(JsonFileTripRepository(path), TZ).add_trip(make_trip())

    restarted = DiaryService(JsonFileTripRepository(path), TZ)  # new process, same file
    result = restarted.add_trip(make_trip())

    assert result.created is False
    assert len(restarted.trips_for_day(DAY)) == 1
    assert len(JsonFileTripRepository(path).all()) == 1
