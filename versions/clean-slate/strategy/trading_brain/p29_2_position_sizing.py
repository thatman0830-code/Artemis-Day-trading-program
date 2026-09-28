from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p13_stop_loss_selection import StopSelection
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import FinalSetupQualification, SetupModel
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelection, EntryZoneSelectionState
from strategy.trading_brain.p29_1_entry_execution import EntryFill, EntryOrder, OrderState


class PositionSizingErrorCode(str, Enum):
    POSITION_SIZE_INVALID = "POSITION_SIZE_INVALID"


@dataclass(frozen=True)
class PreFillAccountFact:
    id: str
    account_id: str
    pre_fill_equity: Decimal
    as_of_time: int
    input_version: str
    immutable: bool = True


@dataclass(frozen=True)
class SizingRiskConfiguration:
    id: str
    risk_percent: Decimal
    effective_time: int
    input_version: str
    immutable: bool = True


@dataclass(frozen=True)
class InstrumentSizingConstraints:
    id: str
    symbol: str
    minimum_tick: Decimal
    tick_value: Decimal
    contract_multiplier: Decimal
    minimum_quantity: Decimal
    quantity_increment: Decimal
    effective_time: int
    input_version: str
    maximum_quantity: Decimal | None = None
    immutable: bool = True


@dataclass(frozen=True)
class PositionSizing:
    id: str
    setup_id: str
    setup_candidate_id: str
    model: SetupModel
    direction: StructuralRegime
    symbol: str
    timeframe: str
    final_qualification_id: str
    entry_zone_selection_id: str
    stop_selection_id: str
    entry_order_id: str
    entry_fill_id: str
    account_fact_id: str
    risk_configuration_id: str
    instrument_constraints_id: str
    input_version: str
    entry_price: Decimal
    stop_price: Decimal
    stop_distance: Decimal
    stop_distance_ticks: Decimal
    pre_fill_equity: Decimal
    risk_percent: Decimal
    maximum_risk: Decimal
    tick_value: Decimal
    contract_multiplier: Decimal
    risk_per_unit: Decimal
    raw_quantity: Decimal
    quantity_increment: Decimal
    minimum_quantity: Decimal
    maximum_quantity: Decimal | None
    proposed_quantity: Decimal
    actual_risk_dollars: Decimal
    calculated_time: int
    authorized: bool = False
    immutable: bool = True


@dataclass(frozen=True)
class PositionSizingError:
    id: str
    code: PositionSizingErrorCode
    reason: str
    setup_id: str | None
    calculated_time: int
    immutable: bool = True


@dataclass(frozen=True)
class PositionSizingResult:
    proposal: PositionSizing | None
    error: PositionSizingError | None

    @property
    def valid(self) -> bool:
        return self.proposal is not None and self.error is None


