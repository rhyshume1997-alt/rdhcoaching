"""tbot.primitives — SPEC.md §4 primitives P1–P20 plus the shared ATR helper.

Every function here is **pure**: it reads a :class:`~tbot.models.Series` and a
:class:`~tbot.config.Config` (or explicitly documented arguments) and returns a value.  Nothing
mutates its inputs, nothing touches module-level state, nothing does I/O.

Scope discipline: this module contains **no detector logic**.  Detectors (SPEC.md §5), the trade
plan builder (§8), the management state machine (§9), the risk layer (§10) and the backtester
(§12) all import from here and must not re-implement any of it.

Every primitive's docstring names its source ID (``Pn`` plus any ``CF-nn`` / ``Sn-Rnn`` rule).
As SPEC.md §4 states outright, *all* of P1–P20 are **[OUR CHOICE]** algorithms supplied by
CONFLICTS.md for concepts the corpus leaves undefined; they are the first sweep targets in a
backtest.  Individual parameter-level [OUR CHOICE] markers are repeated per function.

Index convention: every ``*_index`` argument and field is a positional bar index into the
``series`` that was passed in (0-based).  Ranges written ``[start_index, end_index]`` are
**inclusive** at both ends unless the docstring says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Literal, Sequence

import numpy as np

from .config import Config
from .models import (
    Box,
    Direction,
    Level,
    Series,
    SwingKind,
    SwingPoint,
    Timeframe,
    Trend,
    ZoneSide,
    dec,
)

__all__ = [
    # shared
    "true_range",
    "atr_array",
    "atr_at",
    "atr_value",
    # P1
    "swing_points",
    "confirmed_swings",
    # P2
    "DirectionalChange",
    "directional_change",
    "find_directional_changes",
    # P3
    "LevelCluster",
    "cluster_levels",
    # P4
    "TouchCount",
    "count_touches",
    # P5
    "zone_box",
    "order_block_box",
    # P6
    "ZoneFill",
    "midpoint_of",
    "measure_fill",
    # P7
    "MidRange",
    "mid_range",
    "in_no_trade_band",
    # P8
    "RangeCheck",
    "check_range",
    # P9
    "tolerance_band",
    "bar_at_level",
    "price_at_level",
    # P10
    "GapMeasure",
    "sufficient_gap",
    # P11
    "classify_trend",
    # P12
    "is_capitulation_wick",
    "capitulation_wicks",
    # P13
    "ConsolidationCheck",
    "check_consolidation",
    "is_horizontal_consolidation",
    # P14
    "ConfluenceObject",
    "ConfluenceResult",
    "score_confluence",
    # P15
    "ob_liquidity_taken_pct",
    # P16
    "day_start",
    "week_start",
    "is_weekend",
    "same_session",
    # P17
    "is_stale_trade",
    # P18
    "LiquidityScreen",
    "liquidity_screen",
    # P19
    "stop_buffer",
    "stop_buffer_zone",
    "apply_stop_buffer",
    # P20
    "PMTResult",
    "points_of_most_touch",
]

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


# =========================================================================== ATR


def true_range(series: Series) -> np.ndarray:
    """Wilder true range per bar.

    ``TR[0] = high - low``; afterwards ``max(h-l, |h - prev_close|, |l - prev_close|)``.
    Shared helper for :func:`atr_array` (SPEC.md §4 preamble: ``ATR(n)`` means Wilder ATR).
    """
    high, low, close = series.high, series.low, series.close
    if len(series) == 0:
        return np.empty(0, dtype="float64")
    tr = np.empty(len(series), dtype="float64")
    tr[0] = high[0] - low[0]
    if len(series) > 1:
        prev_close = close[:-1]
        tr[1:] = np.maximum.reduce([
            high[1:] - low[1:],
            np.abs(high[1:] - prev_close),
            np.abs(low[1:] - prev_close),
        ])
    return tr


def atr_array(series: Series, period: int) -> np.ndarray:
    """Wilder ATR over ``period`` bars, one value per bar, no NaNs.

    Seeded at bar ``period-1`` with the simple mean of the first ``period`` true ranges, then
    smoothed ``ATR[i] = (ATR[i-1]*(n-1) + TR[i]) / n``.

    **[OUR CHOICE]** warm-up: bars before the seed carry the *expanding mean* of the true ranges
    seen so far instead of NaN, so short synthetic series and the first bars of a backtest still
    produce a usable band.  SPEC.md §12.1 tells the backtester to discard the warm-up window
    anyway; this only keeps the primitives total.
    """
    if period < 1:
        raise ValueError(f"atr period must be >= 1, got {period}")
    # Memoised on the Series' own derived-array cache, exactly like ``open``/``high``/… — a
    # ``Series`` is immutable by contract (INTERFACES.md §2), so the value can never go stale,
    # and every caller still gets the identical array.  Without this the pipeline recomputes the
    # same ATR thousands of times per bar (it is the single hottest call in the package).
    cache_key = f"__atr_{period}"
    cached = series._cache.get(cache_key)
    if cached is not None:
        return cached
    tr = true_range(series)
    n = len(tr)
    out = np.empty(n, dtype="float64")
    if n == 0:
        return out
    running = 0.0
    for i in range(min(period, n)):
        running += tr[i]
        out[i] = running / (i + 1)
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    out.flags.writeable = False
    series._cache[cache_key] = out
    return out


def atr_value(series: Series, config: Config, index: int | None = None) -> float:
    """``ATR(atr_period)`` at ``index`` as a **float** — the hot path, no Decimal round-trip.

    :func:`atr_at` is the Decimal face of the same number and is what rules should use.  This
    exists because the measured hot path did ``float(atr_at(...))``: a float out of the cached
    ATR array, boxed into a ``Decimal``, then immediately unboxed again.  At 156,715 ``atr_at``
    calls per bar (``_touches`` -> :func:`tolerance_band` -> here) that round-trip was the single
    largest leaf cost in the backtest.

    **Bit-exact with the old path by construction**: ``dec()`` of a float is exact and ``float()``
    of that Decimal returns the identical float, so every caller sees the same value it saw
    before.  Nothing here changes a rule or a threshold.
    """
    if len(series) == 0:
        raise ValueError("atr_at: empty series has no ATR")
    i = len(series) - 1 if index is None else _norm_index(series, index)
    return float(atr_array(series, config.atr_period)[i])


def atr_at(series: Series, config: Config, index: int | None = None) -> Decimal:
    """``ATR(atr_period)`` on this series at ``index`` (default: the last bar), as a Decimal.

    Source: SPEC.md §4 preamble, ``atr_period`` (**[OUR CHOICE]**, default 14).  Every ``*_atr``
    config key is a multiple of this value, always measured *on the object's own timeframe*.
    """
    return dec(atr_value(series, config, index))


def _norm_index(series: Series, index: int) -> int:
    n = len(series)
    i = index + n if index < 0 else index
    if not 0 <= i < n:
        raise IndexError(f"bar index {index} out of range for series of {n} bars")
    return i


def _atr_value(series: Series, config: Config, index: int | None) -> float:
    return atr_value(series, config, index)


# =========================================================================== P1


def swing_points(
    series: Series,
    config: Config,
    *,
    k: int | None = None,
    source: Literal["body", "wick"] | None = None,
) -> list[SwingPoint]:
    """**P1** — fractal swing/pivot detection (S7-R11, S5-R44; answers S2-A12, S5-A16, S7-A7,
    S8-A2, S6-A1).  **[OUR CHOICE]** algorithm.

    A bar ``i`` is a swing high when its body high is the maximum of the window
    ``[i-k, i+k]``, and a swing low when its body low is the minimum.  Both may be true at once.

    Parameters
    ----------
    series : the bars to scan (closed bars only — P1 forbids repainting).
    config : uses ``swing_k`` (default 3; the spec notes 5 on weekly/monthly) and
        ``swing_price_source`` (``"body"`` by default — bodies, not wicks).
    k, source : per-call overrides of those two keys (e.g. ``k=5`` on ``1W``).

    Returns pivots in ascending ``bar_index`` order.  ``price`` is the body extreme,
    ``wick_price`` the wick extreme at the same bar (used for stops, CF-14, and SFP raids), and
    ``confirmed_at_index = bar_index + k`` — **a pivot is unusable before that bar**
    (:meth:`~tbot.models.SwingPoint.is_usable_at`).

    Ties break toward the **earlier** bar: the pivot bar must be strictly beyond every bar to its
    left in the window and at-or-beyond every bar to its right.
    """
    kk = config.swing_k if k is None else k
    src = config.swing_price_source if source is None else source
    if kk < 1:
        raise ValueError(f"swing_k must be >= 1, got {kk}")
    n = len(series)
    if n < 2 * kk + 1:
        return []
    if src == "body":
        highs, lows = series.body_high, series.body_low
    elif src == "wick":
        highs, lows = series.high, series.low
    else:  # pragma: no cover - guarded by config validation
        raise ValueError(f"swing_price_source must be 'body' or 'wick', got {src!r}")

    out: list[SwingPoint] = []
    for i in range(kk, n - kk):
        left = slice(i - kk, i)
        right = slice(i + 1, i + kk + 1)
        if highs[i] > highs[left].max() and highs[i] >= highs[right].max():
            out.append(_mk_swing(series, SwingKind.HIGH, i, dec(highs[i]), dec(series.high[i]), kk))
        if lows[i] < lows[left].min() and lows[i] <= lows[right].min():
            out.append(_mk_swing(series, SwingKind.LOW, i, dec(lows[i]), dec(series.low[i]), kk))
    out.sort(key=lambda p: (p.bar_index, p.kind.value))
    return out


def _mk_swing(series: Series, kind: SwingKind, i: int, price: Decimal, wick: Decimal, k: int) -> SwingPoint:
    return SwingPoint(
        id=f"{series.symbol}:{series.tf.value}:{kind.value}:{i}",
        symbol=series.symbol,
        tf=series.tf,
        kind=kind,
        bar_index=i,
        price=price,
        wick_price=wick,
        confirmed_at_index=i + k,
        k=k,
    )


def confirmed_swings(pivots: Sequence[SwingPoint], at_index: int) -> list[SwingPoint]:
    """P1 no-lookahead filter: the pivots a detector may read while standing on bar ``at_index``."""
    return [p for p in pivots if p.confirmed_at_index <= at_index]


# =========================================================================== P2


@dataclass(frozen=True, slots=True)
class DirectionalChange:
    """Result of :func:`directional_change` (**P2**)."""

    trigger_index: int          #: the bar ``j`` the move is measured from
    direction: Direction        #: LONG = move up, SHORT = move down
    extreme_index: int
    extreme_price: Decimal
    move: Decimal               #: ``|extreme - close[j]|`` in price
    move_atr: Decimal           #: the same move in ATR multiples
    order_block_index: int | None  #: last opposite-colour candle at or before ``j`` (S6-R1/R2)


def directional_change(series: Series, config: Config, j: int) -> DirectionalChange | None:
    """**P2** — "directional change in price", the order-block trigger (S6-R1, S6-R2; S6-A1).
    **[OUR CHOICE]** algorithm.

    From bar ``j``, look forward at most ``dir_change_max_bars`` (default 10) and take the larger
    excursion from ``close[j]`` (highest high for an up move, lowest low for a down move).  The
    move qualifies when

    * ``|extreme - close[j]| >= dir_change_atr * ATR(atr_period)`` (default 2.0 ATR), **and**

    P2 stays a pure geometric primitive.  **Q6**'s percentage-by-timeframe floor is applied by the
    *consumers*, where it can be reported: supply/demand zones already run it as P10
    (``sufficient_gap``), and order blocks run it under ``dir_change_uses_sufficient_gap_table``
    (see :mod:`tbot.detectors.orderblocks`).

    * price never retraced more than **33 %** of the excursion before reaching that extreme
      (the retrace figure is fixed in the P2 pseudocode, not a config key).

    Returns ``None`` when no qualifying move exists.  ``order_block_index`` is the last
    opposite-colour candle at or before ``j`` — the last **red** candle before an up move, the
    last **green** candle before a down move.  A doji (``close == open``) counts as red, i.e. as
    a bullish-OB candidate — **[OUR CHOICE]**, the corpus never rules on dojis.
    """
    n = len(series)
    jj = _norm_index(series, j)
    if jj >= n - 1:
        return None
    stop = min(n - 1, jj + config.dir_change_max_bars)
    if stop <= jj:
        return None
    anchor = float(series.close[jj])
    highs, lows = series.high, series.low
    up_i = int(jj + 1 + np.argmax(highs[jj + 1: stop + 1]))
    dn_i = int(jj + 1 + np.argmin(lows[jj + 1: stop + 1]))
    up_move, dn_move = float(highs[up_i]) - anchor, anchor - float(lows[dn_i])

    if up_move <= 0 and dn_move <= 0:
        return None
    direction = Direction.LONG if up_move >= dn_move else Direction.SHORT
    extreme_index = up_i if direction is Direction.LONG else dn_i
    move = up_move if direction is Direction.LONG else dn_move

    atr = _atr_value(series, config, jj)
    if atr <= 0 or move < config.dir_change_atr * atr:
        return None
    if _retraced_before_extreme(series, jj, extreme_index, direction, move, cutoff=0.33):
        return None
    return DirectionalChange(
        trigger_index=jj,
        direction=direction,
        extreme_index=extreme_index,
        extreme_price=dec(highs[extreme_index] if direction is Direction.LONG else lows[extreme_index]),
        move=dec(move),
        move_atr=dec(move / atr),
        order_block_index=_last_opposite_colour(series, jj, direction),
    )


def _retraced_before_extreme(
    series: Series, start: int, extreme_index: int, direction: Direction, move: float, cutoff: float
) -> bool:
    """True when price gave back more than ``cutoff`` of the excursion before the extreme."""
    if move <= 0:
        return True
    anchor = float(series.close[start])
    run = anchor
    for i in range(start + 1, extreme_index):
        # Measure the give-back against the best price set by *earlier* bars: a bar that itself
        # extends the move is not penalised for its own opposite extreme.  **[OUR CHOICE]**
        if direction is Direction.LONG:
            if run > anchor and (run - float(series.low[i])) > cutoff * move:
                return True
            run = max(run, float(series.high[i]))
        else:
            if run < anchor and (float(series.high[i]) - run) > cutoff * move:
                return True
            run = min(run, float(series.low[i]))
    return False


def _last_opposite_colour(series: Series, j: int, direction: Direction) -> int | None:
    """S6-R1/S6-R2: last red candle before an up move / last green candle before a down move."""
    green = series.is_green
    for i in range(j, -1, -1):
        if direction is Direction.LONG and not bool(green[i]):
            return i
        if direction is Direction.SHORT and bool(green[i]):
            return i
    return None


def find_directional_changes(series: Series, config: Config) -> list[DirectionalChange]:
    """**P2** applied to every bar; the order-block detector's raw event feed."""
    out: list[DirectionalChange] = []
    for j in range(len(series) - 1):
        dc = directional_change(series, config, j)
        if dc is not None:
            out.append(dc)
    return out


