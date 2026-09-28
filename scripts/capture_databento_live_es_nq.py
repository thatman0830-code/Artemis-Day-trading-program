"""Bounded, read-only Databento ES/NQ live-capture probe."""
from pathlib import Path
from datetime import datetime, timezone
import json, os, sys, threading, time, uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import databento as db
from backtesting.databento_live_bar_aggregator_v1 import aggregate_trades
from backtesting.databento_live_canonicalizer_v1 import canonicalize_bars

def diagnose_capture(counts, mapping_symbols, system_messages):
    """Classify zero-flow captures without treating them as valid market data."""
    total = sum(counts.values())
    mapped = {row.get("requested_symbol") for row in mapping_symbols}
    ack = any(row.get("code") == "subscription_ack" for row in system_messages)
    heartbeat = any(row.get("code") == "heartbeat" for row in system_messages)
    if total:
        status = "VALID_SAMPLES"
    elif not ack:
        status = "SUBSCRIPTION_OR_ENTITLEMENT_FAILURE"
    elif mapped != set(counts):
        status = "SYMBOL_RESOLUTION_FAILURE"
    elif heartbeat:
        status = "NO_CURRENT_FLOW_OR_MARKET_CLOSED"
    else:
        status = "NO_SAMPLES_UNCLASSIFIED"
    return {"status": status, "records": total, "subscription_ack": ack,
            "heartbeat": heartbeat, "mapped_symbols": sorted(mapped),
            "expected_symbols": sorted(counts)}


def main():
    key = os.environ.get("DATABENTO_API_KEY")
    if not key or not key.startswith("db-"):
        raise SystemExit("DATABENTO_API_KEY is not configured")
    seconds = int(os.environ.get("DATABENTO_CAPTURE_SECONDS", "20"))
    if seconds < 5 or seconds > 120:
        raise SystemExit("DATABENTO_CAPTURE_SECONDS must be 5..120")
    # Use Databento continuous contracts so the probe rolls automatically at
    # quarterly expiry.  Hard-coding ESU6/NQU6 caused a silent zero-record
    # window after the September 2026 rollover even though the subscription
    # and symbol mapping both succeeded.
    requested_symbols = [x.strip() for x in os.environ.get("DATABENTO_SYMBOLS", "ES.c.0,NQ.c.0").split(",") if x.strip()]
    if requested_symbols != ["ES.c.0", "NQ.c.0"]:
        raise SystemExit("DATABENTO_SYMBOLS must contain ES.c.0,NQ.c.0")
    client = db.Live(key=key)
    client.subscribe(dataset="GLBX.MDP3", schema="trades", stype_in="continuous", symbols=requested_symbols)
    timer = threading.Timer(seconds, client.stop)
    timer.daemon = True
    timer.start()
    started = datetime.now(timezone.utc)
    counts = {symbol: 0 for symbol in requested_symbols}
    instrument_symbols = {}
    instrument_requested_symbols = {}
    mapping_symbols = []
    system_messages = []
    unmatched_record_count = 0
    records = []
    try:
        for record in client:
            if type(record).__name__ == "SystemMsg":
                system_messages.append({"code": str(getattr(record, "code", "")), "message": str(getattr(record, "msg", "")), "ts_event": str(getattr(record, "pretty_ts_event", ""))})
                continue
            if type(record).__name__ == "SymbolMappingMsg":
                instrument_symbols[getattr(record, "instrument_id", None)] = str(getattr(record, "stype_out_symbol", ""))
                instrument_requested_symbols[getattr(record, "instrument_id", None)] = str(getattr(record, "stype_in_symbol", ""))
                mapping_symbols.append({"instrument_id": getattr(record, "instrument_id", None), "requested_symbol": str(getattr(record, "stype_in_symbol", "")), "raw_symbol": str(getattr(record, "stype_out_symbol", ""))})
                continue
            instrument_id = getattr(record, "instrument_id", None)
            raw_symbol = instrument_symbols.get(instrument_id)
            requested_symbol = instrument_requested_symbols.get(instrument_id)
            if requested_symbol in counts:
                counts[requested_symbol] += 1
                records.append({
                    "type": type(record).__name__,
                    "symbol": raw_symbol,
                    "requested_symbol": requested_symbol,
                    "ts_event": str(getattr(record, "pretty_ts_event", "")),
                    "ts_recv": str(getattr(record, "pretty_ts_recv", "")),
                    "price_raw": int(getattr(record, "price", 0)),
                    "size": int(getattr(record, "size", 0)),
                    "action": str(getattr(record, "action", "")),
                })
            else:
                unmatched_record_count += 1
    finally:
        timer.cancel()
        client.stop()
    finished = datetime.now(timezone.utc)
    latency_samples = []
    for item in records:
        try:
            source = datetime.fromisoformat(item["ts_event"].replace("Z", "+00:00"))
            received = datetime.fromisoformat(item["ts_recv"].replace("Z", "+00:00"))
            latency_samples.append(max(0.0, (received - source).total_seconds()))
        except (TypeError, ValueError):
            continue
    latency = {
        "contract_version": "provider-neutral-latency-v1",
        "stale_threshold_seconds": 5.0,
        "sample_count": len(latency_samples),
        "source_to_receive_max_seconds": round(max(latency_samples), 6) if latency_samples else None,
        "source_to_receive_avg_seconds": round(sum(latency_samples) / len(latency_samples), 6) if latency_samples else None,
        "stale_sample_count": sum(x > 5.0 for x in latency_samples),
        "freshness_state": "FRESH" if latency_samples and max(latency_samples) <= 5.0 else ("NO_SAMPLES" if not latency_samples else "STALE"),
    }
    diagnostics = diagnose_capture(counts, mapping_symbols, system_messages)
    document = {
        "schema_version": "databento-live-es-nq-capture-v1",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "dataset": "GLBX.MDP3",
        "symbols": requested_symbols,
        "record_counts": counts,
        "mapping_symbols": mapping_symbols[:100],
        "system_messages": system_messages[:100],
        "unmatched_record_count": unmatched_record_count,
        "latency": latency,
        "diagnostics": diagnostics,
        "records": records,
        "read_only": True,
        "paper_execution_permitted": False,
        "trading_authority": False,
    }
    canonical = canonicalize_bars(aggregate_trades(records))
    bars_document = {
        "schema_version": "databento-live-canonical-bars-v1",
        "dataset": "GLBX.MDP3",
        "captured_at": finished.isoformat(),
        "bars": [{"symbol": x.symbol, "open_time": x.open_time.isoformat(), "close_time": x.close_time.isoformat(),
                  "open": format(x.open, "f"), "high": format(x.high, "f"), "low": format(x.low, "f"),
                  "close": format(x.close, "f"), "volume": format(x.volume or 0, "f"), "id": x.id} for x in canonical],
        "read_only": True, "trading_authority": False,
    }
    output = ROOT / "outputs/provider_neutral_paper_trial/live-capture-latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name("." + output.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    bars_output = ROOT / "outputs/provider_neutral_paper_trial/live-bars-latest.json"
    bars_temporary = bars_output.with_name("." + bars_output.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        bars_temporary.write_text(json.dumps(bars_document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(bars_temporary, bars_output)
    finally:
        bars_temporary.unlink(missing_ok=True)
    stream_output = ROOT / "outputs/provider_neutral_paper_trial/live-bars.jsonl"
    with stream_output.open("a", encoding="utf-8") as stream:
        for bar in bars_document["bars"]:
            stream.write(json.dumps(bar, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"schema_version": document["schema_version"], "record_counts": counts,
                      "read_only": True, "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
