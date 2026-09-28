"""Deterministic Phase 5 risk and verified-session facts.

This module authorizes no trade.  It consumes immutable Phase 4 accounting
facts and emits advisory decisions or internal forced-action instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum, IntEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .accounting import ACCOUNTING_VERSION, AccountingSnapshotPhase4V2, MarginBasis, MarginSpecificationV2
from .contracts import InstrumentSpecificationV2, OrderSide, RiskDecision, RiskEventV2, RiskPhase
from .ohlc_execution import OHLCBarV2
from .specifications import _finite_decimal, _text, _utc, canonical_fingerprint


RISK_POLICY_VERSION = "RISK_SESSIONS_V2_PHASE5_1"


class RiskReason(str, Enum):
    OK = "OK"
    MISSING_SESSION = "MISSING_SESSION"
    SESSION_IDENTITY_MISMATCH = "SESSION_IDENTITY_MISMATCH"
    SESSION_OUTSIDE_EFFECTIVE_RANGE = "SESSION_OUTSIDE_EFFECTIVE_RANGE"
    SESSION_OVERLAP = "SESSION_OVERLAP"
    OUTSIDE_VERIFIED_SESSION = "OUTSIDE_VERIFIED_SESSION"
    MISSING_RISK_LIMITS = "MISSING_RISK_LIMITS"
    STALE_RISK_LIMITS = "STALE_RISK_LIMITS"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    GROSS_EXPOSURE_LIMIT = "GROSS_EXPOSURE_LIMIT"
    NET_EXPOSURE_LIMIT = "NET_EXPOSURE_LIMIT"
    POSITION_LIMIT = "POSITION_LIMIT"
    CONCENTRATION_LIMIT = "CONCENTRATION_LIMIT"
    LEVERAGE_LIMIT = "LEVERAGE_LIMIT"
    INITIAL_MARGIN_LIMIT = "INITIAL_MARGIN_LIMIT"
    MAINTENANCE_MARGIN_BREACH = "MAINTENANCE_MARGIN_BREACH"
    SESSION_LOSS_LIMIT = "SESSION_LOSS_LIMIT"
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    SESSION_FLATTEN_DEADLINE = "SESSION_FLATTEN_DEADLINE"
    INVALID_REFERENCE_EQUITY = "INVALID_REFERENCE_EQUITY"
    REFERENCE_RESET = "REFERENCE_RESET"
    EVENT_TIME_REGRESSION = "EVENT_TIME_REGRESSION"
    DUPLICATE_EVENT_CONFLICT = "DUPLICATE_EVENT_CONFLICT"
    CHECKPOINT_TAMPERED = "CHECKPOINT_TAMPERED"
    LATER_BAR_REQUIRED = "LATER_BAR_REQUIRED"
    BAR_INELIGIBLE = "BAR_INELIGIBLE"
    END_OF_DATA_RESIDUAL = "END_OF_DATA_RESIDUAL"


class RiskSessionError(ValueError):
    def __init__(self, reason: RiskReason, detail: str):
        self.reason, self.detail = reason, detail
        super().__init__(f"{reason.value}: {detail}")


class RiskAction(str, Enum):
    NONE = "NONE"
    REJECT_NEW_EXPOSURE = "REJECT_NEW_EXPOSURE"
    FORCE_FLATTEN = "FORCE_FLATTEN"
    MARGIN_CALL = "MARGIN_CALL"
    LIQUIDATION_REQUIRED = "LIQUIDATION_REQUIRED"


class PipelinePriority(IntEnum):
    DATA_AND_SESSION = 10
    SETTLEMENT_FUNDING_ROLLOVER = 20
    MARKET_DATA = 30
    STRATEGY = 40
    PRE_TRADE_RISK = 50
    FILLS = 60
    ACCOUNTING = 70
    POST_ACCOUNTING_RISK = 80
    REPORTING = 90


class BreachPriority(IntEnum):
    MAINTENANCE_MARGIN = 10
    SESSION_LOSS = 20
    DRAWDOWN = 30


def _sha(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field} must be lowercase SHA-256")


def _positive(value: Decimal, field: str) -> None:
    _finite_decimal(value, field)
    if value <= 0:
        raise ValueError(f"{field} must be positive")


def _same_identity(record, market: str, instrument_id: str, contract_id: str | None) -> bool:
    return (record.market, record.instrument_id, record.contract_id) == (market, instrument_id, contract_id)


@dataclass(frozen=True, slots=True)
class VerifiedSessionV2:
    schema_version: str
    session_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    session_date: date
    timezone: str
    open_time: datetime
    close_time: datetime
    effective_from: datetime
    effective_to: datetime | None
    calendar_version: str
    source_ids: tuple[str, ...]

    @classmethod
    def create(cls, **values) -> "VerifiedSessionV2":
        sid = canonical_fingerprint("verified-session-v2-1", *(values[k].isoformat() if k == "session_date" else values[k] for k in (
            "market", "instrument_id", "contract_id", "session_date", "timezone", "open_time",
            "close_time", "effective_from", "effective_to", "calendar_version", "source_ids")))
        return cls("verified-session-v2-1", sid, **values)

    def __post_init__(self) -> None:
        if self.schema_version != "verified-session-v2-1": raise ValueError("unsupported session schema")
        _sha(self.session_id, "session_id")
        for n in ("market", "instrument_id", "timezone", "calendar_version"): _text(getattr(self, n), n)
        try: ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc: raise ValueError("timezone is unknown") from exc
        for n in ("open_time", "close_time", "effective_from"): _utc(getattr(self, n), n)
        if self.effective_to is not None: _utc(self.effective_to, "effective_to")
        if self.open_time >= self.close_time: raise ValueError("session must be non-empty")
        if self.open_time < self.effective_from or (self.effective_to is not None and self.close_time > self.effective_to):
            raise ValueError("session lies outside evidence effectiveness")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)): raise ValueError("session sources invalid")
        expected = canonical_fingerprint(self.schema_version, self.market, self.instrument_id,
            self.contract_id, self.session_date.isoformat(), self.timezone, self.open_time, self.close_time,
            self.effective_from, self.effective_to, self.calendar_version, self.source_ids)
        if expected != self.session_id: raise ValueError("session identity mismatch")


@dataclass(frozen=True, slots=True)
class RiskLimitsV2:
    schema_version: str
    limits_id: str
    run_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    effective_from: datetime
    effective_to: datetime | None
    max_gross_exposure: Decimal
    max_net_exposure: Decimal
    max_position_quantity: Decimal
    max_concentration: Decimal
    max_leverage: Decimal
    max_initial_margin: Decimal
    max_session_loss: Decimal
    max_drawdown: Decimal
    flatten_buffer_seconds: int
    risk_policy_version: str
    source_ids: tuple[str, ...]

    @classmethod
    def create(cls, **values) -> "RiskLimitsV2":
        names = ("run_id", "market", "instrument_id", "contract_id", "effective_from", "effective_to",
            "max_gross_exposure", "max_net_exposure", "max_position_quantity", "max_concentration",
            "max_leverage", "max_initial_margin", "max_session_loss", "max_drawdown",
            "flatten_buffer_seconds", "risk_policy_version", "source_ids")
        lid = canonical_fingerprint("risk-limits-v2-1", *(values[k] for k in names))
        return cls("risk-limits-v2-1", lid, **values)

    def __post_init__(self) -> None:
        if self.schema_version != "risk-limits-v2-1" or self.risk_policy_version != RISK_POLICY_VERSION:
            raise ValueError("unsupported risk limits version")
        _sha(self.limits_id, "limits_id"); _sha(self.run_id, "run_id")
        for n in ("market", "instrument_id", "risk_policy_version"): _text(getattr(self, n), n)
        _utc(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _utc(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from: raise ValueError("risk interval invalid")
        for n in ("max_gross_exposure", "max_net_exposure", "max_position_quantity",
                  "max_leverage", "max_initial_margin", "max_session_loss", "max_drawdown"):
            _positive(getattr(self, n), n)
        _positive(self.max_concentration, "max_concentration")
        if self.max_concentration > 1: raise ValueError("concentration cannot exceed one")
        if not isinstance(self.flatten_buffer_seconds, int) or self.flatten_buffer_seconds < 0:
            raise ValueError("flatten buffer must be nonnegative integer seconds")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)): raise ValueError("risk sources invalid")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.market, self.instrument_id,
            self.contract_id, self.effective_from, self.effective_to, self.max_gross_exposure,
            self.max_net_exposure, self.max_position_quantity, self.max_concentration, self.max_leverage,
            self.max_initial_margin, self.max_session_loss, self.max_drawdown, self.flatten_buffer_seconds,
            self.risk_policy_version, self.source_ids)
        if expected != self.limits_id: raise ValueError("risk limits identity mismatch")


@dataclass(frozen=True, slots=True)
class PortfolioRiskContextV2:
    schema_version: str
    context_id: str
    run_id: str
    as_of: datetime
    equity: Decimal
    gross_exposure_before: Decimal
    net_exposure_before: Decimal
    session_reference_equity: Decimal
    session_peak_equity: Decimal
    source_snapshot_ids: tuple[str, ...]

    @classmethod
    def create(cls, **values) -> "PortfolioRiskContextV2":
        names = ("run_id", "as_of", "equity", "gross_exposure_before", "net_exposure_before",
                 "session_reference_equity", "session_peak_equity", "source_snapshot_ids")
        cid = canonical_fingerprint("portfolio-risk-context-v2-1", *(values[k] for k in names))
        return cls("portfolio-risk-context-v2-1", cid, **values)

    def __post_init__(self) -> None:
        if self.schema_version != "portfolio-risk-context-v2-1": raise ValueError("unsupported context schema")
        _sha(self.context_id, "context_id"); _sha(self.run_id, "run_id"); _utc(self.as_of, "as_of")
        _positive(self.equity, "equity"); _positive(self.session_reference_equity, "session_reference_equity")
        _positive(self.session_peak_equity, "session_peak_equity")
        for n in ("gross_exposure_before", "net_exposure_before"):
            _finite_decimal(getattr(self, n), n)
        if self.gross_exposure_before < 0: raise ValueError("gross exposure cannot be negative")
        if self.session_peak_equity < self.session_reference_equity: raise ValueError("peak precedes reference")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.as_of, self.equity,
            self.gross_exposure_before, self.net_exposure_before, self.session_reference_equity,
            self.session_peak_equity, self.source_snapshot_ids)
        if expected != self.context_id: raise ValueError("portfolio context identity mismatch")


@dataclass(frozen=True, slots=True)
class PreTradeRiskRequestV2:
    schema_version: str
    request_id: str
    run_id: str
    evaluated_at: datetime
    market: str
    instrument_id: str
    contract_id: str | None
    side: OrderSide
    quantity: Decimal
    reference_price: Decimal
    source_action_id: str
    source_bar_id: str

    @classmethod
    def create(cls, **values) -> "PreTradeRiskRequestV2":
        names = ("run_id", "evaluated_at", "market", "instrument_id", "contract_id", "side",
                 "quantity", "reference_price", "source_action_id", "source_bar_id")
        rid = canonical_fingerprint("pretrade-risk-request-v2-1", *(values[k] for k in names))
        return cls("pretrade-risk-request-v2-1", rid, **values)

    def __post_init__(self) -> None:
        if self.schema_version != "pretrade-risk-request-v2-1": raise ValueError("unsupported request schema")
        for n in ("request_id", "run_id", "source_action_id", "source_bar_id"): _sha(getattr(self, n), n)
        _utc(self.evaluated_at, "evaluated_at"); _positive(self.quantity, "quantity"); _positive(self.reference_price, "reference_price")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.evaluated_at, self.market,
            self.instrument_id, self.contract_id, self.side, self.quantity, self.reference_price,
            self.source_action_id, self.source_bar_id)
        if expected != self.request_id: raise ValueError("pretrade request identity mismatch")


@dataclass(frozen=True, slots=True)
class RiskDecisionRecordV2:
    schema_version: str
    decision_id: str
    event: RiskEventV2
    action: RiskAction
    values: tuple[tuple[str, Decimal], ...]
    limits_id: str
    session_id: str
    decision_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != "risk-decision-record-v2-1": raise ValueError("unsupported decision schema")
        for n in ("decision_id", "limits_id", "session_id", "decision_fingerprint"): _sha(getattr(self, n), n)
        if tuple(sorted(self.values)) != self.values: raise ValueError("risk values must be canonically ordered")
        expected = canonical_fingerprint(self.schema_version, self.event, self.action, self.values, self.limits_id, self.session_id)
        if expected != self.decision_fingerprint or self.decision_id != expected: raise ValueError("decision fingerprint mismatch")


def resolve_session(sessions: tuple[VerifiedSessionV2, ...], *, at: datetime, market: str,
                    instrument_id: str, contract_id: str | None) -> VerifiedSessionV2:
    _utc(at, "at")
    matching = [s for s in sessions if _same_identity(s, market, instrument_id, contract_id) and s.open_time <= at < s.close_time]
    if not matching: raise RiskSessionError(RiskReason.MISSING_SESSION, "no verified session covers event")
    if len(matching) != 1: raise RiskSessionError(RiskReason.SESSION_OVERLAP, "multiple verified sessions cover event")
    return matching[0]


def _effective(limits: RiskLimitsV2, at: datetime) -> bool:
    return limits.effective_from <= at and (limits.effective_to is None or at < limits.effective_to)


def _decision(*, run_id: str, at: datetime, market: str, instrument_id: str,
              phase: RiskPhase, decision: RiskDecision, reasons: tuple[RiskReason, ...],
              sources: tuple[str, ...], action: RiskAction, values: dict[str, Decimal],
              limits: RiskLimitsV2, session: VerifiedSessionV2) -> RiskDecisionRecordV2:
    codes = tuple(reason.value for reason in reasons)
    event_id = canonical_fingerprint("risk-event-v2-1", run_id, at, market, instrument_id,
                                     phase, decision, codes, sources, RISK_POLICY_VERSION)
    event = RiskEventV2("risk-event-v2-1", event_id, run_id, at, market, instrument_id,
                        phase, decision, codes, sources, RISK_POLICY_VERSION)
    ordered = tuple(sorted(values.items()))
    fp = canonical_fingerprint("risk-decision-record-v2-1", event, action, ordered, limits.limits_id, session.session_id)
    return RiskDecisionRecordV2("risk-decision-record-v2-1", fp, event, action, ordered,
                                limits.limits_id, session.session_id, fp)


def evaluate_pre_trade(*, request: PreTradeRiskRequestV2, snapshot: AccountingSnapshotPhase4V2,
                       context: PortfolioRiskContextV2, limits: RiskLimitsV2,
                       session: VerifiedSessionV2, instrument: InstrumentSpecificationV2,
                       margin: MarginSpecificationV2) -> RiskDecisionRecordV2:
    if request.run_id != snapshot.run_id or request.run_id != context.run_id or request.run_id != limits.run_id:
        raise RiskSessionError(RiskReason.IDENTITY_MISMATCH, "run identities differ")
    identity = (request.market, request.instrument_id, request.contract_id)
    if any(not _same_identity(x, *identity) for x in (snapshot, limits, session, instrument, margin)):
        raise RiskSessionError(RiskReason.IDENTITY_MISMATCH, "market/instrument/contract identities differ")
    if snapshot.accounting_version != ACCOUNTING_VERSION:
        raise RiskSessionError(RiskReason.VERSION_MISMATCH, "accounting version differs")
    if not _effective(limits, request.evaluated_at):
        raise RiskSessionError(RiskReason.STALE_RISK_LIMITS, "risk limits are not effective")
    if not session.open_time <= request.evaluated_at < session.close_time:
        raise RiskSessionError(RiskReason.OUTSIDE_VERIFIED_SESSION, "request outside verified session")
    direction = Decimal("1") if request.side == OrderSide.BUY else Decimal("-1")
    projected_q = snapshot.position.signed_quantity + direction * request.quantity
    notional = abs(projected_q) * request.reference_price * instrument.contract_multiplier
    old_notional = abs(snapshot.position.signed_quantity) * request.reference_price * instrument.contract_multiplier
    gross = context.gross_exposure_before - old_notional + notional
    net = context.net_exposure_before - snapshot.position.signed_quantity * request.reference_price * instrument.contract_multiplier + projected_q * request.reference_price * instrument.contract_multiplier
    concentration = Decimal("0") if gross == 0 else notional / gross
    leverage = gross / context.equity
    if margin.basis == MarginBasis.PER_CONTRACT:
        initial_margin = abs(projected_q) * margin.customer_initial
    else:
        initial_margin = notional * margin.customer_initial
    values = {"concentration": concentration, "gross_exposure": gross, "initial_margin": initial_margin,
              "leverage": leverage, "net_exposure": net, "projected_quantity": projected_q}
    checks = ((RiskReason.GROSS_EXPOSURE_LIMIT, gross > limits.max_gross_exposure),
              (RiskReason.NET_EXPOSURE_LIMIT, abs(net) > limits.max_net_exposure),
              (RiskReason.POSITION_LIMIT, abs(projected_q) > limits.max_position_quantity),
              (RiskReason.CONCENTRATION_LIMIT, concentration > limits.max_concentration),
              (RiskReason.LEVERAGE_LIMIT, leverage > limits.max_leverage),
              (RiskReason.INITIAL_MARGIN_LIMIT, initial_margin > limits.max_initial_margin))
    reasons = tuple(reason for reason, breached in checks if breached) or (RiskReason.OK,)
    allowed = reasons == (RiskReason.OK,)
    sources = (request.request_id, snapshot.snapshot_id, context.context_id, instrument.specification_id,
               margin.margin_specification_id)
    return _decision(run_id=request.run_id, at=request.evaluated_at, market=request.market,
        instrument_id=request.instrument_id, phase=RiskPhase.PRE_TRADE,
        decision=RiskDecision.ALLOW if allowed else RiskDecision.REJECT, reasons=reasons,
        sources=sources, action=RiskAction.NONE if allowed else RiskAction.REJECT_NEW_EXPOSURE,
        values=values, limits=limits, session=session)


@dataclass(frozen=True, slots=True)
class SessionRiskStateV2:
    schema_version: str
    state_id: str
    run_id: str
    session_id: str
    as_of: datetime
    reference_equity: Decimal
    peak_equity: Decimal
    current_equity: Decimal
    session_loss: Decimal
    drawdown: Decimal
    source_snapshot_ids: tuple[str, ...]
    risk_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "session-risk-state-v2-1" or self.risk_policy_version != RISK_POLICY_VERSION: raise ValueError("unsupported session state")
        for n in ("state_id", "run_id", "session_id"): _sha(getattr(self, n), n)
        _utc(self.as_of, "as_of")
        for n in ("reference_equity", "peak_equity", "current_equity", "session_loss", "drawdown"): _finite_decimal(getattr(self, n), n)
        if self.reference_equity <= 0 or self.peak_equity < self.reference_equity or self.session_loss < 0 or self.drawdown < 0: raise ValueError("session equity geometry invalid")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.session_id, self.as_of,
            self.reference_equity, self.peak_equity, self.current_equity, self.session_loss,
            self.drawdown, self.source_snapshot_ids, self.risk_policy_version)
        if expected != self.state_id: raise ValueError("session state identity mismatch")


@dataclass(frozen=True, slots=True)
class ForcedFlattenInstructionV2:
    schema_version: str
    instruction_id: str
    run_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    side: OrderSide
    quantity: Decimal
    triggered_at: datetime
    breach_bar_id: str
    decision_id: str
    accounting_snapshot_id: str
    session_id: str
    status: str

    def __post_init__(self) -> None:
        if self.schema_version != "forced-flatten-instruction-v2-1" or self.status != "UNRESOLVED": raise ValueError("unsupported forced instruction")
        for n in ("instruction_id", "run_id", "breach_bar_id", "decision_id", "accounting_snapshot_id", "session_id"): _sha(getattr(self, n), n)
        _positive(self.quantity, "quantity"); _utc(self.triggered_at, "triggered_at")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.market, self.instrument_id,
            self.contract_id, self.side, self.quantity, self.triggered_at, self.breach_bar_id,
            self.decision_id, self.accounting_snapshot_id, self.session_id, self.status)
        if expected != self.instruction_id: raise ValueError("forced instruction identity mismatch")


@dataclass(frozen=True, slots=True)
class MarginCallFactV2:
    schema_version: str
    fact_id: str
    decision_id: str
    accounting_snapshot_id: str
    required_margin: Decimal
    equity: Decimal
    as_of: datetime

    def __post_init__(self) -> None:
        if self.schema_version != "margin-call-fact-v2-1": raise ValueError("unsupported margin call schema")
        _sha(self.fact_id, "fact_id"); _sha(self.decision_id, "decision_id"); _sha(self.accounting_snapshot_id, "accounting_snapshot_id")
        _finite_decimal(self.required_margin, "required_margin"); _finite_decimal(self.equity, "equity"); _utc(self.as_of, "as_of")
        if self.required_margin < 0: raise ValueError("required margin cannot be negative")
        expected = canonical_fingerprint(self.schema_version, self.decision_id,
            self.accounting_snapshot_id, self.required_margin, self.equity, self.as_of)
        if expected != self.fact_id: raise ValueError("margin call identity mismatch")


@dataclass(frozen=True, slots=True)
class LiquidationRequiredFactV2:
    schema_version: str
    fact_id: str
    margin_call_id: str
    decision_id: str
    as_of: datetime
    status: str

    def __post_init__(self) -> None:
        if self.schema_version != "liquidation-required-fact-v2-1" or self.status != "UNRESOLVED": raise ValueError("unsupported liquidation-required fact")
        _sha(self.fact_id, "fact_id"); _sha(self.margin_call_id, "margin_call_id"); _sha(self.decision_id, "decision_id"); _utc(self.as_of, "as_of")
        expected = canonical_fingerprint(self.schema_version, self.margin_call_id,
            self.decision_id, self.as_of, self.status)
        if expected != self.fact_id: raise ValueError("liquidation-required identity mismatch")


@dataclass(frozen=True, slots=True)
class PostAccountingRiskEvaluationV2:
    schema_version: str
    evaluation_id: str
    state: SessionRiskStateV2
    decision: RiskDecisionRecordV2
    forced_flatten: ForcedFlattenInstructionV2 | None
    margin_call: MarginCallFactV2 | None
    liquidation_required: LiquidationRequiredFactV2 | None

    def __post_init__(self) -> None:
        if self.schema_version != "post-accounting-risk-evaluation-v2-1": raise ValueError("unsupported post-accounting evaluation")
        _sha(self.evaluation_id, "evaluation_id")
        expected = canonical_fingerprint(self.schema_version, self.state, self.decision,
                                         self.forced_flatten, self.margin_call, self.liquidation_required)
        if expected != self.evaluation_id: raise ValueError("post-accounting evaluation fingerprint mismatch")


def evaluate_post_accounting(*, snapshot: AccountingSnapshotPhase4V2, prior_state: SessionRiskStateV2 | None,
                             limits: RiskLimitsV2, session: VerifiedSessionV2,
                             trigger_bar_id: str) -> PostAccountingRiskEvaluationV2:
    _sha(trigger_bar_id, "trigger_bar_id")
    if snapshot.run_id != limits.run_id or not _same_identity(snapshot, limits.market, limits.instrument_id, limits.contract_id) or not _same_identity(session, limits.market, limits.instrument_id, limits.contract_id):
        raise RiskSessionError(RiskReason.IDENTITY_MISMATCH, "post-accounting identities differ")
    if snapshot.accounting_version != ACCOUNTING_VERSION: raise RiskSessionError(RiskReason.VERSION_MISMATCH, "accounting version differs")
    if not _effective(limits, snapshot.as_of): raise RiskSessionError(RiskReason.STALE_RISK_LIMITS, "risk limits are not effective")
    if not session.open_time <= snapshot.as_of < session.close_time: raise RiskSessionError(RiskReason.OUTSIDE_VERIFIED_SESSION, "snapshot outside verified session")
    if prior_state is None:
        reference = peak = snapshot.equity
        source_ids = (snapshot.snapshot_id,)
    else:
        if prior_state.run_id != snapshot.run_id or prior_state.session_id != session.session_id: raise RiskSessionError(RiskReason.REFERENCE_RESET, "prior state lineage differs")
        if snapshot.as_of < prior_state.as_of: raise RiskSessionError(RiskReason.EVENT_TIME_REGRESSION, "accounting chronology regressed")
        reference, peak = prior_state.reference_equity, max(prior_state.peak_equity, snapshot.equity)
        source_ids = prior_state.source_snapshot_ids + (() if snapshot.snapshot_id in prior_state.source_snapshot_ids else (snapshot.snapshot_id,))
    if reference <= 0: raise RiskSessionError(RiskReason.INVALID_REFERENCE_EQUITY, "reference equity must be positive")
    loss, drawdown = max(Decimal("0"), reference - snapshot.equity), max(Decimal("0"), peak - snapshot.equity)
    state_id = canonical_fingerprint("session-risk-state-v2-1", snapshot.run_id, session.session_id,
        snapshot.as_of, reference, peak, snapshot.equity, loss, drawdown, source_ids, RISK_POLICY_VERSION)
    state = SessionRiskStateV2("session-risk-state-v2-1", state_id, snapshot.run_id, session.session_id,
        snapshot.as_of, reference, peak, snapshot.equity, loss, drawdown, source_ids, RISK_POLICY_VERSION)
    ordered = ((RiskReason.MAINTENANCE_MARGIN_BREACH, snapshot.margin_breach),
               (RiskReason.SESSION_LOSS_LIMIT, loss > limits.max_session_loss),
               (RiskReason.DRAWDOWN_LIMIT, drawdown > limits.max_drawdown))
    reasons = tuple(reason for reason, hit in ordered if hit) or (RiskReason.OK,)
    breached = reasons != (RiskReason.OK,)
    decision = _decision(run_id=snapshot.run_id, at=snapshot.as_of, market=snapshot.market,
        instrument_id=snapshot.instrument_id, phase=RiskPhase.POST_EVENT,
        decision=RiskDecision.FORCE_FLATTEN if breached else RiskDecision.ALLOW, reasons=reasons,
        sources=(snapshot.snapshot_id, state.state_id, trigger_bar_id),
        action=RiskAction.FORCE_FLATTEN if breached else RiskAction.NONE,
        values={"drawdown": drawdown, "equity": snapshot.equity, "session_loss": loss}, limits=limits, session=session)
    forced = None
    if breached and snapshot.position.signed_quantity:
        side = OrderSide.SELL if snapshot.position.signed_quantity > 0 else OrderSide.BUY
        iid = canonical_fingerprint("forced-flatten-instruction-v2-1", snapshot.run_id, snapshot.market,
            snapshot.instrument_id, snapshot.contract_id, side, abs(snapshot.position.signed_quantity),
            snapshot.as_of, trigger_bar_id, decision.decision_id, snapshot.snapshot_id, session.session_id, "UNRESOLVED")
        forced = ForcedFlattenInstructionV2("forced-flatten-instruction-v2-1", iid, snapshot.run_id,
            snapshot.market, snapshot.instrument_id, snapshot.contract_id, side,
            abs(snapshot.position.signed_quantity), snapshot.as_of, trigger_bar_id,
            decision.decision_id, snapshot.snapshot_id, session.session_id, "UNRESOLVED")
    margin_call = liquidation = None
    if snapshot.margin_breach:
        mid = canonical_fingerprint("margin-call-fact-v2-1", decision.decision_id, snapshot.snapshot_id,
                                    snapshot.customer_maintenance_margin, snapshot.equity, snapshot.as_of)
        margin_call = MarginCallFactV2("margin-call-fact-v2-1", mid, decision.decision_id,
            snapshot.snapshot_id, snapshot.customer_maintenance_margin, snapshot.equity, snapshot.as_of)
        lid = canonical_fingerprint("liquidation-required-fact-v2-1", mid, decision.decision_id, snapshot.as_of, "UNRESOLVED")
        liquidation = LiquidationRequiredFactV2("liquidation-required-fact-v2-1", lid, mid, decision.decision_id, snapshot.as_of, "UNRESOLVED")
    eid = canonical_fingerprint("post-accounting-risk-evaluation-v2-1", state, decision, forced, margin_call, liquidation)
    return PostAccountingRiskEvaluationV2("post-accounting-risk-evaluation-v2-1", eid, state, decision, forced, margin_call, liquidation)


def evaluate_session_flatten(*, snapshot: AccountingSnapshotPhase4V2, limits: RiskLimitsV2,
                             session: VerifiedSessionV2, trigger_bar_id: str) -> PostAccountingRiskEvaluationV2:
    """Emit an internal flatten instruction at the verified deadline; never an order."""
    deadline = session.close_time - timedelta(seconds=limits.flatten_buffer_seconds)
    if snapshot.as_of < deadline:
        raise RiskSessionError(RiskReason.OUTSIDE_VERIFIED_SESSION, "session flatten deadline not reached")
    if snapshot.position.signed_quantity == 0:
        raise RiskSessionError(RiskReason.END_OF_DATA_RESIDUAL, "flat position needs no session action")
    base = evaluate_post_accounting(snapshot=snapshot, prior_state=None, limits=limits,
                                    session=session, trigger_bar_id=trigger_bar_id)
    decision = _decision(run_id=snapshot.run_id, at=snapshot.as_of, market=snapshot.market,
        instrument_id=snapshot.instrument_id, phase=RiskPhase.SESSION,
        decision=RiskDecision.FORCE_FLATTEN, reasons=(RiskReason.SESSION_FLATTEN_DEADLINE,),
        sources=(snapshot.snapshot_id, base.state.state_id, trigger_bar_id), action=RiskAction.FORCE_FLATTEN,
        values={"deadline_epoch": Decimal(str(int(deadline.timestamp()))), "equity": snapshot.equity},
        limits=limits, session=session)
    side = OrderSide.SELL if snapshot.position.signed_quantity > 0 else OrderSide.BUY
    iid = canonical_fingerprint("forced-flatten-instruction-v2-1", snapshot.run_id, snapshot.market,
        snapshot.instrument_id, snapshot.contract_id, side, abs(snapshot.position.signed_quantity),
        snapshot.as_of, trigger_bar_id, decision.decision_id, snapshot.snapshot_id, session.session_id, "UNRESOLVED")
    forced = ForcedFlattenInstructionV2("forced-flatten-instruction-v2-1", iid, snapshot.run_id,
        snapshot.market, snapshot.instrument_id, snapshot.contract_id, side,
        abs(snapshot.position.signed_quantity), snapshot.as_of, trigger_bar_id,
        decision.decision_id, snapshot.snapshot_id, session.session_id, "UNRESOLVED")
    eid = canonical_fingerprint("post-accounting-risk-evaluation-v2-1", base.state, decision,
                                forced, None, None)
    return PostAccountingRiskEvaluationV2("post-accounting-risk-evaluation-v2-1", eid,
                                          base.state, decision, forced, None, None)


def validate_forced_flatten_bar(instruction: ForcedFlattenInstructionV2, bar: OHLCBarV2,
                                session: VerifiedSessionV2) -> None:
    if bar.bar_id == instruction.breach_bar_id or bar.open_time <= instruction.triggered_at:
        raise RiskSessionError(RiskReason.LATER_BAR_REQUIRED, "forced action requires a later bar")
    if not _same_identity(bar, instruction.market, instruction.instrument_id, instruction.contract_id) or session.session_id != instruction.session_id:
        raise RiskSessionError(RiskReason.IDENTITY_MISMATCH, "forced-action bar lineage differs")
    if not (bar.finalized and bar.session_eligible and bar.data_quality_valid and bar.contract_eligible):
        raise RiskSessionError(RiskReason.BAR_INELIGIBLE, "forced-action bar is ineligible")
    if not session.open_time <= bar.open_time and bar.close_time <= session.close_time:
        raise RiskSessionError(RiskReason.OUTSIDE_VERIFIED_SESSION, "bar outside verified session")


def completed_run_gate(snapshot: AccountingSnapshotPhase4V2,
                       instructions: tuple[ForcedFlattenInstructionV2, ...]) -> None:
    if snapshot.position.signed_quantity != 0 or any(item.status == "UNRESOLVED" for item in instructions):
        raise RiskSessionError(RiskReason.END_OF_DATA_RESIDUAL, "position or forced instruction remains unresolved")


@dataclass(frozen=True, slots=True)
class RiskSessionCheckpointV2:
    schema_version: str
    checkpoint_id: str
    ledger_fingerprint: str
    ledger: "RiskSessionLedgerV2"

    def __post_init__(self) -> None:
        if self.schema_version != "risk-session-checkpoint-v2-1": raise ValueError("unsupported checkpoint")
        _sha(self.checkpoint_id, "checkpoint_id"); _sha(self.ledger_fingerprint, "ledger_fingerprint")
        if self.ledger.ledger_fingerprint != self.ledger_fingerprint: raise RiskSessionError(RiskReason.CHECKPOINT_TAMPERED, "checkpoint differs")


@dataclass(frozen=True, slots=True)
class RiskSessionLedgerV2:
    schema_version: str
    run_id: str
    decisions: tuple[RiskDecisionRecordV2, ...]
    post_evaluations: tuple[PostAccountingRiskEvaluationV2, ...]
    ledger_fingerprint: str

    @classmethod
    def create(cls, run_id: str) -> "RiskSessionLedgerV2":
        _sha(run_id, "run_id")
        fp = canonical_fingerprint("risk-session-ledger-v2-1", run_id, (), ())
        return cls("risk-session-ledger-v2-1", run_id, (), (), fp)

    def _fingerprint(self, decisions, evaluations):
        return canonical_fingerprint(self.schema_version, self.run_id, decisions, evaluations)

    def verify_integrity(self):
        if self.ledger_fingerprint != self._fingerprint(self.decisions, self.post_evaluations):
            raise RiskSessionError(RiskReason.CHECKPOINT_TAMPERED, "risk ledger differs")

    def apply(self, record: RiskDecisionRecordV2 | PostAccountingRiskEvaluationV2) -> "RiskSessionLedgerV2":
        self.verify_integrity()
        decision = record.decision if isinstance(record, PostAccountingRiskEvaluationV2) else record
        by_id = {item.decision_id: item for item in self.decisions}
        if decision.decision_id in by_id:
            if by_id[decision.decision_id] == decision: return self
            raise RiskSessionError(RiskReason.DUPLICATE_EVENT_CONFLICT, "decision identity reused")
        if decision.event.run_id != self.run_id: raise RiskSessionError(RiskReason.IDENTITY_MISMATCH, "run differs")
        if self.decisions and (decision.event.event_time, decision.decision_id) < (self.decisions[-1].event.event_time, self.decisions[-1].decision_id):
            raise RiskSessionError(RiskReason.EVENT_TIME_REGRESSION, "risk chronology regressed")
        ds = self.decisions + (decision,)
        es = self.post_evaluations + ((record,) if isinstance(record, PostAccountingRiskEvaluationV2) else ())
        return replace(self, decisions=ds, post_evaluations=es, ledger_fingerprint=self._fingerprint(ds, es))

    def checkpoint(self) -> RiskSessionCheckpointV2:
        self.verify_integrity()
        cid = canonical_fingerprint("risk-session-checkpoint-v2-1", self.ledger_fingerprint)
        return RiskSessionCheckpointV2("risk-session-checkpoint-v2-1", cid, self.ledger_fingerprint, self)
