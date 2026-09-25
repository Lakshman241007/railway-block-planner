"""
Tests for Phase 2: CP-SAT Objective + Constraint Hardening.

Covers the complete Phase 2 Test Matrix:
  TEST 1: Block availability (valid block, service date, times, availability window)
  TEST 2: Maintenance duration (short, normal, equal to window, longer than window)
  TEST 3: Work / block compatibility (location / corridor matching)
  TEST 4: Non-overlapping possessions (same location/block + overlapping times vs adjacency)
  TEST 5: Safety buffers (maintenance 10:00-11:00 vs train movement 11:15 with 30m buffer)
  TEST 6: Train movement conflicts (overlap vs safe separation vs multiple surrounding trains)
  TEST 7: Resource constraints (Track Tamper capacity 1 overlap vs adjacency)
  TEST 8: High priority vs low priority under contention (priority_value 95 vs 40)
  TEST 9: High priority but infeasible (priority_value 95 no slot vs priority_value 40 feasible)
  TEST 10: Multiple feasible jobs with different priorities
  TEST 11: All requests feasible
  TEST 12: No requests feasible (0 scheduled is OPTIMAL, not automatically INFEASIBLE)
  TEST 13: Existing conflict detection integration (ConflictDetector & validate_final_plan)
  TEST 14: Objective balance (priority, block utilization, operational efficiency)
  IMPORTANT PRIORITY TEST: Competing jobs with 2 slots each vs infeasible high-priority
"""

from datetime import date, time, timedelta
import pytest

from backend.app.block_planner.schemas import CandidateWorkItem, CorridorAvailabilityWindow
from backend.app.scheduler.schemas import WorkBlockMatch
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.objective import compute_slot_coefficient
from backend.app.optimizer.schemas import (
    ObjectiveWeights,
    OptimizationRequest,
    OptimizationStatus,
)
from backend.app.optimizer.validator import validate_final_plan
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    BlockType,
    MaintenanceRecord,
    MaintenanceStatus,
    MovementRecord,
    Priority,
    TimetableRecord,
    TrainRecord,
    TrainStatus,
)


@pytest.fixture
def base_date() -> date:
    return date(2026, 9, 10)


# ===========================================================================
# TEST 1: Block Availability
# ===========================================================================
class TestBlockAvailability:
    """TEST 1: CP-SAT can only select valid block / possession windows."""

    def test_allocates_only_within_valid_available_windows(self, base_date: date):
        """Candidates on blocked windows are excluded from allocation."""
        work = CandidateWorkItem(
            work_id="WORK-AVAIL-1",
            asset_id="AST-01",
            location="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority_value=85.0,
            priority=Priority.HIGH,
            preferred_date=base_date,
        )
        # Window 1 is Blocked by timetable traffic; Window 2 is Available
        win_blocked = CorridorAvailabilityWindow(
            window_id="WIN-BLOCKED",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="08:00",
            end_time="10:00",
            duration_minutes=120,
            status="Blocked",
        )
        win_avail = CorridorAvailabilityWindow(
            window_id="WIN-AVAILABLE",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="01:00",
            end_time="03:00",
            duration_minutes=120,
            status="Available",
        )
        matches = [
            WorkBlockMatch(match_id="M-1", work_id="WORK-AVAIL-1", window_id="WIN-BLOCKED", is_compatible=True),
            WorkBlockMatch(match_id="M-2", work_id="WORK-AVAIL-1", window_id="WIN-AVAILABLE", is_compatible=True),
        ]

        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work],
                available_windows=[win_blocked, win_avail],
                candidate_matches=matches,
            )
        )

        assert result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(result.scheduled_blocks) == 1
        blk = result.scheduled_blocks[0]
        # Must be assigned to the Available window, NOT the Blocked one
        assert blk.start_time == "01:00"
        assert blk.end_time == "02:00"
        assert blk.duration_minutes == 60


