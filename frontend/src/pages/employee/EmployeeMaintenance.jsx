import React, { useState } from 'react';
import PageContainer from '../../components/PageContainer';
import PriorityBadge from '../../components/PriorityBadge';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function EmployeeMaintenance({
  maintenanceRecords = [],
  loading = false,
  error = null,
  onRetry,
  onSelectBlock,
}) {
  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('ALL');

  const filtered = maintenanceRecords.filter((m) => {
    const textMatch =
      !search ||
      (m.asset_id && m.asset_id.toLowerCase().includes(search.toLowerCase())) ||
      (m.location && m.location.toLowerCase().includes(search.toLowerCase())) ||
      (m.maintenance_type && m.maintenance_type.toLowerCase().includes(search.toLowerCase())) ||
      (m.equipment && m.equipment.toLowerCase().includes(search.toLowerCase()));

    const priorityMatch =
      priorityFilter === 'ALL' ||
      (m.priority && String(m.priority).toLowerCase() === priorityFilter.toLowerCase());

    return textMatch && priorityMatch;
  });

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">🛠</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            SMMS Maintenance Work Orders Roster (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Safety & Maintenance Management System records, asset maintenance windows, and gang machinery allocations.
          </div>
        </div>
        <div className="employee-banner-tag">
          {filtered.length} ASSETS
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>🛠 SMMS Scheduled Work Orders</span>
              <span className="badge badge-green">{filtered.length} ORDERS</span>
              <span className="badge badge-outline">READ-ONLY MONITORING</span>
            </div>
            <div className="panel-subtitle">
              Detailed tracking of required maintenance slots, required gangs & machinery
            </div>
          </div>
        </div>

        <div className="panel-body">
          <div className="filter-toolbar">
            <div className="search-input-wrap">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                className="search-input"
                placeholder="Search Asset ID, Location, Equipment..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

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
          </div>

          {error ? (
            <ErrorState
              title="Failed to Load Maintenance Data"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Loading maintenance work orders..." />
          ) : (
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Asset ID</th>
                    <th>Asset Type</th>
                    <th>Location</th>
                    <th>Maintenance Type</th>
                    <th>Requested Date</th>
                    <th>Preferred Start</th>
                    <th>Duration</th>
                    <th>Equipment</th>
                    <th>Gangs</th>
                    <th>Priority</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan="11" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                        No maintenance work orders found matching criteria.
                      </td>
                    </tr>
                  ) : (
                    filtered.map((m, idx) => (
                      <tr
                        key={m.asset_id + idx}
                        className="clickable"
                        onClick={() => onSelectBlock && onSelectBlock(m)}
                      >
                        <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                          {m.asset_id}
                        </td>
                        <td>{m.asset_type || 'Track'}</td>
                        <td className="table-cell-highlight">{m.location}</td>
                        <td>{m.maintenance_type || 'Inspection'}</td>
                        <td className="table-cell-mono">{m.requested_date}</td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{m.preferred_start || '--:--'}</td>
                        <td className="table-cell-mono">{m.duration_minutes || m.required_duration}m</td>
                        <td>
                          <span className="badge badge-outline">{m.equipment || 'Standard'}</span>
                        </td>
                        <td className="table-cell-mono">{m.required_resources || 1}</td>
                        <td><PriorityBadge priority={m.priority} /></td>
                        <td><StatusBadge status={m.status} /></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
