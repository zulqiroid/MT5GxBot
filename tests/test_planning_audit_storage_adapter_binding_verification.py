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
from app.strategy.planning_audit_record import (
    StrategyPlanningAuditRecordFactory,
)
from app.strategy.planning_audit_storage_adapter_assessment import (
    PlanningAuditStorageAdapterCapability,
    PlanningAuditStorageAdapterCapabilitySnapshot,
    StrategyPlanningAuditStorageAdapterAssessmentGate,
)
from app.strategy.planning_audit_storage_adapter_binding import (
    PlanningAuditStorageAdapterBindingMode,
    PlanningAuditStorageAdapterBindingVerificationMode,
    PlanningAuditStorageAdapterInvocationMode,
    StrategyPlanningAuditStorageAdapterBindingFactory,
)
from app.strategy.planning_audit_storage_adapter_binding_verification import (
    PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_VERIFICATION_SCHEMA_VERSION,
    AuditStorageAdapterBindingVerificationBlocker,
    AuditStorageAdapterBindingVerificationCheck,
    AuditStorageAdapterBindingVerificationDecision,
    AuditStorageAdapterBindingVerificationFactory,
    AuditStorageAdapterBindingVerificationReason,
    AuditStorageAdapterBindingVerificationReceipt,
    AuditStorageAdapterBindingVerificationStatus,
    PlanningAuditStorageAdapterBindingVerificationBlocker,
    PlanningAuditStorageAdapterBindingVerificationCheck,
    PlanningAuditStorageAdapterBindingVerificationDecision,
    PlanningAuditStorageAdapterBindingVerificationError,
    PlanningAuditStorageAdapterBindingVerificationErrorReason,
    PlanningAuditStorageAdapterBindingVerificationFactory,
    PlanningAuditStorageAdapterBindingVerificationReason,
    PlanningAuditStorageAdapterBindingVerificationReceipt,
    PlanningAuditStorageAdapterBindingVerificationStatus,
    StrategyAuditStorageAdapterBindingVerificationFactory,
    StrategyAuditStorageAdapterBindingVerificationReceipt,
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory,
    StrategyPlanningAuditStorageAdapterBindingVerificationReceipt,
    verify_planning_audit_storage_adapter_binding,
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


def test_invalid_binding_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdapterBindingVerificationError,
        match="INVALID_ADAPTER_BINDING_DECISION",
    ) as captured:
        (StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify("invalid"))

    assert captured.value.reason == (
        PlanningAuditStorageAdapterBindingVerificationErrorReason.INVALID_ADAPTER_BINDING_DECISION
    )


def test_bullish_binding_is_verified() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )

    assert decision.status == (PlanningAuditStorageAdapterBindingVerificationStatus.VERIFIED)
    assert decision.reason == (PlanningAuditStorageAdapterBindingVerificationReason.VERIFIED)
    assert decision.blockers == ()
    assert decision.is_verified is True
    assert decision.has_receipt is True


def test_bearish_binding_is_verified() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bearish_adapter_binding()
    )

    assert decision.is_verified is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.receipt_required.side == StrategyOrderSide.SELL


def test_blocked_binding_produces_no_receipt() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        blocked_adapter_binding()
    )

    assert decision.is_blocked is True
    assert decision.receipt is None
    assert decision.has_receipt is False
    assert decision.reason == (
        PlanningAuditStorageAdapterBindingVerificationReason.ADAPTER_BINDING_BLOCKED
    )
    assert decision.blockers == (
        PlanningAuditStorageAdapterBindingVerificationBlocker.ADAPTER_BINDING_BLOCKED,
    )


def test_receipt_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        blocked_adapter_binding()
    )

    with pytest.raises(
        ValueError,
        match="No adapter-binding verification receipt",
    ):
        _ = decision.receipt_required


def test_receipt_preserves_binding_decision() -> None:
    binding_decision = bullish_adapter_binding()
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(binding_decision)
        .receipt_required
    )

    assert receipt.adapter_binding is binding_decision
    assert receipt.binding is (binding_decision.binding_required)


def test_receipt_preserves_snapshot_and_contract() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.snapshot is receipt.binding.snapshot
    assert receipt.contract is receipt.binding.contract


def test_receipt_preserves_metadata() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.broker_symbol == "XAUUSDm"
    assert receipt.observed_at == OBSERVED_AT
    assert receipt.direction == (DirectionalPermissionDirection.BULLISH)
    assert receipt.side == StrategyOrderSide.BUY
    assert receipt.schema_version == (
        PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_VERIFICATION_SCHEMA_VERSION
    )


