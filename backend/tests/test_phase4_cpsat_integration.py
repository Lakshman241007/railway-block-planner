"""
Phase 4 Test Suite — Integrate Scheduler with CP-SAT.

Validates the full daily scheduling pipeline:
DailySchedulingProblem → DailyScheduler → OptimizationRequest → CP_SAT_Optimizer → DailyScheduleResult

Key Requirements Tested:
1. Successful Optimization: Full orchestration produces scheduled assignments and solver telemetry.
2. Multiple Candidate Blocks: Work items matching multiple windows preserve all candidate slot options for CP-SAT.
3. Infeasible Problem: Infeasible constraints yield INFEASIBLE status, zero fake scheduled blocks, and clear diagnostics.
4. Solver Diagnostics & Telemetry: Unscheduled works distinguish pre-solver rejections from solver unassigned works.
5. Priority & Priority Value: Existing priority levels and priority_value pass through directly without AI/ML.
6. Hard Constraints: Capacity limits and non-overlap constraints are strictly enforced by the CP-SAT solver.
7. Architectural Boundary: Daily scheduling path is Scheduler → CP-SAT, completely decoupled from BlockPlanner CP-SAT calls.
8. Pre-Solver Diagnostic Mode: invoke_solver=False provides pre-solver inspection without invoking CP-SAT.
"""

from datetime import date, datetime, timezone
from typing import List
from unittest.mock import patch

import pytest

from backend.app.block_planner.schemas import (
    CandidateWorkItem,
    CorridorAvailabilityWindow,
    DailySchedulingProblem,
)
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
    OptimizedBlock,
    SolverStatistics,
)
from backend.app.scheduler.scheduler import DailyScheduler, MaintenanceScheduler
from backend.app.scheduler.schemas import (
    DailyAvailabilityReport,
    DailyScheduleResult,
    WorkMatchReport,
)
from backend.app.schemas.unified_data import Priority


@pytest.fixture
def target_date() -> date:
    return date(2026, 10, 15)


@pytest.fixture
def feasible_problem(target_date: date) -> DailySchedulingProblem:
    """
    Constructs a well-formed DailySchedulingProblem with multiple compatible candidates,
    allowing CP-SAT to mathematically find an optimal schedule.
    """
    candidate_works = [
        # Work 1: Critical track maintenance at Perambur, duration 120m
        CandidateWorkItem(
            work_id="WORK-CRIT-01",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=120,
            asset_id="TRK-MAS-01",
            asset_type="Track",
            priority=Priority.CRITICAL,
            priority_value=4.0,
            preferred_start="01:30",
            preferred_date=target_date,
            required_resources=2,
            is_mandatory=True,
        ),
        # Work 2: High priority track renewal at Arakkonam, duration 90m
        CandidateWorkItem(
            work_id="WORK-HIGH-02",
            location="Arakkonam",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=90,
            asset_id="TRK-AJJ-01",
            asset_type="Track",
            priority=Priority.HIGH,
            priority_value=3.0,
            preferred_start="02:00",
            preferred_date=target_date,
            required_resources=2,
        ),
        # Work 3: Incompatible candidate (duration exceeds available windows)
        CandidateWorkItem(
            work_id="WORK-TOO-LONG",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=480,  # Exceeds window length
            asset_id="TRK-MAS-99",
            asset_type="Track",
            priority=Priority.LOW,
            preferred_start="01:00",
            preferred_date=target_date,
            required_resources=2,
        ),
    ]

    available_windows = [
        # Window 1: Night window on Chennai-Arakkonam (01:00 to 05:00, 240 mins)
        CorridorAvailabilityWindow(
            window_id="WIN-MAS-AJJ-NIGHT",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="01:00",
            end_time="05:00",
            duration_minutes=240,
            status="Available",
            restrictions=[],
            capacity_info={"max_crew": 10},
            max_parallel_works=2,
        ),
        # Window 2: Secondary night window on Chennai-Arakkonam (02:00 to 04:30, 150 mins)
        CorridorAvailabilityWindow(
            window_id="WIN-MAS-AJJ-EARLY",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="02:00",
            end_time="04:30",
            duration_minutes=150,
            status="Available",
            restrictions=[],
            capacity_info={"max_crew": 8},
            max_parallel_works=2,
        ),
    ]

    return DailySchedulingProblem(
        problem_id="PROB-PHASE4-FEASIBLE",
        target_date=target_date,
        candidate_works=candidate_works,
        available_windows=available_windows,
        timetable_constraints=[],
        goods_train_forecast_windows=[],
        operational_restrictions=[],
        buffer_minutes=15,
        metadata={"source": "BlockPlanner", "horizon": "1 day"},
    )


