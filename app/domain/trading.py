from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Final, TypeAlias

DecimalLike: TypeAlias = Decimal | int | float | str

CANONICAL_GOLD_SYMBOL: Final[str] = "XAUUSD"
MAX_TRADE_RISK_PERCENT: Final[Decimal] = Decimal("1.00")


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class EntryType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class TradePlanStatus(str, Enum):
    PLANNED = "PLANNED"
    ARMED = "ARMED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


def _positive_decimal(value: DecimalLike, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _required_identifier(value: str, field_name: str) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > 64:
        raise ValueError(f"{field_name} cannot exceed 64 characters.")

    return normalized


@dataclass(frozen=True, slots=True)
class TradePlan:
    """Immutable broker-independent Gold trade plan."""

    symbol: str
    side: TradeSide
    entry_type: EntryType
    entry_price: DecimalLike
    stop_loss: DecimalLike
    take_profit: DecimalLike
    risk_percent: DecimalLike
    strategy_id: str
    setup_id: str
    oco_group_id: str | None = None

    def __post_init__(self) -> None:
        symbol = str(self.symbol).strip().upper()

        if symbol != CANONICAL_GOLD_SYMBOL:
            raise ValueError(f"Only canonical symbol {CANONICAL_GOLD_SYMBOL} is supported.")

        try:
            side = TradeSide(self.side)
        except ValueError as error:
            raise ValueError(f"Unsupported trade side: {self.side}.") from error

        try:
            entry_type = EntryType(self.entry_type)
        except ValueError as error:
            raise ValueError(f"Unsupported entry type: {self.entry_type}.") from error

        entry_price = _positive_decimal(
            self.entry_price,
            "entry_price",
        )
        stop_loss = _positive_decimal(
            self.stop_loss,
            "stop_loss",
        )
        take_profit = _positive_decimal(
            self.take_profit,
            "take_profit",
        )
        risk_percent = _positive_decimal(
            self.risk_percent,
            "risk_percent",
        )

        if risk_percent > MAX_TRADE_RISK_PERCENT:
            raise ValueError(f"risk_percent cannot exceed {MAX_TRADE_RISK_PERCENT}%.")

        strategy_id = _required_identifier(
            self.strategy_id,
            "strategy_id",
        )
        setup_id = _required_identifier(
            self.setup_id,
            "setup_id",
        )

        oco_group_id: str | None = None

        if self.oco_group_id is not None:
            oco_group_id = _required_identifier(
                self.oco_group_id,
                "oco_group_id",
            )

        if side == TradeSide.BUY:
            if stop_loss >= entry_price:
                raise ValueError("BUY stop_loss must be below entry_price.")

            if take_profit <= entry_price:
                raise ValueError("BUY take_profit must be above entry_price.")

        if side == TradeSide.SELL:
            if stop_loss <= entry_price:
                raise ValueError("SELL stop_loss must be above entry_price.")

            if take_profit >= entry_price:
                raise ValueError("SELL take_profit must be below entry_price.")

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "entry_type", entry_type)
        object.__setattr__(self, "entry_price", entry_price)
        object.__setattr__(self, "stop_loss", stop_loss)
        object.__setattr__(self, "take_profit", take_profit)
        object.__setattr__(self, "risk_percent", risk_percent)
        object.__setattr__(self, "strategy_id", strategy_id)
        object.__setattr__(self, "setup_id", setup_id)
        object.__setattr__(self, "oco_group_id", oco_group_id)

    @property
    def stop_distance(self) -> Decimal:
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward_distance(self) -> Decimal:
        return abs(self.take_profit - self.entry_price)

    @property
    def risk_reward_ratio(self) -> Decimal:
        return self.reward_distance / self.stop_distance

    @property
    def is_pending_order(self) -> bool:
        return self.entry_type in {
            EntryType.LIMIT,
            EntryType.STOP,
        }

    @property
    def has_oco_group(self) -> bool:
        return self.oco_group_id is not None
