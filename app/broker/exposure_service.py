from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from app.broker.mt5_client import MT5ConnectionError
from app.domain.trading import EntryType, TradeSide


class BrokerExposureErrorReason(str, Enum):
    CONNECTION_REQUIRED = "CONNECTION_REQUIRED"
    POSITIONS_READ_FAILED = "POSITIONS_READ_FAILED"
    ORDERS_READ_FAILED = "ORDERS_READ_FAILED"
    POSITIONS_UNAVAILABLE = "POSITIONS_UNAVAILABLE"
    ORDERS_UNAVAILABLE = "ORDERS_UNAVAILABLE"
    INVALID_POSITION_DATA = "INVALID_POSITION_DATA"
    INVALID_ORDER_DATA = "INVALID_ORDER_DATA"
    UNSUPPORTED_POSITION_TYPE = "UNSUPPORTED_POSITION_TYPE"
    UNSUPPORTED_ORDER_TYPE = "UNSUPPORTED_ORDER_TYPE"
    DUPLICATE_TICKET = "DUPLICATE_TICKET"
    INVALID_CLOCK = "INVALID_CLOCK"


class BrokerExposureSafetyIssue(str, Enum):
    MULTIPLE_OPEN_POSITIONS = "MULTIPLE_OPEN_POSITIONS"
    POSITION_AND_PENDING_ORDERS = "POSITION_AND_PENDING_ORDERS"
    POSITION_WITHOUT_STOP_LOSS = "POSITION_WITHOUT_STOP_LOSS"
    POSITION_WITHOUT_TAKE_PROFIT = "POSITION_WITHOUT_TAKE_PROFIT"
    PENDING_ORDER_WITHOUT_STOP_LOSS = "PENDING_ORDER_WITHOUT_STOP_LOSS"
    PENDING_ORDER_WITHOUT_TAKE_PROFIT = "PENDING_ORDER_WITHOUT_TAKE_PROFIT"


class BrokerExposureServiceError(RuntimeError):
    """Structured failure while reading broker exposure."""

    def __init__(
        self,
        reason: BrokerExposureErrorReason,
        message: str,
    ) -> None:
        self.reason = BrokerExposureErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Broker exposure error [{self.reason.value}]: {self.message}")


@runtime_checkable
class BrokerExposureClient(Protocol):
    """Read-only client contract required by exposure mapping."""

    @property
    def initialized(self) -> bool: ...

    def positions_get(
        self,
        symbol: str | None = None,
    ) -> Any: ...

    def orders_get(
        self,
        symbol: str | None = None,
    ) -> Any: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _required_text(
    value: object,
    field_name: str,
    maximum_length: int = 128,
) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


def _optional_text(
    value: object,
    field_name: str,
    maximum_length: int = 128,
) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()

    if not normalized:
        return None

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


def _finite_decimal(
    value: object,
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
    value: object,
    field_name: str,
) -> Decimal:
    decimal_value = _finite_decimal(
        value,
        field_name,
    )

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _optional_positive_price(
    value: object,
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None

    decimal_value = _finite_decimal(
        value,
        field_name,
    )

    if decimal_value == 0:
        return None

    if decimal_value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return decimal_value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer.")

    try:
        integer_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a positive integer.") from error

    if integer_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return integer_value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer.")

    try:
        integer_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a non-negative integer.") from error

    if integer_value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return integer_value


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _epoch_to_utc(
    value: object,
    field_name: str,
) -> datetime:
    seconds = _positive_integer(
        value,
        field_name,
    )

    try:
        return datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        )
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"{field_name} contains an invalid Unix timestamp.") from error


def _required_field(
    source: object,
    field_name: str,
) -> object:
    if isinstance(source, Mapping):
        if field_name not in source:
            raise ValueError(f"Broker exposure field is missing: {field_name}.")

        return source[field_name]

    if not hasattr(source, field_name):
        raise ValueError(f"Broker exposure field is missing: {field_name}.")

    return getattr(source, field_name)


