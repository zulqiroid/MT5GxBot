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
from app.strategy.directional_permission import (
    DirectionalDecision,
    DirectionalDirection,
    DirectionalGate,
    DirectionalPermissionDecision,
    DirectionalPermissionDirection,
    DirectionalPermissionError,
    DirectionalPermissionErrorReason,
    DirectionalPermissionPolicy,
    DirectionalPermissionReason,
    DirectionalPermissionStatus,
    DirectionalPolicy,
    DirectionalReason,
    DirectionalStatus,
    MultiTimeframeBiasGate,
    MultiTimeframeDirectionalGate,
    evaluate_directional_permission,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
    MultiTimeframeContextSnapshot,
)

START = datetime(
    2026,
    7,
    20,
    0,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    broker_symbol: str = "XAUUSDm",
    count: int = 8,
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []

    for index in range(count):
        open_time = START + duration * index

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


@lru_cache(maxsize=1)
def neutral_snapshot() -> MultiTimeframeContextSnapshot:
    mapping = {timeframe: create_series(timeframe) for timeframe in GOLD_TIMEFRAME_HIERARCHY}

    return MultiTimeframeContextBuilder().build(mapping)


def with_biases(
    biases: dict[
        TimeframeName,
        MarketStructureBias,
    ],
) -> MultiTimeframeContextSnapshot:
    snapshot = neutral_snapshot()

    structure_biases = tuple(
        (
            timeframe,
            MarketStructureBias(
                biases.get(
                    timeframe,
                    MarketStructureBias.NEUTRAL,
                )
            ),
        )
        for timeframe in GOLD_TIMEFRAME_HIERARCHY
    )

    return replace(
        snapshot,
        structure_biases=structure_biases,
    )


def bullish_snapshot(
    *,
    execution_bias: MarketStructureBias = (MarketStructureBias.NEUTRAL),
) -> MultiTimeframeContextSnapshot:
    return with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
            TimeframeName.M5: execution_bias,
        }
    )


def bearish_snapshot(
    *,
    execution_bias: MarketStructureBias = (MarketStructureBias.NEUTRAL),
) -> MultiTimeframeContextSnapshot:
    return with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BEARISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
            TimeframeName.M5: execution_bias,
        }
    )


def test_default_policy_is_conservative() -> None:
    policy = DirectionalPermissionPolicy()

    assert policy.require_higher_timeframe_alignment is True
    assert policy.minimum_aligned_timeframes == 3
    assert policy.allow_neutral_setup_timeframe is True
    assert policy.allow_neutral_execution_timeframe is True
    assert policy.allow_opposing_setup_timeframe is False
    assert policy.allow_opposing_execution_timeframe is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"require_higher_timeframe_alignment": 1},
        {"minimum_aligned_timeframes": 0},
        {"minimum_aligned_timeframes": True},
        {"minimum_aligned_timeframes": 5},
        {"allow_neutral_setup_timeframe": 1},
        {"allow_neutral_execution_timeframe": 1},
        {"allow_opposing_setup_timeframe": 1},
        {"allow_opposing_execution_timeframe": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        DirectionalPermissionPolicy(**overrides)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="DirectionalPermissionPolicy",
    ):
        MultiTimeframeDirectionalGate(policy="invalid")


def test_invalid_context_is_fail_safe() -> None:
    with pytest.raises(
        DirectionalPermissionError,
        match="INVALID_CONTEXT",
    ) as captured:
        MultiTimeframeDirectionalGate().evaluate("invalid")

    assert captured.value.reason == (DirectionalPermissionErrorReason.INVALID_CONTEXT)


def test_neutral_higher_timeframes_are_unresolved() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(neutral_snapshot())

    assert decision.is_blocked is True
    assert decision.has_direction is False
    assert decision.direction == (DirectionalPermissionDirection.NONE)
    assert decision.reason == (DirectionalPermissionReason.HIGHER_TIMEFRAME_UNRESOLVED)


