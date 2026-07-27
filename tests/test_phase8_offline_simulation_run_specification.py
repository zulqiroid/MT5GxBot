import hashlib
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
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
from app.strategy.phase8_closed_candle_data_contract import (
    StrategyPhase8ClosedCandleDataContractFactory,
)
from app.strategy.phase8_closed_candle_snapshot import (
    Phase8ClosedCandle,
    StrategyPhase8ClosedCandleSnapshotFactory,
    build_phase8_closed_candle_series,
)
from app.strategy.phase8_closed_candle_snapshot_verification import (
    StrategyPhase8ClosedCandleSnapshotVerificationFactory,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
    StrategyPhase8DryRunPackageFactory,
    StrategyPhase8DryRunScenarioFactory,
    StrategyPhase8HandoffFactory,
    StrategyPhase8SimulationAdmissionGate,
    build_phase8_dry_run_foundation,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION_SCHEMA_VERSION,
    Phase8OfflineSimulationDataAccess,
    Phase8OfflineSimulationReplayOrder,
    Phase8OfflineSimulationRunMode,
    Phase8OfflineSimulationRunPolicy,
    Phase8OfflineSimulationRunSpecification,
    Phase8OfflineSimulationRunSpecificationBlocker,
    Phase8OfflineSimulationRunSpecificationError,
    Phase8OfflineSimulationRunSpecificationErrorReason,
    Phase8OfflineSimulationRunSpecificationFactory,
    Phase8OfflineSimulationRunSpecificationReason,
    Phase8OfflineSimulationRunSpecificationStatus,
    StrategyPhase8OfflineSimulationRunSpecification,
    StrategyPhase8OfflineSimulationRunSpecificationFactory,
    generate_phase8_offline_simulation_run_specification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackageFactory,
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


@lru_cache(maxsize=1)
def bullish_package_decision():
    return build_phase8_dry_run_foundation(bullish_final_bundle_decision())


@lru_cache(maxsize=1)
def bearish_package_decision():
    return build_phase8_dry_run_foundation(bearish_final_bundle_decision())


@lru_cache(maxsize=1)
def existing_package_decision():
    return build_phase8_dry_run_foundation(existing_final_bundle_decision())


@lru_cache(maxsize=1)
def blocked_package_decision():
    return StrategyPhase8DryRunPackageFactory().generate(blocked_admission_decision())


CAPTURED_AT = datetime(
    2025,
    3,
    1,
    tzinfo=timezone.utc,
)


_TIMEFRAME_STEPS = {
    Phase8Timeframe.H4: timedelta(hours=4),
    Phase8Timeframe.H1: timedelta(hours=1),
    Phase8Timeframe.M15: timedelta(minutes=15),
    Phase8Timeframe.M5: timedelta(minutes=5),
}


@lru_cache(maxsize=1)
def bullish_contract_decision():
    return StrategyPhase8ClosedCandleDataContractFactory().generate(bullish_package_decision())


@lru_cache(maxsize=1)
def bearish_contract_decision():
    return StrategyPhase8ClosedCandleDataContractFactory().generate(bearish_package_decision())


@lru_cache(maxsize=1)
def existing_contract_decision():
    return StrategyPhase8ClosedCandleDataContractFactory().generate(existing_package_decision())


@lru_cache(maxsize=1)
def blocked_contract_decision():
    return StrategyPhase8ClosedCandleDataContractFactory().generate(blocked_package_decision())


def make_candles(
    timeframe,
    *,
    count=200,
    start=None,
):
    step = _TIMEFRAME_STEPS[timeframe]
    first_open = start or datetime(
        2025,
        1,
        1,
        tzinfo=timezone.utc,
    )
    candles = []

    for index in range(count):
        open_time = first_open + step * index
        open_price = 2000.0 + index * 0.1
        close_price = open_price + 0.05

        candles.append(
            Phase8ClosedCandle(
                open_time=open_time,
                close_time=open_time + step,
                open_price=open_price,
                high_price=close_price + 0.10,
                low_price=open_price - 0.10,
                close_price=close_price,
            )
        )

    return tuple(candles)


def make_series(
    timeframe,
    *,
    count=200,
    start=None,
):
    return build_phase8_closed_candle_series(
        timeframe,
        make_candles(
            timeframe,
            count=count,
            start=start,
        ),
    )


@lru_cache(maxsize=1)
def complete_series():
    return tuple(
        make_series(timeframe)
        for timeframe in (
            Phase8Timeframe.H4,
            Phase8Timeframe.H1,
            Phase8Timeframe.M15,
            Phase8Timeframe.M5,
        )
    )


@lru_cache(maxsize=1)
def bullish_snapshot_decision():
    return StrategyPhase8ClosedCandleSnapshotFactory().generate(
        bullish_contract_decision(),
        source_name="EXTERNAL_TEST_FIXTURE",
        captured_at=CAPTURED_AT,
        series=complete_series(),
    )


@lru_cache(maxsize=1)
def bearish_snapshot_for_verification():
    return StrategyPhase8ClosedCandleSnapshotFactory().generate(
        bearish_contract_decision(),
        source_name="EXTERNAL_TEST_FIXTURE",
        captured_at=CAPTURED_AT,
        series=complete_series(),
    )


@lru_cache(maxsize=1)
def existing_snapshot_for_verification():
    return StrategyPhase8ClosedCandleSnapshotFactory().generate(
        existing_contract_decision(),
        source_name="EXTERNAL_TEST_FIXTURE",
        captured_at=CAPTURED_AT,
        series=complete_series(),
    )


@lru_cache(maxsize=1)
def blocked_snapshot_for_verification():
    return StrategyPhase8ClosedCandleSnapshotFactory().generate(blocked_contract_decision())


@lru_cache(maxsize=1)
def bullish_verification_decision():
    return StrategyPhase8ClosedCandleSnapshotVerificationFactory().verify(
        bullish_snapshot_decision()
    )


def unsafe_snapshot_decision(
    **snapshot_changes,
):
    source_decision = bullish_snapshot_decision()
    source_snapshot = source_decision.snapshot_required

    snapshot = object.__new__(type(source_snapshot))

    snapshot_fields = (
        "contract_decision",
        "source_name",
        "captured_at",
        "series",
        "schema_version",
        "contract_id",
        "contract_digest",
        "snapshot_digest",
    )

    for field_name in snapshot_fields:
        object.__setattr__(
            snapshot,
            field_name,
            snapshot_changes.get(
                field_name,
                getattr(source_snapshot, field_name),
            ),
        )

    decision = object.__new__(type(source_decision))

    object.__setattr__(
        decision,
        "contract_decision",
        source_decision.contract_decision,
    )
    object.__setattr__(
        decision,
        "status",
        source_decision.status,
    )
    object.__setattr__(
        decision,
        "reason",
        source_decision.reason,
    )
    object.__setattr__(
        decision,
        "blockers",
        source_decision.blockers,
    )
    object.__setattr__(
        decision,
        "snapshot",
        snapshot,
    )

    return decision


@lru_cache(maxsize=1)
def bearish_verification_for_input():
    return StrategyPhase8ClosedCandleSnapshotVerificationFactory().verify(
        bearish_snapshot_for_verification()
    )


@lru_cache(maxsize=1)
def existing_verification_for_input():
    return StrategyPhase8ClosedCandleSnapshotVerificationFactory().verify(
        existing_snapshot_for_verification()
    )


@lru_cache(maxsize=1)
def blocked_verification_for_input():
    return StrategyPhase8ClosedCandleSnapshotVerificationFactory().verify(
        blocked_snapshot_for_verification()
    )


@lru_cache(maxsize=1)
def bullish_input_decision():
    return StrategyPhase8SimulationInputPackageFactory().generate(bullish_verification_decision())


@lru_cache(maxsize=1)
def bearish_input_for_specification():
    return StrategyPhase8SimulationInputPackageFactory().generate(bearish_verification_for_input())


@lru_cache(maxsize=1)
def existing_input_for_specification():
    return StrategyPhase8SimulationInputPackageFactory().generate(existing_verification_for_input())


@lru_cache(maxsize=1)
def blocked_input_for_specification():
    return StrategyPhase8SimulationInputPackageFactory().generate(blocked_verification_for_input())


@lru_cache(maxsize=1)
def offline_bullish_specification_decision():
    return StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        bullish_input_decision()
    )


