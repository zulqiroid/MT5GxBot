import hashlib
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.analysis_pipeline import (
    MultiTimeframeAnalysisPipeline,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderIntentBlueprintFactory,
    StrategyOrderSide,
)
from app.strategy.order_intent_execution_lock import (
    StrategyExecutionBoundaryLockFactory,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8DryRunFoundationError,
    Phase8DryRunPackage,
    Phase8DryRunPackageReason,
    Phase8DryRunPackageStatus,
    Phase8DryRunScenario,
    Phase8DryRunScenarioBlocker,
    Phase8DryRunScenarioReason,
    Phase8DryRunScenarioStatus,
    Phase8Handoff,
    Phase8HandoffBlocker,
    Phase8HandoffReason,
    Phase8HandoffStatus,
    Phase8MarketDataMode,
    Phase8RunMode,
    Phase8SimulationAdmission,
    Phase8SimulationAdmissionBlocker,
    Phase8SimulationAdmissionReason,
    Phase8SimulationAdmissionStatus,
    Phase8Timeframe,
    StrategyPhase8DryRunPackage,
    StrategyPhase8DryRunPackageFactory,
    StrategyPhase8DryRunScenario,
    StrategyPhase8DryRunScenarioFactory,
    StrategyPhase8Handoff,
    StrategyPhase8HandoffFactory,
    StrategyPhase8SimulationAdmission,
    StrategyPhase8SimulationAdmissionGate,
    build_phase8_dry_run_foundation,
)
from app.strategy.planning_audit_export import (
    StrategyPlanningAuditExportFactory,
)
from app.strategy.planning_audit_final_bundle import (
    StrategyPlanningAuditFinalBundleFactory,
)
from app.strategy.planning_audit_manifest import (
    StrategyPlanningAuditManifestFactory,
)
from app.strategy.planning_audit_persistence_completion import (
    StrategyPlanningAuditPersistenceCompletionFactory,
)
from app.strategy.planning_audit_persistence_outcome_contract import (
    PlanningAuditPersistenceOutcomeKind,
    StrategyPlanningAuditPersistenceOutcomeContractFactory,
)
from app.strategy.planning_audit_persistence_outcome_evidence import (
    PlanningAuditPersistenceOutcomeEvidenceSnapshot,
    StrategyPlanningAuditPersistenceOutcomeEvidenceGate,
)
from app.strategy.planning_audit_persistence_outcome_receipt import (
    StrategyPlanningAuditPersistenceOutcomeReceiptFactory,
)
from app.strategy.planning_audit_persistence_request import (
    StrategyPlanningAuditPersistenceRequestFactory,
)
from app.strategy.planning_audit_persistence_request_verification import (
    StrategyPlanningAuditPersistenceRequestVerificationFactory,
)
from app.strategy.planning_audit_record import (
    StrategyPlanningAuditRecordFactory,
)
from app.strategy.planning_audit_storage_adapter_assessment import (
    PlanningAuditStorageAdapterCapability,
    PlanningAuditStorageAdapterCapabilitySnapshot,
    StrategyPlanningAuditStorageAdapterAssessmentGate,
)
from app.strategy.planning_audit_storage_adapter_binding import (
    StrategyPlanningAuditStorageAdapterBindingFactory,
)
from app.strategy.planning_audit_storage_adapter_binding_verification import (
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory,
)
from app.strategy.planning_audit_storage_adapter_contract import (
    StrategyPlanningAuditStorageAdapterContractFactory,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageSnapshot,
    PlanningAuditStorageTarget,
    StrategyPlanningAuditStorageAdmissionGate,
)
from app.strategy.planning_audit_storage_blueprint import (
    StrategyPlanningAuditStorageBlueprintFactory,
)
from app.strategy.planning_audit_verification import (
    StrategyPlanningAuditVerificationFactory,
)
from app.strategy.planning_package import (
    StrategyPlanningPackageFactory,
)
from app.strategy.position_size_calculation import (
    StrategyPositionSizeCalculator,
)
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoffDecision,
    StrategyPositionSizingHandoffFactory,
)
from app.strategy.position_sizing_specification import (
    PositionSizingSpecification,
    StrategyPositionSizingSpecificationGate,
)
from app.strategy.price_planning_admission import (
    StrategyPricePlanningAdmissionGate,
)
from app.strategy.price_planning_blueprint import (
    StrategyPricePlanningBlueprintFactory,
)
from app.strategy.price_reference_availability import (
    PriceReferenceAvailabilityItem,
    PriceReferenceAvailabilitySnapshot,
    StrategyPriceReferenceAvailabilityGate,
)
from app.strategy.price_reference_plan import (
    PriceReferenceRole,
    StrategyPriceReferencePlanFactory,
)
from app.strategy.price_reference_resolution import (
    PriceReferenceValueObservation,
    PriceReferenceValueSnapshot,
    StrategyPriceReferenceResolutionGate,
)
from app.strategy.reward_risk_analysis import (
    StrategyRewardRiskAnalysisGate,
)
from app.strategy.risk_budget_admission import (
    StrategyRiskBudgetAdmissionGate,
    StrategyRiskBudgetSnapshot,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidateFactory,
)
from app.strategy.setup_candidate_quality import (
    StrategySetupCandidateQualityGate,
)
from app.strategy.setup_qualification import (
    StrategySetupQualificationGate,
)
from app.strategy.sized_trade_plan import (
    StrategySizedTradePlanFactory,
)

