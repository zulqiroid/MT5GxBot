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
from app.strategy.planning_audit_export import (
    StrategyPlanningAuditExportFactory,
)
from app.strategy.planning_audit_manifest import (
    StrategyPlanningAuditManifestFactory,
)
from app.strategy.planning_audit_persistence_outcome_contract import (
    PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT_SCHEMA_VERSION,
    AuditPersistenceConflictPolicy,
    AuditPersistenceOutcomeContract,
    AuditPersistenceOutcomeContractDecision,
    AuditPersistenceOutcomeContractFactory,
    AuditPersistenceOutcomeEvidenceMode,
    AuditPersistenceOutcomeKind,
    PlanningAuditPersistenceConflictPolicy,
    PlanningAuditPersistenceOutcomeContract,
    PlanningAuditPersistenceOutcomeContractBlocker,
    PlanningAuditPersistenceOutcomeContractDecision,
    PlanningAuditPersistenceOutcomeContractError,
    PlanningAuditPersistenceOutcomeContractErrorReason,
    PlanningAuditPersistenceOutcomeContractFactory,
    PlanningAuditPersistenceOutcomeContractReason,
    PlanningAuditPersistenceOutcomeContractStatus,
    PlanningAuditPersistenceOutcomeEvidenceMode,
    PlanningAuditPersistenceOutcomeKind,
    StrategyAuditPersistenceOutcomeContract,
    StrategyAuditPersistenceOutcomeContractFactory,
    StrategyPlanningAuditPersistenceOutcomeContract,
    StrategyPlanningAuditPersistenceOutcomeContractFactory,
    generate_planning_audit_persistence_outcome_contract,
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


def test_invalid_verification_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditPersistenceOutcomeContractError,
        match="INVALID_REQUEST_VERIFICATION_DECISION",
    ) as captured:
        (StrategyPlanningAuditPersistenceOutcomeContractFactory().generate("invalid"))

    assert captured.value.reason == (
        PlanningAuditPersistenceOutcomeContractErrorReason.INVALID_REQUEST_VERIFICATION_DECISION
    )


def test_bullish_outcome_contract_is_created() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    assert decision.status == (PlanningAuditPersistenceOutcomeContractStatus.CREATED)
    assert decision.reason == (PlanningAuditPersistenceOutcomeContractReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_contract is True


def test_bearish_outcome_contract_is_created() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bearish_request_verification()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.contract_required.side == StrategyOrderSide.SELL


def test_blocked_verification_produces_no_contract() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        blocked_request_verification()
    )

    assert decision.is_blocked is True
    assert decision.contract is None
    assert decision.has_contract is False
    assert decision.reason == (
        PlanningAuditPersistenceOutcomeContractReason.REQUEST_VERIFICATION_BLOCKED
    )
    assert decision.blockers == (
        PlanningAuditPersistenceOutcomeContractBlocker.REQUEST_VERIFICATION_BLOCKED,
    )


def test_contract_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        blocked_request_verification()
    )

    with pytest.raises(
        ValueError,
        match="No planning-audit persistence outcome contract",
    ):
        _ = decision.contract_required


def test_contract_preserves_verification_decision() -> None:
    verification = bullish_request_verification()
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(verification)
        .contract_required
    )

    assert contract.request_verification is verification
    assert contract.verification_receipt is (verification.receipt_required)
    assert contract.request is (verification.receipt_required.request)


def test_contract_preserves_metadata() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.broker_symbol == "XAUUSDm"
    assert contract.observed_at == OBSERVED_AT
    assert contract.direction == (DirectionalPermissionDirection.BULLISH)
    assert contract.side == StrategyOrderSide.BUY
    assert contract.schema_version == (PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT_SCHEMA_VERSION)


def test_allowed_outcomes_are_exact() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.allowed_outcomes == (
        PlanningAuditPersistenceOutcomeKind.CREATED,
        PlanningAuditPersistenceOutcomeKind.EXISTING,
    )
    assert contract.allowed_outcome_count == 2
    assert contract.allows_created is True
    assert contract.allows_existing is True


