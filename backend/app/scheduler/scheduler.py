"""
Maintenance Scheduler Engine for Railway Block Planner.

Generates feasible, conflict-free maintenance block slots by evaluating
infrastructure maintenance requests against passenger train timetables,
active track movements, and goods train forecasts.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union
import uuid

from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    MaintenanceRecord,
    MovementRecord,
    Priority,
    TimetableRecord,
)

logger = logging.getLogger(__name__)

# Priority sorting rank
PRIORITY_RANK = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 3,
    Priority.MEDIUM: 2,
    Priority.LOW: 1,
}

# Corridor location normalization map for matching sub-stations and chainages to sections
LOCATION_ALIASES = {
    "chennai-arakkonam": ["chennai", "perambur", "ajj", "arakkonam", "km40-42", "basin bridge"],
    "arakkonam-renigunta": ["arakkonam", "ajj", "walajah", "ru", "renigunta", "km85-87"],
    "chennai-villupuram": ["chennai", "tambaram", "tbm", "cgl", "chengalpattu", "vm", "villupuram", "tlgp"],
    "tambaram-chengalpattu": ["tambaram", "tbm", "cgl", "chengalpattu"],
    "villupuram-chengalpattu": ["villupuram", "vm", "cgl", "chengalpattu", "tlgp"],
}

if TYPE_CHECKING:
    from backend.app.block_planner.schemas import (
        CandidateWorkItem,
        DailySchedulingProblem,
    )
from backend.app.forecast.schemas import GoodsForecastItem
from backend.app.optimizer.schemas import OptimizationRequest
from backend.app.scheduler.schemas import (
    CorridorAvailabilityWindow,
    DailyAvailabilityReport,
    DailyScheduleResult,
    FeasibleSlot,
    MaintenanceScheduleItem,
    ScheduleResult,
    WorkBlockMatch,
    WorkMatchReport,
)



def _parse_time_to_minutes(time_val: Union[str, time, None]) -> Optional[int]:
    """Convert time object or HH:MM string to minutes from midnight."""
    if time_val is None:
        return None
    if isinstance(time_val, time):
        return time_val.hour * 60 + time_val.minute
    s = str(time_val).strip()
    if not s or s in ("--", "None"):
        return None
    try:
        parts = [int(p) for p in s.split(":")[:2]]
        return parts[0] * 60 + parts[1]
    except Exception:
        return None


def _calculate_duration_minutes(
    start_val: Union[str, time, None],
    end_val: Union[str, time, None],
    default_start: int = 480,
    default_end: int = 600,
) -> int:
    """
    Calculate required duration in minutes, correctly handling overnight spans
    where end time is numerically earlier than start time (crossing midnight).
    """
    start_m = _parse_time_to_minutes(start_val)
    if start_m is None:
        start_m = default_start
    end_m = _parse_time_to_minutes(end_val)
    if end_m is None:
        end_m = default_end

    if end_m < start_m:
        end_m += 1440
    dur = end_m - start_m
    return max(30, dur)


def _format_minutes_to_time(minutes: int) -> str:
    """Convert minutes to HH:MM format (modulo 24 hours for overnight rollover)."""
    norm = minutes % 1440
    h = norm // 60
    m = norm % 60
    return f"{h:02d}:{m:02d}"


def _get_horizon_days(
    schedule_type: str,
    start_date: date,
) -> int:
    """
    Return the scheduling horizon in days.

    daily   -> selected date only
    weekly  -> selected date + next 6 days
    monthly -> selected date through the last day of that month
    """
    schedule_type = schedule_type.lower().strip()
    if schedule_type == "daily":
        return 1
    if schedule_type == "weekly":
        return 7
    if schedule_type == "monthly":
        last_day = calendar.monthrange(
            start_date.year,
            start_date.month,
        )[1]
        return last_day - start_date.day + 1
    raise ValueError(
        "schedule_type must be 'daily', 'weekly', or 'monthly'"
    )


def _generate_schedule_dates(
    start_date: date,
    horizon_days: int,
) -> List[date]:
    """Generate all dates included in the scheduling horizon."""
    return [
        start_date + timedelta(days=offset)
        for offset in range(horizon_days)
    ]


def _normalize_location_str(loc: str) -> str:
    return (loc or "").lower().strip().replace(" ", "").replace("-", "")


def _get_matched_corridor_key(loc: str) -> Optional[str]:
    norm = _normalize_location_str(loc)
    for c_key in LOCATION_ALIASES:
        if norm == _normalize_location_str(c_key):
            return c_key
    return None


def _locations_match(loc1: str, loc2: str) -> bool:
    """
    Determine if two location/section descriptions refer to overlapping trackage.
    Handles exact matches, station-to-corridor containment, and sub-corridor relationships.
    Avoids false positives between distinct corridors that share junctions.
    """
    l1 = (loc1 or "").lower().strip()
    l2 = (loc2 or "").lower().strip()
    if not l1 or not l2:
        return False
    if l1 == l2:
        return True

    corr1 = _get_matched_corridor_key(l1)
    corr2 = _get_matched_corridor_key(l2)

    # Sub-corridor relationships
    sub_corridors = {
        "chennai-villupuram": {"tambaram-chengalpattu", "villupuram-chengalpattu"},
    }

    # Both are recognized corridors
    if corr1 and corr2:
        if corr1 == corr2:
            return True
        if corr2 in sub_corridors.get(corr1, set()) or corr1 in sub_corridors.get(corr2, set()):
            return True
        return False

    # One is a corridor and one is a station/section
    if corr1 or corr2:
        corr = corr1 or corr2
        stn = l2 if corr1 else l1
        stn_norm = _normalize_location_str(stn)
        aliases = LOCATION_ALIASES[corr]
        for a in aliases:
            a_norm = _normalize_location_str(a)
            if stn_norm == a_norm or (len(a_norm) >= 3 and a_norm in stn_norm) or (len(stn_norm) >= 3 and stn_norm in a_norm):
                return True
        return False

    # Neither is a recognized corridor: compare as station / chainage / section strings
    norm1 = _normalize_location_str(l1)
    norm2 = _normalize_location_str(l2)
    if norm1 == norm2:
        return True
    if len(norm1) >= 3 and len(norm2) >= 3:
        if norm1 in norm2 or norm2 in norm1:
            return True

    # Check if both are aliases of the same corridor (e.g. AJJ and Arakkonam)
    for corridor, aliases in LOCATION_ALIASES.items():
        in_l1 = any(norm1 == _normalize_location_str(a) for a in aliases)
        in_l2 = any(norm2 == _normalize_location_str(a) for a in aliases)
        if in_l1 and in_l2:
            return True

    return False


class MaintenanceScheduler:
    """
    Rule-based heuristic scheduler for railway maintenance blocks.
    """

    def __init__(
        self,
        maintenance_records: Optional[List[MaintenanceRecord]] = None,
        block_records: Optional[List[BlockRecord]] = None,
        timetables: Optional[List[TimetableRecord]] = None,
        goods_forecasts: Optional[List[GoodsForecastItem]] = None,
        movements: Optional[List[MovementRecord]] = None,
        buffer_minutes: int = 15,
    ) -> None:
        self.maintenance_records = maintenance_records or []
        self.block_records = block_records or []
        self.timetables = timetables or []
        self.goods_forecasts = goods_forecasts or []
        self.movements = movements or []
        self.buffer_minutes = max(0, buffer_minutes)

    def _build_location_occupancy(
        self,
        target_date: date,
        location: str,
        additional_occupancy: Optional[List[Tuple[int, int, str]]] = None,
    ) -> List[Tuple[int, int, str]]:
        """
        Collect all occupied time intervals [start_mins, end_mins, description]
        for the given location including safety buffers, supporting overnight
        spans across target_date and next calendar day.
        """
        occupied: List[Tuple[int, int, str]] = []
        if additional_occupancy:
            occupied.extend(additional_occupancy)
        next_date = target_date + timedelta(days=1)
        prev_date = target_date - timedelta(days=1)

        # 1. Check Passenger / Fixed Timetable stops on target_date and next_date
        train_tts: Dict[Tuple[date, str], List[TimetableRecord]] = {}
        for tt in self.timetables:
            if tt.service_date in (target_date, next_date):
                train_tts.setdefault((tt.service_date, tt.train_id), []).append(tt)

        for (s_date, tid), stops in train_tts.items():
            day_offset = (s_date - target_date).days * 1440
            stops_sorted = sorted(stops, key=lambda s: s.sequence)
            for stop in stops_sorted:
                if _locations_match(stop.station_code, location):
                    arr = _parse_time_to_minutes(stop.arrival_time)
                    dep = _parse_time_to_minutes(stop.departure_time)
                    t_start = arr if arr is not None else (dep - 5 if dep is not None else 600)
                    t_end = dep if dep is not None else (arr + 5 if arr is not None else 605)
                    start_buf = max(0, day_offset + t_start - self.buffer_minutes)
                    end_buf = day_offset + t_end + self.buffer_minutes
                    occupied.append((start_buf, end_buf, f"Train {tid} at {stop.station_code}"))

        # 2. Check Goods Train Forecasts
        for fc in self.goods_forecasts:
            if fc.service_date in (target_date, next_date) and _locations_match(fc.section, location):
                day_offset = (fc.service_date - target_date).days * 1440
                f_start = _parse_time_to_minutes(fc.forecasted_entry)
                f_end = _parse_time_to_minutes(fc.forecasted_exit)
                if f_start is not None and f_end is not None:
                    if f_end < f_start:
                        f_end += 1440
                    start_buf = max(0, day_offset + f_start - self.buffer_minutes)
                    end_buf = day_offset + f_end + self.buffer_minutes
                    occupied.append((start_buf, end_buf, f"Goods Forecast {fc.train_id} ({fc.section})"))

        # 3. Check Active Movements
        for m in self.movements:
            if _locations_match(m.section, location):
                m_start = _parse_time_to_minutes(m.entry_time)
                m_end = _parse_time_to_minutes(m.exit_time)
                if m_start is not None and m_end is not None:
                    if m_end < m_start:
                        m_end += 1440
                    start_buf = max(0, m_start - self.buffer_minutes)
                    end_buf = m_end + self.buffer_minutes
                    occupied.append((start_buf, end_buf, f"Movement {m.train_id} ({m.section})"))

        # 4. Check Approved Existing Blocks
        for b in self.block_records:
            if b.status == BlockStatus.APPROVED and _locations_match(b.location, location):
                b_start = _parse_time_to_minutes(b.requested_start)
                b_end = _parse_time_to_minutes(b.requested_end)
                if b_start is not None and b_end is not None:
                    dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
                    if b.requested_date == target_date:
                        occupied.append((b_start, b_start + dur, f"Approved Block {b.block_id}"))
                    elif b.requested_date == next_date:
                        occupied.append((1440 + b_start, 1440 + b_start + dur, f"Next Day Approved Block {b.block_id}"))
                    elif b.requested_date == prev_date:
                        if b_start + dur > 1440:
                            occupied.append((0, (b_start + dur) - 1440, f"Previous Day Approved Block {b.block_id}"))

        # Merge overlapping intervals
        if not occupied:
            return []

        occupied.sort(key=lambda x: x[0])
        merged: List[Tuple[int, int, str]] = []
        curr_start, curr_end, curr_desc = occupied[0]

        for s, e, desc in occupied[1:]:
            if s <= curr_end:
                curr_end = max(curr_end, e)
                curr_desc += f", {desc}"
            else:
                merged.append((curr_start, curr_end, curr_desc))
                curr_start, curr_end, curr_desc = s, e, desc
        merged.append((curr_start, curr_end, curr_desc))

        return merged

    def find_feasible_slots(
        self,
        location: str,
        duration_minutes: int,
        preferred_start: str,
        target_date: date,
        max_slots: int = 5,
        additional_occupancy: Optional[List[Tuple[int, int, str]]] = None,
    ) -> List[FeasibleSlot]:
        """
        Identify free time windows on the target date satisfying the requested duration,
        supporting continuous overnight windows crossing midnight up to early morning (08:00).
        """
        if duration_minutes <= 0 or duration_minutes > 1440:
            return []

        occupied = self._build_location_occupancy(target_date, location, additional_occupancy=additional_occupancy)
        pref_mins = _parse_time_to_minutes(preferred_start) or 600

        # Timeline limit covers target_date (1440) plus early morning window up to 08:00 (480 mins)
        timeline_limit = 1440 + min(duration_minutes, 480)

        free_windows: List[Tuple[int, int]] = []
        current_cursor = 0

        for occ_start, occ_end, _ in occupied:
            if occ_start > current_cursor:
                free_windows.append((current_cursor, min(timeline_limit, occ_start)))
            current_cursor = max(current_cursor, occ_end)

        if current_cursor < timeline_limit:
            free_windows.append((current_cursor, timeline_limit))

        # Filter windows that can accommodate the required duration
        candidate_slots: List[FeasibleSlot] = []
        slot_idx = 1

        for w_start, w_end in free_windows:
            window_len = w_end - w_start
            if window_len >= duration_minutes:
                # 1. Check if preferred start fits directly inside this window
                if w_start <= pref_mins and (pref_mins + duration_minutes) <= min(w_end, timeline_limit) and pref_mins < 1440:
                    s_start = pref_mins
                    s_end = pref_mins + duration_minutes
                    is_match = True
                    fit = 1.0
                    slot = FeasibleSlot(
                        slot_id=f"SLOT-{slot_idx:03d}",
                        location=location,
                        service_date=target_date,
                        start_time=_format_minutes_to_time(s_start),
                        end_time=_format_minutes_to_time(s_end),
                        duration_minutes=duration_minutes,
                        fit_score=fit,
                        is_preferred_match=is_match,
                    )
                    candidate_slots.append(slot)
                    slot_idx += 1

                # 2. Also add window start slot (must start on target_date and end within timeline)
                if w_start < 1440 and (w_start + duration_minutes) <= timeline_limit:
                    s_start = w_start
                    s_end = w_start + duration_minutes
                    dist = abs(s_start - pref_mins)
                    fit = max(0.1, round(1.0 - (dist / 1440.0), 3))
                    slot = FeasibleSlot(
                        slot_id=f"SLOT-{slot_idx:03d}",
                        location=location,
                        service_date=target_date,
                        start_time=_format_minutes_to_time(s_start),
                        end_time=_format_minutes_to_time(s_end),
                        duration_minutes=duration_minutes,
                        fit_score=fit,
                        is_preferred_match=(dist <= 15),
                    )
                    candidate_slots.append(slot)
                    slot_idx += 1

                # 3. If window is large enough, also add an end-aligned slot (must start on target_date)
                if window_len > duration_minutes + 30:
                    s_start = w_end - duration_minutes
                    s_end = w_end
                    if 0 <= s_start < 1440:
                        dist = abs(s_start - pref_mins)
                        fit = max(0.1, round(1.0 - (dist / 1440.0), 3))
                        slot = FeasibleSlot(
                            slot_id=f"SLOT-{slot_idx:03d}",
                            location=location,
                            service_date=target_date,
                            start_time=_format_minutes_to_time(s_start),
                            end_time=_format_minutes_to_time(s_end),
                            duration_minutes=duration_minutes,
                            fit_score=fit,
                            is_preferred_match=(dist <= 15),
                        )
                        candidate_slots.append(slot)
                        slot_idx += 1

        # Deduplicate and sort by fit_score descending
        seen_times = set()
        unique_slots: List[FeasibleSlot] = []
        for s in sorted(candidate_slots, key=lambda x: x.fit_score, reverse=True):
            key = (s.start_time, s.end_time, s.duration_minutes)
            if key not in seen_times:
                seen_times.add(key)
                unique_slots.append(s)

        return unique_slots[:max_slots]

    def schedule(
        self,
        target_date: Optional[date] = None,
        priority_filter: Optional[str] = None,
        location_filter: Optional[str] = None,
        schedule_type: str = "daily",
    ) -> ScheduleResult:
        """
        Generate full schedule assignments for all active maintenance and block requests.
        """
        s_date = target_date or date.today()

        # Determine scheduling horizon
        horizon_days = _get_horizon_days(schedule_type=schedule_type, start_date=s_date)
        schedule_dates = _generate_schedule_dates(start_date=s_date, horizon_days=horizon_days)
        schedule_date_set = set(schedule_dates)

        # Combine maintenance records and block records for scheduling
        requests_to_schedule = []

        for m in self.maintenance_records:
            if m.requested_date in schedule_date_set and m.maintenance_required:
                if priority_filter and m.priority.value.lower() != priority_filter.lower():
                    continue
                if location_filter and location_filter.lower() not in m.location.lower():
                    continue
                pref_str = (
                    m.preferred_start.strftime("%H:%M")
                    if hasattr(m.preferred_start, "strftime")
                    else str(m.preferred_start)
                )
                requests_to_schedule.append({
                    "type": "maintenance",
                    "id": m.asset_id,
                    "asset_id": m.asset_id,
                    "block_id": None,
                    "location": m.location,
                    "priority": m.priority,
                    "duration": m.duration_minutes,
                    "preferred_start": pref_str,
                    "requested_date": m.requested_date,
                })

        for b in self.block_records:
            if b.requested_date in schedule_date_set and b.status != BlockStatus.CANCELLED:
                if priority_filter and b.priority.value.lower() != priority_filter.lower():
                    continue
                if location_filter and location_filter.lower() not in b.location.lower():
                    continue
                dur = _calculate_duration_minutes(b.requested_start, b.requested_end)
                requests_to_schedule.append({
                    "type": "block",
                    "id": b.block_id,
                    "asset_id": None,
                    "block_id": b.block_id,
                    "location": b.location,
                    "priority": b.priority,
                    "duration": dur,
                    "preferred_start": b.requested_start,
                    "requested_date": b.requested_date,
                })

        # Sort requests by priority (Critical first), duration descending, and request ID for strict determinism
        requests_to_schedule.sort(
            key=lambda r: (
                PRIORITY_RANK.get(r["priority"], 1),
                r["duration"],
                r["id"],
            ),
            reverse=True,
        )

        scheduled_items: List[MaintenanceScheduleItem] = []
        unfeasible_items: List[MaintenanceScheduleItem] = []
        sched_counter = 1

        # Track maintenance assignments made during this scheduling run: (date, location, start, end, id)
        assigned_intervals: List[Tuple[date, str, int, int, str]] = []

        for req in requests_to_schedule:
            candidate_slots: List[FeasibleSlot] = []

            # Prefer the originally requested date first
            candidate_dates = sorted(
                schedule_dates,
                key=lambda d: (
                    0 if d == req["requested_date"] else 1,
                    abs((d - req["requested_date"]).days),
                ),
            )

            for candidate_date in candidate_dates:
                slots = self.find_feasible_slots(
                    location=req["location"],
                    duration_minutes=req["duration"],
                    preferred_start=req["preferred_start"],
                    target_date=candidate_date,
                    max_slots=5,
                )
                for slot in slots:
                    slot_start = _parse_time_to_minutes(slot.start_time) or 0
                    slot_end = slot_start + slot.duration_minutes

                    # Check against tasks already assigned by this scheduler run
                    has_internal_conflict = False
                    for (assigned_date, assigned_location, assigned_start, assigned_end, _) in assigned_intervals:
                        if assigned_date != candidate_date:
                            continue
                        if not _locations_match(assigned_location, req["location"]):
                            continue
                        if slot_start < assigned_end and slot_end > assigned_start:
                            has_internal_conflict = True
                            break

                    if not has_internal_conflict:
                        candidate_slots.append(slot)

            if candidate_slots:
                primary = max(
                    candidate_slots,
                    key=lambda slot: (
                        slot.fit_score,
                        -abs(
                            (_parse_time_to_minutes(slot.start_time) or 0)
                            - (_parse_time_to_minutes(req["preferred_start"]) or 600)
                        ),
                    ),
                )
                alts = [slot for slot in candidate_slots if slot != primary][:5]
                status = (
                    "Scheduled"
                    if (primary.service_date == req["requested_date"] and primary.is_preferred_match)
                    else "AlternativeSuggested"
                )
                item = MaintenanceScheduleItem(
                    schedule_id=f"SCHED-{sched_counter:04d}",
                    request_id=req["id"],
                    asset_id=req["asset_id"],
                    block_id=req["block_id"],
                    location=req["location"],
                    priority=req["priority"],
                    requested_duration=req["duration"],
                    preferred_start=req["preferred_start"],
                    assigned_slot=primary,
                    alternative_slots=alts,
                    status=status,
                    notes=f"Feasible window identified within the {schedule_type} scheduling horizon.",
                )
                scheduled_items.append(item)

                assigned_start = _parse_time_to_minutes(primary.start_time) or 0
                assigned_end = assigned_start + primary.duration_minutes
                assigned_intervals.append(
                    (
                        primary.service_date,
                        req["location"],
                        assigned_start,
                        assigned_end,
                        req["id"],
                    )
                )
            else:
                item = MaintenanceScheduleItem(
                    schedule_id=f"SCHED-{sched_counter:04d}",
                    request_id=req["id"],
                    asset_id=req["asset_id"],
                    block_id=req["block_id"],
                    location=req["location"],
                    priority=req["priority"],
                    requested_duration=req["duration"],
                    preferred_start=req["preferred_start"],
                    assigned_slot=None,
                    alternative_slots=[],
                    status="Unfeasible",
                    notes=f"No conflict-free time window of sufficient duration available within the {schedule_type} scheduling horizon.",
                )
                unfeasible_items.append(item)

            sched_counter += 1

        return ScheduleResult(
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_date=s_date,
            total_requested=len(requests_to_schedule),
            total_scheduled=len(scheduled_items),
            total_unfeasible=len(unfeasible_items),
            scheduled_items=scheduled_items,
            unfeasible_items=unfeasible_items,
        )

    # -----------------------------------------------------------------------
    # Phase 3 — Daily Scheduling Pipeline
    # -----------------------------------------------------------------------

    def determine_daily_availability(
        self,
        problem: DailySchedulingProblem,
    ) -> DailyAvailabilityReport:
        """
        Determine usable daily block/time windows from DailySchedulingProblem.
        Classifies windows into Available, Restricted, or Blocked based on timetable passage
        constraints, goods-train forecasts, and operational restrictions.
        Provides an auditable diagnostic trail.
        """
        s_date = problem.target_date
        buffer_mins = problem.buffer_minutes

        audited_windows: List[CorridorAvailabilityWindow] = []
        blocked_periods: List[Dict[str, Any]] = []
        timetable_restrictions: List[Dict[str, Any]] = []
        goods_train_restrictions: List[Dict[str, Any]] = []
        active_movement_restrictions: List[Dict[str, Any]] = []
        corridor_stats: Dict[str, Dict[str, Any]] = {}

        # 1. Process Timetable Constraints into blocked intervals and restrictions
        timetable_intervals: List[Tuple[int, int, str, str]] = []  # (start_m, end_m, desc, station)
        for tt in problem.timetable_constraints:
            arr_m = _parse_time_to_minutes(tt.get("arrival_time"))
            dep_m = _parse_time_to_minutes(tt.get("departure_time"))
            station = tt.get("station_code") or ""
            train_id = tt.get("train_id") or "Train"

            t_start = arr_m if arr_m is not None else (dep_m - 5 if dep_m is not None else 600)
            t_end = dep_m if dep_m is not None else (arr_m + 5 if arr_m is not None else 605)
            start_buf = max(0, t_start - buffer_mins)
            end_buf = min(1440, t_end + buffer_mins)

            desc = f"Passenger Train {train_id} at {station} ({_format_minutes_to_time(t_start)}-{_format_minutes_to_time(t_end)})"
            timetable_intervals.append((start_buf, end_buf, desc, station))

            timetable_restrictions.append({
                "train_id": train_id,
                "station_code": station,
                "passage_window": f"{_format_minutes_to_time(t_start)}-{_format_minutes_to_time(t_end)}",
                "buffer_window": f"{_format_minutes_to_time(start_buf)}-{_format_minutes_to_time(end_buf)}",
                "impact": f"Possession blocked within {buffer_mins}m buffer",
            })

            blocked_periods.append({
                "start_time": _format_minutes_to_time(start_buf),
                "end_time": _format_minutes_to_time(end_buf),
                "location": station,
                "reason": desc,
                "type": "Timetable",
            })

        # 2. Process Goods Train Forecasts
        goods_intervals: List[Tuple[int, int, str, str]] = []  # (start_m, end_m, desc, section)
        for g in problem.goods_train_forecast_windows:
            f_start = _parse_time_to_minutes(g.get("forecasted_entry"))
            f_end = _parse_time_to_minutes(g.get("forecasted_exit"))
            sec = g.get("section") or ""
            tid = g.get("train_id") or "Goods"
            conf = g.get("confidence", 0.8)

            if f_start is not None and f_end is not None:
                if f_end < f_start:
                    f_end += 1440
                start_buf = max(0, f_start - buffer_mins)
                end_buf = min(1440, f_end + buffer_mins)
                desc = f"Goods Train {tid} on {sec} ({_format_minutes_to_time(f_start)}-{_format_minutes_to_time(f_end)})"
                goods_intervals.append((start_buf, end_buf, desc, sec))

                goods_train_restrictions.append({
                    "train_id": tid,
                    "section": sec,
                    "window": f"{_format_minutes_to_time(f_start)}-{_format_minutes_to_time(f_end)}",
                    "confidence": conf,
                    "impact": "Possession caution / speed restriction recommended",
                })

                blocked_periods.append({
                    "start_time": _format_minutes_to_time(start_buf),
                    "end_time": _format_minutes_to_time(end_buf),
                    "location": sec,
                    "reason": desc,
                    "type": "GoodsForecast",
                })

        # 3. Process Operational Restrictions from Problem
        for op_res in problem.operational_restrictions:
            active_movement_restrictions.append({
                "restriction": op_res,
                "enforced": True,
                "scope": "Corridor-wide",
            })

        # 4. Audit each Available Window in Problem
        for win in problem.available_windows:
            w_start_m = _parse_time_to_minutes(win.start_time) or 0
            w_end_m = _parse_time_to_minutes(win.end_time) or (w_start_m + win.duration_minutes)
            if w_end_m < w_start_m:
                w_end_m += 1440

            win_restrictions = list(win.restrictions)
            status = win.status

            # Check timetable overlap
            has_timetable_block = False
            for t_start, t_end, desc, stn in timetable_intervals:
                if _locations_match(win.corridor, stn) or (win.section and _locations_match(win.section, stn)):
                    if max(w_start_m, t_start) < min(w_end_m, t_end):
                        has_timetable_block = True
                        win_restrictions.append(f"Direct buffer contention with {desc}")

            # Check goods train overlap
            has_goods_restriction = False
            for g_start, g_end, desc, sec in goods_intervals:
                if _locations_match(win.corridor, sec) or (win.section and _locations_match(win.section, sec)):
                    if max(w_start_m, g_start) < min(w_end_m, g_end):
                        has_goods_restriction = True
                        win_restrictions.append(f"Projected goods train interaction: {desc}")

            # Determine final auditable status
            if has_timetable_block:
                status = "Blocked"
            elif has_goods_restriction:
                status = "Restricted" if status != "Blocked" else "Blocked"
            elif status not in ("Available", "Restricted", "Blocked"):
                status = "Available"

            audited_win = CorridorAvailabilityWindow(
                window_id=win.window_id,
                corridor=win.corridor,
                service_date=win.service_date,
                start_time=win.start_time,
                end_time=win.end_time,
                duration_minutes=win.duration_minutes,
                block_id=win.block_id,
                section=win.section,
                status=status,
                restrictions=win_restrictions,
                capacity_info=win.capacity_info,
                max_parallel_works=win.max_parallel_works,
            )
            audited_windows.append(audited_win)

            # Track corridor capacity
            corr = win.corridor
            corridor_stats.setdefault(corr, {
                "total_windows": 0,
                "available_windows": 0,
                "restricted_windows": 0,
                "blocked_windows": 0,
                "total_window_minutes": 0,
                "usable_minutes": 0,
            })
            corridor_stats[corr]["total_windows"] += 1
            corridor_stats[corr]["total_window_minutes"] += win.duration_minutes
            if status == "Available":
                corridor_stats[corr]["available_windows"] += 1
                corridor_stats[corr]["usable_minutes"] += win.duration_minutes
            elif status == "Restricted":
                corridor_stats[corr]["restricted_windows"] += 1
                corridor_stats[corr]["usable_minutes"] += int(win.duration_minutes * 0.75)
            elif status == "Blocked":
                corridor_stats[corr]["blocked_windows"] += 1

        rep_id = f"AVREP-{s_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        return DailyAvailabilityReport(
            report_id=rep_id,
            target_date=s_date,
            generated_at=datetime.now(timezone.utc).isoformat(),
            available_windows=audited_windows,
            blocked_periods=blocked_periods,
            timetable_restrictions=timetable_restrictions,
            goods_train_restrictions=goods_train_restrictions,
            active_movement_restrictions=active_movement_restrictions,
            corridor_capacities=corridor_stats,
        )

    def match_work_to_blocks(
        self,
        candidate_works: List[CandidateWorkItem],
        availability_report: DailyAvailabilityReport,
    ) -> WorkMatchReport:
        """
        Evaluate candidate work items against available corridor windows.
        Identifies feasible candidate relationships (WorkBlockMatch) without performing
        global optimization (which is reserved for CP-SAT in Phase 4).
        Records audit diagnostics and categorizes rejection causes.
        """
        successful_matches: List[WorkBlockMatch] = []
        rejected_works: List[Dict[str, Any]] = []
        rejection_summary: Dict[str, int] = {
            "Location mismatch": 0,
            "Insufficient duration": 0,
            "Resource unavailable": 0,
            "Asset incompatibility": 0,
            "Operational incompatibility": 0,
        }

        matched_work_ids: Set[str] = set()
        evaluated_matches: List[WorkBlockMatch] = []

        for work in candidate_works:
            work_had_compatible_match = False
            work_rejections_for_candidate: List[str] = []

            for window in availability_report.available_windows:
                reasons: List[str] = []
                details: Dict[str, Any] = {}

                # 1. Location / Corridor Match
                loc_match = (
                    _locations_match(work.location, window.corridor)
                    or (work.corridor and _locations_match(work.corridor, window.corridor))
                    or (window.section and _locations_match(work.location, window.section))
                )
                if not loc_match:
                    reasons.append("Location mismatch")
                    details["location"] = f"Work location '{work.location}' does not match window corridor '{window.corridor}'"
                else:
                    details["location"] = "Location matched"

                # 2. Operational Incompatibility (Blocked Window or Operational Contention)
                if window.status == "Blocked":
                    reasons.append("Operational incompatibility")
                    details["window_status"] = f"Window {window.window_id} is Blocked by timetable traffic"
                else:
                    details["window_status"] = f"Window status is {window.status}"

                # 3. Duration Check
                if window.duration_minutes < work.required_duration_minutes:
                    reasons.append("Insufficient duration")
                    details["duration"] = f"Required {work.required_duration_minutes}m exceeds available {window.duration_minutes}m"
                else:
                    details["duration"] = f"Required {work.required_duration_minutes}m fits available {window.duration_minutes}m"

                # 4. Resource / Capacity Check
                max_crew = window.capacity_info.get("max_crew") if window.capacity_info else None
                if max_crew is not None and work.required_resources > max_crew:
                    reasons.append("Resource unavailable")
                    details["resources"] = f"Required resources {work.required_resources} exceeds window limit {max_crew}"
                elif window.max_parallel_works < 1:
                    reasons.append("Resource unavailable")
                    details["resources"] = "Window parallel works capacity saturated"
                else:
                    details["resources"] = f"Resources {work.required_resources} satisfied"

                # 5. Asset Incompatibility Check
                asset_compat = True
                for constraint in work.constraints:
                    c_lower = constraint.lower()
                    for restr in window.restrictions:
                        r_lower = restr.lower()
                        # e.g. traction power active vs OHE isolation required
                        if "ohe" in c_lower and ("traction active" in r_lower or "no ohe" in r_lower):
                            asset_compat = False
                            details["asset_compatibility"] = f"Constraint '{constraint}' conflicts with window restriction '{restr}'"
                        elif "heavy" in c_lower and "no heavy" in r_lower:
                            asset_compat = False
                            details["asset_compatibility"] = f"Constraint '{constraint}' conflicts with window restriction '{restr}'"

                if not asset_compat:
                    reasons.append("Asset incompatibility")
                else:
                    details.setdefault("asset_compatibility", "Asset compatible with corridor window")

                # Determine Compatibility and Fit Score
                is_compatible = (len(reasons) == 0)

                if is_compatible:
                    # Calculate temporal fit score based on deviation from preferred start
                    if work.preferred_start:
                        pref_m = _parse_time_to_minutes(work.preferred_start)
                        win_start_m = _parse_time_to_minutes(window.start_time)
                        if pref_m is not None and win_start_m is not None:
                            dist = abs(pref_m - win_start_m)
                            fit = max(0.1, round(1.0 - (dist / 1440.0), 3))
                        else:
                            fit = 1.0
                    else:
                        fit = 1.0

                    work_had_compatible_match = True
                    matched_work_ids.add(work.work_id)
                else:
                    fit = 0.0
                    work_rejections_for_candidate.extend(reasons)

                ai_prio = getattr(work, "priority_enrichment", None)
                ai_val = getattr(work, "priority_value", None)
                if ai_prio is not None:
                    details["ai_priority"] = ai_prio.model_dump()
                elif ai_val is not None:
                    details["ai_priority"] = {"priority_value": ai_val}
                elif getattr(work, "ai_priority_context", None):
                    details["ai_priority"] = work.ai_priority_context

                match_item = WorkBlockMatch(
                    match_id=f"MATCH-{work.work_id}-{window.window_id}",
                    work_id=work.work_id,
                    window_id=window.window_id,
                    is_compatible=is_compatible,
                    fit_score=fit,
                    compatibility_details=details,
                    rejection_reasons=reasons,
                    priority_value=ai_val,
                    priority_enrichment=ai_prio,
                )
                evaluated_matches.append(match_item)
                if is_compatible:
                    successful_matches.append(match_item)

            if not work_had_compatible_match:
                # Candidate work had no compatible window among all evaluated windows
                unique_reasons = list(dict.fromkeys(work_rejections_for_candidate))
                rejected_works.append({
                    "work_id": work.work_id,
                    "location": work.location,
                    "corridor": work.corridor,
                    "priority": work.priority.value if work.priority else "None",
                    "priority_value": getattr(work, "priority_value", None),
                    "duration_minutes": work.required_duration_minutes,
                    "reasons": unique_reasons,
                })
                for r in unique_reasons:
                    if r in rejection_summary:
                        rejection_summary[r] += 1
                    else:
                        rejection_summary[r] = rejection_summary.get(r, 0) + 1

        total_works = len(candidate_works)
        total_matches = len(matched_work_ids)
        total_rejected = len(rejected_works)

        rep_id = f"MATCHREP-{availability_report.target_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        return WorkMatchReport(
            report_id=rep_id,
            target_date=availability_report.target_date,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_works=total_works,
            total_matches=total_matches,
            total_rejected=total_rejected,
            successful_matches=successful_matches,
            rejected_works=rejected_works,
            rejection_summary=rejection_summary,
        )

    def build_cpsat_input(
        self,
        problem: DailySchedulingProblem,
        match_report: WorkMatchReport,
        availability_report: Optional[DailyAvailabilityReport] = None,
    ) -> OptimizationRequest:
        """
        Transform prepared daily scheduling problem and match report into canonical OptimizationRequest.
        Transfers candidate constraints, mandatory status, pinned slots, priorities, and capacities.
        Transfers candidate works and successful work-block pairings for downstream CP-SAT optimization.
        """
        mandatory_ids = [w.work_id for w in problem.candidate_works if w.is_mandatory]
        pinned = {w.work_id: w.pinned_slot for w in problem.candidate_works if w.is_pinned and w.pinned_slot}

        # Preserve priority information and explicit priority_value if present
        priority_overrides: Dict[str, Any] = {}
        for w in problem.candidate_works:
            pv = getattr(w, "priority_value", None)
            if pv is not None:
                priority_overrides[w.work_id] = str(pv)
            elif w.priority:
                priority_overrides[w.work_id] = w.priority.value

        # Custom capacities from availability report
        capacities: Optional[Dict[str, int]] = None
        if availability_report and availability_report.corridor_capacities:
            capacities = {}
            for corr, stats in availability_report.corridor_capacities.items():
                capacities[f"cap_{corr}"] = stats.get("usable_minutes", 0)

        windows_list = availability_report.available_windows if availability_report else problem.available_windows

        return OptimizationRequest(
            target_date=problem.target_date,
            horizon_days=1,
            buffer_minutes=problem.buffer_minutes,
            mandatory_request_ids=mandatory_ids if mandatory_ids else None,
            pinned_slots=pinned if pinned else None,
            priority_overrides=priority_overrides if priority_overrides else None,
            custom_capacities=capacities,
            include_forecast=bool(problem.goods_train_forecast_windows),
            max_slots_per_request=5,
            strategy_preset="balanced",
            candidate_works=problem.candidate_works,
            candidate_matches=match_report.successful_matches,
            available_windows=windows_list,
        )

    def schedule_daily(
        self,
        problem: DailySchedulingProblem,
        invoke_solver: bool = True,
        optimizer: Optional[Any] = None,
    ) -> DailyScheduleResult:
        """
        Orchestrate daily scheduling preparation and CP-SAT mathematical optimization:
        DailySchedulingProblem → determine_daily_availability → match_work_to_blocks → build_cpsat_input → CP_SAT_Optimizer.
        Produces full DailyScheduleResult with scheduled assignments, diagnostics, and solver statistics.
        """
        # Step 1: Availability Audit
        avail_report = self.determine_daily_availability(problem)

        # Step 2: Work-to-block candidate matching
        match_report = self.match_work_to_blocks(problem.candidate_works, avail_report)

        # Step 3: Prepare CP-SAT input contract
        opt_req = self.build_cpsat_input(problem, match_report, avail_report)

        plan_id = f"DSCHED-{problem.target_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # If solver invocation is disabled (pre-solver inspection / diagnostic mode)
        if not invoke_solver:
            return DailyScheduleResult(
                plan_id=plan_id,
                target_date=problem.target_date,
                generated_at=datetime.now(timezone.utc).isoformat(),
                total_scheduled=0,
                total_unscheduled=match_report.total_rejected,
                scheduled_works=[m.model_dump() for m in match_report.successful_matches],
                optimized_block_assignments=[],
                unscheduled_works=[],
                diagnostics={
                    "total_windows_audited": len(avail_report.available_windows),
                    "rejection_summary": match_report.rejection_summary,
                    "corridor_capacities": avail_report.corridor_capacities,
                },
                matching_statistics={
                    "total_works": match_report.total_works,
                    "total_matches": match_report.total_matches,
                    "total_rejected": match_report.total_rejected,
                    "rejection_summary": match_report.rejection_summary,
                },
                optimization_metadata={
                    "optimization_request": opt_req.model_dump(),
                    "status": "PreparedForOptimization",
                },
            )

        # Step 4: Invoke CP-SAT Optimizer (Phase 4 Integration)
        from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
        from backend.app.optimizer.schemas import OptimizationStatus

        if optimizer is None:
            optimizer = CP_SAT_Optimizer(
                maintenance_records=self.maintenance_records,
                block_records=self.block_records,
                timetables=self.timetables,
                goods_forecasts=self.goods_forecasts,
                movements=self.movements,
                trains=getattr(self, "trains", None),
            )

        opt_res = optimizer.optimize(request=opt_req)

        # Build categorized unscheduled works preserving matching vs solver diagnostics
        combined_unscheduled: List[Dict[str, Any]] = []
        seen_unscheduled_ids = set()

        candidate_map = {w.work_id: w for w in problem.candidate_works}

        # 1. Pre-solver matching rejections (no compatible window exists)
        for r_work in match_report.rejected_works:
            r_id = r_work.get("work_id")
            if r_id and r_id not in seen_unscheduled_ids:
                seen_unscheduled_ids.add(r_id)
                c_work = candidate_map.get(r_id)
                pv = getattr(c_work, "priority_value", None) if c_work else r_work.get("priority_value")
                combined_unscheduled.append({
                    "request_id": r_id,
                    "work_id": r_id,
                    "location": r_work.get("location"),
                    "corridor": r_work.get("corridor"),
                    "priority": r_work.get("priority"),
                    "priority_value": pv,
                    "duration_minutes": r_work.get("duration_minutes"),
                    "source": "PreSolverMatching",
                    "reason": f"No compatible block exists: {', '.join(r_work.get('reasons', []))}",
                    "rejection_reasons": r_work.get("reasons", []),
                })

        # 2. Solver unscheduled blocks (had candidate slots, but CP-SAT did not select)
        for un_b in opt_res.unscheduled_blocks:
            u_id = un_b.request_id
            if u_id and u_id not in seen_unscheduled_ids:
                seen_unscheduled_ids.add(u_id)
                c_work = candidate_map.get(u_id)
                pv = getattr(un_b, "priority_value", None) or (getattr(c_work, "priority_value", None) if c_work else None)
                combined_unscheduled.append({
                    "request_id": u_id,
                    "work_id": u_id,
                    "asset_id": un_b.asset_id,
                    "location": un_b.location,
                    "priority": un_b.priority.value if hasattr(un_b.priority, "value") else str(un_b.priority),
                    "priority_value": pv,
                    "duration_minutes": un_b.duration_minutes,
                    "source": "CP_SAT_Solver",
                    "reason": un_b.reason,
                    "resource_contention": un_b.resource_contention,
                })

        # Total scheduled and unscheduled counts
        num_scheduled = len(opt_res.scheduled_blocks) if opt_res.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE) else 0
        total_unassigned = len(combined_unscheduled)

        # Optimization metadata with solver telemetry
        opt_meta = {
            "optimization_request": opt_req.model_dump(),
            "status": opt_res.status.value,
            "objective_value": opt_res.objective_value,
            "plan_id": opt_res.plan_id,
            "wall_time_seconds": opt_res.solver_statistics.wall_time_seconds,
            "num_variables": opt_res.solver_statistics.num_variables,
            "num_constraints": opt_res.solver_statistics.num_constraints,
        }
        if opt_res.status == OptimizationStatus.INFEASIBLE:
            opt_meta["infeasibility_explanation"] = "CP-SAT proved problem has no mathematically feasible solution under hard constraints"

        # Attach AI priority context to scheduled blocks if available
        for block in opt_res.scheduled_blocks:
            c_work = candidate_map.get(block.request_id)
            if c_work:
                if getattr(block, "priority_value", None) is None:
                    block.priority_value = getattr(c_work, "priority_value", None)
                if getattr(block, "priority_enrichment", None) is None:
                    block.priority_enrichment = getattr(c_work, "priority_enrichment", None)

        ai_enriched_count = sum(
            1 for w in problem.candidate_works
            if getattr(w, "priority_value", None) is not None or getattr(w, "priority_enrichment", None) is not None
        )

        diagnostics = {
            "solver_status": opt_res.status.value,
            "objective_value": opt_res.objective_value,
            "total_windows_audited": len(avail_report.available_windows),
            "rejection_summary": match_report.rejection_summary,
            "corridor_capacities": avail_report.corridor_capacities,
            "pre_solver_rejected_count": len(match_report.rejected_works),
            "solver_unscheduled_count": len(opt_res.unscheduled_blocks),
            "conflicts_before": opt_res.solver_statistics.conflicts_before,
            "conflicts_after": opt_res.solver_statistics.conflicts_after,
            "ai_prioritization_summary": {
                "total_candidate_works": len(problem.candidate_works),
                "ai_enriched_works": ai_enriched_count,
            },
        }

        sched_blocks_dump = [b.model_dump() if hasattr(b, "model_dump") else b for b in opt_res.scheduled_blocks]

        return DailyScheduleResult(
            plan_id=plan_id,
            target_date=problem.target_date,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_scheduled=num_scheduled,
            total_unscheduled=total_unassigned,
            scheduled_works=sched_blocks_dump,
            optimized_block_assignments=opt_res.scheduled_blocks,
            unscheduled_works=combined_unscheduled,
            diagnostics=diagnostics,
            matching_statistics={
                "total_works": match_report.total_works,
                "total_matches": match_report.total_matches,
                "total_rejected": match_report.total_rejected,
                "rejection_summary": match_report.rejection_summary,
            },
            optimization_metadata=opt_meta,
            solver_statistics=opt_res.solver_statistics,
        )


# Phase 3 Scheduler Alias
DailyScheduler = MaintenanceScheduler

