# File-input paper valuation integration

This is a caller-driven integration of the existing bounded session, clock guard,
closed-BTC-mark validator, durable accounting checkpoint, and dashboard performance
projection. It does not generate signals, fills, orders, or launch a background
process. It is not evidence that supervised trading has started.

## Input boundary

The trusted owner acquisition layer supplies a snapshot root and typed reference
containing a plain relative path, exact SHA-256, and actual source availability
timestamp. No filesystem mtime is substituted for market availability. Missing,
oversized, checksum-mismatched, linked/reparse, non-file, or observed-changing
snapshots reject. Reads are capped at 2 MiB plus one sentinel byte; no silent
truncation or whole-archive tail selection occurs. Existing 1,000-row and candle
freshness limits remain unchanged. A raw archive exceeding those limits needs a
separately validated bounded snapshot producer.

This is not a hostile-filesystem security boundary: handle/path checks detect
ordinary observed changes but do not promise protection from an adversary racing
parent directories or special files. The deployment must own and protect the
root. Hashes identify content, not provider authenticity. Snapshot references are
trusted in-memory inputs, not parsed or authenticated external manifests.

## Session behavior

Each poll reads bounded bytes, obtains injected clock-health evidence, captures
UTC/monotonic time, validates the complete candle snapshot, and forwards only a
valuation mark through the existing clock/session gates. File acquisition latency
is included in the interval since the prior clock observation. No independent
watchdog can interrupt a stalled I/O operation here; on resumption the clock gap
gate rejects it. That external watchdog remains a deployment requirement.

Poll observation time and bar availability are separate. Repeated polling does
not refresh an old bar's age or original mark identity. New bars must be contiguous,
and conflicting retained revisions reject. The cursor is updated only after the
session call returns. It is in-memory, not a recoverable runtime cursor. Preserve
versioned source snapshots externally; this reader does not archive their bytes.

Input failures latch this integration and attempt the existing identity-bound
stop at the last accepted UTC observation. Stop failure is explicitly unconfirmed.
A stop disconnects the paper gateway; it does not fabricate liquidation fills.
The caller must not bypass this integration's latch by reusing underlying APIs.

## Verification

Isolated synthetic files exercise file -> clock -> mark -> checkpoint -> dashboard
performance projection, polling idempotency, a subsequent closed bar, and explicit
stop. Fault tests cover missing/corrupt/future/stale data, bad clock health, loop
gaps, changing files, invalid paths, size limits, and failed stop persistence.
No recorder archive, production clock, scheduler, provider, database, network,
or operational process is accessed by these tests. The dashboard HTTP server is
not launched; its existing verified performance projection is tested directly.

The demonstrated path has zero orders and zero fills. Strategy-to-execution
integration, reviewed source/fee/instrument assumptions, real input acquisition,
external watchdog, and a supervised runtime demonstration remain outstanding.
Local tests are not a Hermes audit, profitability evidence, or deployment approval.
