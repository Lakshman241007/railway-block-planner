/**
 * @file Timeline.jsx
 * @description 24-Hour corridor possession Gantt chart component.
 * Renders multi-discipline occupancy bars with real-time feedback for
 * manual timetable edits (✏️) and pinned possession slots (📌).
 * Adheres to CS-001-REV-1.0 (RULE-01.1: <= 60 lines per function, RULE-03.2: header).
 */

import React from 'react';
import { CORRIDOR_DISCIPLINES, parseTimeToMinutes } from '../types';

/**
 * Assign a maintenance block to its corresponding railway discipline corridor.
 *
 * @param {Object} block - Possession or maintenance record
 * @returns {string} Discipline identifier key
 */
function assignDiscipline(block) {
  const typeStr = String(
    block.block_type || block.maintenance_type || block.reason || block.asset_type || ''
  ).toLowerCase();

  if (typeStr.includes('sig') || typeStr.includes('telecom') || typeStr.includes('cable')) {
    return 'signal';
  }
  if (typeStr.includes('bridge') || typeStr.includes('girder')) {
    return 'bridge';
  }
  if (typeStr.includes('ohe') || typeStr.includes('traction') || typeStr.includes('power') || typeStr.includes('electric')) {
    return 'ohe';
  }
  if (typeStr.includes('point') || typeStr.includes('crossing') || typeStr.includes('switch')) {
    return 'points';
  }
  if (typeStr.includes('lc') || typeStr.includes('gate') || typeStr.includes('level')) {
    return 'level_crossing';
  }
  return 'track';
}

/**
 * Priority legend indicator badge list.
 */
function TimelineLegend() {
  const legendItems = [
    { label: 'Critical', color: '#ef4444' },
    { label: 'High', color: '#f97316' },
    { label: 'Medium', color: '#eab308' },
    { label: 'Low', color: '#10b981' },
  ];

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.75rem' }}>
      {legendItems.map((item) => (
        <span key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, background: item.color, borderRadius: 2 }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

/**
 * 24-Hour top ruler showing hourly increments.
 */
function TimelineHeaderRuler({ hours }) {
  return (
    <div className="timeline-header-ruler">
      <div className="timeline-row-label-col">DISCIPLINE</div>
      <div className="timeline-ruler-slots">
        {hours.slice(0, 24).map((h) => (
          <div key={h} className={`timeline-ruler-slot ${h % 4 === 0 ? 'major' : ''}`}>
            {String(h).padStart(2, '0')}:00
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Single possession block bar rendered inside the 1440-minute day grid.
 */
function TimelinePossessionBlock({ blk, idx, onSelectBlock }) {
  const startMins = parseTimeToMinutes(blk.start_time || blk.requested_start || '00:00');
  const durationMins = blk.duration_minutes || blk.required_duration || 120;
  const leftPct = (startMins / 1440) * 100;
  const widthPct = Math.max(3, (durationMins / 1440) * 100);

  const priority = String(blk.priority || 'Medium').toLowerCase();
  const isOvernight = (startMins + durationMins) > 1440;
  const priorityClass = `possession-${priority}`;

  const blockId = blk.block_id || blk.block_request_id || blk.request_id || blk.asset_id || `BLK-${idx + 1}`;
  const startTime = blk.start_time || blk.requested_start || '--:--';
  const endTime = blk.end_time || blk.requested_end || '--:--';

  const editTag = blk.is_manual_edit ? '✏️' : (blk.is_shifted ? '↔️' : '');
  const pinTag = blk.is_pinned ? '📌' : '';
  const tooltipExtra = `${blk.is_manual_edit ? ' (Manually Edited)' : blk.is_shifted ? ' (Shifted)' : ''}${blk.is_pinned ? ' (Pinned)' : ''}`;

  return (
    <div
      key={blockId + idx}
      className={`timeline-possession-block ${priorityClass} ${isOvernight ? 'possession-overnight' : ''}`}
      style={{
        left: `${Math.min(95, Math.max(0, leftPct))}%`,
        width: `${Math.min(100 - leftPct, widthPct)}%`,
      }}
      onClick={() => onSelectBlock && onSelectBlock(blk)}
      title={`${blockId} | ${blk.location || 'Section'}\n${startTime} -> ${endTime} (${durationMins} min)\nPriority: ${blk.priority || 'Normal'}${isOvernight ? ' (Overnight)' : ''}${tooltipExtra}`}
    >
      <div className="block-title">
        {blockId} {isOvernight ? '🌙' : ''} {editTag} {pinTag}
      </div>
      <div className="block-time">
        {startTime} - {endTime}
      </div>
    </div>
  );
}

/**
 * A single corridor discipline row containing its scheduled possession blocks.
 */
function TimelineTrackRow({ discipline, blocks, onSelectBlock }) {
  return (
    <div className="timeline-track-row">
      <div className="timeline-row-header">
        <div className="timeline-row-name">
          <span>{discipline.icon}</span>
          <span>{discipline.name.split(' ')[0]}</span>
        </div>
        <div className="timeline-row-sub">{discipline.code} Corridor</div>
      </div>

      <div className="timeline-grid-track">
        {blocks.map((blk, idx) => (
          <TimelinePossessionBlock
            key={(blk.block_id || blk.request_id || idx) + '-' + idx}
            blk={blk}
            idx={idx}
            onSelectBlock={onSelectBlock}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Master Timeline component rendering the complete possession Gantt view.
 */
export default function Timeline({
  blocks = [],
  targetDate,
  onSelectBlock,
}) {
  const hours = Array.from({ length: 25 }, (_, i) => i);

  const disciplineMap = {};
  CORRIDOR_DISCIPLINES.forEach((d) => {
    disciplineMap[d.id] = [];
  });

  blocks.forEach((block) => {
    const disciplineId = assignDiscipline(block);
    if (!disciplineMap[disciplineId]) {
      disciplineMap[disciplineId] = [];
    }
    disciplineMap[disciplineId].push(block);
  });

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">
            <span>24-Hour Corridor Operations & Possession Gantt</span>
            <span className="badge badge-cyan">{targetDate || 'Today'}</span>
          </div>
          <div className="panel-subtitle">
            Live multi-discipline possession timeline with continuous overnight block visualization
          </div>
        </div>
        <TimelineLegend />
      </div>

      <div className="panel-body" style={{ padding: 12 }}>
        <div className="timeline-container">
          <TimelineHeaderRuler hours={hours} />
          <div className="timeline-track-rows">
            {CORRIDOR_DISCIPLINES.map((discipline) => (
              <TimelineTrackRow
                key={discipline.id}
                discipline={discipline}
                blocks={disciplineMap[discipline.id] || []}
                onSelectBlock={onSelectBlock}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
