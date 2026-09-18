"""
Block Planner package.

Exports the tactical BlockPlanner and canonical planning horizon contracts.
"""

from typing import Any

from backend.app.block_planner.schemas import (
    BlockPlanRequest,
    BlockPlanResult,
    CandidateWorkItem,
    CorridorAvailabilityWindow,
    DailySchedulingProblem,
    MonthlyPlan,
    MonthlyPlanItem,
    WeeklyPlan,
    WeeklyPlanItem,
)

__all__ = [
    "BlockPlanner",
    "BlockPlanRequest",
    "BlockPlanResult",
    "CandidateWorkItem",
    "CorridorAvailabilityWindow",
    "DailySchedulingProblem",
    "MonthlyPlan",
    "MonthlyPlanItem",
    "WeeklyPlan",
    "WeeklyPlanItem",
]


def __getattr__(name: str) -> Any:
    if name == "BlockPlanner":
        from backend.app.block_planner.planner import BlockPlanner
        return BlockPlanner
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

