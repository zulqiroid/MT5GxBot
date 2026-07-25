from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from loguru import logger

from app.broker.mt5_client import MT5ConnectionError
from app.domain.exposure import AccountSnapshot


class AccountServiceErrorReason(str, Enum):
    CONNECTION_REQUIRED = "CONNECTION_REQUIRED"
    ACCOUNT_INFO_UNAVAILABLE = "ACCOUNT_INFO_UNAVAILABLE"
    ACCOUNT_INFO_READ_FAILED = "ACCOUNT_INFO_READ_FAILED"
    INVALID_ACCOUNT_DATA = "INVALID_ACCOUNT_DATA"
    INVALID_CLOCK = "INVALID_CLOCK"


class AccountReadinessReason(str, Enum):
    ACCOUNT_TRADING_DISABLED = "ACCOUNT_TRADING_DISABLED"
    EXPERT_TRADING_DISABLED = "EXPERT_TRADING_DISABLED"


class AccountServiceError(RuntimeError):
    """Structured account-service failure."""

    def __init__(
        self,
        reason: AccountServiceErrorReason,
        message: str,
    ) -> None:
        self.reason = AccountServiceErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Account service error [{self.reason.value}]: {self.message}")


@runtime_checkable
class AccountInfoClient(Protocol):
    """Read-only client contract required by AccountService."""

    @property
    def initialized(self) -> bool: ...

    def account_info(self) -> Any: ...

    def terminal_info(self) -> Any: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    raise ValueError(f"{field_name} must be a boolean or broker flag 0/1.")


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
            raise ValueError(f"Broker account field is missing: {field_name}.")

        return source[field_name]

    if not hasattr(source, field_name):
        raise ValueError(f"Broker account field is missing: {field_name}.")

    return getattr(source, field_name)


def _optional_field(
    source: object,
    field_name: str,
) -> object | None:
    if isinstance(source, Mapping):
        return source.get(field_name)

    return getattr(source, field_name, None)


@dataclass(frozen=True, slots=True)
class BrokerAccountSnapshot:
    """Validated broker account state and automation permissions."""

    account: AccountSnapshot
    leverage: int
    trade_allowed: bool
    expert_trading_allowed: bool
    account_name: str | None = None
    company: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.account, AccountSnapshot):
            raise ValueError("account must be an AccountSnapshot instance.")

        leverage = _positive_integer(
            self.leverage,
            "leverage",
        )
        trade_allowed = _strict_boolean(
            self.trade_allowed,
            "trade_allowed",
        )
        expert_trading_allowed = _strict_boolean(
            self.expert_trading_allowed,
            "expert_trading_allowed",
        )
        account_name = _optional_text(
            self.account_name,
            "account_name",
        )
        company = _optional_text(
            self.company,
            "company",
        )

        object.__setattr__(self, "leverage", leverage)
        object.__setattr__(
            self,
            "trade_allowed",
            trade_allowed,
        )
        object.__setattr__(
            self,
            "expert_trading_allowed",
            expert_trading_allowed,
        )
        object.__setattr__(
            self,
            "account_name",
            account_name,
        )
        object.__setattr__(self, "company", company)

    @property
    def readiness_reasons(
        self,
    ) -> tuple[AccountReadinessReason, ...]:
        reasons: list[AccountReadinessReason] = []

        if not self.trade_allowed:
            reasons.append(AccountReadinessReason.ACCOUNT_TRADING_DISABLED)

        if not self.expert_trading_allowed:
            reasons.append(AccountReadinessReason.EXPERT_TRADING_DISABLED)

        return tuple(reasons)

    @property
    def automated_trading_ready(self) -> bool:
        return not self.readiness_reasons


