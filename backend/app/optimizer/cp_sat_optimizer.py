"""
CP-SAT Maintenance Block Optimizer Engine (Phase 5).

Provides deterministic, multi-objective mathematical optimization for railway
maintenance possessions and block schedules using Google OR-Tools CP-SAT.

Includes Feature 3 capabilities:
- Runtime priority/urgency overrides
- Slot pinning to protect mobilized teams
- Mandatory task scheduling constraints
- Task exclusion/freezing for re-optimization runs
- Strategy presets (balanced, max_throughput, minimal_disruption, safety_priority)
- Re-optimization schedule churn and shift telemetry
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import logging
from pathlib import Path
import time as pytime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid
import yaml

from ortools.sat.python import cp_model

from backend.app.forecast.schemas import GoodsForecastItem
from backend.app.optimizer.constraints import (
    add_equipment_capacity_constraints,
    add_mandatory_scheduling_constraints,
    add_slot_assignment_constraints,
    add_track_overlap_constraints,
)
from backend.app.optimizer.objective import build_optimization_objective
from backend.app.optimizer.schemas import (
    ObjectiveWeights,
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
    OptimizedBlock,
    SolverStatistics,
    UnscheduledBlock,
)
from backend.app.scheduler.schemas import FeasibleSlot
from backend.app.scheduler.scheduler import (
    MaintenanceScheduler,
    PRIORITY_RANK,
    _calculate_duration_minutes,
    _format_minutes_to_time,
    _locations_match,
    _parse_time_to_minutes,
)
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

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "constraints.yaml"

# Feature 3 Strategy presets defining mathematical objective trade-offs
STRATEGY_PRESETS: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "weights": {
            "weight_scheduled": 10000,
            "weight_priority_critical": 5000,
            "weight_priority_high": 2500,
            "weight_priority_medium": 1000,
            "weight_priority_low": 200,
            "weight_preferred_deviation": 5,
            "weight_disruption": 50,
            "weight_resource_contention": 100,
        },
        "min_buffer_minutes": 15,
    },
    "max_throughput": {
        "weights": {
            "weight_scheduled": 25000,
            "weight_priority_critical": 3000,
            "weight_priority_high": 1500,
            "weight_priority_medium": 800,
            "weight_priority_low": 100,
            "weight_preferred_deviation": 1,
            "weight_disruption": 10,
            "weight_resource_contention": 50,
        },
        "min_buffer_minutes": 10,
    },
    "minimal_disruption": {
        "weights": {
            "weight_scheduled": 6000,
            "weight_priority_critical": 5000,
            "weight_priority_high": 2500,
            "weight_priority_medium": 1000,
            "weight_priority_low": 200,
            "weight_preferred_deviation": 40,
            "weight_disruption": 100,
            "weight_resource_contention": 100,
        },
        "min_buffer_minutes": 15,
    },
    "safety_priority": {
        "weights": {
            "weight_scheduled": 8000,
            "weight_priority_critical": 6000,
            "weight_priority_high": 3000,
            "weight_priority_medium": 1000,
            "weight_priority_low": 200,
            "weight_preferred_deviation": 10,
            "weight_disruption": 150,
            "weight_resource_contention": 150,
        },
        "min_buffer_minutes": 20,
    },
}


def load_constraints_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load constraints, capacities, and weights from YAML configuration file."""
    target_path = config_path or DEFAULT_CONFIG_PATH
    if target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.warning("Could not load config from %s: %s. Using defaults.", target_path, exc)

    return {
        "horizon": {"default_horizon_days": 7, "max_horizon_days": 30},
        "safety": {"buffer_minutes": 15, "min_block_duration_minutes": 30, "max_block_duration_minutes": 720},
        "resource_capacities": {
            "Track Tamper": 1,
            "Overhead Line Inspection Vehicle": 1,
            "OHE Car": 1,
            "Signal Testing Unit": 1,
            "Ballast Cleaner": 1,
            "Rail Crane": 1,
            "Tower Wagon": 2,
            "Welding Unit": 2,
            "General": 5,
        },
        "objective_weights": {
            "weight_scheduled": 10000,
            "weight_priority_critical": 5000,
            "weight_priority_high": 2500,
            "weight_priority_medium": 1000,
            "weight_priority_low": 200,
            "weight_preferred_deviation": 5,
            "weight_disruption": 50,
            "weight_resource_contention": 100,
        },
        "solver": {
            "time_limit_seconds": 30.0,
            "num_workers": 4,
            "random_seed": 42,
            "log_search_progress": False,
        },
    }


