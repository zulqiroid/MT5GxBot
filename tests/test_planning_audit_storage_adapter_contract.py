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
from app.strategy.planning_audit_storage_adapter_contract import (
    PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_SCHEMA_VERSION,
    AuditStorageAdapterContract,
    AuditStorageAdapterContractDecision,
    AuditStorageAdapterContractFactory,
    AuditStorageAdapterOperation,
    AuditStorageDuplicatePolicy,
    AuditStorageIntegrityPolicy,
    AuditStorageResultExpectation,
    PlanningAuditStorageAdapterContract,
    PlanningAuditStorageAdapterContractBlocker,
    PlanningAuditStorageAdapterContractDecision,
    PlanningAuditStorageAdapterContractError,
    PlanningAuditStorageAdapterContractErrorReason,
    PlanningAuditStorageAdapterContractFactory,
    PlanningAuditStorageAdapterContractReason,
    PlanningAuditStorageAdapterContractStatus,
    PlanningAuditStorageAdapterOperation,
    PlanningAuditStorageDuplicatePolicy,
    PlanningAuditStorageIntegrityPolicy,
    PlanningAuditStorageResultExpectation,
    StrategyAuditStorageAdapterContract,
    StrategyAuditStorageAdapterContractFactory,
    StrategyPlanningAuditStorageAdapterContract,
    StrategyPlanningAuditStorageAdapterContractFactory,
    generate_planning_audit_storage_adapter_contract,
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


def test_invalid_blueprint_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdapterContractError,
        match="INVALID_STORAGE_BLUEPRINT_DECISION",
    ) as captured:
        (StrategyPlanningAuditStorageAdapterContractFactory().generate("invalid"))

    assert captured.value.reason == (
        PlanningAuditStorageAdapterContractErrorReason.INVALID_STORAGE_BLUEPRINT_DECISION
    )


def test_bullish_contract_is_created() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

    assert decision.status == (PlanningAuditStorageAdapterContractStatus.CREATED)
    assert decision.reason == (PlanningAuditStorageAdapterContractReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_contract is True


def test_bearish_contract_is_created() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bearish_storage_blueprint()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.contract_required.side == StrategyOrderSide.SELL


def test_blocked_blueprint_produces_no_contract() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        blocked_storage_blueprint()
    )

    assert decision.is_blocked is True
    assert decision.contract is None
    assert decision.has_contract is False
    assert decision.reason == (PlanningAuditStorageAdapterContractReason.STORAGE_BLUEPRINT_BLOCKED)
    assert decision.blockers == (
        PlanningAuditStorageAdapterContractBlocker.STORAGE_BLUEPRINT_BLOCKED,
    )


def test_contract_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        blocked_storage_blueprint()
    )

    with pytest.raises(
        ValueError,
        match="No planning-audit storage adapter contract",
    ):
        _ = decision.contract_required


def test_contract_preserves_blueprint_decision() -> None:
    blueprint_decision = bullish_storage_blueprint()
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(blueprint_decision)
        .contract_required
    )

    assert contract.storage_blueprint is blueprint_decision
    assert contract.blueprint is (blueprint_decision.blueprint_required)


def test_contract_preserves_metadata() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.broker_symbol == "XAUUSDm"
    assert contract.observed_at == OBSERVED_AT
    assert contract.direction == (DirectionalPermissionDirection.BULLISH)
    assert contract.side == StrategyOrderSide.BUY
    assert contract.schema_version == (PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_SCHEMA_VERSION)


def test_contract_uses_append_if_absent() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.operation == (PlanningAuditStorageAdapterOperation.APPEND_IF_ABSENT)


def test_contract_returns_existing_duplicate() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.duplicate_policy == (PlanningAuditStorageDuplicatePolicy.RETURN_EXISTING)


def test_contract_requires_integrity_verification() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.integrity_policy == (PlanningAuditStorageIntegrityPolicy.VERIFY_BEFORE_ACCEPT)
    assert contract.requires_integrity_verification is True


def test_contract_result_is_created_or_existing() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.result_expectation == (
        PlanningAuditStorageResultExpectation.CREATED_OR_EXISTING
    )


def test_contract_preserves_storage_safeguards() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.requires_append_only is True
    assert contract.requires_encryption_at_rest is True
    assert contract.requires_idempotency is True


def test_contract_preserves_payload() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )
    blueprint = contract.blueprint

    assert contract.target == blueprint.target
    assert contract.content == blueprint.content
    assert contract.content_bytes == (blueprint.content_bytes)
    assert contract.content_length_bytes == (blueprint.content_length_bytes)
    assert contract.content_digest == (blueprint.content_digest)
    assert contract.manifest_digest == (blueprint.manifest_digest)
    assert contract.idempotency_key == (blueprint.idempotency_key)
    assert contract.retention_days == (blueprint.retention_days)


