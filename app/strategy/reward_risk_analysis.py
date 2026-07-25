from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.price_reference_resolution import (
    PriceReferenceResolutionDecision,
)

_ZERO = Decimal("0")


class RewardRiskAnalysisStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    BLOCKED = "BLOCKED"


class RewardRiskAnalysisReason(str, Enum):
    QUALIFIED = "QUALIFIED"
    RESOLUTION_BLOCKED = "RESOLUTION_BLOCKED"
    ENTRY_VALUE_MISSING = "ENTRY_VALUE_MISSING"
    STOP_VALUE_MISSING = "STOP_VALUE_MISSING"
    TARGET_VALUE_MISSING = "TARGET_VALUE_MISSING"
    MULTIPLE_VALUES_MISSING = "MULTIPLE_VALUES_MISSING"
    INVALID_RISK_DISTANCE = "INVALID_RISK_DISTANCE"
    INVALID_REWARD_DISTANCE = "INVALID_REWARD_DISTANCE"
    MULTIPLE_DISTANCES_INVALID = "MULTIPLE_DISTANCES_INVALID"
    BELOW_MINIMUM_REWARD_RISK = "BELOW_MINIMUM_REWARD_RISK"


class RewardRiskAnalysisBlocker(str, Enum):
    RESOLUTION_BLOCKED = "RESOLUTION_BLOCKED"
    ENTRY_VALUE_MISSING = "ENTRY_VALUE_MISSING"
    STOP_VALUE_MISSING = "STOP_VALUE_MISSING"
    TARGET_VALUE_MISSING = "TARGET_VALUE_MISSING"
    INVALID_RISK_DISTANCE = "INVALID_RISK_DISTANCE"
    INVALID_REWARD_DISTANCE = "INVALID_REWARD_DISTANCE"
    BELOW_MINIMUM_REWARD_RISK = "BELOW_MINIMUM_REWARD_RISK"


class RewardRiskAnalysisErrorReason(str, Enum):
    INVALID_RESOLUTION_DECISION = "INVALID_RESOLUTION_DECISION"


class RewardRiskAnalysisError(RuntimeError):
    """Structured reward-to-risk analysis failure."""

    def __init__(
        self,
        reason: RewardRiskAnalysisErrorReason,
        message: str,
    ) -> None:
        self.reason = RewardRiskAnalysisErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Reward-to-risk analysis error [{self.reason.value}]: {self.message}")


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


@dataclass(frozen=True, slots=True)
class RewardRiskAnalysisPolicy:
    """
    Minimum reward-to-risk requirement.

    Qualification remains analytical and does not authorize
    position sizing, broker submission, or trading.
    """

    minimum_reward_risk: Decimal = Decimal("2")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_reward_risk",
            _positive_finite_decimal(
                self.minimum_reward_risk,
                "minimum_reward_risk",
            ),
        )


