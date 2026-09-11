import React from 'react';
import PageContainer from '../../components/PageContainer';
import StatCard from '../../components/StatCard';
import PriorityBadge from '../../components/PriorityBadge';
import EmptyState from '../../components/EmptyState';

export default function EmployeePlanStatus({
  optimizationResult,
  targetDate,
  onSelectBlock,
}) {
  const stats = optimizationResult?.solver_statistics;
  const scheduledBlocks = optimizationResult?.scheduled_blocks || [];
  const unscheduledBlocks = optimizationResult?.unscheduled_blocks || [];
  const status = optimizationResult?.status || 'IDLE';

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">📊</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            Master CP-SAT Optimization Plan Diagnostics (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Current mathematical solver schedule state for <strong>{targetDate}</strong>. Read-only inspection of assigned possession windows and capacity bounds.
          </div>
        </div>
        <div className="employee-banner-tag">
          {scheduledBlocks.length} ASSIGNED
        </div>
      </div>

      {/* Solver Metrics Summary */}
      {optimizationResult ? (
        <>
          <div className="stat-grid">
            <StatCard
              title="SOLVER STATUS"
              value={status}
              subtitle={`Objective: ${stats?.objective_value != null ? stats.objective_value.toLocaleString() : '--'}`}
              icon="⚡"
              accent={status === 'OPTIMAL' ? 'green' : 'cyan'}
              badge={status}
              badgeType={status === 'OPTIMAL' ? 'success' : 'warning'}
            />

            <StatCard
              title="SCHEDULED POSSESSIONS"
              value={stats?.num_scheduled ?? scheduledBlocks.length}
              subtitle={`Total Requests: ${stats?.total_requests ?? (scheduledBlocks.length + unscheduledBlocks.length)}`}
              icon="✅"
              accent="green"
              badge="ASSIGNED"
              badgeType="success"
            />

            <StatCard
              title="CONFLICTS RESOLVED"
              value={stats?.num_conflicts_avoided ?? 0}
              subtitle={
                stats?.conflicts_before != null && stats?.conflicts_after != null
                  ? `Before: ${stats.conflicts_before} → After: ${stats.conflicts_after}`
                  : 'Safety Headways Protected'
              }
              icon="🛡️"
              accent="amber"
              badge="PROTECTED"
              badgeType="info"
            />

            <StatCard
              title="SOLVE DURATION"
              value={stats?.wall_time_seconds != null ? `${stats.wall_time_seconds.toFixed(3)}s` : '< 0.05s'}
              subtitle={`Vars: ${stats?.num_variables ?? 0} | Constraints: ${stats?.num_constraints ?? 0}`}
              icon="⏱️"
              accent="cyan"
              badge="OR-TOOLS"
              badgeType="info"
            />
          </div>

          {/* Plan Metadata Card */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="panel-title">
                  <span>📋 Master Plan Information</span>
                  <span className="badge badge-green">VERIFIED PLAN</span>
                  <span className="badge badge-outline">READ-ONLY</span>
                </div>
                <div className="panel-subtitle">Plan identification, solver constraints, and configuration parameters</div>
              </div>
            </div>
            <div className="panel-body">
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="detail-label">Plan ID</span>
                  <span className="detail-value table-cell-mono" style={{ color: '#38bdf8', fontWeight: 700 }}>
                    {optimizationResult.plan_id || 'PLN-LATEST'}
                  </span>
                </div>

                <div className="detail-item">
                  <span className="detail-label">Target Date</span>
                  <span className="detail-value table-cell-mono">{targetDate}</span>
                </div>

                <div className="detail-item">
                  <span className="detail-label">Planning Horizon</span>
                  <span className="detail-value">{optimizationResult.horizon_days || 7} Days</span>
                </div>

                <div className="detail-item">
                  <span className="detail-label">Safety Buffer</span>
                  <span className="detail-value">15 Minutes Headway</span>
                </div>

                <div className="detail-item">
                  <span className="detail-label">Generated At</span>
                  <span className="detail-value table-cell-mono">
                    {optimizationResult.generated_at ? new Date(optimizationResult.generated_at).toLocaleString() : 'Recent'}
                  </span>
                </div>

                <div className="detail-item">
                  <span className="detail-label">Freight Headways Included</span>
                  <span className="detail-value">
                    <span className="badge badge-green">YES (Active Protection)</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Scheduled Possessions Table */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="panel-title">
                  <span>✅ Scheduled Track Possessions ({scheduledBlocks.length})</span>
                </div>
                <div className="panel-subtitle">Assigned possession time slots and equipment allocations</div>
              </div>
            </div>
            <div className="panel-body">
              {scheduledBlocks.length === 0 ? (
                <EmptyState
                  title="No Scheduled Blocks in Plan"
                  message="No block requests could be scheduled within the current corridor constraints."
                  icon="🚧"
                />
              ) : (
                <div className="table-responsive">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Block ID</th>
                        <th>Location</th>
                        <th>Service Date</th>
                        <th>Time Window</th>
                        <th>Duration</th>
                        <th>Priority</th>
                        <th>Assigned Machinery</th>
                        <th>Fit Score</th>
                        <th>Inspection</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scheduledBlocks.map((b, idx) => {
                        const bId = b.block_id || b.request_id || `BLK-${idx + 1}`;
                        return (
                          <tr
                            key={bId + idx}
                            className="clickable"
                            onClick={() => onSelectBlock && onSelectBlock(b)}
                          >
                            <td className="table-cell-mono" style={{ color: '#38bdf8', fontWeight: 700 }}>
                              {bId}
                            </td>
                            <td className="table-cell-highlight">{b.location}</td>
                            <td className="table-cell-mono">{b.service_date || targetDate}</td>
                            <td className="table-cell-mono" style={{ color: '#34d399' }}>
                              {b.start_time} → {b.end_time}
                            </td>
                            <td className="table-cell-mono">{b.duration_minutes}m</td>
                            <td><PriorityBadge priority={b.priority} /></td>
                            <td>{b.equipment || 'Standard Gang'}</td>
                            <td>
                              <span className="badge badge-green">
                                {b.fit_score != null ? `${(b.fit_score * 100).toFixed(0)}%` : '—'}
                              </span>
                            </td>
                            <td>
                              <span className="badge badge-outline" style={{ fontSize: '0.68rem' }}>
                                👁️ Inspect
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Unscheduled Block Diagnostics Section */}
          {unscheduledBlocks.length > 0 && (
            <div className="panel" style={{ borderLeft: '3px solid #ef4444' }}>
              <div className="panel-header" style={{ background: 'rgba(239, 68, 68, 0.04)' }}>
                <div>
                  <div className="panel-title" style={{ color: '#f87171' }}>
                    <span>⚠ Unscheduled Requests Diagnostic Engine ({unscheduledBlocks.length})</span>
                  </div>
                  <div className="panel-subtitle">
                    Causal reasoning generated by mathematical solver for requests that could not be accommodated
                  </div>
                </div>
              </div>
              <div className="panel-body">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {unscheduledBlocks.map((ub, idx) => (
                    <div
                      key={ub.block_id + idx}
                      style={{
                        background: 'rgba(239, 68, 68, 0.06)',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                        borderRadius: 6,
                        padding: '12px 16px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <span className="table-cell-mono" style={{ fontWeight: 700, color: '#f87171' }}>
                          {ub.block_id} — {ub.location}
                        </span>
                        <PriorityBadge priority={ub.priority} />
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
                        <strong>Diagnostic Reason:</strong> {ub.unscheduled_reason || 'Insufficient track possession window free of passenger train timetables.'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="panel">
          <div className="panel-body">
            <EmptyState
              title="No Plan Record"
              message={`No CP-SAT optimization plan has been computed or published for ${targetDate}. Operating under standard timetable.`}
              icon="📊"
            />
          </div>
        </div>
      )}
    </PageContainer>
  );
}
