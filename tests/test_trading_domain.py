from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.domain.trading import EntryType, TradePlan, TradeSide


def create_buy_plan(**overrides: object) -> TradePlan:
    values: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": TradeSide.BUY,
        "entry_type": EntryType.MARKET,
        "entry_price": "2400.00",
        "stop_loss": "2390.00",
        "take_profit": "2420.00",
        "risk_percent": "0.25",
        "strategy_id": "smc_market_structure",
        "setup_id": "setup-001",
    }
    values.update(overrides)

    return TradePlan(**values)


def create_sell_plan(**overrides: object) -> TradePlan:
    values: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": TradeSide.SELL,
        "entry_type": EntryType.LIMIT,
        "entry_price": "2400.00",
        "stop_loss": "2410.00",
        "take_profit": "2380.00",
        "risk_percent": "0.25",
        "strategy_id": "smc_market_structure",
        "setup_id": "setup-002",
        "oco_group_id": "oco-001",
    }
    values.update(overrides)

    return TradePlan(**values)


def test_valid_buy_plan_is_normalized() -> None:
    plan = create_buy_plan(
        symbol=" xauusd ",
        strategy_id=" strategy-a ",
        setup_id=" setup-a ",
    )

    assert plan.symbol == "XAUUSD"
    assert plan.side == TradeSide.BUY
    assert plan.entry_price == Decimal("2400.00")
    assert plan.risk_percent == Decimal("0.25")
    assert plan.strategy_id == "strategy-a"
    assert plan.setup_id == "setup-a"


def test_valid_sell_plan_supports_oco_group() -> None:
    plan = create_sell_plan()

    assert plan.side == TradeSide.SELL
    assert plan.entry_type == EntryType.LIMIT
    assert plan.has_oco_group is True
    assert plan.oco_group_id == "oco-001"


def test_risk_reward_ratio_is_calculated_exactly() -> None:
    plan = create_buy_plan()

    assert plan.stop_distance == Decimal("10.00")
    assert plan.reward_distance == Decimal("20.00")
    assert plan.risk_reward_ratio == Decimal("2")


@pytest.mark.parametrize(
    "entry_type",
    [
        EntryType.LIMIT,
        EntryType.STOP,
    ],
)
def test_limit_and_stop_entries_are_pending(
    entry_type: EntryType,
) -> None:
    plan = create_buy_plan(entry_type=entry_type)

    assert plan.is_pending_order is True


def test_market_entry_is_not_pending() -> None:
    plan = create_buy_plan(entry_type=EntryType.MARKET)

    assert plan.is_pending_order is False


@pytest.mark.parametrize(
    "symbol",
    [
        "EURUSD",
        "BTCUSD",
        "GOLD",
        "",
    ],
)
def test_noncanonical_symbol_is_rejected(symbol: str) -> None:
    with pytest.raises(ValueError, match="Only canonical symbol"):
        create_buy_plan(symbol=symbol)


@pytest.mark.parametrize(
    ("stop_loss", "take_profit", "message"),
    [
        ("2400.00", "2420.00", "stop_loss must be below"),
        ("2410.00", "2420.00", "stop_loss must be below"),
        ("2390.00", "2400.00", "take_profit must be above"),
        ("2390.00", "2395.00", "take_profit must be above"),
    ],
)
def test_invalid_buy_price_geometry_is_rejected(
    stop_loss: str,
    take_profit: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        create_buy_plan(
            stop_loss=stop_loss,
            take_profit=take_profit,
        )


@pytest.mark.parametrize(
    ("stop_loss", "take_profit", "message"),
    [
        ("2400.00", "2380.00", "stop_loss must be above"),
        ("2390.00", "2380.00", "stop_loss must be above"),
        ("2410.00", "2400.00", "take_profit must be below"),
        ("2410.00", "2420.00", "take_profit must be below"),
    ],
)
def test_invalid_sell_price_geometry_is_rejected(
    stop_loss: str,
    take_profit: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        create_sell_plan(
            stop_loss=stop_loss,
            take_profit=take_profit,
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        "1.01",
        "2",
        "100",
    ],
)
def test_risk_above_one_percent_is_rejected(
    risk_percent: str,
) -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        create_buy_plan(risk_percent=risk_percent)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("entry_price", "0"),
        ("stop_loss", "-1"),
        ("take_profit", "NaN"),
        ("risk_percent", "0"),
    ],
)
def test_invalid_decimal_values_are_rejected(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValueError):
        create_buy_plan(**{field_name: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"strategy_id": ""},
        {"setup_id": "   "},
        {"oco_group_id": "\n"},
    ],
)
def test_blank_identifiers_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        create_buy_plan(**overrides)


def test_trade_plan_is_immutable() -> None:
    plan = create_buy_plan()

    with pytest.raises(FrozenInstanceError):
        plan.entry_price = Decimal("2500.00")
