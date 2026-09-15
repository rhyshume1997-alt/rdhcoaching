"""tbot.detectors.sfp — SPEC.md §5.8: the swing failure pattern (pipeline stage 13).

The pattern
-----------
A **bearish SFP** is a candle whose *wick* takes out a prior swing **high** — the liquidity resting
above it — while the candle's *body closes back below* that swing (S7-R21, S8-R3, S5-R4).  A
**bullish SFP** is the mirror through a prior swing low (S7-R22, S5-R5).  Structure is read on
bodies throughout (S7-R11, S5-R44), so the raid is measured against the swing's **wick** price
(that is where the stops are) and the "closes back inside" test against the swing's **body**
price (that is where the structure is).

Every filter of §5.8, in the order :func:`evaluate` applies them
---------------------------------------------------------------
======  ====================================================================================
filter  rule
======  ====================================================================================
close   The candle must close back **inside**.  A candle that closes *beyond* the level is not
        an SFP and there is no trade — S7-R23, S8-R3.
timing  **No mid-candle entries** — S7-R24.  A raid is only ever a candidate once its own bar
        has closed, because the candle can still close back through the level.  Nothing here
        reads an unclosed bar, and the entry reference is always that bar's *close*.
adjac.  The SFP candle may not sit within ``sfp_min_bars_between`` bars of the swing candle it
        raids — S7-R25.
separ.  The raided swing must be at least ``sfp_min_swing_separation_atr`` ATR away in price
        from its nearest same-kind neighbour; swings that close together give weak SFPs —
        S7-R28, S8-R4.
trend   ``sfp_trend_veto``: no SFP against the prevailing trend — S7-R31.
level   ``sfp_standalone_enabled = false``: an SFP with no pre-marked level or zone at the swept
        price is not a trade.  Zones are marked first and the SFP arrives as late confluence —
        S7-R30, CF-20, CF-32 step 7.
deep    The chase cap: a confirming close further than ``sfp_max_close_distance_atr`` from the
        swept level is a deep wick that has already run.  Per S5-R7 this bans the **market**
        entry, and CF-20's missed-entry rule then applies: rest a limit at the prior swing
        high/low with the same wick stop (S5-R6, S7-R27, S8-R6).  The record is still emitted,
        with ``chase_allowed = False`` and ``entry_kind = "limit_at_swept_level"``.
======  ====================================================================================

Entry, stop, and what this module deliberately does not decide
-------------------------------------------------------------
``sfp_entry_price = "confirming_close"`` (CF-20): the confirming candle's close is the reference
price, executed on the next open — the same instant in a bar-close backtest, which is why S7-C6 is
recorded as a phrasing artefact.  The stop sits beyond the raiding wick with the P19 buffer.
``SFP.stop_pct`` reports the resulting stop distance in percent so the planner can run the CF-06
escalation (tighten → downgrade → skip) for the 17 %-stop case of S7-R26; ``max_stop_pct_leverage``
is ``planner.py``'s key and is deliberately **not** read here.  Sizing, R:R and DCA (zero — SFPs
are single-entry, CF-17) all belong downstream.

Config keys read here (owned by this module per INTERFACES.md §7): ``sfp_entry_price``,
``sfp_standalone_enabled``, ``sfp_min_bars_between``, ``sfp_min_swing_separation_atr``,
``sfp_max_close_distance_atr``, ``sfp_trend_veto``, ``sfp_governing_timeframe``,
``sfp_raid_price_source`` (Q6).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Sequence

from .. import primitives as P
from ..config import Config
from ..models import Direction, Level, Series, SwingKind, SwingPoint, Timeframe, Trend, Zone, dec
from .base import object_id
from .structure import structure_state

__all__ = [
    "SFP",
    "governing_timeframe",
    "raid_price",
    "SFPEvaluation",
    "raid_candidates",
    "evaluate",
    "find_sfps",
    "SFPDetector",
]

EntryKind = Literal["confirming_close", "limit_at_swept_level"]


def governing_timeframe(
    structure_tf: Timeframe | str,
    config: Config,
    *,
    trade_tf: Timeframe | str | None = None,
    valid_timeframes: Sequence[Timeframe | str] = (),
) -> Timeframe:
    """``sfp_governing_timeframe`` resolved (CF-20, answering S8-A3).

    **Q7 (inferred, S8 ``[00:23:06]`` / ``[00:16:46]``, S7 ``[01:24:22]`` / ``[01:26:03]``).**  The
    shipped mode is now ``"highest_valid"``.  SFP validity legitimately *differs* by timeframe —
    the same sweep is a valid daily SFP and an invalid 12H one — and he resolves it by trading the
    **highest** timeframe on which the SFP is valid, demoting a lower-timeframe-only SFP to a
    scalp (which the CF-38 timeframe classes then do automatically):

        *"on the daily… that's automatically a swing failure. Now, if we look at the 12-hour, we
        closed above, not an SFP"* — S8 ``[00:23:06]``;
        *"on a lower time frame, you could definitely take that. But on the daily, it's a missed
        attempt"* — S7 ``[01:24:22]``.

    ``valid_timeframes`` is the set of timeframes on which the SFP actually validated.  The search
    is bounded below by ``trade_tf`` (default: the structure timeframe) and above by
    ``structure_tf + 1`` rung — higher timeframes always take precedence (S7 ``[00:21:45]``) but
    the bot may not wander arbitrarily far up the ladder looking for a validation.  With no
    ``valid_timeframes`` supplied there is nothing to search and the structure timeframe stands,
    which is exactly the old ``"trade_structure_tf"`` behaviour.

    ``"trade_structure_tf"`` pins it to the trade's own structure timeframe; ``"1D"`` pins it to
    the daily.
    """
    mode = config.sfp_governing_timeframe
    st = Timeframe.parse(structure_tf)
    if mode == "trade_structure_tf":
        return st
    if mode == "highest_valid":
        low = Timeframe.parse(trade_tf) if trade_tf is not None else st
        high = st.step(1)
        in_band = [
            tf for tf in (Timeframe.parse(t) for t in valid_timeframes)
            if low.rank <= tf.rank <= high.rank
        ]
        return max(in_band, key=lambda tf: tf.rank) if in_band else st
    return Timeframe.parse(mode)


@dataclass(frozen=True, slots=True)
class SFP:
    """One swing failure pattern.

    ``bar_index`` is the confirming candle — the candle whose wick raided and whose body closed
    back inside.  ``entry_index`` is the same bar by construction: there is no mid-candle entry
    (S7-R24), and ``entry_price`` is that bar's close under ``sfp_entry_price =
    "confirming_close"``.

    ``direction`` is the *trade* direction: a bearish SFP (raid of a swing high) is a ``SHORT``.
    """

    id: str
    symbol: str
    tf: Timeframe
    direction: Direction
    bar_index: int
    entry_index: int
    swing_id: str
    swing_index: int
    swept_price: Decimal          #: the raided swing's wick — the liquidity level
    structure_price: Decimal      #: the raided swing's body — the structural level
    raid_extreme: Decimal         #: how far the raiding wick actually went
    close_price: Decimal
    entry_price: Decimal
    entry_kind: EntryKind
    chase_allowed: bool
    stop_price: Decimal
    stop_pct: Decimal             #: |stop - entry| / entry * 100, for the CF-06 escalation
    stop_is_capitulation_wick: bool
    close_distance_atr: Decimal
    swing_separation_atr: Decimal
    bars_between: int
    trend: Trend
    level_ids: tuple[str, ...] = ()
    zone_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SFPEvaluation:
    """A candidate raid plus the verdict on it.

    ``accepted`` records whether the candidate survived every §5.8 filter; ``reasons`` names the
    filters that rejected it, one string each.  :func:`find_sfps` (and therefore
    :meth:`SFPDetector.detect`) returns only the accepted ones — INTERFACES.md §6.4 forbids
    returning rejected objects — so this is the diagnostic view.
    """

    bar_index: int
    swing_id: str
    direction: Direction
    accepted: bool
    sfp: SFP | None
    reasons: tuple[str, ...]


# --------------------------------------------------------------------------- geometry


def raid_candidates(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
) -> list[tuple[int, SwingPoint, Direction]]:
    """Every ``(bar_index, raided_swing, trade_direction)`` where a wick took swing liquidity.

    Geometry only — no filter is applied here, not even the close test.  A bar raids a swing high
    when ``high > raid_price(swing)`` (the **wick**, Q6 carve-out — see :func:`raid_price`), and a
    swing low when ``low < raid_price(swing)``; only swings
    confirmed at or before the raiding bar and printed strictly before it are eligible (P1
    no-repaint, INTERFACES.md §9.1).  Each bar is matched against the **most recent** eligible
    swing of each kind, so one bar yields at most one bearish and one bullish candidate.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    out: list[tuple[int, SwingPoint, Direction]] = []
    for i in range(len(series)):
        usable = [p for p in P.confirmed_swings(all_pivots, i) if p.bar_index < i]
        highs = [p for p in usable if p.kind is SwingKind.HIGH]
        lows = [p for p in usable if p.kind is SwingKind.LOW]
        if highs and dec(series.high[i]) > raid_price(highs[-1], config):
            out.append((i, highs[-1], Direction.SHORT))
        if lows and dec(series.low[i]) < raid_price(lows[-1], config):
            out.append((i, lows[-1], Direction.LONG))
    return out


