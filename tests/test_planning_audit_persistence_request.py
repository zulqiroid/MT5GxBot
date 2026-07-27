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
from app.strategy.planning_audit_persistence_request import (
    PLANNING_AUDIT_PERSISTENCE_REQUEST_SCHEMA_VERSION,
    AuditPersistenceInvocationMode,
    AuditPersistenceRequest,
    AuditPersistenceRequestDecision,
    AuditPersistenceRequestFactory,
    AuditPersistenceRequestMode,
    PlanningAuditPersistenceInvocationMode,
    PlanningAuditPersistenceRequest,
    PlanningAuditPersistenceRequestBlocker,
    PlanningAuditPersistenceRequestDecision,
    PlanningAuditPersistenceRequestError,
    PlanningAuditPersistenceRequestErrorReason,
    PlanningAuditPersistenceRequestFactory,
    PlanningAuditPersistenceRequestMode,
    PlanningAuditPersistenceRequestReason,
    PlanningAuditPersistenceRequestStatus,
    StrategyAuditPersistenceRequest,
    StrategyAuditPersistenceRequestFactory,
    StrategyPlanningAuditPersistenceRequestBlueprint,
    StrategyPlanningAuditPersistenceRequestFactory,
    generate_planning_audit_persistence_request,
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
    PlanningAuditStorageAdapterInvocationMode,
    StrategyPlanningAuditStorageAdapterBindingFactory,
)
from app.strategy.planning_audit_storage_adapter_binding_verification import (
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory,
)
from app.strategy.planning_audit_storage_adapter_contract import (
    PlanningAuditStorageAdapterOperation,
    PlanningAuditStorageDuplicatePolicy,
    PlanningAuditStorageIntegrityPolicy,
    PlanningAuditStorageResultExpectation,
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


def test_invalid_verification_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditPersistenceRequestError,
        match="INVALID_BINDING_VERIFICATION_DECISION",
    ) as captured:
        (StrategyPlanningAuditPersistenceRequestFactory().generate("invalid"))

    assert captured.value.reason == (
        PlanningAuditPersistenceRequestErrorReason.INVALID_BINDING_VERIFICATION_DECISION
    )


def test_bullish_request_is_created() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
    )

    assert decision.status == (PlanningAuditPersistenceRequestStatus.CREATED)
    assert decision.reason == (PlanningAuditPersistenceRequestReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_request is True


def test_bearish_request_is_created() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bearish_binding_verification()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.request_required.side == StrategyOrderSide.SELL


def test_blocked_verification_produces_no_request() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        blocked_binding_verification()
    )

    assert decision.is_blocked is True
    assert decision.request is None
    assert decision.has_request is False
    assert decision.reason == (PlanningAuditPersistenceRequestReason.BINDING_VERIFICATION_BLOCKED)
    assert decision.blockers == (
        PlanningAuditPersistenceRequestBlocker.BINDING_VERIFICATION_BLOCKED,
    )


def test_request_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        blocked_binding_verification()
    )

    with pytest.raises(
        ValueError,
        match="No planning-audit persistence request",
    ):
        _ = decision.request_required


def test_request_preserves_verification_decision() -> None:
    verification = bullish_binding_verification()
    request = (
        StrategyPlanningAuditPersistenceRequestFactory().generate(verification).request_required
    )

    assert request.binding_verification is verification
    assert request.receipt is verification.receipt_required


def test_request_preserves_binding_lineage() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.binding is request.receipt.binding
    assert request.snapshot is request.receipt.snapshot
    assert request.contract is request.receipt.contract


def test_request_preserves_metadata() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.broker_symbol == "XAUUSDm"
    assert request.observed_at == OBSERVED_AT
    assert request.direction == (DirectionalPermissionDirection.BULLISH)
    assert request.side == StrategyOrderSide.BUY
    assert request.schema_version == (PLANNING_AUDIT_PERSISTENCE_REQUEST_SCHEMA_VERSION)


def test_request_is_prepare_only() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.request_mode == (PlanningAuditPersistenceRequestMode.PREPARE_ONLY)
    assert request.is_prepare_only is True


def test_request_invocation_is_disabled() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.invocation_mode == (PlanningAuditPersistenceInvocationMode.DISABLED)
    assert request.binding.invocation_mode == PlanningAuditStorageAdapterInvocationMode.DISABLED


def test_request_preserves_adapter_reference() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.adapter_name == (request.snapshot.adapter_name)
    assert request.target == request.snapshot.target
    assert request.target == request.contract.target


