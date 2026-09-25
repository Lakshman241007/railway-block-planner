import React from 'react';

/**
 * Compact tooltip for icon-only controls and truncated values.
 * Wrap any trigger element (usually a .btn-icon-only) with this component.
 *
 *   <Tooltip label="Resolve conflict">
 *     <button className="btn btn-icon-only btn-ghost">✓</button>
 *   </Tooltip>
 */
export default function Tooltip({ label, children, position = 'top' }) {
  if (!label) return children;

  return (
    <span className="tooltip-wrap" tabIndex={-1}>
      {children}
      <span className={`tooltip-bubble${position === 'right' ? ' pos-right' : ''}`} role="tooltip">
        {label}
      </span>
    </span>
  );
}
