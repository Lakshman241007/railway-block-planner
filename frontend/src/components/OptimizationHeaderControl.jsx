/**
 * @file OptimizationHeaderControl.jsx
 * @description Header control bar for CP-SAT Optimization triggers and solver parameters.
 * @module components/OptimizationHeaderControl
 */

import React from 'react';

export default function OptimizationHeaderControl({
  horizonDays,
  setHorizonDays,
  bufferMinutes,
  setBufferMinutes,
  includeForecast,
  setIncludeForecast,
  handleRun,
  isOptimizing,
  optimizationStep,
}) {
  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">
            <span>⚡ Google OR-Tools CP-SAT Mathematical Optimizer</span>
            <span className="badge badge-cyan">Phase 5</span>
          </div>
          <div className="panel-subtitle">
            Constraint programming solver with track mutual exclusion, headway buffers & resource capacity bounds
          </div>
        </div>

        <button className="btn btn-primary" onClick={handleRun} disabled={isOptimizing}>
          {isOptimizing ? '⚡ SOLVING CP-SAT...' : '⚡ RUN CP-SAT OPTIMIZATION'}
        </button>
      </div>

      <div className="panel-body">
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="detail-item" style={{ minWidth: 150 }}>
            <label className="detail-label">Planning Horizon</label>
            <select
              className="select-control"
              value={horizonDays}
              onChange={(e) => setHorizonDays(e.target.value)}
              disabled={isOptimizing}
            >
              <option value="1">1 Day (Shift Plan)</option>
              <option value="3">3 Days (Rolling)</option>
              <option value="7">7 Days (Weekly Plan)</option>
              <option value="14">14 Days (Bi-Weekly)</option>
              <option value="30">30 Days (Monthly Plan)</option>
            </select>
          </div>

          <div className="detail-item" style={{ minWidth: 150 }}>
            <label className="detail-label">Safety Buffer (Min)</label>
            <select
              className="select-control"
              value={bufferMinutes}
              onChange={(e) => setBufferMinutes(e.target.value)}
              disabled={isOptimizing}
            >
              <option value="10">10 Minutes</option>
              <option value="15">15 Minutes (Standard)</option>
              <option value="20">20 Minutes (Heavy Corridor)</option>
              <option value="30">30 Minutes (Maximum)</option>
            </select>
          </div>

          <div className="detail-item" style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16 }}>
            <input
              type="checkbox"
              id="forecast-check"
              checked={includeForecast}
              onChange={(e) => setIncludeForecast(e.target.checked)}
              disabled={isOptimizing}
              style={{ cursor: 'pointer', width: 16, height: 16 }}
            />
            <label htmlFor="forecast-check" style={{ fontSize: '0.8rem', color: '#f1f5f9', cursor: 'pointer' }}>
              Include Goods Train Forecast Headways
            </label>
          </div>
        </div>

        {isOptimizing && (
          <div className="optimization-stepper" style={{ marginTop: 20 }}>
            <div className={`step-item ${optimizationStep >= 1 ? (optimizationStep === 1 ? 'active' : 'done') : ''}`}>
              <div className="step-icon-circle">1</div>
              <span>Building candidate possession windows from timetable & corridors...</span>
            </div>
            <div className={`step-item ${optimizationStep >= 2 ? (optimizationStep === 2 ? 'active' : 'done') : ''}`}>
              <div className="step-icon-circle">2</div>
              <span>Running CP-SAT solver (constraints: track exclusive possession, machine capacity, safety headways)...</span>
            </div>
            <div className={`step-item ${optimizationStep >= 3 ? 'done' : ''}`}>
              <div className="step-icon-circle">3</div>
              <span>Synthesizing optimal schedule and calculating disruption metrics...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
