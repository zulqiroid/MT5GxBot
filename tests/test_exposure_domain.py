from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.exposure import (
    AccountSnapshot,
    GoldExposureSnapshot,
    PendingOrderSnapshot,
    PositionSnapshot,
)
from app.domain.trading import EntryType, TradeSide

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def create_account(**overrides: object) -> AccountSnapshot:
    values: dict[str, object] = {
        "login": 12345678,
        "server": "Broker-Demo",
        "currency": "usd",
        "balance": "10000.00",
        "equity": "9800.00",
        "margin": "1000.00",
        "free_margin": "8800.00",
        "observed_at": NOW,
    }
    values.update(overrides)

    return AccountSnapshot(**values)


def create_pending_order(
    **overrides: object,
) -> PendingOrderSnapshot:
    values: dict[str, object] = {
        "ticket": 1001,
        "symbol": "XAUUSD",
        "side": TradeSide.BUY,
        "entry_type": EntryType.STOP,
        "volume": "0.10",
        "entry_price": "2410.00",
        "stop_loss": "2400.00",
        "take_profit": "2430.00",
        "risk_percent": "0.25",
        "strategy_id": "liquidity-breakout",
        "setup_id": "setup-001",
        "magic_number": 26062801,
        "created_at": NOW,
        "oco_group_id": "oco-001",
    }
    values.update(overrides)

    return PendingOrderSnapshot(**values)


def create_position(
    **overrides: object,
) -> PositionSnapshot:
    values: dict[str, object] = {
        "ticket": 2001,
        "symbol": "XAUUSD",
        "side": TradeSide.BUY,
        "volume": "0.10",
        "entry_price": "2400.00",
        "current_price": "2405.00",
        "stop_loss": "2390.00",
        "take_profit": "2420.00",
        "initial_risk_percent": "0.50",
        "unrealized_pnl": "50.00",
        "strategy_id": "smc-continuation",
        "setup_id": "setup-002",
        "magic_number": 26062801,
        "opened_at": NOW,
        "observed_at": NOW + timedelta(minutes=15),
    }
    values.update(overrides)

    return PositionSnapshot(**values)


def test_account_snapshot_normalizes_values() -> None:
    account = create_account()

    assert account.currency == "USD"
    assert account.balance == Decimal("10000.00")
    assert account.equity == Decimal("9800.00")
    assert account.observed_at.tzinfo == timezone.utc


def test_account_metrics_are_calculated_exactly() -> None:
    account = create_account()

    assert account.margin_level_percent == Decimal("980")
    assert account.drawdown_percent == Decimal("2.00")


def test_zero_margin_has_no_margin_level() -> None:
    account = create_account(margin="0")

    assert account.margin_level_percent is None


def test_non_positive_balance_has_no_drawdown_percentage() -> None:
    account = create_account(balance="0")

    assert account.drawdown_percent is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("login", 0),
        ("server", ""),
        ("currency", " "),
        ("margin", "-1"),
        ("equity", "NaN"),
    ],
)
def test_invalid_account_values_are_rejected(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        create_account(**{field_name: value})


def test_naive_account_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        create_account(observed_at=datetime(2026, 7, 25, 12, 0))


def test_pending_order_is_normalized() -> None:
    order = create_pending_order(
        symbol=" xauusd ",
        volume="0.100",
    )

    assert order.symbol == "XAUUSD"
    assert order.volume == Decimal("0.100")
    assert order.risk_percent == Decimal("0.25")
    assert order.oco_group_id == "oco-001"


def test_pending_order_risk_reward_is_exact() -> None:
    order = create_pending_order()

    assert order.stop_distance == Decimal("10.00")
    assert order.reward_distance == Decimal("20.00")
    assert order.risk_reward_ratio == Decimal("2")


def test_market_order_cannot_be_pending() -> None:
    with pytest.raises(ValueError, match="LIMIT or STOP"):
        create_pending_order(entry_type=EntryType.MARKET)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("ticket", 0),
        ("volume", "0"),
        ("risk_percent", "1.01"),
        ("magic_number", 0),
        ("symbol", "EURUSD"),
    ],
)
def test_invalid_pending_order_values_are_rejected(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        create_pending_order(**{field_name: value})


def test_invalid_pending_order_geometry_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="stop_loss must be below",
    ):
        create_pending_order(stop_loss="2420.00")


