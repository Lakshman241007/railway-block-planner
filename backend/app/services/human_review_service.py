"""
Phase 9 — Human-in-the-Loop Conflict Review & Plan Verification Service.

Provides domain logic for:
  - Conflict lifecycle management (DETECTED → AUTO_RESOLVED / REQUIRES_HUMAN_REVIEW → ...)
  - AutoResolver escalation (wraps existing AutoResolver with lifecycle awareness)
  - Human conflict-review transitions (resolve, reject, defer)
  - Plan verification lifecycle (DRAFT → OPERATOR_REVIEW → APPROVED → PUBLISHED)
  - Structured unresolved-conflict reason generation

Business rules:
  - A recommendation is NOT automatically a resolution.
  - AUTO_RESOLVED means the AutoResolver determined safe automatic resolution.
  - REQUIRES_HUMAN_REVIEW means the AutoResolver could not safely resolve.
  - Unverified plans must not be treated as approved/published operational plans.
  - Only APPROVED/PUBLISHED plans are available through employee-facing retrieval.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.app.scheduler.auto_resolver import AutoResolver
from backend.app.scheduler.schemas import (
    ConflictItem,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
)
from backend.app.schemas.phase9_schemas import (
    ConflictReviewItem,
    ConflictStatus,
    HumanReviewAction,
    PlanStatus,
    UnresolvedReason,
    VALID_CONFLICT_TRANSITIONS,
    VALID_PLAN_TRANSITIONS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory conflict state store (lightweight, no extra DB table required)
# ---------------------------------------------------------------------------

class ConflictStateStore:
    """
    In-memory store for conflict lifecycle state.

    Conflicts are keyed by conflict_id. Each entry holds the enriched
    ConflictReviewItem with lifecycle state, unresolved reason, and
    review metadata.

    This avoids creating an additional database table while still providing
    structured state tracking within a running backend instance.
    """

    def __init__(self) -> None:
        self._conflicts: Dict[str, ConflictReviewItem] = {}

    def put(self, item: ConflictReviewItem) -> None:
        """Store or update a conflict review item."""
        self._conflicts[item.conflict_id] = item

    def get(self, conflict_id: str) -> Optional[ConflictReviewItem]:
        """Retrieve a conflict by ID."""
        return self._conflicts.get(conflict_id)

    def get_by_status(self, status: ConflictStatus) -> List[ConflictReviewItem]:
        """Retrieve all conflicts with the given status."""
        return [c for c in self._conflicts.values() if c.status == status]

    def get_all(self) -> List[ConflictReviewItem]:
        """Retrieve all tracked conflicts."""
        return list(self._conflicts.values())

    def get_requiring_review(self) -> List[ConflictReviewItem]:
        """Retrieve conflicts in REQUIRES_HUMAN_REVIEW or DEFERRED status."""
        return [
            c for c in self._conflicts.values()
            if c.status in (ConflictStatus.REQUIRES_HUMAN_REVIEW, ConflictStatus.DEFERRED)
        ]

    def clear(self) -> None:
        """Clear all conflict state (useful for testing)."""
        self._conflicts.clear()


# Singleton store instance
_conflict_store = ConflictStateStore()


def get_conflict_store() -> ConflictStateStore:
    """Get the singleton conflict state store."""
    return _conflict_store


# ---------------------------------------------------------------------------
# Unresolved Reason Generation
# ---------------------------------------------------------------------------

def _generate_unresolved_reason(
    conflict: ConflictItem,
    recommendation: Optional[Dict[str, str]] = None,
) -> UnresolvedReason:
    """
    Attempt to determine and structure the reason why AutoResolver cannot
    safely resolve a conflict.

    Uses actual conflict data — does NOT fabricate explanations.
    When a definitive reason cannot be determined, explicitly states so.
    """
    reason_code = "UNDETERMINED"
    reason = "Automatic resolution failed; a definitive reason could not be determined."
    constraints: List[str] = []
    is_definitive = False

    # Analyze based on conflict severity
    if conflict.severity == ConflictSeverity.CRITICAL:
        reason_code = "CRITICAL_SEVERITY"
        reason = (
            f"Conflict has Critical severity: {conflict.description}. "
            "Automatic resolution cannot safely override Critical conflicts without operator verification."
        )
        constraints.append(f"Severity: {conflict.severity.value}")
        is_definitive = True

    # Analyze based on conflict type
    elif conflict.conflict_type == ConflictType.TRAIN_BLOCK:
        if conflict.overlap_minutes > 0:
            reason_code = "TRAIN_BLOCK_OVERLAP"
            reason = (
                f"Train-Block overlap of {conflict.overlap_minutes} minutes at {conflict.location}. "
                f"Entities {conflict.entity1_id} ({conflict.entity1_type}) and "
                f"{conflict.entity2_id} ({conflict.entity2_type}) have a temporal collision "
                "that requires operator judgment."
            )
            constraints.append(f"Overlap duration: {conflict.overlap_minutes} minutes")
            constraints.append(f"Location: {conflict.location}")
            constraints.append(f"Time window: {conflict.start_time} - {conflict.end_time}")
            is_definitive = True

    elif conflict.conflict_type == ConflictType.BLOCK_BLOCK:
        reason_code = "BLOCK_BLOCK_CONTENTION"
        reason = (
            f"Block-Block contention at {conflict.location} between "
            f"{conflict.entity1_id} and {conflict.entity2_id}. "
            "Sequential staggering may not be feasible without operator assessment."
        )
        constraints.append(f"Location: {conflict.location}")
        constraints.append(f"Entity 1: {conflict.entity1_id} ({conflict.entity1_type})")
        constraints.append(f"Entity 2: {conflict.entity2_id} ({conflict.entity2_type})")
        if conflict.overlap_minutes > 0:
            constraints.append(f"Overlap: {conflict.overlap_minutes} minutes")
        is_definitive = True

    elif conflict.conflict_type == ConflictType.RESOURCE_CONTENTION:
        reason_code = "RESOURCE_CONTENTION"
        reason = (
            f"Resource contention at {conflict.location} between "
            f"{conflict.entity1_id} and {conflict.entity2_id}. "
            "Equipment sharing requires operator scheduling judgment."
        )
        constraints.append(f"Location: {conflict.location}")
        if conflict.overlap_minutes > 0:
            constraints.append(f"Contention window: {conflict.overlap_minutes} minutes")
        is_definitive = True

    elif conflict.conflict_type == ConflictType.SAFETY_BUFFER_VIOLATION:
        reason_code = "SAFETY_BUFFER_VIOLATION"
        reason = (
            f"Safety buffer violation at {conflict.location}. "
            "Automatic buffer adjustment may compromise operational safety."
        )
        constraints.append(f"Location: {conflict.location}")
        constraints.append(f"Time window: {conflict.start_time} - {conflict.end_time}")
        is_definitive = True

    # Add priority constraint info if available
    if conflict.entity1_priority:
        constraints.append(f"Entity 1 priority: {conflict.entity1_priority}")
    if conflict.entity2_priority:
        constraints.append(f"Entity 2 priority: {conflict.entity2_priority}")

    # Include the existing recommendation as context if available
    if recommendation:
        constraints.append(f"AutoResolver suggestion: {recommendation.get('strategy', 'N/A')}")

    entities = [e for e in [conflict.entity1_id, conflict.entity2_id] if e]

    return UnresolvedReason(
        reason_code=reason_code,
        reason=reason,
        explanation=reason,
        conflicting_entities=entities,
        violated_constraints=constraints,
        conflicting_constraints=constraints,
        is_reason_definitive=is_definitive,
    )


# ---------------------------------------------------------------------------
# AutoResolver Escalation
# ---------------------------------------------------------------------------

class EscalatingAutoResolver:
    """
    Wraps the existing AutoResolver with conflict lifecycle awareness.

    For each conflict:
      - Attempts automatic resolution using existing strategies.
      - If the conflict has CRITICAL severity, escalates to REQUIRES_HUMAN_REVIEW
        (critical conflicts should never be silently auto-resolved).
      - Otherwise, marks as AUTO_RESOLVED with the resolution recommendation.

    Preserves ALL existing AutoResolver strategies — does not replace them.
    """

    def __init__(self) -> None:
        self._resolver = AutoResolver()

    def process_conflict_report(
        self,
        report: ConflictReport,
    ) -> Tuple[List[ConflictReviewItem], List[Dict[str, Any]]]:
        """
        Process a full conflict report through the escalation-aware resolver.

        Returns:
            Tuple of (enriched ConflictReviewItems, resolution plan dicts)
        """
        review_items: List[ConflictReviewItem] = []
        resolution_plan: List[Dict[str, Any]] = []

        for conflict in report.conflicts:
            item, resolution = self._process_single_conflict(conflict)
            review_items.append(item)
            if resolution:
                resolution_plan.append(resolution)
            # Store in the conflict state store
            _conflict_store.put(item)

        return review_items, resolution_plan

    def _process_single_conflict(
        self,
        conflict: ConflictItem,
    ) -> Tuple[ConflictReviewItem, Optional[Dict[str, Any]]]:
        """
        Process a single conflict through escalation logic.

        Critical-severity conflicts are ALWAYS escalated to human review.
        All other conflicts use existing AutoResolver strategies.
        """
        # Generate recommendation using existing AutoResolver
        recommendation = self._get_recommendation(conflict)

        # Determine if this conflict can be safely auto-resolved
        can_auto_resolve = self._can_safely_auto_resolve(conflict)

        if can_auto_resolve:
            status = ConflictStatus.AUTO_RESOLVED
            unresolved_reason = None
        else:
            status = ConflictStatus.REQUIRES_HUMAN_REVIEW
            unresolved_reason = _generate_unresolved_reason(conflict, recommendation)

        review_item = ConflictReviewItem(
            conflict_id=conflict.conflict_id,
            status=status,
            conflict_type=conflict.conflict_type.value,
            severity=conflict.severity.value,
            location=conflict.location,
            service_date=conflict.service_date.isoformat(),
            start_time=conflict.start_time,
            end_time=conflict.end_time,
            overlap_minutes=conflict.overlap_minutes,
            entity1_type=conflict.entity1_type,
            entity1_id=conflict.entity1_id,
            entity2_type=conflict.entity2_type,
            entity2_id=conflict.entity2_id,
            description=conflict.description,
            auto_resolver_recommendation=recommendation,
            unresolved_reason=unresolved_reason,
        )

        resolution_dict = None
        if can_auto_resolve and recommendation:
            resolution_dict = {
                "conflict_id": conflict.conflict_id,
                "status": ConflictStatus.AUTO_RESOLVED.value,
                "type": conflict.conflict_type.value,
                "severity": conflict.severity.value,
                **recommendation,
            }

        return review_item, resolution_dict

    def _can_safely_auto_resolve(self, conflict: ConflictItem) -> bool:
        """
        Determine if a conflict can be safely auto-resolved.

        Rules:
          - CRITICAL severity → never auto-resolve (requires human judgment)
          - HIGH severity → never auto-resolve (safety-sensitive)
          - MEDIUM/LOW with existing strategy → auto-resolve
        """
        if conflict.severity in (ConflictSeverity.CRITICAL, ConflictSeverity.HIGH):
            return False
        return True

    def _get_recommendation(self, conflict: ConflictItem) -> Optional[Dict[str, str]]:
        """Generate a recommendation using the existing AutoResolver."""
        try:
            if conflict.conflict_type == ConflictType.TRAIN_BLOCK:
                return self._resolver.resolve_train_block_conflict(conflict)
            elif conflict.conflict_type == ConflictType.BLOCK_BLOCK:
                return self._resolver.resolve_block_block_conflict(conflict)
            elif conflict.conflict_type == ConflictType.RESOURCE_CONTENTION:
                return self._resolver.resolve_resource_contention(conflict)
            else:
                return {
                    "strategy": "Buffer Adjustment",
                    "recommendation": f"Enforce {conflict.overlap_minutes} min additional buffer clearance.",
                }
        except Exception as exc:
            logger.warning("AutoResolver recommendation failed for %s: %s", conflict.conflict_id, exc)
            return None


# ---------------------------------------------------------------------------
# Human Conflict-Review Service
# ---------------------------------------------------------------------------

class ConflictReviewService:
    """
    Service handling human review transitions for conflicts.

    Enforces valid state transitions and records review metadata.
    """

    @staticmethod
    def resolve_conflict(
        conflict_id: str,
        notes: Optional[str] = None,
        reviewed_by: str = "operator",
    ) -> ConflictReviewItem:
        """Transition a conflict to HUMAN_RESOLVED."""
        return ConflictReviewService._transition(
            conflict_id=conflict_id,
            target_status=ConflictStatus.HUMAN_RESOLVED,
            notes=notes,
            reviewed_by=reviewed_by,
        )

    @staticmethod
    def reject_conflict(
        conflict_id: str,
        notes: Optional[str] = None,
        reviewed_by: str = "operator",
    ) -> ConflictReviewItem:
        """Transition a conflict to REJECTED."""
        return ConflictReviewService._transition(
            conflict_id=conflict_id,
            target_status=ConflictStatus.REJECTED,
            notes=notes,
            reviewed_by=reviewed_by,
        )

    @staticmethod
    def defer_conflict(
        conflict_id: str,
        notes: Optional[str] = None,
        reviewed_by: str = "operator",
    ) -> ConflictReviewItem:
        """Transition a conflict to DEFERRED (remains unresolved)."""
        return ConflictReviewService._transition(
            conflict_id=conflict_id,
            target_status=ConflictStatus.DEFERRED,
            notes=notes,
            reviewed_by=reviewed_by,
        )

    @staticmethod
    def _transition(
        conflict_id: str,
        target_status: ConflictStatus,
        notes: Optional[str] = None,
        reviewed_by: str = "operator",
    ) -> ConflictReviewItem:
        """
        Execute a conflict state transition with validation.

        Raises ValueError if:
          - conflict_id not found
          - transition is invalid from current state
        """
        store = get_conflict_store()
        item = store.get(conflict_id)

        if item is None:
            raise ValueError(f"Conflict '{conflict_id}' not found in review store.")

        current_status = item.status
        valid_targets = VALID_CONFLICT_TRANSITIONS.get(current_status, [])

        if target_status not in valid_targets:
            raise ValueError(
                f"Invalid state transition: {current_status.value} → {target_status.value}. "
                f"Valid transitions from {current_status.value}: "
                f"{[s.value for s in valid_targets] if valid_targets else 'none (terminal state)'}."
            )

        # Create updated item with new status and review metadata
        updated = item.model_copy(update={
            "status": target_status,
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now().isoformat(),
            "review_notes": notes,
        })

        store.put(updated)
        logger.info(
            "Conflict %s transitioned: %s → %s (by %s)",
            conflict_id, current_status.value, target_status.value, reviewed_by,
        )
        return updated

    @staticmethod
    def is_resolved(conflict_id: str) -> bool:
        """Check if a conflict has been successfully resolved (auto or human)."""
        store = get_conflict_store()
        item = store.get(conflict_id)
        if item is None:
            return False
        return item.status in (ConflictStatus.AUTO_RESOLVED, ConflictStatus.HUMAN_RESOLVED)

    @staticmethod
    def get_unresolved_count() -> int:
        """Count conflicts that are NOT resolved (excludes AUTO_RESOLVED and HUMAN_RESOLVED)."""
        store = get_conflict_store()
        resolved_statuses = {ConflictStatus.AUTO_RESOLVED, ConflictStatus.HUMAN_RESOLVED}
        return sum(
            1 for c in store.get_all()
            if c.status not in resolved_statuses
        )


# ---------------------------------------------------------------------------
# Plan Verification Service
# ---------------------------------------------------------------------------

class PlanVerificationService:
    """
    Service managing plan lifecycle transitions.

    Rules:
      - Generated plans start as DRAFT.
      - DRAFT → OPERATOR_REVIEW when submitted for review.
      - OPERATOR_REVIEW → APPROVED when operator approves.
      - OPERATOR_REVIEW → DRAFT if operator requests re-work.
      - APPROVED → PUBLISHED when ready for employee-facing system.
      - APPROVED → OPERATOR_REVIEW if modifications require re-review.
      - Only APPROVED/PUBLISHED plans are returned by employee-facing retrieval.
    """

    @staticmethod
    def submit_for_review(
        plan: Any,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transition plan from DRAFT to OPERATOR_REVIEW."""
        return PlanVerificationService._transition_plan(
            plan=plan,
            target_status=PlanStatus.OPERATOR_REVIEW,
            notes=notes,
        )

    @staticmethod
    def approve_plan(
        plan: Any,
        approved_by: str = "operator",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transition plan to APPROVED."""
        result = PlanVerificationService._transition_plan(
            plan=plan,
            target_status=PlanStatus.APPROVED,
            notes=notes,
        )
        plan.approved_by = approved_by
        plan.approved_at = datetime.now()
        return result

    @staticmethod
    def publish_plan(
        plan: Any,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transition plan to PUBLISHED."""
        result = PlanVerificationService._transition_plan(
            plan=plan,
            target_status=PlanStatus.PUBLISHED,
            notes=notes,
        )
        plan.published_at = datetime.now()
        return result

    @staticmethod
    def request_rework(
        plan: Any,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return plan to DRAFT for rework (from OPERATOR_REVIEW)."""
        return PlanVerificationService._transition_plan(
            plan=plan,
            target_status=PlanStatus.DRAFT,
            notes=notes,
        )

    @staticmethod
    def require_re_review(
        plan: Any,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return plan to OPERATOR_REVIEW (from APPROVED) after modifications."""
        return PlanVerificationService._transition_plan(
            plan=plan,
            target_status=PlanStatus.OPERATOR_REVIEW,
            notes=notes,
        )

    @staticmethod
    def _transition_plan(
        plan: Any,
        target_status: PlanStatus,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a plan state transition with validation.

        Raises ValueError if transition is invalid from current state.
        """
        current_status_str = getattr(plan, "plan_status", "DRAFT") or "DRAFT"
        try:
            current_status = PlanStatus(current_status_str)
        except ValueError:
            current_status = PlanStatus.DRAFT

        valid_targets = VALID_PLAN_TRANSITIONS.get(current_status, [])

        if target_status not in valid_targets:
            raise ValueError(
                f"Invalid plan state transition: {current_status.value} → {target_status.value}. "
                f"Valid transitions from {current_status.value}: "
                f"{[s.value for s in valid_targets] if valid_targets else 'none (terminal state)'}."
            )

        previous = current_status.value
        plan.plan_status = target_status.value
        if notes:
            plan.plan_notes = notes

        logger.info(
            "Plan %s transitioned: %s → %s",
            getattr(plan, "plan_id", "unknown"),
            previous,
            target_status.value,
        )

        return {
            "plan_id": getattr(plan, "plan_id", "unknown"),
            "previous_status": previous,
            "new_status": target_status.value,
            "transitioned_at": datetime.now().isoformat(),
            "notes": notes,
        }

    @staticmethod
    def is_employee_visible(plan: Any) -> bool:
        """Check if a plan is eligible for employee-facing retrieval."""
        status_str = getattr(plan, "plan_status", "DRAFT") or "DRAFT"
        return status_str in (PlanStatus.APPROVED.value, PlanStatus.PUBLISHED.value)
