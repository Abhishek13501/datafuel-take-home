from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_mumbai_report():
    response = client.get(
        "/osa",
        params={
            "city": "Mumbai",
            "date": "2026-09-28"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["city"] == "Mumbai"
    assert data["date"] == "2026-09-28"
    assert data["osa_pct"] is not None
    assert data["observations"] > 0


def test_invalid_city():
    response = client.get(
        "/osa",
        params={
            "city": "Hyderabad",
            "date": "2026-09-28"
        }
    )

    assert response.status_code == 400


def test_no_data():
    response = client.get(
        "/osa",
        params={
            "city": "Mumbai",
            "date": "2026-10-01"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "no_data"
    assert data["osa_pct"] is None
    assert data["observations"] == 0