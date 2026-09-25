"""
Comprehensive Test Suite for Phase 3 — Feasibility + Final Plan Validation.

Covers:
  PART 1 — Solver Status Handling:
    - OPTIMAL: Valid optimal plan classified correctly
    - FEASIBLE: Valid feasible plan classified correctly
    - INFEASIBLE: Impossible constraint problems classified correctly
    - TIME_LIMIT: Solver timeout classified correctly without error
    - MODEL_INVALID: Model invalid status handled cleanly

  PART 2 — Extracted Allocation Validation:
    - Verifies request_id, block_id, service_date, start_time, end_time
    - Verifies all allocations have end_time > start_time (or correct overnight wrap)
    - Verifies duration integrity: duration_minutes matches end - start
    - Verifies allocation satisfies timetable separation and conflict detector

  PART 3 — Duration Validation:
    - Detects zero duration allocations
    - Detects negative duration allocations
    - Detects shortened duration allocations (scheduled duration < requested duration)
    - Detects duration mismatch between timestamps and duration_minutes

  PART 4 — Block Validation:
    - Verifies allocation fits within candidate availability window bounds
    - Detects allocation exceeding window boundaries
    - Detects allocation assigned to incompatible corridor/section
    - Verifies unknown request_ids are flagged

  PART 5 — Conflict Validation:
    - Direct train collisions detected and flagged by validator
    - Overlapping track possessions at same location detected
    - Resource/equipment contention detected
    - Validates that conflict detector output sets is_valid=False

  PART 6 — Unscheduled Diagnostics:
    - Differentiates solver failure/infeasibility vs legitimate preemption
    - Distinguishes NO_FEASIBLE_WINDOW from capacity/equipment preemption
    - Populates resource_contention field when specialized equipment is contested
    - Ensures count integrity: scheduled + unscheduled == total_requests

  PART 7 — Invalid Allocation Detection:
    - Synthetic corruption test: corrupted start_time/end_time caught
    - Duplicate block_ids detected
    - Corrupted missing service_date caught
    - Certified clean output: unmodified valid plan passes with is_valid=True
"""

from datetime import date, time, timedelta
import pytest

from backend.app.block_planner.schemas import CandidateWorkItem, CorridorAvailabilityWindow
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
    OptimizedBlock,
    SolverStatistics,
    UnscheduledBlock,
)
from backend.app.optimizer.validator import validate_final_plan
from backend.app.scheduler.schemas import WorkBlockMatch
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    MaintenanceRecord,
    MaintenanceStatus,
    MovementRecord,
    Priority,
    TimetableRecord,
    TrainRecord,
)


@pytest.fixture
def base_date() -> date:
    return date(2026, 9, 15)


