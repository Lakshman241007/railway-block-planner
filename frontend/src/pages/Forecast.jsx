import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import ForecastCard from '../components/ForecastCard';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

export default function Forecast({
  forecasts = [],
  loading = false,
  error = null,
  onRetry,
  onRunForecast,
  isRunning = false,
  targetDate,
}) {
  const [selectedSection, setSelectedSection] = useState('ALL');

  const filtered = forecasts.filter((f) => {
    if (selectedSection === 'ALL') return true;
    return f.section && f.section.toLowerCase().includes(selectedSection.toLowerCase());
  });

  const highConfCount = forecasts.filter((f) => f.confidence_level === 'HIGH' || f.confidence_score >= 0.75).length;

  return (
    <PageContainer>
      {/* Forecast Hero / Stats */}
      <div className="stat-grid">
        <StatCard
          title="GOODS TRAINS DETECTED"
          value={forecasts.length}
          subtitle="Active Corridor Freight"
          icon="📦"
          accent="amber"
          badge="FREIGHT"
          badgeType="warning"
        />

        <StatCard
          title="HIGH CONFIDENCE"
          value={highConfCount}
          subtitle="ML Confidence Score ≥ 75%"
          icon="🎯"
          accent="green"
          badge="HIGH CONF."
          badgeType="success"
        />

        <StatCard
          title="FORECAST HORIZON"
          value="24h"
          subtitle="Entry/Exit Window Predictions"
          icon="⏱️"
          accent="cyan"
          badge="COA / TDMS"
          badgeType="info"
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>📈 Goods Train Movement Forecast Engine</span>
              <span className="badge badge-cyan">{forecasts.length} PREDICTIONS</span>
            </div>
            <div className="panel-subtitle">
              Heuristic transit window predictions powering maintenance possession scheduling for {targetDate}
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

          {error ? (
            <ErrorState
              title="Failed to Load Goods Forecast"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Generating goods train telemetry forecasts..." />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon="📦"
              title="No Freight Forecasts"
              message={`No goods train movements forecasted for ${targetDate || 'selected date'}.`}
              actionLabel={onRunForecast ? "⚡ Run Forecast" : undefined}
              onAction={onRunForecast}
            />
          ) : (
            <div className="card-grid">
              {filtered.map((fc, idx) => (
                <ForecastCard key={fc.train_id + idx} forecast={fc} />
              ))}
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
