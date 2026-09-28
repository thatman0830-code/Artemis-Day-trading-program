from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256

from backtesting.adapter import TradingBrainMarketDataAdapter
from backtesting.accounting import EquitySizingPolicy, SimulatedEquityLedger, SimulatedEquityLedgerEngine
from backtesting.manifests import BacktestRunManifest
from backtesting.orchestrator import BatchEvaluationResult, EvaluationOutcome, OrchestrationCheckpoint
from backtesting.replay import ReplayCheckpoint, ReplayPublication
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION
from strategy.trading_brain.p29_1_entry_execution import (
    EntryExecutionContext, EntryExecutionEngine, EntryExecutionHistory,
    EntryFill, EntryOrder, ExecutionMode, OrderState,
)
from strategy.trading_brain.p29_2_position_sizing import (
    InstrumentSizingConstraints, PositionSizing, PositionSizingEngine,
    PreFillAccountFact, SizingRiskConfiguration,
)
from strategy.trading_brain.p29_3_protective_orders import (
    ProtectiveOrderEngine, ProtectiveOrderHistory, ProtectiveOrderSet,
)
from strategy.trading_brain.p29_4_exit_resolution import (
    ExecutionRecord, ExitResolutionEngine, ExitResolutionHistory, PriceObservation,
)
from strategy.trading_brain.p29_5_execution_costs import (
    ExecutionCostEngine, ExecutionCostHistory, ExecutionCostRecord,
    ExecutionCostSpecification,
)
from strategy.trading_brain.p29_6_position_lifecycle import (
    Position, PositionLifecycleEngine, PositionLifecycleHistory,
)
from strategy.trading_brain.position_state_contract import PositionState
from strategy.trading_brain.p29_7_1_trade_accounting import (
    TradeAccounting, TradeAccountingEngine, TradeAccountingHistory,
)


