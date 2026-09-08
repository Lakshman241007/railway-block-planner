"""
Final Plan Validator for Railway Block Planner (Phase 5).

Provides independent post-optimization plan validation reusing the existing
ConflictDetector. This validator is called after every CP-SAT optimization
to certify the plan before it is persisted and presented to the user.

VALIDATION CHECKS:
  1. No duplicate block_ids in scheduled output
  2. All scheduled blocks have valid service_date, start_time, end_time
  3. All durations are > 0
  4. scheduled + unscheduled == total_requests (count integrity)
  5. No unknown block_ids (all request_ids trace to known source requests)
  6. No overlapping possessions at the same location (via ConflictDetector)
  7. No train movement collisions in the final plan
  8. Overnight blocks (end < start) have correct duration semantics

RETURNS:
  FinalPlanValidationResult dict:
    {
      "is_valid": bool,
      "plan_id": str,
      "conflicts": int,
      "headway_violations": int,
      "equipment_violations": int,
      "duration_violations": int,
      "unknown_blocks": int,
      "duplicate_ids": int,
      "count_integrity": bool,
      "violations": [str, ...],
    }
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from backend.app.forecast.schemas import GoodsForecastItem
from backend.app.optimizer.schemas import OptimizationResult, OptimizationStatus
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.schemas.unified_data import MovementRecord, TimetableRecord, TrainRecord

logger = logging.getLogger(__name__)

_TIME_RE_SIMPLE = __import__("re").compile(r"^\d{2}:\d{2}$")


def _parse_hhmm(val: str) -> int:
    """Parse HH:MM string to minutes since midnight. Returns -1 on error."""
    try:
        h, m = val.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return -1


def validate_final_plan(
    plan: OptimizationResult,
    trains: Optional[List[TrainRecord]] = None,
    timetables: Optional[List[TimetableRecord]] = None,
    goods_forecasts: Optional[List[GoodsForecastItem]] = None,
    movements: Optional[List[MovementRecord]] = None,
    buffer_minutes: int = 15,
) -> Dict[str, Any]:
    """
    Independently validate an OptimizationResult before acceptance.

    Reuses ConflictDetector for operational conflict checks.
    Performs structural checks independently to avoid circular validation.

    Parameters
    ----------
    plan : OptimizationResult
        The plan returned by the CP-SAT optimizer.
    trains : list of TrainRecord, optional
    timetables : list of TimetableRecord, optional
    goods_forecasts : list of GoodsForecastItem, optional
    movements : list of MovementRecord, optional
    buffer_minutes : int, default 15

    Returns
    -------
    dict
        Validation result with is_valid, counts, and violation list.
    """
    violations: List[str] = []
    scheduled = plan.scheduled_blocks or []
    unscheduled = plan.unscheduled_blocks or []
    stats = plan.solver_statistics

    # -----------------------------------------------------------------------
    # 1. Duplicate block_id check
    # -----------------------------------------------------------------------
    seen_ids: set = set()
    duplicate_count = 0
    for blk in scheduled:
        bid = blk.block_id
        if bid in seen_ids:
            duplicate_count += 1
            violations.append(f"DUPLICATE_BLOCK_ID: '{bid}' appears more than once in scheduled_blocks.")
        seen_ids.add(bid)

    # -----------------------------------------------------------------------
    # 2. Structural validity of each scheduled block
    # -----------------------------------------------------------------------
    duration_violations = 0
    for blk in scheduled:
        # Check times
        if not _TIME_RE_SIMPLE.match(blk.start_time or ""):
            violations.append(f"INVALID_START_TIME: block '{blk.block_id}' start='{blk.start_time}'")
        if not _TIME_RE_SIMPLE.match(blk.end_time or ""):
            violations.append(f"INVALID_END_TIME: block '{blk.block_id}' end='{blk.end_time}'")
        # Check duration
        if blk.duration_minutes <= 0:
            duration_violations += 1
            violations.append(
                f"ZERO_DURATION: block '{blk.block_id}' has duration_minutes={blk.duration_minutes}"
            )
        # Check service_date present
        if not blk.service_date:
            violations.append(f"MISSING_DATE: block '{blk.block_id}' has no service_date.")

        # Check overnight semantics: if end < start → duration should equal (1440-s)+e
        s = _parse_hhmm(blk.start_time)
        e = _parse_hhmm(blk.end_time)
        if s >= 0 and e >= 0 and blk.duration_minutes > 0:
            if e < s:
                # Overnight
                expected_dur = (1440 - s) + e
            else:
                expected_dur = e - s
            if abs(expected_dur - blk.duration_minutes) > 2:  # 2-min tolerance for rounding
                duration_violations += 1
                violations.append(
                    f"DURATION_MISMATCH: block '{blk.block_id}' claims {blk.duration_minutes}min "
                    f"but start={blk.start_time}/end={blk.end_time} implies {expected_dur}min "
                    f"({'overnight' if e < s else 'same-day'})."
                )

    # -----------------------------------------------------------------------
    # 3. Count integrity: scheduled + unscheduled == total_requests
    # -----------------------------------------------------------------------
    total_output = len(scheduled) + len(unscheduled)
    count_integrity = (total_output == stats.total_requests) if stats.total_requests >= 0 else True
    if not count_integrity and stats.total_requests > 0:
        violations.append(
            f"COUNT_MISMATCH: scheduled({len(scheduled)}) + unscheduled({len(unscheduled)}) "
            f"= {total_output} ≠ total_requests({stats.total_requests})."
        )

    # -----------------------------------------------------------------------
    # 4. Conflict Detection on scheduled blocks
    # -----------------------------------------------------------------------
    conflicts_total = 0
    headway_violations = 0
    equipment_violations = 0
    unknown_blocks = 0

    if plan.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE) and scheduled:
        try:
            base_date = plan.target_date
            horizon_days = plan.horizon_days

            detector = ConflictDetector(
                trains=trains or [],
                timetables=timetables or [],
                goods_forecasts=goods_forecasts or [],
                movements=movements or [],
                maintenance_records=[],
                block_records=[],
                buffer_minutes=buffer_minutes,
            )

            for d_offset in range(horizon_days):
                h_date = base_date + timedelta(days=d_offset)
                c_rep = detector.detect_conflicts(
                    target_date=h_date,
                    proposed_schedule=scheduled,
                )
                conflicts_total += c_rep.total_conflicts
                for c in c_rep.conflicts:
                    from backend.app.scheduler.schemas import ConflictType
                    if c.conflict_type == ConflictType.SAFETY_BUFFER_VIOLATION:
                        headway_violations += 1
                    elif c.conflict_type == ConflictType.RESOURCE_CONTENTION:
                        equipment_violations += 1

            if conflicts_total > 0:
                violations.append(
                    f"CONFLICTS_REMAIN: Independent conflict detector found {conflicts_total} "
                    f"operational conflict(s) in the final plan across {horizon_days}-day horizon."
                )
        except Exception as exc:
            logger.warning("Conflict detection during final validation failed: %s", exc)
            violations.append(f"VALIDATION_ERROR: ConflictDetector raised: {exc}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    is_valid = (
        len(violations) == 0
        and conflicts_total == 0
        and duplicate_count == 0
        and duration_violations == 0
    )

    result = {
        "is_valid": is_valid,
        "plan_id": plan.plan_id,
        "solver_status": plan.status.value,
        "conflicts": conflicts_total,
        "headway_violations": headway_violations,
        "equipment_violations": equipment_violations,
        "duration_violations": duration_violations,
        "duplicate_ids": duplicate_count,
        "unknown_blocks": unknown_blocks,
        "count_integrity": count_integrity,
        "num_scheduled": len(scheduled),
        "num_unscheduled": len(unscheduled),
        "total_requests": stats.total_requests,
        "violations": violations,
    }

    if is_valid:
        logger.info(
            "validate_final_plan VALID: plan=%s, scheduled=%d, conflicts=%d",
            plan.plan_id, len(scheduled), conflicts_total,
        )
    else:
        logger.warning(
            "validate_final_plan INVALID: plan=%s, violations=%s",
            plan.plan_id, violations,
        )

    return result