# =========================================================================== P3


@dataclass(frozen=True, slots=True)
class LevelCluster:
    """One P3 price cluster — the raw material the §5.1 level detector turns into a
    :class:`~tbot.models.Level`."""

    price: Decimal                     #: volume-weighted mean of member pivots
    member_pivot_ids: tuple[str, ...]
    bar_indices: tuple[int, ...]
    high_members: int
    low_members: int
    radius: Decimal                    #: the clustering radius that produced it

    @property
    def touch_seed(self) -> int:
        """Member count — the "two touches is enough" test of S4-R4 applies to this."""
        return len(self.member_pivot_ids)


def cluster_levels(
    series: Series,
    config: Config,
    pivots: Sequence[SwingPoint],
    *,
    now_index: int | None = None,
) -> list[LevelCluster]:
    """**P3** — horizontal level construction and clustering (S4-R4, S7 ``[00:05:04]``;
    answers S2-A3, S3-A7, S4-A2, S5-A15).  **[OUR CHOICE]** algorithm.

    Single-link clustering of confirmed pivots whose ``bar_index >= now - level_lookback_bars``
    (default 500), with radius ``level_cluster_atr * ATR(atr_period)`` (default 0.25 ATR).  A
    cluster survives when it holds at least ``level_min_touches`` pivots (default 2).  The cluster
    price is the **volume-weighted mean** of its member pivot prices — the machine form of his
    "points of most touch".

    ``now_index`` defaults to the last bar; only pivots confirmed at or before it are used, so a
    backtest can call this bar-by-bar without lookahead.  Re-cluster only on a **new confirmed
    pivot** — never on intrabar data.

    Returns clusters sorted ascending by price.
    """
    if len(series) == 0:
        return []
    now = len(series) - 1 if now_index is None else _norm_index(series, now_index)
    lookback_start = now - config.level_lookback_bars
    usable = [
        p for p in pivots
        if p.confirmed_at_index <= now and p.bar_index >= lookback_start and p.bar_index <= now
    ]
    if not usable:
        return []
    radius = float(atr_at(series, config, now)) * config.level_cluster_atr
    usable.sort(key=lambda p: (float(p.price), p.bar_index))

    groups: list[list[SwingPoint]] = [[usable[0]]]
    for pivot in usable[1:]:
        if float(pivot.price) - float(groups[-1][-1].price) <= radius:
            groups[-1].append(pivot)
        else:
            groups.append([pivot])

    volume = series.volume
    out: list[LevelCluster] = []
    for grp in groups:
        if len(grp) < config.level_min_touches:
            continue
        weights = [max(float(volume[p.bar_index]), 0.0) for p in grp]
        total = sum(weights)
        if total > 0:
            price = sum(float(p.price) * w for p, w in zip(grp, weights)) / total
        else:  # zero-volume series: fall back to the plain mean  **[OUR CHOICE]**
            price = sum(float(p.price) for p in grp) / len(grp)
        out.append(LevelCluster(
            price=dec(price),
            member_pivot_ids=tuple(p.id for p in grp),
            bar_indices=tuple(p.bar_index for p in grp),
            high_members=sum(1 for p in grp if p.kind is SwingKind.HIGH),
            low_members=sum(1 for p in grp if p.kind is SwingKind.LOW),
            radius=dec(radius),
        ))
    out.sort(key=lambda c: c.price)
    return out


