# Windows clock evidence for supervised paper sessions

Status: locally tested offline implementation; not an independent Hermes audit,
runtime deployment, measured clock accuracy, or paper-launch approval.

`paper_windows_clock_evidence_v1.py` decodes supplied English UTF-8
`w32tm /query /status /verbose` bytes. It does not invoke W32Time, access a
provider, read runtime files, alter time configuration, or start a session.
The existing owner-context collector remains unchanged.

## Contract and uncertainty

The trusted acquisition boundary must supply exact raw SHA-256 and UTC capture
start/end. Captures longer than five seconds and reports older than 90 seconds
reject. Required fields must occur exactly once. Unsupported localization,
invalid numbers, nonzero leap/sync-error codes, invalid stratum, unapproved
sources and synchronization age over 24 hours reject. Successful-sync display
text is retained in raw bytes; numeric time-since-good-sync supplies age instead
of guessing the display date's locale/timezone. This decoder does not independently
validate that display date or authenticate the status producer.

Offset is the signed phase offset in integer nanoseconds. Uncertainty includes:

- Reported root dispersion plus half root delay, rounded upward.
- Precision from the reported base-two exponent, rounded upward.
- Explicit drift allowance over reported sync age, full query duration, and the
  entire 90-second permitted health lifetime.
- Explicit positive local uncertainty allowance and full query duration.

The drift floor of 15,000 ns/second (15 ppm) is a policy baseline, not a measured
hardware bound. Root distance is an estimate, not a certified bound. Summing these
terms intentionally may overcount uncertainty. Never invent a zero local allowance
or lower observed dispersion to pass the gate. A deployment-specific reviewed
policy must provide the exact source allowlist, local allowance, drift allowance,
and evidence hash. No production policy or owner approval is supplied here.

The health source identity binds raw bytes, policy fields, policy evidence hash,
capture timestamps and computed values. Hashes provide identity, not authenticity.
Receipt objects are trusted in-memory outputs, not a serialized trust boundary.

The existing clock guard still enforces its two-second total budget, freshness,
monotonic deadline, loop-gap and wall/monotonic divergence checks. Excessive
uncertainty produces a health observation that the guard rejects, not a fabricated
healthy observation. `read_and_start` / `read_and_step` obtain health through an
injected reader; acquisition or decoding errors latch the guard and attempt the
existing stop path. Failed stops are explicitly unconfirmed. No independent
watchdog exists in this wrapper, and raw APIs must not bypass it in deployment.

## Verification and remaining launch work

Fixtures are synthetic and isolated. Tests cover exact arithmetic, canonical
binding, source rejection, duplicate/missing/localized fields, uncertainty,
freshness, policy types, and durable stop before command dispatch on decoder error.
These are not profitability or real-world accuracy tests.

To reach a demonstrated supervised paper session:

1. Approve and validate clock assumptions; wire trusted bounded raw acquisition.
2. Wire real closed-bar snapshots and the selected strategy to validated simulated
   fills and exact cost evidence. Do not relabel 15-minute bars as one-minute fills.
3. Exercise the integrated runtime, external stop/watchdog, dashboard, and outage
   recovery using isolated artifacts; retain evidence.
4. Obtain fresh launch evidence and session-specific supervision confirmation.

First-session scope is bounded local BTC spot simulation, not exchange-hosted
paper execution, ES/NQ activation, live trading, or unattended 24/7 operation.

## References

- Microsoft, [Windows Time tools and settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings): status query fields and phase offset.
- IETF, [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html): delay/dispersion distance and oscillator-tolerance aging. This mapping is a local conservative policy model, not a claim to implement the full NTP algorithm.
