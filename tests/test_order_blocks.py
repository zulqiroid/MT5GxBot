from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.displacement import (
    DisplacementDirection,
    DisplacementImpulse,
    DisplacementPolicy,
    DisplacementSet,
)
from app.strategy.order_blocks import (
    OB,
    OBDetector,
    OBDirection,
    OBPolicy,
    OBSet,
    OrderBlock,
    OrderBlockCollection,
    OrderBlockDetectionError,
    OrderBlockDetectionErrorReason,
    OrderBlockDetector,
    OrderBlockDirection,
    OrderBlockFinder,
    OrderBlockMode,
    OrderBlockPolicy,
    OrderBlockSet,
    OrderBlockZoneMode,
    detect_order_blocks,
)

START = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    rows: list[tuple[str, str, str, str]],
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []

    for index, (open_, high, low, close) in enumerate(rows):
        open_time = START + duration * index

        candles.append(
            ClosedCandle(
                broker_symbol=broker_symbol,
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=open_,
                high=high,
                low=low,
                close=close,
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


def create_displacement_set(
    rows: list[tuple[str, str, str, str]],
    specifications: list[tuple[int, DisplacementDirection]],
    *,
    displacement_policy: (DisplacementPolicy | None) = None,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> DisplacementSet:
    policy = displacement_policy or DisplacementPolicy(lookback_candles=2)
    series = create_series(
        rows,
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )
    impulses: list[DisplacementImpulse] = []

    for index, direction in specifications:
        prior_candles = series.candles[index - policy.lookback_candles : index]
        baseline = sum(
            (candle.high - candle.low for candle in prior_candles),
            start=Decimal("0"),
        ) / Decimal(policy.lookback_candles)

        impulses.append(
            DisplacementImpulse(
                index=index,
                direction=direction,
                candle=series.candles[index],
                baseline_average_range=baseline,
            )
        )

    return DisplacementSet(
        source=series,
        policy=policy,
        impulses=tuple(impulses),
    )


def bullish_displacements(
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> DisplacementSet:
    return create_displacement_set(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "110", "99", "109"),
        ],
        [(2, DisplacementDirection.BULLISH)],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )


def bearish_displacements() -> DisplacementSet:
    return create_displacement_set(
        [
            ("100", "102", "98", "99"),
            ("99", "103", "98", "102"),
            ("102", "103", "91", "92"),
        ],
        [(2, DisplacementDirection.BEARISH)],
    )


def reusable_source_displacements() -> DisplacementSet:
    policy = DisplacementPolicy(lookback_candles=1)

    return create_displacement_set(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "110", "100", "109"),
            ("109", "111", "107", "110"),
            ("110", "122", "109", "121"),
        ],
        [
            (2, DisplacementDirection.BULLISH),
            (4, DisplacementDirection.BULLISH),
        ],
        displacement_policy=policy,
    )


def multiple_direction_displacements() -> DisplacementSet:
    policy = DisplacementPolicy(lookback_candles=1)

    return create_displacement_set(
        [
            ("101", "102", "98", "99"),
            ("99", "108", "99", "107"),
            ("104", "106", "102", "105"),
            ("105", "106", "96", "97"),
        ],
        [
            (1, DisplacementDirection.BULLISH),
            (3, DisplacementDirection.BEARISH),
        ],
        displacement_policy=policy,
    )


def detected_bullish_block() -> OrderBlock:
    return OrderBlockDetector().detect(bullish_displacements()).blocks[0]


