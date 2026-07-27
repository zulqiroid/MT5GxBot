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
from app.strategy.phase8_closed_candle_snapshot import (
    Phase8ClosedCandleSnapshotDecision,
    StrategyPhase8ClosedCandleSnapshot,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
)

PHASE_8_CLOSED_CANDLE_SNAPSHOT_VERIFICATION_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8ClosedCandleSnapshotVerificationCheck(
    str,
    Enum,
):
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    SNAPSHOT_ID_MATCH = "SNAPSHOT_ID_MATCH"
    SNAPSHOT_DIGEST_MATCH = "SNAPSHOT_DIGEST_MATCH"
    CONTRACT_LINEAGE_MATCH = "CONTRACT_LINEAGE_MATCH"
    SERIES_COUNT_MATCH = "SERIES_COUNT_MATCH"
    TIMEFRAME_ORDER_MATCH = "TIMEFRAME_ORDER_MATCH"
    CANDLE_COUNTS_MATCH = "CANDLE_COUNTS_MATCH"
    SERIES_DIGESTS_MATCH = "SERIES_DIGESTS_MATCH"
    CANDLE_DIGESTS_MATCH = "CANDLE_DIGESTS_MATCH"
    CLOSURE_TIMES_MATCH = "CLOSURE_TIMES_MATCH"
    NO_IO_BOUNDARY = "NO_IO_BOUNDARY"


_VERIFICATION_CHECKS = (
    Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_CREATED,
    Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_ID_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_DIGEST_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.CONTRACT_LINEAGE_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.SERIES_COUNT_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.TIMEFRAME_ORDER_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.CANDLE_COUNTS_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.SERIES_DIGESTS_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.CANDLE_DIGESTS_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.CLOSURE_TIMES_MATCH,
    Phase8ClosedCandleSnapshotVerificationCheck.NO_IO_BOUNDARY,
)


class Phase8ClosedCandleSnapshotVerificationStatus(
    str,
    Enum,
):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class Phase8ClosedCandleSnapshotVerificationReason(
    str,
    Enum,
):
    VERIFIED = "VERIFIED"
    SNAPSHOT_BLOCKED = "SNAPSHOT_BLOCKED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class Phase8ClosedCandleSnapshotVerificationBlocker(
    str,
    Enum,
):
    SNAPSHOT_BLOCKED = "SNAPSHOT_BLOCKED"
    SNAPSHOT_ID_MISMATCH = "SNAPSHOT_ID_MISMATCH"
    SNAPSHOT_DIGEST_MISMATCH = "SNAPSHOT_DIGEST_MISMATCH"
    CONTRACT_LINEAGE_MISMATCH = "CONTRACT_LINEAGE_MISMATCH"
    SERIES_COUNT_MISMATCH = "SERIES_COUNT_MISMATCH"
    TIMEFRAME_ORDER_MISMATCH = "TIMEFRAME_ORDER_MISMATCH"
    CANDLE_COUNT_MISMATCH = "CANDLE_COUNT_MISMATCH"
    SERIES_DIGEST_MISMATCH = "SERIES_DIGEST_MISMATCH"
    CANDLE_DIGEST_MISMATCH = "CANDLE_DIGEST_MISMATCH"
    CLOSURE_TIME_MISMATCH = "CLOSURE_TIME_MISMATCH"
    IO_BOUNDARY_VIOLATION = "IO_BOUNDARY_VIOLATION"


_CHECK_TO_BLOCKER = {
    Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_ID_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.SNAPSHOT_ID_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_DIGEST_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.SNAPSHOT_DIGEST_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.CONTRACT_LINEAGE_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.CONTRACT_LINEAGE_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.SERIES_COUNT_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.SERIES_COUNT_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.TIMEFRAME_ORDER_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.TIMEFRAME_ORDER_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.CANDLE_COUNTS_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.CANDLE_COUNT_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.SERIES_DIGESTS_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.SERIES_DIGEST_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.CANDLE_DIGESTS_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.CANDLE_DIGEST_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.CLOSURE_TIMES_MATCH: (
        Phase8ClosedCandleSnapshotVerificationBlocker.CLOSURE_TIME_MISMATCH
    ),
    Phase8ClosedCandleSnapshotVerificationCheck.NO_IO_BOUNDARY: (
        Phase8ClosedCandleSnapshotVerificationBlocker.IO_BOUNDARY_VIOLATION
    ),
}


