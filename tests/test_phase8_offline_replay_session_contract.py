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
from app.strategy.phase8_offline_replay_event_contract import (
    StrategyPhase8OfflineReplayEventContractFactory,
)
from app.strategy.phase8_offline_replay_event_materialization import (
    StrategyPhase8OfflineReplayEventMaterializationFactory,
)
from app.strategy.phase8_offline_replay_event_materialization_plan import (
    StrategyPhase8OfflineReplayEventMaterializationPlanFactory,
)
from app.strategy.phase8_offline_replay_plan import (
    StrategyPhase8OfflineReplayPlanFactory,
)
from app.strategy.phase8_offline_replay_session_contract import (
    PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT_SCHEMA_VERSION,
    Phase8OfflineReplayCompletionRule,
    Phase8OfflineReplayCursorSemantics,
    Phase8OfflineReplaySessionContract,
    Phase8OfflineReplaySessionContractBlocker,
    Phase8OfflineReplaySessionContractError,
    Phase8OfflineReplaySessionContractErrorReason,
    Phase8OfflineReplaySessionContractFactory,
    Phase8OfflineReplaySessionContractMode,
    Phase8OfflineReplaySessionContractPolicy,
    Phase8OfflineReplaySessionContractReason,
    Phase8OfflineReplaySessionContractStatus,
    Phase8OfflineReplayTransitionCommitMode,
    StrategyPhase8OfflineReplaySessionContract,
    StrategyPhase8OfflineReplaySessionContractFactory,
    generate_phase8_offline_replay_session_contract,
)
from app.strategy.phase8_offline_replay_session_plan import (
    StrategyPhase8OfflineReplaySessionPlanFactory,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecificationFactory,
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


@lru_cache(maxsize=1)
def bearish_specification_for_replay_plan():
    return StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        bearish_input_for_specification()
    )


@lru_cache(maxsize=1)
def existing_specification_for_replay_plan():
    return StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        existing_input_for_specification()
    )


@lru_cache(maxsize=1)
def blocked_specification_for_replay_plan():
    return StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        blocked_input_for_specification()
    )


@lru_cache(maxsize=1)
def bullish_replay_plan_decision():
    return StrategyPhase8OfflineReplayPlanFactory().generate(
        offline_bullish_specification_decision()
    )


@lru_cache(maxsize=1)
def event_contract_bearish_plan_decision():
    return StrategyPhase8OfflineReplayPlanFactory().generate(
        bearish_specification_for_replay_plan()
    )


@lru_cache(maxsize=1)
def event_contract_existing_plan_decision():
    return StrategyPhase8OfflineReplayPlanFactory().generate(
        existing_specification_for_replay_plan()
    )


@lru_cache(maxsize=1)
def event_contract_blocked_plan_decision():
    return StrategyPhase8OfflineReplayPlanFactory().generate(
        blocked_specification_for_replay_plan()
    )


@lru_cache(maxsize=1)
def event_contract_bullish_decision():
    return StrategyPhase8OfflineReplayEventContractFactory().generate(
        bullish_replay_plan_decision()
    )


@lru_cache(maxsize=1)
def materialization_bearish_contract_decision():
    return StrategyPhase8OfflineReplayEventContractFactory().generate(
        event_contract_bearish_plan_decision()
    )


@lru_cache(maxsize=1)
def materialization_existing_contract_decision():
    return StrategyPhase8OfflineReplayEventContractFactory().generate(
        event_contract_existing_plan_decision()
    )


@lru_cache(maxsize=1)
def materialization_blocked_contract_decision():
    return StrategyPhase8OfflineReplayEventContractFactory().generate(
        event_contract_blocked_plan_decision()
    )


@lru_cache(maxsize=1)
def materialization_bullish_decision():
    return StrategyPhase8OfflineReplayEventMaterializationPlanFactory().generate(
        event_contract_bullish_decision()
    )


@lru_cache(maxsize=1)
def replay_events_bearish_plan_decision():
    return StrategyPhase8OfflineReplayEventMaterializationPlanFactory().generate(
        materialization_bearish_contract_decision()
    )


@lru_cache(maxsize=1)
def replay_events_existing_plan_decision():
    return StrategyPhase8OfflineReplayEventMaterializationPlanFactory().generate(
        materialization_existing_contract_decision()
    )


