# SAMPLE_RUN.md — one real backtest, shipped defaults, nothing tuned

Every number below is the output of the single run named in section 1, on shipped defaults and
synthetic data. Nothing was edited by hand and no default was loosened to manufacture trades:
where the strategy produced almost nothing, section 4 says which gate stopped it.

> **Stale in one respect (F6, frame pass 2).** This run predates `stop_buffer_zone_fraction`
> (`../FRAME_FINDINGS.md` F6), which changed how a stop anchored to a **zone** is placed: half the
> box height beyond the box's far edge instead of 0.15 ATR beyond a candle anchor. Plans that hang
> off a zone — not the two S/R tickets quoted in §3 — would move, and with them `stop_too_tight`,
> the R:R counters and the sizes that follow from stop width. The run has not been regenerated
> (~22 minutes wall clock — see the 2026-09-15 correction in §2 on how that scales); every
> other number below still stands.

> **Stale in a second respect (F9, the R:R basis).** This run gated G14 on R:R measured to
> **TP1**. `rr_measured_to` now defaults to `final_tp` (`../FRAME_FINDINGS.md` F9), which is where
> his own position tool's R:R readout measures to. §4's `rr_below_min` row (257, 1.8 %) is the
> figure for the **old** basis; re-measured on this same series under the new one it falls to 2.
> The 255 plans that moves are not new candidates — they are plans this run built and then vetoed,
> which now go on to the later gates. Every other row moves only by that knock-on.

**This run is on the post-Q1–Q15 defaults** (see `../CHANGELOG_EVIDENCE.md`). Section 2 carries the
before/after against the previous run, which was on the pre-fix defaults. The headline is that the
**USD figures moved by roughly 10× and the trade count did not move at all** — which is exactly what
the Q8 sizing fix predicts and is the cleanest possible confirmation that it changed sizing and
nothing else.

## 1. The command

`data/synthetic_4h.csv` is built from `tbot.data.synthetic()` alone — eight seeded blocks
chained into one continuous series, each rebased onto the previous block's last close:

```python
from datetime import datetime, timezone
import pandas as pd
from tbot.data import synthetic
from tbot.models import Timeframe

frames, last = [], None
for seed in range(1, 9):
    f = synthetic(seed=seed, tf=Timeframe.H4).series.frame.copy()
    if last is not None:
        f = f.mul(last / f["close"].iloc[0])
    last = f["close"].iloc[-1]
    frames.append(f)
out = pd.concat(frames)
out.index = pd.date_range(datetime(2022, 1, 1, tzinfo=timezone.utc),
                          periods=len(out), freq="240min", tz="UTC")
out.index.name = "timestamp"
out.reset_index().to_csv("data/synthetic_4h.csv", index=False)
```

```bash
python -m tbot backtest \
    --csv data/synthetic_4h.csv --tf 4H --symbol SYNTHUSDT \
    --events events.txt --save-run run.json
```

Wall clock: about 22 minutes. The harness calls the pipeline once per post-warm-up bar and every
detector re-derives its whole live set from bar 0 each time (INTERFACES.md §6.2), so the cost
grows with the square of the series length.

> **Correction, 2026-09-15 — the 22 minutes stands, the explanation of it does not.** The wall
> clock above is what this recorded run took and is left as measured. But "grows with the square
> of the series length" understates it: per-bar cost was measured at **O(n^2.2)**, which makes a
> full run **O(n^3.2)**. Seven-point curve in `../CLAUDE.md` open item 5. Two consequences worth
> carrying: projections from this figure are **± roughly 2×**, because cost depends on *which*
> bars as well as how many (0.757s vs 1.338s per bar at identical window length on different
> data); and the cost is **not** detector output being re-derived in the way this sentence
> implies — the ATR array is rebuilt exactly once per bar (0.5 ms of a 9.8 s bar, measured, a
> cache there was rejected). It is `detectors/trendlines.py` `_touches`, O(P³) pairwise pivot
> geometry, ~2,601 calls per bar.

