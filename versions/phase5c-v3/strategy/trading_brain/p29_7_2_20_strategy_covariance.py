from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import StrategyPeriodReturnObservation


class CovarianceMode(str, Enum):
    FULL_HISTORY = "FULL_HISTORY"
    EXPANDING = "EXPANDING"
    ROLLING = "ROLLING"


class CovarianceStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"


@dataclass(frozen=True)
class CovarianceUniverseMember:
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    immutable: bool = True


@dataclass(frozen=True)
class CovarianceUniverse:
    id: str
    version: str
    members: tuple[CovarianceUniverseMember, ...]
    period_type: PeriodType
    account_timezone: str
    source_version: str
    strategy_calculation_version: str
    calculation_version: str
    historical_version: str
    calculation_mode: CovarianceMode
    window_size: int | None
    immutable: bool = True


@dataclass(frozen=True)
class CovarianceAlignedPair:
    id: str
    sequence: int
    period_start: int
    period_end: int
    net_r_a: Decimal
    net_r_b: Decimal
    observation_a_id: str
    observation_b_id: str
    period_a_id: str
    period_b_id: str
    source_period_snapshot_a_id: str
    source_period_snapshot_b_id: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyCovariance:
    id: str
    universe_id: str
    universe_version: str
    strategy_a_id: str
    strategy_b_id: str
    observation_start: int | None
    observation_end: int | None
    observation_count: int
    mean_return_a: Decimal | None
    mean_return_b: Decimal | None
    variance_a: Decimal | None
    variance_b: Decimal | None
    covariance: Decimal | None
    status: CovarianceStatus
    calculation_mode: CovarianceMode
    window_size: int | None
    aligned_pairs: tuple[CovarianceAlignedPair, ...]
    source_observation_a_ids: tuple[str, ...]
    source_observation_b_ids: tuple[str, ...]
    missing_period_end_ids_a: tuple[int, ...]
    missing_period_end_ids_b: tuple[int, ...]
    created_time: int
    as_of_time: int
    source_version: str
    calculation_version: str
    historical_version: str
    active: bool
    historical: bool
    immutable: bool = True


@dataclass(frozen=True)
class CovarianceMatrixCell:
    id: str
    row_index: int
    column_index: int
    row_strategy_id: str
    column_strategy_id: str
    canonical_strategy_a_id: str
    canonical_strategy_b_id: str
    covariance_record_id: str
    covariance: Decimal | None
    observation_count: int
    status: CovarianceStatus
    diagonal: bool
    immutable: bool = True


@dataclass(frozen=True)
class StrategyCovarianceMatrix:
    id: str
    universe_id: str
    universe_version: str
    universe_members: tuple[CovarianceUniverseMember, ...]
    strategy_ids: tuple[str, ...]
    covariance_records: tuple[StrategyCovariance, ...]
    covariance_cells: tuple[CovarianceMatrixCell, ...]
    observation_start: int | None
    observation_end: int | None
    calculation_mode: CovarianceMode
    window_size: int | None
    complete: bool
    as_of_time: int
    account_timezone: str
    period_type: PeriodType
    source_version: str
    strategy_calculation_version: str
    calculation_version: str
    historical_version: str
    source_observation_ids: tuple[str, ...]
    future_excluded_observation_ids: tuple[str, ...]
    active: bool
    historical: bool
    immutable: bool = True


@dataclass(frozen=True)
class CovarianceError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    universe_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class CovarianceHistory:
    matrices: tuple[StrategyCovarianceMatrix, ...] = ()


@dataclass(frozen=True)
class CovarianceResult:
    matrix: StrategyCovarianceMatrix | None
    error: CovarianceError | None
    history: CovarianceHistory

    @property
    def valid(self) -> bool:
        return self.matrix is not None and self.error is None


