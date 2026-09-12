"""
Unit and integration tests for Phase 4 Maintenance Scheduler, Conflict Detector,
and Auto-Resolver.
"""

from __future__ import annotations

from datetime import date, time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.connection import Base
from backend.app.database.repositories import (
    BlockRepository,
    MaintenanceRepository,
    TimetableRepository,
    TrainRepository,
)
from backend.app.forecast.forecast import GoodsTrainForecaster
from backend.app.forecast.schemas import GoodsForecastItem, ForecastConfidenceLevel
from backend.app.scheduler.auto_resolver import AutoResolver
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.scheduler.scheduler import MaintenanceScheduler
from backend.app.scheduler.schemas import (
    ConflictSeverity,
    ConflictType,
    FeasibleSlot,
    ScheduleResult,
)
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
def mock_timetables():
    return [
        TimetableRecord(
            train_id="P204",
            service_date=date(2026, 9, 5),
            station_code="Chennai",
            arrival_time=None,
            departure_time="10:05",
            platform=1,
            sequence=1,
        ),
        TimetableRecord(
            train_id="P204",
            service_date=date(2026, 9, 5),
            station_code="Perambur",
            arrival_time="10:15",
            departure_time="10:17",
            platform=2,
            sequence=2,
        ),
        TimetableRecord(
            train_id="P204",
            service_date=date(2026, 9, 5),
            station_code="AJJ",
            arrival_time="11:15",
            departure_time="11:20",
            platform=1,
            sequence=3,
        ),
    ]


@pytest.fixture
def mock_maintenance_records():
    return [
        MaintenanceRecord(
            asset_id="TRK-1025",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=120,
            requested_date=date(2026, 9, 5),
            preferred_start=time(14, 0),
            required_resources=8,
            equipment="Tamping Machine",
            status=MaintenanceStatus.PENDING,
        ),
        MaintenanceRecord(
            asset_id="SIG-2041",
            asset_type="Signal",
            location="Perambur Junction",
            maintenance_type="Inspection",
            maintenance_required=True,
            priority=Priority.MEDIUM,
            duration_minutes=60,
            requested_date=date(2026, 9, 5),
            preferred_start=time(12, 0),
            required_resources=3,
            equipment="Signal Testing Kit",
            status=MaintenanceStatus.PENDING,
        ),
    ]


@pytest.fixture
def mock_forecasts():
    return [
        GoodsForecastItem(
            forecast_id="FC-0001",
            train_id="G123",
            route_id="R-CHN-AJJ",
            section="Chennai-Perambur",
            direction="Up",
            line="Main",
            service_date=date(2026, 9, 5),
            forecasted_entry="09:30",
            forecasted_exit="09:45",
            delay_minutes=0,
            confidence_score=0.90,
            confidence_level=ForecastConfidenceLevel.HIGH,
        ),
    ]


@pytest.fixture
def mock_block_records():
    return [
        BlockRecord(
            block_id="BLK-001",
            location="Chennai-Arakkonam",
            block_type=BlockType.MAINTENANCE,
            requested_date=date(2026, 9, 5),
            requested_start="10:00",
            requested_end="12:00",
            reason="Track maintenance",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        ),
    ]


def test_find_feasible_slots_empty_corridor():
    scheduler = MaintenanceScheduler(buffer_minutes=15)
    slots = scheduler.find_feasible_slots(
        location="Isolated-Section",
        duration_minutes=120,
        preferred_start="10:00",
        target_date=date(2026, 9, 5),
    )
    assert len(slots) > 0
    assert slots[0].duration_minutes == 120
    assert slots[0].start_time == "10:00"
    assert slots[0].is_preferred_match is True
    assert slots[0].fit_score == 1.0


def test_find_feasible_slots_with_traffic(mock_timetables, mock_forecasts):
    scheduler = MaintenanceScheduler(
        timetables=mock_timetables,
        goods_forecasts=mock_forecasts,
        buffer_minutes=15,
    )
    slots = scheduler.find_feasible_slots(
        location="Chennai-Arakkonam",
        duration_minutes=120,
        preferred_start="10:00",
        target_date=date(2026, 9, 5),
    )
    # Train P204 is active between 10:00 and 11:35 in this section with buffer
    # The scheduler should provide alternative feasible slots that avoid 10:00 - 11:35
    assert len(slots) > 0
    for s in slots:
        assert s.start_time != "10:00" or s.is_preferred_match is False


