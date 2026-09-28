"""Single-generation supervised paper rearm; contains no submission transport."""
from dataclasses import replace
from pathlib import Path
import json
import os

from backtesting.execution_accounting_v2.order_ledger import (
    LedgerEventKind, OrderLedgerEventV2, OrderLedgerV2,
)
from backtesting.execution_accounting_v2.ohlc_execution import (
    ExecutionInstructionV2, ExecutionSourceLineageV2,
)
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_oco_checkpoint_v1 import _unique
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.paper_oco_handoff_v1 import PaperOCOHandoffStoreV1, _review
from execution.paper_oco_initial_v1 import create_persisted_protective_session, open_persisted_protective_session, _unpack
from execution.supervised_paper_launch_evidence_v1 import (
    OwnerSupervisionConfirmationV1, evaluate_collected_launch_evidence, read_launch_evidence,
)
from execution.supervised_paper_launch_gate_v1 import SupervisedPaperLaunchPolicyV1


VERSION = "paper-oco-successor-v1"
MAX_BYTES = 1_000_000


def _event(ledger, intent, kind, handoff_id, at):
    snapshot = ledger.order(intent.order_id)
    event_id = canonical_fingerprint(VERSION, handoff_id, intent.order_id, kind.value, at)
    return OrderLedgerEventV2("order-ledger-event-v2-1", event_id, intent.order_id, kind,
        at, len(ledger.events)+1, snapshot.order_version, intent.market, intent.instrument_id,
        intent.contract_id, handoff_id, "SUPERVISED_PAPER_PROTECTIVE_REARM",
        contract_eligibility_verified=kind is LedgerEventKind.ACTIVATE)


def _active_ledger(stop, target, handoff_id, at):
    ledger = OrderLedgerV2.create((stop, target))
    for kind in (LedgerEventKind.SUBMIT, LedgerEventKind.ACCEPT, LedgerEventKind.ACTIVATE):
        events = sorted((_event(ledger, item, kind, handoff_id, at) for item in (stop, target)),
            key=lambda item: item.event_id)
        # Recreate after each application so sequence and order version remain exact.
        for template in events:
            event = replace(template, sequence_number=len(ledger.events)+1,
                expected_order_version=ledger.order(template.order_id).order_version)
            ledger = ledger.apply(event)
    return ledger


def _initial(predecessor, inputs, handoff_id):
    _, old = predecessor.load()
    ledger = _active_ledger(inputs["stop"], inputs["target"], handoff_id, inputs["reviewed_at"])
    previous = {item.order_id: item for item in old.instructions}
    instructions = []
    for candidate in (inputs["stop"], inputs["target"]):
        base = previous[candidate.replaces_order_id]
        activation = next(event for event in ledger.events
            if event.order_id == candidate.order_id and event.kind is LedgerEventKind.ACTIVATE)
        lineage = ExecutionSourceLineageV2.create(source_bar=inputs["source_bar"],
            action_id=candidate.action_id, order_id=candidate.order_id,
            activation_event_id=activation.event_id, activation_event_time=activation.event_time)
        instruction_id = canonical_fingerprint(VERSION, handoff_id, candidate.order_id,
            base.priority, base.participation_rate, base.slippage_ticks, base.assumption_version, lineage)
        instructions.append(ExecutionInstructionV2("execution-instruction-v2-1", instruction_id,
            candidate.order_id, base.priority, base.participation_rate, base.slippage_ticks,
            base.assumption_version, lineage))
    return dict(accounting=inputs["accounting"], ledger=ledger,
        stop_order_id=inputs["stop"].order_id, target_order_id=inputs["target"].order_id,
        policy=old.policy, instructions=tuple(instructions), armed_at=inputs["reviewed_at"])


