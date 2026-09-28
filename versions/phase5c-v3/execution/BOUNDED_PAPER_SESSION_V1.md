# Bounded offline paper-session driver

Base checkpoint: `0087b34b4df07066c54b1e3d6046a57bbf561ced`.

## Implemented boundary

`BoundedPaperSessionV1` is a caller-driven API around the persisted paper
workflow. It does not start a process, generate orders/fills, collect prices,
connect to a broker, or claim trading authority.

- `start(now)` requires strict launch-evidence decoding, current identity-checked
  owner confirmation, checkpoint/limit agreement, eligible gate results, fresh
  BTC spot accounting, a healthy empty adapter, and an empty session directory.
- `step(cycle, verified_fill=..., closed_mark=...)` rechecks launch evidence and
  confirmation, checks chronology/deadline, and enforces five command attempts,
  100 per-order notional and 200 cumulative reserved notional. These defaults
  are inherited from the existing launch-decision module. Notional is in the
  accounting instrument's quote currency, not a claim of dollar equivalence.
- Fill evidence must bind to an order introduced in this session, including side
  and time. Actual cumulative fill notionals are bounded separately. Marked
  position plus outstanding order exposure is checked after accounting updates;
  a breach preserves the observed mark and halts instead of inventing a close.
- Commands/events cannot be replayed through the driver. No automatic recovery
  or reconciliation-observation input is supported. This avoids the known bridge
  limitation on replay after a genuinely changed gateway snapshot.
- `stop(now)` writes the identity-bound stop request and verifies disconnected,
  STOPPED state and reconciled performance. It does not liquidate positions or
  fabricate exit fills. Existing owner stop requests are honored by the workflow.
- Failure attempts a durable halt, releases ownership, and makes this driver
  inactive. Failure to persist the halt is explicitly reported as unconfirmed.

## Deliberate limits and remaining work

This is not an autonomous session runner. Time is supplied by the caller and
checked at API boundaries; there is no background timer to stop a stalled caller.
The caller must supply trustworthy current UTC time and enforce a watchdog.
The deadline is the earliest of session duration, initial permit expiry, and
owner-confirmation expiry. Fresh launch evidence is reloaded each step; a stale
BTC heartbeat blocks further processing even before that deadline.

Launch evidence and its supplied checkpoint identify the intended repository;
this module does not independently inspect Git or runtime processes. Source
collection and fresh owner authorization remain external prerequisites.

The caller must supply genuine closed-bar price lineage, explicit costs, and
validated simulated fill economics. A `PriceEvidenceV2` object alone does not
prove bar closure. The driver never reads the recorder archive or synthesizes
evidence to fill this gap. BTC perpetuals, ES/NQ, live execution, automatic
restarts, cross-process budget recovery, and paper profitability claims are out
of scope.

The existing dashboard reads adapter-checkpoint.json, performance-checkpoint.json,
and latest-health.json under the chosen session root and refreshes every five
seconds. It has not been launched by these tests.

## Tests

All tests use temporary fixtures. Coverage includes submission/fill/mark/stop,
mark-driven exposure breach, gate blocks, instrument and order limits, cumulative
reservations, command budget, chronology/expiry, owner stop, duplicate command,
tampered confirmation, directory reuse refusal, and stop-write failure.

Additional local review coverage: stale heartbeat on a later step; corrupt evidence
reloaded after startup; wrong-side, unknown-order, future, and excessive-notional
fills rejected before gateway mutation; expired confirmation refusal; stop allowed
after permit expiry; explicit step/stop halt-write failure; automatic recovery
input refusal. Focused driver verification: 27 passed.

Status: locally reviewed offline implementation; no independent Hermes audit of
this driver is claimed. Not authorization to launch a session. A trusted runtime
clock/watchdog and source-evidence/strategy integration are still required.
