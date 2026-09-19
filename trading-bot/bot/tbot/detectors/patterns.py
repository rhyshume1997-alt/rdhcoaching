"""tbot.detectors.patterns — SPEC.md §5.10: the chart-pattern library (pipeline stage 11).

Ships **disabled** (``module_chart_patterns_enabled = false``, CF-37) because he disowns trading
patterns himself.  Even when enabled it is **confluence-only** and can never be the sole reason
for a trade (S4-R38, PL-4).  Pattern objects still score while the module is off
(``disowned_modules_still_score_confluence = true``) — both of those keys belong to
``pipeline.py`` and are deliberately not read here; this module emits objects, nothing more.

Every pattern has two mandatory halves
--------------------------------------
1. **Geometry + a measured move.**  The measured target is *theoretical* (S4 ``[00:53:25]``,
   S5-R39): real take-profits go at intervening structural levels, which is ``planner.py``'s job.
   Each :class:`Pattern` therefore carries ``measured_target_is_theoretical = True``.
2. **The trigger: breakout/breakdown + retest + close/hold** (S4-R19, CF-16 flip-pending family).
   Naked breakouts are explicitly the riskiest option and are excluded, and limit orders must not
   be pre-placed at the line before the flip.  ``Pattern.confirmed`` is false and
   ``entry_price`` is ``None`` until the retest holds; the stop then sits just beyond the flipped
   level (P19 buffer).  The retest must happen on the timeframe the pattern was drawn on (S4-R29,
   PL-8) — pass the series the pattern was drawn on and nothing else.

Falling wedge vs bull flag — his "steep vs tight" eyeball, quantified
--------------------------------------------------------------------
S4-R23 is the classification rule in his own words: *steep + break of market structure (lower
lows / lower highs) = falling wedge; tight consolidation with no structure break = bull flag;
parallel (non-converging) lines = channel, not a wedge.*  :func:`classify_consolidation` replaces
each of the three eyeball terms with a measurement:

* **"tight"** → P13 :func:`~tbot.primitives.check_consolidation` passes: the linreg drift over the
  window is within ``consolidation_max_drift_atr`` and the window height within
  ``consolidation_max_height_atr``.  **"steep"** is simply the negation — P13 failing on drift.
  The thresholds are read *through* P13, never off ``Config`` (they belong to ``zones.py``).
* **"break of market structure"** → the window's own P1 pivots print both lower lows **and**
  lower highs (mirrored for a rising wedge).  This is S4-R23's own parenthetical, evaluated as
  pivot geometry; it is not the CF-22 body-close MSB event and does not call ``structure.py``.
* **"converging" vs "parallel"** → fit a line through the window's swing highs and another
  through its swing lows; the boundaries converge when the width at the end of the window is at
  most :data:`WEDGE_CONVERGENCE_RATIO` of the width at its start.  Anything wider is a channel.

A window too short for P13's ``consolidation_min_bars`` is ``"too_small"`` and is treated as plain
S/R instead of a pattern (S4 ``[01:03:29]``, S4-A17).

Config keys read here (owned by this module per INTERFACES.md §7): ``cup_handle_floor_pct``,
``pattern_pole_anchor``.  Everything else — ATR, tolerance bands, consolidation thresholds,
directional-change thresholds, the stop buffer — is reached through the primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Sequence

from .. import primitives as P
from ..config import Config
from ..models import Direction, Level, Series, SwingKind, SwingPoint, Timeframe, dec
from .base import object_id

__all__ = [
    "WEDGE_CONVERGENCE_RATIO",
    "WEDGE_MAX_PIVOTS",
    "_wedge_window",
    "Pattern",
    "BreakoutRetest",
    "ConsolidationVerdict",
    "classify_consolidation",
    "confirm_breakout_retest",
    "find_flags",
    "find_wedges_and_channels",
    "find_double_tops_bottoms",
    "find_cup_and_handle",
    "find_head_and_shoulders",
    "find_quasimodo",
    "PatternDetector",
]

#: **[OUR CHOICE]** — sweep target.  Boundary lines "converge" when the width at the end of the
#: window is at most this fraction of the width at its start; wider than that is a parallel
#: channel, not a wedge (S4-R23 gives the distinction but no number, and §11 names none).
WEDGE_CONVERGENCE_RATIO = Decimal("0.75")

#: **[OUR CHOICE]** — sweep target.  A wedge is drawn on a handful of swings, so the window is the
#: first this many confirmed pivots after the impulse.  Without a cap the boundary fit would grow
#: to the end of the series and stop describing a wedge at all; S4 gives no pivot count.
WEDGE_MAX_PIVOTS = 6

#: Patterns he describes but does not play, kept here so the omission is explicit rather than an
#: oversight: the trend-line inverse head and shoulders is valid only against a downtrend line and
#: "he does not play them at all" (S5-R41), so it is never emitted.
NOT_IMPLEMENTED_PATTERNS = ("trendline_inverse_head_and_shoulders",)

PatternKind = Literal[
    "bull_flag",
    "bear_flag",
    "falling_wedge",
    "rising_wedge",
    "rising_channel",
    "cup_and_handle",
    "head_and_shoulders",
    "inverse_head_and_shoulders",
    "bearish_quasimodo",
    "double_top",
    "double_bottom",
]


# --------------------------------------------------------------------------- records


@dataclass(frozen=True, slots=True)
class Pattern:
    """One chart pattern.

    ``trigger_price`` is the line that must break: a flag boundary, a wedge boundary or a
    neckline.  ``confirmed`` means breakout **and** retest happened (S4-R19); until then
    ``entry_price`` and ``stop_price`` are ``None`` and the object is confluence only.
    ``measured_target`` is the S4 measured move — theoretical by construction.
    """

    id: str
    symbol: str
    tf: Timeframe
    kind: PatternKind
    direction: Direction | None            #: ``None`` for a neutral pattern (rising channel)
    start_index: int
    end_index: int
    completion_index: int
    pivot_indices: tuple[int, ...]
    trigger_price: Decimal
    measured_move: Decimal | None
    measured_target: Decimal | None
    breakout_index: int | None = None
    retest_index: int | None = None
    confirmed: bool = False
    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    invalidation_price: Decimal | None = None
    measured_target_is_theoretical: bool = True
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @property
    def confluence_price(self) -> Decimal:
        """Where the pattern scores: the line that defines it."""
        return self.trigger_price


@dataclass(frozen=True, slots=True)
class BreakoutRetest:
    """Result of :func:`confirm_breakout_retest` — the S4-R19 trigger, in three parts."""

    breakout_index: int | None
    retest_index: int | None
    confirmed: bool
    entry_price: Decimal | None
    stop_price: Decimal | None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConsolidationVerdict:
    """Result of :func:`classify_consolidation` — S4-R23 made numeric."""

    kind: Literal["flag", "wedge", "channel", "too_small", "unclassified"]
    tight: bool                     #: P13 horizontality — his "tight"
    steep: bool                     #: P13 failed on drift — his "steep"
    structure_break: bool           #: lower lows *and* lower highs (mirrored for a rising wedge)
    converging: bool
    parallel: bool
    drift_atr: Decimal
    height_atr: Decimal
    width_start: Decimal
    width_end: Decimal
    reasons: tuple[str, ...]


# --------------------------------------------------------------------------- shared helpers


def _pivots_in(
    pivots: Sequence[SwingPoint], start: int, end: int, kind: SwingKind | None = None
) -> list[SwingPoint]:
    return [
        p
        for p in pivots
        if start <= p.bar_index <= end and (kind is None or p.kind is kind)
    ]


def _line_through(points: Sequence[SwingPoint]) -> tuple[Decimal, Decimal] | None:
    """Least-squares line ``(slope_per_bar, value_at_bar_0)`` through pivot prices.

    ``None`` when fewer than two pivots — a boundary needs two points, which is also why a wedge
    cannot be called on a window with only one swing high or one swing low.
    """
    if len(points) < 2:
        return None
    n = Decimal(len(points))
    xs = [Decimal(p.bar_index) for p in points]
    ys = [p.price for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return Decimal(0), mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    return slope, mean_y - slope * mean_x


def _at(line: tuple[Decimal, Decimal], bar_index: int) -> Decimal:
    slope, intercept = line
    return intercept + slope * Decimal(bar_index)


def _wedge_window(
    pivots: Sequence[SwingPoint], falling: bool, limit: int = WEDGE_MAX_PIVOTS
) -> list[SwingPoint]:
    """The pivots a wedge is drawn on: the run that keeps its direction, capped at ``limit``.

    A falling wedge is a sequence of lower highs and lower lows (S4-R23), so the window ends at
    the first swing **high** that prints above its predecessor — that pivot is the break, not part
    of the wedge.  A rising wedge ends at the first swing **low** below its predecessor.  Without
    this the boundary fit would swallow the breakout leg and stop describing a wedge at all.
    """
    window: list[SwingPoint] = []
    last_high: Decimal | None = None
    last_low: Decimal | None = None
    for pivot in pivots:
        if falling and pivot.kind is SwingKind.HIGH and last_high is not None and pivot.price > last_high:
            break
        if not falling and pivot.kind is SwingKind.LOW and last_low is not None and pivot.price < last_low:
            break
        window.append(pivot)
        if pivot.kind is SwingKind.HIGH:
            last_high = pivot.price
        else:
            last_low = pivot.price
        if len(window) >= limit:
            break
    return window


def _lower_lows_and_lower_highs(pivots: Sequence[SwingPoint], falling: bool) -> bool:
    """S4-R23's parenthetical: does the window contain a break of market structure?

    ``falling=True`` asks for lower lows **and** lower highs (the falling-wedge case);
    ``falling=False`` for higher highs and higher lows (the rising-wedge mirror).  Pure P1 pivot
    geometry — the CF-22 body-close MSB event lives in ``structure.py`` and is a different object.
    """
    highs = [p.price for p in pivots if p.kind is SwingKind.HIGH]
    lows = [p.price for p in pivots if p.kind is SwingKind.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return False
    if falling:
        return highs[-1] < highs[0] and lows[-1] < lows[0]
    return highs[-1] > highs[0] and lows[-1] > lows[0]


def _consolidation_window(series: Series, config: Config, start: int) -> int | None:
    """The longest window beginning at ``start`` that P13 still calls horizontal.

    Growing stops at the first bar that breaks horizontality once a valid window exists.  While
    the window is merely *too short*, P13 says so in ``reasons`` and the scan keeps extending —
    that is how ``consolidation_min_bars`` is honoured without reading ``zones.py``'s key.
    """
    best: int | None = None
    for end in range(start, len(series)):
        check = P.check_consolidation(series, config, start, end)
        if check.horizontal:
            best = end
            continue
        if best is not None:
            break
        if any("consolidation_min_bars" in r for r in check.reasons):
            continue
        break
    return best


def confirm_breakout_retest(
    series: Series,
    config: Config,
    trigger_price: Decimal,
    direction: Direction,
    from_index: int,
    *,
    retest_timeout_bars: int | None = None,
) -> BreakoutRetest:
    """S4-R19: breakout/breakdown → retest → close/hold, then enter with the stop beyond the line.

    The breakout is a **body close** beyond ``trigger_price``.  The retest is a later bar whose
    range re-enters the P9 tolerance band around the line *and* whose close holds on the new side
    — the broken resistance closing as support, or the reverse.  The entry is that retest bar's
    close and the stop is ``trigger_price`` plus the P19 buffer on the far side.

    ``retest_timeout_bars`` bounds the wait; ``None`` scans to the end of the series, which is the
    honest default because S4 gives the pattern retest no deadline (``msb_retest_timeout_bars``
    is ``structure.py``'s key and governs MSBs, not patterns).
    """
    breakout: int | None = None
    for j in range(from_index + 1, len(series)):
        close = dec(series.close[j])
        if direction is Direction.LONG and close > trigger_price:
            breakout = j
            break
        if direction is Direction.SHORT and close < trigger_price:
            breakout = j
            break
    if breakout is None:
        return BreakoutRetest(None, None, False, None, None, ("no body close through the pattern line (S4-R19)",))

    last = len(series) - 1 if retest_timeout_bars is None else min(breakout + retest_timeout_bars, len(series) - 1)
    for j in range(breakout + 1, last + 1):
        if not P.bar_at_level(series, config, trigger_price, j):
            continue
        close = dec(series.close[j])
        holds = close >= trigger_price if direction is Direction.LONG else close <= trigger_price
        if not holds:
            continue
        buffer = P.stop_buffer(series, config, j)
        return BreakoutRetest(
            breakout_index=breakout,
            retest_index=j,
            confirmed=True,
            entry_price=close,
            stop_price=P.apply_stop_buffer(trigger_price, direction, buffer),
            reasons=(),
        )
    return BreakoutRetest(
        breakout_index=breakout,
        retest_index=None,
        confirmed=False,
        entry_price=None,
        stop_price=None,
        reasons=("breakout without a holding retest; naked breakouts are excluded (S4-R19)",),
    )


def _pattern(
    series: Series,
    kind: PatternKind,
    *,
    direction: Direction | None,
    start: int,
    end: int,
    pivots: Sequence[int],
    trigger: Decimal,
    move: Decimal | None,
    target: Decimal | None,
    trigger_result: BreakoutRetest | None,
    invalidation: Decimal | None,
    source_ids: Sequence[str],
    ordinal: int = 0,
    extra_reasons: Sequence[str] = (),
) -> Pattern:
    br = trigger_result or BreakoutRetest(None, None, False, None, None, ())
    completion = br.retest_index if br.retest_index is not None else (br.breakout_index if br.breakout_index is not None else end)
    return Pattern(
        id=object_id(series, kind, completion, ordinal),
        symbol=series.symbol,
        tf=series.tf,
        kind=kind,
        direction=direction,
        start_index=start,
        end_index=end,
        completion_index=completion,
        pivot_indices=tuple(pivots),
        trigger_price=trigger,
        measured_move=move,
        measured_target=target,
        breakout_index=br.breakout_index,
        retest_index=br.retest_index,
        confirmed=br.confirmed,
        entry_price=br.entry_price,
        stop_price=br.stop_price,
        invalidation_price=invalidation,
        reasons=tuple(br.reasons) + tuple(extra_reasons),
        source_ids=tuple(source_ids),
    )


# --------------------------------------------------------------------------- S4-R23


def classify_consolidation(
    series: Series,
    config: Config,
    start_index: int,
    end_index: int,
    *,
    impulse: Direction,
    pivots: Sequence[SwingPoint] | None = None,
) -> ConsolidationVerdict:
    """S4-R23 quantified: is this window a **flag**, a **wedge**, or a **channel**?

    ``impulse`` is the direction of the leg that led into the window — a bull flag / falling wedge
    follows an up impulse, a bear flag / rising wedge a down one.  See the module docstring for
    what replaces each of his three eyeball terms.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    window = _pivots_in(all_pivots, start_index, end_index)
    check = P.check_consolidation(series, config, start_index, end_index)
    reasons: list[str] = list(check.reasons)

    if any("consolidation_min_bars" in r for r in check.reasons):
        return ConsolidationVerdict(
            kind="too_small",
            tight=False,
            steep=False,
            structure_break=False,
            converging=False,
            parallel=False,
            drift_atr=check.drift_atr,
            height_atr=check.height_atr,
            width_start=Decimal(0),
            width_end=Decimal(0),
            reasons=tuple(reasons) + ("too small for a pattern; treat as plain S/R (S4-A17)",),
        )

    tight = check.horizontal
    steep = any("consolidation_max_drift_atr" in r for r in check.reasons)
    falling = impulse is Direction.LONG
    structure_break = _lower_lows_and_lower_highs(window, falling=falling)

    upper = _line_through(_pivots_in(window, start_index, end_index, SwingKind.HIGH))
    lower = _line_through(_pivots_in(window, start_index, end_index, SwingKind.LOW))
    width_start = width_end = Decimal(0)
    converging = parallel = False
    if upper is None or lower is None:
        reasons.append("fewer than two swing highs or lows in the window; boundaries undefined")
    else:
        width_start = _at(upper, start_index) - _at(lower, start_index)
        width_end = _at(upper, end_index) - _at(lower, end_index)
        if width_start > 0:
            converging = Decimal(0) < width_end <= WEDGE_CONVERGENCE_RATIO * width_start
            parallel = not converging
        else:
            reasons.append("degenerate boundary width at the window start")

    if tight and not structure_break:
        kind: Literal["flag", "wedge", "channel", "too_small", "unclassified"] = "flag"
    elif steep and structure_break and converging:
        kind = "wedge"
    elif parallel:
        kind = "channel"
        reasons.append("parallel lines => channel, not a wedge (S4-R23)")
    else:
        kind = "unclassified"
        reasons.append("neither a tight flag nor a steep converging wedge (S4-R23)")

    return ConsolidationVerdict(
        kind=kind,
        tight=tight,
        steep=steep,
        structure_break=structure_break,
        converging=converging,
        parallel=parallel,
        drift_atr=check.drift_atr,
        height_atr=check.height_atr,
        width_start=width_start,
        width_end=width_end,
        reasons=tuple(reasons),
    )


# --------------------------------------------------------------------------- flags


def _impulse_legs(
    series: Series, config: Config, pivots: Sequence[SwingPoint]
) -> list[tuple[SwingPoint, SwingPoint, Direction]]:
    """Pivot legs that P2 also calls a directional change — the flag poles.

    A leg is a confirmed swing low → later swing high (up impulse) or the mirror.  It counts as an
    impulse only when :func:`~tbot.primitives.find_directional_changes` produced an event whose
    extreme is that leg's terminal pivot, so the "is this move big enough" question stays with P2
    (``dir_change_atr``) instead of being re-answered here.
    """
    dcs = P.find_directional_changes(series, config)
    up_extremes = {d.extreme_index for d in dcs if d.direction is Direction.LONG}
    down_extremes = {d.extreme_index for d in dcs if d.direction is Direction.SHORT}
    out: list[tuple[SwingPoint, SwingPoint, Direction]] = []
    for first, second in zip(pivots, pivots[1:]):
        if first.kind is second.kind:
            continue
        if first.kind is SwingKind.LOW and second.price > first.price:
            if any(abs(e - second.bar_index) <= second.k for e in up_extremes):
                out.append((first, second, Direction.LONG))
        elif first.kind is SwingKind.HIGH and second.price < first.price:
            if any(abs(e - second.bar_index) <= second.k for e in down_extremes):
                out.append((first, second, Direction.SHORT))
    return out


def find_flags(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    retest_timeout_bars: int | None = None,
) -> list[Pattern]:
    """Bull and bear flags (S4-R17, S4-R18, S4-R23, S5-R39).

    Pole = the impulse selected by ``pattern_pole_anchor`` (``"most_recent_impulse"`` by default —
    **[OUR CHOICE]**; he says outright there is no wrong impulse to take it from, S4-C6, S4-A21).
    Flag = the window straight after the pole that :func:`classify_consolidation` calls a *flag*:
    tight, no structure break, and sloping flat or **against** the impulse.

    Measured target: the pole copied to the **base** of the flag for a bull flag (S4-R17), and to
    the **top** of the flag projected down for a bear flag (S4-R18).  Trigger: a close through the
    flag boundary plus the retest (S4-R19).  A break above a bear flag invalidates it (S4-R28),
    and the mirror for a bull flag — recorded as ``invalidation_price``.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    legs = _impulse_legs(series, config, all_pivots)
    if not legs:
        return []
    if config.pattern_pole_anchor == "first_impulse":
        legs = legs[:1] + [lg for lg in legs[1:] if False]
    out: list[Pattern] = []
    per_bar: dict[int, int] = {}
    seen: set[tuple[int, int]] = set()

    ordered = legs if config.pattern_pole_anchor == "first_impulse" else list(reversed(legs))
    for start_pivot, end_pivot, direction in ordered:
        window_start = end_pivot.bar_index + 1
        if window_start >= len(series):
            continue
        window_end = _consolidation_window(series, config, window_start)
        if window_end is None or (window_start, window_end) in seen:
            continue
        seen.add((window_start, window_end))
        verdict = classify_consolidation(
            series, config, window_start, window_end, impulse=direction, pivots=all_pivots
        )
        if verdict.kind != "flag":
            continue
        slope = P.check_consolidation(series, config, window_start, window_end).slope_per_bar
        if direction is Direction.LONG and slope > 0:
            continue        # a bull flag slopes flat or against the impulse (S4-R23)
        if direction is Direction.SHORT and slope < 0:
            continue

        pole = abs(end_pivot.price - start_pivot.price)
        flag_top = dec(series.high[window_start:window_end + 1].max())
        flag_base = dec(series.low[window_start:window_end + 1].min())
        if direction is Direction.LONG:
            kind: PatternKind = "bull_flag"
            trigger, target, invalidation = flag_top, flag_base + pole, flag_base
        else:
            kind = "bear_flag"
            trigger, target, invalidation = flag_base, flag_top - pole, flag_top
        br = confirm_breakout_retest(
            series, config, trigger, direction, window_end,
            retest_timeout_bars=retest_timeout_bars,
        )
        anchor = br.retest_index if br.retest_index is not None else (br.breakout_index or window_end)
        n = per_bar.get(anchor, 0)
        per_bar[anchor] = n + 1
        out.append(
            _pattern(
                series, kind, direction=direction, start=start_pivot.bar_index, end=window_end,
                pivots=(start_pivot.bar_index, end_pivot.bar_index),
                trigger=trigger, move=pole, target=target, trigger_result=br,
                invalidation=invalidation, ordinal=n,
                source_ids=(
                    "S4-R17" if direction is Direction.LONG else "S4-R18",
                    "S4-R19", "S4-R23", "S5-R39", "P2", "P13",
                    "pattern_pole_anchor=" + config.pattern_pole_anchor,
                ),
            )
        )
    return out


# --------------------------------------------------------------------------- wedges / channels


def find_wedges_and_channels(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    retest_timeout_bars: int | None = None,
) -> list[Pattern]:
    """Falling / rising wedges and the neutral rising channel (S4-R21, S4-R22, S8 ``[01:11:44]``).

    A wedge window is the stretch after an impulse that :func:`classify_consolidation` calls a
    *wedge*: steep, containing a structure break, and with converging boundaries.  Parallel
    boundaries make it a **rising channel** instead — neutral, neither bullish nor bearish, with
    **no** measured target.

    Measured targets: the falling wedge measures bottom trend line → top trend line **at the
    wedge's origin** and places that distance at the breakout point (S4-R21); the rising wedge
    measures top → bottom and places it at the breakdown point (S4-R22).  A rising wedge is valid
    only when price arrived into it **from below** (S4-R22) — the bar before the window must sit
    under the lower boundary.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    legs = _impulse_legs(series, config, all_pivots)
    out: list[Pattern] = []
    per_bar: dict[int, int] = {}
    seen: set[int] = set()

    for _, end_pivot, direction in legs:
        start = end_pivot.bar_index + 1
        if start >= len(series) - 1 or start in seen:
            continue
        seen.add(start)
        window = _wedge_window(
            _pivots_in(all_pivots, start, len(series) - 1), falling=direction is Direction.LONG
        )
        if not window:
            continue
        end = max(p.bar_index for p in window)
        if end <= start:
            continue
        verdict = classify_consolidation(
            series, config, start, end, impulse=direction, pivots=all_pivots
        )
        upper = _line_through(_pivots_in(all_pivots, start, end, SwingKind.HIGH))
        lower = _line_through(_pivots_in(all_pivots, start, end, SwingKind.LOW))
        if upper is None or lower is None:
            continue
        width_at_origin = verdict.width_start

        if verdict.kind == "wedge" and direction is Direction.LONG:
            trigger = _at(upper, end)
            br = confirm_breakout_retest(
                series, config, trigger, Direction.LONG, end,
                retest_timeout_bars=retest_timeout_bars,
            )
            breakout_price = dec(series.close[br.breakout_index]) if br.breakout_index is not None else trigger
            anchor = br.retest_index if br.retest_index is not None else (br.breakout_index or end)
            n = per_bar.get(anchor, 0)
            per_bar[anchor] = n + 1
            out.append(
                _pattern(
                    series, "falling_wedge", direction=Direction.LONG, start=start, end=end,
                    pivots=tuple(p.bar_index for p in window), trigger=trigger,
                    move=width_at_origin, target=breakout_price + width_at_origin,
                    trigger_result=br, invalidation=_at(lower, end), ordinal=n,
                    source_ids=("S4-R21", "S4-R23", "S4-R19", "P13"),
                )
            )
        elif verdict.kind == "wedge" and direction is Direction.SHORT:
            arrived_from_below = start > 0 and dec(series.close[start - 1]) < _at(lower, start)
            if not arrived_from_below:
                continue        # S4-R22: a rising wedge must be entered from below
            trigger = _at(lower, end)
            br = confirm_breakout_retest(
                series, config, trigger, Direction.SHORT, end,
                retest_timeout_bars=retest_timeout_bars,
            )
            breakdown_price = dec(series.close[br.breakout_index]) if br.breakout_index is not None else trigger
            anchor = br.retest_index if br.retest_index is not None else (br.breakout_index or end)
            n = per_bar.get(anchor, 0)
            per_bar[anchor] = n + 1
            out.append(
                _pattern(
                    series, "rising_wedge", direction=Direction.SHORT, start=start, end=end,
                    pivots=tuple(p.bar_index for p in window), trigger=trigger,
                    move=width_at_origin, target=breakdown_price - width_at_origin,
                    trigger_result=br, invalidation=_at(upper, end), ordinal=n,
                    source_ids=("S4-R22", "S4-R23", "S4-R19", "P13"),
                )
            )
        elif verdict.kind == "channel" and _at(lower, end) > _at(lower, start):
            n = per_bar.get(end, 0)
            per_bar[end] = n + 1
            out.append(
                _pattern(
                    series, "rising_channel", direction=None, start=start, end=end,
                    pivots=tuple(p.bar_index for p in window), trigger=_at(upper, end),
                    move=None, target=None, trigger_result=None, invalidation=None, ordinal=n,
                    source_ids=("S4-R23", "S8-neutral-channel"),
                    extra_reasons=("rising parallel channel is neutral: no measured target",),
                )
            )
    out.sort(key=lambda p: (p.completion_index, p.id))
    return out


# --------------------------------------------------------------------------- double top / bottom


def find_double_tops_bottoms(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    retest_timeout_bars: int | None = None,
) -> list[Pattern]:
    """Double tops and double bottoms (S7-R32, S7-R33, S7-R34, S8-R25; also SPEC.md §5.7).

    The second body extreme must be **close to** the first — bodies, not wicks (S7-R32,
    S5-R44) — which is the P9 tolerance band.  The neckline is the opposing pivot between them;
    entry is the neckline break plus the retest (S7-R33).  Measured target =
    ``(neckline - bottom)`` projected beyond the neckline (S7-R34).  A double bottom is
    invalidated by a close below its low, a double top by a close above its high.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    out: list[Pattern] = []
    per_bar: dict[int, int] = {}
    for kind_enum, kind, direction in (
        (SwingKind.HIGH, "double_top", Direction.SHORT),
        (SwingKind.LOW, "double_bottom", Direction.LONG),
    ):
        same = [p for p in all_pivots if p.kind is kind_enum]
        opposing = [p for p in all_pivots if p.kind is not kind_enum]
        for first, second in zip(same, same[1:]):
            if not P.price_at_level(
                series, config, second.price, first.price, at_index=second.bar_index
            ):
                continue
            between = [p for p in opposing if first.bar_index < p.bar_index < second.bar_index]
            if not between:
                continue
            neck = (
                min(between, key=lambda p: p.price)
                if kind_enum is SwingKind.HIGH
                else max(between, key=lambda p: p.price)
            )
            extreme = max(first.price, second.price) if kind_enum is SwingKind.HIGH else min(first.price, second.price)
            move = abs(neck.price - extreme)
            target = neck.price - move if direction is Direction.SHORT else neck.price + move
            br = confirm_breakout_retest(
                series, config, neck.price, direction, second.confirmed_at_index,
                retest_timeout_bars=retest_timeout_bars,
            )
            anchor = br.retest_index if br.retest_index is not None else (br.breakout_index or second.confirmed_at_index)
            n = per_bar.get(anchor, 0)
            per_bar[anchor] = n + 1
            out.append(
                _pattern(
                    series, kind, direction=direction, start=first.bar_index, end=second.bar_index,
                    pivots=(first.bar_index, neck.bar_index, second.bar_index),
                    trigger=neck.price, move=move, target=target, trigger_result=br,
                    invalidation=extreme, ordinal=n,
                    source_ids=("S7-R32", "S7-R33", "S7-R34", "S8-R25", "S4-R19", "P9"),
                )
            )
    out.sort(key=lambda p: (p.completion_index, p.id))
    return out


# --------------------------------------------------------------------------- cup and handle


def find_cup_and_handle(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    retest_timeout_bars: int | None = None,
) -> list[Pattern]:
    """Cup and handle (S4-R24; ``cup_handle_floor_pct``, whose midpoint is **[OUR CHOICE]**).

    Shape: a swing high (left rim) → a swing low (cup base) → a swing high back at the same price
    (right rim, the *two rejections from the neckline*, checked with the P9 band) → a handle low.
    The handle must not retrace below ``cup_handle_floor_pct`` of the cup depth — S4-A9 records
    that he says "40 to 50 %" twice in the same breath, so the 45 % default is the midpoint and
    marked as ours.  Target = cup base → neckline, projected up from the neckline.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    highs = [p for p in all_pivots if p.kind is SwingKind.HIGH]
    lows = [p for p in all_pivots if p.kind is SwingKind.LOW]
    out: list[Pattern] = []
    per_bar: dict[int, int] = {}
    floor = dec(config.cup_handle_floor_pct) / Decimal(100)

    for left, right in zip(highs, highs[1:]):
        if not P.price_at_level(series, config, right.price, left.price, at_index=right.bar_index):
            continue
        cup = [p for p in lows if left.bar_index < p.bar_index < right.bar_index]
        if not cup:
            continue
        base = min(cup, key=lambda p: p.price)
        neckline = max(left.price, right.price)
        depth = neckline - base.price
        if depth <= 0:
            continue
        handles = [p for p in lows if p.bar_index > right.bar_index]
        if not handles:
            continue
        handle = handles[0]
        if handle.price < neckline - floor * depth:
            continue        # handle retraced past the cup-depth floor (S4-R24)
        br = confirm_breakout_retest(
            series, config, neckline, Direction.LONG, handle.confirmed_at_index,
            retest_timeout_bars=retest_timeout_bars,
        )
        anchor = br.retest_index if br.retest_index is not None else (br.breakout_index or handle.confirmed_at_index)
        n = per_bar.get(anchor, 0)
        per_bar[anchor] = n + 1
        out.append(
            _pattern(
                series, "cup_and_handle", direction=Direction.LONG, start=left.bar_index,
                end=handle.bar_index,
                pivots=(left.bar_index, base.bar_index, right.bar_index, handle.bar_index),
                trigger=neckline, move=depth, target=neckline + depth, trigger_result=br,
                invalidation=handle.price, ordinal=n,
                source_ids=("S4-R24", "S4-A9", "S4-R19", "P9"),
            )
        )
    out.sort(key=lambda p: (p.completion_index, p.id))
    return out


# --------------------------------------------------------------------------- head and shoulders


def find_head_and_shoulders(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    retest_timeout_bars: int | None = None,
) -> list[Pattern]:
    """Head and shoulders, and its inverse (S4-R25, S4-R26, S5-R40).

    H&S — head above both shoulders; the neckline is the shallower of the two troughs.  **Never
    short the right shoulder** (S4-R26): the entry is the neckline breakdown, the retest and the
    rejection, which is exactly what :func:`confirm_breakout_retest` gates, so ``entry_price``
    stays ``None`` until then.  Target = head → neckline, projected down.

    Inverse H&S — the head must be **below both shoulders** (a hard geometric filter, S4-R25), the
    right shoulder is not formed until the neckline is touched, and the right-shoulder peak must
    not exceed the left-shoulder peak (S5-R40).  Target = head bottom → neckline, projected up.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    out: list[Pattern] = []
    per_bar: dict[int, int] = {}

    for kind_enum, kind, direction in (
        (SwingKind.HIGH, "head_and_shoulders", Direction.SHORT),
        (SwingKind.LOW, "inverse_head_and_shoulders", Direction.LONG),
    ):
        same = [p for p in all_pivots if p.kind is kind_enum]
        opposing = [p for p in all_pivots if p.kind is not kind_enum]
        for a in range(len(same) - 2):
            left, head, right = same[a], same[a + 1], same[a + 2]
            if kind_enum is SwingKind.HIGH:
                if not (head.price > left.price and head.price > right.price):
                    continue
            elif not (head.price < left.price and head.price < right.price):
                continue
            t1 = [p for p in opposing if left.bar_index < p.bar_index < head.bar_index]
            t2 = [p for p in opposing if head.bar_index < p.bar_index < right.bar_index]
            if not t1 or not t2:
                continue
            first_peak, second_peak = t1[-1], t2[0]
            if kind_enum is SwingKind.LOW and second_peak.price > first_peak.price:
                continue        # right-shoulder peak must not exceed the left's (S5-R40)
            if kind_enum is SwingKind.LOW and not P.price_at_level(
                series, config, second_peak.price, first_peak.price, at_index=right.confirmed_at_index
            ):
                continue        # the right shoulder is not formed until the neckline is touched
            neckline = (
                min(first_peak.price, second_peak.price)
                if kind_enum is SwingKind.HIGH
                else max(first_peak.price, second_peak.price)
            )
            move = abs(head.price - neckline)
            target = neckline - move if direction is Direction.SHORT else neckline + move
            br = confirm_breakout_retest(
                series, config, neckline, direction, right.confirmed_at_index,
                retest_timeout_bars=retest_timeout_bars,
            )
            anchor = br.retest_index if br.retest_index is not None else (br.breakout_index or right.confirmed_at_index)
            n = per_bar.get(anchor, 0)
            per_bar[anchor] = n + 1
            out.append(
                _pattern(
                    series, kind, direction=direction, start=left.bar_index, end=right.bar_index,
                    pivots=(left.bar_index, first_peak.bar_index, head.bar_index,
                            second_peak.bar_index, right.bar_index),
                    trigger=neckline, move=move, target=target, trigger_result=br,
                    invalidation=head.price, ordinal=n,
                    source_ids=(
                        ("S4-R26",) if kind_enum is SwingKind.HIGH else ("S4-R25", "S5-R40")
                    ) + ("S4-R19", "P9"),
                    extra_reasons=(
                        ("never short the right shoulder; entry is the neckline breakdown + "
                         "retest + rejection (S4-R26)",)
                        if kind_enum is SwingKind.HIGH
                        else ()
                    ),
                )
            )
    out.sort(key=lambda p: (p.completion_index, p.id))
    return out


# --------------------------------------------------------------------------- quasimodo


def find_quasimodo(
    series: Series,
    config: Config,
    *,
    levels: Sequence[Level] = (),
    pivots: Sequence[SwingPoint] | None = None,
) -> list[Pattern]:
    """Bearish quasimodo (S4-R27, S6-R50, S8 ``[00:10:53]``).

    Sequence: an uptrend of higher highs and higher lows → the final higher high ``HH2`` → a close
    below the prior higher low, printing a lower low → a rally back to ``HH2`` that makes a
    **lower high** there → the rejection is the trigger.  It **must** coincide with horizontal
    resistance (S6-R50), so a ``Level`` inside the P9 band at the lower high is required: with no
    ``levels`` supplied nothing is emitted.  No measured target is stated anywhere, so none is
    invented.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    highs = [p for p in all_pivots if p.kind is SwingKind.HIGH]
    lows = [p for p in all_pivots if p.kind is SwingKind.LOW]
    out: list[Pattern] = []
    per_bar: dict[int, int] = {}

    for i in range(len(highs) - 2):
        hh1, hh2, lower_high = highs[i], highs[i + 1], highs[i + 2]
        if not (hh2.price > hh1.price and lower_high.price < hh2.price):
            continue
        hl = [p for p in lows if hh1.bar_index < p.bar_index < hh2.bar_index]
        ll = [p for p in lows if hh2.bar_index < p.bar_index < lower_high.bar_index]
        if not hl or not ll:
            continue
        higher_low, lower_low = hl[-1], ll[0]
        if lower_low.price >= higher_low.price:
            continue        # the leg after the final HH must print a lower low (S4-R27)
        closed_below = any(
            dec(series.close[j]) < higher_low.price
            for j in range(hh2.bar_index + 1, lower_low.bar_index + 1)
        )
        if not closed_below:
            continue
        if not P.price_at_level(
            series, config, lower_high.price, hh2.price, at_index=lower_high.bar_index
        ):
            continue        # the rally must return *to the previous higher high* (S4-R27)
        confluent = [
            lv.id
            for lv in levels
            if P.price_at_level(
                series, config, lower_high.price, lv.price_at(lower_high.bar_index),
                at_index=lower_high.bar_index,
            )
        ]
        if not confluent:
            continue        # must coincide with horizontal resistance (S6-R50)
        trigger_index = lower_high.confirmed_at_index
        if trigger_index >= len(series):
            continue
        n = per_bar.get(trigger_index, 0)
        per_bar[trigger_index] = n + 1
        buffer = P.stop_buffer(series, config, trigger_index)
        out.append(
            Pattern(
                id=object_id(series, "bearish_quasimodo", trigger_index, n),
                symbol=series.symbol,
                tf=series.tf,
                kind="bearish_quasimodo",
                direction=Direction.SHORT,
                start_index=hh1.bar_index,
                end_index=lower_high.bar_index,
                completion_index=trigger_index,
                pivot_indices=(hh1.bar_index, higher_low.bar_index, hh2.bar_index,
                               lower_low.bar_index, lower_high.bar_index),
                trigger_price=lower_high.price,
                measured_move=None,
                measured_target=None,
                breakout_index=None,
                retest_index=trigger_index,
                confirmed=True,
                entry_price=dec(series.close[trigger_index]),
                stop_price=P.apply_stop_buffer(lower_high.wick_price, Direction.SHORT, buffer),
                invalidation_price=hh2.price,
                reasons=(f"coincides with horizontal resistance {confluent[0]} (S6-R50)",),
                source_ids=("S4-R27", "S6-R50", "P9", "P19"),
            )
        )
    out.sort(key=lambda p: (p.completion_index, p.id))
    return out


# --------------------------------------------------------------------------- detector


class PatternDetector:
    """SPEC.md §5.10 detector (pipeline stage 11) — INTERFACES.md §6 protocol.

    Confluence-only by design: :meth:`to_confluence` emits class ``"pattern"`` (weight 0.5) and
    nothing else, so a pattern can never satisfy the two-class rule on its own (S4-R38, PL-4).
    Patterns nest and may form on trend lines; both simply count as extra confluence
    (S4 ``[01:42:49]``), which the P14 scorer handles.
    """

    name = "chart_patterns"
    stage = 11
    source_ids = (
        "CF-37",
        "S4-R17",
        "S4-R18",
        "S4-R19",
        "S4-R21",
        "S4-R22",
        "S4-R23",
        "S4-R24",
        "S4-R25",
        "S4-R26",
        "S4-R27",
        "S4-R28",
        "S4-R29",
        "S4-R38",
        "S5-R39",
        "S5-R40",
        "S5-R41",
        "S6-R50",
        "S7-R32",
        "S7-R33",
        "S7-R34",
        "S8-R25",
        "P1",
        "P2",
        "P9",
        "P13",
        "P19",
    )
    produces = ("pattern",)

    #: S4-R38 / PL-4 — a pattern is never the sole reason for a trade.
    standalone_forbidden = True
    #: S5-R41 — he does not play them, so they are never emitted.
    not_implemented = NOT_IMPLEMENTED_PATTERNS

    def detect(
        self,
        series: Series,
        config: Config,
        *,
        levels: Sequence[Level] = (),
        pivots: Sequence[SwingPoint] | None = None,
        retest_timeout_bars: int | None = None,
    ) -> list[Pattern]:
        """Every pattern completed by the bars in ``series``, newest last.

        ``series`` must be the timeframe the pattern is drawn on: the confirming retest has to
        happen there (S4-R29, PL-8), and a lower-timeframe retest may improve the entry price but
        never confirms a higher-timeframe pattern.  ``levels`` feed the bearish quasimodo's
        mandatory horizontal-resistance coincidence (S6-R50).
        """
        all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
        out: list[Pattern] = []
        out.extend(find_flags(series, config, pivots=all_pivots, retest_timeout_bars=retest_timeout_bars))
        out.extend(find_wedges_and_channels(series, config, pivots=all_pivots, retest_timeout_bars=retest_timeout_bars))
        out.extend(find_double_tops_bottoms(series, config, pivots=all_pivots, retest_timeout_bars=retest_timeout_bars))
        out.extend(find_cup_and_handle(series, config, pivots=all_pivots, retest_timeout_bars=retest_timeout_bars))
        out.extend(find_head_and_shoulders(series, config, pivots=all_pivots, retest_timeout_bars=retest_timeout_bars))
        out.extend(find_quasimodo(series, config, levels=levels, pivots=all_pivots))
        out.sort(key=lambda p: (p.completion_index, p.kind, p.id))
        return out

    def to_confluence(
        self, objects: Sequence[Any], config: Config
    ) -> list[P.ConfluenceObject]:
        return [
            P.ConfluenceObject(
                id=obj.id,
                price=obj.confluence_price,
                obj_class="pattern",
                tf=obj.tf,
                source_ids=obj.source_ids,
            )
            for obj in objects
            if isinstance(obj, Pattern)
        ]
