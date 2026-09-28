"""Read-only Phase 5B real-data validation/target analysis (no model scoring)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.core_v1.production_adapters import PassBV3ArchiveAdapter
from bot2.data_foundation.contracts import MarketEvent
from bot2.data_foundation.instruments import normalize_contract
from bot2.data_foundation.sync import synchronize_contract_roots
from bot2.data_foundation.validation import validate_events
from bot2.features_labels.targets_v3 import HORIZONS_MINUTES, TARGET_SPEC, TARGET_VERSION, generate_future_targets

SPLITS = {
    "TRAIN": (date(2025, 6, 2), date(2025, 12, 31)),
    "VALIDATION": (date(2026, 1, 1), date(2026, 2, 27)),
    "OOS_TEST": (date(2026, 3, 1), date(2026, 8, 26)),
}


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position); high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def load_events(market: str, common: dict):
    adapter = PassBV3ArchiveAdapter(market=market, **common)
    metadata = adapter.validate()
    events: list[MarketEvent] = []
    grouped = defaultdict(list)
    for item in adapter.iter_events():
        bar = item.bar
        event = MarketEvent(bar.instrument_id, "CME", "OHLCV_1M_BAR_CLOSE", bar.close_time,
            None, float(bar.close), float(bar.volume), sequence=bar.sequence,
            event_id=bar.id, session_id=bar.session_id, contract_id=bar.contract_id,
            timestamp_source="HISTORICAL_EXCHANGE_EVENT")
        events.append(event); grouped[(event.instrument, event.session_id)].append(event)
    # Validate each exact contract/session with no synthetic receipt clock.
    reason_counts = Counter(); event_hashes = []
    for key in sorted(grouped):
        rows = grouped[key]
        accepted, quality = validate_events(rows, as_of=rows[-1].exchange_time,
            max_age=timedelta(days=1000))
        reason_counts.update(quality.reason_counts)
        event_hashes.append((key, quality.event_hash))
    events.sort(key=lambda event: (event.exchange_time, event.instrument))
    quality_all, report = validate_events(events, as_of=events[-1].exchange_time,
        max_age=timedelta(days=1000))
    if len(quality_all) != len(events):
        raise AssertionError("Phase 1 validation unexpectedly dropped historical rows")
    return adapter, metadata, events, report, event_hashes


def split_for(session_id: str) -> str | None:
    session_date = date.fromisoformat(session_id)
    for name, (start, end) in SPLITS.items():
        if start <= session_date <= end:
            return name
    return None


def target_distributions(events_by_contract: dict[str, list[MarketEvent]]):
    out = {"volatility_reference": "prior 30 consecutive same-session/same-contract 1m returns; ratio thresholds <0.8/0.8-1.2/>1.2", "distributions": {}, "stability": {}, "session_dependence": {},
           "severe_imbalance_cells": []}
    for horizon in HORIZONS_MINUTES:
        targets = generate_future_targets(events_by_contract, horizons=(horizon,))
        metrics = ("future_direction", "future_volatility_state", "future_structure")
        for root in ("ES", "NQ"):
            for split in SPLITS:
                selected = [row for row in targets if row.root_symbol == root and split_for(row.session_id) == split]
                valid = [row for row in selected if row.validity == "VALID"]
                record = {"observations": len(selected), "valid": len(valid),
                          "invalid_observations": len(selected) - len(valid),
                          "invalid_reasons": dict(sorted(Counter(code for row in selected if row.validity != "VALID" for code in row.reason_codes).items()))}
                for metric in metrics:
                    distribution = Counter(getattr(row, metric) for row in valid)
                    record[metric] = dict(sorted(distribution.items()))
                    total = sum(distribution.values())
                    shares = {key: value / total for key, value in distribution.items()} if total else {}
                    record[metric + "_shares"] = shares
                    if (len(distribution) < 2 or (shares and max(shares.values()) >= .95)
                            or (shares and min(shares.values()) < .01)):
                        out["severe_imbalance_cells"].append({"root": root, "split": split,
                            "horizon_minutes": horizon, "target": metric, "shares": shares})
                out["distributions"][f"{root}:{split}:{horizon}m"] = record

            root_rows = [row for row in targets if row.root_symbol == root and row.validity == "VALID"]
            root_rows.sort(key=lambda row: (row.instrument, row.session_id, row.observation_time))
            for metric in metrics:
                pairs = same_pairs = changes = 0
                previous = None
                for row in root_rows:
                    key = (row.instrument, row.session_id)
                    time = row.observation_time
                    if previous is not None and previous[0] == key:
                        from datetime import datetime
                        last_time = datetime.fromisoformat(previous[1].replace("Z", "+00:00"))
                        now = datetime.fromisoformat(time.replace("Z", "+00:00"))
                        if now - last_time == timedelta(minutes=1):
                            pairs += 1
                            if getattr(row, metric) == previous[2]: same_pairs += 1
                            else: changes += 1
                    previous = (key, time, getattr(row, metric))
                out["stability"][f"{root}:{horizon}m:{metric}"] = {
                    "adjacent_pairs": pairs, "persistent_pairs": same_pairs,
                    "transitions": changes, "persistence_rate": same_pairs / pairs if pairs else None,
                    "transition_rate": changes / pairs if pairs else None}

            # Broad session-location dependence based on the first/last observed
            # archive bar of each exact contract/session (no calendar guess).
            bounds = {}
            for contract, rows in events_by_contract.items():
                if normalize_contract(contract, rows[0].contract_id or contract,
                        reference_date=rows[0].exchange_time.date()).root_symbol != root:
                    continue
                by_session = defaultdict(list)
                for event in rows: by_session[event.session_id].append(event.exchange_time)
                for session_id, times in by_session.items():
                    bounds[(contract, session_id)] = (min(times), max(times))
            segment_counts = defaultdict(Counter)
            from datetime import datetime
            for row in root_rows:
                begin, end = bounds[(row.instrument, row.session_id)]
                now = datetime.fromisoformat(row.observation_time.replace("Z", "+00:00"))
                elapsed = (now - begin).total_seconds() / 60
                remaining = (end - now).total_seconds() / 60
                segment = "FIRST_120_MIN" if elapsed < 120 else "LAST_120_MIN" if remaining < 120 else "MIDDLE"
                for metric in metrics: segment_counts[(segment, metric)][getattr(row, metric)] += 1
            for (segment, metric), counts in segment_counts.items():
                out["session_dependence"][f"{root}:{horizon}m:{segment}:{metric}"] = dict(sorted(counts.items()))
    return out


def build_analysis() -> tuple[dict, dict, dict]:
    common = dict(repository_root=ROOT, archive_root=ROOT / "data/backtests/es_nq_pass_b_archive_3",
        plan_root=ROOT / "data/backtests/es_nq_pass_b_plan_3",
        continuation_root=ROOT / "data/backtests/es_nq_pass_b_continuation_plan_1",
        final_audit_path=ROOT / "outputs/archive_audits/es_nq_pass_b_final_audit.json")
    per_market = {}; all_events = {}; event_hashes = {}
    for market in ("ES", "NQ"):
        adapter, metadata, events, quality, group_hashes = load_events(market, common)
        all_events[market] = events; event_hashes[market] = quality.event_hash
        by_contract = defaultdict(list)
        for event in events: by_contract[event.instrument].append(event)
        contract_stats = {}
        for contract, rows in sorted(by_contract.items()):
            identity = normalize_contract(contract, rows[0].contract_id or contract,
                reference_date=rows[0].exchange_time.date())
            contract_stats[contract] = {"root_symbol": identity.root_symbol, "expiry": identity.expiry,
                "instrument_id": identity.instrument_id, "rows": len(rows),
                "sessions": len({event.session_id for event in rows}),
                "first_session": min(event.session_id for event in rows),
                "last_session": max(event.session_id for event in rows)}
        per_market[market] = {"dataset_id": metadata.dataset_id,
            "archive_fingerprint": metadata.dataset_fingerprint,
            "source_archive_sha256": metadata.lineage.archive_sha256,
            "promoted_audit_sha256": metadata.lineage.manifest_sha256,
            "calendar_sha256": metadata.lineage.calendar_sha256,
            "rollover_sha256": metadata.lineage.rollover_sha256,
            "eligibility": metadata.eligibility.classification,
            "rows": len(events), "sessions": len({event.session_id for event in events}),
            "event_timestamp_start": events[0].exchange_time.isoformat().replace("+00:00", "Z"),
            "event_timestamp_end": events[-1].exchange_time.isoformat().replace("+00:00", "Z"),
            "receive_timestamp_available": False, "receive_timestamp_count": 0,
            "phase1_event_hash": quality.event_hash,
            "phase1_validated_rows": quality.accepted_events,
            "phase1_quality_reasons": dict(quality.reason_counts),
            "data_quality_episodes": len(adapter.data_quality_events),
            "missing_aggregate_minutes": sum(q.missing_intervals for q in adapter.data_quality_events),
            "contract_inventory": contract_stats}

    pairs, sync = synchronize_contract_roots(all_events["ES"], all_events["NQ"])
    root_groups = {}
    for market in ("ES", "NQ"):
        for event in all_events[market]: root_groups[event.instrument] = market
    group_events = {contract: [event for event in all_events[root]
                        if event.instrument == contract]
                    for contract, root in root_groups.items()}
    target_stats = target_distributions(group_events)
    rollovers = json.loads((common["plan_root"] / "rollovers.json").read_text(encoding="utf-8"))
    roll_report = {}
    effective_sessions = set()
    for market, detail in rollovers["markets"].items():
        roll_report[market] = [{"decision_session": row["decision_session"],
            "effective_session": row["effective_session"], "decision_time": row["decision_time"],
            "outgoing_id": row["outgoing_id"], "incoming_id": row["incoming_id"],
            "method": row["method"], "no_lookahead": row["no_lookahead"],
            "evidence_sessions": sorted({e["session"] for e in row["evidence"]}),
            "evidence_contracts": sorted({e["ticker"] for e in row["evidence"]})}
            for row in detail["decisions"]]
        effective_sessions.update(row["effective_session"] for row in detail["decisions"])
    es_keys = {(e.session_id, e.exchange_time) for e in all_events["ES"]}
    nq_keys = {(e.session_id, e.exchange_time) for e in all_events["NQ"]}
    unmatched_es = es_keys - nq_keys; unmatched_nq = nq_keys - es_keys
    boundary_es = sum(session in effective_sessions for session, _ in unmatched_es)
    boundary_nq = sum(session in effective_sessions for session, _ in unmatched_nq)
    manifest = {"manifest_schema_version": "bot2-real-research-dataset-manifest-v2",
        "source": "Databento promoted ES/NQ Pass B v3 archive; historical exchange event timestamps only",
        "code_commit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "session_count": len({event.session_id for event in all_events["ES"]} &
                             {event.session_id for event in all_events["NQ"]}),
        "date_range": ["2025-06-02", "2026-08-26"], "markets": per_market,
        "exact_aligned_rows": sync.exact_matches, "unmatched_es": sync.es_unmatched,
        "unmatched_nq": sync.nq_unmatched, "es_match_rate": sync.es_match_rate,
        "nq_match_rate": sync.nq_match_rate,
        "unmatched_on_roll_effective_sessions": {"ES": boundary_es, "NQ": boundary_nq},
        "contract_expiry_mismatch_aligned_pairs": sync.contract_expiry_mismatch_pairs,
        "session_mismatch_event_count": sync.session_mismatch_events,
        "contract_policy": "No continuous series. Frozen active-window rollover metadata OWNER_TWO_SESSION_VOLUME_CROSSOVER_SPARSE_V2 selects the active listed contract per session; original OHLCV and contract IDs remain unchanged.",
        "roll_transitions": roll_report,
        "timestamp_provenance": {"event_timestamp": "normalized one-minute bar close timestamp from exchange event window", "receive_timestamp_available": False, "source": "HISTORICAL_EXCHANGE_EVENT"},
        "feature_version": "bot2-feature-registry-v2", "target_version": TARGET_VERSION,
        "target_horizons_minutes": list(HORIZONS_MINUTES), "target_spec_sha256": canonical_hash(TARGET_SPEC),
        "target_distributions_sha256": canonical_hash(target_stats),
        "phase1_event_hashes": event_hashes,
        "trading_authority": False}
    manifest["manifest_hashing"] = "SHA-256 canonical sorted compact JSON excluding manifest_sha256 field"
    manifest["manifest_sha256"] = canonical_hash(manifest)
    phase5c = {"schema_version": "bot2-phase5c-experiment-manifest-v1",
        "experiment_id": "bot2-phase5c-future-state-esnq-v1",
        "created_before_model_evaluation": True,
        "source_dataset_manifest_sha256": manifest["manifest_sha256"],
        "code_commit": manifest["code_commit"],
        "feature_version": manifest["feature_version"], "target_version": manifest["target_version"],
        "target_spec": TARGET_SPEC, "target_spec_sha256": manifest["target_spec_sha256"],
        "volatility_reference": target_stats["volatility_reference"],
        "split_dates_inclusive": {name: [start.isoformat(), end.isoformat()] for name, (start, end) in SPLITS.items()},
        "purge_minutes": 30, "embargo_minutes": 30,
        "random_seeds": [1, 2, 3], "sequence_lengths": [8],
        "candidate_models": ["A0_PREVIOUS_LABEL_PERSISTENCE", "A0_TRAIN_MAJORITY", "A0_TRAIN_TRANSITION_MATRIX", "A1_NUMPY_MULTIHEAD_MLP", "A2_FIXED_CAUSAL_TEMPORAL_TRANSFORM_PLUS_MLP"],
        "baseline_specifications": {
            "A0_PREVIOUS_LABEL_PERSISTENCE": "For each target head, carry forward the most recent label whose full information interval ended no later than the prediction observation time; abstain if unavailable.",
            "A0_TRAIN_MAJORITY": "Per root/head/horizon majority class computed from TRAIN labels only; class tie-break is lexical.",
            "A0_TRAIN_TRANSITION_MATRIX": "One-step target-state transition probabilities estimated from TRAIN only with fixed Laplace alpha=1 smoothing; condition on the most recent eligible past label, never a future-overlapping label."
        },
        "no_skill_references": ["TRAIN_MAJORITY", "UNIFORM_PROBABILITY"],
        "metrics": ["log_loss", "brier_score", "balanced_accuracy", "macro_precision", "macro_recall", "macro_f1", "confusion_matrix", "reliability", "coverage_vs_reliability", "latency_p50_p95_p99_max"],
        "calibration": "Temperature scaling fitted only on validation targets; no OOS fitting.",
        "oos_model_scoring_performed": False, "requires_separate_architecture_review_before_oos": True,
        "trading_authority": False}
    phase5c["manifest_hashing"] = "SHA-256 canonical sorted compact JSON excluding manifest_sha256 field"
    phase5c["manifest_sha256"] = canonical_hash(phase5c)
    return manifest, target_stats, phase5c


def main():
    manifest, stats, phase5c = build_analysis()
    output = ROOT / "outputs" / "bot2_phase5b"
    output.mkdir(parents=True, exist_ok=True)
    (output / "target_distributions_v3.json").write_text(json.dumps(stats, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "real_es_nq_research_dataset_manifest_v2.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (ROOT / "config" / "bot2_phase5c_experiment_manifest_v1.json").write_text(json.dumps(phase5c, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dataset_manifest_sha256": manifest["manifest_sha256"],
        "phase5c_manifest_sha256": phase5c["manifest_sha256"],
        "es_rows": manifest["markets"]["ES"]["rows"], "nq_rows": manifest["markets"]["NQ"]["rows"],
        "aligned": manifest["exact_aligned_rows"], "match_es": manifest["es_match_rate"],
        "match_nq": manifest["nq_match_rate"], "cutpoints": stats["cutpoints"],
        "severe_imbalance_cells": len(stats["severe_imbalance_cells"])}, sort_keys=True))


if __name__ == "__main__":
    main()