def test_higher_timeframe_conflict_is_blocked() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        }
    )

    decision = MultiTimeframeDirectionalGate().evaluate(snapshot)

    assert decision.is_blocked is True
    assert decision.direction == (DirectionalPermissionDirection.NONE)
    assert decision.reason == (DirectionalPermissionReason.HIGHER_TIMEFRAME_CONFLICT)


def test_bullish_direction_is_allowed() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.status == (DirectionalPermissionStatus.ALLOWED)
    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.reason == (DirectionalPermissionReason.ALIGNED)
    assert decision.is_bullish is True


def test_bearish_direction_is_allowed() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bearish_snapshot())

    assert decision.is_allowed is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.is_bearish is True


def test_full_bullish_alignment_is_allowed() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(
        bullish_snapshot(execution_bias=(MarketStructureBias.BULLISH))
    )

    assert decision.aligned_count == 4
    assert decision.alignment_score == Decimal("1")


def test_alignment_below_minimum_is_blocked() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
        }
    )

    decision = MultiTimeframeDirectionalGate().evaluate(snapshot)

    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.reason == (DirectionalPermissionReason.INSUFFICIENT_ALIGNMENT)
    assert decision.aligned_count == 2


def test_setup_timeframe_conflict_is_blocked() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
            TimeframeName.M5: (MarketStructureBias.BULLISH),
        }
    )

    decision = MultiTimeframeDirectionalGate().evaluate(snapshot)

    assert decision.reason == (DirectionalPermissionReason.SETUP_TIMEFRAME_CONFLICT)
    assert decision.direction == (DirectionalPermissionDirection.BULLISH)


def test_execution_timeframe_conflict_is_blocked() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(
        bullish_snapshot(execution_bias=(MarketStructureBias.BEARISH))
    )

    assert decision.reason == (DirectionalPermissionReason.EXECUTION_TIMEFRAME_CONFLICT)
    assert decision.opposing_timeframes == (TimeframeName.M5,)


def test_neutral_setup_is_allowed_by_default() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M5: (MarketStructureBias.BULLISH),
        }
    )

    decision = MultiTimeframeDirectionalGate().evaluate(snapshot)

    assert decision.is_allowed is True
    assert TimeframeName.M15 in (decision.neutral_timeframes)


def test_neutral_setup_can_be_blocked() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M5: (MarketStructureBias.BULLISH),
        }
    )
    policy = DirectionalPermissionPolicy(allow_neutral_setup_timeframe=False)

    decision = MultiTimeframeDirectionalGate(policy).evaluate(snapshot)

    assert decision.reason == (DirectionalPermissionReason.SETUP_TIMEFRAME_NEUTRAL)


def test_neutral_execution_is_allowed_by_default() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.is_allowed is True
    assert decision.execution_bias == (MarketStructureBias.NEUTRAL)


def test_neutral_execution_can_be_blocked() -> None:
    policy = DirectionalPermissionPolicy(allow_neutral_execution_timeframe=False)

    decision = MultiTimeframeDirectionalGate(policy).evaluate(bullish_snapshot())

    assert decision.reason == (DirectionalPermissionReason.EXECUTION_TIMEFRAME_NEUTRAL)


def test_opposing_setup_can_be_explicitly_allowed() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
            TimeframeName.M5: (MarketStructureBias.BULLISH),
        }
    )
    policy = DirectionalPermissionPolicy(allow_opposing_setup_timeframe=True)

    decision = MultiTimeframeDirectionalGate(policy).evaluate(snapshot)

    assert decision.is_allowed is True
    assert decision.opposing_timeframes == (TimeframeName.M15,)


def test_opposing_execution_can_be_explicitly_allowed() -> None:
    policy = DirectionalPermissionPolicy(allow_opposing_execution_timeframe=True)

    decision = MultiTimeframeDirectionalGate(policy).evaluate(
        bullish_snapshot(execution_bias=(MarketStructureBias.BEARISH))
    )

    assert decision.is_allowed is True