def test_contract_is_design_ready_only() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

    assert contract.is_adapter_contract_ready is True
    assert contract.can_continue_to_adapter_implementation is True
    assert decision.can_continue_to_adapter_implementation is True


def test_contract_performs_no_write_or_execution() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

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
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

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
def test_contract_contains_no_implementation_surface(
    attribute_name: str,
) -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert not hasattr(contract, attribute_name)


def test_contract_id_is_deterministic() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    assert contract.contract_id == (
        "XAUUSDm:BUY:"
        "AUDIT_STORAGE_ADAPTER_CONTRACT:"
        "AUDIT_ARCHIVE:"
        "APPEND_IF_ABSENT:"
        "RETURN_EXISTING:"
        "VERIFY_BEFORE_ACCEPT:"
        f"IDEMPOTENCY_SHA256["
        f"{contract.idempotency_key}]"
    )


def test_contract_stable_id_is_deterministic() -> None:
    blueprint = bullish_storage_blueprint()
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory().generate(blueprint).contract_required
    )

    assert contract.stable_id == (
        f"{blueprint.stable_id}:PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT:{contract.contract_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    blueprint = bullish_storage_blueprint()
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(blueprint)

    assert decision.stable_id == (
        f"{blueprint.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    blueprint = blocked_storage_blueprint()
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(blueprint)

    assert decision.stable_id == (
        f"{blueprint.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_GENERATION:"
        "BLOCKED:STORAGE_BLUEPRINT_BLOCKED:"
        "STORAGE_BLUEPRINT_BLOCKED"
    )


def test_direct_contract_rejects_blocked_blueprint() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    with pytest.raises(
        ValueError,
        match="created audit storage blueprint",
    ):
        replace(
            contract,
            storage_blueprint=blocked_storage_blueprint(),
        )


def test_direct_contract_rejects_wrong_schema() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
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


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
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
def test_direct_contract_rejects_raw_enums(
    field_name: str,
    value: str,
    message: str,
) -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
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
        ("content", "{}"),
        ("content_length_bytes", 1),
        ("content_digest", "0" * 64),
        ("manifest_digest", "0" * 64),
        ("idempotency_key", "0" * 64),
        ("retention_days", 1),
    ],
)
def test_direct_contract_rejects_wrong_values(
    field_name: str,
    value: object,
) -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    with pytest.raises(ValueError, match=field_name):
        replace(
            contract,
            **{field_name: value},
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=(PlanningAuditStorageAdapterContractStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditStorageAdapterContractReason.STORAGE_BLUEPRINT_BLOCKED),
        )


def test_manual_decision_rejects_missing_contract() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            contract=None,
        )


def test_manual_decision_rejects_unexpected_contract() -> None:
    blocked = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        blocked_storage_blueprint()
    )
    created_contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            contract=created_contract,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        blocked_storage_blueprint()
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditStorageAdapterContractBlocker.STORAGE_BLUEPRINT_BLOCKED,
                PlanningAuditStorageAdapterContractBlocker.STORAGE_BLUEPRINT_BLOCKED,
            ),
        )


def test_contract_is_immutable() -> None:
    contract = (
        StrategyPlanningAuditStorageAdapterContractFactory()
        .generate(bullish_storage_blueprint())
        .contract_required
    )

    with pytest.raises(FrozenInstanceError):
        contract.content = "{}"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditStorageAdapterContractStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditStorageAdapterContractFactory()
    blueprint = bullish_storage_blueprint()

    assert factory.generate(blueprint) == factory.generate(blueprint)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_storage_adapter_contract(bullish_storage_blueprint())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditStorageAdapterContractFactory()
    blueprint = bullish_storage_blueprint()

    assert factory.build(blueprint) == factory.generate(blueprint)
    assert factory.evaluate(blueprint) == factory.generate(blueprint)


def test_public_aliases_are_preserved() -> None:
    assert AuditStorageAdapterContract is StrategyPlanningAuditStorageAdapterContract
    assert AuditStorageAdapterContractDecision is PlanningAuditStorageAdapterContractDecision
    assert AuditStorageAdapterContractFactory is StrategyPlanningAuditStorageAdapterContractFactory
    assert AuditStorageAdapterOperation is PlanningAuditStorageAdapterOperation
    assert AuditStorageDuplicatePolicy is PlanningAuditStorageDuplicatePolicy
    assert AuditStorageIntegrityPolicy is PlanningAuditStorageIntegrityPolicy
    assert AuditStorageResultExpectation is PlanningAuditStorageResultExpectation
    assert PlanningAuditStorageAdapterContract is StrategyPlanningAuditStorageAdapterContract
    assert (
        PlanningAuditStorageAdapterContractFactory
        is StrategyPlanningAuditStorageAdapterContractFactory
    )
    assert StrategyAuditStorageAdapterContract is StrategyPlanningAuditStorageAdapterContract
    assert (
        StrategyAuditStorageAdapterContractFactory
        is StrategyPlanningAuditStorageAdapterContractFactory
    )
