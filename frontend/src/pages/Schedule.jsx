/**
 * @file Schedule.jsx
 * @description Master optimized maintenance possession schedule page.
 * Displays 24-hour Gantt chart and possession slot breakdown table with
 * live reflection of manual timetable shifts and pinned slots.
 * Adheres to CS-001-REV-1.0 (RULE-01.1: <= 60 lines per function, RULE-03.2: header).
 */

import React, { useState } from 'react';
import Timeline from '../components/Timeline';
import PriorityBadge from '../components/PriorityBadge';
import LoadingState from '../components/LoadingState';

/**
 * Filter toolbar for selecting priority levels.
 */
function ScheduleFilterBar({ priorityFilter, setPriorityFilter, totalCount }) {
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

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <span className="badge badge-outline">Total Allocated: {totalCount}</span>
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
  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">Possession Slot Breakdown</div>
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
 * Main Schedule Page Component.
 */
export default function Schedule({
  blocks = [],
  optimizationResult,
  targetDate,
  onSelectBlock,
  loading = false,
}) {
  const [priorityFilter, setPriorityFilter] = useState('ALL');

  const displayBlocks = (optimizationResult?.scheduled_blocks?.length
    ? optimizationResult.scheduled_blocks
    : blocks).filter((b) => {
      const pMatch = priorityFilter === 'ALL' || String(b.priority).toLowerCase() === priorityFilter.toLowerCase();
      return pMatch;
    });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📅 Master Optimized Maintenance Possession Schedule</span>
              <span className="badge badge-cyan">{displayBlocks.length} POSSESSIONS</span>
            </div>
            <div className="panel-subtitle">
              High-resolution Gantt view mapping maintenance occupations across corridors and track sections
            </div>
          </div>
        </div>

        <div className="panel-body">
          <ScheduleFilterBar
            priorityFilter={priorityFilter}
            setPriorityFilter={setPriorityFilter}
            totalCount={displayBlocks.length}
          />

          {loading ? (
            <LoadingState message="Generating schedule projection..." />
          ) : (
            <Timeline
              blocks={displayBlocks}
              targetDate={targetDate}
              onSelectBlock={onSelectBlock}
            />
          )}
        </div>
      </div>

      <ScheduleTable
        displayBlocks={displayBlocks}
        targetDate={targetDate}
        onSelectBlock={onSelectBlock}
      />
    </div>
  );
}
