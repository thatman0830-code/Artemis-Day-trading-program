from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_7_drawdown import DrawdownPoint, DrawdownSnapshot


class RecoveryEpisodeStatus(str, Enum):
    RECOVERED = "RECOVERED"
    UNRECOVERED = "UNRECOVERED"


class CurrentRecoveryStatus(str, Enum):
    NO_ACTIVE_DRAWDOWN = "NO_ACTIVE_DRAWDOWN"
    UNDERWATER = "UNDERWATER"
    RECOVERED = "RECOVERED"


@dataclass(frozen=True)
class RecoveryScope:
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
class StartingEquityObservation:
    id: str
    time: int
    equity: Decimal
    equity_curve_snapshot_id: str
    immutable: bool = True


@dataclass(frozen=True)
class RecoveryEpisode:
    id: str
    episode_key: str
    sequence: int
    status: RecoveryEpisodeStatus
    peak_equity: Decimal
    peak_time: int
    peak_source_id: str
    drawdown_start_equity: Decimal
    drawdown_start_time: int
    drawdown_start_point_id: str
    trough_equity: Decimal
    trough_time: int
    trough_point_id: str
    recovery_equity: Decimal | None
    recovery_time: int | None
    recovery_point_id: str | None
    recovery_depth: Decimal
    recovery_depth_pct: Decimal | None
    recovery_duration: int | None
    recovered: bool
    contains_maximum_drawdown: bool
    maximum_drawdown_source_point_ids: tuple[str, ...]
    source_drawdown_snapshot_id: str
    source_drawdown_point_ids: tuple[str, ...]
    source_equity_point_ids: tuple[str, ...]
    creation_time: int
    finalized_time: int | None
    immutable: bool = True


@dataclass(frozen=True)
class RecoveryStatisticsSnapshot:
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
    starting_equity_observation_id: str
    total_drawdowns: int
    recovered_drawdowns: int
    unrecovered_drawdowns: int
    recovery_ratio: Decimal | None
    average_recovery_duration: Decimal | None
    maximum_recovery_duration: int | None
    maximum_recovery_episode_ids: tuple[str, ...]
    current_recovery_status: CurrentRecoveryStatus
    current_unrecovered_duration: int | None
    current_drawdown_episode_id: str | None
    finalized_observation_time: int
    episodes: tuple[RecoveryEpisode, ...]
    source_equity_series_id: str
    source_drawdown_series_id: str
    source_drawdown_point_ids: tuple[str, ...]
    source_equity_point_ids: tuple[str, ...]
    rounding_mode: str
    duration_unit: str
    immutable: bool = True


@dataclass(frozen=True)
class RecoveryError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class RecoveryHistory:
    snapshots: tuple[RecoveryStatisticsSnapshot, ...] = ()


