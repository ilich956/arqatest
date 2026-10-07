import datetime as dt

from app.domain import PaymentMethod, PaymentTotals
from app.repository import InMemoryTripRepository
from app.service import DiaryService
from app.summary import summarize, trip_day
from tests.factories import make_cash_trip, make_trip

TZ = dt.timezone(dt.timedelta(hours=5))
DAY = dt.date(2026, 10, 1)


def test_summary_of_the_example_day():
    summary = summarize(DAY, [make_trip(), make_cash_trip()])

    assert summary.date == DAY
    assert summary.trips == 2
    assert summary.revenue == 3900
    assert summary.commission == 585
    assert summary.net == 3315
    assert summary.by_payment[PaymentMethod.CARD] == PaymentTotals(trips=1, revenue=2400, commission=360, net=2040)
    assert summary.by_payment[PaymentMethod.CASH] == PaymentTotals(trips=1, revenue=1500, commission=225, net=1275)


def test_summary_of_an_empty_day_is_all_zeros():
    summary = summarize(DAY, [])

    assert (summary.trips, summary.revenue, summary.commission, summary.net) == (0, 0, 0, 0)
    assert summary.by_payment[PaymentMethod.CARD] == PaymentTotals()
    assert summary.by_payment[PaymentMethod.CASH] == PaymentTotals()


def test_unused_payment_method_is_still_reported():
    summary = summarize(DAY, [make_trip()])

    assert summary.by_payment[PaymentMethod.CASH].trips == 0
    assert summary.by_payment[PaymentMethod.CARD].trips == 1


def test_breakdown_adds_up_to_the_totals():
    trips = [make_trip(id=f"t{i}", amount=1000 + i, commission=i, payment="cash" if i % 2 else "card") for i in range(1, 8)]
    summary = summarize(DAY, trips)

    parts = summary.by_payment.values()
    assert sum(p.trips for p in parts) == summary.trips
    assert sum(p.revenue for p in parts) == summary.revenue
    assert sum(p.commission for p in parts) == summary.commission
    assert sum(p.net for p in parts) == summary.net


def test_trip_day_is_taken_in_the_drivers_timezone():
    just_after_midnight_local = make_trip(start="2026-10-02T00:30:00+05:00", end="2026-10-02T00:50:00+05:00")
    same_moment_in_utc = make_trip(id="t2", start="2026-10-01T20:00:00+00:00", end="2026-10-01T20:20:00+00:00")

    assert trip_day(just_after_midnight_local, TZ) == dt.date(2026, 10, 2)
    assert trip_day(same_moment_in_utc, TZ) == dt.date(2026, 10, 2)  # 01:00 local


def test_service_returns_only_the_requested_day_ordered_by_start():
    later = make_trip(id="late", start="2026-10-01T18:00:00+05:00", end="2026-10-01T18:30:00+05:00")
    earlier = make_trip(id="early")
    other_day = make_trip(id="other", start="2026-10-02T08:00:00+05:00", end="2026-10-02T08:20:00+05:00")
    service = DiaryService(InMemoryTripRepository([later, other_day, earlier]), TZ)

    assert [t.id for t in service.trips_for_day(DAY)] == ["early", "late"]
    assert service.summary_for_day(DAY).trips == 2
    assert service.summary_for_day(dt.date(2026, 10, 3)).trips == 0
    assert service.days_with_trips() == [DAY, dt.date(2026, 10, 2)]
