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
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
)
from app.strategy.phase8_offline_replay_event_materialization import (
    Phase8OfflineReplayEvent,
    StrategyPhase8OfflineReplayEventBatch,
)
from app.strategy.phase8_offline_replay_progressed_session_state import (
    StrategyPhase8OfflineReplayProgressedSessionState,
)
from app.strategy.phase8_offline_replay_subsequent_transition_application import (
    Phase8OfflineReplaySubsequentTransitionApplicationDecision,
    StrategyPhase8OfflineReplaySubsequentTransitionApplicationReceipt,
)
from app.strategy.phase8_offline_replay_subsequent_transition_contract import (
    StrategyPhase8OfflineReplaySubsequentTransitionContract,
)

PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_PROGRESSED_SESSION_STATE_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplaySubsequentProgressedSessionStateMode(
    str,
    Enum,
):
    IMMUTABLE_SUBSEQUENT_PROGRESSED_STATE = "IMMUTABLE_SUBSEQUENT_PROGRESSED_STATE"


class Phase8OfflineReplaySubsequentProgressedSessionLifecycle(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"


class Phase8OfflineReplaySubsequentProgressedSessionStateStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplaySubsequentProgressedSessionStateReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED = "SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED"


class Phase8OfflineReplaySubsequentProgressedSessionStateBlocker(
    str,
    Enum,
):
    SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED = "SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED"


class Phase8OfflineReplaySubsequentProgressedSessionStateErrorReason(
    str,
    Enum,
):
    INVALID_SUBSEQUENT_TRANSITION_APPLICATION_DECISION = (
        "INVALID_SUBSEQUENT_TRANSITION_APPLICATION_DECISION"
    )


class Phase8OfflineReplaySubsequentProgressedSessionStateError(
    RuntimeError,
):
    """Structured subsequent progressed-state failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplaySubsequentProgressedSessionStateErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplaySubsequentProgressedSessionStateErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 subsequent progressed offline "
            f"replay-session state error [{self.reason.value}]: "
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

    for attribute_name in (
        "fetches_data",
        "initializes_mt5",
        "executes_replay",
        "evaluates_strategy",
        "executes_simulation",
        "emits_orders",
        "starts_session",
        "starts_replay",
    ):
        if hasattr(subject, attribute_name) and getattr(subject, attribute_name):
            return False

    return True


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySubsequentProgressedSessionStatePolicy:
    """Strict reusable state requirements after three events."""

    application_receipt_verified: bool = True
    prior_progressed_state_immutable: bool = True
    counters_match_receipt: bool = True
    sequence_continuity_verified: bool = True
    last_consumed_event_bound: bool = True
    next_event_bound: bool = True
    forward_only: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "application_receipt_verified",
            "prior_progressed_state_immutable",
            "counters_match_receipt",
            "sequence_continuity_verified",
            "last_consumed_event_bound",
            "next_event_bound",
            "forward_only",
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
                self.application_receipt_verified,
                self.prior_progressed_state_immutable,
                self.counters_match_receipt,
                self.sequence_continuity_verified,
                self.last_consumed_event_bound,
                self.next_event_bound,
                self.forward_only,
                self.in_memory_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_state_payload(
    *,
    schema_version: str,
    application_receipt_id: str,
    application_digest: str,
    subsequent_transition_contract_id: str,
    subsequent_transition_contract_digest: str,
    prior_progressed_state_id: str,
    prior_progressed_state_digest: str,
    event_batch_id: str,
    event_batch_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    state_mode: (Phase8OfflineReplaySubsequentProgressedSessionStateMode),
    lifecycle: (Phase8OfflineReplaySubsequentProgressedSessionLifecycle),
    state_version: int,
    cursor_index: int,
    consumed_count: int,
    remaining_count: int,
    total_event_count: int,
    last_consumed_sequence_index: int,
    last_consumed_event_id: str,
    last_consumed_event_digest: str,
    last_consumed_event_time: datetime,
    last_consumed_event_timeframe: Phase8Timeframe,
    next_event_sequence_index: int,
    next_event_id: str,
    next_event_digest: str,
    next_event_time: datetime,
    next_event_timeframe: Phase8Timeframe,
    completion_reached: bool,
    policy: (Phase8OfflineReplaySubsequentProgressedSessionStatePolicy),
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"APPLICATION_RECEIPT_ID={application_receipt_id}",
            f"APPLICATION_DIGEST={application_digest}",
            (f"SUBSEQUENT_TRANSITION_CONTRACT_ID={subsequent_transition_contract_id}"),
            (f"SUBSEQUENT_TRANSITION_CONTRACT_DIGEST={subsequent_transition_contract_digest}"),
            (f"PRIOR_PROGRESSED_STATE_ID={prior_progressed_state_id}"),
            (f"PRIOR_PROGRESSED_STATE_DIGEST={prior_progressed_state_digest}"),
            f"EVENT_BATCH_ID={event_batch_id}",
            f"EVENT_BATCH_DIGEST={event_batch_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"SOURCE_NAME={source_name}",
            (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
            ("TIMEFRAMES=" + ",".join(timeframe.value for timeframe in timeframes)),
            f"STATE_MODE={state_mode.value}",
            f"LIFECYCLE={lifecycle.value}",
            f"STATE_VERSION={state_version}",
            f"CURSOR_INDEX={cursor_index}",
            f"CONSUMED_COUNT={consumed_count}",
            f"REMAINING_COUNT={remaining_count}",
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"LAST_CONSUMED_SEQUENCE_INDEX={last_consumed_sequence_index}"),
            (f"LAST_CONSUMED_EVENT_ID={last_consumed_event_id}"),
            (f"LAST_CONSUMED_EVENT_DIGEST={last_consumed_event_digest}"),
            (f"LAST_CONSUMED_EVENT_TIME={_canonical_datetime(last_consumed_event_time)}"),
            (f"LAST_CONSUMED_EVENT_TIMEFRAME={last_consumed_event_timeframe.value}"),
            (f"NEXT_EVENT_SEQUENCE_INDEX={next_event_sequence_index}"),
            f"NEXT_EVENT_ID={next_event_id}",
            f"NEXT_EVENT_DIGEST={next_event_digest}",
            (f"NEXT_EVENT_TIME={_canonical_datetime(next_event_time)}"),
            (f"NEXT_EVENT_TIMEFRAME={next_event_timeframe.value}"),
            (f"COMPLETION_REACHED={str(completion_reached).lower()}"),
            (f"APPLICATION_RECEIPT_VERIFIED={str(policy.application_receipt_verified).lower()}"),
            (
                "PRIOR_PROGRESSED_STATE_IMMUTABLE="
                f"{str(policy.prior_progressed_state_immutable).lower()}"
            ),
            (f"COUNTERS_MATCH_RECEIPT={str(policy.counters_match_receipt).lower()}"),
            (f"SEQUENCE_CONTINUITY_VERIFIED={str(policy.sequence_continuity_verified).lower()}"),
            (f"LAST_CONSUMED_EVENT_BOUND={str(policy.last_consumed_event_bound).lower()}"),
            (f"NEXT_EVENT_BOUND={str(policy.next_event_bound).lower()}"),
            (f"FORWARD_ONLY={str(policy.forward_only).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "SUBSEQUENT_PROGRESSED_STATE_CREATED=true",
            "ADDITIONAL_TRANSITION_EXECUTED=false",
            "ADDITIONAL_EVENT_CONSUMPTION=false",
            "ADDITIONAL_CURSOR_ADVANCEMENT=false",
            "REPLAY_LOOP_EXECUTION=false",
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
class StrategyPhase8OfflineReplaySubsequentProgressedSessionState:
    """
    Immutable reusable session state after three events.

    It represents cursor three, three consumed events and
    797 remaining events without applying another transition.
    """

    subsequent_transition_application_decision: Phase8OfflineReplaySubsequentTransitionApplicationDecision = field(
        repr=False
    )
    policy: Phase8OfflineReplaySubsequentProgressedSessionStatePolicy
    schema_version: str
    application_receipt_id: str
    application_digest: str
    subsequent_transition_contract_id: str
    subsequent_transition_contract_digest: str
    prior_progressed_state_id: str
    prior_progressed_state_digest: str
    event_batch_id: str
    event_batch_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    state_mode: Phase8OfflineReplaySubsequentProgressedSessionStateMode
    lifecycle: Phase8OfflineReplaySubsequentProgressedSessionLifecycle
    state_version: int
    cursor_index: int
    consumed_count: int
    remaining_count: int
    total_event_count: int
    last_consumed_sequence_index: int
    last_consumed_event_id: str
    last_consumed_event_digest: str
    last_consumed_event_time: datetime
    last_consumed_event_timeframe: Phase8Timeframe
    next_event_sequence_index: int
    next_event_id: str
    next_event_digest: str
    next_event_time: datetime
    next_event_timeframe: Phase8Timeframe
    completion_reached: bool
    state_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.subsequent_transition_application_decision,
            Phase8OfflineReplaySubsequentTransitionApplicationDecision,
        ):
            raise ValueError(
                "subsequent_transition_application_decision "
                "must be a "
                "Phase8OfflineReplaySubsequentTransitionApplicationDecision."
            )

        if not (self.subsequent_transition_application_decision.is_applied):
            raise ValueError(
                "A subsequent progressed session state "
                "requires an applied subsequent-transition "
                "receipt."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplaySubsequentProgressedSessionStatePolicy,
        ):
            raise ValueError(
                "policy must be a Phase8OfflineReplaySubsequentProgressedSessionStatePolicy."
            )

        if not self.policy.is_strict:
            raise ValueError(
                "Subsequent progressed-state policy must remain strict and no-lookahead."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (
            PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_PROGRESSED_SESSION_STATE_SCHEMA_VERSION
        ):
            raise ValueError(
                "schema_version must match the current subsequent progressed-state schema."
            )

        string_fields = (
            (
                "application_receipt_id",
                self.application_receipt_id,
            ),
            ("application_digest", self.application_digest),
            (
                "subsequent_transition_contract_id",
                self.subsequent_transition_contract_id,
            ),
            (
                "subsequent_transition_contract_digest",
                self.subsequent_transition_contract_digest,
            ),
            (
                "prior_progressed_state_id",
                self.prior_progressed_state_id,
            ),
            (
                "prior_progressed_state_digest",
                self.prior_progressed_state_digest,
            ),
            ("event_batch_id", self.event_batch_id),
            ("event_batch_digest", self.event_batch_digest),
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            (
                "last_consumed_event_id",
                self.last_consumed_event_id,
            ),
            (
                "last_consumed_event_digest",
                self.last_consumed_event_digest,
            ),
            ("next_event_id", self.next_event_id),
            ("next_event_digest", self.next_event_digest),
            ("state_digest", self.state_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "application_digest",
            "subsequent_transition_contract_digest",
            "prior_progressed_state_digest",
            "event_batch_digest",
            "last_consumed_event_digest",
            "next_event_digest",
            "state_digest",
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
            self.state_mode,
            Phase8OfflineReplaySubsequentProgressedSessionStateMode,
        ):
            raise ValueError(
                "state_mode must be a "
                "Phase8OfflineReplaySubsequentProgressedSessionStateMode "
                "member."
            )

        if self.state_mode != (
            Phase8OfflineReplaySubsequentProgressedSessionStateMode.IMMUTABLE_SUBSEQUENT_PROGRESSED_STATE
        ):
            raise ValueError("state_mode must remain IMMUTABLE_SUBSEQUENT_PROGRESSED_STATE.")

        if not isinstance(
            self.lifecycle,
            Phase8OfflineReplaySubsequentProgressedSessionLifecycle,
        ):
            raise ValueError(
                "lifecycle must be a "
                "Phase8OfflineReplaySubsequentProgressedSessionLifecycle "
                "member."
            )

        if self.lifecycle != (Phase8OfflineReplaySubsequentProgressedSessionLifecycle.ACTIVE):
            raise ValueError("lifecycle must remain ACTIVE.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not isinstance(
            self.last_consumed_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("last_consumed_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(
            self.next_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("next_event_timeframe must be a Phase8Timeframe member.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        last_consumed_event_time = _aware_datetime(
            self.last_consumed_event_time,
            "last_consumed_event_time",
        )
        next_event_time = _aware_datetime(
            self.next_event_time,
            "next_event_time",
        )

        if last_consumed_event_time > captured_at:
            raise ValueError("last_consumed_event_time cannot exceed captured_at.")

        if next_event_time > captured_at:
            raise ValueError("next_event_time cannot exceed captured_at.")

        if next_event_time < last_consumed_event_time:
            raise ValueError("next_event_time cannot precede the last consumed event.")

        state_version = _positive_integer(
            self.state_version,
            "state_version",
        )
        cursor_index = _positive_integer(
            self.cursor_index,
            "cursor_index",
        )
        consumed_count = _positive_integer(
            self.consumed_count,
            "consumed_count",
        )
        remaining_count = _positive_integer(
            self.remaining_count,
            "remaining_count",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )
        last_consumed_sequence_index = _positive_integer(
            self.last_consumed_sequence_index,
            "last_consumed_sequence_index",
        )
        next_event_sequence_index = _positive_integer(
            self.next_event_sequence_index,
            "next_event_sequence_index",
        )
        completion_reached = _strict_boolean(
            self.completion_reached,
            "completion_reached",
        )

        if state_version != 3:
            raise ValueError("state_version must remain three after the third replay transition.")

        if cursor_index != consumed_count:
            raise ValueError(
                "cursor_index must equal consumed_count under next-event cursor semantics."
            )

        if consumed_count + remaining_count != (total_event_count):
            raise ValueError("consumed_count plus remaining_count must equal total_event_count.")

        if last_consumed_sequence_index != (cursor_index - 1):
            raise ValueError("last_consumed_sequence_index must equal cursor_index minus one.")

        if next_event_sequence_index != cursor_index:
            raise ValueError("next_event_sequence_index must equal cursor_index.")

        if completion_reached:
            raise ValueError("The state after three events cannot be complete.")

        application_receipt = self.subsequent_transition_application_decision.receipt_required
        transition_contract = application_receipt.transition_contract
        prior_progressed_state = application_receipt.progressed_state
        event_batch = application_receipt.event_batch

        comparisons = (
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
                "subsequent_transition_contract_id",
                normalized_strings["subsequent_transition_contract_id"],
                transition_contract.stable_id,
            ),
            (
                "subsequent_transition_contract_digest",
                normalized_strings["subsequent_transition_contract_digest"],
                transition_contract.transition_digest,
            ),
            (
                "prior_progressed_state_id",
                normalized_strings["prior_progressed_state_id"],
                prior_progressed_state.stable_id,
            ),
            (
                "prior_progressed_state_digest",
                normalized_strings["prior_progressed_state_digest"],
                prior_progressed_state.state_digest,
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
                application_receipt.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                application_receipt.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable "
                    "subsequent-transition application "
                    "lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Subsequent progressed states support Gold/XAUUSD only.")

        if self.direction != application_receipt.direction:
            raise ValueError("direction must match the application receipt.")

        if self.side != application_receipt.side:
            raise ValueError("side must match the application receipt.")

        if captured_at != application_receipt.captured_at:
            raise ValueError("captured_at must match the application receipt.")

        if self.timeframes != application_receipt.timeframes:
            raise ValueError("timeframes must match the application receipt.")

        numeric_comparisons = (
            (
                "cursor_index",
                cursor_index,
                application_receipt.resulting_cursor_index,
            ),
            (
                "consumed_count",
                consumed_count,
                application_receipt.resulting_consumed_count,
            ),
            (
                "remaining_count",
                remaining_count,
                application_receipt.resulting_remaining_count,
            ),
            (
                "total_event_count",
                total_event_count,
                application_receipt.total_event_count,
            ),
            (
                "last_consumed_sequence_index",
                last_consumed_sequence_index,
                (application_receipt.last_consumed_sequence_index),
            ),
            (
                "next_event_sequence_index",
                next_event_sequence_index,
                (application_receipt.next_event_sequence_index),
            ),
        )

        for field_name, supplied, expected in numeric_comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the subsequent-transition application receipt."
                )

        if completion_reached != (application_receipt.completion_reached):
            raise ValueError("completion_reached must match the application receipt.")

        last_consumed_event = application_receipt.consumed_event
        next_event = application_receipt.next_event

        if normalized_strings["last_consumed_event_id"] != last_consumed_event.stable_id:
            raise ValueError("last_consumed_event_id must match the third consumed event.")

        if normalized_strings["last_consumed_event_digest"] != last_consumed_event.event_digest:
            raise ValueError("last_consumed_event_digest must match the third consumed event.")

        if last_consumed_event_time != (last_consumed_event.event_time):
            raise ValueError("last_consumed_event_time must match the third consumed event.")

        if self.last_consumed_event_timeframe != (last_consumed_event.timeframe):
            raise ValueError("last_consumed_event_timeframe must match the third consumed event.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at cursor three.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at cursor three.")

        if next_event_time != next_event.event_time:
            raise ValueError("next_event_time must match the event at cursor three.")

        if self.next_event_timeframe != next_event.timeframe:
            raise ValueError("next_event_timeframe must match the event at cursor three.")

        if last_consumed_event.event_time != (last_consumed_event.close_time):
            raise ValueError("The last consumed event must represent a closed candle.")

        if next_event.event_time != next_event.close_time:
            raise ValueError("The next event must represent a closed candle.")

        if prior_progressed_state.cursor_index != 2:
            raise ValueError("The immutable prior progressed cursor was altered.")

        if prior_progressed_state.consumed_count != 2:
            raise ValueError("The immutable prior progressed consumed count was altered.")

        if prior_progressed_state.remaining_count != 798:
            raise ValueError("The immutable prior progressed remaining count was altered.")

        if last_consumed_sequence_index != (
            prior_progressed_state.last_consumed_sequence_index + 1
        ):
            raise ValueError("Subsequent progressed-state sequence continuity is invalid.")

        safe_subjects = (
            self.subsequent_transition_application_decision,
            application_receipt,
            (application_receipt.subsequent_transition_contract_decision),
            transition_contract,
            transition_contract.progressed_state_decision,
            prior_progressed_state,
            event_batch,
        )

        if not all(_has_safe_external_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Subsequent progressed-state lineage violates the external-I/O or broker boundary."
            )

        canonical_payload = _canonical_state_payload(
            schema_version=schema_version,
            application_receipt_id=normalized_strings["application_receipt_id"],
            application_digest=normalized_strings["application_digest"],
            subsequent_transition_contract_id=(
                normalized_strings["subsequent_transition_contract_id"]
            ),
            subsequent_transition_contract_digest=(
                normalized_strings["subsequent_transition_contract_digest"]
            ),
            prior_progressed_state_id=normalized_strings["prior_progressed_state_id"],
            prior_progressed_state_digest=(normalized_strings["prior_progressed_state_digest"]),
            event_batch_id=normalized_strings["event_batch_id"],
            event_batch_digest=normalized_strings["event_batch_digest"],
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            state_mode=self.state_mode,
            lifecycle=self.lifecycle,
            state_version=state_version,
            cursor_index=cursor_index,
            consumed_count=consumed_count,
            remaining_count=remaining_count,
            total_event_count=total_event_count,
            last_consumed_sequence_index=(last_consumed_sequence_index),
            last_consumed_event_id=normalized_strings["last_consumed_event_id"],
            last_consumed_event_digest=(normalized_strings["last_consumed_event_digest"]),
            last_consumed_event_time=(last_consumed_event_time),
            last_consumed_event_timeframe=(self.last_consumed_event_timeframe),
            next_event_sequence_index=(next_event_sequence_index),
            next_event_id=normalized_strings["next_event_id"],
            next_event_digest=normalized_strings["next_event_digest"],
            next_event_time=next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            completion_reached=completion_reached,
            policy=self.policy,
        )

        if normalized_strings["state_digest"] != (_sha256_digest(canonical_payload)):
            raise ValueError(
                "state_digest does not match the canonical subsequent progressed session state."
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
            "last_consumed_event_time",
            last_consumed_event_time,
        )
        object.__setattr__(
            self,
            "next_event_time",
            next_event_time,
        )
        object.__setattr__(
            self,
            "state_version",
            state_version,
        )
        object.__setattr__(
            self,
            "cursor_index",
            cursor_index,
        )
        object.__setattr__(
            self,
            "consumed_count",
            consumed_count,
        )
        object.__setattr__(
            self,
            "remaining_count",
            remaining_count,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )
        object.__setattr__(
            self,
            "last_consumed_sequence_index",
            last_consumed_sequence_index,
        )
        object.__setattr__(
            self,
            "next_event_sequence_index",
            next_event_sequence_index,
        )
        object.__setattr__(
            self,
            "completion_reached",
            completion_reached,
        )

    @property
    def application_receipt(
        self,
    ) -> StrategyPhase8OfflineReplaySubsequentTransitionApplicationReceipt:
        return self.subsequent_transition_application_decision.receipt_required

    @property
    def subsequent_transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySubsequentTransitionContract:
        return self.application_receipt.transition_contract

    @property
    def prior_progressed_state(
        self,
    ) -> StrategyPhase8OfflineReplayProgressedSessionState:
        return self.application_receipt.progressed_state

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.application_receipt.event_batch

    @property
    def last_consumed_event(
        self,
    ) -> Phase8OfflineReplayEvent:
        return self.application_receipt.consumed_event

    @property
    def next_event(self) -> Phase8OfflineReplayEvent:
        return self.application_receipt.next_event

    @property
    def canonical_payload(self) -> str:
        return _canonical_state_payload(
            schema_version=self.schema_version,
            application_receipt_id=(self.application_receipt_id),
            application_digest=self.application_digest,
            subsequent_transition_contract_id=(self.subsequent_transition_contract_id),
            subsequent_transition_contract_digest=(self.subsequent_transition_contract_digest),
            prior_progressed_state_id=(self.prior_progressed_state_id),
            prior_progressed_state_digest=(self.prior_progressed_state_digest),
            event_batch_id=self.event_batch_id,
            event_batch_digest=self.event_batch_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            timeframes=self.timeframes,
            state_mode=self.state_mode,
            lifecycle=self.lifecycle,
            state_version=self.state_version,
            cursor_index=self.cursor_index,
            consumed_count=self.consumed_count,
            remaining_count=self.remaining_count,
            total_event_count=self.total_event_count,
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            last_consumed_event_id=(self.last_consumed_event_id),
            last_consumed_event_digest=(self.last_consumed_event_digest),
            last_consumed_event_time=(self.last_consumed_event_time),
            last_consumed_event_timeframe=(self.last_consumed_event_timeframe),
            next_event_sequence_index=(self.next_event_sequence_index),
            next_event_id=self.next_event_id,
            next_event_digest=self.next_event_digest,
            next_event_time=self.next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            completion_reached=self.completion_reached,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def is_subsequent_progressed_state(self) -> bool:
        return True

    @property
    def session_initialized(self) -> bool:
        return True

    @property
    def session_active(self) -> bool:
        return True

    @property
    def has_next_event(self) -> bool:
        return not self.completion_reached

    @property
    def prior_state_preserved(self) -> bool:
        return True

    @property
    def represents_applied_transition(self) -> bool:
        return True

    @property
    def creates_next_state(self) -> bool:
        return True

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
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def can_continue_to_future_transition_contract(
        self,
    ) -> bool:
        return self.has_next_event

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

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
    def subsequent_progressed_state_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_"
            "PROGRESSED_SESSION_STATE:"
            f"STATE_SHA256[{self.state_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.subsequent_transition_application_decision.stable_id}:"
            f"{self.subsequent_progressed_state_id}"
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySubsequentProgressedSessionStateDecision:
    """Immutable subsequent progressed-state decision."""

    subsequent_transition_application_decision: Phase8OfflineReplaySubsequentTransitionApplicationDecision = field(
        repr=False
    )
    status: Phase8OfflineReplaySubsequentProgressedSessionStateStatus
    reason: Phase8OfflineReplaySubsequentProgressedSessionStateReason
    blockers: tuple[
        Phase8OfflineReplaySubsequentProgressedSessionStateBlocker,
        ...,
    ]
    state: StrategyPhase8OfflineReplaySubsequentProgressedSessionState | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.subsequent_transition_application_decision,
            Phase8OfflineReplaySubsequentTransitionApplicationDecision,
        ):
            raise ValueError(
                "subsequent_transition_application_decision "
                "must be a "
                "Phase8OfflineReplaySubsequentTransitionApplicationDecision."
            )

        try:
            status = Phase8OfflineReplaySubsequentProgressedSessionStateStatus(self.status)
            reason = Phase8OfflineReplaySubsequentProgressedSessionStateReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported subsequent progressed-state status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplaySubsequentProgressedSessionStateBlocker(blocker)
            for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Subsequent progressed-state blockers cannot contain duplicates.")

        if self.subsequent_transition_application_decision.is_blocked:
            if (
                status != (Phase8OfflineReplaySubsequentProgressedSessionStateStatus.BLOCKED)
                or reason
                != (
                    Phase8OfflineReplaySubsequentProgressedSessionStateReason.SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED
                )
                or blockers
                != (
                    Phase8OfflineReplaySubsequentProgressedSessionStateBlocker.SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED,
                )
                or self.state is not None
            ):
                raise ValueError(
                    "Blocked subsequent progressed-state "
                    "result does not match its application "
                    "decision."
                )
        else:
            if (
                status != (Phase8OfflineReplaySubsequentProgressedSessionStateStatus.CREATED)
                or reason != (Phase8OfflineReplaySubsequentProgressedSessionStateReason.CREATED)
                or blockers
                or not isinstance(
                    self.state,
                    StrategyPhase8OfflineReplaySubsequentProgressedSessionState,
                )
                or (
                    self.state.subsequent_transition_application_decision
                    is not self.subsequent_transition_application_decision
                )
            ):
                raise ValueError(
                    "Created subsequent progressed-state "
                    "result does not match its application "
                    "decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.subsequent_transition_application_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.subsequent_transition_application_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplaySubsequentProgressedSessionStateStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_state(self) -> bool:
        return self.state is not None

    @property
    def state_required(
        self,
    ) -> StrategyPhase8OfflineReplaySubsequentProgressedSessionState:
        if self.state is None:
            raise ValueError(
                "No Phase 8 subsequent progressed offline replay-session state was created."
            )

        return self.state

    @property
    def creates_next_state(self) -> bool:
        return self.is_created

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
    def can_continue_to_future_transition_contract(
        self,
    ) -> bool:
        return self.is_created and self.state_required.has_next_event

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
            f"{self.subsequent_transition_application_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_"
            "PROGRESSED_SESSION_STATE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplaySubsequentProgressedSessionStateFactory:
    """Pure immutable subsequent progressed-state factory."""

    def generate(
        self,
        subsequent_transition_application_decision: (
            Phase8OfflineReplaySubsequentTransitionApplicationDecision
        ),
        policy: (Phase8OfflineReplaySubsequentProgressedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplaySubsequentProgressedSessionStateDecision:
        if not isinstance(
            subsequent_transition_application_decision,
            Phase8OfflineReplaySubsequentTransitionApplicationDecision,
        ):
            raise (
                Phase8OfflineReplaySubsequentProgressedSessionStateError(
                    Phase8OfflineReplaySubsequentProgressedSessionStateErrorReason.INVALID_SUBSEQUENT_TRANSITION_APPLICATION_DECISION,
                    "subsequent_transition_application_decision "
                    "must be a "
                    "Phase8OfflineReplaySubsequentTransitionApplicationDecision.",
                )
            )

        selected_policy = policy or (Phase8OfflineReplaySubsequentProgressedSessionStatePolicy())

        if not isinstance(
            selected_policy,
            Phase8OfflineReplaySubsequentProgressedSessionStatePolicy,
        ):
            raise ValueError(
                "policy must be a Phase8OfflineReplaySubsequentProgressedSessionStatePolicy."
            )

        if subsequent_transition_application_decision.is_blocked:
            return Phase8OfflineReplaySubsequentProgressedSessionStateDecision(
                subsequent_transition_application_decision=(
                    subsequent_transition_application_decision
                ),
                status=(Phase8OfflineReplaySubsequentProgressedSessionStateStatus.BLOCKED),
                reason=(
                    Phase8OfflineReplaySubsequentProgressedSessionStateReason.SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED
                ),
                blockers=(
                    Phase8OfflineReplaySubsequentProgressedSessionStateBlocker.SUBSEQUENT_TRANSITION_APPLICATION_BLOCKED,
                ),
                state=None,
            )

        application_receipt = subsequent_transition_application_decision.receipt_required
        transition_contract = application_receipt.transition_contract
        prior_progressed_state = application_receipt.progressed_state
        event_batch = application_receipt.event_batch
        last_consumed_event = application_receipt.consumed_event
        next_event = application_receipt.next_event

        canonical_payload = _canonical_state_payload(
            schema_version=(
                PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_PROGRESSED_SESSION_STATE_SCHEMA_VERSION
            ),
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            subsequent_transition_contract_id=(transition_contract.stable_id),
            subsequent_transition_contract_digest=(transition_contract.transition_digest),
            prior_progressed_state_id=(prior_progressed_state.stable_id),
            prior_progressed_state_digest=(prior_progressed_state.state_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=application_receipt.broker_symbol,
            direction=application_receipt.direction,
            side=application_receipt.side,
            source_name=application_receipt.source_name,
            captured_at=application_receipt.captured_at,
            timeframes=application_receipt.timeframes,
            state_mode=(
                Phase8OfflineReplaySubsequentProgressedSessionStateMode.IMMUTABLE_SUBSEQUENT_PROGRESSED_STATE
            ),
            lifecycle=(Phase8OfflineReplaySubsequentProgressedSessionLifecycle.ACTIVE),
            state_version=3,
            cursor_index=(application_receipt.resulting_cursor_index),
            consumed_count=(application_receipt.resulting_consumed_count),
            remaining_count=(application_receipt.resulting_remaining_count),
            total_event_count=(application_receipt.total_event_count),
            last_consumed_sequence_index=(application_receipt.last_consumed_sequence_index),
            last_consumed_event_id=(last_consumed_event.stable_id),
            last_consumed_event_digest=(last_consumed_event.event_digest),
            last_consumed_event_time=(last_consumed_event.event_time),
            last_consumed_event_timeframe=(last_consumed_event.timeframe),
            next_event_sequence_index=(application_receipt.next_event_sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            completion_reached=(application_receipt.completion_reached),
            policy=selected_policy,
        )

        state = StrategyPhase8OfflineReplaySubsequentProgressedSessionState(
            subsequent_transition_application_decision=(subsequent_transition_application_decision),
            policy=selected_policy,
            schema_version=(
                PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_PROGRESSED_SESSION_STATE_SCHEMA_VERSION
            ),
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            subsequent_transition_contract_id=(transition_contract.stable_id),
            subsequent_transition_contract_digest=(transition_contract.transition_digest),
            prior_progressed_state_id=(prior_progressed_state.stable_id),
            prior_progressed_state_digest=(prior_progressed_state.state_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=(event_batch.batch_digest),
            broker_symbol=(application_receipt.broker_symbol),
            direction=application_receipt.direction,
            side=application_receipt.side,
            source_name=application_receipt.source_name,
            captured_at=application_receipt.captured_at,
            timeframes=application_receipt.timeframes,
            state_mode=(
                Phase8OfflineReplaySubsequentProgressedSessionStateMode.IMMUTABLE_SUBSEQUENT_PROGRESSED_STATE
            ),
            lifecycle=(Phase8OfflineReplaySubsequentProgressedSessionLifecycle.ACTIVE),
            state_version=3,
            cursor_index=(application_receipt.resulting_cursor_index),
            consumed_count=(application_receipt.resulting_consumed_count),
            remaining_count=(application_receipt.resulting_remaining_count),
            total_event_count=(application_receipt.total_event_count),
            last_consumed_sequence_index=(application_receipt.last_consumed_sequence_index),
            last_consumed_event_id=(last_consumed_event.stable_id),
            last_consumed_event_digest=(last_consumed_event.event_digest),
            last_consumed_event_time=(last_consumed_event.event_time),
            last_consumed_event_timeframe=(last_consumed_event.timeframe),
            next_event_sequence_index=(application_receipt.next_event_sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=(next_event.event_digest),
            next_event_time=next_event.event_time,
            next_event_timeframe=(next_event.timeframe),
            completion_reached=(application_receipt.completion_reached),
            state_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplaySubsequentProgressedSessionStateDecision(
            subsequent_transition_application_decision=(subsequent_transition_application_decision),
            status=(Phase8OfflineReplaySubsequentProgressedSessionStateStatus.CREATED),
            reason=(Phase8OfflineReplaySubsequentProgressedSessionStateReason.CREATED),
            blockers=(),
            state=state,
        )

    def build(
        self,
        subsequent_transition_application_decision: (
            Phase8OfflineReplaySubsequentTransitionApplicationDecision
        ),
        policy: (Phase8OfflineReplaySubsequentProgressedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplaySubsequentProgressedSessionStateDecision:
        return self.generate(
            subsequent_transition_application_decision,
            policy,
        )

    def evaluate(
        self,
        subsequent_transition_application_decision: (
            Phase8OfflineReplaySubsequentTransitionApplicationDecision
        ),
        policy: (Phase8OfflineReplaySubsequentProgressedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplaySubsequentProgressedSessionStateDecision:
        return self.generate(
            subsequent_transition_application_decision,
            policy,
        )


def generate_phase8_offline_replay_subsequent_progressed_session_state(
    subsequent_transition_application_decision: (
        Phase8OfflineReplaySubsequentTransitionApplicationDecision
    ),
    policy: (Phase8OfflineReplaySubsequentProgressedSessionStatePolicy | None) = None,
) -> Phase8OfflineReplaySubsequentProgressedSessionStateDecision:
    return StrategyPhase8OfflineReplaySubsequentProgressedSessionStateFactory().generate(
        subsequent_transition_application_decision,
        policy,
    )


Phase8OfflineReplaySubsequentProgressedSessionState = (
    StrategyPhase8OfflineReplaySubsequentProgressedSessionState
)
Phase8OfflineReplaySubsequentProgressedSessionStateFactory = (
    StrategyPhase8OfflineReplaySubsequentProgressedSessionStateFactory
)
