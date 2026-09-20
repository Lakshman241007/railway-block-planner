"""
Application Service Layer for Railway Block Planner.

Orchestrates the canonical planning and optimization pipeline:
    API Request
        ↓
    Block Planner (tactical planning & daily problem preparation)
        ↓
    Daily Scheduler (window auditing, candidate matching, CP-SAT optimization)
        ↓
    DailyScheduleResult

The service acts strictly as an orchestrator. Domain logic, data retrieval,
forecasting, and constraint formulation remain encapsulated inside BlockPlanner
and DailyScheduler.
"""

from __future__ import annotations

import logging
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.block_planner.planner import BlockPlanner
from backend.app.block_planner.schemas import (
    DailyProblemRequest,
    DailySchedulingProblem,
    MonthlyPlan,
    MonthlyPlanRequest,
    WeeklyPlan,
    WeeklyPlanRequest,
)
from backend.app.scheduler.scheduler import DailyScheduler
from backend.app.scheduler.schemas import DailyScheduleResult

logger = logging.getLogger(__name__)


class SchedulingService:
    """
    Application service orchestrating tactical maintenance planning,
    daily problem formulation, and CP-SAT mathematical optimization.
    """

    @staticmethod
    def generate_monthly_plan(
        request: MonthlyPlanRequest,
        db: Optional[Session] = None,
    ) -> MonthlyPlan:
        """Orchestrate 30-day tactical monthly plan via BlockPlanner."""
        planner = BlockPlanner(db=db)
        return planner.generate_monthly_plan(
            target_date=request.target_date,
            horizon_days=request.horizon_days,
        )

    @staticmethod
    def generate_weekly_plan(
        request: WeeklyPlanRequest,
        db: Optional[Session] = None,
    ) -> WeeklyPlan:
        """Orchestrate 7-day tactical weekly plan via BlockPlanner."""
        planner = BlockPlanner(db=db)
        return planner.generate_weekly_plan(
            target_date=request.target_date,
            horizon_days=request.horizon_days,
        )

    @staticmethod
    def prepare_daily_problem(
        request: DailyProblemRequest,
        db: Optional[Session] = None,
    ) -> DailySchedulingProblem:
        """Orchestrate canonical DailySchedulingProblem formulation via BlockPlanner."""
        planner = BlockPlanner(db=db)
        return planner.prepare_daily_problem(
            target_date=request.target_date,
            buffer_minutes=request.buffer_minutes,
            priority_filter=request.priority_filter,
            location_filter=request.location_filter,
            include_forecast=request.include_forecast,
        )

    @staticmethod
    def schedule_daily(
        problem: DailySchedulingProblem,
        db: Optional[Session] = None,
    ) -> DailyScheduleResult:
        """
        Orchestrate the canonical daily scheduling workflow:
        1. If the request does not supply candidate works and available windows,
           delegate daily problem formulation to BlockPlanner.
        2. Delegate daily availability auditing, candidate matching, and CP-SAT
           mathematical optimization to DailyScheduler.
        3. Return canonical DailyScheduleResult.
        """
        # Step 1: If problem is unpopulated and DB session exists, delegate to BlockPlanner
        if not problem.candidate_works and not problem.available_windows and db is not None:
            planner = BlockPlanner(db=db)
            problem = planner.prepare_daily_problem(
                target_date=problem.target_date,
                buffer_minutes=problem.buffer_minutes,
            )

        # Step 2: Delegate scheduling and optimization to DailyScheduler
        scheduler = DailyScheduler(buffer_minutes=problem.buffer_minutes)
        return scheduler.schedule_daily(problem=problem, invoke_solver=True)
