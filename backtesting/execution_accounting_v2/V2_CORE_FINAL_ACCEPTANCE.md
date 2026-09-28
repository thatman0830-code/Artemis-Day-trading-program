# V2 Core Final Acceptance

V2 Core is accepted for deterministic offline research and untouched-OOS
validation, subject to `V2_CORE_LIMITATIONS.md`.

## Reviewed phases

1. Immutable contracts, evidence, effective-dated specifications, validation.
2. Deterministic order lifecycle ledger and quantity conservation.
3. Conservative finalized-OHLC execution with source lineage and no look-ahead.
4. Exact instrument accounting, costs, settlement, margin and immutable facts.
5. Advisory pre/post risk, verified sessions and later-bar flatten instructions.
6. Separate rollover legs, funding boundaries, deterministic event priority.
7. Reconciliation, partitioned analytics, stress, ruin and advisory promotion.

## Acceptance properties

Records are frozen and content-addressed; economic values are finite Decimal;
timestamps are UTC and chronologically gated; market/instrument/contract/session/
version identities remain isolated; duplicate economic facts reject; replay and
checkpoints are deterministic and tamper-evident; missing authority fails closed.

Core v1 remains separately versioned and reproducible. V2 does not reinterpret
or overwrite v1 results. V2 outputs are offline research evidence only.

No analytic result guarantees profitability or authorizes deployment, trading,
account mutation, order submission, or operational control.
