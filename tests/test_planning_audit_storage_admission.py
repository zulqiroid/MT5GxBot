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
from app.strategy.planning_audit_storage_admission import (
    AuditStorageAdmissionBlocker,
    AuditStorageAdmissionDecision,
    AuditStorageAdmissionGate,
    AuditStorageAdmissionPolicy,
    AuditStorageAdmissionReason,
    AuditStorageAdmissionStatus,
    AuditStorageMetrics,
    AuditStorageSnapshot,
    AuditStorageTarget,
    PlanningAuditStorageAdmissionBlocker,
    PlanningAuditStorageAdmissionDecision,
    PlanningAuditStorageAdmissionError,
    PlanningAuditStorageAdmissionErrorReason,
    PlanningAuditStorageAdmissionPolicy,
    PlanningAuditStorageAdmissionReason,
    PlanningAuditStorageAdmissionStatus,
    PlanningAuditStorageMetrics,
    PlanningAuditStorageSnapshot,
    PlanningAuditStorageTarget,
    StrategyAuditStorageAdmissionGate,
    StrategyPlanningAuditStorageAdmissionGate,
    evaluate_planning_audit_storage_admission,
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


def test_default_policy_is_strict() -> None:
    policy = PlanningAuditStorageAdmissionPolicy()

    assert policy.require_non_stale_snapshot is True
    assert policy.require_storage_enabled is True
    assert policy.require_encryption_at_rest is True
    assert policy.require_append_only is True
    assert policy.require_idempotency is True
    assert policy.minimum_retention_days == 90


@pytest.mark.parametrize(
    "overrides",
    [
        {"require_non_stale_snapshot": 1},
        {"require_storage_enabled": 1},
        {"require_encryption_at_rest": 1},
        {"require_append_only": 1},
        {"require_idempotency": 1},
        {"minimum_retention_days": 0},
        {"minimum_retention_days": True},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PlanningAuditStorageAdmissionPolicy(**overrides)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PlanningAuditStorageAdmissionPolicy",
    ):
        StrategyPlanningAuditStorageAdmissionGate(policy="invalid")


def test_invalid_verification_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdmissionError,
        match="INVALID_VERIFICATION_DECISION",
    ) as captured:
        StrategyPlanningAuditStorageAdmissionGate().evaluate("invalid")

    assert captured.value.reason == (
        PlanningAuditStorageAdmissionErrorReason.INVALID_VERIFICATION_DECISION
    )


def test_verified_receipt_requires_snapshot() -> None:
    with pytest.raises(
        PlanningAuditStorageAdmissionError,
        match="INVALID_STORAGE_SNAPSHOT",
    ):
        StrategyPlanningAuditStorageAdmissionGate().evaluate(bullish_verification())


def test_invalid_snapshot_type_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditStorageAdmissionError,
        match="INVALID_STORAGE_SNAPSHOT",
    ):
        StrategyPlanningAuditStorageAdmissionGate().evaluate(
            bullish_verification(),
            "invalid",
        )


def test_blocked_verification_requires_no_snapshot() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(blocked_verification())

    assert decision.is_blocked is True
    assert decision.snapshot is None
    assert decision.metrics is None
    assert decision.reason == (PlanningAuditStorageAdmissionReason.VERIFICATION_BLOCKED)
    assert decision.blockers == (PlanningAuditStorageAdmissionBlocker.VERIFICATION_BLOCKED,)


def test_bullish_storage_is_admitted() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    assert decision.status == (PlanningAuditStorageAdmissionStatus.ADMITTED)
    assert decision.reason == (PlanningAuditStorageAdmissionReason.ADMITTED)
    assert decision.blockers == ()
    assert decision.is_admitted is True


def test_bearish_storage_is_admitted() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bearish_verification(),
        storage_snapshot(),
    )

    assert decision.is_admitted is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.side == StrategyOrderSide.SELL


def test_snapshot_preserves_read_only_contract() -> None:
    snapshot = storage_snapshot()

    assert snapshot.target == (PlanningAuditStorageTarget.AUDIT_ARCHIVE)
    assert snapshot.is_read_only_snapshot is True
    assert snapshot.can_write_storage is False


def test_decision_preserves_receipt_and_snapshot() -> None:
    verification = bullish_verification()
    snapshot = storage_snapshot()
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        verification,
        snapshot,
    )

    assert decision.verification is verification
    assert decision.receipt is (verification.receipt_required)
    assert decision.snapshot is snapshot


def test_decision_preserves_metadata() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.side == StrategyOrderSide.BUY


def test_same_time_snapshot_is_fresh() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(observed_at=OBSERVED_AT),
    )

    assert decision.is_admitted is True


def test_stale_snapshot_is_blocked() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.reason == (PlanningAuditStorageAdmissionReason.SNAPSHOT_STALE)
    assert decision.blockers == (PlanningAuditStorageAdmissionBlocker.SNAPSHOT_STALE,)


