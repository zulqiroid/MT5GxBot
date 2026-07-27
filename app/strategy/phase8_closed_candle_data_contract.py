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
    Phase8DryRunPackageDecision,
    Phase8MarketDataMode,
    Phase8RunMode,
    Phase8Timeframe,
    StrategyPhase8DryRunPackage,
)

PHASE_8_CLOSED_CANDLE_DATA_CONTRACT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8ClosedCandleDataContractStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8ClosedCandleDataContractReason(str, Enum):
    CREATED = "CREATED"
    DRY_RUN_PACKAGE_BLOCKED = "DRY_RUN_PACKAGE_BLOCKED"


class Phase8ClosedCandleDataContractBlocker(str, Enum):
    DRY_RUN_PACKAGE_BLOCKED = "DRY_RUN_PACKAGE_BLOCKED"


class Phase8ClosedCandleDataContractErrorReason(
    str,
    Enum,
):
    INVALID_DRY_RUN_PACKAGE_DECISION = "INVALID_DRY_RUN_PACKAGE_DECISION"


class Phase8ClosedCandleDataContractError(RuntimeError):
    """Structured closed-candle contract failure."""

    def __init__(
        self,
        reason: Phase8ClosedCandleDataContractErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8ClosedCandleDataContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 closed-candle data-contract error [{self.reason.value}]: {self.message}"
        )


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


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _is_gold_symbol(symbol: str) -> bool:
    return symbol.upper().startswith("XAUUSD")


def _canonical_contract_payload(
    *,
    schema_version: str,
    package_id: str,
    package_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    run_mode: Phase8RunMode,
    market_data_mode: Phase8MarketDataMode,
    timeframes: tuple[Phase8Timeframe, ...],
    minimum_closed_candles_per_timeframe: int,
    require_timezone_aware_open_times: bool,
    require_strictly_increasing_open_times: bool,
    require_unique_open_times: bool,
    require_finite_ohlc: bool,
    require_positive_ohlc: bool,
    require_ohlc_consistency: bool,
    require_latest_candle_closed: bool,
) -> str:
    timeframe_fragment = ",".join(timeframe.value for timeframe in timeframes)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"PACKAGE_ID={package_id}",
            f"PACKAGE_DIGEST={package_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"RUN_MODE={run_mode.value}",
            f"MARKET_DATA_MODE={market_data_mode.value}",
            f"TIMEFRAMES={timeframe_fragment}",
            (f"MINIMUM_CLOSED_CANDLES_PER_TIMEFRAME={minimum_closed_candles_per_timeframe}"),
            (f"REQUIRE_TIMEZONE_AWARE_OPEN_TIMES={str(require_timezone_aware_open_times).lower()}"),
            (
                "REQUIRE_STRICTLY_INCREASING_OPEN_TIMES="
                f"{str(require_strictly_increasing_open_times).lower()}"
            ),
            (f"REQUIRE_UNIQUE_OPEN_TIMES={str(require_unique_open_times).lower()}"),
            (f"REQUIRE_FINITE_OHLC={str(require_finite_ohlc).lower()}"),
            (f"REQUIRE_POSITIVE_OHLC={str(require_positive_ohlc).lower()}"),
            (f"REQUIRE_OHLC_CONSISTENCY={str(require_ohlc_consistency).lower()}"),
            (f"REQUIRE_LATEST_CANDLE_CLOSED={str(require_latest_candle_closed).lower()}"),
            "EXTERNAL_DATA_ONLY=true",
            "DATA_FETCH=false",
            "MT5_INITIALIZATION=false",
            "NETWORK_WRITE=false",
            "BROKER_WRITE=false",
            "ORDER_SUBMISSION=false",
        )
    )


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandleDataPolicy:
    """Strict policy for future external candle snapshots."""

    minimum_closed_candles_per_timeframe: int = 200
    require_timezone_aware_open_times: bool = True
    require_strictly_increasing_open_times: bool = True
    require_unique_open_times: bool = True
    require_finite_ohlc: bool = True
    require_positive_ohlc: bool = True
    require_ohlc_consistency: bool = True
    require_latest_candle_closed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_closed_candles_per_timeframe",
            _positive_integer(
                self.minimum_closed_candles_per_timeframe,
                "minimum_closed_candles_per_timeframe",
            ),
        )

        for field_name in (
            "require_timezone_aware_open_times",
            "require_strictly_increasing_open_times",
            "require_unique_open_times",
            "require_finite_ohlc",
            "require_positive_ohlc",
            "require_ohlc_consistency",
            "require_latest_candle_closed",
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
                self.require_timezone_aware_open_times,
                self.require_strictly_increasing_open_times,
                self.require_unique_open_times,
                self.require_finite_ohlc,
                self.require_positive_ohlc,
                self.require_ohlc_consistency,
                self.require_latest_candle_closed,
            )
        )


