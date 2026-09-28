from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import CumulativeSnapshot
from strategy.trading_brain.p29_7_2_8_streak_statistics import StreakSnapshot


RESULT_ORDER = (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN)


@dataclass(frozen=True)
class TradeSequenceScope:
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    source_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class TradeSequenceObservation:
    id: str
    sequence: int
    trade_id: str
    accounting_id: str
    setup_id: str
    opened_time: int
    closed_time: int
    trade_result: TradeResult
    net_pnl: Decimal
    gross_pnl: Decimal
    net_r: Decimal
    gross_r: Decimal
    cumulative_point_id: str
    cumulative_net_pnl: Decimal
    cumulative_net_r: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class ResultTransition:
    id: str
    sequence: int
    from_trade_id: str
    to_trade_id: str
    from_result: TradeResult
    to_result: TradeResult
    from_sequence: int
    to_sequence: int
    immutable: bool = True


@dataclass(frozen=True)
class TransitionStatistic:
    id: str
    from_result: TradeResult
    to_result: TradeResult
    transition_count: int
    source_state_outgoing_count: int
    probability: Decimal | None
    transition_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class ResultRun:
    id: str
    sequence: int
    result: TradeResult
    start_sequence: int
    end_sequence: int
    start_time: int
    end_time: int
    length: int
    trade_ids: tuple[str, ...]
    accounting_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class TradeSequenceSnapshot:
    id: str
    scope_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    source_version: str
    calculation_version: str
    historical_version: str
    as_of_time: int
    sequence_length: int
    transition_count: int
    run_count: int
    observations: tuple[TradeSequenceObservation, ...]
    result_sequence: tuple[TradeResult, ...]
    net_pnl_sequence: tuple[Decimal, ...]
    net_r_sequence: tuple[Decimal, ...]
    transitions: tuple[ResultTransition, ...]
    transition_statistics: tuple[TransitionStatistic, ...]
    runs: tuple[ResultRun, ...]
    maximum_winning_run: int
    maximum_losing_run: int
    maximum_winning_streak_trade_id_groups: tuple[tuple[str, ...], ...]
    maximum_losing_streak_trade_id_groups: tuple[tuple[str, ...], ...]
    current_trade_id: str | None
    current_run_id: str | None
    source_accounting_ids: tuple[str, ...]
    source_trade_ids: tuple[str, ...]
    source_cumulative_snapshot_id: str
    source_cumulative_point_ids: tuple[str, ...]
    source_streak_snapshot_id: str
    future_excluded_trade_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class TradeSequenceError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class TradeSequenceHistory:
    snapshots: tuple[TradeSequenceSnapshot, ...] = ()


