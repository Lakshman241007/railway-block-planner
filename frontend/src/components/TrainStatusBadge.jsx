import React from 'react';
import { getStatusBadgeClass } from '../types';

/**
 * TrainStatusBadge — renders the train's actual operational status from the
 * data model (train.status), never a fabricated value.
 *
 * Backend statuses: Running, Scheduled, Delayed, Terminated, Cancelled.
 * Uses the existing status badge palette so no new visual style is introduced.
 */
export default function TrainStatusBadge({ train }) {
  const statusStr = String((train && train.status) || 'Unknown');
  const badgeClass = getStatusBadgeClass(statusStr);

  return (
    <span className={`badge ${badgeClass}`}>
      <span className="dot" style={{ width: 5, height: 5 }} />
      {statusStr}
    </span>
  );
}
