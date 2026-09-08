import { apiFetch } from './api';

/**
 * Plans and CP-SAT Optimization API Service (Phase 5)
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

/**
 * Retrieve the latest persisted optimized plan for a target date.
 * Returns null (not throws) if no plan exists for that date.
 *
 * @param {string} targetDate - YYYY-MM-DD format date string
 * @returns {Promise<Object|null>} { plan_meta, result } or null if not found
 */
export async function getLatestOptimizedPlan(targetDate) {
  try {
    const params = new URLSearchParams();
    if (targetDate) params.append('target_date', targetDate);
    return await apiFetch(`/api/plans/optimized/latest?${params.toString()}`);
  } catch (err) {
    // 404 means no plan exists for this date — not an error condition
    if (err?.status === 404 || (err?.message && err.message.includes('404'))) {
      return null;
    }
    throw err;
  }
}

/**
 * Retrieve a specific optimized plan by its plan_id.
 *
 * @param {string} planId - Unique plan identifier (e.g. OPT-PLAN-XXXXXXXX)
 * @returns {Promise<Object>} { plan_meta, result }
 */
export async function getOptimizedPlanById(planId) {
  return apiFetch(`/api/plans/optimized/${encodeURIComponent(planId)}`);
}

/**
 * List all persisted optimized plan summaries.
 *
 * @param {Object} opts - { targetDate, skip, limit }
 * @returns {Promise<Object>} { data, count, total }
 */
export async function listOptimizedPlans({ targetDate = null, skip = 0, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (targetDate) params.append('target_date', targetDate);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/plans/optimized?${params.toString()}`);
}
