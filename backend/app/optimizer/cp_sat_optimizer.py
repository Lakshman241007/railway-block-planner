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
            "weight_priority_value": 50,
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
            "weight_priority_value": 30,
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
            "weight_priority_value": 50,
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
            "weight_priority_value": 60,
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
    overrides: Optional[Dict[str, Any]],
) -> Priority:
    """Resolve runtime operator priority override for a maintenance task."""
    if not overrides or req_id not in overrides:
        return original
    override_val = overrides[req_id]
    if isinstance(override_val, Priority):
        return override_val
    val_str = str(override_val).strip()
    for p in Priority:
        if p.value.lower() == val_str.lower():
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
        trains: Optional[List[TrainRecord]] = None,
    ) -> None:
        self.maintenance_records = maintenance_records or []
        self.block_records = block_records or []
        self.timetables = timetables or []
        self.goods_forecasts = goods_forecasts or []
        self.movements = movements or []
        self.trains = trains or []
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

        # Ingest candidate works from OptimizationRequest (Phase 4 Daily Scheduler pipeline)
        existing_ids = {r["request_id"] for r in active}
        if req.candidate_works:
            for w in req.candidate_works:
                w_id = getattr(w, "work_id", None) or (w.get("work_id") if isinstance(w, dict) else str(w))
                if not w_id or w_id in existing_ids or w_id in exclude_set:
                    continue
                w_loc = getattr(w, "location", None) or (w.get("location") if isinstance(w, dict) else "")
                w_prio = getattr(w, "priority", None) or (w.get("priority") if isinstance(w, dict) else Priority.MEDIUM)
                if isinstance(w_prio, str):
                    try:
                        w_prio = Priority(w_prio)
                    except Exception:
                        w_prio = Priority.MEDIUM
                if req.priority_filter and w_prio.value.lower() != req.priority_filter.lower():
                    continue
                if req.location_filter and req.location_filter.lower() not in w_loc.lower():
                    continue

                w_date = getattr(w, "preferred_date", None) or (w.get("preferred_date") if isinstance(w, dict) else None) or base_date
                w_start = getattr(w, "preferred_start", None) or (w.get("preferred_start") if isinstance(w, dict) else None) or "00:00"
                w_dur = getattr(w, "required_duration_minutes", None) or (w.get("required_duration_minutes") if isinstance(w, dict) else 60)
                w_res = getattr(w, "required_resources", None) or (w.get("required_resources") if isinstance(w, dict) else 1)
                w_equip = getattr(w, "equipment", None) or (w.get("equipment") if isinstance(w, dict) else None)
                w_asset = getattr(w, "asset_id", None) or (w.get("asset_id") if isinstance(w, dict) else None) or w_id

                eff_prio = _apply_priority_override(w_id, w_prio, req.priority_overrides)
                p_val = getattr(w, "priority_value", None) or (w.get("priority_value") if isinstance(w, dict) else None)
                if p_val is None and req.priority_overrides and w_id in req.priority_overrides:
                    try:
                        p_val = float(req.priority_overrides[w_id])
                    except (ValueError, TypeError):
                        pass
                item = {
                    "request_id": w_id,
                    "asset_id": w_asset,
                    "block_id": None,
                    "location": w_loc,
                    "priority": eff_prio,
                    "duration_minutes": w_dur,
                    "requested_date": w_date,
                    "preferred_start": str(w_start),
                    "equipment": w_equip,
                    "required_resources": w_res,
                    "priority_value": p_val,
                    "priority_enrichment": getattr(w, "priority_enrichment", None) or (w.get("priority_enrichment") if isinstance(w, dict) else None),
                }
                active.append(item)
                existing_ids.add(w_id)

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
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Construct normalized dictionary for a candidate maintenance request."""
        pref_str = m.preferred_start.strftime("%H:%M") if hasattr(m.preferred_start, "strftime") else str(m.preferred_start)
        eff_prio = _apply_priority_override(req_id, m.priority, overrides)
        p_val = getattr(m, "priority_value", None)
        if p_val is None and overrides and req_id in overrides:
            try:
                p_val = float(overrides[req_id])
            except (ValueError, TypeError):
                pass
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
            "priority_value": p_val,
            "priority_enrichment": getattr(m, "priority_enrichment", None),
        }

    def _build_block_request_dict(
        self,
        b: BlockRecord,
        req_id: str,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Construct normalized dictionary for a candidate block request."""
        dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
        eff_prio = _apply_priority_override(req_id, b.priority, overrides)
        p_val = getattr(b, "priority_value", None)
        if p_val is None and overrides and req_id in overrides:
            try:
                p_val = float(overrides[req_id])
            except (ValueError, TypeError):
                pass
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
            "priority_value": p_val,
            "priority_enrichment": getattr(b, "priority_enrichment", None),
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

        windows_map: Dict[str, Any] = {}
        if req.available_windows:
            for w in req.available_windows:
                w_id = getattr(w, "window_id", None) or (w.get("window_id") if isinstance(w, dict) else None)
                if w_id:
                    windows_map[w_id] = w

        matches_by_work: Dict[str, List[Any]] = {}
        if req.candidate_matches is not None:
            for m in req.candidate_matches:
                m_work_id = getattr(m, "work_id", None) or (m.get("work_id") if isinstance(m, dict) else None)
                is_compat = getattr(m, "is_compatible", True) if hasattr(m, "is_compatible") else (m.get("is_compatible", True) if isinstance(m, dict) else True)
                if m_work_id and is_compat:
                    matches_by_work.setdefault(m_work_id, []).append(m)

        for r_item in active_requests:
            req_id = r_item["request_id"]
            requests_to_slots[req_id] = []
            pref_mins = _parse_time_to_minutes(r_item["preferred_start"]) or 600

            if req.candidate_matches is not None:
                candidate_matches_for_item = list(matches_by_work.get(req_id, []))
                if req.pinned_slots and req_id in req.pinned_slots:
                    pin_val = req.pinned_slots[req_id]
                    pin_start, pin_end = _parse_pinned_window(pin_val, r_item["duration_minutes"])
                    matching_pins = [
                        m for m in candidate_matches_for_item
                        if getattr(windows_map.get(getattr(m, "window_id", None) or (m.get("window_id") if isinstance(m, dict) else None)), "start_time", "") == pin_start
                    ]
                    if matching_pins:
                        candidate_matches_for_item = matching_pins
                    else:
                        s_id = f"PINNED-{req_id}"
                        requests_to_slots[req_id].append(s_id)
                        p_start_m = _parse_time_to_minutes(pin_start) or 0
                        p_end_m = p_start_m + r_item["duration_minutes"]
                        slot_metadata[s_id] = {
                            "slot_id": s_id,
                            "request_id": req_id,
                            "asset_id": r_item["asset_id"],
                            "block_id": r_item["block_id"],
                            "location": r_item["location"],
                            "service_date": r_item["requested_date"],
                            "start_time": pin_start,
                            "end_time": pin_end,
                            "start_minutes": p_start_m,
                            "end_minutes": p_end_m,
                            "duration_minutes": r_item["duration_minutes"],
                            "preferred_start_minutes": pref_mins,
                            "fit_score": 1.0,
                            "is_preferred_match": True,
                            "priority": r_item["priority"],
                            "priority_value": r_item.get("priority_value"),
                            "equipment": r_item["equipment"],
                            "required_resources": r_item["required_resources"],
                        }
                        continue

                for m in candidate_matches_for_item:
                    win_id = getattr(m, "window_id", None) or (m.get("window_id") if isinstance(m, dict) else None)
                    win = windows_map.get(win_id)
                    if not win:
                        continue
                    w_start_str = getattr(win, "start_time", "00:00") or "00:00"
                    w_end_str = getattr(win, "end_time", "23:59") or "23:59"
                    w_block_id = getattr(win, "block_id", None) or win_id
                    fit = getattr(m, "fit_score", 1.0) if hasattr(m, "fit_score") else (m.get("fit_score", 1.0) if isinstance(m, dict) else 1.0)

                    s_id = f"OPT-SLOT-{slot_counter:04d}"
                    slot_counter += 1
                    requests_to_slots[req_id].append(s_id)
                    s_start = _parse_time_to_minutes(w_start_str) or 0
                    s_end = s_start + r_item["duration_minutes"]
                    dev_mins = abs(s_start - pref_mins)

                    slot_metadata[s_id] = {
                        "slot_id": s_id,
                        "request_id": req_id,
                        "asset_id": r_item["asset_id"],
                        "block_id": w_block_id,
                        "window_id": win_id,
                        "location": r_item["location"],
                        "service_date": r_item["requested_date"],
                        "start_time": w_start_str,
                        "end_time": _format_minutes_to_time(s_end),
                        "start_minutes": s_start,
                        "end_minutes": s_end,
                        "duration_minutes": r_item["duration_minutes"],
                        "preferred_start_minutes": pref_mins,
                        "fit_score": fit,
                        "is_preferred_match": (dev_mins <= 15),
                        "priority": r_item["priority"],
                        "priority_value": r_item.get("priority_value"),
                        "equipment": r_item["equipment"],
                        "required_resources": r_item["required_resources"],
                    }
            else:
                # Legacy candidate slot generation
                slots = self._find_slots_for_single_request(scheduler, r_item, req)
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
                        "priority_value": r_item.get("priority_value"),
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
            priority_value=r_item.get("priority_value"),
            priority_enrichment=r_item.get("priority_enrichment"),
            priority_contribution=meta.get("priority_contribution"),
        )

    def _build_unscheduled_block(
        self,
        r_item: Dict[str, Any],
        s_ids: List[str],
    ) -> UnscheduledBlock:
        """Create an UnscheduledBlock diagnostic item."""
        dur = r_item.get("duration_minutes", 0)
        if dur > 1440:
            reason = f"INVALID_REQUEST: Duration exceeds 24-hour day boundary ({dur}m > 1440m)."
        elif not s_ids:
            reason = "NO_FEASIBLE_WINDOW: No feasible conflict-free time window available within timetable / traffic headroom."
        else:
            reason = "Preempted by higher-priority request or equipment capacity limits."
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
            priority_value=r_item.get("priority_value"),
            priority_enrichment=r_item.get("priority_enrichment"),
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
        max_time_allowed = req.time_limit_seconds or cfg.get("time_limit_seconds", 30.0)

        status_map = {
            cp_model.OPTIMAL: OptimizationStatus.OPTIMAL,
            cp_model.FEASIBLE: OptimizationStatus.FEASIBLE,
            cp_model.INFEASIBLE: OptimizationStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: OptimizationStatus.MODEL_INVALID,
            cp_model.UNKNOWN: OptimizationStatus.UNKNOWN,
        }
        if raw == cp_model.UNKNOWN and wall_time >= (max_time_allowed * 0.90):
            solver_status = OptimizationStatus.TIME_LIMIT
        else:
            solver_status = status_map.get(raw, OptimizationStatus.UNKNOWN)
        return solver, solver_status, wall_time

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
        conflicts_before: int = 0,
        conflicts_after: int = 0,
    ) -> SolverStatistics:
        """Calculate solver performance metrics and re-optimization churn statistics."""
        num_pinned = sum(1 for b in scheduled_blocks if b.is_pinned)
        num_shifted = sum(1 for b in scheduled_blocks if b.is_shifted)
        unchanged = num_pinned + sum(1 for b in scheduled_blocks if not b.is_shifted and not b.is_pinned)
        stability_score = round(unchanged / total_requests, 3) if total_requests > 0 else 1.0
        num_avoided = max(0, conflicts_before - conflicts_after)

        return SolverStatistics(
            status=solver_status,
            objective_value=float(solver.ObjectiveValue()) if solver_status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE) else None,
            wall_time_seconds=wall_time,
            num_scheduled=len(scheduled_blocks),
            num_unscheduled=len(unscheduled_blocks),
            num_conflicts_avoided=num_avoided,
            conflicts_before=conflicts_before,
            conflicts_after=conflicts_after,
            total_requests=total_requests,
            num_variables=num_vars,
            num_constraints=num_constraints,
            num_branches=int(solver.NumBranches()) if hasattr(solver, "NumBranches") else 0,
            num_pinned=num_pinned,
            num_shifted=num_shifted,
            stability_score=stability_score,
        )

    def _count_horizon_conflicts(
        self,
        base_date: date,
        horizon_days: int,
        buffer_mins: int,
        proposed_schedule: Optional[Any] = None,
    ) -> int:
        """Count operational conflicts across horizon days using ConflictDetector.

        When evaluating a proposed_schedule (post-optimization), LOW-severity
        safety buffer violations are excluded because the CP-SAT solver
        prevents direct collisions but does not enforce soft headway margins
        against every timetable entry.
        """
        from backend.app.scheduler.conflict_detector import ConflictDetector
        from backend.app.scheduler.schemas import ConflictSeverity as CSev, ConflictType as CType
        end_date = base_date + timedelta(days=horizon_days)
        maint = [] if proposed_schedule else [m for m in self.maintenance_records if base_date <= m.requested_date < end_date]
        blocks = [] if proposed_schedule else [b for b in self.block_records if base_date <= b.requested_date < end_date]
        detector = ConflictDetector(
            trains=self.trains,
            timetables=self.timetables,
            goods_forecasts=self.goods_forecasts,
            movements=self.movements,
            maintenance_records=maint,
            block_records=blocks,
            buffer_minutes=buffer_mins,
        )
        total = 0
        for d_offset in range(horizon_days):
            h_date = base_date + timedelta(days=d_offset)
            c_rep = detector.detect_conflicts(target_date=h_date, proposed_schedule=proposed_schedule)
            if proposed_schedule:
                hard = [c for c in c_rep.conflicts
                        if not (c.conflict_type == CType.SAFETY_BUFFER_VIOLATION and c.severity == CSev.LOW)]
                total += len(hard)
            else:
                total += c_rep.total_conflicts
        return total


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

    def _resolve_mandatory_ids(
        self,
        mandatory_request_ids: Optional[Set[str]],
        req: OptimizationRequest,
        requests_to_slots: Dict[str, List[str]],
    ) -> Set[str]:
        """Aggregate mandatory constraints from explicit IDs and pinned slots."""
        all_mand = set(mandatory_request_ids or set())
        if req.mandatory_request_ids:
            all_mand.update(req.mandatory_request_ids)
        if req.pinned_slots:
            active_ids = set(requests_to_slots.keys())
            all_mand.update(k for k in req.pinned_slots.keys() if k in active_ids)
        return all_mand

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
        conflicts_before = self._count_horizon_conflicts(base_date, horizon_days, buffer_mins)
        scheduler = self._create_scheduler(active_requests, req, buffer_mins)
        requests_to_slots, slot_metadata = self._generate_candidate_slots(scheduler, active_requests, req)

        model = cp_model.CpModel()
        slot_vars = self._create_decision_variables(model, requests_to_slots)
        all_mandatory = self._resolve_mandatory_ids(mandatory_request_ids, req, requests_to_slots)

        num_constraints = self._build_model_constraints(
            model, slot_vars, requests_to_slots, slot_metadata, capacities, all_mandatory
        )
        build_optimization_objective(model, slot_vars, slot_metadata, weights)

        solver, solver_status, wall_time = self._solve_model(model, req)
        scheduled, unscheduled = self._extract_results(
            solver, slot_vars, slot_metadata, active_requests, requests_to_slots, solver_status, req
        )
        unscheduled.extend(excluded_blocks)

        conflicts_after = self._count_horizon_conflicts(base_date, horizon_days, buffer_mins, proposed_schedule=scheduled) if scheduled else 0
        total_req_count = len(active_requests) + len(excluded_blocks)
        stats = self._compute_statistics(
            solver, solver_status, scheduled, unscheduled, total_req_count,
            len(slot_vars), num_constraints, wall_time,
            conflicts_before=conflicts_before,
            conflicts_after=conflicts_after,
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
