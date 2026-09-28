"""Five-day, observation-only Forex Factory market-context trial."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime,timedelta,timezone
import hashlib,json

VERSION="forex-factory-shadow-trial-v1"
IMPACTS={"Low","Medium","High","Holiday","Non-Economic"}

def five_weekdays(start:date)->tuple[str,...]:
 days=[];cursor=start
 while len(days)<5:
  if cursor.weekday()<5:days.append(cursor.isoformat())
  cursor+=timedelta(days=1)
 return tuple(days)

@dataclass(frozen=True)
class NewsEventV1:
 event_id:str;title:str;currency:str;scheduled_at:datetime;impact:str
 forecast:str;previous:str;actual:str

@dataclass(frozen=True)
class ShadowTrialSnapshotV1:
 snapshot_id:str;observed_at:datetime;source_sha256:str;trial_days:tuple[str,...]
 state:str;all_event_count:int;usd_event_count:int;high_impact_usd_count:int
 events:tuple[NewsEventV1,...];directional_signal_permitted:bool=False
 order_influence_permitted:bool=False;paper_execution_permitted:bool=False
 trading_authority:bool=False;schema_version:str=VERSION

@dataclass(frozen=True)
class ShadowPolicyV1:
 name:str;high_before_minutes:int;high_after_minutes:int
 medium_before_minutes:int;medium_after_minutes:int

POLICIES=(ShadowPolicyV1("CONSERVATIVE",30,30,10,10),ShadowPolicyV1("MODERATE",15,20,5,5),ShadowPolicyV1("AGGRESSIVE",5,10,0,0))

@dataclass(frozen=True)
class NewsContextV1:
 profile:str;as_of:datetime;regime:str;nearby_event_ids:tuple[str,...]
 new_entry_recommendation:str;position_recommendation:str
 price_volume_confirmation_required:bool
 directional_signal:str|None=None;order_influence_permitted:bool=False
 trading_authority:bool=False

def classify_news_context(*,events:tuple[NewsEventV1,...],as_of:datetime,policy:ShadowPolicyV1)->NewsContextV1:
 if as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0):raise ValueError("UTC as_of required")
 nearby=[];regime="NORMAL_SESSION"
 for event in events:
  if event.currency!="USD"or event.impact not in{"High","Medium"}:continue
  before=policy.high_before_minutes if event.impact=="High"else policy.medium_before_minutes
  after=policy.high_after_minutes if event.impact=="High"else policy.medium_after_minutes
  delta=(as_of-event.scheduled_at).total_seconds()/60
  if -before<=delta<=after:
   nearby.append(event)
   if delta<0:regime="PRE_ANNOUNCEMENT"
   elif delta<=5:regime="RELEASE_VOLATILITY"
   else:regime="POST_NEWS_DISCOVERY"
 blocked=bool(nearby)
 position="RESEARCH_FLATTEN_OR_REDUCE"if blocked and policy.name=="CONSERVATIVE"else("RESEARCH_REDUCE_OR_HOLD"if blocked else"NO_NEWS_ADJUSTMENT")
 return NewsContextV1(policy.name,as_of,regime,tuple(x.event_id for x in nearby),"SHADOW_BLOCK"if blocked else"SHADOW_ALLOW",position,blocked)

def daily_risk_map(snapshot:ShadowTrialSnapshotV1)->dict:
 rows=[]
 for day in snapshot.trial_days:
  events=[x for x in snapshot.events if x.currency=="USD"and x.scheduled_at.date().isoformat()==day]
  rows.append({"day":day,"event_count":len(events),"high_impact_count":sum(x.impact=="High"for x in events),"events":[{"event_id":x.event_id,"title":x.title,"scheduled_at":x.scheduled_at.isoformat(),"impact":x.impact}for x in events]})
 return {"schema_version":"forex-factory-daily-risk-map-v1","source_snapshot_id":snapshot.snapshot_id,"days":rows,"directional_signal_permitted":False,"order_influence_permitted":False,"trading_authority":False}

def parse_snapshot(raw:bytes,*,observed_at:datetime,start_day:date)->ShadowTrialSnapshotV1:
 if observed_at.tzinfo is None or observed_at.utcoffset()!=timedelta(0):raise ValueError("UTC observed_at required")
 value=json.loads(raw)
 if not isinstance(value,list):raise ValueError("calendar list required")
 events=[]
 for row in value:
  required={"title","country","date","impact","forecast","previous"}
  if not isinstance(row,dict)or not required.issubset(row):raise ValueError("calendar event schema rejected")
  when=datetime.fromisoformat(str(row["date"]).replace("Z","+00:00")).astimezone(timezone.utc)
  impact=str(row["impact"])
  if impact not in IMPACTS:raise ValueError("unknown impact rejected")
  body=(str(row["title"]),str(row["country"]),when.isoformat(),impact,str(row["forecast"]),str(row["previous"]),str(row.get("actual","")))
  event_id=hashlib.sha256(json.dumps(body,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
  events.append(NewsEventV1(event_id,body[0],body[1],when,body[3],body[4],body[5],body[6]))
 events.sort(key=lambda x:(x.scheduled_at,x.currency,x.title,x.event_id))
 if len({x.event_id for x in events})!=len(events):raise ValueError("duplicate calendar event rejected")
 source=hashlib.sha256(raw).hexdigest();days=five_weekdays(start_day)
 usd=tuple(x for x in events if x.currency=="USD")
 identity=hashlib.sha256((VERSION+source+observed_at.isoformat()).encode()).hexdigest()
 return ShadowTrialSnapshotV1(identity,observed_at,source,days,"OBSERVING",len(events),len(usd),sum(x.impact=="High" for x in usd),tuple(events))
