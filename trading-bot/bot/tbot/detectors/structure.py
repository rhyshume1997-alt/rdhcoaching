"""tbot.detectors.structure — SPEC.md §5.7: swing points, trend, market-structure break.

What lives here
---------------
* **Trend state** — higher highs / higher lows versus lower highs / lower lows, read off candle
  **bodies** (S5-R44, S7-R11).  The classification itself is P11; this module only supplies the
  pivots and the "last technical higher low / lower high" that the rest of §5.7 refers to.
* **Market structure break (MSB)** — a single candle **body close** beyond the last opposing
  swing point (S7-R12, S7-R13, ``msb_price_source = "body_close"``), with the *line-chart
  tiebreaker* of S7-R11 / S8-R27 for the exact-tie case (see :func:`body_close_through`).
* **Post-break retest** — detection is not action (CF-22).  Opening a position in the new
  direction needs the break **plus** the retest holding, within ``msb_retest_timeout_bars``
  (S7-R15, S7-R16, S8-R26, TBOT1-R15).
* **The two-step structure exit** — ``msb_exit_mode``: ``"break_only"`` (default, CF-22) fires on
  detection alone; ``"break_plus_lower_high"`` is S3-R21 / S2-R28's version — the close through
  structure **then** a confirmed lower high (mirror: a confirmed higher low for a short).
* **Reclaim re-entry** — S8-R28: bias resumes only when the lost structure level is reclaimed by
  a body close **and** flipped.  A reclaim alone is not enough, so a :class:`StructureReclaim`
  always carries ``requires_flip_confirmation=True``; the CF-15 flip machine itself belongs to
  ``detectors/levels.py`` (it owns ``flip_confirm_candles``).
* **Bias invalidation level** — CF-23's *separate* object for spot/long-term bags: the deepest
  swing low within ``bias_level_lookback_bars`` carrying at least ``bias_level_min_confluence``
  confluences.  The technical higher low still drives MSB.

Config keys read here (owned by this module per INTERFACES.md §7): ``swing_k``,
``swing_price_source``, ``trend_pivot_count``, ``trend_timeframe``, ``structure_tf_offset``,
``msb_price_source``, ``msb_exit_mode``, ``msb_entry_requires_retest``,
``msb_retest_timeout_bars``, ``msb_deviation_invalidates`` (Q11), ``higher_low_selection``, ``bias_level_enabled``,
``bias_level_lookback_bars``, ``bias_level_min_confluence``, ``htf_veto_enabled``,
``htf_veto_timeframe``.  Everything else (tolerance bands, ATR, confluence weights) is reached
**through** the primitives, never read off ``Config`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from .. import primitives as P
from ..config import Config
from ..models import (
    Direction,
    Level,
    LevelKind,
    Series,
    SwingKind,
    SwingPoint,
    Timeframe,
    Trend,
    dec,
)
from .base import object_id

__all__ = [
    "StructureState",
    "MSB",
    "StructureExit",
    "StructureReclaim",
    "structure_tf_for",
    "body_close_through",
    "structure_state",
    "find_msbs",
    "find_structure_exits",
    "find_reclaims",
    "bias_invalidation_level",
    "htf_veto_reason",
    "StructureDetector",
]


# --------------------------------------------------------------------------- records


@dataclass(frozen=True, slots=True)
class StructureState:
    """Trend plus the structure references every §5.7 rule points at, as of ``bar_index``.

    ``last_higher_low`` is the most recent confirmed swing **low** that printed above its
    predecessor, ``last_lower_high`` the most recent confirmed swing **high** that printed below
    its predecessor — the *technical* reading (``higher_low_selection = "technical"``, CF-23).
    Both are ``None`` until two same-kind pivots have been confirmed.
    """

    bar_index: int
    trend: Trend
    last_higher_low: SwingPoint | None
    last_lower_high: SwingPoint | None
    last_swing_high: SwingPoint | None
    last_swing_low: SwingPoint | None
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MSB:
    """A market structure break (S7-R12, S7-R13).

    ``direction`` is the direction the break points in: ``LONG`` for a bullish MSB (body close
    above the last lower high), ``SHORT`` for a bearish one (body close below the last higher
    low).  ``entry_armed`` is the CF-22 *action* flag — detection alone never arms an entry when
    ``msb_entry_requires_retest`` is true, and **Q11** disarms it outright when
    ``deviation_index`` is set (a close back beyond the broken level before any retest, S2
    ``[00:25:56]``).
    """

    id: str
    symbol: str
    tf: Timeframe
    direction: Direction
    break_index: int
    broken_swing_id: str
    broken_swing_index: int
    broken_price: Decimal
    close_price: Decimal
    line_chart_tiebreak: bool
    retest_required: bool
    retest_index: int | None
    retest_deadline_index: int
    entry_armed: bool
    entry_price: Decimal | None
    #: **Q11** — bar at which price closed back beyond the broken level before any retest, i.e.
    #: the break was a deviation and the setup is dead (``msb_deviation_invalidates``, S2
    #: ``[00:25:56]``).  ``None`` when no deviation occurred.
    deviation_index: int | None = None
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @property
    def retest_confirmed(self) -> bool:
        return self.retest_index is not None

    @property
    def deviated(self) -> bool:
        """Q11 — the break was reclaimed without a retest; nothing may arm off it."""
        return self.deviation_index is not None


@dataclass(frozen=True, slots=True)
class StructureExit:
    """A structure-driven exit signal for an *open* position (CF-22 exit action).

    ``mode`` echoes ``msb_exit_mode``.  Under ``"break_plus_lower_high"`` the signal is not
    ``confirmed`` until ``confirm_index`` — the bar the confirming lower high (or, for a short,
    higher low) became a usable pivot.
    """

    id: str
    symbol: str
    tf: Timeframe
    direction: Direction
    msb_id: str
    break_index: int
    confirm_index: int | None
    mode: str
    confirmed: bool
    confirming_swing_id: str | None = None
    source_ids: tuple[str, ...] = ()

    @property
    def signal_index(self) -> int | None:
        """The bar the exit actually fires on, or ``None`` while unconfirmed."""
        return self.break_index if self.mode == "break_only" else self.confirm_index


@dataclass(frozen=True, slots=True)
class StructureReclaim:
    """A body close back through a lost structure level (S8-R28, CF-21 re-entry trigger (b)).

    S8-R28 is explicit that this is **not** sufficient on its own: bias resumes only once the
    level is reclaimed *and* flipped.  ``requires_flip_confirmation`` is therefore always true;
    the CF-15 confirmation itself is ``detectors/levels.py``'s job.
    """

    id: str
    symbol: str
    tf: Timeframe
    direction: Direction
    reclaim_index: int
    level_price: Decimal
    close_price: Decimal
    msb_id: str
    requires_flip_confirmation: bool = True
    source_ids: tuple[str, ...] = ()


# --------------------------------------------------------------------------- helpers


def structure_tf_for(trade_tf: Timeframe | str, config: Config) -> Timeframe:
    """CF-24's two-tier map: ``structure_tf = trade_tf + structure_tf_offset`` rungs.

    Trend, MSB, counter-trend classification and the HTF veto are evaluated there and **only**
    there.  The ladder is clamped at both ends by :meth:`Timeframe.step`.
    """
    return Timeframe.parse(trade_tf).step(config.structure_tf_offset)


def trend_timeframe_for(trade_tf: Timeframe | str, config: Config) -> Timeframe:
    """``trend_timeframe`` resolved: ``"structure_tf"`` defers to :func:`structure_tf_for`."""
    if config.trend_timeframe == "structure_tf":
        return structure_tf_for(trade_tf, config)
    return Timeframe.parse(config.trend_timeframe)


def _swing_price(series: Series, config: Config, pivot: SwingPoint) -> Decimal:
    """The price an MSB is measured against: the pivot's body extreme, or its wick under
    ``msb_price_source = "wick"``."""
    if config.msb_price_source == "wick":
        return pivot.wick_price
    return pivot.price


def body_close_through(
    series: Series,
    bar_index: int,
    level_price: Decimal,
    direction: Direction,
    *,
    line_chart_level: Decimal | None = None,
) -> tuple[bool, bool]:
    """S7-R12/R13 body-close test, with the S7-R11 / S8-R27 **line-chart tiebreaker**.

    Returns ``(broke, used_line_chart)``.

    The primary test is strict: a bullish break needs ``close > level``, a bearish one
    ``close < level``.  He reads structure off bodies and, *when the count is unclear, switches
    the chart to line mode* (S7-R11 "when in doubt switch the chart to line mode", S8-R27
    "line-chart confirmation used to count structure").  The only mechanically unclear case is an
    exact tie — the close landing on the level — so that is where the tiebreaker is applied: the
    comparison is re-run against the **line-chart price of the pivot bar**, i.e. that bar's close
    rather than its body extreme.  A line chart plots closes, so this is literally what switching
    the chart does.  **[OUR CHOICE]** mechanisation of an eyeball instruction; the tie itself is
    exact-equality, so this never fires on ordinary data and never widens the primary test.
    """
    close = dec(series.close[bar_index])
    if direction is Direction.LONG:
        if close > level_price:
            return True, False
        if close == level_price and line_chart_level is not None:
            return close > line_chart_level, True
        return False, False
    if close < level_price:
        return True, False
    if close == level_price and line_chart_level is not None:
        return close < line_chart_level, True
    return False, False


def _pivots(series: Series, config: Config, pivots: Sequence[SwingPoint] | None) -> list[SwingPoint]:
    return list(pivots) if pivots is not None else P.swing_points(series, config)


def structure_state(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    at_index: int | None = None,
) -> StructureState:
    """Trend (P11) plus the last technical higher low / lower high as of ``at_index``.

    Only pivots confirmed at or before ``at_index`` are consulted (P1, INTERFACES.md §9.1), so
    this is safe to call bar-by-bar.
    """
    idx = len(series) - 1 if at_index is None else (at_index if at_index >= 0 else len(series) + at_index)
    all_pivots = _pivots(series, config, pivots)
    usable = P.confirmed_swings(all_pivots, idx)
    highs = [p for p in usable if p.kind is SwingKind.HIGH]
    lows = [p for p in usable if p.kind is SwingKind.LOW]

    last_higher_low: SwingPoint | None = None
    for prev, cur in zip(lows, lows[1:]):
        if cur.price > prev.price:
            last_higher_low = cur
    last_lower_high: SwingPoint | None = None
    for prev, cur in zip(highs, highs[1:]):
        if cur.price < prev.price:
            last_lower_high = cur

    return StructureState(
        bar_index=idx,
        trend=P.classify_trend(usable, config, at_index=idx),
        last_higher_low=last_higher_low,
        last_lower_high=last_lower_high,
        last_swing_high=highs[-1] if highs else None,
        last_swing_low=lows[-1] if lows else None,
        source_ids=("P11", "S7-R11", "S5-R44", "CF-23"),
    )


# --------------------------------------------------------------------------- MSB


def _find_retest(
    series: Series,
    config: Config,
    level_price: Decimal,
    direction: Direction,
    break_index: int,
    deadline_index: int,
) -> tuple[int | None, int | None]:
    """``(retest_index, deviation_index)`` — the first of the two events to occur, or both None.

    **Retest.** The first bar after ``break_index`` that revisits ``level_price`` (P9 band) and
    holds.  "Holds" is a close on the **new** side: after a bullish MSB the broken lower high must
    act as support (close at or above it), after a bearish MSB the broken higher low must act as
    resistance (close at or below it) — S7-R15, S7-R16.

    **Deviation (Q11, derived, S2 ``[00:25:56]``).**  ``msb_deviation_invalidates``: a body close
    back *beyond* the broken level, outside the P9 tolerance band, before that retest ever arrives
    means the break was never real — *"if we reclaim it without a retest, meaning if we close back
    above, then this is just a deviation of that level."*  This is his actual invalidation, and it
    is a condition, not a clock: he refuses to bound the retest wait at all ("next candle or
    however many candles it takes", S4 ``[00:35:08]``).  ``msb_retest_timeout_bars`` remains the
    outer bound and remains **[OUR CHOICE]**.

    The scan stops at whichever fires first, so a deviation cannot be rescued by a later retest
    inside the same window.
    """
    last = min(deadline_index, len(series) - 1)
    for j in range(break_index + 1, last + 1):
        close = dec(series.close[j])
        if P.bar_at_level(series, config, level_price, j):
            if direction is Direction.LONG and close >= level_price:
                return j, None
            if direction is Direction.SHORT and close <= level_price:
                return j, None
        if not config.msb_deviation_invalidates:
            continue
        # A body close back beyond the broken level, and beyond the P9 tolerance band around it
        # so a close hovering on the line is not mistaken for a reclaim: the break is a deviation
        # (S2 `[00:25:56]`).  Same price source as the break itself — bodies (S7-R11).
        tol = P.atr_at(series, config, j) * dec(config.level_tolerance_atr)
        if direction is Direction.LONG and close < level_price - tol:
            return None, j
        if direction is Direction.SHORT and close > level_price + tol:
            return None, j
    return None, None


def find_msbs(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    bias_level: Level | None = None,
) -> list[MSB]:
    """Every market structure break completed by the bars in ``series`` (S7-R12, S7-R13).

    A break fires on the **first** body close beyond a given opposing swing point; the same pivot
    can only be broken once, so a trend that keeps closing lower does not re-emit the same MSB.
    Detection is unconditional (CF-22): the object is emitted whether or not the retest arrives,
    and ``entry_armed`` carries the action decision.

    ``higher_low_selection = "confluence_weighted"`` (S8-C2's reading) swaps the bearish
    reference for ``bias_level`` when one is supplied; the default ``"technical"`` always uses the
    swing structure, which is CF-23's verdict.
    """
    all_pivots = _pivots(series, config, pivots)
    out: list[MSB] = []
    broken: set[str] = set()
    per_bar: dict[int, int] = {}

    for i in range(1, len(series)):
        state = structure_state(series, config, pivots=all_pivots, at_index=i)
        candidates: list[tuple[Direction, SwingPoint | None, Decimal | None, str]] = [
            (Direction.SHORT, state.last_higher_low, None, "S7-R12"),
            (Direction.LONG, state.last_lower_high, None, "S7-R13"),
        ]
        if config.higher_low_selection == "confluence_weighted" and bias_level is not None:
            candidates[0] = (Direction.SHORT, None, bias_level.price, "S8-C2")

        for direction, pivot, override_price, rule in candidates:
            if pivot is not None:
                if pivot.bar_index >= i:
                    continue
                key = pivot.id
                level_price = _swing_price(series, config, pivot)
                line_level = dec(series.close[pivot.bar_index])
                swing_index = pivot.bar_index
            elif override_price is not None:
                key = f"bias:{override_price}"
                level_price = override_price
                line_level = None
                swing_index = bias_level.created_index if bias_level is not None else i
            else:
                continue
            if key in broken:
                continue
            broke, tiebreak = body_close_through(
                series, i, level_price, direction, line_chart_level=line_level
            )
            if not broke:
                continue
            broken.add(key)

            deadline = i + config.msb_retest_timeout_bars
            retest, deviation = _find_retest(
                series, config, level_price, direction, i, deadline
            )
            retest_required = config.msb_entry_requires_retest
            armed = (retest is not None) if retest_required else True
            reasons: tuple[str, ...] = ()
            if deviation is not None:
                # Q11: a close back beyond the broken level kills the setup outright, whether or
                # not a retest was required.  Detection still stands — the break happened — but
                # nothing may arm off it (S2 `[00:25:56]`).
                armed = False
                reasons = (
                    f"deviation: close back beyond {level_price} at bar {deviation} before any "
                    f"retest — msb_deviation_invalidates (S2 `[00:25:56]`)",
                )
            elif retest_required and retest is None:
                reasons = (
                    f"no retest of {level_price} within msb_retest_timeout_bars "
                    f"{config.msb_retest_timeout_bars}",
                )
            n = per_bar.get(i)
            per_bar[i] = 0 if n is None else n + 1
            src = ("CF-22", rule, "S7-R11", "msb_price_source=" + config.msb_price_source)
            if tiebreak:
                src = src + ("S8-R27",)
            if retest_required:
                src = src + (("S7-R15",) if direction is Direction.LONG else ("S7-R16", "S8-R26"))
            if deviation is not None:
                src = src + ("S2 `[00:25:56]`",)
            out.append(
                MSB(
                    id=object_id(series, "msb", i, per_bar[i]),
                    symbol=series.symbol,
                    tf=series.tf,
                    direction=direction,
                    break_index=i,
                    broken_swing_id=pivot.id if pivot is not None else key,
                    broken_swing_index=swing_index,
                    broken_price=level_price,
                    close_price=dec(series.close[i]),
                    line_chart_tiebreak=tiebreak,
                    retest_required=retest_required,
                    retest_index=retest,
                    deviation_index=deviation,
                    retest_deadline_index=deadline,
                    entry_armed=armed,
                    entry_price=dec(series.close[retest]) if retest is not None else None,
                    reasons=reasons,
                    source_ids=src,
                )
            )
    out.sort(key=lambda m: (m.break_index, m.direction.value))
    return out


# --------------------------------------------------------------------------- exits


def find_structure_exits(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    msbs: Sequence[MSB] | None = None,
) -> list[StructureExit]:
    """Structure exits for open positions (CF-22 exit action, ``msb_exit_mode``).

    ``"break_only"`` (default) — the exit fires on the MSB itself.  S2-R28 and S3-R21's extra
    confirmation costs a full leg, which is why it is the alternative and not the default.

    ``"break_plus_lower_high"`` — S3-R21's two-step: the close below the last higher low, **then**
    a subsequent confirmed **lower high**.  The mirror for a short position is a close above the
    last lower high followed by a confirmed **higher low**.  The exit is not ``confirmed`` until
    that second pivot is usable (``confirmed_at_index``), which is the bar the signal fires on.
    """
    all_pivots = _pivots(series, config, pivots)
    events = list(msbs) if msbs is not None else find_msbs(series, config, pivots=all_pivots)
    mode = config.msb_exit_mode
    out: list[StructureExit] = []
    per_bar: dict[int, int] = {}

    for msb in events:
        confirm_index: int | None = None
        confirming: str | None = None
        if mode == "break_only":
            confirmed = True
        else:
            kind = SwingKind.HIGH if msb.direction is Direction.SHORT else SwingKind.LOW
            same = [p for p in all_pivots if p.kind is kind]
            for prev, cur in zip(same, same[1:]):
                if cur.bar_index <= msb.break_index:
                    continue
                lower_high = msb.direction is Direction.SHORT and cur.price < prev.price
                higher_low = msb.direction is Direction.LONG and cur.price > prev.price
                if lower_high or higher_low:
                    confirm_index = cur.confirmed_at_index
                    confirming = cur.id
                    break
            confirmed = confirm_index is not None and confirm_index < len(series)
            if not confirmed:
                confirm_index = None
                confirming = None
        anchor = msb.break_index if mode == "break_only" else (confirm_index or msb.break_index)
        n = per_bar.get(anchor)
        per_bar[anchor] = 0 if n is None else n + 1
        out.append(
            StructureExit(
                id=object_id(series, "structure_exit", anchor, per_bar[anchor]),
                symbol=series.symbol,
                tf=series.tf,
                direction=msb.direction,
                msb_id=msb.id,
                break_index=msb.break_index,
                confirm_index=confirm_index,
                mode=mode,
                confirmed=confirmed,
                confirming_swing_id=confirming,
                source_ids=("CF-22", "S2-R28", "S3-R21") if mode != "break_only" else ("CF-22", "S7-R12"),
            )
        )
    out.sort(key=lambda e: (e.signal_index if e.signal_index is not None else e.break_index, e.direction.value))
    return out


# --------------------------------------------------------------------------- reclaim


def find_reclaims(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    msbs: Sequence[MSB] | None = None,
) -> list[StructureReclaim]:
    """The first body close back through each lost structure level (S8-R28, S6-R24, CF-21).

    One reclaim per MSB: after a bearish MSB the reclaim is a close back **above** the broken
    higher low; after a bullish MSB, a close back **below** the broken lower high.  The object is
    a *trigger candidate*, not a bias change — ``requires_flip_confirmation`` says so, and the
    CF-15 flip machine that satisfies it lives in ``detectors/levels.py``.
    """
    all_pivots = _pivots(series, config, pivots)
    events = list(msbs) if msbs is not None else find_msbs(series, config, pivots=all_pivots)
    out: list[StructureReclaim] = []
    per_bar: dict[int, int] = {}
    for msb in events:
        reclaim_dir = msb.direction.opposite
        for j in range(msb.break_index + 1, len(series)):
            broke, _ = body_close_through(series, j, msb.broken_price, reclaim_dir)
            if not broke:
                continue
            n = per_bar.get(j)
            per_bar[j] = 0 if n is None else n + 1
            out.append(
                StructureReclaim(
                    id=object_id(series, "structure_reclaim", j, per_bar[j]),
                    symbol=series.symbol,
                    tf=series.tf,
                    direction=reclaim_dir,
                    reclaim_index=j,
                    level_price=msb.broken_price,
                    close_price=dec(series.close[j]),
                    msb_id=msb.id,
                    requires_flip_confirmation=True,
                    source_ids=("S8-R28", "S6-R24", "CF-21"),
                )
            )
            break
    out.sort(key=lambda r: (r.reclaim_index, r.direction.value))
    return out


# --------------------------------------------------------------------------- CF-23 bias level


def bias_invalidation_level(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    confluence_objects: Sequence[P.ConfluenceObject] = (),
    at_index: int | None = None,
) -> Level | None:
    """CF-23's ``bias_invalidation_level`` — his "my higher low", kept as a separate object.

    The deepest confirmed swing **low** within ``bias_level_lookback_bars`` whose P14 confluence
    score reaches ``bias_level_min_confluence``.  Used for spot/long-term bags only: breaking the
    *technical* higher low downgrades conviction and blocks new longs, breaking *this* level
    closes the bag (S8-C2).

    ``confluence_objects`` are the priced objects of stages 3–8; with none supplied nothing can
    reach the confluence floor and the function returns ``None`` rather than guessing.
    """
    if not config.bias_level_enabled:
        return None
    idx = len(series) - 1 if at_index is None else (at_index if at_index >= 0 else len(series) + at_index)
    usable = P.confirmed_swings(_pivots(series, config, pivots), idx)
    floor_index = idx - config.bias_level_lookback_bars
    lows = [p for p in usable if p.kind is SwingKind.LOW and p.bar_index >= floor_index]
    if not lows:
        return None
    threshold = dec(config.bias_level_min_confluence)
    best: SwingPoint | None = None
    for low in lows:
        score = P.score_confluence(
            series, config, low.price, confluence_objects, at_index=idx
        ).score
        if score < threshold:
            continue
        if best is None or low.price < best.price:
            best = low
    if best is None:
        return None
    return Level(
        id=object_id(series, "bias_invalidation_level", best.bar_index),
        symbol=series.symbol,
        tf=series.tf,
        price=best.price,
        kind=LevelKind.SUPPORT,
        created_index=best.bar_index,
        member_pivot_ids=[best.id],
        anchor_indices=[best.bar_index],
        source_ids=("CF-23", "S8-C2"),
    )


# --------------------------------------------------------------------------- CF-24 HTF veto


def htf_veto_reason(
    htf_series: Series,
    config: Config,
    direction: Direction,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    at_index: int | None = None,
) -> str | None:
    """CF-24 / S7-R20: the higher timeframe wins where it disagrees with the entry direction.

    ``htf_series`` must be the series for ``config.htf_veto_timeframe`` (resolve
    ``"structure_tf"`` / ``"trade_tf"`` before calling — a bar index from one timeframe is
    meaningless in another).  Returns the veto string for ``Setup.vetoes``, or ``None``.
    """
    if not config.htf_veto_enabled:
        return None
    state = structure_state(htf_series, config, pivots=pivots, at_index=at_index)
    if direction is Direction.LONG and state.trend is Trend.DOWN:
        return f"htf_veto: {htf_series.tf.value} trend is down (S7-R20)"
    if direction is Direction.SHORT and state.trend is Trend.UP:
        return f"htf_veto: {htf_series.tf.value} trend is up (S7-R20)"
    return None


# --------------------------------------------------------------------------- detector


class StructureDetector:
    """SPEC.md §5.7 detector (pipeline stage 2) — INTERFACES.md §6 protocol.

    :meth:`detect` returns the structure **events** completed by the bars it is handed — MSBs,
    structure exits and reclaims — newest last.  Swing points themselves come straight from P1
    and are exposed by :meth:`swings` rather than duplicated into the event stream.
    """

    name = "structure"
    stage = 2
    source_ids = (
        "CF-22",
        "CF-23",
        "CF-24",
        "S7-R11",
        "S7-R12",
        "S7-R13",
        "S7-R14",
        "S7-R15",
        "S7-R16",
        "S8-R26",
        "S8-R27",
        "S8-R28",
        "S5-R44",
        "S3-R21",
        "S2-R28",
        "P1",
        "P11",
    )
    produces = ("sr_level",)

    def swings(self, series: Series, config: Config) -> list[SwingPoint]:
        """P1 pivots on this series — bodies by default (``swing_price_source``)."""
        return P.swing_points(series, config)

    def state_at(
        self, series: Series, config: Config, at_index: int | None = None
    ) -> StructureState:
        return structure_state(series, config, at_index=at_index)

    def detect(self, series: Series, config: Config) -> list[Any]:
        pivots = self.swings(series, config)
        msbs = find_msbs(series, config, pivots=pivots)
        exits = find_structure_exits(series, config, pivots=pivots, msbs=msbs)
        reclaims = find_reclaims(series, config, pivots=pivots, msbs=msbs)
        events: list[Any] = [*msbs, *exits, *reclaims]
        events.sort(key=_completion_index)
        return events

    def to_confluence(
        self, objects: Sequence[Any], config: Config
    ) -> list[P.ConfluenceObject]:
        """A broken structure level is S/R once it has been broken (the retest is the trade).

        Only MSBs price an object; exits and reclaims are events, not levels.
        """
        out: list[P.ConfluenceObject] = []
        for obj in objects:
            if isinstance(obj, MSB):
                out.append(
                    P.ConfluenceObject(
                        id=obj.id,
                        price=obj.broken_price,
                        obj_class="sr_level",
                        tf=obj.tf,
                        source_ids=obj.source_ids,
                    )
                )
        return out


def _completion_index(obj: Any) -> tuple[int, str]:
    if isinstance(obj, MSB):
        return (obj.break_index, obj.id)
    if isinstance(obj, StructureExit):
        return (obj.signal_index if obj.signal_index is not None else obj.break_index, obj.id)
    if isinstance(obj, StructureReclaim):
        return (obj.reclaim_index, obj.id)
    return (0, "")
