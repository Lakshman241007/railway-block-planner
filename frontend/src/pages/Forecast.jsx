import React, { useState } from 'react';
import ForecastCard from '../components/ForecastCard';
import LoadingState from '../components/LoadingState';

export default function Forecast({ forecasts = [], loading = false, onRunForecast, isRunning = false }) {
  const [selectedSection, setSelectedSection] = useState('ALL');

  const filtered = forecasts.filter((f) => {
    if (selectedSection === 'ALL') return true;
    return f.section && f.section.toLowerCase().includes(selectedSection.toLowerCase());
  });

  const highConfCount = forecasts.filter((f) => f.confidence_level === 'HIGH' || f.confidence_score >= 0.75).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Forecast Hero / Stats */}
      <div className="stat-grid">
        <div className="stat-card accent-amber">
          <div className="stat-card-header">
            <span>GOODS TRAINS DETECTED</span>
            <span>📦</span>
          </div>
          <div className="stat-card-value" style={{ color: '#fbbf24' }}>
            {forecasts.length}
          </div>
          <div className="stat-card-footer">
            <span>Active Corridor Freight</span>
          </div>
        </div>

        <div className="stat-card accent-green">
          <div className="stat-card-header">
            <span>HIGH CONFIDENCE</span>
            <span>🎯</span>
          </div>
          <div className="stat-card-value" style={{ color: '#34d399' }}>
            {highConfCount}
          </div>
          <div className="stat-card-footer">
            <span>ML Confidence Score &ge; 75%</span>
          </div>
        </div>

        <div className="stat-card accent-cyan">
          <div className="stat-card-header">
            <span>FORECAST HORIZON</span>
            <span>⏱️</span>
          </div>
          <div className="stat-card-value" style={{ color: '#38bdf8' }}>
            24h
          </div>
          <div className="stat-card-footer">
            <span>Entry/Exit Window Predictions</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📈 Goods Train Movement Forecast Engine</span>
              <span className="badge badge-cyan">Phase 4</span>
            </div>
            <div className="panel-subtitle">
              Heuristic transit window predictions powering maintenance possession scheduling
            </div>
          </div>

          {onRunForecast && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onRunForecast}
              disabled={isRunning}
            >
              {isRunning ? '⏳ Predicting...' : '⚡ Re-run Forecast'}
            </button>
          )}
        </div>

        <div className="panel-body">
          <div className="filter-toolbar">
            <div className="filter-group">
              <select
                className="select-control"
                value={selectedSection}
                onChange={(e) => setSelectedSection(e.target.value)}
              >
                <option value="ALL">All Sections & Corridors</option>
                <option value="Chennai-Arakkonam">Chennai-Arakkonam</option>
                <option value="Arakkonam-Renigunta">Arakkonam-Renigunta</option>
                <option value="Tambaram-Chengalpattu">Tambaram-Chengalpattu</option>
                <option value="Basin Bridge">Basin Bridge-Vyasarpadi</option>
              </select>
            </div>
          </div>

          {loading ? (
            <LoadingState message="Generating goods train telemetry forecasts..." />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
              No forecasted freight movements found for this section.
            </div>
          ) : (
            <div className="card-grid">
              {filtered.map((fc, idx) => (
                <ForecastCard key={fc.train_id + idx} forecast={fc} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
