import hashlib
import json
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
from app.strategy.planning_audit_manifest import (
    StrategyPlanningAuditManifestFactory,
)
from app.strategy.planning_audit_record import (
    PLANNING_AUDIT_RECORD_SCHEMA_VERSION,
    AuditRecord,
    AuditRecordDecision,
    AuditRecordEntry,
    AuditRecordFactory,
    AuditRecordField,
    PlanningAuditRecord,
    PlanningAuditRecordBlocker,
    PlanningAuditRecordDecision,
    PlanningAuditRecordEntry,
    PlanningAuditRecordError,
    PlanningAuditRecordErrorReason,
    PlanningAuditRecordFactory,
    PlanningAuditRecordField,
    PlanningAuditRecordReason,
    PlanningAuditRecordStatus,
    StrategyAuditRecord,
    StrategyAuditRecordDecision,
    StrategyAuditRecordFactory,
    StrategyPlanningAuditRecord,
    StrategyPlanningAuditRecordFactory,
    generate_planning_audit_record,
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


def test_invalid_manifest_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditRecordError,
        match="INVALID_AUDIT_MANIFEST_DECISION",
    ) as captured:
        StrategyPlanningAuditRecordFactory().generate("invalid")

    assert captured.value.reason == (PlanningAuditRecordErrorReason.INVALID_AUDIT_MANIFEST_DECISION)


def test_bullish_record_is_created() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())

    assert decision.status == (PlanningAuditRecordStatus.CREATED)
    assert decision.reason == (PlanningAuditRecordReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_record is True


def test_bearish_record_is_created() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bearish_audit_manifest())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.record_required.side == StrategyOrderSide.SELL


def test_blocked_manifest_produces_no_record() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(blocked_audit_manifest())

    assert decision.is_blocked is True
    assert decision.record is None
    assert decision.has_record is False
    assert decision.reason == (PlanningAuditRecordReason.AUDIT_MANIFEST_BLOCKED)
    assert decision.blockers == (PlanningAuditRecordBlocker.AUDIT_MANIFEST_BLOCKED,)


def test_record_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(blocked_audit_manifest())

    with pytest.raises(
        ValueError,
        match="No planning-audit record",
    ):
        _ = decision.record_required


def test_record_preserves_manifest_decision() -> None:
    manifest_decision = bullish_audit_manifest()
    record = StrategyPlanningAuditRecordFactory().generate(manifest_decision).record_required

    assert record.audit_manifest is manifest_decision
    assert record.manifest is manifest_decision.manifest_required


def test_record_has_eleven_entries() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert record.entry_count == 11


def test_entry_field_order_is_deterministic() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert tuple(entry.field for entry in record.entries) == (
        PlanningAuditRecordField.MANIFEST_SCHEMA_VERSION,
        PlanningAuditRecordField.MANIFEST_DIGEST,
        PlanningAuditRecordField.BROKER_SYMBOL,
        PlanningAuditRecordField.OBSERVED_AT,
        PlanningAuditRecordField.DIRECTION,
        PlanningAuditRecordField.SIDE,
        PlanningAuditRecordField.PACKAGE_ID,
        PlanningAuditRecordField.PACKAGE_STABLE_ID,
        PlanningAuditRecordField.MANIFEST_ID,
        PlanningAuditRecordField.MANIFEST_STABLE_ID,
        PlanningAuditRecordField.MANIFEST_CANONICAL_PAYLOAD,
    )


def test_record_values_match_manifest() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required
    manifest = record.manifest
    values = {entry.field: entry.value for entry in record.entries}

    assert values[PlanningAuditRecordField.MANIFEST_SCHEMA_VERSION] == manifest.schema_version
    assert values[PlanningAuditRecordField.MANIFEST_DIGEST] == manifest.digest
    assert values[PlanningAuditRecordField.BROKER_SYMBOL] == manifest.broker_symbol
    assert values[PlanningAuditRecordField.OBSERVED_AT] == manifest.observed_at.isoformat()
    assert values[PlanningAuditRecordField.DIRECTION] == manifest.direction.value
    assert values[PlanningAuditRecordField.SIDE] == manifest.side.value
    assert values[PlanningAuditRecordField.PACKAGE_ID] == manifest.package.package_id
    assert values[PlanningAuditRecordField.MANIFEST_ID] == manifest.manifest_id
    assert values[PlanningAuditRecordField.MANIFEST_CANONICAL_PAYLOAD] == manifest.canonical_payload


def test_record_preserves_metadata() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert record.broker_symbol == "XAUUSDm"
    assert record.observed_at == OBSERVED_AT
    assert record.direction == (DirectionalPermissionDirection.BULLISH)
    assert record.side == StrategyOrderSide.BUY
    assert record.manifest_digest == (record.manifest.digest)
    assert record.schema_version == (PLANNING_AUDIT_RECORD_SCHEMA_VERSION)


def test_canonical_json_is_valid() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required
    parsed = json.loads(record.canonical_json)

    assert parsed["schema_version"] == "1.0"
    assert len(parsed["entries"]) == 11


def test_record_digest_is_lowercase_sha256() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert len(record.record_digest) == 64
    assert record.record_digest == record.record_digest.lower()
    assert set(record.record_digest) <= set("0123456789abcdef")
    assert record.digest_algorithm == "SHA-256"


def test_record_digest_matches_canonical_json() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required
    expected = hashlib.sha256(record.canonical_json.encode("utf-8")).hexdigest()

    assert record.record_digest == expected


def test_record_generation_is_canonical() -> None:
    factory = StrategyPlanningAuditRecordFactory()
    manifest = bullish_audit_manifest()

    first = factory.generate(manifest).record_required
    second = factory.generate(manifest).record_required

    assert first.canonical_json == second.canonical_json
    assert first.record_digest == second.record_digest


