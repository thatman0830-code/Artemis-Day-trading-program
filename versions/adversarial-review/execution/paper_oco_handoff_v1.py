"""Create-only replacement preparation, not activation or order submission."""
import json
import os
from datetime import timedelta

from backtesting.execution_accounting_v2.ohlc_execution import OHLCBarV2
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_oco_checkpoint_v1 import _unique
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.paper_oco_initial_v1 import _pack, _unpack
from execution.paper_oco_replacement_v1 import review_protective_replacement


MAX_BYTES = 16 * 1024 * 1024
_INPUTS = {"expected_checkpoint_id", "accounting", "stop", "target", "source_bar", "reviewed_at", "gap_bars"}


def _review(predecessor, inputs):
    if type(inputs) is not dict or set(inputs) != _INPUTS:
        raise PaperOCOError("invalid handoff inputs")
    proposal = {key: value for key, value in inputs.items() if key != "gap_bars"}
    review = review_protective_replacement(predecessor=predecessor, **proposal)
    _, old = predecessor.load()
    start = min(fill.fill_time for fill in old.pending.evaluation.fills)
    # Include the entire minute containing the fill. OHLC cannot attribute a
    # touch within that minute to before/after the fill, so ambiguous touches reject.
    cursor = start.replace(second=0, microsecond=0)
    bars = inputs["gap_bars"]
    if type(bars) is not tuple or not 1 <= len(bars) <= 1000:
        raise PaperOCOError("bounded contiguous gap evidence required")
    identities = set()
    instrument = inputs["accounting"].instrument
    for bar in bars:
        if type(bar) is not OHLCBarV2:
            raise PaperOCOError("typed gap bar required")
        bar.__post_init__()
        if (bar.open_time != cursor or bar.close_time != cursor + timedelta(minutes=1)
                or bar.bar_id in identities or bar.available_at > inputs["reviewed_at"]
                or bar.source_version != inputs["source_bar"].source_version
                or (bar.market, bar.instrument_id, bar.contract_id) !=
                   (instrument.market, instrument.instrument_id, instrument.contract_id)
                or any(getattr(bar, flag) is not True for flag in
                       ("finalized", "session_eligible", "data_quality_valid", "contract_eligible"))
                or bar.open_time < instrument.effective_from
                or (instrument.effective_to is not None and bar.close_time > instrument.effective_to)):
            raise PaperOCOError("gap evidence is incomplete, ineligible or mismatched")
        if bar.low <= inputs["stop"].stop_price or bar.high >= inputs["target"].limit_price:
            raise PaperOCOError("protective price touched during blocked interval")
        identities.add(bar.bar_id)
        cursor = bar.close_time
    if bars[-1] != inputs["source_bar"]:
        raise PaperOCOError("gap evidence must end at exact replacement source")
    return dict(review_id=review.review_id, covered_from=start.isoformat(),
        covered_until=cursor.isoformat(), reviewed_at=inputs["reviewed_at"].isoformat(),
        uncovered_tail=cursor < inputs["reviewed_at"], requires_runtime_revalidation=True)


class PaperOCOHandoffStoreV1:
    """One immutable prepared proposal per predecessor directory.

    Uses the predecessor journal lock. Evidence and intents are persisted together;
    preparation never creates a successor coordinator or changes predecessor state.
    """

    def __init__(self, predecessor):
        self.predecessor = predecessor
        self.path = predecessor.journal.root / "oco-replacement-prepared.json"

    def _safe(self):
        self.predecessor.journal._safe()
        if self.path.is_symlink():
            raise PaperOCOError("linked handoff file")
        if self.path.exists() and (not self.path.is_file() or
                getattr(self.path.lstat(), "st_file_attributes", 0) & 0x400):
            raise PaperOCOError("unsafe handoff file")

    def load(self):
        self._safe()
        with self.path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if not raw or len(raw) > MAX_BYTES:
            raise PaperOCOError("handoff size limit")
        try:
            doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(PaperOCOError("invalid numeric constant")))
            if (type(doc) is not dict or set(doc) != {"version", "handoff_id", "inputs", "assessment", "state", "trading_authority", "rearm_authorized"}
                    or doc["version"] != "paper-oco-handoff-v1" or doc["state"] != "PREPARED_ONLY"
                    or doc["trading_authority"] is not False or doc["rearm_authorized"] is not False
                    or type(doc["inputs"]) is not dict or set(doc["inputs"]) != _INPUTS):
                raise PaperOCOError("invalid handoff schema or authority")
            inputs = {key: _unpack(value) for key, value in doc["inputs"].items()}
            assessment = _review(self.predecessor, inputs)
            if (doc["assessment"] != assessment or doc["handoff_id"] !=
                    canonical_fingerprint("paper-oco-handoff-v1", inputs, assessment)):
                raise PaperOCOError("handoff evidence mismatch")
            return doc
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            raise PaperOCOError("invalid prepared handoff") from exc

    def prepare(self, **inputs):
        journal = self.predecessor.journal
        journal._acquire()
        try:
            self._safe()
            assessment = _review(self.predecessor, inputs)
            identity = canonical_fingerprint("paper-oco-handoff-v1", inputs, assessment)
            if self.path.exists():
                existing = self.load()
                if existing["handoff_id"] != identity:
                    raise PaperOCOError("conflicting replacement already prepared")
                with self.path.open("r+b") as stream:
                    os.fsync(stream.fileno())
                return existing
            doc = dict(version="paper-oco-handoff-v1", handoff_id=identity,
                inputs={key: _pack(value) for key, value in inputs.items()}, assessment=assessment,
                state="PREPARED_ONLY", trading_authority=False, rearm_authorized=False)
            raw = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            if len(raw) > MAX_BYTES:
                raise PaperOCOError("handoff size limit")
            with self.path.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            return self.load()
        finally:
            journal.lock.unlink()
