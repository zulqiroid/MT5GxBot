from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.exposure import AccountSnapshot
from app.domain.sizing import (
    GoldSymbolSpecification,
    PositionSizeBlockReason,
    calculate_position_size,
)
from app.domain.trading import (
    EntryType,
    TradePlan,
    TradeSide,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def create_plan(**overrides: object) -> TradePlan:
    values: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": TradeSide.BUY,
        "entry_type": EntryType.MARKET,
        "entry_price": "2400.00",
        "stop_loss": "2390.00",
        "take_profit": "2420.00",
        "risk_percent": "0.25",
        "strategy_id": "smc-continuation",
        "setup_id": "setup-001",
    }
    values.update(overrides)

    return TradePlan(**values)


def create_account(**overrides: object) -> AccountSnapshot:
    values: dict[str, object] = {
        "login": 12345678,
        "server": "Broker-Demo",
        "currency": "USD",
        "balance": "10000.00",
        "equity": "10000.00",
        "margin": "0",
        "free_margin": "10000.00",
        "observed_at": NOW,
    }
    values.update(overrides)

    return AccountSnapshot(**values)


def create_specification(
    **overrides: object,
) -> GoldSymbolSpecification:
    values: dict[str, object] = {
        "symbol": "XAUUSD",
        "account_currency": "USD",
        "tick_size": "0.01",
        "tick_value_per_lot": "1.00",
        "volume_min": "0.01",
        "volume_max": "100.00",
        "volume_step": "0.01",
    }
    values.update(overrides)

    return GoldSymbolSpecification(**values)


def calculate(
    *,
    plan: TradePlan | None = None,
    account: AccountSnapshot | None = None,
    specification: GoldSymbolSpecification | None = None,
):
    return calculate_position_size(
        plan=plan or create_plan(),
        account=account or create_account(),
        specification=(specification or create_specification()),
    )


def test_standard_gold_position_size_is_exact() -> None:
    decision = calculate()

    assert decision.allowed is True

    sizing = decision.require_allowed()

    assert sizing.risk_capital == Decimal("10000.00")
    assert sizing.requested_risk_amount == Decimal("25.0000")
    assert sizing.stop_distance == Decimal("10.00")
    assert sizing.ticks_to_stop == Decimal("1000")
    assert sizing.risk_per_lot == Decimal("1000.00")
    assert sizing.raw_volume == Decimal("0.025")
    assert sizing.volume == Decimal("0.02")
    assert sizing.actual_risk_amount == Decimal("20.00")
    assert sizing.actual_risk_percent == Decimal("0.200")
    assert sizing.was_rounded_down is True
    assert sizing.was_capped_by_maximum is False


def test_lower_equity_is_used_as_risk_capital() -> None:
    decision = calculate(
        account=create_account(
            balance="10000",
            equity="8000",
        )
    )

    sizing = decision.require_allowed()

    assert sizing.risk_capital == Decimal("8000")
    assert sizing.requested_risk_amount == Decimal("20.00")
    assert sizing.volume == Decimal("0.02")


def test_lower_balance_is_used_as_risk_capital() -> None:
    decision = calculate(
        account=create_account(
            balance="8000",
            equity="10000",
        )
    )

    sizing = decision.require_allowed()

    assert sizing.risk_capital == Decimal("8000")


def test_stop_ticks_are_rounded_up_conservatively() -> None:
    decision = calculate(
        plan=create_plan(
            entry_price="2400.005",
            stop_loss="2390.000",
            take_profit="2420.000",
        )
    )

    sizing = decision.require_allowed()

    assert sizing.stop_distance == Decimal("10.005")
    assert sizing.ticks_to_stop == Decimal("1001")
    assert sizing.risk_per_lot == Decimal("1001.00")
    assert sizing.actual_risk_amount <= sizing.requested_risk_amount


def test_exact_volume_step_is_not_marked_rounded() -> None:
    decision = calculate(plan=create_plan(risk_percent="0.20"))

    sizing = decision.require_allowed()

    assert sizing.raw_volume == Decimal("0.02")
    assert sizing.volume == Decimal("0.02")
    assert sizing.was_rounded_down is False


