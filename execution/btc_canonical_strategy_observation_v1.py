"""Read-only canonical Trading Brain observation over immutable BTC snapshots."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import platform
from pathlib import Path
import sys

from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import GapPolicy, normalize_historical_candle, validate_dataset
from backtesting.orchestrator import (
    BatchEvaluationResult, EvaluationOutcome, TradingBrainEvaluationOrchestrator,
)
from backtesting.replay import DeterministicReplay
from execution.btc_archive_snapshot_source_v1 import (
    BTCArchiveSnapshotV1, read_btc_archive_snapshot,
)
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION
from strategy.trading_brain.owner_policies import OWNER_MIN_RR_POLICY_ID, minimum_rr_policy

VERSION="btc-canonical-strategy-observation-v1"
ACTIONABLE=(EvaluationOutcome.ARMED_CONTINUATION,EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL)
FIELDS=("symbol","timeframe","open_time","close_time","open","high","low","close","volume","is_closed")


class BTCCanonicalStrategyObservationError(RuntimeError):pass


def _id(*values):
    return hashlib.sha256("\x1f".join(str(value) for value in values).encode()).hexdigest()


def _utc(text):
    if not isinstance(text,str):raise BTCCanonicalStrategyObservationError("candle time is invalid")
    try:value=datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError as exc:raise BTCCanonicalStrategyObservationError("candle time is invalid")from exc
    if value.tzinfo is None or value.utcoffset()!=timedelta(0):
        raise BTCCanonicalStrategyObservationError("candle time is not UTC")
    return value.astimezone(timezone.utc)


def _decimal(text,field):
    try:value=Decimal(text)
    except (InvalidOperation,TypeError) as exc:
        raise BTCCanonicalStrategyObservationError(f"{field} is invalid")from exc
    if not value.is_finite():raise BTCCanonicalStrategyObservationError(f"{field} is invalid")
    return value


def _candles(path,*,dataset_id,expected_timeframe):
    try:
        with Path(path).open("r",encoding="utf-8-sig",newline="")as stream:
            reader=csv.DictReader(stream)
            if tuple(reader.fieldnames or ())!=FIELDS:
                raise BTCCanonicalStrategyObservationError("snapshot fields are invalid")
            rows=tuple(reader)
    except OSError as exc:raise BTCCanonicalStrategyObservationError("snapshot is unreadable")from exc
    if not rows:raise BTCCanonicalStrategyObservationError("snapshot has no candles")
    values=[]
    for row in rows:
        if row["symbol"]!="BTC"or row["timeframe"]!=expected_timeframe or row["is_closed"]!="true":
            raise BTCCanonicalStrategyObservationError("snapshot candle identity is invalid")
        values.append(normalize_historical_candle({
            "symbol":row["symbol"],"timeframe":row["timeframe"],
            "open_time":_utc(row["open_time"]),"close_time":_utc(row["close_time"]),
            "open":_decimal(row["open"],"open"),"high":_decimal(row["high"],"high"),
            "low":_decimal(row["low"],"low"),"close":_decimal(row["close"],"close"),
            "volume":_decimal(row["volume"],"volume")if row["volume"] else None,
            "is_closed":True},dataset_id=dataset_id,schema_version="historical-candle-v1",
            source="hyperliquid-public-mainnet",exchange="hyperliquid"))
    return tuple(values)


@dataclass(frozen=True,slots=True)
class BTCCanonicalStrategyObservationV1:
    one_minute: BTCArchiveSnapshotV1
    five_minute: BTCArchiveSnapshotV1
    result: BatchEvaluationResult
    candle_count: int
    actionable: bool
    observation_id: str
    trading_authority: bool=False

    def __post_init__(self):
        expected_actionable=(self.result.outcome in ACTIONABLE
            and self.result.setup_fact.final_qualification is not None
            and self.result.setup_fact.entry_zone is not None)
        expected=_id(VERSION,self.one_minute.snapshot_id,self.five_minute.snapshot_id,
            self.result.id,self.candle_count,expected_actionable,False)
        if (self.one_minute.manifest_sha256!=self.five_minute.manifest_sha256
                or self.one_minute.archive_id!=self.five_minute.archive_id
                or self.one_minute.manifest_updated_at!=self.five_minute.manifest_updated_at
                or self.actionable is not expected_actionable or self.observation_id!=expected
                or self.trading_authority is not False):
            raise BTCCanonicalStrategyObservationError("strategy observation identity is invalid")


def _observation(one,five,result,candle_count):
    actionable=(result.outcome in ACTIONABLE and result.setup_fact.final_qualification is not None
        and result.setup_fact.entry_zone is not None)
    identity=_id(VERSION,one.snapshot_id,five.snapshot_id,result.id,candle_count,actionable,False)
    return BTCCanonicalStrategyObservationV1(one,five,result,candle_count,actionable,identity,False)


def _observe_snapshots(*,one,five,snapshot_root,as_of):
    if (one.manifest_sha256,one.archive_id,one.manifest_updated_at)!=(
            five.manifest_sha256,five.archive_id,five.manifest_updated_at):
        raise BTCCanonicalStrategyObservationError("strategy streams are not from one manifest")
    dataset_id=_id(VERSION,one.reference.sha256,five.reference.sha256)
    root=Path(snapshot_root).absolute()
    candles=_candles(root/one.reference.relative_path,dataset_id=dataset_id,expected_timeframe="1m")
    candles+=_candles(root/five.reference.relative_path,dataset_id=dataset_id,expected_timeframe="5m")
    ordered=tuple(sorted(candles,key=lambda item:(item.open_time,item.symbol,item.timeframe.value,item.id)))
    dataset=validate_dataset(ordered,dataset_id=dataset_id,schema_version="historical-candle-v1",
        source="hyperliquid-public-mainnet",exchange="hyperliquid",gap_policy=GapPolicy.RECORD,
        validation_time=as_of)
    manifest=DatasetManifest.from_dataset(dataset,symbol="BTC",created_at=as_of,
        configuration_id=VERSION)
    run=BacktestRunManifest.create(dataset=manifest,
        trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
        strategy_configuration_version=OWNER_MIN_RR_POLICY_ID,
        model_configuration_version=VERSION,replay_start_inclusive=manifest.interval_start_inclusive,
        replay_end_exclusive=manifest.interval_end_exclusive,starting_equity=Decimal("100"),
        execution_cost_configuration_id="btc-paper-economics-policy-v1",random_seed=0,
        runtime=RuntimeFacts(f"{sys.version_info.major}.{sys.version_info.minor}",
            platform.python_implementation(),platform.system(),VERSION),
        risk_reward_policy_id=OWNER_MIN_RR_POLICY_ID)
    engine=TradingBrainEvaluationOrchestrator(dataset=dataset,run=run,minimum_tick=Decimal("1"),
        calculation_version=VERSION,account_timezone="UTC",
        risk_reward_policy=minimum_rr_policy(OWNER_MIN_RR_POLICY_ID),canonical_mode=True,
        enabled_prior_period_reference_types=())
    state=engine.initial_state();last=None
    for publication in DeterministicReplay(dataset=dataset,run=run):
        commit=engine.evaluate(publication=publication,state=state,request=None)
        state,last=commit.state,commit.result
    if last is None:raise BTCCanonicalStrategyObservationError("strategy replay produced no observation")
    return _observation(one,five,last,len(ordered))


def observe_btc_canonical_strategy(*,archive_root,snapshot_root,as_of):
    """Replay bounded exact 1m/5m snapshots and return only the newest canonical fact."""
    one=read_btc_archive_snapshot(archive_root,timeframe="1m",as_of=as_of,snapshot_root=snapshot_root)
    five=read_btc_archive_snapshot(archive_root,timeframe="5m",as_of=as_of,snapshot_root=snapshot_root)
    return _observe_snapshots(one=one,five=five,snapshot_root=snapshot_root,as_of=as_of)


class BTCCanonicalStrategyObserverV1:
    """In-process cache: unchanged immutable snapshots never replay twice."""
    def __init__(self,*,archive_root,snapshot_root):
        self.archive_root=Path(archive_root).absolute()
        self.snapshot_root=Path(snapshot_root).absolute()
        self._key=None;self._observation=None

    def observe(self,*,as_of):
        one=read_btc_archive_snapshot(self.archive_root,timeframe="1m",as_of=as_of,
            snapshot_root=self.snapshot_root)
        five=read_btc_archive_snapshot(self.archive_root,timeframe="5m",as_of=as_of,
            snapshot_root=self.snapshot_root)
        key=(one.reference.sha256,five.reference.sha256)
        if key==self._key:
            return _observation(one,five,self._observation.result,
                self._observation.candle_count)
        observation=_observe_snapshots(one=one,five=five,snapshot_root=self.snapshot_root,
            as_of=as_of)
        self._key,self._observation=key,observation
        return observation
