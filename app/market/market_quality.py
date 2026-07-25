from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.config.constants import TimeframeName
from app.market.multi_timeframe_service import (
    MultiTimeframeMarketSnapshot,
)
from app.market.timeframes import (
    SUPPORTED_STRATEGY_TIMEFRAMES,
    get_timeframe_spec,
    parse_timeframe,
)


class MarketDataQualityIssue(str, Enum):
    HISTORY_TOO_SHORT = "HISTORY_TOO_SHORT"
    HISTORY_GAP = "HISTORY_GAP"
    STALE_TIMEFRAME = "STALE_TIMEFRAME"
    LATEST_CLOSE_MISALIGNED = "LATEST_CLOSE_MISALIGNED"
    CROSS_TIMEFRAME_PRICE_DIVERGENCE = "CROSS_TIMEFRAME_PRICE_DIVERGENCE"


def _positive_integer(
    value: object,
    field_name: str,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    if value > maximum:
        raise ValueError(f"{field_name} cannot exceed {maximum}.")

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    if value > maximum:
        raise ValueError(f"{field_name} cannot exceed {maximum}.")

    return value


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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def expected_latest_close_time(
    evaluated_at: datetime,
    timeframe: TimeframeName | str,
) -> datetime:
    """
    Return the most recent fully completed timeframe boundary.

    Examples at 12:37 UTC:
    - H4  -> 12:00
    - H1  -> 12:00
    - M15 -> 12:30
    - M5  -> 12:35
    """

    normalized = _utc_datetime(
        evaluated_at,
        "evaluated_at",
    )
    parsed = parse_timeframe(timeframe)
    timeframe_seconds = get_timeframe_spec(parsed).seconds

    epoch_seconds = int(normalized.timestamp())
    boundary_epoch = epoch_seconds - epoch_seconds % timeframe_seconds

    return datetime.fromtimestamp(
        boundary_epoch,
        tz=timezone.utc,
    )


@dataclass(frozen=True, slots=True)
class MarketDataQualityPolicy:
    """Deterministic strategy market-data requirements."""

    minimum_h4_candles: int = 2
    minimum_h1_candles: int = 2
    minimum_m15_candles: int = 2
    minimum_m5_candles: int = 2
    max_staleness_bars: int = 1
    alignment_grace_seconds: int = 0
    max_close_divergence_percent: Decimal = Decimal("5.00")
    require_contiguous: bool = True
    require_boundary_alignment: bool = True

    def __post_init__(self) -> None:
        minimum_h4_candles = _positive_integer(
            self.minimum_h4_candles,
            "minimum_h4_candles",
            10_000,
        )
        minimum_h1_candles = _positive_integer(
            self.minimum_h1_candles,
            "minimum_h1_candles",
            10_000,
        )
        minimum_m15_candles = _positive_integer(
            self.minimum_m15_candles,
            "minimum_m15_candles",
            10_000,
        )
        minimum_m5_candles = _positive_integer(
            self.minimum_m5_candles,
            "minimum_m5_candles",
            10_000,
        )
        max_staleness_bars = _positive_integer(
            self.max_staleness_bars,
            "max_staleness_bars",
            100,
        )
        alignment_grace_seconds = _non_negative_integer(
            self.alignment_grace_seconds,
            "alignment_grace_seconds",
            86_400,
        )
        max_close_divergence_percent = _positive_decimal(
            self.max_close_divergence_percent,
            "max_close_divergence_percent",
        )
        require_contiguous = _strict_boolean(
            self.require_contiguous,
            "require_contiguous",
        )
        require_boundary_alignment = _strict_boolean(
            self.require_boundary_alignment,
            "require_boundary_alignment",
        )

        object.__setattr__(
            self,
            "minimum_h4_candles",
            minimum_h4_candles,
        )
        object.__setattr__(
            self,
            "minimum_h1_candles",
            minimum_h1_candles,
        )
        object.__setattr__(
            self,
            "minimum_m15_candles",
            minimum_m15_candles,
        )
        object.__setattr__(
            self,
            "minimum_m5_candles",
            minimum_m5_candles,
        )
        object.__setattr__(
            self,
            "max_staleness_bars",
            max_staleness_bars,
        )
        object.__setattr__(
            self,
            "alignment_grace_seconds",
            alignment_grace_seconds,
        )
        object.__setattr__(
            self,
            "max_close_divergence_percent",
            max_close_divergence_percent,
        )
        object.__setattr__(
            self,
            "require_contiguous",
            require_contiguous,
        )
        object.__setattr__(
            self,
            "require_boundary_alignment",
            require_boundary_alignment,
        )

    def minimum_count_for(
        self,
        timeframe: TimeframeName | str,
    ) -> int:
        parsed = parse_timeframe(timeframe)

        counts = {
            TimeframeName.H4: self.minimum_h4_candles,
            TimeframeName.H1: self.minimum_h1_candles,
            TimeframeName.M15: self.minimum_m15_candles,
            TimeframeName.M5: self.minimum_m5_candles,
        }

        try:
            return counts[parsed]
        except KeyError as error:
            raise ValueError(f"{parsed.value} is not a primary strategy timeframe.") from error


@dataclass(frozen=True, slots=True)
class MarketDataQualityDiagnostic:
    """One timeframe-specific quality finding."""

    issue: MarketDataQualityIssue
    timeframe: TimeframeName
    message: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.issue,
            MarketDataQualityIssue,
        ):
            raise ValueError("issue must be a MarketDataQualityIssue.")

        timeframe = parse_timeframe(self.timeframe)

        if timeframe not in SUPPORTED_STRATEGY_TIMEFRAMES:
            raise ValueError(f"{timeframe.value} is not a primary strategy timeframe.")

        message = " ".join(str(self.message).strip().split())

        if not message:
            raise ValueError("message cannot be blank.")

        if len(message) > 512:
            raise ValueError("message cannot exceed 512 characters.")

        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )
        object.__setattr__(
            self,
            "message",
            message,
        )


