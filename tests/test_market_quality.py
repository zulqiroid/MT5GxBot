from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    CandleWindow,
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.closed_candle_service import (
    CandleDataSnapshot,
    CandleLoadRequest,
)
from app.market.market_quality import (
    MarketDataQualityIssue,
    MarketDataQualityPolicy,
    MarketDataQualityValidator,
    StrategyMarketQualityValidator,
    expected_latest_close_time,
)
from app.market.multi_timeframe_service import (
    MultiTimeframeLoadRequest,
    MultiTimeframeMarketSnapshot,
    TimeframeMarketSlice,
)
from app.market.timeframes import (
    SUPPORTED_STRATEGY_TIMEFRAMES,
    get_timeframe_spec,
)

NOW = datetime(
    2026,
    7,
    25,
    12,
    37,
    tzinfo=timezone.utc,
)


LATEST_OPEN_TIMES = {
    TimeframeName.H4: datetime(
        2026,
        7,
        25,
        8,
        0,
        tzinfo=timezone.utc,
    ),
    TimeframeName.H1: datetime(
        2026,
        7,
        25,
        11,
        0,
        tzinfo=timezone.utc,
    ),
    TimeframeName.M15: datetime(
        2026,
        7,
        25,
        12,
        15,
        tzinfo=timezone.utc,
    ),
    TimeframeName.M5: datetime(
        2026,
        7,
        25,
        12,
        30,
        tzinfo=timezone.utc,
    ),
}


def create_candle(
    *,
    timeframe: TimeframeName,
    open_time: datetime,
    close: str = "2400.00",
) -> ClosedCandle:
    close_price = Decimal(close)

    return ClosedCandle(
        broker_symbol="XAUUSDm",
        timeframe=timeframe,
        open_time=open_time,
        observed_at=NOW,
        open=close_price,
        high=close_price + Decimal("5"),
        low=close_price - Decimal("5"),
        close=close_price,
        tick_volume=1000,
        spread=20,
        real_volume=0,
    )


def create_slice(
    timeframe: TimeframeName,
    *,
    count: int = 3,
    latest_open_time: datetime | None = None,
    close: str = "2400.00",
    create_gap: bool = False,
) -> TimeframeMarketSlice:
    latest_open = latest_open_time or LATEST_OPEN_TIMES[timeframe]
    duration = get_timeframe_spec(timeframe).duration

    open_times = [latest_open - duration * index for index in reversed(range(count))]

    if create_gap and count >= 2:
        open_times[0] = open_times[0] - duration

    candles = tuple(
        create_candle(
            timeframe=timeframe,
            open_time=open_time,
            close=close,
        )
        for open_time in open_times
    )

    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=timeframe,
        candles=candles,
    )

    request = CandleLoadRequest(
        broker_symbol="XAUUSDm",
        timeframe=timeframe,
        closed_count=count,
        include_forming=False,
        require_contiguous=False,
    )

    data = CandleDataSnapshot(
        request=request,
        window=CandleWindow(closed=series),
        loaded_at=NOW,
    )

    return TimeframeMarketSlice(
        timeframe=timeframe,
        data=data,
    )


