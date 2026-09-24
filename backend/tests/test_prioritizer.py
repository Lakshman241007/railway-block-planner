from datetime import date

import pytest

from backend.app.prioritization.prioritizer import MaintenancePrioritizer
from backend.app.prioritization.schemas import PriorityWeights
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)
from backend.app.prioritization.service import PrioritizationService


def make_maintenance(
    *,
    priority=Priority.HIGH,
    status=MaintenanceStatus.PENDING,
    duration=120,
    resources=2,
    maintenance_required=True,
    requested_date=date(2026, 9, 22),
):
    return MaintenanceRecord(
        asset_id="ASSET-001",
        asset_type="Track",
        location="Chennai",
        maintenance_type="Inspection",
        maintenance_required=maintenance_required,
        priority=priority,
        duration_minutes=duration,
        requested_date=requested_date,
        preferred_start="10:00",
        required_resources=resources,
        equipment="Inspection Kit",
        status=status,
        source="smms",
    )


def test_all_factors_are_normalized():
    maintenance = make_maintenance()

    prioritizer = MaintenancePrioritizer()

    factors = prioritizer.calculate_factors(
        maintenance,
        reference_date=date(2026, 9, 22),
    )

    assert 0 <= factors.urgency <= 100
    assert 0 <= factors.criticality <= 100
    assert 0 <= factors.overdue_factor <= 100
    assert 0 <= factors.asset_availability_impact <= 100
    assert 0 <= factors.operational_impact <= 100


def test_criticality_mapping():
    prioritizer = MaintenancePrioritizer()

    expected = {
        Priority.LOW: 25.0,
        Priority.MEDIUM: 50.0,
        Priority.HIGH: 75.0,
        Priority.CRITICAL: 100.0,
    }

    for priority, expected_score in expected.items():
        maintenance = make_maintenance(priority=priority)

        factors = prioritizer.calculate_factors(
            maintenance,
            reference_date=date(2026, 9, 22),
        )

        assert factors.criticality == expected_score


def test_overdue_factor_increases_with_overdue_days():
    prioritizer = MaintenancePrioritizer()

    maintenance = make_maintenance(
        requested_date=date(2026, 9, 1),
    )

    factors = prioritizer.calculate_factors(
        maintenance,
        reference_date=date(2026, 9, 22),
    )

    assert factors.overdue_factor > 0


def test_overdue_factor_is_zero_when_not_overdue():
    prioritizer = MaintenancePrioritizer()

    maintenance = make_maintenance(
        requested_date=date(2026, 9, 22),
    )

    factors = prioritizer.calculate_factors(
        maintenance,
        reference_date=date(2026, 9, 22),
    )

    assert factors.overdue_factor == 0


def test_longer_maintenance_has_higher_asset_impact():
    prioritizer = MaintenancePrioritizer()

    short_job = make_maintenance(duration=60)
    long_job = make_maintenance(duration=480)

    short_factors = prioritizer.calculate_factors(short_job)
    long_factors = prioritizer.calculate_factors(long_job)

    assert long_factors.asset_availability_impact > (
        short_factors.asset_availability_impact
    )


def test_more_resources_increase_operational_impact():
    prioritizer = MaintenancePrioritizer()

    low_resource_job = make_maintenance(resources=1)
    high_resource_job = make_maintenance(resources=10)

    low_factors = prioritizer.calculate_factors(low_resource_job)
    high_factors = prioritizer.calculate_factors(high_resource_job)

    assert high_factors.operational_impact > (
        low_factors.operational_impact
    )


def test_weighted_score_is_deterministic():
    prioritizer = MaintenancePrioritizer()

    factors = {
        "urgency": 80,
        "criticality": 60,
        "overdue_factor": 40,
        "asset_availability_impact": 20,
        "operational_impact": 50,
    }

    from backend.app.prioritization.schemas import PriorityFactors

    priority_factors = PriorityFactors(**factors)

    score_1 = prioritizer.calculate_score(priority_factors)
    score_2 = prioritizer.calculate_score(priority_factors)

    assert score_1 == score_2


def test_different_weights_change_score():
    from backend.app.prioritization.schemas import PriorityFactors

    factors = PriorityFactors(
        urgency=100,
        criticality=50,
        overdue_factor=50,
        asset_availability_impact=50,
        operational_impact=50,
    )

    default_prioritizer = MaintenancePrioritizer()

    urgency_heavy = MaintenancePrioritizer(
        weights=PriorityWeights(
            urgency=0.60,
            criticality=0.10,
            overdue_factor=0.10,
            asset_availability_impact=0.10,
            operational_impact=0.10,
        )
    )

    default_score = default_prioritizer.calculate_score(factors)
    urgency_score = urgency_heavy.calculate_score(factors)

    assert urgency_score > default_score


def test_prioritize_returns_complete_information():
    maintenance = make_maintenance()

    prioritizer = MaintenancePrioritizer()

    result = prioritizer.prioritize(
        maintenance,
        reference_date=date(2026, 9, 22),
    )

    assert result.maintenance_id == "ASSET-001"
    assert 0 <= result.priority_value <= 100
    assert result.explanation
    assert 0 <= result.confidence <= 1


def test_completed_maintenance_has_zero_urgency():
    maintenance = make_maintenance(
        status=MaintenanceStatus.COMPLETED,
    )

    prioritizer = MaintenancePrioritizer()

    factors = prioritizer.calculate_factors(maintenance)

    assert factors.urgency == 0


def test_not_required_maintenance_has_zero_urgency():
    maintenance = make_maintenance(
        maintenance_required=False,
    )

    prioritizer = MaintenancePrioritizer()

    factors = prioritizer.calculate_factors(maintenance)

    assert factors.urgency == 0


def test_service_prioritizes_one_maintenance_record():
    maintenance = make_maintenance()

    service = PrioritizationService()

    result = service.prioritize(
        maintenance,
        reference_date=date(2026, 9, 22),
    )

    assert result.maintenance_id == "ASSET-001"
    assert 0 <= result.priority_value <= 100


def test_service_prioritizes_multiple_maintenance_records():
    first = make_maintenance(
        priority=Priority.HIGH,
    )

    second = make_maintenance(
        priority=Priority.CRITICAL,
    )

    service = PrioritizationService()

    results = service.prioritize_many(
        [first, second],
        reference_date=date(2026, 9, 22),
    )

    assert len(results) == 2
    assert results[0].maintenance_id == "ASSET-001"
    assert results[1].maintenance_id == "ASSET-001"
    assert results[1].priority_value > results[0].priority_value