"""Retain verified NinjaTrader closed bars in restart-safe hash chains."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import argparse,hashlib,json,os,time
from execution.ninjatrader_closed_bar_bridge_v1 import NinjaTraderClosedBarError,read_closed_bar
from futures_data.sessions import IntervalClassification, SessionCalendar
VERSION="ninjatrader-closed-bar-recorder-v1"
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+".tmp");tmp.write_bytes(_canonical(value)+b"\n");os.replace(tmp,path)
def _missing_counts(left,right):
 calendar=SessionCalendar();unresolved=scheduled=0;cursor=left+timedelta(minutes=1)
 while cursor<right:
  classification=calendar.classify(cursor-timedelta(minutes=1))
  if classification is IntervalClassification.OPEN:unresolved+=1
  else:scheduled+=1
  cursor+=timedelta(minutes=1)
 return unresolved,scheduled
def _chain(path):
 previous="0"*64;last=None;count=0;gaps=0;scheduled=0
 if not path.exists():return previous,last,count,gaps,scheduled
 for raw in path.read_bytes().splitlines():
  doc=json.loads(raw);digest=doc.pop("record_sha256")
  if doc.get("schema_version")!=VERSION or doc.get("previous_record_sha256")!=previous or hashlib.sha256(_canonical(doc)).hexdigest()!=digest:raise ValueError("closed-bar chain invalid")
  close=datetime.fromisoformat(doc["close_time_utc"])
  if last is not None:
   delta=int((close-last).total_seconds()//60)
   if delta<=0:raise ValueError("closed-bar chronology invalid")
   unresolved_delta,scheduled_delta=_missing_counts(last,close);gaps+=unresolved_delta;scheduled+=scheduled_delta
  previous,last,count=digest,close,count+1
 return previous,last,count,gaps,scheduled
def record_one(*,bar_path,archive_root,as_of):
 bar=read_closed_bar(path=bar_path,as_of=as_of);lane=bar.market.value;chain=Path(archive_root)/lane/(bar.close_time.date().isoformat()+".jsonl");chain.parent.mkdir(parents=True,exist_ok=True)
 previous,last,count,gaps,scheduled=_chain(chain)
 if last==bar.close_time:return False
 if last is not None and bar.close_time<last:raise ValueError("closed bar regressed")
 gap,scheduled_gap=_missing_counts(last,bar.close_time)if last else(0,0)
 body={"close":str(bar.close),"close_time_utc":bar.close_time.isoformat(),"high":str(bar.high),"instrument":bar.instrument,"low":str(bar.low),"market":lane,"open":str(bar.open),"open_time_utc":bar.open_time.isoformat(),"paper_only":True,"previous_record_sha256":previous,"schema_version":VERSION,"source_payload_sha256":bar.payload_sha256,"trading_authority":False,"volume":bar.volume}
 digest=hashlib.sha256(_canonical(body)).hexdigest()
 with chain.open("ab")as stream:stream.write(_canonical({**body,"record_sha256":digest})+b"\n");stream.flush();os.fsync(stream.fileno())
 _atomic(chain.parent/"manifest.json",{"archive_file":chain.name,"head_record_sha256":digest,"instrument":bar.instrument,"last_close_time_utc":bar.close_time.isoformat(),"market":lane,"record_count":count+1,"schema_version":VERSION,"scheduled_non_trading_minute_count":scheduled+scheduled_gap,"state":"RECORDING","trading_authority":False,"unresolved_gap_count":gaps+gap})
 return True
def cycle(*,bar_root,archive_root,as_of):
 result={}
 for root in("MES","MNQ"):
  try:result[root]=record_one(bar_path=Path(bar_root)/(root+".bar.json"),archive_root=archive_root,as_of=as_of)
  except(NinjaTraderClosedBarError,FileNotFoundError):result[root]=None
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--bar-root",type=Path,required=True);p.add_argument("--archive-root",type=Path,required=True);p.add_argument("--interval",type=float,default=1);a=p.parse_args()
 lock_path=a.archive_root/".single-writer.lock";lock_path.parent.mkdir(parents=True,exist_ok=True)
 lock=lock_path.open("a+b")
 try:
  import msvcrt
  lock.seek(0);lock.write(b"0");lock.flush();lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError as exc:raise RuntimeError("NinjaTrader closed-bar recorder already running")from exc
  while True:cycle(bar_root=a.bar_root,archive_root=a.archive_root,as_of=datetime.now(timezone.utc));time.sleep(a.interval)
 finally:
  try:
   lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  except Exception:pass
  lock.close()
if __name__=="__main__":main()
