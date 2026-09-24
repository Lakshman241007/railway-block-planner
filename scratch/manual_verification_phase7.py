"""
Manual API Verification Script for Phase 7.

Validates the full HTTP pipeline:
HTTP Request → FastAPI → Block Planner / Scheduler → CP-SAT → HTTP Response

Scenario 1:
- 2 candidate works competing for 1 constrained available window (60 min)
- Work 1: 60 min, priority_value = 40.0
- Work 2: 60 min, priority_value = 95.0
- Window: 60 min, max_parallel_works = 1
Expected: Higher-priority Work 2 is selected by CP-SAT through the API.

Scenario 2:
- 2 candidate works:
  - Work 1: 60 min, priority_value = 25.0 (feasible for window)
  - Work 2: 180 min, priority_value = 99.0 (high priority, but infeasible for 60 min window)
- Window: 60 min, max_parallel_works = 1
Expected: High priority cannot override feasibility. Work 1 is selected; Work 2 is rejected.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

def main():
    client = TestClient(app)
    target_date = "2026-09-07"

    print("=" * 60)
    print("PHASE 7 MANUAL END-TO-END HTTP API VERIFICATION")
    print("=" * 60)

    # -------------------------------------------------------------------
    # Scenario 1: Competing works with different priority_values
    # -------------------------------------------------------------------
    print("\n--- Scenario 1: Two competing feasible works, differing priorities ---")
    payload1 = {
        "problem_id": "MANUAL-SCENARIO-1",
        "target_date": target_date,
        "candidate_works": [
            {
                "work_id": "WORK-LOW",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,
                "priority_value": 40.0,
            },
            {
                "work_id": "WORK-HIGH",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,
                "priority_value": 95.0,
            },
        ],
        "available_windows": [
            {
                "window_id": "WIN-CONSTRAINED-1",
                "corridor": "Chennai-Arakkonam",
                "service_date": target_date,
                "start_time": "02:00",
                "end_time": "03:00",
                "duration_minutes": 60,
                "max_parallel_works": 1,
            }
        ],
    }

    resp1 = client.post("/api/scheduler/daily", json=payload1)
    assert resp1.status_code == 200, f"Scenario 1 failed with {resp1.status_code}: {resp1.text}"
    data1 = resp1.json()

    print(f"Status Code: {resp1.status_code}")
    print(f"Plan ID: {data1['plan_id']}")
    print(f"Total Scheduled: {data1['total_scheduled']}")
    print(f"Total Unscheduled: {data1['total_unscheduled']}")
    scheduled_ids1 = [w.get("request_id") or w.get("work_id") for w in data1["scheduled_works"]]
    print(f"Scheduled IDs: {scheduled_ids1}")
    assert "WORK-HIGH" in scheduled_ids1, "Expected WORK-HIGH to be selected due to higher priority_value"
    assert "WORK-LOW" not in scheduled_ids1, "Expected WORK-LOW to be unselected due to single slot capacity"
    print(">>> Scenario 1 PASSED: Higher-priority feasible work selected.")

    # -------------------------------------------------------------------
    # Scenario 2: High priority + Infeasible window vs Feasible low priority
    # -------------------------------------------------------------------
    print("\n--- Scenario 2: High-priority infeasible work vs Low-priority feasible work ---")
    payload2 = {
        "problem_id": "MANUAL-SCENARIO-2",
        "target_date": target_date,
        "candidate_works": [
            {
                "work_id": "WORK-FEASIBLE-LOW",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 60,
                "priority_value": 25.0,
            },
            {
                "work_id": "WORK-INFEASIBLE-HIGH",
                "location": "Chennai-Arakkonam",
                "required_duration_minutes": 180,  # 3 hours, cannot fit in 1 hour window
                "priority_value": 99.0,
            },
        ],
        "available_windows": [
            {
                "window_id": "WIN-CONSTRAINED-2",
                "corridor": "Chennai-Arakkonam",
                "service_date": target_date,
                "start_time": "02:00",
                "end_time": "03:00",
                "duration_minutes": 60,
                "max_parallel_works": 1,
            }
        ],
    }

    resp2 = client.post("/api/scheduler/daily", json=payload2)
    assert resp2.status_code == 200, f"Scenario 2 failed with {resp2.status_code}: {resp2.text}"
    data2 = resp2.json()

    print(f"Status Code: {resp2.status_code}")
    print(f"Plan ID: {data2['plan_id']}")
    print(f"Total Scheduled: {data2['total_scheduled']}")
    print(f"Total Unscheduled: {data2['total_unscheduled']}")
    scheduled_ids2 = [w.get("request_id") or w.get("work_id") for w in data2["scheduled_works"]]
    print(f"Scheduled IDs: {scheduled_ids2}")
    unscheduled_ids2 = [w.get("request_id") or w.get("work_id") for w in data2["unscheduled_works"]]
    print(f"Unscheduled IDs: {unscheduled_ids2}")

    assert "WORK-FEASIBLE-LOW" in scheduled_ids2, "Expected feasible low-priority work to be scheduled"
    assert "WORK-INFEASIBLE-HIGH" not in scheduled_ids2, "Infeasible work MUST NOT be scheduled regardless of priority_value"
    assert "WORK-INFEASIBLE-HIGH" in unscheduled_ids2, "Infeasible work must appear in unscheduled_works"
    print(">>> Scenario 2 PASSED: High priority cannot override feasibility hard constraints.")

    print("\n" + "=" * 60)
    print("ALL MANUAL VERIFICATIONS SUCCEEDED!")
    print("=" * 60)

if __name__ == "__main__":
    main()
