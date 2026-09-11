import React from 'react';
import PageContainer from '../../components/PageContainer';
import StatCard from '../../components/StatCard';
import Timeline from '../../components/Timeline';
import ConflictCard from '../../components/ConflictCard';
import ForecastCard from '../../components/ForecastCard';
import PriorityBadge from '../../components/PriorityBadge';
import StatusBadge from '../../components/StatusBadge';
import EmptyState from '../../components/EmptyState';
import { getCanonicalPossessions } from '../../types';

export default function EmployeeDashboard({
  blocks = [],
  timetable = [],
  conflicts = [],
  forecasts = [],
  trains = [],
  maintenanceRecords = [],
  optimizationResult,
  targetDate,
  onSelectBlock,
  onNavigate,
}) {
  const { possessions: displayBlocks } = getCanonicalPossessions({
    optimizationResult,
    blocks,
    targetDate,
    dateScope: 'DATE',
    priorityFilter: 'ALL',
  });

  const scheduledCount = blocks.filter((b) => (b.status || '').toLowerCase() === 'scheduled' || (b.status || '').toLowerCase() === 'approved').length;
  const activeMaintenance = maintenanceRecords.filter((m) => (m.status || '').toLowerCase() !== 'completed' && (m.status || '').toLowerCase() !== 'cancelled');
  const criticalConflicts = conflicts.filter((c) => String(c.severity || '').toLowerCase() === 'critical').length;
  const solverStats = optimizationResult?.solver_statistics;
  const optimizationStatus = optimizationResult?.status || 'IDLE';

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">👁️</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            Railway Operations Live Monitoring Portal
          </div>
          <div className="employee-banner-subtitle">
            Situational awareness feed for <strong>{targetDate}</strong>. All data streams are synchronized directly with divisional dispatch. Read-only permissions active.
          </div>
        </div>
        <div className="employee-banner-tag">
          LIVE FEED
        </div>
      </div>

      {/* Top 6 Information Cards as specified for Employee */}
      <div className="stat-grid stat-grid-6">
        <StatCard
          title="TODAY'S ACTIVE BLOCKS"
          value={displayBlocks.length}
          subtitle={`Possessions on ${targetDate}`}
          icon="🚧"
          accent="cyan"
          badge="MONITORED"
          badgeType="info"
        />

        <StatCard
          title="SCHEDULED BLOCKS"
          value={scheduledCount}
          subtitle="Confirmed in BDMS"
          icon="✅"
          accent="green"
          badge="AUTHORIZED"
          badgeType="success"
        />

        <StatCard
          title="ACTIVE MAINTENANCE"
          value={activeMaintenance.length}
          subtitle="Work Orders in Progress"
          icon="🛠"
          accent="amber"
          badge="CREW DEPLOYED"
          badgeType="warning"
        />

        <StatCard
          title="TRAINS IN OPERATION"
          value={trains.length}
          subtitle="Passenger & Freight"
          icon="🚆"
          accent="cyan"
          badge="CORRIDOR"
          badgeType="info"
        />

        <StatCard
          title="UPCOMING BLOCKS"
          value={blocks.length}
          subtitle="BDMS Schedule Roster"
          icon="⏱️"
          accent="green"
          badge="ROSTER"
          badgeType="success"
        />

        <StatCard
          title="CURRENT CONFLICTS"
          value={conflicts.length}
          subtitle={criticalConflicts > 0 ? `${criticalConflicts} Critical Overlaps` : "Safety Clear"}
          icon="⚠"
          accent={conflicts.length > 0 ? (criticalConflicts > 0 ? "red" : "amber") : "green"}
          badge={conflicts.length > 0 ? "ATTENTION" : "NORMAL"}
          badgeType={conflicts.length > 0 ? "critical" : "success"}
        />
      </div>

      {/* 1. Today's Operational Schedule (Read-Only Timeline & Table) */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📅 Today's Operational Possession Schedule</span>
              <span className="badge badge-green">{displayBlocks.length} ACTIVE WINDOWS</span>
              <span className="badge badge-outline">READ-ONLY MONITORING</span>
            </div>
            <div className="panel-subtitle">
              Official maintenance track possessions scheduled for {targetDate}. Click any item to inspect full operational details.
            </div>
          </div>
          {onNavigate && (
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('schedule')}>
              Full Schedule View →
            </button>
          )}
        </div>
        <div className="panel-body">
          {displayBlocks.length === 0 ? (
            <EmptyState
              title="No Possessions Scheduled Today"
              message={`There are no maintenance blocks scheduled for ${targetDate}.`}
              icon="🚧"
            />
          ) : (
            <>
              {/* Lane-packed Gantt Timeline */}
              <Timeline
                blocks={displayBlocks}
                targetDate={targetDate}
                onSelectBlock={onSelectBlock}
              />

              <div style={{ marginTop: 20 }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
                  Possession Roster Breakdown (Click to Inspect)
                </div>
                <div className="table-responsive">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Block ID</th>
                        <th>Location</th>
                        <th>Track</th>
                        <th>Start Time</th>
                        <th>End Time</th>
                        <th>Duration</th>
                        <th>Priority</th>
                        <th>Status</th>
                        <th>Assigned Machinery</th>
                        <th>Inspection</th>
                      </tr>
                    </thead>
                    <tbody>
                      {displayBlocks.slice(0, 8).map((b, idx) => {
                        const bId = b.block_id || b.request_id || `BLK-${idx + 1}`;
                        const isOvernight = b.start_time && b.end_time && b.end_time < b.start_time;
                        return (
                          <tr
                            key={bId + idx}
                            className="clickable"
                            onClick={() => onSelectBlock && onSelectBlock(b)}
                          >
                            <td className="table-cell-mono" style={{ color: '#34d399', fontWeight: 700 }}>
                              {bId} {isOvernight ? '🌙' : ''}
                            </td>
                            <td className="table-cell-highlight">{b.location}</td>
                            <td className="table-cell-mono">{b.track_number || 'Main Line'}</td>
                            <td className="table-cell-mono" style={{ color: '#34d399' }}>
                              {b.start_time || b.requested_start}
                            </td>
                            <td className="table-cell-mono" style={{ color: '#34d399' }}>
                              {b.end_time || b.requested_end}
                            </td>
                            <td className="table-cell-mono">{b.duration_minutes || b.required_duration}m</td>
                            <td><PriorityBadge priority={b.priority} /></td>
                            <td><StatusBadge status={b.status || 'Scheduled'} /></td>
                            <td>{b.equipment || 'Standard Gang'}</td>
                            <td>
                              <span className="badge badge-outline" style={{ fontSize: '0.68rem' }}>
                                👁️ View
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Two Column Grid: Train Traffic & Maintenance Status */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: 20 }}>
        {/* 2. Train Traffic */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>🚦 Corridor Train Traffic (Read-Only)</span>
                <span className="badge badge-cyan">{trains.length} TRAINS</span>
              </div>
              <div className="panel-subtitle">Live timetable schedules and active corridor section occupancies</div>
            </div>
            {onNavigate && (
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('trains')}>
                View All Trains →
              </button>
            )}
          </div>
          <div className="panel-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Train</th>
                    <th>Route</th>
                    <th>Departure</th>
                    <th>Type</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {trains.slice(0, 5).map((t, idx) => (
                    <tr key={t.train_id + idx}>
                      <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>{t.train_id}</td>
                      <td className="table-cell-highlight">{t.origin} → {t.destination}</td>
                      <td className="table-cell-mono" style={{ color: '#34d399' }}>{t.departure_time || '--:--'}</td>
                      <td>
                        <span className={`badge ${String(t.train_type || '').toLowerCase().includes('goods') ? 'badge-warning' : 'badge-cyan'}`}>
                          {t.train_type || 'Passenger'}
                        </span>
                      </td>
                      <td><span className="badge badge-green">ON SCHEDULE</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 3. Maintenance Status */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>🛠 Scheduled Maintenance Work Orders</span>
                <span className="badge badge-amber">{maintenanceRecords.length} ORDERS</span>
              </div>
              <div className="panel-subtitle">SMMS track maintenance and gang deployments for {targetDate}</div>
            </div>
            {onNavigate && (
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('maintenance')}>
                View All Orders →
              </button>
            )}
          </div>
          <div className="panel-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Asset ID</th>
                    <th>Work Type</th>
                    <th>Location</th>
                    <th>Window</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {maintenanceRecords.slice(0, 5).map((m, idx) => (
                    <tr key={(m.asset_id || 'M') + idx}>
                      <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>{m.asset_id}</td>
                      <td>{m.maintenance_type || 'Preventive'}</td>
                      <td className="table-cell-highlight">{m.location}</td>
                      <td className="table-cell-mono" style={{ color: '#34d399' }}>
                        {m.preferred_start || '09:00'} ({m.duration_minutes || 120}m)
                      </td>
                      <td><StatusBadge status={m.status || 'Pending'} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Grid: Current Conflicts & Goods Freight Forecast */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: 20 }}>
        {/* 4. Current Conflicts (Read-Only Inspection) */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>⚠ Current Operational Conflicts</span>
                <span className={`badge ${conflicts.length > 0 ? 'badge-critical' : 'badge-green'}`}>
                  {conflicts.length} DETECTED
                </span>
              </div>
              <div className="panel-subtitle">
                Automated detection of train overlaps & safety buffer violations (Inspection Only)
              </div>
            </div>
            {onNavigate && (
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('conflicts')}>
                Conflict Report →
              </button>
            )}
          </div>
          <div className="panel-body">
            {conflicts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '32px 16px', color: '#10b981' }}>
                <div style={{ fontSize: '1.8rem', marginBottom: 6 }}>🛡️</div>
                <div style={{ fontWeight: 700, fontSize: '0.92rem', color: '#fff' }}>No Active Conflicts Detected</div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 4 }}>
                  All scheduled train movements and maintenance possessions have confirmed safety headways for {targetDate}.
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {conflicts.slice(0, 2).map((conflict, idx) => (
                  <ConflictCard key={conflict.conflict_id || idx} conflict={conflict} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 5. Goods Train Forecast (Read-Only - Strictly NO Run Button) */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>📈 Goods Train Movement Forecast</span>
                <span className="badge badge-amber">{forecasts.length} PREDICTIONS</span>
                <span className="badge badge-outline">READ-ONLY</span>
              </div>
              <div className="panel-subtitle">
                Freight transit window telemetry published by Divisional Dispatch for {targetDate}
              </div>
            </div>
            {onNavigate && (
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('forecast')}>
                Freight Forecast View →
              </button>
            )}
          </div>
          <div className="panel-body">
            {forecasts.length === 0 ? (
              <EmptyState
                icon="📦"
                title="No Goods Forecast Available"
                message={`No goods train movements forecasted for ${targetDate}. Check back when dispatch updates the feed.`}
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {forecasts.slice(0, 2).map((fc, idx) => (
                  <ForecastCard key={fc.train_id + idx} forecast={fc} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 6. Plan / Optimization Status (Read-Only - Strictly NO Run Button) */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📊 Master Plan & Optimization Status</span>
              <span className={`badge ${optimizationStatus === 'OPTIMAL' ? 'badge-green' : 'badge-cyan'}`}>
                {optimizationStatus}
              </span>
              <span className="badge badge-outline">LATEST DISPATCH PLAN</span>
            </div>
            <div className="panel-subtitle">
              Current mathematical solver schedule state published for {targetDate}
            </div>
          </div>
          {onNavigate && (
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('plan-status')}>
              Full Plan Diagnostics →
            </button>
          )}
        </div>
        <div className="panel-body">
          {optimizationResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                <div className="kpi-mini-card">
                  <span className="kpi-mini-label">Plan Identifier</span>
                  <span className="kpi-mini-value table-cell-mono" style={{ color: '#38bdf8', fontSize: '0.95rem' }}>
                    {optimizationResult.plan_id || 'PLN-LATEST'}
                  </span>
                </div>
                <div className="kpi-mini-card">
                  <span className="kpi-mini-label">Solver Status</span>
                  <span className="kpi-mini-value" style={{ color: '#34d399' }}>
                    {optimizationResult.status || 'COMPLETED'}
                  </span>
                </div>
                <div className="kpi-mini-card">
                  <span className="kpi-mini-label">Scheduled Blocks</span>
                  <span className="kpi-mini-value" style={{ color: '#34d399' }}>
                    {solverStats?.num_scheduled ?? (optimizationResult.scheduled_blocks || []).length}
                  </span>
                </div>
                <div className="kpi-mini-card">
                  <span className="kpi-mini-label">Unscheduled Requests</span>
                  <span className="kpi-mini-value" style={{ color: (optimizationResult.unscheduled_blocks || []).length > 0 ? '#f87171' : '#94a3b8' }}>
                    {(optimizationResult.unscheduled_blocks || []).length}
                  </span>
                </div>
                <div className="kpi-mini-card">
                  <span className="kpi-mini-label">Planning Horizon</span>
                  <span className="kpi-mini-value" style={{ color: '#cbd5e1' }}>
                    {optimizationResult.horizon_days || 7} Days
                  </span>
                </div>
                <div className="kpi-mini-card">
                  <span className="kpi-mini-label">Collisions Avoided</span>
                  <span className="kpi-mini-value" style={{ color: '#38bdf8' }}>
                    {solverStats?.num_conflicts_avoided ?? 0}
                  </span>
                </div>
              </div>

              <div style={{ padding: 12, borderRadius: 6, background: 'rgba(15, 23, 42, 0.5)', border: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                  ℹ️ This plan was generated by the Chief Controller via Google OR-Tools CP-SAT. All timings are synchronized.
                </span>
                <span className="badge badge-green">VERIFIED DISPATCH</span>
              </div>
            </div>
          ) : (
            <EmptyState
              icon="📊"
              title="No Plan Record"
              message={`No CP-SAT optimization plan has been published for ${targetDate}. Operating under standard timetable.`}
            />
          )}
        </div>
      </div>
    </PageContainer>
  );
}
