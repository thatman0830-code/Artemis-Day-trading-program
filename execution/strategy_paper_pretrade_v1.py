"""Offline pre-fill sizing and V2 risk evaluation, never submission authority."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction

from backtesting.execution_accounting_v2.risk_sessions import PreTradeRiskRequestV2, evaluate_pre_trade
from backtesting.execution_accounting_v2.contracts import RiskDecision
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from backtesting.execution_accounting_v2.accounting import MarginBasis
from execution.paper_closed_bar_input_v1 import _sha, _utc
from execution.paper_gateway_v2 import PaperGatewaySnapshotV1, PaperOrderState
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.strategy_paper_intent_v1 import compile_strategy_paper_intent, _milliseconds
from execution.btc_perpetual_strategy_intent_v1 import compile_btc_perpetual_strategy_intent
from execution.supervised_paper_launch_decision_v1 import MAXIMUM_ORDER_NOTIONAL


class PaperPretradeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PaperSizingPolicyV1:
    effective_from: datetime
    effective_to: datetime
    maximum_equity_risk_fraction: Decimal
    maximum_planned_loss: Decimal
    fixed_cost_allowance: Decimal
    per_unit_cost_allowance: Decimal
    evidence_sha256: str

    def __post_init__(self):
        _utc(self.effective_from); _utc(self.effective_to); _sha(self.evidence_sha256)
        if self.effective_to <= self.effective_from:
            raise PaperPretradeError("invalid sizing policy interval")
        for value in (self.maximum_equity_risk_fraction,self.maximum_planned_loss,
                      self.fixed_cost_allowance,self.per_unit_cost_allowance):
            if type(value) is not Decimal or not value.is_finite() or value < 0:
                raise PaperPretradeError("exact nonnegative Decimal sizing facts required")
            if len(value.as_tuple().digits) > 28 or abs(value.as_tuple().exponent) > 28:
                raise PaperPretradeError("sizing precision exceeds supported bound")
        if not 0 < self.maximum_equity_risk_fraction <= 1 or self.maximum_planned_loss <= 0:
            raise PaperPretradeError("positive bounded risk budget required")


@dataclass(frozen=True, slots=True)
class PaperPretradePlanV1:
    plan_id: str
    strategy_intent: object
    risk_decision: object
    quantity: Decimal
    planned_stop_loss_with_allowances: Decimal
    reserved_cash: Decimal
    risk_eligible: bool
    submission_authorized: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if self.submission_authorized is not False or self.trading_authority is not False:
            raise PaperPretradeError("pretrade plan cannot authorize submission")


def plan_strategy_paper_pretrade(*, strategy_inputs, performance, gateway, context,
                                limits, session, sizing_policy, source_bar_id):
    """Recompile the proposed strategy intent using a computed grid quantity.

    Inputs are trusted typed records. No mutable runtime is read or changed.
    Cost allowances are owner-supplied assumptions, not realized costs or a loss cap.
    """
    args = dict(strategy_inputs)
    _sha(source_bar_id)
    if "quantity" in args or "quantity_evidence_sha256" in args:
        raise PaperPretradeError("quantity must be computed by pretrade sizing")
    if not isinstance(performance,PaperPerformanceLedgerV1) or not isinstance(sizing_policy,PaperSizingPolicyV1):
        raise PaperPretradeError("typed performance and sizing policy required")
    performance.__post_init__()
    gateway = PaperGatewaySnapshotV1.resume(gateway)
    if performance.reconcile_gateway(gateway) != performance:
        raise PaperPretradeError("performance checkpoint is not bound to current gateway")
    if not gateway.connected or gateway.kill_switch_active or gateway.reconciliation_required:
        raise PaperPretradeError("gateway is not healthy")
    if any(r.state in (PaperOrderState.ACCEPTED,PaperOrderState.PARTIALLY_FILLED) for r in gateway.records):
        raise PaperPretradeError("outstanding orders require reservation accounting")
    book = performance.accounting; snapshot = book.snapshot
    now = args["now"]; expiry = args["expires_at"]; _utc(now); _utc(expiry)
    if snapshot.position.signed_quantity != 0:
        raise PaperPretradeError("flat position required")
    strategy_instrument = (args.get("instrument") or
                           getattr(args.get("economics"), "instrument", None))
    if strategy_instrument != book.instrument or args["run_id"] != book.run_id:
        raise PaperPretradeError("strategy and accounting identity mismatch")
    is_perpetual = book.instrument.profile is InstrumentProfile.BTC_LINEAR_PERPETUAL
    if is_perpetual and args.get("margin") != book.margin_specification:
        raise PaperPretradeError("strategy and accounting margin identity mismatch")
    context.__post_init__(); limits.__post_init__(); session.__post_init__()
    if (not timedelta(0) <= now-snapshot.as_of <= timedelta(seconds=5)
            or not timedelta(0) <= now-context.as_of <= timedelta(seconds=5)):
        raise PaperPretradeError("stale or future accounting/context evidence")
    if (context.source_snapshot_ids != (snapshot.snapshot_id,) or context.equity != snapshot.equity
            or context.gross_exposure_before != 0 or context.net_exposure_before != 0
            or context.session_peak_equity < snapshot.equity):
        raise PaperPretradeError("single-account flat context does not reconcile")
    if (context.session_reference_equity-snapshot.equity >= limits.max_session_loss
            or context.session_peak_equity-snapshot.equity >= limits.max_drawdown
            or snapshot.margin_breach):
        raise PaperPretradeError("existing loss drawdown or margin breach")
    if (not sizing_policy.effective_from <= now < expiry <= sizing_policy.effective_to
            or expiry > session.close_time-timedelta(seconds=limits.flatten_buffer_seconds)
            or (limits.effective_to is not None and expiry > limits.effective_to)
            or not book.margin_specification.effective_from <= now
            or (book.margin_specification.effective_to is not None and expiry > book.margin_specification.effective_to)):
        raise PaperPretradeError("policy/session/margin coverage insufficient")
    availability = args["position_availability"]
    if availability.checked_time != _milliseconds(snapshot.as_of):
        raise PaperPretradeError("position observation is not current accounting time")
    q = args["qualification"]; inst = book.instrument
    for value in (q.entry,q.stop,inst.contract_multiplier,inst.quantity_step,snapshot.equity,snapshot.cash):
        if type(value) is not Decimal or not value.is_finite() or value <= 0:
            raise PaperPretradeError("positive Decimal sizing economics required")
        if len(value.as_tuple().digits)>28 or abs(value.as_tuple().exponent)>28:
            raise PaperPretradeError("sizing precision exceeds supported bound")
    if q.entry <= q.stop:
        raise PaperPretradeError("positive long stop distance required")
    p = sizing_policy
    # Exact rational floor prevents division rounding from adding an extra step.
    F = Fraction
    unit_loss = (F(q.entry)-F(q.stop))*F(inst.contract_multiplier)+F(p.per_unit_cost_allowance)
    if is_perpetual:
        margin = book.margin_specification
        unit_margin = (F(margin.customer_initial) if margin.basis is MarginBasis.PER_CONTRACT
            else F(q.entry)*F(inst.contract_multiplier)*F(margin.customer_initial))
        unit_cash = unit_margin + F(p.per_unit_cost_allowance)
    else:
        unit_cash = F(q.entry)*F(inst.contract_multiplier)+F(p.per_unit_cost_allowance)
    budget = min(F(snapshot.equity)*F(p.maximum_equity_risk_fraction),F(p.maximum_planned_loss))
    capacities = ((budget-F(p.fixed_cost_allowance))/unit_loss,
        (F(snapshot.cash)-F(p.fixed_cost_allowance))/unit_cash,
        F(MAXIMUM_ORDER_NOTIONAL)/(F(q.entry)*F(inst.contract_multiplier)),F(limits.max_position_quantity))
    steps = min(capacities)//F(inst.quantity_step)
    if steps <= 0:
        raise PaperPretradeError("budget cannot fund one quantity step")
    with localcontext() as arithmetic:
        arithmetic.prec = 180
        quantity = Decimal(steps)*inst.quantity_step
        planned_loss = quantity*((q.entry-q.stop)*inst.contract_multiplier+p.per_unit_cost_allowance)+p.fixed_cost_allowance
        if is_perpetual:
            margin_per_unit = (book.margin_specification.customer_initial
                if book.margin_specification.basis is MarginBasis.PER_CONTRACT else
                q.entry*inst.contract_multiplier*book.margin_specification.customer_initial)
            reserved = quantity*(margin_per_unit+p.per_unit_cost_allowance)+p.fixed_cost_allowance
        else:
            reserved = quantity*(q.entry*inst.contract_multiplier+p.per_unit_cost_allowance)+p.fixed_cost_allowance
    evidence = canonical_fingerprint("paper-pretrade-sizing-v1",performance.ledger_id,gateway.snapshot_id,
        context,limits,session.session_id,p,quantity,planned_loss,reserved,args,source_bar_id)
    compiler = compile_btc_perpetual_strategy_intent if is_perpetual else compile_strategy_paper_intent
    translated = compiler(**args,quantity=quantity,quantity_evidence_sha256=evidence)
    request = PreTradeRiskRequestV2.create(run_id=book.run_id,evaluated_at=now,market=book.market,
        instrument_id=book.instrument_id,contract_id=book.contract_id,side=translated.intent.side,
        quantity=quantity,reference_price=q.entry,source_action_id=translated.intent.action_id,
        source_bar_id=source_bar_id)
    decision = evaluate_pre_trade(request=request,snapshot=snapshot,context=context,limits=limits,
        session=session,instrument=inst,margin=book.margin_specification)
    plan_id = canonical_fingerprint("paper-pretrade-plan-v1",evidence,translated,decision)
    return PaperPretradePlanV1(plan_id,translated,decision,quantity,planned_loss,reserved,
                              decision.event.decision is RiskDecision.ALLOW)
