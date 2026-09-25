"""
Phase 5 — AI Prioritization Integration Test Suite.

Verifies:
1. Canonical PriorityEnrichment contract validation (urgency, criticality, overdue_factor, priority_value, metadata).
   - asset_availability_impact and operational_impact are NOT part of the current contract;
     they are future extensions and are not tested here.
   - priority_value is the DERIVED result of the scorer combining the three factor fields.
     It is the single numerical optimization signal consumed by CP-SAT.
2. MaintenanceRecord enrichment and backward compatibility.
3. BlockPlanner propagation (MonthlyPlan, WeeklyPlan, DailySchedulingProblem, CandidateWorkItem).
4. DailyScheduler candidate matching (WorkBlockMatch compatibility_details["ai_priority"]).
5. OptimizationRequest passthrough (priority_overrides, candidate_works).
6. Legacy missing AI fallback (no arbitrary numbers fabricated).
7. Error handling and resilient degradation on scorer failure.
8. End-to-end pipeline execution from enriched MaintenanceRecord to DailyScheduleResult.
"""

from datetime import date, datetime, time, timezone
import pytest

from backend.app.block_planner.planner import BlockPlanner
from backend.app.block_planner.schemas import (
    CandidateWorkItem,
    DailySchedulingProblem,
    MonthlyPlan,
    WeeklyPlan,
)
from backend.app.optimizer.cp_sat_optimizer import CP_SAT_Optimizer
from backend.app.optimizer.schemas import OptimizationRequest, OptimizationStatus
from backend.app.prioritization import AIPrioritizer, PriorityEnrichment
from backend.app.scheduler.schemas import (
    CorridorAvailabilityWindow,
    DailyScheduleResult,
    WorkBlockMatch,
)
from backend.app.scheduler.scheduler import DailyScheduler, MaintenanceScheduler
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
    Priority,
)


@pytest.fixture
def target_date() -> date:
    return date(2026, 10, 20)


@pytest.fixture
def sample_enrichment() -> PriorityEnrichment:
    return PriorityEnrichment(
        urgency=0.92,
        criticality=0.88,
        overdue_factor=1.45,
        priority_value=94.5,
        metadata={"model_version": "v1-alpha", "feature_importance": {"overdue": 0.6}},
    )


@pytest.fixture
def sample_maintenance_record(target_date: date) -> MaintenanceRecord:
    return MaintenanceRecord(
        asset_id="TRK-MAS-AJJ-001",
        asset_type="Track",
        location="Chennai-Arakkonam",
        maintenance_type="Track Renewal",
        maintenance_required=True,
        priority=Priority.HIGH,
        duration_minutes=120,
        requested_date=target_date,
        preferred_start=time(2, 0),
        required_resources=3,
        equipment="Track Tamper 01",
        status=MaintenanceStatus.PENDING,
        source="smms",
    )


# ===========================================================================
# 1. Canonical PriorityEnrichment Contract
# ===========================================================================

class TestPriorityEnrichmentContract:
    def test_valid_enrichment_instantiation(self, sample_enrichment: PriorityEnrichment):
        """Verify that all currently-supported fields are accepted and stored correctly."""
        assert sample_enrichment.urgency == 0.92
        assert sample_enrichment.criticality == 0.88
        assert sample_enrichment.overdue_factor == 1.45
        assert sample_enrichment.priority_value == 94.5
        assert sample_enrichment.metadata["model_version"] == "v1-alpha"
        # Confirm that the unsupported future fields (asset_availability_impact,
        # operational_impact) are NOT present as typed attributes on the current contract.
        assert not hasattr(PriorityEnrichment.model_fields, "asset_availability_impact")
        assert not hasattr(PriorityEnrichment.model_fields, "operational_impact")

    def test_enrichment_validation_ranges(self):
        # Urgency must be between 0.0 and 1.0
        with pytest.raises(Exception):
            PriorityEnrichment(urgency=1.5, priority_value=50.0)

        with pytest.raises(Exception):
            PriorityEnrichment(criticality=-0.1, priority_value=50.0)


# ===========================================================================
# 2. MaintenanceRecord AI Enrichment
# ===========================================================================

