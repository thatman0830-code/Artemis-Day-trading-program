# ES/NQ Historical Backfill Owner Decision Review

Date: 2026-08-26  
Review mode: offline, read-only artifact inspection  
Decision: **BLOCKED — the metadata inventory is valid evidence but is not an executable backfill plan**

## Integrity and security

All 20 retained metadata bodies (10 ES and 10 NQ) recompute to the SHA-256
values in their request manifests. The preflight made zero aggregate requests,
started no backfill or recorder, and recorded no automatic retry. The dedicated
credential directory is absent. The BTC recorder's established read-only health
event remained `RECORDING`; no BTC file or process was changed.

The common entitlement window recorded by both inventories is
`[2024-08-25, 2026-08-27)`. Successful metadata discovery over that interval
does not prove aggregate-bar entitlement for every contract or date.

## ES inventory

Inventory totals (these are **not approved estimates**, because overlapping
listed contracts are double-counted):

- 26 contracts; 10,736 contract-sessions; 2,154 aggregate requests;
  14,815,680 one-minute rows.
- Estimated raw storage: 3,007,583,040 bytes (2.80 GiB).
- Estimated normalized storage: 3,333,528,000 bytes (3.10 GiB).
- Minimum duration at four calls/minute: 539 minutes (8h 59m).
- Discovery exclusions: 80 spread/combo observations. The 126 accepted
  observations collapse to 26 unique tickers, so 100 were repeated
  point-in-time observations—not additional contracts. No micro, option,
  unrelated-root, malformed, or lifecycle-conflict exclusion was recorded.

| Ticker | Provider listing/trading interval | Settlement/expiration | Planned coverage |
|---|---|---|---|
| ESH6 | 2023-08-21–2026-03-20 | 2026-03-20 | 2024-08-25–2026-03-21 exclusive |
| ESH7 | 2023-08-21–2027-03-19 | 2027-03-19 | 2024-08-25–2026-08-27 exclusive |
| ESH8 | 2023-08-21–2028-03-17 | 2028-03-17 | 2024-08-25–2026-08-27 exclusive |
| ESH9 | 2023-12-15–2029-03-16 | 2029-03-16 | 2024-08-25–2026-08-27 exclusive |
| ESM5 | 2023-03-17–2025-06-20 | 2025-06-20 | 2024-08-25–2025-06-21 exclusive |
| ESM6 | 2023-08-21–2026-06-18 | 2026-06-18 | 2024-08-25–2026-06-19 exclusive |
| ESM7 | 2023-08-21–2027-06-17 | 2027-06-17 | 2024-08-25–2026-08-27 exclusive |
| ESM8 | 2023-08-21–2028-06-16 | 2028-06-16 | 2024-08-25–2026-08-27 exclusive |
| ESM9 | 2024-03-15–2029-06-15 | 2029-06-15 | 2024-08-25–2026-08-27 exclusive |
| ESU5 | 2023-06-16–2025-09-19 | 2025-09-19 | 2024-08-25–2025-09-20 exclusive |
| ESU6 | 2023-08-21–2026-09-18 | 2026-09-18 | 2024-08-25–2026-08-27 exclusive |
| ESU7 | 2023-08-21–2027-09-17 | 2027-09-17 | 2024-08-25–2026-08-27 exclusive |
| ESU8 | 2023-08-21–2028-09-15 | 2028-09-15 | 2024-08-25–2026-08-27 exclusive |
| ESU9 | 2024-06-21–2029-09-21 | 2029-09-21 | 2024-08-25–2026-08-27 exclusive |
| ESZ5 | 2021-06-07–2025-12-19 | 2025-12-19 | 2024-08-25–2025-12-20 exclusive |
| ESZ6 | 2021-09-17–2026-12-18 | 2026-12-18 | 2024-08-25–2026-08-27 exclusive |
| ESZ7 | 2022-09-16–2027-12-17 | 2027-12-17 | 2024-08-25–2026-08-27 exclusive |
| ESZ8 | 2023-09-15–2028-12-15 | 2028-12-15 | 2024-08-25–2026-08-27 exclusive |
| ESZ9 | 2024-09-20–2029-12-21 | 2029-12-21 | 2024-09-20–2026-08-27 exclusive |
| ESH0 | 2024-12-20–2030-03-15 | 2030-03-15 | 2024-12-20–2026-08-27 exclusive |
| ESM0 | 2025-03-21–2030-06-21 | 2030-06-21 | 2025-03-21–2026-08-27 exclusive |
| ESU0 | 2025-06-20–2030-09-20 | 2030-09-20 | 2025-06-20–2026-08-27 exclusive |
| ESZ0 | 2025-09-19–2030-12-20 | 2030-12-20 | 2025-09-19–2026-08-27 exclusive |
| ESH1 | 2025-12-19–2031-03-21 | 2031-03-21 | 2025-12-19–2026-08-27 exclusive |
| ESM1 | 2026-03-20–2031-06-20 | 2031-06-20 | 2026-03-20–2026-08-27 exclusive |
| ESU1 | 2026-06-18–2031-09-19 | 2031-09-19 | 2026-06-18–2026-08-27 exclusive |

## NQ inventory

Inventory totals (also unapproved because of overlap/double-counting):

- 17 contracts; 5,222 contract-sessions; 1,049 aggregate requests;
  7,206,360 one-minute rows.
