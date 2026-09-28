# BOT 2.0 Phase 5C-Z — A0 Majority Tie-Break Remediation Specification v1

**Status: PROPOSED — NOT IMPLEMENTED.** This is separate from the abstention/comparison protocol clarification. It does not amend the frozen specification, authorize scoring, or authorize a code change in this pass.

## Finding

- **Classification:** `IMPLEMENTATION_DEFECT`.
- **Authoritative requirement:** the earliest frozen A0 specification, committed in `6a79f53e653944620fe582be33caccdd370269f9` (v1 manifest), requires a TRAIN-only per-root/head/horizon majority with a **lexical tie-break**. The Phase 5B remediation record and frozen v2/v3 specs repeat that rule.
- **Frozen vocabularies/orders:** Direction `DOWN=0, FLAT=1, UP=2`; volatility `LOW=0, NORMAL=1, HIGH=2`; structure `RANGE=0, TRANSITION=1, TREND=2`.
- **Current behavior:** `bot2/phase5c_v3/experiment_runner.py` chooses the lowest class index among tied TRAIN counts via `np.argmax(counts)`. This is an implementation behavior, not an authorized reinterpretation of the lexical requirement. The separate lowest-index tie rule for decoding tied probabilities does not apply to majority-label selection.
- **Chronology:** the index-based implementation appears in commit `f867bf4` (2026-09-22 00:25 -0700), before the structural-preflight review documented that the potential mismatch had been noticed. The lexical requirement predates it. This is established from version history and documents only; no protected rows or tie frequency were inspected.

## Synthetic reproducer

Use only a synthetic TRAIN label-count vector for volatility:

```text
LOW=1, NORMAL=0, HIGH=1
```

Frozen lexical behavior chooses `HIGH` because `HIGH < LOW` lexically among the tied maximum labels. Current class-index argmax chooses `LOW` because index 0 is less than index 2. This reproducer does not imply that such a tie exists in any protected partition.

## Minimal correction, if separately authorized

For `A0_TRAIN_MAJORITY` only: find the maximum TRAIN count, form the set of frozen class labels attaining that count, select the lexicographically smallest label, then emit its corresponding one-hot output. Do not change class order, data, prior availability, A0 persistence/transition behavior, validation selection, A1/A2, features, targets, architecture, calibration, metrics, thresholds, seeds, or any other scientific surface.

## Required synthetic tests

1. Equal maximum counts for volatility `HIGH` and `LOW` select `HIGH` (even though its class index is larger).
2. Equal maximum counts for a class set whose lexical and index minima coincide still select that same label.
3. A unique maximum is unchanged.
4. Permuting input row order does not change the result.
5. TRAIN-only counts are used; validation/test/OOS labels cannot affect the selected class.
6. Every emitted class is in the frozen vocabulary and one-hot index mapping is correct.

Tests must use wholly synthetic arrays; no protected archive, protected tie counts, or protected metric may be read. Before a later implementation pass, obtain a separate authorization for this narrow defect-only patch and independent review. After correction, retain the original frozen protocol hash and bind the code change to its remediation record; do not rewrite the spec to match old code.

**No code or tests were changed or run for this finding.**
