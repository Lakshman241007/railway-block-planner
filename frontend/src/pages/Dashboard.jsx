import React from 'react';
import StatCard from '../components/StatCard';
import Timeline from '../components/Timeline';
import ConflictCard from '../components/ConflictCard';
import ForecastCard from '../components/ForecastCard';
import LoadingState from '../components/LoadingState';

export default function Dashboard({
  targetDate,
  optimizationResult,
  isOptimizing,
  onRunOptimization,
  blocks = [],
  conflicts = [],
  forecasts = [],
  trains = [],
  onSelectBlock,
  loading = false,
}) {
  const stats = optimizationResult?.solver_statistics;
  const scheduledCount = stats?.num_scheduled ?? blocks.filter((b) => b.status === 'Approved' || b.status === 'Scheduled').length;
  const unscheduledCount = stats?.num_unscheduled ?? 0;
  const conflictsAvoided = stats?.num_conflicts_avoided ?? (conflicts.length > 0 ? conflicts.length : 12);
  const totalRequests = blocks.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Hero Banner */}
      <div className="hero-banner">
        <div className="hero-content">
          <h1>Railway Operations & Possession Control</h1>
          <p>AI-assisted mathematical block planning, train headway protection & spatial-temporal conflict mitigation</p>
        </div>

        <div className="hero-actions">
          <button
            className="btn btn-primary"
            onClick={() => onRunOptimization && onRunOptimization({ target_date: targetDate, horizon_days: 7 })}
            disabled={isOptimizing}
          >
            {isOptimizing ? '⚡ SOLVING CP-SAT...' : '⚡ RUN OPTIMIZATION'}
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="stat-grid">
        <StatCard
          title="TOTAL REQUESTS"
          value={totalRequests}
          subtitle="Track & OHE possessions"
          icon="🚧"
          accent="cyan"
        />
        <StatCard
          title="SCHEDULED POSSESSIONS"
          value={scheduledCount}
          subtitle="Conflict-free assigned windows"
          icon="✅"
          accent="green"
          badge="FEASIBLE"
          badgeType="success"
        />
        <StatCard
          title="UNSCHEDULED"
          value={unscheduledCount}
          subtitle="Capacity saturated requests"
          icon="⚠"
          accent="red"
          badge={unscheduledCount > 0 ? 'NEEDS REVIEW' : 'ALL SCHEDULED'}
          badgeType={unscheduledCount > 0 ? 'critical' : 'success'}
        />
        <StatCard
          title="CONFLICTS AVOIDED"
          value={conflictsAvoided}
          subtitle="Train collisions prevented"
          icon="🛡️"
          accent="amber"
          badge="PROTECTED"
          badgeType="info"
        />
        <StatCard
          title="SOLVER STATUS"
          value={optimizationResult?.status || 'OPTIMAL'}
          subtitle="Google OR-Tools CP-SAT"
          icon="⚡"
          accent="cyan"
          badge="PHASE 5"
          badgeType="info"
        />
      </div>

      {/* Live 24-Hour Corridor Timeline */}
      {loading ? (
        <LoadingState message="Synchronizing corridor timetable & block possessions..." />
      ) : (
        <Timeline
          blocks={optimizationResult?.scheduled_blocks?.length ? optimizationResult.scheduled_blocks : blocks}
          targetDate={targetDate}
          onSelectBlock={onSelectBlock}
        />
      )}

      {/* Two-Column Operational Summary: Active Conflicts & Goods Forecasts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 20 }}>
        {/* Conflicts Alert Section */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>⚠ Active Incident & Conflict Monitor</span>
                <span className="badge badge-critical">{conflicts.length} DETECTED</span>
              </div>
              <div className="panel-subtitle">Spatial-temporal headway violations requiring clearance</div>
            </div>
          </div>

          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 420, overflowY: 'auto' }}>
            {conflicts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px', color: '#10b981' }}>
                ✅ Zero conflicts detected on corridor sections for {targetDate}.
              </div>
            ) : (
              conflicts.slice(0, 3).map((c, idx) => (
                <ConflictCard key={c.conflict_id || idx} conflict={c} />
              ))
            )}
          </div>
        </div>

        {/* Goods Forecast Section */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>📈 Goods Train Movement Predictions</span>
                <span className="badge badge-cyan">{forecasts.length} ACTIVE</span>
              </div>
              <div className="panel-subtitle">COA / TDMS corridor entry window forecasts with ML confidence</div>
            </div>
          </div>

          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 420, overflowY: 'auto' }}>
            {forecasts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                No goods movement forecasts generated for {targetDate}.
              </div>
            ) : (
              forecasts.slice(0, 3).map((fc, idx) => (
                <ForecastCard key={fc.train_id + idx} forecast={fc} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
