/**
 * @file Timeline.jsx
 * @description 24-Hour corridor possession Gantt chart component.
 * Renders multi-discipline occupancy bars with lane-packing for concurrent slots,
 * and real-time visual feedback for manual edits (✏️), shifted slots (↔️), and pinned slots (📌).
 * Adheres to CS-001-REV-1.0 (RULE-01.1: <= 60 lines per function, RULE-03.2: header).
 * @module components/Timeline
 */

import React from 'react';
import { CORRIDOR_DISCIPLINES, inferDiscipline, parseTimeToMinutes } from '../types';

const LANE_BLOCK_HEIGHT = 38;
const LANE_GAP = 5;
const LANE_VERTICAL_PADDING = 6;
const MIN_ROW_HEIGHT = 50;

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
 * Assign possession blocks into non-overlapping vertical lanes for compact Gantt display.
 *
 * @param {Array<Object>} disciplineBlocks - Blocks in the current discipline corridor
 * @returns {{ items: Array<Object>, laneCount: number }} Positioned items with lane indices
 */
function assignLanes(disciplineBlocks) {
  const items = disciplineBlocks.map((block, originalIndex) => {
    const startMins = parseTimeToMinutes(block.start_time || block.requested_start || '00:00');
    const durationMins = block.duration_minutes || block.required_duration || 120;
    const endMins = startMins + durationMins;
    return { block, originalIndex, startMins, durationMins, endMins };
  });

  const sorted = [...items].sort((a, b) => a.startMins - b.startMins || a.endMins - b.endMins);
  const laneEnds = [];

  sorted.forEach((item) => {
    let laneIndex = laneEnds.findIndex((laneEnd) => laneEnd <= item.startMins);
    if (laneIndex === -1) {
      laneIndex = laneEnds.length;
      laneEnds.push(item.endMins);
    } else {
      laneEnds[laneIndex] = item.endMins;
    }
    item.lane = laneIndex;
  });

  return { items: sorted, laneCount: Math.max(1, laneEnds.length) };
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
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: '0.72rem', color: '#94a3b8' }}>
      {legendItems.map((item) => (
        <span key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, background: item.color, borderRadius: 2 }} />
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
        {hours.map((h) => (
          <div key={h} className={`timeline-ruler-slot ${h % 4 === 0 ? 'major' : ''}`}>
            {String(h).padStart(2, '0')}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Single possession block bar rendered inside the 1440-minute day grid.
 */
function TimelinePossessionBlock({ item, onSelectBlock }) {
  const { block: blk, originalIndex: idx, startMins, durationMins, lane } = item;
  const leftPct = (startMins / 1440) * 100;
  const widthPct = Math.max(2.5, (durationMins / 1440) * 100);

  const priority = String(blk.priority || 'Medium').toLowerCase();
  const isOvernight = (startMins + durationMins) > 1440;
  const priorityClass = `possession-${priority}`;

  const blockId = blk.block_id || blk.block_request_id || blk.request_id || blk.asset_id || `BLK-${idx + 1}`;
  const startTime = blk.start_time || blk.requested_start || '--:--';
  const endTime = blk.end_time || blk.requested_end || '--:--';

  const laneTop = LANE_VERTICAL_PADDING + lane * (LANE_BLOCK_HEIGHT + LANE_GAP);
  const editTag = blk.is_manual_edit ? '✏️' : (blk.is_shifted ? '↔️' : '');
  const pinTag = blk.is_pinned ? '📌' : '';
  const tooltipExtra = `${blk.is_manual_edit ? ' (Manually Edited)' : blk.is_shifted ? ' (Shifted)' : ''}${blk.is_pinned ? ' (Pinned)' : ''}`;

  return (
    <div
      key={blockId + idx}
      className={`timeline-possession-block ${priorityClass} ${isOvernight ? 'possession-overnight' : ''}`}
      style={{
        left: `${Math.min(96, Math.max(0, leftPct))}%`,
        width: `${Math.min(100 - leftPct, widthPct)}%`,
        top: laneTop,
        height: LANE_BLOCK_HEIGHT,
        bottom: 'auto',
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
 * A single corridor discipline row containing its scheduled possession blocks in stacked lanes.
 */
function TimelineTrackRow({ discipline, blocks, onSelectBlock }) {
  const { items, laneCount } = assignLanes(blocks);
  const rowHeight = Math.max(
    MIN_ROW_HEIGHT,
    LANE_VERTICAL_PADDING * 2 + laneCount * LANE_BLOCK_HEIGHT + (laneCount - 1) * LANE_GAP
  );

  return (
    <div className="timeline-track-row" style={{ minHeight: rowHeight }}>
      <div className="timeline-row-header">
        <div className="timeline-row-name">
          <span>{discipline.icon}</span>
          <span>{discipline.name.split(' ')[0]}</span>
        </div>
        <div className="timeline-row-sub">{discipline.code} Corridor</div>
      </div>

      <div className="timeline-grid-track">
        {items.map((item) => (
          <TimelinePossessionBlock
            key={(item.block.block_id || item.block.request_id || item.originalIndex) + '-' + item.originalIndex}
            item={item}
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
  const hours = Array.from({ length: 24 }, (_, i) => i);

  const disciplineMap = {};
  CORRIDOR_DISCIPLINES.forEach((d) => {
    disciplineMap[d.id] = [];
  });

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
            Multi-discipline track possession timeline with continuous overnight block visualization
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

