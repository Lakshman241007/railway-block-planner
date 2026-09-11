import React from 'react';
import { useAuth } from '../../auth/AuthContext';
import { OPERATOR_ROUTES, navigateTo } from '../../router';

export default function OperatorSidebar({
  activePage,
  onNavigate,
  isOnline = true,
  conflictCount = 0,
  forecastCount = 0,
  pendingBlockCount = 0,
}) {
  const { switchRole } = useAuth();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '◉', path: OPERATOR_ROUTES.DASHBOARD },
    { id: 'schedule', label: 'Schedule', icon: '📅', path: OPERATOR_ROUTES.SCHEDULE },
    { id: 'blocks', label: 'Block Requests', icon: '🚧', path: OPERATOR_ROUTES.BLOCKS, badge: pendingBlockCount > 0 ? pendingBlockCount : null },
    { id: 'maintenance', label: 'Maintenance', icon: '🛠', path: OPERATOR_ROUTES.MAINTENANCE },
    { id: 'trains', label: 'Train Traffic', icon: '🚦', path: OPERATOR_ROUTES.TRAINS },
    { id: 'forecast', label: 'Goods Forecast', icon: '📈', path: OPERATOR_ROUTES.FORECAST, badge: forecastCount > 0 ? forecastCount : null },
    { id: 'optimization', label: 'Optimization', icon: '⚡', path: OPERATOR_ROUTES.OPTIMIZATION },
    { id: 'conflicts', label: 'Conflicts', icon: '⚠', path: OPERATOR_ROUTES.CONFLICTS, badge: conflictCount > 0 ? conflictCount : null, isAlert: true },
  ];

  const handleItemClick = (item) => {
    if (onNavigate) {
      onNavigate(item.id, item.path);
    } else {
      navigateTo(item.path);
    }
  };

  return (
    <aside className="sidebar operator-sidebar">
      <div className="sidebar-header">
        <div className="brand-icon" style={{ background: '#0284c7' }}>🚆</div>
        <div className="brand-info">
          <div className="brand-title">
            RAILWAY <span>PLANNER</span>
          </div>
          <div className="brand-subtitle" style={{ color: '#38bdf8' }}>
            Operator Control Center
          </div>
        </div>
      </div>

      <div className="sidebar-role-indicator operator-theme">
        <div className="role-indicator-badge">
          <span className="pulse-dot active" />
          <span>CHIEF CONTROLLER (FULL ACCESS)</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Operational Controls</div>
        {navItems.map((item) => (
          <button
            key={item.id}
            id={`operator-nav-${item.id}`}
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
          className="role-switch-sidebar-btn employee-alt"
          onClick={switchRole}
          title="Switch view to Employee Operations Monitor"
        >
          <span className="switch-icon">🔄</span>
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#e2e8f0' }}>Switch Role</div>
            <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>To Employee Monitor</div>
          </div>
        </button>

        <div className="system-status-box">
          <div className="status-row">
            <span className="status-indicator">
              <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
              Dispatch: {isOnline ? 'Online' : 'Offline'}
            </span>
            <span className="version-tag">OPERATOR</span>
          </div>
          <div className="status-row">
            <span className="status-indicator">
              <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
              OR-Tools CP-SAT
            </span>
            <span style={{ fontSize: '0.68rem', color: '#38bdf8' }}>Enabled</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
