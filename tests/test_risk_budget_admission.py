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
    RewardRiskAnalysisDecision,
    RewardRiskAnalysisPolicy,
    StrategyRewardRiskAnalysisGate,
)
from app.strategy.risk_budget_admission import (
    AccountRiskSnapshot,
    RiskAdmissionBlocker,
    RiskAdmissionDecision,
    RiskAdmissionGate,
    RiskAdmissionPolicy,
    RiskAdmissionReason,
    RiskAdmissionStatus,
    RiskBudgetAdmissionBlocker,
    RiskBudgetAdmissionDecision,
    RiskBudgetAdmissionError,
    RiskBudgetAdmissionErrorReason,
    RiskBudgetAdmissionPolicy,
    RiskBudgetAdmissionReason,
    RiskBudgetAdmissionStatus,
    StrategyRiskAdmissionGate,
    StrategyRiskBudgetAdmissionGate,
    StrategyRiskBudgetSnapshot,
    evaluate_risk_budget_admission,
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


def reward_risk_for(
    direction: DirectionalPermissionDirection,
    *,
    ratio: Decimal = Decimal("2"),
) -> RewardRiskAnalysisDecision:
    if direction == DirectionalPermissionDirection.BULLISH:
        selected_bias = MarketStructureBias.BULLISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2340")
        target_value = entry_value + Decimal("10") * ratio
    elif direction == DirectionalPermissionDirection.BEARISH:
        selected_bias = MarketStructureBias.BEARISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2360")
        target_value = entry_value - Decimal("10") * ratio
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
    availability_snapshot = PriceReferenceAvailabilitySnapshot(
        plan=plan,
        items=tuple(
            PriceReferenceAvailabilityItem(
                requirement=requirement,
                available=True,
            )
            for requirement in plan.requirements
        ),
    )
    availability = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot,
    )
    role_values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    observations = tuple(
        PriceReferenceValueObservation(
            requirement=requirement,
            value=role_values[requirement.role],
        )
        for requirement in (
            availability.selected_entry,
            availability.selected_stop,
            availability.selected_target,
        )
        if requirement is not None
    )
    resolution = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=observations,
        ),
    )

    return StrategyRewardRiskAnalysisGate(
        RewardRiskAnalysisPolicy(minimum_reward_risk=Decimal("2"))
    ).evaluate(resolution)


@lru_cache(maxsize=1)
def qualified_bullish_reward_risk() -> RewardRiskAnalysisDecision:
    return reward_risk_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def qualified_bearish_reward_risk() -> RewardRiskAnalysisDecision:
    return reward_risk_for(
        DirectionalPermissionDirection.BEARISH,
        ratio=Decimal("2.5"),
    )


@lru_cache(maxsize=1)
def blocked_reward_risk() -> RewardRiskAnalysisDecision:
    return reward_risk_for(
        DirectionalPermissionDirection.BULLISH,
        ratio=Decimal("1.5"),
    )


def risk_snapshot(
    *,
    observed_at: datetime = OBSERVED_AT,
    equity: Decimal = Decimal("10000"),
    proposed: Decimal = Decimal("100"),
    aggregate: Decimal = Decimal("0"),
    daily_loss: Decimal = Decimal("0"),
    positions: int = 0,
    kill_switch: bool = False,
) -> StrategyRiskBudgetSnapshot:
    return StrategyRiskBudgetSnapshot(
        observed_at=observed_at,
        account_equity=equity,
        proposed_risk_amount=proposed,
        current_aggregate_risk_amount=aggregate,
        realized_daily_loss_amount=daily_loss,
        open_gold_positions=positions,
        kill_switch_active=kill_switch,
    )


def test_default_policy_values() -> None:
    policy = RiskBudgetAdmissionPolicy()

    assert policy.maximum_setup_risk_percent == (Decimal("1"))
    assert policy.maximum_aggregate_risk_percent == (Decimal("2"))
    assert policy.maximum_daily_loss_percent == (Decimal("3"))
    assert policy.maximum_gold_positions == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"maximum_setup_risk_percent": 1},
        {"maximum_setup_risk_percent": Decimal("0")},
        {"maximum_setup_risk_percent": Decimal("101")},
        {"maximum_aggregate_risk_percent": 2},
        {"maximum_aggregate_risk_percent": Decimal("0")},
        {"maximum_daily_loss_percent": 3},
        {"maximum_daily_loss_percent": Decimal("0")},
        {"maximum_gold_positions": 0},
        {"maximum_gold_positions": True},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        RiskBudgetAdmissionPolicy(**overrides)


