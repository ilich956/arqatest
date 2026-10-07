import pytest

from tests.factories import cash_trip_payload, trip_payload


def post(client, payload):
    return client.post("/api/trips", json=payload)


def test_add_then_read_back_trips_and_summary(client):
    assert post(client, trip_payload()).status_code == 201
    assert post(client, cash_trip_payload()).status_code == 201

    trips = client.get("/api/trips", params={"date": "2026-10-01"}).json()
    summary = client.get("/api/summary", params={"date": "2026-10-01"}).json()

    assert [t["id"] for t in trips] == ["t1", "t2"]
    assert summary["trips"] == 2
    assert summary["revenue"] == 3900
    assert summary["commission"] == 585
    assert summary["net"] == 3315
    assert summary["by_payment"]["cash"] == {"trips": 1, "revenue": 1500, "commission": 225, "net": 1275}
    assert summary["by_payment"]["card"] == {"trips": 1, "revenue": 2400, "commission": 360, "net": 2040}


def test_other_days_are_empty(client):
    post(client, trip_payload())

    assert client.get("/api/trips", params={"date": "2026-10-02"}).json() == []
    assert client.get("/api/summary", params={"date": "2026-10-02"}).json()["trips"] == 0


def test_repeated_post_returns_200_and_creates_no_duplicate(client):
    first = post(client, trip_payload())
    second = post(client, trip_payload())

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(client.get("/api/trips", params={"date": "2026-10-01"}).json()) == 1


def test_same_id_with_different_data_returns_409(client):
    post(client, trip_payload())

    response = post(client, trip_payload(amount=5000))

    assert response.status_code == 409
    assert client.get("/api/summary", params={"date": "2026-10-01"}).json()["revenue"] == 2400


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 0},
        {"amount": -100},
        {"amount": 12.5},
        {"amount": "2400"},
        {"commission": -1},
        {"commission": 5000},
        {"end": "2026-10-01T08:10:00+05:00"},  # end == start
        {"end": "2026-10-01T08:00:00+05:00"},  # end before start
        {"start": "2026-10-01T08:10:00"},  # no timezone
        {"payment": "bitcoin"},
        {"id": ""},
    ],
    ids=lambda o: ",".join(f"{k}={v}" for k, v in o.items()),
)
def test_invalid_trips_are_rejected_and_not_stored(client, overrides):
    response = post(client, trip_payload(**overrides))

    assert response.status_code == 422
    assert client.get("/api/trips", params={"date": "2026-10-01"}).json() == []


def test_missing_field_is_rejected(client):
    payload = trip_payload()
    del payload["payment"]

    assert post(client, payload).status_code == 422


def test_bad_date_parameter_is_rejected(client):
    assert client.get("/api/trips", params={"date": "not-a-date"}).status_code == 422


def test_config_exposes_offset_and_today(client):
    config = client.get("/api/config").json()

    assert config["utc_offset"] == "+05:00"
    assert len(config["today"]) == 10


def test_client_page_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Driver Shift Diary" in response.text
