"""Validate provider-neutral evidence continuity after a recovery or replay."""
from collections import defaultdict
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    bars_path = ROOT / "outputs/provider_neutral_paper_trial/live-bars-latest.json"
    ledger_path = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"
    cockpit_path = ROOT / "outputs/provider_neutral_paper_trial/cockpit-latest.json"
    if not bars_path.exists() or not cockpit_path.exists(): raise SystemExit("Provider-neutral replay evidence is incomplete.")
    latest = json.loads(bars_path.read_text(encoding="utf-8"))
    bars = latest.get("bars", [])
    by_symbol = defaultdict(list)
    for bar in bars:
        if not bar.get("symbol") or not bar.get("id") or not bar.get("close_time"): raise SystemExit("Malformed canonical bar detected.")
        by_symbol[bar["symbol"]].append(bar)
    if len({bar["id"] for bar in bars}) != len(bars): raise SystemExit("Duplicate canonical bar identity detected.")
    for symbol, rows in by_symbol.items():
        if [row["close_time"] for row in rows] != sorted(row["close_time"] for row in rows): raise SystemExit(f"Out-of-order canonical bars detected for {symbol}.")
    cockpit = json.loads(cockpit_path.read_text(encoding="utf-8"))
    if cockpit.get("trading_authority") is not False or cockpit.get("authority", {}).get("live_trading_permitted") is not False: raise SystemExit("Replay validation rejected unauthorized state.")
    ledger_rows = 0; ledger_ids = set()
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            row = json.loads(line); ledger_rows += 1; expected = dict(row); actual = expected.pop("decision_id", None)
            fingerprint = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if actual != fingerprint or actual in ledger_ids: raise SystemExit("Decision-ledger identity is not deterministic.")
            ledger_ids.add(actual)
    print(json.dumps({"schema_version": "provider-neutral-replay-validation-v1", "bar_count": len(bars), "ledger_rows": ledger_rows, "trading_authority": False}))

if __name__ == "__main__": main()