def test_setup_limit_cannot_exceed_aggregate_limit() -> None:
    with pytest.raises(
        ValueError,
        match="cannot exceed",
    ):
        RiskBudgetAdmissionPolicy(
            maximum_setup_risk_percent=Decimal("3"),
            maximum_aggregate_risk_percent=Decimal("2"),
        )


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="RiskBudgetAdmissionPolicy",
    ):
        StrategyRiskBudgetAdmissionGate(policy="invalid")


def test_invalid_reward_risk_is_fail_safe() -> None:
    with pytest.raises(
        RiskBudgetAdmissionError,
        match="INVALID_REWARD_RISK_DECISION",
    ) as captured:
        StrategyRiskBudgetAdmissionGate().evaluate("invalid")

    assert captured.value.reason == (RiskBudgetAdmissionErrorReason.INVALID_REWARD_RISK_DECISION)


def test_invalid_snapshot_type_is_fail_safe() -> None:
    with pytest.raises(
        RiskBudgetAdmissionError,
        match="INVALID_RISK_SNAPSHOT",
    ):
        StrategyRiskBudgetAdmissionGate().evaluate(
            qualified_bullish_reward_risk(),
            "invalid",
        )


def test_qualified_reward_risk_requires_snapshot() -> None:
    with pytest.raises(
        RiskBudgetAdmissionError,
        match="INVALID_RISK_SNAPSHOT",
    ):
        StrategyRiskBudgetAdmissionGate().evaluate(qualified_bullish_reward_risk())


def test_snapshot_cannot_predate_strategy() -> None:
    snapshot = risk_snapshot(observed_at=OBSERVED_AT - timedelta(seconds=1))

    with pytest.raises(
        RiskBudgetAdmissionError,
        match="cannot predate",
    ):
        StrategyRiskBudgetAdmissionGate().evaluate(
            qualified_bullish_reward_risk(),
            snapshot,
        )


def test_blocked_reward_risk_needs_no_snapshot() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(blocked_reward_risk())

    assert decision.is_blocked is True
    assert decision.snapshot is None
    assert decision.metrics is None
    assert decision.reason == (RiskBudgetAdmissionReason.REWARD_RISK_BLOCKED)
    assert decision.blockers == (RiskBudgetAdmissionBlocker.REWARD_RISK_BLOCKED,)


def test_default_snapshot_is_admitted() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.status == (RiskBudgetAdmissionStatus.ADMITTED)
    assert decision.reason == (RiskBudgetAdmissionReason.ADMITTED)
    assert decision.blockers == ()
    assert decision.is_admitted is True


def test_bearish_setup_can_be_admitted() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bearish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.is_admitted is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)


def test_exact_setup_risk_limit_is_admitted() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(proposed=Decimal("100")),
    )

    assert decision.is_admitted is True
    assert decision.metrics is not None
    assert decision.metrics.proposed_risk_percent == (Decimal("1"))


def test_exact_aggregate_risk_limit_is_admitted() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(
            proposed=Decimal("100"),
            aggregate=Decimal("100"),
        ),
    )

    assert decision.is_admitted is True
    assert decision.metrics is not None
    assert decision.metrics.aggregate_risk_after_percent == Decimal("2")


def test_kill_switch_blocks() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(kill_switch=True),
    )

    assert decision.reason == (RiskBudgetAdmissionReason.KILL_SWITCH_ACTIVE)
    assert decision.blockers == (RiskBudgetAdmissionBlocker.KILL_SWITCH_ACTIVE,)


def test_existing_gold_position_blocks() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(positions=1),
    )

    assert decision.reason == (RiskBudgetAdmissionReason.GOLD_POSITION_LIMIT_REACHED)


def test_daily_loss_threshold_blocks() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(daily_loss=Decimal("300")),
    )

    assert decision.reason == (RiskBudgetAdmissionReason.DAILY_LOSS_LIMIT_REACHED)


def test_daily_loss_below_threshold_is_allowed() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(daily_loss=Decimal("299.99")),
    )

    assert decision.is_admitted is True


def test_setup_risk_above_limit_blocks() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(proposed=Decimal("100.01")),
    )

    assert decision.reason == (RiskBudgetAdmissionReason.SETUP_RISK_LIMIT_EXCEEDED)


def test_aggregate_risk_above_limit_blocks() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(
            proposed=Decimal("100"),
            aggregate=Decimal("100.01"),
        ),
    )

    assert decision.reason == (RiskBudgetAdmissionReason.AGGREGATE_RISK_LIMIT_EXCEEDED)


