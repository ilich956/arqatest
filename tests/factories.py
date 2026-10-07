"""Helpers for building valid trips in tests."""
from app.domain import Trip


def trip_payload(**overrides) -> dict:
    """Trip t1 from the task statement; override any field."""
    payload = {
        "id": "t1",
        "start": "2026-10-01T08:10:00+05:00",
        "end": "2026-10-01T08:32:00+05:00",
        "amount": 2400,
        "payment": "card",
        "commission": 360,
    }
    return {**payload, **overrides}


def cash_trip_payload(**overrides) -> dict:
    """Trip t2 from the task statement."""
    return trip_payload(
        id="t2",
        start="2026-10-01T09:05:00+05:00",
        end="2026-10-01T09:20:00+05:00",
        amount=1500,
        payment="cash",
        commission=225,
        **overrides,
    )


def make_trip(**overrides) -> Trip:
    return Trip.model_validate(trip_payload(**overrides))


def make_cash_trip(**overrides) -> Trip:
    return Trip.model_validate(cash_trip_payload(**overrides))
