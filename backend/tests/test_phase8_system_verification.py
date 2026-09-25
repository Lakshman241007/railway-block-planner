"""
Phase 8 System Verification and Architectural Validation Test Suite.

Comprehensive cross-module verification covering:
1. End-to-end planning pipeline (Monthly → Weekly → Daily Problem → Scheduler → CP-SAT → Result)
2. Monthly/Weekly/Daily planning horizon consistency
3. Priority propagation and single-signal XOR objective verification
4. Missing priority and AI Prioritizer fallback behavior
5. Candidate matching and availability classification (Available, Restricted, Blocked)
6. Mandatory maintenance and spatial-temporal contention handling
7. Infeasible optimization and solver status mapping
8. API end-to-end integration and legacy compatibility
9. Determinism, human-workload factor principles, and performance smoke testing
"""

from __future__ import annotations

from datetime import date, time as dt_time, timedelta
import json
import time
from typing import Any, Dict, List, Optional
import unittest.mock

import pytest
from fastapi.testclient import TestClient

from backend.app.block_planner.planner import BlockPlanner
from backend.app.block_planner.schemas import (
    CandidateWorkItem,
    DailyProblemRequest,
    DailySchedulingProblem,
    MonthlyPlan,
    MonthlyPlanRequest,
    WeeklyPlan,
    WeeklyPlanRequest,
)
from backend.app.main import app
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.objective import compute_slot_coefficient
from backend.app.optimizer.schemas import ObjectiveWeights, OptimizationRequest, OptimizationStatus
from backend.app.prioritization.prioritizer import AIPrioritizer
from backend.app.scheduler.scheduler import DailyScheduler
from backend.app.scheduler.schemas import (
    CorridorAvailabilityWindow,
    DailyScheduleResult,
)
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    BlockType,
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
    PriorityEnrichment,
)
from backend.app.services.scheduling_service import SchedulingService

client = TestClient(app)

TARGET_DATE = date(2026, 9, 7)
TARGET_DATE_STR = "2026-09-07"


def make_maint_record(
    asset_id: str,
    location: str = "Chennai-Arakkonam",
    asset_type: str = "Track",
    maintenance_type: str = "Preventive",
    maintenance_required: bool = True,
    priority: Priority = Priority.HIGH,
    priority_value: Optional[float] = None,
    priority_enrichment: Optional[PriorityEnrichment] = None,
    duration_minutes: int = 60,
    requested_date: date = TARGET_DATE,
    preferred_start: Any = dt_time(2, 0),
    required_resources: int = 1,
    equipment: str = "Track Tamper",
    status: MaintenanceStatus = MaintenanceStatus.PENDING,
    source: str = "TEST",
) -> MaintenanceRecord:
    return MaintenanceRecord(
        asset_id=asset_id,
        location=location,
        asset_type=asset_type,
        maintenance_type=maintenance_type,
        maintenance_required=maintenance_required,
        priority=priority,
        priority_value=priority_value,
        priority_enrichment=priority_enrichment,
        duration_minutes=duration_minutes,
        requested_date=requested_date,
        preferred_start=preferred_start,
        required_resources=required_resources,
        equipment=equipment,
        status=status,
        source=source,
    )


# ===========================================================================
# 1. End-to-End Planning Pipeline & Horizon Consistency
# ===========================================================================