def test_stale_snapshot_can_be_allowed() -> None:
    policy = PlanningAuditStorageAdmissionPolicy(require_non_stale_snapshot=False)
    decision = StrategyPlanningAuditStorageAdmissionGate(policy).evaluate(
        bullish_verification(),
        storage_snapshot(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.is_admitted is True


@pytest.mark.parametrize(
    ("snapshot_overrides", "expected_blocker"),
    [
        (
            {"storage_enabled": False},
            PlanningAuditStorageAdmissionBlocker.STORAGE_DISABLED,
        ),
        (
            {"encryption_at_rest": False},
            PlanningAuditStorageAdmissionBlocker.ENCRYPTION_REQUIRED,
        ),
        (
            {"append_only": False},
            PlanningAuditStorageAdmissionBlocker.APPEND_ONLY_REQUIRED,
        ),
        (
            {"idempotency_supported": False},
            PlanningAuditStorageAdmissionBlocker.IDEMPOTENCY_REQUIRED,
        ),
        (
            {"retention_days": 89},
            PlanningAuditStorageAdmissionBlocker.RETENTION_TOO_SHORT,
        ),
        (
            {"available_capacity_bytes": 0},
            PlanningAuditStorageAdmissionBlocker.INSUFFICIENT_CAPACITY,
        ),
    ],
)
def test_individual_storage_blockers(
    snapshot_overrides: dict[str, object],
    expected_blocker: (PlanningAuditStorageAdmissionBlocker),
) -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(**snapshot_overrides),
    )

    assert decision.is_blocked is True
    assert decision.blockers == (expected_blocker,)


def test_multiple_blockers_are_deterministic() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(
            observed_at=(OBSERVED_AT - timedelta(seconds=1)),
            storage_enabled=False,
            encryption_at_rest=False,
            append_only=False,
            idempotency_supported=False,
            retention_days=1,
            available_capacity_bytes=0,
        ),
    )

    assert decision.reason == (PlanningAuditStorageAdmissionReason.MULTIPLE_STORAGE_BLOCKERS)
    assert decision.blockers == (
        PlanningAuditStorageAdmissionBlocker.SNAPSHOT_STALE,
        PlanningAuditStorageAdmissionBlocker.STORAGE_DISABLED,
        PlanningAuditStorageAdmissionBlocker.ENCRYPTION_REQUIRED,
        PlanningAuditStorageAdmissionBlocker.APPEND_ONLY_REQUIRED,
        PlanningAuditStorageAdmissionBlocker.IDEMPOTENCY_REQUIRED,
        PlanningAuditStorageAdmissionBlocker.RETENTION_TOO_SHORT,
        PlanningAuditStorageAdmissionBlocker.INSUFFICIENT_CAPACITY,
    )


def test_required_capacity_matches_verified_payload() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )
    metrics = decision.metrics_required

    assert metrics.required_capacity_bytes == (
        bullish_verification().receipt_required.verified_content_length_bytes
    )


def test_exact_capacity_is_admitted() -> None:
    required = bullish_verification().receipt_required.verified_content_length_bytes
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(available_capacity_bytes=required),
    )

    assert decision.is_admitted is True
    assert decision.metrics_required.capacity_surplus_bytes == 0
    assert decision.metrics_required.capacity_deficit_bytes == 0


def test_capacity_deficit_is_exact() -> None:
    required = bullish_verification().receipt_required.verified_content_length_bytes
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(available_capacity_bytes=required - 1),
    )

    assert decision.is_blocked is True
    assert decision.metrics_required.capacity_deficit_bytes == 1


def test_exact_retention_is_admitted() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(retention_days=90),
    )

    assert decision.is_admitted is True
    assert decision.metrics_required.retention_surplus_days == 0
    assert decision.metrics_required.retention_deficit_days == 0


def test_retention_deficit_is_exact() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(retention_days=89),
    )

    assert decision.metrics_required.retention_deficit_days == 1


def test_admitted_decision_can_continue_only_to_design() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    assert decision.can_continue_to_storage_write_design is True
    assert decision.storage_write_authorized is False


def test_blocked_decision_cannot_continue() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(storage_enabled=False),
    )

    assert decision.can_continue_to_storage_write_design is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

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
def test_decision_contains_no_write_or_execution_surface(
    attribute_name: str,
) -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
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
        {"target": "AUDIT_ARCHIVE"},
        {"storage_enabled": 1},
        {"encryption_at_rest": 1},
        {"append_only": 1},
        {"idempotency_supported": 1},
        {"retention_days": 0},
        {"retention_days": True},
        {"available_capacity_bytes": -1},
        {"available_capacity_bytes": True},
    ],
)
def test_invalid_snapshot_is_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "observed_at": OBSERVED_AT,
        "target": (PlanningAuditStorageTarget.AUDIT_ARCHIVE),
        "storage_enabled": True,
        "encryption_at_rest": True,
        "append_only": True,
        "idempotency_supported": True,
        "retention_days": 365,
        "available_capacity_bytes": 1_000_000,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        PlanningAuditStorageSnapshot(**values)


