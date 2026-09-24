"""
Deterministic maintenance prioritization engine.

The engine converts unified MaintenanceRecord data into five
normalized priority factors and calculates a weighted priority score.

No LLM is used to make the final priority decision.
"""

from __future__ import annotations

from datetime import date

from backend.app.schemas.unified_data import MaintenanceRecord, Priority

from .schemas import (
    PriorityFactors,
    PriorityInformation,
    PriorityWeights,
)


class MaintenancePrioritizer:
    """Generate explainable and deterministic maintenance priorities."""

    def __init__(self, weights: PriorityWeights | None = None) -> None:
        self.weights = weights or PriorityWeights()

    def calculate_factors(
        self,
        maintenance: MaintenanceRecord,
        reference_date: date | None = None,
    ) -> PriorityFactors:
        """Calculate the five normalized prioritization factors."""

        reference_date = reference_date or date.today()

        return PriorityFactors(
            urgency=self._urgency(maintenance),
            criticality=self._criticality(maintenance),
            overdue_factor=self._overdue_factor(
                maintenance,
                reference_date,
            ),
            asset_availability_impact=self._asset_availability_impact(
                maintenance
            ),
            operational_impact=self._operational_impact(maintenance),
        )

    def calculate_score(self, factors: PriorityFactors) -> float:
        """Calculate the deterministic weighted priority score."""

        score = (
            self.weights.urgency * factors.urgency
            + self.weights.criticality * factors.criticality
            + self.weights.overdue_factor * factors.overdue_factor
            + self.weights.asset_availability_impact
            * factors.asset_availability_impact
            + self.weights.operational_impact
            * factors.operational_impact
        )

        return round(score, 2)

    def prioritize(
        self,
        maintenance: MaintenanceRecord,
        reference_date: date | None = None,
        maintenance_id: str | None = None
    ) -> PriorityInformation:
        """Generate complete priority information for one maintenance record."""

        factors = self.calculate_factors(
            maintenance,
            reference_date=reference_date,
        )

        score = self.calculate_score(factors)

        explanation = (
            f"Priority score {score:.2f}/100 based on "
            f"urgency {factors.urgency:.1f}, "
            f"criticality {factors.criticality:.1f}, "
            f"overdue factor {factors.overdue_factor:.1f}, "
            f"asset availability impact "
            f"{factors.asset_availability_impact:.1f}, "
            f"and operational impact {factors.operational_impact:.1f}."
        )

        return PriorityInformation(
            maintenance_id=maintenance_id or maintenance.asset_id,
            factors=factors,
            priority_value=score,
            explanation=explanation,
            confidence=self._confidence(maintenance),
        )

    @staticmethod
    def _urgency(maintenance: MaintenanceRecord) -> float:
        """Convert maintenance status into an urgency score."""

        mapping = {
            "Pending": 70.0,
            "Approved": 85.0,
            "Completed": 0.0,
            "Cancelled": 0.0,
        }

        if not maintenance.maintenance_required:
            return 0.0

        return mapping.get(maintenance.status.value, 50.0)

    @staticmethod
    def _criticality(maintenance: MaintenanceRecord) -> float:
        """Convert source maintenance priority into a normalized score."""

        mapping = {
            Priority.LOW: 25.0,
            Priority.MEDIUM: 50.0,
            Priority.HIGH: 75.0,
            Priority.CRITICAL: 100.0,
        }

        return mapping[maintenance.priority]

    @staticmethod
    def _overdue_factor(
        maintenance: MaintenanceRecord,
        reference_date: date,
    ) -> float:
        """Increase the score as the requested maintenance date becomes overdue."""

        days_overdue = (
            reference_date - maintenance.requested_date
        ).days

        if days_overdue <= 0:
            return 0.0

        # Saturates at 100 after 30 overdue days.
        return min(100.0, (days_overdue / 30.0) * 100.0)

    @staticmethod
    def _asset_availability_impact(
        maintenance: MaintenanceRecord,
    ) -> float:
        """Estimate asset availability impact from maintenance duration."""

        # 8 hours or more is treated as maximum impact.
        return min(100.0, (maintenance.duration_minutes / 480.0) * 100.0)

    @staticmethod
    def _operational_impact(
        maintenance: MaintenanceRecord,
    ) -> float:
        """Estimate operational impact from resources and maintenance state."""

        resource_score = min(
            100.0,
            (maintenance.required_resources / 10.0) * 100.0,
        )

        required_score = 100.0 if maintenance.maintenance_required else 0.0

        return round(
            (resource_score * 0.4) + (required_score * 0.6),
            2,
        )

    @staticmethod
    def _confidence(
        maintenance: MaintenanceRecord,
    ) -> float:
        """Calculate confidence from completeness of available inputs."""

        available_fields = [
            maintenance.asset_id,
            maintenance.asset_type,
            maintenance.location,
            maintenance.maintenance_type,
            maintenance.equipment,
            maintenance.requested_date,
            maintenance.duration_minutes,
            maintenance.required_resources,
            maintenance.priority,
            maintenance.status,
        ]

        completeness = sum(
            value is not None and value != ""
            for value in available_fields
        ) / len(available_fields)

        return round(completeness, 2)