from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    Decimal,
    InvalidOperation,
)
from enum import Enum
from typing import TypeAlias

from app.domain.exposure import AccountSnapshot
from app.domain.trading import (
    CANONICAL_GOLD_SYMBOL,
    TradePlan,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class PositionSizeBlockReason(str, Enum):
    ACCOUNT_CAPITAL_NON_POSITIVE = "ACCOUNT_CAPITAL_NON_POSITIVE"
    ACCOUNT_CURRENCY_MISMATCH = "ACCOUNT_CURRENCY_MISMATCH"
    RISK_BUDGET_BELOW_MINIMUM_VOLUME = "RISK_BUDGET_BELOW_MINIMUM_VOLUME"


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


def _required_text(
    value: str,
    field_name: str,
    maximum_length: int = 12,
) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


@dataclass(frozen=True, slots=True)
class GoldSymbolSpecification:
    """Broker-independent XAUUSD sizing specification."""

    symbol: str
    account_currency: str
    tick_size: DecimalLike
    tick_value_per_lot: DecimalLike
    volume_min: DecimalLike
    volume_max: DecimalLike
    volume_step: DecimalLike

    def __post_init__(self) -> None:
        symbol = str(self.symbol).strip().upper()

        if symbol != CANONICAL_GOLD_SYMBOL:
            raise ValueError(f"Only canonical symbol {CANONICAL_GOLD_SYMBOL} is supported.")

        account_currency = _required_text(
            self.account_currency,
            "account_currency",
        ).upper()

        tick_size = _positive_decimal(
            self.tick_size,
            "tick_size",
        )
        tick_value_per_lot = _positive_decimal(
            self.tick_value_per_lot,
            "tick_value_per_lot",
        )
        volume_min = _positive_decimal(
            self.volume_min,
            "volume_min",
        )
        volume_max = _positive_decimal(
            self.volume_max,
            "volume_max",
        )
        volume_step = _positive_decimal(
            self.volume_step,
            "volume_step",
        )

        if volume_max < volume_min:
            raise ValueError("volume_max cannot be below volume_min.")

        if volume_step > volume_max:
            raise ValueError("volume_step cannot exceed volume_max.")

        if volume_min % volume_step != 0:
            raise ValueError("volume_min must align with volume_step.")

        if volume_max % volume_step != 0:
            raise ValueError("volume_max must align with volume_step.")

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(
            self,
            "account_currency",
            account_currency,
        )
        object.__setattr__(self, "tick_size", tick_size)
        object.__setattr__(
            self,
            "tick_value_per_lot",
            tick_value_per_lot,
        )
        object.__setattr__(self, "volume_min", volume_min)
        object.__setattr__(self, "volume_max", volume_max)
        object.__setattr__(self, "volume_step", volume_step)

    def normalize_volume_down(
        self,
        volume: DecimalLike,
    ) -> Decimal:
        requested_volume = _positive_decimal(
            volume,
            "volume",
        )

        units = (requested_volume / self.volume_step).to_integral_value(rounding=ROUND_FLOOR)

        return units * self.volume_step


@dataclass(frozen=True, slots=True)
class PositionSize:
    """Exact approved XAUUSD position-size calculation."""

    volume: Decimal
    risk_capital: Decimal
    requested_risk_amount: Decimal
    actual_risk_amount: Decimal
    requested_risk_percent: Decimal
    actual_risk_percent: Decimal
    stop_distance: Decimal
    ticks_to_stop: Decimal
    risk_per_lot: Decimal
    raw_volume: Decimal
    was_rounded_down: bool
    was_capped_by_maximum: bool

    def __post_init__(self) -> None:
        decimal_fields = (
            "volume",
            "risk_capital",
            "requested_risk_amount",
            "actual_risk_amount",
            "requested_risk_percent",
            "actual_risk_percent",
            "stop_distance",
            "ticks_to_stop",
            "risk_per_lot",
            "raw_volume",
        )

        for field_name in decimal_fields:
            value = getattr(self, field_name)

            if not isinstance(value, Decimal):
                raise ValueError(f"{field_name} must be a Decimal.")

            if not value.is_finite() or value <= 0:
                raise ValueError(f"{field_name} must be finite and greater than zero.")

        if not isinstance(self.was_rounded_down, bool):
            raise ValueError("was_rounded_down must be a boolean.")

        if not isinstance(
            self.was_capped_by_maximum,
            bool,
        ):
            raise ValueError("was_capped_by_maximum must be a boolean.")

        if self.actual_risk_amount > self.requested_risk_amount:
            raise ValueError("actual_risk_amount cannot exceed requested_risk_amount.")

        if self.actual_risk_percent > self.requested_risk_percent:
            raise ValueError("actual_risk_percent cannot exceed requested_risk_percent.")


@dataclass(frozen=True, slots=True)
class PositionSizeDecision:
    """Allowed or blocked result of position sizing."""

    reasons: tuple[PositionSizeBlockReason, ...]
    sizing: PositionSize | None

    def __post_init__(self) -> None:
        reasons = tuple(dict.fromkeys(self.reasons))

        if reasons and self.sizing is not None:
            raise ValueError("A blocked sizing decision cannot contain an approved size.")

        if not reasons and self.sizing is None:
            raise ValueError("An allowed sizing decision must contain an approved size.")

        object.__setattr__(self, "reasons", reasons)

    @property
    def allowed(self) -> bool:
        return not self.reasons and self.sizing is not None

    def require_allowed(self) -> PositionSize:
        if self.sizing is not None and not self.reasons:
            return self.sizing

        reason_text = ", ".join(reason.value for reason in self.reasons)

        raise PermissionError(f"Position sizing blocked: {reason_text}")


def calculate_position_size(
    *,
    plan: TradePlan,
    account: AccountSnapshot,
    specification: GoldSymbolSpecification,
) -> PositionSizeDecision:
    """Calculate conservative Gold volume without broker effects."""

    if not isinstance(plan, TradePlan):
        raise ValueError("plan must be a TradePlan instance.")

    if not isinstance(account, AccountSnapshot):
        raise ValueError("account must be an AccountSnapshot instance.")

    if not isinstance(
        specification,
        GoldSymbolSpecification,
    ):
        raise ValueError("specification must be a GoldSymbolSpecification instance.")

    if account.currency != specification.account_currency:
        return PositionSizeDecision(
            reasons=(PositionSizeBlockReason.ACCOUNT_CURRENCY_MISMATCH,),
            sizing=None,
        )

    risk_capital = min(
        account.balance,
        account.equity,
    )

    if risk_capital <= 0:
        return PositionSizeDecision(
            reasons=(PositionSizeBlockReason.ACCOUNT_CAPITAL_NON_POSITIVE,),
            sizing=None,
        )

    requested_risk_amount = risk_capital * plan.risk_percent / Decimal("100")

    stop_distance = plan.stop_distance

    ticks_to_stop = (stop_distance / specification.tick_size).to_integral_value(
        rounding=ROUND_CEILING
    )

    risk_per_lot = ticks_to_stop * specification.tick_value_per_lot

    raw_volume = requested_risk_amount / risk_per_lot

    capped_volume = min(
        raw_volume,
        specification.volume_max,
    )

    normalized_volume = specification.normalize_volume_down(
        capped_volume,
    )

    if normalized_volume < specification.volume_min:
        return PositionSizeDecision(
            reasons=(PositionSizeBlockReason.RISK_BUDGET_BELOW_MINIMUM_VOLUME,),
            sizing=None,
        )

    actual_risk_amount = normalized_volume * risk_per_lot

    actual_risk_percent = actual_risk_amount / risk_capital * Decimal("100")

    sizing = PositionSize(
        volume=normalized_volume,
        risk_capital=risk_capital,
        requested_risk_amount=requested_risk_amount,
        actual_risk_amount=actual_risk_amount,
        requested_risk_percent=plan.risk_percent,
        actual_risk_percent=actual_risk_percent,
        stop_distance=stop_distance,
        ticks_to_stop=ticks_to_stop,
        risk_per_lot=risk_per_lot,
        raw_volume=raw_volume,
        was_rounded_down=(normalized_volume < capped_volume),
        was_capped_by_maximum=(raw_volume > specification.volume_max),
    )

    return PositionSizeDecision(
        reasons=(),
        sizing=sizing,
    )
