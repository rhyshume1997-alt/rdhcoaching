"""FastAPI app: JSON API and the static frontend, one process, one port.

Everything the browser needs is served from here — there is no build step, no second server and
no CORS story, because the page and the API share an origin.

The API is deliberately shaped so the UI cannot show a number without its provenance: every
object it returns carries ``source_ids``, every analysis envelope carries the exact
``(pair, timeframe, last closed bar, settings revision)`` it was computed from, and the feed's
own health is a first-class resource rather than something inferred from missing data.

Read-only, throughout.  Nothing in this package can place an order (SPEC.md §1.9, §12.6).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tbot.config import KEY_SPEC_BY_NAME, ConfigError

from .analysis import AnalysisService
from .feed import build_feed
from .gates import GATES, group_rejections
from .settings import DashboardSettings, SettingsStore, grouped_tunables, tunable_rows
from .store import MarketData

__all__ = ["create_app", "serve", "Hub"]

log = logging.getLogger("tbot.dashboard")

STATIC_DIR = Path(__file__).resolve().parent / "static"

#: forming-bar broadcasts per pair per second.  **[OUR CHOICE]** — a display rate, nothing
#: downstream of it recomputes anything.
TICK_BROADCAST_HZ = 2.0


class Hub:
    """Fan-out to every open dashboard websocket.  A dead socket is dropped, never awaited."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def drop(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)

    async def broadcast(self, message: Mapping[str, Any]) -> None:
        if not self._clients:
            return
        payload = json.dumps(message, default=str)
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


