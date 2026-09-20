"""
Optimizer Pydantic schemas (Phase 5).

Defines canonical data contracts for CP-SAT mathematical optimization,
decision results, unscheduled diagnostics, solver statistics, and planning horizons.

PROTOTYPE DISCLAIMER:
Optimization models and objective parameters are prototype assumptions for the
hackathon demonstration and are NOT official railway operating rules.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.unified_data import Priority, PriorityEnrichment


class OptimizationStatus(str, Enum):
    """Status returned by the CP-SAT mathematical solver."""
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIME_LIMIT = "TIME_LIMIT"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"


class ObjectiveWeights(BaseModel):
    """
    Configurable weights for the multi-objective optimization function.

    Priority signal model (single-priority XOR rule):
        Primary path  — weight_priority_value × priority_value
            Applied when priority_value is not None.  This is the sole priority
            utility term; categorical label weights are excluded.
        Legacy fallback — weight_priority_critical / high / medium / low
            Applied ONLY when priority_value is None.  Preserves backward
            compatibility for records that have not been scored by the
            AI prioritization layer.  Never active simultaneously with
            the primary numerical path.
    """

    weight_scheduled: int = Field(
        default=10000,
        ge=0,
        description="Weight awarded for each successfully scheduled maintenance block",
    )
    weight_priority_critical: int = Field(
        default=5000,
        ge=0,
        description=(
            "[Legacy fallback] Bonus applied when priority_value is None and "
            "categorical priority is Critical. Never combined with weight_priority_value."
        ),
    )
    weight_priority_high: int = Field(
        default=2500,
        ge=0,
        description=(
            "[Legacy fallback] Bonus applied when priority_value is None and "
            "categorical priority is High. Never combined with weight_priority_value."
        ),
    )
    weight_priority_medium: int = Field(
        default=1000,
        ge=0,
        description=(
            "[Legacy fallback] Bonus applied when priority_value is None and "
            "categorical priority is Medium. Never combined with weight_priority_value."
        ),
    )
    weight_priority_low: int = Field(
        default=200,
        ge=0,
        description=(
            "[Legacy fallback] Bonus applied when priority_value is None and "
            "categorical priority is Low. Never combined with weight_priority_value."
        ),
    )
    weight_priority_value: int = Field(
        default=50,
        ge=0,
        description=(
            "[Primary] Multiplier for the single numerical priority signal. "
            "Objective contribution = weight_priority_value × priority_value. "
            "Applied only when priority_value is not None; categorical weights "
            "are excluded when this path is active."
        ),
    )
    weight_preferred_deviation: int = Field(
        default=5,
        ge=0,
        description="Penalty per minute of deviation from the preferred start time",
    )
    weight_disruption: int = Field(
        default=50,
        ge=0,
        description="Penalty multiplier for scheduling in lower-fit candidate slots",
    )
    weight_resource_contention: int = Field(
        default=100,
        ge=0,
        description="Penalty multiplier for equipment contention pressure",
    )

    model_config = {"str_strip_whitespace": True}


class OptimizationRequest(BaseModel):
    """
    Request model for triggering CP-SAT maintenance block optimization.
    """

    target_date: Optional[date] = Field(
        default=None,
        description="Start date of the optimization planning horizon (default: today)",
    )
    horizon_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Optimization planning horizon in days (e.g. 7 for weekly, 30 for monthly)",
    )
    priority_filter: Optional[str] = Field(
        default=None,
        description="Filter requests by priority (Critical, High, Medium, Low)",
    )
    location_filter: Optional[str] = Field(
        default=None,
        description="Filter requests by corridor / section name",
    )
    buffer_minutes: int = Field(
        default=15,
        ge=0,
        le=60,
        description="Safety headway buffer in minutes",
    )
    time_limit_seconds: float = Field(
        default=30.0,
        gt=0.0,
        le=300.0,
        description="Maximum solver execution time in seconds",
    )
    num_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of parallel search workers for CP-SAT",
    )
    weights: Optional[ObjectiveWeights] = Field(
        default=None,
        description="Optional custom objective weights overriding default configuration",
    )
    custom_capacities: Optional[Dict[str, int]] = Field(
        default=None,
        description="Optional override for equipment/resource capacity limits",
    )
    include_forecast: bool = Field(
        default=True,
        description="Whether to incorporate goods train forecasts during candidate slot generation",
    )
    max_slots_per_request: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum candidate slots generated per maintenance request",
    )

    # --- Feature 3: Urgency Overrides & Re-Optimization Preferences ---
    priority_overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Per-task priority overrides for this run: { 'TRK-M-001': 'Critical' } or numerical AI priority values",
    )
    pinned_slots: Optional[Dict[str, str]] = Field(
        default=None,
        description="Locked slot times for re-optimization: { 'TRK-M-001': '02:00-04:00' }",
    )
    mandatory_request_ids: Optional[List[str]] = Field(
        default=None,
        description="Task IDs that MUST be scheduled (hard constraint: sum(x) == 1)",
    )
    exclude_from_reopt: Optional[List[str]] = Field(
        default=None,
        description="Task IDs to exclude/freeze from this re-optimization run",
    )
    strategy_preset: Optional[str] = Field(
        default="balanced",
        description="Solver trade-off preset: 'balanced' | 'max_throughput' | 'minimal_disruption' | 'safety_priority'",
    )

    # --- Daily Scheduler Integration (Phase 4) ---
    candidate_works: Optional[List[Any]] = Field(
        default=None,
        description="Candidate maintenance work items from DailySchedulingProblem",
    )
    candidate_matches: Optional[List[Any]] = Field(
        default=None,
        description="Candidate work-to-window pairings from WorkMatchReport",
    )
    available_windows: Optional[List[Any]] = Field(
        default=None,
        description="Audited corridor availability windows from DailyAvailabilityReport",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class OptimizedBlock(BaseModel):
    """
    A maintenance block assigned and verified by the CP-SAT optimizer.
    """

    block_id: str = Field(..., description="Unique optimized block assignment ID")
    request_id: str = Field(..., description="Originating request ID (asset_id or block_id)")
    asset_id: Optional[str] = Field(default=None, description="Asset ID if from maintenance request")
    block_request_id: Optional[str] = Field(default=None, description="Block ID if from block request")
    location: str = Field(..., description="Corridor section / track location")
    service_date: date = Field(..., description="Scheduled service date")
    start_time: str = Field(..., description="Scheduled start time (HH:MM)")
    end_time: str = Field(..., description="Scheduled end time (HH:MM)")
    duration_minutes: int = Field(..., gt=0, description="Scheduled duration in minutes")
    priority: Priority = Field(..., description="Maintenance urgency priority")
    equipment: Optional[str] = Field(default=None, description="Specialized equipment allocated")
    required_resources: int = Field(default=1, ge=1, description="Resource/manpower units allocated")
    status: str = Field(default="Scheduled", description="Scheduling status")
    assigned_slot_id: str = Field(..., description="Assigned candidate slot identifier")
    fit_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Fit score of assigned slot")
    is_preferred_match: bool = Field(default=True, description="True if scheduled at preferred time")
    deviation_minutes: int = Field(default=0, ge=0, description="Minutes deviated from requested start")
    is_pinned: bool = Field(default=False, description="True if block was pinned by operator preference")
    is_shifted: bool = Field(default=False, description="True if block shifted from requested or prior slot")
    priority_value: Optional[float] = Field(default=None, description="Authoritative AI priority score")
    priority_enrichment: Optional[PriorityEnrichment] = Field(default=None, description="AI prioritization explainability metrics")
    priority_contribution: Optional[int] = Field(
        default=None,
        description="Objective score contribution awarded from numerical priority",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class UnscheduledBlock(BaseModel):
    """
    A maintenance request that could not be scheduled by the optimizer,
    along with root-cause diagnostic explanation.
    """

    request_id: str = Field(..., description="Originating request ID")
    asset_id: Optional[str] = Field(default=None, description="Asset ID if applicable")
    block_id: Optional[str] = Field(default=None, description="Block request ID if applicable")
    location: str = Field(..., description="Corridor section requested")
    requested_date: date = Field(..., description="Original requested date")
    preferred_start: str = Field(..., description="Original requested start time (HH:MM)")
    duration_minutes: int = Field(..., gt=0, description="Requested duration in minutes")
    priority: Priority = Field(..., description="Priority level")
    equipment: Optional[str] = Field(default=None, description="Requested specialized equipment")
    required_resources: int = Field(default=1, ge=1, description="Requested resource units")
    reason: str = Field(..., description="Detailed diagnostic explanation for why this could not be scheduled")
    resource_contention: Optional[str] = Field(
        default=None, description="Specific resource, track, or crew constraint causing the blockage"
    )
    priority_value: Optional[float] = Field(default=None, description="Authoritative AI priority score")
    priority_enrichment: Optional[PriorityEnrichment] = Field(default=None, description="AI prioritization explainability metrics")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class SolverStatistics(BaseModel):
    """
    Mathematical solver telemetry and execution performance metrics.
    """

    status: OptimizationStatus = Field(..., description="Solver status result")
    objective_value: Optional[float] = Field(default=None, description="Final mathematical objective value")
    wall_time_seconds: float = Field(default=0.0, ge=0.0, description="Solver execution time in seconds")
    num_scheduled: int = Field(default=0, ge=0, description="Total maintenance blocks successfully scheduled")
    num_unscheduled: int = Field(default=0, ge=0, description="Total unscheduled maintenance requests")
    num_conflicts_avoided: int = Field(default=0, ge=0, description="Estimated conflicts resolved by solver")
    conflicts_before: Optional[int] = Field(default=None, ge=0, description="Pre-optimization operational conflicts count")
    conflicts_after: Optional[int] = Field(default=None, ge=0, description="Post-optimization operational conflicts count")
    total_requests: int = Field(default=0, ge=0, description="Total maintenance requests processed")
    num_variables: int = Field(default=0, ge=0, description="Total CP-SAT decision variables created")
    num_constraints: int = Field(default=0, ge=0, description="Total hard constraints enforced")
    num_branches: Optional[int] = Field(default=0, ge=0, description="Search branches explored by CP-SAT")
    num_pinned: int = Field(default=0, ge=0, description="Number of pinned possessions retained")
    num_shifted: int = Field(default=0, ge=0, description="Possessions whose times shifted during re-optimization")
    stability_score: Optional[float] = Field(default=None, description="Percentage of schedule unchanged (0.0 - 1.0)")

    model_config = {"str_strip_whitespace": True}


class OptimizationResult(BaseModel):
    """
    Unified CP-SAT maintenance optimization response model.
    """

    plan_id: str = Field(..., description="Unique optimization run identifier")
    generated_at: str = Field(..., description="ISO generation timestamp")
    target_date: date = Field(..., description="Start date of the optimization horizon")
    horizon_days: int = Field(default=7, description="Planning horizon length in days")
    status: OptimizationStatus = Field(..., description="Solver status (OPTIMAL, FEASIBLE, INFEASIBLE)")
    objective_value: Optional[float] = Field(default=None, description="Achieved objective score")
    solver_statistics: SolverStatistics = Field(..., description="Execution telemetry and statistics")
    scheduled_blocks: List[OptimizedBlock] = Field(default_factory=list, description="Optimized scheduled blocks")
    unscheduled_blocks: List[UnscheduledBlock] = Field(
        default_factory=list, description="Unscheduled requests with diagnostics"
    )
    phase: str = Field(default="Phase 5 - CP-SAT Optimization", description="Pipeline phase")
    notes: Optional[str] = Field(default=None, description="Prototype notes and disclaimer summary")

    model_config = {"str_strip_whitespace": True}
