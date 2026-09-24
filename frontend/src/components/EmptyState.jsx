import React from 'react';

/**
 * Standard empty state: tells the user what's empty, why it might be empty,
 * and what they can do next. Never renders a fake/no-op action — pass
 * `actionLabel` + `onAction` only when there is a real next step.
 */
export default function EmptyState({
  title = 'No records found',
  message = 'There are no active railway operations or maintenance items for this query.',
  actionLabel,
  onAction,
  icon = '📋',
}) {
  return (
    <div className="state-panel empty">
      <div className="state-icon">{icon}</div>
      <div className="state-title">{title}</div>
      <div className="state-message">{message}</div>
      {actionLabel && onAction && (
        <div className="state-actions">
          <button className="btn btn-secondary btn-sm" onClick={onAction}>
            {actionLabel}
          </button>
        </div>
      )}
    </div>
  );
}