class TestMaintenanceRecordEnrichment:
    def test_attach_enrichment_to_maintenance_record(
        self,
        sample_maintenance_record: MaintenanceRecord,
        sample_enrichment: PriorityEnrichment,
    ):
        prioritizer = AIPrioritizer()
        enriched = prioritizer.enrich_record(sample_maintenance_record, enrichment=sample_enrichment)

        assert enriched.priority_enrichment is not None
        assert enriched.priority_enrichment.priority_value == 94.5
        assert enriched.priority_value == 94.5
        # Preserves existing rule-based Priority as fallback
        assert enriched.priority == Priority.HIGH

    def test_batch_enrich_records(self, target_date: date, sample_enrichment: PriorityEnrichment):
        rec1 = MaintenanceRecord(
            asset_id="TRK-01",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.MEDIUM,
            duration_minutes=60,
            requested_date=target_date,
            preferred_start=time(1, 0),
            required_resources=1,
            equipment="Hand Tools",
            status=MaintenanceStatus.PENDING,
        )
        rec2 = MaintenanceRecord(
            asset_id="SIG-02",
            asset_type="Signal",
            location="Perambur",
            maintenance_type="Inspection",
            maintenance_required=True,
            priority=Priority.LOW,
            duration_minutes=45,
            requested_date=target_date,
            preferred_start=time(3, 0),
            required_resources=1,
            equipment="Multimeter",
            status=MaintenanceStatus.PENDING,
        )

        prioritizer = AIPrioritizer()
        results = prioritizer.enrich_records([rec1, rec2], enrichments={"TRK-01": sample_enrichment})

        assert results[0].priority_value == 94.5
        assert results[0].priority_enrichment is not None
        assert results[1].priority_value is None
        assert results[1].priority_enrichment is None


# ===========================================================================
# 3. BlockPlanner AI Priority Propagation
# ===========================================================================

class TestBlockPlannerPropagation:
    def test_monthly_and_weekly_plan_propagation(
        self,
        target_date: date,
        sample_maintenance_record: MaintenanceRecord,
        sample_enrichment: PriorityEnrichment,
    ):
        sample_maintenance_record.priority_enrichment = sample_enrichment
        sample_maintenance_record.priority_value = sample_enrichment.priority_value

        planner = BlockPlanner(maintenance_records=[sample_maintenance_record])

        monthly = planner.generate_monthly_plan(target_date=target_date)
        assert len(monthly.items) == 1
        assert monthly.items[0].priority_value == 94.5
        assert monthly.items[0].priority_enrichment is not None
        assert monthly.items[0].priority_enrichment.urgency == 0.92

        weekly = planner.generate_weekly_plan(target_date=target_date)
        assert len(weekly.items) == 1
        assert weekly.items[0].priority_value == 94.5
        assert weekly.items[0].priority_enrichment is not None

    def test_daily_problem_preparation_passes_ai_context(
        self,
        target_date: date,
        sample_maintenance_record: MaintenanceRecord,
        sample_enrichment: PriorityEnrichment,
    ):
        sample_maintenance_record.priority_enrichment = sample_enrichment
        sample_maintenance_record.priority_value = sample_enrichment.priority_value

        planner = BlockPlanner(maintenance_records=[sample_maintenance_record])
        problem = planner.prepare_daily_problem(target_date=target_date)

        assert len(problem.candidate_works) == 1
        cand = problem.candidate_works[0]
        assert cand.priority_value == 94.5
        assert cand.priority_enrichment is not None
        assert cand.ai_priority_context is not None
        assert cand.ai_priority_context["priority_value"] == 94.5
        assert cand.ai_priority_context["urgency"] == 0.92


# ===========================================================================
# 4. DailyScheduler Matching & Explainability
# ===========================================================================

class TestSchedulerCandidateMatching:
    def test_match_work_to_blocks_records_ai_details(
        self,
        target_date: date,
        sample_enrichment: PriorityEnrichment,
    ):
        work = CandidateWorkItem(
            work_id="MNT-TRK-MAS-AJJ-001",
            location="Chennai-Arakkonam",
            required_duration_minutes=90,
            priority=Priority.HIGH,
            preferred_start="02:00",
            preferred_date=target_date,
            priority_value=94.5,
            priority_enrichment=sample_enrichment,
        )
        window = CorridorAvailabilityWindow(
            window_id="WIN-NIGHT-01",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="01:30",
            end_time="03:30",
            duration_minutes=120,
            status="Available",
        )

        scheduler = DailyScheduler()
        from backend.app.scheduler.schemas import DailyAvailabilityReport

        avail = DailyAvailabilityReport(
            report_id="AVAIL-TEST",
            target_date=target_date,
            generated_at=datetime.now(timezone.utc).isoformat(),
            available_windows=[window],
        )

        match_rep = scheduler.match_work_to_blocks([work], avail)
        assert match_rep.total_matches == 1
        match = match_rep.successful_matches[0]
        assert match.priority_value == 94.5
        assert match.priority_enrichment is not None
        assert "ai_priority" in match.compatibility_details
        assert match.compatibility_details["ai_priority"]["urgency"] == 0.92
        assert match.compatibility_details["ai_priority"]["priority_value"] == 94.5


# ===========================================================================
# 5. OptimizationRequest Passthrough
# ===========================================================================