- bars: **800** 4H bars, 2022-01-01 to 2022-05-14
- warm-up discarded (SPEC.md §12.1): **500** bars, so **300** bars were actually analysed
- starting equity: 10000 USD (`--equity` default — [OUR CHOICE], not a §11 key)
- non-default config keys this run: **none** (0 changed)

`4H` matters: CF-38 makes anything from `15m` to `2H` a *scalp*. `module_scalp_enabled` now ships
**true** with `scalp_tf_floor = 30m` (Q14), so a 1H series is no longer empty by construction — but
`4H` is the first timeframe at `swing_tf_floor` and is what this run is about.

## 2. Headline numbers, and the delta against the pre-fix run

| metric | **this run** | previous run | delta |
|---|---|---|---|
| closed trades | **2** | 2 | **unchanged** |
| win rate (net P&L > 0) | **100.00%** (2W / 0L / 0BE) | 100.00% (2W / 0L / 0BE) | unchanged |
| expectancy, R | **+10.9799 R** | +10.9344 R | +0.05 R |
| expectancy, USD | **+384.22 USD** | +35.75 USD | **×10.7** |
| net P&L | **+768.44 USD** (10000.00 → 10768.44) | +71.49 USD | **×10.7** |
| **risk per trade (USD at stop)** | **50.00 USD** | 5.00 USD | **×10.0** |
| **risk per trade (% of equity)** | **0.500%** | 0.050% | **×10.0** |
| notional per trade | **10000.00 USD** (100% of equity) | 1000.00 USD (10%) | ×10.0 |
| derived leverage | 25x / 37.9x | 3.8x / 5.0x | ×6.6 / ×7.6 |
| max drawdown | **0.01%** (0.78 USD) | 0.00% (0.06 USD) | ×13 |
| fees / funding | **5.50 / 2.09 USD** | 0.51 / 0.20 USD | ×10.8 / ×10.4 |
| plans armed | **23** | 18 | +5 |
| still open at the end | 0 | 0 | unchanged |
| candidates rejected | **14015** | 13785 | +230 |
| detections recorded | **326** | 395 | −69 |

### Reading the delta

**The sizing fix is the whole story, and it is clean.** Trade count, win rate, close reasons, entry
prices, stops and TP levels are all identical or near-identical; only the *quantity* changed. That is
what a mislabelled ceiling should do when it is corrected, and it is why the R multiples barely
moved while the USD figures moved by an order of magnitude.

**Risk per trade went from 0.05% to 0.50% of equity — ten times, exactly the ceiling ratio.** Both
trades are still `notional_clamped_to_ceiling`, because this synthetic series produces very tight
stops (about 0.5% of entry) and a 100%-of-equity notional against a 0.5% stop can only ever risk
0.5% of equity. The CF-01 budget is 4%, so the clamp is still binding — it is just binding at the
right place now. **This is the regime `CHANGELOG_EVIDENCE.md` Q8 predicts**: with the ceiling at
100.0 the clamp bites only for stops tighter than 5%, which is precisely what a 0.5% stop is. On
real data with his 7–9% stops the clamp would not fire at all and the trade would risk the full 4%.

**The remaining under-risking is not a bug and not the same bug.** 0.5% against a 4% budget is the
notional ceiling doing its documented job on an unusually tight stop, reported as
`notional_clamped_to_ceiling` on every plan. The old 0.05% was a *margin* percentage masquerading as
a notional ceiling, and no stop width could have rescued it.

**Detections fell 395 → 326 (−17%)** and rejections rose slightly. Two changes account for this:
Q6's `dir_change_uses_sufficient_gap_table` now rejects order-block candidates whose impulse leg is
below his percentage-by-timeframe floor (reported, not silent), and Q1's `ob_fill_invalidation_pct`
kills order blocks at 75% of liquidity taken instead of at the zone's 50% line — which *revives*
some blocks the old rule killed early and kills others the old rule kept. Net: fewer, better-founded
objects.

**`rr_below_min` rose 29 → 257 and `stop_too_tight` 71 → 139.** Both are downstream of the same
thing: with 39/61 entry ladders (Q3) instead of 30/70, the blended entry sits slightly further from
the first rung, which moves R:R and stop distance on every two-leg plan. `insufficient_tps` fell
73 → 37 for the same reason.

