# Institutional Operational Standard

The system must be designed for faults, not described as fault-free. Unattended
operation is permitted only while a content-addressed readiness decision is
healthy. This decision is advisory and never grants trading authority.

## Enforced controls

- Every required component must have exactly one running instance.
- Heartbeats must remain inside the declared recovery-point objective (RPO).
- Restart budgets are bounded; exhaustion is an incident, not an infinite loop.
- Unresolved market-data gaps and integrity failures block readiness.
- Minimum free storage and maximum clock skew are explicit policy values.
- Missing observations and observations from the future fail closed.
- Open incidents block readiness; resolved incidents remain immutable evidence.
- Decisions and incidents are deterministic, content-addressed records.

## Existing runtime mechanisms

The BTC recorder already has a named mutex, Task Scheduler `IgnoreNew`, bounded
exponential restart delay, secret-free JSONL events, alerts, and post-start health
verification. ES/NQ has a single-instance scheduled collector, health reports,
locks, and stop-request visibility. These mechanisms supply observations to the
new unified evaluator; they do not bypass it.

## Still required before operational trading

- A read-only adapter that converts owner-context Task Scheduler and recorder
  evidence into signed/hashed observations without exposing credentials.
- Durable off-host monitoring and alert delivery with tested escalation.
- Backup, restoration, disaster-recovery, and failover exercises with measured
  RPO/RTO results.
- Append-only audit retention, access control, dependency/SBOM controls, patching,
  secret rotation, clock synchronization, capacity testing, and incident drills.
- Independent security review and explicit owner deployment authorization.
- Broker/exchange order reconciliation, kill switch, exposure limits, and manual
  recovery procedures, built only after offline OOS and paper gates pass.

No claim of institutional readiness or 24/7 trading readiness is justified until
the remaining controls are implemented and exercised with retained evidence.