# ===========================================================================
# TEST 2: Maintenance Duration
# ===========================================================================
class TestMaintenanceDuration:
    """TEST 2: Verify end_time = start_time + duration and window containment."""

    def test_short_normal_and_exact_duration_fit(self, base_date: date):
        """Jobs that fit (short, normal, or exactly equal to window) are scheduled with preserved duration."""
        # 30m short job, 60m normal job, 120m exact fit job
        works = [
            CandidateWorkItem(work_id="W-SHORT", location="Chennai-Arakkonam", required_duration_minutes=30, priority_value=70.0),
            CandidateWorkItem(work_id="W-NORMAL", location="Chennai-Arakkonam", required_duration_minutes=60, priority_value=80.0),
            CandidateWorkItem(work_id="W-EXACT", location="Chennai-Arakkonam", required_duration_minutes=120, priority_value=90.0),
        ]
        windows = [
            CorridorAvailabilityWindow(window_id="WIN-S", corridor="Chennai-Arakkonam", service_date=base_date, start_time="01:00", end_time="02:00", duration_minutes=60),
            CorridorAvailabilityWindow(window_id="WIN-N", corridor="Chennai-Arakkonam", service_date=base_date, start_time="02:00", end_time="03:30", duration_minutes=90),
            CorridorAvailabilityWindow(window_id="WIN-E", corridor="Chennai-Arakkonam", service_date=base_date, start_time="04:00", end_time="06:00", duration_minutes=120),
        ]
        matches = [
            WorkBlockMatch(match_id="M-S", work_id="W-SHORT", window_id="WIN-S", is_compatible=True),
            WorkBlockMatch(match_id="M-N", work_id="W-NORMAL", window_id="WIN-N", is_compatible=True),
            WorkBlockMatch(match_id="M-E", work_id="W-EXACT", window_id="WIN-E", is_compatible=True),
        ]

        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=works,
                available_windows=windows,
                candidate_matches=matches,
            )
        )

        assert len(result.scheduled_blocks) == 3
        scheduled_map = {b.request_id: b for b in result.scheduled_blocks}

        # Check duration preservation: end_time = start_time + maintenance_duration
        assert scheduled_map["W-SHORT"].start_time == "01:00"
        assert scheduled_map["W-SHORT"].end_time == "01:30"
        assert scheduled_map["W-SHORT"].duration_minutes == 30

        assert scheduled_map["W-NORMAL"].start_time == "02:00"
        assert scheduled_map["W-NORMAL"].end_time == "03:00"
        assert scheduled_map["W-NORMAL"].duration_minutes == 60

        assert scheduled_map["W-EXACT"].start_time == "04:00"
        assert scheduled_map["W-EXACT"].end_time == "06:00"
        assert scheduled_map["W-EXACT"].duration_minutes == 120

    def test_job_longer_than_window_is_rejected(self, base_date: date):
        """A maintenance job longer than available window cannot fit and must not be scheduled."""
        work = CandidateWorkItem(
            work_id="W-TOO-LONG",
            location="Chennai-Arakkonam",
            required_duration_minutes=180,  # 3 hours
            priority_value=99.0,
        )
        # Window is only 2 hours (120 minutes)
        win = CorridorAvailabilityWindow(
            window_id="WIN-SHORT",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="01:00",
            end_time="03:00",
            duration_minutes=120,
        )
        match = WorkBlockMatch(match_id="M-1", work_id="W-TOO-LONG", window_id="WIN-SHORT", is_compatible=True)

        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work],
                available_windows=[win],
                candidate_matches=[match],
            )
        )

        assert len(result.scheduled_blocks) == 0
        assert len(result.unscheduled_blocks) == 1
        assert result.unscheduled_blocks[0].request_id == "W-TOO-LONG"


