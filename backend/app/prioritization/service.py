"""
Service layer for maintenance prioritization.
"""

from __future__ import annotations

from datetime import date

from backend.app.schemas.unified_data import MaintenanceRecord

from .prioritizer import MaintenancePrioritizer
from .schemas import PriorityInformation, PriorityWeights


class PrioritizationService:
    """Provides application-level maintenance prioritization."""

    def __init__(
        self,
        weights: PriorityWeights | None = None,
    ) -> None:
        self.prioritizer = MaintenancePrioritizer(weights=weights)

    def prioritize(
        self,
        maintenance: MaintenanceRecord,
        reference_date: date | None = None,
        maintenance_id: str | None = None
    ) -> PriorityInformation:
        """Generate priority information for one maintenance record."""

        return self.prioritizer.prioritize(
            maintenance,
            reference_date=reference_date,
            maintenance_id=maintenance_id
        )

    def prioritize_many(
        self,
        maintenance_records: list[MaintenanceRecord],
        reference_date: date | None = None,
    ) -> list[PriorityInformation]:
        """Generate priority information for multiple maintenance records."""

        return [
            self.prioritize(
                maintenance,
                reference_date=reference_date,
            )
            for maintenance in maintenance_records
        ]