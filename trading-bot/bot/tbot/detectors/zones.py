"""tbot.detectors.zones — SPEC.md §5.5 supply / demand zones.

Implements the trader's **non-textbook** definition and the textbook one side by side (CF-10):

* ``continuation`` (his) — up-impulse → horizontal consolidation → continues **up** (demand);
  down-impulse → consolidation → continues **down** (supply).  S5-R15, S6-R4, S6-R5.
* ``reversal`` (textbook) — down → consolidation → up (demand); up → consolidation → down
  (supply).  S5 ``[00:32:06]``, S6 ``[00:32:38]``, TBOT1 §2.

``zone_direction_mode`` selects which classes are emitted; the default emits both, because he
demonstrably trades both and never gives a selection rule (S6-A26).

Detection follows the SPEC.md §5.5 algorithm exactly, and every step is a primitive:

1. impulse leg — **P2** :func:`~tbot.primitives.find_directional_changes`;
2. consolidation window — **P13** :func:`~tbot.primitives.check_consolidation` plus the S5-R17
   two-full-bodies minimum with the half-candle rule (:func:`count_bodies`);
3. box — **P5** :func:`~tbot.primitives.zone_box` (bodies, small wicks folded in, giant wicks
   excluded: CF-13, S5-R19, S6-R9, S7-R7);
4. breakout, then the move away — **P10** :func:`~tbot.primitives.sufficient_gap`;
5. both gap tests must pass — the per-timeframe percentage table **and** the ATR multiple
   (CF-11, S5-R16; the 2H/4H/8H/12H rows and the 3D+ row are **[OUR CHOICE]**);
6. depth must sit in ``[min_zone_depth_atr, max_zone_depth_atr]`` — CF-12; **the ATR
   normalisation is OURS**, his figures are raw dollars ("$100 is way too tiny", S6-R48) and do
   not transfer between instruments;
7. midpoint frozen at creation (**P6**, CF-08, S5-A11); entry price from **P20**
   :func:`~tbot.primitives.points_of_most_touch`.

**F1 nested geometry, off by default.**  ``zone_wick_band_enabled`` (default ``False``) adds a
second, outer band to every zone: the frames show him drawing an inner box on candle **bodies**
and an outer box extended to the **wick** extreme (FRAME_FINDINGS.md F1, S6 frame 52:38).  With
it on, ``Zone.box_top``/``box_bottom`` still hold the body core and price the entries, while
``Zone.wick_band_top``/``wick_band_bottom`` hold the band the stop is placed beyond — see
:func:`wick_band`.  With it off (the default) no band is built and every number this module
produces is byte-identical to the single-box model.  The finding rests on **one** clear frame and
is labelled as such; it needs corroboration before it becomes the default geometry.

Lifecycle (CONFLICTS.md CF-07 / CF-08):

* invalidation is **50 % of zone depth**, measured on the zone *as originally drawn*, by any
  **wick** through the midpoint (``zone_fill_measure = "wick_touch"``).  Beyond it the setup is
  dead and no re-take is permitted — S5-R28, S6-R10;
* while under 50 % the zone may be re-taken **repeatedly** — S5-R28, S6-R25.  ``touch_count``
  counts those replays; the size decay that consumes it (``touch_size_decay``) belongs to
  ``risk.py``, and the "zones use the fill rule, not the touch limit" switch
  (``zone_touch_uses_fill_rule_not_count``) belongs to ``detectors/levels.py`` — this module
  reads neither;
* a dead zone is re-armed when an independent higher-timeframe level with
  ``touch_count <= dead_zone_rescue_max_touches`` sits inside the remaining half, and the trade
  is then taken **on that level, not on the zone** (CF-08, S7-R4, S7-C3) — see
  :func:`rescue_dead_zones`.

This module owns the CF-08 / CF-10 / CF-11 / CF-12 / CF-13 configuration keys listed in
INTERFACES.md §7; :func:`min_size_atr` and :func:`fill_invalidation_pct` hand the two values
``detectors/orderblocks.py`` needs across the module boundary, so that the owner stays the only
reader.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from ..config import Config
from ..models import (
    Box,
    Direction,
    Level,
    Series,
    Timeframe,
    Zone,
    ZoneClass,
    ZoneSide,
    dec,
)
from .. import primitives as P
from .base import object_id

__all__ = [
    "SupplyDemandZoneDetector",
    "ZoneRejection",
    "count_bodies",
    "death_index",
    "fill_invalidation_pct",
    "max_size_atr",
    "min_size_atr",
    "rescue_dead_zones",
    "wick_band",
    "zone_strength",
    "zone_touch_windows",
]

_LOG = logging.getLogger(__name__)

_ZERO = Decimal(0)
_HALF = Decimal("0.5")


# --------------------------------------------------------------------------- config accessors

def min_size_atr(config: Config) -> Decimal:
    """``min_zone_depth_atr`` (CF-12) — the floor a zone **or an order block** must clear.

    SPEC.md §5.6 gives an order block the same minimum (``size_atr >= min_zone_depth_atr``, the
    machine form of "smaller than a pinky nail" and "$100 is way too tiny", S7-R6, S6-R48).  The
    key is owned here, so ``detectors/orderblocks.py`` receives the value through this accessor
    instead of reading a key that is not its own (INTERFACES.md §7).
    """
    return dec(config.min_zone_depth_atr)


def max_size_atr(config: Config) -> Decimal:
    """``max_zone_depth_atr`` (CF-12, S8-R23 "way too wide and not concise")."""
    return dec(config.max_zone_depth_atr)


def fill_invalidation_pct(config: Config) -> Decimal:
    """``zone_fill_invalidation_pct`` (CF-08) — 50 % by default, the S7 alternative is 70/80.

    Handed to ``detectors/orderblocks.py``, which needs to know whether the S7 setting is in
    force (it switches the OB fill measure to **P15**, SPEC.md §5.6 / S7-R3).
    """
    return dec(config.zone_fill_invalidation_pct)


# --------------------------------------------------------------------------- rejection record

@dataclass(frozen=True, slots=True)
class ZoneRejection:
    """A zone candidate that did not survive, with the ``reasons`` of the primitive that killed it.

    INTERFACES.md §6.4: rejected objects must not be returned, but an interesting rejection (a
    zone that failed the gap test) is logged with the primitive's own wording — never re-worded.
    """

    formation_start_index: int
    formation_end_index: int
    breakout_index: int
    side: ZoneSide
    zone_class: ZoneClass
    reasons: tuple[str, ...]


# --------------------------------------------------------------------------- S5-R17 body count

def count_bodies(
    series: Series, config: Config, box: Box, start_index: int, end_index: int
) -> Decimal:
    """S5-R17 — candle bodies inside ``box``, counted **his way**, in halves.

    His rule, verbatim in scope: *"The full candle body must be within the zone.  If you have
    half of the candle body closing or so opening within the zone and it closes outside, that is
    considered a half candle.  Two half candles make a full candle"* (S5 ``[00:47:48]``,
    ``[00:49:30]``), and *"one-and-a-half candles is not valid"*.

    So each bar in the inclusive window — **extended by the bar on either side**, because those
    are precisely the candles that straddle the edge of a drawn box — scores

    * ``1.0`` when both body ends sit inside the box,
    * ``0.5`` when exactly one end sits inside it (it opened *or* closed inside and left),
    * ``0`` otherwise, including a body that engulfs the whole box — **[OUR CHOICE]**: he only
      ever describes a candle poking out of one side.

    Wicks never count (S5-R17, CF-13).  The sum is a multiple of ``0.5``; the caller compares it
    against ``min_zone_bodies`` (default 2, S5-R17), so a 1.5-candle consolidation is rejected
    exactly as he rejects it.
    """
    lo = max(0, min(start_index, end_index) - 1)
    hi = min(len(series) - 1, max(start_index, end_index) + 1)
    top, bottom = box.top, box.bottom
    total = _ZERO
    for i in range(lo, hi + 1):
        body_high = dec(series.body_high[i])
        body_low = dec(series.body_low[i])
        inside_high = bottom <= body_high <= top
        inside_low = bottom <= body_low <= top
        if inside_high and inside_low:
            total += Decimal(1)
        elif inside_high or inside_low:
            total += _HALF
    return total


# --------------------------------------------------------------------------- F1 wick band

def wick_band(
    series: Series,
    config: Config,
    box: Box,
    side: ZoneSide,
    start_index: int,
    end_index: int,
) -> tuple[Decimal, Decimal] | None:
    """**F1** — the outer band of the nested two-box zone geometry, or ``None`` when disabled.

    Reference frame: **S6 52:38**, LINK 1D, his own label *"Bullish OB"*.  Paused and measured, he
    has drawn **two nested boxes**, not one: an inner, darker box whose lower edge sits on the
    candle **bodies**, and an outer, lighter box sharing the same upper edge but extended down to
    the **wick** lows.  The wick band measured ≈83 % of the inner body-box height.
    ``FRAME_FINDINGS.md`` F1 records the measurement; three further frames (S5 1:30:30 BONK 12H,
    S5 1:24:41 boxes A and B on ZEC 1D) corroborate the *body* anchoring with the wick left
    outside, but show only the single inner box.

    **What this reconciles.**  The transcripts leave two statements in tension: *"draw your boxes
    on candle bodies"* (S5, S6 — the basis of P5 / CF-13) and *"usually wicks are going to give
    you that entry point"* (S5 ``[01:05:00]``).  The frames say both are true of the same drawn
    object because it is two objects: the **body box is the core, where the entries are priced**
    (P20 points-of-most-touch runs on it, unchanged), and the **wick band is the outer extent,
    where the stop goes** (CF-14 anchors beyond it).  Neither statement has to give way.

    Geometry.  The band shares the body box's *near* edge — the one price reaches first, and the
    one the frame shows unchanged between the two boxes — and extends past the *far* edge to the
    wick extreme of the formation window: down to ``min(low)`` for a demand zone, up to
    ``max(high)`` for a supply zone.

    Outlier rule.  ``zone_wick_band_max_ratio`` (1.0) caps the extension at that multiple of the
    body-box height.  A wick reaching further than the whole body box is treated as an outlier
    and **excluded** — the band collapses back onto the body edge — which is the same instinct as
    the CF-13 giant-wick exclusion, applied one level out.  The measured example was 83 %, so the
    default cap admits it with room to spare.

    **Confidence: single-frame observation, needs corroboration.**  ``zone_wick_band_enabled``
    defaults to ``False`` and this function then returns ``None``, so no ``Zone`` carries a band
    and every downstream number is byte-identical to the single-box model.  FRAME_FINDINGS.md F1
    asks for 3–5 more frames of him drawing a zone before this becomes the default geometry.
    """
    if not config.zone_wick_band_enabled:
        return None
    lo = min(start_index, end_index)
    hi = max(start_index, end_index)
    lo = max(0, lo)
    hi = min(len(series) - 1, hi)
    wick_high = dec(float(series.high[lo:hi + 1].max()))
    wick_low = dec(float(series.low[lo:hi + 1].min()))

    core_height = box.height
    cap = dec(config.zone_wick_band_max_ratio) * core_height

    if side is ZoneSide.DEMAND:
        extension = box.bottom - wick_low
        if extension <= _ZERO or extension > cap:
            return box.top, box.bottom          # no wick below the body, or an outlier: excluded
        return box.top, wick_low
    extension = wick_high - box.top
    if extension <= _ZERO or extension > cap:
        return box.top, box.bottom
    return wick_high, box.bottom


# --------------------------------------------------------------------------- lifecycle helpers

def death_index(
    series: Series,
    config: Config,
    box: Box,
    side: ZoneSide,
    *,
    from_index: int,
    to_index: int | None = None,
) -> int | None:
    """First bar at which **P6** calls the zone dead, or ``None`` while it is still alive.

    :func:`~tbot.primitives.measure_fill` tracks the deepest penetration so far, which is
    monotone non-decreasing in ``to_index`` — so the death bar is found by bisection over the
    primitive rather than by re-deriving the fill measurement here (INTERFACES.md §1.1).
    """
    end = len(series) - 1 if to_index is None else to_index
    lo = from_index + 1
    if lo > end:
        return None
    if not P.measure_fill(series, config, box, side, from_index=from_index, to_index=end).is_dead:
        return None
    while lo < end:
        mid = (lo + end) // 2
        if P.measure_fill(series, config, box, side, from_index=from_index, to_index=mid).is_dead:
            end = mid
        else:
            lo = mid + 1
    return lo


def zone_touch_windows(
    series: Series, box: Box, *, from_index: int, to_index: int | None = None
) -> tuple[tuple[int, int], ...]:
    """Replay windows: maximal runs of bars whose range intersects the zone box.

    **[OUR CHOICE]** counting rule for the CF-07 zone case.  A zone is a box, not a line, so the
    box itself is the tolerance — there is no P4/P9 band and no ATR re-arm here; price is either
    in the zone or out of it.  Consecutive in-zone bars are **one** touch (the P4 convention),
    and the counter re-arms as soon as a bar trades wholly outside the box.

    ``from_index`` is the bar the zone became usable (the breakout) and is **excluded**: the
    formation bars cannot touch their own zone (the P6 convention).  Each window is an inclusive
    ``(start, end)`` pair, ready to hand to **P20**
    :func:`~tbot.primitives.points_of_most_touch`.
    """
    end = len(series) - 1 if to_index is None else to_index
    top, bottom = float(box.top), float(box.bottom)
    windows: list[tuple[int, int]] = []
    start: int | None = None
    for i in range(from_index + 1, end + 1):
        inside = float(series.low[i]) <= top and float(series.high[i]) >= bottom
        if inside and start is None:
            start = i
        elif not inside and start is not None:
            windows.append((start, i - 1))
            start = None
    if start is not None:
        windows.append((start, end))
    return tuple(windows)


def zone_strength(zone: Zone, config: Config) -> Decimal:
    """Relative zone strength — **[OUR CHOICE]**, no number for it exists anywhere in the corpus.

    SPEC.md §5.5 gives three proportionalities and no scale (S5-R18, S6-R6, S6-R7, S6-R8):
    strength rises with the **consolidation candle count**, with the **timeframe**, and with the
    **size of the move away**.  This renders them as a product of three ratios, each 1.0 at the
    minimum the rules already enforce, so a barely-valid zone scores ~1.0 and a long, high-
    timeframe, far-travelled zone scores well above it::

        bodies    = body_count / min_zone_bodies
        timeframe = (tf.rank + 1) / (Timeframe.H1.rank + 1)
        move      = move_away_atr / sufficient_gap_atr_mult

    It is deliberately **not** written onto the object: SPEC.md §2.4 has no ``strength`` field
    and INTERFACES.md forbids inventing one locally.  Scoring belongs to ``confluence.py``
    (P14) — this is a reporting/ranking aid, not a weight.
    """
    bodies = dec(zone.body_count) / dec(max(1, config.min_zone_bodies))
    tf_ratio = dec(zone.tf.rank + 1) / dec(Timeframe.H1.rank + 1)
    mult = dec(config.sufficient_gap_atr_mult)
    move = zone.move_away_atr / mult if mult > 0 else zone.move_away_atr
    return bodies * tf_ratio * move


def rescue_dead_zones(
    zones: Sequence[Zone], levels: Sequence[Level], config: Config, series: Series
) -> list[Zone]:
    """CF-08 / S7-R4 / S7-C3 rescue clause — re-arm dead zones on an independent level.

    A zone killed by the 50 % rule is re-armed when an independent support/resistance carrying
    ``touch_count <= dead_zone_rescue_max_touches`` (3 — his "2nd–3rd touch of an HTF support is
    a great area") sits **inside the remaining half**: below the frozen midpoint for a demand
    zone, above it for a supply zone.  The trade is then built **on that level, not on the
    zone** — hence only ``Zone.rescued_by_level_id`` is set here; the plan builder reads it.

    "Higher timeframe" is read as *not lower than the zone's own* — **[OUR CHOICE]**: an
    independent level drawn on the same structure timeframe is the ordinary case, and what the
    rule excludes is a level borrowed from a faster chart.  Ties break toward the level with the
    fewest touches, then the nearest to the zone's far edge, then the lowest ``id`` — no
    dependence on the order ``levels`` arrives in.

    Mutates and returns ``zones`` (they are the caller's own freshly built objects).
    """
    if not config.dead_zone_htf_support_rescue or not levels:
        return list(zones)
    limit = config.dead_zone_rescue_max_touches
    for zone in zones:
        if not zone.is_dead or zone.rescued_by_level_id is not None:
            continue
        if zone.side is ZoneSide.DEMAND:
            low, high = zone.box_bottom, zone.midpoint
            far_edge = zone.box_bottom
        else:
            low, high = zone.midpoint, zone.box_top
            far_edge = zone.box_top
        candidates = [
            lvl for lvl in levels
            if lvl.touch_count <= limit
            and lvl.tf.rank >= series.tf.rank
            and low <= lvl.price_at(zone.breakout_index) <= high
        ]
        if not candidates:
            continue
        best = min(
            candidates,
            key=lambda lvl: (lvl.touch_count,
                             abs(lvl.price_at(zone.breakout_index) - far_edge),
                             lvl.id),
        )
        zone.rescued_by_level_id = best.id
        zone.source_ids = _add_ids(zone.source_ids, ("CF-08", "S7-R4", "S7-C3"))
    return list(zones)


def _add_ids(existing: tuple[str, ...], extra: Iterable[str]) -> tuple[str, ...]:
    """Union preserving first-seen order — determinism (INTERFACES.md §9.9: no set ordering)."""
    out = list(existing)
    for item in extra:
        if item not in out:
            out.append(item)
    return tuple(out)


# --------------------------------------------------------------------------- the detector

@dataclass(frozen=True, slots=True)
class _Candidate:
    """One impulse → consolidation → breakout triple, before validation."""

    formation_start: int
    formation_end: int
    breakout_index: int
    side: ZoneSide
    zone_class: ZoneClass
    box: Box
    impulse_index: int
    impulse_move_atr: Decimal


class SupplyDemandZoneDetector:
    """SPEC.md §5.5 supply/demand zone detector (stage 7 of the §3.1 pipeline).

    ``levels`` are the stage-3 output; they are used **only** for the CF-08 rescue clause and may
    be omitted.  The detector never calls another detector (INTERFACES.md §6): ``pipeline.py``
    hands the levels in.
    """

    name: str = "supply_demand_zones"
    stage: int = 7
    source_ids: tuple[str, ...] = (
        "CF-08", "CF-10", "CF-11", "CF-12", "CF-13",
        "S5-R15", "S5-R16", "S5-R17", "S5-R18", "S5-R19", "S5-R28", "S5-R30",
        "S6-R4", "S6-R5", "S6-R9", "S6-R10", "S6-R25", "S6-R48",
        "S7-R4", "S7-R7", "S8-R23",
        "F1",
    )
    produces: tuple[str, ...] = ("zone",)

    __slots__ = ("levels",)

    def __init__(self, levels: Sequence[Level] = ()) -> None:
        self.levels: tuple[Level, ...] = tuple(levels)

    # ---------------------------------------------------------------- public API

    def detect(self, series: Series, config: Config) -> list[Zone]:
        """Every valid zone completed within ``series``, **newest last** by breakout bar."""
        return self.detect_with_rejections(series, config)[0]

    def detect_with_rejections(
        self, series: Series, config: Config
    ) -> tuple[list[Zone], list[ZoneRejection]]:
        """:meth:`detect` plus the rejected candidates, for diagnostics and tests.

        The rejection ``reasons`` are the strings the rejecting primitive produced (P10's
        ``GapMeasure.reasons``, P13's ``ConsolidationCheck.reasons``); only the CF-12 depth-band
        and S5-R17 body-count wordings originate here, because those tests are made in this
        module.
        """
        zones: list[Zone] = []
        rejections: list[ZoneRejection] = []
        if len(series) < 3:
            return zones, rejections

        survivors: list[tuple[_Candidate, P.GapMeasure, Decimal, Decimal]] = []
        for cand in self._candidates(series, config):
            outcome = self._validate(series, config, cand)
            if isinstance(outcome, ZoneRejection):
                rejections.append(outcome)
                _LOG.debug("zone rejected [%d..%d]->%d: %s", cand.formation_start,
                           cand.formation_end, cand.breakout_index, "; ".join(outcome.reasons))
                continue
            survivors.append((cand, *outcome))

        kept, nested_out = self._resolve_nesting(survivors, config)
        rejections.extend(nested_out)

        # INTERFACES.md §6.5: ``symbol:tf:detector:completion_bar``, plus ``:n`` only when one
        # bar really does complete several zones.
        used: dict[int, int] = {}
        for cand, gap, depth_atr, bodies in sorted(
                kept, key=lambda e: (e[0].breakout_index, e[0].formation_start)):
            ordinal = used.get(cand.breakout_index, 0)
            used[cand.breakout_index] = ordinal + 1
            zones.append(self._build(series, config, cand, gap, depth_atr, bodies, ordinal))

        zones.sort(key=lambda z: (z.breakout_index, z.formation_start_index, z.id))
        if self.levels:
            rescue_dead_zones(zones, self.levels, config, series)
        return zones, rejections

    def to_confluence(
        self, objects: Sequence[Zone], config: Config
    ) -> list[P.ConfluenceObject]:
        """P14 adapter — a zone scores at its point-of-most-touch entry price (P20, S5-R23).

        A dead zone that no level rescued contributes nothing: beyond 50 % fill "the setup is
        dead and no re-take is permitted" (CF-08, S5-R28).  The CF-10 continuation bonus is
        ``confluence.py``'s to apply (``zone_continuation_confluence_bonus``); it reads
        ``Zone.zone_class``.
        """
        out: list[P.ConfluenceObject] = []
        for zone in objects:
            if zone.is_dead and zone.rescued_by_level_id is None:
                continue
            price = zone.entry_price_pmt if zone.entry_price_pmt is not None else zone.outer_edge
            out.append(P.ConfluenceObject(
                id=zone.id,
                price=price,
                obj_class="zone",
                tf=zone.tf,
                source_ids=zone.source_ids,
            ))
        return out

    # ---------------------------------------------------------------- candidate generation

    def _candidates(self, series: Series, config: Config) -> list[_Candidate]:
        """Impulse leg (P2) → the consolidation that follows it → the bar that broke out.

        SPEC.md §5.5 steps 1, 2 and 4.  One candidate per impulse leg: the search stops at the
        **first** bar that closes outside the box the consolidation had drawn by then, which is
        what "wait for the breakout" means.
        """
        out: list[_Candidate] = []
        seen: set[tuple[int, int, int]] = set()
        min_bars = max(1, config.consolidation_min_bars)
        for leg in _impulse_legs(series, config):
            found = _find_breakout(series, config, leg.extreme_index + 1, min_bars)
            if found is None:
                continue
            start, end, breakout, direction = found
            key = (start, end, breakout)
            if key in seen:
                continue
            seen.add(key)
            side = ZoneSide.DEMAND if direction is Direction.LONG else ZoneSide.SUPPLY
            zone_class = (ZoneClass.CONTINUATION if direction is leg.direction
                          else ZoneClass.REVERSAL)
            if not _class_enabled(zone_class, config):
                continue
            out.append(_Candidate(
                formation_start=start,
                formation_end=end,
                breakout_index=breakout,
                side=side,
                zone_class=zone_class,
                box=P.zone_box(series, config, start, end),
                impulse_index=leg.trigger_index,
                impulse_move_atr=leg.move_atr,
            ))
        return out

    # ---------------------------------------------------------------- validation

    def _validate(
        self, series: Series, config: Config, cand: _Candidate
    ) -> ZoneRejection | tuple[P.GapMeasure, Decimal, Decimal]:
        reasons: list[str] = []

        cons = P.check_consolidation(series, config, cand.formation_start, cand.formation_end)
        if not cons.horizontal:
            reasons.extend(cons.reasons)

        bodies = count_bodies(series, config, cand.box,
                              cand.formation_start, cand.formation_end)
        if bodies < dec(config.min_zone_bodies):
            reasons.append(f"{bodies} candle bodies < min_zone_bodies {config.min_zone_bodies}")

        direction = Direction.LONG if cand.side is ZoneSide.DEMAND else Direction.SHORT
        gap = P.sufficient_gap(series, config, cand.breakout_index, direction,
                               box=cand.box, tf=series.tf)
        if not gap.valid:
            reasons.extend(gap.reasons)

        atr = P.atr_at(series, config, cand.formation_end)
        depth_atr = cand.box.height / atr if atr > 0 else _ZERO
        if depth_atr < dec(config.min_zone_depth_atr):
            reasons.append(f"depth {float(depth_atr):.2f} ATR < min_zone_depth_atr "
                           f"{config.min_zone_depth_atr}")

        if reasons:
            return ZoneRejection(cand.formation_start, cand.formation_end, cand.breakout_index,
                                 cand.side, cand.zone_class, tuple(reasons))
        return gap, depth_atr, bodies

    # ---------------------------------------------------------------- CF-12 zone within zone

    def _resolve_nesting(
        self,
        survivors: Sequence[tuple[_Candidate, P.GapMeasure, Decimal, Decimal]],
        config: Config,
    ) -> tuple[list[tuple[_Candidate, P.GapMeasure, Decimal, Decimal]], list[ZoneRejection]]:
        """CF-12 / S5-R30 — a zone inside a zone resolves to the **larger** one.

        ``zone_within_zone_policy``:

        * ``"larger_if_within_max_depth"`` (default) — the longer consolidation wins *only if*
          it still passes ``max_zone_depth_atr``; otherwise the inner zone is used, which is how
          CF-12 reconciles S5-R30 ("take the larger") with S8-R23 ("way too wide and not
          concise");
        * ``"always_larger"`` — S5-R30 taken literally: the larger zone wins and keeps its place
          even when it is over-wide.

        "Larger" is more consolidation bars, then the deeper box, then the earlier formation —
        never call order.
        """
        policy = config.zone_within_zone_policy
        max_depth = dec(config.max_zone_depth_atr)
        order = sorted(range(len(survivors)),
                       key=lambda i: (survivors[i][0].formation_start,
                                      survivors[i][0].formation_end))
        dropped: dict[int, tuple[str, ...]] = {}
        bypass: set[int] = set()

        for a_pos, i in enumerate(order):
            for j in order[a_pos + 1:]:
                if i in dropped or j in dropped:
                    continue
                ci, cj = survivors[i][0], survivors[j][0]
                if not _nested(ci, cj):
                    continue
                outer, inner = (i, j) if _is_larger(ci, cj) else (j, i)
                outer_depth = survivors[outer][2]
                if policy == "always_larger":
                    bypass.add(outer)
                    dropped[inner] = ("zone within zone: superseded by the larger consolidation "
                                      "(S5-R30, zone_within_zone_policy='always_larger')",)
                elif outer_depth <= max_depth:
                    dropped[inner] = ("zone within zone: superseded by the larger consolidation "
                                      "(CF-12, S5-R30)",)
                else:
                    dropped[outer] = (f"depth {float(outer_depth):.2f} ATR > max_zone_depth_atr "
                                      f"{config.max_zone_depth_atr}",)

        kept: list[tuple[_Candidate, P.GapMeasure, Decimal, Decimal]] = []
        rejections: list[ZoneRejection] = []
        for i, entry in enumerate(survivors):
            cand, _gap, depth_atr, _bodies = entry
            if i in dropped:
                reasons = dropped[i]
            elif depth_atr > max_depth and i not in bypass:
                reasons = (f"depth {float(depth_atr):.2f} ATR > max_zone_depth_atr "
                           f"{config.max_zone_depth_atr}",)
            else:
                kept.append(entry)
                continue
            rejections.append(ZoneRejection(cand.formation_start, cand.formation_end,
                                            cand.breakout_index, cand.side, cand.zone_class,
                                            reasons))
            _LOG.debug("zone rejected [%d..%d]->%d: %s", cand.formation_start,
                       cand.formation_end, cand.breakout_index, "; ".join(reasons))
        return kept, rejections

    # ---------------------------------------------------------------- object construction

    def _build(
        self,
        series: Series,
        config: Config,
        cand: _Candidate,
        gap: P.GapMeasure,
        depth_atr: Decimal,
        bodies: Decimal,
        ordinal: int,
    ) -> Zone:
        box = cand.box
        last = len(series) - 1
        died = death_index(series, config, box, cand.side, from_index=cand.breakout_index)
        alive_to = died if died is not None else last

        # CF-07/S5-R28 replay: touches only count while the zone is alive.
        windows = zone_touch_windows(series, box, from_index=cand.breakout_index,
                                     to_index=alive_to)

        fill_box = self._fill_box(series, config, cand, windows)
        fill = P.measure_fill(series, config, fill_box, cand.side,
                              from_index=cand.breakout_index)

        pmt = P.points_of_most_touch(
            series, config, box, cand.side,
            windows=((cand.formation_start, cand.formation_end), *windows),
            at_index=alive_to,
        )

        band = wick_band(series, config, box, cand.side,
                         cand.formation_start, cand.formation_end)

        ids = ["CF-13", "S5-R17", "CF-11", "S5-R16", "CF-12"]
        if band is not None:
            ids.append("F1")
        if cand.zone_class is ZoneClass.CONTINUATION:
            ids.extend(["CF-10", "S5-R15",
                        "S6-R5" if cand.side is ZoneSide.DEMAND else "S6-R4"])
        else:
            ids.extend(["CF-10", "S6-A26"])
        if fill.is_dead:
            ids.extend(["CF-08", "S5-R28", "S6-R10"])
        elif windows:
            ids.extend(["CF-07", "S5-R28", "S6-R25"])

        return Zone(
            id=object_id(series, self.name, cand.breakout_index, ordinal),
            symbol=series.symbol,
            tf=series.tf,
            side=cand.side,
            zone_class=cand.zone_class,
            box_top=box.top,
            box_bottom=box.bottom,
            midpoint=P.midpoint_of(box),      # frozen at creation, never re-measured (CF-08)
            body_count=int(bodies),
            formation_start_index=cand.formation_start,
            formation_end_index=cand.formation_end,
            breakout_index=cand.breakout_index,
            move_away_pct=gap.gap_pct,
            move_away_atr=gap.gap_atr,
            depth_atr=depth_atr,
            fill_pct=fill.fill_pct,
            is_dead=fill.is_dead,
            touch_count=len(windows),
            entry_price_pmt=pmt.price,
            source_ids=tuple(ids),
            # F1: the body core stays in ``box_top``/``box_bottom`` and keeps pricing the
            # entries; the band is carried alongside it and only the stop reads it.
            wick_band_top=None if band is None else band[0],
            wick_band_bottom=None if band is None else band[1],
        )

    def _fill_box(
        self,
        series: Series,
        config: Config,
        cand: _Candidate,
        windows: Sequence[tuple[int, int]],
    ) -> Box:
        """The box the 50 % rule is measured against, per ``zone_fill_reference`` (CF-08).

        ``"as_originally_drawn"`` (default, S5-A11) — the formation box, frozen.
        ``"remeasured_after_each_touch"`` — **[OUR CHOICE]** rendering of the sweep alternative:
        the P5 box is re-drawn over the formation window **extended through the latest touch**,
        so a deep retest widens the reference and the zone survives longer.  ``Zone.midpoint``
        stays the frozen creation value either way (INTERFACES.md §9.2).
        """
        if config.zone_fill_reference == "as_originally_drawn" or not windows:
            return cand.box
        return P.zone_box(series, config, cand.formation_start, windows[-1][1])


# --------------------------------------------------------------------------- module helpers

def _impulse_legs(series: Series, config: Config) -> list[P.DirectionalChange]:
    """P2 events collapsed to one leg per impulse.

    :func:`~tbot.primitives.find_directional_changes` fires on **every** bar from which a
    qualifying move exists, so one impulse produces a run of consecutive same-direction events.
    The run collapses to its **earliest** trigger, whose extreme is the end of the leg as it was
    seen from before the move — later triggers look forward past the impulse and drag the
    extreme into the consolidation that follows it.  **[OUR CHOICE]**, and the reason the
    consolidation window starts where it does.
    """
    legs: list[P.DirectionalChange] = []
    last_trigger: int | None = None
    last_direction: Direction | None = None
    for change in P.find_directional_changes(series, config):
        if (last_trigger is not None and change.direction is last_direction
                and change.trigger_index == last_trigger + 1):
            last_trigger = change.trigger_index
            continue
        legs.append(change)
        last_trigger, last_direction = change.trigger_index, change.direction
    return legs


def _find_breakout(
    series: Series, config: Config, after: int, min_bars: int
) -> tuple[int, int, int, Direction] | None:
    """Grow the consolidation past ``after`` until a bar **closes** outside its P5 box.

    For every candidate end bar the window start is the earliest bar at or after ``after`` that
    makes the window **horizontal** (P13), then trimmed by :func:`_trim_leading` so the leading
    tail of the impulse is not mistaken for consolidation.  The first bar whose close sits
    beyond the box built on the window so far is the breakout — SPEC.md §5.5 step 4, "wait for
    the breakout".

    Returns ``(formation_start, formation_end, breakout_index, direction)``.  The window is the
    longest one that still starts inside the consolidation — "longer consolidation = stronger
    zone" (S5-R18, S5-R30) — after :func:`_trim_leading` has removed the tail of the impulse.
    """
    n = len(series)
    first = max(0, after)
    for end in range(first + min_bars - 1, n - 1):
        start = _trim_leading(series, config, first, end, min_bars)
        if not P.check_consolidation(series, config, start, end).horizontal:
            continue
        box = P.zone_box(series, config, start, end)
        close = float(series.close[end + 1])
        if close > float(box.top):
            return start, end, end + 1, Direction.LONG
        if close < float(box.bottom):
            return start, end, end + 1, Direction.SHORT
    return None


def _trim_leading(series: Series, config: Config, start: int, end: int, min_bars: int) -> int:
    """Drop the leading bars that still belong to the impulse, not to the consolidation.

    A bar is part of the consolidation once its **body** sits wholly inside the P5 box drawn on
    the bars that follow it; the last leg of an impulse pokes out of that box by definition.
    **[OUR CHOICE]** — it is the S5-R17 "full candle body must be within the zone" test applied
    to the window's own front edge, and it is what makes the consolidation start where he draws
    it rather than one or two impulse bars early.
    """
    while end - start + 1 > min_bars:
        inner = P.zone_box(series, config, start + 1, end)
        body_high = dec(series.body_high[start])
        body_low = dec(series.body_low[start])
        if inner.bottom <= body_low and body_high <= inner.top:
            break
        start += 1
    return start


def _class_enabled(zone_class: ZoneClass, config: Config) -> bool:
    """CF-10 ``zone_direction_mode`` — ``both`` (default), ``continuation_only``, ``reversal_only``."""
    mode = config.zone_direction_mode
    if mode == "continuation_only":
        return zone_class is ZoneClass.CONTINUATION
    if mode == "reversal_only":
        return zone_class is ZoneClass.REVERSAL
    return True


def _nested(a: _Candidate, b: _Candidate) -> bool:
    """True when one candidate's box and formation window sit inside the other's."""
    if a.side is not b.side:
        return False
    windows_overlap = (a.formation_start <= b.formation_end
                       and b.formation_start <= a.formation_end)
    if not windows_overlap:
        return False
    a_in_b = b.box.bottom <= a.box.bottom and a.box.top <= b.box.top
    b_in_a = a.box.bottom <= b.box.bottom and b.box.top <= a.box.top
    return a_in_b or b_in_a


def _is_larger(a: _Candidate, b: _Candidate) -> bool:
    """S5-R30 "larger" = longer consolidation, then deeper box, then earlier formation."""
    a_bars = a.formation_end - a.formation_start + 1
    b_bars = b.formation_end - b.formation_start + 1
    if a_bars != b_bars:
        return a_bars > b_bars
    if a.box.height != b.box.height:
        return a.box.height > b.box.height
    return a.formation_start <= b.formation_start
