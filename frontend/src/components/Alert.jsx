import React from 'react';

const ICONS = {
  information: 'ℹ',
  warning: '▲',
  critical: '⛔',
};

/**
 * Inline alert with three levels: information, warning, critical.
 * Critical uses a left rail accent rather than a saturated fill, so a page
 * with several alerts doesn't read as visually aggressive.
 *
 *   <Alert level="critical" title="Signal conflict detected"
 *          message="Two trains are booked on Block B-14 for an overlapping window." />
 */
export default function Alert({
  level = 'information',
  title,
  message,
  actions,
  onDismiss,
}) {
  return (
    <div className={`alert alert-${level}`} role={level === 'critical' ? 'alert' : 'status'}>
      <span className="alert-icon">{ICONS[level] || ICONS.information}</span>
      <div className="alert-body">
        {title && <div className="alert-title">{title}</div>}
        {message && <div className="alert-message">{message}</div>}
        {actions && <div className="alert-actions">{actions}</div>}
      </div>
      {onDismiss && (
        <button type="button" className="alert-dismiss" onClick={onDismiss} aria-label="Dismiss">
          ✕
        </button>
      )}
    </div>
  );
}
