"""Bounded caller-supplied runtime loop for supervised BTC paper execution.

The loop acquires no provider data and creates no strategy decisions or fills.
Each cycle must carry an immutable snapshot reference and, when submitting an
entry, the independently produced strategy receipt bound to those exact bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_file_valuation_v1 import PaperFileValuationV1, PaperSnapshotReferenceV1
from execution.strategy_paper_intent_v1 import StrategyPaperIntentV1
from execution.btc_perpetual_strategy_intent_v1 import BTCPerpetualStrategyIntentV1
from execution.btc_perpetual_paper_gateway_bridge_v1 import prepare_btc_perpetual_paper_command
from execution.strategy_paper_pretrade_v1 import PaperPretradePlanV1
from execution.supervised_paper_performance_v1 import VerifiedPaperFillV1


VERSION = "supervised-btc-paper-runtime-v2"
MAXIMUM_POLL_INTERVAL = timedelta(seconds=4)
MAXIMUM_CYCLES = 75


class SupervisedPaperRuntimeError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SupervisedPaperRuntimeInputV1:
    reference: PaperSnapshotReferenceV1
    command: PaperAdapterCommandV1 | None = None
    strategy_intent: StrategyPaperIntentV1 | BTCPerpetualStrategyIntentV1 | None = None
    verified_fill: VerifiedPaperFillV1 | None = None
    trading_authority: bool = False

    def __post_init__(self):
        if not isinstance(self.reference, PaperSnapshotReferenceV1):
            raise SupervisedPaperRuntimeError("typed snapshot reference required")
        if self.command is not None and not isinstance(self.command, PaperAdapterCommandV1):
            raise SupervisedPaperRuntimeError("typed paper command required")
        if self.strategy_intent is not None and type(self.strategy_intent) not in (
                StrategyPaperIntentV1,BTCPerpetualStrategyIntentV1):
            raise SupervisedPaperRuntimeError("typed strategy receipt required")
        if self.verified_fill is not None and not isinstance(self.verified_fill, VerifiedPaperFillV1):
            raise SupervisedPaperRuntimeError("typed verified fill required")
        if self.trading_authority is not False:
            raise SupervisedPaperRuntimeError("runtime input cannot grant trading authority")
        submission = None if self.command is None else self.command.submission
        if submission is not None:
            if (self.strategy_intent is None or self.strategy_intent.intent != submission.intent
                    or self.strategy_intent.source_sha256 != self.reference.sha256):
                raise SupervisedPaperRuntimeError("entry command is not bound to snapshot strategy evidence")
        elif self.strategy_intent is not None:
            raise SupervisedPaperRuntimeError("orphan strategy receipt")
        if self.verified_fill is not None:
            event = None if self.command is None else self.command.event
            if event is None or event != self.verified_fill.paper_event:
                raise SupervisedPaperRuntimeError("verified fill is not bound to the cycle event")


def prepare_btc_perpetual_runtime_input(*, plan: PaperPretradePlanV1, launch: dict,
        reference: PaperSnapshotReferenceV1, expected_gateway_snapshot_id: str,
        requested_at, market_data_at) -> SupervisedPaperRuntimeInputV1:
    """Bind a verified perpetual plan and launch permit to one immutable input snapshot."""
    if type(plan) is not PaperPretradePlanV1 or type(plan.strategy_intent) is not BTCPerpetualStrategyIntentV1:
        raise SupervisedPaperRuntimeError("typed BTC perpetual pretrade plan required")
    if not isinstance(reference,PaperSnapshotReferenceV1) or reference.sha256!=plan.strategy_intent.source_sha256:
        raise SupervisedPaperRuntimeError("perpetual plan is not bound to runtime snapshot")
    command=prepare_btc_perpetual_paper_command(plan=plan,launch=launch,
        expected_gateway_snapshot_id=expected_gateway_snapshot_id,
        requested_at=requested_at,market_data_at=market_data_at)
    return SupervisedPaperRuntimeInputV1(reference,command,plan.strategy_intent)


@dataclass(frozen=True, slots=True)
class SupervisedPaperRuntimeResultV1:
    session_id: str
    state: str
    cycles: int
    commands: int
    started_at: str
    stopped_at: str
    ledger_id: str
    runtime_id: str
    termination_reason: str
    trading_authority: bool = False

    def __post_init__(self):
        if (len(self.session_id) != 32
                or any(char not in "0123456789abcdef" for char in self.session_id)
                or type(self.cycles) is not int or not 0 <= self.cycles <= MAXIMUM_CYCLES
                or type(self.commands) is not int or not 0 <= self.commands <= 5
                or self.state != "STOPPED"
                or self.termination_reason not in {
                    "SUPERVISOR_STOP", "SESSION_DEADLINE", "CYCLE_LIMIT"}
                or self.trading_authority is not False):
            raise SupervisedPaperRuntimeError("runtime result fields are invalid")
        body = {"version": VERSION, "session_id": self.session_id, "state": self.state,
            "cycles": self.cycles, "commands": self.commands, "started_at": self.started_at,
            "stopped_at": self.stopped_at, "ledger_id": self.ledger_id,
            "termination_reason": self.termination_reason,
            "trading_authority": False}
        if self.runtime_id != hashlib.sha256(_canonical(body)).hexdigest():
            raise SupervisedPaperRuntimeError("runtime result identity mismatch")


def _result(session, *, cycles, started_at, stopped_at, termination_reason):
    stopped = session.stop(stopped_at)
    body = {"version": VERSION, "session_id": stopped.session_id, "state": stopped.state,
        "cycles": cycles, "commands": stopped.commands, "started_at": started_at.isoformat(),
        "stopped_at": stopped_at.isoformat(), "ledger_id": stopped.ledger_id,
        "termination_reason": termination_reason,
        "trading_authority": False}
    identity = hashlib.sha256(_canonical(body)).hexdigest()
    return SupervisedPaperRuntimeResultV1(stopped.session_id, stopped.state, cycles,
        stopped.commands, body["started_at"], body["stopped_at"], stopped.ledger_id,
        identity, termination_reason, False)


def write_runtime_result(path, result):
    if not isinstance(result, SupervisedPaperRuntimeResultV1) or result.trading_authority is not False:
        raise SupervisedPaperRuntimeError("typed non-authoritative result required")
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    document = {name: getattr(result, name) for name in result.__dataclass_fields__}
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary, "xb") as stream:
            stream.write(_canonical(document) + b"\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class SupervisedBTCPaperRuntimeV1:
    def __init__(self, valuation, *, poll_interval=timedelta(seconds=4)):
        if not isinstance(valuation, PaperFileValuationV1):
            raise SupervisedPaperRuntimeError("typed valuation integration required")
        if not timedelta(0) < poll_interval <= MAXIMUM_POLL_INTERVAL:
            raise SupervisedPaperRuntimeError("poll interval exceeds hard ceiling")
        self.valuation = valuation
        self.poll_interval = poll_interval
        self.used = False

    def run(self, *, input_reader, health_reader, waiter, utc_reader=None,
            monotonic_reader=None, output_path=None):
        if self.used:
            raise SupervisedPaperRuntimeError("runtime is single-use")
        if not all(callable(item) for item in (input_reader, health_reader, waiter)):
            raise SupervisedPaperRuntimeError("runtime dependencies must be callable")
        self.used = True; cycles = 0
        self.valuation.start(health_reader, utc_reader=utc_reader,
            monotonic_reader=monotonic_reader)
        session = self.valuation.clock.session
        started_at = self.valuation.clock.guard.last.utc
        try:
            while cycles < MAXIMUM_CYCLES:
                if session.workflow.stop_path.exists():
                    final = _result(session, cycles=cycles, started_at=started_at,
                        stopped_at=self.valuation.clock.guard.last.utc,
                        termination_reason="SUPERVISOR_STOP")
                    break
                current = input_reader()
                if not isinstance(current, SupervisedPaperRuntimeInputV1):
                    raise SupervisedPaperRuntimeError("input reader returned invalid cycle")
                # Canonical observation may be process-isolated and relatively
                # expensive.  It is never valid to enter valuation after that
                # work has carried the runtime across its bounded deadline.
                observed_now = utc_reader() if utc_reader is not None else datetime.now(timezone.utc)
                # Reserve one complete poll interval for the valuation health
                # read and controlled stop.  Starting valuation closer than
                # this can cross the hard deadline between the precheck and
                # the clock-guarded session step.
                if session.deadline - observed_now <= self.poll_interval:
                    final = _result(session, cycles=cycles, started_at=started_at,
                        stopped_at=observed_now, termination_reason="SESSION_DEADLINE")
                    break
                _, result = self.valuation.poll(current.reference, health_reader,
                    command=current.command, verified_fill=current.verified_fill,
                    utc_reader=utc_reader, monotonic_reader=monotonic_reader)
                cycles += 1
                now = self.valuation.clock.guard.last.utc
                health = result[2]
                if not session.active:
                    stopped = session.bridge.store.load()
                    body = {"version": VERSION, "session_id": session.workflow.session_id,
                        "state": health.state.value, "cycles": cycles, "commands": session.commands,
                        "started_at": started_at.isoformat(), "stopped_at": now.isoformat(),
                        "ledger_id": stopped.ledger_id,
                        "termination_reason": "SUPERVISOR_STOP",
                        "trading_authority": False}
                    runtime_id = hashlib.sha256(_canonical(body)).hexdigest()
                    final = SupervisedPaperRuntimeResultV1(session.workflow.session_id,
                        health.state.value, cycles, session.commands, body["started_at"],
                        body["stopped_at"], stopped.ledger_id, runtime_id,
                        body["termination_reason"], False)
                    break
                if session.deadline - now <= self.poll_interval:
                    final = _result(session, cycles=cycles, started_at=started_at,
                        stopped_at=now, termination_reason="SESSION_DEADLINE")
                    break
                waiter(self.poll_interval.total_seconds())
            else:
                now = self.valuation.clock.guard.last.utc
                final = _result(session, cycles=cycles, started_at=started_at,
                    stopped_at=now, termination_reason="CYCLE_LIMIT")
            if output_path is not None:
                write_runtime_result(output_path, final)
            return final
        except Exception:
            if session.active:
                try: session.stop(self.valuation.clock.guard.last.utc)
                except Exception as stop_error:
                    raise SupervisedPaperRuntimeError("runtime failed; stop unconfirmed") from stop_error
            raise