def _resolve_preset_weights_and_buffer(
    req: OptimizationRequest,
    default_weights: Dict[str, Any],
) -> Tuple[ObjectiveWeights, int]:
    """Resolve weights and buffer minutes applying strategy preset trade-offs."""
    buffer_mins = req.buffer_minutes
    preset_key = (req.strategy_preset or "balanced").lower()
    preset = STRATEGY_PRESETS.get(preset_key, STRATEGY_PRESETS["balanced"])

    if preset_key == "safety_priority":
        buffer_mins = max(buffer_mins, preset.get("min_buffer_minutes", 20))

    if req.weights:
        return req.weights, buffer_mins

    weight_dict = dict(preset.get("weights", default_weights))
    return ObjectiveWeights(**weight_dict), buffer_mins


def _apply_priority_override(
    req_id: str,
    original: Priority,
    overrides: Optional[Dict[str, str]],
) -> Priority:
    """Resolve runtime operator priority override for a maintenance task."""
    if not overrides or req_id not in overrides:
        return original
    override_val = overrides[req_id]
    for p in Priority:
        if p.value.lower() == override_val.lower():
            return p
    return original


def _parse_pinned_window(pinned_val: str, duration_minutes: int) -> Tuple[str, str]:
    """Parse pinned slot time string into start_time and end_time (HH:MM)."""
    clean = pinned_val.strip()
    if "-" in clean:
        parts = clean.split("-")
        return parts[0].strip(), parts[1].strip()
    s_min = _parse_time_to_minutes(clean) or 0
    e_min = s_min + duration_minutes
    return _format_minutes_to_time(s_min), _format_minutes_to_time(e_min)


