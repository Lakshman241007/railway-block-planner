import React from 'react';

export default function Sidebar({ activePage, setActivePage, isOnline = true, conflictCount = 0, forecastCount = 0 }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '◉' },
    { id: 'schedule', label: 'Schedule', icon: '📅' },
    { id: 'optimization', label: 'Optimization', icon: '⚡' },
    { id: 'blocks', label: 'Block Requests', icon: '🚧' },
    { id: 'maintenance', label: 'Maintenance', icon: '🛠' },
    { id: 'trains', label: 'Train Traffic', icon: '🚦' },
    { id: 'forecast', label: 'Goods Forecast', icon: '📈', badge: forecastCount > 0 ? forecastCount : null },
    { id: 'conflicts', label: 'Conflicts', icon: '⚠', badge: conflictCount > 0 ? conflictCount : null, isAlert: true },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-icon">🚆</div>
        <div className="brand-info">
          <div className="brand-title">
            RAILWAY <span>PLANNER</span>
          </div>
          <div className="brand-subtitle">Operations & Possession Control</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Operational Navigation</div>
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activePage === item.id ? 'active' : ''}`}
            onClick={() => setActivePage(item.id)}
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
        <div className="system-status-box">
          <div className="status-row">
            <span className="status-indicator">
              <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
              Backend: {isOnline ? 'Online' : 'Offline'}
            </span>
            <span className="version-tag">v0.5.0</span>
          </div>
          <div className="status-row">
            <span className="status-indicator">
              <span className={`dot ${isOnline ? 'online' : 'offline'}`} />
              DB: Connected
            </span>
            <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>CP-SAT Active</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
