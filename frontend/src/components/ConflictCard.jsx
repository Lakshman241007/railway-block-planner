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

  // Severity-weighted presentation: the more severe the conflict, the more
  // visual pressure the card carries (border weight + icon), so a scan down
  // a list of conflicts reads priority at a glance without extra text.
  const isCritical = sev === 'critical';

  return (
    <div className={`operation-card ${sevClass}`} style={isCritical ? { borderLeftWidth: 4 } : undefined}>
      <div className="card-header-row">
        <div>
          <div className="card-code" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>{isCritical ? '⛔' : '⚠'}</span>
            <span>{conflict.conflict_id || 'CONF-0001'}</span>
          </div>
          <div className="card-meta-text">{conflict.conflict_type || 'Train-Block Overlap'}</div>
        </div>
        <span className={`badge ${getBadgeClass(sev)}`}>
          {sev.toUpperCase()}
        </span>
      </div>

      <div className="card-detail-box">
        <div className="card-kv-row">
          <span className="card-kv-label">Location</span>
          <span className="card-kv-value">{conflict.location}</span>
        </div>
        <div className="card-kv-row">
          <span className="card-kv-label">Affected entities</span>
          <span className="card-kv-value mono" style={{ color: 'var(--accent-bright)' }}>
            {conflict.entity1_type} ({conflict.entity1_id}) ⚡ {conflict.entity2_type} ({conflict.entity2_id})
          </span>
        </div>
        <div className="card-kv-row">
          <span className="card-kv-label">Collision window</span>
          <span className="card-kv-value mono" style={{ color: '#f87171' }}>
            {conflict.start_time} → {conflict.end_time} ({conflict.overlap_minutes || 0}m overlap)
          </span>
        </div>
        <div style={{ marginTop: 4, color: '#cbd5e1', lineHeight: 1.4, fontSize: '0.75rem' }}>
          {conflict.description}
        </div>
      </div>

      {conflict.suggested_action && (
        <div className="card-resolution-box">
          <strong>💡 Recommended resolution:</strong> {conflict.suggested_action}
        </div>
      )}
    </div>
  );
}
