from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.reward_risk_analysis import (
    RewardRiskAnalysisDecision,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _canonical_decimal(value: Decimal) -> str:
    """
    Return a scale-independent Decimal representation.

    Numerically equivalent values such as Decimal("1"),
    Decimal("1.0"), and Decimal("1.00") must produce the
    same deterministic stable-ID fragment.
    """

    if value == _ZERO:
        return "0"

    return format(value.normalize(), "f")


class RiskBudgetAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


class RiskBudgetAdmissionReason(str, Enum):
    ADMITTED = "ADMITTED"
    REWARD_RISK_BLOCKED = "REWARD_RISK_BLOCKED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    GOLD_POSITION_LIMIT_REACHED = "GOLD_POSITION_LIMIT_REACHED"
    DAILY_LOSS_LIMIT_REACHED = "DAILY_LOSS_LIMIT_REACHED"
    SETUP_RISK_LIMIT_EXCEEDED = "SETUP_RISK_LIMIT_EXCEEDED"
    AGGREGATE_RISK_LIMIT_EXCEEDED = "AGGREGATE_RISK_LIMIT_EXCEEDED"
    MULTIPLE_RISK_BLOCKERS = "MULTIPLE_RISK_BLOCKERS"


class RiskBudgetAdmissionBlocker(str, Enum):
    REWARD_RISK_BLOCKED = "REWARD_RISK_BLOCKED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    GOLD_POSITION_LIMIT_REACHED = "GOLD_POSITION_LIMIT_REACHED"
    DAILY_LOSS_LIMIT_REACHED = "DAILY_LOSS_LIMIT_REACHED"
    SETUP_RISK_LIMIT_EXCEEDED = "SETUP_RISK_LIMIT_EXCEEDED"
    AGGREGATE_RISK_LIMIT_EXCEEDED = "AGGREGATE_RISK_LIMIT_EXCEEDED"


class RiskBudgetAdmissionErrorReason(str, Enum):
    INVALID_REWARD_RISK_DECISION = "INVALID_REWARD_RISK_DECISION"
    INVALID_RISK_SNAPSHOT = "INVALID_RISK_SNAPSHOT"


class RiskBudgetAdmissionError(RuntimeError):
    """Structured strategy risk-budget admission failure."""

    def __init__(
        self,
        reason: RiskBudgetAdmissionErrorReason,
        message: str,
    ) -> None:
        self.reason = RiskBudgetAdmissionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Risk-budget admission error [{self.reason.value}]: {self.message}")


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value


def _positive_finite_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value <= _ZERO:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _non_negative_finite_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value < _ZERO:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _percentage(
    value: object,
    field_name: str,
) -> Decimal:
    selected = _positive_finite_decimal(
        value,
        field_name,
    )

    if selected > _HUNDRED:
        raise ValueError(f"{field_name} cannot exceed 100.")

    return selected


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


@dataclass(frozen=True, slots=True)
class RiskBudgetAdmissionPolicy:
    """
    Account-level risk limits for one Gold setup.

    Admission remains analytical and does not calculate
    volume or authorize a broker order.
    """

    maximum_setup_risk_percent: Decimal = Decimal("1")
    maximum_aggregate_risk_percent: Decimal = Decimal("2")
    maximum_daily_loss_percent: Decimal = Decimal("3")
    maximum_gold_positions: int = 1

    def __post_init__(self) -> None:
        setup_percent = _percentage(
            self.maximum_setup_risk_percent,
            "maximum_setup_risk_percent",
        )
        aggregate_percent = _percentage(
            self.maximum_aggregate_risk_percent,
            "maximum_aggregate_risk_percent",
        )
        daily_percent = _percentage(
            self.maximum_daily_loss_percent,
            "maximum_daily_loss_percent",
        )
        maximum_positions = _positive_integer(
            self.maximum_gold_positions,
            "maximum_gold_positions",
        )

        if setup_percent > aggregate_percent:
            raise ValueError(
                "maximum_setup_risk_percent cannot exceed maximum_aggregate_risk_percent."
            )

        object.__setattr__(
            self,
            "maximum_setup_risk_percent",
            setup_percent,
        )
        object.__setattr__(
            self,
            "maximum_aggregate_risk_percent",
            aggregate_percent,
        )
        object.__setattr__(
            self,
            "maximum_daily_loss_percent",
            daily_percent,
        )
        object.__setattr__(
            self,
            "maximum_gold_positions",
            maximum_positions,
        )


@dataclass(frozen=True, slots=True)
class StrategyRiskBudgetSnapshot:
    """Immutable account-risk state for one admission check."""

    observed_at: datetime
    account_equity: Decimal
    proposed_risk_amount: Decimal
    current_aggregate_risk_amount: Decimal
    realized_daily_loss_amount: Decimal
    open_gold_positions: int
    kill_switch_active: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed_at",
            _aware_datetime(
                self.observed_at,
                "observed_at",
            ),
        )
        object.__setattr__(
            self,
            "account_equity",
            _positive_finite_decimal(
                self.account_equity,
                "account_equity",
            ),
        )
        object.__setattr__(
            self,
            "proposed_risk_amount",
            _positive_finite_decimal(
                self.proposed_risk_amount,
                "proposed_risk_amount",
            ),
        )
        object.__setattr__(
            self,
            "current_aggregate_risk_amount",
            _non_negative_finite_decimal(
                self.current_aggregate_risk_amount,
                "current_aggregate_risk_amount",
            ),
        )
        object.__setattr__(
            self,
            "realized_daily_loss_amount",
            _non_negative_finite_decimal(
                self.realized_daily_loss_amount,
                "realized_daily_loss_amount",
            ),
        )
        object.__setattr__(
            self,
            "open_gold_positions",
            _non_negative_integer(
                self.open_gold_positions,
                "open_gold_positions",
            ),
        )
        object.__setattr__(
            self,
            "kill_switch_active",
            _strict_boolean(
                self.kill_switch_active,
                "kill_switch_active",
            ),
        )

    @property
    def aggregate_risk_after_admission(self) -> Decimal:
        return self.current_aggregate_risk_amount + self.proposed_risk_amount

    @property
    def stable_id(self) -> str:
        kill_switch = "ACTIVE" if self.kill_switch_active else "INACTIVE"

        return (
            f"{self.observed_at.isoformat()}:"
            f"EQUITY["
            f"{_canonical_decimal(self.account_equity)}]:"
            f"PROPOSED["
            f"{_canonical_decimal(self.proposed_risk_amount)}]:"
            f"AGGREGATE["
            f"{_canonical_decimal(self.current_aggregate_risk_amount)}]:"
            f"DAILY_LOSS["
            f"{_canonical_decimal(self.realized_daily_loss_amount)}]:"
            f"GOLD_POSITIONS[{self.open_gold_positions}]:"
            f"KILL_SWITCH[{kill_switch}]"
        )