@dataclass(frozen=True, slots=True)
class StrategyPhase8ClosedCandleDataContract:
    """
    Immutable analytical contract for future externally
    supplied closed-candle data.

    It defines validation requirements only. It does not
    fetch data, initialize MT5, invoke an adapter, write
    storage, contact a broker, or submit an order.
    """

    package_decision: Phase8DryRunPackageDecision = field(repr=False)
    policy: Phase8ClosedCandleDataPolicy
    schema_version: str
    package_id: str
    package_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    run_mode: Phase8RunMode
    market_data_mode: Phase8MarketDataMode
    timeframes: tuple[Phase8Timeframe, ...]
    contract_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.package_decision,
            Phase8DryRunPackageDecision,
        ):
            raise ValueError("package_decision must be a Phase8DryRunPackageDecision.")

        if not self.package_decision.is_created:
            raise ValueError("A closed-candle data contract requires a created dry-run package.")

        if not isinstance(
            self.policy,
            Phase8ClosedCandleDataPolicy,
        ):
            raise ValueError("policy must be a Phase8ClosedCandleDataPolicy.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_CLOSED_CANDLE_DATA_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current closed-candle data-contract schema."
            )

        package_id = _non_empty_string(
            self.package_id,
            "package_id",
        )
        package_digest = _non_empty_string(
            self.package_digest,
            "package_digest",
        )
        broker_symbol = _non_empty_string(
            self.broker_symbol,
            "broker_symbol",
        )
        contract_digest = _non_empty_string(
            self.contract_digest,
            "contract_digest",
        )

        for field_name, digest in (
            ("package_digest", package_digest),
            ("contract_digest", contract_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if not isinstance(
            self.side,
            StrategyOrderSide,
        ):
            raise ValueError("side must be a StrategyOrderSide member.")

        if not isinstance(
            self.run_mode,
            Phase8RunMode,
        ):
            raise ValueError("run_mode must be a Phase8RunMode member.")

        if self.run_mode != Phase8RunMode.SIMULATION_ONLY:
            raise ValueError("run_mode must remain SIMULATION_ONLY.")

        if not isinstance(
            self.market_data_mode,
            Phase8MarketDataMode,
        ):
            raise ValueError("market_data_mode must be a Phase8MarketDataMode member.")

        if self.market_data_mode != Phase8MarketDataMode.CLOSED_CANDLES_ONLY:
            raise ValueError("market_data_mode must remain CLOSED_CANDLES_ONLY.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        package = self.package_decision.package_required

        if package_id != package.stable_id:
            raise ValueError("package_id must match the Phase 8 dry-run package.")

        if package_digest != package.package_digest:
            raise ValueError("package_digest must match the Phase 8 dry-run package.")

        if broker_symbol != package.broker_symbol:
            raise ValueError("broker_symbol must match the Phase 8 dry-run package.")

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Closed-candle contracts support Gold/XAUUSD only.")

        if self.direction != package.direction:
            raise ValueError("direction must match the Phase 8 dry-run package.")

        if self.side != package.side:
            raise ValueError("side must match the Phase 8 dry-run package.")

        if self.run_mode != package.scenario.run_mode:
            raise ValueError("run_mode must match the dry-run scenario.")

        if self.market_data_mode != package.scenario.market_data_mode:
            raise ValueError("market_data_mode must match the dry-run scenario.")

        if self.timeframes != package.scenario.timeframes:
            raise ValueError("timeframes must match the dry-run scenario.")

        if not package.phase_8_batch_1_complete:
            raise ValueError("Phase 8 Batch 1 must be complete.")

        if not package.simulation_only:
            raise ValueError("The source package must remain simulation-only.")

        if not package.uses_closed_candles_only:
            raise ValueError("The source package must require closed candles only.")

        if package.initializes_mt5:
            raise ValueError("The source package cannot initialize MT5.")

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
            if getattr(package, attribute_name):
                raise ValueError(
                    f"The source package violates the non-executable boundary: {attribute_name}."
                )

        canonical_payload = _canonical_contract_payload(
            schema_version=schema_version,
            package_id=package_id,
            package_digest=package_digest,
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            run_mode=self.run_mode,
            market_data_mode=self.market_data_mode,
            timeframes=self.timeframes,
            minimum_closed_candles_per_timeframe=(self.policy.minimum_closed_candles_per_timeframe),
            require_timezone_aware_open_times=(self.policy.require_timezone_aware_open_times),
            require_strictly_increasing_open_times=(
                self.policy.require_strictly_increasing_open_times
            ),
            require_unique_open_times=(self.policy.require_unique_open_times),
            require_finite_ohlc=(self.policy.require_finite_ohlc),
            require_positive_ohlc=(self.policy.require_positive_ohlc),
            require_ohlc_consistency=(self.policy.require_ohlc_consistency),
            require_latest_candle_closed=(self.policy.require_latest_candle_closed),
        )

        if contract_digest != _sha256_digest(canonical_payload):
            raise ValueError(
                "contract_digest does not match the canonical closed-candle data contract."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "package_id",
            package_id,
        )
        object.__setattr__(
            self,
            "package_digest",
            package_digest,
        )
        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "contract_digest",
            contract_digest,
        )

    @property
    def package(self) -> StrategyPhase8DryRunPackage:
        return self.package_decision.package_required

    @property
    def observed_at(self) -> datetime:
        return self.package.observed_at

    @property
    def required_series_count(self) -> int:
        return len(self.timeframes)

    @property
    def required_candle_counts(
        self,
    ) -> tuple[tuple[Phase8Timeframe, int], ...]:
        return tuple(
            (
                timeframe,
                self.policy.minimum_closed_candles_per_timeframe,
            )
            for timeframe in self.timeframes
        )

    @property
    def minimum_total_closed_candles(self) -> int:
        return self.required_series_count * self.policy.minimum_closed_candles_per_timeframe

    @property
    def canonical_payload(self) -> str:
        return _canonical_contract_payload(
            schema_version=self.schema_version,
            package_id=self.package_id,
            package_digest=self.package_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            run_mode=self.run_mode,
            market_data_mode=self.market_data_mode,
            timeframes=self.timeframes,
            minimum_closed_candles_per_timeframe=(self.policy.minimum_closed_candles_per_timeframe),
            require_timezone_aware_open_times=(self.policy.require_timezone_aware_open_times),
            require_strictly_increasing_open_times=(
                self.policy.require_strictly_increasing_open_times
            ),
            require_unique_open_times=(self.policy.require_unique_open_times),
            require_finite_ohlc=(self.policy.require_finite_ohlc),
            require_positive_ohlc=(self.policy.require_positive_ohlc),
            require_ohlc_consistency=(self.policy.require_ohlc_consistency),
            require_latest_candle_closed=(self.policy.require_latest_candle_closed),
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_contract_ready(self) -> bool:
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
    def can_continue_to_snapshot_design(self) -> bool:
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
    def contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_CLOSED_CANDLE_DATA_CONTRACT:"
            f"{self.run_mode.value}:"
            f"{self.market_data_mode.value}:"
            f"CONTRACT_SHA256[{self.contract_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.package_decision.stable_id}:{self.contract_id}"


@dataclass(frozen=True, slots=True)
class _ClosedCandleContractEvaluation:
    status: Phase8ClosedCandleDataContractStatus
    reason: Phase8ClosedCandleDataContractReason
    blockers: tuple[
        Phase8ClosedCandleDataContractBlocker,
        ...,
    ]
    contract: StrategyPhase8ClosedCandleDataContract | None


def _derive_contract(
    package_decision: Phase8DryRunPackageDecision,
    policy: Phase8ClosedCandleDataPolicy,
) -> _ClosedCandleContractEvaluation:
    if package_decision.is_blocked:
        return _ClosedCandleContractEvaluation(
            status=Phase8ClosedCandleDataContractStatus.BLOCKED,
            reason=(Phase8ClosedCandleDataContractReason.DRY_RUN_PACKAGE_BLOCKED),
            blockers=(Phase8ClosedCandleDataContractBlocker.DRY_RUN_PACKAGE_BLOCKED,),
            contract=None,
        )

    package = package_decision.package_required
    scenario = package.scenario

    canonical_payload = _canonical_contract_payload(
        schema_version=(PHASE_8_CLOSED_CANDLE_DATA_CONTRACT_SCHEMA_VERSION),
        package_id=package.stable_id,
        package_digest=package.package_digest,
        broker_symbol=package.broker_symbol,
        direction=package.direction,
        side=package.side,
        run_mode=scenario.run_mode,
        market_data_mode=scenario.market_data_mode,
        timeframes=scenario.timeframes,
        minimum_closed_candles_per_timeframe=(policy.minimum_closed_candles_per_timeframe),
        require_timezone_aware_open_times=(policy.require_timezone_aware_open_times),
        require_strictly_increasing_open_times=(policy.require_strictly_increasing_open_times),
        require_unique_open_times=(policy.require_unique_open_times),
        require_finite_ohlc=policy.require_finite_ohlc,
        require_positive_ohlc=policy.require_positive_ohlc,
        require_ohlc_consistency=(policy.require_ohlc_consistency),
        require_latest_candle_closed=(policy.require_latest_candle_closed),
    )

    contract = StrategyPhase8ClosedCandleDataContract(
        package_decision=package_decision,
        policy=policy,
        schema_version=(PHASE_8_CLOSED_CANDLE_DATA_CONTRACT_SCHEMA_VERSION),
        package_id=package.stable_id,
        package_digest=package.package_digest,
        broker_symbol=package.broker_symbol,
        direction=package.direction,
        side=package.side,
        run_mode=scenario.run_mode,
        market_data_mode=scenario.market_data_mode,
        timeframes=scenario.timeframes,
        contract_digest=_sha256_digest(canonical_payload),
    )

    return _ClosedCandleContractEvaluation(
        status=Phase8ClosedCandleDataContractStatus.CREATED,
        reason=Phase8ClosedCandleDataContractReason.CREATED,
        blockers=(),
        contract=contract,
    )


@dataclass(frozen=True, slots=True)
class Phase8ClosedCandleDataContractDecision:
    """Validated analytical closed-candle contract result."""

    package_decision: Phase8DryRunPackageDecision = field(repr=False)
    policy: Phase8ClosedCandleDataPolicy
    status: Phase8ClosedCandleDataContractStatus
    reason: Phase8ClosedCandleDataContractReason
    blockers: tuple[
        Phase8ClosedCandleDataContractBlocker,
        ...,
    ]
    contract: StrategyPhase8ClosedCandleDataContract | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.package_decision,
            Phase8DryRunPackageDecision,
        ):
            raise ValueError("package_decision must be a Phase8DryRunPackageDecision.")

        if not isinstance(
            self.policy,
            Phase8ClosedCandleDataPolicy,
        ):
            raise ValueError("policy must be a Phase8ClosedCandleDataPolicy.")

        try:
            status = Phase8ClosedCandleDataContractStatus(self.status)
            reason = Phase8ClosedCandleDataContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported closed-candle contract status or reason.") from error

        blockers = tuple(
            Phase8ClosedCandleDataContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Closed-candle contract blockers cannot contain duplicates.")

        if self.contract is not None and not isinstance(
            self.contract,
            StrategyPhase8ClosedCandleDataContract,
        ):
            raise ValueError("contract must be a StrategyPhase8ClosedCandleDataContract or None.")

        expected = _derive_contract(
            self.package_decision,
            self.policy,
        )
        supplied = _ClosedCandleContractEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            contract=self.contract,
        )

        if supplied != expected:
            raise ValueError(
                "Closed-candle data-contract result does not match its package and policy."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.package_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.package_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8ClosedCandleDataContractStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_contract(self) -> bool:
        return self.contract is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def contract_required(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        if self.contract is None:
            raise ValueError("No Phase 8 closed-candle data contract was created.")

        return self.contract

    @property
    def can_continue_to_snapshot_design(self) -> bool:
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
            f"{self.package_decision.stable_id}:"
            "PHASE_8_CLOSED_CANDLE_DATA_CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8ClosedCandleDataContractFactory:
    """
    Pure factory for closed-candle data requirements.

    CREATED permits later external snapshot design only.
    No market data is fetched and no MT5, network, storage,
    broker, or trading operation is performed.
    """

    def generate(
        self,
        package_decision: Phase8DryRunPackageDecision,
        policy: Phase8ClosedCandleDataPolicy | None = None,
    ) -> Phase8ClosedCandleDataContractDecision:
        if not isinstance(
            package_decision,
            Phase8DryRunPackageDecision,
        ):
            raise Phase8ClosedCandleDataContractError(
                Phase8ClosedCandleDataContractErrorReason.INVALID_DRY_RUN_PACKAGE_DECISION,
                "package_decision must be a Phase8DryRunPackageDecision.",
            )

        selected_policy = policy or Phase8ClosedCandleDataPolicy()

        if not isinstance(
            selected_policy,
            Phase8ClosedCandleDataPolicy,
        ):
            raise ValueError("policy must be a Phase8ClosedCandleDataPolicy.")

        evaluation = _derive_contract(
            package_decision,
            selected_policy,
        )

        return Phase8ClosedCandleDataContractDecision(
            package_decision=package_decision,
            policy=selected_policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            contract=evaluation.contract,
        )

    def build(
        self,
        package_decision: Phase8DryRunPackageDecision,
        policy: Phase8ClosedCandleDataPolicy | None = None,
    ) -> Phase8ClosedCandleDataContractDecision:
        return self.generate(
            package_decision,
            policy,
        )

    def evaluate(
        self,
        package_decision: Phase8DryRunPackageDecision,
        policy: Phase8ClosedCandleDataPolicy | None = None,
    ) -> Phase8ClosedCandleDataContractDecision:
        return self.generate(
            package_decision,
            policy,
        )


def generate_phase8_closed_candle_data_contract(
    package_decision: Phase8DryRunPackageDecision,
    policy: Phase8ClosedCandleDataPolicy | None = None,
) -> Phase8ClosedCandleDataContractDecision:
    return StrategyPhase8ClosedCandleDataContractFactory().generate(
        package_decision,
        policy,
    )


Phase8ClosedCandleDataContract = StrategyPhase8ClosedCandleDataContract
Phase8ClosedCandleDataContractFactory = StrategyPhase8ClosedCandleDataContractFactory
