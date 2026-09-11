import React, { useState } from 'react';
import PageContainer from '../../components/PageContainer';
import StatCard from '../../components/StatCard';
import ConflictCard from '../../components/ConflictCard';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';

export default function EmployeeConflicts({
  conflicts = [],
  loading = false,
  error = null,
  onRetry,
  targetDate,
}) {
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const filtered = conflicts.filter((c) => {
    if (severityFilter === 'ALL') return true;
    return String(c.severity || '').toLowerCase() === severityFilter.toLowerCase();
  });

  const criticalCount = conflicts.filter((c) => String(c.severity || '').toLowerCase() === 'critical').length;
  const majorCount = conflicts.filter((c) => String(c.severity || '').toLowerCase() === 'major' || String(c.severity || '').toLowerCase() === 'high').length;
  const minorCount = conflicts.length - criticalCount - majorCount;

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">⚠</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            Spatial-Temporal Conflict Detection Report (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Safety analysis report detailing simultaneous track section occupancies and safety headway buffer infractions for <strong>{targetDate}</strong>.
          </div>
        </div>
        <div className="employee-banner-tag">
          {conflicts.length} INCIDENTS
        </div>
      </div>

      {/* Conflict Statistics */}
      <div className="stat-grid">
        <StatCard
          title="TOTAL CONFLICTS"
          value={conflicts.length}
          subtitle={`Detected on ${targetDate}`}
          icon="⚠"
          accent={conflicts.length > 0 ? "amber" : "green"}
          badge={conflicts.length > 0 ? "ATTENTION" : "CLEAR"}
          badgeType={conflicts.length > 0 ? "warning" : "success"}
        />

        <StatCard
          title="CRITICAL COLLISIONS"
          value={criticalCount}
          subtitle="Direct Track Overlap"
          icon="🚨"
          accent="red"
          badge={criticalCount > 0 ? "CRITICAL" : "ZERO"}
          badgeType={criticalCount > 0 ? "critical" : "success"}
        />

        <StatCard
          title="HEADWAY WARNINGS"
          value={minorCount + majorCount}
          subtitle="Buffer Separation < 15m"
          icon="⏱️"
          accent="amber"
          badge="BUFFER"
          badgeType="info"
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>⚠ Spatial-Temporal Conflict Log</span>
              <span className={`badge ${conflicts.length > 0 ? 'badge-critical' : 'badge-green'}`}>
                {filtered.length} INCIDENTS
              </span>
              <span className="badge badge-outline">READ-ONLY AUDIT</span>
            </div>
            <div className="panel-subtitle">
              Collision detection engine telemetry across passenger timetables, freight paths, and track possession blocks
            </div>
          </div>
        </div>

        <div className="panel-body">
          <div className="filter-toolbar">
            <div className="filter-group">
              <select
                className="select-control"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
              >
                <option value="ALL">All Severities</option>
                <option value="Critical">Critical Only</option>
                <option value="Major">Major Only</option>
                <option value="Minor">Minor Only</option>
              </select>
            </div>
            <span className="badge badge-outline">
              Showing {filtered.length} of {conflicts.length} incidents
            </span>
          </div>

          {error ? (
            <ErrorState
              title="Failed to Load Conflict Analysis"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Scanning operational entities for spatial-temporal overlaps..." />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 16px', color: '#10b981' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>🛡️</div>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>No Operational Conflicts Detected</div>
              <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginTop: 4 }}>
                All track possessions and train paths maintain required safety headways for {targetDate}.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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