OBSERVED_AT = datetime(
    2026,
    7,
    26,
    20,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    count: int = 8,
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    first_open = OBSERVED_AT - duration * count
    candles: list[ClosedCandle] = []

    for index in range(count):
        open_time = first_open + duration * index

        if index % 2 == 0:
            open_price = Decimal("100")
            close_price = Decimal("101")
        else:
            open_price = Decimal("101")
            close_price = Decimal("100")

        candles.append(
            ClosedCandle(
                broker_symbol="XAUUSDm",
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=open_price,
                high=Decimal("102"),
                low=Decimal("98"),
                close=close_price,
                tick_volume=1000,
                spread=20,
                real_volume=0,
            )
        )

    return ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=timeframe,
        candles=tuple(candles),
    )


@lru_cache(maxsize=1)
def neutral_context():
    mapping = {timeframe: create_series(timeframe) for timeframe in GOLD_TIMEFRAME_HIERARCHY}

    return MultiTimeframeContextBuilder().build(mapping)


def handoff_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
) -> PositionSizingHandoffDecision:
    if direction == DirectionalPermissionDirection.BULLISH:
        selected_bias = MarketStructureBias.BULLISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2340")
        target_value = Decimal("2370")
    elif direction == DirectionalPermissionDirection.BEARISH:
        selected_bias = MarketStructureBias.BEARISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2360")
        target_value = Decimal("2325")
    else:
        raise ValueError("Direction must be resolved.")

    context = replace(
        neutral_context(),
        structure_biases=tuple(
            (
                timeframe,
                (
                    selected_bias
                    if timeframe
                    in {
                        TimeframeName.H4,
                        TimeframeName.H1,
                        TimeframeName.M15,
                    }
                    else MarketStructureBias.NEUTRAL
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )
    analysis = MultiTimeframeAnalysisPipeline().evaluate_context(context)
    qualification = StrategySetupQualificationGate().evaluate(analysis)
    candidate = StrategySetupCandidateFactory().generate(qualification).candidate_required
    quality = StrategySetupCandidateQualityGate().evaluate(candidate)
    admission = StrategyPricePlanningAdmissionGate().evaluate(quality)
    blueprint = StrategyPricePlanningBlueprintFactory().generate(admission)
    plan_decision = StrategyPriceReferencePlanFactory().generate(blueprint)
    plan = plan_decision.plan_required
    availability = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        PriceReferenceAvailabilitySnapshot(
            plan=plan,
            items=tuple(
                PriceReferenceAvailabilityItem(
                    requirement=requirement,
                    available=True,
                )
                for requirement in plan.requirements
            ),
        ),
    )
    values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    resolution = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=tuple(
                PriceReferenceValueObservation(
                    requirement=requirement,
                    value=values[requirement.role],
                )
                for requirement in (
                    availability.selected_entry,
                    availability.selected_stop,
                    availability.selected_target,
                )
                if requirement is not None
            ),
        ),
    )
    reward_risk = StrategyRewardRiskAnalysisGate().evaluate(resolution)
    risk_admission = StrategyRiskBudgetAdmissionGate().evaluate(
        reward_risk,
        StrategyRiskBudgetSnapshot(
            observed_at=OBSERVED_AT,
            account_equity=Decimal("10000"),
            proposed_risk_amount=Decimal("100"),
            current_aggregate_risk_amount=Decimal("0"),
            realized_daily_loss_amount=Decimal("0"),
            open_gold_positions=0,
            kill_switch_active=blocked,
        ),
    )

    return StrategyPositionSizingHandoffFactory().generate(risk_admission)