# ===========================================================================
# TEST 3: Work / Block Compatibility
# ===========================================================================
class TestWorkBlockCompatibility:
    """TEST 3: Work is assigned only to compatible blocks / corridors."""

    def test_location_mismatch_prevents_slot_allocation(self, base_date: date):
        """Work for Tambaram-Chengalpattu cannot be assigned to Chennai-Arakkonam window."""
        work = CandidateWorkItem(
            work_id="W-TBM",
            location="Tambaram-Chengalpattu",
            required_duration_minutes=60,
            priority_value=85.0,
        )
        win = CorridorAvailabilityWindow(
            window_id="WIN-MAS-AJJ",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="01:00",
            end_time="03:00",
            duration_minutes=120,
        )
        match = WorkBlockMatch(match_id="M-INCOMPAT", work_id="W-TBM", window_id="WIN-MAS-AJJ", is_compatible=True)

        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work],
                available_windows=[win],
                candidate_matches=[match],
            )
        )

        assert len(result.scheduled_blocks) == 0
        assert len(result.unscheduled_blocks) == 1


# ===========================================================================
# TEST 4: Non-Overlapping Possessions
# ===========================================================================
class TestNonOverlappingPossessions:
    """TEST 4: Overlapping times at same location cannot both be scheduled; adjacent times are permitted."""

    def test_overlapping_possessions_at_same_location_mutually_exclusive(self, base_date: date):
        """Job A: 10:00-12:00, Job B: 11:00-13:00 on same section -> only one can be selected."""
        job_a = CandidateWorkItem(
            work_id="JOB-A",
            location="Chennai-Arakkonam",
            required_duration_minutes=120,
            priority_value=90.0,
            priority=Priority.HIGH,
        )
        job_b = CandidateWorkItem(
            work_id="JOB-B",
            location="Chennai-Arakkonam",
            required_duration_minutes=120,
            priority_value=50.0,
            priority=Priority.MEDIUM,
        )
        # Windows: Win A is 10:00-12:00, Win B is 11:00-13:00 (overlapping on same track)
        win_a = CorridorAvailabilityWindow(
            window_id="WIN-A",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="10:00",
            end_time="12:00",
            duration_minutes=120,
        )
        win_b = CorridorAvailabilityWindow(
            window_id="WIN-B",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="11:00",
            end_time="13:00",
            duration_minutes=120,
        )
        matches = [
            WorkBlockMatch(match_id="M-A", work_id="JOB-A", window_id="WIN-A", is_compatible=True),
            WorkBlockMatch(match_id="M-B", work_id="JOB-B", window_id="WIN-B", is_compatible=True),
        ]
        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[job_a, job_b],
                available_windows=[win_a, win_b],
                candidate_matches=matches,
            )
        )

        # Overlapping times on the same location: at most one can be scheduled!
        assert result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(result.scheduled_blocks) == 1
        assert len(result.unscheduled_blocks) == 1
        # The higher-priority job (JOB-A: 90 vs 50) is chosen
        assert result.scheduled_blocks[0].request_id == "JOB-A"

    def test_adjacent_possessions_are_permitted(self, base_date: date):
        """Job A: 10:00-12:00, Job B: 12:00-14:00 on same section -> both can be scheduled."""
        req_a = MaintenanceRecord(
            asset_id="JOB-ADJ-A",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            priority_value=80.0,
            duration_minutes=120,
            requested_date=base_date,
            preferred_start=time(10, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.APPROVED,
        )
        req_b = MaintenanceRecord(
            asset_id="JOB-ADJ-B",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            priority_value=75.0,
            duration_minutes=120,
            requested_date=base_date,
            preferred_start=time(12, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.APPROVED,
        )
        optimizer = CP_SAT_Optimizer(maintenance_records=[req_a, req_b])
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                pinned_slots={"JOB-ADJ-A": "10:00-12:00", "JOB-ADJ-B": "12:00-14:00"},
            )
        )

        # Non-overlapping adjacency allows both to be scheduled
        assert len(result.scheduled_blocks) == 2
        sched_ids = {b.request_id for b in result.scheduled_blocks}
        assert sched_ids == {"JOB-ADJ-A", "JOB-ADJ-B"}


