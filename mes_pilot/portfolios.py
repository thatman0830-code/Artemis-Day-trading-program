"""Three isolated, paper-only MES accounts consuming the same market events.

The strategy, calendar and feed are shared. Only risk budgets differ. This
compares sizing policies; it does not create three independent strategies or
grant any live/prop execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from collections import Counter
import json

from mes_pilot.config import ROOT, PilotConfig, load_config
from mes_pilot.engine import PilotEngine
from mes_pilot.report import build_report

DEFAULT_PORTFOLIOS = ROOT / "config" / "mes_paper_portfolios_v1.json"
NAMES = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")
RISK_KEYS = {"max_contracts", "max_new_trade_budget_usd", "capacity_fraction", "net_daily_stop_usd"}


def load_portfolio_configs(path: Path = DEFAULT_PORTFOLIOS) -> dict[str, PilotConfig]:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("schema_version") != "mes-paper-portfolios-v1" or spec.get("paper_only") is not True:
        raise ValueError("invalid or non-paper portfolio specification")
    if set(spec.get("profiles", {})) != set(NAMES):
        raise ValueError("exactly the three named paper portfolios are required")
    start = float(spec["starting_equity_usd"])
    floor = float(spec["initial_floor_usd"])
    allowance = float(spec["drawdown_allowance_usd"])
    reserve = float(spec["execution_reserve_usd"])
    if start != 100000 or allowance <= 0 or abs(start - floor - allowance) > 1e-9:
        raise ValueError("100K starting equity and a coherent initial trailing floor are required")
    if reserve < 0 or reserve >= allowance:
        raise ValueError("execution reserve must be nonnegative and below the drawdown allowance")
    configs = {}
    spec_hash = sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    for name in NAMES:
        limits = spec["profiles"][name]
        if set(limits) != RISK_KEYS:
            raise ValueError(f"{name} may override risk limits only")
        overrides = {"risk": {
            "synthetic_starting_equity_usd": start,
            "static_synthetic_floor_usd": floor,
            "synthetic_floor_model": "INTRADAY_TRAILING",
            "synthetic_drawdown_allowance_usd": allowance,
            "execution_reserve_usd": reserve,
            **limits,
        }, "paper_portfolio": {"id": name, "spec_hash": spec_hash,
                               "status": spec["model_status"]}}
        cfg = load_config(overrides=overrides)
        if cfg.mode != "PAPER_AUTO" or cfg.live_auto_enabled:
            raise ValueError("paper portfolios cannot enable a broker or prop route")
        configs[name] = cfg
    # Only risk and portfolio identity can differ across the three books.
    reference = configs[NAMES[0]].raw
    for cfg in configs.values():
        for key in ("instrument", "costs", "session", "events", "data", "strategy", "accumulation"):
            if cfg.raw[key] != reference[key]:
                raise ValueError(f"portfolio {key} mismatch")
    return configs


class PortfolioGroup:
    def __init__(self, configs: dict[str, PilotConfig], *, out_dir: Path, calendar,
                 data_source: str, quote_mode: str = "LIVE", evidence_label: str = "AUTONOMOUS_PAPER"):
        if set(configs) != set(NAMES):
            raise ValueError("three paper portfolios required")
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.calendar = calendar
        self.engines = {}
        for name in NAMES:
            cfg = configs[name]
            if cfg.mode != "PAPER_AUTO" or cfg.live_auto_enabled:
                raise ValueError("portfolio group is paper-only")
            path = self.out_dir / name.lower()
            path.mkdir(parents=True, exist_ok=True)
            identity = path / "portfolio-identity.json"
            expected = {"portfolio": name, "config_hash": cfg.config_hash}
            if identity.exists() and json.loads(identity.read_text(encoding="utf-8")) != expected:
                raise ValueError(f"{name} persisted account belongs to a different config; refusing to reset it")
            if not identity.exists():
                identity.write_text(json.dumps(expected, indent=1), encoding="utf-8")
            self.engines[name] = PilotEngine(cfg, out_dir=path, evidence_label=evidence_label,
                                             data_source=data_source, quote_mode=quote_mode, calendar=calendar)

    def start_warmup(self):
        for eng in self.engines.values():
            eng.warmup = True

    def end_warmup(self):
        for eng in self.engines.values():
            eng.end_warmup()

    def process_bar(self, bar, live_quote=None, **kw):
        """Same bar (and context/continuity/source flags) to every isolated book."""
        for eng in self.engines.values():
            eng.process_bar(bar, live_quote=live_quote, **kw)

    def attest_zero_trade(self, minute_start, evidence):
        for eng in self.engines.values():
            eng.attest_zero_trade(minute_start, evidence)

    def record_feed_event(self, kind, **fields):
        for eng in self.engines.values():
            eng.record_feed_event(kind, **fields)

    @property
    def last_bar(self):
        return next(iter(self.engines.values())).last_bar

    def process_quote(self, quote):
        for eng in self.engines.values():
            eng.process_quote(quote)

    def finish(self):
        for eng in self.engines.values():
            eng.finish()

    def comparison(self) -> dict:
        reports = {}
        candidates = {}
        terminal = {}
        terminal_reasons = {}
        decision_reasons = {}
        for name, eng in self.engines.items():
            report = build_report(eng.ledger.path, eng.cfg)
            (eng.out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
            reports[name] = report
            candidate_records = eng.ledger.records("CANDIDATE")
            terminal_records = eng.ledger.records("SETUP_TERMINAL")
            candidates[name] = [r["signal_id"] for r in candidate_records]
            terminal[name] = [r["setup_id"] for r in terminal_records]
            terminal_reasons[name] = dict(Counter(r.get("reason") or "UNSPECIFIED" for r in terminal_records))
            decision_reasons[name] = dict(Counter(r.get("reason") or "ACCEPTED" for r in candidate_records))
        aligned = (all(candidates[n] == candidates[NAMES[0]] for n in NAMES[1:]) and
                   all(terminal[n] == terminal[NAMES[0]] for n in NAMES[1:]))
        comparison = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "paper_only": True,
            "same_signal_ids": aligned,
            "shared_signal_count": len(candidates[NAMES[0]]),
            "setup_terminal_reasons": terminal_reasons[NAMES[0]],
            "portfolio_results": {
                name: {"config_hash": self.engines[name].cfg.config_hash,
                       "risk_limits": {k: self.engines[name].cfg.raw["risk"][k] for k in RISK_KEYS},
                       "completed_positions": rep["positions"]["completed"],
                       "eligible_sessions": rep["sessions"]["eligible_dates"],
                       "session_summary_rows": rep["sessions"]["summary_rows"],
                       "calendar_days_spanned": rep["sessions"]["eligible_calendar_days_spanned"],
                       "mixed_ineligible_dates": rep["sessions"]["mixed_ineligible_dates"],
                       "observed_win_rate": rep["comparison"]["CURRENT_BOT_RESULT"]["observed_win_rate"],
                       "net_pnl_usd": rep["pnl"]["net_usd"],
                       "mean_net_r": rep["pnl"]["mean_net_r"],
                       "skip_reasons": rep["skip_reasons"],
                       "candidate_decision_reasons": decision_reasons[name],
                       "paper_floor_usd": self.engines[name].risk.state.floor_usd,
                       "paper_peak_equity_usd": self.engines[name].risk.state.peak_equity,
                       "paper_floor_breached": self.engines[name].risk.state.floor_breached}
                for name, rep in reports.items()},
            "qualification": {name: rep.get("qualification") for name, rep in reports.items()},
            "latest_session_status_layers": {
                name: (self.engines[name].ledger.records("SESSION_SUMMARY") or [{}])[-1].get("status_layers")
                for name in NAMES},
            "interpretation": "Same signals compare sizing and risk only. No win-rate target is presumed achieved.",
        }
        (self.out_dir / "portfolio-comparison.json").write_text(json.dumps(comparison, indent=1), encoding="utf-8")
        if not aligned:
            raise RuntimeError("paper portfolio signal streams diverged; comparison is invalid")
        return comparison
