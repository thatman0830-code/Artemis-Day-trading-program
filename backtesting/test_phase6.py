import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.__main__ import main, parser
from backtesting.file_runner import _json_bytes, execute, export, load_inputs


ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "backtesting"


def args(command, output=None):
    values = [command, "--data", str(EXAMPLE / "dataset_manifest.json"),
              "--config", str(EXAMPLE / "backtest_config.json")]
    if output is not None: values += ["--output", str(output)]
    return values


def test_cli_help_validate_and_inspect(capsys):
    with pytest.raises(SystemExit) as exit_:
        parser().parse_args(["--help"])
    assert exit_.value.code == 0
    assert main(args("validate")) == 0
    assert "VALID dataset=" in capsys.readouterr().out
    assert main(args("inspect")) == 0
    output = capsys.readouterr().out
    assert "mode=PAPER_SIMULATION" in output and "exchange_submission=false" in output


def test_csv_json_parsing_preserves_decimal_and_utc():
    dataset, raw, config = load_inputs(EXAMPLE / "dataset_manifest.json", EXAMPLE / "backtest_config.json")
    assert dataset.candles[0].open == Decimal("100.00")
    assert dataset.candles[0].open_time.utcoffset().total_seconds() == 0
    assert config["starting_equity"] == "10000.00"


def test_complete_run_exports_stable_order_checksums_and_simulation_marker(tmp_path):
    output = tmp_path / "result"
    assert main(args("run", output)) == 0
    expected = {"run_manifest.json", "dataset_manifest.json", "result.json",
                "trades.csv", "equity.csv", "summary.txt", "checksums.json"}
    assert {p.name for p in output.iterdir()} == expected
    checks = json.loads((output / "checksums.json").read_text())["sha256"]
    from hashlib import sha256
    for name, digest in checks.items(): assert sha256((output / name).read_bytes()).hexdigest() == digest
    assert (output / "trades.csv").read_text().splitlines()[0].startswith("trade_id,accounting_id")
    assert "HISTORICAL SIMULATION ONLY" in (output / "summary.txt").read_text()
    first = (output / "result.json").read_bytes()
    assert main(args("run", output) + ["--overwrite"]) == 0
    assert (output / "result.json").read_bytes() == first


def test_existing_output_refusal_has_documented_exit_code(tmp_path, capsys):
    output = tmp_path / "existing"; output.mkdir()
    assert main(args("run", output)) == 4
    assert "use --overwrite" in capsys.readouterr().err


def test_secret_unknown_schema_and_json_float_rejection(tmp_path):
    config = json.loads((EXAMPLE / "backtest_config.json").read_text())
    config["private_key"] = "never"
    path = tmp_path / "secret.json"; path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="secret-like"):
        load_inputs(EXAMPLE / "dataset_manifest.json", path)
    config.pop("private_key"); config["schema_version"] = "future"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="unsupported"):
        load_inputs(EXAMPLE / "dataset_manifest.json", path)
    config["schema_version"] = "backtesting-config-v1"; config["starting_equity"] = 10000.0
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="floats"):
        load_inputs(EXAMPLE / "dataset_manifest.json", path)


def test_missing_file_naive_timestamp_and_incomplete_candle_rejection(tmp_path):
    manifest = json.loads((EXAMPLE / "dataset_manifest.json").read_text())
    manifest["files"][0]["path"] = "missing.csv"
    path = tmp_path / "manifest.json"; path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="missing timeframe"):
        load_inputs(path, EXAMPLE / "backtest_config.json")
    csv_text = (EXAMPLE / "candles_5m.csv").read_text().replace("2026-08-20T00:00:00Z", "2026-08-20T00:00:00", 1)
    (tmp_path / "candles.csv").write_text(csv_text)
    manifest["files"][0]["path"] = "candles.csv"; path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="UTC"):
        load_inputs(path, EXAMPLE / "backtest_config.json")
    (tmp_path / "candles.csv").write_text((EXAMPLE / "candles_5m.csv").read_text().replace(",true\n", ",false\n", 1))
    with pytest.raises(ValueError, match="completed candles"):
        load_inputs(path, EXAMPLE / "backtest_config.json")


def test_null_infinity_and_not_applicable_serialization_is_lossless():
    payload = _json_bytes({"null": None, "infinity": Decimal("Infinity"),
                           "status": "NOT_APPLICABLE"})
    decoded = json.loads(payload)
    assert decoded == {"infinity": {"status": "POSITIVE_INFINITY"},
                       "null": None, "status": "NOT_APPLICABLE"}


def test_powershell_launcher_forwards_parameters_and_security_boundary():
    script = (ROOT / "scripts" / "run_backtest.ps1").read_text()
    for value in ("$Data", "$Config", "$Output", "--overwrite", "$LASTEXITCODE"):
        assert value in script
    tree = ast.parse((Path(__file__).parent / "file_runner.py").read_text())
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    forbidden = ("requests", "websocket", "wallet", "signing", "private_key", "hyperliquid")
    assert not any(any(word in name.lower() for word in forbidden) for name in imports)
