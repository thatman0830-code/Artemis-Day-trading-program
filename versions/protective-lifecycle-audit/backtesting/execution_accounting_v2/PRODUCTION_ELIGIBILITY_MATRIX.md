# Production Eligibility Matrix

| Requirement | ES | NQ | BTC spot | BTC linear perpetual |
|---|---|---|---|---|
| Proven instrument identity | Partial/current terms | Partial/current terms | Missing | Missing |
| Tick/step/multiplier | Established current terms | Established current terms | Missing history | Missing history |
| Authoritative sessions | Historical CME copy incomplete | Historical CME copy incomplete | Owner UTC policy needed | Continuous/funding policy needed |
| Settlement | Rule semantics established; exact history needed | Rule semantics established; exact history needed | N/A | N/A |
| Clearing margin history | Missing | Missing | N/A | Missing tiers/history |
| Exchange/clearing/regulatory fees | Partial | Partial | N/A | N/A |
| Owner broker commission | Missing | Missing | N/A | N/A |
| Fee schedule/tier | N/A beyond above | N/A beyond above | Missing | Missing |
| Mark/oracle/funding | N/A | N/A | N/A | Missing |
| Slippage/participation | Owner values missing | Owner values missing | Owner values missing | Owner values missing |
| Complete risk inputs | Missing | Missing | Missing | Missing |
| Current production eligibility | **REJECT** | **REJECT** | **REJECT** | **REJECT** |

Synthetic contract tests may use explicit `SYNTHETIC_TEST_ONLY` records. Such records cannot become
production eligible. No unsupported cell is filled with zero or inferred from candles.