def test_invalid_input_decision_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineSimulationRunSpecificationError,
        match="INVALID_INPUT_PACKAGE_DECISION",
    ) as captured:
        (StrategyPhase8OfflineSimulationRunSpecificationFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineSimulationRunSpecificationErrorReason.INVALID_INPUT_PACKAGE_DECISION
    )


def test_default_policy_is_strict() -> None:
    policy = Phase8OfflineSimulationRunPolicy()

    assert policy.is_strict is True
    assert policy.strict_chronology is True
    assert policy.no_lookahead is True
    assert policy.closed_candles_only is True
    assert policy.deterministic_replay is True
    assert policy.preserve_source_prices is True


def test_policy_rejects_non_boolean_value() -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineSimulationRunPolicy(no_lookahead=1)


def test_bullish_specification_is_created() -> None:
    decision = offline_bullish_specification_decision()

    assert decision.status == (Phase8OfflineSimulationRunSpecificationStatus.CREATED)
    assert decision.reason == (Phase8OfflineSimulationRunSpecificationReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_specification is True


def test_bearish_specification_is_created() -> None:
    decision = StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        bearish_input_for_specification()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.specification_required.side == StrategyOrderSide.SELL


def test_existing_specification_is_created() -> None:
    decision = StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        existing_input_for_specification()
    )

    assert decision.is_created is True