class CP_SAT_Optimizer:
    """
    Core mathematical optimizer scheduling railway maintenance requests
    using Google OR-Tools CP-SAT.
    """

    def __init__(
        self,
        maintenance_records: Optional[List[MaintenanceRecord]] = None,
        block_records: Optional[List[BlockRecord]] = None,
        timetables: Optional[List[TimetableRecord]] = None,
        goods_forecasts: Optional[List[GoodsForecastItem]] = None,
        movements: Optional[List[MovementRecord]] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self.maintenance_records = maintenance_records or []
        self.block_records = block_records or []
        self.timetables = timetables or []
        self.goods_forecasts = goods_forecasts or []
        self.movements = movements or []
        self.config = load_constraints_config(config_path)

    def _collect_requests(
        self,
        req: OptimizationRequest,
        base_date: date,
        end_date: date,
    ) -> Tuple[List[Dict[str, Any]], List[UnscheduledBlock]]:
        """Collect and filter maintenance and block requests across horizon."""
        active: List[Dict[str, Any]] = []
        excluded: List[UnscheduledBlock] = []
        exclude_set = set(req.exclude_from_reopt or [])

        for m in self.maintenance_records:
            if not m.maintenance_required:
                continue
            m_id = m.asset_id
            m_db_id = str(getattr(m, "id", None) or "")
            if m_id in exclude_set or (m_db_id and m_db_id in exclude_set):
                excluded.append(self._make_excluded_block(m, m_id))
                continue
            if req.priority_filter and m.priority.value.lower() != req.priority_filter.lower():
                continue
            if req.location_filter and req.location_filter.lower() not in m.location.lower():
                continue
            if base_date <= m.requested_date < end_date:
                active.append(self._build_maint_request_dict(m, m_id, req.priority_overrides))

        for b in self.block_records:
            if b.status == BlockStatus.CANCELLED:
                continue
            b_id = b.block_id
            if b_id in exclude_set:
                excluded.append(self._make_excluded_block_record(b, b_id))
                continue
            if req.priority_filter and b.priority.value.lower() != req.priority_filter.lower():
                continue
            if req.location_filter and req.location_filter.lower() not in b.location.lower():
                continue
            if base_date <= b.requested_date < end_date:
                active.append(self._build_block_request_dict(b, b_id, req.priority_overrides))

        active.sort(
            key=lambda r: (PRIORITY_RANK.get(r["priority"], 1), r["duration_minutes"], r["request_id"]),
            reverse=True,
        )
        return active, excluded

    def _make_excluded_block(self, m: MaintenanceRecord, req_id: str) -> UnscheduledBlock:
        """Create unscheduled block record for an excluded maintenance request."""
        pref_str = m.preferred_start.strftime("%H:%M") if hasattr(m.preferred_start, "strftime") else str(m.preferred_start)
        return UnscheduledBlock(
            request_id=req_id,
            asset_id=m.asset_id,
            block_id=None,
            location=m.location,
            requested_date=m.requested_date,
            preferred_start=pref_str,
            duration_minutes=m.duration_minutes,
            priority=m.priority,
            equipment=m.equipment,
            required_resources=m.required_resources,
            reason="Excluded from re-optimization run by operator preference.",
        )

    def _make_excluded_block_record(self, b: BlockRecord, req_id: str) -> UnscheduledBlock:
        """Create unscheduled block record for an excluded existing block request."""
        dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
        return UnscheduledBlock(
            request_id=req_id,
            asset_id=None,
            block_id=b.block_id,
            location=b.location,
            requested_date=b.requested_date,
            preferred_start=b.requested_start,
            duration_minutes=dur,
            priority=b.priority,
            equipment=None,
            required_resources=1,
            reason="Excluded from re-optimization run by operator preference.",
        )

    def _build_maint_request_dict(
        self,
        m: MaintenanceRecord,
        req_id: str,
        overrides: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Construct normalized dictionary for a candidate maintenance request."""
        pref_str = m.preferred_start.strftime("%H:%M") if hasattr(m.preferred_start, "strftime") else str(m.preferred_start)
        eff_prio = _apply_priority_override(req_id, m.priority, overrides)
        return {
            "request_id": req_id,
            "asset_id": m.asset_id,
            "block_id": None,
            "location": m.location,
            "priority": eff_prio,
            "duration_minutes": m.duration_minutes,
            "requested_date": m.requested_date,
            "preferred_start": pref_str,
            "equipment": m.equipment,
            "required_resources": m.required_resources,
        }

    def _build_block_request_dict(
        self,
        b: BlockRecord,
        req_id: str,
        overrides: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Construct normalized dictionary for a candidate block request."""
        dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
        eff_prio = _apply_priority_override(req_id, b.priority, overrides)
        return {
            "request_id": req_id,
            "asset_id": None,
            "block_id": b.block_id,
            "location": b.location,
            "priority": eff_prio,
            "duration_minutes": dur,
            "requested_date": b.requested_date,
            "preferred_start": b.requested_start,
            "equipment": None,
            "required_resources": 1,
        }

    def _find_slots_for_single_request(
        self,
        scheduler: MaintenanceScheduler,
        r_item: Dict[str, Any],
        req: OptimizationRequest,
    ) -> List[FeasibleSlot]:
        """Find feasible candidate slots for a request, enforcing slot pinning if requested."""
        req_id = r_item["request_id"]
        r_date = r_item["requested_date"]
        slots = scheduler.find_feasible_slots(
            location=r_item["location"],
            duration_minutes=r_item["duration_minutes"],
            preferred_start=r_item["preferred_start"],
            target_date=r_date,
            max_slots=req.max_slots_per_request,
        )

        if not (req.pinned_slots and req_id in req.pinned_slots):
            return slots

        pin_val = req.pinned_slots[req_id]
        pin_start, pin_end = _parse_pinned_window(pin_val, r_item["duration_minutes"])
        matching = [s for s in slots if s.start_time == pin_start]
        if matching:
            return matching

        return [
            FeasibleSlot(
                slot_id=f"PINNED-{req_id}",
                location=r_item["location"],
                service_date=r_date,
                start_time=pin_start,
                end_time=pin_end,
                duration_minutes=r_item["duration_minutes"],
                fit_score=1.0,
                is_preferred_match=True,
            )
        ]

    def _generate_candidate_slots(
        self,
        scheduler: MaintenanceScheduler,
        active_requests: List[Dict[str, Any]],
        req: OptimizationRequest,
    ) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
        """Generate feasible candidate slots for active requests including pinned slots."""
        requests_to_slots: Dict[str, List[str]] = {}
        slot_metadata: Dict[str, Dict[str, Any]] = {}
        slot_counter = 1

        for r_item in active_requests:
            req_id = r_item["request_id"]
            requests_to_slots[req_id] = []
            slots = self._find_slots_for_single_request(scheduler, r_item, req)
            pref_mins = _parse_time_to_minutes(r_item["preferred_start"]) or 600

            for slot in slots:
                s_id = f"OPT-SLOT-{slot_counter:04d}"
                slot_counter += 1
                requests_to_slots[req_id].append(s_id)
                s_start = _parse_time_to_minutes(slot.start_time) or 0
                s_end = s_start + r_item["duration_minutes"]

                slot_metadata[s_id] = {
                    "slot_id": s_id,
                    "request_id": req_id,
                    "asset_id": r_item["asset_id"],
                    "block_id": r_item["block_id"],
                    "location": r_item["location"],
                    "service_date": r_item["requested_date"],
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                    "start_minutes": s_start,
                    "end_minutes": s_end,
                    "duration_minutes": r_item["duration_minutes"],
                    "preferred_start_minutes": pref_mins,
                    "fit_score": slot.fit_score,
                    "is_preferred_match": slot.is_preferred_match,
                    "priority": r_item["priority"],
                    "equipment": r_item["equipment"],
                    "required_resources": r_item["required_resources"],
                }

        return requests_to_slots, slot_metadata

    def _build_optimized_block(
        self,
        r_item: Dict[str, Any],
        sched_slot_id: str,
        meta: Dict[str, Any],
        is_pinned: bool,
        counter: int,
    ) -> OptimizedBlock:
        """Create an OptimizedBlock assignment from solver selection."""
        pref_mins = _parse_time_to_minutes(r_item["preferred_start"]) or 600
        dev_mins = abs(meta["start_minutes"] - pref_mins)
        is_shifted = (not is_pinned) and (dev_mins > 0)

        return OptimizedBlock(
            block_id=f"BLK-OPT-{counter:04d}",
            request_id=r_item["request_id"],
            asset_id=r_item["asset_id"],
            block_request_id=r_item["block_id"],
            location=r_item["location"],
            service_date=meta["service_date"],
            start_time=meta["start_time"],
            end_time=meta["end_time"],
            duration_minutes=r_item["duration_minutes"],
            priority=r_item["priority"],
            equipment=r_item["equipment"],
            required_resources=r_item["required_resources"],
            status="Scheduled",
            assigned_slot_id=sched_slot_id,
            fit_score=meta["fit_score"],
            is_preferred_match=meta["is_preferred_match"],
            deviation_minutes=dev_mins,
            is_pinned=is_pinned,
            is_shifted=is_shifted,
        )

    def _build_unscheduled_block(
        self,
        r_item: Dict[str, Any],
        s_ids: List[str],
    ) -> UnscheduledBlock:
        """Create an UnscheduledBlock diagnostic item."""
        reason = (
            "No feasible conflict-free time window available within timetable / traffic headroom."
            if not s_ids
            else "Preempted by higher-priority request or equipment capacity limits."
        )
        return UnscheduledBlock(
            request_id=r_item["request_id"],
            asset_id=r_item["asset_id"],
            block_id=r_item["block_id"],
            location=r_item["location"],
            requested_date=r_item["requested_date"],
            preferred_start=r_item["preferred_start"],
            duration_minutes=r_item["duration_minutes"],
            priority=r_item["priority"],
            equipment=r_item["equipment"],
            required_resources=r_item["required_resources"],
            reason=reason,
        )

    def _extract_results(
        self,
        solver: cp_model.CpSolver,
        slot_vars: Dict[Tuple[str, str], cp_model.IntVar],
        slot_metadata: Dict[str, Dict[str, Any]],
        active_requests: List[Dict[str, Any]],
        requests_to_slots: Dict[str, List[str]],
        solver_status: OptimizationStatus,
        req: OptimizationRequest,
    ) -> Tuple[List[OptimizedBlock], List[UnscheduledBlock]]:
        """Extract scheduled assignments and diagnostic unscheduled requests."""
        scheduled: List[OptimizedBlock] = []
        unscheduled: List[UnscheduledBlock] = []
        block_counter = 1
        pinned_keys = set(req.pinned_slots.keys() if req.pinned_slots else [])

        for r_item in active_requests:
            req_id = r_item["request_id"]
            s_ids = requests_to_slots.get(req_id, [])
            sched_slot_id: Optional[str] = None

            if solver_status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
                for s_id in s_ids:
                    var = slot_vars.get((req_id, s_id))
                    if var is not None and solver.Value(var) == 1:
                        sched_slot_id = s_id
                        break

            if sched_slot_id:
                meta = slot_metadata[sched_slot_id]
                is_pinned = req_id in pinned_keys
                block = self._build_optimized_block(r_item, sched_slot_id, meta, is_pinned, block_counter)
                scheduled.append(block)
                block_counter += 1
            else:
                unscheduled.append(self._build_unscheduled_block(r_item, s_ids))

        return scheduled, unscheduled

    def _build_model_constraints(
        self,
        model: cp_model.CpModel,
        slot_vars: Dict[Tuple[str, str], cp_model.IntVar],
        requests_to_slots: Dict[str, List[str]],
        slot_metadata: Dict[str, Dict[str, Any]],
        capacities: Dict[str, int],
        all_mandatory: Set[str],
    ) -> int:
        """Add CP-SAT assignment, track non-overlap, capacity, and mandatory constraints."""
        total_c = 0
        total_c += add_slot_assignment_constraints(model, slot_vars, requests_to_slots)
        total_c += add_track_overlap_constraints(model, slot_vars, slot_metadata)
        total_c += add_equipment_capacity_constraints(model, slot_vars, slot_metadata, capacities)
        if all_mandatory:
            total_c += add_mandatory_scheduling_constraints(model, slot_vars, all_mandatory, requests_to_slots)
        return total_c

    def _solve_model(
        self,
        model: cp_model.CpModel,
        req: OptimizationRequest,
    ) -> Tuple[cp_model.CpSolver, OptimizationStatus, float]:
        """Execute CP-SAT solver and map termination status."""
        solver = cp_model.CpSolver()
        cfg = self.config.get("solver", {})
        solver.parameters.max_time_in_seconds = req.time_limit_seconds or cfg.get("time_limit_seconds", 30.0)
        solver.parameters.num_workers = req.num_workers or cfg.get("num_workers", 4)
        solver.parameters.random_seed = cfg.get("random_seed", 42)
        solver.parameters.log_search_progress = cfg.get("log_search_progress", False)

        start_t = pytime.time()
        raw = solver.Solve(model)
        wall_time = round(pytime.time() - start_t, 4)

        status_map = {
            cp_model.OPTIMAL: OptimizationStatus.OPTIMAL,
            cp_model.FEASIBLE: OptimizationStatus.FEASIBLE,
            cp_model.INFEASIBLE: OptimizationStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: OptimizationStatus.MODEL_INVALID,
            cp_model.UNKNOWN: OptimizationStatus.UNKNOWN,
        }
        return solver, status_map.get(raw, OptimizationStatus.UNKNOWN), wall_time

    def _compute_statistics(
        self,
        solver: cp_model.CpSolver,
        solver_status: OptimizationStatus,
        scheduled_blocks: List[OptimizedBlock],
        unscheduled_blocks: List[UnscheduledBlock],
        total_requests: int,
        num_vars: int,
        num_constraints: int,
        wall_time: float,
    ) -> SolverStatistics:
        """Calculate solver performance metrics and re-optimization churn statistics."""
        num_pinned = sum(1 for b in scheduled_blocks if b.is_pinned)
        num_shifted = sum(1 for b in scheduled_blocks if b.is_shifted)
        unchanged = num_pinned + sum(1 for b in scheduled_blocks if not b.is_shifted and not b.is_pinned)
        stability_score = round(unchanged / total_requests, 3) if total_requests > 0 else 1.0

        return SolverStatistics(
            status=solver_status,
            objective_value=float(solver.ObjectiveValue()) if solver_status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE) else None,
            wall_time_seconds=wall_time,
            num_scheduled=len(scheduled_blocks),
            num_unscheduled=len(unscheduled_blocks),
            num_conflicts_avoided=num_constraints,
            total_requests=total_requests,
            num_variables=num_vars,
            num_constraints=num_constraints,
            num_branches=int(solver.NumBranches()) if hasattr(solver, "NumBranches") else 0,
            num_pinned=num_pinned,
            num_shifted=num_shifted,
            stability_score=stability_score,
        )


    def _create_scheduler(
        self,
        active_requests: List[Dict[str, Any]],
        req: OptimizationRequest,
        buffer_mins: int,
    ) -> MaintenanceScheduler:
        """Create a scheduler instance considering fixed and active block records."""
        active_ids = {r["block_id"] for r in active_requests if r["block_id"]}
        fixed = [b for b in self.block_records if b.block_id not in active_ids]
        return MaintenanceScheduler(
            maintenance_records=[],
            block_records=fixed,
            timetables=self.timetables,
            goods_forecasts=self.goods_forecasts if req.include_forecast else [],
            movements=self.movements,
            buffer_minutes=buffer_mins,
        )

    def _create_decision_variables(
        self,
        model: cp_model.CpModel,
        requests_to_slots: Dict[str, List[str]],
    ) -> Dict[Tuple[str, str], cp_model.IntVar]:
        """Create CP-SAT boolean decision variables for candidate slot assignments."""
        slot_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
        for req_id, s_ids in requests_to_slots.items():
            for s_id in s_ids:
                clean_name = f"x_{req_id}_{s_id}".replace("-", "_").replace(" ", "_")
                slot_vars[(req_id, s_id)] = model.NewBoolVar(clean_name)
        return slot_vars

    def optimize(
        self,
        request: Optional[OptimizationRequest] = None,
        mandatory_request_ids: Optional[Set[str]] = None,
    ) -> OptimizationResult:
        """Execute CP-SAT mathematical optimization over the requested horizon."""
        req = request or OptimizationRequest()
        base_date = req.target_date or date.today()
        horizon_days = max(1, min(30, req.horizon_days))
        end_date = base_date + timedelta(days=horizon_days)

        weights, buffer_mins = _resolve_preset_weights_and_buffer(req, self.config.get("objective_weights", {}))
        capacities = dict(self.config.get("resource_capacities", {}))
        if req.custom_capacities:
            capacities.update(req.custom_capacities)

        active_requests, excluded_blocks = self._collect_requests(req, base_date, end_date)
        scheduler = self._create_scheduler(active_requests, req, buffer_mins)
        requests_to_slots, slot_metadata = self._generate_candidate_slots(scheduler, active_requests, req)

        model = cp_model.CpModel()
        slot_vars = self._create_decision_variables(model, requests_to_slots)

        all_mandatory: Set[str] = set(mandatory_request_ids or set())
        if req.mandatory_request_ids:
            all_mandatory.update(req.mandatory_request_ids)
        if req.pinned_slots:
            active_ids = set(requests_to_slots.keys())
            all_mandatory.update(k for k in req.pinned_slots.keys() if k in active_ids)

        num_constraints = self._build_model_constraints(
            model, slot_vars, requests_to_slots, slot_metadata, capacities, all_mandatory
        )
        build_optimization_objective(model, slot_vars, slot_metadata, weights)

        solver, solver_status, wall_time = self._solve_model(model, req)
        scheduled, unscheduled = self._extract_results(
            solver, slot_vars, slot_metadata, active_requests, requests_to_slots, solver_status, req
        )
        unscheduled.extend(excluded_blocks)

        total_req_count = len(active_requests) + len(excluded_blocks)
        stats = self._compute_statistics(
            solver, solver_status, scheduled, unscheduled, total_req_count,
            len(slot_vars), num_constraints, wall_time
        )

        return OptimizationResult(
            plan_id=f"OPT-PLAN-{uuid.uuid4().hex[:8].upper()}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_date=base_date,
            horizon_days=horizon_days,
            status=solver_status,
            objective_value=stats.objective_value,
            solver_statistics=stats,
            scheduled_blocks=scheduled,
            unscheduled_blocks=unscheduled,
            phase="Phase 5 - CP-SAT Optimization",
            notes="Optimization rules and objective weights are prototype assumptions and NOT official railway operating rules.",
        )