@dataclass(frozen=True)
class RecoveryResult:
    snapshot: RecoveryStatisticsSnapshot | None
    error: RecoveryError | None
    history: RecoveryHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class RecoveryStatisticsEngine:
    """Canonical #29.7.2.12 recovery episodes over authoritative #29.7.2.7 facts."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.12:" + kind + ":" + ":".join(map(str, parts))))

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
        error = RecoveryError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return RecoveryResult(None, error, history)

    def calculate(
        self, *, scope: RecoveryScope | None,
        drawdown: DrawdownSnapshot | None,
        starting_equity: StartingEquityObservation | None,
        as_of_time: int,
        history: RecoveryHistory = RecoveryHistory(),
    ) -> RecoveryResult:
        as_of = int(as_of_time)
        if scope is None or drawdown is None or starting_equity is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_RECOVERY_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope(scope, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        ids = [point.id for point in drawdown.points]
        trade_ids = [point.trade_id for point in drawdown.points]
        equity_ids = [point.equity_point_id for point in drawdown.points]
        if len(ids) != len(set(ids)) or len(trade_ids) != len(set(trade_ids)) or len(equity_ids) != len(set(equity_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_DRAWDOWN_POINT", scope, as_of, history)
        reason = self._validate_drawdown(scope, drawdown, starting_equity, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)

        episode_builders = []
        active = None
        latest_peak_equity = self._decimal(starting_equity.equity)
        latest_peak_time = int(starting_equity.time)
        latest_peak_source_id = starting_equity.id
        maximum_sources = set(drawdown.maximum_drawdown_abs_point_ids)

        for point in drawdown.points:
            equity = self._decimal(point.equity)
            if active is None:
                if point.drawdown_abs > 0:
                    active = {
                        "peak_equity": self._decimal(point.peak_equity),
                        "peak_time": latest_peak_time,
                        "peak_source_id": latest_peak_source_id,
                        "start": point,
                        "trough": point,
                        "points": [point],
                    }
                else:
                    latest_peak_equity = equity
                    latest_peak_time = point.time
                    latest_peak_source_id = point.id
                continue

            active["points"].append(point)
            if equity >= active["peak_equity"]:
                episode_builders.append((active, point))
                active = None
                latest_peak_equity = equity
                latest_peak_time = point.time
                latest_peak_source_id = point.id
            elif equity < active["trough"].equity:
                active["trough"] = point

        if active is not None:
            episode_builders.append((active, None))

        episodes = []
        for sequence, (builder, recovery) in enumerate(episode_builders, start=1):
            start = builder["start"]
            trough = builder["trough"]
            source_points = tuple(builder["points"])
            recovered = recovery is not None
            status = RecoveryEpisodeStatus.RECOVERED if recovered else RecoveryEpisodeStatus.UNRECOVERED
            duration = recovery.time - start.time if recovered else None
            episode_key = self._uid("episode-key", scope.id, builder["peak_source_id"], start.id)
            episode_id = self._uid(
                "episode", episode_key, status.value, trough.id,
                recovery.id if recovery else "OPEN", recovery.time if recovery else as_of,
            )
            maximum_ids = tuple(point.equity_point_id for point in source_points if point.equity_point_id in maximum_sources)
            episodes.append(RecoveryEpisode(
                episode_id, episode_key, sequence, status, builder["peak_equity"], builder["peak_time"],
                builder["peak_source_id"], self._decimal(start.equity), start.time, start.id,
                self._decimal(trough.equity), trough.time, trough.id,
                self._decimal(recovery.equity) if recovery else None, recovery.time if recovery else None,
                recovery.id if recovery else None, self._decimal(trough.drawdown_abs),
                self._decimal(trough.drawdown_pct) if trough.drawdown_pct is not None else None,
                duration, recovered, bool(maximum_ids), maximum_ids, drawdown.id,
                tuple(point.id for point in source_points), tuple(point.equity_point_id for point in source_points),
                start.time, recovery.time if recovery else None,
            ))

        episodes = tuple(episodes)
        recovered_episodes = tuple(item for item in episodes if item.recovered)
        total = len(episodes)
        recovered_count = len(recovered_episodes)
        unrecovered_count = total - recovered_count
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            ratio = Decimal(recovered_count) / Decimal(total) if total else None
            average = sum((Decimal(item.recovery_duration) for item in recovered_episodes), Decimal(0)) / Decimal(recovered_count) if recovered_count else None
        maximum = max((item.recovery_duration for item in recovered_episodes), default=None)
        maximum_ids = tuple(item.id for item in recovered_episodes if item.recovery_duration == maximum) if maximum is not None else ()
        if episodes and not episodes[-1].recovered:
            current_status = CurrentRecoveryStatus.UNDERWATER
            current_id = episodes[-1].id
            current_duration = as_of - episodes[-1].drawdown_start_time
        elif episodes:
            current_status = CurrentRecoveryStatus.RECOVERED
            current_id = None
            current_duration = None
        else:
            current_status = CurrentRecoveryStatus.NO_ACTIVE_DRAWDOWN
            current_id = None
            current_duration = None
        finalized_observation_time = drawdown.points[-1].time if drawdown.points else starting_equity.time
        snapshot_id = self._uid(
            "snapshot", scope.id, drawdown.id, starting_equity.id, starting_equity.equity, as_of,
            *((point.id, point.equity, point.peak_equity, point.drawdown_abs, point.drawdown_pct) for point in drawdown.points),
        )
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return RecoveryResult(exact, None, history)
        if any((item.scope_id, item.as_of_time, item.input_version, item.calculation_version) == (scope.id, as_of, scope.input_version, scope.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_RECOVERY_SNAPSHOT", scope, as_of, history)
        snapshot = RecoveryStatisticsSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.setup_model,
            scope.direction, scope.input_version, scope.calculation_version, as_of, starting_equity.id,
            total, recovered_count, unrecovered_count, ratio, average, maximum, maximum_ids,
            current_status, current_duration, current_id, finalized_observation_time, episodes,
            drawdown.equity_curve_snapshot_id, drawdown.id, tuple(point.id for point in drawdown.points),
            drawdown.source_equity_point_ids, "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS", "SECONDS",
        )
        return RecoveryResult(snapshot, None, RecoveryHistory(history.snapshots + (snapshot,)))

    def _validate_scope(self, scope, as_of):
        if not scope.immutable or as_of < 0 or not all(str(value).strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return "RECOVERY_SCOPE_INVALID"
        return None

    def _validate_drawdown(self, scope, drawdown, starting, as_of):
        if not drawdown.immutable or drawdown.as_of_time != as_of:
            return "DRAWDOWN_POINT_IN_TIME_MISMATCH"
        if (drawdown.scope_id, drawdown.strategy_id, drawdown.symbol, drawdown.timeframe.lower(), drawdown.setup_model, drawdown.direction, drawdown.input_version, drawdown.calculation_version) != (scope.id, scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version, scope.calculation_version):
            return "RECOVERY_DRAWDOWN_SCOPE_OR_VERSION_MISMATCH"
        if not all((drawdown.id, drawdown.equity_curve_snapshot_id)) or drawdown.trade_count != len(drawdown.points):
            return "DRAWDOWN_SOURCE_INVALID_OR_INCOMPLETE"
        if not starting.immutable or not starting.id or starting.equity_curve_snapshot_id != drawdown.equity_curve_snapshot_id or starting.time < 0 or starting.time > as_of:
            return "STARTING_EQUITY_OBSERVATION_INVALID"
        try:
            starting_value = self._decimal(starting.equity)
            if starting_value != self._decimal(drawdown.starting_equity):
                return "STARTING_EQUITY_VALUE_MISMATCH"
            if drawdown.points and starting.time > drawdown.points[0].time:
                return "STARTING_EQUITY_CHRONOLOGY_INVALID"
            if tuple(sorted(drawdown.points, key=lambda point: (point.time, point.trade_id))) != drawdown.points:
                return "DRAWDOWN_POINT_ORDER_INVALID"
            if tuple(point.equity_point_id for point in drawdown.points) != drawdown.source_equity_point_ids:
                return "DRAWDOWN_SOURCE_IDENTITY_MISMATCH"
            prior_peak = starting_value
            for expected, point in enumerate(drawdown.points, start=1):
                if not point.immutable or point.sequence != expected:
                    return "DRAWDOWN_POINT_NONCONTIGUOUS"
                if not all((point.id, point.trade_id, point.equity_point_id)) or point.time > as_of:
                    return "DRAWDOWN_POINT_IDENTITY_OR_TIME_INVALID"
                equity = self._decimal(point.equity)
                peak = self._decimal(point.peak_equity)
                absolute = self._decimal(point.drawdown_abs)
                percentage = self._decimal(point.drawdown_pct) if point.drawdown_pct is not None else None
                if peak < prior_peak or equity > peak or absolute < 0 or absolute != peak - equity:
                    return "DRAWDOWN_POINT_FACT_INVALID"
                if peak > 0:
                    if percentage != absolute / peak * Decimal(100):
                        return "DRAWDOWN_PERCENTAGE_FACT_INVALID"
                elif percentage is not None:
                    return "NONPOSITIVE_PEAK_PERCENTAGE_INVALID"
                prior_peak = peak
            if self._decimal(drawdown.current_peak_equity) != prior_peak:
                return "DRAWDOWN_CURRENT_PEAK_MISMATCH"
            expected_current = self._decimal(drawdown.points[-1].drawdown_abs) if drawdown.points else Decimal(0)
            if self._decimal(drawdown.current_drawdown_abs) != expected_current:
                return "DRAWDOWN_CURRENT_VALUE_MISMATCH"
            maximum = max((self._decimal(point.drawdown_abs) for point in drawdown.points), default=Decimal(0))
            if self._decimal(drawdown.maximum_drawdown_abs) != maximum:
                return "DRAWDOWN_MAXIMUM_VALUE_MISMATCH"
            expected_maximum_ids = tuple(point.equity_point_id for point in drawdown.points if point.drawdown_abs == maximum)
            if drawdown.maximum_drawdown_abs_point_ids != expected_maximum_ids:
                return "DRAWDOWN_MAXIMUM_LINEAGE_MISMATCH"
        except ValueError:
            return "NON_FINITE_DRAWDOWN_INPUT"
        return None
