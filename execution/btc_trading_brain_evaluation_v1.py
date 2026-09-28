"""Run and persist an advisory-only canonical Trading Brain evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.orchestrator import EvaluationOutcome, TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from execution.btc_archive_dataset_source_v1 import BTCArchiveDatasetV1
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION


VERSION = "btc-trading-brain-evaluation-v1"
CALCULATION_VERSION = "canonical-live-archive-advisory-v1"


class BTCTradingBrainEvaluationError(RuntimeError):
    pass


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


@dataclass(frozen=True, slots=True)
class BTCTradingBrainEvaluationV1:
    dataset_id: str
    dataset_fingerprint: str
    source_bundle_id: str
    instrument_specification_id: str
    minimum_tick: str
    run_id: str
    replay_checkpoint_id: str
    orchestration_checkpoint_id: str
    evaluated_batch_count: int
    outcome_counts: tuple[tuple[str, int], ...]
    latest_outcome: str
    latest_setup_fact_id: str
    active_request_ids: tuple[str, ...]
    report_id: str
    instrument_profile: InstrumentProfile = InstrumentProfile.BTC_LINEAR_PERPETUAL
    advisory_only: bool = True
    live_trading_permitted: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if (self.instrument_profile is not InstrumentProfile.BTC_LINEAR_PERPETUAL
                or self.advisory_only is not True or self.live_trading_permitted is not False
                or self.trading_authority is not False):
            raise BTCTradingBrainEvaluationError("evaluation cannot grant trading authority")
        expected = hashlib.sha256(_canonical(self.as_dict(include_id=False))).hexdigest()
        if self.report_id != expected:
            raise BTCTradingBrainEvaluationError("evaluation identity mismatch")

    def as_dict(self, *, include_id: bool = True) -> dict:
        value = {"schema_version": VERSION, "dataset_id": self.dataset_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "source_bundle_id": self.source_bundle_id,
            "instrument_specification_id": self.instrument_specification_id,
            "minimum_tick": self.minimum_tick, "run_id": self.run_id,
            "replay_checkpoint_id": self.replay_checkpoint_id,
            "orchestration_checkpoint_id": self.orchestration_checkpoint_id,
            "evaluated_batch_count": self.evaluated_batch_count,
            "outcome_counts": dict(self.outcome_counts),
            "latest_outcome": self.latest_outcome,
            "latest_setup_fact_id": self.latest_setup_fact_id,
            "active_request_ids": list(self.active_request_ids),
            "instrument_profile": self.instrument_profile.value,
            "advisory_only": True, "live_trading_permitted": False,
            "trading_authority": False}
        if include_id:
            value["report_id"] = self.report_id
        return value


def evaluate_btc_trading_brain(*, source: BTCArchiveDatasetV1,
        minimum_tick: Decimal, instrument_specification_id: str) -> BTCTradingBrainEvaluationV1:
    if (not isinstance(source, BTCArchiveDatasetV1)
            or source.instrument_profile is not InstrumentProfile.BTC_LINEAR_PERPETUAL
            or source.trading_authority is not False):
        raise BTCTradingBrainEvaluationError("verified advisory dataset source is required")
    if (not isinstance(minimum_tick, Decimal) or not minimum_tick.is_finite()
            or minimum_tick <= 0):
        raise BTCTradingBrainEvaluationError("minimum_tick must be a positive exact Decimal")
    if not isinstance(instrument_specification_id, str) or len(instrument_specification_id) != 64:
        raise BTCTradingBrainEvaluationError("instrument specification identity is required")
    if any(char not in "0123456789abcdef" for char in instrument_specification_id):
        raise BTCTradingBrainEvaluationError("instrument specification identity is invalid")
    dataset = source.dataset
    manifest = DatasetManifest.from_dataset(dataset, symbol="BTC",
        created_at=source.manifest_updated_at,
        configuration_id=hashlib.sha256((VERSION + source.bundle_id).encode()).hexdigest())
    run = BacktestRunManifest.create(dataset=manifest,
        trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
        strategy_configuration_version="canonical-trading-brain-v1",
        model_configuration_version="canonical-auto-requests-v1",
        replay_start_inclusive=manifest.interval_start_inclusive,
        replay_end_exclusive=manifest.interval_end_exclusive,
        starting_equity=Decimal("100000"),
        execution_cost_configuration_id="advisory-no-execution-v1", random_seed=0,
        runtime=RuntimeFacts("deterministic", "python", "offline",
                             "btc-trading-brain-evaluation-v1"))
    replay = DeterministicReplay(dataset=dataset, run=run)
    engine = TradingBrainEvaluationOrchestrator(dataset=dataset, run=run,
        minimum_tick=minimum_tick, calculation_version=CALCULATION_VERSION,
        account_timezone="UTC", canonical_mode=True,
        enabled_prior_period_reference_types=("PDH", "PDL"))
    state = engine.initial_state()
    for publication in replay:
        state = engine.evaluate(publication=publication, state=state).state
    replay_checkpoint = replay.checkpoint()
    orchestration_checkpoint = engine.checkpoint(
        state=state, replay_checkpoint=replay_checkpoint)
    engine.validate_resume(state=state, checkpoint=orchestration_checkpoint,
                           replay_checkpoint=replay_checkpoint)
    counts = tuple((outcome.value, sum(item.outcome is outcome for item in state.batch_results))
                   for outcome in EvaluationOutcome)
    latest = state.batch_results[-1]
    active_ids = tuple(sorted(item.id for item in state.active_requests))
    values = {"schema_version": VERSION, "dataset_id": dataset.dataset_id,
        "dataset_fingerprint": dataset.fingerprint, "source_bundle_id": source.bundle_id,
        "instrument_specification_id": instrument_specification_id,
        "minimum_tick": format(minimum_tick, "f"), "run_id": run.id,
        "replay_checkpoint_id": replay_checkpoint.event_sequence_id,
        "orchestration_checkpoint_id": orchestration_checkpoint.id,
        "evaluated_batch_count": len(state.batch_results), "outcome_counts": dict(counts),
        "latest_outcome": latest.outcome.value,
        "latest_setup_fact_id": latest.setup_fact.id,
        "active_request_ids": list(active_ids), "advisory_only": True,
        "instrument_profile": InstrumentProfile.BTC_LINEAR_PERPETUAL.value,
        "live_trading_permitted": False, "trading_authority": False}
    report_id = hashlib.sha256(_canonical(values)).hexdigest()
    return BTCTradingBrainEvaluationV1(dataset.dataset_id, dataset.fingerprint,
        source.bundle_id, instrument_specification_id, format(minimum_tick, "f"), run.id,
        replay_checkpoint.event_sequence_id, orchestration_checkpoint.id,
        len(state.batch_results), counts, latest.outcome.value, latest.setup_fact.id,
        active_ids, report_id, InstrumentProfile.BTC_LINEAR_PERPETUAL, True, False, False)


def persist_btc_trading_brain_evaluation(report: BTCTradingBrainEvaluationV1,
                                         path) -> Path:
    if not isinstance(report, BTCTradingBrainEvaluationV1):
        raise BTCTradingBrainEvaluationError("canonical evaluation report is required")
    target = Path(path).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical(report.as_dict())
    if target.exists():
        if not target.is_file() or target.is_symlink():
            raise BTCTradingBrainEvaluationError("evaluation target is not a plain file")
        if target.read_bytes() == payload:
            return target
        raise BTCTradingBrainEvaluationError("conflicting evaluation already exists")
    temporary = target.with_name(target.name + ".tmp")
    if temporary.exists():
        raise BTCTradingBrainEvaluationError("stale evaluation temporary exists")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return target
