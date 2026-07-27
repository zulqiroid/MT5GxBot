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
    PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_SCHEMA_VERSION,
    AuditStorageAdapterBinding,
    AuditStorageAdapterBindingDecision,
    AuditStorageAdapterBindingFactory,
    AuditStorageAdapterBindingMode,
    AuditStorageAdapterBindingVerificationMode,
    AuditStorageAdapterInvocationMode,
    PlanningAuditStorageAdapterBinding,
    PlanningAuditStorageAdapterBindingBlocker,
    PlanningAuditStorageAdapterBindingDecision,
    PlanningAuditStorageAdapterBindingError,
    PlanningAuditStorageAdapterBindingErrorReason,
    PlanningAuditStorageAdapterBindingFactory,
    PlanningAuditStorageAdapterBindingMode,
    PlanningAuditStorageAdapterBindingReason,
    PlanningAuditStorageAdapterBindingStatus,
    PlanningAuditStorageAdapterBindingVerificationMode,
    PlanningAuditStorageAdapterInvocationMode,
    StrategyAuditStorageAdapterBinding,
    StrategyAuditStorageAdapterBindingFactory,
    StrategyPlanningAuditStorageAdapterBinding,
    StrategyPlanningAuditStorageAdapterBindingFactory,
    generate_planning_audit_storage_adapter_binding,
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


def test_invalid_assessment_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdapterBindingError,
        match="INVALID_ADAPTER_ASSESSMENT_DECISION",
    ) as captured:
        (StrategyPlanningAuditStorageAdapterBindingFactory().generate("invalid"))

    assert captured.value.reason == (
        PlanningAuditStorageAdapterBindingErrorReason.INVALID_ADAPTER_ASSESSMENT_DECISION
    )


def test_bullish_binding_is_created() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    assert decision.status == (PlanningAuditStorageAdapterBindingStatus.CREATED)
    assert decision.reason == (PlanningAuditStorageAdapterBindingReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_binding is True


def test_bearish_binding_is_created() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bearish_adapter_assessment()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.binding_required.side == StrategyOrderSide.SELL


def test_blocked_assessment_produces_no_binding() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        blocked_adapter_assessment()
    )

    assert decision.is_blocked is True
    assert decision.binding is None
    assert decision.has_binding is False
    assert decision.reason == (PlanningAuditStorageAdapterBindingReason.ADAPTER_ASSESSMENT_BLOCKED)
    assert decision.blockers == (
        PlanningAuditStorageAdapterBindingBlocker.ADAPTER_ASSESSMENT_BLOCKED,
    )


def test_binding_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        blocked_adapter_assessment()
    )

    with pytest.raises(
        ValueError,
        match="No planning-audit storage adapter binding",
    ):
        _ = decision.binding_required


def test_binding_preserves_assessment() -> None:
    assessment = bullish_adapter_assessment()
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory().generate(assessment).binding_required
    )

    assert binding.adapter_assessment is assessment
    assert binding.snapshot is assessment.snapshot_required
    assert binding.contract is (assessment.adapter_contract.contract_required)


def test_binding_preserves_metadata() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.broker_symbol == "XAUUSDm"
    assert binding.observed_at == OBSERVED_AT
    assert binding.direction == (DirectionalPermissionDirection.BULLISH)
    assert binding.side == StrategyOrderSide.BUY
    assert binding.schema_version == (PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_SCHEMA_VERSION)


def test_binding_preserves_adapter_reference() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.adapter_name == (binding.snapshot.adapter_name)
    assert binding.target == binding.snapshot.target
    assert binding.target == binding.contract.target
    assert binding.capability_snapshot_id == (binding.snapshot.stable_id)
    assert binding.contract_id == (binding.contract.contract_id)


def test_binding_is_reference_only() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.binding_mode == (PlanningAuditStorageAdapterBindingMode.REFERENCE_ONLY)
    assert binding.is_reference_only is True
    assert binding.has_adapter_instance is False


def test_binding_invocation_is_disabled() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.invocation_mode == (PlanningAuditStorageAdapterInvocationMode.DISABLED)
    assert binding.snapshot.invocation_enabled is False


def test_binding_locks_snapshot_and_contract() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.verification_mode == (
        PlanningAuditStorageAdapterBindingVerificationMode.SNAPSHOT_AND_CONTRACT_LOCKED
    )


def test_binding_preserves_contract_semantics() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )
    contract = binding.contract

    assert binding.operation == contract.operation
    assert binding.duplicate_policy == contract.duplicate_policy
    assert binding.integrity_policy == contract.integrity_policy
    assert binding.result_expectation == contract.result_expectation


def test_binding_preserves_digest_lineage() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )
    contract = binding.contract

    assert binding.content_digest == (contract.content_digest)
    assert binding.manifest_digest == (contract.manifest_digest)
    assert binding.idempotency_key == (contract.idempotency_key)


@pytest.mark.parametrize(
    "field_name",
    [
        "content_digest",
        "manifest_digest",
        "idempotency_key",
    ],
)
def test_binding_digests_are_lowercase_sha256(
    field_name: str,
) -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )
    value = getattr(binding, field_name)

    assert len(value) == 64
    assert value == value.lower()
    assert set(value) <= set("0123456789abcdef")


def test_binding_continues_only_to_verification_design() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    assert binding.is_binding_ready is True
    assert binding.can_continue_to_binding_verification_design is True
    assert decision.can_continue_to_binding_verification_design is True


