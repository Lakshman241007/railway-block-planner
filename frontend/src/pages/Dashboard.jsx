import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import Timeline from '../components/Timeline';
import ConflictCard from '../components/ConflictCard';
import ForecastCard from '../components/ForecastCard';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { getCanonicalPossessions } from '../types';

export default function Dashboard({
  targetDate,
  optimizationResult,
  isOptimizing,
  onRunOptimization,
  blocks = [],
  maintenance = [],
  conflicts = [],
  forecasts = [],
  trains = [],
  onSelectBlock,
  loading = false,
  error = null,
  onRetry,
}) {
  const [dateScope, setDateScope] = useState('DATE'); // 'DATE' | 'HORIZON'

  const {
    possessions: displayBlocks,
    isOptimized,
    horizonTotal,
    dateTotal,
  } = getCanonicalPossessions({
    optimizationResult,
    blocks,
    targetDate,
    dateScope,
  });

  const stats = optimizationResult?.solver_statistics;

  // Compute date-accurate request telemetry
  const dateBlocks = blocks.filter((b) => (b.requested_date || b.service_date) === targetDate);
  const dateMaint = maintenance.filter((m) => (m.requested_date || m.service_date) === targetDate);
  const totalDateRequests = dateBlocks.length + dateMaint.length;
  const totalHorizonRequests = stats?.total_requests ?? (blocks.length + maintenance.length);

  const displayRequests = dateScope === 'DATE' ? totalDateRequests : totalHorizonRequests;
  const scheduledCount = dateScope === 'DATE' ? dateTotal : horizonTotal;
  const unscheduledCount = stats?.num_unscheduled ?? 0;
  const conflictsAvoided = stats?.num_conflicts_avoided ?? 0;

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
          value={displayRequests}
          subtitle={
            dateScope === 'DATE'
              ? `${dateBlocks.length} blocks + ${dateMaint.length} maint. (${targetDate})`
              : `${totalHorizonRequests} total across planning horizon`
          }
          icon="🚧"
          accent="cyan"
          badge={dateScope === 'DATE' ? targetDate : 'HORIZON'}
          badgeType="info"
        />
        <StatCard
          title="SCHEDULED POSSESSIONS"
          value={scheduledCount}
          subtitle={
            dateScope === 'DATE'
              ? `${dateTotal} for ${targetDate} (${horizonTotal} horizon total)`
              : `${horizonTotal} conflict-free assigned windows`
          }
          icon="✅"
          accent="green"
          badge={isOptimized ? 'OPTIMIZED' : 'CURRENT'}
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

      {/* Date Scope Filter Control & Live Corridor Timeline */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
        <div className="segmented-control">
          <button
            className={`segmented-tab ${dateScope === 'DATE' ? 'active' : ''}`}
            onClick={() => setDateScope('DATE')}
          >
            📅 Selected Date: {targetDate} ({dateTotal})
          </button>
          <button
            className={`segmented-tab ${dateScope === 'HORIZON' ? 'active' : ''}`}
            onClick={() => setDateScope('HORIZON')}
          >
            🌐 Full Horizon: 7-Day ({horizonTotal})
          </button>
        </div>
        <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
          {dateScope === 'DATE'
            ? `Displaying ${displayBlocks.length} possessions assigned specifically for ${targetDate}`
            : `Displaying all ${displayBlocks.length} possessions across the 7-day planning horizon`}
        </div>
      </div>

      {loading ? (
        <LoadingState message="Synchronizing corridor timetable & block possessions..." />
      ) : (
        <Timeline
          blocks={displayBlocks}
          targetDate={dateScope === 'DATE' ? targetDate : `${targetDate} (Horizon)`}
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
