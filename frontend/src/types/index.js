/**
 * Railway Block Planner Types & Operational Constants
 */

export const Priority = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

/**
 * Schedule type values — must match backend Literal["daily","weekly","monthly"].
 * Always use these constants when calling generateSchedule().
 */
export const ScheduleType = {
  DAILY: 'daily',
  WEEKLY: 'weekly',
  MONTHLY: 'monthly',
};

export const BlockStatus = {
  REQUESTED: 'Requested',
  APPROVED: 'Approved',
  SCHEDULED: 'Scheduled',
  REJECTED: 'Rejected',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
};

export const ConflictSeverity = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

export const ConflictReviewStatus = {
  DETECTED: 'DETECTED',
  AUTO_RESOLVED: 'AUTO_RESOLVED',
  REQUIRES_HUMAN_REVIEW: 'REQUIRES_HUMAN_REVIEW',
  HUMAN_RESOLVED: 'HUMAN_RESOLVED',
  REJECTED: 'REJECTED',
  DEFERRED: 'DEFERRED',
};

export const PlanApprovalStatus = {
  DRAFT: 'DRAFT',
  OPTIMIZED: 'OPTIMIZED',
  UNDER_REVIEW: 'UNDER_REVIEW',
  APPROVED: 'APPROVED',
  PUBLISHED: 'PUBLISHED',
  REJECTED: 'REJECTED',
};

export function getConflictReviewBadgeClass(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'AUTO_RESOLVED' || s === 'HUMAN_RESOLVED' || s === 'RESOLVED') return 'badge-low';
  if (s === 'REQUIRES_HUMAN_REVIEW' || s === 'UNDER_REVIEW') return 'badge-critical';
  if (s === 'DETECTED' || s === 'DEFERRED') return 'badge-medium';
  if (s === 'REJECTED') return 'badge-critical';
  return 'badge-outline';
}

export function getPlanApprovalBadgeClass(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'PUBLISHED') return 'badge-low';
  if (s === 'APPROVED') return 'badge-high';
  if (s === 'UNDER_REVIEW' || s === 'OPTIMIZED') return 'badge-medium';
  if (s === 'REJECTED') return 'badge-critical';
  return 'badge-outline';
}

export const CORRIDOR_DISCIPLINES = [
  { id: 'track', name: 'Track & Permanent Way', code: 'TRK', icon: '🛤️' },
  { id: 'signal', name: 'Signalling & Telecom', code: 'SIG', icon: '🚦' },
  { id: 'bridge', name: 'Bridge & Structures', code: 'BRG', icon: '🌉' },
  { id: 'ohe', name: 'Traction / OHE', code: 'OHE', icon: '⚡' },
  { id: 'points', name: 'Points & Crossings', code: 'PNT', icon: '🔀' },
  { id: 'level_crossing', name: 'Level Crossings', code: 'LC', icon: '🚧' },
];

export const CORRIDOR_SECTIONS = [
  'Chennai-Arakkonam',
  'Arakkonam-Renigunta',
  'Chennai-Villupuram',
  'Tambaram-Chengalpattu',
  'Villupuram-Chengalpattu',
  'Basin Bridge-Vyasarpadi',
  'KM40-42',
  'KM85-87',
];

export function getPriorityClass(priority) {
  const p = String(priority || '').toLowerCase();
  if (p === 'critical') return 'badge-critical';
  if (p === 'high') return 'badge-high';
  if (p === 'medium') return 'badge-medium';
  return 'badge-low';
}

export function getStatusBadgeClass(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'approved' || s === 'scheduled' || s === 'completed' || s === 'running') return 'badge-low';
  if (s === 'pending' || s === 'requested' || s === 'delayed') return 'badge-medium';
  if (s === 'cancelled' || s === 'rejected') return 'badge-critical';
  return 'badge-outline';
}

