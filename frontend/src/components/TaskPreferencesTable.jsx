/**
 * @file TaskPreferencesTable.jsx
 * @description Candidate Task Urgency Overrides and Re-Optimization Preferences Table.
 * Allows operators to elevate priorities, lock pinned slots, enforce mandatory scheduling, or skip tasks.
 * @module components/TaskPreferencesTable
 */

import React, { useState } from 'react';
import PriorityBadge from './PriorityBadge';

function TaskPreferenceRow({
  task,
  priorityOverride,
  onOverridePriority,
  mode, // 'auto' | 'pin' | 'force' | 'skip'
  onSelectMode,
  pinnedSlot,
  onUpdatePinnedSlot,
}) {
  const isExcluded = mode === 'skip';
  const isPinned = mode === 'pin';
  const isForced = mode === 'force';

  return (
    <tr style={{ opacity: isExcluded ? 0.5 : 1, transition: 'opacity 0.2s ease' }}>
      <td className="table-cell-mono" style={{ fontWeight: 600, color: '#38bdf8' }}>
        {task.id}
      </td>
      <td style={{ fontSize: '0.85rem' }}>{task.location}</td>
      <td>
        <PriorityBadge priority={task.basePriority} />
      </td>
      <td>
        <select
          className="select-control"
          style={{ padding: '3px 8px', fontSize: '0.78rem', minWidth: 125 }}
          value={priorityOverride || ''}
          onChange={(e) => onOverridePriority(task.id, e.target.value || null)}
          disabled={isExcluded}
        >
          <option value="">(Base: {task.basePriority})</option>
          <option value="Critical">🚨 Critical</option>
          <option value="High">⚠️ High</option>
          <option value="Medium">⚡ Medium</option>
          <option value="Low">⚪ Low</option>
        </select>
      </td>
      <td>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            type="button"
            className={`btn btn-sm ${mode === 'auto' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '2px 8px', fontSize: '0.72rem' }}
            onClick={() => onSelectMode(task.id, 'auto')}
            title="Flexible solver allocation"
          >
            🔄 Auto
          </button>
          <button
            type="button"
            className={`btn btn-sm ${isPinned ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '2px 8px', fontSize: '0.72rem', borderColor: isPinned ? '#34d399' : undefined }}
            onClick={() => onSelectMode(task.id, isPinned ? 'auto' : 'pin')}
            title="Lock slot to current window (zero churn)"
          >
            📌 Pin
          </button>
          <button
            type="button"
            className={`btn btn-sm ${isForced ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '2px 8px', fontSize: '0.72rem', borderColor: isForced ? '#fbbf24' : undefined }}
            onClick={() => onSelectMode(task.id, isForced ? 'auto' : 'force')}
            title="Mandatory hard constraint"
          >
            ⚡ Force
          </button>
          <button
            type="button"
            className={`btn btn-sm ${isExcluded ? 'btn-danger' : 'btn-secondary'}`}
            style={{ padding: '2px 8px', fontSize: '0.72rem' }}
            onClick={() => onSelectMode(task.id, isExcluded ? 'auto' : 'skip')}
            title="Exclude from this re-optimization run"
          >
            🚫 Skip
          </button>
        </div>
      </td>
      <td className="table-cell-mono" style={{ fontSize: '0.78rem' }}>
        {isPinned ? (
          <input
            type="text"
            className="input-control"
            style={{ padding: '2px 6px', fontSize: '0.75rem', width: 105, border: '1px solid #34d399' }}
            value={pinnedSlot || task.defaultSlot || '02:00-04:00'}
            onChange={(e) => onUpdatePinnedSlot(task.id, e.target.value)}
            placeholder="HH:MM-HH:MM"
          />
        ) : (
          <span style={{ color: isExcluded ? '#94a3b8' : '#cbd5e1' }}>
            {task.defaultSlot || `${task.preferredStart} (${task.duration}m)`}
          </span>
        )}
      </td>
    </tr>
  );
}

export default function TaskPreferencesTable({
  candidateTasks = [],
  priorityOverrides = {},
  onOverridePriority,
  taskModes = {},
  onSelectMode,
  pinnedSlots = {},
  onUpdatePinnedSlot,
  isOpen,
  onToggleOpen,
}) {
  const [filterText, setFilterText] = useState('');

  const filtered = candidateTasks.filter((t) => {
    if (!filterText) return true;
    const q = filterText.toLowerCase();
    return t.id.toLowerCase().includes(q) || t.location.toLowerCase().includes(q);
  });

  const pinnedCount = Object.values(taskModes).filter((m) => m === 'pin').length;
  const forcedCount = Object.values(taskModes).filter((m) => m === 'force').length;
  const skippedCount = Object.values(taskModes).filter((m) => m === 'skip').length;
  const overrideCount = Object.keys(priorityOverrides).filter((k) => priorityOverrides[k]).length;

  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <div
        className="panel-header"
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={onToggleOpen}
      >
        <div>
          <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{isOpen ? '▼' : '►'}</span>
            <span>Task Urgency & Re-Optimization Preferences ({candidateTasks.length})</span>
            {overrideCount > 0 && <span className="badge badge-amber">{overrideCount} Overridden</span>}
            {pinnedCount > 0 && <span className="badge badge-green">{pinnedCount} Pinned</span>}
            {forcedCount > 0 && <span className="badge badge-cyan">{forcedCount} Forced</span>}
            {skippedCount > 0 && <span className="badge badge-red">{skippedCount} Excluded</span>}
          </div>
          <div className="panel-subtitle">
            Configure per-task urgency overrides, lock team slots, force mandatory scheduling, or freeze tasks
          </div>
        </div>
      </div>

      {isOpen && (
        <div className="panel-body">
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <input
              type="text"
              className="input-control"
              placeholder="Search candidate tasks by ID or corridor section..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              style={{ maxWidth: 360, fontSize: '0.8rem' }}
            />
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              Showing {filtered.length} of {candidateTasks.length} tasks
            </span>
          </div>

          <div className="table-responsive" style={{ maxHeight: 380, overflowY: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Task ID</th>
                  <th>Location</th>
                  <th>Base Priority</th>
                  <th>Urgency Override</th>
                  <th>Re-Opt Preference</th>
                  <th>Window / Pinned Slot</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((task) => (
                  <TaskPreferenceRow
                    key={task.id}
                    task={task}
                    priorityOverride={priorityOverrides[task.id]}
                    onOverridePriority={onOverridePriority}
                    mode={taskModes[task.id] || 'auto'}
                    onSelectMode={onSelectMode}
                    pinnedSlot={pinnedSlots[task.id]}
                    onUpdatePinnedSlot={onUpdatePinnedSlot}
                  />
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', color: '#94a3b8', padding: 20 }}>
                      No candidate tasks match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
