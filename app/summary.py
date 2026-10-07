"""Pure functions for grouping trips by day and computing the daily summary."""
import datetime as dt
from collections.abc import Iterable

from app.domain import DaySummary, PaymentMethod, PaymentTotals, Trip


def trip_day(trip: Trip, tz: dt.tzinfo) -> dt.date:
    """The driver's calendar day a trip belongs to (by its start time)."""
    return trip.start.astimezone(tz).date()


def _totals(trips: list[Trip]) -> dict[str, int]:
    revenue = sum(t.amount for t in trips)
    commission = sum(t.commission for t in trips)
    return {
        "trips": len(trips),
        "revenue": revenue,
        "commission": commission,
        "net": revenue - commission,
    }


def summarize(day: dt.date, trips: Iterable[Trip]) -> DaySummary:
    """Build the summary for `day` from trips that already belong to that day.

    Every payment method is always present in `by_payment`, even with zero trips.
    """
    trips = list(trips)
    by_payment = {
        method: PaymentTotals(**_totals([t for t in trips if t.payment is method]))
        for method in PaymentMethod
    }
    return DaySummary(date=day, by_payment=by_payment, **_totals(trips))
