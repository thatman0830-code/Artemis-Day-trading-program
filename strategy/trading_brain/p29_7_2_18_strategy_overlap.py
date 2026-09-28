from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode


@dataclass(frozen=True)
class OverlapScope:
    id: str
    source_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyOverlap:
    id: str
    strategy_a_id: str
    strategy_b_id: str
    trade_a_id: str
    trade_b_id: str
    accounting_a_id: str
    accounting_b_id: str
    position_a_id: str
    position_b_id: str
    symbol_a: str
    symbol_b: str
    timeframe_a: str
    timeframe_b: str
    model_a: object
    model_b: object
    direction_a: object
    direction_b: object
    overlap_start: int
    overlap_end: int
    overlap_duration: int
    simultaneous_risk: Decimal
    simultaneous_notional_exposure: Decimal | None
    created_time: int
    active: bool
    historical: bool
    immutable: bool = True


@dataclass(frozen=True)
class UnionOverlapInterval:
    id: str
    strategy_a_id: str
    strategy_b_id: str
    overlap_start: int
    overlap_end: int
    overlap_duration: int
    source_overlap_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class StrategyPairOverlap:
    id: str
    strategy_a_id: str
    strategy_b_id: str
    co_occurrence: bool
    overlap_trade_pair_count: int
    total_overlap_duration: int
    first_overlap_time: int | None
    last_overlap_time: int | None
    union_intervals: tuple[UnionOverlapInterval, ...]
    source_overlap_ids: tuple[str, ...]
    active: bool
    historical: bool
    immutable: bool = True


@dataclass(frozen=True)
class StrategyCountObservation:
    id: str
    timestamp: int
    interval_end: int
    duration: int
    active_strategy_count: int
    active_strategy_ids: tuple[str, ...]
    active_trade_ids: tuple[str, ...]
    simultaneous_risk: Decimal
    simultaneous_notional_exposure: Decimal | None
    immutable: bool = True


