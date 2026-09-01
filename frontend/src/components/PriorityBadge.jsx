import React from 'react';
import { getPriorityClass } from '../types';

export default function PriorityBadge({ priority }) {
  const pStr = String(priority || 'Low');
  const badgeClass = getPriorityClass(pStr);

  return (
    <span className={`badge ${badgeClass}`}>
      {pStr.toUpperCase()}
    </span>
  );
}
