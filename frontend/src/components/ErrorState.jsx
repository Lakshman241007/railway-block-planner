import React from 'react';

/**
 * Standard error state: what failed, why (when known), and what can be done.
 * Uses only existing functionality (retry callback) — no invented actions.
 */
export default function ErrorState({
  title = 'Unable to load data',
  message = 'An error occurred while connecting to the Railway Block Planner API.',
  onRetry,
}) {
  return (
    <div className="state-panel error">
      <div className="state-icon">⚠</div>
      <div className="state-title">{title}</div>
      <div className="state-message">{message}</div>
      {onRetry && (
        <div className="state-actions">
          <button className="btn btn-secondary btn-sm" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
