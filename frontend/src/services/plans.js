import { apiFetch } from './api';

/**
 * Plans and CP-SAT Optimization API Service
 */

export async function getPlans(status = null, skip = 0, limit = 100) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/plans?${params.toString()}`);
}

export async function optimizePlan(payload = {}) {
  return apiFetch('/api/plans/optimize', {
    method: 'POST',
    body: JSON.stringify({
      target_date: payload.target_date || new Date().toISOString().split('T')[0],
      horizon_days: payload.horizon_days || 7,
      priority_filter: payload.priority_filter || null,
      location_filter: payload.location_filter || null,
      include_forecast: payload.include_forecast !== false,
      buffer_minutes: payload.buffer_minutes || 15,
      time_limit_seconds: payload.time_limit_seconds || 15.0,
      num_workers: payload.num_workers || 4,
    }),
  });
}

export async function generatePlan(payload = {}) {
  return apiFetch('/api/plans/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