def test_record_is_serialization_ready_only() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert record.is_serialization_ready is True
    assert record.is_persisted is False
    assert record.can_write_storage is False
    assert record.can_write_network is False


def test_record_never_authorizes_execution() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert record.execution_authorized is False
    assert record.has_broker_request is False
    assert record.can_submit_order is False
    assert record.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())

    assert decision.can_write_storage is False
    assert decision.can_write_network is False
    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "save",
        "persist",
        "write",
        "write_file",
        "insert",
        "send_network",
        "request",
        "order_request",
        "broker_ticket",
        "authorize",
        "submit",
        "send_order",
        "order_send",
    ],
)
def test_record_contains_no_write_or_execution_surface(
    attribute_name: str,
) -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert not hasattr(record, attribute_name)


def test_record_id_is_deterministic() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    assert record.record_id == (f"XAUUSDm:BUY:PLANNING_AUDIT_RECORD:SHA256[{record.record_digest}]")


def test_record_stable_id_is_deterministic() -> None:
    manifest = bullish_audit_manifest()
    record = StrategyPlanningAuditRecordFactory().generate(manifest).record_required

    assert record.stable_id == (f"{manifest.stable_id}:PLANNING_AUDIT_RECORD:{record.record_id}")


def test_created_decision_stable_id_is_deterministic() -> None:
    manifest = bullish_audit_manifest()
    decision = StrategyPlanningAuditRecordFactory().generate(manifest)

    assert decision.stable_id == (
        f"{manifest.stable_id}:PLANNING_AUDIT_RECORD_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    manifest = blocked_audit_manifest()
    decision = StrategyPlanningAuditRecordFactory().generate(manifest)

    assert decision.stable_id == (
        f"{manifest.stable_id}:"
        "PLANNING_AUDIT_RECORD_GENERATION:"
        "BLOCKED:AUDIT_MANIFEST_BLOCKED:"
        "AUDIT_MANIFEST_BLOCKED"
    )


def test_direct_record_rejects_blocked_manifest() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="created audit manifest",
    ):
        replace(
            record,
            audit_manifest=blocked_audit_manifest(),
        )


def test_direct_record_rejects_wrong_schema() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            record,
            schema_version="2.0",
        )


def test_direct_record_requires_tuple_entries() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="tuple",
    ):
        replace(
            record,
            entries=list(record.entries),
        )


def test_direct_record_rejects_missing_entry() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="exactly match",
    ):
        replace(
            record,
            entries=record.entries[:-1],
        )


def test_direct_record_rejects_reordered_entries() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            record,
            entries=tuple(reversed(record.entries)),
        )


def test_direct_record_rejects_foreign_value() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required
    modified = replace(
        record.entries[0],
        value="FOREIGN_VALUE",
    )

    with pytest.raises(
        ValueError,
        match="exactly match",
    ):
        replace(
            record,
            entries=(
                modified,
                *record.entries[1:],
            ),
        )


def test_entry_rejects_raw_field() -> None:
    with pytest.raises(
        ValueError,
        match="PlanningAuditRecordField",
    ):
        PlanningAuditRecordEntry(
            field="BROKER_SYMBOL",
            value="XAUUSDm",
        )


def test_direct_record_rejects_wrong_digest() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            record,
            record_digest="0" * 64,
        )


def test_direct_record_rejects_uppercase_digest() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(
        ValueError,
        match="lowercase",
    ):
        replace(
            record,
            record_digest=record.record_digest.upper(),
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PlanningAuditRecordStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditRecordReason.AUDIT_MANIFEST_BLOCKED),
        )


def test_manual_decision_rejects_missing_record() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            record=None,
        )


def test_manual_decision_rejects_unexpected_record() -> None:
    blocked = StrategyPlanningAuditRecordFactory().generate(blocked_audit_manifest())
    created_record = (
        StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            record=created_record,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(blocked_audit_manifest())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditRecordBlocker.AUDIT_MANIFEST_BLOCKED,
                PlanningAuditRecordBlocker.AUDIT_MANIFEST_BLOCKED,
            ),
        )


def test_entry_is_immutable() -> None:
    entry = (
        StrategyPlanningAuditRecordFactory()
        .generate(bullish_audit_manifest())
        .record_required.entries[0]
    )

    with pytest.raises(FrozenInstanceError):
        entry.value = "modified"


def test_record_is_immutable() -> None:
    record = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest()).record_required

    with pytest.raises(FrozenInstanceError):
        record.record_digest = "0" * 64


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditRecordStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditRecordFactory()
    manifest = bullish_audit_manifest()

    assert factory.generate(manifest) == factory.generate(manifest)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_record(bullish_audit_manifest())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditRecordFactory()
    manifest = bullish_audit_manifest()

    assert factory.build(manifest) == factory.generate(manifest)
    assert factory.evaluate(manifest) == factory.generate(manifest)


def test_public_aliases_are_preserved() -> None:
    assert AuditRecord is StrategyPlanningAuditRecord
    assert AuditRecordDecision is PlanningAuditRecordDecision
    assert AuditRecordEntry is PlanningAuditRecordEntry
    assert AuditRecordFactory is StrategyPlanningAuditRecordFactory
    assert AuditRecordField is PlanningAuditRecordField
    assert PlanningAuditRecord is StrategyPlanningAuditRecord
    assert PlanningAuditRecordFactory is StrategyPlanningAuditRecordFactory
    assert StrategyAuditRecord is StrategyPlanningAuditRecord
    assert StrategyAuditRecordDecision is PlanningAuditRecordDecision
    assert StrategyAuditRecordFactory is StrategyPlanningAuditRecordFactory
