"""Phase 7 deterministic reporting, reconciliation, and advisory validation.

Consumes finalized immutable facts. It has no provider, execution, strategy,
account, promotion-authority, or runtime-system capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .specifications import _finite_decimal, _text, _utc, canonical_fingerprint

PHASE7_VERSION = "REPORTING_VALIDATION_V2_PHASE7_1"
ZERO = Decimal("0")
ONE = Decimal("1")


class Phase7Reason(str, Enum):
    OK = "OK"
    EMPTY_SAMPLE = "EMPTY_SAMPLE"
    INCOMPLETE_TRADE = "INCOMPLETE_TRADE"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    DUPLICATE_CONFLICT = "DUPLICATE_CONFLICT"
    CHRONOLOGY_ERROR = "CHRONOLOGY_ERROR"
    LOOKAHEAD_REJECTED = "LOOKAHEAD_REJECTED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    COST_RECONCILIATION_MISMATCH = "COST_RECONCILIATION_MISMATCH"
    BLENDED_EVIDENCE_PROHIBITED = "BLENDED_EVIDENCE_PROHIBITED"
    MISSING_REGIME_LABEL = "MISSING_REGIME_LABEL"
    INSUFFICIENT_OOS_TRADES = "INSUFFICIENT_OOS_TRADES"
    NONPOSITIVE_EXPECTANCY = "NONPOSITIVE_EXPECTANCY"
    PLANNED_RR_BELOW_MINIMUM = "PLANNED_RR_BELOW_MINIMUM"
    ECONOMIC_HURDLE_NOT_MET = "ECONOMIC_HURDLE_NOT_MET"
    UNRESOLVED_UPSTREAM_STATE = "UNRESOLVED_UPSTREAM_STATE"
    CHECKPOINT_TAMPERED = "CHECKPOINT_TAMPERED"
    UNSUPPORTED_PROBABILITY_MODEL = "UNSUPPORTED_PROBABILITY_MODEL"
    MISSING_STRESS_EVIDENCE = "MISSING_STRESS_EVIDENCE"
    MISSING_RUIN_EVIDENCE = "MISSING_RUIN_EVIDENCE"


class Phase7Error(ValueError):
    def __init__(self, reason: Phase7Reason, detail: str):
        self.reason, self.detail = reason, detail
        super().__init__(f"{reason.value}: {detail}")


class EvidencePartition(str, Enum):
    TRAINING = "TRAINING"
    VALIDATION = "VALIDATION"
    UNTOUCHED_OOS = "UNTOUCHED_OOS"
    FORWARD_RECORDED = "FORWARD_RECORDED"
    PAPER = "PAPER"
    LIVE = "LIVE"


class PromotionOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SkipReason(str, Enum):
    NONE = "NONE"
    NO_SETUP = "NO_SETUP"
    MISSING_DATA = "MISSING_DATA"
    STALE_DATA = "STALE_DATA"
    SESSION_INELIGIBLE = "SESSION_INELIGIBLE"
    RISK_REJECTED = "RISK_REJECTED"
    UNRESOLVED_ROLLOVER = "UNRESOLVED_ROLLOVER"
    MISSING_FUNDING = "MISSING_FUNDING"


class StressKind(str, Enum):
    CLUSTERED_LOSS = "CLUSTERED_LOSS"
    GAP = "GAP"
    SLIPPAGE_SHOCK = "SLIPPAGE_SHOCK"
    FUNDING_SHOCK = "FUNDING_SHOCK"
    ROLLOVER_STRESS = "ROLLOVER_STRESS"
    STRATEGY_DEGRADATION = "STRATEGY_DEGRADATION"
    PROBABILITY_OF_RUIN = "PROBABILITY_OF_RUIN"


def _sha(v: str, field: str) -> None:
    if not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
        raise ValueError(f"{field} must be lowercase SHA-256")


def _decimal(v: Decimal, field: str, *, nonnegative: bool = False) -> None:
    _finite_decimal(v, field)
    if nonnegative and v < ZERO:
        raise ValueError(f"{field} must be nonnegative")


@dataclass(frozen=True, slots=True)
class FinalizedTradeV2:
    schema_version: str
    trade_id: str
    run_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    opened_at: datetime
    closed_at: datetime
    partition: EvidencePartition
    strategy_version: str
    accounting_version: str
    quantity: Decimal
    planned_risk: Decimal
    planned_reward: Decimal
    gross_pnl: Decimal
    commission: Decimal
    fees: Decimal
    slippage: Decimal
    funding: Decimal
    settlement_cost: Decimal
    rollover_friction: Decimal
    infrastructure_cost: Decimal
    net_pnl: Decimal
    entry_notional: Decimal
    exit_notional: Decimal
    source_ids: tuple[str, ...]

    @classmethod
    def create(cls, **v) -> "FinalizedTradeV2":
        names = ("run_id","market","instrument_id","contract_id","opened_at","closed_at","partition",
            "strategy_version","accounting_version","quantity","planned_risk","planned_reward","gross_pnl",
            "commission","fees","slippage","funding","settlement_cost","rollover_friction",
            "infrastructure_cost","net_pnl","entry_notional","exit_notional","source_ids")
        tid = canonical_fingerprint("finalized-trade-v2-1", *(v[n] for n in names))
        return cls("finalized-trade-v2-1", tid, **v)

    def __post_init__(self) -> None:
        if self.schema_version != "finalized-trade-v2-1": raise ValueError("unsupported trade schema")
        _sha(self.trade_id, "trade_id"); _sha(self.run_id, "run_id")
        for n in ("market", "instrument_id", "strategy_version", "accounting_version"): _text(getattr(self, n), n)
        _utc(self.opened_at, "opened_at"); _utc(self.closed_at, "closed_at")
        if self.closed_at <= self.opened_at: raise ValueError("trade chronology invalid")
        for n in ("quantity", "planned_risk", "planned_reward", "commission", "fees", "slippage",
                  "settlement_cost", "rollover_friction", "infrastructure_cost", "entry_notional", "exit_notional"):
            _decimal(getattr(self, n), n, nonnegative=True)
        for n in ("gross_pnl", "funding", "net_pnl"): _decimal(getattr(self, n), n)
        if self.quantity <= ZERO or self.planned_risk <= ZERO: raise ValueError("quantity and planned risk must be positive")
        expected_net = self.gross_pnl - self.commission - self.fees - self.slippage - self.settlement_cost - self.rollover_friction - self.infrastructure_cost + self.funding
        if self.net_pnl != expected_net: raise Phase7Error(Phase7Reason.COST_RECONCILIATION_MISMATCH, "gross minus costs plus signed funding must equal net")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)): raise ValueError("trade lineage invalid")
        expected=canonical_fingerprint(self.schema_version,self.run_id,self.market,self.instrument_id,self.contract_id,
            self.opened_at,self.closed_at,self.partition,self.strategy_version,self.accounting_version,self.quantity,
            self.planned_risk,self.planned_reward,self.gross_pnl,self.commission,self.fees,self.slippage,self.funding,
            self.settlement_cost,self.rollover_friction,self.infrastructure_cost,self.net_pnl,self.entry_notional,
            self.exit_notional,self.source_ids)
        if self.trade_id != expected: raise Phase7Error(Phase7Reason.CHECKPOINT_TAMPERED,"trade fingerprint mismatch")

    @property
    def planned_rr(self) -> Decimal: return self.planned_reward / self.planned_risk
    @property
    def turnover(self) -> Decimal: return self.entry_notional + self.exit_notional


@dataclass(frozen=True, slots=True)
class RegimeLabelV2:
    schema_version: str
    label_id: str
    market: str
    instrument_id: str
    effective_from: datetime
    effective_to: datetime
    known_at: datetime
    volatility: str
    trend: str
    liquidity: str
    session: str
    label_version: str
    source_ids: tuple[str, ...]

    @classmethod
    def create(cls, **v) -> "RegimeLabelV2":
        names=("market","instrument_id","effective_from","effective_to","known_at","volatility","trend",
               "liquidity","session","label_version","source_ids")
        lid = canonical_fingerprint("regime-label-v2-1", *(v[n] for n in names))
        return cls("regime-label-v2-1", lid, **v)

    def __post_init__(self) -> None:
        if self.schema_version != "regime-label-v2-1": raise ValueError("unsupported regime schema")
        _sha(self.label_id, "label_id")
        for n in ("effective_from", "effective_to", "known_at"): _utc(getattr(self, n), n)
        if self.effective_to <= self.effective_from or self.known_at > self.effective_from:
            raise Phase7Error(Phase7Reason.LOOKAHEAD_REJECTED, "regime label was not known point-in-time")
        for n in ("market", "instrument_id", "volatility", "trend", "liquidity", "session", "label_version"): _text(getattr(self, n), n)
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)): raise ValueError("regime lineage invalid")
        expected=canonical_fingerprint(self.schema_version,self.market,self.instrument_id,self.effective_from,
            self.effective_to,self.known_at,self.volatility,self.trend,self.liquidity,self.session,
            self.label_version,self.source_ids)
        if self.label_id != expected: raise Phase7Error(Phase7Reason.CHECKPOINT_TAMPERED,"regime fingerprint mismatch")


def segment_trades_by_regime(*, trades: tuple[FinalizedTradeV2, ...],
                             labels: tuple[RegimeLabelV2, ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return immutable label-to-trade lineage without reclassifying outcomes."""
    out=[]
    for trade in sorted(trades, key=lambda t: (t.closed_at, t.trade_id)):
        matches=[x for x in labels if x.market==trade.market and x.instrument_id==trade.instrument_id
                 and x.effective_from <= trade.closed_at < x.effective_to and x.known_at <= trade.closed_at]
        if len(matches) != 1: raise Phase7Error(Phase7Reason.MISSING_REGIME_LABEL, "trade needs exactly one point-in-time regime label")
        out.append((matches[0].label_id,(trade.trade_id,)))
    grouped={}
    for label_id, ids in out: grouped.setdefault(label_id,[]).extend(ids)
    return tuple((key,tuple(grouped[key])) for key in sorted(grouped))