def test_default_policy_is_conservative() -> None:
    policy = OrderBlockPolicy()

    assert policy.search_back_candles == 3
    assert policy.zone_mode == (OrderBlockZoneMode.FULL_RANGE)
    assert policy.minimum_zone_size == Decimal("0")
    assert policy.allow_source_reuse is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"search_back_candles": 0},
        {"search_back_candles": True},
        {"search_back_candles": 101},
        {"zone_mode": "INVALID"},
        {"minimum_zone_size": "-0.01"},
        {"minimum_zone_size": "NaN"},
        {"minimum_zone_size": True},
        {"allow_source_reuse": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        OrderBlockPolicy(**overrides)


def test_bullish_order_block_is_detected() -> None:
    result = OrderBlockDetector().detect(bullish_displacements())

    assert result.count == 1
    assert len(result.bullish) == 1
    assert result.bearish == ()

    block = result.blocks[0]

    assert block.direction == (OrderBlockDirection.BULLISH)
    assert block.source_index == 1
    assert block.confirmation_index == 2
    assert block.is_bullish is True
    assert block.is_bearish is False


def test_bearish_order_block_is_detected() -> None:
    result = OrderBlockDetector().detect(bearish_displacements())

    assert result.count == 1
    assert result.bullish == ()
    assert len(result.bearish) == 1

    block = result.blocks[0]

    assert block.direction == (OrderBlockDirection.BEARISH)
    assert block.source_index == 1


def test_nearest_opposite_candle_is_selected() -> None:
    displacements = create_displacement_set(
        [
            ("101", "103", "99", "100"),
            ("100", "102", "98", "99"),
            ("99", "101", "97", "98"),
            ("98", "110", "97", "109"),
        ],
        [(3, DisplacementDirection.BULLISH)],
    )

    block = OrderBlockDetector().detect(displacements).blocks[0]

    assert block.source_index == 2


def test_same_direction_candles_are_skipped() -> None:
    displacements = create_displacement_set(
        [
            ("100", "102", "98", "99"),
            ("99", "103", "98", "102"),
            ("102", "105", "101", "104"),
            ("104", "115", "103", "114"),
        ],
        [(3, DisplacementDirection.BULLISH)],
    )

    block = OrderBlockDetector().detect(displacements).blocks[0]

    assert block.source_index == 0


def test_no_opposite_candle_returns_no_block() -> None:
    displacements = create_displacement_set(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "102"),
            ("102", "104", "100", "103"),
            ("103", "114", "102", "113"),
        ],
        [(3, DisplacementDirection.BULLISH)],
    )

    result = OrderBlockDetector().detect(displacements)

    assert result.blocks == ()


def test_source_outside_search_window_is_ignored() -> None:
    displacements = create_displacement_set(
        [
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
            ("101", "103", "99", "102"),
            ("102", "104", "100", "103"),
            ("103", "114", "102", "113"),
        ],
        [(4, DisplacementDirection.BULLISH)],
    )
    policy = OrderBlockPolicy(search_back_candles=2)

    result = OrderBlockDetector(policy).detect(displacements)

    assert result.blocks == ()


def test_doji_is_not_an_order_block_source() -> None:
    displacements = create_displacement_set(
        [
            ("101", "103", "99", "100"),
            ("100", "102", "98", "100"),
            ("100", "110", "99", "109"),
        ],
        [(2, DisplacementDirection.BULLISH)],
    )

    block = OrderBlockDetector().detect(displacements).blocks[0]

    assert block.source_index == 0


def test_full_range_zone_uses_wicks() -> None:
    block = detected_bullish_block()

    assert block.zone_mode == (OrderBlockZoneMode.FULL_RANGE)
    assert block.lower_bound == Decimal("99")
    assert block.upper_bound == Decimal("103")
    assert block.size == Decimal("4")
    assert block.midpoint == Decimal("101")


def test_body_zone_uses_open_and_close() -> None:
    policy = OrderBlockPolicy(zone_mode=OrderBlockZoneMode.BODY)

    block = OrderBlockDetector(policy).detect(bullish_displacements()).blocks[0]

    assert block.lower_bound == Decimal("100")
    assert block.upper_bound == Decimal("101")
    assert block.size == Decimal("1")
    assert block.midpoint == Decimal("100.5")


def test_exact_minimum_zone_size_is_rejected() -> None:
    policy = OrderBlockPolicy(minimum_zone_size="4")

    result = OrderBlockDetector(policy).detect(bullish_displacements())

    assert result.blocks == ()


def test_zone_above_minimum_size_is_detected() -> None:
    policy = OrderBlockPolicy(minimum_zone_size="3.99")

    result = OrderBlockDetector(policy).detect(bullish_displacements())

    assert result.count == 1


def test_source_reuse_is_disabled_by_default() -> None:
    result = OrderBlockDetector().detect(reusable_source_displacements())

    assert result.count == 1
    assert result.blocks[0].confirmation_index == 2


def test_source_reuse_can_be_enabled() -> None:
    policy = OrderBlockPolicy(allow_source_reuse=True)

    result = OrderBlockDetector(policy).detect(reusable_source_displacements())

    assert result.count == 2
    assert {block.source_index for block in result.blocks} == {1}


