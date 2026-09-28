# OOS Evidence Readiness

This milestone adds the immutable boundary that must be satisfied before an
untouched-OOS run is labeled or evaluated. It does not choose dates, inspect a
hidden partition, tune a strategy, access a provider, or authorize trading.

Each BTC, ES, and NQ plan independently binds:

- repository-relative evidence files, SHA-256 hashes, sizes, record counts,
  timeframes, and coverage;
- every known missing interval;
- exactly ordered training, validation, and untouched-OOS intervals;
- versioned official evidence for every required economic/specification kind;
- publication, capture, effective-date, and plan-freeze chronology; and
- a deterministic content fingerprint.

The plan fails closed for path traversal, duplicate files, invalid coverage,
overlapping or reordered partitions, any missing interval intersecting untouched
OOS, absent or incomplete authoritative evidence, post-effective publication,
post-freeze capture, and fingerprint tampering.

Important: a readiness plan is a declaration over verified inputs. A separate
archive scanner must calculate the real file hashes, counts, intervals, and gaps.
No plan may be created from estimates or manually invented facts.

Remaining work before the first OOS run:

1. Build and independently audit the read-only archive scanner.
2. Acquire authoritative effective-dated fee, margin, instrument, session,
   rollover, and (where applicable) funding evidence.
3. Have the owner approve the frozen dates without viewing OOS outcomes.
4. Produce separate BTC, ES, and NQ plans and preserve them before execution.
