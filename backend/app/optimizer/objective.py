"""
CP-SAT Soft Multi-Objective Engine (Phase 5 / Phase 6).

Formulates the weighted multi-criteria objective function for CP-SAT:
1. Maximize total scheduled maintenance throughput
2. Single priority signal — one priority utility term per work item:
       if priority_value is not None  →  W_priority_value × priority_value
       if priority_value is None      →  legacy categorical bonus (fallback only)
   priority_value is the DERIVED result produced by AIPrioritizer from the
   currently-supported factors (urgency, criticality, overdue_factor).
   It is the authoritative optimization signal; the categorical label
   (Critical / High / Medium / Low) is retained only as a human-readable
   classification and as a legacy fallback for unscored records.
3. Minimize temporal deviation from requested preferred start times
4. Penalize operational disruption and suboptimal slot fits

Backward compatibility rule:
    When priority_value is not None — ONLY the numerical term applies.
    When priority_value is None     — ONLY the categorical bonus applies.
    These two paths are mutually exclusive; they are never both counted.

PROTOTYPE DISCLAIMER:
Objective weights and scoring formulations are prototype assumptions for the
hackathon demonstration and are NOT official railway operating rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from backend.app.optimizer.schemas import ObjectiveWeights
from backend.app.schemas.unified_data import Priority

logger = logging.getLogger(__name__)


def get_priority_weight(priority: Priority, weights: ObjectiveWeights) -> int:
    """
    Return the configured integer weight for the given categorical priority level.

    Used ONLY as a legacy fallback when priority_value is None.
    When priority_value is present, the caller must use the numerical path instead.
    """
    if priority == Priority.CRITICAL:
        return weights.weight_priority_critical
    elif priority == Priority.HIGH:
        return weights.weight_priority_high
    elif priority == Priority.MEDIUM:
        return weights.weight_priority_medium
    elif priority == Priority.LOW:
        return weights.weight_priority_low
    return weights.weight_priority_low


def compute_slot_coefficient(
    meta: Dict[str, Any],
    weights: ObjectiveWeights,
) -> int:
    """
    Calculate the net integer objective coefficient for assigning a maintenance
    request to a specific candidate slot.

    Single-priority rule (XOR — mutually exclusive paths):
    ────────────────────────────────────────────────────
    if priority_value is not None:
        priority_utility = W_priority_value × priority_value
        (categorical Priority label is ignored for objective purposes)

    if priority_value is None:
        priority_utility = get_priority_weight(priority)   [legacy fallback]
        (no numerical score is available; categorical label is used instead)

    These two paths are NEVER applied simultaneously.

    Full formula:
        coeff = W_scheduled
              + priority_utility   [exactly one of the two paths above]
              - W_dev × |start_mins + day_shift×1440 - pref_mins|
              - (W_disruption × int((1 − fit_score) × 100)) // 10

    priority_contribution stored in meta reflects ONLY the numerical term
    (W_priority_value × priority_value), or 0 when the legacy path is active.
    """
    # 1. Base scheduling reward
    coeff = weights.weight_scheduled

    # 2. Single priority utility — XOR between numerical and legacy categorical paths
    priority_value = meta.get("priority_value")
    priority_contribution = 0

    if priority_value is not None:
        # Numerical path: priority_value is the sole priority signal.
        # The categorical Priority label is intentionally excluded from the
        # objective here; it serves only as a human-readable classification.
        try:
            p_val = float(priority_value)
            priority_contribution = int(round(weights.weight_priority_value * p_val))
            coeff += priority_contribution
        except (ValueError, TypeError):
            # Malformed priority_value — fall back to categorical to avoid
            # silently dropping all priority information.
            priority = meta.get("priority", Priority.LOW)
            coeff += get_priority_weight(priority, weights)

    else:
        # Legacy fallback path: no numerical priority score is available.
        # Use categorical Priority to preserve backward compatibility for
        # records that have not been through the AI prioritization layer.
        priority = meta.get("priority", Priority.LOW)
        coeff += get_priority_weight(priority, weights)

    # priority_contribution captures only the numerical term for explainability.
    # It is 0 when the legacy categorical path is active.
    meta["priority_contribution"] = priority_contribution

    # 3. Preferred start time & date deviation penalty (in absolute timeline minutes)
    start_mins = meta.get("start_minutes", 0)
    pref_mins = meta.get("preferred_start_minutes", start_mins)
    day_shift = meta.get("day_shift", 0)
    total_deviation = abs(day_shift * 1440 + start_mins - pref_mins)
    coeff -= weights.weight_preferred_deviation * total_deviation

    # 4. Disruption / slot fit degradation penalty
    fit_score = meta.get("fit_score", 1.0)
    disruption_penalty = int(round((1.0 - max(0.0, min(1.0, fit_score))) * 100))
    coeff -= (weights.weight_disruption * disruption_penalty) // 10

    # 5. Optional block utilization reward (Rule 9: integer scaling)
    if getattr(weights, "weight_block_utilization", 0) > 0:
        dur = meta.get("duration_minutes", 0)
        coeff += weights.weight_block_utilization * dur

    # 6. Optional operational efficiency reward (Rule 9: integer scaling)
    if getattr(weights, "weight_operational_efficiency", 0) > 0:
        eff_bonus = int(round(max(0.0, min(1.0, fit_score)) * 100))
        coeff += (weights.weight_operational_efficiency * eff_bonus) // 10

    return coeff


def build_optimization_objective(
    model: cp_model.CpModel,
    slot_vars: Dict[Tuple[str, str], cp_model.IntVar],
    slot_metadata: Dict[str, Dict[str, Any]],
    weights: ObjectiveWeights,
) -> Dict[Tuple[str, str], int]:
    """
    Constructs and attaches the linear maximization objective to the CP-SAT model.

    Returns the dictionary of computed coefficients for telemetry and logging.
    """
    objective_terms = []
    coefficients: Dict[Tuple[str, str], int] = {}

    for (req_id, s_id), var in slot_vars.items():
        meta = slot_metadata.get(s_id, {})
        coeff = compute_slot_coefficient(meta, weights)
        coefficients[(req_id, s_id)] = coeff
        objective_terms.append(coeff * var)

    if objective_terms:
        model.Maximize(sum(objective_terms))
    else:
        model.Maximize(0)

    return coefficients
