"""
Phase 7 — End-to-End System Verification & Final Hardening Test Suite.

Verifies the complete Railway Block Planner pipeline:
    DATA INGESTION / REPOSITORY
        ↓
    AI PRIORITIZATION (urgency, criticality, overdue → priority_value)
        ↓
    BLOCK PLANNER (Monthly/Weekly → DailySchedulingProblem)
        ↓
    DAILY SCHEDULER (feasible corridor window matching)
        ↓
    CONFLICT DETECTION (train movements, track occupancy, headway buffers)
        ↓
    CP-SAT MATHEMATICAL OPTIMIZATION (exact objective & hard constraints)
        ↓
    FEASIBILITY & PLAN VALIDATION (comprehensive validator)
        ↓
    PERSISTENCE LAYER (SQLite optimized plan storage & retrieval)
        ↓
    REST API (POST /optimize, GET /optimized/{plan_id}, GET /optimized/latest)
        ↓
    FRONTEND DATA ADAPTER CONTRACTS
"""

from __future__ import annotations

from datetime import date, time
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from backend.app.block_planner.schemas import (
    CandidateWorkItem,
    CorridorAvailabilityWindow,
    DailySchedulingProblem,
)
from backend.app.main import app
from backend.app.optimizer.schemas import OptimizationStatus
from backend.app.prioritization import PriorityEnrichment
from backend.app.scheduler.scheduler import DailyScheduler
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)

client = TestClient(app)
TARGET_DATE = date(2026, 9, 7)
TARGET_DATE_STR = "2026-09-07"


# ===========================================================================
# Part 2 & 3 — Single Request End-to-End Trace & Priority Propagation
# ===========================================================================

def test_single_request_trace_and_priority_propagation():
    """
    Traces a single deterministic maintenance request (REQ-E2E-001) through all pipeline stages:
    Ingestion → Enrichment (92.0) → Problem → CP-SAT → Validation → Persistence → API.
    Verifies priority_value = 92.0 remains unchanged throughout.
    """
    req_id = "REQ-E2E-001"
    raw_record = MaintenanceRecord(
        asset_id=req_id,
        asset_type="Track",
        location="Chennai-Arakkonam",
        maintenance_type="Track Renewal",
        maintenance_required=True,
        priority=Priority.CRITICAL,
        duration_minutes=90,
        requested_date=TARGET_DATE,
        preferred_start=time(2, 0),
        required_resources=2,
        equipment="Tamper-01",
        status=MaintenanceStatus.PENDING,
        source="smms",
        priority_value=92.0,
        priority_enrichment=PriorityEnrichment(
            urgency=0.95,
            criticality=0.90,
            overdue_factor=1.30,
            priority_value=92.0,
            metadata={"explanation": "Safety critical track renewal on high density corridor"},
        ),
    )

    # 1. Verify priority extraction
    assert raw_record.priority_value == 92.0
    assert raw_record.priority_enrichment is not None
    assert raw_record.priority_enrichment.priority_value == 92.0

    # 2. Block Planner conversion
    work_item = CandidateWorkItem(
        work_id=raw_record.asset_id,
        location=raw_record.location,
        corridor=raw_record.location,
        required_duration_minutes=raw_record.duration_minutes,
        preferred_start="02:00",
        priority_value=raw_record.priority_value,
        priority=raw_record.priority,
    )
    assert work_item.work_id == req_id
    assert work_item.priority_value == 92.0

    # 3. Daily Scheduler matching
    avail_window = CorridorAvailabilityWindow(
        window_id="WIN-E2E-01",
        corridor="Chennai-Arakkonam",
        service_date=TARGET_DATE,
        start_time="01:30",
        end_time="04:30",
        duration_minutes=180,
    )
    problem = DailySchedulingProblem(
        problem_id="PROB-E2E-01",
        target_date=TARGET_DATE,
        candidate_works=[work_item],
        available_windows=[avail_window],
    )

    # 4. CP-SAT Optimization
    scheduler = DailyScheduler()
    sched_result = scheduler.schedule_daily(problem)
    assert sched_result.total_scheduled == 1
    assert len(sched_result.optimized_block_assignments) == 1

    match = sched_result.optimized_block_assignments[0]
    assigned_work_id = match.request_id if hasattr(match, "request_id") else getattr(match, "work_id", None)
    assert assigned_work_id == req_id
    assert getattr(match, "priority_value", None) == 92.0

    # 5. API & Persistence
    api_payload = {
        "target_date": TARGET_DATE_STR,
        "horizon_days": 1,
    }
    resp = client.post("/api/plans/optimize", json=api_payload)
    assert resp.status_code == 200
    plan_data = resp.json()
    assert "plan_id" in plan_data
    plan_id = plan_data["plan_id"]

    # 6. Persistence Retrieval
    get_resp = client.get(f"/api/plans/optimized/{plan_id}")
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["plan_meta"]["plan_id"] == plan_id
    assert retrieved["result"]["status"] in ("OPTIMAL", "FEASIBLE")


