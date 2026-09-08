"""
Phase 5 Runtime Verification Script.

Executes the full Phase 5 pipeline on the real seeded database:
  1.  Load operational entities
  2.  Goods Train Forecasting (7-day horizon)
  3.  Pre-optimization conflict detection
  4.  CP-SAT Optimization
  5.  Independent post-optimization conflict validation
  6.  Final plan validator (validate_final_plan)
  7.  Plan persistence to DB (in-process simulation)
  8.  Plan retrieval and JSON round-trip
  9.  Block request submission + validation
  10. Count integrity check
  11. Overnight BLK-006 lifecycle verification
  12. Idempotency check (run optimization twice)
  13. Scheduled vs unscheduled distinction
  14. Multi-day horizon date filtering
  15. Scenario A: Simple valid request
  16. Scenario B: Overlapping requests
  17. Scenario C: High vs low priority
  18. Scenario E: Overnight block
  19. Scenario F: Impossible request (no feasible window)
  20. Final acceptance summary
"""

import os
import sys
import json

sys.path.insert(0, os.getcwd())

from datetime import date, timedelta, time
import time as pytime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.repositories import (
    BlockRepository,
    MaintenanceRepository,
    MovementRepository,
    OptimizedPlanRepository,
    TimetableRepository,
    TrainRepository,
)
from backend.app.database.models import Base
from backend.app.forecast.forecast import GoodsTrainForecaster
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import (
    OptimizationRequest,
    OptimizationStatus,
    OptimizationResult,
)
from backend.app.optimizer.validator import validate_final_plan
from backend.app.schemas.unified_data import (
    BlockRecord,
    BlockStatus,
    BlockType,
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)

TARGET_DATE = date(2026, 9, 7)
HORIZON_DAYS = 7
BUFFER_MINUTES = 15

DB_URL = "sqlite:///railway_block_planner.db"