def _optional_field(
    source: object,
    field_name: str,
) -> object | None:
    if isinstance(source, Mapping):
        return source.get(field_name)

    return getattr(source, field_name, None)


def _required_first_field(
    source: object,
    field_names: tuple[str, ...],
) -> object:
    for field_name in field_names:
        value = _optional_field(
            source,
            field_name,
        )

        if value is not None:
            return value

    names = ", ".join(field_names)

    raise ValueError(f"Broker exposure requires one of these fields: {names}.")


def _position_side(value: object) -> TradeSide:
    position_type = _non_negative_integer(
        value,
        "position type",
    )

    if position_type == 0:
        return TradeSide.BUY

    if position_type == 1:
        return TradeSide.SELL

    raise ValueError(f"Unsupported MT5 position type: {position_type}.")


def _pending_order_type(
    value: object,
) -> tuple[TradeSide, EntryType]:
    order_type = _non_negative_integer(
        value,
        "order type",
    )

    order_types: dict[int, tuple[TradeSide, EntryType]] = {
        2: (TradeSide.BUY, EntryType.LIMIT),
        3: (TradeSide.SELL, EntryType.LIMIT),
        4: (TradeSide.BUY, EntryType.STOP),
        5: (TradeSide.SELL, EntryType.STOP),
    }

    try:
        return order_types[order_type]
    except KeyError as error:
        raise ValueError(f"Unsupported active MT5 order type: {order_type}.") from error


@dataclass(frozen=True, slots=True)
class BrokerPositionSnapshot:
    """Immutable read-only representation of an MT5 position."""

    ticket: int
    broker_symbol: str
    side: TradeSide
    volume: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    unrealized_pnl: Decimal
    magic_number: int
    opened_at: datetime
    observed_at: datetime
    comment: str | None = None

    def __post_init__(self) -> None:
        ticket = _positive_integer(
            self.ticket,
            "ticket",
        )
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
            maximum_length=64,
        )

        try:
            side = TradeSide(self.side)
        except ValueError as error:
            raise ValueError(f"Unsupported position side: {self.side}.") from error

        volume = _positive_decimal(
            self.volume,
            "volume",
        )
        entry_price = _positive_decimal(
            self.entry_price,
            "entry_price",
        )
        current_price = _positive_decimal(
            self.current_price,
            "current_price",
        )
        stop_loss = _optional_positive_price(
            self.stop_loss,
            "stop_loss",
        )
        take_profit = _optional_positive_price(
            self.take_profit,
            "take_profit",
        )
        unrealized_pnl = _finite_decimal(
            self.unrealized_pnl,
            "unrealized_pnl",
        )
        magic_number = _non_negative_integer(
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
        comment = _optional_text(
            self.comment,
            "comment",
        )

        if observed_at < opened_at:
            raise ValueError("observed_at cannot be earlier than opened_at.")

        object.__setattr__(self, "ticket", ticket)
        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(
            self,
            "entry_price",
            entry_price,
        )
        object.__setattr__(
            self,
            "current_price",
            current_price,
        )
        object.__setattr__(
            self,
            "stop_loss",
            stop_loss,
        )
        object.__setattr__(
            self,
            "take_profit",
            take_profit,
        )
        object.__setattr__(
            self,
            "unrealized_pnl",
            unrealized_pnl,
        )
        object.__setattr__(
            self,
            "magic_number",
            magic_number,
        )
        object.__setattr__(
            self,
            "opened_at",
            opened_at,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )
        object.__setattr__(self, "comment", comment)

    @property
    def has_stop_loss(self) -> bool:
        return self.stop_loss is not None

    @property
    def has_take_profit(self) -> bool:
        return self.take_profit is not None

    @property
    def price_move(self) -> Decimal:
        if self.side == TradeSide.BUY:
            return self.current_price - self.entry_price

        return self.entry_price - self.current_price


@dataclass(frozen=True, slots=True)
class BrokerPendingOrderSnapshot:
    """Immutable read-only representation of an active MT5 order."""

    ticket: int
    broker_symbol: str
    side: TradeSide
    entry_type: EntryType
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    magic_number: int
    created_at: datetime
    observed_at: datetime
    comment: str | None = None

    def __post_init__(self) -> None:
        ticket = _positive_integer(
            self.ticket,
            "ticket",
        )
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
            maximum_length=64,
        )

        try:
            side = TradeSide(self.side)
        except ValueError as error:
            raise ValueError(f"Unsupported order side: {self.side}.") from error

        try:
            entry_type = EntryType(self.entry_type)
        except ValueError as error:
            raise ValueError(f"Unsupported entry type: {self.entry_type}.") from error

        if entry_type == EntryType.MARKET:
            raise ValueError("Active pending orders cannot use MARKET.")

        volume = _positive_decimal(
            self.volume,
            "volume",
        )
        entry_price = _positive_decimal(
            self.entry_price,
            "entry_price",
        )
        stop_loss = _optional_positive_price(
            self.stop_loss,
            "stop_loss",
        )
        take_profit = _optional_positive_price(
            self.take_profit,
            "take_profit",
        )
        magic_number = _non_negative_integer(
            self.magic_number,
            "magic_number",
        )
        created_at = _utc_datetime(
            self.created_at,
            "created_at",
        )
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )
        comment = _optional_text(
            self.comment,
            "comment",
        )

        if observed_at < created_at:
            raise ValueError("observed_at cannot be earlier than created_at.")

        object.__setattr__(self, "ticket", ticket)
        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(self, "side", side)
        object.__setattr__(
            self,
            "entry_type",
            entry_type,
        )
        object.__setattr__(self, "volume", volume)
        object.__setattr__(
            self,
            "entry_price",
            entry_price,
        )
        object.__setattr__(
            self,
            "stop_loss",
            stop_loss,
        )
        object.__setattr__(
            self,
            "take_profit",
            take_profit,
        )
        object.__setattr__(
            self,
            "magic_number",
            magic_number,
        )
        object.__setattr__(
            self,
            "created_at",
            created_at,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )
        object.__setattr__(self, "comment", comment)

    @property
    def has_stop_loss(self) -> bool:
        return self.stop_loss is not None

    @property
    def has_take_profit(self) -> bool:
        return self.take_profit is not None