def test_full_schedule_execution(mock_maintenance_records, mock_timetables, mock_forecasts):
    scheduler = MaintenanceScheduler(
        maintenance_records=mock_maintenance_records,
        timetables=mock_timetables,
        goods_forecasts=mock_forecasts,
    )
    result = scheduler.schedule(target_date=date(2026, 9, 5))

    assert isinstance(result, ScheduleResult)
    assert result.total_requested == 2
    assert result.total_scheduled >= 1
    assert len(result.scheduled_items) >= 1


def test_train_block_conflict_detection(mock_timetables, mock_block_records):
    # BLK-001 is requested 10:00 - 12:00 on Chennai-Arakkonam
    # P204 is at Chennai at 10:05 and Perambur at 10:15
    detector = ConflictDetector(
        timetables=mock_timetables,
        block_records=mock_block_records,
    )
    report = detector.detect_conflicts(target_date=date(2026, 9, 5))

    assert report.is_conflict_free is False
    assert report.total_conflicts >= 1
    assert report.critical_count >= 1

    train_conflicts = [c for c in report.conflicts if c.conflict_type == ConflictType.TRAIN_BLOCK]
    assert len(train_conflicts) >= 1
    assert train_conflicts[0].entity1_id == "P204"
    assert train_conflicts[0].entity2_id == "BLK-001"


def test_block_block_conflict_detection():
    b1 = BlockRecord(
        block_id="BLK-A",
        location="Chennai-Arakkonam",
        block_type=BlockType.MAINTENANCE,
        requested_date=date(2026, 9, 5),
        requested_start="10:00",
        requested_end="12:00",
        reason="Work 1",
        priority=Priority.HIGH,
        status=BlockStatus.REQUESTED,
    )
    b2 = BlockRecord(
        block_id="BLK-B",
        location="Chennai-Arakkonam",
        block_type=BlockType.MAINTENANCE,
        requested_date=date(2026, 9, 5),
        requested_start="11:00",
        requested_end="13:00",
        reason="Work 2",
        priority=Priority.HIGH,
        status=BlockStatus.REQUESTED,
    )
    detector = ConflictDetector(block_records=[b1, b2])
    report = detector.detect_conflicts(target_date=date(2026, 9, 5))

    bb_conflicts = [c for c in report.conflicts if c.conflict_type == ConflictType.BLOCK_BLOCK]
    assert len(bb_conflicts) == 1
    assert bb_conflicts[0].overlap_minutes == 60


def test_resource_contention_detection():
    m1 = MaintenanceRecord(
        asset_id="TRK-1",
        asset_type="Track",
        location="Chennai-Perambur",
        maintenance_type="Preventive",
        maintenance_required=True,
        priority=Priority.HIGH,
        duration_minutes=120,
        requested_date=date(2026, 9, 5),
        preferred_start=time(10, 0),
        required_resources=5,
        equipment="Tamping Machine",
        status=MaintenanceStatus.PENDING,
    )
    m2 = MaintenanceRecord(
        asset_id="TRK-2",
        asset_type="Track",
        location="Tambaram-Chengalpattu",
        maintenance_type="Preventive",
        maintenance_required=True,
        priority=Priority.MEDIUM,
        duration_minutes=120,
        requested_date=date(2026, 9, 5),
        preferred_start=time(10, 30),
        required_resources=5,
        equipment="Tamping Machine",
        status=MaintenanceStatus.PENDING,
    )
    detector = ConflictDetector(maintenance_records=[m1, m2])
    report = detector.detect_conflicts(target_date=date(2026, 9, 5))

    res_conflicts = [c for c in report.conflicts if c.conflict_type == ConflictType.RESOURCE_CONTENTION]
    assert len(res_conflicts) == 1
    assert "Tamping Machine" in res_conflicts[0].description


def test_auto_resolver(mock_timetables, mock_block_records):
    detector = ConflictDetector(
        timetables=mock_timetables,
        block_records=mock_block_records,
    )
    report = detector.detect_conflicts(target_date=date(2026, 9, 5))

    resolver = AutoResolver()
    resolutions = resolver.generate_resolution_plan(report)

    assert len(resolutions) == len(report.conflicts)
    for r in resolutions:
        assert "strategy" in r
        assert "recommendation" in r


def test_scheduler_unfeasible_oversized_duration(mock_timetables):
    """Test that requests with impossible duration return Unfeasible status."""
    scheduler = MaintenanceScheduler(
        maintenance_records=[
            MaintenanceRecord(
                asset_id="TRK-999",
                asset_type="Track",
                location="Chennai-Arakkonam",
                maintenance_type="Renewal",
                maintenance_required=True,
                priority=Priority.CRITICAL,
                duration_minutes=1500,  # > 24 hours
                requested_date=date(2026, 9, 5),
                preferred_start=time(6, 0),
                required_resources=10,
                equipment="Crane",
                status=MaintenanceStatus.PENDING,
            )
        ],
        timetables=mock_timetables,
    )
    result = scheduler.schedule(target_date=date(2026, 9, 5))
    assert result.total_requested == 1
    assert result.total_scheduled == 0
    assert result.total_unfeasible == 1
    assert result.unfeasible_items[0].status == "Unfeasible"


