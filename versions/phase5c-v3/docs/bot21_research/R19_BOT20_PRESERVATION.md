# R19 — BOT 2.0 Preservation Architecture

Role: fresh independent preservation architect, Batch 2 recovery.  
Date and public-source access date: 2026-09-24, America/Phoenix.  
Status: COMPLETE — independent first pass frozen on save; conceptual research only.  
Source count: 7 substantive sources: 1 internal current-state audit and 6 public primary/official sources. The user instruction attachment is a scope/provenance record, not an eighth research source.  
Scope: coexistence and preservation only; no final BOT 2.1 synthesis, implementation, executable specification, or authorization to operate.

## Principal finding

The safest conceptual boundary is an independently permissioned research execution domain, with separate package, environment, configuration and artifact ownership, receiving only specifically approved read-only observations and emitting non-authoritative research records to a separate sink. A separate process is useful but insufficient if it retains BOT 2.0 filesystem permissions, credentials, writable shared state, or unrestricted network access. A stronger host or virtual-machine boundary can reduce shared-kernel and resource exposure; this report does not select a deployment technology. The minimum preservation property is that stopping, failing, exhausting, or compromising BOT 2.1 cannot require a BOT 2.0 code, configuration, ledger, risk, or recovery change. This is a preservation conclusion, not a complete architecture selection. [R19-S01–S04]

The highest operational integration risk is accidental authority inheritance through shared configuration/imports/credentials into risk, paper gateway, ledger or recovery. A research prediction becoming an order proposal is already a boundary crossing, even if an existing risk check would subsequently reject it. The highest scientific integration risk is shared data/session/feature/preprocessing semantics or contaminated lineage being silently carried into a new namespace. Both risks can survive a new directory name. [R19-S01]

## Evidence boundary and confidence

The mandatory audit was read in full, including the handoff, with focused rereads of its architecture, data, controls, and preservation sections. It describes a dirty tree on branch `bot2-phase5c-z-review-remediation`, HEAD `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`. These identities and current-state findings are inherited audit evidence, not independently reverified source/runtime claims. No raw source, configuration, model, dataset, manifest, checkpoint, ledger, output, protected result, or environment secret was read for R19. The existing R19 draft was copied and hashed as bytes without reading its text.

The audit establishes a mixed repository with adjacent research and operational subsystems; it does not establish a single working ES/NQ model-to-order service. It reports first-observed-row session-open semantics, two synchronization approaches, fragmented risk defaults, an unsigned provenance anchor, an unbounded S4 contamination boundary, no approved scientific-source authority, and no verified promoted baseline or active paper session. Phase 5C remains paused and protected OOS closed. Existing code and historical tests are evidence of design intent, not present runtime correctness. [R19-S01, §§3–10, 22–35, 42–50]

Consequently, all reuse classifications below mean candidates for a separately authorized future review. None authorizes loading present datasets, importing modules, executing an adapter, or opening protected material. Public guidance supports general engineering principles; its application to BOT 2.0 is explicitly this specialist's inference.

## Classification vocabulary

These categories overlap. A component can be preserved while its exported information is a future reuse candidate. A risk label does not override preservation.

| Category | Meaning in this report |
|---|---|
| PRESERVE_READ_ONLY | Retain existing bytes, behavior, identity and custody; no research-led repair or migration. Protected assets remain inaccessible, not merely read-only. |
| REUSE_THROUGH_VERSIONED_INTERFACE | Consider approved information through a stable, separately reviewed contract; no permission to import implementation or trust current payloads. |
| REQUIRES_ADAPTER | Semantic translation or authority separation needs an explicit future boundary; adapter design/creation is out of scope. |
| DO_NOT_IMPORT_DIRECTLY | Transitive behavior, side effects, dependencies, authority or contamination prevent treating a module/artifact as a safe library. |
| HIGH_BLAST_RADIUS | Shared semantics or mutable state can affect multiple scientific or operational consumers. |
| REPLACE_ONLY_AFTER_INDEPENDENT_VALIDATION | A future replacement needs its own review and evidence, without silently changing existing BOT 2.0 behavior. This is not replacement authorization. |
| HISTORICAL_ONLY | Evidence about a past design or event, never present approval, performance proof or runnable baseline. |

