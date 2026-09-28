# Reconciled Phase 4 Audit Test Results

Source Hermes evidence:

- Original Phase 4 adversarial run: 113 passed.
- Original baseline/full runs had 26 failures solely in tests requiring gitignored runtime evidence.
- The failure set was unchanged after adding the Hermes tests.

Codex reconciliation gates:

- Integrated Hermes Phase 4 adversarial: 67 passed in 0.95s.
- Phase 5 focused: 28 passed in 0.91s.
- Complete execution/accounting v2: 463 passed in 1.85s.
- Full offline repository: 1,594 passed in 44.74s.
- `git diff --check`: passed.

This file does not import the original unsupported checksum claims.
