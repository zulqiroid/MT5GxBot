from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.constants import BotMode
from app.domain.exposure import (
    AccountSnapshot,
    GoldExposureSnapshot,
    PendingOrderSnapshot,
    PositionSnapshot,
)
from app.domain.risk import (
    DailyRiskSnapshot,
    RiskBlockReason,
    RiskLimits,
    evaluate_trade_plan,
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
        "margin": "1000.00",
        "free_margin": "9000.00",
        "observed_at": NOW,
    }
    values.update(overrides)

    return AccountSnapshot(**values)


def create_daily(**overrides: object) -> DailyRiskSnapshot:
    values: dict[str, object] = {
        "starting_balance": "10000.00",
        "realized_pnl": "0",
        "trades_opened": 0,
        "observed_at": NOW,
    }
    values.update(overrides)

    return DailyRiskSnapshot(**values)


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
        "risk_percent": "0.40",
        "strategy_id": "liquidity-breakout",
        "setup_id": "setup-002",
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
        "setup_id": "setup-003",
        "magic_number": 26062801,
        "opened_at": NOW - timedelta(minutes=15),
        "observed_at": NOW,
    }
    values.update(overrides)

    return PositionSnapshot(**values)


def evaluate(
    *,
    plan: TradePlan | None = None,
    account: AccountSnapshot | None = None,
    exposure: GoldExposureSnapshot | None = None,
    daily: DailyRiskSnapshot | None = None,
    limits: RiskLimits | None = None,
    bot_mode: BotMode = BotMode.PAPER,
    live_trading_armed: bool = False,
    evaluated_at: datetime = NOW,
):
    return evaluate_trade_plan(
        plan=plan or create_plan(),
        account=account or create_account(),
        exposure=exposure or GoldExposureSnapshot(),
        daily=daily or create_daily(),
        limits=limits or RiskLimits(),
        bot_mode=bot_mode,
        live_trading_armed=live_trading_armed,
        evaluated_at=evaluated_at,
    )


def test_safe_paper_trade_is_allowed() -> None:
    decision = evaluate()

    assert decision.allowed is True
    assert decision.reasons == ()
    assert decision.current_reserved_risk_percent == Decimal("0")
    assert decision.projected_reserved_risk_percent == Decimal("0.25")


def test_armed_live_trade_is_allowed() -> None:
    decision = evaluate(
        bot_mode=BotMode.LIVE,
        live_trading_armed=True,
    )

    assert decision.allowed is True


def test_unarmed_live_trade_is_blocked() -> None:
    decision = evaluate(bot_mode=BotMode.LIVE)

    assert decision.allowed is False
    assert RiskBlockReason.LIVE_TRADING_NOT_ARMED in decision.reasons


def test_live_arming_flag_is_invalid_outside_live_mode() -> None:
    decision = evaluate(live_trading_armed=True)

    assert RiskBlockReason.INVALID_LIVE_ARMING_STATE in decision.reasons


@pytest.mark.parametrize(
    ("field_name", "value", "reason"),
    [
        (
            "balance",
            "0",
            RiskBlockReason.ACCOUNT_BALANCE_NON_POSITIVE,
        ),
        (
            "equity",
            "-1",
            RiskBlockReason.ACCOUNT_EQUITY_NON_POSITIVE,
        ),
    ],
)
def test_non_positive_account_values_are_blocked(
    field_name: str,
    value: str,
    reason: RiskBlockReason,
) -> None:
    decision = evaluate(account=create_account(**{field_name: value}))

    assert reason in decision.reasons


def test_stale_account_snapshot_is_blocked() -> None:
    account = create_account(observed_at=NOW - timedelta(seconds=31))

    decision = evaluate(account=account)

    assert RiskBlockReason.ACCOUNT_SNAPSHOT_STALE in decision.reasons
    assert decision.account_snapshot_age_seconds == Decimal("31.0")


def test_account_snapshot_from_future_is_blocked() -> None:
    account = create_account(observed_at=NOW + timedelta(seconds=6))

    decision = evaluate(account=account)

    assert RiskBlockReason.ACCOUNT_SNAPSHOT_FROM_FUTURE in decision.reasons


def test_daily_snapshot_from_future_is_blocked() -> None:
    daily = create_daily(observed_at=NOW + timedelta(seconds=6))

    decision = evaluate(daily=daily)

    assert RiskBlockReason.DAILY_SNAPSHOT_FROM_FUTURE in decision.reasons


def test_low_margin_level_is_blocked() -> None:
    account = create_account(
        equity="1000",
        margin="1000",
    )

    decision = evaluate(account=account)

    assert RiskBlockReason.MARGIN_LEVEL_TOO_LOW in decision.reasons


def test_zero_margin_does_not_create_false_margin_block() -> None:
    account = create_account(margin="0")

    decision = evaluate(account=account)

    assert RiskBlockReason.MARGIN_LEVEL_TOO_LOW not in decision.reasons


def test_daily_loss_is_calculated_exactly() -> None:
    daily = create_daily(realized_pnl="-200")

    assert daily.daily_loss_amount == Decimal("200")
    assert daily.daily_loss_percent == Decimal("2.00")


def test_positive_realized_pnl_has_zero_daily_loss() -> None:
    daily = create_daily(realized_pnl="500")

    assert daily.daily_loss_amount == Decimal("0")
    assert daily.daily_loss_percent == Decimal("0")


