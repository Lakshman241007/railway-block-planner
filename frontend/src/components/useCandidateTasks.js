/**
 * @file useCandidateTasks.js
 * @description Custom hook preparing normalized candidate maintenance tasks for re-optimization.
 * @module components/useCandidateTasks
 */

import { useMemo } from 'react';

export function useCandidateTasks(maintenance = [], blocks = [], optimizationResult = null) {
  return useMemo(() => {
    const list = [];
    const seen = new Set();
    const schedBlocks = optimizationResult?.scheduled_blocks || [];

    maintenance.forEach((m) => {
      if (m.maintenance_required && m.asset_id && !seen.has(m.asset_id)) {
        seen.add(m.asset_id);
        const match = schedBlocks.find((b) => b.request_id === m.asset_id || b.asset_id === m.asset_id);
        const startStr = m.preferred_start?.substring
          ? m.preferred_start.substring(0, 5)
          : String(m.preferred_start || '02:00');
        list.push({
          id: m.asset_id,
          location: m.location,
          basePriority: m.priority || 'Medium',
          preferredStart: startStr,
          duration: m.duration_minutes || 120,
          defaultSlot: match ? `${match.start_time}-${match.end_time}` : null,
        });
      }
    });

    blocks.forEach((b) => {
      if (b.block_id && !seen.has(b.block_id) && b.status !== 'Cancelled') {
        seen.add(b.block_id);
        const match = schedBlocks.find((sb) => sb.request_id === b.block_id || sb.block_request_id === b.block_id);
        list.push({
          id: b.block_id,
          location: b.location,
          basePriority: b.priority || 'Medium',
          preferredStart: b.requested_start || '02:00',
          duration: 120,
          defaultSlot: match ? `${match.start_time}-${match.end_time}` : `${b.requested_start}-${b.requested_end}`,
        });
      }
    });

    return list;
  }, [maintenance, blocks, optimizationResult]);
}
