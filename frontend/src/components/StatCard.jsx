import React from 'react';

export default function StatCard({
  title,
  value,
  subtitle,
  icon,
  accent = 'cyan',
  badge,
  badgeType = 'info',
}) {
  const accentClass = `accent-${accent}`;

  return (
    <div className={`stat-card ${accentClass}`}>
      <div className="stat-card-header">
        <span>{title}</span>
        {icon && <span className="stat-card-icon">{icon}</span>}
      </div>

      <div className="stat-card-value">{value}</div>

      <div className="stat-card-footer">
        {badge && <span className={`badge ${badgeType === 'critical' ? 'badge-critical' : badgeType === 'success' ? 'badge-low' : 'badge-cyan'}`}>{badge}</span>}
        <span>{subtitle}</span>
      </div>
    </div>
  );
}
