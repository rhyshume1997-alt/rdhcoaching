"""Candle storage and connection state.  Pure: no I/O, no async, no exchange imports.

This module owns the **no-lookahead boundary**.  A :class:`CandleStore` keeps closed bars in
one list and the single still-forming bar in a separate slot, and the only way to get a
:class:`tbot.models.Series` out of it is :meth:`CandleStore.series`, which reads the closed
list and nothing else.  The forming bar is reachable only through :attr:`CandleStore.forming`,
which the HTTP layer sends to the browser for drawing and which no analysis path touches.

SPEC.md §12.1 makes no-lookahead a harness-level assertion; here it is a structural one — the
engine is never handed the object that would violate it.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Literal, Sequence

import numpy as np
import pandas as pd

from tbot.models import Series, Timeframe

from .exchanges import Kline

__all__ = [
    "CandleStore",
    "ConnectionState",
    "MarketData",
    "ConnectionStatus",
    "bar_close_ms",
]

ConnectionStatus = Literal[
    "idle", "connecting", "live", "reconnecting", "rate_limited", "error", "stopped", "replay"
]

#: How far past a bar's close we tolerate before calling the feed stale, as a multiple of the
#: bar length, plus a floor for fast timeframes.  **[OUR CHOICE]** — presentation only, it
#: gates a banner in the UI and never touches an analysis result.
STALE_BAR_MULTIPLE = 2.0
STALE_FLOOR_SECONDS = 90.0


def bar_close_ms(open_time_ms: int, tf: str) -> int:
    """The epoch-ms instant at which the bar opening at ``open_time_ms`` closes."""
    return int(open_time_ms) + Timeframe.parse(tf).minutes * 60_000


# =========================================================================== connection state


@dataclass(slots=True)
class ConnectionState:
    """What the UI needs to say, plainly, about whether the numbers are live.

    Every field is written by :mod:`tbot.dashboard.feed` and read by the HTTP layer.  There is
    deliberately no "assume it is fine" default: a store with no data reports ``idle`` and the
    frontend renders that as *not live*, never as a stale price dressed up as a current one.
    """

    source: str = "binance"
    status: ConnectionStatus = "idle"
    detail: str = ""
    since: float = field(default_factory=time.time)
    last_message_at: float | None = None
    last_error: str = ""
    attempts: int = 0
    next_retry_at: float | None = None
    #: set when the venue told us to slow down; the UI shows the countdown
    retry_after: float | None = None
    messages: int = 0

    def set(self, status: ConnectionStatus, detail: str = "") -> None:
        if status != self.status:
            self.since = time.time()
        self.status = status
        self.detail = detail

    def note_message(self) -> None:
        self.last_message_at = time.time()
        self.messages += 1

    @property
    def is_live(self) -> bool:
        return self.status in ("live", "replay")

    def seconds_since_message(self, now: float | None = None) -> float | None:
        if self.last_message_at is None:
            return None
        return max(0.0, (now if now is not None else time.time()) - self.last_message_at)

    def to_dict(self, now: float | None = None) -> dict[str, object]:
        now = time.time() if now is None else now
        return {
            "source": self.source,
            "status": self.status,
            "detail": self.detail,
            "live": self.is_live,
            "since": self.since,
            "uptime_seconds": max(0.0, now - self.since),
            "last_message_at": self.last_message_at,
            "seconds_since_message": self.seconds_since_message(now),
            "last_error": self.last_error,
            "attempts": self.attempts,
            "next_retry_at": self.next_retry_at,
            "retry_after": self.retry_after,
            "messages": self.messages,
        }


# =========================================================================== candle store


class CandleStore:
    """Closed bars for one ``(symbol, timeframe)``, plus the one bar still forming.

    Thread-safe: the feed writes from the event loop thread, the analysis service reads from a
    worker thread.  The lock is held only for list manipulation, never across a pipeline run.
    """

    __slots__ = ("symbol", "tf", "_closed", "_by_time", "forming", "_lock", "max_bars",
                 "last_gap_at", "backfilled_at")

    def __init__(self, symbol: str, tf: str, *, max_bars: int = 1500) -> None:
        self.symbol = symbol.upper()
        self.tf = tf
        self.max_bars = int(max_bars)
        self._closed: list[Kline] = []
        self._by_time: dict[int, int] = {}
        self.forming: Kline | None = None
        self._lock = threading.RLock()
        self.last_gap_at: float | None = None
        self.backfilled_at: float | None = None

    # ---------------------------------------------------------------- writes

    def backfill(self, klines: Sequence[Kline], *, now_ms: int | None = None) -> int:
        """Replace the closed history from a REST response.

        REST endpoints hand back the still-forming bar as the final row without saying so, so
        closedness is decided here from the wall clock: a bar is closed when its close instant
        has passed.  Any trailing bar that has not closed becomes :attr:`forming`, not history.
        """
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        closed: list[Kline] = []
        forming: Kline | None = None
        for k in sorted(klines, key=lambda x: x.open_time_ms):
            if bar_close_ms(k.open_time_ms, self.tf) <= now_ms:
                closed.append(k.replace_closed(True))
            else:
                forming = k.replace_closed(False)
        with self._lock:
            self._closed = closed[-self.max_bars:]
            self._reindex()
            if forming is not None:
                self.forming = forming
            self.backfilled_at = time.time()
            return len(self._closed)

    def apply(self, kline: Kline) -> bool:
        """Apply one live update.  Returns ``True`` iff a **new closed bar** appeared.

        A ``True`` return is the only event that may trigger a pipeline recompute.  Updates to
        the forming bar return ``False`` however many arrive per second.
        """
        with self._lock:
            if not kline.is_closed:
                last = self._closed[-1].open_time_ms if self._closed else None
                if last is not None and kline.open_time_ms <= last:
                    # a late tick for a bar we already closed: never resurrect it (P1 no repaint)
                    return False
                self.forming = kline
                return False

            existing = self._by_time.get(kline.open_time_ms)
            if existing is not None:
                self._closed[existing] = kline
                if self.forming is not None and self.forming.open_time_ms == kline.open_time_ms:
                    self.forming = None
                return False

            last = self._closed[-1].open_time_ms if self._closed else None
            if last is not None and kline.open_time_ms < last:
                return False  # out-of-order history; the backfill is authoritative
            if last is not None:
                step = Timeframe.parse(self.tf).minutes * 60_000
                if kline.open_time_ms > last + step:
                    # we missed at least one bar — the caller should re-backfill
                    self.last_gap_at = time.time()
            self._closed.append(kline)
            if len(self._closed) > self.max_bars:
                self._closed = self._closed[-self.max_bars:]
            self._reindex()
            if self.forming is not None and self.forming.open_time_ms <= kline.open_time_ms:
                self.forming = None
            return True

    def _reindex(self) -> None:
        self._by_time = {k.open_time_ms: i for i, k in enumerate(self._closed)}

    def clear_gap(self) -> None:
        with self._lock:
            self.last_gap_at = None

    # ---------------------------------------------------------------- reads

    def __len__(self) -> int:
        with self._lock:
            return len(self._closed)

    @property
    def closed(self) -> tuple[Kline, ...]:
        with self._lock:
            return tuple(self._closed)

    @property
    def last_closed_open_ms(self) -> int | None:
        with self._lock:
            return self._closed[-1].open_time_ms if self._closed else None

    @property
    def last_price(self) -> float | None:
        with self._lock:
            if self.forming is not None:
                return self.forming.close
            return self._closed[-1].close if self._closed else None

    def series(self, *, venue_kind: str = "spot", max_bars: int | None = None) -> Series | None:
        """The engine's view: **closed bars only**.

        This is the single conversion point from dashboard data to engine data, and the forming
        bar is not in scope here — it lives in :attr:`forming` and is never read by this method.
        Returns ``None`` when there is no history yet.
        """
        rows = self.closed
        if max_bars:
            rows = rows[-int(max_bars):]
        if not rows:
            return None
        index = pd.to_datetime([k.open_time_ms for k in rows], unit="ms", utc=True)
        return Series.from_arrays(
            timestamps=index,
            open_=np.array([k.open for k in rows], dtype="float64"),
            high=np.array([k.high for k in rows], dtype="float64"),
            low=np.array([k.low for k in rows], dtype="float64"),
            close=np.array([k.close for k in rows], dtype="float64"),
            volume=np.array([k.volume for k in rows], dtype="float64"),
            quote_volume=np.array([k.quote_volume for k in rows], dtype="float64"),
            tf=self.tf,
            symbol=self.symbol,
            venue_kind=venue_kind,  # type: ignore[arg-type]
        )

    def candles_json(self, limit: int = 600) -> list[dict[str, float]]:
        """Closed bars for Lightweight Charts (``time`` in **seconds**)."""
        return [
            {"time": k.open_time_ms // 1000, "open": k.open, "high": k.high,
             "low": k.low, "close": k.close, "volume": k.volume}
            for k in self.closed[-int(limit):]
        ]

    def forming_json(self) -> dict[str, float] | None:
        k = self.forming
        if k is None:
            return None
        return {"time": k.open_time_ms // 1000, "open": k.open, "high": k.high,
                "low": k.low, "close": k.close, "volume": k.volume, "forming": True}

    def is_stale(self, now: float | None = None) -> bool:
        """True when the newest bar is older than the feed should have allowed."""
        last = self.last_closed_open_ms
        if last is None:
            return True
        now = time.time() if now is None else now
        minutes = Timeframe.parse(self.tf).minutes
        allowance = max(STALE_FLOOR_SECONDS, minutes * 60.0 * STALE_BAR_MULTIPLE)
        return (now * 1000 - bar_close_ms(last, self.tf)) / 1000.0 > allowance


# =========================================================================== the whole book


class MarketData:
    """Every ``(symbol, timeframe)`` store the dashboard is watching, plus feed health."""

    def __init__(self, source: str = "binance", *, max_bars: int = 1500) -> None:
        self._stores: dict[tuple[str, str], CandleStore] = {}
        self._lock = threading.RLock()
        self.max_bars = int(max_bars)
        self.connection = ConnectionState(source=source)

    def key(self, symbol: str, tf: str) -> tuple[str, str]:
        return (symbol.upper(), tf)

    def store(self, symbol: str, tf: str) -> CandleStore:
        k = self.key(symbol, tf)
        with self._lock:
            store = self._stores.get(k)
            if store is None:
                store = CandleStore(k[0], tf, max_bars=self.max_bars)
                self._stores[k] = store
            return store

    def get(self, symbol: str, tf: str) -> CandleStore | None:
        with self._lock:
            return self._stores.get(self.key(symbol, tf))

    def keys(self) -> list[tuple[str, str]]:
        with self._lock:
            return sorted(self._stores)

    def prune(self, wanted: Iterable[tuple[str, str]]) -> None:
        """Drop stores no longer in the watchlist so memory follows the settings."""
        keep = {self.key(s, t) for s, t in wanted}
        with self._lock:
            for k in list(self._stores):
                if k not in keep:
                    del self._stores[k]