## Component disposition

All component facts and paths in this table come from R19-S01; they were not independently inspected. Abbreviations: P = PRESERVE_READ_ONLY; V = REUSE_THROUGH_VERSIONED_INTERFACE; A = REQUIRES_ADAPTER; D = DO_NOT_IMPORT_DIRECTLY; B = HIGH_BLAST_RADIUS; R = REPLACE_ONLY_AFTER_INDEPENDENT_VALIDATION; H = HISTORICAL_ONLY.

| Component | Categories | Preservation boundary and future evidence needed |
|---|---|---|
| `futures_data/`, source probes, recorders, backfill/recovery | P, A, D, B | Ingestion ownership and provider credentials stay outside research. Future observation access must not trigger collection, backfill, subscription changes, archive repair or recorder restart. |
| Pass B archive adapter and `backtesting/core_v1/production_adapters.py` | P, V, A, D, B | Interface concepts may be reusable after provenance review. Direct invocation may open pinned archives; no current invocation is allowed. New data authority cannot be inferred from old validation metadata. |
| Raw event schemas, dataset manifests, validators, reason codes | P, V, B, R | Preserve old versions and rejection semantics. New schemas must declare compatibility and semantic differences; a parseable row is not proof of causal availability. |
| Session, roll, exact-contract and ES/NQ synchronization | P, A, B, R | Calendar/session and nearest/exact differences require independent resolution in a new contract. Do not fix BOT 2.0 in place or rename existing semantics as equivalent. |
| Replay/cutoff utility | P, V, A | Preserve ordered-input assumption and absence of historical receipt-time. Future use requires explicit ordering and availability interpretation; replay is not a proven live execution simulation. |
| Feature engine and 24-field registry | P, V, A, B, R | Feature-row meaning/order can be studied; direct import is not approved. A calendar-open correction changes scientific meaning even if type/field names remain stable. Keep old feature identity intact. |
| Future targets and label registry | P, V, D, B, R | Definitions may inform future offline research. Labels and target-generating state must never enter an observation/shadow input interface. Keep maturity and future information intervals distinct. |
| Train-only scaler and preprocessing artifacts | P, D, B, R | Never share mutable fitted state or silently refit BOT 2.0 artifacts. New lineage must identify fitting population, schema and transformation version. No existing artifact is approved to load. |
| A0/A1/A2 models; calibration, abstention, ablation logic | P, D, R | Preserve candidates and controls. Do not turn research outputs into strategy signals or reuse weights/calibrators by path convenience. Replacement claims need independent evidence and authority. |
| Regime logic and strategy modules | P, V, A, D | Vocabulary may be compared; research-only candidate status stays research-only. No route from classification to proposal is authorized. |
| Experiment registry and research-artifact registry | P, A, B | Separate future experiment/model identities and approval meanings; do not append BOT 2.1 experiments to the BOT 2.0 registry. Existing append-only behavior is not a verified model-promotion service. |
| Phase 5C V1/V2/V3 manifests, anchors, splits, protocol and no-score guards | P, D, B | Preserve restrictions and historical identities. No adapter may reinterpret preflight success, frozen status, or hash match as evaluation approval. |
| V4 proposal and V5 incident/source-boundary records | P, D, H | Quarantined/not-adopted proposals remain so. Preserve incident evidence; its existence does not cleanse lineage. V5's current blocker remains operative audit evidence. |
| Protected OOS, outputs, results, archives and checkpoints | P, D, B | No access in this work. Read-only access is still prohibited exposure. Future research must obtain an approved source boundary without using protected results to justify itself. |
| Risk/pretrade/portfolio guards and policy defaults | P, D, B, R | Existing authority remains independent of research. Conflicting scopes/defaults cannot be merged opportunistically. Research cannot mutate limits or reuse an authorization object. |
| Execution modules and provider adapters | P, D, B, R | No imports, broker credentials, order route or lifecycle hooks in the research domain. Read-only provider code is not a proof that all transitive behavior is harmless. |
| Paper gateway, paper exchange adapter and fill engine | P, D, B, R | Paper is stateful, not synonymous with shadow. Idempotency, reconciliation, fill assumptions and receipts must not be affected by research. |
| SQLite ledger and paper event/receipt state | P, D, B, R | No shared writable database or default relative-path resolution. A research record is not a ledger transaction; research restart cannot replay entries into accounting. |
| Monitoring, dashboards and alert delivery | P, V, A, B | Selected status vocabulary may cross a future observation interface. Separate namespaces, sinks and ownership prevent research health from masking operational failure or flooding existing alerts. |
| Recovery, scheduler, watchdog and reconciliation | P, D, B, R | Research must not restart BOT 2.0, change scheduled tasks, repair archives, reset sessions, or reconcile account state. Automatic recovery must not undo a deliberate research disable. |
| Configuration, global environment, secrets and broker connections | P, D, B | Separate ownership and effective permissions; no inherited credential/config search path. No secret values or connection state were inspected. |
| Historical synthetic demonstrations/test reports | P, H | Retain for history; they cannot establish current green tests, profitable models, clean lineage, or paper readiness. |
| Dirty working copies and local Git history | P, B | A commit hash does not capture uncommitted source/control work. No checkout, cleanup, stash or reset is part of preservation. Owner baseline review remains outstanding. |

