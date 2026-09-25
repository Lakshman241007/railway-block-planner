import React from 'react';

/* ==========================================================================
   SIDEBAR / NAVIGATION SVG ICON SET
   Consistent 24x24 viewBox, 1.8px stroke, rendered at 18px — matches the
   stroke weight and optical alignment of the icons used in Header.jsx.
   ========================================================================== */

const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
};

export function IconDashboard({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}

export function IconSchedule({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <rect x="3" y="4" width="18" height="17" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
      <line x1="7" y1="14" x2="7" y2="14" />
      <line x1="12" y1="14" x2="12" y2="14" />
      <line x1="17" y1="14" x2="17" y2="14" />
    </svg>
  );
}

export function IconBlocks({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <path d="M12 2 3 7v10l9 5 9-5V7l-9-5z" />
      <path d="M3 7l9 5 9-5" />
      <line x1="12" y1="12" x2="12" y2="22" />
    </svg>
  );
}

export function IconMaintenance({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <path d="M14.7 6.3a4 4 0 1 1-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 1 5.4-5.4l-2.8 2.8-2-2 2.8-2.8z" />
    </svg>
  );
}

export function IconTrains({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <rect x="5" y="3" width="14" height="13" rx="4" />
      <line x1="5" y1="10" x2="19" y2="10" />
      <line x1="9" y1="16" x2="7" y2="21" />
      <line x1="15" y1="16" x2="17" y2="21" />
      <circle cx="9" cy="13" r="0.6" fill="currentColor" stroke="none" />
      <circle cx="15" cy="13" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconForecast({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <polyline points="3 17 9 11 13 15 21 6" />
      <polyline points="15 6 21 6 21 12" />
    </svg>
  );
}

export function IconOptimization({ className = '' }) {
  return (
    <svg className={className} {...base} fill="currentColor" stroke="none">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

export function IconConflicts({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <path d="M10.3 3.5 1.8 18a1.5 1.5 0 0 0 1.3 2.3h17.8a1.5 1.5 0 0 0 1.3-2.3L13.7 3.5a1.5 1.5 0 0 0-2.6 0z" />
      <line x1="12" y1="9.5" x2="12" y2="13.5" />
      <line x1="12" y1="16.7" x2="12" y2="16.7" />
    </svg>
  );
}

export function IconPlanStatus({ className = '' }) {
  return (
    <svg className={className} {...base}>
      <path d="M3 3v18h18" />
      <rect x="7" y="12" width="3" height="6" />
      <rect x="12.5" y="8" width="3" height="10" />
      <rect x="18" y="5" width="3" height="13" />
    </svg>
  );
}

export function IconTrainBrand({ className = '' }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="5" y="3" width="14" height="13" rx="4" />
      <line x1="5" y1="10" x2="19" y2="10" />
      <line x1="9" y1="16" x2="7" y2="21" />
      <line x1="15" y1="16" x2="17" y2="21" />
      <circle cx="9" cy="13" r="0.6" fill="currentColor" stroke="none" />
      <circle cx="15" cy="13" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconSwapRole({ className = '' }) {
  return (
    <svg className={className} width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7 7h12m0 0-4-4m4 4-4 4M17 17H5m0 0 4 4m-4-4 4-4" />
    </svg>
  );
}
