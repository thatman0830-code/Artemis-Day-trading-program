"""Read-only completeness verification for the scheduled OneDrive delivery task."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .off_host_alert_delivery import verify_delivery


def main() -> int:
    parser=argparse.ArgumentParser(description="Verify OneDrive alert delivery completeness")
    parser.add_argument("--alerts",type=Path,required=True)
    parser.add_argument("--sink",type=Path,required=True)
    parser.add_argument("--receipts",type=Path,required=True)
    args=parser.parse_args()
    count=verify_delivery(alerts_path=args.alerts,sink=args.sink,local_receipts=args.receipts)
    print(json.dumps({"state":"DELIVERY_VERIFIED","verified_count":count,
                      "trading_authority":False},sort_keys=True,separators=(",",":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