## Separation dimensions and their limits

The following are conceptual requirements to evaluate later, not a filesystem layout or configuration specification.

| Dimension | Preservation purpose | Residual risk/evidence obligation |
|---|---|---|
| Separate package | Avoid direct/transitive coupling to BOT 2.0 internals. | A package boundary does not remove side effects, shared defaults or runtime authority. |
| Separate virtual environment | Keep research dependency changes from changing BOT 2.0 dependencies. | Python environments isolate package installations; they are not access-control or host-resource boundaries. A reproducible environment also needs a separately reviewed interpreter/dependency identity. [R19-S02] |
| Separate configuration | Keep credentials, limits, startup and default paths independently owned. | Global environment inheritance and implicit relative paths can defeat apparent separation; effective configuration needs later evidence. |
| Separate model registry | Keep candidate identity distinct from permission to serve or promote. | A mutable “latest” name cannot establish approval or reproduce a prior pairing of model/preprocessor/schema. |
| Separate experiment registry | Preserve BOT 2.0 records and independent trial accounting. | Namespacing alone does not remove derivative contamination or undisclosed shared selection decisions. |
| Separate manifests | Record new data authority, transformation lineage and scope. | New manifest IDs or hashes cannot confer clean scientific origin. [R19-S07] |
| Separate outputs, logs and checkpoints | Prevent overwrite, accidental artifact discovery and mixed ownership. | Shared disks, caches, default destinations, links and retention jobs can cross boundaries; physical permissions and capacity remain unverified. |
| Read-only dataset interface | Expose only approved observations while preserving source custody. | Read-only is not permission to read OOS; partition eligibility and access scope are separate requirements. |
| Versioned schemas | Make identity and compatibility explicit for consumers. | Serialization compatibility does not establish behavioral or scientific equivalence. [R19-S05] |
| Typed prediction interface | Distinguish prediction from proposal, authorization and execution receipt. | Types and authority labels must be enforced by independent consumers/permissions; a declaration alone is not a barrier. |
| Shadow interface | Observe and record without affecting decisions, orders or state. | No synchronous dependency may make BOT 2.0 wait for research; paper gateways are outside shadow. |
| Feature flags | Allow independently governed research enable/disable. | A flag is operational control, not the security boundary; ambiguity/restart must not restore authority. |
| Process isolation | Limit failures and memory/state sharing. | Same-user processes may still share files, credentials, network, CPU/GPU/disk and supervisors. |
| Resource and security isolation | Contain load and privilege independently. | Technology strength and host compatibility must be established; Microsoft distinguishes process containers from stronger hypervisor isolation. [R19-S04, S06] |

