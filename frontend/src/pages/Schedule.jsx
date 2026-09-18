/**
 * @file Schedule.jsx
 * @description Master optimized maintenance possession schedule and timetable page.
 * Displays multi-lane 24-hour Gantt chart, timetable stop inspector, and possession breakdown
 * with live reflection of manual timetable shifts (↔️), edits (✏️), and pinned slots (📌).
 * Adheres to CS-001-REV-1.0 (RULE-01.1: <= 60 lines per function, RULE-03.2: header).
 * @module pages/Schedule
 */

import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import Timeline from '../components/Timeline';
import PriorityBadge from '../components/PriorityBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

/**
 * Header toolbar with segmented tab toggle between Possession and Timetable views.
 */
function SchedulePanelHeader({ displayBlocks, horizonTotal, targetDate, timetable, activeTab, setActiveTab }) {
  return (
    <div className="panel-header">
      <div>
        <div className="panel-title">
          <span>📅 Master Operational & Possession Schedule</span>
          <span className="badge badge-cyan">{displayBlocks.length} POSSESSIONS ({targetDate})</span>
          {horizonTotal > displayBlocks.length && (
            <span className="badge badge-outline" title={`Full optimization horizon: ${horizonTotal} blocks across all dates`}>
              {horizonTotal} TOTAL HORIZON
            </span>
          )}
          <span className="badge badge-outline">{timetable.length} TIMETABLE STOPS</span>
        </div>
        <div className="panel-subtitle">
          Gantt timeline mapping maintenance possessions and scheduled train stops for {targetDate}
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
  );
}

/**
 * Filter toolbar for selecting priority levels.
 */
function ScheduleFilterBar({ priorityFilter, setPriorityFilter, displayBlocksCount, horizonTotal, targetDate }) {
  return (
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

      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <span className="badge badge-outline">Showing: {displayBlocksCount} for {targetDate}</span>
        {horizonTotal > displayBlocksCount && (
          <span className="badge badge-outline" style={{ color: '#94a3b8' }}>
            Horizon total: {horizonTotal}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Single table row rendering a possession slot with manual shift indicators.
 */
function ScheduleTableRow({ b, idx, targetDate, onSelectBlock }) {
  const bId = b.block_id || b.request_id || `BLK-${idx + 1}`;
  const isOvernight = (b.start_time && b.end_time && b.end_time < b.start_time);

  return (
    <tr
      key={(b.block_id || b.request_id || idx) + '-' + idx}
      className="clickable"
      onClick={() => onSelectBlock && onSelectBlock(b)}
    >
      <td className="table-cell-mono" style={{ color: '#38bdf8', fontWeight: 700 }}>
        {bId} {isOvernight ? '🌙' : ''}
        {b.is_manual_edit ? (
          <span className="badge badge-amber" style={{ marginLeft: 6, fontSize: '0.65rem' }}>✏️ Edited</span>
        ) : b.is_shifted ? (
          <span className="badge badge-amber" style={{ marginLeft: 6, fontSize: '0.65rem' }}>↔️ Shifted</span>
        ) : null}
        {b.is_pinned ? (
          <span className="badge badge-purple" style={{ marginLeft: 4, fontSize: '0.65rem' }}>📌 Pinned</span>
        ) : null}
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
          {b.fit_score != null ? `${(b.fit_score * 100).toFixed(0)}%` : '100%'}
        </span>
      </td>
    </tr>
  );
}

/**
 * Detailed breakdown table of scheduled possession slots.
 */
function ScheduleTable({ displayBlocks, targetDate, onSelectBlock }) {
  if (displayBlocks.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">Possession Slot Breakdown</div>
            <div className="panel-subtitle">Assigned possession time windows and required gang resources</div>
          </div>
        </div>
        <div className="panel-body">
          <EmptyState
            title="No Possessions Scheduled"
            message={`No block possessions scheduled for ${targetDate}. Run CP-SAT optimization or adjust filters.`}
            icon="🚧"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Possession Slot Breakdown</div>
          <div className="panel-subtitle">Assigned possession time windows and required gang resources</div>
        </div>
      </div>
      <div className="panel-body">
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
              {displayBlocks.map((b, idx) => (
                <ScheduleTableRow
                  key={(b.block_id || b.request_id || idx) + '-' + idx}
                  b={b}
                  idx={idx}
                  targetDate={targetDate}
                  onSelectBlock={onSelectBlock}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/**
 * Searchable timetable stops table view.
 */
function TimetableTable({ filteredTimetable, targetDate, timetableSearch, setTimetableSearch }) {
  return (
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
  );
}

/**
 * Main Schedule Page Component.
 */
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
  const [activeTab, setActiveTab] = useState('possession');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [timetableSearch, setTimetableSearch] = useState('');

  const allOptimizedBlocks = optimizationResult?.scheduled_blocks || [];
  const horizonTotal = allOptimizedBlocks.length;

  const displayBlocks = (horizonTotal > 0
    ? allOptimizedBlocks.filter((b) => {
        const blockDate = b.service_date ? String(b.service_date) : null;
        const dateMatch = blockDate ? blockDate === targetDate : true;
        const pMatch = priorityFilter === 'ALL' || String(b.priority).toLowerCase() === priorityFilter.toLowerCase();
        return dateMatch && pMatch;
      })
    : blocks.filter((b) => {
        const pMatch = priorityFilter === 'ALL' || String(b.priority).toLowerCase() === priorityFilter.toLowerCase();
        return pMatch;
      }));

  const filteredTimetable = timetable.filter((tt) => {
    if (!timetableSearch) return true;
    return (tt.train_id && tt.train_id.toLowerCase().includes(timetableSearch.toLowerCase())) ||
           (tt.station_code && tt.station_code.toLowerCase().includes(timetableSearch.toLowerCase()));
  });

  return (
    <PageContainer>
      <div className="panel">
        <SchedulePanelHeader
          displayBlocks={displayBlocks}
          horizonTotal={horizonTotal}
          targetDate={targetDate}
          timetable={timetable}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />

        <div className="panel-body">
          {error ? (
            <ErrorState title="Failed to Load Schedule" message={error} onRetry={onRetry} />
          ) : loading ? (
            <LoadingState message="Generating schedule projection..." />
          ) : activeTab === 'possession' ? (
            <>
              <ScheduleFilterBar
                priorityFilter={priorityFilter}
                setPriorityFilter={setPriorityFilter}
                displayBlocksCount={displayBlocks.length}
                horizonTotal={horizonTotal}
                targetDate={targetDate}
              />
              <Timeline
                blocks={displayBlocks}
                targetDate={targetDate}
                onSelectBlock={onSelectBlock}
              />
            </>
          ) : (
            <TimetableTable
              filteredTimetable={filteredTimetable}
              targetDate={targetDate}
              timetableSearch={timetableSearch}
              setTimetableSearch={setTimetableSearch}
            />
          )}
        </div>
      </div>

      {activeTab === 'possession' && !error && !loading && (
        <ScheduleTable
          displayBlocks={displayBlocks}
          targetDate={targetDate}
          onSelectBlock={onSelectBlock}
        />
      )}
    </PageContainer>
  );
}