def validate_evidence_partitions(trades: tuple[FinalizedTradeV2, ...]) -> None:
    """Reject relabeling and chronological overlap across evidence partitions."""
    ordered=sorted(trades,key=lambda t:(t.opened_at,t.closed_at,t.trade_id))
    if len({t.trade_id for t in ordered}) != len(ordered):
        raise Phase7Error(Phase7Reason.DUPLICATE_CONFLICT,"duplicate trade identity")
    lineage={}
    for trade in ordered:
        for source_id in trade.source_ids:
            prior=lineage.get(source_id)
            if prior is not None and prior is not trade.partition:
                raise Phase7Error(Phase7Reason.BLENDED_EVIDENCE_PROHIBITED,"source trade was relabeled across partitions")
            lineage[source_id]=trade.partition
    for i,left in enumerate(ordered):
        for right in ordered[i+1:]:
            if (left.market,left.instrument_id)!=(right.market,right.instrument_id): continue
            if left.partition is right.partition: continue
            if right.opened_at < left.closed_at and left.opened_at < right.closed_at:
                raise Phase7Error(Phase7Reason.BLENDED_EVIDENCE_PROHIBITED,"evidence partitions overlap chronologically")


@dataclass(frozen=True, slots=True)
class ReconciliationInputV2:
    run_id: str
    contracts_fingerprint: str
    orders_fingerprint: str
    execution_fingerprint: str
    accounting_fingerprint: str
    risk_fingerprint: str
    sessions_fingerprint: str
    rollover_fingerprint: str
    funding_fingerprint: str
    unresolved_state_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for n in ("run_id", "contracts_fingerprint", "orders_fingerprint", "execution_fingerprint",
                  "accounting_fingerprint", "risk_fingerprint", "sessions_fingerprint",
                  "rollover_fingerprint", "funding_fingerprint"): _sha(getattr(self, n), n)


