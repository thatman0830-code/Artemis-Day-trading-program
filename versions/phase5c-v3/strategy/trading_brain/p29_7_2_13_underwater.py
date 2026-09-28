from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_7_drawdown import DrawdownSnapshot
from strategy.trading_brain.p29_7_2_12_recovery import (
    CurrentRecoveryStatus, RecoveryEpisode, RecoveryEpisodeStatus, RecoveryStatisticsSnapshot,
    StartingEquityObservation,
)


@dataclass(frozen=True)
class UnderwaterScope:
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    calculation_version: str
    immutable: bool = True


@dataclass(frozen=True)
class UnderwaterEpisode:
    id: str
    sequence: int
    recovery_episode_id: str
    recovery_episode_key: str
    start_time: int
    end_time: int | None
    episode_peak_equity: Decimal
    peak_time: int
    peak_source_id: str
    trough_equity: Decimal
    trough_time: int
    trough_point_id: str
    recovery_equity: Decimal | None
    recovered: bool
    duration: int | None
    current_duration: int | None
    active: bool
    recovery_depth: Decimal
    recovery_depth_pct: Decimal | None
    contains_maximum_drawdown: bool
    maximum_drawdown_source_point_ids: tuple[str, ...]
    source_drawdown_snapshot_id: str
    source_drawdown_point_ids: tuple[str, ...]
    source_equity_point_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class UnderwaterState:
    id: str
    sequence: int
    timestamp: int
    equity: Decimal
    peak_equity: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal | None
    underwater: bool
    active_episode_id: str | None
    recovery_episode_id: str | None
    underwater_start_time: int | None
    current_time_underwater: int
    source_drawdown_point_id: str | None
    source_equity_point_id: str | None
    immutable: bool = True


@dataclass(frozen=True)
class UnderwaterStatisticsSnapshot:
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
    episode_count: int
    recovered_episode_count: int
    active_episode_count: int
    total_historical_time_underwater: int
    current_time_underwater: int
    maximum_completed_time_underwater: int | None
    maximum_completed_episode_ids: tuple[str, ...]
    average_completed_time_underwater: Decimal | None
    median_completed_time_underwater: Decimal | None
    completed_duration_distribution: tuple[int, ...]
    current_underwater: bool
    active_episode_id: str | None
    episodes: tuple[UnderwaterEpisode, ...]
    states: tuple[UnderwaterState, ...]
    starting_equity_observation_id: str
    source_equity_series_id: str
    source_drawdown_series_id: str
    source_recovery_snapshot_id: str
    source_drawdown_point_ids: tuple[str, ...]
    source_equity_point_ids: tuple[str, ...]
    finalized_observation_time: int
    duration_unit: str
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class UnderwaterError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class UnderwaterHistory:
    snapshots: tuple[UnderwaterStatisticsSnapshot, ...] = ()