class StrategyCovarianceEngine:
    """Canonical #29.7.2.20 pairwise-complete sample covariance matrix."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.20:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, universe, as_of, history):
        universe_id = universe.id if universe else None
        error = CovarianceError(self._uid("error", universe_id or "NONE", code.value, reason, as_of), code, reason, universe_id, as_of)
        return CovarianceResult(None, error, history)

    def calculate(self, *, universe: CovarianceUniverse | None,
                  observations: tuple[StrategyPeriodReturnObservation, ...] | None,
                  as_of_time: int, history: CovarianceHistory = CovarianceHistory()) -> CovarianceResult:
        as_of = int(as_of_time)
        if universe is None or observations is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_COVARIANCE_INPUT_MISSING", universe, as_of, history)
        reason = self._validate_universe(universe, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, universe, as_of, history)
        for matrix in history.matrices:
            size = len(matrix.strategy_ids)
            if (not matrix.immutable or not matrix.complete or
                    len(matrix.covariance_records) != size * (size + 1) // 2 or
                    len(matrix.covariance_cells) != size * size):
                return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "COVARIANCE_MATRIX_INCOMPLETE", universe, as_of, history)
            for cell in matrix.covariance_cells:
                reverse = matrix.covariance_cells[cell.column_index * size + cell.row_index]
                if cell.covariance != reverse.covariance or cell.covariance_record_id != reverse.covariance_record_id:
                    return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "COVARIANCE_MATRIX_ASYMMETRIC", universe, as_of, history)
        ids = tuple(item.id for item in observations)
        keys = tuple((item.strategy_id, item.period_end, item.source_version) for item in observations)
        if len(ids) != len(set(ids)) or len(keys) != len(set(keys)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_STRATEGY_PERIOD_OBSERVATION", universe, as_of, history)
        if observations != tuple(sorted(observations, key=lambda item: (item.period_end, item.strategy_id, item.id))):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "COVARIANCE_OBSERVATION_ORDER_INVALID", universe, as_of, history)
        members = {member.strategy_id: member for member in universe.members}
        for item in observations:
            reason = self._validate_observation(universe, members, item)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, universe, as_of, history)
        eligible = tuple(item for item in observations if item.period_end <= as_of and item.finalized_time <= as_of)
        future = tuple(item.id for item in observations if item not in eligible)
        by_strategy = {strategy_id: {item.period_end: item for item in eligible if item.strategy_id == strategy_id} for strategy_id in members}
        records = []
        strategy_ids = tuple(members)
        for row, strategy_a in enumerate(strategy_ids):
            for strategy_b in strategy_ids[row:]:
                built = self._record(universe, strategy_a, strategy_b, by_strategy, as_of)
                if isinstance(built, str):
                    return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, built, universe, as_of, history)
                records.append(built)
        records_tuple = tuple(records)
        record_map = {(record.strategy_a_id, record.strategy_b_id): record for record in records_tuple}
        cells = []
        for row_index, row_strategy in enumerate(strategy_ids):
            for column_index, column_strategy in enumerate(strategy_ids):
                key = tuple(sorted((row_strategy, column_strategy)))
                record = record_map[key]
                cells.append(CovarianceMatrixCell(
                    self._uid("cell", universe.id, universe.version, row_strategy, column_strategy, as_of),
                    row_index, column_index, row_strategy, column_strategy, key[0], key[1], record.id,
                    record.covariance, record.observation_count, record.status, row_strategy == column_strategy,
                ))
        cells_tuple = tuple(cells)
        expected_records = len(strategy_ids) * (len(strategy_ids) + 1) // 2
        expected_cells = len(strategy_ids) ** 2
        complete = len(records_tuple) == expected_records and len(cells_tuple) == expected_cells
        if not complete:
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "COVARIANCE_MATRIX_INCOMPLETE", universe, as_of, history)
        for cell in cells_tuple:
            reverse = cells_tuple[cell.column_index * len(strategy_ids) + cell.row_index]
            if cell.covariance != reverse.covariance or cell.covariance_record_id != reverse.covariance_record_id:
                return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "COVARIANCE_MATRIX_ASYMMETRIC", universe, as_of, history)
        matrix_id = self._uid("matrix", universe.id, universe.version, universe.calculation_version, as_of, *(item.id for item in eligible))
        exact = next((item for item in history.matrices if item.id == matrix_id), None)
        if exact:
            return CovarianceResult(exact, None, history)
        if any((item.universe_id, item.universe_version, item.as_of_time, item.source_version, item.calculation_version, item.historical_version) ==
               (universe.id, universe.version, as_of, universe.source_version, universe.calculation_version, universe.historical_version)
               for item in history.matrices):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_COVARIANCE_MATRIX", universe, as_of, history)
        starts = tuple(record.observation_start for record in records_tuple if record.observation_start is not None)
        ends = tuple(record.observation_end for record in records_tuple if record.observation_end is not None)
        matrix = StrategyCovarianceMatrix(
            matrix_id, universe.id, universe.version, universe.members, strategy_ids, records_tuple, cells_tuple,
            min(starts) if starts else None, max(ends) if ends else None, universe.calculation_mode,
            universe.window_size, True, as_of, universe.account_timezone, universe.period_type,
            universe.source_version, universe.strategy_calculation_version, universe.calculation_version,
            universe.historical_version, tuple(item.id for item in eligible), future, False, True,
        )
        return CovarianceResult(matrix, None, CovarianceHistory(history.matrices + (matrix,)))

    def _record(self, universe, strategy_a, strategy_b, by_strategy, as_of):
        ends_a = set(by_strategy[strategy_a]); ends_b = set(by_strategy[strategy_b])
        common = sorted(ends_a & ends_b)
        if universe.calculation_mode == CovarianceMode.ROLLING:
            common = common[-universe.window_size:]
        aligned = []
        for sequence, period_end in enumerate(common, start=1):
            a = by_strategy[strategy_a][period_end]; b = by_strategy[strategy_b][period_end]
            if (a.period_start, a.period_end, a.period_type, a.account_timezone) != (b.period_start, b.period_end, b.period_type, b.account_timezone):
                return "COVARIANCE_PERIOD_ALIGNMENT_INVALID"
            try:
                value_a = self._decimal(a.net_r); value_b = self._decimal(b.net_r)
            except ValueError:
                return "NON_FINITE_COVARIANCE_INPUT"
            aligned.append(CovarianceAlignedPair(
                self._uid("aligned", universe.id, strategy_a, strategy_b, period_end, a.id, b.id),
                sequence, a.period_start, period_end, value_a, value_b, a.id, b.id,
                a.period_id, b.period_id, a.source_period_snapshot_id, b.source_period_snapshot_id,
            ))
        pairs = tuple(aligned); count = len(pairs)
        mean_a = mean_b = variance_a = variance_b = covariance = None
        status = CovarianceStatus.INSUFFICIENT_OBSERVATIONS
        if count:
            with localcontext() as context:
                context.prec = 50
                mean_a = sum((item.net_r_a for item in pairs), Decimal(0)) / Decimal(count)
                mean_b = sum((item.net_r_b for item in pairs), Decimal(0)) / Decimal(count)
                if count >= 2:
                    sample = Decimal(count - 1)
                    variance_a = sum(((item.net_r_a - mean_a) ** 2 for item in pairs), Decimal(0)) / sample
                    variance_b = sum(((item.net_r_b - mean_b) ** 2 for item in pairs), Decimal(0)) / sample
                    covariance = sum(((item.net_r_a - mean_a) * (item.net_r_b - mean_b) for item in pairs), Decimal(0)) / sample
                    status = CovarianceStatus.VALID
        source_a = tuple(item.observation_a_id for item in pairs); source_b = tuple(item.observation_b_id for item in pairs)
        return StrategyCovariance(
            self._uid("record", universe.id, universe.version, strategy_a, strategy_b, as_of, *source_a, *source_b),
            universe.id, universe.version, strategy_a, strategy_b,
            pairs[0].period_start if pairs else None, pairs[-1].period_end if pairs else None,
            count, mean_a, mean_b, variance_a, variance_b, covariance, status,
            universe.calculation_mode, universe.window_size, pairs, source_a, source_b,
            tuple(sorted(ends_b - ends_a)), tuple(sorted(ends_a - ends_b)), as_of, as_of,
            universe.source_version, universe.calculation_version, universe.historical_version, False, True,
        )

    @staticmethod
    def _validate_universe(universe, as_of):
        if not universe.immutable or as_of < 0 or universe.period_type not in tuple(PeriodType) or universe.calculation_mode not in tuple(CovarianceMode):
            return "COVARIANCE_UNIVERSE_INVALID"
        identity = (universe.id, universe.version, universe.account_timezone, universe.source_version,
                    universe.strategy_calculation_version, universe.calculation_version, universe.historical_version)
        if not all(str(value).strip() for value in identity):
            return "COVARIANCE_UNIVERSE_IDENTITY_MISSING"
        strategy_ids = tuple(member.strategy_id for member in universe.members)
        if strategy_ids != tuple(sorted(strategy_ids)):
            return "COVARIANCE_UNIVERSE_ORDER_INVALID"
        if len(strategy_ids) != len(set(strategy_ids)) or any(not member.immutable for member in universe.members):
            return "COVARIANCE_UNIVERSE_MEMBERSHIP_INVALID"
        if universe.calculation_mode == CovarianceMode.ROLLING:
            if not isinstance(universe.window_size, int) or universe.window_size < 2:
                return "COVARIANCE_WINDOW_INVALID"
        elif universe.window_size is not None:
            return "COVARIANCE_WINDOW_INVALID"
        return None

    def _validate_observation(self, universe, members, item):
        if not item.immutable or not item.finalized:
            return "NON_FINAL_PERIOD_RETURN_OBSERVATION"
        if item.strategy_id not in members:
            return "COVARIANCE_UNIVERSE_MEMBERSHIP_MISMATCH"
        member = members[item.strategy_id]
        if (item.symbol, item.timeframe, item.setup_model, item.direction) != (member.symbol, member.timeframe, member.setup_model, member.direction):
            return "COVARIANCE_SERIES_SCOPE_MISMATCH"
        if (item.period_type, item.account_timezone, item.source_version, item.calculation_version, item.historical_version) != (
            universe.period_type, universe.account_timezone, universe.source_version,
            universe.strategy_calculation_version, universe.historical_version,
        ):
            return "COVARIANCE_PERIOD_OR_VERSION_MISMATCH"
        if item.period_start < 0 or item.period_end <= item.period_start or item.finalized_time < item.period_end:
            return "COVARIANCE_PERIOD_CHRONOLOGY_INVALID"
        if not all(str(value).strip() for value in (item.id, item.period_id, item.source_period_snapshot_id)):
            return "COVARIANCE_OBSERVATION_IDENTITY_MISSING"
        try:
            self._decimal(item.net_r)
        except ValueError:
            return "NON_FINITE_COVARIANCE_INPUT"
        return None
