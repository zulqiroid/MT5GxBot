from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    Phase8ClosedCandleDataContractDecision,
    StrategyPhase8ClosedCandleDataContract,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
)

PHASE_8_CLOSED_CANDLE_SNAPSHOT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


_TIMEFRAME_DURATIONS = {
    Phase8Timeframe.H4: timedelta(hours=4),
    Phase8Timeframe.H1: timedelta(hours=1),
    Phase8Timeframe.M15: timedelta(minutes=15),
    Phase8Timeframe.M5: timedelta(minutes=5),
}


class Phase8ClosedCandleSnapshotStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8ClosedCandleSnapshotReason(str, Enum):
    CREATED = "CREATED"
    DATA_CONTRACT_BLOCKED = "DATA_CONTRACT_BLOCKED"


class Phase8ClosedCandleSnapshotBlocker(str, Enum):
    DATA_CONTRACT_BLOCKED = "DATA_CONTRACT_BLOCKED"


class Phase8ClosedCandleSnapshotErrorReason(str, Enum):
    INVALID_DATA_CONTRACT_DECISION = "INVALID_DATA_CONTRACT_DECISION"


class Phase8ClosedCandleSnapshotError(RuntimeError):
    """Structured external candle-snapshot failure."""

    def __init__(
        self,
        reason: Phase8ClosedCandleSnapshotErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8ClosedCandleSnapshotErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 closed-candle snapshot error [{self.reason.value}]: {self.message}"
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


def _positive_finite_number(
    value: object,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(f"{field_name} must be a number.")

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


def _canonical_price(value: float) -> str:
    return format(value, ".17g")


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandle:
    """One immutable externally supplied closed candle."""

    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float

    def __post_init__(self) -> None:
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

        open_price = _positive_finite_number(
            self.open_price,
            "open_price",
        )
        high_price = _positive_finite_number(
            self.high_price,
            "high_price",
        )
        low_price = _positive_finite_number(
            self.low_price,
            "low_price",
        )
        close_price = _positive_finite_number(
            self.close_price,
            "close_price",
        )

        if high_price < max(open_price, close_price):
            raise ValueError(
                "high_price must be greater than or equal to open_price and close_price."
            )

        if low_price > min(open_price, close_price):
            raise ValueError("low_price must be less than or equal to open_price and close_price.")

        if high_price < low_price:
            raise ValueError("high_price cannot be lower than low_price.")

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

    @property
    def canonical_row(self) -> str:
        return "|".join(
            (
                _canonical_datetime(self.open_time),
                _canonical_datetime(self.close_time),
                _canonical_price(self.open_price),
                _canonical_price(self.high_price),
                _canonical_price(self.low_price),
                _canonical_price(self.close_price),
            )
        )

    @property
    def candle_digest(self) -> str:
        return _sha256_digest(self.canonical_row)

    @property
    def is_closed(self) -> bool:
        return self.close_time > self.open_time


def _canonical_series_payload(
    *,
    timeframe: Phase8Timeframe,
    candles: tuple[Phase8ClosedCandle, ...],
) -> str:
    lines = [
        (f"SCHEMA_VERSION={PHASE_8_CLOSED_CANDLE_SNAPSHOT_SCHEMA_VERSION}"),
        f"TIMEFRAME={timeframe.value}",
        f"CANDLE_COUNT={len(candles)}",
    ]

    lines.extend(
        (f"CANDLE_{index}={candle.canonical_row}")
        for index, candle in enumerate(
            candles,
            start=1,
        )
    )

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandleSeries:
    """Immutable ordered series for one timeframe."""

    timeframe: Phase8Timeframe
    candles: tuple[Phase8ClosedCandle, ...] = field(repr=False)
    series_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("timeframe must be a Phase8Timeframe member.")

        if not isinstance(self.candles, tuple):
            raise ValueError("candles must be a tuple.")

        if not self.candles:
            raise ValueError("candles cannot be empty.")

        if not all(isinstance(candle, Phase8ClosedCandle) for candle in self.candles):
            raise ValueError("candles must contain Phase8ClosedCandle members.")

        expected_duration = _TIMEFRAME_DURATIONS[self.timeframe]
        previous_open_time: datetime | None = None
        seen_open_times: set[datetime] = set()

        for candle in self.candles:
            if candle.close_time - candle.open_time != expected_duration:
                raise ValueError(f"Every candle duration must match {self.timeframe.value}.")

            if candle.open_time in seen_open_times:
                raise ValueError("Candle open times must be unique.")

            if previous_open_time is not None and candle.open_time <= previous_open_time:
                raise ValueError("Candle open times must be strictly increasing.")

            seen_open_times.add(candle.open_time)
            previous_open_time = candle.open_time

        series_digest = _non_empty_string(
            self.series_digest,
            "series_digest",
        )

        if not _is_lowercase_sha256(series_digest):
            raise ValueError("series_digest must be a lowercase SHA-256 hexadecimal value.")

        canonical_payload = _canonical_series_payload(
            timeframe=self.timeframe,
            candles=self.candles,
        )

        if series_digest != _sha256_digest(canonical_payload):
            raise ValueError("series_digest does not match the canonical candle-series payload.")

        object.__setattr__(
            self,
            "series_digest",
            series_digest,
        )

    @property
    def candle_count(self) -> int:
        return len(self.candles)

    @property
    def first_open_time(self) -> datetime:
        return self.candles[0].open_time

    @property
    def latest_open_time(self) -> datetime:
        return self.candles[-1].open_time

    @property
    def latest_close_time(self) -> datetime:
        return self.candles[-1].close_time

    @property
    def canonical_payload(self) -> str:
        return _canonical_series_payload(
            timeframe=self.timeframe,
            candles=self.candles,
        )

    @property
    def is_ordered(self) -> bool:
        return True

    @property
    def uses_closed_candles(self) -> bool:
        return all(candle.is_closed for candle in self.candles)


def build_phase8_closed_candle_series(
    timeframe: Phase8Timeframe,
    candles: tuple[Phase8ClosedCandle, ...],
) -> Phase8ClosedCandleSeries:
    if not isinstance(timeframe, Phase8Timeframe):
        raise ValueError("timeframe must be a Phase8Timeframe member.")

    if not isinstance(candles, tuple):
        raise ValueError("candles must be a tuple.")

    canonical_payload = _canonical_series_payload(
        timeframe=timeframe,
        candles=candles,
    )

    return Phase8ClosedCandleSeries(
        timeframe=timeframe,
        candles=candles,
        series_digest=_sha256_digest(canonical_payload),
    )


def _canonical_snapshot_payload(
    *,
    schema_version: str,
    contract_id: str,
    contract_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    series: tuple[Phase8ClosedCandleSeries, ...],
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
        f"CONTRACT_ID={contract_id}",
        f"CONTRACT_DIGEST={contract_digest}",
        f"BROKER_SYMBOL={broker_symbol}",
        f"DIRECTION={direction.value}",
        f"SIDE={side.value}",
        f"SOURCE_NAME={source_name}",
        (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
        f"SERIES_COUNT={len(series)}",
        (f"TOTAL_CANDLE_COUNT={sum(item.candle_count for item in series)}"),
    ]

    for index, item in enumerate(series, start=1):
        lines.extend(
            (
                (f"SERIES_{index}_TIMEFRAME={item.timeframe.value}"),
                (f"SERIES_{index}_CANDLE_COUNT={item.candle_count}"),
                (f"SERIES_{index}_DIGEST={item.series_digest}"),
            )
        )

    lines.extend(
        (
            "EXTERNAL_DATA_ONLY=true",
            "DATA_FETCH=false",
            "MT5_INITIALIZATION=false",
            "NETWORK_WRITE=false",
            "STORAGE_WRITE=false",
            "BROKER_WRITE=false",
            "ORDER_SUBMISSION=false",
        )
    )

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class StrategyPhase8ClosedCandleSnapshot:
    """
    Immutable validated external closed-candle snapshot.

    Nested source objects are excluded from repr so a failed
    assertion cannot recursively render the complete Phase 7
    and Phase 8 lineage.
    """

    contract_decision: Phase8ClosedCandleDataContractDecision = field(repr=False)
    source_name: str
    captured_at: datetime
    series: tuple[
        Phase8ClosedCandleSeries,
        ...,
    ] = field(repr=False)
    schema_version: str
    contract_id: str
    contract_digest: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.contract_decision,
            Phase8ClosedCandleDataContractDecision,
        ):
            raise ValueError("contract_decision must be a Phase8ClosedCandleDataContractDecision.")

        if not self.contract_decision.is_created:
            raise ValueError("A closed-candle snapshot requires a created data contract.")

        source_name = _non_empty_string(
            self.source_name,
            "source_name",
        )
        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_CLOSED_CANDLE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current closed-candle snapshot schema.")

        if not isinstance(self.series, tuple):
            raise ValueError("series must be a tuple.")

        if not all(
            isinstance(
                item,
                Phase8ClosedCandleSeries,
            )
            for item in self.series
        ):
            raise ValueError("series must contain Phase8ClosedCandleSeries members.")

        if len(self.series) != len(_REQUIRED_TIMEFRAMES):
            raise ValueError("series must contain exactly four timeframe series.")

        supplied_timeframes = tuple(item.timeframe for item in self.series)

        if supplied_timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("series must contain H4, H1, M15, and M5 in deterministic order.")

        if len(set(supplied_timeframes)) != len(supplied_timeframes):
            raise ValueError("series timeframes must be unique.")

        contract_id = _non_empty_string(
            self.contract_id,
            "contract_id",
        )
        contract_digest = _non_empty_string(
            self.contract_digest,
            "contract_digest",
        )
        snapshot_digest = _non_empty_string(
            self.snapshot_digest,
            "snapshot_digest",
        )

        for field_name, digest in (
            ("contract_digest", contract_digest),
            ("snapshot_digest", snapshot_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        contract = self.contract_decision.contract_required
        minimum_count = contract.policy.minimum_closed_candles_per_timeframe

        if contract_id != contract.stable_id:
            raise ValueError("contract_id must match the closed-candle data contract.")

        if contract_digest != contract.contract_digest:
            raise ValueError("contract_digest must match the closed-candle data contract.")

        if contract.timeframes != supplied_timeframes:
            raise ValueError("Snapshot timeframes must match the closed-candle data contract.")

        for item in self.series:
            if item.candle_count < minimum_count:
                raise ValueError(
                    f"{item.timeframe.value} requires at least {minimum_count} closed candles."
                )

            if item.latest_close_time > captured_at:
                raise ValueError(
                    f"{item.timeframe.value} latest candle must be closed by captured_at."
                )

            if not item.uses_closed_candles:
                raise ValueError(f"{item.timeframe.value} must contain closed candles only.")

        package = contract.package

        if package.broker_symbol != contract.broker_symbol:
            raise ValueError("Snapshot contract symbol lineage is inconsistent.")

        if package.initializes_mt5:
            raise ValueError("Snapshot source package cannot initialize MT5.")

        for attribute_name in (
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
        ):
            if getattr(contract, attribute_name):
                raise ValueError(
                    f"The data contract violates the non-executable boundary: {attribute_name}."
                )

        canonical_payload = _canonical_snapshot_payload(
            schema_version=schema_version,
            contract_id=contract_id,
            contract_digest=contract_digest,
            broker_symbol=contract.broker_symbol,
            direction=contract.direction,
            side=contract.side,
            source_name=source_name,
            captured_at=captured_at,
            series=self.series,
        )

        if snapshot_digest != _sha256_digest(canonical_payload):
            raise ValueError(
                "snapshot_digest does not match the canonical closed-candle snapshot payload."
            )

        object.__setattr__(
            self,
            "source_name",
            source_name,
        )
        object.__setattr__(
            self,
            "captured_at",
            captured_at,
        )
        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "contract_id",
            contract_id,
        )
        object.__setattr__(
            self,
            "contract_digest",
            contract_digest,
        )
        object.__setattr__(
            self,
            "snapshot_digest",
            snapshot_digest,
        )

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.contract_decision.contract_required

    @property
    def broker_symbol(self) -> str:
        return self.contract.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.contract.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.contract.side

    @property
    def timeframes(self) -> tuple[Phase8Timeframe, ...]:
        return tuple(item.timeframe for item in self.series)

    @property
    def series_count(self) -> int:
        return len(self.series)

    @property
    def total_candle_count(self) -> int:
        return sum(item.candle_count for item in self.series)

    @property
    def latest_close_time(self) -> datetime:
        return max(item.latest_close_time for item in self.series)

    @property
    def canonical_payload(self) -> str:
        return _canonical_snapshot_payload(
            schema_version=self.schema_version,
            contract_id=self.contract_id,
            contract_digest=self.contract_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            series=self.series,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_validated(self) -> bool:
        return True

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def external_data_only(self) -> bool:
        return True

    @property
    def fetches_data(self) -> bool:
        return False

    @property
    def initializes_mt5(self) -> bool:
        return False

    @property
    def can_continue_to_snapshot_verification(
        self,
    ) -> bool:
        return True

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
    def snapshot_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_CLOSED_CANDLE_SNAPSHOT:"
            f"SOURCE[{self.source_name}]:"
            f"SNAPSHOT_SHA256[{self.snapshot_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.contract_decision.stable_id}:{self.snapshot_id}"


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandleSnapshotDecision:
    """Validated external closed-candle snapshot result."""

    contract_decision: Phase8ClosedCandleDataContractDecision = field(repr=False)
    status: Phase8ClosedCandleSnapshotStatus
    reason: Phase8ClosedCandleSnapshotReason
    blockers: tuple[
        Phase8ClosedCandleSnapshotBlocker,
        ...,
    ]
    snapshot: StrategyPhase8ClosedCandleSnapshot | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.contract_decision,
            Phase8ClosedCandleDataContractDecision,
        ):
            raise ValueError("contract_decision must be a Phase8ClosedCandleDataContractDecision.")

        try:
            status = Phase8ClosedCandleSnapshotStatus(self.status)
            reason = Phase8ClosedCandleSnapshotReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported closed-candle snapshot status or reason.") from error

        blockers = tuple(Phase8ClosedCandleSnapshotBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Closed-candle snapshot blockers cannot contain duplicates.")

        if self.contract_decision.is_blocked:
            expected_status = Phase8ClosedCandleSnapshotStatus.BLOCKED
            expected_reason = Phase8ClosedCandleSnapshotReason.DATA_CONTRACT_BLOCKED
            expected_blockers = (Phase8ClosedCandleSnapshotBlocker.DATA_CONTRACT_BLOCKED,)

            if (
                status != expected_status
                or reason != expected_reason
                or blockers != expected_blockers
                or self.snapshot is not None
            ):
                raise ValueError(
                    "Blocked snapshot result does not match its blocked data contract."
                )
        else:
            if (
                status != Phase8ClosedCandleSnapshotStatus.CREATED
                or reason != Phase8ClosedCandleSnapshotReason.CREATED
                or blockers
                or not isinstance(
                    self.snapshot,
                    StrategyPhase8ClosedCandleSnapshot,
                )
            ):
                raise ValueError("Created snapshot result does not match its data contract.")

            if self.snapshot.contract_decision is not self.contract_decision:
                raise ValueError("Snapshot must preserve the exact data-contract decision.")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.contract_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.contract_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8ClosedCandleSnapshotStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_snapshot(self) -> bool:
        return self.snapshot is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def snapshot_required(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        if self.snapshot is None:
            raise ValueError("No Phase 8 closed-candle snapshot was created.")

        return self.snapshot

    @property
    def can_continue_to_snapshot_verification(
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
            f"{self.contract_decision.stable_id}:"
            "PHASE_8_CLOSED_CANDLE_SNAPSHOT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8ClosedCandleSnapshotFactory:
    """
    Pure factory for externally supplied candle snapshots.

    No candle data is fetched. No MT5, adapter, storage,
    network, broker, or execution operation is performed.
    """

    def generate(
        self,
        contract_decision: (Phase8ClosedCandleDataContractDecision),
        *,
        source_name: str = "EXTERNAL_READ_ONLY",
        captured_at: datetime | None = None,
        series: tuple[
            Phase8ClosedCandleSeries,
            ...,
        ] = (),
    ) -> Phase8ClosedCandleSnapshotDecision:
        if not isinstance(
            contract_decision,
            Phase8ClosedCandleDataContractDecision,
        ):
            raise Phase8ClosedCandleSnapshotError(
                Phase8ClosedCandleSnapshotErrorReason.INVALID_DATA_CONTRACT_DECISION,
                "contract_decision must be a Phase8ClosedCandleDataContractDecision.",
            )

        if contract_decision.is_blocked:
            return Phase8ClosedCandleSnapshotDecision(
                contract_decision=contract_decision,
                status=(Phase8ClosedCandleSnapshotStatus.BLOCKED),
                reason=(Phase8ClosedCandleSnapshotReason.DATA_CONTRACT_BLOCKED),
                blockers=(Phase8ClosedCandleSnapshotBlocker.DATA_CONTRACT_BLOCKED,),
                snapshot=None,
            )

        if captured_at is None:
            raise ValueError("captured_at is required for a created closed-candle snapshot.")

        contract = contract_decision.contract_required
        canonical_payload = _canonical_snapshot_payload(
            schema_version=(PHASE_8_CLOSED_CANDLE_SNAPSHOT_SCHEMA_VERSION),
            contract_id=contract.stable_id,
            contract_digest=contract.contract_digest,
            broker_symbol=contract.broker_symbol,
            direction=contract.direction,
            side=contract.side,
            source_name=source_name,
            captured_at=captured_at,
            series=series,
        )

        snapshot = StrategyPhase8ClosedCandleSnapshot(
            contract_decision=contract_decision,
            source_name=source_name,
            captured_at=captured_at,
            series=series,
            schema_version=(PHASE_8_CLOSED_CANDLE_SNAPSHOT_SCHEMA_VERSION),
            contract_id=contract.stable_id,
            contract_digest=contract.contract_digest,
            snapshot_digest=_sha256_digest(canonical_payload),
        )

        return Phase8ClosedCandleSnapshotDecision(
            contract_decision=contract_decision,
            status=Phase8ClosedCandleSnapshotStatus.CREATED,
            reason=Phase8ClosedCandleSnapshotReason.CREATED,
            blockers=(),
            snapshot=snapshot,
        )

    def build(
        self,
        contract_decision: (Phase8ClosedCandleDataContractDecision),
        *,
        source_name: str = "EXTERNAL_READ_ONLY",
        captured_at: datetime | None = None,
        series: tuple[
            Phase8ClosedCandleSeries,
            ...,
        ] = (),
    ) -> Phase8ClosedCandleSnapshotDecision:
        return self.generate(
            contract_decision,
            source_name=source_name,
            captured_at=captured_at,
            series=series,
        )

    def evaluate(
        self,
        contract_decision: (Phase8ClosedCandleDataContractDecision),
        *,
        source_name: str = "EXTERNAL_READ_ONLY",
        captured_at: datetime | None = None,
        series: tuple[
            Phase8ClosedCandleSeries,
            ...,
        ] = (),
    ) -> Phase8ClosedCandleSnapshotDecision:
        return self.generate(
            contract_decision,
            source_name=source_name,
            captured_at=captured_at,
            series=series,
        )


def generate_phase8_closed_candle_snapshot(
    contract_decision: Phase8ClosedCandleDataContractDecision,
    *,
    source_name: str,
    captured_at: datetime,
    series: tuple[
        Phase8ClosedCandleSeries,
        ...,
    ],
) -> Phase8ClosedCandleSnapshotDecision:
    return StrategyPhase8ClosedCandleSnapshotFactory().generate(
        contract_decision,
        source_name=source_name,
        captured_at=captured_at,
        series=series,
    )


Phase8ClosedCandleSnapshot = StrategyPhase8ClosedCandleSnapshot
Phase8ClosedCandleSnapshotFactory = StrategyPhase8ClosedCandleSnapshotFactory
