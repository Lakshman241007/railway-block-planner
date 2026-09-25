/**
 * @file OptimizationDecisionPipeline.jsx
 * @description Phase 6 — Decision Pipeline for the Pro-Max Operator Control Center.
 * Renders the real-time operational optimization pipeline:
 *   AI Priority → Block Planner → Scheduler → CP-SAT → Final Block Plan
 * Every stage reflects actual backend telemetry, solver status, and persisted plan validation.
 * @module components/OptimizationDecisionPipeline
 */

import React from 'react';
import StatusBadge from './StatusBadge';
import PriorityBadge from './PriorityBadge';

export default function OptimizationDecisionPipeline({
  optimizationResult = null,
  isOptimizing = false,
  optimizationStep = 0, // 0: idle, 1: building/planning, 2: solving, 3: completed
  targetDate,
  blocks = [],
  maintenance = [],
  error = null,
  onSelectStage,
  onSelectBlock,
}) {
  const stats = optimizationResult?.solver_statistics;
  const planId = optimizationResult?.plan_id;
  const solverStatus = optimizationResult?.status;
  const validation = optimizationResult?.validation;
  const scheduledBlocks = optimizationResult?.scheduled_blocks || [];
  const unscheduledBlocks = optimizationResult?.unscheduled_blocks || [];

  // Compute live request telemetry
  const totalRequests = stats?.total_requests ?? (blocks.length + maintenance.length);
  const criticalCount = [...blocks, ...maintenance].filter(
    (r) => String(r.priority).toLowerCase() === 'critical'
  ).length;
  const highCount = [...blocks, ...maintenance].filter(
    (r) => String(r.priority).toLowerCase() === 'high'
  ).length;

  // Derive stage 1: AI PRIORITY
  let aiPriorityStatus = 'READY';
  let aiPriorityBadgeType = 'info';
  let aiPriorityDetail = `${totalRequests} Requests Scored`;
  if (error && !optimizationResult) {
    aiPriorityStatus = 'ERROR';
    aiPriorityBadgeType = 'critical';
    aiPriorityDetail = 'Telemetry Error';
  } else if (totalRequests === 0) {
    aiPriorityStatus = 'NO DATA';
    aiPriorityBadgeType = 'warning';
    aiPriorityDetail = 'No Active Requests';
  } else if (isOptimizing && optimizationStep === 1) {
    aiPriorityStatus = 'EVALUATING';
    aiPriorityBadgeType = 'info';
    aiPriorityDetail = 'Weighting Priorities';
  } else if (criticalCount > 0 || highCount > 0) {
    aiPriorityDetail = `${criticalCount} Critical, ${highCount} High`;
  }

  // Derive stage 2: BLOCK PLANNER
  let plannerStatus = 'READY';
  let plannerBadgeType = 'info';
  let plannerDetail = `${totalRequests} Work Orders`;
  if (error && !optimizationResult) {
    plannerStatus = 'ERROR';
    plannerBadgeType = 'critical';
    plannerDetail = 'Planning Failed';
  } else if (isOptimizing && optimizationStep === 1) {
    plannerStatus = 'PROCESSING';
    plannerBadgeType = 'info';
    plannerDetail = 'Corridor Windows';
  } else if (optimizationResult) {
    plannerStatus = 'COMPLETED';
    plannerBadgeType = 'success';
    plannerDetail = `${optimizationResult.horizon_days || 7}-Day Horizon`;
  }

  // Derive stage 3: SCHEDULER
  let schedulerStatus = 'READY';
  let schedulerBadgeType = 'info';
  let schedulerDetail = 'Headway Feasibility';
  if (error && !optimizationResult) {
    schedulerStatus = 'ERROR';
    schedulerBadgeType = 'critical';
    schedulerDetail = 'Unavailable';
  } else if (isOptimizing && (optimizationStep === 1 || optimizationStep === 2)) {
    schedulerStatus = 'PROCESSING';
    schedulerBadgeType = 'info';
    schedulerDetail = 'Filtering Slots';
  } else if (optimizationResult) {
    schedulerStatus = 'COMPLETED';
    schedulerBadgeType = 'success';
    schedulerDetail = 'Mutual Exclusion Bounds';
  }

  // Derive stage 4: CP-SAT SOLVER
  let cpsatStatus = 'NOT RUN';
  let cpsatBadgeType = 'muted';
  let cpsatDetail = 'Awaiting Trigger';
  if (error && isOptimizing) {
    cpsatStatus = 'ERROR';
    cpsatBadgeType = 'critical';
    cpsatDetail = 'Solver Crashed';
  } else if (isOptimizing && optimizationStep >= 2) {
    cpsatStatus = 'RUNNING';
    cpsatBadgeType = 'info';
    cpsatDetail = 'Searching Optimal Slots';
  } else if (optimizationResult) {
    cpsatStatus = solverStatus || 'COMPLETED';
    if (solverStatus === 'OPTIMAL') {
      cpsatBadgeType = 'success';
      cpsatDetail = stats?.objective_value != null ? `Obj: ${stats.objective_value.toLocaleString()}` : 'Mathematical Optimum';
    } else if (solverStatus === 'FEASIBLE') {
      cpsatBadgeType = 'warning';
      cpsatDetail = stats?.objective_value != null ? `Obj: ${stats.objective_value.toLocaleString()}` : 'Feasible Allocation';
    } else if (solverStatus === 'INFEASIBLE') {
      cpsatBadgeType = 'critical';
      cpsatDetail = 'No Feasible Solution';
    } else if (solverStatus === 'TIME_LIMIT') {
      cpsatBadgeType = 'warning';
      cpsatDetail = 'Time Limit Reached';
    } else {
      cpsatBadgeType = 'info';
      cpsatDetail = solverStatus;
    }
  }

  // Derive stage 5: FINAL BLOCK PLAN
  let finalPlanStatus = 'NOT AVAILABLE';
  let finalPlanBadgeType = 'muted';
  let finalPlanDetail = 'Awaiting CP-SAT Result';
  if (error && !optimizationResult) {
    finalPlanStatus = 'NOT AVAILABLE';
    finalPlanBadgeType = 'critical';
    finalPlanDetail = 'Execution Error';
  } else if (isOptimizing) {
    finalPlanStatus = 'COMPOSING';
    finalPlanBadgeType = 'info';
    finalPlanDetail = 'Validating Output...';
  } else if (optimizationResult) {
    if (solverStatus === 'INFEASIBLE') {
      finalPlanStatus = 'INFEASIBLE';
      finalPlanBadgeType = 'critical';
      finalPlanDetail = 'Constraints Unsatisfiable';
    } else if (validation?.is_valid === false) {
      finalPlanStatus = 'INVALID';
      finalPlanBadgeType = 'critical';
      finalPlanDetail = `${validation.violations?.length || 1} Violation(s)`;
    } else if (solverStatus === 'OPTIMAL') {
      finalPlanStatus = 'VALIDATED';
      finalPlanBadgeType = 'success';
      finalPlanDetail = `${scheduledBlocks.length} Scheduled, ${unscheduledBlocks.length} Unsched.`;
    } else if (solverStatus === 'FEASIBLE') {
      finalPlanStatus = 'AVAILABLE';
      finalPlanBadgeType = 'warning';
      finalPlanDetail = `${scheduledBlocks.length} Scheduled, ${unscheduledBlocks.length} Unsched.`;
    } else {
      finalPlanStatus = 'AVAILABLE';
      finalPlanBadgeType = 'info';
      finalPlanDetail = `${scheduledBlocks.length} Scheduled`;
    }
  }

  const stages = [
    {
      id: 'ai-priority',
      title: 'AI PRIORITY',
      icon: '🧠',
      status: aiPriorityStatus,
      badgeType: aiPriorityBadgeType,
      detail: aiPriorityDetail,
      subtext: 'Phase 5 Urgency & Criticality Scoring',
    },
    {
      id: 'block-planner',
      title: 'BLOCK PLANNER',
      icon: '📋',
      status: plannerStatus,
      badgeType: plannerBadgeType,
      detail: plannerDetail,
      subtext: 'Possession Windows & Track Demarcation',
    },
    {
      id: 'scheduler',
      title: 'SCHEDULER',
      icon: '⏱️',
      status: schedulerStatus,
      badgeType: schedulerBadgeType,
      detail: schedulerDetail,
      subtext: 'Feasible Slots & Headway Protection',
    },
    {
      id: 'cpsat',
      title: 'CP-SAT SOLVER',
      icon: '⚡',
      status: cpsatStatus,
      badgeType: cpsatBadgeType,
      detail: cpsatDetail,
      subtext: stats?.wall_time_seconds != null ? `Solve Time: ${stats.wall_time_seconds.toFixed(3)}s` : 'OR-Tools Constraint Programming',
    },
    {
      id: 'final-plan',
      title: 'FINAL BLOCK PLAN',
      icon: '📑',
      status: finalPlanStatus,
      badgeType: finalPlanBadgeType,
      detail: finalPlanDetail,
      subtext: planId ? `ID: ${planId}` : `Target: ${targetDate || 'Today'}`,
    },
  ];

  return (
    <div className="panel decision-pipeline-panel" style={{ border: '1px solid rgba(56, 189, 248, 0.22)', background: 'var(--bg-panel)' }}>
      <div className="panel-header" style={{ padding: '12px 18px', background: 'rgba(15, 23, 42, 0.6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.1rem' }}>⚡</span>
          <div>
            <div className="panel-title" style={{ fontSize: '0.88rem' }}>
              <span>Optimization Decision Pipeline</span>
              <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                END-TO-END TELEMETRY
              </span>
            </div>
            <div className="panel-subtitle" style={{ fontSize: '0.72rem' }}>
              Real-time multi-stage decision lineage from AI priority assessment to mathematically validated block allocation
            </div>
          </div>
        </div>

        {planId && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>ACTIVE PLAN:</span>
            <span className="badge badge-cyan mono" style={{ fontSize: '0.72rem', fontWeight: 700 }}>
              {planId}
            </span>
          </div>
        )}
      </div>

      <div className="panel-body" style={{ padding: '16px' }}>
        <div
          className="pipeline-stages-container"
          style={{
            display: 'flex',
            alignItems: 'stretch',
            gap: '8px',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
          }}
        >
          {stages.map((stage, idx) => {
            const isLast = idx === stages.length - 1;
            const badgeClass =
              stage.badgeType === 'success'
                ? 'badge-green'
                : stage.badgeType === 'warning'
                ? 'badge-amber'
                : stage.badgeType === 'critical'
                ? 'badge-critical'
                : stage.badgeType === 'info'
                ? 'badge-cyan'
                : 'badge-outline';

            return (
              <React.Fragment key={stage.id}>
                <div
                  className="pipeline-stage-card"
                  onClick={() => onSelectStage && onSelectStage(stage.id)}
                  style={{
                    flex: '1 1 180px',
                    minWidth: '170px',
                    background: 'rgba(15, 23, 42, 0.75)',
                    border: '1px solid rgba(51, 65, 85, 0.7)',
                    borderRadius: '6px',
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    cursor: onSelectStage ? 'pointer' : 'default',
                    transition: 'border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#38bdf8';
                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(56, 189, 248, 0.15)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(51, 65, 85, 0.7)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span>{stage.icon}</span>
                        <span>{stage.title}</span>
                      </span>
                      <span className={`badge ${badgeClass}`} style={{ fontSize: '0.66rem', padding: '1px 5px' }}>
                        {stage.status}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f1f5f9', marginTop: 4, lineHeight: 1.3 }}>
                      {stage.detail}
                    </div>
                  </div>

                  <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 8, borderTop: '1px solid rgba(51, 65, 85, 0.4)', paddingTop: 6 }}>
                    {stage.subtext}
                  </div>
                </div>

                {!isLast && (
                  <div
                    className="pipeline-connector"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#475569',
                      fontSize: '1.1rem',
                      userSelect: 'none',
                      padding: '0 2px',
                    }}
                  >
                    →
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
