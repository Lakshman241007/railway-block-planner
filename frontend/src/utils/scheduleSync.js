/**
 * @file scheduleSync.js
 * @description Synchronization utility for updating in-memory optimizer schedule
 * state when manual timetable edits are saved via BlockDetailModal.
 * Adheres to CS-001-REV-1.0 (RULE-01.1: <= 60 lines per function, RULE-03.2: header).
 */

import { parseTimeToMinutes } from '../types';

/**
 * Check whether a scheduled block matches the saved block by any identifier.
 *
 * @param {Object} b - Scheduled block from optimizationResult
 * @param {Object} savedBlock - Original block modified in modal
 * @returns {boolean} True if matching entity
 */
export function isBlockMatch(b, savedBlock) {
  if (!b || !savedBlock) return false;

  const targetIds = [
    savedBlock.block_id,
    savedBlock.request_id,
    savedBlock.asset_id,
    savedBlock.block_request_id,
    savedBlock.id != null ? String(savedBlock.id) : null,
  ].filter(Boolean);

  const blockIds = [
    b.block_id,
    b.request_id,
    b.asset_id,
    b.block_request_id,
    b.id != null ? String(b.id) : null,
  ].filter(Boolean);

  return targetIds.some((tid) => blockIds.includes(tid));
}

/**
 * Calculate duration in minutes between start and end time strings (HH:MM).
 *
 * @param {string} startTime - Start time (HH:MM)
 * @param {string} endTime - End time (HH:MM)
 * @param {number} fallbackDuration - Fallback duration in minutes
 * @returns {number} Duration in minutes
 */
export function calculateDuration(startTime, endTime, fallbackDuration = 120) {
  if (startTime && endTime) {
    const s = parseTimeToMinutes(startTime);
    const e = parseTimeToMinutes(endTime);
    let diff = e - s;
    if (diff <= 0) diff += 1440; // Overnight possession wrap
    return diff;
  }
  return fallbackDuration;
}

/**
 * Update an in-memory list of scheduled blocks with manual edits.
 *
 * @param {Array<Object>} scheduledBlocks - Existing scheduled blocks
 * @param {Object} savedBlock - Entity that was edited
 * @param {Object} editDraft - New field values from inspector form
 * @returns {{ updatedBlocks: Array<Object>, matched: boolean }}
 */
export function updateScheduledBlockList(scheduledBlocks, savedBlock, editDraft) {
  let matched = false;

  const updatedBlocks = (scheduledBlocks || []).map((b) => {
    if (!isBlockMatch(b, savedBlock)) return b;
    matched = true;

    const newStart = editDraft.requested_start || editDraft.preferred_start || b.start_time;
    const newEnd = editDraft.requested_end || b.end_time;
    const explicitDur = editDraft.duration_minutes
      ? parseInt(editDraft.duration_minutes, 10)
      : null;
    const durationMins = (explicitDur && !isNaN(explicitDur))
      ? explicitDur
      : calculateDuration(newStart, newEnd, b.duration_minutes);

    return {
      ...b,
      start_time: newStart,
      end_time: newEnd,
      duration_minutes: durationMins,
      priority: editDraft.priority || b.priority,
      status: editDraft.status || b.status,
      is_shifted: true,
      is_pinned: true,
      is_manual_edit: true,
    };
  });

  return { updatedBlocks, matched };
}
