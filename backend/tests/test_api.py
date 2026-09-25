"""
API endpoint integration tests for Railway Block Planner FastAPI routes.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_db
from backend.app.database.connection import Base
from backend.app.database.seed import seed_database
from backend.app.main import app


@pytest.fixture(scope="module")
def test_client():
    """Create a TestClient with an in-memory SQLite database populated with seed data."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Seed test database with Phase 2 data
    seed_session = TestingSessionLocal()
    project_root = Path(__file__).resolve().parents[2]
    seed_database(data_dir=project_root / "data", session=seed_session)
    seed_session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_health_endpoint(test_client):
    """Test /health returns ok status and database connectivity."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "version" in data


def test_root_endpoint(test_client):
    """Test / root endpoint returns metadata or serves frontend SPA."""
    response = test_client.get("/")
    assert response.status_code == 200
    if "text/html" in response.headers.get("content-type", ""):
        assert "<!DOCTYPE html>" in response.text
    else:
        data = response.json()
        assert data["name"] == "Railway Block Planner API"
        assert data["docs"] == "/docs"


def test_get_trains_endpoint(test_client):
    """Test /api/trains lists all seeded trains."""
    response = test_client.get("/api/trains")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["count"] > 0
    assert payload["total"] > 0


def test_get_trains_filtered(test_client):
    """Test /api/trains?status=Running filters correctly."""
    response = test_client.get("/api/trains?status=Running")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    for train in payload["data"]:
        assert train["status"].lower() == "running"


def test_get_train_by_id_success(test_client):
    """Test /api/trains/{train_id} returns the specific train."""
    # First get list to find a valid train_id
    list_resp = test_client.get("/api/trains")
    first_train_id = list_resp.json()["data"][0]["train_id"]

    response = test_client.get(f"/api/trains/{first_train_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["train_id"] == first_train_id


def test_get_train_by_id_404(test_client):
    """Test /api/trains/{train_id} returns 404 for unknown train."""
    response = test_client.get("/api/trains/UNKNOWN_9999")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_get_maintenance_endpoint(test_client):
    """Test /api/maintenance lists maintenance records."""
    response = test_client.get("/api/maintenance")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["count"] > 0


def test_get_maintenance_filters(test_client):
    """Test /api/maintenance with priority filter."""
    response = test_client.get("/api/maintenance?priority=High")
    assert response.status_code == 200
    payload = response.json()
    for item in payload["data"]:
        assert item["priority"].lower() == "high"


def test_get_maintenance_by_asset(test_client):
    """Test /api/maintenance/{asset_id} success and 404."""
    list_resp = test_client.get("/api/maintenance")
    first_asset_id = list_resp.json()["data"][0]["asset_id"]

    response = test_client.get(f"/api/maintenance/{first_asset_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    assert data[0]["asset_id"] == first_asset_id

    # 404 for unknown asset
    response_404 = test_client.get("/api/maintenance/NONEXISTENT_ASSET")
    assert response_404.status_code == 404


def test_get_blocks_endpoint(test_client):
    """Test /api/blocks lists block requests."""
    response = test_client.get("/api/blocks")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["count"] > 0


def test_get_block_by_id_success_and_404(test_client):
    """Test /api/blocks/{block_id} success and 404."""
    list_resp = test_client.get("/api/blocks")
    first_block_id = list_resp.json()["data"][0]["block_id"]

    response = test_client.get(f"/api/blocks/{first_block_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["block_id"] == first_block_id

    # 404
    response_404 = test_client.get("/api/blocks/NONEXISTENT_BLOCK")
    assert response_404.status_code == 404


def test_get_plans_endpoint(test_client):
    """Test /api/plans returns Phase 5 block planning view (data + note)."""
    response = test_client.get("/api/plans")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    # Phase 5: 'message' replaced with 'note' pointing to /api/plans/optimized
    assert "note" in payload
    assert payload["count"] > 0



# ===========================================================================
# Phase 4 API Tests
# ===========================================================================

def test_get_forecast_endpoint(test_client):
    """Test GET /api/forecast returns forecasted goods movements."""
    response = test_client.get("/api/forecast")
    assert response.status_code == 200
    payload = response.json()
    assert "forecasts" in payload
    assert "total_trains_forecasted" in payload
    assert payload["total_trains_forecasted"] >= 1
    assert payload["average_confidence"] > 0.0


def test_run_forecast_endpoint(test_client):
    """Test POST /api/forecast/run with filters."""
    response = test_client.post(
        "/api/forecast/run",
        json={"target_date": "2026-09-05", "horizon_hours": 12, "train_id": "G123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "forecasts" in payload
    assert all(fc["train_id"] == "G123" for fc in payload["forecasts"])


def test_scheduler_feasible_slots_endpoint(test_client):
    """Test POST /api/scheduler/feasible-slots finds valid slots."""
    response = test_client.post(
        "/api/scheduler/feasible-slots",
        json={
            "location": "Chennai-Arakkonam",
            "duration_minutes": 60,
            "preferred_start": "14:00",
            "target_date": "2026-09-05",
            "buffer_minutes": 15,
        },
    )
    assert response.status_code == 200
    slots = response.json()
    assert isinstance(slots, list)
    assert len(slots) > 0
    assert slots[0]["duration_minutes"] == 60


def test_scheduler_conflicts_endpoint(test_client):
    """Test POST /api/scheduler/conflicts returns conflict report."""
    response = test_client.post(
        "/api/scheduler/conflicts?target_date=2026-09-05&buffer_minutes=15"
    )
    assert response.status_code == 200
    report = response.json()
    assert "total_conflicts" in report
    assert "conflicts" in report
    assert "is_conflict_free" in report


def test_scheduler_schedule_endpoint(test_client):
    """Test POST /api/scheduler/schedule generates schedule result."""
    response = test_client.post(
        "/api/scheduler/schedule",
        json={"target_date": "2026-09-05", "buffer_minutes": 15},
    )
    assert response.status_code == 200
    result = response.json()
    assert "total_requested" in result
    assert "scheduled_items" in result


def test_plans_generate_endpoint(test_client):
    """Test POST /api/plans/generate runs full Phase 4 BlockPlanner."""
    response = test_client.post(
        "/api/plans/generate",
        json={"target_date": "2026-09-05", "include_forecast": True, "include_conflicts": True},
    )
    assert response.status_code == 200
    plan = response.json()
    assert "plan_id" in plan
    assert "schedule" in plan
    assert "conflict_report" in plan
    assert "resolution_recommendations" in plan


def test_get_timetable_endpoint(test_client):
    """Test GET /api/timetable returns paginated timetable stops."""
    response = test_client.get("/api/timetable")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert "count" in payload
    assert "total" in payload
    assert payload["total"] > 0


def test_get_timetable_filtered_by_date(test_client):
    """Test GET /api/timetable?service_date=2026-09-07 returns stops for default date."""
    response = test_client.get("/api/timetable?service_date=2026-09-07")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 39
    assert all(item["service_date"] == "2026-09-07" for item in payload["data"])


def test_get_timetable_by_train(test_client):
    """Test GET /api/timetable/train/{train_id} returns scheduled stops."""
    response = test_client.get("/api/timetable/train/G123")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["count"] > 0
    assert all(item["train_id"] == "G123" for item in payload["data"])


def test_get_movements_endpoint(test_client):
    """Test GET /api/movements returns corridor movement records."""
    response = test_client.get("/api/movements")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert "count" in payload
    assert "total" in payload
    assert payload["total"] > 0


def test_get_movements_by_train(test_client):
    """Test GET /api/movements/train/{train_id} returns movements for train."""
    response = test_client.get("/api/movements/train/G123")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["count"] > 0
    assert all(item["train_id"] == "G123" for item in payload["data"])


def test_get_movements_by_section(test_client):
    """Test GET /api/movements/section/{section} returns section movements."""
    response = test_client.get("/api/movements/section/Chennai-Perambur")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["count"] > 0


# ===========================================================================
# Feature 1 — PATCH endpoint tests: Manual Schedule Editing
# ===========================================================================

def test_patch_block_updates_fields(test_client):
    """PATCH /api/blocks/{block_id} — partial update persists new values."""
    # Fetch a real block_id from the seeded database.
    list_resp = test_client.get("/api/blocks")
    first_block = list_resp.json()["data"][0]
    block_id = first_block["block_id"]

    # Patch only priority and status; other fields must remain unchanged.
    patch_resp = test_client.patch(
        f"/api/blocks/{block_id}",
        json={"priority": "High", "status": "Approved"},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()["data"]
    assert updated["block_id"] == block_id
    assert updated["priority"] == "High"
    assert updated["status"] == "Approved"
    # Structural fields must not have been touched.
    assert updated["location"] == first_block["location"]
    assert updated["block_type"] == first_block["block_type"]


def test_patch_block_empty_body_returns_current_record(test_client):
    """PATCH /api/blocks/{block_id} with empty body returns the unchanged record."""
    list_resp = test_client.get("/api/blocks")
    first_block = list_resp.json()["data"][0]
    block_id = first_block["block_id"]

    patch_resp = test_client.patch(f"/api/blocks/{block_id}", json={})
    assert patch_resp.status_code == 200
    # The returned record must be identical to what was there before.
    returned = patch_resp.json()["data"]
    assert returned["block_id"] == block_id


def test_patch_block_404(test_client):
    """PATCH /api/blocks/{block_id} returns 404 for an unknown block_id."""
    response = test_client.patch(
        "/api/blocks/NONEXISTENT_BLOCK_XYZ",
        json={"priority": "High"},
    )
    assert response.status_code == 404
    assert "detail" in response.json()


def test_patch_block_invalid_priority_422(test_client):
    """PATCH /api/blocks/{block_id} returns 422 for an unrecognised priority value."""
    list_resp = test_client.get("/api/blocks")
    block_id = list_resp.json()["data"][0]["block_id"]

    response = test_client.patch(
        f"/api/blocks/{block_id}",
        json={"priority": "SuperUrgent"},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_patch_block_invalid_status_422(test_client):
    """PATCH /api/blocks/{block_id} returns 422 for an unrecognised status value."""
    list_resp = test_client.get("/api/blocks")
    block_id = list_resp.json()["data"][0]["block_id"]

    response = test_client.patch(
        f"/api/blocks/{block_id}",
        json={"status": "Pending"},  # Valid for maintenance, not for blocks.
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_patch_maintenance_updates_fields(test_client):
    """PATCH /api/maintenance/{id} — partial update persists new values."""
    # Fetch a real integer id from the seeded database.
    list_resp = test_client.get("/api/maintenance")
    first_record = list_resp.json()["data"][0]
    record_id = first_record["id"]

    patch_resp = test_client.patch(
        f"/api/maintenance/{record_id}",
        json={"status": "Approved", "duration_minutes": 90},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()["data"]
    assert updated["id"] == record_id
    assert updated["status"] == "Approved"
    assert updated["duration_minutes"] == 90
    # Structural fields must not have been touched.
    assert updated["asset_id"] == first_record["asset_id"]


def test_patch_maintenance_empty_body_returns_current_record(test_client):
    """PATCH /api/maintenance/{id} with empty body returns the unchanged record."""
    list_resp = test_client.get("/api/maintenance")
    first_record = list_resp.json()["data"][0]
    record_id = first_record["id"]

    patch_resp = test_client.patch(f"/api/maintenance/{record_id}", json={})
    assert patch_resp.status_code == 200
    returned = patch_resp.json()["data"]
    assert returned["id"] == record_id


def test_patch_maintenance_404(test_client):
    """PATCH /api/maintenance/{id} returns 404 for an unknown integer id."""
    response = test_client.patch(
        "/api/maintenance/999999",
        json={"status": "Approved"},
    )
    assert response.status_code == 404
    assert "detail" in response.json()


def test_patch_maintenance_invalid_duration_422(test_client):
    """PATCH /api/maintenance/{id} returns 422 when duration_minutes <= 0."""
    list_resp = test_client.get("/api/maintenance")
    record_id = list_resp.json()["data"][0]["id"]

    response = test_client.patch(
        f"/api/maintenance/{record_id}",
        json={"duration_minutes": 0},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_patch_maintenance_invalid_status_422(test_client):
    """PATCH /api/maintenance/{id} returns 422 for an unrecognised status."""
    list_resp = test_client.get("/api/maintenance")
    record_id = list_resp.json()["data"][0]["id"]

    response = test_client.patch(
        f"/api/maintenance/{record_id}",
        json={"status": "Rejected"},  # Valid for blocks, not for maintenance.
    )
    assert response.status_code == 422
    assert "detail" in response.json()


# ===========================================================================
# Schedule-Type API Contract Tests
# ===========================================================================

def test_scheduler_schedule_accepts_daily(test_client):
    """POST /api/scheduler/schedule with schedule_type='daily' returns 200."""
    response = test_client.post(
        "/api/scheduler/schedule",
        json={"target_date": "2026-09-05", "buffer_minutes": 15, "schedule_type": "daily"},
    )
    assert response.status_code == 200
    result = response.json()
    assert "total_requested" in result
    assert "scheduled_items" in result


def test_scheduler_schedule_accepts_weekly(test_client):
    """POST /api/scheduler/schedule with schedule_type='weekly' returns 200 with 7-day horizon."""
    response = test_client.post(
        "/api/scheduler/schedule",
        json={"target_date": "2026-09-05", "buffer_minutes": 15, "schedule_type": "weekly"},
    )
    assert response.status_code == 200
    result = response.json()
    assert "total_requested" in result
    assert "scheduled_items" in result


def test_scheduler_schedule_accepts_monthly(test_client):
    """POST /api/scheduler/schedule with schedule_type='monthly' returns 200."""
    response = test_client.post(
        "/api/scheduler/schedule",
        json={"target_date": "2026-09-01", "buffer_minutes": 15, "schedule_type": "monthly"},
    )
    assert response.status_code == 200
    result = response.json()
    assert "total_requested" in result
    assert "scheduled_items" in result


def test_scheduler_schedule_rejects_invalid_schedule_type(test_client):
    """POST /api/scheduler/schedule with invalid schedule_type returns HTTP 422."""
    response = test_client.post(
        "/api/scheduler/schedule",
        json={"target_date": "2026-09-05", "buffer_minutes": 15, "schedule_type": "biweekly"},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_scheduler_schedule_defaults_to_daily_when_type_omitted(test_client):
    """POST /api/scheduler/schedule without schedule_type defaults to daily (backward compat)."""
    response = test_client.post(
        "/api/scheduler/schedule",
        json={"target_date": "2026-09-05", "buffer_minutes": 15},
    )
    assert response.status_code == 200
    result = response.json()
    assert "total_requested" in result
    assert "scheduled_items" in result
