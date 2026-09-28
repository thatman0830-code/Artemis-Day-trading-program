from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from enum import Enum
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import (
    StructuralEventType, StructuralRegime, StructuralStateSnapshot,
)


class DisplacementOutcome(str, Enum):
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    INSUFFICIENT_REFERENCE = "INSUFFICIENT_REFERENCE"
    INVALID_INPUT = "INVALID_INPUT"
    UPSTREAM_INVALID = "UPSTREAM_INVALID"


@dataclass(frozen=True)
class MechanicalDisplacementPolicy:
    id: str
    reference_length: int
    body_expansion_threshold: Decimal
    minimum_body_ratio: Decimal
    structural_clearance_ticks: int
    gap_policy: str
    provenance: str
    calculation_version: str

    @classmethod
    def owner_mechanical_v1(cls, *, calculation_version: str):
        return cls(
            "OWNER_MECHANICAL_V1", 20, Decimal("1.5"), Decimal("0.60"),
            1, "REQUIRE_CONTIGUOUS", "OWNER_AUTHORED_PENDING_CANONICAL_VALIDATION",
            calculation_version,
        )


@dataclass(frozen=True)
class DisplacementCandle:
    id: str
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    dataset_id: str
    run_id: str
    source_version: str
    calculation_version: str
    is_closed: bool = True


@dataclass(frozen=True)
class StructuralDisplacementContext:
    id: str
    symbol: str
    timeframe: str
    direction: StructuralRegime
    event_type: StructuralEventType
    structural_snapshot_id: str
    governing_swing_id: str
    governing_price: Decimal


@dataclass(frozen=True)
class DisplacementQualification:
    id: str
    evaluation_key: str
    outcome: DisplacementOutcome
    reason: str
    qualified: bool
    evaluation_candle_id: str
    reference_candle_ids: tuple[str, ...]
    structural_context_id: str
    structural_candidate_id: str
    structural_snapshot_id: str
    governing_swing_id: str
    symbol: str
    timeframe: str
    direction: StructuralRegime
    event_type: StructuralEventType
    governing_price: Decimal
    minimum_tick: Decimal
    body: Decimal | None
    range: Decimal | None
    median_prior_body: Decimal | None
    body_expansion: Decimal | None
    body_ratio: Decimal | None
    occurrence_time: datetime
    available_at: datetime
    dataset_id: str
    run_id: str
    policy_id: str
    source_version: str
    calculation_version: str
    active: bool = True
    invalidation_reason: str | None = None


@dataclass(frozen=True)
class DisplacementLedger:
    records: tuple[DisplacementQualification, ...] = ()


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode()).hexdigest()


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


