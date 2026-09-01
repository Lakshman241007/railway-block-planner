import React from 'react';
import { getStatusBadgeClass } from '../types';

export default function StatusBadge({ status }) {
  const statusStr = String(status || 'Unknown');
  const badgeClass = getStatusBadgeClass(statusStr);

  return (
    <span className={`badge ${badgeClass}`}>
      <span className="dot" style={{ width: 5, height: 5 }} />
      {statusStr}
    </span>
  );
}