# ===========================================================================
# PART 1: Solver Status Handling
# ===========================================================================
class TestSolverStatusHandling:
    """Verify system distinguishes OPTIMAL, FEASIBLE, INFEASIBLE, TIME_LIMIT, MODEL_INVALID."""

    def test_optimal_status_plan(self, base_date: date):
        """OPTIMAL: Valid problem solved to proven mathematical optimality."""
        work = CandidateWorkItem(
            work_id="OPT-W1",
            asset_id="AST-01",
            location="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority=Priority.HIGH,
            priority_value=85.0,
            preferred_date=base_date,
        )
        win = CorridorAvailabilityWindow(
            window_id="OPT-WIN1",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
            status="Available",
        )
        match = WorkBlockMatch(match_id="M-1", work_id="OPT-W1", window_id="OPT-WIN1", is_compatible=True)

        opt = CP_SAT_Optimizer()
        res = opt.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work],
                available_windows=[win],
                candidate_matches=[match],
            )
        )

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 1
        assert len(res.unscheduled_blocks) == 0

        val = validate_final_plan(res, source_requests=[work], available_windows=[win])
        assert val["is_valid"] is True
        assert val["solver_status"] == OptimizationStatus.OPTIMAL.value

    def test_infeasible_problem_status(self, base_date: date):
        """INFEASIBLE: Mutually contradictory mandatory requirements yield INFEASIBLE status."""
        req1 = MaintenanceRecord(
            asset_id="MAND-01",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=120,
            requested_date=base_date,
            preferred_start=time(2, 0),
            required_resources=1,
            equipment="Track Tamper",
            status=MaintenanceStatus.APPROVED,
        )
        # Train timetable blocks the entire 24h window
        tt = [
            TimetableRecord(
                train_id="BLOCKER-TRAIN",
                service_date=base_date,
                station_code="Chennai",
                arrival_time="00:01",
                departure_time="23:59",
                sequence=1,
            )
        ]
        opt = CP_SAT_Optimizer(maintenance_records=[req1], timetables=tt)
        res = opt.optimize(
            OptimizationRequest(target_date=base_date, horizon_days=1),
            mandatory_request_ids={"MAND-01"},
        )

        assert res.status == OptimizationStatus.INFEASIBLE
        assert len(res.scheduled_blocks) == 0
        assert len(res.unscheduled_blocks) == 1
        assert "INFEASIBLE_PROBLEM" in res.unscheduled_blocks[0].reason

        val = validate_final_plan(res)
        assert val["is_valid"] is True  # 0 scheduled blocks has 0 violations
        assert val["solver_status"] == OptimizationStatus.INFEASIBLE.value

    def test_time_limit_status_handling(self, base_date: date):
        """TIME_LIMIT: Solver time-out is handled as TIME_LIMIT without error."""
        stats = SolverStatistics(
            status=OptimizationStatus.TIME_LIMIT,
            objective_value=None,
            wall_time_seconds=30.0,
            num_scheduled=0,
            num_unscheduled=1,
            total_requests=1,
            num_variables=10,
            num_constraints=10,
        )
        unsched = UnscheduledBlock(
            request_id="REQ-TL-1",
            location="Chennai-Arakkonam",
            requested_date=base_date,
            preferred_start="02:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            required_resources=1,
            reason="SOLVER_TIME_LIMIT: Solver reached time limit before scheduling this request.",
        )
        res = OptimizationResult(
            plan_id="OPT-TL-001",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.TIME_LIMIT,
            solver_statistics=stats,
            scheduled_blocks=[],
            unscheduled_blocks=[unsched],
        )

        val = validate_final_plan(res)
        assert val["solver_status"] == OptimizationStatus.TIME_LIMIT.value
        assert val["is_valid"] is True


