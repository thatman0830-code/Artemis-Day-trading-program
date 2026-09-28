"""Prepared-only paper reservation checkpoint. Never submits or releases funds."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from execution.paper_exchange_adapter_checkpoint_v1 import PaperAdapterCheckpointStoreV1
from execution.paper_performance_checkpoint_v1 import PaperPerformanceCheckpointStoreV1
from execution.strategy_paper_pretrade_v1 import plan_strategy_paper_pretrade

VERSION = "paper-prepared-reservation-v1"
MAX_BYTES = 16_384
FIELDS = {"plan_id","strategy_order_id","order_id","performance_ledger_id","gateway_snapshot_id",
          "quantity","reserved_cash","planned_loss","prepared_at","expires_at"}
COMMITMENT_FIELDS={"command_id","command_fingerprint","paper_order_id","after_gateway_snapshot_id","committed_at"}


class PaperReservationError(ValueError):
    pass


@dataclass(frozen=True,slots=True)
class PaperReservationReconciliationV1:
    state:str
    checkpoint_id:str
    order_present:bool
    recovery_applied:bool
    trading_authority:bool=False

    def __post_init__(self):
        if (self.state not in ("EMPTY","PREPARED_NO_ORDER","COMMITTED")
                or not re.fullmatch("[0-9a-f]{64}",self.checkpoint_id)
                or type(self.order_present)is not bool or type(self.recovery_applied)is not bool
                or self.trading_authority is not False):
            raise PaperReservationError("reservation reconciliation result invalid")


def _bytes(value):
    return json.dumps(value,sort_keys=True,separators=(",", ":"),allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key,value in pairs:
        if key in result: raise PaperReservationError("duplicate reservation field")
        result[key]=value
    return result


def _validate(body, session_id):
    if (type(body) is not dict or set(body)!={"version","session_id","state","reservation","submission_authorized","trading_authority"}
            or body["version"]!=VERSION or body["session_id"]!=session_id
            or body["submission_authorized"] is not False or body["trading_authority"] is not False):
        raise PaperReservationError("reservation schema/session/authority mismatch")
    record=body["reservation"]
    if body["state"]=="EMPTY" and record is None: return
    expected=FIELDS if body["state"]=="PREPARED" else FIELDS|COMMITMENT_FIELDS if body["state"]=="COMMITTED" else set()
    if type(record) is not dict or set(record)!=expected:
        raise PaperReservationError("invalid reservation state or fields")
    for name,value in record.items():
        if type(value) is not str or not 0<len(value)<=256:
            raise PaperReservationError("reservation fields must be bounded strings")
        if name.endswith("_id") and name!="strategy_order_id" and not re.fullmatch("[0-9a-f]{64}",value):
            raise PaperReservationError("invalid reservation identity")
    if body["state"]=="COMMITTED" and not re.fullmatch("[0-9a-f]{64}",record["command_fingerprint"]):
        raise PaperReservationError("invalid reservation identity")
    for name in ("quantity","reserved_cash","planned_loss"):
        try: value=Decimal(record[name])
        except InvalidOperation as exc: raise PaperReservationError("invalid reservation economics") from exc
        if not value.is_finite() or value<=0: raise PaperReservationError("invalid reservation economics")
    try:
        date_names=("prepared_at","expires_at")+(("committed_at",)if body["state"]=="COMMITTED"else())
        dates=[datetime.fromisoformat(record[name]) for name in date_names]
        if any(t.tzinfo is None or t.utcoffset()!=timedelta(0) for t in dates) or not dates[0]<dates[1]<=dates[0]+timedelta(minutes=5):
            raise ValueError("chronology")
        if body["state"]=="COMMITTED" and not dates[0]<=dates[2]<=dates[1]:raise ValueError("chronology")
    except ValueError as exc: raise PaperReservationError("invalid reservation chronology") from exc


class PaperReservationCheckpointV1:
    def __init__(self, root, session_id):
        if type(session_id) is not str or not re.fullmatch("[0-9a-f]{32}",session_id):
            raise PaperReservationError("explicit session UUID hex required")
        self.root=Path(root); self.session_id=session_id
        self.path=self.root/"prepared-reservation.json"
        self.lock_path=self.root/"prepared-reservation.lock"

    def _safe(self):
        if not self.root.is_dir(): raise PaperReservationError("existing session root required")
        for path in (self.path,self.lock_path,self.root,*self.root.parents):
            if path.exists() or path.is_symlink():
                info=path.lstat()
                if path.is_symlink() or getattr(info,"st_file_attributes",0)&0x400:
                    raise PaperReservationError("linked/reparse reservation path rejected")

    def _acquire(self):
        self._safe()
        try: fd=os.open(self.lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc: raise PaperReservationError("reservation writer lock exists") from exc
        os.close(fd)

    def load(self):
        self._safe()
        try:
            with self.path.open("rb") as stream: raw=stream.read(MAX_BYTES+1)
            if not 0<len(raw)<=MAX_BYTES: raise PaperReservationError("reservation size invalid")
            doc=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique)
            if type(doc) is not dict or set(doc)!={"checkpoint_id","body"}:
                raise PaperReservationError("reservation envelope invalid")
            _validate(doc["body"],self.session_id)
            if _hash(doc["body"])!=doc["checkpoint_id"]:
                raise PaperReservationError("reservation checksum mismatch")
            return doc
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise PaperReservationError("reservation missing or unreadable; no automatic reset") from exc

    def _write(self, body):
        _validate(body,self.session_id)
        doc={"checkpoint_id":_hash(body),"body":body}
        raw=_bytes(doc)+b"\n"
        if len(raw)>MAX_BYTES: raise PaperReservationError("reservation size invalid")
        temporary=self.root/(".reservation-"+uuid.uuid4().hex+".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return doc

    def initialize(self):
        self._acquire()
        try:
            if self.path.exists(): raise PaperReservationError("reservation already exists")
            return self._write(dict(version=VERSION,session_id=self.session_id,state="EMPTY",
                reservation=None,submission_authorized=False,trading_authority=False))
        finally: self.lock_path.unlink(missing_ok=True)

    def prepare(self, *, pretrade_inputs, expected_checkpoint_id):
        self._acquire()
        try:
            current=self.load()
            if current["checkpoint_id"]!=expected_checkpoint_id:
                raise PaperReservationError("reservation compare-and-swap conflict")
            adapter_store=PaperAdapterCheckpointStoreV1(self.root/"adapter-checkpoint.json")
            performance_store=PaperPerformanceCheckpointStoreV1(self.root/"performance-checkpoint.json")
            adapter=adapter_store.load(); performance=performance_store.load()
            args=dict(pretrade_inputs)
            if args["gateway"]!=adapter.gateway or args["performance"]!=performance:
                raise PaperReservationError("caller plan inputs differ from durable checkpoints")
            plan=plan_strategy_paper_pretrade(**{**args,"gateway":adapter.gateway,"performance":performance})
            if not plan.risk_eligible: raise PaperReservationError("pretrade risk rejected")
            intent=plan.strategy_intent
            record=dict(plan_id=plan.plan_id,strategy_order_id=intent.strategy_order_id,
                order_id=intent.intent.order_id,performance_ledger_id=performance.ledger_id,
                gateway_snapshot_id=adapter.gateway.snapshot_id,quantity=str(plan.quantity),
                reserved_cash=str(plan.reserved_cash),planned_loss=str(plan.planned_stop_loss_with_allowances),
                prepared_at=intent.intent.submitted_at.isoformat(),expires_at=intent.intent.expires_at.isoformat())
            if current["body"]["reservation"] is not None:
                if current["body"]["reservation"]==record: return current
                raise PaperReservationError("existing reservation conflict; no automatic release or replacement")
            if adapter_store.load()!=adapter or performance_store.load()!=performance:
                raise PaperReservationError("source checkpoints changed during preparation")
            return self._write({**current["body"],"state":"PREPARED","reservation":record})
        finally: self.lock_path.unlink(missing_ok=True)

    def commit(self, *, expected_checkpoint_id):
        """Bind a prepared reservation to its already-durable accepted order."""
        self._acquire()
        try:
            current=self.load()
            if current["checkpoint_id"]!=expected_checkpoint_id:
                raise PaperReservationError("reservation compare-and-swap conflict")
            if current["body"]["state"]=="COMMITTED":return current
            if current["body"]["state"]!="PREPARED":
                raise PaperReservationError("prepared reservation required")
            record=current["body"]["reservation"]
            adapter=PaperAdapterCheckpointStoreV1(self.root/"adapter-checkpoint.json").load()
            matches=[]
            for receipt in adapter.receipts:
                paper_order_id=getattr(receipt,"paper_order_id",None)
                if not receipt.accepted or paper_order_id is None:continue
                order=next((item for item in adapter.gateway.records
                    if item.paper_order_id==paper_order_id),None)
                if order is not None and order.order_id==record["order_id"]:matches.append((receipt,order))
            if len(matches)!=1:raise PaperReservationError("unique durable accepted order required")
            receipt,order=matches[0]
            if (receipt.before_snapshot_id!=record["gateway_snapshot_id"]
                    or receipt.paper_order_id!=order.paper_order_id):
                raise PaperReservationError("accepted order conflicts with reservation")
            committed={**record,"command_id":receipt.command_id,
                "command_fingerprint":receipt.command_fingerprint,"paper_order_id":order.paper_order_id,
                "after_gateway_snapshot_id":receipt.after_snapshot_id,
                "committed_at":order.accepted_at.isoformat()}
            return self._write({**current["body"],"state":"COMMITTED","reservation":committed})
        finally:self.lock_path.unlink(missing_ok=True)

    def reconcile(self):
        """Classify or recover reservation state exclusively from durable facts."""
        current=self.load();body=current["body"]
        adapter=PaperAdapterCheckpointStoreV1(self.root/"adapter-checkpoint.json").load()
        performance=PaperPerformanceCheckpointStoreV1(self.root/"performance-checkpoint.json").load()
        if performance.reconcile_gateway(adapter.gateway)!=performance:
            raise PaperReservationError("durable performance and gateway differ")
        if body["state"]=="EMPTY":
            if adapter.gateway.records or adapter.receipts:
                raise PaperReservationError("empty reservation conflicts with durable gateway activity")
            return PaperReservationReconciliationV1("EMPTY",current["checkpoint_id"],False,False,False)
        record=body["reservation"]
        candidates=[]
        for receipt in adapter.receipts:
            paper_order_id=getattr(receipt,"paper_order_id",None)
            if not receipt.accepted or paper_order_id is None:continue
            order=next((item for item in adapter.gateway.records if item.paper_order_id==paper_order_id),None)
            if order is not None and order.order_id==record["order_id"]:candidates.append((receipt,order))
        if body["state"]=="PREPARED":
            if not candidates:
                if (adapter.gateway.snapshot_id!=record["gateway_snapshot_id"]
                        or adapter.gateway.records or adapter.receipts):
                    raise PaperReservationError("prepared reservation conflicts with durable gateway activity")
                return PaperReservationReconciliationV1("PREPARED_NO_ORDER",current["checkpoint_id"],False,False,False)
            if len(candidates)!=1:raise PaperReservationError("ambiguous durable accepted order")
            committed=self.commit(expected_checkpoint_id=current["checkpoint_id"])
            return PaperReservationReconciliationV1("COMMITTED",committed["checkpoint_id"],True,True,False)
        if len(candidates)!=1:raise PaperReservationError("committed reservation lacks unique durable order")
        receipt,order=candidates[0]
        expected={"command_id":receipt.command_id,"command_fingerprint":receipt.command_fingerprint,
            "paper_order_id":order.paper_order_id,"after_gateway_snapshot_id":receipt.after_snapshot_id,
            "committed_at":order.accepted_at.isoformat()}
        if any(record[name]!=value for name,value in expected.items()) or receipt.before_snapshot_id!=record["gateway_snapshot_id"]:
            raise PaperReservationError("committed reservation conflicts with durable order")
        return PaperReservationReconciliationV1("COMMITTED",current["checkpoint_id"],True,False,False)
