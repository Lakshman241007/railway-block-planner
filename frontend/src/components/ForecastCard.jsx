import React from 'react';

export default function ForecastCard({ forecast, onClick }) {
  const confidence = forecast.confidence_level || (forecast.confidence_score >= 0.75 ? 'HIGH' : forecast.confidence_score >= 0.5 ? 'MEDIUM' : 'LOW');
  
  const getBadgeClass = (conf) => {
    switch (conf) {
      case 'HIGH':
        return 'badge-low'; // green
      case 'MEDIUM':
        return 'badge-medium'; // yellow
      case 'LOW':
      default:
        return 'badge-critical'; // red
    }
  };

  const getBorderColor = (conf) => {
    switch (conf) {
      case 'HIGH':
        return '3px solid #10b981';
      case 'MEDIUM':
        return '3px solid #eab308';
      case 'LOW':
      default:
        return '3px solid #ef4444';
    }
  };

  const delayVal = forecast.delay_minutes ?? forecast.estimated_delay_minutes ?? 0;

  return (
    <div
      className="operation-card clickable"
      onClick={() => onClick && onClick(forecast)}
      style={{
        borderLeft: getBorderColor(confidence),
        minHeight: '160px',
        justifyContent: 'space-between',
      }}
    >
      <div className="card-header-row">
        <div>
          <div className="card-code" style={{ color: '#fbbf24' }}>
            📦 {forecast.train_id}
          </div>
          <div className="card-meta-text">{forecast.section || 'Corridor Section'}</div>
        </div>
        <span className={`badge ${getBadgeClass(confidence)}`}>
          {confidence} CONFIDENCE
        </span>
      </div>

      <div className="card-detail-box">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Forecast Entry</span>
          <span className="table-cell-mono" style={{ color: '#38bdf8' }}>{forecast.forecasted_entry || '--:--'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Forecast Exit</span>
          <span className="table-cell-mono" style={{ color: '#38bdf8' }}>{forecast.forecasted_exit || '--:--'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Estimated Delay</span>
          <span style={{ color: delayVal > 15 ? '#f87171' : '#34d399', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
            {delayVal > 0 ? `+${delayVal} min` : 'Nominal'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8' }}>Confidence Score</span>
          <span className="table-cell-mono" style={{ fontWeight: 600 }}>
            {forecast.confidence_score != null ? `${(forecast.confidence_score * 100).toFixed(0)}%` : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}
