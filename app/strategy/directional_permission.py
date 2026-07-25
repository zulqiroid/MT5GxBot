from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.config.constants import TimeframeName
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextSnapshot,
)


class DirectionalPermissionStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class DirectionalPermissionDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"


class DirectionalPermissionReason(str, Enum):
    ALIGNED = "ALIGNED"
    HIGHER_TIMEFRAME_CONFLICT = "HIGHER_TIMEFRAME_CONFLICT"
    HIGHER_TIMEFRAME_UNRESOLVED = "HIGHER_TIMEFRAME_UNRESOLVED"
    NO_DOMINANT_DIRECTION = "NO_DOMINANT_DIRECTION"
    SETUP_TIMEFRAME_CONFLICT = "SETUP_TIMEFRAME_CONFLICT"
    SETUP_TIMEFRAME_NEUTRAL = "SETUP_TIMEFRAME_NEUTRAL"
    EXECUTION_TIMEFRAME_CONFLICT = "EXECUTION_TIMEFRAME_CONFLICT"
    EXECUTION_TIMEFRAME_NEUTRAL = "EXECUTION_TIMEFRAME_NEUTRAL"
    INSUFFICIENT_ALIGNMENT = "INSUFFICIENT_ALIGNMENT"


class DirectionalPermissionErrorReason(str, Enum):
    INVALID_CONTEXT = "INVALID_CONTEXT"


class DirectionalPermissionError(RuntimeError):
    """Structured directional-gate evaluation failure."""

    def __init__(
        self,
        reason: DirectionalPermissionErrorReason,
        message: str,
    ) -> None:
        self.reason = DirectionalPermissionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Directional permission error [{self.reason.value}]: {self.message}")


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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _direction_for_bias(
    bias: MarketStructureBias,
) -> DirectionalPermissionDirection:
    selected_bias = MarketStructureBias(bias)

    if selected_bias == MarketStructureBias.BULLISH:
        return DirectionalPermissionDirection.BULLISH

    if selected_bias == MarketStructureBias.BEARISH:
        return DirectionalPermissionDirection.BEARISH

    return DirectionalPermissionDirection.NONE


def _bias_for_direction(
    direction: DirectionalPermissionDirection,
) -> MarketStructureBias:
    selected_direction = DirectionalPermissionDirection(direction)

    if selected_direction == DirectionalPermissionDirection.BULLISH:
        return MarketStructureBias.BULLISH

    if selected_direction == DirectionalPermissionDirection.BEARISH:
        return MarketStructureBias.BEARISH

    return MarketStructureBias.NEUTRAL


@dataclass(frozen=True, slots=True)
class DirectionalPermissionPolicy:
    """
    Conservative multi-timeframe directional policy.

    This policy evaluates strategy direction only. It does
    not authorize broker-side trading.
    """

    require_higher_timeframe_alignment: bool = True
    minimum_aligned_timeframes: int = 3
    allow_neutral_setup_timeframe: bool = True
    allow_neutral_execution_timeframe: bool = True
    allow_opposing_setup_timeframe: bool = False
    allow_opposing_execution_timeframe: bool = False

    def __post_init__(self) -> None:
        require_higher_timeframe_alignment = _strict_boolean(
            self.require_higher_timeframe_alignment,
            "require_higher_timeframe_alignment",
        )
        minimum_aligned_timeframes = _positive_integer(
            self.minimum_aligned_timeframes,
            "minimum_aligned_timeframes",
            len(GOLD_TIMEFRAME_HIERARCHY),
        )
        allow_neutral_setup_timeframe = _strict_boolean(
            self.allow_neutral_setup_timeframe,
            "allow_neutral_setup_timeframe",
        )
        allow_neutral_execution_timeframe = _strict_boolean(
            self.allow_neutral_execution_timeframe,
            "allow_neutral_execution_timeframe",
        )
        allow_opposing_setup_timeframe = _strict_boolean(
            self.allow_opposing_setup_timeframe,
            "allow_opposing_setup_timeframe",
        )
        allow_opposing_execution_timeframe = _strict_boolean(
            self.allow_opposing_execution_timeframe,
            "allow_opposing_execution_timeframe",
        )

        object.__setattr__(
            self,
            "require_higher_timeframe_alignment",
            require_higher_timeframe_alignment,
        )
        object.__setattr__(
            self,
            "minimum_aligned_timeframes",
            minimum_aligned_timeframes,
        )
        object.__setattr__(
            self,
            "allow_neutral_setup_timeframe",
            allow_neutral_setup_timeframe,
        )
        object.__setattr__(
            self,
            "allow_neutral_execution_timeframe",
            allow_neutral_execution_timeframe,
        )
        object.__setattr__(
            self,
            "allow_opposing_setup_timeframe",
            allow_opposing_setup_timeframe,
        )
        object.__setattr__(
            self,
            "allow_opposing_execution_timeframe",
            allow_opposing_execution_timeframe,
        )


