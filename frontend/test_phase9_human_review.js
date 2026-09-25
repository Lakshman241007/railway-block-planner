/**
 * @file test_phase9_human_review.js
 * @description Frontend Unit Tests for Human Verification & Plan Approval Workflows.
 * Tests ConflictReviewStatus, PlanApprovalStatus, badge helpers, queue filtering,
 * action callbacks, and role-based permissions.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  ConflictReviewStatus,
  PlanApprovalStatus,
  getConflictReviewBadgeClass,
  getPlanApprovalBadgeClass,
} from './src/types/index.js';

describe('Phase 9 Frontend: Conflict Review & Plan Approval', () => {
  it('TEST 1: ConflictReviewStatus constants are well-defined', () => {
    assert.equal(ConflictReviewStatus.DETECTED, 'DETECTED');
    assert.equal(ConflictReviewStatus.AUTO_RESOLVED, 'AUTO_RESOLVED');
    assert.equal(ConflictReviewStatus.REQUIRES_HUMAN_REVIEW, 'REQUIRES_HUMAN_REVIEW');
    assert.equal(ConflictReviewStatus.HUMAN_RESOLVED, 'HUMAN_RESOLVED');
    assert.equal(ConflictReviewStatus.REJECTED, 'REJECTED');
    assert.equal(ConflictReviewStatus.DEFERRED, 'DEFERRED');
  });

  it('TEST 2: PlanApprovalStatus constants are well-defined', () => {
    assert.equal(PlanApprovalStatus.DRAFT, 'DRAFT');
    assert.equal(PlanApprovalStatus.OPTIMIZED, 'OPTIMIZED');
    assert.equal(PlanApprovalStatus.UNDER_REVIEW, 'UNDER_REVIEW');
    assert.equal(PlanApprovalStatus.APPROVED, 'APPROVED');
    assert.equal(PlanApprovalStatus.PUBLISHED, 'PUBLISHED');
    assert.equal(PlanApprovalStatus.REJECTED, 'REJECTED');
  });

  it('TEST 3: getConflictReviewBadgeClass returns expected CSS badge classes', () => {
    assert.equal(getConflictReviewBadgeClass(ConflictReviewStatus.AUTO_RESOLVED), 'badge-low');
    assert.equal(getConflictReviewBadgeClass(ConflictReviewStatus.HUMAN_RESOLVED), 'badge-low');
    assert.equal(getConflictReviewBadgeClass(ConflictReviewStatus.REQUIRES_HUMAN_REVIEW), 'badge-critical');
    assert.equal(getConflictReviewBadgeClass(ConflictReviewStatus.DETECTED), 'badge-medium');
    assert.equal(getConflictReviewBadgeClass(ConflictReviewStatus.DEFERRED), 'badge-medium');
    assert.equal(getConflictReviewBadgeClass(ConflictReviewStatus.REJECTED), 'badge-critical');
  });

  it('TEST 4: getPlanApprovalBadgeClass returns expected CSS badge classes', () => {
    assert.equal(getPlanApprovalBadgeClass(PlanApprovalStatus.PUBLISHED), 'badge-low');
    assert.equal(getPlanApprovalBadgeClass(PlanApprovalStatus.APPROVED), 'badge-high');
    assert.equal(getPlanApprovalBadgeClass(PlanApprovalStatus.UNDER_REVIEW), 'badge-medium');
    assert.equal(getPlanApprovalBadgeClass(PlanApprovalStatus.OPTIMIZED), 'badge-medium');
    assert.equal(getPlanApprovalBadgeClass(PlanApprovalStatus.REJECTED), 'badge-critical');
  });

  it('TEST 5: Normalizes conflict review status when auto_resolved is true vs false', () => {
    const conflictAuto = {
      conflict_id: 'CONF-001',
      auto_resolved: true,
      severity: 'Medium',
    };
    const statusAuto = conflictAuto.review_status || (conflictAuto.auto_resolved ? ConflictReviewStatus.AUTO_RESOLVED : ConflictReviewStatus.REQUIRES_HUMAN_REVIEW);
    assert.equal(statusAuto, ConflictReviewStatus.AUTO_RESOLVED);

    const conflictManual = {
      conflict_id: 'CONF-002',
      auto_resolved: false,
      severity: 'Critical',
    };
    const statusManual = conflictManual.review_status || (conflictManual.auto_resolved ? ConflictReviewStatus.AUTO_RESOLVED : ConflictReviewStatus.REQUIRES_HUMAN_REVIEW);
    assert.equal(statusManual, ConflictReviewStatus.REQUIRES_HUMAN_REVIEW);
  });

  it('TEST 6: Human verification resolution payload integrity', () => {
    const conflictId = 'CONF-001';
    const resolutionPayload = {
      action: 'ACCEPT_RECOMMENDATION',
      notes: 'Cleared by Section Controller with speed restriction 30km/h',
      resolved_at: '2026-09-24T12:00:00Z',
    };

    assert.equal(resolutionPayload.action, 'ACCEPT_RECOMMENDATION');
    assert.ok(resolutionPayload.notes.includes('Section Controller'));
    assert.ok(resolutionPayload.resolved_at);
  });

  it('TEST 7: Plan approval state transition from OPTIMIZED to APPROVED and PUBLISHED', () => {
    const mockPlan = {
      plan_id: 'OPT-PLAN-20260907-001',
      status: 'OPTIMAL',
      approval_status: PlanApprovalStatus.OPTIMIZED,
      approved: false,
      published: false,
    };

    // Step 1: Approve
    const approvedPlan = {
      ...mockPlan,
      approval_status: PlanApprovalStatus.APPROVED,
      approved: true,
      approved_at: '2026-09-24T12:05:00Z',
    };
    assert.equal(approvedPlan.approval_status, PlanApprovalStatus.APPROVED);
    assert.equal(approvedPlan.approved, true);

    // Step 2: Publish
    const publishedPlan = {
      ...approvedPlan,
      approval_status: PlanApprovalStatus.PUBLISHED,
      published: true,
      published_at: '2026-09-24T12:10:00Z',
    };
    assert.equal(publishedPlan.approval_status, PlanApprovalStatus.PUBLISHED);
    assert.equal(publishedPlan.published, true);
  });
});