@dataclass(frozen=True, slots=True)
class BrokerGoldExposureSnapshot:
    """Combined broker-side Gold exposure for reconciliation."""

    broker_symbol: str
    positions: tuple[BrokerPositionSnapshot, ...]
    pending_orders: tuple[BrokerPendingOrderSnapshot, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
            maximum_length=64,
        )
        positions = tuple(self.positions)
        pending_orders = tuple(self.pending_orders)
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )

        for position in positions:
            if not isinstance(
                position,
                BrokerPositionSnapshot,
            ):
                raise ValueError("positions must contain BrokerPositionSnapshot instances.")

            if position.broker_symbol != broker_symbol:
                raise ValueError("Position symbol does not match snapshot symbol.")

        for order in pending_orders:
            if not isinstance(
                order,
                BrokerPendingOrderSnapshot,
            ):
                raise ValueError(
                    "pending_orders must contain BrokerPendingOrderSnapshot instances."
                )

            if order.broker_symbol != broker_symbol:
                raise ValueError("Order symbol does not match snapshot symbol.")

        tickets = [item.ticket for item in (*positions, *pending_orders)]

        if len(tickets) != len(set(tickets)):
            raise ValueError("Duplicate broker tickets are not allowed.")

        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "positions",
            positions,
        )
        object.__setattr__(
            self,
            "pending_orders",
            pending_orders,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )

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
    def safety_issues(
        self,
    ) -> tuple[BrokerExposureSafetyIssue, ...]:
        issues: list[BrokerExposureSafetyIssue] = []

        if len(self.positions) > 1:
            issues.append(BrokerExposureSafetyIssue.MULTIPLE_OPEN_POSITIONS)

        if self.positions and self.pending_orders:
            issues.append(BrokerExposureSafetyIssue.POSITION_AND_PENDING_ORDERS)

        if any(not position.has_stop_loss for position in self.positions):
            issues.append(BrokerExposureSafetyIssue.POSITION_WITHOUT_STOP_LOSS)

        if any(not position.has_take_profit for position in self.positions):
            issues.append(BrokerExposureSafetyIssue.POSITION_WITHOUT_TAKE_PROFIT)

        if any(not order.has_stop_loss for order in self.pending_orders):
            issues.append(BrokerExposureSafetyIssue.PENDING_ORDER_WITHOUT_STOP_LOSS)

        if any(not order.has_take_profit for order in self.pending_orders):
            issues.append(BrokerExposureSafetyIssue.PENDING_ORDER_WITHOUT_TAKE_PROFIT)

        return tuple(issues)

    @property
    def safe_for_new_entry(self) -> bool:
        return not self.has_active_exposure and not self.safety_issues

    @property
    def reconciliation_required(self) -> bool:
        return self.has_active_exposure or bool(self.safety_issues)


