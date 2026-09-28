# ES/NQ Forward Archive Integrity

The read-only whole-archive verifier requires exact one-to-one inventories across
raw, normalized, pending, manifest, and checkpoint artifacts for both ES and NQ.
It validates identities, relative paths, schema versions, SHA-256 links, byte and
row counts, strictly increasing timestamps, accumulated volume, and nonnegative
missing-minute classifications. Unexpected or missing artifacts fail closed.

The current retained archive verifies as 4 sessions, 5,520 normalized rows, 20
linked artifacts, and zero unresolved missing minutes. This establishes integrity
of retained bytes and lineage; it does not establish completeness beyond the
configured eligible sessions, market accuracy, profitability, or trading authority.
