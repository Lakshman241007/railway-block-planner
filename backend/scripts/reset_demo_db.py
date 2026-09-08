"""
Demo Database Reset and Baseline Initialization Script for Railway Block Planner (Phase 6).

Safely resets the local prototype database to a clean, known, verified baseline state:
  1. Re-creates all relational schema tables.
  2. Runs the Phase 2 multi-source integrator and seeds unified records.
  3. Verifies expected record counts (Trains, Movements, Timetables, Maintenance, Blocks).
  4. Ensures readiness for target evaluation date: 2026-09-07.

Usage
-----
    python backend/scripts/reset_demo_db.py
    python backend/scripts/reset_demo_db.py --check-only
"""

from __future__ import annotations

import argparse
import os
import sys
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

from sqlalchemy import func
from backend.app.database.connection import SessionLocal, init_db, reset_db
from backend.app.database.models import (
    Block,
    Maintenance,
    Movement,
    OptimizedPlan,
    Timetable,
    Train,
)
from backend.app.database.seed import seed_database


def inspect_database():
    """Inspect current database record counts."""
    init_db()
    db = SessionLocal()
    try:
        trains = db.query(func.count(Train.train_id)).scalar() or 0
        movements = db.query(func.count(Movement.id)).scalar() or 0
        timetables = db.query(func.count(Timetable.id)).scalar() or 0
        maintenance = db.query(func.count(Maintenance.id)).scalar() or 0
        blocks = db.query(func.count(Block.block_id)).scalar() or 0
        plans = db.query(func.count(OptimizedPlan.plan_id)).scalar() or 0

        return {
            "trains": trains,
            "movements": movements,
            "timetables": timetables,
            "maintenance": maintenance,
            "blocks": blocks,
            "plans": plans,
        }
    finally:
        db.close()


def reset_to_demo_state() -> bool:
    """Safely drop, recreate, and re-seed the operational database."""
    print("=" * 65)
    print(" Railway Block Planner — Demo Data Reset Utility (Phase 6)")
    print("=" * 65)
    print("Resetting database to verified baseline operational state...")

    # Drop and reseed
    stats = seed_database(reset=True)

    print("\nSeed statistics:")
    print(f"  • Trains inserted     : {stats['inserted_trains']}")
    print(f"  • Maintenance inserted: {stats['inserted_maintenance']}")
    print(f"  • Movements inserted  : {stats['inserted_movements']}")
    print(f"  • Blocks inserted     : {stats['inserted_blocks']}")
    print(f"  • Timetable inserted  : {stats['inserted_timetable']}")

    # Verify counts
    counts = inspect_database()
    print("\nDatabase verification:")
    print(f"  • Total Trains in DB     : {counts['trains']}")
    print(f"  • Total Movements in DB  : {counts['movements']}")
    print(f"  • Total Timetables in DB : {counts['timetables']}")
    print(f"  • Total Maintenance in DB: {counts['maintenance']}")
    print(f"  • Total Blocks in DB     : {counts['blocks']}")
    print(f"  • Total Plans in DB      : {counts['plans']} (clean reset)")

    is_ready = (
        counts["trains"] >= 10
        and counts["blocks"] >= 12
        and counts["timetables"] >= 200
        and counts["maintenance"] >= 10
    )

    if is_ready:
        print("\n[SUCCESS] Demo database successfully reset to clean verified state.")
        print("Default operational target date: 2026-09-07")
        return True
    else:
        print("\n[ERROR] Database verification failed: record counts below required thresholds.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Railway Block Planner Demo Data Reset")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only inspect and display current database counts without modifying data",
    )
    args = parser.parse_args()

    if args.check_only:
        print("=" * 65)
        print(" Railway Block Planner — Database Status Inspection")
        print("=" * 65)
        counts = inspect_database()
        for entity, count in counts.items():
            print(f"  • {entity.capitalize()}: {count}")
        sys.exit(0)

    success = reset_to_demo_state()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
