---
title: Configuration vs Logic Boundary
type: configuration
---

# Configuration vs Logic Boundary

## LOCKED LOGIC
The mechanical rules, ownership boundaries, mathematical definitions, state machines, and invariants in `01_Market_Primitives/`, `02_Setup_Engine/`, `03_Execution/`, and `04_Analytics/` are **locked**. They are governed by [[Trading Brain — Source Precedence]] and Amendments 001–005A.

## CONFIGURABLE RUNTIME VALUES
The values in [[Runtime Configuration Registry]] parameterize the locked logic at runtime.

## Rules
- Configuration **may** change parameter values **only where explicitly permitted** by source.
- Configuration **may not** redefine primitive ownership.
- Configuration **may not** redefine mathematical rules, invariants, or state machines.
- A missing configuration value is a **deployment prerequisite**, not missing trading logic — it does not block specification readiness.

## Owner Policy (non-blocking, not configuration)
- indicators mandatory-vs-optional (source does not gate setups on indicators; #26 excludes them)
- optional #17 session/time/event no-trade overlays (mechanical no-trades are already emergent from locked primitives)

See [[Trading Brain — Implementation Readiness]].
