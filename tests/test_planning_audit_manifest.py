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
from app.strategy.planning_audit_manifest import (
    PLANNING_AUDIT_SCHEMA_VERSION,
    AuditLineageComponent,
    AuditLineageEntry,
    PlanningAuditComponent,
    PlanningAuditLineageEntry,
    PlanningAuditManifest,
    PlanningAuditManifestBlocker,
    PlanningAuditManifestDecision,
    PlanningAuditManifestError,
    PlanningAuditManifestErrorReason,
    PlanningAuditManifestFactory,
    PlanningAuditManifestReason,
    PlanningAuditManifestStatus,
    StrategyAuditManifest,
    StrategyAuditManifestDecision,
    StrategyAuditManifestFactory,
    StrategyPlanningAuditManifest,
    StrategyPlanningAuditManifestFactory,
    generate_planning_audit_manifest,
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


def test_invalid_planning_package_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditManifestError,
        match="INVALID_PLANNING_PACKAGE_DECISION",
    ) as captured:
        StrategyPlanningAuditManifestFactory().generate("invalid")

    assert captured.value.reason == (
        PlanningAuditManifestErrorReason.INVALID_PLANNING_PACKAGE_DECISION
    )


def test_bullish_manifest_is_created() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())

    assert decision.status == (PlanningAuditManifestStatus.CREATED)
    assert decision.reason == (PlanningAuditManifestReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_manifest is True


def test_bearish_manifest_is_created() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bearish_planning_package())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.manifest_required.side == StrategyOrderSide.SELL


def test_blocked_package_produces_no_manifest() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(blocked_planning_package())

    assert decision.is_blocked is True
    assert decision.manifest is None
    assert decision.has_manifest is False
    assert decision.reason == (PlanningAuditManifestReason.PLANNING_PACKAGE_BLOCKED)
    assert decision.blockers == (PlanningAuditManifestBlocker.PLANNING_PACKAGE_BLOCKED,)


def test_manifest_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(blocked_planning_package())

    with pytest.raises(
        ValueError,
        match="No planning-audit manifest",
    ):
        _ = decision.manifest_required


def test_manifest_preserves_package_decision() -> None:
    planning_package = bullish_planning_package()
    manifest = StrategyPlanningAuditManifestFactory().generate(planning_package).manifest_required

    assert manifest.planning_package is planning_package
    assert manifest.package is planning_package.package_required


def test_manifest_has_seven_components() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert manifest.component_count == 7


def test_lineage_component_order_is_deterministic() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert tuple(entry.component for entry in manifest.lineage) == (
        PlanningAuditComponent.RISK_ADMISSION,
        PlanningAuditComponent.SIZING_HANDOFF,
        PlanningAuditComponent.SIZING_SPECIFICATION,
        PlanningAuditComponent.POSITION_SIZE,
        PlanningAuditComponent.SIZED_TRADE_PLAN,
        PlanningAuditComponent.ORDER_INTENT,
        PlanningAuditComponent.EXECUTION_LOCK,
    )


def test_lineage_matches_package_stable_ids() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )
    package = manifest.package

    assert tuple(entry.stable_id for entry in manifest.lineage) == (
        package.risk_admission.stable_id,
        package.sizing_handoff.stable_id,
        package.sizing_specification.stable_id,
        package.position_size.stable_id,
        package.sized_plan.stable_id,
        package.order_intent.stable_id,
        package.execution_lock.stable_id,
    )


def test_manifest_preserves_metadata() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert manifest.broker_symbol == "XAUUSDm"
    assert manifest.observed_at == OBSERVED_AT
    assert manifest.direction == (DirectionalPermissionDirection.BULLISH)
    assert manifest.side == StrategyOrderSide.BUY
    assert manifest.schema_version == (PLANNING_AUDIT_SCHEMA_VERSION)


def test_digest_is_lowercase_sha256() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert len(manifest.digest) == 64
    assert manifest.digest == manifest.digest.lower()
    assert set(manifest.digest) <= set("0123456789abcdef")
    assert manifest.digest_algorithm == "SHA-256"
    assert manifest.is_tamper_evident is True


def test_digest_matches_canonical_payload() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )
    expected = hashlib.sha256(manifest.canonical_payload.encode("utf-8")).hexdigest()

    assert manifest.digest == expected


def test_canonical_payload_is_deterministic() -> None:
    factory = StrategyPlanningAuditManifestFactory()
    planning_package = bullish_planning_package()

    first = factory.generate(planning_package).manifest_required
    second = factory.generate(planning_package).manifest_required

    assert first.canonical_payload == second.canonical_payload
    assert first.digest == second.digest


def test_payload_contains_package_identity() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert "SCHEMA_VERSION=1.0" in manifest.canonical_payload
    assert "BROKER_SYMBOL=XAUUSDm" in manifest.canonical_payload
    assert f"PACKAGE_ID={manifest.package.package_id}" in manifest.canonical_payload
    assert f"PACKAGE_STABLE_ID={manifest.package.stable_id}" in manifest.canonical_payload


def test_payload_contains_every_lineage_entry() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    for entry in manifest.lineage:
        assert entry.canonical_line in manifest.canonical_payload


def test_manifest_id_is_deterministic() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert manifest.manifest_id == (f"XAUUSDm:BUY:PLANNING_AUDIT:SHA256[{manifest.digest}]")


