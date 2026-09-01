import React from 'react';

export default function ForecastCard({ forecast, onClick }) {
  const confidence = forecast.confidence_level || (forecast.confidence_score >= 0.75 ? 'HIGH' : forecast.confidence_score >= 0.5 ? 'MEDIUM' : 'LOW');
  const confColor = confidence === 'HIGH' ? '#10b981' : confidence === 'MEDIUM' ? '#f59e0b' : '#ef4444';

  return (
    <div
      className="operation-card clickable"
      onClick={() => onClick && onClick(forecast)}
      style={{ borderLeft: `4px solid ${confColor}` }}
    >
      <div className="card-header-row">
        <div>
          <div className="card-code" style={{ color: '#fbbf24' }}>
            📦 Freight {forecast.train_id}
          </div>
          <div className="card-meta-text">Corridor Section: {forecast.section}</div>
        </div>
        <span
          className="badge"
          style={{
            background: `${confColor}20`,
            borderColor: `${confColor}60`,
            color: confColor,
          }}
        >
          {confidence} CONFIDENCE
        </span>
      </div>

      <div className="card-detail-box">
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Forecasted Entry (ETA):</span>
          <span className="table-cell-mono" style={{ color: '#38bdf8' }}>{forecast.forecasted_entry || '00:00'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Forecasted Exit (ETD):</span>
          <span className="table-cell-mono" style={{ color: '#38bdf8' }}>{forecast.forecasted_exit || '00:00'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Estimated Delay:</span>
          <span style={{ color: forecast.estimated_delay_minutes > 15 ? '#f87171' : '#34d399', fontFamily: 'var(--font-mono)' }}>
            {forecast.estimated_delay_minutes ? `+${forecast.estimated_delay_minutes} min` : 'Nominal'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Confidence Score:</span>
          <span className="table-cell-mono">
            {forecast.confidence_score != null ? `${(forecast.confidence_score * 100).toFixed(0)}%` : '85%'}
          </span>
        </div>
      </div>
    </div>
  );
}
