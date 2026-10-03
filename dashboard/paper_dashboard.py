"""Read-only local dashboard for the MES paper portfolio runner.

Localhost GET only; never writes to the runner. Evidence qualification uses the runner's own rules
(mes_pilot.report.collapse_session_dates + the append-only corrections registry, mes_pilot.evidence),
so the UI can never count a session the reports would not. Diagnostic and synthetic runs are listed
separately and never shown as forward evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent
BOOKS = ("conservative", "moderate", "aggressive")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_jsonl(path: Path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return rows


def _runner_modules(root: Path):
    """Import the runner's evidence rules read-only (no side effects)."""
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from mes_pilot.evidence import apply_corrections, load_corrections
        from mes_pilot.report import collapse_session_dates
        return apply_corrections, load_corrections, collapse_session_dates
    except Exception:  # runner code unavailable: show raw only, flagged
        return None


def _chain_ok(rows) -> bool:
    from hashlib import sha256
    prev = "0" * 64
    for rec in rows:
        body = dict(rec)
        digest = body.pop("hash", None)
        if digest is None or body.get("prev_hash") != prev:
            return False
        if sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != digest:
            return False
        prev = digest
    return True


def qualification(root: Path, ledgers: dict) -> dict:
    mods = _runner_modules(root)
    if mods is None:
        return {"available": False, "note": "Runner evidence rules unavailable; qualified counts not shown."}
    apply_corrections, load_corrections, collapse = mods
    reg = root / "outputs" / "mes_pilot" / "evidence_qualification" / "corrections.jsonl"
    corrections = load_corrections(reg) if reg.exists() else []
    out = {"available": True, "registry": str(reg), "correction_rows": len(corrections), "books": {}}
    for key, rows in ledgers.items():
        sessions = [r for r in rows if r.get("type") == "SESSION_SUMMARY"]
        raw = collapse(sessions)
        corrected, applied = apply_corrections(sessions, corrections)
        q = collapse(corrected)
        chain = _chain_ok(rows) if rows else None
        by_hash = {c["session_summary_record_hash"]: c for c in applied}
        dates = []
        for s in sessions:
            c = by_hash.get(s.get("hash"))
            dates.append({"session_date": s.get("session_date"), "raw_classification": s.get("classification"),
                          "qualified_classification": c["corrected_classification"] if c else s.get("classification"),
                          "qualified": s.get("session_date") in q["eligible_dates"] and bool(chain),
                          "reason_code": c["reason_code"] if c else None,
                          "reason_detail": c["reason_detail"] if c else None,
                          "status_layers": s.get("status_layers"), "readiness": s.get("readiness"),
                          "window_bars": s.get("window_bars"), "run_id": s.get("run_id")})
        out["books"][key] = {"raw_eligible_sessions": raw["eligible_count"],
                             "qualified_eligible_sessions": q["eligible_count"] if chain else 0,
                             "ledger_chain_verified": chain, "dates": dates}
    return out


def shared_signals(ledgers: dict) -> list:
    """Each live setup once (shared across books), with every book's decision/quantity."""
    signals: dict = {}
    for key, rows in ledgers.items():
        warm_cut = None
        for r in rows:
            if r.get("type") == "WARMUP_COMPLETE":
                warm_cut = r.get("last_bar")
        for r in rows:
            t = r.get("type")
            if t == "SETUP_TERMINAL":
                ts = (r.get("transitions") or [{}])[-1].get("market_data_ts")
                if warm_cut and ts and ts <= warm_cut:
                    continue   # historical warmup terminal (Oct 2 leak), not a live signal
                sid = r.get("setup_id")
                sig = signals.setdefault(sid, {"signal_id": sid, "family": r.get("family"),
                                               "direction": r.get("direction"), "market_data_ts": ts,
                                               "state": r.get("state"), "reason": r.get("reason"),
                                               "refs": r.get("refs"), "books": {}})
                sig["books"].setdefault(key, {"decision": r.get("state"), "reason": r.get("reason"), "quantity": 0})
            elif t == "CANDIDATE":
                sid = r.get("signal_id")
                sig = signals.setdefault(sid, {"signal_id": sid, "family": r.get("setup_family"),
                                               "direction": r.get("direction"), "market_data_ts": r.get("decision_ts"),
                                               "refs": r.get("refs"), "books": {}})
                sig["books"][key] = {"decision": r.get("decision_state"), "reason": r.get("reason"),
                                     "quantity": (r.get("risk") or {}).get("quantity", 0)}
    return sorted(signals.values(), key=lambda s: s.get("market_data_ts") or "")[-20:]


