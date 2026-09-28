"""Small fail-closed CONNECT proxy for the isolated worker network."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import ipaddress
import json
import os
import socket
import sys


ALLOWED = frozenset(
    item.strip().lower()
    for item in os.environ.get("HERMES_EGRESS_ALLOWLIST", "").split(",")
    if item.strip()
)
CONNECT_TIMEOUT = 15
IDLE_TIMEOUT = 120
MAX_CONNECTIONS = 8
semaphore = asyncio.Semaphore(MAX_CONNECTIONS)


def log(event: str, **facts: object) -> None:
    print(json.dumps({
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **facts,
    }, sort_keys=True), flush=True)


async def permitted(host: str) -> bool:
    host = host.rstrip(".").lower()
    if host not in ALLOWED:
        return False
    try:
        if ipaddress.ip_address(host):
            return False
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        records = await loop.run_in_executor(
            None, lambda: socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        )
    except OSError:
        return False
    for record in records:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global:
            return False
    return bool(records)


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await asyncio.wait_for(reader.read(65536), IDLE_TIMEOUT):
            writer.write(data)
            await writer.drain()
    except (asyncio.TimeoutError, ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    peer = str(client_writer.get_extra_info("peername"))
    async with semaphore:
        upstream_writer = None
        try:
            first = await asyncio.wait_for(client_reader.readline(), 10)
            parts = first.decode("ascii", "strict").strip().split()
            if len(parts) != 3 or parts[0] != "CONNECT":
                log("DENY", peer=peer, reason="CONNECT_ONLY")
                client_writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
                await client_writer.drain()
                return
            authority = parts[1]
            host, separator, port_text = authority.rpartition(":")
            if not separator or not host or port_text != "443" or not await permitted(host):
                log("DENY", peer=peer, authority=authority, reason="NOT_ALLOWLISTED")
                client_writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                await client_writer.drain()
                return
            while True:
                line = await asyncio.wait_for(client_reader.readline(), 10)
                if line in {b"\r\n", b"\n", b""}:
                    break
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(host, 443), CONNECT_TIMEOUT
            )
            log("ALLOW", peer=peer, host=host, port=443)
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()
            await asyncio.gather(
                relay(client_reader, upstream_writer),
                relay(upstream_reader, client_writer),
            )
        except Exception as exc:
            log("ERROR", peer=peer, error=type(exc).__name__)
        finally:
            client_writer.close()
            if upstream_writer is not None:
                upstream_writer.close()


async def main() -> None:
    if not ALLOWED:
        raise SystemExit("HERMES_EGRESS_ALLOWLIST must contain at least one exact hostname")
    server = await asyncio.start_server(handle, "0.0.0.0", 3128)
    log("START", allowlist=sorted(ALLOWED), max_connections=MAX_CONNECTIONS)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

