# Phase 9 Walkthrough — Human-in-the-Loop Conflict Escalation & Plan Verification

> [!IMPORTANT]
> **Frontend Exclusion Notice:**
> Frontend implementation is intentionally excluded from Phase 9 and will be implemented separately by the frontend team. This phase provides all backend contracts, schemas, escalation services, database schema migrations, and REST APIs required to power human-in-the-loop review and multi-stage plan verification.

---

## 1. Existing Conflict Architecture Summary

Prior to Phase 9, the railway block planning system featured:
- **Conflict Detection:** Identified train-block, block-block, and resource contention overlaps (`backend/app/scheduler/conflict_detector.py`).
- **Rule-Based AutoResolver:** Suggested resolution strategies (e.g. `RETRAIN_DELAY`, `BLOCK_SHIFT`, `RESOURCE_REALLOCATION`) via `backend/app/scheduler/auto_resolver.py`.
- **Stateless Recommendations:** The resolver returned recommendation objects directly without tracking operational lifecycle states or tracking unresolved conflicts requiring operator escalation.
- **Single-Stage Optimization:** Plans were generated and saved with basic execution metadata, but lacked formal multi-stage verification states (`DRAFT` → `OPERATOR_REVIEW` → `APPROVED` → `PUBLISHED`).

---

## 2. New Conflict Lifecycle States & State Transitions