def create_app(
    settings: DashboardSettings | None = None,
    *,
    market: MarketData | None = None,
    start_feed: bool = True,
    feed_factory: Callable[..., Any] | None = None,
    analysis_kwargs: Mapping[str, Any] | None = None,
) -> FastAPI:
    """Build the app.  ``start_feed=False`` gives a fully working API with no network at all."""

    store = SettingsStore(settings or DashboardSettings())
    data = market or MarketData(source=store.settings.source)
    hub = Hub()
    state: dict[str, Any] = {"last_tick_broadcast": {}}

    async def on_update(symbol: str, tf: str, result: Any) -> None:
        await hub.broadcast({
            "type": "analysis",
            "symbol": symbol,
            "timeframe": tf,
            "ok": result.ok,
            "error": result.error,
            "bar_time": (result.payload or {}).get("meta", {}).get("bar_time")
            if result.payload else None,
            "duration_seconds": round(result.duration, 3),
            "settings_revision": result.key.revision,
        })

    analysis = AnalysisService(data, store, on_update=on_update,
                               **dict(analysis_kwargs or {}))

    async def broadcast_status() -> None:
        await hub.broadcast({"type": "status", "status": status_payload()})

    def status_payload() -> dict[str, Any]:
        settings_now = store.settings
        conn = data.connection.to_dict()
        pairs: list[dict[str, Any]] = []
        for symbol, tf in settings_now.subscriptions():
            s = data.get(symbol, tf)
            result = analysis.latest(symbol, tf)
            pairs.append({
                "symbol": symbol, "timeframe": tf,
                "bars": len(s) if s else 0,
                "last_price": s.last_price if s else None,
                "last_closed_open_ms": s.last_closed_open_ms if s else None,
                "forming": s.forming_json() if s else None,
                "data_stale": bool(s.is_stale()) if s else True,
                "gap_detected": bool(s.last_gap_at) if s else False,
                "analysis_current": analysis.is_current(result, symbol, tf),
                "analysis_error": (result.error if result and not result.ok else None),
            })
        any_stale = any(p["data_stale"] for p in pairs) if pairs else True
        return {
            "connection": conn,
            "pairs": pairs,
            "clients": hub.count,
            "cache": dict(analysis.stats),
            "settings_revision": settings_now.revision,
            "source": settings_now.source,
            "trustworthy": bool(conn["live"] and not any_stale),
            "server_time": time.time(),
        }

    async def on_closed_bar(symbol: str, tf: str) -> None:
        # the only event that may trigger a pipeline pass
        await analysis.request(symbol, tf)

    async def on_tick(symbol: str, tf: str) -> None:
        now = time.time()
        last = state["last_tick_broadcast"].get((symbol, tf), 0.0)
        if now - last < 1.0 / TICK_BROADCAST_HZ:
            return
        state["last_tick_broadcast"][(symbol, tf)] = now
        s = data.get(symbol, tf)
        if s is None:
            return
        await hub.broadcast({"type": "tick", "symbol": symbol, "timeframe": tf,
                             "forming": s.forming_json(), "last_price": s.last_price})

    factory = feed_factory or build_feed

    def make_feed() -> Any:
        # The adapter (and, for 'replay', the whole feed class) is chosen from the settings at
        # construction, so changing ``source`` or ``venue_kind`` has to rebuild the feed rather
        # than restart the old one against the wrong venue.
        return factory(data, store, on_closed_bar=on_closed_bar, on_tick=on_tick,
                       on_state=broadcast_status)

    state["feed"] = make_feed()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_feed:
            await state["feed"].start()
        try:
            yield
        finally:
            if start_feed:
                with contextlib.suppress(Exception):
                    await state["feed"].stop()
            analysis.shutdown()

    app = FastAPI(title="tbot dashboard", version="1.0",
                  description="Read-only view over tbot.pipeline. Places no orders.",
                  lifespan=lifespan)
    app.state.settings_store = store
    app.state.market = data
    app.state.analysis = analysis
    app.state.hub = hub
    app.state.feed = state["feed"]

    # ------------------------------------------------------------------ API

    @app.get("/api/status")
    async def api_status() -> dict[str, Any]:
        return status_payload()

    @app.get("/api/settings")
    async def api_settings_get() -> dict[str, Any]:
        s = store.settings
        return {
            "settings": s.to_dict(),
            "tunables": grouped_tunables(store.config, s.overrides),
        }

    @app.post("/api/settings")
    async def api_settings_post(request: Request) -> dict[str, Any]:
        try:
            patch = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="body must be JSON")
        if not isinstance(patch, dict):
            raise HTTPException(status_code=400, detail="body must be a JSON object")
        before = store.settings
        try:
            new = store.apply(patch)
        except ConfigError as err:
            raise HTTPException(status_code=400, detail={
                "message": "config rejected — nothing changed",
                "problems": [str(p) for p in err.problems],
            })
        except (ValueError, TypeError, KeyError) as err:
            raise HTTPException(status_code=400, detail={"message": str(err)})

        analysis.invalidate()
        data.prune(new.subscriptions())
        rebuild = new.source != before.source or new.venue_kind != before.venue_kind
        restart = (rebuild or new.pairs != before.pairs
                   or new.timeframes != before.timeframes
                   or new.history_bars != before.history_bars)
        if restart:
            # the subscription set changed: reconnect rather than serve a stale stream
            if start_feed:
                await state["feed"].stop()
            if rebuild:
                data.connection.source = new.source
                state["feed"] = make_feed()
                app.state.feed = state["feed"]
            if start_feed:
                await state["feed"].start()
        if not restart or not start_feed:
            for symbol, tf in new.subscriptions():
                asyncio.create_task(analysis.request(symbol, tf, force=True))
        await hub.broadcast({"type": "settings", "revision": new.revision,
                             "restarted_feed": bool(restart)})
        return {
            "settings": new.to_dict(),
            "tunables": grouped_tunables(store.config, new.overrides),
            "recomputing": [f"{s}:{t}" for s, t in new.subscriptions()],
            "feed_restarted": bool(restart),
        }

    @app.get("/api/watchlist")
    async def api_watchlist(refresh: bool = False) -> dict[str, Any]:
        if refresh:
            for symbol, tf in store.settings.subscriptions():
                await analysis.request(symbol, tf)
        return {"rows": analysis.watchlist(), "status": status_payload()}

    @app.get("/api/analysis")
    async def api_analysis(
        symbol: str = Query(..., min_length=2, max_length=24),
        timeframe: str = Query(...),
        refresh: bool = False,
    ) -> JSONResponse:
        symbol = symbol.upper()
        settings_now = store.settings
        if (symbol, timeframe) not in settings_now.subscriptions():
            raise HTTPException(
                status_code=404,
                detail=f"{symbol} {timeframe} is not in the watchlist; add it in Settings")
        result = await analysis.request(symbol, timeframe, force=refresh, wait=refresh)
        if result is None:
            result = analysis.latest(symbol, timeframe)
        s = data.get(symbol, timeframe)
        if result is None:
            return JSONResponse({
                "ok": False,
                "error": "no analysis yet — waiting for enough closed bars",
                "symbol": symbol, "timeframe": timeframe,
                "candles": s.candles_json() if s else [],
                "forming": s.forming_json() if s else None,
                "stale": True,
            }, status_code=200)
        envelope = result.envelope(
            stale=not analysis.is_current(result, symbol, timeframe),
            last_price=s.last_price if s else None)
        envelope["symbol"] = symbol
        envelope["timeframe"] = timeframe
        envelope["candles"] = s.candles_json() if s else []
        envelope["forming"] = s.forming_json() if s else None
        envelope["data_stale"] = bool(s.is_stale()) if s else True
        envelope["connection"] = data.connection.to_dict()
        if envelope["analysis"]:
            envelope["rejection_groups"] = group_rejections(
                envelope["analysis"].get("rejections") or [])
        return JSONResponse(envelope)

    @app.get("/api/setups")
    async def api_setups() -> dict[str, Any]:
        """Every qualified trade plan across the watchlist, best conviction first."""
        order = {"high": 3, "normal": 2, "low": 1}
        plans: list[dict[str, Any]] = []
        for symbol, tf in store.settings.subscriptions():
            result = analysis.latest(symbol, tf)
            if result is None or not result.ok or not result.payload:
                continue
            current = analysis.is_current(result, symbol, tf)
            s = data.get(symbol, tf)
            for plan in result.payload.get("plans") or []:
                row = dict(plan)
                row["timeframe"] = tf
                row["stale"] = not current
                row["bar_time"] = result.payload.get("meta", {}).get("bar_time")
                row["last_price"] = s.last_price if s else None
                plans.append(row)
        plans.sort(key=lambda p: (-order.get(str(p.get("conviction")), 0),
                                  -(p.get("confluence_score") or 0)))
        return {"plans": plans, "count": len(plans)}

    @app.get("/api/rejections")
    async def api_rejections(symbol: str | None = None,
                             timeframe: str | None = None) -> dict[str, Any]:
        """Near-misses grouped by the gate that killed them, across one pair or all of them."""
        records: list[dict[str, Any]] = []
        for sym, tf in store.settings.subscriptions():
            if symbol and sym != symbol.upper():
                continue
            if timeframe and tf != timeframe:
                continue
            result = analysis.latest(sym, tf)
            if result is None or not result.ok or not result.payload:
                continue
            for rec in result.payload.get("rejections") or []:
                row = dict(rec)
                row["timeframe"] = tf
                row["symbol"] = row.get("symbol") or sym
                records.append(row)
        groups = group_rejections(records)
        return {
            "groups": groups,
            "total": len(records),
            "scope": {"symbol": symbol, "timeframe": timeframe},
            "gates_evaluated": sorted({g["gate"] for g in groups}),
        }

    @app.get("/api/gates")
    async def api_gates() -> dict[str, Any]:
        return {"gates": list(GATES.values())}

    @app.get("/api/config")
    async def api_config(grep: str | None = None, limit: int = 60) -> dict[str, Any]:
        """Search all 247 keys — value, default and the source rule id behind each one."""
        names = list(KEY_SPEC_BY_NAME)
        if grep:
            needle = grep.strip().lower()
            names = [k for k in names
                     if needle in k.lower()
                     or needle in KEY_SPEC_BY_NAME[k].source_id.lower()
                     or needle in KEY_SPEC_BY_NAME[k].group.lower()]
        names = names[:max(1, min(int(limit), 250))]
        return {"keys": tunable_rows(store.config, store.settings.overrides, names),
                "total": len(KEY_SPEC_BY_NAME)}

    # ------------------------------------------------------------------ websocket

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        await hub.add(ws)
        try:
            await ws.send_text(json.dumps({"type": "status", "status": status_payload()},
                                          default=str))
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": time.time()}))
                elif msg.get("type") == "status":
                    await ws.send_text(json.dumps({"type": "status",
                                                   "status": status_payload()}, default=str))
        except WebSocketDisconnect:
            pass
        except Exception:  # pragma: no cover - transport-level
            pass
        finally:
            await hub.drop(ws)

    # ------------------------------------------------------------------ frontend

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


def serve(settings: DashboardSettings | None = None, *, host: str = "127.0.0.1",
          port: int = 8000, log_level: str = "warning") -> None:
    """Run the dashboard.  Blocks until interrupted."""
    import uvicorn

    app = create_app(settings)
    uvicorn.run(app, host=host, port=port, log_level=log_level)
