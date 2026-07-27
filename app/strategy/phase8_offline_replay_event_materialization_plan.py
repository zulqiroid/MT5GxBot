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
    Phase8OfflineReplayEventContractDecision,
    Phase8OfflineReplayEventField,
    Phase8OfflineReplayEventKind,
    Phase8OfflineReplayEventTimestampSource,
    StrategyPhase8OfflineReplayEventContract,
)
from app.strategy.phase8_offline_replay_plan import (
    Phase8OfflineReplayClock,
    Phase8OfflineReplayMergeMode,
    Phase8OfflineReplayTieBreak,
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_PLAN_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


_REQUIRED_PRIORITIES = (
    0,
    1,
    2,
    3,
)


_REQUIRED_SERIES_INDICES = (
    0,
    1,
    2,
    3,
)


class Phase8OfflineReplayEventMaterializationMode(
    str,
    Enum,
):
    IMMUTABLE_EVENT_BUILD = "IMMUTABLE_EVENT_BUILD"


class Phase8OfflineReplaySequenceAssignment(
    str,
    Enum,
):
    AFTER_STABLE_MERGE = "AFTER_STABLE_MERGE"


class Phase8OfflineReplayOrderingKey(str, Enum):
    EVENT_TIME_TIMEFRAME_PRIORITY_SERIES_CANDLE = "EVENT_TIME_TIMEFRAME_PRIORITY_SERIES_CANDLE"


class Phase8OfflineReplayEventMaterializationPlanStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayEventMaterializationPlanReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    EVENT_CONTRACT_BLOCKED = "EVENT_CONTRACT_BLOCKED"


class Phase8OfflineReplayEventMaterializationPlanBlocker(
    str,
    Enum,
):
    EVENT_CONTRACT_BLOCKED = "EVENT_CONTRACT_BLOCKED"


class Phase8OfflineReplayEventMaterializationPlanErrorReason(
    str,
    Enum,
):
    INVALID_EVENT_CONTRACT_DECISION = "INVALID_EVENT_CONTRACT_DECISION"


class Phase8OfflineReplayEventMaterializationPlanError(
    RuntimeError,
):
    """Structured materialization-plan failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayEventMaterializationPlanErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayEventMaterializationPlanErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 replay event materialization-plan error [{self.reason.value}]: {self.message}"
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
        "creates_events",
        "materializes_events",
        "emits_orders",
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
class Phase8OfflineReplayEventMaterializationPolicy:
    """Strict future event-materialization requirements."""

    snapshot_sources_only: bool = True
    stable_chronological_merge: bool = True
    assign_sequence_after_merge: bool = True
    validate_candle_digests: bool = True
    validate_series_digests: bool = True
    no_lookahead: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "snapshot_sources_only",
            "stable_chronological_merge",
            "assign_sequence_after_merge",
            "validate_candle_digests",
            "validate_series_digests",
            "no_lookahead",
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
                self.snapshot_sources_only,
                self.stable_chronological_merge,
                self.assign_sequence_after_merge,
                self.validate_candle_digests,
                self.validate_series_digests,
                self.no_lookahead,
            )
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayEventSourcePlan:
    """Immutable mapping for one snapshot candle series."""

    timeframe: Phase8Timeframe
    timeframe_priority: int
    series_index: int
    candle_count: int
    start_candle_index: int
    end_candle_index: int
    first_event_time: datetime
    last_event_time: datetime
    series_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("timeframe must be a Phase8Timeframe member.")

        timeframe_priority = _non_negative_integer(
            self.timeframe_priority,
            "timeframe_priority",
        )
        series_index = _non_negative_integer(
            self.series_index,
            "series_index",
        )
        candle_count = _positive_integer(
            self.candle_count,
            "candle_count",
        )
        start_candle_index = _non_negative_integer(
            self.start_candle_index,
            "start_candle_index",
        )
        end_candle_index = _non_negative_integer(
            self.end_candle_index,
            "end_candle_index",
        )

        if start_candle_index != 0:
            raise ValueError("start_candle_index must be zero.")

        if end_candle_index != candle_count - 1:
            raise ValueError("end_candle_index must equal candle_count minus one.")

        first_event_time = _aware_datetime(
            self.first_event_time,
            "first_event_time",
        )
        last_event_time = _aware_datetime(
            self.last_event_time,
            "last_event_time",
        )

        if last_event_time < first_event_time:
            raise ValueError("last_event_time cannot precede first_event_time.")

        series_digest = _non_empty_string(
            self.series_digest,
            "series_digest",
        )

        if not _is_lowercase_sha256(series_digest):
            raise ValueError("series_digest must be a lowercase SHA-256 hexadecimal value.")

        object.__setattr__(
            self,
            "timeframe_priority",
            timeframe_priority,
        )
        object.__setattr__(
            self,
            "series_index",
            series_index,
        )
        object.__setattr__(
            self,
            "candle_count",
            candle_count,
        )
        object.__setattr__(
            self,
            "start_candle_index",
            start_candle_index,
        )
        object.__setattr__(
            self,
            "end_candle_index",
            end_candle_index,
        )
        object.__setattr__(
            self,
            "first_event_time",
            first_event_time,
        )
        object.__setattr__(
            self,
            "last_event_time",
            last_event_time,
        )
        object.__setattr__(
            self,
            "series_digest",
            series_digest,
        )

    @property
    def planned_event_count(self) -> int:
        return self.candle_count

    @property
    def is_complete_series(self) -> bool:
        return self.start_candle_index == 0 and self.end_candle_index == self.candle_count - 1

    @property
    def canonical_row(self) -> str:
        return "|".join(
            (
                self.timeframe.value,
                str(self.timeframe_priority),
                str(self.series_index),
                str(self.candle_count),
                str(self.start_candle_index),
                str(self.end_candle_index),
                _canonical_datetime(self.first_event_time),
                _canonical_datetime(self.last_event_time),
                self.series_digest,
            )
        )


def _canonical_materialization_payload(
    *,
    schema_version: str,
    event_contract_id: str,
    event_contract_digest: str,
    replay_plan_id: str,
    replay_plan_digest: str,
    specification_id: str,
    specification_digest: str,
    input_package_id: str,
    input_digest: str,
    snapshot_id: str,
    snapshot_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    event_kind: Phase8OfflineReplayEventKind,
    timestamp_source: Phase8OfflineReplayEventTimestampSource,
    replay_clock: Phase8OfflineReplayClock,
    merge_mode: Phase8OfflineReplayMergeMode,
    tie_break: Phase8OfflineReplayTieBreak,
    materialization_mode: (Phase8OfflineReplayEventMaterializationMode),
    sequence_assignment: (Phase8OfflineReplaySequenceAssignment),
    ordering_key: Phase8OfflineReplayOrderingKey,
    event_fields: tuple[
        Phase8OfflineReplayEventField,
        ...,
    ],
    source_plans: tuple[
        Phase8OfflineReplayEventSourcePlan,
        ...,
    ],
    sequence_start: int,
    sequence_end: int,
    total_event_count: int,
    policy: Phase8OfflineReplayEventMaterializationPolicy,
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
        f"EVENT_CONTRACT_ID={event_contract_id}",
        (f"EVENT_CONTRACT_DIGEST={event_contract_digest}"),
        f"REPLAY_PLAN_ID={replay_plan_id}",
        f"REPLAY_PLAN_DIGEST={replay_plan_digest}",
        f"SPECIFICATION_ID={specification_id}",
        (f"SPECIFICATION_DIGEST={specification_digest}"),
        f"INPUT_PACKAGE_ID={input_package_id}",
        f"INPUT_DIGEST={input_digest}",
        f"SNAPSHOT_ID={snapshot_id}",
        f"SNAPSHOT_DIGEST={snapshot_digest}",
        f"BROKER_SYMBOL={broker_symbol}",
        f"DIRECTION={direction.value}",
        f"SIDE={side.value}",
        f"SOURCE_NAME={source_name}",
        (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
        f"EVENT_KIND={event_kind.value}",
        f"TIMESTAMP_SOURCE={timestamp_source.value}",
        f"REPLAY_CLOCK={replay_clock.value}",
        f"MERGE_MODE={merge_mode.value}",
        f"TIE_BREAK={tie_break.value}",
        (f"MATERIALIZATION_MODE={materialization_mode.value}"),
        (f"SEQUENCE_ASSIGNMENT={sequence_assignment.value}"),
        f"ORDERING_KEY={ordering_key.value}",
        f"EVENT_FIELD_COUNT={len(event_fields)}",
        f"SOURCE_PLAN_COUNT={len(source_plans)}",
        f"SEQUENCE_START={sequence_start}",
        f"SEQUENCE_END={sequence_end}",
        f"TOTAL_EVENT_COUNT={total_event_count}",
    ]

    for index, event_field in enumerate(
        event_fields,
        start=1,
    ):
        lines.append(f"EVENT_FIELD_{index}={event_field.value}")

    for index, source_plan in enumerate(
        source_plans,
        start=1,
    ):
        lines.append(f"SOURCE_PLAN_{index}={source_plan.canonical_row}")

    lines.extend(
        (
            (f"SNAPSHOT_SOURCES_ONLY={str(policy.snapshot_sources_only).lower()}"),
            (f"STABLE_CHRONOLOGICAL_MERGE={str(policy.stable_chronological_merge).lower()}"),
            (f"ASSIGN_SEQUENCE_AFTER_MERGE={str(policy.assign_sequence_after_merge).lower()}"),
            (f"VALIDATE_CANDLE_DIGESTS={str(policy.validate_candle_digests).lower()}"),
            (f"VALIDATE_SERIES_DIGESTS={str(policy.validate_series_digests).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            "EVENT_CREATION=false",
            "EVENT_MATERIALIZATION=false",
            "REPLAY_EXECUTION=false",
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

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class StrategyPhase8OfflineReplayEventMaterializationPlan:
    """
    Immutable plan for future replay-event materialization.

    This object defines source mappings, ordering and
    sequence bounds only. It does not create events, iterate
    candles, execute replay, evaluate strategy logic, fetch
    data, initialize MT5, write storage, contact a broker,
    or submit an order.
    """

    event_contract_decision: Phase8OfflineReplayEventContractDecision = field(repr=False)
    policy: Phase8OfflineReplayEventMaterializationPolicy
    schema_version: str
    event_contract_id: str
    event_contract_digest: str
    replay_plan_id: str
    replay_plan_digest: str
    specification_id: str
    specification_digest: str
    input_package_id: str
    input_digest: str
    snapshot_id: str
    snapshot_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    event_kind: Phase8OfflineReplayEventKind
    timestamp_source: Phase8OfflineReplayEventTimestampSource
    replay_clock: Phase8OfflineReplayClock
    merge_mode: Phase8OfflineReplayMergeMode
    tie_break: Phase8OfflineReplayTieBreak
    materialization_mode: Phase8OfflineReplayEventMaterializationMode
    sequence_assignment: Phase8OfflineReplaySequenceAssignment
    ordering_key: Phase8OfflineReplayOrderingKey
    event_fields: tuple[
        Phase8OfflineReplayEventField,
        ...,
    ]
    source_plans: tuple[
        Phase8OfflineReplayEventSourcePlan,
        ...,
    ] = field(repr=False)
    sequence_start: int
    sequence_end: int
    total_event_count: int
    materialization_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.event_contract_decision,
            Phase8OfflineReplayEventContractDecision,
        ):
            raise ValueError(
                "event_contract_decision must be a Phase8OfflineReplayEventContractDecision."
            )

        if not self.event_contract_decision.is_created:
            raise ValueError(
                "A materialization plan requires a created offline replay-event contract."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplayEventMaterializationPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayEventMaterializationPolicy.")

        if not self.policy.is_strict:
            raise ValueError("Event-materialization policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_PLAN_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current event-materialization plan schema."
            )

        string_fields = (
            ("event_contract_id", self.event_contract_id),
            (
                "event_contract_digest",
                self.event_contract_digest,
            ),
            ("replay_plan_id", self.replay_plan_id),
            (
                "replay_plan_digest",
                self.replay_plan_digest,
            ),
            ("specification_id", self.specification_id),
            (
                "specification_digest",
                self.specification_digest,
            ),
            ("input_package_id", self.input_package_id),
            ("input_digest", self.input_digest),
            ("snapshot_id", self.snapshot_id),
            ("snapshot_digest", self.snapshot_digest),
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            (
                "materialization_digest",
                self.materialization_digest,
            ),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "event_contract_digest",
            "replay_plan_digest",
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "materialization_digest",
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
                "event_kind",
                self.event_kind,
                Phase8OfflineReplayEventKind,
            ),
            (
                "timestamp_source",
                self.timestamp_source,
                Phase8OfflineReplayEventTimestampSource,
            ),
            (
                "replay_clock",
                self.replay_clock,
                Phase8OfflineReplayClock,
            ),
            (
                "merge_mode",
                self.merge_mode,
                Phase8OfflineReplayMergeMode,
            ),
            (
                "tie_break",
                self.tie_break,
                Phase8OfflineReplayTieBreak,
            ),
            (
                "materialization_mode",
                self.materialization_mode,
                Phase8OfflineReplayEventMaterializationMode,
            ),
            (
                "sequence_assignment",
                self.sequence_assignment,
                Phase8OfflineReplaySequenceAssignment,
            ),
            (
                "ordering_key",
                self.ordering_key,
                Phase8OfflineReplayOrderingKey,
            ),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{field_name} must be a {enum_type.__name__} member.")

        if self.materialization_mode != (
            Phase8OfflineReplayEventMaterializationMode.IMMUTABLE_EVENT_BUILD
        ):
            raise ValueError("materialization_mode must remain IMMUTABLE_EVENT_BUILD.")

        if self.sequence_assignment != (Phase8OfflineReplaySequenceAssignment.AFTER_STABLE_MERGE):
            raise ValueError("sequence_assignment must remain AFTER_STABLE_MERGE.")

        if self.ordering_key != (
            Phase8OfflineReplayOrderingKey.EVENT_TIME_TIMEFRAME_PRIORITY_SERIES_CANDLE
        ):
            raise ValueError(
                "ordering_key must preserve the exact deterministic event-ordering tuple."
            )

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )

        if not isinstance(self.event_fields, tuple):
            raise ValueError("event_fields must be a tuple.")

        if not all(
            isinstance(
                event_field,
                Phase8OfflineReplayEventField,
            )
            for event_field in self.event_fields
        ):
            raise ValueError("event_fields must contain Phase8OfflineReplayEventField members.")

        if not isinstance(self.source_plans, tuple):
            raise ValueError("source_plans must be a tuple.")

        if len(self.source_plans) != 4:
            raise ValueError("source_plans must contain four entries.")

        if not all(
            isinstance(
                source_plan,
                Phase8OfflineReplayEventSourcePlan,
            )
            for source_plan in self.source_plans
        ):
            raise ValueError(
                "source_plans must contain Phase8OfflineReplayEventSourcePlan members."
            )

        if (
            tuple(source_plan.timeframe for source_plan in self.source_plans)
            != _REQUIRED_TIMEFRAMES
        ):
            raise ValueError("source_plans must preserve H4, H1, M15, and M5 deterministic order.")

        if (
            tuple(source_plan.timeframe_priority for source_plan in self.source_plans)
            != _REQUIRED_PRIORITIES
        ):
            raise ValueError("source_plans must preserve exact timeframe priorities.")

        if (
            tuple(source_plan.series_index for source_plan in self.source_plans)
            != _REQUIRED_SERIES_INDICES
        ):
            raise ValueError("source_plans must preserve exact series indices.")

        sequence_start = _non_negative_integer(
            self.sequence_start,
            "sequence_start",
        )
        sequence_end = _non_negative_integer(
            self.sequence_end,
            "sequence_end",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )

        if sequence_start != 0:
            raise ValueError("sequence_start must be zero.")

        if sequence_end != total_event_count - 1:
            raise ValueError("sequence_end must equal total_event_count minus one.")

        if total_event_count != sum(
            source_plan.planned_event_count for source_plan in self.source_plans
        ):
            raise ValueError("total_event_count must equal the sum of source-plan events.")

        event_contract = self.event_contract_decision.event_contract_required
        replay_plan = event_contract.plan
        specification = event_contract.specification
        input_package = event_contract.input_package
        snapshot = event_contract.snapshot

        comparisons = (
            (
                "event_contract_id",
                normalized_strings["event_contract_id"],
                event_contract.stable_id,
            ),
            (
                "event_contract_digest",
                normalized_strings["event_contract_digest"],
                event_contract.contract_digest,
            ),
            (
                "replay_plan_id",
                normalized_strings["replay_plan_id"],
                replay_plan.stable_id,
            ),
            (
                "replay_plan_digest",
                normalized_strings["replay_plan_digest"],
                replay_plan.plan_digest,
            ),
            (
                "specification_id",
                normalized_strings["specification_id"],
                specification.stable_id,
            ),
            (
                "specification_digest",
                normalized_strings["specification_digest"],
                specification.specification_digest,
            ),
            (
                "input_package_id",
                normalized_strings["input_package_id"],
                input_package.stable_id,
            ),
            (
                "input_digest",
                normalized_strings["input_digest"],
                input_package.input_digest,
            ),
            (
                "snapshot_id",
                normalized_strings["snapshot_id"],
                snapshot.stable_id,
            ),
            (
                "snapshot_digest",
                normalized_strings["snapshot_digest"],
                snapshot.snapshot_digest,
            ),
            (
                "broker_symbol",
                normalized_strings["broker_symbol"],
                event_contract.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                event_contract.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable replay-event contract lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Event-materialization plans support Gold/XAUUSD only.")

        if self.direction != event_contract.direction:
            raise ValueError("direction must match the replay-event contract.")

        if self.side != event_contract.side:
            raise ValueError("side must match the replay-event contract.")

        if captured_at != event_contract.captured_at:
            raise ValueError("captured_at must match the replay-event contract.")

        contract_controls = (
            (
                "event_kind",
                self.event_kind,
                event_contract.event_kind,
            ),
            (
                "timestamp_source",
                self.timestamp_source,
                event_contract.timestamp_source,
            ),
            (
                "replay_clock",
                self.replay_clock,
                event_contract.replay_clock,
            ),
            (
                "merge_mode",
                self.merge_mode,
                event_contract.merge_mode,
            ),
            (
                "tie_break",
                self.tie_break,
                event_contract.tie_break,
            ),
            (
                "event_fields",
                self.event_fields,
                event_contract.event_fields,
            ),
        )

        for field_name, supplied, expected in contract_controls:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the replay-event contract.")

        for series_index, (
            replay_series_plan,
            source_plan,
        ) in enumerate(
            zip(
                replay_plan.series_plans,
                self.source_plans,
                strict=True,
            )
        ):
            expected_values = (
                replay_series_plan.timeframe,
                replay_series_plan.priority,
                series_index,
                replay_series_plan.candle_count,
                replay_series_plan.start_index,
                replay_series_plan.end_index,
                replay_series_plan.first_close_time,
                replay_series_plan.latest_close_time,
                replay_series_plan.series_digest,
            )
            supplied_values = (
                source_plan.timeframe,
                source_plan.timeframe_priority,
                source_plan.series_index,
                source_plan.candle_count,
                source_plan.start_candle_index,
                source_plan.end_candle_index,
                source_plan.first_event_time,
                source_plan.last_event_time,
                source_plan.series_digest,
            )

            if supplied_values != expected_values:
                raise ValueError(
                    f"{replay_series_plan.timeframe.value} "
                    "source plan must match the immutable "
                    "offline replay plan."
                )

            if source_plan.last_event_time > captured_at:
                raise ValueError(
                    f"{source_plan.timeframe.value} source plan cannot include an open candle."
                )

        if total_event_count != (event_contract.total_event_count):
            raise ValueError("total_event_count must match the replay-event contract.")

        if not event_contract.no_lookahead:
            raise ValueError("Replay-event contract must remain no-lookahead.")

        if not event_contract.zero_based_sequence:
            raise ValueError("Replay-event contract must require a zero-based sequence.")

        if event_contract.creates_events or event_contract.materializes_events:
            raise ValueError("Replay-event contract cannot create or materialize events.")

        safe_subjects = (
            self.event_contract_decision,
            event_contract,
            event_contract.plan_decision,
            replay_plan,
            replay_plan.specification_decision,
            specification,
            specification.input_decision,
            input_package,
            event_contract.verification_receipt,
            snapshot,
            event_contract.contract,
            event_contract.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Event-materialization lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_materialization_payload(
            schema_version=schema_version,
            event_contract_id=normalized_strings["event_contract_id"],
            event_contract_digest=normalized_strings["event_contract_digest"],
            replay_plan_id=normalized_strings["replay_plan_id"],
            replay_plan_digest=normalized_strings["replay_plan_digest"],
            specification_id=normalized_strings["specification_id"],
            specification_digest=normalized_strings["specification_digest"],
            input_package_id=normalized_strings["input_package_id"],
            input_digest=normalized_strings["input_digest"],
            snapshot_id=normalized_strings["snapshot_id"],
            snapshot_digest=normalized_strings["snapshot_digest"],
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            event_kind=self.event_kind,
            timestamp_source=self.timestamp_source,
            replay_clock=self.replay_clock,
            merge_mode=self.merge_mode,
            tie_break=self.tie_break,
            materialization_mode=(self.materialization_mode),
            sequence_assignment=(self.sequence_assignment),
            ordering_key=self.ordering_key,
            event_fields=self.event_fields,
            source_plans=self.source_plans,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            total_event_count=total_event_count,
            policy=self.policy,
        )

        if normalized_strings["materialization_digest"] != _sha256_digest(canonical_payload):
            raise ValueError(
                "materialization_digest does not match the canonical event-materialization plan."
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
            "sequence_start",
            sequence_start,
        )
        object.__setattr__(
            self,
            "sequence_end",
            sequence_end,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.event_contract_decision.event_contract_required

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.event_contract.plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.event_contract.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.event_contract.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.event_contract.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.event_contract.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.event_contract.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.event_contract.dry_run_package

    @property
    def timeframes(self) -> tuple[Phase8Timeframe, ...]:
        return tuple(source_plan.timeframe for source_plan in self.source_plans)

    @property
    def source_plan_count(self) -> int:
        return len(self.source_plans)

    @property
    def event_field_count(self) -> int:
        return len(self.event_fields)

    @property
    def planned_event_count(self) -> int:
        return self.total_event_count

    @property
    def first_event_time(self) -> datetime:
        return min(source_plan.first_event_time for source_plan in self.source_plans)

    @property
    def last_event_time(self) -> datetime:
        return max(source_plan.last_event_time for source_plan in self.source_plans)

    @property
    def canonical_payload(self) -> str:
        return _canonical_materialization_payload(
            schema_version=self.schema_version,
            event_contract_id=self.event_contract_id,
            event_contract_digest=(self.event_contract_digest),
            replay_plan_id=self.replay_plan_id,
            replay_plan_digest=self.replay_plan_digest,
            specification_id=self.specification_id,
            specification_digest=(self.specification_digest),
            input_package_id=self.input_package_id,
            input_digest=self.input_digest,
            snapshot_id=self.snapshot_id,
            snapshot_digest=self.snapshot_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            event_kind=self.event_kind,
            timestamp_source=self.timestamp_source,
            replay_clock=self.replay_clock,
            merge_mode=self.merge_mode,
            tie_break=self.tie_break,
            materialization_mode=self.materialization_mode,
            sequence_assignment=self.sequence_assignment,
            ordering_key=self.ordering_key,
            event_fields=self.event_fields,
            source_plans=self.source_plans,
            sequence_start=self.sequence_start,
            sequence_end=self.sequence_end,
            total_event_count=self.total_event_count,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def snapshot_sources_only(self) -> bool:
        return self.policy.snapshot_sources_only

    @property
    def zero_based_sequence(self) -> bool:
        return self.sequence_start == 0

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def creates_events(self) -> bool:
        return False

    @property
    def materializes_events(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
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
    def can_continue_to_event_materialization(
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
    def materialization_plan_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_PLAN:"
            "MATERIALIZATION_SHA256["
            f"{self.materialization_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.event_contract_decision.stable_id}:{self.materialization_plan_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayEventMaterializationPlanDecision:
    """Immutable event-materialization plan decision."""

    event_contract_decision: Phase8OfflineReplayEventContractDecision = field(repr=False)
    status: Phase8OfflineReplayEventMaterializationPlanStatus
    reason: Phase8OfflineReplayEventMaterializationPlanReason
    blockers: tuple[
        Phase8OfflineReplayEventMaterializationPlanBlocker,
        ...,
    ]
    plan: StrategyPhase8OfflineReplayEventMaterializationPlan | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.event_contract_decision,
            Phase8OfflineReplayEventContractDecision,
        ):
            raise ValueError(
                "event_contract_decision must be a Phase8OfflineReplayEventContractDecision."
            )

        try:
            status = Phase8OfflineReplayEventMaterializationPlanStatus(self.status)
            reason = Phase8OfflineReplayEventMaterializationPlanReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported event-materialization plan status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayEventMaterializationPlanBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Event-materialization blockers cannot contain duplicates.")

        if self.event_contract_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayEventMaterializationPlanStatus.BLOCKED)
                or reason
                != (Phase8OfflineReplayEventMaterializationPlanReason.EVENT_CONTRACT_BLOCKED)
                or blockers
                != (Phase8OfflineReplayEventMaterializationPlanBlocker.EVENT_CONTRACT_BLOCKED,)
                or self.plan is not None
            ):
                raise ValueError(
                    "Blocked event-materialization result does not match its event contract."
                )
        else:
            if (
                status != (Phase8OfflineReplayEventMaterializationPlanStatus.CREATED)
                or reason != (Phase8OfflineReplayEventMaterializationPlanReason.CREATED)
                or blockers
                or not isinstance(
                    self.plan,
                    StrategyPhase8OfflineReplayEventMaterializationPlan,
                )
                or self.plan.event_contract_decision is not self.event_contract_decision
            ):
                raise ValueError(
                    "Created event-materialization result does not match its event contract."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.event_contract_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.event_contract_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplayEventMaterializationPlanStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_plan(self) -> bool:
        return self.plan is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def plan_required(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        if self.plan is None:
            raise ValueError("No Phase 8 offline replay event materialization plan was created.")

        return self.plan

    @property
    def can_continue_to_event_materialization(
        self,
    ) -> bool:
        return self.is_created

    @property
    def creates_events(self) -> bool:
        return False

    @property
    def materializes_events(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
        return False

    @property
    def executes_simulation(self) -> bool:
        return False

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
            f"{self.event_contract_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_EVENT_"
            "MATERIALIZATION_PLAN_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayEventMaterializationPlanFactory:
    """Pure immutable materialization-plan factory."""

    def generate(
        self,
        event_contract_decision: (Phase8OfflineReplayEventContractDecision),
        policy: (Phase8OfflineReplayEventMaterializationPolicy | None) = None,
    ) -> Phase8OfflineReplayEventMaterializationPlanDecision:
        if not isinstance(
            event_contract_decision,
            Phase8OfflineReplayEventContractDecision,
        ):
            raise (
                Phase8OfflineReplayEventMaterializationPlanError(
                    Phase8OfflineReplayEventMaterializationPlanErrorReason.INVALID_EVENT_CONTRACT_DECISION,
                    "event_contract_decision must be a Phase8OfflineReplayEventContractDecision.",
                )
            )

        selected_policy = policy or Phase8OfflineReplayEventMaterializationPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayEventMaterializationPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayEventMaterializationPolicy.")

        if event_contract_decision.is_blocked:
            return Phase8OfflineReplayEventMaterializationPlanDecision(
                event_contract_decision=(event_contract_decision),
                status=(Phase8OfflineReplayEventMaterializationPlanStatus.BLOCKED),
                reason=(Phase8OfflineReplayEventMaterializationPlanReason.EVENT_CONTRACT_BLOCKED),
                blockers=(
                    Phase8OfflineReplayEventMaterializationPlanBlocker.EVENT_CONTRACT_BLOCKED,
                ),
                plan=None,
            )

        event_contract = event_contract_decision.event_contract_required
        replay_plan = event_contract.plan
        specification = event_contract.specification
        input_package = event_contract.input_package
        snapshot = event_contract.snapshot

        source_plans = tuple(
            Phase8OfflineReplayEventSourcePlan(
                timeframe=series_plan.timeframe,
                timeframe_priority=series_plan.priority,
                series_index=series_index,
                candle_count=series_plan.candle_count,
                start_candle_index=series_plan.start_index,
                end_candle_index=series_plan.end_index,
                first_event_time=(series_plan.first_close_time),
                last_event_time=(series_plan.latest_close_time),
                series_digest=series_plan.series_digest,
            )
            for series_index, series_plan in enumerate(replay_plan.series_plans)
        )

        total_event_count = sum(source_plan.planned_event_count for source_plan in source_plans)
        sequence_start = 0
        sequence_end = total_event_count - 1

        canonical_payload = _canonical_materialization_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_PLAN_SCHEMA_VERSION),
            event_contract_id=event_contract.stable_id,
            event_contract_digest=(event_contract.contract_digest),
            replay_plan_id=replay_plan.stable_id,
            replay_plan_digest=replay_plan.plan_digest,
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=event_contract.broker_symbol,
            direction=event_contract.direction,
            side=event_contract.side,
            source_name=event_contract.source_name,
            captured_at=event_contract.captured_at,
            event_kind=event_contract.event_kind,
            timestamp_source=(event_contract.timestamp_source),
            replay_clock=event_contract.replay_clock,
            merge_mode=event_contract.merge_mode,
            tie_break=event_contract.tie_break,
            materialization_mode=(
                Phase8OfflineReplayEventMaterializationMode.IMMUTABLE_EVENT_BUILD
            ),
            sequence_assignment=(Phase8OfflineReplaySequenceAssignment.AFTER_STABLE_MERGE),
            ordering_key=(
                Phase8OfflineReplayOrderingKey.EVENT_TIME_TIMEFRAME_PRIORITY_SERIES_CANDLE
            ),
            event_fields=event_contract.event_fields,
            source_plans=source_plans,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            total_event_count=total_event_count,
            policy=selected_policy,
        )

        plan = StrategyPhase8OfflineReplayEventMaterializationPlan(
            event_contract_decision=(event_contract_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_PLAN_SCHEMA_VERSION),
            event_contract_id=event_contract.stable_id,
            event_contract_digest=(event_contract.contract_digest),
            replay_plan_id=replay_plan.stable_id,
            replay_plan_digest=replay_plan.plan_digest,
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=event_contract.broker_symbol,
            direction=event_contract.direction,
            side=event_contract.side,
            source_name=event_contract.source_name,
            captured_at=event_contract.captured_at,
            event_kind=event_contract.event_kind,
            timestamp_source=(event_contract.timestamp_source),
            replay_clock=event_contract.replay_clock,
            merge_mode=event_contract.merge_mode,
            tie_break=event_contract.tie_break,
            materialization_mode=(
                Phase8OfflineReplayEventMaterializationMode.IMMUTABLE_EVENT_BUILD
            ),
            sequence_assignment=(Phase8OfflineReplaySequenceAssignment.AFTER_STABLE_MERGE),
            ordering_key=(
                Phase8OfflineReplayOrderingKey.EVENT_TIME_TIMEFRAME_PRIORITY_SERIES_CANDLE
            ),
            event_fields=event_contract.event_fields,
            source_plans=source_plans,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            total_event_count=total_event_count,
            materialization_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayEventMaterializationPlanDecision(
            event_contract_decision=(event_contract_decision),
            status=(Phase8OfflineReplayEventMaterializationPlanStatus.CREATED),
            reason=(Phase8OfflineReplayEventMaterializationPlanReason.CREATED),
            blockers=(),
            plan=plan,
        )

    def build(
        self,
        event_contract_decision: (Phase8OfflineReplayEventContractDecision),
        policy: (Phase8OfflineReplayEventMaterializationPolicy | None) = None,
    ) -> Phase8OfflineReplayEventMaterializationPlanDecision:
        return self.generate(
            event_contract_decision,
            policy,
        )

    def evaluate(
        self,
        event_contract_decision: (Phase8OfflineReplayEventContractDecision),
        policy: (Phase8OfflineReplayEventMaterializationPolicy | None) = None,
    ) -> Phase8OfflineReplayEventMaterializationPlanDecision:
        return self.generate(
            event_contract_decision,
            policy,
        )


def generate_phase8_offline_replay_event_materialization_plan(
    event_contract_decision: (Phase8OfflineReplayEventContractDecision),
    policy: (Phase8OfflineReplayEventMaterializationPolicy | None) = None,
) -> Phase8OfflineReplayEventMaterializationPlanDecision:
    return StrategyPhase8OfflineReplayEventMaterializationPlanFactory().generate(
        event_contract_decision,
        policy,
    )


Phase8OfflineReplayEventMaterializationPlan = StrategyPhase8OfflineReplayEventMaterializationPlan
Phase8OfflineReplayEventMaterializationPlanFactory = (
    StrategyPhase8OfflineReplayEventMaterializationPlanFactory
)
