# tbot — a trading-signal system with a strict backtest harness

`tbot` turns the rules extracted in [`../SPEC.md`](../SPEC.md) into code: it reads OHLCV candles,
runs an analysis pipeline over them (support/resistance, ranges, supply/demand zones, order blocks,
market structure, fibs, SFPs, confluence scoring, qualification gates), builds trade plans, and
simulates those plans bar by bar with a deliberately pessimistic execution model.

It is a **research and analysis tool**. It emits plans and statistics. That is all it does.

---

## What this is NOT

* **It does not trade.** There is no live trading in this build and none is planned here.
  `tbot/execution.py` defines the `ExecutionAdapter` protocol and two implementations: a
  `PaperAdapter` that records intended orders in memory, and a `NullAdapter` whose every method
  raises `NotImplementedError`. There is no exchange client, no API key handling, no endpoint and
  no signing code anywhere in the package (SPEC.md §1.9, §12.6).
* **It makes no network calls.** Not one, anywhere in `tbot/`. Market data arrives as a CSV you
  produced yourself. The one downloader in this repository, `scripts/fetch_klines.py`, lives
  *outside* the package precisely so that boundary stays visible.
* **It is not financial advice, and it is not a validated strategy.** The instructor's claimed
  77–82 % win rate is treated as a *hypothesis the harness exists to test* (SPEC.md §12.5), never
  as a target. Nothing in the package sizes, weights or calibrates anything against that number.
* **It is not the trader's own system.** A large fraction of the numbers are ours, not his: every
  value marked `[OUR CHOICE]` or "OUR number" in `tbot config` output is an interpolation over a
  gap in the source material. See [`../CONFLICTS.md`](../CONFLICTS.md) and SPEC.md §14 for the
  fifteen questions that are still open.

---

## Install

Python 3.11+. The package needs `numpy`, `pandas` and `PyYAML`.

```bash
cd bot
python -m pip install -r requirements.txt
python -m pytest              # the full suite
python -m tbot --help
```

`requirements.txt` covers both the engine (`numpy`, `pandas`, `PyYAML`) and the web dashboard
(`fastapi`, `uvicorn`, `httpx`, `websockets`). The engine alone needs only the first three.

There is no build step and no packaging metadata to install: run it from this directory, or put
this directory on `PYTHONPATH`.

---

## The five commands

`python -m tbot <command>` (or `python -c "from tbot.cli import main; main()"`).

### 1. `backtest` — run the §12 harness and print the metrics report

```bash
python -m tbot backtest --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT
python -m tbot backtest --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT \
    --set min_rr=2.5 --set swing_k=5 --equity 25000 \
    --events run_events.txt --save-run run.json
```

Prints win rate under all three definitions, the 77–82 % claim beside the measured value,
expectancy, the R distribution, max drawdown, per-detector and per-config attribution, fill
quality, excess risk, the veto census and time in market. Every figure is **net of fees, slippage
and funding** — SPEC.md §12.3 forbids reporting anything gross.

### 2. `scan` — trade tickets for the latest bars

```bash
python -m tbot scan --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT
python -m tbot scan --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT --bars 20
```

Runs the pipeline over the last `--bars` closes and prints any resulting plan as a human-readable
ticket: entry ladder, then stop, then take-profits — the order SPEC.md §8 builds them in — with the
size, the R:R, the invalidation level and the source rule IDs behind the plan. If nothing
qualifies, it says so: an empty result is correct behaviour (PL-9, "never force a setup"), not a
failure.

### 3. `config` — every key with its value, default and source

```bash
python -m tbot config                       # all 245 keys
python -m tbot config --changed-only        # just what this run overrides
python -m tbot config --group 11.12         # the backtest-harness keys
python -m tbot config --grep zone
python -m tbot config --config configs/default.yaml --set min_rr=3.0 --json
```

The `source` column is the provenance: a rule ID like `CF-08; S5-R28, S6-R10` means the value comes
from the corpus; `[OUR CHOICE]` or "OUR number" means we invented it to fill a gap. That
distinction is the point of the command — no number in this system should be presented as the
trader's unless it actually is.

### 4. `explain` — one trade's full source-rule chain

```bash
python -m tbot backtest --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT --save-run run.json
python -m tbot explain --trade T0007 --run run.json
# or re-run the (deterministic) backtest and explain straight from it:
python -m tbot explain --trade T0007 --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT
```

Prints every event behind that trade — detection, qualification rejection, plan, arm, each fill,
each state transition, each trail, the exit — with the rule IDs attached to each line, plus the
execution assumptions that governed the fills. Any trade the harness produced can be explained
after the fact; that is a hard requirement, not a convenience.

---

## CSV format

`tbot.data.load_csv` expects a header row and these columns:

```csv
timestamp,open,high,low,close,volume,quote_volume
2024-01-01T00:00:00+00:00,101.5,103.2,101.0,102.8,1523.4,156_000.0
```

| Column | Notes |
|---|---|
| `timestamp` | Bar **open** time. ISO-8601 (any offset) or epoch seconds/milliseconds. Parsed to UTC. Aliases accepted: `time`, `open_time`, `date`, `datetime`. |
| `open,high,low,close` | Floats. `low <= min(open,close) <= max(open,close) <= high` is enforced. |
| `volume` | Base-asset volume. Required. |
| `quote_volume` | Optional; derived as `close * volume` when absent. |

Rules the loader enforces: strictly increasing, unique timestamps (duplicates keep the last row);
**closed bars only** — drop the still-forming final bar before saving, because P1 forbids
repainting. Gaps between bars are fine; nothing assumes a fixed step.

