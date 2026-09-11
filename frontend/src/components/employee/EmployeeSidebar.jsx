import React from 'react';
import { useAuth } from '../../auth/AuthContext';
import { EMPLOYEE_ROUTES, navigateTo } from '../../router';

export default function EmployeeSidebar({
  activePage,
  onNavigate,
  isOnline = true,
  conflictCount = 0,
  forecastCount = 0,
}) {
  const { switchRole } = useAuth();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '◉', path: EMPLOYEE_ROUTES.DASHBOARD },
    { id: 'schedule', label: 'Schedule', icon: '📅', path: EMPLOYEE_ROUTES.SCHEDULE },
    { id: 'blocks', label: 'Block Status', icon: '🚧', path: EMPLOYEE_ROUTES.BLOCKS },
    { id: 'maintenance', label: 'Maintenance', icon: '🛠', path: EMPLOYEE_ROUTES.MAINTENANCE },
    { id: 'trains', label: 'Train Traffic', icon: '🚦', path: EMPLOYEE_ROUTES.TRAINS },
    { id: 'forecast', label: 'Goods Forecast', icon: '📈', path: EMPLOYEE_ROUTES.FORECAST, badge: forecastCount > 0 ? forecastCount : null },
    { id: 'plan-status', label: 'Plan Status', icon: '📊', path: EMPLOYEE_ROUTES.PLAN_STATUS },
    { id: 'conflicts', label: 'Conflicts', icon: '⚠', path: EMPLOYEE_ROUTES.CONFLICTS, badge: conflictCount > 0 ? conflictCount : null, isAlert: true },
  ];

  const handleItemClick = (item) => {
    if (onNavigate) {
      onNavigate(item.id, item.path);
    } else {
      navigateTo(item.path);
    }
  };

  return (
    <aside className="sidebar employee-sidebar">
      <div className="sidebar-header">
        <div className="brand-icon" style={{ background: '#059669' }}>🚆</div>
        <div className="brand-info">
          <div className="brand-title">
            RAILWAY <span>PLANNER</span>
          </div>
          <div className="brand-subtitle" style={{ color: '#34d399' }}>
            Employee Operations View
          </div>
        </div>
      </div>

      <div className="sidebar-role-indicator employee-theme">
        <div className="role-indicator-badge">
          <span className="read-only-badge-icon">👁️</span>
          <span>MONITORING ONLY (READ-ONLY)</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Operations Monitoring</div>
        {navItems.map((item) => (
          <button
            key={item.id}
            id={`employee-nav-${item.id}`}
            className={`nav-item ${activePage === item.id ? 'active' : ''}`}
            onClick={() => handleItemClick(item)}
          >
            <span className="nav-item-icon">{item.icon}</span>
            <span>{item.label}</span>
            {item.badge != null && (
              <span className={`nav-badge ${item.isAlert ? '' : 'info'}`}>{item.badge}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        {/* Role Switcher Button */}
        <button
          className="role-switch-sidebar-btn operator-alt"
          onClick={switchRole}
          title="Switch view to Operator Control Center"
        >
          <span className="switch-icon">🔄</span>
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#e2e8f0' }}>Switch Role</div>
            <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>To Operator Controls</div>
          </div>
        </button>

        <div className="system-status-box">
          <div className="status-row">
            <span className="status-indicator">
              <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
              Live Feed: {isOnline ? 'Online' : 'Offline'}
            </span>
            <span className="version-tag" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>
              EMPLOYEE
            </span>
          </div>
          <div className="status-row">
            <span className="status-indicator">
              <span className="dot online" />
              Permissions
            </span>
            <span style={{ fontSize: '0.68rem', color: '#10b981' }}>Strict Read-Only</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