@dataclass(frozen=True, slots=True)
class RiskBudgetMetrics:
    """Exact account-risk percentages and limits."""

    account_equity: Decimal
    proposed_risk_amount: Decimal
    current_aggregate_risk_amount: Decimal
    aggregate_risk_after_admission: Decimal
    realized_daily_loss_amount: Decimal
    proposed_risk_percent: Decimal
    aggregate_risk_before_percent: Decimal
    aggregate_risk_after_percent: Decimal
    daily_loss_percent: Decimal
    maximum_setup_risk_amount: Decimal
    maximum_aggregate_risk_amount: Decimal
    maximum_daily_loss_amount: Decimal
    remaining_aggregate_risk_before: Decimal
    remaining_aggregate_risk_after: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "account_equity",
            _positive_finite_decimal(
                self.account_equity,
                "account_equity",
            ),
        )
        object.__setattr__(
            self,
            "proposed_risk_amount",
            _positive_finite_decimal(
                self.proposed_risk_amount,
                "proposed_risk_amount",
            ),
        )

        for field_name in (
            "current_aggregate_risk_amount",
            "aggregate_risk_after_admission",
            "realized_daily_loss_amount",
            "proposed_risk_percent",
            "aggregate_risk_before_percent",
            "aggregate_risk_after_percent",
            "daily_loss_percent",
            "maximum_setup_risk_amount",
            "maximum_aggregate_risk_amount",
            "maximum_daily_loss_amount",
            "remaining_aggregate_risk_before",
            "remaining_aggregate_risk_after",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_finite_decimal(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        expected_aggregate = self.current_aggregate_risk_amount + self.proposed_risk_amount

        if self.aggregate_risk_after_admission != expected_aggregate:
            raise ValueError(
                "aggregate_risk_after_admission does not match current and proposed risk."
            )

        expected_proposed_percent = self.proposed_risk_amount / self.account_equity * _HUNDRED
        expected_before_percent = (
            self.current_aggregate_risk_amount / self.account_equity * _HUNDRED
        )
        expected_after_percent = (
            self.aggregate_risk_after_admission / self.account_equity * _HUNDRED
        )
        expected_daily_percent = self.realized_daily_loss_amount / self.account_equity * _HUNDRED

        if self.proposed_risk_percent != (expected_proposed_percent):
            raise ValueError("proposed_risk_percent is inconsistent.")

        if self.aggregate_risk_before_percent != (expected_before_percent):
            raise ValueError("aggregate_risk_before_percent is inconsistent.")

        if self.aggregate_risk_after_percent != (expected_after_percent):
            raise ValueError("aggregate_risk_after_percent is inconsistent.")

        if self.daily_loss_percent != expected_daily_percent:
            raise ValueError("daily_loss_percent is inconsistent.")

        if self.maximum_setup_risk_amount > self.maximum_aggregate_risk_amount:
            raise ValueError(
                "Maximum setup risk amount cannot exceed maximum aggregate risk amount."
            )

        expected_remaining_before = max(
            _ZERO,
            self.maximum_aggregate_risk_amount - self.current_aggregate_risk_amount,
        )
        expected_remaining_after = max(
            _ZERO,
            self.maximum_aggregate_risk_amount - self.aggregate_risk_after_admission,
        )

        if self.remaining_aggregate_risk_before != (expected_remaining_before):
            raise ValueError("remaining_aggregate_risk_before is inconsistent.")

        if self.remaining_aggregate_risk_after != (expected_remaining_after):
            raise ValueError("remaining_aggregate_risk_after is inconsistent.")

    @property
    def stable_id(self) -> str:
        return (
            f"EQUITY["
            f"{_canonical_decimal(self.account_equity)}]:"
            f"PROPOSED["
            f"{_canonical_decimal(self.proposed_risk_amount)}]:"
            f"PROPOSED_PCT["
            f"{_canonical_decimal(self.proposed_risk_percent)}]:"
            f"AGGREGATE_AFTER["
            f"{_canonical_decimal(self.aggregate_risk_after_admission)}]:"
            f"AGGREGATE_AFTER_PCT["
            f"{_canonical_decimal(self.aggregate_risk_after_percent)}]:"
            f"DAILY_LOSS_PCT["
            f"{_canonical_decimal(self.daily_loss_percent)}]"
        )


def _build_metrics(
    snapshot: StrategyRiskBudgetSnapshot,
    policy: RiskBudgetAdmissionPolicy,
) -> RiskBudgetMetrics:
    equity = snapshot.account_equity
    maximum_setup_amount = equity * policy.maximum_setup_risk_percent / _HUNDRED
    maximum_aggregate_amount = equity * policy.maximum_aggregate_risk_percent / _HUNDRED
    maximum_daily_loss_amount = equity * policy.maximum_daily_loss_percent / _HUNDRED
    aggregate_after = snapshot.aggregate_risk_after_admission

    return RiskBudgetMetrics(
        account_equity=equity,
        proposed_risk_amount=(snapshot.proposed_risk_amount),
        current_aggregate_risk_amount=(snapshot.current_aggregate_risk_amount),
        aggregate_risk_after_admission=aggregate_after,
        realized_daily_loss_amount=(snapshot.realized_daily_loss_amount),
        proposed_risk_percent=(snapshot.proposed_risk_amount / equity * _HUNDRED),
        aggregate_risk_before_percent=(snapshot.current_aggregate_risk_amount / equity * _HUNDRED),
        aggregate_risk_after_percent=(aggregate_after / equity * _HUNDRED),
        daily_loss_percent=(snapshot.realized_daily_loss_amount / equity * _HUNDRED),
        maximum_setup_risk_amount=(maximum_setup_amount),
        maximum_aggregate_risk_amount=(maximum_aggregate_amount),
        maximum_daily_loss_amount=(maximum_daily_loss_amount),
        remaining_aggregate_risk_before=max(
            _ZERO,
            maximum_aggregate_amount - snapshot.current_aggregate_risk_amount,
        ),
        remaining_aggregate_risk_after=max(
            _ZERO,
            maximum_aggregate_amount - aggregate_after,
        ),
    )


@dataclass(frozen=True, slots=True)
class _RiskBudgetEvaluation:
    status: RiskBudgetAdmissionStatus
    reason: RiskBudgetAdmissionReason
    blockers: tuple[
        RiskBudgetAdmissionBlocker,
        ...,
    ]
    snapshot: StrategyRiskBudgetSnapshot | None
    metrics: RiskBudgetMetrics | None


_BLOCKER_REASON_MAP = {
    RiskBudgetAdmissionBlocker.REWARD_RISK_BLOCKED: (RiskBudgetAdmissionReason.REWARD_RISK_BLOCKED),
    RiskBudgetAdmissionBlocker.KILL_SWITCH_ACTIVE: (RiskBudgetAdmissionReason.KILL_SWITCH_ACTIVE),
    RiskBudgetAdmissionBlocker.GOLD_POSITION_LIMIT_REACHED: (
        RiskBudgetAdmissionReason.GOLD_POSITION_LIMIT_REACHED
    ),
    RiskBudgetAdmissionBlocker.DAILY_LOSS_LIMIT_REACHED: (
        RiskBudgetAdmissionReason.DAILY_LOSS_LIMIT_REACHED
    ),
    RiskBudgetAdmissionBlocker.SETUP_RISK_LIMIT_EXCEEDED: (
        RiskBudgetAdmissionReason.SETUP_RISK_LIMIT_EXCEEDED
    ),
    RiskBudgetAdmissionBlocker.AGGREGATE_RISK_LIMIT_EXCEEDED: (
        RiskBudgetAdmissionReason.AGGREGATE_RISK_LIMIT_EXCEEDED
    ),
}


def _reason_for_blockers(
    blockers: tuple[
        RiskBudgetAdmissionBlocker,
        ...,
    ],
) -> RiskBudgetAdmissionReason:
    if not blockers:
        return RiskBudgetAdmissionReason.ADMITTED

    if len(blockers) == 1:
        return _BLOCKER_REASON_MAP[blockers[0]]

    return RiskBudgetAdmissionReason.MULTIPLE_RISK_BLOCKERS


def _derive_admission(
    reward_risk: RewardRiskAnalysisDecision,
    snapshot: StrategyRiskBudgetSnapshot | None,
    policy: RiskBudgetAdmissionPolicy,
) -> _RiskBudgetEvaluation:
    if reward_risk.is_blocked:
        return _RiskBudgetEvaluation(
            status=RiskBudgetAdmissionStatus.BLOCKED,
            reason=(RiskBudgetAdmissionReason.REWARD_RISK_BLOCKED),
            blockers=(RiskBudgetAdmissionBlocker.REWARD_RISK_BLOCKED,),
            snapshot=None,
            metrics=None,
        )

    if snapshot is None:
        raise RiskBudgetAdmissionError(
            RiskBudgetAdmissionErrorReason.INVALID_RISK_SNAPSHOT,
            "A qualified reward-to-risk decision requires a StrategyRiskBudgetSnapshot.",
        )

    if snapshot.observed_at < reward_risk.observed_at:
        raise RiskBudgetAdmissionError(
            RiskBudgetAdmissionErrorReason.INVALID_RISK_SNAPSHOT,
            "Risk snapshot cannot predate the strategy analysis observation.",
        )

    metrics = _build_metrics(
        snapshot,
        policy,
    )
    blockers: list[RiskBudgetAdmissionBlocker] = []

    if snapshot.kill_switch_active:
        blockers.append(RiskBudgetAdmissionBlocker.KILL_SWITCH_ACTIVE)

    if snapshot.open_gold_positions >= policy.maximum_gold_positions:
        blockers.append(RiskBudgetAdmissionBlocker.GOLD_POSITION_LIMIT_REACHED)

    if metrics.daily_loss_percent >= policy.maximum_daily_loss_percent:
        blockers.append(RiskBudgetAdmissionBlocker.DAILY_LOSS_LIMIT_REACHED)

    if metrics.proposed_risk_percent > policy.maximum_setup_risk_percent:
        blockers.append(RiskBudgetAdmissionBlocker.SETUP_RISK_LIMIT_EXCEEDED)

    if metrics.aggregate_risk_after_percent > policy.maximum_aggregate_risk_percent:
        blockers.append(RiskBudgetAdmissionBlocker.AGGREGATE_RISK_LIMIT_EXCEEDED)

    blocker_tuple = tuple(blockers)

    return _RiskBudgetEvaluation(
        status=(
            RiskBudgetAdmissionStatus.BLOCKED
            if blocker_tuple
            else RiskBudgetAdmissionStatus.ADMITTED
        ),
        reason=_reason_for_blockers(blocker_tuple),
        blockers=blocker_tuple,
        snapshot=snapshot,
        metrics=metrics,
    )


@dataclass(frozen=True, slots=True)
class RiskBudgetAdmissionDecision:
    """Validated strategy account-risk admission."""

    reward_risk: RewardRiskAnalysisDecision
    policy: RiskBudgetAdmissionPolicy
    status: RiskBudgetAdmissionStatus
    reason: RiskBudgetAdmissionReason
    blockers: tuple[
        RiskBudgetAdmissionBlocker,
        ...,
    ]
    snapshot: StrategyRiskBudgetSnapshot | None
    metrics: RiskBudgetMetrics | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.reward_risk,
            RewardRiskAnalysisDecision,
        ):
            raise ValueError("reward_risk must be a RewardRiskAnalysisDecision.")

        if not isinstance(
            self.policy,
            RiskBudgetAdmissionPolicy,
        ):
            raise ValueError("policy must be a RiskBudgetAdmissionPolicy.")

        try:
            status = RiskBudgetAdmissionStatus(self.status)
            reason = RiskBudgetAdmissionReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported risk-budget status or reason.") from error

        blockers = tuple(RiskBudgetAdmissionBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Risk-budget blockers cannot contain duplicates.")

        if self.snapshot is not None and not isinstance(
            self.snapshot,
            StrategyRiskBudgetSnapshot,
        ):
            raise ValueError("snapshot must be a StrategyRiskBudgetSnapshot or None.")

        if self.metrics is not None and not isinstance(
            self.metrics,
            RiskBudgetMetrics,
        ):
            raise ValueError("metrics must be RiskBudgetMetrics or None.")

        expected = _derive_admission(
            self.reward_risk,
            self.snapshot,
            self.policy,
        )
        supplied = _RiskBudgetEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            snapshot=self.snapshot,
            metrics=self.metrics,
        )

        if supplied != expected:
            raise ValueError(
                "Risk-budget admission does not match its "
                "reward-to-risk decision, snapshot, and "
                "policy."
            )

        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "blockers",
            blockers,
        )

    @property
    def broker_symbol(self) -> str:
        return self.reward_risk.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.reward_risk.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.reward_risk.direction

    @property
    def reward_risk_ratio(self) -> Decimal | None:
        return self.reward_risk.reward_risk_ratio

    @property
    def is_admitted(self) -> bool:
        return self.status == RiskBudgetAdmissionStatus.ADMITTED

    @property
    def is_blocked(self) -> bool:
        return not self.is_admitted

    @property
    def approved_risk_amount(self) -> Decimal | None:
        if not self.is_admitted or self.snapshot is None:
            return None

        return self.snapshot.proposed_risk_amount

    @property
    def can_continue_to_position_sizing(self) -> bool:
        return self.is_admitted

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )
        snapshot_fragment = (
            self.snapshot.stable_id if self.snapshot is not None else "NO_RISK_SNAPSHOT"
        )
        metrics_fragment = self.metrics.stable_id if self.metrics is not None else "NO_RISK_METRICS"

        return (
            f"{self.reward_risk.stable_id}:"
            f"RISK_BUDGET_ADMISSION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{snapshot_fragment}:"
            f"{metrics_fragment}"
        )


