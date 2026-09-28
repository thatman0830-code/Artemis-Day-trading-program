from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backtesting.downloader import PUBLIC_URLS, PublicCandleTransport, _ms
from backtesting.market_data import CanonicalTimeframe


@dataclass(frozen=True)
class StreamCoverage:
    timeframe: CanonicalTimeframe
    earliest: datetime | None
    latest_closed: datetime | None
    candle_count: int
    contiguous_windows: tuple[tuple[datetime, datetime], ...]
    gap_count: int
    duplicate_count: int
    overlap_count: int
    malformed_count: int


@dataclass(frozen=True)
class CoverageSelection:
    sufficient: bool
    dataset_start: datetime | None
    scored_start: datetime | None
    replay_end: datetime | None
    reasons: tuple[str, ...]


def _dt(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc)


class RecentCoverageProbe:
    def __init__(self, *, transport=None, now=None):
        self.transport=transport or PublicCandleTransport()
        self.now=now or (lambda:datetime.now(timezone.utc))

    def probe(self, *, symbol: str, timeframes: tuple[CanonicalTimeframe, ...],
              data_network: str) -> tuple[StreamCoverage, ...]:
        if data_network not in PUBLIC_URLS:
            raise ValueError("unsupported public data network")
        end=self.now().astimezone(timezone.utc); results=[]
        for timeframe in timeframes:
            payload=json.dumps({"type":"candleSnapshot","req":{"coin":symbol,
                "interval":timeframe.value,"startTime":0,"endTime":_ms(end)}},
                separators=(",",":"),sort_keys=True).encode()
            rows=json.loads(self.transport.post(url=PUBLIC_URLS[data_network],
                payload=payload,timeout=15).decode(),parse_float=str,parse_int=int)
            if not isinstance(rows,list): raise ValueError("malformed coverage response")
            duration=int(timeframe.duration.total_seconds()*1000); valid=[]; malformed=0
            for row in rows:
                if not isinstance(row,dict) or not {"t","T","s","i","o","h","l","c"}<=set(row):
                    malformed+=1; continue
                if row["T"]-row["t"] not in (duration,duration-1):
                    malformed+=1; continue
                close=row["t"]+duration
                if close<=_ms(end): valid.append((row["t"],close))
            valid.sort(); duplicate=len(valid)-len({item[0] for item in valid})
            unique=sorted(set(valid)); overlaps=0; windows=[]
            if unique:
                start,prior_end=unique[0]
                for opened,closed in unique[1:]:
                    if opened<prior_end: overlaps+=1
                    if opened!=prior_end:
                        windows.append((_dt(start),_dt(prior_end))); start=opened
                    prior_end=max(prior_end,closed)
                windows.append((_dt(start),_dt(prior_end)))
            results.append(StreamCoverage(timeframe,_dt(unique[0][0]) if unique else None,
                _dt(unique[-1][1]) if unique else None,len(unique),tuple(windows),
                max(0,len(windows)-1),duplicate,overlaps,malformed))
        return tuple(results)


def select_diagnostic_interval(coverage: tuple[StreamCoverage, ...], *,
                               reference_bars: int = 20,
                               minimum_scored: timedelta = timedelta(hours=6)) -> CoverageSelection:
    reasons=[]
    if not coverage or any(item.earliest is None or item.latest_closed is None for item in coverage):
        return CoverageSelection(False,None,None,None,("REQUIRED_STREAM_EMPTY",))
    for item in coverage:
        if item.gap_count or item.duplicate_count or item.overlap_count or item.malformed_count:
            reasons.append(f"{item.timeframe.value}:DATA_QUALITY_INVALID")
    earliest=max(item.earliest for item in coverage)
    latest=min(item.latest_closed for item in coverage)
    # A boundary shared by all configured bars is a 4H UTC boundary.
    latest_ms=_ms(latest); four_hours=14_400_000
    replay_end=_dt((latest_ms//four_hours)*four_hours)
    warmup=max(item.timeframe.duration*reference_bars for item in coverage)
    structural_ready=earliest+warmup
    # Scoring starts on the first 4H boundary with a whole preceding UTC day.
    ready=max(structural_ready,
        datetime.combine((earliest+timedelta(days=1)).date(),datetime.min.time(),tzinfo=timezone.utc))
    ready_ms=_ms(ready); scored_start=_dt(((ready_ms+four_hours-1)//four_hours)*four_hours)
    prior_day_start=datetime.combine((scored_start-timedelta(days=1)).date(),
                                     datetime.min.time(),tzinfo=timezone.utc)
    dataset_start=min(earliest,prior_day_start)
    if prior_day_start<earliest:
        reasons.append("COMPLETE_PRECEDING_UTC_DAY_UNAVAILABLE")
    if scored_start- earliest < warmup:
        reasons.append("STRUCTURAL_DISPLACEMENT_WARMUP_UNAVAILABLE")
    if replay_end-scored_start<minimum_scored:
        reasons.append("SIX_HOUR_SCORED_REPLAY_UNAVAILABLE")
    return CoverageSelection(not reasons,dataset_start if not reasons else None,
                             scored_start if not reasons else None,
                             replay_end if not reasons else None,tuple(reasons))
