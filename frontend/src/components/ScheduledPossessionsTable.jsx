/**
 * @file ScheduledPossessionsTable.jsx
 * @description Renders mathematically optimized maintenance possession assignments.
 * Highlights slot pinning, schedule shifts, and match quality.
 * @module components/ScheduledPossessionsTable
 */

import React from 'react';
import PriorityBadge from './PriorityBadge';

export default function ScheduledPossessionsTable({ blocks = [], onSelectBlock }) {
  if (!blocks.length) return null;

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">
            <span>Optimized Possession Assignments ({blocks.length})</span>
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
                <th>Re-Opt Status</th>
                <th>Fit Score</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {blocks.map((b, idx) => (
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
                  <td>
                    <PriorityBadge
                      priority={b.priority}
                      value={b.priority_value != null ? b.priority_value : b.priority_enrichment?.priority_value}
                      showValue={(b.priority_value != null || b.priority_enrichment?.priority_value != null)}
                    />
                  </td>
                  <td>
                    {b.is_pinned && <span className="badge badge-green">📌 Pinned</span>}
                    {b.is_shifted && (
                      <span className="badge badge-amber" title={`Deviated ${b.deviation_minutes}m from preferred start`}>
                        ↔️ Shifted ({b.deviation_minutes}m)
                      </span>
                    )}
                    {!b.is_pinned && !b.is_shifted && <span className="badge badge-cyan">🎯 Exact Match</span>}
                  </td>
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
  );
}
