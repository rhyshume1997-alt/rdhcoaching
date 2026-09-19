"""Exchange wire formats — URL building and payload parsing, as pure functions.

Nothing in this module performs I/O.  It exists so the parts of exchange integration that are
easy to get wrong (interval codes, array offsets, "is this bar closed?", rate-limit signalling)
can be unit-tested with recorded payload shapes and no network at all.

Two sources, both **public market data only**:

* Binance  — ``GET /api/v3/klines`` and ``wss://stream.binance.com:9443/stream``
* Bybit    — ``GET /v5/market/kline`` and ``wss://stream.bybit.com/v5/public/{category}``

Bybit is the fallback, selected with ``--source bybit`` (config switch ``source``).

A third "source", :class:`ReplaySource`, is not an exchange at all: see :mod:`tbot.dashboard.feed`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "Kline",
    "ExchangeAdapter",
    "BinanceAdapter",
    "BybitAdapter",
    "RateLimited",
    "adapter_for",
    "SOURCES",
    "DASHBOARD_TIMEFRAMES",
]

#: Timeframes the dashboard offers.  A subset of ``tbot.models.Timeframe``: ``2D`` has no
#: Binance kline interval and ``3D`` has no Bybit one, so neither is offered rather than
#: silently served by a different bar length than the label claims.
DASHBOARD_TIMEFRAMES: tuple[str, ...] = ("15m", "30m", "1H", "2H", "4H", "8H", "12H", "1D", "1W")

SOURCES: tuple[str, ...] = ("binance", "bybit", "replay")


class RateLimited(Exception):
    """The venue asked us to slow down.  ``retry_after`` is in seconds."""

    def __init__(self, message: str, retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = float(retry_after)


@dataclass(frozen=True, slots=True)
class Kline:
    """One candle as the venue reports it.

    ``open_time_ms`` is the bar **open** time in epoch milliseconds and is the identity of the
    bar: two updates with the same ``open_time_ms`` are the same candle at different moments of
    its life.  ``is_closed`` is the venue's own flag (Binance ``k.x``, Bybit ``confirm``), never
    something we infer from the clock — a wrong guess here would feed a half-formed bar to the
    engine, which is exactly the lookahead SPEC.md §12.1 forbids.
    """

    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    is_closed: bool

    def replace_closed(self, is_closed: bool) -> "Kline":
        return Kline(self.open_time_ms, self.open, self.high, self.low, self.close,
                     self.volume, self.quote_volume, is_closed)


def _f(value: Any) -> float:
    return float(value)


class ExchangeAdapter:
    """Base class.  Subclasses are stateless; one instance per process is fine."""

    name: str = "abstract"
    #: label -> venue interval code
    intervals: Mapping[str, str] = {}
    rest_url: str = ""
    #: how many klines one REST call may return
    max_klines_per_call: int = 1000

    # ---------------------------------------------------------------- capability

    def supports(self, tf: str) -> bool:
        return tf in self.intervals

    def interval(self, tf: str) -> str:
        try:
            return self.intervals[tf]
        except KeyError:
            raise ValueError(
                f"{self.name} has no kline interval for timeframe {tf!r}; "
                f"supported: {', '.join(sorted(self.intervals))}"
            ) from None

    # ---------------------------------------------------------------- REST

    def rest_request(self, symbol: str, tf: str, limit: int) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError

    def parse_klines(self, payload: Any) -> list[Kline]:
        raise NotImplementedError

    def rest_error(self, status: int, headers: Mapping[str, str], body: Any) -> Exception | None:
        """Return the exception a non-2xx (or error-shaped 200) response should raise."""
        raise NotImplementedError

    # ---------------------------------------------------------------- websocket

    def stream_url(self, subs: Sequence[tuple[str, str]]) -> str:
        raise NotImplementedError

    def subscribe_messages(self, subs: Sequence[tuple[str, str]]) -> list[str]:
        return []

    def ping_message(self) -> str | None:
        """A text keepalive to send every ``ping_interval`` seconds, or ``None``."""
        return None

    ping_interval: float = 20.0

    def parse_message(self, raw: str | bytes) -> tuple[str, str, Kline] | None:
        """``(symbol, timeframe, kline)`` for a candle update, else ``None``.

        ``None`` covers every non-candle frame — subscribe acks, pongs, heartbeats, and
        anything we do not recognise.  An unparseable frame is never fatal.
        """
        raise NotImplementedError


# =========================================================================== Binance


class BinanceAdapter(ExchangeAdapter):
    """Binance spot public market data."""

    name = "binance"
    rest_url = "https://api.binance.com/api/v3/klines"
    ws_base = "wss://stream.binance.com:9443/stream"
    intervals = {
        "15m": "15m", "30m": "30m", "1H": "1h", "2H": "2h", "4H": "4h",
        "8H": "8h", "12H": "12h", "1D": "1d", "3D": "3d", "1W": "1w",
    }
    #: Binance closes an idle connection after 24h and pings every 3 minutes; the websockets
    #: library answers protocol-level pings itself, so no application ping is needed.
    ping_interval = 0.0

    def rest_request(self, symbol: str, tf: str, limit: int) -> tuple[str, dict[str, Any]]:
        return self.rest_url, {
            "symbol": symbol.upper(),
            "interval": self.interval(tf),
            "limit": max(1, min(int(limit), self.max_klines_per_call)),
        }

    def parse_klines(self, payload: Any) -> list[Kline]:
        # [ openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, ... ]
        if not isinstance(payload, list):
            raise ValueError(f"binance klines: expected a list, got {type(payload).__name__}")
        out: list[Kline] = []
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) < 8:
                raise ValueError(f"binance klines: malformed row {row!r}")
            out.append(Kline(
                open_time_ms=int(row[0]),
                open=_f(row[1]), high=_f(row[2]), low=_f(row[3]), close=_f(row[4]),
                volume=_f(row[5]), quote_volume=_f(row[7]),
                # REST never says so; the caller decides which trailing bar is still forming
                # from the wall clock.  See CandleStore.backfill.
                is_closed=True,
            ))
        return out

    def rest_error(self, status: int, headers: Mapping[str, str], body: Any) -> Exception | None:
        if status in (429, 418):
            retry = headers.get("Retry-After") or headers.get("retry-after")
            try:
                seconds = float(retry) if retry else 60.0
            except (TypeError, ValueError):
                seconds = 60.0
            return RateLimited(f"binance rate limit (HTTP {status})", retry_after=seconds)
        if status >= 400:
            msg = body if isinstance(body, str) else json.dumps(body)[:200]
            return RuntimeError(f"binance HTTP {status}: {msg}")
        if isinstance(body, dict) and "code" in body:
            return RuntimeError(f"binance error {body.get('code')}: {body.get('msg')}")
        return None

    def stream_url(self, subs: Sequence[tuple[str, str]]) -> str:
        names = [f"{sym.lower()}@kline_{self.interval(tf)}" for sym, tf in subs]
        return f"{self.ws_base}?streams={'/'.join(names)}"

    def parse_message(self, raw: str | bytes) -> tuple[str, str, Kline] | None:
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(msg, dict):
            return None
        data = msg.get("data", msg)
        if not isinstance(data, dict) or data.get("e") != "kline":
            return None
        k = data.get("k")
        if not isinstance(k, dict):
            return None
        tf = _reverse(self.intervals, str(k.get("i")))
        if tf is None:
            return None
        try:
            kline = Kline(
                open_time_ms=int(k["t"]),
                open=_f(k["o"]), high=_f(k["h"]), low=_f(k["l"]), close=_f(k["c"]),
                volume=_f(k.get("v", 0.0)), quote_volume=_f(k.get("q", 0.0)),
                is_closed=bool(k.get("x", False)),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return str(data.get("s") or k.get("s") or "").upper(), tf, kline


# =========================================================================== Bybit


class BybitAdapter(ExchangeAdapter):
    """Bybit v5 public market data (spot by default, ``linear`` for perps)."""

    name = "bybit"
    rest_url = "https://api.bybit.com/v5/market/kline"
    ws_base = "wss://stream.bybit.com/v5/public"
    intervals = {
        "15m": "15", "30m": "30", "1H": "60", "2H": "120", "4H": "240",
        "8H": "480", "12H": "720", "1D": "D", "1W": "W",
    }
    max_klines_per_call = 1000
    ping_interval = 20.0

    def __init__(self, category: str = "spot") -> None:
        if category not in ("spot", "linear", "inverse"):
            raise ValueError(f"bybit category must be spot|linear|inverse, got {category!r}")
        self.category = category

    def rest_request(self, symbol: str, tf: str, limit: int) -> tuple[str, dict[str, Any]]:
        return self.rest_url, {
            "category": self.category,
            "symbol": symbol.upper(),
            "interval": self.interval(tf),
            "limit": max(1, min(int(limit), self.max_klines_per_call)),
        }

    def parse_klines(self, payload: Any) -> list[Kline]:
        # result.list is NEWEST FIRST: [ start, open, high, low, close, volume, turnover ]
        if not isinstance(payload, dict):
            raise ValueError(f"bybit klines: expected an object, got {type(payload).__name__}")
        rows = (payload.get("result") or {}).get("list")
        if not isinstance(rows, list):
            raise ValueError("bybit klines: no result.list in payload")
        out: list[Kline] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 7:
                raise ValueError(f"bybit klines: malformed row {row!r}")
            out.append(Kline(
                open_time_ms=int(row[0]),
                open=_f(row[1]), high=_f(row[2]), low=_f(row[3]), close=_f(row[4]),
                volume=_f(row[5]), quote_volume=_f(row[6]),
                is_closed=True,
            ))
        out.sort(key=lambda k: k.open_time_ms)
        return out

    def rest_error(self, status: int, headers: Mapping[str, str], body: Any) -> Exception | None:
        if status in (403, 429):
            return RateLimited(f"bybit rate limit (HTTP {status})", retry_after=60.0)
        if status >= 400:
            msg = body if isinstance(body, str) else json.dumps(body)[:200]
            return RuntimeError(f"bybit HTTP {status}: {msg}")
        if isinstance(body, dict):
            code = body.get("retCode")
            if code in (10006, 10018):
                return RateLimited(f"bybit rate limit (retCode {code})", retry_after=60.0)
            if code not in (None, 0):
                return RuntimeError(f"bybit retCode {code}: {body.get('retMsg')}")
        return None

    def stream_url(self, subs: Sequence[tuple[str, str]]) -> str:
        return f"{self.ws_base}/{self.category}"

    def subscribe_messages(self, subs: Sequence[tuple[str, str]]) -> list[str]:
        args = [f"kline.{self.interval(tf)}.{sym.upper()}" for sym, tf in subs]
        # Bybit caps args per frame; ten topics per frame is comfortably inside every tier.
        frames: list[str] = []
        for i in range(0, len(args), 10):
            frames.append(json.dumps({"op": "subscribe", "args": args[i:i + 10]}))
        return frames

    def ping_message(self) -> str | None:
        return json.dumps({"op": "ping"})

    def parse_message(self, raw: str | bytes) -> tuple[str, str, Kline] | None:
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(msg, dict):
            return None
        topic = msg.get("topic")
        if not isinstance(topic, str) or not topic.startswith("kline."):
            return None
        parts = topic.split(".")
        if len(parts) != 3:
            return None
        tf = _reverse(self.intervals, parts[1])
        if tf is None:
            return None
        symbol = parts[2].upper()
        rows = msg.get("data")
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[-1]
        if not isinstance(row, dict):
            return None
        try:
            kline = Kline(
                open_time_ms=int(row["start"]),
                open=_f(row["open"]), high=_f(row["high"]), low=_f(row["low"]),
                close=_f(row["close"]),
                volume=_f(row.get("volume", 0.0)), quote_volume=_f(row.get("turnover", 0.0)),
                is_closed=bool(row.get("confirm", False)),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return symbol, tf, kline


def _reverse(mapping: Mapping[str, str], value: str) -> str | None:
    for label, code in mapping.items():
        if code == value:
            return label
    return None


def adapter_for(source: str, *, category: str = "spot") -> ExchangeAdapter:
    """``"binance"`` / ``"bybit"`` -> an adapter.  ``"replay"`` has none (it is offline)."""
    key = (source or "").strip().lower()
    if key == "binance":
        return BinanceAdapter()
    if key == "bybit":
        return BybitAdapter(category=category)
    raise ValueError(f"unknown market-data source {source!r}; expected one of {', '.join(SOURCES)}")


def supported_timeframes(source: str) -> tuple[str, ...]:
    """The dashboard timeframes a source can actually serve."""
    if (source or "").lower() == "replay":
        return DASHBOARD_TIMEFRAMES
    adapter = adapter_for(source)
    return tuple(tf for tf in DASHBOARD_TIMEFRAMES if adapter.supports(tf))


def chunk(items: Iterable[Any], size: int) -> list[list[Any]]:
    """Split ``items`` into lists of at most ``size`` (stream subscription batching)."""
    out: list[list[Any]] = []
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            out.append(batch)
            batch = []
    if batch:
        out.append(batch)
    return out