def test_majority_mode_can_resolve_without_htf_pair() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
            TimeframeName.M5: (MarketStructureBias.BULLISH),
        }
    )
    policy = DirectionalPermissionPolicy(require_higher_timeframe_alignment=False)

    decision = MultiTimeframeDirectionalGate(policy).evaluate(snapshot)

    assert decision.is_allowed is True
    assert decision.direction == (DirectionalPermissionDirection.BULLISH)


def test_majority_mode_tie_is_blocked() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
            TimeframeName.M5: (MarketStructureBias.BEARISH),
        }
    )
    policy = DirectionalPermissionPolicy(
        require_higher_timeframe_alignment=False,
        allow_opposing_setup_timeframe=True,
        allow_opposing_execution_timeframe=True,
    )

    decision = MultiTimeframeDirectionalGate(policy).evaluate(snapshot)

    assert decision.reason == (DirectionalPermissionReason.NO_DOMINANT_DIRECTION)
    assert decision.has_direction is False


def test_aligned_timeframe_order_is_deterministic() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.aligned_timeframes == (
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
    )
    assert decision.neutral_timeframes == (TimeframeName.M5,)


def test_alignment_score_is_exact() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.alignment_score == Decimal("0.75")
    assert decision.aligned_count == 3
    assert decision.opposing_count == 0
    assert decision.neutral_count == 1


def test_higher_timeframe_direction_is_available() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.higher_timeframe_direction == (DirectionalPermissionDirection.BULLISH)


def test_conflicted_higher_timeframe_direction_is_none() -> None:
    snapshot = with_biases(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
        }
    )

    decision = MultiTimeframeDirectionalGate().evaluate(snapshot)

    assert decision.higher_timeframe_direction == (DirectionalPermissionDirection.NONE)


def test_bias_lookup_is_available() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.bias_for(TimeframeName.H4) == MarketStructureBias.BULLISH
    assert decision.setup_bias == (MarketStructureBias.BULLISH)
    assert decision.execution_bias == (MarketStructureBias.NEUTRAL)


def test_invalid_bias_lookup_is_rejected() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    with pytest.raises(ValueError):
        decision.bias_for("M1")


def test_decision_preserves_context_metadata() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == (decision.context.observed_at)
    assert decision.stable_id == (
        f"{decision.context.stable_id}:DIRECTIONAL_PERMISSION:ALLOWED:BULLISH:ALIGNED"
    )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(DirectionalPermissionReason.INSUFFICIENT_ALIGNMENT),
        )


def test_manual_decision_rejects_wrong_direction() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            direction=(DirectionalPermissionDirection.BEARISH),
        )


def test_decision_is_immutable() -> None:
    decision = MultiTimeframeDirectionalGate().evaluate(bullish_snapshot())

    with pytest.raises(FrozenInstanceError):
        decision.status = DirectionalPermissionStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = DirectionalPermissionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_aligned_timeframes = 4


def test_evaluation_is_deterministic() -> None:
    gate = MultiTimeframeDirectionalGate()
    snapshot = bullish_snapshot()

    assert gate.evaluate(snapshot) == gate.evaluate(snapshot)


def test_function_api_delegates() -> None:
    decision = evaluate_directional_permission(bullish_snapshot())

    assert decision.is_allowed is True


def test_gate_alias_methods_delegate() -> None:
    gate = MultiTimeframeDirectionalGate()
    snapshot = bullish_snapshot()

    assert gate.decide(snapshot) == gate.evaluate(snapshot)
    assert gate.check(snapshot) == gate.evaluate(snapshot)


def test_public_aliases_are_preserved() -> None:
    assert DirectionalDecision is DirectionalPermissionDecision
    assert DirectionalDirection is DirectionalPermissionDirection
    assert DirectionalStatus is DirectionalPermissionStatus
    assert DirectionalReason is DirectionalPermissionReason
    assert DirectionalPolicy is DirectionalPermissionPolicy
    assert DirectionalGate is MultiTimeframeDirectionalGate
    assert MultiTimeframeBiasGate is MultiTimeframeDirectionalGate
