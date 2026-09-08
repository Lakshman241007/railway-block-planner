/**
 * @file ConflictCard.jsx
 * @description Incident & Conflict Alert card displaying operational collisions, entity priorities,
 * and rule-based priority precedence recommendations.
 * @module components/ConflictCard
 */

import React from 'react';
import PriorityBadge from './PriorityBadge';

function EntityTag({ id, type, priority }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <span className="table-cell-mono">{type} ({id})</span>
      {priority && (
        ['Critical', 'High', 'Medium', 'Low'].includes(priority) ? (
          <PriorityBadge priority={priority} />
        ) : (
          <span className="badge badge-cyan" style={{ fontSize: '0.65rem', padding: '1px 5px' }}>{priority}</span>
        )
      )}
    </span>
  );
}

export default function ConflictCard({ conflict }) {
  const sev = String(conflict.severity || 'Medium').toLowerCase();
  const sevBadge = sev === 'critical' ? 'badge-critical' : sev === 'high' ? 'badge-high' : 'badge-medium';

  return (
    <div className={`operation-card conflict-${sev}`}>
      <div className="card-header-row">
        <div>
          <div className="card-code" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>⚠</span>
            <span>{conflict.conflict_id || 'CONF-0001'}</span>
          </div>
          <div className="card-meta-text">{conflict.conflict_type || 'Train-Block Headway Conflict'}</div>
        </div>
        <span className={`badge ${sevBadge}`}>{sev.toUpperCase()} SEVERITY</span>
      </div>

      <div className="card-detail-box">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
          <span style={{ color: '#94a3b8' }}>Affected Entities:</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <EntityTag id={conflict.entity1_id} type={conflict.entity1_type} priority={conflict.entity1_priority} />
            <span style={{ color: '#f87171', fontWeight: 700 }}>⚡</span>
            <EntityTag id={conflict.entity2_id} type={conflict.entity2_type} priority={conflict.entity2_priority} />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span style={{ color: '#94a3b8' }}>Collision Window:</span>
          <span className="table-cell-mono" style={{ color: '#f87171' }}>
            {conflict.start_time} ➔ {conflict.end_time} ({conflict.overlap_minutes || 0}m overlap)
          </span>
        </div>

        {conflict.precedence_entity_id && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
            <span style={{ color: '#94a3b8' }}>Operational Precedence:</span>
            <span className="badge badge-green">🎯 {conflict.precedence_entity_id}</span>
          </div>
        )}

        <div style={{ marginTop: 6, color: '#cbd5e1', lineHeight: 1.4, fontSize: '0.8rem' }}>
          {conflict.description}
        </div>
      </div>

      {conflict.suggested_action && (
        <div className="card-resolution-box" style={{ borderLeft: '3px solid #34d399', background: 'rgba(52, 211, 153, 0.08)' }}>
          <strong>💡 Recommended Resolution:</strong> {conflict.suggested_action}
        </div>
      )}
    </div>
  );
}