class TestSuccessfulOptimizationPipeline:
    """Validates end-to-end schedule_daily() with CP-SAT solver invocation."""

    def test_schedule_daily_invokes_cpsat_and_populates_result(
        self, feasible_problem: DailySchedulingProblem
    ):
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(feasible_problem, invoke_solver=True)

        assert isinstance(result, DailyScheduleResult)
        assert result.plan_id.startswith("DSCHED-")
        assert result.target_date == feasible_problem.target_date

        # CP-SAT must have scheduled the feasible works
        assert result.total_scheduled >= 1
        assert len(result.optimized_block_assignments) == result.total_scheduled

        # Check solver statistics
        assert result.solver_statistics is not None
        assert isinstance(result.solver_statistics, SolverStatistics)
        assert result.solver_statistics.status in (
            OptimizationStatus.OPTIMAL,
            OptimizationStatus.FEASIBLE,
        )
        assert result.solver_statistics.objective_value is not None
        assert result.solver_statistics.objective_value > 0

        # Check optimization metadata
        assert result.optimization_metadata is not None
        assert result.optimization_metadata["status"] in ("OPTIMAL", "FEASIBLE")
        assert "optimization_request" in result.optimization_metadata
        assert "wall_time_seconds" in result.optimization_metadata

        # Mandatory critical work must be scheduled
        scheduled_req_ids = [b.request_id for b in result.optimized_block_assignments]
        assert "WORK-CRIT-01" in scheduled_req_ids


class TestMultipleCandidateBlocks:
    """Verifies that multiple candidate possibilities reach CP-SAT rather than being greedily locked."""

    def test_multiple_candidate_blocks_preserved_for_cpsat(self, target_date: date):
        # 1 candidate work that fits into Window 1, Window 2, and Window 3
        work = CandidateWorkItem(
            work_id="WORK-MULTI-SLOT",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority=Priority.HIGH,
            preferred_start="02:00",
            preferred_date=target_date,
            required_resources=2,
        )
        windows = [
            CorridorAvailabilityWindow(
                window_id="WIN-1-0100",
                corridor="Chennai-Arakkonam",
                service_date=target_date,
                start_time="01:00",
                end_time="03:00",
                duration_minutes=120,
                status="Available",
            ),
            CorridorAvailabilityWindow(
                window_id="WIN-2-0200",
                corridor="Chennai-Arakkonam",
                service_date=target_date,
                start_time="02:00",
                end_time="04:00",
                duration_minutes=120,
                status="Available",
            ),
            CorridorAvailabilityWindow(
                window_id="WIN-3-0300",
                corridor="Chennai-Arakkonam",
                service_date=target_date,
                start_time="03:00",
                end_time="05:00",
                duration_minutes=120,
                status="Available",
            ),
        ]
        problem = DailySchedulingProblem(
            problem_id="PROB-MULTI-CANDIDATES",
            target_date=target_date,
            candidate_works=[work],
            available_windows=windows,
        )

        scheduler = DailyScheduler()
        avail_report = scheduler.determine_daily_availability(problem)
        match_report = scheduler.match_work_to_blocks(problem.candidate_works, avail_report)

        # Work-to-block matching must find all 3 windows compatible
        matches = [m for m in match_report.successful_matches if m.work_id == "WORK-MULTI-SLOT"]
        assert len(matches) == 3
        matched_window_ids = {m.window_id for m in matches}
        assert matched_window_ids == {"WIN-1-0100", "WIN-2-0200", "WIN-3-0300"}

        # Build CP-SAT input
        opt_req = scheduler.build_cpsat_input(problem, match_report, avail_report)
        assert opt_req.candidate_matches is not None
        assert len(opt_req.candidate_matches) == 3

        # CP-SAT receives all 3 candidate slot variables and chooses the best one
        optimizer = CP_SAT_Optimizer()
        opt_res = optimizer.optimize(request=opt_req)

        assert opt_res.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(opt_res.scheduled_blocks) == 1
        # Because preferred_start is 02:00, CP-SAT's objective should pick WIN-2-0200 (start_time 02:00)
        chosen = opt_res.scheduled_blocks[0]
        assert chosen.start_time == "02:00"
        assert chosen.deviation_minutes == 0


