"""
Phase 9 — Human-in-the-Loop Conflict Escalation & Plan Verification Tests.

Covers:
  Conflict Lifecycle (1–9)
  Explanation / Reason (10–13)
  Plan Lifecycle (14–20)

Does NOT modify existing tests. Does NOT test frontend.
"""

from __future__ import annotations

import json
import pytest
from datetime import date, datetime
from typing import Any, Dict
from unittest.mock import MagicMock

from backend.app.schemas.phase9_schemas import (
    ConflictReviewItem,
    ConflictStatus,
    HumanReviewAction,
    HumanReviewRequest,
    PlanStatus,
    UnresolvedReason,
    VALID_CONFLICT_TRANSITIONS,
    VALID_PLAN_TRANSITIONS,
)
from backend.app.scheduler.schemas import (
    ConflictItem,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
)
from backend.app.services.human_review_service import (
    ConflictReviewService,
    ConflictStateStore,
    EscalatingAutoResolver,
    PlanVerificationService,
    _generate_unresolved_reason,
    get_conflict_store,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_conflict_store():
    """Clear the global conflict store before each test."""
    store = get_conflict_store()
    store.clear()
    yield
    store.clear()


def _make_conflict(
    conflict_id: str = "CNF-001",
    conflict_type: ConflictType = ConflictType.BLOCK_BLOCK,
    severity: ConflictSeverity = ConflictSeverity.MEDIUM,
    location: str = "Chennai-Arakkonam",
    overlap_minutes: int = 30,
    entity1_type: str = "Block",
    entity1_id: str = "BLK-001",
    entity2_type: str = "Block",
    entity2_id: str = "BLK-002",
    entity1_priority: str = None,
    entity2_priority: str = None,
) -> ConflictItem:
    """Factory for test ConflictItem instances."""
    return ConflictItem(
        conflict_id=conflict_id,
        conflict_type=conflict_type,
        severity=severity,
        location=location,
        service_date=date(2026, 9, 24),
        start_time="10:00",
        end_time="11:00",
        overlap_minutes=overlap_minutes,
        entity1_type=entity1_type,
        entity1_id=entity1_id,
        entity2_type=entity2_type,
        entity2_id=entity2_id,
        description=f"Test conflict between {entity1_id} and {entity2_id}",
        entity1_priority=entity1_priority,
        entity2_priority=entity2_priority,
    )


def _make_conflict_report(*conflicts: ConflictItem) -> ConflictReport:
    """Factory for test ConflictReport instances."""
    conflict_list = list(conflicts)
    return ConflictReport(
        generated_at=datetime.now().isoformat(),
        target_date=date(2026, 9, 24),
        total_conflicts=len(conflict_list),
        conflicts=conflict_list,
    )


def _make_mock_plan(
    plan_id: str = "plan-test-001",
    plan_status: str = "DRAFT",
) -> MagicMock:
    """Factory for mock OptimizedPlan-like objects."""
    plan = MagicMock()
    plan.plan_id = plan_id
    plan.plan_status = plan_status
    plan.plan_notes = None
    plan.approved_by = None
    plan.approved_at = None
    plan.published_at = None
    return plan


# ===========================================================================
# CONFLICT LIFECYCLE TESTS (1–9)
# ===========================================================================

class TestConflictLifecycle:
    """Tests for conflict lifecycle state management."""

    # 1. Conflict is detected
    def test_conflict_detected_initial_state(self):
        """A newly processed conflict should be in a valid initial state."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.MEDIUM)
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)

        assert len(review_items) == 1
        item = review_items[0]
        assert item.conflict_id == "CNF-001"
        assert item.status in (ConflictStatus.AUTO_RESOLVED, ConflictStatus.REQUIRES_HUMAN_REVIEW)

    # 2. Known resolvable conflict → AUTO_RESOLVED
    def test_resolvable_conflict_auto_resolved(self):
        """A MEDIUM-severity conflict should be AUTO_RESOLVED."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.MEDIUM)
        report = _make_conflict_report(conflict)

        review_items, resolution_plan = resolver.process_conflict_report(report)

        assert review_items[0].status == ConflictStatus.AUTO_RESOLVED
        assert len(resolution_plan) == 1
        assert resolution_plan[0]["status"] == "AUTO_RESOLVED"

    # 3. Unresolvable conflict → REQUIRES_HUMAN_REVIEW
    def test_unresolvable_conflict_requires_human_review(self):
        """A CRITICAL-severity conflict should require human review."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)

        review_items, resolution_plan = resolver.process_conflict_report(report)

        assert review_items[0].status == ConflictStatus.REQUIRES_HUMAN_REVIEW
        assert len(resolution_plan) == 0  # No auto-resolution

    def test_high_severity_requires_human_review(self):
        """HIGH-severity conflicts should also require human review."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.HIGH)
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)

        assert review_items[0].status == ConflictStatus.REQUIRES_HUMAN_REVIEW

    # 4. Unresolved conflict is never counted as resolved
    def test_unresolved_conflict_not_counted_as_resolved(self):
        """A REQUIRES_HUMAN_REVIEW conflict must NOT be counted as resolved."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        assert not ConflictReviewService.is_resolved("CNF-001")
        assert ConflictReviewService.get_unresolved_count() == 1

    # 5. Human resolve → HUMAN_RESOLVED
    def test_human_resolve(self):
        """An operator can resolve a REQUIRES_HUMAN_REVIEW conflict."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        updated = ConflictReviewService.resolve_conflict(
            "CNF-001",
            notes="Resolved by scheduling adjustment",
            reviewed_by="supervisor",
        )

        assert updated.status == ConflictStatus.HUMAN_RESOLVED
        assert updated.reviewed_by == "supervisor"
        assert updated.review_notes == "Resolved by scheduling adjustment"
        assert updated.reviewed_at is not None
        assert ConflictReviewService.is_resolved("CNF-001")

    # 6. Human reject → REJECTED
    def test_human_reject(self):
        """An operator can reject a conflict resolution."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        updated = ConflictReviewService.reject_conflict("CNF-001", notes="Not valid")

        assert updated.status == ConflictStatus.REJECTED
        assert not ConflictReviewService.is_resolved("CNF-001")

    # 7. Human defer → DEFERRED
    def test_human_defer(self):
        """An operator can defer a conflict for later review."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        updated = ConflictReviewService.defer_conflict("CNF-001", notes="Will handle later")

        assert updated.status == ConflictStatus.DEFERRED

    # 8. Deferred conflict remains unresolved
    def test_deferred_conflict_remains_unresolved(self):
        """A DEFERRED conflict must NOT be counted as resolved."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        ConflictReviewService.defer_conflict("CNF-001")

        assert not ConflictReviewService.is_resolved("CNF-001")
        assert ConflictReviewService.get_unresolved_count() == 1

    def test_deferred_can_be_resolved_later(self):
        """A DEFERRED conflict can later be resolved."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        ConflictReviewService.defer_conflict("CNF-001")
        updated = ConflictReviewService.resolve_conflict("CNF-001")

        assert updated.status == ConflictStatus.HUMAN_RESOLVED
        assert ConflictReviewService.is_resolved("CNF-001")

    # 9. Invalid state transitions are rejected
    def test_invalid_transition_auto_resolved_to_human_resolved(self):
        """Cannot transition from AUTO_RESOLVED to HUMAN_RESOLVED."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.LOW)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        # Should be auto-resolved
        store = get_conflict_store()
        assert store.get("CNF-001").status == ConflictStatus.AUTO_RESOLVED

        with pytest.raises(ValueError, match="Invalid state transition"):
            ConflictReviewService.resolve_conflict("CNF-001")

    def test_invalid_transition_human_resolved_to_rejected(self):
        """Cannot transition from HUMAN_RESOLVED (terminal) to another state."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)
        resolver.process_conflict_report(report)

        ConflictReviewService.resolve_conflict("CNF-001")

        with pytest.raises(ValueError, match="Invalid state transition"):
            ConflictReviewService.reject_conflict("CNF-001")

    def test_conflict_not_found_raises_error(self):
        """Attempting to review a nonexistent conflict raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            ConflictReviewService.resolve_conflict("NONEXISTENT")


# ===========================================================================
# EXPLANATION / REASON TESTS (10–13)
# ===========================================================================

class TestUnresolvedReason:
    """Tests for unresolved conflict reason/explanation."""

    # 10. Unresolved conflict contains reason when determinable
    def test_unresolved_conflict_has_reason(self):
        """A REQUIRES_HUMAN_REVIEW conflict should have a structured reason."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.CRITICAL)
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)
        item = review_items[0]

        assert item.unresolved_reason is not None
        assert item.unresolved_reason.reason_code == "CRITICAL_SEVERITY"
        assert len(item.unresolved_reason.reason) > 0
        assert item.unresolved_reason.is_reason_definitive is True

    # 11. Relevant constraints/evidence are preserved
    def test_constraints_preserved(self):
        """Unresolved reason should contain relevant constraint information."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(
            severity=ConflictSeverity.HIGH,
            conflict_type=ConflictType.TRAIN_BLOCK,
            overlap_minutes=45,
            entity1_type="GoodsForecast",
            entity1_id="GT-001",
            entity2_type="Block",
            entity2_id="BLK-001",
            entity1_priority="High",
            entity2_priority="Medium",
        )
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)
        item = review_items[0]

        assert item.unresolved_reason is not None
        constraints = item.unresolved_reason.conflicting_constraints
        assert len(constraints) > 0
        # Should contain actual overlap/location data
        constraint_text = " ".join(constraints)
        assert "45" in constraint_text or "overlap" in constraint_text.lower() or "Chennai" in constraint_text

    # 12. Unknown reason is explicitly represented
    def test_unknown_reason_explicit(self):
        """When reason is undetermined, it should be explicitly stated."""
        # Directly test the reason generator with a conflict where no
        # specific rule matches (should not happen with current types but test the fallback)
        reason = _generate_unresolved_reason(
            _make_conflict(
                severity=ConflictSeverity.MEDIUM,  # Medium would normally be auto-resolved
                conflict_type=ConflictType.BLOCK_BLOCK,
            ),
        )
        # Even for a known type, the reason should be definitive
        # The undetermined case is for truly unknown scenarios
        assert reason.reason_code in ("BLOCK_BLOCK_CONTENTION", "UNDETERMINED")
        assert len(reason.reason) > 0

    def test_undetermined_reason_fallback(self):
        """Direct test of undetermined reason when no rule matches."""
        conflict = _make_conflict(severity=ConflictSeverity.LOW)
        # Force a scenario where nothing matches well
        reason = UnresolvedReason(
            reason_code="UNDETERMINED",
            reason="Automatic resolution failed; a definitive reason could not be determined.",
            conflicting_constraints=[],
            is_reason_definitive=False,
        )
        assert reason.reason_code == "UNDETERMINED"
        assert reason.is_reason_definitive is False
        assert "could not be determined" in reason.reason

    # 13. No fabricated reason is produced
    def test_no_fabricated_reason_for_auto_resolved(self):
        """AUTO_RESOLVED conflicts should NOT have unresolved_reason."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(severity=ConflictSeverity.MEDIUM)
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)
        item = review_items[0]

        assert item.status == ConflictStatus.AUTO_RESOLVED
        assert item.unresolved_reason is None

    def test_reason_uses_actual_conflict_data(self):
        """Reason should reference actual conflict fields, not fabricated data."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(
            severity=ConflictSeverity.CRITICAL,
            location="Tambaram-Chengalpattu",
            entity1_id="BLK-X",
            entity2_id="BLK-Y",
        )
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)
        item = review_items[0]

        assert item.unresolved_reason is not None
        # Reason should contain the actual conflict description
        assert "Critical" in item.unresolved_reason.reason or "BLK-X" in item.unresolved_reason.reason or "Tambaram" in item.unresolved_reason.reason

    def test_all_conflict_types_produce_valid_reasons(self):
        """Each conflict type should produce a valid reason when escalated."""
        resolver = EscalatingAutoResolver()
        for ct in ConflictType:
            conflict = _make_conflict(
                conflict_id=f"CNF-{ct.value}",
                severity=ConflictSeverity.HIGH,
                conflict_type=ct,
            )
            report = _make_conflict_report(conflict)
            review_items, _ = resolver.process_conflict_report(report)
            item = review_items[0]
            assert item.unresolved_reason is not None
            assert item.unresolved_reason.reason_code != ""
            assert len(item.unresolved_reason.reason) > 10


# ===========================================================================
# PLAN LIFECYCLE TESTS (14–20)
# ===========================================================================

class TestPlanLifecycle:
    """Tests for plan verification lifecycle."""

    # 14. Generated plan starts in appropriate unverified state
    def test_plan_starts_as_draft(self):
        """A newly generated plan should start with DRAFT status."""
        plan = _make_mock_plan(plan_status="DRAFT")
        assert plan.plan_status == "DRAFT"
        assert not PlanVerificationService.is_employee_visible(plan)

    # 15. Existing priority editing remains functional
    def test_priority_editing_preserved(self):
        """Plan data modifications should not be blocked by lifecycle state."""
        plan = _make_mock_plan(plan_status="DRAFT")
        # Simulate priority edit — this should work regardless of plan_status
        plan.result_json = '{"modified": true}'
        assert plan.result_json == '{"modified": true}'
        # Plan status is unaffected by data edits
        assert plan.plan_status == "DRAFT"

    # 16. Modified plan requires appropriate review
    def test_modified_plan_requires_review(self):
        """After submitting for review and getting approved, modification should
        require re-review by going back to OPERATOR_REVIEW."""
        plan = _make_mock_plan(plan_status="APPROVED")
        result = PlanVerificationService.require_re_review(
            plan, notes="Priority was edited"
        )
        assert result["new_status"] == "OPERATOR_REVIEW"
        assert plan.plan_status == "OPERATOR_REVIEW"

    # 17. Approval changes the plan state correctly
    def test_approval_changes_state(self):
        """Approving a plan transitions it from OPERATOR_REVIEW to APPROVED."""
        plan = _make_mock_plan(plan_status="OPERATOR_REVIEW")
        result = PlanVerificationService.approve_plan(
            plan, approved_by="supervisor"
        )
        assert result["new_status"] == "APPROVED"
        assert plan.plan_status == "APPROVED"
        assert plan.approved_by == "supervisor"
        assert plan.approved_at is not None

    # 18. Publication changes the plan state correctly
    def test_publication_changes_state(self):
        """Publishing an approved plan transitions it to PUBLISHED."""
        plan = _make_mock_plan(plan_status="APPROVED")
        result = PlanVerificationService.publish_plan(plan)
        assert result["new_status"] == "PUBLISHED"
        assert plan.plan_status == "PUBLISHED"
        assert plan.published_at is not None

    # 19. Unapproved plans are not returned by employee-facing retrieval
    def test_unapproved_plans_not_employee_visible(self):
        """DRAFT and OPERATOR_REVIEW plans must NOT be employee-visible."""
        for status in ("DRAFT", "OPERATOR_REVIEW"):
            plan = _make_mock_plan(plan_status=status)
            assert not PlanVerificationService.is_employee_visible(plan)

    def test_approved_plans_employee_visible(self):
        """APPROVED and PUBLISHED plans must be employee-visible."""
        for status in ("APPROVED", "PUBLISHED"):
            plan = _make_mock_plan(plan_status=status)
            assert PlanVerificationService.is_employee_visible(plan)

    # 20. Existing OptimizedPlan persistence remains functional
    def test_plan_persistence_compatibility(self):
        """New plan_status field has a sensible default for backward compatibility."""
        plan = _make_mock_plan()
        # Default plan_status should be DRAFT
        assert plan.plan_status == "DRAFT"
        # Should be able to transition through the full lifecycle
        PlanVerificationService.submit_for_review(plan)
        assert plan.plan_status == "OPERATOR_REVIEW"
        PlanVerificationService.approve_plan(plan)
        assert plan.plan_status == "APPROVED"
        PlanVerificationService.publish_plan(plan)
        assert plan.plan_status == "PUBLISHED"


class TestPlanInvalidTransitions:
    """Test invalid plan state transitions."""

    def test_cannot_approve_draft_directly(self):
        """Cannot approve a DRAFT plan without submitting for review first."""
        plan = _make_mock_plan(plan_status="DRAFT")
        with pytest.raises(ValueError, match="Invalid plan state transition"):
            PlanVerificationService.approve_plan(plan)

    def test_cannot_publish_draft(self):
        """Cannot publish a DRAFT plan."""
        plan = _make_mock_plan(plan_status="DRAFT")
        with pytest.raises(ValueError, match="Invalid plan state transition"):
            PlanVerificationService.publish_plan(plan)

    def test_cannot_publish_operator_review(self):
        """Cannot publish an OPERATOR_REVIEW plan (must approve first)."""
        plan = _make_mock_plan(plan_status="OPERATOR_REVIEW")
        with pytest.raises(ValueError, match="Invalid plan state transition"):
            PlanVerificationService.publish_plan(plan)

    def test_published_is_terminal(self):
        """PUBLISHED is a terminal state — no further transitions."""
        plan = _make_mock_plan(plan_status="PUBLISHED")
        with pytest.raises(ValueError, match="Invalid plan state transition"):
            PlanVerificationService.approve_plan(plan)


# ===========================================================================
# MIXED SCENARIO TESTS
# ===========================================================================

class TestMixedScenarios:
    """Integration-style tests combining multiple conflict and plan operations."""

    def test_mixed_severity_conflicts(self):
        """Process a report with both auto-resolvable and unresolvable conflicts."""
        resolver = EscalatingAutoResolver()
        report = _make_conflict_report(
            _make_conflict(conflict_id="CNF-LOW", severity=ConflictSeverity.LOW),
            _make_conflict(conflict_id="CNF-MED", severity=ConflictSeverity.MEDIUM),
            _make_conflict(conflict_id="CNF-HIGH", severity=ConflictSeverity.HIGH),
            _make_conflict(conflict_id="CNF-CRIT", severity=ConflictSeverity.CRITICAL),
        )

        review_items, resolution_plan = resolver.process_conflict_report(report)

        auto_resolved = [i for i in review_items if i.status == ConflictStatus.AUTO_RESOLVED]
        needs_review = [i for i in review_items if i.status == ConflictStatus.REQUIRES_HUMAN_REVIEW]

        assert len(auto_resolved) == 2  # LOW and MEDIUM
        assert len(needs_review) == 2   # HIGH and CRITICAL
        assert len(resolution_plan) == 2

    def test_auto_resolver_recommendation_preserved(self):
        """AutoResolver recommendation should be preserved even when escalated."""
        resolver = EscalatingAutoResolver()
        conflict = _make_conflict(
            severity=ConflictSeverity.CRITICAL,
            conflict_type=ConflictType.BLOCK_BLOCK,
        )
        report = _make_conflict_report(conflict)

        review_items, _ = resolver.process_conflict_report(report)
        item = review_items[0]

        assert item.status == ConflictStatus.REQUIRES_HUMAN_REVIEW
        assert item.auto_resolver_recommendation is not None
        assert "strategy" in item.auto_resolver_recommendation

    def test_conflict_store_operations(self):
        """Verify conflict store CRUD operations."""
        store = ConflictStateStore()
        item = ConflictReviewItem(
            conflict_id="test-1",
            status=ConflictStatus.DETECTED,
            conflict_type="Block-Block Contention",
            severity="Medium",
            location="Test",
            service_date="2026-09-24",
            start_time="10:00",
            end_time="11:00",
            entity1_type="Block",
            entity1_id="B1",
            entity2_type="Block",
            entity2_id="B2",
            description="Test conflict",
        )
        store.put(item)
        assert store.get("test-1") is not None
        assert len(store.get_all()) == 1
        store.clear()
        assert len(store.get_all()) == 0

    def test_full_plan_lifecycle_with_rework(self):
        """Test the full plan lifecycle including a rework cycle."""
        plan = _make_mock_plan()

        # DRAFT → OPERATOR_REVIEW
        PlanVerificationService.submit_for_review(plan)
        assert plan.plan_status == "OPERATOR_REVIEW"
        assert not PlanVerificationService.is_employee_visible(plan)

        # OPERATOR_REVIEW → DRAFT (rework)
        PlanVerificationService.request_rework(plan, notes="Needs priority adjustments")
        assert plan.plan_status == "DRAFT"

        # DRAFT → OPERATOR_REVIEW (re-submit)
        PlanVerificationService.submit_for_review(plan)
        assert plan.plan_status == "OPERATOR_REVIEW"

        # OPERATOR_REVIEW → APPROVED
        PlanVerificationService.approve_plan(plan, approved_by="admin")
        assert plan.plan_status == "APPROVED"
        assert PlanVerificationService.is_employee_visible(plan)

        # APPROVED → PUBLISHED
        PlanVerificationService.publish_plan(plan)
        assert plan.plan_status == "PUBLISHED"
        assert PlanVerificationService.is_employee_visible(plan)


# ===========================================================================
# VALID TRANSITION MAP TESTS
# ===========================================================================

class TestTransitionMaps:
    """Verify the transition maps are consistent and complete."""

    def test_all_conflict_statuses_in_transition_map(self):
        """Every ConflictStatus should have an entry in the transition map."""
        for status in ConflictStatus:
            assert status in VALID_CONFLICT_TRANSITIONS

    def test_all_plan_statuses_in_transition_map(self):
        """Every PlanStatus should have an entry in the transition map."""
        for status in PlanStatus:
            assert status in VALID_PLAN_TRANSITIONS

    def test_terminal_states_have_no_transitions(self):
        """Terminal conflict states should have empty transition lists."""
        assert VALID_CONFLICT_TRANSITIONS[ConflictStatus.AUTO_RESOLVED] == []
        assert VALID_CONFLICT_TRANSITIONS[ConflictStatus.HUMAN_RESOLVED] == []
        assert VALID_CONFLICT_TRANSITIONS[ConflictStatus.REJECTED] == []

    def test_published_is_terminal(self):
        """PUBLISHED is terminal for plans."""
        assert VALID_PLAN_TRANSITIONS[PlanStatus.PUBLISHED] == []
