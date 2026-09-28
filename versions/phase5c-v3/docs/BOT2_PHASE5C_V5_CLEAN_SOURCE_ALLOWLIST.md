# BOT 2.0 Phase 5C V5 Clean-Source Allowlist

**Disposition: STOP — CLEAN SOURCE BOUNDARY CANNOT BE ESTABLISHED**  
**Status: FROZEN DENY LIST; no scientific design authority approved.**

This record was created before any V5 scientific design. It classifies only known candidate/provenance sources. Because the S4 incident time and derivation chain cannot be established, chronological appearance before V4 is insufficient to certify a document as pre-incident. Per the authorization, uncertainty is DENY. This inventory is not a claim that every possible repository authority has been discovered; the provenance boundary is itself unbounded.

No file below `outputs/` was listed, searched, opened, hashed, or inspected. No V4 scientific contents were used to design V5. V4 identities below are recorded only for quarantine/audit.

| # | Candidate source | SHA-256 / provenance evidence | Predates V4? | Could contain protected performance? | S4 separation established? | Scientific design authority | Reason |
|---:|---|---|---|---|---|---|---|
| 1 | `outputs/<unidentified serialized artifact>` | Exact path/hash/time unavailable; implicated only by the prior independent V4 audit | Unknown | Unknown, potentially high | No; direct reported exposure | **DENY** | Never inspect; identity and exposure are unbounded. |
| 2 | `docs/BOT2_PHASE5C_V3_PROTOCOL.md` | SHA-256 `23905dbd4215669477645313b931243a644e83755577c4abf7ac57a0adc62667`; commit `9a1ecfaf08077252049dd187d44f8641da1186aa` | Yes by Git chronology | No performance content established by this provenance-only audit | No incident cutoff proves it predates S4 | **DENY** | Strong historical V3 anchor, but cannot certify pre-incident status. |
| 3 | `docs/BOT2_PHASE5C_V3_PROVENANCE.md` | SHA-256 `69c500e0f181e2e38ca50ae91b9ff21f0461738e6b55f900e039376325d1dc58`; commit `66caddf995af9c6e78e8852055bae25459b57b18` | Yes by Git chronology | Not assessed by content | No incident cutoff proves it predates S4 | **DENY** | Provenance identity is insufficient to bound exposure. |
| 4 | `config/bot2_phase5c_v3_manifest.lock.json` | SHA-256 `7cb99e0862aad63d28896ab888f9422e99737f923a0f8ded8b3dc3238dbc4a32`; commit `66caddf995af9c6e78e8852055bae25459b57b18` | Yes by Git chronology | No result artifact indicated by its role; content not used | No incident cutoff proves it predates S4 | **DENY** | Identity lock cannot establish the missing incident boundary. |
| 5 | `docs/BOT2_PHASE5C_Z_A0_ABSTENTION_PROTOCOL_REVIEW.md` | SHA-256 `d720d7e821303fe3f9e92d3ebfc772c9c66aaa96be64b1031ec40f601e810b10`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No S4 cutoff or derivation lineage. |
| 6 | `docs/BOT2_PHASE5C_Z_A0_TIE_BREAK_REMEDIATION_SPEC_V1.md` | SHA-256 `355c825fa8ca09c7e79f5fea7db91866772ab2cf9c87e16edf7ac49e005fcd04`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No S4 cutoff or derivation lineage. |
| 7 | `docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_COORDINATOR_REVIEW.md` | SHA-256 `477ee27f36ff46e089529e718042c546931789778d18993d77e13b7fea48545f`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No S4 cutoff or derivation lineage. |
| 8 | `docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1.md` | SHA-256 `eb9e08338c20ead395e0915078caeb80bdd600fd39f4791f8bfb3fd640296b4f`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No S4 cutoff or derivation lineage. |
| 9 | `docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1_INDEPENDENT_REVIEW.md` | SHA-256 `e7cca6049db997a13289c742458309fb16836525bd2c05baf734e0fcf2c3c007`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No verifiable agent/input provenance or S4 cutoff. |
| 10 | `docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V2_COORDINATOR_REVIEW.md` | SHA-256 `d17d5ee1c49317d114ce5217a5d0938973db6da6b945a59667b45b4e5f6a7a87`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No S4 cutoff or derivation lineage. |
| 11 | `docs/BOT2_PHASE5C_Z_REVIEW_BLOCKER_REMEDIATION.md` | SHA-256 `964bdf765ec54d27a17c1b7b6bf455d80cfd0ee67a131a14063cfa50874c10c1`; untracked at reviewed HEAD | Before V4 by observed file chronology | Unknown | No | **DENY** | No S4 cutoff or derivation lineage. |
| 12 | `docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md` | SHA-256 `3f697ee8fb2e802a9e9f0332f27504d6d8cdaa9220c32745d930bb34fa598630`; untracked; detached sidecar matches | No | Unknown | No | **DENY** | Quarantined; contamination unbounded. Not a scientific source. |
| 13 | `config/bot2_phase5c_v4_protocol_proposal.json` | SHA-256 `32345143af5bc9e4021fbbd18aa39ea064aca33db040873b073f9f2ad79d75b0`; untracked; detached sidecar matches | No | Unknown | No | **DENY** | Quarantined; contamination unbounded. Not a scientific source. |
| 14 | `docs/BOT2_PHASE5C_PROTOCOL_V4_COORDINATOR_RECONCILIATION.md` | SHA-256 `f4f6e5a299003f156efffb4c2bdf3599f39b64248612fd159bbc77029b7dd6b8`; untracked | No | Unknown | No | **DENY** | Coordinator assertions cannot independently bound contamination. |
| 15 | `docs/BOT2_PHASE5C_V4_INDEPENDENT_SCIENTIFIC_REVIEW.md` | SHA-256 `7c2ee1718ad19dcd94997bcd537139e99abd0a14a55382d6712ecbdd9c5259ce`; untracked | No | Review reports no protected work by that review; historical counters unverified | Reports unresolved S4 | **DENY as design authority; audit-only use permitted** | May describe V4 rejection/defect categories only; no scientific rule may be sourced from it. |

### Tally and gate

- Enumerated candidate/provenance sources: **15** (not exhaustive because provenance is unbounded).
- Approved scientific design authorities: **0**.
- Denied as scientific design authorities: **15**; item 15 is restricted to the narrow audit-only use above.
- V3 model/feature/target/WF/calibration/abstention/A0/A1/A2/test specifications not independently traceable to a proven pre-S4 cutoff are not approved by implication; any additional candidate is DENY until separately provenance-reviewed.
- Four clean-room design roles were **not launched**. No V5 scientific design was started.

The clean-room source gate fails. Stop with **STOP — CLEAN SOURCE BOUNDARY CANNOT BE ESTABLISHED**.
