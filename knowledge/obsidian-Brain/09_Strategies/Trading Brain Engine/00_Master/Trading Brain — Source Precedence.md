---
title: Trading Brain — Source Precedence
type: master-policy
appendix_a_modified: false
---

# Source Precedence

1. **Owner Resolution Amendments 001–007**
2. **Later explicit owner-supplied locked definitions**
3. **Canonical implementation specification**
4. **Appendix A / recovered historical transcript**

## Rule

Higher-precedence source governs implementation. Lower-precedence source remains historical evidence. **Superseded historical text must not be deleted** — it is preserved in [[Appendix A — Recovered Historical Transcript]].

## Known Supersessions

### Amendment 007
- Preserves #27's theoretical-EQ ≥2R setup gate and adds [[#29.0 Execution Eligibility]] as the downstream realistic-entry ≥2R authorization gate.
- Establishes [[Execution Entity Hierarchy]] and [[Execution Quality EOD Metrics]].
- Extends #29.1/#29.6 interfaces without renumbering or replacing existing primitives.

### Amendment 001 — C1 (Canonical analytics numbering)
Frozen registry `#29.7.2.9–.20` governs. Any older internal numbering recap inside supplied source text is historical wording and does **not** renumber the registry. Notably the `#29.7.2.15` internal recap → `SUPERSEDED_BY_AMENDMENT_001_C1`.

### Amendment 001 — C2 (Global fail-closed duplicate policy)
`duplicate canonical uniqueness key within one source_version → DATA_INTEGRITY_ERROR → dataset_status = DATA_INTEGRITY_ERROR → affected_calculation_valid = FALSE → no finalized analytical snapshot`. No silent deduplication, no retain-and-continue, no averaging, no arbitrary selection. Supersedes:
- `#29.7.2.14` exclude-and-continue duplicate wording → `SUPERSEDED_BY_AMENDMENT_001_C2`
- `#29.7.2.17` retain-canonical-and-continue wording → `SUPERSEDED_BY_AMENDMENT_001_C2`
- `#29.7.2.16` reject-ambiguous-dataset behavior is **consistent** with C2.

### Amendment 001 — C3 (Canonical StrategyPeriodReturnObservation)
See [[StrategyPeriodReturnObservation]]. `.19`/`.20` consume period-aligned `net_r`; `period_end <= T`; missing ≠ zero; finalized `net_r = 0` is a real observation. No old `{timestamp, return_value}` schema may be restored.

### Amendment 002
- **R1** — Time / Period policy → [[Time — Period Policy]]
- **R2** — Identity / Versioning policy → [[Identity — Versioning Policy]]
- **R3** — Precision / Rounding policy → [[Precision — Rounding Policy]]

### Amendment 003
Enum / Error taxonomy → [[Canonical Enum Registry]], [[Canonical Error Registry]], [[Error Precedence — Fail Closed]].

### Amendment 005A
Reversal sweep-side mapping and #27/#28 ownership:
```
Bearish prior regime → LSL sweep → bullish reversal
Bullish prior regime → BSL sweep → bearish reversal

#27 pre-zone qualification → #28 (select/freeze zone + EQ) → #27 final Entry/Stop/Target/≥2R validation → arm
```
The historical `IF Setup.state != ARMED: #28 does nothing` circular wording is superseded; do not restore it.
