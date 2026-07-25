from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias

from app.config.constants import BotMode
from app.domain.exposure import (
    AccountSnapshot,
    GoldExposureSnapshot,
)
from app.domain.trading import (
    MAX_TRADE_RISK_PERCENT,
    EntryType,
    TradePlan,
)

DecimalLike: TypeAlias = Decimal | int | float | str

FUTURE_TIMESTAMP_TOLERANCE = timedelta(seconds=5)


class RiskBlockReason(str, Enum):
    LIVE_TRADING_NOT_ARMED = "LIVE_TRADING_NOT_ARMED"
    INVALID_LIVE_ARMING_STATE = "INVALID_LIVE_ARMING_STATE"

    ACCOUNT_BALANCE_NON_POSITIVE = "ACCOUNT_BALANCE_NON_POSITIVE"
    ACCOUNT_EQUITY_NON_POSITIVE = "ACCOUNT_EQUITY_NON_POSITIVE"
    ACCOUNT_SNAPSHOT_STALE = "ACCOUNT_SNAPSHOT_STALE"
    ACCOUNT_SNAPSHOT_FROM_FUTURE = "ACCOUNT_SNAPSHOT_FROM_FUTURE"
    DAILY_SNAPSHOT_FROM_FUTURE = "DAILY_SNAPSHOT_FROM_FUTURE"
    MARGIN_LEVEL_TOO_LOW = "MARGIN_LEVEL_TOO_LOW"

    DAILY_LOSS_LIMIT_REACHED = "DAILY_LOSS_LIMIT_REACHED"
    DAILY_TRADE_LIMIT_REACHED = "DAILY_TRADE_LIMIT_REACHED"

    TRADE_RISK_LIMIT_EXCEEDED = "TRADE_RISK_LIMIT_EXCEEDED"
    AGGREGATE_RISK_LIMIT_EXCEEDED = "AGGREGATE_RISK_LIMIT_EXCEEDED"

    OPEN_POSITION_EXISTS = "OPEN_POSITION_EXISTS"
    PENDING_ORDER_CONFLICT = "PENDING_ORDER_CONFLICT"
    OCO_GROUP_REQUIRED = "OCO_GROUP_REQUIRED"
    OCO_GROUP_MISMATCH = "OCO_GROUP_MISMATCH"


def _finite_decimal(
    value: DecimalLike,
    field_name: str,
) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    return decimal_value


