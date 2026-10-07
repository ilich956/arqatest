"""HTTP layer: routes, request parsing and status codes."""
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.domain import DaySummary, Trip
from app.service import DiaryService, TripConflictError

router = APIRouter(prefix="/api")


def get_service(request: Request) -> DiaryService:
    return request.app.state.service


ServiceDep = Annotated[DiaryService, Depends(get_service)]
DayQuery = Annotated[
    dt.date | None,
    Query(alias="date", description="Day as YYYY-MM-DD; defaults to today"),
]


@router.get("/config")
def get_config(request: Request, service: ServiceDep) -> dict[str, str]:
    """Settings the client needs: today's date and the driver's UTC offset."""
    return {
        "today": service.today().isoformat(),
        "utc_offset": request.app.state.settings.utc_offset_iso,
    }


@router.get("/days")
def list_days(service: ServiceDep) -> list[dt.date]:
    """All days that have at least one trip."""
    return service.days_with_trips()


@router.get("/trips")
def list_trips(service: ServiceDep, day: DayQuery = None) -> list[Trip]:
    """Trips of the given day, ordered by start time."""
    return service.trips_for_day(day or service.today())


@router.get("/summary")
def get_summary(service: ServiceDep, day: DayQuery = None) -> DaySummary:
    """Summary of the given day: trips, revenue, commission, net, cash/card split."""
    return service.summary_for_day(day or service.today())


@router.post(
    "/trips",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Identical trip already existed; nothing was created"},
        409: {"description": "Same id already used by a different trip"},
    },
)
def add_trip(trip: Trip, response: Response, service: ServiceDep) -> Trip:
    """Add a trip. Idempotent by `id`: re-sending the same trip returns 200, not a duplicate."""
    try:
        result = service.add_trip(trip)
    except TripConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result.trip
