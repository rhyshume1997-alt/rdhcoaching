"""The only module in ``tbot`` that opens a socket.

**Read-only public market data.**  Two endpoints per venue — a klines REST call for backfill and
a public candle websocket for live updates — no API key, no signature, no account endpoints, and
no code path that could place, amend or cancel an order.  If you are auditing this package for
exchange access, this file and this file alone is what you need to read.

Failure handling is a first-class feature, not a fallback:

* every disconnect is retried with exponential backoff and jitter, capped;
* a rate-limit response (HTTP 429/418, Bybit ``retCode`` 10006) is distinguished from a network
  error and honours the venue's ``Retry-After``;
* every state change is written to :class:`~tbot.dashboard.store.ConnectionState`, which the UI
  renders verbatim.  While the feed is not ``live`` the frontend labels the numbers as not live
  rather than showing the last price as if it were current.

``ReplayFeed`` is a third, offline "source": deterministic candles from the repository's own
synthetic CSV, played forward on a timer.  It needs no network at all, which is what makes the
dashboard demonstrable and testable without an exchange.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import logging
import random
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence

from tbot.models import Timeframe

from .exchanges import ExchangeAdapter, Kline, RateLimited, adapter_for
from .settings import SettingsStore
from .store import MarketData

__all__ = ["MarketFeed", "ReplayFeed", "build_feed", "backoff_delay"]

log = logging.getLogger("tbot.dashboard.feed")

#: **[OUR CHOICE]** — reconnect schedule.  1s, 2s, 4s ... capped at 60s, with up to 30 % jitter
#: so several streams do not all retry on the same tick.
BACKOFF_BASE = 1.0
BACKOFF_CAP = 60.0
BACKOFF_JITTER = 0.3

#: A connection that has stayed up this long is treated as healthy and resets the attempt count.
HEALTHY_AFTER = 90.0

OnClosedBar = Callable[[str, str], Awaitable[None] | None]
OnTick = Callable[[str, str], Awaitable[None] | None]


def backoff_delay(attempt: int, *, base: float = BACKOFF_BASE, cap: float = BACKOFF_CAP,
                  jitter: float = BACKOFF_JITTER, rand: Callable[[], float] | None = None) -> float:
    """Exponential backoff with jitter.  Pure, so the schedule is testable."""
    attempt = max(0, int(attempt))
    raw = min(cap, base * (2.0 ** attempt))
    r = (rand or random.random)()
    return round(raw * (1.0 - jitter + 2.0 * jitter * r), 3)


class _FeedBase:
    def __init__(self, market: MarketData, settings: SettingsStore, *,
                 on_closed_bar: OnClosedBar | None = None,
                 on_tick: OnTick | None = None,
                 on_state: Callable[[], Awaitable[None] | None] | None = None) -> None:
        self.market = market
        self.settings = settings
        self.on_closed_bar = on_closed_bar
        self.on_tick = on_tick
        self.on_state = on_state
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self._supervise(), name="tbot-feed")

    async def stop(self) -> None:
        self._stopping.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.market.connection.set("stopped", "feed stopped")
        await self._announce()

    async def _supervise(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    # ------------------------------------------------------------------ callbacks

    async def _announce(self) -> None:
        if self.on_state is None:
            return
        maybe = self.on_state()
        if asyncio.iscoroutine(maybe):
            await maybe

    async def _emit_closed(self, symbol: str, tf: str) -> None:
        if self.on_closed_bar is None:
            return
        maybe = self.on_closed_bar(symbol, tf)
        if asyncio.iscoroutine(maybe):
            await maybe

    async def _emit_tick(self, symbol: str, tf: str) -> None:
        if self.on_tick is None:
            return
        maybe = self.on_tick(symbol, tf)
        if asyncio.iscoroutine(maybe):
            await maybe

    async def _ingest(self, symbol: str, tf: str, kline: Kline) -> None:
        store = self.market.store(symbol, tf)
        closed = store.apply(kline)
        self.market.connection.note_message()
        if closed:
            await self._emit_closed(symbol, tf)
        else:
            await self._emit_tick(symbol, tf)


# =========================================================================== live exchange feed


class MarketFeed(_FeedBase):
    """REST backfill + public websocket, with backoff and rate-limit handling."""

    def __init__(self, market: MarketData, settings: SettingsStore, *,
                 adapter: ExchangeAdapter | None = None,
                 http_factory: Callable[[], Any] | None = None,
                 ws_connect: Callable[..., Any] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(market, settings, **kwargs)
        s = settings.settings
        self.adapter = adapter or adapter_for(s.source, category=(
            "linear" if s.venue_kind == "perp" else "spot"))
        self._http_factory = http_factory
        self._ws_connect = ws_connect
        self._subs: tuple[tuple[str, str], ...] = ()

    # ------------------------------------------------------------------ REST

    def _client(self) -> Any:
        if self._http_factory is not None:
            return self._http_factory()
        import httpx

        return httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "tbot-dashboard/1.0"})

    async def backfill(self, client: Any, symbol: str, tf: str) -> int:
        """One REST page of history for one pair.  Raises :class:`RateLimited` when told to."""
        settings = self.settings.settings
        url, params = self.adapter.rest_request(symbol, tf, settings.history_bars)
        response = await client.get(url, params=params)
        status = int(getattr(response, "status_code", 200))
        try:
            body: Any = response.json()
        except Exception:
            body = getattr(response, "text", "")
        err = self.adapter.rest_error(status, dict(getattr(response, "headers", {})), body)
        if err is not None:
            raise err
        klines = self.adapter.parse_klines(body)
        store = self.market.store(symbol, tf)
        count = store.backfill(klines)
        store.clear_gap()
        return count

    async def backfill_all(self, subs: Sequence[tuple[str, str]]) -> None:
        conn = self.market.connection
        client = self._client()
        try:
            for symbol, tf in subs:
                if self._stopping.is_set():
                    return
                try:
                    n = await self.backfill(client, symbol, tf)
                except RateLimited as exc:
                    conn.retry_after = exc.retry_after
                    conn.last_error = str(exc)
                    conn.set("rate_limited",
                             f"{self.adapter.name} asked us to wait {exc.retry_after:.0f}s")
                    await self._announce()
                    raise
                else:
                    log.info("backfilled %s %s: %d closed bars", symbol, tf, n)
                    await self._emit_closed(symbol, tf)
                # be a polite client: the venue publishes weight limits, we stay well under
                await asyncio.sleep(0.25)
        finally:
            close = getattr(client, "aclose", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()

    # ------------------------------------------------------------------ websocket

    async def _connect_ws(self, url: str) -> Any:
        if self._ws_connect is not None:
            return await self._ws_connect(url)
        import websockets

        return await websockets.connect(url, ping_interval=20, ping_timeout=20,
                                        max_queue=512, open_timeout=20)

    async def _stream_once(self, subs: Sequence[tuple[str, str]]) -> None:
        conn = self.market.connection
        url = self.adapter.stream_url(subs)
        conn.set("connecting", f"connecting to {self.adapter.name}")
        await self._announce()
        ws = await self._connect_ws(url)
        connected_at = time.time()
        try:
            for frame in self.adapter.subscribe_messages(subs):
                await ws.send(frame)
            conn.set("live", f"{self.adapter.name} stream open ({len(subs)} streams)")
            conn.last_error = ""
            conn.retry_after = None
            conn.next_retry_at = None
            await self._announce()

            ping_task: asyncio.Task | None = None
            if self.adapter.ping_message() and self.adapter.ping_interval > 0:
                ping_task = asyncio.create_task(self._ping_loop(ws))
            try:
                async for raw in ws:
                    if self._stopping.is_set():
                        break
                    if time.time() - connected_at > HEALTHY_AFTER and conn.attempts:
                        conn.attempts = 0
                    parsed = self.adapter.parse_message(raw)
                    if parsed is None:
                        conn.note_message()
                        continue
                    symbol, tf, kline = parsed
                    if (symbol, tf) not in set(subs):
                        continue
                    await self._ingest(symbol, tf, kline)
            finally:
                if ping_task is not None:
                    ping_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await ping_task
        finally:
            close = getattr(ws, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result

    async def _ping_loop(self, ws: Any) -> None:
        msg = self.adapter.ping_message()
        while msg and not self._stopping.is_set():
            await asyncio.sleep(self.adapter.ping_interval)
            with contextlib.suppress(Exception):
                await ws.send(msg)

    # ------------------------------------------------------------------ supervision

    async def _supervise(self) -> None:
        conn = self.market.connection
        while not self._stopping.is_set():
            subs = self.settings.settings.subscriptions()
            self._subs = subs
            self.market.prune(subs)
            try:
                await self.backfill_all(subs)
                await self._stream_once(subs)
                if self._stopping.is_set():
                    return
                conn.set("reconnecting", "stream closed by the venue")
            except asyncio.CancelledError:
                raise
            except RateLimited as exc:
                conn.attempts += 1
                delay = max(exc.retry_after, backoff_delay(conn.attempts))
                conn.next_retry_at = time.time() + delay
                await self._announce()
                await self._sleep(delay)
                continue
            except Exception as exc:
                conn.last_error = f"{type(exc).__name__}: {exc}"
                conn.set("reconnecting", conn.last_error)
                log.warning("feed error: %s", conn.last_error)

            conn.attempts += 1
            delay = backoff_delay(conn.attempts)
            conn.next_retry_at = time.time() + delay
            conn.set("reconnecting",
                     f"retrying in {delay:.0f}s (attempt {conn.attempts})"
                     + (f" — {conn.last_error}" if conn.last_error else ""))
            await self._announce()
            await self._sleep(delay)

    async def _sleep(self, delay: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=max(0.0, delay))


# =========================================================================== offline replay


DEFAULT_REPLAY_CSV = Path(__file__).resolve().parents[2] / "data" / "synthetic_4h.csv"


def _load_replay_rows(path: Path) -> list[tuple[float, float, float, float, float, float]]:
    rows: list[tuple[float, float, float, float, float, float]] = []
    with path.open(newline="") as fh:
        for rec in csv.DictReader(fh):
            rows.append((float(rec["open"]), float(rec["high"]), float(rec["low"]),
                         float(rec["close"]), float(rec.get("volume") or 0.0),
                         float(rec.get("quote_volume") or 0.0)))
    if not rows:
        raise ValueError(f"replay CSV {path} has no rows")
    return rows


def _scale_for(symbol: str) -> float:
    """A deterministic per-symbol price scale, so replay pairs do not all sit at 100."""
    h = 0
    for ch in symbol:
        h = (h * 131 + ord(ch)) % 100_003
    return round(0.25 + (h % 400) / 10.0, 4)


class ReplayFeed(_FeedBase):
    """Deterministic offline candles, played forward on a timer.

    Not an exchange and not a simulation of one: it exists so the dashboard can be run, shown
    and tested end to end with no network.  The connection state reports ``replay`` and the UI
    labels it as replay, never as a live venue.
    """

    def __init__(self, market: MarketData, settings: SettingsStore, *,
                 csv_path: Path | str | None = None,
                 bar_seconds: float = 6.0, tick_seconds: float = 1.0,
                 clock: Callable[[], float] = time.time, **kwargs: Any) -> None:
        super().__init__(market, settings, **kwargs)
        self.csv_path = Path(csv_path or DEFAULT_REPLAY_CSV)
        self.bar_seconds = float(bar_seconds)
        self.tick_seconds = float(tick_seconds)
        self._clock = clock
        self._rows = _load_replay_rows(self.csv_path)
        self._cursor: dict[tuple[str, str], int] = {}

    def _kline(self, symbol: str, tf: str, position: int, open_ms: int,
               *, closed: bool, progress: float = 1.0) -> Kline:
        o, h, l, c, v, q = self._rows[position % len(self._rows)]
        scale = _scale_for(symbol)
        o, h, l, c = o * scale, h * scale, l * scale, c * scale
        if not closed:
            # a partial bar: the close walks from open to its eventual close
            c = o + (c - o) * max(0.0, min(1.0, progress))
            h = max(o, c, o + (h - o) * progress)
            l = min(o, c, o + (l - o) * progress)
            v = v * progress
            q = q * progress
        return Kline(open_ms, o, h, l, c, v, q, closed)

    def seed(self, symbol: str, tf: str, bars: int, *, now_ms: int | None = None) -> int:
        """Fill a store with ``bars`` closed bars ending just before now.  Synchronous."""
        step = Timeframe.parse(tf).minutes * 60_000
        now_ms = int(self._clock() * 1000) if now_ms is None else int(now_ms)
        last_open = (now_ms // step) * step - step
        start = last_open - (bars - 1) * step
        klines = [self._kline(symbol, tf, i, start + i * step, closed=True)
                  for i in range(bars)]
        store = self.market.store(symbol, tf)
        count = store.backfill(klines, now_ms=now_ms)
        self._cursor[(symbol.upper(), tf)] = bars
        return count

    async def _supervise(self) -> None:
        conn = self.market.connection
        conn.source = "replay"
        subs = self.settings.settings.subscriptions()
        self.market.prune(subs)
        conn.set("connecting", "seeding replay history")
        await self._announce()
        for symbol, tf in subs:
            self.seed(symbol, tf, self.settings.settings.history_bars)
            await self._emit_closed(symbol, tf)
        conn.set("replay", f"offline replay from {self.csv_path.name} — not live market data")
        await self._announce()

        elapsed = 0.0
        while not self._stopping.is_set():
            await self._sleep(self.tick_seconds)
            if self._stopping.is_set():
                return
            elapsed += self.tick_seconds
            close_bar = elapsed >= self.bar_seconds
            for symbol, tf in self.settings.settings.subscriptions():
                key = (symbol.upper(), tf)
                pos = self._cursor.get(key)
                if pos is None:
                    self.seed(symbol, tf, self.settings.settings.history_bars)
                    continue
                store = self.market.store(symbol, tf)
                last = store.last_closed_open_ms
                if last is None:
                    continue
                step = Timeframe.parse(tf).minutes * 60_000
                open_ms = last + step
                if close_bar:
                    await self._ingest(symbol, tf,
                                       self._kline(symbol, tf, pos, open_ms, closed=True))
                    self._cursor[key] = pos + 1
                else:
                    progress = min(0.99, elapsed / self.bar_seconds)
                    await self._ingest(symbol, tf,
                                       self._kline(symbol, tf, pos, open_ms,
                                                   closed=False, progress=progress))
            conn.note_message()
            if close_bar:
                elapsed = 0.0

    async def _sleep(self, delay: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=max(0.0, delay))


def build_feed(market: MarketData, settings: SettingsStore, **kwargs: Any) -> _FeedBase:
    """``source`` decides which feed the app runs."""
    source = settings.settings.source
    if source == "replay":
        return ReplayFeed(market, settings, **kwargs)
    return MarketFeed(market, settings, **kwargs)