def raid_price(swing: SwingPoint, config: Config) -> Decimal:
    """**Q6 carve-out** — the price the SFP raids, and the price its stop sits beyond.

    ``swing_price_source`` is ``"body"`` because *structure* is read off bodies (S7
    ``[00:18:50]``, ``[01:11:53]``, S5 ``[01:25:16]``).  The SFP is the one object that does not
    follow it: S7 ``[01:14:44]`` — *"swing high points are usually taken by wicks, not by bodies.
    Okay, but the candle body closes below the swing high point and this wick has taken out all of
    its liquidity."*  Two different objects at one pivot: the **wick** is where the liquidity and
    therefore the raid level and the stop are; the **body** is where the structure and therefore
    the "closes back inside" test is.

    ``sfp_raid_price_source`` records that carve-out (``"wick"``, stated) so it is visible and
    sweepable rather than hard-coded.
    """
    return swing.price if config.sfp_raid_price_source == "body" else swing.wick_price


def _closes_back_inside(series: Series, bar_index: int, swing: SwingPoint, direction: Direction) -> bool:
    """S7-R21/R22 versus S7-R23: the body must close back **inside** the structural level."""
    close = dec(series.close[bar_index])
    if direction is Direction.SHORT:
        return close < swing.price
    return close > swing.price


