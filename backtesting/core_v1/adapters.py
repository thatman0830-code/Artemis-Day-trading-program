from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from .models import CoreBar, CoreEvent, require_utc


@dataclass(frozen=True)
class ActiveContractWindow:
    contract_id: str
    start_inclusive: datetime
    end_exclusive: datetime
    rollover_decision_id: str


@dataclass(frozen=True)
class VerifiedArchiveSlice:
    market: str
    instrument_id: str
    path: Path
    sha256_hex: str
    dataset_fingerprint: str
    bars: tuple[CoreBar, ...]
    active_windows: tuple[ActiveContractWindow, ...] = ()
    supplemental_events: tuple[CoreEvent, ...] = ()

    def validate(self) -> None:
        if self.path.exists() and sha256(self.path.read_bytes()).hexdigest() != self.sha256_hex:
            raise ValueError("archive checksum mismatch")
        previous = None
        seen = set()
        for bar in self.bars:
            if bar.market != self.market or (self.instrument_id and bar.instrument_id != self.instrument_id):
                raise ValueError("archive scope mismatch")
            if bar.id in seen or (previous and bar.close_time <= previous):
                raise ValueError("duplicate or nonchronological archive bar")
            seen.add(bar.id); previous = bar.close_time
            if self.market in ("ES", "NQ"):
                matches = [w for w in self.active_windows if w.contract_id == bar.contract_id and
                           w.start_inclusive <= bar.open_time < w.end_exclusive]
                if len(matches) != 1:
                    raise ValueError("futures bar lacks one active-contract window")

    def visible_at(self, timestamp: datetime) -> tuple[CoreBar, ...]:
        require_utc(timestamp); self.validate()
        return tuple(bar for bar in self.bars if bar.close_time <= timestamp)


class BTCArchiveAdapter(VerifiedArchiveSlice):
    pass


class ESArchiveAdapter(VerifiedArchiveSlice):
    pass


class NQArchiveAdapter(VerifiedArchiveSlice):
    pass
