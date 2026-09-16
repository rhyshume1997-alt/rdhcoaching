# GAPS.md — five engineering gaps found by review, 2026-09-15

**Read this before re-deriving any of it.** Five gaps were identified by a review pass. All five
are **our engineering ideas, not rules extracted from the instructor.** None of them traces to a
transcript, a frame or the risk doc. That is the single most important fact on this page, and it
governs how each one ships:

- every new config key carries an explicit `[OUR CHOICE]` marker in its `source_id`;
- every new behaviour ships behind a flag **defaulted off**, with a test asserting that output is
  bit-for-bit identical to today when the flag is off (the `zone_wick_band_enabled` pattern);
- no test is ever weakened to make something pass — if a default was wrong, the default changes
  and the change is stated;
- one gap per commit, full suite green before moving on.

Status legend: `OPEN` · `DESIGN` (proposals written, nothing implemented) · `IMPLEMENTED, NOT OPERATIONAL` (code shipped, dependency missing) · `DONE`.

---

## Read this before counting closed gaps

**Nothing in this file has changed what the bot does.** Three commits of new subsystems are in
and every one of them is inert by default. Counting them as progress would be counting
scaffolding as a building.

| shipped | status | what would make it real |
|---|---|---|
| `max_entry_distance_pct` (CHANGELOG_EVIDENCE.md, DISCORD CHECK 2026-09-15) | off by default; the threshold that would make it useful is **still unmeasured** | the 2026-09-12 resting-entry batch needs spot at post time from bybit to tighten `sweep_bracket`; then a sweep |
| GAP 1 `backtest --split` | **operational** — and the naming defect found by the first OOS run is fixed: `in_sample_fraction` now divides the **analysable** bars, not the raw series, so the delivered share matches the requested one. The header prints both analysable counts. | nothing |
| GAP 2 correlated-exposure cap | **operational in the pipeline, not in the backtest** — A1 landed, and two follow-up defects are fixed: a 3-bar correlation could drive the cap (now floored at `min_correlation_overlap_bars`), and the veto reason stated the *requested* lookback rather than the bars actually measured. `tbot backtest` still injects no portfolio state, so it cannot fire there | a PortfolioState built from the engine's own live trades |
| A1 context channel + `align_series` | **operational** — and it fixed a live defect (`rolling_correlation` correlated misaligned dates, sign-inverting on a periodic path) | nothing |

### The sequencing risk, recorded because it is the thing most likely to be forgotten

**The core strategy has never produced one trustworthy backtest.** Gaps 1 and 2 are defensible
ahead of that: out-of-sample discipline is a *prerequisite* for validation, correlation control
is risk management, and neither touches how a trade is chosen or planned.

**GAP 3 is different in kind: it is a strategy change.** A setup-selection layer ranks plans.
Ranking plans that are themselves wrong produces a confident ordering of broken plans — and it
makes the breakage *harder* to see, because the ranking looks like it is doing work.

So GAP 3 is **designed and not built**, deliberately, and the trigger for building it is not a
date but a result: a backtest that holds positions across bars and places take-profits on the
correct side, on plans whose entries are not drifting far from market. Until that exists,
building the ranker is building on sand. *(The entry-drift and trigger-drift work is tracked
outside this file; this note records the dependency, not its detail.)*

GAPS 4 and 5 are proposal-only for the same reason and have not been started.

---

## GAP 1 — No out-of-sample discipline

**Status:** DONE (2026-09-15). See "What shipped" at the end of this entry.

**What is missing.** There is no walk-forward, holdout or train/test split anywhere in
`bot/tbot/backtest/`. The package is two files, `engine.py` and `metrics.py`, and neither
partitions the series.

**Evidence.**

```
$ cd bot && grep -rniE "walk.?forward|hold.?out|train.{0,3}test|in.?sample|out.?of.?sample" tbot/backtest/
tbot/backtest/metrics.py:35,58,318,324   MIN_SAMPLE_FOR_CONCLUSION   (a 30-trade floor, not a split)
tbot/backtest/engine.py:798              str(...).split(":")[0]      (string split, not a data split)
```

Five hits, none of them a data split. `ls tbot/backtest/` → `engine.py`, `metrics.py`, `__init__.py`.

**Why it costs money.** Two parameters are explicitly queued to be resolved *by sweep* —
`swing_k` (bracket 2–4) and `sufficient_gap_pct_by_tf` (every row) — see CLAUDE.md "What's open"
items 2 and 3. Sweeping two open parameters on one symbol with no split is a curve-fitting
machine: it will return a number, the number will look good, and it will mean nothing. Worse, it
poisons everything downstream — once a fitted `swing_k` is baked in, every later measurement
(the 77–82% win-rate test, any gap below) inherits the overfit and cannot be trusted either.
This is the cheapest gap to close and the one that makes the other four measurable.

**Shipping.** A `--split` flag on `tbot backtest` that partitions the series chronologically
(default 2/3 in-sample, 1/3 out-of-sample) and reports **both segments separately, clearly
labelled, never merged into one headline**. No sweep runner yet — just make the split exist and
be reportable. Without `--split`, output byte-identical to today; both paths tested.

**What shipped.**

- `backtest/engine.py`: `split_backtest()`, `SplitResult`, `SplitError`, and
  `DEFAULT_IN_SAMPLE_FRACTION = 2/3` (marked `[OUR CHOICE]` in the source comment — he has
  never been recorded discussing out-of-sample testing at all).
- `cli.py`: `--split [FRACTION]`, bare flag = 2/3. Two labelled reports, **no combined
  headline** — `SplitResult` deliberately exposes no merged metric, and a test enforces that.
- Contamination vs cold start: the out-of-sample run is handed the **whole** series with
  `warmup_bars` set to the split index. §12.1 already treats warm-up bars as history that
  detectors may read but on which no analysis runs, so the segment gets warmed detector state
  without opening a trade before the split. The lookahead guarantee is untouched.
- `--events` / `--save-run` under `--split` write one suffixed pair per segment
  (`run.in_sample.json`, `run.out_of_sample.json`); the unsuffixed name is not written.
- 12 tests in `tests/test_integration.py`, including the acceptance test
  `test_backtest_without_split_is_byte_identical_to_the_single_run`. Suite 1,075 -> **1,087**.

### The first out-of-sample run (2026-09-15)

`tbot backtest --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT --max-bars 900 --split`,
shipped defaults, nothing tuned. 577s wall clock (predicted ~14 min; inside the ±2× band).

