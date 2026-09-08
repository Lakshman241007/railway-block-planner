/**
 * @file plans.js
 * @description API service methods for Block Plans and CP-SAT Mathematical Optimization.
 * Includes Feature 3 re-optimization parameters: priority overrides, slot pinning, exclusions, and presets.
 * @module services/plans
 */

import { apiFetch } from './api';

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
      priority_overrides: payload.priority_overrides || null,
      pinned_slots: payload.pinned_slots || null,
      mandatory_request_ids: payload.mandatory_request_ids || null,
      exclude_from_reopt: payload.exclude_from_reopt || null,
      strategy_preset: payload.strategy_preset || 'balanced',
    }),
  });
}

export async function generatePlan(payload = {}) {
  return apiFetch('/api/plans/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
