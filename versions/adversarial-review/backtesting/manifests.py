from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256

from backtesting.market_data import (
    CanonicalTimeframe, Gap, HistoricalDataset, ValidationStatus, _canonical_decimal,
)


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC timezone-aware.")
    return value.astimezone(timezone.utc)


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    return value


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode()).hexdigest()


@dataclass(frozen=True)
class DatasetManifest:
    id: str
    dataset_id: str
    schema_version: str
    source: str
    exchange: str
    symbol: str
    timeframes: tuple[CanonicalTimeframe, ...]
    interval_start_inclusive: datetime
    interval_end_exclusive: datetime
    candle_counts: tuple[tuple[CanonicalTimeframe, int], ...]
    gaps: tuple[Gap, ...]
    fingerprint: str
    created_at: datetime
    timezone: str
    validation_status: ValidationStatus
    approved_exclusions: tuple[str, ...]
    configuration_id: str

    def __post_init__(self) -> None:
        for value, name in ((self.dataset_id, "dataset_id"), (self.schema_version, "schema_version"),
                            (self.source, "source"), (self.exchange, "exchange"),
                            (self.symbol, "symbol"), (self.fingerprint, "fingerprint"),
                            (self.configuration_id, "configuration_id")):
            _text(value, name)
        start = _utc(self.interval_start_inclusive, "interval_start_inclusive")
        end = _utc(self.interval_end_exclusive, "interval_end_exclusive")
        _utc(self.created_at, "created_at")
        if start >= end or self.timezone != "UTC":
            raise ValueError("Dataset manifest requires a valid UTC half-open interval.")
        if not self.timeframes or tuple(sorted(set(self.timeframes), key=lambda t: t.duration)) != self.timeframes:
            raise ValueError("Dataset timeframes must be unique and canonically ordered.")
        if not isinstance(self.validation_status, ValidationStatus):
            raise TypeError("validation_status must be canonical.")
        if tuple(timeframe for timeframe, _ in self.candle_counts) != self.timeframes:
            raise ValueError("Candle counts must correspond to every canonical timeframe.")
        if any(isinstance(count, bool) or not isinstance(count, int) or count <= 0 for _, count in self.candle_counts):
            raise ValueError("Candle counts must be positive integers.")
        if not isinstance(self.approved_exclusions, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.approved_exclusions):
            raise ValueError("Approved exclusions must be immutable nonblank descriptions.")
        expected = _hash(("dataset-manifest-v1", self.dataset_id, self.fingerprint,
                          self.symbol, self.configuration_id, start.isoformat(), end.isoformat()))
        if self.id != expected:
            raise ValueError("Dataset manifest identity is inconsistent.")

    @classmethod
    def from_dataset(cls, dataset: HistoricalDataset, *, symbol: str,
                     created_at: datetime, configuration_id: str,
                     approved_exclusions: tuple[str, ...] = ()) -> DatasetManifest:
        _text(symbol, "symbol"); _text(configuration_id, "configuration_id")
        created = _utc(created_at, "created_at")
        if symbol != dataset.symbol:
            raise ValueError("Manifest symbol does not match the validated dataset.")
        selected = tuple(c for c in dataset.candles if c.symbol == symbol)
        if not selected:
            raise ValueError("Manifest symbol has no validated candles.")
        timeframes = tuple(sorted({c.timeframe for c in selected}, key=lambda t: t.duration))
        counts = tuple((tf, sum(c.timeframe is tf for c in selected)) for tf in timeframes)
        start = min(c.open_time for c in selected)
        # Replay events use candle close timestamps and [start, end). The
        # exclusive horizon is therefore one datetime quantum after the final
        # included close timestamp.
        end = max(c.close_time for c in selected) + timedelta(microseconds=1)
        identity = _hash(("dataset-manifest-v1", dataset.dataset_id, dataset.fingerprint,
                          symbol, configuration_id, start.isoformat(), end.isoformat()))
        return cls(identity, dataset.dataset_id, dataset.schema_version, dataset.source,
                   dataset.exchange, symbol, timeframes, start, end, counts,
                   dataset.gaps, dataset.fingerprint, created, "UTC",
                   dataset.validation_status, approved_exclusions, configuration_id)


@dataclass(frozen=True)
class RuntimeFacts:
    python_version: str
    implementation: str
    platform: str
    application_version: str

    def __post_init__(self) -> None:
        for field in ("python_version", "implementation", "platform", "application_version"):
            _text(getattr(self, field), field)


