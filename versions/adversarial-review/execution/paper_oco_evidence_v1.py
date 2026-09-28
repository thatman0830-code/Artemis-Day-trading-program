"""Content-addressed action evidence for offline protective journal replay."""
from dataclasses import fields
import json
import os
import re

from backtesting.execution_accounting_v2.accounting import InstrumentAccountingLedgerV2
from backtesting.execution_accounting_v2.ohlc_execution import OHLCBarV2
from backtesting.execution_accounting_v2.order_ledger import OrderLedgerEventV2, LedgerEventKind
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint, _utc
from execution.paper_oco_checkpoint_v1 import PaperOCOCheckpointV1, _unique
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.paper_performance_checkpoint_v1 import _encode, _decode


MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


def _validate(payload):
    if type(payload) is not dict or set(payload) not in (
            {"accounting"}, {"accounting", "bar", "evaluated_at"}, {"accounting", "cancellations"}):
        raise PaperOCOError("invalid protective evidence fields")
    if type(payload["accounting"]) is not InstrumentAccountingLedgerV2:
        raise PaperOCOError("accounting ledger required")
    payload["accounting"].verify_integrity()
    if "cancellations" in payload:
        events = payload["cancellations"]
        if type(events) is not tuple or not 1 <= len(events) <= 4:
            raise PaperOCOError("bounded cancellation tuple required")
        for event in events:
            if (type(event) is not OrderLedgerEventV2
                    or event.kind not in (LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL)
                    or event.replacement_intent is not None or event.fill_quantity is not None):
                raise PaperOCOError("cancellation-only evidence required")
            event.__post_init__()
    if "bar" in payload:
        if type(payload["bar"]) is not OHLCBarV2:
            raise PaperOCOError("OHLC bar required")
        payload["bar"].__post_init__()
        if any(type(getattr(payload["bar"], name)) is not bool for name in
               ("finalized", "session_eligible", "data_quality_valid", "contract_eligible")):
            raise PaperOCOError("bar eligibility flags must be booleans")
        _utc(payload["evaluated_at"], "evaluated_at")


class PaperOCOEvidenceStoreV1:
    """Immutable create-only files. Partial files block, never overwrite/repair.

    Shares an owner-controlled directory with the journal. No directory scan,
    pickle, dynamic imports, or mutation of the accounting codec's type registry.
    """

    def __init__(self, journal):
        self.journal = journal

    def _path(self, identity):
        if type(identity) is not str or not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise PaperOCOError("invalid evidence identity")
        self.journal._safe()
        path = self.journal.root / ("oco-evidence-" + identity + ".json")
        if path.is_symlink():
            raise PaperOCOError("linked evidence path")
        if path.exists():
            info = path.lstat()
            if not path.is_file() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise PaperOCOError("unsafe evidence path")
        return path

    def get(self, identity):
        path = self._path(identity)
        with path.open("rb") as stream:
            raw = stream.read(MAX_EVIDENCE_BYTES + 1)
        if not raw or len(raw) > MAX_EVIDENCE_BYTES:
            raise PaperOCOError("invalid evidence size")
        try:
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(PaperOCOError("invalid number")))
            if (type(document) is not dict or set(document) != {"version", "evidence_id", "payload", "trading_authority"}
                    or document["version"] != "paper-oco-evidence-v1"
                    or document["evidence_id"] != identity or document["trading_authority"] is not False):
                raise PaperOCOError("invalid evidence envelope")
            encoded = document["payload"]
            if type(encoded) is not dict or set(encoded) not in (
                    {"accounting"}, {"accounting", "bar", "evaluated_at"}, {"accounting", "cancellations"}):
                raise PaperOCOError("invalid evidence payload")
            payload = {"accounting": _decode(encoded["accounting"])}
            if "cancellations" in encoded:
                raw_events = encoded["cancellations"]
                if type(raw_events) is not list or not 1 <= len(raw_events) <= 4:
                    raise PaperOCOError("invalid cancellation list")
                events = []
                for raw_event in raw_events:
                    if type(raw_event) is not dict or set(raw_event) != {f.name for f in fields(OrderLedgerEventV2)}:
                        raise PaperOCOError("invalid cancellation schema")
                    values = {k: _decode(v) for k, v in raw_event.items() if k != "kind"}
                    events.append(OrderLedgerEventV2(**values, kind=LedgerEventKind(raw_event["kind"])))
                payload["cancellations"] = tuple(events)
            if "bar" in encoded:
                bar = encoded["bar"]
                if type(bar) is not dict or set(bar) != {f.name for f in fields(OHLCBarV2)}:
                    raise PaperOCOError("invalid bar schema")
                payload.update(bar=OHLCBarV2(**{k: _decode(v) for k, v in bar.items()}),
                    evaluated_at=_decode(encoded["evaluated_at"]))
            _validate(payload)
            if canonical_fingerprint(payload) != identity:
                raise PaperOCOError("evidence fingerprint mismatch")
            return payload
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise PaperOCOError("invalid protective evidence") from exc

    def put(self, payload):
        _validate(payload)
        identity = canonical_fingerprint(payload)
        path = self._path(identity)
        encoded = {"accounting": _encode(payload["accounting"])}
        if "cancellations" in payload:
            encoded["cancellations"] = [
                {f.name: event.kind.value if f.name == "kind" else _encode(getattr(event, f.name))
                 for f in fields(OrderLedgerEventV2)} for event in payload["cancellations"]]
        if "bar" in payload:
            encoded.update(bar={f.name: _encode(getattr(payload["bar"], f.name)) for f in fields(OHLCBarV2)},
                evaluated_at=_encode(payload["evaluated_at"]))
        raw = json.dumps(dict(version="paper-oco-evidence-v1", evidence_id=identity,
            payload=encoded, trading_authority=False), sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(raw) > MAX_EVIDENCE_BYTES:
            raise PaperOCOError("evidence size limit")
        try:
            with path.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass  # Exact existing evidence must validate; never overwrite it.
        if self.get(identity) != payload:
            raise PaperOCOError("retained evidence differs")
        # A prior writer may have lost its acknowledgement or failed at fsync.
        # Re-flush validated existing bytes before letting a journal reference it.
        with path.open("r+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        return identity


class DurablePaperOCOReplayV1:
    """Persist and verify evidence before advancing the existing journal.

    Initial arming specifications/ledgers remain explicit constructor inputs.
    This wrapper grants no execution authority and performs no rearming.
    """

    def __init__(self, root, *, initial):
        self.journal = PaperOCOCheckpointV1(root, initial=initial)
        self.evidence = PaperOCOEvidenceStoreV1(self.journal)

    def initialize(self):
        return self.journal.initialize()

    def load(self):
        return self.journal.load(evidence=self.evidence)

    def advance(self, *, kind, payload, expected_checkpoint_id):
        expected = {"EVALUATE": {"accounting", "bar", "evaluated_at"},
                    "ACK": {"accounting"}, "CANCEL_ACK": {"accounting", "cancellations"}}
        if kind not in expected or type(payload) is not dict or set(payload) != expected[kind]:
            raise PaperOCOError("operation and evidence differ")
        identity = self.evidence.put(payload)
        # Use the decoded retained object, not the caller's transient payload.
        return self.journal.advance(kind=kind, payload=self.evidence.get(identity),
            evidence=self.evidence, expected_checkpoint_id=expected_checkpoint_id)