def create_snapshot(
    *,
    counts: dict[TimeframeName, int] | None = None,
    latest_open_times: (dict[TimeframeName, datetime] | None) = None,
    close_prices: dict[TimeframeName, str] | None = None,
    gap_timeframe: TimeframeName | None = None,
) -> MultiTimeframeMarketSnapshot:
    selected_counts = counts or {timeframe: 3 for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES}
    selected_open_times = latest_open_times or LATEST_OPEN_TIMES
    selected_close_prices = close_prices or {
        timeframe: "2400.00" for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES
    }

    request = MultiTimeframeLoadRequest(
        broker_symbol="XAUUSDm",
        h4_count=selected_counts[TimeframeName.H4],
        h1_count=selected_counts[TimeframeName.H1],
        m15_count=selected_counts[TimeframeName.M15],
        m5_count=selected_counts[TimeframeName.M5],
        require_contiguous=False,
        max_staleness_bars=10,
        reject_stale=False,
    )

    slices = tuple(
        create_slice(
            timeframe,
            count=selected_counts[timeframe],
            latest_open_time=selected_open_times[timeframe],
            close=selected_close_prices[timeframe],
            create_gap=(gap_timeframe == timeframe),
        )
        for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES
    )

    return MultiTimeframeMarketSnapshot(
        request=request,
        evaluated_at=NOW,
        slices=slices,
    )


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        (
            TimeframeName.H4,
            datetime(
                2026,
                7,
                25,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        (
            TimeframeName.H1,
            datetime(
                2026,
                7,
                25,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        (
            TimeframeName.M15,
            datetime(
                2026,
                7,
                25,
                12,
                30,
                tzinfo=timezone.utc,
            ),
        ),
        (
            TimeframeName.M5,
            datetime(
                2026,
                7,
                25,
                12,
                35,
                tzinfo=timezone.utc,
            ),
        ),
    ],
)
def test_expected_latest_close_time(
    timeframe: TimeframeName,
    expected: datetime,
) -> None:
    assert (
        expected_latest_close_time(
            NOW,
            timeframe,
        )
        == expected
    )


def test_expected_close_normalizes_timezone() -> None:
    local_time = datetime(
        2026,
        7,
        25,
        17,
        37,
        tzinfo=timezone(timedelta(hours=5)),
    )

    assert expected_latest_close_time(
        local_time,
        TimeframeName.M5,
    ) == datetime(
        2026,
        7,
        25,
        12,
        35,
        tzinfo=timezone.utc,
    )


def test_naive_expected_close_time_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        expected_latest_close_time(
            datetime(2026, 7, 25, 12, 37),
            TimeframeName.M5,
        )


def test_default_policy_is_conservative() -> None:
    policy = MarketDataQualityPolicy()

    assert policy.minimum_h4_candles == 2
    assert policy.minimum_h1_candles == 2
    assert policy.minimum_m15_candles == 2
    assert policy.minimum_m5_candles == 2
    assert policy.max_staleness_bars == 1
    assert policy.alignment_grace_seconds == 0
    assert policy.max_close_divergence_percent == Decimal("5.00")
    assert policy.require_contiguous is True
    assert policy.require_boundary_alignment is True


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        (TimeframeName.H4, 10),
        (TimeframeName.H1, 20),
        (TimeframeName.M15, 30),
        (TimeframeName.M5, 40),
    ],
)
def test_policy_returns_minimum_count(
    timeframe: TimeframeName,
    expected: int,
) -> None:
    policy = MarketDataQualityPolicy(
        minimum_h4_candles=10,
        minimum_h1_candles=20,
        minimum_m15_candles=30,
        minimum_m5_candles=40,
    )

    assert policy.minimum_count_for(timeframe) == expected


