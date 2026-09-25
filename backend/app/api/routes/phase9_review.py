"""
Phase 9 — Human-in-the-Loop Conflict Review & Plan Verification API Routes.

Exposes backend endpoints for:
  GET  /api/conflicts/review           — List conflicts requiring human review
  GET  /api/conflicts/review/all       — List all tracked conflicts with lifecycle state
  POST /api/conflicts/{conflict_id}/resolve  — Human-resolve a conflict
  POST /api/conflicts/{conflict_id}/reject   — Reject a conflict resolution
  POST /api/conflicts/{conflict_id}/defer    — Defer a conflict for later review
  POST /api/conflicts/process          — Process a conflict report through escalation
  POST /api/plans/{plan_id}/submit-review    — Submit plan for operator review
  POST /api/plans/{plan_id}/approve    — Approve a plan
  POST /api/plans/{plan_id}/publish    — Publish an approved plan
  GET  /api/plans/published            — Employee-facing: only APPROVED/PUBLISHED plans

Routes remain thin — business logic is in human_review_service.py.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.database.repositories import OptimizedPlanRepository
from backend.app.schemas.phase9_schemas import (
    ConflictReviewItem,
    ConflictStatus,
    HumanReviewAction,
    HumanReviewRequest,
    PlanApprovalRequest,
    PlanStatus,
    PlanStatusResponse,
)
from backend.app.services.human_review_service import (
    ConflictReviewService,
    EscalatingAutoResolver,
    PlanVerificationService,
    get_conflict_store,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conflict Review Router
# ---------------------------------------------------------------------------

conflicts_router = APIRouter(prefix="/conflicts", tags=["Conflict Review (Phase 9)"])


@conflicts_router.get(
    "/review",
    summary="List conflicts requiring human review",
    response_description="Conflicts in REQUIRES_HUMAN_REVIEW or DEFERRED status",
)
def get_conflicts_for_review() -> Dict[str, Any]:
    """
    Retrieve all conflicts that need human review.

    Returns conflicts with status REQUIRES_HUMAN_REVIEW or DEFERRED,
    including structured unresolved reasons and AutoResolver recommendations.
    """
    store = get_conflict_store()
    items = store.get_requiring_review()
    return {
        "data": [item.model_dump() for item in items],
        "count": len(items),
        "statuses_included": [
            ConflictStatus.REQUIRES_HUMAN_REVIEW.value,
            ConflictStatus.DEFERRED.value,
        ],
    }


@conflicts_router.get(
    "/review/all",
    summary="List all tracked conflicts with lifecycle state",
    response_description="All conflicts processed through the escalation-aware resolver",
)
def get_all_tracked_conflicts(
    status: Optional[str] = Query(None, description="Filter by conflict status"),
) -> Dict[str, Any]:
    """
    Retrieve all conflicts tracked by the Phase 9 lifecycle system.

    Includes AUTO_RESOLVED, REQUIRES_HUMAN_REVIEW, HUMAN_RESOLVED, REJECTED, and DEFERRED.
    """
    store = get_conflict_store()
    if status:
        try:
            status_enum = ConflictStatus(status)
            items = store.get_by_status(status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {[s.value for s in ConflictStatus]}",
            )
    else:
        items = store.get_all()

    # Compute summary counts
    status_counts = {}
    for item in store.get_all():
        status_counts[item.status.value] = status_counts.get(item.status.value, 0) + 1

    return {
        "data": [item.model_dump() for item in items],
        "count": len(items),
        "status_summary": status_counts,
        "total_unresolved": ConflictReviewService.get_unresolved_count(),
    }


@conflicts_router.post(
    "/process",
    summary="Process a conflict report through escalation-aware auto-resolver",
    response_description="Enriched conflict items with lifecycle state and resolution plan",
)
def process_conflicts(
    target_date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD). Defaults to today."),
    buffer_minutes: int = Query(15, ge=0, le=60, description="Safety buffer minutes"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Run conflict detection and process results through the escalation-aware
    AutoResolver. Each conflict is classified as either AUTO_RESOLVED or
    REQUIRES_HUMAN_REVIEW based on severity and type.

    This endpoint:
    1. Detects conflicts using the existing ConflictDetector.
    2. Runs each conflict through the EscalatingAutoResolver.
    3. Returns enriched ConflictReviewItems with lifecycle state.
    """
    from backend.app.database.repositories import (
        BlockRepository,
        MaintenanceRepository,
        MovementRepository,
        TimetableRepository,
        TrainRepository,
    )
    from backend.app.forecast.forecast import GoodsTrainForecaster
    from backend.app.scheduler.conflict_detector import ConflictDetector

    target_d = date.fromisoformat(target_date) if target_date else date.today()

    trains = [t.to_pydantic() for t in TrainRepository(db).get_all(limit=1000)]
    movements = [m.to_pydantic() for m in MovementRepository(db).get_all(limit=1000)]
    timetables = [tt.to_pydantic() for tt in TimetableRepository(db).get_all(limit=1000)]
    maintenance = [m.to_pydantic() for m in MaintenanceRepository(db).get_all(limit=1000)]
    blocks = [b.to_pydantic() for b in BlockRepository(db).get_all(limit=1000)]

    forecaster = GoodsTrainForecaster(trains=trains, movements=movements, timetables=timetables)
    fc_result = forecaster.predict(target_date=target_d)

    detector = ConflictDetector(
        trains=trains,
        timetables=timetables,
        goods_forecasts=fc_result.forecasts,
        movements=movements,
        maintenance_records=maintenance,
        block_records=blocks,
        buffer_minutes=buffer_minutes,
    )
    report = detector.detect_conflicts(target_date=target_d)

    # Process through escalation-aware resolver
    resolver = EscalatingAutoResolver()
    review_items, resolution_plan = resolver.process_conflict_report(report)

    auto_resolved = [i for i in review_items if i.status == ConflictStatus.AUTO_RESOLVED]
    needs_review = [i for i in review_items if i.status == ConflictStatus.REQUIRES_HUMAN_REVIEW]

    return {
        "target_date": target_d.isoformat(),
        "total_conflicts": len(review_items),
        "auto_resolved_count": len(auto_resolved),
        "requires_human_review_count": len(needs_review),
        "conflicts": [item.model_dump() for item in review_items],
        "resolution_plan": resolution_plan,
    }


