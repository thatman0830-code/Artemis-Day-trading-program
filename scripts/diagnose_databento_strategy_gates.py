from __future__ import annotations
import json,sys
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backtesting.databento_research_dataset_v1 import read_databento_research_days
from backtesting.databento_strategy_gate_diagnostic_v1 import diagnose_strategy_gates
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_v1 import _evaluate_once
def main():
 now=datetime.now(timezone.utc);days=('2026-09-04','2026-09-07','2026-09-08','2026-09-09','2026-09-10');markets={}
 for market in FuturesCanonicalMarket:
  evidence=read_databento_research_days(ROOT/'data/databento_recovery_staging',market=market,days=days,as_of=now)
  _,state=_evaluate_once(evidence=evidence,minimum_tick=Decimal('0.25'),specification_id='0'*64,as_of=now,return_state=True)
  markets[market.value]=asdict(diagnose_strategy_gates(state))
 report={'schema_version':'databento-five-day-strategy-gate-audit-v1','state':'COMPLETE','context_days_utc':list(days),'markets':markets,'threshold_changes_applied':False,'comparison_only':True,'paper_execution_permitted':False,'trading_authority':False}
 out=ROOT/'outputs/futures_data/databento_research_evaluation/2026-09-10-gate-audit.json';out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(report,sort_keys=True,separators=(',',':')));tmp.replace(out);print(json.dumps(report,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
