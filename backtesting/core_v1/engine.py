from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from hashlib import sha256
from time import perf_counter

from .adapters import VerifiedArchiveSlice
from .capabilities import CapabilityReport, EngineCapabilities, validate_capabilities
from .models import (AccountingSnapshot, ActionKind, BacktestResult, CoreEvent, EndPolicy,
    EventType, ExecutionConfig, FillRecord, InstrumentSpec, OrderRecord, OrderType,
    PositionSnapshot, ReadOnlyState, RiskConfig, Side, Trigger, TriggerKind, canonical,
    fingerprint, require_decimal, require_utc)
from .strategy import Strategy


@dataclass(frozen=True)
class EngineRunConfiguration:
    run_id: str
    configuration_version: str
    starting_cash: Decimal
    execution: ExecutionConfig
    risk: RiskConfig
    evaluation_start: datetime
    evaluation_end: datetime
    calendar_fingerprints: tuple[str, ...] = ()
    rollover_fingerprints: tuple[str, ...] = ()
    split_plan_id: str = "UNSPECIFIED"
    random_seed: int = 0
    schema_versions: tuple[str, ...] = ("backtest-engine-core-v1",)

    def __post_init__(self) -> None:
        require_decimal(self.starting_cash, "starting_cash", positive=True)
        require_utc(self.evaluation_start); require_utc(self.evaluation_end)
        if self.evaluation_start >= self.evaluation_end:
            raise ValueError("run interval is invalid")
        if not self.split_plan_id or not self.schema_versions:
            raise ValueError("split and schema identities are required")