@lru_cache(maxsize=1)
def replay_events_blocked_plan_decision():
    return StrategyPhase8OfflineReplayEventMaterializationPlanFactory().generate(
        materialization_blocked_contract_decision()
    )


@lru_cache(maxsize=1)
def replay_events_bullish_decision():
    return StrategyPhase8OfflineReplayEventMaterializationFactory().generate(
        materialization_bullish_decision()
    )


def source_price(candle, preferred, fallback):
    if hasattr(candle, preferred):
        return float(getattr(candle, preferred))

    return float(getattr(candle, fallback))


@lru_cache(maxsize=1)
def session_bearish_event_decision():
    return StrategyPhase8OfflineReplayEventMaterializationFactory().generate(
        replay_events_bearish_plan_decision()
    )


@lru_cache(maxsize=1)
def session_existing_event_decision():
    return StrategyPhase8OfflineReplayEventMaterializationFactory().generate(
        replay_events_existing_plan_decision()
    )


@lru_cache(maxsize=1)
def session_blocked_event_decision():
    return StrategyPhase8OfflineReplayEventMaterializationFactory().generate(
        replay_events_blocked_plan_decision()
    )


@lru_cache(maxsize=1)
def bullish_session_plan_decision():
    return StrategyPhase8OfflineReplaySessionPlanFactory().generate(
        replay_events_bullish_decision()
    )


@lru_cache(maxsize=1)
def session_contract_bearish_plan_decision():
    return StrategyPhase8OfflineReplaySessionPlanFactory().generate(
        session_bearish_event_decision()
    )


@lru_cache(maxsize=1)
def session_contract_existing_plan_decision():
    return StrategyPhase8OfflineReplaySessionPlanFactory().generate(
        session_existing_event_decision()
    )


@lru_cache(maxsize=1)
def session_contract_blocked_plan_decision():
    return StrategyPhase8OfflineReplaySessionPlanFactory().generate(
        session_blocked_event_decision()
    )


@lru_cache(maxsize=1)
def bullish_session_contract_decision():
    return StrategyPhase8OfflineReplaySessionContractFactory().generate(
        bullish_session_plan_decision()
    )


def test_invalid_session_plan_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineReplaySessionContractError,
        match="INVALID_SESSION_PLAN_DECISION",
    ) as captured:
        (StrategyPhase8OfflineReplaySessionContractFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineReplaySessionContractErrorReason.INVALID_SESSION_PLAN_DECISION
    )


def test_default_session_contract_policy_is_strict() -> None:
    policy = Phase8OfflineReplaySessionContractPolicy()

    assert policy.is_strict is True
    assert policy.cursor_points_to_next_event is True
    assert policy.forward_only_cursor is True
    assert policy.one_event_per_transition is True
    assert policy.atomic_in_memory_transition is True
    assert policy.deterministic_completion is True
    assert policy.fresh_strategy_state is True
    assert policy.no_lookahead is True
    assert policy.no_external_io is True


@pytest.mark.parametrize(
    "field_name",
    [
        "cursor_points_to_next_event",
        "forward_only_cursor",
        "one_event_per_transition",
        "atomic_in_memory_transition",
        "deterministic_completion",
        "fresh_strategy_state",
        "no_lookahead",
        "no_external_io",
    ],
)
def test_session_contract_policy_rejects_non_boolean(
    field_name,
) -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineReplaySessionContractPolicy(**{field_name: 1})


