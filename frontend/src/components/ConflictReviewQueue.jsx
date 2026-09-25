import React, { useState, useMemo } from 'react';
import { ConflictReviewStatus, getConflictReviewBadgeClass } from '../types';

export default function ConflictReviewQueue({
  conflicts = [],
  onSelectConflict,
  onQuickResolve,
  onQuickDefer,
  isOperator = false,
  loading = false,
}) {
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Normalize review status for each conflict
  const normalizedConflicts = useMemo(() => {
    return conflicts.map((c) => {
      const status = c.review_status || c.status || (c.auto_resolved ? ConflictReviewStatus.AUTO_RESOLVED : ConflictReviewStatus.REQUIRES_HUMAN_REVIEW);
      return {
        ...c,
        calculated_status: status,
      };
    });
  }, [conflicts]);

  const filteredConflicts = useMemo(() => {
    return normalizedConflicts.filter((c) => {
      // 1. Status Filter
      if (statusFilter !== 'ALL') {
        if (c.calculated_status !== statusFilter) return false;
      }

      // 2. Severity Filter
      if (severityFilter !== 'ALL') {
        const s = String(c.severity || '').toLowerCase();
        if (s !== severityFilter.toLowerCase()) return false;
      }

      // 3. Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const loc = String(c.location || '').toLowerCase();
        const id = String(c.conflict_id || '').toLowerCase();
        const e1 = String(c.entity1_id || '').toLowerCase();
        const e2 = String(c.entity2_id || '').toLowerCase();
        const desc = String(c.description || '').toLowerCase();
        if (!loc.includes(q) && !id.includes(q) && !e1.includes(q) && !e2.includes(q) && !desc.includes(q)) {
          return false;
        }
      }

      return true;
    });
  }, [normalizedConflicts, statusFilter, severityFilter, searchQuery]);

  // Status breakdown counts
  const counts = useMemo(() => {
    const total = normalizedConflicts.length;
    const reqHuman = normalizedConflicts.filter((c) => c.calculated_status === ConflictReviewStatus.REQUIRES_HUMAN_REVIEW).length;
    const autoResolved = normalizedConflicts.filter((c) => c.calculated_status === ConflictReviewStatus.AUTO_RESOLVED).length;
    const humanResolved = normalizedConflicts.filter((c) => c.calculated_status === ConflictReviewStatus.HUMAN_RESOLVED).length;
    const rejected = normalizedConflicts.filter((c) => c.calculated_status === ConflictReviewStatus.REJECTED).length;
    const deferred = normalizedConflicts.filter((c) => c.calculated_status === ConflictReviewStatus.DEFERRED).length;
    return { total, reqHuman, autoResolved, humanResolved, rejected, deferred };
  }, [normalizedConflicts]);

  const getSeverityBadge = (sev) => {
    const s = String(sev || '').toLowerCase();
    if (s === 'critical') return <span className="badge badge-critical">CRITICAL</span>;
    if (s === 'high') return <span className="badge badge-high">HIGH</span>;
    if (s === 'medium') return <span className="badge badge-medium">MEDIUM</span>;
    return <span className="badge badge-low">LOW</span>;
  };

  return (
    <div className="table-wrapper" style={{ marginTop: 12 }}>
      {/* Header Controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        {/* Status segmented filters */}
        <div className="segmented-control" style={{ overflowX: 'auto', maxWidth: '100%' }}>
          <button
            type="button"
            className={`segmented-tab ${statusFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setStatusFilter('ALL')}
          >
            All ({counts.total})
          </button>
          <button
            type="button"
            className={`segmented-tab ${statusFilter === ConflictReviewStatus.REQUIRES_HUMAN_REVIEW ? 'active' : ''}`}
            onClick={() => setStatusFilter(ConflictReviewStatus.REQUIRES_HUMAN_REVIEW)}
          >
            Needs Review ({counts.reqHuman})
          </button>
          <button
            type="button"
            className={`segmented-tab ${statusFilter === ConflictReviewStatus.AUTO_RESOLVED ? 'active' : ''}`}
            onClick={() => setStatusFilter(ConflictReviewStatus.AUTO_RESOLVED)}
          >
            Auto-Resolved ({counts.autoResolved})
          </button>
          <button
            type="button"
            className={`segmented-tab ${statusFilter === ConflictReviewStatus.HUMAN_RESOLVED ? 'active' : ''}`}
            onClick={() => setStatusFilter(ConflictReviewStatus.HUMAN_RESOLVED)}
          >
            Human-Resolved ({counts.humanResolved})
          </button>
          <button
            type="button"
            className={`segmented-tab ${statusFilter === ConflictReviewStatus.DEFERRED ? 'active' : ''}`}
            onClick={() => setStatusFilter(ConflictReviewStatus.DEFERRED)}
          >
            Deferred ({counts.deferred})
          </button>
          <button
            type="button"
            className={`segmented-tab ${statusFilter === ConflictReviewStatus.REJECTED ? 'active' : ''}`}
            onClick={() => setStatusFilter(ConflictReviewStatus.REJECTED)}
          >
            Rejected ({counts.rejected})
          </button>
        </div>

        {/* Search input & severity filter */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="text"
            className="text-input"
            placeholder="Search conflicts, IDs, locations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 220, fontSize: '0.78rem' }}
          />

          <select
            className="select-input"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{ fontSize: '0.78rem' }}
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {filteredConflicts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '32px 16px', color: '#94a3b8' }}>
          <div style={{ fontSize: '1.6rem', marginBottom: 6 }}>🛡️</div>
          <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: '0.9rem' }}>No conflicts match the current review filters</div>
          <div style={{ fontSize: '0.75rem', marginTop: 4 }}>
            Try adjusting your search query or status filter.
          </div>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Conflict ID</th>
                <th>Location / Section</th>
                <th>Window / Overlap</th>
                <th>Affected Entities</th>
                <th>Severity</th>
                <th>Review Status</th>
                <th>Recommended Action</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredConflicts.map((conflict, idx) => {
                const isCritical = String(conflict.severity || '').toLowerCase() === 'critical';
                const status = conflict.calculated_status;
                const requiresHuman = status === ConflictReviewStatus.REQUIRES_HUMAN_REVIEW;

                return (
                  <tr
                    key={conflict.conflict_id || idx}
                    style={{
                      cursor: 'pointer',
                      background: isCritical && requiresHuman ? 'rgba(239, 68, 68, 0.05)' : undefined,
                    }}
                    onClick={() => onSelectConflict(conflict)}
                  >
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>{isCritical ? '🚨' : '⚠'}</span>
                        <span className="mono" style={{ fontWeight: 600, color: '#f8fafc' }}>
                          {conflict.conflict_id || `CONF-${idx + 1}`}
                        </span>
                      </div>
                    </td>

                    <td>
                      <div style={{ fontWeight: 500, color: '#e2e8f0', fontSize: '0.78rem' }}>
                        {conflict.location || '—'}
                      </div>
                    </td>

                    <td>
                      <div className="mono" style={{ fontSize: '0.75rem', color: isCritical ? '#f87171' : '#fbbf24' }}>
                        {conflict.start_time || '--:--'} - {conflict.end_time || '--:--'}
                      </div>
                      <div style={{ fontSize: '0.68rem', color: '#64748b' }}>
                        {conflict.overlap_minutes || 0}m duration
                      </div>
                    </td>

                    <td>
                      <div style={{ fontSize: '0.75rem' }}>
                        <span style={{ color: '#38bdf8' }}>{conflict.entity1_id || 'Block'}</span>
                        <span style={{ color: '#64748b', margin: '0 4px' }}>⚡</span>
                        <span style={{ color: '#f43f5e' }}>{conflict.entity2_id || 'Train'}</span>
                      </div>
                    </td>

                    <td>{getSeverityBadge(conflict.severity)}</td>

                    <td>
                      <span className={`badge ${getConflictReviewBadgeClass(status)}`}>
                        {status}
                      </span>
                    </td>

                    <td>
                      <div
                        style={{
                          fontSize: '0.74rem',
                          color: '#cbd5e1',
                          maxWidth: 220,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={conflict.suggested_action || 'None'}
                      >
                        {conflict.suggested_action || '—'}
                      </div>
                    </td>

                    <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'inline-flex', gap: 6 }}>
                        <button
                          type="button"
                          className="btn-action btn-outline"
                          style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                          onClick={() => onSelectConflict(conflict)}
                        >
                          Review
                        </button>
                        {isOperator && requiresHuman && onQuickResolve && (
                          <button
                            type="button"
                            className="btn-action btn-primary"
                            style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                            onClick={() => onQuickResolve(conflict.conflict_id)}
                            title="Quick Resolve with AutoResolver recommendation"
                          >
                            ✓
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
