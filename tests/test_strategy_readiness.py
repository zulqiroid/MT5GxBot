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
from app.strategy.context_freshness import (
    ContextFreshnessPolicy,
    ContextFreshnessReason,
    MultiTimeframeFreshnessGate,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
    DirectionalPermissionPolicy,
    DirectionalPermissionReason,
    MultiTimeframeDirectionalGate,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
    MultiTimeframeContextSnapshot,
)
from app.strategy.strategy_readiness import (
    CompositeStrategyReadinessGate,
    ReadinessBlocker,
    ReadinessDecision,
    ReadinessGate,
    ReadinessPolicy,
    ReadinessReason,
    ReadinessStatus,
    StrategyAnalysisReadinessGate,
    StrategyReadinessBlocker,
    StrategyReadinessDecision,
    StrategyReadinessError,
    StrategyReadinessErrorReason,
    StrategyReadinessPolicy,
    StrategyReadinessReason,
    StrategyReadinessStatus,
    evaluate_strategy_readiness,
)

OBSERVED_AT = datetime(
    2026,
    7,
    25,
    20,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    end_at: datetime = OBSERVED_AT,
    count: int = 8,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    first_open = end_at - duration * count
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
                broker_symbol=broker_symbol,
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
        broker_symbol=broker_symbol,
        timeframe=timeframe,
        candles=tuple(candles),
    )


def build_snapshot(
    *,
    h4_end_at: datetime = OBSERVED_AT,
) -> MultiTimeframeContextSnapshot:
    mapping = {
        timeframe: create_series(
            timeframe,
            end_at=(h4_end_at if timeframe == TimeframeName.H4 else OBSERVED_AT),
        )
        for timeframe in GOLD_TIMEFRAME_HIERARCHY
    }

    return MultiTimeframeContextBuilder().build(mapping)


@lru_cache(maxsize=1)
def neutral_fresh_snapshot() -> MultiTimeframeContextSnapshot:
    return build_snapshot()


def with_biases(
    snapshot: MultiTimeframeContextSnapshot,
    biases: dict[
        TimeframeName,
        MarketStructureBias,
    ],
) -> MultiTimeframeContextSnapshot:
    return replace(
        snapshot,
        structure_biases=tuple(
            (
                timeframe,
                biases.get(
                    timeframe,
                    MarketStructureBias.NEUTRAL,
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )


def bullish_snapshot(
    *,
    stale_h4: bool = False,
) -> MultiTimeframeContextSnapshot:
    snapshot = (
        build_snapshot(h4_end_at=(OBSERVED_AT - timedelta(hours=8)))
        if stale_h4
        else neutral_fresh_snapshot()
    )

    return with_biases(
        snapshot,
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        },
    )


def bearish_snapshot() -> MultiTimeframeContextSnapshot:
    return with_biases(
        neutral_fresh_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BEARISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
        },
    )


def test_default_policy_contains_both_gates() -> None:
    policy = StrategyReadinessPolicy()

    assert isinstance(
        policy.freshness_policy,
        ContextFreshnessPolicy,
    )
    assert isinstance(
        policy.directional_policy,
        DirectionalPermissionPolicy,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("freshness_policy", "invalid"),
        ("directional_policy", "invalid"),
    ],
)
def test_invalid_nested_policy_is_rejected(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        StrategyReadinessPolicy(**{field_name: value})


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="StrategyReadinessPolicy",
    ):
        CompositeStrategyReadinessGate(policy="invalid")


def test_invalid_context_is_fail_safe() -> None:
    with pytest.raises(
        StrategyReadinessError,
        match="INVALID_CONTEXT",
    ) as captured:
        CompositeStrategyReadinessGate().evaluate("invalid")

    assert captured.value.reason == (StrategyReadinessErrorReason.INVALID_CONTEXT)


def test_fresh_bullish_context_is_ready() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    assert decision.status == (StrategyReadinessStatus.READY)
    assert decision.reason == (StrategyReadinessReason.READY)
    assert decision.blockers == ()
    assert decision.is_ready is True
    assert decision.can_analyze_setup is True


