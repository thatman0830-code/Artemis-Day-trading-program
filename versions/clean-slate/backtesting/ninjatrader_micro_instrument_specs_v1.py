"""Verified immutable CME MES/MNQ specifications for paper-design review."""
from dataclasses import dataclass
from decimal import Decimal
import hashlib,json
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
VERSION="ninjatrader-micro-instrument-specifications-v1"
@dataclass(frozen=True)
class MicroInstrumentSpecificationV1:
 specification_id:str;market:FuturesCanonicalMarket;instrument:str;product_code:str;exchange:str;currency:str;contract_multiplier:Decimal;minimum_tick:Decimal;tick_value:Decimal;settlement:str;delivery_month:str;expiration_rule:str;primary_source_url:str;verified_on:str
 paper_design_evidence:bool=True;paper_execution_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def _make(market,instrument,code,multiplier,tick_value,url):
 body={"version":VERSION,"market":market.value,"instrument":instrument,"code":code,"exchange":"CME","currency":"USD","multiplier":format(multiplier,'f'),"tick":"0.25","tick_value":format(tick_value,'f'),"settlement":"CASH","delivery_month":"2026-09","expiration_rule":"THIRD_FRIDAY_OF_DELIVERY_MONTH","source":url,"verified_on":"2026-09-08","authority":False};identity=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 return MicroInstrumentSpecificationV1(identity,market,instrument,code,"CME","USD",multiplier,Decimal("0.25"),tick_value,"CASH","2026-09","THIRD_FRIDAY_OF_DELIVERY_MONTH",url,"2026-09-08")
def verified_micro_instrument_specifications():
 return (_make(FuturesCanonicalMarket.ES,"MES SEP26","MES",Decimal("5"),Decimal("1.25"),"https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.contractSpecs.html"),_make(FuturesCanonicalMarket.NQ,"MNQ SEP26","MNQ",Decimal("2"),Decimal("0.50"),"https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html"))
def verify_micro_instrument_specifications(specs):
 expected=verified_micro_instrument_specifications()
 if specs!=expected or tuple(x.market for x in specs)!=(FuturesCanonicalMarket.ES,FuturesCanonicalMarket.NQ)or any(x.minimum_tick*x.contract_multiplier!=x.tick_value or x.trading_authority is not False for x in specs):raise ValueError("verified MES/MNQ specifications required")
 return expected
