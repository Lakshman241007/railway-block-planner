import React from 'react';

/**
 * KPI / metric card. `size` controls visual weight so important metrics can
 * be made to feel more important without inventing a separate component:
 *   - "featured": primary metric for the page (e.g. Active Conflicts)
 *   - "default":  standard KPI (unchanged from prior behavior)
 *   - "compact":  secondary/contextual metric
 */
export default function StatCard({
  title,
  value,
  subtitle,
  icon,
  accent = 'cyan',
  badge,
  badgeType = 'info',
  size = 'default',
  trend,
  trendDirection = 'flat',
}) {
  const accentClass = `accent-${accent}`;
  const sizeClass = size === 'featured' ? 'featured' : size === 'compact' ? 'compact' : '';

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

  const trendArrow = trendDirection === 'up' ? '▲' : trendDirection === 'down' ? '▼' : '·';

  return (
    <div className={`stat-card ${accentClass} ${sizeClass}`.trim()}>
      <div className="stat-card-header">
        <span>{title}</span>
        {icon && <span className="stat-card-icon">{icon}</span>}
      </div>

      <div className="stat-card-value">{value}</div>

      <div className="stat-card-footer">
        {badge && (
          <span className={`badge ${getBadgeClass(badgeType)}`} style={{ flexShrink: 0 }}>
            {badge}
          </span>
        )}
        {trend && (
          <span className={`stat-card-trend ${trendDirection}`} style={{ flexShrink: 0 }}>
            {trendArrow} {trend}
          </span>
        )}
        <span
          title={subtitle}
          style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {subtitle}
        </span>
      </div>
    </div>
  );
}