class PaperOCOSuccessorV1:
    """Create and verify exactly one local successor from one prepared handoff."""

    def __init__(self, handoff):
        if type(handoff) is not PaperOCOHandoffStoreV1:
            raise PaperOCOError("typed prepared handoff required")
        self.handoff = handoff
        self.root = handoff.predecessor.journal.root
        self.path = self.root / "oco-successor-binding.json"

    def _successor(self, handoff_id):
        return self.root / ("oco-successor-" + handoff_id)

    def _read(self):
        self.handoff._safe()
        if self.path.is_symlink() or (self.path.exists() and not self.path.is_file()):
            raise PaperOCOError("unsafe successor binding")
        with self.path.open("rb") as stream:
            raw = stream.read(MAX_BYTES+1)
        if not raw or len(raw)>MAX_BYTES:
            raise PaperOCOError("successor binding size limit")
        try:
            doc=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(PaperOCOError("invalid numeric constant")))
            fields={"version","binding_id","handoff_id","launch_id","launch_evidence_id",
                "confirmation_id","successor_initial_id",
                "state","paper_only","live_trading_permitted","trading_authority"}
            if (type(doc) is not dict or set(doc)!=fields or doc["version"]!=VERSION
                    or doc["state"] not in ("IN_FLIGHT","COMMITTED")
                    or doc["paper_only"] is not True or doc["live_trading_permitted"] is not False
                    or doc["trading_authority"] is not False):
                raise PaperOCOError("invalid successor binding")
            return doc
        except (ValueError,TypeError,KeyError,RecursionError) as exc:
            raise PaperOCOError("invalid successor binding") from exc

    def load(self):
        doc=self._read()
        if doc["state"]!="COMMITTED":
            raise PaperOCOError("successor creation requires owner recovery")
        prepared=self.handoff.load()
        if prepared["handoff_id"]!=doc["handoff_id"]:
            raise PaperOCOError("successor handoff identity mismatch")
        runner=open_persisted_protective_session(self._successor(doc["handoff_id"]))
        if runner.journal.initial_id!=doc["successor_initial_id"]:
            raise PaperOCOError("successor initial identity mismatch")
        expected=canonical_fingerprint(VERSION,doc["handoff_id"],doc["launch_id"],
            doc["launch_evidence_id"],doc["confirmation_id"],doc["successor_initial_id"])
        if doc["binding_id"]!=expected:
            raise PaperOCOError("successor binding identity mismatch")
        return doc,runner

    def create(self, *, expected_handoff_id, evidence_path, confirmation, policy, activated_at):
        if (type(confirmation) is not OwnerSupervisionConfirmationV1
                or type(policy) is not SupervisedPaperLaunchPolicyV1):
            raise PaperOCOError("typed supervision confirmation and policy required")
        try:
            rebuilt=OwnerSupervisionConfirmationV1.create(confirmed_at=confirmation.confirmed_at,
                expires_at=confirmation.expires_at,repository_checkpoint=confirmation.repository_checkpoint,
                owner_supervision_confirmed=confirmation.owner_supervision_confirmed,
                stop_control_verified=confirmation.stop_control_verified,
                maximum_session_seconds=confirmation.maximum_session_seconds,
                maximum_commands=confirmation.maximum_commands,
                maximum_order_notional=confirmation.maximum_order_notional,
                maximum_gross_exposure=confirmation.maximum_gross_exposure)
            if rebuilt!=confirmation:
                raise PaperOCOError("owner confirmation identity mismatch")
            evidence=read_launch_evidence(Path(evidence_path))
            launch=evaluate_collected_launch_evidence(evidence=evidence,
                confirmation=confirmation,policy=policy,as_of=activated_at)
        except (ValueError,OSError) as exc:
            if isinstance(exc,PaperOCOError): raise
            raise PaperOCOError("supervised launch evidence invalid") from exc
        if (not launch.eligible or launch.reasons or launch.expires_at is None
                or launch.advisory_only is not True or launch.live_trading_permitted is not False
                or launch.trading_authority is not False or launch.permitted_markets!=("BTC",)
                or not launch.evaluated_at<=activated_at<launch.expires_at):
            raise PaperOCOError("current eligible supervised paper decision required")
        journal=self.handoff.predecessor.journal
        journal._acquire()
        try:
            prepared=self.handoff.load()
            if prepared["handoff_id"]!=expected_handoff_id:
                raise PaperOCOError("stale prepared handoff")
            inputs={key:_unpack(value) for key,value in prepared["inputs"].items()}
            assessment=_review(self.handoff.predecessor,inputs)
            if (assessment["uncovered_tail"] is not False or activated_at!=inputs["reviewed_at"]
                    or launch.evaluated_at!=activated_at):
                raise PaperOCOError("handoff and launch must be gap-free and contemporaneous")
            notional=max(inputs["stop"].quantity*inputs["stop"].stop_price,
                inputs["target"].quantity*inputs["target"].limit_price)
            gross=inputs["accounting"].snapshot.position.signed_quantity*inputs["source_bar"].close
            if notional>launch.maximum_order_notional or gross>launch.maximum_gross_exposure:
                raise PaperOCOError("successor exceeds supervised risk limits")
            initial=_initial(self.handoff.predecessor,inputs,prepared["handoff_id"])
            initial_id=canonical_fingerprint(initial)
            identity=canonical_fingerprint(VERSION,prepared["handoff_id"],launch.launch_id,
                evidence.evidence_id,confirmation.confirmation_id,initial_id)
            if self.path.exists():
                existing=self._read()
                if existing["state"]!="COMMITTED" or existing["binding_id"]!=identity:
                    raise PaperOCOError("successor binding is incomplete or conflicting")
                return self.load()
            successor=self._successor(prepared["handoff_id"])
            if successor.exists():
                raise PaperOCOError("unbound successor directory requires owner review")
            core=dict(version=VERSION,binding_id=identity,handoff_id=prepared["handoff_id"],
                launch_id=launch.launch_id,launch_evidence_id=evidence.evidence_id,
                confirmation_id=confirmation.confirmation_id,successor_initial_id=initial_id,state="IN_FLIGHT",
                paper_only=True,live_trading_permitted=False,trading_authority=False)
            self._write(core)
            successor.mkdir()
            create_persisted_protective_session(successor,initial=initial)
            self._write({**core,"state":"COMMITTED"})
            return self.load()
        finally:
            journal.lock.unlink()

    def _write(self,doc):
        raw=json.dumps(doc,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        temporary=self.root/".oco-successor-binding.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:
            temporary.unlink(missing_ok=True)
