# tbot/INTERFACES.md — the foundation contract

**Status: final for the foundation layer.** `tbot/config.py`, `tbot/models.py`,
`tbot/primitives.py` and `tbot/data.py` are built and tested (`python -m pytest`, 125 tests).
Detectors (SPEC.md §5), confluence (§6), qualification (§7), the plan builder (§8), the
management state machine (§9), the risk layer (§10) and the backtester (§12) are built **against
this document**. Everything below is prescriptive: if your module needs something that is not
here, ask for it to be added to the foundation rather than re-deriving it locally.

Read SPEC.md §2, §4 and §11 alongside this file — this file says *how the code expresses* those
sections, not what the rules are.

Contents: [1 Rules of engagement](#1-rules-of-engagement) · [2 Series](#2-the-series-contract) ·
[3 Models](#3-the-data-model) · [4 Config](#4-config) · [5 Primitives](#5-primitive-reference) ·
[6 Detector protocol](#6-the-detector-protocol) · [7 Config ownership](#7-config-key-ownership-by-module) ·
[8 Worked examples](#8-worked-examples) · [9 Invariants](#9-invariants-you-must-not-break)

---

## 1 Rules of engagement

1. **Import, never re-implement.** Every algorithm of SPEC.md §4 lives in `tbot.primitives`. If
   you find yourself writing a swing-detection loop, an ATR, a tolerance band, a fill
   measurement or a confluence sum inside a detector, stop: it already exists and the tests in
   `tests/test_primitives.py` are its contract.
2. **Purity.** Foundation functions are pure. Your module must not monkey-patch, mutate a
   `Config`, mutate a `Series`, or hold module-level mutable state. Determinism is a hard
   requirement (SPEC.md §12: identical inputs must produce identical plans).
3. **Prices are `Decimal`.** Convert once, at the boundary, with `tbot.models.dec`. Never build a
   `Decimal` straight from a raw float (`Decimal(0.1)` is not `Decimal("0.1")`); `dec` routes
   through `repr` so the value reads the way a human wrote it.
4. **Indices are positional.** Every `*_index` is a 0-based offset into the `Series` you were
   handed. Never a timestamp, never a pandas label, never an index into a different timeframe's
   series.
5. **No lookahead, ever.** A detector standing on bar `i` may read `series.head(i + 1)` and
   pivots with `confirmed_at_index <= i` only (`primitives.confirmed_swings`). SPEC.md §12.1
   makes this a harness-level assertion.
6. **Every emitted object carries `source_ids`.** See §6. A plan that cannot name the rule IDs
   behind it is a bug.
7. **`[OUR CHOICE]` markers stay.** If you copy a rule into a docstring, copy its marker with it.
   Nothing marked `[OUR CHOICE]` or "OUR number" may ever be presented as the trader's own rule.
8. **No network calls.** Anywhere. Live execution is out of scope (SPEC.md §1.9, §12.6).

Python: 3.11, `from __future__ import annotations` in every module, full type hints, `slots=True`
on every dataclass.

---

## 2 The `Series` contract

```python
from tbot.models import Series, Timeframe

class Series:
    def __init__(self, frame: pd.DataFrame, tf: Timeframe | str, symbol: str = "TEST",
                 venue_kind: Literal["spot", "perp"] = "spot", *,
                 validate: bool = True, copy: bool = True) -> None: ...

    @classmethod
    def from_arrays(cls, timestamps, open_, high, low, close, volume=None, quote_volume=None,
                    tf: Timeframe | str = Timeframe.H1, symbol: str = "TEST",
                    venue_kind: Literal["spot", "perp"] = "spot") -> Series: ...
```

**Guarantees you may rely on** (all enforced at construction; a violation raises `ValueError`):

| Guarantee | Detail |
|---|---|
| Columns | exactly `open, high, low, close, volume, quote_volume`, `float64`, in that order |
| Index | tz-aware **UTC** `DatetimeIndex` of **bar open times** |
| Ordering | strictly increasing, unique |
| Gaps | **allowed** — never assume a fixed step between rows; use `series.tf.minutes` for bar length, not index arithmetic |
| Closedness | every row is a closed bar (`Candle.is_closed is True`). Loaders drop the live partial bar; P1 forbids repainting |
| Bar sanity | `low <= min(open, close) <= max(open, close) <= high` for every row |
| Immutability | treat as read-only; `frame` is a defensive copy and derived arrays are cached and marked non-writeable |

**Accessors** (all `np.ndarray[float64]`, length `len(series)`, cached):
`open high low close volume quote_volume body_high body_low body_size upper_wick lower_wick
bar_range is_green` — plus `index` / `timestamps` (`DatetimeIndex`).

`body_high = max(open, close)`, `body_low = min(open, close)`, `is_green = close > open`
(a doji is **not** green — S6-R1/R2 colour mapping).

**Methods**

```python
len(series)                      # bar count
series.tf                        # Timeframe enum, e.g. Timeframe.H4
series.symbol, series.venue_kind # "SOLUSDT", "spot" | "perp"  (perp setups need perp candles, S6-R43)
series.slice(start, stop)        # -> Series, positional, [start, stop)
series.head(n)                   # -> Series, the "as of bar n-1" view: THE no-lookahead helper
series.candle(i)                 # -> Candle (Decimal prices)
series.candles()                 # -> Iterator[Candle]
series.timestamp(i)              # -> datetime (UTC)
series.price_at(i, "body_high")  # -> Decimal
```

One `Series` = one symbol on one timeframe. Multi-timeframe work holds a
`dict[Timeframe, Series]`; a `bar_index` from one timeframe is **meaningless** in another — map
through timestamps (`series.timestamp(i)`), never by arithmetic.

---

## 3 The data model

`tbot/models.py` implements SPEC.md §2 exactly. Frozen (immutable) records: `Candle`,
`SwingPoint`, `Fill`, `FibLevel`, `Box`. Mutable (state machines write to them): `Level`, `Zone`,
`OrderBlock`, `Setup`, `EntryRung`, `TakeProfit`, `TradePlan`, `Position`.

Enums — always use the enum, never the raw string, in new code (they are `str` subclasses, so
`Timeframe.H4 == "4H"` holds for serialisation):

| Enum | Members |
|---|---|
| `Timeframe` | `M15 M30 H1 H2 H4 H8 H12 D1 D2 D3 W1` (`.rank`, `.minutes`, `.pandas_freq`, `.step(n)`, `.parse()`) |
| `Direction` | `LONG SHORT` (`.sign` → ±1, `.opposite`) |
| `SwingKind` | `HIGH LOW` |
| `LevelKind` | `SUPPORT RESISTANCE SR_PENDING SR_CONFIRMED_SUPPORT SR_CONFIRMED_RESISTANCE RANGE_HIGH RANGE_LOW MID_RANGE TRENDLINE` |
| `FlipState` | `NONE PENDING CONFIRMED_SUPPORT CONFIRMED_RESISTANCE` (CF-15 machine) |
| `ZoneSide` / `ZoneClass` | `DEMAND SUPPLY` / `CONTINUATION REVERSAL` |
| `OBSide` | `BULLISH BEARISH` (bullish = last **red** candle before an up move, S6-R1/R2) |
| `TradeClass` | `SWING SCALP COUNTER_TREND PRICE_DISCOVERY` |
| `EntryFamily` | `RETEST FLIP_PENDING TRIGGER` (CF-16) |
| `Vehicle` / `Conviction` | `SPOT LEVERAGE` / `LOW NORMAL HIGH` |
| `PositionState` | `DRAFT ARMED PARTIAL OPEN MANAGING CLOSED EXPIRED CANCELLED` (§9.1) |
| `Account` | `LONG_TERM SPOT_SHORT LEVERAGE_SWING LEVERAGE_SCALP CHALLENGE` |
| `OrderType` / `FillKind` | `LIMIT MARKET` / `ENTRY DCA TP STOP EXIT` |
| `CloseReason` | `STOP TP_FINAL TRAIL_OUT STRUCTURAL_STALE TIME_STALE MSB_EXIT SPOT_FLIP MANUAL` |
| `Trend` | `UP DOWN NEUTRAL` (P11; `NEUTRAL` is **not** counter-trend) |
| `ConfluenceClass` | `SR_LEVEL ZONE ORDER_BLOCK RANGE_BOUNDARY FIB TRENDLINE PATTERN SFP RSI_DIVERGENCE EMA200 CME_GAP` — the keys of `config.confluence_weights` |

Helpers worth knowing:

* `dec(x) -> Decimal` — the only sanctioned float→Decimal conversion.
* `Box(top, bottom, start_index, end_index, included_upper_wick, included_lower_wick)` with
  `.height`, `.midpoint`, `.contains(price)` — the shared P5 box type. Zones and order blocks
  both come from it.
* `Zone.outer_edge` — `box_top` for demand, `box_bottom` for supply: the edge price reaches
  first, which is what P6 fill and P20 measure from.
* `Zone.body_stop_edge` — the mirror: `box_bottom` for demand, `box_top` for supply, the edge
  price reaches **last**. `plan.place_stop` measures the **F6** stop from it
  (`stop_buffer_zone_fraction × Zone.depth` beyond it).
* `TradePlan.rr_to_tp1` / `TradePlan.rr_to_final_tp` — both R:R figures, measured from
  `sizing_reference` (CF-18) against the stop. `plan.rr_for_gate(config, plan)` picks the one
  `rr_measured_to` names; since **F9** that is the **final** TP, because his position tool's R:R
  readout measures to its single target line. G14 is applied to that value, never to `rr_to_tp1`
  directly.
* `Level.price_at(bar_index)` — constant for horizontals, sloped for `TRENDLINE`.
* `SwingPoint.is_usable_at(bar_index)` — the P1 no-repaint guard.
* `Position.is_live` — `PARTIAL | OPEN | MANAGING`, i.e. what counts against §10 concurrency caps.
* `Setup.qualified` — `not self.vetoes`.

Field-by-field definitions are the SPEC.md §2 tables; the dataclasses match them name for name.

---

## 4 Config

```python
from tbot.config import Config, ConfigError, KEY_SPECS, KEY_SPEC_BY_NAME

cfg = Config.load()                     # all 247 SPEC.md §11 defaults
cfg = Config.load("configs/default.yaml")   # defaults deep-merged with a YAML file
cfg = cfg.with_overrides(swing_k=5, min_rr=2.5)   # validated copy — the sweep entry point
```

| Member | Signature | Notes |
|---|---|---|
| `Config.load` | `(path: str \| Path \| None = None, *, validate: bool = True) -> Config` | `None` → defaults. Unknown YAML keys are errors. |
| `Config.defaults_dict` | `() -> dict[str, Any]` | fresh `{key: default}` |
| `Config.with_overrides` | `(**overrides: Any) -> Config` | validated copy; **use this instead of mutating** |
| `Config.to_dict` | `() -> dict[str, Any]` | flat snapshot, containers copied |
| `Config.describe` | `() -> list[tuple[str, Any, Any, str]]` | `(key, value, default, source_id)` in §11 table order — the CLI provenance view |
| `Config.non_default_keys` | `() -> list[str]` | what a run actually changed |
| `Config.validate` | `() -> Config` | raises `ConfigError` with **every** problem |
| `write_default_yaml` | `(path) -> Path` | regenerates `configs/default.yaml`, one commented key per line |

`Config` is a **frozen, slotted dataclass with all 247 keys as flat attributes** — `cfg.swing_k`,
`cfg.zone_fill_invalidation_pct`, `cfg.sufficient_gap_pct_by_tf["4H"]`. There is no nesting and
no dict access: `cfg["swing_k"]` does not work, by design, so a typo is an `AttributeError` at
first touch rather than a silent `None`.

`ConfigError.problems` is the full list of problems; `str(err)` renders them under a count
header. Validation covers python type, enum membership, numeric bounds (from the §11 "Allowed"
column where it gives one, else the natural bound of the declared type), container shape
(split lists must sum to 1.0, bands must be ascending, `pipeline_order` must be a permutation of
the 18 §3.1 stages, `sufficient_gap_pct_by_tf` must cover the ladder) and the cross-key
invariants (`min_zone_depth_atr < max_zone_depth_atr`, `rsi_oversold < rsi_overbought`,
`tp_count_* >= tp_min_count`, allocations ≤ 100 %, …).

`KEY_SPECS` is the metadata table — `KeySpec(key, default, spec_type, py_type, members, minimum,
maximum, source_id, group, note)`. Use `KEY_SPEC_BY_NAME[k].source_id` whenever you need to print
or log why a number is what it is.

**Do not add keys** without transcript evidence. The 247 are the complete tunable surface (§11.13 + the 8 evidence-derived additions of CHANGELOG_EVIDENCE.md + the 3 frame-derived additions of FRAME_FINDINGS.md: F1 `zone_wick_band_enabled` / `zone_wick_band_max_ratio` from pass 1, F6 `stop_buffer_zone_fraction` from pass 2 + the 2 Discord-derived additions of CHANGELOG_EVIDENCE.md: `max_entry_distance_enabled` / `max_entry_distance_pct`). If a rule needs a number
that is not in the table, that is a spec gap: raise it, do not invent a local constant. If you
must hard-code an unavoidable engineering constant, mark it `[OUR CHOICE]` in the docstring and
flag it for the sweep list.

---

## 5 Primitive reference

Import as `import tbot.primitives as P`. Every signature below is **final**.

### Shared

```python
P.true_range(series: Series) -> np.ndarray
P.atr_array(series: Series, period: int) -> np.ndarray          # Wilder, no NaNs
P.atr_at(series: Series, config: Config, index: int | None = None) -> Decimal
```

`atr_at` defaults to the **last** bar. In a backtest, always pass the current bar index (or slice
the series with `head`) — an ATR read from the end of a full history is lookahead.

### P1 – P20

```python
# P1  swing points (S7-R11, S5-R44)
P.swing_points(series, config, *, k: int | None = None,
               source: Literal["body","wick"] | None = None) -> list[SwingPoint]
P.confirmed_swings(pivots: Sequence[SwingPoint], at_index: int) -> list[SwingPoint]

# P2  directional change / order-block trigger (S6-R1, S6-R2)
P.directional_change(series, config, j: int) -> DirectionalChange | None
P.find_directional_changes(series, config) -> list[DirectionalChange]
#   DirectionalChange(trigger_index, direction, extreme_index, extreme_price, move, move_atr,
#                     order_block_index)

# P3  level clustering (S4-R4)
P.cluster_levels(series, config, pivots: Sequence[SwingPoint], *,
                 now_index: int | None = None) -> list[LevelCluster]
#   LevelCluster(price, member_pivot_ids, bar_indices, high_members, low_members, radius)
#                .touch_seed == len(member_pivot_ids)

# P4  touch counting
P.count_touches(series, config, level_price: Decimal | float,
                side: Literal["support","resistance"], *,
                start_index: int = 0, end_index: int | None = None) -> TouchCount
#   TouchCount(count, history: tuple[(bar_index, close)], break_index, last_touch_index).broke

# P5  boxes (CF-13)
P.zone_box(series, config, start_index: int, end_index: int, *, source: str | None = None) -> Box
P.order_block_box(series, config, bar_index: int) -> Box

# P6  50 % fill (CF-08)
P.midpoint_of(box: Box) -> Decimal
P.measure_fill(series, config, box: Box, side: ZoneSide, *,
               from_index: int, to_index: int | None = None) -> ZoneFill
#   ZoneFill(fill_pct, is_dead, midpoint_hit, deepest_index, deepest_price, midpoint)

# P7  mid-range (CF-25, CF-26)   — note: no Series argument, it is pure geometry + levels
P.mid_range(config, range_high, range_low, levels: Sequence[Level] = ()) -> MidRange
P.in_no_trade_band(price, mid: MidRange) -> bool
#   MidRange(price, band_low, band_high, geometric_mid, source, level_id).contains(price)

# P8  range validity / staleness
P.check_range(series, config, upper, lower, *, start_index: int,
              end_index: int | None = None) -> RangeCheck
#   RangeCheck(valid, upper_touches, lower_touches, height, height_atr, bars,
#              body_close_beyond_index, last_touch_index, stale, reasons)

# P9  tolerance band
P.tolerance_band(series, config, level_price, at_index=None) -> tuple[Decimal, Decimal]
P.bar_at_level(series, config, level_price, bar_index: int) -> bool
P.price_at_level(series, config, price, level_price, at_index=None) -> bool

# P10 sufficient gap (CF-11)
P.sufficient_gap(series, config, breakout_index: int, direction: Direction, *,
                 box: Box | None = None, tf: Timeframe | str | None = None,
                 end_index: int | None = None) -> GapMeasure
#   GapMeasure(anchor, extreme, extreme_index, gap_pct, gap_atr, required_pct, required_atr,
#              valid, reasons)

# P11 trend
P.classify_trend(pivots: Sequence[SwingPoint], config, *, at_index: int | None = None) -> Trend

# P12 capitulation wick (TBOT1-C4 split: not a stop anchor, allowed as an entry target)
P.is_capitulation_wick(series, config, bar_index: int, side: Literal["upper","lower"]) -> bool
P.capitulation_wicks(series, config) -> list[tuple[int, str]]

# P13 horizontal consolidation
P.check_consolidation(series, config, start_index: int, end_index: int) -> ConsolidationCheck
P.is_horizontal_consolidation(series, config, start_index: int, end_index: int) -> bool
#   ConsolidationCheck(horizontal, bars, drift, drift_atr, height, height_atr, slope_per_bar,
#                      reasons)

# P14 confluence (CF-31, §6.2)
P.score_confluence(series, config, candidate_price, objects: Iterable[ConfluenceObject], *,
                   at_index: int | None = None, continuation_zone: bool = False) -> ConfluenceResult
#   ConfluenceObject(id, price, obj_class, weight=None, tf=None, source_ids=())
#   ConfluenceResult(score, classes, contributors, merged, qualified, bonus, unknown_classes,
#                    reasons)

# P15 OB liquidity taken (S7-R3 alternative fill rule)
P.ob_liquidity_taken_pct(series, config, box: Box, side: ZoneSide, *,
                         from_index: int, to_index: int | None = None) -> Decimal

# P16 sessions (CF-45)
P.day_start(ts: datetime, config) -> datetime
P.week_start(ts: datetime, config) -> datetime
P.is_weekend(ts: datetime, config) -> bool
P.same_session(a: datetime, b: datetime, config) -> bool

# P17 stale trade (off by default)
P.is_stale_trade(config, *, bars_in_trade: int, mfe_atr, mae_atr, tps_hit: int) -> bool

# P18 liquidity / barcoding screen (demote, never exclude)
P.liquidity_screen(series, config, *, median_quote_volume_usd: Decimal | float | None = None,
                   lookback_bars: int = 200) -> LiquidityScreen
#   LiquidityScreen(passes, tier: "A"|"B", wick_heavy, median_quote_volume_usd,
#                   median_wick_ratio, wicky_bar_fraction, reasons)

# P19 stop buffer (CF-14)
P.stop_buffer(series, config, at_index: int | None = None) -> Decimal
P.apply_stop_buffer(anchor_price, direction: Direction, buffer) -> Decimal

# P20 points of most touch (entry price inside a zone)
P.points_of_most_touch(series, config, box: Box, side: ZoneSide,
                       windows: Sequence[tuple[int, int]], *,
                       at_index: int | None = None) -> PMTResult
#   PMTResult(price, bin_width, bin_centres, counts, winning_bin)
```

Conventions that hold across all of them:

* `(start_index, end_index)` windows are **inclusive at both ends**.
* `from_index` in `measure_fill` / `ob_liquidity_taken_pct` is the creation bar and is
  **excluded** — formation bars cannot fill their own zone.
* `end_index=None` / `at_index=None` / `to_index=None` mean "the last bar of this series". In a
  bar-by-bar backtest, pass the current index explicitly or hand in `series.head(i + 1)`.
* Anything that can legitimately fail returns a result object with `valid` / `passes` /
  `horizontal` plus a `reasons: tuple[str, ...]` you should propagate into `Setup.vetoes`.
  `ValueError` means *you called it wrong* (inverted window, empty series, missing box).
* Negative indices are accepted and normalised (`-1` = last bar).

### `tbot.data`

```python
load_csv(path, tf: Timeframe | str, symbol: str = "UNKNOWN",
         venue_kind: Literal["spot","perp"] = "spot") -> Series
resample(series: Series, tf: Timeframe | str, config: Config | None = None) -> Series
synthetic(*, seed: int = 7, tf=Timeframe.H1, symbol: str = "SYNTH", base_price: float = 100.0,
          noise: float = 0.05, start: datetime | None = None) -> SyntheticSeries
#   SyntheticSeries(series, features: SyntheticFeatures)
```

`SyntheticFeatures` gives the exact bar indices of everything embedded: `range_start/end`,
`range_high/low`, `impulse_start/end`, `consolidation_start/end`, `breakout_index`,
`zone_top/bottom`, `order_block_index`, `ob_dir_change_index`, `sfp_index`, `sfp_swing_index`,
`sfp_swing_price`, `retest_index`, `total_bars`. Use it in **your** tests: your zone detector
should find the zone at `[consolidation_start, consolidation_end]`, your OB detector should find
`order_block_index`, your SFP detector should fire at `sfp_index` and nowhere else. Same `seed`
⇒ byte-identical bars; the structure is seed-independent and only the wick noise moves.

`resample` only goes **up** the ladder and cuts daily+ bars at `config.day_boundary_utc`.

---

## 6 The detector protocol

Every stage-3…stage-14 detector is a class implementing this protocol. Put it in
`tbot/detectors/<name>.py`.

```python
from typing import Protocol, Sequence, runtime_checkable

@runtime_checkable
class Detector(Protocol):
    """SPEC.md §5 detector. Pure: same (series, config) in, same objects out."""

    name: str                      # stable snake_case id, e.g. "supply_demand_zones"
    stage: int                     # SPEC.md §3.1 stage number (levels=3, zones=7, obs=8, ...)
    source_ids: tuple[str, ...]    # the rule IDs this detector implements, e.g. ("CF-10","S5-R15")
    produces: tuple[str, ...]      # ConfluenceClass values it can emit, e.g. ("zone",)

    def detect(self, series: Series, config: Config) -> list[Any]: ...
```

Rules:

1. `detect` returns model objects (`Level`, `Zone`, `OrderBlock`, `SwingPoint`, `FibLevel`,
   pattern/SFP records), **newest last**, ordered by the bar that completed them.
2. `detect(series, config)` sees only the bars it is given. To run bar-by-bar, the harness calls
   `detector.detect(series.head(i + 1), config)`; a detector must therefore never look at
   `series[-1]` expecting "now" to be anything other than the last bar it received.
3. **Source-rule reporting.** Two levels:
   * class level — `Detector.source_ids` names the rules the detector implements;
   * object level — every emitted object sets its own `source_ids: tuple[str, ...]` field with
     the specific rules that fired for *that* object (e.g. a rescued dead zone adds `"CF-08"`,
     `"S7-R4"`). All model dataclasses have this field, defaulting to `()`.
   The confluence layer copies object `source_ids` into `ConfluenceObject.source_ids`; the plan
   builder unions the contributors' ids into `TradePlan.source_ids`. That chain is how a plan
   explains itself, and the CLI prints it next to `Config.describe()`.
4. Objects that are *rejected* must not be returned. Where the rejection is interesting
   (a zone that failed the gap test), log it with the `reasons` tuple from the primitive that
   rejected it — do not invent your own wording.
5. Ids are deterministic and collision-free:
   `f"{symbol}:{tf.value}:{detector.name}:{completion_bar_index}"` (add `:{n}` when one bar
   produces several). Never use `uuid4`, never use `id()`, never use a running counter that
   depends on call order.
6. Detectors do **not** score, gate, size, or place anything. They emit objects. Scoring is
   `confluence.py` (P14), gating is `qualification.py` (§7), sizing is `risk.py` (§10).
7. Confluence adapter: expose

   ```python
   def to_confluence(self, objects: Sequence[Any], config: Config) -> list[P.ConfluenceObject]: ...
   ```

   mapping your objects to the price they should score at (a zone scores at its
   `entry_price_pmt`, a level at `price`, an OB at its `midpoint`) with `obj_class` set to one of
   your declared `produces` values. Objects from modules that ship disabled still score
   (`disowned_modules_still_score_confluence = true`, CF-37) — the module switch controls trade
   generation, not scoring.

Pipeline order is `config.pipeline_order` (18 stages, SPEC.md §3.1). `pipeline.py` owns the
ordering; a detector must never call another detector.

---

## 7 Config key ownership by module

Every one of the 247 keys is owned by exactly one module below — **the owner is the only module
that reads it directly**; everyone else receives the derived value as an argument. Before adding
any parameter, search this table: it probably exists already.

Foundation keys (`atr_period`, `pmt_bin_atr`, `day_boundary_utc`) are read by the primitives on
your behalf — pass `config` through, do not re-derive.

### `detectors/levels.py — §5.1 support/resistance + §5.2 SR flip machine`

| Key | Default | Source |
|---|---|---|
| `flip_confirm_candles` | `2` | CF-15; S5-R3, S2-R1/R2/R3 |
| `flip_extra_candle_below_tf` | `"4H"` | CF-15; Q10 stated, S2 `[00:26:30]` (was inferred) |
| `flip_requires_body_close` | `True` | CF-15; S4-R5, S8-R41 |
| `level_cluster_atr` | `0.25` | P3 — [OUR CHOICE]; S4-A2 |
| `level_lookback_bars` | `500` | P3 — [OUR CHOICE]; S2-A3 |
| `level_min_touches` | `2` | P3; S4-R4, S7 `[00:05:04]` |
| `level_tolerance_atr` | `0.15` | P4/P9 — [OUR CHOICE]; S2-A2, S3-A8 |
| `line_touch_hard_limit` | `3` | CF-07; Q2 derived, S5 `[00:24:35]` `[00:25:40]` — touches 1-3 play, the 4th is vetoed |
| `pending_sr_expiry_bars` | `60` | CF-15 — OUR number; S2-A15 |
| `range_boundary_touch_limit` | `6` | CF-07; Q2 stated, S4 `[00:44:55]` ("five touches, I'm going to keep taking this trade") |
| `touch_reset_atr` | `0.5` | P4 — [OUR CHOICE]; TBOT1-A6 |
| `zone_touch_uses_fill_rule_not_count` | `True` | CF-07; Q2 derived, S6 `[00:52:38]` (same zone played three times, stopped by the fill line) |

### `detectors/trendlines.py — §5.3 (ships disabled)`

Owns no configuration keys of its own; it reads `level_tolerance_atr`, `touch_reset_atr` and `swing_k` through the primitives, and its module switch `module_trendline_break_enabled` is owned by `pipeline.py`.

### `detectors/ranges.py — §5.4 ranges and mid-range`

| Key | Default | Source |
|---|---|---|
| `mid_range_band_pct` | `15.0` | CF-25 — OUR number; S4-A3, S8-A14 |
| `mid_range_limits_from_extremes_enabled` | `True` | CF-25; Q12 stated, S4 `[00:34:02]` ("if price is up here, then yes, you're going to set limits at mid-range") |
| `mid_range_requires_intermediate_stop` | `True` | CF-25; S5-R13 |
| `mid_range_search_pct` | `10.0` | CF-26, P7; Q12 stated, S4 `[00:17:53]` ("it will usually align with support and resistance") |
| `monday_range_source_tf` | `"1D"` | CF-45; S5-R8, S5-R9 |
| `range_death_mode` | `"close_beyond_plus_flip"` | CF-26; S4-A16 |
| `range_max_age_bars` | `300` | CF-26, P8 — OUR number |
| `range_min_bars` | `20` | P8 — [OUR CHOICE] |
| `range_min_height_atr` | `3.0` | CF-26, P8 — OUR number; S4-A15 |
| `range_stale_bars` | `60` | P8 — [OUR CHOICE] |

### `detectors/zones.py — §5.5 supply/demand zones`

| Key | Default | Source |
|---|---|---|
| `consolidation_max_drift_atr` | `0.75` | P13 — [OUR CHOICE]; S5-A5, S6-A27 |
| `consolidation_max_height_atr` | `2.0` | P13 — [OUR CHOICE] |
| `consolidation_min_bars` | `2` | P13; S5-R17 |
| `dead_zone_htf_support_rescue` | `True` | CF-08; Q1 stated, S7 `[00:08:22]` (a fully-taken OB is playable on an independent HTF support) |
| `dead_zone_rescue_max_touches` | `3` | CF-08; S7-R4 |
| `max_zone_depth_atr` | `3.0` | CF-12; S8-R23 — normalisation is OURS |
| `min_zone_bodies` | `2` | CF-12; S5-R17 |
| `min_zone_depth_atr` | `0.5` | CF-12; S6-R48, S7-R6 — normalisation is OURS |
| `sufficient_gap_anchor` | `"breakout_close_to_extreme"` | P10; S5-A1 — [OUR CHOICE] |
| `sufficient_gap_atr_mult` | `2.0` | CF-11 — OUR number |
| `sufficient_gap_pct_by_tf` | `{'15m': 3.0, '30m': 4.0, '1H': 4.0, '2H': ...` | CF-11; Q13 stated rows 15m/30m/1H/1D/2D (S5 `[00:36:38]` `[00:54:07]` `[00:35:30]` `[00:36:05]` `[01:17:59]`); 2H/4H/8H/12H/3D+ [OUR CHOICE] |
| `sufficient_gap_require_both_tests` | `True` | CF-11 |
| `sufficient_gap_retrace_cutoff` | `0.5` | P10 — [OUR CHOICE] |
| `wick_include_max_atr` | `0.5` | CF-13, P5 — OUR number |
| `wick_include_max_pct` | `2.0` | CF-13, P5; S7-R7 |
| `zone_box_source` | `"body_plus_small_wick"` | CF-13; S5-R17, S5-R19, S6-R9 |
| `zone_direction_mode` | `"both"` | CF-10; S5-R15, S6-R4/R5, S6-A26 |
| `zone_fill_invalidation_pct` | `50.0` | CF-08; Q1 stated, S5 `[00:38:52]` `[00:41:10]` — multi-candle zones ONLY |
| `zone_fill_measure` | `"wick_touch"` | CF-08, P6; Q1 inferred (he says "pierced through", S5 `[01:23:02]`; never "wick"/"close") |
| `zone_fill_reference` | `"as_originally_drawn"` | CF-08, P6; S5-A11 |
| `zone_within_zone_policy` | `"larger_if_within_max_depth"` | CF-12; S5-R30 |
| `zone_wick_band_enabled` | `False` | **F1** — FRAME_FINDINGS.md F1, S6 frame 52:38; single-frame observation, needs corroboration. Off = byte-identical to the single-box model |
| `zone_wick_band_max_ratio` | `1.0` | **F1** — same frame; measured example 83%. sweep_bracket 0.83-1.0 |

### `detectors/orderblocks.py — §5.6 order blocks`

| Key | Default | Source |
|---|---|---|
| `dir_change_atr` | `2.0` | P2 — [OUR CHOICE]; S6-A1 |
| `dir_change_max_bars` | `10` | P2 — [OUR CHOICE] |
| `dir_change_uses_sufficient_gap_table` | `True` | P2; Q6 inferred, S5 `[00:54:07]` `[00:36:05]` `[00:35:30]` |
| `ob_box_source` | `"body_with_small_wick"` | CF-09, P5; S6-R9 |
| `ob_fill_invalidation_pct` | `75.0` | CF-08, P15; Q1 stated, S7 `[00:07:14]`-`[00:08:54]` ("my rule for order blocks are like around 70 80%") |
| `ob_inside_zone_precedence` | `"zone_wins"` | CF-09; Q5 stated, S6 `[01:07:32]` ("demand zone over the order block") |
| `ob_liquidity_measure` | `"deepest_wick_through_body_range"` | P15; S7-A2 — measure is [OUR CHOICE], the threshold it feeds is stated (ob_fill_invalidation_pct) |
| `ob_max_candles` | `1` | CF-09; S6-R3 |

### `detectors/structure.py — §5.7 swings, trend, MSB, bias level`

| Key | Default | Source |
|---|---|---|
| `bias_level_enabled` | `True` | CF-23 (spot/long-term only); S8-C2 |
| `bias_level_lookback_bars` | `200` | CF-23 — OUR number |
| `bias_level_min_confluence` | `2.0` | CF-23 — OUR number |
| `higher_low_selection` | `"technical"` | CF-23; S7-R12, S8-C2 |
| `htf_veto_enabled` | `True` | CF-24; Q7 stated, S8 `[00:38:57]` `[00:41:12]` (was inferred) |
| `htf_veto_timeframe` | `"1D"` | CF-24; Q7 stated, S8 `[00:41:12]` ("the daily super bearish") |
| `msb_deviation_invalidates` | `True` | CF-22; Q11 derived, S2 `[00:25:56]` |
| `msb_entry_requires_retest` | `True` | CF-22; Q11 stated x4, S7 `[00:26:59]` `[00:28:40]`, S8 `[00:25:58]` `[01:17:19]` |
| `msb_exit_mode` | `"break_only"` | CF-22; S7-R12, S3-R21, S2-R28 |
| `msb_price_source` | `"body_close"` | CF-22; Q7 stated x4, S7 `[00:18:50]` `[01:11:53]`, S5 `[01:25:16]` |
| `msb_retest_timeout_bars` | `20` | CF-22 — OUR number; S7-A20 |
| `structure_tf_offset` | `2` | CF-24 — OUR construct; S7-A8, S7-A9 |
| `swing_k` | `3` | P1 — [OUR CHOICE]; S7-A7 |
| `swing_price_source` | `"body"` | P1; Q6 stated, S7 `[00:18:50]` `[01:10:48]` `[01:11:53]`, S5 `[01:25:16]` (was [OUR CHOICE]) |
| `trend_pivot_count` | `4` | P11 — [OUR CHOICE] |
| `trend_timeframe` | `"structure_tf"` | P11; CF-24 |

### `detectors/sfp.py — §5.8 swing failure patterns`

| Key | Default | Source |
|---|---|---|
| `sfp_entry_price` | `"confirming_close"` | CF-20; S7-R21, S8-R5, S7-C6 |
| `sfp_governing_timeframe` | `"highest_valid"` | CF-20; Q7 inferred, S8 `[00:23:06]` `[00:16:46]`, S7 `[01:24:22]` `[01:26:03]` |
| `sfp_max_close_distance_atr` | `1.5` | CF-20 — OUR number; S5-R7 |
| `sfp_min_bars_between` | `3` | CF-20; Q6 floor stated at 2, S7 `[01:19:52]` ("candles cannot be next to each other"); the value 3 is OURS |
| `sfp_min_swing_separation_atr` | `1.0` | CF-20 — OUR number; S7-R28, S8-R4 |
| `sfp_raid_price_source` | `"wick"` | CF-20, P1; Q6 stated, S7 `[01:14:44]` |
| `sfp_standalone_enabled` | `False` | CF-20; S7-R30, S7-C5 |
| `sfp_trend_veto` | `True` | CF-20; S7-R31 |

### `detectors/fibs.py — §5.9 fibonacci`

| Key | Default | Source |
|---|---|---|
| `fib_886_enabled` | `False` | CF-33; Q15 stated, S6 `[01:38:53]` ("I just haven't back tested it") — excluded by his own arithmetic |
| `fib_anchor_selection` | `"most_recent_qualifying_swing_pair"` | CF-34 — [OUR CHOICE]; S6-A16, TBOT1-A2 |
| `fib_dca_level` | `0.786` | CF-33; Q15 stated, S6 `[01:56:54]` ("the 786 fib is usually my DCA point") |
| `fib_draw_convention` | `"s6"` | CF-34; S6-R34, S6-R35, S6-C6, S7-R1 |
| `fib_entry_level` | `[0.618, 0.66]` | CF-33; TBOT1-R5 |
| `fib_levels_active` | `[0.618, 0.66, 0.786]` | CF-33; Q15 stated, S6 `[01:41:14]`-`[01:41:52]` ("I use the three middle ones" of 886/786/66/618/236) |
| `fib_loses_ties_to_sr` | `True` | CF-32; S6-R38 |
| `golden_pocket_band` | `[0.618, 0.66]` | CF-33; Q15 stated, S6 `[01:26:22]` `[01:40:01]` — 0.66 is his, 0.65 is other people's and lies inside the band |

### `detectors/patterns.py — §5.10 chart patterns (ships disabled)`

| Key | Default | Source |
|---|---|---|
| `cup_handle_floor_pct` | `45.0` | S4-R24, S4-A9 — midpoint is [OUR CHOICE] |
| `pattern_pole_anchor` | `"most_recent_impulse"` | S4-R17, S4-C6 — [OUR CHOICE] |

### `detectors/indicators.py — §3.1 stage 14, CF-36`

| Key | Default | Source |
|---|---|---|
| `ema200_confluence_enabled` | `False` | CF-36; S6 `[01:09:27]` |
| `rsi_divergence_mode` | `"confluence_only"` | CF-36; S8-C3 |
| `rsi_overbought` | `70` | CF-36; S8-R40, S8-C4 |
| `rsi_oversold` | `30` | CF-36; S8-R40, S8-C4 |
| `rsi_period` | `14` | CF-36 — OURS; S8-A19 |
| `rsi_timeframe` | `"structure_tf"` | CF-36 — OURS; S8-A19 |

### `confluence.py — §6 scoring, dedup, conviction`

| Key | Default | Source |
|---|---|---|
| `confluence_dedup_same_class` | `True` | CF-31, P14 |
| `confluence_gate_mode` | `"raw_count"` | CF-31; Q5 derived, S5 `[01:05:33]`, S8 `[00:53:41]` |
| `confluence_merge_atr` | `0.25` | CF-31, P14 — OUR number; TBOT1-A4 |
| `confluence_weights` | `{'sr_level': 1.5, 'zone': 1.25, 'order_blo...` | CF-31 — weights are OURS; S6-A15. Q5: ranking + conviction only, never the entry gate |
| `high_conviction_score` | `4.0` | §6.3 — [OUR CHOICE]; S6 `[01:35:26]` |
| `min_confluence_count` | `3.0` | CF-31; Q5 derived, S5 `[01:43:55]` `[01:05:33]`, S8 `[00:53:41]` — RAW object count, not a weighted score |
| `single_class_trade_forbidden` | `True` | CF-31; Q5 stated, S6 `[00:45:16]` ("I don't take trades based off OBS alone. I need confluence") |
| `zone_continuation_confluence_bonus` | `1.0` | CF-10 — OUR number |

### `pipeline.py — §3 stage ordering and module switches`

| Key | Default | Source |
|---|---|---|
| `disowned_modules_still_score_confluence` | `True` | CF-37; Q14 stated, S4 `[01:48:29]`, S6 `[01:56:54]` |
| `max_entry_distance_enabled` | `False` | [OUR CHOICE] — DISCORD CHECK 2026-09-15; off until a sweep says otherwise |
| `max_entry_distance_pct` | `15.0` | [OUR CHOICE] — range bounded by DISCORD CHECK 2026-09-15, value never stated |
| `module_chart_patterns_enabled` | `False` | CF-37; Q14 stated, S4-R38 / S4 `[01:48:29]` — "never on a pattern alone", not a disavowal |
| `module_scalp_enabled` | `True` | CF-37; Q14 inferred (REVERSES CF-37), S5 `[01:41:45]` `[01:42:50]`, S8 `[00:44:49]` |
| `module_trendline_break_enabled` | `False` | CF-37; Q14 stated, S8 `[00:28:52]` `[00:30:37]` — the objection is operational (no hard stop) |
| `pipeline_order` | `['universe_calendar_gate', 'load_align_can...` | CF-32; S6-R28, S6-C2 |
| `sfp_evaluated_last` | `True` | CF-32; S7-R30 |

### `qualification.py — §7 gate stack, regime, universe, calendar, shorting`

| Key | Default | Source |
|---|---|---|
| `all_pairs_at_resistance_veto` | `True` | CF-35; TBOT1-R20 |
| `bvol_event_window_hours` | `72` | CF-35; S3-R1, S3-C2 |
| `bvol_size_multiplier` | `0.5` | CF-35; S3-R5 |
| `bvol_zone` | `[0.81, 1.4]` | CF-35; S3-R7 |
| `context_priority` | `['USDT.D', 'BTC.D', 'BVOL']` | CF-35; S3-R11 |
| `counter_trend_demote_to_scalp` | `True` | CF-03; Q9 stated, S7 `[00:25:12]` `[00:26:26]` ("these will be scalp plays") |
| `counter_trend_mode` | `"size_down_and_demote"` | CF-03; Q9 stated, S7 `[00:19:28]` `[00:25:12]` — "veto" struck (it mis-read a pending-order rule, S7 `[00:17:06]`) |
| `counter_trend_size_multiplier` | `0.5` | CF-03; Q9 stated, S7 `[00:20:00]` ("use half of your usual amount"); S3-R25, S8-R1 |
| `dxy_gate_enabled` | `False` | CF-35; S3-C8, S3-A21 |
| `dxy_gate_min_rolling_corr` | `0.4` | CF-35 — OUR construct |
| `event_blackout_hours` | `24` | CF-39 — OUR number |
| `event_blackout_mode` | `"leverage_only"` | CF-39; S8-R2 |
| `event_resume_requires_range` | `True` | CF-39; S2-R27 |
| `event_tf_step_up` | `1` | CF-39; S5-R36 |
| `leverage_max_mcap_rank` | `100` | CF-40; S2 §2 (large/mid boundary) |
| `max_median_wick_ratio` | `0.55` | P18 — [OUR CHOICE]; S2-R35, S2-A20 |
| `max_wicky_bar_fraction` | `0.4` | P18 — [OUR CHOICE]; S7-A24 |
| `memecoin_vehicle` | `"spot_only"` | CF-40; S6-R45, S7-R38 |
| `min_daily_volume_usd` | `50000000` | CF-40, P18 — floor is OURS; S8-R31 |
| `min_expected_move_pct` | `{'scalp': 2.0, 'swing': 5.0}` | CF-41; S3-R15, S6-R8, S8 `[00:47:58]` |
| `min_rr` | `2.0` | CF-42 — OUR number, corroborated as a floor by **F9** (4 frames, 2.13–5.00); S3-R26 (1:1 rejected); sweep 2.0–2.5 |
| `net_short_allowed_in_uptrend` | `False` | CF-41; S4-R36 |
| `new_listing_days` | `30` | CF-40 — OUR number; S6-R44 |
| `rr_measured_from` | `"average_entry"` | CF-42; CF-18 |
| `rr_measured_to` | `"final_tp"` | CF-42; **F9** — his position tool measures R:R to its single target line (TBOT1 4:11 / 22:59 / 1:09:19, S8 1:28:33). Was `"tp1"`. |
| `scalp_excludes_btc` | `True` | CF-40; S8-R32 |
| `scalp_tf_ceiling` | `"2H"` | CF-38; Q14 stated, S5-R34 / S5 `[01:41:45]` ("I prefer a 2 hour than a 30 minute 100% of the time") |
| `scalp_tf_floor` | `"30m"` | CF-38; Q14 stated, S5-R34 / S5 `[01:41:45]`; S8 `[01:34:48]` on low-timeframe unreliability |
| `short_in_price_discovery` | `False` | CF-41; S3-R28, S6-R37 |
| `shorts_enabled` | `True` | CF-41; S7-C9 |
| `swing_tf_floor` | `"4H"` | CF-38; S5-R34, S6 `[00:57:15]` |
| `universe_max_symbols` | `3` | CF-40; S8-R33 |
| `weekend_mode` | `"leverage_blocked"` | CF-39; TBOT1-R24, TBOT1-C8 |

### `planner.py — §8 trade-plan construction (entries -> stop -> TPs)`

| Key | Default | Source |
|---|---|---|
| `allow_market_orders` | `"trigger_family_only"` | CF-16; Q10 stated, S4 `[02:03:04]` ("I never market into anything. So I always set limits") |
| `capitulation_volume_mult` | `2.0` | P12 — [OUR CHOICE] |
| `capitulation_wick_atr` | `3.0` | P12 — [OUR CHOICE]; TBOT1-A15, S8-A17 |
| `capitulation_wick_body_ratio` | `3.0` | P12 — [OUR CHOICE] |
| `dca2_min_zone_depth_atr` | `1.5` | CF-17 — OUR number; S5-R22 |
| `dca_count_breakdown` | `0` | CF-17; S8-R11 |
| `dca_count_default` | `1` | CF-17; S6-R16 |
| `dca_count_max` | `2` | CF-17; S2-R9, S6 `[01:01:51]` |
| `dca_count_scalp_max` | `1` | CF-17; S8-R17 |
| `dca_size_split_2` | `[0.39, 0.61]` | CF-18; Q3 derived, S6 `[00:48:10]` — 35:55 of his own LINK ladder (avg 17.6332 reproduces exactly) |
| `dca_size_split_3` | `[0.2, 0.3, 0.5]` | CF-18; Q3 derived, S6 `[00:38:49]`-`[00:40:05]` — 35:55:100 = 18.4/29.0/52.6, avg 17.9215 exact |
| `dca_size_split_wick_heavy_2` | `[0.25, 0.75]` | CF-18; Q3 stated, S6 `[01:54:34]` ("very light there, like 20 to 30%") |
| `duplicate_stop_offset_bps` | `1.5` | CF-05; S4-R34 |
| `entry_family_flip_pending_enabled` | `True` | CF-16; Q10 stated, S4 `[00:55:38]` ("you're not going to place limit orders at the SR line") |
| `entry_family_retest_enabled` | `True` | CF-16; Q10 stated, S3 `[01:54:12]` (an SR point is by definition already flipped) |
| `entry_family_trigger_enabled` | `True` | CF-16; CF-20, CF-22 |
| `leverage_downgrade_max_multiple` | `3.0` | CF-06 ("low leverage" unquantified, TBOT1-A7) — [OUR CHOICE] |
| `max_stop_pct_leverage` | `9.0` | CF-06; S7-R7, S6 `[00:08:04]` |
| `min_stop_pct` | `0.5` | CF-06; S7-C8 |
| `presr_light_limit_enabled` | `False` | CF-16; Q10 stated-as-inferior, S2 `[00:27:08]`-`[00:27:41]` |
| `size_and_stop_computed_from` | `"average_entry"` | CF-18; Q3 stated, S6 `[00:40:40]` ("18.456 minus our average entry") |
| `spot_exit_mode` | `"close_below_level_then_flip"` | CF-05; S8-R36, TBOT1-R18 |
| `spot_invalidation_timeframe` | `"1D"` | CF-05; TBOT1-R18 |
| `spot_synthetic_stop_for_sizing` | `True` | CF-05 — our construct |
| `stop_buffer_atr` | `0.15` | CF-14, P19 — OUR number; S2-A8, TBOT1-A14 — **fallback**, for stops not anchored to a zone |
| `stop_buffer_zone_fraction` | `0.5` | **F6** — FRAME_FINDINGS.md pass 2; TBOT1 4:11, TBOT1 1:09:19, S8 1:28:33 (three frames, 0.48/0.49/0.58); sweep 0.45–0.60 |
| `stop_never_beyond_opposing_level` | `True` | CF-14; S5-R25, S6-R19 |
| `stop_tighten_tf_steps` | `2` | CF-06; S4-R16, S8 `[01:21:46]` |
| `stop_wick_max_pct` | `3.0` | CF-14; S6-R18 |
| `tp_count_price_discovery_max` | `5` | CF-27; S6-R36 |
| `tp_count_scalp` | `3` | CF-27; S8-R19, TBOT1-R17 |
| `tp_count_swing` | `2` | CF-27; S4-R1/R2, S6-R20 |
| `tp_min_count` | `2` | CF-27; S5-R26 |
| `tp_split_2` | `[0.5, 0.5]` | CF-28; Q4 stated, S4 `[00:17:53]` `[00:18:27]` ("if it's two TPS, then I do 50/50") |
| `tp_split_3` | `[0.4, 0.3, 0.3]` | CF-28; Q4 stated, S4 `[00:18:27]` ("if it's three TPS, I have 40 30 30") |
| `tp_split_4` | `[0.4, 0.25, 0.2, 0.15]` | CF-28 — OURS |
| `tp_split_5` | `[0.35, 0.25, 0.2, 0.12, 0.08]` | CF-28 — OURS |
| `wide_stop_policy` | `"tighten_then_downgrade_then_skip"` | CF-06; S4-R16, S5-R24, TBOT1-R7 |

### `manager.py — §9 trade-management state machine`

| Key | Default | Source |
|---|---|---|
| `average_up_enabled` | `False` | CF-19; S3-R13, S3-A10 |
| `average_up_only_at_sr_point` | `True` | CF-19; S3-R14 |
| `average_up_trigger_atr` | `2.0` | CF-19 — OUR number |
| `break_even_reference` | `"average_entry"` | CF-29; CF-18 |
| `reaction_threshold_atr` | `0.75` | P17 — [OUR CHOICE] |
| `reentry_cooldown_bars` | `3` | CF-21 — OUR number |
| `reentry_max_attempts_per_level` | `2` | CF-21 — OUR number; S8-A20 |
| `reentry_stacked_conditionals_enabled` | `True` | CF-21; TBOT1-R26 |
| `reentry_trigger` | `"sfp_or_close_reclaim"` | CF-21; S2-R13, S6-R24 |
| `reentry_window_bars` | `100` | CF-21 — OUR number |
| `stale_exit_bars` | `8` | CF-30, P17 — OUR number |
| `stale_exit_enabled` | `False` | CF-30; S6-A17 |
| `stale_exit_mae_atr` | `1.0` | CF-30, P17 — OUR number |
| `structural_stale_exit_enabled` | `True` | CF-30; S6-R22, S6-R23, S7-R39, S8-R9 |
| `tp_residual_policy` | `"trail_out"` | CF-28; Q4 stated, S5 `[00:40:00]` (he accepts being trailed out) |
| `trail_on_tp1` | `"break_even"` | CF-29; S4-R11, S5-R27 |
| `trail_on_tp2` | `"tp1_price"` | CF-29; S4-R11, S5-R27 |

### `risk.py — §10 risk, portfolio, accounts, challenge`

| Key | Default | Source |
|---|---|---|
| `account_scoped_cut_rules` | `True` | CF-43; S2-C6, S2 `[00:53:58]` |
| `alloc_cash_min_pct` | `20.0` | S2-R17, S2-C5 |
| `alloc_futures_pct` | `10.0` | S2-R16 |
| `alloc_large_cap_pct` | `35.0` | S2-R16 |
| `alloc_micro_cap_pct` | `3.0` | S2-R16 |
| `alloc_mid_cap_pct` | `15.0` | S2-R16 |
| `alloc_small_cap_pct` | `5.0` | S2-R16 |
| `challenge_cadence` | `"weekly"` | CF-44; S2-R33 |
| `challenge_goal_pct` | `8.0` | CF-44; S2-C7 |
| `challenge_stop_on_goal` | `True` | CF-44; S2-R22 |
| `daily_loss_count_limit` | `2` | CF-44; S2-R21 |
| `default_leverage` | `10.0` | CF-02; Q8 stated, S2 `[01:52:12]` ("I always do 10x") |
| `equity_restart_mode` | `"off"` | S2-R26 — default is [OUR CHOICE] |
| `hedge_enabled` | `False` | S4-R35 — default is [OUR CHOICE] |
| `hedge_max_leverage` | `3.0` | S4-R35 |
| `hedge_size_ratio` | `1.0` | S4-R35 |
| `high_conviction_loss_pct_enabled` | `False` | CF-01; TBOT1-R13 |
| `long_term_derisk_multiple` | `{'full': 3.0, 'partial': 2.0}` | CF-43; S2-R18 |
| `long_term_exit_mode` | `"macro_msb_two_step"` | CF-43; S3-R21, S7-R36 |
| `long_term_max_large_caps` | `5` | S2-R19 |
| `long_term_max_mid_caps` | `4` | S2-R19 |
| `loss_definition` | `"closed_below_average_entry_net_fees"` | CF-44; S2-A23 |
| `margin_pct_leverage` | `10.0` | CF-02; Q8 stated, S7 `[00:25:54]` `[00:20:33]` |
| `max_concurrent_leverage_global` | `4` | CF-04; S4-C8 |
| `max_concurrent_leverage_scalp` | `2` | CF-04; S4-R30 |
| `max_concurrent_leverage_swing` | `2` | CF-04; S4-R30, S2-R32 |
| `max_concurrent_spot` | `5` | CF-04; S4-R31 |
| `max_loss_pct_counter_trend` | `2.0` | CF-01; Q9 stated 2-3% band, S7 `[00:20:00]`; = counter_trend_size_multiplier x max_loss_pct_swing |
| `max_loss_pct_low_conviction` | `1.5` | CF-01; S6-R26 |
| `max_loss_pct_scalp` | `2.5` | CF-01; S2-R20, S3-R24 |
| `max_loss_pct_swing` | `4.0` | CF-01; S2-R20, S3-R24, S5-R32, S6-R11, S7-R8 |
| `max_loss_pct_swing_hard_cap` | `5.0` | CF-01; S6-R11, TBOT1-R13 |
| `max_notional_pct_leverage` | `100.0` | CF-02; Q8 derived, S6 `[00:08:36]`-`[00:11:27]` (was S7-R8, a MARGIN figure) |
| `max_total_spot_deployment_pct` | `70.0` | CF-02; S4-R31, S8-R35 |
| `risk_ratchet_up_allowed` | `False` | CF-44; S2-R24 |
| `spot_notional_pct_high_conviction` | `12.0` | CF-02; S8-R35 |
| `spot_notional_pct_low_conviction` | `6.0` | CF-02; S8-R35 |
| `spot_short_term_tp_move_pct` | `12.5` | S2 `[01:15:16]` |
| `touch_size_decay` | `[1.0, 1.0, 1.0, 0.66, 0.5]` | CF-07; Q2 inferred — shifted one index right; the only indexed reduction he gives is the 5th touch, S8 `[00:54:14]` |

### `backtest.py — §12 harness`

| Key | Default | Source |
|---|---|---|
| `backtest_execution_tf` | `"1m"` | [OUR CHOICE] — §12.2 |
| `fee_maker_bps` | `2.0` | [OUR CHOICE] |
| `fee_taker_bps` | `5.5` | [OUR CHOICE] |
| `funding_bps_per_8h` | `1.0` | [OUR CHOICE] — leverage only |
| `intrabar_fill_model` | `"stop_first"` | [OUR CHOICE] — §12.2, deliberately pessimistic |
| `limit_fill_requires_trade_through` | `True` | [OUR CHOICE] — §12.2 |
| `slippage_limit_bps` | `0.0` | [OUR CHOICE] — limits fill at price or not at all |
| `slippage_market_bps` | `5.0` | [OUR CHOICE] |

### `tbot/primitives.py + tbot/data.py (foundation — read by everyone)`

| Key | Default | Source |
|---|---|---|
| `atr_period` | `14` | ATR(14) is assumed throughout CONFLICTS.md — [OUR CHOICE] |
| `day_boundary_utc` | `"00:00"` | CF-45, P16; S5-R8, S8-R44 |
| `pmt_bin_atr` | `0.05` | P20 — [OUR CHOICE]; S5-A15 |
---

## 8 Worked examples

All five snippets run against `synthetic(seed=7)` and the shipped defaults, and the printed
values below are the real outputs (they are re-asserted in `tests/test_primitives.py`).

```python
from tbot.config import Config
from tbot.data import synthetic
from tbot.models import Box, Direction, ZoneSide, dec
import tbot.primitives as P

cfg = Config.load()
syn = synthetic(seed=7)
s, f = syn.series, syn.features
```

### 8.1 P5 + P6 — building a zone box and asking whether it is still alive

The two are always used together: **build the box once, freeze the midpoint, then re-measure the
fill as bars arrive.** `from_index` is the bar the zone became usable (the breakout), and it is
excluded — the formation bars cannot fill their own zone.

```python
box  = P.zone_box(s, cfg, f.consolidation_start, f.consolidation_end)   # P5
fill = P.measure_fill(s, cfg, box, ZoneSide.DEMAND, from_index=f.breakout_index)  # P6

box.top, box.bottom      # Decimal('120.94370385130748'), Decimal('119.05193245776317')
box.midpoint             # Decimal('119.997818154535325')   <-- store this on Zone.midpoint
fill.fill_pct            # Decimal('19.959998233633822')    ~20 % of depth
fill.is_dead             # False  (< zone_fill_invalidation_pct = 50)
fill.midpoint_hit        # False
fill.deepest_index       # 95     the bar that made the deepest penetration
```

Zone lifecycle for a detector:

```python
zone.midpoint = box.midpoint          # frozen at creation, NEVER recomputed (CF-08, S5-A11)
...                                    # later, on bar i:
fill = P.measure_fill(s.head(i + 1), cfg, box, zone.side, from_index=zone.breakout_index)
zone.fill_pct, zone.is_dead = fill.fill_pct, fill.is_dead
```

`is_dead` is not the end of the story: `dead_zone_htf_support_rescue` (CF-08, S7-R4) may re-arm
the setup **on the rescuing level, not on the zone**. Set `Zone.rescued_by_level_id` and build the
plan against that level.

### 8.2 P10 — the sufficient-gap test (the most misread primitive)

`breakout_index` is the bar whose **close** broke the consolidation, not the last consolidation
bar and not the extreme. The scan then walks forward and stops at the first retrace bigger than
`sufficient_gap_retrace_cutoff` (0.5) of the excursion so far — so the "extreme" is the end of the
first clean leg, never the highest bar of all time.

```python
g = P.sufficient_gap(s, cfg, f.breakout_index, Direction.LONG)   # breakout_index == 76

g.anchor         # Decimal('123.1')    close of bar 76
g.extreme        # Decimal('138.544')  end of the first clean leg
g.extreme_index  # 84
g.gap_pct        # Decimal('12.55')    |extreme - anchor| / anchor * 100
g.gap_atr        # Decimal('7.81')
g.required_pct   # Decimal('4.0')      sufficient_gap_pct_by_tf["1H"]
g.valid          # True                both tests pass (sufficient_gap_require_both_tests)
g.reasons        # ()                  populate Setup.vetoes from this when invalid
```

Two traps:

* **The timeframe is the series' own** unless you pass `tf=`. A zone drawn on 4H must be measured
  with a 4H series, or you silently use the 1H row of the table (4.0 % instead of 6.0 %).
* Non-default `sufficient_gap_anchor` values (`"zone_top_to_extreme"`, `"zone_mid_to_close"`)
  **require** `box=`; calling without it raises `ValueError` rather than guessing.

### 8.3 P4 — touch counting, and why your count differs from the chart

Touches are **sequences**, not bars. Consecutive in-band bars are one touch, and the counter
re-arms only after price leaves the band by `touch_reset_atr` (0.5 ATR). Scanning **stops** at the
first body close through the level — that is the hand-off to the CF-15 flip machine.

```python
t = P.count_touches(s, cfg, f.range_high, "resistance",
                    start_index=f.range_start, end_index=f.range_end)
t.count              # 5
[i for i, _ in t.history]   # [23, 31, 39, 47, 55]
t.break_index        # None

# extend past the range and the break appears:
P.count_touches(s, cfg, f.range_high, "resistance", start_index=f.range_start).break_index  # 60
```

`side` is the level's **original** role, not your trade direction. Feed `t.count` into the CF-07
limits: `line_touch_hard_limit` (3) for a bare line, `range_boundary_touch_limit` (6) for a range
boundary, and `touch_size_decay[touch_index - 1]` for the size multiplier — zones use the fill
rule instead (`zone_touch_uses_fill_rule_not_count`).

### 8.4 P14 — confluence scoring and dedup

Feed it *priced objects*, one per detector output, and it does the merging, the same-class dedup
and the two-class rule. Never pre-sum weights yourself, and never pass cross-market context in —
that is a veto, weight 0 (TBOT1 §10, CF-35).

```python
objs = [
    P.ConfluenceObject("lvl-a", dec(120.90), "sr_level", source_ids=("S4-R4",)),
    P.ConfluenceObject("lvl-b", dec(121.00), "sr_level"),          # same class as lvl-a
    P.ConfluenceObject("zone-1", dec(120.80), "zone", source_ids=("CF-10", "S5-R15")),
    P.ConfluenceObject("ob-59", dec(120.95), "order_block"),
    P.ConfluenceObject("fib-gp", dec(133.00), "fib"),              # far outside the merge band
]

r = P.score_confluence(s, cfg, 120.90, objs, at_index=90)
r.score        # Decimal('3.75')   = 1.5 (best sr_level) + 1.25 (zone) + 1.0 (ob); lvl-b adds 0
r.classes      # frozenset({'sr_level', 'zone', 'order_block'})
r.contributors # (lvl-a, zone-1, ob-59)  -- one winner per class
len(r.merged)  # 4   fib-gp is 12 points away; the band is confluence_merge_atr * ATR
r.qualified    # True  (>= min_confluence_count 3.0 and >= 2 classes)

# a continuation zone (his definition) adds the CF-10 bonus:
P.score_confluence(s, cfg, 120.90, objs, at_index=90, continuation_zone=True).score   # 4.75
```

4.75 ≥ `high_conviction_score` (4.0), so `confluence.py` maps this to `Conviction.HIGH` — provided
no adverse regime flag (§6.3). Tie-breaks *between* candidate setups (higher score, then higher
timeframe) belong to `confluence.py`, not here; `fib_loses_ties_to_sr` must be resolved **before**
you build the object list (S6-R38).

### 8.5 P20 — the entry price inside a zone

The zone box tells you where the zone is; P20 tells you **where in it to bid**. Pass the formation
window *plus every subsequent touch window* — the histogram is cumulative, that is the point.

```python
pmt = P.points_of_most_touch(
    s, cfg, box, ZoneSide.DEMAND,
    windows=[(f.consolidation_start, f.consolidation_end),   # formation
             (f.retest_index, f.retest_index + 3)],          # a later touch
    at_index=95,
)

pmt.price       # Decimal('120.088...')  -> Zone.entry_price_pmt, and the rung-1 limit price
pmt.bin_width   # Decimal('0.0901')      == pmt_bin_atr (0.05) * ATR (1.791)
len(pmt.counts) # 21 bins across the box
pmt.winning_bin # 11
```

Ties break toward the **outer edge** — `box_top` for demand, `box_bottom` for supply — because
that is where his lightest "entry at the SR point" sits (S5-R20, S7-R18). The limit goes at
`pmt.price` itself, never at a band edge (P9).

---

## 9 Invariants you must not break

1. **No repainting.** Never read a pivot before `confirmed_at_index`, never read a bar after the
   one you are standing on. Use `series.head(i + 1)` and `P.confirmed_swings(pivots, i)`.
2. **Freeze what the spec freezes.** `Zone.midpoint` is set once (CF-08). `TradePlan.stop_price`
   and the initial risk are set once; trailing mutates `Position.current_stop`, never the plan.
   `planned_average_entry` is for pre-trade R:R; realised maths uses `average_entry` (CF-18).
3. **Order of construction is entry ladder → stop → take-profits** (SPEC.md §8, TBOT1 §14 step 14).
   Do not size before the stop exists.
4. **One stop per plan.** `duplicate_stop_offset_bps` is an execution-reliability device; the
   backtest simulates the first stop only (A9).
5. **Never force a setup.** If nothing qualifies, emit nothing (PL-9, S6-R46). An empty plan list
   is a valid, expected result.
6. **Vetoes are recorded, not swallowed.** Push the `reasons` string from the primitive that
   failed into `Setup.vetoes`; gate order is §7.1 G1…G9 and the first veto stops evaluation.
7. **Never invent a config key**, never hard-code a number that §11 already names, and keep every
   `[OUR CHOICE]` marker attached to the value it describes.
8. **Decimal in, Decimal out** for prices; floats stay inside numpy loops. Never round a price for
   display inside a computation path.
9. **Determinism.** No `uuid4`, no wall-clock reads, no set iteration order dependence, no
   `dict` ordering assumptions beyond insertion order, no unseeded RNG.
10. **`is_closed` only.** Detectors never see a forming bar; the harness feeds closed bars and
    P1's whole no-repainting guarantee rests on it.

### Extending the foundation

Need a new shared primitive, model field or config key? It goes **into the foundation**, with a
docstring naming its source ID, a test in `tests/test_primitives.py`, and an entry here — not
into your module as a private helper. That is the whole point of this file: the same rule
implemented twice, slightly differently, is the failure mode this layer exists to prevent.