@lru_cache(maxsize=1)
def bullish_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def sizing_specification(
    *,
    observed_at: datetime = OBSERVED_AT,
    broker_symbol: str = "XAUUSDm",
    digits: int = 2,
    point_size: Decimal = Decimal("0.01"),
    tick_size: Decimal = Decimal("0.01"),
    tick_value: Decimal = Decimal("1"),
    contract_size: Decimal = Decimal("100"),
    volume_min: Decimal = Decimal("0.01"),
    volume_max: Decimal = Decimal("100"),
    volume_step: Decimal = Decimal("0.01"),
) -> PositionSizingSpecification:
    return PositionSizingSpecification(
        observed_at=observed_at,
        broker_symbol=broker_symbol,
        digits=digits,
        point_size=point_size,
        tick_size=tick_size,
        tick_value=tick_value,
        contract_size=contract_size,
        volume_min=volume_min,
        volume_max=volume_max,
        volume_step=volume_step,
    )


def specification_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
    tick_size: Decimal = Decimal("0.01"),
    tick_value: Decimal = Decimal("1"),
    volume_min: Decimal = Decimal("0.01"),
    volume_max: Decimal = Decimal("100"),
    volume_step: Decimal = Decimal("0.01"),
):
    handoff = (
        blocked_handoff()
        if blocked
        else (
            bullish_handoff()
            if direction == DirectionalPermissionDirection.BULLISH
            else bearish_handoff()
        )
    )
    gate = StrategyPositionSizingSpecificationGate()

    if blocked:
        return gate.evaluate(handoff)

    return gate.evaluate(
        handoff,
        sizing_specification(
            tick_size=tick_size,
            tick_value=tick_value,
            volume_min=volume_min,
            volume_max=volume_max,
            volume_step=volume_step,
        ),
    )


@lru_cache(maxsize=1)
def bullish_specification_decision():
    return specification_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_specification_decision():
    return specification_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_specification_decision():
    return specification_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


@lru_cache(maxsize=1)
def bullish_calculation():
    return StrategyPositionSizeCalculator().calculate(bullish_specification_decision())


@lru_cache(maxsize=1)
def bearish_calculation():
    return StrategyPositionSizeCalculator().calculate(bearish_specification_decision())


@lru_cache(maxsize=1)
def blocked_calculation():
    return StrategyPositionSizeCalculator().calculate(blocked_specification_decision())


@lru_cache(maxsize=1)
def bullish_sized_plan():
    return StrategySizedTradePlanFactory().generate(bullish_calculation())


@lru_cache(maxsize=1)
def bearish_sized_plan():
    return StrategySizedTradePlanFactory().generate(bearish_calculation())


@lru_cache(maxsize=1)
def blocked_sized_plan():
    return StrategySizedTradePlanFactory().generate(blocked_calculation())


@lru_cache(maxsize=1)
def bullish_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())


@lru_cache(maxsize=1)
def bearish_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(bearish_sized_plan())


@lru_cache(maxsize=1)
def blocked_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())


@lru_cache(maxsize=1)
def bullish_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())


@lru_cache(maxsize=1)
def bearish_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(bearish_order_intent())


@lru_cache(maxsize=1)
def blocked_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())


@lru_cache(maxsize=1)
def bullish_planning_package():
    return StrategyPlanningPackageFactory().generate(bullish_execution_lock())


@lru_cache(maxsize=1)
def bearish_planning_package():
    return StrategyPlanningPackageFactory().generate(bearish_execution_lock())


@lru_cache(maxsize=1)
def blocked_planning_package():
    return StrategyPlanningPackageFactory().generate(blocked_execution_lock())


@lru_cache(maxsize=1)
def bullish_audit_manifest():
    return StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())


@lru_cache(maxsize=1)
def bearish_audit_manifest():
    return StrategyPlanningAuditManifestFactory().generate(bearish_planning_package())


@lru_cache(maxsize=1)
def blocked_audit_manifest():
    return StrategyPlanningAuditManifestFactory().generate(blocked_planning_package())


@lru_cache(maxsize=1)
def bullish_audit_record():
    return StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())


@lru_cache(maxsize=1)
def bearish_audit_record():
    return StrategyPlanningAuditRecordFactory().generate(bearish_audit_manifest())


@lru_cache(maxsize=1)
def blocked_audit_record():
    return StrategyPlanningAuditRecordFactory().generate(blocked_audit_manifest())


@lru_cache(maxsize=1)
def bullish_audit_export():
    return StrategyPlanningAuditExportFactory().generate(bullish_audit_record())


@lru_cache(maxsize=1)
def bearish_audit_export():
    return StrategyPlanningAuditExportFactory().generate(bearish_audit_record())


@lru_cache(maxsize=1)
def blocked_audit_export():
    return StrategyPlanningAuditExportFactory().generate(blocked_audit_record())