def test_conflict_policy_rejects_digest_mismatch() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.conflict_policy == (
        PlanningAuditPersistenceConflictPolicy.REJECT_DIGEST_MISMATCH
    )
    assert contract.requires_digest_match is True


def test_verified_result_evidence_is_required() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.evidence_mode == (
        PlanningAuditPersistenceOutcomeEvidenceMode.REQUIRE_VERIFIED_RESULT
    )
    assert contract.requires_verified_result is True


def test_contract_preserves_request_identity() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )
    request = contract.request
    receipt = contract.verification_receipt

    assert contract.expected_request_id == (request.request_id)
    assert contract.expected_request_id == (receipt.verified_request_id)
    assert contract.expected_request_digest == (request.request_digest)
    assert contract.expected_request_digest == (receipt.verified_request_digest)


def test_contract_preserves_payload_lineage() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )
    request = contract.request
    receipt = contract.verification_receipt

    assert contract.expected_content_length_bytes == (request.content_length_bytes)
    assert contract.expected_content_length_bytes == (receipt.verified_content_length_bytes)
    assert contract.expected_content_digest == (request.content_digest)
    assert contract.expected_content_digest == (receipt.verified_content_digest)
    assert contract.expected_manifest_digest == (request.manifest_digest)
    assert contract.expected_manifest_digest == (receipt.verified_manifest_digest)


def test_contract_preserves_idempotency_lineage() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.expected_idempotency_key == (contract.request.idempotency_key)
    assert contract.expected_idempotency_key == (
        contract.verification_receipt.verified_idempotency_key
    )


def test_contract_preserves_binding_lineage() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )
    request = contract.request
    receipt = contract.verification_receipt

    assert contract.expected_binding_receipt_digest == (request.binding_verification_receipt_digest)
    assert contract.expected_binding_receipt_digest == (receipt.verified_binding_receipt_digest)
    assert contract.expected_binding_id == (request.binding_id)
    assert contract.expected_binding_id == (receipt.verified_binding_id)
    assert contract.expected_snapshot_id == (request.snapshot_id)
    assert contract.expected_snapshot_id == (receipt.verified_snapshot_id)
    assert contract.expected_contract_id == (request.contract_id)
    assert contract.expected_contract_id == (receipt.verified_contract_id)


@pytest.mark.parametrize(
    "field_name",
    [
        "expected_request_digest",
        "expected_content_digest",
        "expected_manifest_digest",
        "expected_idempotency_key",
        "expected_binding_receipt_digest",
        "outcome_contract_digest",
    ],
)
def test_contract_digests_are_lowercase_sha256(
    field_name: str,
) -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )
    value = getattr(contract, field_name)

    assert len(value) == 64
    assert value == value.lower()
    assert set(value) <= set("0123456789abcdef")


def test_contract_digest_matches_canonical_payload() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )
    expected = hashlib.sha256(contract.canonical_payload.encode("utf-8")).hexdigest()

    assert contract.outcome_contract_digest == expected
    assert contract.digest_algorithm == "SHA-256"


def test_contract_is_specification_only() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    assert contract.is_specification_only is True
    assert contract.is_outcome_contract_ready is True
    assert contract.can_continue_to_outcome_evidence_design is True
    assert decision.can_continue_to_outcome_evidence_design is True
    assert contract.has_outcome_evidence is False
    assert decision.has_outcome_evidence is False