@dataclass(frozen=True)
class BacktestRunManifest:
    id: str
    dataset_id: str
    dataset_fingerprint: str
    trading_brain_contract_version: str
    strategy_configuration_version: str
    model_configuration_version: str
    symbol: str
    timeframes: tuple[CanonicalTimeframe, ...]
    replay_start_inclusive: datetime
    replay_end_exclusive: datetime
    starting_equity: Decimal
    execution_cost_configuration_id: str
    random_seed: int
    runtime: RuntimeFacts
    mode: str
    exchange_submission_enabled: bool
    risk_reward_policy_id: str = "CANONICAL_MIN_RR_V1"
    performance_objective_id: str = "NONE"
    performance_sample_type: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        _text(self.risk_reward_policy_id, "risk_reward_policy_id")
        _text(self.performance_objective_id, "performance_objective_id")
        if ((self.performance_objective_id == "NONE" and self.performance_sample_type != "UNSPECIFIED")
                or (self.performance_objective_id != "NONE" and self.performance_sample_type != "OUT_OF_SAMPLE")):
            raise ValueError("performance objective/sample type identity is inconsistent")
        if self.mode != "PAPER_SIMULATION" or self.exchange_submission_enabled is not False:
            raise ValueError("Backtest runs are paper simulation with exchange submission disabled.")
        start = _utc(self.replay_start_inclusive, "replay_start_inclusive")
        end = _utc(self.replay_end_exclusive, "replay_end_exclusive")
        if start >= end:
            raise ValueError("Replay interval must be nonempty and half-open.")
        if not self.timeframes or any(not isinstance(item, CanonicalTimeframe) for item in self.timeframes):
            raise ValueError("Run timeframes must be canonical and nonempty.")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise TypeError("random_seed must be an integer.")
        if not isinstance(self.starting_equity, Decimal) or not self.starting_equity.is_finite() or self.starting_equity <= 0:
            raise ValueError("starting_equity must be a finite positive Decimal.")
        parts = ("backtest-run-v1", self.dataset_id, self.dataset_fingerprint,
                          self.trading_brain_contract_version, self.strategy_configuration_version,
                          self.model_configuration_version, self.symbol,
                          ",".join(t.value for t in self.timeframes), start.isoformat(),
                          end.isoformat(), _canonical_decimal(self.starting_equity),
                          self.execution_cost_configuration_id, str(self.random_seed),
                          self.runtime.python_version, self.runtime.implementation,
                          self.runtime.platform, self.runtime.application_version,
                          "PAPER_SIMULATION", "false")
        if (self.risk_reward_policy_id, self.performance_objective_id) != ("CANONICAL_MIN_RR_V1", "NONE"):
            parts += (self.risk_reward_policy_id, self.performance_objective_id,
                      self.performance_sample_type)
        expected = _hash(parts)
        if self.id != expected:
            raise ValueError("Backtest run identity is inconsistent.")

    @classmethod
    def create(cls, *, dataset: DatasetManifest, trading_brain_contract_version: str,
               strategy_configuration_version: str, model_configuration_version: str,
               replay_start_inclusive: datetime, replay_end_exclusive: datetime,
               starting_equity: Decimal, execution_cost_configuration_id: str,
               random_seed: int, runtime: RuntimeFacts,
               risk_reward_policy_id: str = "CANONICAL_MIN_RR_V1",
               performance_objective_id: str = "NONE") -> BacktestRunManifest:
        start = _utc(replay_start_inclusive, "replay_start_inclusive")
        end = _utc(replay_end_exclusive, "replay_end_exclusive")
        if start >= end or start < dataset.interval_start_inclusive or end > dataset.interval_end_exclusive:
            raise ValueError("Requested half-open replay interval is invalid or outside the dataset.")
        if not isinstance(starting_equity, Decimal):
            raise TypeError("starting_equity must be Decimal.")
        if not starting_equity.is_finite() or starting_equity <= 0:
            raise ValueError("starting_equity must be finite and positive.")
        for value, name in ((trading_brain_contract_version, "trading_brain_contract_version"),
                            (strategy_configuration_version, "strategy_configuration_version"),
                            (model_configuration_version, "model_configuration_version"),
                            (execution_cost_configuration_id, "execution_cost_configuration_id")):
            _text(value, name)
        if isinstance(random_seed, bool) or not isinstance(random_seed, int):
            raise TypeError("random_seed must be an integer.")
        parts = ("backtest-run-v1", dataset.dataset_id, dataset.fingerprint,
                          trading_brain_contract_version, strategy_configuration_version,
                          model_configuration_version, dataset.symbol,
                          ",".join(t.value for t in dataset.timeframes), start.isoformat(),
                          end.isoformat(), _canonical_decimal(starting_equity),
                          execution_cost_configuration_id, str(random_seed),
                          runtime.python_version, runtime.implementation, runtime.platform,
                          runtime.application_version, "PAPER_SIMULATION", "false")
        performance_sample_type = "OUT_OF_SAMPLE" if performance_objective_id != "NONE" else "UNSPECIFIED"
        if (risk_reward_policy_id, performance_objective_id) != ("CANONICAL_MIN_RR_V1", "NONE"):
            parts += (risk_reward_policy_id, performance_objective_id,
                      performance_sample_type)
        identity = _hash(parts)
        return cls(identity, dataset.dataset_id, dataset.fingerprint,
                   trading_brain_contract_version, strategy_configuration_version,
                   model_configuration_version, dataset.symbol, dataset.timeframes,
                   start, end, starting_equity, execution_cost_configuration_id,
                   random_seed, runtime, "PAPER_SIMULATION", False,
                   risk_reward_policy_id, performance_objective_id,
                   performance_sample_type)
