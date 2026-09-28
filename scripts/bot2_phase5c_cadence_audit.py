"""Read-only Phase 5C-P cadence/eligibility audit; never fits or scores models."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.core_v1.production_adapters import PassBV3ArchiveAdapter
from bot2.data_foundation.cadence import audit_cadence
from bot2.data_foundation.contracts import MarketEvent
from bot2.data_foundation.instruments import normalize_contract
from bot2.data_foundation.sync import synchronize_contract_roots
from bot2.features_labels.features import FEATURE_NAMES_V3, generate_features
from bot2.features_labels.targets_v3 import HORIZONS_MINUTES, generate_future_targets
from bot2.neural.sequences import build_sequences

DATASET_SHA256 = "e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67"
COMMON = {
    "repository_root": ROOT,
    "archive_root": ROOT / "data/backtests/es_nq_pass_b_archive_3",
    "plan_root": ROOT / "data/backtests/es_nq_pass_b_plan_3",
    "continuation_root": ROOT / "data/backtests/es_nq_pass_b_continuation_plan_1",
    "final_audit_path": ROOT / "outputs/archive_audits/es_nq_pass_b_final_audit.json",
}
CODE_MAP = {
    "future_direction": {"DOWN": 0, "FLAT": 1, "UP": 2},
    "future_volatility_state": {"LOW": 0, "NORMAL": 1, "HIGH": 2},
    "future_structure": {"RANGE": 0, "TRANSITION": 1, "TREND": 2},
}


def load_market(root: str):
    adapter = PassBV3ArchiveAdapter(market=root, **COMMON)
    metadata = adapter.validate()
    events: list[MarketEvent] = []
    for item in adapter.iter_events():
        bar = item.bar
        events.append(MarketEvent(bar.instrument_id, "CME", "OHLCV_1M_BAR_CLOSE",
            bar.close_time, None, float(bar.close), float(bar.volume), sequence=bar.sequence,
            event_id=bar.id, session_id=bar.session_id, contract_id=bar.contract_id,
            timestamp_source="HISTORICAL_EXCHANGE_EVENT"))
    return adapter, metadata, events


def run() -> dict:
    by_root: dict[str, list[MarketEvent]] = {}
    adapters = {}
    metadata = {}
    for root in ("ES", "NQ"):
        adapter, meta, events = load_market(root)
        adapters[root], metadata[root], by_root[root] = adapter, meta, events

    pairs, sync = synchronize_contract_roots(by_root["ES"], by_root["NQ"])
    root_groups: dict[str, str] = {}
    grouped: dict[str, dict[tuple[str, str], list[MarketEvent]]] = {"ES": defaultdict(list), "NQ": defaultdict(list)}
    by_root_session: dict[str, dict[str, list[MarketEvent]]] = {"ES": defaultdict(list), "NQ": defaultdict(list)}
    for root, events in by_root.items():
        for event in events:
            identity = normalize_contract(event.instrument, event.contract_id or event.instrument,
                                          reference_date=event.exchange_time.date())
            root_groups[event.instrument] = identity.root_symbol
            grouped[root][(event.instrument, event.session_id or "")].append(event)
            by_root_session[root][event.session_id or ""].append(event)

    calendar = json.loads((COMMON["plan_root"] / "calendar.json").read_text(encoding="utf-8"))
    active_intervals = {
        row["session_date"]: tuple((
            datetime.fromisoformat(interval["start_utc"].replace("Z", "+00:00")).astimezone(timezone.utc),
            datetime.fromisoformat(interval["end_exclusive_utc"].replace("Z", "+00:00")).astimezone(timezone.utc),
        ) for interval in row.get("active_intervals", []))
        for row in calendar["sessions"]
    }

    roots_out = {}
    for root in ("ES", "NQ"):
        events = by_root[root]
        cadence = audit_cadence(events, active_intervals=active_intervals)
        gaps = [gap for gap in cadence.gaps]
        quality_events = adapters[root].data_quality_events
        source_classifications = Counter(q.reason for q in quality_events)
        source_missing = sum(q.missing_intervals for q in quality_events)
        affected_source_sessions = len({q.session_id for q in quality_events})
        total = len(events)
        valid_feature_rows = 0
        feature_reasons: Counter[str] = Counter()
        target_by_horizon = {h: {"total": 0, "valid": 0, "invalid_reasons": Counter()} for h in HORIZONS_MINUTES}
        sequence_by_horizon = {h: {"possible": 0, "eligible": 0, "rejections": Counter()} for h in HORIZONS_MINUTES}

        for (contract, session_id), own_rows in sorted(grouped[root].items()):
            own_rows.sort(key=lambda row: row.exchange_time)
            session_inputs: dict[str, list[MarketEvent]] = {contract: own_rows}
            counterpart_root = "NQ" if root == "ES" else "ES"
            other_rows = by_root_session[counterpart_root].get(session_id, [])
            session_inputs.update({row.instrument: [] for row in other_rows})
            for row in other_rows:
                session_inputs[row.instrument].append(row)
            session_roots = {instrument: root_groups[instrument] for instrument in session_inputs}
            features = generate_features(session_inputs, source_dataset_id="phase5b-esnq-passb-v3",
                source_dataset_sha256=DATASET_SHA256, root_groups=session_roots)
            feature_by_time = {row.observation_time: row for row in features if row.instrument == contract}
            valid_feature_rows += sum(all(feature_by_time[e.exchange_time.isoformat().replace("+00:00", "Z")]
                .values.get(name) is not None for name in FEATURE_NAMES_V3) for e in own_rows)
            for row in feature_by_time.values():
                if any(row.values.get(name) is None for name in FEATURE_NAMES_V3):
                    feature_reasons.update(row.reason_codes or ("REQUIRED_FEATURE_UNAVAILABLE",))

            all_targets = generate_future_targets({contract: own_rows}, horizons=HORIZONS_MINUTES)
            targets_by_horizon = {h: {target.observation_time: target for target in all_targets
                if target.horizon_minutes == h} for h in HORIZONS_MINUTES}
            for horizon in HORIZONS_MINUTES:
                target_by_time = targets_by_horizon[horizon]
                target_rows = tuple(target_by_time.values())
                stats = target_by_horizon[horizon]
                for target in target_rows:
                    stats["total"] += 1
                    if target.validity == "VALID":
                        stats["valid"] += 1
                    else:
                        stats["invalid_reasons"].update(target.reason_codes)
                seq_stats = sequence_by_horizon[horizon]
                seq_stats["possible"] += max(0, len(own_rows) - 8 + 1)
                sequence_input = []
                for event in own_rows:
                    stamp = event.exchange_time.isoformat().replace("+00:00", "Z")
                    feature = feature_by_time[stamp]
                    target = target_by_time[stamp]
                    targets = {}
                    if target.validity == "VALID":
                        targets = {name: CODE_MAP[target_name][getattr(target, target_name)]
                            for name, target_name in (("direction", "future_direction"),
                                ("volatility", "future_volatility_state"), ("structure", "future_structure"))}
                    sequence_input.append({"observation_time": stamp, "instrument": contract,
                        "contract_id": event.contract_id, "session_id": session_id,
                        "values": feature.values, "targets": targets})
                batch = build_sequences(sequence_input, sequence_length=8,
                    feature_names=FEATURE_NAMES_V3)
                seq_stats["eligible"] += len(batch.timestamps)
                seq_stats["rejections"].update(batch.rejection_counts)

        source_gap_counts = Counter(str(q.missing_intervals) for q in quality_events)
        roots_out[root] = {
            "total_archive_observations": total,
            "expected_cadence_seconds": cadence.expected_interval_seconds,
            "checked_adjacent_pairs": cadence.checked_adjacent_pairs,
            "expected_calendar_closure_crossings_excluded": cadence.excluded_calendar_boundary_pairs,
            "cadence_valid_observations_after_first_in_session": cadence.cadence_valid_pairs,
            "cadence_invalid_adjacent_pairs": cadence.cadence_invalid_pairs,
            "boundary_first_observations_not_counted_as_pairs": total - cadence.checked_adjacent_pairs,
            "gap_count": cadence.gap_count,
            "missing_interval_count_from_observed_timestamps": cadence.missing_interval_count,
            "gap_sizes_missing_minutes_to_gap_count": dict(sorted(cadence.gap_size_distribution.items(), key=lambda x: int(x[0]))),
            "gap_reason_codes": dict(sorted(cadence.reason_counts.items())),
            "sessions_affected_by_timestamp_gaps": cadence.sessions_affected,
            "archive_source_quality_reason_codes": dict(sorted(source_classifications.items())),
            "archive_source_quality_gap_count": len(quality_events),
            "archive_source_quality_missing_minutes": source_missing,
            "archive_source_quality_gap_sizes": dict(sorted(source_gap_counts.items(), key=lambda x: int(x[0]))),
            "archive_source_quality_sessions_affected": affected_source_sessions,
            "source_gap_semantics_caveat": "SPARSE_NO_ELIGIBLE_TRADE_AGGREGATE does not distinguish no eligible trade from missing source/feed observation; no inference is made.",
            "feature_rows_eligible_all_registered_features": valid_feature_rows,
            "feature_rows_eligible_percent": valid_feature_rows / total * 100 if total else 0,
            "feature_unavailability_reason_codes": dict(sorted(feature_reasons.items())),
            "targets_by_horizon": {str(h): {"total": v["total"], "valid": v["valid"],
                "eligible_percent": v["valid"] / v["total"] * 100 if v["total"] else 0,
                "invalid_reason_codes": dict(sorted(v["invalid_reasons"].items()))}
                for h, v in target_by_horizon.items()},
            "sequence_windows_by_horizon_length_8": {str(h): {"possible": v["possible"],
                "eligible": v["eligible"], "eligible_percent": v["eligible"] / v["possible"] * 100 if v["possible"] else 0,
                "rejection_reason_codes": dict(sorted(v["rejections"].items()))}
                for h, v in sequence_by_horizon.items()},
        }

    matched = sync.exact_matches
    output = {
        "schema_version": "bot2-phase5c-cadence-eligibility-report-v1",
        "dataset_manifest_sha256": DATASET_SHA256,
        "source_archive": "Promoted Databento Pass B v3 normalized OHLCV minute bars; exchange close timestamps; no receipt timestamps",
        "date_range_inclusive": ["2025-06-02", "2026-08-26"],
        "expected_cadence_seconds": 60,
        "cadence_valid_definition": "Within one exact listed contract and explicit source session, consecutive observations have exactly 60 elapsed seconds. The first observation in each session is a boundary, not a pair and is excluded from cadence-pair denominator.",
        "closures_and_boundaries": "Session boundaries, contract roll boundaries, and exchange-calendar closures are not treated as missing bars; checks never cross exact session/contract groups.",
        "no_synthetic_market_data": True,
        "es_nq_exact_alignment": {"exact_session_timestamp_matches": matched,
            "unmatched_es": sync.es_unmatched, "unmatched_nq": sync.nq_unmatched,
            "es_aligned_percent": sync.es_match_rate * 100, "nq_aligned_percent": sync.nq_match_rate * 100,
            "no_forward_fill": sync.no_forward_fill,
            "alignment_requires_same_session_and_exact_timestamp": True},
        "markets": roots_out,
        "method": "Feature and target eligibility only; sequence construction is a deterministic eligibility audit. No baselines or neural models are fitted, no predictions or performance metrics are generated, and no OOS scoring is performed.",
        "trading_authority": False,
    }
    return output


if __name__ == "__main__":
    report = run()
    target = ROOT / "docs/BOT2_PHASE5C_DATA_ELIGIBILITY.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target), "es_rows": report["markets"]["ES"]["total_archive_observations"],
        "nq_rows": report["markets"]["NQ"]["total_archive_observations"],
        "es_feature_eligible_pct": report["markets"]["ES"]["feature_rows_eligible_percent"],
        "nq_feature_eligible_pct": report["markets"]["NQ"]["feature_rows_eligible_percent"],
        "aligned_pct": report["es_nq_exact_alignment"]["es_aligned_percent"]}, sort_keys=True))
