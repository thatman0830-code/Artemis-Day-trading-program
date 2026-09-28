from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from typing import Iterator, Mapping

from backtesting.manifests import BacktestRunManifest
from backtesting.market_data import CanonicalTimeframe, HistoricalCandle, HistoricalDataset
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION


class ReplayState(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a UTC timezone-aware datetime.")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _event_order(candle: HistoricalCandle) -> tuple[str, int, str, str]:
    return (candle.symbol, int(candle.timeframe.duration.total_seconds()),
            candle.timeframe.value, candle.id)


@dataclass(frozen=True)
class ReplayEvent:
    id: str
    batch_sequence: int
    event_sequence: int
    event_time: datetime
    candle_id: str
    dataset_id: str
    dataset_schema_version: str
    dataset_fingerprint: str
    run_id: str
    trading_brain_contract_version: str
    source: str
    exchange: str
    symbol: str
    timeframe: CanonicalTimeframe
    candle: HistoricalCandle


@dataclass(frozen=True)
class ReplayBatch:
    id: str
    sequence: int
    event_time: datetime
    events: tuple[ReplayEvent, ...]


@dataclass(frozen=True)
class VisibleStream:
    symbol: str
    timeframe: CanonicalTimeframe
    candles: tuple[HistoricalCandle, ...]
    latest_candle_id: str | None


@dataclass(frozen=True)
class AvailabilitySnapshot:
    id: str
    run_id: str
    dataset_id: str
    published_batch_id: str
    as_of: datetime
    streams: tuple[VisibleStream, ...]


@dataclass(frozen=True)
class ClockSnapshot:
    run_id: str
    state: ReplayState
    current_time: datetime
    next_batch_sequence: int
    published_batch_count: int
    total_batch_count: int
    exhausted: bool


@dataclass(frozen=True)
class ReplayPublication:
    batch: ReplayBatch
    availability: AvailabilitySnapshot
    clock: ClockSnapshot


@dataclass(frozen=True)
class ReplayCheckpoint:
    checkpoint_version: str
    dataset_id: str
    dataset_fingerprint: str
    run_id: str
    trading_brain_contract_version: str
    event_sequence_id: str
    state: ReplayState
    current_time: datetime
    next_batch_sequence: int
    last_published_batch_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_version": self.checkpoint_version,
            "dataset_id": self.dataset_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "run_id": self.run_id,
            "trading_brain_contract_version": self.trading_brain_contract_version,
            "event_sequence_id": self.event_sequence_id,
            "state": self.state.value,
            "current_time": _stamp(self.current_time),
            "next_batch_sequence": self.next_batch_sequence,
            "last_published_batch_id": self.last_published_batch_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayCheckpoint:
        required = {
            "checkpoint_version", "dataset_id", "dataset_fingerprint", "run_id",
            "trading_brain_contract_version", "event_sequence_id", "state",
            "current_time", "next_batch_sequence", "last_published_batch_id",
        }
        if set(value) != required:
            raise ValueError("Checkpoint fields are incomplete or unexpected.")
        try:
            current = datetime.fromisoformat(str(value["current_time"]).replace("Z", "+00:00"))
            state = ReplayState(value["state"])
        except (TypeError, ValueError) as error:
            raise ValueError("Checkpoint state or timestamp is invalid.") from error
        sequence = value["next_batch_sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("Checkpoint cursor must be a nonnegative integer.")
        last = value["last_published_batch_id"]
        if last is not None and (not isinstance(last, str) or not last):
            raise ValueError("Checkpoint last batch identity is invalid.")
        return cls(
            str(value["checkpoint_version"]), str(value["dataset_id"]),
            str(value["dataset_fingerprint"]), str(value["run_id"]),
            str(value["trading_brain_contract_version"]), str(value["event_sequence_id"]),
            state, _utc(current, "current_time"), sequence, last,
        )


class DeterministicReplay(Iterator[ReplayPublication]):
    """Phase 2 atomic closed-candle event clock. It never invokes strategy code."""

    CHECKPOINT_VERSION = "backtesting-replay-checkpoint-v1"

    def __init__(self, *, dataset: HistoricalDataset, run: BacktestRunManifest):
        self._validate_compatibility(dataset=dataset, run=run)
        self._dataset = dataset
        self._run = run
        self._batches = self._build_batches(dataset=dataset, run=run)
        self._event_sequence_id = _hash((
            "replay-sequence-v1", run.id, dataset.fingerprint,
            *(batch.id for batch in self._batches),
        ))
        self._streams = {
            (run.symbol, timeframe): [] for timeframe in run.timeframes
        }
        self._state = ReplayState.READY
        self._current_time = run.replay_start_inclusive
        self._cursor = 0

    @staticmethod
    def _validate_compatibility(*, dataset: HistoricalDataset,
                                run: BacktestRunManifest) -> None:
        if not isinstance(dataset, HistoricalDataset):
            raise TypeError("dataset must be a Phase 1 validated dataset.")
        if not isinstance(run, BacktestRunManifest):
            raise TypeError("run must be an immutable Phase 1 run manifest.")
        if run.trading_brain_contract_version != INTERFACE_CONTRACT_VERSION:
            raise ValueError("Run Trading Brain contract version is incompatible.")
        if (run.dataset_id, run.dataset_fingerprint, run.symbol) != (
                dataset.dataset_id, dataset.fingerprint, dataset.symbol):
            raise ValueError("Run and dataset identity/fingerprint/symbol mismatch.")
        available = {candle.timeframe for candle in dataset.candles}
        if not run.timeframes or any(timeframe not in available for timeframe in run.timeframes):
            raise ValueError("Run requests an unavailable dataset timeframe.")

    @classmethod
    def _build_batches(cls, *, dataset: HistoricalDataset,
                       run: BacktestRunManifest) -> tuple[ReplayBatch, ...]:
        eligible = tuple(candle for candle in dataset.candles
                         if candle.symbol == run.symbol
                         and candle.timeframe in run.timeframes
                         and run.replay_start_inclusive <= candle.close_time < run.replay_end_exclusive)
        grouped: dict[datetime, list[HistoricalCandle]] = {}
        for candle in eligible:
            grouped.setdefault(candle.close_time, []).append(candle)
        batches: list[ReplayBatch] = []
        for batch_sequence, event_time in enumerate(sorted(grouped)):
            ordered = tuple(sorted(grouped[event_time], key=_event_order))
            events: list[ReplayEvent] = []
            for event_sequence, candle in enumerate(ordered):
                event_id = _hash(("replay-event-v1", run.id, dataset.fingerprint,
                                  str(batch_sequence), str(event_sequence), candle.id,
                                  _stamp(event_time)))
                events.append(ReplayEvent(
                    event_id, batch_sequence, event_sequence, event_time, candle.id,
                    dataset.dataset_id, dataset.schema_version, dataset.fingerprint,
                    run.id, run.trading_brain_contract_version, dataset.source,
                    dataset.exchange, candle.symbol, candle.timeframe, candle,
                ))
            batch_id = _hash(("replay-batch-v1", run.id, dataset.fingerprint,
                              str(batch_sequence), _stamp(event_time),
                              *(event.id for event in events)))
            batches.append(ReplayBatch(batch_id, batch_sequence, event_time, tuple(events)))
        return tuple(batches)

    @property
    def clock(self) -> ClockSnapshot:
        return ClockSnapshot(
            self._run.id, self._state, self._current_time, self._cursor,
            self._cursor, len(self._batches), self._state is ReplayState.COMPLETED,
        )

    @property
    def event_sequence_id(self) -> str:
        return self._event_sequence_id

    def start(self) -> ClockSnapshot:
        if self._state is not ReplayState.READY:
            raise RuntimeError("Replay clock has already started.")
        self._state = ReplayState.ACTIVE if self._batches else ReplayState.COMPLETED
        return self.clock

    def _snapshot(self, batch: ReplayBatch) -> AvailabilitySnapshot:
        streams = tuple(
            VisibleStream(symbol, timeframe, tuple(candles), candles[-1].id if candles else None)
            for (symbol, timeframe), candles in sorted(
                self._streams.items(), key=lambda item: (item[0][0], int(item[0][1].duration.total_seconds()), item[0][1].value)
            )
        )
        identity = _hash(("availability-v1", self._run.id, batch.id,
                          *(f"{stream.symbol}:{stream.timeframe.value}:"
                            f"{','.join(c.id for c in stream.candles)}" for stream in streams)))
        return AvailabilitySnapshot(identity, self._run.id, self._dataset.dataset_id,
                                    batch.id, batch.event_time, streams)

    def advance(self) -> ReplayPublication:
        if self._state is ReplayState.READY:
            raise RuntimeError("Replay clock must be started before advancing.")
        if self._state is ReplayState.COMPLETED:
            raise RuntimeError("Replay is completed; no further batch may be published.")
        if self._cursor >= len(self._batches):
            raise RuntimeError("Replay cursor conflicts with the event sequence.")
        batch = self._batches[self._cursor]
        if batch.event_time < self._current_time:
            raise RuntimeError("Replay time cannot move backward.")

        # The complete timestamp group is installed before a snapshot or result
        # is returned, so no observer can see a partial same-time publication.
        additions: dict[tuple[str, CanonicalTimeframe], list[HistoricalCandle]] = {}
        for event in batch.events:
            additions.setdefault((event.symbol, event.timeframe), []).append(event.candle)
        for stream, candles in additions.items():
            self._streams[stream].extend(candles)

        self._cursor += 1
        self._current_time = batch.event_time
        if self._cursor == len(self._batches):
            self._state = ReplayState.COMPLETED
        availability = self._snapshot(batch)
        return ReplayPublication(batch, availability, self.clock)

    def _query(self, *, symbol: str, timeframe: CanonicalTimeframe,
               as_of: datetime, lookback: int | None) -> tuple[HistoricalCandle, ...]:
        timestamp = _utc(as_of, "as_of")
        if (symbol, timeframe) not in self._streams:
            raise ValueError("Unknown or out-of-scope symbol/timeframe stream.")
        if timestamp < self._run.replay_start_inclusive or timestamp >= self._run.replay_end_exclusive:
            raise ValueError("Query timestamp is outside the permitted half-open run scope.")
        if timestamp > self._current_time:
            raise ValueError("Query cannot access unpublished future replay time.")
        if lookback is not None and (isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 0):
            raise ValueError("lookback must be a nonnegative integer.")
        visible = tuple(c for c in self._streams[(symbol, timeframe)] if c.close_time <= timestamp)
        if lookback is None:
            return visible
        if lookback == 0:
            return ()
        return visible[-lookback:]

    def history(self, *, symbol: str, timeframe: CanonicalTimeframe,
                as_of: datetime) -> tuple[HistoricalCandle, ...]:
        return self._query(symbol=symbol, timeframe=timeframe, as_of=as_of, lookback=None)

    def lookback(self, *, symbol: str, timeframe: CanonicalTimeframe,
                 as_of: datetime, count: int) -> tuple[HistoricalCandle, ...]:
        return self._query(symbol=symbol, timeframe=timeframe, as_of=as_of, lookback=count)

    def latest(self, *, symbol: str, timeframe: CanonicalTimeframe,
               as_of: datetime) -> HistoricalCandle | None:
        values = self._query(symbol=symbol, timeframe=timeframe, as_of=as_of, lookback=1)
        return values[-1] if values else None

    def checkpoint(self) -> ReplayCheckpoint:
        last = self._batches[self._cursor - 1].id if self._cursor else None
        return ReplayCheckpoint(
            self.CHECKPOINT_VERSION, self._dataset.dataset_id,
            self._dataset.fingerprint, self._run.id,
            self._run.trading_brain_contract_version, self._event_sequence_id,
            self._state, self._current_time, self._cursor, last,
        )

    @classmethod
    def resume(cls, *, dataset: HistoricalDataset, run: BacktestRunManifest,
               checkpoint: ReplayCheckpoint) -> DeterministicReplay:
        if not isinstance(checkpoint, ReplayCheckpoint):
            raise TypeError("checkpoint must be an immutable ReplayCheckpoint.")
        replay = cls(dataset=dataset, run=run)
        if checkpoint.checkpoint_version != cls.CHECKPOINT_VERSION:
            raise ValueError("Checkpoint version is incompatible.")
        if (checkpoint.dataset_id, checkpoint.dataset_fingerprint, checkpoint.run_id,
            checkpoint.trading_brain_contract_version, checkpoint.event_sequence_id) != (
                dataset.dataset_id, dataset.fingerprint, run.id,
                run.trading_brain_contract_version, replay._event_sequence_id):
            raise ValueError("Checkpoint dataset/run/contract/event-sequence mismatch.")
        if checkpoint.next_batch_sequence > len(replay._batches):
            raise ValueError("Checkpoint cursor exceeds the event sequence.")
        expected_last = (replay._batches[checkpoint.next_batch_sequence - 1].id
                         if checkpoint.next_batch_sequence else None)
        if checkpoint.last_published_batch_id != expected_last:
            raise ValueError("Checkpoint last-published batch identity conflicts.")
        expected_time = (replay._batches[checkpoint.next_batch_sequence - 1].event_time
                         if checkpoint.next_batch_sequence else run.replay_start_inclusive)
        if checkpoint.current_time != expected_time:
            raise ValueError("Checkpoint clock position conflicts with its cursor.")
        expected_states = (
            {ReplayState.READY, ReplayState.ACTIVE}
            if checkpoint.next_batch_sequence == 0 and replay._batches
            else {ReplayState.READY, ReplayState.COMPLETED}
            if not replay._batches
            else {ReplayState.COMPLETED}
            if checkpoint.next_batch_sequence == len(replay._batches)
            else {ReplayState.ACTIVE}
        )
        if checkpoint.state not in expected_states:
            raise ValueError("Checkpoint state conflicts with its cursor.")
        for batch in replay._batches[:checkpoint.next_batch_sequence]:
            for event in batch.events:
                replay._streams[(event.symbol, event.timeframe)].append(event.candle)
        replay._cursor = checkpoint.next_batch_sequence
        replay._current_time = checkpoint.current_time
        replay._state = checkpoint.state
        return replay

    def __iter__(self) -> DeterministicReplay:
        return self

    def __next__(self) -> ReplayPublication:
        if self._state is ReplayState.READY:
            self.start()
        if self._state is ReplayState.COMPLETED:
            raise StopIteration
        return self.advance()