One file = one symbol on one timeframe. Pass the timeframe with `--tf` (`15m 30m 1H 2H 4H 8H 12H
1D 2D 3D 1W`) and use `--venue perp` for perpetual-futures candles, since perp setups must be read
off perp charts (S6-R43).

---

## Getting data

**This container has no exchange access**, and the package is not allowed to fetch anything itself.
`scripts/fetch_klines.py` is a standalone, standard-library-only script you run **on your own
machine** against Binance's or Bybit's *public* market-data REST endpoints. No API key, no account,
no signature, no order placement.

```bash
# Binance spot, 3000 four-hour bars
python scripts/fetch_klines.py --symbol SOLUSDT --tf 4H --bars 3000 --out data/sol_4h.csv

# Bybit USDT perpetual, 5000 one-hour bars
python scripts/fetch_klines.py --venue bybit --market linear --symbol BTCUSDT --tf 1H \
    --bars 5000 --out data/btc_1h_perp.csv

python -m tbot backtest --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT
```

It writes exactly the column set above and drops the unclosed final bar for you.

---

## The execution model, in one paragraph

The corpus contains no execution model, so the harness invents one and makes it pessimistic on
purpose (SPEC.md §12.2 — every assumption is `[OUR CHOICE]`). Detectors are handed
`series.head(i+1)` and never the full frame, and any object they emit that references a bar past
`i` raises `LookaheadError`. Orders armed at the close of bar `i` are first workable on bar `i+1`.
Within a bar the order of evaluation is: trigger entries at the open → resting limits → **the stop**
→ take-profits, so when one bar contains both a stop and a target the stop wins. Limits need a
strict trade-through and fill at their own price with no improvement credited; stops are market
orders that fill at the worse of the stop and the open, with adverse slippage and taker fees; a
same-bar entry and stop is a full loss, not a skipped trade; a trailed stop is live for the
remainder of the bar that trailed it. Fees, slippage and funding are charged inside the P&L before
any metric is computed. Full detail: the module docstring of `tbot/backtest/engine.py`.

---

## The dashboard

```bash
python -m tbot dashboard
```

That is the whole command. It prints a URL — open it in a browser. One process, one port
(8000 by default), no configuration file and no build step.

```bash
# pick your own pairs and timeframes
python -m tbot dashboard --pairs BTCUSDT,ETHUSDT,SOLUSDT --tf 4H,1H

# Bybit instead of Binance
python -m tbot dashboard --source bybit

# no internet? deterministic offline candles, so you can see the whole UI work
python -m tbot dashboard --source replay
```

Five panels: the **chart** (candles with the engine's zones, order blocks, levels, trend lines,
entry ladder, stop and targets drawn on top), the **watchlist** (trend, regime, nearest zone and
how far away it is), **live setups** (trade tickets with per-leg size, R:R, conviction and the
rule IDs behind every number), **rejected** (near-misses grouped by the gate that stopped them,
with counts, so you can see which of your rules is doing the work), and **settings** (pairs,
timeframes and the config keys most worth tuning, applied live without a restart).

Three things worth knowing:

* **It is read-only.** It reads public candle endpoints — no API key, no account, no signed
  request, no order path anywhere in it. `tbot/dashboard/feed.py` is the only module in the
  package that opens a socket; everything else in `tbot` still makes no network calls at all.
* **It analyses closed bars only.** The bar currently forming is drawn on the chart and marked
  as such, and is never handed to the engine — the same no-lookahead rule the backtester
  enforces (SPEC.md §12.1). `tests/test_dashboard.py` proves it.
* **It tells you when it is not live.** A dropped websocket, a rate limit or a stale bar puts a
  banner across the top in words. It will not show you a stale price dressed up as a live one.

---

## Layout

```
bot/
  tbot/
    config.py        245 keys, each with a default and a source ID   (foundation)
    models.py        the SPEC.md §2 data model, Series contract      (foundation)
    primitives.py    P1-P20, the algorithms CONFLICTS.md supplies    (foundation)
    data.py          CSV loading, resampling, the synthetic series   (foundation)
    detectors/       §5 detectors
    confluence.py    §6 scoring          qualify.py   §7 gates
    plan.py          §8 plan builder     manage.py    §9 state machine
    risk.py          §10 risk layer      regime.py    §7.2 macro layer
    backtest/
      engine.py      §12.1-12.3 simulator, no lookahead, full event log
      metrics.py     §12.4 metrics, §12.5 claim-as-hypothesis
    execution.py     §12.6 adapter protocol; live path raises, on purpose
    cli.py           backtest / scan / config / explain / dashboard
    dashboard/       the local web dashboard (the ONLY networked code in the package)
      exchanges.py   Binance/Bybit wire formats — pure, no I/O
      store.py       candle storage; the closed-bar / forming-bar boundary
      feed.py        the only module that opens a socket (public market data)
      analysis.py    cached, throttled, thread-pooled pipeline runner
      serialize.py   PipelineRun -> JSON      gates.py   §7.1 gate wording
      server.py      FastAPI app              static/    the single-page frontend
    INTERFACES.md    the binding foundation contract — read this first
  scripts/
    fetch_klines.py  standalone downloader (NOT part of the package)
  tests/
  configs/default.yaml
```

## Further reading

* [`tbot/INTERFACES.md`](tbot/INTERFACES.md) — the binding contract for anything that touches the
  foundation: the `Series` guarantees, the data model, config-key ownership per module, the
  detector protocol, and the invariants you must not break.
* [`../SPEC.md`](../SPEC.md) — the full specification. §3 is the pipeline order, §11 the config
  reference, §12 the harness requirements, §13 what ships disabled and why, §14 the fifteen open
  questions that block full fidelity.
* [`../CONFLICTS.md`](../CONFLICTS.md) — every contradiction in the source material, how it was
  resolved, and which resolutions are ours rather than his.