@dataclass(frozen=True, slots=True)
class MarketDataQualityDecision:
    """Immutable market-data validation result."""

    snapshot: MultiTimeframeMarketSnapshot
    policy: MarketDataQualityPolicy
    issues: tuple[MarketDataQualityIssue, ...]
    diagnostics: tuple[MarketDataQualityDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.snapshot,
            MultiTimeframeMarketSnapshot,
        ):
            raise ValueError("snapshot must be a MultiTimeframeMarketSnapshot.")

        if not isinstance(
            self.policy,
            MarketDataQualityPolicy,
        ):
            raise ValueError("policy must be a MarketDataQualityPolicy.")

        issues = tuple(dict.fromkeys(self.issues))
        diagnostics = tuple(self.diagnostics)

        for issue in issues:
            if not isinstance(
                issue,
                MarketDataQualityIssue,
            ):
                raise ValueError("issues must contain MarketDataQualityIssue values.")

        for diagnostic in diagnostics:
            if not isinstance(
                diagnostic,
                MarketDataQualityDiagnostic,
            ):
                raise ValueError("diagnostics must contain MarketDataQualityDiagnostic instances.")

        diagnostic_issues = {diagnostic.issue for diagnostic in diagnostics}

        if not diagnostic_issues.issubset(set(issues)):
            raise ValueError("Every diagnostic issue must appear in the decision issues.")

        object.__setattr__(
            self,
            "issues",
            issues,
        )
        object.__setattr__(
            self,
            "diagnostics",
            diagnostics,
        )

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def strategy_ready(self) -> bool:
        return self.valid

    def diagnostics_for(
        self,
        timeframe: TimeframeName | str,
    ) -> tuple[MarketDataQualityDiagnostic, ...]:
        parsed = parse_timeframe(timeframe)

        return tuple(
            diagnostic for diagnostic in self.diagnostics if diagnostic.timeframe == parsed
        )

    def require_valid(
        self,
    ) -> MarketDataQualityDecision:
        if self.valid:
            return self

        issue_text = ", ".join(issue.value for issue in self.issues)

        raise ValueError(f"Strategy market data failed quality gate: {issue_text}")


