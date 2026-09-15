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
    │   ├── config.py       251 keys, each with default, type, range, source ID and
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
    └── tests/              1,099 tests
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

- 1,099 tests passing (`cd bot && python -m pytest -q`)
- 251 config keys
- Runs end to end on synthetic data; four CLI commands work
- **Never run on real market data.** Not once. This is the single biggest gap.

## Commands

```bash
cd bot
python -m pytest -q                              # 1,099 tests
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

## Traps that have already caught someone

- **Margin vs notional.** "10%" is the margin he commits, not position face value. At 10×
  that's ~100% of equity in notional. Getting this backwards made every trade risk a tenth
  of what it should. See `tests/test_risk.py::TestQ8HisWorkedSizingExample`.
- **R:R basis.** TradingView's position tool measures to the *final* target. Measuring to
  TP1 instead vetoed 27% of valid setups. See F9.
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
- **Config keys that are declared but never read.** `rr_measured_to` was one; changing it
  did nothing until it was wired. `rr_measured_from` is still inert — harmless today
  because it duplicates `size_and_stop_computed_from`, but don't assume a key is live.

## Scope boundary

Live order execution is out of scope by design, not by omission. If it is ever built it
belongs behind the `ExecutionAdapter` protocol in a separate, separately reviewed package
with its own credential handling, rate limiting, reconciliation and kill switch. Do not
add it to `tbot/`.

The instructor's win-rate claim is a hypothesis to test, never an assumption to build on.