export function parseMinutesToTime(mins) {
  if (mins == null) return '--:--';
  const norm = ((mins % 1440) + 1440) % 1440;
  const h = Math.floor(norm / 60);
  const m = norm % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

export function parseTimeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const parts = String(timeStr).split(':');
  if (parts.length < 2) return 0;
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

/**
 * Infer corridor operational discipline from block attributes.
 * Checks discipline, equipment, request_id, asset_id, location, and reason.
 */
export function inferDiscipline(block) {
  if (!block) return 'track';
  if (block.discipline) {
    const d = String(block.discipline).toLowerCase();
    const valid = CORRIDOR_DISCIPLINES.find((cd) => cd.id === d);
    if (valid) return valid.id;
  }

  const text = `${block.equipment || ''} ${block.location || ''} ${block.request_id || ''} ${block.asset_id || ''} ${block.block_id || ''} ${block.block_type || ''} ${block.maintenance_type || ''} ${block.reason || ''}`.toLowerCase();

  if (text.includes('ohe') || text.includes('traction') || text.includes('overhead') || text.includes('power') || text.includes('electric') || text.includes('ohe-')) {
    return 'ohe';
  }
  if (text.includes('sig') || text.includes('telecom') || text.includes('signal') || text.includes('cable') || text.includes('sig-')) {
    return 'signal';
  }
  if (text.includes('bridge') || text.includes('girder') || text.includes('pamban') || text.includes('brg-')) {
    return 'bridge';
  }
  if ((text.includes('point') || text.includes('crossing') || text.includes('switch') || text.includes('pnt-')) &&
      !text.includes('level') && !text.includes('lc') && !text.includes('gate') && !text.includes('boom') && !text.includes('lvl')) {
    return 'points';
  }
  if (text.includes('lc') || text.includes('gate') || text.includes('boom') || text.includes('level') || text.includes('lvl') || text.includes('lc-') || text.includes('lvl-')) {
    return 'level_crossing';
  }
  return 'track';
}

/**
 * Shared canonical selector for scheduled / operational possessions.
 * Ensures Dashboard, Schedule, and Timeline derive identical records.
 */
export function getCanonicalPossessions({
  optimizationResult = null,
  blocks = [],
  targetDate,
  dateScope = 'DATE', // 'DATE' | 'HORIZON'
  priorityFilter = 'ALL',
  disciplineFilter = 'ALL',
}) {
  const isOptimized = Boolean(optimizationResult?.scheduled_blocks?.length);
  const rawList = isOptimized ? optimizationResult.scheduled_blocks : blocks;
  const horizonTotal = rawList.length;

  const dateTotal = rawList.filter((b) => {
    const bDate = b.service_date || b.requested_date;
    return bDate ? String(bDate) === String(targetDate) : true;
  }).length;

  const filtered = rawList.filter((b) => {
    // 1. Date filter (when scope is DATE)
    if (dateScope === 'DATE' && targetDate) {
      const bDate = b.service_date || b.requested_date;
      if (bDate && String(bDate) !== String(targetDate)) {
        return false;
      }
    }

    // 2. Priority filter
    if (priorityFilter && priorityFilter !== 'ALL') {
      const bPriority = String(b.priority || '').toLowerCase();
      if (bPriority !== priorityFilter.toLowerCase()) {
        return false;
      }
    }

    // 3. Discipline filter
    if (disciplineFilter && disciplineFilter !== 'ALL') {
      const disc = inferDiscipline(b);
      if (disc !== disciplineFilter.toLowerCase()) {
        return false;
      }
    }

    return true;
  });

  return {
    possessions: filtered,
    isOptimized,
    horizonTotal,
    dateTotal,
  };
}

/**
 * Extract canonical priority assessment and AI explainability enrichment
 * from a maintenance record, block request, or scheduled allocation.
 *
 * @param {Object} record - Maintenance, block, or possession record
 * @returns {Object} Extracted priority factors, priorityValue, and AI explanation
 */
export function extractPriorityEnrichment(record) {
  if (!record) {
    return {
      priorityValue: null,
      urgency: null,
      criticality: null,
      overdueFactor: null,
      assetAvailabilityImpact: null,
      operationalImpact: null,
      explanation: null,
      hasPriorityData: false,
    };
  }

  const pe = record.priority_enrichment || {};
  const meta = pe.metadata || {};

  const priorityValue =
    record.priority_value != null
      ? record.priority_value
      : pe.priority_value != null
      ? pe.priority_value
      : null;

  const urgency =
    pe.urgency != null
      ? pe.urgency
      : record.urgency != null
      ? record.urgency
      : null;

  const criticality =
    pe.criticality != null
      ? pe.criticality
      : record.criticality != null
      ? record.criticality
      : null;

  const overdueFactor =
    pe.overdue_factor != null
      ? pe.overdue_factor
      : record.overdue_factor != null
      ? record.overdue_factor
      : null;

  const assetAvailabilityImpact =
    pe.asset_availability_impact != null
      ? pe.asset_availability_impact
      : meta.asset_availability_impact != null
      ? meta.asset_availability_impact
      : record.asset_availability_impact != null
      ? record.asset_availability_impact
      : null;

  const operationalImpact =
    pe.operational_impact != null
      ? pe.operational_impact
      : meta.operational_impact != null
      ? meta.operational_impact
      : record.operational_impact != null
      ? record.operational_impact
      : null;

  const explanation =
    pe.explanation ||
    pe.ai_explanation ||
    meta.explanation ||
    meta.ai_explanation ||
    record.ai_explanation ||
    record.explanation ||
    null;

  const hasPriorityData =
    priorityValue != null ||
    urgency != null ||
    criticality != null ||
    overdueFactor != null ||
    assetAvailabilityImpact != null ||
    operationalImpact != null ||
    explanation != null;

  return {
    priorityValue,
    urgency,
    criticality,
    overdueFactor,
    assetAvailabilityImpact,
    operationalImpact,
    explanation,
    hasPriorityData,
  };
}

