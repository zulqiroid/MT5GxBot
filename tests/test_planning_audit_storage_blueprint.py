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
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageSnapshot,
    PlanningAuditStorageTarget,
    StrategyPlanningAuditStorageAdmissionGate,
)
from app.strategy.planning_audit_storage_blueprint import (
    PLANNING_AUDIT_STORAGE_BLUEPRINT_SCHEMA_VERSION,
    AuditStorageBlueprint,
    AuditStorageBlueprintDecision,
    AuditStorageBlueprintFactory,
    AuditStorageEncryptionMode,
    AuditStorageIdempotencyMode,
    AuditStorageWriteMode,
    PlanningAuditStorageBlueprint,
    PlanningAuditStorageBlueprintBlocker,
    PlanningAuditStorageBlueprintDecision,
    PlanningAuditStorageBlueprintError,
    PlanningAuditStorageBlueprintErrorReason,
    PlanningAuditStorageBlueprintFactory,
    PlanningAuditStorageBlueprintReason,
    PlanningAuditStorageBlueprintStatus,
    PlanningAuditStorageEncryptionMode,
    PlanningAuditStorageIdempotencyMode,
    PlanningAuditStorageWriteMode,
    StrategyAuditStorageBlueprint,
    StrategyAuditStorageBlueprintFactory,
    StrategyPlanningAuditStorageBlueprint,
    StrategyPlanningAuditStorageBlueprintFactory,
    generate_planning_audit_storage_blueprint,
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


def test_invalid_storage_admission_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageBlueprintError,
        match="INVALID_STORAGE_ADMISSION_DECISION",
    ) as captured:
        (StrategyPlanningAuditStorageBlueprintFactory().generate("invalid"))

    assert captured.value.reason == (
        PlanningAuditStorageBlueprintErrorReason.INVALID_STORAGE_ADMISSION_DECISION
    )


def test_bullish_blueprint_is_created() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

    assert decision.status == (PlanningAuditStorageBlueprintStatus.CREATED)
    assert decision.reason == (PlanningAuditStorageBlueprintReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_blueprint is True


def test_bearish_blueprint_is_created() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bearish_storage_admission())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.blueprint_required.side == StrategyOrderSide.SELL


def test_blocked_admission_produces_no_blueprint() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(blocked_storage_admission())

    assert decision.is_blocked is True
    assert decision.blueprint is None
    assert decision.has_blueprint is False
    assert decision.reason == (PlanningAuditStorageBlueprintReason.STORAGE_ADMISSION_BLOCKED)
    assert decision.blockers == (PlanningAuditStorageBlueprintBlocker.STORAGE_ADMISSION_BLOCKED,)


def test_blueprint_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(blocked_storage_admission())

    with pytest.raises(
        ValueError,
        match="No planning-audit storage blueprint",
    ):
        _ = decision.blueprint_required


def test_blueprint_preserves_admission() -> None:
    admission = bullish_storage_admission()
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory().generate(admission).blueprint_required
    )

    assert blueprint.storage_admission is admission
    assert blueprint.receipt is (admission.verification.receipt_required)
    assert blueprint.snapshot is admission.snapshot_required
    assert blueprint.metrics is admission.metrics_required


def test_blueprint_preserves_audit_lineage() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.envelope is blueprint.receipt.envelope
    assert blueprint.record is blueprint.receipt.record
    assert blueprint.manifest is blueprint.receipt.manifest
    assert blueprint.package is blueprint.receipt.package


def test_blueprint_preserves_metadata() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.broker_symbol == "XAUUSDm"
    assert blueprint.observed_at == OBSERVED_AT
    assert blueprint.direction == (DirectionalPermissionDirection.BULLISH)
    assert blueprint.side == StrategyOrderSide.BUY
    assert blueprint.schema_version == (PLANNING_AUDIT_STORAGE_BLUEPRINT_SCHEMA_VERSION)


def test_blueprint_preserves_storage_target() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.target == (PlanningAuditStorageTarget.AUDIT_ARCHIVE)


def test_blueprint_requires_append_only_storage() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.write_mode == (PlanningAuditStorageWriteMode.APPEND_ONLY)
    assert blueprint.is_append_only is True