def test_blocked_input_blocks_specification() -> None:
    decision = StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        blocked_input_for_specification()
    )

    assert decision.is_blocked is True
    assert decision.specification is None
    assert decision.reason == (
        Phase8OfflineSimulationRunSpecificationReason.SIMULATION_INPUT_BLOCKED
    )
    assert decision.blockers == (
        Phase8OfflineSimulationRunSpecificationBlocker.SIMULATION_INPUT_BLOCKED,
    )


def test_specification_required_rejects_blocked() -> None:
    decision = StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        blocked_input_for_specification()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 offline simulation",
    ):
        _ = decision.specification_required


def test_specification_preserves_input_identity() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.input_decision is (bullish_input_decision())
    assert specification.input_package is (bullish_input_decision().package_required)


def test_specification_preserves_complete_lineage() -> None:
    specification = offline_bullish_specification_decision().specification_required
    package = specification.input_package

    assert specification.verification_receipt is (package.verification_receipt)
    assert specification.snapshot is package.snapshot
    assert specification.contract is package.contract
    assert specification.dry_run_package is (package.dry_run_package)
    assert specification.input_package_id == (package.stable_id)
    assert specification.snapshot_id == (package.snapshot_id)


def test_specification_preserves_digests() -> None:
    specification = offline_bullish_specification_decision().specification_required
    package = specification.input_package

    assert specification.input_digest == (package.input_digest)
    assert specification.verification_receipt_digest == (package.verification_receipt_digest)
    assert specification.snapshot_digest == (package.snapshot_digest)
    assert specification.contract_digest == (package.contract_digest)
    assert specification.dry_run_package_digest == (package.dry_run_package_digest)


def test_specification_preserves_metadata() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.broker_symbol == "XAUUSDm"
    assert specification.direction == (DirectionalPermissionDirection.BULLISH)
    assert specification.side == StrategyOrderSide.BUY
    assert specification.source_name == ("EXTERNAL_TEST_FIXTURE")
    assert specification.captured_at == CAPTURED_AT
    assert specification.schema_version == (
        PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION_SCHEMA_VERSION
    )


def test_specification_timeframes_are_exact() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )
    assert specification.series_count == 4


def test_specification_preserves_candle_counts() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.series_counts == (specification.input_package.series_counts)
    assert specification.total_candle_count == 800
    assert specification.replay_event_count == 800


def test_run_controls_are_exact() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.run_mode == (Phase8OfflineSimulationRunMode.OFFLINE_REPLAY_ONLY)
    assert specification.replay_order == (Phase8OfflineSimulationReplayOrder.OLDEST_TO_NEWEST)
    assert specification.data_access == (Phase8OfflineSimulationDataAccess.SNAPSHOT_ONLY)


def test_specification_digest_is_deterministic() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert (
        specification.specification_digest
        == hashlib.sha256(specification.canonical_payload.encode("utf-8")).hexdigest()
    )
    assert specification.digest_algorithm == "SHA-256"


def test_specification_is_offline_no_lookahead() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.is_ready is True
    assert specification.offline_only is True
    assert specification.snapshot_only is True
    assert specification.no_lookahead is True
    assert specification.strict_chronology is True
    assert specification.executes_simulation is False
    assert specification.can_continue_to_offline_replay_plan is True


def test_specification_performs_no_io_or_execution() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.fetches_data is False
    assert specification.initializes_mt5 is False
    assert specification.has_adapter_instance is False
    assert specification.request_submission_authorized is False
    assert specification.adapter_invocation_authorized is False
    assert specification.storage_write_authorized is False
    assert specification.can_write_storage is False
    assert specification.can_write_network is False
    assert specification.execution_authorized is False
    assert specification.has_broker_request is False
    assert specification.can_submit_order is False
    assert specification.is_executable is False