@dataclass(frozen=True, slots=True)
class ReconciliationRecordV2:
    schema_version: str
    reconciliation_id: str
    run_id: str
    lineage_ids: tuple[str, ...]
    complete: bool
    reason: Phase7Reason


def reconcile(inputs: ReconciliationInputV2) -> ReconciliationRecordV2:
    lineage = (inputs.contracts_fingerprint, inputs.orders_fingerprint, inputs.execution_fingerprint,
               inputs.accounting_fingerprint, inputs.risk_fingerprint, inputs.sessions_fingerprint,
               inputs.rollover_fingerprint, inputs.funding_fingerprint)
    if len(set(lineage)) != len(lineage):
        raise Phase7Error(Phase7Reason.RECONCILIATION_MISMATCH, "ledger lineage fingerprints must be distinct")
    reason = Phase7Reason.OK if not inputs.unresolved_state_ids else Phase7Reason.UNRESOLVED_UPSTREAM_STATE
    rid = canonical_fingerprint("phase7-reconciliation-v2-1", inputs.run_id, lineage, inputs.unresolved_state_ids, reason)
    return ReconciliationRecordV2("phase7-reconciliation-v2-1", rid, inputs.run_id, lineage, not inputs.unresolved_state_ids, reason)


@dataclass(frozen=True, slots=True)
class MetricSnapshotV2:
    schema_version: str
    snapshot_id: str
    run_id: str
    market: str
    partition: EvidencePartition
    as_of: datetime
    trade_ids: tuple[str, ...]
    trade_count: int
    wins: int
    losses: int
    breakevens: int
    gross_pnl: Decimal
    net_pnl: Decimal
    total_cost: Decimal
    expectancy: Decimal | None
    profit_factor: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    sharpe: Decimal | None
    sortino: Decimal | None
    maximum_drawdown: Decimal
    recovery_trades: int | None
    exposure: Decimal
    turnover: Decimal
    tail_loss: Decimal | None
    reporting_version: str


