import React from 'react';
import { useAuth } from '../auth/AuthContext';

export default function Header({
  pageTitle,
  pageTag = 'CONTROL ROOM',
  targetDate,
  onDateChange,
  isOnline = true,
  onRunOptimization,
  onResetBaseline,
  isOptimizing = false,
  onRefresh,
}) {
  const { role, profile, isOperator, isEmployee, switchRole } = useAuth();

  return (
    <header className={`top-header ${isEmployee ? 'employee-top-header' : 'operator-top-header'}`}>
      <div className="header-left">
        <h2 className="header-page-title">
          {pageTitle}
          <span className={`header-page-tag ${isEmployee ? 'employee-tag' : ''}`}>
            {isEmployee ? 'EMPLOYEE' : pageTag}
          </span>
        </h2>
      </div>

      <div className="header-right">
        {/* Date Selector */}
        <div className="date-selector-pill">
          <span>📅</span>
          <input
            type="date"
            className="date-input-mini"
            value={targetDate}
            onChange={(e) => onDateChange && onDateChange(e.target.value)}
            title="Select target planning/service date"
          />
        </div>

        {/* Read-Only Badge for Employee */}
        {isEmployee && (
          <div className="header-readonly-badge" title="Employee view is strictly read-only">
            <span className="readonly-icon">👁️</span>
            <span>READ-ONLY</span>
          </div>
        )}

        {/* System Online Status */}
        <div className={`header-status-badge ${isOnline ? '' : 'offline'}`}>
          <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
          {isOnline ? 'OPERATIONAL' : 'OFFLINE'}
        </div>

        {/* Operator Reset Baseline Button */}
        {isOperator && onResetBaseline && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={onResetBaseline}
            title="Reset operational data back to baseline unoptimized demo state (15 conflicts)"
            id="header-reset-baseline-btn"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
          >
            🔄 RESET DEMO
          </button>
        )}

        {/* Operator Optimization Button (Only shown to Operators) */}
        {isOperator && onRunOptimization && (
          <button
            className="btn btn-primary btn-sm"
            onClick={onRunOptimization}
            disabled={isOptimizing || !isOnline}
            id="header-run-optimization-btn"
          >
            {isOptimizing ? '⚡ SOLVING...' : '⚡ RUN OPTIMIZATION'}
          </button>
        )}

        {/* Refresh Button */}
        {onRefresh && (
          <button
            className="btn btn-secondary btn-icon-only btn-sm"
            onClick={onRefresh}
            title="Refresh operational data feed"
            id="header-refresh-btn"
          >
            🔄
          </button>
        )}

        {/* Role Switcher Pill */}
        <button
          className={`role-switcher-toggle ${isOperator ? 'to-employee' : 'to-operator'}`}
          onClick={switchRole}
          title={isOperator ? "Switch to Employee Read-Only View" : "Switch to Operator Control Center"}
          id="header-role-switch-btn"
        >
          <span className="role-switch-icon">⇄</span>
          <span>{isOperator ? 'Employee View' : 'Operator View'}</span>
        </button>

        {/* Profile Chip */}
        <div
          className={`operator-chip ${isEmployee ? 'employee-chip' : ''}`}
          title={`${profile.name} — ${profile.title} (${profile.station})`}
        >
          <div
            className="operator-avatar"
            style={{ background: isEmployee ? '#059669' : '#0284c7' }}
          >
            {profile.shortName}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
            <span style={{ fontWeight: 600, color: '#f8fafc' }}>{profile.name}</span>
            <span style={{ fontSize: '0.65rem', color: isEmployee ? '#34d399' : '#38bdf8' }}>
              {profile.title}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