# ===========================================================================
# TEST 5 & 6: Safety Buffers and Train Movement Conflicts
# ===========================================================================
class TestSafetyBuffersAndTrainConflicts:
    """TEST 5 & 6: Safety buffers and train movement conflict enforcement."""

    def test_safety_buffer_headway_violation_rejected(self, base_date: date):
        """Maintenance 10:00-11:00 vs Train movement at 11:15 with 30m safety buffer must not be scheduled."""
        movement = MovementRecord(
            train_id="TR-101",
            route_id="R-CHN-AJJ",
            section="Chennai-Arakkonam",
            direction="Up",
            movement_status="Occupied",
            entry_time="11:15",
            exit_time="11:30",
            line="Main",
        )
        req = MaintenanceRecord(
            asset_id="MAINT-BUF-TEST",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=60,
            requested_date=base_date,
            preferred_start=time(10, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.APPROVED,
        )
        # With 30 min buffer: Train enters at 11:15, so occupied from 10:45 to 12:00.
        # A 10:00-11:00 maintenance block violates the 30-min buffer headway (11:00 to 11:15 is only 15 mins).
        optimizer = CP_SAT_Optimizer(maintenance_records=[req], movements=[movement])
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                buffer_minutes=30,
            )
        )

        if result.scheduled_blocks:
            blk = result.scheduled_blocks[0]
            # Must NOT be scheduled during 10:00-11:00 due to buffer violation
            assert not (blk.start_time == "10:00" and blk.end_time == "11:00")
            # End time must maintain at least 30 min buffer before 11:15 (i.e. <= 10:45)
            assert blk.end_time <= "10:45" or blk.start_time >= "12:00"

    def test_maintenance_with_safe_separation_is_scheduled(self, base_date: date):
        """Maintenance 01:00-03:00 with train movement at 06:00 is completely safe."""
        movement = MovementRecord(
            train_id="TR-202",
            route_id="R-CHN-AJJ",
            section="Chennai-Arakkonam",
            direction="Up",
            movement_status="Occupied",
            entry_time="06:00",
            exit_time="06:30",
            line="Main",
        )
        req = MaintenanceRecord(
            asset_id="MAINT-SAFE-WIN",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            priority_value=85.0,
            duration_minutes=120,
            requested_date=base_date,
            preferred_start=time(1, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.APPROVED,
        )
        optimizer = CP_SAT_Optimizer(maintenance_records=[req], movements=[movement])
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                buffer_minutes=15,
            )
        )

        assert len(result.scheduled_blocks) == 1
        blk = result.scheduled_blocks[0]
        assert blk.request_id == "MAINT-SAFE-WIN"
        assert blk.start_time == "01:00"
        assert blk.end_time == "03:00"


