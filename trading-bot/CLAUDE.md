# CLAUDE.md — project context

Read this before touching anything. It exists so a fresh session doesn't have to
reconstruct eight hours of reasoning from the code.

## What this is

A **trading signal and backtesting system** reverse-engineered from a recorded 8-part
crypto TA course plus one live-analysis walkthrough by an instructor who trades supply
and demand zones. The videos are the source of truth; everything here traces back to
them.

**It does not trade.** There is no exchange client, no API key handling, no order
endpoint anywhere in the package. `tbot/execution.py` is a deliberate wall — read its
module docstring before proposing anything that changes that.

## Layout

```
trading_bot/
├── CLAUDE.md               ← you are here
├── SPEC.md                 the consolidated specification. 14 sections, every rule
│                           carries a source ID. Start here for behaviour questions.
├── CONFLICTS.md            45 reconciled contradictions between sessions, each with a
│                           verdict, reasoning and a config key. Authoritative when
│                           SPEC and a transcript disagree.
├── FRAME_FINDINGS.md       measurements taken from paused video frames (F1–F9).
│                           Distinct from what he *says* — this is what he *does*.
├── CHANGELOG_EVIDENCE.md   which of the 15 open questions got answered, from what
├── QUESTIONS_FOR_TRADER.md the ones still unanswered, phrased to send to him
├── transcripts/            8 auto-caption transcripts, 30-second timestamped blocks
├── extracts/               one rule extract per session, 317 numbered rules
├── answers/                the evidence-mining pass that answered 13 of 15 questions
└── bot/                    the Python package
    ├── tbot/
    │   ├── config.py       252 keys, each with default, type, range, source ID and
    │   │                   (where known) a sweep bracket. THE most important file.
    │   ├── INTERFACES.md   binding contracts between modules. Read before editing any
    │   │                   detector — six agents built these in parallel against it.
    │   ├── primitives.py   P1–P20 + P19b, the shared algorithms
    │   ├── detectors/      levels, trendlines, ranges, zones, orderblocks,
    │   │                   structure, sfp, fibs, patterns
    │   ├── pipeline.py     wires detectors → confluence → regime → qualify → plan
    │   ├── plan.py         entry ladder, stops, TPs, position sizing
    │   ├── manage.py       trade management state machine
    │   ├── risk.py         portfolio caps, concurrency, sizing solver
    │   ├── backtest/       bar-by-bar simulator, no lookahead by construction
    │   └── dashboard/      FastAPI + Lightweight Charts local web UI
    └── tests/              1,138 tests
```

## Conventions that matter

**Provenance is not optional.** Every rule and every config default carries a source ID:

| Marker | Meaning |
|---|---|
| `S2`–`S8`, `TBOT1` | a session transcript, with timestamp |
| `CF-nn` | a reconciled conflict in CONFLICTS.md |
| `Pn` | a primitive algorithm |
| `F1`–`F9` | measured from a video frame |
| `[OUR CHOICE]` / `OUR number` | **he never said this** — an engineering default |

If you add a parameter, it gets a source ID or an explicit `[OUR CHOICE]` marker. Never
invent a threshold and present it as his.

**Confidence labels** on evidence: `stated` (he says the number), `derived`
(arithmetic from a worked example), `inferred` (consistent with behaviour, never said),
`absent` (nothing anywhere).

**Single-source findings ship behind a flag, defaulted off.** See
`zone_wick_band_enabled` for the pattern.

**Never weaken a test to make something pass.** If a test fails because an old default
was wrong, change the default and say so explicitly.

## Current state

- 1,138 tests passing (`cd bot && python -m pytest -q`)
- 252 config keys
- Runs end to end on synthetic data; four CLI commands work
- **Never run on real market data.** Not once. This is the single biggest gap.

## Commands

