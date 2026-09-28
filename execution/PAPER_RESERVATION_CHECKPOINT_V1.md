# Prepared-only paper reservation checkpoint

This adds durable preparation to the existing strategy/pretrade integration.
It is not submission authority, a launch permit, an accounting cash debit, an
installed protective order, or evidence that a paper session ran.

## Lifecycle

Explicit initialization creates EMPTY under a supplied session UUID. Preparation
reloads the existing adapter/performance checkpoint files, compares them to caller
inputs, reruns the pretrade planner and rejects a noneligible risk result. It checks
source checkpoint identities again before writing PREPARED. One prepared reservation
is supported per root/session. Exact retries with the current checkpoint ID are
idempotent; different plans reject, including a changed quantity for the same setup.
There is no automatic expiry release, replacement, cancellation, or submission.

The record retains plan/strategy/order identities, gateway/performance identities,
quantity, modeled reserved cash/loss and preparation/expiry timestamps. The full
plan inputs remain external evidence and must be retained separately. It never
sets `submission_authorized` or `trading_authority` to true.

## Persistence contract

- Exclusive writer lock, expected-checkpoint compare-and-swap, unique temporary
  file, flush/fsync, and atomic replacement follow existing checkpoint conventions.
- UTF-8 JSON loading rejects duplicates, unknown fields, invalid economics,
  incompatible state/session/authority, checksum mismatches and oversized records.
- Missing or corrupt checkpoints block preparation; no automatic reset occurs.
  Initialization refuses an existing file. Operator deletion/reinitialization is
  outside this contract and must never be used to clear an unresolved reservation.
- Before-replace failures retain EMPTY; a failure after replacement can leave
  PREPARED despite a raised exception. Reload and reconcile, never assume rollback.
  Tests inject both cases. Real machine-power-loss durability is not established by
  these injected tests, and directory metadata is not explicitly fsynced here.
- An abandoned writer lock blocks progress and is not automatically removed by a
  later writer. Manual recovery requires inspection, not blind deletion.

The adapter, performance and reservation files are **not a single atomic
transaction**. Re-reading detects observed races, but another writer could change
source state after the last check. The future submitting coordinator must serialize
all session writes and revalidate current source/launch/clock/protective state.
This PREPARED record is never safe to execute on its own.

## Trust and scope

The caller supplies the session identity and trusted pretrade inputs, including
evaluation time. Preparation does not authenticate the owner, read a current clock,
assert workflow ownership, or launch/stop an operational session. The root must be
owner-controlled; symlink/reparse checks are not a hostile-filesystem security
guarantee. Hashes identify data, not authenticate approval. `load()` returns a fresh
decoded evidence dictionary, not a validated executable permit.

The reserve is a retained intent to reserve, not a shared balance lock across
sessions. Multi-session concurrency, aggregate reservations, releases, and durable
submission-state reconciliation are unsupported. Do not deploy simultaneous roots
as a way around the single-reservation boundary.

Tests use temporary synthetic adapter/accounting files and the actual pretrade
planner. They cover reload, unchanged adapter bytes, idempotence, conflicts, stale
CAS, rejected risk, stale/changed source checkpoints, writer locks, corruption,
session mismatch and interrupted-write acknowledgement. No recorder, scheduler,
provider, network, credentials or operational order path was accessed.

Next required work: serialize reservation use with the paper session, implement
protective lifecycle and explicit submission/reconciliation transitions, then
validated V2 fills/costs and a supervised runtime demonstration. This checkpoint
has local regression coverage, not an independent Hermes audit.