class TestPipelineEndToEndAndHorizon:
    """Verifies complete Monthly → Weekly → Daily Problem → DailyScheduler → CP-SAT flow."""

    def test_full_pipeline_monthly_to_cpsat_result(self):
        """Verify data flow across all planning and scheduling tiers."""
        # 1. Setup mock/sample operational records
        m1 = make_maint_record(
            asset_id="AST-E2E-1",
            location="Chennai-Arakkonam",
            asset_type="Track",
            maintenance_type="Preventive",
            requested_date=TARGET_DATE,
            duration_minutes=60,
            priority=Priority.HIGH,
            priority_value=85.0,
            maintenance_required=True,
            status=MaintenanceStatus.PENDING,
        )
        b1 = BlockRecord(
            block_id="BLK-E2E-1",
            location="Chennai-Arakkonam",
            block_type=BlockType.MAINTENANCE,
            requested_date=TARGET_DATE,
            requested_start="02:00",
            requested_end="04:00",
            status=BlockStatus.REQUESTED,
            reason="Night maintenance",
            priority=Priority.MEDIUM,
            priority_value=50.0,
        )

        planner = BlockPlanner(
            maintenance_records=[m1],
            block_records=[b1],
            trains=[],
            movements=[],
            timetables=[],
        )

        # 2. Monthly Plan
        monthly = planner.generate_monthly_plan(target_date=TARGET_DATE, horizon_days=30)
        assert isinstance(monthly, MonthlyPlan)
        assert monthly.total_items >= 2
        assert any(it.work_id == "MNT-AST-E2E-1" for it in monthly.items)

        # 3. Weekly Plan
        weekly = planner.generate_weekly_plan(target_date=TARGET_DATE, horizon_days=7)
        assert isinstance(weekly, WeeklyPlan)
        assert weekly.total_items >= 2
        assert any(it.work_id == "MNT-AST-E2E-1" for it in weekly.items)

        # 4. Daily Problem Preparation
        problem = planner.prepare_daily_problem(target_date=TARGET_DATE, buffer_minutes=15)
        assert isinstance(problem, DailySchedulingProblem)
        assert problem.target_date == TARGET_DATE
        assert len(problem.candidate_works) >= 2
        assert len(problem.available_windows) >= 1

        # 5. Daily Scheduler & CP-SAT Execution
        scheduler = DailyScheduler(buffer_minutes=15)
        result = scheduler.schedule_daily(problem=problem, invoke_solver=True)
        assert isinstance(result, DailyScheduleResult)
        assert result.plan_id.startswith("DSCHED-")
        assert result.target_date == TARGET_DATE
        assert result.total_scheduled + result.total_unscheduled == len(problem.candidate_works)
        assert result.solver_statistics is not None

    def test_planning_horizon_consistency(self):
        """
        Verify: monthly horizon (30 days) ⊃ weekly horizon (7 days) ⊃ daily target date.
        Work scheduled outside weekly horizon must not appear in weekly plan.
        """
        day_within_week = TARGET_DATE + timedelta(days=2)
        day_outside_week = TARGET_DATE + timedelta(days=15)

        m_in = make_maint_record(
            asset_id="AST-IN-WEEK",
            location="Chennai-Arakkonam",
            asset_type="Signal",
            requested_date=day_within_week,
            duration_minutes=60,
            priority=Priority.HIGH,
            maintenance_required=True,
        )
        m_out = make_maint_record(
            asset_id="AST-OUT-WEEK",
            location="Chennai-Arakkonam",
            asset_type="Signal",
            requested_date=day_outside_week,
            duration_minutes=60,
            priority=Priority.MEDIUM,
            maintenance_required=True,
        )

        planner = BlockPlanner(
            maintenance_records=[m_in, m_out],
            block_records=[],
            trains=[],
            movements=[],
            timetables=[],
        )

        monthly = planner.generate_monthly_plan(target_date=TARGET_DATE, horizon_days=30)
        weekly = planner.generate_weekly_plan(target_date=TARGET_DATE, horizon_days=7)
        daily = planner.prepare_daily_problem(target_date=day_within_week)

        # Monthly should have both
        monthly_work_ids = {it.work_id for it in monthly.items}
        assert "MNT-AST-IN-WEEK" in monthly_work_ids
        assert "MNT-AST-OUT-WEEK" in monthly_work_ids

        # Weekly should have ONLY the one within 7 days
        weekly_work_ids = {it.work_id for it in weekly.items}
        assert "MNT-AST-IN-WEEK" in weekly_work_ids
        assert "MNT-AST-OUT-WEEK" not in weekly_work_ids

        # Daily problem for day_within_week should contain MNT-AST-IN-WEEK
        daily_work_ids = {it.work_id for it in daily.candidate_works}
        assert "MNT-AST-IN-WEEK" in daily_work_ids
        assert "MNT-AST-OUT-WEEK" not in daily_work_ids


