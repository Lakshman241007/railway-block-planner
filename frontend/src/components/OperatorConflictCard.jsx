import React, { useState } from 'react';
import { ConflictReviewStatus, getConflictReviewBadgeClass } from '../types';

export default function OperatorConflictCard({
  conflict,
  onReview,
  onResolve,
  onReject,
  onDefer,
  isResolving = false,
}) {
  const [expanded, setExpanded] = useState(false);

  const sev = String(conflict.severity || 'Medium').toLowerCase();
  const isCritical = sev === 'critical';
  const isHigh = sev === 'high';

  const reviewStatus =
    conflict.review_status ||
    conflict.status ||
    (conflict.auto_resolved
      ? ConflictReviewStatus.AUTO_RESOLVED
      : ConflictReviewStatus.REQUIRES_HUMAN_REVIEW);

  const isRequiresReview = reviewStatus === ConflictReviewStatus.REQUIRES_HUMAN_REVIEW;
  const isAutoResolved = reviewStatus === ConflictReviewStatus.AUTO_RESOLVED;
  const isHumanResolved = reviewStatus === ConflictReviewStatus.HUMAN_RESOLVED;
  const isRejected = reviewStatus === ConflictReviewStatus.REJECTED;
  const isDeferred = reviewStatus === ConflictReviewStatus.DEFERRED;

  const getSeverityBadgeClass = (s) => {
    switch (s) {
      case 'critical':
        return 'badge-critical';
      case 'high':
        return 'badge-high';
      case 'medium':
        return 'badge-medium';
      case 'low':
      default:
        return 'badge-low';
    }
  };

  return (
    <div
      className={`operation-card conflict-${sev}`}
      style={{
        borderLeftWidth: 4,
        borderLeftColor: isCritical
          ? 'var(--status-danger)'
          : isHigh
          ? 'var(--status-high)'
          : 'var(--status-warning)',
        background: 'linear-gradient(180deg, #131f37 0%, #0c1424 100%)',
        border: '1px solid rgba(255, 255, 255, 0.09)',
        borderRadius: 12,
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.35)',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      {/* Card Header Row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 8,
              background: isCritical ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              border: `1px solid ${isCritical ? 'rgba(239, 68, 68, 0.4)' : 'rgba(245, 158, 11, 0.4)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.25rem',
              flexShrink: 0,
            }}
          >
            {isCritical ? '⛔' : '⚠'}
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span className="mono" style={{ fontSize: '0.98rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '0.5px' }}>
                {conflict.conflict_id || 'CONF-0001'}
              </span>
              <span className={`badge ${getSeverityBadgeClass(sev)}`}>
                {sev.toUpperCase()} SEVERITY
              </span>
              <span className={`badge ${getConflictReviewBadgeClass(reviewStatus)}`}>
                {reviewStatus}
              </span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 3 }}>
              {conflict.conflict_type || 'Train-Block Overlap & Spatial Collision'} • Location: <strong style={{ color: '#cbd5e1' }}>{conflict.location || 'Network Section'}</strong>
            </div>
          </div>
        </div>

        {/* Quick Review Status Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isAutoResolved && (
            <span style={{ fontSize: '0.74rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(16, 185, 129, 0.1)', padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              🤖 Handled by AutoResolver
            </span>
          )}
          {isHumanResolved && (
            <span style={{ fontSize: '0.74rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(56, 189, 248, 0.1)', padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(56, 189, 248, 0.3)' }}>
              ✓ Operator Resolved
            </span>
          )}
          {isDeferred && (
            <span style={{ fontSize: '0.74rem', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(245, 158, 11, 0.1)', padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(245, 158, 11, 0.3)' }}>
              ⏱ Deferred
            </span>
          )}
          {isRejected && (
            <span style={{ fontSize: '0.74rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(239, 68, 68, 0.1)', padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              ✕ Resolution Rejected
            </span>
          )}
        </div>
      </div>

      {/* Main Metadata Grid Box */}
      <div
        style={{
          background: 'rgba(9, 14, 26, 0.75)',
          border: '1px solid rgba(255, 255, 255, 0.07)',
          borderRadius: 8,
          padding: '14px 18px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16,
        }}
      >
        <div>
          <span style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
            Location / Section
          </span>
          <div style={{ fontSize: '0.86rem', color: '#f8fafc', fontWeight: 600, marginTop: 3 }}>
            {conflict.location || '—'}
          </div>
        </div>

        <div>
          <span style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
            Affected Entities
          </span>
          <div style={{ fontSize: '0.86rem', marginTop: 3, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#38bdf8', fontWeight: 600 }}>
              {conflict.entity1_type || 'Block'}: {conflict.entity1_id || 'BLK-UNKNOWN'}
            </span>
            <span style={{ color: '#64748b' }}>⚡</span>
            <span style={{ color: '#f43f5e', fontWeight: 600 }}>
              {conflict.entity2_type || 'Train'}: {conflict.entity2_id || 'TRN-UNKNOWN'}
            </span>
          </div>
        </div>

        <div>
          <span style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
            Collision Window & Overlap
          </span>
          <div className="mono" style={{ fontSize: '0.86rem', color: isCritical ? '#f87171' : '#fbbf24', fontWeight: 700, marginTop: 3 }}>
            {conflict.start_time || '--:--'} → {conflict.end_time || '--:--'}
            <span style={{ fontSize: '0.76rem', color: '#94a3b8', fontWeight: 400, marginLeft: 6 }}>
              ({conflict.overlap_minutes || 0}m overlap)
            </span>
          </div>
        </div>
      </div>

      {/* Description Context */}
      {conflict.description && (
        <div style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.5, background: 'rgba(255, 255, 255, 0.02)', padding: '10px 14px', borderRadius: 6 }}>
          {conflict.description}
        </div>
      )}

      {/* AutoResolver Recommended Action Box */}
      {conflict.suggested_action && (
        <div
          style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.28)',
            borderRadius: 8,
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
          }}
        >
          <span style={{ fontSize: '1.1rem', lineHeight: 1 }}>💡</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              AutoResolver Recommended Resolution:
            </div>
            <div style={{ fontSize: '0.82rem', color: '#f1f5f9', marginTop: 3, lineHeight: 1.45 }}>
              {conflict.suggested_action}
            </div>
          </div>
        </div>
      )}

      {/* Expandable Technical Telemetry */}
      {expanded && (
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            borderRadius: 8,
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            fontSize: '0.78rem',
          }}
        >
          <div style={{ fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.7rem' }}>
            Technical Incident Telemetry & Audit Log
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
            <div>
              <span style={{ color: '#64748b' }}>Reason Code: </span>
              <span className="mono" style={{ color: '#cbd5e1' }}>{conflict.reason_code || conflict.conflict_type || 'HEADWAY_BUFFER_BREACH'}</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Safety Headway: </span>
              <span style={{ color: '#cbd5e1' }}>15 minutes required</span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Detection Engine: </span>
              <span style={{ color: '#cbd5e1' }}>Spatial-Temporal ConflictDetector</span>
            </div>
          </div>
          {conflict.resolution_notes && (
            <div style={{ marginTop: 6, paddingTop: 8, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <span style={{ color: '#34d399', fontWeight: 600 }}>Operator Notes: </span>
              <span style={{ color: '#e2e8f0' }}>{conflict.resolution_notes}</span>
            </div>
          )}
          {conflict.rejection_reason && (
            <div style={{ marginTop: 6, paddingTop: 8, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <span style={{ color: '#f87171', fontWeight: 600 }}>Rejection Reason: </span>
              <span style={{ color: '#e2e8f0' }}>{conflict.rejection_reason}</span>
            </div>
          )}
          {conflict.defer_reason && (
            <div style={{ marginTop: 6, paddingTop: 8, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <span style={{ color: '#fbbf24', fontWeight: 600 }}>Deferral Note: </span>
              <span style={{ color: '#e2e8f0' }}>{conflict.defer_reason}</span>
            </div>
          )}
        </div>
      )}

      {/* Operator Decision Action Area */}
      <div
        style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          paddingTop: 14,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        {/* Toggle Details Button */}
        <button
          type="button"
          className="btn-action btn-outline"
          style={{ padding: '6px 12px', fontSize: '0.76rem', color: '#94a3b8' }}
          onClick={() => setExpanded((prev) => !prev)}
        >
          {expanded ? '▲ Hide Details' : '▼ View Full Incident Details'}
        </button>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn-action btn-secondary"
            style={{ padding: '7px 14px', fontSize: '0.8rem', fontWeight: 600 }}
            onClick={() => onReview(conflict)}
          >
            🔍 Review Details
          </button>

          {isRequiresReview && (
            <>
              <button
                type="button"
                className="btn-action btn-primary"
                style={{ padding: '7px 16px', fontSize: '0.8rem', fontWeight: 700 }}
                onClick={() => onResolve(conflict.conflict_id, {
                  action: conflict.suggested_action || 'ACCEPT_RECOMMENDATION',
                  notes: 'Quick resolved by Chief Controller with AutoResolver recommendation',
                })}
                disabled={isResolving}
              >
                ✓ Resolve Conflict
              </button>

              <button
                type="button"
                className="btn-action btn-outline"
                style={{ padding: '7px 14px', fontSize: '0.8rem', color: '#fbbf24', borderColor: 'rgba(245, 158, 11, 0.4)' }}
                onClick={() => onDefer(conflict.conflict_id, {
                  reason: 'AWAITING_TRAFFIC_UPDATE',
                  notes: 'Deferred to next operational assessment',
                })}
              >
                ⏱ Defer
              </button>

              <button
                type="button"
                className="btn-action btn-outline"
                style={{ padding: '7px 14px', fontSize: '0.8rem', color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.4)' }}
                onClick={() => onReject(conflict.conflict_id, {
                  reason: 'SCHEDULE_UNVIABLE',
                  notes: 'Rejected proposed resolution',
                })}
              >
                ✕ Reject
              </button>
            </>
          )}

          {!isRequiresReview && (
            <button
              type="button"
              className="btn-action btn-outline"
              style={{ padding: '6px 12px', fontSize: '0.76rem' }}
              onClick={() => onReview(conflict)}
            >
              Change Decision...
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
