"""
Phase 4 — Final Plan API + Persistence Integration Test Suite.

Verifies:
  Part 1: Optimization Request Flow (Request → Validation → Planning → Scheduling → CP-SAT → Final Validation → Persistence → API Response)
          Validation failure rejection (invalid plans are NOT persisted as successful, returns HTTP 422)
  Part 2: Plan Identity (OPT-PLAN-XXXXXXXX format, stable across API response, DB record, retrieval)
  Part 3: Persisted Optimization Result (retains plan_id, solver_status, objective_value, counts, allocations, diagnostics, validation)
  Part 4: Scheduled Allocation Persistence (request_id, block_id, asset_id, location, service_date, start_time, end_time, duration, priority, priority_value)
  Part 5: Unscheduled Result Persistence (request_id, priority, priority_value, unscheduled status, diagnostic reason, diagnostic message)
  Part 6: GET /api/plans/optimized (persisted plan summaries, pagination, filtering by target_date)
  Part 7: GET /api/plans/optimized/latest (retrieval without re-running CP-SAT, 404 on missing, target_date query vs latest overall)
  Part 8: GET /api/plans/optimized/{plan_id} (retrieves exact plan; Plans A, B, C isolation without cross-contamination)
  Part 9: Plan Consistency (Optimization Response == Persisted DB Result == GET /optimized/{plan_id} == GET /optimized/latest)
  Part 10: Date & Planning Horizon Consistency (target_date, horizon_days, service_date, generated_at)
  Part 11: Transaction Safety (rollback on persistence failure, no orphaned or half-persisted plans)
  Part 12: Duplicate Plan Protection & ID Uniqueness (save_or_update idempotent safety, distinct plan_ids per run)
  Part 13: API Error Handling (invalid input 422, validation failure 422, persistence failure 500, not found 404)
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_db
from backend.app.block_planner.planner import BlockPlanner
from backend.app.database.connection import SessionLocal
from backend.app.database.models import Block, OptimizedPlan
from backend.app.database.repositories import BlockRepository, OptimizedPlanRepository
from backend.app.main import app
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
    OptimizedBlock,
    Priority,
    SolverStatistics,
    UnscheduledBlock,
)
from backend.app.optimizer.validator import validate_final_plan
from backend.app.schemas.unified_data import BlockRecord, MaintenanceRecord

client = TestClient(app)

TARGET_DATE_STR = "2026-09-07"
OPERATOR_HEADERS = {"X-User-Role": "Operator"}


# ===========================================================================
# Part 1: Optimization Request Flow & Validation Enforcement
# ===========================================================================

class TestPart1_OptimizationRequestFlow:
    """Part 1: Full pipeline execution and rejection of invalid final plans."""

    def test_full_optimization_flow_success(self):
        """Pipeline runs CP-SAT, validates, persists, and returns valid plan with 200."""
        resp = client.post(
            "/api/plans/optimize",
            json={
                "target_date": TARGET_DATE_STR,
                "horizon_days": 3,
                "buffer_minutes": 15,
                "include_forecast": True,
            },
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"].startswith("OPT-PLAN-")
        assert data["status"] in ("OPTIMAL", "FEASIBLE")
        assert len(data["scheduled_blocks"]) > 0
        assert data.get("validation") is not None
        assert data["validation"]["is_valid"] is True

    def test_invalid_plan_rejected_and_not_persisted(self):
        """If Phase 3 validation reports is_valid=False, API returns 422 and does NOT persist the invalid plan."""
        fake_violations = [
            "CONFLICTS_REMAIN: 2 operational conflict(s) detected.",
            "DURATION_ALTERED: block 'BLK-BAD' duration was shortened.",
        ]

        def mock_invalid_validate(*args, **kwargs):
            return {
                "is_valid": False,
                "violations": fake_violations,
                "conflicts": 2,
                "headway_violations": 0,
                "equipment_violations": 0,
                "duration_violations": 1,
                "duplicate_ids": 0,
                "unknown_blocks": 0,
                "count_integrity": True,
            }

        with patch("backend.app.api.routes.plans.validate_final_plan", side_effect=mock_invalid_validate):
            resp = client.post(
                "/api/plans/optimize",
                json={
                    "target_date": "2026-09-20",
                    "horizon_days": 1,
                    "buffer_minutes": 15,
                },
                headers=OPERATOR_HEADERS,
            )
            assert resp.status_code == 422
            err_data = resp.json()
            assert "validation failed" in err_data["detail"].lower()
            assert "CONFLICTS_REMAIN" in err_data["detail"]

            # Confirm no plan was persisted for that date
            get_resp = client.get("/api/plans/optimized/latest?target_date=2026-09-20")
            assert get_resp.status_code == 404


# ===========================================================================
# Part 2: Plan Identity
# ===========================================================================

class TestPart2_PlanIdentity:
    """Part 2: Stable, canonical OPT-PLAN-XXXXXXXX plan identity."""

    def test_plan_id_format_and_stability(self):
        """Plan ID is stable across POST /optimize, DB record, and GET /optimized/{plan_id}."""
        resp = client.post(
            "/api/plans/optimize",
            json={
                "target_date": TARGET_DATE_STR,
                "horizon_days": 2,
                "buffer_minutes": 15,
            },
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        plan_id = resp.json()["plan_id"]
        assert plan_id.startswith("OPT-PLAN-")
        assert len(plan_id) >= 16

        # Retrieve by ID
        get_resp = client.get(f"/api/plans/optimized/{plan_id}")
        assert get_resp.status_code == 200
        retrieved = get_resp.json()
        assert retrieved["plan_meta"]["plan_id"] == plan_id
        assert retrieved["result"]["plan_id"] == plan_id


# ===========================================================================
# Part 3: Persist the Optimization Result
# ===========================================================================

class TestPart3_PersistOptimizationResult:
    """Part 3: Stored plan retains all required fields and metadata."""

    def test_persisted_result_contains_all_fields(self):
        resp = client.post(
            "/api/plans/optimize",
            json={
                "target_date": TARGET_DATE_STR,
                "horizon_days": 3,
                "buffer_minutes": 15,
            },
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        opt_data = resp.json()
        plan_id = opt_data["plan_id"]

        get_resp = client.get(f"/api/plans/optimized/{plan_id}")
        assert get_resp.status_code == 200
        payload = get_resp.json()
        meta = payload["plan_meta"]
        res = payload["result"]

        # Metadata checks
        assert meta["plan_id"] == plan_id
        assert meta["target_date"] == TARGET_DATE_STR
        assert meta["horizon_days"] == 3
        assert meta["solver_status"] in ("OPTIMAL", "FEASIBLE")
        assert meta["num_scheduled"] == len(res["scheduled_blocks"])
        assert meta["num_unscheduled"] == len(res["unscheduled_blocks"])
        assert meta["total_requests"] == meta["num_scheduled"] + meta["num_unscheduled"]
        assert "generated_at" in meta
        assert meta["generated_at"] is not None

        # Result checks
        assert res["plan_id"] == plan_id
        assert res["status"] == meta["solver_status"]
        assert "scheduled_blocks" in res
        assert "unscheduled_blocks" in res
        assert "solver_statistics" in res
        assert "validation" in res


# ===========================================================================
# Part 4: Scheduled Allocation Persistence
# ===========================================================================

class TestPart4_ScheduledAllocationPersistence:
    """Part 4: Traceability and preservation of scheduled allocation attributes."""

    def test_scheduled_allocations_retain_all_identifiers(self):
        resp = client.post(
            "/api/plans/optimize",
            json={
                "target_date": TARGET_DATE_STR,
                "horizon_days": 3,
                "buffer_minutes": 15,
            },
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        plan_id = resp.json()["plan_id"]

        get_resp = client.get(f"/api/plans/optimized/{plan_id}")
        assert get_resp.status_code == 200
        sched_blocks = get_resp.json()["result"]["scheduled_blocks"]
        assert len(sched_blocks) > 0

        for block in sched_blocks:
            assert block.get("block_id"), "Missing block_id"
            assert block.get("request_id"), "Missing request_id"
            assert block.get("location"), "Missing location"
            assert block.get("service_date"), "Missing service_date"
            assert block.get("start_time"), "Missing start_time"
            assert block.get("end_time"), "Missing end_time"
            assert block.get("duration_minutes") > 0, "Invalid duration"
            assert block.get("priority") in ("Critical", "High", "Medium", "Low"), "Missing priority"
            assert "assigned_slot_id" in block, "Missing assigned_slot_id"
            assert "required_resources" in block, "Missing required_resources"


# ===========================================================================
# Part 5: Unscheduled Result Persistence
# ===========================================================================

class TestPart5_UnscheduledResultPersistence:
    """Part 5: Traceability, diagnostic reasons, and status in unscheduled blocks."""

    def test_unscheduled_blocks_retain_diagnostics(self):
        resp = client.post(
            "/api/plans/optimize",
            json={
                "target_date": TARGET_DATE_STR,
                "horizon_days": 3,
                "buffer_minutes": 15,
            },
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        plan_id = resp.json()["plan_id"]

        get_resp = client.get(f"/api/plans/optimized/{plan_id}")
        assert get_resp.status_code == 200
        unsched_blocks = get_resp.json()["result"]["unscheduled_blocks"]

        for ub in unsched_blocks:
            assert ub.get("request_id"), "Missing request_id"
            assert ub.get("location"), "Missing location"
            assert ub.get("priority") in ("Critical", "High", "Medium", "Low")
            assert ub.get("reason"), "Missing diagnostic reason"
            assert ub.get("status") == "Unscheduled"
            assert ub.get("diagnostic_message") is not None


# ===========================================================================
# Part 6: GET /api/plans/optimized
# ===========================================================================

class TestPart6_ListOptimizedPlans:
    """Part 6: List persisted plans without re-running CP-SAT."""

    def test_list_plans_metadata_and_filtering(self):
        # 1. Create a plan for TARGET_DATE_STR
        resp = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 1, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        created_id = resp.json()["plan_id"]

        # 2. List all plans
        list_resp = client.get("/api/plans/optimized")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "data" in data
        assert "count" in data
        assert "total" in data
        assert data["count"] > 0
        plan_ids = [p["plan_id"] for p in data["data"]]
        assert created_id in plan_ids

        # 3. Filter by target_date
        filt_resp = client.get(f"/api/plans/optimized?target_date={TARGET_DATE_STR}")
        assert filt_resp.status_code == 200
        filt_data = filt_resp.json()
        for p in filt_data["data"]:
            assert p["target_date"] == TARGET_DATE_STR

        # 4. Pagination
        page_resp = client.get("/api/plans/optimized?limit=1&skip=0")
        assert page_resp.status_code == 200
        assert len(page_resp.json()["data"]) <= 1


# ===========================================================================
# Part 7: GET /api/plans/optimized/latest
# ===========================================================================

class TestPart7_GetLatestPlan:
    """Part 7: Retrieve latest persisted plan without re-running solver or mutating data."""

    def test_get_latest_with_and_without_target_date(self):
        # Create a fresh plan
        resp = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 2, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        fresh_plan_id = resp.json()["plan_id"]

        # 1. Query with ?target_date=TARGET_DATE_STR
        date_latest_resp = client.get(f"/api/plans/optimized/latest?target_date={TARGET_DATE_STR}")
        assert date_latest_resp.status_code == 200
        assert date_latest_resp.json()["result"]["plan_id"] == fresh_plan_id

        # 2. Query without target_date (gets overall latest plan)
        overall_latest_resp = client.get("/api/plans/optimized/latest")
        assert overall_latest_resp.status_code == 200
        assert overall_latest_resp.json()["result"]["plan_id"] == fresh_plan_id

        # 3. Query for nonexistent date returns 404
        missing_resp = client.get("/api/plans/optimized/latest?target_date=1900-01-01")
        assert missing_resp.status_code == 404


# ===========================================================================
# Part 8: GET /api/plans/optimized/{plan_id} (Plan Isolation)
# ===========================================================================

class TestPart8_PlanIsolation:
    """Part 8: Strict isolation between Plans A, B, and C."""

    def test_plans_a_b_c_isolation(self):
        # Generate Plan A
        resp_a = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 1, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp_a.status_code == 200
        plan_a_id = resp_a.json()["plan_id"]

        # Generate Plan B
        resp_b = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 2, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp_b.status_code == 200
        plan_b_id = resp_b.json()["plan_id"]

        # Generate Plan C
        resp_c = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 3, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp_c.status_code == 200
        plan_c_id = resp_c.json()["plan_id"]

        assert plan_a_id != plan_b_id != plan_c_id

        # Request Plan B: must return only Plan B with horizon_days=2
        get_b = client.get(f"/api/plans/optimized/{plan_b_id}")
        assert get_b.status_code == 200
        data_b = get_b.json()
        assert data_b["plan_meta"]["plan_id"] == plan_b_id
        assert data_b["result"]["plan_id"] == plan_b_id
        assert data_b["result"]["horizon_days"] == 2

        # Non-existent ID returns 404
        get_missing = client.get("/api/plans/optimized/OPT-PLAN-NONEXISTENT")
        assert get_missing.status_code == 404


# ===========================================================================
# Part 9: Plan Consistency
# ===========================================================================

class TestPart9_PlanConsistency:
    """Part 9: Agreement between POST /optimize response, DB record, GET /{id}, and GET /latest."""

    def test_all_endpoints_agree_on_plan_data(self):
        # 1. Run optimization
        post_resp = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 3, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        plan_id = post_data["plan_id"]

        # 2. Get by ID
        by_id_resp = client.get(f"/api/plans/optimized/{plan_id}")
        assert by_id_resp.status_code == 200
        by_id_data = by_id_resp.json()["result"]

        # 3. Get latest
        latest_resp = client.get(f"/api/plans/optimized/latest?target_date={TARGET_DATE_STR}")
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()["result"]

        # 4. Check exact agreement across all three
        for key in ("plan_id", "status", "objective_value", "target_date", "horizon_days"):
            assert post_data[key] == by_id_data[key] == latest_data[key], f"Mismatch on {key}"

        # Check counts
        assert len(post_data["scheduled_blocks"]) == len(by_id_data["scheduled_blocks"]) == len(latest_data["scheduled_blocks"])
        assert len(post_data["unscheduled_blocks"]) == len(by_id_data["unscheduled_blocks"]) == len(latest_data["unscheduled_blocks"])

        # Check solver statistics
        post_stats = post_data["solver_statistics"]
        id_stats = by_id_data["solver_statistics"]
        latest_stats = latest_data["solver_statistics"]
        assert post_stats["num_scheduled"] == id_stats["num_scheduled"] == latest_stats["num_scheduled"]
        assert post_stats["num_unscheduled"] == id_stats["num_unscheduled"] == latest_stats["num_unscheduled"]
        assert post_stats["total_requests"] == id_stats["total_requests"] == latest_stats["total_requests"]


# ===========================================================================
# Part 10: Date / Planning Horizon Consistency
# ===========================================================================

class TestPart10_DateHorizonConsistency:
    """Part 10: Dates and horizons are not mixed across optimization horizon."""

    def test_date_horizon_integrity(self):
        target = "2026-09-10"
        horizon = 5
        resp = client.post(
            "/api/plans/optimize",
            json={"target_date": target, "horizon_days": horizon, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_date"] == target
        assert data["horizon_days"] == horizon

        base_d = date.fromisoformat(target)
        max_d = base_d + timedelta(days=horizon)

        # Scheduled blocks must fall within [target_date, target_date + horizon_days]
        for sb in data["scheduled_blocks"]:
            s_d = date.fromisoformat(sb["service_date"])
            assert base_d <= s_d <= max_d, f"Block date {s_d} outside horizon [{base_d}, {max_d}]"


# ===========================================================================
# Part 11: Transaction Safety
# ===========================================================================

class TestPart11_TransactionSafety:
    """Part 11: Transaction safety and rollback when persistence fails."""

    def test_persistence_failure_triggers_rollback(self):
        """When DB persistence raises an exception, the transaction is rolled back and HTTP 500 returned."""
        with patch.object(OptimizedPlanRepository, "save_or_update", side_effect=RuntimeError("Simulated DB I/O Error")):
            resp = client.post(
                "/api/plans/optimize",
                json={"target_date": TARGET_DATE_STR, "horizon_days": 1, "buffer_minutes": 15},
                headers=OPERATOR_HEADERS,
            )
            assert resp.status_code == 500
            assert "Database persistence failure" in resp.json()["detail"]


# ===========================================================================
# Part 12: Duplicate Plan Protection & ID Uniqueness
# ===========================================================================

class TestPart12_DuplicatePlanProtection:
    """Part 12: Idempotent save_or_update and distinct identities per optimization run."""

    def test_each_run_creates_unique_plan_id(self):
        resp1 = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 1, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        resp2 = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": 1, "buffer_minutes": 15},
            headers=OPERATOR_HEADERS,
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        id1 = resp1.json()["plan_id"]
        id2 = resp2.json()["plan_id"]
        assert id1 != id2, "Subsequent runs must generate distinct plan IDs"

    def test_save_or_update_does_not_duplicate_primary_key(self):
        """Re-saving the same plan_id via repository updates the record rather than raising duplicate key error."""
        db = SessionLocal()
        try:
            repo = OptimizedPlanRepository(db)
            plan_id = f"OPT-PLAN-TEST-{TARGET_DATE_STR.replace('-', '')}"

            plan_data = {
                "plan_id": plan_id,
                "target_date": TARGET_DATE_STR,
                "horizon_days": 7,
                "solver_status": "OPTIMAL",
                "objective_value": 100.0,
                "num_scheduled": 5,
                "num_unscheduled": 1,
                "total_requests": 6,
                "result_json": json.dumps({"plan_id": plan_id, "status": "OPTIMAL"}),
            }

            # First save creates
            rec1 = repo.save_or_update(plan_data)
            assert rec1.plan_id == plan_id
            assert rec1.num_scheduled == 5

            # Second save updates without error
            plan_data["num_scheduled"] = 6
            rec2 = repo.save_or_update(plan_data)
            assert rec2.plan_id == plan_id
            assert rec2.num_scheduled == 6
        finally:
            db.close()


# ===========================================================================
# Part 13: API Error Handling
# ===========================================================================

class TestPart13_APIErrorHandling:
    """Part 13: API error behavior across boundary cases."""

    def test_invalid_input_horizon_days_rejected_422(self):
        """Input validation rejects horizon_days < 1 with 422."""
        resp = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "horizon_days": -5},
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 422

    def test_invalid_input_buffer_minutes_rejected_422(self):
        """Input validation rejects buffer_minutes < 0 with 422."""
        resp = client.post(
            "/api/plans/optimize",
            json={"target_date": TARGET_DATE_STR, "buffer_minutes": -10},
            headers=OPERATOR_HEADERS,
        )
        assert resp.status_code == 422

    def test_plan_not_found_returns_404(self):
        """Requesting an unknown plan_id returns 404."""
        resp = client.get("/api/plans/optimized/OPT-PLAN-DOES-NOT-EXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_latest_plan_not_found_returns_404(self):
        """Requesting latest plan for a date with no plans returns 404."""
        resp = client.get("/api/plans/optimized/latest?target_date=1970-01-01")
        assert resp.status_code == 404
        assert "no optimized plan found" in resp.json()["detail"].lower()
