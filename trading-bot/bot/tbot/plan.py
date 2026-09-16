"""tbot.plan — SPEC.md §8, trade-plan construction.

Takes a qualified :class:`~tbot.models.Setup` plus the structural objects that justified it and
returns a complete :class:`~tbot.models.TradePlan`.  The order of construction is **fixed** and
is an INTERFACES.md §9 invariant: **entry ladder -> stop -> take-profits**, then size, then
vehicle.  Nothing is sized before the stop exists.

The pieces, in the order :func:`build_plan` runs them:

1. **Entry family** (CF-16) — retest / flip-pending / trigger, with market orders permitted only
   for the trigger family (``allow_market_orders = "trigger_family_only"``).
2. **Entry ladder** (CF-17, CF-18) — 1-3 rungs.  The first fill is the **lightest**, at the near
   level; the heaviest sits at the far end of the ladder (bottom for longs, top for shorts).
   DCA prices attach to the *next structural level*, never to fixed increments (S2-R10).
3. **Stop** (CF-14) — wick anchor at the far edge, falling back to the candle **body** when the
   wick is a P12 capitulation wick or exceeds ``stop_wick_max_pct``; never straddling an
   independent opposing level; then the ``stop_buffer_atr`` buffer (P19).
4. **Wide-stop escalation** (CF-06) — LTF tighten, then downgrade the vehicle, then skip. Size is
   *always* solved from the risk budget regardless of which branch fires.
5. **Take-profits** (CF-27, CF-28) — structural levels in the trade direction, never fixed R
   multiples, with the front-loaded split applied to the number of TPs actually placed.
6. **Size** (CF-01, CF-02) — solved **backwards** from the risk budget so a full stop-out loses
   exactly the capped percentage; notional is derived and then clamped.
7. **Consistency** — :func:`check_plan_consistency` re-derives the loss from the blended entry,
   the stop and the quantity and refuses to emit a plan that does not add up.

Config keys read here are exactly the ``planner.py`` block of INTERFACES.md §7.  The risk ladder
(CF-01), the notional ceilings (CF-02) and the CF-07 touch decay belong to :mod:`tbot.risk` and
arrive as a :class:`~tbot.risk.SizingBudget`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Sequence

import tbot.primitives as P
from tbot.config import Config
from tbot.models import (
    Conviction,
    Direction,
    EntryFamily,
    EntryRung,
    Level,
    OrderType,
    Series,
    Setup,
    TakeProfit,
    TradeClass,
    TradePlan,
    Vehicle,
    Zone,
    dec,
)
from tbot.risk import (
    HUNDRED,
    MONEY_ABS_TOL,
    MONEY_REL_TOL,
    ONE,
    ZERO,
    SizingBudget,
    money_close,
    money_ge,
    money_le,
)

__all__ = [
    "PlanError",
    "PlanInconsistent",
    "PlanInputs",
    "StopAnchor",
    "StopDecision",
    "stop_distance_pct",
    "VehicleDecision",
    "SizeSolution",
    "ConsistencyReport",
    "PlanBuild",
    "money_close",
    "money_ge",
    "money_le",
    "entry_family_enabled",
    "order_type_for_family",
    "dca_leg_count",
    "entry_split",
    "build_entry_ladder",
    "blended_entry",
    "sizing_reference",
    "stop_anchor",
    "place_stop",
    "escalate_wide_stop",
    "tp_count_for",
    "tp_split",
    "select_take_profits",
    "rr_ratio",
    "rr_for_gate",
    "solve_size",
    "derive_leverage",
    "plan_loss_at_stop",
    "check_plan_consistency",
    "assert_plan_consistent",
    "build_plan",
]


class PlanError(ValueError):
    """The caller wired :func:`build_plan` up wrong (bad direction, empty series, no levels)."""


class PlanInconsistent(AssertionError):
    """A built plan failed :func:`assert_plan_consistent` — a bug, never a market condition."""


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True, slots=True)
class PlanInputs:
    """Everything §8 needs that is not in the :class:`~tbot.models.Setup` itself.

    The plan builder never runs a detector and never scores anything (INTERFACES.md §6 rule 6):
    the objects below are handed in by the pipeline.  All ``*_levels`` are
    :class:`~tbot.models.Level` objects; their prices are read through ``Level.price_at`` so a
    sloped trend line resolves correctly at ``at_index``.
    """

    setup: Setup
    series: Series
    budget: SizingBudget
    #: The near level the first, lightest rung rests on (the SR point — S3-R13, S5-R20, S7-R18).
    entry_level: Level
    #: Bar whose wick anchors the stop: the far-edge extreme of the zone/level (CF-14 step 1).
    stop_anchor_index: int
    #: Structural levels further out along the ladder, **nearest first** (S2-R10, S5-C5).
    dca_levels: Sequence[Level] = ()
    #: Structural levels in the trade direction for the TP ladder, nearest first (S6-R20).
    tp_levels: Sequence[Level] = ()
    #: Independent opposing S/R the stop must not straddle (CF-14 step 3, S5-R25, S6-R19).
    opposing_levels: Sequence[Level] = ()
    #: The zone the setup hangs off, when there is one — drives the CF-17 second DCA.
    zone: Zone | None = None
    #: Bar to evaluate at.  ``None`` = the last bar of ``series`` (a backtest must pass it).
    at_index: int | None = None
    #: Lower-timeframe series for the CF-06 step-1 tightening, already stepped down
    #: ``stop_tighten_tf_steps`` rungs, plus the bar in it to re-anchor on.
    ltf_series: Series | None = None
    ltf_stop_anchor_index: int | None = None
    #: P18 ``wick_heavy`` — switches the CF-18 split to the 20/80 variant (S6-R27).
    wick_heavy: bool = False
    #: Vehicle constraints from the CF-40 universe filter and the CF-39 calendar.
    spot_allowed: bool = True
    leverage_allowed: bool = True
    #: Theoretical measured-move target; real TPs go at intervening levels (S4 ``[00:53:25]``).
    measured_move_target: Decimal | None = None
    #: Level whose loss kills the trade (CF-30).  Defaults to ``entry_level.id``.
    invalidation_level_id: str | None = None
    bias_invalidation_price: Decimal | None = None
    expires_at_index: int | None = None
    #: ``0`` DCA legs regardless of zone depth: breakdown / trend-line / pattern breakout
    #: (S8-R11) and SFP (CF-20) are single-entry plays.
    single_entry_play: bool = False

    def resolved_index(self) -> int:
        return len(self.series) - 1 if self.at_index is None else self.at_index


# --------------------------------------------------------------------------- CF-16 family


def entry_family_enabled(config: Config, family: EntryFamily) -> bool:
    """**CF-16** — is this entry family switched on?"""
    return {
        EntryFamily.RETEST: bool(config.entry_family_retest_enabled),
        EntryFamily.FLIP_PENDING: bool(config.entry_family_flip_pending_enabled),
        EntryFamily.TRIGGER: bool(config.entry_family_trigger_enabled),
    }[family]


def order_type_for_family(config: Config, family: EntryFamily) -> OrderType:
    """**CF-16 / S4-R32 / TBOT1-R25** — never market into anything except a trigger entry.

    ``allow_market_orders``: ``"trigger_family_only"`` (default), ``"never"`` (S4-R32 literal),
    ``"always"``.  The trigger family is SFP and MSB-retest, where the signal is defined on a
    close and the fill is at the next open.
    """
    mode = config.allow_market_orders
    if mode == "always":
        return OrderType.MARKET
    if mode == "trigger_family_only" and family is EntryFamily.TRIGGER:
        return OrderType.MARKET
    return OrderType.LIMIT


# --------------------------------------------------------------------------- CF-17/18 ladder


def dca_leg_count(
    config: Config,
    *,
    trade_class: TradeClass,
    entry_family: EntryFamily,
    zone_depth_atr: Decimal | float | None = None,
    single_entry_play: bool = False,
) -> int:
    """**CF-17** — how many DCA legs (SPEC.md §8.2).  Returns the DCA count, not the rung count.

    * breakdown / trend-line / pattern breakout and SFP: ``dca_count_breakdown`` = 0, single
      entry (S8-R11, CF-20).  The flip-pending family is exactly the breakout case — unless
      ``presr_light_limit_enabled`` (**Q10**, default off), which restores the light-limit-then-
      DCA-at-the-flip ladder he demonstrates in S2 ``[00:27:08]`` and then disowns.
    * scalp: ``dca_count_scalp_max`` = 1, and 0 when the zone is tight (S8-R17).
    * zone / SR swing entry: ``dca_count_default`` = 1, rising to 2 when
      ``zone_depth_atr >= dca2_min_zone_depth_atr`` (1.5) (S5-R22, S6-R16).
    * global maximum ``dca_count_max`` = 2. Six-leg and SMC-style 5-6 order ladders are
      hard-forbidden (S2-R9, S6 ``[01:01:51]``).
    """
    if single_entry_play:
        return int(config.dca_count_breakdown)
    if entry_family is EntryFamily.FLIP_PENDING:
        if config.presr_light_limit_enabled:
            # **Q10** — ``presr_light_limit_enabled`` (default **off**).  The one entry he
            # demonstrates that neither CF-16 family covers: a *light* limit already resting at a
            # level that has been broken but not yet retested, with the heavier leg at the
            # confirmed flip.  S2 ``[00:27:08]``: *"We broke above resistance. This became an SR,
            # right? We came and bounced briefly from it. My entry was light there. My DCA came
            # around 57360."*  He then calls it his own impatience — *"if I was a little more
            # patient and awake, then yes, I would have waited for the flip to happen"* (S2
            # ``[00:27:41]``) — which is why it is permitted-but-inferior and ships off.
            return min(int(config.dca_count_default), int(config.dca_count_max))
        return int(config.dca_count_breakdown)

    n = int(config.dca_count_default)
    depth = None if zone_depth_atr is None else dec(zone_depth_atr)
    if depth is not None and money_ge(depth, dec(config.dca2_min_zone_depth_atr)):
        n = max(n, 2)
    if trade_class in (TradeClass.SCALP, TradeClass.COUNTER_TREND):
        # A "tight" zone is one that does not clear the second-DCA depth threshold; the scalp
        # ladder then collapses to a single entry (S8-R17).  **[OUR CHOICE]** reading of "tight".
        n = min(n, int(config.dca_count_scalp_max))
        if depth is not None and not money_ge(depth, dec(config.dca2_min_zone_depth_atr)):
            n = min(n, int(config.dca_count_scalp_max))
    return max(0, min(n, int(config.dca_count_max)))


def entry_split(config: Config, legs: int, *, wick_heavy: bool = False) -> tuple[Decimal, ...]:
    """**CF-18** — the per-rung size split (SPEC.md §8.3).  **The ratios are OURS.**

    ``legs`` counts rungs, not DCAs: 1 -> ``[1.0]``, 2 -> ``dca_size_split_2`` (30/70),
    3 -> ``dca_size_split_3`` (20/30/50).  Wick-heavy charts use ``dca_size_split_wick_heavy_2``
    (20/80) at two legs (S6-R27).

    **Spec gap:** SPEC.md §8.3 names a wick-heavy 3-leg split (15/25/60) but §11 defines no
    ``dca_size_split_wick_heavy_3`` key.  Rather than invent one (INTERFACES.md §9 rule 7), the
    3-leg wick-heavy case falls back to ``dca_size_split_3`` and the caller sees the fallback in
    :attr:`PlanBuild.notes`.
    """
    if legs < 1:
        raise PlanError(f"legs must be >= 1, got {legs}")
    if legs == 1:
        return (ONE,)
    if legs == 2:
        raw = config.dca_size_split_wick_heavy_2 if wick_heavy else config.dca_size_split_2
    elif legs == 3:
        raw = config.dca_size_split_3
    else:
        raise PlanError(
            f"{legs} rungs exceeds dca_count_max + 1; SMC-style ladders are forbidden (S2-R9)"
        )
    return tuple(dec(x) for x in raw)


def _ladder_extreme(rungs: Sequence[EntryRung]) -> Decimal | None:
    """The furthest **funded** rung — the price an F6 zone stop must still sit beyond.

    Zero-sized rungs are the TBOT1-C6 low-conviction case (DCA legs armed but not funded); they
    buy nothing, so they do not extend the ladder the stop has to invalidate.
    """
    funded = [r for r in rungs if r.size_fraction > ZERO] or list(rungs)
    return funded[-1].price if funded else None


def rungs_the_stop_invalidates(
    rungs: Sequence[EntryRung], stop_price: Decimal | float, direction: Direction
) -> int:
    """How many leading rungs the final stop still invalidates (**Q17**).

    A rung at or beyond the stop is a rung the trade would add size to at a price where its own
    stop says the position is already dead.  He does not place those: TBOT1 ``[00:38:08]`` prices
    the ladder against the stop he could actually place and declines the rung; S6 ``[01:12:28]``
    hits the CF-14 step-3 collision, takes the tighter stop and re-sites the DCA inside it;
    S6 ``[00:23:05]`` drops the DCA entirely where the stop cannot be placed.

    Zero-sized rungs do not count against the ladder, for the reason :func:`_ladder_extreme`
    already gives: the TBOT1-C6 low-conviction legs are armed but not funded, they buy nothing,
    and the engine skips them at fill time.  The ladder is monotone by construction, so this is a
    prefix count.
    """
    stop = dec(stop_price)
    for i, r in enumerate(rungs):
        if r.size_fraction <= ZERO:
            continue
        dead = r.price <= stop if direction is Direction.LONG else r.price >= stop
        if dead:
            return i
    return len(rungs)


def build_entry_ladder(
    config: Config,
    *,
    direction: Direction,
    entry_price: Decimal | float,
    entry_level_id: str,
    dca_levels: Sequence[Level],
    dca_count: int,
    at_index: int,
    wick_heavy: bool = False,
    conviction: Conviction = Conviction.NORMAL,
) -> tuple[list[EntryRung], tuple[str, ...]]:
    """**CF-17 + CF-18** — build the rungs.  Returns ``(rungs, notes)``.

    The first rung is the lightest and sits at ``entry_price`` (the SR point).  Each DCA takes the
    next structural level *against* the trade (below for a long, above for a short) — never a
    fixed price increment (S2-R10).  Levels that are not strictly beyond the previous rung are
    skipped; if that leaves fewer levels than ``dca_count``, the ladder shrinks and a note says so
    (the caller's remedy is S2-R11: drop a timeframe to locate the second level).

    When conviction is ``LOW`` the DCA legs are **armed but sized to zero** — the bot takes the
    first entry only (TBOT1-C6, SPEC.md §8.2).
    """
    px = dec(entry_price)
    notes: list[str] = []
    prices: list[tuple[Decimal, str]] = [(px, entry_level_id)]

    prev = px
    for lvl in dca_levels:
        if len(prices) - 1 >= dca_count:
            break
        lp = lvl.price_at(at_index)
        beyond = lp < prev if direction is Direction.LONG else lp > prev
        if not beyond or money_close(lp, prev):
            notes.append(f"dca_level_skipped_not_beyond_previous_rung:{lvl.id}")
            continue
        prices.append((lp, lvl.id))
        prev = lp

    got = len(prices) - 1
    if got < dca_count:
        notes.append(
            f"dca_ladder_short:{got}_of_{dca_count}_levels_available "
            f"(S2-R11: drop a timeframe to locate the next level)"
        )

    legs = len(prices)
    split = entry_split(config, legs, wick_heavy=wick_heavy)
    if wick_heavy and legs == 3:
        notes.append("wick_heavy_3_leg_split_unavailable_using_dca_size_split_3")

    if conviction is Conviction.LOW and legs > 1:
        split = (ONE,) + tuple(ZERO for _ in range(legs - 1))
        notes.append("low_conviction_dca_armed_but_sized_to_zero (TBOT1-C6)")

    rungs = [
        EntryRung(
            index=i,
            price=p,
            size_fraction=split[i],
            kind="entry" if i == 0 else "dca",
            level_id=level_id,
        )
        for i, (p, level_id) in enumerate(prices)
    ]
    return rungs, tuple(notes)


def sizing_reference(config: Config, rungs: Sequence[EntryRung]) -> Decimal:
    """**CF-18** — ``size_and_stop_computed_from``: which entry price the stop and the size are
    measured from.

    ``"average_entry"`` (default) is the whole point of CF-18: every downstream calculation —
    break-even, risk budget, R:R, TP trailing — uses the blended average, never entry 1.
    ``"first_entry"`` is the recorded alternative.
    """
    if config.size_and_stop_computed_from == "first_entry":
        return dec(rungs[0].price) if rungs else ZERO
    return blended_entry(rungs)


def blended_entry(rungs: Sequence[EntryRung], *, filled_only: bool = False) -> Decimal:
    """Size-weighted average entry (CF-18).

    ``filled_only=False`` gives ``TradePlan.planned_average_entry`` (assume a full fill; used for
    pre-trade R:R).  ``filled_only=True`` gives ``TradePlan.average_entry`` — the realised
    number every downstream calculation uses, never entry 1
    (``size_and_stop_computed_from = "average_entry"``).
    """
    num, den = ZERO, ZERO
    for r in rungs:
        if filled_only and not r.filled:
            continue
        w = dec(r.size_fraction)
        p = dec(r.fill_price if (filled_only and r.fill_price is not None) else r.price)
        num += p * w
        den += w
    if den <= ZERO:
        return ZERO
    return num / den


# --------------------------------------------------------------------------- CF-14 stop


@dataclass(frozen=True, slots=True)
class StopAnchor:
    """The CF-14 anchor, before the P19 buffer is applied."""

    price: Decimal
    bar_index: int
    side: Literal["upper", "lower"]
    used_body: bool
    reasons: tuple[str, ...] = ()


def stop_distance_pct(reference: Decimal, stop: Decimal) -> Decimal:
    """Stop width as a percentage of the entry reference: ``|ref - stop| / ref * 100``.

    Extracted so there is exactly **one** of these in the package, for the same reason
    :func:`rr_ratio` was: :attr:`StopDecision.stop_pct` compares it against ``min_stop_pct`` at
    build time and the SS12 harness compares it against the same floor at the fill, and two copies
    of the expression could drift apart silently. ``ZERO`` on a non-positive reference.
    """
    if reference <= ZERO:
        return ZERO
    return abs(reference - stop) / reference * HUNDRED


@dataclass(frozen=True, slots=True)
class StopDecision:
    """A placed stop: one price, plus the audit trail of how it got there."""

    price: Decimal
    anchor: StopAnchor
    reference_price: Decimal
    buffer: Decimal
    #: CF-14 step 3 moved the stop inside this opposing level.  The clip runs **after** the
    #: ``min_stop_pct`` widening and wins, by design: step 3 is a hard stated rule and the floor
    #: is ``[OUR CHOICE]``, so inverting the precedence would put our preference above his rule.
    clipped_to_level_id: str | None = None
    #: The CF-06 ``min_stop_pct`` floor fired during placement.  This says the floor **fired**,
    #: not that the final price still respects it: a later clip can pull the stop back inside the
    #: floor, and when it does, both flags are true and :attr:`stop_pct` is below the floor.
    #: Whether the final price respects the floor is derivable from the price; whether the floor
    #: ever fired is not, which is why this is recorded rather than reconstructed.
    widened_to_min_stop_pct: bool = False
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ("CF-14", "P19")

    @property
    def stop_pct(self) -> Decimal:
        """Stop width as a percentage of the reference (blended entry) price."""
        return stop_distance_pct(self.reference_price, self.price)

    @property
    def distance(self) -> Decimal:
        return abs(self.reference_price - self.price)

    def duplicate_price(self, config: Config) -> Decimal:
        """**S4-R34** — leverage stops are duplicated ``duplicate_stop_offset_bps`` (1.5) apart,
        because exchange stops sometimes fail to trigger.

        The second stop sits *further out* than the first.  INTERFACES.md §9 invariant 4: the
        backtest simulates the first stop only; this is an execution-reliability device.
        """
        off = self.price * dec(config.duplicate_stop_offset_bps) / dec(10_000)
        return self.price - off if self.price < self.reference_price else self.price + off


def stop_anchor(
    series: Series,
    config: Config,
    *,
    direction: Direction,
    bar_index: int,
) -> StopAnchor:
    """**CF-14 steps 1-2** — pick the anchor: the qualifying wick, or the body when it is not.

    1. candidate = the wick extreme at the far edge (the low for a long, the high for a short) —
       S2-R12, S6-R17, S8-R18;
    2. if that wick is a **P12 capitulation wick** (TBOT1-R6, and note the TBOT1-C4 split: it is
       still a valid *entry* target) **or** its length exceeds ``stop_wick_max_pct`` (3.0 %) of
       price (S6-R18's rejected $0.60 on a ~$17 coin), fall back to the candle **body** extreme.

    Structure is body-based, stops are wick-based — the apparent S7-C7/S5-C7 contradiction is the
    CF-13 scope collision (SPEC.md §8.9).
    """
    i = bar_index if bar_index >= 0 else len(series) + bar_index
    if not 0 <= i < len(series):
        raise PlanError(f"stop anchor bar {bar_index} outside series of {len(series)} bars")

    side: Literal["upper", "lower"] = "lower" if direction is Direction.LONG else "upper"
    wick_price = dec(series.low[i] if direction is Direction.LONG else series.high[i])
    body_price = dec(series.body_low[i] if direction is Direction.LONG else series.body_high[i])
    wick_len = dec(series.lower_wick[i] if direction is Direction.LONG else series.upper_wick[i])
    close = dec(series.close[i])

    reasons: list[str] = []
    if P.is_capitulation_wick(series, config, i, side):
        reasons.append("capitulation_wick_not_a_stop_anchor (P12, TBOT1-R6)")
    if close > ZERO:
        wick_pct = wick_len / close * HUNDRED
        if wick_pct > dec(config.stop_wick_max_pct) and not money_close(
            wick_pct, dec(config.stop_wick_max_pct)
        ):
            reasons.append(
                f"wick_exceeds_stop_wick_max_pct ({wick_pct}% > {config.stop_wick_max_pct}%)"
            )

    if reasons:
        return StopAnchor(body_price, i, side, True, tuple(reasons))
    return StopAnchor(wick_price, i, side, False, ())


def place_stop(
    series: Series,
    config: Config,
    *,
    direction: Direction,
    bar_index: int,
    reference_price: Decimal | float,
    opposing_levels: Sequence[Level] = (),
    at_index: int | None = None,
    wick_band_edge: Decimal | float | None = None,
    zone_stop_edge: Decimal | float | None = None,
    zone_height: Decimal | float | None = None,
    beyond_price: Decimal | float | None = None,
) -> StopDecision:
    """**CF-14** in full — anchor, opposing-level clip, buffer, ``min_stop_pct`` floor.

    Step 3: if the buffered stop would sit **beyond** an independent opposing S/R level, the stop
    moves to just inside that level rather than straddling it — that level is its own trade
    (S5-R25, S6-R19).  Step 4: the buffer is ``stop_buffer_atr * ATR(atr_period)`` (P19), 0.15 ATR
    by default and **OUR number**.

    Step 4 has **two parameterisations** and the zone one wins where it applies:

    * ``zone_stop_edge`` + ``zone_height`` given — the stop hangs off a **zone**, so it sits
      ``stop_buffer_zone_fraction`` (0.5) × the zone height beyond the zone's far edge (**F6**).
      Three independent pass-2 frames — TBOT1 4:11 BTCUSDT.P 1H, TBOT1 1:09:19 OMUSDT.P 1H,
      S8 1:28:33 SOLUSDT.P 4H — read 0.48 / 0.49 / 0.58 zone-heights below the zone bottom while
      the same three distances are 0.66 % / 2.70 % / 0.81 % of entry.  The fraction clusters, the
      percentage does not, and no ATR multiple is visible anywhere: fraction-of-zone-height is the
      parameterisation, not price percentage and not ATR.
    * otherwise — a stop **not** anchored to a zone (a level, an SFP, a structure break, and the
      CF-06 step-1 LTF re-anchor) — the fallback ``stop_buffer_atr * ATR(atr_period)`` (P19),
      0.15 ATR and still **OUR number**.

    ``beyond_price`` is the price the zone-fraction stop must still sit beyond — the **furthest
    entry rung**, which ``build_plan`` supplies; it defaults to ``reference_price``.  A stop that
    does not invalidate the whole ladder is not a stop, so where a DCA leg reaches past the box
    (a ladder wider than its own zone) the F6 branch stands down and the P19 fallback runs, with
    a reason recorded.  That guard is **[OUR CHOICE]**: the frames show ladders inside the box and
    say nothing about this case.

    The two later steps keep the **P19 ATR** buffer whichever branch fired: the opposing-level
    clip's "just inside" nudge and the F1 band push are offsets in their own right, not the
    anchor rule, and a zone-sized nudge there could put the clip the wrong side of the entry.

    ``min_stop_pct`` (0.5) is a floor on stop *width*: a stop tighter than that is the S7-C8
    "too tight" case.  We widen to the floor rather than skipping — never tighten a stop to fit a
    size, but widening is always safe (S5-R24, S7 ``[00:14:13]``).  Widening-to-floor is
    **[OUR CHOICE]**; CF-06 offers the number but not the remedy.

    ``wick_band_edge`` is the **F1** outer-band edge of the zone the setup hangs off
    (:attr:`~tbot.models.Zone.wick_band_stop_edge`), or ``None`` — which is what it always is
    while ``zone_wick_band_enabled`` is off, the default, so this argument is inert unless the
    flag is switched on.  When it is supplied the stop is pushed **beyond the band**, never
    inside it: F1 reads the two nested boxes as *entries off the body box, stop beyond the wick
    band*, and a stop is only ever widened here, never tightened (S5-R24).
    """
    ref = dec(reference_price)
    anchor = stop_anchor(series, config, direction=direction, bar_index=bar_index)
    atr_buf = P.stop_buffer(series, config, at_index)
    buf = atr_buf
    price = P.apply_stop_buffer(anchor.price, direction, buf)
    reasons: list[str] = list(anchor.reasons)
    clipped: str | None = None
    from_zone = False

    # --- step 4, F6 branch: the stop hangs off a zone -> fraction of the zone height ---------
    if zone_stop_edge is not None and zone_height is not None:
        height = abs(dec(zone_height))
        if height > ZERO:
            zone_buf = P.stop_buffer_zone(config, height)
            zone_price = P.apply_stop_buffer(dec(zone_stop_edge), direction, zone_buf)
            limit = ref
            if beyond_price is not None:
                bp = dec(beyond_price)
                limit = min(ref, bp) if direction is Direction.LONG else max(ref, bp)
            correct_side = (
                zone_price < limit if direction is Direction.LONG else zone_price > limit
            )
            if correct_side or ref <= ZERO:
                buf, price, from_zone = zone_buf, zone_price, True
                reasons.append(
                    f"stop_from_zone_height:{config.stop_buffer_zone_fraction}x{height} "
                    f"(F6, TBOT1 4:11 / TBOT1 1:09:19 / S8 1:28:33)"
                )
            else:
                reasons.append(
                    "zone_fraction_stop_not_beyond_the_entry_ladder_using_atr_buffer "
                    "(F6 fallback)"
                )

    if wick_band_edge is not None:
        band_stop = P.apply_stop_buffer(dec(wick_band_edge), direction, atr_buf)
        beyond = band_stop < price if direction is Direction.LONG else band_stop > price
        if beyond:
            price = band_stop
            reasons.append("stop_beyond_zone_wick_band (F1, S6 frame 52:38)")

    widened = False
    if ref > ZERO:
        floor = dec(config.min_stop_pct)
        pct = abs(ref - price) / ref * HUNDRED
        if pct < floor and not money_close(pct, floor):
            gap = ref * floor / HUNDRED
            price = ref - gap if direction is Direction.LONG else ref + gap
            widened = True
            reasons.append(f"stop_widened_to_min_stop_pct ({pct}% < {floor}%)")

    if config.stop_never_beyond_opposing_level:
        idx = (len(series) - 1) if at_index is None else at_index
        # An "independent opposing level" sits between the anchor and the stop: for a long, a
        # support *below* the entry that our stop would sit under.  This runs **after** the
        # ``min_stop_pct`` widening because CF-14 step 3 is a hard rule and the floor is OURS:
        # a clip that lands inside the floor keeps the clip and records the fact.
        for lvl in opposing_levels:
            lp = lvl.price_at(idx)
            if direction is Direction.LONG:
                if lp < ref and price < lp:
                    price = P.apply_stop_buffer(lp, Direction.SHORT, atr_buf)
                    clipped = lvl.id
            else:
                if lp > ref and price > lp:
                    price = P.apply_stop_buffer(lp, Direction.LONG, atr_buf)
                    clipped = lvl.id
        if clipped is not None:
            # ``widened`` is deliberately NOT reset here.  It records whether the CF-06 floor
            # FIRED, which is a fact about placement; whether the final price still respects the
            # floor is a different fact, derivable from the price itself.  Collapsing the two
            # made the flag report ``False`` for the case that matters most - the floor fired and
            # CF-14 step 3 overruled it - so a saved run could not tell that apart from "the
            # floor never needed to fire".  On one 27-trade sample the flag read true twice, on
            # exactly the two trades that were never clipped, while eleven clipped trades ended
            # with a stop inside the floor and the record denied the floor had fired at all.
            # ``reasons`` always carried both facts; the flags now match it.
            reasons.append(
                f"stop_moved_inside_opposing_level:{clipped} "
                f"(CF-14 step 3, S5-R25, S6-R19)"
            )

    return StopDecision(
        price=price,
        anchor=anchor,
        reference_price=ref,
        buffer=buf,
        clipped_to_level_id=clipped,
        widened_to_min_stop_pct=widened,
        reasons=tuple(reasons),
        source_ids=(("CF-14", "F6", "P19b", "S2-R12", "S6-R17", "S6-R18", "S8-R18") if from_zone
                    else ("CF-14", "P19", "S2-R12", "S6-R17", "S6-R18", "S8-R18")),
    )


# --------------------------------------------------------------------------- CF-06 escalation


@dataclass(frozen=True, slots=True)
class VehicleDecision:
    """The CF-06 wide-stop escalation outcome (SPEC.md §8.6, §8.10)."""

    vehicle: Vehicle
    stop: StopDecision
    max_leverage: Decimal
    skip: bool = False
    tightened: bool = False
    downgraded: bool = False
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ("CF-06",)


def escalate_wide_stop(
    series: Series,
    config: Config,
    *,
    direction: Direction,
    stop: StopDecision,
    preferred_vehicle: Vehicle,
    spot_allowed: bool = True,
    leverage_allowed: bool = True,
    ltf_series: Series | None = None,
    ltf_bar_index: int | None = None,
    opposing_levels: Sequence[Level] = (),
    ltf_at_index: int | None = None,
) -> VehicleDecision:
    """**CF-06** — the ordered escalation of SPEC.md §8.6.  These are stages, not alternatives.

    1. **LTF tighten** — drop ``stop_tighten_tf_steps`` (2) timeframes and re-anchor on the
       nearest qualifying wick/consolidation there (S4-R16, S5-R25, S6-R19, S7-R26, S8
       ``[01:21:46]``).  The caller supplies the already-stepped-down series; without one the
       stage is recorded as unavailable rather than skipped silently.
    2. **Downgrade the vehicle** — if ``stop_pct`` still exceeds ``max_stop_pct_leverage`` (9.0),
       take it on spot, or on leverage capped at ``leverage_downgrade_max_multiple`` (3.0)
       (TBOT1-R7, TBOT1-C3).  Spot is preferred when available — **[OUR CHOICE]**; TBOT1-R7
       offers both without ordering them.
    3. **Skip** — if the vehicle cannot be downgraded (leverage-only account, or spot excluded by
       the coin filter), skip the trade (S7-R7, S7-R26, S8-R23).

    ``wide_stop_policy`` selects the whole ladder (``"tighten_then_downgrade_then_skip"``), or
    ``"size_down_only"`` (accept any width — size always solves from the budget anyway) or
    ``"skip"`` (no tightening, no downgrade).
    """
    policy = config.wide_stop_policy
    cap = dec(config.max_stop_pct_leverage)
    reasons: list[str] = []
    vehicle = preferred_vehicle
    if vehicle is Vehicle.LEVERAGE and not leverage_allowed:
        vehicle = Vehicle.SPOT
        reasons.append("leverage_not_permitted_for_this_symbol_or_window (CF-39, CF-40)")
    if vehicle is Vehicle.SPOT and not spot_allowed:
        vehicle = Vehicle.LEVERAGE
        reasons.append("spot_excluded_by_coin_filter (CF-40)")

    if vehicle is Vehicle.SPOT or policy == "size_down_only":
        # A spot trade has no liquidation and no resting stop: the 9 % ceiling is a leverage
        # constraint (S7-R7, S6 ``[00:08:04]``) and does not bind here.
        return VehicleDecision(vehicle, stop, ONE if vehicle is Vehicle.SPOT else ZERO,
                               reasons=tuple(reasons))

    if money_le(stop.stop_pct, cap):
        return VehicleDecision(vehicle, stop, ZERO, reasons=tuple(reasons))

    reasons.append(f"stop_pct_exceeds_max_stop_pct_leverage ({stop.stop_pct}% > {cap}%)")
    tightened = False

    if policy == "tighten_then_downgrade_then_skip":
        if ltf_series is not None and ltf_bar_index is not None:
            candidate = place_stop(
                ltf_series,
                config,
                direction=direction,
                bar_index=ltf_bar_index,
                reference_price=stop.reference_price,
                opposing_levels=opposing_levels,
                at_index=ltf_at_index,
            )
            if candidate.stop_pct < stop.stop_pct:
                stop = candidate
                tightened = True
                reasons.append(
                    f"ltf_tightened_{config.stop_tighten_tf_steps}_steps "
                    f"to {candidate.stop_pct}% (CF-06 step 1)"
                )
        else:
            reasons.append("ltf_tightening_unavailable_no_lower_timeframe_series (CF-06 step 1)")

        if money_le(stop.stop_pct, cap):
            return VehicleDecision(vehicle, stop, ZERO, tightened=tightened,
                                   reasons=tuple(reasons))

        if spot_allowed:
            reasons.append("vehicle_downgraded_to_spot (CF-06 step 2, TBOT1-R7)")
            return VehicleDecision(Vehicle.SPOT, stop, ONE, tightened=tightened,
                                   downgraded=True, reasons=tuple(reasons))
        if leverage_allowed:
            reasons.append(
                f"vehicle_downgraded_to_leverage_max_"
                f"{config.leverage_downgrade_max_multiple}x (CF-06 step 2, TBOT1-C3)"
            )
            return VehicleDecision(
                Vehicle.LEVERAGE, stop, dec(config.leverage_downgrade_max_multiple),
                tightened=tightened, downgraded=True, reasons=tuple(reasons),
            )

    reasons.append("trade_skipped_stop_too_wide_and_vehicle_cannot_downgrade (CF-06 step 3)")
    return VehicleDecision(vehicle, stop, ZERO, skip=True, tightened=tightened,
                           reasons=tuple(reasons))


# --------------------------------------------------------------------------- CF-27/28 TPs


def tp_count_for(config: Config, trade_class: TradeClass) -> int:
    """**CF-27** — TP count by trade class (SPEC.md §8.7).

    Swing / range 2 (``tp_count_swing``, TP1 mid-range and TP2 the opposite boundary),
    scalp 3 (``tp_count_scalp``), price discovery up to 5
    (``tp_count_price_discovery_max``, from trend-based fib extensions, S6-R36).
    Never fewer than ``tp_min_count`` (2) — S5-R26 is an explicit prohibition on one entry and
    one TP.  A counter-trend trade is a scalp after the CF-03 demotion.
    """
    if trade_class is TradeClass.PRICE_DISCOVERY:
        n = int(config.tp_count_price_discovery_max)
    elif trade_class in (TradeClass.SCALP, TradeClass.COUNTER_TREND):
        n = int(config.tp_count_scalp)
    else:
        n = int(config.tp_count_swing)
    return max(n, int(config.tp_min_count))


def tp_split(config: Config, n: int) -> tuple[Decimal, ...]:
    """**CF-28** — the front-loaded split, applied to the number of TPs *actually placed*.

    2 -> 50/50, 3 -> 40/30/30 (S4-R10, the only numbers in the corpus); 4 and 5 are **OUR**
    extrapolation of his front-loading principle.  Residual after the last TP is closed by the
    trailing stop (``tp_residual_policy = "trail_out"``), never left open.
    """
    table = {
        2: config.tp_split_2,
        3: config.tp_split_3,
        4: config.tp_split_4,
        5: config.tp_split_5,
    }
    if n not in table:
        raise PlanError(f"no CF-28 split for {n} take-profits (2-5 only)")
    return tuple(dec(x) for x in table[n])


def select_take_profits(
    config: Config,
    *,
    direction: Direction,
    levels: Sequence[Level],
    average_entry: Decimal | float,
    trade_class: TradeClass,
    at_index: int,
    measured_move_target: Decimal | float | None = None,
) -> tuple[list[TakeProfit], tuple[str, ...]]:
    """**§8.7** — TPs sit on **structural levels**, never at fixed R multiples (S6-R20, S8-R12).

    Selection rule (**[OUR CHOICE]** — S4-A14/S5-A12/S6-A10/S8-A10 all leave it open): take the
    nearest ``n`` levels in the trade direction whose price is at least ``min_stop_pct`` away
    from the previous TP, ranked by touch count where two levels contend for the same slot,
    capped at the measured-move target where one exists.  The measured "final TP" of a pattern is
    **theoretical** — real profit is taken at intervening levels (S4 ``[00:53:25]``, S5-R39), so
    the target is only appended when the structure does not supply enough levels.

    Returns ``([], reasons)`` when fewer than ``tp_min_count`` levels qualify: S5-R26 forbids one
    entry and one TP, so the plan must be abandoned rather than shipped short.
    """
    avg = dec(average_entry)
    want = tp_count_for(config, trade_class)
    sep_pct = dec(config.min_stop_pct)
    target = None if measured_move_target is None else dec(measured_move_target)
    notes: list[str] = []

    def beyond(a: Decimal, b: Decimal) -> bool:
        return a > b if direction is Direction.LONG else a < b

    priced = [(lvl.price_at(at_index), lvl) for lvl in levels]
    priced = [(p, l) for p, l in priced if beyond(p, avg)]
    if target is not None:
        kept = [(p, l) for p, l in priced if not beyond(p, target)]
        if len(kept) != len(priced):
            notes.append("tp_levels_beyond_measured_move_target_dropped (S4 [00:53:25])")
        priced = kept
    priced.sort(key=lambda pl: abs(pl[0] - avg))

    chosen: list[tuple[Decimal, Level]] = []
    prev = avg
    for price, lvl in priced:
        if len(chosen) >= want:
            break
        gap_pct = abs(price - prev) / prev * HUNDRED if prev > ZERO else HUNDRED
        if gap_pct < sep_pct and not money_close(gap_pct, sep_pct):
            # Too close to the previous TP: contend for that slot on touch count instead.
            if chosen and lvl.touch_count > chosen[-1][1].touch_count:
                chosen[-1] = (price, lvl)
                prev = price
            continue
        chosen.append((price, lvl))
        prev = price

    if len(chosen) < want and target is not None and beyond(target, prev):
        gap_pct = abs(target - prev) / prev * HUNDRED if prev > ZERO else HUNDRED
        if money_ge(gap_pct, sep_pct):
            chosen.append((target, None))  # type: ignore[arg-type]
            notes.append("measured_move_target_used_as_final_tp")

    if len(chosen) < int(config.tp_min_count):
        notes.append(
            f"tp_min_count_not_met ({len(chosen)}/{config.tp_min_count}) — "
            f"S5-R26 forbids one entry and one TP"
        )
        return [], tuple(notes)

    if len(chosen) < want:
        notes.append(f"tp_ladder_short:{len(chosen)}_of_{want}_structural_levels")

    split = tp_split(config, len(chosen))
    tps = [
        TakeProfit(
            index=i,
            price=price,
            size_fraction=split[i],
            level_id=(lvl.id if lvl is not None else None),
        )
        for i, (price, lvl) in enumerate(chosen)
    ]
    return tps, tuple(notes)


def rr_ratio(reference: Decimal, stop: Decimal, target: Decimal) -> Decimal:
    """Reward-to-risk from one entry reference: ``|target - ref| / |ref - stop|``.

    Extracted so there is exactly **one** R:R formula in the package.  :func:`build_plan`
    computes the plan's stored ratios with it, and the §12 harness re-computes the ratio against
    a *realised* trigger fill with it (``backtest/engine.py``).  Two copies of this expression
    could drift apart silently and corrupt every number a backtest produces, which is why the
    harness imports this rather than reimplementing it.

    ``ZERO`` when the stop distance is zero.  **Note the absolute values**: this answers "how big
    is the reward against the risk", not "is the trade the right way round".  A target or a stop
    on the wrong side of ``reference`` still returns a healthy-looking number here, so callers
    must check side separately and first.
    """
    stop_dist = abs(reference - stop)
    if stop_dist <= ZERO:
        return ZERO
    return abs(target - reference) / stop_dist


def rr_for_gate(config: Config, plan: "TradePlan") -> Decimal:
    """**CF-42 / F9** — the R:R figure the G14 gate compares against ``min_rr``.

    ``rr_measured_to`` selects the numerator's target:

    * ``"final_tp"`` (default, **F9**) — the ratio to the **last** TP in the ladder.  Four frames
      of his own TradingView position tool (TBOT1 4:11, TBOT1 22:59, TBOT1 1:09:19, S8 1:28:33)
      read 3.17 / 5.00 / 2.97 / 2.13, and that tool measures to its single **target line** — a
      final target, not a first partial.  *That the tool measures that way is our reading of
      TradingView, not something he states.*
    * ``"tp1"`` — the recorded alternative, and what shipped before F9.  TP1 sits by construction
      much nearer than the final TP (§8.7 takes the *nearest* structural levels), so measuring
      there applies a materially stricter floor than the frames show him applying.

    The *from* side is :func:`sizing_reference`, which CF-18 pins to the blended average entry —
    note that it reads ``size_and_stop_computed_from``, not ``rr_measured_from``.  The two keys
    are duplicates with the same members and the same default; only the former is wired, and that
    predates F9.
    """
    if str(config.rr_measured_to) == "tp1":
        return dec(plan.rr_to_tp1)
    final = plan.rr_to_final_tp
    # A plan built before the field existed (hand-built fixtures) falls back to TP1 rather than
    # silently reading zero and vetoing everything.
    return dec(plan.rr_to_tp1) if final is None else dec(final)


# --------------------------------------------------------------------------- CF-01/02 sizing


@dataclass(frozen=True, slots=True)
class SizeSolution:
    """The §8.8 backwards solve.  ``qty`` is base-asset units, ``notional_usd`` is derived."""

    qty: Decimal
    notional_usd: Decimal
    loss_at_stop_usd: Decimal
    stop_distance: Decimal
    clamped_by_notional: bool = False
    reasons: tuple[str, ...] = ()


def solve_size(
    *,
    average_entry: Decimal | float,
    stop_price: Decimal | float,
    budget: SizingBudget,
) -> SizeSolution:
    """**CF-01 + CF-02** — size is *always* solved backwards (SPEC.md §8.8, S6-R11, S6-R12)::

        qty        = loss_budget_usd / |stop - average_entry|
        qty       *= size_multiplier                      # CF-07 touch decay x CF-03 x CF-35
        notional   = qty * average_entry
        notional   = min(notional, notional_ceiling)       # CF-02
        if clamped: re-solve qty from the clamped notional (risk lands UNDER budget)

    With no clamp the identity ``qty * |stop - average_entry| == loss_budget * multiplier`` holds
    exactly — that is what :func:`check_plan_consistency` re-derives, and it is why the risk cap
    binds at *every* stop width rather than only at convenient ones.
    """
    avg, stop = dec(average_entry), dec(stop_price)
    dist = abs(avg - stop)
    if dist <= ZERO:
        raise PlanError("stop distance is zero — cannot solve size (SPEC.md §8.8)")
    if avg <= ZERO:
        raise PlanError("average entry must be positive")

    qty = budget.loss_budget_usd / dist * budget.size_multiplier
    notional = qty * avg
    reasons: list[str] = []
    clamped = False
    if notional > budget.notional_ceiling_usd and not money_close(
        notional, budget.notional_ceiling_usd
    ):
        notional = budget.notional_ceiling_usd
        qty = notional / avg
        clamped = True
        reasons.append(
            f"notional_clamped_to_ceiling ({budget.notional_ceiling_usd}) — "
            f"risk lands under budget (CF-02)"
        )
    return SizeSolution(
        qty=qty,
        notional_usd=notional,
        loss_at_stop_usd=qty * dist,
        stop_distance=dist,
        clamped_by_notional=clamped,
        reasons=tuple(reasons),
    )


def derive_leverage(
    *, vehicle: Vehicle, notional_usd: Decimal, budget: SizingBudget, max_leverage: Decimal = ZERO
) -> Decimal:
    """**§8.10** — leverage is *derived*, never chosen: ``notional_usd / margin_allocated``, set so
    a stop-out costs exactly the risk budget (S7-R8).  Cross margin is assumed (S4 ``[01:59:38]``).

    **[OUR CHOICE]**: ``margin_allocated`` is read as the loss budget itself — the amount the
    account is prepared to lose — so a full stop-out consumes exactly the margin posted.  Spot is
    always ``1.0``.  ``max_leverage`` caps a CF-06 downgrade at
    ``leverage_downgrade_max_multiple``.
    """
    if vehicle is Vehicle.SPOT:
        return ONE
    margin = budget.target_loss_usd
    if margin <= ZERO:
        return ONE
    lev = dec(notional_usd) / margin
    if max_leverage > ZERO:
        lev = min(lev, max_leverage)
    return lev


# --------------------------------------------------------------------------- consistency


@dataclass(frozen=True, slots=True)
class ConsistencyReport:
    """Result of :func:`check_plan_consistency`."""

    ok: bool
    loss_at_stop_usd: Decimal
    target_loss_usd: Decimal
    realised_risk_pct: Decimal
    problems: tuple[str, ...] = ()


def plan_loss_at_stop(
    plan: TradePlan,
    *,
    use_planned_entry: bool = True,
    reference: Decimal | float | None = None,
) -> Decimal:
    """USD lost if the whole position is stopped out: ``qty * |stop - blended entry|``.

    ``use_planned_entry`` picks ``planned_average_entry`` (the pre-trade number the size was
    solved from) over ``average_entry`` (the realised one, CF-18).  ``reference`` overrides both,
    for the ``size_and_stop_computed_from = "first_entry"`` alternative.
    """
    if reference is not None:
        entry = dec(reference)
    else:
        entry = dec(plan.planned_average_entry if use_planned_entry else plan.average_entry)
    return dec(plan.qty_total) * abs(entry - dec(plan.stop_price))


def check_plan_consistency(
    plan: TradePlan,
    *,
    equity_usd: Decimal | float,
    size_multiplier: Decimal | float = ONE,
    allow_under_budget: bool = True,
    sizing_reference_price: Decimal | float | None = None,
    abs_tol: Decimal = MONEY_ABS_TOL,
    rel_tol: Decimal = MONEY_REL_TOL,
) -> ConsistencyReport:
    """**The plan's own audit.** Does the blended entry, the stop and the size actually produce
    the intended loss?

    Checks, in order:

    1. ``qty_total * |stop - planned_average_entry|`` equals
       ``risk_budget_pct/100 * equity * size_multiplier`` to within tolerance — or is *under* it
       when the CF-02 notional clamp fired and ``allow_under_budget`` is set;
    2. the entry size fractions sum to 1 (or to 1 with the low-conviction zero-weighted DCAs);
    3. the TP size fractions sum to 1 (CF-28 applies to the TPs actually placed);
    4. the stop is on the losing side of the blended entry, and every TP on the winning side;
    5. the rungs step monotonically away from price (first fill lightest, heaviest at the far end
       — S2-R8, S6-R13, S7-R18) and the TPs step monotonically out;
    6. ``tp_min_count`` is met (S5-R26) and the ladder is within ``dca_count_max + 1`` rungs;
    7. ``notional_usd == qty_total * planned_average_entry``.

    Never compares money with ``==``; :func:`~tbot.risk.money_close` is the tolerance helper.
    """
    problems: list[str] = []
    eq = dec(equity_usd)
    mult = dec(size_multiplier)
    entry = dec(plan.planned_average_entry)
    ref = entry if sizing_reference_price is None else dec(sizing_reference_price)
    stop = dec(plan.stop_price)
    loss = plan_loss_at_stop(plan, reference=ref)
    target = dec(plan.risk_budget_pct) / HUNDRED * eq * mult
    realised_pct = (loss / eq * HUNDRED) if eq > ZERO else ZERO

    if not money_close(loss, target, abs_tol=abs_tol, rel_tol=rel_tol):
        if not (allow_under_budget and loss < target):
            problems.append(
                f"loss_at_stop {loss} != risk budget {target} "
                f"(risk_budget_pct={plan.risk_budget_pct}, equity={eq}, multiplier={mult})"
            )

    esum = sum((dec(r.size_fraction) for r in plan.entries), ZERO)
    if not money_close(esum, ONE, abs_tol=abs_tol, rel_tol=rel_tol):
        problems.append(f"entry size fractions sum to {esum}, not 1")
    tsum = sum((dec(t.size_fraction) for t in plan.take_profits), ZERO)
    if not money_close(tsum, ONE, abs_tol=abs_tol, rel_tol=rel_tol):
        problems.append(f"take-profit size fractions sum to {tsum}, not 1")

    long = plan.direction is Direction.LONG
    if long and stop >= entry:
        problems.append(f"long stop {stop} is not below the blended entry {entry}")
    if not long and stop <= entry:
        problems.append(f"short stop {stop} is not above the blended entry {entry}")

    # Rungs must step monotonically away from RUNG 0, not from the blended average.
    # `entry` is the size-weighted average (CF-18) - not a rung, and a convex combination of
    # all of them, so it can sit anywhere inside the ladder. Two consequences, both established
    # by construction in tests/test_plan.py rather than assumed:
    #   * FALSE REJECT of a valid ladder whenever the average lands beyond rung 1. Latent until
    #     dca_size_split_3 was corrected to his stated 15/32.5/52.5 - the old 20/30/50 put the
    #     average at 97.1, coincidentally just above rung 1 at 97.0 in the fixtures.
    #   * UNDER-REPORTS: only the FIRST comparison used the average, so an inversion at
    #     rung 1 could hide behind it while a later rung still tripped. The fix surfaces
    #     MORE problems, not different ones.
    # It did NOT silently accept an invalid ladder: an inversion is caught either by its own
    # comparison or by the next rung's, so the plan was still rejected.
    prev = dec(plan.entries[0].price) if plan.entries else entry
    for r in plan.entries[1:]:
        p = dec(r.price)
        if (long and p >= prev) or (not long and p <= prev):
            problems.append(f"entry rung {r.index} at {p} does not step away from {prev}")
        prev = p
    if plan.entries:
        first = dec(plan.entries[0].size_fraction)
        for r in plan.entries[1:]:
            if dec(r.size_fraction) > ZERO and dec(r.size_fraction) < first:
                problems.append(
                    f"entry rung {r.index} is lighter than the first rung "
                    f"(S2-R8: first fill is the lightest)"
                )

    prev = entry
    for t in plan.take_profits:
        p = dec(t.price)
        if (long and p <= prev) or (not long and p >= prev):
            problems.append(f"take-profit {t.index} at {p} does not step out from {prev}")
        prev = p

    if len(plan.take_profits) < 2:
        problems.append(
            f"{len(plan.take_profits)} take-profits — S5-R26 forbids fewer than tp_min_count"
        )
    if len(plan.entries) > 3:
        problems.append(f"{len(plan.entries)} entry rungs exceeds dca_count_max + 1 (S2-R9)")

    notional = dec(plan.qty_total) * ref
    if not money_close(notional, dec(plan.notional_usd), abs_tol=abs_tol, rel_tol=rel_tol):
        problems.append(f"notional_usd {plan.notional_usd} != qty * blended entry {notional}")

    return ConsistencyReport(
        ok=not problems,
        loss_at_stop_usd=loss,
        target_loss_usd=target,
        realised_risk_pct=realised_pct,
        problems=tuple(problems),
    )


def assert_plan_consistent(
    plan: TradePlan,
    *,
    equity_usd: Decimal | float,
    size_multiplier: Decimal | float = ONE,
    allow_under_budget: bool = True,
    sizing_reference_price: Decimal | float | None = None,
) -> ConsistencyReport:
    """:func:`check_plan_consistency`, raising :class:`PlanInconsistent` on any problem.

    :func:`build_plan` calls this before it returns, so a plan that leaves this module is
    internally consistent by construction.
    """
    rep = check_plan_consistency(
        plan,
        equity_usd=equity_usd,
        size_multiplier=size_multiplier,
        allow_under_budget=allow_under_budget,
        sizing_reference_price=sizing_reference_price,
    )
    if not rep.ok:
        raise PlanInconsistent(
            f"plan {plan.id} is internally inconsistent:\n  " + "\n  ".join(rep.problems)
        )
    return rep


# --------------------------------------------------------------------------- build


@dataclass(frozen=True, slots=True)
class PlanBuild:
    """What :func:`build_plan` returns: the plan, or the reasons there isn't one."""

    plan: TradePlan | None
    stop: StopDecision | None = None
    vehicle_decision: VehicleDecision | None = None
    size: SizeSolution | None = None
    consistency: ConsistencyReport | None = None
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.plan is not None


def build_plan(inputs: PlanInputs, config: Config) -> PlanBuild:
    """Turn a qualified :class:`~tbot.models.Setup` into a complete
    :class:`~tbot.models.TradePlan` (SPEC.md §8).

    Order of construction is entry ladder -> stop -> take-profits, then size, then vehicle
    (INTERFACES.md §9 invariant 3).  Never forces a setup: when a stage cannot be satisfied the
    result carries ``plan=None`` and the reasons, and an empty plan list is a valid, expected
    outcome (PL-9, S6-R46, INTERFACES.md §9 invariant 5).
    """
    setup = inputs.setup
    if setup.vetoes:
        return PlanBuild(None, reasons=tuple(f"setup_vetoed:{v}" for v in setup.vetoes))
    if len(inputs.series) == 0:
        raise PlanError("cannot build a plan from an empty series")

    at = inputs.resolved_index()
    reasons: list[str] = []
    notes: list[str] = []
    src: list[str] = list(setup.source_ids)

    # --- 0. entry family (CF-16) -----------------------------------------------------------
    family = setup.entry_family
    if not entry_family_enabled(config, family):
        return PlanBuild(None, reasons=(f"entry_family_disabled:{family.value} (CF-16)",))
    order_type = order_type_for_family(config, family)
    src.append("CF-16")

    # --- 1. entry ladder (CF-17, CF-18) -----------------------------------------------------
    zone_depth = inputs.zone.depth_atr if inputs.zone is not None else None
    n_dca = dca_leg_count(
        config,
        trade_class=setup.trade_class,
        entry_family=family,
        zone_depth_atr=zone_depth,
        single_entry_play=inputs.single_entry_play,
    )
    entry_price = (
        inputs.zone.entry_price_pmt
        if inputs.zone is not None and inputs.zone.entry_price_pmt is not None
        else inputs.entry_level.price_at(at)
    )
    rungs, ladder_notes = build_entry_ladder(
        config,
        direction=setup.direction,
        entry_price=entry_price,
        entry_level_id=inputs.entry_level.id,
        dca_levels=inputs.dca_levels,
        dca_count=n_dca,
        at_index=at,
        wick_heavy=inputs.wick_heavy,
        conviction=setup.conviction,
    )
    notes.extend(ladder_notes)
    src.extend(("CF-17", "CF-18"))
    planned_avg = blended_entry(rungs)
    # CF-18: the stop and the size are measured from ``size_and_stop_computed_from`` — the
    # blended average by default, entry 1 only under the recorded alternative.
    ref_price = sizing_reference(config, rungs)

    # --- 2. stop (CF-14 + F6, and F1 when the band is switched on) ---------------------------
    # F6: this setup hangs off a zone, so the stop is placed by the *zone-height fraction* rule
    # (``stop_buffer_zone_fraction`` × the box height beyond the box's far edge), not by the
    # ``stop_buffer_atr`` fallback — three pass-2 frames, three pairs, three timeframes.
    # F1: the entry ladder above priced off the zone's **body** box (``entry_price_pmt``); the
    # stop additionally goes beyond the outer **wick** band when the zone carries one.
    # ``wick_band_stop_edge`` is ``None`` for every zone while ``zone_wick_band_enabled`` is off
    # (the default).  The band does **not** survive the CF-06 step-1 LTF tightening below, and
    # neither does the zone fraction: CF-06 re-anchors on a lower timeframe where this zone does
    # not exist, so the LTF probe falls back to P19 — an established risk override keeps
    # precedence over frame geometry.
    band_edge = inputs.zone.wick_band_stop_edge if inputs.zone is not None else None
    zone_edge = inputs.zone.body_stop_edge if inputs.zone is not None else None
    zone_height = inputs.zone.depth if inputs.zone is not None else None
    stop = place_stop(
        inputs.series,
        config,
        direction=setup.direction,
        bar_index=inputs.stop_anchor_index,
        reference_price=ref_price,
        opposing_levels=inputs.opposing_levels,
        at_index=at,
        wick_band_edge=band_edge,
        zone_stop_edge=zone_edge,
        zone_height=zone_height,
        beyond_price=_ladder_extreme(rungs),
    )
    src.extend(stop.source_ids)
    if band_edge is not None:
        src.append("F1")

    # --- 3. wide-stop escalation and vehicle (CF-06, §8.10) ---------------------------------
    preferred = Vehicle.LEVERAGE if inputs.leverage_allowed else Vehicle.SPOT
    vd = escalate_wide_stop(
        inputs.series,
        config,
        direction=setup.direction,
        stop=stop,
        preferred_vehicle=preferred,
        spot_allowed=inputs.spot_allowed,
        leverage_allowed=inputs.leverage_allowed,
        ltf_series=inputs.ltf_series,
        ltf_bar_index=inputs.ltf_stop_anchor_index,
        opposing_levels=inputs.opposing_levels,
    )
    stop = vd.stop
    src.append("CF-06")
    if vd.skip:
        return PlanBuild(None, stop=stop, vehicle_decision=vd,
                         reasons=vd.reasons, notes=tuple(notes))

    # --- 3b. Q17: the stop constrains the ladder, not the reverse ---------------------------
    # CF-14 step 3 has now had the last word on the stop - and it keeps it, exactly as
    # CONFLICTS.md rules and as he does himself at S6 [01:12:28].  What no ruling covered is what
    # happens to a ladder the clipped stop no longer invalidates.  He answers that too: the rung
    # moves inside the stop, or it is dropped and the trade goes one-entry (S6 [00:23:05]; one
    # entry sanctioned at S8 [00:31:44], S8 [01:02:28], S5 [00:41:10]).  Re-siting requires
    # inventing a price, so this drops - the remedy he states in words.
    #
    # Rebuilt through build_entry_ladder rather than by slicing the list, so entry_split
    # renormalises: a lone survivor sizes at 1.0, not at the 0.15 it carried as leg one of three.
    # The stop is NOT re-placed afterwards.  That would be circular, and it is unnecessary:
    # dropping the rungs nearest the stop moves the average away from it, so the CF-06 floor can
    # only get further from violation, never closer.
    if config.entry_ladder_must_sit_inside_stop:
        keep = rungs_the_stop_invalidates(rungs, stop.price, setup.direction)
        if keep < len(rungs):
            # Captured BEFORE build_entry_ladder rebinds ``rungs``: after the rebuild the
            # original length is gone, and the note below reports how much of the ladder went.
            dropped_from = len(rungs)
            if keep == 0:
                return PlanBuild(
                    None, stop=stop, vehicle_decision=vd,
                    reasons=("no_entry_rung_the_stop_invalidates (Q17, TBOT1 [00:38:08])",),
                    notes=tuple(notes),
                )
            rungs, regrown = build_entry_ladder(
                config,
                direction=setup.direction,
                entry_price=entry_price,
                entry_level_id=inputs.entry_level.id,
                dca_levels=inputs.dca_levels,
                dca_count=keep - 1,
                at_index=at,
                wick_heavy=inputs.wick_heavy,
                conviction=setup.conviction,
            )
            notes.extend(n for n in regrown if n not in notes)
            notes.append(
                f"entry_rungs_dropped_outside_stop:{keep}_of_{dropped_from}_kept "
                f"stop={stop.price} (Q17)"
            )
            planned_avg = blended_entry(rungs)
            ref_price = sizing_reference(config, rungs)

    # --- 4. take-profits (CF-27, CF-28) -----------------------------------------------------
    tps, tp_notes = select_take_profits(
        config,
        direction=setup.direction,
        levels=inputs.tp_levels,
        average_entry=planned_avg,
        trade_class=setup.trade_class,
        at_index=at,
        measured_move_target=inputs.measured_move_target,
    )
    notes.extend(tp_notes)
    if not tps:
        return PlanBuild(None, stop=stop, vehicle_decision=vd,
                         reasons=tuple(n for n in tp_notes if "tp_min_count" in n) or
                         ("no_structural_take_profit_levels",), notes=tuple(notes))
    src.extend(("CF-27", "CF-28"))

    # --- 5. size (CF-01, CF-02) -------------------------------------------------------------
    size = solve_size(
        average_entry=ref_price, stop_price=stop.price, budget=inputs.budget
    )
    notes.extend(size.reasons)
    src.extend(inputs.budget.source_ids)

    # --- 6. assemble ------------------------------------------------------------------------
    is_spot = vd.vehicle is Vehicle.SPOT
    leverage = derive_leverage(
        vehicle=vd.vehicle,
        notional_usd=size.notional_usd,
        budget=inputs.budget,
        max_leverage=vd.max_leverage if vd.downgraded else ZERO,
    )
    tp1 = dec(tps[0].price)
    rr = rr_ratio(ref_price, stop.price, tp1)
    final_tp = dec(tps[-1].price)
    # F9 — the same ratio measured to the **final** TP.  Both are carried on the plan; CF-42's
    # ``rr_measured_to`` decides which one the G14 gate reads (see :func:`rr_for_gate`).
    rr_final = rr_ratio(ref_price, stop.price, final_tp)
    expected_move = abs(final_tp - planned_avg) / planned_avg * HUNDRED

    plan = TradePlan(
        id=f"{setup.id}:plan",
        setup_id=setup.id,
        symbol=setup.symbol,
        direction=setup.direction,
        trade_class=setup.trade_class,
        vehicle=vd.vehicle,
        leverage=leverage,
        entries=rungs,
        stop_price=stop.price,
        take_profits=tps,
        qty_total=size.qty,
        notional_usd=size.notional_usd,
        risk_budget_pct=inputs.budget.risk_budget_pct,
        average_entry=blended_entry(rungs, filled_only=True),
        planned_average_entry=planned_avg,
        rr_to_tp1=rr,
        expected_move_pct=expected_move,
        invalidation_level_id=inputs.invalidation_level_id or inputs.entry_level.id,
        # CF-05: spot carries no resting stop; the synthetic stop exists only for sizing, and the
        # real exit is a close beyond the level plus the CF-15 flip confirmation.  **Our
        # construct, not his.**
        stop_is_synthetic=is_spot and bool(config.spot_synthetic_stop_for_sizing),
        spot_exit_rule=str(config.spot_exit_mode) if is_spot else None,
        bias_invalidation_price=inputs.bias_invalidation_price,
        expires_at_index=inputs.expires_at_index,
        source_ids=tuple(dict.fromkeys(src)),
        rr_to_final_tp=rr_final,
        stop_widened_to_min_pct=stop.widened_to_min_stop_pct,
        stop_clipped_to_level_id=stop.clipped_to_level_id,
    )

    rep = assert_plan_consistent(
        plan,
        equity_usd=inputs.budget.equity_usd,
        size_multiplier=inputs.budget.size_multiplier,
        sizing_reference_price=ref_price,
    )
    notes.append(f"order_type:{order_type.value}")
    if is_spot:
        notes.append(f"spot_invalidation_timeframe:{config.spot_invalidation_timeframe}")
    return PlanBuild(
        plan=plan,
        stop=stop,
        vehicle_decision=vd,
        size=size,
        consistency=rep,
        reasons=tuple(reasons),
        notes=tuple(notes),
    )