# ===========================================================================
# TEST 7: Resource Constraints
# ===========================================================================
class TestResourceConstraints:
    """TEST 7: Specialized equipment with limited capacity cannot be overallocated."""

    def test_equipment_capacity_contention(self, base_date: date):
        """Track Tamper capacity=1: Job A (10:00-12:00) and Job B (11:00-13:00) cannot both be scheduled."""
        job_a = CandidateWorkItem(
            work_id="REQ-TAMPER-A",
            location="Chennai-Arakkonam",
            required_duration_minutes=120,
            priority_value=90.0,
            priority=Priority.HIGH,
            equipment="Track Tamper",
        )
        # Job B on DIFFERENT location, so track mutual exclusion does not apply; ONLY equipment capacity limits it
        job_b = CandidateWorkItem(
            work_id="REQ-TAMPER-B",
            location="Tambaram-Chengalpattu",
            required_duration_minutes=120,
            priority_value=40.0,
            priority=Priority.MEDIUM,
            equipment="Track Tamper",
        )
        win_a = CorridorAvailabilityWindow(
            window_id="WIN-TAMP-A",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="10:00",
            end_time="12:00",
            duration_minutes=120,
        )
        win_b = CorridorAvailabilityWindow(
            window_id="WIN-TAMP-B",
            corridor="Tambaram-Chengalpattu",
            service_date=base_date,
            start_time="11:00",
            end_time="13:00",
            duration_minutes=120,
        )
        matches = [
            WorkBlockMatch(match_id="M-TA", work_id="REQ-TAMPER-A", window_id="WIN-TAMP-A", is_compatible=True),
            WorkBlockMatch(match_id="M-TB", work_id="REQ-TAMPER-B", window_id="WIN-TAMP-B", is_compatible=True),
        ]
        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[job_a, job_b],
                available_windows=[win_a, win_b],
                candidate_matches=matches,
                custom_capacities={"Track Tamper": 1},
            )
        )

        # Capacity 1 -> cannot both be assigned simultaneously
        assert result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(result.scheduled_blocks) == 1
        assert result.scheduled_blocks[0].request_id == "REQ-TAMPER-A"

    def test_equipment_adjacent_usage_permitted(self, base_date: date):
        """Track Tamper capacity=1: Job A (10:00-12:00) and Job B (12:00-14:00) are sequentially feasible."""
        job_a = CandidateWorkItem(
            work_id="REQ-SEQ-A",
            location="Chennai-Arakkonam",
            required_duration_minutes=120,
            priority_value=85.0,
            priority=Priority.HIGH,
            equipment="Track Tamper",
        )
        job_b = CandidateWorkItem(
            work_id="REQ-SEQ-B",
            location="Tambaram-Chengalpattu",
            required_duration_minutes=120,
            priority_value=75.0,
            priority=Priority.MEDIUM,
            equipment="Track Tamper",
        )
        win_a = CorridorAvailabilityWindow(
            window_id="WIN-SEQ-A",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="10:00",
            end_time="12:00",
            duration_minutes=120,
        )
        win_b = CorridorAvailabilityWindow(
            window_id="WIN-SEQ-B",
            corridor="Tambaram-Chengalpattu",
            service_date=base_date,
            start_time="12:00",
            end_time="14:00",
            duration_minutes=120,
        )
        matches = [
            WorkBlockMatch(match_id="M-SA", work_id="REQ-SEQ-A", window_id="WIN-SEQ-A", is_compatible=True),
            WorkBlockMatch(match_id="M-SB", work_id="REQ-SEQ-B", window_id="WIN-SEQ-B", is_compatible=True),
        ]
        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[job_a, job_b],
                available_windows=[win_a, win_b],
                candidate_matches=matches,
                custom_capacities={"Track Tamper": 1},
            )
        )

        assert result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(result.scheduled_blocks) == 2


