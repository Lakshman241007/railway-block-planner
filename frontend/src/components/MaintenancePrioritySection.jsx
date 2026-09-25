/**
 * @file MaintenancePrioritySection.jsx
 * @description Renders the Phase 5 Maintenance Priority & Explainability section for an asset/block record.
 * Displays authoritative numerical priority value, contributing factors (urgency, criticality, overdue factor,
 * asset availability, operational impact), and backend AI explainability narrative.
 * @module components/MaintenancePrioritySection
 */

import React from 'react';
import { extractPriorityEnrichment } from '../types';

export default function MaintenancePrioritySection({
  block = null,
  loading = false,
  error = null,
  title = "MAINTENANCE PRIORITY",
}) {
  if (loading) {
    return (
      <div className="card-detail-box priority-section-box" style={{ background: 'rgba(15, 23, 42, 0.65)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '6px', padding: '12px 14px', marginTop: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#94a3b8', fontSize: '0.8rem' }}>
          <span className="spinner" style={{ width: 14, height: 14 }} />
          <span>Priority information loading...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card-detail-box priority-section-box" style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.35)', borderRadius: '6px', padding: '12px 14px', marginTop: '12px' }}>
        <div style={{ color: '#fca5a5', fontSize: '0.8rem' }}>
          ⚠ Unable to load priority information: {typeof error === 'string' ? error : error?.message || 'Unknown error'}
        </div>
      </div>
    );
  }

  if (!block) {
    return (
      <div className="card-detail-box priority-section-box" style={{ background: 'rgba(15, 23, 42, 0.4)', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '12px 14px', marginTop: '12px' }}>
        <span className="detail-label" style={{ color: '#38bdf8' }}>{title}</span>
        <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: '6px' }}>
          Priority information unavailable.
        </div>
      </div>
    );
  }

  const {
    priorityValue,
    urgency,
    criticality,
    overdueFactor,
    assetAvailabilityImpact,
    operationalImpact,
    explanation,
  } = extractPriorityEnrichment(block);

  const formatFactor = (val) => {
    if (val == null) return '--';
    if (typeof val === 'number') {
      return val.toFixed(2);
    }
    return String(val);
  };

  return (
    <div
      className="card-detail-box priority-section-box"
      style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        borderRadius: '6px',
        padding: '12px 14px',
        marginTop: '12px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <span
          className="detail-label"
          style={{ color: '#38bdf8', fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.6px' }}
        >
          {title}
        </span>
        {priorityValue != null && (
          <span
            className="badge badge-cyan mono"
            style={{ fontSize: '0.74rem', fontWeight: 700, padding: '2px 8px' }}
          >
            SCORE {priorityValue}
          </span>
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '8px 12px',
          marginBottom: '12px',
        }}
      >
        <div className="detail-item" style={{ gap: '2px' }}>
          <span className="detail-label" style={{ fontSize: '0.68rem' }}>Priority Value</span>
          <span className="detail-val mono" style={{ fontSize: '0.88rem', fontWeight: 700, color: priorityValue != null ? '#38bdf8' : '#64748b' }}>
            {priorityValue != null ? priorityValue : '--'}
          </span>
        </div>

        <div className="detail-item" style={{ gap: '2px' }}>
          <span className="detail-label" style={{ fontSize: '0.68rem' }}>Urgency</span>
          <span className="detail-val mono" style={{ fontSize: '0.82rem', color: urgency != null ? '#f87171' : '#64748b' }}>
            {formatFactor(urgency)}
          </span>
        </div>

        <div className="detail-item" style={{ gap: '2px' }}>
          <span className="detail-label" style={{ fontSize: '0.68rem' }}>Criticality</span>
          <span className="detail-val mono" style={{ fontSize: '0.82rem', color: criticality != null ? '#fb923c' : '#64748b' }}>
            {formatFactor(criticality)}
          </span>
        </div>

        <div className="detail-item" style={{ gap: '2px' }}>
          <span className="detail-label" style={{ fontSize: '0.68rem' }}>Overdue Factor</span>
          <span className="detail-val mono" style={{ fontSize: '0.82rem', color: overdueFactor != null ? '#facc15' : '#64748b' }}>
            {formatFactor(overdueFactor)}
          </span>
        </div>

        <div className="detail-item" style={{ gap: '2px' }}>
          <span className="detail-label" style={{ fontSize: '0.68rem' }}>Asset Availability</span>
          <span className="detail-val mono" style={{ fontSize: '0.82rem', color: assetAvailabilityImpact != null ? '#34d399' : '#64748b' }}>
            {formatFactor(assetAvailabilityImpact)}
          </span>
        </div>

        <div className="detail-item" style={{ gap: '2px' }}>
          <span className="detail-label" style={{ fontSize: '0.68rem' }}>Operational Impact</span>
          <span className="detail-val mono" style={{ fontSize: '0.82rem', color: operationalImpact != null ? '#a78bfa' : '#64748b' }}>
            {formatFactor(operationalImpact)}
          </span>
        </div>
      </div>

      {/* AI Explanation / Why this maintenance was prioritized */}
      <div
        style={{
          borderTop: '1px solid rgba(148, 163, 184, 0.15)',
          paddingTop: '8px',
          marginTop: '4px',
        }}
      >
        <span
          className="detail-label"
          style={{ color: '#94a3b8', fontSize: '0.68rem', display: 'block', marginBottom: '4px' }}
        >
          WHY THIS MAINTENANCE WAS PRIORITIZED
        </span>
        {explanation ? (
          <div
            style={{
              color: '#e2e8f0',
              fontSize: '0.78rem',
              lineHeight: 1.45,
              background: 'rgba(56, 189, 248, 0.05)',
              borderLeft: '3px solid #38bdf8',
              padding: '6px 10px',
              borderRadius: '0 4px 4px 0',
            }}
          >
            "{explanation}"
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: '0.76rem', fontStyle: 'italic' }}>
            Priority explanation unavailable.
          </div>
        )}
      </div>
    </div>
  );
}
