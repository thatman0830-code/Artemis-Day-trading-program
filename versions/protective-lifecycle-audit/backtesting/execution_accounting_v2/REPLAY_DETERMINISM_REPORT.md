# Phase 2 Replay and Determinism Report

- Events carry UTC logical time, positive global sequence, expected order version, source identity,
  exact instrument identity, and deterministic content fingerprint.
- Event order is time, declared priority, then event identity. Locale, current time, filesystem order,
  dictionary order, thread scheduling, and randomness are absent.
- Transition IDs hash ledger version, event, ordinal, states, all three quantities, reason, and source.
- Quantity conservation is checked after every transition and during integrity verification.
- Exact duplicate events are idempotent; conflicting reuse rejects.
- Checkpoints contain the immutable ledger and fingerprint. Resume verifies the checkpoint first.
- Replaying checkpoint events from root intents produces byte-identical serialization and fingerprint.
- Ledger, event index, event contents, snapshots, transitions, or checkpoint tampering is detected.
- V1/mixed ledger versions reject. Synthetic Phase 1 facts cannot gain production eligibility here.

No wall-clock, provider, network, credential, archive, collector, broker, or trading state participates
in replay.
