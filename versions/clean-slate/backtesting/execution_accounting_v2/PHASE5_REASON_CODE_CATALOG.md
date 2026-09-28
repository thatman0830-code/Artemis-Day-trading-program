# Phase 5 Reason Codes

The machine values are the `RiskReason` enum in `risk_sessions.py`. Categories are: verified-session
absence/overlap/eligibility; missing/stale/mismatched identity or version; gross, net, position,
concentration, leverage, initial-margin, maintenance-margin, session-loss and drawdown limits;
reference reset/chronology; duplicate conflict/tamper; later-bar eligibility; session-flatten
deadline; and explicit end-of-data residual state. `OK` is the only allow reason.

