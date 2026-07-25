from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from loguru import logger

from app.broker.mt5_client import MT5ConnectionError
from app.config.constants import DEFAULT_GOLD_SYMBOL_CANDIDATES
from app.domain.sizing import GoldSymbolSpecification
from app.domain.trading import CANONICAL_GOLD_SYMBOL


class SymbolServiceErrorReason(str, Enum):
    CONNECTION_REQUIRED = "CONNECTION_REQUIRED"
    SYMBOL_LIST_UNAVAILABLE = "SYMBOL_LIST_UNAVAILABLE"
    NO_GOLD_SYMBOL_FOUND = "NO_GOLD_SYMBOL_FOUND"
    SYMBOL_INFO_UNAVAILABLE = "SYMBOL_INFO_UNAVAILABLE"
    TICK_INFO_UNAVAILABLE = "TICK_INFO_UNAVAILABLE"
    SYMBOL_SELECTION_FAILED = "SYMBOL_SELECTION_FAILED"
    SYMBOL_READ_FAILED = "SYMBOL_READ_FAILED"
    INVALID_SYMBOL_DATA = "INVALID_SYMBOL_DATA"
    INVALID_CLOCK = "INVALID_CLOCK"


class SymbolServiceError(RuntimeError):
    """Structured read-only symbol-service failure."""

    def __init__(
        self,
        reason: SymbolServiceErrorReason,
        message: str,
    ) -> None:
        self.reason = SymbolServiceErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Symbol service error [{self.reason.value}]: {self.message}")


@runtime_checkable
class SymbolInfoClient(Protocol):
    """Read-only MT5 client contract used by SymbolService."""

    @property
    def initialized(self) -> bool: ...

    def symbols_get(self) -> Any: ...

    def symbol_info(self, symbol: str) -> Any: ...

    def symbol_info_tick(self, symbol: str) -> Any: ...

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool: ...


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
    maximum_length: int = 256,
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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    raise ValueError(f"{field_name} must be a boolean or broker flag 0/1.")


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _required_field(
    source: object,
    field_name: str,
) -> object:
    if isinstance(source, Mapping):
        if field_name not in source:
            raise ValueError(f"Broker symbol field is missing: {field_name}.")

        return source[field_name]

    if not hasattr(source, field_name):
        raise ValueError(f"Broker symbol field is missing: {field_name}.")

    return getattr(source, field_name)


def _optional_field(
    source: object,
    field_name: str,
) -> object | None:
    if isinstance(source, Mapping):
        return source.get(field_name)

    return getattr(source, field_name, None)


def _symbol_name(source: object) -> str:
    return _required_text(
        _required_field(source, "name"),
        "symbol name",
        maximum_length=64,
    )


def _conservative_tick_value(
    symbol_info: object,
) -> Decimal:
    values: list[Decimal] = []

    for field_name in (
        "trade_tick_value_loss",
        "trade_tick_value",
        "trade_tick_value_profit",
    ):
        raw_value = _optional_field(
            symbol_info,
            field_name,
        )

        if raw_value is None:
            continue

        decimal_value = _finite_decimal(
            raw_value,
            field_name,
        )

        if decimal_value > 0:
            values.append(decimal_value)

    if not values:
        raise ValueError("No positive broker tick value is available.")

    # Selecting the largest available tick value prevents
    # position sizing from understating potential loss.
    return max(values)


