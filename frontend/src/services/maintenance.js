import { apiFetch } from './api';

/**
 * SMMS Maintenance API Service
 */

export async function getMaintenance({ priority = null, status = null, asset_id = null, skip = 0, limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (priority) params.append('priority', priority);
  if (status) params.append('status', status);
  if (asset_id) params.append('asset_id', asset_id);
  params.append('skip', skip);
  params.append('limit', limit);
  return apiFetch(`/api/maintenance?${params.toString()}`);
}

export async function getMaintenanceByAsset(assetId) {
  return apiFetch(`/api/maintenance/${encodeURIComponent(assetId)}`);
}
