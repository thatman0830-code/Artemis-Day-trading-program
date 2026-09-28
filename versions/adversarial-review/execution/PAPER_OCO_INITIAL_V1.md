# Directory-only protective replay

`create_persisted_protective_session(root, initial=...)` persists the exact original
accounting ledger, order ledger, stop/target identities, execution policy,
instructions/source lineage and arming time. It round-trips and validates these
inputs before creating the journal, under the journal's exclusive writer lock.

`open_persisted_protective_session(root)` reconstructs those inputs from
`oco-initial.json` and verifies the journal and all referenced action evidence.
No in-memory initial configuration or action map is needed to reopen. Existing
constructor-based APIs remain supported; old directories lacking the initial file
are not automatically migrated or reset.

The codec has explicit dataclass/enum allowlists and exact field schemas. It reuses
the accounting codec without modifying its registry. Inputs are bounded to 16 MiB;
duplicate fields, unknown types, authority changes, invalid checksums and excessive
nesting reject. UTC/Decimal types and tuple structure survive serialization. Ledger
integrity and initial pair eligibility are checked through the existing coordinator.

Initialization is create-only. A failed configuration write can leave a partial
initial file with no journal; this requires owner review. It is not automatically
overwritten. An abandoned writer lock blocks reopen and is not removed. A missing,
corrupt or interrupted journal cannot be replaced with an empty ARMED session.

Files are flushed with fsync, but initialization across initial configuration and
journal is not a multi-file atomic transaction. Directory metadata durability is
OS/filesystem dependent; no real power-loss guarantee is claimed. The directory
must remain owner-controlled. Hashes detect corruption, not authentic input origin,
malicious directory replacement or rollback to an older complete session. A reopened
object is not an exclusive runtime owner; later writes retain journal CAS/locking.

Synthetic tests cover directory-only replay through full/partial exits, accounting
and cancellation acknowledgements; initial round-trip; overwrite refusal; malformed
configuration; missing journals; fsync failure; foreign locks and size bounds.

This persists a protective coordinator's inputs, not the entire bounded paper
driver's budgets, permits or strategy state. Duplicate-safe replacement handoff,
unprotected-interval assessment, trusted runtime acquisition and supervised launch
remain outstanding. No paper session, recorder, scheduler or provider is operated.