| | in-sample | out-of-sample |
|---|---|---|
| bars | 0–599 | 600–899 |
| **analysable** bars | **100** | **300** |
| closed trades | 1 | 27 |
| equity | 10,000 → 9,984.75 | 10,000 → 9,660.71 |
| net P&L | −15.25 | **−339.29** |
| win rate | 0% (0W/1L) | 37.0% (10W/17L) |
| Wilson 95% | 0.0–79.3% | 21.5–55.8% |
| expectancy | −5.54 R | −7.83 R |

**Neither segment concludes anything.** 1 and 27 closed trades, both under the 30-trade floor,
and both intervals are too wide to separate any hypothesis from any other. The harness says so
itself in both blocks. Out-of-sample is *nearly* at the floor — one more window would reach it.

**A defect in `--split` that this run exposed.** The fraction applies to **total** bars, but the
first 500 bars are warm-up and analysable at all. At 900 bars a "66.7% in-sample" split gives
the in-sample segment **100** analysable bars and out-of-sample **300** — an actual in-sample
share of **25%**, the inverse of what was asked for. The larger segment is the one that is
supposed to be held back.

The split is not *wrong* — it is chronological, disjoint and free of lookahead, and the number
above is real. But **`in_sample_fraction` does not mean what its name says** whenever warm-up is
a large share of the series, and at these sizes it always is. A true 2/3 of *analysable* bars at
n=900 needs `--split 0.85`. Two candidate fixes, neither made yet: measure the fraction over the
post-warm-up region instead of the raw series, or keep the raw-series meaning and report both
numbers so the reader is never misled. **Until that is settled, read any `--split` output by its
analysable-bar counts, which the header prints, not by the percentage.**

**What the −339.29 does not mean.** It is 27 trades in one 50-day window on one symbol, after a
defect fix landed hours earlier, with expectancy dominated by outliers exactly as the 600-bar run
was. It is not evidence about the strategy. What it *is*: the first number this project has
produced where the held-back segment was genuinely held back.

**No sweep runner was added**, as instructed.

**Worth knowing for whoever does the sweep:** the §12.1 default warm-up is **500 bars**. A
2/3 split therefore needs **>750 bars** before the in-sample segment has a single analysable
bar; below that the command refuses with a usage error rather than reporting an empty segment.
`data/synthetic_4h.csv` (800) barely clears it; `data/sol_4h_600.csv` (600) does not.

---

## GAP 2 — No correlation control on concurrent positions

**Status:** OPERATIONAL in the pipeline path (2026-09-15). A1 landed: the gate now assesses real slots and a test drives it end to end through `analyse_bar` — two correlated positions open, a third correlated entry refused at G17, and an anti-correlated book left alone. **Still not reachable from `tbot backtest`**, which injects no portfolio state; see the table at the top of this file.

**What is missing.** `max_concurrent_leverage_global = 4` (`config.py:306`) counts *tickets*, not
*exposures*. Four alt longs in a correlated market is one position with four tickets and four
times the intended risk. Nothing anywhere checks correlation between open positions.

**Evidence.**

```
$ grep -rn "rolling_correlation" tbot/ --include=*.py
tbot/regime.py:75      export
tbot/regime.py:427     def rolling_correlation(a, b, *, lookback_bars=90)
tbot/regime.py:577     rolling_correlation(normalised[DXY_SYMBOL], subject)   ← only caller
$ grep -rniE "correlat" tbot/risk.py
(nothing)
```

The primitive exists and is wired to exactly one thing: the DXY gate. `risk.py`, which owns the
concurrency caps, has never heard of it.

**Why it costs money.** The per-trade risk budget (CF-01, 4% swing) is enforced per ticket. Four
correlated tickets at 4% is a 16% portfolio loss on one market move, not four independent 4%
bets. The cap gives an illusion of diversification that the positions do not have.

**Note on provenance — this matters.** His own stated rule is *"Never more than 2 concurrent
positions"* (risk doc; recorded at `CONFLICTS.md:2305`), which already conflicts with the
`max_concurrent_leverage_global = 4` default from CF-04. **But his reason is not correlation** —
it is margin: four positions leave no margin to fund the DCA legs. Ours is a *different rationale
arriving at a similar limit*. The key must say so. Do not present a correlation cap as his rule.

**Shipping.** `max_correlated_concurrent_enabled` (default **False**), `max_correlated_concurrent`
(default 2), `correlation_threshold` (default 0.7), `correlation_lookback_bars` (default 90). When
enabled, veto a new position if it would exceed the cap among open positions correlated above the
threshold. **Reuse `regime.rolling_correlation` — do not write a second one.**

**What shipped.** `risk.py` gains `correlation_cap_gate()`; the four keys land in group 11.1,
all four marked `[OUR CHOICE]`, and `max_correlated_concurrent`'s note spells out that his
"never more than 2" is a **margin** rule and ours is a different rationale landing near the
same number. `regime.rolling_correlation` is reused; a test asserts `risk.py` contains no
`corrcoef`/`np.cov`/`pearson` of its own.

Called from `pipeline.py` at the CF-04 capacity check — the only place holding both the
portfolio and a per-symbol series map. The enabled-check lives **inside** the gate, not at the
call site: `max_correlated_concurrent_enabled` is `risk.py`'s key and INTERFACES.md §7 lets
only its owner read it. (Reading it in `pipeline.py` broke
`test_pipeline_reads_only_the_keys_it_owns`; the fix was to stop reading it, not to widen the
allow-list.)

**Correlation is signed, not absolute.** Two same-direction positions in anti-correlated assets
partially hedge; an `abs()` would veto the one combination that reduces risk. Tested.

**Two limitations that are real and must not be forgotten:**

1. **`OpenSlot` carries no direction.** A long and a short in the same asset read as
   concentration when they are closer to flat. Conservative for a mixed book, correct for a
   one-way one — and his is one-way (spot accumulation). Fixing it means adding `direction`
   to `OpenSlot`, which touches every caller; deliberately not done in this commit.
2. **The gate is data-starved today.** It can only assess a live slot whose series is present
   in the map it is handed, and `pipeline.ctx.context` carries USDT.D / BTC.D / BVOL, not a
   universe feed. In the current single-symbol harness that is every slot, so the gate would
   assess nothing even if enabled. Unassessed slots are counted and **named in the gate's
   reasons** rather than dropped silently (INTERFACES.md §9.6), so this is visible rather
   than quiet. **This is the same plumbing GAP 3 is about** — GAP 2 only becomes operational
   once a universe feed exists.

