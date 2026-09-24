"""Manual backend verification script for Phase 9 using standard library urllib."""
import json
import urllib.request
import urllib.error
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "http://127.0.0.1:8000"

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

def pprint(data):
    print(json.dumps(data, indent=2, default=str))

print("=" * 70)
print("SCENARIO A -- Process conflicts through escalation-aware resolver")
print("=" * 70)
status, data = request("POST", "/api/conflicts/process?buffer_minutes=15")
assert status == 200, f"Status {status}: {data}"
print(f"Total conflicts: {data['total_conflicts']}")
print(f"Auto-resolved:   {data['auto_resolved_count']}")
print(f"Requires review: {data['requires_human_review_count']}")

auto_resolved = [c for c in data['conflicts'] if c['status'] == 'AUTO_RESOLVED']
needs_review = [c for c in data['conflicts'] if c['status'] == 'REQUIRES_HUMAN_REVIEW']
print(f"\n[OK] AUTO_RESOLVED conflicts: {len(auto_resolved)}")
print(f"[OK] REQUIRES_HUMAN_REVIEW conflicts: {len(needs_review)}")

for c in auto_resolved[:2]:
    print(f"  - {c['conflict_id']}: severity={c['severity']}, recommendation={c.get('auto_resolver_recommendation', {}).get('strategy', 'N/A')}")
    assert c.get('unresolved_reason') is None, "AUTO_RESOLVED should NOT have unresolved_reason"

for c in needs_review[:2]:
    print(f"  - {c['conflict_id']}: severity={c['severity']}, reason_code={c.get('unresolved_reason', {}).get('reason_code', 'N/A')}")
    assert c.get('unresolved_reason') is not None, "REQUIRES_HUMAN_REVIEW should have unresolved_reason"

print("\n" + "=" * 70)
print("SCENARIO B -- Conflict Review API")
print("=" * 70)
status, review_data = request("GET", "/api/conflicts/review")
assert status == 200
print(f"Conflicts for review: {review_data['count']}")

status, all_data = request("GET", "/api/conflicts/review/all")
assert status == 200
print(f"All tracked conflicts: {all_data['count']}")

if needs_review:
    cid = needs_review[0]['conflict_id']
    print(f"\nResolving conflict {cid}...")
    status, result = request("POST", f"/api/conflicts/{cid}/resolve", {
        "action": "resolve",
        "notes": "Verified by manual test",
        "reviewed_by": "test_operator"
    })
    assert status == 200, f"Status {status}: {result}"
    print(f"  [OK] Status: {result['conflict']['status']}")
    print(f"  [OK] Reviewed by: {result['conflict']['reviewed_by']}")
    assert result['conflict']['status'] == 'HUMAN_RESOLVED'

    print(f"\nAttempting to reject already-resolved conflict {cid}...")
    status, err = request("POST", f"/api/conflicts/{cid}/reject", {
        "action": "reject", "notes": "Should fail"
    })
    assert status == 400, f"Expected 400, got {status}"
    print(f"  [OK] Correctly rejected with 400: {err.get('detail', '')[:80]}")

if len(needs_review) > 1:
    cid2 = needs_review[1]['conflict_id']
    print(f"\nDeferring conflict {cid2}...")
    status, result = request("POST", f"/api/conflicts/{cid2}/defer", {
        "action": "defer", "notes": "Will handle later"
    })
    assert status == 200
    assert result['conflict']['status'] == 'DEFERRED'
    print(f"  [OK] Status: DEFERRED (still unresolved)")

print("\n" + "=" * 70)
print("SCENARIO C -- Plan verification lifecycle")
print("=" * 70)

# Check or generate a plan
status, plans_data = request("GET", "/api/plans/optimized?limit=5")
assert status == 200
plans_list = plans_data.get('data', [])
print(f"Existing plans in DB: {len(plans_list)}")

if not plans_list:
    # Trigger optimization to generate a plan if none exists
    print("Triggering optimization to generate a plan...")
    status, opt_resp = request("POST", "/api/plans/optimize", {
        "target_date": "2026-03-30",
        "buffer_minutes": 15
    })
    if status == 200 and 'plan_id' in opt_resp:
        plan_id = opt_resp['plan_id']
        print(f"Generated new plan: {plan_id}")
    else:
        # Re-fetch
        status, plans_data = request("GET", "/api/plans/optimized?limit=5")
        plans_list = plans_data.get('data', [])
        plan_id = plans_list[0]['plan_id'] if plans_list else None
else:
    plan_id = plans_list[0]['plan_id']

if plan_id:
    print(f"Testing lifecycle with plan: {plan_id}")
    
    # Check plan status endpoint
    status, status_data = request("GET", f"/api/plans/{plan_id}/status")
    assert status == 200
    print(f"  [OK] Plan status API: plan_status={status_data['plan_status']}")
    print(f"  [OK] Employee visible: {status_data['is_employee_visible']}")

    curr_status = status_data['plan_status']
    if curr_status == 'DRAFT':
        # Submit for review
        print(f"\n  Submitting plan {plan_id} for review...")
        status, result = request("POST", f"/api/plans/{plan_id}/submit-review", {
            "notes": "Ready for operator review"
        })
        assert status == 200, f"Status {status}: {result}"
        print(f"  [OK] {result['transition']['previous_status']} -> {result['transition']['new_status']}")
        curr_status = result['plan']['plan_status']

    if curr_status == 'OPERATOR_REVIEW':
        # Approve
        print(f"  Approving plan {plan_id}...")
        status, result = request("POST", f"/api/plans/{plan_id}/approve", {
            "notes": "Plan approved by supervisor", "approved_by": "supervisor_alice"
        })
        assert status == 200, f"Status {status}: {result}"
        print(f"  [OK] {result['transition']['previous_status']} -> {result['transition']['new_status']}")
        assert result['plan']['approved_by'] == 'supervisor_alice'
        curr_status = result['plan']['plan_status']

    # Check employee-facing published endpoint
    status, published = request("GET", "/api/plans/published")
    assert status == 200
    print(f"\n  Employee-facing plans (APPROVED/PUBLISHED): {published['count']}")
    assert any(p['plan_id'] == plan_id for p in published['data']), "Approved/Published plan should be visible"
    print(f"  [OK] Plan {plan_id} is visible in employee-facing endpoint")

    if curr_status == 'APPROVED':
        print(f"  Publishing plan {plan_id}...")
        status, result = request("POST", f"/api/plans/{plan_id}/publish", {
            "notes": "Releasing to field operations"
        })
        assert status == 200
        print(f"  [OK] {result['transition']['previous_status']} -> {result['transition']['new_status']}")
        assert result['plan']['published_at'] is not None

# Verify unapproved plans are NOT in published endpoint
print(f"\n  Verifying DRAFT / OPERATOR_REVIEW plans are excluded from published endpoint...")
status, published = request("GET", "/api/plans/published")
assert status == 200
for p in published['data']:
    assert p['plan_status'] in ('APPROVED', 'PUBLISHED'), f"Non-approved plan found: {p['plan_id']} ({p['plan_status']})"
print(f"  [OK] All {published['count']} published plans are strictly APPROVED or PUBLISHED")

print("\n" + "=" * 70)
print("ALL MANUAL VERIFICATION SCENARIOS PASSED [OK]")
print("=" * 70)
