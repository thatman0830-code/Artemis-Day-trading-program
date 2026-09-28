from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from .contracts import ContractSpec, FuturesBar, decimal, identity, utc


class RollRule(str, Enum):
    FIXED_DAYS = "FIXED_DAYS_BEFORE_EXPIRATION"
    VOLUME_CROSSOVER = "VOLUME_CROSSOVER_POINT_IN_TIME"


@dataclass(frozen=True)
class RollPolicy:
    id: str
    rule: RollRule
    version: str
    days_before_expiration: int | None = None

    def __post_init__(self) -> None:
        if self.rule is RollRule.FIXED_DAYS and (self.days_before_expiration is None or self.days_before_expiration < 0):
            raise ValueError("fixed-day policy needs a nonnegative day count")
        if self.rule is RollRule.VOLUME_CROSSOVER and self.days_before_expiration is not None:
            raise ValueError("volume policy cannot contain fixed days")
        if self.id != identity("roll-policy-v1", self.rule.value, self.version, self.days_before_expiration):
            raise ValueError("roll policy identity mismatch")


@dataclass(frozen=True)
class RollDecision:
    id: str
    old_contract_id: str
    new_contract_id: str
    decision_time: datetime
    effective_time: datetime
    policy_id: str
    evidence_ids: tuple[str, ...]
    old_volume: Decimal | None = None
    new_volume: Decimal | None = None


def decide_roll(*, old: ContractSpec, new: ContractSpec, policy: RollPolicy,
                decision_time: datetime, evidence: tuple[FuturesBar, ...] = ()) -> RollDecision:
    decision = utc(decision_time, "decision_time")
    if old.root is not new.root or old.expiration_date >= new.expiration_date:
        raise ValueError("roll contracts are incompatible")
    if any(x.close_time > decision or x.contract_id not in {old.id, new.id} for x in evidence):
        raise ValueError("roll evidence contains future or incompatible facts")
    old_v = new_v = None
    if policy.rule is RollRule.FIXED_DAYS:
        boundary = old.expiration_date - timedelta(days=policy.days_before_expiration or 0)
        if decision.date() < boundary: raise ValueError("fixed roll is not yet eligible")
    else:
        old_v = sum((x.volume for x in evidence if x.contract_id == old.id), Decimal(0))
        new_v = sum((x.volume for x in evidence if x.contract_id == new.id), Decimal(0))
        if not evidence or new_v <= old_v: raise ValueError("volume crossover is not proven")
    effective = decision + timedelta(minutes=1)
    ident = identity("roll-decision-v1", old.id, new.id, decision.isoformat(), effective.isoformat(), policy.id, *(x.id for x in evidence))
    return RollDecision(ident, old.id, new.id, decision, effective, policy.id,
                        tuple(x.id for x in evidence), old_v, new_v)


def stitch_unadjusted(bars: tuple[FuturesBar, ...], decisions: tuple[RollDecision, ...]) -> tuple[FuturesBar, ...]:
    if not bars: return ()
    ordered = tuple(sorted(bars, key=lambda x: (x.open_time, x.id)))
    if ordered != bars: raise ValueError("bars must be ordered")
    active = bars[0].contract_id; decision_by_time = {x.effective_time: x for x in decisions}; result = []
    for bar in bars:
        if bar.open_time in decision_by_time:
            fact = decision_by_time[bar.open_time]
            if fact.old_contract_id != active: raise ValueError("roll lineage conflict")
            active = fact.new_contract_id
        if bar.contract_id == active: result.append(bar)
    return tuple(result)