class TestInfeasibleProblemHandling:
    """Verifies that infeasible problems return INFEASIBLE status without fake schedules."""

    def test_infeasible_problem_does_not_produce_fake_schedule(self, target_date: date):
        # Two MANDATORY works on the SAME section with identical duration in a window of parallel_works=1
        # and insufficient window duration to run both sequentially (sum of durations exceeds window).
        works = [
            CandidateWorkItem(
                work_id="WORK-MAND-A",
                location="Perambur",
                corridor="Chennai-Arakkonam",
                required_duration_minutes=100,
                priority=Priority.CRITICAL,
                preferred_start="01:00",
                preferred_date=target_date,
                is_mandatory=True,
            ),
            CandidateWorkItem(
                work_id="WORK-MAND-B",
                location="Perambur",
                corridor="Chennai-Arakkonam",
                required_duration_minutes=100,
                priority=Priority.CRITICAL,
                preferred_start="01:00",
                preferred_date=target_date,
                is_mandatory=True,
            ),
        ]
        # Only 1 single window of 120m (can fit either A or B, but NOT both mandatory works)
        windows = [
            CorridorAvailabilityWindow(
                window_id="WIN-TIGHT-SINGLE",
                corridor="Chennai-Arakkonam",
                section="Perambur",
                service_date=target_date,
                start_time="01:00",
                end_time="03:00",
                duration_minutes=120,
                status="Available",
                max_parallel_works=1,
            )
        ]
        problem = DailySchedulingProblem(
            problem_id="PROB-INFEASIBLE-TEST",
            target_date=target_date,
            candidate_works=works,
            available_windows=windows,
        )

        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem, invoke_solver=True)

        assert isinstance(result, DailyScheduleResult)
        assert result.total_scheduled == 0
        assert len(result.optimized_block_assignments) == 0
        assert len(result.scheduled_works) == 0

        # Status must reflect infeasibility
        assert result.solver_statistics is not None
        assert result.solver_statistics.status == OptimizationStatus.INFEASIBLE
        assert result.optimization_metadata["status"] == "INFEASIBLE"
        assert "infeasibility_explanation" in result.optimization_metadata


class TestUnscheduledWorkDiagnostics:
    """Verifies that unscheduled diagnostics distinguish matching rejections from CP-SAT preemption."""

    def test_distinguishes_matching_rejection_from_solver_unassigned(
        self, feasible_problem: DailySchedulingProblem
    ):
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(feasible_problem, invoke_solver=True)

        # WORK-TOO-LONG should be in unscheduled_works with source 'PreSolverMatching'
        too_long_item = next(
            (u for u in result.unscheduled_works if u.get("work_id") == "WORK-TOO-LONG"),
            None,
        )
        assert too_long_item is not None
        assert too_long_item["source"] == "PreSolverMatching"
        assert any("Insufficient duration" in r for r in too_long_item.get("rejection_reasons", []))

        # Diagnostics counters
        assert result.diagnostics["pre_solver_rejected_count"] >= 1
        assert "solver_status" in result.diagnostics


