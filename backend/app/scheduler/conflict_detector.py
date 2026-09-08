"""
Conflict Detection Engine for Railway Block Planner.

Analyzes proposed maintenance windows, block requests, train timetables,
active movements, and goods train forecasts to detect spatial-temporal collisions,
safety buffer violations, and resource contentions with operational priority precedence.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.app.forecast.schemas import ForecastConfidenceLevel, GoodsForecastItem
from backend.app.scheduler.schemas import (
    ConflictItem,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
    ScheduleResult,
)
from backend.app.scheduler.scheduler import (
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

LOCATION_ALIASES = {
    "chennai-arakkonam": ["chennai", "perambur", "ajj", "arakkonam", "km40-42", "basin bridge"],
    "arakkonam-renigunta": ["arakkonam", "ajj", "walajah", "ru", "renigunta", "km85-87"],
    "chennai-villupuram": ["chennai", "tambaram", "tbm", "cgl", "chengalpattu", "vm", "villupuram", "tlgp"],
    "tambaram-chengalpattu": ["tambaram", "tbm", "cgl", "chengalpattu"],
    "villupuram-chengalpattu": ["villupuram", "vm", "cgl", "chengalpattu", "tlgp"],
}


def _evaluate_block_precedence(
    b1: Dict[str, Any],
    b2: Dict[str, Any],
) -> Tuple[Optional[str], str, str]:
    """
    Evaluate operational priority precedence between conflicting track blocks.
    Returns: (precedence_entity_id, suggested_action, resolution_strategy)
    """
    p1 = b1.get("priority", Priority.MEDIUM)
    p2 = b2.get("priority", Priority.MEDIUM)
    r1 = PRIORITY_RANK.get(p1, 2)
    r2 = PRIORITY_RANK.get(p2, 2)
    end1 = _format_minutes_to_time(b1["end"])
    end2 = _format_minutes_to_time(b2["end"])

    if r1 > r2:
        return (
            b1["id"],
            f"Priority Precedence: Prioritize {b1['id']} ({p1.value}). Defer or shift {b2['id']} ({p2.value}) to start after {end1}.",
            "Priority Precedence (Defer Lower Priority)",
        )
    elif r2 > r1:
        return (
            b2["id"],
            f"Priority Precedence: Prioritize {b2['id']} ({p2.value}). Defer or shift {b1['id']} ({p1.value}) to start after {end2}.",
            "Priority Precedence (Defer Lower Priority)",
        )
    elif p1 == Priority.CRITICAL and p2 == Priority.CRITICAL:
        return (
            "Joint Consolidation",
            f"Joint Critical Consolidation: Both {b1['id']} and {b2['id']} are Critical emergency repairs on section {b1['location']}. Execute simultaneous possession under unified permit.",
            "Joint Emergency Consolidation",
        )
    else:
        dur1 = b1["end"] - b1["start"]
        dur2 = b2["end"] - b2["start"]
        shorter_id = b1["id"] if dur1 <= dur2 else b2["id"]
        return (
            shorter_id,
            f"Priority Tie ({p1.value}): Stagger possessions sequentially. Schedule shorter task {shorter_id} first, or consolidate maintenance gangs under unified possession.",
            "Sequential Staggering",
        )


def _evaluate_resource_precedence(
    b1: Dict[str, Any],
    b2: Dict[str, Any],
    eq_name: str,
) -> Tuple[Optional[str], str, str]:
    """Evaluate equipment contention priority precedence."""
    p1 = b1.get("priority", Priority.MEDIUM)
    p2 = b2.get("priority", Priority.MEDIUM)
    r1 = PRIORITY_RANK.get(p1, 2)
    r2 = PRIORITY_RANK.get(p2, 2)

    if r1 >= r2:
        return (
            b1["id"],
            f"Equipment Allocation: Allocate '{eq_name}' to {b1['id']} ({p1.value}) first; transfer to {b2['id']} ({p2.value}) sequentially after 60 min transit.",
            "Equipment Time-Sharing",
        )
    else:
        return (
            b2["id"],
            f"Equipment Allocation: Allocate '{eq_name}' to {b2['id']} ({p2.value}) first; transfer to {b1['id']} ({p1.value}) sequentially after 60 min transit.",
            "Equipment Time-Sharing",
        )


class ConflictDetector:
    """
    Evaluates spatial-temporal conflicts across all railway domain entities,
    accurately detecting overlaps and buffer compressions crossing midnight.
    """

    def __init__(
        self,
        trains: Optional[List[TrainRecord]] = None,
        timetables: Optional[List[TimetableRecord]] = None,
        goods_forecasts: Optional[List[GoodsForecastItem]] = None,
        movements: Optional[List[MovementRecord]] = None,
        maintenance_records: Optional[List[MaintenanceRecord]] = None,
        block_records: Optional[List[BlockRecord]] = None,
        buffer_minutes: int = 15,
    ) -> None:
        self.trains = trains or []
        self.timetables = timetables or []
        self.goods_forecasts = goods_forecasts or []
        self.movements = movements or []
        self.maintenance_records = maintenance_records or []
        self.block_records = block_records or []
        self.buffer_minutes = max(0, buffer_minutes)

    def _gather_proposed_windows(self, proposed_schedule: Any, c_date: date) -> List[Dict[str, Any]]:
        """Extract intervals from proposed ScheduleResult or list of OptimizedBlock."""
        windows: List[Dict[str, Any]] = []
        raw_items = getattr(proposed_schedule, "scheduled_items", None)
        if raw_items is None and isinstance(proposed_schedule, (list, tuple)):
            raw_items = proposed_schedule
        elif raw_items is None:
            raw_items = []

        for item in raw_items:
            if hasattr(item, "assigned_slot") and item.assigned_slot:
                s_min = _parse_time_to_minutes(item.assigned_slot.start_time)
                if s_min is not None:
                    day_off = (item.assigned_slot.service_date - c_date).days * 1440
                    abs_s = day_off + s_min
                    windows.append({
                        "id": item.request_id,
                        "type": "ScheduledBlock",
                        "location": item.location,
                        "start": abs_s,
                        "end": abs_s + item.requested_duration,
                        "priority": item.priority,
                        "equipment": getattr(item, "equipment", None),
                    })
            elif hasattr(item, "start_time") and getattr(item, "service_date", None):
                s_min = _parse_time_to_minutes(item.start_time)
                if s_min is not None:
                    day_off = (item.service_date - c_date).days * 1440
                    abs_s = day_off + s_min
                    dur = getattr(item, "duration_minutes", 60)
                    b_id = getattr(item, "block_id", None) or getattr(item, "request_id", "BLK")
                    windows.append({
                        "id": b_id,
                        "type": "ScheduledBlock",
                        "location": item.location,
                        "start": abs_s,
                        "end": abs_s + dur,
                        "priority": getattr(item, "priority", Priority.MEDIUM),
                        "equipment": getattr(item, "equipment", None),
                    })
        return windows

    def _gather_db_windows(self, c_date: date, next_date: date) -> List[Dict[str, Any]]:
        """Extract intervals from active database maintenance records and block records."""
        windows: List[Dict[str, Any]] = []
        for m in self.maintenance_records:
            if m.requested_date in (c_date, next_date) and m.maintenance_required:
                p_start = _parse_time_to_minutes(m.preferred_start)
                if p_start is not None:
                    day_off = (m.requested_date - c_date).days * 1440
                    abs_s = day_off + p_start
                    windows.append({
                        "id": m.asset_id,
                        "type": "MaintenanceRequest",
                        "location": m.location,
                        "start": abs_s,
                        "end": abs_s + m.duration_minutes,
                        "priority": m.priority,
                        "equipment": m.equipment,
                    })

        for b in self.block_records:
            if b.requested_date in (c_date, next_date) and b.status != BlockStatus.CANCELLED:
                b_start = _parse_time_to_minutes(b.requested_start)
                if b_start is not None:
                    dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
                    day_off = (b.requested_date - c_date).days * 1440
                    abs_s = day_off + b_start
                    windows.append({
                        "id": b.block_id,
                        "type": "BlockRequest",
                        "location": b.location,
                        "start": abs_s,
                        "end": abs_s + dur,
                        "priority": b.priority,
                        "equipment": None,
                    })
        return windows

    def _gather_block_windows(
        self,
        proposed_schedule: Optional[Any],
        c_date: date,
        next_date: date,
    ) -> List[Dict[str, Any]]:
        """Extract all candidate possession intervals normalized in absolute minutes."""
        if proposed_schedule:
            return self._gather_proposed_windows(proposed_schedule, c_date)
        return self._gather_db_windows(c_date, next_date)

    def _detect_timetable_conflicts(
        self,
        block_windows: List[Dict[str, Any]],
        c_date: date,
        next_date: date,
        start_idx: int,
    ) -> Tuple[List[ConflictItem], int]:
        """Check direct train overlaps and headway buffer compressions against passenger timetable."""
        conflicts: List[ConflictItem] = []
        c_idx = start_idx

        for tt in self.timetables:
            tt_date = getattr(tt, "service_date", None)
            if tt_date is not None and tt_date not in (c_date, next_date):
                continue
            day_offset = (tt_date - c_date).days * 1440 if tt_date is not None else 0

            t_arr = _parse_time_to_minutes(tt.arrival_time)
            t_dep = _parse_time_to_minutes(tt.departure_time)
            if t_arr is None and t_dep is None:
                continue
            t_start = t_arr if t_arr is not None else t_dep
            t_end = t_dep if t_dep is not None else t_arr
            if t_end < t_start:
                t_end += 1440
            t_end = max(t_end, t_start + 5)
            abs_t_start = day_offset + t_start
            abs_t_end = day_offset + t_end

            for blk in block_windows:
                if not _locations_match(tt.station_code, blk["location"]):
                    continue
                overlap_s = max(abs_t_start, blk["start"])
                overlap_e = min(abs_t_end, blk["end"])

                if overlap_s < overlap_e:
                    item = self._build_train_overlap_item(tt, blk, overlap_s, overlap_e, c_date, c_idx)
                    conflicts.append(item)
                    c_idx += 1
                else:
                    item = self._build_buffer_violation_item(tt, blk, abs_t_start, abs_t_end, c_date, c_idx)
                    if item:
                        conflicts.append(item)
                        c_idx += 1

        return conflicts, c_idx

    def _build_train_overlap_item(
        self,
        tt: TimetableRecord,
        blk: Dict[str, Any],
        overlap_s: int,
        overlap_e: int,
        c_date: date,
        c_idx: int,
    ) -> ConflictItem:
        """Create conflict item for direct passenger train overlap."""
        dur = overlap_e - overlap_s
        p_blk = blk.get("priority", Priority.MEDIUM)
        is_crit = (p_blk == Priority.CRITICAL)
        prec_id = blk["id"] if is_crit else tt.train_id
        action = (
            f"Emergency Precedence: Passenger Train {tt.train_id} held or routed via loop line; prioritize emergency possession {blk['id']} (Critical)."
            if is_crit
            else f"Train Movement Precedence: Passenger Train {tt.train_id} has scheduled corridor priority. Defer {blk['type']} {blk['id']} ({p_blk.value}) by +{dur + self.buffer_minutes} mins."
        )
        return ConflictItem(
            conflict_id=f"CONF-{c_idx:04d}",
            conflict_type=ConflictType.TRAIN_BLOCK,
            severity=ConflictSeverity.CRITICAL,
            location=blk["location"],
            service_date=c_date,
            start_time=_format_minutes_to_time(overlap_s),
            end_time=_format_minutes_to_time(overlap_e),
            overlap_minutes=dur,
            entity1_type="Train",
            entity1_id=tt.train_id,
            entity2_type=blk["type"],
            entity2_id=blk["id"],
            description=f"Train {tt.train_id} scheduled at {tt.station_code} overlaps with {blk['type']} {blk['id']}.",
            suggested_action=action,
            entity1_priority="Passenger Timetable",
            entity2_priority=p_blk.value,
            precedence_entity_id=prec_id,
            resolution_strategy="Emergency Holding / Diversion" if is_crit else "Shift Maintenance Block",
        )

    def _build_buffer_violation_item(
        self,
        tt: TimetableRecord,
        blk: Dict[str, Any],
        t_start: int,
        t_end: int,
        c_date: date,
        c_idx: int,
    ) -> Optional[ConflictItem]:
        """Create conflict item for safety buffer violation gap if under threshold."""
        gap_before = blk["start"] - t_end
        gap_after = t_start - blk["end"]
        if not ((0 <= gap_before < self.buffer_minutes) or (0 <= gap_after < self.buffer_minutes)):
            return None

        buf_gap = min(gap_before if gap_before >= 0 else 9999, gap_after if gap_after >= 0 else 9999)
        return ConflictItem(
            conflict_id=f"CONF-{c_idx:04d}",
            conflict_type=ConflictType.SAFETY_BUFFER_VIOLATION,
            severity=ConflictSeverity.LOW,
            location=blk["location"],
            service_date=c_date,
            start_time=_format_minutes_to_time(min(t_start, blk["start"])),
            end_time=_format_minutes_to_time(max(t_end, blk["end"])),
            overlap_minutes=self.buffer_minutes - buf_gap,
            entity1_type="Train",
            entity1_id=tt.train_id,
            entity2_type=blk["type"],
            entity2_id=blk["id"],
            description=f"Train {tt.train_id} passes within {buf_gap} min (< {self.buffer_minutes} min safety buffer) of {blk['type']} {blk['id']}.",
            suggested_action=f"Increase clearance gap to minimum {self.buffer_minutes} minutes.",
            entity1_priority="Passenger Timetable",
            entity2_priority=blk.get("priority", Priority.MEDIUM).value,
        )

    def _detect_goods_conflicts(
        self,
        block_windows: List[Dict[str, Any]],
        c_date: date,
        next_date: date,
        start_idx: int,
    ) -> Tuple[List[ConflictItem], int]:
        """Check train-block conflicts against predicted goods train traffic."""
        conflicts: List[ConflictItem] = []
        c_idx = start_idx

        for fc in self.goods_forecasts:
            if fc.service_date not in (c_date, next_date):
                continue
            day_off = (fc.service_date - c_date).days * 1440
            f_start = _parse_time_to_minutes(fc.forecasted_entry)
            f_end = _parse_time_to_minutes(fc.forecasted_exit)
            if f_start is None or f_end is None:
                continue
            if f_end < f_start:
                f_end += 1440
            abs_fs = day_off + f_start
            abs_fe = day_off + f_end

            for blk in block_windows:
                if not _locations_match(fc.section, blk["location"]):
                    continue
                overlap_s = max(abs_fs, blk["start"])
                overlap_e = min(abs_fe, blk["end"])
                if overlap_s < overlap_e:
                    conflicts.append(self._build_goods_conflict_item(
                        c_idx, c_date, fc, blk, overlap_s, overlap_e
                    ))
                    c_idx += 1

        return conflicts, c_idx

    def _build_goods_conflict_item(
        self,
        c_idx: int,
        c_date: date,
        fc: GoodsForecastItem,
        blk: Dict[str, Any],
        overlap_s: int,
        overlap_e: int,
    ) -> ConflictItem:
        """Construct ConflictItem for forecasted freight overlap with maintenance slot."""
        dur = overlap_e - overlap_s
        p_blk = blk.get("priority", Priority.MEDIUM)
        is_low_conf = (
            getattr(fc, "confidence_level", None) == ForecastConfidenceLevel.LOW
            or getattr(fc, "confidence_score", 1.0) < 0.5
        )
        if is_low_conf:
            sev = ConflictSeverity.LOW
            note = f" (Advisory: Low Confidence {getattr(fc, 'confidence_score', 0.25)*100:.0f}%)"
        else:
            sev = ConflictSeverity.HIGH if p_blk in (Priority.CRITICAL, Priority.HIGH) else ConflictSeverity.MEDIUM
            note = ""

        return ConflictItem(
            conflict_id=f"CONF-{c_idx:04d}",
            conflict_type=ConflictType.TRAIN_BLOCK,
            severity=sev,
            location=blk["location"],
            service_date=c_date,
            start_time=_format_minutes_to_time(overlap_s),
            end_time=_format_minutes_to_time(overlap_e),
            overlap_minutes=dur,
            entity1_type="GoodsForecast",
            entity1_id=fc.train_id,
            entity2_type=blk["type"],
            entity2_id=blk["id"],
            description=f"Forecasted goods movement {fc.train_id} on {fc.section} overlaps with {blk['type']} {blk['id']}{note}.",
            suggested_action=f"Traffic Precedence: Route goods train {fc.train_id} via Loop line siding to prioritize {blk['type']} {blk['id']} ({p_blk.value}).",
            entity1_priority="Freight Movement",
            entity2_priority=p_blk.value,
            precedence_entity_id=blk["id"],
            resolution_strategy="Reroute / Loop Line Possession",
        )

    def _build_movement_collision_item(
        self,
        c_idx: int,
        c_date: date,
        m: MovementRecord,
        blk: Dict[str, Any],
        overlap_s: int,
        overlap_e: int,
    ) -> ConflictItem:
        """Construct ConflictItem for active train movement direct collision."""
        dur = overlap_e - overlap_s
        p_blk = blk.get("priority", Priority.MEDIUM)
        sev = ConflictSeverity.CRITICAL if p_blk in (Priority.CRITICAL, Priority.HIGH) else ConflictSeverity.HIGH
        return ConflictItem(
            conflict_id=f"CONF-{c_idx:04d}",
            conflict_type=ConflictType.TRAIN_BLOCK,
            severity=sev,
            location=blk["location"],
            service_date=c_date,
            start_time=_format_minutes_to_time(overlap_s),
            end_time=_format_minutes_to_time(overlap_e),
            overlap_minutes=dur,
            entity1_type="Movement",
            entity1_id=m.train_id,
            entity2_type=blk["type"],
            entity2_id=blk["id"],
            description=f"Active movement of train {m.train_id} on section {m.section} directly collides with {blk['type']} {blk['id']}.",
            suggested_action=f"Adjust possession timing or re-route train {m.train_id} via Loop line.",
            entity1_priority="Active Movement",
            entity2_priority=p_blk.value if hasattr(p_blk, "value") else str(p_blk),
        )

    def _build_movement_buffer_item(
        self,
        c_idx: int,
        c_date: date,
        m: MovementRecord,
        blk: Dict[str, Any],
        abs_m_start: int,
        abs_m_end: int,
        buf_gap: int,
    ) -> ConflictItem:
        """Construct ConflictItem for active movement safety buffer violation."""
        p_blk = blk.get("priority", Priority.MEDIUM)
        return ConflictItem(
            conflict_id=f"CONF-{c_idx:04d}",
            conflict_type=ConflictType.SAFETY_BUFFER_VIOLATION,
            severity=ConflictSeverity.LOW,
            location=blk["location"],
            service_date=c_date,
            start_time=_format_minutes_to_time(abs_m_start),
            end_time=_format_minutes_to_time(abs_m_end),
            overlap_minutes=0,
            entity1_type="Movement",
            entity1_id=m.train_id,
            entity2_type=blk["type"],
            entity2_id=blk["id"],
            description=f"Train movement {m.train_id} passes within {buf_gap} min (< {self.buffer_minutes} min buffer) of {blk['type']} {blk['id']}.",
            suggested_action=f"Maintain minimum safety buffer of {self.buffer_minutes} min.",
            entity1_priority="Active Movement",
            entity2_priority=p_blk.value if hasattr(p_blk, "value") else str(p_blk),
        )

    def _detect_movement_conflicts(
        self,
        block_windows: List[Dict[str, Any]],
        c_date: date,
        start_idx: int,
    ) -> Tuple[List[ConflictItem], int]:
        """Check train-block conflicts against active train movements (COA)."""
        conflicts: List[ConflictItem] = []
        c_idx = start_idx

        for m in self.movements:
            m_start = _parse_time_to_minutes(m.entry_time)
            m_end = _parse_time_to_minutes(m.exit_time)
            if m_start is None or m_end is None:
                continue
            if m_end < m_start:
                m_end += 1440
            abs_m_start = m_start
            abs_m_end = m_end

            for blk in block_windows:
                if not _locations_match(m.section, blk["location"]):
                    continue
                overlap_s = max(abs_m_start, blk["start"])
                overlap_e = min(abs_m_end, blk["end"])
                if overlap_s < overlap_e:
                    conflicts.append(self._build_movement_collision_item(
                        c_idx, c_date, m, blk, overlap_s, overlap_e
                    ))
                    c_idx += 1
                elif self.buffer_minutes > 0:
                    gap_before = blk["start"] - abs_m_end
                    gap_after = abs_m_start - blk["end"]
                    if (0 <= gap_before < self.buffer_minutes) or (0 <= gap_after < self.buffer_minutes):
                        buf_gap = min(gap_before if gap_before >= 0 else 9999, gap_after if gap_after >= 0 else 9999)
                        conflicts.append(self._build_movement_buffer_item(
                            c_idx, c_date, m, blk, abs_m_start, abs_m_end, buf_gap
                        ))
                        c_idx += 1

        return conflicts, c_idx

    def _detect_block_block_conflicts(
        self,
        block_windows: List[Dict[str, Any]],
        c_date: date,
        start_idx: int,
    ) -> Tuple[List[ConflictItem], int]:
        """Detect simultaneous track occupancy collisions applying priority precedence."""
        conflicts: List[ConflictItem] = []
        c_idx = start_idx

        for i in range(len(block_windows)):
            for j in range(i + 1, len(block_windows)):
                b1 = block_windows[i]
                b2 = block_windows[j]
                if b1["id"] == b2["id"] or not _locations_match(b1["location"], b2["location"]):
                    continue

                overlap_s = max(b1["start"], b2["start"])
                overlap_e = min(b1["end"], b2["end"])
                if overlap_s < overlap_e:
                    dur = overlap_e - overlap_s
                    p1 = b1.get("priority", Priority.MEDIUM)
                    p2 = b2.get("priority", Priority.MEDIUM)
                    sev = ConflictSeverity.CRITICAL if (p1 == Priority.CRITICAL or p2 == Priority.CRITICAL) else ConflictSeverity.HIGH
                    prec_id, action, strat = _evaluate_block_precedence(b1, b2)

                    conflicts.append(ConflictItem(
                        conflict_id=f"CONF-{c_idx:04d}",
                        conflict_type=ConflictType.BLOCK_BLOCK,
                        severity=sev,
                        location=b1["location"],
                        service_date=c_date,
                        start_time=_format_minutes_to_time(overlap_s),
                        end_time=_format_minutes_to_time(overlap_e),
                        overlap_minutes=dur,
                        entity1_type=b1["type"],
                        entity1_id=b1["id"],
                        entity2_type=b2["type"],
                        entity2_id=b2["id"],
                        description=f"Simultaneous track blocks {b1['id']} ({p1.value}) and {b2['id']} ({p2.value}) collide on section {b1['location']}.",
                        suggested_action=action,
                        entity1_priority=p1.value,
                        entity2_priority=p2.value,
                        precedence_entity_id=prec_id,
                        resolution_strategy=strat,
                    ))
                    c_idx += 1

        return conflicts, c_idx

    def _detect_resource_conflicts(
        self,
        block_windows: List[Dict[str, Any]],
        c_date: date,
        start_idx: int,
    ) -> Tuple[List[ConflictItem], int]:
        """Detect equipment capacity contention between overlapping maintenance requests."""
        conflicts: List[ConflictItem] = []
        c_idx = start_idx

        for i in range(len(block_windows)):
            for j in range(i + 1, len(block_windows)):
                b1 = block_windows[i]
                b2 = block_windows[j]
                if b1["id"] == b2["id"]:
                    continue
                eq1 = b1.get("equipment")
                eq2 = b2.get("equipment")
                if eq1 and eq2 and eq1.strip().lower() == eq2.strip().lower() and eq1.strip().lower() != "none":
                    overlap_s = max(b1["start"], b2["start"])
                    overlap_e = min(b1["end"], b2["end"])
                    if overlap_s < overlap_e:
                        prec_id, action, strat = _evaluate_resource_precedence(b1, b2, eq1)
                        p1 = b1.get("priority", Priority.MEDIUM)
                        p2 = b2.get("priority", Priority.MEDIUM)
                        conflicts.append(ConflictItem(
                            conflict_id=f"CONF-{c_idx:04d}",
                            conflict_type=ConflictType.RESOURCE_CONTENTION,
                            severity=ConflictSeverity.MEDIUM,
                            location=f"{b1['location']} & {b2['location']}",
                            service_date=c_date,
                            start_time=_format_minutes_to_time(overlap_s),
                            end_time=_format_minutes_to_time(overlap_e),
                            overlap_minutes=overlap_e - overlap_s,
                            entity1_type=b1["type"],
                            entity1_id=b1["id"],
                            entity2_type=b2["type"],
                            entity2_id=b2["id"],
                            description=f"Specialized equipment '{eq1}' concurrently requested by {b1['id']} ({p1.value}) and {b2['id']} ({p2.value}).",
                            suggested_action=action,
                            entity1_priority=p1.value,
                            entity2_priority=p2.value,
                            precedence_entity_id=prec_id,
                            resolution_strategy=strat,
                        ))
                        c_idx += 1

        return conflicts, c_idx

    def detect_conflicts(
        self,
        target_date: Optional[date] = None,
        proposed_schedule: Optional[ScheduleResult] = None,
    ) -> ConflictReport:
        """Scan all active entities for operational conflicts on the target date."""
        c_date = target_date or date.today()
        next_date = c_date + timedelta(days=1)
        conflicts: List[ConflictItem] = []

        block_windows = self._gather_block_windows(proposed_schedule, c_date, next_date)
        tt_conflicts, c_idx = self._detect_timetable_conflicts(block_windows, c_date, next_date, 1)
        conflicts.extend(tt_conflicts)

        mov_conflicts, c_idx = self._detect_movement_conflicts(block_windows, c_date, c_idx)
        conflicts.extend(mov_conflicts)

        fc_conflicts, c_idx = self._detect_goods_conflicts(block_windows, c_date, next_date, c_idx)
        conflicts.extend(fc_conflicts)

        bb_conflicts, c_idx = self._detect_block_block_conflicts(block_windows, c_date, c_idx)
        conflicts.extend(bb_conflicts)

        res_conflicts, _ = self._detect_resource_conflicts(block_windows, c_date, c_idx)
        conflicts.extend(res_conflicts)

        crit = sum(1 for c in conflicts if c.severity == ConflictSeverity.CRITICAL)
        high = sum(1 for c in conflicts if c.severity == ConflictSeverity.HIGH)
        med = sum(1 for c in conflicts if c.severity == ConflictSeverity.MEDIUM)
        low = sum(1 for c in conflicts if c.severity == ConflictSeverity.LOW)

        return ConflictReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_date=c_date,
            total_conflicts=len(conflicts),
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            is_conflict_free=(len(conflicts) == 0),
            conflicts=conflicts,
        )
