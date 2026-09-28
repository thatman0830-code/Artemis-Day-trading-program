"""Deterministic, isolated operational drills for supervised paper execution.

These drills exercise repository-owned paper controls only.  They neither
operate recorders nor claim that a simulated interruption is a physical outage.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from backtesting.execution_accounting_v2.contracts import (
    OrderIntentV2, OrderSide, OrderType, TimeInForce,
)
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1, PaperAdapterReason, PaperExchangeAdapterV1
from execution.paper_gateway_v2 import PaperGatewayPolicyV1, PaperGatewaySnapshotV1, PaperSubmissionV1
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1, SupervisedPaperPolicyV1, SupervisedPaperState,
    SupervisedPaperWorkflowV1,
)
from monitoring.off_host_alert_delivery import deliver_alerts, verify_delivery


DRILL_VERSION = "supervised-paper-operational-drills-v1"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class OperationalDrillObservationV1:
    name: str
    passed: bool
    reason: str
    evidence_id: str
    simulated: bool = True
    trading_authority: bool = False


@dataclass(frozen=True, slots=True)
class OperationalDrillReportV1:
    schema_version: str
    observed_at: datetime
    observations: tuple[OperationalDrillObservationV1, ...]
    report_id: str
    physical_outage_claimed: bool = False
    recorder_operation_claimed: bool = False
    trading_authority: bool = False


def _initial() -> PaperExchangeAdapterV1:
    policy = PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), 2, timedelta(seconds=5))
    return PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(policy))


def _command(adapter: PaperExchangeAdapterV1, now: datetime, label: str = "primary") -> PaperAdapterCommandV1:
    sha = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    intent = OrderIntentV2(
        "order-intent-v2-1", sha("order:" + label), sha("run"), sha("action:" + label),
        "BTC", "BTC-PERP", None, OrderSide.BUY, Decimal("1"), OrderType.MARKET,
        TimeInForce.IOC, None, None, now, now, None, None, None, "config-v1", "policy-v1",
    )
    submission = PaperSubmissionV1(sha("key:" + label), intent, Decimal("100"), now, now,
                                   sha("authorization:" + label), True)
    return PaperAdapterCommandV1(sha("command:" + label), adapter.gateway.snapshot_id,
                                 submission=submission)


def _workflow(path: Path, policy: SupervisedPaperPolicyV1, session_digit: str) -> SupervisedPaperWorkflowV1:
    path.mkdir()
    return SupervisedPaperWorkflowV1(path, policy, _initial(), session_digit * 32)


def _observation(name: str, passed: bool, reason: str, evidence: object) -> OperationalDrillObservationV1:
    return OperationalDrillObservationV1(name, passed, reason,
        _digest({"name": name, "passed": passed, "reason": reason, "evidence": evidence}))


def run_supervised_operational_drills(root: Path, *, observed_at: datetime) -> OperationalDrillReportV1:
    """Run isolated simulations and return immutable, content-addressed evidence."""
    root = Path(root)
    if root.exists() or root.is_symlink():
        raise ValueError("drill root must be a new path")
    if observed_at.tzinfo is None or observed_at.utcoffset() != timedelta(0):
        raise ValueError("observed_at must be UTC")
    root.mkdir(parents=True)
    policy = SupervisedPaperPolicyV1(timedelta(seconds=5))
    observations: list[OperationalDrillObservationV1] = []

    durable = _workflow(root / "durable-command", policy, "1")
    with durable:
        before = durable.store.load(); command = _command(before, observed_at)
        after, receipt, health = durable.cycle(SupervisedPaperCycleV1(observed_at, observed_at, command))
        passed = bool(receipt and receipt.accepted and durable.store.load() == after and
                      health.state is SupervisedPaperState.HEALTHY)
        observations.append(_observation("durable-command", passed, "command checkpointed before success returned",
                                         [after.adapter_id, receipt.command_id if receipt else None]))

    restarted = SupervisedPaperWorkflowV1(durable.root, policy, _initial(), "2" * 32)
    restarted.acquire(); restart_state = restarted.start()
    try:
        record = restart_state.gateway.records[0]
        exact = ((record.paper_order_id, record.state, record.filled_quantity,
                  record.remaining_quantity, record.version),)
        waiting = restarted.cycle(SupervisedPaperCycleV1(observed_at, observed_at))[2]
        recovered = restarted.cycle(SupervisedPaperCycleV1(
            observed_at + timedelta(seconds=1), observed_at + timedelta(seconds=1),
            reconciliation_observation=exact))[0]
        passed = (waiting.state is SupervisedPaperState.RECONCILIATION_REQUIRED and
                  recovered.gateway.connected and not recovered.gateway.reconciliation_required)
        observations.append(_observation("simulated-power-loss-restart", passed,
            "restart disconnects and requires exact reconciliation", recovered.adapter_id))
    finally:
        restarted.release()

    exception_flow = _workflow(root / "process-exception", policy, "3")
    try:
        with exception_flow:
            raise RuntimeError("simulated process exception")
    except RuntimeError:
        pass
    observations.append(_observation("simulated-process-exception", not exception_flow.lock_path.exists(),
        "context exit releases single-owner lock", exception_flow.store.load().adapter_id))

    alert_sources: list[Path] = []
    for name, input_time, expected, digit in (
        ("stale-recorder-evidence", observed_at - timedelta(seconds=6), SupervisedPaperState.HALTED_STALE_INPUT, "4"),
        ("future-clock-evidence", observed_at + timedelta(microseconds=1), SupervisedPaperState.HALTED_FUTURE_INPUT, "5"),
    ):
        flow = _workflow(root / name, policy, digit)
        with flow:
            state, _, health = flow.cycle(SupervisedPaperCycleV1(observed_at, input_time))
            passed = (health.state is expected and state.gateway.kill_switch_active and
                      not state.gateway.connected and flow.store.load() == state)
            observations.append(_observation(name, passed,
                "bad timing evidence halts and disconnects without operating a recorder", state.adapter_id))
            alert_sources.append(flow.alerts_path)

    corrupt = _workflow(root / "corrupt-checkpoint", policy, "6")
    corrupt.acquire(); corrupt.start(); corrupt.release(); corrupt.store.path.write_bytes(b"corrupt")
    rejected = False
    try:
        with SupervisedPaperWorkflowV1(corrupt.root, policy, _initial(), "7" * 32):
            pass
    except Exception:
        rejected = True
    observations.append(_observation("checkpoint-corruption", rejected and not corrupt.lock_path.exists(),
        "corrupt checkpoint rejects restart and releases ownership", "rejected"))

    replay = _workflow(root / "idempotent-replay", policy, "8")
    with replay:
        state = replay.store.load(); command = _command(state, observed_at, "replay")
        first, first_receipt, _ = replay.cycle(SupervisedPaperCycleV1(observed_at, observed_at, command))
        second, second_receipt, _ = replay.cycle(SupervisedPaperCycleV1(observed_at, observed_at, command))
        passed = (first == second and len(second.gateway.records) == 1 and len(second.receipts) == 1 and
                  first_receipt is not None and first_receipt.accepted and second_receipt is not None and
                  second_receipt.reason is PaperAdapterReason.IDEMPOTENT_REPLAY)
        observations.append(_observation("duplicate-command-replay", passed,
            "exact retry creates no duplicate exposure", second.adapter_id))

        conflict_submission = replace(command.submission, authorized=False)
        conflict = replace(command, submission=conflict_submission)
        unchanged, conflict_receipt, _ = replay.cycle(SupervisedPaperCycleV1(observed_at, observed_at, conflict))
        passed = (unchanged == second and conflict_receipt is not None and
                  conflict_receipt.reason is PaperAdapterReason.COMMAND_CONFLICT)
        observations.append(_observation("conflicting-command-reuse", passed,
            "same command identity with different content rejects", unchanged.adapter_id))

    mismatch = _workflow(root / "reconciliation-mismatch", policy, "9")
    mismatch.acquire(); state = mismatch.start()
    state, _, _ = mismatch.cycle(SupervisedPaperCycleV1(observed_at, observed_at, _command(state, observed_at, "mismatch")))
    mismatch.release()
    mismatch2 = SupervisedPaperWorkflowV1(mismatch.root, policy, _initial(), "a" * 32)
    mismatch2.acquire(); mismatch2.start()
    try:
        failed, _, health = mismatch2.cycle(SupervisedPaperCycleV1(observed_at, observed_at,
                                                                   reconciliation_observation=()))
        passed = (health.state is SupervisedPaperState.RECONCILIATION_REQUIRED and
                  failed.gateway.kill_switch_active and not failed.gateway.connected)
        observations.append(_observation("reconciliation-mismatch", passed,
            "mismatch remains disconnected with kill switch active", failed.adapter_id))
    finally:
        mismatch2.release()

    stopped = _workflow(root / "controlled-stop", policy, "b")
    with stopped:
        stopped.stop_path.write_text(json.dumps({"session_id": "b" * 32, "stop": True,
                                                 "trading_authority": False}), encoding="utf-8")
        state, _, health = stopped.cycle(SupervisedPaperCycleV1(observed_at, observed_at))
        passed = health.state is SupervisedPaperState.STOPPED and not state.gateway.connected
        observations.append(_observation("controlled-stop", passed,
            "identity-bound stop disconnects and emits alert", state.adapter_id))

    sink = root / "local-cloud-sync-fixture"; (sink / "inbox").mkdir(parents=True)
    (sink / "acknowledgements").mkdir()
    manifest = {"schema_version": "owner-alert-sink-v1", "sink_id": "paper-drill-sink",
                "transport": "CLOUD_SYNC", "off_host_attested": True, "trading_authority": False}
    (sink / "sink-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    receipts = root / "delivery-receipts"
    delivered = deliver_alerts(alerts_path=alert_sources[0], sink=sink, local_receipts=receipts,
                               delivered_at=observed_at)
    verified = verify_delivery(alerts_path=alert_sources[0], sink=sink, local_receipts=receipts)
    observations.append(_observation("local-cloud-sync-alert-handoff", len(delivered) == verified == 1,
        "local fixture verifies delivery format only; physical off-host delivery is not claimed",
        [item["receipt_id"] for item in delivered]))

    core = {"schema_version": DRILL_VERSION, "observed_at": observed_at.isoformat(),
            "observations": [{field: getattr(item, field) for field in item.__dataclass_fields__}
                             for item in observations],
            "physical_outage_claimed": False, "recorder_operation_claimed": False,
            "trading_authority": False}
    return OperationalDrillReportV1(DRILL_VERSION, observed_at, tuple(observations), _digest(core),
                                    False, False, False)