def diagnostics(root: Path) -> dict:
    base = root / "outputs" / "mes_pilot"
    out = []
    for kind in ("diagnostic_oct02_complete_context", "diagnostic_bridge_check", "diagnostic_synthetic_lifecycle"):
        for d in sorted((base / kind).glob("*"))[-2:] if (base / kind).exists() else []:
            out.append({"kind": kind, "path": str(d), "label": "DIAGNOSTIC / SYNTHETIC - not forward evidence"})
    recon = read_json(base / "repair_2026-10-02" / "oct02_c1_displacement_reconstruction.json")
    complete = sorted((base / "diagnostic_oct02_complete_context").glob("*/oct02_complete_context_diagnostic.json")) \
        if (base / "diagnostic_oct02_complete_context").exists() else []
    cc = read_json(complete[-1]) if complete else None
    return {"runs": out, "oct02_original_reconstruction": recon,
            "oct02_complete_context": None if cc is None else {
                "label": cc.get("label"), "readiness_transitions": cc.get("readiness_transitions"),
                "setups_terminal": [{k: s.get(k) for k in ("family", "direction", "state", "reason")} |
                                    {"displacement": (s.get("refs") or {}).get("displacement"),
                                     "efficiency_ratio": (s.get("refs") or {}).get("efficiency_ratio")}
                                    for s in cc.get("setups_terminal", [])]}}


def make_state(root: Path):
    out = root / "outputs" / "mes_pilot" / "autonomous_paper_portfolios"
    cfg = read_json(root / "config" / "mes_paper_portfolios_v1.json") or {}
    profiles = cfg.get("profiles", {})
    comparison = read_json(out / "portfolio-comparison.json")
    books, ledgers = {}, {}
    for key in BOOKS:
        folder = out / key
        report = read_json(folder / "report.json")
        risk = read_json(folder / "risk-state.json")
        sim = read_json(folder / "simulator-state.json")
        ledger = read_jsonl(folder / "autonomous_paper-ledger.jsonl")
        ledgers[key] = ledger
        candidates = [r for r in ledger if str(r.get("event_type", r.get("type", ""))).upper() == "CANDIDATE"]
        books[key] = {"report": report, "risk": risk, "simulator": sim,
                      "ledger": [r for r in ledger if r.get("type") in ("SESSION_SUMMARY", "SETUP_TERMINAL", "CANDIDATE",
                                                                        "POSITION_CLOSED", "WARMUP_COMPLETE",
                                                                        "CONTEXT_READINESS", "CONTEXT_GAP")],
                      "latest_candidate": candidates[-1] if candidates else None,
                      "config": profiles.get(key.upper(), {})}
    events = read_jsonl(out / "live-feed.jsonl")
    feed_summary = read_json(out / "live-feed-summary.json")
    return {"root": str(root), "output_dir": str(out), "output_exists": out.exists(),
            "comparison": comparison, "books": books, "feed_events": events[-100:],
            "feed_summary": feed_summary, "group_kill_switch": read_json(out / "group-kill-switch.json"),
            "config": cfg, "qualification": qualification(root, ledgers), "shared_signals": shared_signals(ledgers),
            "diagnostics": diagnostics(root)}


class Handler(BaseHTTPRequestHandler):
    root = DEFAULT_ROOT

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/state":
            body = json.dumps(make_state(self.root), default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        elif route == "/" or route == "/index.html":
            try:
                body = (HERE / "paper_dashboard.html").read_bytes()
            except OSError:
                self.send_error(500, "Dashboard page is missing")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            self.send_error(404)
            return
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.send_error(405, "Read-only dashboard")

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Artemis read-only local paper dashboard")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="Runner checkout containing config/ and outputs/ (default: repository root)")
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1",
                        help="Local loopback interface only")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.root = args.root.expanduser().resolve()
    if not Handler.root.is_dir():
        parser.error("--root must name an existing runner checkout")
    print(f"Artemis read-only paper dashboard: http://{args.host}:{args.port}/")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
