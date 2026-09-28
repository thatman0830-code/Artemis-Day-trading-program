"""Canonical advisory replay for an independent NinjaTrader historical export."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib

from backtesting.ninjatrader_canonical_smoke_v1 import _evaluate_once
from backtesting.ninjatrader_historical_export_v1 import NinjaTraderHistoricalExportV1

VERSION = "ninjatrader-export-canonical-replay-v1"


@dataclass(frozen=True)
class NinjaTraderExportCanonicalReplayV1:
    report_id: str; market: object; source_sha256: str; dataset_fingerprint: str
    source_bar_count: int; evaluated_batch_count: int; outcome_counts: tuple
    latest_outcome: str; latest_setup_fact_id: str
    deterministic_repeat_verified: bool = True; cross_source_equivalence_claimed: bool = False
    advisory_only: bool = True; paper_execution_permitted: bool = False
    trading_authority: bool = False; schema_version: str = VERSION


def evaluate_ninjatrader_export(*, evidence, specification_id, as_of):
    if not isinstance(evidence, NinjaTraderHistoricalExportV1) or evidence.historical_replay_eligible is not True or evidence.trading_authority is not False:
        raise ValueError("verified independent NinjaTrader export required")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() != timedelta(0) or as_of < evidence.latest_close_utc:
        raise ValueError("valid UTC evaluation time required")
    class View: pass
    view = View(); view.dataset = evidence.dataset; view.market = evidence.market; view.chain_head_sha256 = evidence.source_sha256
    first = _evaluate_once(evidence=view, minimum_tick=Decimal("0.25"), specification_id=specification_id, as_of=as_of)
    second = _evaluate_once(evidence=view, minimum_tick=Decimal("0.25"), specification_id=specification_id, as_of=as_of)
    if first != second: raise ValueError("independent export replay is nondeterministic")
    _, _, _, batches, counts, outcome, setup_id, _ = first
    identity = hashlib.sha256("\x1f".join((VERSION, evidence.market.value, evidence.source_sha256, evidence.dataset.fingerprint, specification_id, str(batches), outcome, setup_id)).encode()).hexdigest()
    return NinjaTraderExportCanonicalReplayV1(identity, evidence.market, evidence.source_sha256, evidence.dataset.fingerprint, evidence.record_count, batches, counts, outcome, setup_id)
