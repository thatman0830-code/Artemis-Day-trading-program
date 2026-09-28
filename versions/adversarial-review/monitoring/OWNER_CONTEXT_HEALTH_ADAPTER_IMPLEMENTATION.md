# Owner-Context Operational-Health Adapter V1

## Outcome

`monitoring.owner_context_health_adapter` is a pure, read-only translation boundary. It consumes only dependency-injected, sanitized facts and produces immutable `ComponentObservationV1` records plus the existing advisory `OperationalReadinessV1` decision.

The adapter contains no Windows API reader, process controller, provider client, network client, credential reader, archive writer, or trading interface. It cannot infer task installation from sandbox visibility and accepts task evidence only when explicitly marked `OWNER_CONTEXT`.

## Public contract

- `ComponentIdentityV1`: exact expected task/action/single-instance/restart identity.
- `SanitizedComponentFactsV1`: collected task, heartbeat, restart, gap, integrity, storage, clock, incident, timestamp, and source-hash facts.
- `SanitizedFactsReader`: dependency-injected read protocol.
- `adapt_owner_context_health`: deterministic fail-closed adapter and evaluator.
- `AdaptedOwnerContextHealthV1`: content-addressed provenance envelope containing observations and readiness.

Only `btc-recorder` and `es-nq-recorder` are accepted. BTC requires its explicit `Running` contract. ES/NQ may use `Ready` only when its supplied identity explicitly permits that state. Neither state is sufficient without heartbeat, singleton, gap, integrity, storage, clock, restart, and incident validation.

## Boundaries

All output has `trading_authority=false`. The result is operational advice only and cannot start, stop, enable, disable, install, remove, or alter a task or process. No `.env` or credential-named material is read by this implementation.

## Determinism and auditability

UTC collection timestamps and SHA-256 source-file hashes are mandatory. Observation and report identities are SHA-256 content addresses over canonical JSON-compatible values. Inputs and outputs are frozen dataclasses; repeated evaluation of identical facts is byte-logically deterministic.

## Verification

Focused tests cover healthy translation, component-specific task state, all critical readiness controls, sandbox visibility rejection, stale/future/cross-component facts, exact identity and policy matching, immutable records, provenance, and deterministic replay.
