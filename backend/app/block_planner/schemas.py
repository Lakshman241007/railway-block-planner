"""
Block Planner Schemas for Railway Block Planner (Phase 4).

Defines unified request and response models for the end-to-end block planning
pipeline connecting forecasting, scheduling, and conflict detection.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.forecast.schemas import GoodsForecastResult
from backend.app.schemas.unified_data import Priority
from backend.app.scheduler.schemas import (
    ConflictReport,
    CorridorAvailabilityWindow,
    MaintenanceScheduleItem,
    ScheduleResult,
)



class BlockPlanRequest(BaseModel):
    """
    Request model to generate an end-to-end maintenance block plan.
    """

    target_date: Optional[date] = Field(default=None, description="Date to plan maintenance for (default: today)")
    priority_filter: Optional[str] = Field(default=None, description="Optional priority filter")
    location_filter: Optional[str] = Field(default=None, description="Optional corridor/section filter")
    buffer_minutes: int = Field(default=15, ge=0, le=60, description="Safety headway buffer in minutes")
    include_forecast: bool = Field(default=True, description="Whether to include goods train forecasting")
    include_conflicts: bool = Field(default=True, description="Whether to perform conflict detection")

    model_config = {"str_strip_whitespace": True}


class BlockPlanResult(BaseModel):
    """
    Unified end-to-end block planning response.
    """

    plan_id: str = Field(..., description="Unique plan generation identifier")
    generated_at: str = Field(..., description="ISO timestamp")
    target_date: date = Field(..., description="Service date of the plan")
    phase: str = Field(default="Phase 4 - Forecast + Scheduler + Conflict Detection")
    forecast_summary: Optional[Dict[str, Any]] = Field(default=None, description="Goods train forecast summary")
    schedule: ScheduleResult = Field(..., description="Heuristic maintenance schedule")
    conflict_report: Optional[ConflictReport] = Field(default=None, description="Conflict detection results")
    resolution_recommendations: List[Dict[str, str]] = Field(
        default_factory=list, description="Rule-based heuristic resolution suggestions"
    )

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Phase 1 — Block Planner Data Contracts (Monthly & Weekly Planning Horizons)
# ---------------------------------------------------------------------------

class MonthlyPlanItem(BaseModel):
    """
    Represents a single planned maintenance work item in the 30-day monthly plan.
    Bucketed into month and week planning intervals.
    """

    work_id: str = Field(..., description="Unique maintenance work identifier")
    month_bucket: str = Field(..., description="Planning month bucket (e.g. '2026-10')")
    week_bucket: int = Field(..., ge=1, le=5, description="Week bucket within the month (1 to 5)")
    corridor: str = Field(..., description="Corridor or railway section identifier")
    estimated_duration_minutes: int = Field(..., gt=0, description="Estimated work duration in minutes")
    priority: Optional[Priority] = Field(default=None, description="Existing priority level")
    asset_id: Optional[str] = Field(default=None, description="Associated railway asset identifier")
    asset_type: Optional[str] = Field(default=None, description="Asset category (Track, Signal, OHE, Bridge, etc.)")
    location: Optional[str] = Field(default=None, description="Detailed location or kilometer chainage")
    maintenance_type: Optional[str] = Field(default=None, description="Maintenance category (Preventive, Repair, Inspection, etc.)")
    required_resources: int = Field(default=1, ge=1, description="Estimated resource units required")
    equipment: Optional[str] = Field(default=None, description="Required specialized equipment")
    status: str = Field(default="Planned", description="Planning lifecycle status (Planned, Deferred, Approved)")
    description: Optional[str] = Field(default=None, description="Work description or engineering notes")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class MonthlyPlan(BaseModel):
    """
    Represents a 30-day tactical maintenance plan aggregating monthly work volume,
    corridor distributions, and weekly bucket breakdowns.
    """

    plan_id: str = Field(..., description="Unique monthly plan identifier")
    planning_month: str = Field(..., description="Planning period label (e.g. '2026-10')")
    start_date: date = Field(..., description="Start date of the 30-day horizon")
    end_date: date = Field(..., description="End date of the 30-day horizon")
    horizon_days: int = Field(default=30, ge=28, le=31, description="Planning horizon length in days")
    generated_at: str = Field(..., description="ISO generation timestamp")
    corridor_summaries: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated maintenance volume/counts per corridor",
    )
    total_maintenance_volume: int = Field(
        default=0,
        ge=0,
        description="Total maintenance volume in estimated minutes across all items",
    )
    total_items: int = Field(
        default=0,
        ge=0,
        description="Total number of maintenance items in this plan",
    )
    weekly_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Volume and item counts partitioned by week bucket (e.g. {'Week 1': {...}})",
    )
    items: List[MonthlyPlanItem] = Field(
        default_factory=list,
        description="List of planned monthly maintenance items",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operational metadata, version, or author information",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class WeeklyPlanItem(BaseModel):
    """
    Represents a planned maintenance item scheduled within a 7-day weekly horizon.
    """

    work_id: str = Field(..., description="Unique maintenance work identifier")
    target_date: date = Field(..., description="Target service date within the week")
    corridor: str = Field(..., description="Corridor identifier")
    location: str = Field(..., description="Railway section or station location")
    estimated_duration_minutes: int = Field(..., gt=0, description="Estimated work duration in minutes")
    asset_id: Optional[str] = Field(default=None, description="Asset identifier")
    asset_type: Optional[str] = Field(default=None, description="Asset category")
    block_id: Optional[str] = Field(default=None, description="Associated block request ID if applicable")
    asset_compatibility_requirements: List[str] = Field(
        default_factory=list,
        description="Asset compatibility constraints or requirements",
    )
    required_resources: int = Field(default=1, ge=1, description="Required personnel / crew units")
    required_equipment: Optional[str] = Field(default=None, description="Required specialized machinery")
    priority: Optional[Priority] = Field(default=None, description="Existing urgency priority level")
    preferred_start: Optional[str] = Field(default=None, description="Preferred start time (HH:MM)")
    constraints: List[str] = Field(
        default_factory=list,
        description="Operational constraints (e.g. 'OHE Power Block required', 'Speed restriction')",
    )
    is_mandatory: bool = Field(default=False, description="Whether this task is mandatory/hard-constrained")
    is_pinned: bool = Field(default=False, description="Whether slot timing is pinned from a previous plan")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class WeeklyPlan(BaseModel):
    """
    Represents a 7-day tactical maintenance plan bridging monthly buckets to daily scheduling problems.
    """

    plan_id: str = Field(..., description="Unique weekly plan identifier")
    start_date: date = Field(..., description="Start date of the 7-day horizon")
    end_date: date = Field(..., description="End date of the 7-day horizon")
    horizon_days: int = Field(default=7, ge=1, le=14, description="Planning horizon length in days")
    generated_at: str = Field(..., description="ISO generation timestamp")
    total_items: int = Field(default=0, ge=0, description="Total number of maintenance items")
    total_duration_minutes: int = Field(default=0, ge=0, description="Total planned duration in minutes")
    daily_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Maintenance item counts partitioned by day (e.g. {'2026-10-05': 3})",
    )
    corridor_summaries: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of weekly volume and work counts per corridor",
    )
    items: List[WeeklyPlanItem] = Field(
        default_factory=list,
        description="Planned maintenance items for the week",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational planning metadata")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Phase 1 — DailySchedulingProblem Contract (Block Planner → Scheduler Interface)
# ---------------------------------------------------------------------------

class CandidateWorkItem(BaseModel):
    """
    Work item prepared by the Block Planner for input into the daily scheduling problem.
    Designed for seamless future extension with AI prioritization payloads without schema breakage.
    """

    work_id: str = Field(..., description="Unique candidate work identifier")
    location: str = Field(..., description="Railway corridor section or station")
    required_duration_minutes: int = Field(..., gt=0, description="Required work duration in minutes")
    asset_id: Optional[str] = Field(default=None, description="Target asset identifier")
    asset_type: Optional[str] = Field(default=None, description="Asset classification (Track, Signal, OHE, Bridge, etc.)")
    corridor: Optional[str] = Field(default=None, description="Corridor designation (e.g. 'Chennai-Arakkonam')")
    maintenance_type: Optional[str] = Field(default=None, description="Maintenance category (Preventive, Repair, etc.)")
    required_resources: int = Field(default=1, ge=1, description="Required manpower / resource units")
    required_equipment: Optional[str] = Field(default=None, description="Required machinery / equipment")
    priority: Optional[Priority] = Field(default=None, description="Current operational priority level")
    preferred_start: Optional[str] = Field(default=None, description="Requested / preferred start time (HH:MM)")
    preferred_date: Optional[date] = Field(default=None, description="Preferred execution date")
    constraints: List[str] = Field(default_factory=list, description="Operational constraints")
    is_mandatory: bool = Field(default=False, description="Hard constraint: must be scheduled")
    is_pinned: bool = Field(default=False, description="Slot is locked to a specific time")
    pinned_slot: Optional[str] = Field(default=None, description="Locked slot time interval (HH:MM-HH:MM)")
    ai_priority_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Extensible envelope reserved for future AI prioritization metrics (urgency, criticality, overdue_factor, etc.)",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class DailySchedulingProblem(BaseModel):
    """
    Canonical interface contract connecting the Block Planner to the Scheduler.
    Encapsulates all candidate works, availability windows, constraints, and operational buffers
    for a single target scheduling date.
    """

    problem_id: str = Field(..., description="Unique daily problem identifier")
    target_date: date = Field(..., description="Target service date for scheduling")
    candidate_works: List[CandidateWorkItem] = Field(
        default_factory=list,
        description="Candidate maintenance items requiring scheduling slots",
    )
    available_windows: List[CorridorAvailabilityWindow] = Field(
        default_factory=list,
        description="Available corridor and block time windows",
    )
    timetable_constraints: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Passenger timetable constraints and scheduled train passages",
    )
    goods_train_forecast_windows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Forecasted goods train movements and section passage windows",
    )
    operational_restrictions: List[str] = Field(
        default_factory=list,
        description="Corridor-wide operational restrictions, headway rules, or speed caps",
    )
    buffer_minutes: int = Field(
        default=15,
        ge=0,
        le=60,
        description="Safety headway buffer in minutes required between trains and blocks",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual metadata, planner version, or provenance details",
    )

    model_config = {"str_strip_whitespace": True, "extra": "allow"}

