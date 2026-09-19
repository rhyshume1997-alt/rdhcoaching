"""tbot.dashboard — a local, read-only web dashboard over :mod:`tbot.pipeline`.

The ``tbot`` *analysis* package makes no network calls (SPEC.md §1.9, INTERFACES.md §1.8).
This sub-package is the deliberate, quarantined exception: it fetches **public market data
only** — no API key, no account, no signature, and no code path anywhere in it can place,
amend or cancel an order.  Everything it downloads is candles.

Layering, so the quarantine stays obvious::

    exchanges.py   URL building + payload parsing.  Pure functions, no I/O, no imports of
                   httpx or websockets.  This is where the exchange wire formats live.
    store.py       CandleStore + ConnectionState.  Pure.  Holds closed bars and the single
                   forming bar *separately* — the no-lookahead boundary.
    feed.py        The only module that opens a socket.  Backfill over REST, live updates
                   over the public websocket, exponential backoff, rate-limit detection.
    analysis.py    Cached, throttled, thread-pool-backed runner for tbot.pipeline.
    serialize.py   PipelineRun -> JSON the browser can draw.
    gates.py       Human wording for the §7.1 gate ids, for the "Rejected" panel.
    server.py      FastAPI app: JSON API + the static frontend on one port.

``python -m tbot dashboard`` starts it.
"""

from __future__ import annotations

__all__ = ["create_app", "serve"]


def __getattr__(name: str):  # pragma: no cover - thin lazy re-export
    if name in ("create_app", "serve"):
        from . import server

        return getattr(server, name)
    raise AttributeError(name)
