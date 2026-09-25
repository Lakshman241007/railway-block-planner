"""
Phase 6 — Single Priority Signal Test Suite.

Verifies that the CP-SAT optimizer uses exactly ONE priority utility term:

    if priority_value is not None:
        priority_utility = weight_priority_value × priority_value
        (categorical label is ignored for objective purposes)

    if priority_value is None:
        priority_utility = categorical legacy bonus (fallback only)

The two paths are mutually exclusive — they are never simultaneously applied.

Tests:
1. Numerical priority determines slot preference (priority_value drives selection).
2. Categorical label does NOT add objective utility when priority_value is present.
3. Priority contribution is a single term: W × priority_value, no categorical additive.
4. Hard constraints dominate priority (infeasible high-priority loses to feasible low-priority).
5. Missing numerical priority (priority_value = None) uses legacy categorical fallback.
6. Mandatory work semantics are unaffected by priority.
7. priority_value propagates end-to-end without substitution by categorical score.
8. weight_priority_value configuration linearly scales contribution.

Future factors (asset_availability_impact, operational_impact) are NOT tested here.
They remain deferred extensions.
"""

from datetime import date, time
import pytest

from backend.app.block_planner.schemas import CandidateWorkItem, DailySchedulingProblem
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.objective import compute_slot_coefficient
from backend.app.optimizer.schemas import (
    ObjectiveWeights,
    OptimizationRequest,
    OptimizationStatus,
    OptimizedBlock,
)
from backend.app.scheduler.schemas import (
    CorridorAvailabilityWindow,
    WorkBlockMatch,
    WorkMatchReport,
)
from backend.app.scheduler.scheduler import DailyScheduler
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)


@pytest.fixture
def target_date() -> date:
    return date(2026, 11, 10)


def _make_work(
    work_id: str,
    priority: Priority,
    priority_value,
    duration: int = 60,
    start: str = "02:00",
    target_date: date = date(2026, 11, 10),
    corridor: str = "Chennai-Arakkonam",
    is_mandatory: bool = False,
) -> CandidateWorkItem:
    return CandidateWorkItem(
        work_id=work_id,
        location=corridor,
        corridor=corridor,
        required_duration_minutes=duration,
        priority=priority,
        preferred_start=start,
        preferred_date=target_date,
        priority_value=priority_value,
        is_mandatory=is_mandatory,
    )


def _single_window(target_date: date, duration: int = 60, max_parallel: int = 1) -> CorridorAvailabilityWindow:
    return CorridorAvailabilityWindow(
        window_id="WIN-TEST-01",
        corridor="Chennai-Arakkonam",
        service_date=target_date,
        start_time="02:00",
        end_time=f"0{2 + duration // 60}:{duration % 60:02d}" if duration % 60 == 0 else "04:00",
        duration_minutes=duration,
        max_parallel_works=max_parallel,
        status="Available",
    )