def _sqrt(v: Decimal) -> Decimal: return v.sqrt()


def calculate_metrics(*, trades: tuple[FinalizedTradeV2, ...], run_id: str, market: str,
                      partition: EvidencePartition, as_of: datetime) -> MetricSnapshotV2:
    _sha(run_id, "run_id"); _utc(as_of, "as_of")
    ordered = tuple(sorted(trades, key=lambda t: (t.closed_at, t.trade_id)))
    if len({t.trade_id for t in ordered}) != len(ordered): raise Phase7Error(Phase7Reason.DUPLICATE_CONFLICT, "duplicate trade identity")
    for t in ordered:
        if t.run_id != run_id or t.market != market or t.partition != partition: raise Phase7Error(Phase7Reason.IDENTITY_MISMATCH, "trade scope mismatch")
        if t.closed_at > as_of: raise Phase7Error(Phase7Reason.LOOKAHEAD_REJECTED, "future trade in snapshot")
    if ordered:
        scope={(t.instrument_id,t.strategy_version,t.accounting_version) for t in ordered}
        if len(scope) != 1: raise Phase7Error(Phase7Reason.VERSION_MISMATCH, "instrument or version scopes cannot be mixed")
    values = [t.net_pnl for t in ordered]; n = len(values)
    wins = [v for v in values if v > ZERO]; losses = [v for v in values if v < ZERO]
    gross = sum((t.gross_pnl for t in ordered), ZERO); net = sum(values, ZERO)
    costs = sum((t.commission + t.fees + t.slippage + t.settlement_cost + t.rollover_friction + t.infrastructure_cost - t.funding for t in ordered), ZERO)
    expectancy = net / Decimal(n) if n else None
    profit_factor = (sum(wins, ZERO) / -sum(losses, ZERO)) if losses else None
    avg_win = sum(wins, ZERO) / Decimal(len(wins)) if wins else None
    avg_loss = sum(losses, ZERO) / Decimal(len(losses)) if losses else None
    sharpe = sortino = None
    if n >= 2:
        mean = expectancy
        variance = sum(((v - mean) ** 2 for v in values), ZERO) / Decimal(n - 1)
        sharpe = mean / _sqrt(variance) if variance > ZERO else None
        downside = [min(v, ZERO) for v in values]
        down_var = sum((v * v for v in downside), ZERO) / Decimal(n)
        sortino = mean / _sqrt(down_var) if down_var > ZERO else None
    equity = peak = ZERO; max_dd = ZERO; peak_index = trough_index = recovery = None
    for i, value in enumerate(values):
        equity += value
        if equity > peak: peak, peak_index = equity, i
        dd = peak - equity
        if dd > max_dd: max_dd, trough_index, recovery = dd, i, None
        if recovery is None and trough_index is not None and i > trough_index and equity >= peak: recovery = i - trough_index
    exposure = sum((t.exit_notional for t in ordered), ZERO)
    turnover = sum((t.turnover for t in ordered), ZERO)
    tail_loss = min(values) if values else None
    sid = canonical_fingerprint("metric-snapshot-v2-1", run_id, market, partition, as_of,
                                tuple(t.trade_id for t in ordered), gross, net, costs, PHASE7_VERSION)
    return MetricSnapshotV2("metric-snapshot-v2-1", sid, run_id, market, partition, as_of,
        tuple(t.trade_id for t in ordered), n, len(wins), len(losses), n-len(wins)-len(losses),
        gross, net, costs, expectancy, profit_factor, avg_win, avg_loss, sharpe, sortino,
        max_dd, recovery, exposure, turnover, tail_loss, PHASE7_VERSION)