def test_bullish_session_contract_is_created() -> None:
    decision = bullish_session_contract_decision()

    assert decision.status == (Phase8OfflineReplaySessionContractStatus.CREATED)
    assert decision.reason == (Phase8OfflineReplaySessionContractReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_session_contract is True


def test_bearish_session_contract_is_created() -> None:
    decision = StrategyPhase8OfflineReplaySessionContractFactory().generate(
        session_contract_bearish_plan_decision()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.session_contract_required.side == StrategyOrderSide.SELL


def test_existing_session_contract_is_created() -> None:
    decision = StrategyPhase8OfflineReplaySessionContractFactory().generate(
        session_contract_existing_plan_decision()
    )

    assert decision.is_created is True


def test_blocked_plan_blocks_session_contract() -> None:
    decision = StrategyPhase8OfflineReplaySessionContractFactory().generate(
        session_contract_blocked_plan_decision()
    )

    assert decision.is_blocked is True
    assert decision.session_contract is None
    assert decision.reason == (Phase8OfflineReplaySessionContractReason.SESSION_PLAN_BLOCKED)
    assert decision.blockers == (Phase8OfflineReplaySessionContractBlocker.SESSION_PLAN_BLOCKED,)


def test_contract_required_rejects_blocked_result() -> None:
    decision = StrategyPhase8OfflineReplaySessionContractFactory().generate(
        session_contract_blocked_plan_decision()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 offline replay-session contract",
    ):
        _ = decision.session_contract_required


def test_contract_preserves_session_plan_identity() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.session_plan_decision is (bullish_session_plan_decision())
    assert contract.session_plan is (bullish_session_plan_decision().plan_required)


def test_contract_preserves_complete_lineage() -> None:
    contract = bullish_session_contract_decision().session_contract_required
    plan = contract.session_plan

    assert contract.event_batch is plan.event_batch
    assert contract.materialization_plan is (plan.materialization_plan)
    assert contract.event_contract is plan.event_contract
    assert contract.replay_plan is plan.replay_plan
    assert contract.specification is plan.specification
    assert contract.input_package is plan.input_package
    assert contract.verification_receipt is (plan.verification_receipt)
    assert contract.snapshot is plan.snapshot
    assert contract.contract is plan.contract
    assert contract.dry_run_package is (plan.dry_run_package)


def test_contract_preserves_identifiers() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.session_plan_id == (contract.session_plan.stable_id)
    assert contract.event_batch_id == (contract.event_batch.stable_id)
    assert contract.materialization_plan_id == (contract.materialization_plan.stable_id)
    assert contract.event_contract_id == (contract.event_contract.stable_id)
    assert contract.replay_plan_id == (contract.replay_plan.stable_id)
    assert contract.specification_id == (contract.specification.stable_id)
    assert contract.input_package_id == (contract.input_package.stable_id)
    assert contract.snapshot_id == (contract.snapshot.stable_id)


def test_contract_preserves_digests() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.session_plan_digest == (contract.session_plan.session_digest)
    assert contract.event_batch_digest == (contract.event_batch.batch_digest)
    assert contract.materialization_plan_digest == (
        contract.materialization_plan.materialization_digest
    )
    assert contract.event_contract_digest == (contract.event_contract.contract_digest)
    assert contract.replay_plan_digest == (contract.replay_plan.plan_digest)
    assert contract.specification_digest == (contract.specification.specification_digest)
    assert contract.input_digest == (contract.input_package.input_digest)
    assert contract.snapshot_digest == (contract.snapshot.snapshot_digest)


def test_contract_preserves_metadata() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.broker_symbol == "XAUUSDm"
    assert contract.direction == (DirectionalPermissionDirection.BULLISH)
    assert contract.side == StrategyOrderSide.BUY
    assert contract.source_name == ("EXTERNAL_TEST_FIXTURE")
    assert contract.captured_at == CAPTURED_AT
    assert contract.schema_version == (PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT_SCHEMA_VERSION)


def test_contract_timeframes_are_exact() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )


def test_contract_sequence_window_is_exact() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.sequence_start == 0
    assert contract.sequence_end == 799
    assert contract.initial_cursor_index == 0
    assert contract.completion_cursor_index == 800
    assert contract.transition_count == 800
    assert contract.total_event_count == 800


def test_contract_initial_counts_are_exact() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.initial_consumed_count == 0
    assert contract.initial_remaining_count == 800


def test_contract_time_bounds_match_session_plan() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.first_event_time == (contract.session_plan.first_event_time)
    assert contract.last_event_time == (contract.session_plan.last_event_time)
    assert contract.last_event_time <= contract.captured_at


def test_contract_inherited_controls_match_plan() -> None:
    contract = bullish_session_contract_decision().session_contract_required
    plan = contract.session_plan

    assert contract.session_mode == plan.session_mode
    assert contract.cursor_mode == plan.cursor_mode
    assert contract.transition_mode == (plan.transition_mode)
    assert contract.initial_state_mode == (plan.initial_state_mode)


def test_contract_cursor_controls_are_exact() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.contract_mode == (Phase8OfflineReplaySessionContractMode.IMMUTABLE_FORWARD_ONLY)
    assert contract.cursor_semantics == (Phase8OfflineReplayCursorSemantics.NEXT_EVENT_INDEX)
    assert contract.completion_rule == (Phase8OfflineReplayCompletionRule.CURSOR_EQUALS_EVENT_COUNT)
    assert contract.transition_commit_mode == (
        Phase8OfflineReplayTransitionCommitMode.ATOMIC_IN_MEMORY
    )


def test_contract_digest_is_deterministic() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert (
        contract.contract_digest
        == hashlib.sha256(contract.canonical_payload.encode("utf-8")).hexdigest()
    )
    assert contract.digest_algorithm == "SHA-256"


def test_session_contract_is_contract_only() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.is_ready is True
    assert contract.contract_only is True
    assert contract.cursor_points_to_next_event is True
    assert contract.forward_only is True
    assert contract.no_lookahead is True
    assert contract.completion_is_deterministic is True
    assert contract.initializes_session is False
    assert contract.starts_session is False
    assert contract.advances_cursor is False
    assert contract.consumes_events is False
    assert contract.executes_replay is False
    assert contract.evaluates_strategy is False
    assert contract.executes_simulation is False
    assert contract.emits_orders is False
    assert contract.can_continue_to_offline_replay_session_state is True


def test_session_contract_performs_no_external_io() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.fetches_data is False
    assert contract.initializes_mt5 is False
    assert contract.has_adapter_instance is False
    assert contract.request_submission_authorized is False
    assert contract.adapter_invocation_authorized is False
    assert contract.storage_write_authorized is False
    assert contract.can_write_storage is False
    assert contract.can_write_network is False
    assert contract.execution_authorized is False
    assert contract.has_broker_request is False
    assert contract.can_submit_order is False
    assert contract.is_executable is False


def test_contract_decision_performs_no_execution() -> None:
    decision = bullish_session_contract_decision()

    assert decision.initializes_session is False
    assert decision.starts_session is False
    assert decision.advances_cursor is False
    assert decision.consumes_events is False
    assert decision.executes_replay is False
    assert decision.evaluates_strategy is False
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
        "initialize",
        "initialize_session",
        "start",
        "start_session",
        "run",
        "replay",
        "next_event",
        "consume_event",
        "advance_cursor",
        "commit_transition",
        "evaluate_strategy",
        "evaluate_signal",
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
def test_contract_has_no_execution_surface(
    attribute_name,
) -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert not hasattr(contract, attribute_name)


def test_session_contract_id_is_deterministic() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    assert contract.session_contract_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT:"
        f"CONTRACT_SHA256[{contract.contract_digest}]"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    source = bullish_session_plan_decision()
    decision = bullish_session_contract_decision()

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_SESSION_"
        "CONTRACT_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    source = session_contract_blocked_plan_decision()
    decision = StrategyPhase8OfflineReplaySessionContractFactory().generate(source)

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_SESSION_"
        "CONTRACT_GENERATION:"
        "BLOCKED:SESSION_PLAN_BLOCKED:"
        "SESSION_PLAN_BLOCKED"
    )