def test_conflict_detector_clean_no_conflicts():
    """Test conflict detector returns is_conflict_free=True when entities are disjoint."""
    tt = [
        TimetableRecord(
            train_id="P1",
            service_date=date(2026, 9, 5),
            station_code="Chennai",
            arrival_time=None,
            departure_time="06:00",
            platform=1,
            sequence=1,
        )
    ]
    blk = [
        BlockRecord(
            block_id="BLK-NIGHT",
            location="Chennai",
            block_type=BlockType.MAINTENANCE,
            requested_date=date(2026, 9, 5),
            requested_start="22:00",
            requested_end="23:30",
            reason="Night inspection",
            priority=Priority.LOW,
            status=BlockStatus.REQUESTED,
        )
    ]
    detector = ConflictDetector(timetables=tt, block_records=blk, buffer_minutes=15)
    report = detector.detect_conflicts(target_date=date(2026, 9, 5))
    assert report.is_conflict_free is True
    assert report.total_conflicts == 0


def test_block_planner_facade_end_to_end(
    mock_timetables, mock_maintenance_records, mock_block_records, mock_forecasts
):
    """Test BlockPlanner facade orchestrating Forecast, Scheduler, Conflict Detector."""
    from backend.app.block_planner.planner import BlockPlanner
    from backend.app.block_planner.schemas import BlockPlanRequest

    planner = BlockPlanner(
        timetables=mock_timetables,
        maintenance_records=mock_maintenance_records,
        block_records=mock_block_records,
    )
    plan = planner.generate_plan(
        BlockPlanRequest(target_date=date(2026, 9, 5), include_forecast=True, include_conflicts=True)
    )

    assert plan.plan_id.startswith("PLAN-")
    assert plan.target_date == date(2026, 9, 5)
    assert plan.schedule.total_requested >= 1
    assert plan.conflict_report is not None
    assert isinstance(plan.resolution_recommendations, list)


# ===========================================================================
# Schedule-Type Horizon Tests (Daily / Weekly / Monthly)
# ===========================================================================

from backend.app.scheduler.scheduler import _get_horizon_days, _generate_schedule_dates
from backend.app.scheduler.schemas import ScheduleRequest, ScheduleType


def _make_maintenance(asset_id: str, target_date: date) -> MaintenanceRecord:
    """Helper: create a minimal pending maintenance record for a given date."""
    return MaintenanceRecord(
        asset_id=asset_id,
        asset_type="Track",
        location="Chennai-Arakkonam",
        maintenance_type="Preventive",
        maintenance_required=True,
        priority=Priority.MEDIUM,
        duration_minutes=60,
        requested_date=target_date,
        preferred_start=time(10, 0),
        required_resources=2,
        equipment="Standard Gang",
        status=MaintenanceStatus.PENDING,
    )


# ── 1. Daily scheduling ────────────────────────────────────────────────────

def test_daily_horizon_is_one_day():
    """daily schedule_type must produce exactly 1 planning day."""
    horizon = _get_horizon_days("daily", date(2026, 9, 7))
    assert horizon == 1


def test_daily_schedule_execution():
    """Daily scheduler returns a ScheduleResult and processes only the requested date."""
    scheduler = MaintenanceScheduler(
        maintenance_records=[_make_maintenance("TRK-D1", date(2026, 9, 7))],
    )
    result = scheduler.schedule(target_date=date(2026, 9, 7), schedule_type="daily")

    assert isinstance(result, ScheduleResult)
    assert result.total_requested == 1
    # Any slot that is assigned must fall on the requested date
    for item in result.scheduled_items:
        if item.assigned_slot:
            assert item.assigned_slot.service_date == date(2026, 9, 7)


# ── 2. Weekly scheduling ───────────────────────────────────────────────────

def test_weekly_horizon_is_seven_days():
    """weekly schedule_type must produce exactly 7 planning days."""
    horizon = _get_horizon_days("weekly", date(2026, 9, 7))
    assert horizon == 7


def test_weekly_schedule_generates_seven_date_range():
    """_generate_schedule_dates with horizon=7 covers exactly Mon-Sun."""
    start = date(2026, 9, 7)
    dates = _generate_schedule_dates(start, 7)
    assert len(dates) == 7
    assert dates[0] == start
    assert dates[-1] == date(2026, 9, 13)