def test_decision_performs_no_io_or_execution() -> None:
    decision = offline_bullish_specification_decision()

    assert decision.executes_simulation is False
    assert decision.fetches_data is False
    assert decision.initializes_mt5 is False
    assert decision.has_adapter_instance is False
    assert decision.request_submission_authorized is False
    assert decision.adapter_invocation_authorized is False
    assert decision.storage_write_authorized is False
    assert decision.can_write_storage is False
    assert decision.can_write_network is False
    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "run",
        "replay",
        "run_simulation",
        "simulate",
        "fetch",
        "download",
        "copy_rates",
        "copy_rates_from",
        "adapter",
        "adapter_instance",
        "repository",
        "connection",
        "cursor",
        "transaction",
        "insert",
        "save",
        "persist",
        "write",
        "execute",
        "send",
        "submit_request",
        "order_request",
        "broker_ticket",
        "send_order",
        "order_send",
    ],
)
def test_specification_has_no_implementation_surface(
    attribute_name,
) -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert not hasattr(specification, attribute_name)


def test_specification_id_is_deterministic() -> None:
    specification = offline_bullish_specification_decision().specification_required

    assert specification.specification_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION:"
        "SPEC_SHA256["
        f"{specification.specification_digest}]"
    )


def test_direct_specification_rejects_wrong_schema() -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            specification,
            schema_version="2.0",
        )


def test_direct_specification_rejects_unsafe_policy() -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            specification,
            policy=Phase8OfflineSimulationRunPolicy(no_lookahead=False),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("input_package_id", "foreign-input"),
        (
            "verification_receipt_id",
            "foreign-receipt",
        ),
        ("snapshot_id", "foreign-snapshot"),
        ("contract_id", "foreign-contract"),
        ("dry_run_package_id", "foreign-package"),
    ],
)
def test_direct_specification_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            specification,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "input_digest",
        "verification_receipt_digest",
        "snapshot_digest",
        "contract_digest",
        "dry_run_package_digest",
    ],
)
def test_direct_specification_rejects_foreign_digests(
    field_name,
) -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            specification,
            **{field_name: "0" * 64},
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "run_mode",
            "OFFLINE_REPLAY_ONLY",
            "Phase8OfflineSimulationRunMode",
        ),
        (
            "replay_order",
            "OLDEST_TO_NEWEST",
            "Phase8OfflineSimulationReplayOrder",
        ),
        (
            "data_access",
            "SNAPSHOT_ONLY",
            "Phase8OfflineSimulationDataAccess",
        ),
    ],
)
def test_direct_specification_rejects_raw_enums(
    field_name,
    value,
    message,
) -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(ValueError, match=message):
        replace(
            specification,
            **{field_name: value},
        )


def test_direct_specification_rejects_reordered_timeframes() -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            specification,
            timeframes=tuple(reversed(specification.timeframes)),
        )


def test_direct_specification_rejects_wrong_counts() -> None:
    specification = offline_bullish_specification_decision().specification_required
    counts = (
        (
            specification.series_counts[0][0],
            199,
        ),
        *specification.series_counts[1:],
    )

    with pytest.raises(ValueError):
        replace(
            specification,
            series_counts=counts,
        )


def test_direct_specification_rejects_wrong_total() -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(
        ValueError,
        match="total_candle_count",
    ):
        replace(
            specification,
            total_candle_count=799,
        )


def test_direct_specification_rejects_wrong_digest() -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(
        ValueError,
        match="specification_digest",
    ):
        replace(
            specification,
            specification_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = offline_bullish_specification_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineSimulationRunSpecificationStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_specification() -> None:
    decision = offline_bullish_specification_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            specification=None,
        )


def test_policy_is_immutable() -> None:
    policy = Phase8OfflineSimulationRunPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_specification_is_immutable() -> None:
    specification = offline_bullish_specification_decision().specification_required

    with pytest.raises(FrozenInstanceError):
        specification.specification_digest = "0" * 64


def test_decision_is_immutable() -> None:
    decision = offline_bullish_specification_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineSimulationRunSpecificationStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPhase8OfflineSimulationRunSpecificationFactory()
    source = bullish_input_decision()

    first = factory.generate(source).specification_required
    second = factory.generate(source).specification_required

    assert first.specification_digest == second.specification_digest
    assert first.canonical_payload == second.canonical_payload


def test_function_api_delegates() -> None:
    decision = generate_phase8_offline_simulation_run_specification(bullish_input_decision())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPhase8OfflineSimulationRunSpecificationFactory()
    source = bullish_input_decision()
    generated = factory.generate(source)

    assert (
        factory.build(source).specification_required.specification_digest
        == generated.specification_required.specification_digest
    )
    assert (
        factory.evaluate(source).specification_required.specification_digest
        == generated.specification_required.specification_digest
    )


def test_public_aliases_are_preserved() -> None:
    assert (
        Phase8OfflineSimulationRunSpecification is StrategyPhase8OfflineSimulationRunSpecification
    )
    assert (
        Phase8OfflineSimulationRunSpecificationFactory
        is StrategyPhase8OfflineSimulationRunSpecificationFactory
    )