NIST's no-implicit-trust principle supports evaluating each resource access independently rather than trusting a package because it lives in the same repository. This is an engineering analogy, not a claim that BOT 2.0 implements a certified zero-trust architecture. [R19-S03]

## Meaning of a non-authoritative observation/prediction boundary

A future review needs evidence that observation identity includes instrument and exact contract, session interpretation, event/bar meaning, causal availability, missingness/freshness, schema version and lineage. Prediction identity should distinguish originating observation, model/preprocessor/calibrator versions, horizon and target semantics, uncertainty/abstention validity and production time. These are categories of evidence, not a finalized message schema or temporal contract.

`trading_authority=false` should remain an explicit declaration of scope, with no facility for the research producer to upgrade it. Missing, malformed, contradictory or unfamiliar authority metadata must not be interpreted as permission. However, the critical preservation property is external: no order endpoint, credentials, shared writable operational state or consumer that turns these records into proposals. A boolean cannot enforce that property by itself. The audit's existing research flags and scoped paper permissions must not be conflated. [R19-S01]

A versioned interface must cover semantics as well as field types: calendar-open versus first-observed-open; event-time versus arrival-time; exact versus nearest synchronization; contract identity; unavailable versus zero; research record versus accounting event. Protocol Buffers documentation illustrates that even wire-safe changes can break application behavior. It is a compatibility example, not a recommendation to adopt Protocol Buffers. [R19-S05]

Any future adapter must have limited responsibility and explicit provenance for translation. It must not repair missing data, fit a scaler, consult future targets, open protected archives, rewrite manifests, or import execution authority as an undocumented convenience. No adapter is defined here.

## Failure containment, rollback and fallback

Preservation should be assessed against concrete failure classes before a later integration authorization:

| Failure class | Desired containment outcome | Evidence missing today |
|---|---|---|
| Research crash, timeout or malformed output | Research becomes unavailable; BOT 2.0's independent state and decisions do not depend on recovery. | Consumer dependency graph and actual runtime authority. |
| CPU/GPU/memory/disk exhaustion or log storm | Research load cannot consume resources reserved for operational ingestion/control. | Capacity, resource ownership and isolation behavior. |
| Data source outage or stale/missing input | Research marks unavailable or stops; it cannot change the source, fill gaps or request operational restart. | Proven feed/interface ownership and availability semantics. |
| Wrong schema/model/preprocessor combination | No consumption as an approved research record; no operational route exists. | Compatibility, version selection and approval records. |
| Unexpected import/config/credential inheritance | Resource access remains denied outside the approved research scope. | Import effects and effective permissions; neither examined here. |
| Restart after deliberate disable | Research remains disabled until separately authorized; supervisor cannot recreate authority. | Supervisor ownership and persisted enable/disable behavior. |
| Duplicate or delayed shadow output | It remains a research record and cannot become a duplicate order or ledger entry. | End-to-end consumer behavior. |
| Provenance challenge | Affected research is quarantined; BOT 2.0 frozen restrictions remain unchanged. | Resolved incident boundary and approved scientific source. |

Bulkhead guidance motivates separating scarce-resource pools so one workload cannot cause cascading failure. Applied here, independent logs and processes need accompanying resource ownership; shared disks and feeds still create coupling. [R19-S04]

Rollback at this boundary means withdrawal of BOT 2.1 research consumption/production and preservation of its audit history. It does not mean restoring a BOT 2.0 Git checkout, modifying the dirty worktree, rolling a ledger backward or reinstalling its environment. Fallback means research unavailable or the prior independently approved operational state continuing under its own controls. It must never mean bypassing abstention, selecting an unapproved model, loosening risk, or auto-enabling paper/live execution. No current stable BOT 2.0 baseline has been established, so “fall back to BOT 2.0” is not presently a verified deployment promise. [R19-S01]

