"""Supplementally bind immutable paper attribution to its sibling strategy history."""
from __future__ import annotations

import argparse,hashlib,json,os
from pathlib import Path

from execution.paper_session_attribution_v1 import (
    ARTIFACT as ATTRIBUTION_ARTIFACT,SCHEMA as ATTRIBUTION_SCHEMA,_canonical,_read,_read_strategy_history,
)

SCHEMA="paper-strategy-history-binding-v1"
ARTIFACT="strategy-history-binding-v1.json"


class PaperStrategyHistoryBindingError(RuntimeError):pass


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def build_binding(session_root:Path)->dict:
    root=Path(session_root).resolve();attribution_path=root/ATTRIBUTION_ARTIFACT
    if not root.is_dir()or not attribution_path.is_file():
        raise PaperStrategyHistoryBindingError("session attribution is unavailable")
    raw=attribution_path.read_bytes()
    try:attribution=json.loads(raw)
    except (UnicodeDecodeError,json.JSONDecodeError)as exc:
        raise PaperStrategyHistoryBindingError("session attribution is unreadable")from exc
    payload=attribution.get("payload")if type(attribution)is dict else None
    if (attribution.get("schema_version")!=ATTRIBUTION_SCHEMA or type(payload)is not dict
            or payload.get("session_directory")!=root.name
            or attribution.get("payload_sha256")!=_sha(_canonical(payload))):
        raise PaperStrategyHistoryBindingError("session attribution identity is invalid")
    status,_=_read(root/"canonical-strategy-status.json")
    history_path=root.parent/(root.name+"-canonical-strategy-history.jsonl")
    try:summary,history_hash=_read_strategy_history(history_path,status)
    except Exception as exc:raise PaperStrategyHistoryBindingError("strategy history verification failed")from exc
    if summary is None:raise PaperStrategyHistoryBindingError("strategy history is unavailable")
    body={"schema_version":SCHEMA,"session_directory":root.name,
        "attribution_file_sha256":_sha(raw),"attribution_payload_sha256":attribution["payload_sha256"],
        "history_relative_path":"../"+history_path.name,"history_file_sha256":history_hash,
        "history_summary":summary,"advisory_only":True,"live_trading_permitted":False,
        "trading_authority":False}
    return {"schema_version":SCHEMA,"payload":body,"payload_sha256":_sha(_canonical(body))}


def write_binding(session_root:Path)->Path:
    root=Path(session_root).resolve();document=build_binding(root);path=root/ARTIFACT
    raw=_canonical(document)+b"\n"
    if path.exists():
        if path.read_bytes()!=raw:raise PaperStrategyHistoryBindingError("immutable binding conflict")
        return path
    temporary=root/("."+ARTIFACT+f".{os.getpid()}.tmp")
    try:
        with temporary.open("xb")as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)
    return path


def read_binding(attribution_path:Path)->str|None:
    path=Path(attribution_path).parent/ARTIFACT
    if not path.exists():return None
    expected=build_binding(path.parent);raw=path.read_bytes()
    try:actual=json.loads(raw)
    except (UnicodeDecodeError,json.JSONDecodeError)as exc:raise PaperStrategyHistoryBindingError("binding is unreadable")from exc
    if actual!=expected:raise PaperStrategyHistoryBindingError("binding verification failed")
    return _sha(raw)


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--sessions-root",type=Path,required=True);args=parser.parse_args()
    paths=[]
    for attribution in sorted(args.sessions_root.glob("*/"+ATTRIBUTION_ARTIFACT)):
        paths.append(str(write_binding(attribution.parent)))
    print(json.dumps({"state":"STRATEGY_HISTORY_BINDINGS_COMPLETE","binding_count":len(paths),
        "paths":paths,"trading_authority":False},sort_keys=True));return 0


if __name__=="__main__":raise SystemExit(main())
