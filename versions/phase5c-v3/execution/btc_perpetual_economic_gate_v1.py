"""Fail-closed economic gate for supervised BTC perpetual paper trading."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2
from backtesting.execution_accounting_v2.specifications import (
    EligibilityReport, InstrumentProfile, SpecificationRepository, SpecificationType,
    canonical_fingerprint, evaluate_production_eligibility,
)
from backtesting.execution_accounting_v2.validation import validate_repository_provenance
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidBTCPerpetualPrecisionV1


VERSION = "btc-perpetual-economic-gate-v1"
REQUIRED_TYPES = (SpecificationType.INSTRUMENT, SpecificationType.MARK_PRICE,
    SpecificationType.ORACLE_PRICE, SpecificationType.FUNDING, SpecificationType.MARGIN_TIER,
    SpecificationType.FEE_TIER, SpecificationType.SLIPPAGE, SpecificationType.PARTICIPATION,
    SpecificationType.RISK_LIMITS)


class BTCPerpetualEconomicGateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BTCPerpetualEconomicEligibilityV1:
    gate_id: str
    eligibility: EligibilityReport
    instrument: InstrumentSpecificationV2
    precision_id: str
    specification_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    advisory_only: bool = True
    live_trading_permitted: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if (not self.eligibility.eligible or self.advisory_only is not True
                or self.live_trading_permitted is not False or self.trading_authority is not False):
            raise BTCPerpetualEconomicGateError("economic gate cannot grant trading authority")
        expected = canonical_fingerprint(VERSION, self.eligibility, self.instrument,
            self.precision_id, self.specification_ids, self.evidence_ids, True, False, False)
        if self.gate_id != expected:
            raise BTCPerpetualEconomicGateError("economic gate identity mismatch")


def evaluate_btc_perpetual_economics(*, repository: SpecificationRepository,
        repository_root, instrument: InstrumentSpecificationV2,
        precision: HyperliquidBTCPerpetualPrecisionV1,
        as_of: datetime) -> BTCPerpetualEconomicEligibilityV1:
    if not isinstance(repository, SpecificationRepository):
        raise BTCPerpetualEconomicGateError("specification repository is required")
    if (not isinstance(instrument, InstrumentSpecificationV2)
            or instrument.profile is not InstrumentProfile.BTC_LINEAR_PERPETUAL
            or (instrument.market, instrument.instrument_id, instrument.contract_id)
                != ("BTC-PERP", "BTC", "BTC-PERP")):
        raise BTCPerpetualEconomicGateError("exact BTC perpetual instrument is required")
    if not isinstance(precision, HyperliquidBTCPerpetualPrecisionV1):
        raise BTCPerpetualEconomicGateError("perpetual precision evidence is required")
    if instrument.quantity_step != precision.quantity_step:
        raise BTCPerpetualEconomicGateError("instrument quantity step conflicts with precision evidence")
    if any((item.market, item.instrument_id) != ("BTC-PERP", "BTC")
           for item in repository.specifications + repository.evidence):
        raise BTCPerpetualEconomicGateError("repository must be isolated to BTC perpetual")
    provenance = validate_repository_provenance(repository, repository_root)
    if not provenance.valid:
        raise BTCPerpetualEconomicGateError("economic evidence provenance is invalid")
    eligibility = evaluate_production_eligibility(repository,
        InstrumentProfile.BTC_LINEAR_PERPETUAL, "BTC-PERP", "BTC", as_of)
    if not eligibility.eligible:
        reasons = ",".join(sorted({item.reason.value for item in eligibility.issues}))
        raise BTCPerpetualEconomicGateError("economic eligibility failed: " + reasons)
    selected = tuple(repository.resolve(kind, "BTC-PERP", "BTC", as_of)
                     for kind in REQUIRED_TYPES)
    if any(item is None for item in selected):
        raise BTCPerpetualEconomicGateError("required effective specification is absent")
    instrument_record = selected[0]
    expected_values = (("contract_id", "BTC-PERP"), ("contract_multiplier", format(instrument.contract_multiplier, "f")),
        ("currency", instrument.currency), ("profile", instrument.profile.value),
        ("quantity_step", format(instrument.quantity_step, "f")),
        ("tick_size", format(instrument.tick_size, "f")))
    if (instrument_record.specification_id != instrument.specification_id
            or instrument_record.evidence_ids != instrument.evidence_ids
            or instrument_record.values != expected_values
            or not instrument_record.effective_from <= as_of
            or (instrument_record.effective_to is not None and as_of >= instrument_record.effective_to)):
        raise BTCPerpetualEconomicGateError("typed instrument conflicts with effective specification")
    evidence_ids = tuple(sorted({eid for item in selected for eid in item.evidence_ids}))
    if not set(precision.source_evidence_ids).issubset(evidence_ids):
        raise BTCPerpetualEconomicGateError("precision evidence is outside the eligible repository")
    specification_ids = tuple(sorted(item.specification_id for item in selected))
    gate_id = canonical_fingerprint(VERSION, eligibility, instrument, precision.precision_id,
        specification_ids, evidence_ids, True, False, False)
    return BTCPerpetualEconomicEligibilityV1(gate_id, eligibility, instrument,
        precision.precision_id, specification_ids, evidence_ids, True, False, False)
