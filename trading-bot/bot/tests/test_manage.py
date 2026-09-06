"""Contract tests for :mod:`tbot.manage` (SPEC.md §9, the trade-management state machine).

Two things matter most here and both are covered exhaustively:

* **every transition in the §9.2 table fires** when its state, event and guard line up, and lands
  in the state the table says, carrying the rule ID the table says;
* **the transitions that should NOT fire do not** — a TP touch on an armed plan, a trend flip
  after a fill, a level-loss cut on the ``long_term`` book (CF-43), an average-up while
  ``average_up_enabled`` is false, a time-stale exit while ``stale_exit_enabled`` is false.

Plans are assembled by hand so nothing here depends on the detectors or on ``build_plan``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import tbot.manage as M
from tbot.config import Config
from tbot.models import (
    Account,
    CloseReason,
    Direction,
    EntryRung,
    Position,
    PositionState,
    TakeProfit,
    Timeframe,
    TradeClass,
    TradePlan,
    Vehicle,
    dec,
)
from tbot.risk import money_close


# --------------------------------------------------------------------------- helpers

def make_plan(
    *,
    direction: Direction = Direction.LONG,
    entries=((100.0, 0.3), (90.0, 0.7)),
    tps=((120.0, 0.4), (140.0, 0.3), (160.0, 0.3)),
    stop: float = 85.0,
    vehicle: Vehicle = Vehicle.LEVERAGE,
    qty: float = 10.0,
    expires_at_index: int | None = None,
) -> TradePlan:
    rungs = [
        EntryRung(index=i, price=dec(p), size_fraction=dec(f),
                  kind="entry" if i == 0 else "dca", level_id=f"L{i}")
        for i, (p, f) in enumerate(entries)
    ]
    tp_objs = [
        TakeProfit(index=i, price=dec(p), size_fraction=dec(f), level_id=f"T{i}")
        for i, (p, f) in enumerate(tps)
    ]
    planned = sum((dec(p) * dec(f) for p, f in entries), Decimal(0))
    return TradePlan(
        id="S1:plan", setup_id="S1", symbol="T", direction=direction,
        trade_class=TradeClass.SWING, vehicle=vehicle, leverage=dec(2),
        entries=rungs, stop_price=dec(stop), take_profits=tp_objs,
        qty_total=dec(qty), notional_usd=dec(qty) * planned, risk_budget_pct=dec(4),
        average_entry=dec(0), planned_average_entry=planned, rr_to_tp1=dec(3),
        expected_move_pct=dec(20), invalidation_level_id="L0",
        expires_at_index=expires_at_index,
    )


def manager(cfg: Config, plan: TradePlan | None = None, **kw) -> M.TradeManager:
    return M.TradeManager(cfg, plan or make_plan(), **kw)


def arm(mgr: M.TradeManager, bar: int = 0) -> None:
    assert mgr.handle(M.Event(M.EventKind.PLAN_PUBLISHED, bar)) is not None


def fill(mgr: M.TradeManager, rung: int, bar: int, price: float | None = None):
    return mgr.handle(
        M.Event(M.EventKind.RUNG_FILLED, bar, rung_index=rung,
                fill_price=None if price is None else dec(price))
    )


def tp(mgr: M.TradeManager, index: int, bar: int, price: float | None = None):
    return mgr.handle(
        M.Event(M.EventKind.TP_TOUCHED, bar, tp_index=index,
                price=None if price is None else dec(price))
    )


@pytest.fixture()
def cfg() -> Config:
    return Config.load()


# ======================================================================= the table itself


def test_transition_ids_are_unique_and_every_row_names_a_rule() -> None:
    ids = [t.id for t in M.TRANSITIONS]
    assert len(ids) == len(set(ids))
    for t in M.TRANSITIONS:
        assert t.rule_id and t.description
        assert t.from_states


def test_every_applied_transition_is_logged_with_its_rule_id(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 3, 120.0)
    assert len(mgr.log) == 4
    for rec in mgr.log:
        assert rec.rule_id
        assert rec.transition_id
        assert rec.actions
    assert mgr.rule_ids() == ("CF-16", "CF-18", "S8-R20", "CF-29")


# ======================================================================= DRAFT / ARMED


def test_draft_to_armed_places_the_resting_limits(cfg: Config) -> None:
    mgr = manager(cfg)
    rec = mgr.handle(M.Event(M.EventKind.PLAN_PUBLISHED, 0))
    assert rec is not None and rec.transition_id == "T01" and rec.rule_id == "CF-16"
    assert mgr.state is PositionState.ARMED
    assert mgr.position.current_stop == dec(85.0)


def test_armed_expires_at_expires_at_index(cfg: Config) -> None:
    mgr = manager(cfg, make_plan(expires_at_index=12))
    arm(mgr)
    assert mgr.handle(M.Event(M.EventKind.BAR_CLOSED, 11)).transition_id == "T03"
    assert mgr.state is PositionState.ARMED
    rec = mgr.handle(M.Event(M.EventKind.BAR_CLOSED, 12))
    assert rec.transition_id == "T02" and rec.rule_id == "CF-15"
    assert mgr.state is PositionState.EXPIRED


def test_armed_first_fill_goes_to_partial_then_open(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    rec = fill(mgr, 0, 1)
    assert rec.transition_id == "T04" and mgr.state is PositionState.PARTIAL
    assert mgr.position.average_entry == dec(100)
    assert money_close(mgr.position.qty_open, dec(10) * dec("0.3"))
    rec = fill(mgr, 1, 2)
    assert rec.transition_id == "T11" and mgr.state is PositionState.OPEN
    assert money_close(mgr.position.qty_open, dec(10))


def test_a_single_rung_plan_goes_straight_to_open(cfg: Config) -> None:
    mgr = manager(cfg, make_plan(entries=((100.0, 1.0),)))
    arm(mgr)
    rec = fill(mgr, 0, 1)
    assert rec.transition_id == "T05" and mgr.state is PositionState.OPEN


def test_confirmation_entry_lands_in_open_for_a_single_rung(cfg: Config) -> None:
    mgr = manager(cfg, make_plan(entries=((100.0, 1.0),)))
    arm(mgr)
    rec = mgr.handle(
        M.Event(M.EventKind.CONFIRMATION_COMPLETED, 4, rung_index=0, fill_price=dec("100.4"))
    )
    assert rec.transition_id == "T07" and rec.rule_id == "CF-22"
    assert mgr.state is PositionState.OPEN
    assert mgr.position.average_entry == dec("100.4")


def test_trend_flip_cancels_unfilled_limits_only(cfg: Config) -> None:
    """S7-R17 / S7-A19 — an already-filled position is **not** closed by this rule."""
    mgr = manager(cfg)
    arm(mgr)
    rec = mgr.handle(M.Event(M.EventKind.TREND_FLIPPED, 5))
    assert rec.transition_id == "T08" and mgr.state is PositionState.CANCELLED

    other = manager(cfg)
    arm(other)
    fill(other, 0, 1)
    assert other.handle(M.Event(M.EventKind.TREND_FLIPPED, 5)) is None   # must NOT fire
    assert other.state is PositionState.PARTIAL


def test_dead_zone_cancels_an_armed_plan(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    rec = mgr.handle(M.Event(M.EventKind.ZONE_INVALIDATED, 6))
    assert rec.transition_id == "T09" and rec.rule_id == "CF-08"
    assert mgr.state is PositionState.CANCELLED


def test_blackout_cancels_leverage_but_spot_survives(cfg: Config) -> None:
    """CF-39 — event/weekend blackout blocks leverage; spot plans survive."""
    lev = manager(cfg)
    arm(lev)
    rec = lev.handle(M.Event(M.EventKind.BLACKOUT_STARTED, 7))
    assert rec.transition_id == "T10" and lev.state is PositionState.CANCELLED

    spot = manager(cfg, make_plan(vehicle=Vehicle.SPOT))
    arm(spot)
    assert spot.handle(M.Event(M.EventKind.BLACKOUT_STARTED, 7)) is None   # must NOT fire
    assert spot.state is PositionState.ARMED


# ======================================================================= fills and the ladder


def test_dca_fill_remaps_tp1_to_the_original_entry(cfg: Config) -> None:
    """S8-R20 / §9.3 — the original entry price is now an SR point."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    assert mgr.plan.take_profits[0].price == dec(120.0)
    rec = fill(mgr, 1, 2)
    assert rec.rule_id == "S8-R20"
    assert mgr.plan.take_profits[0].price == dec(100.0)         # rung 1's price
    assert mgr.plan.take_profits[1].price == dec(140.0)         # untouched, still structural
    assert any("tp1_remapped" in a for a in rec.actions)


