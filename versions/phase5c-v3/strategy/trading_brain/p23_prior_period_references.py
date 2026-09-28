from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionResult, LiquidityReference, LiquiditySide, LiquidityState,
)


POLICY_ID = "OWNER_PRIOR_PERIOD_V1"


class PriorPeriodReferenceType(str, Enum):
    PDH = "PDH"
    PDL = "PDL"
    PWH = "PWH"
    PWL = "PWL"


class PriorPeriodOutcome(str, Enum):
    REGISTERED = "REGISTERED"
    INSUFFICIENT_PERIOD = "INSUFFICIENT_PERIOD"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class PriorPeriodCandle:
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
class PriorPeriodStatus:
    reference_type: PriorPeriodReferenceType
    outcome: PriorPeriodOutcome
    reason: str
    local_start: datetime
    local_end: datetime
    utc_start: datetime
    utc_end: datetime


@dataclass(frozen=True)
class PriorPeriodReferenceFact:
    id: str
    reference: LiquidityReference
    reference_type: PriorPeriodReferenceType
    local_period_start: datetime
    local_period_end: datetime
    utc_period_start: datetime
    utc_period_end: datetime
    account_timezone: str
    tied_extreme_candle_ids: tuple[str, ...]
    symbol: str
    source_timeframe: str
    dataset_id: str
    run_id: str
    policy_id: str
    source_version: str
    calculation_version: str
    provenance: str
    active: bool = True
    historical: bool = False
    consumed: bool = False
    predecessor_fact_id: str | None = None
    transition_reason: str | None = None


@dataclass(frozen=True)
class PriorPeriodEvaluation:
    id: str
    evaluation_time: datetime
    account_timezone: str
    policy_id: str
    statuses: tuple[PriorPeriodStatus, ...]
    registered_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class PriorPeriodTransition:
    id: str
    reference_id: str
    predecessor_fact_id: str
    successor_fact_id: str
    transition_time: datetime
    reason: str


@dataclass(frozen=True)
class PriorPeriodReferenceLedger:
    facts: tuple[PriorPeriodReferenceFact, ...] = ()
    evaluations: tuple[PriorPeriodEvaluation, ...] = ()
    transitions: tuple[PriorPeriodTransition, ...] = ()

    @property
    def active_references(self) -> tuple[LiquidityReference, ...]:
        latest: dict[str, PriorPeriodReferenceFact] = {}
        for fact in self.facts:
            latest[fact.reference.id] = fact
        return tuple(
            latest[key].reference for key in sorted(latest)
            if latest[key].active and not latest[key].historical and not latest[key].consumed
        )


def _hash(*parts: object) -> str:
    return sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC timezone-aware.")
    return value.astimezone(timezone.utc)