class TestOptimizationRequestPassthrough:
    def test_build_cpsat_input_transfers_numeric_priority(
        self,
        target_date: date,
        sample_enrichment: PriorityEnrichment,
    ):
        work = CandidateWorkItem(
            work_id="WORK-AI-01",
            location="Chennai-Arakkonam",
            required_duration_minutes=60,
            priority=Priority.MEDIUM,
            priority_value=94.5,
            priority_enrichment=sample_enrichment,
        )
        problem = DailySchedulingProblem(
            problem_id="PROB-TEST-AI",
            target_date=target_date,
            candidate_works=[work],
            available_windows=[],
        )
        from backend.app.scheduler.schemas import WorkMatchReport

        match_rep = WorkMatchReport(
            report_id="REP-01",
            target_date=target_date,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        scheduler = DailyScheduler()
        opt_req = scheduler.build_cpsat_input(problem, match_rep)

        assert opt_req.priority_overrides is not None
        assert opt_req.priority_overrides["WORK-AI-01"] == "94.5"
        assert opt_req.candidate_works is not None
        assert opt_req.candidate_works[0].priority_value == 94.5


# ===========================================================================
# 6. Legacy Missing AI Fallback (No Fabricated Defaults)
# ===========================================================================

class TestLegacyMissingAIFallback:
    def test_unassigned_records_never_fabricate_arbitrary_scores(
        self,
        sample_maintenance_record: MaintenanceRecord,
    ):
        prioritizer = AIPrioritizer()
        # No enrichment passed
        result = prioritizer.enrich_record(sample_maintenance_record, enrichment=None)

        # Must remain None - NEVER fabricate priority_value = 50.0
        assert result.priority_value is None
        assert result.priority_enrichment is None
        # Rule-based priority untouched
        assert result.priority == Priority.HIGH

    def test_planner_without_ai_falls_back_gracefully(self, target_date: date):
        legacy_rec = MaintenanceRecord(
            asset_id="LEGACY-TRK-01",
            asset_type="Track",
            location="Chennai-Arakkonam",
            maintenance_type="Preventive",
            maintenance_required=True,
            priority=Priority.HIGH,
            duration_minutes=60,
            requested_date=target_date,
            preferred_start=time(2, 0),
            required_resources=2,
            equipment="Tamper",
            status=MaintenanceStatus.PENDING,
        )
        planner = BlockPlanner(maintenance_records=[legacy_rec])
        prob = planner.prepare_daily_problem(target_date=target_date)

        assert prob.candidate_works[0].priority_value is None
        assert prob.candidate_works[0].priority_enrichment is None
        assert prob.candidate_works[0].priority == Priority.HIGH


# ===========================================================================
# 7. Resilient Degradation & Error Handling
# ===========================================================================

class TestAIPrioritizerErrorHandling:
    def test_scorer_exception_does_not_crash_pipeline(
        self,
        sample_maintenance_record: MaintenanceRecord,
    ):
        def failing_scorer(rec: MaintenanceRecord):
            raise RuntimeError("Model service connection timeout / GPU out of memory")

        prioritizer = AIPrioritizer(scorer=failing_scorer)
        # Should gracefully catch exception, log warning, and leave priority_value None
        res = prioritizer.enrich_record(sample_maintenance_record)

        assert res.priority_value is None
        assert res.priority_enrichment is None
        assert res.priority == Priority.HIGH


# ===========================================================================
# 8. End-to-End Pipeline Execution
# ===========================================================================

class TestPhase5EndToEndPipeline:
    def test_full_pipeline_from_enriched_maint_to_daily_schedule_result(
        self,
        target_date: date,
        sample_maintenance_record: MaintenanceRecord,
        sample_enrichment: PriorityEnrichment,
    ):
        # 1. Enrich maintenance record
        prioritizer = AIPrioritizer()
        enriched_rec = prioritizer.enrich_record(sample_maintenance_record, enrichment=sample_enrichment)

        # 2. Block planner organizes daily problem
        planner = BlockPlanner(maintenance_records=[enriched_rec])
        problem = planner.prepare_daily_problem(target_date=target_date)

        # Provide a matching available window
        window = CorridorAvailabilityWindow(
            window_id="WIN-MAS-AJJ-0100",
            corridor="Chennai-Arakkonam",
            service_date=target_date,
            start_time="01:00",
            end_time="04:00",
            duration_minutes=180,
            status="Available",
        )
        problem.available_windows.append(window)

        # 3. Daily Scheduler coordinates matching and CP-SAT execution
        scheduler = DailyScheduler(maintenance_records=[enriched_rec])
        result = scheduler.schedule_daily(problem, invoke_solver=True)

        assert isinstance(result, DailyScheduleResult)
        assert result.total_scheduled == 1
        assert "ai_prioritization_summary" in result.diagnostics
        assert result.diagnostics["ai_prioritization_summary"]["ai_enriched_works"] == 1

        sched_block = result.optimized_block_assignments[0]
        assert sched_block.priority_value == 94.5
        assert sched_block.priority_enrichment is not None
        assert sched_block.priority_enrichment.urgency == 0.92