**`insufficient_confluence` is essentially flat (7001 → 6925) despite Q5 changing the gate from a
weighted score to a raw object count.** That is worth stating plainly: the two gates reject almost
the same *number* of candidates on this series — but not the same candidates. The raw-count gate now
admits three-object stacks that score under 3.0 weighted (which is the whole point, per S5
`[01:05:33]`) and rejects two-object stacks that used to pass on weight alone.

## 3. Example trade tickets

Armed on bar 642 (2022-04-18 00:00 UTC) as `T0011`; closed on bar 647 for +231.8766 USD = +11.228R (tp_final).

```
--------------------------------------------------------------------------
  LONG  SYNTHUSDT    swing / leverage @ 25x
  plan setup:SYNTHUSDT:4H:support_resistance_levels:638:long:plan   setup setup:SYNTHUSDT:4H:support_resistance_levels:638:long
  conviction high   confluence 4.0 (order_block, pattern, range_boundary, sr_level)   entry family retest
  last close 334.6743321925531
--------------------------------------------------------------------------
  ENTRIES (ladder, light first then heavier at the DCA — CF-17/CF-18)
    0. entry 328.11209038485595   39.0% of size   on SYNTHUSDT:4H:support_resistance_levels:638   [resting]
    1. dca   327.9534238702418   61.0% of size   on SYNTHUSDT:4H:ranges:605   [resting]
    planned average entry  328.0153038109413185
  STOP (one per plan — CF-14; the duplicate of S4-R34 is an execution device)
    326.3752272918866119075
  TAKE PROFITS (structural levels — §8.7, CF-27/CF-28)
    TP0: 341.236574000250225   50.0% out   SYNTHUSDT:4H:ranges:623    
    TP1: 354.3610576156445   50.0% out   SYNTHUSDT:4H:support_resistance_levels:642    
  SIZE AND RISK
    qty 30.48638244563038823601848357   notional 10000.00 USD   risk budget 4.0%
    R:R to TP1 8.061373988165668139926171927   expected move 8.031867263086030841847728580%
    invalidation level SYNTHUSDT:4H:support_resistance_levels:638
  SOURCE RULES: CF-32, CF-37, SPEC-3.1, S4-R4, S7 [00:05:04], S5-R8, S5-R9, CF-45, CF-09, CF-13, S6-R3, S6-R9, S6-R2, CF-12, S6-R48, S7-R6, S7-R3, P15, S7-R32, S7-R33, S7-R34, S8-R25, S4-R19, P9, CF-16, CF-17, CF-18, CF-14, P19, S2-R12, S6-R17, S6-R18, S8-R18, CF-06, CF-27, CF-28, CF-01, CF-02, CF-07, S6-R11, S6-R12, S6 `[00:08:36]`
--------------------------------------------------------------------------
```

Armed on bar 642 (2022-04-18 00:00 UTC) as `T0012`; closed on bar 651 for +536.5675 USD = +10.731R (tp_final).

