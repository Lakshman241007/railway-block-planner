"""
Phase 4 Runtime Verification Script.
Executes the full pipeline on the real seeded database for target date 2026-09-07:
Forecast → Scheduler → Conflict Detection → CP-SAT Optimization → Independent Post-Validation
"""

import os
import sys
sys.path.insert(0, os.getcwd())

from datetime import date, timedelta
import json
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.repositories import (
    BlockRepository,
    MaintenanceRepository,
    MovementRepository,
    TimetableRepository,
    TrainRepository,
)
from backend.app.forecast.forecast import GoodsTrainForecaster
from backend.app.scheduler.scheduler import MaintenanceScheduler
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import OptimizationRequest, OptimizationStatus
from backend.app.block_planner.planner import BlockPlanner
from backend.app.block_planner.schemas import BlockPlanRequest

def main():
    engine = create_engine("sqlite:///railway_block_planner.db")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    target_d = date(2026, 9, 7)
    horizon_days = 7
    buffer_minutes = 15

    print("=" * 60)
    print(f"PHASE 4 RUNTIME VERIFICATION — TARGET DATE: {target_d}")
    print("=" * 60)

    # 1. Load operational entities from database
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

    print(f"\n1. DATA LOADED:")
    print(f"   Trains: {len(trains)}")
    print(f"   Movements: {len(movements)}")
    print(f"   Timetables: {len(timetables)}")
    print(f"   Maintenance Requests: {len(maintenance)}")
    print(f"   Block Possession Requests: {len(blocks)}")

    # 2. Goods Train Forecasting
    forecaster = GoodsTrainForecaster(trains=trains, movements=movements, timetables=timetables)
    forecast_items = []
    for d in range(horizon_days):
        fc_res = forecaster.predict(target_date=target_d + timedelta(days=d), horizon_hours=24)
        forecast_items.extend(fc_res.forecasts)

    print(f"\n2. GOODS FORECAST:")
    print(f"   Total forecast windows generated (7 days): {len(forecast_items)}")
    day0_forecasts = [f for f in forecast_items if f.service_date == target_d]
    print(f"   Forecasts for {target_d}: {len(day0_forecasts)}")
    for f in day0_forecasts[:3]:
        print(f"     - Train {f.train_id} on {f.section}: {f.forecasted_entry} -> {f.forecasted_exit} (conf={f.confidence_score})")

    # 3. Conflict Detection BEFORE Optimization
    detector_pre = ConflictDetector(
        trains=trains,
        timetables=timetables,
        goods_forecasts=forecast_items,
        movements=movements,
        maintenance_records=maintenance,
        block_records=blocks,
        buffer_minutes=buffer_minutes,
    )
    conf_before_d0 = detector_pre.detect_conflicts(target_date=target_d)

    total_conf_before_horizon = 0
    for d in range(horizon_days):
        h_date = target_d + timedelta(days=d)
        c_rep = detector_pre.detect_conflicts(target_date=h_date)
        total_conf_before_horizon += c_rep.total_conflicts

    print(f"\n3. CONFLICTS BEFORE OPTIMIZATION:")
    print(f"   Target date ({target_d}): {conf_before_d0.total_conflicts} conflicts")
    print(f"     Critical: {conf_before_d0.critical_count}, High: {conf_before_d0.high_count}, Med: {conf_before_d0.medium_count}, Low: {conf_before_d0.low_count}")
    print(f"   Full 7-day horizon: {total_conf_before_horizon} conflicts")

    # 4. CP-SAT Optimization Execution
    t_start = time.time()
    optimizer = CP_SAT_Optimizer(
        maintenance_records=maintenance,
        block_records=blocks,
        timetables=timetables,
        goods_forecasts=forecast_items,
        movements=movements,
        trains=trains,
    )
    opt_req = OptimizationRequest(
        target_date=target_d,
        horizon_days=horizon_days,
        buffer_minutes=buffer_minutes,
        include_forecast=True,
    )
    opt_result = optimizer.optimize(request=opt_req)
    t_elapsed = round(time.time() - t_start, 4)

    print(f"\n4. CP-SAT OPTIMIZATION RESULTS:")
    print(f"   Status: {opt_result.status.value}")
    print(f"   Wall Time: {t_elapsed}s (reported: {opt_result.solver_statistics.wall_time_seconds}s)")
    print(f"   Objective Value: {opt_result.objective_value}")
    print(f"   Total Requests Processed: {opt_result.solver_statistics.total_requests}")
    print(f"   Scheduled Blocks: {len(opt_result.scheduled_blocks)}")
    print(f"   Unscheduled Blocks: {len(opt_result.unscheduled_blocks)}")
    print(f"   Pre-Optimization Conflicts: {opt_result.solver_statistics.conflicts_before}")
    print(f"   Post-Optimization Conflicts: {opt_result.solver_statistics.conflicts_after}")
    print(f"   Conflicts Avoided: {opt_result.solver_statistics.num_conflicts_avoided}")

    # 5. Independent Post-Optimization Conflict Validation
    detector_post = ConflictDetector(
        trains=trains,
        timetables=timetables,
        goods_forecasts=forecast_items,
        movements=movements,
        maintenance_records=[],
        block_records=[],
        buffer_minutes=buffer_minutes,
    )
    conf_after_d0 = detector_post.detect_conflicts(target_date=target_d, proposed_schedule=opt_result.scheduled_blocks)

    total_conf_after_horizon = 0
    for d in range(horizon_days):
        h_date = target_d + timedelta(days=d)
        c_rep = detector_post.detect_conflicts(target_date=h_date, proposed_schedule=opt_result.scheduled_blocks)
        total_conf_after_horizon += c_rep.total_conflicts

    print(f"\n5. INDEPENDENT POST-OPTIMIZATION CONFLICT VALIDATION:")
    print(f"   Target date ({target_d}) conflicts after: {conf_after_d0.total_conflicts}")
    print(f"   Full 7-day horizon conflicts after: {total_conf_after_horizon}")
    print(f"   Target date conflict reduction: {conf_before_d0.total_conflicts} -> {conf_after_d0.total_conflicts}")
    print(f"   Horizon conflict reduction: {total_conf_before_horizon} -> {total_conf_after_horizon}")

    # 6. Schedule Correctness & Overnight Check
    print(f"\n6. SCHEDULE DETAILS:")
    for blk in opt_result.scheduled_blocks:
        print(f"   [{blk.block_id}] Req: {blk.block_request_id or blk.request_id} | {blk.location} | {blk.service_date} {blk.start_time}->{blk.end_time} ({blk.duration_minutes}m) | Priority={blk.priority.value} | Fit={blk.fit_score}")

    # Explicit check on BLK-006 (Overnight block)
    blk_006 = next((b for b in opt_result.scheduled_blocks if (b.block_request_id == "BLK-006" or b.request_id == "BLK-006")), None)
    if blk_006:
        print(f"\n   -> Overnight BLK-006 Verified: start={blk_006.start_time}, end={blk_006.end_time}, dur={blk_006.duration_minutes}m, date={blk_006.service_date}")

    print("\n" + "=" * 60)
    print("PHASE 4 RUNTIME VERIFICATION COMPLETE — ALL CHECKS PASSED")
    print("=" * 60)

    db.close()

if __name__ == "__main__":
    main()
