import React from 'react';
import { CORRIDOR_DISCIPLINES, inferDiscipline, parseTimeToMinutes } from '../types';

const LANE_BLOCK_HEIGHT = 38;
const LANE_GAP = 5;
const LANE_VERTICAL_PADDING = 6;
const MIN_ROW_HEIGHT = 50;

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

  blocks.forEach((block) => {
    const assignedDiscipline = inferDiscipline(block);

    if (!disciplineMap[assignedDiscipline]) {
      disciplineMap[assignedDiscipline] = [];
    }
    disciplineMap[assignedDiscipline].push(block);
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
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: '0.72rem', color: '#94a3b8' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, background: '#ef4444', borderRadius: 2 }} /> Critical
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, background: '#f97316', borderRadius: 2 }} /> High
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, background: '#eab308', borderRadius: 2 }} /> Medium
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, background: '#10b981', borderRadius: 2 }} /> Low
          </span>
        </div>
      </div>

      <div className="panel-body" style={{ padding: 12 }}>
        <div className="timeline-container">
          {/* Time Ruler */}
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

          {/* Discipline Track Rows */}
          <div className="timeline-track-rows">
            {CORRIDOR_DISCIPLINES.map((discipline) => {
              const disciplineBlocks = disciplineMap[discipline.id] || [];
              const { items, laneCount } = assignLanes(disciplineBlocks);
              const rowHeight = Math.max(
                MIN_ROW_HEIGHT,
                LANE_VERTICAL_PADDING * 2 + laneCount * LANE_BLOCK_HEIGHT + (laneCount - 1) * LANE_GAP
              );

              return (
                <div key={discipline.id} className="timeline-track-row" style={{ minHeight: rowHeight }}>
                  <div className="timeline-row-header">
                    <div className="timeline-row-name">
                      <span>{discipline.icon}</span>
                      <span>{discipline.name.split(' ')[0]}</span>
                    </div>
                    <div className="timeline-row-sub">{discipline.code} Corridor</div>
                  </div>

                  <div className="timeline-grid-track">
                    {items.map(({ block: blk, originalIndex: idx, startMins, durationMins, lane }) => {
                      const leftPct = (startMins / 1440) * 100;
                      const widthPct = Math.max(2.5, (durationMins / 1440) * 100);

                      const priority = String(blk.priority || 'Medium').toLowerCase();
                      const isOvernight = (startMins + durationMins) > 1440;
                      const priorityClass = `possession-${priority}`;

                      const blockId = blk.block_id || blk.block_request_id || blk.request_id || blk.asset_id || `BLK-${idx + 1}`;
                      const startTime = blk.start_time || blk.requested_start || '--:--';
                      const endTime = blk.end_time || blk.requested_end || '--:--';

                      const laneTop = LANE_VERTICAL_PADDING + lane * (LANE_BLOCK_HEIGHT + LANE_GAP);

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
                          title={`${blockId} | ${blk.location || 'Section'}\n${startTime} -> ${endTime} (${durationMins} min)\nPriority: ${blk.priority || 'Normal'}${isOvernight ? ' (Overnight)' : ''}`}
                        >
                          <div className="block-title">
                            {blockId} {isOvernight ? '🌙' : ''}
                          </div>
                          <div className="block-time">
                            {startTime} - {endTime}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
