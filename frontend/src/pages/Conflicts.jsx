import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import ConflictCard from '../components/ConflictCard';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

export default function Conflicts({ conflicts = [], blocks = [], loading = false, error = null, onRetry, targetDate }) {
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const filtered = conflicts.filter((c) => {
    if (severityFilter === 'ALL') return true;
    if (severityFilter === 'MEDIUM') {
      const s = String(c.severity || '').toLowerCase();
      return s === 'medium' || s === 'low';
    }
    return String(c.severity || '').toLowerCase() === severityFilter.toLowerCase();
  });

  const criticalCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'critical').length;
  const highCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'high').length;
  const mediumCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'medium').length;
  const lowCount = conflicts.filter((c) => String(c.severity).toLowerCase() === 'low').length;

  return (
    <PageContainer>
      {/* Severity Stats Grid */}
      <div className="stat-grid">
        <StatCard
          title="CRITICAL SEVERITY"
          value={criticalCount}
          subtitle="Direct train-block collision"
          icon="🚨"
          accent="red"
          badge="CRITICAL"
          badgeType="critical"
        />

        <StatCard
          title="HIGH SEVERITY"
          value={highCount}
          subtitle="Simultaneous track occupancy"
          icon="⚠"
          accent="amber"
          badge="HIGH"
          badgeType="warning"
        />

        <StatCard
          title="HEADWAY BUFFER VIOLATIONS"
          value={mediumCount + lowCount}
          subtitle="< 15 min safety clearance"
          icon="⏱️"
          accent="green"
          badge="BUFFER"
          badgeType="info"
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>⚠ Spatial-Temporal Conflict & Incident Center</span>
              <span className={`badge ${filtered.length > 0 ? 'badge-critical' : 'badge-low'}`}>
                {filtered.length} INCIDENTS
              </span>
            </div>
            <div className="panel-subtitle">
              Automated detection of train overlaps, safety buffer violations & machine capacity saturation for {targetDate}
            </div>
          </div>

          <div className="segmented-control">
            <button
              className={`segmented-tab ${severityFilter === 'ALL' ? 'active' : ''}`}
              onClick={() => setSeverityFilter('ALL')}
            >
              All ({conflicts.length})
            </button>
            <button
              className={`segmented-tab ${severityFilter === 'CRITICAL' ? 'active' : ''}`}
              onClick={() => setSeverityFilter('CRITICAL')}
            >
              Critical ({criticalCount})
            </button>
            <button
              className={`segmented-tab ${severityFilter === 'HIGH' ? 'active' : ''}`}
              onClick={() => setSeverityFilter('HIGH')}
            >
              High ({highCount})
            </button>
            <button
              className={`segmented-tab ${severityFilter === 'MEDIUM' ? 'active' : ''}`}
              onClick={() => setSeverityFilter('MEDIUM')}
            >
              Medium/Low ({mediumCount + lowCount})
            </button>
          </div>
        </div>

        <div className="panel-body">
          {error ? (
            <ErrorState
              title="Failed to Detect Operational Conflicts"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Scanning network for operational conflicts..." />
          ) : filtered.length === 0 && blocks.length === 0 ? (
            <EmptyState
              icon="📭"
              title="No Block Data Available"
              message="No block possession requests available to analyze for conflicts."
            />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#10b981' }}>
              <div style={{ fontSize: '1.8rem', marginBottom: 6 }}>🛡️</div>
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>No Operational Conflicts Detected</div>
              <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 4 }}>
                All scheduled block possessions meet safety buffer criteria and have exclusive track possession for {targetDate}.
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
    </PageContainer>
  );
}
