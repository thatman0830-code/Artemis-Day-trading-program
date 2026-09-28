"""Fail-closed persistence bridge for supervised paper performance.

This coordinator has no execution transport and creates no market evidence. It
binds the already-durable paper adapter checkpoint to the already-durable
performance checkpoint after every supervised cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backtesting.execution_accounting_v2.accounting import (
    FillEconomicsV2, InstrumentAccountingLedgerV2, PriceEvidenceV2,
)
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from execution.paper_gateway_v2 import PaperEventKind, PaperOrderEventV1
from execution.paper_performance_checkpoint_v1 import (
    PaperPerformanceCheckpointStoreV1,
)
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1, SupervisedPaperState, SupervisedPaperWorkflowV1,
)


class SupervisedPaperPerformanceError(RuntimeError):
    """The adapter/accounting persistence boundary could not be verified."""


class PaperPerformanceHaltUnconfirmedError(SupervisedPaperPerformanceError):
    """The failure response could not be fully persisted; owner action is required."""


@dataclass(frozen=True, slots=True)
class VerifiedPaperFillV1:
    paper_event: PaperOrderEventV1
    fill: ExecutionFillV2
    economics: FillEconomicsV2

    def __post_init__(self) -> None:
        if self.paper_event.kind is not PaperEventKind.FILL:
            raise ValueError("verified paper fill requires a fill event")


class SupervisedPaperPerformanceV1:
    """Coordinates adapter and accounting checkpoints without trading authority."""

    def __init__(self, workflow: SupervisedPaperWorkflowV1,
                 initial_accounting: InstrumentAccountingLedgerV2):
        self.workflow = workflow
        self.initial_accounting = initial_accounting
        self._failed = False
        self.store = PaperPerformanceCheckpointStoreV1(
            Path(workflow.root) / "performance-checkpoint.json")

    def start(self) -> tuple[object, PaperPerformanceLedgerV1]:
        """Start both stores and prove that their retained fill state agrees."""
        self._assert_not_failed()
        try:
            adapter = self.workflow.start()
            if self.store.path.exists():
                ledger = self.store.load()
                updated = ledger.reconcile_gateway(adapter.gateway)
                self._save_if_changed(ledger, updated)
                ledger = updated
            else:
                ledger = PaperPerformanceLedgerV1.create(
                    self.initial_accounting, adapter.gateway)
                ledger = ledger.reconcile_gateway(adapter.gateway)
                self.store.initialize(ledger)
            return adapter, ledger
        except Exception as exc:
            self._failed = True
            self._halt()
            raise SupervisedPaperPerformanceError(
                "paper performance startup reconciliation failed") from exc

    def cycle(self, cycle: SupervisedPaperCycleV1, *,
              verified_fill: VerifiedPaperFillV1 | None = None,
              closed_mark: PriceEvidenceV2 | None = None):
        """Persist verified fill/mark evidence and reconcile every cycle.

        Files are individually atomic, not a two-file transaction.
        The adapter command is persisted first. Any missing, conflicting, stale,
        or unwritable accounting evidence then durably halts the adapter.
        """
        self._assert_not_failed()
        try:
            if closed_mark is not None and (
                    closed_mark.observed_at > cycle.now or
                    closed_mark.available_at > cycle.now):
                raise SupervisedPaperPerformanceError("future or unavailable mark evidence")
            before = self.store.load()
            adapter, receipt, health = self.workflow.cycle(cycle)
            ledger = before
            command_event = None
            if cycle.command is not None:
                if cycle.command.event is not None:
                    command_event = cycle.command.event
                elif cycle.command.contingent_resolution is not None:
                    command_event = cycle.command.contingent_resolution.fill
            accepted_fill = (receipt is not None and receipt.accepted and
                             command_event is not None and
                             command_event.kind is PaperEventKind.FILL)
            if accepted_fill != (verified_fill is not None):
                raise SupervisedPaperPerformanceError(
                    "accepted paper fill and verified accounting evidence must correspond")
            if verified_fill is not None:
                if verified_fill.paper_event != command_event:
                    raise SupervisedPaperPerformanceError(
                        "verified fill references a different paper event")
                ledger = ledger.apply_fill(gateway=adapter.gateway,
                    paper_event=verified_fill.paper_event,
                    fill=verified_fill.fill, economics=verified_fill.economics)
            if closed_mark is not None:
                if health.state is not SupervisedPaperState.HEALTHY:
                    raise SupervisedPaperPerformanceError(
                        "mark evidence cannot be accepted while workflow is unhealthy")
                ledger = ledger.apply_mark(closed_mark)
            ledger = ledger.reconcile_gateway(adapter.gateway)
            self._save_if_changed(before, ledger)
            return adapter, receipt, health, ledger
        except Exception as exc:
            self._failed = True
            self._halt(cycle)
            if isinstance(exc, SupervisedPaperPerformanceError):
                raise
            raise SupervisedPaperPerformanceError(
                "paper performance cycle failed closed") from exc

    def _save_if_changed(self, before, after) -> None:
        if after.ledger_id != before.ledger_id:
            self.store.save(after, expected_ledger_id=before.ledger_id)

    def _assert_not_failed(self) -> None:
        if self._failed:
            raise SupervisedPaperPerformanceError(
                "coordinator is latched after failure; fresh startup reconciliation required")

    def _halt(self, cycle: SupervisedPaperCycleV1 | None = None) -> None:
        try:
            if cycle is None:
                self.workflow.store.halt()
            else:
                self.workflow.halt_performance_persistence(cycle)
        except Exception as exc:
            raise PaperPerformanceHaltUnconfirmedError(
                "halt/health/alert persistence unconfirmed; owner intervention required") from exc
