from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from futures_data.archive import archive_path, commit_archive, single_writer_lock, verify_archive
from futures_data.contracts import ContractSpec, FuturesBar, FuturesRoot, Page, identity, SCHEMA_VERSION
from futures_data.massive import MassiveFuturesProvider, RetryPolicy, parse_outright_ticker
from futures_data.planning import ForwardCollectorPolicy, PROHIBITED_CAPABILITIES, create_backfill_plan
from futures_data.rollover import RollPolicy, RollRule, decide_roll, stitch_unadjusted
from futures_data.sessions import IntervalClassification, SessionCalendar, classify_gaps

UTC = timezone.utc
NOW = datetime(2026, 1, 15, 20, tzinfo=UTC)


def row(ticker="ESH2026", root="ES"):
    return {"ticker":ticker,"instrument_type":"future","is_continuous":False,"exchange":"CME",
        "first_trade_date":"2025-03-01","last_trade_date":"2026-03-20","expiration_date":"2026-03-20",
        "settlement_date":"2026-03-20","tick_size":"0.25","tick_value":"12.50",
        "multiplier":"50","source_version":"mock-v1"}


def transport(operation, params):
    if operation in ("contracts", "contract"):
        raw=b'{"mock":"contract"}'; return Page((row(params.get("ticker","ESH2026")),), raw, None)
    if operation == "minute-bars":
        start=datetime.fromisoformat(params["start"]); ms=int(start.timestamp()*1000)
        record={"timestamp":ms,"provider_timestamp":ms+1,"open":"5000.00","high":"5001.00",
                "low":"4999.75","close":"5000.25","volume":"10","finalized":True}
        return Page((record,), b'{"mock":"bar"}', None, rate_limit_remaining=4)
    return Page((), b'{}', None)


def provider(transport_fn=transport, sleep=lambda _:None):
    return MassiveFuturesProvider(transport_fn, now=lambda:NOW, sleep=sleep,
        policy=RetryPolicy(calls_per_minute=4, max_attempts=3), random_seed=1)


def contract(ticker="ESH2026"):
    return provider().get_contract(ticker, as_of=NOW)


def bar(spec, minute=0, volume="10"):
    opened=datetime(2026,1,15,20,minute,tzinfo=UTC); closed=opened+timedelta(minutes=1)
    return FuturesBar(identity(SCHEMA_VERSION,spec.id,opened.isoformat(),closed.isoformat()),spec.id,
        spec.provider_ticker,spec.root,opened,closed,opened,Decimal("5000"),Decimal("5001"),
        Decimal("4999"),Decimal("5000.25"),Decimal(volume),True,spec.source_version)


@pytest.mark.parametrize("ticker,hint,expected", [("ESH26",None,(FuturesRoot.ES,3,2026)),("NQZ2027",None,(FuturesRoot.NQ,12,2027)),("ESU6",2026,(FuturesRoot.ES,9,2026))])
def test_contract_parsing(ticker, hint, expected): assert parse_outright_ticker(ticker,contract_year_hint=hint)==expected


def test_one_digit_contract_year_requires_point_in_time_hint():
    with pytest.raises(ValueError): parse_outright_ticker("ESU6")
    with pytest.raises(ValueError): parse_outright_ticker("ESU6",contract_year_hint=2037)


@pytest.mark.parametrize("ticker", ["ES1!","MESZ26","NQH26-NQM26","ES","SPY","ESH26C5000"])
def test_rejects_continuous_micro_spread_option_and_wrong_root(ticker):
    with pytest.raises(ValueError): parse_outright_ticker(ticker)


def test_contract_and_bar_are_exact_and_audited():
    spec=contract(); bars,manifest=provider().get_minute_bars(spec,start=NOW,end=NOW+timedelta(minutes=1))
    assert bars[0].open==Decimal("5000.00") and manifest.raw_sha256 and manifest.parameters==tuple(sorted(manifest.parameters))
    with pytest.raises(TypeError):
        bad=row(); bad["tick_size"]=0.25; provider(lambda *_:Page((bad,),b'{}',None)).get_contract("ESH2026",as_of=NOW)


def test_pagination_cursor_and_rate_limit_retry_after():
    calls=[]; sleeps=[]
    def mock(op,params):
        calls.append(dict(params))
        if len(calls)==1:return Page((),b'busy',None,429,retry_after_seconds=Decimal("2"))
        return transport(op,params)
    spec=provider().get_contract("ESH2026",as_of=NOW)
    bars,manifest=provider(mock,sleeps.append).get_minute_bars(spec,start=NOW,end=NOW+timedelta(minutes=1),cursor="c1")
    assert bars and calls[-1]["cursor"]=="c1" and any(x>=2 for x in sleeps)


