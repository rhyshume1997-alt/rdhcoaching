# SPEC.md — Consolidated trading-bot specification

**Status:** implementable. This file supersedes the extracts for anything it covers.
**Authority order:** `CONFLICTS.md` (binding wherever it has ruled) → the eight per-session
extracts (`extracts/*.md`) for anything CONFLICTS.md does not cover → this document's own
engineering choices, every one of which is marked **[OUR CHOICE]**.

**Source-ID convention.** Every rule below carries at least one source ID:

| Prefix | Meaning | Example |
|---|---|---|
| `S2`–`S8` | Session extract rule / ambiguity / contradiction note | `S5-R28`, `S6-A12`, `S7-C2` |
| `TBOT1` | Live walkthrough extract | `TBOT1-R17` |
| `CF-nn` | Reconciled verdict in CONFLICTS.md | `CF-08` |
| `Pn` | Undefined primitive, algorithm supplied by CONFLICTS.md | `P14` |
| **[OUR CHOICE]** | Engineering decision with no basis in the corpus | — |

Anything marked **[OUR CHOICE]** is ours, not the trader's, and must never be described to him as
his. Keys that CONFLICTS.md marks "**OUR number**" carry the same warning and are the first
parameters to sweep in a backtest.

---

## 1. System overview

1. The bot is a **signal-generation and backtesting system** for discretionary-style crypto
   technical analysis, mechanised from an eight-session course plus one live walkthrough.
2. It ingests OHLCV candles for a small symbol universe across a fixed timeframe ladder
   (`15m, 30m, 1H, 2H, 4H, 8H, 12H, 1D, 2D, 3D, 1W`) and marks up each chart in a fixed order
   (S6-R28, CF-32).
3. Detectors produce price objects: support/resistance levels and SR flip points, trend lines,
   ranges, supply/demand zones, order blocks, swing points and market structure, SFPs, fib levels
   and chart patterns (S6-R28, S4-R38, S7-R30).
4. Objects that coincide at one price are merged into a **deduplicated weighted confluence score**
   (CF-31, P14); a candidate needs `min_confluence_count` ≥ 3.0 across ≥2 distinct classes.
5. Candidates pass a gate stack — regime/macro context (CF-35), calendar (CF-39), universe
   eligibility (CF-40), R:R (CF-42), mid-range (CF-25), trend and shorting policy (CF-41).
6. A survivor becomes a **fully specified TradePlan**: entry ladder with per-rung sizes, one stop,
   2–5 take-profits, position size solved backwards from the portfolio risk budget, and a
   vehicle decision (spot vs leverage) (CF-01, CF-17, CF-18, CF-27, CF-28, CF-06).
7. A trade-management state machine defines every transition after the plan is armed, including
   stop trailing on TP hits (CF-29) and re-anchoring on DCA fills (S8-R20).
8. A bar-by-bar backtest harness simulates plans historically with explicitly conservative
   intrabar fill assumptions, fees and slippage, and reports win rate, expectancy, max drawdown,
   R distribution and per-detector attribution.
9. **Live order execution is out of scope.** The system emits plans; it does not place orders.
   All exchange interaction sits behind `ExecutionAdapter`, an interface with **no implementation**
   in this build (see §12.6). Nothing in this spec may call an exchange API. **[OUR CHOICE]**
10. The instructor's claimed 77–82% win rate (S5 `[00:38:20]`, S5-A19) is recorded as a
    **hypothesis for the backtest to test**, never as a design assumption (CONFLICTS.md
    "Dismissed as apparent-only": *do not encode as a target*).

---

## 2. Data model

All prices are `Decimal`. All timestamps are timezone-aware UTC. All sizes are in base-asset
units unless suffixed `_usd` or `_pct`. `tf` is a member of the timeframe ladder (CF-24).

### 2.1 Candle

| Field | Type | Notes |
|---|---|---|
| `symbol` | `str` | e.g. `"SOLUSDT"` |
| `tf` | `Timeframe` | enum over the ladder (CF-24) |
| `open_time` | `datetime` | bar open, UTC; daily bars key off `day_boundary_utc` (CF-45, P16) |
| `close_time` | `datetime` | bar close, UTC |
| `open, high, low, close` | `Decimal` | |
| `volume` | `Decimal` | base units |
| `quote_volume` | `Decimal` | USD-equivalent, for P18 liquidity screen |
| `is_closed` | `bool` | detectors read **only** closed bars (P1: no repainting) |
| `body_high` | `Decimal` (derived) | `max(open, close)` — structure source (S7-R11, S5-R44) |
| `body_low` | `Decimal` (derived) | `min(open, close)` |
| `upper_wick` | `Decimal` (derived) | `high - body_high` |
| `lower_wick` | `Decimal` (derived) | `body_low - low` |
| `is_green` | `bool` (derived) | `close > open` (S6-R1/R2 colour mapping) |
| `venue_kind` | `Literal["spot","perp"]` | perp setups must use perp candles (S6-R43) |

### 2.2 SwingPoint

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `symbol`, `tf` | | |
| `kind` | `Literal["high","low"]` | |
| `bar_index` | `int` | index of the pivot bar |
| `price` | `Decimal` | body extreme, not wick (P1, S7-R11) |
| `wick_price` | `Decimal` | the wick extreme at the same bar — used for stops (CF-14) and SFP raids |
| `confirmed_at_index` | `int` | `bar_index + swing_k`; unusable before this (P1) |
| `k` | `int` | the `swing_k` used |

### 2.3 Level

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `symbol`, `tf` | | `tf` = the structure timeframe it was built on (CF-24) |
| `price` | `Decimal` | volume-weighted mean of member pivots (P3) |
| `kind` | `Literal["support","resistance","sr_pending","sr_confirmed_support","sr_confirmed_resistance","range_high","range_low","mid_range","trendline"]` | S2 state machine + S4 range roles |
| `member_pivot_ids` | `list[str]` | (P3) |
| `touch_count` | `int` | per P4 counting rules |
| `touch_history` | `list[tuple[int, Decimal]]` | (bar_index, price) per counted touch |
| `created_index` | `int` | |
| `flip_state` | `FlipState` | see §5.2 state machine (CF-15) |
| `pending_since_index` | `int \| None` | drives `pending_sr_expiry_bars` (CF-15) |
| `break_move_away_pct` | `Decimal \| None` | SR quality score (S2-R6) |
| `is_untested_sr` | `bool` | strongest rejection candidate (S6-R39) |
| `tolerance` | `Decimal` (derived) | `level_tolerance_atr × ATR(atr_period)` (P4, P9) |
| `slope_per_bar` | `Decimal` | non-zero only for `trendline` (S6-R28: "diagonal S/R") |
| `anchor_indices` | `list[int]` | trend-line touch bars; ≥3 required (S2-R14, S3-R19, S4-R20, S5-R1, S8-R7) |

### 2.4 Zone

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `symbol`, `tf` | | |
| `side` | `Literal["demand","supply"]` | |
| `zone_class` | `Literal["continuation","reversal"]` | his definition vs textbook (CF-10) |
| `box_top`, `box_bottom` | `Decimal` | body-anchored, small wicks included (CF-13, P5) |
| `midpoint` | `Decimal` | frozen at creation; never re-measured (P6, CF-08) |
| `body_count` | `int` | ≥ `min_zone_bodies` (S5-R17) |
| `formation_start_index`, `formation_end_index` | `int` | |
| `breakout_index` | `int` | bar the consolidation broke (P10) |
| `move_away_pct`, `move_away_atr` | `Decimal` | must pass both gap tests (CF-11) |
| `depth_atr` | `Decimal` | must be in `[min_zone_depth_atr, max_zone_depth_atr]` (CF-12) |
| `fill_pct` | `Decimal` | deepest penetration as % of depth (P6) |
| `is_dead` | `bool` | `fill_pct ≥ zone_fill_invalidation_pct` (CF-08) |
| `rescued_by_level_id` | `str \| None` | HTF-support rescue of a dead zone (CF-08, S7-R4) |
| `touch_count` | `int` | drives `touch_size_decay` (CF-07) |
| `contained_ob_ids` | `list[str]` | zone boundaries govern over a contained OB (CF-09, S6-R31) |
| `entry_price_pmt` | `Decimal` | point-of-most-touch entry price (P20, S5-R23) |
| `wick_band_top`, `wick_band_bottom` | `Decimal \| None` | **F1** outer wick band; both `None` unless `zone_wick_band_enabled` (§5.5) |

Derived properties: `outer_edge` (the edge price reaches first — where the **entries** are priced),
`body_stop_edge` (the far edge of the **body** box — where the **F6** stop is measured from, §8.5)
and `wick_band_stop_edge` (the far edge of the F1 band, or `None`).

### 2.5 OrderBlock

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `symbol`, `tf` | | |
| `side` | `Literal["bullish","bearish"]` | bullish = last **red** candle before an up move; bearish = last **green** candle before a down move (S6-R1, S6-R2, CF-09; S7-C4 discarded) |
| `bar_index` | `int` | exactly one candle (S6-R3, `ob_max_candles = 1`) |
| `box_top`, `box_bottom` | `Decimal` | body under the P5 wick test (`ob_box_source`) |
| `dir_change_index` | `int` | the directional change it precedes (P2) |
| `dir_change_atr_move` | `Decimal` | (P2) |
| `liquidity_taken_pct` | `Decimal` | P15, used only if `zone_fill_invalidation_pct` is set to the S7 values |
| `fill_pct` | `Decimal` | same measure as Zone (P6) |
| `is_dead` | `bool` | (CF-08, S8-R21) |
| `parent_zone_id` | `str \| None` | if set, `ob_inside_zone_precedence = "zone_wins"` (CF-09) |
| `size_atr` | `Decimal` | rejects "smaller than a pinky nail" blocks numerically (S7-R6, S7-A5, CF-12) |

### 2.6 Setup (a scored candidate, pre-qualification)

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `symbol` | `str` | |
| `direction` | `Literal["long","short"]` | |
| `trade_tf` | `Timeframe` | where the entry is placed |
| `structure_tf` | `Timeframe` | `trade_tf + structure_tf_offset` (CF-24) |
| `trade_class` | `Literal["swing","scalp","counter_trend","price_discovery"]` | CF-38 boundary: swing floor 4H, scalp ceiling 2H |
| `anchor_price` | `Decimal` | the price the confluence stacks on |
| `object_ids` | `list[str]` | contributing Levels/Zones/OrderBlocks/fibs/patterns/SFP |
| `confluence_score` | `Decimal` | weighted, deduplicated (CF-31, P14) |
| `confluence_classes` | `set[str]` | ≥2 required (`single_class_trade_forbidden`) |
| `entry_family` | `Literal["retest","flip_pending","trigger"]` | CF-16 |
| `regime_flags` | `dict[str, Any]` | USDT.D / BTC.D / BVOL / all-pairs veto (CF-35) |
| `vetoes` | `list[str]` | populated by §7 gates; non-empty ⇒ no plan |
| `conviction` | `Literal["low","normal","high"]` | drives size modifiers (CF-01, CF-02, CF-07) |
| `created_index` | `int` | |

### 2.7 TradePlan

| Field | Type | Notes |
|---|---|---|
| `id`, `setup_id` | `str` | |
| `symbol`, `direction`, `trade_class` | | |
| `vehicle` | `Literal["spot","leverage"]` | CF-05, CF-06, CF-40 |
| `leverage` | `Decimal` | 1.0 for spot; ≤ `leverage_downgrade_max_multiple` on a downgrade (CF-06) |
| `entries` | `list[EntryRung]` | 1–3 rungs (CF-17) |
| `stop_price` | `Decimal` | one stop; duplicated at execution by `duplicate_stop_offset_bps` (S4-R34) |
| `stop_is_synthetic` | `bool` | true for spot: sizing-only, no resting order (CF-05) |
| `spot_exit_rule` | `str \| None` | `"close_below_level_then_flip"` (CF-05, TBOT1-R18) |
| `take_profits` | `list[TakeProfit]` | 2–5 (CF-27) |
| `qty_total` | `Decimal` | solved from the risk budget (S6-R12, CF-01) |
| `notional_usd` | `Decimal` | derived, clamped by CF-02 ceilings |
| `risk_budget_pct` | `Decimal` | the CF-01 cap actually applied |
| `average_entry` | `Decimal` | size-weighted over **filled** rungs; all downstream maths uses this (CF-18) |
| `planned_average_entry` | `Decimal` | assuming full fill; used for pre-trade R:R |
| `rr_to_tp1` | `Decimal` | R:R to the **first** TP; the recorded alternative basis (CF-42) |
| `rr_to_final_tp` | `Decimal \| None` | R:R to the **final** TP — what G14 compares against `min_rr` by default (CF-42, **F9**) |
| `expected_move_pct` | `Decimal` | ≥ `min_expected_move_pct` (CF-41) |
| `invalidation_level_id` | `str` | the level whose loss kills the trade (CF-30) |
| `bias_invalidation_price` | `Decimal \| None` | spot/long-term only (CF-23) |
| `expires_at_index` | `int \| None` | `msb_retest_timeout_bars` / `pending_sr_expiry_bars` |

`EntryRung`: `{ index: int, price: Decimal, size_fraction: Decimal, kind: Literal["entry","dca"],
level_id: str, filled: bool, fill_index: int|None, fill_price: Decimal|None }`
(CF-17, CF-18; DCA prices attach to levels, not fixed increments — S2-R10).

`TakeProfit`: `{ index: int, price: Decimal, size_fraction: Decimal, level_id: str|None,
hit: bool, hit_index: int|None }` (CF-27, CF-28; TPs sit on structural levels — S6-R20, S8-R12).

### 2.8 Position

| Field | Type | Notes |
|---|---|---|
| `id`, `plan_id` | `str` | |
| `account` | `Literal["long_term","spot_short","leverage_swing","leverage_scalp","challenge"]` | S2-R32, CF-43 |
| `state` | `PositionState` | see §9 |
| `qty_open` | `Decimal` | |
| `average_entry` | `Decimal` | recomputed on every fill (CF-18) |
| `current_stop` | `Decimal` | mutated by the trailing rules (CF-29) |
| `stop_reason` | `str` | `"initial" \| "break_even" \| "tp1" \| "tp_n_minus_1"` |
| `tps_hit` | `int` | |
| `realised_pnl_usd`, `unrealised_pnl_usd` | `Decimal` | |
| `mae_atr`, `mfe_atr` | `Decimal` | for P17 and reporting |
| `bars_in_trade` | `int` | |
| `opened_index`, `closed_index` | `int \| None` | |
| `close_reason` | `str \| None` | `"stop" \| "tp_final" \| "trail_out" \| "structural_stale" \| "time_stale" \| "msb_exit" \| "spot_flip" \| "manual"` |
| `touch_index_at_entry` | `int` | the level touch number that produced this trade (CF-07) |
| `r_multiple` | `Decimal \| None` | realised, measured from `average_entry` against the initial stop |

### 2.9 Fill

| Field | Type | Notes |
|---|---|---|
| `id`, `position_id` | `str` | |
| `kind` | `Literal["entry","dca","tp","stop","exit"]` | |
| `bar_index`, `timestamp` | | |
| `price`, `qty` | `Decimal` | |
| `order_type` | `Literal["limit","market"]` | market only for the trigger family (CF-16) |
| `fee_usd` | `Decimal` | `fee_maker_bps` / `fee_taker_bps` |
| `slippage_bps` | `Decimal` | |
| `excess_risk_usd` | `Decimal` | non-zero when a spot exit slips past the synthetic stop (CF-05) |

---

## 3. Analysis pipeline

The canonical pipeline is CF-32, which is S6-R28's chart-preparation order with the fib/pattern
ordering conflict (S6-C2) resolved, cross-checked against the 17-step applied sequence he actually
runs in TBOT1 §14. Stages run in order, per symbol, per `trade_tf`. Every stage reads **closed bars
only**.

### 3.1 Stage table

| # | Stage | Inputs | Outputs | Governing rules | TBOT1 §14 step |
|---|---|---|---|---|---|
| 0 | **Universe & calendar gate** | symbol metadata, volume, event calendar, clock | eligible symbols, vehicle tier, blackout flags | CF-39, CF-40, P16, P18 | 16 (partly) |
| 1 | **Load & align candles** | OHLCV per tf | `Candle[]` per tf; `ATR(atr_period)` per tf | P16 (`day_boundary_utc`), S6-R43 (perp chart for perp) | 1 |
| 2 | **Structure (bodies)** | candles on `structure_tf` | `SwingPoint[]`, trend label, last HL / last LH, MSB flags | P1, P11, S7-R11, S7-R12/R13, S5-R44 | 2, 12 |
| 3 | **Horizontal levels & SR flips** | swing points | `Level[]` with flip state and touch counts | P3, P4, CF-15, S2-R1…R5, S8-R41 | 4 |
| 4 | **Trend lines** | swing points | `Level[]` of kind `trendline` | S2-R14, S3-R19, S4-R20, S5-R1, S8-R7, P3 scoring | 3 |
| 5 | **Ranges & mid-range** | levels | `Range` objects, `mid_range` level, no-trade band | P7, P8, CF-25, CF-26, S4-R3/R4 | 4 |
| 6 | **Liquidity map** | swing points, equal highs/lows | sweep targets (feeds SFP + TP selection) | TBOT1 §14 step 5, S8-R? (equal highs/lows `[00:16:11]`) | 5 |
| 7 | **Supply/demand zones** | candles, levels | `Zone[]` (both classes) with gap and depth validation | CF-10, CF-11, CF-12, CF-13, P5, P10, P13, S5-R15…R19 | 6 |
| 8 | **Order blocks** | candles, dir-change events, zones | `OrderBlock[]`, one candle each | CF-09, P2, P5, S6-R1/R2/R3 | 6 |
| 9 | **Context / regime charts** | USDT.D, BTC.D, BVOL, (DXY off) | regime flags: `risk_on`, `size_multiplier`, `hard_veto` | CF-35, S3-R8/R9/R11/R12, TBOT1-R19/R20 | 16 |
| 10 | **Fibs** | swing pairs on `structure_tf` | golden-pocket band, 0.786, extensions in price discovery | CF-33, CF-34, P1, S6-R32…R36 | 7 |
| 11 | **Chart patterns** | candles, levels, trend lines | `Pattern[]`, confluence-only | CF-37, S4-R17…R28, S4-R38 | 9 |
| 12 | **Confluence scoring** | all objects above | `Setup[]` with deduplicated weighted score | CF-31, P14 | 8 |
| 13 | **SFP (second-order)** | swing points, setups from 12 | SFP triggers attached to existing setups | CF-20, S7-R30, `sfp_evaluated_last` | 9 (late) |
| 14 | **RSI / divergence (confluence-only)** | closes on `structure_tf` | divergence flag, weight 0.5 | CF-36, TBOT1-R11, S8-R39/R40 | 10 |
| 15 | **LTF refinement** | candles on `trade_tf` and below | refined entry price, tightened stop candidates | CF-06, S2-R11, S5-R? (`[00:37:46]`), S8-R15 | 11 |
| 16 | **Setup qualification** | setups + gates | qualified setups or vetoes | §7 (CF-25, CF-31, CF-41, CF-42, CF-35, CF-39, CF-40) | 13, 16 |
| 17 | **Trade-plan construction** | qualified setups | `TradePlan` (entry ladder → stop → TPs, in that order) | §8; TBOT1 §14 step 14 fixes the *order*: entry, then stop, then TPs | 14, 15, 17 |

### 3.2 Ordering rules that the pipeline enforces

| Rule | Statement | Source |
|---|---|---|
| PL-1 | Support/resistance is drawn **first, always**; everything later is subordinate. | S6-R28, S6 `[01:03:33]` |
| PL-2 | Trend lines are diagonal S/R and belong to stage 4, not to the pattern stage. | S6-R28 |
| PL-3 | Fibs are drawn at stage 10 and **lose every tie to drawn S/R**. | S6-R38, `fib_loses_ties_to_sr` |
| PL-4 | Patterns are stage 11 and are confluence only — never a standalone trade. | S4-R38, CF-37 |
| PL-5 | SFP is evaluated **last**, only after price interacts with a level from stages 3/7/8. | S7-R30, `sfp_evaluated_last`, CF-32 |
| PL-6 | Context charts are a gate at stage 9 and **never** generate an entry. | CF-35, TBOT1 §10 |
| PL-7 | Analysis starts on the higher timeframe and drills down; the HTF definition wins where LTF and HTF disagree. | S6-R28, S7-R20, S8 `[00:38:57]`, `htf_veto_enabled` |
| PL-8 | A pattern's confirming retest must occur on the timeframe the pattern was drawn on. | S4-R29 |
| PL-9 | If nothing qualifies, emit no plan. Never force a setup. | S6-R46, TBOT1 §14 step 17 |
| PL-10 | Chart-inversion check (S6-R47) is **not implemented**; it is a human visual aid with no machine analogue. **[OUR CHOICE]** | S6-R47 |

---

## 4. Primitives (P1–P20)

These are the algorithms CONFLICTS.md supplies for concepts the corpus leaves undefined. **All of
them are OUR choices** and are the first sweep targets in any backtest. `ATR(n)` means Wilder ATR
over `atr_period` bars on the object's own timeframe.

### P1 — Swing point (pivot) detection