def test_request_preserves_contract_semantics() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    contract = request.contract

    assert request.operation == contract.operation
    assert request.operation == (PlanningAuditStorageAdapterOperation.APPEND_IF_ABSENT)
    assert request.duplicate_policy == contract.duplicate_policy
    assert request.duplicate_policy == (PlanningAuditStorageDuplicatePolicy.RETURN_EXISTING)
    assert request.integrity_policy == contract.integrity_policy
    assert request.integrity_policy == (PlanningAuditStorageIntegrityPolicy.VERIFY_BEFORE_ACCEPT)
    assert request.result_expectation == contract.result_expectation
    assert request.result_expectation == (PlanningAuditStorageResultExpectation.CREATED_OR_EXISTING)


def test_request_preserves_payload() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    contract = request.contract

    assert request.content == contract.content
    assert request.content_bytes == contract.content_bytes
    assert request.content_length_bytes == (contract.content_length_bytes)
    assert len(request.content_bytes) == (request.content_length_bytes)


def test_request_preserves_digest_lineage() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    receipt = request.receipt
    contract = request.contract

    assert request.content_digest == (contract.content_digest)
    assert request.content_digest == (receipt.verified_content_digest)
    assert request.manifest_digest == (contract.manifest_digest)
    assert request.manifest_digest == (receipt.verified_manifest_digest)
    assert request.idempotency_key == (contract.idempotency_key)
    assert request.idempotency_key == (receipt.verified_idempotency_key)


def test_request_preserves_retention() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.retention_days == (request.contract.retention_days)


def test_request_preserves_verified_identities() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    receipt = request.receipt

    assert request.binding_verification_receipt_digest == receipt.receipt_digest
    assert request.binding_id == (receipt.verified_binding_id)
    assert request.binding_id == (request.binding.binding_id)
    assert request.snapshot_id == (receipt.verified_snapshot_id)
    assert request.snapshot_id == (request.snapshot.stable_id)
    assert request.contract_id == (receipt.verified_contract_id)
    assert request.contract_id == (request.contract.contract_id)


@pytest.mark.parametrize(
    "field_name",
    [
        "content_digest",
        "manifest_digest",
        "idempotency_key",
        "binding_verification_receipt_digest",
        "request_digest",
    ],
)
def test_request_digests_are_lowercase_sha256(
    field_name: str,
) -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    value = getattr(request, field_name)

    assert len(value) == 64
    assert value == value.lower()
    assert set(value) <= set("0123456789abcdef")


def test_request_digest_matches_canonical_payload() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    expected = hashlib.sha256(request.canonical_payload.encode("utf-8")).hexdigest()

    assert request.request_digest == expected
    assert request.digest_algorithm == "SHA-256"


def test_request_is_ready_for_verification_design_only() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
    )

    assert request.is_request_blueprint_ready is True
    assert request.can_continue_to_request_verification_design is True
    assert decision.can_continue_to_request_verification_design is True


def test_request_performs_no_write_or_execution() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.has_adapter_instance is False
    assert request.request_submission_authorized is False
    assert request.adapter_invocation_authorized is False
    assert request.storage_write_authorized is False
    assert request.is_persisted is False
    assert request.can_write_storage is False
    assert request.can_write_network is False
    assert request.execution_authorized is False
    assert request.has_broker_request is False
    assert request.can_submit_order is False
    assert request.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
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
def test_request_contains_no_implementation_surface(
    attribute_name: str,
) -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert not hasattr(request, attribute_name)


def test_request_id_is_deterministic() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    assert request.request_id == (
        "XAUUSDm:BUY:"
        "AUDIT_PERSISTENCE_REQUEST:"
        "injected-audit-adapter:"
        "AUDIT_ARCHIVE:"
        "PREPARE_ONLY:"
        "DISABLED:"
        "APPEND_IF_ABSENT:"
        f"IDEMPOTENCY_SHA256["
        f"{request.idempotency_key}]:"
        f"REQUEST_SHA256[{request.request_digest}]"
    )


