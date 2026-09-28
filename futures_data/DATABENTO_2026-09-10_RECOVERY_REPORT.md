# Databento/NinjaTrader Recovery Trial — 2026-09-10 UTC

State: `REVIEW_REQUIRED`; promotion and cross-source merge prohibited.

The cost preflight estimated USD 0.0050380826 per market (USD 0.0100761652
total), below the hard USD 0.25 ceiling. Immutable historical evidence retained
1,380 `ohlcv-1m` records for each of `MES.v.0` and `MNQ.v.0`. The original
Databento lane files and NinjaTrader daily files remain separate and are linked
to their reconciliation reports by SHA-256.

| Lane | Ninja minutes | Databento minutes | Exact matches | Missing from Ninja | Price conflicts | Volume-only conflicts |
|---|---:|---:|---:|---:|---:|---:|
| ES | 1,147 | 1,380 | 1,004 | 233 | 3 | 140 |
| NQ | 1,147 | 1,380 | 732 | 233 | 8 | 407 |

One 23:59 UTC NinjaTrader bar was explicitly excluded per lane because the
NinjaTrader daily archive assigns it to the following date by close time while
the Databento request assigns bars by open time. The 233 missing NinjaTrader
minutes form a common cross-market interval. This is strong recovery evidence,
but the conflicts must first be classified as volume-only, price differences,
or contract-roll lineage differences. Databento instrument IDs `42003239`
(MES) and `42004800` (MNQ) were observed under volume-leading continuous
symbols. A free metadata lookup resolved those IDs to `MESU6` and `MNQU6`,
matching NinjaTrader's September 2026 contracts. Rollover mismatch is therefore
excluded as the explanation. Most conflicts are volume-only; the three MES and
eight MNQ price-conflict minutes remain quarantined for field-level inspection.

No recovered bar is canonical, no strategy input changed, and no paper or live
order authority was introduced.

## Conservative disposition

The common 233-minute difference consists of a 231-minute recorder outage from
13:30 through 17:20 UTC and isolated 20:59 and 23:59 boundary minutes. Because
volume differs by provider, Databento bars must not be spliced into the immutable
NinjaTrader chain. The complete Databento day is eligible only as a separate,
provider-consistent research lane. Volume features must use Databento volume for
the entire lane; cross-provider volume mixing is prohibited. The lane cannot
authorize paper or live execution, and all eleven price-conflict minutes remain
explicit diagnostics.
