"""
Plans API endpoints (Phase 5 — Final Block Planner Integration).

Exposes:
  POST /api/plans/generate   — Phase 4 heuristic block plan (Forecast + Scheduler + Conflict Detection)
  POST /api/plans/optimize   — Phase 5 CP-SAT optimized block plan (persisted to DB)
  GET  /api/plans/optimized  — List all persisted optimized plan summaries
  GET  /api/plans/optimized/latest  — Retrieve latest plan for a target date
  GET  /api/plans/optimized/{plan_id} — Retrieve plan by ID (full OptimizationResult)
  GET  /api/plans            — Block requests as block planning view (operational data)

Plan Persistence:
  Every call to POST /api/plans/optimize generates a plan_id, runs the CP-SAT solver,
  persists the result to the optimized_plans table, and returns the OptimizationResult.
  Subsequent GET requests can retrieve the plan without re-running the solver.

Block Status Update:
  After a successful optimization (OPTIMAL or FEASIBLE), scheduled blocks have their
  DB status updated from Requested → Approved, reflecting truthful lifecycle tracking.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.block_planner.planner import BlockPlanner
from backend.app.block_planner.schemas import BlockPlanRequest, BlockPlanResult
from backend.app.database.repositories import BlockRepository, OptimizedPlanRepository
from backend.app.optimizer.schemas import OptimizationRequest, OptimizationResult
from backend.app.optimizer.validator import validate_final_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


# ---------------------------------------------------------------------------
# GET /api/plans — Block planning requests view (operational data)
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="Get BDMS block requests as planning view",
    response_description="List of block planning requests from BDMS",
)
def get_plans(
    status: Optional[str] = Query(None, description="Filter by status (e.g. Approved, Requested)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieve stored BDMS block planning requests from the database.
    For CP-SAT optimization results, use GET /api/plans/optimized.
    """
    repo = BlockRepository(db)
    blocks = repo.get_all(status=status, skip=skip, limit=limit)
    total_count = repo.count(status=status)
    return {
        "data": [b.to_dict() for b in blocks],
        "count": len(blocks),
        "total": total_count,
        "note": "Use POST /api/plans/optimize to run CP-SAT optimization. Use GET /api/plans/optimized to retrieve persisted plans.",
    }


# ---------------------------------------------------------------------------
# GET /api/plans/optimized — List persisted optimized plans
# ---------------------------------------------------------------------------