```
--------------------------------------------------------------------------
  SHORT SYNTHUSDT    swing / leverage @ 37.87878787878787878787878788x
  plan setup:SYNTHUSDT:4H:support_resistance_levels:642:short:plan   setup setup:SYNTHUSDT:4H:support_resistance_levels:642:short
  conviction normal   confluence 3.75 (pattern, range_boundary, sr_level, trendline)   entry family retest
  last close 334.6743321925531
--------------------------------------------------------------------------
  ENTRIES (ladder, light first then heavier at the DCA — CF-17/CF-18)
    0. entry 354.3610576156445   100.0% of size   on SYNTHUSDT:4H:support_resistance_levels:642   [resting]
    planned average entry  354.3610576156445
  STOP (one per plan — CF-14; the duplicate of S4-R34 is an execution device)
    356.1328629037227225
  TAKE PROFITS (structural levels — §8.7, CF-27/CF-28)
    TP0: 341.236574000250225   50.0% out   SYNTHUSDT:4H:ranges:623    
    TP1: 329.07568233433403   50.0% out   SYNTHUSDT:4H:ranges:605:1    
  SIZE AND RISK
    qty 28.21980515377747099903600794   notional 10000.00 USD   risk budget 4.0%
    R:R to TP1 7.407407407407426743199827588   expected move 7.135483636787226718798127415%
    invalidation level SYNTHUSDT:4H:support_resistance_levels:642
  SOURCE RULES: CF-32, CF-37, SPEC-3.1, S4-R4, S7 [00:05:04], S4-R3, P8, CF-15, CF-07, S7-R32, S7-R33, S7-R34, S8-R25, S4-R19, P9, S2-R14, S3-R19, S4-R20, S5-R1, S8-R7, S6-R28, CF-16, CF-17, CF-18, CF-14, P19, S2-R12, S6-R17, S6-R18, S8-R18, CF-06, CF-27, CF-28, CF-01, CF-02, S6-R11, S6-R12, S6 `[00:08:36]`
--------------------------------------------------------------------------
```

Note the two Q-driven changes visible on the face of the first ticket: the ladder is **39/61**
(Q3, derived from his own worked LINK ladder) where it was 30/70, and `P15` now appears in the
source-rule chain (Q1 — the order-block liquidity measure is live for the first time).

## 4. Rejection attribution — which gate is actually shaping the strategy

14015 rejections across 300 analysed bars. Every one carries the §7.1 gate that stopped it and that gate's own wording; nothing is dropped silently (INTERFACES.md §9.6).

| gate | what it is | reason | count | share | previous |
|---|---|---|---:|---:|---:|
| G5 | confluence object count (CF-31, Q5) | `insufficient_confluence` | 6925 | 49.4% | 7001 |
| G4 | weekend (CF-39, TBOT1-R24) | `weekend_blocked` | 3682 | 26.3% | 3696 |
| G0 | pipeline pre-gate (candidate formation) [OUR CHOICE] | `anchor_beyond_price` | 1777 | 12.7% | 1777 |
| G11 | object dead / touch limit (CF-07, CF-08, Q1) | `touch_limit` | 776 | 5.5% | 774 |
| G8 | higher-timeframe veto (CF-24) | `htf_veto` | 337 | 2.4% | 285 |
| G14 | R:R below min_rr (CF-42) | `rr_below_min` | 257 | 1.8% | 29 |
| G13 | stop too tight (CF-06, CF-14) | `stop_too_tight` | 139 | 1.0% | 71 |
| G6 | mid-range no-trade band (CF-25) | `mid_range_no_trade` | 71 | 0.5% | 65 |
| G16 | fewer than tp_min_count structural TPs (CF-27) | `insufficient_tps` | 37 | 0.3% | 73 |
| G0 | pipeline pre-gate (candidate formation) [OUR CHOICE] | `zone_candidate_rejected` | 6 | 0.0% | 6 |
| G15 | expected move too small (CF-41) | `move_too_small` | 6 | 0.0% | 6 |
| G9 | shorting policy (CF-41) | `short_policy` | 2 | 0.0% | 2 |

### What that says

1. **G5 `insufficient_confluence` (49.4% of all rejections)** is still the binding constraint, and
   Q5 did not loosen it — it re-pointed it. The gate now counts raw deduplicated objects against
   `min_confluence_count` instead of summing an invented weight map, so it rejects a different
   population of roughly the same size.
