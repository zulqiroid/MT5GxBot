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
    AuditStorageAdapterAssessmentBlocker,
    AuditStorageAdapterAssessmentDecision,
    AuditStorageAdapterAssessmentGate,
    AuditStorageAdapterAssessmentMetrics,
    AuditStorageAdapterAssessmentPolicy,
    AuditStorageAdapterAssessmentReason,
    AuditStorageAdapterAssessmentStatus,
    AuditStorageAdapterCapability,
    AuditStorageAdapterCapabilitySnapshot,
    PlanningAuditStorageAdapterAssessmentBlocker,
    PlanningAuditStorageAdapterAssessmentDecision,
    PlanningAuditStorageAdapterAssessmentError,
    PlanningAuditStorageAdapterAssessmentErrorReason,
    PlanningAuditStorageAdapterAssessmentMetrics,
    PlanningAuditStorageAdapterAssessmentPolicy,
    PlanningAuditStorageAdapterAssessmentReason,
    PlanningAuditStorageAdapterAssessmentStatus,
    PlanningAuditStorageAdapterCapability,
    PlanningAuditStorageAdapterCapabilitySnapshot,
    StrategyAuditStorageAdapterAssessmentGate,
    StrategyPlanningAuditStorageAdapterAssessmentGate,
    assess_planning_audit_storage_adapter,
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


def test_default_policy_is_strict() -> None:
    policy = PlanningAuditStorageAdapterAssessmentPolicy()

    assert policy.require_non_stale_snapshot is True
    assert policy.require_active_adapter is True
    assert policy.require_invocation_disabled is True
    assert policy.require_append_if_absent is True
    assert policy.require_duplicate_return_existing is True
    assert policy.require_integrity_verification is True
    assert policy.require_encryption_at_rest is True
    assert policy.require_idempotency_lookup is True
    assert policy.require_retention_enforcement is True
    assert policy.require_dry_run_only is True


@pytest.mark.parametrize(
    "field_name",
    [
        "require_non_stale_snapshot",
        "require_active_adapter",
        "require_invocation_disabled",
        "require_append_if_absent",
        "require_duplicate_return_existing",
        "require_integrity_verification",
        "require_encryption_at_rest",
        "require_idempotency_lookup",
        "require_retention_enforcement",
        "require_dry_run_only",
    ],
)
def test_policy_rejects_non_boolean_values(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        PlanningAuditStorageAdapterAssessmentPolicy(**{field_name: 1})


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PlanningAuditStorageAdapterAssessmentPolicy",
    ):
        StrategyPlanningAuditStorageAdapterAssessmentGate(policy="invalid")


def test_invalid_contract_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdapterAssessmentError,
        match="INVALID_ADAPTER_CONTRACT_DECISION",
    ) as captured:
        (StrategyPlanningAuditStorageAdapterAssessmentGate().assess("invalid"))

    assert captured.value.reason == (
        PlanningAuditStorageAdapterAssessmentErrorReason.INVALID_ADAPTER_CONTRACT_DECISION
    )


def test_created_contract_requires_snapshot() -> None:
    with pytest.raises(
        PlanningAuditStorageAdapterAssessmentError,
        match="INVALID_CAPABILITY_SNAPSHOT",
    ):
        (StrategyPlanningAuditStorageAdapterAssessmentGate().assess(bullish_adapter_contract()))


def test_invalid_snapshot_type_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdapterAssessmentError,
        match="INVALID_CAPABILITY_SNAPSHOT",
    ):
        (
            StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
                bullish_adapter_contract(),
                "invalid",
            )
        )


def test_blocked_contract_requires_no_snapshot() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        blocked_adapter_contract()
    )

    assert decision.is_blocked is True
    assert decision.snapshot is None
    assert decision.metrics is None
    assert decision.reason == (PlanningAuditStorageAdapterAssessmentReason.ADAPTER_CONTRACT_BLOCKED)
    assert decision.blockers == (
        PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_CONTRACT_BLOCKED,
    )


def test_bullish_adapter_is_compatible() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    assert decision.status == (PlanningAuditStorageAdapterAssessmentStatus.COMPATIBLE)
    assert decision.reason == (PlanningAuditStorageAdapterAssessmentReason.COMPATIBLE)
    assert decision.blockers == ()
    assert decision.is_compatible is True


def test_bearish_adapter_is_compatible() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bearish_adapter_contract(),
        capability_snapshot(),
    )

    assert decision.is_compatible is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.side == StrategyOrderSide.SELL


def test_snapshot_is_read_only() -> None:
    snapshot = capability_snapshot()

    assert snapshot.is_read_only_snapshot is True
    assert snapshot.can_invoke_adapter is False
    assert snapshot.can_write_storage is False
    assert snapshot.capability_count == 7


