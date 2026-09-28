from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from datetime import datetime,timezone
from decimal import Decimal
from backtesting.databento_research_dataset_v1 import read_databento_research_days
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_v1 import _evaluate_once
from backtesting.ninjatrader_shadow_profile_comparison_v1 import compare_shadow_profiles
def main():
 now=datetime.now(timezone.utc);markets={};qualified=0
 for market in FuturesCanonicalMarket:
  evidence=read_databento_research_days(ROOT/'data/databento_recovery_staging',market=market,days=('2026-09-04','2026-09-07','2026-09-08','2026-09-09','2026-09-10'),as_of=now)
  result=_evaluate_once(evidence=evidence,minimum_tick=Decimal('0.25'),specification_id='0'*64,as_of=now);counts=dict(result[4]);armed=counts.get('ARMED_CONTINUATION',0)+counts.get('ENTRY_ZONE_ARMED_REVERSAL',0);qualified+=armed
  markets[market.value]={"dataset_id":evidence.dataset.dataset_id,"record_count":evidence.record_count,"gap_fact_count":len(evidence.dataset.gaps),"outcome_counts":counts,"qualified_opportunity_count":armed,"source_sha256":evidence.source_sha256}
 profiles=compare_shadow_profiles(trades=(),evaluated_at=now)
 report={"schema_version":"databento-research-day-evaluation-v1","state":"COMPLETE","context_days_utc":["2026-09-04","2026-09-07","2026-09-08","2026-09-09","2026-09-10"],"shortened_session_days_utc":["2026-09-07"],"evaluation_day_utc":"2026-09-10","markets":markets,"qualified_opportunity_count":qualified,"profile_selection_state":profiles.selection_state.value,"profile_candidate":None,"profile_trade_count":0,"reason":"qualified signals require retained completed lifecycles before risk-profile ranking","comparison_only":True,"paper_execution_permitted":False,"trading_authority":False}
 out=ROOT/'outputs/futures_data/databento_research_evaluation/2026-09-10.json';out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');tmp.write_bytes(json.dumps(report,sort_keys=True,separators=(',',':')).encode()+b'\n');tmp.replace(out);print(json.dumps(report,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
