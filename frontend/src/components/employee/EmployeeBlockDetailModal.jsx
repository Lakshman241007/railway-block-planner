import React from 'react';
import PriorityBadge from '../PriorityBadge';
import StatusBadge from '../StatusBadge';

/**
 * Genuinely Read-Only Block Detail Inspector for Employee / Monitoring Dashboard.
 * Strictly no form controls, no edit button, no save button, no mutation triggers.
 */
export default function EmployeeBlockDetailModal({ block, onClose }) {
  if (!block) return null;

  const blockId = block.block_id || block.request_id || block.id || 'N/A';
  const isOvernight = block.start_time && block.end_time && block.end_time < block.start_time;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-box"
        style={{ maxWidth: 640, borderTop: '4px solid #10b981' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span className="badge badge-green" style={{ fontSize: '0.7rem', letterSpacing: 0.5 }}>
                👁️ READ-ONLY OPERATIONAL RECORD
              </span>
              <span className="badge badge-outline" style={{ fontSize: '0.7rem' }}>
                MONITORING VIEW
              </span>
            </div>
            <div className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>{blockId}</span>
              {isOvernight && <span title="Overnight window across midnight">🌙</span>}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
              BDMS Disconnection & Possession Record — Inspection Only
            </div>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Status & Priority Row */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', background: 'rgba(15, 23, 42, 0.6)', padding: 12, borderRadius: 6, border: '1px solid #1e293b' }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 2 }}>CURRENT STATUS</div>
              <StatusBadge status={block.status || 'Scheduled'} />
            </div>
            <div style={{ borderLeft: '1px solid #334155', paddingLeft: 12 }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 2 }}>SAFETY PRIORITY</div>
              <PriorityBadge priority={block.priority || 'Medium'} />
            </div>
            <div style={{ borderLeft: '1px solid #334155', paddingLeft: 12 }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 2 }}>BLOCK TYPE</div>
              <span className="badge badge-cyan" style={{ textTransform: 'uppercase' }}>
                {block.block_type || 'Track'}
              </span>
            </div>
            {block.fit_score != null && (
              <div style={{ borderLeft: '1px solid #334155', paddingLeft: 12 }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: 2 }}>CP-SAT FIT</div>
                <span className="badge badge-green">
                  {(block.fit_score * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          {/* Grid of Read-Only Attributes */}
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Corridor Section</span>
              <span className="detail-value table-cell-highlight">{block.section || '—'}</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Specific Location / Station</span>
              <span className="detail-value">{block.location || '—'}</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Track Identification</span>
              <span className="detail-value table-cell-mono">{block.track_number || 'Main Line'}</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Service Date</span>
              <span className="detail-value table-cell-mono">
                {block.service_date || block.requested_date || '—'}
              </span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Scheduled Window</span>
              <span className="detail-value table-cell-mono" style={{ color: '#34d399', fontWeight: 600 }}>
                {block.start_time || block.requested_start || '--:--'} → {block.end_time || block.requested_end || '--:--'}
                {isOvernight ? ' (Overnight)' : ''}
              </span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Approved Duration</span>
              <span className="detail-value table-cell-mono">
                {block.duration_minutes || block.required_duration || '—'} minutes
              </span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Machine / Equipment Required</span>
              <span className="detail-value">
                <span className="badge badge-outline">{block.equipment || 'Standard Gang'}</span>
              </span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Gang / Crew Resource Allocation</span>
              <span className="detail-value table-cell-mono">
                {block.required_resources ?? 1} Gang(s)
              </span>
            </div>
          </div>

          {/* Operational Reason */}
          <div style={{ background: 'rgba(15, 23, 42, 0.4)', padding: 12, borderRadius: 6, border: '1px solid #1e293b' }}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
              Operational Reason & Justification
            </div>
            <div style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.5 }}>
              {block.reason || 'Preventive track maintenance and inspection.'}
            </div>
          </div>

          {/* Security & Role Notice */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'rgba(16, 185, 129, 0.05)', borderRadius: 4, border: '1px solid rgba(16, 185, 129, 0.2)', fontSize: '0.72rem', color: '#94a3b8' }}>
            <span>ℹ️</span>
            <span>You are viewing this record in Employee Read-Only Mode. Changes can only be submitted by an authorized Operator.</span>
          </div>
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onClose}>
            Close Inspection
          </button>
        </div>
      </div>
    </div>
  );
}
