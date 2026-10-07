"""Application settings (read from environment variables)."""
import os
from dataclasses import dataclass
from datetime import timedelta, timezone, tzinfo
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """Runtime configuration.

    DIARY_STORAGE          storage backend: auto, json, postgres (default: auto)
    DIARY_DATA_FILE        path to the JSON file with trips       (default: data/trips.json)
    DIARY_DATABASE_URL     PostgreSQL connection URL              (optional)
    DIARY_UTC_OFFSET_HOURS driver's timezone as a UTC offset      (default: 5, i.e. Astana)
    DIARY_LOG_LEVEL        Python logging level                   (default: INFO)
    """

    storage: str = "auto"
    data_file: Path = BASE_DIR / "data" / "trips.json"
    database_url: str | None = None
    utc_offset_hours: int = 5
    log_level: str = "INFO"

    @property
    def tz(self) -> tzinfo:
        return timezone(timedelta(hours=self.utc_offset_hours))

    @property
    def utc_offset_iso(self) -> str:
        """Offset formatted for ISO-8601 strings, e.g. '+05:00'."""
        minutes = self.utc_offset_hours * 60
        sign = "+" if minutes >= 0 else "-"
        hours, mins = divmod(abs(minutes), 60)
        return f"{sign}{hours:02d}:{mins:02d}"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            storage=os.getenv("DIARY_STORAGE", cls.storage).lower(),
            data_file=Path(os.getenv("DIARY_DATA_FILE", cls.data_file)),
            database_url=os.getenv("DIARY_DATABASE_URL"),
            utc_offset_hours=int(os.getenv("DIARY_UTC_OFFSET_HOURS", cls.utc_offset_hours)),
            log_level=os.getenv("DIARY_LOG_LEVEL", cls.log_level).upper(),
        )