class TestSinglePrioritySignal:
    """Core test suite proving that exactly one priority signal governs the objective."""

    # -----------------------------------------------------------------------
    # Test 1 — Numerical priority_value determines slot preference
    # -----------------------------------------------------------------------

    def test_1_numerical_priority_determines_preference(self, target_date: date):
        """
        Two works compete for one scarce slot.
        Both have the same categorical label (MEDIUM) and same duration.
        Only priority_value differs: 90 vs 40.
        The optimizer must select the higher priority_value work.
        """
        work_high = _make_work("WORK-HIGH", Priority.MEDIUM, priority_value=90.0, target_date=target_date)
        work_low  = _make_work("WORK-LOW",  Priority.MEDIUM, priority_value=40.0, target_date=target_date)

        window = _single_window(target_date, duration=60, max_parallel=1)
        problem = DailySchedulingProblem(
            problem_id="PROB-NUM-PRIO",
            target_date=target_date,
            candidate_works=[work_high, work_low],
            available_windows=[window],
        )

        result = DailyScheduler().schedule_daily(problem, invoke_solver=True)

        assert result.total_scheduled == 1
        selected = result.optimized_block_assignments[0]
        assert selected.request_id == "WORK-HIGH", (
            f"Expected WORK-HIGH (priority_value=90) to be selected, "
            f"got {selected.request_id} (priority_value={selected.priority_value})"
        )
        assert selected.priority_value == 90.0

    # -----------------------------------------------------------------------
    # Test 2 — Categorical label does NOT add utility when priority_value present
    # -----------------------------------------------------------------------

    def test_2_categorical_label_does_not_add_objective_utility(self):
        """
        Two slots with identical priority_value but different categorical labels.
        compute_slot_coefficient must return the same priority_contribution for both.

        This proves the categorical label is excluded from the objective calculation
        when priority_value is not None.
        """
        weights = ObjectiveWeights(weight_priority_value=50)

        # CRITICAL label + priority_value = 40
        meta_critical = {
            "priority": Priority.CRITICAL,
            "priority_value": 40.0,
            "start_minutes": 120,
            "preferred_start_minutes": 120,
            "fit_score": 1.0,
        }
        # LOW label + priority_value = 40 (same numerical value)
        meta_low = {
            "priority": Priority.LOW,
            "priority_value": 40.0,
            "start_minutes": 120,
            "preferred_start_minutes": 120,
            "fit_score": 1.0,
        }

        coeff_critical = compute_slot_coefficient(meta_critical, weights)
        coeff_low      = compute_slot_coefficient(meta_low,      weights)

        # Both must produce identical objective coefficients.
        # The categorical labels (CRITICAL vs LOW) must not create any difference.
        assert coeff_critical == coeff_low, (
            f"Categorical label created spurious objective difference: "
            f"CRITICAL coeff={coeff_critical}, LOW coeff={coeff_low}. "
            f"Difference={coeff_critical - coeff_low} (should be 0)."
        )

        # Verify the priority_contribution is purely numerical
        assert meta_critical["priority_contribution"] == int(round(50 * 40.0))
        assert meta_low["priority_contribution"]      == int(round(50 * 40.0))

    # -----------------------------------------------------------------------
    # Test 3 — Priority contribution is a single term: W × priority_value
    # -----------------------------------------------------------------------

    def test_3_priority_contribution_is_single_term(self):
        """
        When priority_value is present, priority_contribution must equal exactly
        weight_priority_value × priority_value — and nothing else.

        Specifically, no categorical bonus must be added on top.
        """
        weights = ObjectiveWeights(weight_priority_value=50)
        priority_value = 80.0
        expected_contribution = int(round(50 * priority_value))  # 4000

        meta = {
            "priority": Priority.CRITICAL,   # Would add 5000 under old double-counting model
            "priority_value": priority_value,
            "start_minutes": 120,
            "preferred_start_minutes": 120,
            "fit_score": 1.0,
        }

        coeff = compute_slot_coefficient(meta, weights)
        actual_contribution = meta["priority_contribution"]

        # priority_contribution must be exactly W × priority_value
        assert actual_contribution == expected_contribution, (
            f"Expected priority_contribution = {expected_contribution} "
            f"(W×priority_value = 50×80), got {actual_contribution}. "
            f"Categorical bonus must NOT be included."
        )

        # Cross-check: total coeff should NOT include the categorical Critical bonus (5000)
        # coeff = weight_scheduled(10000) + priority_contribution(4000) + no penalties = 14000
        expected_coeff = weights.weight_scheduled + expected_contribution
        assert coeff == expected_coeff, (
            f"Expected total coeff = {expected_coeff}, got {coeff}. "
            f"Categorical Critical bonus (5000) must not appear."
        )

    # -----------------------------------------------------------------------
    # Test 4 — Hard constraints dominate priority
    # -----------------------------------------------------------------------

    def test_4_hard_constraints_dominate_priority(self, target_date: date):
        """
        High priority_value work requiring 180m has NO feasible 60m window.
        Low priority_value work fits the 60m window.
        Hard constraints must win: the lower-priority work is scheduled.
        """
        work_infeasible = _make_work(
            "WORK-INFEASIBLE", Priority.CRITICAL, priority_value=99.0,
            duration=180, target_date=target_date,
        )
        work_feasible = _make_work(
            "WORK-FEASIBLE", Priority.LOW, priority_value=15.0,
            duration=60, target_date=target_date,
        )

        window = CorridorAvailabilityWindow(
            window_id="WIN-SHORT-01",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="02:00",
            end_time="03:00",
            duration_minutes=60,
            max_parallel_works=1,
            status="Available",
        )

        problem = DailySchedulingProblem(
            problem_id="PROB-HARD-CONSTRAINTS",
            target_date=target_date,
            candidate_works=[work_infeasible, work_feasible],
            available_windows=[window],
        )

        result = DailyScheduler().schedule_daily(problem, invoke_solver=True)

        assert result.total_scheduled == 1
        assert result.optimized_block_assignments[0].request_id == "WORK-FEASIBLE"

        unscheduled_ids = [u.get("work_id") for u in result.unscheduled_works]
        assert "WORK-INFEASIBLE" in unscheduled_ids

    # -----------------------------------------------------------------------
    # Test 5 — Missing priority_value uses legacy categorical fallback
    # -----------------------------------------------------------------------

    def test_5_missing_priority_value_uses_categorical_fallback(self, target_date: date):
        """
        When priority_value is None, the legacy categorical path activates.
        No numerical score is fabricated.
        Critical must still beat Low via the categorical fallback (backward compat).
        """
        work_critical = _make_work(
            "WORK-CRITICAL-NO-AI", Priority.CRITICAL, priority_value=None,
            target_date=target_date,
        )
        work_low = _make_work(
            "WORK-LOW-NO-AI", Priority.LOW, priority_value=None,
            target_date=target_date,
        )

        window = _single_window(target_date, duration=60, max_parallel=1)
        problem = DailySchedulingProblem(
            problem_id="PROB-LEGACY-COMPAT",
            target_date=target_date,
            candidate_works=[work_critical, work_low],
            available_windows=[window],
        )

        result = DailyScheduler().schedule_daily(problem, invoke_solver=True)

        assert result.total_scheduled == 1
        selected = result.optimized_block_assignments[0]
        assert selected.request_id == "WORK-CRITICAL-NO-AI"
        assert selected.priority == Priority.CRITICAL
        assert selected.priority_value is None

        # priority_contribution must be 0 (numerical path was not active)
        assert selected.priority_contribution == 0

        # Verify coefficient-level: no numerical contribution for legacy path
        weights = ObjectiveWeights()
        meta_crit = {
            "priority": Priority.CRITICAL,
            "priority_value": None,
            "start_minutes": 120, "preferred_start_minutes": 120, "fit_score": 1.0,
        }
        compute_slot_coefficient(meta_crit, weights)
        assert meta_crit["priority_contribution"] == 0  # only categorical applied, no numerical term

    # -----------------------------------------------------------------------
    # Test 6 — Mandatory work dominates priority
    # -----------------------------------------------------------------------

    def test_6_mandatory_work_dominates_priority(self, target_date: date):
        """
        Mandatory work with low priority_value must be scheduled over
        optional work with high priority_value, regardless of priority signals.
        """
        work_mandatory = _make_work(
            "WORK-MANDATORY", Priority.LOW, priority_value=10.0,
            target_date=target_date, is_mandatory=True,
        )
        work_optional_high = _make_work(
            "WORK-OPTIONAL-HIGH", Priority.HIGH, priority_value=99.0,
            target_date=target_date, is_mandatory=False,
        )

        window = _single_window(target_date, duration=60, max_parallel=1)
        problem = DailySchedulingProblem(
            problem_id="PROB-MANDATORY",
            target_date=target_date,
            candidate_works=[work_mandatory, work_optional_high],
            available_windows=[window],
        )

        result = DailyScheduler().schedule_daily(problem, invoke_solver=True)

        assert result.total_scheduled == 1
        assert result.optimized_block_assignments[0].request_id == "WORK-MANDATORY"

    # -----------------------------------------------------------------------
    # Test 7 — priority_value propagates end-to-end unchanged
    # -----------------------------------------------------------------------

    def test_7_priority_value_propagates_end_to_end(self, target_date: date):
        """
        priority_value set on CandidateWorkItem must reach OptimizedBlock unchanged.
        It must not be replaced or supplemented by a categorical-derived score.
        """
        original_priority_value = 85.0
        work = _make_work(
            "WORK-PROPAGATION", Priority.MEDIUM, priority_value=original_priority_value,
            duration=60, target_date=target_date,
        )

        window = CorridorAvailabilityWindow(
            window_id="WIN-PROP-01",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="02:00",
            end_time="04:00",
            duration_minutes=120,
            status="Available",
        )
        problem = DailySchedulingProblem(
            problem_id="PROB-PROPAGATION",
            target_date=target_date,
            candidate_works=[work],
            available_windows=[window],
        )

        result = DailyScheduler().schedule_daily(problem, invoke_solver=True)

        assert result.total_scheduled == 1
        block = result.optimized_block_assignments[0]
        assert block.priority_value == original_priority_value

        # Contribution must be exactly W × priority_value (default weight = 50)
        expected_contribution = int(round(50 * original_priority_value))  # 4250
        assert block.priority_contribution == expected_contribution, (
            f"Expected {expected_contribution}, got {block.priority_contribution}. "
            f"No categorical bonus should be included."
        )

    # -----------------------------------------------------------------------
    # Test 8 — weight_priority_value configuration linearly scales contribution
    # -----------------------------------------------------------------------

    def test_8_weight_configuration_scales_contribution_linearly(self):
        """
        Changing weight_priority_value must scale priority_contribution linearly.
        No categorical bonus must appear in either weight configuration.
        """
        priority_value = 80.0

        meta_default = {
            "priority": Priority.MEDIUM,
            "priority_value": priority_value,
            "start_minutes": 120, "preferred_start_minutes": 120, "fit_score": 1.0,
        }
        meta_boosted = {
            "priority": Priority.MEDIUM,
            "priority_value": priority_value,
            "start_minutes": 120, "preferred_start_minutes": 120, "fit_score": 1.0,
        }

        weights_default = ObjectiveWeights(weight_priority_value=50)
        weights_boosted = ObjectiveWeights(weight_priority_value=150)

        coeff_default = compute_slot_coefficient(meta_default, weights_default)
        coeff_boosted = compute_slot_coefficient(meta_boosted, weights_boosted)

        assert meta_default["priority_contribution"] == int(round(50  * priority_value))  # 4000
        assert meta_boosted["priority_contribution"] == int(round(150 * priority_value))  # 12000

        # The net coefficient difference is exactly (150 - 50) × 80 = 8000
        assert coeff_boosted - coeff_default == 8000, (
            f"Expected coefficient difference = 8000, got {coeff_boosted - coeff_default}. "
            f"Verify no categorical bonus leaked into either calculation."
        )
