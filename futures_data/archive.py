from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .contracts import ContractSpec, FuturesBar, FuturesRoot, RequestManifest, SCHEMA_VERSION, identity, utc
from .sessions import GapFact


ARCHIVE_NAMES = {FuturesRoot.ES: "es_forward_archive_1", FuturesRoot.NQ: "nq_forward_archive_1"}


def archive_path(repository: Path, root: FuturesRoot) -> Path:
    return repository / "data" / "backtests" / ARCHIVE_NAMES[root]


@dataclass(frozen=True)
class ArchiveManifest:
    id: str
    root: FuturesRoot
    schema_version: str
    provider: str
    contract_ids: tuple[str, ...]
    request_ids: tuple[str, ...]
    row_count: int
    earliest: datetime | None
    latest: datetime | None
    normalized_sha256: str
    gaps: tuple[GapFact, ...]
    duplicates: int
    supersedes_manifest_id: str | None
    created_at: datetime
    status: str


def _jsonable(value):
    if isinstance(value, datetime): return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "value"): return value.value
    if hasattr(value, "as_tuple"): return format(value, "f")
    if isinstance(value, tuple): return [_jsonable(x) for x in value]
    if isinstance(value, dict): return {k:_jsonable(v) for k,v in value.items()}
    return value


def canonical_rows(bars: tuple[FuturesBar, ...]) -> bytes:
    rows = []
    for x in bars:
        rows.append({k:_jsonable(v) for k,v in asdict(x).items()})
    return ("\n".join(json.dumps(x, sort_keys=True, separators=(",", ":")) for x in rows) + ("\n" if rows else "")).encode()


@contextmanager
def single_writer_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True); path = directory / ".writer.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("archive already has an active writer") from error
    try:
        os.write(descriptor, str(os.getpid()).encode()); os.close(descriptor); yield
    finally:
        path.unlink(missing_ok=True)


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(content); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def commit_archive(*, directory: Path, root: FuturesRoot, provider: str,
                   contracts: tuple[ContractSpec, ...], bars: tuple[FuturesBar, ...],
                   requests: tuple[RequestManifest, ...], gaps: tuple[GapFact, ...],
                   created_at: datetime, supersedes: str | None = None) -> ArchiveManifest:
    created = utc(created_at, "created_at")
    if any(x.root is not root for x in contracts + tuple(bars)):
        raise ValueError("wrong-contract contamination")
    if len({x.id for x in bars}) != len(bars): raise ValueError("duplicate bars")
    ordered = tuple(sorted(bars, key=lambda x: (x.open_time, x.id)))
    if bars != ordered: raise ValueError("bars must be ordered")
    payload = canonical_rows(bars); digest = sha256(payload).hexdigest()
    ident = identity("futures-archive-v1", root.value, provider, *(x.id for x in contracts),
                     *(x.id for x in requests), digest, supersedes or "")
    manifest = ArchiveManifest(ident, root, SCHEMA_VERSION, provider, tuple(x.id for x in contracts),
        tuple(x.id for x in requests), len(bars), bars[0].open_time if bars else None,
        bars[-1].close_time if bars else None, digest, gaps, 0, supersedes, created, "VALID")
    with single_writer_lock(directory):
        if directory.name != ARCHIVE_NAMES[root]: raise ValueError("archive root/name mismatch")
        atomic_write(directory / "bars.jsonl", payload)
        encoded = json.dumps(_jsonable(asdict(manifest)), sort_keys=True, separators=(",", ":")).encode() + b"\n"
        atomic_write(directory / "archive_manifest.json", encoded)
    return manifest


def verify_archive(directory: Path) -> dict:
    manifest = json.loads((directory / "archive_manifest.json").read_text(encoding="utf-8"))
    payload = (directory / "bars.jsonl").read_bytes()
    if sha256(payload).hexdigest() != manifest["normalized_sha256"]:
        raise ValueError("archive checksum mismatch")
    return manifest