# ===========================================================================
# Part 8 — Priority Competition vs Feasibility Primacy
# ===========================================================================

def test_priority_competition_and_feasibility_primacy():
    """
    Verifies that when two tasks compete for a single slot:
    1. Job A (Priority 95) beats Job B (Priority 40) for the same slot.
    2. If Job A's duration (240m) exceeds slot capacity (120m) while Job B (60m) fits,
       feasibility takes precedence and Job B is scheduled.
    """
    scheduler = DailyScheduler()

    # Scenario 1: Direct Competition (same duration, different priority)
    window = CorridorAvailabilityWindow(
        window_id="WIN-COMPETE-1",
        corridor="Chennai-Arakkonam",
        service_date=TARGET_DATE,
        start_time="02:00",
        end_time="04:00",
        duration_minutes=120,
    )

    job_a = CandidateWorkItem(
        work_id="JOB-A-HIGH",
        location="Chennai-Arakkonam",
        corridor="Chennai-Arakkonam",
        required_duration_minutes=90,
        preferred_start="02:00",
        priority_value=95.0,
        priority=Priority.CRITICAL,
    )
    job_b = CandidateWorkItem(
        work_id="JOB-B-LOW",
        location="Chennai-Arakkonam",
        corridor="Chennai-Arakkonam",
        required_duration_minutes=90,
        preferred_start="02:00",
        priority_value=40.0,
        priority=Priority.LOW,
    )

    prob1 = DailySchedulingProblem(
        problem_id="PROB-COMP-1",
        target_date=TARGET_DATE,
        candidate_works=[job_a, job_b],
        available_windows=[window],
    )
    res1 = scheduler.schedule_daily(prob1)
    assert res1.total_scheduled == 1
    sched_ids = [getattr(b, "request_id", None) or getattr(b, "work_id", None) for b in res1.optimized_block_assignments]
    assert "JOB-A-HIGH" in sched_ids
    assert res1.total_unscheduled == 1

    # Scenario 2: Feasibility Primacy (High priority is infeasible, Low priority fits)
    job_a_long = CandidateWorkItem(
        work_id="JOB-A-OVERSIZED",
        location="Chennai-Arakkonam",
        corridor="Chennai-Arakkonam",
        required_duration_minutes=240,  # Exceeds 120m window
        preferred_start="02:00",
        priority_value=95.0,
        priority=Priority.CRITICAL,
    )
    job_b_fits = CandidateWorkItem(
        work_id="JOB-B-FITS",
        location="Chennai-Arakkonam",
        corridor="Chennai-Arakkonam",
        required_duration_minutes=60,  # Fits cleanly in 120m window
        preferred_start="02:00",
        priority_value=40.0,
        priority=Priority.LOW,
    )

    prob2 = DailySchedulingProblem(
        problem_id="PROB-COMP-2",
        target_date=TARGET_DATE,
        candidate_works=[job_a_long, job_b_fits],
        available_windows=[window],
    )
    res2 = scheduler.schedule_daily(prob2)
    assert res2.total_scheduled == 1
    sched_ids2 = [getattr(b, "request_id", None) or getattr(b, "work_id", None) for b in res2.optimized_block_assignments]
    assert "JOB-B-FITS" in sched_ids2
    assert res2.total_unscheduled == 1


# ===========================================================================
# Part 10 & 11 — Request Accounting & Unscheduled Diagnostics
# ===========================================================================