def test_tp1_is_remapped_only_once(cfg: Config) -> None:
    mgr = manager(cfg, make_plan(entries=((100.0, 0.2), (95.0, 0.3), (90.0, 0.5))))
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    assert mgr.plan.take_profits[0].price == dec(100.0)
    fill(mgr, 2, 3)
    assert mgr.plan.take_profits[0].price == dec(100.0)


def test_a_dca_fill_never_moves_the_stop(cfg: Config) -> None:
    """§9.3 — the stop is unchanged; the average moves, so the budget is re-verified instead."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    assert mgr.position.current_stop == dec(85.0) == mgr.plan.stop_price
    assert mgr.position.average_entry == dec(100) * dec("0.3") + dec(90) * dec("0.7")


def test_a_dca_fill_closes_the_excess_quantity_rather_than_widening_the_stop(cfg: Config) -> None:
    """S6-R11 / S6-R12 — if the new average breaches the budget, cut size, never the stop."""
    plan = make_plan()
    mgr = manager(cfg, plan, loss_budget_usd=dec(50))
    arm(mgr)
    fill(mgr, 0, 1)
    rec = fill(mgr, 1, 2)
    assert any("closed_excess_qty" in a for a in rec.actions)
    avg = dec(mgr.position.average_entry)
    assert money_close(dec(mgr.position.qty_open) * abs(avg - dec(85)), dec(50))
    assert mgr.plan.stop_price == dec(85.0)


# ======================================================================= trailing (CF-29)


def test_tp1_moves_the_stop_to_break_even_at_the_average_entry(cfg: Config) -> None:
    """CF-29 + CF-18 — break-even is the **average** entry, never entry 1."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    avg = dec(mgr.position.average_entry)
    assert avg != dec(100)
    rec = tp(mgr, 0, 5, 120.0)
    assert rec.transition_id == "T16" and rec.rule_id == "CF-29"
    assert mgr.state is PositionState.MANAGING
    assert mgr.position.current_stop == avg
    assert mgr.position.stop_reason == "break_even"
    assert money_close(mgr.position.qty_open, dec(10) * dec("0.6"))


