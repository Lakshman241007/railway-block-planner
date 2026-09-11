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

  const getBadgeClass = (type) => {
    switch (type) {
      case 'critical':
      case 'danger':
        return 'badge-critical';
      case 'warning':
      case 'high':
        return 'badge-high';
      case 'success':
        return 'badge-low';
      case 'info':
      default:
        return 'badge-cyan';
    }
  };

  return (
    <div className={`stat-card ${accentClass}`}>
      <div className="stat-card-header">
        <span>{title}</span>
        {icon && <span className="stat-card-icon">{icon}</span>}
      </div>

      <div className="stat-card-value">{value}</div>

      <div className="stat-card-footer">
        {badge && <span className={`badge ${getBadgeClass(badgeType)}`} style={{ flexShrink: 0 }}>{badge}</span>}
        <span
          title={subtitle}
          style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontSize: '0.72rem',
            color: '#8899ac',
          }}
        >
          {subtitle}
        </span>
      </div>
    </div>
  );
}