def test_position_snapshot_calculates_price_move() -> None:
    position = create_position()

    assert position.price_move == Decimal("5.00")
    assert position.is_profitable is True


def test_sell_position_price_move_is_directional() -> None:
    position = create_position(
        side=TradeSide.SELL,
        entry_price="2400.00",
        current_price="2395.00",
        stop_loss="2410.00",
        take_profit="2380.00",
    )

    assert position.price_move == Decimal("5.00")


def test_negative_unrealized_pnl_is_allowed() -> None:
    position = create_position(unrealized_pnl="-25.00")

    assert position.unrealized_pnl == Decimal("-25.00")
    assert position.is_profitable is False


def test_position_observation_cannot_precede_open_time() -> None:
    with pytest.raises(ValueError, match="earlier"):
        create_position(observed_at=NOW - timedelta(minutes=1))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("ticket", -1),
        ("volume", "0"),
        ("current_price", "NaN"),
        ("initial_risk_percent", "1.50"),
        ("symbol", "GOLD"),
    ],
)
def test_invalid_position_values_are_rejected(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        create_position(**{field_name: value})


def test_empty_exposure_is_valid() -> None:
    exposure = GoldExposureSnapshot()

    assert exposure.has_active_exposure is False
    assert exposure.total_reserved_risk_percent == Decimal("0")
    assert exposure.open_position is None


def test_single_open_position_is_valid() -> None:
    position = create_position()
    exposure = GoldExposureSnapshot(
        positions=(position,),
    )

    assert exposure.has_open_position is True
    assert exposure.has_pending_orders is False
    assert exposure.open_position == position
    assert exposure.total_reserved_risk_percent == Decimal("0.50")


def test_staged_pending_orders_share_aggregate_risk() -> None:
    first = create_pending_order(
        ticket=1001,
        risk_percent="0.40",
    )
    second = create_pending_order(
        ticket=1002,
        side=TradeSide.SELL,
        entry_type=EntryType.STOP,
        entry_price="2390.00",
        stop_loss="2400.00",
        take_profit="2370.00",
        risk_percent="0.60",
    )

    exposure = GoldExposureSnapshot(
        pending_orders=(first, second),
    )

    assert exposure.has_pending_orders is True
    assert exposure.total_reserved_risk_percent == Decimal("1.00")


def test_more_than_one_open_position_is_blocked() -> None:
    first = create_position(ticket=2001)
    second = create_position(ticket=2002)

    with pytest.raises(ValueError, match="Maximum one"):
        GoldExposureSnapshot(
            positions=(first, second),
        )


def test_pending_entries_are_blocked_while_position_is_open() -> None:
    with pytest.raises(
        ValueError,
        match="not allowed while",
    ):
        GoldExposureSnapshot(
            positions=(create_position(),),
            pending_orders=(create_pending_order(),),
        )


def test_duplicate_broker_tickets_are_blocked() -> None:
    first = create_pending_order(ticket=1001)
    second = create_pending_order(
        ticket=1001,
        risk_percent="0.25",
    )

    with pytest.raises(ValueError, match="Duplicate"):
        GoldExposureSnapshot(
            pending_orders=(first, second),
        )


def test_aggregate_pending_risk_above_one_percent_is_blocked() -> None:
    first = create_pending_order(
        ticket=1001,
        risk_percent="0.60",
    )
    second = create_pending_order(
        ticket=1002,
        risk_percent="0.50",
    )

    with pytest.raises(ValueError, match="Aggregate"):
        GoldExposureSnapshot(
            pending_orders=(first, second),
        )
