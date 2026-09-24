from datetime import date

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def make_payload():
    return {
        "maintenance": {
            "maintenance_id": "MW-001",
            "asset_id": "ASSET-001",
            "asset_type": "Track",
            "location": "Chennai",
            "maintenance_type": "Inspection",
            "maintenance_required": True,
            "priority": "High",
            "duration_minutes": 120,
            "requested_date": "2026-09-22",
            "preferred_start": "10:00:00",
            "required_resources": 2,
            "equipment": "Inspection Kit",
            "status": "Pending",
            "source": "smms",
        },
        "reference_date": "2026-09-22",
    }


def test_prioritization_endpoint_exists():
    response = client.post(
        "/api/prioritization",
        json=make_payload(),
    )

    assert response.status_code == 200


def test_prioritization_response_contains_required_fields():
    response = client.post(
        "/api/prioritization",
        json=make_payload(),
    )

    data = response.json()

    assert "maintenance_id" in data
    assert "factors" in data
    assert "priority_value" in data
    assert "explanation" in data
    assert "confidence" in data


def test_prioritization_returns_five_factors():
    response = client.post(
        "/api/prioritization",
        json=make_payload(),
    )

    factors = response.json()["factors"]

    assert set(factors.keys()) == {
        "urgency",
        "criticality",
        "overdue_factor",
        "asset_availability_impact",
        "operational_impact",
    }


def test_prioritization_accepts_custom_weights():
    payload = make_payload()

    payload["weights"] = {
        "urgency": 0.60,
        "criticality": 0.10,
        "overdue_factor": 0.10,
        "asset_availability_impact": 0.10,
        "operational_impact": 0.10,
    }

    response = client.post(
        "/api/prioritization",
        json=payload,
    )

    assert response.status_code == 200
    assert 0 <= response.json()["priority_value"] <= 100


def test_prioritization_rejects_invalid_factor_input():
    payload = make_payload()

    payload["maintenance"]["duration_minutes"] = 0

    response = client.post(
        "/api/prioritization",
        json=payload,
    )

    assert response.status_code == 422


def test_prioritization_preserves_maintenance_id():
    response = client.post(
        "/api/prioritization",
        json=make_payload(),
    )

    assert response.status_code == 200
    assert response.json()["maintenance_id"] == "MW-001"