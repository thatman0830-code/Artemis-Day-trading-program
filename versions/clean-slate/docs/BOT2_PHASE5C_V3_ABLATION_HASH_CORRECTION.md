# Phase 5C v3 Ablation Hash Correction

Date: 2026-09-22
Source of truth: canonical runtime-generated ablation contracts from `bot2.phase5c_v3.experiment_controls.create_ablation_contract`, bound to the verified frozen manifest. Historical review/directive documents remain unchanged.

## Runtime-recalculated SHA-256 values

| Frozen ablation | Canonical runtime SHA-256 |
|---|---|
| `ALL` | `482acdb0217aa30f94a11452c3ccbfe560d5f6828693c7cf16c20d073836992d` |
| `MINUS_CROSS_MARKET` | `faf62abb5fec0cba7ac9a98f6ffe70411dd72b95fa108992a8e8ce4b9f575e39` |
| `MINUS_VWAP` | `9e188e4f9359e73d894ac51d3b8921226f4cf0d443f35df0313696f33d7e113e` |
| `MINUS_VOLUME` | `5b5b369e8e8fc3a504e9a0aa843af8f05512672977a0d1db430ddda5781f5494` |
| `MINUS_VOLATILITY` | `e6b02f29b37321d9c725205f32b5cbe2647260d010ed8531687a811da509452a` |
| `MINUS_SESSION_TIME` | `b16514481934a4c20c3b6cdf577846edbf2b9948bbafae92e98643cfae6204ae` |

## Append-only correction

Two values in the Phase 5C-X prose directive were transcription mistakes, not runtime/specification defects:

- `ALL`: prose `...3ccbf560...` was wrong; runtime is `...3ccbfe560...`.
- `MINUS_CROSS_MARKET`: prose `...f6fffe704...` was wrong; runtime is `...f6ffe704...`.

No runtime masks, canonical ablation definitions, frozen manifest, or historical review documents were altered to match the typos. Independent runtime recalculation on this branch produced all six full hashes above. Canonical manifest SHA-256 remains `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
