/**
 * @module blocks
 * @description BDMS Blocks API Service — PATCH/GET wrappers for the
 *              /api/blocks REST endpoints.
 * @author       Railway Block Planner Team
 * @lastModified 2026-09-07
 * @dependencies services/api.js → apiFetch
 */

import { apiFetch } from './api';

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

/**
 * Partially update a block disconnection record.
 *
 * Only the fields you include in {@link data} are written to the database;
 * all other fields remain unchanged.
 *
 * @param {string} blockId - The block_id of the record to update.
 * @param {{ requested_start?: string, requested_end?: string, priority?: string, status?: string, reason?: string }} data
 * @returns {Promise<{ data: object }>}
 */
export async function updateBlock(blockId, data) {
  return apiFetch(`/api/blocks/${encodeURIComponent(blockId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}