def test_direct_contract_rejects_wrong_schema() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            contract,
            schema_version="2.0",
        )


def test_direct_contract_rejects_unsafe_policy() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            contract,
            policy=(Phase8OfflineReplaySessionContractPolicy(no_lookahead=False)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("session_plan_id", "foreign-session-plan"),
        ("event_batch_id", "foreign-batch"),
        (
            "materialization_plan_id",
            "foreign-materialization-plan",
        ),
        ("event_contract_id", "foreign-contract"),
        ("replay_plan_id", "foreign-replay-plan"),
        ("specification_id", "foreign-specification"),
        ("input_package_id", "foreign-input"),
        ("snapshot_id", "foreign-snapshot"),
    ],
)
def test_direct_contract_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            contract,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "session_plan_digest",
        "event_batch_digest",
        "materialization_plan_digest",
        "event_contract_digest",
        "replay_plan_digest",
        "specification_digest",
        "input_digest",
        "snapshot_digest",
    ],
)
def test_direct_contract_rejects_foreign_digests(
    field_name,
) -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            contract,
            **{field_name: "0" * 64},
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "contract_mode",
            "IMMUTABLE_FORWARD_ONLY",
            "Phase8OfflineReplaySessionContractMode",
        ),
        (
            "cursor_semantics",
            "NEXT_EVENT_INDEX",
            "Phase8OfflineReplayCursorSemantics",
        ),
        (
            "completion_rule",
            "CURSOR_EQUALS_EVENT_COUNT",
            "Phase8OfflineReplayCompletionRule",
        ),
        (
            "transition_commit_mode",
            "ATOMIC_IN_MEMORY",
            "Phase8OfflineReplayTransitionCommitMode",
        ),
    ],
)
def test_direct_contract_rejects_raw_enums(
    field_name,
    value,
    message,
) -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match=message):
        replace(
            contract,
            **{field_name: value},
        )