def test_manifest_stable_id_is_deterministic() -> None:
    planning_package = bullish_planning_package()
    manifest = StrategyPlanningAuditManifestFactory().generate(planning_package).manifest_required

    assert manifest.stable_id == (
        f"{planning_package.stable_id}:PLANNING_AUDIT_MANIFEST:{manifest.manifest_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    planning_package = bullish_planning_package()
    decision = StrategyPlanningAuditManifestFactory().generate(planning_package)

    assert decision.stable_id == (
        f"{planning_package.stable_id}:PLANNING_AUDIT_MANIFEST_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    planning_package = blocked_planning_package()
    decision = StrategyPlanningAuditManifestFactory().generate(planning_package)

    assert decision.stable_id == (
        f"{planning_package.stable_id}:"
        "PLANNING_AUDIT_MANIFEST_GENERATION:"
        "BLOCKED:PLANNING_PACKAGE_BLOCKED:"
        "PLANNING_PACKAGE_BLOCKED"
    )


def test_manifest_never_authorizes_execution() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert manifest.execution_authorized is False
    assert manifest.has_broker_request is False
    assert manifest.can_submit_order is False
    assert manifest.is_executable is False


def test_manifest_performs_no_persistence() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert manifest.is_persisted is False
    assert manifest.can_write_storage is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())

    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_write_storage is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "request",
        "request_dict",
        "order_request",
        "order_type",
        "broker_ticket",
        "authorize",
        "submit",
        "send_order",
        "order_send",
        "save",
        "persist",
        "write_file",
    ],
)
def test_manifest_contains_no_execution_or_write_surface(
    attribute_name: str,
) -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    assert not hasattr(manifest, attribute_name)


def test_direct_manifest_rejects_blocked_package() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="created strategy-planning package",
    ):
        replace(
            manifest,
            planning_package=blocked_planning_package(),
        )


def test_direct_manifest_rejects_wrong_schema() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        replace(
            manifest,
            schema_version="2.0",
        )


def test_direct_manifest_requires_tuple_lineage() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="tuple",
    ):
        replace(
            manifest,
            lineage=list(manifest.lineage),
        )


def test_direct_manifest_rejects_missing_lineage_entry() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="exactly match",
    ):
        replace(
            manifest,
            lineage=manifest.lineage[:-1],
        )


def test_direct_manifest_rejects_reordered_lineage() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            manifest,
            lineage=tuple(reversed(manifest.lineage)),
        )


def test_direct_manifest_rejects_foreign_stable_id() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )
    modified_entry = replace(
        manifest.lineage[0],
        stable_id="FOREIGN_STABLE_ID",
    )

    with pytest.raises(
        ValueError,
        match="exactly match",
    ):
        replace(
            manifest,
            lineage=(
                modified_entry,
                *manifest.lineage[1:],
            ),
        )


def test_lineage_entry_rejects_raw_component() -> None:
    with pytest.raises(
        ValueError,
        match="PlanningAuditComponent",
    ):
        PlanningAuditLineageEntry(
            component="RISK_ADMISSION",
            stable_id="stable",
        )


def test_direct_manifest_rejects_wrong_digest() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="digest does not match",
    ):
        replace(
            manifest,
            digest="0" * 64,
        )


def test_direct_manifest_rejects_uppercase_digest() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="lowercase SHA-256",
    ):
        replace(
            manifest,
            digest=manifest.digest.upper(),
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PlanningAuditManifestStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PlanningAuditManifestReason.PLANNING_PACKAGE_BLOCKED),
        )


def test_manual_decision_rejects_missing_manifest() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            manifest=None,
        )


def test_manual_decision_rejects_unexpected_manifest() -> None:
    blocked = StrategyPlanningAuditManifestFactory().generate(blocked_planning_package())
    created_manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            manifest=created_manifest,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(blocked_planning_package())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PlanningAuditManifestBlocker.PLANNING_PACKAGE_BLOCKED,
                PlanningAuditManifestBlocker.PLANNING_PACKAGE_BLOCKED,
            ),
        )


def test_lineage_entry_is_immutable() -> None:
    entry = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required.lineage[0]
    )

    with pytest.raises(FrozenInstanceError):
        entry.stable_id = "modified"


def test_manifest_is_immutable() -> None:
    manifest = (
        StrategyPlanningAuditManifestFactory()
        .generate(bullish_planning_package())
        .manifest_required
    )

    with pytest.raises(FrozenInstanceError):
        manifest.digest = "0" * 64


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditManifestStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningAuditManifestFactory()
    planning_package = bullish_planning_package()

    assert factory.generate(planning_package) == factory.generate(planning_package)


def test_function_api_delegates() -> None:
    decision = generate_planning_audit_manifest(bullish_planning_package())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningAuditManifestFactory()
    planning_package = bullish_planning_package()

    assert factory.build(planning_package) == factory.generate(planning_package)
    assert factory.evaluate(planning_package) == factory.generate(planning_package)


def test_public_aliases_are_preserved() -> None:
    assert AuditLineageComponent is PlanningAuditComponent
    assert AuditLineageEntry is PlanningAuditLineageEntry
    assert PlanningAuditManifest is StrategyPlanningAuditManifest
    assert PlanningAuditManifestFactory is StrategyPlanningAuditManifestFactory
    assert StrategyAuditManifest is StrategyPlanningAuditManifest
    assert StrategyAuditManifestDecision is PlanningAuditManifestDecision
    assert StrategyAuditManifestFactory is StrategyPlanningAuditManifestFactory
