# V2 Phase 4 Accounting — Codex Reconciliation Report

Source audit commit: `7abb545c313c942f0e90b6e07e73a12d912df147`
Starting checkpoint: `be5e13927f33cefaae69cfd9706f7421764f165e`

The commit is a direct child of the starting checkpoint and adds exactly one adversarial test file
and five audit artifacts. No production file changed. The prior refresh moved from ancestor
`52ff812` to its direct descendant `be5e139`; the commit graph shows no audit-lane history loss.

## Independent review

The original 113 tests used public Phase 4 types and methods; no private helper was imported.
No network, credential, archive, collector, scheduler, exchange, or out-of-sample interface occurs
in the test source. Sixty-seven nonredundant deterministic tests were integrated. Forty-five tests
were rejected as redundant with `test_accounting.py`; the one source-inspection test was rejected
as implementation-coupled and outside Phase 4 accounting behavior. No assertion was weakened and
no production behavior changed.

## Group classification

| Original group | Classification |
|---|---|
| Futures transitions | Rejected as redundant |
| BTC spot | Accepted after correction (3 redundant cases removed) |
| BTC perpetual | Accepted after correction (3 redundant cases removed) |
| Variation settlement | Accepted unchanged |
| Mark/unrealized | Accepted unchanged |
| Cost attribution | Rejected as redundant |
| Margin | Accepted after correction (3 redundant cases removed) |
| Duplicate prevention | Accepted after correction (2 redundant cases removed) |
| Determinism/replay | Accepted after correction (5 redundant cases removed) |
| Residual gates | Accepted after correction (1 redundant case removed) |
| Identity/version/chronology/grid/effective dates | Accepted unchanged |
| Unsupported capabilities | Accepted after correction (float boundary duplicate removed) |
| Accounting reconciliation | Rejected as redundant |
| Event payload validation | Accepted unchanged |
| Position state validation | Accepted unchanged |
| Margin specification validation | Accepted unchanged |
| Fill economics validation | Accepted unchanged |
| BTC logon-task source inspection | Rejected as implementation-coupled |

The original checksum file used Windows checkout bytes for production files, so those values did not
match committed Git-object bytes. `FILE_CHECKSUMS.json` now records independently recomputed
canonical Git-object hashes and the integrated test hash.

## Missing-runtime failures

The audit reported the same 26 `futures_data` failures before and after adding tests. Its retained
test report identifies only gitignored data/output/config evidence and the absent per-worktree venv.
The cited paths are ignored runtime material in the primary repository, and Phase 4 tests were fully
green. No Phase 4 production regression is represented by those failures.

No prohibited runtime state was needed or integrated. Operational state was not queried or changed
during reconciliation.
