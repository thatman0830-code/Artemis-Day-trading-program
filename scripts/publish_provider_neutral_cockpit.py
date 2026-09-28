"""Publish a local, read-only cockpit snapshot for the ES/NQ paper campaign."""
from pathlib import Path
from datetime import datetime, timezone
import ctypes, json, os, shutil, uuid

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backtesting.tradersync_style_adherence_v1 import build_adherence_report
OUT = ROOT / "outputs/provider_neutral_paper_trial/cockpit-latest.json"

def read(name, default=None):
    path = ROOT / name
    if not path.exists(): return default
    # PowerShell 5.1 may emit UTF-8 JSON with a BOM (notably the
    # supervisor health artifact).  Accept both BOM and BOM-less JSON so a
    # valid fail-closed health state cannot crash cockpit publication.
    return json.loads(path.read_text(encoding="utf-8-sig"))

def ledger_summary():
    path = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"
    counts = {"TAKEN": 0, "SKIPPED": 0, "VETOED": 0}
    latest = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try: row = json.loads(line)
            except json.JSONDecodeError: continue
            classification = row.get("decision_class")
            if classification in counts: counts[classification] += 1
            latest.append({"decision_id": row.get("decision_id"), "decision_class": classification,
                           "lane": row.get("lane"), "symbol": row.get("symbol"),
                           "evaluated_at": row.get("evaluated_at"),
                           "execution_quality": row.get("execution_quality", {})})
    return {"counts": counts, "total": sum(counts.values()), "latest": latest[-10:]}

def ledger_analytics():
    path = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: continue
    counts = {"TAKEN": 0, "SKIPPED": 0, "VETOED": 0}
    by_lane, by_symbol = {}, {}
    adherence_values, fill_values = [], []
    for row in rows:
        cls = row.get("decision_class")
        if cls in counts: counts[cls] += 1
        for key, target in (("lane", by_lane), ("symbol", by_symbol)):
            value = row.get(key) or "UNSPECIFIED"
            target[value] = target.get(value, 0) + 1
        quality = row.get("execution_quality", {})
        if quality.get("rule_adherence") is not None: adherence_values.append(quality["rule_adherence"])
        if quality.get("fill_quality_score") is not None: fill_values.append(quality["fill_quality_score"])
    taken = counts["TAKEN"]
    return {
        "schema_version": "provider-neutral-trading-analytics-v1",
        "decision_counts": counts,
        "total_decisions": sum(counts.values()),
        "by_lane": by_lane,
        "by_symbol": by_symbol,
        "taken_sample_count": taken,
        "metric_status": "READY" if taken else "INSUFFICIENT_TAKEN_SAMPLE",
        "plan_adherence_rate": (sum(adherence_values) / len(adherence_values)) if adherence_values else None,
        "execution_quality_score": (sum(fill_values) / len(fill_values)) if fill_values else None,
        "holding_time_minutes": None,
        "profit_factor": None,
        "win_rate": None,
        "drawdown": None,
        "read_only": True,
        "trading_authority": False,
    }

def resource_snapshot():
    disk = shutil.disk_usage(ROOT)
    memory = {"total_bytes": None, "available_bytes": None}
    if os.name == "nt":
        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong),
                        ("pagefile_total", ctypes.c_ulonglong), ("pagefile_available", ctypes.c_ulonglong),
                        ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong),
                        ("extended", ctypes.c_ulonglong)]
        status = Status(); status.length = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            memory = {"total_bytes": status.total, "available_bytes": status.available}
    return {"cpu_count": os.cpu_count(), "memory": memory,
            "disk": {"total_bytes": disk.total, "free_bytes": disk.free},
            "network_reachability": "not_probed_by_read_only_snapshot"}

def main():
    cycle = read("outputs/provider_neutral_paper_trial/live-paper-cycle-latest.json", {})
    adaptive = read("outputs/provider_neutral_paper_trial/adaptive-lane-latest.json", {})
    coverage = read("outputs/provider_neutral_paper_trial/coverage.json", {})
    supervisor = read("outputs/provider_neutral_paper_trial/pipeline-supervisor-health.json", {})
    authority = read("config/provider_neutral_paper_authority.json", {})
    capture = read("outputs/provider_neutral_paper_trial/live-capture-latest.json", {})
    ledger = ledger_summary()
    analytics = ledger_analytics()
    ledger_path = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"
    ledger_rows = []
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            try: ledger_rows.append(json.loads(line))
            except json.JSONDecodeError: continue
    adherence = build_adherence_report(ledger_rows)
    doc = {
        "schema_version": "provider-neutral-cockpit-v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": {"supervisor_state": supervisor.get("state", "UNKNOWN"),
                     "consecutive_failures": supervisor.get("consecutive_failures", 0),
                     "bars_consumed": cycle.get("bars_consumed", 0),
                     # Prefer the live capture's rollover-safe continuous
                     # symbols.  The historical cycle may retain a prior
                     # contract code (for example ESU6/NQU6) and should not
                     # make the operational view appear to be using expired
                     # contracts.
                     "symbols": capture.get("symbols") or cycle.get("symbols", []),
                     "symbol_mappings": capture.get("mapping_symbols", []),
                     "latency": capture.get("latency", {"freshness_state": "UNKNOWN"})},
        "resources": resource_snapshot(),
        "portfolios": cycle.get("profiles", []),
        "baseline": {"signal_status": cycle.get("signal_status", "UNKNOWN"),
                      "paper_execution_permitted": cycle.get("paper_execution_permitted", False)},
        "adaptive": {"candidate_count": sum(r.get("candidate") is not None for r in adaptive.get("reports", [])),
                      "reports": adaptive.get("reports", [])},
        "decision_ledger": ledger,
        "analytics": analytics,
        "plan_adherence": adherence,
        "coverage": {"covered_days": coverage.get("covered_days", 0),
                      "configured_days": coverage.get("configured_days", []),
                      "missing_or_unqualified_days": coverage.get("missing_or_unqualified_days", [])},
        "authority": {"paper_execution_permitted": authority.get("paper_execution_permitted", False),
                      "live_trading_permitted": authority.get("live_trading_permitted", False),
                      "trading_authority": authority.get("trading_authority", False)},
        "comparison_only": False,
        "trading_authority": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("." + OUT.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, OUT)
    finally: tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": doc["schema_version"], "candidate_count": doc["adaptive"]["candidate_count"], "trading_authority": False}, sort_keys=True))

if __name__ == "__main__": main()
