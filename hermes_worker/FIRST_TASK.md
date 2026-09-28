# First Overnight Task: Public BTC Recorder Reliability Audit

Branch: `hermes/recorder-unattended-reliability`

Audit and, only where justified by deterministic tests, improve the public BTC
historical recorder's unattended reliability. Limit scope to DNS failures, TLS
handshake timeouts, bounded reconnects, safe continuation, checksum-safe
interruption recovery, archive resume, gap detection/bounded recovery,
staleness alerts, Windows restart-supervision design (documentation only),
graceful shutdown, and duplicate prevention.

Do not access a live endpoint. Use mocked/local HTTP responses. Do not install a
Windows service or scheduled task. Do not change trading, strategy, risk,
qualification, policy, backtest parameters, dates, or market assumptions. Do
not synthesize candles. Inspect `backtesting/ARCHITECTURE.md`, Phase 1/7A
contracts, `backtesting/recorder.py`, `backtesting/downloader.py`, and their
tests before editing.

Required output: focused tests, all backtesting tests, complete repository tests,
one commit (or a no-change report), and a report conforming to
`hermes_worker/REPORT_TEMPLATE.md`. Stop without merging.

