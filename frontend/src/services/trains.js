import { apiFetch } from './api';

/**
 * Trains & Timetables API Service
 */

export async function getTrains({ status = null, skip = 0, limit = 200 } = {}) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/trains?${params.toString()}`);
}

export async function getTrainById(trainId) {
  return apiFetch(`/api/trains/${encodeURIComponent(trainId)}`);
}
