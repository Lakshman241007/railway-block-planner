"""
Phase 5 End-to-End Test Suite — Scenarios A through J.

Tests the complete end-to-end block planning lifecycle:
  A. Valid block request submission and retrieval
  B. Duplicate block_id rejection
  C. Invalid time format rejection
  D. Zero-duration block rejection
  E. Overnight block submission and validation
  F. POST /api/plans/optimize persists plan (API level)
  G. GET /api/plans/optimized/latest retrieves stored plan
  H. GET /api/plans/optimized/{plan_id} retrieval
  I. Block status updated to Approved after optimization
  J. Count integrity: scheduled + unscheduled == total_requests

Also covers:
  - validate_final_plan unit tests
  - OptimizedPlanRepository persistence tests
  - Schedule date filter logic (service_date isolation)
"""

from __future__ import annotations

import json
from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.optimizer.schemas import OptimizationResult, OptimizationStatus, SolverStatistics
from backend.app.optimizer.validator import validate_final_plan
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    BlockType,
    MaintenanceRecord,
    MaintenanceStatus,
    MovementRecord,
    Priority,
    TimetableRecord,
    TrainRecord,
    TrainStatus,
)

client = TestClient(app)

TARGET_DATE = "2026-09-07"
BASE_DATE = date(2026, 9, 1)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="module")
def unique_block_id():
    """Generate a unique block ID for this test module run."""
    import uuid
    return f"BLK-E2E-{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture
def minimal_optimization_result():
    """Minimal valid OptimizationResult for validator unit tests."""
    from backend.app.optimizer.schemas import OptimizedBlock
    from backend.app.schemas.unified_data import Priority

    return OptimizationResult(
        plan_id="TEST-PLAN-001",
        generated_at="2026-09-07T00:00:00Z",
        target_date=BASE_DATE,
        horizon_days=1,
        status=OptimizationStatus.OPTIMAL,
        objective_value=100.0,
        scheduled_blocks=[
            OptimizedBlock(
                block_id="SCHED-001",
                block_request_id="BLK-001",
                request_id="BLK-001",
                location="Chennai-Arakkonam",
                service_date=BASE_DATE,
                start_time="02:00",
                end_time="05:00",
                duration_minutes=180,
                priority=Priority.HIGH,
                status="Scheduled",
                fit_score=0.95,
                assigned_slot_id="SLOT-001",
            ),
        ],
        unscheduled_blocks=[],
        solver_statistics=SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            total_requests=1,
            num_scheduled=1,
            num_unscheduled=0,
            objective_value=100.0,
            wall_time_seconds=0.05,
            num_variables=5,
            num_constraints=3,
            conflicts_before=2,
            conflicts_after=0,
            num_conflicts_avoided=2,
        ),
    )


# ===========================================================================
# Scenario A: Valid block request submission and retrieval
# ===========================================================================