@dataclass(frozen=True, slots=True)
class _DirectionalEvaluation:
    status: DirectionalPermissionStatus
    direction: DirectionalPermissionDirection
    reason: DirectionalPermissionReason
    aligned_timeframes: tuple[TimeframeName, ...]
    opposing_timeframes: tuple[TimeframeName, ...]
    neutral_timeframes: tuple[TimeframeName, ...]


def _classify_timeframes(
    context: MultiTimeframeContextSnapshot,
    direction: DirectionalPermissionDirection,
) -> tuple[
    tuple[TimeframeName, ...],
    tuple[TimeframeName, ...],
    tuple[TimeframeName, ...],
]:
    selected_bias = _bias_for_direction(direction)
    opposite_bias = (
        MarketStructureBias.BEARISH
        if selected_bias == MarketStructureBias.BULLISH
        else MarketStructureBias.BULLISH
    )

    aligned = tuple(
        timeframe for timeframe, bias in context.structure_biases if bias == selected_bias
    )
    opposing = tuple(
        timeframe for timeframe, bias in context.structure_biases if bias == opposite_bias
    )
    neutral = tuple(
        timeframe
        for timeframe, bias in context.structure_biases
        if bias == MarketStructureBias.NEUTRAL
    )

    return aligned, opposing, neutral


def _blocked_evaluation(
    *,
    direction: DirectionalPermissionDirection,
    reason: DirectionalPermissionReason,
    context: MultiTimeframeContextSnapshot,
) -> _DirectionalEvaluation:
    if direction == DirectionalPermissionDirection.NONE:
        aligned: tuple[TimeframeName, ...] = ()
        opposing: tuple[TimeframeName, ...] = ()
        neutral = tuple(
            timeframe
            for timeframe, bias in context.structure_biases
            if bias == MarketStructureBias.NEUTRAL
        )
    else:
        aligned, opposing, neutral = _classify_timeframes(
            context,
            direction,
        )

    return _DirectionalEvaluation(
        status=DirectionalPermissionStatus.BLOCKED,
        direction=direction,
        reason=reason,
        aligned_timeframes=aligned,
        opposing_timeframes=opposing,
        neutral_timeframes=neutral,
    )


def _candidate_direction(
    context: MultiTimeframeContextSnapshot,
    policy: DirectionalPermissionPolicy,
) -> _DirectionalEvaluation | DirectionalPermissionDirection:
    biases = dict(context.structure_biases)
    h4_direction = _direction_for_bias(biases[TimeframeName.H4])
    h1_direction = _direction_for_bias(biases[TimeframeName.H1])

    if policy.require_higher_timeframe_alignment:
        if (
            h4_direction == DirectionalPermissionDirection.NONE
            or h1_direction == DirectionalPermissionDirection.NONE
        ):
            return _blocked_evaluation(
                direction=(DirectionalPermissionDirection.NONE),
                reason=(DirectionalPermissionReason.HIGHER_TIMEFRAME_UNRESOLVED),
                context=context,
            )

        if h4_direction != h1_direction:
            return _blocked_evaluation(
                direction=(DirectionalPermissionDirection.NONE),
                reason=(DirectionalPermissionReason.HIGHER_TIMEFRAME_CONFLICT),
                context=context,
            )

        return h4_direction

    bullish_count = sum(
        1 for _, bias in context.structure_biases if bias == MarketStructureBias.BULLISH
    )
    bearish_count = sum(
        1 for _, bias in context.structure_biases if bias == MarketStructureBias.BEARISH
    )

    if bullish_count == bearish_count:
        return _blocked_evaluation(
            direction=DirectionalPermissionDirection.NONE,
            reason=(DirectionalPermissionReason.NO_DOMINANT_DIRECTION),
            context=context,
        )

    if bullish_count > bearish_count:
        return DirectionalPermissionDirection.BULLISH

    return DirectionalPermissionDirection.BEARISH


