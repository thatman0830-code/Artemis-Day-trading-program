from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256

from strategy.trading_brain.p19_mechanical_swings import (
    MechanicalSwing, MechanicalSwingResult, MechanicalSwingType,
)
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralRegime, StructuralStateSnapshot,
    StructuralSwing, StructuralSwingSelector,
)


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ValueError("available_at must be a UTC timezone-aware datetime.")
    return value.astimezone(timezone.utc)


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


@dataclass(frozen=True)
class StructuralSwingAvailability:
    """Replay-safe #19 -> #20 handoff; never a trading-semantic state."""

    id: str
    source_swing: MechanicalSwing
    symbol: str
    timeframe: str
    available_at: datetime
    source_version: str
    calculation_version: str


@dataclass(frozen=True)
class StructuralIngestionLedger:
    """Append-only #20 initialization and structural-leg lineage."""

    id: str
    symbol: str
    timeframe: str
    source_version: str
    calculation_version: str
    availability_facts: tuple[StructuralSwingAvailability, ...]
    structural_swings: tuple[StructuralSwing, ...]
    pending_source_swing_ids: tuple[str, ...]
    superseded_source_swing_ids: tuple[str, ...]
    historical_structural_swing_ids: tuple[str, ...]
    snapshots: tuple[StructuralStateSnapshot, ...]

    @property
    def current_snapshot(self) -> StructuralStateSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    @property
    def classification_ready(self) -> bool:
        snapshot = self.current_snapshot
        return bool(
            snapshot is not None
            and snapshot.governing_high is not None
            and snapshot.governing_low is not None
        )


