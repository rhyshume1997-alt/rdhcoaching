#!/usr/bin/env python3
"""fetch_klines.py — a STANDALONE OHLCV downloader.  Not part of the ``tbot`` package.

The ``tbot`` package makes no network calls, anywhere, ever (SPEC.md §1.9, INTERFACES.md §1.8),
and the container it is developed in has no exchange access.  This script is the deliberate
exception and it lives *outside* the package so that separation stays obvious: run it on your own
machine, get a CSV, hand the CSV to ``tbot backtest``.

It uses only the Python standard library, reads **public** market-data endpoints, and needs no API
key, no account and no signature.  Nothing here writes an order.

Usage
-----

    python scripts/fetch_klines.py --symbol SOLUSDT --tf 4H --bars 3000 --out sol_4h.csv
    python scripts/fetch_klines.py --venue bybit --market linear --symbol BTCUSDT --tf 1H \
        --bars 5000 --out btc_1h_perp.csv

Output columns (exactly what ``tbot.data.load_csv`` expects)::

    timestamp,open,high,low,close,volume,quote_volume

``timestamp`` is the bar **open** time in ISO-8601 UTC.  The still-forming final bar is dropped:
P1 forbids repainting and the Series contract requires closed bars only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BINANCE = "https://api.binance.com/api/v3/klines"
BYBIT = "https://api.bybit.com/v5/market/kline"

#: tbot timeframe label -> (binance interval, bybit interval, minutes)
INTERVALS: dict[str, tuple[str, str, int]] = {
    "1m": ("1m", "1", 1),
    "5m": ("5m", "5", 5),
    "15m": ("15m", "15", 15),
    "30m": ("30m", "30", 30),
    "1H": ("1h", "60", 60),
    "2H": ("2h", "120", 120),
    "4H": ("4h", "240", 240),
    "8H": ("8h", "480", 480),
    "12H": ("12h", "720", 720),
    "1D": ("1d", "D", 1440),
    "1W": ("1w", "W", 10080),
}


def _get(url: str, params: dict[str, str | int]) -> object:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "tbot-fetch/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_binance(symbol: str, tf: str, bars: int) -> list[list[float]]:
    interval, _, minutes = INTERVALS[tf]
    step = minutes * 60_000
    end = int(time.time() * 1000) // step * step
    rows: list[list[float]] = []
    while len(rows) < bars:
        want = min(1000, bars - len(rows))
        start = end - want * step
        payload = _get(BINANCE, {"symbol": symbol.upper(), "interval": interval,
                                 "startTime": start, "endTime": end - 1, "limit": want})
        if not payload:
            break
        chunk = [[float(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                  float(k[5]), float(k[7])] for k in payload]  # type: ignore[index]
        rows = chunk + rows
        end = int(chunk[0][0])
        time.sleep(0.25)   # be polite to a public endpoint
    return rows[-bars:]


def fetch_bybit(symbol: str, tf: str, bars: int, market: str) -> list[list[float]]:
    _, interval, minutes = INTERVALS[tf]
    step = minutes * 60_000
    end = int(time.time() * 1000) // step * step
    rows: list[list[float]] = []
    while len(rows) < bars:
        want = min(1000, bars - len(rows))
        payload = _get(BYBIT, {"category": market, "symbol": symbol.upper(),
                               "interval": interval, "end": end - 1, "limit": want})
        entries = payload.get("result", {}).get("list", [])  # type: ignore[union-attr]
        if not entries:
            break
        entries = list(reversed(entries))  # bybit returns newest first
        chunk = [[float(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                  float(k[5]), float(k[6])] for k in entries]
        rows = chunk + rows
        end = int(chunk[0][0])
        time.sleep(0.25)
    return rows[-bars:]


def write_csv(rows: list[list[float]], out: Path, minutes: int) -> int:
    """Write the CSV, dropping any bar that has not closed yet (P1: no repainting)."""
    now_ms = time.time() * 1000
    closed = [r for r in rows if r[0] + minutes * 60_000 <= now_ms]
    closed.sort(key=lambda r: r[0])
    deduped: list[list[float]] = []
    for row in closed:
        if deduped and deduped[-1][0] == row[0]:
            deduped[-1] = row
        else:
            deduped.append(row)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume", "quote_volume"])
        for ts, o, h, low, c, v, qv in deduped:
            stamp = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
            writer.writerow([stamp, o, h, low, c, v, qv])
    return len(deduped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download public OHLCV klines into a CSV that `tbot backtest` can read. "
                    "Standalone: this script is NOT part of the tbot package, which never makes "
                    "network calls.")
    parser.add_argument("--venue", default="binance", choices=("binance", "bybit"))
    parser.add_argument("--market", default="spot", choices=("spot", "linear", "inverse"),
                       help="bybit only: 'linear' for USDT perps (perp setups need perp candles, "
                            "S6-R43)")
    parser.add_argument("--symbol", required=True, help="e.g. SOLUSDT")
    parser.add_argument("--tf", default="4H", choices=sorted(INTERVALS),
                       help="timeframe label, matching tbot's ladder")
    parser.add_argument("--bars", type=int, default=2000, help="how many closed bars to fetch")
    parser.add_argument("--out", required=True, help="output CSV path")
    args = parser.parse_args(argv)

    minutes = INTERVALS[args.tf][2]
    try:
        if args.venue == "binance":
            rows = fetch_binance(args.symbol, args.tf, args.bars)
        else:
            rows = fetch_bybit(args.symbol, args.tf, args.bars, args.market)
    except urllib.error.URLError as err:
        print(f"network error talking to {args.venue}: {err}\n"
              f"Run this on a machine with exchange access; the tbot container has none.",
              file=sys.stderr)
        return 1

    if not rows:
        print(f"no data returned for {args.symbol} {args.tf} on {args.venue}", file=sys.stderr)
        return 1

    out = Path(args.out)
    count = write_csv(rows, out, minutes)
    print(f"wrote {count} closed {args.tf} bars for {args.symbol} to {out}")
    print(f"next: python -m tbot backtest --csv {out} --tf {args.tf} --symbol {args.symbol.upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