```
def swing_points(bars, k=swing_k, source=swing_price_source):
    # source == "body": use max(open,close) / min(open,close)   [S7-R11, S5-R44]
    for i in range(k, len(bars) - k):
        window = bars[i-k : i+k+1]
        if body_high(bars[i]) == max(body_high(b) for b in window):
            yield SwingPoint(kind="high", bar_index=i, price=body_high(bars[i]),
                             wick_price=bars[i].high, confirmed_at_index=i+k)
        if body_low(bars[i]) == min(body_low(b) for b in window):
            yield SwingPoint(kind="low",  bar_index=i, price=body_low(bars[i]),
                             wick_price=bars[i].low,  confirmed_at_index=i+k)
    # ties break toward the EARLIER bar; a pivot is unusable until confirmed_at_index. No repainting.
```
Params: `swing_k = 3` (5 on weekly/monthly), `swing_price_source = "body"`.
Answers S2-A12, S5-A16, S7-A7, S8-A2, S6-A1.

### P2 — "Directional change in price" (order-block trigger)

```
def directional_change(bars, j):
    move = extreme_reached(bars, j, within=dir_change_max_bars)   # high for up, low for down
    if abs(move - bars[j].close) < dir_change_atr * ATR(atr_period): return None
    if retraced_more_than(0.33, of=move, before_reaching=move):   return None
    return direction_of(move)
# The order block is the last opposite-colour candle at or before j.  [S6-R1, S6-R2]
```
Params: `dir_change_atr = 2.0`, `dir_change_max_bars = 10`. Answers S6-A1.

### P3 — Horizontal level construction and clustering

```
candidates = [p for p in swing_points(structure_tf) if p.bar_index >= now - level_lookback_bars]
clusters   = single_link_cluster(candidates, radius=level_cluster_atr * ATR(atr_period))
levels     = [Level(price=volume_weighted_mean(c.members))     # machine "points of most touch"
              for c in clusters if len(c.members) >= level_min_touches]
# Re-clustered only on a NEW CONFIRMED pivot. Never on intrabar data.
```
Params: `level_lookback_bars = 500`, `level_cluster_atr = 0.25`, `level_min_touches = 2`
(S4-R4, S7 `[00:05:04]` "two touches is enough"). Answers S2-A3, S3-A7, S4-A2, S5-A15.

### P4 — Touch definition and counting

```
band = level_tolerance_atr * ATR(atr_period)
touch if bar.range intersects [level.price - band, level.price + band]
        AND bar closes on the level's ORIGINAL side
consecutive in-band bars     -> ONE touch
counter increments again     -> only after price leaves the band by >= touch_reset_atr * ATR
body close THROUGH the level -> ends the touch sequence, starts the CF-15 flip machine
counter resets               -> on role flip, or on cluster rebuild
```
Params: `level_tolerance_atr = 0.15`, `touch_reset_atr = 0.5`.
Answers S2-A5, S5-A16, S8-A11, TBOT1-A6.

### P5 — Zone box boundaries

```
box_top    = max(body_high(b) for b in consolidation)      # N >= min_zone_bodies   [S5-R17]
box_bottom = min(body_low(b)  for b in consolidation)
for wick in (upper, lower):
    if wick_len <= wick_include_max_pct/100 * price and wick_len <= wick_include_max_atr * ATR:
        extend box to include it                            # [S6-R9, S7-R7 "~2% include"]
# Single-candle order block: the box is that candle's body under the same wick test.  [S6-R3]
```
Params: `wick_include_max_pct = 2.0`, `wick_include_max_atr = 0.5`. Answers S5-A4, S6-A4, S8-A6.

**F1 outer band (off by default).** When `zone_wick_band_enabled` is true a *second* box is built
alongside this one, sharing its near edge and extended past its far edge to the wick extreme of the
same window — capped at `zone_wick_band_max_ratio` × the body-box height, past which the wick is an
outlier and excluded. The box above stays the **body core** and keeps pricing the entries; the band
is read only by the stop (§5.5, §8.5, §8.9).

### P6 — 50% fill measurement

```
midpoint = (box_top + box_bottom) / 2     # frozen at zone creation, never re-measured
filled   = any bar WICK trades through midpoint      # zone_fill_measure = "wick_touch"
```
Conservative on purpose: kills the zone earlier than a close-based test. `close_beyond` is the
sweep alternative. Params: `zone_fill_measure`, `zone_fill_reference = "as_originally_drawn"`.
Answers S5-A9, S5-A10, S5-A11, S6-A3, S8-A7.

### P7 — Mid-range

```
geo_mid = (range_high + range_low) / 2
cand    = highest-touch-count P3 level within +/- mid_range_search_pct% of RANGE HEIGHT around geo_mid
mid     = cand.price if cand else geo_mid                      # [S4 definition: "not exactly 50%"]
no_trade_band = [mid - mid_range_band_pct%*height, mid + mid_range_band_pct%*height]
```
Params: `mid_range_search_pct = 10.0`, `mid_range_band_pct = 15.0`. Answers S4-A1, S4-A3, S8-A14.

### P8 — Range detection and staleness

```
range exists if over a window >= range_min_bars on structure_tf:
    >= 2 touches of an upper level AND >= 2 of a lower level (P3/P4)
    AND (upper - lower) >= range_min_height_atr * ATR
    AND no body close has occurred beyond either level
death:   CF-26  (body close beyond a boundary THEN a CF-15 flip in the opposite direction)
retire:  age > range_max_age_bars, or no touch within range_stale_bars
nested:  the range on the HIGHEST timeframe wins    [S7-R20]
```
Params: `range_min_bars = 20`, `range_min_height_atr = 3.0`, `range_max_age_bars = 300`,
`range_stale_bars = 60`. Answers S4-A15, S4-A16.

### P9 — "At the level" / retest tolerance

Same band as P4: `level_tolerance_atr × ATR(atr_period)` (default 0.15). Used for retest detection,
"price is at range lows/highs", and the mid-range zone test. **Limit orders are placed at the level
price itself, not at the band edge.** Answers S2-A2, S3-A8.

### P10 — Sufficient-gap anchor and measurement

```
anchor  = breakout candle CLOSE
extreme = furthest price reached before a retrace > sufficient_gap_retrace_cutoff of the excursion
gap_pct = |extreme - anchor| / anchor * 100
gap_atr = |extreme - anchor| / ATR(atr_period)
valid   = gap_pct >= sufficient_gap_pct_by_tf[tf] AND gap_atr >= sufficient_gap_atr_mult
          (both required when sufficient_gap_require_both_tests)
```
Params: `sufficient_gap_anchor = "breakout_close_to_extreme"`, `sufficient_gap_retrace_cutoff = 0.5`.
Answers S5-A1, S6-A2.

### P11 — Trend / regime classification

```
pivots = last trend_pivot_count confirmed P1 pivots on structure_tf
uptrend   = last two swing HIGHS higher than predecessors AND last two swing LOWS higher
downtrend = mirror
else        = range/neutral      # neutral is NOT counter-trend for CF-03
```
Params: `trend_pivot_count = 4`, `trend_timeframe = structure_tf`. Answers S3-A11, S5-A20, S7-A8.

### P12 — Capitulation wick

```
is_capitulation = wick_len >= capitulation_wick_atr * ATR
                  AND wick_len >= capitulation_wick_body_ratio * own_body
                  AND volume  >= capitulation_volume_mult * median(volume, 20)
```
Excluded as a **stop anchor** (TBOT1-R6, S6-R18); permitted as an **entry target** (TBOT1-R22).
That split is the resolution of TBOT1-C4. Params: `capitulation_wick_atr = 3.0`,
`capitulation_wick_body_ratio = 3.0`, `capitulation_volume_mult = 2.0`. Answers S8-A17, TBOT1-A15.

### P13 — "Consolidates horizontally"

```
horizontal = abs(linreg_slope(closes) * window_len) <= consolidation_max_drift_atr * ATR
             AND (window_high - window_low) <= consolidation_max_height_atr * ATR
             AND window_len >= consolidation_min_bars
```
Rejects the down-drifting consolidations he rejects by eye (S5-R15, S5-A5, S6-A27).
Params: `consolidation_max_drift_atr = 0.75`, `consolidation_max_height_atr = 2.0`,
`consolidation_min_bars = 2` (S5-R17).

### P14 — Confluence scoring and deduplication

```
objs  = all objects whose price is within confluence_merge_atr * ATR of the candidate entry
by_class = group(objs, key=class)
score = sum(max(weight(o) for o in group) for group in by_class)   # same class -> count ONCE
gates = cross-market context is a VETO, never a score contributor  [TBOT1 §10]
take  = score >= min_confluence_count AND len(by_class) >= 2       [single_class_trade_forbidden]
```
Params: `confluence_merge_atr = 0.25`, `confluence_dedup_same_class = true`.
Answers S2-A14, S3-A22, S4-A11, S5-A13, S6-A14, S7 §10, S8-A15, TBOT1-A4/A5.

### P15 — "Liquidity taken" from an order block

Percentage of the OB candle's **body range** that price has traded through since the OB formed,
measured from the OB's outer edge inward using the **deepest wick** penetration. Used **only** when
`zone_fill_invalidation_pct` is set to the S7 values (70/80).
Param: `ob_liquidity_measure = "deepest_wick_through_body_range"`. Answers S7-A2.

### P16 — Session and day boundary

`day_boundary_utc = "00:00"` (CF-45). Keys: daily candle construction, the Monday range (S5-R8/R9),
the two-loss-per-day counter (S2-R21), and the challenge-account period (S2-R23).
Week boundary = Monday 00:00 UTC. Weekend = Saturday 00:00 UTC → Monday 00:00 UTC.
Answers S2-A23, S5-A17. Flagged as open question Q13 (§14).

### P17 — "Immediate reaction" / stale trade

```
no_reaction = bars_in_trade >= stale_exit_bars
              AND mfe < reaction_threshold_atr * ATR
              AND mae >= stale_exit_mae_atr * ATR
              AND tps_hit == 0
```
**Off by default** (`stale_exit_enabled = false`, CF-30) because no number for it exists anywhere.
Params: `stale_exit_bars = 8`, `reaction_threshold_atr = 0.75`, `stale_exit_mae_atr = 1.0`.
Answers S6-A17, S4-A4.

### P18 — Illiquidity / barcoding / wick-heavy screen

```
fails = median_30d_quote_volume_usd < min_daily_volume_usd
     OR median(wick_len / bar_range, last 200 bars on trade_tf) > max_median_wick_ratio
     OR fraction(bars where total_wick > 2 * body) > max_wicky_bar_fraction
# A failing symbol is DEMOTED to spot-only (Tier B), not excluded.   [S6-R45, S7-R38, CF-40]
```
Also sets the `wick_heavy` flag consumed by `dca_size_split_wick_heavy_2` (S6-R27).
Params: `max_median_wick_ratio = 0.55`, `max_wicky_bar_fraction = 0.40`.
Answers S2-A20, S7-A24, S8-A13.

### P19 — Stop buffer

`stop_buffer_atr × ATR(atr_period)` beyond the chosen anchor (CF-14), default **0.15 ATR**.
He never gives a buffer; his own worked example "almost got wicked" (S2-R12, S2-A8, TBOT1-A14),
so 0.15 is the conservative reading of "small". Answers S2-A8, S4-A5, TBOT1-A14.
**Scope after F6:** this is the *fallback* buffer, for stops that are not anchored to a zone, and
for the CF-06 step-1 LTF re-anchor.

### P19b — Stop buffer against a zone (**F6**)

`stop_buffer_zone_fraction × zone height` beyond the zone's far edge, default **0.5**
(sweep 0.45–0.60). Three pass-2 frames — TBOT1 4:11 (BTCUSDT.P 1H), TBOT1 1:09:19 (OMUSDT.P 1H),
S8 1:28:33 (SOLUSDT.P 4H) — put the stop 0.48 / 0.49 / 0.58 zone-heights below the box bottom,
while the same three distances are 0.66 % / 2.70 % / 0.81 % of entry. The fraction clusters, the
percentage does not: fraction-of-zone-height is the parameterisation. See §8.5.

### P20 — "Points of most touch" (entry price inside a zone)

```
bins  = histogram of bar-price intersections at pmt_bin_atr * ATR resolution,
        over the zone's formation window PLUS every subsequent touch
entry = argmax(bins);  ties break toward the price NEAREST THE ZONE'S OUTER EDGE
        (that is where his lightest "entry at the SR point" sits)   [S5-R20, S7-R18]
```
Param: `pmt_bin_atr = 0.05`. Machine version of S4-R4, S5-R23, S5-A15.

---

## 5. Detectors

### 5.1 Support / resistance levels

| Aspect | Specification | Source |
|---|---|---|
| Detection | P3 clustering of confirmed P1 pivots on `structure_tf`; level price = volume-weighted mean of members ("points of most touch") | P3, S4-R4 |
| Validity | `touch_count ≥ level_min_touches` (2). Two touches is enough to call an SR point | S4-R4, S7 `[00:05:04]` |
| Quality score | `break_move_away_pct` per S2-R6: 11% = strong SR, ~2% = "measly", close at the line = very weak. Feeds conviction, not a hard gate | S2-R6, S2-A4 |
| Strength scaling | Strength ∝ timeframe: HTF levels hold, LTF levels get burst through | S5-R35, S6-R7, S4 `[00:35:08]` |
| Untested SR | An SR point that has flipped but not yet been retested is the strongest rejection candidate; the second touch is still valid but weaker | S6-R39 |
| Decay | `touch_size_decay = [1.00, 1.00, 1.00, 0.66, 0.50]` applied by touch index on top of the risk budget. Q2 shifted it one index right: the 3rd touch is *"a great area to go long"* (S7 `[00:08:22]`) and the only indexed reduction he gives is the 5th (S8 `[00:54:14]`) | CF-07, Q2 |
| Hard veto | **Bare S/R line** (no zone, not a range boundary): no trade after `line_touch_hard_limit` (3) touches | CF-07, S4-R14, S5-R2 |
| Zone exception | Zones and order blocks are governed by the **fill rule** (CF-08), not by touch count, when `zone_touch_uses_fill_rule_not_count` | CF-07 |
| Range exception | Range boundaries are playable to `range_boundary_touch_limit` (6) touches | CF-07, S4-C1 |
| Invalidation | Body close through the level starts the flip machine (§5.2); a pending SR expires after `pending_sr_expiry_bars` | CF-15, S2-A15 |
| Do not draw | No resistance far above current price action — only levels price has interacted with | S3 `[00:58:34]` |
| Keys | `level_lookback_bars`, `level_cluster_atr`, `level_min_touches`, `level_tolerance_atr`, `touch_reset_atr`, `line_touch_hard_limit`, `range_boundary_touch_limit`, `touch_size_decay`, `zone_touch_uses_fill_rule_not_count`, `pending_sr_expiry_bars` | |

### 5.2 SR flip state machine

Two-candle confirmation is the default (CF-15). States and transitions:

| From | Event | To | Notes |
|---|---|---|---|
| `support` | body close **below** the level | `sr_pending` | wick below does not flip it (S2-R1, S8-R41) |
| `resistance` | body close **above** the level | `sr_pending` | mirror (S2-R3) |
| `sr_pending` | later candle retests within `level_tolerance_atr` **and closes on the new correct side** | `sr_confirmed_resistance` / `sr_confirmed_support` | this is confirmation candle #2 (S5-R3, S2-R2/R3) |
| `sr_pending` | price closes back through the level **before** any retest-and-rejection | original state (`support`/`resistance`) | **deviation**; the level keeps its identity (S2-R4, S3-R17, S7 def, S8 def) |
| `sr_pending` | `pending_since_index + pending_sr_expiry_bars` elapses | original state | **[OUR CHOICE]** — nobody gives an expiry (S2-A15); default 60 bars |
| `sr_confirmed_*` | entry arms at the **open of the candle after** the retest candle | — | S4-R5's third candle is folded in as entry timing, not evidence (CF-15) |
| any | `flip_extra_candle_below_tf` and `tf < 4H` | one extra confirmation candle required | S2-R7; disabled at 4H and above |
| forbidden | `sr_pending → sr_pending` | — | must pass through a confirmed state (S2-R5) |

**Flip vs reclaim** (S8-R12, S8-R28): a **reclaim** is a bare close back through a level; a **flip**
is break + retest + hold. Only a flip changes the level's role. Bullish bias resumes only on a
flip, never on a reclaim alone (S8-R28). Keys: `flip_confirm_candles`, `flip_extra_candle_below_tf`,
`flip_requires_body_close`, `pending_sr_expiry_bars`.

### 5.3 Trend lines

| Aspect | Specification | Source |
|---|---|---|
| Detection | Fit lines through confirmed P1 pivots; a line is a candidate at **3 touches minimum** | S2-R14, S3-R19, S4-R20, S5-R1, S8-R7 (unanimous across five sessions) |
| Touch test | Same P4 tolerance band, applied to the line's price at that bar. Touches may be bodies or wicks (S2-R14) | P4, S2-R14 |
| Competing lines | Multiple valid lines coexist ("no wrong way to draw a trend line"). Score **all** of them by touch count and total span; the highest-scoring line is the primary, the rest remain as confluence objects. **[OUR CHOICE] for the ranking function** | S3-C10, S8-A4, CONFLICTS "Dismissed as apparent-only" |
| Classification | A trend line is diagonal support (uptrend) or diagonal resistance (downtrend); it participates in stage 4, not stage 11 | S6-R28, S7 `[00:49:00]` |
| Validity | Intact while price has not body-closed through it | TBOT1-R1 |
| Decay | Time decay: a resting trend-line thesis weakens the longer price consolidates into the line without triggering; re-assess rather than leave resting | TBOT1-R29 |
| Invalidation | Candle **close** back through the line — cut immediately for a minimum loss | S7-R39, S8-R9, TBOT1-R28 |
| Re-entry | Re-short as soon as price breaks back below the line, capped by `reentry_max_attempts_per_level` | S8-R10, CF-21 |
| Entry policy | Break entry is small size; add on the retest (the retest variant is the safer one) | S8-R8, S8-R13, TBOT1-R16 |
| DCA policy | **Never** DCA a trend-line/breakdown play: one entry, one stop, multiple TPs | S8-R11, `dca_count_breakdown = 0` |
| Standalone | Never trade trend lines alone | S7-R39, `single_class_trade_forbidden` |
| Module | Ships **disabled**: `module_trendline_break_enabled = false` (he disowns it — S8-C1). Its objects still score confluence | CF-37, `disowned_modules_still_score_confluence` |

### 5.4 Ranges

| Aspect | Specification | Source |
|---|---|---|
| Detection | P8 | P8, S4-R3, S4-R4 |
| Range low | The first support touch after a prior resistance/SR level is broken above and flipped to support | S4-R3 |
| Range high | Confirmed only by a **second** touch of resistance; a first rejection in price discovery does not count | S4-R4 |
| Boundary price | Drawn at the points of most touch where two candidate lines compete | S4-R4, P3 |
| Mid-range | P7 — highest-touch-count level near the geometric 50%, else geometric 50%. Explicitly **not** the exact midpoint | S4 def, S4-A1, P7 |
| Asymmetry | The range low is tradeable before the range high exists | S4 `[00:23:37]` |
| Nested ranges | The highest-timeframe range wins | S7-R20, P8 |
| Playable touches | Up to `range_boundary_touch_limit` (6); he takes the 5th–7th inside a confirmed range | CF-07, S4-R13, S4-C1 |
| Death | Body close beyond a boundary **followed by** a CF-15 flip confirmation in the opposite direction (`range_death_mode = "close_beyond_plus_flip"` — the strictest of his three usages) | CF-26, S4-A16 |
| Staleness | `range_max_age_bars` (300) or no touch in `range_stale_bars` (60) | P8 |
| Plays available | Long the range low, short the range high, plus a breakout-continuation play — three plays off one chart | TBOT1-R27, S4-R1, S4-R2 |
| Never | Long range highs; short range lows; short support before it breaks | S4 exclusions, S5-R10, S4-R9 |
| Monday range | Monday's daily high/low, keyed off `day_boundary_utc`; executed on 1H or 30m | S5-R8, S5-R9, `monday_range_source_tf` |
| Keys | `range_min_bars`, `range_min_height_atr`, `range_max_age_bars`, `range_stale_bars`, `range_death_mode`, `mid_range_search_pct`, `mid_range_band_pct`, `mid_range_limits_from_extremes_enabled`, `mid_range_requires_intermediate_stop`, `range_boundary_touch_limit`, `monday_range_source_tf` | |

### 5.5 Supply / demand zones

**Two classes are detected and labelled** (CF-10). Both are tradeable; `continuation` carries a
conviction bonus because it is the definition he built and back-tested.

| Class | Demand | Supply | Source |
|---|---|---|---|
| `continuation` (his) | up-impulse → horizontal consolidation → continues **up** with a sufficient gap | down-impulse → horizontal consolidation → continues **down** | S5-R15, S6-R5, S6-R4, S7 `[00:46:12]` |
| `reversal` (textbook) | down → consolidation → up | up → consolidation → down | S5 `[00:32:06]`, S6 `[00:32:38]`, TBOT1 §2 |

S6-C1 (his supply zone stated backwards once) is treated as a misspeak: three statements plus every
worked example say down-consolidate-down (CF-10).

**Detection algorithm**

```
1. find impulse leg (P2-style directional move)
2. find the following consolidation window; require P13 "horizontal" AND >= min_zone_bodies
   full candle bodies (two halves = one full)                       [S5-R17]
3. box = P5 (bodies, small wicks included, giant wicks excluded)    [CF-13, S5-R19, S6-R9]
4. wait for the breakout, then measure the move away with P10
5. valid only if BOTH gap tests pass (percentage table + ATR multiple)   [CF-11]
6. valid only if min_zone_depth_atr <= depth/ATR <= max_zone_depth_atr   [CF-12]
7. midpoint frozen (P6); entry price = P20 points-of-most-touch
8. F1, only when zone_wick_band_enabled: build the outer wick band alongside the body box
```

