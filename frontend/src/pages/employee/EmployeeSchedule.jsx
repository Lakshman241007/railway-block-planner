import React, { useState } from 'react';
import PageContainer from '../../components/PageContainer';
import Timeline from '../../components/Timeline';
import PriorityBadge from '../../components/PriorityBadge';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import { getCanonicalPossessions } from '../../types';

export default function EmployeeSchedule({
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

  const {
    possessions: displayBlocks,
    horizonTotal,
    dateTotal,
  } = getCanonicalPossessions({
    optimizationResult,
    blocks,
    targetDate,
    dateScope,
    priorityFilter,
  });

  const filteredTimetable = timetable.filter((tt) => {
    if (!timetableSearch) return true;
    return (
      (tt.train_id && tt.train_id.toLowerCase().includes(timetableSearch.toLowerCase())) ||
      (tt.station_code && tt.station_code.toLowerCase().includes(timetableSearch.toLowerCase()))
    );
  });

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">📅</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            Master Operational & Possession Schedule (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Synchronized Gantt possession timeline and timetable stops for <strong>{targetDate}</strong>. Click any possession to inspect details.
          </div>
        </div>
        <div className="employee-banner-tag">
          {displayBlocks.length} SLOTS
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📅 Master Operational Possession Timeline</span>
              <span className="badge badge-green">
                {displayBlocks.length} POSSESSIONS ({dateScope === 'DATE' ? targetDate : 'HORIZON'})
              </span>
              <span className="badge badge-outline">{timetable.length} TIMETABLE STOPS</span>
            </div>
            <div className="panel-subtitle">
              Visual Gantt diagram mapping track possession windows and scheduled train stops
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
          ) : loading ? (
            <LoadingState message="Generating schedule projection..." />
          ) : activeTab === 'possession' ? (
            <>
              <div className="filter-toolbar">
                <div className="filter-group">
                  <select
                    className="select-control"
                    value={dateScope}
                    onChange={(e) => setDateScope(e.target.value)}
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
                    Showing {displayBlocks.length} {dateScope === 'DATE' ? `for ${targetDate}` : 'across horizon'}
                  </span>
                </div>
              </div>

              {/* Lane-packed visual timeline */}
              <Timeline
                blocks={displayBlocks}
                targetDate={dateScope === 'DATE' ? targetDate : `${targetDate} (Horizon)`}
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

      {/* Schedule Table Summary (Possession Blocks) */}
      {activeTab === 'possession' && !error && !loading && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">Possession Slot Inspection Breakdown</div>
              <div className="panel-subtitle">Assigned possession time windows and required gang resources (Click to inspect)</div>
            </div>
          </div>
          <div className="panel-body">
            {displayBlocks.length === 0 ? (
              <EmptyState
                title="No Possessions Scheduled"
                message={`No block possessions scheduled for ${targetDate}.`}
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
                      <th>Inspection</th>
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
                          <td className="table-cell-mono" style={{ color: '#34d399', fontWeight: 700 }}>
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
      )}
    </PageContainer>
  );
}
