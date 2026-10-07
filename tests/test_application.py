from app.application import create_repository
from app.config import Settings
from app.repository import JsonFileTripRepository


def test_auto_storage_uses_json_without_database_url(tmp_path):
    repository = create_repository(Settings(data_file=tmp_path / "trips.json"))

    assert isinstance(repository, JsonFileTripRepository)


def test_postgres_storage_requires_database_url(tmp_path):
    settings = Settings(storage="postgres", data_file=tmp_path / "trips.json")

    try:
        create_repository(settings)
    except RuntimeError as error:
        assert "DIARY_DATABASE_URL" in str(error)
    else:
        raise AssertionError("expected missing database URL to fail")
