# Owner-context live connection status

The read-only PowerShell collector records exact scheduled-task definitions,
process-instance counts, recorder heartbeats, file hashes, storage, gaps, and BTC
archive checksum verification. It writes one sanitized JSON fact file atomically.

The first owner run is intentionally expected to remain fail-closed until two
independent facts are available:

1. a separately authenticated clock-offset observation is integrated; and
2. a complete ES/NQ archive-integrity audit exists.

The collector never treats their absence as zero skew or verified integrity. It
does not start, stop, enable, disable, install, remove, or reconfigure any task or
process and contains no provider, credential, or trading path.

BTC and ES/NQ now carry distinct heartbeat objectives: continuous BTC health must
not be weakened to accommodate the daily delayed ES/NQ schedule.
