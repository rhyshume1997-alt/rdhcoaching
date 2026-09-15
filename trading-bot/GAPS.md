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

Status legend: `OPEN` · `DESIGN` (proposals written, nothing implemented) · `DONE`.

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

**No sweep runner was added**, as instructed.

**Worth knowing for whoever does the sweep:** the §12.1 default warm-up is **500 bars**. A
2/3 split therefore needs **>750 bars** before the in-sample segment has a single analysable
bar; below that the command refuses with a usage error rather than reporting an empty segment.
`data/synthetic_4h.csv` (800) barely clears it; `data/sol_4h_600.csv` (600) does not.

---

## GAP 2 — No correlation control on concurrent positions

**Status:** OPEN.

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

---

## GAP 3 — No relative strength / cross-symbol ranking

**Status:** OPEN — design proposals first, no code.

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

**Blocked on a design decision.** Candidates worth costing: performance vs a benchmark (BTC) over
N lookbacks; position within own recent range; structure divergence (making HH/HL while the
benchmark is not); behaviour on the last market-wide down day. Each must state **what it needs
from the data layer** — the pipeline receives one symbol's window today, and that plumbing is
plausibly the real cost, not the metric. Propose 2–3, cost them, do not pick one unilaterally.

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