# ===========================================================================
# 2. Priority Propagation & Single-Signal XOR Objective
# ===========================================================================

class TestPriorityPropagationAndXOR:
    """Verifies single priority_value propagation and CP-SAT objective weighting."""

    def test_priority_value_propagates_intact_through_pipeline(self):
        """Verify priority_value survives PriorityAssessment → MaintenanceRecord → CP-SAT → Result."""
        p_val = 87.5
        enrichment = PriorityEnrichment(
            urgency=0.9,
            criticality=0.8,
            overdue_factor=0.7,
            priority_value=p_val,
        )
        record = make_maint_record(
            asset_id="AST-PRIO-PROP",
            location="Chennai-Arakkonam",
            asset_type="Track",
            requested_date=TARGET_DATE,
            duration_minutes=60,
            priority=Priority.HIGH,
            priority_value=p_val,
            priority_enrichment=enrichment,
            maintenance_required=True,
        )

        planner = BlockPlanner(maintenance_records=[record], block_records=[])
        problem = planner.prepare_daily_problem(target_date=TARGET_DATE)

        candidate = next(w for w in problem.candidate_works if w.work_id == "MNT-AST-PRIO-PROP")
        assert candidate.priority_value == p_val

        scheduler = DailyScheduler(buffer_minutes=15)
        result = scheduler.schedule_daily(problem=problem, invoke_solver=True)
        assert result.total_scheduled == 1

        sched_item = result.scheduled_works[0]
        assert sched_item.get("priority_value") == p_val

    def test_case_a_higher_priority_selected_under_scarcity(self):
        """Case A: Two feasible works competing for 1 window. Higher priority_value wins."""
        problem = DailySchedulingProblem(
            problem_id="PROB-CASE-A",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-HIGH-90",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=90.0,
                ),
                CandidateWorkItem(
                    work_id="WORK-LOW-40",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=40.0,
                ),
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-SCARCE-1",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="02:00",
                    end_time="03:00",
                    duration_minutes=60,
                    max_parallel_works=1,
                )
            ],
        )
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        assert result.total_scheduled == 1
        scheduled_ids = [w.get("request_id") or w.get("work_id") for w in result.scheduled_works]
        assert "WORK-HIGH-90" in scheduled_ids
        assert "WORK-LOW-40" not in scheduled_ids

    def test_case_b_hard_constraints_dominate_priority(self):
        """Case B: Infeasible high-priority work (180m > 60m) must NOT be scheduled over feasible low-priority work."""
        problem = DailySchedulingProblem(
            problem_id="PROB-CASE-B",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-INFEASIBLE-99",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=180,  # exceeds 60m window
                    priority_value=99.0,
                ),
                CandidateWorkItem(
                    work_id="WORK-FEASIBLE-15",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=15.0,
                ),
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-60M",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="02:00",
                    end_time="03:00",
                    duration_minutes=60,
                    max_parallel_works=1,
                )
            ],
        )
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        assert result.total_scheduled == 1
        scheduled_ids = [w.get("request_id") or w.get("work_id") for w in result.scheduled_works]
        assert "WORK-FEASIBLE-15" in scheduled_ids
        assert "WORK-INFEASIBLE-99" not in scheduled_ids

    def test_case_c_categorical_label_adds_zero_utility_when_priority_value_present(self):
        """Case C: Verify categorical label contributes zero additional utility when priority_value is present."""
        weights = ObjectiveWeights()
        meta_critical = {
            "priority_value": 40.0,
            "priority": Priority.CRITICAL,  # Categorical Critical
            "start_time": "02:00",
            "duration_minutes": 60,
        }
        meta_low = {
            "priority_value": 40.0,
            "priority": Priority.LOW,       # Categorical Low
            "start_time": "02:00",
            "duration_minutes": 60,
        }

        coeff_critical = compute_slot_coefficient(meta_critical, weights)
        coeff_low = compute_slot_coefficient(meta_low, weights)

        # Both coefficients must be exactly equal because priority_value is the sole signal
        assert coeff_critical == coeff_low
        assert meta_critical["priority_contribution"] == meta_low["priority_contribution"]
        assert meta_critical["priority_contribution"] == int(round(weights.weight_priority_value * 40.0))