class BrokerExposureService:
    """
    Read-only MT5 Gold exposure mapper.

    This service cannot submit, modify, cancel, or close trades.
    """

    def __init__(
        self,
        mt5_client: BrokerExposureClient,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            mt5_client,
            BrokerExposureClient,
        ):
            raise ValueError("mt5_client must implement the BrokerExposureClient protocol.")

        if not callable(clock):
            raise ValueError("clock must be callable.")

        self._mt5 = mt5_client
        self._clock = clock

    def read_snapshot(
        self,
        *,
        broker_symbol: str,
    ) -> BrokerGoldExposureSnapshot:
        symbol = _required_text(
            broker_symbol,
            "broker_symbol",
            maximum_length=64,
        )

        if not self._mt5.initialized:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.CONNECTION_REQUIRED,
                "MT5 must be initialized before reading broker exposure.",
            )

        try:
            raw_positions = self._mt5.positions_get(symbol=symbol)
        except MT5ConnectionError as error:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.POSITIONS_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.POSITIONS_READ_FAILED,
                f"Reading MT5 positions raised {type(error).__name__}: {error}",
            ) from error

        if raw_positions is None:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.POSITIONS_UNAVAILABLE,
                "MT5 returned no positions result.",
            )

        try:
            raw_orders = self._mt5.orders_get(symbol=symbol)
        except MT5ConnectionError as error:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.ORDERS_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.ORDERS_READ_FAILED,
                f"Reading MT5 active orders raised {type(error).__name__}: {error}",
            ) from error

        if raw_orders is None:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.ORDERS_UNAVAILABLE,
                "MT5 returned no active-orders result.",
            )

        try:
            observed_at = _utc_datetime(
                self._clock(),
                "clock result",
            )
        except Exception as error:
            raise BrokerExposureServiceError(
                BrokerExposureErrorReason.INVALID_CLOCK,
                str(error),
            ) from error

        positions: list[BrokerPositionSnapshot] = []

        for raw_position in raw_positions:
            try:
                positions.append(
                    self._map_position(
                        raw_position,
                        broker_symbol=symbol,
                        observed_at=observed_at,
                    )
                )
            except ValueError as error:
                reason = (
                    BrokerExposureErrorReason.UNSUPPORTED_POSITION_TYPE
                    if "Unsupported MT5 position type" in str(error)
                    else BrokerExposureErrorReason.INVALID_POSITION_DATA
                )

                raise BrokerExposureServiceError(
                    reason,
                    str(error),
                ) from error

        pending_orders: list[BrokerPendingOrderSnapshot] = []

        for raw_order in raw_orders:
            try:
                pending_orders.append(
                    self._map_pending_order(
                        raw_order,
                        broker_symbol=symbol,
                        observed_at=observed_at,
                    )
                )
            except ValueError as error:
                reason = (
                    BrokerExposureErrorReason.UNSUPPORTED_ORDER_TYPE
                    if "Unsupported active MT5 order type" in str(error)
                    else BrokerExposureErrorReason.INVALID_ORDER_DATA
                )

                raise BrokerExposureServiceError(
                    reason,
                    str(error),
                ) from error

        try:
            return BrokerGoldExposureSnapshot(
                broker_symbol=symbol,
                positions=tuple(positions),
                pending_orders=tuple(pending_orders),
                observed_at=observed_at,
            )
        except ValueError as error:
            reason = (
                BrokerExposureErrorReason.DUPLICATE_TICKET
                if "Duplicate broker tickets" in str(error)
                else BrokerExposureErrorReason.INVALID_POSITION_DATA
            )

            raise BrokerExposureServiceError(
                reason,
                str(error),
            ) from error

    @staticmethod
    def _map_position(
        raw_position: object,
        *,
        broker_symbol: str,
        observed_at: datetime,
    ) -> BrokerPositionSnapshot:
        raw_symbol = _required_text(
            _required_field(
                raw_position,
                "symbol",
            ),
            "position symbol",
            maximum_length=64,
        )

        if raw_symbol != broker_symbol:
            raise ValueError("Position symbol does not match the requested broker symbol.")

        return BrokerPositionSnapshot(
            ticket=_required_field(
                raw_position,
                "ticket",
            ),
            broker_symbol=raw_symbol,
            side=_position_side(
                _required_field(
                    raw_position,
                    "type",
                )
            ),
            volume=_required_field(
                raw_position,
                "volume",
            ),
            entry_price=_required_field(
                raw_position,
                "price_open",
            ),
            current_price=_required_field(
                raw_position,
                "price_current",
            ),
            stop_loss=_optional_field(
                raw_position,
                "sl",
            ),
            take_profit=_optional_field(
                raw_position,
                "tp",
            ),
            unrealized_pnl=_required_field(
                raw_position,
                "profit",
            ),
            magic_number=_required_field(
                raw_position,
                "magic",
            ),
            opened_at=_epoch_to_utc(
                _required_field(
                    raw_position,
                    "time",
                ),
                "position time",
            ),
            observed_at=observed_at,
            comment=_optional_field(
                raw_position,
                "comment",
            ),
        )

    @staticmethod
    def _map_pending_order(
        raw_order: object,
        *,
        broker_symbol: str,
        observed_at: datetime,
    ) -> BrokerPendingOrderSnapshot:
        raw_symbol = _required_text(
            _required_field(
                raw_order,
                "symbol",
            ),
            "order symbol",
            maximum_length=64,
        )

        if raw_symbol != broker_symbol:
            raise ValueError("Order symbol does not match the requested broker symbol.")

        side, entry_type = _pending_order_type(
            _required_field(
                raw_order,
                "type",
            )
        )

        return BrokerPendingOrderSnapshot(
            ticket=_required_field(
                raw_order,
                "ticket",
            ),
            broker_symbol=raw_symbol,
            side=side,
            entry_type=entry_type,
            volume=_required_first_field(
                raw_order,
                (
                    "volume_current",
                    "volume_initial",
                ),
            ),
            entry_price=_required_field(
                raw_order,
                "price_open",
            ),
            stop_loss=_optional_field(
                raw_order,
                "sl",
            ),
            take_profit=_optional_field(
                raw_order,
                "tp",
            ),
            magic_number=_required_field(
                raw_order,
                "magic",
            ),
            created_at=_epoch_to_utc(
                _required_field(
                    raw_order,
                    "time_setup",
                ),
                "order setup time",
            ),
            observed_at=observed_at,
            comment=_optional_field(
                raw_order,
                "comment",
            ),
        )