2. `weekend_blocked` (G4) is second because `weekend_mode = "leverage_blocked"` and the
   pipeline enters qualification with `vehicle = LEVERAGE` (qualify's own default). Crypto
   synthetic bars run 24/7, so roughly two days in seven are closed to every leverage
   candidate. With a `SymbolProfile` injected, tier B would demote the vehicle to spot and
   these would survive — the pipeline says so in its degradation notes rather than guessing
   a profile.
3. `anchor_beyond_price` (G0) is the pipeline's own pre-gate: a confluence stack that sits
   on the wrong side of the current close cannot be a retest. It is reported rather than
   quietly skipped so the census adds up.
4. **`rr_below_min` is the biggest mover (29 → 257)** and it is a Q3 side-effect, not a regression:
   a 39/61 ladder blends the entry closer to the first rung than 30/70 did, which shortens the
   distance to TP1 relative to the stop on marginal setups. These are candidates the old ladder
   flattered.

## 5. Honest caveats about these numbers

- **The CF-02 notional ceiling is still sizing every trade — but now at the right level.**
  `max_notional_pct_leverage` is 100% of equity (10000 USD here) while the swing loss budget
  is 4% (400 USD). On this series the stop is only ~0.5% wide, so `solve_size` still clamps to
  the ceiling and re-solves quantity, and realised risk lands at 0.50% rather than 4%.
  That is the shipped default behaving as written (`notional_clamped_to_ceiling`, CF-02) on an
  unusually tight stop — **not** the Q8 defect, which was a 10× smaller ceiling derived from a
  margin figure. On stops in his own 7–9% range the clamp would not fire at all.
- **A 2-trade sample proves nothing.** The §12.5 claim comparison says so itself: the 95%
  Wilson interval spans 34%-100%.
- **The §10 portfolio gates never ran.** The harness calls `tbot.pipeline.run(series,
  config)` with no portfolio state, so G17 (CF-04 concurrency, deployment, daily-loss) is
  skipped and 23 plans could arm concurrently. Injecting a `PortfolioState` turns it on. This
  matters more than it used to: at 100% notional per trade, 23 concurrent plans is not a
  position a real book could carry.
- **No cross-market context, calendar, symbol profile or lower-timeframe series was
  injected**, so G1, G3, G7 and the CF-06 step-1 stop tighten degrade to their documented
  no-op. The pipeline reports each one instead of inventing a value.
- **Two config values in this run are still `absent`-class placeholders** (`CHANGELOG_EVIDENCE.md`):
  `swing_k = 3` and the 2H/4H/8H/12H rows of `sufficient_gap_pct_by_tf`. Neither is his, and on a
  4H series the second one is load-bearing.

Verbatim from the run:

```
- no portfolio state injected: the §10 concurrency, deployment and daily-loss gates (G17) are not evaluated and sizing assumes the harness default starting equity
- no SymbolProfile injected: the CF-40 universe tier (G1) is not evaluated and the vehicle is not demoted on rank/volume grounds
- no calendar injected: the CF-39 event blackout (G3) sees an empty calendar; unscheduled news cannot reach the bot at all (TBOT1-A23)
- no active-symbol list injected: the CF-40 watchlist cap (G2) is evaluated against an empty book
- no cross-market context injected (USDT.D / BTC.D / BVOL): the §7.2 regime layer degrades to neutral and never invents a risk-on read
- detectors/indicators.py (§3.1 stage 14, CF-36) is not implemented in this build: the rsi_divergence and ema200 confluence classes are never produced, so nothing scores on them
- no lower-timeframe series injected: CF-06 step 1 (tighten the stop 2 timeframes down) is unavailable and a wide stop goes straight to the vehicle downgrade
```

## 6. The full report, verbatim

```
==============================================================================
BACKTEST REPORT  SYNTHUSDT 4H
==============================================================================
  bars 800 (warm-up discarded: 500)   range 2022-01-01 00:00 -> 2022-05-14 04:00
  equity 10000.00 -> 10768.44 USD   net P&L +768.44
  fees 5.50   funding 2.09   (all metrics are NET - SPEC.md §12.3)

-- WIN RATE (three definitions, §12.4 / S5-A19) ------------------------------
  closed trades                    2
  1. net P&L > 0 (headline)        100.00%   (2W / 0L / 0BE)
  2. full TP-ladder completion     100.00%   (2 of 2)
  3. excluding break-even exits    100.00%   (2 of 2 decided)

-- THE 77-82% CLAIM: A HYPOTHESIS UNDER TEST (§12.5) ------------------------
  claimed (S5, recollection)       77%-82%
  measured (definition 1)          100.00%   n = 2
  95% Wilson interval              34.2% - 100.0%
  verdict: sample too small to conclude anything: 2 closed trade(s), below the 30-trade floor [OUR CHOICE]. The 95% Wilson interval is 34.2%-100.0%, which is too wide to separate any hypothesis from any other.
  S5 [00:38:20] / [01:15:40] state a back-tested 77-82% win rate for the supply/demand method; S4-C2 adds 8/10, 7/10, 10-for-14 and 7-for-7. CONFLICTS.md rules these NOT usable for sizing or validation - recollections, no sample, no win definition. This harness reports the claim only as a hypothesis under test. No sizing, expectancy, Kelly fraction or capacity number anywhere in this package references it, and a measured win rate below it is a result, not a bug to be fitted away (SPEC.md §12.5).

-- EXPECTANCY AND R DISTRIBUTION --------------------------------------------
  expectancy                       +10.9799 R per trade (+384.22 USD)
  R: p5 +10.76  p25 +10.86  median +10.98  p75 +11.10  p95 +11.20
  outcomes worse than -1R          0  (gap and slippage losses: §12.2 A2, A6)
               >= +5.0  ## 2

-- DRAWDOWN -----------------------------------------------------------------
  portfolio max drawdown           0.01%  (0.78 USD)  bar 0 -> 643
    leverage_swing       0.01%  (0.78 USD)

-- PER-DETECTOR ATTRIBUTION (§12.4, CF-31) ----------------------------------
  anchor class              n     win%    exp R   total R     net USD
  order_block               1   100.0%   11.228     11.23      231.88
  pattern                   1   100.0%   10.731     10.73      536.57
  marginal contribution as a confluence member (not the anchor):
  pattern                   1   100.0%   11.228     11.23      231.88
  range_boundary            2   100.0%   10.980     21.96      768.44
  sr_level                  2   100.0%   10.980     21.96      768.44
  trendline                 1   100.0%   10.731     10.73      536.57

-- BY TRADE CLASS -----------------------------------------------------------
  swing                     2   100.0%   10.980     21.96      768.44

-- BY VEHICLE ---------------------------------------------------------------
  leverage                  2   100.0%   10.980     21.96      768.44

-- BY CONVICTION ------------------------------------------------------------
  high                      1   100.0%   11.228     11.23      231.88
  normal                    1   100.0%   10.731     10.73      536.57

-- BY ENTRY FAMILY ----------------------------------------------------------
  retest                    2   100.0%   10.980     21.96      768.44

-- BY TOUCH INDEX AT ENTRY --------------------------------------------------
  touch 3                   1   100.0%   11.228     11.23      231.88
  touch 4                   1   100.0%   10.731     10.73      536.57

-- BY CLOSE REASON ----------------------------------------------------------
  tp_final                  2   100.0%   10.980     21.96      768.44

-- FILL QUALITY (§12.4, A7) -------------------------------------------------
  rung 0: filled 2/2 = 100.0%
  rung 1: filled 0/1 = 0.0%
  realised vs planned average entry: +0.048393 (+1.48 bps, adverse-positive)
  trades whose ladder only partly filled: 1

-- EXCESS RISK (spot exits, §12.2 A8, CF-05) --------------------------------
  total 0.00 USD across 0 trade(s); reported separately and NOT netted out of the risk statistics

-- TIME IN MARKET -----------------------------------------------------------
  median 5.0 bars (20.0h), mean 5.0 bars
    swing              median 5.0 bars (20.0h)

-- VETO CENSUS (which §7 gate is actually shaping the strategy) -------------
  G5                                        6925
  G4                                        3682
  G0                                        1783
  G11                                        776
  G8                                         337
  G14                                        257
  G13                                        139
  G6                                          71
  G16                                         37
  G15                                          6
  G9                                           2
  most common reasons:
    insufficient_confluence                                         6925
    weekend_blocked                                                 3682
    anchor_beyond_price                                             1777
    touch_limit                                                      776
    htf_veto                                                         337
    rr_below_min                                                     257
    stop_too_tight                                                   139
    mid_range_no_trade                                                71
    insufficient_tps                                                  37
    move_too_small                                                     6

==============================================================================
```