def test_decision_preserves_contract_and_snapshot() -> None:
    contract = bullish_adapter_contract()
    snapshot = capability_snapshot()
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(contract, snapshot)

    assert decision.adapter_contract is contract
    assert decision.contract is contract.contract_required
    assert decision.snapshot is snapshot


def test_decision_preserves_metadata() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.side == StrategyOrderSide.BUY


def test_same_time_snapshot_is_current() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(observed_at=OBSERVED_AT),
    )

    assert decision.is_compatible is True


def test_stale_snapshot_is_blocked() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.blockers == (PlanningAuditStorageAdapterAssessmentBlocker.SNAPSHOT_STALE,)


def test_stale_snapshot_can_be_allowed() -> None:
    policy = PlanningAuditStorageAdapterAssessmentPolicy(require_non_stale_snapshot=False)
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate(policy).assess(
        bullish_adapter_contract(),
        capability_snapshot(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.is_compatible is True


@pytest.mark.parametrize(
    ("snapshot_overrides", "expected_blocker"),
    [
        (
            {"active": False},
            PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_INACTIVE,
        ),
        (
            {"invocation_enabled": True},
            PlanningAuditStorageAdapterAssessmentBlocker.INVOCATION_ENABLED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
                    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
                    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
                    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
                    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
                    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.APPEND_IF_ABSENT_UNSUPPORTED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
                    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
                    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
                    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
                    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.DUPLICATE_POLICY_UNSUPPORTED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
                    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
                    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
                    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
                    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.INTEGRITY_VERIFICATION_UNSUPPORTED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
                    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
                    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
                    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
                    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.ENCRYPTION_UNSUPPORTED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
                    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
                    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
                    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
                    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.IDEMPOTENCY_UNSUPPORTED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
                    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
                    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
                    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
                    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.RETENTION_ENFORCEMENT_UNSUPPORTED,
        ),
        (
            {
                "capabilities": (
                    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
                    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
                    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
                    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
                    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
                )
            },
            PlanningAuditStorageAdapterAssessmentBlocker.DRY_RUN_CAPABILITY_REQUIRED,
        ),
        (
            {"maximum_payload_bytes": 1},
            PlanningAuditStorageAdapterAssessmentBlocker.PAYLOAD_TOO_LARGE,
        ),
        (
            {"maximum_retention_days": 1},
            PlanningAuditStorageAdapterAssessmentBlocker.RETENTION_TOO_SHORT,
        ),
    ],
)
def test_individual_adapter_blockers(
    snapshot_overrides: dict[str, object],
    expected_blocker: (PlanningAuditStorageAdapterAssessmentBlocker),
) -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(**snapshot_overrides),
    )

    assert decision.is_blocked is True
    assert decision.blockers == (expected_blocker,)


def test_target_mismatch_is_blocked() -> None:
    source_snapshot = capability_snapshot()
    foreign_snapshot = object.__new__(PlanningAuditStorageAdapterCapabilitySnapshot)

    for field_name in (
        "observed_at",
        "adapter_name",
        "active",
        "invocation_enabled",
        "capabilities",
        "maximum_payload_bytes",
        "maximum_retention_days",
    ):
        object.__setattr__(
            foreign_snapshot,
            field_name,
            getattr(source_snapshot, field_name),
        )

    # The public snapshot constructor correctly rejects raw
    # targets. This isolated forged snapshot exists only to
    # exercise the assessment gate's defensive mismatch
    # branch without adding a second production target.
    object.__setattr__(
        foreign_snapshot,
        "target",
        "FOREIGN_AUDIT_TARGET",
    )

    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        foreign_snapshot,
    )

    assert decision.is_blocked is True
    assert decision.reason == (PlanningAuditStorageAdapterAssessmentReason.TARGET_MISMATCH)
    assert decision.blockers == (PlanningAuditStorageAdapterAssessmentBlocker.TARGET_MISMATCH,)


