"""Evidence-bound paper performance ledger.

This module bridges accepted paper-gateway fill events into the existing Phase 4
instrument-accounting ledger.  It creates neither orders nor fills and carries
no trading authority.  A paper fill is accounted only when its gateway event,
accepted execution fill, and explicit cost evidence agree exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from backtesting.execution_accounting_v2.accounting import (
    AccountingEventKind, AccountingEventV2, FillEconomicsV2,
    InstrumentAccountingLedgerV2, PriceEvidenceV2,
)
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_gateway_v2 import (
    PaperEventKind, PaperGatewaySnapshotV1, PaperOrderEventV1,
)


SCHEMA_VERSION = "paper-performance-ledger-v1"


class PaperPerformanceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PaperFillBindingV1:
    paper_order_id: str
    paper_event_id: str
    paper_event_fingerprint: str
    execution_fill_id: str
    accounting_event_id: str
    quantity: str
    economic_price: str
    total_cost: str
    binding_id: str


@dataclass(frozen=True, slots=True)
class PaperPerformanceLedgerV1:
    schema_version: str
    gateway_snapshot_id: str
    accounting: InstrumentAccountingLedgerV2
    fill_bindings: tuple[PaperFillBindingV1, ...]
    ledger_id: str
    advisory_only: bool = True
    live_trading_permitted: bool = False
    trading_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise PaperPerformanceError("unsupported paper performance schema")
        if not isinstance(self.fill_bindings, tuple):
            raise PaperPerformanceError("fill bindings must be immutable")
        if self.advisory_only is not True or self.live_trading_permitted is not False or self.trading_authority is not False:
            raise PaperPerformanceError("paper performance ledger cannot carry trading authority")
        self.accounting.verify_integrity()
        expected = self._identity(self.gateway_snapshot_id, self.accounting, self.fill_bindings)
        if self.ledger_id != expected:
            raise PaperPerformanceError("paper performance ledger identity mismatch")
        event_ids = tuple(item.paper_event_id for item in self.fill_bindings)
        if len(event_ids) != len(set(event_ids)):
            raise PaperPerformanceError("paper fill event identities must be unique")

    @staticmethod
    def _identity(gateway_snapshot_id, accounting, bindings) -> str:
        return canonical_fingerprint(SCHEMA_VERSION, gateway_snapshot_id,
            accounting.ledger_fingerprint, bindings, True, False, False)

    @classmethod
    def create(cls, accounting: InstrumentAccountingLedgerV2,
               gateway: PaperGatewaySnapshotV1) -> "PaperPerformanceLedgerV1":
        gateway = PaperGatewaySnapshotV1.resume(gateway)
        accounting.verify_integrity()
        if accounting.market not in ("BTC", "BTC-PERP"):
            raise PaperPerformanceError("paper performance v1 supports BTC only")
        if accounting.events:
            raise PaperPerformanceError("new paper performance ledger requires empty accounting history")
        return cls._build(gateway.snapshot_id, accounting, ())

    @classmethod
    def _build(cls, gateway_snapshot_id, accounting, bindings):
        identity = cls._identity(gateway_snapshot_id, accounting, bindings)
        return cls(SCHEMA_VERSION, gateway_snapshot_id, accounting, bindings,
                   identity, True, False, False)

    def apply_fill(self, *, gateway: PaperGatewaySnapshotV1,
                   paper_event: PaperOrderEventV1,
                   fill: ExecutionFillV2,
                   economics: FillEconomicsV2) -> "PaperPerformanceLedgerV1":
        gateway = PaperGatewaySnapshotV1.resume(gateway)
        if paper_event.kind is not PaperEventKind.FILL:
            raise PaperPerformanceError("only paper fill events can enter accounting")
        record = next((item for item in gateway.records
                       if item.paper_order_id == paper_event.paper_order_id), None)
        if record is None:
            raise PaperPerformanceError("paper order is absent from gateway checkpoint")
        retained = dict(record.event_fingerprints).get(paper_event.event_id)
        if retained != paper_event.fingerprint:
            raise PaperPerformanceError("paper fill event is absent or conflicts")
        if (fill.order_id, fill.market, fill.quantity, fill.fill_time) != (
                record.order_id, record.market, paper_event.fill_quantity,
                paper_event.occurred_at):
            raise PaperPerformanceError("gateway and execution fill evidence disagree")
        if (fill.market, fill.instrument_id, fill.contract_id) != (
                self.accounting.market, self.accounting.instrument_id,
                self.accounting.contract_id):
            raise PaperPerformanceError("execution fill and accounting identity disagree")
        if economics.fill_id != fill.fill_id:
            raise PaperPerformanceError("fill economics reference a different fill")
        existing = next((item for item in self.fill_bindings
                         if item.paper_event_id == paper_event.event_id), None)
        accounting_event_id = canonical_fingerprint("paper-accounting-fill-event-v1",
            gateway.snapshot_id, paper_event.fingerprint, fill.fill_id,
            economics.economics_id)
        binding_core = (record.paper_order_id, paper_event.event_id,
            paper_event.fingerprint, fill.fill_id, accounting_event_id,
            str(fill.quantity), str(fill.economic_price), str(economics.total))
        binding = PaperFillBindingV1(*binding_core,
            canonical_fingerprint("paper-fill-binding-v1", *binding_core))
        if existing is not None:
            if existing != binding:
                raise PaperPerformanceError("paper fill replay conflicts")
            return self
        accounted_quantity = sum((fill.quantity for fill in (
            event.fill for event in self.accounting.events
            if event.kind is AccountingEventKind.FILL and event.fill is not None
            and event.fill.order_id == record.order_id)), start=fill.quantity)
        if accounted_quantity != record.filled_quantity:
            raise PaperPerformanceError("gateway filled quantity and accounting evidence disagree")
        event = AccountingEventV2("accounting-event-v2-1", accounting_event_id,
            AccountingEventKind.FILL, fill.fill_time, fill.fill_time,
            fill=fill, fill_economics=economics)
        updated = self.accounting.apply(event)
        return self._build(gateway.snapshot_id, updated,
                           self.fill_bindings + (binding,))

    def apply_mark(self, evidence: PriceEvidenceV2) -> "PaperPerformanceLedgerV1":
        if (evidence.market, evidence.instrument_id, evidence.contract_id) != (
                self.accounting.market, self.accounting.instrument_id,
                self.accounting.contract_id):
            raise PaperPerformanceError("mark and accounting identity disagree")
        event_id = canonical_fingerprint("paper-accounting-mark-event-v1",
                                         evidence.price_event_id)
        event = AccountingEventV2("accounting-event-v2-1", event_id,
            AccountingEventKind.MARK, evidence.observed_at,
            evidence.available_at, price=evidence)
        updated = self.accounting.apply(event)
        if updated is self.accounting:
            return self
        return self._build(self.gateway_snapshot_id, updated, self.fill_bindings)

    def reconcile_gateway(self, gateway: PaperGatewaySnapshotV1) -> "PaperPerformanceLedgerV1":
        gateway = PaperGatewaySnapshotV1.resume(gateway)
        records = {item.paper_order_id: item for item in gateway.records}
        for binding in self.fill_bindings:
            record = records.get(binding.paper_order_id)
            if record is None or dict(record.event_fingerprints).get(binding.paper_event_id) != binding.paper_event_fingerprint:
                raise PaperPerformanceError("accounted fill is not retained by gateway")
        totals: dict[str, object] = {}
        for event in self.accounting.events:
            if event.kind is AccountingEventKind.FILL and event.fill is not None:
                totals[event.fill.order_id] = totals.get(event.fill.order_id, 0) + event.fill.quantity
        for record in gateway.records:
            if totals.get(record.order_id, 0) != record.filled_quantity:
                raise PaperPerformanceError("gateway and accounting filled quantities do not reconcile")
        if gateway.snapshot_id == self.gateway_snapshot_id:
            return self
        return self._build(gateway.snapshot_id, self.accounting, self.fill_bindings)

    @property
    def snapshot(self):
        return self.accounting.snapshot