def test_fresh_bearish_context_is_ready() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bearish_snapshot())

    assert decision.is_ready is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.is_bearish is True


def test_neutral_direction_is_blocked() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(neutral_fresh_snapshot())

    assert decision.is_blocked is True
    assert decision.reason == (StrategyReadinessReason.DIRECTION_BLOCKED)
    assert decision.blockers == (StrategyReadinessBlocker.DIRECTION_BLOCKED,)
    assert decision.has_directional_blocker is True
    assert decision.has_stale_context is False


def test_stale_bullish_context_is_blocked() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot(stale_h4=True))

    assert decision.is_blocked is True
    assert decision.reason == (StrategyReadinessReason.STALE_CONTEXT)
    assert decision.blockers == (StrategyReadinessBlocker.STALE_CONTEXT,)
    assert decision.has_stale_context is True
    assert decision.has_directional_blocker is False


def test_stale_neutral_context_preserves_both_blockers() -> None:
    snapshot = build_snapshot(h4_end_at=(OBSERVED_AT - timedelta(hours=8)))

    decision = CompositeStrategyReadinessGate().evaluate(snapshot)

    assert decision.reason == (StrategyReadinessReason.STALE_AND_DIRECTION_BLOCKED)
    assert decision.blockers == (
        StrategyReadinessBlocker.STALE_CONTEXT,
        StrategyReadinessBlocker.DIRECTION_BLOCKED,
    )
    assert decision.blocker_count == 2


def test_blocker_order_is_deterministic() -> None:
    snapshot = build_snapshot(h4_end_at=(OBSERVED_AT - timedelta(hours=8)))

    first = CompositeStrategyReadinessGate().evaluate(snapshot)
    second = CompositeStrategyReadinessGate().evaluate(snapshot)

    assert first.blockers == second.blockers
    assert first.blockers[0] == (StrategyReadinessBlocker.STALE_CONTEXT)


def test_component_decisions_are_exposed() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    assert decision.freshness.is_ready is True
    assert decision.directional.is_allowed is True
    assert decision.is_fresh is True
    assert decision.is_directionally_allowed is True


def test_directional_properties_delegate() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.has_direction is True
    assert decision.is_bullish is True
    assert decision.is_bearish is False
    assert decision.alignment_score == Decimal("0.75")


def test_stale_timeframes_delegate() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot(stale_h4=True))

    assert decision.stale_timeframes == (TimeframeName.H4,)
    assert TimeframeName.H4 not in (decision.fresh_timeframes)


def test_component_reasons_delegate() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(neutral_fresh_snapshot())

    assert decision.freshness_reason == (ContextFreshnessReason.ALL_TIMEFRAMES_FRESH)
    assert decision.directional_reason == (DirectionalPermissionReason.HIGHER_TIMEFRAME_UNRESOLVED)


def test_custom_directional_policy_is_respected() -> None:
    policy = StrategyReadinessPolicy(
        directional_policy=(DirectionalPermissionPolicy(allow_neutral_execution_timeframe=False))
    )

    decision = CompositeStrategyReadinessGate(policy).evaluate(bullish_snapshot())

    assert decision.is_blocked is True
    assert decision.directional.reason == (DirectionalPermissionReason.EXECUTION_TIMEFRAME_NEUTRAL)


def test_custom_freshness_policy_is_respected() -> None:
    freshness_policy = ContextFreshnessPolicy(
        maximum_lag_candles=(
            (TimeframeName.H4, 2),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        )
    )
    policy = StrategyReadinessPolicy(freshness_policy=freshness_policy)

    decision = CompositeStrategyReadinessGate(policy).evaluate(bullish_snapshot(stale_h4=True))

    assert decision.freshness.is_ready is True
    assert decision.is_ready is True