@dataclass(frozen=True, slots=True)
class StressScenarioV2:
    scenario_id: str
    kind: StressKind
    loss_multiplier: Decimal
    additional_cost_per_trade: Decimal
    cluster_size: int
    ruin_floor: Decimal
    scenario_version: str

    @classmethod
    def create(cls, **v) -> "StressScenarioV2":
        names=("kind","loss_multiplier","additional_cost_per_trade","cluster_size","ruin_floor","scenario_version")
        sid = canonical_fingerprint("stress-scenario-v2-1", *(v[n] for n in names))
        return cls(sid, **v)

    def __post_init__(self) -> None:
        _sha(self.scenario_id, "scenario_id")
        _decimal(self.loss_multiplier, "loss_multiplier", nonnegative=True)
        _decimal(self.additional_cost_per_trade, "additional_cost_per_trade", nonnegative=True)
        _decimal(self.ruin_floor, "ruin_floor")
        if self.cluster_size < 1: raise ValueError("cluster_size must be positive")
        expected=canonical_fingerprint("stress-scenario-v2-1",self.kind,self.loss_multiplier,
            self.additional_cost_per_trade,self.cluster_size,self.ruin_floor,self.scenario_version)
        if self.scenario_id != expected: raise Phase7Error(Phase7Reason.CHECKPOINT_TAMPERED,"stress fingerprint mismatch")


@dataclass(frozen=True, slots=True)
class StressResultV2:
    result_id: str
    scenario_id: str
    kind: StressKind
    stressed_net_pnl: Decimal
    maximum_drawdown: Decimal
    ruin_observed: bool
    trade_count: int