- Estimated raw storage: 1,491,716,520 bytes (1.39 GiB).
- Estimated normalized storage: 1,621,431,000 bytes (1.51 GiB).
- Minimum duration at four calls/minute: 263 minutes (4h 23m).
- Discovery exclusions: 40 spread/combo observations. The 64 accepted
  observations collapse to 17 unique tickers, so 47 were repeated
  point-in-time observations. No other exclusion category was recorded.

| Ticker | Provider listing/trading interval | Settlement/expiration | Planned coverage |
|---|---|---|---|
| NQM5 | 2023-12-15–2025-06-20 | 2025-06-20 | 2024-08-25–2025-06-21 exclusive |
| NQU5 | 2024-03-15–2025-09-19 | 2025-09-19 | 2024-08-25–2025-09-20 exclusive |
| NQZ5 | 2022-05-22–2025-12-19 | 2025-12-19 | 2024-08-25–2025-12-20 exclusive |
| NQZ6 | 2022-05-22–2026-12-18 | 2026-12-18 | 2024-08-25–2026-08-27 exclusive |
| NQZ7 | 2022-09-16–2027-12-17 | 2027-12-17 | 2024-08-25–2026-08-27 exclusive |
| NQZ8 | 2023-09-15–2028-12-15 | 2028-12-15 | 2024-08-25–2026-08-27 exclusive |
| NQZ9 | 2024-06-21–2029-12-21 | 2029-12-21 | 2024-08-25–2026-08-27 exclusive |
| NQH6 | 2024-09-20–2026-03-20 | 2026-03-20 | 2024-09-20–2026-03-21 exclusive |
| NQM6 | 2024-12-20–2026-06-18 | 2026-06-18 | 2024-12-20–2026-06-19 exclusive |
| NQU6 | 2025-03-21–2026-09-18 | 2026-09-18 | 2025-03-21–2026-08-27 exclusive |
| NQZ0 | 2025-06-20–2030-12-20 | 2030-12-20 | 2025-06-20–2026-08-27 exclusive |
| NQH7 | 2025-09-19–2027-03-19 | 2027-03-19 | 2025-09-19–2026-08-27 exclusive |
| NQM7 | 2025-12-19–2027-06-17 | 2027-06-17 | 2025-12-19–2026-08-27 exclusive |
| NQM8 | 2026-03-09–2028-06-16 | 2028-06-16 | 2026-03-09–2026-08-27 exclusive |
| NQM9 | 2026-03-09–2029-06-15 | 2029-06-15 | 2026-03-09–2026-08-27 exclusive |
| NQU7 | 2026-03-20–2027-09-17 | 2027-09-17 | 2026-03-20–2026-08-27 exclusive |
| NQZ1 | 2026-06-29–2031-12-19 | 2031-12-19 | 2026-06-29–2026-08-27 exclusive |

## Coverage, gaps, overlaps, and rollover

The union of planned intervals covers the entitlement window, but the plan has
extensive overlap rather than one active contract per market. No bar-level gap
claim is possible before aggregate data exists. Metadata listing intervals are
not evidence that a far-dated contract traded every minute or should be the
active research contract.

The repository supports `FIXED_DAYS_BEFORE_EXPIRATION` and
`VOLUME_CROSSOVER_POINT_IN_TIME`, but this inventory freezes neither a policy
identity nor roll decisions. The proposed research rule is: build the quarterly
chain chronologically; compare only the current and next contract using the
same completed CME session's finalized volume; retain the current contract on
equality; record the decision after that session closes; and make the next
contract effective at the following eligible minute. This is a proposal, not
an owner-approved policy, and requires overlapping current/next aggregate data.
It must not use future volume or silently stitch contracts.

## Entitlement and unresolved data questions

The metadata result fits the locally imposed two-year date cap, but it does not
prove the Futures Basic aggregate endpoint will serve every requested date.
Aggregate availability, true per-contract bar density, exchange holidays/early
closes, missing/zero-volume minutes, pagination size, response bytes per row,
and usable rollover evidence remain unknown until a separately authorized,
bounded aggregate download.

## Backfill workflow audit

| Required property | Finding |
|---|---|
| Retain every raw aggregate response | **Missing**: implemented only for the bounded probe, not a historical backfill worker. |
| SHA-256 request manifests | Metadata and normalized archive support exists; historical raw-aggregate manifests are not implemented. |
| Separate ES/NQ | Present in planned paths. |
| Checkpoint every successful request | Present for metadata only; aggregate backfill checkpointing is not implemented. |
| Never overwrite verified raw | Probe enforces this; no historical worker enforces it. |
| Safe resume | Not implemented for historical aggregate pages. |
| No automatic retry | Preflight complies; no historical worker exists to audit. |
| Stage, validate, atomically promote | Partial primitives exist, but no end-to-end historical transaction exists; archive replacement can overwrite files. |
| Never fabricate bars | Existing validators reject gaps and do not synthesize. |
| Never silently create continuous series | Individual contracts are retained; stitching requires explicit roll decisions. |
| Status and stop commands | Commands cover metadata preflight only, not a historical backfill. |

Owner approval should remain withheld until the contract-selection/roll policy is
versioned, estimates are regenerated for only the required contract windows,
aggregate entitlement is bounded, and the raw-retaining resumable backfill
worker plus status/stop controls are implemented and tested offline.