def test_non_strategy_policy_count_is_blocked() -> None:
    policy = MarketDataQualityPolicy()

    with pytest.raises(
        ValueError,
        match="not a primary",
    ):
        policy.minimum_count_for(TimeframeName.M1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_h4_candles": 0},
        {"minimum_h1_candles": True},
        {"minimum_m15_candles": 10_001},
        {"minimum_m5_candles": -1},
        {"max_staleness_bars": 0},
        {"alignment_grace_seconds": -1},
        {"max_close_divergence_percent": "0"},
        {"require_contiguous": 1},
        {"require_boundary_alignment": 0},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        MarketDataQualityPolicy(**overrides)


def test_healthy_snapshot_passes_quality_gate() -> None:
    validator = MarketDataQualityValidator()
    snapshot = create_snapshot()

    decision = validator.evaluate(snapshot)

    assert decision.valid is True
    assert decision.strategy_ready is True
    assert decision.issues == ()
    assert decision.diagnostics == ()


def test_history_below_minimum_is_blocked() -> None:
    snapshot = create_snapshot()
    policy = MarketDataQualityPolicy(
        minimum_h4_candles=4,
    )
    validator = MarketDataQualityValidator(policy)

    decision = validator.evaluate(snapshot)

    assert decision.valid is False
    assert MarketDataQualityIssue.HISTORY_TOO_SHORT in decision.issues
    assert len(decision.diagnostics_for(TimeframeName.H4)) == 1


def test_history_gap_is_blocked() -> None:
    snapshot = create_snapshot(gap_timeframe=TimeframeName.M15)

    decision = MarketDataQualityValidator().evaluate(snapshot)

    assert MarketDataQualityIssue.HISTORY_GAP in decision.issues
    assert (
        decision.diagnostics_for(TimeframeName.M15)[0].issue == MarketDataQualityIssue.HISTORY_GAP
    )


def test_gap_can_be_allowed_by_policy() -> None:
    snapshot = create_snapshot(gap_timeframe=TimeframeName.M15)
    policy = MarketDataQualityPolicy(
        require_contiguous=False,
    )

    decision = MarketDataQualityValidator(policy).evaluate(snapshot)

    assert MarketDataQualityIssue.HISTORY_GAP not in decision.issues


def test_stale_timeframe_is_blocked() -> None:
    open_times = dict(LATEST_OPEN_TIMES)
    open_times[TimeframeName.M5] = datetime(
        2026,
        7,
        25,
        12,
        0,
        tzinfo=timezone.utc,
    )

    snapshot = create_snapshot(latest_open_times=open_times)

    decision = MarketDataQualityValidator().evaluate(snapshot)

    assert MarketDataQualityIssue.STALE_TIMEFRAME in decision.issues


def test_larger_staleness_window_can_allow_data() -> None:
    open_times = dict(LATEST_OPEN_TIMES)
    open_times[TimeframeName.M5] = datetime(
        2026,
        7,
        25,
        12,
        25,
        tzinfo=timezone.utc,
    )

    snapshot = create_snapshot(latest_open_times=open_times)
    policy = MarketDataQualityPolicy(
        max_staleness_bars=3,
        require_boundary_alignment=False,
    )

    decision = MarketDataQualityValidator(policy).evaluate(snapshot)

    assert MarketDataQualityIssue.STALE_TIMEFRAME not in decision.issues


def test_misaligned_latest_boundary_is_blocked() -> None:
    open_times = dict(LATEST_OPEN_TIMES)
    open_times[TimeframeName.M5] = datetime(
        2026,
        7,
        25,
        12,
        25,
        tzinfo=timezone.utc,
    )

    snapshot = create_snapshot(latest_open_times=open_times)
    policy = MarketDataQualityPolicy(
        max_staleness_bars=3,
    )

    decision = MarketDataQualityValidator(policy).evaluate(snapshot)

    assert MarketDataQualityIssue.LATEST_CLOSE_MISALIGNED in decision.issues


def test_alignment_check_can_be_disabled() -> None:
    open_times = dict(LATEST_OPEN_TIMES)
    open_times[TimeframeName.M5] = datetime(
        2026,
        7,
        25,
        12,
        25,
        tzinfo=timezone.utc,
    )

    snapshot = create_snapshot(latest_open_times=open_times)
    policy = MarketDataQualityPolicy(
        max_staleness_bars=3,
        require_boundary_alignment=False,
    )

    decision = MarketDataQualityValidator(policy).evaluate(snapshot)

    assert MarketDataQualityIssue.LATEST_CLOSE_MISALIGNED not in decision.issues


def test_alignment_grace_can_allow_small_difference() -> None:
    open_times = dict(LATEST_OPEN_TIMES)
    open_times[TimeframeName.M5] = datetime(
        2026,
        7,
        25,
        12,
        30,
        tzinfo=timezone.utc,
    )

    snapshot = create_snapshot(latest_open_times=open_times)
    policy = MarketDataQualityPolicy(
        max_staleness_bars=2,
        alignment_grace_seconds=300,
    )

    decision = MarketDataQualityValidator(policy).evaluate(snapshot)

    assert MarketDataQualityIssue.LATEST_CLOSE_MISALIGNED not in decision.issues


def test_cross_timeframe_price_divergence_is_blocked() -> None:
    prices = {
        TimeframeName.H4: "2600.00",
        TimeframeName.H1: "2400.00",
        TimeframeName.M15: "2400.00",
        TimeframeName.M5: "2400.00",
    }

    snapshot = create_snapshot(close_prices=prices)

    decision = MarketDataQualityValidator().evaluate(snapshot)

    assert MarketDataQualityIssue.CROSS_TIMEFRAME_PRICE_DIVERGENCE in decision.issues

    diagnostics = decision.diagnostics_for(TimeframeName.H4)

    assert diagnostics[0].issue == (MarketDataQualityIssue.CROSS_TIMEFRAME_PRICE_DIVERGENCE)


def test_price_at_exact_divergence_limit_is_allowed() -> None:
    prices = {
        TimeframeName.H4: "2520.00",
        TimeframeName.H1: "2400.00",
        TimeframeName.M15: "2400.00",
        TimeframeName.M5: "2400.00",
    }

    snapshot = create_snapshot(close_prices=prices)

    decision = MarketDataQualityValidator().evaluate(snapshot)

    assert MarketDataQualityIssue.CROSS_TIMEFRAME_PRICE_DIVERGENCE not in decision.issues


def test_multiple_diagnostics_share_unique_issue() -> None:
    prices = {
        TimeframeName.H4: "2600.00",
        TimeframeName.H1: "2600.00",
        TimeframeName.M15: "2400.00",
        TimeframeName.M5: "2400.00",
    }

    decision = MarketDataQualityValidator().evaluate(create_snapshot(close_prices=prices))

    assert decision.issues.count(MarketDataQualityIssue.CROSS_TIMEFRAME_PRICE_DIVERGENCE) == 1

    divergence_diagnostics = tuple(
        diagnostic
        for diagnostic in decision.diagnostics
        if diagnostic.issue == MarketDataQualityIssue.CROSS_TIMEFRAME_PRICE_DIVERGENCE
    )

    assert len(divergence_diagnostics) == 2


def test_require_valid_returns_valid_decision() -> None:
    decision = MarketDataQualityValidator().evaluate(create_snapshot())

    assert decision.require_valid() is decision


def test_require_valid_raises_with_reasons() -> None:
    decision = MarketDataQualityValidator(MarketDataQualityPolicy(minimum_h4_candles=10)).evaluate(
        create_snapshot()
    )

    with pytest.raises(
        ValueError,
        match="HISTORY_TOO_SHORT",
    ):
        decision.require_valid()


def test_validate_combines_evaluate_and_require() -> None:
    validator = MarketDataQualityValidator()

    decision = validator.validate(create_snapshot())

    assert decision.valid is True


def test_is_valid_returns_boolean() -> None:
    validator = MarketDataQualityValidator()

    assert validator.is_valid(create_snapshot()) is True


def test_decision_is_immutable() -> None:
    decision = MarketDataQualityValidator().evaluate(create_snapshot())

    with pytest.raises(FrozenInstanceError):
        decision.issues = (MarketDataQualityIssue.HISTORY_GAP,)


def test_strategy_validator_alias_is_preserved() -> None:
    assert StrategyMarketQualityValidator is MarketDataQualityValidator


def test_validator_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="MarketDataQualityPolicy",
    ):
        MarketDataQualityValidator(policy="invalid")


def test_evaluate_requires_snapshot_type() -> None:
    validator = MarketDataQualityValidator()

    with pytest.raises(
        ValueError,
        match="MultiTimeframeMarketSnapshot",
    ):
        validator.evaluate("invalid")