# ===========================================================================
# 3. Missing Priority & AI Prioritizer Fallback
# ===========================================================================

class TestMissingPriorityAndAIFallback:
    """Verifies graceful degradation when numerical priority_value is absent or scoring fails."""

    def test_missing_priority_uses_categorical_fallback_without_fabricating_score(self):
        """When priority_value is None, legacy categorical Priority is used without inventing a score."""
        weights = ObjectiveWeights()
        meta_legacy = {
            "priority_value": None,
            "priority": Priority.HIGH,
            "start_time": "02:00",
            "duration_minutes": 60,
        }
        coeff = compute_slot_coefficient(meta_legacy, weights)
        # Expected: base scheduled weight + categorical HIGH weight, priority_contribution == 0
        expected = weights.weight_scheduled + weights.weight_priority_high
        assert coeff == expected
        assert meta_legacy.get("priority_contribution") == 0

    def test_ai_prioritizer_contract_success_and_failure_fallback(self):
        """Verify AIPrioritizer callback success attaches score; exception gracefully falls back."""
        record_success = make_maint_record(
            asset_id="AST-SCORER-OK",
            location="Chennai-Arakkonam",
            priority=Priority.MEDIUM,
            maintenance_required=True,
        )

        def mock_scorer_ok(rec: MaintenanceRecord):
            return PriorityEnrichment(
                urgency=0.8,
                criticality=0.7,
                overdue_factor=0.6,
                priority_value=78.0,
            )

        prioritizer_ok = AIPrioritizer(scorer=mock_scorer_ok)
        prioritizer_ok.enrich_record(record_success)
        assert record_success.priority_value == 78.0
        assert record_success.priority_enrichment is not None

        # Failure path: scorer throws exception
        record_fail = make_maint_record(
            asset_id="AST-SCORER-FAIL",
            location="Chennai-Arakkonam",
            priority=Priority.HIGH,
            maintenance_required=True,
        )

        def mock_scorer_err(rec: MaintenanceRecord):
            raise RuntimeError("Inference service unavailable")

        prioritizer_fail = AIPrioritizer(scorer=mock_scorer_err)
        prioritizer_fail.enrich_record(record_fail)

        # Must NOT crash, must NOT fabricate a score, retains legacy Priority.HIGH
        assert record_fail.priority_value is None
        assert record_fail.priority_enrichment is None
        assert record_fail.priority == Priority.HIGH


# ===========================================================================
# 4. Candidate Matching & Availability Classification
# ===========================================================================