def test_binding_performs_no_write_or_execution() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.adapter_binding_authorized is False
    assert binding.adapter_invocation_authorized is False
    assert binding.storage_write_authorized is False
    assert binding.is_persisted is False
    assert binding.can_write_storage is False
    assert binding.can_write_network is False
    assert binding.execution_authorized is False
    assert binding.has_broker_request is False
    assert binding.can_submit_order is False
    assert binding.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    assert decision.adapter_binding_authorized is False
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
def test_binding_contains_no_implementation_surface(
    attribute_name: str,
) -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert not hasattr(binding, attribute_name)


def test_binding_id_is_deterministic() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    assert binding.binding_id == (
        "XAUUSDm:BUY:"
        "AUDIT_STORAGE_ADAPTER_BINDING:"
        "injected-audit-adapter:"
        "AUDIT_ARCHIVE:"
        "REFERENCE_ONLY:"
        "DISABLED:"
        f"CONTRACT[{binding.contract_id}]:"
        f"IDEMPOTENCY_SHA256["
        f"{binding.idempotency_key}]"
    )


def test_binding_stable_id_is_deterministic() -> None:
    assessment = bullish_adapter_assessment()
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory().generate(assessment).binding_required
    )

    assert binding.stable_id == (
        f"{assessment.stable_id}:PLANNING_AUDIT_STORAGE_ADAPTER_BINDING:{binding.binding_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    assessment = bullish_adapter_assessment()
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(assessment)

    assert decision.stable_id == (
        f"{assessment.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    assessment = blocked_adapter_assessment()
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(assessment)

    assert decision.stable_id == (
        f"{assessment.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_GENERATION:"
        "BLOCKED:ADAPTER_ASSESSMENT_BLOCKED:"
        "ADAPTER_ASSESSMENT_BLOCKED"
    )


def test_direct_binding_rejects_blocked_assessment() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    with pytest.raises(
        ValueError,
        match="compatible audit storage adapter assessment",
    ):
        replace(
            binding,
            adapter_assessment=blocked_adapter_assessment(),
        )


def test_direct_binding_rejects_wrong_schema() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            binding,
            schema_version="2.0",
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
            "binding_mode",
            "REFERENCE_ONLY",
            "PlanningAuditStorageAdapterBindingMode",
        ),
        (
            "invocation_mode",
            "DISABLED",
            "PlanningAuditStorageAdapterInvocationMode",
        ),
        (
            "verification_mode",
            "SNAPSHOT_AND_CONTRACT_LOCKED",
            ("PlanningAuditStorageAdapterBindingVerificationMode"),
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
def test_direct_binding_rejects_raw_enums(
    field_name: str,
    value: str,
    message: str,
) -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    with pytest.raises(ValueError, match=message):
        replace(
            binding,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("adapter_name", "foreign-adapter"),
        ("capability_snapshot_id", "foreign-snapshot"),
        ("contract_id", "foreign-contract"),
        ("content_digest", "0" * 64),
        ("manifest_digest", "0" * 64),
        ("idempotency_key", "0" * 64),
    ],
)
def test_direct_binding_rejects_foreign_values(
    field_name: str,
    value: str,
) -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    with pytest.raises(ValueError, match=field_name):
        replace(
            binding,
            **{field_name: value},
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=(PlanningAuditStorageAdapterBindingStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditStorageAdapterBindingReason.ADAPTER_ASSESSMENT_BLOCKED),
        )


def test_manual_decision_rejects_missing_binding() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            binding=None,
        )


def test_manual_decision_rejects_unexpected_binding() -> None:
    blocked = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        blocked_adapter_assessment()
    )
    created_binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            binding=created_binding,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        blocked_adapter_assessment()
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditStorageAdapterBindingBlocker.ADAPTER_ASSESSMENT_BLOCKED,
                PlanningAuditStorageAdapterBindingBlocker.ADAPTER_ASSESSMENT_BLOCKED,
            ),
        )


def test_binding_is_immutable() -> None:
    binding = (
        StrategyPlanningAuditStorageAdapterBindingFactory()
        .generate(bullish_adapter_assessment())
        .binding_required
    )

    with pytest.raises(FrozenInstanceError):
        binding.adapter_name = "modified"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditStorageAdapterBindingStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditStorageAdapterBindingFactory()
    assessment = bullish_adapter_assessment()

    assert factory.generate(assessment) == factory.generate(assessment)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_storage_adapter_binding(bullish_adapter_assessment())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditStorageAdapterBindingFactory()
    assessment = bullish_adapter_assessment()

    assert factory.build(assessment) == factory.generate(assessment)
    assert factory.evaluate(assessment) == factory.generate(assessment)


def test_public_aliases_are_preserved() -> None:
    assert AuditStorageAdapterBinding is StrategyPlanningAuditStorageAdapterBinding
    assert AuditStorageAdapterBindingDecision is PlanningAuditStorageAdapterBindingDecision
    assert AuditStorageAdapterBindingFactory is StrategyPlanningAuditStorageAdapterBindingFactory
    assert AuditStorageAdapterBindingMode is PlanningAuditStorageAdapterBindingMode
    assert (
        AuditStorageAdapterBindingVerificationMode
        is PlanningAuditStorageAdapterBindingVerificationMode
    )
    assert AuditStorageAdapterInvocationMode is PlanningAuditStorageAdapterInvocationMode
    assert PlanningAuditStorageAdapterBinding is StrategyPlanningAuditStorageAdapterBinding
    assert (
        PlanningAuditStorageAdapterBindingFactory
        is StrategyPlanningAuditStorageAdapterBindingFactory
    )
    assert StrategyAuditStorageAdapterBinding is StrategyPlanningAuditStorageAdapterBinding
    assert (
        StrategyAuditStorageAdapterBindingFactory
        is StrategyPlanningAuditStorageAdapterBindingFactory
    )