def test_direct_contract_rejects_reordered_timeframes() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            contract,
            timeframes=tuple(reversed(contract.timeframes)),
        )


def test_direct_contract_rejects_nonzero_sequence_start() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match="sequence_start"):
        replace(
            contract,
            sequence_start=1,
            initial_cursor_index=1,
        )


def test_direct_contract_rejects_wrong_sequence_end() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError, match="sequence_end"):
        replace(
            contract,
            sequence_end=798,
        )


def test_direct_contract_rejects_wrong_initial_cursor() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="initial_cursor_index",
    ):
        replace(
            contract,
            initial_cursor_index=1,
        )


def test_direct_contract_rejects_wrong_completion_cursor() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="completion_cursor_index",
    ):
        replace(
            contract,
            completion_cursor_index=799,
        )


def test_direct_contract_rejects_wrong_transition_count() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="transition_count",
    ):
        replace(
            contract,
            transition_count=799,
        )


def test_direct_contract_rejects_consumed_initial_state() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="initial_consumed_count",
    ):
        replace(
            contract,
            initial_consumed_count=1,
        )


def test_direct_contract_rejects_wrong_remaining_count() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="initial_remaining_count",
    ):
        replace(
            contract,
            initial_remaining_count=799,
        )


def test_direct_contract_rejects_wrong_total() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(ValueError):
        replace(
            contract,
            total_event_count=799,
        )


def test_direct_contract_rejects_wrong_first_time() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="first_event_time",
    ):
        replace(
            contract,
            first_event_time=contract.last_event_time,
        )


def test_direct_contract_rejects_wrong_last_time() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="last_event_time",
    ):
        replace(
            contract,
            last_event_time=contract.first_event_time,
        )


def test_direct_contract_rejects_wrong_digest() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(
        ValueError,
        match="contract_digest",
    ):
        replace(
            contract,
            contract_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = bullish_session_contract_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineReplaySessionContractStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_contract() -> None:
    decision = bullish_session_contract_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            session_contract=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPhase8OfflineReplaySessionContractFactory().generate(
        session_contract_blocked_plan_decision()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                Phase8OfflineReplaySessionContractBlocker.SESSION_PLAN_BLOCKED,
                Phase8OfflineReplaySessionContractBlocker.SESSION_PLAN_BLOCKED,
            ),
        )


def test_session_contract_policy_is_immutable() -> None:
    policy = Phase8OfflineReplaySessionContractPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_session_contract_is_immutable() -> None:
    contract = bullish_session_contract_decision().session_contract_required

    with pytest.raises(FrozenInstanceError):
        contract.contract_digest = "0" * 64


def test_session_contract_decision_is_immutable() -> None:
    decision = bullish_session_contract_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineReplaySessionContractStatus.BLOCKED


def test_session_contract_generation_is_deterministic() -> None:
    factory = StrategyPhase8OfflineReplaySessionContractFactory()
    source = bullish_session_plan_decision()

    first = factory.generate(source).session_contract_required
    second = factory.generate(source).session_contract_required

    assert first.contract_digest == second.contract_digest
    assert first.canonical_payload == second.canonical_payload


def test_session_contract_function_api_delegates() -> None:
    decision = generate_phase8_offline_replay_session_contract(bullish_session_plan_decision())

    assert decision.is_created is True


def test_session_contract_factory_aliases_delegate() -> None:
    factory = StrategyPhase8OfflineReplaySessionContractFactory()
    source = bullish_session_plan_decision()
    generated = factory.generate(source)

    assert factory.build(source).session_contract_required.contract_digest == (
        generated.session_contract_required.contract_digest
    )
    assert factory.evaluate(source).session_contract_required.contract_digest == (
        generated.session_contract_required.contract_digest
    )


def test_session_contract_public_aliases_are_preserved() -> None:
    assert Phase8OfflineReplaySessionContract is StrategyPhase8OfflineReplaySessionContract
    assert (
        Phase8OfflineReplaySessionContractFactory
        is StrategyPhase8OfflineReplaySessionContractFactory
    )