def _evaluate_directional_permission(
    context: MultiTimeframeContextSnapshot,
    policy: DirectionalPermissionPolicy,
) -> _DirectionalEvaluation:
    candidate = _candidate_direction(
        context,
        policy,
    )

    if isinstance(
        candidate,
        _DirectionalEvaluation,
    ):
        return candidate

    direction = candidate
    aligned, opposing, neutral = _classify_timeframes(
        context,
        direction,
    )
    biases = dict(context.structure_biases)
    expected_bias = _bias_for_direction(direction)
    opposite_bias = (
        MarketStructureBias.BEARISH
        if expected_bias == MarketStructureBias.BULLISH
        else MarketStructureBias.BULLISH
    )

    setup_bias = biases[TimeframeName.M15]
    execution_bias = biases[TimeframeName.M5]

    if setup_bias == opposite_bias and not policy.allow_opposing_setup_timeframe:
        return _DirectionalEvaluation(
            status=DirectionalPermissionStatus.BLOCKED,
            direction=direction,
            reason=(DirectionalPermissionReason.SETUP_TIMEFRAME_CONFLICT),
            aligned_timeframes=aligned,
            opposing_timeframes=opposing,
            neutral_timeframes=neutral,
        )

    if setup_bias == MarketStructureBias.NEUTRAL and not policy.allow_neutral_setup_timeframe:
        return _DirectionalEvaluation(
            status=DirectionalPermissionStatus.BLOCKED,
            direction=direction,
            reason=(DirectionalPermissionReason.SETUP_TIMEFRAME_NEUTRAL),
            aligned_timeframes=aligned,
            opposing_timeframes=opposing,
            neutral_timeframes=neutral,
        )

    if execution_bias == opposite_bias and not policy.allow_opposing_execution_timeframe:
        return _DirectionalEvaluation(
            status=DirectionalPermissionStatus.BLOCKED,
            direction=direction,
            reason=(DirectionalPermissionReason.EXECUTION_TIMEFRAME_CONFLICT),
            aligned_timeframes=aligned,
            opposing_timeframes=opposing,
            neutral_timeframes=neutral,
        )

    if (
        execution_bias == MarketStructureBias.NEUTRAL
        and not policy.allow_neutral_execution_timeframe
    ):
        return _DirectionalEvaluation(
            status=DirectionalPermissionStatus.BLOCKED,
            direction=direction,
            reason=(DirectionalPermissionReason.EXECUTION_TIMEFRAME_NEUTRAL),
            aligned_timeframes=aligned,
            opposing_timeframes=opposing,
            neutral_timeframes=neutral,
        )

    if len(aligned) < policy.minimum_aligned_timeframes:
        return _DirectionalEvaluation(
            status=DirectionalPermissionStatus.BLOCKED,
            direction=direction,
            reason=(DirectionalPermissionReason.INSUFFICIENT_ALIGNMENT),
            aligned_timeframes=aligned,
            opposing_timeframes=opposing,
            neutral_timeframes=neutral,
        )

    return _DirectionalEvaluation(
        status=DirectionalPermissionStatus.ALLOWED,
        direction=direction,
        reason=DirectionalPermissionReason.ALIGNED,
        aligned_timeframes=aligned,
        opposing_timeframes=opposing,
        neutral_timeframes=neutral,
    )