def test_weekly_schedule_can_spread_across_dates():
    """Weekly scheduler can assign items to any of the 7 days."""
    # Create 7 tasks, each on a different day of the week
    start = date(2026, 9, 7)
    records = [
        _make_maintenance(f"TRK-W{i}", start + __import__('datetime').timedelta(days=i))
        for i in range(7)
    ]
    scheduler = MaintenanceScheduler(maintenance_records=records)
    result = scheduler.schedule(target_date=start, schedule_type="weekly")

    assert result.total_requested == 7
    assert result.total_scheduled >= 1  # At least some must be scheduled


# ── 3. Monthly scheduling — general ───────────────────────────────────────

def test_monthly_31_day_month():
    """Monthly horizon from day 1 of a 31-day month covers all 31 days."""
    horizon = _get_horizon_days("monthly", date(2026, 10, 1))
    assert horizon == 31


def test_monthly_30_day_month():
    """Monthly horizon from day 1 of a 30-day month covers all 30 days."""
    horizon = _get_horizon_days("monthly", date(2026, 9, 1))
    assert horizon == 30


def test_monthly_28_day_february():
    """Monthly horizon for a non-leap February covers exactly 28 days from day 1."""
    horizon = _get_horizon_days("monthly", date(2026, 2, 1))
    assert horizon == 28


def test_monthly_29_day_leap_year_february():
    """Monthly horizon for a leap-year February covers exactly 29 days from day 1."""
    horizon = _get_horizon_days("monthly", date(2024, 2, 1))
    assert horizon == 29


def test_monthly_mid_month_start():
    """Starting mid-month produces days remaining in that calendar month."""
    # September has 30 days; starting on the 16th leaves 15 days (16..30)
    horizon = _get_horizon_days("monthly", date(2026, 9, 16))
    assert horizon == 15


def test_monthly_last_day_of_month():
    """Starting on the last day of a month returns exactly 1 day."""
    horizon = _get_horizon_days("monthly", date(2026, 9, 30))
    assert horizon == 1


def test_monthly_schedule_execution():
    """Monthly scheduler returns a ScheduleResult for the full calendar month."""
    start = date(2026, 9, 1)
    scheduler = MaintenanceScheduler(
        maintenance_records=[_make_maintenance("TRK-M1", start)],
    )
    result = scheduler.schedule(target_date=start, schedule_type="monthly")

    assert isinstance(result, ScheduleResult)
    assert result.total_requested == 1


# ── 4. ScheduleRequest schema validation ──────────────────────────────────

def test_schedule_request_accepts_valid_schedule_type():
    """ScheduleRequest must accept all three valid schedule_type values."""
    for stype in ("daily", "weekly", "monthly"):
        req = ScheduleRequest(target_date=date(2026, 9, 7), schedule_type=stype)
        assert req.schedule_type == stype


def test_schedule_request_rejects_invalid_schedule_type():
    """ScheduleRequest must reject any schedule_type not in the allowed set."""
    from pydantic import ValidationError

    for bad in ("Weekly", "DAILY", "week", "month", "biweekly", ""):
        try:
            ScheduleRequest(target_date=date(2026, 9, 7), schedule_type=bad)
            assert False, f"Expected ValidationError for schedule_type={bad!r}"
        except ValidationError:
            pass  # Expected


def test_schedule_request_defaults_to_daily():
    """ScheduleRequest without schedule_type must default to 'daily'."""
    req = ScheduleRequest(target_date=date(2026, 9, 7))
    assert req.schedule_type == "daily"


# ── 5. Conflict detection still works after the changes ───────────────────

def test_conflict_detection_unaffected_by_schedule_type(
    mock_timetables, mock_block_records
):
    """Conflict detector must work correctly regardless of schedule_type changes."""
    detector = ConflictDetector(
        timetables=mock_timetables,
        block_records=mock_block_records,
    )
    report = detector.detect_conflicts(target_date=date(2026, 9, 5))

    assert report.is_conflict_free is False
    assert report.total_conflicts >= 1


# ── 6. Invalid schedule_type raises ValueError in scheduler ───────────────

def test_invalid_schedule_type_raises_value_error():
    """_get_horizon_days must raise ValueError for unrecognised schedule_type."""
    with pytest.raises(ValueError, match="schedule_type"):
        _get_horizon_days("biweekly", date(2026, 9, 7))


# ===========================================================================
# Issue 4 — Monthly Horizon: Mid-Month and Year-Boundary Cases
#
# The backend computes: last_day_of_month - start_day + 1
# (i.e. selected date → last calendar day of that month)
# These tests verify the real date range, not just a hardcoded day count.
# ===========================================================================

