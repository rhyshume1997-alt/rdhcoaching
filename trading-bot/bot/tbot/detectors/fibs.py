"""tbot.detectors.fibs — SPEC.md §5.9: fibonacci retracements (pipeline stage 10).

Three tradeable levels, and only three
--------------------------------------
``fib_levels_active = [0.618, 0.66, 0.786]`` (S6-R33, CF-33).  The **golden pocket** is the band
``[0.618, 0.66]`` — he uses 0.66 and notes others use 0.65 (S6-R32, S6-A23) — and the **0.786** is
a *separate* level, not a synonym for it; S8's interchangeable usage is a verbal slip
(S8 ``[01:07:57]``).  Entry sits at the golden pocket, the DCA at the 0.786 (``fib_entry_level``,
``fib_dca_level``; TBOT1-R5, S6-R15).  The 0.886 is in his recommended five-level list but he has
explicitly **not** back-tested it, so ``fib_886_enabled = false`` (S6-A22, precedence rule 4).
Fib channels, spirals, arcs and non-standard levels (0.113, 0.13, 2.14) are out of scope
entirely (S6 exclusions).

Draw convention and anchors
---------------------------
``fib_draw_convention = "s6"``: a **bullish** fib (looking for a bounce / long) is drawn swing low
→ swing high; a **bearish** fib (rejection / short) swing high → swing low (S6-R34, S6-R35,
S6-C6, S7-R1).  TBOT1's inverted narration is rejected as a live-session artefact, and is
available as ``"tbot1"`` for the sweep.  Anchors come from P1 on the structure timeframe under
``fib_anchor_selection`` — ``"most_recent_qualifying_swing_pair"`` by default.  That selection is
**[OUR CHOICE]**: his own is admittedly arbitrary ("you can take it from many swing low points,
it doesn't matter which one", S6-A16, TBOT1-A2).

Fibs are subordinate — the hard rule
------------------------------------
Two separate consequences, both implemented here:

1. **A fib may never be the sole basis for a trade** (S6-R30, ``single_class_trade_forbidden``).
   :func:`sole_basis_veto` returns the veto string when nothing but fibs sits at a price;
   :meth:`FibDetector.to_confluence` emits class ``"fib"`` and nothing else, so the P14 two-class
   rule catches the same case downstream.
2. **Where a fib disagrees with drawn S/R, the S/R wins** (S6-R38, ``fib_loses_ties_to_sr``,
   PL-3).  "Everything is noise when there are support and resistance lines already drawn."
   :func:`apply_sr_precedence` re-prices a fib that lands inside a drawn level's P9 tolerance
   band (or inside a zone box) onto the S/R price itself, so the ladder is built on the S/R and
   the fib only adds weight.  Fibs are drawn at stage 10, *after* levels (3) and zones (7),
   which is what "fibs are drawn last" means operationally (CF-32).

Config keys read here (owned by this module per INTERFACES.md §7): ``fib_levels_active``,
``golden_pocket_band``, ``fib_entry_level``, ``fib_dca_level``, ``fib_886_enabled``,
``fib_draw_convention``, ``fib_anchor_selection``, ``fib_loses_ties_to_sr``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Sequence

from .. import primitives as P
from ..config import Config
from ..models import Direction, FibLevel, Level, Series, SwingKind, SwingPoint, Zone, dec
from .base import object_id

__all__ = [
    "FibAnchor",
    "RATIO_886",
    "select_anchor",
    "active_ratios",
    "fib_price",
    "role_of",
    "build_fibs",
    "apply_sr_precedence",
    "sole_basis_veto",
    "extension_levels",
    "FibDetector",
]

#: The fifth level of his recommended set, gated by ``fib_886_enabled`` (S6-A22).
RATIO_886 = Decimal("0.886")

FibRole = Literal["entry", "dca", "none"]


@dataclass(frozen=True, slots=True)
class FibAnchor:
    """The swing pair a fib is drawn from.

    ``direction`` is the trade direction the fib serves: ``LONG`` for a bullish fib (drawn low →
    high under the S6 convention), ``SHORT`` for a bearish one.  ``leg`` is ``high - low`` and is
    always positive.
    """

    low: SwingPoint
    high: SwingPoint
    direction: Direction
    drawn_from_index: int      #: the first anchor in drawing order
    drawn_to_index: int        #: the second anchor in drawing order
    confirmed_at_index: int    #: the bar both anchors became usable (P1 no-repaint)

    @property
    def leg(self) -> Decimal:
        return self.high.price - self.low.price


def select_anchor(
    series: Series,
    config: Config,
    direction: Direction,
    *,
    pivots: Sequence[SwingPoint] | None = None,
    at_index: int | None = None,
) -> FibAnchor | None:
    """The swing pair to draw from, per ``fib_anchor_selection``.

    ``"most_recent_qualifying_swing_pair"`` (default, **[OUR CHOICE]**) — under the S6 convention
    a bullish fib needs a swing **low** followed by a later swing **high** (the up-leg being
    retraced); a bearish fib needs a swing high followed by a later swing low.  The pair chosen is
    the one whose *second* anchor is most recent, paired with the opposing pivot immediately
    preceding it; a pair that is degenerate (``high <= low``) is skipped rather than fudged.

    ``"largest_leg"`` — the qualifying pair with the biggest ``high - low``.

    ``"manual"`` — no automatic selection; returns ``None`` so the caller must supply anchors.

    Only pivots confirmed at or before ``at_index`` are used, so this is safe bar-by-bar.
    """
    if config.fib_anchor_selection == "manual":
        return None
    idx = len(series) - 1 if at_index is None else (at_index if at_index >= 0 else len(series) + at_index)
    usable = P.confirmed_swings(
        list(pivots) if pivots is not None else P.swing_points(series, config), idx
    )
    convention_long = direction is Direction.LONG
    if config.fib_draw_convention == "tbot1":
        convention_long = not convention_long

    pairs: list[FibAnchor] = []
    for j, second in enumerate(usable):
        want_second = SwingKind.HIGH if convention_long else SwingKind.LOW
        if second.kind is not want_second:
            continue
        firsts = [
            p
            for p in usable[:j]
            if p.kind is not want_second and p.bar_index < second.bar_index
        ]
        if not firsts:
            continue
        first = firsts[-1]      # the opposing pivot immediately preceding the second anchor
        low, high = (first, second) if convention_long else (second, first)
        if high.price <= low.price:
            continue
        pairs.append(
            FibAnchor(
                low=low,
                high=high,
                direction=direction,
                drawn_from_index=first.bar_index,
                drawn_to_index=second.bar_index,
                confirmed_at_index=max(low.confirmed_at_index, high.confirmed_at_index),
            )
        )
    if not pairs:
        return None
    if config.fib_anchor_selection == "largest_leg":
        return max(pairs, key=lambda a: (a.leg, a.drawn_to_index))
    return max(pairs, key=lambda a: (a.drawn_to_index, a.leg))


def active_ratios(config: Config) -> tuple[Decimal, ...]:
    """The tradeable ratios: ``fib_levels_active``, plus 0.886 only when ``fib_886_enabled``.

    Nothing else is ever emitted — the restriction to these levels *is* the rule (S6-R32, S6-R33).
    """
    ratios = [dec(r) for r in config.fib_levels_active]
    if config.fib_886_enabled and RATIO_886 not in ratios:
        ratios.append(RATIO_886)
    return tuple(sorted(set(ratios)))


def fib_price(anchor: FibAnchor, ratio: Decimal) -> Decimal:
    """Retracement price of ``ratio`` on ``anchor``.

    Bullish (low → high): the retracement comes **down** from the high, ``high - ratio * leg``.
    Bearish (high → low): it comes **up** from the low, ``low + ratio * leg``.
    """
    if anchor.direction is Direction.LONG:
        return anchor.high.price - ratio * anchor.leg
    return anchor.low.price + ratio * anchor.leg


def in_golden_pocket(ratio: Decimal, config: Config) -> bool:
    """Is ``ratio`` inside ``golden_pocket_band`` (default ``[0.618, 0.66]``, CF-33)?"""
    lo, hi = (dec(x) for x in config.golden_pocket_band)
    return lo <= ratio <= hi


def role_of(ratio: Decimal, config: Config) -> FibRole:
    """``"entry"`` at the golden pocket, ``"dca"`` at the 0.786 (TBOT1-R5, S6-R15, CF-33)."""
    if ratio in {dec(x) for x in config.fib_entry_level}:
        return "entry"
    if ratio == dec(config.fib_dca_level):
        return "dca"
    return "none"


def build_fibs(
    series: Series,
    config: Config,
    anchor: FibAnchor,
) -> list[FibLevel]:
    """The active ratios priced on ``anchor``, ordered by ratio.

    Every level carries ``anchor_low_index`` / ``anchor_high_index`` so the draw is reproducible,
    and ``in_golden_pocket`` for the CF-33 band.  Ids are keyed on the anchor's confirmation bar,
    which is the bar the fib became drawable.
    """
    out: list[FibLevel] = []
    for n, ratio in enumerate(active_ratios(config)):
        src = ["CF-33", "CF-34", "S6-R33", "S6-R34" if anchor.direction is Direction.LONG else "S6-R35"]
        if in_golden_pocket(ratio, config):
            src.append("S6-R32")
        role = role_of(ratio, config)
        if role == "entry":
            src.append("TBOT1-R5")
        elif role == "dca":
            src.append("S6-R15")
        if ratio == RATIO_886:
            src.append("S6-A22")
        out.append(
            FibLevel(
                id=object_id(series, "fib", anchor.confirmed_at_index, n),
                symbol=series.symbol,
                tf=series.tf,
                ratio=ratio,
                price=fib_price(anchor, ratio),
                anchor_low_index=anchor.low.bar_index,
                anchor_high_index=anchor.high.bar_index,
                direction=anchor.direction,
                in_golden_pocket=in_golden_pocket(ratio, config),
                source_ids=tuple(src),
            )
        )
    return out


# --------------------------------------------------------------------------- subordination


def apply_sr_precedence(
    series: Series,
    config: Config,
    fibs: Sequence[FibLevel],
    *,
    levels: Sequence[Level] = (),
    zones: Sequence[Zone] = (),
    at_index: int | None = None,
) -> list[FibLevel]:
    """S6-R38 / PL-3: **drawn S/R wins every tie with a fib** (``fib_loses_ties_to_sr``).

    A fib landing inside a drawn level's P9 tolerance band — or inside a zone box — is re-priced
    onto that S/R price and gains ``"S6-R38"`` in its ``source_ids``.  The fib then adds weight at
    the level he actually drew instead of pulling the entry a few ticks off it; a fib with no S/R
    near it is returned untouched, still as confluence only.  Ties among several S/R objects break
    to the **nearest** price, then to the lowest object id, so the result is deterministic.

    With ``fib_loses_ties_to_sr = false`` (the sweep alternative) the fibs are returned unchanged.
    """
    if not config.fib_loses_ties_to_sr:
        return list(fibs)
    idx = len(series) - 1 if at_index is None else (at_index if at_index >= 0 else len(series) + at_index)
    out: list[FibLevel] = []
    for fib in fibs:
        winners: list[tuple[Decimal, str, Decimal]] = []
        for lv in levels:
            lv_price = lv.price_at(idx)
            if P.price_at_level(series, config, fib.price, lv_price, at_index=idx):
                winners.append((abs(fib.price - lv_price), lv.id, lv_price))
        for z in zones:
            if z.box_bottom <= fib.price <= z.box_top:
                edge = z.outer_edge
                winners.append((abs(fib.price - edge), z.id, edge))
        if not winners:
            out.append(fib)
            continue
        _, _, price = min(winners, key=lambda w: (w[0], w[1]))
        out.append(
            FibLevel(
                id=fib.id,
                symbol=fib.symbol,
                tf=fib.tf,
                ratio=fib.ratio,
                price=price,
                anchor_low_index=fib.anchor_low_index,
                anchor_high_index=fib.anchor_high_index,
                direction=fib.direction,
                in_golden_pocket=fib.in_golden_pocket,
                source_ids=fib.source_ids + ("S6-R38", "CF-32"),
            )
        )
    return out


def sole_basis_veto(
    fib: FibLevel, other_objects: Sequence[P.ConfluenceObject]
) -> str | None:
    """S6-R30: a fib is **never** the sole basis for a trade.

    Returns the veto string for ``Setup.vetoes`` when ``other_objects`` holds nothing of a class
    other than ``"fib"``, otherwise ``None``.  The caller passes the objects P14 already merged at
    the candidate price; this is the §5.9 statement of the same rule
    ``single_class_trade_forbidden`` enforces globally in ``confluence.py``.
    """
    if any(o.obj_class != "fib" for o in other_objects):
        return None
    return (
        f"fib {fib.ratio} at {fib.price} has no non-fib confluence; "
        "fibs are never a standalone trade (S6-R30)"
    )


def extension_levels(
    series: Series,
    config: Config,
    *,
    swing_low: SwingPoint,
    swing_high: SwingPoint,
    pullback_low: SwingPoint,
    count: int,
) -> list[FibLevel]:
    """Trend-based fib **extensions** — price discovery only (S6-R36, CF-27).

    Drawn swing low → swing high (the all-time high) → new swing low, projecting ``count``
    take-profit levels above the pullback low.  Unlike retracements, *all* levels are used here,
    not just the golden pocket and the 0.786.  ``count`` is supplied by the caller: the cap lives
    in ``tp_count_price_discovery_max``, which ``planner.py`` owns.
    """
    if count < 1:
        raise ValueError(f"extension_levels: count must be >= 1, got {count}")
    leg = swing_high.price - swing_low.price
    if leg <= 0:
        raise ValueError("extension_levels: swing_high must be above swing_low")
    anchor_bar = max(
        swing_low.confirmed_at_index, swing_high.confirmed_at_index, pullback_low.confirmed_at_index
    )
    out: list[FibLevel] = []
    for n in range(count):
        ratio = dec(n + 1)
        out.append(
            FibLevel(
                id=object_id(series, "fib_extension", anchor_bar, n),
                symbol=series.symbol,
                tf=series.tf,
                ratio=ratio,
                price=pullback_low.price + ratio * leg,
                anchor_low_index=swing_low.bar_index,
                anchor_high_index=swing_high.bar_index,
                direction=Direction.LONG,
                in_golden_pocket=False,
                source_ids=("S6-R36", "CF-27"),
            )
        )
    return out


# --------------------------------------------------------------------------- detector


class FibDetector:
    """SPEC.md §5.9 detector (pipeline stage 10) — INTERFACES.md §6 protocol.

    :meth:`detect` draws both a bullish and a bearish fib from the most recent qualifying swing
    pair and returns the active ratios of each, newest last.  Supply ``levels`` / ``zones`` to get
    the S6-R38 precedence applied in the same call; ``series`` must be the structure-timeframe
    series (CF-34 anchors fibs there).
    """

    name = "fibs"
    stage = 10
    source_ids = (
        "CF-32",
        "CF-33",
        "CF-34",
        "S6-R15",
        "S6-R30",
        "S6-R32",
        "S6-R33",
        "S6-R34",
        "S6-R35",
        "S6-R36",
        "S6-R38",
        "S7-R1",
        "TBOT1-R5",
        "P1",
        "P9",
    )
    produces = ("fib",)

    #: S6-R30 — restated as a class fact so a caller cannot miss it.
    standalone_forbidden = True

    def detect(
        self,
        series: Series,
        config: Config,
        *,
        levels: Sequence[Level] = (),
        zones: Sequence[Zone] = (),
        pivots: Sequence[SwingPoint] | None = None,
        at_index: int | None = None,
    ) -> list[FibLevel]:
        all_pivots = list(pivots) if pivots is not None else P.swing_points(series, config)
        out: list[FibLevel] = []
        for direction in (Direction.LONG, Direction.SHORT):
            anchor = select_anchor(
                series, config, direction, pivots=all_pivots, at_index=at_index
            )
            if anchor is None:
                continue
            fibs = build_fibs(series, config, anchor)
            out.extend(
                apply_sr_precedence(
                    series, config, fibs, levels=levels, zones=zones, at_index=at_index
                )
            )
        out.sort(key=lambda f: (f.anchor_high_index, f.direction.value, f.ratio))
        return out

    def to_confluence(
        self, objects: Sequence[Any], config: Config
    ) -> list[P.ConfluenceObject]:
        return [
            P.ConfluenceObject(
                id=obj.id,
                price=obj.price,
                obj_class="fib",
                tf=obj.tf,
                source_ids=obj.source_ids,
            )
            for obj in objects
            if isinstance(obj, FibLevel)
        ]
