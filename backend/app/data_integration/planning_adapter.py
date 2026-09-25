"""
Adapters between existing unified data models and planning contracts.
"""

from __future__ import annotations

from backend.app.schemas.planning_contracts import MaintenanceWork
from backend.app.schemas.unified_data import MaintenanceRecord


def maintenance_record_to_work(
    record: MaintenanceRecord,
) -> MaintenanceWork:
    """Convert an existing MaintenanceRecord into the planning contract."""

    return MaintenanceWork(
        maintenance_id=record.asset_id,
        asset_id=record.asset_id,
        asset_type=record.asset_type,
        location=record.location,
        maintenance_type=record.maintenance_type,
        maintenance_required=record.maintenance_required,
        priority=record.priority,
        duration_minutes=record.duration_minutes,
        requested_date=record.requested_date,
        preferred_start=record.preferred_start,
        required_resources=record.required_resources,
        equipment=record.equipment,
        status=record.status.value,
        source=record.source,
    )


def maintenance_records_to_work(
    records: list[MaintenanceRecord],
) -> list[MaintenanceWork]:
    """Convert multiple unified maintenance records."""

    return [
        maintenance_record_to_work(record)
        for record in records
    ]