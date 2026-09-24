"""
Phase 2 Block Planner Unit and Integration Tests.

Validates the refactored BlockPlanner:
1. Monthly Planning: 30-day horizon, week buckets (1-5), corridor summaries, priority & asset preservation.
2. Weekly Planning: 7-day horizon, target date organization, constraints, daily breakdown.
3. Daily Problem Preparation: CandidateWorkItem generation, corridor availability windows,
   timetable constraints, goods train forecast windows, buffer/headway rules.
4. Architectural Boundary: Decoupling of BlockPlanner from CP-SAT mathematical optimization.
5. Backward Compatibility: Legacy facade methods (generate_plan, optimize_plan) continue to work.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from unittest.mock import patch
import pytest

from backend.app.block_planner.planner import BlockPlanner, _resolve_corridor
from backend.app.block_planner.schemas import (
    BlockPlanRequest,
    BlockPlanResult,
    CandidateWorkItem,
    CorridorAvailabilityWindow,
    DailySchedulingProblem,
    MonthlyPlan,
    MonthlyPlanItem,
    WeeklyPlan,
    WeeklyPlanItem,
)
from backend.app.forecast.schemas import GoodsForecastItem
from backend.app.optimizer.schemas import OptimizationRequest, OptimizationResult
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


@pytest.fixture
def base_date() -> date:
    return date(2026, 10, 1)


@pytest.fixture
def sample_data(base_date: date):
    """Fixture providing maintenance records and blocks spanning a 30-day horizon."""
    records = [
        # Week 1 (Day 0, Day 5)
        MaintenanceRecord(
            asset_id="TRK-MAS-01",
            asset_type="Track",
            location="Perambur",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.CRITICAL,
            duration_minutes=180,
            requested_date=base_date,  # Day 0 -> Week 1
            preferred_start=time(2, 0),
            required_resources=4,
            equipment="BCM Machine",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        MaintenanceRecord(
            asset_id="SIG-AJJ-02",
            asset_type="Signal",
            location="Arakkonam",
            maintenance_type="Inspection",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=90,
            requested_date=base_date + timedelta(days=5),  # Day 5 -> Week 1
            preferred_start=time(3, 30),
            required_resources=2,
            equipment="Signal Rig",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        # Week 2 (Day 8)
        MaintenanceRecord(
            asset_id="TRK-RU-03",
            asset_type="Track",
            location="Renigunta",
            maintenance_type="Repair",
            maintenance_required=True,
            priority=Priority.MEDIUM,
            duration_minutes=120,
            requested_date=base_date + timedelta(days=8),  # Day 8 -> Week 2
            preferred_start=time(1, 0),
            required_resources=3,
            equipment="Tamper",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        # Week 3 (Day 15)
        MaintenanceRecord(
            asset_id="OHE-TBM-04",
            asset_type="OHE",
            location="Tambaram",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.LOW,
            duration_minutes=60,
            requested_date=base_date + timedelta(days=15),  # Day 15 -> Week 3
            preferred_start=time(4, 0),
            required_resources=2,
            equipment="Tower Wagon",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        # Week 4 (Day 22)
        MaintenanceRecord(
            asset_id="BRG-CGL-05",
            asset_type="Bridge",
            location="Chengalpattu",
            maintenance_type="Inspection",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=240,
            requested_date=base_date + timedelta(days=22),  # Day 22 -> Week 4
            preferred_start=time(1, 30),
            required_resources=5,
            equipment="Bridge Inspection Unit",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        # Week 5 (Day 29)
        MaintenanceRecord(
            asset_id="TRK-VM-06",
            asset_type="Track",
            location="Villupuram",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.MEDIUM,
            duration_minutes=150,
            requested_date=base_date + timedelta(days=29),  # Day 29 -> Week 5
            preferred_start=time(2, 30),
            required_resources=3,
            equipment="BCM Machine",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        # Outside horizon (Day 35) - should be ignored
        MaintenanceRecord(
            asset_id="TRK-OUT-07",
            asset_type="Track",
            location="Perambur",
            maintenance_type="Repair",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=120,
            requested_date=base_date + timedelta(days=35),
            preferred_start=time(1, 0),
            required_resources=2,
            equipment="Tamper",
            status=MaintenanceStatus.APPROVED,
            source="smms",
        ),
        # Not required - should be ignored
        MaintenanceRecord(
            asset_id="TRK-NOT-REQ",
            asset_type="Track",
            location="Perambur",
            maintenance_type="Repair",
            maintenance_required=False,
            priority=Priority.LOW,
            duration_minutes=60,
            requested_date=base_date,
            preferred_start=time(1, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.CANCELLED,
            source="smms",
        ),
    ]

    blocks = [
        # Approved Block in Week 1 (Day 2)
        BlockRecord(
            block_id="BLK-001",
            location="Perambur",
            block_type=BlockType.MAINTENANCE,
            requested_date=base_date + timedelta(days=2),  # Day 2 -> Week 1
            requested_start="01:30",
            requested_end="04:30",
            reason="Track Renewal",
            priority=Priority.CRITICAL,
            status=BlockStatus.APPROVED,
        ),
        # Cancelled block - should be ignored
        BlockRecord(
            block_id="BLK-CANCELLED",
            location="Renigunta",
            block_type=BlockType.TRAFFIC,
            requested_date=base_date + timedelta(days=3),
            requested_start="02:00",
            requested_end="04:00",
            reason="Cancelled Work",
            priority=Priority.LOW,
            status=BlockStatus.CANCELLED,
        ),
    ]

    timetables = [
        TimetableRecord(
            train_id="12601",
            service_date=base_date,
            station_code="PER",
            arrival_time="00:45",
            departure_time="00:50",
            sequence=1,
        ),
        TimetableRecord(
            train_id="12602",
            service_date=base_date,
            station_code="AJJ",
            arrival_time="05:15",
            departure_time="05:20",
            sequence=2,
        ),
    ]

    trains = [
        TrainRecord(
            train_id="12601",
            train_type="Passenger",
            origin="MAS",
            destination="MAQ",
            status=TrainStatus.SCHEDULED,
        )
    ]

    return {
        "records": records,
        "blocks": blocks,
        "timetables": timetables,
        "trains": trains,
    }


class TestCorridorResolution:
    """Validates corridor normalization helper."""

    def test_resolve_corridor_aliases(self):
        assert _resolve_corridor("Perambur") == "Chennai-Arakkonam"
        assert _resolve_corridor("Arakkonam") == "Chennai-Arakkonam"
        assert _resolve_corridor("Renigunta") == "Arakkonam-Renigunta"
        assert _resolve_corridor("Tambaram") == "Chennai-Villupuram"
        assert _resolve_corridor("Villupuram") == "Chennai-Villupuram"

    def test_resolve_unknown_corridor(self):
        assert _resolve_corridor("Katpadi Yard") == "Katpadi Yard"
        assert _resolve_corridor("") == "Unknown-Corridor"


class TestMonthlyPlanning:
    """Validates BlockPlanner.generate_monthly_plan()."""

    def test_monthly_plan_generation_30_day_horizon(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )

        monthly_plan = planner.generate_monthly_plan(target_date=base_date, horizon_days=30)

        assert isinstance(monthly_plan, MonthlyPlan)
        assert monthly_plan.plan_id.startswith("MPLAN-")
        assert monthly_plan.planning_month == "2026-10"
        assert monthly_plan.start_date == base_date
        assert monthly_plan.end_date == base_date + timedelta(days=30)
        assert monthly_plan.horizon_days == 30

        # Total items: 6 active maintenance records + 1 approved block = 7 items
        # (Excludes TRK-OUT-07 outside 30 days, TRK-NOT-REQ not required, BLK-CANCELLED cancelled)
        assert monthly_plan.total_items == 7
        assert len(monthly_plan.items) == 7

        # Total maintenance volume: 180 + 90 + 120 + 60 + 240 + 150 (records) + 180 (block) = 1020 mins
        assert monthly_plan.total_maintenance_volume == 1020

    def test_week_bucket_partitioning(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )

        plan = planner.generate_monthly_plan(target_date=base_date, horizon_days=30)

        # Check weekly breakdown structure
        wb = plan.weekly_breakdown
        assert "Week 1" in wb
        assert "Week 2" in wb
        assert "Week 3" in wb
        assert "Week 4" in wb
        assert "Week 5" in wb

        # Week 1: TRK-MAS-01 (day 0), BLK-001 (day 2), SIG-AJJ-02 (day 5) -> 3 items
        assert wb["Week 1"]["items_count"] == 3
        # Week 2: TRK-RU-03 (day 8) -> 1 item
        assert wb["Week 2"]["items_count"] == 1
        # Week 3: OHE-TBM-04 (day 15) -> 1 item
        assert wb["Week 3"]["items_count"] == 1
        # Week 4: BRG-CGL-05 (day 22) -> 1 item
        assert wb["Week 4"]["items_count"] == 1
        # Week 5: TRK-VM-06 (day 29) -> 1 item
        assert wb["Week 5"]["items_count"] == 1

        # Check that each item in plan.items has valid week_bucket in 1..5
        for item in plan.items:
            assert 1 <= item.week_bucket <= 5

    def test_monthly_plan_preserves_attributes(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )
        plan = planner.generate_monthly_plan(target_date=base_date, horizon_days=30)

        # Find the critical item
        crit_item = next(it for it in plan.items if it.asset_id == "TRK-MAS-01")
        assert crit_item.priority == Priority.CRITICAL
        assert crit_item.estimated_duration_minutes == 180
        assert crit_item.corridor == "Chennai-Arakkonam"
        assert crit_item.location == "Perambur"
        assert crit_item.required_resources == 4
        assert crit_item.equipment == "BCM Machine"
        assert crit_item.maintenance_type == "Preventive"

    def test_monthly_plan_corridor_summaries(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )
        plan = planner.generate_monthly_plan(target_date=base_date, horizon_days=30)

        summaries = plan.corridor_summaries
        assert "Chennai-Arakkonam" in summaries
        assert summaries["Chennai-Arakkonam"]["items_count"] >= 2
        assert summaries["Chennai-Arakkonam"]["duration_minutes"] > 0


class TestWeeklyPlanning:
    """Validates BlockPlanner.generate_weekly_plan()."""

    def test_weekly_plan_generation_7_day_horizon(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )

        weekly_plan = planner.generate_weekly_plan(target_date=base_date, horizon_days=7)

        assert isinstance(weekly_plan, WeeklyPlan)
        assert weekly_plan.plan_id.startswith("WPLAN-")
        assert weekly_plan.start_date == base_date
        assert weekly_plan.end_date == base_date + timedelta(days=7)
        assert weekly_plan.horizon_days == 7

        # Items in Week 1 (within [base_date, base_date + 7)):
        # TRK-MAS-01 (Day 0), BLK-001 (Day 2), SIG-AJJ-02 (Day 5) = 3 items
        assert weekly_plan.total_items == 3
        assert len(weekly_plan.items) == 3

        # Day breakdown
        assert len(weekly_plan.daily_breakdown) == 3

    def test_weekly_plan_preserves_constraints_and_priority(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )
        weekly_plan = planner.generate_weekly_plan(target_date=base_date, horizon_days=7)

        crit_work = next(it for it in weekly_plan.items if it.asset_id == "TRK-MAS-01")
        assert crit_work.priority == Priority.CRITICAL
        assert crit_work.is_mandatory is True
        assert crit_work.preferred_start == "02:00"
        assert crit_work.target_date == base_date
        assert "Requires BCM Machine" in crit_work.constraints


class TestDailyProblemPreparation:
    """Validates BlockPlanner.prepare_daily_problem()."""

    def test_daily_problem_preparation_contracts(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
            timetables=sample_data["timetables"],
            trains=sample_data["trains"],
        )

        problem = planner.prepare_daily_problem(
            target_date=base_date,
            buffer_minutes=15,
            include_forecast=False,
        )

        assert isinstance(problem, DailySchedulingProblem)
        assert problem.problem_id.startswith("PROB-")
        assert problem.target_date == base_date
        assert problem.buffer_minutes == 15

        # On base_date, we have TRK-MAS-01
        assert len(problem.candidate_works) == 1
        c_work = problem.candidate_works[0]
        assert isinstance(c_work, CandidateWorkItem)
        assert c_work.work_id == "MNT-TRK-MAS-01"
        assert c_work.location == "Perambur"
        assert c_work.priority == Priority.CRITICAL
        assert c_work.required_duration_minutes == 180
        assert c_work.is_mandatory is True

        # Available windows
        assert len(problem.available_windows) >= 1
        win = problem.available_windows[0]
        assert isinstance(win, CorridorAvailabilityWindow)
        assert win.service_date == base_date
        assert win.duration_minutes > 0

        # Timetable constraints
        assert len(problem.timetable_constraints) >= 1
        assert problem.timetable_constraints[0]["train_id"] == "12601"

        # Operational restrictions
        assert len(problem.operational_restrictions) >= 1

    def test_daily_problem_filtering(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
        )

        # Filter by priority Medium on base_date (TRK-MAS-01 is Critical)
        problem = planner.prepare_daily_problem(
            target_date=base_date,
            priority_filter="Medium",
            include_forecast=False,
        )
        assert len(problem.candidate_works) == 0

        # Filter by location Perambur on base_date
        prob_perambur = planner.prepare_daily_problem(
            target_date=base_date,
            location_filter="Perambur",
            include_forecast=False,
        )
        assert len(prob_perambur.candidate_works) == 1


class TestArchitecturalBoundary:
    """
    Verifies that the new BlockPlanner planning methods are strictly decoupled
    from CP-SAT mathematical optimization.
    """

    def test_new_planning_methods_do_not_invoke_cp_sat(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
            timetables=sample_data["timetables"],
        )

        # Mock CP_SAT_Optimizer to verify it is NEVER called by monthly, weekly, or daily problem preparation
        with patch("backend.app.optimizer.cp_sat_optimizer.CP_SAT_Optimizer") as mock_solver:
            monthly = planner.generate_monthly_plan(target_date=base_date)
            assert isinstance(monthly, MonthlyPlan)
            mock_solver.assert_not_called()

            weekly = planner.generate_weekly_plan(target_date=base_date)
            assert isinstance(weekly, WeeklyPlan)
            mock_solver.assert_not_called()

            problem = planner.prepare_daily_problem(target_date=base_date, include_forecast=False)
            assert isinstance(problem, DailySchedulingProblem)
            mock_solver.assert_not_called()


class TestBackwardCompatibility:
    """Verifies that legacy facades generate_plan and optimize_plan continue to work."""

    def test_legacy_generate_plan(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"],
            block_records=sample_data["blocks"],
            timetables=sample_data["timetables"],
        )

        result = planner.generate_plan(
            BlockPlanRequest(target_date=base_date, include_forecast=False, include_conflicts=False)
        )
        assert isinstance(result, BlockPlanResult)
        assert result.plan_id.startswith("PLAN-")
        assert result.target_date == base_date

    def test_legacy_optimize_plan_delegation(self, base_date: date, sample_data: dict):
        planner = BlockPlanner(
            maintenance_records=sample_data["records"][:1],
            timetables=sample_data["timetables"],
        )

        result = planner.optimize_plan(
            OptimizationRequest(target_date=base_date, horizon_days=1, include_forecast=False)
        )
        assert isinstance(result, OptimizationResult)
        assert result.plan_id.startswith("OPT-")
