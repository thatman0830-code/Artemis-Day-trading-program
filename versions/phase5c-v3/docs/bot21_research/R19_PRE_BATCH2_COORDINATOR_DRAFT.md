# R19 — BOT 2.0 preservation boundary

**Status:** coordinator read-only boundary note; not an independent code audit. BOT 2.0 source, risk, provider, paper, monitoring, recovery and Phase 5C artifacts remain untouched.

## What R0 may study

Only named, non-protected documentation and explicitly read-only architecture/contracts when needed to understand interfaces. The user-supplied specification is the authority for the A2 description and Phase 5C closed boundary. Current Git metadata was checked: repository branch `bot2-phase5c-z-review-remediation`, HEAD `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`; working tree was already dirty. That state is preserved; no branch switch, stash, reset, commit, merge, or cleanup occurred.

## Read-only interface concept

Future BOT 2.1 should initially be a separate research package/process with its own namespace, dependencies, manifests and read-only data adapter. It may consume a documented, point-in-time market-data contract through an explicitly versioned adapter. It must not import broker, order submission, sizing, execution, paper gateway, authorization, credentials, or risk mutation pathways. Inference/prediction output, if ever separately authorized, should be a research artifact only.

## Never consume in R0

Protected Phase 5C outputs, predictions, probabilities, metrics, P&L, scoring results, sealed OOS samples, or outcomes. Do not use V3/V4/V5/Phase 5C outcomes or scientific decisions as BOT 2.1 rules. Do not train, infer, benchmark, score, trade, connect to brokers, alter providers, or modify BOT 2.0 contracts/source/risk.

**TECHNICAL_CONSTRAINT:** no Bot2 component was modified. `docs/bot21_research/` is the only new intended area. A file-level changed-path audit remains a final verification requirement.
