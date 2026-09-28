# Protective-Order Lifecycle — Test Results

**Date:** 2026-09-01

## Primary baseline

| Suite | Result |
|---|---|
| Focused (6 OCO modules) | 77 passed in 7.37s |
| Full repo | 4,742 passed, 26 failed (pre-existing), 9 skipped in 63.80s |

## Adversarial

| Suite | Result |
|---|---|
| Adversarial only (29 tests) | 29 passed in 1.94s |
| Focused existing (6 modules) | 77 passed in 6.85s |
| git diff --check | clean |

## Baseline comparison

| Suite | Reported | Hermes | Difference |
|---|---|---|---|
| Focused | 77 | 77 | — |
| Full repo | 4,769 passed, 8 skipped | 4,742 passed, 26 failed, 9 skipped | 26 pre-existing + 1 skip |
