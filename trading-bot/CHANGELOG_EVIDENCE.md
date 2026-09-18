# CHANGELOG_EVIDENCE.md — the fifteen open questions, answered from the recordings

Three research agents re-mined the source recordings (`transcripts/`, sessions S2–S8 + TBOT1) against
the fifteen questions in `CONFLICTS.md` § *Unresolvable without the trader*. **Thirteen came back with
an answer.** This file records what changed, at what confidence, and the timestamp that decided it.

Confidence labels are the researchers':

| Label | Meaning | How it was applied |
|---|---|---|
| `stated` | He says it, in numbers, on tape | Default changed, source ID and timestamp written into `configs/default.yaml` |
| `derived` | Solved arithmetically or by counting off a worked example | Same as `stated` |
| `inferred` | Consistent with behaviour, never stated | Applied, **and the key's source line in `configs/default.yaml` is marked `inferred` / `[INFERRED]`** |
| `absent` | Not in the corpus | **No value invented.** Existing default kept, labelled `[OUR CHOICE]`, sweep plan recorded below |

Where a finding contradicts a `CONFLICTS.md` verdict the new evidence wins, and the reversal is
recorded in place in that document so it stays authoritative. Full evidence with quotes:
`answers/part1.md` (Q1–Q5), `answers/part2.md` (Q6–Q10), `answers/part3.md` (Q11–Q15).

---

## The critical one

### Q8 — Normal leverage position size — **a live defect, `derived`**

**Evidence:** S6 `[00:08:36]`–`[00:11:27]` (the worked sizing loop); S7 `[00:25:54]`, `[00:20:33]`
(10 % is margin); S2 `[01:52:12]` (*"I always do 10x"*); S6 `[00:13:47]`, S2 `[01:52:52]` (margin
semantics confirmed unprompted); S3 `[00:04:25]` (the 20 % figure, same quantity at a different date).

`max_notional_pct_leverage = 10.0` was his **margin** percentage being enforced as a **notional**
ceiling. Because SPEC §8.8 re-solves quantity from the clamped notional, it did not merely cap
exposure — it discarded the CF-01 risk budget. Every leverage trade was landing at ≈**0.74 %**
portfolio risk against a 4 % budget.

His worked example, $1,000 portfolio, average entry 38.38, stop 41.23 (distance 2.85):

| | attempt 1 | attempt 2 | accepted |
|---|---|---|---|
| legs | 15 + 25 | 8 + 15 | **7 + 12** |
| total qty | 40 | 23 | **19** |
| loss at stop | **$114** | **$65** | **$54** |
| % of portfolio | 11.4 % *"too high"* | 6.5 % *"still too high"* | **5.4 % *"this is okay"*** |
| notional (qty × avg) | $1,535 = 153.5 % | $883 = 88.3 % | **$729 = 72.9 %** |

The notional row is the one he never says out loud, and a 10 % notional ceiling cannot produce any of
the three. The margin reading also closes S7's own arithmetic: 10 % in, 5 % of portfolio lost = half
of what you put in, which needs leverage; at 10x, $100 margin is $1,000 notional and a **5 %** adverse
move gives exactly the $50. Under the notional reading the same sentence needs a **50 % stop**, which
`max_stop_pct_leverage = 9.0` forbids outright.

| Key | Before | After | Confidence |
|---|---|---|---|
| `max_notional_pct_leverage` | 10.0 | **100.0** (= 10 % margin × 10x) | `derived` |
| `margin_pct_leverage` | *(did not exist)* | **10.0** | `stated` |
| `default_leverage` | *(did not exist)* | **10.0** | `stated` |

**Regression test:** `tests/test_risk.py::TestQ8HisWorkedSizingExample` — nine tests. It reproduces his
three attempts from the raw legs, asserts the exact $114 / $65 / $54 and the 72.9 % notional, feeds the
bot his own 5.415 % risk and asserts it prints his ticket back (**qty 19, loss $54.15, notional
$729.22, nothing clamped**), pins the old 10.0 behaviour at 0.74 % realised risk (a 5.4x under-risking on this stop width) so
the regression cannot silently return, and checks the margin reading against `max_stop_pct_leverage`.

