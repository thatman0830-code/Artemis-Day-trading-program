"""Read-only whole-archive integrity audit for delayed ES/NQ forward data."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import argparse
from dataclasses import asdict

AUDIT_VERSION = "ES_NQ_FORWARD_ARCHIVE_INTEGRITY_V2"


class ForwardArchiveIntegrityError(ValueError): pass


def _hash(path: Path) -> str: return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class ForwardArchiveIntegrityV1:
    audit_id: str
    state: str
    archive_path: str
    artifact_count: int
    session_count: int
    row_count: int
    raw_bytes: int
    normalized_bytes: int
    observed_no_bar_minute_count: int
    unresolved_gap_count: int
    artifact_sha256: tuple[tuple[str, str], ...]
    trading_authority: bool = False
    version: str = AUDIT_VERSION


def audit_forward_archive(repository: Path) -> ForwardArchiveIntegrityV1:
    repository = repository.resolve(); archive = (repository / "data/futures_forward").resolve()
    if repository not in archive.parents or not archive.is_dir():
        raise ForwardArchiveIntegrityError("archive root missing or outside repository")
    artifacts: list[tuple[str, str]] = []; sessions = rows = raw_bytes = normalized_bytes = no_bars = gaps = 0
    for root in ("ES", "NQ"):
        base = archive / root
        manifests = sorted((base / "manifests").glob("*.json"))
        if not manifests: raise ForwardArchiveIntegrityError(f"{root} has no manifests")
        stems = {path.stem for path in manifests}
        for folder, suffix in (("raw", ".json"), ("normalized", ".jsonl"),
                               ("pending", ".json"), ("checkpoints", ".json")):
            actual = {path.stem for path in (base / folder).glob(f"*{suffix}")}
            if actual != stems: raise ForwardArchiveIntegrityError(f"{root} {folder} inventory mismatch")
        for manifest_path in manifests:
            stem = manifest_path.stem
            paths = {"manifest":manifest_path, "raw":base/"raw"/(stem+".json"),
                     "normalized":base/"normalized"/(stem+".jsonl"),
                     "pending":base/"pending"/(stem+".json"),
                     "checkpoint":base/"checkpoints"/(stem+".json")}
            try:
                manifest=json.loads(paths["manifest"].read_text("utf-8")); pending=json.loads(paths["pending"].read_text("utf-8")); checkpoint=json.loads(paths["checkpoint"].read_text("utf-8"))
            except (OSError,json.JSONDecodeError) as exc: raise ForwardArchiveIntegrityError(f"{root} malformed artifact: {stem}") from exc
            identity=(manifest.get("root"),manifest.get("ticker"),manifest.get("session_date"),manifest.get("contract_id"))
            if (identity[0] != root or not str(identity[1]).startswith(root)
                    or stem != f"{identity[2]}-{identity[1]}"
                    or any(pending.get(k)!=manifest.get(k) for k in ("root","ticker","session_date","contract_id","run_id"))
                    or any(checkpoint.get(k)!=manifest.get(k) for k in ("root","ticker","session_date"))):
                raise ForwardArchiveIntegrityError(f"{root} identity mismatch: {stem}")
            if (manifest.get("schema_version")!="es-nq-delayed-forward-v1"
                    or pending.get("schema_version")!="es-nq-delayed-forward-v1"
                    or checkpoint.get("schema_version")!="es-nq-delayed-forward-v1"):
                raise ForwardArchiveIntegrityError(f"{root} schema mismatch: {stem}")
            expected_paths={"raw":f"raw/{stem}.json","normalized":f"normalized/{stem}.jsonl"}
            if (manifest.get("raw_relative_path")!=expected_paths["raw"] or manifest.get("normalized_relative_path")!=expected_paths["normalized"]
                    or pending.get("raw_relative_path")!=expected_paths["raw"]
                    or checkpoint.get("manifest_relative_path")!=f"manifests/{stem}.json"):
                raise ForwardArchiveIntegrityError(f"{root} path mismatch: {stem}")
            hashes={name:_hash(path) for name,path in paths.items()}
            if (hashes["raw"]!=manifest.get("raw_sha256") or hashes["raw"]!=pending.get("raw_sha256")
                    or hashes["normalized"]!=manifest.get("normalized_sha256")
                    or hashes["manifest"]!=checkpoint.get("manifest_sha256")):
                raise ForwardArchiveIntegrityError(f"{root} checksum mismatch: {stem}")
            if (paths["raw"].stat().st_size!=manifest.get("raw_bytes") or paths["raw"].stat().st_size!=pending.get("raw_bytes")
                    or paths["normalized"].stat().st_size!=manifest.get("normalized_bytes")):
                raise ForwardArchiveIntegrityError(f"{root} byte-count mismatch: {stem}")
            lines=paths["normalized"].read_text("utf-8").splitlines()
            if len(lines)!=manifest.get("normalized_rows"): raise ForwardArchiveIntegrityError(f"{root} row-count mismatch: {stem}")
            previous=None; volume=0
            for line in lines:
                try: row=json.loads(line); timestamp=int(row["window_start_ns"]); volume += int(row["volume"])
                except (json.JSONDecodeError,KeyError,TypeError,ValueError) as exc: raise ForwardArchiveIntegrityError(f"{root} normalized row malformed: {stem}") from exc
                if row.get("root")!=root or row.get("ticker")!=identity[1] or row.get("session_date")!=identity[2] or row.get("contract_id")!=identity[3]:
                    raise ForwardArchiveIntegrityError(f"{root} normalized identity mismatch: {stem}")
                if previous is not None and timestamp <= previous: raise ForwardArchiveIntegrityError(f"{root} chronology mismatch: {stem}")
                previous=timestamp
            if str(volume)!=str(manifest.get("observed_volume")): raise ForwardArchiveIntegrityError(f"{root} volume mismatch: {stem}")
            missing=manifest.get("missing_aggregate_minutes")
            if isinstance(missing,bool) or not isinstance(missing,int) or missing<0: raise ForwardArchiveIntegrityError(f"{root} gap count invalid: {stem}")
            if missing:
                if manifest.get("missing_semantics") != "ZERO_OBSERVED_ELIGIBLE_TRADE_VOLUME_NO_OHLC":
                    raise ForwardArchiveIntegrityError(f"{root} missing-minute semantics invalid: {stem}")
                no_bars += missing
            sessions+=1; rows+=len(lines); raw_bytes+=paths["raw"].stat().st_size; normalized_bytes+=paths["normalized"].stat().st_size
            for name,path in paths.items(): artifacts.append((path.relative_to(repository).as_posix(),hashes[name]))
    ordered=tuple(sorted(artifacts)); audit_id=sha256(json.dumps((AUDIT_VERSION,ordered,sessions,rows,raw_bytes,normalized_bytes,no_bars,gaps),separators=(",",":"),sort_keys=True).encode()).hexdigest()
    return ForwardArchiveIntegrityV1(audit_id,"VERIFIED",archive.relative_to(repository).as_posix(),len(ordered),sessions,rows,raw_bytes,normalized_bytes,no_bars,gaps,ordered,False)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True);args=parser.parse_args(argv)
    try: result=audit_forward_archive(args.repository)
    except ForwardArchiveIntegrityError as exc:
        print(json.dumps({"state":"REJECTED","error":str(exc),"trading_authority":False},sort_keys=True));return 2
    print(json.dumps(asdict(result),sort_keys=True,separators=(",",":")));return 0


if __name__ == "__main__": raise SystemExit(main())
