import React, { useState } from 'react';
import { ConflictReviewStatus, getConflictReviewBadgeClass, getPriorityClass } from '../types';

export default function ConflictReviewModal({
  conflict,
  onClose,
  onResolve,
  onReject,
  onDefer,
  isOperator = false,
}) {
  if (!conflict) return null;

  const [activeAction, setActiveAction] = useState('resolve'); // 'resolve' | 'reject' | 'defer'
  const [resolutionAction, setResolutionAction] = useState(
    conflict.suggested_action || 'ACCEPT_RECOMMENDATION'
  );
  const [operatorNotes, setOperatorNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('SCHEDULE_UNVIABLE');
  const [deferReason, setDeferReason] = useState('AWAITING_TRAFFIC_UPDATE');
  const [deferUntil, setDeferUntil] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const reviewStatus = conflict.review_status || conflict.status || ConflictReviewStatus.REQUIRES_HUMAN_REVIEW;
  const severity = String(conflict.severity || 'Medium').toLowerCase();
  const isCritical = severity === 'critical';

  const handleExecute = async () => {
    setSubmitting(true);
    try {
      if (activeAction === 'resolve') {
        await onResolve(conflict.conflict_id, {
          action: resolutionAction,
          notes: operatorNotes || 'Resolved by operator',
          resolved_at: new Date().toISOString(),
        });
      } else if (activeAction === 'reject') {
        await onReject(conflict.conflict_id, {
          reason: rejectionReason,
          notes: operatorNotes,
          rejected_at: new Date().toISOString(),
        });
      } else if (activeAction === 'defer') {
        await onDefer(conflict.conflict_id, {
          reason: deferReason,
          defer_until: deferUntil || null,
          notes: operatorNotes,
          deferred_at: new Date().toISOString(),
        });
      }
      onClose();
    } catch (err) {
      console.error('Action error:', err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-content"
        style={{ maxWidth: 680, width: '92%' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '1.4rem' }}>{isCritical ? '🚨' : '⚠'}</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="modal-title">{conflict.conflict_id || 'CONF-INCIDENT'}</span>
                <span className={`badge ${getConflictReviewBadgeClass(reviewStatus)}`}>
                  {reviewStatus}
                </span>
                <span className={`badge ${isCritical ? 'badge-critical' : 'badge-high'}`}>
                  {severity.toUpperCase()}
                </span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 2 }}>
                {conflict.conflict_type || 'Spatial-Temporal Corridor Conflict'} • {conflict.location || 'Network Section'}
              </div>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Conflict Summary Box */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 8,
              padding: '12px 14px',
            }}
          >
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f8fafc', marginBottom: 8 }}>
              Collision Context & Headway Violation
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>Location</span>
                <div style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500 }}>{conflict.location || '—'}</div>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>Collision Window</span>
                <div style={{ fontSize: '0.82rem', color: '#f87171', fontFamily: 'monospace', fontWeight: 600 }}>
                  {conflict.start_time || '--:--'} → {conflict.end_time || '--:--'} ({conflict.overlap_minutes || 0}m overlap)
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>Reason Code</span>
                <div style={{ fontSize: '0.82rem', color: '#38bdf8', fontFamily: 'monospace' }}>
                  {conflict.reason_code || conflict.conflict_type || 'TRACK_HEADWAY_BREACH'}
                </div>
              </div>
            </div>
            {conflict.description && (
              <div style={{ marginTop: 10, fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.4 }}>
                {conflict.description}
              </div>
            )}
          </div>

          {/* Involved Entities Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {/* Entity 1 (Maintenance/Block) */}
            <div
              style={{
                background: 'rgba(56, 189, 248, 0.05)',
                border: '1px solid rgba(56, 189, 248, 0.2)',
                borderRadius: 8,
                padding: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 600, textTransform: 'uppercase' }}>
                  🛠️ Work / Possession
                </span>
                <span className="badge badge-outline" style={{ fontSize: '0.65rem' }}>
                  {conflict.entity1_type || 'Block'}
                </span>
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                {conflict.entity1_id || 'BLK-UNKNOWN'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8', marginTop: 4 }}>
                Scheduled window: {conflict.start_time} - {conflict.end_time}
              </div>
            </div>

            {/* Entity 2 (Train / Freight / Passenger) */}
            <div
              style={{
                background: 'rgba(244, 63, 94, 0.05)',
                border: '1px solid rgba(244, 63, 94, 0.2)',
                borderRadius: 8,
                padding: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: '0.72rem', color: '#f43f5e', fontWeight: 600, textTransform: 'uppercase' }}>
                  🚆 Train / Traffic
                </span>
                <span className="badge badge-outline" style={{ fontSize: '0.65rem' }}>
                  {conflict.entity2_type || 'Train'}
                </span>
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                {conflict.entity2_id || 'TRN-UNKNOWN'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8', marginTop: 4 }}>
                Passing window: {conflict.start_time} - {conflict.end_time}
              </div>
            </div>
          </div>

          {/* AutoResolver Recommended Action */}
          {conflict.suggested_action && (
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: 8,
                padding: '12px 14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontWeight: 600, fontSize: '0.8rem' }}>
                <span>💡</span>
                <span>AutoResolver Recommendation:</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#e2e8f0', marginTop: 4, lineHeight: 1.4 }}>
                {conflict.suggested_action}
              </div>
            </div>
          )}

          {/* Operator Action Controls (Operator Only) */}
          {isOperator ? (
            <div
              style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 8,
                padding: '14px',
              }}
            >
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f8fafc', marginBottom: 10 }}>
                Operator Human Verification & Action
              </div>

              {/* Action Tabs */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <button
                  type="button"
                  onClick={() => setActiveAction('resolve')}
                  className={`btn-action ${activeAction === 'resolve' ? 'btn-primary' : 'btn-outline'}`}
                  style={{ flex: 1, padding: '6px 10px', fontSize: '0.78rem' }}
                >
                  ✓ Resolve / Approve
                </button>
                <button
                  type="button"
                  onClick={() => setActiveAction('reject')}
                  className={`btn-action ${activeAction === 'reject' ? 'btn-critical' : 'btn-outline'}`}
                  style={{ flex: 1, padding: '6px 10px', fontSize: '0.78rem' }}
                >
                  ✕ Reject Proposal
                </button>
                <button
                  type="button"
                  onClick={() => setActiveAction('defer')}
                  className={`btn-action ${activeAction === 'defer' ? 'btn-warning' : 'btn-outline'}`}
                  style={{ flex: 1, padding: '6px 10px', fontSize: '0.78rem' }}
                >
                  ⏱ Defer Decision
                </button>
              </div>

              {/* Action specific inputs */}
              {activeAction === 'resolve' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div>
                    <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                      Selected Resolution Strategy
                    </label>
                    <select
                      className="select-input"
                      value={resolutionAction}
                      onChange={(e) => setResolutionAction(e.target.value)}
                      style={{ width: '100%', fontSize: '0.8rem' }}
                    >
                      <option value="ACCEPT_RECOMMENDATION">Accept AutoResolver Recommendation</option>
                      <option value="RESCHEDULE_SLOT">Reschedule to Later Available Window</option>
                      <option value="REASSIGN_TRACK">Reassign to Parallel Loop / Alternative Track</option>
                      <option value="REDUCE_DURATION">Compress Possession Duration (Meet 15m Headway)</option>
                      <option value="MANUAL_OVERRIDE">Manual Clearance with Station Master Coordination</option>
                    </select>
                  </div>
                </div>
              )}

              {activeAction === 'reject' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div>
                    <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                      Rejection Reason Code
                    </label>
                    <select
                      className="select-input"
                      value={rejectionReason}
                      onChange={(e) => setRejectionReason(e.target.value)}
                      style={{ width: '100%', fontSize: '0.8rem' }}
                    >
                      <option value="SCHEDULE_UNVIABLE">Proposed window unviable for heavy freight corridor</option>
                      <option value="RESOURCE_UNAVAILABLE">Required maintenance gang/machine unavailable</option>
                      <option value="PASSENGER_PRIORITY">Priority given to high-speed passenger service</option>
                      <option value="OTHER_OPERATIONAL">Other operational restriction</option>
                    </select>
                  </div>
                </div>
              )}

              {activeAction === 'defer' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div>
                      <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                        Deferral Reason
                      </label>
                      <select
                        className="select-input"
                        value={deferReason}
                        onChange={(e) => setDeferReason(e.target.value)}
                        style={{ width: '100%', fontSize: '0.8rem' }}
                      >
                        <option value="AWAITING_TRAFFIC_UPDATE">Awaiting Live Freight Movement Telemetry</option>
                        <option value="NEXT_SHIFT_REVIEW">Hand over to Next Planning Shift</option>
                        <option value="DIVISION_CONSULTATION">Pending Divisional Control Approval</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                        Defer Until Time (Optional)
                      </label>
                      <input
                        type="time"
                        className="text-input"
                        value={deferUntil}
                        onChange={(e) => setDeferUntil(e.target.value)}
                        style={{ width: '100%', fontSize: '0.8rem' }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Operator Verification Notes */}
              <div style={{ marginTop: 10 }}>
                <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                  Operator Verification Log & Notes
                </label>
                <textarea
                  className="textarea-input"
                  rows={2}
                  value={operatorNotes}
                  onChange={(e) => setOperatorNotes(e.target.value)}
                  placeholder="Provide audit notes for this verification decision..."
                  style={{ width: '100%', fontSize: '0.78rem' }}
                />
              </div>
            </div>
          ) : (
            <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: 12, borderRadius: 8, fontSize: '0.78rem', color: '#94a3b8' }}>
              🔒 <strong>Employee Monitoring View:</strong> Conflict decisions and resolutions must be confirmed by an authorized Chief Controller / Operator.
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
          <button className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          {isOperator && (
            <button
              className={
                activeAction === 'reject'
                  ? 'btn-critical'
                  : activeAction === 'defer'
                  ? 'btn-warning'
                  : 'btn-primary'
              }
              onClick={handleExecute}
              disabled={submitting}
            >
              {submitting
                ? 'Processing...'
                : activeAction === 'reject'
                ? 'Confirm Rejection'
                : activeAction === 'defer'
                ? 'Confirm Deferral'
                : 'Confirm Resolution'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
