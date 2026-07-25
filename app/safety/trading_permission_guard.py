from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Protocol, runtime_checkable

from app.broker.account_service import (
    AccountServiceError,
    BrokerAccountSnapshot,
)
from app.broker.exposure_service import (
    BrokerExposureServiceError,
    BrokerGoldExposureSnapshot,
)
from app.broker.mt5_client import MT5ConnectionSnapshot
from app.broker.symbol_service import (
    BrokerGoldSymbolSnapshot,
    SymbolServiceError,
)
from app.config.constants import BotMode
from app.config.settings import Settings


class TradingPermissionIssue(str, Enum):
    READ_ONLY_MODE = "READ_ONLY_MODE"
    LIVE_TRADING_NOT_ARMED = "LIVE_TRADING_NOT_ARMED"

    CONNECTION_SNAPSHOT_FAILED = "CONNECTION_SNAPSHOT_FAILED"
    CONNECTION_SNAPSHOT_INVALID = "CONNECTION_SNAPSHOT_INVALID"
    MT5_NOT_INITIALIZED = "MT5_NOT_INITIALIZED"
    TERMINAL_UNAVAILABLE = "TERMINAL_UNAVAILABLE"
    TERMINAL_DISCONNECTED = "TERMINAL_DISCONNECTED"
    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"

    ACCOUNT_SERVICE_FAILED = "ACCOUNT_SERVICE_FAILED"
    ACCOUNT_TRADING_DISABLED = "ACCOUNT_TRADING_DISABLED"
    EXPERT_TRADING_DISABLED = "EXPERT_TRADING_DISABLED"

    SYMBOL_SERVICE_FAILED = "SYMBOL_SERVICE_FAILED"
    SPREAD_LIMIT_EXCEEDED = "SPREAD_LIMIT_EXCEEDED"

    EXPOSURE_SERVICE_FAILED = "EXPOSURE_SERVICE_FAILED"
    BROKER_EXPOSURE_ACTIVE = "BROKER_EXPOSURE_ACTIVE"
    BROKER_EXPOSURE_UNSAFE = "BROKER_EXPOSURE_UNSAFE"


INFRASTRUCTURE_ISSUES = frozenset(
    {
        TradingPermissionIssue.CONNECTION_SNAPSHOT_FAILED,
        TradingPermissionIssue.CONNECTION_SNAPSHOT_INVALID,
        TradingPermissionIssue.MT5_NOT_INITIALIZED,
        TradingPermissionIssue.TERMINAL_UNAVAILABLE,
        TradingPermissionIssue.TERMINAL_DISCONNECTED,
        TradingPermissionIssue.ACCOUNT_UNAVAILABLE,
        TradingPermissionIssue.ACCOUNT_SERVICE_FAILED,
        TradingPermissionIssue.SYMBOL_SERVICE_FAILED,
        TradingPermissionIssue.EXPOSURE_SERVICE_FAILED,
    }
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _positive_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _required_text(
    value: object,
    field_name: str,
    maximum_length: int,
) -> str:
    normalized = " ".join(str(value).strip().split())

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


@dataclass(frozen=True, slots=True)
class TradingPermissionDiagnostic:
    """One structured readiness diagnostic."""

    component: str
    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "component",
            _required_text(
                self.component,
                "component",
                64,
            ),
        )
        object.__setattr__(
            self,
            "code",
            _required_text(
                self.code,
                "code",
                128,
            ),
        )
        object.__setattr__(
            self,
            "message",
            _required_text(
                self.message,
                "message",
                512,
            ),
        )


