import { apiFetch } from './api';

/**
 * BDMS Blocks API Service
 */

export async function getBlocks({ date = null, location = null, status = null, skip = 0, limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (date) params.append('date', date);
  if (location) params.append('location', location);
  if (status) params.append('status', status);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/blocks?${params.toString()}`);
}

export async function getBlockById(blockId) {
  return apiFetch(`/api/blocks/${encodeURIComponent(blockId)}`);
}