# ===========================================================================
# TEST 8, 9, 10 & IMPORTANT PRIORITY TEST
# ===========================================================================
class TestPriorityObjectiveAndFeasibility:
    """TEST 8, 9, 10 and IMPORTANT PRIORITY TEST: Priority influence and hard constraint precedence."""

    def test_important_priority_test_competition_and_infeasibility(self, base_date: date):
        """
        IMPORTANT PRIORITY TEST:
        Scenario 1:
          JOB A: priority_value = 95, duration = 60 min, feasible slots = 2
          JOB B: priority_value = 40, duration = 60 min, feasible slots = 2
          Both compete for the same constrained resource/window -> higher priority_value wins.
        Scenario 2:
          JOB A: priority_value = 95, NO feasible slots
          JOB B: priority_value = 40, feasible slot exists
          -> JOB B is scheduled. Priority does not override feasibility.
        """
        # SCENARIO 1: Both feasible and competing for a single capacity-1 window
        job_a = CandidateWorkItem(
            work_id="JOB-A",
            location="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority_value=95.0,
            priority=Priority.CRITICAL,
        )
        job_b = CandidateWorkItem(
            work_id="JOB-B",
            location="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority_value=40.0,
            priority=Priority.MEDIUM,
        )
        # Windows: 2 candidate slots on the same corridor
        win1 = CorridorAvailabilityWindow(window_id="WIN-1", corridor="Chennai-Arakkonam", service_date=base_date, start_time="01:00", end_time="02:00", duration_minutes=60)
        win2 = CorridorAvailabilityWindow(window_id="WIN-2", corridor="Chennai-Arakkonam", service_date=base_date, start_time="01:00", end_time="02:00", duration_minutes=60)
        # Both jobs match with both windows (2 feasible slots each)
        matches = [
            WorkBlockMatch(match_id="M-A1", work_id="JOB-A", window_id="WIN-1", is_compatible=True),
            WorkBlockMatch(match_id="M-A2", work_id="JOB-A", window_id="WIN-2", is_compatible=True),
            WorkBlockMatch(match_id="M-B1", work_id="JOB-B", window_id="WIN-1", is_compatible=True),
            WorkBlockMatch(match_id="M-B2", work_id="JOB-B", window_id="WIN-2", is_compatible=True),
        ]

        optimizer1 = CP_SAT_Optimizer()
        res1 = optimizer1.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[job_a, job_b],
                available_windows=[win1, win2],
                candidate_matches=matches,
            )
        )
        # At 01:00-02:00 on Chennai-Arakkonam, non-overlapping track constraint limits to 1 possession.
        # Job A (priority_value=95) MUST be chosen over Job B (priority_value=40)
        assert len(res1.scheduled_blocks) == 1
        assert res1.scheduled_blocks[0].request_id == "JOB-A"

        # SCENARIO 2: Job A has NO feasible slots (e.g. 0 matches); Job B has a feasible slot
        matches_scen2 = [
            WorkBlockMatch(match_id="M-B1", work_id="JOB-B", window_id="WIN-1", is_compatible=True),
        ]
        optimizer2 = CP_SAT_Optimizer()
        res2 = optimizer2.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[job_a, job_b],
                available_windows=[win1],
                candidate_matches=matches_scen2,
            )
        )

        # Hard constraints dominate: Job B gets scheduled even though priority_value 40 < 95
        assert len(res2.scheduled_blocks) == 1
        assert res2.scheduled_blocks[0].request_id == "JOB-B"
        assert len(res2.unscheduled_blocks) == 1
        assert res2.unscheduled_blocks[0].request_id == "JOB-A"


