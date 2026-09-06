"""tbot.detectors.orderblocks — SPEC.md §5.6 order blocks.

An order block is **exactly one candle** — asked and answered directly, "never two" (S6-R3,
``ob_max_candles = 1``):

* **bullish** OB — the last **red** candle before a directional change **up** (S6-R2);
* **bearish** OB — the last **green** candle before a directional change **down** (S6-R1).

S7's "a bearish order block is the last red candle" uses the identical phrase he uses for the
bullish one, which makes it internally impossible; CF-09 discards it (S7-C4).  A doji is treated
as red by **P2**, i.e. as a bullish-OB candidate — that is the primitive's **[OUR CHOICE]**, not
a rule of his.

Everything is a primitive:

* the directional change is **P2** :func:`~tbot.primitives.find_directional_changes`;
* the box is **P5** :func:`~tbot.primitives.order_block_box` — the candle's *body* under the same
  small-wick test as a zone (``ob_box_source = "body_with_small_wick"``, CF-13, S6-R9, S7-R7);
* invalidation is the **same 50 % fill rule as a zone** (**P6**, CF-08, S8-R21 "completely
  filled ⇒ dead"), with **P15** :func:`~tbot.primitives.ob_liquidity_taken_pct` governing the
  block's own life: **Q1** gives the order block its own threshold, ``ob_fill_invalidation_pct``
  (75 %, his stated 70–80 band, S7-R3), so P15 is always the measure that decides. ``fill_pct``
  is still reported for comparison, but it no longer decides.

**Minimum size.**  His figures are raw dollars — "$100 is way too tiny", a $0.30 ENS block called
weak, "smaller than a pinky nail" (S6-R48, S7-R6, S7-A5).  SPEC.md §5.6 replaces them with the
normalised measure ``size_atr >= min_zone_depth_atr`` (CF-12); **the ATR normalisation is OURS**,
his dollars are not transferable between instruments.  The threshold lives in
``detectors/zones.py`` (which owns the key), and arrives here through
:func:`tbot.detectors.zones.min_size_atr` — this module reads no key it does not own
(INTERFACES.md §7).

**Nesting.**  An order block is usually found *inside* a demand zone (S5 ``[00:33:12]``,
S5-A14).  Where it is, ``ob_inside_zone_precedence = "zone_wins"``: the **zone's** boundaries and
fill rule govern, because he prefers "more consolidation demand zone over the order block"
(CF-09, S6-R31).  See :func:`link_to_zones`.

An order block is **never** a standalone signal (S6-R29) — that gate is
``single_class_trade_forbidden`` in ``confluence.py``; detectors do not gate (INTERFACES.md §6.6).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from ..config import Config
from ..models import (
    Box,
    Direction,
    OBSide,
    OrderBlock,
    Series,
    Zone,
    ZoneSide,
    dec,
)
from .. import primitives as P
from .base import object_id
from .zones import fill_invalidation_pct, min_size_atr

__all__ = [
    "OrderBlockDetector",
    "OrderBlockRejection",
    "S7_LIQUIDITY_THRESHOLD_PCT",
    "dir_change_gap_reason",
    "ob_invalidation_pct",
    "link_to_zones",
    "ob_zone_side",
]

_LOG = logging.getLogger(__name__)

_ZERO = Decimal(0)

#: Legacy switch: the ``zone_fill_invalidation_pct`` value at or above which the *zone* key was
#: read as "set to the S7 order-block values (70/80)".  **Q1 retired this coupling** — the order
#: block now has its own ``ob_fill_invalidation_pct`` and P15 is live at every zone setting.  The
#: constant is kept only so a caller that pinned the old behaviour still resolves.
S7_LIQUIDITY_THRESHOLD_PCT: Decimal = Decimal(70)


def ob_invalidation_pct(config: Config) -> Decimal:
    """**Q1** — the order-block death threshold, ``ob_fill_invalidation_pct`` (75 %, band 70–80).

    ``stated``, S7 ``[00:08:54]``: *"so my rule for order blocks are like around 70 80%"*, said in
    the same breath as an explicit denial that the zone rule applies — S7 ``[00:07:14]``: *"so this
    one doesn't have a rule where you know 50% has to be taken."*  A 50 %-filled order block is one
    he still takes (S7 ``[00:37:57]``), which is what makes a single 50 % threshold untenable.

    Before Q1 this read ``zone_fill_invalidation_pct`` and P15 was dead code, because P15 only ran
    when the *zone* key was raised to 70/80 — a setting nothing shipped.
    """
    return dec(config.ob_fill_invalidation_pct)


def dir_change_gap_reason(
    series: Series, config: Config, change: P.DirectionalChange
) -> str | None:
    """**Q6 [INFERRED]** — reject a directional change whose impulse leg is too small *in percent*.

    ``dir_change_uses_sufficient_gap_table`` (default true).  He never attaches a size to
    "directional change" in the order-block definition, but the only quantified move-size test he
    owns is the sufficient-gap-by-timeframe table, and in every worked example the order block and
    the supply/demand zone are marked off the **same** impulse leg whose gap he has just checked
    out loud:

        *"Price goes up, consolidates, breakout, sufficient gap 30 minutes 4%. That's sufficient
        enough. … Here is another example of a demand zone with a two candle. This is also an
        order block."* — S5 ``[00:54:07]``

        *"Now a four or 3% move on the daily is not a strong move from this breakout point.
        Higher time frames need to have a higher move away from that zone."* — S5 ``[00:36:05]``

    The structural point matters more than the rows: **his threshold is a percentage that scales
    with timeframe, not an ATR multiple**, which ``dir_change_atr`` alone cannot express.  On the
    timeframes that can be checked by hand 2.0 ATR is materially *looser* than his percentage
    floors, i.e. the detector was calling directional changes he would not.  ``dir_change_atr``
    is retained as a secondary floor inside P2 and both must pass.

    Supply/demand zones already apply the same table one stage later as **P10**
    (``sufficient_gap``); this is the order-block half, which had no percentage test at all.
    Returns the rejection wording, or ``None`` when the leg is big enough.
    """
    if not config.dir_change_uses_sufficient_gap_table:
        return None
    required = float(config.sufficient_gap_pct_by_tf.get(series.tf.value, 0.0))
    if required <= 0.0:
        return None
    anchor = abs(float(series.close[change.trigger_index]))
    if anchor <= 0.0:
        return None
    pct = float(change.move) / anchor * 100.0
    if pct >= required:
        return None
    return (
        f"impulse leg {pct:.2f}% < sufficient_gap_pct_by_tf[{series.tf.value}] {required:.2f}% "
        f"(Q6, dir_change_uses_sufficient_gap_table)"
    )


def ob_zone_side(side: OBSide) -> ZoneSide:
    """P6/P15 speak in zone terms: a **bullish** OB is demand, a **bearish** OB is supply."""
    return ZoneSide.DEMAND if side is OBSide.BULLISH else ZoneSide.SUPPLY


@dataclass(frozen=True, slots=True)
class OrderBlockRejection:
    """An order-block candidate that did not survive (INTERFACES.md §6.4)."""

    bar_index: int
    dir_change_index: int
    side: OBSide
    reasons: tuple[str, ...]


# --------------------------------------------------------------------------- CF-09 nesting

def link_to_zones(
    order_blocks: Sequence[OrderBlock], zones: Sequence[Zone], config: Config
) -> list[OrderBlock]:
    """CF-09 / S6-R31 — attach each order block to the zone that contains it.

    Containment is pure geometry: the OB box sits wholly inside the zone box.  When several
    zones qualify the one with the **most consolidation** wins (S5-R18, S5-R30), then the
    earliest breakout, then the lowest ``id`` — never call order.

    ``ob_inside_zone_precedence``:

    * ``"zone_wins"`` (default) — the zone's boundaries and fill rule govern, so the contained
      block inherits the zone's ``fill_pct`` / ``is_dead``;
    * ``"ob_wins"`` — the link is recorded for reporting but the block keeps its own P6/P15 fill.

    Both directions of the link are written: ``OrderBlock.parent_zone_id`` and
    ``Zone.contained_ob_ids`` (SPEC.md §2.4, §2.5).  Mutates and returns ``order_blocks``.
    """
    if not zones:
        return list(order_blocks)
    zone_wins = config.ob_inside_zone_precedence == "zone_wins"
    for block in order_blocks:
        holders = [z for z in zones
                   if z.box_bottom <= block.box_bottom and block.box_top <= z.box_top]
        if not holders:
            continue
        parent = min(holders, key=lambda z: (-z.body_count, z.breakout_index, z.id))
        block.parent_zone_id = parent.id
        if block.id not in parent.contained_ob_ids:
            parent.contained_ob_ids.append(block.id)
        block.source_ids = _add_ids(block.source_ids, ("CF-09", "S6-R31", "S5-A14"))
        if zone_wins:
            block.fill_pct = parent.fill_pct
            block.is_dead = parent.is_dead
    return list(order_blocks)


def _add_ids(existing: tuple[str, ...], extra: Sequence[str]) -> tuple[str, ...]:
    out = list(existing)
    for item in extra:
        if item not in out:
            out.append(item)
    return tuple(out)


# --------------------------------------------------------------------------- the detector

@dataclass(frozen=True, slots=True)
class _Candidate:
    bar_index: int
    side: OBSide
    change: P.DirectionalChange


class OrderBlockDetector:
    """SPEC.md §5.6 order-block detector (stage 8 of the §3.1 pipeline).

    ``zones`` are the stage-7 output.  They are optional and are used only for the CF-09 nesting
    rule; a detector never calls another detector (INTERFACES.md §6), so ``pipeline.py`` hands
    them in.  ``min_size_atr`` overrides the CF-12 minimum for a caller that has already derived
    it; when omitted it is read through :func:`tbot.detectors.zones.min_size_atr`, the owner of
    the key.
    """

    name: str = "order_blocks"
    stage: int = 8
    source_ids: tuple[str, ...] = (
        "CF-09", "CF-12", "CF-13", "CF-08",
        "S6-R1", "S6-R2", "S6-R3", "S6-R9", "S6-R31", "S6-R48",
        "S5-A14", "S7-R3", "S7-R6", "S8-R21",
    )
    produces: tuple[str, ...] = ("order_block",)

    __slots__ = ("zones", "_min_size_atr")

    def __init__(
        self,
        zones: Sequence[Zone] = (),
        *,
        min_size_atr: Decimal | float | None = None,
    ) -> None:
        self.zones: tuple[Zone, ...] = tuple(zones)
        self._min_size_atr: Decimal | None = None if min_size_atr is None else dec(min_size_atr)

    # ---------------------------------------------------------------- public API

    def detect(self, series: Series, config: Config) -> list[OrderBlock]:
        """Every valid order block completed within ``series``, **newest last**."""
        return self.detect_with_rejections(series, config)[0]

    def detect_with_rejections(
        self, series: Series, config: Config
    ) -> tuple[list[OrderBlock], list[OrderBlockRejection]]:
        """:meth:`detect` plus the rejected candidates and why (INTERFACES.md §6.4)."""
        blocks: list[OrderBlock] = []
        rejections: list[OrderBlockRejection] = []
        floor = self._min_size_atr if self._min_size_atr is not None else min_size_atr(config)

        # INTERFACES.md §6.5: ``:n`` is appended only when one completion bar really does carry
        # several blocks, so a rejected candidate never shifts a surviving block's id.
        used: dict[int, int] = {}
        for cand in self._candidates(series, config):
            gap_reason = dir_change_gap_reason(series, config, cand.change)
            if gap_reason is not None:
                rejections.append(OrderBlockRejection(cand.bar_index, cand.change.trigger_index,
                                                      cand.side, (gap_reason,)))
                _LOG.debug("order block rejected at %d: %s", cand.bar_index, gap_reason)
                continue
            box = self._box(series, config, cand)
            atr = P.atr_at(series, config, cand.bar_index)
            size_atr = box.height / atr if atr > 0 else _ZERO
            if size_atr < floor:
                reason = (f"order block size {float(size_atr):.2f} ATR < min_zone_depth_atr "
                          f"{float(floor)}")
                rejections.append(OrderBlockRejection(cand.bar_index, cand.change.trigger_index,
                                                      cand.side, (reason,)))
                _LOG.debug("order block rejected at %d: %s", cand.bar_index, reason)
                continue
            completion = cand.change.extreme_index
            ordinal = used.get(completion, 0)
            used[completion] = ordinal + 1
            blocks.append(self._build(series, config, cand, box, size_atr, ordinal))

        if self.zones:
            link_to_zones(blocks, self.zones, config)
        return blocks, rejections

    def to_confluence(
        self, objects: Sequence[OrderBlock], config: Config
    ) -> list[P.ConfluenceObject]:
        """P14 adapter — an order block scores at its box midpoint (INTERFACES.md §6.7).

        A dead block contributes nothing (CF-08, S8-R21); under ``"zone_wins"`` "dead" is the
        parent zone's verdict, which is the whole point of S6-R31.
        """
        out: list[P.ConfluenceObject] = []
        for block in objects:
            if block.is_dead:
                continue
            out.append(P.ConfluenceObject(
                id=block.id,
                price=block.midpoint,
                obj_class="order_block",
                tf=block.tf,
                source_ids=block.source_ids,
            ))
        return out

    # ---------------------------------------------------------------- candidate generation

    def _candidates(self, series: Series, config: Config) -> list[_Candidate]:
        """One candidate per opposing candle that is genuinely the **last** one before the move.

        :func:`~tbot.primitives.find_directional_changes` fires from every bar a qualifying move
        can be measured from, and several of those events point at the same
        ``order_block_index``.  Two filters resolve it, both straight from S6-R1/S6-R2:

        * the candle after the block must already be the **move's** colour — otherwise the block
          is not the *last* opposing candle before the change, merely an early one in a run
          (**[OUR CHOICE]** machine form of "the last red candle before a directional change");
        * each block bar is emitted once, carrying the **earliest** directional change it
          precedes (tie: the larger move) — deterministic, never call-order dependent.
        """
        green = series.is_green
        n = len(series)
        best: dict[int, P.DirectionalChange] = {}
        for change in P.find_directional_changes(series, config):
            ob_index = change.order_block_index
            if ob_index is None or ob_index + 1 >= n:
                continue
            move_is_green = change.direction is Direction.LONG
            if bool(green[ob_index + 1]) is not move_is_green:
                continue
            current = best.get(ob_index)
            if current is None or (change.trigger_index, -change.move) < (
                    current.trigger_index, -current.move):
                best[ob_index] = change

        out = [
            _Candidate(
                bar_index=ob_index,
                side=(OBSide.BULLISH if change.direction is Direction.LONG else OBSide.BEARISH),
                change=change,
            )
            for ob_index, change in best.items()
        ]
        # Newest last, ordered by the bar that completed them: the move-away extreme is the
        # first bar at which the directional change — and therefore the block — is knowable.
        out.sort(key=lambda c: (c.change.extreme_index, c.bar_index))
        return out

    def _box(self, series: Series, config: Config, cand: _Candidate) -> Box:
        """**P5** box.  ``ob_max_candles`` is 1 (S6-R3): exactly one candle, never two.

        The documented alternative (3, "treat as a mini-zone") widens the box back over the
        consecutive same-colour run that ends at the block candle, capped at the key's value,
        through the same P5 constructor.  ``OrderBlock.bar_index`` always names the block candle
        itself.
        """
        if config.ob_max_candles <= 1:
            return P.order_block_box(series, config, cand.bar_index)
        colour = bool(series.is_green[cand.bar_index])
        start = cand.bar_index
        while (start > 0 and cand.bar_index - start + 1 < config.ob_max_candles
               and bool(series.is_green[start - 1]) is colour):
            start -= 1
        return P.zone_box(series, config, start, cand.bar_index, source=config.ob_box_source)

    # ---------------------------------------------------------------- object construction

    def _build(
        self,
        series: Series,
        config: Config,
        cand: _Candidate,
        box: Box,
        size_atr: Decimal,
        ordinal: int,
    ) -> OrderBlock:
        side = cand.side
        zone_side = ob_zone_side(side)
        # The block cannot be filled by its own move away: **P2** guarantees price travelled
        # >= dir_change_atr with no retrace past 33 % before the extreme, so the extreme is the
        # first bar from which a genuine return can be measured.  It is the order-block analogue
        # of a zone's breakout bar, and like it, it is excluded.  **[OUR CHOICE]**
        from_index = cand.change.extreme_index
        fill = P.measure_fill(series, config, box, zone_side, from_index=from_index)
        liquidity = P.ob_liquidity_taken_pct(series, config, box, zone_side,
                                             from_index=from_index)

        ids = ["CF-09", "CF-13", "S6-R3", "S6-R9",
               "S6-R2" if side is OBSide.BULLISH else "S6-R1",
               "CF-12", "S6-R48", "S7-R6"]
        # Q1 (stated, S7 `[00:07:14]`-`[00:08:54]`): a single-candle order block dies when ~75 %
        # of its liquidity has been taken, NOT at the zone's 50 % fill line.  The measure is P15
        # — the deepest **wick** through the body range — whatever ``zone_fill_measure`` says
        # about zones.  This is the code path that used to be unreachable.
        threshold = ob_invalidation_pct(config)
        is_dead = liquidity >= threshold
        ids.extend(["S7-R3", "P15"])
        if is_dead:
            ids.extend(["CF-08", "S8-R21"])

        return OrderBlock(
            id=object_id(series, self.name, cand.change.extreme_index, ordinal),
            symbol=series.symbol,
            tf=series.tf,
            side=side,
            bar_index=cand.bar_index,
            box_top=box.top,
            box_bottom=box.bottom,
            dir_change_index=cand.change.trigger_index,
            dir_change_atr_move=cand.change.move_atr,
            liquidity_taken_pct=liquidity,
            fill_pct=fill.fill_pct,
            is_dead=is_dead,
            size_atr=size_atr,
            source_ids=tuple(ids),
        )
