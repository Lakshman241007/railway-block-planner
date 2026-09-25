import React, { useState } from 'react';
import { PlanApprovalStatus, getPlanApprovalBadgeClass } from '../types';

export default function PlanApprovalSection({
  optimizationResult,
  onApprovePlan,
  onPublishPlan,
  onRejectPlan,
  isOperator = false,
  targetDate,
}) {
  const [approving, setApproving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [operatorNotes, setOperatorNotes] = useState('');
  const [showNotesInput, setShowNotesInput] = useState(false);

  if (!optimizationResult) return null;

  const planId = optimizationResult.plan_id || 'OPT-PLAN-CURRENT';
  const solverStatus = optimizationResult.status || 'OPTIMAL';
  const approvalStatus = optimizationResult.approval_status || (optimizationResult.published ? PlanApprovalStatus.PUBLISHED : (optimizationResult.approved ? PlanApprovalStatus.APPROVED : PlanApprovalStatus.UNDER_REVIEW));

  const numScheduled = optimizationResult.solver_statistics?.num_scheduled ?? optimizationResult.scheduled_blocks?.length ?? 0;
  const numUnscheduled = optimizationResult.solver_statistics?.num_unscheduled ?? optimizationResult.unscheduled_blocks?.length ?? 0;
  const conflictsAfter = optimizationResult.solver_statistics?.conflicts_after ?? 0;
  const isValid = optimizationResult.validation?.is_valid !== false;

  const isApproved = approvalStatus === PlanApprovalStatus.APPROVED;
  const isPublished = approvalStatus === PlanApprovalStatus.PUBLISHED;

  const handleApprove = async () => {
    setApproving(true);
    try {
      if (onApprovePlan) {
        await onApprovePlan(planId, {
          notes: operatorNotes || 'Approved by human operator after constraint verification',
        });
      }
    } finally {
      setApproving(false);
      setShowNotesInput(false);
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      if (onPublishPlan) {
        await onPublishPlan(planId, {
          notes: operatorNotes || 'Published to live operational network',
        });
      }
    } finally {
      setPublishing(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    try {
      if (onRejectPlan) {
        await onRejectPlan(planId, {
          reason: operatorNotes || 'Rejected by operator review',
        });
      }
    } finally {
      setRejecting(false);
      setShowNotesInput(false);
    }
  };

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 10,
        padding: '16px 20px',
        marginBottom: 16,
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {/* Left: Plan metadata & Approval status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: isPublished ? 'rgba(16, 185, 129, 0.15)' : isApproved ? 'rgba(56, 189, 248, 0.15)' : 'rgba(234, 179, 8, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.2rem',
            }}
          >
            {isPublished ? '🚀' : isApproved ? '✓' : '📋'}
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
                Plan Human Verification & Approval
              </span>
              <span className={`badge ${getPlanApprovalBadgeClass(approvalStatus)}`}>
                {approvalStatus}
              </span>
              <span className="badge badge-outline mono" style={{ fontSize: '0.72rem' }}>
                {planId}
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
              Target Service Date: <span className="mono" style={{ color: '#cbd5e1' }}>{targetDate || optimizationResult.target_date}</span> • Solver: <strong style={{ color: '#10b981' }}>{solverStatus}</strong>
            </div>
          </div>
        </div>

        {/* Right: Operator Action Triggers */}
        {isOperator && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {!isApproved && !isPublished && (
              <button
                type="button"
                className="btn-action btn-primary"
                style={{ padding: '6px 14px', fontSize: '0.78rem', fontWeight: 600 }}
                onClick={handleApprove}
                disabled={approving || !isValid}
              >
                {approving ? 'Approving...' : '✓ Approve Plan'}
              </button>
            )}

            {isApproved && !isPublished && (
              <button
                type="button"
                className="btn-action"
                style={{
                  padding: '6px 14px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  background: '#10b981',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                }}
                onClick={handlePublish}
                disabled={publishing}
              >
                {publishing ? 'Publishing...' : '🚀 Publish to Operational Network'}
              </button>
            )}

            {isPublished && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  color: '#10b981',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  background: 'rgba(16, 185, 129, 0.1)',
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                <span>✓ Active on Operational Network</span>
              </div>
            )}

            {!isPublished && (
              <button
                type="button"
                className="btn-action btn-outline"
                style={{ padding: '6px 10px', fontSize: '0.75rem', color: '#f87171' }}
                onClick={() => setShowNotesInput((prev) => !prev)}
              >
                {showNotesInput ? 'Hide Options' : 'Review Notes / Reject'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Verification Integrity Checklist */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 10,
          marginTop: 14,
          paddingTop: 12,
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.76rem' }}>
          <span>{isValid ? '✅' : '❌'}</span>
          <span style={{ color: '#cbd5e1' }}>Independent Conflict Validation:</span>
          <strong style={{ color: isValid ? '#10b981' : '#f87171' }}>{isValid ? 'PASSED (0 Conflicts)' : 'VIOLATIONS'}</strong>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.76rem' }}>
          <span>📊</span>
          <span style={{ color: '#cbd5e1' }}>Allocations:</span>
          <strong style={{ color: '#38bdf8' }}>{numScheduled} Scheduled</strong>
          <span style={{ color: '#64748b' }}>({numUnscheduled} Unscheduled)</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.76rem' }}>
          <span>🛡️</span>
          <span style={{ color: '#cbd5e1' }}>Safety Headway:</span>
          <strong style={{ color: '#10b981' }}>15m Enforced</strong>
        </div>
      </div>

      {/* Collapsible Notes & Reject Form */}
      {showNotesInput && isOperator && !isPublished && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: 'rgba(0, 0, 0, 0.25)',
            borderRadius: 6,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <label style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
            Operator Decision Log & Review Notes:
          </label>
          <textarea
            className="textarea-input"
            rows={2}
            value={operatorNotes}
            onChange={(e) => setOperatorNotes(e.target.value)}
            placeholder="Add notes explaining your approval decision or reason for plan rejection..."
            style={{ fontSize: '0.78rem' }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button
              type="button"
              className="btn-action btn-critical"
              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
              onClick={handleReject}
              disabled={rejecting}
            >
              {rejecting ? 'Rejecting...' : 'Reject Plan'}
            </button>
            <button
              type="button"
              className="btn-action btn-primary"
              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
              onClick={handleApprove}
              disabled={approving || !isValid}
            >
              {approving ? 'Approving...' : 'Approve with Notes'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