def test_forming_out_of_range_duplicate_and_ordering_rejected():
    spec=contract(); ms=int(NOW.timestamp()*1000); base={"timestamp":ms,"open":"1","high":"1","low":"1","close":"1","volume":"0","finalized":False}
    with pytest.raises(ValueError): provider(lambda *_:Page((base,),b'x',None)).get_minute_bars(spec,start=NOW,end=NOW+timedelta(minutes=1))
    good={**base,"finalized":True}
    with pytest.raises(ValueError): provider(lambda *_:Page((good,good),b'x',None)).get_minute_bars(spec,start=NOW,end=NOW+timedelta(minutes=1))


def test_sessions_dst_maintenance_holiday_early_close_and_gap():
    cal=SessionCalendar(frozenset({date(2026,1,19)}),((date(2026,11,27),time(12)),))
    assert cal.classify(datetime(2026,3,9,21,30,tzinfo=UTC)) is IntervalClassification.MAINTENANCE
    assert cal.classify(datetime(2026,1,19,18,tzinfo=UTC)) is IntervalClassification.HOLIDAY
    assert cal.classify(datetime(2026,11,27,19,tzinfo=UTC)) is IntervalClassification.EARLY_CLOSE
    facts=classify_gaps((NOW,NOW+timedelta(minutes=3)),cal); assert sum(x.missing_minutes for x in facts)==2


def test_rollover_no_lookahead_and_unadjusted_stitch():
    old=contract(); r=row("ESM2026"); r["first_trade_date"]="2025-06-01"; r["last_trade_date"]="2026-06-19"; r["expiration_date"]="2026-06-19"; r["settlement_date"]="2026-06-19"
    new=provider(lambda *_:Page((r,),b'{}',None)).get_contract("ESM2026",as_of=NOW)
    policy=RollPolicy(identity("roll-policy-v1",RollRule.VOLUME_CROSSOVER.value,"v1",None),RollRule.VOLUME_CROSSOVER,"v1")
    old_bar,new_bar=bar(old,0,"5"),bar(new,0,"10")
    decision=decide_roll(old=old,new=new,policy=policy,decision_time=NOW+timedelta(minutes=1),evidence=(old_bar,new_bar))
    assert decision.effective_time==NOW+timedelta(minutes=2)
    with pytest.raises(ValueError): decide_roll(old=old,new=new,policy=policy,decision_time=NOW,evidence=(old_bar,))


def test_archive_atomic_checksum_isolation_idempotent_and_lock(tmp_path):
    spec=contract(); bars=(bar(spec),); directory=archive_path(tmp_path,FuturesRoot.ES)
    _,request=provider().get_minute_bars(spec,start=NOW,end=NOW+timedelta(minutes=1))
    first=commit_archive(directory=directory,root=FuturesRoot.ES,provider="massive-futures",contracts=(spec,),bars=bars,requests=(request,),gaps=(),created_at=NOW)
    second=commit_archive(directory=directory,root=FuturesRoot.ES,provider="massive-futures",contracts=(spec,),bars=bars,requests=(request,),gaps=(),created_at=NOW)
    assert first.id==second.id and verify_archive(directory)["root"]=="ES"
    with single_writer_lock(directory):
        with pytest.raises(RuntimeError):
            with single_writer_lock(directory): pass
    (directory/"bars.jsonl").write_bytes(b"corrupt")
    with pytest.raises(ValueError): verify_archive(directory)
    with pytest.raises(ValueError): commit_archive(directory=archive_path(tmp_path,FuturesRoot.NQ),root=FuturesRoot.NQ,provider="x",contracts=(spec,),bars=bars,requests=(),gaps=(),created_at=NOW)


def test_dry_run_hard_limits_and_forward_cutoff(tmp_path):
    spec=contract(); plan=create_backfill_plan(repository=tmp_path,contracts=(spec,),start=NOW-timedelta(days=365),end=NOW)
    assert plan.dry_run_only and plan.licensing_confirmation_required and plan.expected_calls>0
    assert "es_forward_archive_1" in plan.archive_paths[0]
    with pytest.raises(ValueError): create_backfill_plan(repository=tmp_path,contracts=(spec,),start=NOW-timedelta(days=800),end=NOW)
    policy=ForwardCollectorPolicy(timedelta(minutes=15),timedelta(minutes=2))
    assert policy.finalized_cutoff(NOW)==NOW-timedelta(minutes=17)


def test_no_trading_or_account_capabilities():
    instance=provider()
    assert PROHIBITED_CAPABILITIES=={"orders","positions","accounts","wallets","signing","execution"}
    assert all(not hasattr(instance,name) for name in PROHIBITED_CAPABILITIES)