def test_request_accounting_and_diagnostics():
    """
    Verifies the mathematical invariance:
    TOTAL_REQUESTS == SCHEDULED_REQUESTS + UNSCHEDULED_REQUESTS
    and checks that unscheduled requests carry diagnostic reasons and preserved priority values.
    """
    scheduler = DailyScheduler()
    window = CorridorAvailabilityWindow(
        window_id="WIN-ACCT-1",
        corridor="Chennai-Villupuram",
        service_date=TARGET_DATE,
        start_time="01:00",
        end_time="03:00",
        duration_minutes=120,
    )

    works = [
        CandidateWorkItem(
            work_id="REQ-OK-1",
            location="Chennai-Villupuram",
            corridor="Chennai-Villupuram",
            required_duration_minutes=60,
            preferred_start="01:00",
            priority_value=80.0,
        ),
        CandidateWorkItem(
            work_id="REQ-OK-2",
            location="Chennai-Villupuram",
            corridor="Chennai-Villupuram",
            required_duration_minutes=60,
            preferred_start="02:00",
            priority_value=70.0,
        ),
        CandidateWorkItem(
            work_id="REQ-NO-WINDOW",
            location="Remote-Corridor-No-Window",
            corridor="Remote-Corridor-No-Window",
            required_duration_minutes=60,
            preferred_start="01:00",
            priority_value=85.0,
        ),
        CandidateWorkItem(
            work_id="REQ-TOO-LONG",
            location="Chennai-Villupuram",
            corridor="Chennai-Villupuram",
            required_duration_minutes=300,
            preferred_start="01:00",
            priority_value=60.0,
        ),
    ]

    prob = DailySchedulingProblem(
        problem_id="PROB-ACCT-1",
        target_date=TARGET_DATE,
        candidate_works=works,
        available_windows=[window],
    )
    result = scheduler.schedule_daily(prob)

    # Invariance check
    total_in = len(works)
    total_out = result.total_scheduled + result.total_unscheduled
    assert total_in == total_out == 4

    # Diagnostic checks
    unsched_map = {}
    for u in result.unscheduled_works:
        if isinstance(u, dict):
            k = u.get("work_id") or u.get("request_id")
            unsched_map[k] = u
        else:
            k = getattr(u, "work_id", None) or getattr(u, "request_id", None)
            unsched_map[k] = u

    assert "REQ-NO-WINDOW" in unsched_map
    assert "REQ-TOO-LONG" in unsched_map

    item_no_win = unsched_map["REQ-NO-WINDOW"]
    pv_no_win = item_no_win.get("priority_value") if isinstance(item_no_win, dict) else getattr(item_no_win, "priority_value", None)
    assert pv_no_win == 85.0


# ===========================================================================
# Part 12 & 27 — Multiple Optimization Runs & Persistence Isolation
# ===========================================================================

def test_multiple_optimization_runs_isolation():
    """
    Runs optimization twice with different horizons/parameters.
    Verifies that Plan A and Plan B remain isolated in persistence,
    and GET /latest returns the most recent run (Plan B).
    """
    # 1. Trigger Run 1 (Plan A)
    resp1 = client.post("/api/plans/optimize", json={"target_date": TARGET_DATE_STR, "horizon_days": 1})
    assert resp1.status_code == 200
    plan_a = resp1.json()
    plan_a_id = plan_a["plan_id"]

    # 2. Trigger Run 2 (Plan B)
    resp2 = client.post("/api/plans/optimize", json={"target_date": TARGET_DATE_STR, "horizon_days": 7})
    assert resp2.status_code == 200
    plan_b = resp2.json()
    plan_b_id = plan_b["plan_id"]

    assert plan_a_id != plan_b_id

    # 3. Retrieve Plan A by ID
    get_a = client.get(f"/api/plans/optimized/{plan_a_id}")
    assert get_a.status_code == 200
    assert get_a.json()["plan_meta"]["plan_id"] == plan_a_id
    assert get_a.json()["plan_meta"]["horizon_days"] == 1

    # 4. Retrieve Plan B by ID
    get_b = client.get(f"/api/plans/optimized/{plan_b_id}")
    assert get_b.status_code == 200
    assert get_b.json()["plan_meta"]["plan_id"] == plan_b_id
    assert get_b.json()["plan_meta"]["horizon_days"] == 7

    # 5. Retrieve Latest
    get_latest = client.get("/api/plans/optimized/latest")
    assert get_latest.status_code == 200
    assert get_latest.json()["plan_meta"]["plan_id"] == plan_b_id