@dataclass(frozen=True, slots=True)
class ProbabilityOfRuinV2:
    simulation_id: str
    path_count: int
    ruined_paths: int
    probability: Decimal
    starting_capital: Decimal
    ruin_floor: Decimal


def probability_of_ruin(*, paths: tuple[tuple[Decimal, ...], ...], starting_capital: Decimal,
                        ruin_floor: Decimal) -> ProbabilityOfRuinV2:
    """Exact empirical ruin frequency over explicitly supplied deterministic paths."""
    _decimal(starting_capital, "starting_capital", nonnegative=True); _decimal(ruin_floor, "ruin_floor")
    if not paths: raise Phase7Error(Phase7Reason.EMPTY_SAMPLE, "ruin simulation needs explicit paths")
    ruined=0
    for path in paths:
        equity=starting_capital; hit=equity <= ruin_floor
        for value in path: _decimal(value,"path_return"); equity += value; hit |= equity <= ruin_floor
        ruined += int(hit)
    probability=Decimal(ruined)/Decimal(len(paths))
    sid=canonical_fingerprint("probability-of-ruin-v2-1",paths,starting_capital,ruin_floor,probability)
    return ProbabilityOfRuinV2(sid,len(paths),ruined,probability,starting_capital,ruin_floor)


def run_stress(*, trades: tuple[FinalizedTradeV2, ...], scenario: StressScenarioV2,
               starting_capital: Decimal) -> StressResultV2:
    _decimal(starting_capital, "starting_capital", nonnegative=True)
    ordered = sorted(trades, key=lambda t: (t.closed_at, t.trade_id))
    values = []
    for i, t in enumerate(ordered):
        value = t.net_pnl - scenario.additional_cost_per_trade
        if value < ZERO or (scenario.kind is StressKind.CLUSTERED_LOSS and i < scenario.cluster_size):
            value -= abs(value) * scenario.loss_multiplier
        values.append(value)
    equity = peak = starting_capital; max_dd = ZERO; ruin = equity <= scenario.ruin_floor
    for value in values:
        equity += value; peak = max(peak, equity); max_dd = max(max_dd, peak-equity); ruin |= equity <= scenario.ruin_floor
    total = sum(values, ZERO)
    rid = canonical_fingerprint("stress-result-v2-1", scenario.scenario_id,
                                tuple(t.trade_id for t in ordered), starting_capital, total, max_dd, ruin)
    return StressResultV2(rid, scenario.scenario_id, scenario.kind, total, max_dd, ruin, len(values))


@dataclass(frozen=True, slots=True)
class EconomicHurdleV2:
    capital: Decimal
    required_net_return: Decimal
    actual_net_return: Decimal
    passed: bool


def economic_hurdles(metrics: MetricSnapshotV2, capital_levels: tuple[Decimal, ...],
                     required_net_return: Decimal) -> tuple[EconomicHurdleV2, ...]:
    _decimal(required_net_return, "required_net_return")
    out=[]
    for capital in capital_levels:
        _decimal(capital, "capital", nonnegative=True)
        if capital == ZERO: raise ValueError("capital must be positive")
        actual=metrics.net_pnl/capital
        out.append(EconomicHurdleV2(capital, required_net_return, actual, actual >= required_net_return))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class PromotionDecisionV2:
    decision_id: str
    outcome: PromotionOutcome
    market: str
    snapshot_id: str
    reasons: tuple[Phase7Reason, ...]
    advisory_only: bool


