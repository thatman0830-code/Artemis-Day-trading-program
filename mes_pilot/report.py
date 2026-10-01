"""Daily / cumulative evidence report for one evidence label (never pooled).

Shows three separate figures: SOURCE ENGINE BENCHMARK (user-attested 69.9%,
not this bot), CURRENT BOT RESULT (measured from this ledger only, with a
Wilson 95% interval) and TARGET (70% / 75% objective). Sessions are classified
so a valid no-setup session is never confused with a calendar outage or a
broken pipeline.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from math import sqrt
from pathlib import Path
import json

from mes_pilot.config import PilotConfig


def wilson(wins: int, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(centre - half, 4), round(centre + half, 4)


def build_report(ledger_path: Path, cfg: PilotConfig) -> dict:
    recs = [json.loads(x) for x in Path(ledger_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    labels = {r["evidence_label"] for r in recs}
    if len(labels) > 1:
        raise ValueError(f"ledger mixes evidence labels {labels}; refusing to pool")
    label = labels.pop() if labels else "EMPTY"
    closed = [r for r in recs if r["type"] == "POSITION_CLOSED"]
    sessions = [r for r in recs if r["type"] == "SESSION_SUMMARY"]
    cands = [r for r in recs if r["type"] == "CANDIDATE"]
    wins = sum(1 for r in closed if r["outcome"] == "WIN")
    losses = sum(1 for r in closed if r["outcome"] == "LOSS")
    be = sum(1 for r in closed if r["outcome"] == "BREAKEVEN")
    n = len(closed)
    net = round(sum(r["net_pnl"] for r in closed), 2)
    fees = round(sum(r["fees"] for r in closed), 2)
    rs = [r["net_r"] for r in closed if r.get("net_r") is not None]
    gross_win = sum(r["net_pnl"] for r in closed if r["net_pnl"] > 0)
    gross_loss = -sum(r["net_pnl"] for r in closed if r["net_pnl"] < 0)
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for r in closed:
        equity += r["net_pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    cls = Counter(s["classification"] for s in sessions)
    skip = Counter()
    for s in sessions:
        skip.update(s.get("skip_reasons", {}))
    decisions = Counter(c["decision_state"] for c in cands)
    days = sorted({s["session_date"] for s in sessions})
    span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 if days else 0
    ev = cfg.evidence
    traded_sessions = sum(1 for s in sessions if s["window_bars"] > 0
                          and s["classification"] not in ("CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION", "OPERATIONAL_FAULT",
                                                         "EXCHANGE_HOLIDAY_NO_ENTRIES"))
    return {
        "evidence_label": label,
        "strategy_version": cfg.strategy_version,
        "config_hash": cfg.config_hash,
        "comparison": {
            "SOURCE_ENGINE_BENCHMARK": {"win_rate": ev.source_benchmark, "label": ev.source_label},
            "CURRENT_BOT_RESULT": {"completed_positions": n, "observed_win_rate": round(wins / n, 4) if n else None,
                                   "wilson_95": wilson(wins, n), "evidence_label": label},
            "TARGET": {"minimum": ev.promotion_win_rate, "higher_objective": ev.higher_objective},
        },
        "positions": {"completed": n, "wins": wins, "losses": losses, "breakeven": be,
                      "breakeven_policy": "counted in denominator, reported separately"},
        "pnl": {"net_usd": net, "fees_usd": fees, "mean_net_r": round(sum(rs) / len(rs), 4) if rs else None,
                "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else None,
                "max_closed_drawdown_usd": round(max_dd, 2)},
        "exit_reasons": dict(Counter(r["exit_reason"] for r in closed)),
        "by_setup": {fam: {"positions": sum(1 for r in closed if r["setup_id"] and _fam(cands, r["signal_id"]) == fam)}
                     for fam in ("REVERSAL_R1", "CONTINUATION_C1")},
        "decisions": dict(decisions),
        "sessions": {
            "total": len(sessions),
            "by_classification": dict(cls),
            "calendar_unavailable_operational_limitation": cls.get("CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION", 0),
            "no_valid_setup": cls.get("NO_VALID_SETUP", 0),
            "operational_fault": cls.get("OPERATIONAL_FAULT", 0),
            "no_session_data": cls.get("NO_SESSION_DATA_IN_WINDOW", 0),
            "exchange_holiday": cls.get("EXCHANGE_HOLIDAY_NO_ENTRIES", 0),
        },
        "skip_reasons": dict(skip.most_common()),
        "evidence_progress": {
            "positions": f"{n}/{ev.min_positions}", "eligible_sessions": f"{traded_sessions}/{ev.min_sessions}",
            "calendar_days_spanned": f"{span}/{ev.min_calendar_days}",
            "initial_review_floor_met": n >= ev.min_positions and traded_sessions >= ev.min_sessions and span >= ev.min_calendar_days,
            "note": "Review floor only; not proof of a 70% population win probability.",
        },
        "ledger_chain_verified": _verify(recs),
    }


def _fam(cands, signal_id):
    for c in cands:
        if c["signal_id"] == signal_id:
            return c["setup_family"]
    return None


def _verify(recs) -> bool:
    from hashlib import sha256
    prev = "0" * 64
    for rec in recs:
        body = dict(rec)
        digest = body.pop("hash")
        if body["prev_hash"] != prev:
            return False
        if sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != digest:
            return False
        prev = digest
    return True


def render_text(rep: dict) -> str:
    c = rep["comparison"]
    cur = c["CURRENT_BOT_RESULT"]
    rate = "n/a" if cur["observed_win_rate"] is None else format(cur["observed_win_rate"], ".1%")
    ci = cur["wilson_95"]
    ci_text = f"  (Wilson 95% {ci[0]:.1%}-{ci[1]:.1%})" if ci else ""
    lines = [
        f"=== MES PAPER PILOT REPORT [{rep['evidence_label']}] {rep['strategy_version']} cfg {rep['config_hash'][:12]} ===",
        f"SOURCE ENGINE BENCHMARK : {c['SOURCE_ENGINE_BENCHMARK']['win_rate']:.1%}  ({c['SOURCE_ENGINE_BENCHMARK']['label']})",
        f"CURRENT BOT RESULT      : {cur['completed_positions']} positions, win rate {rate}{ci_text}",
        f"TARGET                  : >= {c['TARGET']['minimum']:.0%} (higher objective {c['TARGET']['higher_objective']:.0%})",
        f"Net P&L ${rep['pnl']['net_usd']}  fees ${rep['pnl']['fees_usd']}  mean net R {rep['pnl']['mean_net_r']}  "
        f"PF {rep['pnl']['profit_factor']}  max DD ${rep['pnl']['max_closed_drawdown_usd']}",
        f"W/L/BE {rep['positions']['wins']}/{rep['positions']['losses']}/{rep['positions']['breakeven']}  exits {rep['exit_reasons']}",
        f"Sessions {rep['sessions']['total']}: {rep['sessions']['by_classification']}",
        f"  calendar-unavailable (operational limitation): {rep['sessions']['calendar_unavailable_operational_limitation']}"
        f" | no valid setup: {rep['sessions']['no_valid_setup']} | operational faults: {rep['sessions']['operational_fault']}",
        f"Decisions {rep['decisions']}",
        f"Top skip reasons {dict(list(rep['skip_reasons'].items())[:8])}",
        f"Evidence progress {rep['evidence_progress']}",
        f"Ledger hash chain verified: {rep['ledger_chain_verified']}",
    ]
    return "\n".join(lines)