def test_multiple_blockers_preserve_order() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(
            proposed=Decimal("150"),
            aggregate=Decimal("100"),
            daily_loss=Decimal("300"),
            positions=1,
            kill_switch=True,
        ),
    )

    assert decision.reason == (RiskBudgetAdmissionReason.MULTIPLE_RISK_BLOCKERS)
    assert decision.blockers == (
        RiskBudgetAdmissionBlocker.KILL_SWITCH_ACTIVE,
        RiskBudgetAdmissionBlocker.GOLD_POSITION_LIMIT_REACHED,
        RiskBudgetAdmissionBlocker.DAILY_LOSS_LIMIT_REACHED,
        RiskBudgetAdmissionBlocker.SETUP_RISK_LIMIT_EXCEEDED,
        RiskBudgetAdmissionBlocker.AGGREGATE_RISK_LIMIT_EXCEEDED,
    )


def test_custom_policy_is_applied() -> None:
    policy = RiskBudgetAdmissionPolicy(
        maximum_setup_risk_percent=Decimal("0.5"),
        maximum_aggregate_risk_percent=Decimal("1"),
        maximum_daily_loss_percent=Decimal("2"),
        maximum_gold_positions=2,
    )
    decision = StrategyRiskBudgetAdmissionGate(policy).evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(
            proposed=Decimal("50"),
            aggregate=Decimal("50"),
            positions=1,
        ),
    )

    assert decision.is_admitted is True


def test_metrics_are_exact() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(
            proposed=Decimal("75"),
            aggregate=Decimal("50"),
            daily_loss=Decimal("25"),
        ),
    )

    metrics = decision.metrics

    assert metrics is not None
    assert metrics.proposed_risk_percent == (Decimal("0.75"))
    assert metrics.aggregate_risk_before_percent == (Decimal("0.5"))
    assert metrics.aggregate_risk_after_percent == (Decimal("1.25"))
    assert metrics.daily_loss_percent == (Decimal("0.25"))


def test_metrics_limits_are_exact() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    metrics = decision.metrics

    assert metrics is not None
    assert metrics.maximum_setup_risk_amount == (Decimal("100"))
    assert metrics.maximum_aggregate_risk_amount == (Decimal("200"))
    assert metrics.maximum_daily_loss_amount == (Decimal("300"))


def test_remaining_aggregate_budget_is_exact() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(
            proposed=Decimal("75"),
            aggregate=Decimal("50"),
        ),
    )

    metrics = decision.metrics

    assert metrics is not None
    assert metrics.remaining_aggregate_risk_before == (Decimal("150"))
    assert metrics.remaining_aggregate_risk_after == (Decimal("75"))


def test_approved_risk_amount_is_exposed() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(proposed=Decimal("75")),
    )

    assert decision.approved_risk_amount == (Decimal("75"))
    assert decision.can_continue_to_position_sizing is True


def test_blocked_decision_has_no_approved_amount() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(kill_switch=True),
    )

    assert decision.approved_risk_amount is None


def test_decision_preserves_metadata() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.reward_risk_ratio == Decimal("2")
    assert decision.blocker_count == 0


def test_decision_is_explicitly_non_executable() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "volume",
        "lot_size",
        "order_type",
        "order_request",
        "broker_ticket",
        "send_order",
    ],
)
def test_decision_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
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
        {"account_equity": Decimal("0")},
        {"proposed_risk_amount": Decimal("0")},
        {"current_aggregate_risk_amount": (Decimal("-1"))},
        {"realized_daily_loss_amount": (Decimal("-1"))},
        {"open_gold_positions": -1},
        {"open_gold_positions": True},
        {"kill_switch_active": 1},
    ],
)
def test_invalid_snapshot_is_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "observed_at": OBSERVED_AT,
        "account_equity": Decimal("10000"),
        "proposed_risk_amount": Decimal("100"),
        "current_aggregate_risk_amount": Decimal("0"),
        "realized_daily_loss_amount": Decimal("0"),
        "open_gold_positions": 0,
        "kill_switch_active": False,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        StrategyRiskBudgetSnapshot(**values)


def test_snapshot_aggregate_after_is_exact() -> None:
    snapshot = risk_snapshot(
        proposed=Decimal("75"),
        aggregate=Decimal("50"),
    )

    assert snapshot.aggregate_risk_after_admission == (Decimal("125"))


def test_snapshot_stable_id_is_deterministic() -> None:
    snapshot = risk_snapshot()

    assert snapshot.stable_id == (
        f"{OBSERVED_AT.isoformat()}:"
        "EQUITY[10000]:"
        "PROPOSED[100]:"
        "AGGREGATE[0]:"
        "DAILY_LOSS[0]:"
        "GOLD_POSITIONS[0]:"
        "KILL_SWITCH[INACTIVE]"
    )


def test_metrics_reject_inconsistent_aggregate() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.metrics is not None

    with pytest.raises(
        ValueError,
        match="aggregate_risk_after",
    ):
        replace(
            decision.metrics,
            aggregate_risk_after_admission=(Decimal("201")),
        )


