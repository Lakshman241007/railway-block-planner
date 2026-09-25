import React from 'react';
import { useAuth } from '../auth/AuthContext';
import Tooltip from './Tooltip';

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
  onToggleMobileMenu,
  isMobileMenuOpen = false,
  onToggleSidebar,
  sidebarCollapsed = false,
}) {
  const { role, profile, isOperator, isEmployee, switchRole } = useAuth();

  return (
    <header className={`top-header ${isEmployee ? 'employee-top-header' : 'operator-top-header'}`}>
      {/* 1. LEFT ZONE: Hamburger, Collapse Toggle, Page Title & Role Badge */}
      <div className="header-left">
        {/* Mobile menu toggle hamburger */}
        <button
          type="button"
          className="btn-mobile-toggle"
          id="btn-mobile-menu-toggle"
          onClick={onToggleMobileMenu}
          title={isMobileMenuOpen ? "Close menu" : "Open navigation menu"}
          aria-label="Toggle navigation menu"
        >
          {isMobileMenuOpen ? '✕' : '☰'}
        </button>

        {/* Desktop Sidebar Collapse Toggle */}
        {onToggleSidebar && (
          <Tooltip label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <button
              type="button"
              className="btn btn-secondary btn-icon-only btn-xs btn-sidebar-collapse"
              onClick={onToggleSidebar}
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              style={{ width: 32, height: 32, flexShrink: 0 }}
            >
              {sidebarCollapsed ? '▶' : '◀'}
            </button>
          </Tooltip>
        )}

        <div className="header-title-group">
          <h2 className="header-page-title">{pageTitle}</h2>
          <span className={`header-page-tag ${isEmployee ? 'employee-tag' : ''}`}>
            {isEmployee ? 'EMPLOYEE DECK' : pageTag}
          </span>
        </div>
      </div>

      {/* 2. RIGHT ZONE: Date, Operational Status, Actions, Role Switcher & Operator Profile */}
      <div className="header-right">
        {/* Date Selector */}
        <div className="date-selector-pill">
          <span style={{ fontSize: '0.82rem', lineHeight: 1 }}>📅</span>
          <input
            type="date"
            className="date-input-mini"
            value={targetDate}
            onChange={(e) => onDateChange && onDateChange(e.target.value)}
            title="Select target planning date"
          />
        </div>

        {/* Operational / Offline Status */}
        <div className={`header-status-badge ${isOnline ? '' : 'offline'}`}>
          <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
          <span>{isOnline ? 'OPERATIONAL' : 'OFFLINE'}</span>
        </div>

        {/* Read-Only Badge for Employee */}
        {isEmployee && (
          <div className="header-readonly-badge" title="Employee view is strictly read-only">
            <span>👁️ READ-ONLY</span>
          </div>
        )}

        {/* Reset Demo Button (Operator) */}
        {isOperator && onResetBaseline && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={onResetBaseline}
            title="Reset operational data back to baseline unoptimized state"
            id="header-reset-baseline-btn"
          >
            🔄 RESET DEMO
          </button>
        )}

        {/* Run Optimization Button (Operator) */}
        {isOperator && onRunOptimization && (
          <button
            className="btn btn-primary btn-sm"
            onClick={onRunOptimization}
            disabled={isOptimizing || !isOnline}
            id="header-run-optimization-btn"
            style={{ fontWeight: 700 }}
          >
            {isOptimizing ? '⚡ SOLVING...' : '⚡ RUN OPTIMIZATION'}
          </button>
        )}

        {/* Utility / Refresh Button */}
        {onRefresh && (
          <Tooltip label="Refresh operational data feed">
            <button
              className="btn btn-secondary btn-icon-only btn-sm"
              onClick={onRefresh}
              aria-label="Refresh operational data feed"
              id="header-refresh-btn"
              style={{ width: 34, height: 34, padding: 0, flexShrink: 0 }}
            >
              🔄
            </button>
          </Tooltip>
        )}

        {/* Role Switcher Toggle */}
        <button
          className={`role-switcher-toggle ${isOperator ? 'to-employee' : 'to-operator'}`}
          onClick={switchRole}
          title={isOperator ? "Switch to Employee View" : "Switch to Operator View"}
          id="header-role-switch-btn"
        >
          <span className="role-switch-icon">⇄</span>
          <span>{isOperator ? 'Employee View' : 'Operator View'}</span>
        </button>

        {/* Operator Profile Chip */}
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
          <div className="operator-chip-text">
            <span className="operator-chip-name">{profile.name}</span>
            <span className="operator-chip-title" style={{ color: isEmployee ? '#34d399' : '#38bdf8' }}>
              {profile.title}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