@dataclass(frozen=True, slots=True)
class TradingPermissionSnapshot:
    """Immutable result of the broker permission gate."""

    evaluated_at: datetime
    bot_mode: BotMode
    maximum_spread_points: Decimal
    issues: tuple[TradingPermissionIssue, ...]
    diagnostics: tuple[TradingPermissionDiagnostic, ...]
    connection: MT5ConnectionSnapshot | None = None
    account: BrokerAccountSnapshot | None = None
    symbol: BrokerGoldSymbolSnapshot | None = None
    exposure: BrokerGoldExposureSnapshot | None = None

    def __post_init__(self) -> None:
        evaluated_at = _utc_datetime(
            self.evaluated_at,
            "evaluated_at",
        )

        try:
            bot_mode = BotMode(self.bot_mode)
        except ValueError as error:
            raise ValueError(f"Unsupported bot mode: {self.bot_mode}.") from error

        maximum_spread_points = _positive_decimal(
            self.maximum_spread_points,
            "maximum_spread_points",
        )

        issues = tuple(dict.fromkeys(self.issues))
        diagnostics = tuple(self.diagnostics)

        for issue in issues:
            if not isinstance(
                issue,
                TradingPermissionIssue,
            ):
                raise ValueError("issues must contain TradingPermissionIssue values.")

        for diagnostic in diagnostics:
            if not isinstance(
                diagnostic,
                TradingPermissionDiagnostic,
            ):
                raise ValueError("diagnostics must contain TradingPermissionDiagnostic instances.")

        if self.connection is not None and not isinstance(
            self.connection,
            MT5ConnectionSnapshot,
        ):
            raise ValueError("connection must be an MT5ConnectionSnapshot.")

        if self.account is not None and not isinstance(
            self.account,
            BrokerAccountSnapshot,
        ):
            raise ValueError("account must be a BrokerAccountSnapshot.")

        if self.symbol is not None and not isinstance(
            self.symbol,
            BrokerGoldSymbolSnapshot,
        ):
            raise ValueError("symbol must be a BrokerGoldSymbolSnapshot.")

        if self.exposure is not None and not isinstance(
            self.exposure,
            BrokerGoldExposureSnapshot,
        ):
            raise ValueError("exposure must be a BrokerGoldExposureSnapshot.")

        object.__setattr__(
            self,
            "evaluated_at",
            evaluated_at,
        )
        object.__setattr__(
            self,
            "bot_mode",
            bot_mode,
        )
        object.__setattr__(
            self,
            "maximum_spread_points",
            maximum_spread_points,
        )
        object.__setattr__(self, "issues", issues)
        object.__setattr__(
            self,
            "diagnostics",
            diagnostics,
        )

    @property
    def allowed(self) -> bool:
        return not self.issues

    @property
    def new_entry_allowed(self) -> bool:
        return self.allowed

    @property
    def infrastructure_ready(self) -> bool:
        return not any(issue in INFRASTRUCTURE_ISSUES for issue in self.issues)

    @property
    def is_read_only_mode(self) -> bool:
        return TradingPermissionIssue.READ_ONLY_MODE in self.issues

    def require_allowed(
        self,
    ) -> TradingPermissionSnapshot:
        if self.allowed:
            return self

        reason_text = ", ".join(issue.value for issue in self.issues)

        raise PermissionError(f"Broker entry blocked by permission guard: {reason_text}")


@runtime_checkable
class ConnectionSnapshotReader(Protocol):
    def connection_snapshot(
        self,
    ) -> MT5ConnectionSnapshot: ...


@runtime_checkable
class AccountSnapshotReader(Protocol):
    def read_snapshot(
        self,
    ) -> BrokerAccountSnapshot: ...


@runtime_checkable
class SymbolSnapshotReader(Protocol):
    def read_snapshot(
        self,
        *,
        account_currency: str,
    ) -> BrokerGoldSymbolSnapshot: ...


@runtime_checkable
class ExposureSnapshotReader(Protocol):
    def read_snapshot(
        self,
        *,
        broker_symbol: str,
    ) -> BrokerGoldExposureSnapshot: ...


