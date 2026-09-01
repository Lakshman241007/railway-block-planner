import React from 'react';
import { CORRIDOR_DISCIPLINES, parseTimeToMinutes } from '../types';

export default function Timeline({
  blocks = [],
  targetDate,
  onSelectBlock,
}) {
  // Hours to render on ruler (00 to 24)
  const hours = Array.from({ length: 25 }, (_, i) => i);

  // Group blocks into disciplines
  const disciplineMap = {};
  CORRIDOR_DISCIPLINES.forEach((d) => {
    disciplineMap[d.id] = [];
  });

  blocks.forEach((block) => {
    // Map block type or reason or location to discipline
    const typeStr = String(block.block_type || block.maintenance_type || block.reason || block.asset_type || '').toLowerCase();
    let assignedDiscipline = 'track';

    if (typeStr.includes('sig') || typeStr.includes('telecom') || typeStr.includes('cable')) {
      assignedDiscipline = 'signal';
    } else if (typeStr.includes('bridge') || typeStr.includes('girder')) {
      assignedDiscipline = 'bridge';
    } else if (typeStr.includes('ohe') || typeStr.includes('traction') || typeStr.includes('power') || typeStr.includes('electric')) {
      assignedDiscipline = 'ohe';
    } else if (typeStr.includes('point') || typeStr.includes('crossing') || typeStr.includes('switch')) {
      assignedDiscipline = 'points';
    } else if (typeStr.includes('lc') || typeStr.includes('gate') || typeStr.includes('level')) {
      assignedDiscipline = 'level_crossing';
    }

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
            Live multi-discipline possession timeline with continuous overnight block visualization
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#ef4444', borderRadius: 2 }} /> Critical
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#f97316', borderRadius: 2 }} /> High
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#eab308', borderRadius: 2 }} /> Medium
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#10b981', borderRadius: 2 }} /> Low
          </span>
        </div>
      </div>

      <div className="panel-body" style={{ padding: 12 }}>
        <div className="timeline-container">
          {/* Time Ruler */}
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

          {/* Discipline Track Rows */}
          <div className="timeline-track-rows">
            {CORRIDOR_DISCIPLINES.map((discipline) => {
              const disciplineBlocks = disciplineMap[discipline.id] || [];

              return (
                <div key={discipline.id} className="timeline-track-row">
                  <div className="timeline-row-header">
                    <div className="timeline-row-name">
                      <span>{discipline.icon}</span>
                      <span>{discipline.name.split(' ')[0]}</span>
                    </div>
                    <div className="timeline-row-sub">{discipline.code} Corridor</div>
                  </div>

                  <div className="timeline-grid-track">
                    {disciplineBlocks.map((blk, idx) => {
                      const startMins = parseTimeToMinutes(blk.start_time || blk.requested_start || '00:00');
                      const durationMins = blk.duration_minutes || blk.required_duration || 120;
                      
                      // Calculate position on 1440-minute day scale
                      const leftPct = (startMins / 1440) * 100;
                      const widthPct = Math.max(3, (durationMins / 1440) * 100);

                      const priority = String(blk.priority || 'Medium').toLowerCase();
                      const isOvernight = (startMins + durationMins) > 1440;
                      const priorityClass = `possession-${priority}`;

                      const blockId = blk.block_id || blk.block_request_id || blk.request_id || blk.asset_id || `BLK-${idx + 1}`;
                      const startTime = blk.start_time || blk.requested_start || '--:--';
                      const endTime = blk.end_time || blk.requested_end || '--:--';

                      return (
                        <div
                          key={blockId + idx}
                          className={`timeline-possession-block ${priorityClass} ${isOvernight ? 'possession-overnight' : ''}`}
                          style={{
                            left: `${Math.min(95, Math.max(0, leftPct))}%`,
                            width: `${Math.min(100 - leftPct, widthPct)}%`,
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