@dataclass(frozen=True)
class TradeSequenceResult:
    snapshot: TradeSequenceSnapshot | None
    error: TradeSequenceError | None
    history: TradeSequenceHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class TradeSequenceEngine:
    """Canonical #29.7.2.14 finalized trade sequence/path facts."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.14:" + kind + ":" + ":".join(map(str, parts))))

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
        error = TradeSequenceError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return TradeSequenceResult(None, error, history)

    def calculate(
        self, *, scope: TradeSequenceScope | None,
        trades: tuple[TradeAccounting, ...] | None,
        cumulative: CumulativeSnapshot | None,
        streaks: StreakSnapshot | None,
        as_of_time: int,
        history: TradeSequenceHistory = TradeSequenceHistory(),
    ) -> TradeSequenceResult:
        as_of = int(as_of_time)
        if scope is None or trades is None or cumulative is None or streaks is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_TRADE_SEQUENCE_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope(scope, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        trade_ids = [trade.trade_id for trade in trades]
        accounting_ids = [trade.id for trade in trades]
        cumulative_ids = [point.id for point in cumulative.points]
        if len(trade_ids) != len(set(trade_ids)) or len(accounting_ids) != len(set(accounting_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, as_of, history)
        if len(cumulative_ids) != len(set(cumulative_ids)) or len(cumulative.source_trade_ids) != len(set(cumulative.source_trade_ids)) or len(streaks.source_trade_ids) != len(set(streaks.source_trade_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_UPSTREAM_SEQUENCE_KEY", scope, as_of, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        eligible = tuple(sorted((trade for trade in trades if trade.closed_time <= as_of), key=lambda trade: (trade.closed_time, trade.trade_id)))
        future = tuple(sorted(trade.trade_id for trade in trades if trade.closed_time > as_of))
        reason = self._validate_upstream(scope, eligible, future, cumulative, streaks, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)

        observations = []
        try:
            for sequence, (trade, point) in enumerate(zip(eligible, cumulative.points), start=1):
                observations.append(TradeSequenceObservation(
                    self._uid("observation", scope.id, trade.id, point.id), sequence, trade.trade_id,
                    trade.id, trade.setup_id, trade.opened_time, trade.closed_time, trade.trade_result,
                    self._decimal(trade.net_pnl), self._decimal(trade.gross_pnl), self._decimal(trade.net_r),
                    self._decimal(trade.gross_r), point.id, self._decimal(point.cumulative_net_pnl),
                    self._decimal(point.cumulative_net_r),
                ))
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_TRADE_SEQUENCE_INPUT", scope, as_of, history)
        observations = tuple(observations)
        transitions = tuple(ResultTransition(
            self._uid("transition", left.id, right.id), index, left.trade_id, right.trade_id,
            left.trade_result, right.trade_result, left.sequence, right.sequence,
        ) for index, (left, right) in enumerate(zip(observations, observations[1:]), start=1))
        transition_statistics = self._transition_statistics(scope, transitions)
        runs = self._runs(scope, observations)
        source_accounting_ids = tuple(item.accounting_id for item in observations)
        snapshot_id = self._uid(
            "snapshot", scope.id, scope.source_version, scope.historical_version, scope.calculation_version,
            as_of, cumulative.id, streaks.id,
            *((item.accounting_id, item.trade_result.value, item.net_pnl, item.net_r) for item in observations),
        )
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return TradeSequenceResult(exact, None, history)
        if any((item.scope_id, item.as_of_time, item.source_version, item.historical_version, item.calculation_version) == (scope.id, as_of, scope.source_version, scope.historical_version, scope.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_TRADE_SEQUENCE_SNAPSHOT", scope, as_of, history)
        snapshot = TradeSequenceSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.setup_model,
            scope.direction, scope.input_version, scope.source_version, scope.calculation_version,
            scope.historical_version, as_of, len(observations), len(transitions), len(runs), observations,
            tuple(item.trade_result for item in observations), tuple(item.net_pnl for item in observations),
            tuple(item.net_r for item in observations), transitions, transition_statistics, runs,
            streaks.maximum_winning_streak, streaks.maximum_losing_streak,
            streaks.maximum_winning_streak_trade_id_groups, streaks.maximum_losing_streak_trade_id_groups,
            observations[-1].trade_id if observations else None, runs[-1].id if runs else None,
            source_accounting_ids, tuple(item.trade_id for item in observations), cumulative.id,
            tuple(point.id for point in cumulative.points), streaks.id, future,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return TradeSequenceResult(snapshot, None, TradeSequenceHistory(history.snapshots + (snapshot,)))

    def _transition_statistics(self, scope, transitions):
        rows = []
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            for source in RESULT_ORDER:
                outgoing = tuple(item for item in transitions if item.from_result == source)
                denominator = len(outgoing)
                for target in RESULT_ORDER:
                    matching = tuple(item for item in outgoing if item.to_result == target)
                    probability = Decimal(len(matching)) / Decimal(denominator) if denominator else None
                    rows.append(TransitionStatistic(
                        self._uid("transition-statistic", scope.id, source.value, target.value),
                        source, target, len(matching), denominator, probability,
                        tuple(item.id for item in matching),
                    ))
        return tuple(rows)

    def _runs(self, scope, observations):
        groups = []
        current = []
        for item in observations:
            if current and item.trade_result != current[-1].trade_result:
                groups.append(tuple(current))
                current = []
            current.append(item)
        if current:
            groups.append(tuple(current))
        return tuple(ResultRun(
            self._uid("run", scope.id, group[0].accounting_id, group[-1].accounting_id), index,
            group[0].trade_result, group[0].sequence, group[-1].sequence, group[0].closed_time,
            group[-1].closed_time, len(group), tuple(item.trade_id for item in group),
            tuple(item.accounting_id for item in group),
        ) for index, group in enumerate(groups, start=1))

    def _validate_scope(self, scope, as_of):
        if not scope.immutable or as_of < 0 or not all(str(value).strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.source_version, scope.calculation_version, scope.historical_version)):
            return "TRADE_SEQUENCE_SCOPE_INVALID"
        return None

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if (trade.strategy_id, trade.symbol, trade.timeframe.lower(), trade.model, trade.direction, trade.input_version) != (scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version):
            return "TRADE_SEQUENCE_ACCOUNTING_SCOPE_OR_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in RESULT_ORDER:
            return "TRADE_RESULT_INVALID"
        try:
            for value in (trade.net_pnl, trade.gross_pnl, trade.net_r, trade.gross_r):
                self._decimal(value)
        except ValueError:
            return "NON_FINITE_TRADE_SEQUENCE_INPUT"
        return None

    def _validate_upstream(self, scope, eligible, future, cumulative, streaks, as_of):
        if not cumulative.immutable or not streaks.immutable:
            return "NON_FINAL_TRADE_SEQUENCE_UPSTREAM"
        expected_scope = (scope.id, scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version, scope.calculation_version, as_of)
        cumulative_scope = (cumulative.scope_id, cumulative.strategy_id, cumulative.symbol, cumulative.timeframe.lower(), cumulative.setup_model, cumulative.direction, cumulative.input_version, cumulative.calculation_version, cumulative.as_of_time)
        streak_scope = (streaks.scope_id, streaks.strategy_id, streaks.symbol, streaks.timeframe.lower(), streaks.setup_model, streaks.direction, streaks.input_version, streaks.calculation_version, streaks.as_of_time)
        if cumulative_scope != expected_scope:
            return "TRADE_SEQUENCE_CUMULATIVE_SCOPE_OR_VERSION_MISMATCH"
        if streak_scope != expected_scope:
            return "TRADE_SEQUENCE_STREAK_SCOPE_OR_VERSION_MISMATCH"
        trade_ids = tuple(trade.trade_id for trade in eligible)
        accounting_ids = tuple(trade.id for trade in eligible)
        results = tuple(trade.trade_result for trade in eligible)
        if cumulative.trade_count != len(eligible) or cumulative.source_trade_ids != trade_ids or cumulative.source_accounting_ids != accounting_ids or tuple(cumulative.future_excluded_trade_ids) != future:
            return "CUMULATIVE_SEQUENCE_POPULATION_MISMATCH"
        if streaks.trade_count != len(eligible) or streaks.source_trade_ids != trade_ids or streaks.source_accounting_ids != accounting_ids or streaks.source_results != results or tuple(streaks.future_excluded_trade_ids) != future:
            return "STREAK_SEQUENCE_POPULATION_MISMATCH"
        if len(cumulative.points) != len(eligible):
            return "CUMULATIVE_POINT_MISSING"
        prior_pnl = Decimal(0)
        prior_r = Decimal(0)
        try:
            for sequence, (trade, point) in enumerate(zip(eligible, cumulative.points), start=1):
                if not point.immutable or point.sequence != sequence or (point.trade_id, point.accounting_id, point.closed_time) != (trade.trade_id, trade.id, trade.closed_time):
                    return "CUMULATIVE_POINT_IDENTITY_OR_ORDER_MISMATCH"
                net_pnl = self._decimal(point.net_pnl)
                net_r = self._decimal(point.net_r)
                if net_pnl != self._decimal(trade.net_pnl) or net_r != self._decimal(trade.net_r):
                    return "CUMULATIVE_POINT_VALUE_MISMATCH"
                if self._decimal(point.prior_cumulative_net_pnl) != prior_pnl or self._decimal(point.prior_cumulative_net_r) != prior_r:
                    return "CUMULATIVE_PRIOR_VALUE_MISMATCH"
                prior_pnl = self._decimal(point.cumulative_net_pnl)
                prior_r = self._decimal(point.cumulative_net_r)
                if prior_pnl != self._decimal(point.prior_cumulative_net_pnl) + net_pnl or prior_r != self._decimal(point.prior_cumulative_net_r) + net_r:
                    return "CUMULATIVE_TRANSITION_INVALID"
            if self._decimal(cumulative.final_cumulative_net_pnl) != prior_pnl or self._decimal(cumulative.final_cumulative_net_r) != prior_r:
                return "CUMULATIVE_FINAL_VALUE_INVALID"
        except ValueError:
            return "NON_FINITE_TRADE_SEQUENCE_INPUT"
        expected_win_groups = self._result_groups(eligible, TradeResult.WIN)
        expected_loss_groups = self._result_groups(eligible, TradeResult.LOSS)
        max_wins = max(map(len, expected_win_groups), default=0)
        max_losses = max(map(len, expected_loss_groups), default=0)
        max_win_groups = tuple(group for group in expected_win_groups if len(group) == max_wins) if max_wins else ()
        max_loss_groups = tuple(group for group in expected_loss_groups if len(group) == max_losses) if max_losses else ()
        if (streaks.maximum_winning_streak, streaks.maximum_losing_streak, streaks.maximum_winning_streak_trade_id_groups, streaks.maximum_losing_streak_trade_id_groups) != (max_wins, max_losses, max_win_groups, max_loss_groups):
            return "STREAK_FACT_MISMATCH"
        return None

    @staticmethod
    def _result_groups(trades, result):
        groups = []
        current = []
        for trade in trades:
            if trade.trade_result == result:
                current.append(trade.trade_id)
            elif current:
                groups.append(tuple(current))
                current = []
        if current:
            groups.append(tuple(current))
        return tuple(groups)