@lru_cache(maxsize=1)
def bullish_verification():
    return StrategyPlanningAuditVerificationFactory().verify(bullish_audit_export())


@lru_cache(maxsize=1)
def bearish_verification():
    return StrategyPlanningAuditVerificationFactory().verify(bearish_audit_export())


@lru_cache(maxsize=1)
def blocked_verification():
    return StrategyPlanningAuditVerificationFactory().verify(blocked_audit_export())


def storage_snapshot(
    *,
    observed_at: datetime = OBSERVED_AT,
    target: PlanningAuditStorageTarget = (PlanningAuditStorageTarget.AUDIT_ARCHIVE),
    storage_enabled: bool = True,
    encryption_at_rest: bool = True,
    append_only: bool = True,
    idempotency_supported: bool = True,
    retention_days: int = 365,
    available_capacity_bytes: int = 1_000_000,
) -> PlanningAuditStorageSnapshot:
    return PlanningAuditStorageSnapshot(
        observed_at=observed_at,
        target=target,
        storage_enabled=storage_enabled,
        encryption_at_rest=encryption_at_rest,
        append_only=append_only,
        idempotency_supported=idempotency_supported,
        retention_days=retention_days,
        available_capacity_bytes=(available_capacity_bytes),
    )


@lru_cache(maxsize=1)
def bullish_storage_admission():
    return StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )


@lru_cache(maxsize=1)
def bearish_storage_admission():
    return StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bearish_verification(),
        storage_snapshot(),
    )


@lru_cache(maxsize=1)
def blocked_storage_admission():
    return StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(storage_enabled=False),
    )


@lru_cache(maxsize=1)
def bullish_storage_blueprint():
    return StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())


@lru_cache(maxsize=1)
def bearish_storage_blueprint():
    return StrategyPlanningAuditStorageBlueprintFactory().generate(bearish_storage_admission())


@lru_cache(maxsize=1)
def blocked_storage_blueprint():
    return StrategyPlanningAuditStorageBlueprintFactory().generate(blocked_storage_admission())


@lru_cache(maxsize=1)
def bullish_adapter_contract():
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )


@lru_cache(maxsize=1)
def bearish_adapter_contract():
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bearish_storage_blueprint()
    )


@lru_cache(maxsize=1)
def blocked_adapter_contract():
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(
        blocked_storage_blueprint()
    )


def capability_snapshot(
    *,
    observed_at: datetime = OBSERVED_AT,
    adapter_name: str = "injected-audit-adapter",
    target: PlanningAuditStorageTarget = (PlanningAuditStorageTarget.AUDIT_ARCHIVE),
    active: bool = True,
    invocation_enabled: bool = False,
    capabilities: tuple[
        PlanningAuditStorageAdapterCapability,
        ...,
    ] = (
        PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
        PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
        PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
        PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
        PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
        PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
        PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
    ),
    maximum_payload_bytes: int = 1_000_000,
    maximum_retention_days: int = 3650,
) -> PlanningAuditStorageAdapterCapabilitySnapshot:
    return PlanningAuditStorageAdapterCapabilitySnapshot(
        observed_at=observed_at,
        adapter_name=adapter_name,
        target=target,
        active=active,
        invocation_enabled=invocation_enabled,
        capabilities=capabilities,
        maximum_payload_bytes=maximum_payload_bytes,
        maximum_retention_days=maximum_retention_days,
    )


@lru_cache(maxsize=1)
def bullish_adapter_assessment():
    return StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )


@lru_cache(maxsize=1)
def bearish_adapter_assessment():
    return StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bearish_adapter_contract(),
        capability_snapshot(),
    )


@lru_cache(maxsize=1)
def blocked_adapter_assessment():
    return StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(active=False),
    )


@lru_cache(maxsize=1)
def bullish_adapter_binding():
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )


@lru_cache(maxsize=1)
def bearish_adapter_binding():
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bearish_adapter_assessment()
    )


@lru_cache(maxsize=1)
def blocked_adapter_binding():
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        blocked_adapter_assessment()
    )


@lru_cache(maxsize=1)
def bullish_binding_verification():
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )


@lru_cache(maxsize=1)
def bearish_binding_verification():
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bearish_adapter_binding()
    )


@lru_cache(maxsize=1)
def blocked_binding_verification():
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        blocked_adapter_binding()
    )


@lru_cache(maxsize=1)
def bullish_persistence_request():
    return StrategyPlanningAuditPersistenceRequestFactory().generate(bullish_binding_verification())


@lru_cache(maxsize=1)
def bearish_persistence_request():
    return StrategyPlanningAuditPersistenceRequestFactory().generate(bearish_binding_verification())


