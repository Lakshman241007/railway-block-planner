/**
 * @module blocks
 * @description BDMS Blocks API Service — GET/POST/PATCH wrappers for the
 *              /api/blocks REST endpoints.
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
 * Submit a new block request to BDMS (POST /api/blocks).
 *
 * @param {Object} payload - Block request fields:
 *   block_id, location, block_type, requested_date,
 *   requested_start, requested_end, reason, priority
 * @returns {Promise<Object>} BlockValidationResponse from server
 */
export async function submitBlock(payload) {
  return apiFetch('/api/blocks', {
    method: 'POST',
    body: JSON.stringify({
      block_id: payload.block_id,
      location: payload.location,
      block_type: payload.block_type,
      requested_date: payload.requested_date,
      requested_start: payload.requested_start,
      requested_end: payload.requested_end,
      reason: payload.reason,
      priority: payload.priority,
      source: payload.source || 'BDMS-UI',
    }),
  });
}

/**
 * Partially update a block disconnection record.
 *
 * Only the fields you include in data are written to the database;
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
