# MES Paper Pilot v1 (`mes_pilot/`)

Implements the autonomous PAPER path from *Trading-bot-code-master.pdf v1.2*
(sha256 `8296c98e…0cbc0fce`) and the Claude Code environment XML v2.1.
Every numeric default lives in `config/mes_paper_pilot_v1.json` with a
provenance label; changing any value changes the config hash recorded on
every ledger record.

**Status:** the paper path works end to end on synthetic data and archive
replay. **No measured strategy win rate exists yet.** The 69.9% figure is the
user-attested *source engine* benchmark, not this bot.

## Operating modes

| Mode | Route | Can reach |
|---|---|---|
| `PAPER_AUTO` (default) | `SimulatorRoute` | in-process `PaperSimulator` only |
| `PROP_MANUAL_ALERTS` | `AlertRoute` | writes advisory alerts to `prop-alerts.jsonl`; no submit/modify/cancel/UI |
| `LIVE_AUTO` | none | always raises `LiveAutoDisabled` (even with the flag set) |

`mes_pilot/tests/test_modes_isolation.py` statically scans the package for
order/UI/network imports; `databento` (read-only market data) is allowed only
in `mes_pilot/live_feed.py`.

## Gap list versus the audit (verified against this checkout, 2026-10-01)

| Audit finding | Verified | Action in this branch |
|---|---|---|
| Adaptive lane hard-codes `paper_execution_permitted: False` (`scripts/run_adaptive_confirmation_lane.py:20-21`) | Yes | Left untouched as a historical research lane; the pilot is a separate explicit-mode path. |
| Strategy output never reaches the paper engine | Yes | `mes_pilot.engine` connects setup → decision → risk → route → simulator → ledger. |
| Baseline cycle always reports `NO_SIGNALS` (`scripts/run_provider_neutral_live_paper_cycle.py`) | Yes | Not used by the pilot; its inactivity is not counted as evidence. File left untouched (it holds Frank's uncommitted edits). |
| 294 adaptive candidates lacked a sweep | Yes, explained | `backtesting/adaptive_confirmation_lane_v1.py` checks a 3-bar internal pattern, not a premarked level; REVERSAL_R1 now requires a sweep of a premarked level. Confirmations were not relaxed. |
| Risk engine / kill switch / ledger work | Yes (777 pre-existing tests pass) | Reused as an outer layer (`risk.pretrade.PreTradeAuthorization`). They are BTC-shaped (percent sizing, fractional size, bps fees), so MES tick/integer dollar-capacity sizing is new in `mes_pilot/risk.py`. |
| 1.5% daily / 3% drawdown caps | Yes (`config/provider_neutral_hard_risk_controls.json`) | Preserved as outer caps; stricter pilot limits apply. |
| No order adapter exists | Not contradicted | None added. |
| Live bar feed | Stream ends 2026-09-22 | Live paper uses `mes_pilot/live_feed.py` (Databento MES.c.0, read-only). |
| Calendar | Forex Factory weekly snapshots only (recent weeks) | Missing coverage blocks new entries; see limitations. |

## Documented discrepancies with existing repository definitions

- `strategy/market_structure.py`: same strict 2-bar pivot, but it records no
  confirmation time; the pilot makes a swing usable only after its second
  right-hand bar closes.
- `strategy/liquidity.py`: sweeps measured in percent (BTC); the pilot uses
  whole ticks (≥1 tick beyond, close back through).
- `risk/risk_engine.py`: minimum stop distance 0.05% (≈15 MES ticks at 7,700)
  would block valid structural stops; the pilot's outer-layer instance uses 0
  and keeps the direction/zero-distance checks. Documented in `risk.py`.

## Pilot rules (proposed paper defaults, not source-engine settings)

See `mes_pilot/setups.py` docstring for REVERSAL_R1 / CONTINUATION_C1, and
the config file for every number. Highlights: 09:30–11:30 ET entries, flat by
11:30, no premarket; H4/H1 aligned bias; fills at the first executable quote
after the confirming M1 close; 60 s intent life, 2-tick drift limit; ≥1.0
gross R:R; 30-min max hold; $50k synthetic equity, $48.5k floor, $100 reserve,
budget = min($100, 5%·C, daily headroom, …) = $70 initially, $150 daily stop,
1 MES, 3 entries/session, pause after 3 consecutive net losses until next
session and a logged review.

## Evidence separation

Each ledger file holds exactly one evidence label (`SYNTHETIC_TEST`,
`HISTORICAL_DEVELOPMENT`, `WALK_FORWARD`, `AUTONOMOUS_PAPER`, `MANUAL_PROP`,
`REPLAY_DIAGNOSTIC_NON_DEPLOYABLE`, …). The report refuses to pool labels and
prints SOURCE ENGINE BENCHMARK / CURRENT BOT RESULT / TARGET separately.
`PROTECTED_OOS` (2026-06-01..2026-08-26) is refused by the replay CLI.

Session classes: `TRADED`, `NO_VALID_SETUP`, `SETUPS_CONFIRMED_BUT_NOT_TAKEN`,
`CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION`, `OPERATIONAL_FAULT`,
`NO_SESSION_DATA_IN_WINDOW`. A calendar outage is never counted as a
no-setup session.

## Commands (PowerShell, from the repository root)

```powershell
# synthetic end-to-end proof (one qualifying trade, one rejected setup)
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py demo

# import Forex Factory snapshots into the pilot calendar (offline files)
.\.venv\Scripts\python.exe scripts\import_mes_pilot_calendar.py

# historical development replay (calendar required -> uncovered sessions abstain)
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py replay --start 2025-09-02 --end 2026-01-30

# diagnostic replay without a calendar (labeled non-deployable)
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py replay --start 2025-09-02 --end 2026-01-30 --calendar-policy diagnostic-not-required

# live PAPER session (needs DATABENTO_API_KEY with GLBX.MDP3 MES live entitlement and a fresh calendar)
.\.venv\Scripts\python.exe scripts\import_mes_pilot_calendar.py --fetch
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py live --mode PAPER_AUTO

# operator controls
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py report --dir outputs\mes_pilot\autonomous_paper
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py kill-switch on --reason "manual stop"
.\.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py review --note "reviewed 3-loss pause"

# tests
.\.venv\Scripts\python.exe -m pytest -q mes_pilot\tests
```

## Known limitations

- **Historical calendar unavailable.** Forex Factory snapshots cover only
  recent weeks; the FMP economic calendar requires a paid plan. Replays with
  the required calendar abstain on uncovered sessions
  (`CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION`); diagnostic replays are
  labeled non-deployable.
- **Replay quotes are modeled** (bar open ± 1 tick); historical bars cannot
  validate spread, queue position or latency.
- **ES bars proxy MES prices** in replay (same index and tick size); live mode
  uses native MES data.
- Commission ($0.85/side), slippage and margin ($2,500) are placeholders until
  the platform's scheduled values are entered.
- `outputs/` and `data/` are git-ignored: ledgers and the imported calendar
  (`data/mes_pilot/calendar/`) are local; re-run the importer on a new machine.
- First diagnostic replay (2025-09-02..2026-01-30, calendar not required,
  non-deployable): 2 positions in 105 sessions, both stopped out. The pilot
  definitions are very selective (most C1 candidates lack a qualifying
  displacement FVG; many R1 sweeps are exceeded before structure confirms).
  Any change to those thresholds must be a new versioned variant, not a retune.
- No prop account profile is configured; prop alerts are blocked unless run
  with `--prop-dry-run`, which marks every alert DRY RUN.
