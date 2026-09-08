import React from 'react';

export default function ConflictCard({ conflict, onResolveClick }) {
  const sev = String(conflict.severity || 'Medium').toLowerCase();
  const sevClass = `conflict-${sev}`;

  const getBadgeClass = (severity) => {
    switch (severity) {
      case 'critical':
        return 'badge-critical';
      case 'high':
        return 'badge-high';
      case 'medium':
      default:
        return 'badge-medium';
    }
  };

  return (
    <div className={`operation-card ${sevClass}`}>
      <div className="card-header-row">
        <div>
          <div className="card-code" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>⚠</span>
            <span>{conflict.conflict_id || 'CONF-0001'}</span>
          </div>
          <div className="card-meta-text">{conflict.conflict_type || 'Train-Block Overlap'}</div>
        </div>
        <span className={`badge ${getBadgeClass(sev)}`}>
          {sev.toUpperCase()}
        </span>
      </div>

      <div className="card-detail-box">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Location</span>
          <span style={{ color: '#fff', fontWeight: 600 }}>{conflict.location}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Affected Entities</span>
          <span className="table-cell-mono">
            {conflict.entity1_type} ({conflict.entity1_id}) ⚡ {conflict.entity2_type} ({conflict.entity2_id})
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Collision Window</span>
          <span className="table-cell-mono" style={{ color: '#f87171' }}>
            {conflict.start_time} → {conflict.end_time} ({conflict.overlap_minutes || 0}m overlap)
          </span>
        </div>
        <div style={{ marginTop: 4, color: '#cbd5e1', lineHeight: 1.4, fontSize: '0.75rem' }}>
          {conflict.description}
        </div>
      </div>

      {conflict.suggested_action && (
        <div className="card-resolution-box">
          <strong>💡 Recommended Resolution:</strong> {conflict.suggested_action}
        </div>
      )}
    </div>
  );
}
