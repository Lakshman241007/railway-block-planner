import React, { useState, useMemo } from 'react';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import OperatorConflictCard from '../components/OperatorConflictCard';
import ConflictReviewModal from '../components/ConflictReviewModal';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { ConflictReviewStatus } from '../types';

export default function Conflicts({
  conflicts = [],
  blocks = [],
  loading = false,
  error = null,
  onRetry,
  targetDate,
  isOperator = true,
  onResolveConflict,
  onRejectConflict,
  onDeferConflict,
  onProcessConflicts,
  isProcessing = false,
}) {
  const [selectedConflict, setSelectedConflict] = useState(null);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Normalize review status for each conflict
  const normalizedConflicts = useMemo(() => {
    return conflicts.map((c) => {
      const status =
        c.review_status ||
        c.status ||
        (c.auto_resolved
          ? ConflictReviewStatus.AUTO_RESOLVED
          : ConflictReviewStatus.REQUIRES_HUMAN_REVIEW);
      return {
        ...c,
        calculated_status: status,
      };
    });
  }, [conflicts]);

  // Breakdown counts
  const counts = useMemo(() => {
    const total = normalizedConflicts.length;
    const reqHuman = normalizedConflicts.filter(
      (c) => c.calculated_status === ConflictReviewStatus.REQUIRES_HUMAN_REVIEW
    ).length;
    const autoResolved = normalizedConflicts.filter(
      (c) => c.calculated_status === ConflictReviewStatus.AUTO_RESOLVED
    ).length;
    const humanResolved = normalizedConflicts.filter(
      (c) => c.calculated_status === ConflictReviewStatus.HUMAN_RESOLVED
    ).length;
    const rejected = normalizedConflicts.filter(
      (c) => c.calculated_status === ConflictReviewStatus.REJECTED
    ).length;
    const deferred = normalizedConflicts.filter(
      (c) => c.calculated_status === ConflictReviewStatus.DEFERRED
    ).length;
    const critical = normalizedConflicts.filter(
      (c) => String(c.severity || '').toLowerCase() === 'critical'
    ).length;
    const high = normalizedConflicts.filter(
      (c) =>
        String(c.severity || '').toLowerCase() === 'high' ||
        String(c.severity || '').toLowerCase() === 'major'
    ).length;
    const mediumLow = total - critical - high;

    return { total, reqHuman, autoResolved, humanResolved, rejected, deferred, critical, high, mediumLow };
  }, [normalizedConflicts]);

  // Filtered conflicts
  const filtered = useMemo(() => {
    return normalizedConflicts.filter((c) => {
      // 1. Status Filter
      if (statusFilter !== 'ALL') {
        if (c.calculated_status !== statusFilter) return false;
      }

      // 2. Severity Filter
      if (severityFilter !== 'ALL') {
        const s = String(c.severity || '').toLowerCase();
        if (severityFilter === 'CRITICAL' && s !== 'critical') return false;
        if (severityFilter === 'HIGH' && s !== 'high' && s !== 'major') return false;
        if (severityFilter === 'MEDIUM' && s !== 'medium' && s !== 'low' && s !== 'minor') return false;
      }

      // 3. Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const loc = String(c.location || '').toLowerCase();
        const id = String(c.conflict_id || '').toLowerCase();
        const e1 = String(c.entity1_id || '').toLowerCase();
        const e2 = String(c.entity2_id || '').toLowerCase();
        const desc = String(c.description || '').toLowerCase();
        const sug = String(c.suggested_action || '').toLowerCase();
        if (
          !loc.includes(q) &&
          !id.includes(q) &&
          !e1.includes(q) &&
          !e2.includes(q) &&
          !desc.includes(q) &&
          !sug.includes(q)
        ) {
          return false;
        }
      }

      return true;
    });
  }, [normalizedConflicts, statusFilter, severityFilter, searchQuery]);

  const handleQuickResolve = async (conflictId, payload) => {
    if (onResolveConflict) {
      await onResolveConflict(conflictId, payload || {
        action: 'ACCEPT_RECOMMENDATION',
        notes: 'Resolved by operator review',
      });
    }
  };

  const handleQuickDefer = async (conflictId, payload) => {
    if (onDeferConflict) {
      await onDeferConflict(conflictId, payload || {
        reason: 'AWAITING_TRAFFIC_UPDATE',
        notes: 'Deferred to next cycle',
      });
    }
  };

  const handleQuickReject = async (conflictId, payload) => {
    if (onRejectConflict) {
      await onRejectConflict(conflictId, payload || {
        reason: 'SCHEDULE_UNVIABLE',
        notes: 'Rejected by operator',
      });
    }
  };

  return (
    <PageContainer>
      {/* Operator Awareness & Mission Header Banner (Matching Employee rhythm) */}
      <div className="operator-action-bar" style={{ padding: '16px 24px', borderRadius: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              background: 'rgba(2, 132, 199, 0.16)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.45rem',
              color: '#38bdf8',
              flexShrink: 0,
            }}
          >
            ⚠
          </div>
          <div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.2px' }}>
              Spatial-Temporal Conflict Dispatch (Decision Center)
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 3, lineHeight: 1.45 }}>
              Active collision detection telemetry, train-block headway infractions & machine capacity saturation for <strong>{targetDate}</strong>. Execute operator verification and resolution workflows.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="employee-banner-tag" style={{ background: 'rgba(2, 132, 199, 0.18)', borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8', fontSize: '0.76rem', padding: '6px 14px' }}>
            {conflicts.length} INCIDENTS DETECTED
          </div>
        </div>
      </div>

      {/* 4 Standardized KPIs (Matching Employee Visual Hierarchy) */}
      <div className="stat-grid">
        <StatCard
          title="HUMAN REVIEW REQUIRED"
          value={counts.reqHuman}
          subtitle="Awaiting operator verification"
          icon="🚨"
          accent={counts.reqHuman > 0 ? "red" : "green"}
          badge={counts.reqHuman > 0 ? "ACTION NEEDED" : "CLEAR"}
          badgeType={counts.reqHuman > 0 ? "critical" : "success"}
        />

        <StatCard
          title="AUTO-RESOLVED"
          value={counts.autoResolved}
          subtitle="Resolved by AutoResolver engine"
          icon="🤖"
          accent="green"
          badge="AUTOMATED"
          badgeType="low"
        />

        <StatCard
          title="CRITICAL COLLISIONS"
          value={counts.critical}
          subtitle="Direct Track Overlap"
          icon="⛔"
          accent="red"
          badge={counts.critical > 0 ? "CRITICAL" : "ZERO"}
          badgeType={counts.critical > 0 ? "critical" : "success"}
        />

        <StatCard
          title="HEADWAY WARNINGS"
          value={counts.high + counts.mediumLow}
          subtitle="Buffer Separation < 15m"
          icon="⏱️"
          accent="amber"
          badge="BUFFER"
          badgeType="info"
        />
      </div>

      {/* Main Conflict Center Panel */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>⚠ Spatial-Temporal Conflict Decision Center</span>
              <span className={`badge ${conflicts.length > 0 ? 'badge-critical' : 'badge-green'}`}>
                {filtered.length} INCIDENTS
              </span>
              <span className="badge badge-outline">OPERATOR DECISION DECK</span>
            </div>
            <div className="panel-subtitle">
              Collision detection engine telemetry & human verification decision queue across passenger timetables, freight paths, and track possession blocks
            </div>
          </div>

          {/* AutoResolver Re-scan Trigger */}
          {onProcessConflicts && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => onProcessConflicts({ target_date: targetDate, buffer_minutes: 15 })}
              disabled={isProcessing || loading}
              style={{ fontWeight: 700 }}
            >
              {isProcessing ? '⚡ Scanning AutoResolver...' : '⚡ Re-scan AutoResolver'}
            </button>
          )}
        </div>

        <div className="panel-body">
          {/* Filter & Search Toolbar */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              background: 'rgba(9, 14, 26, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 8,
              padding: '12px 16px',
            }}
          >
            {/* Status Segmented Tabs */}
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

            {/* Search and Severity Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', width: 240 }}>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search conflicts, IDs, locations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ height: 34, fontSize: '0.78rem', paddingLeft: 30 }}
                />
                <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#64748b', fontSize: '0.75rem' }}>
                  🔍
                </span>
              </div>

              <select
                className="select-control"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                style={{ height: 34, width: 150, fontSize: '0.78rem' }}
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">Critical Only</option>
                <option value="HIGH">High Only</option>
                <option value="MEDIUM">Medium / Low</option>
              </select>

              <span className="badge badge-outline" style={{ height: 34, display: 'inline-flex', alignItems: 'center' }}>
                Showing {filtered.length} of {conflicts.length}
              </span>
            </div>
          </div>

          {/* Main Content Area */}
          {error ? (
            <ErrorState
              title="Failed to Load Conflict Analysis"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Scanning operational entities for spatial-temporal overlaps..." />
          ) : conflicts.length === 0 && blocks.length === 0 ? (
            <EmptyState
              icon="📭"
              title="No Block Data Available"
              message="No block possession requests available to analyze for conflicts."
            />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 16px', color: '#10b981' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>🛡️</div>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>No Operational Conflicts Found</div>
              <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginTop: 4 }}>
                No incidents match the active filters for {targetDate}. All active possessions maintain safe headway.
              </div>
            </div>
          ) : (
            /* Primary Presentation: Stacked Incident Cards with Rich Decision Controls */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {filtered.map((conflict, idx) => (
                <OperatorConflictCard
                  key={conflict.conflict_id || idx}
                  conflict={conflict}
                  onReview={setSelectedConflict}
                  onResolve={handleQuickResolve}
                  onReject={handleQuickReject}
                  onDefer={handleQuickDefer}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detailed Human Verification Modal */}
      {selectedConflict && (
        <ConflictReviewModal
          conflict={selectedConflict}
          onClose={() => setSelectedConflict(null)}
          onResolve={onResolveConflict || handleQuickResolve}
          onReject={onRejectConflict || handleQuickReject}
          onDefer={onDeferConflict || handleQuickDefer}
          isOperator={isOperator}
        />
      )}
    </PageContainer>
  );
}