@router.get(
    "/optimized",
    summary="List persisted CP-SAT optimized plan summaries",
    response_description="List of plan summaries ordered by generation time (newest first)",
)
def list_optimized_plans(
    target_date: Optional[str] = Query(None, description="Filter by target date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List all persisted CP-SAT optimization plan summaries.
    Returns metadata (plan_id, status, counts, timestamps) without the full result JSON.
    Use GET /api/plans/optimized/{plan_id} for the full OptimizationResult.
    """
    repo = OptimizedPlanRepository(db)
    plans = repo.get_all(target_date=target_date, skip=skip, limit=limit)
    total = repo.count(target_date=target_date)
    return {
        "data": [p.to_dict() for p in plans],
        "count": len(plans),
        "total": total,
    }


# ---------------------------------------------------------------------------
# GET /api/plans/optimized/latest — Latest plan for a target date
# ---------------------------------------------------------------------------

@router.get(
    "/optimized/latest",
    summary="Retrieve the latest persisted optimized plan for a target date",
    response_description="Full OptimizationResult for the most recent plan on the requested date",
)
def get_latest_optimized_plan(
    target_date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD). Defaults to today."),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieve the most recently generated CP-SAT plan for a given target date.

    This endpoint is used by the frontend to restore the optimization result
    after a browser refresh without re-running the solver.

    Returns 404 if no plan has been generated for the specified date.
    """
    target_d_str = target_date or date.today().isoformat()
    repo = OptimizedPlanRepository(db)
    plan = repo.get_latest_by_date(target_d_str)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail=f"No optimized plan found for target date '{target_d_str}'. Run POST /api/plans/optimize first.",
        )
    try:
        result_data = json.loads(plan.result_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stored plan '{plan.plan_id}' has corrupted JSON payload: {exc}",
        )
    return {
        "plan_meta": plan.to_dict(),
        "result": result_data,
    }


# ---------------------------------------------------------------------------
# GET /api/plans/optimized/{plan_id} — Retrieve plan by ID
# ---------------------------------------------------------------------------

@router.get(
    "/optimized/{plan_id}",
    summary="Retrieve a specific optimized plan by plan_id",
    response_description="Full OptimizationResult for the specified plan",
)
def get_optimized_plan_by_id(
    plan_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieve a specific CP-SAT optimization result by its unique plan_id.
    Returns the full OptimizationResult including scheduled_blocks and unscheduled_blocks.
    """
    repo = OptimizedPlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail=f"Optimized plan '{plan_id}' not found.",
        )
    try:
        result_data = json.loads(plan.result_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stored plan '{plan_id}' has corrupted JSON payload: {exc}",
        )
    return {
        "plan_meta": plan.to_dict(),
        "result": result_data,
    }


# ---------------------------------------------------------------------------
# POST /api/plans/generate — Phase 4 heuristic plan (non-persisted)
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    summary="Generate Phase 4 heuristic maintenance block plan (non-persisted)",
    response_model=BlockPlanResult,
)
def generate_block_plan(
    request: Optional[BlockPlanRequest] = None,
    db: Session = Depends(get_db),
) -> BlockPlanResult:
    """
    Generate an end-to-end maintenance block plan orchestrating:
    1. Goods train movement forecast with confidence scoring
    2. Feasible maintenance slot scheduling
    3. Spatial-temporal conflict detection and rule-based resolution recommendations

    Results are NOT persisted. For persisted CP-SAT plans, use POST /api/plans/optimize.
    """
    planner = BlockPlanner(db=db)
    return planner.generate_plan(request=request or BlockPlanRequest())


# ---------------------------------------------------------------------------
# POST /api/plans/optimize — Phase 5 CP-SAT plan (persisted)
# ---------------------------------------------------------------------------

@router.post(
    "/optimize",
    summary="Generate and persist Phase 5 CP-SAT optimized maintenance block plan",
    response_model=OptimizationResult,
)
def optimize_block_plan(
    request: Optional[OptimizationRequest] = None,
    db: Session = Depends(get_db),
) -> OptimizationResult:
    """
    Generate a mathematically optimized maintenance block plan using OR-Tools CP-SAT:
    1. Candidate slot generation across weekly/monthly horizon
    2. Hard constraints (train movement protection, track non-overlap, equipment capacity)
    3. Weighted multi-objective maximization (priority, throughput, minimal deviation)
    4. Independent post-optimization conflict validation
    5. Persistence to DB for retrieval after browser refresh
    6. Block status update: scheduled blocks → Approved in DB

    The plan is persisted with a unique plan_id. Retrieve it via:
      GET /api/plans/optimized/latest?target_date=YYYY-MM-DD
      GET /api/plans/optimized/{plan_id}
    """
    req = request or OptimizationRequest()
    planner = BlockPlanner(db=db)
    result: OptimizationResult = planner.optimize_plan(request=req)

    # -----------------------------------------------------------------------
    # Final plan validation (Phase 5)
    # -----------------------------------------------------------------------
    from backend.app.database.repositories import (
        BlockRepository,
        MaintenanceRepository,
        MovementRepository,
        TimetableRepository,
        TrainRepository,
    )
    from backend.app.forecast.forecast import GoodsTrainForecaster
    from datetime import timedelta

    try:
        trains = [t.to_pydantic() for t in TrainRepository(db).get_all(limit=1000)]
        movements = [m.to_pydantic() for m in MovementRepository(db).get_all(limit=1000)]
        timetables = [tt.to_pydantic() for tt in TimetableRepository(db).get_all(limit=1000)]
        target_d = req.target_date or date.today()

        # Forecast across horizon for validation
        forecaster = GoodsTrainForecaster(trains=trains, movements=movements, timetables=timetables)
        forecast_items = []
        for d_offset in range(req.horizon_days):
            day_date = target_d + timedelta(days=d_offset)
            fc_res = forecaster.predict(target_date=day_date, horizon_hours=24)
            forecast_items.extend(fc_res.forecasts)

        validation = validate_final_plan(
            plan=result,
            trains=trains,
            timetables=timetables,
            goods_forecasts=forecast_items,
            movements=movements,
            buffer_minutes=req.buffer_minutes,
        )
        if not validation["is_valid"]:
            logger.warning(
                "Final plan '%s' failed independent validation: %s",
                result.plan_id,
                validation.get("violations"),
            )
        else:
            logger.info(
                "Final plan '%s' passed independent validation: %s scheduled, 0 conflicts.",
                result.plan_id,
                len(result.scheduled_blocks),
            )
    except Exception as exc:
        logger.warning("Final plan validation error (non-fatal): %s", exc)
        validation = {"is_valid": None, "error": str(exc)}

    # -----------------------------------------------------------------------
    # Update block statuses: scheduled → Approved
    # -----------------------------------------------------------------------
    from backend.app.optimizer.schemas import OptimizationStatus
    if result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
        block_repo = BlockRepository(db)
        scheduled_block_request_ids = {
            b.block_request_id or b.request_id
            for b in result.scheduled_blocks
            if b.block_request_id or b.request_id
        }
        for bid in scheduled_block_request_ids:
            existing = block_repo.get_by_id(bid)
            if existing and existing.status in ("Requested",):
                try:
                    block_repo.update(bid, {"status": "Approved"})
                except Exception as exc:
                    logger.warning("Could not update block status for '%s': %s", bid, exc)

    # -----------------------------------------------------------------------
    # Persist plan to DB
    # -----------------------------------------------------------------------
    plan_repo = OptimizedPlanRepository(db)
    try:
        result_json_str = result.model_dump_json()
        stats = result.solver_statistics
        plan_data = {
            "plan_id": result.plan_id,
            "target_date": str(result.target_date),
            "horizon_days": result.horizon_days,
            "solver_status": result.status.value,
            "objective_value": result.objective_value,
            "num_scheduled": stats.num_scheduled,
            "num_unscheduled": stats.num_unscheduled,
            "total_requests": stats.total_requests,
            "conflicts_before": stats.conflicts_before,
            "conflicts_after": stats.conflicts_after,
            "wall_time_seconds": stats.wall_time_seconds,
            "result_json": result_json_str,
        }
        plan_repo.create(plan_data)
        logger.info("Optimized plan '%s' persisted to DB.", result.plan_id)
    except Exception as exc:
        # Persistence failure must not mask the optimization result
        logger.error("Failed to persist optimized plan '%s': %s", result.plan_id, exc)

    return result