class Phase8ClosedCandleSnapshotVerificationErrorReason(
    str,
    Enum,
):
    INVALID_SNAPSHOT_DECISION = "INVALID_SNAPSHOT_DECISION"


class Phase8ClosedCandleSnapshotVerificationError(
    RuntimeError,
):
    """Structured snapshot-verification failure."""

    def __init__(
        self,
        reason: (Phase8ClosedCandleSnapshotVerificationErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8ClosedCandleSnapshotVerificationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 closed-candle snapshot verification "
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


def _expected_snapshot_id(
    snapshot: StrategyPhase8ClosedCandleSnapshot,
) -> str:
    return (
        f"{snapshot.broker_symbol}:"
        f"{snapshot.side.value}:"
        "PHASE_8_CLOSED_CANDLE_SNAPSHOT:"
        f"SOURCE[{snapshot.source_name}]:"
        f"SNAPSHOT_SHA256[{snapshot.snapshot_digest}]"
    )


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandleSnapshotVerificationEntry:
    check: Phase8ClosedCandleSnapshotVerificationCheck
    passed: bool

    def __post_init__(self) -> None:
        try:
            check = Phase8ClosedCandleSnapshotVerificationCheck(self.check)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported snapshot-verification check.") from error

        passed = _strict_boolean(
            self.passed,
            "passed",
        )

        object.__setattr__(self, "check", check)
        object.__setattr__(self, "passed", passed)


def _has_safe_boundary(
    snapshot_decision: Phase8ClosedCandleSnapshotDecision,
    snapshot: StrategyPhase8ClosedCandleSnapshot,
) -> bool:
    boolean_false_attributes = (
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

    for subject in (snapshot_decision, snapshot):
        for attribute_name in boolean_false_attributes:
            if not hasattr(subject, attribute_name):
                return False

            if getattr(subject, attribute_name):
                return False

        if not hasattr(subject, "fetches_data"):
            return False

        if subject.fetches_data:
            return False

        if not hasattr(subject, "initializes_mt5"):
            return False

        if subject.initializes_mt5:
            return False

    return True


def _evaluate_created_snapshot(
    snapshot_decision: Phase8ClosedCandleSnapshotDecision,
) -> tuple[
    tuple[
        Phase8ClosedCandleSnapshotVerificationEntry,
        ...,
    ],
    tuple[
        Phase8ClosedCandleSnapshotVerificationBlocker,
        ...,
    ],
]:
    snapshot = snapshot_decision.snapshot_required
    contract = snapshot.contract
    minimum_count = contract.policy.minimum_closed_candles_per_timeframe

    snapshot_created = snapshot_decision.is_created and snapshot_decision.has_snapshot

    snapshot_id_matches = snapshot.snapshot_id == _expected_snapshot_id(snapshot)

    snapshot_digest_matches = snapshot.snapshot_digest == _sha256_digest(snapshot.canonical_payload)

    contract_lineage_matches = (
        snapshot.contract_id == contract.stable_id
        and snapshot.contract_digest == contract.contract_digest
        and snapshot.contract_decision is snapshot_decision.contract_decision
    )

    series_count_matches = snapshot.series_count == 4 and len(snapshot.series) == 4

    timeframe_order_matches = (
        snapshot.timeframes == _REQUIRED_TIMEFRAMES and snapshot.timeframes == contract.timeframes
    )

    candle_counts_match = all(
        item.candle_count >= minimum_count for item in snapshot.series
    ) and snapshot.total_candle_count == sum(item.candle_count for item in snapshot.series)

    series_digests_match = all(
        item.series_digest == _sha256_digest(item.canonical_payload) for item in snapshot.series
    )

    candle_digests_match = all(
        candle.candle_digest == _sha256_digest(candle.canonical_row)
        for item in snapshot.series
        for candle in item.candles
    )

    closure_times_match = (
        all(
            candle.close_time > candle.open_time and candle.close_time <= snapshot.captured_at
            for item in snapshot.series
            for candle in item.candles
        )
        and snapshot.latest_close_time <= snapshot.captured_at
    )

    no_io_boundary = _has_safe_boundary(
        snapshot_decision,
        snapshot,
    )

    results = {
        Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_CREATED: snapshot_created,
        Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_ID_MATCH: snapshot_id_matches,
        Phase8ClosedCandleSnapshotVerificationCheck.SNAPSHOT_DIGEST_MATCH: snapshot_digest_matches,
        Phase8ClosedCandleSnapshotVerificationCheck.CONTRACT_LINEAGE_MATCH: contract_lineage_matches,
        Phase8ClosedCandleSnapshotVerificationCheck.SERIES_COUNT_MATCH: series_count_matches,
        Phase8ClosedCandleSnapshotVerificationCheck.TIMEFRAME_ORDER_MATCH: timeframe_order_matches,
        Phase8ClosedCandleSnapshotVerificationCheck.CANDLE_COUNTS_MATCH: candle_counts_match,
        Phase8ClosedCandleSnapshotVerificationCheck.SERIES_DIGESTS_MATCH: series_digests_match,
        Phase8ClosedCandleSnapshotVerificationCheck.CANDLE_DIGESTS_MATCH: candle_digests_match,
        Phase8ClosedCandleSnapshotVerificationCheck.CLOSURE_TIMES_MATCH: closure_times_match,
        Phase8ClosedCandleSnapshotVerificationCheck.NO_IO_BOUNDARY: no_io_boundary,
    }

    entries = tuple(
        Phase8ClosedCandleSnapshotVerificationEntry(
            check=check,
            passed=results[check],
        )
        for check in _VERIFICATION_CHECKS
    )

    blockers: list[Phase8ClosedCandleSnapshotVerificationBlocker] = []

    if not snapshot_created:
        blockers.append(Phase8ClosedCandleSnapshotVerificationBlocker.SNAPSHOT_BLOCKED)

    for entry in entries:
        if entry.passed:
            continue

        blocker = _CHECK_TO_BLOCKER.get(entry.check)

        if blocker is not None and blocker not in blockers:
            blockers.append(blocker)

    return entries, tuple(blockers)


def _canonical_receipt_payload(
    *,
    schema_version: str,
    snapshot_id: str,
    snapshot_digest: str,
    contract_id: str,
    contract_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    series_digests: tuple[
        tuple[Phase8Timeframe, str],
        ...,
    ],
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ],
    total_candle_count: int,
    entries: tuple[
        Phase8ClosedCandleSnapshotVerificationEntry,
        ...,
    ],
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
        f"SNAPSHOT_ID={snapshot_id}",
        f"SNAPSHOT_DIGEST={snapshot_digest}",
        f"CONTRACT_ID={contract_id}",
        f"CONTRACT_DIGEST={contract_digest}",
        f"BROKER_SYMBOL={broker_symbol}",
        f"DIRECTION={direction.value}",
        f"SIDE={side.value}",
        f"SOURCE_NAME={source_name}",
        (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
        f"SERIES_COUNT={len(series_digests)}",
        f"TOTAL_CANDLE_COUNT={total_candle_count}",
    ]

    for index, (
        digest_item,
        count_item,
    ) in enumerate(
        zip(
            series_digests,
            series_counts,
            strict=True,
        ),
        start=1,
    ):
        digest_timeframe, digest = digest_item
        count_timeframe, count = count_item

        lines.extend(
            (
                (f"SERIES_{index}_TIMEFRAME={digest_timeframe.value}"),
                (f"SERIES_{index}_COUNT_TIMEFRAME={count_timeframe.value}"),
                f"SERIES_{index}_CANDLE_COUNT={count}",
                f"SERIES_{index}_DIGEST={digest}",
            )
        )

    for index, entry in enumerate(entries, start=1):
        lines.extend(
            (
                (f"CHECK_{index}_NAME={entry.check.value}"),
                (f"CHECK_{index}_PASSED={str(entry.passed).lower()}"),
            )
        )

    lines.extend(
        (
            "VERIFIED=true",
            "DATA_FETCH=false",
            "MT5_INITIALIZATION=false",
            "STORAGE_WRITE=false",
            "NETWORK_WRITE=false",
            "BROKER_WRITE=false",
            "ORDER_SUBMISSION=false",
        )
    )

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
    """Immutable deterministic verification receipt."""

    snapshot_decision: Phase8ClosedCandleSnapshotDecision = field(repr=False)
    schema_version: str
    snapshot_id: str
    snapshot_digest: str
    contract_id: str
    contract_digest: str
    source_name: str
    captured_at: datetime
    series_digests: tuple[
        tuple[Phase8Timeframe, str],
        ...,
    ]
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ]
    total_candle_count: int
    entries: tuple[
        Phase8ClosedCandleSnapshotVerificationEntry,
        ...,
    ]
    receipt_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.snapshot_decision,
            Phase8ClosedCandleSnapshotDecision,
        ):
            raise ValueError("snapshot_decision must be a Phase8ClosedCandleSnapshotDecision.")

        if not self.snapshot_decision.is_created:
            raise ValueError("A verification receipt requires a created closed-candle snapshot.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_CLOSED_CANDLE_SNAPSHOT_VERIFICATION_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current snapshot-verification schema.")

        snapshot_id = _non_empty_string(
            self.snapshot_id,
            "snapshot_id",
        )
        snapshot_digest = _non_empty_string(
            self.snapshot_digest,
            "snapshot_digest",
        )
        contract_id = _non_empty_string(
            self.contract_id,
            "contract_id",
        )
        contract_digest = _non_empty_string(
            self.contract_digest,
            "contract_digest",
        )
        source_name = _non_empty_string(
            self.source_name,
            "source_name",
        )
        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        receipt_digest = _non_empty_string(
            self.receipt_digest,
            "receipt_digest",
        )

        for field_name, digest in (
            ("snapshot_digest", snapshot_digest),
            ("contract_digest", contract_digest),
            ("receipt_digest", receipt_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        if not isinstance(self.series_digests, tuple):
            raise ValueError("series_digests must be a tuple.")

        if not isinstance(self.series_counts, tuple):
            raise ValueError("series_counts must be a tuple.")

        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple.")

        total_candle_count = _positive_integer(
            self.total_candle_count,
            "total_candle_count",
        )

        snapshot = self.snapshot_decision.snapshot_required

        if snapshot_id != snapshot.stable_id:
            raise ValueError("snapshot_id must match the verified closed-candle snapshot.")

        if snapshot_digest != snapshot.snapshot_digest:
            raise ValueError("snapshot_digest must match the verified closed-candle snapshot.")

        if contract_id != snapshot.contract.stable_id:
            raise ValueError("contract_id must match the verified data contract.")

        if contract_digest != snapshot.contract.contract_digest:
            raise ValueError("contract_digest must match the verified data contract.")

        if source_name != snapshot.source_name:
            raise ValueError("source_name must match the verified snapshot.")

        if captured_at != snapshot.captured_at:
            raise ValueError("captured_at must match the verified snapshot.")

        expected_series_digests = tuple(
            (
                item.timeframe,
                item.series_digest,
            )
            for item in snapshot.series
        )
        expected_series_counts = tuple(
            (
                item.timeframe,
                item.candle_count,
            )
            for item in snapshot.series
        )

        if self.series_digests != expected_series_digests:
            raise ValueError("series_digests must match the verified snapshot.")

        if self.series_counts != expected_series_counts:
            raise ValueError("series_counts must match the verified snapshot.")

        if total_candle_count != snapshot.total_candle_count:
            raise ValueError("total_candle_count must match the verified snapshot.")

        expected_entries, blockers = _evaluate_created_snapshot(self.snapshot_decision)

        if blockers:
            raise ValueError(
                "A verification receipt cannot be created for a snapshot with failed checks."
            )

        if self.entries != expected_entries:
            raise ValueError("entries must match the exact deterministic verification checks.")

        if tuple(entry.check for entry in self.entries) != _VERIFICATION_CHECKS:
            raise ValueError("entries must preserve exact check order.")

        if not all(entry.passed for entry in self.entries):
            raise ValueError("All verification entries must pass.")

        canonical_payload = _canonical_receipt_payload(
            schema_version=schema_version,
            snapshot_id=snapshot_id,
            snapshot_digest=snapshot_digest,
            contract_id=contract_id,
            contract_digest=contract_digest,
            broker_symbol=snapshot.broker_symbol,
            direction=snapshot.direction,
            side=snapshot.side,
            source_name=source_name,
            captured_at=captured_at,
            series_digests=self.series_digests,
            series_counts=self.series_counts,
            total_candle_count=total_candle_count,
            entries=self.entries,
        )

        if receipt_digest != _sha256_digest(canonical_payload):
            raise ValueError("receipt_digest does not match the canonical verification receipt.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "snapshot_id",
            snapshot_id,
        )
        object.__setattr__(
            self,
            "snapshot_digest",
            snapshot_digest,
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
            "total_candle_count",
            total_candle_count,
        )
        object.__setattr__(
            self,
            "receipt_digest",
            receipt_digest,
        )

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.snapshot_decision.snapshot_required

    @property
    def broker_symbol(self) -> str:
        return self.snapshot.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.snapshot.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.snapshot.side

    @property
    def canonical_payload(self) -> str:
        return _canonical_receipt_payload(
            schema_version=self.schema_version,
            snapshot_id=self.snapshot_id,
            snapshot_digest=self.snapshot_digest,
            contract_id=self.contract_id,
            contract_digest=self.contract_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            series_digests=self.series_digests,
            series_counts=self.series_counts,
            total_candle_count=self.total_candle_count,
            entries=self.entries,
        )

    @property
    def check_count(self) -> int:
        return len(self.entries)

    @property
    def passed_check_count(self) -> int:
        return sum(1 for entry in self.entries if entry.passed)

    @property
    def is_verified(self) -> bool:
        return True

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_simulation_input_design(
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
    def receipt_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_CLOSED_CANDLE_SNAPSHOT_VERIFICATION:"
            f"RECEIPT_SHA256[{self.receipt_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.snapshot_decision.stable_id}:{self.receipt_id}"


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandleSnapshotVerificationDecision:
    """Deterministic snapshot-verification decision."""

    snapshot_decision: Phase8ClosedCandleSnapshotDecision = field(repr=False)
    status: Phase8ClosedCandleSnapshotVerificationStatus
    reason: Phase8ClosedCandleSnapshotVerificationReason
    blockers: tuple[
        Phase8ClosedCandleSnapshotVerificationBlocker,
        ...,
    ]
    receipt: StrategyPhase8ClosedCandleSnapshotVerificationReceipt | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.snapshot_decision,
            Phase8ClosedCandleSnapshotDecision,
        ):
            raise ValueError("snapshot_decision must be a Phase8ClosedCandleSnapshotDecision.")

        try:
            status = Phase8ClosedCandleSnapshotVerificationStatus(self.status)
            reason = Phase8ClosedCandleSnapshotVerificationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported snapshot-verification status or reason.") from error

        blockers = tuple(
            Phase8ClosedCandleSnapshotVerificationBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Verification blockers cannot contain duplicates.")

        if self.snapshot_decision.is_blocked:
            if (
                status != (Phase8ClosedCandleSnapshotVerificationStatus.BLOCKED)
                or reason != (Phase8ClosedCandleSnapshotVerificationReason.SNAPSHOT_BLOCKED)
                or blockers != (Phase8ClosedCandleSnapshotVerificationBlocker.SNAPSHOT_BLOCKED,)
                or self.receipt is not None
            ):
                raise ValueError("Blocked verification result does not match its blocked snapshot.")
        else:
            _, expected_blockers = _evaluate_created_snapshot(self.snapshot_decision)

            if expected_blockers:
                if (
                    status != (Phase8ClosedCandleSnapshotVerificationStatus.BLOCKED)
                    or reason != (Phase8ClosedCandleSnapshotVerificationReason.VERIFICATION_FAILED)
                    or blockers != expected_blockers
                    or self.receipt is not None
                ):
                    raise ValueError(
                        "Failed verification result does not match its snapshot checks."
                    )
            else:
                if (
                    status != (Phase8ClosedCandleSnapshotVerificationStatus.VERIFIED)
                    or reason != (Phase8ClosedCandleSnapshotVerificationReason.VERIFIED)
                    or blockers
                    or not isinstance(
                        self.receipt,
                        StrategyPhase8ClosedCandleSnapshotVerificationReceipt,
                    )
                    or self.receipt.snapshot_decision is not self.snapshot_decision
                ):
                    raise ValueError("Verified result does not match its snapshot checks.")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.snapshot_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.snapshot_decision.direction

    @property
    def is_verified(self) -> bool:
        return self.status == (Phase8ClosedCandleSnapshotVerificationStatus.VERIFIED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_verified

    @property
    def has_receipt(self) -> bool:
        return self.receipt is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def receipt_required(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        if self.receipt is None:
            raise ValueError("No Phase 8 snapshot-verification receipt was created.")

        return self.receipt

    @property
    def can_continue_to_simulation_input_design(
        self,
    ) -> bool:
        return self.is_verified

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
            f"{self.snapshot_decision.stable_id}:"
            "PHASE_8_CLOSED_CANDLE_SNAPSHOT_VERIFICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8ClosedCandleSnapshotVerificationFactory:
    """Pure deterministic snapshot-verification factory."""

    def verify(
        self,
        snapshot_decision: (Phase8ClosedCandleSnapshotDecision),
    ) -> Phase8ClosedCandleSnapshotVerificationDecision:
        if not isinstance(
            snapshot_decision,
            Phase8ClosedCandleSnapshotDecision,
        ):
            raise Phase8ClosedCandleSnapshotVerificationError(
                Phase8ClosedCandleSnapshotVerificationErrorReason.INVALID_SNAPSHOT_DECISION,
                "snapshot_decision must be a Phase8ClosedCandleSnapshotDecision.",
            )

        if snapshot_decision.is_blocked:
            return Phase8ClosedCandleSnapshotVerificationDecision(
                snapshot_decision=snapshot_decision,
                status=(Phase8ClosedCandleSnapshotVerificationStatus.BLOCKED),
                reason=(Phase8ClosedCandleSnapshotVerificationReason.SNAPSHOT_BLOCKED),
                blockers=(Phase8ClosedCandleSnapshotVerificationBlocker.SNAPSHOT_BLOCKED,),
                receipt=None,
            )

        entries, blockers = _evaluate_created_snapshot(snapshot_decision)

        if blockers:
            return Phase8ClosedCandleSnapshotVerificationDecision(
                snapshot_decision=snapshot_decision,
                status=(Phase8ClosedCandleSnapshotVerificationStatus.BLOCKED),
                reason=(Phase8ClosedCandleSnapshotVerificationReason.VERIFICATION_FAILED),
                blockers=blockers,
                receipt=None,
            )

        snapshot = snapshot_decision.snapshot_required
        series_digests = tuple(
            (
                item.timeframe,
                item.series_digest,
            )
            for item in snapshot.series
        )
        series_counts = tuple(
            (
                item.timeframe,
                item.candle_count,
            )
            for item in snapshot.series
        )

        canonical_payload = _canonical_receipt_payload(
            schema_version=(PHASE_8_CLOSED_CANDLE_SNAPSHOT_VERIFICATION_SCHEMA_VERSION),
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            contract_id=snapshot.contract.stable_id,
            contract_digest=(snapshot.contract.contract_digest),
            broker_symbol=snapshot.broker_symbol,
            direction=snapshot.direction,
            side=snapshot.side,
            source_name=snapshot.source_name,
            captured_at=snapshot.captured_at,
            series_digests=series_digests,
            series_counts=series_counts,
            total_candle_count=snapshot.total_candle_count,
            entries=entries,
        )

        receipt = StrategyPhase8ClosedCandleSnapshotVerificationReceipt(
            snapshot_decision=snapshot_decision,
            schema_version=(PHASE_8_CLOSED_CANDLE_SNAPSHOT_VERIFICATION_SCHEMA_VERSION),
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            contract_id=snapshot.contract.stable_id,
            contract_digest=(snapshot.contract.contract_digest),
            source_name=snapshot.source_name,
            captured_at=snapshot.captured_at,
            series_digests=series_digests,
            series_counts=series_counts,
            total_candle_count=(snapshot.total_candle_count),
            entries=entries,
            receipt_digest=_sha256_digest(canonical_payload),
        )

        return Phase8ClosedCandleSnapshotVerificationDecision(
            snapshot_decision=snapshot_decision,
            status=(Phase8ClosedCandleSnapshotVerificationStatus.VERIFIED),
            reason=(Phase8ClosedCandleSnapshotVerificationReason.VERIFIED),
            blockers=(),
            receipt=receipt,
        )

    def generate(
        self,
        snapshot_decision: (Phase8ClosedCandleSnapshotDecision),
    ) -> Phase8ClosedCandleSnapshotVerificationDecision:
        return self.verify(snapshot_decision)

    def build(
        self,
        snapshot_decision: (Phase8ClosedCandleSnapshotDecision),
    ) -> Phase8ClosedCandleSnapshotVerificationDecision:
        return self.verify(snapshot_decision)

    def evaluate(
        self,
        snapshot_decision: (Phase8ClosedCandleSnapshotDecision),
    ) -> Phase8ClosedCandleSnapshotVerificationDecision:
        return self.verify(snapshot_decision)


def verify_phase8_closed_candle_snapshot(
    snapshot_decision: Phase8ClosedCandleSnapshotDecision,
) -> Phase8ClosedCandleSnapshotVerificationDecision:
    return StrategyPhase8ClosedCandleSnapshotVerificationFactory().verify(snapshot_decision)


Phase8ClosedCandleSnapshotVerificationReceipt = (
    StrategyPhase8ClosedCandleSnapshotVerificationReceipt
)
Phase8ClosedCandleSnapshotVerificationFactory = (
    StrategyPhase8ClosedCandleSnapshotVerificationFactory
)
