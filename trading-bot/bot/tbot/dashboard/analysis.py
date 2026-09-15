"""Cached, throttled, off-the-event-loop pipeline runner.

Three properties this module has to have, because a full pipeline pass over ~900 bars costs
seconds, not milliseconds:

**It never blocks the event loop.**  Every ``tbot.pipeline.analyse_bar`` call runs in a
``ThreadPoolExecutor``.  The pipeline is pure (INTERFACES.md §9.1), holds no module-level
mutable state and mutates neither its ``Series`` nor its ``Config``, so running several passes
concurrently in threads is safe by construction.

**It recomputes only when the answer can have changed.**  The cache key is
``(symbol, timeframe, last closed bar, settings revision, source, venue)``.  A price tick on the
forming bar does not move any component of that key, so a burst of ticks costs zero pipeline
passes.  A new closed bar or a settings edit moves it, and exactly one pass follows.

**A burst never queues.**  Requests coalesce: while a key is computing, further requests set a
single dirty flag rather than stacking tasks, and a minimum interval per key spaces out
back-to-back runs.  Ten ticks in a second produce one recompute, not ten.

And the property that matters most: :meth:`AnalysisService.compute` builds its ``Series`` from
:meth:`CandleStore.series`, which reads closed bars only.  The forming bar reaches this module
only as ``last_price``, which is used for display distances and is never part of the analysed
series.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from tbot import pipeline
from tbot.config import Config

from .serialize import serialize_run, watchlist_row
from .settings import SettingsStore
from .store import MarketData

__all__ = ["AnalysisKey", "AnalysisResult", "AnalysisService", "MIN_BARS"]

log = logging.getLogger("tbot.dashboard.analysis")

#: Below this the detectors have nothing to stand on and the run is noise, so we say so
#: rather than drawing an empty chart that looks like "no setups". **[OUR CHOICE]**
MIN_BARS = 120


@dataclass(frozen=True, slots=True)
class AnalysisKey:
    """Everything that can change an answer.  Nothing that cannot."""

    symbol: str
    timeframe: str
    last_bar_ms: int
    revision: int
    source: str
    venue_kind: str

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "timeframe": self.timeframe,
                "last_bar_ms": self.last_bar_ms, "settings_revision": self.revision,
                "source": self.source, "venue_kind": self.venue_kind}


@dataclass(slots=True)
class AnalysisResult:
    key: AnalysisKey
    payload: dict[str, Any] | None
    computed_at: float
    duration: float
    error: str | None = None
    traceback: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and self.payload is not None

    def envelope(self, *, stale: bool, last_price: float | None) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "key": self.key.to_dict(),
            "computed_at": self.computed_at,
            "age_seconds": max(0.0, time.time() - self.computed_at),
            "duration_seconds": round(self.duration, 3),
            "stale": bool(stale),
            "last_price": last_price,
            "analysis": self.payload,
        }


class AnalysisService:
    """Owns the cache, the throttle and the worker pool."""

    def __init__(
        self,
        market: MarketData,
        settings: SettingsStore,
        *,
        max_workers: int = 2,
        min_interval: float = 2.0,
        cache_size: int = 96,
        on_update: Callable[[str, str, AnalysisResult], Awaitable[None] | None] | None = None,
        executor: Any | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        from concurrent.futures import ThreadPoolExecutor

        self.market = market
        self.settings = settings
        self.min_interval = float(min_interval)
        self.cache_size = int(cache_size)
        self.on_update = on_update
        self._clock = clock
        self._executor = executor if executor is not None else ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)), thread_name_prefix="tbot-pipeline")
        self._owns_executor = executor is None

        self._cache: "OrderedDict[AnalysisKey, AnalysisResult]" = OrderedDict()
        self._latest: dict[tuple[str, str], AnalysisResult] = {}
        self._slots: dict[tuple[str, str], _Slot] = {}
        self._lock = threading.RLock()
        self.stats: dict[str, int] = {
            "computed": 0, "cache_hits": 0, "coalesced": 0, "throttled": 0,
            "errors": 0, "skipped_no_data": 0,
        }

    # ------------------------------------------------------------------ keys and cache

    def key_for(self, symbol: str, tf: str) -> AnalysisKey | None:
        store = self.market.get(symbol, tf)
        if store is None:
            return None
        last = store.last_closed_open_ms
        if last is None:
            return None
        s = self.settings.settings
        return AnalysisKey(symbol.upper(), tf, int(last), s.revision, s.source, s.venue_kind)

    def cached(self, symbol: str, tf: str) -> AnalysisResult | None:
        """The result for the *current* key, or ``None`` if it would need recomputing."""
        key = self.key_for(symbol, tf)
        if key is None:
            return None
        with self._lock:
            return self._cache.get(key)

    def latest(self, symbol: str, tf: str) -> AnalysisResult | None:
        """The most recent result for this pair, current key or not."""
        with self._lock:
            return self._latest.get((symbol.upper(), tf))

    def is_current(self, result: AnalysisResult | None, symbol: str, tf: str) -> bool:
        return result is not None and result.key == self.key_for(symbol, tf)

    def _store_result(self, key: AnalysisKey, result: AnalysisResult) -> None:
        with self._lock:
            self._cache[key] = result
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
            self._latest[(key.symbol, key.timeframe)] = result

    def invalidate(self) -> None:
        """Drop everything.  Called when settings change; the revision alone would do it, but
        holding results that can never be served again just wastes memory."""
        with self._lock:
            self._cache.clear()

    # ------------------------------------------------------------------ the compute itself

    def compute(self, symbol: str, tf: str, key: AnalysisKey, config: Config) -> AnalysisResult:
        """Synchronous.  Runs in a worker thread; never call this from the event loop."""
        started = self._clock()
        store = self.market.get(symbol, tf)
        if store is None:
            return AnalysisResult(key, None, started, 0.0, error="no data for this pair yet")
        settings = self.settings.settings
        # ---- the no-lookahead boundary: closed bars only, the forming bar is not in scope
        series = store.series(venue_kind=settings.venue_kind, max_bars=settings.history_bars)
        if series is None or len(series) < MIN_BARS:
            have = 0 if series is None else len(series)
            return AnalysisResult(
                key, None, started, self._clock() - started,
                error=f"only {have} closed bars; the engine needs at least {MIN_BARS}")
        try:
            run = pipeline.analyse_bar(series, config)
            payload = serialize_run(run, last_price=store.last_price)
        except Exception as exc:  # the UI must show a failed pass, not a blank chart
            log.exception("pipeline failed for %s %s", symbol, tf)
            return AnalysisResult(key, None, started, self._clock() - started,
                                  error=f"{type(exc).__name__}: {exc}",
                                  traceback=traceback.format_exc(limit=8))
        return AnalysisResult(key, payload, self._clock(), self._clock() - started)

    # ------------------------------------------------------------------ scheduling

    def _slot(self, symbol: str, tf: str) -> "_Slot":
        k = (symbol.upper(), tf)
        with self._lock:
            slot = self._slots.get(k)
            if slot is None:
                slot = _Slot()
                self._slots[k] = slot
            return slot

    async def request(self, symbol: str, tf: str, *, force: bool = False,
                      wait: bool = False) -> AnalysisResult | None:
        """Ensure an up-to-date result exists for ``(symbol, tf)``.

        Returns whatever is available *now* — the fresh result if it was already cached or if
        ``wait`` is set, otherwise the previous one while the recompute runs in the background.
        Never blocks the event loop and never queues more than one pending run per pair.
        """
        symbol = symbol.upper()
        key = self.key_for(symbol, tf)
        if key is None:
            self.stats["skipped_no_data"] += 1
            return None

        if not force:
            with self._lock:
                hit = self._cache.get(key)
            if hit is not None:
                self.stats["cache_hits"] += 1
                return hit

        slot = self._slot(symbol, tf)
        with self._lock:
            if slot.running:
                slot.dirty = True
                self.stats["coalesced"] += 1
                return self._latest.get((symbol, tf))
            elapsed = self._clock() - slot.last_started
            if elapsed < self.min_interval and not wait:
                if not slot.scheduled:
                    slot.scheduled = True
                    delay = self.min_interval - elapsed
                    asyncio.get_running_loop().create_task(
                        self._delayed(symbol, tf, delay))
                self.stats["throttled"] += 1
                return self._latest.get((symbol, tf))
            slot.running = True
            slot.last_started = self._clock()

        return await self._run(symbol, tf, key)

    async def _delayed(self, symbol: str, tf: str, delay: float) -> None:
        try:
            await asyncio.sleep(max(0.0, delay))
        finally:
            self._slot(symbol, tf).scheduled = False
        await self.request(symbol, tf)

    async def _run(self, symbol: str, tf: str, key: AnalysisKey) -> AnalysisResult:
        config = self.settings.config
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                self._executor, self.compute, symbol, tf, key, config)
        except Exception as exc:  # pragma: no cover - executor-level failure
            result = AnalysisResult(key, None, self._clock(), 0.0,
                                    error=f"{type(exc).__name__}: {exc}")
        finally:
            slot = self._slot(symbol, tf)
            slot.running = False

        self.stats["computed"] += 1
        if not result.ok:
            self.stats["errors"] += 1
        self._store_result(key, result)

        if self.on_update is not None:
            try:
                maybe = self.on_update(symbol, tf, result)
                if asyncio.iscoroutine(maybe):
                    await maybe
            except Exception:  # pragma: no cover - a broadcast failure must not kill analysis
                log.exception("on_update callback failed")

        slot = self._slot(symbol, tf)
        if slot.dirty:
            slot.dirty = False
            # one follow-up pass, scheduled — never a recursive burst
            asyncio.get_running_loop().create_task(self.request(symbol, tf))
        return result

    # ------------------------------------------------------------------ views

    def watchlist(self) -> list[dict[str, Any]]:
        """One row per (pair, timeframe) in settings order, whatever state each is in."""
        settings = self.settings.settings
        rows: list[dict[str, Any]] = []
        for symbol, tf in settings.subscriptions():
            store = self.market.get(symbol, tf)
            result = self.latest(symbol, tf)
            last_price = store.last_price if store is not None else None
            if store is None:
                status, error = "waiting", "no data yet"
            elif result is None:
                status, error = "analysing", ""
            elif not result.ok:
                status, error = "error", result.error or "unknown error"
            elif not self.is_current(result, symbol, tf):
                status, error = "recomputing", ""
            else:
                status, error = "ready", ""
            row = watchlist_row(symbol, tf, result.payload if result else None,
                                last_price=last_price, status=status, error=error)
            row["bars"] = len(store) if store is not None else 0
            row["data_stale"] = bool(store.is_stale()) if store is not None else True
            rows.append(row)
        return rows

    def shutdown(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)


@dataclass(slots=True)
class _Slot:
    """Per-pair scheduling state.  ``dirty`` is the coalescing flag; there is exactly one."""

    running: bool = False
    dirty: bool = False
    scheduled: bool = False
    last_started: float = 0.0
