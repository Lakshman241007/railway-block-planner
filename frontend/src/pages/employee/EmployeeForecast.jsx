import React, { useState } from 'react';
import PageContainer from '../../components/PageContainer';
import StatCard from '../../components/StatCard';
import ForecastCard from '../../components/ForecastCard';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';

export default function EmployeeForecast({
  forecasts = [],
  loading = false,
  error = null,
  onRetry,
  targetDate,
}) {
  const [selectedSection, setSelectedSection] = useState('ALL');

  const filtered = forecasts.filter((f) => {
    if (selectedSection === 'ALL') return true;
    return f.section && f.section.toLowerCase().includes(selectedSection.toLowerCase());
  });

  const highConfCount = forecasts.filter(
    (f) => f.confidence_level === 'HIGH' || f.confidence_score >= 0.75
  ).length;

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">📈</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            Goods Train Freight Forecast Telemetry (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Predicted transit windows for unscheduled freight rakes across Chennai division corridors for <strong>{targetDate}</strong>. Published by Central Freight Dispatch.
          </div>
        </div>
        <div className="employee-banner-tag">
          {forecasts.length} FREIGHT PREDICTIONS
        </div>
      </div>

      {/* Forecast Hero / Stats */}
      <div className="stat-grid">
        <StatCard
          title="GOODS TRAINS DETECTED"
          value={forecasts.length}
          subtitle="Active Corridor Freight Rakes"
          icon="📦"
          accent="amber"
          badge="FREIGHT FEED"
          badgeType="warning"
        />

        <StatCard
          title="HIGH CONFIDENCE FORECASTS"
          value={highConfCount}
          subtitle="Confidence Score ≥ 75%"
          icon="🎯"
          accent="green"
          badge="HIGH CONF."
          badgeType="success"
        />

        <StatCard
          title="PREDICTION HORIZON"
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
              <span>📈 Goods Train Movement Forecast Feed</span>
              <span className="badge badge-green">{forecasts.length} ACTIVE PREDICTIONS</span>
              <span className="badge badge-outline">READ-ONLY FEED</span>
            </div>
            <div className="panel-subtitle">
              Heuristic transit window predictions powering maintenance possession scheduling for {targetDate}
            </div>
          </div>
          {/* Strictly NO "Run Forecast" button for employee */}
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
            <span className="badge badge-outline">
              Showing {filtered.length} of {forecasts.length} predictions
            </span>
          </div>

          {error ? (
            <ErrorState
              title="Failed to Load Goods Forecast"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Fetching goods train telemetry predictions..." />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon="📦"
              title="No Freight Forecasts"
              message={`No goods train movements forecasted for ${targetDate || 'selected date'}.`}
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
