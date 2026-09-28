from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import CumulativePoint, CumulativeSnapshot


@dataclass(frozen=True)
class EquityPoint:
    id: str
    sequence: int
    time: int
    trade_id: str
    accounting_id: str
    cumulative_point_id: str
    cumulative_net_pnl: Decimal
    starting_equity: Decimal
    equity: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class EquityCurveSnapshot:
    id: str
    scope_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    calculation_version: str
    as_of_time: int
    starting_equity: Decimal
    trade_count: int
    ending_equity: Decimal
    points: tuple[EquityPoint, ...]
    cumulative_snapshot_id: str
    source_cumulative_point_ids: tuple[str, ...]
    source_trade_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class EquityCurveError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class EquityCurveHistory:
    snapshots: tuple[EquityCurveSnapshot, ...] = ()


@dataclass(frozen=True)
class EquityCurveResult:
    snapshot: EquityCurveSnapshot | None
    error: EquityCurveError | None
    history: EquityCurveHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class EquityCurveEngine:
    """Canonical #29.7.2.6 equity observations sourced only from #29.7.2.5."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.6:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, cumulative, as_of, history):
        scope_id = cumulative.scope_id if cumulative else None
        error = EquityCurveError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return EquityCurveResult(None, error, history)

    def calculate(self, *, cumulative: CumulativeSnapshot | None, starting_equity: Decimal | None, as_of_time: int, history: EquityCurveHistory = EquityCurveHistory()) -> EquityCurveResult:
        as_of = int(as_of_time)
        if cumulative is None or starting_equity is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_EQUITY_INPUT_MISSING", cumulative, as_of, history)
        point_ids = [point.id for point in cumulative.points]
        trade_ids = [point.trade_id for point in cumulative.points]
        accounting_ids = [point.accounting_id for point in cumulative.points]
        if len(point_ids) != len(set(point_ids)) or len(trade_ids) != len(set(trade_ids)) or len(accounting_ids) != len(set(accounting_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CUMULATIVE_POINT", cumulative, as_of, history)
        reason = self._validate_cumulative(cumulative, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, cumulative, as_of, history)
        try:
            initial = self._decimal(starting_equity)
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "STARTING_EQUITY_INVALID", cumulative, as_of, history)
        points = []
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            for point in cumulative.points:
                equity = initial + self._decimal(point.cumulative_net_pnl)
                points.append(EquityPoint(
                    self._uid("point", cumulative.id, initial, point.id), point.sequence,
                    point.closed_time, point.trade_id, point.accounting_id, point.id,
                    point.cumulative_net_pnl, initial, equity,
                ))
            ending_equity = initial + self._decimal(cumulative.final_cumulative_net_pnl)
        snapshot_id = self._uid("snapshot", cumulative.id, initial, as_of)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return EquityCurveResult(exact, None, history)
        if any((snapshot.scope_id, snapshot.as_of_time) == (cumulative.scope_id, as_of) for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_EQUITY_CURVE_SNAPSHOT", cumulative, as_of, history)
        snapshot = EquityCurveSnapshot(
            snapshot_id, cumulative.scope_id, cumulative.strategy_id, cumulative.symbol,
            cumulative.timeframe, cumulative.setup_model, cumulative.direction,
            cumulative.input_version, cumulative.calculation_version, as_of, initial,
            cumulative.trade_count, ending_equity, tuple(points), cumulative.id,
            tuple(point.id for point in cumulative.points), cumulative.source_trade_ids,
            cumulative.future_excluded_trade_ids, "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return EquityCurveResult(snapshot, None, EquityCurveHistory(history.snapshots + (snapshot,)))

    def _validate_cumulative(self, cumulative, as_of):
        if not cumulative.immutable:
            return "NON_FINAL_CUMULATIVE_SNAPSHOT"
        if as_of < 0 or cumulative.as_of_time != as_of:
            return "CUMULATIVE_POINT_IN_TIME_MISMATCH"
        if not all(value.strip() for value in (cumulative.id, cumulative.scope_id, cumulative.strategy_id, cumulative.symbol, cumulative.timeframe, cumulative.input_version, cumulative.calculation_version)):
            return "CUMULATIVE_SCOPE_INVALID"
        if cumulative.starting_cumulative_net_pnl != 0 or cumulative.starting_cumulative_net_r != 0:
            return "CUMULATIVE_ZERO_BASELINE_INVALID"
        if cumulative.trade_count != len(cumulative.points):
            return "CUMULATIVE_POINT_MISSING"
        point_ids = [point.id for point in cumulative.points]
        trade_ids = [point.trade_id for point in cumulative.points]
        accounting_ids = [point.accounting_id for point in cumulative.points]
        if tuple(trade_ids) != cumulative.source_trade_ids or tuple(accounting_ids) != cumulative.source_accounting_ids:
            return "CUMULATIVE_SOURCE_IDENTITY_MISMATCH"
        if tuple(sorted(cumulative.points, key=lambda point: (point.closed_time, point.trade_id))) != cumulative.points:
            return "CUMULATIVE_ORDER_INVALID"
        prior_pnl = Decimal("0")
        prior_r = Decimal("0")
        try:
            for expected_sequence, point in enumerate(cumulative.points, start=1):
                if not point.immutable or point.sequence != expected_sequence:
                    return "CUMULATIVE_POINT_NONCONTIGUOUS"
                if not all((point.id, point.trade_id, point.accounting_id)) or point.closed_time > as_of:
                    return "CUMULATIVE_POINT_IDENTITY_OR_TIME_INVALID"
                net_pnl = self._decimal(point.net_pnl)
                net_r = self._decimal(point.net_r)
                recorded_prior_pnl = self._decimal(point.prior_cumulative_net_pnl)
                recorded_prior_r = self._decimal(point.prior_cumulative_net_r)
                cumulative_pnl = self._decimal(point.cumulative_net_pnl)
                cumulative_r = self._decimal(point.cumulative_net_r)
                if recorded_prior_pnl != prior_pnl or recorded_prior_r != prior_r:
                    return "CUMULATIVE_PRIOR_VALUE_INVALID"
                if cumulative_pnl != prior_pnl + net_pnl or cumulative_r != prior_r + net_r:
                    return "CUMULATIVE_TRANSITION_INVALID"
                prior_pnl, prior_r = cumulative_pnl, cumulative_r
            if self._decimal(cumulative.final_cumulative_net_pnl) != prior_pnl or self._decimal(cumulative.final_cumulative_net_r) != prior_r:
                return "CUMULATIVE_FINAL_VALUE_INVALID"
        except ValueError:
            return "NON_FINITE_CUMULATIVE_VALUE"
        return None