# =========================================================================== P4


@dataclass(frozen=True, slots=True)
class TouchCount:
    """Result of :func:`count_touches` (**P4**)."""

    count: int
    history: tuple[tuple[int, Decimal], ...]   #: ``(bar_index, close)`` per counted touch
    break_index: int | None                    #: first body close through the level, if any
    last_touch_index: int | None

    @property
    def broke(self) -> bool:
        """True when a body close went through the level (hands over to the CF-15 flip machine)."""
        return self.break_index is not None


def count_touches(
    series: Series,
    config: Config,
    level_price: Decimal | float,
    side: Literal["support", "resistance"],
    *,
    start_index: int = 0,
    end_index: int | None = None,
) -> TouchCount:
    """**P4** — touch definition and counting (answers S2-A5, S5-A16, S8-A11, TBOT1-A6).
    **[OUR CHOICE]** algorithm.

    Band: ``level_tolerance_atr * ATR(atr_period)`` (default 0.15 ATR), re-evaluated per bar.

    * a **touch** is a bar whose range intersects the band *and* which closes on the level's
      ORIGINAL side (at or above a support, at or below a resistance);
    * consecutive in-band bars are **one** touch;
    * the counter re-arms only after price leaves the band by ``touch_reset_atr * ATR``
      (default 0.5 ATR), measured from the level to the nearest edge of the bar's range;
    * a **body close through** the level ends the sequence and hands over to the CF-15 flip
      machine — scanning stops there and ``break_index`` is set;
    * counters reset on role flip or cluster rebuild, which is the caller's job (call again).

    ``side`` is the level's original role, not the trade direction.
    """
    price = float(level_price)
    n = len(series)
    if n == 0:
        return TouchCount(0, (), None, None)
    lo_i = _norm_index(series, start_index)
    hi_i = n - 1 if end_index is None else _norm_index(series, end_index)
    atr = atr_array(series, config.atr_period)
    high, low, close = series.high, series.low, series.close

    count = 0
    history: list[tuple[int, Decimal]] = []
    armed = True
    last_touch: int | None = None
    for i in range(lo_i, hi_i + 1):
        band = config.level_tolerance_atr * float(atr[i])
        reset = config.touch_reset_atr * float(atr[i])
        wrong_side = close[i] < price if side == "support" else close[i] > price
        if wrong_side:
            return TouchCount(count, tuple(history), i, last_touch)
        intersects = low[i] <= price + band and high[i] >= price - band
        if intersects:
            if armed:
                count += 1
                history.append((i, dec(close[i])))
                last_touch = i
                armed = False
        else:
            gap = low[i] - price if low[i] > price else price - high[i]
            if gap >= reset:
                armed = True
    return TouchCount(count, tuple(history), None, last_touch)


# =========================================================================== P5


def zone_box(
    series: Series,
    config: Config,
    start_index: int,
    end_index: int,
    *,
    source: str | None = None,
) -> Box:
    """**P5** — zone box boundaries (S5-R17, S5-R19, S6-R9, S7-R7; CF-13; answers S5-A4, S6-A4,
    S8-A6).  **[OUR CHOICE]** algorithm.

    Body-anchored box over the inclusive window ``[start_index, end_index]``::

        box_top    = max(body_high)   box_bottom = min(body_low)

    Then each side's wick is folded in **only if it is small on both tests**:
    ``wick_len <= wick_include_max_pct/100 * price`` (default 2 %) **and**
    ``wick_len <= wick_include_max_atr * ATR`` (default 0.5 ATR, an **OUR number** addition).
    Giant wicks stay excluded — that is the whole point of the test.  The percentage test is
    taken against the box edge being extended (**[OUR CHOICE]** reference price).

    ``source`` overrides the config key: ``"body_plus_small_wick"`` / ``"body_with_small_wick"``
    (default), ``"body_only"`` (no wick ever), ``"full_range"`` (always high/low).  Zones read
    ``zone_box_source``; order blocks read ``ob_box_source`` via :func:`order_block_box`.
    """
    lo = _norm_index(series, start_index)
    hi = _norm_index(series, end_index)
    if hi < lo:
        raise ValueError(f"zone_box: end_index {end_index} precedes start_index {start_index}")
    mode = source or config.zone_box_source
    top = float(series.body_high[lo:hi + 1].max())
    bottom = float(series.body_low[lo:hi + 1].min())
    wick_top = float(series.high[lo:hi + 1].max())
    wick_bottom = float(series.low[lo:hi + 1].min())

    if mode == "full_range":
        return Box(dec(wick_top), dec(wick_bottom), lo, hi, True, True)
    if mode == "body_only":
        return Box(dec(top), dec(bottom), lo, hi, False, False)

    atr = _atr_value(series, config, hi)
    inc_up = _small_wick(wick_top - top, top, atr, config)
    inc_dn = _small_wick(bottom - wick_bottom, bottom, atr, config)
    return Box(
        top=dec(wick_top if inc_up else top),
        bottom=dec(wick_bottom if inc_dn else bottom),
        start_index=lo,
        end_index=hi,
        included_upper_wick=inc_up,
        included_lower_wick=inc_dn,
    )


def _small_wick(wick_len: float, reference_price: float, atr: float, config: Config) -> bool:
    if wick_len <= 0:
        return False
    pct_ok = wick_len <= config.wick_include_max_pct / 100.0 * abs(reference_price)
    atr_ok = config.wick_include_max_atr <= 0 or wick_len <= config.wick_include_max_atr * atr
    return pct_ok and atr_ok


def order_block_box(series: Series, config: Config, bar_index: int) -> Box:
    """**P5 / S6-R3** — the single-candle order-block box: that candle's body under the same wick
    test, using ``ob_box_source`` (default ``"body_with_small_wick"``).  ``ob_max_candles`` is 1:
    an OB is **exactly one candle, never two** (S6-R3), so this takes a single index.
    """
    i = _norm_index(series, bar_index)
    return zone_box(series, config, i, i, source=config.ob_box_source)


# =========================================================================== P6


