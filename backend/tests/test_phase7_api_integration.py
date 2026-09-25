"""
Phase 7 API Integration Test Suite.

Verifies end-to-end integration of the planning and optimization pipeline
with the FastAPI application:
    API Request
        ↓
    Unified RailState / Data Layer
        ↓
    Block Planner
        ↓
    Daily Scheduler (DailyScheduler.schedule_daily)
        ↓
    CP-SAT Optimizer
        ↓
    DailyScheduleResult
        ↓
    API Response

Tests:
    Test 1 — API endpoint exists: canonical /api/scheduler/daily accepts requests.
    Test 2 — Request reaches scheduler: DailyScheduler.schedule_daily is called, NOT BlockPlanner.optimize_plan.
    Test 3 — Successful scheduling response: valid DailyScheduleResult returned.
    Test 4 — Priority propagation: priority_value survives the full pipeline to API response.
    Test 5 — Hard constraints: high priority_value cannot override window duration constraint.
    Test 6 — Infeasible optimization: infeasible request returns structured 200 with diagnostics, not 500.
    Test 7 — Validation errors: malformed payloads yield HTTP 422.
    Test 8 — Legacy compatibility: legacy endpoints /api/plans/optimize and /api/scheduler/schedule continue working.
    Bonus tests: /api/plans/monthly, /api/plans/weekly, /api/plans/daily-problem endpoints.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.block_planner.planner import BlockPlanner
from backend.app.main import app
from backend.app.scheduler.scheduler import DailyScheduler

client = TestClient(app)

TARGET_DATE_STR = "2026-09-07"
TARGET_DATE = date(2026, 9, 7)


# ===========================================================================
# Test 1 — API Endpoint Exists
# ===========================================================================

def test_1_canonical_scheduling_endpoint_exists():
    """Test 1: Canonical endpoint POST /api/scheduler/daily is registered and accepts a valid request."""
    payload = {
        "problem_id": "PROB-T1-EXIST",
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "WORK-T1-1",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,
                "priority_value": 75.0,
            }
        ],
        "available_windows": [
            {
                "window_id": "WIN-T1-1",
                "corridor": "Chennai-Arakkonam",
                "service_date": TARGET_DATE_STR,
                "start_time": "02:00",
                "end_time": "04:00",
                "duration_minutes": 120,
            }
        ],
    }
    response = client.post("/api/scheduler/daily", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "plan_id" in data
    assert data["target_date"] == TARGET_DATE_STR


# ===========================================================================
# Test 2 — Request Reaches Scheduler (Not Legacy Facade)
# ===========================================================================

def test_2_request_reaches_scheduler_not_legacy_facade():
    """Test 2: Verify API invokes canonical DailyScheduler.schedule_daily, NOT BlockPlanner.optimize_plan."""
    payload = {
        "problem_id": "PROB-T2-ROUTING",
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "WORK-T2-1",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,
                "priority_value": 50.0,
            }
        ],
        "available_windows": [
            {
                "window_id": "WIN-T2-1",
                "corridor": "Chennai-Arakkonam",
                "service_date": TARGET_DATE_STR,
                "start_time": "01:00",
                "end_time": "03:00",
                "duration_minutes": 120,
            }
        ],
    }

    original_schedule_daily = DailyScheduler.schedule_daily
    calls = []

    def spy_schedule_daily(self, *args, **kwargs):
        calls.append((args, kwargs))
        return original_schedule_daily(self, *args, **kwargs)

    with patch.object(DailyScheduler, "schedule_daily", spy_schedule_daily):
        with patch.object(BlockPlanner, "optimize_plan") as mock_legacy:
            response = client.post("/api/scheduler/daily", json=payload)
            assert response.status_code == 200
            assert len(calls) > 0, "DailyScheduler.schedule_daily was NOT called!"
            assert not mock_legacy.called, "Legacy BlockPlanner.optimize_plan was unexpectedly called!"



# ===========================================================================
# Test 3 — Successful Scheduling Response Structure
# ===========================================================================

def test_3_successful_scheduling_response_structure():
    """Test 3: A valid scheduling problem returns the complete DailyScheduleResult schema."""
    payload = {
        "problem_id": "PROB-T3-STRUCT",
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "WORK-T3-1",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 90,
                "priority_value": 80.0,
            }
        ],
        "available_windows": [
            {
                "window_id": "WIN-T3-1",
                "corridor": "Chennai-Arakkonam",
                "service_date": TARGET_DATE_STR,
                "start_time": "01:00",
                "end_time": "04:00",
                "duration_minutes": 180,
            }
        ],
    }
    response = client.post("/api/scheduler/daily", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify structural schema compliance with DailyScheduleResult
    required_fields = [
        "plan_id",
        "target_date",
        "generated_at",
        "total_scheduled",
        "total_unscheduled",
        "scheduled_works",
        "optimized_block_assignments",
        "unscheduled_works",
        "diagnostics",
        "matching_statistics",
        "optimization_metadata",
        "solver_statistics",
    ]
    for field in required_fields:
        assert field in data, f"Missing required response field: {field}"

    assert data["total_scheduled"] == 1
    assert data["total_unscheduled"] == 0
    assert len(data["scheduled_works"]) == 1
    assert data["solver_statistics"]["status"] in ("OPTIMAL", "FEASIBLE")


# ===========================================================================
# Test 4 — Priority Propagation
# ===========================================================================

def test_4_priority_propagation_through_api_pipeline():
    """
    Test 4: Verify priority_value survives:
    API request → DailySchedulingProblem → Scheduler → OptimizationRequest → CP-SAT → response
    """
    priority_input = 88.5
    payload = {
        "problem_id": "PROB-T4-PRIO",
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "WORK-T4-PRIO",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,
                "priority_value": priority_input,
            }
        ],
        "available_windows": [
            {
                "window_id": "WIN-T4-1",
                "corridor": "Chennai-Arakkonam",
                "service_date": TARGET_DATE_STR,
                "start_time": "01:00",
                "end_time": "03:00",
                "duration_minutes": 120,
            }
        ],
    }
    response = client.post("/api/scheduler/daily", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_scheduled"] == 1
    scheduled_item = data["scheduled_works"][0]
    assert scheduled_item.get("priority_value") == priority_input, (
        f"Expected priority_value {priority_input}, got {scheduled_item.get('priority_value')}"
    )

    opt_block = data["optimized_block_assignments"][0]
    assert opt_block.get("priority_value") == priority_input


# ===========================================================================
# Test 5 — Hard Constraints Overrule High Priority
# ===========================================================================

def test_5_hard_constraints_not_overridden_by_high_priority():
    """
    Test 5: An infeasible high-priority work (duration 300m > window 120m)
    must NOT be scheduled merely because of a high priority_value.
    A feasible lower-priority work must be scheduled instead.
    """
    payload = {
        "problem_id": "PROB-T5-HARD-CONSTRAINTS",
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "WORK-T5-INFEASIBLE-HIGH",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 300,  # Cannot fit in 120m window
                "priority_value": 99.0,            # Very high priority
            },
            {
                "work_id": "WORK-T5-FEASIBLE-LOW",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,   # Fits easily
                "priority_value": 20.0,            # Lower priority
            },
        ],
        "available_windows": [
            {
                "window_id": "WIN-T5-1",
                "corridor": "Chennai-Arakkonam",
                "service_date": TARGET_DATE_STR,
                "start_time": "02:00",
                "end_time": "04:00",
                "duration_minutes": 120,
                "max_parallel_works": 1,
            }
        ],
    }
    response = client.post("/api/scheduler/daily", json=payload)
    assert response.status_code == 200
    data = response.json()

    scheduled_ids = [w.get("block_request_id") or w.get("request_id") or w.get("work_id") for w in data["scheduled_works"]]
    assert "WORK-T5-FEASIBLE-LOW" in scheduled_ids, "Feasible low-priority work should have been scheduled"
    assert "WORK-T5-INFEASIBLE-HIGH" not in scheduled_ids, "Infeasible high-priority work MUST NOT be scheduled!"

    # Infeasible work must appear in unscheduled works with diagnostic reason
    unscheduled_ids = [w.get("request_id") or w.get("work_id") for w in data["unscheduled_works"]]
    assert "WORK-T5-INFEASIBLE-HIGH" in unscheduled_ids


# ===========================================================================
# Test 6 — Infeasible Optimization Yields Structured Result (Not 500)
# ===========================================================================

def test_6_infeasible_problem_returns_structured_status_not_500():
    """
    Test 6: Valid request with no feasible schedule returns HTTP 200 with structured
    diagnostics and total_scheduled == 0, rather than HTTP 500 crash.
    """
    payload = {
        "problem_id": "PROB-T6-INFEASIBLE",
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "WORK-T6-TOO-LONG",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 500,
                "priority_value": 90.0,
            }
        ],
        "available_windows": [
            {
                "window_id": "WIN-T6-SHORT",
                "corridor": "Chennai-Arakkonam",
                "service_date": TARGET_DATE_STR,
                "start_time": "01:00",
                "end_time": "02:00",
                "duration_minutes": 60,
            }
        ],
    }
    response = client.post("/api/scheduler/daily", json=payload)
    assert response.status_code == 200, f"Expected 200 with diagnostics, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["total_scheduled"] == 0
    assert data["total_unscheduled"] >= 1
    assert len(data["unscheduled_works"]) >= 1
    assert any(
        w.get("request_id") == "WORK-T6-TOO-LONG" or w.get("work_id") == "WORK-T6-TOO-LONG"
        for w in data["unscheduled_works"]
    )
    assert "diagnostics" in data



# ===========================================================================
# Test 7 — Validation Errors
# ===========================================================================

def test_7_validation_errors_return_422():
    """Test 7: Malformed or invalid scheduling input receives HTTP 422 Unprocessable Entity."""
    # Invalid date format
    response = client.post("/api/scheduler/daily", json={
        "target_date": "not-a-valid-date",
    })
    assert response.status_code == 422

    # Negative duration in candidate work
    response = client.post("/api/scheduler/daily", json={
        "target_date": TARGET_DATE_STR,
        "candidate_works": [
            {
                "work_id": "W-BAD",
                "location": "Loc",
                "required_duration_minutes": -30,
            }
        ],
    })
    assert response.status_code == 422

    # Buffer minutes out of range (> 60)
    response = client.post("/api/scheduler/daily", json={
        "target_date": TARGET_DATE_STR,
        "buffer_minutes": 999,
    })
    assert response.status_code == 422


# ===========================================================================
# Test 8 — Legacy Compatibility
# ===========================================================================

def test_8_legacy_endpoints_compatibility():
    """Test 8: Verify existing legacy endpoints still behave as expected."""
    # Legacy endpoint 1: POST /api/scheduler/schedule (Phase 4 heuristic)
    resp_sched = client.post("/api/scheduler/schedule", json={
        "target_date": TARGET_DATE_STR,
        "buffer_minutes": 15,
    })
    assert resp_sched.status_code == 200
    sched_data = resp_sched.json()
    assert "total_requested" in sched_data
    assert "scheduled_items" in sched_data

    # Legacy endpoint 2: POST /api/plans/optimize (Phase 5 CP-SAT)
    resp_opt = client.post("/api/plans/optimize", json={
        "target_date": TARGET_DATE_STR,
        "horizon_days": 1,
        "buffer_minutes": 15,
    })
    assert resp_opt.status_code == 200
    opt_data = resp_opt.json()
    assert "plan_id" in opt_data
    assert "status" in opt_data
    assert "solver_statistics" in opt_data


# ===========================================================================
# Decoupled Planning Endpoints Tests
# ===========================================================================

def test_decoupled_monthly_plan_endpoint():
    """Verify POST /api/plans/monthly returns a valid MonthlyPlan."""
    response = client.post("/api/plans/monthly", json={
        "target_date": TARGET_DATE_STR,
        "horizon_days": 30,
    })
    assert response.status_code == 200
    data = response.json()
    assert "plan_id" in data
    assert "planning_month" in data
    assert "weekly_breakdown" in data
    assert "items" in data


def test_decoupled_weekly_plan_endpoint():
    """Verify POST /api/plans/weekly returns a valid WeeklyPlan."""
    response = client.post("/api/plans/weekly", json={
        "target_date": TARGET_DATE_STR,
        "horizon_days": 7,
    })
    assert response.status_code == 200
    data = response.json()
    assert "plan_id" in data
    assert "horizon_days" in data
    assert "corridor_summaries" in data
    assert "items" in data


def test_decoupled_daily_problem_endpoint():
    """Verify POST /api/plans/daily-problem returns a valid DailySchedulingProblem."""
    response = client.post("/api/plans/daily-problem", json={
        "target_date": TARGET_DATE_STR,
        "buffer_minutes": 15,
    })
    assert response.status_code == 200
    data = response.json()
    assert "problem_id" in data
    assert data["target_date"] == TARGET_DATE_STR
    assert "candidate_works" in data
    assert "available_windows" in data
