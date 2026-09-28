"""Repair only a byte-identical duplicate tail in a NinjaTrader hash chain.

The original evidence is copied into quarantine before any replacement.  Every
other corruption shape fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from execution.ninjatrader_closed_bar_recorder_v1 import VERSION, _canonical, _chain


def repair(*, chain: Path, manifest: Path, quarantine: Path, report: Path) -> dict:
    raw = chain.read_bytes(); lines = raw.splitlines()
    if len(lines) < 2 or lines[-1] != lines[-2]:
        raise ValueError("only a byte-identical duplicate tail is repairable")
    candidate = b"\n".join(lines[:-1]) + b"\n"
    original_sha = hashlib.sha256(raw).hexdigest()
    repaired_sha = hashlib.sha256(candidate).hexdigest()
    quarantine.mkdir(parents=True, exist_ok=True)
    preserved = quarantine / f"{chain.name}.{original_sha}.duplicate-tail"
    if preserved.exists() and preserved.read_bytes() != raw:
        raise ValueError("quarantine identity conflict")
    if not preserved.exists():
        preserved.write_bytes(raw)
    temporary = chain.with_name("." + chain.name + ".repair.tmp")
    temporary.write_bytes(candidate)
    # Validate the staged chain before replacing the source.
    head, last, count, gaps, scheduled = _chain(temporary)
    current = json.loads(manifest.read_text("utf-8-sig"))
    if current.get("schema_version") != VERSION or current.get("trading_authority") is not False:
        raise ValueError("manifest policy rejected")
    os.replace(temporary, chain)
    updated = {**current, "head_record_sha256": head,
               "last_close_time_utc": last.isoformat(), "record_count": count,
               "unresolved_gap_count": gaps,
               "scheduled_non_trading_minute_count": scheduled}
    manifest_tmp = manifest.with_name("." + manifest.name + ".repair.tmp")
    manifest_tmp.write_bytes(_canonical(updated) + b"\n"); os.replace(manifest_tmp, manifest)
    document = {"schema_version":"ninjatrader-duplicate-tail-repair-v1",
        "state":"REPAIRED_WITH_ORIGINAL_QUARANTINED","chain":str(chain),
        "original_sha256":original_sha,"repaired_sha256":repaired_sha,
        "quarantine_path":str(preserved),"removed_duplicate_count":1,
        "record_count":count,"head_record_sha256":head,"observed_at":datetime.now(timezone.utc).isoformat(),
        "paper_execution_permitted":False,"trading_authority":False}
    report.parent.mkdir(parents=True,exist_ok=True)
    report_tmp=report.with_name("."+report.name+".tmp")
    report_tmp.write_bytes(_canonical(document)+b"\n");os.replace(report_tmp,report)
    return document


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument("--chain",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--quarantine",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True);a=p.parse_args()
    print(json.dumps(repair(chain=a.chain,manifest=a.manifest,quarantine=a.quarantine,report=a.report),sort_keys=True,separators=(",",":")))
    return 0


if __name__=="__main__":raise SystemExit(main())
