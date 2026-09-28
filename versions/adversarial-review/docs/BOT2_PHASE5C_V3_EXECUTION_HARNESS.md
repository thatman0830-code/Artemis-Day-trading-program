# BOT 2.0 Phase 5C v3 Execution Harness

## Current state: preflight only

The only CLI entry point is `scripts/run_phase5c_v3_preflight.py`; `--dry-run` is required. The program has no model-evaluation command and writes no score artifacts. A successful result means only `PREFLIGHT_READY_NO_SCORING`; it is not approval to train, evaluate, or trade.

Preflight verifies v3's canonical hash and closed authority flags; the untouched v2 canonical hash; the source dataset manifest and eligibility report hashes; feature-registry and target-spec hashes; ES/NQ payload presence; full archive report/tree hash and per-file hash/size entries; sequence/cadence evidence; contract inventory; exact-session ES/NQ alignment and no-forward-fill evidence; frozen temporal splits; purge/embargo; A2 architecture/parameter count/receptive field; training configuration and seeds; calibration/abstention partitions; train-only shuffle controls; ablation IDs; primary metrics; append-only output destination; and that scoring/trading permissions remain false.

Every failure is reported as a machine-readable `{check, status, reason_code}` object and returns `PREFLIGHT_BLOCKED`; the CLI exits nonzero. The output directory is `outputs/bot2_phase5c_v3/results` and must be absent or empty for this dry run. No file is written there by preflight.

The dataset payload and final Pass B archive were independently checked read-only against the frozen final archive audit fingerprint `405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b`; the archive audit reported `FINAL_ES_NQ_ARCHIVE_AUDIT_PASS`, 130 requests, 877,679 normalized rows, no duplicate rows, no synthesized rows, and no continuous-price adjustment. Its classified missing-minute/quality episodes remain subject to the already-frozen eligibility report; this does not imply every minute is populated.

No scoring, OOS labels/metrics, or model results are read or produced. Independent review is still required. Only after review and a separate user authorization can an evaluation harness be designed; do not proceed to Phase 5C scoring or trading from this preflight result.
