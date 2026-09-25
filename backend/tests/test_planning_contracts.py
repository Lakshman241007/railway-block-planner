from datetime import date, time

from backend.app.data_integration.planning_adapter import (
    maintenance_record_to_work,
    maintenance_records_to_work,
)
from backend.app.schemas.planning_contracts import (
    BlockAvailability,
    GoodsForecast,
    MaintenanceWork,
    MonthlyPlan,
    PlanningHorizon,
    TimetableConstraints,
    WeeklyPlan,
)
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)


def make_record() -> MaintenanceRecord:
    return MaintenanceRecord(
        asset_id="ASSET-001",
        asset_type="Track",
        location="Chennai",
        maintenance_type="Inspection",
        maintenance_required=True,
        priority=Priority.HIGH,
        duration_minutes=120,
        requested_date=date(2026, 9, 22),
        preferred_start=time(10, 0),
        required_resources=2,
        equipment="Inspection Kit",
        status=MaintenanceStatus.PENDING,
        source="smms",
    )


def test_maintenance_record_converts_to_maintenance_work():
    record = make_record()

    work = maintenance_record_to_work(record)

    assert isinstance(work, MaintenanceWork)
    assert work.maintenance_id == "ASSET-001"
    assert work.asset_id == "ASSET-001"
    assert work.priority == Priority.HIGH
    assert work.duration_minutes == 120


def test_multiple_records_convert_to_multiple_work_items():
    records = [make_record(), make_record()]

    works = maintenance_records_to_work(records)

    assert len(works) == 2
    assert all(isinstance(work, MaintenanceWork) for work in works)


def test_block_availability_contract():
    block = BlockAvailability(
        block_id="BLOCK-001",
        location="Chennai",
        available_date=date(2026, 9, 22),
        start_time=time(10, 0),
        end_time=time(12, 0),
    )

    assert block.block_id == "BLOCK-001"
    assert block.available is True


def test_timetable_constraints_contract():
    constraint = TimetableConstraints(
        train_id="T001",
        service_date=date(2026, 9, 22),
        station_code="MAS",
        arrival=time(9, 30),
        departure=time(10, 0),
    )

    assert constraint.train_id == "T001"
    assert constraint.station_code == "MAS"


def test_goods_forecast_contract():
    forecast = GoodsForecast(
        route_id="R001",
        forecast_date=date(2026, 9, 22),
        expected_train_count=5,
        expected_volume=1200.0,
    )

    assert forecast.expected_train_count == 5
    assert forecast.expected_volume == 1200.0


def test_planning_horizon():
    horizon = PlanningHorizon(
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 30),
    )

    assert horizon.end_date >= horizon.start_date


def test_weekly_plan():
    plan = WeeklyPlan(
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
        maintenance_ids=["ASSET-001"],
    )

    assert plan.maintenance_ids == ["ASSET-001"]


def test_monthly_plan():
    plan = MonthlyPlan(
        month_start=date(2026, 9, 1),
        month_end=date(2026, 9, 30),
        maintenance_ids=["ASSET-001"],
    )

    assert plan.maintenance_ids == ["ASSET-001"]