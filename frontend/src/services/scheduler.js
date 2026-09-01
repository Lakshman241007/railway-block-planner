import { apiFetch } from './api';

/**
 * Scheduler & Conflict Detection API Service
 */

export async function getFeasibleSlots({ location, duration_minutes, preferred_start = '10:00', target_date = null, buffer_minutes = 15 }) {
  return apiFetch('/api/scheduler/feasible-slots', {
    method: 'POST',
    body: JSON.stringify({
      location,
      duration_minutes,
      preferred_start,
      target_date,
      buffer_minutes,
    }),
  });
}

export async function detectConflicts(target_date = null, buffer_minutes = 15) {
  const params = new URLSearchParams();
  if (target_date) params.append('target_date', target_date);
  params.append('buffer_minutes', buffer_minutes);
  return apiFetch(`/api/scheduler/conflicts?${params.toString()}`, {
    method: 'POST',
  });
}

export async function generateSchedule({ target_date = null, priority_filter = null, location_filter = null, buffer_minutes = 15 } = {}) {
  return apiFetch('/api/scheduler/schedule', {
    method: 'POST',
    body: JSON.stringify({
      target_date,
      priority_filter,
      location_filter,
      buffer_minutes,
    }),
  });
}