@lru_cache(maxsize=1)
def blocked_persistence_request():
    return StrategyPlanningAuditPersistenceRequestFactory().generate(blocked_binding_verification())


@lru_cache(maxsize=1)
def bullish_request_verification():
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(
        bullish_persistence_request()
    )


@lru_cache(maxsize=1)
def bearish_request_verification():
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(
        bearish_persistence_request()
    )


@lru_cache(maxsize=1)
def blocked_request_verification():
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(
        blocked_persistence_request()
    )


@lru_cache(maxsize=1)
def bullish_outcome_contract():
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )


@lru_cache(maxsize=1)
def bearish_outcome_contract():
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bearish_request_verification()
    )


@lru_cache(maxsize=1)
def blocked_outcome_contract():
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        blocked_request_verification()
    )


def outcome_evidence(
    contract_decision=None,
    *,
    observed_at=OBSERVED_AT,
    source_name="external-audit-store",
    outcome_kind=(PlanningAuditPersistenceOutcomeKind.CREATED),
    storage_record_reference="AUDIT-RECORD-0001",
    request_id=None,
    request_digest=None,
    content_length_bytes=None,
    content_digest=None,
    manifest_digest=None,
    idempotency_key=None,
    binding_receipt_digest=None,
    binding_id=None,
    snapshot_id=None,
    contract_id=None,
):
    selected = contract_decision or bullish_outcome_contract()
    contract = selected.contract_required

    return PlanningAuditPersistenceOutcomeEvidenceSnapshot.create(
        observed_at=observed_at,
        source_name=source_name,
        target=contract.target,
        outcome_kind=outcome_kind,
        storage_record_reference=(storage_record_reference),
        request_id=(request_id or contract.expected_request_id),
        request_digest=(request_digest or contract.expected_request_digest),
        content_length_bytes=(
            content_length_bytes
            if content_length_bytes is not None
            else (contract.expected_content_length_bytes)
        ),
        content_digest=(content_digest or contract.expected_content_digest),
        manifest_digest=(manifest_digest or contract.expected_manifest_digest),
        idempotency_key=(idempotency_key or contract.expected_idempotency_key),
        binding_receipt_digest=(
            binding_receipt_digest or (contract.expected_binding_receipt_digest)
        ),
        binding_id=(binding_id or contract.expected_binding_id),
        snapshot_id=(snapshot_id or contract.expected_snapshot_id),
        contract_id=(contract_id or contract.expected_contract_id),
    )


@lru_cache(maxsize=1)
def bullish_outcome_evidence_decision():
    return StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )


@lru_cache(maxsize=1)
def existing_outcome_evidence_decision():
    evidence = outcome_evidence(
        outcome_kind=(PlanningAuditPersistenceOutcomeKind.EXISTING),
        storage_record_reference=("AUDIT-RECORD-EXISTING-0001"),
    )

    return StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        evidence,
    )


@lru_cache(maxsize=1)
def bearish_outcome_evidence_decision():
    contract = bearish_outcome_contract()

    return StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        contract,
        outcome_evidence(contract),
    )


@lru_cache(maxsize=1)
def blocked_outcome_evidence_decision():
    return StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(request_id="foreign-request"),
    )


@lru_cache(maxsize=1)
def bullish_outcome_receipt():
    return StrategyPlanningAuditPersistenceOutcomeReceiptFactory().generate(
        bullish_outcome_evidence_decision()
    )


@lru_cache(maxsize=1)
def existing_outcome_receipt():
    return StrategyPlanningAuditPersistenceOutcomeReceiptFactory().generate(
        existing_outcome_evidence_decision()
    )


@lru_cache(maxsize=1)
def bearish_outcome_receipt():
    return StrategyPlanningAuditPersistenceOutcomeReceiptFactory().generate(
        bearish_outcome_evidence_decision()
    )


@lru_cache(maxsize=1)
def blocked_outcome_receipt():
    return StrategyPlanningAuditPersistenceOutcomeReceiptFactory().generate(
        blocked_outcome_evidence_decision()
    )


@lru_cache(maxsize=1)
def bullish_persistence_completion():
    return StrategyPlanningAuditPersistenceCompletionFactory().generate(bullish_outcome_receipt())


@lru_cache(maxsize=1)
def existing_persistence_completion():
    return StrategyPlanningAuditPersistenceCompletionFactory().generate(existing_outcome_receipt())


@lru_cache(maxsize=1)
def bearish_persistence_completion():
    return StrategyPlanningAuditPersistenceCompletionFactory().generate(bearish_outcome_receipt())


