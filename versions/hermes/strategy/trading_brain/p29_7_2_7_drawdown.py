from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_6_equity_curve import EquityCurveSnapshot, EquityPoint


@dataclass(frozen=True)
class DrawdownPoint:
    id: str
    sequence: int
    time: int
    trade_id: str
    equity_point_id: str
    equity: Decimal
    peak_equity: Decimal
    drawdown_abs: Decimal
    drawdown_pct: Decimal | None
    immutable: bool = True


@dataclass(frozen=True)
class DrawdownSnapshot:
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
    current_peak_equity: Decimal
    current_drawdown_abs: Decimal
    current_drawdown_pct: Decimal | None
    maximum_drawdown_abs: Decimal
    maximum_drawdown_pct: Decimal | None
    maximum_drawdown_abs_point_ids: tuple[str, ...]
    maximum_drawdown_pct_point_ids: tuple[str, ...]
    points: tuple[DrawdownPoint, ...]
    equity_curve_snapshot_id: str
    source_equity_point_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class DrawdownError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class DrawdownHistory:
    snapshots: tuple[DrawdownSnapshot, ...] = ()


@dataclass(frozen=True)
class DrawdownResult:
    snapshot: DrawdownSnapshot | None
    error: DrawdownError | None
    history: DrawdownHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class DrawdownEngine:
    """Canonical #29.7.2.7 peak-to-trough drawdown over #29.7.2.6."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.7:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, curve, as_of, history):
        scope_id = curve.scope_id if curve else None
        error = DrawdownError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return DrawdownResult(None, error, history)

    def calculate(self, *, equity_curve: EquityCurveSnapshot | None, as_of_time: int, history: DrawdownHistory = DrawdownHistory()) -> DrawdownResult:
        as_of = int(as_of_time)
        if equity_curve is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_DRAWDOWN_INPUT_MISSING", equity_curve, as_of, history)
        point_ids = [point.id for point in equity_curve.points]
        trade_ids = [point.trade_id for point in equity_curve.points]
        if len(point_ids) != len(set(point_ids)) or len(trade_ids) != len(set(trade_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_EQUITY_POINT", equity_curve, as_of, history)
        reason = self._validate_curve(equity_curve, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, equity_curve, as_of, history)
        points = []
        peak = self._decimal(equity_curve.starting_equity)
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            for source in equity_curve.points:
                equity = self._decimal(source.equity)
                peak = max(peak, equity)
                absolute = peak - equity
                percentage = absolute / peak * Decimal("100") if peak > 0 else None
                points.append(DrawdownPoint(
                    self._uid("point", equity_curve.id, source.id), source.sequence,
                    source.time, source.trade_id, source.id, equity, peak, absolute,
                    percentage,
                ))
        maximum_abs = max((point.drawdown_abs for point in points), default=Decimal("0"))
        defined_percentages = tuple(point.drawdown_pct for point in points if point.drawdown_pct is not None)
        maximum_pct = max(defined_percentages) if defined_percentages else None
        max_abs_ids = tuple(point.equity_point_id for point in points if point.drawdown_abs == maximum_abs)
        max_pct_ids = tuple(point.equity_point_id for point in points if maximum_pct is not None and point.drawdown_pct == maximum_pct)
        current_abs = points[-1].drawdown_abs if points else Decimal("0")
        current_pct = points[-1].drawdown_pct if points else (Decimal("0") if peak > 0 else None)
        snapshot_id = self._uid("snapshot", equity_curve.id, as_of)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return DrawdownResult(exact, None, history)
        if any((snapshot.scope_id, snapshot.as_of_time) == (equity_curve.scope_id, as_of) for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_DRAWDOWN_SNAPSHOT", equity_curve, as_of, history)
        snapshot = DrawdownSnapshot(
            snapshot_id, equity_curve.scope_id, equity_curve.strategy_id,
            equity_curve.symbol, equity_curve.timeframe, equity_curve.setup_model,
            equity_curve.direction, equity_curve.input_version,
            equity_curve.calculation_version, as_of, equity_curve.starting_equity,
            equity_curve.trade_count, peak, current_abs, current_pct, maximum_abs,
            maximum_pct, max_abs_ids, max_pct_ids, tuple(points), equity_curve.id,
            tuple(point.id for point in equity_curve.points),
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return DrawdownResult(snapshot, None, DrawdownHistory(history.snapshots + (snapshot,)))

    def _validate_curve(self, curve, as_of):
        if not curve.immutable:
            return "NON_FINAL_EQUITY_CURVE"
        if as_of < 0 or curve.as_of_time != as_of:
            return "EQUITY_POINT_IN_TIME_MISMATCH"
        if not all(value.strip() for value in (curve.id, curve.scope_id, curve.strategy_id, curve.symbol, curve.timeframe, curve.input_version, curve.calculation_version, curve.cumulative_snapshot_id)):
            return "EQUITY_SCOPE_INVALID"
        if curve.trade_count != len(curve.points):
            return "EQUITY_POINT_MISSING"
        if tuple(sorted(curve.points, key=lambda point: (point.time, point.trade_id))) != curve.points:
            return "EQUITY_ORDER_INVALID"
        try:
            starting = self._decimal(curve.starting_equity)
            for expected_sequence, point in enumerate(curve.points, start=1):
                if not point.immutable or point.sequence != expected_sequence:
                    return "EQUITY_POINT_NONCONTIGUOUS"
                if not all((point.id, point.trade_id, point.accounting_id, point.cumulative_point_id)) or point.time > as_of:
                    return "EQUITY_POINT_IDENTITY_OR_TIME_INVALID"
                if self._decimal(point.starting_equity) != starting:
                    return "EQUITY_STARTING_VALUE_MISMATCH"
                cumulative = self._decimal(point.cumulative_net_pnl)
                equity = self._decimal(point.equity)
                if equity != starting + cumulative:
                    return "EQUITY_TRANSITION_INVALID"
            ending = self._decimal(curve.ending_equity)
            expected_ending = self._decimal(curve.points[-1].equity) if curve.points else starting
            if ending != expected_ending:
                return "EQUITY_ENDING_VALUE_INVALID"
        except ValueError:
            return "NON_FINITE_EQUITY_VALUE"
        return None
