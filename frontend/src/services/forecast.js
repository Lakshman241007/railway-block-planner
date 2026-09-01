import { apiFetch } from './api';

/**
 * Goods Train Forecasting API Service
 */

export async function getGoodsForecast({ target_date = null, horizon_hours = 24, train_id = null, section = null } = {}) {
  const params = new URLSearchParams();
  if (target_date) params.append('target_date', target_date);
  params.append('horizon_hours', horizon_hours);
  if (train_id) params.append('train_id', train_id);
  if (section) params.append('section', section);
  return apiFetch(`/api/forecast?${params.toString()}`);
}

export async function runGoodsForecast(payload) {
  return apiFetch('/api/forecast/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