def test_tp2_moves_the_stop_to_tp1_price(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5, 120.0)
    rec = tp(mgr, 1, 6, 140.0)
    assert rec.transition_id == "T17"
    assert mgr.position.current_stop == mgr.plan.take_profits[0].price
    assert mgr.position.stop_reason == "tp1"


def test_tp3_moves_the_stop_to_the_previous_tp_and_closes_the_trade(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5, 120.0)
    tp(mgr, 1, 6, 140.0)
    rec = tp(mgr, 2, 7, 160.0)
    assert rec.transition_id == "T15" and rec.rule_id == "CF-28"
    assert mgr.state is PositionState.CLOSED
    assert mgr.position.close_reason is CloseReason.TP_FINAL
    assert mgr.position.qty_open == dec(0)
    assert mgr.position.current_stop == dec(140.0)     # trailed to TP2 on the way out


def test_a_four_tp_plan_trails_to_tp_n_minus_one(cfg: Config) -> None:
    plan = make_plan(tps=((110.0, 0.4), (120.0, 0.25), (130.0, 0.2), (140.0, 0.15)))
    mgr = manager(cfg, plan)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5)
    tp(mgr, 1, 6)
    rec = tp(mgr, 2, 7)
    assert rec.transition_id == "T17"
    assert mgr.position.current_stop == dec(120.0)
    assert mgr.position.stop_reason == "tp_n_minus_1"


def test_trail_on_tp1_none_leaves_the_stop_alone(cfg: Config) -> None:
    off = cfg.with_overrides(trail_on_tp1="none")
    mgr = manager(off)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5)
    assert mgr.position.current_stop == dec(85.0)
    assert mgr.position.stop_reason == "initial"


def test_trail_on_tp2_break_even_alternative(cfg: Config) -> None:
    """S6-R21's looser restatement, kept as config and discarded as the default (CF-29)."""
    alt = cfg.with_overrides(trail_on_tp2="break_even")
    mgr = manager(alt)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5)
    tp(mgr, 1, 6)
    assert mgr.position.current_stop == dec(mgr.position.average_entry)


def test_break_even_reference_first_entry_alternative(cfg: Config) -> None:
    alt = cfg.with_overrides(break_even_reference="first_entry")
    mgr = manager(alt)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5)
    assert mgr.position.current_stop == dec(100.0)


