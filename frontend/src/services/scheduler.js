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

/**
 * Generate a maintenance schedule for the given planning horizon.
 *
 * @param {object} opts
 * @param {string|null}  opts.target_date     - ISO date string (YYYY-MM-DD). Defaults to today.
 * @param {string}       opts.schedule_type   - 'daily' | 'weekly' | 'monthly'. Defaults to 'daily'.
 * @param {string|null}  opts.priority_filter - Filter by priority label (e.g. 'High').
 * @param {string|null}  opts.location_filter - Filter by corridor/section substring.
 * @param {number}       opts.buffer_minutes  - Safety headway buffer in minutes (0–60).
 */
export async function generateSchedule({
  target_date = null,
  schedule_type = 'daily',
  priority_filter = null,
  location_filter = null,
  buffer_minutes = 15,
} = {}) {
  return apiFetch('/api/scheduler/schedule', {
    method: 'POST',
    body: JSON.stringify({
      target_date,
      schedule_type,
      priority_filter,
      location_filter,
      buffer_minutes,
    }),
  });
}
