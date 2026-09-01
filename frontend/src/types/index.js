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
