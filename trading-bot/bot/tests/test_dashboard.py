"""Tests for tbot.dashboard — API surface, throttling/caching, and the no-lookahead boundary.

No network, anywhere.  Every exchange interaction is either a pure parse of a recorded payload
shape or a fake transport; the live candles are the repository's own offline replay feed.

The test that matters most is :class:`TestNoLookahead`: it proves that the still-forming bar the
dashboard displays is not, and cannot be, part of what the engine analyses (SPEC.md §12.1).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tbot.dashboard import exchanges as X
from tbot.dashboard.analysis import AnalysisKey, AnalysisResult, AnalysisService
from tbot.dashboard.exchanges import BinanceAdapter, BybitAdapter, Kline, RateLimited
from tbot.dashboard.feed import MarketFeed, ReplayFeed, backoff_delay
from tbot.dashboard.gates import GATES, describe_gate, group_rejections
from tbot.dashboard.serialize import jsonable, watchlist_row
from tbot.dashboard.server import create_app
from tbot.dashboard.settings import DashboardSettings, SettingsStore
from tbot.dashboard.store import CandleStore, MarketData, bar_close_ms

HOUR_MS = 3_600_000
#: A bar-aligned instant in the past, fixed for the whole test session, so seeded history
#: is always history and never accidentally in the future.
SEED_NOW_MS = int(time.time()) // 14_400 * 14_400 * 1000


def k(open_ms: int, close: float = 100.0, *, closed: bool = True, high: float | None = None,
      low: float | None = None) -> Kline:
    return Kline(open_ms, close, high if high is not None else close + 1.0,
                 low if low is not None else close - 1.0, close, 10.0, 1000.0, closed)


# =========================================================================== exchange formats


class TestBinanceAdapter:
    def test_rest_request_uses_the_venue_interval_code(self) -> None:
        url, params = BinanceAdapter().rest_request("btcusdt", "4H", 900)
        assert url.endswith("/api/v3/klines")
        assert params == {"symbol": "BTCUSDT", "interval": "4h", "limit": 900}

    def test_rest_limit_is_capped_at_one_page(self) -> None:
        _, params = BinanceAdapter().rest_request("BTCUSDT", "1H", 99_999)
        assert params["limit"] == 1000

    def test_unknown_timeframe_is_an_error_not_a_guess(self) -> None:
        with pytest.raises(ValueError, match="no kline interval"):
            BinanceAdapter().rest_request("BTCUSDT", "2D", 100)

    def test_parse_klines_reads_the_documented_offsets(self) -> None:
        payload = [[1700000000000, "1.5", "2.5", "1.0", "2.0", "10.0",
                    1700003599999, "20.0", 42, "5", "10", "0"]]
        (bar,) = BinanceAdapter().parse_klines(payload)
        assert (bar.open_time_ms, bar.open, bar.high, bar.low, bar.close) == (
            1700000000000, 1.5, 2.5, 1.0, 2.0)
        assert bar.volume == 10.0 and bar.quote_volume == 20.0

    def test_parse_klines_rejects_a_malformed_row(self) -> None:
        with pytest.raises(ValueError):
            BinanceAdapter().parse_klines([[1, 2, 3]])

    def test_stream_url_lists_every_subscription(self) -> None:
        url = BinanceAdapter().stream_url([("BTCUSDT", "4H"), ("ETHUSDT", "1H")])
        assert url.endswith("?streams=btcusdt@kline_4h/ethusdt@kline_1h")

    def test_parse_message_carries_the_venue_closed_flag(self) -> None:
        frame = json.dumps({"stream": "btcusdt@kline_4h", "data": {
            "e": "kline", "s": "BTCUSDT",
            "k": {"t": 1700000000000, "i": "4h", "o": "1", "h": "3", "l": "0.5",
                  "c": "2", "v": "7", "q": "14", "x": False}}})
        symbol, tf, bar = BinanceAdapter().parse_message(frame)
        assert (symbol, tf) == ("BTCUSDT", "4H")
        assert bar.is_closed is False and bar.close == 2.0

        closed = json.loads(frame)
        closed["data"]["k"]["x"] = True
        assert BinanceAdapter().parse_message(json.dumps(closed))[2].is_closed is True

    @pytest.mark.parametrize("frame", [
        "not json", "[]", json.dumps({"result": None, "id": 1}),
        json.dumps({"data": {"e": "trade"}}),
        json.dumps({"data": {"e": "kline", "k": {"i": "9h"}}}),
    ])
    def test_non_candle_frames_are_ignored_not_fatal(self, frame: str) -> None:
        assert BinanceAdapter().parse_message(frame) is None

    def test_rate_limit_is_distinguished_from_a_plain_error(self) -> None:
        adapter = BinanceAdapter()
        err = adapter.rest_error(429, {"Retry-After": "17"}, {})
        assert isinstance(err, RateLimited) and err.retry_after == 17.0
        assert isinstance(adapter.rest_error(418, {}, {}), RateLimited)
        assert isinstance(adapter.rest_error(500, {}, "boom"), RuntimeError)
        assert adapter.rest_error(200, {}, [[1, 2, 3]]) is None


class TestBybitAdapter:
    def test_rest_request_includes_the_category(self) -> None:
        url, params = BybitAdapter("linear").rest_request("BTCUSDT", "4H", 500)
        assert url.endswith("/v5/market/kline")
        assert params == {"category": "linear", "symbol": "BTCUSDT",
                          "interval": "240", "limit": 500}

    def test_parse_klines_reverses_bybits_newest_first_ordering(self) -> None:
        payload = {"retCode": 0, "result": {"list": [
            ["1700003600000", "2", "3", "1", "2.5", "5", "12"],
            ["1700000000000", "1", "2", "0.5", "1.5", "4", "6"],
        ]}}
        bars = BybitAdapter().parse_klines(payload)
        assert [b.open_time_ms for b in bars] == [1700000000000, 1700003600000]

    def test_subscribe_frames_are_batched(self) -> None:
        subs = [(f"SYM{i}USDT", "1H") for i in range(23)]
        frames = BybitAdapter().subscribe_messages(subs)
        assert len(frames) == 3
        assert json.loads(frames[0])["op"] == "subscribe"
        assert json.loads(frames[0])["args"][0] == "kline.60.SYM0USDT"

    def test_parse_message_reads_confirm_as_closedness(self) -> None:
        frame = json.dumps({"topic": "kline.240.BTCUSDT", "data": [
            {"start": 1700000000000, "open": "1", "high": "2", "low": "0.5",
             "close": "1.5", "volume": "3", "turnover": "4", "confirm": True}]})
        symbol, tf, bar = BybitAdapter().parse_message(frame)
        assert (symbol, tf, bar.is_closed) == ("BTCUSDT", "4H", True)

    def test_retcode_rate_limit_is_recognised(self) -> None:
        assert isinstance(BybitAdapter().rest_error(200, {}, {"retCode": 10006}), RateLimited)
        assert isinstance(BybitAdapter().rest_error(200, {}, {"retCode": 10001,
                                                              "retMsg": "bad"}), RuntimeError)
        assert BybitAdapter().rest_error(200, {}, {"retCode": 0, "result": {}}) is None


def test_adapter_for_rejects_an_unknown_source() -> None:
    with pytest.raises(ValueError, match="unknown market-data source"):
        X.adapter_for("kraken")


def test_supported_timeframes_never_promises_a_bar_length_the_venue_lacks() -> None:
    assert "3D" not in X.supported_timeframes("bybit")
    assert "2D" not in X.supported_timeframes("binance")
    assert set(X.supported_timeframes("replay")) == set(X.DASHBOARD_TIMEFRAMES)


# =========================================================================== candle store


class TestCandleStore:
    def test_backfill_splits_the_still_forming_trailing_bar_off_the_history(self) -> None:
        store = CandleStore("BTCUSDT", "1H")
        bars = [k(i * HOUR_MS, 100.0 + i) for i in range(1, 6)]
        # "now" is halfway through the bar that opened at 5h
        n = store.backfill(bars, now_ms=5 * HOUR_MS + HOUR_MS // 2)
        assert n == 4
        assert store.last_closed_open_ms == 4 * HOUR_MS
        assert store.forming is not None
        assert store.forming.open_time_ms == 5 * HOUR_MS
        assert store.forming.is_closed is False

    def test_a_forming_update_is_never_a_new_bar(self) -> None:
        store = CandleStore("BTCUSDT", "1H")
        store.backfill([k(i * HOUR_MS) for i in range(1, 4)], now_ms=4 * HOUR_MS)
        for _ in range(25):
            assert store.apply(k(4 * HOUR_MS, 555.0, closed=False)) is False
        assert len(store) == 3
        assert store.forming.close == 555.0

    def test_a_closed_update_is_a_new_bar_exactly_once(self) -> None:
        store = CandleStore("BTCUSDT", "1H")
        store.backfill([k(i * HOUR_MS) for i in range(1, 4)], now_ms=4 * HOUR_MS)
        store.apply(k(4 * HOUR_MS, 101.0, closed=False))
        assert store.apply(k(4 * HOUR_MS, 102.0, closed=True)) is True
        assert store.apply(k(4 * HOUR_MS, 102.5, closed=True)) is False   # a correction
        assert len(store) == 4
        assert store.forming is None

    def test_a_late_tick_can_never_resurrect_a_closed_bar(self) -> None:
        store = CandleStore("BTCUSDT", "1H")
        store.backfill([k(i * HOUR_MS) for i in range(1, 4)], now_ms=4 * HOUR_MS)
        assert store.apply(k(3 * HOUR_MS, 9_999.0, closed=False)) is False
        assert store.forming is None
        assert store.series().close[-1] == pytest.approx(100.0)

    def test_a_skipped_bar_is_recorded_as_a_gap(self) -> None:
        store = CandleStore("BTCUSDT", "1H")
        store.backfill([k(i * HOUR_MS) for i in range(1, 4)], now_ms=4 * HOUR_MS)
        assert store.last_gap_at is None
        store.apply(k(6 * HOUR_MS, closed=True))
        assert store.last_gap_at is not None
        store.clear_gap()
        assert store.last_gap_at is None

    def test_max_bars_trims_the_oldest(self) -> None:
        store = CandleStore("BTCUSDT", "1H", max_bars=10)
        store.backfill([k(i * HOUR_MS) for i in range(1, 40)], now_ms=40 * HOUR_MS)
        assert len(store) == 10
        assert store.last_closed_open_ms == 39 * HOUR_MS

    def test_series_matches_the_closed_bars_and_nothing_else(self) -> None:
        store = CandleStore("BTCUSDT", "1H")
        store.backfill([k(i * HOUR_MS, 100.0 + i) for i in range(1, 21)], now_ms=21 * HOUR_MS)
        series = store.series()
        assert len(series) == 20
        assert series.symbol == "BTCUSDT" and series.tf.value == "1H"
        assert series.close[-1] == pytest.approx(120.0)

    def test_staleness_is_measured_against_the_bar_length(self) -> None:
        now_ms = 100 * HOUR_MS
        store = CandleStore("BTCUSDT", "1H")
        store.backfill([k(i * HOUR_MS) for i in range(96, 100)], now_ms=now_ms)
        assert store.is_stale(now=now_ms / 1000 + 60) is False
        assert store.is_stale(now=now_ms / 1000 + 6 * 3600) is True

    def test_bar_close_ms_uses_the_timeframe_length(self) -> None:
        assert bar_close_ms(0, "4H") == 4 * HOUR_MS
        assert bar_close_ms(HOUR_MS, "15m") == HOUR_MS + 15 * 60_000


# =========================================================================== no lookahead


@pytest.fixture(scope="module")
def seeded() -> tuple[MarketData, SettingsStore]:
    """A market book filled from the offline replay feed.  No network."""
    settings = SettingsStore(DashboardSettings(
        pairs=("BTCUSDT",), timeframes=("4H",), source="replay", history_bars=400))
    market = MarketData(source="replay")
    feed = ReplayFeed(market, settings)
    feed.seed("BTCUSDT", "4H", 400, now_ms=SEED_NOW_MS)
    return market, settings


class TestNoLookahead:
    """The forming bar is displayed, never analysed."""

    def test_the_forming_bar_is_absent_from_the_engines_series(self, seeded) -> None:
        market, _ = seeded
        store = market.get("BTCUSDT", "4H")
        before = store.series()
        last_closed_open = store.last_closed_open_ms

        # a forming bar that would visibly wreck any detector if it leaked in
        store.apply(Kline(last_closed_open + 4 * HOUR_MS, 1.0, 1e9, 1e-9, 5.0,
                          1.0, 1.0, False))
        assert store.forming is not None
        after = store.series()

        assert len(after) == len(before)
        assert after.timestamps[-1] == before.timestamps[-1]
        assert after.high.max() == pytest.approx(before.high.max())
        assert after.low.min() == pytest.approx(before.low.min())
        assert int(after.timestamps[-1].timestamp() * 1000) == last_closed_open

    def test_every_bar_in_the_series_has_already_closed(self, seeded) -> None:
        market, _ = seeded
        store = market.get("BTCUSDT", "4H")
        now_ms = store.last_closed_open_ms + 4 * HOUR_MS + 1
        for bar in store.closed:
            assert bar.is_closed is True
            assert bar_close_ms(bar.open_time_ms, "4H") <= now_ms

    def test_the_analysis_is_identical_with_and_without_a_forming_bar(self, seeded) -> None:
        """The strong form: run the real pipeline both ways and compare the output."""
        market, settings = seeded
        store = market.get("BTCUSDT", "4H")
        store.forming = None
        service = AnalysisService(market, settings, min_interval=0.0)
        key = service.key_for("BTCUSDT", "4H")
        assert key is not None

        clean = service.compute("BTCUSDT", "4H", key, settings.config)
        assert clean.ok, clean.error

        # now show a wildly different forming bar and recompute
        store.apply(Kline(store.last_closed_open_ms + 4 * HOUR_MS,
                          1.0, 1e6, 1e-6, 7.0, 1.0, 1.0, False))
        polluted = service.compute("BTCUSDT", "4H", key, settings.config)
        assert polluted.ok, polluted.error

        # the cache key did not move either: a forming bar is not a new bar
        assert service.key_for("BTCUSDT", "4H") == key

        def engine_only(payload: dict) -> dict:
            """Strip the two display-only fields that carry the live price by design."""
            plans = [{key: value for key, value in plan.items()
                      if key not in ("last_price", "distance_to_entry_pct")}
                     for plan in payload["plans"]]
            return dict(payload, plans=plans)

        clean_e, polluted_e = engine_only(clean.payload), engine_only(polluted.payload)
        for section in ("overlays", "plans", "setups", "rejections", "trend",
                        "structure_trend", "clusters", "detections", "regime"):
            assert polluted_e[section] == clean_e[section], section
        assert polluted.payload["meta"]["bar_time"] == clean.payload["meta"]["bar_time"]
        assert polluted.payload["meta"]["last_close"] == clean.payload["meta"]["last_close"]
        # ...and the only thing that did change is the display-only last price
        assert polluted.payload["meta"]["last_price"] == 7.0
        service.shutdown()
        store.forming = None


# =========================================================================== caching/throttle


class _CountingService(AnalysisService):
    """An AnalysisService whose pipeline pass is a stub, so the scheduling is what is tested."""

    def __init__(self, *args: Any, block: threading.Event | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[AnalysisKey] = []
        self.block = block

    def compute(self, symbol: str, tf: str, key: AnalysisKey, config: Any) -> AnalysisResult:
        self.calls.append(key)
        if self.block is not None:
            self.block.wait(timeout=5.0)
        return AnalysisResult(key, {"stub": True, "plans": [], "setups": [],
                                    "rejections": [], "meta": {}}, time.time(), 0.0)


class _Clock:
    def __init__(self) -> None:
        self.t = 1_000.0

    def __call__(self) -> float:
        return self.t


def _market_with(bars: int = 3) -> tuple[MarketData, SettingsStore]:
    settings = SettingsStore(DashboardSettings(pairs=("BTCUSDT",), timeframes=("1H",),
                                               source="replay"))
    market = MarketData(source="replay")
    store = market.store("BTCUSDT", "1H")
    store.backfill([k(i * HOUR_MS) for i in range(1, bars + 1)],
                   now_ms=(bars + 1) * HOUR_MS)
    return market, settings


async def _drain() -> None:
    """Let scheduled follow-up tasks run, then cancel anything still pending."""
    for _ in range(6):
        await asyncio.sleep(0)
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


class TestCaching:
    def test_the_key_is_the_bar_settings_source_and_venue(self) -> None:
        market, settings = _market_with()
        svc = AnalysisService(market, settings)
        first = svc.key_for("BTCUSDT", "1H")
        assert first is not None
        assert first.last_bar_ms == 3 * HOUR_MS

        market.store("BTCUSDT", "1H").apply(k(4 * HOUR_MS, closed=False))
        assert svc.key_for("BTCUSDT", "1H") == first, "a tick must not move the cache key"

        market.store("BTCUSDT", "1H").apply(k(4 * HOUR_MS, closed=True))
        assert svc.key_for("BTCUSDT", "1H").last_bar_ms == 4 * HOUR_MS

        settings.apply({"overrides": {"min_rr": 2.5}})
        assert svc.key_for("BTCUSDT", "1H").revision == 1
        svc.shutdown()

    def test_no_key_without_data(self) -> None:
        market = MarketData()
        svc = AnalysisService(market, SettingsStore())
        assert svc.key_for("BTCUSDT", "1H") is None
        svc.shutdown()

    def test_a_tick_burst_costs_no_pipeline_passes(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            svc = _CountingService(market, settings, min_interval=0.0)
            store = market.store("BTCUSDT", "1H")
            assert await svc.request("BTCUSDT", "1H") is not None
            assert len(svc.calls) == 1

            for i in range(40):
                store.apply(k(4 * HOUR_MS, 100.0 + i, closed=False))
                await svc.request("BTCUSDT", "1H")
            assert len(svc.calls) == 1, "ticks must never trigger a recompute"
            assert svc.stats["cache_hits"] == 40
            svc.shutdown()

        asyncio.run(scenario())

    def test_a_new_closed_bar_costs_exactly_one_pass(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            svc = _CountingService(market, settings, min_interval=0.0)
            store = market.store("BTCUSDT", "1H")
            await svc.request("BTCUSDT", "1H")
            store.apply(k(4 * HOUR_MS, closed=True))
            await svc.request("BTCUSDT", "1H")
            await svc.request("BTCUSDT", "1H")
            assert len(svc.calls) == 2
            assert [c.last_bar_ms for c in svc.calls] == [3 * HOUR_MS, 4 * HOUR_MS]
            svc.shutdown()

        asyncio.run(scenario())

    def test_a_settings_change_recomputes_without_a_restart(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            svc = _CountingService(market, settings, min_interval=0.0)
            await svc.request("BTCUSDT", "1H")
            settings.apply({"overrides": {"min_rr": 3.0}})
            svc.invalidate()
            await svc.request("BTCUSDT", "1H")
            assert len(svc.calls) == 2
            assert svc.calls[0].revision == 0 and svc.calls[1].revision == 1
            svc.shutdown()

        asyncio.run(scenario())

    def test_the_cache_is_bounded(self) -> None:
        market, settings = _market_with()
        svc = AnalysisService(market, settings, cache_size=3)
        for i in range(10):
            key = AnalysisKey("BTCUSDT", "1H", i, 0, "replay", "spot")
            svc._store_result(key, AnalysisResult(key, {"i": i}, 0.0, 0.0))
        assert len(svc._cache) == 3
        svc.shutdown()


class TestThrottling:
    def test_requests_inside_the_min_interval_do_not_start_a_pass(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            clock = _Clock()
            svc = _CountingService(market, settings, min_interval=30.0, clock=clock)
            store = market.store("BTCUSDT", "1H")
            await svc.request("BTCUSDT", "1H")
            assert len(svc.calls) == 1

            for i in range(5, 10):
                store.apply(k(i * HOUR_MS, closed=True))
                await svc.request("BTCUSDT", "1H")
            assert len(svc.calls) == 1, "the throttle must hold the burst"
            assert svc.stats["throttled"] == 5

            clock.t += 31.0
            await svc.request("BTCUSDT", "1H")
            assert len(svc.calls) == 2, "and release once the interval has passed"
            await _drain()
            svc.shutdown()

        asyncio.run(scenario())

    def test_only_one_delayed_run_is_ever_scheduled_per_pair(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            clock = _Clock()
            svc = _CountingService(market, settings, min_interval=30.0, clock=clock)
            store = market.store("BTCUSDT", "1H")
            await svc.request("BTCUSDT", "1H")
            before = len(asyncio.all_tasks())
            for i in range(5, 15):
                store.apply(k(i * HOUR_MS, closed=True))
                await svc.request("BTCUSDT", "1H")
            scheduled = len(asyncio.all_tasks()) - before
            assert scheduled <= 1, "a burst must never queue a task per tick"
            await _drain()
            svc.shutdown()

        asyncio.run(scenario())

    def test_requests_during_a_pass_coalesce_into_one_follow_up(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            block = threading.Event()
            svc = _CountingService(market, settings, min_interval=0.0, block=block)
            store = market.store("BTCUSDT", "1H")

            first = asyncio.create_task(svc.request("BTCUSDT", "1H"))
            for _ in range(10):
                await asyncio.sleep(0)

            # while that pass is in flight, a new bar lands and ten requests pile in
            store.apply(k(4 * HOUR_MS, closed=True))
            for _ in range(10):
                await svc.request("BTCUSDT", "1H")
            assert svc.stats["coalesced"] == 10
            assert len(svc.calls) == 1

            block.set()
            await first
            for _ in range(20):
                await asyncio.sleep(0.01)
                if len(svc.calls) > 1:
                    break
            assert len(svc.calls) == 2, "ten coalesced requests must produce one extra pass"
            assert svc.calls[1].last_bar_ms == 4 * HOUR_MS
            await _drain()
            svc.shutdown()

        asyncio.run(scenario())

    def test_a_failed_pass_is_reported_not_swallowed(self) -> None:
        async def scenario() -> None:
            market, settings = _market_with()
            svc = AnalysisService(market, settings, min_interval=0.0)
            # only 3 closed bars: far below the engine's minimum
            result = await svc.request("BTCUSDT", "1H")
            assert result is not None and not result.ok
            assert "closed bars" in result.error
            assert svc.stats["errors"] == 1
            svc.shutdown()

        asyncio.run(scenario())


# =========================================================================== backoff


class TestBackoff:
    def test_the_delay_doubles_and_then_caps(self) -> None:
        delays = [backoff_delay(i, rand=lambda: 0.5) for i in range(10)]
        assert delays[:6] == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
        assert all(d <= 60.0 for d in delays)
        assert delays[-1] == 60.0

    def test_jitter_stays_inside_the_band(self) -> None:
        for attempt in range(8):
            lo = backoff_delay(attempt, rand=lambda: 0.0)
            hi = backoff_delay(attempt, rand=lambda: 1.0)
            assert lo < hi
            assert lo >= min(60.0, 2 ** attempt) * 0.7 - 1e-9


# =========================================================================== feed transport


class _FakeResponse:
    def __init__(self, payload: Any, status: int = 200, headers: dict | None = None) -> None:
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.calls.append((url, params or {}))
        return self.response

    async def aclose(self) -> None:
        pass


class TestFeedTransport:
    def _payload(self, bars: int, step_ms: int = 4 * HOUR_MS) -> list[list[Any]]:
        base = SEED_NOW_MS - bars * step_ms
        return [[base + i * step_ms, "10", "11", "9", "10.5", "100",
                 base + (i + 1) * step_ms - 1, "1000", 5, "1", "1", "0"]
                for i in range(bars)]

    def test_backfill_stores_history_without_touching_the_network(self) -> None:
        settings = SettingsStore(DashboardSettings(pairs=("BTCUSDT",), timeframes=("4H",),
                                                   history_bars=300))
        market = MarketData()
        client = _FakeClient(_FakeResponse(self._payload(10)))
        feed = MarketFeed(market, settings, http_factory=lambda: client)
        n = asyncio.run(feed.backfill(client, "BTCUSDT", "4H"))
        assert n >= 9
        assert client.calls[0][1]["interval"] == "4h"
        assert client.calls[0][1]["limit"] == 300
        assert len(market.get("BTCUSDT", "4H")) == n

    def test_a_rate_limited_backfill_raises_and_says_how_long_to_wait(self) -> None:
        settings = SettingsStore(DashboardSettings(pairs=("BTCUSDT",), timeframes=("4H",)))
        market = MarketData()
        client = _FakeClient(_FakeResponse({"code": -1003, "msg": "too many"}, 429,
                                           {"Retry-After": "42"}))
        feed = MarketFeed(market, settings, http_factory=lambda: client)
        with pytest.raises(RateLimited) as err:
            asyncio.run(feed.backfill(client, "BTCUSDT", "4H"))
        assert err.value.retry_after == 42.0

    def test_backfill_all_records_the_rate_limit_in_the_connection_state(self) -> None:
        settings = SettingsStore(DashboardSettings(pairs=("BTCUSDT",), timeframes=("4H",)))
        market = MarketData()
        client = _FakeClient(_FakeResponse({}, 429, {"Retry-After": "9"}))
        feed = MarketFeed(market, settings, http_factory=lambda: client)
        with pytest.raises(RateLimited):
            asyncio.run(feed.backfill_all([("BTCUSDT", "4H")]))
        conn = market.connection
        assert conn.status == "rate_limited"
        assert conn.retry_after == 9.0
        assert conn.to_dict()["live"] is False

    def test_replay_seeding_is_deterministic_and_offline(self) -> None:
        settings = SettingsStore(DashboardSettings(pairs=("BTCUSDT",), timeframes=("4H",),
                                                   source="replay"))
        a, b = MarketData(), MarketData()
        ReplayFeed(a, settings).seed("BTCUSDT", "4H", 200, now_ms=SEED_NOW_MS)
        ReplayFeed(b, settings).seed("BTCUSDT", "4H", 200, now_ms=SEED_NOW_MS)
        assert a.get("BTCUSDT", "4H").closed == b.get("BTCUSDT", "4H").closed
        assert len(a.get("BTCUSDT", "4H")) == 200


# =========================================================================== rejection panel


class TestRejectionGrouping:
    def _records(self) -> list[dict[str, Any]]:
        return (
            [{"gate": "G5", "reason": "insufficient_confluence", "setup_id": f"s{i}",
              "symbol": "BTCUSDT", "direction": "long", "time": 1,
              "source_ids": ["CF-31", "P14"], "detail": "2 of 3 classes"} for i in range(7)]
            + [{"gate": "G14", "reason": "rr_below_min", "setup_id": "r1",
                "symbol": "BTCUSDT", "direction": "long", "source_ids": ["CF-42"]}]
            + [{"gate": "G5", "reason": "single_class_trade", "setup_id": "s9",
                "symbol": "ETHUSDT", "direction": "short", "source_ids": ["CF-31"]}]
        )

    def test_groups_are_ordered_by_how_much_work_each_gate_did(self) -> None:
        groups = group_rejections(self._records())
        assert [g["gate"] for g in groups] == ["G5", "G14"]
        assert groups[0]["count"] == 8
        assert groups[0]["share_pct"] == pytest.approx(88.9, abs=0.1)
        assert sum(g["count"] for g in groups) == 9

    def test_each_group_explains_itself_and_names_the_keys_that_move_it(self) -> None:
        g5 = group_rejections(self._records())[0]
        assert g5["title"] == "Confluence / conviction"
        assert "min_confluence_count" in g5["config_keys"]
        assert g5["loosening"]
        assert g5["what"]

    def test_reasons_are_counted_and_worded(self) -> None:
        g5 = group_rejections(self._records())[0]
        reasons = {r["reason"]: r for r in g5["reasons"]}
        assert reasons["insufficient_confluence"]["count"] == 7
        assert reasons["single_class_trade"]["count"] == 1
        assert "min_confluence_count" in reasons["insufficient_confluence"]["text"]
        assert reasons["insufficient_confluence"]["source_ids"] == ["CF-31", "P14"]

    def test_examples_are_capped_so_the_panel_stays_readable(self) -> None:
        g5 = group_rejections(self._records())[0]
        for reason in g5["reasons"]:
            assert len(reason["examples"]) <= 5

    def test_an_unknown_gate_still_renders(self) -> None:
        groups = group_rejections([{"gate": "G99", "reason": "mystery"}])
        assert groups[0]["gate"] == "G99"
        assert groups[0]["title"]
        assert describe_gate("G99")["config_keys"] == []

    def test_every_documented_gate_names_real_config_keys(self) -> None:
        from tbot.config import KEY_SPEC_BY_NAME
        for gate in GATES.values():
            for key in gate["config_keys"]:
                assert key in KEY_SPEC_BY_NAME, f"{gate['gate']} references unknown key {key}"

    def test_no_rejections_is_an_empty_grouping_not_an_error(self) -> None:
        assert group_rejections([]) == []


# =========================================================================== serialization


def test_jsonable_flattens_decimals_enums_and_sets() -> None:
    from decimal import Decimal
    from tbot.models import Direction
    assert jsonable(Decimal("1.25")) == 1.25
    assert jsonable(Direction.LONG) == "long"
    assert jsonable({"a": {Decimal("2")}}) == {"a": [2.0]}


def test_watchlist_row_measures_distance_to_the_edge_price_reaches_first() -> None:
    payload = {
        "trend": "up", "structure_trend": "up", "meta": {"bar_time": 10, "last_close": 100.0},
        "regime": {"state": "risk_on", "risk_on": True},
        "plans": [{"conviction": "high"}], "setups": [{"qualified": True}], "rejections": [],
        "overlays": {"zones": [
            {"id": "z1", "side": "demand", "zone_class": "continuation", "top": 95.0,
             "bottom": 90.0, "fill_pct": 0.0, "touch_count": 1, "is_dead": False,
             "source_ids": ["CF-13"]},
            {"id": "z2", "side": "supply", "zone_class": "reversal", "top": 130.0,
             "bottom": 120.0, "fill_pct": 0.0, "touch_count": 0, "is_dead": False,
             "source_ids": ["CF-13"]},
        ]},
    }
    row = watchlist_row("BTCUSDT", "4H", payload, last_price=100.0, status="ready")
    assert row["nearest_zone"]["id"] == "z1"      # demand top 95 is 5 away; supply bottom is 20
    assert row["nearest_zone"]["edge"] == 95.0
    assert row["distance_pct"] == pytest.approx(-5.0)
    assert row["live_setups"] == 1 and row["best_conviction"] == "high"


def test_watchlist_row_ignores_dead_zones() -> None:
    payload = {"overlays": {"zones": [
        {"id": "dead", "side": "demand", "zone_class": "reversal", "top": 99.0, "bottom": 98.0,
         "fill_pct": 100.0, "touch_count": 4, "is_dead": True, "source_ids": []},
    ]}, "meta": {}, "plans": [], "setups": [], "rejections": []}
    row = watchlist_row("BTCUSDT", "4H", payload, last_price=100.0, status="ready")
    assert row["nearest_zone"] is None


def test_watchlist_row_survives_a_pair_with_no_analysis_yet() -> None:
    row = watchlist_row("BTCUSDT", "4H", None, last_price=None, status="waiting",
                        error="no data yet")
    assert row["status"] == "waiting" and row["distance_pct"] is None


# =========================================================================== settings


class TestSettings:
    def test_a_bad_config_value_changes_nothing(self) -> None:
        from tbot.config import ConfigError
        store = SettingsStore()
        store.apply({"overrides": {"min_rr": 2.5}})
        before = store.settings
        with pytest.raises(ConfigError):
            store.apply({"overrides": {"min_rr": -1}})
        assert store.settings is before
        assert store.config.min_rr == 2.5

    def test_an_unknown_key_is_refused_by_name(self) -> None:
        with pytest.raises(ValueError, match="unknown config key"):
            SettingsStore().apply({"overrides": {"make_me_rich": True}})

    def test_the_revision_increments_so_the_cache_key_moves(self) -> None:
        store = SettingsStore()
        assert store.settings.revision == 0
        assert store.apply({"overrides": {"min_rr": 2.1}}).revision == 1
        assert store.apply({"overrides": {"min_rr": 2.2}}).revision == 2

    @pytest.mark.parametrize("patch,message", [
        ({"pairs": []}, "at least one pair"),
        ({"pairs": ["BTC/USDT!"]}, "not a usable symbol"),
        ({"timeframes": ["7H"]}, "not a timeframe"),
        ({"timeframes": ["1H", "2H", "4H", "8H", "12H"]}, "at most 4 timeframes"),
        ({"history_bars": 10}, "history_bars"),
        ({"source": "kraken"}, "unknown source"),
        ({"venue_kind": "futures"}, "venue_kind"),
    ])
    def test_input_validation(self, patch: dict, message: str) -> None:
        with pytest.raises((ValueError, TypeError), match=message):
            SettingsStore().apply(patch)

    def test_symbols_are_normalised(self) -> None:
        s = SettingsStore().apply({"pairs": [" btc/usdt ", "eth-usdt", "BTCUSDT"]})
        assert s.pairs == ("BTCUSDT", "ETHUSDT")

    def test_subscriptions_are_the_cross_product(self) -> None:
        s = DashboardSettings(pairs=("A", "B"), timeframes=("1H", "4H"))
        assert s.subscriptions() == (("A", "1H"), ("A", "4H"), ("B", "1H"), ("B", "4H"))


# =========================================================================== HTTP API


@pytest.fixture(scope="module")
def client() -> TestClient:
    """A fully wired app with no feed running and one pre-seeded pair.  No network."""
    settings = DashboardSettings(pairs=("BTCUSDT", "ETHUSDT"), timeframes=("4H",),
                                 source="replay", history_bars=400)
    market = MarketData(source="replay")
    seeder = ReplayFeed(market, SettingsStore(settings))
    seeder.seed("BTCUSDT", "4H", 400, now_ms=SEED_NOW_MS)
    app = create_app(settings, market=market, start_feed=False,
                     analysis_kwargs={"min_interval": 0.0})
    with TestClient(app) as c:
        c.get("/api/analysis?symbol=BTCUSDT&timeframe=4H&refresh=true")
        yield c


class TestApi:
    def test_the_page_and_its_assets_are_served_from_the_same_port(self, client) -> None:
        assert client.get("/").status_code == 200
        assert "tbot" in client.get("/").text
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/style.css").status_code == 200

    def test_status_reports_feed_health_and_cache_counters(self, client) -> None:
        st = client.get("/api/status").json()
        assert set(st) >= {"connection", "pairs", "cache", "trustworthy", "source"}
        assert st["connection"]["source"] == "replay"
        assert {p["symbol"] for p in st["pairs"]} == {"BTCUSDT", "ETHUSDT"}
        assert st["cache"]["computed"] >= 1

    def test_status_refuses_to_call_a_dead_feed_trustworthy(self, client) -> None:
        # start_feed=False, so the connection never went live
        st = client.get("/api/status").json()
        assert st["connection"]["live"] is False
        assert st["trustworthy"] is False

    def test_analysis_returns_candles_overlays_and_plans(self, client) -> None:
        env = client.get("/api/analysis?symbol=BTCUSDT&timeframe=4H").json()
        assert env["ok"] is True, env.get("error")
        assert len(env["candles"]) > 100
        a = env["analysis"]
        assert a["symbol"] == "BTCUSDT" and a["timeframe"] == "4H"
        assert {"zones", "order_blocks", "levels", "fibs", "ranges"} <= set(a["overlays"])
        assert a["overlays"]["zones"], "the replay fixture should produce zones"
        assert isinstance(a["plans"], list)
        assert env["key"]["symbol"] == "BTCUSDT"
        assert env["key"]["last_bar_ms"] > 0

    def test_every_drawn_object_carries_its_rule_ids(self, client) -> None:
        a = client.get("/api/analysis?symbol=BTCUSDT&timeframe=4H").json()["analysis"]
        drawn = (a["overlays"]["zones"] + a["overlays"]["order_blocks"]
                 + a["overlays"]["levels"] + a["overlays"]["fibs"])
        assert drawn
        for obj in drawn:
            assert obj["source_ids"], f"{obj['id']} reached the chart with no provenance"
        for plan in a["plans"]:
            assert plan["source_ids"]
            assert plan["setup"]["source_ids"]

    def test_bar_indices_are_translated_into_times_for_the_chart(self, client) -> None:
        a = client.get("/api/analysis?symbol=BTCUSDT&timeframe=4H").json()["analysis"]
        assert a["meta"]["bar_time"] > 1_000_000_000
        for zone in a["overlays"]["zones"]:
            assert zone["start_time"] is not None
            assert zone["start_time"] <= a["meta"]["bar_time"]

    def test_a_pair_outside_the_watchlist_is_a_404_with_advice(self, client) -> None:
        r = client.get("/api/analysis?symbol=DOGEUSDT&timeframe=4H")
        assert r.status_code == 404
        assert "watchlist" in r.json()["detail"]

    def test_a_pair_with_no_data_says_so_rather_than_drawing_nothing(self, client) -> None:
        env = client.get("/api/analysis?symbol=ETHUSDT&timeframe=4H").json()
        assert env["ok"] is False
        assert env["error"]

    def test_watchlist_has_one_row_per_pair_and_timeframe(self, client) -> None:
        rows = client.get("/api/watchlist").json()["rows"]
        assert [(r["symbol"], r["timeframe"]) for r in rows] == [
            ("BTCUSDT", "4H"), ("ETHUSDT", "4H")]
        btc = rows[0]
        assert btc["status"] == "ready"
        assert btc["trend"] in ("up", "down", "neutral")
        assert btc["last_price"] is not None
        assert btc["bars"] == 400
        eth = rows[1]
        assert eth["status"] == "waiting" and eth["last_price"] is None

    def test_setups_are_tickets_with_ladder_stop_and_targets(self, client) -> None:
        data = client.get("/api/setups").json()
        assert data["count"] == len(data["plans"])
        for plan in data["plans"]:
            assert plan["entries"] and plan["take_profits"]
            assert plan["stop_price"] is not None
            assert plan["qty_total"] is not None
            assert plan["rr_to_tp1"] is not None
            # F9: the ticket ships both ratios so the chart can show the gated one.
            assert plan["rr_to_final_tp"] is not None
            assert plan["conviction"] in ("low", "normal", "high")
            assert sum(e["size_fraction"] for e in plan["entries"]) == pytest.approx(1.0, abs=1e-6)
            assert plan["source_ids"]

    def test_rejections_are_grouped_by_gate_with_counts(self, client) -> None:
        data = client.get("/api/rejections").json()
        assert data["total"] >= 1
        assert data["groups"]
        assert sum(g["count"] for g in data["groups"]) == data["total"]
        first = data["groups"][0]
        assert {"gate", "title", "what", "loosening", "config_keys", "reasons",
                "share_pct"} <= set(first)
        assert first["count"] >= data["groups"][-1]["count"]

    def test_rejections_can_be_scoped_to_one_pair(self, client) -> None:
        data = client.get("/api/rejections?symbol=ETHUSDT&timeframe=4H").json()
        assert data["total"] == 0 and data["groups"] == []

    def test_gates_endpoint_documents_the_whole_stack(self, client) -> None:
        gates = client.get("/api/gates").json()["gates"]
        ids = {g["gate"] for g in gates}
        assert {"G5", "G11", "G14", "G17"} <= ids
        for g in gates:
            assert g["what"] and g["loosening"]

    def test_config_search_returns_value_default_and_source_id(self, client) -> None:
        data = client.get("/api/config?grep=zone").json()
        assert data["total"] == 254
        assert data["keys"]
        for row in data["keys"]:
            assert "source_id" in row and row["source_id"]
            assert "default" in row and "value" in row

    def test_settings_get_offers_the_shortlist_with_provenance(self, client) -> None:
        data = client.get("/api/settings").json()
        assert data["settings"]["pairs"] == ["BTCUSDT", "ETHUSDT"]
        assert data["settings"]["source"] == "replay"
        groups = data["tunables"]
        assert len(groups) >= 4
        keys = {row["key"] for g in groups for row in g["keys"]}
        assert {"min_rr", "min_confluence_count", "stop_buffer_atr"} <= keys
        for g in groups:
            for row in g["keys"]:
                assert row["source_id"]

    def test_a_settings_edit_bumps_the_revision_and_recomputes(self, client) -> None:
        before = client.get("/api/status").json()["settings_revision"]
        r = client.post("/api/settings", json={"overrides": {"min_rr": 1.9}})
        assert r.status_code == 200
        body = r.json()
        assert body["settings"]["revision"] == before + 1
        assert body["settings"]["overrides"]["min_rr"] == 1.9
        assert body["recomputing"] == ["BTCUSDT:4H", "ETHUSDT:4H"]
        # the POST already kicked off a pass per pair; poll until the new one lands
        for _ in range(50):
            env = client.get("/api/analysis?symbol=BTCUSDT&timeframe=4H").json()
            if env["key"]["settings_revision"] == before + 1:
                break
            time.sleep(0.2)
        assert env["key"]["settings_revision"] == before + 1
        assert env["stale"] is False

    def test_a_rejected_settings_edit_lists_every_problem_and_changes_nothing(
            self, client) -> None:
        before = client.get("/api/settings").json()["settings"]
        r = client.post("/api/settings", json={"overrides": {"min_rr": -3}})
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "nothing changed" in detail["message"]
        assert detail["problems"]
        assert client.get("/api/settings").json()["settings"] == before

    def test_a_rejected_pair_list_changes_nothing(self, client) -> None:
        before = client.get("/api/settings").json()["settings"]
        r = client.post("/api/settings", json={"pairs": ["not a symbol!"]})
        assert r.status_code == 400
        assert client.get("/api/settings").json()["settings"] == before

    def test_the_websocket_pushes_status_on_connect(self, client) -> None:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "status"
            assert msg["status"]["source"] == "replay"
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"


    def test_switching_the_source_rebuilds_the_feed_for_the_new_venue(self) -> None:
        """A restart is not enough: the adapter is chosen when the feed is constructed."""
        app = create_app(DashboardSettings(pairs=("BTCUSDT",), timeframes=("4H",),
                                           source="binance"), start_feed=False)
        with TestClient(app) as c:
            assert type(app.state.feed).__name__ == "MarketFeed"
            assert app.state.feed.adapter.name == "binance"

            assert c.post("/api/settings", json={"source": "bybit"}).status_code == 200
            assert app.state.feed.adapter.name == "bybit"

            assert c.post("/api/settings", json={"source": "replay"}).status_code == 200
            assert type(app.state.feed).__name__ == "ReplayFeed"
            assert c.get("/api/status").json()["connection"]["source"] == "replay"


class TestReadOnly:
    """Guard-rails: the dashboard must stay incapable of touching an account."""

    def test_no_route_mutates_an_exchange(self) -> None:
        app = create_app(DashboardSettings(source="replay"), start_feed=False)
        posts = {r.path for r in app.routes
                 if "POST" in (getattr(r, "methods", None) or set())}
        assert posts == {"/api/settings"}, "settings is the only write endpoint"

    def test_the_feed_module_never_names_an_order_endpoint(self) -> None:
        from pathlib import Path
        import tbot.dashboard as pkg

        banned = ("/api/v3/order", "/v5/order", "X-MBX-APIKEY", "recvWindow",
                  "api_secret", "apiKey", "import hmac", "hmac.new")
        for path in Path(pkg.__file__).parent.rglob("*.py"):
            text = path.read_text()
            for token in banned:
                assert token not in text, f"{path.name} mentions {token!r}"