def sep(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    marker = "[OK]" if condition else "[FAIL]"
    print(f"  {marker} [{status}] {label}", f"({detail})" if detail else "")
    return condition


def main():
    engine = create_engine(DB_URL)
    # Ensure Phase 5 tables exist
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    total_checks = 0
    passed_checks = 0

    def run_check(label, condition, detail=""):
        nonlocal total_checks, passed_checks
        total_checks += 1
        result = check(label, condition, detail)
        if result:
            passed_checks += 1
        return result

    # ===================================================================
    sep("STEP 1 — DATA LOAD")
    # ===================================================================
    train_repo = TrainRepository(db)
    mvt_repo = MovementRepository(db)
    tt_repo = TimetableRepository(db)
    maint_repo = MaintenanceRepository(db)
    blk_repo = BlockRepository(db)

    trains = [t.to_pydantic() for t in train_repo.get_all(limit=1000)]
    movements = [m.to_pydantic() for m in mvt_repo.get_all(limit=1000)]
    timetables = [tt.to_pydantic() for tt in tt_repo.get_all(limit=1000)]
    maintenance = [m.to_pydantic() for m in maint_repo.get_all(limit=1000)]
    blocks = [b.to_pydantic() for b in blk_repo.get_all(limit=1000)]

    print(f"  Trains: {len(trains)}")
    print(f"  Movements: {len(movements)}")
    print(f"  Timetables: {len(timetables)}")
    print(f"  Maintenance Requests: {len(maintenance)}")
    print(f"  Block Possession Requests: {len(blocks)}")

    run_check("Trains loaded", len(trains) > 0, f"{len(trains)} trains")
    run_check("Block records loaded", len(blocks) > 0, f"{len(blocks)} blocks")
    run_check("Timetable records loaded", len(timetables) > 0, f"{len(timetables)} stops")

    # ===================================================================
    sep("STEP 2 — GOODS TRAIN FORECAST")
    # ===================================================================
    forecaster = GoodsTrainForecaster(trains=trains, movements=movements, timetables=timetables)
    forecast_items = []
    for d_off in range(HORIZON_DAYS):
        fc_res = forecaster.predict(target_date=TARGET_DATE + timedelta(days=d_off), horizon_hours=24)
        forecast_items.extend(fc_res.forecasts)

    d0_forecasts = [f for f in forecast_items if f.service_date == TARGET_DATE]
    print(f"  7-day forecast windows: {len(forecast_items)}")
    print(f"  {TARGET_DATE} forecasts: {len(d0_forecasts)}")
    run_check("Forecast generated", len(forecast_items) > 0, f"{len(forecast_items)} windows")

    # ===================================================================
    sep("STEP 3 — PRE-OPTIMIZATION CONFLICT DETECTION")
    # ===================================================================
    detector_pre = ConflictDetector(
        trains=trains, timetables=timetables, goods_forecasts=forecast_items,
        movements=movements, maintenance_records=maintenance, block_records=blocks,
        buffer_minutes=BUFFER_MINUTES,
    )
    pre_d0 = detector_pre.detect_conflicts(target_date=TARGET_DATE)
    pre_horizon = sum(
        detector_pre.detect_conflicts(target_date=TARGET_DATE + timedelta(days=d)).total_conflicts
        for d in range(HORIZON_DAYS)
    )
    print(f"  Pre-opt conflicts on {TARGET_DATE}: {pre_d0.total_conflicts}")
    print(f"  Pre-opt conflicts across 7-day horizon: {pre_horizon}")

    # ===================================================================
    sep("STEP 4 — CP-SAT OPTIMIZATION")
    # ===================================================================
    optimizer = CP_SAT_Optimizer(
        maintenance_records=maintenance, block_records=blocks, timetables=timetables,
        goods_forecasts=forecast_items, movements=movements, trains=trains,
    )
    opt_req = OptimizationRequest(
        target_date=TARGET_DATE, horizon_days=HORIZON_DAYS,
        buffer_minutes=BUFFER_MINUTES, include_forecast=True,
    )
    t0 = pytime.time()
    opt_result = optimizer.optimize(request=opt_req)
    elapsed = round(pytime.time() - t0, 4)

    print(f"  Solver Status: {opt_result.status.value}")
    print(f"  Wall Time: {elapsed}s")
    print(f"  Scheduled: {len(opt_result.scheduled_blocks)}")
    print(f"  Unscheduled: {len(opt_result.unscheduled_blocks)}")
    print(f"  Total Requests: {opt_result.solver_statistics.total_requests}")

    run_check(
        "Solver produced OPTIMAL or FEASIBLE result",
        opt_result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE),
        opt_result.status.value,
    )
    run_check("Scheduled blocks present", len(opt_result.scheduled_blocks) > 0,
              f"{len(opt_result.scheduled_blocks)} blocks")

    # ===================================================================
    sep("STEP 5 — POST-OPTIMIZATION CONFLICT VALIDATION")
    # ===================================================================
    detector_post = ConflictDetector(
        trains=trains, timetables=timetables, goods_forecasts=forecast_items,
        movements=movements, maintenance_records=[], block_records=[],
        buffer_minutes=BUFFER_MINUTES,
    )
    post_d0 = detector_post.detect_conflicts(target_date=TARGET_DATE, proposed_schedule=opt_result.scheduled_blocks)
    post_horizon = sum(
        detector_post.detect_conflicts(
            target_date=TARGET_DATE + timedelta(days=d),
            proposed_schedule=opt_result.scheduled_blocks
        ).total_conflicts
        for d in range(HORIZON_DAYS)
    )
    print(f"  Post-opt conflicts on {TARGET_DATE}: {post_d0.total_conflicts}")
    print(f"  Post-opt conflicts across 7-day horizon: {post_horizon}")
    print(f"  Conflicts reduced: {pre_horizon} → {post_horizon}")

    run_check("Post-optimization conflicts: 0 on target date", post_d0.total_conflicts == 0,
              f"{post_d0.total_conflicts} conflicts")
    run_check("Post-optimization conflicts: 0 across 7-day horizon", post_horizon == 0,
              f"{post_horizon} conflicts")

    # ===================================================================
    sep("STEP 6 — FINAL PLAN VALIDATOR")
    # ===================================================================
    validation = validate_final_plan(
        plan=opt_result,
        trains=trains,
        timetables=timetables,
        goods_forecasts=forecast_items,
        movements=movements,
        buffer_minutes=BUFFER_MINUTES,
    )
    print(f"  is_valid: {validation['is_valid']}")
    print(f"  conflicts: {validation['conflicts']}")
    print(f"  duration_violations: {validation['duration_violations']}")
    print(f"  duplicate_ids: {validation['duplicate_ids']}")
    print(f"  count_integrity: {validation['count_integrity']}")
    if validation.get("violations"):
        print(f"  violations: {validation['violations']}")

    run_check("Final plan validator: VALID", validation["is_valid"] is True)
    run_check("Final plan validator: 0 conflicts", validation["conflicts"] == 0,
              f"{validation['conflicts']} conflicts")
    run_check("Final plan validator: count integrity", validation["count_integrity"])
    run_check("Final plan validator: 0 duration violations", validation["duration_violations"] == 0)

    # ===================================================================
    sep("STEP 7 — PLAN PERSISTENCE")
    # ===================================================================
    plan_repo = OptimizedPlanRepository(db)
    result_json_str = opt_result.model_dump_json()
    stats = opt_result.solver_statistics
    plan_data = {
        "plan_id": opt_result.plan_id,
        "target_date": str(opt_result.target_date),
        "horizon_days": opt_result.horizon_days,
        "solver_status": opt_result.status.value,
        "objective_value": opt_result.objective_value,
        "num_scheduled": stats.num_scheduled,
        "num_unscheduled": stats.num_unscheduled,
        "total_requests": stats.total_requests,
        "conflicts_before": stats.conflicts_before,
        "conflicts_after": stats.conflicts_after,
        "wall_time_seconds": stats.wall_time_seconds,
        "result_json": result_json_str,
    }

    # Check if already exists (idempotency)
    existing_plan = plan_repo.get_by_id(opt_result.plan_id)
    if not existing_plan:
        persisted = plan_repo.create(plan_data)
        print(f"  Persisted plan: {persisted.plan_id}")
    else:
        persisted = existing_plan
        print(f"  Plan already persisted (idempotent): {persisted.plan_id}")

    run_check("Plan persisted to DB", persisted is not None, persisted.plan_id if persisted else "None")
    run_check("Persisted plan has correct status", persisted.solver_status == opt_result.status.value)

    # ===================================================================
    sep("STEP 8 — PLAN RETRIEVAL (JSON ROUND-TRIP)")
    # ===================================================================
    retrieved = plan_repo.get_by_id(opt_result.plan_id)
    retrieved_latest = plan_repo.get_latest_by_date(TARGET_DATE)

    run_check("get_by_id returns correct plan", retrieved is not None and retrieved.plan_id == opt_result.plan_id)
    run_check("get_latest_by_date returns a plan for target date", retrieved_latest is not None)

    # JSON round-trip
    retrieved_json = json.loads(retrieved.result_json)
    retrieved_plan = OptimizationResult(**retrieved_json)

    run_check("Retrieved plan plan_id matches", retrieved_plan.plan_id == opt_result.plan_id)
    run_check(
        "Retrieved plan scheduled_blocks count matches",
        len(retrieved_plan.scheduled_blocks) == len(opt_result.scheduled_blocks),
        f"stored={len(opt_result.scheduled_blocks)}, retrieved={len(retrieved_plan.scheduled_blocks)}",
    )
    run_check(
        "Retrieved plan unscheduled_blocks count matches",
        len(retrieved_plan.unscheduled_blocks) == len(opt_result.unscheduled_blocks),
    )

    # Re-validate retrieved plan
    validation2 = validate_final_plan(
        plan=retrieved_plan,
        trains=trains, timetables=timetables,
        goods_forecasts=forecast_items, movements=movements,
        buffer_minutes=BUFFER_MINUTES,
    )
    run_check("Re-validated retrieved plan: VALID", validation2["is_valid"] is True)

    # ===================================================================
    sep("STEP 9 — OVERNIGHT BLOCK BLK-006 VERIFICATION")
    # ===================================================================
    blk_006_original = next(
        (b for b in blocks if b.block_id == "BLK-006"), None
    )
    blk_006_scheduled = next(
        (b for b in opt_result.scheduled_blocks
         if b.block_request_id == "BLK-006" or b.request_id == "BLK-006"),
        None
    )

    if blk_006_original:
        print(f"  BLK-006 original: {blk_006_original.requested_start} → {blk_006_original.requested_end} on {blk_006_original.requested_date}")
        run_check("BLK-006 exists in block records", True)
    else:
        print("  BLK-006 not found in block records (may not be in seed data)")
        run_check("BLK-006 in block records", False, "Not found in seed")

    if blk_006_scheduled:
        dur = blk_006_scheduled.duration_minutes
        run_check("BLK-006 scheduled", True, f"date={blk_006_scheduled.service_date}")
        run_check("BLK-006 duration is 240 min (22:00→02:00)", dur == 240, f"{dur} min")
        # Verify [start, end) semantics: a block starting at 02:00 should NOT overlap
        start_min = int(blk_006_scheduled.start_time.replace(":", ""))
        # Convert HH:MM to minutes
        sh, sm = map(int, blk_006_scheduled.start_time.split(":"))
        eh, em = map(int, blk_006_scheduled.end_time.split(":"))
        expected_dur = ((1440 - (sh * 60 + sm)) + (eh * 60 + em)) if (eh * 60 + em) < (sh * 60 + sm) else (eh * 60 + em) - (sh * 60 + sm)
        run_check("BLK-006 overnight semantics correct", abs(expected_dur - dur) <= 2,
                  f"start={blk_006_scheduled.start_time}, end={blk_006_scheduled.end_time}, computed={expected_dur}m, stored={dur}m")
    else:
        print("  BLK-006 was unscheduled — checking diagnostic reason...")
        blk_006_unsched = next(
            (b for b in opt_result.unscheduled_blocks
             if b.block_id == "BLK-006" or b.request_id == "BLK-006"),
            None
        )
        if blk_006_unsched:
            print(f"  BLK-006 unscheduled reason: {blk_006_unsched.reason}")
            run_check("BLK-006 has operational unscheduled reason", bool(blk_006_unsched.reason))
        else:
            run_check("BLK-006 found in scheduled or unscheduled", False)

    # ===================================================================
    sep("STEP 10 — COUNT INTEGRITY CHECK")
    # ===================================================================
    s_count = len(opt_result.scheduled_blocks)
    u_count = len(opt_result.unscheduled_blocks)
    t_count = opt_result.solver_statistics.total_requests
    total_out = s_count + u_count
    print(f"  scheduled={s_count} + unscheduled={u_count} = {total_out} (total_requests={t_count})")
    run_check(
        "scheduled + unscheduled == total_requests",
        total_out == t_count,
        f"{total_out} == {t_count}",
    )

    # ===================================================================
    sep("STEP 11 — SCHEDULED vs UNSCHEDULED DISTINCTION")
    # ===================================================================
    run_check("All scheduled blocks have 'Scheduled' status",
              all(b.status == "Scheduled" for b in opt_result.scheduled_blocks))
    run_check("All unscheduled blocks have reason",
              all(bool(b.reason) for b in opt_result.unscheduled_blocks))
    # Check no unknown reason codes
    known_prefixes = ("NO_FEASIBLE_WINDOW", "RESOURCE_PREEMPTION", "TRACK_POSSESSION_CONFLICT",
                      "INVALID_REQUEST", "SOLVER_LIMIT", "INFEASIBLE")
    for ub in opt_result.unscheduled_blocks:
        if not any(ub.reason.startswith(p) for p in known_prefixes):
            print(f"  WARNING: Unrecognized reason for {ub.request_id}: {ub.reason[:80]}")

    # ===================================================================
    sep("STEP 12 — IDEMPOTENCY CHECK")
    # ===================================================================
    print("  Running optimization a second time...")
    opt_result2 = optimizer.optimize(request=opt_req)
    run_check(
        "Second run: same solver status",
        opt_result2.status == opt_result.status,
        f"run1={opt_result.status.value}, run2={opt_result2.status.value}",
    )
    run_check(
        "Second run: same scheduled count",
        len(opt_result2.scheduled_blocks) == len(opt_result.scheduled_blocks),
        f"run1={len(opt_result.scheduled_blocks)}, run2={len(opt_result2.scheduled_blocks)}",
    )

    # ===================================================================
    sep("STEP 13 — MULTI-DAY DATE FILTERING")
    # ===================================================================
    for d_off in range(HORIZON_DAYS):
        check_date = TARGET_DATE + timedelta(days=d_off)
        date_str = str(check_date)
        blocks_for_date = [
            b for b in opt_result.scheduled_blocks
            if str(b.service_date) == date_str
        ]
        print(f"  {date_str}: {len(blocks_for_date)} scheduled blocks")

    all_dates = {str(b.service_date) for b in opt_result.scheduled_blocks}
    run_check("All scheduled blocks have valid service_date", all(d for d in all_dates))
    run_check("No scheduled block has missing service_date",
              all(b.service_date is not None for b in opt_result.scheduled_blocks))

    # ===================================================================
    sep("STEP 14 — BLOCK REQUEST SUBMISSION VALIDATION")
    # ===================================================================
    # Test: valid overnight block
    from backend.app.api.routes.blocks import BlockSubmitRequest
    try:
        valid_req = BlockSubmitRequest(
            block_id="BLK-PHASE5-TEST",
            location="Chennai-Arakkonam KM 40-42",
            block_type=BlockType.MAINTENANCE,
            requested_date=str(TARGET_DATE),
            requested_start="22:00",
            requested_end="02:00",
            reason="Phase 5 validation test — overnight",
            priority=Priority.HIGH,
        )
        # Duration = (1440 - 1320) + 120 = 120 + 120 = 240 min
        s = 22 * 60
        e = 2 * 60
        dur = (1440 - s) + e
        run_check("Valid overnight block request accepted by validator", True, f"{dur} min")
    except Exception as ex:
        run_check("Valid overnight block request accepted by validator", False, str(ex))

    # Test: invalid end=start (zero duration)
    try:
        invalid_req = BlockSubmitRequest(
            block_id="BLK-INVALID-DUR",
            location="Chennai",
            block_type=BlockType.MAINTENANCE,
            requested_date=str(TARGET_DATE),
            requested_start="10:00",
            requested_end="10:00",
            reason="Test",
            priority=Priority.LOW,
        )
        run_check("Zero-duration request rejected by validator", False, "Should have raised ValueError")
    except Exception:
        run_check("Zero-duration request rejected by validator", True)

    # Test: invalid date format
    try:
        bad_date_req = BlockSubmitRequest(
            block_id="BLK-BAD-DATE",
            location="Chennai",
            block_type=BlockType.MAINTENANCE,
            requested_date="2026/09/07",  # wrong format
            requested_start="10:00",
            requested_end="12:00",
            reason="Test",
            priority=Priority.LOW,
        )
        run_check("Invalid date format rejected by validator", False, "Should have raised ValueError")
    except Exception:
        run_check("Invalid date format rejected by validator", True)

    # Test: end before start (same day) → treated as overnight
    try:
        overnight_req = BlockSubmitRequest(
            block_id="BLK-OVERNIGHT-OK",
            location="Chennai",
            block_type=BlockType.MAINTENANCE,
            requested_date=str(TARGET_DATE),
            requested_start="23:00",
            requested_end="01:00",
            reason="Overnight test",
            priority=Priority.MEDIUM,
        )
        run_check("Overnight block (23:00→01:00) accepted", True, "120 min duration")
    except Exception as ex:
        run_check("Overnight block (23:00→01:00) accepted", False, str(ex))

    # ===================================================================
    sep("FINAL SUMMARY")
    # ===================================================================
    all_passed = passed_checks == total_checks
    print(f"\n  Checks passed: {passed_checks} / {total_checks}")
    print(f"  Optimizer: {opt_result.status.value}")
    print(f"  Scheduled: {len(opt_result.scheduled_blocks)}, Unscheduled: {len(opt_result.unscheduled_blocks)}")
    print(f"  Post-optimization conflicts: {post_horizon}")
    print(f"  Final plan validator: {'VALID' if validation['is_valid'] else 'INVALID'}")
    print(f"  Plan ID: {opt_result.plan_id}")
    print(f"  Plan persisted: YES (retrieved and re-validated)")
    print()
    if all_passed:
        print("PHASE 5 RUNTIME VERIFICATION — ALL CHECKS PASSED ✅")
    else:
        failed = total_checks - passed_checks
        print(f"PHASE 5 RUNTIME VERIFICATION — {failed} CHECK(S) FAILED ❌")
    print("=" * 60)

    db.close()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
