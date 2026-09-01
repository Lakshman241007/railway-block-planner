import React from 'react';

export default function Header({
  pageTitle,
  pageTag = 'CONTROL ROOM',
  targetDate,
  onDateChange,
  isOnline = true,
  onRunOptimization,
  isOptimizing = false,
  onRefresh,
}) {
  return (
    <header className="top-header">
      <div className="header-left">
        <h2 className="header-page-title">
          {pageTitle}
          <span className="header-page-tag">{pageTag}</span>
        </h2>
      </div>

      <div className="header-right">
        <div className="date-selector-pill">
          <span>📅 Date:</span>
          <input
            type="date"
            className="date-input-mini"
            value={targetDate}
            onChange={(e) => onDateChange && onDateChange(e.target.value)}
          />
        </div>

        <div className={`header-status-badge ${isOnline ? '' : 'offline'}`}>
          <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
          {isOnline ? 'SYSTEM OPERATIONAL' : 'OFFLINE'}
        </div>

        {onRunOptimization && (
          <button
            className="btn btn-primary btn-sm"
            onClick={onRunOptimization}
            disabled={isOptimizing || !isOnline}
          >
            {isOptimizing ? '⚡ SOLVING...' : '⚡ RUN OPTIMIZATION'}
          </button>
        )}

        {onRefresh && (
          <button
            className="btn btn-secondary btn-icon-only btn-sm"
            onClick={onRefresh}
            title="Refresh live data"
          >
            🔄
          </button>
        )}

        <div className="operator-chip">
          <div className="operator-avatar">OP</div>
          <span>Chief Controller</span>
        </div>
      </div>
    </header>
  );
}
