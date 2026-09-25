"""
Phase 9 — Human-in-the-Loop Conflict Escalation & Plan Verification Schemas.

Defines:
  - ConflictStatus: canonical conflict lifecycle states
  - PlanStatus: plan verification lifecycle states
  - UnresolvedReason: structured explanation for why auto-resolution failed
  - ConflictReviewItem: enriched conflict view for human review
  - HumanReviewAction / HumanReviewRequest: operator action payloads
  - PlanApprovalResponse: plan lifecycle transition responses
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Conflict Lifecycle States
# ---------------------------------------------------------------------------

class ConflictStatus(str, Enum):
    """Canonical conflict lifecycle states."""
    DETECTED = "DETECTED"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    HUMAN_RESOLVED = "HUMAN_RESOLVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


# ---------------------------------------------------------------------------
# Plan Lifecycle States
# ---------------------------------------------------------------------------

class PlanStatus(str, Enum):
    """Plan verification lifecycle states."""
    DRAFT = "DRAFT"
    OPERATOR_REVIEW = "OPERATOR_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"


# ---------------------------------------------------------------------------
# Valid State Transitions
# ---------------------------------------------------------------------------

VALID_CONFLICT_TRANSITIONS: Dict[ConflictStatus, List[ConflictStatus]] = {
    ConflictStatus.DETECTED: [
        ConflictStatus.AUTO_RESOLVED,
        ConflictStatus.REQUIRES_HUMAN_REVIEW,
    ],
    ConflictStatus.REQUIRES_HUMAN_REVIEW: [
        ConflictStatus.HUMAN_RESOLVED,
        ConflictStatus.REJECTED,
        ConflictStatus.DEFERRED,
    ],
    ConflictStatus.AUTO_RESOLVED: [],
    ConflictStatus.HUMAN_RESOLVED: [],
    ConflictStatus.REJECTED: [],
    ConflictStatus.DEFERRED: [
        ConflictStatus.HUMAN_RESOLVED,
        ConflictStatus.REJECTED,
    ],
}

VALID_PLAN_TRANSITIONS: Dict[PlanStatus, List[PlanStatus]] = {
    PlanStatus.DRAFT: [PlanStatus.OPERATOR_REVIEW],
    PlanStatus.OPERATOR_REVIEW: [PlanStatus.APPROVED, PlanStatus.DRAFT],
    PlanStatus.APPROVED: [PlanStatus.PUBLISHED, PlanStatus.OPERATOR_REVIEW],
    PlanStatus.PUBLISHED: [],
}


# ---------------------------------------------------------------------------
# Unresolved Conflict Reason
# ---------------------------------------------------------------------------

class UnresolvedReason(BaseModel):
    """
    Structured explanation for why AutoResolver could not safely resolve a conflict.

    When a definitive reason can be determined from the conflict data, reason_code
    and reason will contain specific information. When the reason cannot be
    determined, reason_code is 'UNDETERMINED' and reason states this explicitly.
    """
    reason_code: str = Field(
        ...,
        description="Machine-readable reason code (e.g. NO_FEASIBLE_BLOCK, CRITICAL_SEVERITY, UNDETERMINED)",
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of why auto-resolution failed",
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of why auto-resolution failed (alias of reason)",
    )
    conflicting_entities: List[str] = Field(
        default_factory=list,
        description="List of entity identifiers involved in the unresolved conflict",
    )
    violated_constraints: List[str] = Field(
        default_factory=list,
        description="List of specific violated constraints that prevented auto-resolution",
    )
    conflicting_constraints: List[str] = Field(
        default_factory=list,
        description="List of specific constraints that prevented resolution",
    )
    is_reason_definitive: bool = Field(
        default=True,
        description="False if the reason could not be definitively determined",
    )

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Conflict Review Item (enriched for human review)
# ---------------------------------------------------------------------------

class ConflictReviewItem(BaseModel):
    """
    Enriched conflict representation for human review, combining the original
    ConflictItem data with lifecycle state and unresolved reason information.
    """
    conflict_id: str = Field(..., description="Unique conflict identifier")
    status: ConflictStatus = Field(..., description="Current lifecycle status")
    conflict_type: str = Field(..., description="Category of conflict")
    severity: str = Field(..., description="Severity grading")
    location: str = Field(..., description="Corridor / section where conflict occurs")
    service_date: str = Field(..., description="Date of occurrence (ISO format)")
    start_time: str = Field(..., description="Conflict start time (HH:MM)")
    end_time: str = Field(..., description="Conflict end time (HH:MM)")
    overlap_minutes: int = Field(default=0, description="Duration of physical overlap in minutes")
    entity1_type: str = Field(..., description="Type of first entity")
    entity1_id: str = Field(..., description="Identifier of first entity")
    entity2_type: str = Field(..., description="Type of second entity")
    entity2_id: str = Field(..., description="Identifier of second entity")
    description: str = Field(..., description="Human-readable description of conflict")

    # AutoResolver recommendation (preserved from original)
    auto_resolver_recommendation: Optional[Dict[str, str]] = Field(
        default=None,
        description="AutoResolver recommendation if available (strategy + recommendation text)",
    )

    # Unresolved reason (populated when status is REQUIRES_HUMAN_REVIEW or DEFERRED)
    unresolved_reason: Optional[UnresolvedReason] = Field(
        default=None,
        description="Structured reason why auto-resolution failed",
    )

    # Human review metadata
    reviewed_by: Optional[str] = Field(default=None, description="Operator who reviewed")
    reviewed_at: Optional[str] = Field(default=None, description="ISO timestamp of review")
    review_notes: Optional[str] = Field(default=None, description="Operator notes")

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Human Review Action Payloads
# ---------------------------------------------------------------------------

class HumanReviewAction(str, Enum):
    """Actions an operator can take on a conflict requiring human review."""
    RESOLVE = "resolve"
    REJECT = "reject"
    DEFER = "defer"


class HumanReviewRequest(BaseModel):
    """Request payload for a human review action on a conflict."""
    action: HumanReviewAction = Field(..., description="Action to take: resolve, reject, or defer")
    notes: Optional[str] = Field(default=None, description="Operator notes explaining the decision")
    reviewed_by: Optional[str] = Field(default="operator", description="Identifier of the reviewing operator")

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Plan Approval / Publication Responses
# ---------------------------------------------------------------------------

class PlanApprovalRequest(BaseModel):
    """Request payload for plan approval or publication."""
    notes: Optional[str] = Field(default=None, description="Operator notes")
    approved_by: Optional[str] = Field(default="operator", description="Identifier of approving operator")

    model_config = {"str_strip_whitespace": True}


class PlanStatusResponse(BaseModel):
    """Response after a plan lifecycle transition."""
    plan_id: str
    previous_status: str
    new_status: str
    transitioned_at: str
    notes: Optional[str] = None

    model_config = {"str_strip_whitespace": True}