@lru_cache(maxsize=1)
def blocked_persistence_completion():
    return StrategyPlanningAuditPersistenceCompletionFactory().generate(blocked_outcome_receipt())


@lru_cache(maxsize=1)
def bullish_final_bundle_decision():
    return StrategyPlanningAuditFinalBundleFactory().generate(bullish_persistence_completion())


@lru_cache(maxsize=1)
def existing_final_bundle_decision():
    return StrategyPlanningAuditFinalBundleFactory().generate(existing_persistence_completion())


@lru_cache(maxsize=1)
def bearish_final_bundle_decision():
    return StrategyPlanningAuditFinalBundleFactory().generate(bearish_persistence_completion())


@lru_cache(maxsize=1)
def blocked_final_bundle_decision():
    return StrategyPlanningAuditFinalBundleFactory().generate(blocked_persistence_completion())


@lru_cache(maxsize=1)
def bullish_handoff_decision():
    return StrategyPhase8HandoffFactory().generate(bullish_final_bundle_decision())


@lru_cache(maxsize=1)
def blocked_handoff_decision():
    return StrategyPhase8HandoffFactory().generate(blocked_final_bundle_decision())


@lru_cache(maxsize=1)
def bullish_scenario_decision():
    return StrategyPhase8DryRunScenarioFactory().generate(bullish_handoff_decision())


@lru_cache(maxsize=1)
def blocked_scenario_decision():
    return StrategyPhase8DryRunScenarioFactory().generate(blocked_handoff_decision())


@lru_cache(maxsize=1)
def bullish_admission_decision():
    return StrategyPhase8SimulationAdmissionGate().assess(bullish_scenario_decision())


@lru_cache(maxsize=1)
def blocked_admission_decision():
    return StrategyPhase8SimulationAdmissionGate().assess(blocked_scenario_decision())


def test_invalid_final_bundle_is_fail_safe() -> None:
    with pytest.raises(
        Phase8DryRunFoundationError,
        match="INVALID_FINAL_BUNDLE_DECISION",
    ):
        StrategyPhase8HandoffFactory().generate("invalid")


def test_bullish_handoff_is_created() -> None:
    decision = bullish_handoff_decision()

    assert decision.status == Phase8HandoffStatus.CREATED
    assert decision.reason == Phase8HandoffReason.CREATED
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.handoff is not None


def test_bearish_handoff_is_created() -> None:
    decision = StrategyPhase8HandoffFactory().generate(bearish_final_bundle_decision())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.handoff_required.side == StrategyOrderSide.SELL


def test_existing_outcome_handoff_is_created() -> None:
    decision = StrategyPhase8HandoffFactory().generate(existing_final_bundle_decision())

    assert decision.is_created is True
    assert decision.handoff_required.outcome_kind == (PlanningAuditPersistenceOutcomeKind.EXISTING)


def test_blocked_final_bundle_blocks_handoff() -> None:
    decision = blocked_handoff_decision()

    assert decision.is_blocked is True
    assert decision.handoff is None
    assert decision.reason == (Phase8HandoffReason.FINAL_BUNDLE_BLOCKED)
    assert decision.blockers == (Phase8HandoffBlocker.FINAL_BUNDLE_BLOCKED,)


def test_handoff_preserves_final_bundle() -> None:
    handoff = bullish_handoff_decision().handoff_required
    bundle = bullish_final_bundle_decision().bundle_required

    assert handoff.final_bundle is bundle
    assert handoff.final_bundle_id == bundle.stable_id
    assert handoff.final_bundle_digest == (bundle.bundle_digest)
    assert handoff.broker_symbol == bundle.broker_symbol
    assert handoff.direction == bundle.direction
    assert handoff.side == bundle.side


def test_handoff_digest_is_deterministic() -> None:
    handoff = bullish_handoff_decision().handoff_required
    expected = hashlib.sha256(handoff.canonical_payload.encode("utf-8")).hexdigest()

    assert handoff.handoff_digest == expected


def test_invalid_handoff_is_fail_safe() -> None:
    with pytest.raises(
        Phase8DryRunFoundationError,
        match="INVALID_HANDOFF_DECISION",
    ):
        StrategyPhase8DryRunScenarioFactory().generate("invalid")


