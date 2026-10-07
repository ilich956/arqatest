"""Application factory: wires settings, storage, service and routes together."""
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import Settings
from app.repository import JsonFileTripRepository, PostgresTripRepository, TripRepository
from app.service import DiaryService

STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, repository: TripRepository | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    repository = repository if repository is not None else create_repository(settings)

    app = FastAPI(title="Driver Shift Diary", version="1.0.0")
    app.state.settings = settings
    app.state.service = DiaryService(repository, settings.tz)
    app.middleware("http")(log_requests)
    app.include_router(router)
    # Mounted last so it never shadows /api routes.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="client")
    logger.info("application started", extra={"storage": settings.storage})
    return app


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_repository(settings: Settings) -> TripRepository:
    storage = settings.storage
    if storage == "auto":
        storage = "postgres" if settings.database_url else "json"

    if storage == "postgres":
        if not settings.database_url:
            raise RuntimeError("DIARY_DATABASE_URL is required when DIARY_STORAGE=postgres")
        logger.info("using PostgreSQL trip repository")
        return PostgresTripRepository(settings.database_url)

    if storage == "json":
        logger.info("using JSON trip repository at %s", settings.data_file)
        return JsonFileTripRepository(settings.data_file)

    raise RuntimeError("DIARY_STORAGE must be one of: auto, json, postgres")


async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception("%s %s failed after %.1fms", request.method, request.url.path, elapsed_ms)
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("%s %s -> %s %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
    return response
