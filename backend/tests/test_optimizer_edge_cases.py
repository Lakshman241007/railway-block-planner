"""
Comprehensive Phase 4 Edge-Case Test Matrix for Railway Block Planner.

Validates the full matrix of 20 edge cases:
1. Zero block requests
2. One block request
3. Multiple non-overlapping blocks
4. Multiple overlapping blocks
5. Same priority conflict
6. Different priority conflict
7. Overnight block
8. Adjacent intervals
9. Impossible block
10. Maintenance conflict
11. Train movement conflict
12. Headway conflict
13. Multi-day scheduling
14. No feasible solution
15. Solver time limit
16. Missing forecast
17. Low-confidence forecast
18. Empty timetable
19. Empty movements
20. Repeated identical optimization input (Determinism)
"""

from __future__ import annotations

from datetime import date, time, timedelta
import pytest

from backend.app.forecast.schemas import ForecastConfidenceLevel, GoodsForecastItem
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationStatus,
)
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.scheduler.scheduler import MaintenanceScheduler
from backend.app.scheduler.schemas import ConflictSeverity, ConflictType
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
def target_d() -> date:
    return date(2026, 9, 7)


class TestEdgeCaseMatrix:
    """Explicit test cases for each of the 20 Phase 4 edge cases."""

    # 1. Zero block requests
    def test_01_zero_block_requests(self, target_d: date):
        opt = CP_SAT_Optimizer()
        req = OptimizationRequest(target_date=target_d, horizon_days=1)
        res = opt.optimize(req)

        assert res.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE)
        assert len(res.scheduled_blocks) == 0
        assert len(res.unscheduled_blocks) == 0
        assert res.solver_statistics.total_requests == 0
        assert res.solver_statistics.num_conflicts_avoided == 0

    # 2. One block request
    def test_02_one_block_request(self, target_d: date):
        b = BlockRecord(
            block_id="BLK-SINGLE",
            location="Chennai-Arakkonam",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="02:00",
            requested_end="04:00",
            reason="Night maintenance",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        opt = CP_SAT_Optimizer(block_records=[b])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 1
        assert len(res.unscheduled_blocks) == 0
        assert res.scheduled_blocks[0].request_id == "BLK-SINGLE"
        assert res.scheduled_blocks[0].duration_minutes == 120

    # 3. Multiple non-overlapping blocks
    def test_03_multiple_non_overlapping_blocks(self, target_d: date):
        b1 = BlockRecord(
            block_id="BLK-EARLY",
            location="Chennai-Arakkonam",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="01:00",
            requested_end="03:00",
            reason="Early",
            priority=Priority.MEDIUM,
            status=BlockStatus.REQUESTED,
        )
        b2 = BlockRecord(
            block_id="BLK-LATE",
            location="Chennai-Arakkonam",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="04:00",
            requested_end="06:00",
            reason="Late",
            priority=Priority.MEDIUM,
            status=BlockStatus.REQUESTED,
        )
        opt = CP_SAT_Optimizer(block_records=[b1, b2])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 2
        assert len(res.unscheduled_blocks) == 0

    # 4. Multiple overlapping blocks
    def test_04_multiple_overlapping_blocks(self, target_d: date):
        b1 = BlockRecord(
            block_id="BLK-O1",
            location="KM40-42",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:00",
            requested_end="12:00",
            reason="Work 1",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        b2 = BlockRecord(
            block_id="BLK-O2",
            location="KM40-42",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:30",
            requested_end="12:30",
            reason="Work 2",
            priority=Priority.MEDIUM,
            status=BlockStatus.REQUESTED,
        )
        detector = ConflictDetector(block_records=[b1, b2])
        conf_before = detector.detect_conflicts(target_date=target_d)
        assert conf_before.total_conflicts >= 1

        opt = CP_SAT_Optimizer(block_records=[b1, b2])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        # Both cannot overlap at the exact same location and time
        assert res.status == OptimizationStatus.OPTIMAL
        # If both are scheduled, their time windows must NOT overlap
        if len(res.scheduled_blocks) == 2:
            s1 = res.scheduled_blocks[0]
            s2 = res.scheduled_blocks[1]
            assert s1.start_time >= s2.end_time or s2.start_time >= s1.end_time

    # 5. Same priority conflict
    def test_05_same_priority_conflict(self, target_d: date):
        b1 = BlockRecord(
            block_id="BLK-EQ1",
            location="Chennai-Perambur",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="14:00",
            requested_end="16:00",
            reason="A",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        b2 = BlockRecord(
            block_id="BLK-EQ2",
            location="Chennai-Perambur",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="14:00",
            requested_end="16:00",
            reason="B",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        opt = CP_SAT_Optimizer(block_records=[b1, b2])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert res.status == OptimizationStatus.OPTIMAL
        # Never concurrently scheduled at identical time
        sched = res.scheduled_blocks
        if len(sched) == 2:
            assert sched[0].start_time != sched[1].start_time

    # 6. Different priority conflict
    def test_06_different_priority_conflict(self, target_d: date):
        b_crit = BlockRecord(
            block_id="BLK-CRIT",
            location="Basin Bridge-Vyasarpadi",
            block_type=BlockType.EMERGENCY,
            requested_date=target_d,
            requested_start="10:00",
            requested_end="12:00",
            reason="Track buckling emergency",
            priority=Priority.CRITICAL,
            status=BlockStatus.REQUESTED,
        )
        b_low = BlockRecord(
            block_id="BLK-LOW",
            location="Basin Bridge-Vyasarpadi",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:00",
            requested_end="12:00",
            reason="Routine vegetation clearing",
            priority=Priority.LOW,
            status=BlockStatus.REQUESTED,
        )
        opt = CP_SAT_Optimizer(block_records=[b_crit, b_low])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        crit_sched = [s for s in res.scheduled_blocks if s.request_id == "BLK-CRIT"]
        assert len(crit_sched) == 1
        # Critical priority gets primary preferred window
        assert crit_sched[0].is_preferred_match is True

    # 7. Overnight block (BLK-006: 22:00 -> 02:00)
    def test_07_overnight_block_duration_and_constraints(self, target_d: date):
        b_overnight = BlockRecord(
            block_id="BLK-006",
            location="Basin Bridge-Vyasarpadi",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="22:00",
            requested_end="02:00",
            reason="Overnight track possession",
            priority=Priority.CRITICAL,
            status=BlockStatus.APPROVED,
        )
        # Verify duration arithmetic is strictly 240 minutes, NOT negative
        from backend.app.scheduler.scheduler import _calculate_duration_minutes
        dur = _calculate_duration_minutes(b_overnight.requested_start, b_overnight.requested_end)
        assert dur == 240

        opt = CP_SAT_Optimizer(block_records=[b_overnight])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=2))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 1
        blk = res.scheduled_blocks[0]
        assert blk.duration_minutes == 240
        assert blk.start_time == "22:00"
        assert blk.end_time == "02:00"

    # 8. Adjacent intervals (boundary semantics)
    def test_08_adjacent_intervals_no_conflict(self, target_d: date):
        b1 = BlockRecord(
            block_id="BLK-ADJ-1",
            location="Chengalpattu",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:00",
            requested_end="12:00",
            reason="Work 1",
            priority=Priority.MEDIUM,
            status=BlockStatus.REQUESTED,
        )
        b2 = BlockRecord(
            block_id="BLK-ADJ-2",
            location="Chengalpattu",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="12:00",
            requested_end="14:00",
            reason="Work 2",
            priority=Priority.MEDIUM,
            status=BlockStatus.REQUESTED,
        )
        detector = ConflictDetector(block_records=[b1, b2])
        rep = detector.detect_conflicts(target_date=target_d)
        # Block-Block overlap between strictly adjacent blocks [10-12) and [12-14) is 0
        bb_conflicts = [c for c in rep.conflicts if c.conflict_type == ConflictType.BLOCK_BLOCK]
        assert len(bb_conflicts) == 0

    # 9. Impossible block (exceeding 24 hours)
    def test_09_impossible_block_handling(self, target_d: date):
        m_impossible = MaintenanceRecord(
            asset_id="IMP-001",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Overhaul",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=1500,  # > 1440 minutes
            requested_date=target_d,
            preferred_start=time(2, 0),
            required_resources=1,
            equipment="None",
            status=MaintenanceStatus.APPROVED,
        )
        opt = CP_SAT_Optimizer(maintenance_records=[m_impossible])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert len(res.scheduled_blocks) == 0
        assert len(res.unscheduled_blocks) == 1
        assert "INVALID_REQUEST" in res.unscheduled_blocks[0].reason or "NO_FEASIBLE_WINDOW" in res.unscheduled_blocks[0].reason

    # 10. Maintenance conflict (same equipment capacity bottleneck)
    def test_10_maintenance_equipment_capacity_conflict(self, target_d: date):
        m1 = MaintenanceRecord(
            asset_id="M-EQ-1",
            asset_type="Track",
            location="Chennai-Perambur",
            maintenance_type="Tamping",
            maintenance_required=True,
            priority=Priority.CRITICAL,
            duration_minutes=120,
            requested_date=target_d,
            preferred_start=time(2, 0),
            required_resources=1,
            equipment="Track Tamper",
            status=MaintenanceStatus.APPROVED,
        )
        m2 = MaintenanceRecord(
            asset_id="M-EQ-2",
            asset_type="Track",
            location="Tambaram-Chengalpattu",
            maintenance_type="Tamping",
            maintenance_required=True,
            priority=Priority.LOW,
            duration_minutes=120,
            requested_date=target_d,
            preferred_start=time(2, 0),
            required_resources=1,
            equipment="Track Tamper",
            status=MaintenanceStatus.APPROVED,
        )
        # Capacity of Track Tamper is 1
        opt = CP_SAT_Optimizer(
            maintenance_records=[m1, m2],
        )
        res = opt.optimize(OptimizationRequest(
            target_date=target_d,
            horizon_days=1,
            custom_capacities={"Track Tamper": 1},
        ))

        assert res.status == OptimizationStatus.OPTIMAL
        # If both are scheduled, they must NOT overlap in time because capacity = 1
        if len(res.scheduled_blocks) == 2:
            b1, b2 = res.scheduled_blocks
            assert b1.start_time != b2.start_time

    # 11. Train movement conflict (active COA movement)
    def test_11_train_movement_conflict_detection(self, target_d: date):
        mov = MovementRecord(
            train_id="MOV-999",
            route_id="R-CHN-AJJ",
            section="Chennai-Perambur",
            direction="Up",
            movement_status="Occupied",
            entry_time="10:00",
            exit_time="10:30",
            line="Main",
        )
        blk = BlockRecord(
            block_id="BLK-MOV-TEST",
            location="Chennai-Perambur",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:15",
            requested_end="11:15",
            reason="Track work",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        detector = ConflictDetector(movements=[mov], block_records=[blk])
        rep = detector.detect_conflicts(target_date=target_d)

        assert rep.total_conflicts >= 1
        mov_conflicts = [c for c in rep.conflicts if c.entity1_type == "Movement" or c.entity2_type == "Movement"]
        assert len(mov_conflicts) >= 1
        assert mov_conflicts[0].entity1_id == "MOV-999"

    # 12. Headway conflict (train within 15 min buffer)
    def test_12_headway_safety_buffer_violation(self, target_d: date):
        tt = TimetableRecord(
            train_id="T-BUFFER",
            service_date=target_d,
            station_code="Chennai",
            arrival_time="10:00",
            departure_time="10:05",
            sequence=1,
        )
        blk = BlockRecord(
            block_id="BLK-HEADWAY",
            location="Chennai",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:10",  # Only 5 min gap (< 15 min buffer)
            requested_end="11:00",
            reason="Testing headway",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        detector = ConflictDetector(timetables=[tt], block_records=[blk], buffer_minutes=15)
        rep = detector.detect_conflicts(target_date=target_d)

        buf_conflicts = [c for c in rep.conflicts if c.conflict_type == ConflictType.SAFETY_BUFFER_VIOLATION]
        assert len(buf_conflicts) >= 1
        assert buf_conflicts[0].severity == ConflictSeverity.LOW

    # 13. Multi-day scheduling across weekly horizon
    def test_13_multiday_date_expansion(self, target_d: date):
        records = [
            MaintenanceRecord(
                asset_id=f"MD-JOB-{i}",
                asset_type="Track",
                location=f"Section-{i}",
                maintenance_type="Routine",
                maintenance_required=True,
                priority=Priority.HIGH,
                duration_minutes=60,
                requested_date=target_d + timedelta(days=i),
                preferred_start=time(2, 0),
                required_resources=1,
                equipment="Track Tamper",
                status=MaintenanceStatus.APPROVED,
            )
            for i in range(5)
        ]
        opt = CP_SAT_Optimizer(maintenance_records=records)
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=7))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 5
        scheduled_dates = {b.service_date for b in res.scheduled_blocks}
        assert len(scheduled_dates) == 5

    # 14. No feasible solution (INFEASIBLE with impossible mandatory constraints)
    def test_14_infeasible_mandatory_constraint(self, target_d: date):
        b_imp = BlockRecord(
            block_id="BLK-FORCE-IMP",
            location="Blocked-Section",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:00",
            requested_end="18:00",
            reason="Impossible",
            priority=Priority.CRITICAL,
            status=BlockStatus.REQUESTED,
        )
        # Train permanently occupying the section leaving zero candidate slots
        tt = TimetableRecord(
            train_id="T-BLOCKER",
            service_date=target_d,
            station_code="Blocked-Section",
            arrival_time="00:01",
            departure_time="23:59",
            sequence=1,
        )
        opt = CP_SAT_Optimizer(block_records=[b_imp], timetables=[tt])
        res = opt.optimize(
            request=OptimizationRequest(target_date=target_d, horizon_days=1),
            mandatory_request_ids={"BLK-FORCE-IMP"},
        )
        assert res.status == OptimizationStatus.INFEASIBLE
        assert len(res.scheduled_blocks) == 0

    # 15. Solver time limit handling
    def test_15_solver_status_time_limit(self, target_d: date):
        # Set a tiny time limit to ensure timeout branch is gracefully handled
        opt = CP_SAT_Optimizer()
        res = opt.optimize(OptimizationRequest(
            target_date=target_d,
            horizon_days=1,
            time_limit_seconds=0.001,
        ))
        assert res.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE, OptimizationStatus.TIME_LIMIT, OptimizationStatus.UNKNOWN)

    # 16. Missing forecast handling
    def test_16_missing_forecast_graceful_handling(self, target_d: date):
        b = BlockRecord(
            block_id="BLK-NO-FC",
            location="Chennai-Arakkonam",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="03:00",
            requested_end="05:00",
            reason="Track check",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        # No forecasts provided
        opt = CP_SAT_Optimizer(block_records=[b], goods_forecasts=[])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1, include_forecast=False))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 1

    # 17. Low-confidence forecast handling
    def test_17_low_confidence_forecast_handling(self, target_d: date):
        low_fc = GoodsForecastItem(
            forecast_id="FC-LOW-CONF",
            train_id="G-UNCERTAIN",
            route_id="R-CHN-AJJ",
            section="Chennai-Perambur",
            direction="Up",
            line="Main",
            service_date=target_d,
            forecasted_entry="10:00",
            forecasted_exit="10:30",
            delay_minutes=45,
            confidence_score=0.25,
            confidence_level=ForecastConfidenceLevel.LOW,
        )
        blk = BlockRecord(
            block_id="BLK-TEST-LOW",
            location="Chennai-Perambur",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:05",
            requested_end="10:25",
            reason="Routine work",
            priority=Priority.MEDIUM,
            status=BlockStatus.REQUESTED,
        )
        detector = ConflictDetector(goods_forecasts=[low_fc], block_records=[blk])
        rep = detector.detect_conflicts(target_date=target_d)

        assert rep.total_conflicts == 1
        conf = rep.conflicts[0]
        # Low confidence forecast yields LOW severity advisory conflict
        assert conf.severity == ConflictSeverity.LOW
        assert "Advisory: Low Confidence" in conf.description

    # 18. Empty timetable handling
    def test_18_empty_timetable_handling(self, target_d: date):
        b = BlockRecord(
            block_id="BLK-NO-TT",
            location="Isolated-Branch",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="10:00",
            requested_end="14:00",
            reason="Branch line renewal",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        opt = CP_SAT_Optimizer(block_records=[b], timetables=[])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 1
        assert res.scheduled_blocks[0].start_time == "10:00"

    # 19. Empty movements handling
    def test_19_empty_movements_handling(self, target_d: date):
        b = BlockRecord(
            block_id="BLK-NO-MOV",
            location="Section-Empty-Mov",
            block_type=BlockType.MAINTENANCE,
            requested_date=target_d,
            requested_start="04:00",
            requested_end="06:00",
            reason="Rail grinding",
            priority=Priority.HIGH,
            status=BlockStatus.REQUESTED,
        )
        opt = CP_SAT_Optimizer(block_records=[b], movements=[])
        res = opt.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert res.status == OptimizationStatus.OPTIMAL
        assert len(res.scheduled_blocks) == 1

    # 20. Repeated identical optimization input (100% Determinism)
    def test_20_deterministic_reproducibility(self, target_d: date):
        records = [
            BlockRecord(
                block_id=f"BLK-DET-{i}",
                location="Chennai-Arakkonam" if i % 2 == 0 else "KM40-42",
                block_type=BlockType.MAINTENANCE,
                requested_date=target_d,
                requested_start=f"0{i+1}:00",
                requested_end=f"0{i+3}:00",
                reason=f"Routine work {i}",
                priority=Priority.HIGH if i % 2 == 0 else Priority.MEDIUM,
                status=BlockStatus.REQUESTED,
            )
            for i in range(4)
        ]
        opt1 = CP_SAT_Optimizer(block_records=records)
        res1 = opt1.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        opt2 = CP_SAT_Optimizer(block_records=records)
        res2 = opt2.optimize(OptimizationRequest(target_date=target_d, horizon_days=1))

        assert res1.status == res2.status
        assert res1.objective_value == res2.objective_value
        assert len(res1.scheduled_blocks) == len(res2.scheduled_blocks)
        assert len(res1.unscheduled_blocks) == len(res2.unscheduled_blocks)
        assert res1.solver_statistics.num_conflicts_avoided == res2.solver_statistics.num_conflicts_avoided

        for b1, b2 in zip(res1.scheduled_blocks, res2.scheduled_blocks):
            assert b1.block_id == b2.block_id
            assert b1.start_time == b2.start_time
            assert b1.end_time == b2.end_time
            assert b1.location == b2.location
            assert b1.fit_score == b2.fit_score