def test_bullish_scenario_is_created() -> None:
    decision = bullish_scenario_decision()

    assert decision.status == (Phase8DryRunScenarioStatus.CREATED)
    assert decision.reason == (Phase8DryRunScenarioReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True


def test_blocked_handoff_blocks_scenario() -> None:
    decision = blocked_scenario_decision()

    assert decision.is_blocked is True
    assert decision.scenario is None
    assert decision.reason == (Phase8DryRunScenarioReason.HANDOFF_BLOCKED)
    assert decision.blockers == (Phase8DryRunScenarioBlocker.HANDOFF_BLOCKED,)


def test_scenario_is_simulation_only() -> None:
    scenario = bullish_scenario_decision().scenario_required

    assert scenario.run_mode == (Phase8RunMode.SIMULATION_ONLY)
    assert scenario.is_executable is False
    assert scenario.execution_authorized is False


def test_scenario_uses_closed_candles_only() -> None:
    scenario = bullish_scenario_decision().scenario_required

    assert scenario.market_data_mode == (Phase8MarketDataMode.CLOSED_CANDLES_ONLY)
    assert scenario.uses_closed_candles_only is True


def test_scenario_timeframes_are_exact() -> None:
    scenario = bullish_scenario_decision().scenario_required

    assert scenario.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )
    assert scenario.uses_required_timeframes is True


def test_scenario_is_gold_only() -> None:
    scenario = bullish_scenario_decision().scenario_required

    assert scenario.broker_symbol.upper().startswith("XAUUSD")


def test_scenario_does_not_initialize_mt5() -> None:
    scenario = bullish_scenario_decision().scenario_required

    assert scenario.initializes_mt5 is False


def test_scenario_digest_is_deterministic() -> None:
    scenario = bullish_scenario_decision().scenario_required
    expected = hashlib.sha256(scenario.canonical_payload.encode("utf-8")).hexdigest()

    assert scenario.scenario_digest == expected


def test_invalid_scenario_is_fail_safe() -> None:
    with pytest.raises(
        Phase8DryRunFoundationError,
        match="INVALID_SCENARIO_DECISION",
    ):
        (StrategyPhase8SimulationAdmissionGate().assess("invalid"))


def test_simulation_is_admitted() -> None:
    decision = bullish_admission_decision()

    assert decision.status == (Phase8SimulationAdmissionStatus.ADMITTED)
    assert decision.reason == (Phase8SimulationAdmissionReason.ADMITTED)
    assert decision.blockers == ()
    assert decision.is_admitted is True


def test_blocked_scenario_blocks_admission() -> None:
    decision = blocked_admission_decision()

    assert decision.is_blocked is True
    assert decision.admission is None
    assert decision.reason == (Phase8SimulationAdmissionReason.SCENARIO_BLOCKED)
    assert decision.blockers == (Phase8SimulationAdmissionBlocker.SCENARIO_BLOCKED,)


def test_admission_preserves_scenario() -> None:
    admission = bullish_admission_decision().admission_required
    scenario = bullish_scenario_decision().scenario_required

    assert admission.scenario is scenario
    assert admission.scenario_id == scenario.stable_id
    assert admission.scenario_digest == (scenario.scenario_digest)


def test_admission_digest_is_deterministic() -> None:
    admission = bullish_admission_decision().admission_required

    assert len(admission.admission_digest) == 64
    assert admission.admission_digest == (admission.admission_digest.lower())


def test_admission_does_not_initialize_mt5() -> None:
    admission = bullish_admission_decision().admission_required

    assert admission.initializes_mt5 is False


def test_invalid_admission_is_fail_safe() -> None:
    with pytest.raises(
        Phase8DryRunFoundationError,
        match="INVALID_ADMISSION_DECISION",
    ):
        StrategyPhase8DryRunPackageFactory().generate("invalid")


