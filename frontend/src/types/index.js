/**
 * Railway Block Planner Types & Operational Constants
 */

export const Priority = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

export const BlockStatus = {
  REQUESTED: 'Requested',
  APPROVED: 'Approved',
  SCHEDULED: 'Scheduled',
  REJECTED: 'Rejected',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
};

export const ConflictSeverity = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

export const CORRIDOR_DISCIPLINES = [
  { id: 'track', name: 'Track & Permanent Way', code: 'TRK', icon: '🛤️' },
  { id: 'signal', name: 'Signalling & Telecom', code: 'SIG', icon: '🚦' },
  { id: 'bridge', name: 'Bridge & Structures', code: 'BRG', icon: '🌉' },
  { id: 'ohe', name: 'Traction / OHE', code: 'OHE', icon: '⚡' },
  { id: 'points', name: 'Points & Crossings', code: 'PNT', icon: '🔀' },
  { id: 'level_crossing', name: 'Level Crossings', code: 'LC', icon: '🚧' },
];

export const CORRIDOR_SECTIONS = [
  'Chennai-Arakkonam',
  'Arakkonam-Renigunta',
  'Chennai-Villupuram',
  'Tambaram-Chengalpattu',
  'Villupuram-Chengalpattu',
  'Basin Bridge-Vyasarpadi',
  'KM40-42',
  'KM85-87',
];

export function getPriorityClass(priority) {
  const p = String(priority || '').toLowerCase();
  if (p === 'critical') return 'badge-critical';
  if (p === 'high') return 'badge-high';
  if (p === 'medium') return 'badge-medium';
  return 'badge-low';
}

export function getStatusBadgeClass(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'approved' || s === 'scheduled' || s === 'completed' || s === 'running') return 'badge-low';
  if (s === 'pending' || s === 'requested' || s === 'delayed') return 'badge-medium';
  if (s === 'cancelled' || s === 'rejected') return 'badge-critical';
  return 'badge-outline';
}

export function parseMinutesToTime(mins) {
  if (mins == null) return '--:--';
  const norm = ((mins % 1440) + 1440) % 1440;
  const h = Math.floor(norm / 60);
  const m = norm % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

export function parseTimeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const parts = String(timeStr).split(':');
  if (parts.length < 2) return 0;
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

/**
 * Infer corridor operational discipline from block attributes.
 * Checks discipline, equipment, request_id, asset_id, location, and reason.
 */
export function inferDiscipline(block) {
  if (!block) return 'track';
  if (block.discipline) {
    const d = String(block.discipline).toLowerCase();
    const valid = CORRIDOR_DISCIPLINES.find((cd) => cd.id === d);
    if (valid) return valid.id;
  }

  const text = `${block.equipment || ''} ${block.location || ''} ${block.request_id || ''} ${block.asset_id || ''} ${block.block_id || ''} ${block.block_type || ''} ${block.maintenance_type || ''} ${block.reason || ''}`.toLowerCase();

  if (text.includes('ohe') || text.includes('traction') || text.includes('overhead') || text.includes('power') || text.includes('electric') || text.includes('ohe-')) {
    return 'ohe';
  }
  if (text.includes('sig') || text.includes('telecom') || text.includes('signal') || text.includes('cable') || text.includes('sig-')) {
    return 'signal';
  }
  if (text.includes('bridge') || text.includes('girder') || text.includes('pamban') || text.includes('brg-')) {
    return 'bridge';
  }
  if ((text.includes('point') || text.includes('crossing') || text.includes('switch') || text.includes('pnt-')) &&
      !text.includes('level') && !text.includes('lc') && !text.includes('gate') && !text.includes('boom') && !text.includes('lvl')) {
    return 'points';
  }
  if (text.includes('lc') || text.includes('gate') || text.includes('boom') || text.includes('level') || text.includes('lvl') || text.includes('lc-') || text.includes('lvl-')) {
    return 'level_crossing';
  }
  return 'track';
}

/**
 * Shared canonical selector for scheduled / operational possessions.
 * Ensures Dashboard, Schedule, and Timeline derive identical records.
 */
export function getCanonicalPossessions({
  optimizationResult = null,
  blocks = [],
  targetDate,
  dateScope = 'DATE', // 'DATE' | 'HORIZON'
  priorityFilter = 'ALL',
  disciplineFilter = 'ALL',
}) {
  const isOptimized = Boolean(optimizationResult?.scheduled_blocks?.length);
  const rawList = isOptimized ? optimizationResult.scheduled_blocks : blocks;
  const horizonTotal = rawList.length;

  const dateTotal = rawList.filter((b) => {
    const bDate = b.service_date || b.requested_date;
    return bDate ? String(bDate) === String(targetDate) : true;
  }).length;

  const filtered = rawList.filter((b) => {
    // 1. Date filter (when scope is DATE)
    if (dateScope === 'DATE' && targetDate) {
      const bDate = b.service_date || b.requested_date;
      if (bDate && String(bDate) !== String(targetDate)) {
        return false;
      }
    }

    // 2. Priority filter
    if (priorityFilter && priorityFilter !== 'ALL') {
      const bPriority = String(b.priority || '').toLowerCase();
      if (bPriority !== priorityFilter.toLowerCase()) {
        return false;
      }
    }

    // 3. Discipline filter
    if (disciplineFilter && disciplineFilter !== 'ALL') {
      const disc = inferDiscipline(b);
      if (disc !== disciplineFilter.toLowerCase()) {
        return false;
      }
    }

    return true;
  });

  return {
    possessions: filtered,
    isOptimized,
    horizonTotal,
    dateTotal,
  };
}
