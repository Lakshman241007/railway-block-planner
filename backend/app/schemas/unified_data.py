"""
Unified Data Schema for Railway Block Planner.

This module defines the canonical data models used across the entire
railway block planning system. All data sources (SMMS, TMS, TDMS, COA,
BDMS, etc.) are normalized into these unified models before being used
by downstream modules such as the scheduler, conflict detector, or
optimizer.

The MaintenanceRecord model is the central contract:
    Source CSV → Collector → Validator → Normalizer → MaintenanceRecord

Any future data source must ultimately produce MaintenanceRecord objects
so that downstream consumers remain source-agnostic.
"""

from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    """Allowed maintenance priority levels, ordered by urgency."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class MaintenanceStatus(str, Enum):
    """Allowed lifecycle statuses for a maintenance record."""
    PENDING = "Pending"
    APPROVED = "Approved"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


# ---------------------------------------------------------------------------
# Phase 5 — AI Prioritization Enrichment Contract
# ---------------------------------------------------------------------------

class PriorityEnrichment(BaseModel):
    """
    Priority Assessment Enrichment Contract (Phase 5).

    Encapsulates the currently-supported priority factors and the final derived score
    consumed by downstream scheduling and CP-SAT optimization.

    Architecture
    ────────────
    Current supported factors (inputs):
        urgency        — How time-sensitive the maintenance work is.
        criticality    — Safety/structural importance of the asset or track section.
        overdue_factor — Temporal signal representing how overdue the maintenance is.

    Derived result (output):
        priority_value — The single authoritative numerical priority score produced by
                         combining the above factors, supplied by AIPrioritizer.scorer
                         or a future rules/ML implementation.  It is NOT a manually-
                         provided peer input alongside the factors.

    Explainability
    ──────────────
    The three factor fields are preserved alongside priority_value so that the system
    can always explain:
      "This work received this priority because of its urgency, criticality,
       and overdue status."

    Future Extensions (NOT currently implemented)
    ─────────────────────────────────────────────
    asset_availability_impact — Impact on asset operational availability.
    operational_impact        — Disruption to wider network operations.

    These factors require richer railway asset/network relationship data and/or
    historical operational datasets that are not yet available to the system.
    They will be introduced in a future phase once the required data pipelines
    and/or AI/ML feature extraction capabilities are in place.

    PROTOTYPE DISCLAIMER
    ────────────────────
    No ML inference model is currently implemented.  This contract acts as the
    integration adapter for a future rules-based or ML scoring component.
    """

    urgency: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Normalized urgency metric (0.0 to 1.0). "
            "Reflects how time-sensitive the maintenance work is based on deadline proximity "
            "and deferral risk derived from available maintenance data."
        ),
    )
    criticality: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Asset/track safety criticality rating (0.0 to 1.0). "
            "Reflects the safety or structural importance classification available "
            "from the maintenance or asset record."
        ),
    )
    overdue_factor: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Temporal overdue multiplier (≥ 0.0). "
            "A derived signal representing how overdue the maintenance is relative to "
            "its scheduled or recommended interval."
        ),
    )
    priority_value: float = Field(
        ...,
        description=(
            "Derived authoritative numerical priority score for downstream scheduling. "
            "This is the OUTPUT produced by combining urgency, criticality, and "
            "overdue_factor via AIPrioritizer.scorer or a future rules/ML implementation. "
            "It is NOT a manually-provided input alongside the factor fields."
        ),
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Provenance details, model version, feature importances, or any other "
            "explainability context attached by the scoring implementation."
        ),
    )

    # extra="allow" preserves forward-compatibility: future fields (e.g. asset_availability_impact,
    # operational_impact) can be passed through without causing schema validation failures
    # once the required data pipelines are available.
    model_config = {"str_strip_whitespace": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Unified Maintenance Record
# ---------------------------------------------------------------------------

class MaintenanceRecord(BaseModel):
    """
    Canonical representation of a single maintenance activity.

    Every data source must normalize its records into this model.
    The schema is intentionally kept generic so that future sources
    (TMS, TDMS, COA, BDMS, timetable data, etc.) can coexist with
    the same downstream pipeline.

    Attributes:
        asset_id:               Unique identifier for the railway asset.
        asset_type:             Category of the asset (Track, Signal, Bridge, …).
        location:               Human-readable location or section description.
        maintenance_type:       Kind of maintenance (Preventive, Repair, …).
        maintenance_required:   Whether maintenance is actually needed.
        priority:               Urgency level.
        duration_minutes:       Expected duration of the work in minutes.
        requested_date:         Date the maintenance was requested for.
        preferred_start:        Preferred start time on that date.
        required_resources:     Number of personnel / resource units required.
        equipment:              Equipment needed for the maintenance.
        status:                 Current lifecycle status of the request.
        source:                 Name of the originating data source.
    """

    asset_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the railway asset",
    )
    asset_type: str = Field(
        ...,
        min_length=1,
        description="Category of the asset (e.g. Track, Signal, Bridge)",
    )
    location: str = Field(
        ...,
        min_length=1,
        description="Human-readable location or section description",
    )
    maintenance_type: str = Field(
        ...,
        min_length=1,
        description="Kind of maintenance (e.g. Preventive, Repair, Inspection)",
    )
    maintenance_required: bool = Field(
        ...,
        description="Whether maintenance is actually needed",
    )
    priority: Priority = Field(
        ...,
        description="Urgency level of the maintenance request",
    )
    duration_minutes: int = Field(
        ...,
        gt=0,
        description="Expected duration of the work in minutes",
    )
    requested_date: date = Field(
        ...,
        description="Date the maintenance was requested for",
    )
    preferred_start: time = Field(
        ...,
        description="Preferred start time on the requested date",
    )
    required_resources: int = Field(
        ...,
        gt=0,
        description="Number of personnel / resource units required",
    )
    equipment: str = Field(
        ...,
        min_length=1,
        description="Equipment needed for the maintenance",
    )
    status: MaintenanceStatus = Field(
        ...,
        description="Current lifecycle status of the request",
    )
    source: Optional[str] = Field(
        default=None,
        description="Name of the originating data source (e.g. 'smms')",
    )
    priority_enrichment: Optional[PriorityEnrichment] = Field(
        default=None,
        description="AI prioritization enrichment contract containing explainable factors and priority_value",
    )
    priority_value: Optional[float] = Field(
        default=None,
        description="Authoritative numerical priority score (extracted from priority_enrichment if available)",
    )

    # --- extra validators -------------------------------------------------

    @field_validator("duration_minutes")
    @classmethod
    def duration_must_be_positive(cls, value: int) -> int:
        """Ensure duration is a positive integer."""
        if value <= 0:
            raise ValueError("duration_minutes must be a positive integer")
        return value

    @field_validator("required_resources")
    @classmethod
    def resources_must_be_positive(cls, value: int) -> int:
        """Ensure required_resources is a positive integer."""
        if value <= 0:
            raise ValueError("required_resources must be a positive integer")
        return value

    model_config = {
        "str_strip_whitespace": True,
        "extra": "allow",
    }


# ---------------------------------------------------------------------------
# Phase 2 — Additional Enumerations
# ---------------------------------------------------------------------------

class TrainStatus(str, Enum):
    """Allowed operational statuses for a train."""
    RUNNING = "Running"
    DELAYED = "Delayed"
    SCHEDULED = "Scheduled"
    TERMINATED = "Terminated"
    CANCELLED = "Cancelled"


class BlockStatus(str, Enum):
    """Allowed statuses for a block/disconnection request."""
    REQUESTED = "Requested"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class BlockType(str, Enum):
    """Types of block/disconnection."""
    MAINTENANCE = "Maintenance"
    EMERGENCY = "Emergency"
    NON_INTERLOCKED = "Non-Interlocked"
    TRAFFIC = "Traffic"


# ---------------------------------------------------------------------------
# Phase 2 — Unified Train Record (TMS / TDMS)
# ---------------------------------------------------------------------------

class TrainRecord(BaseModel):
    """
    Canonical representation of a train's operational state.

    Produced by normalizing TMS and/or TDMS data.  When records from
    both sources refer to the same ``train_id``, they may be merged
    by the Merger.
    """

    train_id: str = Field(..., min_length=1, description="Unique train identifier")
    train_type: str = Field(..., min_length=1, description="Goods, Passenger, etc.")
    origin: str = Field(..., min_length=1, description="Origin station")
    destination: str = Field(..., min_length=1, description="Destination station")
    status: TrainStatus = Field(..., description="Current operational status")

    # Optional fields — may come from TMS, TDMS, or both
    current_station: Optional[str] = Field(default=None, description="Station the train is currently at")
    next_station: Optional[str] = Field(default=None, description="Next station in the journey")
    route_id: Optional[str] = Field(default=None, description="Route identifier (from TDMS)")
    priority: Optional[Priority] = Field(default=None, description="Operational priority (from TDMS)")

    scheduled_arrival: Optional[str] = Field(default=None, description="Scheduled arrival time (HH:MM)")
    scheduled_departure: Optional[str] = Field(default=None, description="Scheduled departure time (HH:MM)")
    actual_arrival: Optional[str] = Field(default=None, description="Actual arrival time (HH:MM)")
    actual_departure: Optional[str] = Field(default=None, description="Actual departure time (HH:MM)")
    expected_arrival: Optional[str] = Field(default=None, description="Expected arrival (TDMS)")
    expected_departure: Optional[str] = Field(default=None, description="Expected departure (TDMS)")

    source: Optional[str] = Field(default=None, description="Originating data source(s)")

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Phase 2 — Unified Movement Record (COA)
# ---------------------------------------------------------------------------

class MovementRecord(BaseModel):
    """
    Canonical representation of a corridor/section movement.

    Produced by normalizing COA data.  Describes whether a particular
    section of track is occupied, clear, or approaching.
    """

    train_id: str = Field(..., min_length=1, description="Train using this section")
    route_id: str = Field(..., min_length=1, description="Route identifier")
    section: str = Field(..., min_length=1, description="Track section (e.g. Chennai-Perambur)")
    direction: str = Field(..., min_length=1, description="Up or Down direction")
    movement_status: str = Field(..., min_length=1, description="Occupied, Clear, Approaching, Scheduled")
    entry_time: str = Field(..., description="Entry time into the section (HH:MM)")
    exit_time: str = Field(..., description="Exit time from the section (HH:MM)")
    line: str = Field(..., min_length=1, description="Main line or Loop")

    source: Optional[str] = Field(default=None, description="Originating data source")

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Phase 2 — Unified Block Record (BDMS)
# ---------------------------------------------------------------------------

class BlockRecord(BaseModel):
    """
    Canonical representation of a block/disconnection request.

    Produced by normalizing BDMS data.  Represents a planned or
    requested block on a section of railway for maintenance or other
    purposes.
    """

    block_id: str = Field(..., min_length=1, description="Unique block request identifier")
    location: str = Field(..., min_length=1, description="Location or section for the block")
    block_type: BlockType = Field(..., description="Type of block")
    requested_date: date = Field(..., description="Date the block is requested for")
    requested_start: str = Field(..., description="Requested start time (HH:MM)")
    requested_end: str = Field(..., description="Requested end time (HH:MM)")
    reason: str = Field(..., min_length=1, description="Reason for the block request")
    priority: Priority = Field(..., description="Priority of the block request")
    status: BlockStatus = Field(..., description="Current status of the block request")

    source: Optional[str] = Field(default=None, description="Originating data source")

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Phase 2 — Unified Timetable Record
# ---------------------------------------------------------------------------

class TimetableRecord(BaseModel):
    """
    Canonical representation of a single timetable entry.

    Each record represents one train's stop at one station.
    Multiple records form the full journey of a train.
    """

    train_id: str = Field(..., min_length=1, description="Train identifier")
    service_date: date = Field(..., description="Date of service")
    station_code: str = Field(..., min_length=1, description="Station code")
    arrival_time: Optional[str] = Field(default=None, description="Arrival time (HH:MM) or None for origin")
    departure_time: Optional[str] = Field(default=None, description="Departure time (HH:MM) or None for terminus")
    platform: Optional[int] = Field(default=None, gt=0, description="Platform number")
    sequence: int = Field(..., gt=0, description="Stop sequence number in the journey")

    source: Optional[str] = Field(default=None, description="Originating data source")

    model_config = {"str_strip_whitespace": True}