def test_blueprint_requires_encryption_at_rest() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.encryption_mode == (
        PlanningAuditStorageEncryptionMode.ENCRYPTION_AT_REST_REQUIRED
    )
    assert blueprint.requires_encryption_at_rest is True


def test_blueprint_requires_idempotency() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.idempotency_mode == (PlanningAuditStorageIdempotencyMode.IDEMPOTENCY_REQUIRED)
    assert blueprint.requires_idempotency is True


def test_content_matches_verified_envelope() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.content == blueprint.envelope.content
    assert blueprint.content_bytes == (blueprint.content.encode("utf-8"))


def test_content_length_matches_verified_receipt() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.content_length_bytes == (blueprint.envelope.content_length_bytes)
    assert blueprint.content_length_bytes == (blueprint.receipt.verified_content_length_bytes)
    assert blueprint.required_capacity_bytes == (blueprint.content_length_bytes)


def test_content_digest_matches_verified_lineage() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.content_digest == (blueprint.envelope.content_digest)
    assert blueprint.content_digest == (blueprint.receipt.verified_content_digest)
    assert blueprint.manifest_digest == (blueprint.envelope.manifest_digest)
    assert blueprint.manifest_digest == (blueprint.receipt.verified_manifest_digest)


def test_idempotency_key_is_lowercase_sha256() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert len(blueprint.idempotency_key) == 64
    assert blueprint.idempotency_key == (blueprint.idempotency_key.lower())
    assert set(blueprint.idempotency_key) <= set("0123456789abcdef")


def test_idempotency_key_is_deterministic() -> None:
    admission = bullish_storage_admission()
    factory = StrategyPlanningAuditStorageBlueprintFactory()

    first = factory.generate(admission).blueprint_required
    second = factory.generate(admission).blueprint_required

    assert first.idempotency_key == second.idempotency_key


def test_retention_matches_admitted_snapshot() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.retention_days == 365
    assert blueprint.retention_days == (blueprint.snapshot.retention_days)


def test_capacity_matches_admitted_metrics() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.required_capacity_bytes == (blueprint.metrics.required_capacity_bytes)
    assert blueprint.available_capacity_bytes == (blueprint.metrics.available_capacity_bytes)
    assert blueprint.available_capacity_bytes >= blueprint.required_capacity_bytes


def test_blueprint_is_ready_for_adapter_design_only() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

    assert blueprint.is_write_blueprint_ready is True
    assert decision.can_continue_to_storage_adapter_design is True
    assert blueprint.storage_write_authorized is False
    assert decision.storage_write_authorized is False


def test_blueprint_performs_no_write_or_execution() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.is_persisted is False
    assert blueprint.can_write_storage is False
    assert blueprint.can_write_network is False
    assert blueprint.execution_authorized is False
    assert blueprint.has_broker_request is False
    assert blueprint.can_submit_order is False
    assert blueprint.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

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
def test_blueprint_contains_no_write_or_execution_surface(
    attribute_name: str,
) -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert not hasattr(blueprint, attribute_name)


def test_blueprint_id_is_deterministic() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    assert blueprint.blueprint_id == (
        "XAUUSDm:BUY:"
        "AUDIT_STORAGE_BLUEPRINT:"
        "AUDIT_ARCHIVE:"
        "APPEND_ONLY:"
        f"BYTES[{blueprint.content_length_bytes}]:"
        f"CONTENT_SHA256[{blueprint.content_digest}]:"
        f"IDEMPOTENCY_SHA256["
        f"{blueprint.idempotency_key}]"
    )