def test_volume_is_capped_by_broker_maximum() -> None:
    decision = calculate(
        plan=create_plan(
            entry_price="2400",
            stop_loss="2399",
            take_profit="2402",
            risk_percent="1.00",
        ),
        account=create_account(
            balance="1000000",
            equity="1000000",
        ),
        specification=create_specification(
            volume_max="1.00",
        ),
    )

    sizing = decision.require_allowed()

    assert sizing.raw_volume == Decimal("100")
    assert sizing.volume == Decimal("1.00")
    assert sizing.was_capped_by_maximum is True
    assert sizing.actual_risk_amount == Decimal("100.00")


def test_risk_budget_below_minimum_volume_is_blocked() -> None:
    decision = calculate(
        account=create_account(
            balance="1000",
            equity="1000",
        )
    )

    assert decision.allowed is False
    assert decision.sizing is None
    assert PositionSizeBlockReason.RISK_BUDGET_BELOW_MINIMUM_VOLUME in decision.reasons


@pytest.mark.parametrize(
    ("balance", "equity"),
    [
        ("0", "10000"),
        ("10000", "0"),
        ("-1", "10000"),
        ("10000", "-1"),
    ],
)
def test_non_positive_risk_capital_is_blocked(
    balance: str,
    equity: str,
) -> None:
    decision = calculate(
        account=create_account(
            balance=balance,
            equity=equity,
        )
    )

    assert PositionSizeBlockReason.ACCOUNT_CAPITAL_NON_POSITIVE in decision.reasons


def test_account_currency_mismatch_is_blocked() -> None:
    decision = calculate(
        account=create_account(currency="EUR"),
        specification=create_specification(account_currency="USD"),
    )

    assert decision.allowed is False
    assert PositionSizeBlockReason.ACCOUNT_CURRENCY_MISMATCH in decision.reasons


def test_require_allowed_raises_for_blocked_decision() -> None:
    decision = calculate(
        account=create_account(
            balance="1000",
            equity="1000",
        )
    )

    with pytest.raises(
        PermissionError,
        match="RISK_BUDGET_BELOW_MINIMUM_VOLUME",
    ):
        decision.require_allowed()


def test_position_size_is_immutable() -> None:
    sizing = calculate().require_allowed()

    with pytest.raises(FrozenInstanceError):
        sizing.volume = Decimal("1.00")


def test_volume_normalization_always_rounds_down() -> None:
    specification = create_specification(
        volume_step="0.10",
        volume_min="0.10",
        volume_max="100.00",
    )

    assert specification.normalize_volume_down("1.29") == Decimal("1.20")


@pytest.mark.parametrize(
    "overrides",
    [
        {"symbol": "EURUSD"},
        {"account_currency": ""},
        {"tick_size": "0"},
        {"tick_value_per_lot": "0"},
        {"volume_min": "0"},
        {"volume_max": "0"},
        {"volume_step": "0"},
        {
            "volume_min": "1.00",
            "volume_max": "0.50",
        },
        {
            "volume_min": "0.01",
            "volume_max": "1.00",
            "volume_step": "2.00",
        },
        {
            "volume_min": "0.015",
            "volume_step": "0.01",
        },
        {
            "volume_max": "1.005",
            "volume_step": "0.01",
        },
    ],
)
def test_invalid_symbol_specifications_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        create_specification(**overrides)


def test_actual_risk_never_exceeds_requested_risk() -> None:
    test_cases = [
        ("0.10", "2399.99"),
        ("0.25", "2390.00"),
        ("0.50", "2387.43"),
        ("1.00", "2375.12"),
    ]

    for risk_percent, stop_loss in test_cases:
        decision = calculate(
            plan=create_plan(
                risk_percent=risk_percent,
                stop_loss=stop_loss,
            )
        )

        if decision.allowed:
            sizing = decision.require_allowed()

            assert sizing.actual_risk_amount <= sizing.requested_risk_amount
            assert sizing.actual_risk_percent <= sizing.requested_risk_percent


def test_required_inputs_must_use_domain_types() -> None:
    with pytest.raises(ValueError, match="TradePlan"):
        calculate_position_size(
            plan="invalid",
            account=create_account(),
            specification=create_specification(),
        )

    with pytest.raises(ValueError, match="AccountSnapshot"):
        calculate_position_size(
            plan=create_plan(),
            account="invalid",
            specification=create_specification(),
        )

    with pytest.raises(
        ValueError,
        match="GoldSymbolSpecification",
    ):
        calculate_position_size(
            plan=create_plan(),
            account=create_account(),
            specification="invalid",
        )