def test_multiple_blockers_are_deterministic() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(
            observed_at=(OBSERVED_AT - timedelta(seconds=1)),
            active=False,
            invocation_enabled=True,
            capabilities=(),
            maximum_payload_bytes=1,
            maximum_retention_days=1,
        ),
    )

    assert decision.reason == (
        PlanningAuditStorageAdapterAssessmentReason.MULTIPLE_ADAPTER_BLOCKERS
    )
    assert decision.blockers == (
        PlanningAuditStorageAdapterAssessmentBlocker.SNAPSHOT_STALE,
        PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_INACTIVE,
        PlanningAuditStorageAdapterAssessmentBlocker.INVOCATION_ENABLED,
        PlanningAuditStorageAdapterAssessmentBlocker.APPEND_IF_ABSENT_UNSUPPORTED,
        PlanningAuditStorageAdapterAssessmentBlocker.DUPLICATE_POLICY_UNSUPPORTED,
        PlanningAuditStorageAdapterAssessmentBlocker.INTEGRITY_VERIFICATION_UNSUPPORTED,
        PlanningAuditStorageAdapterAssessmentBlocker.ENCRYPTION_UNSUPPORTED,
        PlanningAuditStorageAdapterAssessmentBlocker.IDEMPOTENCY_UNSUPPORTED,
        PlanningAuditStorageAdapterAssessmentBlocker.RETENTION_ENFORCEMENT_UNSUPPORTED,
        PlanningAuditStorageAdapterAssessmentBlocker.DRY_RUN_CAPABILITY_REQUIRED,
        PlanningAuditStorageAdapterAssessmentBlocker.PAYLOAD_TOO_LARGE,
        PlanningAuditStorageAdapterAssessmentBlocker.RETENTION_TOO_SHORT,
    )


def test_exact_payload_limit_is_compatible() -> None:
    required = bullish_adapter_contract().contract_required.content_length_bytes
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(maximum_payload_bytes=required),
    )

    assert decision.is_compatible is True
    assert decision.metrics_required.payload_surplus_bytes == 0
    assert decision.metrics_required.payload_deficit_bytes == 0


def test_payload_deficit_is_exact() -> None:
    required = bullish_adapter_contract().contract_required.content_length_bytes
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(maximum_payload_bytes=required - 1),
    )

    assert decision.metrics_required.payload_deficit_bytes == 1


def test_exact_retention_limit_is_compatible() -> None:
    required = bullish_adapter_contract().contract_required.retention_days
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(maximum_retention_days=required),
    )

    assert decision.is_compatible is True
    assert decision.metrics_required.retention_surplus_days == 0
    assert decision.metrics_required.retention_deficit_days == 0


def test_retention_deficit_is_exact() -> None:
    required = bullish_adapter_contract().contract_required.retention_days
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(maximum_retention_days=required - 1),
    )

    assert decision.metrics_required.retention_deficit_days == 1


def test_compatible_result_continues_only_to_design() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    assert decision.can_continue_to_adapter_binding_design is True
    assert decision.adapter_binding_authorized is False
    assert decision.adapter_invocation_authorized is False


def test_blocked_result_cannot_continue() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(active=False),
    )

    assert decision.can_continue_to_adapter_binding_design is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

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
        "repository",
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
def test_decision_contains_no_implementation_surface(
    attribute_name: str,
) -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    assert not hasattr(decision, attribute_name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"observed_at": "invalid"},
        {
            "observed_at": datetime(
                2026,
                7,
                26,
                20,
                0,
            )
        },
        {"adapter_name": ""},
        {"target": "AUDIT_ARCHIVE"},
        {"active": 1},
        {"invocation_enabled": 1},
        {"capabilities": []},
        {"capabilities": ("APPEND_IF_ABSENT",)},
        {
            "capabilities": (
                PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
                PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
            )
        },
        {
            "capabilities": (
                PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
                PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
            )
        },
        {"maximum_payload_bytes": 0},
        {"maximum_payload_bytes": True},
        {"maximum_retention_days": 0},
        {"maximum_retention_days": True},
    ],
)
def test_invalid_snapshot_is_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "observed_at": OBSERVED_AT,
        "adapter_name": "injected-audit-adapter",
        "target": (PlanningAuditStorageTarget.AUDIT_ARCHIVE),
        "active": True,
        "invocation_enabled": False,
        "capabilities": (
            PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
            PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
            PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
            PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
            PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
            PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
            PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
        ),
        "maximum_payload_bytes": 1_000_000,
        "maximum_retention_days": 3650,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        PlanningAuditStorageAdapterCapabilitySnapshot(**values)


def test_snapshot_stable_id_is_deterministic() -> None:
    snapshot = capability_snapshot()
    capabilities = ",".join(capability.value for capability in snapshot.capabilities)

    assert snapshot.stable_id == (
        f"{OBSERVED_AT.isoformat()}:"
        "injected-audit-adapter:"
        "AUDIT_ARCHIVE:"
        "ACTIVE[True]:"
        "INVOCATION_ENABLED[False]:"
        f"CAPABILITIES[{capabilities}]:"
        "MAX_PAYLOAD_BYTES[1000000]:"
        "MAX_RETENTION_DAYS[3650]"
    )


def test_metrics_stable_id_is_deterministic() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )
    metrics = decision.metrics_required

    assert metrics.stable_id == (
        f"REQUIRED_PAYLOAD["
        f"{metrics.required_payload_bytes}]:"
        "MAXIMUM_PAYLOAD[1000000]:"
        f"PAYLOAD_SURPLUS["
        f"{metrics.payload_surplus_bytes}]:"
        "PAYLOAD_DEFICIT[0]:"
        "REQUIRED_RETENTION[365]:"
        "MAXIMUM_RETENTION[3650]:"
        "RETENTION_SURPLUS[3285]:"
        "RETENTION_DEFICIT[0]"
    )