Phase 9 introduces explicit conflict lifecycle states defined in [`backend/app/schemas/phase9_schemas.py`](file:///c:/Users/kk141/source/repos/railway-block-planner/backend/app/schemas/phase9_schemas.py):

| State | Type | Description | Allowed Next Transitions |
| :--- | :--- | :--- | :--- |
| `DETECTED` | Initial | Conflict detected during scheduling/conflict detection | `AUTO_RESOLVED`, `REQUIRES_HUMAN_REVIEW` |
| `AUTO_RESOLVED` | Resolved | Automatically resolved by rule engine (low/medium severity) | *(Terminal)* |
| `REQUIRES_HUMAN_REVIEW` | Pending | Escalated to human operator queue (high/critical severity or unresolvable) | `HUMAN_RESOLVED`, `REJECTED`, `DEFERRED` |
| `DEFERRED` | Pending | Postponed by operator; remains unresolved in review queue | `HUMAN_RESOLVED`, `REJECTED` |
| `HUMAN_RESOLVED` | Resolved | Explicitly resolved by human operator | *(Terminal)* |
| `REJECTED` | Resolved (Rejected) | Explicitly rejected by human operator | *(Terminal)* |

### State Transition Validation
Transitions are strictly enforced via `VALID_CONFLICT_TRANSITIONS`. Invalid transitions (e.g., attempting to reject an `AUTO_RESOLVED` conflict or transitioning directly from `DETECTED` to `HUMAN_RESOLVED`) raise HTTP 400 validation errors.

---

## 3. Escalation Behavior & AutoResolver Wrapping

The `EscalatingAutoResolver` in [`backend/app/services/human_review_service.py`](file:///c:/Users/kk141/source/repos/railway-block-planner/backend/app/services/human_review_service.py) wraps the existing `AutoResolver` rather than replacing it:

```
[Conflict Detector] -> ConflictItem
                              |
                   [EscalatingAutoResolver]
                              |
            +-----------------+-----------------+
            |                                   |
    Severity <= MEDIUM                  Severity >= HIGH
    or Resolvable Strategy              or Unresolvable Strategy
            |                                   |
            v                                   v
     `AUTO_RESOLVED`                 `REQUIRES_HUMAN_REVIEW`
  (No unresolved_reason)              (With UnresolvedReason)
```

- **Transparent Wrapping:** The core recommendation engine (`AutoResolver.resolve()`) remains intact and unmodified.
- **Accurate Resolution Counting:** Unresolved or high-severity conflicts escalated to `REQUIRES_HUMAN_REVIEW` are **never** counted as resolved.
- **Zero Hallucination:** No fake confidence scores or synthetic probabilities are generated.

---

## 4. Structured Unresolved-Conflict Reasons

When a conflict cannot be automatically resolved or requires mandatory human judgment, the service attaches a structured `UnresolvedReason` object:

```json
{
  "reason_code": "HIGH_SEVERITY_MANDATORY_REVIEW",
  "explanation": "Conflict involves high or critical severity (HIGH) which requires mandatory human operator verification before execution.",
  "conflicting_entities": ["TRAIN_12001", "BLK-2026-001"],
  "violated_constraints": ["HEADWAY", "TRACK_OCCUPANCY"],
  "mitigation_attempted": "RETRAIN_DELAY",
  "recommended_action": "Operator should review train delay vs block schedule adjustment."
}
```

Standard reason codes include:
- `HIGH_SEVERITY_MANDATORY_REVIEW`: Severity is `HIGH` or `CRITICAL`.
- `NO_VIABLE_SLOT`: Insufficient track window or buffer available.
- `RESOURCE_UNAVAILABLE`: Crew, loco, or maintenance equipment constraint.
- `PREFERENCE_CONFLICT`: Conflicting priority constraints between competing entities.
- `UNKNOWN_UNDETERMINED_REASON`: Explicit fallback for edge cases (never invents false causes).

---

## 5. Human Review API Endpoints

Registered under `/api/conflicts`:

- `POST /api/conflicts/process?buffer_minutes=15` — Runs conflict detection + escalating resolver; returns conflicts categorized by status.
- `GET /api/conflicts/review` — Returns pending conflicts (`REQUIRES_HUMAN_REVIEW` and `DEFERRED`).
- `GET /api/conflicts/review/all` — Returns all tracked conflicts.
- `POST /api/conflicts/{conflict_id}/resolve` — Mark conflict as `HUMAN_RESOLVED`.
- `POST /api/conflicts/{conflict_id}/reject` — Mark conflict as `REJECTED`.
- `POST /api/conflicts/{conflict_id}/defer` — Mark conflict as `DEFERRED`.

---

## 6. Plan Verification Lifecycle & Employee-Facing Plan Visibility

### Database Schema Extension
Extended `OptimizedPlan` in [`backend/app/database/models.py`](file:///c:/Users/kk141/source/repos/railway-block-planner/backend/app/database/models.py) with 5 new columns:
- `plan_status`: `VARCHAR(50)` (default `"DRAFT"`)
- `approved_by`: `VARCHAR(100)` (nullable)
- `approved_at`: `DATETIME` (nullable)
- `published_at`: `DATETIME` (nullable)
- `plan_notes`: `TEXT` (nullable)

### Lifecycle Flow
```
 [Optimizer] ---> DRAFT
                    |
                    v (submit-review)
             OPERATOR_REVIEW
                    |
        +-----------+-----------+
        |                       | (request-rework)
        v (approve)             +---> DRAFT
     APPROVED
        |
        v (publish)
    PUBLISHED (Terminal)
```

### Employee-Facing Visibility Guarantee
The endpoint `GET /api/plans/published` filters strictly by:
```python
OptimizedPlan.plan_status.in_(["APPROVED", "PUBLISHED"])
```
Unapproved plans (`DRAFT`, `OPERATOR_REVIEW`) are never exposed to downstream employee-facing consumers.

---

## 7. Compatibility with Existing Operator Priority Editing

Existing operator editing and priority-based optimization remain fully functional:
- When an operator patches a maintenance block priority (`PATCH /api/blocks/{id}` or `PATCH /api/maintenance/{id}`), the optimizer respects the modified priorities.
- If an existing `APPROVED` plan has its underlying blocks or priorities modified, the verification service can transition the plan status back to `OPERATOR_REVIEW` or `DRAFT` via `require_re_review()`, ensuring unreviewed changes are never silently published.

---

## 8. Complete API Examples & Payload Schemas

### Resolving a Conflict
`POST /api/conflicts/CONF-TRN-001/resolve`
```json
{
  "action": "resolve",
  "notes": "Train 12001 rescheduled by 15 minutes to clear maintenance window",
  "reviewed_by": "operator_sharma"
}
```

### Approving a Plan
`POST /api/plans/OPT-PLAN-2E54536E/approve`
```json
{
  "notes": "Plan verified against overnight track maintenance requirements",
  "approved_by": "supervisor_patel"
}
```

### Publishing a Plan
`POST /api/plans/OPT-PLAN-2E54536E/publish`
```json
{
  "notes": "Plan released to dispatch operations"
}
```

---

## 9. Phase 9 Backend Test Coverage (40 Focused Tests)

Defined in [`backend/tests/test_phase9_human_verification.py`](file:///c:/Users/kk141/source/repos/railway-block-planner/backend/tests/test_phase9_human_verification.py):

| Test Class | Test Count | Description |
| :--- | :--- | :--- |
| `TestConflictLifecycle` | 13 | Tests DETECTED, AUTO_RESOLVED, REQUIRES_HUMAN_REVIEW, resolve, reject, defer, terminal states, and invalid transitions |
| `TestUnresolvedReason` | 7 | Verifies structured reason codes, entity preserving, fallback handling, and zero hallucination for auto-resolved items |
| `TestPlanLifecycle` | 8 | Tests DRAFT initialization, priority editing compatibility, rework loops, approval, publication, and employee visibility |
| `TestPlanInvalidTransitions` | 4 | Enforces invalid state transition restrictions (e.g. DRAFT cannot directly publish) |
| `TestMixedScenarios` | 4 | Tests mixed severity conflict batches, recommendation preservation, and rework cycles |
| `TestTransitionMaps` | 4 | Verifies transition graph completeness and terminal state invariants |

---

## 10. Focused Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\kk141\source\repos\railway-block-planner
collected 40 items

backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_conflict_detected_initial_state PASSED [  2%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_resolvable_conflict_auto_resolved PASSED [  5%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_unresolvable_conflict_requires_human_review PASSED [  7%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_high_severity_requires_human_review PASSED [ 10%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_unresolved_conflict_not_counted_as_resolved PASSED [ 12%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_human_resolve PASSED [ 15%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_human_reject PASSED [ 17%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_human_defer PASSED [ 20%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_deferred_conflict_remains_unresolved PASSED [ 22%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_deferred_can_be_resolved_later PASSED [ 25%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_invalid_transition_auto_resolved_to_human_resolved PASSED [ 27%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_invalid_transition_human_resolved_to_rejected PASSED [ 30%]
backend/tests/test_phase9_human_verification.py::TestConflictLifecycle::test_conflict_not_found_raises_error PASSED [ 32%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_unresolved_conflict_has_reason PASSED [ 35%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_constraints_preserved PASSED [ 37%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_unknown_reason_explicit PASSED [ 40%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_undetermined_reason_fallback PASSED [ 42%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_no_fabricated_reason_for_auto_resolved PASSED [ 45%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_reason_uses_actual_conflict_data PASSED [ 47%]
backend/tests/test_phase9_human_verification.py::TestUnresolvedReason::test_all_conflict_types_produce_valid_reasons PASSED [ 50%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_plan_starts_as_draft PASSED [ 52%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_priority_editing_preserved PASSED [ 55%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_modified_plan_requires_review PASSED [ 57%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_approval_changes_state PASSED [ 60%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_publication_changes_state PASSED [ 62%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_unapproved_plans_not_employee_visible PASSED [ 65%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_approved_plans_employee_visible PASSED [ 67%]
backend/tests/test_phase9_human_verification.py::TestPlanLifecycle::test_plan_persistence_compatibility PASSED [ 70%]
backend/tests/test_phase9_human_verification.py::TestPlanInvalidTransitions::test_cannot_approve_draft_directly PASSED [ 72%]
backend/tests/test_phase9_human_verification.py::TestPlanInvalidTransitions::test_cannot_publish_draft PASSED [ 75%]
backend/tests/test_phase9_human_verification.py::TestPlanInvalidTransitions::test_cannot_publish_operator_review PASSED [ 77%]
backend/tests/test_phase9_human_verification.py::TestPlanInvalidTransitions::test_published_is_terminal PASSED [ 80%]
backend/tests/test_phase9_human_verification.py::TestMixedScenarios::test_mixed_severity_conflicts PASSED [ 82%]
backend/tests/test_phase9_human_verification.py::TestMixedScenarios::test_auto_resolver_recommendation_preserved PASSED [ 85%]
backend/tests/test_phase9_human_verification.py::TestMixedScenarios::test_conflict_store_operations PASSED [ 87%]
backend/tests/test_phase9_human_verification.py::TestMixedScenarios::test_full_plan_lifecycle_with_rework PASSED [ 90%]
backend/tests/test_phase9_human_verification.py::TestTransitionMaps::test_all_conflict_statuses_in_transition_map PASSED [ 92%]
backend/tests/test_phase9_human_verification.py::TestTransitionMaps::test_all_plan_statuses_in_transition_map PASSED [ 95%]
backend/tests/test_phase9_human_verification.py::TestTransitionMaps::test_terminal_states_have_no_transitions PASSED [ 97%]
backend/tests/test_phase9_human_verification.py::TestTransitionMaps::test_published_is_terminal PASSED [100%]

============================= 40 passed in 2.44s ==============================
```

---

## 11. Full Test Suite Regression Results (412 Passed)

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\kk141\source\repos\railway-block-planner
collected 412 items

backend\tests\test_api.py ..................................             [  8%]
backend\tests\test_collectors.py .....................                   [ 13%]
backend\tests\test_conflict_resolver.py ......                           [ 14%]
backend\tests\test_database.py .....                                     [ 16%]
backend\tests\test_entity_mapper.py ........                             [ 17%]
backend\tests\test_forecast.py ........                                  [ 19%]
backend\tests\test_integrator.py ......                                  [ 21%]
backend\tests\test_merger.py .....                                       [ 22%]
backend\tests\test_normalizer.py ..............                          [ 25%]
backend\tests\test_optimizer.py ................................         [ 33%]
backend\tests\test_optimizer_edge_cases.py ....................          [ 38%]
backend\tests\test_phase1_data_contracts.py ..................           [ 42%]
backend\tests\test_phase2_block_planner.py .............                 [ 46%]
backend\tests\test_phase3_scheduler.py ...........                       [ 48%]
backend\tests\test_phase4_cpsat_integration.py ........                  [ 50%]
backend\tests\test_phase5_ai_integration.py ............                 [ 53%]
backend\tests\test_phase5_e2e.py ...........................             [ 60%]
backend\tests\test_phase6_acceptance.py ....................             [ 65%]
backend\tests\test_phase6_priority_optimization.py ........              [ 66%]
backend\tests\test_phase7_api_integration.py ...........                 [ 69%]
backend\tests\test_phase8_system_verification.py ......................  [ 75%]
backend\tests\test_phase9_human_verification.py ........................ [ 80%]
................                                                         [ 84%]
backend\tests\test_repositories.py .....                                 [ 85%]
backend\tests\test_scheduler.py .............                            [ 89%]
backend\tests\test_seed.py ..                                            [ 89%]
backend\tests\test_validators.py ....................................... [ 99%]
....                                                                     [100%]

====================== 412 passed, 6 warnings in 41.79s =======================
```

---

## 12. Manual API Verification Walkthrough Results

Executed via [`backend/scripts/verify_phase9.py`](file:///c:/Users/kk141/source/repos/railway-block-planner/backend/scripts/verify_phase9.py) against active server:

```
======================================================================
SCENARIO A -- Process conflicts through escalation-aware resolver
======================================================================
Total conflicts: 0
Auto-resolved:   0
Requires review: 0

[OK] AUTO_RESOLVED conflicts: 0
[OK] REQUIRES_HUMAN_REVIEW conflicts: 0

======================================================================
SCENARIO B -- Conflict Review API
======================================================================
Conflicts for review: 0
All tracked conflicts: 0

======================================================================
SCENARIO C -- Plan verification lifecycle
======================================================================
Existing plans in DB: 5
Testing lifecycle with plan: OPT-PLAN-2E54536E
  [OK] Plan status API: plan_status=DRAFT
  [OK] Employee visible: False

  Submitting plan OPT-PLAN-2E54536E for review...
  [OK] DRAFT -> OPERATOR_REVIEW
  Approving plan OPT-PLAN-2E54536E...
  [OK] OPERATOR_REVIEW -> APPROVED

  Employee-facing plans (APPROVED/PUBLISHED): 1
  [OK] Plan OPT-PLAN-2E54536E is visible in employee-facing endpoint
  Publishing plan OPT-PLAN-2E54536E...
  [OK] APPROVED -> PUBLISHED

  Verifying DRAFT / OPERATOR_REVIEW plans are excluded from published endpoint...
  [OK] All 1 published plans are strictly APPROVED or PUBLISHED

```

### SCENARIO D — Forced Unresolvable Conflict Verification
Executed via [`backend/scripts/verify_scenario_d.py`](file:///c:/Users/kk141/source/repos/railway-block-planner/backend/scripts/verify_scenario_d.py):

```
===========================================================================
SCENARIO D -- Forced Unresolvable Conflict Verification
===========================================================================
[STEP 1] Created deterministic conflict in DB for date 2026-10-20:
         - Train: EXP-99999 (AJJ, 10:00-10:30)
         - Maintenance: MAIN-DET-CRIT-01 (AJJ, 09:30-11:30, Priority: Critical)

[STEP 2] Processing conflicts via POST /api/conflicts/process?target_date=2026-10-20...
         Total Conflicts Detected: 6
         Auto-Resolved:            0
         Requires Human Review:    6

[STEP 3] Verifying Conflict Lifecycle Status:
         Conflict ID: CONF-0001
         Status:      REQUIRES_HUMAN_REVIEW
         [OK] status == 'REQUIRES_HUMAN_REVIEW'

[STEP 4] Verifying Structured Unresolved Reason Fields:
         - reason_code:          CRITICAL_SEVERITY
         - explanation:          Conflict has Critical severity: Train EXP-99999 scheduled at AJJ overlaps with MaintenanceRequest MAIN-DET-CRIT-01.. Automatic resolution cannot safely override Critical conflicts without operator verification.
         - conflicting_entities: ['EXP-99999', 'MAIN-DET-CRIT-01']
         - violated_constraints: ['Severity: Critical', 'Entity 1 priority: Passenger Timetable', 'Entity 2 priority: Critical', 'AutoResolver suggestion: Shift Maintenance Block']
         [OK] reason_code exists:          'CRITICAL_SEVERITY'
         [OK] explanation exists:          'Conflict has Critical severity: Train EXP-99999 sc...'
         [OK] conflicting_entities exist:  ['EXP-99999', 'MAIN-DET-CRIT-01']
         [OK] violated_constraints exist:  ['Severity: Critical', 'Entity 1 priority: Passenger Timetable', 'Entity 2 priority: Critical', 'AutoResolver suggestion: Shift Maintenance Block']

[STEP 5] Calling GET /api/conflicts/review to inspect review queue...
         Queue items count: 6
         [OK] Conflict CONF-0001 is present in review queue with status 'REQUIRES_HUMAN_REVIEW'

[STEP 6] Resolving conflict via POST /api/conflicts/CONF-0001/resolve...

[STEP 7] Verifying Resolved Status:
         - status:        HUMAN_RESOLVED
         - reviewed_by:   chief_controller_kumar
         - review_notes:  Emergency maintenance given precedence; Train EXP-99999 held at previous junction.
         - reviewed_at:   2026-09-24T17:58:06.494043
         [OK] status == 'HUMAN_RESOLVED'
         [OK] Conflict removed from pending review queue

===========================================================================
SCENARIO D -- ALL 7 STEPS COMPLETED & VERIFIED SUCCESSFULLY [OK]
===========================================================================
```

---

## 13. Remaining Limitations & Edge Cases

1. **Conflict Store Volatility:** Active conflict review states are currently maintained in memory (`ConflictStateStore`) during operational runtime. Persistent conflict historical archiving can be added in a future phase if long-term audit trail requirements expand.
2. **Concurrent Approval Locks:** Multi-user concurrent editing of the same draft plan is currently serialized through SQLite transactions; optimistic concurrency tokens (ETags / version numbers) can be added as an operational enhancement.
3. **Frontend Implementation:** As per specifications, all UI components, screens, and employee portal dashboards will be built by the frontend team against these backend contracts.