def test_bullish_dry_run_package_is_created() -> None:
    decision = StrategyPhase8DryRunPackageFactory().generate(bullish_admission_decision())

    assert decision.status == (Phase8DryRunPackageStatus.CREATED)
    assert decision.reason == (Phase8DryRunPackageReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True


def test_bearish_dry_run_package_is_created() -> None:
    decision = build_phase8_dry_run_foundation(bearish_final_bundle_decision())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.package_required.side == StrategyOrderSide.SELL


def test_existing_outcome_package_is_created() -> None:
    decision = build_phase8_dry_run_foundation(existing_final_bundle_decision())

    assert decision.is_created is True
    assert decision.package_required.outcome_kind == (PlanningAuditPersistenceOutcomeKind.EXISTING)


def test_blocked_admission_blocks_package() -> None:
    decision = StrategyPhase8DryRunPackageFactory().generate(blocked_admission_decision())

    assert decision.is_blocked is True
    assert decision.package is None
    assert decision.reason == (Phase8DryRunPackageReason.SIMULATION_ADMISSION_BLOCKED)


def test_package_preserves_complete_lineage() -> None:
    source = bullish_final_bundle_decision()
    decision = build_phase8_dry_run_foundation(source)
    package = decision.package_required

    assert package.admission is (package.admission_decision.admission_required)
    assert package.scenario is package.admission.scenario
    assert package.handoff is package.scenario.handoff
    assert package.final_bundle is package.handoff.final_bundle
    assert package.final_bundle.stable_id == (source.bundle_required.stable_id)


def test_package_digest_is_deterministic() -> None:
    package = build_phase8_dry_run_foundation(bullish_final_bundle_decision()).package_required
    expected = hashlib.sha256(package.canonical_payload.encode("utf-8")).hexdigest()

    assert package.package_digest == expected


def test_batch_1_marks_completion() -> None:
    decision = build_phase8_dry_run_foundation(bullish_final_bundle_decision())
    package = decision.package_required

    assert package.phase_8_batch_1_complete is True
    assert decision.phase_8_batch_1_complete is True
    assert package.simulation_only is True
    assert package.uses_closed_candles_only is True


@pytest.mark.parametrize(
    "subject",
    [
        lambda: bullish_handoff_decision().handoff_required,
        lambda: bullish_scenario_decision().scenario_required,
        lambda: bullish_admission_decision().admission_required,
        lambda: build_phase8_dry_run_foundation(bullish_final_bundle_decision()).package_required,
    ],
)
def test_all_batch_objects_are_non_executable(
    subject,
) -> None:
    value = subject()

    assert value.has_adapter_instance is False
    assert value.request_submission_authorized is False
    assert value.adapter_invocation_authorized is False
    assert value.storage_write_authorized is False
    assert value.can_write_storage is False
    assert value.can_write_network is False
    assert value.execution_authorized is False
    assert value.has_broker_request is False
    assert value.can_submit_order is False
    assert value.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "adapter",
        "adapter_instance",
        "repository",
        "connection",
        "cursor",
        "transaction",
        "sql",
        "insert",
        "save",
        "persist",
        "write",
        "invoke",
        "execute",
        "send",
        "submit_request",
        "request_handle",
        "order_request",
        "broker_ticket",
        "send_order",
        "order_send",
    ],
)
def test_package_has_no_implementation_surface(
    attribute_name,
) -> None:
    package = build_phase8_dry_run_foundation(bullish_final_bundle_decision()).package_required

    assert not hasattr(package, attribute_name)


def test_handoff_is_immutable() -> None:
    handoff = bullish_handoff_decision().handoff_required

    with pytest.raises(FrozenInstanceError):
        handoff.broker_symbol = "modified"


def test_scenario_is_immutable() -> None:
    scenario = bullish_scenario_decision().scenario_required

    with pytest.raises(FrozenInstanceError):
        scenario.run_mode = Phase8RunMode.SIMULATION_ONLY


def test_admission_is_immutable() -> None:
    admission = bullish_admission_decision().admission_required

    with pytest.raises(FrozenInstanceError):
        admission.scenario_id = "modified"


def test_package_is_immutable() -> None:
    package = build_phase8_dry_run_foundation(bullish_final_bundle_decision()).package_required

    with pytest.raises(FrozenInstanceError):
        package.package_digest = "0" * 64


def test_batch_generation_is_deterministic() -> None:
    source = bullish_final_bundle_decision()

    assert build_phase8_dry_run_foundation(source) == build_phase8_dry_run_foundation(source)


def test_factory_aliases_delegate() -> None:
    bundle = bullish_final_bundle_decision()
    handoff_factory = StrategyPhase8HandoffFactory()
    handoff = handoff_factory.generate(bundle)

    assert handoff_factory.build(bundle) == handoff
    assert handoff_factory.evaluate(bundle) == handoff

    scenario_factory = StrategyPhase8DryRunScenarioFactory()
    scenario = scenario_factory.generate(handoff)

    assert scenario_factory.build(handoff) == scenario
    assert scenario_factory.evaluate(handoff) == scenario

    admission_gate = StrategyPhase8SimulationAdmissionGate()
    admission = admission_gate.assess(scenario)

    assert admission_gate.evaluate(scenario) == admission
    assert admission_gate.check(scenario) == admission

    package_factory = StrategyPhase8DryRunPackageFactory()
    package = package_factory.generate(admission)

    assert package_factory.build(admission) == package
    assert package_factory.evaluate(admission) == package


def test_public_aliases_are_preserved() -> None:
    assert Phase8Handoff is StrategyPhase8Handoff
    assert Phase8DryRunScenario is StrategyPhase8DryRunScenario
    assert Phase8SimulationAdmission is StrategyPhase8SimulationAdmission
    assert Phase8DryRunPackage is StrategyPhase8DryRunPackage
