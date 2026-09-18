"""
Block Planner Facade for Railway Block Planner (Phase 4).

Coordinates the end-to-end Phase 4 workflow:
    GoodsTrainForecaster → MaintenanceScheduler → ConflictDetector → AutoResolver
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
from typing import List, Optional, Dict, Any, Set
import uuid
from sqlalchemy.orm import Session

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
from backend.app.database.repositories import (
    BlockRepository,
    MaintenanceRepository,
    MovementRepository,
    TimetableRepository,
    TrainRepository,
)
from backend.app.forecast.forecast import GoodsTrainForecaster
from backend.app.forecast.schemas import GoodsForecastItem, GoodsForecastResult
from backend.app.optimizer.schemas import OptimizationRequest, OptimizationResult
from backend.app.scheduler.auto_resolver import AutoResolver
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.scheduler.scheduler import (
    LOCATION_ALIASES,
    MaintenanceScheduler,
    PRIORITY_RANK,
    _calculate_duration_minutes,
    _locations_match,
)
from backend.app.scheduler.schemas import ConflictReport, ScheduleResult
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    MaintenanceRecord,
    MovementRecord,
    Priority,
    TimetableRecord,
    TrainRecord,
)

logger = logging.getLogger(__name__)


def _resolve_corridor(location: str) -> str:
    """
    Resolve a station or section description to a canonical corridor name using existing project aliases.
    """
    if not location:
        return "Unknown-Corridor"
    loc_lower = location.lower().strip()
    for corridor, aliases in LOCATION_ALIASES.items():
        if corridor in loc_lower or any(alias in loc_lower for alias in aliases):
            parts = corridor.split("-")
            return "-".join(p.capitalize() for p in parts)
    return location.strip().title()


class BlockPlanner:
    """
    Tactical Block Planner responsible for:
    1. Monthly Planning: Organizing work over a 30-day horizon into week buckets (1-5).
    2. Weekly Planning: Refining work into a 7-day horizon with target dates and constraints.
    3. Daily Problem Preparation: Producing canonical DailySchedulingProblem contracts for Scheduler.

    Decoupled from CP-SAT mathematical optimization (delegated to downstream Scheduler/Optimizer).
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        trains: Optional[List[TrainRecord]] = None,
        movements: Optional[List[MovementRecord]] = None,
        timetables: Optional[List[TimetableRecord]] = None,
        maintenance_records: Optional[List[MaintenanceRecord]] = None,
        block_records: Optional[List[BlockRecord]] = None,
    ) -> None:
        self.db = db
        self.trains = trains
        self.movements = movements
        self.timetables = timetables
        self.maintenance_records = maintenance_records
        self.block_records = block_records

    def _ensure_data_loaded(self) -> None:
        """Load data from database repositories if not provided in constructor."""
        if self.db:
            if self.trains is None:
                self.trains = [t.to_pydantic() for t in TrainRepository(self.db).get_all(limit=1000)]
            if self.movements is None:
                self.movements = [m.to_pydantic() for m in MovementRepository(self.db).get_all(limit=1000)]
            if self.timetables is None:
                self.timetables = [tt.to_pydantic() for tt in TimetableRepository(self.db).get_all(limit=1000)]
            if self.maintenance_records is None:
                self.maintenance_records = [m.to_pydantic() for m in MaintenanceRepository(self.db).get_all(limit=1000)]
            if self.block_records is None:
                self.block_records = [b.to_pydantic() for b in BlockRepository(self.db).get_all(limit=1000)]
        else:
            self.trains = self.trains or []
            self.movements = self.movements or []
            self.timetables = self.timetables or []
            self.maintenance_records = self.maintenance_records or []
            self.block_records = self.block_records or []

    # -----------------------------------------------------------------------
    # Phase 2 — Monthly Planning
    # -----------------------------------------------------------------------

    def generate_monthly_plan(
        self,
        target_date: Optional[date] = None,
        horizon_days: int = 30,
    ) -> MonthlyPlan:
        """
        Organize maintenance requirements over a 30-day monthly planning horizon.
        Assigns work items into weekly buckets (1 to 5) and aggregates corridor volumes.
        Preserves priority, estimated duration, location/corridor, asset, and crew/equipment.
        """
        self._ensure_data_loaded()
        start_d = target_date or date.today()
        end_d = start_d + timedelta(days=horizon_days)

        items: List[MonthlyPlanItem] = []
        corridor_volume: Dict[str, Dict[str, int]] = {}
        weekly_volume: Dict[str, Dict[str, int]] = {
            f"Week {w}": {"items_count": 0, "duration_minutes": 0} for w in range(1, 6)
        }

        # 1. Collect from maintenance records
        for m in self.maintenance_records:
            if not m.maintenance_required:
                continue
            if start_d <= m.requested_date < end_d:
                day_offset = (m.requested_date - start_d).days
                week_bucket = min(5, max(1, (day_offset // 7) + 1))
                corridor = _resolve_corridor(m.location)
                dur = m.duration_minutes

                item = MonthlyPlanItem(
                    work_id=f"MNT-{m.asset_id}",
                    month_bucket=m.requested_date.strftime("%Y-%m"),
                    week_bucket=week_bucket,
                    corridor=corridor,
                    estimated_duration_minutes=dur,
                    priority=m.priority,
                    asset_id=m.asset_id,
                    asset_type=m.asset_type,
                    location=m.location,
                    maintenance_type=m.maintenance_type,
                    required_resources=m.required_resources,
                    equipment=m.equipment,
                    status="Planned",
                    description=f"{m.maintenance_type} for {m.asset_id} at {m.location}",
                )
                items.append(item)

                corridor_volume.setdefault(corridor, {"items_count": 0, "duration_minutes": 0})
                corridor_volume[corridor]["items_count"] += 1
                corridor_volume[corridor]["duration_minutes"] += dur

                w_key = f"Week {week_bucket}"
                weekly_volume[w_key]["items_count"] += 1
                weekly_volume[w_key]["duration_minutes"] += dur

        # 2. Collect from block records
        for b in self.block_records:
            if b.status == BlockStatus.CANCELLED:
                continue
            if start_d <= b.requested_date < end_d:
                day_offset = (b.requested_date - start_d).days
                week_bucket = min(5, max(1, (day_offset // 7) + 1))
                corridor = _resolve_corridor(b.location)
                dur = _calculate_duration_minutes(b.requested_start, b.requested_end)

                item = MonthlyPlanItem(
                    work_id=f"BLK-{b.block_id}",
                    month_bucket=b.requested_date.strftime("%Y-%m"),
                    week_bucket=week_bucket,
                    corridor=corridor,
                    estimated_duration_minutes=dur,
                    priority=b.priority,
                    asset_id=None,
                    asset_type="Block Possession",
                    location=b.location,
                    maintenance_type=b.block_type.value if hasattr(b.block_type, "value") else str(b.block_type),
                    required_resources=1,
                    equipment=None,
                    status="Planned",
                    description=b.reason or f"Block possession {b.block_id}",
                )
                items.append(item)

                corridor_volume.setdefault(corridor, {"items_count": 0, "duration_minutes": 0})
                corridor_volume[corridor]["items_count"] += 1
                corridor_volume[corridor]["duration_minutes"] += dur

                w_key = f"Week {week_bucket}"
                weekly_volume[w_key]["items_count"] += 1
                weekly_volume[w_key]["duration_minutes"] += dur

        # Deterministic sorting: week_bucket ascending, priority descending, duration descending, work_id
        items.sort(
            key=lambda it: (
                it.week_bucket,
                -PRIORITY_RANK.get(it.priority, 1) if it.priority else -1,
                -it.estimated_duration_minutes,
                it.work_id,
            )
        )

        total_vol = sum(it.estimated_duration_minutes for it in items)
        plan_id = f"MPLAN-{uuid.uuid4().hex[:8].upper()}"

        return MonthlyPlan(
            plan_id=plan_id,
            planning_month=start_d.strftime("%Y-%m"),
            start_date=start_d,
            end_date=end_d,
            horizon_days=horizon_days,
            generated_at=datetime.now(timezone.utc).isoformat(),
            corridor_summaries=corridor_volume,
            total_maintenance_volume=total_vol,
            total_items=len(items),
            weekly_breakdown=weekly_volume,
            items=items,
            metadata={"planner_version": "2.0.0", "source": "BlockPlanner"},
        )

    # -----------------------------------------------------------------------
    # Phase 2 — Weekly Planning
    # -----------------------------------------------------------------------

    def generate_weekly_plan(
        self,
        target_date: Optional[date] = None,
        horizon_days: int = 7,
    ) -> WeeklyPlan:
        """
        Refine maintenance requirements into a 7-day weekly horizon.
        Organizes work by specific target service date, preserving priority, asset context,
        equipment/resource requirements, and operational constraints.
        """
        self._ensure_data_loaded()
        start_d = target_date or date.today()
        end_d = start_d + timedelta(days=horizon_days)

        items: List[WeeklyPlanItem] = []
        daily_breakdown: Dict[str, int] = {}
        corridor_summaries: Dict[str, Dict[str, int]] = {}

        # 1. Maintenance records
        for m in self.maintenance_records:
            if not m.maintenance_required:
                continue
            if start_d <= m.requested_date < end_d:
                corridor = _resolve_corridor(m.location)
                pref_str = (
                    m.preferred_start.strftime("%H:%M")
                    if hasattr(m.preferred_start, "strftime")
                    else str(m.preferred_start)
                )
                is_mandatory = (m.priority == Priority.CRITICAL)

                compat: List[str] = []
                if m.asset_type:
                    compat.append(f"{m.asset_type} standard operating safety clearance")

                constraints: List[str] = []
                if m.equipment:
                    constraints.append(f"Requires {m.equipment}")

                item = WeeklyPlanItem(
                    work_id=f"MNT-{m.asset_id}",
                    target_date=m.requested_date,
                    corridor=corridor,
                    location=m.location,
                    estimated_duration_minutes=m.duration_minutes,
                    asset_id=m.asset_id,
                    asset_type=m.asset_type,
                    block_id=None,
                    asset_compatibility_requirements=compat,
                    required_resources=m.required_resources,
                    required_equipment=m.equipment,
                    priority=m.priority,
                    preferred_start=pref_str,
                    constraints=constraints,
                    is_mandatory=is_mandatory,
                    is_pinned=False,
                )
                items.append(item)

                d_str = m.requested_date.isoformat()
                daily_breakdown[d_str] = daily_breakdown.get(d_str, 0) + 1

                corridor_summaries.setdefault(corridor, {"items_count": 0, "total_duration": 0})
                corridor_summaries[corridor]["items_count"] += 1
                corridor_summaries[corridor]["total_duration"] += m.duration_minutes

        # 2. Block records
        for b in self.block_records:
            if b.status == BlockStatus.CANCELLED:
                continue
            if start_d <= b.requested_date < end_d:
                corridor = _resolve_corridor(b.location)
                dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
                is_mandatory = (b.priority == Priority.CRITICAL)

                item = WeeklyPlanItem(
                    work_id=f"BLK-{b.block_id}",
                    target_date=b.requested_date,
                    corridor=corridor,
                    location=b.location,
                    estimated_duration_minutes=dur,
                    asset_id=None,
                    asset_type="Block",
                    block_id=b.block_id,
                    asset_compatibility_requirements=[],
                    required_resources=1,
                    required_equipment=None,
                    priority=b.priority,
                    preferred_start=b.requested_start,
                    constraints=[f"Block type: {b.block_type.value if hasattr(b.block_type, 'value') else b.block_type}"],
                    is_mandatory=is_mandatory,
                    is_pinned=False,
                )
                items.append(item)

                d_str = b.requested_date.isoformat()
                daily_breakdown[d_str] = daily_breakdown.get(d_str, 0) + 1

                corridor_summaries.setdefault(corridor, {"items_count": 0, "total_duration": 0})
                corridor_summaries[corridor]["items_count"] += 1
                corridor_summaries[corridor]["total_duration"] += dur

        # Sort: target_date ascending, priority descending, duration descending, work_id
        items.sort(
            key=lambda it: (
                it.target_date,
                -PRIORITY_RANK.get(it.priority, 1) if it.priority else -1,
                -it.estimated_duration_minutes,
                it.work_id,
            )
        )

        total_dur = sum(it.estimated_duration_minutes for it in items)
        plan_id = f"WPLAN-{uuid.uuid4().hex[:8].upper()}"

        return WeeklyPlan(
            plan_id=plan_id,
            start_date=start_d,
            end_date=end_d,
            horizon_days=horizon_days,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_items=len(items),
            total_duration_minutes=total_dur,
            daily_breakdown=daily_breakdown,
            corridor_summaries=corridor_summaries,
            items=items,
            metadata={"planner_version": "2.0.0", "source": "BlockPlanner"},
        )

    # -----------------------------------------------------------------------
    # Phase 2 — Daily Problem Preparation (Block Planner → Scheduler Boundary)
    # -----------------------------------------------------------------------

    def prepare_daily_problem(
        self,
        target_date: Optional[date] = None,
        buffer_minutes: int = 15,
        priority_filter: Optional[str] = None,
        location_filter: Optional[str] = None,
        include_forecast: bool = True,
    ) -> DailySchedulingProblem:
        """
        Transform selected daily work and operational information into the canonical
        DailySchedulingProblem interface contract for the Scheduler.
        Decoupled from CP-SAT and heuristic matching logic.
        """
        self._ensure_data_loaded()
        target_d = target_date or date.today()

        candidate_works: List[CandidateWorkItem] = []
        active_corridors: Set[str] = set()

        # 1. Build CandidateWorkItems from maintenance records
        for m in self.maintenance_records:
            if m.requested_date == target_d and m.maintenance_required:
                if priority_filter and m.priority.value.lower() != priority_filter.lower():
                    continue
                if location_filter and location_filter.lower() not in m.location.lower():
                    continue

                pref_str = (
                    m.preferred_start.strftime("%H:%M")
                    if hasattr(m.preferred_start, "strftime")
                    else str(m.preferred_start)
                )
                corridor = _resolve_corridor(m.location)
                active_corridors.add(corridor)

                c_work = CandidateWorkItem(
                    work_id=f"MNT-{m.asset_id}",
                    location=m.location,
                    required_duration_minutes=m.duration_minutes,
                    asset_id=m.asset_id,
                    asset_type=m.asset_type,
                    corridor=corridor,
                    maintenance_type=m.maintenance_type,
                    required_resources=m.required_resources,
                    required_equipment=m.equipment,
                    priority=m.priority,
                    preferred_start=pref_str,
                    preferred_date=m.requested_date,
                    constraints=[f"Equipment: {m.equipment}"] if m.equipment else [],
                    is_mandatory=(m.priority == Priority.CRITICAL),
                    is_pinned=False,
                )
                candidate_works.append(c_work)

        # 2. Build CandidateWorkItems from block records
        for b in self.block_records:
            if b.requested_date == target_d and b.status != BlockStatus.CANCELLED:
                if priority_filter and b.priority.value.lower() != priority_filter.lower():
                    continue
                if location_filter and location_filter.lower() not in b.location.lower():
                    continue

                corridor = _resolve_corridor(b.location)
                dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
                active_corridors.add(corridor)

                c_work = CandidateWorkItem(
                    work_id=f"BLK-{b.block_id}",
                    location=b.location,
                    required_duration_minutes=dur,
                    asset_id=None,
                    asset_type="Block",
                    corridor=corridor,
                    maintenance_type=b.block_type.value if hasattr(b.block_type, "value") else str(b.block_type),
                    required_resources=1,
                    required_equipment=None,
                    priority=b.priority,
                    preferred_start=b.requested_start,
                    preferred_date=b.requested_date,
                    constraints=[f"Block Type: {b.block_type.value if hasattr(b.block_type, 'value') else b.block_type}"],
                    is_mandatory=(b.priority == Priority.CRITICAL),
                    is_pinned=False,
                )
                candidate_works.append(c_work)

        # Sort candidate works deterministically (Critical priority first, duration desc, work_id)
        candidate_works.sort(
            key=lambda w: (
                -PRIORITY_RANK.get(w.priority, 1) if w.priority else -1,
                -w.required_duration_minutes,
                w.work_id,
            )
        )

        # 3. Available corridor / block windows
        available_windows: List[CorridorAvailabilityWindow] = []
        win_idx = 1
        if not active_corridors:
            active_corridors = {"Chennai-Arakkonam"}

        for corr in sorted(active_corridors):
            # Standard night possession window
            win = CorridorAvailabilityWindow(
                window_id=f"WIN-{target_d.strftime('%Y%m%d')}-{win_idx:02d}",
                corridor=corr,
                service_date=target_d,
                start_time="01:00",
                end_time="05:00",
                duration_minutes=240,
                status="Available",
                restrictions=["Standard night maintenance headway"],
                capacity_info={"max_parallel_blocks": 2},
                max_parallel_works=2,
            )
            available_windows.append(win)
            win_idx += 1

        # Also add any already-approved blocks for target_date as established windows
        for b in self.block_records:
            if b.requested_date == target_d and b.status == BlockStatus.APPROVED:
                dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
                win = CorridorAvailabilityWindow(
                    window_id=f"WIN-APPR-{b.block_id}",
                    corridor=_resolve_corridor(b.location),
                    service_date=target_d,
                    start_time=b.requested_start,
                    end_time=b.requested_end,
                    duration_minutes=dur,
                    block_id=b.block_id,
                    section=b.location,
                    status="Available",
                    restrictions=[f"Approved possession for {b.reason}"],
                    capacity_info={"max_parallel_blocks": 1},
                    max_parallel_works=1,
                )
                available_windows.append(win)

        # 4. Timetable constraints (Passenger trains on target_date and next day buffer)
        next_d = target_d + timedelta(days=1)
        timetable_constraints: List[Dict[str, Any]] = []
        for tt in self.timetables:
            if tt.service_date in (target_d, next_d):
                timetable_constraints.append({
                    "train_id": tt.train_id,
                    "service_date": tt.service_date.isoformat(),
                    "station_code": tt.station_code,
                    "arrival_time": tt.arrival_time,
                    "departure_time": tt.departure_time,
                    "sequence": tt.sequence,
                })

        # 5. Goods train forecast windows
        goods_forecast_windows: List[Dict[str, Any]] = []
        if include_forecast and self.trains and (self.movements or self.timetables):
            forecaster = GoodsTrainForecaster(
                trains=self.trains,
                movements=self.movements,
                timetables=self.timetables,
            )
            fc_res = forecaster.predict(target_date=target_d, horizon_hours=24)
            for fc in fc_res.forecasts:
                goods_forecast_windows.append({
                    "train_id": fc.train_id,
                    "service_date": fc.service_date.isoformat(),
                    "section": fc.section,
                    "forecasted_entry": fc.forecasted_entry,
                    "forecasted_exit": fc.forecasted_exit,
                    "confidence": fc.confidence,
                })

        # 6. Operational restrictions
        operational_restrictions: List[str] = [
            f"Safety headway buffer: {buffer_minutes} minutes",
            "OHE power isolation clearance required for overhead traction works",
            "Single line working protocol applies during full block possessions",
        ]

        problem_id = f"PROB-{target_d.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        return DailySchedulingProblem(
            problem_id=problem_id,
            target_date=target_d,
            candidate_works=candidate_works,
            available_windows=available_windows,
            timetable_constraints=timetable_constraints,
            goods_train_forecast_windows=goods_forecast_windows,
            operational_restrictions=operational_restrictions,
            buffer_minutes=buffer_minutes,
            metadata={
                "planner_version": "2.0.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_candidate_works": len(candidate_works),
                "total_available_windows": len(available_windows),
            },
        )

    # -----------------------------------------------------------------------
    # Legacy Facade Methods (Preserved for backward compatibility)
    # -----------------------------------------------------------------------

    def generate_plan(self, request: Optional[BlockPlanRequest] = None) -> BlockPlanResult:
        """
        [Legacy Facade - Phase 4]
        Execute end-to-end Phase 4 block planning orchestrating:
        GoodsTrainForecaster → MaintenanceScheduler → ConflictDetector → AutoResolver.
        """
        req = request or BlockPlanRequest()
        target_d = req.target_date or date.today()

        self._ensure_data_loaded()

        forecast_result: Optional[GoodsForecastResult] = None
        forecast_items: List[GoodsForecastItem] = []
        forecast_summary: Optional[dict] = None

        # Step 1: Goods Train Forecast
        if req.include_forecast:
            forecaster = GoodsTrainForecaster(
                trains=self.trains,
                movements=self.movements,
                timetables=self.timetables,
            )
            forecast_result = forecaster.predict(target_date=target_d, horizon_hours=24)
            forecast_items = forecast_result.forecasts
            forecast_summary = {
                "total_trains_forecasted": forecast_result.total_trains_forecasted,
                "total_section_windows": forecast_result.total_section_windows,
                "average_confidence": forecast_result.average_confidence,
                "summary_by_section": forecast_result.summary_by_section,
            }

        # Step 2: Maintenance Scheduler
        scheduler = MaintenanceScheduler(
            maintenance_records=self.maintenance_records,
            block_records=self.block_records,
            timetables=self.timetables,
            goods_forecasts=forecast_items,
            movements=self.movements,
            buffer_minutes=req.buffer_minutes,
        )
        schedule_result = scheduler.schedule(
            target_date=target_d,
            priority_filter=req.priority_filter,
            location_filter=req.location_filter,
        )

        # Step 3: Conflict Detection & Resolution
        conflict_report: Optional[ConflictReport] = None
        resolutions: List[dict] = []

        if req.include_conflicts:
            detector = ConflictDetector(
                trains=self.trains,
                timetables=self.timetables,
                goods_forecasts=forecast_items,
                movements=self.movements,
                maintenance_records=self.maintenance_records,
                block_records=self.block_records,
                buffer_minutes=req.buffer_minutes,
            )
            conflict_report = detector.detect_conflicts(
                target_date=target_d,
                proposed_schedule=schedule_result,
            )

            resolver = AutoResolver()
            resolutions = resolver.generate_resolution_plan(conflict_report)

        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

        return BlockPlanResult(
            plan_id=plan_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_date=target_d,
            phase="Phase 4 - Forecast + Scheduler + Conflict Detection",
            forecast_summary=forecast_summary,
            schedule=schedule_result,
            conflict_report=conflict_report,
            resolution_recommendations=resolutions,
        )

    def optimize_plan(self, request: Optional[OptimizationRequest] = None) -> OptimizationResult:
        """
        [Legacy Facade - Phase 5]
        Delegates CP-SAT mathematical optimization to CP_SAT_Optimizer.
        Preserved for backward compatibility with existing Phase 5 endpoints.
        """
        from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer

        req = request or OptimizationRequest()
        target_d = req.target_date or date.today()

        self._ensure_data_loaded()

        forecast_items: List[GoodsForecastItem] = []
        if req.include_forecast:
            forecaster = GoodsTrainForecaster(
                trains=self.trains,
                movements=self.movements,
                timetables=self.timetables,
            )
            for d_offset in range(req.horizon_days):
                day_date = target_d + timedelta(days=d_offset)
                fc_res = forecaster.predict(target_date=day_date, horizon_hours=24)
                forecast_items.extend(fc_res.forecasts)

        optimizer = CP_SAT_Optimizer(
            maintenance_records=self.maintenance_records,
            block_records=self.block_records,
            timetables=self.timetables,
            goods_forecasts=forecast_items,
            movements=self.movements,
            trains=self.trains,
        )

        return optimizer.optimize(request=req)