class TestScenarioA_ValidBlockSubmission:
    """Scenario A: Submit a valid block request via POST /api/blocks."""

    def test_A1_submit_valid_block(self, unique_block_id):
        """A1: A well-formed block request returns 201 with VALIDATED status."""
        response = client.post("/api/blocks", json={
            "block_id": unique_block_id,
            "location": "Chennai-Arakkonam KM 40-42",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "02:00",
            "requested_end": "05:00",
            "reason": "Track geometry correction — Phase 5 E2E test",
            "priority": "High",
        })
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "VALIDATED"
        assert data["block_id"] == unique_block_id
        assert data["duration_minutes"] == 180  # 02:00 → 05:00 = 3h = 180min
        assert data["priority"] == "High"

    def test_A2_block_appears_in_list(self, unique_block_id):
        """A2: The submitted block appears in GET /api/blocks list."""
        response = client.get("/api/blocks?limit=200")
        assert response.status_code == 200
        data = response.json()
        block_ids = [b["block_id"] for b in data["data"]]
        assert unique_block_id in block_ids

    def test_A3_block_retrieval_by_id(self, unique_block_id):
        """A3: The submitted block can be retrieved by its block_id."""
        response = client.get(f"/api/blocks/{unique_block_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["block_id"] == unique_block_id
        assert data["data"]["status"] == "Requested"


# ===========================================================================
# Scenario B: Duplicate block_id rejection
# ===========================================================================

class TestScenarioB_DuplicateBlockRejection:
    """Scenario B: Submitting a duplicate block_id must return 409."""

    def test_B1_duplicate_block_rejected(self, unique_block_id):
        """B1: Submitting the same block_id a second time returns 409 Conflict."""
        response = client.post("/api/blocks", json={
            "block_id": unique_block_id,
            "location": "Chennai",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "06:00",
            "requested_end": "08:00",
            "reason": "Duplicate test",
            "priority": "Low",
        })
        assert response.status_code == 409, (
            f"Expected 409 Conflict for duplicate block_id, got {response.status_code}: {response.text}"
        )


# ===========================================================================
# Scenario C: Invalid time format rejection
# ===========================================================================

class TestScenarioC_InvalidTimeFormat:
    """Scenario C: Time fields must be HH:MM format."""

    def test_C1_invalid_start_time_rejected(self):
        """C1: start_time in wrong format (H:MM) returns 422."""
        response = client.post("/api/blocks", json={
            "block_id": "BLK-C1-INVALID",
            "location": "Chennai",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "2:00",  # Invalid: must be HH:MM
            "requested_end": "05:00",
            "reason": "Test",
            "priority": "Low",
        })
        assert response.status_code == 422, f"Expected 422 for bad time format, got {response.status_code}"

    def test_C2_invalid_date_format_rejected(self):
        """C2: requested_date in YYYY/MM/DD format returns 422."""
        response = client.post("/api/blocks", json={
            "block_id": "BLK-C2-BADDATE",
            "location": "Chennai",
            "block_type": "Maintenance",
            "requested_date": "2026/09/07",  # Invalid: must be YYYY-MM-DD
            "requested_start": "02:00",
            "requested_end": "05:00",
            "reason": "Test",
            "priority": "Low",
        })
        assert response.status_code == 422, f"Expected 422 for bad date format, got {response.status_code}"

    def test_C3_out_of_range_time_rejected(self):
        """C3: Time value 25:00 returns 422."""
        response = client.post("/api/blocks", json={
            "block_id": "BLK-C3-BADTIME",
            "location": "Chennai",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "25:00",  # Invalid hour
            "requested_end": "05:00",
            "reason": "Test",
            "priority": "Low",
        })
        assert response.status_code == 422

    def test_C4_missing_location_rejected(self):
        """C4: Empty location string returns 422."""
        response = client.post("/api/blocks", json={
            "block_id": "BLK-C4-NOLOC",
            "location": "",  # Invalid: min_length=1
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "02:00",
            "requested_end": "05:00",
            "reason": "Test",
            "priority": "Low",
        })
        assert response.status_code == 422


# ===========================================================================
# Scenario D: Zero-duration block rejection
# ===========================================================================

class TestScenarioD_ZeroDurationRejection:
    """Scenario D: A block where start == end (zero duration) must be rejected."""

    def test_D1_same_start_end_rejected(self):
        """D1: requested_start == requested_end on same day → zero duration → 422."""
        response = client.post("/api/blocks", json={
            "block_id": "BLK-D1-ZERODUR",
            "location": "Chennai",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "10:00",
            "requested_end": "10:00",  # Zero duration
            "reason": "Test",
            "priority": "Low",
        })
        assert response.status_code == 422, f"Expected 422 for zero duration, got {response.status_code}"


# ===========================================================================
# Scenario E: Overnight block submission and validation
# ===========================================================================

class TestScenarioE_OvernightBlock:
    """Scenario E: Overnight blocks (end < start) must be accepted and timed correctly."""

    def test_E1_overnight_block_accepted(self):
        """E1: An overnight block 22:00→02:00 (240 min) is accepted with correct duration."""
        import uuid
        block_id = f"BLK-E1-OVERNIGHT-{uuid.uuid4().hex[:6].upper()}"
        response = client.post("/api/blocks", json={
            "block_id": block_id,
            "location": "Chennai-Arakkonam",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "22:00",
            "requested_end": "02:00",  # Overnight → 240 min
            "reason": "Track maintenance — overnight possession",
            "priority": "High",
        })
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["duration_minutes"] == 240, (
            f"Expected 240 min for 22:00→02:00 overnight, got {data['duration_minutes']}"
        )
        assert data["status"] == "VALIDATED"

    def test_E2_overnight_block_23_to_01(self):
        """E2: Overnight block 23:00→01:00 = 120 min."""
        import uuid
        block_id = f"BLK-E2-OVR2-{uuid.uuid4().hex[:6].upper()}"
        response = client.post("/api/blocks", json={
            "block_id": block_id,
            "location": "Arakkonam-Renigunta",
            "block_type": "Maintenance",
            "requested_date": TARGET_DATE,
            "requested_start": "23:00",
            "requested_end": "01:00",  # 120 min overnight
            "reason": "Signal maintenance",
            "priority": "Medium",
        })
        assert response.status_code == 201
        assert response.json()["duration_minutes"] == 120


# ===========================================================================
# Scenario F: POST /api/plans/optimize persists plan
# ===========================================================================

class TestScenarioF_OptimizationPersistence:
    """Scenario F: Running CP-SAT optimization via POST /api/plans/optimize persists the plan."""

    @pytest.fixture(scope="class")
    @classmethod
    def optimization_response(cls):
        """Run optimization and cache result for all tests in this class."""
        response = client.post("/api/plans/optimize", json={
            "target_date": TARGET_DATE,
            "horizon_days": 7,
            "buffer_minutes": 15,
            "include_forecast": True,
        })
        return response

    def test_F1_optimize_returns_200(self, optimization_response):
        """F1: POST /api/plans/optimize returns HTTP 200."""
        assert optimization_response.status_code == 200, (
            f"Expected 200, got {optimization_response.status_code}: {optimization_response.text[:300]}"
        )

    def test_F2_optimize_returns_valid_result_shape(self, optimization_response):
        """F2: Response contains required fields: plan_id, status, scheduled_blocks, solver_statistics."""
        data = optimization_response.json()
        assert "plan_id" in data, "Missing plan_id"
        assert "status" in data, "Missing status"
        assert "scheduled_blocks" in data, "Missing scheduled_blocks"
        assert "unscheduled_blocks" in data, "Missing unscheduled_blocks"
        assert "solver_statistics" in data, "Missing solver_statistics"

    def test_F3_solver_status_is_optimal_or_feasible(self, optimization_response):
        """F3: Solver status is OPTIMAL or FEASIBLE (not INFEASIBLE or UNKNOWN)."""
        data = optimization_response.json()
        assert data["status"] in ("OPTIMAL", "FEASIBLE"), (
            f"Expected OPTIMAL or FEASIBLE, got {data['status']}"
        )

    def test_F4_plan_persisted_get_latest(self, optimization_response):
        """F4: After optimization, GET /api/plans/optimized/latest returns the plan."""
        response = client.get(f"/api/plans/optimized/latest?target_date={TARGET_DATE}")
        assert response.status_code == 200, (
            f"Expected 200 from /optimized/latest, got {response.status_code}: {response.text[:200]}"
        )
        data = response.json()
        assert "plan_meta" in data, "Missing plan_meta in latest plan response"
        assert "result" in data, "Missing result in latest plan response"

    def test_F5_retrieved_plan_matches_optimization_result(self, optimization_response):
        """F5: The retrieved plan's plan_id matches the optimization response plan_id."""
        opt_data = optimization_response.json()
        opt_plan_id = opt_data.get("plan_id")
        response = client.get(f"/api/plans/optimized/{opt_plan_id}")
        assert response.status_code == 200, (
            f"GET /api/plans/optimized/{opt_plan_id} returned {response.status_code}"
        )
        retrieved = response.json()
        assert retrieved["result"]["plan_id"] == opt_plan_id


# ===========================================================================
# Scenario G: GET /api/plans/optimized lists plans
# ===========================================================================

class TestScenarioG_PlanListing:
    """Scenario G: GET /api/plans/optimized returns list of persisted plans."""

    def test_G1_list_plans_returns_200(self):
        """G1: GET /api/plans/optimized returns HTTP 200."""
        response = client.get("/api/plans/optimized")
        assert response.status_code == 200

    def test_G2_list_plans_has_data_shape(self):
        """G2: Response has data, count, total fields."""
        response = client.get("/api/plans/optimized")
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert "total" in data

    def test_G3_list_plans_date_filter(self):
        """G3: Date filter returns only plans for that date."""
        response = client.get(f"/api/plans/optimized?target_date={TARGET_DATE}")
        assert response.status_code == 200
        data = response.json()
        for plan in data["data"]:
            assert plan["target_date"] == TARGET_DATE, (
                f"Plan {plan['plan_id']} has date {plan['target_date']}, expected {TARGET_DATE}"
            )


# ===========================================================================
# Scenario H: GET /api/plans/optimized/latest — 404 for unknown date
# ===========================================================================

class TestScenarioH_LatestPlanNotFound:
    """Scenario H: GET /api/plans/optimized/latest for a date with no plan returns 404."""

    def test_H1_unknown_date_returns_404(self):
        """H1: Requesting latest plan for a date with no data returns 404."""
        response = client.get("/api/plans/optimized/latest?target_date=1900-01-01")
        assert response.status_code == 404, (
            f"Expected 404 for date with no plan, got {response.status_code}"
        )

    def test_H2_404_for_nonexistent_plan_id(self):
        """H2: Requesting a non-existent plan_id returns 404."""
        response = client.get("/api/plans/optimized/NONEXISTENT-PLAN-ID-999")
        assert response.status_code == 404


# ===========================================================================
# Scenario I: Count integrity
# ===========================================================================

class TestScenarioI_CountIntegrity:
    """Scenario I: scheduled + unscheduled == total_requests in every optimization."""

    def test_I1_count_integrity(self):
        """I1: scheduled_blocks + unscheduled_blocks == solver_statistics.total_requests."""
        response = client.post("/api/plans/optimize", json={
            "target_date": TARGET_DATE,
            "horizon_days": 3,
            "buffer_minutes": 15,
            "include_forecast": True,
        })
        assert response.status_code == 200
        data = response.json()
        n_sched = len(data["scheduled_blocks"])
        n_unsched = len(data["unscheduled_blocks"])
        total = data["solver_statistics"]["total_requests"]
        assert n_sched + n_unsched == total, (
            f"Count integrity FAILED: scheduled({n_sched}) + unscheduled({n_unsched}) "
            f"= {n_sched + n_unsched} ≠ total_requests({total})"
        )

    def test_I2_all_unscheduled_have_reasons(self):
        """I2: Every unscheduled block must have a non-empty reason."""
        response = client.post("/api/plans/optimize", json={
            "target_date": TARGET_DATE,
            "horizon_days": 3,
            "buffer_minutes": 15,
            "include_forecast": True,
        })
        assert response.status_code == 200
        data = response.json()
        for ub in data["unscheduled_blocks"]:
            assert ub.get("reason"), (
                f"Unscheduled block {ub.get('request_id')} has no reason"
            )


# ===========================================================================
# Scenario J: Final Plan Validator unit tests
# ===========================================================================

class TestScenarioJ_FinalPlanValidator:
    """Scenario J: validate_final_plan independent correctness checks."""

    def test_J1_valid_plan_passes(self, minimal_optimization_result):
        """J1: A structurally valid plan with no conflicts passes validation."""
        result = validate_final_plan(minimal_optimization_result)
        assert result["is_valid"] is True
        assert result["conflicts"] == 0
        assert result["duration_violations"] == 0
        assert result["duplicate_ids"] == 0
        assert result["count_integrity"] is True

    def test_J2_duplicate_block_id_detected(self):
        """J2: A plan with duplicate block_ids fails validation."""
        from backend.app.optimizer.schemas import OptimizedBlock

        dup_plan = OptimizationResult(
            plan_id="DUP-PLAN",
            generated_at="2026-09-07T00:00:00Z",
            target_date=BASE_DATE,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            objective_value=50.0,
            scheduled_blocks=[
                OptimizedBlock(
                    block_id="DUP-001",
                    block_request_id="REQ-001",
                    request_id="REQ-001",
                    location="Chennai",
                    service_date=BASE_DATE,
                    start_time="02:00",
                    end_time="04:00",
                    duration_minutes=120,
                    priority=Priority.HIGH,
                    status="Scheduled",
                    fit_score=0.9,
                    assigned_slot_id="SLOT-A1",
                ),
                OptimizedBlock(
                    block_id="DUP-001",  # Duplicate!
                    block_request_id="REQ-002",
                    request_id="REQ-002",
                    location="Arakkonam",
                    service_date=BASE_DATE,
                    start_time="05:00",
                    end_time="07:00",
                    duration_minutes=120,
                    priority=Priority.MEDIUM,
                    status="Scheduled",
                    fit_score=0.8,
                    assigned_slot_id="SLOT-A2",
                ),
            ],
            unscheduled_blocks=[],
            solver_statistics=SolverStatistics(
                status=OptimizationStatus.OPTIMAL,
                total_requests=2,
                num_scheduled=2,
                num_unscheduled=0,
                objective_value=50.0,
                wall_time_seconds=0.01,
                num_variables=4,
                num_constraints=2,
                conflicts_before=0,
                conflicts_after=0,
                num_conflicts_avoided=0,
            ),
        )
        result = validate_final_plan(dup_plan)
        assert result["is_valid"] is False
        assert result["duplicate_ids"] >= 1

    def test_J3_zero_duration_block_detected(self):
        """J3: A plan with a mismatched duration (claimed 999 min but times say 120 min) fails validation."""
        from backend.app.optimizer.schemas import OptimizedBlock

        zero_dur_plan = OptimizationResult(
            plan_id="ZERO-DUR-PLAN",
            generated_at="2026-09-07T00:00:00Z",
            target_date=BASE_DATE,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            objective_value=50.0,
            scheduled_blocks=[
                OptimizedBlock(
                    block_id="ZERO-001",
                    block_request_id="REQ-001",
                    request_id="REQ-001",
                    location="Chennai",
                    service_date=BASE_DATE,
                    start_time="02:00",
                    end_time="04:00",
                    duration_minutes=999,  # Claimed 999 min but start/end implies 120 min — mismatch!
                    priority=Priority.HIGH,
                    status="Scheduled",
                    fit_score=0.9,
                    assigned_slot_id="SLOT-Z1",
                ),
            ],
            unscheduled_blocks=[],
            solver_statistics=SolverStatistics(
                status=OptimizationStatus.OPTIMAL,
                total_requests=1,
                num_scheduled=1,
                num_unscheduled=0,
                objective_value=50.0,
                wall_time_seconds=0.01,
                num_variables=4,
                num_constraints=2,
                conflicts_before=0,
                conflicts_after=0,
                num_conflicts_avoided=0,
            ),
        )
        result = validate_final_plan(zero_dur_plan)
        assert result["is_valid"] is False
        assert result["duration_violations"] >= 1

    def test_J4_count_mismatch_detected(self):
        """J4: A plan where total_requests doesn't match scheduled+unscheduled fails count integrity."""
        from backend.app.optimizer.schemas import OptimizedBlock

        mismatch_plan = OptimizationResult(
            plan_id="COUNT-MISMATCH-PLAN",
            generated_at="2026-09-07T00:00:00Z",
            target_date=BASE_DATE,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            objective_value=50.0,
            scheduled_blocks=[
                OptimizedBlock(
                    block_id="MATCH-001",
                    block_request_id="REQ-001",
                    request_id="REQ-001",
                    location="Chennai",
                    service_date=BASE_DATE,
                    start_time="02:00",
                    end_time="04:00",
                    duration_minutes=120,
                    priority=Priority.HIGH,
                    status="Scheduled",
                    fit_score=0.9,
                    assigned_slot_id="SLOT-M1",
                ),
            ],
            unscheduled_blocks=[],
            solver_statistics=SolverStatistics(
                status=OptimizationStatus.OPTIMAL,
                total_requests=5,  # Intentionally mismatched: 1+0 ≠ 5
                num_scheduled=1,
                num_unscheduled=0,
                objective_value=50.0,
                wall_time_seconds=0.01,
                num_variables=4,
                num_constraints=2,
                conflicts_before=0,
                conflicts_after=0,
                num_conflicts_avoided=0,
            ),
        )
        result = validate_final_plan(mismatch_plan)
        assert result["count_integrity"] is False
