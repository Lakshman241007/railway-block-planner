import { apiFetch } from './api';

/**
 * Timetable API Service
 */

export async function getTimetable({ train_id = null, service_date = null, skip = 0, limit = 200 } = {}) {
  const params = new URLSearchParams();
  if (train_id) params.append('train_id', train_id);
  if (service_date) params.append('service_date', service_date);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/timetable?${params.toString()}`);
}

export async function getTimetableByTrain(trainId) {
  return apiFetch(`/api/timetable/train/${encodeURIComponent(trainId)}`);
}

export async function getTimetableById(id) {
  return apiFetch(`/api/timetable/${encodeURIComponent(id)}`);
}