def _positive_decimal(
    value: DecimalLike,
    field_name: str,
) -> Decimal:
    decimal_value = _finite_decimal(value, field_name)

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _non_negative_integer(
    value: int,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _positive_integer(
    value: int,
    field_name: str,
) -> int:
    normalized = _non_negative_integer(value, field_name)

    if normalized == 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return normalized


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Configured limits used by the deterministic risk gate."""

    max_trade_risk_percent: DecimalLike = Decimal("0.25")
    max_aggregate_risk_percent: DecimalLike = Decimal("1.00")
    max_daily_loss_percent: DecimalLike = Decimal("2.00")
    max_trades_per_day: int = 3
    min_margin_level_percent: DecimalLike = Decimal("150")
    max_account_snapshot_age_seconds: int = 30

    def __post_init__(self) -> None:
        max_trade_risk_percent = _positive_decimal(
            self.max_trade_risk_percent,
            "max_trade_risk_percent",
        )
        max_aggregate_risk_percent = _positive_decimal(
            self.max_aggregate_risk_percent,
            "max_aggregate_risk_percent",
        )
        max_daily_loss_percent = _positive_decimal(
            self.max_daily_loss_percent,
            "max_daily_loss_percent",
        )
        min_margin_level_percent = _positive_decimal(
            self.min_margin_level_percent,
            "min_margin_level_percent",
        )
        max_trades_per_day = _positive_integer(
            self.max_trades_per_day,
            "max_trades_per_day",
        )
        max_account_snapshot_age_seconds = _positive_integer(
            self.max_account_snapshot_age_seconds,
            "max_account_snapshot_age_seconds",
        )

        if max_trade_risk_percent > MAX_TRADE_RISK_PERCENT:
            raise ValueError(f"max_trade_risk_percent cannot exceed {MAX_TRADE_RISK_PERCENT}%.")

        if max_aggregate_risk_percent > MAX_TRADE_RISK_PERCENT:
            raise ValueError(f"max_aggregate_risk_percent cannot exceed {MAX_TRADE_RISK_PERCENT}%.")

        if max_trade_risk_percent > max_aggregate_risk_percent:
            raise ValueError("max_trade_risk_percent cannot exceed max_aggregate_risk_percent.")

        if max_daily_loss_percent > Decimal("10"):
            raise ValueError("max_daily_loss_percent cannot exceed 10%.")

        if max_trades_per_day > 20:
            raise ValueError("max_trades_per_day cannot exceed 20.")

        if min_margin_level_percent > Decimal("10000"):
            raise ValueError("min_margin_level_percent is unreasonably high.")

        if max_account_snapshot_age_seconds > 3600:
            raise ValueError("max_account_snapshot_age_seconds cannot exceed 3600.")

        object.__setattr__(
            self,
            "max_trade_risk_percent",
            max_trade_risk_percent,
        )
        object.__setattr__(
            self,
            "max_aggregate_risk_percent",
            max_aggregate_risk_percent,
        )
        object.__setattr__(
            self,
            "max_daily_loss_percent",
            max_daily_loss_percent,
        )
        object.__setattr__(
            self,
            "max_trades_per_day",
            max_trades_per_day,
        )
        object.__setattr__(
            self,
            "min_margin_level_percent",
            min_margin_level_percent,
        )
        object.__setattr__(
            self,
            "max_account_snapshot_age_seconds",
            max_account_snapshot_age_seconds,
        )


@dataclass(frozen=True, slots=True)
class DailyRiskSnapshot:
    """Current trading-day loss and activity state."""

    starting_balance: DecimalLike
    realized_pnl: DecimalLike
    trades_opened: int
    observed_at: datetime

    def __post_init__(self) -> None:
        starting_balance = _positive_decimal(
            self.starting_balance,
            "starting_balance",
        )
        realized_pnl = _finite_decimal(
            self.realized_pnl,
            "realized_pnl",
        )
        trades_opened = _non_negative_integer(
            self.trades_opened,
            "trades_opened",
        )
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )

        object.__setattr__(
            self,
            "starting_balance",
            starting_balance,
        )
        object.__setattr__(
            self,
            "realized_pnl",
            realized_pnl,
        )
        object.__setattr__(
            self,
            "trades_opened",
            trades_opened,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )

    @property
    def daily_loss_amount(self) -> Decimal:
        return max(-self.realized_pnl, Decimal("0"))

    @property
    def daily_loss_percent(self) -> Decimal:
        return self.daily_loss_amount / self.starting_balance * Decimal("100")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Immutable output of the deterministic risk gate."""

    reasons: tuple[RiskBlockReason, ...]
    current_reserved_risk_percent: Decimal
    projected_reserved_risk_percent: Decimal
    daily_loss_percent: Decimal
    account_snapshot_age_seconds: Decimal

    def __post_init__(self) -> None:
        reasons = tuple(dict.fromkeys(self.reasons))

        object.__setattr__(self, "reasons", reasons)

    @property
    def allowed(self) -> bool:
        return not self.reasons

    def require_allowed(self) -> None:
        if self.allowed:
            return

        reason_text = ", ".join(reason.value for reason in self.reasons)

        raise PermissionError(f"Trade blocked by risk gate: {reason_text}")


def evaluate_trade_plan(
    *,
    plan: TradePlan,
    account: AccountSnapshot,
    exposure: GoldExposureSnapshot,
    daily: DailyRiskSnapshot,
    limits: RiskLimits,
    bot_mode: BotMode,
    live_trading_armed: bool,
    evaluated_at: datetime,
) -> RiskDecision:
    """Evaluate a new trade plan without broker side effects."""

    evaluation_time = _utc_datetime(
        evaluated_at,
        "evaluated_at",
    )

    try:
        execution_mode = BotMode(bot_mode)
    except ValueError as error:
        raise ValueError(f"Unsupported bot mode: {bot_mode}.") from error

    if not isinstance(live_trading_armed, bool):
        raise ValueError("live_trading_armed must be a boolean.")

    reasons: list[RiskBlockReason] = []

    if execution_mode == BotMode.LIVE and not live_trading_armed:
        reasons.append(RiskBlockReason.LIVE_TRADING_NOT_ARMED)

    if execution_mode != BotMode.LIVE and live_trading_armed:
        reasons.append(RiskBlockReason.INVALID_LIVE_ARMING_STATE)

    if account.balance <= 0:
        reasons.append(RiskBlockReason.ACCOUNT_BALANCE_NON_POSITIVE)

    if account.equity <= 0:
        reasons.append(RiskBlockReason.ACCOUNT_EQUITY_NON_POSITIVE)

    account_age = evaluation_time - account.observed_at
    account_age_seconds = Decimal(str(account_age.total_seconds()))

    if account_age < -FUTURE_TIMESTAMP_TOLERANCE:
        reasons.append(RiskBlockReason.ACCOUNT_SNAPSHOT_FROM_FUTURE)
    elif account_age.total_seconds() > (limits.max_account_snapshot_age_seconds):
        reasons.append(RiskBlockReason.ACCOUNT_SNAPSHOT_STALE)

    if daily.observed_at > evaluation_time + FUTURE_TIMESTAMP_TOLERANCE:
        reasons.append(RiskBlockReason.DAILY_SNAPSHOT_FROM_FUTURE)

    margin_level = account.margin_level_percent

    if margin_level is not None and margin_level < limits.min_margin_level_percent:
        reasons.append(RiskBlockReason.MARGIN_LEVEL_TOO_LOW)

    daily_loss_percent = daily.daily_loss_percent

    if daily_loss_percent >= limits.max_daily_loss_percent:
        reasons.append(RiskBlockReason.DAILY_LOSS_LIMIT_REACHED)

    if daily.trades_opened >= limits.max_trades_per_day:
        reasons.append(RiskBlockReason.DAILY_TRADE_LIMIT_REACHED)

    if plan.risk_percent > limits.max_trade_risk_percent:
        reasons.append(RiskBlockReason.TRADE_RISK_LIMIT_EXCEEDED)

    if exposure.has_open_position:
        reasons.append(RiskBlockReason.OPEN_POSITION_EXISTS)

    if exposure.has_pending_orders:
        if plan.entry_type == EntryType.MARKET:
            reasons.append(RiskBlockReason.PENDING_ORDER_CONFLICT)
        else:
            existing_oco_groups = {order.oco_group_id for order in exposure.pending_orders}

            if plan.oco_group_id is None or None in existing_oco_groups:
                reasons.append(RiskBlockReason.OCO_GROUP_REQUIRED)
            elif existing_oco_groups != {plan.oco_group_id}:
                reasons.append(RiskBlockReason.OCO_GROUP_MISMATCH)

    current_reserved_risk = exposure.total_reserved_risk_percent
    projected_reserved_risk = current_reserved_risk + plan.risk_percent

    if projected_reserved_risk > limits.max_aggregate_risk_percent:
        reasons.append(RiskBlockReason.AGGREGATE_RISK_LIMIT_EXCEEDED)

    return RiskDecision(
        reasons=tuple(reasons),
        current_reserved_risk_percent=(current_reserved_risk),
        projected_reserved_risk_percent=(projected_reserved_risk),
        daily_loss_percent=daily_loss_percent,
        account_snapshot_age_seconds=(account_age_seconds),
    )