import calendar as _calendar
from datetime import timedelta as _td


def _last_date_of_month(d: date) -> date:
    """Return the last calendar date of the month containing d."""
    last_day = _calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


# ── A. 30-day month, mid-month (September 12) ─────────────────────────────

def test_monthly_horizon_sep12_remaining_days():
    """Sep 12 → Sep 30 = 19 days remaining."""
    start = date(2026, 9, 12)
    horizon = _get_horizon_days("monthly", start)
    assert horizon == 19


def test_monthly_horizon_sep12_end_date():
    """The last date of the Sep-12 monthly window must be September 30."""
    start = date(2026, 9, 12)
    horizon = _get_horizon_days("monthly", start)
    dates = _generate_schedule_dates(start, horizon)
    assert dates[-1] == date(2026, 9, 30)
    assert dates[0] == start


# ── B. 30-day month, mid-month (April 12) ─────────────────────────────────

def test_monthly_horizon_apr12_remaining_days():
    """Apr 12 → Apr 30 = 19 days remaining."""
    start = date(2026, 4, 12)
    horizon = _get_horizon_days("monthly", start)
    assert horizon == 19


def test_monthly_horizon_apr12_end_date():
    """The last date of the Apr-12 monthly window must be April 30."""
    start = date(2026, 4, 12)
    horizon = _get_horizon_days("monthly", start)
    dates = _generate_schedule_dates(start, horizon)
    assert dates[-1] == date(2026, 4, 30)
    assert dates[0] == start


# ── C. February 28 (non-leap), mid-month (Feb 10, 2026) ──────────────────

def test_monthly_horizon_feb10_nonleap_remaining_days():
    """Feb 10 (non-leap 2026) → Feb 28 = 19 days remaining."""
    start = date(2026, 2, 10)
    horizon = _get_horizon_days("monthly", start)
    assert horizon == 19


def test_monthly_horizon_feb10_nonleap_end_date():
    """Last date of Feb-10 (2026) monthly window must be Feb 28."""
    start = date(2026, 2, 10)
    horizon = _get_horizon_days("monthly", start)
    dates = _generate_schedule_dates(start, horizon)
    assert dates[-1] == date(2026, 2, 28)
    assert dates[0] == start


# ── D. February 29 (leap year 2028), mid-month (Feb 10) ──────────────────

def test_monthly_horizon_feb10_leap_remaining_days():
    """Feb 10 (leap year 2028) → Feb 29 = 20 days remaining."""
    start = date(2028, 2, 10)
    horizon = _get_horizon_days("monthly", start)
    assert horizon == 20


def test_monthly_horizon_feb10_leap_end_date():
    """Last date of Feb-10 (2028 leap) monthly window must be Feb 29."""
    start = date(2028, 2, 10)
    horizon = _get_horizon_days("monthly", start)
    dates = _generate_schedule_dates(start, horizon)
    assert dates[-1] == date(2028, 2, 29)
    assert dates[0] == start


# ── E. Year boundary (December 20 → December 31) ─────────────────────────

def test_monthly_horizon_dec20_remaining_days():
    """Dec 20 → Dec 31 = 12 days remaining."""
    start = date(2026, 12, 20)
    horizon = _get_horizon_days("monthly", start)
    assert horizon == 12


def test_monthly_horizon_dec20_end_date():
    """Last date of Dec-20 monthly window must be December 31."""
    start = date(2026, 12, 20)
    horizon = _get_horizon_days("monthly", start)
    dates = _generate_schedule_dates(start, horizon)
    assert dates[-1] == date(2026, 12, 31)
    assert dates[0] == start


def test_monthly_end_date_always_matches_calendar_last_day():
    """
    Parametric check: for every test start date the last planning date must
    equal the real last calendar day of that month, regardless of start day.
    """
    cases = [
        date(2026, 9, 12),   # Sep, 30-day
        date(2026, 4, 12),   # Apr, 30-day
        date(2026, 2, 10),   # Feb, 28-day (non-leap)
        date(2028, 2, 10),   # Feb, 29-day (leap)
        date(2026, 12, 20),  # Dec, 31-day
        date(2026, 10, 1),   # Oct, 31-day from day 1
        date(2026, 9, 30),   # Last day of September
    ]
    for start in cases:
        horizon = _get_horizon_days("monthly", start)
        dates = _generate_schedule_dates(start, horizon)
        expected_last = _last_date_of_month(start)
        assert dates[-1] == expected_last, (
            f"For start={start}: expected last={expected_last}, "
            f"got {dates[-1]} (horizon={horizon})"
        )
        assert dates[0] == start
