import React from 'react';

/**
 * Calm, professional loading indicator. Use the default spinner for page/
 * panel loads; pass `variant="skeleton"` with `rows` for a list/table that
 * is about to populate, so the layout doesn't jump once data arrives.
 */
export default function LoadingState({
  message = 'Loading operational telemetry…',
  variant = 'spinner',
  rows = 4,
}) {
  if (variant === 'skeleton') {
    return (
      <div className="state-panel loading" style={{ alignItems: 'stretch', gap: 'var(--space-sm)' }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div className="skeleton-row" key={i} />
        ))}
      </div>
    );
  }

  return (
    <div className="state-panel loading">
      <div className="radar-spinner" />
      <div className="state-loading-label">{message}</div>
    </div>
  );
}