def test_request_stable_id_is_deterministic() -> None:
    verification = bullish_binding_verification()
    request = (
        StrategyPlanningAuditPersistenceRequestFactory().generate(verification).request_required
    )

    assert request.stable_id == (
        f"{verification.stable_id}:PLANNING_AUDIT_PERSISTENCE_REQUEST:{request.request_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    verification = bullish_binding_verification()
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(verification)

    assert decision.stable_id == (
        f"{verification.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_REQUEST_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    verification = blocked_binding_verification()
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(verification)

    assert decision.stable_id == (
        f"{verification.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_REQUEST_GENERATION:"
        "BLOCKED:BINDING_VERIFICATION_BLOCKED:"
        "BINDING_VERIFICATION_BLOCKED"
    )


def test_direct_request_rejects_blocked_verification() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(
        ValueError,
        match="verified adapter-binding decision",
    ):
        replace(
            request,
            binding_verification=(blocked_binding_verification()),
        )


def test_direct_request_rejects_wrong_schema() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            request,
            schema_version="2.0",
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "request_mode",
            "PREPARE_ONLY",
            "PlanningAuditPersistenceRequestMode",
        ),
        (
            "invocation_mode",
            "DISABLED",
            "PlanningAuditPersistenceInvocationMode",
        ),
        (
            "target",
            "AUDIT_ARCHIVE",
            "PlanningAuditStorageTarget",
        ),
        (
            "operation",
            "APPEND_IF_ABSENT",
            "PlanningAuditStorageAdapterOperation",
        ),
        (
            "duplicate_policy",
            "RETURN_EXISTING",
            "PlanningAuditStorageDuplicatePolicy",
        ),
        (
            "integrity_policy",
            "VERIFY_BEFORE_ACCEPT",
            "PlanningAuditStorageIntegrityPolicy",
        ),
        (
            "result_expectation",
            "CREATED_OR_EXISTING",
            "PlanningAuditStorageResultExpectation",
        ),
    ],
)
def test_direct_request_rejects_raw_enums(
    field_name: str,
    value: str,
    message: str,
) -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(ValueError, match=message):
        replace(
            request,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("adapter_name", "foreign-adapter"),
        ("content", "{}"),
        ("content_length_bytes", 1),
        ("content_digest", "0" * 64),
        ("manifest_digest", "0" * 64),
        ("idempotency_key", "0" * 64),
        ("retention_days", 1),
        (
            "binding_verification_receipt_digest",
            "0" * 64,
        ),
        ("binding_id", "foreign-binding"),
        ("snapshot_id", "foreign-snapshot"),
        ("contract_id", "foreign-contract"),
        ("request_digest", "0" * 64),
    ],
)
def test_direct_request_rejects_foreign_values(
    field_name: str,
    value: object,
) -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(ValueError, match=field_name):
        replace(
            request,
            **{field_name: value},
        )


def test_direct_request_rejects_uppercase_digest() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(
        ValueError,
        match="lowercase",
    ):
        replace(
            request,
            request_digest="A" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PlanningAuditPersistenceRequestStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditPersistenceRequestReason.BINDING_VERIFICATION_BLOCKED),
        )


def test_manual_decision_rejects_missing_request() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            request=None,
        )


def test_manual_decision_rejects_unexpected_request() -> None:
    blocked = StrategyPlanningAuditPersistenceRequestFactory().generate(
        blocked_binding_verification()
    )
    created_request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            request=created_request,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        blocked_binding_verification()
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditPersistenceRequestBlocker.BINDING_VERIFICATION_BLOCKED,
                PlanningAuditPersistenceRequestBlocker.BINDING_VERIFICATION_BLOCKED,
            ),
        )


def test_request_is_immutable() -> None:
    request = (
        StrategyPlanningAuditPersistenceRequestFactory()
        .generate(bullish_binding_verification())
        .request_required
    )

    with pytest.raises(FrozenInstanceError):
        request.adapter_name = "modified"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditPersistenceRequestFactory().generate(
        bullish_binding_verification()
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditPersistenceRequestStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditPersistenceRequestFactory()
    verification = bullish_binding_verification()

    assert factory.generate(verification) == factory.generate(verification)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_persistence_request(bullish_binding_verification())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditPersistenceRequestFactory()
    verification = bullish_binding_verification()

    assert factory.build(verification) == factory.generate(verification)
    assert factory.evaluate(verification) == factory.generate(verification)


def test_public_aliases_are_preserved() -> None:
    assert AuditPersistenceRequest is StrategyPlanningAuditPersistenceRequestBlueprint
    assert AuditPersistenceRequestDecision is PlanningAuditPersistenceRequestDecision
    assert AuditPersistenceRequestFactory is StrategyPlanningAuditPersistenceRequestFactory
    assert AuditPersistenceRequestMode is PlanningAuditPersistenceRequestMode
    assert AuditPersistenceInvocationMode is PlanningAuditPersistenceInvocationMode
    assert PlanningAuditPersistenceRequest is StrategyPlanningAuditPersistenceRequestBlueprint
    assert PlanningAuditPersistenceRequestFactory is StrategyPlanningAuditPersistenceRequestFactory
    assert StrategyAuditPersistenceRequest is StrategyPlanningAuditPersistenceRequestBlueprint
    assert StrategyAuditPersistenceRequestFactory is StrategyPlanningAuditPersistenceRequestFactory