def evaluate_promotion(*, metrics: MetricSnapshotV2, trades: tuple[FinalizedTradeV2, ...],
                       hurdles: tuple[EconomicHurdleV2, ...], reconciliation: ReconciliationRecordV2,
                       minimum_oos_trades: int = 200,
                       stress_results: tuple[StressResultV2, ...] = (),
                       required_stress_kinds: tuple[StressKind, ...] = (),
                       ruin_evidence: ProbabilityOfRuinV2 | None = None,
                       require_ruin: bool = False) -> PromotionDecisionV2:
    if metrics.partition is not EvidencePartition.UNTOUCHED_OOS:
        raise Phase7Error(Phase7Reason.BLENDED_EVIDENCE_PROHIBITED, "promotion uses untouched OOS only")
    ordered_ids=tuple(t.trade_id for t in sorted(trades,key=lambda t:(t.closed_at,t.trade_id)))
    if ordered_ids != metrics.trade_ids or reconciliation.run_id != metrics.run_id:
        raise Phase7Error(Phase7Reason.RECONCILIATION_MISMATCH, "promotion lineage differs from metric snapshot")
    if minimum_oos_trades < 200: raise ValueError("minimum_oos_trades cannot weaken the frozen 200-trade floor")
    reasons=[]
    if not reconciliation.complete: reasons.append(Phase7Reason.UNRESOLVED_UPSTREAM_STATE)
    if metrics.trade_count < minimum_oos_trades: reasons.append(Phase7Reason.INSUFFICIENT_OOS_TRADES)
    if metrics.expectancy is None or metrics.expectancy <= ZERO: reasons.append(Phase7Reason.NONPOSITIVE_EXPECTANCY)
    if any(t.planned_rr < ONE for t in trades): reasons.append(Phase7Reason.PLANNED_RR_BELOW_MINIMUM)
    if not hurdles or any(not h.passed for h in hurdles): reasons.append(Phase7Reason.ECONOMIC_HURDLE_NOT_MET)
    observed={result.kind for result in stress_results}
    if any(kind not in observed for kind in required_stress_kinds): reasons.append(Phase7Reason.MISSING_STRESS_EVIDENCE)
    if require_ruin and ruin_evidence is None: reasons.append(Phase7Reason.MISSING_RUIN_EVIDENCE)
    outcome = (PromotionOutcome.INSUFFICIENT_EVIDENCE if Phase7Reason.INSUFFICIENT_OOS_TRADES in reasons
               else PromotionOutcome.FAIL if reasons else PromotionOutcome.PASS)
    did=canonical_fingerprint("promotion-decision-v2-1", metrics.snapshot_id, reconciliation.reconciliation_id,
                              tuple(reasons), outcome, PHASE7_VERSION)
    return PromotionDecisionV2(did, outcome, metrics.market, metrics.snapshot_id, tuple(reasons), True)


@dataclass(frozen=True, slots=True)
class BacktestResultV2:
    schema_version: str
    result_id: str
    run_id: str
    reconciliation_id: str
    metric_snapshot_ids: tuple[str, ...]
    stress_result_ids: tuple[str, ...]
    promotion_decision_ids: tuple[str, ...]
    skip_reasons: tuple[SkipReason, ...]
    reporting_version: str

    @classmethod
    def create(cls, **v) -> "BacktestResultV2":
        rid=canonical_fingerprint("backtest-result-v2-1", *(v[n] for n in v))
        return cls("backtest-result-v2-1", rid, **v)

    def __post_init__(self) -> None:
        if self.reporting_version != PHASE7_VERSION: raise Phase7Error(Phase7Reason.VERSION_MISMATCH, "reporting version mismatch")
        for n in ("result_id", "run_id", "reconciliation_id"): _sha(getattr(self,n),n)
        for values in (self.metric_snapshot_ids, self.stress_result_ids, self.promotion_decision_ids):
            if len(values) != len(set(values)): raise Phase7Error(Phase7Reason.DUPLICATE_CONFLICT, "duplicate result lineage")
            for value in values: _sha(value,"result_lineage_id")
        expected=canonical_fingerprint(self.schema_version, self.run_id, self.reconciliation_id,
            self.metric_snapshot_ids, self.stress_result_ids, self.promotion_decision_ids,
            self.skip_reasons, self.reporting_version)
        if self.result_id != expected: raise Phase7Error(Phase7Reason.CHECKPOINT_TAMPERED, "result fingerprint mismatch")
