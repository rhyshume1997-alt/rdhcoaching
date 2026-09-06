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
    │   ├── config.py       245 keys, each with default, type, range, source ID and
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
    └── tests/              1,065 tests
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

- 1,065 tests passing (`cd bot && python -m pytest -q`)
- 245 config keys
- Runs end to end on synthetic data; four CLI commands work
- **Never run on real market data.** Not once. This is the single biggest gap.

## Commands

```bash
cd bot
python -m pytest -q                              # 1,065 tests
python -m tbot config                            # every key with its source rule
python -m tbot config --grep stop                # filter
python -m tbot backtest --csv data/synthetic_4h.csv
python -m tbot scan --csv data/synthetic_4h.csv  # trade tickets
python -m tbot explain --run <run.json>          # trace a trade to its rules
python -m tbot dashboard --source replay         # local UI, works offline
python scripts/fetch_klines.py --help            # pull real OHLCV (needs internet)
```

## What's open, in priority order

1. **Run it on real data.** Nothing here has been validated against a real candle.
   `scripts/fetch_klines.py` pulls Binance/Bybit klines. Everything below depends on this.
2. **Sweep `swing_k`** (bracket 2–4). Every structure rule, SFP, fib anchor and order
   block depends on swing detection, and the value is currently a guess. Video evidence
   bounds it at ≤4 but cannot distinguish 2, 3 or 4.
3. **Sweep `sufficient_gap_pct_by_tf`** for 2H/4H/8H/12H. He states 15m, 30m, 1H, 1D and
   2D and skips exactly the range he trades most. Two video passes confirmed the numbers
   do not exist on screen either. Not interpolable — his own slopes disagree by 3×.
4. **Test the 77–82% win rate claim.** Coded as a hypothesis in SPEC §12.5, never tested.
5. **Build `detectors/indicators.py`** — RSI divergence and EMA200 confluence classes.
   The pipeline stage exists and reports itself unavailable rather than silently skipping.

## Traps that have already caught someone

- **Margin vs notional.** "10%" is the margin he commits, not position face value. At 10×
  that's ~100% of equity in notional. Getting this backwards made every trade risk a tenth
  of what it should. See `tests/test_risk.py::TestQ8HisWorkedSizingExample`.
- **R:R basis.** TradingView's position tool measures to the *final* target. Measuring to
  TP1 instead vetoed 27% of valid setups. See F9.
- **Percentages measured over hand-drawings.** Two readings (8.10% on 1H, 26.99% on 4H)
  look like clean thresholds and are measured across sketches, not candles. Both are
  recorded as explicitly rejected in FRAME_FINDINGS.md.
- **Config keys that are declared but never read.** `rr_measured_to` was one; changing it
  did nothing until it was wired. `rr_measured_from` is still inert — harmless today
  because it duplicates `size_and_stop_computed_from`, but don't assume a key is live.

## Scope boundary

Live order execution is out of scope by design, not by omission. If it is ever built it
belongs behind the `ExecutionAdapter` protocol in a separate, separately reviewed package
with its own credential handling, rate limiting, reconciliation and kill switch. Do not
add it to `tbot/`.

The instructor's win-rate claim is a hypothesis to test, never an assumption to build on.
