import React, { useState } from 'react';
import StatCard from './StatCard';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';
import EmptyState from './EmptyState';

export default function OptimizationPanel({
  targetDate,
  onRunOptimization,
  onResetBaseline,
  isOptimizing,
  optimizationResult,
  optimizationStep = 0, // 0: idle, 1: building, 2: solving, 3: complete
  onSelectBlock,
}) {
  const [horizonDays, setHorizonDays] = useState(7);
  const [includeForecast, setIncludeForecast] = useState(true);
  const [bufferMinutes, setBufferMinutes] = useState(15);

  const handleRun = () => {
    if (onRunOptimization) {
      onRunOptimization({
        target_date: targetDate,
        horizon_days: parseInt(horizonDays, 10),
        include_forecast: includeForecast,
        buffer_minutes: parseInt(bufferMinutes, 10),
      });
    }
  };

  const stats = optimizationResult?.solver_statistics;
  const scheduledBlocks = optimizationResult?.scheduled_blocks || [];
  const unscheduledBlocks = optimizationResult?.unscheduled_blocks || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Optimization Control Bar */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>⚡ Google OR-Tools CP-SAT Mathematical Optimizer</span>
              <span className="badge badge-cyan">Phase 5</span>
            </div>
            <div className="panel-subtitle">
              Constraint programming solver with track mutual exclusion, headway buffers & resource capacity bounds
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            {onResetBaseline && (
              <button
                className="btn btn-secondary"
                onClick={onResetBaseline}
                disabled={isOptimizing}
                title="Reset database back to baseline unoptimized state"
              >
                🔄 Reset Baseline
              </button>
            )}
            <button
              className="btn btn-primary"
              onClick={handleRun}
              disabled={isOptimizing}
            >
              {isOptimizing ? '⚡ SOLVING CP-SAT...' : '⚡ RUN CP-SAT OPTIMIZATION'}
            </button>
          </div>
        </div>

        <div className="panel-body">
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="detail-item" style={{ minWidth: 160 }}>
              <label className="detail-label">Planning Horizon</label>
              <select
                className="select-control"
                value={horizonDays}
                onChange={(e) => setHorizonDays(e.target.value)}
                disabled={isOptimizing}
              >
                <option value="1">1 Day (Shift Plan)</option>
                <option value="3">3 Days (Rolling)</option>
                <option value="7">7 Days (Weekly Plan)</option>
                <option value="14">14 Days (Bi-Weekly)</option>
                <option value="30">30 Days (Monthly Plan)</option>
              </select>
            </div>

            <div className="detail-item" style={{ minWidth: 160 }}>
              <label className="detail-label">Safety Buffer (Min)</label>
              <select
                className="select-control"
                value={bufferMinutes}
                onChange={(e) => setBufferMinutes(e.target.value)}
                disabled={isOptimizing}
              >
                <option value="10">10 Minutes</option>
                <option value="15">15 Minutes (Standard)</option>
                <option value="20">20 Minutes (Heavy Corridor)</option>
                <option value="30">30 Minutes (Maximum)</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 32, paddingBottom: 4 }}>
              <input
                type="checkbox"
                id="forecast-check"
                checked={includeForecast}
                onChange={(e) => setIncludeForecast(e.target.checked)}
                disabled={isOptimizing}
                style={{ cursor: 'pointer', width: 15, height: 15 }}
              />
              <label htmlFor="forecast-check" style={{ fontSize: '0.78rem', color: '#cbd5e1', cursor: 'pointer' }}>
                Include Goods Train Forecast Headways
              </label>
            </div>
          </div>

          {/* Solver Progress Stepper */}
          {isOptimizing && (
            <div className="optimization-stepper" style={{ marginTop: 16 }}>
              <div className={`step-item ${optimizationStep >= 1 ? (optimizationStep === 1 ? 'active' : 'done') : ''}`}>
                <div className="step-icon-circle">1</div>
                <span>Building candidate possession windows from timetable & corridors...</span>
              </div>
              <div className={`step-item ${optimizationStep >= 2 ? (optimizationStep === 2 ? 'active' : 'done') : ''}`}>
                <div className="step-icon-circle">2</div>
                <span>Running CP-SAT solver (constraints: track exclusive possession, machine capacity, safety headways)...</span>
              </div>
              <div className={`step-item ${optimizationStep >= 3 ? 'done' : ''}`}>
                <div className="step-icon-circle">3</div>
                <span>Synthesizing optimal schedule and calculating disruption metrics...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Idle / Not Run State */}
      {!optimizationResult && !isOptimizing && (
        <div className="panel">
          <div className="panel-body">
            <EmptyState
              title="CP-SAT Optimization Not Run"
              message={`Mathematical solver has not been executed for ${targetDate}. Configure parameters above and click 'Run CP-SAT Optimization' to compute optimal non-overlapping possession windows.`}
              icon="⚡"
              actionLabel="⚡ RUN CP-SAT OPTIMIZATION"
              onAction={handleRun}
            />
          </div>
        </div>
      )}

      {/* Solver Metrics Summary */}
      {optimizationResult && (
        <div className="stat-grid">
          <StatCard
            title="SOLVER STATUS"
            value={optimizationResult.status || 'UNKNOWN'}
            subtitle={`Objective: ${stats?.objective_value != null ? stats.objective_value.toLocaleString() : '--'}`}
            icon="⚡"
            accent="cyan"
            badge={optimizationResult.status}
            badgeType={optimizationResult.status === 'OPTIMAL' ? 'success' : 'warning'}
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
            title="CONFLICTS AVOIDED"
            value={stats?.num_conflicts_avoided ?? 0}
            subtitle={
              stats?.conflicts_before != null && stats?.conflicts_after != null
                ? `Before: ${stats.conflicts_before} → After: ${stats.conflicts_after}`
                : 'Headway Collisions Resolved'
            }
            icon="🛡️"
            accent="amber"
            badge="PROTECTED"
            badgeType="info"
          />

          <StatCard
            title="SOLVE TIME"
            value={stats?.wall_time_seconds != null ? `${stats.wall_time_seconds.toFixed(3)}s` : '< 0.05s'}
            subtitle={`Vars: ${stats?.num_variables ?? 0} | Constraints: ${stats?.num_constraints ?? 0}`}
            icon="⏱️"
            accent="cyan"
            badge="OR-TOOLS"
            badgeType="info"
          />
        </div>
      )}

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
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Request ID</th>
                    <th>Location</th>
                    <th>Priority</th>
                    <th>Duration</th>
                    <th>Causal Diagnostic (Why was it not scheduled?)</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {unscheduledBlocks.map((u, idx) => (
                    <tr key={u.request_id || idx}>
                      <td className="table-cell-mono">{u.request_id}</td>
                      <td>{u.location}</td>
                      <td><PriorityBadge priority={u.priority} /></td>
                      <td className="table-cell-mono">{u.duration_minutes || '--'}m</td>
                      <td style={{ color: '#fca5a5', maxWidth: 420, whiteSpace: 'normal', fontSize: '0.75rem' }}>
                        {u.reason || 'Preempted by higher priority request or track possession collision.'}
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onSelectBlock && onSelectBlock(u)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Scheduled Possessions Table */}
      {scheduledBlocks.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>Optimized Possession Assignments ({scheduledBlocks.length})</span>
              </div>
              <div className="panel-subtitle">
                Conflict-free mathematical slot assignments satisfying all headway and capacity bounds
              </div>
            </div>
          </div>

          <div className="panel-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Block ID</th>
                    <th>Request ID</th>
                    <th>Location</th>
                    <th>Date</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Duration</th>
                    <th>Priority</th>
                    <th>Equipment</th>
                    <th>Fit Score</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {scheduledBlocks.map((b, idx) => (
                    <tr
                      key={b.block_id || idx}
                      className="clickable"
                      onClick={() => onSelectBlock && onSelectBlock(b)}
                    >
                      <td className="table-cell-mono" style={{ color: '#38bdf8', fontWeight: 700 }}>
                        {b.block_id}
                      </td>
                      <td className="table-cell-mono">{b.block_request_id || b.request_id}</td>
                      <td className="table-cell-highlight">{b.location}</td>
                      <td className="table-cell-mono">{b.service_date}</td>
                      <td className="table-cell-mono" style={{ color: '#34d399' }}>{b.start_time}</td>
                      <td className="table-cell-mono" style={{ color: '#34d399' }}>{b.end_time}</td>
                      <td className="table-cell-mono">{b.duration_minutes}m</td>
                      <td><PriorityBadge priority={b.priority} /></td>
                      <td>{b.equipment || 'Standard Gang'}</td>
                      <td>
                        <span className="badge badge-cyan">
                          {b.fit_score != null ? `${(b.fit_score * 100).toFixed(0)}%` : '100%'}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-secondary btn-sm">Inspect</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