@dataclass(frozen=True)
class UnderwaterResult:
    snapshot: UnderwaterStatisticsSnapshot | None
    error: UnderwaterError | None
    history: UnderwaterHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class UnderwaterStatisticsEngine:
    """Canonical #29.7.2.13 underwater observations over #29.7.2.7/.12 facts."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.13:" + kind + ":" + ":".join(map(str, parts))))

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
        error = UnderwaterError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return UnderwaterResult(None, error, history)

    def calculate(
        self, *, scope: UnderwaterScope | None,
        drawdown: DrawdownSnapshot | None,
        recovery: RecoveryStatisticsSnapshot | None,
        starting_equity: StartingEquityObservation | None,
        as_of_time: int,
        history: UnderwaterHistory = UnderwaterHistory(),
    ) -> UnderwaterResult:
        as_of = int(as_of_time)
        if scope is None or drawdown is None or recovery is None or starting_equity is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_UNDERWATER_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope(scope, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        point_ids = [point.id for point in drawdown.points]
        equity_ids = [point.equity_point_id for point in drawdown.points]
        episode_ids = [episode.id for episode in recovery.episodes]
        episode_keys = [episode.episode_key for episode in recovery.episodes]
        if len(point_ids) != len(set(point_ids)) or len(equity_ids) != len(set(equity_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_DRAWDOWN_POINT", scope, as_of, history)
        if len(episode_ids) != len(set(episode_ids)) or len(episode_keys) != len(set(episode_keys)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_RECOVERY_EPISODE", scope, as_of, history)
        reason = self._validate_inputs(scope, drawdown, recovery, starting_equity, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)

        episodes = tuple(self._episode(record, recovery.finalized_observation_time) for record in recovery.episodes)
        episode_by_recovery_id = {item.recovery_episode_id: item for item in episodes}
        source_to_recovery = {}
        for record in recovery.episodes:
            for point_id in record.source_drawdown_point_ids:
                source_to_recovery[point_id] = record

        starting_value = self._decimal(starting_equity.equity)
        states = [UnderwaterState(
            self._uid("state", scope.id, starting_equity.id), 0, starting_equity.time,
            starting_value, starting_value, Decimal(0), Decimal(0) if starting_value > 0 else None,
            False, None, None, None, 0, None, None,
        )]
        for point in drawdown.points:
            underwater = self._decimal(point.drawdown_abs) > 0
            record = source_to_recovery.get(point.id)
            active = episode_by_recovery_id.get(record.id) if record and underwater else None
            states.append(UnderwaterState(
                self._uid("state", scope.id, point.id), point.sequence, point.time,
                self._decimal(point.equity), self._decimal(point.peak_equity), self._decimal(point.drawdown_abs),
                self._decimal(point.drawdown_pct) if point.drawdown_pct is not None else None,
                underwater, active.id if active else None, record.id if record and underwater else None,
                record.drawdown_start_time if record and underwater else None,
                point.time - record.drawdown_start_time if record and underwater else 0,
                point.id, point.equity_point_id,
            ))
        states = tuple(states)

        completed = tuple(item for item in episodes if item.recovered)
        active = tuple(item for item in episodes if item.active)
        durations = tuple(sorted(item.duration for item in completed))
        total_historical = sum(durations)
        current_duration = active[0].current_duration if active else 0
        maximum = max(durations, default=None)
        maximum_ids = tuple(item.id for item in completed if item.duration == maximum) if maximum is not None else ()
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            average = Decimal(total_historical) / Decimal(len(completed)) if completed else None
            median = None
            if durations:
                middle = len(durations) // 2
                median = Decimal(durations[middle]) if len(durations) % 2 else (Decimal(durations[middle - 1]) + Decimal(durations[middle])) / Decimal(2)
        current_underwater = bool(active)
        snapshot_id = self._uid(
            "snapshot", scope.id, drawdown.id, recovery.id, starting_equity.id, as_of,
            *((point.id, point.equity, point.peak_equity, point.drawdown_abs) for point in drawdown.points),
            *((episode.id, episode.status.value, episode.trough_point_id, episode.recovery_point_id) for episode in recovery.episodes),
        )
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return UnderwaterResult(exact, None, history)
        if any((item.scope_id, item.as_of_time, item.input_version, item.calculation_version) == (scope.id, as_of, scope.input_version, scope.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_UNDERWATER_SNAPSHOT", scope, as_of, history)
        snapshot = UnderwaterStatisticsSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.setup_model,
            scope.direction, scope.input_version, scope.calculation_version, as_of, len(episodes),
            len(completed), len(active), total_historical, current_duration, maximum, maximum_ids,
            average, median, durations, current_underwater, active[0].id if active else None,
            episodes, states, starting_equity.id, drawdown.equity_curve_snapshot_id, drawdown.id,
            recovery.id, tuple(point.id for point in drawdown.points), drawdown.source_equity_point_ids,
            recovery.finalized_observation_time, "SECONDS", "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return UnderwaterResult(snapshot, None, UnderwaterHistory(history.snapshots + (snapshot,)))

    def _episode(self, record: RecoveryEpisode, finalized_time: int) -> UnderwaterEpisode:
        active = not record.recovered
        current_duration = finalized_time - record.drawdown_start_time if active else None
        return UnderwaterEpisode(
            self._uid("episode", record.id), record.sequence, record.id, record.episode_key,
            record.drawdown_start_time, record.recovery_time, record.peak_equity, record.peak_time,
            record.peak_source_id, record.trough_equity, record.trough_time, record.trough_point_id,
            record.recovery_equity, record.recovered, record.recovery_duration, current_duration, active,
            record.recovery_depth, record.recovery_depth_pct, record.contains_maximum_drawdown,
            record.maximum_drawdown_source_point_ids, record.source_drawdown_snapshot_id,
            record.source_drawdown_point_ids, record.source_equity_point_ids,
        )

    def _validate_scope(self, scope, as_of):
        if not scope.immutable or as_of < 0 or not all(str(value).strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return "UNDERWATER_SCOPE_INVALID"
        return None

    def _validate_inputs(self, scope, drawdown, recovery, starting, as_of):
        if not drawdown.immutable or not recovery.immutable or not starting.immutable:
            return "NON_FINAL_UNDERWATER_SOURCE"
        if drawdown.as_of_time != as_of or recovery.as_of_time != as_of:
            return "UNDERWATER_POINT_IN_TIME_MISMATCH"
        expected_scope = (scope.id, scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version, scope.calculation_version)
        if (drawdown.scope_id, drawdown.strategy_id, drawdown.symbol, drawdown.timeframe.lower(), drawdown.setup_model, drawdown.direction, drawdown.input_version, drawdown.calculation_version) != expected_scope:
            return "UNDERWATER_DRAWDOWN_SCOPE_OR_VERSION_MISMATCH"
        if (recovery.scope_id, recovery.strategy_id, recovery.symbol, recovery.timeframe.lower(), recovery.setup_model, recovery.direction, recovery.input_version, recovery.calculation_version) != expected_scope:
            return "UNDERWATER_RECOVERY_SCOPE_OR_VERSION_MISMATCH"
        if recovery.source_drawdown_series_id != drawdown.id or recovery.source_equity_series_id != drawdown.equity_curve_snapshot_id:
            return "UNDERWATER_SOURCE_SERIES_MISMATCH"
        if recovery.starting_equity_observation_id != starting.id or starting.equity_curve_snapshot_id != drawdown.equity_curve_snapshot_id:
            return "UNDERWATER_STARTING_EQUITY_IDENTITY_MISMATCH"
        if recovery.source_drawdown_point_ids != tuple(point.id for point in drawdown.points) or recovery.source_equity_point_ids != drawdown.source_equity_point_ids:
            return "UNDERWATER_SOURCE_POINT_IDENTITY_MISMATCH"
        if recovery.finalized_observation_time != (drawdown.points[-1].time if drawdown.points else starting.time):
            return "UNDERWATER_FINALIZED_TIME_MISMATCH"
        if drawdown.trade_count != len(drawdown.points) or tuple(sorted(drawdown.points, key=lambda point: (point.time, point.trade_id))) != drawdown.points:
            return "UNDERWATER_DRAWDOWN_ORDER_OR_COMPLETENESS_INVALID"
        try:
            if self._decimal(starting.equity) != self._decimal(drawdown.starting_equity):
                return "UNDERWATER_STARTING_EQUITY_VALUE_MISMATCH"
            if starting.time > recovery.finalized_observation_time or starting.time > as_of:
                return "UNDERWATER_STARTING_EQUITY_CHRONOLOGY_INVALID"
            for expected, point in enumerate(drawdown.points, start=1):
                if not point.immutable or point.sequence != expected or point.time > as_of:
                    return "UNDERWATER_DRAWDOWN_POINT_INVALID"
                equity = self._decimal(point.equity)
                peak = self._decimal(point.peak_equity)
                absolute = self._decimal(point.drawdown_abs)
                if equity > peak or absolute < 0 or absolute != peak - equity:
                    return "UNDERWATER_DRAWDOWN_FACT_INVALID"
                self._decimal(point.drawdown_pct) if point.drawdown_pct is not None else None
            reason = self._validate_recovery_episodes(recovery, drawdown, as_of)
            if reason:
                return reason
        except ValueError:
            return "NON_FINITE_UNDERWATER_INPUT"
        return None

    def _validate_recovery_episodes(self, recovery, drawdown, as_of):
        if recovery.total_drawdowns != len(recovery.episodes):
            return "RECOVERY_EPISODE_COUNT_MISMATCH"
        recovered = tuple(item for item in recovery.episodes if item.recovered)
        active = tuple(item for item in recovery.episodes if not item.recovered)
        if recovery.recovered_drawdowns != len(recovered) or recovery.unrecovered_drawdowns != len(active) or len(active) > 1:
            return "RECOVERY_EPISODE_STATE_COUNT_MISMATCH"
        point_by_id = {point.id: point for point in drawdown.points}
        previous_end_index = None
        drawdown_indices = {point.id: index for index, point in enumerate(drawdown.points)}
        covered_point_ids = []
        for expected, episode in enumerate(recovery.episodes, start=1):
            if not episode.immutable or episode.sequence != expected or episode.source_drawdown_snapshot_id != drawdown.id:
                return "RECOVERY_EPISODE_IDENTITY_INVALID"
            if not episode.source_drawdown_point_ids or any(point_id not in point_by_id for point_id in episode.source_drawdown_point_ids):
                return "RECOVERY_EPISODE_SOURCE_MISSING"
            points = tuple(point_by_id[point_id] for point_id in episode.source_drawdown_point_ids)
            covered_point_ids.extend(episode.source_drawdown_point_ids)
            if tuple(point.id for point in drawdown.points if point.id in set(episode.source_drawdown_point_ids)) != episode.source_drawdown_point_ids:
                return "RECOVERY_EPISODE_SOURCE_ORDER_INVALID"
            start_index = drawdown_indices[points[0].id]
            end_index = drawdown_indices[points[-1].id]
            if end_index - start_index + 1 != len(points):
                return "RECOVERY_EPISODE_SOURCE_NONCONTIGUOUS"
            if previous_end_index is not None and start_index <= previous_end_index:
                return "OVERLAPPING_RECOVERY_EPISODES"
            if episode.drawdown_start_point_id != points[0].id or episode.drawdown_start_time != points[0].time:
                return "RECOVERY_EPISODE_START_MISMATCH"
            if points[0].drawdown_abs <= 0:
                return "RECOVERY_EPISODE_WITHOUT_DRAWDOWN"
            trough_candidates = points[:-1] if episode.recovered else points
            trough = min(trough_candidates, key=lambda point: point.equity)
            if episode.trough_point_id != trough.id or episode.trough_time != trough.time:
                return "RECOVERY_EPISODE_TROUGH_MISMATCH"
            try:
                if self._decimal(episode.peak_equity) != self._decimal(points[0].peak_equity):
                    return "RECOVERY_EPISODE_PEAK_MISMATCH"
                if self._decimal(episode.trough_equity) != self._decimal(trough.equity) or self._decimal(episode.recovery_depth) != self._decimal(trough.drawdown_abs):
                    return "RECOVERY_EPISODE_DEPTH_MISMATCH"
                recorded_pct = self._decimal(episode.recovery_depth_pct) if episode.recovery_depth_pct is not None else None
                trough_pct = self._decimal(trough.drawdown_pct) if trough.drawdown_pct is not None else None
                if recorded_pct != trough_pct:
                    return "RECOVERY_EPISODE_PERCENTAGE_MISMATCH"
            except ValueError:
                return "NON_FINITE_UNDERWATER_INPUT"
            if episode.source_equity_point_ids != tuple(point.equity_point_id for point in points):
                return "RECOVERY_EPISODE_EQUITY_LINEAGE_MISMATCH"
            expected_maximum_ids = tuple(point.equity_point_id for point in points if point.equity_point_id in set(drawdown.maximum_drawdown_abs_point_ids))
            if episode.maximum_drawdown_source_point_ids != expected_maximum_ids or episode.contains_maximum_drawdown != bool(expected_maximum_ids):
                return "RECOVERY_EPISODE_MAXIMUM_LINEAGE_MISMATCH"
            if episode.recovered:
                if episode.status != RecoveryEpisodeStatus.RECOVERED or episode.recovery_point_id != points[-1].id or episode.recovery_time != points[-1].time or episode.recovery_duration != episode.recovery_time - episode.drawdown_start_time:
                    return "RECOVERY_EPISODE_TERMINAL_MISMATCH"
                if self._decimal(episode.recovery_equity) != self._decimal(points[-1].equity) or episode.recovery_equity < episode.peak_equity:
                    return "RECOVERY_EPISODE_RECOVERY_VALUE_MISMATCH"
                previous_end_index = end_index
            else:
                if episode.status != RecoveryEpisodeStatus.UNRECOVERED or any(value is not None for value in (episode.recovery_point_id, episode.recovery_time, episode.recovery_duration)):
                    return "RECOVERY_EPISODE_OPEN_STATE_INVALID"
                if expected != len(recovery.episodes):
                    return "NONTERMINAL_UNRECOVERED_EPISODE"
                previous_end_index = end_index
        if len(covered_point_ids) != len(set(covered_point_ids)):
            return "OVERLAPPING_RECOVERY_EPISODE_SOURCES"
        if any(point.drawdown_abs > 0 and point.id not in set(covered_point_ids) for point in drawdown.points):
            return "RECOVERY_EPISODE_COVERAGE_MISSING"
        completed_durations = tuple(item.recovery_duration for item in recovered)
        expected_ratio = Decimal(len(recovered)) / Decimal(len(recovery.episodes)) if recovery.episodes else None
        expected_average = sum((Decimal(value) for value in completed_durations), Decimal(0)) / Decimal(len(completed_durations)) if completed_durations else None
        expected_maximum = max(completed_durations, default=None)
        if recovery.recovery_ratio != expected_ratio or recovery.average_recovery_duration != expected_average or recovery.maximum_recovery_duration != expected_maximum:
            return "RECOVERY_AGGREGATE_MISMATCH"
        if active:
            expected_status = CurrentRecoveryStatus.UNDERWATER
            expected_current_id = active[0].id
            expected_current_duration = as_of - active[0].drawdown_start_time
        elif recovered:
            expected_status = CurrentRecoveryStatus.RECOVERED
            expected_current_id = None
            expected_current_duration = None
        else:
            expected_status = CurrentRecoveryStatus.NO_ACTIVE_DRAWDOWN
            expected_current_id = None
            expected_current_duration = None
        if (recovery.current_recovery_status, recovery.current_drawdown_episode_id, recovery.current_unrecovered_duration) != (expected_status, expected_current_id, expected_current_duration):
            return "RECOVERY_CURRENT_STATE_MISMATCH"
        return None