def test_contract_performs_no_write_or_execution() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.has_adapter_instance is False
    assert contract.request_submission_authorized is False
    assert contract.adapter_invocation_authorized is False
    assert contract.storage_write_authorized is False
    assert contract.is_persisted is False
    assert contract.can_write_storage is False
    assert contract.can_write_network is False
    assert contract.execution_authorized is False
    assert contract.has_broker_request is False
    assert contract.can_submit_order is False
    assert contract.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    assert decision.has_adapter_instance is False
    assert decision.request_submission_authorized is False
    assert decision.adapter_invocation_authorized is False
    assert decision.storage_write_authorized is False
    assert decision.is_persisted is False
    assert decision.can_write_storage is False
    assert decision.can_write_network is False
    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "outcome",
        "outcome_evidence",
        "storage_result",
        "adapter",
        "adapter_instance",
        "repository",
        "callable",
        "callback",
        "filename",
        "file_path",
        "directory",
        "connection",
        "cursor",
        "transaction",
        "sql",
        "insert",
        "save",
        "persist",
        "write",
        "write_file",
        "invoke",
        "execute",
        "upload",
        "post",
        "send",
        "submit_request",
        "request_handle",
        "order_request",
        "broker_ticket",
        "authorize",
        "submit",
        "send_order",
        "order_send",
    ],
)
def test_contract_contains_no_implementation_surface(
    attribute_name: str,
) -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert not hasattr(contract, attribute_name)


def test_contract_id_is_deterministic() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    assert contract.contract_id == (
        "XAUUSDm:BUY:"
        "AUDIT_PERSISTENCE_OUTCOME_CONTRACT:"
        "AUDIT_ARCHIVE:"
        "REJECT_DIGEST_MISMATCH:"
        "REQUIRE_VERIFIED_RESULT:"
        f"REQUEST[{contract.expected_request_id}]:"
        f"CONTRACT_SHA256["
        f"{contract.outcome_contract_digest}]"
    )


def test_contract_stable_id_is_deterministic() -> None:
    verification = bullish_request_verification()
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(verification)
        .contract_required
    )

    assert contract.stable_id == (
        f"{verification.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT:"
        f"{contract.contract_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    verification = bullish_request_verification()
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(verification)

    assert decision.stable_id == (
        f"{verification.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_OUTCOME_"
        "CONTRACT_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    verification = blocked_request_verification()
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(verification)

    assert decision.stable_id == (
        f"{verification.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_OUTCOME_"
        "CONTRACT_GENERATION:"
        "BLOCKED:REQUEST_VERIFICATION_BLOCKED:"
        "REQUEST_VERIFICATION_BLOCKED"
    )


def test_direct_contract_rejects_blocked_verification() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(
        ValueError,
        match="verified persistence-request decision",
    ):
        replace(
            contract,
            request_verification=(blocked_request_verification()),
        )


def test_direct_contract_rejects_wrong_schema() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            contract,
            schema_version="2.0",
        )


def test_direct_contract_requires_tuple_outcomes() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(ValueError, match="tuple"):
        replace(
            contract,
            allowed_outcomes=list(contract.allowed_outcomes),
        )


def test_direct_contract_rejects_raw_outcomes() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(
        ValueError,
        match="OutcomeKind",
    ):
        replace(
            contract,
            allowed_outcomes=tuple(outcome.value for outcome in contract.allowed_outcomes),
        )


def test_direct_contract_rejects_duplicate_outcomes() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            contract,
            allowed_outcomes=(
                PlanningAuditPersistenceOutcomeKind.CREATED,
                PlanningAuditPersistenceOutcomeKind.CREATED,
            ),
        )