def _nearest_same_kind_gap(
    swing: SwingPoint, pivots: Sequence[SwingPoint], at_index: int
) -> Decimal | None:
    """Price distance from ``swing`` to the closest other confirmed pivot of the same kind.

    ``None`` when there is no second same-kind pivot to compare against, in which case the
    separation filter has nothing to reject (S7-R28 is about *pairs* of swings).
    """
    others = [
        p
        for p in P.confirmed_swings(pivots, at_index)
        if p.kind is swing.kind and p.id != swing.id
    ]
    if not others:
        return None
    return min(abs(p.price - swing.price) for p in others)


def _objects_at_price(
    series: Series,
    config: Config,
    price: Decimal,
    levels: Sequence[Level],
    zones: Sequence[Zone],
    at_index: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Pre-marked levels (P9 tolerance band) and zones (box containment) at ``price``."""
    level_ids = tuple(
        lv.id
        for lv in levels
        if P.price_at_level(series, config, price, lv.price_at(at_index), at_index=at_index)
    )
    zone_ids = tuple(z.id for z in zones if z.box_bottom <= price <= z.box_top)
    return level_ids, zone_ids


# --------------------------------------------------------------------------- evaluation


def evaluate(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    levels: Sequence[Level] = (),
    zones: Sequence[Zone] = (),
    trend: Trend | None = None,
) -> list[SFPEvaluation]:
    """Apply every §5.8 filter to every raid candidate and report the verdicts.

    Parameters
    ----------
    levels, zones :
        The **pre-marked** objects from pipeline stages 3 / 7 / 8 — the S/R levels and
        supply/demand zones another detector produced on this same series.  They are an input,
        never something this module derives: CF-32 step 7 evaluates the SFP *only after* price
        interacts with a level from those stages, and ``sfp_standalone_enabled = false`` makes an
        SFP with nothing pre-marked at the swept price a non-trade (S7-R30).  Pass them in the
        same timeframe as ``series``; a bar index from another timeframe is meaningless.
    trend :
        The prevailing trend for the ``sfp_trend_veto`` test (S7-R31).  Under Q7's
        ``sfp_governing_timeframe = "highest_valid"`` this must be the trend of the timeframe
        :func:`governing_timeframe` resolves to — pass it explicitly when ``series`` is not that
        timeframe.  When omitted it is classified from ``series`` with P11.
    """
    all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
    prevailing = (
        trend
        if trend is not None
        else structure_state(series, config, pivots=all_pivots).trend
    )
    out: list[SFPEvaluation] = []
    per_bar: dict[int, int] = {}

    for bar_index, swing, direction in raid_candidates(series, config, pivots=all_pivots):
        reasons: list[str] = []
        atr = P.atr_at(series, config, bar_index)

        # 1. no close back inside => not an SFP, no trade (S7-R23, S8-R3)
        if not _closes_back_inside(series, bar_index, swing, direction):
            reasons.append(
                f"close {dec(series.close[bar_index])} did not close back inside "
                f"{swing.price} (S7-R23)"
            )

        # 2. adjacency (S7-R25)
        bars_between = bar_index - swing.bar_index
        if bars_between < config.sfp_min_bars_between:
            reasons.append(
                f"SFP candle is {bars_between} bars from the swing it raids "
                f"< sfp_min_bars_between {config.sfp_min_bars_between} (S7-R25)"
            )

        # 3. swing separation (S7-R28, S8-R4)
        gap = _nearest_same_kind_gap(swing, all_pivots, bar_index)
        separation_atr = (gap / atr) if (gap is not None and atr > 0) else Decimal(0)
        if gap is not None and separation_atr < dec(config.sfp_min_swing_separation_atr):
            reasons.append(
                f"swing separation {separation_atr:.2f} ATR "
                f"< sfp_min_swing_separation_atr {config.sfp_min_swing_separation_atr} (S7-R28)"
            )

        # 4. trend veto (S7-R31)
        if config.sfp_trend_veto:
            if direction is Direction.SHORT and prevailing is Trend.UP:
                reasons.append("sfp_trend_veto: bearish SFP against an up trend (S7-R31)")
            if direction is Direction.LONG and prevailing is Trend.DOWN:
                reasons.append("sfp_trend_veto: bullish SFP against a down trend (S7-R31)")

        # 5. no pre-marked level or zone at the swept price (S7-R30, CF-20)
        swept = raid_price(swing, config)
        level_ids, zone_ids = _objects_at_price(
            series, config, swept, levels, zones, bar_index
        )
        if not config.sfp_standalone_enabled and not level_ids and not zone_ids:
            reasons.append(
                f"no pre-marked level or zone at {swept}; "
                "sfp_standalone_enabled is false (S7-R30)"
            )

        # 6. chase cap / deep wick (S5-R7, CF-20) — bans the market entry, not the pattern
        close_price = dec(series.close[bar_index])
        distance = abs(close_price - swept)
        close_distance_atr = (distance / atr) if atr > 0 else Decimal(0)
        chase_allowed = close_distance_atr <= dec(config.sfp_max_close_distance_atr)
        chase_reason = (
            f"confirming close is {close_distance_atr:.2f} ATR from the swept level "
            f"> sfp_max_close_distance_atr {config.sfp_max_close_distance_atr}; "
            "market entry banned, resting a limit at the swept level instead (S5-R7, S7-R27)"
        )

        if reasons:
            out.append(
                SFPEvaluation(
                    bar_index=bar_index,
                    swing_id=swing.id,
                    direction=direction,
                    accepted=False,
                    sfp=None,
                    reasons=tuple(reasons),
                )
            )
            continue

        raid_extreme = dec(series.high[bar_index] if direction is Direction.SHORT else series.low[bar_index])
        buffer = P.stop_buffer(series, config, bar_index)
        stop_price = P.apply_stop_buffer(raid_extreme, direction, buffer)
        if config.sfp_entry_price == "next_open" and bar_index + 1 < len(series):
            entry_reference = dec(series.open[bar_index + 1])
        else:
            entry_reference = close_price
        entry_price = entry_reference if chase_allowed else swept
        entry_kind: EntryKind = "confirming_close" if chase_allowed else "limit_at_swept_level"
        stop_pct = (
            abs(stop_price - entry_price) / entry_price * Decimal(100)
            if entry_price != 0
            else Decimal(0)
        )
        src = ["CF-20", "S8-R3", "S7-R21" if direction is Direction.SHORT else "S7-R22"]
        src.append("sfp_entry_price=" + config.sfp_entry_price)
        src.append("S7-R24")
        src.append("S7-R25")
        src.append("S7-R28")
        if config.sfp_trend_veto:
            src.append("S7-R31")
        if not config.sfp_standalone_enabled:
            src.append("S7-R30")
        if not chase_allowed:
            src.extend(["S5-R7", "S5-R6", "S7-R27", "S8-R6"])
        src.extend(["CF-14", "P19"])

        n = per_bar.get(bar_index, 0)
        per_bar[bar_index] = n + 1
        sfp = SFP(
            id=object_id(series, "sfp", bar_index, n),
            symbol=series.symbol,
            tf=series.tf,
            direction=direction,
            bar_index=bar_index,
            entry_index=bar_index,
            swing_id=swing.id,
            swing_index=swing.bar_index,
            swept_price=swept,
            structure_price=swing.price,
            raid_extreme=raid_extreme,
            close_price=close_price,
            entry_price=entry_price,
            entry_kind=entry_kind,
            chase_allowed=chase_allowed,
            stop_price=stop_price,
            stop_pct=stop_pct,
            stop_is_capitulation_wick=P.is_capitulation_wick(
                series, config, bar_index, "upper" if direction is Direction.SHORT else "lower"
            ),
            close_distance_atr=close_distance_atr,
            swing_separation_atr=separation_atr,
            bars_between=bars_between,
            trend=prevailing,
            level_ids=level_ids,
            zone_ids=zone_ids,
            reasons=() if chase_allowed else (chase_reason,),
            source_ids=tuple(src),
        )
        out.append(
            SFPEvaluation(
                bar_index=bar_index,
                swing_id=swing.id,
                direction=direction,
                accepted=True,
                sfp=sfp,
                reasons=() if chase_allowed else (chase_reason,),
            )
        )
    out.sort(key=lambda e: (e.bar_index, e.direction.value))
    return out


def find_sfps(
    series: Series,
    config: Config,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    levels: Sequence[Level] = (),
    zones: Sequence[Zone] = (),
    trend: Trend | None = None,
) -> list[SFP]:
    """The accepted SFPs only, newest last."""
    return [
        ev.sfp
        for ev in evaluate(
            series, config, pivots=pivots, levels=levels, zones=zones, trend=trend
        )
        if ev.accepted and ev.sfp is not None
    ]


# --------------------------------------------------------------------------- detector


class SFPDetector:
    """SPEC.md §5.8 detector (pipeline stage 13) — INTERFACES.md §6 protocol.

    Stage 13 is deliberately last (``sfp_evaluated_last``, CF-32 / PL-5): the SFP is second-order
    confluence attached to a level that was already on the chart, which is why :meth:`detect`
    takes ``levels`` and ``zones`` as inputs.
    """

    name = "swing_failure_pattern"
    stage = 13
    source_ids = (
        "CF-20",
        "S5-R4",
        "S5-R5",
        "S5-R6",
        "S5-R7",
        "S7-R21",
        "S7-R22",
        "S7-R23",
        "S7-R24",
        "S7-R25",
        "S7-R27",
        "S7-R28",
        "S7-R30",
        "S7-R31",
        "S8-R3",
        "S8-R4",
        "S8-R5",
        "S8-R6",
        "P1",
        "P9",
        "P19",
    )
    produces = ("sfp",)

    #: S7-R24 — the entry reference is always a *closed* candle's close, never an intrabar price.
    mid_candle_entry_forbidden = True

    def detect(
        self,
        series: Series,
        config: Config,
        *,
        levels: Sequence[Level] = (),
        zones: Sequence[Zone] = (),
        trend: Trend | None = None,
        pivots: Sequence[SwingPoint] | None = None,
    ) -> list[SFP]:
        return find_sfps(
            series, config, pivots=pivots, levels=levels, zones=zones, trend=trend
        )

    def evaluate(
        self,
        series: Series,
        config: Config,
        *,
        levels: Sequence[Level] = (),
        zones: Sequence[Zone] = (),
        trend: Trend | None = None,
        pivots: Sequence[SwingPoint] | None = None,
    ) -> list[SFPEvaluation]:
        """Diagnostic view: every candidate with its accept/reject reasons."""
        return evaluate(
            series, config, pivots=pivots, levels=levels, zones=zones, trend=trend
        )

    def to_confluence(
        self, objects: Sequence[Any], config: Config
    ) -> list[P.ConfluenceObject]:
        """An SFP scores at the level it swept — that is where the confluence stack sits."""
        return [
            P.ConfluenceObject(
                id=obj.id,
                price=obj.swept_price,
                obj_class="sfp",
                tf=obj.tf,
                source_ids=obj.source_ids,
            )
            for obj in objects
            if isinstance(obj, SFP)
        ]
