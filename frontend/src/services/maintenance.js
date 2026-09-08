/**
 * @module maintenance
 * @description SMMS Maintenance API Service — PATCH/GET wrappers for the
 *              /api/maintenance REST endpoints.
 * @author       Railway Block Planner Team
 * @lastModified 2026-09-07
 * @dependencies services/api.js → apiFetch
 */

import { apiFetch } from './api';

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

/**
 * Partially update a maintenance record by its integer database id.
 *
 * The ``id`` (integer primary key) is used rather than ``asset_id`` because
 * multiple records can share the same asset.  Only the fields you include in
 * {@link data} are written to the database; all others remain unchanged.
 *
 * @param {number} id - The integer primary-key id of the record to update.
 * @param {{ preferred_start?: string, duration_minutes?: number, priority?: string, status?: string }} data
 * @returns {Promise<{ data: object }>}
 */
export async function updateMaintenance(id, data) {
  return apiFetch(`/api/maintenance/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}
