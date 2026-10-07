import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.config import Settings
from app.repository import InMemoryTripRepository


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_file=tmp_path / "trips.json", utc_offset_hours=5)


@pytest.fixture
def client(settings) -> TestClient:
    return TestClient(create_app(settings, InMemoryTripRepository()))