@dataclass(frozen=True, slots=True)
class BrokerGoldSymbolSnapshot:
    """Validated broker-specific Gold symbol state."""

    broker_symbol: str
    specification: GoldSymbolSpecification
    bid: Decimal
    ask: Decimal
    point: Decimal
    digits: int
    visible: bool
    observed_at: datetime
    description: str | None = None
    path: str | None = None

    def __post_init__(self) -> None:
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
            maximum_length=64,
        )

        if not isinstance(
            self.specification,
            GoldSymbolSpecification,
        ):
            raise ValueError("specification must be a GoldSymbolSpecification instance.")

        if self.specification.symbol != CANONICAL_GOLD_SYMBOL:
            raise ValueError("specification must represent canonical XAUUSD.")

        bid = _positive_decimal(self.bid, "bid")
        ask = _positive_decimal(self.ask, "ask")
        point = _positive_decimal(self.point, "point")
        digits = _non_negative_integer(
            self.digits,
            "digits",
        )
        visible = _strict_boolean(
            self.visible,
            "visible",
        )
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )
        description = _optional_text(
            self.description,
            "description",
        )
        path = _optional_text(
            self.path,
            "path",
        )

        if digits > 12:
            raise ValueError("digits cannot exceed 12.")

        if ask < bid:
            raise ValueError("ask cannot be below bid.")

        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)
        object.__setattr__(self, "point", point)
        object.__setattr__(self, "digits", digits)
        object.__setattr__(self, "visible", visible)
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )
        object.__setattr__(
            self,
            "description",
            description,
        )
        object.__setattr__(self, "path", path)

    @property
    def canonical_symbol(self) -> str:
        return CANONICAL_GOLD_SYMBOL

    @property
    def raw_spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def spread_points(self) -> Decimal:
        return self.raw_spread / self.point

    @property
    def midpoint(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    def spread_within(
        self,
        maximum_points: object,
    ) -> bool:
        maximum = _finite_decimal(
            maximum_points,
            "maximum_points",
        )

        if maximum < 0:
            raise ValueError("maximum_points cannot be negative.")

        return self.spread_points <= maximum


class SymbolService:
    """
    Read-only broker Gold symbol resolver.

    This service never initializes MT5 and contains no order,
    position, or trade-modification methods.
    """

    def __init__(
        self,
        mt5_client: SymbolInfoClient,
        candidates: Iterable[str] | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            mt5_client,
            SymbolInfoClient,
        ):
            raise ValueError("mt5_client must implement the SymbolInfoClient protocol.")

        if not callable(clock):
            raise ValueError("clock must be callable.")

        selected_candidates = DEFAULT_GOLD_SYMBOL_CANDIDATES if candidates is None else candidates

        normalized_candidates: list[str] = []
        seen: set[str] = set()

        for raw_candidate in selected_candidates:
            candidate = _required_text(
                raw_candidate,
                "symbol candidate",
                maximum_length=64,
            )

            comparison_key = candidate.upper()

            if comparison_key in seen:
                continue

            seen.add(comparison_key)
            normalized_candidates.append(candidate)

        if not normalized_candidates:
            raise ValueError("At least one Gold symbol candidate is required.")

        self._mt5 = mt5_client
        self._candidates = tuple(normalized_candidates)
        self._clock = clock

    @property
    def candidates(self) -> tuple[str, ...]:
        return self._candidates

    def resolve_symbol(self) -> str:
        """Resolve the first available broker Gold symbol."""

        self._require_connection()

        try:
            raw_symbols = self._mt5.symbols_get()
        except MT5ConnectionError as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_READ_FAILED,
                f"Reading the MT5 symbol list raised {type(error).__name__}: {error}",
            ) from error

        if raw_symbols is None:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_LIST_UNAVAILABLE,
                "MT5 returned no symbol list.",
            )

        try:
            names = tuple(_symbol_name(raw_symbol) for raw_symbol in raw_symbols)
        except (TypeError, ValueError) as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.INVALID_SYMBOL_DATA,
                str(error),
            ) from error

        if not names:
            raise SymbolServiceError(
                SymbolServiceErrorReason.NO_GOLD_SYMBOL_FOUND,
                "The broker symbol list is empty.",
            )

        exact_names = set(names)
        case_insensitive_names: dict[str, str] = {}

        for name in names:
            case_insensitive_names.setdefault(
                name.upper(),
                name,
            )

        for candidate in self._candidates:
            if candidate in exact_names:
                return candidate

            matched_name = case_insensitive_names.get(candidate.upper())

            if matched_name is not None:
                return matched_name

        candidates_text = ", ".join(self._candidates)

        raise SymbolServiceError(
            SymbolServiceErrorReason.NO_GOLD_SYMBOL_FOUND,
            f"No configured Gold symbol was found. Candidates: {candidates_text}.",
        )

    def find_gold_symbol(self) -> str:
        """Backward-compatible Gold symbol resolver."""

        return self.resolve_symbol()

    def get_symbol_info(
        self,
        symbol: str | None = None,
    ) -> Any:
        """Return raw broker symbol information."""

        self._require_connection()

        selected_symbol = (
            self.resolve_symbol()
            if symbol is None
            else _required_text(
                symbol,
                "symbol",
                maximum_length=64,
            )
        )

        return self._read_symbol_info(selected_symbol)

    def read_snapshot(
        self,
        *,
        account_currency: str,
    ) -> BrokerGoldSymbolSnapshot:
        """Resolve and map the current Gold symbol state."""

        self._require_connection()

        normalized_currency = _required_text(
            account_currency,
            "account_currency",
            maximum_length=12,
        ).upper()

        broker_symbol = self.resolve_symbol()
        raw_info = self._read_symbol_info(broker_symbol)

        try:
            visible = _strict_boolean(
                _required_field(raw_info, "visible"),
                "visible",
            )
        except (TypeError, ValueError) as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.INVALID_SYMBOL_DATA,
                str(error),
            ) from error

        if not visible:
            try:
                selected = self._mt5.symbol_select(
                    broker_symbol,
                    True,
                )
            except MT5ConnectionError as error:
                raise SymbolServiceError(
                    SymbolServiceErrorReason.SYMBOL_SELECTION_FAILED,
                    str(error),
                ) from error
            except Exception as error:
                raise SymbolServiceError(
                    SymbolServiceErrorReason.SYMBOL_SELECTION_FAILED,
                    f"Selecting the Gold symbol raised {type(error).__name__}: {error}",
                ) from error

            if not selected:
                raise SymbolServiceError(
                    SymbolServiceErrorReason.SYMBOL_SELECTION_FAILED,
                    f"MT5 rejected Market Watch selection for {broker_symbol}.",
                )

            raw_info = self._read_symbol_info(broker_symbol)

            try:
                visible = _strict_boolean(
                    _required_field(
                        raw_info,
                        "visible",
                    ),
                    "visible",
                )
            except (TypeError, ValueError) as error:
                raise SymbolServiceError(
                    SymbolServiceErrorReason.INVALID_SYMBOL_DATA,
                    str(error),
                ) from error

            if not visible:
                raise SymbolServiceError(
                    SymbolServiceErrorReason.SYMBOL_SELECTION_FAILED,
                    f"{broker_symbol} remained invisible after selection.",
                )

        raw_tick = self._read_tick(broker_symbol)

        try:
            observed_at = _utc_datetime(
                self._clock(),
                "clock result",
            )
        except Exception as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.INVALID_CLOCK,
                str(error),
            ) from error

        try:
            point = _positive_decimal(
                _required_field(raw_info, "point"),
                "point",
            )
            tick_size = _positive_decimal(
                _required_field(
                    raw_info,
                    "trade_tick_size",
                ),
                "trade_tick_size",
            )
            tick_value = _conservative_tick_value(raw_info)

            specification = GoldSymbolSpecification(
                symbol=CANONICAL_GOLD_SYMBOL,
                account_currency=normalized_currency,
                tick_size=tick_size,
                tick_value_per_lot=tick_value,
                volume_min=_required_field(
                    raw_info,
                    "volume_min",
                ),
                volume_max=_required_field(
                    raw_info,
                    "volume_max",
                ),
                volume_step=_required_field(
                    raw_info,
                    "volume_step",
                ),
            )

            return BrokerGoldSymbolSnapshot(
                broker_symbol=broker_symbol,
                specification=specification,
                bid=_required_field(raw_tick, "bid"),
                ask=_required_field(raw_tick, "ask"),
                point=point,
                digits=_required_field(
                    raw_info,
                    "digits",
                ),
                visible=visible,
                observed_at=observed_at,
                description=_optional_field(
                    raw_info,
                    "description",
                ),
                path=_optional_field(
                    raw_info,
                    "path",
                ),
            )
        except (TypeError, ValueError) as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.INVALID_SYMBOL_DATA,
                str(error),
            ) from error

    def log_symbol_info(
        self,
        *,
        account_currency: str,
    ) -> None:
        snapshot = self.read_snapshot(account_currency=account_currency)

        logger.info("========== GOLD SYMBOL INFO ==========")
        logger.info(
            "Canonical Symbol: {}",
            snapshot.canonical_symbol,
        )
        logger.info(
            "Broker Symbol: {}",
            snapshot.broker_symbol,
        )
        logger.info("Bid: {}", snapshot.bid)
        logger.info("Ask: {}", snapshot.ask)
        logger.info(
            "Spread Points: {}",
            snapshot.spread_points,
        )
        logger.info(
            "Tick Size: {}",
            snapshot.specification.tick_size,
        )
        logger.info(
            "Tick Value Per Lot: {}",
            snapshot.specification.tick_value_per_lot,
        )
        logger.info(
            "Volume Min: {}",
            snapshot.specification.volume_min,
        )
        logger.info(
            "Volume Max: {}",
            snapshot.specification.volume_max,
        )
        logger.info(
            "Volume Step: {}",
            snapshot.specification.volume_step,
        )

    def _require_connection(self) -> None:
        if self._mt5.initialized:
            return

        raise SymbolServiceError(
            SymbolServiceErrorReason.CONNECTION_REQUIRED,
            "MT5 must be initialized before reading symbols.",
        )

    def _read_symbol_info(
        self,
        symbol: str,
    ) -> Any:
        try:
            raw_info = self._mt5.symbol_info(symbol)
        except MT5ConnectionError as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_READ_FAILED,
                f"Reading symbol information raised {type(error).__name__}: {error}",
            ) from error

        if raw_info is None:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_INFO_UNAVAILABLE,
                f"MT5 returned no information for {symbol}.",
            )

        return raw_info

    def _read_tick(
        self,
        symbol: str,
    ) -> Any:
        try:
            raw_tick = self._mt5.symbol_info_tick(symbol)
        except MT5ConnectionError as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise SymbolServiceError(
                SymbolServiceErrorReason.SYMBOL_READ_FAILED,
                f"Reading symbol tick raised {type(error).__name__}: {error}",
            ) from error

        if raw_tick is None:
            raise SymbolServiceError(
                SymbolServiceErrorReason.TICK_INFO_UNAVAILABLE,
                f"MT5 returned no tick for {symbol}.",
            )

        return raw_tick


GoldSymbolService = SymbolService