12 tests (11 in `tests/test_risk.py`, 1 wiring test in `tests/test_pipeline.py`), including the
acceptance test `test_correlation_cap_is_a_no_op_while_disabled` and a pipeline test proving
rejections and plan ids are unchanged bar-for-bar with the flag off. Suite 1,087 -> **1,099**.

---

## GAP 3 — No relative strength / cross-symbol ranking

**Status:** DESIGN (2026-09-15). Costed below. **Do not build yet** — see the sequencing note at the top of this file.

**What is missing.** The pipeline analyses **one symbol in isolation**. Nothing ranks the
universe, so nothing chooses between symbols.

**Evidence.**

```
$ grep -rniE "relative.?strength|cross.?symbol|benchmark" tbot/*.py tbot/detectors/*.py
(no hits — the only "rank" hits are confluence.rank_clusters, which ranks
 clusters WITHIN one symbol, never symbols against each other)
```

`analyse_bar(series, config, *, context, calendar, portfolio_state, profile, active_symbols, ...)`
(`pipeline.py:1174`) takes **one** `series`. There is already a `context: Mapping[str, Series]`
injection point (`pipeline.py:249`, consumed by `_stage_context_regime` at `pipeline.py:496`) but
it carries USDT.D / BTC.D / BVOL for the §7.2 cross-market *veto* — it is not a universe feed, and
nothing ranks what is in it.

**Why it costs money.** SAMPLE_RUN.md §4: **14,015 candidate rejections across 300 bars on one
symbol**, with 23 plans armed. Choosing between candidates is the actual problem and it is
entirely unaddressed — the bot currently takes whatever passes the gates first, on whatever symbol
it was pointed at. In a real universe that is close to random selection among survivors.

*(The review cited "131 setups from 100 bars"; I could not locate that figure in SAMPLE_RUN.md.
The verifiable equivalents are the 14,015 / 300 / 23 above, which make the same point.)*

**Blocked on a design decision — and on a dependency that is bigger than the decision.**
Designs below, priced. **Nothing implemented.**

---

### A. THE PLUMBING — price this first, it is the shared dependency

GAP 2 is already blocked on this, so it is not Gap 3's cost alone. The headline finding:

> **The harness → pipeline boundary passes two arguments and drops every other injection point
> on the floor.** `default_plan_provider` calls `entry(window.series, config)`
> (`backtest/engine.py:473`). `pipeline.run()` accepts `context`, `calendar`,
> `portfolio_state`, `profile`, `active_symbols` and `ltf_series` (`pipeline.py:1247-1257`) and
> **none of them is ever passed by the harness.** This is not "the universe feed has no data" —
> the channel does not exist.

SAMPLE_RUN.md already records the consequences as live degradation: `:236` *"The §10 portfolio
gates never ran"*, `:251` no portfolio state, `:255` no cross-market context, `:257` no LTF
series. **CF-04 concurrency has therefore never been evaluated in any backtest ever run.**

The work splits into a moderate half and a large half, and they unlock different things.

#### A1 — aligned multi-symbol injection (moderate)

Give the pipeline a `Mapping[str, Series]` truncated to `now`, per bar.

| what | where | why it is not free |
|---|---|---|
| widen `BarWindow` | `engine.py:238-251` — holds exactly one `series`/`symbol`/`tf` | dataclass + every construction site |
| widen `PlanProvider` | `engine.py:430-438` | it is a `Protocol`; tests implement it too |
| populate and pass | `engine.py:473` | the one-line drop that causes all of the above |
| **timestamp alignment** | **does not exist** — `grep -E "def align\|reindex\|common_index"` over `tbot/*.py` returns nothing | symbols list at different dates and have different gaps; bar *i* of SOL is not bar *i* of BTC |
| extend the lookahead audit | `engine.py:~750` audits `plans`/`setups`/`detections` only | one un-truncated series in the map silently leaks the future into a ranking |

**A latent bug A1 must fix on the way.** `regime.rolling_correlation` (`regime.py:433-437`)
takes a **positional** tail — `n = min(len(a), len(b), lookback)` then `a.close[-n:]`,
`b.close[-n:]`. Nothing checks that the two tails cover the same *dates*. With one series today
(DXY) that is merely fragile; with N symbols of differing history it silently correlates
mismatched dates — and it is the primitive GAP 2's cap is built on. Alignment is therefore a
correctness requirement, not a nicety.

**A1 unlocks:** GAP 2 becomes operational; metrics B1, B3 and the benchmark variant of B4.
**A1 does not unlock:** anything that needs N symbols *simulated together*.

#### A2 — N-symbol simulation (large, and gated on something else)

| what | where | why it is expensive |
|---|---|---|
| the loop | `engine.py:728-760` — `BacktestEngine(series, ...)`, `for i in range(n)` over one series | this is the harness's spine |
| the result | `engine.py:1296` — `BacktestResult` is per-symbol (`symbol`, `tf`, `bars`) | metrics, `--save-run`, `explain` and the split all read it |
| the book | `_mark(i, ts, close)` marks one close | one equity curve across N symbols is a different accounting model |
| portfolio gates | never injected today | they would fire for the first time; expect the trade count to move |

**The cost multiplier is the blocker.** *Figures corrected 2026-09-15 — the exponent was
wrong.* Per-bar cost is **O(n^2.2)** measured, so a full run is **O(n^3.2)**, not O(n²)
(CLAUDE.md open item 5 carries the seven-point curve). ~14 min at 900 bars, **~85 min at 1500**,
each **± roughly 2×** because cost depends on which bars as well as how many — 0.757s vs 1.338s
per bar at identical window length on different data. Multiply by N symbols. **A2 is hostage to
that cost and should not be attempted before it.**

Note what the fix is *not*: caching the ATR array was measured and rejected — it is rebuilt once
per bar, 0.5 ms inside a 9.8 s bar. The cost is `trendlines.py` `_touches`, O(P³) pairwise pivot
geometry. And the **sweep** is not blocked by any of this: 30 configs are 30 independent
processes at ~122 MB each on 10 physical cores, blocked only by free RAM.

#### A3 — what already exists and must not be rebuilt

`dashboard/store.py` `MarketData` is a working per-`(symbol, tf)` registry with `.get()` and
`.series(...)`, fed live, capped at 24 pairs (`dashboard/settings.py:89`). **The universe data
structure already exists.** What the dashboard does *not* do is the cross-symbol call:
`dashboard/analysis.py:192` runs `pipeline.analyse_bar(series, config)` **per symbol,
independently, with no context** — the same two-argument call the harness makes.