class StructuralStateProducer:
    """#20 structural initialization and swing-ingestion/advancement only.

    It consumes confirmed #19 observations at their explicit availability
    boundary. It does not qualify displacement, BOS/MSS, liquidity, CISD,
    confluence, setup, risk, or execution facts.
    """

    @staticmethod
    def _required(value: str, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required.")
        return value.strip()

    @staticmethod
    def _validate_swing(swing: MechanicalSwing, timeframe: str) -> None:
        if not isinstance(swing, MechanicalSwing) or not swing.confirmed:
            raise ValueError("#20 ingestion requires immutable confirmed #19 swings.")
        if swing.timeframe != timeframe:
            raise ValueError("#19/#20 timeframe lineage mismatch.")
        if not isinstance(swing.price, Decimal):
            raise TypeError("Structural ingestion prices must be Decimal.")
        if not swing.price.is_finite() or swing.price <= 0:
            raise ValueError("Structural ingestion prices must be finite and positive.")
        if isinstance(swing.pivot_time, bool) or not isinstance(swing.pivot_time, int):
            raise TypeError("pivot_time must be an exact integer epoch value.")
        if not swing.id.strip():
            raise ValueError("Source swing identity is required.")

    @staticmethod
    def _availability(
        *, swing: MechanicalSwing, symbol: str, available_at: datetime,
        source_version: str, calculation_version: str,
    ) -> StructuralSwingAvailability:
        identity = _hash((
            "trading-brain:#20-availability-v1", swing.id, symbol,
            swing.timeframe, _stamp(available_at), source_version,
            calculation_version,
        ))
        return StructuralSwingAvailability(
            identity, swing, symbol, swing.timeframe, available_at,
            source_version, calculation_version,
        )

    @staticmethod
    def _legs(
        swings: tuple[MechanicalSwing, ...],
    ) -> tuple[tuple[MechanicalSwing, ...], tuple[str, ...]]:
        ordered = tuple(sorted(swings, key=lambda item: (item.pivot_time, item.type.value, item.id)))
        selected: list[MechanicalSwing] = []
        superseded: list[str] = []
        current: MechanicalSwing | None = None
        for swing in ordered:
            if current is None:
                current = swing
                continue
            if swing.type != current.type:
                selected.append(current)
                current = swing
                continue
            more_extreme = (
                swing.price > current.price
                if swing.type == MechanicalSwingType.H
                else swing.price < current.price
            )
            if more_extreme:
                superseded.append(current.id)
                current = swing
            else:
                superseded.append(swing.id)
        if current is not None:
            selected.append(current)
        return tuple(selected), tuple(superseded)

    @staticmethod
    def _snapshot_id(
        *, symbol: str, timeframe: str, source_version: str,
        calculation_version: str, predecessor: str | None,
        as_of: datetime, governing_high: StructuralSwing,
        governing_low: StructuralSwing, regime: StructuralRegime,
        protected_high: StructuralSwing | None,
        protected_low: StructuralSwing | None,
        candidate_high: StructuralSwing | None,
        candidate_low: StructuralSwing | None,
    ) -> str:
        return _hash((
            "trading-brain:#20-ingestion-state-v1", symbol, timeframe,
            source_version, calculation_version, predecessor or "",
            _stamp(as_of), governing_high.id, governing_low.id, regime.value,
            protected_high.id if protected_high else "",
            protected_low.id if protected_low else "",
            candidate_high.id if candidate_high else "",
            candidate_low.id if candidate_low else "",
        ))

    @staticmethod
    def _ledger_id(
        *, symbol: str, timeframe: str, source_version: str,
        calculation_version: str,
        facts: tuple[StructuralSwingAvailability, ...],
        snapshots: tuple[StructuralStateSnapshot, ...],
    ) -> str:
        return _hash((
            "trading-brain:#20-ingestion-ledger-v1", symbol, timeframe,
            source_version, calculation_version,
            *(fact.id for fact in facts), *(snapshot.id for snapshot in snapshots),
        ))

    def ingest(
        self, *, swing_result: MechanicalSwingResult, symbol: str,
        available_at: datetime, source_version: str,
        calculation_version: str,
        ledger: StructuralIngestionLedger | None = None,
        state_before: StructuralStateSnapshot | None = None,
    ) -> StructuralIngestionLedger:
        if not isinstance(swing_result, MechanicalSwingResult):
            raise TypeError("A canonical #19 MechanicalSwingResult is required.")
        symbol = self._required(symbol, "symbol")
        timeframe = self._required(swing_result.timeframe, "timeframe")
        source_version = self._required(source_version, "source_version")
        calculation_version = self._required(calculation_version, "calculation_version")
        available_at = _utc(available_at)
        for swing in swing_result.swings:
            self._validate_swing(swing, timeframe)
        ids = [swing.id for swing in swing_result.swings]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate #19 swing identity is a data-integrity failure.")
        canonical_order = tuple(sorted(
            swing_result.swings,
            key=lambda item: (item.pivot_time, item.type.value, item.id),
        ))
        if swing_result.swings != canonical_order:
            raise ValueError("#19 swing inputs must use canonical increasing chronology.")

        if ledger is None:
            facts: tuple[StructuralSwingAvailability, ...] = ()
            snapshots: tuple[StructuralStateSnapshot, ...] = ()
        else:
            if not isinstance(ledger, StructuralIngestionLedger):
                raise TypeError("ledger must be an immutable StructuralIngestionLedger.")
            if (ledger.symbol, ledger.timeframe, ledger.source_version,
                ledger.calculation_version) != (
                    symbol, timeframe, source_version, calculation_version):
                raise ValueError("#20 ingestion symbol/timeframe/version lineage mismatch.")
            facts, snapshots = ledger.availability_facts, ledger.snapshots

        state_appended = False
        if state_before is not None:
            if state_before.timeframe != timeframe:
                raise ValueError("Prior #20 state timeframe mismatch.")
            current = snapshots[-1] if snapshots else None
            if current is None or (
                state_before != current
                and state_before.predecessor_state_id != current.id
            ):
                raise ValueError("Prior #20 state is not contiguous with ingestion history.")
            if state_before != current:
                snapshots = snapshots + (state_before,)
                state_appended = True

        existing_by_source = {fact.source_swing.id: fact for fact in facts}
        result_by_source = {swing.id: swing for swing in swing_result.swings}
        for source_id, fact in existing_by_source.items():
            supplied = result_by_source.get(source_id)
            if supplied is not None and supplied != fact.source_swing:
                raise ValueError("Conflicting reuse of a #19 swing identity.")

        new_swings = tuple(
            swing for swing in swing_result.swings if swing.id not in existing_by_source
        )
        if not new_swings:
            if ledger is not None and not state_appended:
                return ledger
            if ledger is not None:
                current = snapshots[-1]
                referenced = {
                    item.id for item in (
                        current.governing_high, current.governing_low,
                        current.protected_high, current.protected_low,
                        current.candidate_protected_high,
                        current.candidate_protected_low,
                    ) if item is not None
                }
                historical = tuple(
                    item.id for item in ledger.structural_swings
                    if item.id not in referenced
                )
                return StructuralIngestionLedger(
                    self._ledger_id(
                        symbol=symbol, timeframe=timeframe,
                        source_version=source_version,
                        calculation_version=calculation_version,
                        facts=facts, snapshots=snapshots,
                    ), symbol, timeframe, source_version, calculation_version,
                    facts, ledger.structural_swings,
                    ledger.pending_source_swing_ids,
                    ledger.superseded_source_swing_ids,
                    historical, snapshots,
                )
            return StructuralIngestionLedger(
                self._ledger_id(
                    symbol=symbol, timeframe=timeframe,
                    source_version=source_version,
                    calculation_version=calculation_version,
                    facts=(), snapshots=(),
                ), symbol, timeframe, source_version, calculation_version,
                (), (), (), (), (), (),
            )

        if facts and available_at < facts[-1].available_at:
            raise ValueError("Swing availability must advance monotonically.")
        if len({swing.pivot_time for swing in new_swings}) != 1:
            raise ValueError(
                "Replay-safe availability is unproven for multiple newly observed pivot times."
            )
        available_ms = _milliseconds(available_at)
        if any(swing.pivot_time >= available_ms for swing in new_swings):
            raise ValueError("A swing cannot be available at or before its pivot occurrence.")
        if facts:
            last_pivot = max(fact.source_swing.pivot_time for fact in facts)
            if new_swings[0].pivot_time < last_pivot:
                raise ValueError("Stale/out-of-order #19 swing input.")

        appended = tuple(
            self._availability(
                swing=swing, symbol=symbol, available_at=available_at,
                source_version=source_version,
                calculation_version=calculation_version,
            )
            for swing in sorted(new_swings, key=lambda item: (item.pivot_time, item.type.value, item.id))
        )
        facts = facts + appended
        all_swings = tuple(fact.source_swing for fact in facts)
        selected, superseded = self._legs(all_swings)

        # The first opposite pair is the explicit baseline. Thereafter the
        # newest leg remains pending until an opposite structural leg closes it.
        if len(selected) < 2:
            finalized_mechanical: tuple[MechanicalSwing, ...] = ()
            pending = tuple(item.id for item in selected)
            structural: tuple[StructuralSwing, ...] = ()
        else:
            finalized_mechanical = selected if len(selected) == 2 else selected[:-1]
            pending = () if len(selected) == 2 else (selected[-1].id,)
            structural = StructuralSwingSelector().select(
                swings=finalized_mechanical
            ).swings

        base = state_before or (snapshots[-1] if snapshots else None)
        if structural:
            high = next(item for item in reversed(structural) if item.type == MechanicalSwingType.H)
            low = next(item for item in reversed(structural) if item.type == MechanicalSwingType.L)
            regime = base.regime if base is not None else StructuralRegime.INITIALIZING
            protected_high = base.protected_high if base is not None else None
            protected_low = base.protected_low if base is not None else None
            candidate_high = base.candidate_protected_high if base is not None else None
            candidate_low = base.candidate_protected_low if base is not None else None
            if regime == StructuralRegime.BULLISH:
                eligible = [item for item in structural if item.classification == StructuralClassification.HL]
                if eligible:
                    candidate_low = eligible[-1]
            elif regime == StructuralRegime.BEARISH:
                eligible = [item for item in structural if item.classification == StructuralClassification.LH]
                if eligible:
                    candidate_high = eligible[-1]

            unchanged = bool(
                base is not None
                and base.governing_high == high
                and base.governing_low == low
                and base.candidate_protected_high == candidate_high
                and base.candidate_protected_low == candidate_low
            )
            if not unchanged:
                predecessor = base.id if base is not None else None
                snapshot_id = self._snapshot_id(
                    symbol=symbol, timeframe=timeframe,
                    source_version=source_version,
                    calculation_version=calculation_version,
                    predecessor=predecessor, as_of=available_at,
                    governing_high=high, governing_low=low, regime=regime,
                    protected_high=protected_high, protected_low=protected_low,
                    candidate_high=candidate_high, candidate_low=candidate_low,
                )
                snapshots = snapshots + (StructuralStateSnapshot(
                    snapshot_id, timeframe, regime, high, low,
                    protected_high, protected_low, candidate_high, candidate_low,
                    predecessor, available_ms,
                ),)

        referenced = set()
        if snapshots:
            current = snapshots[-1]
            referenced = {
                item.id for item in (
                    current.governing_high, current.governing_low,
                    current.protected_high, current.protected_low,
                    current.candidate_protected_high,
                    current.candidate_protected_low,
                ) if item is not None
            }
        historical = tuple(item.id for item in structural if item.id not in referenced)
        ledger_id = self._ledger_id(
            symbol=symbol, timeframe=timeframe, source_version=source_version,
            calculation_version=calculation_version, facts=facts,
            snapshots=snapshots,
        )
        return StructuralIngestionLedger(
            ledger_id, symbol, timeframe, source_version, calculation_version,
            facts, structural, pending, superseded, historical, snapshots,
        )
