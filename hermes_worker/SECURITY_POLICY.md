# Hermes Overnight Worker Security Policy

Status: fail-closed. This policy does not authorize trading.

## Boundary

Hermes must run inside a whole-process OS sandbox. A native host process and
Hermes' in-process approval or allowlist features are not security boundaries.
The sandbox receives only the dedicated sanitized clone, a dedicated Hermes
home, and `hermes_worker/reports`. It never receives the owner workspace,
Windows home, Docker socket, browser profile, Credential Manager, `.env*`,
`data/`, `outputs/`, logs from unrelated programs, wallet files, or the
canonical Obsidian vault.

The worker branch must match `hermes/*`. The worker may commit there, but must
not merge, push, force-push, rebase, rewrite history, alter `main`, install a
service/scheduled task, or modify the owner workspace.

## Prohibited authority

No private keys, seed phrases, wallets, account/API/broker credentials,
authenticated account APIs, order submission, mainnet/testnet execution,
signing, risk authorization, strategy optimization, policy changes, live
trading, browser password stores, personal documents, or canonical Obsidian
modification. Do not invoke modules under `exchange/`, `execution/`, or `risk/`
except static read-only inspection and tests; never instantiate exchange/order
clients. Unknown state fails closed.

No changes to owner-approved R, win-rate, risk, stop, target, displacement, or
strategy rules. No parameter tuning, date selection after results, test/data
validation weakening, material deletion, data synthesis, or package install.

## Required task gates

Every task states its objective, contracts inspected, assumptions, budget, and
branch; adds or updates tests; runs focused and complete relevant suites; logs
commands/tool calls/network destinations/files/commits/results/errors; writes a
Markdown report; lists unresolved risks; and stops without merging. Ambiguity,
budget exhaustion, unavailable dependencies, or a prohibited operation means
stop and report.

