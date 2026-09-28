from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import hashlib

import pytest

from execution.paper_closed_bar_input_v1 import validate_closed_btc_mark, ClosedBTCBarError
from execution.test_paper_performance_ledger_v1 import T, H, accounting
from execution.test_bounded_paper_session_v1 import driver
from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1

HEADER = "symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"


def row(offset=0, **changes):
    values = dict(symbol="BTC", timeframe="1m", open_time=(T+timedelta(minutes=offset)).isoformat(),
        close_time=(T+timedelta(minutes=offset+1)).isoformat(), open="50000", high="51000",
        low="49000", close="50500", volume="12", is_closed="true")
    values.update(changes)
    return ",".join(values.values())+"\n"


def validate(body=None, **changes):
    payload = (HEADER + (row() if body is None else body)).encode()
    args = dict(payload=payload, expected_sha256=hashlib.sha256(payload).hexdigest(),
        timeframe="1m", available_at=T+timedelta(minutes=1), as_of=T+timedelta(minutes=1),
        maximum_bar_age=timedelta(minutes=1), instrument_id="BTC",
        mark_specification_id=H("mark-spec"), source_version="btc-1m-fixture-v1")
    args.update(changes)
    return validate_closed_btc_mark(**args)


def test_exact_close_and_lineage_are_immutable():
    result = validate()
    assert result.mark.price == Decimal("50500")
    assert result.mark.observed_at == T+timedelta(minutes=1)
    assert result.mark.available_at == result.mark.observed_at
    assert result.mark.price_event_id == result.receipt_id
    assert result.source_sha256 == hashlib.sha256((HEADER+row()).encode()).hexdigest()
    assert result.trading_authority is False
    with pytest.raises(FrozenInstanceError):
        result.timeframe = "15m"
    with pytest.raises(ClosedBTCBarError, match="authority"):
        replace(result, trading_authority=True)


def test_perpetual_mark_has_explicit_contract_identity():
    result=validate(market="BTC-PERP",contract_id="BTC-PERP")
    assert (result.mark.market,result.mark.instrument_id,result.mark.contract_id)==(
        "BTC-PERP","BTC","BTC-PERP")
    with pytest.raises(ClosedBTCBarError,match="identity"):
        validate(market="BTC-PERP",contract_id=None)


@pytest.mark.parametrize("change", [{"symbol":"ES"}, {"timeframe":"15m"},
    {"is_closed":"false"}, {"close":"NaN"}, {"high":"1"}, {"volume":"-1"},
    {"open":"-1","high":"-1","low":"-3","close":"-2"},
    {"close_time":(T+timedelta(seconds=59)).isoformat()},
    {"open_time":(T+timedelta(seconds=1)).isoformat(),"close_time":(T+timedelta(seconds=61)).isoformat()}])
def test_invalid_bar_evidence_rejects(change):
    with pytest.raises(ClosedBTCBarError):
        validate(row(**change))


@pytest.mark.parametrize("body", [row()+row(), row()+row(2), row(1)+row()])
def test_duplicate_gap_regression_reject(body):
    with pytest.raises(ClosedBTCBarError):
        validate(body, available_at=T+timedelta(minutes=4), as_of=T+timedelta(minutes=4))


def test_source_hash_future_and_stale_gates():
    with pytest.raises(ClosedBTCBarError, match="checksum"):
        validate(expected_sha256="f"*64)
    with pytest.raises(ClosedBTCBarError, match="not yet available"):
        validate(available_at=T+timedelta(minutes=2))
    with pytest.raises(ClosedBTCBarError, match="closes after"):
        validate(available_at=T)
    with pytest.raises(ClosedBTCBarError, match="stale"):
        validate(as_of=T+timedelta(minutes=3))
    with pytest.raises(ClosedBTCBarError, match="UTC"):
        validate(as_of=T.replace(tzinfo=None))


def test_polling_replay_retains_first_availability_and_conflicts_reject():
    original = validate()
    assert validate(previous=original, available_at=T+timedelta(minutes=1,seconds=2),
        as_of=T+timedelta(minutes=1,seconds=2)) is original
    with pytest.raises(ClosedBTCBarError, match="conflicting"):
        validate(row(close="50600"), previous=original)
    with pytest.raises(ClosedBTCBarError, match="lineage"):
        validate(previous=original, source_version="different")


def test_next_bar_requires_continuity_and_rejects_retained_revision():
    first = validate()
    second = validate(row()+row(1), previous=first,
        available_at=T+timedelta(minutes=2), as_of=T+timedelta(minutes=2))
    assert second.source_row_count == 2
    with pytest.raises(ClosedBTCBarError, match="sequence"):
        validate(row(2), previous=first, available_at=T+timedelta(minutes=3), as_of=T+timedelta(minutes=3))
    with pytest.raises(ClosedBTCBarError, match="conflicting"):
        validate(row(close="50600")+row(1), previous=first,
            available_at=T+timedelta(minutes=2), as_of=T+timedelta(minutes=2))


def test_fifteen_minute_bar_is_valuation_not_execution_bar():
    result = validate(row(timeframe="15m",close_time=(T+timedelta(minutes=15)).isoformat()),
        timeframe="15m", available_at=T+timedelta(minutes=15), as_of=T+timedelta(minutes=15))
    assert result.timeframe == "15m" and result.mark.price_type == "MARK"


def test_mark_projects_through_bounded_driver_without_orders(tmp_path):
    item = driver(tmp_path); item.start(T)
    receipt = validate()
    now = receipt.mark.available_at
    _, _, _, book = item.step(SupervisedPaperCycleV1(now,now), closed_mark=receipt.mark)
    assert book.snapshot.position.mark_price == Decimal("50500")
    assert book.fill_bindings == ()
    stopped = item.stop(now)
    assert stopped.commands == 0 and stopped.state == "STOPPED"


def test_size_and_row_caps():
    with pytest.raises(ClosedBTCBarError, match="size"):
        validate(payload=b"", expected_sha256=hashlib.sha256(b"").hexdigest())
    with pytest.raises(ClosedBTCBarError, match="row count"):
        validate(row()*1001)