def test_multiple_blocks_are_ordered() -> None:
    result = OrderBlockDetector().detect(multiple_direction_displacements())

    assert result.count == 2
    assert [block.confirmation_index for block in result.blocks] == [1, 3]
    assert result.latest is result.blocks[-1]
    assert result.latest_bullish is result.bullish[-1]
    assert result.latest_bearish is result.bearish[-1]


def test_direction_and_confirmation_filters() -> None:
    result = OrderBlockDetector().detect(multiple_direction_displacements())

    assert result.by_direction(OrderBlockDirection.BULLISH) == result.bullish
    assert result.by_direction(OrderBlockDirection.BEARISH) == result.bearish
    assert result.confirmed_at_index(1) == (result.blocks[0],)
    assert result.confirmed_at_index(2) == ()


def test_invalid_direction_filter_is_rejected() -> None:
    result = OrderBlockDetector().detect(bullish_displacements())

    with pytest.raises(ValueError):
        result.by_direction("INVALID")


def test_nearest_bullish_below_is_selected() -> None:
    result = OrderBlockDetector().detect(multiple_direction_displacements())

    nearest = result.nearest_bullish_below("110")

    assert nearest is result.bullish[0]


def test_nearest_bearish_above_is_selected() -> None:
    result = OrderBlockDetector().detect(multiple_direction_displacements())

    nearest = result.nearest_bearish_above("95")

    assert nearest is result.bearish[0]


def test_nearest_lookup_returns_none_without_candidate() -> None:
    result = OrderBlockDetector().detect(multiple_direction_displacements())

    assert result.nearest_bullish_below("90") is None
    assert result.nearest_bearish_above("120") is None


def test_block_contains_price_and_distance() -> None:
    block = detected_bullish_block()

    assert block.contains_price("99") is True
    assert block.contains_price("101") is True
    assert block.contains_price("103") is True
    assert block.contains_price("104") is False
    assert block.distance_from("98") == Decimal("1")
    assert block.distance_from("101") == Decimal("0")
    assert block.distance_from("105") == Decimal("2")


def test_block_exposes_confirmation_context() -> None:
    block = detected_bullish_block()

    assert block.source_distance == 1
    assert block.confirmed_at == (block.displacement.confirmed_at)
    assert block.stable_id == ("XAUUSDm:M5:BULLISH:1:2:FULL_RANGE")


def test_result_preserves_market_context() -> None:
    result = OrderBlockDetector().detect(
        bullish_displacements(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1
    assert result.source is result.displacements.source


def test_empty_displacement_set_returns_empty_result() -> None:
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
        ]
    )
    displacements = DisplacementSet(
        source=series,
        policy=DisplacementPolicy(lookback_candles=2),
        impulses=(),
    )

    result = OrderBlockDetector().detect(displacements)

    assert result.count == 0
    assert result.blocks == ()
    assert result.latest is None
    assert result.latest_bullish is None
    assert result.latest_bearish is None


def test_invalid_displacement_set_type_is_fail_safe() -> None:
    with pytest.raises(
        OrderBlockDetectionError,
        match="INVALID_DISPLACEMENT_SET",
    ) as captured:
        OrderBlockDetector().detect("invalid")

    assert captured.value.reason == (OrderBlockDetectionErrorReason.INVALID_DISPLACEMENT_SET)


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="OrderBlockPolicy",
    ):
        OrderBlockDetector(policy="invalid")


def test_manual_block_rejects_wrong_direction() -> None:
    displacements = bullish_displacements()
    displacement = displacements.impulses[0]

    with pytest.raises(
        ValueError,
        match="displacement direction",
    ):
        OrderBlock(
            source_index=1,
            direction=OrderBlockDirection.BEARISH,
            zone_mode=OrderBlockZoneMode.FULL_RANGE,
            source_candle=(displacements.source.candles[1]),
            displacement=displacement,
        )


def test_manual_block_rejects_same_direction_source() -> None:
    displacements = bullish_displacements()
    displacement = displacements.impulses[0]

    with pytest.raises(
        ValueError,
        match="must oppose",
    ):
        OrderBlock(
            source_index=0,
            direction=OrderBlockDirection.BULLISH,
            zone_mode=OrderBlockZoneMode.FULL_RANGE,
            source_candle=(displacements.source.candles[0]),
            displacement=displacement,
        )


