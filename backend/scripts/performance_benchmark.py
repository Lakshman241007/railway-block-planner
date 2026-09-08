"""
Performance Benchmark Measurement Script for Railway Block Planner (Phase 6).

Measures:
  1. DB connection & initialization time
  2. Entity retrieval queries (Trains, Movements, Timetable, Maintenance, Blocks)
  3. Goods train forecast computation
  4. Conflict detection execution
  5. CP-SAT optimization wall time
  6. Final plan validation time
  7. Plan persistence & retrieval round-trip
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database.connection import SessionLocal, init_db
from backend.app.database.repositories import (
    BlockRepository,
    MaintenanceRepository,
    MovementRepository,
    OptimizedPlanRepository,
    TimetableRepository,
    TrainRepository,
)
from backend.app.forecast.forecast import GoodsTrainForecaster
from backend.app.scheduler.conflict_detector import ConflictDetector
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import OptimizationRequest
from backend.app.optimizer.validator import validate_final_plan

TARGET_DATE = date(2026, 9, 7)


def measure(name, func, iterations=1):
    start = time.perf_counter()
    res = None
    for _ in range(iterations):
        res = func()
    elapsed_ms = ((time.perf_counter() - start) / iterations) * 1000.0
    print(f"  • {name:<36}: {elapsed_ms:8.2f} ms")
    return elapsed_ms, res


def main():
    print("=" * 65)
    print(" Railway Block Planner — Performance Benchmark (Phase 6)")
    print("=" * 65)

    client = TestClient(app)

    # 1. Database init
    t_init, _ = measure("Database table initialization", init_db)

    # 2. Entity retrieval via repositories
    db = SessionLocal()
    train_repo = TrainRepository(db)
    maint_repo = MaintenanceRepository(db)
    move_repo = MovementRepository(db)
    block_repo = BlockRepository(db)
    tt_repo = TimetableRepository(db)

    t_trains, trains = measure("Train retrieval (DB)", lambda: train_repo.get_all())
    t_maint, maint = measure("Maintenance retrieval (DB)", lambda: maint_repo.get_all())
    t_move, move = measure("Movement retrieval (DB)", lambda: move_repo.get_all())
    t_block, blocks = measure("Block retrieval (DB)", lambda: block_repo.get_all())
    t_tt, tt = measure("Timetable retrieval (DB)", lambda: tt_repo.get_all())

    # 3. Forecast generation
    forecaster = GoodsTrainForecaster(trains=trains, movements=move, timetables=tt)
    t_fc, fc = measure("Goods train forecast (72h)", lambda: forecaster.predict(target_date=TARGET_DATE, horizon_hours=72))

    # 4. Conflict detection
    detector = ConflictDetector(trains=trains, block_records=blocks, timetables=tt, maintenance_records=maint, movements=move)
    t_cd, cd = measure("Conflict detection (target date)", lambda: detector.detect_conflicts(target_date=TARGET_DATE))

    # 5. CP-SAT optimization
    optimizer = CP_SAT_Optimizer(
        trains=trains,
        maintenance_records=maint,
        block_records=blocks,
        movements=move,
        timetables=tt,
    )
    req = OptimizationRequest(target_date=TARGET_DATE, horizon_days=7, buffer_minutes=15)
    t_opt, opt_result = measure("CP-SAT optimization (7 days)", lambda: optimizer.optimize(req))

    # 6. Final plan validation
    t_val, val_result = measure("Final plan independent validation", lambda: validate_final_plan(opt_result))

    # 7. Persistence and retrieval
    plan_repo = OptimizedPlanRepository(db)
    plan_data = {
        "plan_id": f"BENCH-{opt_result.plan_id}",
        "target_date": opt_result.target_date,
        "horizon_days": opt_result.horizon_days,
        "solver_status": opt_result.status.value,
        "objective_value": opt_result.objective_value,
        "num_scheduled": opt_result.solver_statistics.num_scheduled,
        "num_unscheduled": opt_result.solver_statistics.num_unscheduled,
        "total_requests": opt_result.solver_statistics.total_requests,
        "conflicts_before": opt_result.solver_statistics.conflicts_before,
        "conflicts_after": opt_result.solver_statistics.conflicts_after,
        "wall_time_seconds": opt_result.solver_statistics.wall_time_seconds,
        "result_json": opt_result.model_dump_json(),
    }
    t_persist, _ = measure("Plan persistence to DB", lambda: plan_repo.create(plan_data))
    t_retrieve, _ = measure("Plan retrieval from DB", lambda: plan_repo.get_latest_by_date(TARGET_DATE))

    # 8. REST API Endpoints via TestClient
    print("\nREST API Response Latency (in-process):")
    measure("GET  /health", lambda: client.get("/health"))
    measure("GET  /api/trains", lambda: client.get("/api/trains"))
    measure("GET  /api/blocks", lambda: client.get("/api/blocks"))
    measure("GET  /api/maintenance", lambda: client.get("/api/maintenance"))
    measure("GET  /api/timetable", lambda: client.get("/api/timetable?service_date=2026-09-07"))
    measure("GET  /api/movements", lambda: client.get("/api/movements"))
    measure("GET  /api/forecast", lambda: client.get("/api/forecast?target_date=2026-09-07&horizon_hours=48"))
    measure("GET  /api/conflicts", lambda: client.get("/api/conflicts?service_date=2026-09-07"))
    measure("POST /api/plans/optimize", lambda: client.post("/api/plans/optimize", json={"target_date": "2026-09-07", "horizon_days": 7}))

    db.close()
    print("\n[SUCCESS] Performance benchmark completed successfully.")


if __name__ == "__main__":
    main()
