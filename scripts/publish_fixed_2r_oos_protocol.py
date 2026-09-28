"""Pre-register the untouched fixed-2R shadow comparison; grants no authority."""
from pathlib import Path
import json
import os
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    document = {"schema_version": "fixed-2r-shadow-oos-protocol-v1",
        "state": "PRE_REGISTERED_AWAITING_OOS_DATA",
        "development_evidence_days_utc": ["2026-09-04", "2026-09-07", "2026-09-08",
                                            "2026-09-09", "2026-09-10"],
        "untouched_oos_days": ["2026-09-14", "2026-09-15", "2026-09-16",
                               "2026-09-17", "2026-09-18"],
        "signal_source": "EXPERIMENTAL_MAJOR_SINGLE_GLOBEX_PDH_PDL_V1",
        "entry_and_stop_policy": "UNCHANGED_CANONICAL_DOWNSTREAM_FACTS",
        "target_policy": {"type": "FIXED_R_MULTIPLE", "r_multiple": "2.0",
                          "partial_exits": False, "trailing_stop": False},
        "lifecycle_policy": {"maximum_holding_bars": 30,
                             "bar_timeframe": "1m", "ambiguous_bar": "STOP_FIRST"},
        "profiles": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"],
        "promotion_requirements": {"all_oos_days_complete": True,
            "minimum_completed_trades": 20, "positive_net_expectancy_after_costs": True,
            "maximum_drawdown_within_profile_limit": True,
            "no_automatic_winner_selection": True, "owner_review_required": True},
        "development_only_observation": {"fixed_2r_30_bar_target_count": 11,
            "fixed_2r_30_bar_stop_count": 8, "unresolved_count": 9,
            "waiting_entry_count": 1,
            "warning": "HYPOTHESIS_FORMATION_ONLY_NOT_PERFORMANCE_VALIDATION"},
        "canonical_policy_changed": False, "approved": False,
        "comparison_only": True, "paper_execution_permitted": False,
        "live_trading_permitted": False, "trading_authority": False}
    target = ROOT / "outputs/experimental_target_five_day/fixed-2r-oos-protocol.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x") as stream:
            json.dump(document, stream, sort_keys=True, separators=(",", ":"))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"schema_version": document["schema_version"],
        "state": document["state"], "untouched_oos_days": document["untouched_oos_days"],
        "paper_execution_permitted": False, "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