**F1 — nested geometry (`zone_wick_band_enabled`, default `false`).** Frame evidence (S6 52:38,
LINK 1D, labelled *"Bullish OB"*) shows him drawing a zone as **two nested boxes**: an inner box on
candle **bodies** and an outer band extended to the **wick** extreme, the band measuring ≈83 % of
the inner box's height. With the flag on, a `Zone` carries both extents and the split is:

| Reads | Extent | Why |
|---|---|---|
| Entry ladder, P20 points-of-most-touch, confluence | the **body box** (`box_top`/`box_bottom`) | *"draw your boxes on candle bodies"* (S5, S6) |
| Stop (CF-14, §8.5) | the **wick band** (`wick_band_stop_edge`) | *"beyond the far side of the zone"* (S6-R17), and the far side is the band |

That reconciles *"draw your boxes on candle bodies"* with *"usually wicks are going to give you that
entry point"* (S5 `[01:05:00]`): the wick entry survives as the P20 cluster **inside** the body box,
while the wick *extent* becomes a second object that only the stop reads. `zone_wick_band_max_ratio`
(1.0) caps the band at that multiple of the body-box height; beyond the cap the wick is an outlier
and is excluded, collapsing the band onto the body edge.

**Confidence: one frame, and pass 2 weakened it.** It ships **off**, so the default geometry is
unchanged and every number produced with the flag down is byte-identical to the single-box model.
The second frame pass makes the case *worse*, not better: the same drawing re-read at S6 53:46
measures the band at **0.33×** rather than 0.83×, and the rectangle was **mid-drag**, with
overlapping fills; two other frames (S6 54:22, S8 33:56) show a **single** box; and the cleanest
settled box in the batch (S8 1:28:33) is a single box on body extremes. The two-box form appears
in roughly **one frame in four** and is not his standard convention. What *is* consistent across
both passes: in every **settled** box measured, top and bottom both anchor to candle **bodies** —
that part is solid, and it is what §5.5 already implements. `zone_wick_band_max_ratio` is not a
trustworthy number (two readings of one drawing, 2.5× apart); its sweep bracket is widened to
**0.30–1.00** to span both.

**Sufficient-gap table (CF-11).** Rows marked *ours* are interpolated/extrapolated and are
**[OUR CHOICE]**.

| TF | min gap % | Source |
|---|---|---|
| 15m | 3.0 | S5-R16 |
| 30m | **4.0** | S5-R16 / S5 `[00:54:07]` — corrected from 3.5 (Q13, `stated`) |
| 1H | 4.0 | S5-R16 (lower bound of "3–5% totally fine") |
| 2H | 5.0 | **interpolated — [OUR CHOICE]** |
| 4H | 6.0 | **interpolated — [OUR CHOICE]** |
| 8H | 7.0 | **interpolated — [OUR CHOICE]** |
| 12H | 7.5 | **interpolated — [OUR CHOICE]** |
| 1D | 8.0 | S5-R16 (lower bound of 8–12%) |
| 2D | 13.0 | S5-R16 |
| 3D+ | 15.0 | **extrapolated — [OUR CHOICE]** |

Secondary test: `move_away ≥ sufficient_gap_atr_mult × ATR(atr_period)`; both must pass when
`sufficient_gap_require_both_tests`.

**F5 — the four *ours* rows are confirmed absent from the video, not merely from the transcripts.**
A frame pass found **no percentage readout on any 2H, 4H, 8H or 12H chart**; every genuine
measure-tool reading in the corpus sits on 1H or 30m. The one candidate that reads like a clean
threshold — **8.10 % at S5 36:05** — was measured across a **hand-drawn illustration rather than
real candles** and must not be used as evidence for any row. Video is exhausted here; a backtest
sweep is the only remaining route, and no `sweep_bracket` is recorded on the key because none is
derivable. See CONFLICTS.md CF-11 and CHANGELOG_EVIDENCE.md Q13.

| Aspect | Specification | Source |
|---|---|---|
| Strength scaling | ∝ consolidation candle count; ∝ timeframe; ∝ size of the move away | S6-R6, S6-R7, S6-R8, S5-R18 |
| Zone within zone | Take the **larger** zone (longer consolidation) — but only if it still passes `max_zone_depth_atr`; otherwise use the inner zone | CF-12, S5-R30, S8-R23 |
| Regime bias | More supply zones form in downtrends, more demand zones in uptrends; bias accordingly | S5-R42, S6-R49 |
| Invalidation | **50% of zone depth filled** (`zone_fill_invalidation_pct = 50`), measured on the zone as originally drawn, by any **wick** through the midpoint. Beyond it the setup is dead and no re-take is permitted | CF-08, S5-R28, S6-R10, P6 |
| Rescue clause | A dead zone is re-armed if an independent HTF support/resistance with `touch_index ≤ dead_zone_rescue_max_touches` (3) sits inside the remaining half — the trade is then taken **on that level, not on the zone** | CF-08, S7-R4, S7-C3 |
| After death | A **different** setup may be built lower — typically an untouched support with a tighter stop | S5-R29 |
| Replay | While < 50% filled the zone may be re-taken repeatedly, with `touch_size_decay` applied | S5-R28, S6-R25, CF-07 |
| Reject | Zone outside the depth band; fewer than 2 bodies; failed gap test; no confluence | S5-R17, S6-R48, S8-R23, S6-R46 |
| Nested geometry | Body core + outer wick band, entries off the core and the stop beyond the band — **off by default**, one frame | **F1**, S6 frame 52:38 |
| Keys | `zone_direction_mode`, `zone_continuation_confluence_bonus`, `sufficient_gap_pct_by_tf`, `sufficient_gap_atr_mult`, `sufficient_gap_require_both_tests`, `sufficient_gap_anchor`, `sufficient_gap_retrace_cutoff`, `min_zone_depth_atr`, `max_zone_depth_atr`, `min_zone_bodies`, `zone_within_zone_policy`, `zone_box_source`, `wick_include_max_pct`, `wick_include_max_atr`, `zone_fill_invalidation_pct`, `zone_fill_measure`, `zone_fill_reference`, `dead_zone_htf_support_rescue`, `dead_zone_rescue_max_touches`, `zone_wick_band_enabled`, `zone_wick_band_max_ratio`, `consolidation_*` | |

### 5.6 Order blocks

| Aspect | Specification | Source |
|---|---|---|
| Cardinality | **Exactly one candle.** Never two. Asked and answered directly | S6-R3, `ob_max_candles = 1` |
| Bullish OB | The last **red** candle before a directional change **up** | S6-R2, CF-09 |
| Bearish OB | The last **green** candle before a directional change **down** | S6-R1, CF-09 |
| S7-C4 | S7's "bearish OB = last red candle" is internally impossible and is **discarded** | CF-09, S7-C4 |
| Directional change | P2 | P2, S6-A1 |
| Box | Candle body under the P5 wick test (`ob_box_source = "body_with_small_wick"`) | CF-13, P5 |
| Minimum size | `size_atr ≥ min_zone_depth_atr` — the machine form of "smaller than a pinky nail" and "$100 is way too tiny" | S7-R6, S6-R48, CF-12 |
| Inside a zone | The **zone's** boundaries and fill rule govern (`ob_inside_zone_precedence = "zone_wins"`); he prefers "more consolidation demand zone over the order block" | CF-09, S6-R31, S5-A14 |
| Invalidation | Same 50% fill rule as zones (CF-08). "Completely filled" ⇒ dead | S8-R21, S5-R31 |
| S7 alternative | If `zone_fill_invalidation_pct` is set to 70/80, fill is measured by P15 instead | S7-R3, P15 |
| Standalone | **Never** an OB-only trade | S6-R29, `single_class_trade_forbidden` |
| Keys | `ob_max_candles`, `ob_box_source`, `ob_inside_zone_precedence`, `dir_change_atr`, `dir_change_max_bars`, `ob_liquidity_measure` | |

### 5.7 Swing points and market structure

| Aspect | Specification | Source |
|---|---|---|
| Swing detection | P1 fractal, `swing_k = 3`, **bodies only** | P1, S7-R11, S5-R44 |
| Trend | P11 on `structure_tf` only. Neutral ≠ counter-trend | P11, CF-24 |
| Timeframe map | Every trade has a `trade_tf`; `structure_tf = trade_tf + structure_tf_offset` steps up the ladder (default 2, e.g. 1H trade → 4H structure). Trend, MSB, counter-trend classification and the HTF veto are evaluated **there and only there** | CF-24 |
| MSB detection | A single **candle body close** beyond the last opposing swing point. Bearish = close below the last higher low; bullish = close above the last lower high | S7-R12, S7-R13, `msb_price_source = "body_close"` |
| MSB **exit** action | Fires on detection alone (`msb_exit_mode = "break_only"`) — S3-R21's two-step version costs a full leg and is the alternative | CF-22, S2-R28, S3-R21 |
| MSB **entry** action | Requires detection **plus** the retest holding: after a bullish MSB, long the retest of the broken lower high as support; after a bearish MSB, short the retest of the broken higher low as resistance / the next lower high | CF-22, S7-R15, S7-R16, S8-R26, TBOT1-R15 |
| Retest timeout | `msb_retest_timeout_bars` (20) — **[OUR CHOICE]**, S7-A20 leaves it undefined | CF-22 |
| No pre-emption | Do not short the close below structure; do not open a short before a body close below the last higher low | S8-R26, S7-R14 |
| Post-MSB continuation | After an upside break of structure, buy the **next higher low**, stop below the previous higher low | TBOT1-R15, S3-R23 |
| "His higher low" | `higher_low_selection = "technical"` drives MSB. His confluence-weighted level is a **separate object**, `bias_invalidation_level`, used only for spot/long-term bags: the deepest swing low within `bias_level_lookback_bars` carrying ≥ `bias_level_min_confluence` confluences. Breaking the technical level downgrades conviction and blocks new longs; breaking the bias level closes the bag | CF-23, S8-C2 |
| Double bottom / top | Second body-low close to the first (bodies, **not** wicks); neckline break, retest, then entry. Measured target = (neckline − bottom) projected above the neckline. Invalidated on a close below the low | S7-R32, S7-R33, S7-R34, S8-R25 |
| HTF double top | Take partial profit and move the stop to break-even regardless of the expected resolution | S7-R35, S8-R25 |
| Keys | `swing_k`, `swing_price_source`, `trend_pivot_count`, `trend_timeframe`, `structure_tf_offset`, `htf_veto_enabled`, `htf_veto_timeframe`, `msb_exit_mode`, `msb_entry_requires_retest`, `msb_retest_timeout_bars`, `msb_price_source`, `higher_low_selection`, `bias_level_enabled`, `bias_level_min_confluence`, `bias_level_lookback_bars` | |

### 5.8 SFP (swing failure pattern)

| Aspect | Specification | Source |
|---|---|---|
| Bearish SFP | Wick takes out a prior swing **high**; the candle **body closes below** it | S7-R21, S8-R3, S5-R4 |
| Bullish SFP | Wick takes out a prior swing **low**; the candle **body closes above** it | S7-R22, S8-R3, S5-R5 |
| Not an SFP | The candle closes **beyond** the level. No trade | S7-R23, S8-R3 |
| Entry | `sfp_entry_price = "confirming_close"` — the confirming candle's close is the reference price, executed on the next open. In a bar-close backtest these are the same instant; S7-C6 is a phrasing artefact | CF-20, S7-R21, S7-R22, S8-R5 |
| Mid-candle entries | Forbidden — the candle can still close back through the level | S7-R24 |
| Missed entry | Rest a limit at the prior swing high/low with the same wick stop (chase captures ~1%, the limit ~2%) | S5-R6, S7-R27, S8-R6 |
| Chase cap | Do not market-enter if the confirming candle closed more than `sfp_max_close_distance_atr` (1.5 ATR) from the swept level | S5-R7, CF-20 (**OUR number**) |
| Adjacency | The SFP candle may not be within `sfp_min_bars_between` (3) bars of the swing candle it raids | S7-R25, CF-20 (**OUR number**) |
| Separation | The two swing points must be ≥ `sfp_min_swing_separation_atr` (1.0 ATR) apart; closer ⇒ weak SFP | S7-R28, S8-R4, CF-20 (**OUR number**) |
| Trend veto | Do not take an SFP against the prevailing trend (`sfp_trend_veto = true`) | S7-R31 |
| Standalone | **Confluence-only by default.** `sfp_standalone_enabled = false`; the standalone mode exists solely to backtest S7-C5's "20 trades, 3–4 stop-outs, still net winning" claim, which he immediately advises against | CF-20, S7-R30, S7-C5 |
| Governing TF | The trade's own `structure_tf` — not whichever timeframe happens to make the SFP valid (resolves S8-A3) | CF-20 |
| Stop | Beyond the raiding wick, subject to the CF-14 oversized/capitulation-wick fallback | S7-R21/R22, S8-R18, CF-14 |
| Deep wick | If the wick-anchored stop exceeds `max_stop_pct_leverage`, run the CF-06 escalation (tighten on LTF → downgrade vehicle → skip). A 17% SFP stop is explicitly rejected | S7-R26, CF-06 |
| DCA | Zero — single entry | CF-17 |
| Strength | HTF SFPs give deeper retraces than LTF SFPs | S7-R29 |
| Keys | `sfp_entry_price`, `sfp_standalone_enabled`, `sfp_min_bars_between`, `sfp_min_swing_separation_atr`, `sfp_max_close_distance_atr`, `sfp_trend_veto`, `sfp_governing_timeframe`, `sfp_evaluated_last` | |

### 5.9 Fibonacci

| Aspect | Specification | Source |
|---|---|---|
| Draw convention | **Bullish fib = swing low → swing high** (bounces, longs); **bearish fib = swing high → swing low** (rejections, shorts). TBOT1's inversion is a live-narration artefact and is rejected (`fib_draw_convention = "s6"`) | CF-34, S6-R34, S6-R35, S6-C6, S7-R1 |
| Anchors | `fib_anchor_selection = "most_recent_qualifying_swing_pair"` on `structure_tf`, via P1. **[OUR CHOICE]** — his own is admittedly arbitrary (S6-A16, TBOT1-A2) | CF-34, P1 |
| Golden pocket | `[0.618, 0.66]`. He uses 0.66, notes others use 0.65 | CF-33, S6-R32, S6-A23 |
| 0.786 | A **separate** level, not a synonym for the golden pocket. **Q15: S8 never conflates them** — `[01:07:57]` mentions the GP with no 0.786 present, and `[01:14:50]` reads *"the golden pocket, the 786 fib"*, a two-item list whose conjunction the auto-captioner dropped (as at S6 `[01:32:28]`). An ASR artefact, not a verbal slip | CF-33, **Q15 `stated`**, S6-R32 |
| Active set | `[0.618, 0.66, 0.786]` | S6-R33, CF-33 |
| 0.886 | In his recommended five-level list but explicitly **not back-tested by him** ⇒ `fib_886_enabled = false` (precedence rule 4) | S6-A22, CF-33 |
| Role | Entry sits at the golden pocket; DCA at the 0.786 | TBOT1-R5, S6-R15, CF-33 |
| Tie-break | Where fibs disagree with drawn S/R, **S/R wins** (`fib_loses_ties_to_sr`). "Everything is noise when there are support and resistance lines already drawn" | S6-R38, CF-32 |
| Standalone | Never trade fibs alone | S6-R30, `single_class_trade_forbidden` |
| Extensions | Trend-based fib extensions are used **only in price discovery**, drawn swing low → swing high (ATH) → new swing low, producing TP1…TP5. All levels used, not just GP/0.786 | S6-R36, CF-27 |
| Excluded | Fib channels, spirals, arcs, and non-standard levels (0.113, 0.13, 2.14) | S6 exclusions |
| Keys | `fib_draw_convention`, `fib_anchor_selection`, `golden_pocket_band`, `fib_levels_active`, `fib_886_enabled`, `fib_entry_level`, `fib_dca_level`, `fib_loses_ties_to_sr`, `tp_count_price_discovery_max` | |

### 5.10 Chart patterns

Ships **disabled** (`module_chart_patterns_enabled = false`, CF-37) because he disowns trading them
himself; when enabled it is **confluence-only** and can never be the sole reason for a trade
(S4-R38). Pattern objects always score confluence even while the module is off
(`disowned_modules_still_score_confluence = true`).

| Pattern | Geometry / validity | Measured target | Source |
|---|---|---|---|
| Bull flag | Impulse pole + **tight** consolidation with **no change in market structure**; flat or against-impulse slope | Pole (most recent green impulse) copied to the flag base | S4-R17, S4-R23, S5-R39, S8 `[01:10:30]` |
| Bear flag | Mirror; a break **above** the flag invalidates it | Pole (first red impulse) copied to the flag top, projected down | S4-R18, S4-R28 |
| Falling wedge | Steep, converging, **contains** a break of market structure (lower lows/lower highs). Parallel lines ⇒ channel, not a wedge | Bottom-to-top trend-line width at the wedge origin, placed at the breakout point | S4-R21, S4-R23 |
| Rising wedge | Valid only if price arrived into the wedge **from below** | Top-to-bottom width, placed at the breakdown point | S4-R22 |
| Rising parallel channel | Neutral — neither bullish nor bearish | none | S8 `[01:11:44]` |
| Cup and handle | Wide base, two rejections from the neckline; handle must not retrace below `cup_handle_floor_pct` of cup depth | Cup base → neckline, projected up from the neckline | S4-R24, S4-A9 |
| Head and shoulders | Head above both shoulders. **Never short the right shoulder.** Entry = neckline breakdown + retest + rejection, with a very tight stop | Head → neckline, projected down | S4-R26 |
| Inverse H&S | Head **below both** shoulders (hard geometric filter); the right shoulder is not formed until the neckline is touched; right-shoulder high ≤ left-shoulder high | Head bottom → neckline, projected up | S4-R25, S5-R40 |
| Trend-line inverse H&S | Valid only against a **downtrend** line acting as resistance; he does not play them at all ⇒ ships off | none | S5-R41 |
| Bearish quasimodo | Requires a prior uptrend: final HH → close below the prior HL (making a LL) → rally back to the previous HH → lower high there → rejection = trigger. Must coincide with horizontal resistance | none stated | S4-R27, S6-R50, S8 `[00:10:53]` |
| Double bottom / top | See §5.7 | (neckline − bottom) projected up | S7-R32 |

| Aspect | Specification | Source |
|---|---|---|
| Entry | Breakout/breakdown **+ retest + close/hold**, then enter with the stop just beyond the flipped level. Naked breakouts are the riskiest option and are excluded | S4-R19, CF-16 flip-pending family |
| Retest TF | Must occur on the timeframe the pattern was drawn on; an LTF retest may improve the entry price but does not confirm an HTF pattern | S4-R29 |
| Targets | The measured "final TP" is **theoretical**; real TPs go at intervening structural levels | S4 `[00:53:25]`, S5-R39, CF-28 |
| Minimum size | A consolidation too small for a pattern is treated as plain S/R instead | S4 `[01:03:29]`, S4-A17 |
| Nesting | Patterns may nest and may form on trend lines; both count as extra confluence | S4 `[01:42:49]` |
| Pole anchor | `pattern_pole_anchor = "most_recent_impulse"` — **[OUR CHOICE]**; he says outright there is no wrong impulse (S4-C6, S4-A21) | S4-R17 |
| Keys | `module_chart_patterns_enabled`, `disowned_modules_still_score_confluence`, `cup_handle_floor_pct`, `pattern_pole_anchor` | |

---

## 6. Confluence and scoring

### 6.1 Weights

Weights follow his stated hierarchy (S6-R28, S6-R38, S6 §10) but **the numbers are OURS** — he ranks
and makes pairwise "more confluence" comparisons but never scores (S6-A15, CF-31).

| Class | Weight | Rationale / source |
|---|---|---|
| Support / resistance level, SR point | **1.5** | "Support and resistance is first. Always" (S6-R28); "everything is noise when there are S/R lines already drawn" (S6-R38) |
| Supply / demand zone | **1.25** | Second in his drawing order (S6-R28) |
| Order block | **1.0** | Below the zone that contains it (S6-R31) |
| Range boundary | **1.0** | S4-R1/R2, S6 §10 |
| Fib golden pocket / 0.786 | **1.0** | Ranked above patterns (S6 `[01:56:54]`), below S/R (S6-R38) |
| Trend line | **0.75** | Diagonal S/R but the weakest of the drawn objects (S7-R39) |
| Chart pattern | **0.5** | Confluence only (S4-R38) |
| SFP | **0.5** | Second-order confluence (S7-R30) |
| RSI divergence | **0.5** | Confluence-only intersection of S8's disowning and TBOT1's use (CF-36) |
| 200 EMA (daily only) | **0.5** | Off by default (`ema200_confluence_enabled = false`, S6 `[01:09:27]`) |
| CME gap | **0.5** | "Confluence contributor at most, never a signal" (S3-R35, S8 `[00:24:46]`) |
| Zone class = `continuation` | **+1.0 bonus** | `zone_continuation_confluence_bonus` (CF-10) |
| Cross-market context (BTC.D / USDT.D / BTC pair / beta parent) | **veto only, weight 0** | TBOT1 §10, CF-35 |

### 6.2 Scoring algorithm

Exactly P14:

```
objects = [o for o in all_objects if abs(o.price - candidate_price) <= confluence_merge_atr * ATR]
groups  = group_by_class(objects)
score   = sum(max(weight(o) for o in g) for g in groups)      # same class counts ONCE
if zone_class == "continuation": score += zone_continuation_confluence_bonus
qualified = (score >= min_confluence_count) and (len(groups) >= 2)
```

- `min_confluence_count = 3.0` (weighted). The single explicit endorsement in the corpus is
  "3 is a good one" (S5 `[01:43:55]`), and 3 is the modal observed count (S2 Injective, S5 SOL,
  S6 `[00:18:57]`, S8 DOGE) (CF-31).
- **`single_class_trade_forbidden = true`** — a hard rule of its own, independent of the score.
  Never OB alone (S6-R29), never fibs alone (S6-R30), never patterns alone (S4-R38), never SFP
  alone (S7-R30), never trend lines alone (S7-R39), never BTC.D alone (S3 `[00:59:40]`).
- **Deduplication resolves TBOT1-A4** (SR point + supply zone + order block at one price): three
  *different* classes ⇒ 3 objects, 3 contributions; two objects of the same class ⇒ one contribution.
- **Tie-break between two candidate setups:** take the one with the higher score
  (S6-R31, S8 `[00:42:25]`, TBOT1 `[00:23:30]`). Where scores tie, take the higher-timeframe
  object (S7-R20).
- **Fib vs S/R disagreement** resolves to S/R before scoring (`fib_loses_ties_to_sr`, S6-R38).

### 6.3 Conviction mapping

`conviction` is derived from the score and modifiers and drives sizing, not eligibility.

| Condition | Conviction | Effect |
|---|---|---|
| score ≥ `high_conviction_score` (4.0) **and** no adverse regime flag | `high` | Spot notional 12% (S8-R35); unlocks `max_loss_pct_swing_hard_cap` **only if** `high_conviction_loss_pct_enabled` (off by default) (CF-01) |
| `min_confluence_count` ≤ score < 4.0 | `normal` | Standard budgets (CF-01, CF-02) |
| Price action unclear, or an adverse-but-non-vetoing regime flag, or a mid-range behaviour flag (S8-C6) | `low` | `max_loss_pct_low_conviction` = 1.5% (~1/3 size, S6-R26); spot notional 6% (S8-R35); DCA leg armed at **zero size** (TBOT1-C6) |

`high_conviction_score` is **[OUR CHOICE]** (default 4.0), chosen because his 4-confluence examples
are the ones he calls "everything points to that area" (S6 `[01:35:26]`, TBOT1 `[00:23:30]`).

---

## 7. Setup qualification

A `Setup` becomes a `TradePlan` only if it passes **every** gate. Gates are evaluated in this order;
the first veto stops evaluation and is recorded in `Setup.vetoes`.

### 7.1 Gate table

| # | Gate | Condition to pass | Veto reason | Source |
|---|---|---|---|---|
| G1 | Universe tier | Symbol is Tier A or Tier B (§7.3); Tier B forces `vehicle = spot` | `universe_tier_c` | CF-40, P18 |
| G2 | Watchlist size | Active symbols ≤ `universe_max_symbols` (3) | `watchlist_full` | S8-R33, CF-40 |
| G3 | Calendar — event | Not within `event_blackout_hours` of a scheduled high-impact event, **or** the trade is spot. After the event, leverage re-arms only once a range has formed | `event_blackout` | CF-39, S2-R27, S5-R36, S8-R2 |
| G4 | Calendar — weekend | Not inside the weekend window, **or** the trade is spot | `weekend_blocked` | CF-39, S5-R37, TBOT1-R24 |
| G5 | Confluence | `score ≥ min_confluence_count` **and** ≥2 distinct classes | `insufficient_confluence` / `single_class` | CF-31, P14 |
| G6 | Mid-range | Price is **outside** the P7 no-trade band. If price is at a range extreme, a limit *at* mid-range is permitted only when an intermediate structural stop exists between it and the far boundary | `mid_range_no_trade` | CF-25, S4-R8, S5-R13, S8-R30 |
| G7 | Regime / macro (§7.2) | No hard veto from the context layer | `regime_veto` | CF-35, TBOT1-R19/R20 |
| G8 | HTF veto | The `htf_veto_timeframe` (1D) candle does not oppose the trade direction | `htf_veto` | S7-R20, S8 `[00:38:57]` |
| G9 | Shorting policy (§7.4) | All four short gates pass (shorts only) | `short_policy` | CF-41 |
| G10 | Price discovery | If in price discovery: long-only; extensions supply the TP ladder | `short_in_price_discovery` | S3-R28, S6-R37, CF-41 |
| G11 | Object liveness | The anchoring zone/OB is not dead (CF-08), or is rescued; the level is under its touch limit (CF-07) | `object_dead` / `touch_limit` | CF-07, CF-08 |
| G12 | Stop constructible | A CF-14 anchor exists and the CF-06 escalation resolves to a tradeable vehicle | `no_stop_anchor` / `stop_too_wide` | CF-06, CF-14, S5-R13 |
| G13 | Stop floor | `stop_pct ≥ min_stop_pct` (0.5) — a stop can also be **too tight** | `stop_too_tight` | S7-C8, CF-06 |
| G14 | R:R | R:R ≥ `min_rr` (2.0), measured from `average_entry` to the TP `rr_measured_to` names — the **final** TP since **F9** — against the stop | `rr_below_min` | CF-42, S3-R26, F9 |
| G15 | Expected move | `expected_move_pct ≥ min_expected_move_pct` for the class (scalp 2.0, swing 5.0) | `move_too_small` | CF-41, S3-R15, S6-R8 |
| G16 | TP count | At least `tp_min_count` (2) structural TP levels exist | `insufficient_tps` | S5-R26, CF-27 |
| G17 | Portfolio capacity | §10 concurrency, daily-loss and deployment caps all have room | `capacity` | CF-04, CF-44, CF-02 |
| G18 | Module enabled | If the setup's primary detector belongs to a disabled module (§13), no plan is produced — the objects still score confluence for other setups | `module_disabled` | CF-37 |

### 7.2 Regime / macro layer (S3, CF-35)

Context charts are a **gate, never a signal source**. They may only (a) veto, (b) reduce size, or
(c) permit normal size.

| Chart | Read | Effect | Source |
|---|---|---|---|
| `USDT.D` | **Inverted TA**, scoped to this ticker only: at resistance ⇒ risk-**on** for alts; at support ⇒ risk-**off** / take profit | Size multiplier; risk-off blocks new alt longs | S3-R9, S3-R32, S3-C4 |
| `BTC.D` | **Inverted TA**, same scoping: at resistance ⇒ buy alts; at support ⇒ trim alts | Size multiplier; confluence-only, never standalone | S3-R8, S3-C5 |
| Dominance trend | While BTC.D **and** USDT.D are both trending up, stay risk-off on alts; alt longs re-arm only after USDT.D rejects its next level | Blocks new alt longs | TBOT1-R19 |
| All-pairs veto | If the coin's USDT pair, its BTC pair **and** BTC itself are all at resistance simultaneously → **hard veto** on longs | `all_pairs_at_resistance_veto = true` | TBOT1-R20 |
| Alt/BTC pair | An alt's BTC pairing is a relative-strength filter; a strong BTC pair means the deep pullback you are bidding will not come | Conviction modifier | S3-R29, S6-R41, S7-R37 |
| Beta coins | A beta coin is gated on its major (ETH → OP/LDO/ENS; SOL → JTO/JUP/PYTH; also POPCAT/WIF/MYRO). The parent's move overrides the coin's own technicals | Gate: no plan while the parent is adverse | S6-R42, TBOT1-R21, S8-R34 |
| `BVOL` | Daily only. A candle entering `bvol_zone` sets a volatility-event flag for `bvol_event_window_hours` (72). **No directional signal** — the move can be either way | `bvol_size_multiplier` (0.5) on leverage; spot unaffected | S3-R1, S3-R3, S3-R5, CF-35 |
| BVOL TA | The **only** permitted operation is the static zone-touch test; no trend/structure/direction analysis. Box relocation is manual and is **not automated** | — | S3-R2, S3-C1, S3-A4 |
| `DXY` | **Disabled by default** (`dxy_gate_enabled = false`) — he states the correlation has been broken for ~7 months and cannot explain it. When enabled, gated on a rolling correlation check that is **[OUR CHOICE]** | — | S3-R10, S3-C8, CF-35 |
| Priority | `context_priority = ["USDT.D", "BTC.D", "BVOL"]`, DXY omitted. S3-R11's full order is the alternative | — | S3-R11, CF-35 |
| CME gap | Confluence contributor at most, never a signal; gaps do not have to fill | Weight 0.5 | S3-R35, S8 `[00:24:46]` |
| Funding | Recorded, not acted on — introduced and deferred, only "-3 is extreme" given | none | S3-R34, S3-A20 |
| News | **Not implemented.** Discretionary and not encodable (TBOT1-A23); only the scheduled-event calendar (G3) is machine-readable. **[OUR CHOICE]** | — | TBOT1-A23 |

### 7.3 Universe filter (CF-40)

| Tier | Criteria | Permitted vehicles |
|---|---|---|
| **A** | market-cap rank ≤ `leverage_max_mcap_rank` (100) **and** 30-day median USD volume ≥ `min_daily_volume_usd` (50M) **and** passes the P18 wick screen | leverage + spot |
| **B** | Passes volume but fails rank, **or** is a memecoin (`memecoin_vehicle = "spot_only"`), **or** is newly listed (< `new_listing_days` = 30), **or** fails the P18 wick screen | spot only |
| **C** | Below the volume floor, barcoding, or an airdrop-driven chart (S8 `[01:04:42]`, S8 `[00:05:47]`) | excluded (CF-40) |

- The meme exclusions are **vehicle** exclusions, not universe exclusions — which is why he keeps
  calling levels on coins he says he doesn't trade (CF-40, TBOT1-C5, S4-C4).
- BTC is eligible for swing and spot but **excluded from the scalp module**
  (`scalp_excludes_btc = true`, S8-R32); this does not conflict with S8-R33, which is his swing/spot set.
- Watchlist capped at `universe_max_symbols = 3` (S8-R33); 5 (S3-R29) is the alternative.
- Perp setups must be analysed on the perp chart, not the spot chart (S6-R43).

### 7.4 Shorting policy (CF-41)

| # | Gate | Hardness | Source |
|---|---|---|---|
| 1 | Never short in price discovery | **hard** | S3-R28, S6-R37 |
| 2 | Never short at unbroken support — only at a broken-and-flipped level | **hard** | S4-R9 |
| 3 | Never be **net short** while `structure_tf` is in an uptrend (`net_short_allowed_in_uptrend = false`) — the position-level form of "don't short strength" | hard | S4-R36, TBOT1-R12 |
| 4 | Expected move to TP1 ≥ `min_expected_move_pct` | hard | S3-R15, S7 `[00:31:36]` |
| 5 | A counter-trend short (structure TF up) takes the CF-03 size reduction and demotion | modifier | CF-03 |

TBOT1-C2 resolves as: he shorts strength **into a marked resistance inside a downtrend**, never
strength in open space — which is exactly what gates 2 and 3 encode (CF-41).

### 7.5 Counter-trend handling (CF-03)

`counter_trend_mode = "size_down_and_demote"`:

1. The setup is **allowed**, not vetoed (four sessions plus the live session all reduce size; only
   one clause in S7 vetoes, and S7 re-permits fifteen minutes later — S7-C1).
2. Notional × `counter_trend_size_multiplier` (0.5) (S3-R25, S7-R9, S8-R1).
3. Risk capped at `max_loss_pct_counter_trend` (2.0%).
4. `counter_trend_demote_to_scalp = true`: reclassified as a **scalp**, inheriting the scalp TP
   ladder, DCA count and holding expectations (S7-R10).
5. S3-C9's "the loss stays the same" clause is **discarded**: halving size halves risk.
6. Neutral trend (P11) is **not** counter-trend.

---

## 8. Trade plan construction

Order of construction is fixed: **entry ladder → stop → take-profits** (TBOT1 §14 step 14), then
size, then vehicle.

### 8.1 Entry family selection (CF-16)

| Family | When | Order type | Source |
|---|---|---|---|
| **Retest** (primary) | The level has **already** flipped (an SR point exists) | Resting limits at the SR point and at the DCA levels below/above | S3-R13, S5-R20, S6-R14, S7-R18, S8-R16 |
| **Flip-pending** | The level has **not** yet flipped. No order may rest at the line; the entry arms only after CF-15 confirmation completes. Governs all pattern breakouts, range-boundary breaks and trend-line breaks | Limit, armed post-confirmation | S4-R19 |
| **Trigger** | SFP and MSB-retest entries — event-driven, defined on a close | Market permitted (`allow_market_orders = "trigger_family_only"`) | CF-20, CF-22, S4-R32 |

CF-16 is the resolution of S3-C12/S4-C7: S4 is describing a level that has not flipped yet, S3 one
that has. Never enter because price is moving in your direction (S2-R30); never enter at current
market price for the retest family (TBOT1-R25).

### 8.2 Entry ladder — rung count (CF-17)

| Play class | DCA legs | Source |
|---|---|---|
| Zone / SR swing entry | **1** default; **2** if `zone_depth_atr ≥ dca2_min_zone_depth_atr` (1.5) | S5-R22, S6-R16, CF-17 |
| Scalp | **1** max; **0** if the zone is tight | S8-R17 |
| Breakdown / trend-line / pattern breakout | **0** — single entry | S8-R11 |
| SFP | **0** — single entry | CF-20 |
| Global maximum | `dca_count_max = 2`. Six-leg ladders and SMC-style 5–6 order ladders are **hard-forbidden** | S2-R9, S6 `[01:01:51]` |

DCA prices attach to the **next structural level** (support below for longs, resistance above for
shorts), never to fixed price increments (S2-R10). If the trade timeframe offers only one level,
drop a timeframe to locate the second (S2-R11, S5 `[00:37:46]`). The 0.786 fib is the standard DCA
level when it lands there (S6-R15, TBOT1-R5). When conviction is `low`, the DCA leg is armed but
**sized to zero** — the bot takes the first entry only (TBOT1-C6, §6.3).

### 8.3 Entry ladder — per-rung sizing (CF-18)

Fixed splits, weighted toward the last leg. **Q3 (`derived`) makes these his, not ours**: the one
worked ladder in the corpus gives both prices and quantities and he reads the resulting average back
off the exchange, so the arithmetic is checkable. S6 `[00:38:49]` — 35 : 55 : 100 at 17.28 / 17.858 /
18.181, average *"17.921"*, and (35×17.28 + 55×17.858 + 100×18.181)/190 = 17.9215, exact. With the
third rung unfilled, S6 `[00:48:10]` — *"17.63 somewhere there… a total of 90 coins"*, and
(35×17.28 + 55×17.858)/90 = 17.6332, exact. The *"these are just random numbers"* disclaimer (S6-A8)
is about the absolute quantities driving the loss calculation, not the shape — which is why this is
`derived` rather than `stated`.

| Legs | Default split | Wick-heavy split (P18 `wick_heavy` flag) | Source |
|---|---|---|---|
| 2 | `[0.39, 0.61]` | `[0.25, 0.75]` | **Q3 derived, S6 `[00:48:10]`**; wick-heavy S6-R27 / S6 `[01:54:34]` |
| 3 | `[0.20, 0.30, 0.50]` | `[0.15, 0.25, 0.60]` | **Q3 derived, S6 `[00:38:49]`** (35:55:100 = 18.4/29.0/52.6) |

- First entry is always the **lightest**; the heaviest fill sits at the far end of the ladder —
  bottom for longs, top for shorts (S2-R8, S5-R20, S5-R21, S6-R13, S7-R18, S8-R16).
- The S6-R13 / S7-R18 disagreement ("average nearer the final DCA" vs "roughly mid-zone") is not a
  disagreement: the 3-leg shape lands *"closer to the last DCA point"* and the 2-leg shape lands
  *"somewhere in the middle"* (S6 `[00:46:58]`), which is exactly what he says of each (Q3, CF-18).
- Wick-heavy is his one **stated** number: *"you go in very light there, like I'm talking about 20 to
  30%"* (S6 `[01:54:34]`); 25/75 is the midpoint of that band.
- `size_and_stop_computed_from = "average_entry"`: every downstream calculation — break-even, risk
  budget, R:R, TP trailing — uses the **average entry**, never entry 1 (CF-18).
- **Swing-short ladder variant** (TBOT1-R14): a ladder up to a ceiling with the average mid-range is
  the same object with the rung prices taken from successive resistances; rung count still obeys
  `dca_count_max`.

### 8.4 Averaging up (CF-19) — disabled by default

`average_up_enabled = false`. Appears once (S3-R13), with no trigger condition (S3-A10), against a
monotonic ladder everywhere else. When enabled it fires only if **all** of:

1. the first entry is filled;
2. price has moved `average_up_trigger_atr` (2.0, **OUR number**) in favour without filling the DCA;
3. the add price is an **SR point**, never a zone interior or open air (`average_up_only_at_sr_point`, S3-R14);
4. the blended average still leaves the trade inside its risk budget with the **original** stop.

Never add to a leverage position to improve the liquidation price (S4-R33). Once a support level is
lost, stop adding entirely (S2-R31).

### 8.5 Stop placement (CF-14)

Deterministic anchor selection:

```
1. anchor = extreme of the qualifying WICK at the far edge of the zone/level      [S2-R12, S6-R17, S8-R18]
2. if is_capitulation_wick(anchor)              -> fall back to the candle BODY extreme  [P12, TBOT1-R6]
   if wick_len > stop_wick_max_pct% of price    -> fall back to the candle BODY extreme  [S6-R18]
3. if the resulting stop would sit BEYOND an independent opposing S/R level:
       move the stop just inside that level and re-run the CF-06 LTF tightening
       (never straddle it — that level is its own trade)                          [S5-R25, S6-R19]
4. stop, by which parameterisation applies:
   a. the setup hangs off a ZONE ->
        stop = zone far edge -/+ stop_buffer_zone_fraction * zone height             [F6, P19b]
        (far edge = box_bottom for a demand zone, box_top for supply; 0.5 by default)
   b. otherwise (a level, an SFP, a structure break, the CF-06 LTF re-anchor) ->
        stop = anchor -/+ stop_buffer_atr * ATR(atr_period)                          [P19]

F1, only when zone_wick_band_enabled and the setup hangs off a zone -- applied between 2 and 3:
   if the stop does not already sit beyond Zone.wick_band_stop_edge, push it beyond the band
   (widen only, never tighten)                                                     [F1, S5-R24]
```

**F6 — the stop distance is a fraction of the ZONE HEIGHT (pass-2 frames, default changed).**
Three independent frames, three pairs, three timeframes, two exchanges, each with a position tool
and a zone box on screen:

| Frame | Chart | Stop below the box bottom, as a fraction of box height | Same, as % of entry |
|---|---|---|---|
| TBOT1 4:11 | BTCUSDT.P 1H Binance | **0.48** | 0.66 % |
| TBOT1 1:09:19 | OMUSDT.P 1H Binance | **0.49** | 2.70 % |
| S8 1:28:33 | SOLUSDT.P 4H MEXC | **0.58** | 0.81 % |

The fraction clusters tightly (0.48–0.58, mean ≈ 0.52); the price percentage does not
(0.66–2.70 %); no ATR multiple is visible anywhere. So the stable rule is **fraction of zone
height** — not a price percentage, and not an ATR multiple. `stop_buffer_zone_fraction`
(**0.5**, sweep 0.45–0.60) replaces `stop_buffer_atr` for any stop anchored to a zone;
`stop_buffer_atr` (0.15, still **OUR number**) survives as the fallback for stops that are not
(levels, SFPs, structure breaks) and for the CF-06 step-1 LTF re-anchor, where the HTF zone does
not exist. Step 3's clip and the F1 band push keep the P19 ATR nudge in either branch — they are
offsets, not the anchor rule.

- **Precedence is unchanged.** `stop_never_beyond_opposing_level` still clips the F6 stop
  (step 3), and the CF-06 wide-stop ladder — tighten → downgrade → skip — still runs after it.
- **Guard [OUR CHOICE].** If a DCA leg reaches past the far edge of its own box, the zone stop
  would not invalidate the whole ladder; F6 then stands down to P19 and records the reason. The
  frames show ladders inside the box and say nothing about this case.
- In every readable frame the stop sits **below the candle bodies but deliberately not below the
  deepest / capitulation wick** — the spoken rule at TBOT1 22:57, now with four frames behind it.
  The zone box is body-anchored, so an F6 stop inherits this; P12 enforces it on the P19 branch.

- Structure is body-based, stops are **wick**-based: the apparent S7-C7/S5-C7 contradiction is a
  scope collision, made explicit in CF-13 (§8.9).
- **F1 (off by default).** S6-R17's *"beyond the far side of the zone"* is unambiguous while a zone
  is one box; under the §5.5 nested geometry it has two candidate far sides, and the frames say the
  stop goes beyond the **wick band**, not the body core. The band applies **before** step 3, so the
  `stop_never_beyond_opposing_level` clip still overrides it, and it does **not** survive the CF-06
  step-1 LTF tightening — CF-06 is an established risk override, F1 is a single-frame observation,
  and where they collide the established rule wins. With the flag down no zone carries a band and
  this step is absent.
- Leverage stops are duplicated: two orders `duplicate_stop_offset_bps` (1.5) apart, because
  exchange stops sometimes fail to trigger (S4-R34).
