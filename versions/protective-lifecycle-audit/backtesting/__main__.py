import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

from backtesting.file_runner import build_pipeline, execute, export, load_inputs
from backtesting.downloader import DownloadRequest, HistoricalCandleDownloader
from backtesting.market_data import CanonicalTimeframe, GapPolicy
from backtesting.recorder import (
    ForwardCandleRecorder, JsonLineEventSink, RecorderConfiguration,
    freeze_snapshot,
)


def utc(value):
    if not value.endswith("Z"): raise argparse.ArgumentTypeError("timestamp must be UTC ISO 8601 with Z")
    try: return datetime.fromisoformat(value[:-1]+"+00:00").astimezone(timezone.utc)
    except ValueError as error: raise argparse.ArgumentTypeError("timestamp is malformed") from error


def parser():
    root = argparse.ArgumentParser(prog="python -m backtesting", description="Offline deterministic historical simulation only")
    commands = root.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download", help="download public closed candles only")
    download.add_argument("--symbol", required=True)
    download.add_argument("--timeframes", required=True, nargs="+", choices=[x.value for x in CanonicalTimeframe])
    download.add_argument("--start", required=True, type=utc); download.add_argument("--end", required=True, type=utc)
    download.add_argument("--data-network", choices=("testnet","main"+"net"), default="testnet")
    download.add_argument("--output", required=True); download.add_argument("--gap-policy", choices=("REJECT","RECORD"), default="REJECT")
    download.add_argument("--resume", action="store_true"); download.add_argument("--overwrite", action="store_true")
    record = commands.add_parser("record", help="record public closed candles into a growing archive")
    record.add_argument("--symbol", required=True)
    record.add_argument("--timeframes", required=True, nargs="+", choices=[x.value for x in CanonicalTimeframe])
    record.add_argument("--data-network", choices=("testnet","main"+"net"), default="testnet")
    record.add_argument("--output", required=True)
    record.add_argument("--poll-seconds", type=float, default=15.0)
    record.add_argument("--timeout-seconds", type=float, default=15.0)
    record.add_argument("--retry-limit", type=int, default=3)
    record.add_argument("--retry-base-seconds", type=float, default=1.0)
    record.add_argument("--retry-max-seconds", type=float, default=30.0)
    record.add_argument("--retry-jitter-fraction", type=float, default=0.20)
    record.add_argument("--cycle-failure-limit", type=int, default=3)
    record.add_argument("--gap-backfill-limit", type=int, default=8)
    record.add_argument("--log-file")
    record.add_argument("--alert-file")
    snapshot = commands.add_parser("snapshot", help="freeze a verified archive interval")
    snapshot.add_argument("--archive", required=True); snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--start", required=True, type=utc); snapshot.add_argument("--end", required=True, type=utc)
    snapshot.add_argument("--overwrite", action="store_true")
    for name in ("validate", "inspect", "run"):
        item = commands.add_parser(name)
        item.add_argument("--data", required=True); item.add_argument("--config", required=True)
        if name == "run":
            item.add_argument("--output", required=True); item.add_argument("--overwrite", action="store_true")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "download":
            request=DownloadRequest(args.symbol,tuple(CanonicalTimeframe(x) for x in args.timeframes),
                args.start,args.end,args.data_network,Path(args.output),GapPolicy(args.gap_policy),args.overwrite,args.resume)
            manifest=HistoricalCandleDownloader().download(request)
            print(f"Dataset manifest: {manifest}"); print("PUBLIC DATA ONLY; trading remains disabled"); return 0
        if args.command == "record":
            event_sink = JsonLineEventSink(Path(args.log_file)) if args.log_file else None
            alert_hook = JsonLineEventSink(Path(args.alert_file)) if args.alert_file else None
            recorder = ForwardCandleRecorder(configuration=RecorderConfiguration(
                args.symbol, tuple(CanonicalTimeframe(x) for x in args.timeframes),
                args.data_network, Path(args.output), args.poll_seconds,
                args.timeout_seconds, args.retry_limit, 5000,
                args.retry_base_seconds, args.retry_max_seconds,
                args.retry_jitter_fraction, args.cycle_failure_limit,
                args.gap_backfill_limit), event_sink=event_sink,
                alert_hook=alert_hook)
            print("PUBLIC CLOSED-CANDLE RECORDING ONLY; trading remains disabled")
            result = recorder.run()
            print(f"Archive state: {result['state']}"); return 0
        if args.command == "snapshot":
            manifest = freeze_snapshot(archive=Path(args.archive), output=Path(args.output),
                start=args.start, end=args.end, overwrite=args.overwrite)
            print(f"Validated immutable snapshot: {manifest}"); return 0
        dataset, raw, config = load_inputs(args.data, args.config)
        manifest, run, _ = build_pipeline(dataset, raw, config)
        if args.command == "validate":
            print(f"VALID dataset={dataset.fingerprint} run={run.id}"); return 0
        if args.command == "inspect":
            print(f"dataset_id={manifest.dataset_id}"); print(f"fingerprint={manifest.fingerprint}")
            print(f"symbol={manifest.symbol}"); print(f"timeframes={','.join(x.value for x in manifest.timeframes)}")
            print(f"run_id={run.id}")
            print(f"setup_request_mode={config['setup_request_mode']}")
            print(f"prior_period_policy={config.get('prior_period_policy_id', 'OWNER_PRIOR_PERIOD_V1')}")
            print(f"risk_reward_policy={config.get('risk_reward_policy_id', 'CANONICAL_MIN_RR_V1')}")
            print(f"performance_objective={config.get('performance_objective_id', 'NONE')}")
            print(f"displacement_policy={config.get('displacement_policy_id', 'NOT_APPLICABLE')}")
            print("mode=PAPER_SIMULATION exchange_submission=false"); return 0
        print("Running deterministic historical simulation...")
        manifest, run, state, result = execute(dataset, raw, config)
        try:
            path = export(args.output, dataset_manifest=manifest, run=run, state=state,
                          result=result, overwrite=args.overwrite)
        except (FileExistsError, OSError) as error:
            print(f"OUTPUT ERROR: {error}", file=sys.stderr); return 4
        print(f"SUCCESS result={result.id}"); print(f"Output: {path}"); return 0
    except (ValueError, TypeError, OSError) as error:
        print(f"VALIDATION ERROR: {error}", file=sys.stderr); return 2
    except Exception as error:
        print(f"REPLAY ERROR: {error}", file=sys.stderr); return 3


if __name__ == "__main__": raise SystemExit(main())