def test_all_required_checks_are_present() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.checks == (
        PlanningAuditStorageAdapterBindingVerificationCheck.REFERENCE_ONLY_MODE,
        PlanningAuditStorageAdapterBindingVerificationCheck.INVOCATION_DISABLED,
        PlanningAuditStorageAdapterBindingVerificationCheck.SNAPSHOT_ID_MATCH,
        PlanningAuditStorageAdapterBindingVerificationCheck.CONTRACT_ID_MATCH,
        PlanningAuditStorageAdapterBindingVerificationCheck.CONTRACT_SEMANTICS_MATCH,
        PlanningAuditStorageAdapterBindingVerificationCheck.DIGEST_LINEAGE_MATCH,
        PlanningAuditStorageAdapterBindingVerificationCheck.IDEMPOTENCY_KEY_MATCH,
        PlanningAuditStorageAdapterBindingVerificationCheck.NO_IMPLEMENTATION_SURFACE,
    )
    assert receipt.verification_count == 8


def test_binding_modes_are_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.binding.binding_mode == (PlanningAuditStorageAdapterBindingMode.REFERENCE_ONLY)
    assert receipt.binding.is_reference_only is True
    assert receipt.binding.invocation_mode == (PlanningAuditStorageAdapterInvocationMode.DISABLED)
    assert receipt.binding.verification_mode == (
        PlanningAuditStorageAdapterBindingVerificationMode.SNAPSHOT_AND_CONTRACT_LOCKED
    )


def test_binding_identity_is_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.verified_binding_id == (receipt.binding.binding_id)


def test_snapshot_identity_is_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.verified_snapshot_id == (receipt.binding.capability_snapshot_id)
    assert receipt.verified_snapshot_id == (receipt.snapshot.stable_id)


def test_contract_identity_is_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.verified_contract_id == (receipt.binding.contract_id)
    assert receipt.verified_contract_id == (receipt.contract.contract_id)


def test_contract_semantics_are_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )
    binding = receipt.binding
    contract = receipt.contract

    assert binding.operation == contract.operation
    assert binding.duplicate_policy == contract.duplicate_policy
    assert binding.integrity_policy == contract.integrity_policy
    assert binding.result_expectation == contract.result_expectation


def test_content_digest_lineage_is_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.verified_content_digest == (receipt.binding.content_digest)
    assert receipt.verified_content_digest == (receipt.contract.content_digest)


def test_manifest_digest_lineage_is_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.verified_manifest_digest == (receipt.binding.manifest_digest)
    assert receipt.verified_manifest_digest == (receipt.contract.manifest_digest)


def test_idempotency_lineage_is_verified() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.verified_idempotency_key == (receipt.binding.idempotency_key)
    assert receipt.verified_idempotency_key == (receipt.contract.idempotency_key)


@pytest.mark.parametrize(
    "field_name",
    [
        "verified_content_digest",
        "verified_manifest_digest",
        "verified_idempotency_key",
        "receipt_digest",
    ],
)
def test_receipt_digests_are_lowercase_sha256(
    field_name: str,
) -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )
    value = getattr(receipt, field_name)

    assert len(value) == 64
    assert value == value.lower()
    assert set(value) <= set("0123456789abcdef")


def test_receipt_digest_matches_canonical_payload() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )
    expected = hashlib.sha256(receipt.canonical_payload.encode("utf-8")).hexdigest()

    assert receipt.receipt_digest == expected
    assert receipt.digest_algorithm == "SHA-256"


def test_receipt_is_verified_and_tamper_evident() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.is_verified is True
    assert receipt.is_tamper_evident is True
    assert receipt.can_continue_to_persistence_request_design is True


def test_receipt_performs_no_write_or_execution() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.has_adapter_instance is False
    assert receipt.adapter_invocation_authorized is False
    assert receipt.storage_write_authorized is False
    assert receipt.is_persisted is False
    assert receipt.can_write_storage is False
    assert receipt.can_write_network is False
    assert receipt.execution_authorized is False
    assert receipt.has_broker_request is False
    assert receipt.can_submit_order is False
    assert receipt.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )

    assert decision.can_continue_to_persistence_request_design is True
    assert decision.has_adapter_instance is False
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
        "request",
        "order_request",
        "broker_ticket",
        "authorize",
        "submit",
        "send_order",
        "order_send",
    ],
)
def test_receipt_contains_no_implementation_surface(
    attribute_name: str,
) -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert not hasattr(receipt, attribute_name)


def test_receipt_id_is_deterministic() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    assert receipt.receipt_id == (
        "XAUUSDm:BUY:"
        "AUDIT_ADAPTER_BINDING_VERIFIED:"
        f"BINDING[{receipt.verified_binding_id}]:"
        f"RECEIPT_SHA256[{receipt.receipt_digest}]"
    )


def test_receipt_stable_id_is_deterministic() -> None:
    binding = bullish_adapter_binding()
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(binding)
        .receipt_required
    )

    assert receipt.stable_id == (
        f"{binding.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_"
        "VERIFICATION_RECEIPT:"
        f"{receipt.receipt_id}"
    )


def test_verified_decision_stable_id_is_deterministic() -> None:
    binding = bullish_adapter_binding()
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(binding)

    assert decision.stable_id == (
        f"{binding.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_"
        "VERIFICATION:"
        "VERIFIED:VERIFIED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    binding = blocked_adapter_binding()
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(binding)

    assert decision.stable_id == (
        f"{binding.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_"
        "VERIFICATION:"
        "BLOCKED:ADAPTER_BINDING_BLOCKED:"
        "ADAPTER_BINDING_BLOCKED"
    )


def test_direct_receipt_rejects_blocked_binding() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="created audit storage adapter binding",
    ):
        replace(
            receipt,
            adapter_binding=blocked_adapter_binding(),
        )