def test_daily_loss_limit_is_blocked_at_exact_limit() -> None:
    decision = evaluate(daily=create_daily(realized_pnl="-200"))

    assert RiskBlockReason.DAILY_LOSS_LIMIT_REACHED in decision.reasons


def test_daily_trade_limit_is_blocked_at_exact_limit() -> None:
    decision = evaluate(daily=create_daily(trades_opened=3))

    assert RiskBlockReason.DAILY_TRADE_LIMIT_REACHED in decision.reasons


def test_configured_trade_risk_limit_is_enforced() -> None:
    decision = evaluate(plan=create_plan(risk_percent="0.50"))

    assert RiskBlockReason.TRADE_RISK_LIMIT_EXCEEDED in decision.reasons


def test_open_position_blocks_new_entry() -> None:
    exposure = GoldExposureSnapshot(positions=(create_position(),))

    decision = evaluate(exposure=exposure)

    assert RiskBlockReason.OPEN_POSITION_EXISTS in decision.reasons


def test_market_entry_conflicts_with_pending_orders() -> None:
    exposure = GoldExposureSnapshot(pending_orders=(create_pending_order(),))

    decision = evaluate(exposure=exposure)

    assert RiskBlockReason.PENDING_ORDER_CONFLICT in decision.reasons


def test_matching_oco_pending_entry_is_allowed() -> None:
    exposure = GoldExposureSnapshot(pending_orders=(create_pending_order(risk_percent="0.40"),))
    plan = create_plan(
        entry_type=EntryType.STOP,
        entry_price="2390",
        stop_loss="2400",
        take_profit="2370",
        side=TradeSide.SELL,
        risk_percent="0.25",
        oco_group_id="oco-001",
    )

    decision = evaluate(
        plan=plan,
        exposure=exposure,
    )

    assert decision.allowed is True
    assert decision.projected_reserved_risk_percent == Decimal("0.65")


def test_missing_oco_group_is_blocked() -> None:
    exposure = GoldExposureSnapshot(pending_orders=(create_pending_order(),))
    plan = create_plan(
        entry_type=EntryType.STOP,
        oco_group_id=None,
    )

    decision = evaluate(
        plan=plan,
        exposure=exposure,
    )

    assert RiskBlockReason.OCO_GROUP_REQUIRED in decision.reasons


def test_mismatched_oco_group_is_blocked() -> None:
    exposure = GoldExposureSnapshot(pending_orders=(create_pending_order(),))
    plan = create_plan(
        entry_type=EntryType.STOP,
        oco_group_id="oco-999",
    )

    decision = evaluate(
        plan=plan,
        exposure=exposure,
    )

    assert RiskBlockReason.OCO_GROUP_MISMATCH in decision.reasons


def test_aggregate_risk_above_limit_is_blocked() -> None:
    exposure = GoldExposureSnapshot(pending_orders=(create_pending_order(risk_percent="0.80"),))
    plan = create_plan(
        entry_type=EntryType.STOP,
        risk_percent="0.25",
        oco_group_id="oco-001",
    )

    decision = evaluate(
        plan=plan,
        exposure=exposure,
    )

    assert RiskBlockReason.AGGREGATE_RISK_LIMIT_EXCEEDED in decision.reasons
    assert decision.projected_reserved_risk_percent == Decimal("1.05")


def test_require_allowed_does_nothing_when_allowed() -> None:
    decision = evaluate()

    decision.require_allowed()


def test_require_allowed_raises_with_block_reasons() -> None:
    decision = evaluate(bot_mode=BotMode.LIVE)

    with pytest.raises(
        PermissionError,
        match="LIVE_TRADING_NOT_ARMED",
    ):
        decision.require_allowed()


@pytest.mark.parametrize(
    "values",
    [
        {"max_trade_risk_percent": "0"},
        {"max_trade_risk_percent": "1.01"},
        {"max_aggregate_risk_percent": "1.01"},
        {
            "max_trade_risk_percent": "0.75",
            "max_aggregate_risk_percent": "0.50",
        },
        {"max_daily_loss_percent": "10.01"},
        {"max_trades_per_day": 0},
        {"max_trades_per_day": 21},
        {"min_margin_level_percent": "0"},
        {"max_account_snapshot_age_seconds": 0},
        {"max_account_snapshot_age_seconds": 3601},
    ],
)
def test_invalid_risk_limits_are_rejected(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        RiskLimits(**values)


@pytest.mark.parametrize(
    "values",
    [
        {"starting_balance": "0"},
        {"realized_pnl": "NaN"},
        {"trades_opened": -1},
        {"trades_opened": True},
        {
            "observed_at": datetime(
                2026,
                7,
                25,
                12,
                0,
            )
        },
    ],
)
def test_invalid_daily_snapshot_is_rejected(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        create_daily(**values)


def test_naive_evaluation_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate(
            evaluated_at=datetime(
                2026,
                7,
                25,
                12,
                0,
            )
        )


def test_live_armed_value_must_be_boolean() -> None:
    with pytest.raises(ValueError, match="boolean"):
        evaluate_trade_plan(
            plan=create_plan(),
            account=create_account(),
            exposure=GoldExposureSnapshot(),
            daily=create_daily(),
            limits=RiskLimits(),
            bot_mode=BotMode.PAPER,
            live_trading_armed=1,
            evaluated_at=NOW,
        )
