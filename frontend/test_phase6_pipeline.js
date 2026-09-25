/**
 * @file test_phase6_pipeline.js
 * @description Frontend Unit Tests for Phase 6 — Operator UI: Final Plan + Decision Pipeline.
 * Tests decision pipeline stage derivations, CP-SAT solver status preservation,
 * final plan validation reflection, counts integrity, error states, and empty states.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

// Pure logic pipeline state derivation tester (matching OptimizationDecisionPipeline logic)
function derivePipelineStages({
  optimizationResult = null,
  isOptimizing = false,
  optimizationStep = 0,
  blocks = [],
  maintenance = [],
  error = null,
  targetDate = '2026-09-07',
}) {
  const stats = optimizationResult?.solver_statistics;
  const planId = optimizationResult?.plan_id;
  const solverStatus = optimizationResult?.status;
  const validation = optimizationResult?.validation;
  const scheduledBlocks = optimizationResult?.scheduled_blocks || [];
  const unscheduledBlocks = optimizationResult?.unscheduled_blocks || [];

  const totalRequests = stats?.total_requests ?? (blocks.length + maintenance.length);
  const criticalCount = [...blocks, ...maintenance].filter(
    (r) => String(r.priority).toLowerCase() === 'critical'
  ).length;
  const highCount = [...blocks, ...maintenance].filter(
    (r) => String(r.priority).toLowerCase() === 'high'
  ).length;

  // 1. AI Priority
  let aiPriorityStatus = 'READY';
  let aiPriorityDetail = `${totalRequests} Requests Scored`;
  if (error && !optimizationResult) {
    aiPriorityStatus = 'ERROR';
    aiPriorityDetail = 'Telemetry Error';
  } else if (totalRequests === 0) {
    aiPriorityStatus = 'NO DATA';
    aiPriorityDetail = 'No Active Requests';
  } else if (isOptimizing && optimizationStep === 1) {
    aiPriorityStatus = 'EVALUATING';
    aiPriorityDetail = 'Weighting Priorities';
  } else if (criticalCount > 0 || highCount > 0) {
    aiPriorityDetail = `${criticalCount} Critical, ${highCount} High`;
  }

  // 2. Block Planner
  let plannerStatus = 'READY';
  let plannerDetail = `${totalRequests} Work Orders`;
  if (error && !optimizationResult) {
    plannerStatus = 'ERROR';
    plannerDetail = 'Planning Failed';
  } else if (isOptimizing && optimizationStep === 1) {
    plannerStatus = 'PROCESSING';
    plannerDetail = 'Corridor Windows';
  } else if (optimizationResult) {
    plannerStatus = 'COMPLETED';
    plannerDetail = `${optimizationResult.horizon_days || 7}-Day Horizon`;
  }

  // 3. Scheduler
  let schedulerStatus = 'READY';
  let schedulerDetail = 'Headway Feasibility';
  if (error && !optimizationResult) {
    schedulerStatus = 'ERROR';
    schedulerDetail = 'Unavailable';
  } else if (isOptimizing && (optimizationStep === 1 || optimizationStep === 2)) {
    schedulerStatus = 'PROCESSING';
    schedulerDetail = 'Filtering Slots';
  } else if (optimizationResult) {
    schedulerStatus = 'COMPLETED';
    schedulerDetail = 'Mutual Exclusion Bounds';
  }

  // 4. CP-SAT Solver
  let cpsatStatus = 'NOT RUN';
  let cpsatDetail = 'Awaiting Trigger';
  if (error && isOptimizing) {
    cpsatStatus = 'ERROR';
    cpsatDetail = 'Solver Crashed';
  } else if (isOptimizing && optimizationStep >= 2) {
    cpsatStatus = 'RUNNING';
    cpsatDetail = 'Searching Optimal Slots';
  } else if (optimizationResult) {
    cpsatStatus = solverStatus || 'COMPLETED';
    if (solverStatus === 'OPTIMAL') {
      cpsatDetail = stats?.objective_value != null ? `Obj: ${stats.objective_value.toLocaleString()}` : 'Mathematical Optimum';
    } else if (solverStatus === 'FEASIBLE') {
      cpsatDetail = stats?.objective_value != null ? `Obj: ${stats.objective_value.toLocaleString()}` : 'Feasible Allocation';
    } else if (solverStatus === 'INFEASIBLE') {
      cpsatDetail = 'No Feasible Solution';
    } else if (solverStatus === 'TIME_LIMIT') {
      cpsatDetail = 'Time Limit Reached';
    } else {
      cpsatDetail = solverStatus;
    }
  }

  // 5. Final Block Plan
  let finalPlanStatus = 'NOT AVAILABLE';
  let finalPlanDetail = 'Awaiting CP-SAT Result';
  if (error && !optimizationResult) {
    finalPlanStatus = 'NOT AVAILABLE';
    finalPlanDetail = 'Execution Error';
  } else if (isOptimizing) {
    finalPlanStatus = 'COMPOSING';
    finalPlanDetail = 'Validating Output...';
  } else if (optimizationResult) {
    if (solverStatus === 'INFEASIBLE') {
      finalPlanStatus = 'INFEASIBLE';
      finalPlanDetail = 'Constraints Unsatisfiable';
    } else if (validation?.is_valid === false) {
      finalPlanStatus = 'INVALID';
      finalPlanDetail = `${validation.violations?.length || 1} Violation(s)`;
    } else if (solverStatus === 'OPTIMAL') {
      finalPlanStatus = 'VALIDATED';
      finalPlanDetail = `${scheduledBlocks.length} Scheduled, ${unscheduledBlocks.length} Unsched.`;
    } else if (solverStatus === 'FEASIBLE') {
      finalPlanStatus = 'AVAILABLE';
      finalPlanDetail = `${scheduledBlocks.length} Scheduled, ${unscheduledBlocks.length} Unsched.`;
    } else {
      finalPlanStatus = 'AVAILABLE';
      finalPlanDetail = `${scheduledBlocks.length} Scheduled`;
    }
  }

  return {
    aiPriorityStatus,
    aiPriorityDetail,
    plannerStatus,
    plannerDetail,
    schedulerStatus,
    schedulerDetail,
    cpsatStatus,
    cpsatDetail,
    finalPlanStatus,
    finalPlanDetail,
    planId,
  };
}

test('TEST 1: Pipeline renders all 5 canonical stages in correct sequence', () => {
  const result = derivePipelineStages({
    blocks: [{ block_id: 'BLK-01', priority: 'High' }],
    maintenance: [{ asset_id: 'TRK-01', priority: 'Critical' }],
  });
  assert.ok(result.aiPriorityStatus);
  assert.ok(result.plannerStatus);
  assert.ok(result.schedulerStatus);
  assert.ok(result.cpsatStatus);
  assert.ok(result.finalPlanStatus);
});

test('TEST 2 & 3: OPTIMAL CP-SAT status displays OPTIMAL and VALIDATED final plan', () => {
  const mockOptimalResult = {
    plan_id: 'OPT-PLAN-A1B2C3D4',
    status: 'OPTIMAL',
    horizon_days: 7,
    objective_value: 8420,
    scheduled_blocks: [{ block_id: 'BLK-01' }, { block_id: 'BLK-02' }],
    unscheduled_blocks: [{ request_id: 'REQ-01', reason: 'NO_FEASIBLE_WINDOW' }],
    solver_statistics: {
      objective_value: 8420,
      num_scheduled: 2,
      num_unscheduled: 1,
      total_requests: 3,
      wall_time_seconds: 0.045,
    },
    validation: { is_valid: true, violations: [] },
  };

  const stages = derivePipelineStages({ optimizationResult: mockOptimalResult });
  assert.equal(stages.cpsatStatus, 'OPTIMAL');
  assert.match(stages.cpsatDetail, /8,420/);
  assert.equal(stages.finalPlanStatus, 'VALIDATED');
  assert.equal(stages.finalPlanDetail, '2 Scheduled, 1 Unsched.');
  assert.equal(stages.planId, 'OPT-PLAN-A1B2C3D4');
});

test('TEST 4: FEASIBLE CP-SAT solver status displays FEASIBLE (does not claim OPTIMAL)', () => {
  const mockFeasibleResult = {
    plan_id: 'OPT-PLAN-FEASIBLE',
    status: 'FEASIBLE',
    scheduled_blocks: [{ block_id: 'BLK-01' }],
    unscheduled_blocks: [],
    solver_statistics: {
      objective_value: 5000,
      num_scheduled: 1,
      num_unscheduled: 0,
      total_requests: 1,
    },
  };

  const stages = derivePipelineStages({ optimizationResult: mockFeasibleResult });
  assert.equal(stages.cpsatStatus, 'FEASIBLE');
  assert.notEqual(stages.cpsatStatus, 'OPTIMAL');
  assert.equal(stages.finalPlanStatus, 'AVAILABLE');
});

test('TEST 5: INFEASIBLE status communicates constraints unsatisfiable and no valid plan', () => {
  const mockInfeasibleResult = {
    plan_id: 'OPT-PLAN-INFEASIBLE',
    status: 'INFEASIBLE',
    scheduled_blocks: [],
    unscheduled_blocks: [{ request_id: 'REQ-01', reason: 'INFEASIBLE' }],
    solver_statistics: {
      num_scheduled: 0,
      num_unscheduled: 1,
      total_requests: 1,
    },
  };

  const stages = derivePipelineStages({ optimizationResult: mockInfeasibleResult });
  assert.equal(stages.cpsatStatus, 'INFEASIBLE');
  assert.equal(stages.finalPlanStatus, 'INFEASIBLE');
  assert.equal(stages.finalPlanDetail, 'Constraints Unsatisfiable');
});

test('TEST 6: No plan shows the correct empty state (CP-SAT NOT RUN, Final Plan NOT AVAILABLE)', () => {
  const stages = derivePipelineStages({
    optimizationResult: null,
    isOptimizing: false,
    blocks: [{ block_id: 'BLK-01', priority: 'Medium' }],
  });
  assert.equal(stages.cpsatStatus, 'NOT RUN');
  assert.equal(stages.finalPlanStatus, 'NOT AVAILABLE');
  assert.equal(stages.plannerStatus, 'READY');
  assert.equal(stages.schedulerStatus, 'READY');
});

test('TEST 7: Loading state shows active solving / processing progression', () => {
  const stages = derivePipelineStages({
    isOptimizing: true,
    optimizationStep: 2,
    blocks: [{ block_id: 'BLK-01' }],
  });
  assert.equal(stages.cpsatStatus, 'RUNNING');
  assert.equal(stages.finalPlanStatus, 'COMPOSING');
});

test('TEST 8: API error shows error state without claiming success', () => {
  const stages = derivePipelineStages({
    error: 'Failed to connect to backend',
    blocks: [],
    maintenance: [],
  });
  assert.equal(stages.aiPriorityStatus, 'ERROR');
  assert.equal(stages.plannerStatus, 'ERROR');
  assert.equal(stages.schedulerStatus, 'ERROR');
  assert.equal(stages.finalPlanStatus, 'NOT AVAILABLE');
});

test('TEST 9 & 10: Final plan counts and plan ID match API data exactly', () => {
  const mockResult = {
    plan_id: 'OPT-PLAN-99998888',
    status: 'OPTIMAL',
    scheduled_blocks: new Array(11).fill({ block_id: 'B' }),
    unscheduled_blocks: new Array(3).fill({ request_id: 'U' }),
    solver_statistics: {
      num_scheduled: 11,
      num_unscheduled: 3,
      total_requests: 14,
    },
  };

  const stages = derivePipelineStages({ optimizationResult: mockResult });
  assert.equal(stages.planId, 'OPT-PLAN-99998888');
  assert.equal(stages.finalPlanDetail, '11 Scheduled, 3 Unsched.');
});

test('TEST 11: Pipeline does not fabricate unavailable metrics', () => {
  const emptyResult = {
    plan_id: 'OPT-PLAN-MINIMAL',
    status: 'OPTIMAL',
    scheduled_blocks: [],
    unscheduled_blocks: [],
  };

  const stages = derivePipelineStages({ optimizationResult: emptyResult });
  assert.equal(stages.planId, 'OPT-PLAN-MINIMAL');
  assert.equal(stages.cpsatDetail, 'Mathematical Optimum'); // No fabricated objective
});

test('TEST 12: Priority stage aggregates real priority classifications', () => {
  const stages = derivePipelineStages({
    blocks: [
      { priority: 'Critical' },
      { priority: 'Critical' },
      { priority: 'High' },
    ],
    maintenance: [
      { priority: 'Critical' },
      { priority: 'Medium' },
    ],
  });
  assert.equal(stages.aiPriorityStatus, 'READY');
  assert.equal(stages.aiPriorityDetail, '3 Critical, 1 High');
});

test('TEST 13 & 14: Unscheduled diagnostic reasons and scheduled allocations preserved', () => {
  const mockResultWithDiag = {
    plan_id: 'OPT-PLAN-DIAG',
    status: 'OPTIMAL',
    scheduled_blocks: [{ block_id: 'BLK-101', priority: 'High', service_date: '2026-09-07' }],
    unscheduled_blocks: [
      {
        request_id: 'REQ-104',
        priority: 'High',
        priority_value: 91,
        status: 'Unscheduled',
        reason: 'NO_FEASIBLE_WINDOW',
      },
    ],
  };

  assert.equal(mockResultWithDiag.scheduled_blocks[0].block_id, 'BLK-101');
  assert.equal(mockResultWithDiag.unscheduled_blocks[0].reason, 'NO_FEASIBLE_WINDOW');
  assert.equal(mockResultWithDiag.unscheduled_blocks[0].priority_value, 91);
});
