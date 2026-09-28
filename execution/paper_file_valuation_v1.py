"""Bounded local snapshot -> clock guard -> durable paper valuation integration.

Caller-driven; no strategy, orders, background loop, or provider acquisition.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
import stat

from execution.paper_clock_guard_v1 import ClockCheckedPaperSessionV1, capture_paper_clock
from execution.paper_closed_bar_input_v1 import MAX_BYTES, validate_closed_btc_mark, _sha, _utc


class PaperFileValuationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PaperSnapshotReferenceV1:
    relative_path: str
    sha256: str
    available_at: datetime

    def __post_init__(self):
        if type(self.relative_path) is not str or not self.relative_path:
            raise PaperFileValuationError("plain relative snapshot path required")
        path = Path(self.relative_path)
        if (path.root or path.drive or ".." in path.parts
                or ":" in self.relative_path or "\\" in self.relative_path):
            raise PaperFileValuationError("plain relative snapshot path required")
        _sha(self.sha256); _utc(self.available_at)


def read_paper_snapshot(root, reference):
    """Read at most MAX_BYTES+1, bind exact bytes, reject observed file changes.

    Root and reference come from the trusted owner boundary. This is not an
    adversarial-filesystem security boundary or an authenticated manifest reader.
    """
    if not isinstance(reference, PaperSnapshotReferenceV1):
        raise PaperFileValuationError("typed snapshot reference required")
    root = Path(root).absolute()
    target = root / reference.relative_path
    for path in (target, *target.parents):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,"st_file_attributes",0) & 0x400:
            raise PaperFileValuationError("linked or reparse snapshot path rejected")
    if not target.resolve().is_relative_to(root.resolve()):
        raise PaperFileValuationError("snapshot escapes root")
    def identity(info):
        return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
    before = target.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_BYTES:
        raise PaperFileValuationError("snapshot size/type invalid")
    with target.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        payload = stream.read(MAX_BYTES+1)
        after = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(opened) != identity(after)
            or identity(after) != identity(target.stat()) or len(payload) != before.st_size):
        raise PaperFileValuationError("snapshot changed during acquisition")
    if hashlib.sha256(payload).hexdigest() != reference.sha256:
        raise PaperFileValuationError("snapshot checksum mismatch")
    return payload


class PaperFileValuationV1:
    def __init__(self, *, session, snapshot_root, timeframe, maximum_bar_age,
                 instrument_id, mark_specification_id, source_version,
                 market="BTC", contract_id=None):
        if session.active:
            raise PaperFileValuationError("fresh inactive session required")
        self.clock = ClockCheckedPaperSessionV1(session)
        self.root = Path(snapshot_root)
        self.validation = dict(timeframe=timeframe,maximum_bar_age=maximum_bar_age,
            instrument_id=instrument_id,mark_specification_id=mark_specification_id,
            source_version=source_version,market=market,contract_id=contract_id)
        book=session.bridge.initial_accounting
        if (market,instrument_id,contract_id)!=(book.market,book.instrument_id,book.contract_id):
            raise PaperFileValuationError("valuation identity does not match session accounting")
        self.previous = None
        self.failed = False

    def start(self, health_reader, *, utc_reader=None, monotonic_reader=None):
        if self.failed:
            raise PaperFileValuationError("valuation integration latched")
        try:
            return self.clock.read_and_start(health_reader,utc_reader=utc_reader,
                                             monotonic_reader=monotonic_reader)
        except Exception:
            self.failed = True
            raise

    def poll(self, reference, health_reader, *, command=None, verified_fill=None,
             utc_reader=None, monotonic_reader=None):
        session = self.clock.session
        if self.failed or not session.active:
            raise PaperFileValuationError("valuation integration inactive or latched")
        try:
            payload = read_paper_snapshot(self.root, reference)
            health = health_reader()
            sample = capture_paper_clock(utc_reader=utc_reader,monotonic_reader=monotonic_reader)
            receipt = validate_closed_btc_mark(payload=payload,expected_sha256=reference.sha256,
                available_at=reference.available_at,as_of=sample.utc,previous=self.previous,
                **self.validation)
            # input_observed_at denotes this successful poll, not a new bar or a
            # new provider availability time. Bar freshness is checked separately.
            result = self.clock.step(sample,health,input_observed_at=sample.utc,
                                     command=command, verified_fill=verified_fill,
                                     closed_mark=receipt.mark)
            self.previous = receipt
            return receipt, result
        except Exception as exc:
            self.failed = True
            self.clock.guard.failed = True
            if session.active:
                try:
                    session.stop(self.clock.guard.last.utc)
                except Exception as stop_error:
                    raise PaperFileValuationError("input failure; stop unconfirmed") from stop_error
            raise PaperFileValuationError("valuation input failed; session stopped or already inactive") from exc