def test_manual_block_rejects_symbol_mismatch() -> None:
    displacements = bullish_displacements()
    other = bullish_displacements(broker_symbol="XAUUSD")

    with pytest.raises(
        ValueError,
        match="same broker symbol",
    ):
        OrderBlock(
            source_index=1,
            direction=OrderBlockDirection.BULLISH,
            zone_mode=OrderBlockZoneMode.FULL_RANGE,
            source_candle=other.source.candles[1],
            displacement=displacements.impulses[0],
        )


def test_manual_set_rejects_wrong_source_history() -> None:
    displacements = bullish_displacements()
    other = create_series(
        [
            ("100", "102", "98", "101"),
            ("102", "104", "99", "100"),
            ("100", "110", "99", "109"),
        ]
    )
    block = OrderBlock(
        source_index=1,
        direction=OrderBlockDirection.BULLISH,
        zone_mode=OrderBlockZoneMode.FULL_RANGE,
        source_candle=other.candles[1],
        displacement=displacements.impulses[0],
    )

    with pytest.raises(
        ValueError,
        match="source history",
    ):
        OrderBlockSet(
            displacements=displacements,
            policy=OrderBlockPolicy(),
            blocks=(block,),
        )


def test_manual_set_rejects_non_nearest_source() -> None:
    displacements = create_displacement_set(
        [
            ("101", "103", "99", "100"),
            ("100", "102", "98", "99"),
            ("99", "110", "97", "109"),
        ],
        [(2, DisplacementDirection.BULLISH)],
    )
    block = OrderBlock(
        source_index=0,
        direction=OrderBlockDirection.BULLISH,
        zone_mode=OrderBlockZoneMode.FULL_RANGE,
        source_candle=displacements.source.candles[0],
        displacement=displacements.impulses[0],
    )

    with pytest.raises(
        ValueError,
        match="nearest",
    ):
        OrderBlockSet(
            displacements=displacements,
            policy=OrderBlockPolicy(),
            blocks=(block,),
        )


def test_manual_set_rejects_source_outside_window() -> None:
    displacements = create_displacement_set(
        [
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
            ("101", "103", "99", "102"),
            ("102", "112", "101", "111"),
        ],
        [(3, DisplacementDirection.BULLISH)],
    )
    block = OrderBlock(
        source_index=0,
        direction=OrderBlockDirection.BULLISH,
        zone_mode=OrderBlockZoneMode.FULL_RANGE,
        source_candle=displacements.source.candles[0],
        displacement=displacements.impulses[0],
    )

    with pytest.raises(
        ValueError,
        match="search window",
    ):
        OrderBlockSet(
            displacements=displacements,
            policy=OrderBlockPolicy(search_back_candles=2),
            blocks=(block,),
        )


def test_manual_set_rejects_duplicate_blocks() -> None:
    result = OrderBlockDetector().detect(bullish_displacements())
    block = result.blocks[0]

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        OrderBlockSet(
            displacements=result.displacements,
            policy=result.policy,
            blocks=(block, block),
        )


def test_manual_set_rejects_source_reuse() -> None:
    displacements = reusable_source_displacements()
    policy = OrderBlockPolicy(allow_source_reuse=True)
    detected = OrderBlockDetector(policy).detect(displacements)

    with pytest.raises(
        ValueError,
        match="reuse is disabled",
    ):
        OrderBlockSet(
            displacements=displacements,
            policy=OrderBlockPolicy(),
            blocks=detected.blocks,
        )


def test_block_is_immutable() -> None:
    block = detected_bullish_block()

    with pytest.raises(FrozenInstanceError):
        block.source_index = 0


def test_set_is_immutable() -> None:
    result = OrderBlockDetector().detect(bullish_displacements())

    with pytest.raises(FrozenInstanceError):
        result.blocks = ()


def test_function_api_delegates() -> None:
    result = detect_order_blocks(bullish_displacements())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = OrderBlockDetector()
    displacements = bullish_displacements()

    assert detector.evaluate(displacements) == detector.detect(displacements)
    assert detector.find(displacements) == detector.detect(displacements)


def test_public_aliases_are_preserved() -> None:
    assert OB is OrderBlock
    assert OBDirection is OrderBlockDirection
    assert OBDetector is OrderBlockDetector
    assert OBPolicy is OrderBlockPolicy
    assert OBSet is OrderBlockSet
    assert OrderBlockCollection is OrderBlockSet
    assert OrderBlockFinder is OrderBlockDetector
    assert OrderBlockMode is OrderBlockZoneMode