@dataclass(frozen=True, slots=True)
class DirectionalPermissionDecision:
    """One validated strategy-direction decision."""

    context: MultiTimeframeContextSnapshot
    policy: DirectionalPermissionPolicy
    status: DirectionalPermissionStatus
    direction: DirectionalPermissionDirection
    reason: DirectionalPermissionReason
    aligned_timeframes: tuple[TimeframeName, ...]
    opposing_timeframes: tuple[TimeframeName, ...]
    neutral_timeframes: tuple[TimeframeName, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.context,
            MultiTimeframeContextSnapshot,
        ):
            raise ValueError("context must be a MultiTimeframeContextSnapshot.")

        if not isinstance(
            self.policy,
            DirectionalPermissionPolicy,
        ):
            raise ValueError("policy must be a DirectionalPermissionPolicy.")

        try:
            status = DirectionalPermissionStatus(self.status)
            direction = DirectionalPermissionDirection(self.direction)
            reason = DirectionalPermissionReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported directional permission status, direction, or reason."
            ) from error

        aligned_timeframes = tuple(self.aligned_timeframes)
        opposing_timeframes = tuple(self.opposing_timeframes)
        neutral_timeframes = tuple(self.neutral_timeframes)

        combined = aligned_timeframes + opposing_timeframes + neutral_timeframes

        for timeframe in combined:
            if not isinstance(timeframe, TimeframeName):
                raise ValueError(
                    "Directional timeframe collections must contain TimeframeName values."
                )

        if len(set(combined)) != len(combined):
            raise ValueError("A timeframe cannot belong to multiple directional collections.")

        expected = _evaluate_directional_permission(
            self.context,
            self.policy,
        )

        supplied = _DirectionalEvaluation(
            status=status,
            direction=direction,
            reason=reason,
            aligned_timeframes=aligned_timeframes,
            opposing_timeframes=opposing_timeframes,
            neutral_timeframes=neutral_timeframes,
        )

        if supplied != expected:
            raise ValueError(
                "Directional permission decision does not match its context and policy."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "direction",
            direction,
        )
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "aligned_timeframes",
            aligned_timeframes,
        )
        object.__setattr__(
            self,
            "opposing_timeframes",
            opposing_timeframes,
        )
        object.__setattr__(
            self,
            "neutral_timeframes",
            neutral_timeframes,
        )

    @property
    def broker_symbol(self) -> str:
        return self.context.broker_symbol

    @property
    def observed_at(self):
        return self.context.observed_at

    @property
    def is_allowed(self) -> bool:
        return self.status == DirectionalPermissionStatus.ALLOWED

    @property
    def is_blocked(self) -> bool:
        return not self.is_allowed

    @property
    def is_bullish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BEARISH

    @property
    def has_direction(self) -> bool:
        return self.direction != DirectionalPermissionDirection.NONE

    @property
    def aligned_count(self) -> int:
        return len(self.aligned_timeframes)

    @property
    def opposing_count(self) -> int:
        return len(self.opposing_timeframes)

    @property
    def neutral_count(self) -> int:
        return len(self.neutral_timeframes)

    @property
    def alignment_score(self) -> Decimal:
        return Decimal(self.aligned_count) / Decimal(len(GOLD_TIMEFRAME_HIERARCHY))

    @property
    def higher_timeframe_direction(
        self,
    ) -> DirectionalPermissionDirection:
        biases = dict(self.context.structure_biases)
        h4_direction = _direction_for_bias(biases[TimeframeName.H4])
        h1_direction = _direction_for_bias(biases[TimeframeName.H1])

        if h4_direction == h1_direction and h4_direction != DirectionalPermissionDirection.NONE:
            return h4_direction

        return DirectionalPermissionDirection.NONE

    @property
    def setup_bias(self) -> MarketStructureBias:
        return self.bias_for(TimeframeName.M15)

    @property
    def execution_bias(self) -> MarketStructureBias:
        return self.bias_for(TimeframeName.M5)

    def bias_for(
        self,
        timeframe: TimeframeName,
    ) -> MarketStructureBias:
        try:
            selected_timeframe = TimeframeName(timeframe)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported strategy timeframe: {timeframe}.") from error

        biases = dict(self.context.structure_biases)

        if selected_timeframe not in biases:
            raise ValueError("Timeframe is not part of this directional decision.")

        return biases[selected_timeframe]

    @property
    def stable_id(self) -> str:
        return (
            f"{self.context.stable_id}:"
            f"DIRECTIONAL_PERMISSION:"
            f"{self.status.value}:"
            f"{self.direction.value}:"
            f"{self.reason.value}"
        )


class MultiTimeframeDirectionalGate:
    """
    Pure multi-timeframe strategy-direction gate.

    An ALLOWED result is not broker trading permission.
    """

    def __init__(
        self,
        policy: DirectionalPermissionPolicy | None = None,
    ) -> None:
        selected_policy = policy or DirectionalPermissionPolicy()

        if not isinstance(
            selected_policy,
            DirectionalPermissionPolicy,
        ):
            raise ValueError("policy must be a DirectionalPermissionPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> DirectionalPermissionPolicy:
        return self._policy

    def evaluate(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> DirectionalPermissionDecision:
        if not isinstance(
            context,
            MultiTimeframeContextSnapshot,
        ):
            raise DirectionalPermissionError(
                DirectionalPermissionErrorReason.INVALID_CONTEXT,
                "context must be a MultiTimeframeContextSnapshot.",
            )

        evaluation = _evaluate_directional_permission(
            context,
            self._policy,
        )

        return DirectionalPermissionDecision(
            context=context,
            policy=self._policy,
            status=evaluation.status,
            direction=evaluation.direction,
            reason=evaluation.reason,
            aligned_timeframes=(evaluation.aligned_timeframes),
            opposing_timeframes=(evaluation.opposing_timeframes),
            neutral_timeframes=(evaluation.neutral_timeframes),
        )

    def decide(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> DirectionalPermissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(context)

    def check(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> DirectionalPermissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(context)


def evaluate_directional_permission(
    context: MultiTimeframeContextSnapshot,
    policy: DirectionalPermissionPolicy | None = None,
) -> DirectionalPermissionDecision:
    return MultiTimeframeDirectionalGate(policy=policy).evaluate(context)


DirectionalDecision = DirectionalPermissionDecision
DirectionalDirection = DirectionalPermissionDirection
DirectionalGate = MultiTimeframeDirectionalGate
DirectionalPolicy = DirectionalPermissionPolicy
DirectionalReason = DirectionalPermissionReason
DirectionalStatus = DirectionalPermissionStatus
MultiTimeframeBiasGate = MultiTimeframeDirectionalGate