def test_metrics_reject_inconsistent_percentage() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.metrics is not None

    with pytest.raises(
        ValueError,
        match="proposed_risk_percent",
    ):
        replace(
            decision.metrics,
            proposed_risk_percent=Decimal("2"),
        )


def test_admitted_stable_id_is_deterministic() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.stable_id.startswith(
        f"{decision.reward_risk.stable_id}:RISK_BUDGET_ADMISSION:ADMITTED:ADMITTED:NONE:"
    )
    assert "PROPOSED_PCT[1]" in decision.stable_id


def test_blocked_stable_id_lists_blocker() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(kill_switch=True),
    )

    assert "KILL_SWITCH_ACTIVE" in decision.stable_id


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=RiskBudgetAdmissionStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(RiskBudgetAdmissionReason.KILL_SWITCH_ACTIVE),
        )


def test_manual_decision_rejects_wrong_metrics() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.metrics is not None
    modified = replace(
        decision.metrics,
        maximum_daily_loss_amount=Decimal("400"),
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
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(kill_switch=True),
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                RiskBudgetAdmissionBlocker.KILL_SWITCH_ACTIVE,
                RiskBudgetAdmissionBlocker.KILL_SWITCH_ACTIVE,
            ),
        )


def test_snapshot_is_immutable() -> None:
    snapshot = risk_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.account_equity = Decimal("9000")


def test_metrics_are_immutable() -> None:
    metrics = (
        StrategyRiskBudgetAdmissionGate()
        .evaluate(
            qualified_bullish_reward_risk(),
            risk_snapshot(),
        )
        .metrics
    )

    assert metrics is not None

    with pytest.raises(FrozenInstanceError):
        metrics.proposed_risk_amount = Decimal("50")


def test_decision_is_immutable() -> None:
    decision = StrategyRiskBudgetAdmissionGate().evaluate(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = RiskBudgetAdmissionStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = RiskBudgetAdmissionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.maximum_setup_risk_percent = Decimal("2")


def test_evaluation_is_deterministic() -> None:
    gate = StrategyRiskBudgetAdmissionGate()
    reward_risk = qualified_bullish_reward_risk()
    snapshot = risk_snapshot()

    assert gate.evaluate(
        reward_risk,
        snapshot,
    ) == gate.evaluate(
        reward_risk,
        snapshot,
    )


def test_function_api_delegates() -> None:
    decision = evaluate_risk_budget_admission(
        qualified_bullish_reward_risk(),
        risk_snapshot(),
    )

    assert decision.is_admitted is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyRiskBudgetAdmissionGate()
    reward_risk = qualified_bullish_reward_risk()
    snapshot = risk_snapshot()

    assert gate.admit(
        reward_risk,
        snapshot,
    ) == gate.evaluate(
        reward_risk,
        snapshot,
    )
    assert gate.check(
        reward_risk,
        snapshot,
    ) == gate.evaluate(
        reward_risk,
        snapshot,
    )


def test_public_aliases_are_preserved() -> None:
    assert AccountRiskSnapshot is StrategyRiskBudgetSnapshot
    assert RiskAdmissionBlocker is RiskBudgetAdmissionBlocker
    assert RiskAdmissionDecision is RiskBudgetAdmissionDecision
    assert RiskAdmissionGate is StrategyRiskBudgetAdmissionGate
    assert RiskAdmissionPolicy is RiskBudgetAdmissionPolicy
    assert RiskAdmissionReason is RiskBudgetAdmissionReason
    assert RiskAdmissionStatus is RiskBudgetAdmissionStatus
    assert StrategyRiskAdmissionGate is StrategyRiskBudgetAdmissionGate


def test_equivalent_decimal_scales_share_stable_ids() -> None:
    baseline_snapshot = risk_snapshot()
    scaled_snapshot = risk_snapshot(
        equity=Decimal("10000.00"),
        proposed=Decimal("100.00"),
        aggregate=Decimal("0.00"),
        daily_loss=Decimal("0.00"),
    )

    assert scaled_snapshot.stable_id == baseline_snapshot.stable_id

    reward_risk = qualified_bullish_reward_risk()
    gate = StrategyRiskBudgetAdmissionGate()

    baseline_decision = gate.evaluate(
        reward_risk,
        baseline_snapshot,
    )
    scaled_decision = gate.evaluate(
        reward_risk,
        scaled_snapshot,
    )

    assert baseline_decision.metrics is not None
    assert scaled_decision.metrics is not None
    assert scaled_decision.metrics.stable_id == baseline_decision.metrics.stable_id
    assert scaled_decision.stable_id == baseline_decision.stable_id
