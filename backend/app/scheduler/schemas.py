"""
Scheduler and Conflict Detection Pydantic schemas (Phase 4).

Defines canonical models for feasible maintenance slots, generated schedules,
spatial-temporal conflict reports, severity levels, and resolution actions.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.unified_data import Priority, PriorityEnrichment


class ConflictType(str, Enum):
    """Types of operational conflicts detected in the railway corridor."""
    TRAIN_BLOCK = "Train-Block Overlap"
    BLOCK_BLOCK = "Block-Block Contention"
    SAFETY_BUFFER_VIOLATION = "Safety Buffer Violation"
    RESOURCE_CONTENTION = "Resource Contention"


class ConflictSeverity(str, Enum):
    """Severity ratings for detected operational conflicts."""
    CRITICAL = "Critical"  # Direct collision with passenger train or emergency block
    HIGH = "High"          # Overlap with high-priority train or zero safety buffer
    MEDIUM = "Medium"      # Overlap with flexible goods train or equipment contention
    LOW = "Low"            # Minor buffer compression with low priority traffic


class FeasibleSlot(BaseModel):
    """
    A verified, conflict-free time window on a specific railway section
    that satisfies the required maintenance duration and safety buffers.
    """

    slot_id: str = Field(..., description="Unique identifier for the feasible slot")
    location: str = Field(..., description="Railway section / location description")
    service_date: date = Field(..., description="Date of the slot")
    start_time: str = Field(..., description="Slot start time (HH:MM)")
    end_time: str = Field(..., description="Slot end time (HH:MM)")
    duration_minutes: int = Field(..., gt=0, description="Available window duration in minutes")
    fit_score: float = Field(..., ge=0.0, le=1.0, description="Ranking score based on preferred start match")
    is_preferred_match: bool = Field(default=False, description="True if slot overlaps preferred requested time")

    model_config = {"str_strip_whitespace": True}


class MaintenanceScheduleItem(BaseModel):
    """
    Scheduling assignment decision for a single maintenance or block request.
    """

    schedule_id: str = Field(..., description="Unique schedule assignment ID")
    request_id: str = Field(..., description="Identifier of the originating request (asset_id or block_id)")
    asset_id: Optional[str] = Field(default=None, description="Asset ID if from maintenance request")
    block_id: Optional[str] = Field(default=None, description="Block ID if from block request")
    location: str = Field(..., description="Corridor section or station location")
    priority: Priority = Field(..., description="Urgency priority")
    requested_duration: int = Field(..., gt=0, description="Required work duration in minutes")
    preferred_start: str = Field(..., description="Preferred start time (HH:MM)")
    assigned_slot: Optional[FeasibleSlot] = Field(default=None, description="Primary scheduled feasible slot")
    alternative_slots: List[FeasibleSlot] = Field(default_factory=list, description="Alternative feasible slots")
    status: str = Field(default="Scheduled", description="Scheduled, Unfeasible, or AlternativeSuggested")
    notes: Optional[str] = Field(default=None, description="Scheduling heuristics explanation")

    model_config = {"str_strip_whitespace": True}


class ScheduleResult(BaseModel):
    """
    Full schedule output containing all planned maintenance assignments.
    """

    generated_at: str = Field(..., description="ISO generation timestamp")
    target_date: date = Field(..., description="Target service date")
    total_requested: int = Field(..., ge=0, description="Total requests processed")
    total_scheduled: int = Field(..., ge=0, description="Successfully scheduled requests")
    total_unfeasible: int = Field(..., ge=0, description="Requests with no feasible slot")
    scheduled_items: List[MaintenanceScheduleItem] = Field(default_factory=list)
    unfeasible_items: List[MaintenanceScheduleItem] = Field(default_factory=list)

    model_config = {"str_strip_whitespace": True}


class ConflictItem(BaseModel):
    """
    A single detected operational or spatial-temporal conflict.
    """

    conflict_id: str = Field(..., description="Unique conflict identifier")
    conflict_type: ConflictType = Field(..., description="Category of conflict")
    severity: ConflictSeverity = Field(..., description="Severity grading")
    location: str = Field(..., description="Corridor / section where conflict occurs")
    service_date: date = Field(..., description="Date of occurrence")
    start_time: str = Field(..., description="Conflict start time (HH:MM)")
    end_time: str = Field(..., description="Conflict end time (HH:MM)")
    overlap_minutes: int = Field(default=0, ge=0, description="Duration of physical overlap in minutes")
    entity1_type: str = Field(..., description="Type of first entity (e.g. Train, Block, Maintenance)")
    entity1_id: str = Field(..., description="Identifier of first entity")
    entity2_type: str = Field(..., description="Type of second entity")
    entity2_id: str = Field(..., description="Identifier of second entity")
    description: str = Field(..., description="Human-readable description of conflict")
    suggested_action: Optional[str] = Field(default=None, description="Rule-based resolution recommendation")
    entity1_priority: Optional[str] = Field(default=None, description="Priority of first entity")
    entity2_priority: Optional[str] = Field(default=None, description="Priority of second entity")
    precedence_entity_id: Optional[str] = Field(default=None, description="Entity designated operational precedence")
    resolution_strategy: Optional[str] = Field(default=None, description="Recommended resolution strategy category")

    model_config = {"str_strip_whitespace": True}


class ConflictReport(BaseModel):
    """
    Comprehensive conflict detection audit report.
    """

    generated_at: str = Field(..., description="ISO generation timestamp")
    target_date: date = Field(..., description="Target service date")
    total_conflicts: int = Field(..., ge=0, description="Total detected conflicts")
    critical_count: int = Field(default=0, ge=0, description="Count of Critical severity conflicts")
    high_count: int = Field(default=0, ge=0, description="Count of High severity conflicts")
    medium_count: int = Field(default=0, ge=0, description="Count of Medium severity conflicts")
    low_count: int = Field(default=0, ge=0, description="Count of Low severity conflicts")
    is_conflict_free: bool = Field(default=True, description="True if 0 conflicts detected")
    conflicts: List[ConflictItem] = Field(default_factory=list, description="List of conflict details")

    model_config = {"str_strip_whitespace": True}


# Canonical schedule-type contract shared between API and scheduler engine.
# Literal enforces that FastAPI/Pydantic rejects any other string with HTTP 422.
ScheduleType = Literal["daily", "weekly", "monthly"]


class ScheduleRequest(BaseModel):
    """
    Request payload for maintenance scheduling.
    """

    target_date: Optional[date] = Field(default=None, description="Service date to schedule (default: today)")
    priority_filter: Optional[str] = Field(default=None, description="Filter requests by priority")
    location_filter: Optional[str] = Field(default=None, description="Filter requests by section/location")
    buffer_minutes: int = Field(default=15, ge=0, le=60, description="Safety headway buffer in minutes")
    schedule_type: ScheduleType = Field(
        default="daily",
        description=(
            "Planning horizon type. "
            "'daily' = 1 day, 'weekly' = 7 days, "
            "'monthly' = remaining days in the calendar month."
        ),
    )

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Phase 1 — Data Contracts for Block Planner → Scheduler Architecture
# ---------------------------------------------------------------------------

class CorridorAvailabilityWindow(BaseModel):
    """
    Represents an available corridor or block time window evaluated from timetable,
    forecast, and operational track conditions.
    """

    window_id: str = Field(..., description="Unique availability window identifier")
    corridor: str = Field(..., description="Corridor or line segment")
    service_date: date = Field(..., description="Date of the available window")
    start_time: str = Field(..., description="Window start time (HH:MM)")
    end_time: str = Field(..., description="Window end time (HH:MM)")
    duration_minutes: int = Field(..., gt=0, description="Available window duration in minutes")
    block_id: Optional[str] = Field(default=None, description="Associated block request or section identifier")
    section: Optional[str] = Field(default=None, description="Specific track section within the corridor")
    status: str = Field(default="Available", description="Availability status (Available, Restricted, Blocked)")
    restrictions: List[str] = Field(
        default_factory=list,
        description="Operational restrictions (e.g. speed caps, single-line operation)",
    )
    capacity_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Capacity limits, e.g. max parallel possessions, crew capacity",
    )
    max_parallel_works: int = Field(default=1, ge=1, description="Maximum simultaneous works permitted")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class DailyAvailabilityReport(BaseModel):
    """
    Comprehensive availability audit report produced by the Scheduler for a given target date.
    Summarizes clear windows, blocked intervals, and operational constraints across corridors.
    """

    report_id: str = Field(..., description="Unique availability report identifier")
    target_date: date = Field(..., description="Service date of the availability audit")
    generated_at: str = Field(..., description="ISO generation timestamp")
    available_windows: List[CorridorAvailabilityWindow] = Field(
        default_factory=list,
        description="Verified available time windows across corridors",
    )
    blocked_periods: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Periods blocked by train passages, existing blocks, or restrictions",
    )
    timetable_restrictions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Fixed passenger timetable occupancy and buffer restrictions",
    )
    goods_train_restrictions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Projected goods train windows restricting maintenance access",
    )
    active_movement_restrictions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Live train movements restricting track possession",
    )
    corridor_capacities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Capacity telemetry and utilization metrics per corridor",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class WorkBlockMatch(BaseModel):
    """
    Represents a candidate or evaluated match between a maintenance work item
    and an available block window.
    """

    match_id: str = Field(..., description="Unique match evaluation identifier")
    work_id: str = Field(..., description="Candidate work item identifier")
    window_id: str = Field(..., description="Availability window identifier")
    is_compatible: bool = Field(default=True, description="Whether the work satisfies all compatibility checks for the window")
    fit_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Heuristic or temporal fit score (0.0 to 1.0)")
    compatibility_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed check outcomes: location match, duration fit, resource availability",
    )
    rejection_reasons: List[str] = Field(
        default_factory=list,
        description="List of reasons if incompatible (e.g. 'Location mismatch', 'Insufficient duration')",
    )
    priority_value: Optional[float] = Field(default=None, description="Authoritative AI priority score")
    priority_enrichment: Optional[PriorityEnrichment] = Field(default=None, description="AI prioritization explainability metrics")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class WorkMatchReport(BaseModel):
    """
    Diagnostic matching report distinguishing successful work-to-block matches from rejected works,
    with categorised rejection root-cause statistics.
    """

    report_id: str = Field(..., description="Unique work match report identifier")
    target_date: date = Field(..., description="Service date evaluated")
    generated_at: str = Field(..., description="ISO generation timestamp")
    total_works: int = Field(default=0, ge=0, description="Total candidate work items evaluated")
    total_matches: int = Field(default=0, ge=0, description="Total successfully matched works")
    total_rejected: int = Field(default=0, ge=0, description="Total rejected / unmatchable works")
    successful_matches: List[WorkBlockMatch] = Field(
        default_factory=list,
        description="List of compatible work-to-block matches",
    )
    rejected_works: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Details of candidate works that could not be matched, with causes",
    )
    rejection_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Aggregate counts by rejection category (e.g. 'Location mismatch', 'Insufficient duration', 'Resource unavailable', 'Asset incompatibility', 'Operational incompatibility')",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class DailyScheduleResult(BaseModel):
    """
    Comprehensive daily schedule output representing final block assignments,
    unscheduled diagnostics, matching metrics, and optimization telemetry.
    """

    plan_id: str = Field(..., description="Unique schedule execution identifier")
    target_date: date = Field(..., description="Target service date of the schedule")
    generated_at: str = Field(..., description="ISO generation timestamp")
    total_scheduled: int = Field(default=0, ge=0, description="Count of successfully scheduled maintenance works")
    total_unscheduled: int = Field(default=0, ge=0, description="Count of unscheduled maintenance works")
    scheduled_works: List[Any] = Field(
        default_factory=list,
        description="Scheduled maintenance items or schedule assignments",
    )
    optimized_block_assignments: List[Any] = Field(
        default_factory=list,
        description="Final block possessions assigned and verified by optimizer (OptimizedBlock items)",
    )
    unscheduled_works: List[Any] = Field(
        default_factory=list,
        description="Unscheduled maintenance items with root-cause diagnostic reasons (UnscheduledBlock items)",
    )
    diagnostics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operational diagnostics, bottleneck locations, or resource contention notes",
    )
    matching_statistics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Telemetry regarding work-block candidate matches and rejection ratios",
    )
    optimization_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Solver run configuration, objective presets, or solver parameters",
    )
    solver_statistics: Optional[Any] = Field(
        default=None,
        description="CP-SAT mathematical solver metrics (SolverStatistics)",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


def __getattr__(name: str) -> Any:
    """
    Dynamic attribute resolution allowing candidate problem schemas to be imported
    directly from backend.app.scheduler.schemas without cyclic dependencies.
    """
    if name in ("CandidateWorkItem", "DailySchedulingProblem", "PriorityEnrichment"):
        import backend.app.block_planner.schemas as bps
        return getattr(bps, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
