"""
Deterministic Weighted Scoring Engine for AI Prioritization.

Calculates final priority score via:
    Priority Value = W1 * Urgency + W2 * Criticality + W3 * Overdue + W4 * Asset Availability + W5 * Operational Impact

Weights are fully configurable via PriorityWeights.
"""

from __future__ import annotations

from typing import Optional
from .schemas import PriorityFactors, PriorityWeights


class PriorityScorer:
    """Calculates deterministic weighted scores using configurable factor weights."""

    def __init__(self, weights: Optional[PriorityWeights] = None) -> None:
        self.weights = weights or PriorityWeights()

    def calculate_score(
        self,
        factors: PriorityFactors,
        weights: Optional[PriorityWeights] = None,
    ) -> float:
        """
        Calculate deterministic priority value (0–100).
        """
        w = weights or self.weights
        total_weight = (
            w.urgency
            + w.criticality
            + w.overdue_factor
            + w.asset_availability_impact
            + w.operational_impact
        )
        if total_weight <= 0:
            return 0.0

        raw_score = (
            w.urgency * factors.urgency
            + w.criticality * factors.criticality
            + w.overdue_factor * factors.overdue_factor
            + w.asset_availability_impact * factors.asset_availability_impact
            + w.operational_impact * factors.operational_impact
        )

        # Normalize if weights don't sum to exactly 1.0
        normalized_score = raw_score / total_weight if abs(total_weight - 1.0) > 1e-4 else raw_score
        return round(min(100.0, max(0.0, normalized_score)), 2)