So the missing pieces are narrower than "build a universe feed": (a) a backtest-side loader for
N CSVs, (b) the alignment helper, (c) the call site that hands the map down. (a) and (c) are
small; (b) is the real work and is shared.

---

### B. THE METRIC — cheap once A1 exists, and one is cheap today

Costed against A, not from zero. **Provenance first, because it is not clean:** relative
strength is *not* absent from his thinking. The Discord record has him rotating into it
explicitly — *"Don't ask me why but I am following strength"* (ICP, 2025-11-06) and *"The
strength clearly is in privacy coins/narrative"* (2025-11-04). But he never mechanises it: no
lookback, no benchmark, no threshold, no ranking rule anywhere in eight transcripts or the
written record. **The idea has weak behavioural support; every number in every option below is
ours.**

#### B1 — performance vs a benchmark (BTC) over N lookbacks

Return over *k* bars minus BTC's return over the same *k*, for a few *k*, combined into one
score.

- **Needs:** A1 only, and only **one** extra series. Not the N-symbol engine — each symbol is
  scored against BTC independently, so it works inside today's single-symbol run.
- **Cost:** smallest of the three that are actually cross-symbol.
- **Weakness:** it measures momentum, not setup quality. It is a *filter* ("is this symbol
  leading?"), not a *selector* ("which of these two setups do I take?"). It cannot rank two
  symbols against each other at one instant unless something compares their scores — see B2.
- **Sweep surface:** the lookback set and the combination weights. Both entirely ours.

#### B2 — position within its own recent range

Percentile of close within the trailing *N*-bar high/low.

- **Needs:** **nothing.** It is a primitive over the subject series alone. Computable today, no
  plumbing at all.
- **Cost:** near zero to compute. But *ranking* on it needs somewhere to compare N scalars —
  which is a far smaller piece than A2: a scalar per symbol per bar, not N series through the
  pipeline. That comparison point does not exist either, but it is cheap to add once A1's call
  site exists.
- **Weakness:** it is not cross-symbol at all on its own, and it is close to information the
  pipeline already has — `detectors/ranges.py` computes ranges and `classify_price` already
  places price within one. Risk of re-deriving an existing object under a new name.
- **Honest read:** this is the one that could ship first and prove the ranking *call site*
  without paying for A1. That may be its real value.

#### B3 — structure divergence vs the benchmark

Subject is making HH/HL while the benchmark is not.

- **Needs:** A1, plus running `detectors/structure.py` on the benchmark series each bar.
- **Cost:** roughly doubles per-bar structure work. No new algorithm — `structure_state` and P11
  are reused wholesale.
- **Strength:** the most *his-method-shaped* of the three. He reasons in HH/HL constantly, and
  it composes with the existing trend machinery rather than bolting a new indicator on.
- **Weakness:** binary and coarse. It separates "diverging" from "not" and gives no ordering
  within either bucket, so it filters well and ranks badly.

#### B4 — behaviour on the last market-wide down day (listed, costed, not recommended alone)

- **Benchmark-only variant:** needs A1. **Breadth variant** (how many of N fell) needs full A2.
- **Weakness that rules it out as a primary:** event-sparse. On a few hundred 4H bars there may
  be a handful of qualifying days, so the metric is low-resolution andimpossible to sweep
  meaningfully. Better as a *tiebreak* on top of B1 than as the ranking itself.

---

### The shape of the recommendation

**A1 only, B1 or B3 on top, A2 not until the per-bar cost comes down.** B2 is the cheap
experiment that proves the ranking call site without paying for A1 first. *(2026-09-15: "the
O(n²) fix" was the wrong name for it — the real curve is O(n^3.2) total, and the target is
`trendlines.py` `_touches`, not a data-layer cache.)*

But see the sequencing note at the top of this file: **none of this should be built yet.**

---

## GAP 4 — No chop / regime filter

**Status:** OPEN — design proposals first, no code.

**What is missing.** No trend-strength or ranging measure exists anywhere.

**Evidence.**

```
$ grep -rniE "\bchop|choppy|adx|trend_strength|ranging|rotational|efficiency.?ratio|whipsaw" tbot/ --include=*.py
tbot/dashboard/gates.py:69       prose in a gate description
tbot/detectors/ranges.py:151     prose in a docstring
```

Two hits, both English, neither a measure. Nothing computes how trending or how rotational the
market is.

**Why it costs money.** Supply/demand zones behave in opposite ways depending on regime: they
hold in rotational markets and get run straight through in trending ones. The bot cannot tell the
two apart, so it applies one zone policy to both. His own rule — *"When it is choppy, do not
trade"* — is unimplemented, which means the corpus supports *having* a filter even though it
supports no particular **measure**. The measure will be ours; say so on the key.

---

## GAP 5 — Volume is only a liquidity screen

**Status:** OPEN — evidence search first, then a human decision.

**What is missing (as reviewed).** Volume is a universe filter and a wick screen; no detector uses
it to confirm anything. A zone formed on a volume spike and one formed on dead volume are the same
object to the bot.

**Evidence — and one correction to the review's premise.** The claim "no detector uses it to
confirm anything" is **too strong**. Volume is load-bearing in three places, not one:

| where | what it does |
|---|---|
| `config.py:2624` `min_daily_volume_usd` | universe liquidity filter (as reviewed) |
| `primitives.py:1088–1090`, key `capitulation_volume_mult` (2.0) | **P12 capitulation wick requires `volume >= 2.0 × median(volume, 20)`** — a genuine confirmation condition, consumed by `detectors/sfp.py:430` and `plan.py:442` |
| `primitives.py:462–471`, `levels.py:369` | level cluster price is the **volume-weighted mean** of member pivots |

What *is* absent, confirmed:

```
$ grep -rniE "volume" tbot/detectors/{zones,orderblocks,structure,ranges}.py
(nothing)
```

**Zone and order-block formation quality ignores volume entirely.** That is the real gap, and it
is narrower than stated.

**Why it costs money.** Zone strength is currently a function of geometry and touch count only.
If formation volume separates zones that hold from zones that fail, the bot is discarding a free
discriminator on its single most important object.

**Before proposing anything.** This may be a gap in **his method**, not in the extraction. Raw
counts: `volume` appears 21× in `transcripts/` and 33× in `extracts/`. Those counts are not an
answer — they have not been read in context, and `capitulation_volume_mult` already shows at least
one volume rule was extracted. GAP 5's first action is to read those hits and report plainly
whether he uses volume as a confirmation signal. **If he never does, say so plainly** — then it is
ours to invent or to deliberately leave alone, and that is a decision for a human, not for this
file.

---

# THE FIRST VERDICT RUN — 1,500 bars, out-of-sample, 2026-09-15

Run on `68759b3` via `tbot backtest --csv data/sol_4h.csv --tf 4H --symbol SOLUSDT --split`,
shipped defaults, nothing tuned, no `--set` flags. The CLI builds its config through
`Config.load`, so this run used the corrected `dca_size_split_3` and `tp_count_swing` values
(see `f6b267c`) and is unaffected by the defaults defect found the same evening.

**This is the first run in this project with enough trades on both sides to conclude anything.**
Every earlier number was measured either through `pipeline.py:972` before it was fixed, or on a
sample below the 30-trade floor.

## The numbers

| | in-sample | out-of-sample |
|---|---|---|
| analysable bars | 667 | 333 |
| date range | 2026-01-07 -> 2026-07-20 | 2026-07-20 -> 2026-09-14 |
| closed trades | 77 | **35** |
| win rate (net P&L > 0) | 57.14% (44W/27L/6BE) | **37.14%** (13W/22L) |
| 95% Wilson | 46.0% - 67.6% | 23.2% - 53.7% |
| net P&L on 10,000 | **-639.02** | **-483.28** |
| expectancy | -0.3847 R | -2.5637 R |
| mean win / mean loss (USD) | +29.13 / -77.02 = **0.38:1** | +20.53 / -34.10 = **0.60:1** |
| full TP-ladder completion | 1 of 77 | **0 of 35** |
| max drawdown | 11.55% | 6.02% |
| close reasons | trail_out 49, stop 27, tp_final 1 | stop 19, trail_out 16 |

## The answer to the question this run was built to ask

**No. This rule set, as extracted and as currently implemented, does not show edge
out-of-sample on SOL 4H.** 35 closed trades is above the floor, so this is a result and not a
shrug. Both segments lose money.

It also loses **in-sample**, which removes the usual overfitting story: nothing has been fitted
to this data (no sweep has ever been run), and a rule set that loses on the segment it could
have been fitted to is simply losing.

Per SPEC.md 12.5 this is a result and must not trigger fitting toward the 77-82% claim. The
claim remains what CONFLICTS.md already ruled it: a recollection with no sample and no win
definition, not usable for validation.

## Why it loses — both halves are measured, not inferred

**Winners are truncated.** The TP ladder completed once in 112 trades. `tp_residual_policy =
trail_out` (CF-28) with `trail_on_tp1 = break_even` (CF-29) means a trade that tags TP1 and
reverses books a partial plus a break-even remainder. Both are sourced rules working as
specified.

**Losers overrun.** 27 of 77 in-sample and 19 of 35 out-of-sample came in worse than -1R.

Together the dollar win/loss ratio is 0.38:1 and 0.60:1. Break-even needs roughly 0.75:1 at a
57% win rate and 1.70:1 at 37%. The gap is not marginal.

## The stop-distance defect is structural, confirmed at n=77 and n=35

The dollar value of 1R - `|net_pnl_usd / r_multiple|`, which is
`|realised average entry - initial stop| x filled qty` - spans:

    in-sample       min 1.2699   median 57.139   max 368.35    290x
    out-of-sample   min 0.2347   median 25.322   max 118.63    505x

The earlier 2,167x was measured on 27 trades and could have been a small-sample artefact. It is
not. Risk-first sizing is supposed to make 1R a constant; it varies by two and a half orders of
magnitude, so **`expectancy_R` aggregated across these trades remains meaningless and USD must
be read first.**

`min_stop_pct = 0.5` (CF-06, S7-C8, SOURCED) exists and is implemented at `plan.py:576-583`, but
is checked against the **planned** entry, and `plan.py:585-591` deliberately lets an
opposing-level clip land back inside the floor. Neither is re-checked against the price actually
paid. That fix is not in this run.

## What this verdict does and does not license

It **does** say: the rule set as it stands today is not tradeable on this symbol and timeframe,
and no amount of parameter sweeping should be started on the strength of hope.

It does **not** say the extraction is wrong, or that the method does not work for him. Confounds
that remain open, none of them resolved here:

- the `min_stop_pct` defect above, which is a bot bug and not his rule
- one symbol, one timeframe, eight months, one market regime
- CF-49 to CF-53, five stated rules still unimplemented
- trigger rot: on the earlier 900-bar window, 12 of 17 trigger plans were geometrically invalid
  by the time they filled, and why plans rot between arming and filling is undiagnosed

The honest next step is to fix the stop-distance defect and re-run this exact command, so the
before and after differ by one change. Not to tune anything.

---

# WHY 1R IS NOT CONSTANT: the CF-02 ceiling replaces risk-first sizing, 2026-09-16

Risk-first sizing solves `qty = loss_budget / |stop - entry|` so that every trade risks the same
money. It is not in force. The CF-02 notional ceiling clamps the notional, and
`plan.solve_size` **re-solves quantity from the clamped notional** (`risk.py`, `max_notional`
docstring), so whenever the ceiling binds the quantity is fixed and **risk floats with stop
distance instead**.

Derived from the shipped config, at 10,000 equity and a 100-price instrument:

| stop % of entry | risk-first qty | notional | ceiling binds | actual risk | vs 400 budget |
|---|---:|---:|---|---:|---:|
| 0.002 | 200,000 | 20,000,000 | YES | 0.20 | 0.05% |
| 0.5 | 800 | 80,000 | YES | 50.00 | 12.5% |
| 1.0 | 400 | 40,000 | YES | 100.00 | 25% |
| 2.0 | 200 | 20,000 | YES | 200.00 | 50% |
| **4.0** | 100 | 10,000 | **no** | 400.00 | **100%** |

**The ceiling binds for every stop tighter than 4.00% of entry.** *Corrected 2026-09-16:* an
earlier draft of this paragraph said it therefore binds "on essentially every trade", reasoning
from the 0.549% median stop. Measured on 112 trades it binds on **28 of 77 in-sample and 17 of 35
out-of-sample** - 36% and 49%. The threshold is right; the inference from it was not, because a
partial ladder fill buys less than the full quantity and drops the notional back under the
ceiling. That is the same bimodality reported below (14 at exactly 10,000, 13 at ~2,500). `max_loss_pct_swing = 4.0` is unreachable except
at exactly a 4% stop.

Corroborated by measurement, not only by arithmetic: on the 27-trade sample implied notional is
bimodal and both modes are exact - 14 trades at **exactly 10,000** (the ceiling, binding) and 13
at ~2,500 (partial ladder fills). Per-trade risk across that book runs 0.21 to 118.63 USD, 565x.

## This has happened once before, in the same function

`max_notional`'s own docstring records it: when the leverage row held 10.0 - his *margin*
percentage enforced as a *notional* ceiling - it "silently capped every leverage trade at roughly
0.7 % portfolio risk instead of the 4-5 % the CF-01 ladder assigns". Raising the row to 100%
moved the binding threshold from 0.4% to 4.0%. **It did not remove the mechanism**, and nothing
reports when the ceiling is what decided a trade's size.

## The number that ties it to his method

His worked sizing example accepts **$729 notional on a $1,000 portfolio, 72.9%** (Q8, S6
`[00:08:36]`-`[00:11:27]`). At a 4% risk budget that implies a stop around **5.5%** of entry.
The bot's median stop is **0.549%** - an order of magnitude tighter. `min_stop_pct = 0.5`
(CF-06, S7-C8) exists precisely to stop that, and the CF-14 step 3 clip undoes it
(see the clip/floor interaction above).

So the three findings are one finding:

1. the CF-14 clip pulls stops back inside the sourced CF-06 floor, and nothing re-checks
2. stops an order of magnitude tighter than his method implies
3. the CF-02 ceiling turns those tight stops into tiny positions, so risk varies 565x and the
   4% budget is never spent

## What this does NOT establish

Whether the ceiling, the floor, or the stop placement is the thing to change. That is a design
decision about which sourced rule gives way, and it is not ours to take. It also does not say
the book would be profitable with constant risk - the verdict run lost money on both segments,
and a dollar re-scoring of the 27-trade sample shows the best available stop gate takes the book
from -404 to -75, still negative.

**The reporting guard (step 4) should therefore report implied notional and the count of
ceiling-bound trades, not only the dispersion of `initial_risk_usd`.** The dispersion is the
symptom; the ceiling is the cause, and a guard that reports only the spread invites someone to
treat the spread as the thing to fix.


---

# WHICH STOP GATE, SCORED IN DOLLARS ON 112 TRADES, 2026-09-16

Run `1c87d11` over 1,500 bars with `--split`, then every closed trade bucketed by which gate
would refuse it. **Dollars, not R.** R is circular here - 1R *is* the stop distance, so a
tight-stop trade shows a catastrophic R whatever price did, and ranking gates by the R of their
refusals ranks them by how tight those stops were. That is the question, not the answer.

    build gate   refuses when the PLANNED  stop is inside min_stop_pct (visible at build)
    fill  gate   refuses when the REALISED stop is inside min_stop_pct (only visible at fill)

| | in-sample (n=77, book -729.43) | out-of-sample (n=35, book -483.28) |
|---|---|---|
| both | 10 / **-310.57** / mean -31.06 | 13 / **-341.02** / mean -26.23 |
| build only | 26 / **+339.81** / mean +13.07 | 12 / **+96.55** / mean +8.05 |
| fill only | **0** | **0** |
| neither | 41 / **-758.67** / mean -18.50 | 10 / **-238.81** / mean -23.88 |
| build gate | refuses 36 -> book **-758.67** | refuses 25 -> book -238.81 |
| fill gate | refuses 10 -> book **-418.86** | refuses 13 -> book **-142.26** |
| notional at the CF-02 ceiling | 28 of 77 | 17 of 35 |

## Four findings

**1. The build-time gate refuses the only profitable bucket, in both segments.** "build only" -
planned stop inside the floor, realised stop outside it because the fill drifted away from the
stop - is +339.81 and +96.55, positive mean in each. It replicates out-of-sample, so it is not a
small-sample accident. In-sample the build gate is **actively harmful**: it removes +29.24 of
profit and takes the book from -729.43 to -758.67.

**2. "fill only" is empty in both segments, so the two gates are NESTED, not orthogonal.** Every
sub-floor realised stop was already sub-floor at build. The fill gate refuses exactly the `both`
bucket, a strict subset of the build gate's refusals: **the fill gate is the build gate minus the
profitable bucket.** An earlier framing called these "two different seams" on the strength of a
single fill-only trade (T0049) in a 27-trade window; that trade does not recur in 112 and the
framing does not survive. Build-time and fill-time may still be different seams in principle -
a plan can be sound and its fill ruinous - but on this data that case occurs once in 112.

**3. The fill gate wins in both segments** (-729 -> -419 and -483 -> -142) and the advantage
replicates out-of-sample, which is the test that matters.

**4. The money is in `neither`.** 41 trades and -758.67 in-sample, 10 and -238.81 out-of-sample.
**No stop gate touches the majority of the loss.** This gets stronger at n=112, not weaker.

## What this licenses

Build the **fill-time gate only**. It is strictly better in both segments, it cannot refuse the
profitable bucket because it is a subset, and it needs no invented number - `min_stop_pct = 0.5`
is CF-06, S7-C8, his. The build-time gate has now been measured as value-destroying in-sample and
inferior out-of-sample; shipping it even defaulted off would be shipping something measured
harmful.

## Caveats that govern all of the above

- **This is arithmetic on a closed book, not a re-simulation.** Refusing a trade changes equity,
  concurrency and portfolio state, so the true effect needs the gate built and the backtest
  re-run. It directs the build; it is not a result.
- The `widened` flag in this run is stale: the run was launched at `1c87d11`, before `7044e75`
  removed the reset that erased the flag whenever a clip fired, so clipped trades under-report.
  The bucketing does not use that flag - it uses planned and realised distances - so the buckets
  are sound and only that column is unreliable.
- One symbol, one timeframe, one regime.
- **The best available gate takes out-of-sample from -483 to -142. Still negative.** No stop gate
  found here makes this system profitable.

---

# The fill-time gate as built refuses 2 of the 23 trades it was built for

Measured on the `--split` 1,500-bar run written at `95b6d01` (flag absent, therefore flag-off;
identical book to the `3dbf33b` verdict run). Everything below is measured from that run file.

## First, the existing table above is confirmed, not corrected

An earlier instruction to me said the four-bucket table "predates `7044e75` and has a stale
`widened` column". That instruction was confused, and I carried the confusion. **The table above
never used the `widened` flag** - its own caveat says so: it buckets on *planned distance* vs
*realised distance*. Recomputed on a run that postdates `7044e75`, it reproduces to the cent:

| | in-sample | out-of-sample |
|---|---|---|
| both | 10 / -310.57 | 13 / -341.02 |
| build only | 26 / +339.81 | 12 / +96.55 |
| fill only | 0 | 0 |
| neither | 41 / -758.67 | 10 / -238.81 |

Bucketing instead on *did the CF-06 widen actually fire* answers a different question and gives a
different table. Neither is wrong; they are not the same question, and the difference is not a
correction of one by the other:

| | in-sample | out-of-sample |
|---|---|---|
| both (widen fired AND realised inside) | 0 | 0 |
| build only (widen fired) | 2 / -125.00 | 3 / -187.67 |
| fill only (realised inside, widen never fired) | 10 / -310.57 | 13 / -341.02 |
| neither | 65 / -293.86 | 19 / **+45.40** |

`widened` and `clipped` never co-occur in 112 trades, which is why the `both` cell is empty under
the flag bucketing: where the step-3 clip fires it supersedes the widen, so only one flag is ever
set. **The 23 trades in question are the same 23 under either bucketing** - table A calls them
`both`, table B calls them `fill only`.

## The finding: the gate checks the wrong price, and it is not a marginal miss

`_fill_limit_rungs` calls `_fill_floor_problems(trade, price)` with `price = rung.price`, and the
gate returns `()` once `filled_qty_total > 0`. So it runs **once, against rung 0**, never against
the blended average. That is defensible as written - at the first fill, rung 0 is the only price
actually paid - but rung 0 is, by construction, the price **furthest from the stop**:

    long:   d(p) = (p - s) / p = 1 - s/p     increasing in p, and rung 0 is the highest rung
    short:  d(p) = (s - p) / p = s/p - 1     decreasing in p, and rung 0 is the lowest rung

Either way `d(rung 0) >= d(average)`, so the gate can only ever refuse a **subset** of what the
closed-book arithmetic refused. Measured, the subset is almost empty - rung 0 clears the floor on
21 of the 23:

| ref | rung 0 | average | d(rung 0) | d(average) | gate | R |
|---|---|---|---|---|---|---|
| IS T0055 | 90.0186 | 89.6028 | 0.4925% | 0.0308% | **refuse** | -5.06 |
| OOS T0039 | 76.3464 | 76.3464 | 0.4271% | 0.4271% | **refuse** | -1.29 |
| IS T0013 | 82.1479 | 83.9163 | 2.6076% | 0.4453% | miss | -1.28 |
| IS T0002 | 88.1333 | 89.0361 | 1.0372% | 0.0127% | miss | -10.85 |
| OOS T0084 | 103.2757 | 104.1270 | 0.8267% | **0.0023%** | miss | **-54.26** |

...and 18 more, all `miss`. **The gate refuses 2 of 23.** The worst trade in the dataset - OOS
T0084 at -54.26R, a stop 0.0023% from the average - has a rung 0 sitting 0.8267% away, comfortably
clear of the floor, so the gate waves it through.

**Prediction, recorded before the confirming run finishes:** the flag-ON re-simulation will log
**2 refusals**, not the 23 the closed-book arithmetic implied, and the out-of-sample book will
move from -483.28 by roughly the -1.29 of OOS T0039, not to -142.26. `neither` and `build only`
cannot contribute refusals: their realised distance is already >= the floor, and d(rung 0) is
larger still.

## The real mechanism is the ladder, not the floor

What actually distinguishes those 23 trades is not stop width. It is that **22 of 23 filled a DCA
rung on the far side of their own stop** - adding size at a price where the position was already
invalidated:

| bucket | filled 2+ rungs | had a filled rung beyond the stop |
|---|---|---|
| build only (n=5) | 2 | **0** (0%) |
| fill only (n=23) | 22 | **22** (96%) |
| neither (n=84) | 7 | 4 (5%) |

IS T0013 is the whole mechanism in one trade, all on bar 543: rung 0 (entry) fills 29.79 @ 82.1479;
rung 1 (dca) fills 89.37 - three times the size - @ 84.5058, which is **past the stop at 84.2900**;
the average lands at 83.9163, i.e. 0.4453% from the stop; the stop fills on the same bar.

`place_stop` already owns this principle and states it in prose - it takes `beyond_price=
_ladder_extreme(rungs)`, documented as *"A stop that does not invalidate the whole ladder is not a
stop"*. But that guard governs **only the F6 zone-fraction branch**, and the CF-14 step-3 opposing-
level clip runs afterwards and re-creates exactly the condition the guard exists to prevent. All
23 of these trades were clipped (100%); clipping alone predicts nothing (91-100% of `neither` was
clipped too); what predicts the disaster is a clip that lands **inside the ladder**.

## What this does and does not license

It does **not** license a code change. The resolution is a genuine rule choice with at least three
defensible answers - drop the rungs beyond the clipped stop, let the clip stand down as the F6
branch already does under `beyond_price`, or take the trade as now - and the sources pick none of
them. CF-14 step 3 is a hard stated rule and it wins on stop placement; nothing in the source says
what happens to a ladder the clipped stop no longer invalidates. **This is the same class of
decision as CF-28/CF-29 and it waits for Rhys.**

What it does establish:

- The closed-book figure **-483 -> -142 does not survive contact with the code**. That number
  assumed a gate on the realised blended average; the gate that exists is on rung 0. Any statement
  of that improvement, in this file or elsewhere, is retired.
- `min_stop_pct_enforced_at_fill` (`b88351e`) is honest about what it does and is ~9% effective
  against the population it was aimed at. It ships `False` and is left in place, documented here.
- Out-of-sample, the 19 trades in `neither` made **+45.40** with 13 winners. The entire -483.28
  out-of-sample loss is the 16 gated trades. In-sample `neither` is still -293.86, so this does
  **not** say the rest of the system is profitable - one segment, n=19, below the 30-trade floor.

## The narrow question is answered: there is no second mechanism

Within `neither` - normal-stop trades only - losers stop at about -1R and nothing overruns:

| | losers | mean R | median R | min R | worse than -1.05R | close reasons |
|---|---|---|---|---|---|---|
| in-sample | 16 | -1.066 | -1.087 | -1.271 | 14/16 | stop 15, trail_out 1 |
| out-of-sample | 6 | -0.640 | -0.152 | -1.256 | 3/6 | stop 3, trail_out 3 |

The overrun is fees and slippage on top of -1R, not an unnamed defect. Every trade in the dataset
worse than -1.5R - 7 in-sample, 10 out-of-sample, **17 of 17** - sits in the 23. So the remaining
problem inside normal-stop trades is purely the payoff ratio: `neither` wins 62 of 84 and still
loses money, which is CF-28/CF-29 truncating winners, already documented above.

## A reporting trap this run exposed

In-sample `expectancy_r` is -0.385 and out-of-sample is **-2.564**, driven by losers averaging
-4.412R. Both are artefacts: OOS T0084 risked $0.23 and lost $12.48, which is -54.26R. Meanwhile
`initial_risk_usd` spans $0.23 to $368.35 - a 505x spread - so R is not a common unit across
trades and summing it is not meaningful. In `neither`, expectancy is **+0.096R but -2.96 USD**:
positive in R, negative in dollars. **Read dollars first.** This is the case for the §12.5
reporting guard, which is still unbuilt.

Also: in-sample headline net P&L is -639.02 but the closed book is **-729.43**. The report
discloses why - `1 position(s) still open at the end: excluded from the closed-trade metrics` -
and the +90.41 difference is that position's unrealised mark. Out-of-sample has none open, so the
two segments' headline numbers are not like for like.

## Confirmed by re-simulation: the prediction held exactly

Both 1,500-bar `--split` runs at `b88351e`, identical but for the flag.

|  | OFF | ON | delta |
|---|---|---|---|
| IS closed trades | 77 | **76** | -1 |
| IS headline net | -639.02 | -623.45 | +15.57 |
| IS closed book | -729.43 | -713.86 | +15.57 |
| IS win rate (def. 1) | 57.14% (44W/27L/6BE) | 57.89% (44W/26L/6BE) | +0.75pp |
| IS expectancy | -0.3847 R / -9.47 USD | -0.3232 R / -9.39 USD | |
| OOS closed trades | 35 | **34** | -1 |
| OOS net | -483.28 | **-428.12** | +55.16 |
| OOS win rate (def. 1) | 37.14% (13W/22L) | 38.24% (13W/21L) | +1.10pp |
| OOS expectancy | -2.5637 R / -13.81 USD | **-2.6011 R** / -12.59 USD | |

**Two refusals, and they are the two named in advance** - IS T0055 (rung 0 at 0.4925%) and OOS
T0039 (0.4271%). Nothing else changed: **zero surviving trades moved P&L in either segment**, so
the caveat that refusing trades reshuffles equity and concurrency did not bite at this size. The
removals are clean subtractions of -15.57 and -55.16.

The OFF run also reproduces the pre-flag book to the cent (-729.43 / -483.28), which is
`b88351e`'s bit-identical-while-disabled property confirmed on real data rather than on a fixture.

**The predicted improvement was 2 trades; the closed-book arithmetic had implied 23. Out-of-sample
moved -483.28 -> -428.12, not -483 -> -142.** The estimate overstated the gain by about 6x.

### The R trap, caught in the act

Out-of-sample `expectancy_r` got **worse** when a losing trade was removed: -2.5637 -> -2.6011,
while `expectancy_usd` improved -13.81 -> -12.59. T0039 risked $42.71 and lost 1.29R, so deleting
it *raised* the average |R| of the losers that remain - several of which risked under $6 and so
score -3R to -54R on losses of a few dollars. A number that moves the wrong way when the book
improves is not an expectancy. **Dollars are the headline; R is diagnostic only.** This is now a
worked example for the unbuilt §12.5 reporting guard, not a hypothetical.

### The verdict is unchanged

Out-of-sample: **34 trades, 38.24%, -428.12.** In-sample: **76 trades, 57.89%, -623.45.** Both
segments still lose, in-sample still loses, and the best stop gate measured in this package moves
out-of-sample by 11%. **No out-of-sample edge, and no stop gate found here creates one.**

## Where the money actually goes: partition by mechanism, not by hypothetical gate

The two tables above tell **opposite stories about `neither`**, and that needs saying plainly
rather than leaving both on the page:

    table A (planned vs realised distance)   neither = 51 trades   -997.48
    table B (the CF-06 widen flag)           neither = 84 trades   -248.46

The entire disagreement is one bucket. Table A isolates 38 trades - planned stop inside the floor,
realised stop outside it - into their own cell, where they are **+436.36** (IS +339.81, OOS +96.55).
Table B has no cell for them and folds them into `neither`. Nothing else differs: A's `both` is
B's `fill only`, the same 23 trades, and 51 + 38 - 5 = 84.

So "the money is in `neither`, stops are a sideshow" was an artefact of reading table A, and the
opposite reading is an artefact of table B. **Both tables partition by which hypothetical gate
would refuse a trade. Neither partitions by cause**, so neither answers "where does the money go".

Partitioning by the measured mechanism does - did a filled rung land on the far side of this
trade's own stop:

| | trades | share | net USD | share of loss | wins |
|---|---|---|---|---|---|
| a filled rung beyond its own stop | **26** | 23% | **-958.95** | **79%** | **0** |
| clean ladder | 86 | 77% | -253.76 | 21% | 62 |
| | 112 | | -1,212.71 | | 62 |

In-sample 13 trades / -602.63, out-of-sample 13 / -356.32. **Zero winners in 26, across both
segments.** This is the sharpest statement available from this data and it supersedes both
tables for the purpose of ranking what to fix.

Two things follow that the floor-based bucketings could not show:

- **The floor lens undercounts the mechanism.** 22 of the 26 sit in `fill only`; the other **4
  carry -362.52** (3 in-sample at -292.06, 1 out-of-sample at -70.46) and are invisible to every
  stop-floor bucketing, because their blended average still cleared 0.5% while a rung had already
  filled past the stop. One `fill only` trade conversely had no such rung. The floor is a proxy
  for the mechanism, and a lossy one.
- **The correct figure for the clip-inside-ladder population is -651.59 over 23 trades** (or
  -958.95 over 26 on the mechanism partition). **-964.26 is the 28-trade total** and includes the
  5 `build only` trades at -312.67, which are a different population - none of them filled a rung
  beyond its stop. An earlier summary of mine attributed the 28-trade total to the 23-trade
  bucket, overstating it by 48%. That number never entered this file; it is corrected here so the
  record contradicts it explicitly.

### The one-line diagnosis

`place_stop` runs anchor -> F6/P19 buffer -> wick band -> `min_stop_pct` floor -> CF-14 step-3
clip. **Step 3 is the only step that moves the stop toward the entry, it runs last, and nothing
re-validates after it.** Three findings in three days are that single property: the floor undone
by the clip, the `widened` flag erased by the clip (`7044e75`), and the ladder-invalidation
invariant broken by the clip. One architectural fact, found three times.
