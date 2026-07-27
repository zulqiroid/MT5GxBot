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
from app.strategy.phase8_offline_replay_transition_contract import (
    Phase8OfflineReplayTransitionContractDecision,
    StrategyPhase8OfflineReplayTransitionContract,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_TRANSITION_APPLICATION_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplayTransitionApplicationMode(
    str,
    Enum,
):
    PURE_IMMUTABLE_IN_MEMORY = "PURE_IMMUTABLE_IN_MEMORY"


class Phase8OfflineReplayTransitionApplicationStatus(
    str,
    Enum,
):
    APPLIED = "APPLIED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayTransitionApplicationReason(
    str,
    Enum,
):
    APPLIED = "APPLIED"
    TRANSITION_CONTRACT_BLOCKED = "TRANSITION_CONTRACT_BLOCKED"


class Phase8OfflineReplayTransitionApplicationBlocker(
    str,
    Enum,
):
    TRANSITION_CONTRACT_BLOCKED = "TRANSITION_CONTRACT_BLOCKED"


class Phase8OfflineReplayTransitionApplicationErrorReason(
    str,
    Enum,
):
    INVALID_TRANSITION_CONTRACT_DECISION = "INVALID_TRANSITION_CONTRACT_DECISION"


class Phase8OfflineReplayTransitionApplicationError(
    RuntimeError,
):
    """Structured pure transition-application failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayTransitionApplicationErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayTransitionApplicationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 offline replay-transition application "
            f"error [{self.reason.value}]: {self.message}"
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


def _has_safe_boundary(subject: object) -> bool:
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
class Phase8OfflineReplayTransitionApplicationPolicy:
    """Strict pure in-memory transition application rules."""

    source_state_immutable: bool = True
    contract_verified: bool = True
    consume_exactly_one_event: bool = True
    cursor_increment_by_one: bool = True
    counters_remain_consistent: bool = True
    next_event_rebound: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "source_state_immutable",
            "contract_verified",
            "consume_exactly_one_event",
            "cursor_increment_by_one",
            "counters_remain_consistent",
            "next_event_rebound",
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
                self.source_state_immutable,
                self.contract_verified,
                self.consume_exactly_one_event,
                self.cursor_increment_by_one,
                self.counters_remain_consistent,
                self.next_event_rebound,
                self.in_memory_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_application_payload(
    *,
    schema_version: str,
    transition_contract_id: str,
    transition_contract_digest: str,
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
    application_mode: (Phase8OfflineReplayTransitionApplicationMode),
    transition_index: int,
    prior_cursor_index: int,
    prior_consumed_count: int,
    prior_remaining_count: int,
    consumed_event_sequence_index: int,
    consumed_event_id: str,
    consumed_event_digest: str,
    consumed_event_time: datetime,
    consumed_event_timeframe: Phase8Timeframe,
    resulting_cursor_index: int,
    resulting_consumed_count: int,
    resulting_remaining_count: int,
    last_consumed_sequence_index: int,
    completion_reached: bool,
    next_event_available: bool,
    next_event_sequence_index: int,
    next_event_id: str,
    next_event_digest: str,
    next_event_time: datetime,
    next_event_timeframe: Phase8Timeframe,
    total_event_count: int,
    policy: Phase8OfflineReplayTransitionApplicationPolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            (f"TRANSITION_CONTRACT_ID={transition_contract_id}"),
            (f"TRANSITION_CONTRACT_DIGEST={transition_contract_digest}"),
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
            f"APPLICATION_MODE={application_mode.value}",
            f"TRANSITION_INDEX={transition_index}",
            f"PRIOR_CURSOR_INDEX={prior_cursor_index}",
            (f"PRIOR_CONSUMED_COUNT={prior_consumed_count}"),
            (f"PRIOR_REMAINING_COUNT={prior_remaining_count}"),
            (f"CONSUMED_EVENT_SEQUENCE_INDEX={consumed_event_sequence_index}"),
            f"CONSUMED_EVENT_ID={consumed_event_id}",
            (f"CONSUMED_EVENT_DIGEST={consumed_event_digest}"),
            (f"CONSUMED_EVENT_TIME={_canonical_datetime(consumed_event_time)}"),
            (f"CONSUMED_EVENT_TIMEFRAME={consumed_event_timeframe.value}"),
            (f"RESULTING_CURSOR_INDEX={resulting_cursor_index}"),
            (f"RESULTING_CONSUMED_COUNT={resulting_consumed_count}"),
            (f"RESULTING_REMAINING_COUNT={resulting_remaining_count}"),
            (f"LAST_CONSUMED_SEQUENCE_INDEX={last_consumed_sequence_index}"),
            (f"COMPLETION_REACHED={str(completion_reached).lower()}"),
            (f"NEXT_EVENT_AVAILABLE={str(next_event_available).lower()}"),
            (f"NEXT_EVENT_SEQUENCE_INDEX={next_event_sequence_index}"),
            f"NEXT_EVENT_ID={next_event_id}",
            f"NEXT_EVENT_DIGEST={next_event_digest}",
            (f"NEXT_EVENT_TIME={_canonical_datetime(next_event_time)}"),
            (f"NEXT_EVENT_TIMEFRAME={next_event_timeframe.value}"),
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"SOURCE_STATE_IMMUTABLE={str(policy.source_state_immutable).lower()}"),
            (f"CONTRACT_VERIFIED={str(policy.contract_verified).lower()}"),
            (f"CONSUME_EXACTLY_ONE_EVENT={str(policy.consume_exactly_one_event).lower()}"),
            (f"CURSOR_INCREMENT_BY_ONE={str(policy.cursor_increment_by_one).lower()}"),
            (f"COUNTERS_REMAIN_CONSISTENT={str(policy.counters_remain_consistent).lower()}"),
            (f"NEXT_EVENT_REBOUND={str(policy.next_event_rebound).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "TRANSITION_APPLIED=true",
            "SOURCE_STATE_MUTATED=false",
            "NEXT_STATE_CREATED=false",
            "FULL_REPLAY_EXECUTION=false",
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
class StrategyPhase8OfflineReplayTransitionApplicationReceipt:
    """
    Immutable receipt for the first pure in-memory transition.

    The receipt proves that exactly one closed-candle event
    was consumed according to the transition contract. The
    source state remains immutable and no reusable next-state
    object is created in this step.
    """

    transition_contract_decision: Phase8OfflineReplayTransitionContractDecision = field(repr=False)
    policy: Phase8OfflineReplayTransitionApplicationPolicy
    schema_version: str
    transition_contract_id: str
    transition_contract_digest: str
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
    application_mode: Phase8OfflineReplayTransitionApplicationMode
    transition_index: int
    prior_cursor_index: int
    prior_consumed_count: int
    prior_remaining_count: int
    consumed_event_sequence_index: int
    consumed_event_id: str
    consumed_event_digest: str
    consumed_event_time: datetime
    consumed_event_timeframe: Phase8Timeframe
    resulting_cursor_index: int
    resulting_consumed_count: int
    resulting_remaining_count: int
    last_consumed_sequence_index: int
    completion_reached: bool
    next_event_available: bool
    next_event_sequence_index: int
    next_event_id: str
    next_event_digest: str
    next_event_time: datetime
    next_event_timeframe: Phase8Timeframe
    total_event_count: int
    application_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.transition_contract_decision,
            Phase8OfflineReplayTransitionContractDecision,
        ):
            raise ValueError(
                "transition_contract_decision must be a "
                "Phase8OfflineReplayTransitionContractDecision."
            )

        if not self.transition_contract_decision.is_created:
            raise ValueError(
                "A transition application receipt requires a created transition contract."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplayTransitionApplicationPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayTransitionApplicationPolicy.")

        if not self.policy.is_strict:
            raise ValueError("Transition-application policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_TRANSITION_APPLICATION_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current transition-application schema.")

        string_fields = (
            (
                "transition_contract_id",
                self.transition_contract_id,
            ),
            (
                "transition_contract_digest",
                self.transition_contract_digest,
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
            ("consumed_event_id", self.consumed_event_id),
            (
                "consumed_event_digest",
                self.consumed_event_digest,
            ),
            ("next_event_id", self.next_event_id),
            ("next_event_digest", self.next_event_digest),
            ("application_digest", self.application_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "transition_contract_digest",
            "source_state_digest",
            "session_contract_digest",
            "session_plan_digest",
            "event_batch_digest",
            "consumed_event_digest",
            "next_event_digest",
            "application_digest",
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

        if not isinstance(
            self.application_mode,
            Phase8OfflineReplayTransitionApplicationMode,
        ):
            raise ValueError(
                "application_mode must be a Phase8OfflineReplayTransitionApplicationMode member."
            )

        if self.application_mode != (
            Phase8OfflineReplayTransitionApplicationMode.PURE_IMMUTABLE_IN_MEMORY
        ):
            raise ValueError("application_mode must remain PURE_IMMUTABLE_IN_MEMORY.")

        if not isinstance(
            self.consumed_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("consumed_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(
            self.next_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("next_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        consumed_event_time = _aware_datetime(
            self.consumed_event_time,
            "consumed_event_time",
        )
        next_event_time = _aware_datetime(
            self.next_event_time,
            "next_event_time",
        )

        if consumed_event_time > captured_at:
            raise ValueError("consumed_event_time cannot exceed captured_at.")

        if next_event_time > captured_at:
            raise ValueError("next_event_time cannot exceed captured_at.")

        if next_event_time < consumed_event_time:
            raise ValueError("next_event_time cannot precede the consumed event.")

        transition_index = _non_negative_integer(
            self.transition_index,
            "transition_index",
        )
        prior_cursor_index = _non_negative_integer(
            self.prior_cursor_index,
            "prior_cursor_index",
        )
        prior_consumed_count = _non_negative_integer(
            self.prior_consumed_count,
            "prior_consumed_count",
        )
        prior_remaining_count = _positive_integer(
            self.prior_remaining_count,
            "prior_remaining_count",
        )
        consumed_event_sequence_index = _non_negative_integer(
            self.consumed_event_sequence_index,
            "consumed_event_sequence_index",
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
        last_consumed_sequence_index = _non_negative_integer(
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
        completion_reached = _strict_boolean(
            self.completion_reached,
            "completion_reached",
        )
        next_event_available = _strict_boolean(
            self.next_event_available,
            "next_event_available",
        )

        if transition_index != 0:
            raise ValueError("transition_index must remain zero for the initial application.")

        if prior_cursor_index != 0:
            raise ValueError("prior_cursor_index must remain zero.")

        if prior_consumed_count != 0:
            raise ValueError("prior_consumed_count must remain zero.")

        if prior_remaining_count != total_event_count:
            raise ValueError("prior_remaining_count must equal total_event_count.")

        if consumed_event_sequence_index != prior_cursor_index:
            raise ValueError("consumed_event_sequence_index must equal the prior cursor.")

        if resulting_cursor_index != prior_cursor_index + 1:
            raise ValueError("resulting_cursor_index must increment by exactly one.")

        if resulting_consumed_count != prior_consumed_count + 1:
            raise ValueError("resulting_consumed_count must increment by exactly one.")

        if resulting_remaining_count != prior_remaining_count - 1:
            raise ValueError("resulting_remaining_count must decrement by exactly one.")

        if resulting_consumed_count + resulting_remaining_count != total_event_count:
            raise ValueError("Resulting counters must preserve total_event_count.")

        if last_consumed_sequence_index != consumed_event_sequence_index:
            raise ValueError("last_consumed_sequence_index must equal the consumed event sequence.")

        if completion_reached:
            raise ValueError("The initial transition cannot complete the replay session.")

        if not next_event_available:
            raise ValueError("The initial transition must expose the next replay event.")

        if next_event_sequence_index != resulting_cursor_index:
            raise ValueError("next_event_sequence_index must equal the resulting cursor.")

        transition_contract = self.transition_contract_decision.transition_contract_required
        source_state = transition_contract.session_state
        session_contract = transition_contract.session_contract
        session_plan = transition_contract.session_plan
        event_batch = transition_contract.event_batch

        comparisons = (
            (
                "transition_contract_id",
                normalized_strings["transition_contract_id"],
                transition_contract.stable_id,
            ),
            (
                "transition_contract_digest",
                normalized_strings["transition_contract_digest"],
                transition_contract.transition_digest,
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
                transition_contract.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                transition_contract.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable transition-contract lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Transition applications support Gold/XAUUSD only.")

        if self.direction != transition_contract.direction:
            raise ValueError("direction must match the transition contract.")

        if self.side != transition_contract.side:
            raise ValueError("side must match the transition contract.")

        if captured_at != transition_contract.captured_at:
            raise ValueError("captured_at must match the transition contract.")

        if self.timeframes != transition_contract.timeframes:
            raise ValueError("timeframes must match the transition contract.")

        contract_numeric_values = (
            (
                "transition_index",
                transition_index,
                transition_contract.transition_index,
            ),
            (
                "prior_cursor_index",
                prior_cursor_index,
                transition_contract.current_cursor_index,
            ),
            (
                "prior_consumed_count",
                prior_consumed_count,
                transition_contract.current_consumed_count,
            ),
            (
                "prior_remaining_count",
                prior_remaining_count,
                transition_contract.current_remaining_count,
            ),
            (
                "consumed_event_sequence_index",
                consumed_event_sequence_index,
                (transition_contract.current_event_sequence_index),
            ),
            (
                "resulting_cursor_index",
                resulting_cursor_index,
                transition_contract.resulting_cursor_index,
            ),
            (
                "resulting_consumed_count",
                resulting_consumed_count,
                (transition_contract.resulting_consumed_count),
            ),
            (
                "resulting_remaining_count",
                resulting_remaining_count,
                (transition_contract.resulting_remaining_count),
            ),
            (
                "last_consumed_sequence_index",
                last_consumed_sequence_index,
                (transition_contract.last_consumed_sequence_index),
            ),
            (
                "total_event_count",
                total_event_count,
                transition_contract.total_event_count,
            ),
        )

        for field_name, supplied, expected in contract_numeric_values:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the transition contract.")

        consumed_event = transition_contract.current_event

        if normalized_strings["consumed_event_id"] != (consumed_event.stable_id):
            raise ValueError("consumed_event_id must match the contract current event.")

        if normalized_strings["consumed_event_digest"] != consumed_event.event_digest:
            raise ValueError("consumed_event_digest must match the contract current event.")

        if consumed_event_time != consumed_event.event_time:
            raise ValueError("consumed_event_time must match the contract current event.")

        if self.consumed_event_timeframe != consumed_event.timeframe:
            raise ValueError("consumed_event_timeframe must match the contract current event.")

        next_event = event_batch.events[resulting_cursor_index]

        if next_event.sequence_index != (next_event_sequence_index):
            raise ValueError("The event batch does not preserve the resulting cursor sequence.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at the resulting cursor.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at the resulting cursor.")

        if next_event_time != next_event.event_time:
            raise ValueError("next_event_time must match the event at the resulting cursor.")

        if self.next_event_timeframe != next_event.timeframe:
            raise ValueError("next_event_timeframe must match the event at the resulting cursor.")

        if consumed_event.event_time != (consumed_event.close_time):
            raise ValueError("The consumed event must represent a closed candle.")

        if next_event.event_time != next_event.close_time:
            raise ValueError("The next event must represent a closed candle.")

        if source_state.cursor_index != 0:
            raise ValueError("The immutable source state was altered.")

        if source_state.consumed_count != 0:
            raise ValueError("The immutable source consumed count was altered.")

        if source_state.remaining_count != total_event_count:
            raise ValueError("The immutable source remaining count was altered.")

        safe_subjects = (
            self.transition_contract_decision,
            transition_contract,
            transition_contract.session_state_decision,
            source_state,
            source_state.session_contract_decision,
            session_contract,
            session_contract.session_plan_decision,
            session_plan,
            session_plan.event_materialization_decision,
            event_batch,
            event_batch.materialization_plan_decision,
            transition_contract.materialization_plan,
            transition_contract.event_contract,
            transition_contract.replay_plan,
            transition_contract.specification,
            transition_contract.input_package,
            transition_contract.verification_receipt,
            transition_contract.snapshot,
            transition_contract.contract,
            transition_contract.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Transition-application lineage violates the external-I/O or broker boundary."
            )

        canonical_payload = _canonical_application_payload(
            schema_version=schema_version,
            transition_contract_id=normalized_strings["transition_contract_id"],
            transition_contract_digest=normalized_strings["transition_contract_digest"],
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
            application_mode=self.application_mode,
            transition_index=transition_index,
            prior_cursor_index=prior_cursor_index,
            prior_consumed_count=prior_consumed_count,
            prior_remaining_count=prior_remaining_count,
            consumed_event_sequence_index=(consumed_event_sequence_index),
            consumed_event_id=normalized_strings["consumed_event_id"],
            consumed_event_digest=normalized_strings["consumed_event_digest"],
            consumed_event_time=consumed_event_time,
            consumed_event_timeframe=(self.consumed_event_timeframe),
            resulting_cursor_index=resulting_cursor_index,
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_reached=completion_reached,
            next_event_available=next_event_available,
            next_event_sequence_index=(next_event_sequence_index),
            next_event_id=normalized_strings["next_event_id"],
            next_event_digest=normalized_strings["next_event_digest"],
            next_event_time=next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            total_event_count=total_event_count,
            policy=self.policy,
        )

        if normalized_strings["application_digest"] != _sha256_digest(canonical_payload):
            raise ValueError(
                "application_digest does not match the canonical transition application."
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
            "consumed_event_time",
            consumed_event_time,
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
            "prior_cursor_index",
            prior_cursor_index,
        )
        object.__setattr__(
            self,
            "prior_consumed_count",
            prior_consumed_count,
        )
        object.__setattr__(
            self,
            "prior_remaining_count",
            prior_remaining_count,
        )
        object.__setattr__(
            self,
            "consumed_event_sequence_index",
            consumed_event_sequence_index,
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
            "completion_reached",
            completion_reached,
        )
        object.__setattr__(
            self,
            "next_event_available",
            next_event_available,
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
    def transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionContract:
        return self.transition_contract_decision.transition_contract_required

    @property
    def source_state(
        self,
    ) -> StrategyPhase8OfflineReplaySessionState:
        return self.transition_contract.session_state

    @property
    def session_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        return self.transition_contract.session_contract

    @property
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.transition_contract.session_plan

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.transition_contract.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.transition_contract.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.transition_contract.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.transition_contract.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.transition_contract.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.transition_contract.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.transition_contract.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.transition_contract.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.transition_contract.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.transition_contract.dry_run_package

    @property
    def consumed_event(self) -> Phase8OfflineReplayEvent:
        return self.transition_contract.current_event

    @property
    def next_event(self) -> Phase8OfflineReplayEvent:
        return self.event_batch.events[self.resulting_cursor_index]

    @property
    def canonical_payload(self) -> str:
        return _canonical_application_payload(
            schema_version=self.schema_version,
            transition_contract_id=(self.transition_contract_id),
            transition_contract_digest=(self.transition_contract_digest),
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
            application_mode=self.application_mode,
            transition_index=self.transition_index,
            prior_cursor_index=self.prior_cursor_index,
            prior_consumed_count=(self.prior_consumed_count),
            prior_remaining_count=(self.prior_remaining_count),
            consumed_event_sequence_index=(self.consumed_event_sequence_index),
            consumed_event_id=self.consumed_event_id,
            consumed_event_digest=(self.consumed_event_digest),
            consumed_event_time=self.consumed_event_time,
            consumed_event_timeframe=(self.consumed_event_timeframe),
            resulting_cursor_index=(self.resulting_cursor_index),
            resulting_consumed_count=(self.resulting_consumed_count),
            resulting_remaining_count=(self.resulting_remaining_count),
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            completion_reached=self.completion_reached,
            next_event_available=self.next_event_available,
            next_event_sequence_index=(self.next_event_sequence_index),
            next_event_id=self.next_event_id,
            next_event_digest=self.next_event_digest,
            next_event_time=self.next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            total_event_count=self.total_event_count,
            policy=self.policy,
        )

    @property
    def is_applied(self) -> bool:
        return True

    @property
    def source_state_preserved(self) -> bool:
        return True

    @property
    def executes_transition(self) -> bool:
        return True

    @property
    def advances_cursor(self) -> bool:
        return True

    @property
    def consumes_events(self) -> bool:
        return True

    @property
    def creates_next_state(self) -> bool:
        return False

    @property
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
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
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_advanced_session_state(
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
    def application_receipt_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_TRANSITION_APPLICATION:"
            f"APPLICATION_SHA256[{self.application_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.transition_contract_decision.stable_id}:{self.application_receipt_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayTransitionApplicationDecision:
    """Immutable transition-application decision."""

    transition_contract_decision: Phase8OfflineReplayTransitionContractDecision = field(repr=False)
    status: Phase8OfflineReplayTransitionApplicationStatus
    reason: Phase8OfflineReplayTransitionApplicationReason
    blockers: tuple[
        Phase8OfflineReplayTransitionApplicationBlocker,
        ...,
    ]
    receipt: StrategyPhase8OfflineReplayTransitionApplicationReceipt | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.transition_contract_decision,
            Phase8OfflineReplayTransitionContractDecision,
        ):
            raise ValueError(
                "transition_contract_decision must be a "
                "Phase8OfflineReplayTransitionContractDecision."
            )

        try:
            status = Phase8OfflineReplayTransitionApplicationStatus(self.status)
            reason = Phase8OfflineReplayTransitionApplicationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported transition-application status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayTransitionApplicationBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Transition-application blockers cannot contain duplicates.")

        if self.transition_contract_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayTransitionApplicationStatus.BLOCKED)
                or reason
                != (Phase8OfflineReplayTransitionApplicationReason.TRANSITION_CONTRACT_BLOCKED)
                or blockers
                != (Phase8OfflineReplayTransitionApplicationBlocker.TRANSITION_CONTRACT_BLOCKED,)
                or self.receipt is not None
            ):
                raise ValueError(
                    "Blocked transition-application result does not match its contract decision."
                )
        else:
            if (
                status != (Phase8OfflineReplayTransitionApplicationStatus.APPLIED)
                or reason != (Phase8OfflineReplayTransitionApplicationReason.APPLIED)
                or blockers
                or not isinstance(
                    self.receipt,
                    StrategyPhase8OfflineReplayTransitionApplicationReceipt,
                )
                or self.receipt.transition_contract_decision
                is not self.transition_contract_decision
            ):
                raise ValueError("Applied transition result does not match its contract decision.")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.transition_contract_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.transition_contract_decision.direction

    @property
    def is_applied(self) -> bool:
        return self.status == (Phase8OfflineReplayTransitionApplicationStatus.APPLIED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_applied

    @property
    def has_receipt(self) -> bool:
        return self.receipt is not None

    @property
    def receipt_required(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionApplicationReceipt:
        if self.receipt is None:
            raise ValueError(
                "No Phase 8 offline replay-transition application receipt was created."
            )

        return self.receipt

    @property
    def executes_transition(self) -> bool:
        return self.is_applied

    @property
    def advances_cursor(self) -> bool:
        return self.is_applied

    @property
    def consumes_events(self) -> bool:
        return self.is_applied

    @property
    def creates_next_state(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
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
    def can_continue_to_advanced_session_state(
        self,
    ) -> bool:
        return self.is_applied

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
            f"{self.transition_contract_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_TRANSITION_APPLICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayTransitionApplicationFactory:
    """Pure immutable first-transition application factory."""

    def generate(
        self,
        transition_contract_decision: (Phase8OfflineReplayTransitionContractDecision),
        policy: (Phase8OfflineReplayTransitionApplicationPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionApplicationDecision:
        if not isinstance(
            transition_contract_decision,
            Phase8OfflineReplayTransitionContractDecision,
        ):
            raise Phase8OfflineReplayTransitionApplicationError(
                Phase8OfflineReplayTransitionApplicationErrorReason.INVALID_TRANSITION_CONTRACT_DECISION,
                "transition_contract_decision must be a "
                "Phase8OfflineReplayTransitionContractDecision.",
            )

        selected_policy = policy or Phase8OfflineReplayTransitionApplicationPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayTransitionApplicationPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayTransitionApplicationPolicy.")

        if transition_contract_decision.is_blocked:
            return Phase8OfflineReplayTransitionApplicationDecision(
                transition_contract_decision=(transition_contract_decision),
                status=(Phase8OfflineReplayTransitionApplicationStatus.BLOCKED),
                reason=(Phase8OfflineReplayTransitionApplicationReason.TRANSITION_CONTRACT_BLOCKED),
                blockers=(
                    Phase8OfflineReplayTransitionApplicationBlocker.TRANSITION_CONTRACT_BLOCKED,
                ),
                receipt=None,
            )

        transition_contract = transition_contract_decision.transition_contract_required
        source_state = transition_contract.session_state
        session_contract = transition_contract.session_contract
        session_plan = transition_contract.session_plan
        event_batch = transition_contract.event_batch
        consumed_event = transition_contract.current_event

        resulting_cursor_index = transition_contract.resulting_cursor_index
        next_event = event_batch.events[resulting_cursor_index]

        canonical_payload = _canonical_application_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_TRANSITION_APPLICATION_SCHEMA_VERSION),
            transition_contract_id=(transition_contract.stable_id),
            transition_contract_digest=(transition_contract.transition_digest),
            source_state_id=source_state.stable_id,
            source_state_digest=source_state.state_digest,
            session_contract_id=session_contract.stable_id,
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=session_plan.session_digest,
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=transition_contract.broker_symbol,
            direction=transition_contract.direction,
            side=transition_contract.side,
            source_name=transition_contract.source_name,
            captured_at=transition_contract.captured_at,
            timeframes=transition_contract.timeframes,
            application_mode=(
                Phase8OfflineReplayTransitionApplicationMode.PURE_IMMUTABLE_IN_MEMORY
            ),
            transition_index=(transition_contract.transition_index),
            prior_cursor_index=(transition_contract.current_cursor_index),
            prior_consumed_count=(transition_contract.current_consumed_count),
            prior_remaining_count=(transition_contract.current_remaining_count),
            consumed_event_sequence_index=(consumed_event.sequence_index),
            consumed_event_id=consumed_event.stable_id,
            consumed_event_digest=(consumed_event.event_digest),
            consumed_event_time=consumed_event.event_time,
            consumed_event_timeframe=(consumed_event.timeframe),
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(transition_contract.resulting_consumed_count),
            resulting_remaining_count=(transition_contract.resulting_remaining_count),
            last_consumed_sequence_index=(transition_contract.last_consumed_sequence_index),
            completion_reached=(transition_contract.completion_after_transition),
            next_event_available=True,
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            total_event_count=(transition_contract.total_event_count),
            policy=selected_policy,
        )

        receipt = StrategyPhase8OfflineReplayTransitionApplicationReceipt(
            transition_contract_decision=(transition_contract_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_TRANSITION_APPLICATION_SCHEMA_VERSION),
            transition_contract_id=(transition_contract.stable_id),
            transition_contract_digest=(transition_contract.transition_digest),
            source_state_id=source_state.stable_id,
            source_state_digest=(source_state.state_digest),
            session_contract_id=(session_contract.stable_id),
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=(session_plan.session_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=(event_batch.batch_digest),
            broker_symbol=(transition_contract.broker_symbol),
            direction=transition_contract.direction,
            side=transition_contract.side,
            source_name=(transition_contract.source_name),
            captured_at=(transition_contract.captured_at),
            timeframes=transition_contract.timeframes,
            application_mode=(
                Phase8OfflineReplayTransitionApplicationMode.PURE_IMMUTABLE_IN_MEMORY
            ),
            transition_index=(transition_contract.transition_index),
            prior_cursor_index=(transition_contract.current_cursor_index),
            prior_consumed_count=(transition_contract.current_consumed_count),
            prior_remaining_count=(transition_contract.current_remaining_count),
            consumed_event_sequence_index=(consumed_event.sequence_index),
            consumed_event_id=(consumed_event.stable_id),
            consumed_event_digest=(consumed_event.event_digest),
            consumed_event_time=(consumed_event.event_time),
            consumed_event_timeframe=(consumed_event.timeframe),
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(transition_contract.resulting_consumed_count),
            resulting_remaining_count=(transition_contract.resulting_remaining_count),
            last_consumed_sequence_index=(transition_contract.last_consumed_sequence_index),
            completion_reached=(transition_contract.completion_after_transition),
            next_event_available=True,
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=(next_event.event_digest),
            next_event_time=next_event.event_time,
            next_event_timeframe=(next_event.timeframe),
            total_event_count=(transition_contract.total_event_count),
            application_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayTransitionApplicationDecision(
            transition_contract_decision=(transition_contract_decision),
            status=(Phase8OfflineReplayTransitionApplicationStatus.APPLIED),
            reason=(Phase8OfflineReplayTransitionApplicationReason.APPLIED),
            blockers=(),
            receipt=receipt,
        )

    def apply(
        self,
        transition_contract_decision: (Phase8OfflineReplayTransitionContractDecision),
        policy: (Phase8OfflineReplayTransitionApplicationPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionApplicationDecision:
        return self.generate(
            transition_contract_decision,
            policy,
        )

    def build(
        self,
        transition_contract_decision: (Phase8OfflineReplayTransitionContractDecision),
        policy: (Phase8OfflineReplayTransitionApplicationPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionApplicationDecision:
        return self.generate(
            transition_contract_decision,
            policy,
        )

    def evaluate(
        self,
        transition_contract_decision: (Phase8OfflineReplayTransitionContractDecision),
        policy: (Phase8OfflineReplayTransitionApplicationPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionApplicationDecision:
        return self.generate(
            transition_contract_decision,
            policy,
        )


def apply_phase8_offline_replay_transition(
    transition_contract_decision: (Phase8OfflineReplayTransitionContractDecision),
    policy: (Phase8OfflineReplayTransitionApplicationPolicy | None) = None,
) -> Phase8OfflineReplayTransitionApplicationDecision:
    return StrategyPhase8OfflineReplayTransitionApplicationFactory().generate(
        transition_contract_decision,
        policy,
    )


Phase8OfflineReplayTransitionApplicationReceipt = (
    StrategyPhase8OfflineReplayTransitionApplicationReceipt
)
Phase8OfflineReplayTransitionApplicationFactory = (
    StrategyPhase8OfflineReplayTransitionApplicationFactory
)
