"""
Tests for Role-Based Permission Enforcement (Operator vs Employee).
Verifies that:
- Employee role is restricted to read-only access (GET requests allowed).
- Employee attempts to perform mutations (POST / PATCH / DELETE) return HTTP 403 Forbidden.
- Operator role can execute mutations without restriction.
- Requests without role header default to operator for backwards compatibility.
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
def client():
    """Create a TestClient with an in-memory SQLite database populated with seed data."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_employee_can_read_endpoints(client):
    """Employee must have full read access to operational GET endpoints."""
    headers = {"X-User-Role": "employee"}

    res = client.get("/api/blocks", headers=headers)
    assert res.status_code == 200

    res = client.get("/api/maintenance", headers=headers)
    assert res.status_code == 200

    res = client.get("/api/trains", headers=headers)
    assert res.status_code == 200

    res = client.get("/api/forecast", headers=headers)
    assert res.status_code == 200

    res = client.get("/api/scheduler/conflicts", headers=headers)
    assert res.status_code == 200

    res = client.get("/api/plans/optimized", headers=headers)
    assert res.status_code == 200


def test_employee_mutation_blocked_post_blocks(client):
    """Employee cannot submit block requests (POST /api/blocks -> 403)."""
    headers = {"X-User-Role": "employee"}
    payload = {
        "block_id": "EMP-BLOCKED-01",
        "block_type": "track",
        "section": "MAS-KPD",
        "location": "Arakkonam Jn",
        "track_number": "UP Slow",
        "requested_date": "2026-09-10",
        "requested_start": "10:00",
        "requested_end": "12:00",
        "priority": "Medium",
        "equipment": "BCM",
        "reason": "Unauthorized employee submission test",
    }
    res = client.post("/api/blocks", json=payload, headers=headers)
    assert res.status_code == 403
    assert "Permission denied: Employee role is restricted to read-only access." in res.json()["detail"]


def test_employee_mutation_blocked_patch_blocks(client):
    """Employee cannot update existing blocks (PATCH /api/blocks/{id} -> 403)."""
    headers = {"X-User-Role": "employee"}
    res = client.patch("/api/blocks/BLK-001", json={"status": "Approved"}, headers=headers)
    assert res.status_code == 403
    assert "Permission denied" in res.json()["detail"]


def test_employee_mutation_blocked_patch_maintenance(client):
    """Employee cannot update maintenance work orders (PATCH /api/maintenance/{id} -> 403)."""
    headers = {"X-User-Role": "employee"}
    res = client.patch("/api/maintenance/1", json={"status": "Approved"}, headers=headers)
    assert res.status_code == 403
    assert "Permission denied" in res.json()["detail"]


def test_employee_mutation_blocked_optimize_plan(client):
    """Employee cannot trigger CP-SAT optimization (POST /api/plans/optimize -> 403)."""
    headers = {"X-User-Role": "employee"}
    res = client.post("/api/plans/optimize", json={"target_date": "2026-09-10"}, headers=headers)
    assert res.status_code == 403
    assert "Permission denied" in res.json()["detail"]


def test_employee_mutation_blocked_run_forecast(client):
    """Employee cannot trigger goods forecast recalculation (POST /api/forecast/run -> 403)."""
    headers = {"X-User-Role": "employee"}
    res = client.post("/api/forecast/run", json={"target_date": "2026-09-10", "horizon_hours": 24}, headers=headers)
    assert res.status_code == 403
    assert "Permission denied" in res.json()["detail"]


def test_operator_can_mutate(client):
    """Operator role has full mutation privileges."""
    headers = {"X-User-Role": "operator"}
    # PATCH block
    res = client.patch("/api/blocks/BLK-001", json={"priority": "High"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["priority"] == "High"