def _ms(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


class PriorPeriodLiquidityReferenceProducer:
    """Owner-authored prior-day/week registration; #23 retains pool ownership."""

    @staticmethod
    def _timezone(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("AccountTimezone must be a valid IANA timezone.") from error

    @staticmethod
    def _local_midnight(day: date, zone: ZoneInfo) -> datetime:
        return datetime.combine(day, time.min, tzinfo=zone)

    @classmethod
    def _periods(cls, evaluation_time: datetime, zone: ZoneInfo):
        local = evaluation_time.astimezone(zone)
        daily_end = cls._local_midnight(local.date(), zone)
        daily_start = cls._local_midnight(local.date() - timedelta(days=1), zone)
        week_end_date = local.date() - timedelta(days=local.weekday())
        weekly_end = cls._local_midnight(week_end_date, zone)
        weekly_start = cls._local_midnight(week_end_date - timedelta(days=7), zone)
        return (("DAY", daily_start, daily_end), ("WEEK", weekly_start, weekly_end))

    @staticmethod
    def _valid_candle(candle: PriorPeriodCandle, lineage: tuple[str, ...]) -> bool:
        try:
            _utc(candle.open_time, "open_time"); _utc(candle.close_time, "close_time")
        except ValueError:
            return False
        values = (candle.open, candle.high, candle.low, candle.close)
        return bool(
            candle.id and candle.is_closed and candle.timeframe.lower() == "1m"
            and (candle.symbol, candle.dataset_id, candle.run_id,
                 candle.source_version, candle.calculation_version) == lineage
            and candle.close_time - candle.open_time == timedelta(minutes=1)
            and all(isinstance(value, Decimal) and value.is_finite() for value in values)
            and candle.low > 0 and candle.high >= candle.low
            and candle.low <= candle.open <= candle.high
            and candle.low <= candle.close <= candle.high
        )

    @staticmethod
    def _types(kind: str):
        return ((PriorPeriodReferenceType.PDH, PriorPeriodReferenceType.PDL)
                if kind == "DAY" else
                (PriorPeriodReferenceType.PWH, PriorPeriodReferenceType.PWL))

    def evaluate(
        self, *, candles: tuple[PriorPeriodCandle, ...], evaluation_time: datetime,
        account_timezone: str, symbol: str, dataset_id: str, run_id: str,
        policy_id: str, source_version: str, calculation_version: str,
        ledger: PriorPeriodReferenceLedger | None = None,
    ) -> tuple[PriorPeriodEvaluation, PriorPeriodReferenceLedger]:
        ledger = ledger or PriorPeriodReferenceLedger()
        evaluation_time = _utc(evaluation_time, "evaluation_time")
        if policy_id != POLICY_ID:
            raise ValueError("Unknown prior-period policy identity.")
        if not all(isinstance(item, str) and item.strip() for item in (
            account_timezone, symbol, dataset_id, run_id, source_version,
            calculation_version,
        )):
            raise ValueError("Complete prior-period identity/version lineage is required.")
        zone = self._timezone(account_timezone)
        lineage = (symbol, dataset_id, run_id, source_version, calculation_version)
        ordered = tuple(candles)
        globally_valid = bool(
            all(self._valid_candle(item, lineage) for item in ordered)
            and len({item.id for item in ordered}) == len(ordered)
            and len({item.open_time for item in ordered}) == len(ordered)
            and ordered == tuple(sorted(ordered, key=lambda item: (item.open_time, item.id)))
            and all(item.close_time <= evaluation_time for item in ordered)
        )
        prior_latest: dict[str, PriorPeriodReferenceFact] = {}
        for fact in ledger.facts:
            prior_latest[fact.reference.id] = fact
        facts = list(ledger.facts)
        statuses: list[PriorPeriodStatus] = []
        registered: list[str] = []
        for kind, local_start, local_end in self._periods(evaluation_time, zone):
            utc_start = local_start.astimezone(timezone.utc)
            utc_end = local_end.astimezone(timezone.utc)
            selected = tuple(item for item in ordered
                             if utc_start <= item.open_time and item.close_time <= utc_end)
            expected_count = int((utc_end - utc_start).total_seconds() // 60)
            contiguous = bool(
                globally_valid and utc_end <= evaluation_time
                and len(selected) == expected_count and selected
                and selected[0].open_time == utc_start
                and selected[-1].close_time == utc_end
                and all(selected[index].close_time == selected[index + 1].open_time
                        for index in range(len(selected) - 1))
            )
            for reference_type in self._types(kind):
                if not globally_valid:
                    statuses.append(PriorPeriodStatus(
                        reference_type, PriorPeriodOutcome.INVALID_INPUT,
                        "CANDLE_IDENTITY_VERSION_GEOMETRY_OR_CHRONOLOGY_INVALID",
                        local_start, local_end, utc_start, utc_end,
                    ))
                    continue
                if not contiguous:
                    statuses.append(PriorPeriodStatus(
                        reference_type, PriorPeriodOutcome.INSUFFICIENT_PERIOD,
                        "COMPLETE_CONTIGUOUS_1M_PERIOD_UNAVAILABLE",
                        local_start, local_end, utc_start, utc_end,
                    ))
                    continue
                high_type = reference_type in {
                    PriorPeriodReferenceType.PDH, PriorPeriodReferenceType.PWH,
                }
                price = (max(item.high for item in selected) if high_type
                         else min(item.low for item in selected))
                ties = tuple(item.id for item in selected
                             if (item.high if high_type else item.low) == price)
                side = LiquiditySide.BSL if high_type else LiquiditySide.LSL
                reference_id = _hash(
                    "#23-prior-period-reference-v1", reference_type.value,
                    utc_start.isoformat(), utc_end.isoformat(), account_timezone,
                    symbol, dataset_id, run_id, policy_id, source_version,
                    calculation_version, *ties,
                )
                reference = LiquidityReference(
                    reference_id, "1m", side, price, _ms(utc_end),
                    reference_type.value, True,
                )
                fact_id = _hash("#23-prior-period-fact-v1", reference_id,
                                format(price, "f"), *ties)
                fact = PriorPeriodReferenceFact(
                    fact_id, reference, reference_type, local_start, local_end,
                    utc_start, utc_end, account_timezone, ties, symbol, "1m",
                    dataset_id, run_id, policy_id, source_version,
                    calculation_version, "OWNER_AUTHORED_PRIOR_PERIOD_POLICY",
                )
                prior = prior_latest.get(reference_id)
                if prior is not None:
                    if not prior.active:
                        registered.append(prior.id)
                    elif prior != fact:
                        raise ValueError("Conflicting prior-period reference identity.")
                    else:
                        registered.append(prior.id)
                else:
                    facts.append(fact); prior_latest[reference_id] = fact
                    registered.append(fact.id)
                statuses.append(PriorPeriodStatus(
                    reference_type, PriorPeriodOutcome.REGISTERED,
                    "COMPLETE_PRIOR_PERIOD_REGISTERED", local_start, local_end,
                    utc_start, utc_end,
                ))
        evaluation_id = _hash(
            "#23-prior-period-evaluation-v1", evaluation_time.isoformat(),
            account_timezone, symbol, dataset_id, run_id, policy_id,
            source_version, calculation_version,
            *(f"{item.reference_type.value}:{item.outcome.value}:{item.reason}"
              for item in statuses),
        )
        evaluation = PriorPeriodEvaluation(
            evaluation_id, evaluation_time, account_timezone, policy_id,
            tuple(statuses), tuple(registered),
        )
        prior_evaluation = next((item for item in ledger.evaluations
                                 if item.id == evaluation.id), None)
        if prior_evaluation is not None:
            if prior_evaluation != evaluation:
                raise ValueError("Conflicting prior-period evaluation identity.")
            return prior_evaluation, ledger
        return evaluation, PriorPeriodReferenceLedger(
            tuple(facts), ledger.evaluations + (evaluation,), ledger.transitions,
        )

    @staticmethod
    def consume(
        *, reference_id: str, interaction: LiquidityInteractionResult,
        consumption_time: datetime, ledger: PriorPeriodReferenceLedger,
    ) -> tuple[PriorPeriodReferenceFact, PriorPeriodReferenceLedger]:
        consumption_time = _utc(consumption_time, "consumption_time")
        latest: dict[str, PriorPeriodReferenceFact] = {}
        for fact in ledger.facts:
            latest[fact.reference.id] = fact
        prior = latest.get(reference_id)
        if prior is None:
            raise ValueError("Prior-period reference is absent from its ledger.")
        if not prior.active:
            return prior, ledger
        event = interaction.event
        if (event is None or interaction.pool.state != LiquidityState.CONSUMED
                or event.final_state != LiquidityState.CONSUMED
                or reference_id not in interaction.pool.component_reference_ids):
            return prior, ledger
        historical = replace(
            prior, id=_hash(prior.id, "consumed", event.id), active=False,
            historical=True, consumed=True, predecessor_fact_id=prior.id,
            transition_reason=f"POOL_{event.outcome.value}",
        )
        transition = PriorPeriodTransition(
            _hash("#23-prior-period-transition-v1", prior.id, historical.id),
            reference_id, prior.id, historical.id, consumption_time,
            historical.transition_reason,
        )
        return historical, PriorPeriodReferenceLedger(
            ledger.facts + (historical,), ledger.evaluations,
            ledger.transitions + (transition,),
        )

    @staticmethod
    def invalidate(
        *, reference_id: str, invalidation_time: datetime, reason: str,
        ledger: PriorPeriodReferenceLedger,
    ) -> tuple[PriorPeriodReferenceFact, PriorPeriodReferenceLedger]:
        """Record an explicit upstream invalidation without deleting history."""
        invalidation_time = _utc(invalidation_time, "invalidation_time")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalidation reason must be non-empty.")
        latest: dict[str, PriorPeriodReferenceFact] = {}
        for fact in ledger.facts:
            latest[fact.reference.id] = fact
        prior = latest.get(reference_id)
        if prior is None:
            raise ValueError("Prior-period reference is absent from its ledger.")
        if not prior.active:
            return prior, ledger
        available_at = datetime.fromtimestamp(
            prior.reference.confirmation_time / 1_000, tz=timezone.utc,
        )
        if invalidation_time < available_at:
            raise ValueError("invalidation_time precedes reference availability.")
        normalized_reason = reason.strip()
        historical = replace(
            prior,
            id=_hash(prior.id, "invalidated", invalidation_time.isoformat(), normalized_reason),
            active=False, historical=True, predecessor_fact_id=prior.id,
            transition_reason=f"UPSTREAM_INVALIDATION:{normalized_reason}",
        )
        transition = PriorPeriodTransition(
            _hash("#23-prior-period-transition-v1", prior.id, historical.id),
            reference_id, prior.id, historical.id, invalidation_time,
            historical.transition_reason,
        )
        return historical, PriorPeriodReferenceLedger(
            ledger.facts + (historical,), ledger.evaluations,
            ledger.transitions + (transition,),
        )
