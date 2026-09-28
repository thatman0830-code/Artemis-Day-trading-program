# Owner-Context Health Watchdog

The watchdog automates the existing read-only owner-context health collection and
evaluation boundary. It never grants trading authority and does not start, stop,
enable, disable, or restart either recorder.

## Runtime evidence

- `latest-watchdog-status.json` is the authoritative current watchdog state. Any
  collection or evaluation failure atomically changes it to `UNHEALTHY`.
- `latest-readiness.json` is the last successfully evaluated readiness report.
  It is retained during watchdog failure for diagnosis and is not current status.
- `reports/<report_id>.json` retains content-addressed successful reports.
- `alerts.jsonl` is a flushed append-only local transition spool. Repeated runs in
  the same health/failure state are deduplicated; health changes and recovery are
  retained as new events.
- `alert-state.json` contains only the current deduplication signature.

All records are secret-free and explicitly set `trading_authority` to `false`.

## Scheduling boundary

`install_owner_context_health_watchdog_task.ps1` creates a five-minute,
single-instance, four-minute-bounded owner-context task and immediately disables
it. Installation and later enablement are separate explicit owner operations.
The task uses the existing collector and repository Python environment.

Post-install deployment remains gated by three scripts. The audit script verifies
the exact owner, executable, arguments, working directory, singleton policy,
interval, execution limit, and authority boundary without mutation. The guarded
enablement script requires a disabled audited task, performs one explicit run,
and accepts it only after a fresh `HEALTHY` status and successful task result; on
any failure it disables the task. The removal script refuses an unknown task and
preserves all watchdog evidence.

## Remaining boundary

The alert spool is local evidence, not off-host notification. Durable remote
delivery, escalation acknowledgement, backup/restore drills, and controlled
recorder failure/recovery exercises remain required before an institutional or
24/7 operational-readiness claim.
