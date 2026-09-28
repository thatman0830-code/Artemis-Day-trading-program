# Offline protective lifecycle checkpoint

The OCO checkpoint adds explicit initialization, an exclusive writer lock,
compare-and-swap checkpoint identity, bounded duplicate-free JSON, content hashes,
and deterministic replay through the existing V2 protective coordinator.

Restart requires the exact initial accounting/order ledgers, policy, instructions,
arming time and pair IDs. Every action references a caller-retained evidence
payload by its canonical fingerprint. Evaluation payloads contain the actual
OHLC bar, evaluation time and accounting ledger. Acknowledgements contain the
accounting ledger with actual matching V2 fills and explicit cost evidence.
Missing or changed evidence rejects reload; it is never inferred or fabricated.

The journal stores references and results, **not the full evidence payloads**.
A future runtime integration must durably retain those payloads before advancing,
and must verify the current journal before using any returned coordinator. The
loaded coordinator is a replay view; direct mutations are not persisted. Only
`advance` records operations. No runtime launch path is connected to this module.

## Failure semantics

- Initialization never overwrites an existing checkpoint.
- A foreign lock or stale checkpoint blocks a write without clearing another
  owner's lock. A lock abandoned by a crashed process requires owner review.
- `IN_FLIGHT` is flushed and replaced before evaluation begins. Failure after
  this marker leaves reload blocked, even if no evaluation actually occurred.
- A final committed record includes the evidence hash, result and resulting state.
- Failure after final replacement but before acknowledgement requires reload and
  reconciliation; retry with the old checkpoint ID rejects.
- Pending accounting, partial-exit rearm requirements, and flat-position sibling
  cancellation requirements survive replay. This store never cancels or rearms.
- Replay errors, malformed JSON, mismatched identity or absent evidence fail closed.

Files are individually flushed with fsync and atomically replaced on the same
filesystem. This is not a multi-file transaction or a demonstrated power-loss
guarantee; directory metadata durability depends on the OS/filesystem. Hashes do
not authenticate writers or detect replacement of the entire directory with an
older valid checkpoint. The directory must remain owner-controlled; path checks
reject known symlinks/reparse points but are not a hostile-filesystem security
boundary. Maximum journal size is 1 MB and maximum action count is 1,000.

## Verification boundary

Local synthetic regression tests cover full and partial exits, pending accounting,
no-touch cursor replay, missing evidence, lost acknowledgements, failures before
and after replace, stale writers, lock conflicts, corruption, invalid states,
identity mismatch and failed accounting acknowledgement. This is not an
independent Hermes audit or a real recorder/runtime outage drill.

Next integration still requires durable evidence storage, sibling cancellation
and rearm verification, gateway/accounting coordination, and a bounded supervised
launch path. Trading authority remains false. No provider, scheduler, recorder,
credential, broker, wallet or submission system is accessed.