```bash
cd bot
python -m pytest -q                              # 1,138 tests
python -m tbot config                            # every key with its source rule
python -m tbot config --grep stop                # filter
python -m tbot backtest --csv data/synthetic_4h.csv
python -m tbot backtest --csv data/synthetic_4h.csv --split   # in-sample + out-of-sample
python -m tbot scan --csv data/synthetic_4h.csv  # trade tickets
python -m tbot explain --run <run.json>          # trace a trade to its rules
python -m tbot dashboard --source replay         # local UI, works offline
python scripts/fetch_klines.py --help            # pull real OHLCV (needs internet)
```

## What's open, in priority order

1. **Run it on real data.** Nothing here has been validated against a real candle.
   `scripts/fetch_klines.py` pulls Binance/Bybit klines. Everything below depends on this.
2. **Sweep `swing_k`** (bracket 2–4). Stop looking for his number — there isn't one.
   A written-record pass (CONFLICTS.md, 2026-09-14) established that he defines structure
   *relationally* (HH/HL/LH/LL and which breaks which) and never by a candle count, and
   that he never uses "pivot" as a TA term at all. `swing_k` is our scaffolding for
   finding candidates in code. The sweep decides it. **Run it under `backtest --split`**
   (GAPS.md GAP 1) — an unsplit sweep over two open parameters on one symbol is a
   curve-fitting machine.
3. **Sweep `sufficient_gap_pct_by_tf` — every row, not just 2H/4H/8H/12H.** The five
   "stated" rows are video-only too; no percentage-by-timeframe table exists in writing
   anywhere. He states the gap criterion three times and gives a number zero times.
   Not interpolable — his own slopes disagree by 3×.
4. **Decide what replaces BVOL24H.** The ticker is dead (CF-48). The bot degrades
   gracefully, so `bvol_size_multiplier` silently never halves leverage. Either wire a
   live volatility source or delete the three keys.
5. **The backtest is O(n²) and that blocks the sweep.** `SAMPLE_RUN.md`: ~22 min for
   800 bars, "grows with the square of the series length" — the harness re-runs every
   detector from bar 0 on each bar. Measured: 600 bars ~12 min, 1500 bars ~77 min. A
   sweep over `swing_k` × `sufficient_gap_pct_by_tf` × instruments is days of wall clock
   at that cost. Either cache detector output across bars or the sweep is impractical.
6. **Test the 77–82% win rate claim.** Coded as a hypothesis in SPEC §12.5, never tested.
7. **Build `detectors/indicators.py`** — RSI divergence and EMA200 confluence classes.
   The pipeline stage exists and reports itself unavailable rather than silently skipping.

## Known behavioural gaps (CONFLICTS.md, 2026-09-14)

Found by reading his written notes. Each is a rule he states that the bot does not
implement. None is done.

- **CF-49** a 50%-filled zone is *demoted to plain support*, not killed. The bot has one
  boolean where he has two states.
- **CF-50** the half-candle rule — "1 whole candle and 2 halves is a valid zone".
  `min_zone_bodies` counts whole bodies and rejects zones he accepts.
- **CF-51** "not ever alone" — a zone requires S/R confluence specifically, not three of
  anything.
- **CF-52** funding-rate filter. Doesn't exist in the bot at all.
- **CF-53** never average up unless resistance has flipped to support.

## The first real-data run: what it found (2026-09-14)

600 bars of Bybit SOLUSDT 4H. Equity 10000 -> -660.06. **Not a strategy result** — the
run contains a defect that produces 97.3% of the loss.

**7 of 9 take-profit fills were on the wrong side of the entry.** A long entered at
103.4317 with TP0 at 75.0782 — 27% *below* it. The hit test is `high >= tp.price`, so it
fires on the entry bar and books the loss as a take-profit. Those 7 total −10,370.74 of
the −10,660.06 net.

The split by entry family is perfect:

| family | fill type | n | TP geometry |
|---|---|---|---|
| trigger | market, next bar's open (A5) | 12 | wrong side — all 12 |
| retest | limit, at rung price (A3/A4) | 5 | correct side — all 5 |

Both profitable trades in the run are retest/limit. `select_take_profits` *does* guard the
side (`plan.py:802-806`) but against the **planned** average entry at build time; a trigger
rung then fills wherever the market is and nothing re-validates. T0009's planned entry
back-solves to ~70.80 against the CF-02 notional ceiling; it filled at 103.4317, **46%
away**, and every level inverted at that instant.