def test_blueprint_stable_id_is_deterministic() -> None:
    admission = bullish_storage_admission()
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory().generate(admission).blueprint_required
    )

    assert blueprint.stable_id == (
        f"{admission.stable_id}:PLANNING_AUDIT_STORAGE_BLUEPRINT:{blueprint.blueprint_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    admission = bullish_storage_admission()
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(admission)

    assert decision.stable_id == (
        f"{admission.stable_id}:PLANNING_AUDIT_STORAGE_BLUEPRINT_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    admission = blocked_storage_admission()
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(admission)

    assert decision.stable_id == (
        f"{admission.stable_id}:"
        "PLANNING_AUDIT_STORAGE_BLUEPRINT_GENERATION:"
        "BLOCKED:STORAGE_ADMISSION_BLOCKED:"
        "STORAGE_ADMISSION_BLOCKED"
    )


def test_direct_blueprint_rejects_blocked_admission() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="admitted audit storage decision",
    ):
        replace(
            blueprint,
            storage_admission=blocked_storage_admission(),
        )


def test_direct_blueprint_rejects_wrong_schema() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            blueprint,
            schema_version="2.0",
        )


def test_direct_blueprint_rejects_raw_target() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="PlanningAuditStorageTarget",
    ):
        replace(
            blueprint,
            target="AUDIT_ARCHIVE",
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "write_mode",
            "APPEND_ONLY",
            "PlanningAuditStorageWriteMode",
        ),
        (
            "encryption_mode",
            "ENCRYPTION_AT_REST_REQUIRED",
            "PlanningAuditStorageEncryptionMode",
        ),
        (
            "idempotency_mode",
            "IDEMPOTENCY_REQUIRED",
            "PlanningAuditStorageIdempotencyMode",
        ),
    ],
)
def test_direct_blueprint_rejects_raw_modes(
    field_name: str,
    value: str,
    message: str,
) -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(ValueError, match=message):
        replace(
            blueprint,
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
        ("retention_days", 90),
        ("required_capacity_bytes", 1),
        ("available_capacity_bytes", 1),
    ],
)
def test_direct_blueprint_rejects_wrong_values(
    field_name: str,
    value: object,
) -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(ValueError, match=field_name):
        replace(
            blueprint,
            **{field_name: value},
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PlanningAuditStorageBlueprintStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditStorageBlueprintReason.STORAGE_ADMISSION_BLOCKED),
        )


def test_manual_decision_rejects_missing_blueprint() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            blueprint=None,
        )


def test_manual_decision_rejects_unexpected_blueprint() -> None:
    blocked = StrategyPlanningAuditStorageBlueprintFactory().generate(blocked_storage_admission())
    created_blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            blueprint=created_blueprint,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(blocked_storage_admission())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditStorageBlueprintBlocker.STORAGE_ADMISSION_BLOCKED,
                PlanningAuditStorageBlueprintBlocker.STORAGE_ADMISSION_BLOCKED,
            ),
        )


def test_blueprint_is_immutable() -> None:
    blueprint = (
        StrategyPlanningAuditStorageBlueprintFactory()
        .generate(bullish_storage_admission())
        .blueprint_required
    )

    with pytest.raises(FrozenInstanceError):
        blueprint.content = "{}"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditStorageBlueprintStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditStorageBlueprintFactory()
    admission = bullish_storage_admission()

    assert factory.generate(admission) == factory.generate(admission)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_storage_blueprint(bullish_storage_admission())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditStorageBlueprintFactory()
    admission = bullish_storage_admission()

    assert factory.build(admission) == factory.generate(admission)
    assert factory.evaluate(admission) == factory.generate(admission)


def test_public_aliases_are_preserved() -> None:
    assert AuditStorageBlueprint is StrategyPlanningAuditStorageBlueprint
    assert AuditStorageBlueprintDecision is PlanningAuditStorageBlueprintDecision
    assert AuditStorageBlueprintFactory is StrategyPlanningAuditStorageBlueprintFactory
    assert AuditStorageEncryptionMode is PlanningAuditStorageEncryptionMode
    assert AuditStorageIdempotencyMode is PlanningAuditStorageIdempotencyMode
    assert AuditStorageWriteMode is PlanningAuditStorageWriteMode
    assert PlanningAuditStorageBlueprint is StrategyPlanningAuditStorageBlueprint
    assert PlanningAuditStorageBlueprintFactory is StrategyPlanningAuditStorageBlueprintFactory
    assert StrategyAuditStorageBlueprint is StrategyPlanningAuditStorageBlueprint
    assert StrategyAuditStorageBlueprintFactory is StrategyPlanningAuditStorageBlueprintFactory