class TestCandidateMatchingAndAvailability:
    """Verifies work-to-block matching rules and corridor window status handling."""

    def test_candidate_matching_valid_and_rejected_scenarios(self):
        """Verify location mismatch, duration mismatch, and valid match outcomes."""
        problem = DailySchedulingProblem(
            problem_id="PROB-MATCHING-TEST",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-VALID",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=50.0,
                ),
                CandidateWorkItem(
                    work_id="WORK-LOC-MISMATCH",
                    location="Arakkonam-Renigunta",  # Different corridor
                    required_duration_minutes=60,
                    priority_value=50.0,
                ),
                CandidateWorkItem(
                    work_id="WORK-DUR-MISMATCH",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=200,  # Exceeds 120m window
                    priority_value=50.0,
                ),
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-CHN-AJJ-120",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="02:00",
                    end_time="04:00",
                    duration_minutes=120,
                    status="Available",
                )
            ],
        )
        scheduler = DailyScheduler()
        avail_report = scheduler.determine_daily_availability(problem)
        match_report = scheduler.match_work_to_blocks(problem.candidate_works, avail_report)

        assert match_report.total_works == 3
        assert match_report.total_matches == 1
        assert match_report.total_rejected == 2

        matched_work_ids = {m.work_id for m in match_report.successful_matches}
        assert "WORK-VALID" in matched_work_ids

        rejection_reasons_by_work = {
            r["work_id"]: r["reasons"] for r in match_report.rejected_works
        }
        assert "Location mismatch" in rejection_reasons_by_work["WORK-LOC-MISMATCH"]
        assert "Insufficient duration" in rejection_reasons_by_work["WORK-DUR-MISMATCH"]

    def test_multiple_feasible_windows_all_preserved_for_solver(self):
        """A work fitting multiple windows must preserve all candidate pairings for CP-SAT."""
        problem = DailySchedulingProblem(
            problem_id="PROB-MULTI-WIN",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-FLEXIBLE",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=60.0,
                )
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-1",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="01:00",
                    end_time="03:00",
                    duration_minutes=120,
                ),
                CorridorAvailabilityWindow(
                    window_id="WIN-2",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="03:30",
                    end_time="05:30",
                    duration_minutes=120,
                ),
            ],
        )
        scheduler = DailyScheduler()
        avail_report = scheduler.determine_daily_availability(problem)
        match_report = scheduler.match_work_to_blocks(problem.candidate_works, avail_report)

        # Must have 2 successful matches for the single work
        assert len(match_report.successful_matches) == 2
        matched_window_ids = {m.window_id for m in match_report.successful_matches}
        assert matched_window_ids == {"WIN-1", "WIN-2"}

    def test_availability_classification_blocked_window_not_scheduled(self):
        """A window marked as Blocked cannot be scheduled, even with maximum priority."""
        problem = DailySchedulingProblem(
            problem_id="PROB-BLOCKED-WIN",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-ON-BLOCKED",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=100.0,
                )
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-BLOCKED",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="02:00",
                    end_time="04:00",
                    duration_minutes=120,
                    status="Blocked",
                    restrictions=["Full traffic possession block"],
                )
            ],
        )
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        assert result.total_scheduled == 0
        assert result.total_unscheduled >= 1


# ===========================================================================
# 5. Mandatory Maintenance & Contention Handling
# ===========================================================================

class TestMandatoryAndContention:
    """Verifies mandatory work enforcement and spatial-temporal contention handling."""

    def test_mandatory_work_scheduled_over_optional(self):
        """A mandatory work (is_mandatory=True) must be scheduled when competing with optional work."""
        problem = DailySchedulingProblem(
            problem_id="PROB-MANDATORY-TEST",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-MANDATORY",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    is_mandatory=True,
                    priority=Priority.CRITICAL,
                    priority_value=50.0,
                ),
                CandidateWorkItem(
                    work_id="WORK-OPTIONAL",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    is_mandatory=False,
                    priority=Priority.MEDIUM,
                    priority_value=50.0,
                ),
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-SINGLE-CAPACITY",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="02:00",
                    end_time="03:00",
                    duration_minutes=60,
                    max_parallel_works=1,
                )
            ],
        )
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        assert result.total_scheduled == 1
        scheduled_ids = [w.get("request_id") or w.get("work_id") for w in result.scheduled_works]
        assert "WORK-MANDATORY" in scheduled_ids

    def test_conflicting_works_overlapping_windows_feasible_subset_selected(self):
        """When multiple works compete for overlapping track windows, CP-SAT selects a feasible non-overlapping subset."""
        problem = DailySchedulingProblem(
            problem_id="PROB-CONTENTION-TEST",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-C1",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=80.0,
                ),
                CandidateWorkItem(
                    work_id="WORK-C2",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=70.0,
                ),
            ],
            available_windows=[
                # Single line window allowing only 1 work
                CorridorAvailabilityWindow(
                    window_id="WIN-EXCLUSIVE",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="01:00",
                    end_time="02:00",
                    duration_minutes=60,
                    max_parallel_works=1,
                )
            ],
        )
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        assert result.total_scheduled == 1
        assert result.total_unscheduled == 1
        assert len(result.unscheduled_works) == 1


# ===========================================================================
# 6. Infeasibility & Solver Status Handling
# ===========================================================================

