"""
Prioritization service coordinating factor generation, scoring, and result payload assembly.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Union

from backend.app.schemas.unified_data import MaintenanceRecord
from .factors import (
    compute_asset_availability_impact,
    compute_confidence,
    compute_criticality,
    compute_operational_impact,
    compute_overdue_factor,
    compute_urgency,
    generate_explanation,
)
from .schemas import (
    MaintenancePriority,
    PriorityFactors,
    PriorityInformation,
    PriorityWeights,
)
from .scorer import PriorityScorer


class PrioritizationService:
    """Orchestrates AI prioritization reasoning and deterministic factor scoring."""

    def __init__(self, weights: Optional[PriorityWeights] = None) -> None:
        self.weights = weights or PriorityWeights()
        self.scorer = PriorityScorer(weights=self.weights)

    def calculate_factors(
        self,
        maintenance: Union[MaintenanceRecord, Any],
        reference_date: Optional[date] = None,
    ) -> PriorityFactors:
        """Calculate the five normalized 0-100 factors."""
        return PriorityFactors(
            urgency=compute_urgency(maintenance),
            criticality=compute_criticality(maintenance),
            overdue_factor=compute_overdue_factor(maintenance, reference_date=reference_date),
            asset_availability_impact=compute_asset_availability_impact(maintenance),
            operational_impact=compute_operational_impact(maintenance),
        )

    def prioritize(
        self,
        maintenance: Union[MaintenanceRecord, Any],
        reference_date: Optional[date] = None,
        maintenance_id: Optional[str] = None,
        weights: Optional[PriorityWeights] = None,
    ) -> PriorityInformation:
        """Calculate complete PriorityInformation object for one record."""
        active_weights = weights or self.weights
        factors = self.calculate_factors(maintenance, reference_date=reference_date)
        score = self.scorer.calculate_score(factors, weights=active_weights)
        m_id = maintenance_id or getattr(maintenance, "asset_id", None) or getattr(maintenance, "maintenance_id", "MNT")
        explanation = generate_explanation(factors, score, asset_name=m_id)
        confidence = compute_confidence(maintenance)

        return PriorityInformation(
            maintenance_id=m_id,
            factors=factors,
            priority_value=score,
            explanation=explanation,
            confidence=confidence,
        )

    def prioritize_as_maintenance_priority(
        self,
        maintenance: Union[MaintenanceRecord, Any],
        reference_date: Optional[date] = None,
        maintenance_id: Optional[str] = None,
        weights: Optional[PriorityWeights] = None,
    ) -> MaintenancePriority:
        """Return flat MaintenancePriority schema matching SIH26 specification."""
        info = self.prioritize(maintenance, reference_date=reference_date, maintenance_id=maintenance_id, weights=weights)
        return MaintenancePriority(
            maintenance_id=info.maintenance_id,
            urgency=info.factors.urgency,
            criticality=info.factors.criticality,
            overdue_factor=info.factors.overdue_factor,
            asset_availability_impact=info.factors.asset_availability_impact,
            operational_impact=info.factors.operational_impact,
            priority_value=info.priority_value,
            explanation=info.explanation,
            confidence=info.confidence,
            factors=info.factors,
        )

    def prioritize_batch(
        self,
        items: List[Union[MaintenanceRecord, Any]],
        reference_date: Optional[date] = None,
        weights: Optional[PriorityWeights] = None,
    ) -> List[PriorityInformation]:
        """Prioritize a batch of maintenance records."""
        return [self.prioritize(item, reference_date=reference_date, weights=weights) for item in items]

    def prioritize_many(
        self,
        items: List[Union[MaintenanceRecord, Any]],
        reference_date: Optional[date] = None,
        weights: Optional[PriorityWeights] = None,
    ) -> List[PriorityInformation]:
        """Alias for prioritize_batch."""
        return self.prioritize_batch(items, reference_date=reference_date, weights=weights)