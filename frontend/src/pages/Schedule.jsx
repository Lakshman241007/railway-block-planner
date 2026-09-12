import React, { useState, useCallback } from 'react';
import PageContainer from '../components/PageContainer';
import Timeline from '../components/Timeline';
import PriorityBadge from '../components/PriorityBadge';
import StatusBadge from '../components/StatusBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { getCanonicalPossessions, ScheduleType } from '../types';
import { generateSchedule } from '../services/scheduler';

/** Human-readable labels and descriptions for each schedule type. */
const SCHEDULE_TYPE_META = {
  [ScheduleType.DAILY]: {
    label: 'Daily',
    icon: '📅',
    description: 'Plan for the selected day.',
  },
  [ScheduleType.WEEKLY]: {
    label: 'Weekly',
    icon: '🗓️',
    description: 'Plan across 7 days starting from the selected date.',
  },
  [ScheduleType.MONTHLY]: {
    label: 'Monthly',
    icon: '📆',
    description: 'Plan from the selected date through the end of the month.',
  },
};

export default function Schedule({
  blocks = [],
  timetable = [],
  optimizationResult,
  targetDate,
  onSelectBlock,
  loading = false,
  error = null,
  onRetry,
}) {
  const [activeTab, setActiveTab] = useState('possession'); // 'possession' | 'timetable'
  const [dateScope, setDateScope] = useState('DATE'); // 'DATE' | 'HORIZON'
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [timetableSearch, setTimetableSearch] = useState('');

  // Schedule-type selector state
  const [scheduleType, setScheduleType] = useState(ScheduleType.DAILY);
  const [scheduleResult, setScheduleResult] = useState(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleError, setScheduleError] = useState(null);

  /** Flatten a ScheduleResult into displayable block-like rows. */
  const flattenScheduleItems = (result) => {
    if (!result) return [];
    const rows = [];
    for (const item of result.scheduled_items || []) {
      if (item.assigned_slot) {
        rows.push({
          block_id: item.block_id || item.asset_id || item.schedule_id,
          location: item.location,
          service_date: item.assigned_slot.service_date,
          start_time: item.assigned_slot.start_time,
          end_time: item.assigned_slot.end_time,
          duration_minutes: item.assigned_slot.duration_minutes,
          fit_score: item.assigned_slot.fit_score,
          priority: item.priority,
          status: item.status,
          notes: item.notes,
        });
      }
    }
    return rows;
  };

  const handleRunSchedule = useCallback(async (type) => {
    setScheduleType(type);
    setScheduleLoading(true);
    setScheduleError(null);
    setScheduleResult(null);
    try {
      const result = await generateSchedule({
        target_date: targetDate || null,
        schedule_type: type,
      });
      setScheduleResult(result);
    } catch (err) {
      setScheduleError(err?.message || 'Scheduling request failed. Check API connectivity.');
    } finally {
      setScheduleLoading(false);
    }
  }, [targetDate]);

  // When a schedule result exists, use its items as the possession display source
  const scheduledRows = flattenScheduleItems(scheduleResult);
  const hasScheduleResult = scheduleResult !== null;

  const {
    possessions: displayBlocks,
    isOptimized,
    horizonTotal,
    dateTotal,
  } = getCanonicalPossessions({
    optimizationResult: hasScheduleResult ? null : optimizationResult,
    blocks: hasScheduleResult ? scheduledRows : blocks,
    targetDate,
    dateScope: hasScheduleResult ? 'HORIZON' : dateScope,
    priorityFilter,
  });

  const filteredTimetable = timetable.filter((tt) => {
    if (!timetableSearch) return true;
    return (tt.train_id && tt.train_id.toLowerCase().includes(timetableSearch.toLowerCase())) ||
           (tt.station_code && tt.station_code.toLowerCase().includes(timetableSearch.toLowerCase()));
  });

  const horizonLabel = {
    [ScheduleType.DAILY]: targetDate,
    [ScheduleType.WEEKLY]: '7-DAY HORIZON',
    [ScheduleType.MONTHLY]: 'MONTHLY HORIZON',
  }[scheduleType] || targetDate;

  return (
    <PageContainer>
      {/* ── Schedule Type Selector ────────────────────────────────── */}
      <div className="panel" style={{ marginBottom: 0 }}>
        <div className="panel-header" style={{ paddingBottom: 12 }}>
          <div>
            <div className="panel-title">🗂️ Schedule Planning Horizon</div>
            <div className="panel-subtitle">
              Select a scheduling mode, then generate to see conflict-free maintenance slots.
            </div>
          </div>
        </div>
        <div className="panel-body" style={{ paddingTop: 4 }}>
          {/* Mode selector buttons */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
            {Object.values(ScheduleType).map((type) => {
              const meta = SCHEDULE_TYPE_META[type];
              const isActive = scheduleType === type;
              return (
                <button
                  key={type}
                  id={`schedule-type-${type}`}
                  className={`segmented-tab${isActive ? ' active' : ''}`}
                  onClick={() => setScheduleType(type)}
                  title={meta.description}
                  style={{ minWidth: 110 }}
                >
                  {meta.icon} {meta.label}
                </button>
              );
            })}

            <button
              id="btn-generate-schedule"
              className="btn btn-primary"
              onClick={() => handleRunSchedule(scheduleType)}
              disabled={scheduleLoading}
              style={{ marginLeft: 'auto' }}
            >
              {scheduleLoading ? '⏳ Generating…' : '▶ Generate Schedule'}
            </button>
          </div>

          {/* Horizon description */}
          <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>
            <strong style={{ color: '#cbd5e1' }}>
              {SCHEDULE_TYPE_META[scheduleType].icon} {SCHEDULE_TYPE_META[scheduleType].label}:
            </strong>{' '}
            {SCHEDULE_TYPE_META[scheduleType].description}
          </div>

          {/* Schedule result summary */}
          {scheduleResult && !scheduleLoading && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <span className="badge badge-cyan">
                {scheduleResult.total_scheduled} SCHEDULED
              </span>
              <span className="badge badge-critical">
                {scheduleResult.total_unfeasible} UNFEASIBLE
              </span>
              <span className="badge badge-outline">
                {scheduleResult.total_requested} TOTAL REQUESTS
              </span>
              <span className="badge badge-outline" style={{ color: '#94a3b8' }}>
                Generated {scheduleResult.generated_at?.slice(0, 16).replace('T', ' ')} UTC
              </span>
            </div>
          )}

          {/* Schedule-level error */}
          {scheduleError && !scheduleLoading && (
            <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6, background: 'rgba(239,68,68,0.1)', color: '#f87171', fontSize: 13 }}>
              ⚠️ {scheduleError}
              <button
                style={{ marginLeft: 12, textDecoration: 'underline', background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: 13 }}
                onClick={() => handleRunSchedule(scheduleType)}
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Main Schedule View ────────────────────────────────────── */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📅 Master Operational & Possession Schedule</span>
              <span className="badge badge-cyan">
                {displayBlocks.length} POSSESSIONS ({horizonLabel})
              </span>
              {!hasScheduleResult && dateScope === 'DATE' && horizonTotal > displayBlocks.length && (
                <span className="badge badge-outline" title={`Full optimization horizon: ${horizonTotal} blocks across all dates`}>
                  {horizonTotal} TOTAL HORIZON
                </span>
              )}
              <span className="badge badge-outline">{timetable.length} TIMETABLE STOPS</span>
            </div>
            <div className="panel-subtitle">
              Gantt timeline mapping maintenance possessions and scheduled train stops for{' '}
              {hasScheduleResult
                ? `${scheduleType} horizon starting ${targetDate}`
                : targetDate}
            </div>
          </div>

          <div className="segmented-control">
            <button
              className={`segmented-tab ${activeTab === 'possession' ? 'active' : ''}`}
              onClick={() => setActiveTab('possession')}
            >
              🚧 Possession Schedule ({displayBlocks.length})
            </button>
            <button
              className={`segmented-tab ${activeTab === 'timetable' ? 'active' : ''}`}
              onClick={() => setActiveTab('timetable')}
            >
              🚆 Train Timetable ({timetable.length})
            </button>
          </div>
        </div>

        <div className="panel-body">
          {error ? (
            <ErrorState
              title="Failed to Load Schedule"
              message={error}
              onRetry={onRetry}
            />
          ) : loading || scheduleLoading ? (
            <LoadingState message={scheduleLoading ? `Generating ${scheduleType} schedule…` : 'Generating schedule projection...'} />
          ) : activeTab === 'possession' ? (
            <>
              {/* Filter toolbar — only shown when not using a schedule result */}
              {!hasScheduleResult && (
                <div className="filter-toolbar">
                  <div className="filter-group">
                    <select
                      className="select-control"
                      value={dateScope}
                      onChange={(e) => setDateScope(e.target.value)}
                      title="Toggle between single-day service date possessions and multi-day horizon"
                    >
                      <option value="DATE">📅 Selected Date: {targetDate} ({dateTotal})</option>
                      <option value="HORIZON">🌐 Entire Planning Horizon ({horizonTotal})</option>
                    </select>

                    <select
                      className="select-control"
                      value={priorityFilter}
                      onChange={(e) => setPriorityFilter(e.target.value)}
                    >
                      <option value="ALL">All Priorities</option>
                      <option value="Critical">Critical Priority</option>
                      <option value="High">High Priority</option>
                      <option value="Medium">Medium Priority</option>
                      <option value="Low">Low Priority</option>
                    </select>
                  </div>

                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <span className="badge badge-outline">
                      Showing: {displayBlocks.length} {dateScope === 'DATE' ? `for ${targetDate}` : 'across horizon'}
                    </span>
                    {dateScope === 'DATE' && horizonTotal > displayBlocks.length && (
                      <span className="badge badge-outline" style={{ color: '#94a3b8' }}>
                        Horizon total: {horizonTotal}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* When a schedule result is active, show a priority filter only */}
              {hasScheduleResult && (
                <div className="filter-toolbar">
                  <div className="filter-group">
                    <select
                      className="select-control"
                      value={priorityFilter}
                      onChange={(e) => setPriorityFilter(e.target.value)}
                    >
                      <option value="ALL">All Priorities</option>
                      <option value="Critical">Critical Priority</option>
                      <option value="High">High Priority</option>
                      <option value="Medium">Medium Priority</option>
                      <option value="Low">Low Priority</option>
                    </select>
                  </div>
                  <span className="badge badge-outline" style={{ color: '#94a3b8' }}>
                    {SCHEDULE_TYPE_META[scheduleType].icon} {scheduleType} horizon · {displayBlocks.length} possessions shown
                  </span>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: 12, padding: '4px 10px' }}
                    onClick={() => { setScheduleResult(null); setScheduleError(null); }}
                  >
                    ✕ Clear Schedule Result
                  </button>
                </div>
              )}

              {/* Lane-packed visual timeline */}
              <Timeline
                blocks={displayBlocks}
                targetDate={
                  hasScheduleResult
                    ? `${targetDate} (${SCHEDULE_TYPE_META[scheduleType].label} Horizon)`
                    : dateScope === 'DATE' ? targetDate : `${targetDate} (Horizon)`
                }
                onSelectBlock={onSelectBlock}
              />
            </>
          ) : (
            /* Timetable Stops View */
            <div>
              <div className="filter-toolbar">
                <div className="search-input-wrap">
                  <span className="search-icon">🔍</span>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search Train ID or Station Code (e.g. G123, AJJ, KPD)..."
                    value={timetableSearch}
                    onChange={(e) => setTimetableSearch(e.target.value)}
                  />
                </div>
                <span className="badge badge-outline">
                  Showing {filteredTimetable.length} stops for {targetDate}
                </span>
              </div>

              <div className="table-responsive">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Train ID</th>
                      <th>Service Date</th>
                      <th>Station Code</th>
                      <th>Sequence</th>
                      <th>Arrival Time</th>
                      <th>Departure Time</th>
                      <th>Platform</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTimetable.length === 0 ? (
                      <tr>
                        <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                          No timetable stops found for {targetDate}.
                        </td>
                      </tr>
                    ) : (
                      filteredTimetable.map((tt, idx) => (
                        <tr key={(tt.train_id || 'TT') + idx}>
                          <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                            {tt.train_id}
                          </td>
                          <td className="table-cell-mono">{tt.service_date}</td>
                          <td className="table-cell-highlight">{tt.station_code}</td>
                          <td className="table-cell-mono">#{tt.sequence}</td>
                          <td className="table-cell-mono" style={{ color: tt.arrival_time ? '#34d399' : '#94a3b8' }}>
                            {tt.arrival_time || 'Origin'}
                          </td>
                          <td className="table-cell-mono" style={{ color: tt.departure_time ? '#34d399' : '#94a3b8' }}>
                            {tt.departure_time || 'Terminus'}
                          </td>
                          <td className="table-cell-mono">
                            {tt.platform ? `PF ${tt.platform}` : '—'}
                          </td>
                          <td>
                            <span className="badge badge-outline">{tt.source || 'timetable'}</span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Possession Slot Breakdown Table ───────────────────────── */}
      {activeTab === 'possession' && !error && !(loading || scheduleLoading) && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">Possession Slot Breakdown</div>
              <div className="panel-subtitle">
                {hasScheduleResult
                  ? `${SCHEDULE_TYPE_META[scheduleType].label} schedule — assigned possession time windows`
                  : 'Assigned possession time windows and required gang resources'}
              </div>
            </div>
          </div>
          <div className="panel-body">
            {displayBlocks.length === 0 ? (
              <EmptyState
                title="No Possessions Scheduled"
                message={
                  hasScheduleResult
                    ? `No feasible maintenance windows found for the ${scheduleType} horizon starting ${targetDate}.`
                    : `No block possessions scheduled for ${targetDate}. Run CP-SAT optimization or adjust filters.`
                }
                icon="🚧"
              />
            ) : (
              <div className="table-responsive">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Block ID</th>
                      <th>Location</th>
                      <th>Date</th>
                      <th>Start Time</th>
                      <th>End Time</th>
                      <th>Duration</th>
                      <th>Priority</th>
                      <th>Equipment Required</th>
                      <th>Fit Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayBlocks.map((b, idx) => {
                      const bId = b.block_id || b.request_id || `BLK-${idx + 1}`;
                      const isOvernight = (b.start_time && b.end_time && b.end_time < b.start_time);

                      return (
                        <tr
                          key={bId + idx}
                          className="clickable"
                          onClick={() => onSelectBlock && onSelectBlock(b)}
                        >
                          <td className="table-cell-mono" style={{ color: '#38bdf8', fontWeight: 700 }}>
                            {bId} {isOvernight ? '🌙' : ''}
                          </td>
                          <td className="table-cell-highlight">{b.location}</td>
                          <td className="table-cell-mono">{b.service_date || b.requested_date || targetDate}</td>
                          <td className="table-cell-mono" style={{ color: '#34d399' }}>{b.start_time || b.requested_start}</td>
                          <td className="table-cell-mono" style={{ color: '#34d399' }}>{b.end_time || b.requested_end}</td>
                          <td className="table-cell-mono">{b.duration_minutes || b.required_duration}m</td>
                          <td><PriorityBadge priority={b.priority} /></td>
                          <td>{b.equipment || 'Standard Gang'}</td>
                          <td>
                            <span className="badge badge-cyan">
                              {b.fit_score != null ? `${(b.fit_score * 100).toFixed(0)}%` : '—'}
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
      )}
    </PageContainer>
  );
}