def _ms(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("simulation timestamps must be UTC timezone-aware")
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _hash(*parts: object) -> str:
    return sha256("\x1f".join(map(str, parts)).encode()).hexdigest()


@dataclass(frozen=True)
class SimulationAccountInput:
    id: str
    account_id: str
    starting_equity: Decimal
    risk_percent: Decimal
    input_version: str
    immutable: bool = True


@dataclass(frozen=True)
class SimulationInstrumentInput:
    id: str
    symbol: str
    minimum_tick: Decimal
    tick_value: Decimal
    contract_multiplier: Decimal
    minimum_quantity: Decimal
    quantity_increment: Decimal
    maximum_quantity: Decimal | None
    input_version: str
    immutable: bool = True


@dataclass(frozen=True)
class TradeSimulationConfiguration:
    id: str
    account: SimulationAccountInput
    instrument: SimulationInstrumentInput
    execution_costs: ExecutionCostSpecification
    calculation_version: str
    mode: ExecutionMode = ExecutionMode.PAPER
    exchange_submission_enabled: bool = False
    equity_policy: EquitySizingPolicy = EquitySizingPolicy.COMPOUNDED
    immutable: bool = True


@dataclass(frozen=True)
class SimulationMissingPrerequisite:
    id: str
    owner: str
    reason: str
    batch_id: str
    event_time: datetime


@dataclass(frozen=True)
class LifecycleReference:
    owner: str
    action: str
    output_id: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SimulatedTrade:
    id: str
    setup_fact_id: str
    qualification: object
    selection: object
    stop: object
    target: object
    order: EntryOrder
    fill: EntryFill | None = None
    sizing: PositionSizing | None = None
    protective_set: ProtectiveOrderSet | None = None
    position: Position | None = None
    exit: ExecutionRecord | None = None
    costs: ExecutionCostRecord | None = None
    accounting: TradeAccounting | None = None
    created_batch_sequence: int = 0
    filled_batch_sequence: int | None = None


@dataclass(frozen=True)
class SimulationBatchResult:
    id: str
    batch_id: str
    batch_sequence: int
    event_time: datetime
    references: tuple[LifecycleReference, ...]
    missing: tuple[SimulationMissingPrerequisite, ...]
    active_trade_id: str | None


@dataclass(frozen=True)
class TradeSimulationState:
    id: str
    dataset_id: str
    dataset_fingerprint: str
    run_id: str
    contract_version: str
    configuration_id: str
    last_batch_sequence: int | None = None
    consumed_setup_ids: tuple[str, ...] = ()
    trades: tuple[SimulatedTrade, ...] = ()
    entry_history: EntryExecutionHistory = EntryExecutionHistory()
    protective_history: ProtectiveOrderHistory = ProtectiveOrderHistory()
    exit_history: ExitResolutionHistory = ExitResolutionHistory()
    cost_history: ExecutionCostHistory = ExecutionCostHistory()
    position_history: PositionLifecycleHistory = PositionLifecycleHistory()
    accounting_history: TradeAccountingHistory = TradeAccountingHistory()
    equity_ledger: SimulatedEquityLedger | None = None
    batch_results: tuple[SimulationBatchResult, ...] = ()
    setup_outcomes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulationCommit:
    state: TradeSimulationState
    result: SimulationBatchResult


@dataclass(frozen=True)
class SimulationCheckpoint:
    id: str
    state_id: str
    next_batch_sequence: int
    replay_checkpoint_id: str
    orchestration_checkpoint_id: str
    active_order_id: str | None
    open_position_id: str | None
    protective_set_id: str | None
    accounting_cursor_id: str | None
    equity_snapshot_id: str | None


class HistoricalTradeSimulator:
    """Phase 4 deterministic caller of canonical #29.1-#29.6 only."""

    def __init__(self, *, run: BacktestRunManifest, configuration: TradeSimulationConfiguration):
        self.run, self.configuration = run, configuration
        if run.trading_brain_contract_version != INTERFACE_CONTRACT_VERSION:
            raise ValueError("Trading Brain contract mismatch")
        if configuration.exchange_submission_enabled or configuration.mode != ExecutionMode.PAPER:
            raise ValueError("Phase 4 is paper simulation only")
        if configuration.equity_policy is not EquitySizingPolicy.COMPOUNDED:
            raise ValueError("Phase 5A supports only the canonical compounded equity policy")
        if configuration.account.starting_equity != run.starting_equity:
            raise ValueError("starting equity must originate unchanged from the run manifest")
        if configuration.instrument.symbol != run.symbol:
            raise ValueError("instrument/run symbol mismatch")
        if configuration.execution_costs.id != run.execution_cost_configuration_id:
            raise ValueError("execution-cost configuration identity mismatch")
        versions = {configuration.account.input_version, configuration.instrument.input_version,
                    configuration.execution_costs.input_version}
        if len(versions) != 1:
            raise ValueError("simulation input versions mismatch")
        self.entry = EntryExecutionEngine(); self.sizer = PositionSizingEngine()
        self.protective = ProtectiveOrderEngine(); self.exit_engine = ExitResolutionEngine()
        self.cost = ExecutionCostEngine(); self.lifecycle = PositionLifecycleEngine()
        self.accounting = TradeAccountingEngine(); self.ledger_engine = SimulatedEquityLedgerEngine()

    def initial_state(self) -> TradeSimulationState:
        ident = _hash("phase4-state-v1", self.run.id, self.configuration.id)
        ledger = self.ledger_engine.initial(run_id=self.run.id,
            starting_equity=self.run.starting_equity,
            effective_time=_ms(self.run.replay_start_inclusive),
            input_version=self.configuration.account.input_version)
        return TradeSimulationState(ident, self.run.dataset_id, self.run.dataset_fingerprint,
                                    self.run.id, INTERFACE_CONTRACT_VERSION, self.configuration.id,
                                    accounting_history=TradeAccountingHistory(), equity_ledger=ledger)

    def _validate(self, publication, evaluation, state):
        if not isinstance(publication, ReplayPublication) or not isinstance(evaluation, BatchEvaluationResult):
            raise TypeError("exact Phase 2 publication and Phase 3 evaluation are required")
        if evaluation.context.replay_batch_id != publication.batch.id or evaluation.context.run_id != self.run.id:
            raise ValueError("Phase 2/3 batch identity mismatch")
        if evaluation.context.dataset_fingerprint != state.dataset_fingerprint or state.configuration_id != self.configuration.id:
            raise ValueError("simulation state identity mismatch")
        expected = 0 if state.last_batch_sequence is None else state.last_batch_sequence + 1
        if publication.batch.sequence != expected:
            raise ValueError("simulation batches must be contiguous and chronological")

    def evaluate(self, *, publication: ReplayPublication, evaluation: BatchEvaluationResult,
                 state: TradeSimulationState,
                 finer_observations: dict[str, tuple[PriceObservation, ...]] | None = None) -> SimulationCommit:
        if state.last_batch_sequence == publication.batch.sequence:
            previous = next((row for row in state.batch_results if row.batch_id == publication.batch.id), None)
            if previous is None:
                raise ValueError("conflicting duplicate simulation batch")
            return SimulationCommit(state, previous)
        self._validate(publication, evaluation, state)
        finer_observations = finer_observations or {}
        now = _ms(publication.batch.event_time)
        trades = list(state.trades); refs = []; missing = []
        eh, ph, xh, ch, lh, ah = (state.entry_history, state.protective_history,
            state.exit_history, state.cost_history, state.position_history, state.accounting_history)
        ledger = state.equity_ledger
        if ledger is None:
            raise ValueError("Phase 5A equity ledger is missing")

        # Existing facts are advanced before this batch's newly armed setup is consumed.
        for index, trade in enumerate(trades):
            if trade.exit is not None:
                continue
            relevant = [event.candle for event in publication.batch.events
                        if event.symbol == trade.order.symbol and event.timeframe.value.lower() == trade.order.timeframe.lower()]
            if len(relevant) > 1:
                raise ValueError("atomic batch contains conflicting execution candles")
            if trade.fill is None and relevant:
                result = self.entry.evaluate_candle(order=trade.order,
                    candle=TradingBrainMarketDataAdapter.to_entry_candle(relevant[0]), history=eh)
                eh = result.history
                if result.fill:
                    filled = result.order; assert filled
                    config_time = _ms(evaluation.context.evaluation_time)
                    account = PreFillAccountFact(_hash("account", self.configuration.account.id, result.fill.id, ledger.latest.id),
                        self.configuration.account.account_id, ledger.latest.equity,
                        max(config_time, trade.qualification.finalized_time), self.configuration.account.input_version)
                    risk = SizingRiskConfiguration(_hash("risk", self.configuration.account.id),
                        self.configuration.account.risk_percent, config_time, self.configuration.account.input_version)
                    i = self.configuration.instrument
                    constraints = InstrumentSizingConstraints(i.id, i.symbol, i.minimum_tick, i.tick_value,
                        i.contract_multiplier, i.minimum_quantity, i.quantity_increment, config_time,
                        i.input_version, i.maximum_quantity)
                    sized = self.sizer.calculate(qualification=trade.qualification, selection=trade.selection,
                        stop=trade.stop, order=filled, fill=result.fill, account=account,
                        risk_configuration=risk, constraints=constraints, calculated_time=now)
                    if not sized.valid:
                        missing.append(self._missing("#29.2", sized.error.reason, publication))
                        trades[index] = replace(trade, order=filled, fill=result.fill,
                                                filled_batch_sequence=publication.batch.sequence)
                        continue
                    proposal = sized.proposal; assert proposal
                    made = self.protective.create(qualification=trade.qualification, stop=trade.stop,
                        target=trade.target, entry_order=filled, fill=result.fill, sizing=proposal,
                        created_time=now, history=ph)
                    ph = made.history
                    if not made.valid:
                        missing.append(self._missing("#29.3", made.error.reason, publication)); continue
                    activated = self.protective.activate(protective_set=made.protective_set,
                                                         activation_time=now, history=ph)
                    ph = activated.history
                    opened = self.lifecycle.open(entry_order=filled, fill=result.fill, sizing=proposal,
                        protective_set=activated.protective_set, protective_history=ph, history=lh)
                    lh = opened.history
                    if not opened.valid:
                        missing.append(self._missing("#29.6", opened.error.reason, publication)); continue
                    trade = replace(trade, order=filled, fill=result.fill, sizing=proposal,
                                    protective_set=activated.protective_set, position=opened.position,
                                    filled_batch_sequence=publication.batch.sequence)
                    trades[index] = trade
                    refs.extend((LifecycleReference("#29.1", "FILL", result.fill.id, (filled.id,)),
                                 LifecycleReference("#29.2", "SIZE", proposal.id, (result.fill.id,)),
                                 LifecycleReference("#29.3", "ACTIVATE", activated.protective_set.id, (proposal.id,)),
                                 LifecycleReference("#29.6", "OPEN", opened.position.snapshot_id, (activated.protective_set.id,))))
                elif result.error and result.error.code.value != "ENTRY_NOT_FILLED":
                    missing.append(self._missing("#29.1", result.error.reason, publication))
            elif trade.position and trade.position.state == PositionState.OPEN and relevant and trade.filled_batch_sequence != publication.batch.sequence:
                market = TradingBrainMarketDataAdapter.to_exit_market_data(
                    relevant[0], input_version=self.configuration.instrument.input_version,
                    observations=finer_observations.get(relevant[0].id, ()))
                resolved = self.exit_engine.evaluate(protective_set=trade.protective_set,
                    protective_history=ph, position=self.lifecycle.open_boundary(trade.position),
                    market=market, history=xh)
                xh = resolved.history
                if resolved.error:
                    missing.append(self._missing("#29.4", resolved.error.reason, publication))
                elif resolved.resolution:
                    costs = self.cost.calculate(entry_fill=trade.fill, sizing=trade.sizing,
                        exit_execution=resolved.resolution, specification=self.configuration.execution_costs,
                        calculated_time=now, history=ch)
                    ch = costs.history
                    if not costs.valid:
                        missing.append(self._missing("#29.5", costs.error.reason, publication)); continue
                    closed = self.lifecycle.close(position=trade.position, exit_execution=resolved.resolution,
                        exit_history=xh, history=lh)
                    lh = closed.history
                    if not closed.valid:
                        missing.append(self._missing("#29.6", closed.error.reason, publication)); continue
                    accounted = self.accounting.calculate(
                        strategy_id=self.run.strategy_configuration_version,
                        position=closed.position, entry_fill=trade.fill, sizing=trade.sizing,
                        exit_execution=resolved.resolution, costs=costs.record,
                        accounting_time=now, history=ah)
                    ah = accounted.history
                    if not accounted.valid:
                        missing.append(self._missing("#29.7.1", accounted.error.reason, publication)); continue
                    try:
                        ledger = self.ledger_engine.apply(ledger=ledger, accounting=accounted.record)
                    except (TypeError, ValueError) as error:
                        missing.append(self._missing("EQUITY_LEDGER", str(error), publication)); continue
                    trades[index] = replace(trade, position=closed.position, exit=resolved.resolution,
                                            costs=costs.record, accounting=accounted.record)
                    refs.extend((LifecycleReference("#29.4", "EXIT", resolved.resolution.id, (market.id,)),
                                 LifecycleReference("#29.5", "COST", costs.record.id, (resolved.resolution.id,)),
                                 LifecycleReference("#29.6", "CLOSE", closed.position.snapshot_id, (resolved.resolution.id,)),
                                 LifecycleReference("#29.7.1", "ACCOUNT", accounted.record.id, (closed.position.snapshot_id,)),
                                 LifecycleReference("EQUITY_LEDGER", "APPLY", ledger.latest.id, (accounted.record.id,))))

        fact = evaluation.setup_fact
        armed = evaluation.outcome in (EvaluationOutcome.ARMED_CONTINUATION,
                                       EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL)
        consumed = list(state.consumed_setup_ids)
        if armed and fact.final_qualification and fact.final_qualification.setup_id not in consumed:
            consumed.append(fact.final_qualification.setup_id)
            availability = self.lifecycle.availability(symbol=self.run.symbol, checked_time=now, history=lh)
            if availability.open_position_count:
                missing.append(self._missing("#29.6", "LIVE_POSITION_ALREADY_EXISTS", publication))
            elif any(t.exit is None for t in trades):
                missing.append(self._missing("SIMULATION", "ACTIVE_LIFECYCLE_ALREADY_EXISTS", publication))
            else:
                selection = getattr(fact.entry_zone, "selection", fact.entry_zone)
                stop = getattr(fact.stop, "stop", fact.stop)
                context = EntryExecutionContext(_hash("entry-context", fact.id), self.run.symbol,
                    next(c.timeframe for c in selection.frozen_candidates if c.zone_id == selection.selected_zone_id),
                    self.configuration.instrument.minimum_tick, self.configuration.mode, now)
                made = self.entry.create_order(qualification=fact.final_qualification, selection=selection,
                    context=context, position_availability=availability, created_time=now, history=eh)
                eh = made.history
                if made.valid:
                    active = self.entry.activate_order(order=made.order, activation_time=now, history=eh)
                    eh = active.history
                    trade = SimulatedTrade(_hash("trade", fact.id, active.order.id), fact.id,
                        fact.final_qualification, selection, stop, fact.target, active.order,
                        created_batch_sequence=publication.batch.sequence)
                    trades.append(trade); refs.append(LifecycleReference("#29.1", "ACTIVATE", active.order.record_id, (fact.id,)))
                else:
                    missing.append(self._missing("#29.1", made.error.reason, publication))

        active_id = next((t.id for t in trades if t.exit is None), None)
        result_id = _hash("phase4-batch-v1", state.id, publication.batch.id,
                          *(r.output_id for r in refs), *(m.id for m in missing))
        result = SimulationBatchResult(result_id, publication.batch.id, publication.batch.sequence,
                                       publication.batch.event_time, tuple(refs), tuple(missing), active_id)
        next_id = _hash("phase4-state-v1", state.id, result.id)
        next_state = TradeSimulationState(next_id, state.dataset_id, state.dataset_fingerprint,
            state.run_id, state.contract_version, state.configuration_id, publication.batch.sequence,
            tuple(consumed), tuple(trades), eh, ph, xh, ch, lh, ah, ledger,
            state.batch_results + (result,),
            state.setup_outcomes + (evaluation.outcome.value,))
        return SimulationCommit(next_state, result)

    @staticmethod
    def _missing(owner, reason, publication):
        return SimulationMissingPrerequisite(_hash("phase4-missing", owner, reason, publication.batch.id),
            owner, reason, publication.batch.id, publication.batch.event_time)

    def checkpoint(self, *, state: TradeSimulationState, replay_checkpoint: ReplayCheckpoint,
                   orchestration_checkpoint: OrchestrationCheckpoint) -> SimulationCheckpoint:
        expected = 0 if state.last_batch_sequence is None else state.last_batch_sequence + 1
        if replay_checkpoint.next_batch_sequence != expected or orchestration_checkpoint.replay_checkpoint != replay_checkpoint:
            raise ValueError("Phase 2/3/4 checkpoint cursors mismatch")
        active = next((t for t in state.trades if t.exit is None), None)
        open_position = active.position if active and active.position and active.position.state == PositionState.OPEN else None
        rid = _hash("replay-checkpoint", replay_checkpoint.event_sequence_id, replay_checkpoint.next_batch_sequence)
        oid = orchestration_checkpoint.id
        ident = _hash("phase4-checkpoint-v1", state.id, rid, oid)
        return SimulationCheckpoint(ident, state.id, expected, rid, oid,
            active.order.id if active else None, open_position.id if open_position else None,
            active.protective_set.id if active and active.protective_set else None,
            state.accounting_history.records[-1].id if state.accounting_history.records else None,
            state.equity_ledger.latest.id if state.equity_ledger else None)

    def validate_resume(self, *, state: TradeSimulationState, checkpoint: SimulationCheckpoint,
                        replay_checkpoint: ReplayCheckpoint,
                        orchestration_checkpoint: OrchestrationCheckpoint) -> None:
        if checkpoint != self.checkpoint(state=state, replay_checkpoint=replay_checkpoint,
                                         orchestration_checkpoint=orchestration_checkpoint):
            raise ValueError("Phase 4 checkpoint or state mismatch")