@conflicts_router.post(
    "/{conflict_id}/resolve",
    summary="Human-resolve a conflict",
    response_description="Updated conflict with HUMAN_RESOLVED status",
)
def resolve_conflict(
    conflict_id: str,
    request: Optional[HumanReviewRequest] = None,
) -> Dict[str, Any]:
    """
    Transition a conflict from REQUIRES_HUMAN_REVIEW (or DEFERRED) to HUMAN_RESOLVED.
    """
    req = request or HumanReviewRequest(action=HumanReviewAction.RESOLVE)
    try:
        updated = ConflictReviewService.resolve_conflict(
            conflict_id=conflict_id,
            notes=req.notes,
            reviewed_by=req.reviewed_by or "operator",
        )
        return {
            "success": True,
            "conflict": updated.model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@conflicts_router.post(
    "/{conflict_id}/reject",
    summary="Reject a conflict resolution",
    response_description="Updated conflict with REJECTED status",
)
def reject_conflict(
    conflict_id: str,
    request: Optional[HumanReviewRequest] = None,
) -> Dict[str, Any]:
    """
    Transition a conflict to REJECTED. Rejected conflicts are NOT counted as resolved.
    """
    req = request or HumanReviewRequest(action=HumanReviewAction.REJECT)
    try:
        updated = ConflictReviewService.reject_conflict(
            conflict_id=conflict_id,
            notes=req.notes,
            reviewed_by=req.reviewed_by or "operator",
        )
        return {
            "success": True,
            "conflict": updated.model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@conflicts_router.post(
    "/{conflict_id}/defer",
    summary="Defer a conflict for later review",
    response_description="Updated conflict with DEFERRED status",
)
def defer_conflict(
    conflict_id: str,
    request: Optional[HumanReviewRequest] = None,
) -> Dict[str, Any]:
    """
    Transition a conflict to DEFERRED. Deferred conflicts remain unresolved
    and will continue to appear in the review queue.
    """
    req = request or HumanReviewRequest(action=HumanReviewAction.DEFER)
    try:
        updated = ConflictReviewService.defer_conflict(
            conflict_id=conflict_id,
            notes=req.notes,
            reviewed_by=req.reviewed_by or "operator",
        )
        return {
            "success": True,
            "conflict": updated.model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Plan Verification Router
# ---------------------------------------------------------------------------

plans_review_router = APIRouter(prefix="/plans", tags=["Plan Verification (Phase 9)"])


@plans_review_router.get(
    "/published",
    summary="Employee-facing: retrieve only APPROVED/PUBLISHED plans",
    response_description="Plans eligible for employee-facing display",
)
def get_published_plans(
    target_date: Optional[str] = Query(None, description="Filter by target date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Employee-facing plan retrieval endpoint.

    Only returns plans with plan_status APPROVED or PUBLISHED.
    Unapproved/draft plans are NOT returned.
    """
    repo = OptimizedPlanRepository(db)
    all_plans = repo.get_all(target_date=target_date, skip=0, limit=500)

    # Filter to only employee-visible plans
    visible = [
        p for p in all_plans
        if PlanVerificationService.is_employee_visible(p)
    ]

    # Apply pagination
    paginated = visible[skip:skip + limit]

    return {
        "data": [p.to_dict() for p in paginated],
        "count": len(paginated),
        "total": len(visible),
        "note": "Only APPROVED and PUBLISHED plans are shown in employee-facing view.",
    }


@plans_review_router.post(
    "/{plan_id}/submit-review",
    summary="Submit a plan for operator review",
    response_description="Plan transitioned to OPERATOR_REVIEW",
)
def submit_plan_for_review(
    plan_id: str,
    request: Optional[PlanApprovalRequest] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Transition plan from DRAFT to OPERATOR_REVIEW.
    """
    req = request or PlanApprovalRequest()
    repo = OptimizedPlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    try:
        result = PlanVerificationService.submit_for_review(plan=plan, notes=req.notes)
        db.commit()
        db.refresh(plan)
        return {
            "success": True,
            "transition": result,
            "plan": plan.to_dict(),
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@plans_review_router.post(
    "/{plan_id}/approve",
    summary="Approve a plan",
    response_description="Plan transitioned to APPROVED",
)
def approve_plan(
    plan_id: str,
    request: Optional[PlanApprovalRequest] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Transition plan from OPERATOR_REVIEW to APPROVED.

    The plan must have been submitted for review first.
    Existing priority-editing capabilities remain intact — the plan data
    (including any priority edits) is preserved.
    """
    req = request or PlanApprovalRequest()
    repo = OptimizedPlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    try:
        result = PlanVerificationService.approve_plan(
            plan=plan,
            approved_by=req.approved_by or "operator",
            notes=req.notes,
        )
        db.commit()
        db.refresh(plan)
        return {
            "success": True,
            "transition": result,
            "plan": plan.to_dict(),
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@plans_review_router.post(
    "/{plan_id}/publish",
    summary="Publish an approved plan",
    response_description="Plan transitioned to PUBLISHED",
)
def publish_plan(
    plan_id: str,
    request: Optional[PlanApprovalRequest] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Transition plan from APPROVED to PUBLISHED.

    Published plans are available through the employee-facing /api/plans/published endpoint.
    Only APPROVED plans can be published.
    """
    req = request or PlanApprovalRequest()
    repo = OptimizedPlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    try:
        result = PlanVerificationService.publish_plan(plan=plan, notes=req.notes)
        db.commit()
        db.refresh(plan)
        return {
            "success": True,
            "transition": result,
            "plan": plan.to_dict(),
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@plans_review_router.get(
    "/{plan_id}/status",
    summary="Get plan verification status",
    response_description="Current plan lifecycle status and metadata",
)
def get_plan_status(
    plan_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieve the current verification lifecycle status of a plan.
    """
    repo = OptimizedPlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    return {
        "plan_id": plan.plan_id,
        "plan_status": plan.plan_status,
        "solver_status": plan.solver_status,
        "num_scheduled": plan.num_scheduled,
        "num_unscheduled": plan.num_unscheduled,
        "total_requests": plan.total_requests,
        "approved_by": plan.approved_by,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "published_at": plan.published_at.isoformat() if plan.published_at else None,
        "plan_notes": plan.plan_notes,
        "is_employee_visible": PlanVerificationService.is_employee_visible(plan),
    }
