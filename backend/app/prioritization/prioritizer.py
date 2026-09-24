"""
AI Prioritization Adapter and Contract Interface (Phase 5).

DISCLAIMER:
AI integration contract prepared, but no AI/ML inference model is currently implemented.
This module provides the canonical integration adapter and data contracts for
future ML/AI prioritization models.

Conceptual model:
    Priority Factors (inputs)
        urgency          — time-sensitivity derived from maintenance/deadline data
        criticality      — asset safety importance from maintenance/asset records
        overdue_factor   — temporal signal: how overdue the maintenance is
                ↓
        AIPrioritizer.scorer  (future rules-based or ML implementation)
                ↓
        priority_value   — derived authoritative numerical score consumed by CP-SAT

Future factors (NOT currently supported, require richer data/AI capability):
    asset_availability_impact — needs asset/network relationship data
    operational_impact        — needs historical operational datasets

When AI enrichment is absent or scoring fails, the adapter gracefully falls back
to the legacy Priority enum without fabricating arbitrary default scores.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Union

from backend.app.schemas.unified_data import MaintenanceRecord, Priority, PriorityEnrichment

logger = logging.getLogger(__name__)


class AIPrioritizer:
    """
    Contract interface and adapter for AI Prioritization in the Railway Block Planner pipeline.

    Connects external rules-based or ML/AI scoring implementations with MaintenanceRecord models.
    The scorer's responsibility is to derive priority_value from the three currently-supported
    priority factors (urgency, criticality, overdue_factor) and attach them as a
    PriorityEnrichment payload for explainability and downstream CP-SAT consumption.

    When no scorer is registered, or when scoring fails, the adapter falls back gracefully
    to the legacy categorical Priority without fabricating an arbitrary numerical score.
    """

    def __init__(
        self,
        scorer: Optional[Callable[[MaintenanceRecord], Optional[PriorityEnrichment]]] = None,
    ) -> None:
        """
        Initialize the prioritizer adapter.

        Args:
            scorer: Optional callable that takes a MaintenanceRecord and returns
                    a PriorityEnrichment object. If None, no dynamic model scoring is invoked.
        """
        self.scorer = scorer

    def enrich_record(
        self,
        record: MaintenanceRecord,
        enrichment: Optional[PriorityEnrichment] = None,
    ) -> MaintenanceRecord:
        """
        Attach an AI prioritization enrichment payload to a MaintenanceRecord.

        If enrichment is provided explicitly, it is validated and attached.
        If a scorer callable is registered and no enrichment was provided,
        the scorer is evaluated inside a protected try-except block.
        If no enrichment is available or scoring fails, the record retains its legacy
        Priority without fabricating an arbitrary priority_value.

        Returns:
            The modified MaintenanceRecord (mutated in-place and returned).
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

        # If record already has an enrichment attached, ensure priority_value is in sync
        if record.priority_enrichment is not None:
            record.priority_value = record.priority_enrichment.priority_value
        elif record.priority_value is None:
            # Explicitly do NOT fabricate a fake score (e.g. 50.0). Keep None so downstream
            # relies on legacy Priority.
            pass

        return record

    def enrich_records(
        self,
        records: List[MaintenanceRecord],
        enrichments: Optional[Dict[str, PriorityEnrichment]] = None,
    ) -> List[MaintenanceRecord]:
        """
        Batch enrich a collection of maintenance records.

        Args:
            records: List of maintenance records to enrich.
            enrichments: Optional mapping of asset_id (or index/identifier) to PriorityEnrichment.

        Returns:
            The list of enriched maintenance records.
        """
        enrichments_map = enrichments or {}
        for r in records:
            enr = enrichments_map.get(r.asset_id)
            self.enrich_record(r, enrichment=enr)
        return records