**Sweep:** `max_notional_pct_leverage` over {73.0 (his accepted example), 100.0, 155.0 (his rejected
first attempt), 200.0 (S3's 20 % margin at 10x)}, and `margin_pct_leverage` {10.0, 20.0}.

---

## Applied changes, by question

### Q1 — Zone invalidation: 50 % or 70–80 %? — **`stated`**

**Evidence:** S7 `[00:07:14]`–`[00:08:54]` (*"this one doesn't have a rule where 50% has to be
taken… my rule for order blocks are like around 70 80%"*); S7 `[00:37:57]` (a 50 %-filled OB he
takes); S5 `[00:38:52]`, `[00:41:10]` (the zone rule); S8 `[00:34:48]` (100 % = dead); S7 `[00:08:22]`
(HTF-support rescue).

Verdict (c): **two objects, two thresholds.** Multi-candle supply/demand zone dies at 50 % of depth;
single-candle order block dies at ~75 % of liquidity taken.

| Key | Before | After | Confidence |
|---|---|---|---|
| `ob_fill_invalidation_pct` | *(did not exist)* | **75.0** | `stated` |
| `zone_fill_invalidation_pct` | 50.0 | 50.0, now **scoped to zones only** | `stated` (was `inferred`) |
| `zone_fill_measure` | `"wick_touch"` | unchanged | `inferred` — sweep |

**This activates primitive P15.** `ob_liquidity_taken_pct` previously ran only when
*`zone_fill_invalidation_pct`* was raised to 70/80 — a setting nothing shipped — so the order-block
liquidity measure had never executed in a live configuration. It is now the order block's death test
unconditionally (`tbot/detectors/orderblocks.py::ob_invalidation_pct`). **Reverses** the declared
departure from precedence rule 1 recorded at the top of `CONFLICTS.md`: no departure is needed once
the two measurements are separated.

### Q2 — Third-touch rule vs replaying a zone — **`stated` / `derived` / `absent`**

**Evidence:** S5 `[00:24:35]`, `[00:25:40]` (he numbers the touches: the 4th is the veto, not the
3rd); S6 `[00:52:38]` (one zone played three times, stopped by the fill line); S4 `[00:44:55]` (range
boundary, 5th touch); S8 `[00:54:14]` (*"smaller position only because it's going to be the fifth
touch"*); S7 `[00:08:22]` (the 3rd touch is *"a great area to go long"*).

| Key | Before | After | Confidence |
|---|---|---|---|
| `touch_size_decay` | `[1.0, 1.0, 0.66, 0.5, 0.33]` | **`[1.0, 1.0, 1.0, 0.66, 0.5]`** | `inferred` |
| `line_touch_hard_limit` | 3 | unchanged | upgraded to `derived` |
| `zone_touch_uses_fill_rule_not_count` | true | unchanged | upgraded to `derived` |

The old curve cut size at the 3rd touch, which is a touch he explicitly endorses. **`absent`:** the
multipliers themselves. **Sweep** `touch_size_decay` over flat `[1,1,1,1,1]`, previous
`[1.0,1.0,0.66,0.5,0.33]`, current `[1.0,1.0,1.0,0.66,0.5]`, steep `[1.0,0.75,0.5,0.25,0.0]` —
decide on **expectancy per trade at touch index ≥3, split by object class**, with a secondary check
that total return at index ≥3 stays positive. A flat curve that still wins says the decay is cosmetic.

### Q3 — DCA size split — **`derived`**

**Evidence:** S6 `[00:38:49]`–`[00:40:05]` (35 : 55 : 100 at 17.28 / 17.858 / 18.181 → average
*"17.921"*; recompute = 17.9215, exact); S6 `[00:48:10]` (*"17.63… a total of 90 coins"*; recompute =
17.6332, exact); S6 `[01:54:34]` (wick-heavy first leg *"20 to 30%"*); S2 `[00:21:45]` (entry + first
DCA ≈ half the position, which 35+55 of 190 reproduces at 47.4 %).

| Key | Before | After | Confidence |
|---|---|---|---|
| `dca_size_split_2` | `[0.30, 0.70]` | **`[0.39, 0.61]`** | `derived` |
| `dca_size_split_3` | `[0.20, 0.30, 0.50]` | unchanged — relabelled *OUR ratio* → **derived** | `derived` |
| `dca_size_split_wick_heavy_2` | `[0.20, 0.80]` | **`[0.25, 0.75]`** (midpoint of his band) | `stated` |

Side-effect worth recording: the S6-R13 (*"closer to the last DCA"*) vs S7-R18 (*"roughly mid-zone"*)
disagreement CF-18 was written to resolve is not a disagreement — the 3-leg shape lands closer to the
last DCA and the 2-leg shape lands mid, which is exactly what he says of each.

### Q4 — What fraction comes off at each TP — **`stated` (n≤3) / `absent` (n≥4)**

**Evidence:** S4 `[00:17:53]`, `[00:18:27]` — asked point-blank and answered: *"if it's three TPS, I
have 40 30 30. If it's two TPS, then I do 50/50."* Never revised in S5–S8 or TBOT1.

| Key | Before | After | Confidence |
|---|---|---|---|
| `tp_split_2` | `[0.50, 0.50]` | unchanged | upgraded to `stated` |
| `tp_split_3` | `[0.40, 0.30, 0.30]` | unchanged | upgraded to `stated` |
| `tp_split_4` / `tp_split_5` | `[0.40,0.25,0.20,0.15]` / `[0.35,0.25,0.20,0.12,0.08]` | **unchanged — no value invented** | `absent` |

**`absent` — sweep plan, recorded not applied.** The researcher's preferred shape is to replace the two
invented rows with a single front-loading parameter `tp_split_decay ∈ [0.55, 1.00]`, slice *i* ∝
`decay^(i-1)` renormalised, governing **n≥4 only** — his n=2 and n=3 rows are not geometric (50/50 is
flat; 40/30/30 is one big slice then flat) so no decay can be fitted to them, and they must stay
pinned. Seed 0.80 (→ 34/27/22/17 at n=4), sweep 0.55–1.00 in steps of 0.05. Metric: **realised R per
trade on setups where ≥4 structural TPs were placed**, tie-broken on the fraction of trades reaching
TP2 before being trailed out (CF-29 moves the stop to TP1 on TP2, so back-loading directly raises the
chance of being trailed out of the remainder for nothing). **The key was not added**: adding it would
change `tp_split_4`/`tp_split_5` away from their current values, which is exactly what an `absent`
finding forbids.

### Q5 — Minimum confluence count, and how to count overlaps — **`derived`**

**Evidence:** S5 `[01:43:55]` (three endorsed in answer to a student); S5 `[01:05:33]` (*"So three.
That's why I'm taking this one here"*); S8 `[00:53:41]` (*"one SR, two supply zone, three
confluences"*); S6 `[00:45:16]`, `[00:55:31]` (declines at one); S6 `[01:07:32]` (an OB inside a zone
is not a separate confluence).

| Key | Before | After | Confidence |
|---|---|---|---|
| `confluence_gate_mode` | *(did not exist)* | **`"raw_count"`** | `derived` |
| `min_confluence_count` | 3.0 (weighted score) | 3.0, now a **count of deduplicated objects** | `derived` |
| `confluence_weights` | §6.1 map, used as the gate | unchanged as a map, **demoted to ranking + conviction only** | weights still **OURS** |
| `ob_inside_zone_precedence` | `"zone_wins"` | unchanged | upgraded to `stated` |

The weighted gate silently rejected three-object stacks he demonstrably takes: S5 `[01:05:33]`'s
golden pocket + trend-line retest + consolidation point scores below 3.0 weighted and he names
"three" as his reason for taking it. The gate now counts objects; the §6.1 map is kept for the thing
he actually does with his ranking — choosing between two candidate stacks — and for
`high_conviction_score`. `map_conviction` was changed to take the count too, so the retired weighted
gate cannot come back in through the sizing door.

**`absent`:** the weights themselves — he ranks classes (S6 `[01:03:33]`) but never scores them.
**Sweep** `confluence_weights` `"flat"` vs the §6.1 map, crossed with `min_confluence_count` ∈ {2, 3,
4}; metric = **win rate, expectancy and trade count at each setting**, the tell being whether the
weighted map rejects trades he takes. Also sweep `confluence_merge_atr` 0.15–0.50 — that number is
OURS and it decides what "at the same price" means, which the whole counting rule rests on.

### Q6 — Swing detection and "directional change" — **`stated` / `inferred` / `absent`**

**Evidence:** S7 `[00:18:50]`, `[01:10:48]`, `[01:11:53]`, S5 `[01:25:16]` (structure off bodies /
line chart); **S7 `[01:14:44]`** (*"swing high points are usually taken by wicks, not by bodies. Okay,
but the candle body closes below the swing high point and this wick has taken out all of its
liquidity."*); S5 `[00:54:07]`, `[00:36:05]`, `[00:36:38]` (the move-size table); S7 `[01:19:52]`
(*"candles cannot be next to each other"*).

| Key | Before | After | Confidence |
|---|---|---|---|
| `swing_price_source` | `"body"`, labelled **[OUR CHOICE]** | `"body"`, **re-sourced** to S7/S5 | `stated` |
| `sfp_raid_price_source` | *(did not exist)* | **`"wick"`** — the carve-out | `stated` |
| `dir_change_uses_sufficient_gap_table` | *(did not exist)* | **true** | `inferred` |
| `dir_change_atr` | 2.0 | unchanged, **demoted to a secondary floor** | still `[OUR CHOICE]` |
| `sfp_min_bars_between` | 3 | unchanged; its **floor is now sourced at 2** | value still OURS |
| `swing_k` | 3 | unchanged | **`absent`** |

The **wick carve-out is now implemented and recorded**, not merely true by accident:
`tbot/detectors/sfp.py::raid_price` reads `sfp_raid_price_source` for the raid level, the
"pre-marked object at the swept price" test, the chase-distance measurement and the stop, while the
"closes back inside" test keeps using the body. Two different objects at one pivot, which is what he
says.

For "directional change": he never sizes it, but the only quantified move-size test he owns is the
sufficient-gap table, and in every worked example the order block and the zone are marked off the
same impulse leg whose gap he has just checked out loud. His threshold is a **percentage that scales
with timeframe**, which an ATR multiple cannot express. Implemented in the *order-block detector*
(`dir_change_gap_reason`) rather than inside P2, so P2 stays a pure geometric primitive, zones are not
double-filtered (P10 already applies the table to them), and the rejection is **reported** in the veto
census instead of candidates vanishing silently.

**`absent` — Q6(a), the candle count. STILL OPEN.** There is no fractal width, lookback or N-bar rule
anywhere in eight sessions; he never counts candles either side of a pivot, and his swing points are
ordinal, relational and explicitly multi-valued at one moment (*"this is your swing high. This is
your swing high. This is your swing high."*, S7 `[01:31:23]`). **Sweep** `swing_k` {2, 3, 5}, plus the
two-scale variant (k=2 and k=5 run together, deduped by `confluence_merge_atr`). Metric: **detected
structure breaks per 1,000 bars against the rate he narrates on the same charts** (roughly one MSB per
15–40 daily bars on BTC) — *not* PnL, which will reward whatever k happens to fit the sample. Also
sweep `dir_change_atr` {2.0, 3.0, 5.0, 8.0} and `sfp_min_bars_between` {2, 3, 5}.

### Q7 — Which timeframe governs — **`stated` / `inferred`**

**Evidence:** S7 `[00:21:45]` (*"higher time frame will always take precedence"* — the closest thing
to a governing principle in the corpus); S5 `[01:42:18]`; S8 `[00:23:06]`, `[00:16:46]` (the daily/12H
SFP disagreement); S7 `[01:24:22]`, `[01:26:03]`; S8 `[00:38:57]`, `[00:41:12]` (the daily veto, live).

| Key | Before | After | Confidence |
|---|---|---|---|
| `sfp_governing_timeframe` | `"trade_structure_tf"` | **`"highest_valid"`** | `inferred` |
| `htf_veto_enabled` / `htf_veto_timeframe` | true / `"1D"` | unchanged | upgraded to `stated` |
| `msb_price_source` | `"body_close"` | unchanged | `stated` ×4 |
| `structure_tf_offset` | 2 | unchanged, **demoted to sweep-first** | `[OUR CHOICE]` |

`governing_timeframe()` now performs the search, bounded below by the trade timeframe and above by
`structure_tf + 1` rung; with no validation evidence supplied it degrades to the structure timeframe,
which is the old behaviour. **Sweep** `structure_tf_offset` {1, 2, 3} — offset 3 is evidence-favoured
(1H → 8H lands on his stated favourite swing chart) and the sweep exists to check it does not destroy
trade count.

### Q9 — Counter-trend: cancel it, or halve it — **`stated`, no change**

**Evidence:** S7 `[00:17:06]` (cancel an *armed* setup whose trend flipped); S7 `[00:19:28]`–
`[00:26:26]` (a *deliberate* counter-trend entry: half size, 2–3 %, demoted to a scalp); S3
`[00:04:25]`, S8-R1, S5-R33.

All four defaults confirmed; three reclassified from inferred to sourced. **`"veto"` struck from
`counter_trend_mode`'s allowed values** — it was a mis-reading of a pending-order hygiene rule, not a
position anyone holds. The arithmetic is self-consistent: `counter_trend_size_multiplier` 0.5 ×
`max_loss_pct_swing` 4.0 = exactly `max_loss_pct_counter_trend` 2.0.

### Q10 — Resting limits at the SR point vs waiting for the flip — **`stated`**

**Evidence:** S4 `[00:55:38]` (the prohibition, scoped to an unflipped level); S3 `[01:54:12]`,
`[01:54:49]` (an SR point is *by definition* already flipped); S8 `[00:38:14]` (flip = break + retest
+ hold); S2 `[00:25:19]`, `[00:27:08]`–`[00:27:41]` (the intermediate state, and his own verdict on
it); S2 `[00:26:30]` (`flip_extra_candle_below_tf`, now sourced).

CF-16's two-family split survives intact. One key added for the entry neither family covers:

| Key | Before | After | Confidence |
|---|---|---|---|
| `presr_light_limit_enabled` | *(did not exist)* | **false** | `stated`-as-inferior |

Wired into `plan.dca_leg_count`: when on, a flip-pending setup rests the light first leg at the
broken-but-unretested level and the heavier leg at the confirmed flip — which is exactly the ladder he
describes in S2 `[00:27:08]` and then calls his own impatience. **Sweep** as an on/off pair; metric =
fill rate against deviation rate at freshly-broken levels.

### Q11 — Where the entry goes after a structure break — **`derived` / `absent`**

**Evidence:** S7 `[00:26:59]`, `[00:28:40]`, `[00:40:44]`; S8 `[00:25:58]`, `[01:17:19]`; S4
`[00:35:08]` (*"Next candle or however many candles it takes"*); **S2 `[00:25:56]`** (the deviation).

S7, S8 and S3 describe **one entry at increasing strictness**, not three; CF-22's separation of the S3
*exit* rule from the entry is correct and unchanged.

| Key | Before | After | Confidence |
|---|---|---|---|
| `msb_deviation_invalidates` | *(did not exist)* | **true** | `derived` |
| `msb_entry_requires_retest` | true | unchanged | now `stated` ×4 |
| `msb_retest_timeout_bars` | 20 | **unchanged** | `absent` |

The MSB's only invalidation used to be an [OUR CHOICE] bar count he explicitly declines to give. His
real one is a condition: a body close back beyond the broken level, outside the P9 tolerance band,
before any retest → the break was a deviation and nothing may arm off it. Detection still stands
(CF-22 separates detection from action); what dies is `entry_armed`.

**`absent` — the timeout. Sweep** `msb_retest_timeout_bars` {10, 20, 40, 60, disabled} on the
structure timeframe. Decider: **expectancy per MSB signal, not hit rate** — a long timeout raises fill
count and lowers average quality, so the knee in expectancy × count is the answer. Expect it to come
back flat, now that the deviation rule carries the real invalidation.

### Q12 — Mid-range as a band — **`stated` (the level) / `absent` (the width)**

**Evidence:** S4 `[00:17:53]` (asked outright: *"It will usually align with support and
resistance"*); S4 `[00:24:12]`, S3 `[00:02:15]`, S8 `[01:38:23]`; S4 `[00:12:28]`, `[00:16:47]`,
`[00:34:34]`, S8 `[01:37:43]` (he gates on *consolidating*, six phrasings, never a distance); S4
`[00:34:02]` (limits from the extremes are permitted).

| Key | Before | After | Confidence |
|---|---|---|---|
| `mid_range_search_pct` | 10.0, alternatives included **0** | 10.0; **`0` struck from the allowed set** (minimum raised to 0.1) | `stated` |
| `mid_range_band_pct` | 15.0 | **unchanged** | `absent` |
| `mid_range_limits_from_extremes_enabled` | true | unchanged | upgraded to `stated` |

**`absent` — the band width. Sweep** `mid_range_band_pct` {5, 10, 15, 20} % of range height each side,
jointly with `mid_range_search_pct` {5, 10, 15} since moving the level moves the band. Decider: this is
a pure gate, so measure the **expectancy of the trades it blocks** — if the blocked population's
expectancy is at or above the unblocked one, the band is too wide. Widen until blocked expectancy
drops below zero, then stop.

### Q13 — Sufficient gap for 2H / 4H / 8H / 12H — **`absent`, with one correction**

**Evidence:** S5 `[00:54:07]` (*"sufficient gap 30 minutes 4%. That's sufficient enough."*);
`[00:36:38]`, `[00:35:30]`, `[00:36:05]`, `[01:17:59]`, `[01:41:45]`.

| Key row | Before | After | Confidence |
|---|---|---|---|
| `sufficient_gap_pct_by_tf["30m"]` | 3.5 | **4.0** | `stated` |
| rows 2H / 4H / 8H / 12H / 3D+ | 5.0 / 6.0 / 7.0 / 7.5 / 15.0 | **unchanged** | `absent` |

The 30m row was a **mislabelled guess**: SPEC §5.5 and CF-11 both cite S5-R16 for 3.5, but S5-R16's
own params say "30m: 4% sufficient" and the transcript says 4 %. 3.5 came from smoothing the ladder.
The fix also makes the ≤1H rows read the way he speaks — a flat 3–5 % band with 4 % as the operating
point, not a rising staircase.

**Relabelled:** HIS rows are **15m, 30m, 1H, 1D, 2D**. OURS are **2H, 4H, 8H, 12H, 3D+**. CF-11's
"log-interpolation across timeframe" justification is **withdrawn**: fitting `gap = a·T^b`, his 1H→1D
step gives `b ≈ 0.22` and his 1D→2D step gives `b ≈ 0.70`. No exponent fits both. Extrapolating the
1D→2D slope backwards puts the 12H *below* the 1H; naive volatility scaling puts the 4H past his own
daily floor. The rows are kept as values and kept as guesses.

**`absent` — STILL OPEN. Sweep** each row independently within its defensible bracket (lower-bound fit
4→8 `b=0.218`, upper-bound fit 5→12 `b=0.275`): 2H {4.5, 5.0, 5.5, 6.0, 6.5}; 4H {5.0 … 8.0 by 0.5};
8H {6.0 … 9.0 by 0.5}; 12H {6.5, 7.0, 7.5, 8.0, 9.0, 10.0}. Decider: **expectancy per zone-sourced
trade at the zone's first touch**, with a floor on signal count so the optimiser cannot solve it by
admitting three zones a year. Run each row on that timeframe's own data — do **not** fit one exponent
across all four. Sweep jointly with `sufficient_gap_atr_mult` {1.5, 2.0, 2.5, 3.0}, since the two
tests are ANDed and only the binding one moves the metric; on 2H–12H expect the ATR test to be the
binding one, which is the reverse of how CF-11 framed it. Note S6 `[00:45:16]` calls a 5 % move on a
4H chart *"a lot"* — below the interpolated 4H row of 6.0, so his own worked 4H example would fail the
table.

### Q14 — Do the pattern, trend-line and scalp modules ship — **`stated` / `inferred`**

**Evidence:** patterns — S4 `[01:48:29]`, `[01:47:57]`, `[01:49:39]`, S4-R38; trend-line — S8
`[00:28:52]`, `[00:30:37]`, `[00:31:44]`, `[00:35:55]`; scalp — S5 `[00:20:02]`, `[00:20:36]`,
`[01:41:45]`, `[01:42:50]`, S8 `[01:34:48]`, `[01:35:25]`, `[00:44:49]`, S2 `[01:26:28]`.

| Key | Before | After | Confidence |
|---|---|---|---|
| `module_chart_patterns_enabled` | false | unchanged, **rationale re-sourced** to S4-R38 "never on a pattern alone" | `stated` |
| `module_trendline_break_enabled` | false | unchanged | `stated` (disavowal) / `inferred` (default) |
| `module_scalp_enabled` | false | **true** | `inferred` |
| `scalp_tf_floor` | `"15m"` | **`"30m"`** | `stated` |

Three disavowals, three different kinds. Patterns: he never says they don't work, he says
*pattern-only* trading didn't work for him once, and describes trading pattern breakout+retest as his
own method. Trend-line: the objection is operational (no hard stop, must be babysat) — the one
objection in the corpus that does not transfer to a bot, but not enough to flip the default. Scalp:
*"I suck at scalping"* is a personal-fit statement framed identically to *"chop is weakness"* and *"I
suck at trading XRP"*, and he finishes it *"and if you're good at scalping, then this is going to be
heaven for you"*; what he quit is 150-trades-a-day sub-15m day trading. He names the 2H as his own
favourite scalp chart. A hard veto also left `max_loss_pct_scalp`, `tp_count_scalp`,
`dca_count_scalp_max` and `scalp_excludes_btc` as dead code.

**This reverses CF-37 and is the one recommendation marked `inferred` against a prior verdict.**
Counter-evidence, recorded: his own live S8 scalp session went **1 for 3** (S8 `[01:57:24]`). That is
the argument for the 30m floor rather than for the veto. **Sweep** `module_scalp_enabled` ×
`scalp_tf_floor` {15m, 30m, 1H} × `scalp_tf_ceiling` {2H, 4H}; decider = **expectancy per scalp trade
net of `fee_taker_bps` and `slippage_market_bps`** — fees are the whole argument on low timeframes and
a gross-P&L metric gives the wrong answer. Secondary guard: max drawdown.

### Q15 — Golden pocket: 0.66 or 0.65, and is it ever the 0.786 — **`stated`, no config change**

**Evidence:** S6 `[01:26:22]`, `[01:40:01]`, `[01:40:37]`, `[01:38:53]`, `[01:41:14]`–`[01:41:52]`,
`[02:03:52]`, `[01:53:26]`, `[01:56:54]`–`[01:57:29]`; TBOT1 `[00:03:31]`, `[00:26:30]`.

All three parts confirmed: golden pocket = [0.618, 0.66]; 0.786 is a separate DCA level; 0.886 stays
off by his own arithmetic (*"I use the three middle ones"* of {886, 786, 66, 618, 236}). No key moves.

**Documentation fix applied:** the claim that *"S8 uses golden pocket and 0.786 interchangeably"* is
**struck**, not down-weighted. It rested on two timestamps and neither supports it — `[01:07:57]`
mentions the GP with no 0.786 present, and `[01:14:50]` reads *"lines up with the golden pocket, the
786 fib"*, a two-item list whose conjunction the auto-captioner dropped, exactly as at S6
`[01:32:28]`. In ~20 co-occurrences he enumerates them as two levels in the same order every time.

Reading note recorded on `fib_entry_level`: it means *"the fib level that may coincide with an
entry"*, never *"where entries go"* — *"my entry is always going to be an SR point or a resistance
point"* (S6 `[01:57:29]`).

---

## DISCORD CHECK 2026-09-15 — the written trade record

A fourth source opened up: his own Discord. Not the class transcripts, not the videos — the posts
where he calls trades in real time and then says what happened. 44 posts read across
`#arshmeister-updates` (30, 2025-11-06 → 2026-09-14), `#arsh-active-calls` (4 — the channel was
created 2026-09-12, so that is its complete history) and `#inside-the-mind-of-arsh` (10), plus
server-wide `from:arshmeister` searches on *loss* (95 hits) and *port* (83 hits).

Every figure below is **post text read as characters from the DOM**. Nothing was transcribed off a
screenshot, and numbers that exist only inside his posted chart images are deliberately absent.

### Q16 (new) — how far behind price does he actually bid? — `absent`, range bounded

He states no max-distance gate anywhere. What the record does give is ten entry/DCA ladders:

| date | sym | entry | ladder below entry |
|---|---|---|---|
| 2025-11-06 | ICP | 6.08 (CMP) | -17.76% |
| 2025-11-07 | LINK | 16.07 (CMP) | -5.60% |
| 2025-11-07 | TAO | 409.7 (CMP) | -10.28% |
| 2025-11-13 | BTC | 100.1k (CMP) | -2.70% / -7.09% |
| 2026-09-12 | SUI | 0.79 | -12.06% / -17.24% |
| 2026-09-12 | PUMP | 0.003855 (CMP) | -14.89% / -23.74% |
| 2026-09-12 | ETH | 2370 | -9.28% / -17.51% |
| 2026-09-12 | ZEC | 1045 | -14.83% / -27.18% |
| 2026-09-12 | HYPE | 77 | -6.49% / -14.29% |
| 2026-09-14 | SOL | 104.5 (CMP) | -6.22% |

First rung below entry: median 9.78%, p90 14.89%, max 17.76%.
Deepest rung: median 15.76%, p90 23.74%, max 27.18%.

Six of the ten entries are explicitly at market (*"at CMP"*, *"here at"*, *"bought back into BTC
here at 100.1k"*), so for those entry == close at post time and the ladder percentages **are**
distances below spot. That is the mapping that makes this usable for a close→entry gate.

`G0` in `pipeline.py` rejected only a retest on the *wrong* side of the close
(`anchor_beyond_price`, 12.7% of candidates in SAMPLE_RUN). Nothing bounded a right-side entry
that was absurdly far away; `distance_pct` existed only as a dashboard display column.

| Key | Before | After | Confidence |
|---|---|---|---|
| `max_entry_distance_enabled` | *(did not exist)* | **False** | `absent` — [OUR CHOICE] |
| `max_entry_distance_pct` | *(did not exist)* | **15.0**, `sweep_bracket=(5.0, 27.5)` | `absent` — range from the ladders |

Off by default on purpose: this file's own convention is that an `absent` finding invents no value
and changes no behaviour. 15.0 sits on the median deepest rung and just above the p90 first rung;
27.5 is his observed maximum (ZEC 1045 → 761) and the never-seen-wider bound.

**Regression test:** `tests/test_pipeline.py` — four tests. Default-off proven over the whole
synthetic series, a 0.05% ceiling proven to fire `G0:entry_too_far`, a 100% ceiling proven to leave
the run bit-for-bit identical, and the TRIGGER family proven exempt (CF-16: a trigger is a stop
order, not a resting bid, so distance is meaningless for it).

**UNRESOLVED:** the 2026-09-12 batch (SUI/PUMP/ETH/ZEC/HYPE) is his one set of genuine resting
entries below price — *"Levels are in black also. If they don't fill, then so be it."* Their true
close→entry distance needs spot at 2026-09-12T19:40Z per symbol and is not computable from text.
Pull it from bybit to tighten the bracket. By 2026-09-14 he reports ZEC/SUI/HYPE filled
(*"bottom ticked some entries"*), so that batch filled inside ~2 days.

### Position sizing — corroborates Q8, and it is `% of port`, per rung

He sizes in **percent of portfolio per rung**, not per position:

| date | evidence |
|---|---|
| 2025-11-04 | BTC *"here at 101.2k - 2% of port. Will buy at 93 and 88k if we get it with 2% each"* → 6% max across 3 rungs |
| 2025-11-06 | ICP *"Buying 2% here at CMP (6.08)... Will dca at $5 with 2%"* → 4% |
| 2025-11-07 | LINK *"Bought LINK at CMP (16.07) - 2%... DCA: 15.17 - 2%"* → 4% |
| 2025-11-08 | TAO/LINK *"I am holding my positions both are 4% of my port"* |
| 2025-11-13 | BTC *"No more than 8% of my port will be allocated"* |
| 2025-10-15 | SOL *"back to 10% allocation of total port"* |
| 2025-12-15 | PENGU *"only 3% of my port"* |
| 2025-08-23 | ETH *"Risking max 2%"* (entry 4654, DCA 4567, SL = manual daily close below 4400) |

Portfolio-level restraint is explicit and repeated: *"Only 10% of my port is in the market right
now"* (2025-10-30), *"Bear market you don't full port"* (2025-11-04). Nothing here contradicts the
Q8 correction; it corroborates the risk-first model at a coarser grain — 2% per rung is the unit,
8-10% is the per-idea ceiling.

### Outcomes — what he counts as good and bad

Losses, stated as a percentage **of the play, not the port**, unless he says otherwise:

| date | outcome |
|---|---|
| 2025-08-29 | Fartcoin *"4% net loss on the play (not the port)"*; LTC *"8% loss on the play after we took TP and recompounded"* |
| 2025-09-01 | Cutting all: SOL -3.8%, SUI -7%, AVAX -7% |
| 2025-10-01 | BTC short stopped, avg 15930.9, *"Loss of 1%"* |
| 2025-11-22 | TAO closed *"for a 33% loss on the position. For me it was 11k"*; month total *"Down total of 30k which equates to 12% of my portfolio"* |
| 2026-09-14 | NUDES *"Ive accepted this will go to zero... No more shitcoin calls from me"* (bought $15.5M mcap, -41%) |

Wins:

| date | outcome |
|---|---|
| 2025-11-04 | ZEN 18.11 → 23.62, *"up a massive 32% unleveraged"*, fully closed |
| 2025-11-07 | ICP *"almost a 20% move overnight. Currently up 9%. This will go higher but I'm closing this and adding at same entry if we get it"* |
| 2025-11-11 | LINK *"Closed 40% of LINK at 16.74 for an 8% move"* |
| 2025-10-15 | SOL added 40% back at 203.54 after TP1, average 211.44 |
| 2026-09-14 | ZEC +15%, HYPE +6%, SUI breakeven on the DCA |

The shape is consistent: he scales out in fractions (40%), re-adds at the same level, and treats
closing and re-entering at the same entry as normal rather than as a missed trade.

### Stated logic worth encoding

- **Hard invalidation, never soft.** *"an invalidation level should be hard, I dont like when
  people use soft stop losses. If it loses a level... it should be stopped and you look to
  re-enter later"* (2025-09-07). Reinforced after the October 2025 crash: *"this is why I stress
  the important of not using soft stoplosses... keep a hard stop just incase"* (2025-10-13).
- **Invalidation is a close, not a wick.** ETH SL = *"manual daily close below 4400"*; Fartcoin
  *"lose this and close below on daily I am cutting"*.
- **Leverage is not the risk knob.** *"leverage is 100% irrelevant... Its always position size and
  calculating your stop loss based on position size or quantity size thats how you determine
  risk"* (2025-08-26). And *"Spot > leverage. Enough said"* (2025-10-13).
- **Expectancy over hit rate.** *"in this market, the best traders will have more losses than wins
  probably but will remain profitable with high RR"* (2025-10-30).
- **No setup, no trade.** *"You should only trade if there is a set up there, you have a plan and
  able to execute without any emotions"* (2025-10-30).

None of these are new rules — they corroborate CF-16, the hard-stop reading and the risk-first
sizing model from independent, dated, written evidence rather than from the transcripts.

### Bug found and fixed on the way

`config.write_default_yaml()` called `Path.write_text()` with no `encoding=`. On Windows that is
cp1252, so regenerating `configs/default.yaml` silently rewrote every em-dash and `§` in the file
as mojibake — 222 lines changed for a 2-key addition. Now pinned to `encoding="utf-8"`; the
regenerated file is byte-clean and the diff is 7 insertions.

---

## What is still genuinely unresolved

| # | What | Why it cannot be closed from the corpus |
|---|---|---|
| **Q6(a)** | The swing-detection candle count (`swing_k`) | No fractal width, lookback or N-bar rule appears anywhere in eight sessions. He never counts candles either side of a pivot, not once. His swing points are ordinal, relational and explicitly multi-valued at one instant — *"It doesn't matter which one"* (S6 `[01:21:06]`). `swing_k = 3` stays a placeholder and stays **[OUR CHOICE]**. |
| **Q13** | `sufficient_gap_pct_by_tf` on **2H, 4H, 8H, 12H** (and 3D+) | Nothing is given for any of them — precisely the timeframes he trades most. Worse, they are not interpolable: his 1H→1D and 1D→2D slopes disagree by a factor of three, so no single exponent fits both anchors. |

Five further sub-parts are answered at the level of the *rule* but rest on numbers the corpus does not
contain, and belong to a sweep rather than to him: the touch-decay **curve** (Q2), the TP split for
**n≥4** (Q4), the confluence **weights** (Q5), the MSB retest **timeout** (Q11 — he refuses to bound
it, so this may never have an answer) and the mid-range **band width** (Q12 — he gates on a state, not
a distance, so the question may be the wrong shape).

---

## Files changed

| File | Why |
|---|---|
| `bot/tbot/config.py` | 8 new keys; 9 changed defaults; every touched key's `source_id`/`note` rewritten to carry its confidence label and evidence timestamp |
| `bot/configs/default.yaml` | Regenerated from `config.py` — 242 keys, each with its source ID and timestamp |
| `bot/tbot/risk.py` | Q8: `margin_ceiling_usd`, the corrected notional ceiling, the margin × leverage bound |
| `bot/tbot/plan.py` | Q10: `presr_light_limit_enabled` wired into `dca_leg_count` |
| `bot/tbot/primitives.py` | Q5: `ConfluenceResult.count` and the raw-count gate in P14 |
| `bot/tbot/confluence.py` | Q5: count carried through the cluster; `map_conviction` takes it |
| `bot/tbot/qualify.py` | Q5: G5 gates on the object count |
| `bot/tbot/detectors/orderblocks.py` | Q1: `ob_invalidation_pct` (activates P15); Q6: `dir_change_gap_reason` |
| `bot/tbot/detectors/sfp.py` | Q6: `raid_price` carve-out; Q7: the `highest_valid` search |
| `bot/tbot/detectors/structure.py` | Q11: deviation detection and `MSB.deviation_index` |
| `bot/tbot/INTERFACES.md` | §7 ownership table: 8 new rows, every row's default and source refreshed from `KEY_SPECS` |
| `CONFLICTS.md` | Reversal notes inside CF-02/03/07/08/11/16/18/20/22/26/28/31/33/37, the status table, and the struck questions |
| `SPEC.md` | §5.5 30m row, §8.3 ladder, §10.7 ceilings, §11 tables, §13 disowned modules, §14 status |
| `bot/SAMPLE_RUN.md` | Re-run on the new defaults |

---

## Files changed (DISCORD CHECK 2026-09-15)

| File | Why |
|---|---|
| `bot/tbot/config.py` | 2 new keys (`max_entry_distance_enabled`, `max_entry_distance_pct` with `sweep_bracket`); `write_default_yaml` pinned to UTF-8; key-count strings 245 -> 247 |
| `bot/configs/default.yaml` | Regenerated - 247 keys, byte-clean UTF-8 |
| `bot/tbot/pipeline.py` | `G0:entry_too_far` wired beside `anchor_beyond_price`, gated on the new switch |
| `bot/tbot/INTERFACES.md` | 2 rows in the §7 `pipeline.py` ownership table; counts 245 -> 247 |
| `bot/tbot/cli.py`, `bot/tbot/dashboard/{gates,server,settings}.py` | Count prose 245 -> 247 |
| `bot/tests/test_pipeline.py` | 4 regression tests; `_ALLOWED_KEYS` gains the 2 keys |
| `bot/tests/{test_primitives,test_integration,test_dashboard}.py` | Count invariants 245 -> 247 |
| `SPEC.md` | §11 total line and the 11.3 row record the 2 Discord-derived additions |

---

### Q17 — What happens when the stop cannot sit beyond the whole entry ladder — **`derived`**

Not one of the original fifteen. It was raised by a measured defect: the backtest fills DCA rungs
on the far side of the trade's own stop - the bot adds size at a price where its stop says the
trade is already dead. 26 of 112 trades, **-958.95, 79 % of the total loss, zero winners**
(`GAPS.md`). Two sessions had concluded this was a rule choice the sources do not make, and that
Rhys had to pick a remedy. **The recordings make it.**

**Evidence — four independent passages, four sessions:**

1. **TBOT1 `[00:38:08]`** - the closest to a stated rule. *"ladder all the way till honestly like
   **I would want a wider stop**. Um ladder all the way to like 260ish. **I wouldn't have a DCA
   there.**"* He prices the ladder against the stop he could actually place, and declines the rung
   rather than accept a stop inside it.
2. **S6 `[01:11:53]`-`[01:12:28]`** - **the exact CF-14 step-3 collision, worked on tape.** The stop
   cannot go where he wants because an opposing zone is in the way: *"stop loss very hard to place
   here... if I place it here below this wick, it's basically in... another support area/demand
   zone."* His resolution: *"You can have DCA there and then **probably a tighter stop. It's going
   to be have to be here.** Okay. So, there **then probably DCA there.**"* He takes the tighter
   stop - step 3 wins, as `CONFLICTS.md` already rules - and then **re-sites the DCA inside it**.
   The ladder yields to the stop.
3. **S6 `[00:23:05]`-`[00:23:39]`** - when the geometry will not allow it, the rung is dropped
   entirely: *"this is in a range where **you do not have a DCA**. Now, stops on this one was tough,
   right? Cuz like you can't put it down here. So, the only stop that you could have put was like
   right there."* ... *"If you had no DCA, you got like a 5.2 % move."*
4. **A one-entry trade is normal and sanctioned**, so dropping the rung costs nothing structurally:
   S8 `[00:31:44]` *"you don't DCA on these type of plays. Okay? These are only **one entry, one
   stop loss**"*; S8 `[01:02:28]` *"**You can have one DCA or no DCA.**"*; S5 `[00:41:10]` *"Or you
   have **no final DCA. You just have one stop-loss.**"*

**Counter-examples: none found.** Across roughly fifteen worked chart examples in S5-S8 and TBOT1
the ordering is invariably entry -> DCA -> stop, with the stop beyond the whole ladder (S5
`[00:51:21]`, S6 `[00:13:11]`, `[00:42:25]`, `[01:27:35]`, `[01:35:26]`, S7 `[00:06:41]`, S8
`[00:48:34]`, `[01:03:38]`, `[01:19:57]`, `[01:28:33]`). Searches for a stop placed *between* entry
and DCA returned nothing. This is a grep-and-read sweep of 112k words, not a proof of exhaustiveness.

**The rule:** *the stop constrains the ladder, not the reverse.* A rung that would sit beyond the
placeable stop is not placed - it is moved inside the stop, or dropped, and a one-entry trade is an
acceptable outcome.

**What the bot does instead:** `build_plan` sites the ladder first, `place_stop` then lets the
CF-14 step-3 clip move the stop *inside* that ladder, and nothing re-checks. `place_stop` already
holds the principle for one branch - `beyond_price=_ladder_extreme(rungs)`, *"a stop that does not
invalidate the whole ladder is not a stop"* - but only inside the F6 zone-fraction branch, and
step 3 runs after it.

**Status: this reverses nothing.** It does not touch the `CONFLICTS.md` precedence ruling that step
3 overrides F6 - S6 `[01:12:28]` has him take the tighter stop too. It adds what happens to the
ladder *afterwards*, which the ruling never addressed. **This is an extraction gap, not a rule
choice, and not a judgement call for the user to make.**

Not yet applied. Per the standing convention it ships behind a flag defaulted off and is measured
against the current book before anything changes.

---

## Q18 — Is the notional ceiling his rule? — **`stated`, and it is not**

Raised by the Q17 measurement: fixing the ladder geometry doubled the book's loss because it
widened stops, which released a size cap nobody had identified as binding. Chasing what the cap
actually is leads here.

### His sizing rule, stated as a rule

**S7 `[00:25:54]`** — the only place he teaches sizing as a procedure rather than mentioning a habit:

> *"you have a $1,000 portfolio. **You enter each play with 10 % of your portfolio.** Okay. So uh you
> know **whatever the leverage is you calculate that you only lose four to 5 % of your port** in that
> swing play."*

Two quantities, and only one of them is fixed:

* **margin = 10 % of portfolio** — fixed.
* **leverage = whatever makes the stop-out loss 4-5 %** — *derived from the stop distance*.

Corroborated as a target rather than a cap at **S7 `[00:14:13]`** (*"you're going to be playing with
your position size in advance that you lose no more than four to 5 %"*) and **S2 `[01:47:44]`**
(*"a swing play go in with four to 5 % risk if your stop loss to get hit"*).

### Where the 10x came from, and why it is not a rule

**S2 `[01:52:12]`** is the sole "10x" statement, and it is a spreadsheet walkthrough, not a method:

> *"Position long. Leverage. **I always do 10x, but whatever leverage you put, go ahead and put
> there.**"*

He is filling in a column of his trading-log template and generalises it away in the same sentence.

### The defect

`max_notional_pct_leverage = 100.0`, and its own note states the derivation: *"10 % margin x 10x
default leverage = 100 % of equity."* **That hard-codes the habit as a constraint.** Solving his
actual rule:

    L = 0.4 / stop_distance          notional = 0.10 x equity x L

| stop distance | required leverage | required notional |
|---|---|---|
| **4.00 %** | **10.0x** | **100 % of equity** <- the shipped ceiling |
| 2.00 % | 20.0x | 200 % |
| 1.00 % | 40.0x | 400 % |
| 0.549 % | 72.9x | 729 % |

**The ceiling is exactly the notional his method needs at a 4.00 % stop.** It is not a cap he
states; it is one stop width frozen into a constant. Every tighter stop is silently under-sized,
and tighter is almost all of them - measured stop distances reach 4 % on **5 of 77** in-sample and
**1 of 35** out-of-sample.

Consequence, measured on the shipped baseline: median realised risk is **$57.14 against a $400
budget in-sample (7.0x under) and $25.32 out-of-sample (15.8x under)**.

### This is Q8, half-fixed

Q8 found `max_notional_pct_leverage = 10.0` was his *margin* figure enforced as a *notional*
ceiling, under-risking by ~5x, and corrected it to 100.0 by multiplying margin by 10x. That
corrected the margin/notional confusion and **preserved the fixed-leverage assumption underneath
it**, which S7 `[00:25:54]` contradicts directly. The same bug, one layer down.

### What follows - and it is not good news

Under his stated rule the bot should be risking 4-5 % per swing trade. It has been risking a median
of 0.57 % in-sample. **Every result this project has produced was measured on a book trading roughly
one seventh of its intended size**, including the "no out-of-sample edge" verdict. Correcting it
does not improve that verdict; it scales the losses toward their intended magnitude. Q17 already
showed the shape of this - risk up 2.3x, loss up 2.1x.

**No default changed here.** The correct ceiling is not another constant: his rule derives notional
rather than capping it, so any fixed percentage re-commits the same error at a different number. A
real cap belongs on *leverage*, as an exchange limit, and that number is not in the corpus. The key
already accepts up to 1000.0, so the measurement runs through `--set` with no code change.

### Addendum — no leverage cap is sourced, and his rule does not need one

Confirmed independently: **no maximum leverage is stated anywhere in the corpus.** Only casual
mentions ("I always do 10x", "10x leverage or 20x leverage"), nothing prescriptive. His rule as
extracted is therefore *unbounded* - it derives notional and never caps it.

So **whatever replaces 100.0 is `[OUR CHOICE]` exactly as 100.0 was**, and must carry the marker and
a sweep bracket. Correcting an unsourced constant by substituting a different unsourced constant and
calling it his is the specific failure this file exists to prevent.

**But the unboundedness is less alarming than it looks, because his rule is scale-invariant in the
ratio that matters.** With margin fixed at 10 % of equity and leverage solved so the stop-out costs
4 %, the stop always sits at the same fraction of the distance to liquidation:

    stop at d = 0.4 / L        liquidation at 1 / L        d / (1/L) = 0.40, for every L

| leverage | stop | liquidation | stop as a share of the way there |
|---|---|---|---|
| 10x | 4.000 % | 10.000 % | 0.40 |
| 40x | 1.000 % | 2.500 % | 0.40 |
| 72.9x | 0.549 % | 1.372 % | 0.40 |
| 200x | 0.200 % | 0.500 % | 0.40 |

**The stop is 40 % of the way to liquidation at any leverage.** Raising the ceiling therefore does
not move the position closer to liquidation - that ratio is fixed by his own 10 %-margin / 4 %-risk
pair. The engine models liquidation (`engine._check_liquidation`), so this is checkable rather than
assumed, and the runs below report `liquidations`.

What *does* scale with notional is **fees and funding**, both charged on notional in §12.3. At 729 %
of equity they are 7.3x what the shipped book paid, against an in-sample `total_funding_usd` of
38.06 and `total_fees_usd` of 293.57. A cap is therefore a practical necessity (exchange limits,
funding drag) rather than a risk-control one - which is precisely why it is ours to choose and must
be marked, swept, and never presented as his.

### The 2x2, because one cell is not interpretable

Sizing corrected with Q17 **off** leaves the broken ladder geometry in place, and derived leverage on
the tightest measured stop is ~19,000x. That is the ladder defect read through a corrected sizing
rule, not his method. Q17 **widens** stops and so **lowers** derived leverage, while the sizing
correction **raises** size - the two push opposite ways, and only the pair states what his method
does. All four cells are therefore measured:

| | ceiling 100 % (shipped) | ceiling 1000 % |
|---|---|---|
| Q17 off | the baseline | where the new ceiling sits |
| Q17 on | -1202.21 / -1015.53 | **his method** |
