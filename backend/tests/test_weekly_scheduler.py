"""
Strengthened weekly scheduler test.

Verifies that schedule_type="weekly" produces exactly the expected 7-day
planning horizon, uses the real scheduler's conflict/constraint logic, and
that no 8th day is included.
"""

from datetime import date, timedelta

from backend.app.scheduler.scheduler import (
    MaintenanceScheduler,
    _generate_schedule_dates,
    _get_horizon_days,
)
from backend.app.scheduler.schemas import ScheduleResult
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)
from datetime import time


def _week_records(start: date) -> list:
    """Create one maintenance record per day for the 7-day window."""
    return [
        MaintenanceRecord(
            asset_id=f"TRK-W{i}",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.MEDIUM,
            duration_minutes=60,
            requested_date=start + timedelta(days=i),
            preferred_start=time(10, 0),
            required_resources=2,
            equipment="Standard Gang",
            status=MaintenanceStatus.PENDING,
        )
        for i in range(7)
    ]


TARGET = date(2026, 9, 7)   # Monday
EXPECTED_LAST = date(2026, 9, 13)  # Sunday
EXPECTED_DATES = [TARGET + timedelta(days=i) for i in range(7)]


def test_weekly_horizon_function_returns_seven():
    """_get_horizon_days('weekly', ...) must return exactly 7."""
    assert _get_horizon_days("weekly", TARGET) == 7


def test_weekly_date_range_starts_on_target_date():
    """The first date in the 7-day window must be the target date."""
    dates = _generate_schedule_dates(TARGET, 7)
    assert dates[0] == TARGET


def test_weekly_date_range_ends_on_target_plus_six():
    """The last date in the 7-day window must be target_date + 6."""
    dates = _generate_schedule_dates(TARGET, 7)
    assert dates[-1] == EXPECTED_LAST


def test_weekly_date_range_has_no_eighth_day():
    """The 7-day window must contain exactly 7 dates and no more."""
    dates = _generate_schedule_dates(TARGET, 7)
    assert len(dates) == 7


def test_weekly_date_range_contains_all_seven_expected_dates():
    """Every date from target through target+6 must appear in the range."""
    dates = _generate_schedule_dates(TARGET, 7)
    assert list(dates) == EXPECTED_DATES


def test_weekly_scheduler_accepts_schedule_type():
    """schedule_type='weekly' must be accepted and return a ScheduleResult."""
    scheduler = MaintenanceScheduler()
    result = scheduler.schedule(target_date=TARGET, schedule_type="weekly")
    assert isinstance(result, ScheduleResult)


def test_weekly_scheduler_considers_all_seven_days():
    """
    With one request per day across 7 days, the weekly scheduler must
    process all 7 requests (using its normal conflict/constraint logic).
    """
    records = _week_records(TARGET)
    scheduler = MaintenanceScheduler(maintenance_records=records)
    result = scheduler.schedule(target_date=TARGET, schedule_type="weekly")

    # All 7 are within the horizon — all must be considered
    assert result.total_requested == 7
    # At least some must be scheduled (corridor is empty, so all should be)
    assert result.total_scheduled >= 1


def test_weekly_assigned_slots_are_within_seven_day_window():
    """
    Every assigned slot must have a service_date within [target, target+6].
    No slot may fall outside the 7-day horizon.
    """
    records = _week_records(TARGET)
    scheduler = MaintenanceScheduler(maintenance_records=records)
    result = scheduler.schedule(target_date=TARGET, schedule_type="weekly")

    horizon_dates = set(EXPECTED_DATES)
    for item in result.scheduled_items:
        if item.assigned_slot:
            assert item.assigned_slot.service_date in horizon_dates, (
                f"Slot for {item.request_id} fell on "
                f"{item.assigned_slot.service_date}, outside the 7-day horizon "
                f"({TARGET} – {EXPECTED_LAST})"
            )


def test_weekly_scheduler_does_not_schedule_outside_horizon():
    """
    A request dated 8 days in the future must NOT be included in a weekly run.
    """
    outside_date = TARGET + timedelta(days=7)  # day 8, beyond the 7-day window
    outside_record = MaintenanceRecord(
        asset_id="TRK-OUTSIDE",
        asset_type="Track",
        location="Chennai-Arakkonam",
        maintenance_type="Preventive",
        maintenance_required=True,
        priority=Priority.MEDIUM,
        duration_minutes=60,
        requested_date=outside_date,
        preferred_start=time(10, 0),
        required_resources=2,
        equipment="Standard Gang",
        status=MaintenanceStatus.PENDING,
    )
    scheduler = MaintenanceScheduler(maintenance_records=[outside_record])
    result = scheduler.schedule(target_date=TARGET, schedule_type="weekly")

    # The out-of-horizon request must not be processed at all
    assert result.total_requested == 0, (
        "A request 8 days out must not be included in a 7-day weekly horizon"
    )