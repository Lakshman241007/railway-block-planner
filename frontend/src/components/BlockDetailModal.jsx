import React from 'react';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';

export default function BlockDetailModal({ block, onClose }) {
  if (!block) return null;

  const blockId = block.block_id || block.block_request_id || block.request_id || block.asset_id || 'REQ-001';
  const isOvernight = (block.start_time && block.end_time && block.end_time < block.start_time) ||
                      (block.requested_start && block.requested_end && block.requested_end < block.requested_start);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Operational Detail Inspector
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#00f0ff', fontFamily: 'var(--font-mono)' }}>
              {blockId} {isOvernight ? '🌙 (Overnight Block)' : ''}
            </div>
          </div>
          <button
            className="btn btn-secondary btn-icon-only btn-sm"
            onClick={onClose}
            style={{ borderRadius: '50%' }}
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Location / Section</span>
              <span className="detail-val" style={{ fontWeight: 700 }}>{block.location || 'Chennai-Arakkonam'}</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Service Date</span>
              <span className="detail-val mono">{block.service_date || block.requested_date || '--'}</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Operational Window</span>
              <span className="detail-val mono" style={{ color: '#34d399' }}>
                {block.start_time || block.requested_start || '--'} ➔ {block.end_time || block.requested_end || '--'}
              </span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Duration</span>
              <span className="detail-val mono">{block.duration_minutes || block.required_duration || '--'} Minutes</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Priority Tier</span>
              <div><PriorityBadge priority={block.priority} /></div>
            </div>

            <div className="detail-item">
              <span className="detail-label">Status</span>
              <div><StatusBadge status={block.status} /></div>
            </div>

            <div className="detail-item">
              <span className="detail-label">Equipment / Machinery</span>
              <span className="detail-val">{block.equipment || 'Standard Track Gang'}</span>
            </div>

            <div className="detail-item">
              <span className="detail-label">Resource Gangs</span>
              <span className="detail-val mono">{block.required_resources || 2} Crews</span>
            </div>
          </div>

          {/* Causal or Operational Reason */}
          <div className="card-detail-box" style={{ background: '#0a0e17' }}>
            <span className="detail-label">Operational Justification / Description</span>
            <span style={{ color: '#e2e8f0', fontSize: '0.8rem', lineHeight: 1.4 }}>
              {block.reason || block.description || block.maintenance_type || 'Scheduled preventive corridor possession.'}
            </span>
          </div>

          {/* Solver Diagnostics if Unscheduled */}
          {block.reason && block.reason.toLowerCase().includes('preempt') && (
            <div className="card-resolution-box" style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: '#ef4444' }}>
              <strong style={{ color: '#f87171' }}>CP-SAT Solver Diagnostic:</strong>
              <div style={{ color: '#fca5a5', marginTop: 4 }}>
                This request was not scheduled because higher priority possessions saturated track availability or machine limits on this corridor section.
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
