# V2 Phase 3 Conservative OHLC Execution Report

Phase 3 implements the frozen `CONSERVATIVE_OHLC_1M_V1` and
`BAR_VOLUME_PARTICIPATION_V1` policies. It consumes immutable Phase 1 instrument facts and the Phase
2 ledger and returns immutable execution facts plus a new ledger. It does not mutate its inputs.

Implemented behavior:

- strict finalized, UTC, aligned one-minute bars and availability-time no-look-ahead;
- exact market/instrument/contract/version lineage and instrument effective intervals;
- market fills at the next eligible open plus adverse slippage;
- limit fills at the frozen limit without favorable improvement;
- stop-market gap/open and threshold behavior;
- stop-limit trigger/fill separation across distinct eligible bars;
- exact Decimal adverse tick rounding;
- shared volume budget with quantity-step flooring and deterministic declared priority;
- zero-volume no-fill and missing-volume fail-closed behavior;
- IOC first-eligible-bar cancellation;
- adverse protective collision resolution and explicit ambiguity rejection;
- immutable trigger, fill, policy, allocation, bar, and ledger lineage;
- cryptographically bound finalized source-bar, strategy-action, order, and ledger-activation
  lineage, with same-source and unavailable-source execution rejected;
- deterministic replay, duplicate prevention through Phase 2 identities, and input immutability.

Execution timestamps use the bar's immutable `available_at` boundary because OHLC cannot prove an
intrabar timestamp. The economic reference remains separately recorded. This prevents invented
intrabar paths and future visibility.

Phase 3 does not calculate fees, commissions, PnL, cash, margin, funding, positions, liquidation,
risk authorization, strategy actions, or provider/exchange activity. Those boundaries remain owned
by later phases. Core v1 is unchanged.