def test_exact_two_candle_h4_lag_is_allowed_by_custom_policy() -> None:
    freshness_policy = ContextFreshnessPolicy(
        maximum_lag_candles=(
            (TimeframeName.H4, 2),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        )
    )
    policy = StrategyReadinessPolicy(freshness_policy=freshness_policy)
    decision = CompositeStrategyReadinessGate(policy).evaluate(bullish_snapshot(stale_h4=True))

    detail = decision.freshness.detail_for(TimeframeName.H4)

    assert detail.lag_candle_fraction == Decimal("2")
    assert decision.is_ready is True


def test_decision_preserves_context_metadata() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT


def test_ready_stable_id_is_deterministic() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    assert decision.stable_id == (
        f"{decision.context.stable_id}:STRATEGY_READINESS:READY:READY:NONE"
    )


def test_blocked_stable_id_lists_blockers() -> None:
    snapshot = build_snapshot(h4_end_at=(OBSERVED_AT - timedelta(hours=8)))
    decision = CompositeStrategyReadinessGate().evaluate(snapshot)

    assert decision.stable_id.endswith(
        "STRATEGY_READINESS:BLOCKED:STALE_AND_DIRECTION_BLOCKED:STALE_CONTEXT,DIRECTION_BLOCKED"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=StrategyReadinessStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(StrategyReadinessReason.DIRECTION_BLOCKED),
        )


def test_manual_decision_rejects_wrong_blockers() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            blockers=(StrategyReadinessBlocker.DIRECTION_BLOCKED,),
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(neutral_fresh_snapshot())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                StrategyReadinessBlocker.DIRECTION_BLOCKED,
                StrategyReadinessBlocker.DIRECTION_BLOCKED,
            ),
        )


def test_manual_decision_rejects_foreign_freshness() -> None:
    ready = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())
    foreign_context = bullish_snapshot(stale_h4=True)
    foreign_freshness = MultiTimeframeFreshnessGate().evaluate(foreign_context)

    with pytest.raises(
        ValueError,
        match="readiness context",
    ):
        replace(
            ready,
            freshness=foreign_freshness,
        )


def test_manual_decision_rejects_foreign_directional() -> None:
    ready = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())
    foreign_directional = MultiTimeframeDirectionalGate().evaluate(bearish_snapshot())

    with pytest.raises(
        ValueError,
        match="readiness context",
    ):
        replace(
            ready,
            directional=foreign_directional,
        )


def test_manual_decision_rejects_policy_mismatch() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())
    changed_policy = StrategyReadinessPolicy(
        directional_policy=(DirectionalPermissionPolicy(minimum_aligned_timeframes=4))
    )

    with pytest.raises(
        ValueError,
        match="policy",
    ):
        replace(
            decision,
            policy=changed_policy,
        )


def test_decision_is_immutable() -> None:
    decision = CompositeStrategyReadinessGate().evaluate(bullish_snapshot())

    with pytest.raises(FrozenInstanceError):
        decision.status = StrategyReadinessStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = StrategyReadinessPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.freshness_policy = ContextFreshnessPolicy()


def test_evaluation_is_deterministic() -> None:
    gate = CompositeStrategyReadinessGate()
    snapshot = bullish_snapshot()

    assert gate.evaluate(snapshot) == gate.evaluate(snapshot)


def test_function_api_delegates() -> None:
    decision = evaluate_strategy_readiness(bullish_snapshot())

    assert decision.is_ready is True


def test_gate_alias_methods_delegate() -> None:
    gate = CompositeStrategyReadinessGate()
    snapshot = bullish_snapshot()

    assert gate.check(snapshot) == gate.evaluate(snapshot)
    assert gate.decide(snapshot) == gate.evaluate(snapshot)


def test_public_aliases_are_preserved() -> None:
    assert ReadinessBlocker is StrategyReadinessBlocker
    assert ReadinessDecision is StrategyReadinessDecision
    assert ReadinessPolicy is StrategyReadinessPolicy
    assert ReadinessReason is StrategyReadinessReason
    assert ReadinessStatus is StrategyReadinessStatus
    assert ReadinessGate is CompositeStrategyReadinessGate
    assert StrategyAnalysisReadinessGate is CompositeStrategyReadinessGate