## Gates for later consideration, not actions authorized now

1. Establish owner-approved BOT 2.0 baseline custody that includes dirty working-copy changes; retain incident/protocol restrictions. A commit ID alone is insufficient.
2. Establish a clean scientific-source authority and partition-access policy without inspecting protected results to manufacture certainty.
3. Independently review semantic compatibility of ingestion, temporal identity, features, targets and preprocessing; preserve prior meanings and versions.
4. Review effective permissions, environment/config inheritance, output destinations, credentials, network authority, resource contention and supervisor ownership.
5. Demonstrate, only under future explicit authorization, failure containment, rejection of incompatible records and independent disable/rollback. No tests or demonstrations were run here.
6. Keep any future shadow, paper or execution gate separate. Success at a preservation gate cannot grant trading authority.

The largest uncertainty is actual transitive/runtime authority: the audit does not prove effective ACLs, process identity, scheduler behavior, config resolution, source access or broker availability. The unresolved scientific provenance boundary is an independent blocker. Public documentation cannot resolve either local uncertainty.

## Sources

All public sources below were consulted on 2026-09-24. Official living documentation was checked as available through that date; older foundational documents are retained where applicable. No claim is made of an exhaustive survey or 2026 experimental validation. No peer-reviewed empirical paper is required to infer this preservation boundary; the six public sources are official methodology/technical documentation, not BOT-specific validation.

### R19-S01
- Title: BOT 2.0 — Current-State Master Architecture & Capability Audit.
- Author/organization: local BOT 2.0 audit coordinator; individual author not independently verified.
- Year/date and venue: 2026-09-24; repository internal audit.
- Location: `C:/Users/fjone/hyperliquid-trading-bot-phase5c-v3/docs/BOT2_CURRENT_STATE_MASTER_AUDIT.md`.
- Type/review status: internal static architecture audit, not peer reviewed; some market-data review delegated per its own account.
- Finding: mixed adjacent research/operational components, dirty baseline, protected Phase 5C paused, uncertain runtime readiness and provenance; identifies preservation and reuse zones.
- Limitation: no present execution verification, no protected artifact access, no proof of effective runtime permissions or historical non-exposure; R19 relies on audit rather than raw source.
- Relevance: sole internal factual basis for the component map and local risk assessment.

### R19-S02
- Title: venv — Creation of virtual environments.
- Author/organization: Python Software Foundation and Python documentation contributors.
- Year/version and venue: living Python 3 standard-library documentation, accessed 2026; no fixed article year asserted.
- URL: https://docs.python.org/3/library/venv.html
- Type/review status: official technical documentation; not an academic peer-reviewed study.
- Finding: virtual environments have independent installed packages and a base interpreter; environments are generally recreated rather than moved/copied.
- Limitation: package isolation is not a claim of filesystem, credential, network or kernel containment.
- Relevance: separate dependency environments are necessary hygiene but cannot establish the preservation boundary alone.

### R19-S03
- Title: Zero Trust Architecture, NIST SP 800-207.
- Authors/organization: Scott Rose, Oliver Borchert, Stu Mitchell, Sean Connelly; NIST.
- Year/venue: 2020, final 11 August; NIST Special Publication.
- URL/DOI: https://csrc.nist.gov/pubs/sp/800/207/final ; https://doi.org/10.6028/NIST.SP.800-207
- Type/review status: official government architecture guidance; public standards-development review, not a journal experiment.
- Finding: location or ownership alone confers no implicit trust; resource access requires distinct authentication and authorization.
- Limitation: enterprise architecture guidance does not certify BOT permissions or prescribe this project's process topology.
- Relevance: supports independent resource-authority boundaries rather than trusting repository/package membership.