class PositionSizingEngine:
    """Canonical #29.2 proposed quantity only; never authorizes a trade."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        key = "trading-brain:#29.2:" + kind + ":" + ":".join(map(str, parts))
        return str(uuid5(NAMESPACE_URL, key))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, reason: str, time: int, qualification=None) -> PositionSizingResult:
        setup_id = qualification.setup_id if qualification is not None else None
        return PositionSizingResult(None, PositionSizingError(
            self._uid("error", setup_id or "NONE", reason, time),
            PositionSizingErrorCode.POSITION_SIZE_INVALID, reason, setup_id, int(time),
        ))

    def calculate(
        self, *, qualification: FinalSetupQualification | None,
        selection: EntryZoneSelection | None, stop: StopSelection | None,
        order: EntryOrder | None, fill: EntryFill | None,
        account: PreFillAccountFact | None,
        risk_configuration: SizingRiskConfiguration | None,
        constraints: InstrumentSizingConstraints | None,
        calculated_time: int,
    ) -> PositionSizingResult:
        now = int(calculated_time)
        required = (qualification, selection, stop, order, fill, account, risk_configuration, constraints)
        if any(value is None for value in required):
            return self._invalid("REQUIRED_SIZING_INPUT_MISSING", now, qualification)
        assert qualification and selection and stop and order and fill and account and risk_configuration and constraints
        try:
            equity, percent, tick, tick_value, multiplier, minimum, increment = map(
                self._decimal,
                (account.pre_fill_equity, risk_configuration.risk_percent,
                 constraints.minimum_tick, constraints.tick_value,
                 constraints.contract_multiplier, constraints.minimum_quantity,
                 constraints.quantity_increment),
            )
            maximum = self._decimal(constraints.maximum_quantity) if constraints.maximum_quantity is not None else None
            entry, stop_price = self._decimal(selection.eq_normalized), self._decimal(stop.stop_price)
        except (ValueError, TypeError):
            return self._invalid("NON_FINITE_OR_INVALID_NUMERIC_INPUT", now, qualification)
        if any(value <= 0 for value in (equity, percent, tick, tick_value, multiplier, minimum, increment)):
            return self._invalid("NON_POSITIVE_ACCOUNT_RISK_OR_CONSTRAINT", now, qualification)
        if percent > Decimal("100"):
            return self._invalid("RISK_PERCENT_OUT_OF_RANGE", now, qualification)
        if maximum is not None and (maximum <= 0 or maximum < minimum):
            return self._invalid("MAXIMUM_QUANTITY_INVALID", now, qualification)
        versions = {account.input_version, risk_configuration.input_version, constraints.input_version}
        if len(versions) != 1 or not next(iter(versions)).strip():
            return self._invalid("INPUT_VERSION_MISMATCH", now, qualification)
        if constraints.symbol != order.symbol or fill.symbol != order.symbol:
            return self._invalid("SYMBOL_IDENTITY_MISMATCH", now, qualification)
        if fill.timeframe.lower() != order.timeframe.lower():
            return self._invalid("TIMEFRAME_IDENTITY_MISMATCH", now, qualification)
        if selection.state != EntryZoneSelectionState.SELECTED or selection.eq_normalized is None:
            return self._invalid("FROZEN_ENTRY_INVALID", now, qualification)
        identity_valid = (
            qualification.setup_id == selection.setup_id == stop.setup_id == order.setup_id == fill.setup_id
            and qualification.setup_candidate_id == selection.setup_candidate_id == order.setup_candidate_id
            and qualification.model == selection.model == stop.model == order.model
            and qualification.direction == selection.direction == stop.direction == order.direction
            and qualification.entry_zone_selection_id == selection.id == stop.entry_zone_selection_id == order.entry_zone_selection_id == fill.entry_zone_selection_id
            and qualification.stop_selection_id == stop.id
            and order.final_qualification_id == qualification.id
            and fill.order_id == order.id and fill.order_record_id == order.record_id
        )
        if not identity_valid:
            return self._invalid("SIZING_INPUT_IDENTITY_MISMATCH", now, qualification)
        if order.state != OrderState.FILLED or fill.event != "ENTRY_FILL_CONFIRMED":
            return self._invalid("ENTRY_FILL_NOT_CONFIRMED", now, qualification)
        if not (entry == stop.frozen_entry_price == qualification.entry == order.limit_price == fill.fill_price):
            return self._invalid("FROZEN_ENTRY_PRICE_MISMATCH", now, qualification)
        if stop_price != qualification.stop or tick != selection.minimum_tick or tick != stop.minimum_tick or tick != order.minimum_tick:
            return self._invalid("FROZEN_STOP_OR_TICK_MISMATCH", now, qualification)
        if entry % tick != 0 or stop_price % tick != 0:
            return self._invalid("PRICE_OFF_TICK_GRID", now, qualification)
        if qualification.direction == StructuralRegime.BULLISH and not stop_price < entry:
            return self._invalid("LONG_STOP_GEOMETRY_INVALID", now, qualification)
        if qualification.direction == StructuralRegime.BEARISH and not entry < stop_price:
            return self._invalid("SHORT_STOP_GEOMETRY_INVALID", now, qualification)
        latest = max(qualification.finalized_time, selection.selection_time or selection.eligibility_time,
                     stop.selection_time, order.state_time, fill.fill_time,
                     account.as_of_time, risk_configuration.effective_time, constraints.effective_time)
        if now < latest or account.as_of_time > fill.fill_time or account.as_of_time < qualification.finalized_time:
            return self._invalid("SIZING_INPUT_CHRONOLOGY_INVALID", now, qualification)

        with localcontext() as context:
            context.prec = max(context.prec, 28)
            distance = abs(entry - stop_price)
            ticks = distance / tick
            maximum_risk = equity * percent / Decimal("100")
            risk_per_unit = ticks * tick_value * multiplier
            if distance <= 0 or ticks <= 0 or maximum_risk <= 0 or risk_per_unit <= 0:
                return self._invalid("NON_POSITIVE_RISK", now, qualification)
            raw = maximum_risk / risk_per_unit
            cap = raw if maximum is None else min(raw, maximum)
            quantity = (cap / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
            actual = quantity * risk_per_unit
        if quantity < minimum or quantity <= 0 or actual <= 0 or actual > maximum_risk:
            return self._invalid("POSITION_QUANTITY_OUTSIDE_PERMITTED_RISK_OR_SIZE", now, qualification)
        proposal_id = self._uid("proposal", qualification.id, selection.id, stop.id, order.id, fill.id, account.id, risk_configuration.id, constraints.id, now)
        proposal = PositionSizing(
            proposal_id, qualification.setup_id, qualification.setup_candidate_id,
            qualification.model, qualification.direction, order.symbol, order.timeframe,
            qualification.id, selection.id, stop.id, order.id, fill.id,
            account.id, risk_configuration.id, constraints.id, account.input_version,
            entry, stop_price, distance, ticks, equity, percent, maximum_risk,
            tick_value, multiplier, risk_per_unit, raw, increment, minimum, maximum,
            quantity, actual, now,
        )
        return PositionSizingResult(proposal, None)
