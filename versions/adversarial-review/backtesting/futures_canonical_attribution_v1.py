"""Independent ES/NQ canonical evaluation attribution and evidence gates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from backtesting.futures_canonical_history_v1 import read_futures_canonical_history
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket


VERSION = "futures-canonical-attribution-v1"
MINIMUM_FINALIZED_TRADES = 200


class FuturesCanonicalAttributionError(RuntimeError):
    pass


def _bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class FuturesCanonicalAttributionV1:
    attribution_id: str
    market: FuturesCanonicalMarket
    history_event_count: int
    evaluation_outcome_counts: tuple[tuple[str, int], ...]
    unique_lane_count: int
    unique_dataset_count: int
    latest_evaluated_at: str | None
    history_head_event_id: str | None
    history_fingerprint: str
    finalized_trade_count: int
    minimum_finalized_trades_required: int
    minimum_sample_met: bool
    finalized_accounting_available: bool
    untouched_oos_eligible: bool
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION

    def as_dict(self, *, include_id: bool = True) -> dict:
        result = {"schema_version": VERSION, "market": self.market.value,
            "history_event_count": self.history_event_count,
            "evaluation_outcome_counts": dict(self.evaluation_outcome_counts),
            "unique_lane_count": self.unique_lane_count,
            "unique_dataset_count": self.unique_dataset_count,
            "latest_evaluated_at": self.latest_evaluated_at,
            "history_head_event_id": self.history_head_event_id,
            "history_fingerprint": self.history_fingerprint,
            "finalized_trade_count": self.finalized_trade_count,
            "evidence_gate": {
                "minimum_finalized_trades_required": self.minimum_finalized_trades_required,
                "minimum_sample_met": self.minimum_sample_met,
                "finalized_accounting_available": self.finalized_accounting_available,
                "untouched_oos_eligible": self.untouched_oos_eligible,
            }, "advisory_only": True, "paper_execution_permitted": False,
            "live_trading_permitted": False, "trading_authority": False}
        if include_id:
            result["attribution_id"] = self.attribution_id
        return result


def evaluate_futures_canonical_attribution(
    history_root, *, market: FuturesCanonicalMarket,
    minimum_finalized_trades: int = MINIMUM_FINALIZED_TRADES,
) -> FuturesCanonicalAttributionV1:
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ attribution market required")
    if type(minimum_finalized_trades) is not int or minimum_finalized_trades < 1:
        raise FuturesCanonicalAttributionError("minimum finalized trades must be positive")
    history = read_futures_canonical_history(history_root, market=market)
    counts = Counter(event.latest_outcome for event in history)
    count_items = tuple(sorted(counts.items()))
    lanes = {event.lane_id for event in history}
    datasets = {event.dataset_fingerprint for event in history}
    head = history[-1].event_id if history else None
    history_fingerprint = hashlib.sha256("\x1f".join(
        event.event_id for event in history).encode("ascii")).hexdigest()
    latest = (history[-1].evaluated_at.isoformat(timespec="microseconds")
              .replace("+00:00", "Z")) if history else None

    # Evaluation history contains decisions, not closed-trade accounting.  No
    # trade is inferred from CANDIDATE/ARMED/etc.; a later accounting-binding
    # milestone must supply those immutable facts.
    finalized_trade_count = 0
    minimum_met = finalized_trade_count >= minimum_finalized_trades
    finalized_accounting_available = False
    untouched_oos = minimum_met and finalized_accounting_available
    values = {"schema_version": VERSION, "market": market.value,
        "history_event_count": len(history),
        "evaluation_outcome_counts": dict(count_items),
        "unique_lane_count": len(lanes), "unique_dataset_count": len(datasets),
        "latest_evaluated_at": latest, "history_head_event_id": head,
        "history_fingerprint": history_fingerprint,
        "finalized_trade_count": finalized_trade_count,
        "evidence_gate": {"minimum_finalized_trades_required": minimum_finalized_trades,
            "minimum_sample_met": minimum_met,
            "finalized_accounting_available": finalized_accounting_available,
            "untouched_oos_eligible": untouched_oos},
        "advisory_only": True, "paper_execution_permitted": False,
        "live_trading_permitted": False, "trading_authority": False}
    identity = hashlib.sha256(_bytes(values)).hexdigest()
    return FuturesCanonicalAttributionV1(identity, market, len(history), count_items,
        len(lanes), len(datasets), latest, head, history_fingerprint,
        finalized_trade_count, minimum_finalized_trades, minimum_met,
        finalized_accounting_available, untouched_oos)


def write_futures_canonical_attribution(
    history_root, output_root, *, market: FuturesCanonicalMarket,
    minimum_finalized_trades: int = MINIMUM_FINALIZED_TRADES,
) -> Path:
    summary = evaluate_futures_canonical_attribution(history_root, market=market,
        minimum_finalized_trades=minimum_finalized_trades)
    root = Path(output_root).absolute() / market.value
    if root.exists() and (not root.is_dir() or root.is_symlink()):
        raise FuturesCanonicalAttributionError("attribution output root is unsafe")
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{summary.attribution_id}.json"
    raw = _bytes(summary.as_dict()) + b"\n"
    if target.exists():
        if not target.is_file() or target.is_symlink() or target.read_bytes() != raw:
            raise FuturesCanonicalAttributionError("attribution identity collision")
    else:
        with target.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    pointer = {"schema_version": "futures-canonical-attribution-latest-v1",
        "market": market.value, "attribution_file": target.name,
        "attribution_sha256": hashlib.sha256(raw).hexdigest(),
        "attribution_id": summary.attribution_id, "trading_authority": False}
    temporary = root / f".latest.{os.getpid()}.tmp"
    temporary.write_bytes(_bytes(pointer) + b"\n")
    os.replace(temporary, root / "latest.json")
    return target


def assert_distinct_futures_attributions(
    es: FuturesCanonicalAttributionV1, nq: FuturesCanonicalAttributionV1
) -> None:
    if (es.market, nq.market) != (FuturesCanonicalMarket.ES, FuturesCanonicalMarket.NQ):
        raise FuturesCanonicalAttributionError("expected ordered ES and NQ attributions")
    if es.attribution_id == nq.attribution_id:
        raise FuturesCanonicalAttributionError("ES and NQ attribution identities collided")

