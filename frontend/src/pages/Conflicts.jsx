import React, { useState } from 'react';
import ConflictCard from '../components/ConflictCard';
import LoadingState from '../components/LoadingState';

export default function Conflicts({ conflicts = [], loading = false }) {
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const filtered = conflicts.filter((c) => {
    if (severityFilter === 'ALL') return true;
    return String(c.severity || '').toLowerCase() === severityFilter.toLowerCase();
  });

  const criticalCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'critical').length;
  const highCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'high').length;
  const mediumCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'medium').length;
  const lowCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'low').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Severity Stats Grid */}
      <div className="stat-grid">
        <div className="stat-card accent-red">
          <div className="stat-card-header">
            <span>CRITICAL SEVERITY</span>
            <span>🚨</span>
          </div>
          <div className="stat-card-value" style={{ color: '#ef4444' }}>
            {criticalCount}
          </div>
          <div className="stat-card-footer">
            <span>Direct train-block collision</span>
          </div>
        </div>

        <div className="stat-card accent-amber">
          <div className="stat-card-header">
            <span>HIGH SEVERITY</span>
            <span>⚠</span>
          </div>
          <div className="stat-card-value" style={{ color: '#f97316' }}>
            {highCount}
          </div>
          <div className="stat-card-footer">
            <span>Simultaneous track occupancy</span>
          </div>
        </div>

        <div className="stat-card accent-green">
          <div className="stat-card-header">
            <span>HEADWAY BUFFER VIOLATIONS</span>
            <span>⏱️</span>
          </div>
          <div className="stat-card-value" style={{ color: '#eab308' }}>
            {mediumCount + lowCount}
          </div>
          <div className="stat-card-footer">
            <span>&lt; 15 min safety clearance</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>⚠ Spatial-Temporal Conflict & Incident Center</span>
              <span className="badge badge-critical">{filtered.length} INCIDENTS</span>
            </div>
            <div className="panel-subtitle">
              Automated detection of train overlaps, safety buffer violations & machine capacity saturation
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className={`btn btn-sm ${severityFilter === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSeverityFilter('ALL')}
            >
              All ({conflicts.length})
            </button>
            <button
              className={`btn btn-sm ${severityFilter === 'CRITICAL' ? 'btn-danger' : 'btn-secondary'}`}
              onClick={() => setSeverityFilter('CRITICAL')}
            >
              Critical ({criticalCount})
            </button>
            <button
              className={`btn btn-sm ${severityFilter === 'HIGH' ? 'btn-danger' : 'btn-secondary'}`}
              onClick={() => setSeverityFilter('HIGH')}
            >
              High ({highCount})
            </button>
            <button
              className={`btn btn-sm ${severityFilter === 'MEDIUM' ? 'btn-secondary' : 'btn-secondary'}`}
              onClick={() => setSeverityFilter('MEDIUM')}
            >
              Medium/Low ({mediumCount + lowCount})
            </button>
          </div>
        </div>

        <div className="panel-body">
          {loading ? (
            <LoadingState message="Scanning network for operational conflicts..." />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '50px', color: '#10b981' }}>
              <div style={{ fontSize: '2rem', marginBottom: 8 }}>🛡️</div>
              <div style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>No Operational Conflicts Detected</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 4 }}>
                All scheduled block possessions meet safety buffer criteria and have exclusive track possession.
              </div>
            </div>
          ) : (
            <div className="card-grid">
              {filtered.map((conflict, idx) => (
                <ConflictCard key={conflict.conflict_id || idx} conflict={conflict} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
