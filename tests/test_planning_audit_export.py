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
from app.strategy.planning_audit_export import (
    PLANNING_AUDIT_EXPORT_SCHEMA_VERSION,
    AuditExportEnvelope,
    AuditExportFactory,
    PlanningAuditExportBlocker,
    PlanningAuditExportEncoding,
    PlanningAuditExportEnvelope,
    PlanningAuditExportError,
    PlanningAuditExportErrorReason,
    PlanningAuditExportFactory,
    PlanningAuditExportMediaType,
    PlanningAuditExportReason,
    PlanningAuditExportStatus,
    StrategyAuditExportEnvelope,
    StrategyAuditExportFactory,
    StrategyPlanningAuditExportEnvelope,
    StrategyPlanningAuditExportFactory,
    generate_planning_audit_export,
)
from app.strategy.planning_audit_manifest import (
    StrategyPlanningAuditManifestFactory,
)
from app.strategy.planning_audit_record import (
    StrategyPlanningAuditRecordFactory,
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


def test_invalid_audit_record_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditExportError,
        match="INVALID_AUDIT_RECORD_DECISION",
    ) as captured:
        StrategyPlanningAuditExportFactory().generate("invalid")

    assert captured.value.reason == (PlanningAuditExportErrorReason.INVALID_AUDIT_RECORD_DECISION)


def test_bullish_export_is_created() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bullish_audit_record())

    assert decision.status == (PlanningAuditExportStatus.CREATED)
    assert decision.reason == (PlanningAuditExportReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_envelope is True


def test_bearish_export_is_created() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bearish_audit_record())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.envelope_required.side == StrategyOrderSide.SELL


def test_blocked_record_produces_no_envelope() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(blocked_audit_record())

    assert decision.is_blocked is True
    assert decision.envelope is None
    assert decision.has_envelope is False
    assert decision.reason == (PlanningAuditExportReason.AUDIT_RECORD_BLOCKED)
    assert decision.blockers == (PlanningAuditExportBlocker.AUDIT_RECORD_BLOCKED,)


def test_envelope_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(blocked_audit_record())

    with pytest.raises(
        ValueError,
        match="No planning-audit export envelope",
    ):
        _ = decision.envelope_required


def test_envelope_preserves_record_decision() -> None:
    audit_record = bullish_audit_record()
    envelope = StrategyPlanningAuditExportFactory().generate(audit_record).envelope_required

    assert envelope.audit_record is audit_record
    assert envelope.record is audit_record.record_required


def test_envelope_preserves_manifest() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.manifest is envelope.record.manifest
    assert envelope.manifest_digest == (envelope.record.manifest_digest)
    assert envelope.record_digest == (envelope.record.record_digest)


def test_envelope_preserves_metadata() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.broker_symbol == "XAUUSDm"
    assert envelope.observed_at == OBSERVED_AT
    assert envelope.direction == (DirectionalPermissionDirection.BULLISH)
    assert envelope.side == StrategyOrderSide.BUY


def test_envelope_uses_json_utf8_contract() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.schema_version == (PLANNING_AUDIT_EXPORT_SCHEMA_VERSION)
    assert envelope.media_type == (PlanningAuditExportMediaType.JSON)
    assert envelope.encoding == (PlanningAuditExportEncoding.UTF_8)


def test_content_matches_canonical_record_json() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.content == envelope.record.canonical_json


def test_content_bytes_use_utf8() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.content_bytes == (envelope.content.encode("utf-8"))


def test_content_length_matches_utf8_payload() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.content_length_bytes == len(envelope.content.encode("utf-8"))
    assert envelope.content_length_bytes > 0


def test_content_digest_is_lowercase_sha256() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert len(envelope.content_digest) == 64
    assert envelope.content_digest == envelope.content_digest.lower()
    assert set(envelope.content_digest) <= set("0123456789abcdef")
    assert envelope.digest_algorithm == "SHA-256"


def test_content_digest_matches_payload() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )
    expected = hashlib.sha256(envelope.content_bytes).hexdigest()

    assert envelope.content_digest == expected


def test_content_digest_matches_record_digest() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.content_digest == envelope.record.record_digest


def test_export_payload_is_valid_json() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )
    parsed = json.loads(envelope.content)

    assert parsed["schema_version"] == "1.0"
    assert len(parsed["entries"]) == 11


def test_export_generation_is_canonical() -> None:
    factory = StrategyPlanningAuditExportFactory()
    audit_record = bullish_audit_record()

    first = factory.generate(audit_record).envelope_required
    second = factory.generate(audit_record).envelope_required

    assert first.content == second.content
    assert first.content_length_bytes == second.content_length_bytes
    assert first.content_digest == second.content_digest


def test_envelope_is_export_ready_only() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.is_export_ready is True
    assert envelope.is_persisted is False
    assert envelope.can_write_storage is False
    assert envelope.can_write_network is False


