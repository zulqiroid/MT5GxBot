from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from math import isfinite

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
    Phase8OfflineReplayEventField,
    Phase8OfflineReplayEventKind,
    Phase8OfflineReplayEventTimestampSource,
    StrategyPhase8OfflineReplayEventContract,
)
from app.strategy.phase8_offline_replay_event_materialization_plan import (
    Phase8OfflineReplayEventMaterializationMode,
    Phase8OfflineReplayEventMaterializationPlanDecision,
    Phase8OfflineReplayOrderingKey,
    Phase8OfflineReplaySequenceAssignment,
    StrategyPhase8OfflineReplayEventMaterializationPlan,
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

PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_SCHEMA_VERSION = "1.0"


class Phase8OfflineReplayEventMaterializationStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayEventMaterializationReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    MATERIALIZATION_PLAN_BLOCKED = "MATERIALIZATION_PLAN_BLOCKED"


class Phase8OfflineReplayEventMaterializationBlocker(
    str,
    Enum,
):
    MATERIALIZATION_PLAN_BLOCKED = "MATERIALIZATION_PLAN_BLOCKED"


class Phase8OfflineReplayEventMaterializationErrorReason(
    str,
    Enum,
):
    INVALID_MATERIALIZATION_PLAN_DECISION = "INVALID_MATERIALIZATION_PLAN_DECISION"


class Phase8OfflineReplayEventMaterializationError(
    RuntimeError,
):
    """Structured pure event-materialization failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayEventMaterializationErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayEventMaterializationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 offline replay-event materialization "
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


def _finite_positive_number(
    value: object,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(f"{field_name} must be numeric.")

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")

    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return normalized


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


def _canonical_number(value: float) -> str:
    return format(value, ".17g")


def _is_gold_symbol(symbol: str) -> bool:
    return symbol.upper().startswith("XAUUSD")


def _source_price(
    candle: object,
    preferred_name: str,
    fallback_name: str,
) -> float:
    if hasattr(candle, preferred_name):
        value = getattr(candle, preferred_name)
    elif hasattr(candle, fallback_name):
        value = getattr(candle, fallback_name)
    else:
        raise ValueError(f"Source candle is missing price field {preferred_name}.")

    return _finite_positive_number(
        value,
        preferred_name,
    )


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


def _canonical_event_payload(
    *,
    sequence_index: int,
    timeframe: Phase8Timeframe,
    timeframe_priority: int,
    series_index: int,
    candle_index: int,
    event_time: datetime,
    open_time: datetime,
    close_time: datetime,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    candle_digest: str,
    series_digest: str,
) -> str:
    return "\n".join(
        (
            f"SEQUENCE_INDEX={sequence_index}",
            f"TIMEFRAME={timeframe.value}",
            f"TIMEFRAME_PRIORITY={timeframe_priority}",
            f"SERIES_INDEX={series_index}",
            f"CANDLE_INDEX={candle_index}",
            (f"EVENT_TIME={_canonical_datetime(event_time)}"),
            (f"OPEN_TIME={_canonical_datetime(open_time)}"),
            (f"CLOSE_TIME={_canonical_datetime(close_time)}"),
            f"OPEN_PRICE={_canonical_number(open_price)}",
            f"HIGH_PRICE={_canonical_number(high_price)}",
            f"LOW_PRICE={_canonical_number(low_price)}",
            f"CLOSE_PRICE={_canonical_number(close_price)}",
            f"CANDLE_DIGEST={candle_digest}",
            f"SERIES_DIGEST={series_digest}",
        )
    )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayEvent:
    """Immutable replay event produced from one closed candle."""

    sequence_index: int
    timeframe: Phase8Timeframe
    timeframe_priority: int
    series_index: int
    candle_index: int
    event_time: datetime
    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    candle_digest: str
    series_digest: str
    event_digest: str

    def __post_init__(self) -> None:
        sequence_index = _non_negative_integer(
            self.sequence_index,
            "sequence_index",
        )

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
        candle_index = _non_negative_integer(
            self.candle_index,
            "candle_index",
        )

        event_time = _aware_datetime(
            self.event_time,
            "event_time",
        )
        open_time = _aware_datetime(
            self.open_time,
            "open_time",
        )
        close_time = _aware_datetime(
            self.close_time,
            "close_time",
        )

        if close_time <= open_time:
            raise ValueError("close_time must be later than open_time.")

        if event_time != close_time:
            raise ValueError("event_time must equal candle close_time.")

        open_price = _finite_positive_number(
            self.open_price,
            "open_price",
        )
        high_price = _finite_positive_number(
            self.high_price,
            "high_price",
        )
        low_price = _finite_positive_number(
            self.low_price,
            "low_price",
        )
        close_price = _finite_positive_number(
            self.close_price,
            "close_price",
        )

        if high_price < max(
            open_price,
            low_price,
            close_price,
        ):
            raise ValueError("high_price is inconsistent with OHLC.")

        if low_price > min(
            open_price,
            high_price,
            close_price,
        ):
            raise ValueError("low_price is inconsistent with OHLC.")

        candle_digest = _non_empty_string(
            self.candle_digest,
            "candle_digest",
        )
        series_digest = _non_empty_string(
            self.series_digest,
            "series_digest",
        )
        event_digest = _non_empty_string(
            self.event_digest,
            "event_digest",
        )

        for field_name, digest in (
            ("candle_digest", candle_digest),
            ("series_digest", series_digest),
            ("event_digest", event_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        canonical_payload = _canonical_event_payload(
            sequence_index=sequence_index,
            timeframe=self.timeframe,
            timeframe_priority=timeframe_priority,
            series_index=series_index,
            candle_index=candle_index,
            event_time=event_time,
            open_time=open_time,
            close_time=close_time,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            candle_digest=candle_digest,
            series_digest=series_digest,
        )

        if event_digest != _sha256_digest(canonical_payload):
            raise ValueError("event_digest does not match the canonical replay event.")

        object.__setattr__(
            self,
            "sequence_index",
            sequence_index,
        )
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
            "candle_index",
            candle_index,
        )
        object.__setattr__(
            self,
            "event_time",
            event_time,
        )
        object.__setattr__(
            self,
            "open_time",
            open_time,
        )
        object.__setattr__(
            self,
            "close_time",
            close_time,
        )
        object.__setattr__(
            self,
            "open_price",
            open_price,
        )
        object.__setattr__(
            self,
            "high_price",
            high_price,
        )
        object.__setattr__(
            self,
            "low_price",
            low_price,
        )
        object.__setattr__(
            self,
            "close_price",
            close_price,
        )
        object.__setattr__(
            self,
            "candle_digest",
            candle_digest,
        )
        object.__setattr__(
            self,
            "series_digest",
            series_digest,
        )
        object.__setattr__(
            self,
            "event_digest",
            event_digest,
        )

    @property
    def canonical_payload(self) -> str:
        return _canonical_event_payload(
            sequence_index=self.sequence_index,
            timeframe=self.timeframe,
            timeframe_priority=(self.timeframe_priority),
            series_index=self.series_index,
            candle_index=self.candle_index,
            event_time=self.event_time,
            open_time=self.open_time,
            close_time=self.close_time,
            open_price=self.open_price,
            high_price=self.high_price,
            low_price=self.low_price,
            close_price=self.close_price,
            candle_digest=self.candle_digest,
            series_digest=self.series_digest,
        )

    @property
    def ordering_key(
        self,
    ) -> tuple[datetime, int, int, int]:
        return (
            self.event_time,
            self.timeframe_priority,
            self.series_index,
            self.candle_index,
        )

    @property
    def event_id(self) -> str:
        return (
            f"{self.sequence_index}:"
            f"{self.timeframe.value}:"
            f"{self.candle_index}:"
            f"EVENT_SHA256[{self.event_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return self.event_id


def _canonical_batch_payload(
    *,
    schema_version: str,
    materialization_plan_id: str,
    materialization_plan_digest: str,
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
    events: tuple[Phase8OfflineReplayEvent, ...],
    total_event_count: int,
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
        (f"MATERIALIZATION_PLAN_ID={materialization_plan_id}"),
        (f"MATERIALIZATION_PLAN_DIGEST={materialization_plan_digest}"),
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
        f"SEQUENCE_START={events[0].sequence_index}",
        f"SEQUENCE_END={events[-1].sequence_index}",
        f"TOTAL_EVENT_COUNT={total_event_count}",
    ]

    for index, event_field in enumerate(
        event_fields,
        start=1,
    ):
        lines.append(f"EVENT_FIELD_{index}={event_field.value}")

    for index, event in enumerate(events, start=1):
        lines.extend(
            (
                (f"EVENT_{index}_ID={event.stable_id}"),
                (f"EVENT_{index}_DIGEST={event.event_digest}"),
            )
        )

    lines.extend(
        (
            "IN_MEMORY_ONLY=true",
            "EVENTS_CREATED=true",
            "EVENTS_MATERIALIZED=true",
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

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class StrategyPhase8OfflineReplayEventBatch:
    """
    Immutable in-memory candle-close replay events.

    The events are materialized from the verified snapshot,
    but replay and strategy evaluation are not executed.
    No storage, network, MT5, broker, or order operation is
    performed.
    """

    materialization_plan_decision: Phase8OfflineReplayEventMaterializationPlanDecision = field(
        repr=False
    )
    schema_version: str
    materialization_plan_id: str
    materialization_plan_digest: str
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
    events: tuple[
        Phase8OfflineReplayEvent,
        ...,
    ] = field(repr=False)
    total_event_count: int
    batch_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.materialization_plan_decision,
            Phase8OfflineReplayEventMaterializationPlanDecision,
        ):
            raise ValueError(
                "materialization_plan_decision must be a "
                "Phase8OfflineReplayEventMaterializationPlanDecision."
            )

        if not self.materialization_plan_decision.is_created:
            raise ValueError("An event batch requires a created event-materialization plan.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current event-materialization schema.")

        string_fields = (
            (
                "materialization_plan_id",
                self.materialization_plan_id,
            ),
            (
                "materialization_plan_digest",
                self.materialization_plan_digest,
            ),
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
            ("batch_digest", self.batch_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "materialization_plan_digest",
            "event_contract_digest",
            "replay_plan_digest",
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "batch_digest",
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

        if not isinstance(self.events, tuple):
            raise ValueError("events must be a tuple.")

        if not self.events:
            raise ValueError("events cannot be empty.")

        if not all(isinstance(event, Phase8OfflineReplayEvent) for event in self.events):
            raise ValueError("events must contain Phase8OfflineReplayEvent members.")

        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )

        if len(self.events) != total_event_count:
            raise ValueError("events length must match total_event_count.")

        materialization_plan = self.materialization_plan_decision.plan_required
        event_contract = materialization_plan.event_contract
        replay_plan = materialization_plan.replay_plan
        specification = materialization_plan.specification
        input_package = materialization_plan.input_package
        snapshot = materialization_plan.snapshot

        comparisons = (
            (
                "materialization_plan_id",
                normalized_strings["materialization_plan_id"],
                materialization_plan.stable_id,
            ),
            (
                "materialization_plan_digest",
                normalized_strings["materialization_plan_digest"],
                materialization_plan.materialization_digest,
            ),
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
                materialization_plan.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                materialization_plan.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable event-materialization lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Replay-event batches support Gold/XAUUSD only.")

        if self.direction != materialization_plan.direction:
            raise ValueError("direction must match the materialization plan.")

        if self.side != materialization_plan.side:
            raise ValueError("side must match the materialization plan.")

        if captured_at != materialization_plan.captured_at:
            raise ValueError("captured_at must match the materialization plan.")

        control_fields = (
            "event_kind",
            "timestamp_source",
            "replay_clock",
            "merge_mode",
            "tie_break",
            "materialization_mode",
            "sequence_assignment",
            "ordering_key",
            "event_fields",
        )

        for field_name in control_fields:
            if getattr(self, field_name) != getattr(
                materialization_plan,
                field_name,
            ):
                raise ValueError(f"{field_name} must match the materialization plan.")

        if total_event_count != materialization_plan.total_event_count:
            raise ValueError("total_event_count must match the materialization plan.")

        expected_rows: list[
            tuple[
                datetime,
                int,
                int,
                int,
                object,
                object,
            ]
        ] = []

        for source_plan in materialization_plan.source_plans:
            source_series = snapshot.series[source_plan.series_index]

            for candle_index in range(
                source_plan.start_candle_index,
                source_plan.end_candle_index + 1,
            ):
                candle = source_series.candles[candle_index]

                expected_rows.append(
                    (
                        candle.close_time,
                        source_plan.timeframe_priority,
                        source_plan.series_index,
                        candle_index,
                        candle,
                        source_plan,
                    )
                )

        expected_rows.sort(
            key=lambda row: (
                row[0],
                row[1],
                row[2],
                row[3],
            )
        )

        if len(expected_rows) != total_event_count:
            raise ValueError("Source snapshot event count does not match total_event_count.")

        for sequence_index, (
            event,
            expected_row,
        ) in enumerate(
            zip(
                self.events,
                expected_rows,
                strict=True,
            )
        ):
            (
                expected_event_time,
                expected_priority,
                expected_series_index,
                expected_candle_index,
                source_candle,
                source_plan,
            ) = expected_row

            expected_values = (
                sequence_index,
                source_plan.timeframe,
                expected_priority,
                expected_series_index,
                expected_candle_index,
                expected_event_time,
                source_candle.open_time,
                source_candle.close_time,
                _source_price(
                    source_candle,
                    "open_price",
                    "open",
                ),
                _source_price(
                    source_candle,
                    "high_price",
                    "high",
                ),
                _source_price(
                    source_candle,
                    "low_price",
                    "low",
                ),
                _source_price(
                    source_candle,
                    "close_price",
                    "close",
                ),
                source_candle.candle_digest,
                source_plan.series_digest,
            )

            supplied_values = (
                event.sequence_index,
                event.timeframe,
                event.timeframe_priority,
                event.series_index,
                event.candle_index,
                event.event_time,
                event.open_time,
                event.close_time,
                event.open_price,
                event.high_price,
                event.low_price,
                event.close_price,
                event.candle_digest,
                event.series_digest,
            )

            if supplied_values != expected_values:
                raise ValueError(
                    "Replay event does not match its immutable snapshot candle lineage."
                )

            if event.event_time > captured_at:
                raise ValueError("Replay event cannot represent an open candle.")

        sequence_indices = tuple(event.sequence_index for event in self.events)

        if sequence_indices != tuple(range(total_event_count)):
            raise ValueError("events must preserve an exact zero-based global sequence.")

        ordering_keys = tuple(event.ordering_key for event in self.events)

        if ordering_keys != tuple(sorted(ordering_keys)):
            raise ValueError("events must preserve chronological stable ordering.")

        if len({event.event_digest for event in self.events}) != total_event_count:
            raise ValueError("Every replay event must have a unique event digest.")

        safe_subjects = (
            self.materialization_plan_decision,
            materialization_plan,
            materialization_plan.event_contract_decision,
            event_contract,
            event_contract.plan_decision,
            replay_plan,
            replay_plan.specification_decision,
            specification,
            specification.input_decision,
            input_package,
            materialization_plan.verification_receipt,
            snapshot,
            materialization_plan.contract,
            materialization_plan.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError("Replay-event lineage violates the non-I/O or non-execution boundary.")

        canonical_payload = _canonical_batch_payload(
            schema_version=schema_version,
            materialization_plan_id=(normalized_strings["materialization_plan_id"]),
            materialization_plan_digest=(normalized_strings["materialization_plan_digest"]),
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
            materialization_mode=self.materialization_mode,
            sequence_assignment=self.sequence_assignment,
            ordering_key=self.ordering_key,
            event_fields=self.event_fields,
            events=self.events,
            total_event_count=total_event_count,
        )

        if normalized_strings["batch_digest"] != _sha256_digest(canonical_payload):
            raise ValueError("batch_digest does not match the canonical replay-event batch.")

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
            "total_event_count",
            total_event_count,
        )

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.materialization_plan_decision.plan_required

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.materialization_plan.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.materialization_plan.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.materialization_plan.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.materialization_plan.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.materialization_plan.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.materialization_plan.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.materialization_plan.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.materialization_plan.dry_run_package

    @property
    def sequence_start(self) -> int:
        return self.events[0].sequence_index

    @property
    def sequence_end(self) -> int:
        return self.events[-1].sequence_index

    @property
    def first_event_time(self) -> datetime:
        return self.events[0].event_time

    @property
    def last_event_time(self) -> datetime:
        return self.events[-1].event_time

    @property
    def timeframes(self) -> tuple[Phase8Timeframe, ...]:
        return tuple(
            source_plan.timeframe for source_plan in self.materialization_plan.source_plans
        )

    @property
    def canonical_payload(self) -> str:
        return _canonical_batch_payload(
            schema_version=self.schema_version,
            materialization_plan_id=(self.materialization_plan_id),
            materialization_plan_digest=(self.materialization_plan_digest),
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
            events=self.events,
            total_event_count=self.total_event_count,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def in_memory_only(self) -> bool:
        return True

    @property
    def creates_events(self) -> bool:
        return True

    @property
    def materializes_events(self) -> bool:
        return True

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
    def can_continue_to_offline_replay_session_plan(
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
    def batch_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_EVENT_BATCH:"
            f"BATCH_SHA256[{self.batch_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.materialization_plan_decision.stable_id}:{self.batch_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayEventMaterializationDecision:
    """Immutable pure event-materialization decision."""

    materialization_plan_decision: Phase8OfflineReplayEventMaterializationPlanDecision = field(
        repr=False
    )
    status: Phase8OfflineReplayEventMaterializationStatus
    reason: Phase8OfflineReplayEventMaterializationReason
    blockers: tuple[
        Phase8OfflineReplayEventMaterializationBlocker,
        ...,
    ]
    batch: StrategyPhase8OfflineReplayEventBatch | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.materialization_plan_decision,
            Phase8OfflineReplayEventMaterializationPlanDecision,
        ):
            raise ValueError(
                "materialization_plan_decision must be a "
                "Phase8OfflineReplayEventMaterializationPlanDecision."
            )

        try:
            status = Phase8OfflineReplayEventMaterializationStatus(self.status)
            reason = Phase8OfflineReplayEventMaterializationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported replay-event materialization status or reason."
            ) from error

        blockers = tuple(
            Phase8OfflineReplayEventMaterializationBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Replay-event materialization blockers cannot contain duplicates.")

        if self.materialization_plan_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayEventMaterializationStatus.BLOCKED)
                or reason
                != (Phase8OfflineReplayEventMaterializationReason.MATERIALIZATION_PLAN_BLOCKED)
                or blockers
                != (Phase8OfflineReplayEventMaterializationBlocker.MATERIALIZATION_PLAN_BLOCKED,)
                or self.batch is not None
            ):
                raise ValueError(
                    "Blocked event-materialization result does not match its plan decision."
                )
        else:
            if (
                status != (Phase8OfflineReplayEventMaterializationStatus.CREATED)
                or reason != (Phase8OfflineReplayEventMaterializationReason.CREATED)
                or blockers
                or not isinstance(
                    self.batch,
                    StrategyPhase8OfflineReplayEventBatch,
                )
                or self.batch.materialization_plan_decision
                is not self.materialization_plan_decision
            ):
                raise ValueError(
                    "Created event-materialization result does not match its plan decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.materialization_plan_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.materialization_plan_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplayEventMaterializationStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_batch(self) -> bool:
        return self.batch is not None

    @property
    def batch_required(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        if self.batch is None:
            raise ValueError("No Phase 8 offline replay-event batch was created.")

        return self.batch

    @property
    def creates_events(self) -> bool:
        return self.is_created

    @property
    def materializes_events(self) -> bool:
        return self.is_created

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
    def can_continue_to_offline_replay_session_plan(
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
            f"{self.materialization_plan_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_EVENT_"
            "MATERIALIZATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


def _build_event(
    *,
    sequence_index: int,
    timeframe: Phase8Timeframe,
    timeframe_priority: int,
    series_index: int,
    candle_index: int,
    source_candle: object,
    series_digest: str,
) -> Phase8OfflineReplayEvent:
    open_price = _source_price(
        source_candle,
        "open_price",
        "open",
    )
    high_price = _source_price(
        source_candle,
        "high_price",
        "high",
    )
    low_price = _source_price(
        source_candle,
        "low_price",
        "low",
    )
    close_price = _source_price(
        source_candle,
        "close_price",
        "close",
    )

    canonical_payload = _canonical_event_payload(
        sequence_index=sequence_index,
        timeframe=timeframe,
        timeframe_priority=timeframe_priority,
        series_index=series_index,
        candle_index=candle_index,
        event_time=source_candle.close_time,
        open_time=source_candle.open_time,
        close_time=source_candle.close_time,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        candle_digest=source_candle.candle_digest,
        series_digest=series_digest,
    )

    return Phase8OfflineReplayEvent(
        sequence_index=sequence_index,
        timeframe=timeframe,
        timeframe_priority=timeframe_priority,
        series_index=series_index,
        candle_index=candle_index,
        event_time=source_candle.close_time,
        open_time=source_candle.open_time,
        close_time=source_candle.close_time,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        candle_digest=source_candle.candle_digest,
        series_digest=series_digest,
        event_digest=_sha256_digest(canonical_payload),
    )


class StrategyPhase8OfflineReplayEventMaterializationFactory:
    """Pure in-memory immutable event factory."""

    def generate(
        self,
        materialization_plan_decision: (Phase8OfflineReplayEventMaterializationPlanDecision),
    ) -> Phase8OfflineReplayEventMaterializationDecision:
        if not isinstance(
            materialization_plan_decision,
            Phase8OfflineReplayEventMaterializationPlanDecision,
        ):
            raise (
                Phase8OfflineReplayEventMaterializationError(
                    Phase8OfflineReplayEventMaterializationErrorReason.INVALID_MATERIALIZATION_PLAN_DECISION,
                    "materialization_plan_decision must be a "
                    "Phase8OfflineReplayEventMaterializationPlanDecision.",
                )
            )

        if materialization_plan_decision.is_blocked:
            return Phase8OfflineReplayEventMaterializationDecision(
                materialization_plan_decision=(materialization_plan_decision),
                status=(Phase8OfflineReplayEventMaterializationStatus.BLOCKED),
                reason=(Phase8OfflineReplayEventMaterializationReason.MATERIALIZATION_PLAN_BLOCKED),
                blockers=(
                    Phase8OfflineReplayEventMaterializationBlocker.MATERIALIZATION_PLAN_BLOCKED,
                ),
                batch=None,
            )

        materialization_plan = materialization_plan_decision.plan_required
        event_contract = materialization_plan.event_contract
        replay_plan = materialization_plan.replay_plan
        specification = materialization_plan.specification
        input_package = materialization_plan.input_package
        snapshot = materialization_plan.snapshot

        source_rows: list[
            tuple[
                datetime,
                int,
                int,
                int,
                object,
                str,
                Phase8Timeframe,
            ]
        ] = []

        for source_plan in materialization_plan.source_plans:
            source_series = snapshot.series[source_plan.series_index]

            for candle_index in range(
                source_plan.start_candle_index,
                source_plan.end_candle_index + 1,
            ):
                source_candle = source_series.candles[candle_index]

                source_rows.append(
                    (
                        source_candle.close_time,
                        source_plan.timeframe_priority,
                        source_plan.series_index,
                        candle_index,
                        source_candle,
                        source_plan.series_digest,
                        source_plan.timeframe,
                    )
                )

        source_rows.sort(
            key=lambda row: (
                row[0],
                row[1],
                row[2],
                row[3],
            )
        )

        events = tuple(
            _build_event(
                sequence_index=sequence_index,
                timeframe=timeframe,
                timeframe_priority=timeframe_priority,
                series_index=series_index,
                candle_index=candle_index,
                source_candle=source_candle,
                series_digest=series_digest,
            )
            for sequence_index, (
                _,
                timeframe_priority,
                series_index,
                candle_index,
                source_candle,
                series_digest,
                timeframe,
            ) in enumerate(source_rows)
        )

        canonical_payload = _canonical_batch_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_SCHEMA_VERSION),
            materialization_plan_id=(materialization_plan.stable_id),
            materialization_plan_digest=(materialization_plan.materialization_digest),
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
            broker_symbol=materialization_plan.broker_symbol,
            direction=materialization_plan.direction,
            side=materialization_plan.side,
            source_name=materialization_plan.source_name,
            captured_at=materialization_plan.captured_at,
            event_kind=materialization_plan.event_kind,
            timestamp_source=(materialization_plan.timestamp_source),
            replay_clock=materialization_plan.replay_clock,
            merge_mode=materialization_plan.merge_mode,
            tie_break=materialization_plan.tie_break,
            materialization_mode=(materialization_plan.materialization_mode),
            sequence_assignment=(materialization_plan.sequence_assignment),
            ordering_key=materialization_plan.ordering_key,
            event_fields=materialization_plan.event_fields,
            events=events,
            total_event_count=len(events),
        )

        batch = StrategyPhase8OfflineReplayEventBatch(
            materialization_plan_decision=(materialization_plan_decision),
            schema_version=(PHASE_8_OFFLINE_REPLAY_EVENT_MATERIALIZATION_SCHEMA_VERSION),
            materialization_plan_id=(materialization_plan.stable_id),
            materialization_plan_digest=(materialization_plan.materialization_digest),
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
            broker_symbol=materialization_plan.broker_symbol,
            direction=materialization_plan.direction,
            side=materialization_plan.side,
            source_name=materialization_plan.source_name,
            captured_at=materialization_plan.captured_at,
            event_kind=materialization_plan.event_kind,
            timestamp_source=(materialization_plan.timestamp_source),
            replay_clock=materialization_plan.replay_clock,
            merge_mode=materialization_plan.merge_mode,
            tie_break=materialization_plan.tie_break,
            materialization_mode=(materialization_plan.materialization_mode),
            sequence_assignment=(materialization_plan.sequence_assignment),
            ordering_key=materialization_plan.ordering_key,
            event_fields=materialization_plan.event_fields,
            events=events,
            total_event_count=len(events),
            batch_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayEventMaterializationDecision(
            materialization_plan_decision=(materialization_plan_decision),
            status=(Phase8OfflineReplayEventMaterializationStatus.CREATED),
            reason=(Phase8OfflineReplayEventMaterializationReason.CREATED),
            blockers=(),
            batch=batch,
        )

    def build(
        self,
        materialization_plan_decision: (Phase8OfflineReplayEventMaterializationPlanDecision),
    ) -> Phase8OfflineReplayEventMaterializationDecision:
        return self.generate(materialization_plan_decision)

    def evaluate(
        self,
        materialization_plan_decision: (Phase8OfflineReplayEventMaterializationPlanDecision),
    ) -> Phase8OfflineReplayEventMaterializationDecision:
        return self.generate(materialization_plan_decision)


def generate_phase8_offline_replay_events(
    materialization_plan_decision: (Phase8OfflineReplayEventMaterializationPlanDecision),
) -> Phase8OfflineReplayEventMaterializationDecision:
    return StrategyPhase8OfflineReplayEventMaterializationFactory().generate(
        materialization_plan_decision
    )


Phase8OfflineReplayEventBatch = StrategyPhase8OfflineReplayEventBatch
Phase8OfflineReplayEventMaterializationFactory = (
    StrategyPhase8OfflineReplayEventMaterializationFactory
)