def _quantize_down(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


class CalculationEngine:
    """Offline deterministic Core v1 engine. It has no provider or trading interfaces."""

    def preflight(self, *, strategy: Strategy, archives: tuple[VerifiedArchiveSlice, ...],
                  capabilities: EngineCapabilities = EngineCapabilities()) -> CapabilityReport:
        markets = {archive.market for archive in archives}
        has_volume = all(all(bar.volume is not None for bar in archive.bars) for archive in archives)
        report = validate_capabilities(strategy.requirements, capabilities=capabilities,
            has_volume=has_volume,
            has_funding=False,
            has_rollover=False)
        if not set(strategy.requirements.markets).issubset(markets):
            from .capabilities import CapabilityIssue, CapabilityReport
            issues = report.issues + (CapabilityIssue("MISSING_MARKET_ARCHIVE", "required market archive absent"),)
            return CapabilityReport(fingerprint((report.id, issues)), False, report.requirements_id,
                                    report.capabilities_version, issues)
        return report

    def run(self, *, strategy: Strategy, archives: tuple[VerifiedArchiveSlice, ...],
            specs: tuple[InstrumentSpec, ...], configuration: EngineRunConfiguration) -> BacktestResult:
        started = perf_counter()
        if configuration.execution.end_policy is EndPolicy.FLATTEN:
            raise ValueError("capability preflight rejected run: END_FLATTEN_UNSUPPORTED")
        for archive in archives: archive.validate()
        report = self.preflight(strategy=strategy, archives=archives)
        if not report.accepted:
            raise ValueError("capability preflight rejected run: " + ",".join(i.code for i in report.issues))
        spec_by_instrument = {s.instrument_id: s for s in specs}
        if len(spec_by_instrument) != len(specs): raise ValueError("duplicate instrument specification")
        archive_instruments = {bar.instrument_id for archive in archives for bar in archive.bars}
        if set(spec_by_instrument) != archive_instruments:
            raise ValueError("instrument specification scope mismatch")

        bars = sorted((bar for archive in archives for bar in archive.bars
                       if configuration.evaluation_start <= bar.close_time < configuration.evaluation_end),
                      key=lambda b: (b.close_time, b.market, b.instrument_id, b.sequence, b.id))
        events = [event for archive in archives for event in archive.supplemental_events
                  if configuration.evaluation_start <= event.event_time < configuration.evaluation_end]
        orders = []; fills = []; positions = []; accounting = []; rejections = []
        pending: list[OrderRecord] = []
        quantities: dict[str, Decimal] = {}
        average: dict[str, Decimal] = {}
        cash = configuration.starting_cash
        realized = fees = funding = Decimal("0")
        peak = cash
        visible: dict[tuple[str, str], list] = {}

        for bar in bars:
            event = CoreEvent(fingerprint((bar.id, EventType.FINALIZED_MARKET_BAR.value)),
                EventType.FINALIZED_MARKET_BAR, bar.close_time, bar.market, bar.instrument_id,
                bar.contract_id, bar.session_id, bar.source_id, bar.source_checksum, bar.sequence)
            events.append(event)
            spec = spec_by_instrument.get(bar.instrument_id)
            if spec is None: raise ValueError("missing immutable instrument specification")
            if spec.market != bar.market or not (spec.effective_from <= bar.close_time and
                    (spec.effective_to is None or bar.close_time < spec.effective_to)):
                raise ValueError("instrument specification market/effective-time mismatch")
            for value in (bar.open, bar.high, bar.low, bar.close):
                if value % spec.tick_size != 0:
                    raise ValueError("market price is off the instrument tick grid")

            if bar.missing_before:
                events.append(CoreEvent(fingerprint((bar.id, "missing", bar.missing_before)),
                    EventType.DATA_QUALITY_HALT, bar.open_time, bar.market, bar.instrument_id,
                    bar.contract_id, bar.session_id, bar.source_id, bar.source_checksum, bar.sequence))
                rejections.append("DATA_QUALITY_HALT_MISSING_INTERVAL")

            # Orders created from bar t are eligible only on a later valid bar.
            for order in tuple(pending):
                if order.instrument_id != bar.instrument_id or bar.open_time < order.eligible_after:
                    continue
                if not bar.tradable or bar.missing_before:
                    continue
                requested = order.quantity
                if configuration.execution.volume_participation is None:
                    rejections.append("MISSING_VOLUME_PARTICIPATION")
                    pending.remove(order); continue
                maximum = _quantize_down(bar.volume * configuration.execution.volume_participation,
                                         spec.quantity_step)
                filled_qty = min(requested, maximum)
                if filled_qty <= 0:
                    continue
                price_move = spec.tick_size * spec.slippage_ticks
                price = bar.open + price_move if order.side is Side.BUY else bar.open - price_move
                slippage = abs(price - bar.open) * filled_qty * spec.contract_multiplier
                commission = abs(price * filled_qty * spec.contract_multiplier) * spec.commission_rate
                fill = FillRecord(fingerprint((order.id, bar.id, filled_qty, price)), order.id, bar.id,
                    bar.open_time, price, filled_qty, commission, slippage, filled_qty < requested)
                fills.append(fill); fees += commission
                signed = filled_qty if order.side is Side.BUY else -filled_qty
                previous = quantities.get(bar.instrument_id, Decimal("0"))
                prior_avg = average.get(bar.instrument_id, Decimal("0"))
                new = previous + signed
                if previous and (previous > 0) != (signed > 0):
                    closed = min(abs(previous), abs(signed))
                    direction = Decimal("1") if previous > 0 else Decimal("-1")
                    realized += (price - prior_avg) * closed * spec.contract_multiplier * direction
                if new == 0: average[bar.instrument_id] = Decimal("0")
                elif previous and (previous > 0) != (signed > 0) and abs(signed) > abs(previous):
                    # The residual quantity is a new position in the fill direction.
                    average[bar.instrument_id] = price
                elif previous == 0 or (previous > 0) == (signed > 0):
                    average[bar.instrument_id] = ((abs(previous) * prior_avg + abs(signed) * price) /
                                                  (abs(previous) + abs(signed)))
                quantities[bar.instrument_id] = new
                position = PositionSnapshot(fingerprint((fill.id, new, average[bar.instrument_id])),
                    bar.instrument_id, new, average[bar.instrument_id], bar.open_time, fill.id)
                positions.append(position)
                pending.remove(order)
                if filled_qty < requested:
                    remainder = OrderRecord(fingerprint((order.id, "remainder", filled_qty)), order.action_id,
                        order.instrument_id, order.side, order.order_type, requested-filled_qty,
                        order.submitted_at, order.eligible_after, "PARTIAL", None)
                    pending.append(remainder); orders.append(remainder)

            scope = (bar.market, bar.instrument_id)
            visible.setdefault(scope, []).append(bar)
            latest_positions = []
            for instrument_id, quantity in quantities.items():
                if instrument_id != bar.instrument_id: continue
                latest = next((p for p in reversed(positions) if p.instrument_id == instrument_id), None)
                if latest is not None and latest.quantity == quantity: latest_positions.append(latest)
            state = ReadOnlyState(bar.close_time, tuple(visible[scope]), tuple(latest_positions),
                                  cash + realized - fees, tuple(e.id for e in events
                                  if e.market == bar.market and e.instrument_id == bar.instrument_id))
            trigger = Trigger(fingerprint((event.id, "market-trigger")), TriggerKind.MARKET, event)
            actions = ()
            if bar.market in strategy.requirements.markets:
                events.append(CoreEvent(fingerprint((event.id, "signal")), EventType.SIGNAL_EVALUATION,
                    bar.close_time, bar.market, bar.instrument_id, bar.contract_id, bar.session_id,
                    event.id, bar.source_checksum, bar.sequence))
                actions = strategy.evaluate(trigger, state)
            for action in actions:
                if bar.missing_before:
                    rejections.append("DATA_QUALITY_HALT_ACTION_REJECTED"); continue
                if action.kind not in (ActionKind.ENTER, ActionKind.EXIT, ActionKind.REDUCE, ActionKind.FLATTEN):
                    rejections.append("UNSUPPORTED_ACTION_KIND:" + action.kind.value); continue
                if action.instrument_id != bar.instrument_id or action.side is None or action.quantity is None:
                    rejections.append("ACTION_SCOPE_OR_QUANTITY_INVALID"); continue
                require_decimal(action.quantity, "action quantity", positive=True)
                if _quantize_down(action.quantity, spec.quantity_step) != action.quantity:
                    rejections.append("QUANTITY_STEP_INVALID"); continue
                if action.order_type in (OrderType.LIMIT, OrderType.STOP) and configuration.execution.reject_ambiguous_intrabar:
                    rejections.append("AMBIGUOUS_INTRABAR_WORST_CASE_REJECTED"); continue
                exposure = abs(action.quantity * bar.close * spec.contract_multiplier)
                if exposure > configuration.risk.max_gross_exposure or exposure * spec.margin_rate > configuration.risk.max_margin:
                    rejections.append("RISK_LIMIT_REJECTED"); continue
                order = OrderRecord(fingerprint((action.id, event.id)), action.id, action.instrument_id,
                    action.side, action.order_type, action.quantity, bar.close_time, bar.close_time,
                    "SUBMITTED", None)
                orders.append(order); pending.append(order)
                events.append(CoreEvent(fingerprint((order.id, "submitted")), EventType.ORDER_SUBMITTED,
                    bar.close_time, bar.market, bar.instrument_id, bar.contract_id, bar.session_id,
                    order.id, bar.source_checksum, bar.sequence))

            unrealized = sum(((bar.close - average.get(i, bar.close)) * q *
                             spec_by_instrument[i].contract_multiplier for i, q in quantities.items()
                             if i == bar.instrument_id), Decimal("0"))
            gross = sum((abs(q * (bar.close if i == bar.instrument_id else average[i]) *
                            spec_by_instrument[i].contract_multiplier) for i, q in quantities.items()), Decimal("0"))
            margin = sum((abs(q * (bar.close if i == bar.instrument_id else average[i]) *
                             spec_by_instrument[i].contract_multiplier) * spec_by_instrument[i].margin_rate
                         for i, q in quantities.items()), Decimal("0"))
            equity = cash + realized + unrealized - fees + funding
            peak = max(peak, equity); drawdown = peak - equity
            accounting.append(AccountingSnapshot(fingerprint((event.id, equity, len(fills))), bar.close_time,
                cash, realized, unrealized, fees, funding, margin, gross, equity, drawdown,
                tuple(fill.id for fill in fills)))
            events.append(CoreEvent(fingerprint((event.id, "mark", equity)), EventType.MARK_TO_MARKET,
                bar.close_time, bar.market, bar.instrument_id, bar.contract_id, bar.session_id,
                accounting[-1].id, bar.source_checksum, bar.sequence))
            events.append(CoreEvent(fingerprint((event.id, "risk", gross, margin)), EventType.RISK,
                bar.close_time, bar.market, bar.instrument_id, bar.contract_id, bar.session_id,
                configuration.risk.version, bar.source_checksum, bar.sequence))

        if any(quantity != 0 for quantity in quantities.values()):
            if configuration.execution.end_policy is EndPolicy.REJECT_OPEN:
                rejections.append("OPEN_POSITION_AT_END")
            else:
                rejections.append("END_FLATTEN_REQUIRES_NEXT_VALID_BAR")
        for order in pending: rejections.append("UNFILLED_ORDER_AT_END:" + order.id)
        end_time = configuration.evaluation_end
        events.append(CoreEvent(fingerprint((configuration.run_id, "end")), EventType.END_OF_RUN,
            end_time, "ALL", "ALL", None, None, configuration.run_id, fingerprint(configuration), len(events)))
        ordered_events = tuple(sorted(events, key=lambda e: e.ordering_key))
        finalized = sum(1 for p in positions if p.quantity == 0)
        counts = tuple((market, 0) for market in sorted({a.market for a in archives}))
        gate = "INSUFFICIENT_EVIDENCE" if any(count < 200 for _, count in counts) else "FAIL"
        result_seed = (configuration.run_id, tuple((a.dataset_fingerprint, a.sha256_hex,
            tuple(a.active_windows)) for a in archives),
            fingerprint(strategy.requirements), fingerprint(configuration), report.id,
            tuple(specs),
            ordered_events, tuple(orders), tuple(fills), tuple(positions), tuple(accounting), tuple(rejections))
        return BacktestResult(fingerprint(result_seed), "core-v1-result-1", configuration.run_id,
            tuple(a.dataset_fingerprint for a in archives), fingerprint(strategy.requirements),
            fingerprint(configuration), report.id, ordered_events, tuple(orders), tuple(fills),
            tuple(positions), tuple(accounting), tuple(rejections), finalized, counts, gate,
            (("elapsed_seconds", f"{perf_counter()-started:.6f}"),))