class TestPriorityPreservation:
    """Verifies that priorities and priority_values reach CP-SAT without AI intervention."""

    def test_priorities_and_numeric_values_reach_cpsat(self, feasible_problem: DailySchedulingProblem):
        scheduler = DailyScheduler()
        avail = scheduler.determine_daily_availability(feasible_problem)
        match = scheduler.match_work_to_blocks(feasible_problem.candidate_works, avail)
        opt_req = scheduler.build_cpsat_input(feasible_problem, match, avail)

        # Check priority_overrides passed to OptimizationRequest
        assert opt_req.priority_overrides is not None
        # WORK-CRIT-01 had priority_value=4.0
        assert opt_req.priority_overrides["WORK-CRIT-01"] == "4.0"
        # WORK-HIGH-02 had priority_value=3.0
        assert opt_req.priority_overrides["WORK-HIGH-02"] == "3.0"

        # Solve and verify scheduled blocks preserve original priorities
        result = scheduler.schedule_daily(feasible_problem, invoke_solver=True)
        crit_block = next(
            (b for b in result.optimized_block_assignments if b.request_id == "WORK-CRIT-01"),
            None,
        )
        assert crit_block is not None
        assert crit_block.priority == Priority.CRITICAL


class TestHardConstraints:
    """Verifies CP-SAT enforces non-overlap and capacity constraints in scheduled results."""

    def test_track_overlap_hard_constraint_enforced(self, target_date: date):
        # Two non-mandatory works on the exact same track section Perambur at the same time
        works = [
            CandidateWorkItem(
                work_id="WORK-A",
                location="Perambur",
                corridor="Chennai-Arakkonam",
                required_duration_minutes=90,
                priority=Priority.HIGH,
                preferred_start="01:00",
                preferred_date=target_date,
            ),
            CandidateWorkItem(
                work_id="WORK-B",
                location="Perambur",
                corridor="Chennai-Arakkonam",
                required_duration_minutes=90,
                priority=Priority.MEDIUM,
                preferred_start="01:00",
                preferred_date=target_date,
            ),
        ]
        # Single window of 120m on Perambur: only one 90m work can fit without overlap
        windows = [
            CorridorAvailabilityWindow(
                window_id="WIN-PERAMBUR-120",
                corridor="Chennai-Arakkonam",
                section="Perambur",
                service_date=target_date,
                start_time="01:00",
                end_time="03:00",
                duration_minutes=120,
                status="Available",
                max_parallel_works=1,
            )
        ]
        problem = DailySchedulingProblem(
            problem_id="PROB-OVERLAP-TEST",
            target_date=target_date,
            candidate_works=works,
            available_windows=windows,
        )

        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(problem, invoke_solver=True)

        assert result.total_scheduled == 1
        # Higher-priority WORK-A should be scheduled, WORK-B unscheduled due to track contention
        sched_ids = [b.request_id for b in result.optimized_block_assignments]
        assert "WORK-A" in sched_ids
        assert "WORK-B" not in sched_ids


class TestArchitecturalBoundary:
    """
    Verifies that the new daily scheduling flow executes through:
    DailyScheduler → CP_SAT_Optimizer
    and does NOT call BlockPlanner.optimize_plan().
    """

    def test_scheduler_orchestrates_cpsat_directly(
        self, feasible_problem: DailySchedulingProblem
    ):
        scheduler = DailyScheduler()

        with patch("backend.app.block_planner.planner.BlockPlanner.optimize_plan") as mock_bp_opt:
            result = scheduler.schedule_daily(feasible_problem, invoke_solver=True)
            assert isinstance(result, DailyScheduleResult)
            # BlockPlanner.optimize_plan MUST NOT be called in the new daily flow
            mock_bp_opt.assert_not_called()

    def test_pre_solver_diagnostic_mode_does_not_invoke_cpsat(
        self, feasible_problem: DailySchedulingProblem
    ):
        scheduler = DailyScheduler()

        with patch("backend.app.optimizer.cp_sat_optimizer.CP_SAT_Optimizer.optimize") as mock_opt:
            result = scheduler.schedule_daily(feasible_problem, invoke_solver=False)
            assert isinstance(result, DailyScheduleResult)
            assert result.total_scheduled == 0
            assert result.optimization_metadata["status"] == "PreparedForOptimization"
            # CP-SAT solver MUST NOT be called when invoke_solver=False
            mock_opt.assert_not_called()