### R19-S04
- Title: Bulkhead pattern.
- Author/organization: Microsoft Azure Architecture Center.
- Year/venue: living official architecture guidance, consulted 2026; fixed original publication year not established.
- URL: https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead
- Type/review status: official engineering pattern documentation; not academic peer reviewed.
- Finding: separating workload/resource pools can prevent a failing or overloaded consumer from causing cascading resource failure.
- Limitation: architectural pattern and tradeoffs, not a measured guarantee for this machine or application.
- Relevance: motivates independent resource and failure domains, including logs, storage and feed consumers.

### R19-S05
- Title: Language Guide (proto 3), Updating A Message Type.
- Author/organization: Google / Protocol Buffers documentation contributors.
- Year/venue: living official Protocol Buffers documentation, consulted 2026; fixed article year not established.
- URL: https://protobuf.dev/programming-guides/proto3/#updating
- Type/review status: official format/language documentation, not peer-reviewed empirical research.
- Finding: wire compatibility and application compatibility differ; safe changes depend on format and consumer behavior.
- Limitation: Protobuf-specific rules do not directly govern existing JSON/Python contracts or establish scientific semantic equivalence.
- Relevance: evidence for reviewing versioned interface meaning and consumer behavior, without selecting a serialization technology.

### R19-S06
- Title: Secure Windows containers.
- Author/organization: Microsoft Learn, Windows containers documentation.
- Year/venue: living official technical documentation, consulted 2026; fixed article year not established.
- URL: https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/container-security
- Type/review status: official security documentation; not academic peer reviewed.
- Finding: process-isolated containers share host-kernel exposure; hypervisor-isolated containers provide a stronger security boundary.
- Limitation: container guidance does not prove platform support, deployment fitness or operational isolation on the audited Windows host.
- Relevance: prevents overstating a separate process/container as complete containment; technology choice remains future work.

### R19-S07
- Title: PROV-Overview — An Overview of the PROV Family of Documents.
- Editors/organization: Paul Groth and Luc Moreau; W3C Provenance Working Group.
- Year/venue: 2013-04-30, W3C Working Group Note.
- URL: https://www.w3.org/TR/prov-overview/
- Type/review status: official non-normative standards-family overview; Working Group Note, not itself a W3C Recommendation or academic peer-reviewed result.
- Finding: provenance describes entities, activities and agents and supports representation of attribution, derivation, versioning and provenance of provenance.
- Limitation: representing provenance cannot prove the truth or completeness of an asserted custody/contamination history.
- Relevance: a new manifest namespace or matching digest cannot, by itself, repair BOT 2.0's unresolved scientific-source authority.

## Independence, safety and freeze attestation

I read the current user instruction attachment and the mandatory audit. I did not read the old R16–R19 reports, any new R16/R17/R18 report, any master synthesis, or frozen R1–R15. The existing R19 draft was preserved using a byte copy without text inspection; both original and preservation copy matched SHA-256 `E702BC49C9AE455BC4F344990DBD98F77F6ACCAC65C34A1A6528C30223B73702` before replacement. The preservation copy is `R19_PRE_BATCH2_COORDINATOR_DRAFT.md`; it is not evidence for these conclusions.

Research-document writes were limited to that preservation copy and this report under `docs/bot21_research/`. No source/configuration/data/model/manifest/risk/execution/paper/ledger/protected output was modified or inspected directly. No protected OOS or protected scoring, training, inference, tests, experiments, backtests, trading, broker connections, package installation, environment/CUDA/driver changes, Git mutation, adapter creation, or BOT 2.1 implementation occurred. Web research visited public documentation only. No subagent was spawned by R19.

Completion is an independent conceptual first-pass completion, not a certification of operational safety or readiness. The report is frozen on final save. Its SHA-256 is computed externally after saving and returned in the specialist handoff, avoiding a self-referential embedded digest. No source registry or other report was modified by R19. R20 and X1–X8 remain unauthorized and unstarted.