@dataclass(frozen=True)
class StrategyOverlapSnapshot:
    id: str
    scope_id: str
    source_version: str
    calculation_version: str
    historical_version: str
    as_of_time: int
    strategy_ids: tuple[str, ...]
    strategy_count: int
    finalized_trade_count: int
    strategy_pair_count: int
    overlapping_strategy_pair_count: int
    overlap_trade_pair_count: int
    total_pair_overlap_duration: int
    maximum_simultaneous_strategies: int
    maximum_simultaneous_risk: Decimal
    simultaneous_notional_exposure: Decimal | None
    overlaps: tuple[StrategyOverlap, ...]
    strategy_pair_overlaps: tuple[StrategyPairOverlap, ...]
    strategy_count_observations: tuple[StrategyCountObservation, ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    calculation_timestamp: int
    immutable: bool = True


@dataclass(frozen=True)
class OverlapError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class OverlapHistory:
    snapshots: tuple[StrategyOverlapSnapshot, ...] = ()


@dataclass(frozen=True)
class OverlapResult:
    snapshot: StrategyOverlapSnapshot | None
    error: OverlapError | None
    history: OverlapHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class StrategyOverlapEngine:
    """Canonical #29.7.2.18 read-only finalized-trade overlap facts."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.18:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, scope, as_of, history):
        scope_id = scope.id if scope else None
        error = OverlapError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, as_of)
        return OverlapResult(None, error, history)

    def calculate(self, *, scope: OverlapScope | None, trades: tuple[TradeAccounting, ...] | None,
                  as_of_time: int, history: OverlapHistory = OverlapHistory()) -> OverlapResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_OVERLAP_INPUT_MISSING", scope, as_of, history)
        if not scope.immutable or as_of < 0 or not all(str(value).strip() for value in (scope.id, scope.source_version, scope.calculation_version, scope.historical_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "OVERLAP_SCOPE_INVALID", scope, as_of, history)
        trade_ids = tuple(trade.trade_id for trade in trades)
        accounting_ids = tuple(trade.id for trade in trades)
        position_ids = tuple(trade.position_id for trade in trades)
        if any(len(values) != len(set(values)) for values in (trade_ids, accounting_ids, position_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, as_of, history)
        if trades != tuple(sorted(trades, key=lambda trade: (trade.closed_time, trade.trade_id))):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "OVERLAP_TRADE_ORDER_INVALID", scope, as_of, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        eligible = tuple(trade for trade in trades if trade.closed_time <= as_of and trade.accounting_time <= as_of)
        future = tuple(trade.trade_id for trade in trades if trade not in eligible)
        strategies = tuple(sorted({trade.strategy_id for trade in eligible}))
        overlaps = self._overlaps(eligible, as_of)
        pairs = self._pairs(strategies, overlaps, as_of)
        observations = self._observations(eligible)
        maximum_count = max((row.active_strategy_count for row in observations), default=0)
        maximum_risk = max((row.simultaneous_risk for row in observations), default=Decimal(0))
        source_trade_ids = tuple(trade.trade_id for trade in eligible)
        source_accounting_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", scope.id, scope.source_version, scope.calculation_version, scope.historical_version, as_of, *source_accounting_ids)
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return OverlapResult(exact, None, history)
        if any((item.scope_id, item.source_version, item.calculation_version, item.historical_version, item.as_of_time) ==
               (scope.id, scope.source_version, scope.calculation_version, scope.historical_version, as_of) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_OVERLAP_SNAPSHOT", scope, as_of, history)
        snapshot = StrategyOverlapSnapshot(
            snapshot_id, scope.id, scope.source_version, scope.calculation_version, scope.historical_version,
            as_of, strategies, len(strategies), len(eligible), len(pairs), sum(row.co_occurrence for row in pairs),
            len(overlaps), sum(row.total_overlap_duration for row in pairs), maximum_count, maximum_risk, None,
            overlaps, pairs, observations, source_trade_ids, source_accounting_ids, future, as_of,
        )
        return OverlapResult(snapshot, None, OverlapHistory(history.snapshots + (snapshot,)))

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all(str(value).strip() for value in (trade.id, trade.trade_id, trade.position_id, trade.strategy_id, trade.symbol, trade.timeframe, trade.input_version)):
            return "OVERLAP_TRADE_IDENTITY_MISSING"
        if trade.input_version != scope.source_version:
            return "OVERLAP_SOURCE_VERSION_MISMATCH"
        if trade.opened_time < 0 or trade.closed_time < trade.opened_time or trade.accounting_time < trade.closed_time:
            return "OVERLAP_TRADE_CHRONOLOGY_INVALID"
        if trade.trade_result not in tuple(TradeResult):
            return "OVERLAP_ACCOUNTING_RESULT_INVALID"
        try:
            values = tuple(self._decimal(value) for value in (
                trade.quantity, trade.economic_entry_price, trade.economic_exit_price,
                trade.actual_risk_dollars, trade.net_pnl, trade.net_r,
            ))
        except ValueError:
            return "NON_FINITE_OVERLAP_INPUT"
        if values[0] <= 0 or values[1] <= 0 or values[2] <= 0 or values[3] <= 0:
            return "OVERLAP_ACCOUNTING_FACT_INVALID"
        return None

    def _overlaps(self, trades, as_of):
        rows = []
        opened_order = tuple(sorted(trades, key=lambda trade: (trade.opened_time, trade.closed_time, trade.trade_id)))
        for index, left in enumerate(opened_order):
            for right in opened_order[index + 1:]:
                if left.strategy_id == right.strategy_id:
                    continue
                a, b = (left, right) if left.strategy_id < right.strategy_id else (right, left)
                start = max(a.opened_time, b.opened_time)
                end = min(a.closed_time, b.closed_time)
                if start >= end:
                    continue
                rows.append(StrategyOverlap(
                    self._uid("overlap", a.trade_id, b.trade_id, start, end), a.strategy_id, b.strategy_id,
                    a.trade_id, b.trade_id, a.id, b.id, a.position_id, b.position_id,
                    a.symbol, b.symbol, a.timeframe, b.timeframe, a.model, b.model, a.direction, b.direction,
                    start, end, end - start, self._decimal(a.actual_risk_dollars) + self._decimal(b.actual_risk_dollars),
                    None, max(a.accounting_time, b.accounting_time), False, True,
                ))
        return tuple(sorted(rows, key=lambda row: (row.strategy_a_id, row.strategy_b_id, row.overlap_start, row.overlap_end, row.trade_a_id, row.trade_b_id)))

    def _pairs(self, strategies, overlaps, as_of):
        rows = []
        for index, strategy_a in enumerate(strategies):
            for strategy_b in strategies[index + 1:]:
                sources = tuple(row for row in overlaps if (row.strategy_a_id, row.strategy_b_id) == (strategy_a, strategy_b))
                union = []
                for source in sources:
                    if not union or source.overlap_start > union[-1][1]:
                        union.append([source.overlap_start, source.overlap_end, [source.id]])
                    else:
                        union[-1][1] = max(union[-1][1], source.overlap_end)
                        union[-1][2].append(source.id)
                intervals = tuple(UnionOverlapInterval(
                    self._uid("union", strategy_a, strategy_b, start, end, *ids), strategy_a, strategy_b,
                    start, end, end - start, tuple(ids),
                ) for start, end, ids in union)
                total = sum((row.overlap_duration for row in intervals), 0)
                rows.append(StrategyPairOverlap(
                    self._uid("pair", strategy_a, strategy_b, as_of, *(row.id for row in sources)),
                    strategy_a, strategy_b, bool(sources), len(sources), total,
                    intervals[0].overlap_start if intervals else None,
                    intervals[-1].overlap_end if intervals else None,
                    intervals, tuple(row.id for row in sources), False, True,
                ))
        return tuple(rows)

    def _observations(self, trades):
        timestamps = sorted({time for trade in trades if trade.opened_time < trade.closed_time for time in (trade.opened_time, trade.closed_time)})
        rows = []
        for timestamp, interval_end in zip(timestamps, timestamps[1:]):
            if timestamp >= interval_end:
                continue
            active = tuple(sorted((trade for trade in trades if trade.opened_time <= timestamp < trade.closed_time), key=lambda trade: trade.trade_id))
            active_strategies = tuple(sorted({trade.strategy_id for trade in active}))
            rows.append(StrategyCountObservation(
                self._uid("count", timestamp, interval_end, *(trade.trade_id for trade in active)),
                timestamp, interval_end, interval_end - timestamp, len(active_strategies), active_strategies,
                tuple(trade.trade_id for trade in active),
                sum((self._decimal(trade.actual_risk_dollars) for trade in active), Decimal(0)), None,
            ))
        return tuple(rows)
