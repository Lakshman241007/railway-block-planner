import React from 'react';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import Timeline from '../components/Timeline';
import ConflictCard from '../components/ConflictCard';
import ForecastCard from '../components/ForecastCard';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

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
  error = null,
  onRetry,
}) {
  const stats = optimizationResult?.solver_statistics;
  const scheduledCount = stats?.num_scheduled ?? blocks.filter((b) => b.status === 'Approved' || b.status === 'Scheduled').length;
  const unscheduledCount = stats?.num_unscheduled ?? 0;
  const conflictsAvoided = stats?.num_conflicts_avoided ?? 0;
  const totalRequests = blocks.length;

  return (
    <PageContainer>
      {/* Error Banner if telemetry failed */}
      {error && (
        <ErrorState
          title="Telemetry Connection Warning"
          message={error}
          onRetry={onRetry}
        />
      )}

      {/* Hero Overview */}
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
          badge={optimizationResult ? 'OPTIMIZED' : 'CURRENT'}
          badgeType="success"
        />
        <StatCard
          title="UNSCHEDULED"
          value={unscheduledCount}
          subtitle="Capacity saturated requests"
          icon="⚠"
          accent="red"
          badge={unscheduledCount > 0 ? 'NEEDS REVIEW' : 'NONE'}
          badgeType={unscheduledCount > 0 ? 'critical' : 'success'}
        />
        <StatCard
          title="CONFLICTS AVOIDED"
          value={conflictsAvoided}
          subtitle="Train collisions prevented"
          icon="🛡️"
          accent="amber"
          badge={conflictsAvoided > 0 ? 'PROTECTED' : '—'}
          badgeType="info"
        />
        <StatCard
          title="SOLVER STATUS"
          value={optimizationResult?.status || 'NOT RUN'}
          subtitle="Google OR-Tools CP-SAT"
          icon="⚡"
          accent="cyan"
          badge={optimizationResult?.status || 'IDLE'}
          badgeType={optimizationResult?.status === 'OPTIMAL' ? 'success' : 'info'}
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16 }}>
        {/* Conflicts Alert Section */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>⚠ Active Incident & Conflict Monitor</span>
                <span className={`badge ${conflicts.length > 0 ? 'badge-critical' : 'badge-low'}`}>
                  {conflicts.length} DETECTED
                </span>
              </div>
              <div className="panel-subtitle">Spatial-temporal headway violations requiring clearance</div>
            </div>
          </div>

          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 420, overflowY: 'auto' }}>
            {conflicts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 20px', color: '#10b981', fontSize: '0.85rem' }}>
                ✅ Zero conflicts detected on corridor sections for {targetDate}.
              </div>
            ) : (
              conflicts.slice(0, 5).map((c, idx) => (
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
              <div className="panel-subtitle">COA / TDMS corridor entry window forecasts with confidence scoring</div>
            </div>
          </div>

          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 420, overflowY: 'auto' }}>
            {forecasts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 20px', color: '#94a3b8', fontSize: '0.85rem' }}>
                No goods movement forecasts generated for {targetDate}.
              </div>
            ) : (
              forecasts.slice(0, 5).map((fc, idx) => (
                <ForecastCard key={fc.train_id + idx} forecast={fc} />
              ))
            )}
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
