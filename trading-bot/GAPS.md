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
| GAP 1 `backtest --split` | **operational, with a naming defect** — it splits correctly but `in_sample_fraction` measures over RAW bars, so a "2/3" split at 900 bars is really 25% in-sample by *analysable* bars (warm-up eats 500). First OOS run recorded under GAP 1. | decide whether the fraction should measure over the post-warm-up region, or report both counts |
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