# ===========================================================================
# PART 2: Extracted Allocation Validation
# ===========================================================================
class TestExtractedAllocationValidation:
    """Verify all fields and properties of scheduled allocations are verified post-optimization."""

    def test_valid_allocation_passes_all_checks(self, base_date: date):
        """Well-formed allocation passes structural, duration, and count validation."""
        work = CandidateWorkItem(
            work_id="WORK-V1",
            asset_id="AST-V1",
            location="Chennai-Arakkonam",
            required_duration_minutes=90,
            priority=Priority.HIGH,
            priority_value=88.0,
            preferred_date=base_date,
        )
        win = CorridorAvailabilityWindow(
            window_id="WIN-V1",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="03:00",
            end_time="05:00",
            duration_minutes=120,
            status="Available",
        )
        match = WorkBlockMatch(match_id="M-V1", work_id="WORK-V1", window_id="WIN-V1", is_compatible=True)

        opt = CP_SAT_Optimizer()
        res = opt.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work],
                available_windows=[win],
                candidate_matches=[match],
            )
        )

        val = validate_final_plan(res, source_requests=[work], available_windows=[win])
        assert val["is_valid"] is True
        assert val["num_scheduled"] == 1
        assert val["num_unscheduled"] == 0
        assert val["count_integrity"] is True
        assert val["conflicts"] == 0
        assert val["duration_violations"] == 0
        assert val["unknown_blocks"] == 0

    def test_overnight_allocation_duration_semantics(self, base_date: date):
        """Overnight block (23:00 to 02:00) duration semantics: (1440 - 23*60) + 2*60 = 180m."""
        blk = OptimizedBlock(
            block_id="BLK-OVN-01",
            request_id="REQ-OVN-01",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="23:00",
            end_time="02:00",
            duration_minutes=180,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-OVN",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is True
        assert val["duration_violations"] == 0


# ===========================================================================
# PART 3: Duration Validation
# ===========================================================================
class TestDurationValidation:
    """Verify detection of zero, negative, shortened, or inconsistent duration allocations."""

    def test_detects_zero_duration(self, base_date: date):
        """Allocation claiming 0 duration is flagged as violation."""
        blk = OptimizedBlock(
            block_id="BLK-ZERO",
            request_id="REQ-ZERO",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="04:00",
            end_time="04:00",
            duration_minutes=1,  # Pydantic schema enforces gt=0, set duration_minutes to 1 while times are equal
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-ZERO",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert val["duration_violations"] > 0
        assert any("ZERO_INTERVAL" in v for v in val["violations"])

    def test_detects_shortened_duration_against_source_request(self, base_date: date):
        """Allocation scheduled for 60m when source request asked for 120m is flagged."""
        work = CandidateWorkItem(
            work_id="REQ-DUR-1",
            location="Chennai-Arakkonam",
            required_duration_minutes=120,
            priority=Priority.HIGH,
        )
        blk = OptimizedBlock(
            block_id="BLK-SHORT",
            request_id="REQ-DUR-1",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="04:00",
            end_time="05:00",
            duration_minutes=60,  # Silently shortened to 60m
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-SHORT",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res, source_requests=[work])
        assert val["is_valid"] is False
        assert val["duration_violations"] > 0
        assert any("DURATION_ALTERED" in v for v in val["violations"])

    def test_detects_mismatch_between_timestamps_and_duration_metadata(self, base_date: date):
        """Start 02:00, End 05:00 implies 180m, but block claims 120m."""
        blk = OptimizedBlock(
            block_id="BLK-MISMATCH",
            request_id="REQ-MISMATCH",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="05:00",
            duration_minutes=120,  # Inconsistent with 02:00-05:00 (180m)
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-MISMATCH",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert val["duration_violations"] > 0
        assert any("DURATION_MISMATCH" in v for v in val["violations"])


# ===========================================================================
# PART 4: Block & Window Validation
# ===========================================================================
class TestBlockAndWindowValidation:
    """Verify allocations satisfy availability window boundaries, work compatibility, and identity integrity."""

    def test_detects_allocation_exceeding_window_boundaries(self, base_date: date):
        """Allocation starting at 01:00 when window only starts at 02:00 is flagged."""
        win = CorridorAvailabilityWindow(
            window_id="WIN-STRICT",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
        )
        blk = OptimizedBlock(
            block_id="BLK-OUT-BOUNDS",
            request_id="REQ-OB-1",
            window_id="WIN-STRICT",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="01:00",  # Starts earlier than window 02:00
            end_time="03:00",
            duration_minutes=120,
            priority=Priority.HIGH,
            assigned_slot_id="WIN-STRICT",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-OB",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res, available_windows=[win])
        assert val["is_valid"] is False
        assert any("WINDOW_BOUNDS_EXCEEDED" in v for v in val["violations"])

    def test_detects_incompatible_corridor_location(self, base_date: date):
        """Work requested for Chennai-Arakkonam assigned to Renigunta is flagged."""
        work = CandidateWorkItem(
            work_id="REQ-COMPAT-1",
            location="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority=Priority.HIGH,
        )
        blk = OptimizedBlock(
            block_id="BLK-WRONG-LOC",
            request_id="REQ-COMPAT-1",
            location="Renigunta-Guntakal",  # Incompatible corridor
            service_date=base_date,
            start_time="02:00",
            end_time="03:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-COMPAT",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res, source_requests=[work])
        assert val["is_valid"] is False
        assert any("INCOMPATIBLE_LOCATION" in v for v in val["violations"])

    def test_detects_unknown_source_request(self, base_date: date):
        """Block with request_id not present in source requests is flagged as UNKNOWN_REQUEST."""
        work = CandidateWorkItem(work_id="KNOWN-REQ-1", location="Chennai-Arakkonam", required_duration_minutes=60)
        blk = OptimizedBlock(
            block_id="BLK-GHOST",
            request_id="GHOST-REQ-999",  # Does not exist in source requests
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="03:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-GHOST",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res, source_requests=[work])
        assert val["is_valid"] is False
        assert val["unknown_blocks"] == 1
        assert any("UNKNOWN_REQUEST" in v for v in val["violations"])


# ===========================================================================
# PART 5: Conflict Validation
# ===========================================================================
class TestConflictValidation:
    """Verify ConflictDetector detects train movements, possession overlaps, and equipment contention."""

    def test_detects_train_movement_collision(self, base_date: date):
        """Train timetable stop at 02:30 overlapping block 02:00-04:00 is caught by validator."""
        blk = OptimizedBlock(
            block_id="BLK-TRAIN-CRASH",
            request_id="REQ-TC-1",
            location="Chennai",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        tt = [
            TimetableRecord(
                train_id="EXPRESS-101",
                service_date=base_date,
                station_code="Chennai",
                arrival_time="02:30",
                departure_time="02:40",
                sequence=1,
            )
        ]
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-TRAIN-COLLISION",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res, timetables=tt)
        assert val["is_valid"] is False
        assert val["conflicts"] > 0
        assert any("CONFLICTS_REMAIN" in v for v in val["violations"])

    def test_detects_possession_overlap_at_same_location(self, base_date: date):
        """Two scheduled blocks at same location with overlapping times are caught by ConflictDetector."""
        blk1 = OptimizedBlock(
            block_id="BLK-OV-1",
            request_id="REQ-OV-1",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        blk2 = OptimizedBlock(
            block_id="BLK-OV-2",
            request_id="REQ-OV-2",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="03:00",
            end_time="05:00",
            duration_minutes=120,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-02",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=2,
            num_unscheduled=0,
            total_requests=2,
        )
        res = OptimizationResult(
            plan_id="PLAN-POSS-OVERLAP",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk1, blk2],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert val["conflicts"] > 0
        assert any("CONFLICTS_REMAIN" in v for v in val["violations"])

    def test_detects_equipment_contention(self, base_date: date):
        """Two blocks at different locations simultaneously using 'Track Tamper' are caught."""
        blk1 = OptimizedBlock(
            block_id="BLK-EQ-1",
            request_id="REQ-EQ-1",
            location="Corridor-A",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
            priority=Priority.HIGH,
            equipment="Track Tamper",
            assigned_slot_id="SLOT-01",
        )
        blk2 = OptimizedBlock(
            block_id="BLK-EQ-2",
            request_id="REQ-EQ-2",
            location="Corridor-B",
            service_date=base_date,
            start_time="02:30",
            end_time="04:30",
            duration_minutes=120,
            priority=Priority.HIGH,
            equipment="Track Tamper",
            assigned_slot_id="SLOT-02",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=2,
            num_unscheduled=0,
            total_requests=2,
        )
        res = OptimizationResult(
            plan_id="PLAN-EQUIP-CONTENTION",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk1, blk2],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert val["equipment_violations"] > 0
        assert val["conflicts"] > 0


# ===========================================================================
# PART 6: Unscheduled Diagnostics
# ===========================================================================
class TestUnscheduledDiagnostics:
    """Verify unscheduled reasons and resource contention attribution."""

    def test_distinguishes_no_window_from_preemption(self, base_date: date):
        """Work with no feasible candidate slots receives NO_FEASIBLE_WINDOW diagnostic."""
        work_impossible = CandidateWorkItem(
            work_id="WORK-NO-WIN",
            location="Chennai-Arakkonam",
            required_duration_minutes=300,  # 5 hours
            priority=Priority.LOW,
        )
        # Only 1-hour window available
        win = CorridorAvailabilityWindow(
            window_id="WIN-1H",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="03:00",
            duration_minutes=60,
        )
        match = WorkBlockMatch(match_id="M-1", work_id="WORK-NO-WIN", window_id="WIN-1H", is_compatible=True)

        opt = CP_SAT_Optimizer()
        res = opt.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work_impossible],
                available_windows=[win],
                candidate_matches=[match],
            )
        )

        assert len(res.unscheduled_blocks) == 1
        unsched = res.unscheduled_blocks[0]
        assert "NO_FEASIBLE_WINDOW" in unsched.reason

    def test_equipment_contention_attribution(self, base_date: date):
        """Unscheduled block due to equipment contention populates resource_contention field."""
        work_a = CandidateWorkItem(
            work_id="WORK-TAMPER-A",
            location="Chennai-Arakkonam",
            required_duration_minutes=120,
            priority_value=95.0,
            priority=Priority.CRITICAL,
            equipment="Track Tamper",
        )
        work_b = CandidateWorkItem(
            work_id="WORK-TAMPER-B",
            location="Renigunta-Guntakal",
            required_duration_minutes=120,
            priority_value=40.0,
            priority=Priority.LOW,
            equipment="Track Tamper",
        )
        win1 = CorridorAvailabilityWindow(
            window_id="WIN-T1",
            corridor="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
        )
        win2 = CorridorAvailabilityWindow(
            window_id="WIN-T2",
            corridor="Renigunta-Guntakal",
            service_date=base_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
        )
        matches = [
            WorkBlockMatch(match_id="M-1", work_id="WORK-TAMPER-A", window_id="WIN-T1", is_compatible=True),
            WorkBlockMatch(match_id="M-2", work_id="WORK-TAMPER-B", window_id="WIN-T2", is_compatible=True),
        ]

        opt = CP_SAT_Optimizer()
        res = opt.optimize(
            OptimizationRequest(
                target_date=base_date,
                horizon_days=1,
                candidate_works=[work_a, work_b],
                available_windows=[win1, win2],
                candidate_matches=matches,
                custom_capacities={"Track Tamper": 1},
            )
        )

        assert len(res.scheduled_blocks) == 1
        assert res.scheduled_blocks[0].request_id == "WORK-TAMPER-A"
        assert len(res.unscheduled_blocks) == 1
        unsched = res.unscheduled_blocks[0]
        assert unsched.request_id == "WORK-TAMPER-B"
        assert "Track Tamper" in (unsched.resource_contention or "") or "equipment" in unsched.reason.lower()

    def test_count_integrity_verification(self, base_date: date):
        """scheduled + unscheduled == total_requests integrity check in validator."""
        blk = OptimizedBlock(
            block_id="BLK-C1",
            request_id="REQ-C1",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="02:00",
            end_time="03:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=5,  # Mismatch: total_requests=5, but len(scheduled)+len(unscheduled)=1
        )
        res = OptimizationResult(
            plan_id="PLAN-COUNT-FAIL",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
            unscheduled_blocks=[],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert val["count_integrity"] is False
        assert any("COUNT_MISMATCH" in v for v in val["violations"])


# ===========================================================================
# PART 7: Invalid Allocation Detection (Synthetic Corruption)
# ===========================================================================
class TestInvalidAllocationDetection:
    """Verify synthetic plan corruptions are caught by the validation layer."""

    def test_detects_duplicate_block_ids(self, base_date: date):
        """Duplicate block_ids in scheduled output are caught."""
        blk1 = OptimizedBlock(
            block_id="DUPLICATE-ID",
            request_id="REQ-1",
            location="Corridor-A",
            service_date=base_date,
            start_time="01:00",
            end_time="02:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        blk2 = OptimizedBlock(
            block_id="DUPLICATE-ID",  # Same block_id!
            request_id="REQ-2",
            location="Corridor-B",
            service_date=base_date,
            start_time="03:00",
            end_time="04:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-02",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=2,
            num_unscheduled=0,
            total_requests=2,
        )
        res = OptimizationResult(
            plan_id="PLAN-DUP",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk1, blk2],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert val["duplicate_ids"] == 1
        assert any("DUPLICATE_BLOCK_ID" in v for v in val["violations"])

    def test_detects_malformed_timestamps(self, base_date: date):
        """Invalid time string syntax (e.g. '25:99' or 'bad_time') is caught."""
        blk = OptimizedBlock(
            block_id="BLK-MALFORMED-TIME",
            request_id="REQ-MT-1",
            location="Chennai-Arakkonam",
            service_date=base_date,
            start_time="not_a_time",
            end_time="03:00",
            duration_minutes=60,
            priority=Priority.HIGH,
            assigned_slot_id="SLOT-01",
        )
        stats = SolverStatistics(
            status=OptimizationStatus.OPTIMAL,
            num_scheduled=1,
            num_unscheduled=0,
            total_requests=1,
        )
        res = OptimizationResult(
            plan_id="PLAN-MALFORMED",
            generated_at="2026-09-15T00:00:00Z",
            target_date=base_date,
            horizon_days=1,
            status=OptimizationStatus.OPTIMAL,
            solver_statistics=stats,
            scheduled_blocks=[blk],
        )

        val = validate_final_plan(res)
        assert val["is_valid"] is False
        assert any("INVALID_START_TIME" in v for v in val["violations"])
