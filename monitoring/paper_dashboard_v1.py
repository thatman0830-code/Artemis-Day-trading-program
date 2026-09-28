"""Read-only localhost dashboard for supervised paper-operation evidence.

The dashboard has no execution imports and exposes only GET/HEAD endpoints.  It
never derives P&L from order notional. Verified performance is projected
through a read-only monitoring adapter.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from monitoring.paper_performance_view_v1 import (
    PaperPerformanceViewError, load_performance_view,
)


SCHEMA_VERSION = "paper-dashboard-snapshot-v1"
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_CANDLES = 500
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class PaperDashboardError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _safe_file(path: Path, name: str, *, required: bool = False) -> Path | None:
    path = Path(path)
    if not path.exists():
        if required:
            raise PaperDashboardError(f"{name} is missing")
        return None
    if path.is_symlink() or not path.is_file():
        raise PaperDashboardError(f"{name} is unsafe")
    return path


def _json_file(path: Path, name: str, *, required: bool = False) -> dict | None:
    safe = _safe_file(path, name, required=required)
    if safe is None:
        return None
    if safe.stat().st_size > MAX_JSON_BYTES:
        raise PaperDashboardError(f"{name} is too large")
    try:
        value = json.loads(safe.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaperDashboardError(f"{name} is unreadable") from exc
    if not isinstance(value, dict):
        raise PaperDashboardError(f"{name} must be a JSON object")
    return value


def _load_candles(path: Path) -> list[dict[str, str]]:
    safe = _safe_file(path, "candle archive", required=True)
    expected = ("symbol", "timeframe", "open_time", "close_time", "open",
                "high", "low", "close", "volume", "is_closed")
    try:
        with safe.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != expected:
                raise PaperDashboardError("candle archive fields do not match schema")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise PaperDashboardError("candle archive is unreadable") from exc
    result: list[dict[str, str]] = []
    previous = ""
    for row in rows[-MAX_CANDLES:]:
        if row["symbol"] != "BTC" or row["timeframe"] != "15m" or row["is_closed"].lower() != "true":
            raise PaperDashboardError("candle archive contains unsupported evidence")
        if row["open_time"] <= previous:
            raise PaperDashboardError("candle archive chronology is invalid")
        previous = row["open_time"]
        try:
            for key in ("open", "high", "low", "close", "volume"):
                float(row[key])
        except (TypeError, ValueError) as exc:
            raise PaperDashboardError("candle archive contains invalid numbers") from exc
        result.append({key: row[key] for key in expected})
    if not result:
        raise PaperDashboardError("candle archive is empty")
    return result


def _adapter_view(document: dict | None) -> dict:
    if document is None:
        return {"available": False, "connected": False, "kill_switch_active": None,
                "reconciliation_required": None, "orders": [], "receipts": []}
    try:
        payload = document["payload"]
        gateway = payload["gateway_checkpoint"]["payload"]
        if document["schema_version"] != "paper-exchange-adapter-checkpoint-v1":
            raise KeyError
        if payload["trading_authority"] is not False or gateway["trading_authority"] is not False:
            raise KeyError
        digest = hashlib.sha256(_canonical(payload)).hexdigest()
        if digest != document["payload_sha256"]:
            raise KeyError
        orders = [{key: item[key] for key in ("paper_order_id", "order_id", "market",
                  "notional", "state", "quantity", "filled_quantity", "remaining_quantity",
                  "accepted_at", "last_event_at")} for item in gateway["records"]]
        receipts = [{key: item[key] for key in ("command_id", "accepted", "reason",
                    "gateway_reason", "paper_order_id")} for item in payload["receipts"]]
        return {"available": True, "connected": gateway["connected"],
                "kill_switch_active": gateway["kill_switch_active"],
                "reconciliation_required": gateway["reconciliation_required"],
                "orders": orders, "receipts": receipts}
    except (KeyError, TypeError):
        raise PaperDashboardError("adapter checkpoint is invalid") from None


def build_snapshot(*, candle_path: Path, launch_decision_path: Path,
                   adapter_checkpoint_path: Path, session_health_path: Path,
                   performance_checkpoint_path: Path | None = None,
                   observed_at: datetime | None = None) -> dict:
    observed_at = observed_at or datetime.now(timezone.utc)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise PaperDashboardError("observed_at must be timezone-aware")
    candles = _load_candles(candle_path)
    launch = _json_file(launch_decision_path, "launch decision")
    health = _json_file(session_health_path, "session health")
    adapter = _adapter_view(_json_file(adapter_checkpoint_path, "adapter checkpoint"))
    if performance_checkpoint_path is None:
        performance = {"available": False, "reason":
            "AUTHORITATIVE_FILL_PRICE_AND_MARK_TO_MARKET_LEDGER_UNAVAILABLE"}
    else:
        try:
            performance = load_performance_view(performance_checkpoint_path,
                                                observed_at=observed_at)
        except PaperPerformanceViewError as exc:
            raise PaperDashboardError(str(exc)) from exc
    if performance["available"] and adapter["available"]:
        adapter_document = _json_file(adapter_checkpoint_path, "adapter checkpoint")
        adapter_snapshot = adapter_document["payload"]["gateway_checkpoint"]["payload"]["snapshot_id"]
        if performance["gateway_snapshot_id"] != adapter_snapshot:
            raise PaperDashboardError("performance and adapter checkpoints do not reconcile")
    core = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "market": "BTC", "timeframe": "15m", "candles": candles,
        "launch": launch, "session_health": health, "paper": adapter,
        "performance": performance,
        "advisory_only": True, "live_trading_permitted": False,
        "trading_authority": False,
    }
    return {**core, "snapshot_id": hashlib.sha256(_canonical(core)).hexdigest()}


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Supervised Paper Dashboard</title><style>
:root{color-scheme:dark;--bg:#081018;--panel:#101d29;--line:#263849;--text:#e9f1f8;--muted:#8da3b7;--green:#38d996;--red:#ff6b7a;--blue:#58a6ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center}.badge{border:1px solid var(--green);color:var(--green);padding:6px 10px;border-radius:999px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}.label{color:var(--muted);font-size:12px;text-transform:uppercase}.value{font-size:22px;margin-top:6px}.wide{grid-column:1/-1}canvas{width:100%;height:390px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line)}th{color:var(--muted)}.warn{color:#ffcc66}.bad{color:var(--red)}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}}
</style></head><body><main><div class="top"><div><h1>Supervised Paper Dashboard</h1><div class="label">Read-only localhost evidence view</div></div><div class="badge">NO TRADING AUTHORITY</div></div>
<div class="grid"><div class="card"><div class="label">BTC close</div><div class="value" id="price">—</div></div><div class="card"><div class="label">Cash</div><div class="value" id="cash">—</div></div><div class="card"><div class="label">Equity</div><div class="value" id="equity">—</div></div><div class="card"><div class="label">Net result</div><div class="value" id="net">—</div></div><div class="card"><div class="label">Position</div><div class="value" id="position">—</div></div><div class="card"><div class="label">Unrealized P&amp;L</div><div class="value" id="unrealized">—</div></div><div class="card"><div class="label">Paper session</div><div class="value" id="session">—</div></div><div class="card"><div class="label">Launch decision</div><div class="value" id="launch">—</div></div><div class="card wide"><h2>BTC price</h2><canvas id="chart"></canvas></div><div class="card wide"><h2>Verified equity</h2><canvas id="equityChart"></canvas></div><div class="card wide"><h2>Paper orders</h2><table><thead><tr><th>Order</th><th>State</th><th>Quantity</th><th>Filled</th><th>Notional</th></tr></thead><tbody id="orders"></tbody></table></div><div class="card wide"><h2>Performance integrity</h2><div class="warn" id="performance"></div></div></div><div class="label" id="footer"></div></main>
<script>
const esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function draw(id,rows,key,color){const c=document.getElementById(id),d=devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*d;c.height=h*d;const x=c.getContext('2d');x.scale(d,d);x.clearRect(0,0,w,h);if(rows.length<2)return;const v=rows.map(r=>+r[key]),lo=Math.min(...v),hi=Math.max(...v),pad=24;x.strokeStyle='#263849';x.strokeRect(pad,pad,w-pad*2,h-pad*2);x.beginPath();v.forEach((n,i)=>{const px=pad+i*(w-pad*2)/(v.length-1),py=h-pad-(n-lo)*(h-pad*2)/(hi-lo||1);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle=color;x.lineWidth=2;x.stroke();x.fillStyle='#8da3b7';x.fillText(hi.toFixed(2),4,pad);x.fillText(lo.toFixed(2),4,h-pad)}
const money=v=>v==null?'—':Number(v).toLocaleString(undefined,{style:'currency',currency:'USD'});
async function refresh(){try{const r=await fetch('/api/snapshot',{cache:'no-store'});if(!r.ok)throw Error(await r.text());const s=await r.json(),last=s.candles.at(-1),p=s.performance;price.textContent=money(last.close);session.textContent=s.session_health?.state??(s.paper.available?'CHECKPOINT ONLY':'NOT STARTED');launch.textContent=s.launch?(s.launch.eligible?'ELIGIBLE':'BLOCKED'):'UNAVAILABLE';cash.textContent=p.available?money(p.cash):'—';equity.textContent=p.available?money(p.equity):'—';net.textContent=p.available?money(p.net_result):'—';unrealized.textContent=p.available?money(p.unrealized_pnl):'—';position.textContent=p.available?`${p.position.quantity} BTC`:'—';orders.innerHTML=s.paper.orders.map(o=>`<tr><td>${esc(o.order_id)}</td><td>${esc(o.state)}</td><td>${esc(o.quantity)}</td><td>${esc(o.filled_quantity)}</td><td>${esc(o.notional)}</td></tr>`).join('')||'<tr><td colspan="5">No paper orders recorded</td></tr>';performance.textContent=p.available?`VERIFIED · costs ${money(p.total_costs)} · checkpoint age ${p.checkpoint_age_seconds}s`:p.reason;footer.textContent=`Snapshot ${s.snapshot_id} · observed ${s.observed_at}`;draw('chart',s.candles,'close','#58a6ff');draw('equityChart',p.available?p.equity_curve:[],'equity','#38d996')}catch(e){session.textContent='EVIDENCE ERROR';session.className='value bad';footer.textContent=String(e)}}refresh();setInterval(refresh,5000);addEventListener('resize',refresh);
</script></body></html>'''


def make_handler(config: dict[str, Path]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PaperDashboard/1"

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()

        def _body(self) -> tuple[int, str, bytes]:
            path = urlsplit(self.path).path
            if path == "/":
                return HTTPStatus.OK, "text/html; charset=utf-8", HTML.encode("utf-8")
            if path == "/api/snapshot":
                try:
                    body = _canonical(build_snapshot(**config))
                    return HTTPStatus.OK, "application/json; charset=utf-8", body
                except PaperDashboardError as exc:
                    return HTTPStatus.SERVICE_UNAVAILABLE, "text/plain; charset=utf-8", str(exc).encode("utf-8")
            return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found"

        def do_GET(self) -> None:
            status, content_type, body = self._body()
            self._headers(status, content_type, len(body)); self.wfile.write(body)

        def do_HEAD(self) -> None:
            status, content_type, body = self._body(); self._headers(status, content_type, len(body))

        def do_POST(self) -> None:
            body = b"method not allowed"; self._headers(HTTPStatus.METHOD_NOT_ALLOWED, "text/plain", len(body)); self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only supervised paper dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--candles", type=Path, default=Path("data/backtests/btc_forward_archive_2/BTC_15m.csv"))
    parser.add_argument("--launch", type=Path, default=Path("outputs/paper_launch/launch-decision-latest.json"))
    parser.add_argument("--session-root", type=Path, default=Path("outputs/paper_session"))
    args = parser.parse_args(argv)
    if args.host not in LOOPBACK_HOSTS:
        raise PaperDashboardError("dashboard must bind to loopback")
    if not 1 <= args.port <= 65535:
        raise PaperDashboardError("port is invalid")
    config = {"candle_path": args.candles, "launch_decision_path": args.launch,
              "adapter_checkpoint_path": args.session_root / "adapter-checkpoint.json",
              "session_health_path": args.session_root / "latest-health.json",
              "performance_checkpoint_path": args.session_root / "performance-checkpoint.json"}
    server = ThreadingHTTPServer((args.host, args.port), make_handler(config))
    print(f"PAPER_DASHBOARD_READ_ONLY:http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