# ===========================================================================
# TEST 11 & 12: All Requests Feasible vs No Requests Feasible
# ===========================================================================
class TestFeasibilityExtremes:
    """TEST 11 & 12: All feasible and no feasible requests handling."""

    def test_all_requests_feasible(self, base_date: date):
        """TEST 11: All candidate requests can be scheduled into distinct conflict-free slots."""
        works = [
            CandidateWorkItem(work_id="W-1", location="Corridor-1", required_duration_minutes=60, priority_value=90.0),
            CandidateWorkItem(work_id="W-2", location="Corridor-2", required_duration_minutes=60, priority_value=80.0),
            CandidateWorkItem(work_id="W-3", location="Corridor-3", required_duration_minutes=60, priority_value=70.0),
        ]
        windows = [
            CorridorAvailabilityWindow(window_id="WIN-1", corridor="Corridor-1", service_date=base_date, start_time="01:00", end_time="03:00", duration_minutes=120),
            CorridorAvailabilityWindow(window_id="WIN-2", corridor="Corridor-2", service_date=base_date, start_time="01:00", end_time="03:00", duration_minutes=120),
            CorridorAvailabilityWindow(window_id="WIN-3", corridor="Corridor-3", service_date=base_date, start_time="01:00", end_time="03:00", duration_minutes=120),
        ]
        matches = [
            WorkBlockMatch(match_id="M-1", work_id="W-1", window_id="WIN-1", is_compatible=True),
            WorkBlockMatch(match_id="M-2", work_id="W-2", window_id="WIN-2", is_compatible=True),
            WorkBlockMatch(match_id="M-3", work_id="W-3", window_id="WIN-3", is_compatible=True),
        ]

        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=works,
                available_windows=windows,
                candidate_matches=matches,
            )
        )

        assert result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(result.scheduled_blocks) == 3
        assert len(result.unscheduled_blocks) == 0

    def test_no_requests_feasible_status_semantics(self, base_date: date):
        """TEST 12: 0 scheduled jobs is NOT automatically INFEASIBLE; solver status is OPTIMAL with 0 scheduled."""
        works = [
            CandidateWorkItem(work_id="W-UNFEAS-1", location="Corridor-1", required_duration_minutes=240, priority_value=90.0),
        ]
        # Only a 60-min window available; cannot fit 240m job
        windows = [
            CorridorAvailabilityWindow(window_id="WIN-TINY", corridor="Corridor-1", service_date=base_date, start_time="01:00", end_time="02:00", duration_minutes=60),
        ]
        matches = [
            WorkBlockMatch(match_id="M-TINY", work_id="W-UNFEAS-1", window_id="WIN-TINY", is_compatible=True),
        ]

        optimizer = CP_SAT_Optimizer()
        result = optimizer.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=works,
                available_windows=windows,
                candidate_matches=matches,
            )
        )

        # Status must be OPTIMAL (the mathematical problem of maximizing with 0 feasible slots is solved to optimality)
        assert result.status == OptimizationStatus.OPTIMAL
        assert len(result.scheduled_blocks) == 0
        assert len(result.unscheduled_blocks) == 1
        assert "NO_FEASIBLE_WINDOW" in result.unscheduled_blocks[0].reason


# ===========================================================================
# TEST 13 & 14: Conflict Detection and Objective Balance
# ===========================================================================
class TestConflictDetectionAndObjectiveBalance:
    """TEST 13 & 14: Verification with existing ConflictDetector and Objective balance terms."""

    def test_optimized_plan_passes_independent_conflict_validation(self, base_date: date):
        """TEST 13: validate_final_plan certifies the optimized schedule with 0 operational conflicts."""
        req = MaintenanceRecord(
            asset_id="TRK-VAL-01",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            priority_value=85.0,
            duration_minutes=120,
            requested_date=base_date,
            preferred_start=time(2, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.APPROVED,
        )
        optimizer = CP_SAT_Optimizer(maintenance_records=[req])
        result = optimizer.optimize(OptimizationRequest(target_date=base_date, horizon_days=1))

        assert result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        validation = validate_final_plan(result)
        assert validation["is_valid"] is True
        assert validation["conflicts"] == 0
        assert validation["duplicate_ids"] == 0

    def test_objective_balance_with_utilization_and_efficiency(self):
        """TEST 14: Objective accounts for priority_value, block utilization, and operational efficiency."""
        weights = ObjectiveWeights(
            weight_scheduled=10000,
            weight_priority_value=50,
            weight_block_utilization=10,
            weight_operational_efficiency=20,
        )
        meta = {
            "priority_value": 90.0,
            "duration_minutes": 120,
            "fit_score": 0.95,
            "start_minutes": 120,
            "preferred_start_minutes": 120,
        }
        coeff = compute_slot_coefficient(meta, weights)
        # Base: 10000
        # Priority: 50 * 90 = 4500
        # Deviation: 0
        # Disruption: (50 * round(0.05 * 100)) // 10 = (50 * 5) // 10 = 25
        # Utilization: 10 * 120 = 1200
        # Efficiency: (20 * round(0.95 * 100)) // 10 = (20 * 95) // 10 = 190
        # Total = 10000 + 4500 - 25 + 1200 + 190 = 15865
        assert coeff == 15865
        assert meta["priority_contribution"] == 4500
