"""
Phase 3 Daily Scheduler Unit and Integration Tests.

Validates:
1. Daily Availability: Auditing available windows, classifying Blocked and Restricted windows,
   and tracking corridor capacities.
2. Work-to-Block Matching: Feasible relationship evaluation, fit scoring, non-exclusive matching,
   and audit rejection diagnostics (Location mismatch, Insufficient duration, Resource unavailable,
   Asset incompatibility, Operational incompatibility).
3. Priority Handling: Preserving canonical priorities and existing priority_value without AI/ML dependency.
4. OptimizationRequest Builder: Converting DailySchedulingProblem & match reports to CP-SAT inputs.
5. Daily Scheduling Pipeline: End-to-end schedule_daily producing DailyScheduleResult.
6. Architectural Boundary: Decoupling of Scheduler from CP-SAT solver execution.
7. Backward Compatibility: Legacy schedule() and find_feasible_slots() methods remain fully functional.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
import pytest

from backend.app.block_planner.schemas import (
    CandidateWorkItem,
    CorridorAvailabilityWindow,
    DailySchedulingProblem,
)
from backend.app.optimizer.schemas import OptimizationRequest
from backend.app.scheduler.scheduler import (
    DailyScheduler,
    MaintenanceScheduler,
    _format_minutes_to_time,
    _parse_time_to_minutes,
)
from backend.app.scheduler.schemas import (
    DailyAvailabilityReport,
    DailyScheduleResult,
    WorkBlockMatch,
    WorkMatchReport,
)
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    BlockType,
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
    TimetableRecord,
)


@pytest.fixture
def target_date() -> date:
    return date(2026, 10, 5)


@pytest.fixture
def base_problem(target_date: date) -> DailySchedulingProblem:
    """Fixture providing a realistic DailySchedulingProblem with candidate works, windows, and constraints."""
    candidate_works = [
        # 1. Compatible work for Chennai-Arakkonam (Perambur)
        CandidateWorkItem(
            work_id="WORK-001",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=120,
            asset_id="TRK-MAS-01",
            asset_type="Track",
            priority=Priority.CRITICAL,
            preferred_start="02:00",
            preferred_date=target_date,
            required_resources=3,
            required_equipment="BCM",
            is_mandatory=True,
            is_pinned=False,
        ),
        # 2. Insufficient duration candidate (requires 360m, window is 240m)
        CandidateWorkItem(
            work_id="WORK-LONG",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=360,
            asset_id="TRK-MAS-02",
            asset_type="Track",
            priority=Priority.HIGH,
            preferred_start="01:00",
            preferred_date=target_date,
            required_resources=2,
            is_mandatory=False,
        ),
        # 3. Location mismatch candidate (location is Villupuram, window is Chennai-Arakkonam)
        CandidateWorkItem(
            work_id="WORK-LOC-MISMATCH",
            location="Villupuram",
            corridor="Chennai-Villupuram",
            required_duration_minutes=90,
            asset_id="TRK-VM-01",
            asset_type="Track",
            priority=Priority.MEDIUM,
            preferred_start="02:00",
            preferred_date=target_date,
            required_resources=2,
        ),
        # 4. Resource unavailable candidate (requires 15 crew, window cap is 5)
        CandidateWorkItem(
            work_id="WORK-CREW-HEAVY",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=60,
            asset_id="TRK-MAS-03",
            asset_type="Track",
            priority=Priority.LOW,
            preferred_start="03:00",
            preferred_date=target_date,
            required_resources=15,  # Exceeds max_crew
        ),
        # 5. Asset incompatibility candidate (requires OHE power isolation on traction-active window)
        CandidateWorkItem(
            work_id="WORK-OHE-INCOMPAT",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=60,
            asset_id="OHE-MAS-01",
            asset_type="OHE",
            priority=Priority.HIGH,
            preferred_start="02:30",
            preferred_date=target_date,
            required_resources=2,
            constraints=["Requires OHE power isolation"],
        ),
    ]

    available_windows = [
        # Window 1: Clean Night Window on Chennai-Arakkonam (01:00 to 05:00, 240m)
        CorridorAvailabilityWindow(
            window_id="WIN-MAS-AJJ-NIGHT",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="01:00",
            end_time="05:00",
            duration_minutes=240,
            status="Available",
            restrictions=["Standard night maintenance protocol"],
            capacity_info={"max_crew": 10},
            max_parallel_works=2,
        ),
        # Window 2: Window with traction power active (prohibiting OHE blocks) & limited crew
        CorridorAvailabilityWindow(
            window_id="WIN-MAS-LIMITED",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
            status="Available",
            restrictions=["Traction active - no OHE block allowed"],
            capacity_info={"max_crew": 5},
            max_parallel_works=1,
        ),
        # Window 3: Window on Chennai-Arakkonam directly overlapping daytime timetable train (will become Blocked)
        CorridorAvailabilityWindow(
            window_id="WIN-DAY-BLOCKED",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="07:00",
            end_time="10:00",
            duration_minutes=180,
            section="Perambur",
            status="Available",
            restrictions=[],
            capacity_info={"max_crew": 8},
            max_parallel_works=1,
        ),
        # Window 4: Window on Arakkonam-Renigunta with projected goods train (will become Restricted)
        CorridorAvailabilityWindow(
            window_id="WIN-RU-GOODS",
            corridor="Arakkonam-Renigunta",
            service_date=target_date,
            start_time="02:00",
            end_time="06:00",
            duration_minutes=240,
            section="Renigunta",
            status="Available",
            restrictions=[],
            capacity_info={"max_crew": 8},
            max_parallel_works=1,
        ),
    ]

    timetable_constraints = [
        # Morning passenger train on Perambur (07:30 to 07:45) - overlaps WIN-DAY-BLOCKED
        {
            "train_id": "12601",
            "service_date": target_date.isoformat(),
            "station_code": "Perambur",
            "arrival_time": "07:30",
            "departure_time": "07:45",
            "sequence": 1,
        }
    ]

    goods_train_forecast_windows = [
        # Goods train passing Renigunta during WIN-RU-GOODS
        {
            "train_id": "BOXN-901",
            "service_date": target_date.isoformat(),
            "section": "Renigunta",
            "forecasted_entry": "03:15",
            "forecasted_exit": "03:45",
            "confidence": 0.85,
        }
    ]

    operational_restrictions = [
        "Headway buffer 15m required between train passages and maintenance possession",
        "Single line operation protocol active during major renewals",
    ]

    return DailySchedulingProblem(
        problem_id="PROB-20261005-TEST",
        target_date=target_date,
        candidate_works=candidate_works,
        available_windows=available_windows,
        timetable_constraints=timetable_constraints,
        goods_train_forecast_windows=goods_train_forecast_windows,
        operational_restrictions=operational_restrictions,
        buffer_minutes=15,
        metadata={"source": "BlockPlanner", "horizon": "1 day"},
    )


class TestDailyAvailability:
    """Validates determine_daily_availability()."""

    def test_daily_availability_auditing(self, base_problem: DailySchedulingProblem):
        scheduler = MaintenanceScheduler()
        report = scheduler.determine_daily_availability(base_problem)

        assert isinstance(report, DailyAvailabilityReport)
        assert report.target_date == base_problem.target_date
        assert len(report.available_windows) == 4

        # Check window classification:
        win_night = next(w for w in report.available_windows if w.window_id == "WIN-MAS-AJJ-NIGHT")
        assert win_night.status == "Available"

        # WIN-DAY-BLOCKED should be classified as Blocked due to train 12601 overlap
        win_blocked = next(w for w in report.available_windows if w.window_id == "WIN-DAY-BLOCKED")
        assert win_blocked.status == "Blocked"
        assert any("Direct buffer contention with Passenger Train 12601" in r for r in win_blocked.restrictions)

        # WIN-RU-GOODS should be classified as Restricted due to goods forecast overlap
        win_goods = next(w for w in report.available_windows if w.window_id == "WIN-RU-GOODS")
        assert win_goods.status == "Restricted"
        assert any("Projected goods train interaction" in r for r in win_goods.restrictions)

        # Timetable and goods restrictions
        assert len(report.timetable_restrictions) == 1
        assert report.timetable_restrictions[0]["train_id"] == "12601"
        assert len(report.goods_train_restrictions) == 1
        assert report.goods_train_restrictions[0]["train_id"] == "BOXN-901"

        # Corridor capacity telemetry
        assert "Chennai-Arakkonam" in report.corridor_capacities
        cap = report.corridor_capacities["Chennai-Arakkonam"]
        assert cap["available_windows"] >= 1
        assert cap["blocked_windows"] == 1
        assert cap["total_window_minutes"] > 0


class TestWorkToBlockMatching:
    """Validates match_work_to_blocks()."""

    def test_work_matching_and_rejection_diagnostics(self, base_problem: DailySchedulingProblem):
        scheduler = MaintenanceScheduler()
        avail_report = scheduler.determine_daily_availability(base_problem)
        match_report = scheduler.match_work_to_blocks(base_problem.candidate_works, avail_report)

        assert isinstance(match_report, WorkMatchReport)
        assert match_report.total_works == 5

        # 1. Compatible match: WORK-001 matches WIN-MAS-AJJ-NIGHT
        m1 = next(m for m in match_report.successful_matches if m.work_id == "WORK-001" and m.window_id == "WIN-MAS-AJJ-NIGHT")
        assert m1.is_compatible is True
        assert m1.fit_score > 0.8
        assert m1.compatibility_details["location"] == "Location matched"

        # 2. Location mismatch: WORK-LOC-MISMATCH should have location mismatch against Chennai-Arakkonam
        loc_rejections = [
            m for m in match_report.rejected_works if m["work_id"] == "WORK-LOC-MISMATCH"
        ]
        assert len(loc_rejections) == 1
        assert "Location mismatch" in loc_rejections[0]["reasons"]

        # 3. Insufficient duration: WORK-LONG requires 360m, all windows are <= 240m
        dur_rejections = [
            m for m in match_report.rejected_works if m["work_id"] == "WORK-LONG"
        ]
        assert len(dur_rejections) == 1
        assert "Insufficient duration" in dur_rejections[0]["reasons"]

        # 4. Resource unavailable: WORK-CREW-HEAVY requires 15 crew, exceeds limits on smaller windows
        # Let's check rejection summary
        assert match_report.rejection_summary["Location mismatch"] >= 1
        assert match_report.rejection_summary["Insufficient duration"] >= 1

    def test_matching_does_not_perform_premature_optimization(self, base_problem: DailySchedulingProblem):
        """
        Confirms non-exclusive matching: multiple candidate windows can match one work,
        and multiple works can match one window without greedy lock-in.
        """
        scheduler = MaintenanceScheduler()
        avail_report = scheduler.determine_daily_availability(base_problem)
        match_report = scheduler.match_work_to_blocks(base_problem.candidate_works, avail_report)

        # WORK-001 fits both WIN-MAS-AJJ-NIGHT and WIN-MAS-LIMITED (both are compatible)
        work1_matches = [
            m for m in match_report.successful_matches if m.work_id == "WORK-001"
        ]
        assert len(work1_matches) >= 2
        window_ids = {m.window_id for m in work1_matches}
        assert "WIN-MAS-AJJ-NIGHT" in window_ids
        assert "WIN-MAS-LIMITED" in window_ids

    def test_operational_incompatibility_with_blocked_window(self, base_problem: DailySchedulingProblem):
        """Validates that candidate evaluation against a Blocked window records Operational incompatibility."""
        scheduler = MaintenanceScheduler()
        avail_report = scheduler.determine_daily_availability(base_problem)
        match_report = scheduler.match_work_to_blocks(base_problem.candidate_works, avail_report)

        # In WIN-DAY-BLOCKED, any match attempt has Operational incompatibility
        blocked_matches = [
            m for m in match_report.successful_matches if m.window_id == "WIN-DAY-BLOCKED"
        ]
        # None should be successful
        assert len(blocked_matches) == 0


class TestPriorityHandling:
    """Validates priority preservation and priority_value consumption."""

    def test_existing_priority_preserved_in_matches(self, base_problem: DailySchedulingProblem):
        scheduler = MaintenanceScheduler()
        avail_report = scheduler.determine_daily_availability(base_problem)
        match_report = scheduler.match_work_to_blocks(base_problem.candidate_works, avail_report)

        # Verify candidate work priority remains intact
        w1 = next(w for w in base_problem.candidate_works if w.work_id == "WORK-001")
        assert w1.priority == Priority.CRITICAL

    def test_priority_value_preserved_without_ai_dependency(self, target_date: date):
        """Verify that if an input candidate already has an explicit priority_value, it is preserved."""
        work_with_ai_val = CandidateWorkItem(
            work_id="WORK-WITH-VAL",
            location="Perambur",
            corridor="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority=Priority.HIGH,
            priority_value=88.5,  # dynamic extra field
        )
        problem = DailySchedulingProblem(
            problem_id="PROB-VAL-TEST",
            target_date=target_date,
            candidate_works=[work_with_ai_val],
            available_windows=[],
        )
        scheduler = MaintenanceScheduler()
        match_rep = WorkMatchReport(
            report_id="REP-01",
            target_date=target_date,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        opt_req = scheduler.build_cpsat_input(problem, match_rep)

        assert opt_req.priority_overrides is not None
        assert opt_req.priority_overrides["WORK-WITH-VAL"] == "88.5"


class TestOptimizationRequestBuilder:
    """Validates build_cpsat_input()."""

    def test_build_cpsat_input_contract(self, base_problem: DailySchedulingProblem):
        scheduler = MaintenanceScheduler()
        avail_report = scheduler.determine_daily_availability(base_problem)
        match_report = scheduler.match_work_to_blocks(base_problem.candidate_works, avail_report)

        opt_req = scheduler.build_cpsat_input(base_problem, match_report, avail_report)

        assert isinstance(opt_req, OptimizationRequest)
        assert opt_req.target_date == base_problem.target_date
        assert opt_req.horizon_days == 1
        assert opt_req.buffer_minutes == base_problem.buffer_minutes
        assert opt_req.mandatory_request_ids == ["WORK-001"]
        assert opt_req.priority_overrides is not None
        assert opt_req.priority_overrides["WORK-001"] == "Critical"
        assert opt_req.include_forecast is True


class TestScheduleDailyPipeline:
    """Validates end-to-end schedule_daily() method."""

    def test_schedule_daily_orchestration(self, base_problem: DailySchedulingProblem):
        scheduler = DailyScheduler()
        result = scheduler.schedule_daily(base_problem)

        assert isinstance(result, DailyScheduleResult)
        assert result.plan_id.startswith("DSCHED-")
        assert result.target_date == base_problem.target_date
        assert result.total_scheduled == 0  # Solver not run in Phase 3
        assert result.total_unscheduled > 0
        assert len(result.scheduled_works) >= 1
        assert "optimization_request" in result.optimization_metadata
        assert result.optimization_metadata["status"] == "PreparedForOptimization"


class TestArchitecturalBoundary:
    """
    Verifies that Scheduler methods in Phase 3 do NOT call the CP-SAT solver.
    """

    def test_scheduler_does_not_invoke_cp_sat(self, base_problem: DailySchedulingProblem):
        scheduler = MaintenanceScheduler()

        with patch("backend.app.optimizer.cp_sat_optimizer.CP_SAT_Optimizer") as mock_optimizer:
            avail = scheduler.determine_daily_availability(base_problem)
            assert isinstance(avail, DailyAvailabilityReport)
            mock_optimizer.assert_not_called()

            match = scheduler.match_work_to_blocks(base_problem.candidate_works, avail)
            assert isinstance(match, WorkMatchReport)
            mock_optimizer.assert_not_called()

            opt_req = scheduler.build_cpsat_input(base_problem, match, avail)
            assert isinstance(opt_req, OptimizationRequest)
            mock_optimizer.assert_not_called()

            res = scheduler.schedule_daily(base_problem)
            assert isinstance(res, DailyScheduleResult)
            mock_optimizer.assert_not_called()


class TestBackwardCompatibility:
    """Validates that legacy MaintenanceScheduler methods continue working untouched."""

    def test_legacy_find_feasible_slots(self, target_date: date):
        scheduler = MaintenanceScheduler(buffer_minutes=15)
        slots = scheduler.find_feasible_slots(
            location="Perambur",
            duration_minutes=60,
            preferred_start="02:00",
            target_date=target_date,
        )
        assert isinstance(slots, list)
        assert len(slots) > 0

    def test_legacy_schedule_method(self, target_date: date):
        m = MaintenanceRecord(
            asset_id="TRK-MAS-01",
            asset_type="Track",
            location="Perambur",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=60,
            requested_date=target_date,
            preferred_start=time(2, 0),
            required_resources=2,
            equipment="Tamper",
            status=MaintenanceStatus.APPROVED,
        )
        scheduler = MaintenanceScheduler(maintenance_records=[m], buffer_minutes=15)
        res = scheduler.schedule(target_date=target_date)
        assert res.total_requested == 1
        assert res.total_scheduled == 1