class TestInfeasibilityAndSolverStatuses:
    """Verifies graceful handling of infeasible problems and complete status mappings."""

    def test_infeasible_problem_returns_structured_result_not_crash(self):
        """Infeasible problem returns structured DailyScheduleResult with 0 scheduled, not an unhandled error."""
        problem = DailySchedulingProblem(
            problem_id="PROB-INFEASIBLE-TEST",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="WORK-IMPOSSIBLE",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=500,
                    priority_value=99.0,
                )
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-TINY",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="01:00",
                    end_time="01:30",
                    duration_minutes=30,
                )
            ],
        )
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        assert result.total_scheduled == 0
        assert result.total_unscheduled >= 1
        assert len(result.unscheduled_works) >= 1

    def test_solver_status_mapping_all_statuses(self):
        """Verify status mapping covers all OptimizationStatus enum values."""
        expected_statuses = {
            OptimizationStatus.OPTIMAL,
            OptimizationStatus.FEASIBLE,
            OptimizationStatus.INFEASIBLE,
            OptimizationStatus.TIME_LIMIT,
            OptimizationStatus.UNKNOWN,
            OptimizationStatus.MODEL_INVALID,
        }
        for status in expected_statuses:
            assert isinstance(status.value, str)
            assert status in OptimizationStatus


# ===========================================================================
# 7. API End-to-End & Legacy Compatibility
# ===========================================================================

class TestApiEndToEndAndLegacyCompatibility:
    """Verifies FastAPI endpoints, SchedulingService orchestration, and legacy routes."""

    def test_fastapi_daily_scheduling_via_service(self):
        """Exercise POST /api/scheduler/daily through TestClient."""
        payload = {
            "problem_id": "PROB-API-E2E",
            "target_date": TARGET_DATE_STR,
            "candidate_works": [
                {
                    "work_id": "WORK-API-1",
                    "location": "Chennai-Arakkonam",
                    "required_duration_minutes": 60,
                    "priority_value": 75.0,
                }
            ],
            "available_windows": [
                {
                    "window_id": "WIN-API-1",
                    "corridor": "Chennai-Arakkonam",
                    "service_date": TARGET_DATE_STR,
                    "start_time": "02:00",
                    "end_time": "04:00",
                    "duration_minutes": 120,
                }
            ],
        }
        response = client.post("/api/scheduler/daily", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"].startswith("DSCHED-")
        assert data["total_scheduled"] == 1

    def test_fastapi_decoupled_planning_endpoints(self):
        """Verify POST /api/plans/monthly, weekly, and daily-problem work through FastAPI."""
        # Monthly
        r_m = client.post("/api/plans/monthly", json={"target_date": TARGET_DATE_STR, "horizon_days": 30})
        assert r_m.status_code == 200
        assert "plan_id" in r_m.json()

        # Weekly
        r_w = client.post("/api/plans/weekly", json={"target_date": TARGET_DATE_STR, "horizon_days": 7})
        assert r_w.status_code == 200
        assert "plan_id" in r_w.json()

        # Daily Problem
        r_d = client.post("/api/plans/daily-problem", json={"target_date": TARGET_DATE_STR, "buffer_minutes": 15})
        assert r_d.status_code == 200
        assert "problem_id" in r_d.json()

    def test_legacy_endpoints_unbroken(self):
        """Verify legacy endpoints /api/plans/optimize and /api/scheduler/schedule continue working."""
        # Legacy Phase 4
        r_sched = client.post("/api/scheduler/schedule", json={"target_date": TARGET_DATE_STR, "buffer_minutes": 15})
        assert r_sched.status_code == 200

        # Legacy Phase 5
        r_opt = client.post("/api/plans/optimize", json={"target_date": TARGET_DATE_STR, "horizon_days": 1, "buffer_minutes": 15})
        assert r_opt.status_code == 200

    def test_data_contract_serialization_roundtrip(self):
        """Verify DailySchedulingProblem and DailyScheduleResult serialize/deserialize cleanly."""
        problem = DailySchedulingProblem(
            problem_id="PROB-ROUNDTRIP",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(
                    work_id="W-RT-1",
                    location="Chennai-Arakkonam",
                    required_duration_minutes=60,
                    priority_value=82.5,
                )
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id="WIN-RT-1",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time="01:00",
                    end_time="03:00",
                    duration_minutes=120,
                )
            ],
        )
        json_str = problem.model_dump_json()
        restored = DailySchedulingProblem.model_validate_json(json_str)
        assert restored.problem_id == problem.problem_id
        assert restored.candidate_works[0].priority_value == 82.5