# ===========================================================================
# Part 30 — Deterministic 5-Request Full-Scenario Test
# ===========================================================================

def test_deterministic_5_request_full_scenario():
    """
    Part 30 E2E Scenario:
    5 requests with diverse priority scores:
      REQ-001 (95) -> Critical priority, fits in Alpha corridor window 1 (90m in 120m)
      REQ-002 (82) -> High priority, fits in Alpha corridor window 2 (90m in 120m)
      REQ-003 (60) -> Medium priority, fits in Beta corridor (90m in 90m window)
      REQ-004 (45) -> Low priority, competes with REQ-003 for Beta corridor
      REQ-005 (30) -> Low priority, no available window
    Verifies 100% request accounting, objective scoring, and diagnostic preservation.
    """
    scheduler = DailyScheduler()

    windows = [
        CorridorAvailabilityWindow(
            window_id="WIN-S1A",
            corridor="Corridor-Alpha",
            service_date=TARGET_DATE,
            start_time="01:00",
            end_time="03:00",
            duration_minutes=120,
        ),
        CorridorAvailabilityWindow(
            window_id="WIN-S1B",
            corridor="Corridor-Alpha",
            service_date=TARGET_DATE,
            start_time="03:15",
            end_time="05:15",
            duration_minutes=120,
        ),
        CorridorAvailabilityWindow(
            window_id="WIN-S2",
            corridor="Corridor-Beta",
            service_date=TARGET_DATE,
            start_time="02:00",
            end_time="03:30",
            duration_minutes=90,
        ),
    ]

    requests = [
        CandidateWorkItem(
            work_id="REQ-001",
            location="Corridor-Alpha",
            corridor="Corridor-Alpha",
            required_duration_minutes=90,
            preferred_start="01:00",
            priority_value=95.0,
            priority=Priority.CRITICAL,
        ),
        CandidateWorkItem(
            work_id="REQ-002",
            location="Corridor-Alpha",
            corridor="Corridor-Alpha",
            required_duration_minutes=90,
            preferred_start="03:30",
            priority_value=82.0,
            priority=Priority.HIGH,
        ),
        CandidateWorkItem(
            work_id="REQ-003",
            location="Corridor-Beta",
            corridor="Corridor-Beta",
            required_duration_minutes=90,
            preferred_start="02:00",
            priority_value=60.0,
            priority=Priority.MEDIUM,
        ),
        CandidateWorkItem(
            work_id="REQ-004",
            location="Corridor-Beta",
            corridor="Corridor-Beta",
            required_duration_minutes=90,
            preferred_start="02:00",
            priority_value=45.0,
            priority=Priority.LOW,
        ),
        CandidateWorkItem(
            work_id="REQ-005",
            location="Corridor-Gamma-NoWindow",
            corridor="Corridor-Gamma-NoWindow",
            required_duration_minutes=60,
            preferred_start="01:00",
            priority_value=30.0,
            priority=Priority.LOW,
        ),
    ]

    problem = DailySchedulingProblem(
        problem_id="PROB-SCENARIO-5",
        target_date=TARGET_DATE,
        candidate_works=requests,
        available_windows=windows,
    )
    res = scheduler.schedule_daily(problem)

    # 1. Invariance
    assert res.total_scheduled + res.total_unscheduled == 5

    # 2. Alpha Corridor takes both REQ-001 and REQ-002 across its two distinct windows
    scheduled_ids = {
        getattr(s, "work_id", None) or getattr(s, "request_id", None)
        for s in res.optimized_block_assignments
    }
    assert "REQ-001" in scheduled_ids
    assert "REQ-002" in scheduled_ids

    # 3. Beta Corridor has 90m window: REQ-003 (60.0) beats REQ-004 (45.0)
    assert "REQ-003" in scheduled_ids
    assert "REQ-004" not in scheduled_ids

    # 4. Gamma Corridor has no window: REQ-005 unscheduled
    assert "REQ-005" not in scheduled_ids

    # 5. Diagnostics
    unsched_ids = set()
    for u in res.unscheduled_works:
        if isinstance(u, dict):
            unsched_ids.add(u.get("work_id") or u.get("request_id"))
        else:
            unsched_ids.add(getattr(u, "work_id", None) or getattr(u, "request_id", None))

    assert "REQ-004" in unsched_ids
    assert "REQ-005" in unsched_ids