class DisplacementQualificationProducer:
    """Owner-authored OWNER_MECHANICAL_V1 policy; not original canonical text."""

    @staticmethod
    def _utc(value: datetime, field: str) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field} must be UTC timezone-aware.")
        return value.astimezone(timezone.utc)

    @classmethod
    def context(
        cls, *, state: StructuralStateSnapshot, symbol: str,
        direction: StructuralRegime, event_type: StructuralEventType,
    ) -> StructuralDisplacementContext:
        if direction == StructuralRegime.BULLISH:
            reference = state.protected_high if event_type == StructuralEventType.MSS else state.governing_high
        elif direction == StructuralRegime.BEARISH:
            reference = state.protected_low if event_type == StructuralEventType.MSS else state.governing_low
        else:
            raise ValueError("Displacement direction must be BULLISH or BEARISH.")
        if reference is None or reference.timeframe != state.timeframe:
            raise ValueError("Compatible governing structural reference is required.")
        identity = _hash(("#20-displacement-context-v1", state.id, symbol, state.timeframe,
                          direction.value, event_type.value, reference.id))
        return StructuralDisplacementContext(
            identity, symbol, state.timeframe, direction, event_type,
            state.id, reference.id, reference.price,
        )

    @staticmethod
    def _valid_policy(policy: MechanicalDisplacementPolicy) -> None:
        if not isinstance(policy, MechanicalDisplacementPolicy) or not policy.calculation_version.strip():
            raise ValueError("A versioned OWNER_MECHANICAL_V1 policy is required.")
        expected = MechanicalDisplacementPolicy.owner_mechanical_v1(
            calculation_version=policy.calculation_version
        )
        if policy != expected:
            raise ValueError("OWNER_MECHANICAL_V1 policy fields are immutable.")

    @staticmethod
    def _body(candle: DisplacementCandle) -> Decimal:
        return abs(candle.close - candle.open)

    @classmethod
    def _candle_valid(cls, candle: DisplacementCandle) -> bool:
        try:
            cls._utc(candle.open_time, "open_time")
            cls._utc(candle.close_time, "close_time")
        except ValueError:
            return False
        values = (candle.open, candle.high, candle.low, candle.close)
        return bool(
            candle.is_closed and candle.id and candle.open_time < candle.close_time
            and all(isinstance(value, Decimal) and value.is_finite() for value in values)
            and candle.low > 0 and candle.high >= candle.low
            and candle.low <= candle.open <= candle.high
            and candle.low <= candle.close <= candle.high
        )

    def evaluate(
        self, *, policy: MechanicalDisplacementPolicy,
        context: StructuralDisplacementContext,
        state_before: StructuralStateSnapshot,
        evaluation_candle: DisplacementCandle,
        reference_candles: tuple[DisplacementCandle, ...],
        minimum_tick: Decimal, dataset_id: str, run_id: str,
        source_version: str, calculation_version: str,
        upstream_active: bool = True,
        ledger: DisplacementLedger | None = None,
    ) -> tuple[DisplacementQualification, DisplacementLedger]:
        self._valid_policy(policy)
        if not isinstance(minimum_tick, Decimal) or not minimum_tick.is_finite() or minimum_tick <= 0:
            raise ValueError("minimum_tick must be a finite positive Decimal.")
        if policy.calculation_version != calculation_version:
            raise ValueError("Policy/calculation version mismatch.")
        ledger = ledger or DisplacementLedger()
        key = _hash(("#20-displacement-evaluation-v1", dataset_id, run_id, context.id,
                     evaluation_candle.id, policy.id, source_version, calculation_version))

        references = tuple(reference_candles)
        base = dict(
            evaluation_key=key, evaluation_candle_id=evaluation_candle.id,
            reference_candle_ids=tuple(c.id for c in references),
            structural_context_id=context.id,
            structural_candidate_id=str(uuid5(
                NAMESPACE_URL,
                f"trading-brain:#20:{state_before.id}:"
                f"{_milliseconds(evaluation_candle.open_time)}:"
                f"{context.event_type.value}:{context.direction.value}:"
                f"{context.governing_swing_id}",
            )),
            structural_snapshot_id=context.structural_snapshot_id,
            governing_swing_id=context.governing_swing_id,
            symbol=context.symbol, timeframe=context.timeframe,
            direction=context.direction, event_type=context.event_type,
            governing_price=context.governing_price, minimum_tick=minimum_tick,
            occurrence_time=evaluation_candle.close_time,
            available_at=evaluation_candle.close_time,
            dataset_id=dataset_id, run_id=run_id, policy_id=policy.id,
            source_version=source_version, calculation_version=calculation_version,
        )

        outcome = DisplacementOutcome.NOT_QUALIFIED
        reason = "THRESHOLD_OR_DIRECTION_NOT_SATISFIED"
        body = range_ = median = expansion = ratio = None
        lineage = (
            context.structural_snapshot_id == state_before.id
            and context.timeframe == state_before.timeframe
            and (context.symbol, context.timeframe, dataset_id, run_id, source_version, calculation_version)
            == (evaluation_candle.symbol, evaluation_candle.timeframe,
                evaluation_candle.dataset_id, evaluation_candle.run_id,
                evaluation_candle.source_version, evaluation_candle.calculation_version)
            and all((c.symbol, c.timeframe, c.dataset_id, c.run_id,
                     c.source_version, c.calculation_version)
                    == (evaluation_candle.symbol, evaluation_candle.timeframe,
                        dataset_id, run_id, source_version, calculation_version)
                    for c in references)
        )
        if not upstream_active:
            outcome, reason = DisplacementOutcome.UPSTREAM_INVALID, "UPSTREAM_STRUCTURAL_CONTEXT_INVALID"
        elif not lineage or not self._candle_valid(evaluation_candle) or any(not self._candle_valid(c) for c in references):
            outcome, reason = DisplacementOutcome.INVALID_INPUT, "IDENTITY_VERSION_TIMEFRAME_OR_CANDLE_INVALID"
        elif len(references) != policy.reference_length:
            outcome, reason = DisplacementOutcome.INSUFFICIENT_REFERENCE, "EXACTLY_20_REFERENCES_REQUIRED"
        else:
            ordered = tuple(sorted(references, key=lambda c: (c.open_time, c.id)))
            duration = evaluation_candle.close_time - evaluation_candle.open_time
            contiguous = (
                references == ordered
                and all(c.close_time - c.open_time == duration for c in references)
                and all(ordered[i].close_time == ordered[i + 1].open_time for i in range(19))
                and ordered[-1].close_time == evaluation_candle.open_time
                and all(c.close_time <= evaluation_candle.open_time for c in ordered)
            )
            if not contiguous:
                outcome, reason = DisplacementOutcome.INSUFFICIENT_REFERENCE, "REFERENCE_WINDOW_GAPPED_OR_NONCONTIGUOUS"
            else:
                body = self._body(evaluation_candle)
                range_ = evaluation_candle.high - evaluation_candle.low
                bodies = sorted(self._body(c) for c in ordered)
                median = (bodies[9] + bodies[10]) / Decimal("2")
                if range_ <= 0:
                    outcome, reason = DisplacementOutcome.INVALID_INPUT, "EVALUATION_RANGE_NOT_POSITIVE"
                elif median <= 0:
                    outcome, reason = DisplacementOutcome.INSUFFICIENT_REFERENCE, "MEDIAN_PRIOR_BODY_NOT_POSITIVE"
                else:
                    with localcontext() as decimal_context:
                        decimal_context.prec = max(decimal_context.prec, 28)
                        expansion, ratio = body / median, body / range_
                    clearance = minimum_tick * Decimal(policy.structural_clearance_ticks)
                    directional = (
                        evaluation_candle.close > evaluation_candle.open
                        and evaluation_candle.close >= context.governing_price + clearance
                        if context.direction == StructuralRegime.BULLISH else
                        evaluation_candle.close < evaluation_candle.open
                        and evaluation_candle.close <= context.governing_price - clearance
                    )
                    if directional and expansion >= policy.body_expansion_threshold and ratio >= policy.minimum_body_ratio:
                        outcome, reason = DisplacementOutcome.QUALIFIED, "OWNER_MECHANICAL_V1_ALL_RULES_SATISFIED"

        qualified = outcome == DisplacementOutcome.QUALIFIED
        record_id = _hash((key, outcome.value, reason, str(body), str(range_), str(median),
                           str(expansion), str(ratio), *(c.id for c in references)))
        record = DisplacementQualification(
            record_id, outcome=outcome, reason=reason, qualified=qualified,
            body=body, range=range_, median_prior_body=median,
            body_expansion=expansion, body_ratio=ratio, **base,
        )
        prior = next((item for item in ledger.records if item.evaluation_key == key), None)
        if prior is not None:
            if prior != record:
                raise ValueError("Conflicting displacement evaluation identity.")
            return prior, ledger
        return record, DisplacementLedger(ledger.records + (record,))

    @staticmethod
    def invalidate(
        *, record: DisplacementQualification, reason: str,
        ledger: DisplacementLedger,
    ) -> tuple[DisplacementQualification, DisplacementLedger]:
        if not reason.strip():
            raise ValueError("Upstream invalidation reason is required.")
        if record not in ledger.records:
            raise ValueError("Displacement record is absent from its immutable ledger.")
        if not record.active:
            return record, ledger
        existing = next((
            item for item in ledger.records
            if not item.active and item.evaluation_key == record.evaluation_key
            and item.invalidation_reason == reason
        ), None)
        if existing is not None:
            return existing, ledger
        historical = DisplacementQualification(
            **{**record.__dict__, "id": _hash((record.id, "invalidated", reason)),
               "active": False, "invalidation_reason": reason}
        )
        return historical, DisplacementLedger(ledger.records + (historical,))