- Spot carries **no resting stop**. A **synthetic stop** at the same structural price is used
  *only for sizing*, so the risk budget still binds; the real exit is a candle close beyond the
  level plus the CF-15 flip confirmation (CF-05, S2-R29, S8-R36, TBOT1-R18). Slippage past the
  synthetic stop is accepted and logged as `Fill.excess_risk_usd`. **The synthetic stop is our
  construct, not his** (CF-05).
- Never tighten a stop to fit a size; reduce size instead (S5-R24, S7 `[00:14:13]`).

### 8.6 Wide-stop escalation (CF-06)

Evaluated in this exact sequence — these are stages he runs in order, not alternatives:

| Step | Action | Source |
|---|---|---|
| 1 | Attempt an LTF tightening: drop `stop_tighten_tf_steps` (2) timeframes and re-anchor on the nearest qualifying wick/consolidation there | S4-R16, S5-R25, S6-R19, S7-R26, S8 `[01:21:46]` |
| 2 | If `stop_pct` still exceeds `max_stop_pct_leverage` (9.0), **downgrade the vehicle** to spot or leverage ≤ `leverage_downgrade_max_multiple` (3.0) | TBOT1-R7, TBOT1-C3 |
| 3 | If the vehicle cannot be downgraded (leverage-only account, or spot excluded by the coin filter), **skip the trade** | S8-R23, S7-R7, S7-R26 |
| — | Position size is **always** solved from the risk budget regardless of which branch fires | S6-R11, S6-R12 |

### 8.7 Take-profit placement

**Count** (CF-27), by trade class:

| Class | TPs | Source |
|---|---|---|
| Swing / range | **2** — TP1 mid-range, TP2 the opposite boundary | S4-R1/R2, S6-R20, CF-27 |
| Scalp | **3** | S8-R19, TBOT1-R17 |
| Price discovery | up to **5** from trend-based fib extension levels | S6-R36 |
| Floor | `tp_min_count = 2` — never one entry and one TP | S5-R26 (explicit prohibition) |

**Level selection.** TPs sit on **structural levels** in the trade's direction, never at fixed R
multiples (S6-R20, S8-R12, S5-R26). Selection rule, **[OUR CHOICE]** because S4-A14/S5-A12/S6-A10/
S8-A10 all leave it open: take the nearest `n` P3 levels in the trade direction whose price is at
least `min_stop_pct` away from the previous TP, ranked by touch count, capped at the measured-move
target where one exists. The measured "final TP" of any pattern is **theoretical** — real profit is
taken at intervening levels (S4 `[00:53:25]`, S5-R39).

**Splits** (CF-28), applied to the number of TPs **actually placed**, front-loaded because TP1 is
the most likely to fill (S4-R10):

| TPs | Split | Source |
|---|---|---|
| 2 | `[0.50, 0.50]` | S4-R10 |
| 3 | `[0.40, 0.30, 0.30]` | S4-R10 |
| 4 | `[0.40, 0.25, 0.20, 0.15]` | **extrapolated — [OUR CHOICE]** (CF-28) |
| 5 | `[0.35, 0.25, 0.20, 0.12, 0.08]` | **extrapolated — [OUR CHOICE]** (CF-28) |

Residual after the last TP is closed by the trailing stop (`tp_residual_policy = "trail_out"`),
never left open (CF-28).

**Which TP the R:R gate measures to — F9.** Because TP1 is by construction the *nearest*
qualifying structural level, R:R to TP1 is always the smallest ratio the ladder offers, and on a
2-TP swing plan it is routinely half the ratio to the final TP. Four frames of his own TradingView
position tool (TBOT1 4:11 BTCUSDT.P 1H, TBOT1 22:59 HYPEUSDT.P 4H, TBOT1 1:09:19 OMUSDT.P 1H,
S8 1:28:33 SOLUSDT.P 4H) show its Risk/Reward readout at **3.17 / 5.00 / 2.97 / 2.13**, and that
tool measures to its single **target line** — a final target, not a first partial. *That the tool
measures that way is our reading of TradingView, not something he states.* So `rr_measured_to`
defaults to `"final_tp"` and G14 gates there; `"tp1"` remains the recorded alternative, and it is
what shipped before F9. Both figures are carried on the plan (`rr_to_tp1`, `rr_to_final_tp`) and
both are serialised, so nothing is lost by the change of basis.

### 8.8 Position sizing (CF-01, CF-02)

Sizing is **always solved backwards** — the only worked method in the corpus, and it is
deterministic (S6-R11, S6-R12):

```
loss_budget_usd = risk_budget_pct/100 * equity(account)
qty_total       = loss_budget_usd / abs(stop_price - planned_average_entry)
qty_total      *= touch_size_decay[min(touch_index, 5) - 1]          # CF-07
qty_total      *= counter_trend_size_multiplier   if counter_trend   # CF-03
qty_total      *= bvol_size_multiplier            if bvol_event      # CF-35
notional_usd    = qty_total * planned_average_entry
notional_usd    = min(notional_usd, notional_ceiling(vehicle, conviction))   # CF-02
if clamped: re-solve qty_total from the clamped notional (risk then lands UNDER budget)
```


> **CORRECTION — the constant is $250, not $750.** `Amount` is the account **balance** at that
> leg on a $1,000 nominal base, so `risk = 1000 - Amount(stop leg) = $250` and
> `reward = Amount(target leg) - 1000`. Five frames confirm it: BTC 1H 1792.2, HYPE 4H 2249.04,
> OM 1H 1741.7, SOL 4H 1531.53, BTC 1D 1651.82 — each `Amount - 1000` reproduces
> `qty x target distance` to within 0.4%, while `750 x R:R` misses every one by 18–65%.
> Independently, `qty x stop distance = 250.00` on all **eight** position-tool frames, 2022-11 to
> 2025-06. What is corroborated is unchanged — a constant cash risk, i.e. the risk-first solve —
> but the portfolio inference of 15,000–18,750 is **withdrawn**, having been built on the misread
> field. $250 on a $1,000 nominal base is 25% per trade: a teaching template, not a live sizing
> rule. See `docs/measurement/CORRECTION-risk-figure-v2.txt`.

**Corroborated by F9 (part B).** The stop-side "Amount" on his position tool reads exactly **750**
in all three frames where it is visible — BTCUSDT.P 1H, HYPEUSDT.P 4H and OMUSDT.P 1H, i.e. three
pairs, two timeframes and two exchanges. A constant cash risk per trade is exactly what this
backwards solve produces, and it is direct visual support for the *model*, not for any particular
percentage. Its arithmetic implies a portfolio of roughly **15,000–18,750** at his stated 4–5 % max
loss; that is an **inference and is labelled as one** — his account size is never shown in any
frame (F3) — and **no account-size key is derived from it**.

**Risk-budget ladder** (CF-01), applied to the account the trade belongs to:

| Class | Target | Hard cap | Source |
|---|---|---|---|
| Swing | `max_loss_pct_swing` = **4.0%** | `max_loss_pct_swing_hard_cap` = **5.0%** | S2-R20, S3-R24, S5-R32, S6-R11, S7-R8 |
| Scalp | `max_loss_pct_scalp` = **2.5%** | — | S2-R20, S3-R24 |
| Counter-trend | `max_loss_pct_counter_trend` = **2.0%** | — | S7-R9 (2–3%), S3-R25 (1%) |
| Low conviction | `max_loss_pct_low_conviction` = **1.5%** | — | S6-R26 (1/3 size) |
| High-conviction escalation | TBOT1's 5–6% is available **only** behind `high_conviction_loss_pct_enabled` (default **false**), swing only | — | TBOT1-R13, CF-01 precedence rule 2 |

**Notional ceilings** (CF-02) — notional is a *derived, clamped* quantity, never an input:

| Vehicle | Ceiling | Source |
|---|---|---|
| Leverage | `max_notional_pct_leverage` = **100.0%** of equity (= `margin_pct_leverage` 10 % × `default_leverage` 10x) | **Q8 `derived`, S6 `[00:08:36]`–`[00:11:27]`** |
| Leverage, margin | `margin_pct_leverage` = **10.0%** of equity — the figure S7 and S3 actually quote | S7 `[00:25:54]`, S3 `[00:04:25]` |
| Spot, high conviction | `spot_notional_pct_high_conviction` = **12.0%** | S8-R35 |
| Spot, low conviction | `spot_notional_pct_low_conviction` = **6.0%** | S8-R35 |
| Spot, portfolio-wide | `max_total_spot_deployment_pct` = **70.0%** | S4-R31, S8-R35 |

Risk is always expressed as a **percentage of current equity**, not a fixed notional (S2-R25).

**Provenance of the sizing method (F3 — method correction).** The tooling assumption behind this
section was wrong and is corrected here. A frame pass over the recordings found **no TradingView
position-size tool in any frame**; the on-chart position tool appears with its stats labels turned
*off*. What he actually uses is:

1. a **web average-cost calculator** (coinguides.org) for the blended entry — visible in the S6
   9:40–10:53 frames, the same frames that corroborate `dca_size_split_2` (F2); and
2. the **Windows calculator** for the loss figure — legible on screen: `2.85 × 23 = 65.55`. The
   `2.85` is consistent with the distance from the $38.385 average entry down to the $35.51 leg,
   but he never labels it as a stop, so read it as inferred arithmetic and not as a stated risk
   figure.

**Never visible in any frame: account size, leverage, position value, or a labelled stop.**
Consequence for the Q8 margin-vs-notional resolution above (`max_notional_pct_leverage` 10 → 100):
it rests **entirely on the spoken worked example** at S6 `[00:08:36]`–`[00:11:27]`. The frames
neither corroborate nor contradict it. It stays `derived`, on one source.

### 8.9 Body-vs-wick scope table (CF-13)

Every apparent wick/body contradiction in the corpus is a scope collision. The scopes:

| Scope | Source | Rule |
|---|---|---|
| Zone / OB box | **Body-anchored**, extended to a wick only if `wick_len ≤ wick_include_max_pct` (2.0%) **and** `≤ wick_include_max_atr` (0.5 ATR) | S5-R17, S6-R9, S7-R7, P5 |
| Zone outer band (**F1**, `zone_wick_band_enabled`, **default off**, weakened by pass 2) | A *second* box out to the wick extreme, sharing the body box's near edge, capped at `zone_wick_band_max_ratio` × the body-box height. The body box still prices the entries; only the stop reads the band. Pass 2: the two-box form is in ~1 frame in 4, and the one clear example was mid-drag | F1, S6 frames 52:38 / 53:46 |
| Entry price | The **point-of-most-touch** inside the box — usually the wick cluster, so entries may sit at wick prices even when the box is body-drawn | S5-R23, P20 |
| Structure (HH/HL/LH/LL, MSB, double tops/bottoms) | **Bodies only, no exceptions** | S7-R11, S5-R44, S7-R34 |
| Stops, anchored to a **zone** | **Zone-height-anchored** (**F6**): `stop_buffer_zone_fraction` (0.5) × the box height beyond the box's far edge. The box is body-drawn, so the stop lands below the bodies and above the deepest wick — which is what all four readable frames show | **F6**, TBOT1 4:11 / 1:09:19, S8 1:28:33, TBOT1 22:57 |
| Stops, not anchored to a zone | **Wick-anchored**, subject to the oversized/capitulation-wick fallback, plus the P19 ATR buffer | CF-14, S2-R12, S6-R18 |
| Flip confirmation | **Body close** (`flip_requires_body_close`) | S2-R1, S4-R5, S8-R41 |

### 8.10 Vehicle selection (spot vs leverage)

| Condition | Vehicle | Source |
|---|---|---|
| Tier B symbol (memecoin, newly listed, wick-heavy, off-rank) | **spot only** | S6-R44, S6-R45, S7-R38, CF-40 |
| `stop_pct > max_stop_pct_leverage` after LTF tightening | downgrade to spot or leverage ≤ 3× | CF-06, TBOT1-R7 |
| Event blackout or weekend window | spot permitted, leverage blocked | S8-R2, CF-39 |
| Swing floor 4H / scalp ceiling 2H | class assignment drives the risk budget and TP count | CF-38 |
| Otherwise | leverage permitted up to `max_notional_pct_leverage`, with margin bounded by `margin_pct_leverage` × `default_leverage` | S7-R8, Q8 |

Leverage on a plan is derived, not chosen: `leverage = notional_usd / margin_allocated`, set so the
stop-out costs exactly the risk budget (S7-R8). Cross margin is assumed (S4 `[01:59:38]`).
Hedging (1:1 spot short at ≤ 2–3× — S4-R35) is implemented but **off by default**
(`hedge_enabled = false`, **[OUR CHOICE]**) because it is a portfolio operation, not a signal.

---

## 9. Trade management state machine

### 9.1 States

| State | Meaning | Source |
|---|---|---|
| `DRAFT` | Plan constructed, gates passed, not yet armed | §7, §8 (CF-16) |
| `ARMED` | Limit rungs resting (retest family) or waiting for the confirmation event (flip-pending / trigger family). No exposure | CF-16 |
| `PARTIAL` | ≥1 rung filled, ≥1 rung still resting | CF-18 |
| `OPEN` | All armed rungs filled (or the remaining rungs were cancelled), no TP hit yet | CF-18 |
| `MANAGING` | ≥1 TP hit; stop has been trailed at least once | CF-29 |
| `CLOSED` | Flat. `close_reason` set | CF-28, CF-29, CF-30 |
| `EXPIRED` | Armed plan timed out without triggering | CF-15, CF-22 |
| `CANCELLED` | Armed plan invalidated before any fill | CF-30, S7-R17 |

`PARTIAL` and `OPEN` both count as one position against the concurrency caps of §10.

### 9.2 Transition table

| From | Trigger | To | Actions | Source |
|---|---|---|---|---|
| `DRAFT` | Plan published | `ARMED` | Place resting limits (retest family) or register the confirmation watcher | CF-16 |
| `ARMED` | Rung price touched (limit fill) | `PARTIAL` | Recompute `average_entry`; keep the stop and TPs as planned | CF-18 |
| `ARMED` | Confirmation completes (flip / SFP / MSB retest) | `PARTIAL` or `OPEN` | Enter at the confirming close, executed at the next open | CF-15, CF-20, CF-22 |
| `ARMED` | Trend flips against the setup on `structure_tf` | `CANCELLED` | Cancel unfilled limits only; an already-filled position is **not** closed by this rule | S7-R17, S7-A19 |
| `ARMED` | Anchoring zone reaches `zone_fill_invalidation_pct` | `CANCELLED` | Zone dead (CF-08); a new, lower setup may be built (S5-R29) | CF-08 |
| `ARMED` | `expires_at_index` reached (`pending_sr_expiry_bars` / `msb_retest_timeout_bars`) | `EXPIRED` | — | CF-15, CF-22 |
| `ARMED` | Event/weekend blackout begins and vehicle = leverage | `CANCELLED` | Spot plans survive | CF-39 |
| `PARTIAL` | Remaining rung fills | `OPEN` | Recompute `average_entry`; **re-map TP1 to the original entry price** (that level is now an SR point) and shift the other TPs out | S8-R20 |
| `PARTIAL` | Stop hit before further fills | `CLOSED` (`stop`) | Loss = filled size only | CF-18, S2-R8 (light first entry is precisely this hedge) |
| `PARTIAL` | Support/level under the ladder is lost (close beyond) | `CLOSED` (`structural_stale`) | **Stop adding**; cut. Never keep DCAing a level that is gone | S2-R31, CF-30 |
| `PARTIAL`/`OPEN` | Price never reaches the DCA and `average_up_enabled` | `PARTIAL` | Add at the next SR point only; re-check the risk budget with the original stop | CF-19, S3-R13/R14 |
| `OPEN`/`PARTIAL` | **TP1 hit** | `MANAGING` | Close `tp_split[0]` of size; **move stop to break-even at `average_entry`** (`break_even_reference = "average_entry"`) | CF-29, S4-R11, S5-R27 |
| `MANAGING` | **TP2 hit** | `MANAGING` | Close `tp_split[1]`; **move stop to TP1's price** | CF-29, S4-R11, S5-R27 |
| `MANAGING` | **TPn hit (n ≥ 3)** | `MANAGING` | Close `tp_split[n-1]`; move stop to TP(n−1)'s price | CF-29 |
| `MANAGING` | Final TP hit | `CLOSED` (`tp_final`) | Any residual is trailed out, not left open | CF-28 |
| `MANAGING` | Trailed stop hit after a TP | `CLOSED` (`trail_out`) | **Normal, accepted outcome** — he calls it correct behaviour; the setup may then be re-taken subject to CF-08 and CF-21 | CF-29, S5 `[00:40:00]` |
| `OPEN`/`PARTIAL`/`MANAGING` | Stop hit | `CLOSED` (`stop`) | Increment the daily loss counter if the close is below `average_entry` net of fees | CF-44, S2-R21 |
| `OPEN`/`PARTIAL`/`MANAGING` | The level that justified the trade is **lost** (close beyond it, or it flips against the position) | `CLOSED` (`structural_stale`) | Immediate market exit, accepting the small loss. `structural_stale_exit_enabled = true` | CF-30, S6-R22, S6-R23, S7-R39, S8-R9 |
| `OPEN`/`PARTIAL` | MSB against the position on `structure_tf` | `CLOSED` (`msb_exit`) | `msb_exit_mode = "break_only"` fires on detection alone | CF-22, S2-R28 |
| `OPEN`/`MANAGING` | P17 stale condition **and** `stale_exit_enabled` | `CLOSED` (`time_stale`) | Exit at break-even or better. **Off by default** — no number exists for it anywhere | CF-30, P17 |
| spot `OPEN` | Candle close beyond the level on `spot_invalidation_timeframe` (1D) **plus** the CF-15 flip confirmation | `CLOSED` (`spot_flip`) | Wicks do not count. Log `excess_risk_usd` if the exit is worse than the synthetic stop | CF-05, S2-R29, S8-R36, TBOT1-R18 |
| `long_term` account | Macro MSB two-step on the HTF: close below the last higher low **then** a lower high | `CLOSED` (`msb_exit`) | Sell into the retest; accept being 20–30% off the top. Level-loss cuts do **not** apply to this account | CF-43, S3-R21, S7-R36 |
| `CLOSED` | Re-entry trigger fires (§9.4) | new `DRAFT` | Touch counter continues to increment across re-entries, so size decays | CF-21, CF-07 |

### 9.3 Trailing rules — summary

| Event | New stop | Source |
|---|---|---|
| TP1 hit | Break-even = **average entry** (not first entry) | CF-29, S4-R11, S5-R27, CF-18 |
| TP2 hit | TP1's price | CF-29, S4-R11, S5-R27 |
| TP3+ hit | Previous TP's price | CF-29 |
| DCA rung fills | Stop is **unchanged**; `average_entry` moves, so the loss budget must be re-verified. If the new average breaches the budget, close the excess quantity rather than widening the stop | S6-R11, S6-R12, CF-18 |
| DCA rung fills | TP1 is **re-mapped** to the original entry price (now an SR point); remaining TPs shift out | S8-R20 |
| HTF double top after a large run | Take partial profit and move the stop to break-even, regardless of expected resolution | S7-R35, S8-R25 |
| Regime trim signal (coin at resistance **and** USDT.D/BTC.D at support) | Trim, or at minimum move the stop to break-even or better | S3-R32 |

S6-R21's "TP2 → TP1 **or** break-even" is read as a looser restatement of the same ladder and is
discarded as an alternative (CF-29).

### 9.4 Re-entry (CF-21)

Permitted on **any** of:

| Trigger | Source |
|---|---|
| (a) An SFP prints at the same level | S2-R13, S5-R38 |
| (b) A candle **closes back beyond** the lost level | S6-R24, S3-R22 |
| (c) A pre-armed deeper conditional order triggers (stacked conditionals) | TBOT1-R26, `reentry_stacked_conditionals_enabled` |

Constraints: at most `reentry_max_attempts_per_level` (2) attempts per level per
`reentry_window_bars` (100), with a `reentry_cooldown_bars` (3) gap. The stop is relocated beyond
the wick that caused the stop-out (S4-R12). The level's touch counter keeps incrementing, so
`touch_size_decay` shrinks each successive attempt (CF-07). All three of
`reentry_max_attempts_per_level`, `reentry_cooldown_bars` and `reentry_window_bars` are
**OUR numbers** — no cap is stated anywhere (S8-A20, S4-A13).

Zone-level re-takes are governed separately by CF-08 (50% fill), not by this rule.

---

## 10. Risk and portfolio layer

### 10.1 Accounts (CF-43, S2-R32)

| Account | Cut-on-level-loss? | Exit model |
|---|---|---|
| `long_term` | **No** (S2-C6, S2 `[00:53:58]`) | Macro MSB two-step only (S3-R21, S7-R36) + capital withdrawal at 3×, partial at 2× (S2-R18) |
| `spot_short` | Yes (S2-R31) | CF-05 close-below-then-flip (S2-R29, S8-R36) |
| `leverage_swing` | Yes (S2-R31) | Hard stop (S8-R37) |
| `leverage_scalp` | Yes (S2-R31) | Hard stop (S8-R37) |
| `challenge` | Yes (S2-C4) | Hard stop; §10.5 cadence rules (CF-44) |

`account_scoped_cut_rules = true`. This is stated once in two hours — "if you are an investor, this
does not apply to you" (S2 `[00:53:58]`, S2-C6) — and must be encoded explicitly or the bot will
liquidate the investment book on a 4H support break (CF-43).

### 10.2 Per-trade caps

