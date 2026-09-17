"""
Phase 1 Data Contracts Unit Tests.

Validates schemas and contracts established for:
- Block Planner: MonthlyPlanItem, MonthlyPlan, WeeklyPlanItem, WeeklyPlan
- Interface Contract: CandidateWorkItem, CorridorAvailabilityWindow, DailySchedulingProblem
- Scheduler: DailyAvailabilityReport, WorkBlockMatch, WorkMatchReport, DailyScheduleResult
- AI Prioritization forward-extensibility (CandidateWorkItem extra fields)
- Backward compatibility with existing domain models
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import pytest
from pydantic import ValidationError

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
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
    OptimizedBlock,
    SolverStatistics,
    UnscheduledBlock,
)
from backend.app.scheduler.schemas import (
    ConflictReport,
    DailyAvailabilityReport,
    DailyScheduleResult,
    FeasibleSlot,
    MaintenanceScheduleItem,
    ScheduleResult,
    WorkBlockMatch,
    WorkMatchReport,
)
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)


class TestMonthlyPlanningContracts:
    """Validates 30-day horizon MonthlyPlan and MonthlyPlanItem contracts."""

    def test_monthly_plan_item_valid(self):
        item = MonthlyPlanItem(
            work_id="WORK-M-001",
            month_bucket="2026-10",
            week_bucket=2,
            corridor="Chennai-Arakkonam",
            estimated_duration_minutes=180,
            priority=Priority.HIGH,
            asset_id="TRK-MAS-01",
            asset_type="Track",
            location="Perambur - KM 15",
            maintenance_type="Preventive",
            required_resources=4,
            equipment="BCM Track Relaying",
            status="Planned",
            description="Deep screening of mainline track ballast",
        )
        assert item.work_id == "WORK-M-001"
        assert item.month_bucket == "2026-10"
        assert item.week_bucket == 2
        assert item.corridor == "Chennai-Arakkonam"
        assert item.estimated_duration_minutes == 180
        assert item.priority == Priority.HIGH
        assert item.required_resources == 4

        # Verify serialization
        data = item.model_dump()
        assert data["work_id"] == "WORK-M-001"
        assert data["priority"] == "High"

    def test_monthly_plan_item_validation_errors(self):
        # Invalid duration <= 0
        with pytest.raises(ValidationError):
            MonthlyPlanItem(
                work_id="WORK-INV",
                month_bucket="2026-10",
                week_bucket=1,
                corridor="Chennai-Arakkonam",
                estimated_duration_minutes=0,
            )

        # Invalid week_bucket > 5
        with pytest.raises(ValidationError):
            MonthlyPlanItem(
                work_id="WORK-INV",
                month_bucket="2026-10",
                week_bucket=6,
                corridor="Chennai-Arakkonam",
                estimated_duration_minutes=120,
            )

    def test_monthly_plan_contract(self):
        item1 = MonthlyPlanItem(
            work_id="WORK-M-001",
            month_bucket="2026-10",
            week_bucket=1,
            corridor="Chennai-Arakkonam",
            estimated_duration_minutes=120,
            priority=Priority.CRITICAL,
        )
        item2 = MonthlyPlanItem(
            work_id="WORK-M-002",
            month_bucket="2026-10",
            week_bucket=2,
            corridor="Arakkonam-Renigunta",
            estimated_duration_minutes=240,
            priority=Priority.MEDIUM,
        )

        plan = MonthlyPlan(
            plan_id="MPLAN-2026-10-001",
            planning_month="2026-10",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            horizon_days=31,
            generated_at=datetime.now(timezone.utc).isoformat(),
            corridor_summaries={
                "Chennai-Arakkonam": {"items_count": 1, "duration_minutes": 120},
                "Arakkonam-Renigunta": {"items_count": 1, "duration_minutes": 240},
            },
            total_maintenance_volume=360,
            total_items=2,
            weekly_breakdown={
                "Week 1": {"items_count": 1, "duration_minutes": 120},
                "Week 2": {"items_count": 1, "duration_minutes": 240},
            },
            items=[item1, item2],
            metadata={"planner_version": "2.0.0", "author": "Tactical Planner"},
        )

        assert plan.plan_id == "MPLAN-2026-10-001"
        assert plan.total_items == 2
        assert plan.total_maintenance_volume == 360
        assert len(plan.items) == 2
        assert "Chennai-Arakkonam" in plan.corridor_summaries

        # Test round-trip JSON serialization
        json_str = plan.model_dump_json()
        assert "MPLAN-2026-10-001" in json_str
        loaded = MonthlyPlan.model_validate_json(json_str)
        assert loaded.plan_id == plan.plan_id
        assert len(loaded.items) == 2


class TestWeeklyPlanningContracts:
    """Validates 7-day horizon WeeklyPlan and WeeklyPlanItem contracts."""

    def test_weekly_plan_item_valid(self):
        item = WeeklyPlanItem(
            work_id="WORK-W-101",
            target_date=date(2026, 10, 5),
            corridor="Chennai-Arakkonam",
            location="Perambur",
            estimated_duration_minutes=150,
            asset_id="SIG-AJJ-04",
            asset_type="Signal",
            asset_compatibility_requirements=["Signal interlocking power cut safe"],
            required_resources=3,
            required_equipment="Signal Testing Rig",
            priority=Priority.HIGH,
            preferred_start="02:30",
            constraints=["OHE isolation required", "Speed restriction 45 km/h"],
            is_mandatory=True,
            is_pinned=False,
        )

        assert item.work_id == "WORK-W-101"
        assert item.target_date == date(2026, 10, 5)
        assert item.is_mandatory is True
        assert len(item.constraints) == 2
        assert len(item.asset_compatibility_requirements) == 1

    def test_weekly_plan_contract(self):
        item1 = WeeklyPlanItem(
            work_id="WORK-W-101",
            target_date=date(2026, 10, 5),
            corridor="Chennai-Arakkonam",
            location="Perambur",
            estimated_duration_minutes=150,
            priority=Priority.HIGH,
        )
        item2 = WeeklyPlanItem(
            work_id="WORK-W-102",
            target_date=date(2026, 10, 7),
            corridor="Chennai-Arakkonam",
            location="Arakkonam Yard",
            estimated_duration_minutes=180,
            priority=Priority.CRITICAL,
            is_mandatory=True,
        )

        weekly_plan = WeeklyPlan(
            plan_id="WPLAN-2026-W41",
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 11),
            horizon_days=7,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_items=2,
            total_duration_minutes=330,
            daily_breakdown={"2026-10-05": 1, "2026-10-07": 1},
            corridor_summaries={"Chennai-Arakkonam": {"items_count": 2, "total_duration": 330}},
            items=[item1, item2],
            metadata={"originating_monthly_plan": "MPLAN-2026-10-001"},
        )

        assert weekly_plan.horizon_days == 7
        assert weekly_plan.total_items == 2
        assert weekly_plan.total_duration_minutes == 330
        assert len(weekly_plan.items) == 2


class TestDailySchedulingProblemContracts:
    """Validates DailySchedulingProblem, CandidateWorkItem, and CorridorAvailabilityWindow."""

    def test_candidate_work_item(self):
        c_work = CandidateWorkItem(
            work_id="CAND-001",
            location="Perambur",
            required_duration_minutes=120,
            asset_id="TRK-PER-01",
            asset_type="Track",
            corridor="Chennai-Arakkonam",
            maintenance_type="Preventive",
            required_resources=2,
            required_equipment="Tamping Machine",
            priority=Priority.CRITICAL,
            preferred_start="01:30",
            preferred_date=date(2026, 10, 5),
            constraints=["Headway 15 min buffer"],
            is_mandatory=True,
            is_pinned=False,
        )

        assert c_work.work_id == "CAND-001"
        assert c_work.location == "Perambur"
        assert c_work.priority == Priority.CRITICAL
        assert c_work.is_mandatory is True

    def test_corridor_availability_window(self):
        window = CorridorAvailabilityWindow(
            window_id="WIN-MAS-AJJ-01",
            corridor="Chennai-Arakkonam",
            service_date=date(2026, 10, 5),
            start_time="01:00",
            end_time="04:00",
            duration_minutes=180,
            section="Perambur-Villivakkam",
            status="Available",
            restrictions=["Max axle load 25t"],
            capacity_info={"max_crew": 10, "parallel_blocks_allowed": 1},
            max_parallel_works=1,
        )

        assert window.window_id == "WIN-MAS-AJJ-01"
        assert window.service_date == date(2026, 10, 5)
        assert window.duration_minutes == 180
        assert window.status == "Available"
        assert len(window.restrictions) == 1

    def test_daily_scheduling_problem(self):
        work = CandidateWorkItem(
            work_id="CAND-001",
            location="Perambur",
            required_duration_minutes=120,
            priority=Priority.HIGH,
        )
        window = CorridorAvailabilityWindow(
            window_id="WIN-001",
            corridor="Chennai-Arakkonam",
            service_date=date(2026, 10, 5),
            start_time="01:00",
            end_time="03:30",
            duration_minutes=150,
        )

        problem = DailySchedulingProblem(
            problem_id="PROB-2026-10-05",
            target_date=date(2026, 10, 5),
            candidate_works=[work],
            available_windows=[window],
            timetable_constraints=[
                {"train_id": "12601", "section": "Perambur", "passage_time": "00:45"}
            ],
            goods_train_forecast_windows=[
                {"train_id": "BOXN-01", "section": "Perambur", "entry": "04:15", "exit": "04:45"}
            ],
            operational_restrictions=["Night possession standard protocol"],
            buffer_minutes=15,
            metadata={"created_from": "WeeklyPlan WPLAN-2026-W41"},
        )

        assert problem.problem_id == "PROB-2026-10-05"
        assert problem.target_date == date(2026, 10, 5)
        assert len(problem.candidate_works) == 1
        assert len(problem.available_windows) == 1
        assert problem.buffer_minutes == 15
        assert len(problem.timetable_constraints) == 1
        assert len(problem.goods_train_forecast_windows) == 1

        # Test JSON round-trip
        data_json = problem.model_dump_json()
        assert "PROB-2026-10-05" in data_json
        loaded_prob = DailySchedulingProblem.model_validate_json(data_json)
        assert loaded_prob.problem_id == problem.problem_id
        assert len(loaded_prob.candidate_works) == 1


class TestFutureAIPrioritizationExtensibility:
    """
    Validates that CandidateWorkItem and related schemas accept future AI prioritization
    fields without breaking schema validation or requiring an architectural redesign.
    """

    def test_candidate_work_item_accepts_future_ai_fields_dynamically(self):
        # Pass future AI attributes directly into CandidateWorkItem
        ai_enriched_work = CandidateWorkItem(
            work_id="CAND-AI-001",
            location="Tambaram",
            required_duration_minutes=90,
            priority=Priority.HIGH,
            # Future AI prioritization metrics:
            urgency=0.88,
            criticality=0.95,
            overdue_factor=1.4,
            asset_availability_impact="High",
            operational_impact="Severe",
            priority_value=87.5,
            ai_priority_context={
                "model_version": "v1.2",
                "features": {
                    "vibration_anomaly_score": 0.85,
                    "days_overdue": 12,
                },
            },
        )

        # Confirm standard fields work
        assert ai_enriched_work.work_id == "CAND-AI-001"
        assert ai_enriched_work.priority == Priority.HIGH

        # Confirm extra AI fields were stored and serialize cleanly
        dumped = ai_enriched_work.model_dump()
        assert dumped["urgency"] == 0.88
        assert dumped["criticality"] == 0.95
        assert dumped["overdue_factor"] == 1.4
        assert dumped["priority_value"] == 87.5
        assert dumped["ai_priority_context"]["model_version"] == "v1.2"

        # Roundtrip through JSON
        json_repr = ai_enriched_work.model_dump_json()
        assert "87.5" in json_repr
        restored = CandidateWorkItem.model_validate_json(json_repr)
        assert restored.work_id == "CAND-AI-001"
        assert getattr(restored, "priority_value", None) == 87.5


class TestSchedulerOutputContracts:
    """Validates DailyAvailabilityReport, WorkBlockMatch, WorkMatchReport, and DailyScheduleResult."""

    def test_daily_availability_report(self):
        window = CorridorAvailabilityWindow(
            window_id="WIN-001",
            corridor="Chennai-Villupuram",
            service_date=date(2026, 10, 5),
            start_time="01:30",
            end_time="04:30",
            duration_minutes=180,
        )
        report = DailyAvailabilityReport(
            report_id="AVREP-2026-10-05",
            target_date=date(2026, 10, 5),
            generated_at=datetime.now(timezone.utc).isoformat(),
            available_windows=[window],
            blocked_periods=[
                {"section": "Tambaram", "start": "04:30", "end": "05:30", "reason": "Express Passenger Train"}
            ],
            timetable_restrictions=[
                {"train_id": "16115", "scheduled_start": "04:30", "line": "Main"}
            ],
            goods_train_restrictions=[
                {"goods_train_id": "G-002", "forecast_window": "00:00-01:15"}
            ],
            active_movement_restrictions=[
                {"section": "Tambaram", "speed_restriction": "Caution 20km/h"}
            ],
            corridor_capacities={
                "Chennai-Villupuram": {"available_minutes": 180, "utilization_pct": 0.0}
            },
        )

        assert report.report_id == "AVREP-2026-10-05"
        assert len(report.available_windows) == 1
        assert len(report.blocked_periods) == 1
        assert len(report.timetable_restrictions) == 1
        assert len(report.goods_train_restrictions) == 1
        assert len(report.active_movement_restrictions) == 1

    def test_work_block_match_compatible_and_rejected(self):
        # Compatible match
        compat_match = WorkBlockMatch(
            match_id="MATCH-001",
            work_id="CAND-001",
            window_id="WIN-001",
            is_compatible=True,
            fit_score=0.95,
            compatibility_details={"duration_fit": "120m fits 180m window", "location": "Exact match"},
            rejection_reasons=[],
        )
        assert compat_match.is_compatible is True
        assert compat_match.fit_score == 0.95
        assert len(compat_match.rejection_reasons) == 0

        # Incompatible match
        rejected_match = WorkBlockMatch(
            match_id="MATCH-002",
            work_id="CAND-002",
            window_id="WIN-001",
            is_compatible=False,
            fit_score=0.0,
            compatibility_details={"duration_fit": "240m exceeds 180m window"},
            rejection_reasons=["Insufficient duration", "Asset incompatibility"],
        )
        assert rejected_match.is_compatible is False
        assert rejected_match.fit_score == 0.0
        assert "Insufficient duration" in rejected_match.rejection_reasons
        assert "Asset incompatibility" in rejected_match.rejection_reasons

    def test_work_match_report(self):
        match1 = WorkBlockMatch(
            match_id="MATCH-001",
            work_id="CAND-001",
            window_id="WIN-001",
            is_compatible=True,
            fit_score=1.0,
        )

        report = WorkMatchReport(
            report_id="MATCHREP-2026-10-05",
            target_date=date(2026, 10, 5),
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_works=3,
            total_matches=1,
            total_rejected=2,
            successful_matches=[match1],
            rejected_works=[
                {
                    "work_id": "CAND-002",
                    "reasons": ["Insufficient duration"],
                },
                {
                    "work_id": "CAND-003",
                    "reasons": ["Location mismatch", "Resource unavailable"],
                },
            ],
            rejection_summary={
                "Insufficient duration": 1,
                "Location mismatch": 1,
                "Resource unavailable": 1,
            },
        )

        assert report.total_works == 3
        assert report.total_matches == 1
        assert report.total_rejected == 2
        assert len(report.successful_matches) == 1
        assert len(report.rejected_works) == 2
        assert report.rejection_summary["Insufficient duration"] == 1
        assert report.rejection_summary["Location mismatch"] == 1

    def test_daily_schedule_result(self):
        opt_block = OptimizedBlock(
            block_id="OPT-BLK-001",
            request_id="TRK-M-001",
            asset_id="TRK-MAS-01",
            location="Perambur",
            service_date=date(2026, 10, 5),
            start_time="01:30",
            end_time="03:30",
            duration_minutes=120,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-001",
            fit_score=1.0,
            is_preferred_match=True,
        )

        unsched_block = UnscheduledBlock(
            request_id="TRK-M-002",
            location="Arakkonam",
            requested_date=date(2026, 10, 5),
            preferred_start="02:00",
            duration_minutes=180,
            priority=Priority.MEDIUM,
            reason="Contention with higher-priority passenger train window",
        )

        solver_stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            objective_value=12500.0,
            wall_time_seconds=0.15,
            num_scheduled=1,
            num_unscheduled=1,
            num_conflicts_avoided=2,
            total_requests=2,
            num_variables=10,
            num_constraints=15,
        )

        result = DailyScheduleResult(
            plan_id="DSCHED-2026-10-05-001",
            target_date=date(2026, 10, 5),
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_scheduled=1,
            total_unscheduled=1,
            scheduled_works=[opt_block],
            optimized_block_assignments=[opt_block],
            unscheduled_works=[unsched_block],
            diagnostics={"bottlenecks": ["Arakkonam junction saturation"]},
            matching_statistics={"total_candidates": 2, "match_ratio": 0.5},
            optimization_metadata={"preset": "balanced", "time_limit": 30.0},
            solver_statistics=solver_stats,
        )

        assert result.plan_id == "DSCHED-2026-10-05-001"
        assert result.total_scheduled == 1
        assert result.total_unscheduled == 1
        assert len(result.optimized_block_assignments) == 1
        assert len(result.unscheduled_works) == 1
        assert result.solver_statistics.status == OptimizationStatus.OPTIMAL


class TestCrossModuleSchemaImports:
    """Validates that boundary contracts are cleanly importable from either module."""

    def test_import_from_block_planner(self):
        from backend.app.block_planner.schemas import (
            CandidateWorkItem,
            CorridorAvailabilityWindow,
            DailySchedulingProblem,
            MonthlyPlan,
            MonthlyPlanItem,
            WeeklyPlan,
            WeeklyPlanItem,
        )
        assert CandidateWorkItem is not None
        assert CorridorAvailabilityWindow is not None
        assert DailySchedulingProblem is not None
        assert MonthlyPlan is not None
        assert MonthlyPlanItem is not None
        assert WeeklyPlan is not None
        assert WeeklyPlanItem is not None

    def test_import_from_scheduler(self):
        from backend.app.scheduler.schemas import (
            CandidateWorkItem,
            CorridorAvailabilityWindow,
            DailyAvailabilityReport,
            DailyScheduleResult,
            DailySchedulingProblem,
            WorkBlockMatch,
            WorkMatchReport,
        )
        assert CandidateWorkItem is not None
        assert CorridorAvailabilityWindow is not None
        assert DailySchedulingProblem is not None
        assert DailyAvailabilityReport is not None
        assert DailyScheduleResult is not None
        assert WorkBlockMatch is not None
        assert WorkMatchReport is not None


class TestBackwardCompatibility:
    """Ensures existing domain models and planning schemas continue to function unchanged."""

    def test_maintenance_record_backward_compatibility(self):
        rec = MaintenanceRecord(
            asset_id="TRK-100",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.MEDIUM,
            duration_minutes=90,
            requested_date=date(2026, 10, 5),
            preferred_start=time(2, 0),
            required_resources=2,
            equipment="BCM",
            status=MaintenanceStatus.PENDING,
            source="smms",
        )
        assert rec.asset_id == "TRK-100"
        assert rec.priority == Priority.MEDIUM
        assert rec.duration_minutes == 90

    def test_block_plan_request_and_result_backward_compatibility(self):
        req = BlockPlanRequest(
            target_date=date(2026, 10, 5),
            priority_filter="High",
            buffer_minutes=15,
        )
        assert req.buffer_minutes == 15
        assert req.priority_filter == "High"

        res = BlockPlanResult(
            plan_id="PLAN-001",
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_date=date(2026, 10, 5),
            schedule=ScheduleResult(
                generated_at=datetime.now(timezone.utc).isoformat(),
                target_date=date(2026, 10, 5),
                total_requested=0,
                total_scheduled=0,
                total_unfeasible=0,
            ),
        )
        assert res.plan_id == "PLAN-001"
        assert res.schedule.total_requested == 0

    def test_optimization_request_backward_compatibility(self):
        opt_req = OptimizationRequest(
            target_date=date(2026, 10, 5),
            horizon_days=7,
            priority_filter="Critical",
        )
        assert opt_req.horizon_days == 7
        assert opt_req.priority_filter == "Critical"
