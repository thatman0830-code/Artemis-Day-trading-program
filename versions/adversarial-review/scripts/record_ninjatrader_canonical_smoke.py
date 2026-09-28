"""Record one verified, deterministic ES/NQ advisory smoke evaluation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_history_v1 import (
    append_ninjatrader_canonical_smoke,
)
from backtesting.ninjatrader_canonical_smoke_v1 import (
    assert_distinct_ninjatrader_smokes, evaluate_ninjatrader_canonical_smoke,
)
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset


def _specification_id(instrument: str) -> str:
    # Immutable identity of the narrow facts used by this smoke replay.
    return hashlib.sha256(
        f"XCME|{instrument}|minimum_tick=0.25|smoke-v1".encode("ascii")
    ).hexdigest()


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive-root",type=Path,default=Path("data/ninjatrader_closed_bars"))
    parser.add_argument("--history-root",type=Path,default=Path("outputs/ninjatrader_canonical_smoke_history"))
    parser.add_argument("--day")
    args=parser.parse_args()
    now=datetime.now(timezone.utc);day=args.day or now.date().isoformat();reports=[]
    for market in FuturesCanonicalMarket:
        evidence=read_closed_bar_dataset(args.archive_root,market=market,day=day,as_of=now)
        reports.append(evaluate_ninjatrader_canonical_smoke(evidence=evidence,
            minimum_tick=Decimal("0.25"),
            instrument_specification_id=_specification_id(evidence.instrument),as_of=now))
    assert_distinct_ninjatrader_smokes(reports[0],reports[1])
    events=[append_ninjatrader_canonical_smoke(args.history_root,report=report)
            for report in reports]
    print(json.dumps({"schema_version":"ninjatrader-canonical-smoke-record-result-v1",
        "evaluated_at":now.isoformat(),"reports":[{"market":event.market.value,
        "sequence":event.sequence,"event_id":event.event_id,
        "report_id":event.report_id,"latest_outcome":event.latest_outcome,
        "source_bar_count":event.report["source_bar_count"],
        "deterministic_repeat_verified":event.report["deterministic_repeat_verified"],
        "trading_authority":False} for event in events],"trading_authority":False},
        sort_keys=True,separators=(",",":")))
    return 0


if __name__=="__main__": raise SystemExit(main())
