# V2 Order Ledger Transition Matrix

Ledger version: `order-ledger-v2-1`. Any cell not listed is rejected with
`INVALID_ORDER_TRANSITION` or a more precise terminal/fill reason.

| Current state | Accepted event kinds | Result |
|---|---|---|
| `CREATED` | `SUBMIT`, `FORCED_CLOSE_INTENT` | `SUBMITTED` |
| `SUBMITTED` | `ACCEPT` | `ACCEPTED`; requested quantity becomes accepted/remaining |
| `SUBMITTED` | `REJECT` | `REJECTED` |
| `ACCEPTED` | `ACTIVATE` | `ACTIVE`, with exact-contract eligibility |
| `ACCEPTED` | `REJECT`, cancel request/cancel | respective terminal/request state |
| `ACTIVE` | `TRIGGER` | `TRIGGERED`, stop orders only |
| `ACTIVE`, `TRIGGERED`, `PARTIALLY_FILLED`, `CANCEL_REQUESTED` | `FILL` | partial or filled; stop requires trigger |
| `ACTIVE`, `TRIGGERED` | `EXECUTION_EVALUATED` | IOC residual cancelled |
| eligible nonterminal | `CANCEL_REQUEST` | `CANCEL_REQUESTED` |
| accepted/active/triggered/partial/requested | `CANCEL` | `CANCELLED` |
| active/triggered/partial/requested | `EXPIRE` | `EXPIRED`; DAY/session or GTC/contract proof required |
| active/triggered/partial | `REPLACE` | parent `REPLACED`, linked child `CREATED` |

Terminal states `FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`, and `REPLACED` have no outgoing edges.
Stop-limit fill time must be later than its trigger transition. IOC partial fill emits a partial-fill
transition followed by residual cancellation under the same event with deterministic ordinals.

Equal logical timestamps order by event priority and then lexical event SHA-256: submit/forced intent,
accept, reject, activate, cancel request, cancel, replace, expiry, trigger, fill/evaluation. A stream
not already in this order rejects; the ledger never uses arrival order or thread scheduling.
