"""MES paper pilot command line (PAPER_AUTO by default; LIVE_AUTO is refused).

  demo                      synthetic end-to-end: one qualifying trade, one rejected setup
  replay --start --end      chronological replay of the ES 1-minute archive (MES-sized fills)
  live                      bounded live PAPER session via the read-only Databento feed
  report --dir              evidence report for one ledger directory
  kill-switch on|off        persistent kill switch for a run directory
  review --note             log the review that clears a 3-consecutive-loss pause
  clear-block --note        operator reconciliation after an emergency/mismatch
  alert-resolve             record Frank's actual decision for a manual prop alert

All outputs go under outputs/mes_pilot/ (relative to the repository).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mes_pilot.bars import ET, UTC, load_archive_sessions  # noqa: E402
from mes_pilot.config import load_config  # noqa: E402
from mes_pilot.engine import PilotEngine  # noqa: E402
from mes_pilot.events import EventCalendar  # noqa: E402
from mes_pilot.modes import LiveAutoDisabled, OperatingMode  # noqa: E402
from mes_pilot.report import build_report, render_text  # noqa: E402

OUT = ROOT / "outputs" / "mes_pilot"
CAL_DIR = ROOT / "data" / "mes_pilot" / "calendar"
ARCHIVES = [ROOT / "data" / "backtests" / "es_nq_pass_b_archive_3" / "ES", ROOT / "data" / "futures_forward" / "ES"]


def _run_dir(kind: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / kind / stamp
    path.mkdir(parents=True, exist_ok=False)
    return path


def _print_report(directory: Path, cfg) -> dict:
    ledgers = sorted(directory.glob("*-ledger.jsonl"))
    rep = {}
    for ledger in ledgers:
        rep = build_report(ledger, cfg)
        print(render_text(rep))
        (directory / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return rep


# ---------------------------------------------------------------------------------- demo
def cmd_demo(args):
    from mes_pilot import synthetic as S

    cfg = load_config(overrides={"strategy": {"volatility_filter_enabled": False}})
    days = [date(2026, 9, 14) + timedelta(days=i) for i in range(4)]
    calendar = EventCalendar([], set(days), "SYNTHETIC_COVERAGE_NO_EVENTS")
    base = _run_dir("synthetic_demo")
    until = datetime.combine(days[-1], time(9, 0), ET).astimezone(UTC)
    history = S.history(days, until)
    results = {}
    for scenario in ("qualifying", "rejected"):
        out = base / scenario
        eng = PilotEngine(cfg, out_dir=out, evidence_label="SYNTHETIC_TEST", data_source=f"mes_pilot.synthetic:{scenario}",
                          calendar=calendar, calendar_policy_label="SYNTHETIC")
        for bar in history:
            eng.process_bar(bar)
        x, target_rel = S.choose_geometry(eng, until, history[-1].close, max(S.SCENARIO_DEPTH.values()))
        for bar in S.demo_segment(days[-1], x, history[-1].close, S.SCENARIO_DEPTH[scenario], target_rel):
            eng.process_bar(bar)
        eng.finish()
        print(f"\n##### SCENARIO {scenario.upper()} (swept level {x}, target +{target_rel} pts) -> {out}")
        _summarize_ledger(eng)
        results[scenario] = str(out)
    print(f"\nSynthetic demo ledgers: {base}")
    return results


def _summarize_ledger(eng):
    for rec in eng.ledger.records():
        t = rec["type"]
        if t == "CANDIDATE":
            risk = rec.get("risk") or {}
            print(f"  CANDIDATE {rec['setup_family']} {rec['direction']} decision={rec['decision_state']} reason={rec['reason']}"
                  f" entry_ref={rec['entry_ref']} stop={rec['stop']} target={rec['target']} RR={rec['gross_reward_risk']}"
                  f" qty={risk.get('quantity')} budget={risk.get('budget')} unit_loss={risk.get('unit_loss')}"
                  f" stop_ticks={risk.get('stop_ticks')}")
        elif t in ("INTENT", "ORDER", "FILL", "POSITION_OPENED"):
            keep = {k: rec.get(k) for k in ("intent_id", "status", "reason", "fill_price", "filled_qty", "entry_price",
                                             "stop", "target", "quantity", "slippage_ticks", "quote_source") if rec.get(k) is not None}
            print(f"  {t} {keep}")
        elif t == "POSITION_CLOSED":
            print(f"  POSITION_CLOSED exit={rec['exit_reason']} entry={rec['entry_price']} exit_px={rec['exit_price']}"
                  f" gross=${rec['gross_pnl']} fees=${rec['fees']} net=${rec['net_pnl']} netR={rec['net_r']}"
                  f" outcome={rec['outcome']} hold={rec['hold_minutes']}m MAE={rec['mae_ticks']}t MFE={rec['mfe_ticks']}t")
        elif t == "SESSION_SUMMARY":
            print(f"  SESSION {rec['session_date']} classification={rec['classification']} positions={rec['positions']}"
                  f" net=${rec['net_pnl']} skips={rec['skip_reasons']}")
    print(f"  ledger: {eng.ledger.path}  hash-chain verified: {eng.ledger.verify_chain()}")


# ---------------------------------------------------------------------------------- replay
def cmd_replay(args):
    overrides = {}
    diag = args.calendar_policy == "diagnostic-not-required"
    if diag:
        overrides = {"events": {"required": False}}
    cfg = load_config(overrides=overrides or None)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    sp = cfg.splits
    if not (end < sp.protected_oos[0] or start > sp.protected_oos[1]):
        raise SystemExit(f"Refusing: {start}..{end} overlaps PROTECTED_OOS {sp.protected_oos}; it stays untouched until its planned release.")
    labels = {sp.label_for(start), sp.label_for(end)}
    if len(labels) != 1:
        raise SystemExit(f"Range spans evidence segments {labels}; replay one segment at a time.")
    label = labels.pop()
    if diag:
        label = "REPLAY_DIAGNOSTIC_NON_DEPLOYABLE"
    sessions = load_archive_sessions(ARCHIVES, start=start - timedelta(days=400), end=end)
    warm = [s for s in sessions if s.session_date < start and not (sp.protected_oos[0] <= s.session_date <= sp.protected_oos[1])]
    warm = warm[-cfg.strategy.volatility_sessions:]
    run = [s for s in sessions if start <= s.session_date <= end]
    calendar = EventCalendar.load_dir(CAL_DIR) if CAL_DIR.exists() else EventCalendar.empty()
    out = _run_dir(f"replay_{label.lower()}")
    eng = PilotEngine(cfg, out_dir=out, evidence_label=label, calendar=calendar,
                      data_source=f"ES 1m archive (MES price proxy) {start}..{end}; warmup {len(warm)} sessions",
                      calendar_policy_label="DIAGNOSTIC_NOT_REQUIRED" if diag else "REQUIRED")
    eng.warmup = True
    for s in warm:
        for bar in s.bars:
            eng.process_bar(bar)
    eng.end_warmup()
    for s in run:
        for bar in s.bars:
            eng.process_bar(bar)
    eng.finish()
    print(f"Replay {start}..{end}: {len(run)} sessions, warmup {len(warm)}; ledger {eng.ledger.path}")
    _print_report(out, cfg)


# ---------------------------------------------------------------------------------- live
def cmd_live(args):
    cfg = load_config()
    if args.mode == OperatingMode.LIVE_AUTO.value:
        raise LiveAutoDisabled("LIVE_AUTO is disabled in this version; no personal-live adapter is qualified.")
    from mes_pilot import live_feed  # lazy: databento only needed here

    # Live: point-in-time and a snapshot retrieved within the last 7 days.
    calendar = EventCalendar.load_for_live(CAL_DIR) if CAL_DIR.exists() else EventCalendar.empty()
    label = "AUTONOMOUS_PAPER" if args.mode == "PAPER_AUTO" else "MANUAL_PROP"
    out = OUT / label.lower()
    eng = PilotEngine(cfg, out_dir=out, evidence_label=label, mode=args.mode, quote_mode="LIVE", calendar=calendar,
                      data_source="Databento GLBX.MDP3 MES.c.0 live (read-only)",
                      allow_unconfigured_prop_dry_run=args.prop_dry_run)
    # Warm up structure and volatility history from the archive (most recent sessions, never protected OOS).
    sp = cfg.splits
    hist = [s for s in load_archive_sessions(ARCHIVES, start=date.today() - timedelta(days=400))
            if not (sp.protected_oos[0] <= s.session_date <= sp.protected_oos[1])]
    eng.warmup = True
    for s in hist[-cfg.strategy.volatility_sessions:]:
        for bar in s.bars:
            eng.process_bar(bar)
    eng.end_warmup()
    live_feed.run_session(eng, cfg)
    eng.finish()
    _print_report(out, cfg)


# ---------------------------------------------------------------------------------- admin
def _engine_for_dir(directory: Path, cfg):
    led = sorted(directory.glob("*-ledger.jsonl"))
    label = led[0].name.replace("-ledger.jsonl", "").upper() if led else "AUTONOMOUS_PAPER"
    return PilotEngine(cfg, out_dir=directory, evidence_label=label, data_source="admin", calendar=EventCalendar.empty())


def cmd_report(args):
    _print_report(Path(args.dir), load_config())


def cmd_kill(args):
    eng = _engine_for_dir(Path(args.dir), load_config())
    eng.set_kill_switch(args.state == "on", args.reason)
    print(f"kill switch {'ACTIVE' if args.state == 'on' else 'cleared'} for {args.dir}")


def cmd_review(args):
    eng = _engine_for_dir(Path(args.dir), load_config())
    res = eng.risk.log_review(args.note)
    eng.ledger.append("REVIEW_LOGGED", note=args.note, **res)
    print(res)


def cmd_clear(args):
    eng = _engine_for_dir(Path(args.dir), load_config())
    eng.clear_block(args.note)
    print(f"entries blocked: {eng.blocked}")


def cmd_alert_resolve(args):
    from mes_pilot.alerts import AlertOutbox

    box = AlertOutbox(Path(args.dir) / "prop-alerts.jsonl")
    print(box.resolve(args.alert_id, args.decision, actual_fill_price=args.fill_price, actual_fill_time=args.fill_time,
                      actual_qty=args.qty, actual_stop=args.stop, actual_target=args.target, note=args.note))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo").set_defaults(fn=cmd_demo)
    r = sub.add_parser("replay")
    r.add_argument("--start", required=True)
    r.add_argument("--end", required=True)
    r.add_argument("--calendar-policy", choices=["required", "diagnostic-not-required"], default="required")
    r.set_defaults(fn=cmd_replay)
    lv = sub.add_parser("live")
    lv.add_argument("--mode", choices=["PAPER_AUTO", "PROP_MANUAL_ALERTS", "LIVE_AUTO"], default="PAPER_AUTO")
    lv.add_argument("--prop-dry-run", action="store_true", help="emit alerts marked DRY RUN while no prop profile is configured")
    lv.set_defaults(fn=cmd_live)
    rp = sub.add_parser("report")
    rp.add_argument("--dir", required=True)
    rp.set_defaults(fn=cmd_report)
    k = sub.add_parser("kill-switch")
    k.add_argument("state", choices=["on", "off"])
    k.add_argument("--dir", default=str(OUT / "autonomous_paper"))
    k.add_argument("--reason", default="operator")
    k.set_defaults(fn=cmd_kill)
    rv = sub.add_parser("review")
    rv.add_argument("--dir", default=str(OUT / "autonomous_paper"))
    rv.add_argument("--note", required=True)
    rv.set_defaults(fn=cmd_review)
    cb = sub.add_parser("clear-block")
    cb.add_argument("--dir", default=str(OUT / "autonomous_paper"))
    cb.add_argument("--note", required=True)
    cb.set_defaults(fn=cmd_clear)
    ar = sub.add_parser("alert-resolve")
    ar.add_argument("--dir", default=str(OUT / "manual_prop"))
    ar.add_argument("--alert-id", required=True)
    ar.add_argument("--decision", required=True, choices=["ENTERED", "SKIPPED", "EXPIRED", "MISSED"])
    ar.add_argument("--fill-price", type=float)
    ar.add_argument("--fill-time")
    ar.add_argument("--qty", type=int)
    ar.add_argument("--stop", type=float)
    ar.add_argument("--target", type=float)
    ar.add_argument("--note", default="")
    ar.set_defaults(fn=cmd_alert_resolve)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    main()