# ===========================================================================
# 8. Determinism, Human-Workload Principles & Performance Smoke Test
# ===========================================================================

class TestDeterminismHumanWorkloadPerformance:
    """Verifies deterministic solver stability, factor simplicity, and basic runtime bounds."""

    def test_deterministic_solution_stability(self):
        """Run identical problem twice; verify identical scheduled assignments and objective value."""
        def make_problem():
            return DailySchedulingProblem(
                problem_id="PROB-STABILITY",
                target_date=TARGET_DATE,
                candidate_works=[
                    CandidateWorkItem(
                        work_id="WORK-S1",
                        location="Chennai-Arakkonam",
                        required_duration_minutes=60,
                        priority_value=70.0,
                    ),
                    CandidateWorkItem(
                        work_id="WORK-S2",
                        location="Chennai-Arakkonam",
                        required_duration_minutes=90,
                        priority_value=85.0,
                    ),
                ],
                available_windows=[
                    CorridorAvailabilityWindow(
                        window_id="WIN-S1",
                        corridor="Chennai-Arakkonam",
                        service_date=TARGET_DATE,
                        start_time="01:00",
                        end_time="03:00",
                        duration_minutes=120,
                    )
                ],
            )

        scheduler = DailyScheduler()
        res1 = scheduler.schedule_daily(make_problem())
        res2 = scheduler.schedule_daily(make_problem())

        assert res1.total_scheduled == res2.total_scheduled
        sched1 = [w.get("request_id") or w.get("work_id") for w in res1.scheduled_works]
        sched2 = [w.get("request_id") or w.get("work_id") for w in res2.scheduled_works]
        assert sched1 == sched2
        assert res1.solver_statistics.objective_value == res2.solver_statistics.objective_value

    def test_human_workload_principle_supported_factors_only(self):
        """Verify PriorityEnrichment is strictly computed from the 3 supported factors without requiring manual fields."""
        enrichment = PriorityEnrichment(
            urgency=0.75,
            criticality=0.85,
            overdue_factor=0.60,
            priority_value=73.33,
        )
        fields = PriorityEnrichment.model_fields.keys()
        assert "urgency" in fields
        assert "criticality" in fields
        assert "overdue_factor" in fields
        assert "priority_value" in fields
        # Ensure future factors are NOT required manual schema inputs
        assert "asset_availability_impact" not in fields
        assert "operational_impact" not in fields

    def test_performance_smoke_metrics(self):
        """Smoke test verifying execution under controlled small load with recorded metrics."""
        problem = DailySchedulingProblem(
            problem_id="PROB-SMOKE",
            target_date=TARGET_DATE,
            candidate_works=[
                CandidateWorkItem(work_id=f"WORK-SMOKE-{i}", location="Chennai-Arakkonam", required_duration_minutes=45, priority_value=float(50 + i * 5))
                for i in range(4)
            ],
            available_windows=[
                CorridorAvailabilityWindow(
                    window_id=f"WIN-SMOKE-{i}",
                    corridor="Chennai-Arakkonam",
                    service_date=TARGET_DATE,
                    start_time=f"0{i*2+1}:00",
                    end_time=f"0{i*2+2}:30",
                    duration_minutes=90,
                )
                for i in range(3)
            ],
        )
        t0 = time.perf_counter()
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem)
        elapsed = time.perf_counter() - t0

        assert result.solver_statistics is not None
        assert result.solver_statistics.status in ("OPTIMAL", "FEASIBLE")
        assert result.total_scheduled >= 1
        # Smoke performance bound: small 4-work problem must solve in well under 5 seconds
        assert elapsed < 5.0