**All 17 trades opened and closed on the same bar.** Forced, not inferred: every trade has
`bars_in_trade >= 1` (`engine.py:879` increments before every close path), so the sum is
at least 17; a mean printing as `1.0` caps the sum below 17.85; the sum is an integer.

**The liquidation is a non-event.** T0022's open loss was 1.46 USD against equity of
−630.07. Equity was already negative, and `_check_liquidation` trips on any open loss once
it is. Cost 4.70 USD. The A12 banner is real but points at the aftermath.

**Careful with stop-distance statistics.** The median stop is 22.59% of the *realised*
entry, which looks comfortably wider than the 1.54% median candle — but on the 12 drifted
trades that number is measuring the drift, not the stop. T0009's stop was 1.12% of its
*planned* entry, i.e. inside a typical candle. `stop_buffer_zone_fraction` is not cleared
by that statistic; it needs recomputing against planned entries.

**ROOT CAUSE FOUND — `pipeline.py:972-984`.** Not staleness. The plan geometry is wrong at
construction, confirmed on live data: the dashboard served a SHORT with a planned entry
23.18% below a live price of 103.57, built against the current bar.

```python
# --- G0: is this even a candidate?  A retest is bid *behind* price, never chased.
if setup.entry_family is not EntryFamily.TRIGGER:      # <-- trigger is EXEMPT
    wrong_side = (entry_price > close) if direction is Direction.LONG else (
        entry_price < close)
```

Two defects stacked:

1. **Trigger-family setups skip the gate entirely.** The `is not TRIGGER` guard excludes
   them. Every drifted trade is trigger family; every clean one is retest. 12/12 and 5/5.
2. **The gate tests SIDE, not DISTANCE.** Even for retests, an entry 25% away passes if it
   is on the correct side. Its own veto text — *"would chase the close"* — shows it was
   written to answer "is this a chase?", never "how far away is this?".

**No maximum-distance check exists anywhere in `tbot/`.** Verified three ways: no config
key among the 245 (`sfp_max_close_distance_atr` is SFP proximity, `reentry_max_attempts_
per_level` is a count); no distance-to-entry value gates any decision path; and
`distance_to_entry_pct` exists in exactly **one** place — `dashboard/serialize.py:248`,
rendered at `static/app.js:442-443`. **The number is computed and shown to the user, in
the presentation layer only.** The decision path never sees the figure the UI puts on
screen at −23.18%.

Full chain: gate exempts trigger → trigger entries planned arbitrarily far from market →
they fill at the next bar's open (A5) → stop and TP geometry inverts against the realised
fill → TPs sit behind price and fire instantly. Trigger trades drifted 27–56%.

**Sizing is pinned to a constant, and the call path is why.** `engine.py:430`
(`PlanProvider.__call__(window, config)` carries no portfolio) → `pipeline.py:911-915`
falls back to `PortfolioState(equity_usd=DEFAULT_STARTING_EQUITY)` → `engine.py:132` =
10,000. The constant alone does not show why it never updates; the missing portfolio
argument does. Independently confirmed live: the dashboard printed
`125.634447 x 79.596005 = $10,000.00` from a different code path.

**OPEN DESIGN QUESTION — do not patch this tired.** What is the maximum acceptable
distance from price to entry, and does a trigger plan (a) get vetoed before arming, or
(b) re-derive its stop/TP geometry against the realised fill? Different fixes, different
risk profiles. Picking one at the end of a long day is how a good diagnosis becomes a bad
patch.

**Note added 2026-09-15 — a distance key now exists, and it does NOT close the above.**
The section above is left exactly as written: it is the record of what was true at diagnosis.
Two of its statements have since been overtaken, and one has not.

- *"No maximum-distance check exists anywhere in `tbot/`"* and *"no config key among the 245"*
  — overtaken. `max_entry_distance_pct` (default 15.0, `sweep_bracket` 5.0–27.5) and
  `max_entry_distance_enabled` (default **False**) were added, wired at `G0:entry_too_far`
  beside `anchor_beyond_price`. The key count is now 252.
