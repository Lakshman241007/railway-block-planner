"""Minimal migration script to add Phase 9 columns to optimized_plans."""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "railway_block_planner.db"
conn = sqlite3.connect(db_path)
cursor = conn.execute("PRAGMA table_info(optimized_plans)")
cols = [row[1] for row in cursor.fetchall()]
print(f"Existing columns: {cols}")

migrations = {
    "plan_status": "ALTER TABLE optimized_plans ADD COLUMN plan_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'",
    "approved_by": "ALTER TABLE optimized_plans ADD COLUMN approved_by VARCHAR(100)",
    "approved_at": "ALTER TABLE optimized_plans ADD COLUMN approved_at DATETIME",
    "published_at": "ALTER TABLE optimized_plans ADD COLUMN published_at DATETIME",
    "plan_notes": "ALTER TABLE optimized_plans ADD COLUMN plan_notes TEXT",
}

for col_name, sql in migrations.items():
    if col_name not in cols:
        print(f"Adding column: {col_name}")
        conn.execute(sql)
    else:
        print(f"Column already exists: {col_name}")

conn.commit()
conn.close()
print("Migration complete.")