def test_snapshot_stable_id_is_deterministic() -> None:
    snapshot = storage_snapshot()

    assert snapshot.stable_id == (
        f"{OBSERVED_AT.isoformat()}:"
        "AUDIT_ARCHIVE:"
        "ENABLED[True]:"
        "ENCRYPTED[True]:"
        "APPEND_ONLY[True]:"
        "IDEMPOTENT[True]:"
        "RETENTION_DAYS[365]:"
        "CAPACITY_BYTES[1000000]"
    )


def test_metrics_stable_id_is_deterministic() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )
    metrics = decision.metrics_required

    assert metrics.stable_id == (
        f"REQUIRED_CAPACITY["
        f"{metrics.required_capacity_bytes}]:"
        "AVAILABLE_CAPACITY[1000000]:"
        f"CAPACITY_SURPLUS["
        f"{metrics.capacity_surplus_bytes}]:"
        "CAPACITY_DEFICIT[0]:"
        "RETENTION_DAYS[365]:"
        "MINIMUM_RETENTION_DAYS[90]:"
        "RETENTION_SURPLUS[275]:"
        "RETENTION_DEFICIT[0]"
    )


def test_admitted_stable_id_is_deterministic() -> None:
    verification = bullish_verification()
    snapshot = storage_snapshot()
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        verification,
        snapshot,
    )

    assert decision.stable_id == (
        f"{verification.stable_id}:"
        "PLANNING_AUDIT_STORAGE_ADMISSION:"
        "ADMITTED:ADMITTED:NONE:"
        f"{snapshot.stable_id}:"
        f"{decision.metrics_required.stable_id}"
    )


def test_blocked_stable_id_lists_blocker() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(blocked_verification())

    assert decision.stable_id.endswith(
        "PLANNING_AUDIT_STORAGE_ADMISSION:"
        "BLOCKED:VERIFICATION_BLOCKED:"
        "VERIFICATION_BLOCKED:"
        "NO_STORAGE_SNAPSHOT:"
        "NO_STORAGE_METRICS"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=(PlanningAuditStorageAdmissionStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditStorageAdmissionReason.STORAGE_DISABLED),
        )


def test_manual_decision_rejects_missing_snapshot() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    with pytest.raises(
        PlanningAuditStorageAdmissionError,
        match="INVALID_STORAGE_SNAPSHOT",
    ):
        replace(
            decision,
            snapshot=None,
        )


def test_manual_decision_rejects_wrong_metrics() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )
    modified = replace(
        decision.metrics_required,
        available_capacity_bytes=(decision.metrics_required.available_capacity_bytes + 1),
        capacity_surplus_bytes=(decision.metrics_required.capacity_surplus_bytes + 1),
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
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(storage_enabled=False),
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditStorageAdmissionBlocker.STORAGE_DISABLED,
                PlanningAuditStorageAdmissionBlocker.STORAGE_DISABLED,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = PlanningAuditStorageAdmissionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_retention_days = 365


def test_snapshot_is_immutable() -> None:
    snapshot = storage_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.storage_enabled = False


def test_metrics_are_immutable() -> None:
    metrics = (
        StrategyPlanningAuditStorageAdmissionGate()
        .evaluate(
            bullish_verification(),
            storage_snapshot(),
        )
        .metrics_required
    )

    with pytest.raises(FrozenInstanceError):
        metrics.required_capacity_bytes = 1


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditStorageAdmissionStatus.BLOCKED


def test_evaluation_is_deterministic() -> None:
    gate = StrategyPlanningAuditStorageAdmissionGate()
    verification = bullish_verification()
    snapshot = storage_snapshot()

    assert gate.evaluate(
        verification,
        snapshot,
    ) == gate.evaluate(
        verification,
        snapshot,
    )


def test_function_api_delegates() -> None:
    decision = evaluate_planning_audit_storage_admission(
        bullish_verification(),
        storage_snapshot(),
    )

    assert decision.is_admitted is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPlanningAuditStorageAdmissionGate()
    verification = bullish_verification()
    snapshot = storage_snapshot()

    assert gate.admit(
        verification,
        snapshot,
    ) == gate.evaluate(
        verification,
        snapshot,
    )
    assert gate.check(
        verification,
        snapshot,
    ) == gate.evaluate(
        verification,
        snapshot,
    )


def test_public_aliases_are_preserved() -> None:
    assert AuditStorageAdmissionBlocker is PlanningAuditStorageAdmissionBlocker
    assert AuditStorageAdmissionDecision is PlanningAuditStorageAdmissionDecision
    assert AuditStorageAdmissionGate is StrategyPlanningAuditStorageAdmissionGate
    assert AuditStorageAdmissionPolicy is PlanningAuditStorageAdmissionPolicy
    assert AuditStorageAdmissionReason is PlanningAuditStorageAdmissionReason
    assert AuditStorageAdmissionStatus is PlanningAuditStorageAdmissionStatus
    assert AuditStorageMetrics is PlanningAuditStorageMetrics
    assert AuditStorageSnapshot is PlanningAuditStorageSnapshot
    assert AuditStorageTarget is PlanningAuditStorageTarget
    assert StrategyAuditStorageAdmissionGate is StrategyPlanningAuditStorageAdmissionGate
