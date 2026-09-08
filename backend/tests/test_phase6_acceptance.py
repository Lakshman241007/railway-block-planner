"""
Phase 6 End-to-End Acceptance Test Suite for Railway Block Planner.

Validates the complete operational lifecycle from data layer through optimization
to persistence and frontend-facing APIs:
  Stage A: Database & Seed Baseline Integrity
  Stage B: REST API Health & All 8 Sections Endpoint Reachability
  Stage C: Operational Data Retrieval & Foreign-Key Integrity
  Stage D: Block Request Submission & Strict Validation
  Stage E: CP-SAT Optimization Execution & Constraint Verification
  Stage F: Pre- vs Post-Optimization Conflict Resolution
  Stage G: Independent Final Plan Validator
  Stage H: Plan Persistence & Exact Retrieval Round-Trip
  Stage I: Timetable Alignment & Multi-Day Isolation
  Stage J: Overnight Block Handling (Midnight Crossover)
  Stage K: Failure Resilience & Truthful Error Statuses
"""

import uuid
from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from backend.app.main import app
from backend.app.database.connection import SessionLocal, init_db
from backend.app.database.models import (
    Block,
    Maintenance,
    Movement,
    OptimizedPlan,
    Timetable,
    Train,
)
from backend.app.database.repositories import (
    BlockRepository,
    MaintenanceRepository,
    MovementRepository,
    OptimizedPlanRepository,
    TimetableRepository,
    TrainRepository,
)
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
)
from backend.app.optimizer.validator import validate_final_plan

client = TestClient(app)

TARGET_DATE_STR = "2026-09-07"
TARGET_DATE = date(2026, 9, 7)


# ===========================================================================
# Stage A: Database & Seed Baseline Integrity
# ===========================================================================

class TestStageA_DatabaseBaseline:
    """Stage A: Verify fresh/seeded database holds expected baseline records."""

    def test_A1_database_tables_exist_and_populated(self):
        init_db()
        db = SessionLocal()
        try:
            train_count = db.query(func.count(Train.train_id)).scalar()
            tt_count = db.query(func.count(Timetable.id)).scalar()
            maint_count = db.query(func.count(Maintenance.id)).scalar()
            block_count = db.query(func.count(Block.block_id)).scalar()
            move_count = db.query(func.count(Movement.id)).scalar()

            assert train_count >= 10, f"Expected >= 10 trains, found {train_count}"
            assert tt_count >= 200, f"Expected >= 200 timetables, found {tt_count}"
            assert maint_count >= 10, f"Expected >= 10 maintenance records, found {maint_count}"
            assert block_count >= 12, f"Expected >= 12 blocks, found {block_count}"
            assert move_count >= 10, f"Expected >= 10 movements, found {move_count}"
        finally:
            db.close()

    def test_A2_no_orphan_records(self):
        """Verify 0 orphan records between movements/timetables and trains."""
        db = SessionLocal()
        try:
            train_ids = {t.train_id for t in db.query(Train).all()}
            m_orphans = [m for m in db.query(Movement).all() if m.train_id not in train_ids]
            tt_orphans = [tt for tt in db.query(Timetable).all() if tt.train_id not in train_ids]

            assert len(m_orphans) == 0, f"Found {len(m_orphans)} orphan movements"
            assert len(tt_orphans) == 0, f"Found {len(tt_orphans)} orphan timetable records"
        finally:
            db.close()


# ===========================================================================
# Stage B: REST API Health & All 8 Sections
# ===========================================================================