def test_direct_receipt_rejects_wrong_schema() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            receipt,
            schema_version="2.0",
        )


def test_direct_receipt_requires_tuple_checks() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="tuple",
    ):
        replace(
            receipt,
            checks=list(receipt.checks),
        )


def test_direct_receipt_rejects_raw_checks() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="verification check members",
    ):
        replace(
            receipt,
            checks=tuple(check.value for check in receipt.checks),
        )


def test_direct_receipt_rejects_missing_check() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="every required check",
    ):
        replace(
            receipt,
            checks=receipt.checks[:-1],
        )


def test_direct_receipt_rejects_reordered_checks() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            receipt,
            checks=tuple(reversed(receipt.checks)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("verified_binding_id", "foreign-binding"),
        ("verified_snapshot_id", "foreign-snapshot"),
        ("verified_contract_id", "foreign-contract"),
        ("verified_content_digest", "0" * 64),
        ("verified_manifest_digest", "0" * 64),
        ("verified_idempotency_key", "0" * 64),
        ("receipt_digest", "0" * 64),
    ],
)
def test_direct_receipt_rejects_foreign_values(
    field_name: str,
    value: str,
) -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(ValueError, match=field_name):
        replace(
            receipt,
            **{field_name: value},
        )


def test_direct_receipt_rejects_uppercase_digest() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="lowercase",
    ):
        replace(
            receipt,
            receipt_digest="A" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=(PlanningAuditStorageAdapterBindingVerificationStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditStorageAdapterBindingVerificationReason.ADAPTER_BINDING_BLOCKED),
        )


def test_manual_decision_rejects_missing_receipt() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            receipt=None,
        )


def test_manual_decision_rejects_unexpected_receipt() -> None:
    blocked = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        blocked_adapter_binding()
    )
    created_receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            receipt=created_receipt,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        blocked_adapter_binding()
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditStorageAdapterBindingVerificationBlocker.ADAPTER_BINDING_BLOCKED,
                PlanningAuditStorageAdapterBindingVerificationBlocker.ADAPTER_BINDING_BLOCKED,
            ),
        )


def test_receipt_is_immutable() -> None:
    receipt = (
        StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
        .verify(bullish_adapter_binding())
        .receipt_required
    )

    with pytest.raises(FrozenInstanceError):
        receipt.verified_binding_id = "modified"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditStorageAdapterBindingVerificationStatus.BLOCKED


def test_verification_is_deterministic() -> None:
    factory = StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
    binding = bullish_adapter_binding()

    assert factory.verify(binding) == factory.verify(binding)


def test_function_api_delegates() -> None:
    decision = verify_planning_audit_storage_adapter_binding(bullish_adapter_binding())

    assert decision.is_verified is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditStorageAdapterBindingVerificationFactory()
    binding = bullish_adapter_binding()

    assert factory.generate(binding) == factory.verify(binding)
    assert factory.evaluate(binding) == factory.verify(binding)


def test_public_aliases_are_preserved() -> None:
    assert (
        AuditStorageAdapterBindingVerificationBlocker
        is PlanningAuditStorageAdapterBindingVerificationBlocker
    )
    assert (
        AuditStorageAdapterBindingVerificationCheck
        is PlanningAuditStorageAdapterBindingVerificationCheck
    )
    assert (
        AuditStorageAdapterBindingVerificationDecision
        is PlanningAuditStorageAdapterBindingVerificationDecision
    )
    assert (
        AuditStorageAdapterBindingVerificationFactory
        is StrategyPlanningAuditStorageAdapterBindingVerificationFactory
    )
    assert (
        AuditStorageAdapterBindingVerificationReason
        is PlanningAuditStorageAdapterBindingVerificationReason
    )
    assert (
        AuditStorageAdapterBindingVerificationReceipt
        is StrategyPlanningAuditStorageAdapterBindingVerificationReceipt
    )
    assert (
        AuditStorageAdapterBindingVerificationStatus
        is PlanningAuditStorageAdapterBindingVerificationStatus
    )
    assert (
        PlanningAuditStorageAdapterBindingVerificationFactory
        is StrategyPlanningAuditStorageAdapterBindingVerificationFactory
    )
    assert (
        PlanningAuditStorageAdapterBindingVerificationReceipt
        is StrategyPlanningAuditStorageAdapterBindingVerificationReceipt
    )
    assert (
        StrategyAuditStorageAdapterBindingVerificationFactory
        is StrategyPlanningAuditStorageAdapterBindingVerificationFactory
    )
    assert (
        StrategyAuditStorageAdapterBindingVerificationReceipt
        is StrategyPlanningAuditStorageAdapterBindingVerificationReceipt
    )
