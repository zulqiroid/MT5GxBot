from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

from app.domain.trading import (
    CANONICAL_GOLD_SYMBOL,
    MAX_TRADE_RISK_PERCENT,
    EntryType,
    TradeSide,
)

DecimalLike: TypeAlias = Decimal | int | float | str


def _finite_decimal(value: DecimalLike, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    return decimal_value


def _positive_decimal(value: DecimalLike, field_name: str) -> Decimal:
    decimal_value = _finite_decimal(value, field_name)

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _non_negative_decimal(
    value: DecimalLike,
    field_name: str,
) -> Decimal:
    decimal_value = _finite_decimal(value, field_name)

    if decimal_value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return decimal_value


def _positive_integer(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _required_text(
    value: str,
    field_name: str,
    maximum_length: int = 64,
) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


def _canonical_symbol(value: str) -> str:
    symbol = str(value).strip().upper()

    if symbol != CANONICAL_GOLD_SYMBOL:
        raise ValueError(f"Only canonical symbol {CANONICAL_GOLD_SYMBOL} is supported.")

    return symbol


def _utc_datetime(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _validate_trade_geometry(
    *,
    side: TradeSide,
    entry_price: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
) -> None:
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


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Immutable representation of the broker account state."""

    login: int
    server: str
    currency: str
    balance: DecimalLike
    equity: DecimalLike
    margin: DecimalLike
    free_margin: DecimalLike
    observed_at: datetime

    def __post_init__(self) -> None:
        login = _positive_integer(self.login, "login")
        server = _required_text(self.server, "server")
        currency = _required_text(
            self.currency,
            "currency",
            maximum_length=12,
        ).upper()

        balance = _finite_decimal(self.balance, "balance")
        equity = _finite_decimal(self.equity, "equity")
        margin = _non_negative_decimal(self.margin, "margin")
        free_margin = _finite_decimal(
            self.free_margin,
            "free_margin",
        )
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )

        object.__setattr__(self, "login", login)
        object.__setattr__(self, "server", server)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "balance", balance)
        object.__setattr__(self, "equity", equity)
        object.__setattr__(self, "margin", margin)
        object.__setattr__(self, "free_margin", free_margin)
        object.__setattr__(self, "observed_at", observed_at)

    @property
    def margin_level_percent(self) -> Decimal | None:
        if self.margin == 0:
            return None

        return self.equity / self.margin * Decimal("100")

    @property
    def drawdown_percent(self) -> Decimal | None:
        if self.balance <= 0:
            return None

        drawdown = (self.balance - self.equity) / self.balance * Decimal("100")

        return max(drawdown, Decimal("0"))


@dataclass(frozen=True, slots=True)
class PendingOrderSnapshot:
    """Immutable broker-side pending Gold order."""

    ticket: int
    symbol: str
    side: TradeSide
    entry_type: EntryType
    volume: DecimalLike
    entry_price: DecimalLike
    stop_loss: DecimalLike
    take_profit: DecimalLike
    risk_percent: DecimalLike
    strategy_id: str
    setup_id: str
    magic_number: int
    created_at: datetime
    oco_group_id: str | None = None

    def __post_init__(self) -> None:
        ticket = _positive_integer(self.ticket, "ticket")
        symbol = _canonical_symbol(self.symbol)

        try:
            side = TradeSide(self.side)
        except ValueError as error:
            raise ValueError(f"Unsupported trade side: {self.side}.") from error

        try:
            entry_type = EntryType(self.entry_type)
        except ValueError as error:
            raise ValueError(f"Unsupported entry type: {self.entry_type}.") from error

        if entry_type == EntryType.MARKET:
            raise ValueError("Pending orders must use LIMIT or STOP entry type.")

        volume = _positive_decimal(self.volume, "volume")
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

        _validate_trade_geometry(
            side=side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        strategy_id = _required_text(
            self.strategy_id,
            "strategy_id",
        )
        setup_id = _required_text(
            self.setup_id,
            "setup_id",
        )
        magic_number = _positive_integer(
            self.magic_number,
            "magic_number",
        )
        created_at = _utc_datetime(
            self.created_at,
            "created_at",
        )

        oco_group_id: str | None = None

        if self.oco_group_id is not None:
            oco_group_id = _required_text(
                self.oco_group_id,
                "oco_group_id",
            )

        object.__setattr__(self, "ticket", ticket)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "entry_type", entry_type)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "entry_price", entry_price)
        object.__setattr__(self, "stop_loss", stop_loss)
        object.__setattr__(self, "take_profit", take_profit)
        object.__setattr__(self, "risk_percent", risk_percent)
        object.__setattr__(self, "strategy_id", strategy_id)
        object.__setattr__(self, "setup_id", setup_id)
        object.__setattr__(self, "magic_number", magic_number)
        object.__setattr__(self, "created_at", created_at)
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


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Immutable broker-side open Gold position."""

    ticket: int
    symbol: str
    side: TradeSide
    volume: DecimalLike
    entry_price: DecimalLike
    current_price: DecimalLike
    stop_loss: DecimalLike
    take_profit: DecimalLike
    initial_risk_percent: DecimalLike
    unrealized_pnl: DecimalLike
    strategy_id: str
    setup_id: str
    magic_number: int
    opened_at: datetime
    observed_at: datetime

    def __post_init__(self) -> None:
        ticket = _positive_integer(self.ticket, "ticket")
        symbol = _canonical_symbol(self.symbol)

        try:
            side = TradeSide(self.side)
        except ValueError as error:
            raise ValueError(f"Unsupported trade side: {self.side}.") from error

        volume = _positive_decimal(self.volume, "volume")
        entry_price = _positive_decimal(
            self.entry_price,
            "entry_price",
        )
        current_price = _positive_decimal(
            self.current_price,
            "current_price",
        )
        stop_loss = _positive_decimal(
            self.stop_loss,
            "stop_loss",
        )
        take_profit = _positive_decimal(
            self.take_profit,
            "take_profit",
        )
        initial_risk_percent = _positive_decimal(
            self.initial_risk_percent,
            "initial_risk_percent",
        )

        if initial_risk_percent > MAX_TRADE_RISK_PERCENT:
            raise ValueError(f"initial_risk_percent cannot exceed {MAX_TRADE_RISK_PERCENT}%.")

        unrealized_pnl = _finite_decimal(
            self.unrealized_pnl,
            "unrealized_pnl",
        )

        _validate_trade_geometry(
            side=side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        strategy_id = _required_text(
            self.strategy_id,
            "strategy_id",
        )
        setup_id = _required_text(
            self.setup_id,
            "setup_id",
        )
        magic_number = _positive_integer(
            self.magic_number,
            "magic_number",
        )
        opened_at = _utc_datetime(
            self.opened_at,
            "opened_at",
        )
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )

        if observed_at < opened_at:
            raise ValueError("observed_at cannot be earlier than opened_at.")

        object.__setattr__(self, "ticket", ticket)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "entry_price", entry_price)
        object.__setattr__(self, "current_price", current_price)
        object.__setattr__(self, "stop_loss", stop_loss)
        object.__setattr__(self, "take_profit", take_profit)
        object.__setattr__(
            self,
            "initial_risk_percent",
            initial_risk_percent,
        )
        object.__setattr__(
            self,
            "unrealized_pnl",
            unrealized_pnl,
        )
        object.__setattr__(self, "strategy_id", strategy_id)
        object.__setattr__(self, "setup_id", setup_id)
        object.__setattr__(self, "magic_number", magic_number)
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "observed_at", observed_at)

    @property
    def price_move(self) -> Decimal:
        if self.side == TradeSide.BUY:
            return self.current_price - self.entry_price

        return self.entry_price - self.current_price

    @property
    def is_profitable(self) -> bool:
        return self.unrealized_pnl > 0


@dataclass(frozen=True, slots=True)
class GoldExposureSnapshot:
    """Combined Gold positions and pending entry orders."""

    positions: tuple[PositionSnapshot, ...] = ()
    pending_orders: tuple[PendingOrderSnapshot, ...] = ()

    def __post_init__(self) -> None:
        positions = tuple(self.positions)
        pending_orders = tuple(self.pending_orders)

        if len(positions) > 1:
            raise ValueError("Maximum one open XAUUSD position is allowed.")

        if positions and pending_orders:
            raise ValueError(
                "Pending entry orders are not allowed while an XAUUSD position is open."
            )

        tickets = [item.ticket for item in (*positions, *pending_orders)]

        if len(tickets) != len(set(tickets)):
            raise ValueError("Duplicate broker tickets are not allowed.")

        total_risk = sum(
            (position.initial_risk_percent for position in positions),
            start=Decimal("0"),
        )

        total_risk += sum(
            (order.risk_percent for order in pending_orders),
            start=Decimal("0"),
        )

        if total_risk > MAX_TRADE_RISK_PERCENT:
            raise ValueError(f"Aggregate active Gold risk cannot exceed {MAX_TRADE_RISK_PERCENT}%.")

        object.__setattr__(self, "positions", positions)
        object.__setattr__(
            self,
            "pending_orders",
            pending_orders,
        )

    @property
    def total_reserved_risk_percent(self) -> Decimal:
        position_risk = sum(
            (position.initial_risk_percent for position in self.positions),
            start=Decimal("0"),
        )

        pending_risk = sum(
            (order.risk_percent for order in self.pending_orders),
            start=Decimal("0"),
        )

        return position_risk + pending_risk

    @property
    def has_open_position(self) -> bool:
        return bool(self.positions)

    @property
    def has_pending_orders(self) -> bool:
        return bool(self.pending_orders)

    @property
    def has_active_exposure(self) -> bool:
        return self.has_open_position or self.has_pending_orders

    @property
    def open_position(self) -> PositionSnapshot | None:
        if not self.positions:
            return None

        return self.positions[0]
