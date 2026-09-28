"""Canonical CME futures identities without erasing listed-contract identity."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re

_MONTHS = {"F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
           "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12}
_PATTERN = re.compile(r"^(ES|NQ)([FGHJKMNQUVXZ])(\d{1,2})$")


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    root_symbol: str
    contract_symbol: str
    expiry: str
    venue: str
    instrument_id: str
    schema_version: str = "bot2-instrument-identity-v1"

    def to_dict(self):
        return asdict(self)


def normalize_contract(contract_symbol: str, instrument_id: str, *, reference_date: date,
                       venue: str = "CME") -> InstrumentIdentity:
    match = _PATTERN.fullmatch(contract_symbol.upper())
    if not match:
        raise ValueError("unsupported ES/NQ futures ticker")
    root, month_code, year_code = match.groups()
    digit = int(year_code)
    if len(year_code) == 2:
        year = 2000 + digit if digit < 70 else 1900 + digit
    else:
        # Resolve one-digit futures year against the archive/session date, not
        # an implicit current date. This disambiguates e.g. ESU6 as 2026 here.
        candidates = [year for year in range(reference_date.year - 10, reference_date.year + 11)
                      if year % 10 == digit]
        year = min(candidates, key=lambda value: (abs(value - reference_date.year), value))
    return InstrumentIdentity(root, contract_symbol.upper(), f"{year:04d}-{_MONTHS[month_code]:02d}",
                              venue, instrument_id)
