from datetime import datetime, timezone
import json
import pytest

from futures_data.gap_minute_recheck import GapMinuteRecheckError, recheck

T=datetime(2026,9,2,23,25,tzinfo=timezone.utc)


def response(results=(), **extra):
    body={"status":"OK","results":list(results),**extra}
    return lambda request,key:(200,json.dumps(body).encode(),"request-id")


def test_empty_complete_recheck_is_retained_as_absent_without_authority():
    evidence,raw=recheck("ESU6",T,"secret",response())
    assert evidence["classification"]=="PROVIDER_CONFIRMED_NO_AGGREGATE_ON_RECHECK"
    assert evidence["request_count"]==1 and evidence["archive_modified"] is False
    assert evidence["trading_authority"] is False and evidence["raw_sha256"]
    assert json.loads(raw)["results"]==[]


def test_exact_bar_is_present():
    ns=int(T.timestamp()*1_000_000_000)
    evidence,_=recheck("ESU6",T,"secret",response(({"window_start":ns},)))
    assert evidence["classification"]=="AGGREGATE_PRESENT"


@pytest.mark.parametrize("fetch",[
    lambda request,key:(500,b"{}",None), response(next_url="https://forbidden"),
    response(({"window_start":1},)), response(({"window_start":int(T.timestamp()*1_000_000_000)},)*2),
])
def test_incomplete_or_boundary_conflicting_response_fails_closed(fetch):
    with pytest.raises(GapMinuteRecheckError): recheck("ESU6",T,"secret",fetch)


def test_scope_alignment_and_credential_are_strict():
    for ticker,minute,key in (("BTC",T,"x"),("ESU6",T.replace(second=1),"x"),("ESU6",T,"")):
        with pytest.raises(GapMinuteRecheckError): recheck(ticker,minute,key,response())
