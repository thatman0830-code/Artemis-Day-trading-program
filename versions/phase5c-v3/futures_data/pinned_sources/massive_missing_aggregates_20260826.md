# Massive missing-aggregates semantics (frozen excerpt)

- Canonical URL: https://massive.com/knowledge-base/article/why-are-there-missing-aggregates-in-massives-data
- Retrieved UTC: 2026-08-26T21:36:56.4438380Z
- Title: Why are there missing aggregates in Massive’s data?
- Publisher: Massive.com, Inc.
- Applicable version: page retrieved 2026-08-26

## Source fact

The page metadata states that Massive does not populate an aggregate unless
OHLC values changed or eligible trades occurred during the aggregate period.

## Bounded interpretation

An absent aggregate proves zero observed eligible-trade volume for that
interval under this frozen provider semantic. It does not provide OHLC and must
not cause an OHLC bar to be synthesized.
