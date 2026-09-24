/**
 * @file ReoptDeltaCard.jsx
 * @description Post-solve Schedule Delta & Re-Optimization Stability Telemetry.
 * Displays churn metrics: Pinned possessions, Shifted time windows, and Stability Score.
 * @module components/ReoptDeltaCard
 */

import React from 'react';

export default function ReoptDeltaCard({ stats, totalScheduled }) {
  if (!stats) return null;

  const pinned = stats.num_pinned || 0;
  const shifted = stats.num_shifted || 0;
  const newlyFitted = Math.max(0, totalScheduled - pinned - shifted);
  const scorePercent = stats.stability_score != null ? Math.round(stats.stability_score * 100) : 100;

  const scoreColor = scorePercent >= 80 ? '#34d399' : scorePercent >= 60 ? '#fbbf24' : '#f87171';

  return (
    <div className="panel" style={{ borderLeft: `4px solid ${scoreColor}`, background: 'rgba(15, 23, 42, 0.7)' }}>
      <div className="panel-header" style={{ padding: '12px 18px', borderBottom: '1px solid rgba(255, 255, 255, 0.07)' }}>
        <div>
          <div className="panel-title" style={{ fontSize: '0.95rem' }}>
            <span>📊 Re-Optimization Schedule Delta & Stability Telemetry</span>
          </div>
          <div className="panel-subtitle" style={{ fontSize: '0.78rem' }}>
            Telemetry quantifying schedule retention versus time window churn from prior allocations
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Stability Score:</span>
          <span style={{ fontSize: '1.2rem', fontWeight: 700, color: scoreColor }}>
            {scorePercent}%
          </span>
        </div>
      </div>

      <div className="panel-body" style={{ padding: '14px 18px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14 }}>
          <div style={{ background: 'rgba(52, 211, 153, 0.08)', padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(52, 211, 153, 0.2)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>🔒 Pinned / Retained</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#34d399' }}>{pinned}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Zero schedule churn</div>
          </div>

          <div style={{ background: 'rgba(251, 191, 36, 0.08)', padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(251, 191, 36, 0.2)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>↔️ Shifted Window</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#fbbf24' }}>{shifted}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Moved to accommodate</div>
          </div>

          <div style={{ background: 'rgba(0, 240, 255, 0.08)', padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(0, 240, 255, 0.2)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>🆕 Newly Fitted</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#00f0ff' }}>{newlyFitted}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Fresh allocations</div>
          </div>

          <div style={{ background: 'rgba(148, 163, 184, 0.08)', padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(148, 163, 184, 0.2)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>🛡️ Headways Protected</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc' }}>{stats.num_conflicts_avoided ?? 0}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Track non-overlap pairs</div>
          </div>
        </div>
      </div>
    </div>
  );
}