See §8.8. Additionally: `risk_ratchet_up_allowed = false` — **never** increase risk-per-trade after
a winning streak; de-risking downward is permitted (S2-R24, hard).

### 10.3 Concurrency caps (CF-04)

| Bucket | Cap | Alternative | Source |
|---|---|---|---|
| `max_concurrent_leverage_swing` | 2 | 1 (S2-R32's "one swing play") | S4-R30, S4-C8 |
| `max_concurrent_leverage_scalp` | 2 | — | S4-R30 |
| `max_concurrent_leverage_global` | 4 | 2 (strict reading of S4-R30) | S4-C8 |
| `max_concurrent_spot` | 5 | 6 | S4-R31 |

Close or take profit on an existing play before opening a new one when the bucket is full (S4-R31).
Never open a third leverage position by adding to an existing one (S4-R33).

### 10.4 Daily loss halt

| Rule | Value | Source |
|---|---|---|
| `daily_loss_count_limit` | **2** losing trades in one day ends the day | S2-R21 |
| `loss_definition` | `"closed_below_average_entry_net_fees"` — any trade closed below average entry net of fees, not only a stop-out | CF-44, S2-A23 |
| Day boundary | `day_boundary_utc = "00:00"` (P16) | CF-45 |
| Halt scope | Blocks **new** entries; open positions continue to be managed by §9 | **[OUR CHOICE]** — S2-R21 does not say |

### 10.5 Challenge account (CF-44)

| Key | Default | Rule | Source |
|---|---|---|---|
| `challenge_goal_pct` | **8.0** | The most conservative published figure; alternatives 5, 10, 20 | S2 `[01:20:55]`, S2-C7 |
| `challenge_cadence` | `"weekly"` | Daily is leverage-only | S2-R33 |
| `challenge_stop_on_goal` | `true` | Once the period goal is hit, stop trading for the remainder of the period | S2-R22 |
| *(compounding)* | — | Each period's goal = the previous period's closing balance × goal % | S2-R23 |
| *(no chasing)* | — | Never chase a missed goal into the next period | S2 `[01:29:52]` |
| `equity_restart_mode` | `"off"` **[OUR CHOICE]** | S2-R26's halve-the-account-and-restart is recorded but not automated | S2-R26 |

### 10.6 Allocation by market-cap bucket (S2-R16, S2-R17, S2-R19)

Applies to the `long_term` book. Bucket definitions: large cap = top 50, mid cap = rank 50–100,
small cap = newer names with fundamentals, micro cap = memecoins/shitcoins (S2 §2).

| Key | Default | Stated range | Source |
|---|---|---|---|
| `alloc_futures_pct` | 10.0 | 10% | S2-R16 |
| `alloc_cash_min_pct` | 20.0 | ≥20% at all times (a **floor**, per S2-C5) | S2-R17 |
| `alloc_large_cap_pct` | 35.0 | 30–40% | S2-R16 |
| `alloc_mid_cap_pct` | 15.0 | 10–20% | S2-R16 |
| `alloc_small_cap_pct` | 5.0 | 5% | S2-R16 |
| `alloc_micro_cap_pct` | 3.0 | 2–5% | S2-R16 |
| `long_term_max_large_caps` | 5 | 4–5, up to 5–7 | S2-R19 |
| `long_term_max_mid_caps` | 4 | 3–4 | S2-R19 |
| `long_term_derisk_multiple` | 3.0 full / 2.0 partial | Withdraw initial capital at 3×, partial at 2× | S2-R18, CF-43 |
| `spot_short_term_tp_move_pct` | 12.5 | Rotate the short-term spot book after 10–15% moves | S2 `[01:15:16]` |

Take profit into the cash reserve as price rises (S2-R17). Do not over-diversify — 50 coins is
forbidden (S2-R19).

### 10.7 Counter-trend halving

Already specified in §7.5. Portfolio effect: a counter-trend plan consumes a **scalp** concurrency
slot after demotion (`counter_trend_demote_to_scalp`), not a swing slot (CF-03, S7-R10).

### 10.8 Regime size multipliers

| Source flag | Multiplier | Key |
|---|---|---|
| BVOL volatility event active | 0.5 on leverage; spot unaffected | `bvol_size_multiplier` (CF-35, S3-R5) |
| Counter-trend | 0.5 | `counter_trend_size_multiplier` (CF-03) |
| Touch index 4 / 5+ | 0.66 / 0.50 | `touch_size_decay` (CF-07, Q2) |
| Low conviction | risk cap 1.5% | `max_loss_pct_low_conviction` (S6-R26) |

Multipliers **compose multiplicatively** on notional; the risk cap is then re-checked and binds
whichever is smaller. **[OUR CHOICE]** — composition order is never discussed in the corpus.

---

## 11. Configuration reference

Every tunable in one place. Types: `pct` = percentage points; `atr` = multiple of
`ATR(atr_period)`; `bars` = bar count on the object's own timeframe; `enum`, `bool`, `int`,
`decimal`, `list`, `map`, `tf` = a member of the timeframe ladder.

Entries whose **Source** column says **[OUR CHOICE]** or **OUR number** have no basis in the
transcripts and exist only because the bot cannot run without them. Sweep these first.

### 11.1 Risk and position sizing (CF-01 – CF-06)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `max_loss_pct_swing` | 4.0 | pct | 5.0 (his ceiling), 3.0 | CF-01; S2-R20, S3-R24, S5-R32, S6-R11, S7-R8 |
| `max_loss_pct_swing_hard_cap` | 5.0 | pct | 6.0 | CF-01; S6-R11, TBOT1-R13 |
| `max_loss_pct_scalp` | 2.5 | pct | 2.0, 3.0 | CF-01; S2-R20, S3-R24 |
| `max_loss_pct_counter_trend` | 2.0 | pct | 1.0, 3.0 | CF-01; S3-R25, S7-R9 |
| `max_loss_pct_low_conviction` | 1.5 | pct | 2.0 | CF-01; S6-R26 |
| `high_conviction_loss_pct_enabled` | false | bool | true ⇒ uses `max_loss_pct_swing_hard_cap`, swing only | CF-01; TBOT1-R13 |
| `max_notional_pct_leverage` | 100.0 | pct | 73.0 (his accepted worked example), 155.0, 200.0 | CF-02; **Q8 `derived`, S6 `[00:08:36]`–`[00:11:27]`** — 10.0 was a *margin* figure enforced as a *notional* ceiling |
| `margin_pct_leverage` | 10.0 | pct | 20.0 (S3) | CF-02; **Q8 `stated`, S7 `[00:25:54]`** |
| `default_leverage` | 10.0 | decimal | 5.0, 20.0 | CF-02; **Q8 `stated`, S2 `[01:52:12]`** |
| `spot_notional_pct_high_conviction` | 12.0 | pct | — | CF-02; S8-R35 |
| `spot_notional_pct_low_conviction` | 6.0 | pct | — | CF-02; S8-R35 |
| `max_total_spot_deployment_pct` | 70.0 | pct | 60.0 | CF-02; S4-R31, S8-R35 |
| `counter_trend_mode` | `"size_down_and_demote"` | enum | `"veto"` (S7-R17), `"size_down"` | CF-03 |
| `counter_trend_size_multiplier` | 0.5 | decimal | 0.33 | CF-03; S3-R25, S7-R9, S8-R1 |
| `counter_trend_demote_to_scalp` | true | bool | false | CF-03; S7-R10 |
| `max_concurrent_leverage_swing` | 2 | int | 1 | CF-04; S4-R30, S2-R32 |
| `max_concurrent_leverage_scalp` | 2 | int | — | CF-04; S4-R30 |
| `max_concurrent_leverage_global` | 4 | int | 2 | CF-04; S4-C8 |
| `max_concurrent_spot` | 5 | int | 6 | CF-04; S4-R31 |
| `spot_exit_mode` | `"close_below_level_then_flip"` | enum | `"close_below_level"`, `"hard_stop"` | CF-05; S8-R36, TBOT1-R18 |
| `spot_synthetic_stop_for_sizing` | true | bool | false | CF-05 — **our construct** |
| `spot_invalidation_timeframe` | `"1D"` | tf | = trade timeframe | CF-05; TBOT1-R18 |
| `duplicate_stop_offset_bps` | 1.5 | decimal | 0 (single stop) | CF-05; S4-R34 |
| `max_stop_pct_leverage` | 9.0 | pct | 10.0, 16.0 | CF-06; S7-R7, S6 `[00:08:04]` |
| `wide_stop_policy` | `"tighten_then_downgrade_then_skip"` | enum | `"size_down_only"`, `"skip"` | CF-06; S4-R16, S5-R24, TBOT1-R7 |
| `stop_tighten_tf_steps` | 2 | int | 1 | CF-06; S4-R16, S8 `[01:21:46]` |
| `min_stop_pct` | 0.5 | pct | 0.0 (no floor) | CF-06; S7-C8 |
| `leverage_downgrade_max_multiple` | 3.0 | decimal | 2.0, 5.0 | CF-06 ("low leverage" unquantified, TBOT1-A7) — **[OUR CHOICE]** |
| `hedge_enabled` | false | bool | true | S4-R35 — default is **[OUR CHOICE]** |
| `hedge_size_ratio` | 1.0 | decimal | — | S4-R35 |
| `hedge_max_leverage` | 3.0 | decimal | 2.0 | S4-R35 |

### 11.2 Level and zone lifecycle (CF-07 – CF-14)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `line_touch_hard_limit` | 3 | int | 4, 6 | CF-07; S4-R14, S5-R2, S3-R18 |
| `range_boundary_touch_limit` | 6 | int | 5, 999 (until broken) | CF-07; S4-C1 |
| `touch_size_decay` | `[1.0, 1.0, 1.0, 0.66, 0.5]` | list | flat `[1,1,1,1,1]`; previous `[1.0,1.0,0.66,0.5,0.33]`; steep `[1.0,0.75,0.5,0.25,0.0]` | CF-07, **Q2 `inferred`** — curve shape is still OURS; S8 `[00:54:14]` |
| `zone_touch_uses_fill_rule_not_count` | true | bool | false | CF-07; S5-R28, S6-R25 |
| `zone_fill_invalidation_pct` | 50 | pct | 70, 80 (S7-R3), 100 (S8-R21) | CF-08; S5-R28, S6-R10 |
| `zone_fill_measure` | `"wick_touch"` | enum | `"close_beyond"` | CF-08, P6; S5-A10 |
| `zone_fill_reference` | `"as_originally_drawn"` | enum | `"remeasured_after_each_touch"` | CF-08, P6; S5-A11 |
| `dead_zone_htf_support_rescue` | true | bool | false | CF-08; S7-R4, S7-C3 |
| `dead_zone_rescue_max_touches` | 3 | int | 2 | CF-08; S7-R4 |
| `ob_max_candles` | 1 | int | 3 (mini-zone) | CF-09; S6-R3 |
| `ob_box_source` | `"body_with_small_wick"` | enum | `"body_only"`, `"full_range"` | CF-09, P5; S6-R9 |
| `ob_inside_zone_precedence` | `"zone_wins"` | enum | `"ob_wins"` | CF-09; S6-R31 |
| `ob_liquidity_measure` | `"deepest_wick_through_body_range"` | enum | — | P15; S7-A2 — **[OUR CHOICE]** |
| `zone_direction_mode` | `"both"` | enum | `"continuation_only"`, `"reversal_only"` | CF-10; S5-R15, S6-R4/R5, S6-A26 |
| `zone_continuation_confluence_bonus` | 1.0 | decimal | 0 | CF-10 — **OUR number** |
| `sufficient_gap_pct_by_tf` | §5.5 table | map | `"his_upper_bounds"` (5/5/8/…/12/13) | CF-11; S5-R16 (4 rows interpolated — **[OUR CHOICE]**; **F5** confirms they are absent from the frames too — no sweep bracket is derivable) |
| `sufficient_gap_atr_mult` | 2.0 | atr | 1.5, 3.0 | CF-11 — **OUR number** |
| `sufficient_gap_require_both_tests` | true | bool | false (percentage only) | CF-11 |
| `sufficient_gap_anchor` | `"breakout_close_to_extreme"` | enum | `"zone_top_to_extreme"`, `"zone_mid_to_close"` | P10; S5-A1 — **[OUR CHOICE]** |
| `sufficient_gap_retrace_cutoff` | 0.5 | decimal | 0.33, 0.618 | P10 — **[OUR CHOICE]** |
| `min_zone_depth_atr` | 0.5 | atr | 0.3, 0.75 | CF-12; S6-R48, S7-R6 — **normalisation is OURS** |
| `max_zone_depth_atr` | 3.0 | atr | 2.0, 5.0 | CF-12; S8-R23 — **normalisation is OURS** |
| `min_zone_bodies` | 2 | int | 3 | CF-12; S5-R17 |
| `zone_within_zone_policy` | `"larger_if_within_max_depth"` | enum | `"always_larger"` | CF-12; S5-R30 |
| `wick_include_max_pct` | 2.0 | pct | 1.0, 3.0 | CF-13, P5; S7-R7 |
| `wick_include_max_atr` | 0.5 | atr | disabled | CF-13, P5 — **OUR number** |
| `zone_box_source` | `"body_plus_small_wick"` | enum | `"body_only"`, `"full_range"` | CF-13; S5-R17, S5-R19, S6-R9 |
| `zone_wick_band_enabled` | false | bool | true | **F1** — S6 frame 52:38; single-frame observation, **weakened** by pass 2 (two-box form in ~1 frame in 4; the one clear example was mid-drag) |
| `zone_wick_band_max_ratio` | 1.0 | decimal | sweep 0.30–1.00 | **F1** — S6 frame 52:38 read 83 %, the same drawing at 53:46 read 33 % (mid-drag): a factor-of-2.5 disagreement, so the ratio is not a trustworthy number |
| `stop_wick_max_pct` | 3.0 | pct | 2.0, 3.4 (his exact rejected wick) | CF-14; S6-R18 |
| `stop_buffer_atr` | 0.15 | atr | 0.05, 0.25, 0.5 | CF-14, P19 — **OUR number**; S2-A8, TBOT1-A14; **fallback only**, for stops not anchored to a zone |
| `stop_buffer_zone_fraction` | 0.5 | decimal | sweep 0.45–0.60 | **F6** — TBOT1 4:11, TBOT1 1:09:19, S8 1:28:33; three frames at 0.48 / 0.49 / 0.58 of the zone height |
| `stop_never_beyond_opposing_level` | true | bool | false | CF-14; S5-R25, S6-R19 |

### 11.3 Flip confirmation and entry mechanics (CF-15 – CF-21)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `flip_confirm_candles` | 2 | int | 3 (S4-R5 literal) | CF-15; S5-R3, S2-R1/R2/R3 |
| `flip_extra_candle_below_tf` | `"4H"` | tf | `"1H"`, disabled | CF-15; S2-R7 |
| `flip_requires_body_close` | true | bool | false | CF-15; S4-R5, S8-R41 |
| `pending_sr_expiry_bars` | 60 | bars | 30, 200, 0 (never expires) | CF-15 — **OUR number**; S2-A15 |
| `entry_family_retest_enabled` | true | bool | false | CF-16; S3-R13, S5-R20, S6-R14, S7-R18, S8-R16 |
| `entry_family_flip_pending_enabled` | true | bool | false | CF-16; S4-R19 |
| `entry_family_trigger_enabled` | true | bool | false | CF-16; CF-20, CF-22 |
| `allow_market_orders` | `"trigger_family_only"` | enum | `"never"` (S4-R32 literal), `"always"` | CF-16; S4-R32, TBOT1-R25 |
| `dca_count_default` | 1 | int | 0, 2 | CF-17; S6-R16 |
| `dca_count_max` | 2 | int | 3 (S2-R9 upper bound) | CF-17; S2-R9, S6 `[01:01:51]` |
| `dca_count_scalp_max` | 1 | int | 0 | CF-17; S8-R17 |
| `dca_count_breakdown` | 0 | int | — | CF-17; S8-R11 |
| `dca2_min_zone_depth_atr` | 1.5 | atr | 1.0, 2.0 | CF-17 — **OUR number**; S5-R22 |
| `dca_size_split_2` | `[0.39, 0.61]` | list | `[0.50,0.50]` (spot only), `[0.30,0.70]`; **sweep bracket 0.32–0.40** on the first leg | CF-18 — **Q3 `derived`, S6 `[00:48:10]`**; **corroborated by F2** (S6 frames 9:40–10:53, ORDI 15 @ 35.51 + 25 @ 40.11 = 37.5/62.5, within 1.5 pts) |
| `dca_size_split_3` | `[0.20, 0.30, 0.50]` | list | `[0.33,0.33,0.33]`, `[0.15,0.25,0.60]` | CF-18 — **OUR ratio**; S4 `[02:04:56]` |
| `dca_size_split_wick_heavy_2` | `[0.20, 0.80]` | list | `[0.30,0.70]` | CF-18; S6-R27 |
| `size_and_stop_computed_from` | `"average_entry"` | enum | `"first_entry"` | CF-18; S6-R12 |
| `average_up_enabled` | false | bool | true | CF-19; S3-R13, S3-A10 |
| `average_up_trigger_atr` | 2.0 | atr | 1.0, 3.0 | CF-19 — **OUR number** |
| `average_up_only_at_sr_point` | true | bool | false | CF-19; S3-R14 |
| `sfp_entry_price` | `"confirming_close"` | enum | `"next_open"` | CF-20; S7-R21, S8-R5, S7-C6 |
| `sfp_standalone_enabled` | false | bool | true (backtest-only) | CF-20; S7-R30, S7-C5 |
| `sfp_min_bars_between` | 3 | bars | 1, 5 | CF-20 — **OUR number**; S7-R25, S7-A11 |
| `sfp_min_swing_separation_atr` | 1.0 | atr | 0.5, 2.0 | CF-20 — **OUR number**; S7-R28, S8-R4 |
| `sfp_max_close_distance_atr` | 1.5 | atr | 1.0, 2.5 | CF-20 — **OUR number**; S5-R7 |
| `sfp_trend_veto` | true | bool | false | CF-20; S7-R31 |
| `sfp_governing_timeframe` | `"highest_valid"` | enum | `"trade_structure_tf"`, `"1D"` | CF-20; **Q7 `inferred`, S8 `[00:23:06]`, S7 `[01:24:22]`** |
| `sfp_raid_price_source` | `"wick"` | enum | `"body"` | CF-20, P1; **Q6 `stated`, S7 `[01:14:44]`** |
| `reentry_trigger` | `"sfp_or_close_reclaim"` | enum | `"sfp_only"`, `"close_reclaim_only"`, `"any"` | CF-21; S2-R13, S6-R24 |
| `reentry_max_attempts_per_level` | 2 | int | 1, 3 | CF-21 — **OUR number**; S8-A20 |
| `reentry_cooldown_bars` | 3 | bars | 0, 10 | CF-21 — **OUR number** |
| `reentry_window_bars` | 100 | bars | 50, 200 | CF-21 — **OUR number** |
| `reentry_stacked_conditionals_enabled` | true | bool | false | CF-21; TBOT1-R26 |

### 11.4 Structure and trend (CF-22 – CF-24)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `msb_exit_mode` | `"break_only"` | enum | `"break_plus_lower_high"` | CF-22; S7-R12, S3-R21, S2-R28 |
| `msb_entry_requires_retest` | true | bool | false | CF-22; S7-R15/R16, S8-R26, TBOT1-R15 |
| `msb_retest_timeout_bars` | 20 | bars | 10, 40 | CF-22 — **OUR number**; S7-A20 |
| `msb_price_source` | `"body_close"` | enum | `"wick"` | CF-22; S7-R12, S7-R11 |
| `higher_low_selection` | `"technical"` | enum | `"confluence_weighted"` | CF-23; S7-R12, S8-C2 |
| `bias_level_enabled` | true | bool | false | CF-23 (spot/long-term only); S8-C2 |
| `bias_level_min_confluence` | 2 | decimal | 3 | CF-23 — **OUR number** |
| `bias_level_lookback_bars` | 200 | bars | 100, 400 | CF-23 — **OUR number** |
| `structure_tf_offset` | 2 | int | 1, 3 | CF-24 — **OUR construct**; S7-A8, S7-A9 |
| `htf_veto_enabled` | true | bool | false | CF-24; S7-R20, S8 `[00:38:57]` |
| `htf_veto_timeframe` | `"1D"` | tf | = structure TF | CF-24 |
| `swing_k` | 3 | int | 2, 4 — **sweep bracket 2–4** (5 on weekly/monthly) | P1 — **[OUR CHOICE]**; S7-A7; **F4** (S7 frame 34:30) bounds the width at ≤4 there, ruling out ≥5 for that instance only |
| `swing_price_source` | `"body"` | enum | `"wick"` | P1; S7-R11, S5-R44 |
| `trend_pivot_count` | 4 | int | 2, 6 | P11 — **[OUR CHOICE]** |
| `trend_timeframe` | `"structure_tf"` | enum | any tf | P11; CF-24 |
| `dir_change_atr` | 2.0 | atr | 1.5, 3.0 | P2 — **[OUR CHOICE]**; S6-A1 |
| `dir_change_max_bars` | 10 | bars | 5, 20 | P2 — **[OUR CHOICE]** |
| `level_lookback_bars` | 500 | bars | 250, 1000 | P3 — **[OUR CHOICE]**; S2-A3 |
| `level_cluster_atr` | 0.25 | atr | 0.15, 0.5 | P3 — **[OUR CHOICE]**; S4-A2 |
| `level_min_touches` | 2 | int | 3 | P3; S4-R4, S7 `[00:05:04]` |
| `level_tolerance_atr` | 0.15 | atr | 0.1, 0.3 | P4/P9 — **[OUR CHOICE]**; S2-A2, S3-A8 |
| `touch_reset_atr` | 0.5 | atr | 0.25, 1.0 | P4 — **[OUR CHOICE]**; TBOT1-A6 |
| `capitulation_wick_atr` | 3.0 | atr | 2.0, 4.0 | P12 — **[OUR CHOICE]**; TBOT1-A15, S8-A17 |
| `capitulation_wick_body_ratio` | 3.0 | decimal | 2.0, 4.0 | P12 — **[OUR CHOICE]** |
| `capitulation_volume_mult` | 2.0 | decimal | 1.5, 3.0 | P12 — **[OUR CHOICE]** |
| `consolidation_max_drift_atr` | 0.75 | atr | 0.5, 1.0 | P13 — **[OUR CHOICE]**; S5-A5, S6-A27 |
| `consolidation_max_height_atr` | 2.0 | atr | 1.5, 3.0 | P13 — **[OUR CHOICE]** |
| `consolidation_min_bars` | 2 | bars | 3 | P13; S5-R17 |

### 11.5 Range and mid-range (CF-25 – CF-26)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `mid_range_band_pct` | 15.0 | pct of range height, each side | 10.0, 20.0 | CF-25 — **OUR number**; S4-A3, S8-A14 |
| `mid_range_limits_from_extremes_enabled` | true | bool | false | CF-25; S4-R6, S4-R7, S4 `[00:34:02]` |
| `mid_range_requires_intermediate_stop` | true | bool | false | CF-25; S5-R13 |
| `range_death_mode` | `"close_beyond_plus_flip"` | enum | `"close_beyond"`, `"single_stopout"` | CF-26; S4-A16 |
| `mid_range_search_pct` | 10.0 | pct of range height | 0 (pure geometric 50%) | CF-26, P7 — **OUR resolution**; S4-A1 |
| `range_min_height_atr` | 3.0 | atr | 2.0, 5.0 | CF-26, P8 — **OUR number**; S4-A15 |
| `range_max_age_bars` | 300 | bars | 150, 600 | CF-26, P8 — **OUR number** |
| `range_min_bars` | 20 | bars | 10, 40 | P8 — **[OUR CHOICE]** |
| `range_stale_bars` | 60 | bars | 30, 120 | P8 — **[OUR CHOICE]** |
| `monday_range_source_tf` | `"1D"` | tf | — (execution on 1H/30m) | CF-45; S5-R8, S5-R9 |

### 11.6 Take profit and trade management (CF-27 – CF-30)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `tp_count_swing` | 2 | int | 3 | CF-27; S4-R1/R2, S6-R20 |
| `tp_count_scalp` | 3 | int | 2 | CF-27; S8-R19, TBOT1-R17 |
| `tp_count_price_discovery_max` | 5 | int | 3 | CF-27; S6-R36 |
| `tp_min_count` | 2 | int | — (hard) | CF-27; S5-R26 |
| `tp_split_2` | `[0.50, 0.50]` | list | `[0.60, 0.40]` | CF-28; S4-R10 |
| `tp_split_3` | `[0.40, 0.30, 0.30]` | list | `[0.50, 0.25, 0.25]` | CF-28; S4-R10 |
| `tp_split_4` | `[0.40, 0.25, 0.20, 0.15]` | list | — | CF-28 — **OURS** |
| `tp_split_5` | `[0.35, 0.25, 0.20, 0.12, 0.08]` | list | — | CF-28 — **OURS** |
| `tp_residual_policy` | `"trail_out"` | enum | `"close_at_last_tp"` | CF-28 |
| `trail_on_tp1` | `"break_even"` | enum | `"none"`, `"tp_minus_one_atr"` | CF-29; S4-R11, S5-R27 |
| `trail_on_tp2` | `"tp1_price"` | enum | `"break_even"` (S6-R21) | CF-29; S4-R11, S5-R27 |
| `break_even_reference` | `"average_entry"` | enum | `"first_entry"` | CF-29; CF-18 |
| `stale_exit_enabled` | false | bool | true | CF-30; S6-A17 |
| `stale_exit_bars` | 8 | bars | 4, 16 | CF-30, P17 — **OUR number** |
| `stale_exit_mae_atr` | 1.0 | atr | 0.5, 1.5 | CF-30, P17 — **OUR number** |
| `reaction_threshold_atr` | 0.75 | atr | 0.5, 1.0 | P17 — **[OUR CHOICE]** |
| `structural_stale_exit_enabled` | true | bool | false | CF-30; S6-R22, S6-R23, S7-R39, S8-R9 |

### 11.7 Confluence, pipeline, fibs and indicators (CF-31 – CF-36)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `min_confluence_count` | 3.0 | decimal (weighted) | 2.0, 4.0 | CF-31; S5 `[01:43:55]` |
| `confluence_weights` | §6.1 map | map | `"flat"` (all 1.0) | CF-31 — **weights are OURS**; S6-A15 |
| `confluence_merge_atr` | 0.25 | atr | 0.15, 0.5 | CF-31, P14 — **OUR number**; TBOT1-A4 |
| `confluence_dedup_same_class` | true | bool | false | CF-31, P14 |
| `single_class_trade_forbidden` | true | bool | false | CF-31; S4-R38, S6-R29, S6-R30, S7-R30, S7-R39 |
| `high_conviction_score` | 4.0 | decimal | 3.5, 5.0 | §6.3 — **[OUR CHOICE]**; S6 `[01:35:26]` |
| `pipeline_order` | §3.1 sequence | list | `"patterns_before_fibs"` | CF-32; S6-R28, S6-C2 |
| `fib_loses_ties_to_sr` | true | bool | false | CF-32; S6-R38 |
| `sfp_evaluated_last` | true | bool | false | CF-32; S7-R30 |
| `golden_pocket_band` | `[0.618, 0.66]` | list | `[0.618, 0.65]`, `[0.618, 0.66] ∪ [0.65]` | CF-33; S6-R32, S6-A23 |
| `fib_levels_active` | `[0.618, 0.66, 0.786]` | list | `[0.236, 0.618, 0.66, 0.786, 0.886]` | CF-33; S6-R33 |
| `fib_886_enabled` | false | bool | true | CF-33; S6-A22 (precedence rule 4) |
| `fib_entry_level` | `0.618–0.66` | band | — | CF-33; TBOT1-R5 |
| `fib_dca_level` | 0.786 | decimal | — | CF-33; S6-R15, TBOT1-R5 |
| `fib_draw_convention` | `"s6"` (bullish = low→high) | enum | `"tbot1"` (inverted) | CF-34; S6-R34, S6-R35, S6-C6, S7-R1 |
| `fib_anchor_selection` | `"most_recent_qualifying_swing_pair"` | enum | `"largest_leg"`, `"manual"` | CF-34 — **[OUR CHOICE]**; S6-A16, TBOT1-A2 |
| `dxy_gate_enabled` | false | bool | true | CF-35; S3-C8, S3-A21 |
| `dxy_gate_min_rolling_corr` | 0.4 over 90 days | decimal | 0.3, 0.5 | CF-35 — **OUR construct** |
| `context_priority` | `["USDT.D", "BTC.D", "BVOL"]` | list | S3-R11's full order incl. DXY | CF-35; S3-R11 |
| `bvol_zone` | `[0.81, 1.40]` | list | `[0.19, 0.81]`, `[1.8, 2.2]` | CF-35; S3-R7 |
| `bvol_event_window_hours` | 72 | int (hours) | 48, 96 | CF-35; S3-R1, S3-C2 |
| `bvol_size_multiplier` | 0.5 | decimal | 0.0 (stand aside) | CF-35; S3-R5 |
| `all_pairs_at_resistance_veto` | true | bool | false | CF-35; TBOT1-R20 |
| `rsi_divergence_mode` | `"confluence_only"` | enum | `"off"` (S8 literal), `"standalone"` (TBOT1-R11) | CF-36; S8-C3 |
| `rsi_period` | 14 | int | 7, 21 | CF-36 — **OURS**; S8-A19 |
| `rsi_timeframe` | `"structure_tf"` | enum | any tf | CF-36 — **OURS**; S8-A19 |
| `rsi_oversold` | 30 | int | 50 (S8-R40) | CF-36; S8-R40, S8-C4 |
| `rsi_overbought` | 70 | int | 80 (S8-R40) | CF-36; S8-R40, S8-C4 |
| `ema200_confluence_enabled` | false | bool | true (daily only) | CF-36; S6 `[01:09:27]` |

### 11.8 Modules, timeframe classes, calendar and universe (CF-37 – CF-41)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `module_chart_patterns_enabled` | false | bool | true (confluence-only when on) | CF-37; S8-C1, S4-R38 |
| `module_trendline_break_enabled` | false | bool | true | CF-37; S8-C1, S8 `[00:30:37]` |
| `module_scalp_enabled` | **true** | bool | false | CF-37; **Q14 `inferred` (reverses CF-37), S5 `[01:41:45]`, S5 `[01:42:50]`** |
| `disowned_modules_still_score_confluence` | true | bool | false | CF-37 |
| `swing_tf_floor` | `"4H"` | tf | `"8H"` (S5-R34 strict) | CF-38; S5-R34, S6 `[00:57:15]` |
| `scalp_tf_ceiling` | `"2H"` | tf | `"4H"` (S8-R14) | CF-38; S5-R34 |
| `scalp_tf_floor` | `"30m"` | tf | `"15m"`, `"5m"` (reachable only via `counter_trend_demote_to_scalp`, S7-R10) | CF-38; **Q14 `stated`, S5-R34 / S5 `[01:41:45]`** |
| `event_blackout_mode` | `"leverage_only"` | enum | `"all"` (S2-R27), `"none"` | CF-39; S8-R2 |
| `event_blackout_hours` | 24 | int (hours) | 12, 48 | CF-39 — **OUR number** |
| `event_resume_requires_range` | true | bool | false | CF-39; S2-R27 |
| `weekend_mode` | `"leverage_blocked"` | enum | `"block_all"` (S5-R37), `"normal"` | CF-39; TBOT1-R24, TBOT1-C8 |
| `event_tf_step_up` | 1 | int | 0, 2 | CF-39; S5-R36 |
| `leverage_max_mcap_rank` | 100 | int | 50, 200 | CF-40; S2 §2 (large/mid boundary) |
| `min_daily_volume_usd` | 50_000_000 | int (USD) | 10_000_000, 100_000_000 | CF-40, P18 — floor is **OURS**; S8-R31 |
| `new_listing_days` | 30 | int (days) | 14, 60 | CF-40 — **OUR number**; S6-R44 |
| `universe_max_symbols` | 3 | int | 5 (S3-R29) | CF-40; S8-R33 |
| `scalp_excludes_btc` | true | bool | false | CF-40; S8-R32 |
| `memecoin_vehicle` | `"spot_only"` | enum | `"excluded"`, `"any"` | CF-40; S6-R45, S7-R38 |
| `max_median_wick_ratio` | 0.55 | decimal | 0.45, 0.65 | P18 — **[OUR CHOICE]**; S2-R35, S2-A20 |
| `max_wicky_bar_fraction` | 0.40 | decimal | 0.30, 0.50 | P18 — **[OUR CHOICE]**; S7-A24 |
| `shorts_enabled` | true | bool | false (S7 `[00:31:36]` literal) | CF-41; S7-C9 |
| `net_short_allowed_in_uptrend` | false | bool | true | CF-41; S4-R36 |
| `short_in_price_discovery` | false | bool | — (hard) | CF-41; S3-R28, S6-R37 |
| `min_expected_move_pct` | `{scalp: 2.0, swing: 5.0}` | map | `{scalp: 1.0, swing: 3.0}` | CF-41; S3-R15, S6-R8, S8 `[00:47:58]` |
| `cup_handle_floor_pct` | 45.0 | pct of cup depth | 40.0, 50.0 | S4-R24, S4-A9 — midpoint is **[OUR CHOICE]** |
| `pattern_pole_anchor` | `"most_recent_impulse"` | enum | `"first_impulse"` (S5-R39) | S4-R17, S4-C6 — **[OUR CHOICE]** |

### 11.9 R:R, accounts, challenge and clock (CF-42 – CF-45)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `min_rr` | 2.0 | decimal | 1.5, 3.0 | CF-42 — OUR number, **corroborated as a floor by F9** (four observed trades, 2.13–5.00, lowest 2.13); S3-R26 (1:1 rejected); sweep 2.0–2.5 |
| `rr_measured_to` | `"final_tp"` | enum | `"tp1"` | CF-42; **F9** — his position tool measures R:R to its single target line (TBOT1 4:11 / 22:59 / 1:09:19, S8 1:28:33). Was `"tp1"`. |
| `rr_measured_from` | `"average_entry"` | enum | `"first_entry"` | CF-42; CF-18 |
| `account_scoped_cut_rules` | true | bool | false | CF-43; S2-C6, S2 `[00:53:58]` |
| `long_term_exit_mode` | `"macro_msb_two_step"` | enum | `"level_loss"` | CF-43; S3-R21, S7-R36 |
| `long_term_derisk_multiple` | 3.0 full / 2.0 partial | map | — | CF-43; S2-R18 |
| `challenge_goal_pct` | 8.0 | pct | 5.0, 10.0, 20.0 | CF-44; S2-C7 |
| `challenge_cadence` | `"weekly"` | enum | `"daily"` (leverage only) | CF-44; S2-R33 |
| `challenge_stop_on_goal` | true | bool | false | CF-44; S2-R22 |
| `daily_loss_count_limit` | 2 | int | 1, 3 | CF-44; S2-R21 |
| `loss_definition` | `"closed_below_average_entry_net_fees"` | enum | `"stop_out_only"` | CF-44; S2-A23 |
| `risk_ratchet_up_allowed` | false | bool | — (hard) | CF-44; S2-R24 |
| `equity_restart_mode` | `"off"` | enum | `"halve_on_drawdown"` | S2-R26 — default is **[OUR CHOICE]** |
| `day_boundary_utc` | `"00:00"` | time | `"01:00"` (literal 17:00 PST) | CF-45, P16; S5-R8, S8-R44 |

### 11.10 Portfolio allocation (S2-R16 – S2-R19)

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `alloc_futures_pct` | 10.0 | pct | — | S2-R16 |
| `alloc_cash_min_pct` | 20.0 | pct | floor, not a target | S2-R17, S2-C5 |
| `alloc_large_cap_pct` | 35.0 | pct | 30.0–40.0 | S2-R16 |
| `alloc_mid_cap_pct` | 15.0 | pct | 10.0–20.0 | S2-R16 |
| `alloc_small_cap_pct` | 5.0 | pct | — | S2-R16 |
| `alloc_micro_cap_pct` | 3.0 | pct | 2.0–5.0 | S2-R16 |
| `long_term_max_large_caps` | 5 | int | 4–7 | S2-R19 |
| `long_term_max_mid_caps` | 4 | int | 3–4 | S2-R19 |
| `spot_short_term_tp_move_pct` | 12.5 | pct | 10.0–15.0 | S2 `[01:15:16]` |

### 11.11 Numerics and entry-price resolution

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `atr_period` | 14 | int | 10, 20 | ATR(14) is assumed throughout CONFLICTS.md — **[OUR CHOICE]** |
| `pmt_bin_atr` | 0.05 | atr | 0.02, 0.10 | P20 — **[OUR CHOICE]**; S5-A15 |

### 11.12 Backtest harness — all **[OUR CHOICE]**

| Key | Default | Type | Allowed / alternatives | Source |
|---|---|---|---|---|
| `backtest_execution_tf` | `"1m"` | tf | `"5m"`, `"trade_tf"` (bar-close only) | **[OUR CHOICE]** — §12.2 |
| `intrabar_fill_model` | `"stop_first"` | enum | `"tp_first"`, `"proportional"` | **[OUR CHOICE]** — §12.2, deliberately pessimistic |
| `fee_maker_bps` | 2.0 | bps | 0.0–10.0 | **[OUR CHOICE]** |
| `fee_taker_bps` | 5.5 | bps | 0.0–15.0 | **[OUR CHOICE]** |
| `slippage_limit_bps` | 0.0 | bps | 0.0–5.0 | **[OUR CHOICE]** — limits fill at price or not at all |
| `slippage_market_bps` | 5.0 | bps | 0.0–25.0 | **[OUR CHOICE]** |
| `funding_bps_per_8h` | 1.0 | bps | 0.0–5.0 | **[OUR CHOICE]** — leverage only |
| `limit_fill_requires_trade_through` | true | bool | false (touch is enough) | **[OUR CHOICE]** — §12.2 |

### 11.13 Key count

| Group | Keys |
|---|---|
| 11.1 Risk and position sizing | 29 (+4 GAP-2-derived: `max_correlated_concurrent_enabled`, `max_correlated_concurrent`, `correlation_threshold`, `correlation_lookback_bars` — all [OUR CHOICE], GAPS.md GAP 2) |
| 11.2 Level and zone lifecycle | 30 (+3 frame-derived: `zone_wick_band_enabled`, `zone_wick_band_max_ratio` (F1), `stop_buffer_zone_fraction` (F6)) |
| 11.3 Flip confirmation and entry mechanics | 32 (+2 Discord-derived: `max_entry_distance_enabled`, `max_entry_distance_pct` (DISCORD CHECK 2026-09-15)) |
| 11.4 Structure and trend | 28 |
| 11.5 Range and mid-range | 10 |
| 11.6 Take profit and trade management | 17 |
| 11.7 Confluence, pipeline, fibs, indicators | 29 |
| 11.8 Modules, timeframes, calendar, universe | 26 |
| 11.9 R:R, accounts, challenge, clock | 14 |
| 11.10 Portfolio allocation | 9 |
| 11.11 Numerics | 2 |
| 11.12 Backtest harness | 8 |
| **Total** | **234** |

Of these, **177** are the named keys of CONFLICTS.md's own index, plus 5 keys stated inline in
CONFLICTS.md bullets (`dead_zone_rescue_max_touches`, `fib_dca_level`, `tp_split_5`,
`rsi_overbought`, `rsi_timeframe`), plus 26 parameters introduced by primitives P1–P20, plus 26
keys added by this spec (portfolio allocation, hedging, numerics, pattern geometry, conviction
threshold and the backtest harness), every one of which is marked **[OUR CHOICE]** or carries an
S2/S4 rule ID. 177 + 5 + 26 + 26 = **234**.

The implemented surface is larger: **234 + 8 evidence-derived** keys (`CHANGELOG_EVIDENCE.md`,
Q1–Q15) **+ 3 frame-derived** keys (`FRAME_FINDINGS.md` F1: `zone_wick_band_enabled`,
`zone_wick_band_max_ratio`; F6: `stop_buffer_zone_fraction`) **+ 2 Discord-derived** keys
(`CHANGELOG_EVIDENCE.md`, DISCORD CHECK 2026-09-15: `max_entry_distance_enabled`,
`max_entry_distance_pct`) **+ 4 GAP-2-derived** keys (GAPS.md GAP 2, the correlated-exposure
cap) = **251**, which is what `tbot.config.KEY_SPECS` holds.

**`sweep_bracket`.** A `KeySpec` may carry a machine-readable `(low, high)` bracket wherever
evidence has bounded a key without deciding it, so a parameter sweep reads its search range off the
config instead of parsing it out of prose. Recorded so far: `dca_size_split_2` **0.32–0.40** (F2,
three worked examples), `swing_k` **2–4** (F4), `zone_wick_band_max_ratio` **0.30–1.00** (F1, two
readings of one drawing 2.5× apart), `stop_buffer_zone_fraction` **0.45–0.60** (F6, three frames at
0.48 / 0.49 / 0.58), `min_rr` **2.0–2.5** (F9, four observed R:R readouts spanning 2.13–5.00).
`sufficient_gap_pct_by_tf` deliberately carries **none** — F5 is a negative result and no bracket is
derivable from the corpus.

---

## 12. Backtest harness requirements

### 12.1 Bar-by-bar simulation

| Requirement | Specification | Source |
|---|---|---|
| Loop | One pass, chronological, over bars of `backtest_execution_tf`. Higher-timeframe bars are emitted to the analysis pipeline only at their **close** | P1 (no repainting) |
| Detector inputs | Detectors see only bars with `is_closed = True` and pivots with `confirmed_at_index ≤ now` | P1 |
| No lookahead | A level, zone, OB, fib anchor or pattern may only be used from the first bar at which every constituent pivot was confirmed. A zone is unusable until its sufficient-gap test has completed (P10) | P1, P10, S5-R15 |
| Multi-timeframe | Maintain one aligned candle series per ladder timeframe; daily bars are cut at `day_boundary_utc` | P16, CF-45 |
| Order lifecycle | Resting limits persist across bars until filled, cancelled or expired; the state machine of §9 is evaluated once per execution bar | §9 |
| Warm-up | Discard the first `max(level_lookback_bars, atr_period, bias_level_lookback_bars)` bars per symbol | **[OUR CHOICE]** |

### 12.2 Intrabar fill assumptions — stated explicitly and conservatively

The corpus contains no execution model, so **all of the following is [OUR CHOICE]** and is chosen
to be pessimistic. Report every metric under these assumptions and never soften them.

| Assumption | Rule |
|---|---|
| **A1 — Adverse-first** | When a bar's range contains both the stop and a TP, the **stop is assumed to fill first** (`intrabar_fill_model = "stop_first"`). Never assume the favourable order. |
| **A2 — Entry then stop** | When a bar's range contains both an entry rung and the stop, the entry fills **and then** the stop fills in the same bar. A same-bar entry-and-stop is a full loss, not a skipped trade. |
| **A3 — Limits need trade-through** | A resting limit fills only if the bar trades **strictly through** the limit price (`limit_fill_requires_trade_through = true`); a bar that merely touches the price does not fill. |
| **A4 — Limits fill at their price** | A filled limit fills at exactly its price, with `slippage_limit_bps = 0` and `fee_maker_bps`. No price improvement is ever credited. |
| **A5 — Market/trigger fills** | Trigger-family entries (SFP, MSB retest) fill at the **next bar's open** plus `slippage_market_bps` adverse, with `fee_taker_bps`. |
| **A6 — Stops are market** | A stop fills at the worse of (stop price, next tick) plus `slippage_market_bps` adverse, with `fee_taker_bps`. Gaps fill at the open, at the gapped price — no stop is ever honoured better than the market. |
| **A7 — Partial rungs** | An unfilled rung is unfilled. Never assume a partial ladder fills "close enough"; this is what makes `average_entry` honest. |
| **A8 — Spot excess risk** | For spot, the close-below-then-flip exit (CF-05) may land far past the synthetic stop. The difference is recorded as `Fill.excess_risk_usd` and reported separately; it is **not** netted out of the risk statistics. |
| **A9 — Duplicate stops** | Only the first of the CF-05/S4-R34 duplicate stops is simulated. The second is an execution-reliability device with no backtest meaning. |
| **A10 — No intrabar path** | Where sub-bar data is unavailable, the bar is treated as OHLC only; A1 and A2 govern all ambiguity. |
| **A11 — Funding** | Leverage positions accrue `funding_bps_per_8h` against the position, charged on the `day_boundary_utc` schedule. |
| **A12 — Liquidation** | Cross margin is assumed (S4 `[01:59:38]`); a position whose loss exceeds the account equity is force-closed and flagged. This should never fire if §8.8 sizing is correct — if it does, it is a bug, not a result. |

### 12.3 Fees and slippage

| Component | Default | Applies to |
|---|---|---|
| Maker fee | `fee_maker_bps` = 2.0 | every limit fill (entries, DCAs, TPs placed as limits) |
| Taker fee | `fee_taker_bps` = 5.5 | every market fill (stops, trigger entries, structural exits) |
| Limit slippage | `slippage_limit_bps` = 0.0 | — |
| Market slippage | `slippage_market_bps` = 5.0 | adverse only, never favourable |
| Funding | `funding_bps_per_8h` = 1.0 | leverage positions |

All are **[OUR CHOICE]**. Fees and slippage are charged inside the P&L before any metric is computed;
no metric may be reported gross.

### 12.4 Metrics to report

The metric set and its definitions are **[OUR CHOICE]** — the corpus contains no performance
framework beyond a manual win-rate field in his trade log (S2-A24).

| Metric | Definition | Notes |
|---|---|---|
| **Win rate** | Closed trades with realised P&L > 0, net of fees, over all closed trades | A trade closed at TP1 with the residual trailed out at break-even is **one** trade, not two. A trail-out at TP1 after TP2 (CF-29, S5 `[00:40:00]`) is a **win** |
| **Win-rate variants** | Also report win rate counting only full-TP-ladder completions, and counting break-even exits separately | S5-A19 flags that "a win" is undefined in the corpus — report all three so the ambiguity is visible |
| **Expectancy** | Mean R per trade = mean(`r_multiple`), where R is measured from `average_entry` against the **initial** stop | CF-42, CF-18 |
| **Max drawdown** | Peak-to-trough on the equity curve, per account and portfolio-wide, in % and in USD | §10.1 accounts |
| **R distribution** | Histogram of `r_multiple`, plus P5/P25/median/P75/P95, plus the count of `< -1R` outcomes (slippage/gap losses) | A2, A6 |
| **Per-detector attribution** | For every detector class in §5, the count / win rate / expectancy / total R of trades whose **primary** anchor was that class; plus its marginal contribution as a confluence member | CF-31, CF-37 |
| **Per-config attribution** | Same breakdown split by `trade_class`, `vehicle`, `conviction`, `touch_index_at_entry`, and `entry_family` | CF-07, CF-16, CF-38 |
| **Fill quality** | Rung fill rate per ladder position, and the realised vs planned `average_entry` gap | CF-18, A7 |
| **Excess risk** | Total and per-trade `excess_risk_usd` from spot exits | CF-05, A8 |
| **Veto census** | Count of setups stopped by each §7 gate — this shows which gate is actually shaping the strategy | §7 |
| **Time in market** | Bars in trade by class; median holding period vs his stated expectations (scalp hours→a day, swing days→weeks) | S2 `[01:17:02]` |

### 12.5 The 77–82% claim

S5 `[00:38:20]` and S5 `[01:15:40]` state a back-tested win rate of **77–82%** for the
supply/demand method; S4-C2 records further recollections of 8/10, 7/10, 10-for-14 and 7-for-7.
CONFLICTS.md rules these **not usable for sizing or validation** — "recollections, no sample, no win
definition; do not encode as a target."

Therefore:

1. The figure is a **hypothesis** the backtest exists to test, stated as such in every report.
2. No sizing, expectancy, Kelly fraction or capacity calculation may reference it.
3. The harness must report the measured win rate beside the claim, with the three win definitions
   of §12.4, the sample size, and the date range — so the comparison is honest rather than
   confirmatory.
4. A measured win rate materially below the claim is a **result**, not a bug, and must not trigger
   parameter fitting toward the claim.

### 12.6 Execution adapter (unimplemented)

```python
class ExecutionAdapter(Protocol):
    """NOT IMPLEMENTED. Live order execution is out of scope for this build."""
    def place_limit(self, plan_id: str, rung: EntryRung) -> str: ...
    def place_stop(self, plan_id: str, price: Decimal, qty: Decimal) -> str: ...
    def place_take_profit(self, plan_id: str, tp: TakeProfit) -> str: ...
    def amend_stop(self, order_id: str, new_price: Decimal) -> None: ...
    def cancel(self, order_id: str) -> None: ...
    def close_market(self, position_id: str, qty: Decimal) -> str: ...
    def account_equity(self, account: str) -> Decimal: ...
```

Two implementations exist: `BacktestAdapter` (the §12.1 simulator) and `NullAdapter`, which raises
`NotImplementedError` on every method. No exchange client is present in this build. **[OUR CHOICE]**

---

## 13. Disabled by default

Per CONFLICTS.md precedence rule 4 — "material he disowns ships disabled by default" — and the
rule-5 conservatism applied to unreliable or untested material.

| Module / feature | Config key to enable | Why it ships off | Source |
|---|---|---|---|
| Chart-pattern trading | `module_chart_patterns_enabled = true` | "Why am I sharing this with you if I don't trade it myself." Confluence-only even when enabled | CF-37, S8-C1, S4-R38 |
| Trend-line break / breakdown trading | `module_trendline_break_enabled = true` | Disowned for a stated mechanical reason (the manual-stop problem) | CF-37, S8-C1, S8 `[00:28:52]` |
| Scalping module | ~~`module_scalp_enabled = true`~~ **REVERSED by Q14** — now on, floored at `scalp_tf_floor = 30m`. "I suck at scalping" is a personal-fit statement (he finishes it *"and if you're good at scalping, then this is going to be heaven for you"*, S5 `[00:20:36]`), and he names the 2H as his own favourite scalp chart (S5 `[01:42:50]`). What he quit is 150-trades-a-day sub-15m day trading | CF-37, **Q14 `inferred`** |
| Fair value gaps | *(none — **not implemented**)* | Flatly refused | CF-37, S5 `[01:07:12]` |
| ICT / SMC | *(none — **not implemented**)* | Flatly refused; SMC-style 5–6 order ladders explicitly rejected | CF-37, S5-R? `[01:07:45]`, S6 `[01:01:51]` |
| DXY regime gate | `dxy_gate_enabled = true` | He says the correlation has been broken ~7 months and cannot explain it; a chart cannot be both second-most-important and unreliable | CF-35, S3-C8 |
| 0.886 fib level | `fib_886_enabled = true` | In his recommended list but explicitly **not back-tested by him** | CF-33, S6-A22 |
| SFP as a standalone strategy | `sfp_standalone_enabled = true` | He states the 20-trade survivability claim and then says "I highly suggest you do not do that" | CF-20, S7-C5 |
| Averaging up when the DCA never fills | `average_up_enabled = true` | Stated once, with no trigger condition; every other session's ladder is monotonic | CF-19, S3-A10 |
| Time-based stale exit | `stale_exit_enabled = true` | No bar count, time limit or adverse-excursion threshold exists anywhere | CF-30, S6-A17 |
| High-conviction 5–6% risk escalation | `high_conviction_loss_pct_enabled = true` | TBOT1's live divergence is a size modifier, not the taught default | CF-01, TBOT1-R13 |
| 200 EMA confluence | `ema200_confluence_enabled = true` | "I have no indicators on my chart whatsoever"; the 200 EMA is daily-only and "sometimes" | CF-36, S6 `[01:09:27]` |
| RSI standalone / RSI off | `rsi_divergence_mode = "standalone"` or `"off"` | Default is the confluence-only intersection of S8's disowning and TBOT1's routine use | CF-36 |
| Spot hedging | `hedge_enabled = true` | Taught (S4-R35) but a portfolio operation, not a signal. Default off is **[OUR CHOICE]** | S4-R35 |
| Account halve-and-restart | `equity_restart_mode = "halve_on_drawdown"` | Stated as personal discipline, not a mechanical rule. Default off is **[OUR CHOICE]** | S2-R26 |
| Chart inversion check | *(none — **not implemented**)* | A human visual aid with no machine analogue **[OUR CHOICE]** | S6-R47 |
| News override | *(none — **not implemented**)* | Discretionary and not encodable; only the scheduled-event calendar is machine-readable **[OUR CHOICE]** | TBOT1-A23 |
| BVOL box relocation | *(manual only — **not automated**)* | Purely discretionary; he says he will announce changes manually, which implies it is not meant to be automated | S3-R7, S3-A4 |
| **F1 nested zone geometry** (body core + outer wick band) | `zone_wick_band_enabled = true` | Rule-5 conservatism against a **single frame**, and pass 2 weakened it further: the two-box form appears in ~1 frame in 4, the one clear example (S6 52:38) was measured mid-drag, and the same drawing at 53:46 reads 0.33× instead of 0.83×. With the flag down behaviour is byte-identical to the single-box model | **F1**, S6 frames 52:38 / 53:46 / 54:22, S8 33:56, S8 1:28:33 |

**Important:** disabled trading modules still contribute to **confluence scoring**
(`disowned_modules_still_score_confluence = true`). A bull flag counts 0.5 toward a stack even when
the pattern module cannot open a trade (CF-37).

---

## 14. Open questions blocking full fidelity

The fifteen questions from CONFLICTS.md § *Unresolvable without the trader*, ranked by how much they
block implementation. Each is phrased so it can be sent to him verbatim. The **Currently** column
gives the default the bot runs until he answers.

> **STATUS — thirteen of the fifteen have been answered from the recordings.** The table below is
> kept as written for the audit trail; it is **superseded** by `CHANGELOG_EVIDENCE.md` and by the
> reversal notes now carried inside CONFLICTS.md, and several "Currently" cells are out of date by
> design. Q8 turned out to be a live defect rather than an open question — a *margin* percentage
> enforced as a *notional* ceiling, silently under-risking every leverage trade by roughly 5×.
>
> **Still genuinely open: Q6(a)** (the swing-detection candle count — no fractal width, lookback or
> N-bar rule exists anywhere in eight sessions) and **Q13** (2H / 4H / 8H / 12H — nothing is given
> for any of them, and his 1H→1D and 1D→2D slopes disagree by 3×, so they cannot be interpolated
> either). Both keep their placeholder values, both stay marked **[OUR CHOICE]**, and neither has
> been invented in the meantime.
>
> **A visual-evidence pass (`FRAME_FINDINGS.md`, F1–F5) then went after both from paused frames.**
> Neither closed, but both moved:
>
> * **Q6(a)** is now **bounded**: S7 frame 34:30 shows the 5th candle left of a marked 4H swing high
>   exceeding it, so the left-side width there is **≤4**. That rules out ≥5 *for that instance only*
>   — 2, 3 and 4 all stay admissible — and narrows the sweep from open to **2–4** (`swing_k`
>   `sweep_bracket`). The default stays 3 and stays **[OUR CHOICE]**.
> * **Q13** is **closed as a video question**: no percentage readout exists on any 2H/4H/8H/12H
>   chart, and the one candidate (8.10 % at S5 36:05) is measured over a hand-drawn illustration and
>   must not be used. A backtest sweep is the only remaining route.
>
> The same pass produced one **new** structural finding — F1, the nested body-box/wick-band zone
> geometry of §5.5 — which ships behind `zone_wick_band_enabled`, default off, on one frame.
>
> **A second frame pass (`FRAME_FINDINGS.md`, pass 2) then changed one default and weakened F1.**
>
> * **F6 — stop distance.** Three independent frames (TBOT1 4:11 BTCUSDT.P 1H, TBOT1 1:09:19
>   OMUSDT.P 1H, S8 1:28:33 SOLUSDT.P 4H) put the stop 0.48 / 0.49 / 0.58 **zone-heights** below
>   the box bottom, while the same three distances span 0.66–2.70 % of entry. The parameterisation
>   was wrong, not just the number: `stop_buffer_zone_fraction` (0.5, sweep 0.45–0.60) now places
>   any stop anchored to a zone, and `stop_buffer_atr` is demoted to the non-zone fallback (§8.5).
> * **F1 is weaker, not stronger.** The 0.83× band re-reads as 0.33× on the same drawing (S6
>   53:46, mid-drag); two other frames show a single box. The flag stays off and its ratio bracket
>   widens to 0.30–1.00.
> * **Q5 (`min_confluence_count`) gained two weak data points** — ONDO 1D with 5 objects at price,
>   BONK 12H with 2–3 at price — consistent with 3, nowhere near enough to move it.

| # | Question | Currently | Blocks |
|---|---|---|---|
| **Q1** | **Zone invalidation — 50% or 70–80%, and measured how?** You say a zone is dead once ~50% of it fills (S5/S6), but also that your order-block rule is "around 70 to 80%" of liquidity taken (S7), and elsewhere that a 50%-filled OB is still playable. Is it (a) 50% of zone depth, (b) 70–80% of zone depth, or (c) 50% for zones and 70–80% for single-candle order blocks? And is it breached by any **wick**, or does it need a **close** beyond? | `zone_fill_invalidation_pct = 50`, `zone_fill_measure = "wick_touch"` | Every zone/OB re-take decision |
| **Q2** | **Third-touch rule vs replaying a zone.** Don't take a level after its third touch, but you replay a demand zone until 50% fills and count seven bounces approvingly. Is the third-touch rule (a) only for bare S/R lines, (b) a size reduction, or (c) a hard veto everywhere? If a size reduction, what size at touches 3, 4 and 5? | Three object classes, three rules (CF-07); `touch_size_decay = [1.0,1.0,0.66,0.5,0.33]` | Trade count and sizing on every repeat level |
| **Q3** | **DCA size split.** Always "light at entry, heavier at the DCA", never a ratio. Two legs — 30/70, 25/75, something else? Three legs — 20/30/50? The blended average decides break-even, every TP-trail decision and the position size. | `[0.30, 0.70]` / `[0.20, 0.30, 0.50]` | Average entry ⇒ risk, R:R, break-even, trailing |
| **Q4** | **What fraction comes off at each TP?** The only split given is 50/50 and 40/30/30 (S4). Still current? And when TPs sit at whatever structural levels exist rather than a fixed two or three, how does the split adapt? | S4-R10 splits, extended to 4 and 5 legs by extrapolation | Realised expectancy on every trade |
| **Q5** | **Minimum confluence count, and how to count overlaps.** You refuse OB-only, fib-only, pattern-only, trendline-only and SFP-only trades but never give a number. Is three the floor? And when an SR point, a supply zone and an order block sit at one price, is that three confluences or one? | `min_confluence_count = 3.0`, weighted, deduplicated by class | The primary trade filter |
| **Q6** | **Swing high / swing low detection.** Every structure rule, SFP, fib anchor and order block depends on "a swing point" and "a directional change", neither ever defined. How many candles either side must a high be the highest of — 3? 5? And how big is a "directional change": a fixed %, an ATR multiple, or a break of the prior swing? | P1 fractal `swing_k = 3` on bodies; P2 `dir_change_atr = 2.0` | Every detector in §5 |
| **Q7** | **Which timeframe governs?** For a 1H trade: which timeframe reads trend and market structure, which confirms the MSB close, and which decides SFP validity? (The same sweep was a valid daily SFP and an invalid 12H SFP in S8.) | `structure_tf = trade_tf + 2`; SFP governed by the trade's own structure TF | Counter-trend classification, MSB, HTF veto |
| **Q8** | **Normal leverage position size.** S3 says 20% of portfolio, S7 says 10%, spot is 6–12%. For a leverage swing with a 4–5% max loss, what is the notional and what leverage gets you there? | Notional derived from the risk budget, clamped at 10% of equity | Notional exposure and leverage on every leverage trade |
| **Q9** | **Counter-trend: cancel it, or halve it?** S7 says you'd have cancelled a bullish setup once the trend flipped to lower highs; a minute later, half size against the trend is fine. Hard veto, or 0.5× with a 2–3% cap? And must a counter-trend trade always be demoted to a scalp on a lower timeframe? | `"size_down_and_demote"`, 0.5×, 2.0% cap, demote = true | Whether a whole class of trades exists |
| **Q10** | **Resting limits at the SR point vs waiting for the flip.** S4 says do not put a limit at the line waiting for the flip; everywhere else you say "I always enter at SR points and DCA lower". Is the difference that S4 means a level that hasn't flipped yet, and the SR-point entries are levels that already have? | Yes — two entry families (CF-16) | The bot's primary entry mechanism |
| **Q11** | **Where does the entry go after a structure break?** S7 says short the retest of the broken higher low; S8 says don't short the close, wait for the next lower high; S3 says wait for a lower high to form. Three ways of saying one thing, or three entries? And how many candles do you wait for that retest before abandoning the setup? | Detection ≠ action (CF-22); entry needs the retest; `msb_retest_timeout_bars = 20` | All post-MSB entries |
| **Q12** | **Mid-range as a band.** "No trades at mid-range" only works if mid-range has a width. How far either side — 10% of range height? 15%? And is mid-range the geometric 50% or the nearest S/R level to it? | `mid_range_band_pct = 15.0`; nearest high-touch level within ±10% of geometric 50% | A hard gate that blocks or permits entire sessions |
| **Q13** | **Sufficient gap for 2H, 4H, 8H and 12H** — and the day boundary. You gave numbers for 15m, 30m, 1H, daily and 2-day, not for the timeframes you actually trade most. What is the minimum move away on the 4H and the 12H? Separately: is your 5:00 PM daily close Pacific **daylight** time (00:00 UTC) or standard time (01:00 UTC)? | Interpolated 5/6/7/7.5%; `day_boundary_utc = "00:00"` | Zone validity on his primary timeframes; every "daily close" rule |
| **Q14** | **Are the pattern, trend-line and scalp modules meant to ship at all?** You taught a full pattern library (S4), a full trend-line breakdown method (S8) and a full scalping session (S8), and said in each case you don't trade them. Should the bot run those as live strategies, or use patterns only as extra confluence on your S/R and zone setups? | All three ship **disabled**; their objects still score confluence | Roughly half the taught material |
| **Q15** | **Golden pocket: 0.66 or 0.65 — and is "golden pocket" ever the 0.786?** S6 says 0.618–0.66 and notes others use 0.65. In S8 you use "golden pocket" and "0.786" interchangeably. Confirm: golden pocket = 0.618–0.66, entry level; 0.786 = separate, DCA level. And do you want 0.886 in the set given you said you hadn't back-tested it? | GP `[0.618, 0.66]`; 0.786 separate; `fib_886_enabled = false` | Entry and DCA prices on every fib-confluent setup |

### 14.1 Secondary unknowns already parameterised

These are not in the fifteen but are **OUR numbers** with no basis in the corpus, and should be
swept before any of them is treated as settled: `pending_sr_expiry_bars`, `msb_retest_timeout_bars`,
`reentry_max_attempts_per_level`, `reentry_cooldown_bars`, `reentry_window_bars`,
`sfp_min_bars_between`, `sfp_min_swing_separation_atr`, `sfp_max_close_distance_atr`,
`average_up_trigger_atr`, `dca2_min_zone_depth_atr`, `stop_buffer_atr` (now the non-zone fallback
only — the zone case is evidenced, see F6), `confluence_merge_atr`,
`range_min_height_atr`, `range_max_age_bars`, `new_listing_days`, `event_blackout_hours`,
`bias_level_min_confluence`, `bias_level_lookback_bars`, `stale_exit_bars`, `stale_exit_mae_atr`,
`dxy_gate_min_rolling_corr`, `min_daily_volume_usd`, plus every parameter of P1–P20 and every key
in §11.12.

`min_rr` **left this list at F9**: four frames of his own position-tool R:R readout (2.13, 2.97,
3.17, 5.00) put a floor of 2.0 under every trade observed, so it is now *derived with support*
rather than an invention. He still never states a number (TBOT1-A11), so it is not *his* either,
and it keeps a sweep bracket (2.0–2.5).

None of these may ever be described to the trader as his.
