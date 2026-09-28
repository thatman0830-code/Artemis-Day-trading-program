# Off-Host Alert Delivery Foundation

This module provides deterministic alert-envelope validation, atomic filesystem
handoff, read-back verification, immutable local delivery receipts, and bounded
operator acknowledgement evidence. Every record has `trading_authority=false`.

A sink must contain an exact `owner-alert-sink-v1` manifest with a stable sink
identity, eligible transport classification, and explicit owner attestation.
Malformed alerts, duplicate identities, conflicting immutable files, chronology
errors, and acknowledgement-SLA breaches fail closed.

This is not yet a completed off-host alerting control. The sink attestation and
operator acknowledgement are not cryptographically authenticated, and no real
remote destination, redundant route, escalation recipient, or delivery drill is
configured. Institutional readiness requires an owner-approved external sink,
authenticated acknowledgements, scheduled delivery, outage testing, and retained
evidence demonstrating the alert RTO/SLA.

The initial owner-approved connector targets only
`OneDrive\TradingSystem\AlertEvidence`. Its runner reads the sanitized watchdog
alert spool, validates the exact sink manifest, and writes delivery envelopes to
the synchronized folder plus immutable receipts locally. It does not read other
OneDrive content or credentials, and scheduling remains a separate audited step.

The scheduling layer is installed disabled, runs every five minutes with
`IgnoreNew` and a two-minute execution limit, and uses a limited interactive
owner context. Enablement requires an exact read-only task audit, a successful
fresh task run, and read-only proof that every local alert has both its immutable
OneDrive envelope and matching local receipt. Any failure disables the delivery
task. Removal requires verified identity and preserves all evidence.
