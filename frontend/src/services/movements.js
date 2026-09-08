import { apiFetch } from './api';

/**
 * Train Movements & Section Occupancy API Service
 */

export async function getMovements({ train_id = null, section = null, skip = 0, limit = 200 } = {}) {
  const params = new URLSearchParams();
  if (train_id) params.append('train_id', train_id);
  if (section) params.append('section', section);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/movements?${params.toString()}`);
}

export async function getMovementsByTrain(trainId) {
  return apiFetch(`/api/movements/train/${encodeURIComponent(trainId)}`);
}

export async function getMovementsBySection(section) {
  return apiFetch(`/api/movements/section/${encodeURIComponent(section)}`);
}

export async function getMovementById(id) {
  return apiFetch(`/api/movements/${encodeURIComponent(id)}`);
}
