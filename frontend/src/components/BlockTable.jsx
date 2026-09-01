import React, { useState } from 'react';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';

export default function BlockTable({
  blocks = [],
  title = 'Block Requests',
  subtitle = 'Operational track disconnection and maintenance requests',
  onSelectBlock,
  showFilters = true,
}) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');

  const filtered = blocks.filter((b) => {
    const textMatch =
      !search ||
      (b.block_id && b.block_id.toLowerCase().includes(search.toLowerCase())) ||
      (b.asset_id && b.asset_id.toLowerCase().includes(search.toLowerCase())) ||
      (b.location && b.location.toLowerCase().includes(search.toLowerCase())) ||
      (b.reason && b.reason.toLowerCase().includes(search.toLowerCase()));

    const statusMatch =
      statusFilter === 'ALL' ||
      (b.status && String(b.status).toLowerCase() === statusFilter.toLowerCase());

    const priorityMatch =
      priorityFilter === 'ALL' ||
      (b.priority && String(b.priority).toLowerCase() === priorityFilter.toLowerCase());

    return textMatch && statusMatch && priorityMatch;
  });

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">{title} ({filtered.length})</div>
          <div className="panel-subtitle">{subtitle}</div>
        </div>
      </div>

      <div className="panel-body">
        {showFilters && (
          <div className="filter-toolbar">
            <div className="search-input-wrap">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                className="search-input"
                placeholder="Search Block ID, Location, Reason..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="filter-group">
              <select
                className="select-control"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="ALL">All Statuses</option>
                <option value="Approved">Approved</option>
                <option value="Requested">Requested / Pending</option>
                <option value="Completed">Completed</option>
                <option value="Cancelled">Cancelled</option>
              </select>

              <select
                className="select-control"
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
              >
                <option value="ALL">All Priorities</option>
                <option value="Critical">Critical</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>
          </div>
        )}

        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr>
                <th>Block ID</th>
                <th>Location / Section</th>
                <th>Type</th>
                <th>Date</th>
                <th>Time Window</th>
                <th>Duration</th>
                <th>Reason</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                    No matching block requests found.
                  </td>
                </tr>
              ) : (
                filtered.map((b, idx) => {
                  const bId = b.block_id || b.asset_id || `REQ-${idx + 1}`;
                  const start = b.requested_start || b.start_time || '--';
                  const end = b.requested_end || b.end_time || '--';
                  const dur = b.duration_minutes || b.required_duration || '--';
                  const isOvernight = (b.requested_start && b.requested_end && b.requested_end < b.requested_start);

                  return (
                    <tr
                      key={bId + idx}
                      className="clickable"
                      onClick={() => onSelectBlock && onSelectBlock(b)}
                    >
                      <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                        {bId} {isOvernight ? '🌙' : ''}
                      </td>
                      <td className="table-cell-highlight">{b.location}</td>
                      <td>{b.block_type || b.asset_type || 'Track Block'}</td>
                      <td className="table-cell-mono">{b.requested_date || b.service_date}</td>
                      <td className="table-cell-mono">
                        {start} → {end}
                      </td>
                      <td className="table-cell-mono">{dur}m</td>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {b.reason || b.maintenance_type || 'Routine Possession'}
                      </td>
                      <td><PriorityBadge priority={b.priority} /></td>
                      <td><StatusBadge status={b.status} /></td>
                      <td>
                        <span className="badge badge-outline">{b.source || 'BDMS'}</span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