def test_a_trailed_stop_never_moves_backwards(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5)
    be = mgr.position.current_stop
    rec = mgr.handle(M.Event(M.EventKind.REGIME_TRIM_SIGNAL, 6))
    assert rec.transition_id == "T26"
    assert mgr.position.current_stop == be


def test_htf_double_top_takes_partial_and_moves_to_break_even(cfg: Config) -> None:
    """S7-R35 / S8-R25 — regardless of expected resolution."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    rec = mgr.handle(M.Event(M.EventKind.HTF_DOUBLE_TOP, 4))
    assert rec.transition_id == "T25" and rec.rule_id == "S7-R35"
    assert mgr.state is PositionState.OPEN
    assert mgr.position.current_stop == dec(mgr.position.average_entry)


# ======================================================================= exits


def test_stop_before_any_tp_closes_with_reason_stop(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    rec = mgr.handle(M.Event(M.EventKind.STOP_TOUCHED, 4, price=dec(85)))
    assert rec.transition_id == "T19" and rec.rule_id == "CF-44"
    assert mgr.position.close_reason is CloseReason.STOP
    assert any("daily_loss_counter_candidate" in a for a in rec.actions)
    assert mgr.position.r_multiple is not None and mgr.position.r_multiple < 0


def test_stop_after_a_tp_is_a_trail_out_not_a_loss(cfg: Config) -> None:
    """CF-29 / S5 ``[00:40:00]`` — a normal, accepted outcome."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    tp(mgr, 0, 5)
    rec = mgr.handle(M.Event(M.EventKind.STOP_TOUCHED, 6, price=dec(93)))
    assert rec.transition_id == "T18" and mgr.position.close_reason is CloseReason.TRAIL_OUT


def test_partial_position_cut_when_the_level_under_the_ladder_is_lost(cfg: Config) -> None:
    """S2-R31 — stop adding, cut.  Never keep DCAing a level that is gone."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    rec = mgr.handle(M.Event(M.EventKind.LEVEL_LOST, 4, price=dec(88)))
    assert rec.transition_id == "T14" and rec.rule_id == "S2-R31"
    assert mgr.position.close_reason is CloseReason.STRUCTURAL_STALE


def test_open_position_cut_when_the_justifying_level_is_lost(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    rec = mgr.handle(M.Event(M.EventKind.LEVEL_LOST, 4, price=dec(88)))
    assert rec.transition_id == "T20" and rec.rule_id == "CF-30"
    assert mgr.position.close_reason is CloseReason.STRUCTURAL_STALE


def test_the_long_term_book_is_never_cut_on_a_level_loss(cfg: Config) -> None:
    """CF-43 / S2-C6 — "if you are an investor, this does not apply to you"."""
    mgr = manager(cfg, account=Account.LONG_TERM)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    assert mgr.handle(M.Event(M.EventKind.LEVEL_LOST, 4)) is None        # must NOT fire
    assert mgr.state is PositionState.OPEN
    assert mgr.handle(M.Event(M.EventKind.MSB_AGAINST, 5)) is None       # must NOT fire either
    rec = mgr.handle(M.Event(M.EventKind.MACRO_MSB_TWO_STEP, 6, price=dec(80)))
    assert rec.transition_id == "T24" and rec.rule_id == "CF-43"
    assert mgr.position.close_reason is CloseReason.MSB_EXIT


def test_structural_stale_exit_can_be_switched_off(cfg: Config) -> None:
    off = cfg.with_overrides(structural_stale_exit_enabled=False)
    mgr = manager(off)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    assert mgr.handle(M.Event(M.EventKind.LEVEL_LOST, 4)) is None
    assert mgr.state is PositionState.OPEN


def test_msb_against_closes_an_open_leverage_position(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    rec = mgr.handle(M.Event(M.EventKind.MSB_AGAINST, 4, price=dec(92)))
    assert rec.transition_id == "T21" and rec.rule_id == "CF-22"
    assert mgr.position.close_reason is CloseReason.MSB_EXIT


def test_spot_flip_closes_only_a_spot_plan(cfg: Config) -> None:
    """CF-05 / TBOT1-R18 — a daily close beyond the level plus the flip; wicks do not count."""
    spot = manager(cfg, make_plan(vehicle=Vehicle.SPOT))
    arm(spot)
    fill(spot, 0, 1)
    fill(spot, 1, 2)
    rec = spot.handle(M.Event(M.EventKind.SPOT_FLIP_CONFIRMED, 4, price=dec(88)))
    assert rec.transition_id == "T23" and spot.position.close_reason is CloseReason.SPOT_FLIP

    lev = manager(cfg)
    arm(lev)
    fill(lev, 0, 1)
    fill(lev, 1, 2)
    assert lev.handle(M.Event(M.EventKind.SPOT_FLIP_CONFIRMED, 4)) is None   # must NOT fire


def test_time_stale_exit_is_off_by_default(cfg: Config) -> None:
    """CF-30 / P17 — no number for it exists anywhere in the corpus."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    mgr.position.bars_in_trade = 50
    mgr.position.mae_atr = dec(3)
    mgr.position.mfe_atr = dec(0)
    rec = mgr.handle(M.Event(M.EventKind.BAR_CLOSED, 9))
    assert rec.transition_id == "T27"                      # just a bar, not an exit
    assert mgr.state is PositionState.OPEN