class StrategyRiskBudgetAdmissionGate:
    """
    Pure account-risk budget admission gate.

    ADMITTED means position-size analysis may continue. It
    does not calculate volume or authorize an order.
    """

    def __init__(
        self,
        policy: RiskBudgetAdmissionPolicy | None = None,
    ) -> None:
        selected_policy = policy or RiskBudgetAdmissionPolicy()

        if not isinstance(
            selected_policy,
            RiskBudgetAdmissionPolicy,
        ):
            raise ValueError("policy must be a RiskBudgetAdmissionPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> RiskBudgetAdmissionPolicy:
        return self._policy

    def evaluate(
        self,
        reward_risk: RewardRiskAnalysisDecision,
        snapshot: StrategyRiskBudgetSnapshot | None = None,
    ) -> RiskBudgetAdmissionDecision:
        if not isinstance(
            reward_risk,
            RewardRiskAnalysisDecision,
        ):
            raise RiskBudgetAdmissionError(
                RiskBudgetAdmissionErrorReason.INVALID_REWARD_RISK_DECISION,
                "reward_risk must be a RewardRiskAnalysisDecision.",
            )

        if snapshot is not None and not isinstance(
            snapshot,
            StrategyRiskBudgetSnapshot,
        ):
            raise RiskBudgetAdmissionError(
                RiskBudgetAdmissionErrorReason.INVALID_RISK_SNAPSHOT,
                "snapshot must be a StrategyRiskBudgetSnapshot or None.",
            )

        evaluation = _derive_admission(
            reward_risk,
            snapshot,
            self._policy,
        )

        return RiskBudgetAdmissionDecision(
            reward_risk=reward_risk,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            snapshot=evaluation.snapshot,
            metrics=evaluation.metrics,
        )

    def admit(
        self,
        reward_risk: RewardRiskAnalysisDecision,
        snapshot: StrategyRiskBudgetSnapshot | None = None,
    ) -> RiskBudgetAdmissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            reward_risk,
            snapshot,
        )

    def check(
        self,
        reward_risk: RewardRiskAnalysisDecision,
        snapshot: StrategyRiskBudgetSnapshot | None = None,
    ) -> RiskBudgetAdmissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            reward_risk,
            snapshot,
        )


def evaluate_risk_budget_admission(
    reward_risk: RewardRiskAnalysisDecision,
    snapshot: StrategyRiskBudgetSnapshot | None = None,
    policy: RiskBudgetAdmissionPolicy | None = None,
) -> RiskBudgetAdmissionDecision:
    return StrategyRiskBudgetAdmissionGate(policy=policy).evaluate(
        reward_risk,
        snapshot,
    )


AccountRiskSnapshot = StrategyRiskBudgetSnapshot
RiskAdmissionBlocker = RiskBudgetAdmissionBlocker
RiskAdmissionDecision = RiskBudgetAdmissionDecision
RiskAdmissionGate = StrategyRiskBudgetAdmissionGate
RiskAdmissionPolicy = RiskBudgetAdmissionPolicy
RiskAdmissionReason = RiskBudgetAdmissionReason
RiskAdmissionStatus = RiskBudgetAdmissionStatus
StrategyRiskAdmissionGate = StrategyRiskBudgetAdmissionGate