class TestStageB_APIHealthAndSections:
    """Stage B: Verify all 8 core application sections respond with valid HTTP 200 and data."""

    def test_B1_health_check(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_B2_trains_endpoint(self):
        resp = client.get("/api/trains?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data and len(data["data"]) > 0

    def test_B3_maintenance_endpoint(self):
        resp = client.get("/api/maintenance?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data and len(data["data"]) > 0

    def test_B4_blocks_endpoint(self):
        resp = client.get("/api/blocks?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data and len(data["data"]) > 0

    def test_B5_timetable_endpoint(self):
        resp = client.get(f"/api/timetable?service_date={TARGET_DATE_STR}&limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data and len(data["data"]) > 0

    def test_B6_movements_endpoint(self):
        resp = client.get("/api/movements?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data and len(data["data"]) > 0

    def test_B7_forecast_endpoint(self):
        resp = client.get(f"/api/forecast?target_date={TARGET_DATE_STR}&horizon_hours=48")
        assert resp.status_code == 200
        data = resp.json()
        assert "forecasts" in data and len(data["forecasts"]) > 0

    def test_B8_conflicts_endpoint(self):
        resp = client.get(f"/api/conflicts?service_date={TARGET_DATE_STR}")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_conflicts" in data


# ===========================================================================
# Stage C & D: Block Request Submission & Validation
# ===========================================================================

class TestStageCD_BlockRequestWorkflow:
    """Stage C & D: Submit, validate, and query block requests."""

    submitted_id = None

    @pytest.fixture
    def test_block_id(self):
        return f"BLK-P6-{uuid.uuid4().hex[:6].upper()}"

    def test_D1_submit_valid_block_request(self, test_block_id):
        TestStageCD_BlockRequestWorkflow.submitted_id = test_block_id
        payload = {
            "block_id": test_block_id,
            "location": "Chennai-Arakkonam KM 45-47",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE_STR,
            "requested_start": "01:30",
            "requested_end": "04:30",
            "reason": "Phase 6 Acceptance Test — Tamping & ballast profiling",
            "priority": "High",
        }
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["block_id"] == test_block_id
        assert data["status"] == "VALIDATED"
        assert data["duration_minutes"] == 180

    def test_D2_submitted_block_persisted_in_db(self):
        block_id = TestStageCD_BlockRequestWorkflow.submitted_id
        assert block_id is not None
        resp = client.get(f"/api/blocks/{block_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["block_id"] == block_id
        assert data["location"] == "Chennai-Arakkonam KM 45-47"

    def test_D3_reject_zero_duration_block(self):
        payload = {
            "block_id": f"BLK-ZERO-{uuid.uuid4().hex[:6].upper()}",
            "location": "Tambaram-Chengalpattu",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE_STR,
            "requested_start": "03:00",
            "requested_end": "03:00",  # 0 duration
            "reason": "Invalid zero-duration block",
            "priority": "Medium",
        }
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code in (400, 422)

    def test_D4_reject_invalid_date_format(self):
        payload = {
            "block_id": f"BLK-BAD-DATE-{uuid.uuid4().hex[:6].upper()}",
            "location": "Tambaram-Chengalpattu",
            "block_type": "Maintenance",
            "requested_date": "not-a-date",
            "requested_start": "02:00",
            "requested_end": "04:00",
            "reason": "Invalid date test",
            "priority": "Medium",
        }
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code in (400, 422)


# ===========================================================================
# Stage E, F, G, H: Optimization, Conflict Avoidance, Validator & Persistence
# ===========================================================================

class TestStageEFGH_OptimizationLifecycle:
    """Stage E, F, G, H: Full CP-SAT optimization, conflict detection, validation, persistence."""

    latest_plan_id = None

    def test_EFGH_full_optimization_lifecycle(self):
        # 1. Run optimization on canonical target date 2026-09-07
        opt_resp = client.post("/api/plans/optimize", json={
            "target_date": TARGET_DATE_STR,
            "horizon_days": 7,
            "buffer_minutes": 15,
            "include_forecast": True,
        })
        assert opt_resp.status_code == 200, f"Optimization failed: {opt_resp.text}"
        plan = opt_resp.json()

        # Check solver status
        assert plan["status"] in ("OPTIMAL", "FEASIBLE")
        TestStageEFGH_OptimizationLifecycle.latest_plan_id = plan["plan_id"]

        # Check blocks
        sched_blocks = plan["scheduled_blocks"]
        unsched_blocks = plan["unscheduled_blocks"]
        stats = plan["solver_statistics"]

        assert len(sched_blocks) > 0, "Expected at least 1 scheduled block"
        assert stats["total_requests"] == len(sched_blocks) + len(unsched_blocks), "Count integrity failed"

        # Check conflict reduction
        assert stats["conflicts_before"] is not None and stats["conflicts_before"] > 0
        assert stats["conflicts_after"] == 0, f"Expected 0 post-opt conflicts, got {stats['conflicts_after']}"
        assert stats["num_conflicts_avoided"] == stats["conflicts_before"] - stats["conflicts_after"]

        # 2. Independent validation on returned plan
        opt_res_obj = OptimizationResult.model_validate(plan)
        val = validate_final_plan(opt_res_obj)
        assert val["is_valid"] is True, f"Independent validator rejected plan: {val}"
        assert val["conflicts"] == 0
        assert val["duplicate_ids"] == 0
        assert val["duration_violations"] == 0
        assert val["count_integrity"] is True

        # 3. Plan retrieval by ID
        get_resp = client.get(f"/api/plans/optimized/{plan['plan_id']}")
        assert get_resp.status_code == 200
        retrieved_data = get_resp.json()
        retrieved_plan = retrieved_data["result"]
        assert retrieved_plan["plan_id"] == plan["plan_id"]
        assert len(retrieved_plan["scheduled_blocks"]) == len(sched_blocks)
        assert len(retrieved_plan["unscheduled_blocks"]) == len(unsched_blocks)

        # 4. Plan retrieval by target date latest
        latest_resp = client.get(f"/api/plans/optimized/latest?target_date={TARGET_DATE_STR}")
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()
        latest_plan = latest_data["result"]
        assert latest_plan["plan_id"] == plan["plan_id"]

        # 5. Re-validate retrieved plan
        retrieved_obj = OptimizationResult.model_validate(retrieved_plan)
        val_retrieved = validate_final_plan(retrieved_obj)
        assert val_retrieved["is_valid"] is True, "Retrieved plan became invalid after round-trip!"


# ===========================================================================
# Stage I & J: Timetable Alignment & Overnight Logic
# ===========================================================================

class TestStageIJ_TimetableAndOvernight:
    """Stage I & J: Timetable filtering and midnight-crossing overnight block safety."""

    def test_I1_timetable_date_filtering(self):
        resp = client.get(f"/api/timetable?service_date={TARGET_DATE_STR}")
        assert resp.status_code == 200
        stops = resp.json()["data"]
        for stop in stops:
            assert stop["service_date"] == TARGET_DATE_STR

    def test_J1_overnight_block_duration_calculation(self):
        from backend.app.scheduler.scheduler import _calculate_duration_minutes
        # 22:00 to 02:00 crossing midnight = 4 hours = 240 minutes
        dur = _calculate_duration_minutes("22:00", "02:00")
        assert dur == 240, f"Expected 240 minutes for 22:00→02:00, got {dur}"

        # 23:30 to 03:30 = 4 hours = 240 minutes
        dur2 = _calculate_duration_minutes("23:30", "03:30")
        assert dur2 == 240, f"Expected 240 minutes for 23:30→03:30, got {dur2}"


# ===========================================================================
# Stage K: Failure Resilience
# ===========================================================================

class TestStageK_FailureResilience:
    """Stage K: API handles errors truthfully without crashing or showing fake data."""

    def test_K1_nonexistent_plan_returns_404(self):
        resp = client.get("/api/plans/optimized/PLAN-DOES-NOT-EXIST-9999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_K2_nonexistent_block_returns_404(self):
        resp = client.get("/api/blocks/BLK-NONEXISTENT-9999")
        assert resp.status_code == 404

    def test_K3_invalid_block_submission_returns_error(self):
        resp = client.post("/api/blocks", json={
            "block_id": "",
            "location": "",
            "requested_date": "invalid",
        })
        assert resp.status_code in (400, 422)
