from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.phase8_closed_candle_data_contract import (
    StrategyPhase8ClosedCandleDataContract,
)
from app.strategy.phase8_closed_candle_snapshot import (
    StrategyPhase8ClosedCandleSnapshot,
)
from app.strategy.phase8_closed_candle_snapshot_verification import (
    StrategyPhase8ClosedCandleSnapshotVerificationReceipt,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
    StrategyPhase8DryRunPackage,
)
from app.strategy.phase8_offline_replay_advanced_session_state import (
    Phase8OfflineReplayAdvancedSessionStateDecision,
    StrategyPhase8OfflineReplayAdvancedSessionState,
)
from app.strategy.phase8_offline_replay_event_contract import (
    StrategyPhase8OfflineReplayEventContract,
)
from app.strategy.phase8_offline_replay_event_materialization import (
    Phase8OfflineReplayEvent,
    StrategyPhase8OfflineReplayEventBatch,
)
from app.strategy.phase8_offline_replay_event_materialization_plan import (
    StrategyPhase8OfflineReplayEventMaterializationPlan,
)
from app.strategy.phase8_offline_replay_plan import (
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_replay_session_contract import (
    StrategyPhase8OfflineReplaySessionContract,
)
from app.strategy.phase8_offline_replay_session_plan import (
    StrategyPhase8OfflineReplaySessionPlan,
)
from app.strategy.phase8_offline_replay_session_state import (
    StrategyPhase8OfflineReplaySessionState,
)
from app.strategy.phase8_offline_replay_transition_application import (
    StrategyPhase8OfflineReplayTransitionApplicationReceipt,
)
from app.strategy.phase8_offline_replay_transition_contract import (
    StrategyPhase8OfflineReplayTransitionContract,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_CONTRACT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplayNextTransitionContractMode(
    str,
    Enum,
):
    IMMUTABLE_SINGLE_EVENT = "IMMUTABLE_SINGLE_EVENT"


class Phase8OfflineReplayNextTransitionAction(
    str,
    Enum,
):
    CONSUME_CURRENT_EVENT = "CONSUME_CURRENT_EVENT"


class Phase8OfflineReplayNextTransitionCursorRule(
    str,
    Enum,
):
    INCREMENT_BY_ONE = "INCREMENT_BY_ONE"


class Phase8OfflineReplayNextTransitionCounterRule(
    str,
    Enum,
):
    CONSUMED_PLUS_REMAINING_EQUALS_TOTAL = "CONSUMED_PLUS_REMAINING_EQUALS_TOTAL"


class Phase8OfflineReplayNextTransitionContractStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayNextTransitionContractReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    ADVANCED_STATE_BLOCKED = "ADVANCED_STATE_BLOCKED"


class Phase8OfflineReplayNextTransitionContractBlocker(
    str,
    Enum,
):
    ADVANCED_STATE_BLOCKED = "ADVANCED_STATE_BLOCKED"


class Phase8OfflineReplayNextTransitionContractErrorReason(
    str,
    Enum,
):
    INVALID_ADVANCED_STATE_DECISION = "INVALID_ADVANCED_STATE_DECISION"


class Phase8OfflineReplayNextTransitionContractError(
    RuntimeError,
):
    """Structured next-transition contract failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayNextTransitionContractErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayNextTransitionContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 next offline replay-transition "
            f"contract error [{self.reason.value}]: "
            f"{self.message}"
        )


def _non_empty_string(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    return normalized


def _aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


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


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _canonical_datetime(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def _is_gold_symbol(symbol: str) -> bool:
    return symbol.upper().startswith("XAUUSD")


def _has_safe_external_boundary(subject: object) -> bool:
    required_false_attributes = (
        "has_adapter_instance",
        "request_submission_authorized",
        "adapter_invocation_authorized",
        "storage_write_authorized",
        "can_write_storage",
        "can_write_network",
        "execution_authorized",
        "has_broker_request",
        "can_submit_order",
        "is_executable",
    )

    for attribute_name in required_false_attributes:
        if not hasattr(subject, attribute_name):
            return False

        if getattr(subject, attribute_name):
            return False

    for optional_false_attribute in (
        "fetches_data",
        "executes_simulation",
        "executes_replay",
        "evaluates_strategy",
        "emits_orders",
        "starts_session",
        "starts_replay",
    ):
        if hasattr(subject, optional_false_attribute) and getattr(
            subject, optional_false_attribute
        ):
            return False

    if not hasattr(subject, "initializes_mt5"):
        return False

    if getattr(subject, "initializes_mt5"):
        return False

    return True


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayNextTransitionContractPolicy:
    """Strict next single-event transition requirements."""

    advanced_state_immutable: bool = True
    prior_transition_verified: bool = True
    current_event_bound: bool = True
    continuity_verified: bool = True
    one_event_transition: bool = True
    cursor_increment_by_one: bool = True
    counters_remain_consistent: bool = True
    next_event_bound: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "advanced_state_immutable",
            "prior_transition_verified",
            "current_event_bound",
            "continuity_verified",
            "one_event_transition",
            "cursor_increment_by_one",
            "counters_remain_consistent",
            "next_event_bound",
            "in_memory_only",
            "no_lookahead",
            "no_external_io",
        ):
            object.__setattr__(
                self,
                field_name,
                _strict_boolean(
                    getattr(self, field_name),
                    field_name,
                ),
            )

    @property
    def is_strict(self) -> bool:
        return all(
            (
                self.advanced_state_immutable,
                self.prior_transition_verified,
                self.current_event_bound,
                self.continuity_verified,
                self.one_event_transition,
                self.cursor_increment_by_one,
                self.counters_remain_consistent,
                self.next_event_bound,
                self.in_memory_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_transition_payload(
    *,
    schema_version: str,
    advanced_state_id: str,
    advanced_state_digest: str,
    application_receipt_id: str,
    application_digest: str,
    prior_transition_contract_id: str,
    prior_transition_contract_digest: str,
    source_state_id: str,
    source_state_digest: str,
    session_contract_id: str,
    session_contract_digest: str,
    session_plan_id: str,
    session_plan_digest: str,
    event_batch_id: str,
    event_batch_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    contract_mode: (Phase8OfflineReplayNextTransitionContractMode),
    action: Phase8OfflineReplayNextTransitionAction,
    cursor_rule: (Phase8OfflineReplayNextTransitionCursorRule),
    counter_rule: (Phase8OfflineReplayNextTransitionCounterRule),
    transition_index: int,
    current_cursor_index: int,
    current_consumed_count: int,
    current_remaining_count: int,
    prior_last_consumed_sequence_index: int,
    current_event_sequence_index: int,
    current_event_id: str,
    current_event_digest: str,
    current_event_time: datetime,
    current_event_timeframe: Phase8Timeframe,
    resulting_cursor_index: int,
    resulting_consumed_count: int,
    resulting_remaining_count: int,
    last_consumed_sequence_index: int,
    completion_after_transition: bool,
    next_event_sequence_index: int,
    next_event_id: str,
    next_event_digest: str,
    next_event_time: datetime,
    next_event_timeframe: Phase8Timeframe,
    total_event_count: int,
    policy: Phase8OfflineReplayNextTransitionContractPolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"ADVANCED_STATE_ID={advanced_state_id}",
            f"ADVANCED_STATE_DIGEST={advanced_state_digest}",
            f"APPLICATION_RECEIPT_ID={application_receipt_id}",
            f"APPLICATION_DIGEST={application_digest}",
            (f"PRIOR_TRANSITION_CONTRACT_ID={prior_transition_contract_id}"),
            (f"PRIOR_TRANSITION_CONTRACT_DIGEST={prior_transition_contract_digest}"),
            f"SOURCE_STATE_ID={source_state_id}",
            f"SOURCE_STATE_DIGEST={source_state_digest}",
            f"SESSION_CONTRACT_ID={session_contract_id}",
            (f"SESSION_CONTRACT_DIGEST={session_contract_digest}"),
            f"SESSION_PLAN_ID={session_plan_id}",
            f"SESSION_PLAN_DIGEST={session_plan_digest}",
            f"EVENT_BATCH_ID={event_batch_id}",
            f"EVENT_BATCH_DIGEST={event_batch_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"SOURCE_NAME={source_name}",
            (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
            ("TIMEFRAMES=" + ",".join(timeframe.value for timeframe in timeframes)),
            f"CONTRACT_MODE={contract_mode.value}",
            f"ACTION={action.value}",
            f"CURSOR_RULE={cursor_rule.value}",
            f"COUNTER_RULE={counter_rule.value}",
            f"TRANSITION_INDEX={transition_index}",
            f"CURRENT_CURSOR_INDEX={current_cursor_index}",
            (f"CURRENT_CONSUMED_COUNT={current_consumed_count}"),
            (f"CURRENT_REMAINING_COUNT={current_remaining_count}"),
            (f"PRIOR_LAST_CONSUMED_SEQUENCE_INDEX={prior_last_consumed_sequence_index}"),
            (f"CURRENT_EVENT_SEQUENCE_INDEX={current_event_sequence_index}"),
            f"CURRENT_EVENT_ID={current_event_id}",
            f"CURRENT_EVENT_DIGEST={current_event_digest}",
            (f"CURRENT_EVENT_TIME={_canonical_datetime(current_event_time)}"),
            (f"CURRENT_EVENT_TIMEFRAME={current_event_timeframe.value}"),
            (f"RESULTING_CURSOR_INDEX={resulting_cursor_index}"),
            (f"RESULTING_CONSUMED_COUNT={resulting_consumed_count}"),
            (f"RESULTING_REMAINING_COUNT={resulting_remaining_count}"),
            (f"LAST_CONSUMED_SEQUENCE_INDEX={last_consumed_sequence_index}"),
            (f"COMPLETION_AFTER_TRANSITION={str(completion_after_transition).lower()}"),
            (f"NEXT_EVENT_SEQUENCE_INDEX={next_event_sequence_index}"),
            f"NEXT_EVENT_ID={next_event_id}",
            f"NEXT_EVENT_DIGEST={next_event_digest}",
            (f"NEXT_EVENT_TIME={_canonical_datetime(next_event_time)}"),
            (f"NEXT_EVENT_TIMEFRAME={next_event_timeframe.value}"),
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"ADVANCED_STATE_IMMUTABLE={str(policy.advanced_state_immutable).lower()}"),
            (f"PRIOR_TRANSITION_VERIFIED={str(policy.prior_transition_verified).lower()}"),
            (f"CURRENT_EVENT_BOUND={str(policy.current_event_bound).lower()}"),
            (f"CONTINUITY_VERIFIED={str(policy.continuity_verified).lower()}"),
            (f"ONE_EVENT_TRANSITION={str(policy.one_event_transition).lower()}"),
            (f"CURSOR_INCREMENT_BY_ONE={str(policy.cursor_increment_by_one).lower()}"),
            (f"COUNTERS_REMAIN_CONSISTENT={str(policy.counters_remain_consistent).lower()}"),
            (f"NEXT_EVENT_BOUND={str(policy.next_event_bound).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "NEXT_TRANSITION_CONTRACT_CREATED=true",
            "TRANSITION_EXECUTED=false",
            "ADDITIONAL_EVENT_CONSUMPTION=false",
            "ADDITIONAL_CURSOR_ADVANCEMENT=false",
            "NEXT_STATE_CREATED=false",
            "REPLAY_EXECUTION=false",
            "STRATEGY_EVALUATION=false",
            "SIMULATION_EXECUTION=false",
            "DATA_FETCH=false",
            "MT5_INITIALIZATION=false",
            "ADAPTER_INVOCATION=false",
            "STORAGE_WRITE=false",
            "NETWORK_WRITE=false",
            "BROKER_WRITE=false",
            "ORDER_SUBMISSION=false",
            "EXECUTION_AUTHORIZED=false",
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPhase8OfflineReplayNextTransitionContract:
    """
    Immutable contract for the transition after the first.

    It binds the advanced cursor to the current event and
    defines the expected next cursor, counters and following
    event. It does not apply the transition or perform any
    external execution.
    """

    advanced_state_decision: Phase8OfflineReplayAdvancedSessionStateDecision = field(repr=False)
    policy: Phase8OfflineReplayNextTransitionContractPolicy
    schema_version: str
    advanced_state_id: str
    advanced_state_digest: str
    application_receipt_id: str
    application_digest: str
    prior_transition_contract_id: str
    prior_transition_contract_digest: str
    source_state_id: str
    source_state_digest: str
    session_contract_id: str
    session_contract_digest: str
    session_plan_id: str
    session_plan_digest: str
    event_batch_id: str
    event_batch_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    contract_mode: Phase8OfflineReplayNextTransitionContractMode
    action: Phase8OfflineReplayNextTransitionAction
    cursor_rule: Phase8OfflineReplayNextTransitionCursorRule
    counter_rule: Phase8OfflineReplayNextTransitionCounterRule
    transition_index: int
    current_cursor_index: int
    current_consumed_count: int
    current_remaining_count: int
    prior_last_consumed_sequence_index: int
    current_event_sequence_index: int
    current_event_id: str
    current_event_digest: str
    current_event_time: datetime
    current_event_timeframe: Phase8Timeframe
    resulting_cursor_index: int
    resulting_consumed_count: int
    resulting_remaining_count: int
    last_consumed_sequence_index: int
    completion_after_transition: bool
    next_event_sequence_index: int
    next_event_id: str
    next_event_digest: str
    next_event_time: datetime
    next_event_timeframe: Phase8Timeframe
    total_event_count: int
    transition_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.advanced_state_decision,
            Phase8OfflineReplayAdvancedSessionStateDecision,
        ):
            raise ValueError(
                "advanced_state_decision must be a Phase8OfflineReplayAdvancedSessionStateDecision."
            )

        if not self.advanced_state_decision.is_created:
            raise ValueError(
                "A next-transition contract requires a created advanced session state."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplayNextTransitionContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayNextTransitionContractPolicy.")

        if not self.policy.is_strict:
            raise ValueError("Next-transition policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current next-transition contract schema."
            )

        string_fields = (
            ("advanced_state_id", self.advanced_state_id),
            (
                "advanced_state_digest",
                self.advanced_state_digest,
            ),
            (
                "application_receipt_id",
                self.application_receipt_id,
            ),
            ("application_digest", self.application_digest),
            (
                "prior_transition_contract_id",
                self.prior_transition_contract_id,
            ),
            (
                "prior_transition_contract_digest",
                self.prior_transition_contract_digest,
            ),
            ("source_state_id", self.source_state_id),
            (
                "source_state_digest",
                self.source_state_digest,
            ),
            (
                "session_contract_id",
                self.session_contract_id,
            ),
            (
                "session_contract_digest",
                self.session_contract_digest,
            ),
            ("session_plan_id", self.session_plan_id),
            (
                "session_plan_digest",
                self.session_plan_digest,
            ),
            ("event_batch_id", self.event_batch_id),
            ("event_batch_digest", self.event_batch_digest),
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            ("current_event_id", self.current_event_id),
            (
                "current_event_digest",
                self.current_event_digest,
            ),
            ("next_event_id", self.next_event_id),
            ("next_event_digest", self.next_event_digest),
            ("transition_digest", self.transition_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "advanced_state_digest",
            "application_digest",
            "prior_transition_contract_digest",
            "source_state_digest",
            "session_contract_digest",
            "session_plan_digest",
            "event_batch_digest",
            "current_event_digest",
            "next_event_digest",
            "transition_digest",
        ):
            if not _is_lowercase_sha256(normalized_strings[field_name]):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if not isinstance(self.side, StrategyOrderSide):
            raise ValueError("side must be a StrategyOrderSide member.")

        enum_fields = (
            (
                "contract_mode",
                self.contract_mode,
                Phase8OfflineReplayNextTransitionContractMode,
            ),
            (
                "action",
                self.action,
                Phase8OfflineReplayNextTransitionAction,
            ),
            (
                "cursor_rule",
                self.cursor_rule,
                Phase8OfflineReplayNextTransitionCursorRule,
            ),
            (
                "counter_rule",
                self.counter_rule,
                Phase8OfflineReplayNextTransitionCounterRule,
            ),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{field_name} must be a {enum_type.__name__} member.")

        if self.contract_mode != (
            Phase8OfflineReplayNextTransitionContractMode.IMMUTABLE_SINGLE_EVENT
        ):
            raise ValueError("contract_mode must remain IMMUTABLE_SINGLE_EVENT.")

        if self.action != (Phase8OfflineReplayNextTransitionAction.CONSUME_CURRENT_EVENT):
            raise ValueError("action must remain CONSUME_CURRENT_EVENT.")

        if self.cursor_rule != (Phase8OfflineReplayNextTransitionCursorRule.INCREMENT_BY_ONE):
            raise ValueError("cursor_rule must remain INCREMENT_BY_ONE.")

        if self.counter_rule != (
            Phase8OfflineReplayNextTransitionCounterRule.CONSUMED_PLUS_REMAINING_EQUALS_TOTAL
        ):
            raise ValueError("counter_rule must preserve the exact counter invariant.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        if not isinstance(
            self.current_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("current_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(
            self.next_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("next_event_timeframe must be a Phase8Timeframe member.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        current_event_time = _aware_datetime(
            self.current_event_time,
            "current_event_time",
        )
        next_event_time = _aware_datetime(
            self.next_event_time,
            "next_event_time",
        )

        if current_event_time > captured_at:
            raise ValueError("current_event_time cannot exceed captured_at.")

        if next_event_time > captured_at:
            raise ValueError("next_event_time cannot exceed captured_at.")

        if next_event_time < current_event_time:
            raise ValueError("next_event_time cannot precede the current event.")

        transition_index = _positive_integer(
            self.transition_index,
            "transition_index",
        )
        current_cursor_index = _positive_integer(
            self.current_cursor_index,
            "current_cursor_index",
        )
        current_consumed_count = _positive_integer(
            self.current_consumed_count,
            "current_consumed_count",
        )
        current_remaining_count = _positive_integer(
            self.current_remaining_count,
            "current_remaining_count",
        )
        prior_last_consumed_sequence_index = _non_negative_integer(
            self.prior_last_consumed_sequence_index,
            "prior_last_consumed_sequence_index",
        )
        current_event_sequence_index = _positive_integer(
            self.current_event_sequence_index,
            "current_event_sequence_index",
        )
        resulting_cursor_index = _positive_integer(
            self.resulting_cursor_index,
            "resulting_cursor_index",
        )
        resulting_consumed_count = _positive_integer(
            self.resulting_consumed_count,
            "resulting_consumed_count",
        )
        resulting_remaining_count = _positive_integer(
            self.resulting_remaining_count,
            "resulting_remaining_count",
        )
        last_consumed_sequence_index = _positive_integer(
            self.last_consumed_sequence_index,
            "last_consumed_sequence_index",
        )
        next_event_sequence_index = _positive_integer(
            self.next_event_sequence_index,
            "next_event_sequence_index",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )
        completion_after_transition = _strict_boolean(
            self.completion_after_transition,
            "completion_after_transition",
        )

        if transition_index != current_consumed_count:
            raise ValueError("transition_index must equal the current consumed count.")

        if current_cursor_index != current_consumed_count:
            raise ValueError("current_cursor_index must equal the current consumed count.")

        if current_consumed_count + current_remaining_count != total_event_count:
            raise ValueError("Current counters must preserve total_event_count.")

        if prior_last_consumed_sequence_index != (current_cursor_index - 1):
            raise ValueError(
                "prior_last_consumed_sequence_index must equal current_cursor_index minus one."
            )

        if current_event_sequence_index != (current_cursor_index):
            raise ValueError("current_event_sequence_index must equal current_cursor_index.")

        if current_event_sequence_index != (prior_last_consumed_sequence_index + 1):
            raise ValueError("Current-event sequence continuity is invalid.")

        if resulting_cursor_index != (current_cursor_index + 1):
            raise ValueError("resulting_cursor_index must increment by exactly one.")

        if resulting_consumed_count != (current_consumed_count + 1):
            raise ValueError("resulting_consumed_count must increment by exactly one.")

        if resulting_remaining_count != (current_remaining_count - 1):
            raise ValueError("resulting_remaining_count must decrement by exactly one.")

        if resulting_consumed_count + resulting_remaining_count != total_event_count:
            raise ValueError("Resulting counters must preserve total_event_count.")

        if last_consumed_sequence_index != (current_event_sequence_index):
            raise ValueError("last_consumed_sequence_index must equal the current event sequence.")

        expected_completion = resulting_cursor_index == total_event_count

        if completion_after_transition != expected_completion:
            raise ValueError("completion_after_transition does not match the resulting cursor.")

        if completion_after_transition:
            raise ValueError("The next transition cannot complete this 800-event replay session.")

        if next_event_sequence_index != (resulting_cursor_index):
            raise ValueError("next_event_sequence_index must equal the resulting cursor.")

        advanced_state = self.advanced_state_decision.state_required
        application_receipt = advanced_state.application_receipt
        prior_transition_contract = advanced_state.transition_contract
        source_state = advanced_state.source_state
        session_contract = advanced_state.session_contract
        session_plan = advanced_state.session_plan
        event_batch = advanced_state.event_batch

        comparisons = (
            (
                "advanced_state_id",
                normalized_strings["advanced_state_id"],
                advanced_state.stable_id,
            ),
            (
                "advanced_state_digest",
                normalized_strings["advanced_state_digest"],
                advanced_state.state_digest,
            ),
            (
                "application_receipt_id",
                normalized_strings["application_receipt_id"],
                application_receipt.stable_id,
            ),
            (
                "application_digest",
                normalized_strings["application_digest"],
                application_receipt.application_digest,
            ),
            (
                "prior_transition_contract_id",
                normalized_strings["prior_transition_contract_id"],
                prior_transition_contract.stable_id,
            ),
            (
                "prior_transition_contract_digest",
                normalized_strings["prior_transition_contract_digest"],
                prior_transition_contract.transition_digest,
            ),
            (
                "source_state_id",
                normalized_strings["source_state_id"],
                source_state.stable_id,
            ),
            (
                "source_state_digest",
                normalized_strings["source_state_digest"],
                source_state.state_digest,
            ),
            (
                "session_contract_id",
                normalized_strings["session_contract_id"],
                session_contract.stable_id,
            ),
            (
                "session_contract_digest",
                normalized_strings["session_contract_digest"],
                session_contract.contract_digest,
            ),
            (
                "session_plan_id",
                normalized_strings["session_plan_id"],
                session_plan.stable_id,
            ),
            (
                "session_plan_digest",
                normalized_strings["session_plan_digest"],
                session_plan.session_digest,
            ),
            (
                "event_batch_id",
                normalized_strings["event_batch_id"],
                event_batch.stable_id,
            ),
            (
                "event_batch_digest",
                normalized_strings["event_batch_digest"],
                event_batch.batch_digest,
            ),
            (
                "broker_symbol",
                normalized_strings["broker_symbol"],
                advanced_state.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                advanced_state.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the immutable advanced-state lineage.")

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Next-transition contracts support Gold/XAUUSD only.")

        if self.direction != advanced_state.direction:
            raise ValueError("direction must match the advanced state.")

        if self.side != advanced_state.side:
            raise ValueError("side must match the advanced state.")

        if captured_at != advanced_state.captured_at:
            raise ValueError("captured_at must match the advanced state.")

        if self.timeframes != advanced_state.timeframes:
            raise ValueError("timeframes must match the advanced state.")

        state_numeric_comparisons = (
            (
                "transition_index",
                transition_index,
                advanced_state.consumed_count,
            ),
            (
                "current_cursor_index",
                current_cursor_index,
                advanced_state.cursor_index,
            ),
            (
                "current_consumed_count",
                current_consumed_count,
                advanced_state.consumed_count,
            ),
            (
                "current_remaining_count",
                current_remaining_count,
                advanced_state.remaining_count,
            ),
            (
                "prior_last_consumed_sequence_index",
                prior_last_consumed_sequence_index,
                (advanced_state.last_consumed_sequence_index),
            ),
            (
                "current_event_sequence_index",
                current_event_sequence_index,
                advanced_state.next_event_sequence_index,
            ),
            (
                "total_event_count",
                total_event_count,
                advanced_state.total_event_count,
            ),
        )

        for field_name, supplied, expected in state_numeric_comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the advanced session state.")

        if not advanced_state.has_next_event:
            raise ValueError("Advanced state has no event available.")

        if advanced_state.completion_reached:
            raise ValueError("Completed advanced state cannot create a next-transition contract.")

        current_event = advanced_state.next_event

        if normalized_strings["current_event_id"] != (current_event.stable_id):
            raise ValueError("current_event_id must match the event at the advanced cursor.")

        if normalized_strings["current_event_digest"] != current_event.event_digest:
            raise ValueError("current_event_digest must match the event at the advanced cursor.")

        if current_event_time != current_event.event_time:
            raise ValueError("current_event_time must match the event at the advanced cursor.")

        if self.current_event_timeframe != (current_event.timeframe):
            raise ValueError("current_event_timeframe must match the event at the advanced cursor.")

        next_event = event_batch.events[resulting_cursor_index]

        if next_event.sequence_index != (next_event_sequence_index):
            raise ValueError("Event batch does not preserve the resulting cursor sequence.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at the resulting cursor.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at the resulting cursor.")

        if next_event_time != next_event.event_time:
            raise ValueError("next_event_time must match the event at the resulting cursor.")

        if self.next_event_timeframe != next_event.timeframe:
            raise ValueError("next_event_timeframe must match the event at the resulting cursor.")

        if current_event.event_time != (current_event.close_time):
            raise ValueError("The current event must represent a closed candle.")

        if next_event.event_time != next_event.close_time:
            raise ValueError("The following event must represent a closed candle.")

        if not advanced_state.no_lookahead:
            raise ValueError("Advanced state must remain no-lookahead.")

        if not advanced_state.in_memory_only:
            raise ValueError("Advanced state must remain in-memory only.")

        safe_subjects = (
            self.advanced_state_decision,
            advanced_state,
            advanced_state.transition_application_decision,
            application_receipt,
            application_receipt.transition_contract_decision,
            prior_transition_contract,
            prior_transition_contract.session_state_decision,
            source_state,
            source_state.session_contract_decision,
            session_contract,
            session_contract.session_plan_decision,
            session_plan,
            session_plan.event_materialization_decision,
            event_batch,
            event_batch.materialization_plan_decision,
            advanced_state.materialization_plan,
            advanced_state.event_contract,
            advanced_state.replay_plan,
            advanced_state.specification,
            advanced_state.input_package,
            advanced_state.verification_receipt,
            advanced_state.snapshot,
            advanced_state.contract,
            advanced_state.dry_run_package,
        )

        if not all(_has_safe_external_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Next-transition lineage violates the external-I/O or broker boundary."
            )

        canonical_payload = _canonical_transition_payload(
            schema_version=schema_version,
            advanced_state_id=normalized_strings["advanced_state_id"],
            advanced_state_digest=normalized_strings["advanced_state_digest"],
            application_receipt_id=normalized_strings["application_receipt_id"],
            application_digest=normalized_strings["application_digest"],
            prior_transition_contract_id=(normalized_strings["prior_transition_contract_id"]),
            prior_transition_contract_digest=(
                normalized_strings["prior_transition_contract_digest"]
            ),
            source_state_id=normalized_strings["source_state_id"],
            source_state_digest=normalized_strings["source_state_digest"],
            session_contract_id=normalized_strings["session_contract_id"],
            session_contract_digest=normalized_strings["session_contract_digest"],
            session_plan_id=normalized_strings["session_plan_id"],
            session_plan_digest=normalized_strings["session_plan_digest"],
            event_batch_id=normalized_strings["event_batch_id"],
            event_batch_digest=normalized_strings["event_batch_digest"],
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            contract_mode=self.contract_mode,
            action=self.action,
            cursor_rule=self.cursor_rule,
            counter_rule=self.counter_rule,
            transition_index=transition_index,
            current_cursor_index=current_cursor_index,
            current_consumed_count=current_consumed_count,
            current_remaining_count=current_remaining_count,
            prior_last_consumed_sequence_index=(prior_last_consumed_sequence_index),
            current_event_sequence_index=(current_event_sequence_index),
            current_event_id=normalized_strings["current_event_id"],
            current_event_digest=normalized_strings["current_event_digest"],
            current_event_time=current_event_time,
            current_event_timeframe=(self.current_event_timeframe),
            resulting_cursor_index=resulting_cursor_index,
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_after_transition=(completion_after_transition),
            next_event_sequence_index=(next_event_sequence_index),
            next_event_id=normalized_strings["next_event_id"],
            next_event_digest=normalized_strings["next_event_digest"],
            next_event_time=next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            total_event_count=total_event_count,
            policy=self.policy,
        )

        if normalized_strings["transition_digest"] != (_sha256_digest(canonical_payload)):
            raise ValueError(
                "transition_digest does not match the canonical next-transition contract."
            )

        for field_name, value in normalized_strings.items():
            object.__setattr__(
                self,
                field_name,
                value,
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "captured_at",
            captured_at,
        )
        object.__setattr__(
            self,
            "current_event_time",
            current_event_time,
        )
        object.__setattr__(
            self,
            "next_event_time",
            next_event_time,
        )
        object.__setattr__(
            self,
            "transition_index",
            transition_index,
        )
        object.__setattr__(
            self,
            "current_cursor_index",
            current_cursor_index,
        )
        object.__setattr__(
            self,
            "current_consumed_count",
            current_consumed_count,
        )
        object.__setattr__(
            self,
            "current_remaining_count",
            current_remaining_count,
        )
        object.__setattr__(
            self,
            "prior_last_consumed_sequence_index",
            prior_last_consumed_sequence_index,
        )
        object.__setattr__(
            self,
            "current_event_sequence_index",
            current_event_sequence_index,
        )
        object.__setattr__(
            self,
            "resulting_cursor_index",
            resulting_cursor_index,
        )
        object.__setattr__(
            self,
            "resulting_consumed_count",
            resulting_consumed_count,
        )
        object.__setattr__(
            self,
            "resulting_remaining_count",
            resulting_remaining_count,
        )
        object.__setattr__(
            self,
            "last_consumed_sequence_index",
            last_consumed_sequence_index,
        )
        object.__setattr__(
            self,
            "completion_after_transition",
            completion_after_transition,
        )
        object.__setattr__(
            self,
            "next_event_sequence_index",
            next_event_sequence_index,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )

    @property
    def advanced_state(
        self,
    ) -> StrategyPhase8OfflineReplayAdvancedSessionState:
        return self.advanced_state_decision.state_required

    @property
    def application_receipt(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionApplicationReceipt:
        return self.advanced_state.application_receipt

    @property
    def prior_transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionContract:
        return self.advanced_state.transition_contract

    @property
    def source_state(
        self,
    ) -> StrategyPhase8OfflineReplaySessionState:
        return self.advanced_state.source_state

    @property
    def session_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        return self.advanced_state.session_contract

    @property
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.advanced_state.session_plan

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.advanced_state.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.advanced_state.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.advanced_state.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.advanced_state.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.advanced_state.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.advanced_state.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.advanced_state.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.advanced_state.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.advanced_state.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.advanced_state.dry_run_package

    @property
    def current_event(self) -> Phase8OfflineReplayEvent:
        return self.advanced_state.next_event

    @property
    def next_event(self) -> Phase8OfflineReplayEvent:
        return self.event_batch.events[self.resulting_cursor_index]

    @property
    def canonical_payload(self) -> str:
        return _canonical_transition_payload(
            schema_version=self.schema_version,
            advanced_state_id=self.advanced_state_id,
            advanced_state_digest=(self.advanced_state_digest),
            application_receipt_id=(self.application_receipt_id),
            application_digest=self.application_digest,
            prior_transition_contract_id=(self.prior_transition_contract_id),
            prior_transition_contract_digest=(self.prior_transition_contract_digest),
            source_state_id=self.source_state_id,
            source_state_digest=self.source_state_digest,
            session_contract_id=self.session_contract_id,
            session_contract_digest=(self.session_contract_digest),
            session_plan_id=self.session_plan_id,
            session_plan_digest=self.session_plan_digest,
            event_batch_id=self.event_batch_id,
            event_batch_digest=self.event_batch_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            timeframes=self.timeframes,
            contract_mode=self.contract_mode,
            action=self.action,
            cursor_rule=self.cursor_rule,
            counter_rule=self.counter_rule,
            transition_index=self.transition_index,
            current_cursor_index=self.current_cursor_index,
            current_consumed_count=(self.current_consumed_count),
            current_remaining_count=(self.current_remaining_count),
            prior_last_consumed_sequence_index=(self.prior_last_consumed_sequence_index),
            current_event_sequence_index=(self.current_event_sequence_index),
            current_event_id=self.current_event_id,
            current_event_digest=self.current_event_digest,
            current_event_time=self.current_event_time,
            current_event_timeframe=(self.current_event_timeframe),
            resulting_cursor_index=(self.resulting_cursor_index),
            resulting_consumed_count=(self.resulting_consumed_count),
            resulting_remaining_count=(self.resulting_remaining_count),
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            completion_after_transition=(self.completion_after_transition),
            next_event_sequence_index=(self.next_event_sequence_index),
            next_event_id=self.next_event_id,
            next_event_digest=self.next_event_digest,
            next_event_time=self.next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            total_event_count=self.total_event_count,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def contract_only(self) -> bool:
        return True

    @property
    def continuity_verified(self) -> bool:
        return self.policy.continuity_verified

    @property
    def one_event_transition(self) -> bool:
        return self.policy.one_event_transition

    @property
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def executes_transition(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def creates_next_state(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
        return False

    @property
    def evaluates_strategy(self) -> bool:
        return False

    @property
    def executes_simulation(self) -> bool:
        return False

    @property
    def emits_orders(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
        return False

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_next_transition_application(
        self,
    ) -> bool:
        return True

    @property
    def fetches_data(self) -> bool:
        return False

    @property
    def initializes_mt5(self) -> bool:
        return False

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def next_transition_contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_CONTRACT:"
            f"TRANSITION_SHA256[{self.transition_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.advanced_state_decision.stable_id}:{self.next_transition_contract_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayNextTransitionContractDecision:
    """Immutable next-transition contract decision."""

    advanced_state_decision: Phase8OfflineReplayAdvancedSessionStateDecision = field(repr=False)
    status: Phase8OfflineReplayNextTransitionContractStatus
    reason: Phase8OfflineReplayNextTransitionContractReason
    blockers: tuple[
        Phase8OfflineReplayNextTransitionContractBlocker,
        ...,
    ]
    transition_contract: StrategyPhase8OfflineReplayNextTransitionContract | None = field(
        repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.advanced_state_decision,
            Phase8OfflineReplayAdvancedSessionStateDecision,
        ):
            raise ValueError(
                "advanced_state_decision must be a Phase8OfflineReplayAdvancedSessionStateDecision."
            )

        try:
            status = Phase8OfflineReplayNextTransitionContractStatus(self.status)
            reason = Phase8OfflineReplayNextTransitionContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported next-transition contract status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayNextTransitionContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Next-transition blockers cannot contain duplicates.")

        if self.advanced_state_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayNextTransitionContractStatus.BLOCKED)
                or reason
                != (Phase8OfflineReplayNextTransitionContractReason.ADVANCED_STATE_BLOCKED)
                or blockers
                != (Phase8OfflineReplayNextTransitionContractBlocker.ADVANCED_STATE_BLOCKED,)
                or self.transition_contract is not None
            ):
                raise ValueError(
                    "Blocked next-transition result does not match its advanced state."
                )
        else:
            if (
                status != (Phase8OfflineReplayNextTransitionContractStatus.CREATED)
                or reason != (Phase8OfflineReplayNextTransitionContractReason.CREATED)
                or blockers
                or not isinstance(
                    self.transition_contract,
                    StrategyPhase8OfflineReplayNextTransitionContract,
                )
                or self.transition_contract.advanced_state_decision
                is not self.advanced_state_decision
            ):
                raise ValueError(
                    "Created next-transition result does not match its advanced state."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.advanced_state_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.advanced_state_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplayNextTransitionContractStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_transition_contract(self) -> bool:
        return self.transition_contract is not None

    @property
    def transition_contract_required(
        self,
    ) -> StrategyPhase8OfflineReplayNextTransitionContract:
        if self.transition_contract is None:
            raise ValueError("No Phase 8 next offline replay-transition contract was created.")

        return self.transition_contract

    @property
    def executes_transition(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def creates_next_state(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
        return False

    @property
    def evaluates_strategy(self) -> bool:
        return False

    @property
    def executes_simulation(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
        return False

    @property
    def can_continue_to_next_transition_application(
        self,
    ) -> bool:
        return self.is_created

    @property
    def fetches_data(self) -> bool:
        return False

    @property
    def initializes_mt5(self) -> bool:
        return False

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.advanced_state_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_"
            "CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayNextTransitionContractFactory:
    """Pure immutable next-transition contract factory."""

    def generate(
        self,
        advanced_state_decision: (Phase8OfflineReplayAdvancedSessionStateDecision),
        policy: (Phase8OfflineReplayNextTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplayNextTransitionContractDecision:
        if not isinstance(
            advanced_state_decision,
            Phase8OfflineReplayAdvancedSessionStateDecision,
        ):
            raise (
                Phase8OfflineReplayNextTransitionContractError(
                    Phase8OfflineReplayNextTransitionContractErrorReason.INVALID_ADVANCED_STATE_DECISION,
                    "advanced_state_decision must be a "
                    "Phase8OfflineReplayAdvancedSessionStateDecision.",
                )
            )

        selected_policy = policy or Phase8OfflineReplayNextTransitionContractPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayNextTransitionContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayNextTransitionContractPolicy.")

        if advanced_state_decision.is_blocked:
            return Phase8OfflineReplayNextTransitionContractDecision(
                advanced_state_decision=(advanced_state_decision),
                status=(Phase8OfflineReplayNextTransitionContractStatus.BLOCKED),
                reason=(Phase8OfflineReplayNextTransitionContractReason.ADVANCED_STATE_BLOCKED),
                blockers=(Phase8OfflineReplayNextTransitionContractBlocker.ADVANCED_STATE_BLOCKED,),
                transition_contract=None,
            )

        advanced_state = advanced_state_decision.state_required
        application_receipt = advanced_state.application_receipt
        prior_transition_contract = advanced_state.transition_contract
        source_state = advanced_state.source_state
        session_contract = advanced_state.session_contract
        session_plan = advanced_state.session_plan
        event_batch = advanced_state.event_batch
        current_event = advanced_state.next_event

        transition_index = advanced_state.consumed_count
        resulting_cursor_index = advanced_state.cursor_index + 1
        resulting_consumed_count = advanced_state.consumed_count + 1
        resulting_remaining_count = advanced_state.remaining_count - 1
        last_consumed_sequence_index = current_event.sequence_index
        completion_after_transition = resulting_cursor_index == advanced_state.total_event_count
        next_event = event_batch.events[resulting_cursor_index]

        canonical_payload = _canonical_transition_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_CONTRACT_SCHEMA_VERSION),
            advanced_state_id=advanced_state.stable_id,
            advanced_state_digest=advanced_state.state_digest,
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            prior_transition_contract_id=(prior_transition_contract.stable_id),
            prior_transition_contract_digest=(prior_transition_contract.transition_digest),
            source_state_id=source_state.stable_id,
            source_state_digest=source_state.state_digest,
            session_contract_id=session_contract.stable_id,
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=session_plan.session_digest,
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=advanced_state.broker_symbol,
            direction=advanced_state.direction,
            side=advanced_state.side,
            source_name=advanced_state.source_name,
            captured_at=advanced_state.captured_at,
            timeframes=advanced_state.timeframes,
            contract_mode=(Phase8OfflineReplayNextTransitionContractMode.IMMUTABLE_SINGLE_EVENT),
            action=(Phase8OfflineReplayNextTransitionAction.CONSUME_CURRENT_EVENT),
            cursor_rule=(Phase8OfflineReplayNextTransitionCursorRule.INCREMENT_BY_ONE),
            counter_rule=(
                Phase8OfflineReplayNextTransitionCounterRule.CONSUMED_PLUS_REMAINING_EQUALS_TOTAL
            ),
            transition_index=transition_index,
            current_cursor_index=(advanced_state.cursor_index),
            current_consumed_count=(advanced_state.consumed_count),
            current_remaining_count=(advanced_state.remaining_count),
            prior_last_consumed_sequence_index=(advanced_state.last_consumed_sequence_index),
            current_event_sequence_index=(current_event.sequence_index),
            current_event_id=current_event.stable_id,
            current_event_digest=current_event.event_digest,
            current_event_time=current_event.event_time,
            current_event_timeframe=current_event.timeframe,
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_after_transition=(completion_after_transition),
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            total_event_count=(advanced_state.total_event_count),
            policy=selected_policy,
        )

        transition_contract = StrategyPhase8OfflineReplayNextTransitionContract(
            advanced_state_decision=(advanced_state_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_CONTRACT_SCHEMA_VERSION),
            advanced_state_id=advanced_state.stable_id,
            advanced_state_digest=(advanced_state.state_digest),
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            prior_transition_contract_id=(prior_transition_contract.stable_id),
            prior_transition_contract_digest=(prior_transition_contract.transition_digest),
            source_state_id=source_state.stable_id,
            source_state_digest=(source_state.state_digest),
            session_contract_id=(session_contract.stable_id),
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=(session_plan.session_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=(event_batch.batch_digest),
            broker_symbol=advanced_state.broker_symbol,
            direction=advanced_state.direction,
            side=advanced_state.side,
            source_name=advanced_state.source_name,
            captured_at=advanced_state.captured_at,
            timeframes=advanced_state.timeframes,
            contract_mode=(Phase8OfflineReplayNextTransitionContractMode.IMMUTABLE_SINGLE_EVENT),
            action=(Phase8OfflineReplayNextTransitionAction.CONSUME_CURRENT_EVENT),
            cursor_rule=(Phase8OfflineReplayNextTransitionCursorRule.INCREMENT_BY_ONE),
            counter_rule=(
                Phase8OfflineReplayNextTransitionCounterRule.CONSUMED_PLUS_REMAINING_EQUALS_TOTAL
            ),
            transition_index=transition_index,
            current_cursor_index=(advanced_state.cursor_index),
            current_consumed_count=(advanced_state.consumed_count),
            current_remaining_count=(advanced_state.remaining_count),
            prior_last_consumed_sequence_index=(advanced_state.last_consumed_sequence_index),
            current_event_sequence_index=(current_event.sequence_index),
            current_event_id=(current_event.stable_id),
            current_event_digest=(current_event.event_digest),
            current_event_time=(current_event.event_time),
            current_event_timeframe=(current_event.timeframe),
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_after_transition=(completion_after_transition),
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=(next_event.event_digest),
            next_event_time=next_event.event_time,
            next_event_timeframe=(next_event.timeframe),
            total_event_count=(advanced_state.total_event_count),
            transition_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayNextTransitionContractDecision(
            advanced_state_decision=(advanced_state_decision),
            status=(Phase8OfflineReplayNextTransitionContractStatus.CREATED),
            reason=(Phase8OfflineReplayNextTransitionContractReason.CREATED),
            blockers=(),
            transition_contract=transition_contract,
        )

    def build(
        self,
        advanced_state_decision: (Phase8OfflineReplayAdvancedSessionStateDecision),
        policy: (Phase8OfflineReplayNextTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplayNextTransitionContractDecision:
        return self.generate(
            advanced_state_decision,
            policy,
        )

    def evaluate(
        self,
        advanced_state_decision: (Phase8OfflineReplayAdvancedSessionStateDecision),
        policy: (Phase8OfflineReplayNextTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplayNextTransitionContractDecision:
        return self.generate(
            advanced_state_decision,
            policy,
        )


def generate_phase8_offline_replay_next_transition_contract(
    advanced_state_decision: (Phase8OfflineReplayAdvancedSessionStateDecision),
    policy: (Phase8OfflineReplayNextTransitionContractPolicy | None) = None,
) -> Phase8OfflineReplayNextTransitionContractDecision:
    return StrategyPhase8OfflineReplayNextTransitionContractFactory().generate(
        advanced_state_decision,
        policy,
    )


Phase8OfflineReplayNextTransitionContract = StrategyPhase8OfflineReplayNextTransitionContract
Phase8OfflineReplayNextTransitionContractFactory = (
    StrategyPhase8OfflineReplayNextTransitionContractFactory
)