class TradingPermissionGuard:
    """
    Unified read-only broker permission evaluator.

    This class cannot initialize MT5 or submit, modify, cancel,
    or close broker orders.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        connection_reader: ConnectionSnapshotReader,
        account_reader: AccountSnapshotReader,
        symbol_reader: SymbolSnapshotReader,
        exposure_reader: ExposureSnapshotReader,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(settings, Settings):
            raise ValueError("settings must be a Settings instance.")

        if not isinstance(
            connection_reader,
            ConnectionSnapshotReader,
        ):
            raise ValueError("connection_reader must implement ConnectionSnapshotReader.")

        if not isinstance(
            account_reader,
            AccountSnapshotReader,
        ):
            raise ValueError("account_reader must implement AccountSnapshotReader.")

        if not isinstance(
            symbol_reader,
            SymbolSnapshotReader,
        ):
            raise ValueError("symbol_reader must implement SymbolSnapshotReader.")

        if not isinstance(
            exposure_reader,
            ExposureSnapshotReader,
        ):
            raise ValueError("exposure_reader must implement ExposureSnapshotReader.")

        if not callable(clock):
            raise ValueError("clock must be callable.")

        self._settings = settings
        self._connection_reader = connection_reader
        self._account_reader = account_reader
        self._symbol_reader = symbol_reader
        self._exposure_reader = exposure_reader
        self._clock = clock

    def evaluate(self) -> TradingPermissionSnapshot:
        """Evaluate readiness without broker side effects."""

        evaluated_at = _utc_datetime(
            self._clock(),
            "clock result",
        )

        issues: list[TradingPermissionIssue] = []
        diagnostics: list[TradingPermissionDiagnostic] = []

        connection: MT5ConnectionSnapshot | None = None
        account: BrokerAccountSnapshot | None = None
        symbol: BrokerGoldSymbolSnapshot | None = None
        exposure: BrokerGoldExposureSnapshot | None = None

        self._evaluate_configuration(
            issues=issues,
            diagnostics=diagnostics,
        )

        try:
            raw_connection = self._connection_reader.connection_snapshot()
        except Exception as error:
            issues.append(TradingPermissionIssue.CONNECTION_SNAPSHOT_FAILED)
            diagnostics.append(
                self._exception_diagnostic(
                    component="connection",
                    code=type(error).__name__,
                    error=error,
                )
            )

            return self._build_snapshot(
                evaluated_at=evaluated_at,
                issues=issues,
                diagnostics=diagnostics,
                connection=None,
                account=None,
                symbol=None,
                exposure=None,
            )

        if not isinstance(
            raw_connection,
            MT5ConnectionSnapshot,
        ):
            issues.append(TradingPermissionIssue.CONNECTION_SNAPSHOT_INVALID)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="connection",
                    code="INVALID_SNAPSHOT_TYPE",
                    message=("Connection reader returned an unsupported snapshot type."),
                )
            )

            return self._build_snapshot(
                evaluated_at=evaluated_at,
                issues=issues,
                diagnostics=diagnostics,
                connection=None,
                account=None,
                symbol=None,
                exposure=None,
            )

        connection = raw_connection

        self._evaluate_connection(
            connection=connection,
            issues=issues,
            diagnostics=diagnostics,
        )

        connection_blockers = {
            TradingPermissionIssue.MT5_NOT_INITIALIZED,
            TradingPermissionIssue.TERMINAL_UNAVAILABLE,
            TradingPermissionIssue.TERMINAL_DISCONNECTED,
            TradingPermissionIssue.ACCOUNT_UNAVAILABLE,
        }

        if any(issue in connection_blockers for issue in issues):
            return self._build_snapshot(
                evaluated_at=evaluated_at,
                issues=issues,
                diagnostics=diagnostics,
                connection=connection,
                account=None,
                symbol=None,
                exposure=None,
            )

        account = self._read_account(
            evaluated_at=evaluated_at,
            connection=connection,
            issues=issues,
            diagnostics=diagnostics,
        )

        if account is None:
            return self._build_snapshot(
                evaluated_at=evaluated_at,
                issues=issues,
                diagnostics=diagnostics,
                connection=connection,
                account=None,
                symbol=None,
                exposure=None,
            )

        if not account.trade_allowed:
            issues.append(TradingPermissionIssue.ACCOUNT_TRADING_DISABLED)

        if not account.expert_trading_allowed:
            issues.append(TradingPermissionIssue.EXPERT_TRADING_DISABLED)

        symbol = self._read_symbol(
            account=account,
            issues=issues,
            diagnostics=diagnostics,
        )

        if symbol is None:
            return self._build_snapshot(
                evaluated_at=evaluated_at,
                issues=issues,
                diagnostics=diagnostics,
                connection=connection,
                account=account,
                symbol=None,
                exposure=None,
            )

        maximum_spread = Decimal(self._settings.max_spread_points)

        if symbol.spread_points > maximum_spread:
            issues.append(TradingPermissionIssue.SPREAD_LIMIT_EXCEEDED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="symbol",
                    code="SPREAD_LIMIT_EXCEEDED",
                    message=(
                        f"Current spread "
                        f"{symbol.spread_points} points exceeds "
                        f"limit {maximum_spread}."
                    ),
                )
            )

        exposure = self._read_exposure(
            symbol=symbol,
            issues=issues,
            diagnostics=diagnostics,
        )

        if exposure is None:
            return self._build_snapshot(
                evaluated_at=evaluated_at,
                issues=issues,
                diagnostics=diagnostics,
                connection=connection,
                account=account,
                symbol=symbol,
                exposure=None,
            )

        if exposure.has_active_exposure:
            issues.append(TradingPermissionIssue.BROKER_EXPOSURE_ACTIVE)

        if exposure.safety_issues:
            issues.append(TradingPermissionIssue.BROKER_EXPOSURE_UNSAFE)

            for safety_issue in exposure.safety_issues:
                diagnostics.append(
                    TradingPermissionDiagnostic(
                        component="exposure",
                        code=safety_issue.value,
                        message=(
                            f"Broker Gold exposure requires reconciliation: {safety_issue.value}."
                        ),
                    )
                )

        return self._build_snapshot(
            evaluated_at=evaluated_at,
            issues=issues,
            diagnostics=diagnostics,
            connection=connection,
            account=account,
            symbol=symbol,
            exposure=exposure,
        )

    def check(self) -> TradingPermissionSnapshot:
        """Compatibility alias for evaluate()."""

        return self.evaluate()

    def can_trade(self) -> bool:
        """Return whether a new broker entry is allowed."""

        return self.evaluate().allowed

    def assert_can_trade(
        self,
    ) -> TradingPermissionSnapshot:
        """Raise PermissionError when entry is blocked."""

        return self.evaluate().require_allowed()

    def _evaluate_configuration(
        self,
        *,
        issues: list[TradingPermissionIssue],
        diagnostics: list[TradingPermissionDiagnostic],
    ) -> None:
        if self._settings.bot_mode in {
            BotMode.BACKTEST,
            BotMode.PAPER,
        }:
            issues.append(TradingPermissionIssue.READ_ONLY_MODE)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="configuration",
                    code="READ_ONLY_MODE",
                    message=(
                        f"{self._settings.bot_mode.value} mode "
                        "does not permit broker order submission."
                    ),
                )
            )

        if self._settings.bot_mode == BotMode.LIVE and not self._settings.live_trading_armed:
            issues.append(TradingPermissionIssue.LIVE_TRADING_NOT_ARMED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="configuration",
                    code="LIVE_TRADING_NOT_ARMED",
                    message="LIVE mode is not explicitly armed.",
                )
            )

    @staticmethod
    def _evaluate_connection(
        *,
        connection: MT5ConnectionSnapshot,
        issues: list[TradingPermissionIssue],
        diagnostics: list[TradingPermissionDiagnostic],
    ) -> None:
        if not connection.initialized:
            issues.append(TradingPermissionIssue.MT5_NOT_INITIALIZED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="connection",
                    code=str(connection.last_error_code),
                    message=(connection.last_error_message or "MT5 is not initialized."),
                )
            )

        if not connection.terminal_available:
            issues.append(TradingPermissionIssue.TERMINAL_UNAVAILABLE)

        if not connection.terminal_connected:
            issues.append(TradingPermissionIssue.TERMINAL_DISCONNECTED)

        if not connection.account_available:
            issues.append(TradingPermissionIssue.ACCOUNT_UNAVAILABLE)

    def _read_account(
        self,
        *,
        evaluated_at: datetime,
        connection: MT5ConnectionSnapshot,
        issues: list[TradingPermissionIssue],
        diagnostics: list[TradingPermissionDiagnostic],
    ) -> BrokerAccountSnapshot | None:
        try:
            result = self._account_reader.read_snapshot()
        except AccountServiceError as error:
            issues.append(TradingPermissionIssue.ACCOUNT_SERVICE_FAILED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="account",
                    code=error.reason.value,
                    message=error.message,
                )
            )
            return None
        except Exception as error:
            issues.append(TradingPermissionIssue.ACCOUNT_SERVICE_FAILED)
            diagnostics.append(
                self._exception_diagnostic(
                    component="account",
                    code=type(error).__name__,
                    error=error,
                )
            )
            return None

        if not isinstance(
            result,
            BrokerAccountSnapshot,
        ):
            issues.append(TradingPermissionIssue.ACCOUNT_SERVICE_FAILED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="account",
                    code="INVALID_SNAPSHOT_TYPE",
                    message=("Account reader returned an unsupported snapshot type."),
                )
            )
            return None

        return result

    def _read_symbol(
        self,
        *,
        account: BrokerAccountSnapshot,
        issues: list[TradingPermissionIssue],
        diagnostics: list[TradingPermissionDiagnostic],
    ) -> BrokerGoldSymbolSnapshot | None:
        try:
            result = self._symbol_reader.read_snapshot(account_currency=account.account.currency)
        except SymbolServiceError as error:
            issues.append(TradingPermissionIssue.SYMBOL_SERVICE_FAILED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="symbol",
                    code=error.reason.value,
                    message=error.message,
                )
            )
            return None
        except Exception as error:
            issues.append(TradingPermissionIssue.SYMBOL_SERVICE_FAILED)
            diagnostics.append(
                self._exception_diagnostic(
                    component="symbol",
                    code=type(error).__name__,
                    error=error,
                )
            )
            return None

        if not isinstance(
            result,
            BrokerGoldSymbolSnapshot,
        ):
            issues.append(TradingPermissionIssue.SYMBOL_SERVICE_FAILED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="symbol",
                    code="INVALID_SNAPSHOT_TYPE",
                    message=("Symbol reader returned an unsupported snapshot type."),
                )
            )
            return None

        return result

    def _read_exposure(
        self,
        *,
        symbol: BrokerGoldSymbolSnapshot,
        issues: list[TradingPermissionIssue],
        diagnostics: list[TradingPermissionDiagnostic],
    ) -> BrokerGoldExposureSnapshot | None:
        try:
            result = self._exposure_reader.read_snapshot(broker_symbol=symbol.broker_symbol)
        except BrokerExposureServiceError as error:
            issues.append(TradingPermissionIssue.EXPOSURE_SERVICE_FAILED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="exposure",
                    code=error.reason.value,
                    message=error.message,
                )
            )
            return None
        except Exception as error:
            issues.append(TradingPermissionIssue.EXPOSURE_SERVICE_FAILED)
            diagnostics.append(
                self._exception_diagnostic(
                    component="exposure",
                    code=type(error).__name__,
                    error=error,
                )
            )
            return None

        if not isinstance(
            result,
            BrokerGoldExposureSnapshot,
        ):
            issues.append(TradingPermissionIssue.EXPOSURE_SERVICE_FAILED)
            diagnostics.append(
                TradingPermissionDiagnostic(
                    component="exposure",
                    code="INVALID_SNAPSHOT_TYPE",
                    message=("Exposure reader returned an unsupported snapshot type."),
                )
            )
            return None

        return result

    def _build_snapshot(
        self,
        *,
        evaluated_at: datetime,
        issues: list[TradingPermissionIssue],
        diagnostics: list[TradingPermissionDiagnostic],
        connection: MT5ConnectionSnapshot | None,
        account: BrokerAccountSnapshot | None,
        symbol: BrokerGoldSymbolSnapshot | None,
        exposure: BrokerGoldExposureSnapshot | None,
    ) -> TradingPermissionSnapshot:
        return TradingPermissionSnapshot(
            evaluated_at=evaluated_at,
            bot_mode=self._settings.bot_mode,
            maximum_spread_points=Decimal(self._settings.max_spread_points),
            issues=tuple(issues),
            diagnostics=tuple(diagnostics),
            connection=connection,
            account=account,
            symbol=symbol,
            exposure=exposure,
        )

    @staticmethod
    def _exception_diagnostic(
        *,
        component: str,
        code: str,
        error: Exception,
    ) -> TradingPermissionDiagnostic:
        message = str(error).strip()

        if not message:
            message = type(error).__name__

        return TradingPermissionDiagnostic(
            component=component,
            code=code,
            message=message,
        )
