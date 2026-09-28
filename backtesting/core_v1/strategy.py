from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from .models import Action, ActionKind, OrderType, ReadOnlyState, Side, StrategyRequirements, Trigger, TriggerKind, fingerprint


class Strategy(Protocol):
    @property
    def requirements(self) -> StrategyRequirements: ...
    def evaluate(self, trigger: Trigger, state: ReadOnlyState) -> tuple[Action, ...]: ...


@dataclass(frozen=True)
class NoOpStrategy:
    strategy_id: str = "NO_OP"
    strategy_version: str = "1"
    markets: tuple[str, ...] = ("ES",)

    @property
    def requirements(self) -> StrategyRequirements:
        return StrategyRequirements(self.strategy_id, self.strategy_version, self.markets,
            ("open", "high", "low", "close"), (TriggerKind.MARKET,), (OrderType.MARKET,))

    def evaluate(self, trigger: Trigger, state: ReadOnlyState) -> tuple[Action, ...]:
        return ()


@dataclass(frozen=True)
class DeterministicFixtureStrategy:
    instrument_id: str
    market: str
    quantity: Decimal
    enter_sequence: int = 0
    exit_sequence: int = 2

    @property
    def requirements(self) -> StrategyRequirements:
        return StrategyRequirements("DETERMINISTIC_FIXTURE", "1", (self.market,),
            ("open", "high", "low", "close", "volume"), (TriggerKind.MARKET,), (OrderType.MARKET,), True)

    def evaluate(self, trigger: Trigger, state: ReadOnlyState) -> tuple[Action, ...]:
        sequence = trigger.event.sequence
        if sequence == self.enter_sequence:
            action = Action("", ActionKind.ENTER, self.instrument_id, Side.BUY, self.quantity)
            return (Action(fingerprint((trigger.id, action)), action.kind, action.instrument_id,
                           action.side, action.quantity, action.order_type),)
        if sequence == self.exit_sequence:
            action = Action("", ActionKind.FLATTEN, self.instrument_id, Side.SELL, self.quantity)
            return (Action(fingerprint((trigger.id, action)), action.kind, action.instrument_id,
                           action.side, action.quantity, action.order_type),)
        return ()