@dataclass(frozen=True, slots=True)
class ZoneFill:
    """Result of :func:`measure_fill` (**P6**)."""

    fill_pct: Decimal            #: deepest penetration as % of box depth, clamped to [0, 100]
    is_dead: bool                #: ``fill_pct >= zone_fill_invalidation_pct`` (CF-08)
    midpoint_hit: bool           #: the 50 % line itself was reached
    deepest_index: int | None
    deepest_price: Decimal | None
    midpoint: Decimal


def midpoint_of(box: Box) -> Decimal:
    """**P6** — the zone midpoint, ``(box_top + box_bottom) / 2``.

    Frozen at zone creation and **never re-measured** (``zone_fill_reference =
    "as_originally_drawn"``, CF-08, S5-A11).  Callers must store it on the
    :class:`~tbot.models.Zone` rather than recompute it from a re-drawn box.
    """
    return box.midpoint


def measure_fill(
    series: Series,
    config: Config,
    box: Box,
    side: ZoneSide,
    *,
    from_index: int,
    to_index: int | None = None,
) -> ZoneFill:
    """**P6** — 50 %-fill measurement (CF-08; answers S5-A9, S5-A10, S5-A11, S6-A3, S8-A7).
    **[OUR CHOICE]** algorithm.

    Penetration is measured from the edge price approaches **first** — ``box_top`` for a demand
    zone, ``box_bottom`` for a supply zone — inward, as a percentage of the box depth, over bars
    ``(from_index, to_index]``.  ``from_index`` is the bar the zone was created on and is
    **excluded**: the formation bars cannot fill their own zone.

    ``zone_fill_measure`` selects the probe: ``"wick_touch"`` (default, conservative — any wick
    through counts) or ``"close_beyond"`` (the sweep alternative, closes only).

    A zone is dead at ``fill_pct >= zone_fill_invalidation_pct`` (default 50; the S7 alternative
    is 70/80, in which case order blocks use P15 instead — see :func:`ob_liquidity_taken_pct`).
    """
    depth = float(box.height)
    start = _norm_index(series, from_index) + 1
    end = len(series) - 1 if to_index is None else _norm_index(series, to_index)
    mid = box.midpoint
    if depth <= 0 or start > end:
        return ZoneFill(_ZERO, False, False, None, None, mid)

    if config.zone_fill_measure == "close_beyond":
        probe = series.close
    else:
        probe = series.low if side is ZoneSide.DEMAND else series.high

    window = probe[start:end + 1]
    if side is ZoneSide.DEMAND:
        idx = int(np.argmin(window))
        deepest = float(window[idx])
        penetration = float(box.top) - deepest
    else:
        idx = int(np.argmax(window))
        deepest = float(window[idx])
        penetration = deepest - float(box.bottom)

    pct = max(0.0, min(penetration / depth, 1.0)) * 100.0
    fill_pct = dec(pct)
    return ZoneFill(
        fill_pct=fill_pct,
        is_dead=float(fill_pct) >= config.zone_fill_invalidation_pct,
        midpoint_hit=penetration >= depth / 2.0,
        deepest_index=start + idx,
        deepest_price=dec(deepest),
        midpoint=mid,
    )


# =========================================================================== P7


@dataclass(frozen=True, slots=True)
class MidRange:
    """Result of :func:`mid_range` (**P7**)."""

    price: Decimal
    band_low: Decimal
    band_high: Decimal
    geometric_mid: Decimal
    source: Literal["level", "geometric"]
    level_id: str | None = None

    def contains(self, price: Decimal | float) -> bool:
        """True when ``price`` sits inside the no-trade band (gate G6, CF-25)."""
        return self.band_low <= dec(price) <= self.band_high


def mid_range(
    config: Config,
    range_high: Decimal | float,
    range_low: Decimal | float,
    levels: Sequence[Level] = (),
) -> MidRange:
    """**P7** — mid-range (S4 definition "not exactly 50 %"; CF-25, CF-26; answers S4-A1, S4-A3,
    S8-A14).  **[OUR CHOICE]** algorithm.

    Geometric mid is ``(range_high + range_low) / 2``.  If a P3 level sits within
    ``mid_range_search_pct`` % **of the range height** around it (default 10 %), the
    highest-touch-count such level becomes the mid instead; ties break toward the level nearest
    the geometric mid (**[OUR CHOICE]**), then by lowest id for determinism.

    The no-trade band is ``mid ± mid_range_band_pct % of range height`` (default 15 % each side).
    Gate G6 rejects any setup whose price sits inside it.
    """
    hi, lo = dec(range_high), dec(range_low)
    if hi <= lo:
        raise ValueError(f"mid_range: range_high {hi} must exceed range_low {lo}")
    height = hi - lo
    geo = (hi + lo) / Decimal(2)
    search = height * dec(config.mid_range_search_pct) / _HUNDRED
    band = height * dec(config.mid_range_band_pct) / _HUNDRED

    candidates = [lv for lv in levels if abs(lv.price - geo) <= search]
    chosen: Level | None = None
    if candidates:
        chosen = sorted(candidates, key=lambda lv: (-lv.touch_count, abs(lv.price - geo), lv.id))[0]
    mid = chosen.price if chosen is not None else geo
    return MidRange(
        price=mid,
        band_low=mid - band,
        band_high=mid + band,
        geometric_mid=geo,
        source="level" if chosen is not None else "geometric",
        level_id=chosen.id if chosen is not None else None,
    )


def in_no_trade_band(price: Decimal | float, mid: MidRange) -> bool:
    """Gate G6 helper (CF-25, S4-R8, S5-R13, S8-R30): is price inside the mid-range band?"""
    return mid.contains(price)


# =========================================================================== P8


@dataclass(frozen=True, slots=True)
class RangeCheck:
    """Result of :func:`check_range` (**P8**)."""

    valid: bool
    upper_touches: int
    lower_touches: int
    height: Decimal
    height_atr: Decimal
    bars: int
    body_close_beyond_index: int | None
    last_touch_index: int | None
    stale: bool
    reasons: tuple[str, ...]


def check_range(
    series: Series,
    config: Config,
    upper: Decimal | float,
    lower: Decimal | float,
    *,
    start_index: int,
    end_index: int | None = None,
) -> RangeCheck:
    """**P8** — range validity and staleness (answers S4-A15, S4-A16).  **[OUR CHOICE]** algorithm.

    A range exists over ``[start_index, end_index]`` on the structure timeframe when

    * the window is at least ``range_min_bars`` bars (default 20), **and**
    * the upper level has ≥2 touches and the lower level has ≥2 touches (P3/P4), **and**
    * ``upper - lower >= range_min_height_atr * ATR`` (default 3.0 ATR), **and**
    * no **body close** has occurred beyond either level.

    Staleness (retirement, not death): age above ``range_max_age_bars`` (300) or no touch within
    ``range_stale_bars`` (60).  Death is CF-26's "body close beyond a boundary **then** a CF-15
    flip in the opposite direction" and belongs to the range detector, not here — this primitive
    only reports ``body_close_beyond_index``, the first half of that test.

    Nested ranges: the range on the **highest** timeframe wins (S7-R20) — again a detector
    decision, made with these measurements.
    """
    hi, lo = dec(upper), dec(lower)
    if hi <= lo:
        raise ValueError(f"check_range: upper {hi} must exceed lower {lo}")
    n = len(series)
    if n == 0:
        return RangeCheck(False, 0, 0, hi - lo, _ZERO, 0, None, None, True, ("empty series",))
    lo_i = _norm_index(series, start_index)
    hi_i = n - 1 if end_index is None else _norm_index(series, end_index)
    bars = hi_i - lo_i + 1

    up = count_touches(series, config, hi, "resistance", start_index=lo_i, end_index=hi_i)
    dn = count_touches(series, config, lo, "support", start_index=lo_i, end_index=hi_i)

    close = series.close
    beyond: int | None = None
    for i in range(lo_i, hi_i + 1):
        if close[i] > float(hi) or close[i] < float(lo):
            beyond = i
            break

    atr = float(atr_at(series, config, hi_i))
    height = hi - lo
    height_atr = dec(float(height) / atr) if atr > 0 else _ZERO

    reasons: list[str] = []
    if bars < config.range_min_bars:
        reasons.append(f"window {bars} bars < range_min_bars {config.range_min_bars}")
    if up.count < 2:
        reasons.append(f"upper touches {up.count} < 2")
    if dn.count < 2:
        reasons.append(f"lower touches {dn.count} < 2")
    if float(height_atr) < config.range_min_height_atr:
        reasons.append(f"height {float(height_atr):.2f} ATR < range_min_height_atr "
                       f"{config.range_min_height_atr}")
    if beyond is not None:
        reasons.append(f"body close beyond a boundary at bar {beyond}")

    touches = [t for t in (up.last_touch_index, dn.last_touch_index) if t is not None]
    last_touch = max(touches) if touches else None
    stale = bars > config.range_max_age_bars or (
        last_touch is None or (hi_i - last_touch) > config.range_stale_bars
    )
    return RangeCheck(
        valid=not reasons,
        upper_touches=up.count,
        lower_touches=dn.count,
        height=height,
        height_atr=height_atr,
        bars=bars,
        body_close_beyond_index=beyond,
        last_touch_index=last_touch,
        stale=stale,
        reasons=tuple(reasons),
    )


