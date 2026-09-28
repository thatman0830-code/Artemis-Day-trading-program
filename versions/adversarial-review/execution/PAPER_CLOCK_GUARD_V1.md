# Paper clock safety guard

Local testable component; not an OS synchronizer, live-time attestation, or
independent watchdog. No process, scheduled task, network operation, or real
clock-health collection is performed by this module.

The caller supplies clock-health facts and can either supply paired samples or
use `capture_paper_clock` to bracket a local UTC read with `time.monotonic_ns`.
The capture midpoint is a pairing estimate, not proof of synchronization. A
capture longer than 100 milliseconds, regressing monotonic readings, invalid
values, or reader exceptions reject. Full capture span is conservatively charged
against the uncertainty budget and anchor-divergence limit.

Clock-health facts comprise UTC observation time, synchronization flag, signed
offset, uncertainty, and source SHA-256. The source hash binds supplied evidence
identity but does not authenticate it. A validated clock-health evidence decoder
is still required; local sampling alone does not prove absolute time accuracy.

The single-use in-memory guard checks:

- Exact integer nanoseconds and UTC timestamps.
- Synchronized health, no future health, maximum 90-second health age, and a
  maximum combined absolute offset plus uncertainty of two seconds.
- Strictly advancing monotonic readings and non-regressing UTC.
- At most five seconds between checks, detecting a stalled loop upon resumption.
- At most two seconds divergence from the original UTC/monotonic anchor, so small
  per-step clock drift cannot evade cumulative checking.
- A monotonic fifteen-minute upper deadline; the bounded driver also enforces
  its own shorter evidence/confirmation/session deadlines.

Any rejected observation latches the guard. It does not reset or auto-resynchronize.

`ClockCheckedPaperSessionV1` checks the guard before forwarding any driver input.
On a clock fault it attempts the driver's stop operation using the last accepted
UTC reading. That timestamp is intentionally not a fresh clock observation.
The original clock error is raised after a confirmed stop. A failed stop raises
an explicit unconfirmed-stop error with the underlying cause. Stopping does not
fabricate position-closing fills.

Important: this wrapper cannot act while its own process is frozen. A separate
watchdog and runtime integration are still required before operational launch.
The raw bounded driver remains callable; runtime integration must route inputs
through this wrapper and must not bypass it.

`sample_and_start` and `sample_and_step` capture time before invoking the guarded
driver. A capture failure latches the guard and attempts a stop before input is
forwarded. Readers can be injected for deterministic testing. Default readers
only read local clocks; they do not modify clock configuration.

The existing owner-context collector reports rounded clock_skew_seconds and
source hashes, not the explicit uncertainty required here. There is no automatic
conversion and no assumed zero uncertainty. Clock-health provenance/uncertainty
mapping must be implemented and verified before runtime use.

Verification: 30 focused cases passed using injected readings and temporary
session fixtures. No real session, clock configuration, recorder, or watchdog
service was accessed or changed. No independent Hermes audit is claimed.