def test_compatible_stable_id_is_deterministic() -> None:
    contract = bullish_adapter_contract()
    snapshot = capability_snapshot()
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(contract, snapshot)

    assert decision.stable_id == (
        f"{contract.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_ASSESSMENT:"
        "COMPATIBLE:COMPATIBLE:NONE:"
        f"{snapshot.stable_id}:"
        f"{decision.metrics_required.stable_id}"
    )


def test_blocked_stable_id_is_deterministic() -> None:
    contract = blocked_adapter_contract()
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(contract)

    assert decision.stable_id.endswith(
        "PLANNING_AUDIT_STORAGE_ADAPTER_ASSESSMENT:"
        "BLOCKED:ADAPTER_CONTRACT_BLOCKED:"
        "ADAPTER_CONTRACT_BLOCKED:"
        "NO_CAPABILITY_SNAPSHOT:"
        "NO_ASSESSMENT_METRICS"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=(PlanningAuditStorageAdapterAssessmentStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditStorageAdapterAssessmentReason.ADAPTER_INACTIVE),
        )


def test_manual_decision_rejects_missing_snapshot() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    with pytest.raises(
        PlanningAuditStorageAdapterAssessmentError,
        match="INVALID_CAPABILITY_SNAPSHOT",
    ):
        replace(
            decision,
            snapshot=None,
        )


def test_manual_decision_rejects_wrong_metrics() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )
    metrics = decision.metrics_required
    modified = replace(
        metrics,
        maximum_payload_bytes=(metrics.maximum_payload_bytes + 1),
        payload_surplus_bytes=(metrics.payload_surplus_bytes + 1),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            metrics=modified,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(active=False),
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_INACTIVE,
                PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_INACTIVE,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = PlanningAuditStorageAdapterAssessmentPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.require_active_adapter = False


def test_snapshot_is_immutable() -> None:
    snapshot = capability_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.active = False


def test_metrics_are_immutable() -> None:
    metrics = (
        StrategyPlanningAuditStorageAdapterAssessmentGate()
        .assess(
            bullish_adapter_contract(),
            capability_snapshot(),
        )
        .metrics_required
    )

    with pytest.raises(FrozenInstanceError):
        metrics.required_payload_bytes = 1


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditStorageAdapterAssessmentStatus.BLOCKED


def test_assessment_is_deterministic() -> None:
    gate = StrategyPlanningAuditStorageAdapterAssessmentGate()
    contract = bullish_adapter_contract()
    snapshot = capability_snapshot()

    assert gate.assess(
        contract,
        snapshot,
    ) == gate.assess(
        contract,
        snapshot,
    )


def test_function_api_delegates() -> None:
    decision = assess_planning_audit_storage_adapter(
        bullish_adapter_contract(),
        capability_snapshot(),
    )

    assert decision.is_compatible is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPlanningAuditStorageAdapterAssessmentGate()
    contract = bullish_adapter_contract()
    snapshot = capability_snapshot()

    assert gate.evaluate(
        contract,
        snapshot,
    ) == gate.assess(
        contract,
        snapshot,
    )
    assert gate.check(
        contract,
        snapshot,
    ) == gate.assess(
        contract,
        snapshot,
    )


def test_public_aliases_are_preserved() -> None:
    assert AuditStorageAdapterAssessmentBlocker is PlanningAuditStorageAdapterAssessmentBlocker
    assert AuditStorageAdapterAssessmentDecision is PlanningAuditStorageAdapterAssessmentDecision
    assert AuditStorageAdapterAssessmentGate is StrategyPlanningAuditStorageAdapterAssessmentGate
    assert AuditStorageAdapterAssessmentMetrics is PlanningAuditStorageAdapterAssessmentMetrics
    assert AuditStorageAdapterAssessmentPolicy is PlanningAuditStorageAdapterAssessmentPolicy
    assert AuditStorageAdapterAssessmentReason is PlanningAuditStorageAdapterAssessmentReason
    assert AuditStorageAdapterAssessmentStatus is PlanningAuditStorageAdapterAssessmentStatus
    assert AuditStorageAdapterCapability is PlanningAuditStorageAdapterCapability
    assert AuditStorageAdapterCapabilitySnapshot is PlanningAuditStorageAdapterCapabilitySnapshot
    assert (
        StrategyAuditStorageAdapterAssessmentGate
        is StrategyPlanningAuditStorageAdapterAssessmentGate
    )
