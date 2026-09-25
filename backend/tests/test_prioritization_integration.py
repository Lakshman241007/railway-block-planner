from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def make_maintenance(
    maintenance_id="MW-001",
    priority="High",
    duration_minutes=120,
    required_resources=2,
    requested_date="2026-09-22",
):
    return {
        "maintenance_id": maintenance_id,
        "asset_id": f"ASSET-{maintenance_id}",
        "asset_type": "Track",
        "location": "Chennai",
        "maintenance_type": "Inspection",
        "maintenance_required": True,
        "priority": priority,
        "duration_minutes": duration_minutes,
        "requested_date": requested_date,
        "preferred_start": "10:00:00",
        "required_resources": required_resources,
        "equipment": "Inspection Kit",
        "status": "Pending",
        "source": "smms",
    }


def test_end_to_end_maintenance_prioritization():
    """Verify the complete MaintenanceWork → PriorityInformation flow."""

    payload = {
        "maintenance": make_maintenance(),
        "reference_date": "2026-09-22",
    }

    response = client.post("/api/prioritization", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert "maintenance_id" in data
    assert "factors" in data
    assert "priority_value" in data
    assert "explanation" in data
    assert "confidence" in data

    assert 0 <= data["priority_value"] <= 100
    assert 0 <= data["confidence"] <= 1

    for value in data["factors"].values():
        assert 0 <= value <= 100


def test_high_criticality_produces_higher_score_than_low_criticality():
    """Verify that the criticality factor affects the deterministic score."""

    high_payload = {
        "maintenance": make_maintenance(
            maintenance_id="MW-HIGH",
            priority="Critical",
        ),
        "reference_date": "2026-09-22",
    }

    low_payload = {
        "maintenance": make_maintenance(
            maintenance_id="MW-LOW",
            priority="Low",
        ),
        "reference_date": "2026-09-22",
    }

    high_response = client.post(
        "/api/prioritization",
        json=high_payload,
    )

    low_response = client.post(
        "/api/prioritization",
        json=low_payload,
    )

    assert high_response.status_code == 200
    assert low_response.status_code == 200

    high_score = high_response.json()["priority_value"]
    low_score = low_response.json()["priority_value"]

    assert high_score > low_score


def test_overdue_maintenance_increases_priority():
    """Verify that overdue maintenance contributes to the score."""

    current_payload = {
        "maintenance": make_maintenance(
            maintenance_id="MW-CURRENT",
            requested_date="2026-09-22",
        ),
        "reference_date": "2026-09-22",
    }

    overdue_payload = {
        "maintenance": make_maintenance(
            maintenance_id="MW-OVERDUE",
            requested_date="2026-08-22",
        ),
        "reference_date": "2026-09-22",
    }

    current_response = client.post(
        "/api/prioritization",
        json=current_payload,
    )

    overdue_response = client.post(
        "/api/prioritization",
        json=overdue_payload,
    )

    assert current_response.status_code == 200
    assert overdue_response.status_code == 200

    current_data = current_response.json()
    overdue_data = overdue_response.json()

    assert current_data["factors"]["overdue_factor"] == 0
    assert overdue_data["factors"]["overdue_factor"] > 0

    assert overdue_data["priority_value"] > current_data["priority_value"]


def test_invalid_status_is_rejected():
    """Verify invalid maintenance status cannot enter prioritization."""

    maintenance = make_maintenance()
    maintenance["status"] = "INVALID_STATUS"

    payload = {
        "maintenance": maintenance,
        "reference_date": "2026-09-22",
    }

    response = client.post("/api/prioritization", json=payload)

    assert response.status_code == 422