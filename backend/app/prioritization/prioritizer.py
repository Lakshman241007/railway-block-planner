"""
Deterministic maintenance prioritization engine and adapter (Phase 5 & AI Prioritization Contract).

Includes:
- MaintenancePrioritizer: Generates the 5 normalized factors and deterministic weighted scores.
- AIPrioritizer: Adapter class for CP-SAT pipeline integration and batch record enrichment.
"""

from __future__ import annotations

from datetime import date
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from backend.app.schemas.unified_data import MaintenanceRecord, Priority, PriorityEnrichment
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
from .service import PrioritizationService

logger = logging.getLogger(__name__)


class MaintenancePrioritizer:
    """Generate explainable and deterministic maintenance priorities."""

    def __init__(self, weights: Optional[PriorityWeights] = None) -> None:
        self.weights = weights or PriorityWeights()
        self.service = PrioritizationService(weights=self.weights)

    def calculate_factors(
        self,
        maintenance: MaintenanceRecord,
        reference_date: Optional[date] = None,
    ) -> PriorityFactors:
        """Calculate the five normalized prioritization factors."""
        return self.service.calculate_factors(maintenance, reference_date=reference_date)

    def calculate_score(self, factors: PriorityFactors) -> float:
        """Calculate the deterministic weighted priority score."""
        return self.service.scorer.calculate_score(factors, weights=self.weights)

    def prioritize(
        self,
        maintenance: MaintenanceRecord,
        reference_date: Optional[date] = None,
        maintenance_id: Optional[str] = None,
    ) -> PriorityInformation:
        """Generate complete priority information for one maintenance record."""
        return self.service.prioritize(
            maintenance,
            reference_date=reference_date,
            maintenance_id=maintenance_id,
        )

    # Static helpers for direct individual factor access
    @staticmethod
    def _urgency(maintenance: MaintenanceRecord) -> float:
        return compute_urgency(maintenance)

    @staticmethod
    def _criticality(maintenance: MaintenanceRecord) -> float:
        return compute_criticality(maintenance)

    @staticmethod
    def _overdue_factor(maintenance: MaintenanceRecord, reference_date: date) -> float:
        return compute_overdue_factor(maintenance, reference_date=reference_date)

    @staticmethod
    def _asset_availability_impact(maintenance: MaintenanceRecord) -> float:
        return compute_asset_availability_impact(maintenance)

    @staticmethod
    def _operational_impact(maintenance: MaintenanceRecord) -> float:
        return compute_operational_impact(maintenance)

    @staticmethod
    def _confidence(maintenance: MaintenanceRecord) -> float:
        return compute_confidence(maintenance)


class AIPrioritizer:
    """
    Contract interface and adapter for AI Prioritization in the Railway Block Planner pipeline (Phase 5).

    Connects external rules-based or ML/AI scoring implementations with MaintenanceRecord models.
    The scorer's responsibility is to derive priority_value and attach PriorityEnrichment
    for explainability and downstream CP-SAT consumption.
    """

    def __init__(
        self,
        scorer: Optional[Callable[[MaintenanceRecord], Optional[PriorityEnrichment]]] = None,
    ) -> None:
        self.scorer = scorer

    def enrich_record(
        self,
        record: MaintenanceRecord,
        enrichment: Optional[PriorityEnrichment] = None,
    ) -> MaintenanceRecord:
        """
        Attach an AI prioritization enrichment payload to a MaintenanceRecord.
        """
        if enrichment is not None:
            record.priority_enrichment = enrichment
            record.priority_value = enrichment.priority_value
            return record

        if self.scorer is not None:
            try:
                predicted = self.scorer(record)
                if predicted is not None:
                    record.priority_enrichment = predicted
                    record.priority_value = predicted.priority_value
                    return record
            except Exception as e:
                logger.warning(
                    f"AI Prioritizer scoring failed for asset {record.asset_id}: {e}. "
                    "Gracefully falling back to legacy priority."
                )

        if record.priority_enrichment is not None:
            record.priority_value = record.priority_enrichment.priority_value

        return record

    def enrich_records(
        self,
        records: List[MaintenanceRecord],
        enrichments: Optional[Dict[str, PriorityEnrichment]] = None,
    ) -> List[MaintenanceRecord]:
        """
        Batch enrich a collection of maintenance records.
        """
        enrichments_map = enrichments or {}
        for r in records:
            enr = enrichments_map.get(r.asset_id)
            self.enrich_record(r, enrichment=enr)
        return records


__all__ = [
    "MaintenancePrioritizer",
    "AIPrioritizer",
]