def test_time_stale_exit_fires_when_enabled(cfg: Config) -> None:
    on = cfg.with_overrides(stale_exit_enabled=True)
    mgr = manager(on)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    mgr.position.bars_in_trade = 50
    mgr.position.mae_atr = dec(3)
    mgr.position.mfe_atr = dec(0)
    rec = mgr.handle(M.Event(M.EventKind.BAR_CLOSED, 9))
    assert rec.transition_id == "T22" and mgr.position.close_reason is CloseReason.TIME_STALE


def test_bar_closed_increments_bars_in_trade(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    for i in range(3):
        mgr.handle(M.Event(M.EventKind.BAR_CLOSED, 2 + i))
    assert mgr.position.bars_in_trade == 3


# ======================================================================= must NOT fire


def test_events_that_must_not_fire_are_recorded_as_unmatched(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    # No exposure yet: neither a TP nor a stop can touch anything.
    assert tp(mgr, 0, 3) is None
    assert mgr.handle(M.Event(M.EventKind.STOP_TOUCHED, 3)) is None
    assert mgr.handle(M.Event(M.EventKind.LEVEL_LOST, 3)) is None
    assert mgr.handle(M.Event(M.EventKind.MSB_AGAINST, 3)) is None
    assert mgr.state is PositionState.ARMED
    assert len(mgr.unmatched) == 4
    assert mgr.log == mgr.log[:1]      # only the arming transition ever fired


def test_a_closed_position_ignores_further_market_events(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.handle(M.Event(M.EventKind.STOP_TOUCHED, 4, price=dec(85)))
    assert mgr.state is PositionState.CLOSED
    assert tp(mgr, 0, 5) is None
    assert mgr.handle(M.Event(M.EventKind.BAR_CLOSED, 6)) is None
    assert mgr.state is PositionState.CLOSED


def test_average_up_is_disabled_by_default(cfg: Config) -> None:
    """CF-19 — appears once, with no trigger condition (S3-A10); a rule with no trigger cannot
    be a default."""
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.position.mfe_atr = dec(3)
    ev = M.Event(M.EventKind.AVERAGE_UP_OPPORTUNITY, 5, price=dec(103), detail="sr_point")
    assert mgr.handle(ev) is None
    assert mgr.state is PositionState.PARTIAL


def test_average_up_waits_for_the_favourable_excursion_trigger(cfg: Config) -> None:
    """§8.4 condition 2 — ``average_up_trigger_atr`` (2.0, **OUR number**); S3-A10 flags that the
    corpus gives no trigger at all."""
    on = cfg.with_overrides(average_up_enabled=True)
    mgr = manager(on, loss_budget_usd=dec(1000))
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.position.mfe_atr = dec("0.5")      # not yet 2.0 ATR in favour
    ev = M.Event(M.EventKind.AVERAGE_UP_OPPORTUNITY, 5, price=dec(103), detail="sr_point")
    assert mgr.handle(ev) is None


def test_average_up_fires_when_enabled_at_an_sr_point_inside_the_budget(cfg: Config) -> None:
    on = cfg.with_overrides(average_up_enabled=True)
    mgr = manager(on, loss_budget_usd=dec(1000))
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.position.mfe_atr = dec(3)          # §8.4 condition 2: moved average_up_trigger_atr away
    rec = mgr.handle(
        M.Event(M.EventKind.AVERAGE_UP_OPPORTUNITY, 5, price=dec(103), detail="sr_point")
    )
    assert rec is not None and rec.transition_id == "T13" and rec.rule_id == "CF-19"
    assert mgr.position.average_entry == dec(100) * dec("0.3") + dec(103) * dec("0.7")
    assert mgr.plan.stop_price == dec(85.0)


def test_average_up_refuses_a_price_that_is_not_an_sr_point(cfg: Config) -> None:
    """S3-R14 — only at an SR point, never into a zone interior or open air."""
    on = cfg.with_overrides(average_up_enabled=True)
    mgr = manager(on, loss_budget_usd=dec(1000))
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.position.mfe_atr = dec(3)
    ev = M.Event(M.EventKind.AVERAGE_UP_OPPORTUNITY, 5, price=dec(103), detail="open_air")
    assert mgr.handle(ev) is None


def test_average_up_refuses_to_breach_the_risk_budget(cfg: Config) -> None:
    """§8.4 condition 4 — the blended average must still fit the budget with the ORIGINAL stop."""
    on = cfg.with_overrides(average_up_enabled=True)
    mgr = manager(on, loss_budget_usd=dec(1))
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.position.mfe_atr = dec(3)
    ev = M.Event(M.EventKind.AVERAGE_UP_OPPORTUNITY, 5, price=dec(103), detail="sr_point")
    assert mgr.handle(ev) is None


# ======================================================================= re-entry (CF-21)


def test_reentry_is_allowed_on_an_sfp_and_capped_per_level(cfg: Config) -> None:
    fresh = M.ReentryState(level_id="L0")
    assert M.reentry_allowed(cfg, fresh, 100, trigger="sfp").allowed
    assert M.reentry_allowed(cfg, fresh, 100, trigger="close_reclaim").allowed

    used_up = M.ReentryState("L0", attempts=2, last_attempt_index=10, first_attempt_index=0)
    v = M.reentry_allowed(cfg, used_up, 100, trigger="sfp")
    assert not v.allowed
    assert any("max_attempts_per_level" in r for r in v.reasons)


def test_reentry_respects_the_cooldown_and_the_window(cfg: Config) -> None:
    cooling = M.ReentryState("L0", attempts=1, last_attempt_index=10, first_attempt_index=10)
    assert not M.reentry_allowed(cfg, cooling, 11, trigger="sfp").allowed
    assert M.reentry_allowed(cfg, cooling, 13, trigger="sfp").allowed

    stale = M.ReentryState("L0", attempts=1, last_attempt_index=10, first_attempt_index=0)
    v = M.reentry_allowed(cfg, stale, 500, trigger="sfp")
    assert not v.allowed
    assert any("window_bars_elapsed" in r for r in v.reasons)


def test_stacked_conditionals_are_a_switch(cfg: Config) -> None:
    """TBOT1-R26 — a pre-armed deeper conditional order is the third CF-21 trigger."""
    fresh = M.ReentryState("L0")
    assert M.reentry_allowed(cfg, fresh, 50, trigger="stacked_conditional").allowed
    off = cfg.with_overrides(reentry_stacked_conditionals_enabled=False)
    assert not M.reentry_allowed(off, fresh, 50, trigger="stacked_conditional").allowed


def test_a_closed_position_can_be_re_drafted(cfg: Config) -> None:
    mgr = manager(cfg)
    arm(mgr)
    fill(mgr, 0, 1)
    mgr.handle(M.Event(M.EventKind.STOP_TOUCHED, 4, price=dec(85)))
    rec = mgr.handle(M.Event(M.EventKind.REENTRY_TRIGGER, 8))
    assert rec.transition_id == "T28" and rec.rule_id == "CF-21"
    assert mgr.state is PositionState.DRAFT


# ======================================================================= shorts


def test_the_machine_works_the_same_way_short(cfg: Config) -> None:
    plan = make_plan(
        direction=Direction.SHORT, entries=((100.0, 0.3), (110.0, 0.7)),
        tps=((80.0, 0.4), (70.0, 0.3), (60.0, 0.3)), stop=115.0,
    )
    mgr = manager(cfg, plan)
    arm(mgr)
    fill(mgr, 0, 1)
    fill(mgr, 1, 2)
    assert mgr.plan.take_profits[0].price == dec(100.0)     # re-mapped down to entry 1
    tp(mgr, 0, 5)
    assert mgr.position.current_stop == dec(mgr.position.average_entry)
    assert mgr.position.current_stop < dec(115.0)           # a short's stop falls