def test_envelope_never_authorizes_execution() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.execution_authorized is False
    assert envelope.has_broker_request is False
    assert envelope.can_submit_order is False
    assert envelope.is_executable is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bullish_audit_record())

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
        "save",
        "persist",
        "write",
        "write_file",
        "insert",
        "upload",
        "post",
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
def test_envelope_contains_no_write_or_execution_surface(
    attribute_name: str,
) -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert not hasattr(envelope, attribute_name)


def test_envelope_id_is_deterministic() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    assert envelope.envelope_id == (
        "XAUUSDm:BUY:"
        "PLANNING_AUDIT_EXPORT:"
        "JSON:"
        "UTF8:"
        f"BYTES[{envelope.content_length_bytes}]:"
        f"SHA256[{envelope.content_digest}]"
    )


def test_envelope_stable_id_is_deterministic() -> None:
    audit_record = bullish_audit_record()
    envelope = StrategyPlanningAuditExportFactory().generate(audit_record).envelope_required

    assert envelope.stable_id == (
        f"{audit_record.stable_id}:PLANNING_AUDIT_EXPORT_ENVELOPE:{envelope.envelope_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    audit_record = bullish_audit_record()
    decision = StrategyPlanningAuditExportFactory().generate(audit_record)

    assert decision.stable_id == (
        f"{audit_record.stable_id}:PLANNING_AUDIT_EXPORT_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    audit_record = blocked_audit_record()
    decision = StrategyPlanningAuditExportFactory().generate(audit_record)

    assert decision.stable_id == (
        f"{audit_record.stable_id}:"
        "PLANNING_AUDIT_EXPORT_GENERATION:"
        "BLOCKED:AUDIT_RECORD_BLOCKED:"
        "AUDIT_RECORD_BLOCKED"
    )


def test_direct_envelope_rejects_blocked_record() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="created planning-audit record",
    ):
        replace(
            envelope,
            audit_record=blocked_audit_record(),
        )


def test_direct_envelope_rejects_wrong_schema() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            envelope,
            schema_version="2.0",
        )


def test_direct_envelope_rejects_raw_media_type() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="PlanningAuditExportMediaType",
    ):
        replace(
            envelope,
            media_type="application/json",
        )


def test_direct_envelope_rejects_raw_encoding() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="PlanningAuditExportEncoding",
    ):
        replace(
            envelope,
            encoding="utf-8",
        )


def test_direct_envelope_rejects_wrong_content() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="exactly match",
    ):
        replace(
            envelope,
            content=envelope.content + " ",
        )


@pytest.mark.parametrize(
    "content_length_bytes",
    [
        0,
        -1,
        True,
    ],
)
def test_direct_envelope_rejects_invalid_length_type(
    content_length_bytes: object,
) -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(ValueError):
        replace(
            envelope,
            content_length_bytes=content_length_bytes,
        )


def test_direct_envelope_rejects_wrong_length() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="payload size",
    ):
        replace(
            envelope,
            content_length_bytes=(envelope.content_length_bytes + 1),
        )


def test_direct_envelope_rejects_wrong_digest() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    wrong_digest = "0" * 64 if envelope.content_digest != "0" * 64 else "1" * 64

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            envelope,
            content_digest=wrong_digest,
        )


def test_direct_envelope_rejects_uppercase_digest() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="lowercase",
    ):
        replace(
            envelope,
            content_digest="A" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bullish_audit_record())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PlanningAuditExportStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bullish_audit_record())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditExportReason.AUDIT_RECORD_BLOCKED),
        )


def test_manual_decision_rejects_missing_envelope() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bullish_audit_record())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            envelope=None,
        )


def test_manual_decision_rejects_unexpected_envelope() -> None:
    blocked = StrategyPlanningAuditExportFactory().generate(blocked_audit_record())
    created_envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            envelope=created_envelope,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(blocked_audit_record())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditExportBlocker.AUDIT_RECORD_BLOCKED,
                PlanningAuditExportBlocker.AUDIT_RECORD_BLOCKED,
            ),
        )


def test_envelope_is_immutable() -> None:
    envelope = (
        StrategyPlanningAuditExportFactory().generate(bullish_audit_record()).envelope_required
    )

    with pytest.raises(FrozenInstanceError):
        envelope.content = "{}"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditExportFactory().generate(bullish_audit_record())

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditExportStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditExportFactory()
    audit_record = bullish_audit_record()

    assert factory.generate(audit_record) == factory.generate(audit_record)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_export(bullish_audit_record())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditExportFactory()
    audit_record = bullish_audit_record()

    assert factory.build(audit_record) == factory.generate(audit_record)
    assert factory.evaluate(audit_record) == factory.generate(audit_record)


def test_public_aliases_are_preserved() -> None:
    assert AuditExportEnvelope is StrategyPlanningAuditExportEnvelope
    assert AuditExportFactory is StrategyPlanningAuditExportFactory
    assert PlanningAuditExportEnvelope is StrategyPlanningAuditExportEnvelope
    assert PlanningAuditExportFactory is StrategyPlanningAuditExportFactory
    assert StrategyAuditExportEnvelope is StrategyPlanningAuditExportEnvelope
    assert StrategyAuditExportFactory is StrategyPlanningAuditExportFactory