- **What has NOT changed: the trigger exemption.** The new gate sits *inside the same*
  `if setup.entry_family is not EntryFamily.TRIGGER:` block quoted above. **It would not have
  caught any of the 12 drifted trades** — every one of them is trigger family. It addresses
  defect 2 (side vs distance) for **retests only**. Defect 1, the exemption itself, is
  untouched and is still the open question.
- The threshold is also **still unmeasured against this run**. 15.0 is bounded by ten written
  entry/DCA ladders from the Discord record (CHANGELOG_EVIDENCE.md, DISCORD CHECK 2026-09-15),
  not by the 27–56% drift measured here. Those are different quantities: his ladders describe
  how far *below market* he is willing to bid, not how far a trigger plan may drift from the
  fill. Do not read the 15.0 as an answer to the open design question.

So the open design question at the end of the section above stands unchanged, both halves of
it: the maximum acceptable distance, and whether a trigger plan is vetoed before arming or
re-derives its geometry against the realised fill.

## Traps that have already caught someone

- **Margin vs notional.** "10%" is the margin he commits, not position face value. At 10×
  that's ~100% of equity in notional. Getting this backwards made every trade risk a tenth
  of what it should. See `tests/test_risk.py::TestQ8HisWorkedSizingExample`.
- **R:R basis.** TradingView's position tool measures to the *final* target. Measuring to
  TP1 instead vetoed 27% of valid setups. See F9.
- **A partial fill is UNDER-risked, not over.** Tempting to reason that an adverse realised
  entry (+781 bps in the first real run) breaches the loss cap, because quantity was solved
  from the planned full-fill average. It does not: `qty = qty_total * rung.size_fraction`
  (`engine.py:899`), so an unfilled rung removes its quantity too. Rung 0 alone lands at
  **0.31x** the budgeted loss. Pricing the entry without re-pricing the quantity gets this
  exactly backwards.
- **Percentages measured over hand-drawings.** Two readings (8.10% on 1H, 26.99% on 4H)
  look like clean thresholds and are measured across sketches, not candles. Both are
  recorded as explicitly rejected in FRAME_FINDINGS.md.
- **The consistency check used to compare rungs against the blended average.**
  `check_plan_consistency` started its monotonic ladder walk from the size-weighted
  average rather than from rung 0's price. Latent for months: the old `[0.2, 0.3, 0.5]`
  split put the average at 97.1, coincidentally just above rung 1 at 97.0 in the
  fixtures. Correcting the split to his stated 15/32.5/52.5 moved it to 96.925 and
  exposed it. Fixed, with four regression tests. **Correction to an earlier note here:** it
  did *not* fail in both directions. It falsely rejected valid ladders and misreported which
  rung was at fault, but it never silently accepted an inverted one — a later rung-to-rung
  comparison always caught it. Established by construction, not assumed.
- **`tbot/manage.py` is unreachable.** The whole `TradeManager` state machine is tested
  (`tests/test_manage.py`) and imported by nothing in the package. `engine.py` imports only
  `config` and `models` and reimplements fills, stops and trailing itself. So
  `_reverify_budget` (`manage.py:265`) — written for exactly the case where "after a fill the
  average moved; the stop did not" — has never executed in a backtest. Worse than a dead
  config key: a dead *subsystem* with a green test suite in front of it. Found on the first
  real-data run, 2026-09-14.
- **Config keys that are declared but never read.** `rr_measured_to` was one; changing it
  did nothing until it was wired. `rr_measured_from` is still inert — harmless today
  because it duplicates `size_and_stop_computed_from`, but don't assume a key is live.

## Scope boundary

Live order execution is out of scope by design, not by omission. If it is ever built it
belongs behind the `ExecutionAdapter` protocol in a separate, separately reviewed package
with its own credential handling, rate limiting, reconciliation and kill switch. Do not
add it to `tbot/`.

The instructor's win-rate claim is a hypothesis to test, never an assumption to build on.
