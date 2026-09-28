# Phase 6 Reason Codes

The authoritative machine values are `Phase6Reason` in `rollover_funding.py`. Categories cover
invalid/stale/overlapping/ambiguous roll specifications; identity/version/session/bar failures;
outgoing/incoming and participation failures; unsupported, missing, late, stale, or missed funding;
duplicate/conflicting facts; chronology/priority ambiguity; checkpoint tamper; incomplete roll or
funding; and reconciliation mismatch. `OK` is descriptive only and never trading authority.

`PRIORITY_AMBIGUITY` is the stable reason for every equal-time/equal-priority
collision, independent of lexical event identity. `EVENT_TIME_REGRESSION` is
reserved for actual canonical chronology regression.