def test_direct_contract_rejects_reordered_outcomes() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            contract,
            allowed_outcomes=tuple(reversed(contract.allowed_outcomes)),
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "target",
            "AUDIT_ARCHIVE",
            "PlanningAuditStorageTarget",
        ),
        (
            "conflict_policy",
            "REJECT_DIGEST_MISMATCH",
            "PlanningAuditPersistenceConflictPolicy",
        ),
        (
            "evidence_mode",
            "REQUIRE_VERIFIED_RESULT",
            "PlanningAuditPersistenceOutcomeEvidenceMode",
        ),
    ],
)
def test_direct_contract_rejects_raw_enums(
    field_name: str,
    value: str,
    message: str,
) -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(ValueError, match=message):
        replace(
            contract,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("expected_request_id", "foreign-request"),
        ("expected_request_digest", "0" * 64),
        ("expected_content_length_bytes", 1),
        ("expected_content_digest", "0" * 64),
        ("expected_manifest_digest", "0" * 64),
        ("expected_idempotency_key", "0" * 64),
        (
            "expected_binding_receipt_digest",
            "0" * 64,
        ),
        ("expected_binding_id", "foreign-binding"),
        ("expected_snapshot_id", "foreign-snapshot"),
        ("expected_contract_id", "foreign-contract"),
        ("outcome_contract_digest", "0" * 64),
    ],
)
def test_direct_contract_rejects_foreign_values(
    field_name: str,
    value: object,
) -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(ValueError, match=field_name):
        replace(
            contract,
            **{field_name: value},
        )


def test_direct_contract_rejects_uppercase_digest() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(ValueError, match="lowercase"):
        replace(
            contract,
            outcome_contract_digest="A" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(PlanningAuditPersistenceOutcomeContractStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            reason=(PlanningAuditPersistenceOutcomeContractReason.REQUEST_VERIFICATION_BLOCKED),
        )


def test_manual_decision_rejects_missing_contract() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            contract=None,
        )


def test_manual_decision_rejects_unexpected_contract() -> None:
    blocked = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        blocked_request_verification()
    )
    created_contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(ValueError, match="does not match"):
        replace(
            blocked,
            contract=created_contract,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        blocked_request_verification()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                PlanningAuditPersistenceOutcomeContractBlocker.REQUEST_VERIFICATION_BLOCKED,
                PlanningAuditPersistenceOutcomeContractBlocker.REQUEST_VERIFICATION_BLOCKED,
            ),
        )


def test_contract_is_immutable() -> None:
    contract = (
        StrategyPlanningAuditPersistenceOutcomeContractFactory()
        .generate(bullish_request_verification())
        .contract_required
    )

    with pytest.raises(FrozenInstanceError):
        contract.expected_request_id = "modified"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditPersistenceOutcomeContractStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditPersistenceOutcomeContractFactory()
    verification = bullish_request_verification()

    assert factory.generate(verification) == factory.generate(verification)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_persistence_outcome_contract(bullish_request_verification())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditPersistenceOutcomeContractFactory()
    verification = bullish_request_verification()

    assert factory.build(verification) == factory.generate(verification)
    assert factory.evaluate(verification) == factory.generate(verification)


def test_public_aliases_are_preserved() -> None:
    assert AuditPersistenceConflictPolicy is PlanningAuditPersistenceConflictPolicy
    assert AuditPersistenceOutcomeContract is StrategyPlanningAuditPersistenceOutcomeContract
    assert (
        AuditPersistenceOutcomeContractDecision is PlanningAuditPersistenceOutcomeContractDecision
    )
    assert (
        AuditPersistenceOutcomeContractFactory
        is StrategyPlanningAuditPersistenceOutcomeContractFactory
    )
    assert AuditPersistenceOutcomeEvidenceMode is PlanningAuditPersistenceOutcomeEvidenceMode
    assert AuditPersistenceOutcomeKind is PlanningAuditPersistenceOutcomeKind
    assert (
        PlanningAuditPersistenceOutcomeContract is StrategyPlanningAuditPersistenceOutcomeContract
    )
    assert (
        PlanningAuditPersistenceOutcomeContractFactory
        is StrategyPlanningAuditPersistenceOutcomeContractFactory
    )
    assert (
        StrategyAuditPersistenceOutcomeContract is StrategyPlanningAuditPersistenceOutcomeContract
    )
    assert (
        StrategyAuditPersistenceOutcomeContractFactory
        is StrategyPlanningAuditPersistenceOutcomeContractFactory
    )
