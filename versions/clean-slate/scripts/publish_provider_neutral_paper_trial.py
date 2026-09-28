"""Publish the owned ES/NQ 15-session paper-trial ledger; never routes orders."""
from pathlib import Path
import json
import sys
from datetime import datetime, timezone
import os
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtesting.provider_neutral_paper_trial_v1 import build_provider_neutral_trial, snapshot_document


def atomic_write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    now = datetime.now(timezone.utc)
    snapshot = build_provider_neutral_trial(trades=(), evaluated_at=now)
    document = snapshot_document(snapshot)
    document["market_data_provider"] = "PLUGGABLE_DATABENTO_OR_APPROVED_ALTERNATIVE"
    document["market_data_live_connected"] = False
    document["market_data_note"] = "No live feed is connected; this artifact is the owned simulator boundary."
    atomic_write(ROOT / "outputs/provider_neutral_paper_trial/latest.json", document)
    atomic_write(ROOT / "outputs/provider_neutral_paper_trial/trades.jsonl",
                 {"schema_version": "provider-neutral-paper-trade-journal-v1", "rows": []})
    print(json.dumps({"schema_version": document["schema_version"],
        "trial_id": document["trial_id"], "configured_sessions": document["configured_sessions"],
        "completed_sessions": document["completed_sessions"], "profiles": 3,
        "market_data_live_connected": False, "paper_execution_permitted": False,
        "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