@dataclass(frozen=True, slots=True)
class RewardRiskMetrics:
    """Exact directional price-distance calculations."""

    direction: DirectionalPermissionDirection
    entry_value: Decimal
    stop_value: Decimal
    target_value: Decimal
    risk_distance: Decimal
    reward_distance: Decimal
    reward_risk_ratio: Decimal

    def __post_init__(self) -> None:
        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if self.direction == DirectionalPermissionDirection.NONE:
            raise ValueError(
                "Reward-to-risk metrics require a resolved bullish or bearish direction."
            )

        for field_name in (
            "entry_value",
            "stop_value",
            "target_value",
            "risk_distance",
            "reward_distance",
            "reward_risk_ratio",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_finite_decimal(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.direction == DirectionalPermissionDirection.BULLISH:
            expected_risk = self.entry_value - self.stop_value
            expected_reward = self.target_value - self.entry_value
        else:
            expected_risk = self.stop_value - self.entry_value
            expected_reward = self.entry_value - self.target_value

        if expected_risk <= _ZERO:
            raise ValueError("Directional risk distance must be greater than zero.")

        if expected_reward <= _ZERO:
            raise ValueError("Directional reward distance must be greater than zero.")

        expected_ratio = expected_reward / expected_risk

        if self.risk_distance != expected_risk:
            raise ValueError("risk_distance does not match the directional prices.")

        if self.reward_distance != expected_reward:
            raise ValueError("reward_distance does not match the directional prices.")

        if self.reward_risk_ratio != expected_ratio:
            raise ValueError("reward_risk_ratio does not match the directional distances.")

    @property
    def stable_id(self) -> str:
        return (
            f"{self.direction.value}:"
            f"ENTRY[{self.entry_value}]:"
            f"STOP[{self.stop_value}]:"
            f"TARGET[{self.target_value}]:"
            f"RISK[{self.risk_distance}]:"
            f"REWARD[{self.reward_distance}]:"
            f"RR[{self.reward_risk_ratio}]"
        )


@dataclass(frozen=True, slots=True)
class _RewardRiskEvaluation:
    status: RewardRiskAnalysisStatus
    reason: RewardRiskAnalysisReason
    blockers: tuple[
        RewardRiskAnalysisBlocker,
        ...,
    ]
    metrics: RewardRiskMetrics | None


_MISSING_REASON_MAP = {
    RewardRiskAnalysisBlocker.ENTRY_VALUE_MISSING: (RewardRiskAnalysisReason.ENTRY_VALUE_MISSING),
    RewardRiskAnalysisBlocker.STOP_VALUE_MISSING: (RewardRiskAnalysisReason.STOP_VALUE_MISSING),
    RewardRiskAnalysisBlocker.TARGET_VALUE_MISSING: (RewardRiskAnalysisReason.TARGET_VALUE_MISSING),
}

_DISTANCE_REASON_MAP = {
    RewardRiskAnalysisBlocker.INVALID_RISK_DISTANCE: (
        RewardRiskAnalysisReason.INVALID_RISK_DISTANCE
    ),
    RewardRiskAnalysisBlocker.INVALID_REWARD_DISTANCE: (
        RewardRiskAnalysisReason.INVALID_REWARD_DISTANCE
    ),
}


def _missing_reason(
    blockers: tuple[
        RewardRiskAnalysisBlocker,
        ...,
    ],
) -> RewardRiskAnalysisReason:
    if len(blockers) == 1:
        return _MISSING_REASON_MAP[blockers[0]]

    return RewardRiskAnalysisReason.MULTIPLE_VALUES_MISSING


def _distance_reason(
    blockers: tuple[
        RewardRiskAnalysisBlocker,
        ...,
    ],
) -> RewardRiskAnalysisReason:
    if len(blockers) == 1:
        return _DISTANCE_REASON_MAP[blockers[0]]

    return RewardRiskAnalysisReason.MULTIPLE_DISTANCES_INVALID


def _derive_reward_risk(
    resolution: PriceReferenceResolutionDecision,
    policy: RewardRiskAnalysisPolicy,
) -> _RewardRiskEvaluation:
    if resolution.is_blocked:
        return _RewardRiskEvaluation(
            status=RewardRiskAnalysisStatus.BLOCKED,
            reason=(RewardRiskAnalysisReason.RESOLUTION_BLOCKED),
            blockers=(RewardRiskAnalysisBlocker.RESOLUTION_BLOCKED,),
            metrics=None,
        )

    entry_value = resolution.entry_value
    stop_value = resolution.stop_value
    target_value = resolution.target_value
    missing_blockers: list[RewardRiskAnalysisBlocker] = []

    if entry_value is None:
        missing_blockers.append(RewardRiskAnalysisBlocker.ENTRY_VALUE_MISSING)

    if stop_value is None:
        missing_blockers.append(RewardRiskAnalysisBlocker.STOP_VALUE_MISSING)

    if target_value is None:
        missing_blockers.append(RewardRiskAnalysisBlocker.TARGET_VALUE_MISSING)

    if missing_blockers:
        blocker_tuple = tuple(missing_blockers)

        return _RewardRiskEvaluation(
            status=RewardRiskAnalysisStatus.BLOCKED,
            reason=_missing_reason(blocker_tuple),
            blockers=blocker_tuple,
            metrics=None,
        )

    assert entry_value is not None
    assert stop_value is not None
    assert target_value is not None

    if resolution.direction == DirectionalPermissionDirection.BULLISH:
        risk_distance = entry_value - stop_value
        reward_distance = target_value - entry_value
    elif resolution.direction == DirectionalPermissionDirection.BEARISH:
        risk_distance = stop_value - entry_value
        reward_distance = entry_value - target_value
    else:
        risk_distance = _ZERO
        reward_distance = _ZERO

    distance_blockers: list[RewardRiskAnalysisBlocker] = []

    if risk_distance <= _ZERO:
        distance_blockers.append(RewardRiskAnalysisBlocker.INVALID_RISK_DISTANCE)

    if reward_distance <= _ZERO:
        distance_blockers.append(RewardRiskAnalysisBlocker.INVALID_REWARD_DISTANCE)

    if distance_blockers:
        blocker_tuple = tuple(distance_blockers)

        return _RewardRiskEvaluation(
            status=RewardRiskAnalysisStatus.BLOCKED,
            reason=_distance_reason(blocker_tuple),
            blockers=blocker_tuple,
            metrics=None,
        )

    metrics = RewardRiskMetrics(
        direction=resolution.direction,
        entry_value=entry_value,
        stop_value=stop_value,
        target_value=target_value,
        risk_distance=risk_distance,
        reward_distance=reward_distance,
        reward_risk_ratio=(reward_distance / risk_distance),
    )

    if metrics.reward_risk_ratio < policy.minimum_reward_risk:
        return _RewardRiskEvaluation(
            status=RewardRiskAnalysisStatus.BLOCKED,
            reason=(RewardRiskAnalysisReason.BELOW_MINIMUM_REWARD_RISK),
            blockers=(RewardRiskAnalysisBlocker.BELOW_MINIMUM_REWARD_RISK,),
            metrics=metrics,
        )

    return _RewardRiskEvaluation(
        status=RewardRiskAnalysisStatus.QUALIFIED,
        reason=RewardRiskAnalysisReason.QUALIFIED,
        blockers=(),
        metrics=metrics,
    )


@dataclass(frozen=True, slots=True)
class RewardRiskAnalysisDecision:
    """Validated analytical reward-to-risk decision."""

    resolution: PriceReferenceResolutionDecision
    policy: RewardRiskAnalysisPolicy
    status: RewardRiskAnalysisStatus
    reason: RewardRiskAnalysisReason
    blockers: tuple[
        RewardRiskAnalysisBlocker,
        ...,
    ]
    metrics: RewardRiskMetrics | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.resolution,
            PriceReferenceResolutionDecision,
        ):
            raise ValueError("resolution must be a PriceReferenceResolutionDecision.")

        if not isinstance(
            self.policy,
            RewardRiskAnalysisPolicy,
        ):
            raise ValueError("policy must be a RewardRiskAnalysisPolicy.")

        try:
            status = RewardRiskAnalysisStatus(self.status)
            reason = RewardRiskAnalysisReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported reward-to-risk status or reason.") from error

        blockers = tuple(RewardRiskAnalysisBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Reward-to-risk blockers cannot contain duplicates.")

        if self.metrics is not None and not isinstance(
            self.metrics,
            RewardRiskMetrics,
        ):
            raise ValueError("metrics must be RewardRiskMetrics or None.")

        expected = _derive_reward_risk(
            self.resolution,
            self.policy,
        )
        supplied = _RewardRiskEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            metrics=self.metrics,
        )

        if supplied != expected:
            raise ValueError("Reward-to-risk decision does not match its resolution and policy.")

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
        return self.resolution.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.resolution.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.resolution.direction

    @property
    def entry_value(self) -> Decimal | None:
        return self.resolution.entry_value

    @property
    def stop_value(self) -> Decimal | None:
        return self.resolution.stop_value

    @property
    def target_value(self) -> Decimal | None:
        return self.resolution.target_value

    @property
    def risk_distance(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.risk_distance

    @property
    def reward_distance(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.reward_distance

    @property
    def reward_risk_ratio(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.reward_risk_ratio

    @property
    def minimum_reward_risk(self) -> Decimal:
        return self.policy.minimum_reward_risk

    @property
    def is_qualified(self) -> bool:
        return self.status == RewardRiskAnalysisStatus.QUALIFIED

    @property
    def is_blocked(self) -> bool:
        return not self.is_qualified

    @property
    def has_metrics(self) -> bool:
        return self.metrics is not None

    @property
    def can_continue_to_risk_admission(self) -> bool:
        return self.is_qualified

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
        metrics_fragment = self.metrics.stable_id if self.metrics is not None else "NO_METRICS"

        return (
            f"{self.resolution.stable_id}:"
            f"REWARD_RISK_ANALYSIS:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{metrics_fragment}"
        )


class StrategyRewardRiskAnalysisGate:
    """
    Pure reward-to-risk qualification gate.

    QUALIFIED means later risk-admission analysis may
    continue. It does not calculate volume or authorize an
    order.
    """

    def __init__(
        self,
        policy: RewardRiskAnalysisPolicy | None = None,
    ) -> None:
        selected_policy = policy or RewardRiskAnalysisPolicy()

        if not isinstance(
            selected_policy,
            RewardRiskAnalysisPolicy,
        ):
            raise ValueError("policy must be a RewardRiskAnalysisPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> RewardRiskAnalysisPolicy:
        return self._policy

    def evaluate(
        self,
        resolution: PriceReferenceResolutionDecision,
    ) -> RewardRiskAnalysisDecision:
        if not isinstance(
            resolution,
            PriceReferenceResolutionDecision,
        ):
            raise RewardRiskAnalysisError(
                RewardRiskAnalysisErrorReason.INVALID_RESOLUTION_DECISION,
                "resolution must be a PriceReferenceResolutionDecision.",
            )

        evaluation = _derive_reward_risk(
            resolution,
            self._policy,
        )

        return RewardRiskAnalysisDecision(
            resolution=resolution,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            metrics=evaluation.metrics,
        )

    def qualify(
        self,
        resolution: PriceReferenceResolutionDecision,
    ) -> RewardRiskAnalysisDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(resolution)

    def analyze(
        self,
        resolution: PriceReferenceResolutionDecision,
    ) -> RewardRiskAnalysisDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(resolution)


def evaluate_reward_risk(
    resolution: PriceReferenceResolutionDecision,
    policy: RewardRiskAnalysisPolicy | None = None,
) -> RewardRiskAnalysisDecision:
    return StrategyRewardRiskAnalysisGate(policy=policy).evaluate(resolution)


RewardRiskBlocker = RewardRiskAnalysisBlocker
RewardRiskDecision = RewardRiskAnalysisDecision
RewardRiskGate = StrategyRewardRiskAnalysisGate
RewardRiskPolicy = RewardRiskAnalysisPolicy
RewardRiskReason = RewardRiskAnalysisReason
RewardRiskStatus = RewardRiskAnalysisStatus
StrategyRewardRiskGate = StrategyRewardRiskAnalysisGate
