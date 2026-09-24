"""
Scenario D Verification Script — Forced Unresolvable Conflict

Steps:
1. Create deterministic conflict (overlapping passenger timetable + critical maintenance block).
2. Process through POST /api/conflicts/process.
3. Verify: status == REQUIRES_HUMAN_REVIEW
4. Verify:
   - reason_code exists
   - explanation exists
   - conflicting_entities exist
   - violated_constraints exist
5. GET /api/conflicts/review (verify present in review queue)
6. Resolve through API (POST /api/conflicts/{id}/resolve)
7. Verify: status == HUMAN_RESOLVED
"""

import os
import sys

# Ensure root is in sys.path
sys.path.insert(0, os.path.abspath("."))

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import urllib.request
import urllib.error
from datetime import date

from backend.app.database.connection import SessionLocal
from backend.app.database.models import Maintenance, Timetable, Train

BASE = "http://127.0.0.1:8000"
TARGET_DATE_STR = "2026-10-20"
TARGET_DATE = date.fromisoformat(TARGET_DATE_STR)

def request(method, path, data=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"} if data is not None else {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(resp_body)
        except Exception:
            parsed = {"detail": resp_body}
        return e.code, parsed

def setup_deterministic_conflict():
    """Seed a deterministic high-severity conflict on target date."""
    db = SessionLocal()
    try:
        # Clean up any prior test records for this test date
        db.query(Timetable).filter(Timetable.service_date == TARGET_DATE).delete()
        db.query(Maintenance).filter(Maintenance.requested_date == TARGET_DATE).delete()
        db.query(Train).filter(Train.train_id == "EXP-99999").delete()
        db.commit()

        # 1. Create a passenger train
        train = Train(
            train_id="EXP-99999",
            train_type="Express",
            origin="MAS",
            destination="AJJ",
            status="Scheduled",
            priority="High",
            scheduled_arrival="10:00",
            scheduled_departure="10:30",
            source="Scenario_D",
        )
        db.add(train)

        # 2. Create timetable entry overlapping at station AJJ
        tt = Timetable(
            train_id="EXP-99999",
            station_code="AJJ",
            service_date=TARGET_DATE,
            arrival_time="10:00",
            departure_time="10:30",
            sequence=1,
            source="Scenario_D",
        )
        db.add(tt)

        # 3. Create high/critical maintenance possession on same location & time window
        maint = Maintenance(
            asset_id="MAIN-DET-CRIT-01",
            asset_type="Track",
            location="AJJ",
            maintenance_type="Track Renewal",
            maintenance_required=True,
            priority="Critical",
            duration_minutes=120,
            requested_date=TARGET_DATE,
            preferred_start="09:30",
            required_resources=10,
            equipment="Tamper-01",
            status="Pending",
            source="Scenario_D",
        )
        db.add(maint)
        db.commit()
        print(f"[STEP 1] Created deterministic conflict in DB for date {TARGET_DATE_STR}:")
        print(f"         - Train: EXP-99999 (AJJ, 10:00-10:30)")
        print(f"         - Maintenance: MAIN-DET-CRIT-01 (AJJ, 09:30-11:30, Priority: Critical)")
    finally:
        db.close()

def main():
    print("=" * 75)
    print("SCENARIO D -- Forced Unresolvable Conflict Verification")
    print("=" * 75)

    # 1. Create deterministic conflict
    setup_deterministic_conflict()

    # 2. Process through /api/conflicts/process
    print(f"\n[STEP 2] Processing conflicts via POST /api/conflicts/process?target_date={TARGET_DATE_STR}...")
    status, proc_data = request("POST", f"/api/conflicts/process?target_date={TARGET_DATE_STR}&buffer_minutes=15")
    assert status == 200, f"Failed to process conflicts: {status} - {proc_data}"
    
    total = proc_data.get("total_conflicts", 0)
    auto_resolved = proc_data.get("auto_resolved_count", 0)
    requires_review = proc_data.get("requires_human_review_count", 0)
    print(f"         Total Conflicts Detected: {total}")
    print(f"         Auto-Resolved:            {auto_resolved}")
    print(f"         Requires Human Review:    {requires_review}")
    assert total >= 1, "Expected at least 1 conflict detected"
    assert requires_review >= 1, "Expected at least 1 conflict requiring human review"

    # Find the deterministic conflict item
    conflicts = proc_data.get("conflicts", [])
    target_conflict = None
    for c in conflicts:
        entities = [c.get("entity1_id"), c.get("entity2_id")]
        if "EXP-99999" in entities or "MAIN-DET-CRIT-01" in entities:
            target_conflict = c
            break

    assert target_conflict is not None, f"Deterministic conflict not found in processed list: {conflicts}"
    conflict_id = target_conflict["conflict_id"]
    print(f"\n[STEP 3] Verifying Conflict Lifecycle Status:")
    print(f"         Conflict ID: {conflict_id}")
    print(f"         Status:      {target_conflict.get('status')}")
    assert target_conflict.get("status") == "REQUIRES_HUMAN_REVIEW", \
        f"Expected status REQUIRES_HUMAN_REVIEW, got {target_conflict.get('status')}"
    print(f"         [OK] status == 'REQUIRES_HUMAN_REVIEW'")

    # 4. Verify structured unresolved reason
    print(f"\n[STEP 4] Verifying Structured Unresolved Reason Fields:")
    reason = target_conflict.get("unresolved_reason")
    assert reason is not None, "unresolved_reason must not be None for REQUIRES_HUMAN_REVIEW"

    reason_code = reason.get("reason_code")
    explanation = reason.get("explanation")
    conflicting_entities = reason.get("conflicting_entities")
    violated_constraints = reason.get("violated_constraints")

    print(f"         - reason_code:          {reason_code}")
    print(f"         - explanation:          {explanation}")
    print(f"         - conflicting_entities: {conflicting_entities}")
    print(f"         - violated_constraints: {violated_constraints}")

    assert reason_code, "reason_code must be non-empty"
    assert explanation, "explanation must be non-empty"
    assert conflicting_entities and len(conflicting_entities) >= 2, "conflicting_entities must contain entities"
    assert violated_constraints and len(violated_constraints) >= 1, "violated_constraints must contain constraints"
    print(f"         [OK] reason_code exists:          '{reason_code}'")
    print(f"         [OK] explanation exists:          '{explanation[:50]}...'")
    print(f"         [OK] conflicting_entities exist:  {conflicting_entities}")
    print(f"         [OK] violated_constraints exist:  {violated_constraints}")

    # 5. GET /api/conflicts/review
    print(f"\n[STEP 5] Calling GET /api/conflicts/review to inspect review queue...")
    status, review_data = request("GET", "/api/conflicts/review")
    assert status == 200, f"Failed GET /api/conflicts/review: {status}"
    review_list = review_data.get("data", [])
    matching_in_queue = [c for c in review_list if c["conflict_id"] == conflict_id]
    assert len(matching_in_queue) == 1, f"Conflict {conflict_id} not found in review queue"
    print(f"         Queue items count: {review_data.get('count')}")
    print(f"         [OK] Conflict {conflict_id} is present in review queue with status '{matching_in_queue[0]['status']}'")

    # 6. Resolve through API
    print(f"\n[STEP 6] Resolving conflict via POST /api/conflicts/{conflict_id}/resolve...")
    resolve_payload = {
        "action": "resolve",
        "notes": "Emergency maintenance given precedence; Train EXP-99999 held at previous junction.",
        "reviewed_by": "chief_controller_kumar"
    }
    status, resolve_resp = request("POST", f"/api/conflicts/{conflict_id}/resolve", resolve_payload)
    assert status == 200, f"Failed to resolve conflict: {status} - {resolve_resp}"
    resolved_conflict = resolve_resp.get("conflict", {})

    # 7. Verify status = HUMAN_RESOLVED
    print(f"\n[STEP 7] Verifying Resolved Status:")
    final_status = resolved_conflict.get("status")
    reviewed_by = resolved_conflict.get("reviewed_by")
    review_notes = resolved_conflict.get("review_notes")
    reviewed_at = resolved_conflict.get("reviewed_at")
    print(f"         - status:        {final_status}")
    print(f"         - reviewed_by:   {reviewed_by}")
    print(f"         - review_notes:  {review_notes}")
    print(f"         - reviewed_at:   {reviewed_at}")
    assert final_status == "HUMAN_RESOLVED", f"Expected status HUMAN_RESOLVED, got {final_status}"
    print(f"         [OK] status == 'HUMAN_RESOLVED'")

    # Verify conflict is no longer in pending review queue
    status, review_data_after = request("GET", "/api/conflicts/review")
    assert status == 200
    after_ids = [c["conflict_id"] for c in review_data_after.get("data", [])]
    assert conflict_id not in after_ids, f"Conflict {conflict_id} should no longer be in pending review queue"
    print(f"         [OK] Conflict removed from pending review queue")

    print("\n" + "=" * 75)
    print("SCENARIO D -- ALL 7 STEPS COMPLETED & VERIFIED SUCCESSFULLY [OK]")
    print("=" * 75)

if __name__ == "__main__":
    main()