# =========================================================================== P9


def tolerance_band(
    series: Series, config: Config, level_price: Decimal | float, at_index: int | None = None
) -> tuple[Decimal, Decimal]:
    """**P9** — "at the level" / retest tolerance (answers S2-A2, S3-A8).  **[OUR CHOICE]**.

    Returns ``(low, high) = level_price ± level_tolerance_atr * ATR(atr_period)`` — the same band
    as P4, reused for retest detection, "price is at range highs/lows" and the mid-range test.

    **Limit orders are placed at the level price itself, not at the band edge.**
    """
    band = dec(atr_value(series, config, at_index) * config.level_tolerance_atr)
    price = dec(level_price)
    return price - band, price + band


def bar_at_level(
    series: Series, config: Config, level_price: Decimal | float, bar_index: int
) -> bool:
    """**P9** — does bar ``bar_index``'s range intersect the level's tolerance band?"""
    i = _norm_index(series, bar_index)
    low, high = tolerance_band(series, config, level_price, i)
    return float(series.low[i]) <= float(high) and float(series.high[i]) >= float(low)


def price_at_level(
    series: Series, config: Config, price: Decimal | float, level_price: Decimal | float,
    at_index: int | None = None,
) -> bool:
    """**P9** — is a single price inside the level's tolerance band?"""
    low, high = tolerance_band(series, config, level_price, at_index)
    return low <= dec(price) <= high


# =========================================================================== P10


@dataclass(frozen=True, slots=True)
class GapMeasure:
    """Result of :func:`sufficient_gap` (**P10**)."""

    anchor: Decimal
    extreme: Decimal
    extreme_index: int
    gap_pct: Decimal
    gap_atr: Decimal
    required_pct: Decimal
    required_atr: Decimal
    valid: bool
    reasons: tuple[str, ...]


def sufficient_gap(
    series: Series,
    config: Config,
    breakout_index: int,
    direction: Direction,
    *,
    box: Box | None = None,
    tf: Timeframe | str | None = None,
    end_index: int | None = None,
) -> GapMeasure:
    """**P10** — sufficient-gap anchor and measurement (CF-11, S5-R16; answers S5-A1, S6-A2).
    **[OUR CHOICE]** algorithm and **OUR number** for the ATR multiple.

    Anchor per ``sufficient_gap_anchor``:

    * ``"breakout_close_to_extreme"`` (default) — the breakout candle's **close**;
    * ``"zone_top_to_extreme"`` — the zone box edge in the direction of travel (needs ``box``);
    * ``"zone_mid_to_close"`` — the zone midpoint, measured to the breakout close (needs ``box``).

    The extreme is the furthest price reached after the breakout **before** a retrace greater than
    ``sufficient_gap_retrace_cutoff`` (default 0.5) of the excursion so far.

    Validity needs ``gap_pct >= sufficient_gap_pct_by_tf[tf]`` (the §5.5 table: 3 % at 15m rising
    to 15 % at 3D+, four rows interpolated **[OUR CHOICE]**) **and**
    ``gap_atr >= sufficient_gap_atr_mult`` (default 2.0) when
    ``sufficient_gap_require_both_tests`` is true, otherwise the percentage test alone.
    """
    i = _norm_index(series, breakout_index)
    end = len(series) - 1 if end_index is None else _norm_index(series, end_index)
    mode = config.sufficient_gap_anchor
    tf_label = Timeframe.parse(tf).value if tf is not None else series.tf.value
    required_pct = dec(config.sufficient_gap_pct_by_tf.get(tf_label, 0.0))
    required_atr = dec(config.sufficient_gap_atr_mult)

    if mode == "zone_mid_to_close":
        if box is None:
            raise ValueError("sufficient_gap: sufficient_gap_anchor='zone_mid_to_close' needs box=")
        anchor = float(box.midpoint)
        extreme_index, extreme = i, float(series.close[i])
    else:
        if mode == "zone_top_to_extreme":
            if box is None:
                raise ValueError("sufficient_gap: sufficient_gap_anchor='zone_top_to_extreme' needs box=")
            anchor = float(box.top if direction is Direction.LONG else box.bottom)
        else:
            anchor = float(series.close[i])
        extreme_index, extreme = _extreme_before_retrace(series, i, end, direction, anchor,
                                                         config.sufficient_gap_retrace_cutoff)

    move = abs(extreme - anchor)
    atr = _atr_value(series, config, i)
    gap_pct = dec(move / abs(anchor) * 100.0) if anchor else _ZERO
    gap_atr = dec(move / atr) if atr > 0 else _ZERO

    reasons: list[str] = []
    if gap_pct < required_pct:
        reasons.append(f"gap {float(gap_pct):.2f}% < {float(required_pct):.2f}% required on {tf_label}")
    if config.sufficient_gap_require_both_tests and gap_atr < required_atr:
        reasons.append(f"gap {float(gap_atr):.2f} ATR < sufficient_gap_atr_mult {float(required_atr)}")
    return GapMeasure(dec(anchor), dec(extreme), extreme_index, gap_pct, gap_atr,
                      required_pct, required_atr, not reasons, tuple(reasons))


def _extreme_before_retrace(
    series: Series, start: int, end: int, direction: Direction, anchor: float, cutoff: float
) -> tuple[int, float]:
    best_i, best = start, anchor
    for i in range(start + 1, end + 1):
        # The retrace is judged against the excursion set by earlier bars, so the bar that makes
        # a new extreme is never penalised for its own opposite wick.  **[OUR CHOICE]**
        excursion = (best - anchor) if direction is Direction.LONG else (anchor - best)
        if excursion > 0:
            give_back = (best - float(series.low[i])) if direction is Direction.LONG \
                else (float(series.high[i]) - best)
            if give_back > cutoff * excursion:
                break
        if direction is Direction.LONG:
            hi = float(series.high[i])
            if hi > best:
                best, best_i = hi, i
        else:
            lo = float(series.low[i])
            if lo < best:
                best, best_i = lo, i
    return best_i, best


# =========================================================================== P11


