"""Publish the read-only adaptive confirmation lane from canonical live bars."""
from pathlib import Path
import json, os, uuid
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtesting.adaptive_confirmation_lane_v1 import evaluate

STREAM = ROOT / "outputs/provider_neutral_paper_trial/live-bars.jsonl"
OUT = ROOT / "outputs/provider_neutral_paper_trial/adaptive-lane-latest.json"

def main():
    by_symbol = {}
    if STREAM.exists():
        for line in STREAM.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            bar = json.loads(line); by_symbol.setdefault(bar.get("symbol"), []).append(bar)
    reports = [evaluate(symbol, bars) for symbol, bars in sorted(by_symbol.items()) if symbol]
    doc = {"schema_version":"adaptive-confirmation-lane-batch-v1", "reports":reports,
           "baseline_unchanged":True, "comparison_only":True,
           "paper_execution_permitted":False, "trading_authority":False}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("." + OUT.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, OUT)
    finally: tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version":doc["schema_version"],"reports":len(reports),"candidates":sum(r["candidate"] is not None for r in reports),"trading_authority":False}, sort_keys=True))

if __name__ == "__main__": main()
