"""
Scheduler package.

Exports the MaintenanceScheduler, DailyScheduler alias, and scheduling contracts.
"""

from typing import Any

from backend.app.scheduler.schemas import (
    ConflictItem,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
    CorridorAvailabilityWindow,
    DailyAvailabilityReport,
    DailyScheduleResult,
    FeasibleSlot,
    MaintenanceScheduleItem,
    ScheduleRequest,
    ScheduleResult,
    WorkBlockMatch,
    WorkMatchReport,
)

__all__ = [
    "MaintenanceScheduler",
    "DailyScheduler",
    "CandidateWorkItem",
    "ConflictItem",
    "ConflictReport",
    "ConflictSeverity",
    "ConflictType",
    "CorridorAvailabilityWindow",
    "DailyAvailabilityReport",
    "DailyScheduleResult",
    "DailySchedulingProblem",
    "FeasibleSlot",
    "MaintenanceScheduleItem",
    "ScheduleRequest",
    "ScheduleResult",
    "WorkBlockMatch",
    "WorkMatchReport",
]


def __getattr__(name: str) -> Any:
    if name in ("MaintenanceScheduler", "DailyScheduler"):
        from backend.app.scheduler.scheduler import DailyScheduler, MaintenanceScheduler

        return DailyScheduler if name == "DailyScheduler" else MaintenanceScheduler
    if name in ("CandidateWorkItem", "DailySchedulingProblem"):
        import backend.app.block_planner.schemas as bps

        return getattr(bps, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