def classify_trend(
    pivots: Sequence[SwingPoint], config: Config, *, at_index: int | None = None
) -> Trend:
    """**P11** — trend / regime classification (answers S3-A11, S5-A20, S7-A8).
    **[OUR CHOICE]** algorithm.

    Takes the last ``trend_pivot_count`` **confirmed** pivots (default 4) on the structure
    timeframe.  An uptrend needs the swing highs in that window strictly rising **and** the swing
    lows strictly rising; a downtrend is the mirror; anything else is ``NEUTRAL``.

    ``NEUTRAL`` is **not** counter-trend — CF-03's counter-trend handling only applies against a
    confirmed opposing trend.

    ``at_index`` applies the P1 no-lookahead filter first; pass the current bar in a backtest.
    Evaluate this on ``trend_timeframe`` (= ``structure_tf`` by default, CF-24) and **only** there.
    """
    usable = list(pivots) if at_index is None else confirmed_swings(pivots, at_index)
    usable.sort(key=lambda p: (p.bar_index, p.kind.value))
    window = usable[-config.trend_pivot_count:] if config.trend_pivot_count > 0 else usable
    highs = [p.price for p in window if p.kind is SwingKind.HIGH]
    lows = [p.price for p in window if p.kind is SwingKind.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return Trend.NEUTRAL
    rising = all(b > a for a, b in zip(highs, highs[1:])) and all(b > a for a, b in zip(lows, lows[1:]))
    falling = all(b < a for a, b in zip(highs, highs[1:])) and all(b < a for a, b in zip(lows, lows[1:]))
    if rising:
        return Trend.UP
    if falling:
        return Trend.DOWN
    return Trend.NEUTRAL


# =========================================================================== P12


def is_capitulation_wick(
    series: Series, config: Config, bar_index: int, side: Literal["upper", "lower"]
) -> bool:
    """**P12** — capitulation wick (TBOT1-R6, S6-R18, TBOT1-R22; answers S8-A17, TBOT1-A15).
    **[OUR CHOICE]** algorithm.

    All three tests must pass::

        wick_len >= capitulation_wick_atr * ATR                 (default 3.0)
        wick_len >= capitulation_wick_body_ratio * own_body      (default 3.0)
        volume   >= capitulation_volume_mult * median(volume,20) (default 2.0)

    Consumers must respect the TBOT1-C4 split: such a wick is **excluded as a stop anchor**
    (CF-14 falls back to the body / the next structure) but **permitted as an entry target**.

    The median volume window is the 20 bars ending at ``bar_index`` (fewer near the start of the
    series — **[OUR CHOICE]** warm-up behaviour).  A zero-body bar passes the ratio test.
    """
    i = _norm_index(series, bar_index)
    wick = float(series.upper_wick[i] if side == "upper" else series.lower_wick[i])
    if wick <= 0:
        return False
    atr = _atr_value(series, config, i)
    if atr <= 0 or wick < config.capitulation_wick_atr * atr:
        return False
    body = float(series.body_size[i])
    if body > 0 and wick < config.capitulation_wick_body_ratio * body:
        return False
    window = series.volume[max(0, i - 19): i + 1]
    med = float(np.median(window)) if len(window) else 0.0
    if med > 0 and float(series.volume[i]) < config.capitulation_volume_mult * med:
        return False
    return True


def capitulation_wicks(series: Series, config: Config) -> list[tuple[int, str]]:
    """**P12** applied to every bar; ``[(bar_index, "upper"|"lower")]`` in bar order."""
    out: list[tuple[int, str]] = []
    for i in range(len(series)):
        for side in ("upper", "lower"):
            if is_capitulation_wick(series, config, i, side):  # type: ignore[arg-type]
                out.append((i, side))
    return out


# =========================================================================== P13


@dataclass(frozen=True, slots=True)
class ConsolidationCheck:
    """Result of :func:`check_consolidation` (**P13**)."""

    horizontal: bool
    bars: int
    drift: Decimal          #: ``|slope per bar| * window_len`` in price
    drift_atr: Decimal
    height: Decimal
    height_atr: Decimal
    slope_per_bar: Decimal
    reasons: tuple[str, ...]


def check_consolidation(
    series: Series, config: Config, start_index: int, end_index: int
) -> ConsolidationCheck:
    """**P13** — "consolidates horizontally" (S5-R15, S5-R17; answers S5-A5, S6-A27).
    **[OUR CHOICE]** algorithm.

    Over the inclusive window::

        |linreg_slope(closes) * window_len| <= consolidation_max_drift_atr * ATR   (default 0.75)
        (window_high - window_low)          <= consolidation_max_height_atr * ATR  (default 2.0)
        window_len                          >= consolidation_min_bars              (default 2)

    This is what rejects the down-drifting "consolidations" he rejects by eye.  Window high/low
    are **wick** extremes: a consolidation that is quiet in bodies but violent in wicks is not
    horizontal.
    """
    lo = _norm_index(series, start_index)
    hi = _norm_index(series, end_index)
    if hi < lo:
        raise ValueError(f"check_consolidation: end_index {end_index} precedes start_index {start_index}")
    bars = hi - lo + 1
    closes = series.close[lo:hi + 1]
    x = np.arange(bars, dtype="float64")
    slope = float(np.polyfit(x, closes, 1)[0]) if bars >= 2 else 0.0
    drift = abs(slope) * bars
    height = float(series.high[lo:hi + 1].max() - series.low[lo:hi + 1].min())
    atr = _atr_value(series, config, hi)

    reasons: list[str] = []
    if bars < config.consolidation_min_bars:
        reasons.append(f"{bars} bars < consolidation_min_bars {config.consolidation_min_bars}")
    if atr <= 0:
        reasons.append("ATR is zero; cannot normalise drift or height")
    else:
        if drift > config.consolidation_max_drift_atr * atr:
            reasons.append(f"drift {drift / atr:.2f} ATR > consolidation_max_drift_atr "
                           f"{config.consolidation_max_drift_atr}")
        if height > config.consolidation_max_height_atr * atr:
            reasons.append(f"height {height / atr:.2f} ATR > consolidation_max_height_atr "
                           f"{config.consolidation_max_height_atr}")
    return ConsolidationCheck(
        horizontal=not reasons,
        bars=bars,
        drift=dec(drift),
        drift_atr=dec(drift / atr) if atr > 0 else _ZERO,
        height=dec(height),
        height_atr=dec(height / atr) if atr > 0 else _ZERO,
        slope_per_bar=dec(slope),
        reasons=tuple(reasons),
    )


def is_horizontal_consolidation(
    series: Series, config: Config, start_index: int, end_index: int
) -> bool:
    """**P13** boolean shorthand for :func:`check_consolidation`."""
    return check_consolidation(series, config, start_index, end_index).horizontal


# =========================================================================== P14


@dataclass(frozen=True, slots=True)
class ConfluenceObject:
    """One priced object offered to the P14 scorer.

    Detectors wrap their outputs in this: ``obj_class`` must be a
    :class:`~tbot.models.ConfluenceClass` value (the keys of ``config.confluence_weights``),
    ``source_ids`` carries the detector's rule IDs so the score is explainable.
    """

    id: str
    price: Decimal
    obj_class: str
    weight: Decimal | None = None      #: override; default is the §6.1 class weight
    tf: Timeframe | None = None
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfluenceResult:
    """Result of :func:`score_confluence` (**P14**)."""

    score: Decimal
    classes: frozenset[str]
    contributors: tuple[ConfluenceObject, ...]   #: the winning object per class
    merged: tuple[ConfluenceObject, ...]         #: everything inside the merge band
    qualified: bool
    bonus: Decimal
    unknown_classes: frozenset[str]
    reasons: tuple[str, ...]
    #: **Q5** — the *raw* deduplicated object count, which is what the entry gate compares to
    #: ``min_confluence_count`` under ``confluence_gate_mode = "raw_count"``.  With
    #: ``confluence_dedup_same_class`` on this equals ``len(classes)``.
    count: int = 0

    @property
    def gate_value(self) -> Decimal:
        """The number the gate actually tests — the raw count, or the weighted score."""
        return dec(self.count) if self._raw else self.score

    _raw: bool = False


def score_confluence(
    series: Series,
    config: Config,
    candidate_price: Decimal | float,
    objects: Iterable[ConfluenceObject],
    *,
    at_index: int | None = None,
    continuation_zone: bool = False,
) -> ConfluenceResult:
    """**P14** — confluence scoring and deduplication (CF-31, §6.2; answers S2-A14, S3-A22,
    S4-A11, S5-A13, S6-A14, S7 §10, S8-A15, TBOT1-A4/A5).  The weights are **OURS** (§6.1) and
    ``confluence_merge_atr`` is an **OUR number**.

    Objects within ``confluence_merge_atr * ATR`` (default 0.25) of ``candidate_price`` are
    grouped by class; with ``confluence_dedup_same_class`` (default true) each class contributes
    **once**, at its highest weight — three objects of one class are still one contribution.
    ``zone_continuation_confluence_bonus`` (+1.0) is added when ``continuation_zone`` is set
    (CF-10).

    Qualification (**Q5, derived**): under the shipped ``confluence_gate_mode = "raw_count"`` the
    gate is ``count >= min_confluence_count`` — a count of *deduplicated objects*, not a weighted
    sum.  He counts objects out loud ("one SR, two supply zone, three confluences", S8
    ``[00:53:41]``; "so three, that's why I'm taking this one here", S5 ``[01:05:33]``) and never
    assigns a class a number.  The §6.1 weight map survives as ``score``, which still drives
    ranking between candidate setups and the §6.3 conviction mapping — as a *gate* it silently
    rejected three-object stacks he demonstrably takes.  ``"weighted_score"`` restores the old
    behaviour for sweeps.  Either way ≥2 distinct classes are required while
    ``single_class_trade_forbidden`` (true) — never an OB alone, a fib alone, a pattern alone,
    an SFP alone or a trend line alone.

    Cross-market context (USDT.D / BTC.D / BVOL / beta parent) is a **veto only, weight 0**
    (TBOT1 §10, CF-35): never pass it in here as an object.

    Ties inside a class break toward the object that appears **first** in ``objects``, so callers
    control precedence (e.g. ``fib_loses_ties_to_sr`` is resolved before scoring, S6-R38).
    """
    band = float(atr_at(series, config, at_index)) * config.confluence_merge_atr
    anchor = float(dec(candidate_price))
    merged = [o for o in objects if abs(float(o.price) - anchor) <= band]

    weights = config.confluence_weights
    unknown: set[str] = set()
    by_class: dict[str, list[tuple[Decimal, ConfluenceObject]]] = {}
    for obj in merged:
        if obj.weight is not None:
            w = obj.weight
        elif obj.obj_class in weights:
            w = dec(weights[obj.obj_class])
        else:
            unknown.add(obj.obj_class)
            w = _ZERO
        by_class.setdefault(obj.obj_class, []).append((w, obj))

    contributors: list[ConfluenceObject] = []
    score = _ZERO
    for cls, entries in by_class.items():
        if config.confluence_dedup_same_class:
            best_w, best_obj = max(entries, key=lambda e: e[0])
            score += best_w
            contributors.append(best_obj)
        else:
            score += sum(w for w, _ in entries)
            contributors.extend(o for _, o in entries)

    bonus = dec(config.zone_continuation_confluence_bonus) if continuation_zone else _ZERO
    score += bonus

    # Q5: the raw, deduplicated object count.  With ``confluence_dedup_same_class`` on there is
    # exactly one contributor per class, so this is the "one SR, two supply zone, three" count.
    count = len(contributors)
    raw_gate = config.confluence_gate_mode == "raw_count"

    reasons: list[str] = []
    if raw_gate:
        if count < config.min_confluence_count:
            reasons.append(
                f"{count} confluence object(s) < min_confluence_count "
                f"{config.min_confluence_count} (Q5, confluence_gate_mode=raw_count)"
            )
    elif score < dec(config.min_confluence_count):
        reasons.append(f"score {score} < min_confluence_count {config.min_confluence_count}")
    if config.single_class_trade_forbidden and len(by_class) < 2:
        reasons.append(f"only {len(by_class)} confluence class(es); single_class_trade_forbidden")
    return ConfluenceResult(
        score=score,
        classes=frozenset(by_class),
        contributors=tuple(contributors),
        merged=tuple(merged),
        qualified=not reasons,
        bonus=bonus,
        unknown_classes=frozenset(unknown),
        reasons=tuple(reasons),
        count=count,
        _raw=raw_gate,
    )


# =========================================================================== P15


def ob_liquidity_taken_pct(
    series: Series,
    config: Config,
    box: Box,
    side: ZoneSide,
    *,
    from_index: int,
    to_index: int | None = None,
) -> Decimal:
    """**P15** — "liquidity taken" from an order block (S7-R3, S7-A2).  **[OUR CHOICE]**.

    Percentage of the OB candle's **body range** that price has traded through since the OB
    formed, measured from the OB's outer edge inward using the **deepest wick** penetration
    (``ob_liquidity_measure = "deepest_wick_through_body_range"``).

    Used **only** when ``zone_fill_invalidation_pct`` is set to the S7 values (70/80); with the
    default 50 the ordinary P6 fill rule governs an order block exactly as it governs a zone.
    Note ``side`` is expressed in zone terms: a **bullish** OB is demand, a **bearish** OB supply.
    """
    depth = float(box.height)
    start = _norm_index(series, from_index) + 1
    end = len(series) - 1 if to_index is None else _norm_index(series, to_index)
    if depth <= 0 or start > end:
        return _ZERO
    if side is ZoneSide.DEMAND:
        penetration = float(box.top) - float(series.low[start:end + 1].min())
    else:
        penetration = float(series.high[start:end + 1].max()) - float(box.bottom)
    return dec(max(0.0, min(penetration / depth, 1.0)) * 100.0)


# =========================================================================== P16


def _boundary_offset(config: Config) -> timedelta:
    hh, _, mm = config.day_boundary_utc.partition(":")
    return timedelta(hours=int(hh), minutes=int(mm))


def day_start(ts: datetime, config: Config) -> datetime:
    """**P16** — the start of the trading day containing ``ts`` (CF-45; answers S2-A23, S5-A17).

    ``day_boundary_utc`` (default ``"00:00"``, the alternative being ``"01:00"`` for his literal
    17:00 PST) keys daily candle construction, the Monday range (S5-R8/R9), the two-loss-per-day
    counter (S2-R21) and the challenge-account period (S2-R23).  Flagged as open question Q13.
    """
    ts = _as_utc(ts)
    offset = _boundary_offset(config)
    anchored = ts - offset
    return anchored.replace(hour=0, minute=0, second=0, microsecond=0) + offset


def week_start(ts: datetime, config: Config) -> datetime:
    """**P16** — Monday ``day_boundary_utc`` of the week containing ``ts``."""
    d0 = day_start(ts, config)
    return d0 - timedelta(days=d0.weekday())


def is_weekend(ts: datetime, config: Config) -> bool:
    """**P16** — weekend window: Saturday ``day_boundary_utc`` → Monday ``day_boundary_utc``.

    Consumed by gate G4 with ``weekend_mode`` (default ``"leverage_blocked"``, CF-39).
    """
    ts = _as_utc(ts)
    week = week_start(ts, config)
    return ts >= week + timedelta(days=5)


def same_session(a: datetime, b: datetime, config: Config) -> bool:
    """**P16** — do two timestamps fall in the same ``day_boundary_utc`` day?"""
    return day_start(a, config) == day_start(b, config)


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC (SPEC.md §2)")
    return ts.astimezone(timezone.utc)


# =========================================================================== P17


def is_stale_trade(
    config: Config,
    *,
    bars_in_trade: int,
    mfe_atr: Decimal | float,
    mae_atr: Decimal | float,
    tps_hit: int,
) -> bool:
    """**P17** — "immediate reaction" / stale trade (CF-30; answers S6-A17, S4-A4).
    **[OUR CHOICE]**, and **off by default**::

        stale = bars_in_trade >= stale_exit_bars           (8)
                AND mfe < reaction_threshold_atr * ATR     (0.75)
                AND mae >= stale_exit_mae_atr * ATR        (1.0)
                AND tps_hit == 0

    Always returns ``False`` while ``stale_exit_enabled`` is false (the shipped default) — no
    number for this exists anywhere in the corpus.  Inputs are already ATR-normalised
    (``Position.mfe_atr`` / ``Position.mae_atr``).
    """
    if not config.stale_exit_enabled:
        return False
    return (
        bars_in_trade >= config.stale_exit_bars
        and float(mfe_atr) < config.reaction_threshold_atr
        and float(mae_atr) >= config.stale_exit_mae_atr
        and tps_hit == 0
    )


# =========================================================================== P18


@dataclass(frozen=True, slots=True)
class LiquidityScreen:
    """Result of :func:`liquidity_screen` (**P18**)."""

    passes: bool
    tier: Literal["A", "B"]        #: B = demoted to spot-only, never excluded (CF-40)
    wick_heavy: bool
    median_quote_volume_usd: Decimal
    median_wick_ratio: Decimal
    wicky_bar_fraction: Decimal
    reasons: tuple[str, ...]


def liquidity_screen(
    series: Series,
    config: Config,
    *,
    median_quote_volume_usd: Decimal | float | None = None,
    lookback_bars: int = 200,
) -> LiquidityScreen:
    """**P18** — illiquidity / barcoding / wick-heavy screen (S6-R45, S7-R38, CF-40; answers
    S2-A20, S7-A24, S8-A13).  **[OUR CHOICE]** thresholds.

    Fails when any of::

        median_30d_quote_volume_usd < min_daily_volume_usd            (50e6, floor is OURS)
        median(total_wick / bar_range, last 200 bars) > max_median_wick_ratio   (0.55)
        fraction(bars where total_wick > 2 * body)     > max_wicky_bar_fraction (0.40)

    **A failing symbol is DEMOTED to spot-only (Tier B), not excluded.**  The ``wick_heavy`` flag
    is what ``dca_size_split_wick_heavy_2`` consumes (S6-R27).

    ``median_quote_volume_usd`` should be the caller's true 30-day median; when omitted it is
    estimated from this series' ``quote_volume`` scaled to a day by the timeframe
    (**[OUR CHOICE]** convenience for tests and offline runs).
    """
    n = len(series)
    if n == 0:
        return LiquidityScreen(False, "B", True, _ZERO, _ZERO, _ZERO, ("empty series",))
    window = slice(max(0, n - lookback_bars), n)
    rng = series.bar_range[window]
    total_wick = series.upper_wick[window] + series.lower_wick[window]
    body = series.body_size[window]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(rng > 0, total_wick / np.where(rng > 0, rng, 1.0), 0.0)
    median_ratio = float(np.median(ratio)) if len(ratio) else 0.0
    wicky_fraction = float(np.mean(total_wick > 2.0 * body)) if len(body) else 0.0

    if median_quote_volume_usd is None:
        bars_per_day = max(1.0, 1440.0 / series.tf.minutes)
        median_quote_volume_usd = float(np.median(series.quote_volume[window])) * bars_per_day
    mq = dec(median_quote_volume_usd)

    reasons: list[str] = []
    if float(mq) < config.min_daily_volume_usd:
        reasons.append(f"median 30d quote volume {float(mq):,.0f} USD < min_daily_volume_usd "
                       f"{config.min_daily_volume_usd:,}")
    if median_ratio > config.max_median_wick_ratio:
        reasons.append(f"median wick ratio {median_ratio:.2f} > max_median_wick_ratio "
                       f"{config.max_median_wick_ratio}")
    if wicky_fraction > config.max_wicky_bar_fraction:
        reasons.append(f"wicky bar fraction {wicky_fraction:.2f} > max_wicky_bar_fraction "
                       f"{config.max_wicky_bar_fraction}")
    passes = not reasons
    return LiquidityScreen(
        passes=passes,
        tier="A" if passes else "B",
        wick_heavy=(median_ratio > config.max_median_wick_ratio
                    or wicky_fraction > config.max_wicky_bar_fraction),
        median_quote_volume_usd=mq,
        median_wick_ratio=dec(median_ratio),
        wicky_bar_fraction=dec(wicky_fraction),
        reasons=tuple(reasons),
    )


# =========================================================================== P19


def stop_buffer(series: Series, config: Config, at_index: int | None = None) -> Decimal:
    """**P19** — stop buffer: ``stop_buffer_atr * ATR(atr_period)`` beyond the chosen anchor
    (CF-14; answers S2-A8, S4-A5, TBOT1-A14).  Default 0.15 ATR — an **OUR number**: he never
    gives a buffer, and his own worked example "almost got wicked".

    This is the **fallback** buffer, for stops that are *not* anchored to a zone (levels, SFPs,
    structure breaks) and for the CF-06 step-1 LTF re-anchor.  A stop placed against a zone uses
    :func:`stop_buffer_zone` instead (**F6**).
    """
    return dec(float(atr_at(series, config, at_index)) * config.stop_buffer_atr)


def stop_buffer_zone(config: Config, zone_height: Decimal | float) -> Decimal:
    """**P19b / F6** — stop buffer for a stop placed against a **zone**:
    ``stop_buffer_zone_fraction * zone_height``, beyond the zone's far edge.

    Three pass-2 frames — TBOT1 4:11 (BTCUSDT.P 1H), TBOT1 1:09:19 (OMUSDT.P 1H), S8 1:28:33
    (SOLUSDT.P 4H) — put the stop **0.48 / 0.49 / 0.58** zone-heights below the zone bottom.  The
    same three stops are **0.66 % / 2.70 % / 0.81 %** of entry, i.e. the fraction clusters and the
    price percentage does not: the stable parameterisation is *fraction of zone height*, not a
    price percentage and not an ATR multiple.  Default 0.5, sweep 0.45–0.60.
    """
    h = dec(zone_height)
    if h < 0:
        h = -h
    return dec(config.stop_buffer_zone_fraction) * h


def apply_stop_buffer(
    anchor_price: Decimal | float, direction: Direction, buffer: Decimal | float
) -> Decimal:
    """**P19** — place the stop ``buffer`` beyond ``anchor_price``: below for a long, above for a
    short.  The anchor itself comes from CF-14 (swing wick, zone edge, level), **excluding**
    capitulation wicks (P12, TBOT1-R6).
    """
    price, buf = dec(anchor_price), dec(buffer)
    return price - buf if direction is Direction.LONG else price + buf


# =========================================================================== P20


@dataclass(frozen=True, slots=True)
class PMTResult:
    """Result of :func:`points_of_most_touch` (**P20**)."""

    price: Decimal                    #: the entry price — centre of the winning bin
    bin_width: Decimal
    bin_centres: tuple[Decimal, ...]
    counts: tuple[int, ...]
    winning_bin: int


def points_of_most_touch(
    series: Series,
    config: Config,
    box: Box,
    side: ZoneSide,
    windows: Sequence[tuple[int, int]],
    *,
    at_index: int | None = None,
) -> PMTResult:
    """**P20** — "points of most touch": the entry price inside a zone (S4-R4, S5-R20, S5-R23,
    S7-R18, S5-A15).  **[OUR CHOICE]** algorithm.

    A histogram of bar-price intersections at ``pmt_bin_atr * ATR`` resolution (default 0.05 ATR)
    across the zone's formation window **plus every subsequent touch window** — pass all of them
    in ``windows`` as inclusive ``(start_index, end_index)`` pairs.  A bar contributes to every
    bin its ``[low, high]`` range intersects.

    The entry is the centre of the fullest bin; ties break toward the bin nearest the zone's
    **outer edge** — ``box_top`` for demand, ``box_bottom`` for supply — because that is where his
    lightest "entry at the SR point" sits.
    """
    if not windows:
        raise ValueError("points_of_most_touch: at least one (start, end) window is required")
    atr = float(atr_at(series, config, at_index))
    depth = float(box.height)
    width = max(atr * config.pmt_bin_atr, 1e-12)
    n_bins = max(1, int(round(depth / width))) if depth > 0 else 1
    width = depth / n_bins if depth > 0 else width
    bottom = float(box.bottom)
    counts = [0] * n_bins

    for start, end in windows:
        lo = _norm_index(series, start)
        hi = _norm_index(series, end)
        for i in range(lo, hi + 1):
            bar_lo, bar_hi = float(series.low[i]), float(series.high[i])
            if bar_hi < bottom or bar_lo > bottom + depth:
                continue
            first = max(0, int((max(bar_lo, bottom) - bottom) // width))
            last = min(n_bins - 1, int((min(bar_hi, bottom + depth) - bottom) // width))
            for b in range(first, last + 1):
                counts[b] += 1

    best = max(counts)
    tied = [b for b, c in enumerate(counts) if c == best]
    outer_bin = n_bins - 1 if side is ZoneSide.DEMAND else 0
    winner = min(tied, key=lambda b: (abs(b - outer_bin), b))
    centres = tuple(dec(bottom + (b + 0.5) * width) for b in range(n_bins))
    return PMTResult(
        price=centres[winner],
        bin_width=dec(width),
        bin_centres=centres,
        counts=tuple(counts),
        winning_bin=winner,
    )
