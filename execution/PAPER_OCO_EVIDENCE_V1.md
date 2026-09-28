# Durable offline protective action evidence

`DurablePaperOCOReplayV1` composes the existing protective checkpoint with a
content-addressed evidence store. It writes, flushes, validates and decodes each
action payload before advancing the journal. Reload resolves referenced evidence
directly from files: callers no longer supply an in-memory action evidence map.

EVALUATE records contain the exact OHLC bar, evaluation timestamp and accounting
ledger. ACK records contain the reconciled accounting ledger, including fills and
cost facts. Decimal values and UTC timestamps retain their typed representations.
The existing accounting checkpoint codec is reused without expanding its registry;
bar fields have a separate exact schema. No pickle or dynamic type imports exist.

CANCEL_ACK records additionally retain the acknowledged accounting ledger and a
bounded cancellation-event tuple with an exact schema. See
`PAPER_OCO_CANCELLATION_V1.md` for verification rules and terminal states.

Evidence identities must be lowercase SHA-256 strings; files are create-only.
An exact retry validates and flushes existing bytes without rewriting them.
Partial, corrupt, missing, oversized, wrong-authority or mismatched evidence blocks
replay. No repair, fabricated evidence, silent reset or automatic rearm occurs.
Read/write evidence size is limited to 16 MiB per action. Directories must exist
and remain owner-controlled; known linked/reparse paths reject. These checks are
not protection against malicious concurrent filesystem mutation.

## Transaction boundaries

Evidence is retained before journal evaluation. Failure before journal advance
can leave an unreferenced evidence file; stale CAS attempts can do the same. Such
files confer no execution authority and are not scanned or automatically deleted.
A crash while creating evidence can leave a partial file that requires owner
review. The journal retains its existing IN_FLIGHT blocking and exclusive writer
semantics. This is not a multi-file atomic transaction or a demonstrated real
power-loss guarantee; directory metadata durability remains OS/filesystem-dependent.
Checksums detect corruption, not authentic origin or rollback of an entire folder.

The initial arming inputs (policy, instructions, pair IDs, time, initial order and
accounting ledgers) still need to be supplied exactly on reopen. This step persists
action evidence, not a standalone fully serialized runtime session. Replaying a
loaded coordinator directly does not persist new actions: use wrapper `advance`.

## Verification and remaining integration

Synthetic tests cover disk-only replay of complete and partial exits, accounting
acknowledgements, exact retries, missing/partial/tampered evidence, duplicate JSON,
unsupported types, authority violations, fsync failure, stale CAS, invalid paths,
operation mismatch and size limits. No independent Hermes audit or operational
outage drill has been performed for this addition.

Sibling cancellation/rearming verification, durable initial session inputs,
gateway coordination and supervised runtime launch remain outstanding. No
recorder, scheduler, provider, credential, wallet or order-submission path is
accessed. Paper trading has not been started by this work.