class AccountService:
    """
    Read-only MT5 account service.

    This service:
    - does not initialize MT5;
    - does not place, modify, or close orders;
    - maps raw account data into immutable domain models.
    """

    def __init__(
        self,
        mt5_client: AccountInfoClient,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(mt5_client, AccountInfoClient):
            raise ValueError("mt5_client must implement the AccountInfoClient protocol.")

        if not callable(clock):
            raise ValueError("clock must be callable.")

        self._mt5 = mt5_client
        self._clock = clock

    def get_terminal_info(self) -> Any:
        """Compatibility method for terminal diagnostics."""

        return self._mt5.terminal_info()

    def get_account_info(self) -> Any:
        """Compatibility method returning raw account information."""

        return self._mt5.account_info()

    def read_snapshot(self) -> BrokerAccountSnapshot:
        """Read and validate the current broker account state."""

        if not self._mt5.initialized:
            raise AccountServiceError(
                AccountServiceErrorReason.CONNECTION_REQUIRED,
                "MT5 must be initialized before reading the broker account.",
            )

        try:
            raw_account = self._mt5.account_info()
        except MT5ConnectionError as error:
            raise AccountServiceError(
                AccountServiceErrorReason.ACCOUNT_INFO_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise AccountServiceError(
                AccountServiceErrorReason.ACCOUNT_INFO_READ_FAILED,
                f"Reading MT5 account information raised {type(error).__name__}: {error}",
            ) from error

        if raw_account is None:
            raise AccountServiceError(
                AccountServiceErrorReason.ACCOUNT_INFO_UNAVAILABLE,
                "MT5 returned no account information.",
            )

        try:
            observed_at = _utc_datetime(
                self._clock(),
                "clock result",
            )
        except Exception as error:
            raise AccountServiceError(
                AccountServiceErrorReason.INVALID_CLOCK,
                str(error),
            ) from error

        try:
            account = AccountSnapshot(
                login=_required_field(
                    raw_account,
                    "login",
                ),
                server=_required_field(
                    raw_account,
                    "server",
                ),
                currency=_required_field(
                    raw_account,
                    "currency",
                ),
                balance=_required_field(
                    raw_account,
                    "balance",
                ),
                equity=_required_field(
                    raw_account,
                    "equity",
                ),
                margin=_required_field(
                    raw_account,
                    "margin",
                ),
                free_margin=_required_field(
                    raw_account,
                    "margin_free",
                ),
                observed_at=observed_at,
            )

            return BrokerAccountSnapshot(
                account=account,
                leverage=_positive_integer(
                    _required_field(
                        raw_account,
                        "leverage",
                    ),
                    "leverage",
                ),
                trade_allowed=_strict_boolean(
                    _required_field(
                        raw_account,
                        "trade_allowed",
                    ),
                    "trade_allowed",
                ),
                expert_trading_allowed=_strict_boolean(
                    _required_field(
                        raw_account,
                        "trade_expert",
                    ),
                    "trade_expert",
                ),
                account_name=_optional_field(
                    raw_account,
                    "name",
                ),
                company=_optional_field(
                    raw_account,
                    "company",
                ),
            )
        except (TypeError, ValueError) as error:
            raise AccountServiceError(
                AccountServiceErrorReason.INVALID_ACCOUNT_DATA,
                str(error),
            ) from error

    def get_account_snapshot(self) -> AccountSnapshot:
        """Return only the core domain account snapshot."""

        return self.read_snapshot().account

    def log_terminal_info(self) -> None:
        terminal_info = self.get_terminal_info()

        if terminal_info is None:
            logger.warning("MT5 terminal information is unavailable.")
            return

        logger.info("========== TERMINAL INFO ==========")
        logger.info(
            "Connected: {}",
            getattr(terminal_info, "connected", None),
        )
        logger.info(
            "Trade Allowed: {}",
            getattr(terminal_info, "trade_allowed", None),
        )
        logger.info(
            "Company: {}",
            getattr(terminal_info, "company", None),
        )
        logger.info(
            "Name: {}",
            getattr(terminal_info, "name", None),
        )
        logger.info(
            "Path: {}",
            getattr(terminal_info, "path", None),
        )

    def log_account_info(self) -> None:
        snapshot = self.read_snapshot()
        account = snapshot.account

        logger.info("========== ACCOUNT INFO ==========")
        logger.info("Login: {}", account.login)
        logger.info("Server: {}", account.server)
        logger.info("Currency: {}", account.currency)
        logger.info("Balance: {}", account.balance)
        logger.info("Equity: {}", account.equity)
        logger.info("Margin: {}", account.margin)
        logger.info("Margin Free: {}", account.free_margin)
        logger.info("Leverage: 1:{}", snapshot.leverage)
        logger.info(
            "Account Trade Allowed: {}",
            snapshot.trade_allowed,
        )
        logger.info(
            "Expert Trading Allowed: {}",
            snapshot.expert_trading_allowed,
        )
        logger.info(
            "Automated Trading Ready: {}",
            snapshot.automated_trading_ready,
        )