class MarketDataQualityValidator:
    """
    Pure strategy market-data quality gate.

    This validator performs no MT5 or broker operations.
    """

    def __init__(
        self,
        policy: MarketDataQualityPolicy | None = None,
    ) -> None:
        selected_policy = policy or MarketDataQualityPolicy()

        if not isinstance(
            selected_policy,
            MarketDataQualityPolicy,
        ):
            raise ValueError("policy must be a MarketDataQualityPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> MarketDataQualityPolicy:
        return self._policy

    def evaluate(
        self,
        snapshot: MultiTimeframeMarketSnapshot,
    ) -> MarketDataQualityDecision:
        if not isinstance(
            snapshot,
            MultiTimeframeMarketSnapshot,
        ):
            raise ValueError("snapshot must be a MultiTimeframeMarketSnapshot.")

        issues: list[MarketDataQualityIssue] = []
        diagnostics: list[MarketDataQualityDiagnostic] = []

        for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES:
            market_slice = snapshot.get(timeframe)
            minimum_count = self._policy.minimum_count_for(timeframe)

            if market_slice.closed.count < minimum_count:
                self._add_diagnostic(
                    issues=issues,
                    diagnostics=diagnostics,
                    issue=(MarketDataQualityIssue.HISTORY_TOO_SHORT),
                    timeframe=timeframe,
                    message=(
                        f"{timeframe.value} contains "
                        f"{market_slice.closed.count} candles; "
                        f"minimum required is {minimum_count}."
                    ),
                )

            if self._policy.require_contiguous and market_slice.has_gaps:
                self._add_diagnostic(
                    issues=issues,
                    diagnostics=diagnostics,
                    issue=MarketDataQualityIssue.HISTORY_GAP,
                    timeframe=timeframe,
                    message=(
                        f"{timeframe.value} history contains "
                        f"{market_slice.closed.missing_candle_count} "
                        "missing candle intervals."
                    ),
                )

            if market_slice.is_stale_at(
                snapshot.evaluated_at,
                self._policy.max_staleness_bars,
            ):
                age = market_slice.age_at(snapshot.evaluated_at)
                maximum_age = market_slice.maximum_age(self._policy.max_staleness_bars)

                self._add_diagnostic(
                    issues=issues,
                    diagnostics=diagnostics,
                    issue=(MarketDataQualityIssue.STALE_TIMEFRAME),
                    timeframe=timeframe,
                    message=(
                        f"{timeframe.value} latest close age {age} exceeds maximum {maximum_age}."
                    ),
                )

            if self._policy.require_boundary_alignment:
                expected_close = expected_latest_close_time(
                    snapshot.evaluated_at,
                    timeframe,
                )
                actual_close = market_slice.latest_close_time
                difference_seconds = abs(int((expected_close - actual_close).total_seconds()))

                if difference_seconds > self._policy.alignment_grace_seconds:
                    self._add_diagnostic(
                        issues=issues,
                        diagnostics=diagnostics,
                        issue=(MarketDataQualityIssue.LATEST_CLOSE_MISALIGNED),
                        timeframe=timeframe,
                        message=(
                            f"{timeframe.value} latest close "
                            f"{actual_close.isoformat()} does not "
                            "match expected boundary "
                            f"{expected_close.isoformat()}."
                        ),
                    )

        self._evaluate_price_coherence(
            snapshot=snapshot,
            issues=issues,
            diagnostics=diagnostics,
        )

        return MarketDataQualityDecision(
            snapshot=snapshot,
            policy=self._policy,
            issues=tuple(issues),
            diagnostics=tuple(diagnostics),
        )

    def validate(
        self,
        snapshot: MultiTimeframeMarketSnapshot,
    ) -> MarketDataQualityDecision:
        return self.evaluate(snapshot).require_valid()

    def is_valid(
        self,
        snapshot: MultiTimeframeMarketSnapshot,
    ) -> bool:
        return self.evaluate(snapshot).valid

    def _evaluate_price_coherence(
        self,
        *,
        snapshot: MultiTimeframeMarketSnapshot,
        issues: list[MarketDataQualityIssue],
        diagnostics: list[MarketDataQualityDiagnostic],
    ) -> None:
        reference_price = snapshot.m5.closed.latest.close

        for timeframe in (
            TimeframeName.H4,
            TimeframeName.H1,
            TimeframeName.M15,
        ):
            close_price = snapshot.get(timeframe).closed.latest.close

            divergence_percent = (
                abs(close_price - reference_price) / reference_price * Decimal("100")
            )

            if divergence_percent > self._policy.max_close_divergence_percent:
                self._add_diagnostic(
                    issues=issues,
                    diagnostics=diagnostics,
                    issue=(MarketDataQualityIssue.CROSS_TIMEFRAME_PRICE_DIVERGENCE),
                    timeframe=timeframe,
                    message=(
                        f"{timeframe.value} latest close "
                        f"{close_price} differs from M5 "
                        f"{reference_price} by "
                        f"{divergence_percent}%."
                    ),
                )

    @staticmethod
    def _add_diagnostic(
        *,
        issues: list[MarketDataQualityIssue],
        diagnostics: list[MarketDataQualityDiagnostic],
        issue: MarketDataQualityIssue,
        timeframe: TimeframeName,
        message: str,
    ) -> None:
        issues.append(issue)
        diagnostics.append(
            MarketDataQualityDiagnostic(
                issue=issue,
                timeframe=timeframe,
                message=message,
            )
        )


StrategyMarketQualityValidator = MarketDataQualityValidator
