"""Append-only hash chain of completed, non-executable MES/MNQ shadow trades."""
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal
import hashlib,json,os
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1,ShadowSide
VERSION="ninjatrader-completed-shadow-trade-history-v1"
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def _payload(t):return{"signal_id":t.signal_id,"market":t.market.value,"side":t.side.value,"entry_time":t.entry_time.isoformat(),"exit_time":t.exit_time.isoformat(),"entry_price":format(t.entry_price,"f"),"stop_price":format(t.stop_price,"f"),"exit_price":format(t.exit_price,"f"),"source_report_id":t.source_report_id,"trading_authority":False}
def read_completed_shadow_trade_history(root):
 directory=Path(root).absolute()/"events"
 if not directory.exists():return()
 if not directory.is_dir()or directory.is_symlink():raise ValueError("completed trade history path unsafe")
 paths=sorted(directory.iterdir(),key=lambda x:x.name)
 if[ x.name for x in paths]!=[f"{i:020d}.json"for i in range(len(paths))]or any(not x.is_file()or x.is_symlink()for x in paths):raise ValueError("completed trade inventory invalid")
 trades=[];previous=None;last_exit=None
 for sequence,path in enumerate(paths):
  doc=json.loads(path.read_bytes());digest=doc.pop("event_id")
  if doc.get("schema_version")!=VERSION or doc.get("sequence")!=sequence or doc.get("previous_event_id")!=previous or doc.get("trading_authority")is not False or hashlib.sha256(_canonical(doc)).hexdigest()!=digest:raise ValueError("completed trade chain invalid")
  t=doc.get("trade",{});entry=datetime.fromisoformat(t["entry_time"]);exit=datetime.fromisoformat(t["exit_time"]);trade=CompletedShadowTradeV1(t["signal_id"],FuturesCanonicalMarket(t["market"]),ShadowSide(t["side"]),entry,exit,Decimal(t["entry_price"]),Decimal(t["stop_price"]),Decimal(t["exit_price"]),t["source_report_id"],False)
  if t.get("trading_authority")is not False or(last_exit is not None and trade.exit_time<last_exit):raise ValueError("completed trade chronology invalid")
  trades.append(trade);previous=digest;last_exit=trade.exit_time
 return tuple(trades)
def append_completed_shadow_trade(root,*,trade):
 if not isinstance(trade,CompletedShadowTradeV1)or trade.trading_authority is not False:raise ValueError("non-authoritative completed trade required")
 base=Path(root).absolute();existing=read_completed_shadow_trade_history(base);same=tuple(x for x in existing if x.signal_id==trade.signal_id)
 if same:
  if same!=(trade,):raise ValueError("completed signal identity conflict")
  return same[0]
 if existing and trade.exit_time<existing[-1].exit_time:raise ValueError("completed trade chronology regressed")
 directory=base/"events";directory.mkdir(parents=True,exist_ok=True)
 if directory.is_symlink()or directory.parent.is_symlink():raise ValueError("completed trade directory unsafe")
 body={"schema_version":VERSION,"sequence":len(existing),"previous_event_id":None if not existing else json.loads((directory/f"{len(existing)-1:020d}.json").read_bytes())["event_id"],"trade":_payload(trade),"trading_authority":False};document={**body,"event_id":hashlib.sha256(_canonical(body)).hexdigest()};target=directory/f"{len(existing):020d}.json";temporary=target.with_suffix(".json.tmp")
 try:
  with temporary.open("xb")as stream:stream.write(_canonical(document));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,target)
 finally:temporary.unlink(missing_ok=True)
 return read_completed_shadow_trade_history(base)[-1]
