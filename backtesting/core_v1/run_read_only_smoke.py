from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from futures_data.archive_audit import audit as audit_pass_b

from .adapters import ActiveContractWindow, VerifiedArchiveSlice
from .capabilities import EngineCapabilities
from .engine import CalculationEngine, EngineRunConfiguration
from .models import (Action, ActionKind, EndPolicy, ExecutionConfig, InstrumentSpec,
    OrderType, RiskConfig, Side, StrategyRequirements, TriggerKind, canonical, fingerprint)
from .production_adapters import BTCPhase7PartialAdapter, PassBV3ArchiveAdapter
from .strategy import NoOpStrategy


SMOKE_VERSION = "core-v1-read-only-archive-smoke-v1"
OUTPUT_RELATIVE = Path("outputs/backtesting_smoke/core_v1_read_only_smoke_v1")
SESSIONS = {
    "ES": ("2025-06-17", "2025-06-18", "2025-06-23", "2025-06-24", "2025-06-25"),
    "NQ": ("2025-06-16", "2025-06-17", "2025-06-18", "2025-06-23", "2025-06-24"),
}
MECHANICAL_SESSIONS = ("2025-06-23", "2025-06-24")


def stable_json(value) -> bytes:
    return (json.dumps(canonical(value), sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_new(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle: handle.write(payload)
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class ScriptedMechanicalStrategy:
    market: str
    actions: tuple[tuple[int, str, str, str], ...]

    @property
    def requirements(self):
        return StrategyRequirements("NON_RESEARCH_MECHANICAL_FIXTURE", "1", (self.market,),
            ("open","high","low","close","volume"), (TriggerKind.MARKET,), (OrderType.MARKET,), True)

    def evaluate(self, trigger, state):
        match = next((row for row in self.actions if row[0] == trigger.event.sequence), None)
        if match is None: return ()
        _, instrument, kind, side = match
        action = Action("", ActionKind(kind), instrument, Side(side), Decimal("1"), OrderType.MARKET,
                        reason="NON_RESEARCH_MECHANICAL_FIXTURE")
        return (Action(fingerprint((trigger.id, match)), action.kind, action.instrument_id,
                       action.side, action.quantity, action.order_type, reason=action.reason),)


def spec(ticker: str, market: str, start, end) -> InstrumentSpec:
    # Versioned mechanical smoke assumptions, not a fee/margin claim or research configuration.
    multiplier = Decimal("50") if market == "ES" else Decimal("20")
    return InstrumentSpec(fingerprint(("SMOKE_SPEC_V1",ticker,market)),ticker,market,Decimal("0.25"),
        Decimal("1"),multiplier,Decimal("0.10"),Decimal("0.00001"),Decimal("1"),
        start-timedelta(days=1),end+timedelta(days=1),"NON_RESEARCH_MECHANICAL_FIXTURE_V1","1")


def bounded_rows(adapter: PassBV3ArchiveAdapter, sessions: tuple[str,...]):
    by_session={s:[] for s in sessions}
    quality_by_session={s:[] for s in sessions}
    for q in adapter.data_quality_events:
        if q.session_id in quality_by_session: quality_by_session[q.session_id].append(q)
    for item in adapter.iter_events():
        if item.bar.session_id in by_session: by_session[item.bar.session_id].append(item.bar)
    selected=[]
    for session in sessions:
        rows=by_session[session]
        if not rows: raise ValueError("selected session missing")
        indexes=set(range(min(12,len(rows)))) | set(range(max(0,len(rows)-12),len(rows)))
        for q in quality_by_session[session]:
            for i,row in enumerate(rows):
                if q.start_inclusive-timedelta(minutes=2) <= row.open_time <= q.end_exclusive+timedelta(minutes=2):
                    indexes.add(i)
        selected.extend(rows[i] for i in sorted(indexes))
    selected.sort(key=lambda row:(row.close_time,row.market,row.instrument_id,row.sequence,row.id))
    return tuple(selected), tuple(q for s in sessions for q in quality_by_session[s])


def derived_archive(*, output: Path, market: str, adapter, bars, quality):
    manifest={"smoke_version":SMOKE_VERSION,"market":market,"production_dataset_fingerprint":adapter.metadata.dataset_fingerprint,
        "sessions":SESSIONS[market],"bar_ids":[b.id for b in bars],"quality_ids":[q.id for q in quality]}
    path=output/f"{market.lower()}_slice_manifest.json";checksum=write_new(path,stable_json(manifest))
    windows=[]
    for contract in sorted({b.contract_id for b in bars}):
        rows=[b for b in bars if b.contract_id==contract]
        windows.append(ActiveContractWindow(contract,min(b.open_time for b in rows),
            max(b.close_time for b in rows)+timedelta(microseconds=1),
            next((b.rollover_decision_id for b in rows if b.rollover_decision_id),"INITIAL_WINDOW")))
    supplemental=tuple(e for e in adapter.rollover_events()
        if min(b.open_time for b in bars) <= e.event_time < max(b.close_time for b in bars)+timedelta(minutes=1))
    return VerifiedArchiveSlice(market,"",path,checksum,
        fingerprint((adapter.metadata.dataset_fingerprint,tuple(b.id for b in bars),tuple(q.id for q in quality))),
        bars,tuple(windows),supplemental),manifest,checksum


def run_market(output:Path,market:str,adapter):
    bars,quality=bounded_rows(adapter,SESSIONS[market])
    archive,slice_manifest,slice_sha=derived_archive(output=output,market=market,adapter=adapter,bars=bars,quality=quality)
    specs=tuple(spec(ticker,market,min(b.open_time for b in bars),max(b.close_time for b in bars))
                for ticker in sorted({b.instrument_id for b in bars}))
    execution=ExecutionConfig("SMOKE_EXECUTION_V1",Decimal("0.01"),EndPolicy.REJECT_OPEN)
    risk=RiskConfig("SMOKE_RISK_V1",Decimal("10000000"),Decimal("1000000"),Decimal("1"))
    config=EngineRunConfiguration(f"{market}-READ-ONLY-SMOKE",SMOKE_VERSION,Decimal("100000"),execution,risk,
        min(b.open_time for b in bars),max(b.close_time for b in bars)+timedelta(minutes=1),
        (adapter.metadata.lineage.calendar_sha256 or "",),(adapter.metadata.lineage.rollover_sha256 or "",),
        "SMOKE_FIXED_SESSIONS_V1",0,(SMOKE_VERSION,adapter.metadata.lineage.schema_version))
    engine=CalculationEngine();noop=NoOpStrategy(markets=(market,));cap=engine.preflight(strategy=noop,archives=(archive,))
    no_op_one=engine.run(strategy=noop,archives=(archive,),specs=specs,configuration=config)
    no_op_two=CalculationEngine().run(strategy=noop,archives=(archive,),specs=specs,configuration=config)
    if no_op_one.machine_json()!=no_op_two.machine_json() or no_op_one.id!=no_op_two.id:raise ValueError("NoOp nondeterminism")
    by_session={s:[b for b in bars if b.session_id==s] for s in MECHANICAL_SESSIONS}
    scripted=[]
    for session in MECHANICAL_SESSIONS:
        rows=by_session[session]
        if len(rows)<10 or any(b.missing_before for b in rows[:10]):raise ValueError("mechanical ordinal window invalid")
        scripted.extend(((rows[2].sequence,rows[2].instrument_id,"ENTER","BUY"),
                         (rows[7].sequence,rows[7].instrument_id,"EXIT","SELL")))
    strategy=ScriptedMechanicalStrategy(market,tuple(scripted));mechanical_cap=engine.preflight(strategy=strategy,archives=(archive,))
    mech_one=engine.run(strategy=strategy,archives=(archive,),specs=specs,configuration=config)
    mech_two=CalculationEngine().run(strategy=strategy,archives=(archive,),specs=specs,configuration=config)
    if mech_one.machine_json()!=mech_two.machine_json() or mech_one.id!=mech_two.id:raise ValueError("mechanical nondeterminism")
    if len(mech_one.orders)!=4 or len(mech_one.fills)!=4 or mech_one.positions[-1].quantity!=0:raise ValueError("mechanical postcondition")
    write_new(output/f"{market.lower()}_noop_result.json",no_op_one.machine_json().encode())
    write_new(output/f"{market.lower()}_mechanical_result.json",mech_one.machine_json().encode())
    facts={"market":market,"dataset_fingerprint":adapter.metadata.dataset_fingerprint,
        "slice_fingerprint":archive.dataset_fingerprint,"slice_manifest_sha256":slice_sha,
        "sessions":SESSIONS[market],"rows":len(bars),"quality_events":len(quality),
        "contracts":sorted({(b.instrument_id,b.contract_id) for b in bars}),
        "source_manifest_sha256":sorted({b.source_checksum for b in bars}),
        "rollover_event_ids":[e.id for e in archive.supplemental_events],"capability_report_id":cap.id,
        "mechanical_capability_report_id":mechanical_cap.id,"noop_result_id":no_op_one.id,
        "mechanical_result_id":mech_one.id,"orders":len(mech_one.orders),"fills":len(mech_one.fills),
        "positions":len(mech_one.positions),"fees":str(mech_one.accounting[-1].fees),
        "ending_equity":str(mech_one.accounting[-1].equity),
        "classification":"NON_RESEARCH_MECHANICAL_FIXTURE"}
    return facts


def main(repository:Path)->dict:
    repository=repository.resolve();output=repository/OUTPUT_RELATIVE
    if output.exists():raise FileExistsError("smoke output already exists")
    pre=audit_pass_b(repository);btc_path=repository/"data/backtests/hyperliquid_btc_2026-08-07_to_2026-08-21_mainnet.partial/BTC_1m.csv"
    btc_pre=sha256(btc_path.read_bytes()).hexdigest()
    common=dict(repository_root=repository,archive_root=repository/"data/backtests/es_nq_pass_b_archive_3",
        plan_root=repository/"data/backtests/es_nq_pass_b_plan_3",
        continuation_root=repository/"data/backtests/es_nq_pass_b_continuation_plan_1",
        final_audit_path=repository/"outputs/archive_audits/es_nq_pass_b_final_audit.json")
    facts={}
    for market in ("ES","NQ"):
        adapter=PassBV3ArchiveAdapter(market=market,**common);adapter.validate();facts[market]=run_market(output,market,adapter)
    btc=BTCPhase7PartialAdapter(repository/"data/backtests/hyperliquid_btc_2026-08-07_to_2026-08-21_mainnet.partial")
    btc_meta=btc.validate();btc_rows=[]
    for item in btc.iter_events():
        btc_rows.append(item.bar)
        if len(btc_rows)==20:break
    btc_facts={"dataset_fingerprint":btc_meta.dataset_fingerprint,"classification":btc_meta.eligibility.classification,
        "rows_inspected":len(btc_rows),"coverage_end_exclusive":btc_meta.coverage_end_exclusive,
        "training_validation":btc_meta.eligibility.training_validation,"untouched_oos":btc_meta.eligibility.untouched_oos,
        "final_acceptance":btc_meta.eligibility.final_acceptance}
    write_new(output/"btc_partial_status.json",stable_json(btc_facts))
    post=audit_pass_b(repository);btc_post=sha256(btc_path.read_bytes()).hexdigest()
    if pre["archive_tree_sha256"]!=post["archive_tree_sha256"] or btc_pre!=btc_post:raise ValueError("archive mutation detected")
    audit={"smoke_version":SMOKE_VERSION,"status":"PASS","markets":facts,"BTC":btc_facts,
        "archive_tree_pre":pre["archive_tree_sha256"],"archive_tree_post":post["archive_tree_sha256"],
        "btc_sha256_pre":btc_pre,"btc_sha256_post":btc_post,"archive_writes":0,"network_calls":0,
        "credential_access":False,"strategy_research":False,"classification":"INTEGRATION_SMOKE_ONLY"}
    write_new(output/"smoke_audit.json",stable_json(audit))
    return audit


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True)
    args=parser.parse_args();print(json.dumps(canonical(main(args.repository)),sort_keys=True))
