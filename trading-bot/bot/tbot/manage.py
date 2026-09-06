"""tbot.manage — SPEC.md §9, the trade-management state machine.

The §9.2 transition table is implemented **as a table**: :data:`TRANSITIONS` is an ordered tuple
of :class:`Transition` records, each naming the states it fires from, the event that fires it,
the guard that must hold, the state it lands in, the action it performs and — crucially — the
**rule ID** that justifies it.  :meth:`TradeManager.handle` walks the table in order and applies
the first row whose state, event and guard all match; every application appends a
:class:`TransitionLog` carrying that rule ID.  Nothing moves the machine except a row in the
table, and no row moves it without leaving a logged reason.

Trailing (CF-29, §9.3):

* **TP1 hit** -> stop to break-even at the **average entry**, not entry 1
  (``break_even_reference = "average_entry"``, CF-18, S4-R11, S5-R27);
* **TP2 hit** -> stop to **TP1's price** (``trail_on_tp2 = "tp1_price"``);
* **TPn (n >= 3)** -> stop to TP(n-1)'s price;
* **a DCA rung fills** -> the stop is *unchanged*; ``average_entry`` moves, so the loss budget is
  re-verified and the **excess quantity is closed** rather than the stop widened (S6-R11,
  S6-R12); and **TP1 is re-mapped to the original entry price**, which is now an SR point
  (S8-R20).
* Being trailed out is a **normal, accepted outcome** (CF-29, S5 ``[00:40:00]``), not a failure.

The module holds no module-level mutable state.  A :class:`TradeManager` owns exactly one
plan/position pair and mutates only that :class:`~tbot.models.Position` (which SPEC.md §2 marks
as the mutable half of the model, written by exactly this state machine) — the
:class:`~tbot.models.TradePlan` itself is never mutated: ``stop_price`` and the initial risk are
frozen, and trailing writes ``Position.current_stop`` (INTERFACES.md §9 invariant 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Callable, Sequence

import tbot.primitives as P
from tbot.config import Config
from tbot.models import (
    Account,
    CloseReason,
    Direction,
    PositionState,
    TakeProfit,
    TradePlan,
    Position,
    Vehicle,
    dec,
)
from tbot.plan import blended_entry
from tbot.risk import (
    ZERO,
    cut_on_level_loss_applies,
    money_close,
    money_le,
)

__all__ = [
    "EventKind",
    "Event",
    "TransitionLog",
    "TradeContext",
    "Transition",
    "TRANSITIONS",
    "TradeManager",
    "break_even_price",
    "trail_target",
    "reentry_allowed",
    "ReentryState",
]


# --------------------------------------------------------------------------- events


class EventKind(str, Enum):
    """Every input the §9.2 table reacts to.

    The four workhorses are :attr:`BAR_CLOSED`, :attr:`RUNG_FILLED`, :attr:`TP_TOUCHED` and
    :attr:`STOP_TOUCHED`; the rest are structural signals raised by the detector layer (a trend
    flip, a dead zone, an MSB, a spot flip confirmation) which this module consumes but never
    computes for itself (INTERFACES.md §6 rule 6).
    """

    PLAN_PUBLISHED = "plan_published"
    BAR_CLOSED = "bar_closed"
    RUNG_FILLED = "rung_filled"
    CONFIRMATION_COMPLETED = "confirmation_completed"
    TP_TOUCHED = "tp_touched"
    STOP_TOUCHED = "stop_touched"
    TREND_FLIPPED = "trend_flipped"
    ZONE_INVALIDATED = "zone_invalidated"
    BLACKOUT_STARTED = "blackout_started"
    LEVEL_LOST = "level_lost"
    MSB_AGAINST = "msb_against"
    SPOT_FLIP_CONFIRMED = "spot_flip_confirmed"
    MACRO_MSB_TWO_STEP = "macro_msb_two_step"
    AVERAGE_UP_OPPORTUNITY = "average_up_opportunity"
    HTF_DOUBLE_TOP = "htf_double_top"
    REGIME_TRIM_SIGNAL = "regime_trim_signal"
    REENTRY_TRIGGER = "reentry_trigger"


@dataclass(frozen=True, slots=True)
class Event:
    """One input to the machine.  Immutable; the machine never edits an event."""

    kind: EventKind
    bar_index: int
    price: Decimal | None = None
    rung_index: int | None = None
    tp_index: int | None = None
    fill_price: Decimal | None = None
    timestamp: datetime | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TransitionLog:
    """The audit record.  One per applied transition, in application order."""

    bar_index: int
    transition_id: str
    rule_id: str
    event: EventKind
    from_state: PositionState
    to_state: PositionState
    actions: tuple[str, ...] = ()
    detail: str = ""


# --------------------------------------------------------------------------- context


@dataclass(slots=True)
class TradeContext:
    """Everything a guard or action needs beyond the plan and the position.

    ``loss_budget_usd`` is the CF-01 number :mod:`tbot.risk` solved the size from; it is what the
    S6-R11/S6-R12 re-verification on a DCA fill compares against.  ``atr`` is only used for the
    P17 stale test, which is off by default.
    """

    config: Config
    plan: TradePlan
    position: Position
    account: Account = Account.LEVERAGE_SWING
    loss_budget_usd: Decimal = ZERO
    #: The rung-1 price, frozen at publication: TP1 re-maps here once a DCA fills (S8-R20).
    original_entry_price: Decimal | None = None
    #: Set once TP1 has been re-mapped, so a second DCA fill does not re-map it again.
    tp1_remapped: bool = False

    def __post_init__(self) -> None:
        if self.original_entry_price is None and self.plan.entries:
            self.original_entry_price = dec(self.plan.entries[0].price)

    @property
    def direction(self) -> Direction:
        return self.plan.direction

    @property
    def unfilled_rungs(self) -> tuple[int, ...]:
        return tuple(r.index for r in self.plan.entries if not r.filled)

    @property
    def final_tp_index(self) -> int:
        return self.plan.take_profits[-1].index if self.plan.take_profits else -1


# --------------------------------------------------------------------------- trailing


def break_even_price(ctx: TradeContext) -> Decimal:
    """**CF-29 / CF-18** — ``break_even_reference``.

    ``"average_entry"`` (default) is the realised, size-weighted average over *filled* rungs —
    the whole point of CF-18 is that break-even is never entry 1.  ``"first_entry"`` is the
    alternative.
    """
    if ctx.config.break_even_reference == "first_entry":
        return dec(ctx.plan.entries[0].price) if ctx.plan.entries else ZERO
    avg = dec(ctx.position.average_entry)
    return avg if avg > ZERO else dec(ctx.plan.planned_average_entry)


def trail_target(ctx: TradeContext, tp_index: int) -> tuple[Decimal, str]:
    """**CF-29 / §9.3** — where the stop goes after TP ``tp_index`` (0-based) is hit.

    * TP1 (index 0): ``trail_on_tp1`` — ``"break_even"`` (default), ``"none"``.
    * TP2 (index 1): ``trail_on_tp2`` — ``"tp1_price"`` (default), ``"break_even"``
      (S6-R21's looser restatement, which CF-29 discards as an alternative but keeps as config).
    * TP3+ : the previous TP's price.

    Returns ``(price, stop_reason)``; ``stop_reason`` matches the SPEC.md §2.8 vocabulary
    (``"break_even"``, ``"tp1"``, ``"tp_n_minus_1"``).
    """
    cfg = ctx.config
    if tp_index == 0:
        if cfg.trail_on_tp1 == "none":
            return dec(ctx.position.current_stop), "initial"
        return break_even_price(ctx), "break_even"
    if tp_index == 1:
        if cfg.trail_on_tp2 == "break_even":
            return break_even_price(ctx), "break_even"
        return dec(ctx.plan.take_profits[0].price), "tp1"
    return dec(ctx.plan.take_profits[tp_index - 1].price), "tp_n_minus_1"


def _is_improvement(ctx: TradeContext, new_stop: Decimal) -> bool:
    """A trailed stop only ever moves toward the position (never away): a long's stop rises."""
    cur = dec(ctx.position.current_stop)
    if ctx.direction is Direction.LONG:
        return new_stop > cur and not money_close(new_stop, cur)
    return new_stop < cur and not money_close(new_stop, cur)


# --------------------------------------------------------------------------- actions


def _recompute_average(ctx: TradeContext) -> Decimal:
    avg = blended_entry(ctx.plan.entries, filled_only=True)
    ctx.position.average_entry = avg
    return avg


def _filled_qty(ctx: TradeContext) -> Decimal:
    frac = sum(
        (dec(r.size_fraction) for r in ctx.plan.entries if r.filled), ZERO
    )
    return dec(ctx.plan.qty_total) * frac


def _remap_tp1_to_original_entry(ctx: TradeContext) -> tuple[str, ...]:
    """**S8-R20 / §9.3** — once a DCA fills, TP1 re-maps to the **original entry price**.

    That price is now an SR point: for a long, rung 1 sits above the new blended average and
    price must reclaim it.  The remaining TPs keep their structural prices — they "shift out"
    in the sense that the average entry has moved toward the stop, so every remaining target is
    further away in R terms.  Re-pricing them as well would move take-profits off the structural
    levels that justified them, which S6-R20/S8-R12 forbid.
    """
    if ctx.tp1_remapped or not ctx.plan.take_profits or ctx.original_entry_price is None:
        return ()
    tp1 = ctx.plan.take_profits[0]
    old = dec(tp1.price)
    new = dec(ctx.original_entry_price)
    avg = dec(ctx.position.average_entry)
    beyond = new > avg if ctx.direction is Direction.LONG else new < avg
    if not beyond:
        return (f"tp1_remap_skipped_original_entry_not_beyond_average ({new} vs {avg})",)
    ctx.plan.take_profits[0] = TakeProfit(
        index=tp1.index,
        price=new,
        size_fraction=tp1.size_fraction,
        level_id=tp1.level_id,
        hit=tp1.hit,
        hit_index=tp1.hit_index,
    )
    ctx.tp1_remapped = True
    return (f"tp1_remapped_from_{old}_to_original_entry_{new} (S8-R20)",)


def _reverify_budget(ctx: TradeContext) -> tuple[str, ...]:
    """**S6-R11 / S6-R12 / §9.3** — after a fill the average moved; the stop did **not**.

    If the new average breaches the loss budget, close the **excess quantity** rather than
    widening the stop.  Never tighten a stop to fit a size, and never widen one to fit a fill.
    """
    if ctx.loss_budget_usd <= ZERO:
        return ()
    avg = dec(ctx.position.average_entry)
    stop = dec(ctx.plan.stop_price)
    dist = abs(avg - stop)
    if dist <= ZERO:
        return ()
    qty = dec(ctx.position.qty_open)
    loss = qty * dist
    if money_le(loss, ctx.loss_budget_usd):
        return ()
    allowed = ctx.loss_budget_usd / dist
    excess = qty - allowed
    ctx.position.qty_open = allowed
    return (
        f"closed_excess_qty_{excess}_to_restore_loss_budget "
        f"({loss} > {ctx.loss_budget_usd}) (S6-R11, S6-R12)",
    )


def _close(ctx: TradeContext, ev: Event, reason: CloseReason) -> tuple[str, ...]:
    pos = ctx.position
    pos.close_reason = reason
    pos.closed_index = ev.bar_index
    pos.qty_open = ZERO
    entry = dec(pos.average_entry) or dec(ctx.plan.planned_average_entry)
    initial_risk = abs(entry - dec(ctx.plan.stop_price))
    exit_price = dec(ev.price) if ev.price is not None else dec(pos.current_stop)
    if initial_risk > ZERO and entry > ZERO:
        signed = (exit_price - entry) * Decimal(ctx.direction.sign)
        pos.r_multiple = signed / initial_risk
    return (f"closed:{reason.value}",)


# --------------------------------------------------------------------------- the table


GuardFn = Callable[["TradeContext", Event], bool]
ActionFn = Callable[["TradeContext", Event], "tuple[str, ...]"]


@dataclass(frozen=True, slots=True)
class Transition:
    """One row of the SPEC.md §9.2 table."""

    id: str
    from_states: tuple[PositionState, ...]
    event: EventKind
    to: PositionState | None       #: ``None`` = stay in the current state
    rule_id: str
    description: str
    guard: GuardFn = lambda ctx, ev: True
    action: ActionFn = lambda ctx, ev: ()

    def matches(self, state: PositionState, ev: Event, ctx: TradeContext) -> bool:
        return state in self.from_states and ev.kind is self.event and self.guard(ctx, ev)


_LIVE = (PositionState.PARTIAL, PositionState.OPEN, PositionState.MANAGING)


# ---- guards ---------------------------------------------------------------------------------

def _g_expired(ctx: TradeContext, ev: Event) -> bool:
    exp = ctx.plan.expires_at_index
    return exp is not None and ev.bar_index >= exp


def _g_leverage(ctx: TradeContext, ev: Event) -> bool:
    return ctx.plan.vehicle is Vehicle.LEVERAGE


def _g_spot(ctx: TradeContext, ev: Event) -> bool:
    return ctx.plan.vehicle is Vehicle.SPOT


def _g_cut_applies(ctx: TradeContext, ev: Event) -> bool:
    """**CF-43** — the ``long_term`` book is never cut on a level loss (S2-C6)."""
    return cut_on_level_loss_applies(ctx.config, ctx.account)


def _g_structural_cut(ctx: TradeContext, ev: Event) -> bool:
    return bool(ctx.config.structural_stale_exit_enabled) and _g_cut_applies(ctx, ev)


def _g_long_term(ctx: TradeContext, ev: Event) -> bool:
    return ctx.account is Account.LONG_TERM


def _g_final_tp(ctx: TradeContext, ev: Event) -> bool:
    return ev.tp_index is not None and ev.tp_index == ctx.final_tp_index


def _g_tp1_not_final(ctx: TradeContext, ev: Event) -> bool:
    return ev.tp_index == 0 and not _g_final_tp(ctx, ev)


def _g_tp_n_not_final(ctx: TradeContext, ev: Event) -> bool:
    return ev.tp_index is not None and ev.tp_index >= 1 and not _g_final_tp(ctx, ev)


def _g_trailed_out(ctx: TradeContext, ev: Event) -> bool:
    """A stop hit **after** a TP is a trail-out, not a loss (CF-29, S5 ``[00:40:00]``)."""
    return ctx.position.tps_hit >= 1


def _g_stale(ctx: TradeContext, ev: Event) -> bool:
    """P17, off by default (``stale_exit_enabled = false``) — no number exists for it."""
    pos = ctx.position
    return P.is_stale_trade(
        ctx.config,
        bars_in_trade=pos.bars_in_trade,
        mfe_atr=pos.mfe_atr,
        mae_atr=pos.mae_atr,
        tps_hit=pos.tps_hit,
    )


def _g_average_up(ctx: TradeContext, ev: Event) -> bool:
    """**CF-19**, disabled by default.  All four conditions of SPEC.md §8.4 must hold.

    1. the first entry is filled;
    2. price has moved ``average_up_trigger_atr`` (2.0, **OUR number**) in favour without filling
       the DCA — read off ``Position.mfe_atr``, which is already ATR-normalised;
    3. the add price is an **SR point**, never a zone interior or open air
       (``average_up_only_at_sr_point``, S3-R14) — the caller says so in ``Event.detail``;
    4. the blended average still leaves the trade inside its risk budget with the **original**
       stop.
    """
    cfg = ctx.config
    if not cfg.average_up_enabled:
        return False
    if not any(r.filled for r in ctx.plan.entries):
        return False
    if float(ctx.position.mfe_atr) < cfg.average_up_trigger_atr:
        return False
    if cfg.average_up_only_at_sr_point and "sr_point" not in ev.detail:
        return False
    if ev.price is None or ctx.loss_budget_usd <= ZERO:
        return False
    # Condition 4: re-check the budget against the ORIGINAL stop (S3-R14, §8.4).
    filled = [r for r in ctx.plan.entries if r.filled]
    frac = sum((dec(r.size_fraction) for r in filled), ZERO)
    add_frac = sum((dec(r.size_fraction) for r in ctx.plan.entries if not r.filled), ZERO)
    if add_frac <= ZERO:
        return False
    num = sum((dec(r.fill_price or r.price) * dec(r.size_fraction) for r in filled), ZERO)
    new_avg = (num + dec(ev.price) * add_frac) / (frac + add_frac)
    qty = dec(ctx.plan.qty_total)
    return money_le(qty * abs(new_avg - dec(ctx.plan.stop_price)), ctx.loss_budget_usd)


# ---- actions --------------------------------------------------------------------------------

def _a_arm(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    ctx.position.current_stop = dec(ctx.plan.stop_price)
    ctx.position.stop_reason = "initial"
    return ("resting_limits_placed" if ctx.plan.entries else "confirmation_watcher_registered",)


def _a_fill_rung(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    out: list[str] = []
    idx = ev.rung_index if ev.rung_index is not None else 0
    for r in ctx.plan.entries:
        if r.index == idx and not r.filled:
            r.filled = True
            r.fill_index = ev.bar_index
            r.fill_price = dec(ev.fill_price if ev.fill_price is not None else r.price)
            out.append(f"rung_{idx}_filled_at_{r.fill_price}")
            break
    avg = _recompute_average(ctx)
    ctx.position.qty_open = _filled_qty(ctx)
    if ctx.position.opened_index is None:
        ctx.position.opened_index = ev.bar_index
    out.append(f"average_entry={avg}")
    out.append("stop_unchanged (§9.3: a DCA fill never moves the stop)")
    if idx > 0:
        out.extend(_remap_tp1_to_original_entry(ctx))
        out.extend(_reverify_budget(ctx))
    return tuple(out)


def _a_tp(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    """Close ``tp_split[n]`` of the position and trail the stop (CF-28, CF-29)."""
    out: list[str] = []
    i = ev.tp_index if ev.tp_index is not None else 0
    tp = ctx.plan.take_profits[i]
    tp.hit = True
    tp.hit_index = ev.bar_index
    ctx.position.tps_hit = max(ctx.position.tps_hit, i + 1)
    closed = dec(ctx.plan.qty_total) * dec(tp.size_fraction)
    ctx.position.qty_open = max(dec(ctx.position.qty_open) - closed, ZERO)
    out.append(f"closed_tp_split[{i}]={tp.size_fraction} qty={closed}")
    new_stop, reason = trail_target(ctx, i)
    if reason != "initial" and _is_improvement(ctx, new_stop):
        ctx.position.current_stop = new_stop
        ctx.position.stop_reason = reason
        out.append(f"stop_trailed_to_{new_stop} ({reason})")
    else:
        out.append(f"stop_not_moved (would not improve on {ctx.position.current_stop})")
    return tuple(out)


def _a_final_tp(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    out = list(_a_tp(ctx, ev))
    if dec(ctx.position.qty_open) > ZERO:
        # tp_residual_policy = "trail_out": the residual is closed by the trailing stop, never
        # left open (CF-28).
        out.append(f"residual_{ctx.position.qty_open}_policy_{ctx.config.tp_residual_policy}")
        ctx.position.qty_open = ZERO
    out.extend(_close(ctx, ev, CloseReason.TP_FINAL))
    return tuple(out)


def _a_bar(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    ctx.position.bars_in_trade += 1
    return (f"bars_in_trade={ctx.position.bars_in_trade}",)


def _a_partial_and_be(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    """§9.3 — HTF double top after a large run (S7-R35, S8-R25) and the S3-R32 regime trim:
    take partial profit and move the stop to break-even **or better**, regardless of expected
    resolution."""
    be = break_even_price(ctx)
    out: list[str] = []
    if _is_improvement(ctx, be):
        ctx.position.current_stop = be
        ctx.position.stop_reason = "break_even"
        out.append(f"stop_to_break_even_{be}")
    else:
        out.append(f"stop_already_better_than_break_even ({ctx.position.current_stop})")
    return tuple(out)


def _a_average_up(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    """**CF-19** — add at the next SR point, never into a zone interior or open air (S3-R14)."""
    out: list[str] = []
    for r in ctx.plan.entries:
        if not r.filled:
            r.filled = True
            r.fill_index = ev.bar_index
            r.fill_price = dec(ev.price)
            out.append(f"averaged_up_rung_{r.index}_at_{r.fill_price} (CF-19)")
            break
    out.append(f"average_entry={_recompute_average(ctx)}")
    ctx.position.qty_open = _filled_qty(ctx)
    out.append("stop_unchanged_original (§8.4 condition 4)")
    return tuple(out)


def _mk_close(reason: CloseReason) -> ActionFn:
    def _fn(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
        return _close(ctx, ev, reason)
    return _fn


def _a_stop_out(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    """A stop-out with no TP behind it.  §9.2: increment the daily loss counter if the close is
    below ``average_entry`` net of fees — that accounting lives in :mod:`tbot.risk`
    (``loss_definition``), so the action only flags it."""
    out = list(_close(ctx, ev, CloseReason.STOP))
    out.append("daily_loss_counter_candidate (CF-44, S2-R21; loss_definition applies)")
    return tuple(out)


def _a_cancel_unfilled(ctx: TradeContext, ev: Event) -> tuple[str, ...]:
    """S7-R17/S7-A19 — cancel **unfilled limits only**.  An already-filled position is not closed
    by this rule; that is why the row fires from ``ARMED`` alone."""
    n = len(ctx.unfilled_rungs)
    return (f"cancelled_{n}_unfilled_limits", "filled_exposure_untouched (S7-A19)")


#: The SPEC.md §9.2 table, in evaluation order.  The first row whose ``from_states``, ``event``
#: and ``guard`` all match is the one that fires — so more specific rows (final TP, trail-out)
#: precede their general counterparts (TP n, stop-out).
TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        "T01", (PositionState.DRAFT,), EventKind.PLAN_PUBLISHED, PositionState.ARMED,
        "CF-16", "Plan published -> place resting limits or register the confirmation watcher",
        action=_a_arm,
    ),
    # --- ARMED, no exposure -----------------------------------------------------------------
    Transition(
        "T02", (PositionState.ARMED,), EventKind.BAR_CLOSED, PositionState.EXPIRED,
        "CF-15", "expires_at_index reached (pending_sr_expiry_bars / msb_retest_timeout_bars)",
        guard=_g_expired,
    ),
    Transition(
        "T03", (PositionState.ARMED,), EventKind.BAR_CLOSED, None,
        "CF-16", "Armed and waiting — a bar close on its own changes nothing",
        action=lambda ctx, ev: ("waiting",),
    ),
    Transition(
        "T04", (PositionState.ARMED,), EventKind.RUNG_FILLED, PositionState.PARTIAL,
        "CF-18", "Rung price touched, rungs still resting -> PARTIAL",
        guard=lambda ctx, ev: _g_rungs_remain_after(ctx, ev), action=_a_fill_rung,
    ),
    Transition(
        "T05", (PositionState.ARMED,), EventKind.RUNG_FILLED, PositionState.OPEN,
        "CF-18", "Only rung filled -> OPEN (all armed rungs filled)",
        guard=lambda ctx, ev: not _g_rungs_remain_after(ctx, ev), action=_a_fill_rung,
    ),
    Transition(
        "T06", (PositionState.ARMED,), EventKind.CONFIRMATION_COMPLETED, PositionState.PARTIAL,
        "CF-15", "Flip / SFP / MSB-retest confirmation completes, rungs remain -> PARTIAL",
        guard=lambda ctx, ev: _g_rungs_remain_after(ctx, ev), action=_a_fill_rung,
    ),
    Transition(
        "T07", (PositionState.ARMED,), EventKind.CONFIRMATION_COMPLETED, PositionState.OPEN,
        "CF-22", "Confirmation completes, single entry -> OPEN (enter at the confirming close)",
        guard=lambda ctx, ev: not _g_rungs_remain_after(ctx, ev), action=_a_fill_rung,
    ),
    Transition(
        "T08", (PositionState.ARMED,), EventKind.TREND_FLIPPED, PositionState.CANCELLED,
        "S7-R17", "Trend flips against the setup on structure_tf -> cancel unfilled limits only",
        action=_a_cancel_unfilled,
    ),
    Transition(
        "T09", (PositionState.ARMED,), EventKind.ZONE_INVALIDATED, PositionState.CANCELLED,
        "CF-08", "Anchoring zone reaches zone_fill_invalidation_pct -> dead (S5-R29 may re-arm)",
        action=_a_cancel_unfilled,
    ),
    Transition(
        "T10", (PositionState.ARMED,), EventKind.BLACKOUT_STARTED, PositionState.CANCELLED,
        "CF-39", "Event/weekend blackout begins and vehicle = leverage -> cancel; spot survives",
        guard=_g_leverage, action=_a_cancel_unfilled,
    ),
    # --- PARTIAL: further fills -------------------------------------------------------------
    Transition(
        "T11", (PositionState.PARTIAL,), EventKind.RUNG_FILLED, PositionState.OPEN,
        "S8-R20", "Remaining rung fills -> OPEN; recompute average, re-map TP1 to entry 1",
        guard=lambda ctx, ev: not _g_rungs_remain_after(ctx, ev), action=_a_fill_rung,
    ),
    Transition(
        "T12", (PositionState.PARTIAL,), EventKind.RUNG_FILLED, None,
        "S8-R20", "A rung fills but the ladder is not done -> stay PARTIAL, same actions",
        guard=lambda ctx, ev: _g_rungs_remain_after(ctx, ev), action=_a_fill_rung,
    ),
    Transition(
        "T13", (PositionState.PARTIAL, PositionState.OPEN),
        EventKind.AVERAGE_UP_OPPORTUNITY, PositionState.PARTIAL,
        "CF-19", "Price never reaches the DCA and average_up_enabled -> add at the next SR point",
        guard=_g_average_up, action=_a_average_up,
    ),
    Transition(
        "T14", (PositionState.PARTIAL,), EventKind.LEVEL_LOST, PositionState.CLOSED,
        "S2-R31", "Support under the ladder is lost -> stop adding and cut (structural_stale)",
        guard=_g_structural_cut, action=_mk_close(CloseReason.STRUCTURAL_STALE),
    ),
    # --- take-profits (CF-28, CF-29) --------------------------------------------------------
    Transition(
        "T15", _LIVE, EventKind.TP_TOUCHED, PositionState.CLOSED,
        "CF-28", "Final TP hit -> CLOSED(tp_final); residual is trailed out, never left open",
        guard=_g_final_tp, action=_a_final_tp,
    ),
    Transition(
        "T16", (PositionState.OPEN, PositionState.PARTIAL),
        EventKind.TP_TOUCHED, PositionState.MANAGING,
        "CF-29", "TP1 hit -> close tp_split[0]; stop to break-even at the AVERAGE entry",
        guard=_g_tp1_not_final, action=_a_tp,
    ),
    Transition(
        "T17", (PositionState.MANAGING,), EventKind.TP_TOUCHED, PositionState.MANAGING,
        "CF-29", "TP2 hit -> stop to TP1's price; TPn (n>=3) -> stop to TP(n-1)'s price",
        guard=_g_tp_n_not_final, action=_a_tp,
    ),
    # --- exits ------------------------------------------------------------------------------
    Transition(
        "T18", (PositionState.MANAGING,), EventKind.STOP_TOUCHED, PositionState.CLOSED,
        "CF-29", "Trailed stop hit after a TP -> CLOSED(trail_out): a normal, accepted outcome",
        guard=_g_trailed_out, action=_mk_close(CloseReason.TRAIL_OUT),
    ),
    Transition(
        "T19", _LIVE, EventKind.STOP_TOUCHED, PositionState.CLOSED,
        "CF-44", "Stop hit -> CLOSED(stop); increment the daily loss counter per loss_definition",
        action=_a_stop_out,
    ),
    Transition(
        "T20", _LIVE, EventKind.LEVEL_LOST, PositionState.CLOSED,
        "CF-30", "The level that justified the trade is lost -> immediate market exit",
        guard=_g_structural_cut, action=_mk_close(CloseReason.STRUCTURAL_STALE),
    ),
    Transition(
        "T21", (PositionState.OPEN, PositionState.PARTIAL),
        EventKind.MSB_AGAINST, PositionState.CLOSED,
        "CF-22", "MSB against the position on structure_tf -> CLOSED(msb_exit)",
        guard=_g_cut_applies, action=_mk_close(CloseReason.MSB_EXIT),
    ),
    Transition(
        "T22", (PositionState.OPEN, PositionState.MANAGING),
        EventKind.BAR_CLOSED, PositionState.CLOSED,
        "CF-30", "P17 stale condition and stale_exit_enabled -> CLOSED(time_stale). Off by default",
        guard=_g_stale, action=_mk_close(CloseReason.TIME_STALE),
    ),
    Transition(
        "T23", (PositionState.OPEN, PositionState.PARTIAL, PositionState.MANAGING),
        EventKind.SPOT_FLIP_CONFIRMED, PositionState.CLOSED,
        "CF-05", "Spot: daily close beyond the level + CF-15 flip -> CLOSED(spot_flip). Wicks "
                 "do not count",
        guard=_g_spot, action=_mk_close(CloseReason.SPOT_FLIP),
    ),
    Transition(
        "T24", _LIVE, EventKind.MACRO_MSB_TWO_STEP, PositionState.CLOSED,
        "CF-43", "long_term: HTF close below the last higher low, then a lower high -> msb_exit",
        guard=_g_long_term, action=_mk_close(CloseReason.MSB_EXIT),
    ),
    # --- §9.3 partial-profit rows (state unchanged) -----------------------------------------
    Transition(
        "T25", _LIVE, EventKind.HTF_DOUBLE_TOP, None,
        "S7-R35", "HTF double top after a large run -> partial profit, stop to break-even",
        action=_a_partial_and_be,
    ),
    Transition(
        "T26", _LIVE, EventKind.REGIME_TRIM_SIGNAL, None,
        "S3-R32", "Coin at resistance and USDT.D/BTC.D at support -> trim, or stop to break-even",
        action=_a_partial_and_be,
    ),
    Transition(
        "T27", _LIVE, EventKind.BAR_CLOSED, None,
        "CF-30", "Bar closed with no exit condition -> stay, increment bars_in_trade",
        action=_a_bar,
    ),
    # --- re-entry (CF-21) --------------------------------------------------------------------
    Transition(
        "T28", (PositionState.CLOSED,), EventKind.REENTRY_TRIGGER, PositionState.DRAFT,
        "CF-21", "Re-entry trigger fires -> a NEW draft; the touch counter keeps incrementing so "
                 "touch_size_decay shrinks each attempt",
        action=lambda ctx, ev: ("new_draft_required (CF-21, CF-07 decay continues); "
                                "admission is reentry_allowed(), checked by the caller",),
    ),
)


def _g_rungs_remain_after(ctx: TradeContext, ev: Event) -> bool:
    """Will a rung still be resting *after* this fill is applied?

    Guards run **before** the action, so the count has to look one fill ahead — otherwise a
    single-rung plan would land in ``PARTIAL`` and never leave it.
    """
    idx = ev.rung_index if ev.rung_index is not None else 0
    remaining = [r for r in ctx.plan.entries if not r.filled and r.index != idx]
    return bool(remaining)


# --------------------------------------------------------------------------- CF-21 re-entry


@dataclass(frozen=True, slots=True)
class ReentryState:
    """Per-level re-entry bookkeeping (CF-21).  Passed in; this module stores nothing."""

    level_id: str = ""
    attempts: int = 0
    last_attempt_index: int | None = None
    first_attempt_index: int | None = None


@dataclass(frozen=True, slots=True)
class ReentryVerdict:
    allowed: bool
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ("CF-21", "CF-07")


def reentry_allowed(
    config: Config, state: ReentryState, bar_index: int, *, trigger: str = "sfp"
) -> ReentryVerdict:
    """**CF-21 / §9.4** — may this level be re-taken?

    Triggers (any of): an SFP prints at the level (S2-R13, S5-R38); a candle **closes back
    beyond** the lost level (S6-R24, S3-R22); a pre-armed deeper conditional fires
    (``reentry_stacked_conditionals_enabled``, TBOT1-R26).  ``reentry_trigger`` selects which are
    accepted; the default ``"sfp_or_close_reclaim"`` takes the first two.

    Constraints — all three numbers are **OURS** (S8-A20, S4-A13): at most
    ``reentry_max_attempts_per_level`` (2) attempts per level per ``reentry_window_bars`` (100),
    with a ``reentry_cooldown_bars`` (3) gap.  The level's touch counter keeps incrementing, so
    ``touch_size_decay`` shrinks each successive attempt (CF-07).

    Zone-level re-takes are governed by CF-08 (50 % fill), **not** by this rule.
    """
    reasons: list[str] = []
    mode = config.reentry_trigger
    accepted = {"sfp", "close_reclaim"} if mode == "sfp_or_close_reclaim" else {mode}
    if config.reentry_stacked_conditionals_enabled:
        accepted.add("stacked_conditional")
    if trigger not in accepted:
        reasons.append(f"reentry_trigger_not_accepted:{trigger} (reentry_trigger={mode})")

    if state.attempts >= int(config.reentry_max_attempts_per_level):
        reasons.append(
            f"reentry_max_attempts_per_level_reached "
            f"({state.attempts}/{config.reentry_max_attempts_per_level})"
        )
    if state.last_attempt_index is not None:
        gap = bar_index - state.last_attempt_index
        if gap < int(config.reentry_cooldown_bars):
            reasons.append(
                f"reentry_cooldown_bars_not_elapsed ({gap}/{config.reentry_cooldown_bars})"
            )
    if state.first_attempt_index is not None:
        span = bar_index - state.first_attempt_index
        if span > int(config.reentry_window_bars):
            reasons.append(
                f"reentry_window_bars_elapsed ({span}/{config.reentry_window_bars})"
            )
    return ReentryVerdict(not reasons, tuple(reasons))


# --------------------------------------------------------------------------- the machine


class TradeManager:
    """Drives one position through the SPEC.md §9 table.

    Deterministic and side-effect free beyond the position it owns: same events in, same log out.
    ``handle`` returns the :class:`TransitionLog` it applied, or ``None`` when no row matched —
    an unmatched event is **not** an error (a TP touch on an ``ARMED`` plan is simply noise), it
    is recorded in :attr:`unmatched` so a backtest can assert on the ones that should not fire.
    """

    __slots__ = ("ctx", "log", "unmatched")

    def __init__(
        self,
        config: Config,
        plan: TradePlan,
        position: Position | None = None,
        *,
        account: Account = Account.LEVERAGE_SWING,
        loss_budget_usd: Decimal | float = ZERO,
    ) -> None:
        pos = position or Position(
            id=f"{plan.id}:pos",
            plan_id=plan.id,
            account=account,
            state=PositionState.DRAFT,
            current_stop=dec(plan.stop_price),
        )
        self.ctx = TradeContext(
            config=config,
            plan=plan,
            position=pos,
            account=account,
            loss_budget_usd=dec(loss_budget_usd),
        )
        self.log: list[TransitionLog] = []
        self.unmatched: list[Event] = []

    # -- accessors ---------------------------------------------------------------------------
    @property
    def state(self) -> PositionState:
        return self.ctx.position.state

    @property
    def position(self) -> Position:
        return self.ctx.position

    @property
    def plan(self) -> TradePlan:
        return self.ctx.plan

    def rule_ids(self) -> tuple[str, ...]:
        """Every rule ID that has moved this position, in order — the plan's audit trail."""
        return tuple(entry.rule_id for entry in self.log)

    # -- driving -----------------------------------------------------------------------------
    def handle(self, event: Event) -> TransitionLog | None:
        """Apply the first matching row of :data:`TRANSITIONS`.  ``None`` = nothing fired."""
        state = self.ctx.position.state
        for t in TRANSITIONS:
            if not t.matches(state, event, self.ctx):
                continue
            actions = t.action(self.ctx, event)
            to = t.to if t.to is not None else state
            self.ctx.position.state = to
            record = TransitionLog(
                bar_index=event.bar_index,
                transition_id=t.id,
                rule_id=t.rule_id,
                event=event.kind,
                from_state=state,
                to_state=to,
                actions=actions,
                detail=t.description,
            )
            self.log.append(record)
            return record
        self.unmatched.append(event)
        return None

    def drive(self, events: Sequence[Event]) -> list[TransitionLog]:
        """Feed a sequence of events; returns the transitions that actually fired."""
        out: list[TransitionLog] = []
        for ev in events:
            rec = self.handle(ev)
            if rec is not None:
                out.append(rec)
        return out
