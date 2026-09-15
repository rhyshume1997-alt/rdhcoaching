"""Contract tests for :mod:`tbot.risk` (SPEC.md §10, the risk and portfolio layer).

The three that matter most:

* the **daily-loss halt** actually blocks a new trade after ``daily_loss_count_limit`` losses;
* the **win-streak prohibition** actually blocks a trade that asks for more risk than the
  baseline (``risk_ratchet_up_allowed = false``, S2-R24, marked hard);
* the CF-01 ladder and the CF-04 concurrency caps produce the numbers SPEC.md §10 says they do.

Everything here is pure: portfolio state is built by hand and no function mutates it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import tbot.plan as PL
import tbot.risk as R
from tbot.config import Config
from tbot.models import (
    Account,
    Conviction,
    PositionState,
    TradeClass,
    Vehicle,
    dec,
)

NOW = datetime(2024, 3, 14, 12, 0, tzinfo=timezone.utc)
EQUITY = dec(10_000)


# --------------------------------------------------------------------------- helpers

def slot(
    n: int = 0,
    *,
    vehicle: Vehicle = Vehicle.LEVERAGE,
    trade_class: TradeClass = TradeClass.SWING,
    account: Account = Account.LEVERAGE_SWING,
    state: PositionState = PositionState.OPEN,
    notional: float = 500.0,
    bucket: R.McapBucket = "large",
) -> R.OpenSlot:
    return R.OpenSlot(
        position_id=f"P{n}", account=account, vehicle=vehicle, trade_class=trade_class,
        state=state, notional_usd=dec(notional), symbol=f"C{n}", mcap_bucket=bucket,
    )


def closed(n: int, pnl: float, *, hours_ago: float = 1.0,
           account: Account = Account.LEVERAGE_SWING, stop_out: bool = True) -> R.ClosedTrade:
    return R.ClosedTrade(
        trade_id=f"T{n}", account=account, closed_at=NOW - timedelta(hours=hours_ago),
        pnl_usd=dec(pnl), was_stop_out=stop_out,
    )


def portfolio(**kw) -> R.PortfolioState:
    kw.setdefault("equity_usd", EQUITY)
    kw.setdefault("now", NOW)
    return R.PortfolioState(**kw)


@pytest.fixture()
def cfg() -> Config:
    return Config.load()


# ======================================================================= tolerance helpers


def test_money_close_is_the_only_equality_on_money() -> None:
    a = dec(1) / dec(3) * dec(3)
    assert R.money_close(a, dec(1))
    assert not R.money_close(dec("100.00"), dec("100.01"))
    assert R.money_ge(dec("100.00"), dec("100.00"))
    assert R.money_le(dec("99.99"), dec("100.00"))
    assert R.money_close(dec(0), dec(0))


# ======================================================================= CF-01 risk ladder


def test_risk_ladder_by_trade_class(cfg: Config) -> None:
    assert R.per_trade_risk_pct(cfg, trade_class=TradeClass.SWING) == dec(4.0)
    assert R.per_trade_risk_pct(cfg, trade_class=TradeClass.SCALP) == dec(2.5)
    assert R.per_trade_risk_pct(cfg, trade_class=TradeClass.PRICE_DISCOVERY) == dec(4.0)


def test_counter_trend_halves_the_swing_cap(cfg: Config) -> None:
    """CF-03 / §10.7 — 2.0 % against the swing 4.0 %; S3-C9's "the loss stays the same" is
    discarded, halving size halves risk."""
    ct = R.per_trade_risk_pct(cfg, trade_class=TradeClass.SWING, counter_trend=True)
    assert ct == dec(cfg.max_loss_pct_counter_trend) == dec(2.0)
    assert ct * dec(2) == dec(cfg.max_loss_pct_swing)
    assert R.per_trade_risk_pct(cfg, trade_class=TradeClass.COUNTER_TREND) == dec(2.0)


def test_low_conviction_caps_at_one_and_a_half_percent(cfg: Config) -> None:
    """S6-R26 — 1/3 size when price action is unclear."""
    assert R.per_trade_risk_pct(
        cfg, trade_class=TradeClass.SWING, conviction=Conviction.LOW
    ) == dec(1.5)
    # a low-conviction scalp takes the tighter of the two
    assert R.per_trade_risk_pct(
        cfg, trade_class=TradeClass.SCALP, conviction=Conviction.LOW
    ) == dec(1.5)


def test_high_conviction_escalation_is_off_by_default(cfg: Config) -> None:
    """TBOT1-R13 / CF-01 precedence rule 2 — 5-6 % is an escalation, never the default."""
    assert R.per_trade_risk_pct(
        cfg, trade_class=TradeClass.SWING, conviction=Conviction.HIGH
    ) == dec(4.0)
    on = cfg.with_overrides(high_conviction_loss_pct_enabled=True)
    assert R.per_trade_risk_pct(
        on, trade_class=TradeClass.SWING, conviction=Conviction.HIGH
    ) == dec(5.0)
    # swing only: a high-conviction scalp does not escalate
    assert R.per_trade_risk_pct(
        on, trade_class=TradeClass.SCALP, conviction=Conviction.HIGH
    ) == dec(2.5)


def test_the_swing_hard_cap_binds_everything(cfg: Config) -> None:
    """CF-01 — 5.0 % is a ceiling on every branch of the ladder.

    ``config.py`` already refuses ``max_loss_pct_swing > max_loss_pct_swing_hard_cap``, so the
    cap is pushed from the other side: a scalp cap above it is still clamped down.
    """
    loose = cfg.with_overrides(max_loss_pct_scalp=9.0)
    assert R.per_trade_risk_pct(loose, trade_class=TradeClass.SCALP) == dec(5.0)
    assert R.per_trade_risk_pct(loose, trade_class=TradeClass.SWING) == dec(4.0)


# ======================================================================= CF-07 decay, §10.8


def test_touch_decay_curve(cfg: Config) -> None:
    """**Q2** — the curve shifted one index right: the 3rd touch is full size, the 5th is cut.

    The old curve cut size at the 3rd touch.  It should not: the 3rd touch is one he calls *"a
    great area to go long"* (S7 ``[00:08:22]``) and *"strong support, third touch"* (S4
    ``[01:04:03]``), and the only touch index he ever attaches a reduction to is the **5th** —
    *"we've had one, two, three, four touches of this resistance. So I would go in with a smaller
    position only because it's going to be the fifth touch"* (S8 ``[00:54:14]``).  The shape
    remains **OURS** and is a sweep key.
    """
    assert [R.touch_decay(cfg, i) for i in (1, 2, 3, 4, 5)] == [
        dec(1.0), dec(1.0), dec(1.0), dec("0.66"), dec("0.5")
    ]
    assert R.touch_decay(cfg, 9) == dec("0.5")       # 5+ clamps
    with pytest.raises(ValueError):
        R.touch_decay(cfg, 0)


def test_multipliers_compose_multiplicatively(cfg: Config) -> None:
    """§10.8 — touch decay x counter-trend x BVOL.  Composition order is **[OUR CHOICE]**."""
    m = R.compose_size_multipliers(
        cfg, touch_index=4,
        extra=[cfg.counter_trend_size_multiplier, cfg.bvol_size_multiplier],
    )
    assert R.money_close(m, dec("0.66") * dec("0.5") * dec("0.5"))


# ======================================================================= CF-02 notional


def test_notional_ceilings(cfg: Config) -> None:
    """**Q8** — the leverage row is 100 % of equity, not 10 %.

    10 % is his *margin* figure (S7 ``[00:25:54]``) and was being enforced as a *notional*
    ceiling.  100 % is that margin at his stated default leverage (``margin_pct_leverage`` 10 % x
    ``default_leverage`` 10x).  Spot really is notional and is unchanged.
    """
    lev = R.notional_ceiling_usd(cfg, equity_usd=EQUITY, vehicle=Vehicle.LEVERAGE)
    assert lev == EQUITY * dec(100) / dec(100) == EQUITY
    assert R.margin_ceiling_usd(cfg, equity_usd=EQUITY) == EQUITY * dec(10) / dec(100)
    assert cfg.default_leverage == 10.0
    hi = R.notional_ceiling_usd(
        cfg, equity_usd=EQUITY, vehicle=Vehicle.SPOT, conviction=Conviction.HIGH
    )
    lo = R.notional_ceiling_usd(
        cfg, equity_usd=EQUITY, vehicle=Vehicle.SPOT, conviction=Conviction.LOW
    )
    assert hi == dec(1200) and lo == dec(600)


def test_spot_deployment_cap_is_portfolio_wide(cfg: Config) -> None:
    """CF-02 / S4-R31 / S8-R35 — ~60-70 % deployed, never more."""
    pf = portfolio(open_slots=tuple(
        slot(i, vehicle=Vehicle.SPOT, account=Account.SPOT_SHORT, notional=1300.0)
        for i in range(5)
    ))
    assert R.spot_deployment_gate(cfg, pf, add_notional_usd=dec(400)).allowed
    blocked = R.spot_deployment_gate(cfg, pf, add_notional_usd=dec(1000))
    assert not blocked.allowed
    assert any("max_total_spot_deployment_pct" in r for r in blocked.reasons)


def test_sizing_budget_narrows_the_spot_ceiling_to_the_remaining_deployment(cfg: Config) -> None:
    pf = portfolio(open_slots=tuple(
        slot(i, vehicle=Vehicle.SPOT, account=Account.SPOT_SHORT, notional=1380.0)
        for i in range(5)
    ))
    b = R.sizing_budget(cfg, pf, trade_class=TradeClass.SWING, vehicle=Vehicle.SPOT)
    assert b.notional_ceiling_usd == dec(7000) - dec(6900)
    assert b.loss_budget_usd == dec(400)


def test_sizing_budget_target_loss_includes_the_multiplier(cfg: Config) -> None:
    pf = portfolio()
    b = R.sizing_budget(
        cfg, pf, trade_class=TradeClass.SWING, vehicle=Vehicle.LEVERAGE, touch_index=5
    )
    # Q2 shifted the curve one index right: the 0.5 rung is now the 5th touch, not the 4th.
    assert b.size_multiplier == dec("0.5")
    assert R.money_close(b.target_loss_usd, dec(200))


# ======================================================================= CF-04 concurrency


def test_leverage_and_spot_are_counted_separately(cfg: Config) -> None:
    pf = portfolio(open_slots=(
        slot(1, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SWING),
        slot(2, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SWING),
    ))
    swing = R.concurrency_gate(
        cfg, pf, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SWING
    )
    assert not swing.allowed
    assert any("max_concurrent_leverage_swing" in r for r in swing.reasons)
    # the scalp bucket and the spot bucket are untouched by two swing positions
    assert R.concurrency_gate(
        cfg, pf, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SCALP
    ).allowed
    assert R.concurrency_gate(cfg, pf, vehicle=Vehicle.SPOT, trade_class=TradeClass.SWING).allowed


def test_the_global_leverage_cap_binds_across_buckets(cfg: Config) -> None:
    """S4-C8 — 2 per account and per exchange, so the true global cap is 4."""
    pf = portfolio(open_slots=(
        slot(1, trade_class=TradeClass.SWING), slot(2, trade_class=TradeClass.SWING),
        slot(3, trade_class=TradeClass.SCALP, account=Account.LEVERAGE_SCALP),
        slot(4, trade_class=TradeClass.SCALP, account=Account.LEVERAGE_SCALP),
    ))
    g = R.concurrency_gate(cfg, pf, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SCALP)
    assert not g.allowed
    assert any("global" in r for r in g.reasons)


def test_a_counter_trend_plan_consumes_a_scalp_slot(cfg: Config) -> None:
    """§10.7 / CF-03 — demoted to a scalp, so it does not eat a swing slot."""
    pf = portfolio(open_slots=(
        slot(1, trade_class=TradeClass.SCALP), slot(2, trade_class=TradeClass.SCALP),
    ))
    g = R.concurrency_gate(
        cfg, pf, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SWING, counter_trend=True
    )
    assert not g.allowed
    assert any("scalp" in r for r in g.reasons)


def test_spot_cap(cfg: Config) -> None:
    pf = portfolio(open_slots=tuple(
        slot(i, vehicle=Vehicle.SPOT, account=Account.SPOT_SHORT) for i in range(5)
    ))
    assert not R.concurrency_gate(
        cfg, pf, vehicle=Vehicle.SPOT, trade_class=TradeClass.SWING
    ).allowed


def test_only_live_positions_count(cfg: Config) -> None:
    """SPEC.md §9.1 — ``PARTIAL``/``OPEN``/``MANAGING`` only; armed and closed plans do not."""
    pf = portfolio(open_slots=(
        slot(1, state=PositionState.ARMED), slot(2, state=PositionState.CLOSED),
        slot(3, state=PositionState.CANCELLED), slot(4, state=PositionState.MANAGING),
    ))
    assert len(pf.live_slots()) == 1
    assert R.concurrency_gate(
        cfg, pf, vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SWING
    ).allowed


# ======================================================================= §10.4 daily halt


def test_two_losses_in_a_day_halt_new_entries(cfg: Config) -> None:
    """S2-R21 — two losing trades in one day ends the day."""
    one = portfolio(closed_trades=(closed(1, -100.0),))
    assert R.daily_loss_gate(cfg, one).allowed

    two = portfolio(closed_trades=(closed(1, -100.0), closed(2, -50.0, hours_ago=3)))
    g = R.daily_loss_gate(cfg, two)
    assert not g.allowed
    assert any("daily_loss_count_limit_reached (2/2)" in r for r in g.reasons)


def test_the_daily_halt_blocks_a_whole_trade(cfg: Config) -> None:
    pf = portfolio(closed_trades=(closed(1, -100.0), closed(2, -50.0, hours_ago=2)))
    d = R.approve_trade(
        cfg, pf, account=Account.LEVERAGE_SWING, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    assert not d.allowed
    assert any("daily_loss_count_limit_reached" in r for r in d.reasons)
    # the budget is still reported, so the CLI can say what was refused
    assert d.budget.risk_budget_pct == dec(4.0)


def test_yesterdays_losses_do_not_count(cfg: Config) -> None:
    """CF-45 / P16 — the day boundary is ``day_boundary_utc``."""
    pf = portfolio(closed_trades=(
        closed(1, -100.0, hours_ago=20), closed(2, -100.0, hours_ago=30),
    ))
    assert R.daily_loss_gate(cfg, pf).allowed        # only the 20h-ago one is inside today


def test_a_loss_is_any_trade_closed_below_average_entry_net_fees(cfg: Config) -> None:
    """CF-44 / S2-A23 — not only a stop-out."""
    scratched = closed(1, -5.0, stop_out=False)
    assert R.is_loss(cfg, scratched)
    strict = cfg.with_overrides(loss_definition="stop_out_only")
    assert not R.is_loss(strict, scratched)
    assert R.is_loss(strict, closed(2, -5.0, stop_out=True))


def test_the_halt_is_account_scoped(cfg: Config) -> None:
    pf = portfolio(closed_trades=(
        closed(1, -100.0, account=Account.LEVERAGE_SCALP),
        closed(2, -100.0, account=Account.LEVERAGE_SCALP),
    ))
    assert not R.daily_loss_gate(cfg, pf, account=Account.LEVERAGE_SCALP).allowed
    assert R.daily_loss_gate(cfg, pf, account=Account.LEVERAGE_SWING).allowed


# ======================================================================= S2-R24 ratchet


def test_the_win_streak_prohibition_blocks_a_trade(cfg: Config) -> None:
    """S2-R24, **hard** — never increase risk-per-trade after a winning streak."""
    pf = portfolio(
        closed_trades=(closed(1, 300.0), closed(2, 250.0, hours_ago=5),
                       closed(3, 400.0, hours_ago=9)),
        baseline_risk_pct={TradeClass.SWING.value: dec(2.0)},
    )
    assert R.win_streak(pf) == 3
    g = R.ratchet_gate(cfg, pf, requested_pct=dec(4.0), trade_class=TradeClass.SWING)
    assert not g.allowed
    assert any("risk_ratchet_up_forbidden" in r for r in g.reasons)
    assert any("win_streak=3" in r for r in g.reasons)

    d = R.approve_trade(
        cfg, pf, account=Account.LEVERAGE_SWING, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    assert not d.allowed
    assert any("risk_ratchet_up_forbidden" in r for r in d.reasons)


def test_de_risking_downward_is_always_permitted(cfg: Config) -> None:
    pf = portfolio(baseline_risk_pct={TradeClass.SWING.value: dec(4.0)})
    assert R.ratchet_gate(cfg, pf, requested_pct=dec(2.0), trade_class=TradeClass.SWING).allowed
    assert R.ratchet_gate(cfg, pf, requested_pct=dec(4.0), trade_class=TradeClass.SWING).allowed
    assert R.clamp_requested_risk_pct(
        cfg, pf, requested_pct=dec(9.0), trade_class=TradeClass.SWING
    ) == dec(4.0)
    assert R.clamp_requested_risk_pct(
        cfg, pf, requested_pct=dec(1.0), trade_class=TradeClass.SWING
    ) == dec(1.0)


def test_no_baseline_means_nothing_to_ratchet_up_from(cfg: Config) -> None:
    pf = portfolio(closed_trades=(closed(1, 300.0),))
    assert R.ratchet_gate(cfg, pf, requested_pct=dec(5.0), trade_class=TradeClass.SWING).allowed


def test_the_ratchet_can_be_unlocked_by_config(cfg: Config) -> None:
    on = cfg.with_overrides(risk_ratchet_up_allowed=True)
    pf = portfolio(baseline_risk_pct={TradeClass.SWING.value: dec(2.0)})
    assert R.ratchet_gate(on, pf, requested_pct=dec(4.0), trade_class=TradeClass.SWING).allowed


def test_a_loss_breaks_the_win_streak(cfg: Config) -> None:
    pf = portfolio(closed_trades=(
        closed(1, 300.0, hours_ago=1), closed(2, -50.0, hours_ago=2),
        closed(3, 400.0, hours_ago=3),
    ))
    assert R.win_streak(pf) == 1


# ======================================================================= CF-44 challenge


def test_the_challenge_goal_compounds(cfg: Config) -> None:
    """S2-R23 — each period's goal is the previous period's closing balance x goal %."""
    g1 = R.challenge_period_goal_usd(cfg, period_start_balance_usd=dec(1000))
    assert g1 == dec(80)
    g2 = R.next_period_goal_usd(cfg, period_closing_balance_usd=dec(1080))
    assert g2 == dec("86.4")
    assert g2 > g1


def test_stop_trading_once_the_period_goal_is_hit(cfg: Config) -> None:
    """S2-R22 — stop for the remainder of the period; S2 ``[01:29:52]`` — never chase next week."""
    pf = portfolio(period_start_balance_usd=dec(1000), period_realised_pnl_usd=dec(80))
    g = R.challenge_gate(cfg, pf)
    assert not g.allowed
    assert any("challenge_goal_reached" in r for r in g.reasons)

    short = portfolio(period_start_balance_usd=dec(1000), period_realised_pnl_usd=dec("79.99"))
    assert R.challenge_gate(cfg, short).allowed


def test_the_challenge_gate_blocks_a_whole_trade(cfg: Config) -> None:
    pf = portfolio(period_start_balance_usd=dec(1000), period_realised_pnl_usd=dec(500))
    d = R.approve_trade(
        cfg, pf, account=Account.CHALLENGE, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    assert not d.allowed
    # and the same portfolio on a non-challenge account is unaffected
    other = R.approve_trade(
        cfg, pf, account=Account.LEVERAGE_SWING, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    assert other.allowed


def test_stop_on_goal_is_switchable(cfg: Config) -> None:
    off = cfg.with_overrides(challenge_stop_on_goal=False)
    pf = portfolio(period_start_balance_usd=dec(1000), period_realised_pnl_usd=dec(500))
    assert R.challenge_gate(off, pf).allowed


def test_equity_restart_is_recorded_not_automated(cfg: Config) -> None:
    """S2-R26 — halve-the-account-and-restart is **[OUR CHOICE]** off."""
    pf = portfolio()
    assert R.equity_restart_target(cfg, pf) is None
    on = cfg.with_overrides(equity_restart_mode="halve_on_drawdown")
    assert R.equity_restart_target(on, pf) == EQUITY / dec(2)


# ======================================================================= §10.6 allocation


def test_allocation_targets_match_the_spec(cfg: Config) -> None:
    t = R.allocation_targets(cfg)
    assert t["large"] == dec(35) and t["mid"] == dec(15)
    assert t["small"] == dec(5) and t["micro"] == dec(3)
    assert t["futures"] == dec(10) and t["cash"] == dec(20)


def test_allocation_report_flags_a_bucket_breach_and_the_cash_floor(cfg: Config) -> None:
    pf = portfolio(open_slots=(
        slot(1, vehicle=Vehicle.SPOT, account=Account.LONG_TERM, notional=5000.0,
             bucket="large"),
    ), cash_usd=dec(500))
    rep = R.allocation_report(cfg, pf)
    assert rep.current_pct["large"] == dec(50)
    assert any("alloc_large_cap_exceeded" in b for b in rep.breaches)
    assert any("alloc_cash_min_pct_breached" in b for b in rep.breaches)


def test_allocation_gate_refuses_a_buy_that_would_break_the_cash_floor(cfg: Config) -> None:
    """S2-R17 / S2-C5 — >=20 % cash at all times; it is a floor, not a target."""
    pf = portfolio(cash_usd=dec(2100))
    g = R.allocation_gate(cfg, pf, bucket="large", add_notional_usd=dec(500))
    assert not g.allowed
    assert any("alloc_cash_min_pct_would_breach" in r for r in g.reasons)


def test_allocation_gate_respects_the_name_counts(cfg: Config) -> None:
    """S2-R19 — do not over-diversify; 50 coins is forbidden."""
    pf = portfolio(open_slots=tuple(
        slot(i, vehicle=Vehicle.SPOT, account=Account.LONG_TERM, notional=100.0, bucket="large")
        for i in range(5)
    ), cash_usd=dec(9500))
    g = R.allocation_gate(cfg, pf, bucket="large", add_notional_usd=dec(100))
    assert not g.allowed
    assert any("long_term_max_large_caps_reached (5/5)" in r for r in g.reasons)


def test_leverage_in_the_long_term_book_lands_in_the_futures_sleeve(cfg: Config) -> None:
    pf = portfolio(open_slots=(
        slot(1, vehicle=Vehicle.LEVERAGE, account=Account.LONG_TERM, notional=900.0),
    ), cash_usd=dec(9100))
    rep = R.allocation_report(cfg, pf)
    assert rep.current_pct["futures"] == dec(9)
    assert rep.current_pct["large"] == dec(0)


# ======================================================================= CF-43 accounts


def test_the_long_term_book_is_never_cut_on_a_level_loss(cfg: Config) -> None:
    """S2-C6 / S2 ``[00:53:58]`` — encoded explicitly, or the bot liquidates the investments."""
    assert not R.cut_on_level_loss_applies(cfg, Account.LONG_TERM)
    for acct in (Account.SPOT_SHORT, Account.LEVERAGE_SWING, Account.LEVERAGE_SCALP,
                 Account.CHALLENGE):
        assert R.cut_on_level_loss_applies(cfg, acct)
    off = cfg.with_overrides(account_scoped_cut_rules=False)
    assert R.cut_on_level_loss_applies(off, Account.LONG_TERM)


def test_derisk_at_two_and_three_multiples(cfg: Config) -> None:
    """S2-R18 — withdraw initial capital at 3x, partial at 2x."""
    assert R.derisk_action(cfg, average_entry=dec(100), price=dec(150)) is None
    assert R.derisk_action(cfg, average_entry=dec(100), price=dec(200)) == "partial"
    assert R.derisk_action(cfg, average_entry=dec(100), price=dec(320)) == "full"
    with pytest.raises(ValueError):
        R.derisk_action(cfg, average_entry=dec(0), price=dec(1))


def test_spot_rotation_after_a_twelve_and_a_half_percent_move(cfg: Config) -> None:
    assert not R.spot_rotation_due(cfg, average_entry=dec(100), price=dec(110))
    assert R.spot_rotation_due(cfg, average_entry=dec(100), price=dec("112.5"))


def test_hedging_is_off_by_default(cfg: Config) -> None:
    """S4-R35 — implemented, **[OUR CHOICE]** off: a portfolio operation, not a signal."""
    assert R.hedge_size(cfg, position_notional_usd=dec(1000)) is None
    on = cfg.with_overrides(hedge_enabled=True)
    notional, lev = R.hedge_size(on, position_notional_usd=dec(1000))
    assert notional == dec(1000) and lev == dec(3.0)


def test_long_term_exit_mode(cfg: Config) -> None:
    assert R.long_term_exit_mode(cfg) == "macro_msb_two_step"


# ======================================================================= approve_trade


def test_a_clean_trade_is_approved_with_a_usable_budget(cfg: Config) -> None:
    d = R.approve_trade(
        cfg, portfolio(), account=Account.LEVERAGE_SWING, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    assert d.allowed and d.reasons == ()
    assert d.budget.risk_budget_pct == dec(4.0)
    assert d.budget.loss_budget_usd == dec(400)
    # Q8: 100 % of equity (10 % margin x 10x), not the old mislabelled 10 %.
    assert d.budget.notional_ceiling_usd == dec(10000)
    assert [g.name for g in d.gates] == ["daily_loss_halt", "concurrency", "risk_ratchet"]


def test_approve_trade_reports_every_failing_gate_not_just_the_first(cfg: Config) -> None:
    pf = portfolio(
        closed_trades=(closed(1, -100.0), closed(2, -100.0, hours_ago=2)),
        open_slots=(slot(1, trade_class=TradeClass.SWING), slot(2, trade_class=TradeClass.SWING)),
        baseline_risk_pct={TradeClass.SWING.value: dec(1.0)},
    )
    d = R.approve_trade(
        cfg, pf, account=Account.LEVERAGE_SWING, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    assert not d.allowed
    assert len(d.reasons) == 3


def test_counter_trend_trade_is_sized_down_not_vetoed(cfg: Config) -> None:
    """CF-03 — a size modifier with a demotion, never a veto."""
    d = R.approve_trade(
        cfg, portfolio(), account=Account.LEVERAGE_SCALP, trade_class=TradeClass.COUNTER_TREND,
        vehicle=Vehicle.LEVERAGE, counter_trend=True,
        extra_multipliers=[cfg.counter_trend_size_multiplier],
    )
    assert d.allowed
    assert d.budget.risk_budget_pct == dec(2.0)
    assert d.budget.size_multiplier == dec("0.5")
    assert R.money_close(d.budget.target_loss_usd, dec(100))


def test_risk_module_never_mutates_the_portfolio_it_is_given(cfg: Config) -> None:
    pf = portfolio(open_slots=(slot(1),), closed_trades=(closed(1, -10.0),))
    before = (pf.equity_usd, pf.open_slots, pf.closed_trades, pf.baseline_risk_pct)
    R.approve_trade(
        cfg, pf, account=Account.LEVERAGE_SWING, trade_class=TradeClass.SWING,
        vehicle=Vehicle.LEVERAGE,
    )
    R.allocation_report(cfg, pf)
    R.daily_loss_gate(cfg, pf)
    assert (pf.equity_usd, pf.open_slots, pf.closed_trades, pf.baseline_risk_pct) == before


# ======================================================================= Q8 worked example


class TestQ8HisWorkedSizingExample:
    """**Q8 — the sizing regression test.  This is the proof that the sizing layer is right.**

    ``max_notional_pct_leverage`` shipped at **10.0**, which is his *margin* percentage (S7
    ``[00:25:54]``: *"You have a $1,000 portfolio. You enter each play with 10% of your portfolio.
    Okay. So, whatever the leverage is, you calculate that you only lose four to 5% of your port in
    that swing play."*) being enforced as a *notional* ceiling.  Because
    :func:`tbot.plan.solve_size` re-solves quantity from the clamped notional, every leverage trade
    landed at roughly **0.7 %** portfolio risk instead of the 4-5 % the CF-01 ladder assigns — a
    silent 7x under-risking, arithmetic rather than interpretation.

    The fixture below is his own worked sizing loop, read out loud over three attempts on a $1,000
    portfolio (S6 ``[00:08:36]``-``[00:11:27]``):

        *"If my stops were to get hit, I lose $114. Okay, if you have a $1,000 portfolio, this is
        11.4%. This is too high. So you have to play with your numbers. So let's do like 8 and 15…
        $65, 6.5% of your portfolio. If your stop loss were to get hit, still too high. All right,
        so let's do like seven and 12… now you lose, you know, $54… this is about 5.4% which is
        fine."*

    Entry leg at **35.551**, DCA leg at **40.11**, average **38.38**, stop **41.23** — a 2.85 stop
    distance, 7.43 % of the average entry.  The three quantity pairs he tries are (15, 25) -> 40,
    (8, 15) -> 23 and (7, 12) -> **19**, and the losses he states are **$114 / $65 / $54**.

    The row he never says out loud is the one that matters: the notional of the position he
    **accepts** is 19 x 38.38 = **$729 = 72.9 % of the portfolio**.  A 10 % notional ceiling cannot
    produce any of his three attempts, let alone the accepted one.
    """

    EQUITY_USD = dec(1_000)
    ENTRY_LEG_PRICE = dec("35.551")     # S6 `[00:08:36]`
    DCA_LEG_PRICE = dec("40.11")
    AVERAGE_ENTRY = dec("38.38")        # his stated blend
    STOP = dec("41.23")                 # his stated stop
    STOP_DISTANCE = dec("2.85")         # 41.23 - 38.38

    #: (entry qty, dca qty, total qty, loss at stop USD, exact % of a $1,000 portfolio,
    #: the percentage he says out loud, his verdict)
    HIS_ATTEMPTS = (
        (dec(15), dec(25), dec(40), dec("114.00"), dec("11.400"), 11.4, "too high"),
        (dec(8), dec(15), dec(23), dec("65.55"), dec("6.555"), 6.5, "still too high"),
        (dec(7), dec(12), dec(19), dec("54.15"), dec("5.415"), 5.4, "this is okay"),
    )

    # ------------------------------------------------------------------ his arithmetic

    def test_his_three_attempts_reproduce_the_losses_he_states(self) -> None:
        """$114 / $65 / $54 fall straight out of qty x stop distance. No config involved."""
        for entry_qty, dca_qty, total, loss, pct, spoken, _verdict in self.HIS_ATTEMPTS:
            assert entry_qty + dca_qty == total
            assert total * self.STOP_DISTANCE == loss
            assert loss / self.EQUITY_USD * dec(100) == pct
            # He truncates rather than rounds when he reads them out ("$65", "6.5%").
            assert float(pct) - spoken < 0.06
        assert [int(a[3]) for a in self.HIS_ATTEMPTS] == [114, 65, 54]

    def test_the_stop_is_seven_point_four_three_percent_of_the_average(self) -> None:
        assert self.STOP - self.AVERAGE_ENTRY == self.STOP_DISTANCE
        stop_pct = self.STOP_DISTANCE / self.AVERAGE_ENTRY * dec(100)
        assert float(stop_pct) == pytest.approx(7.43, abs=0.005)

    def test_the_accepted_position_is_729_dollars_of_notional(self) -> None:
        """72.9 % of the portfolio — the row he never says, and the whole of the defect."""
        _e, _d, total, _loss, _pct, _spoken, verdict = self.HIS_ATTEMPTS[-1]
        assert verdict == "this is okay"
        notional = total * self.AVERAGE_ENTRY
        assert float(notional) == pytest.approx(729.22, abs=0.01)
        assert float(notional / self.EQUITY_USD * dec(100)) == pytest.approx(72.9, abs=0.05)

    # ------------------------------------------------------------------ the bot reproduces it

    @staticmethod
    def _budget(cfg: Config, equity: Decimal) -> R.SizingBudget:
        return R.sizing_budget(
            cfg,
            R.PortfolioState(equity_usd=equity, now=NOW),
            trade_class=TradeClass.SWING,
            vehicle=Vehicle.LEVERAGE,
        )

    def test_the_solver_lands_inside_his_accepted_band(self, cfg: Config) -> None:
        """End to end: CF-01 budget -> :func:`tbot.plan.solve_size` -> his numbers.

        At ``max_loss_pct_swing`` = 4.0 the bot risks $40 on a $1,000 book against his $54 at
        5.4 %, so it sizes to **74 %** of his accepted position — the same trade, one notch more
        conservative, exactly as the 4 % / 5.4 % ratio predicts.  Nothing is clamped.
        """
        budget = self._budget(cfg, self.EQUITY_USD)
        assert budget.risk_budget_pct == dec("4.0")
        assert budget.loss_budget_usd == dec("40.0")

        size = PL.solve_size(
            average_entry=self.AVERAGE_ENTRY, stop_price=self.STOP, budget=budget
        )
        assert size.clamped_by_notional is False, size.reasons

        # qty = 40 / 2.85 = 14.035..., against his 19 at his 5.4 % risk.
        assert float(size.qty) == pytest.approx(14.035, abs=0.001)
        assert R.money_close(size.loss_at_stop_usd, budget.loss_budget_usd)

        # Notional 14.035 x 38.38 = $538.6 = 53.9 % of the portfolio.  Far above the old 10 %
        # ceiling, and in the same regime as his own $729.
        assert float(size.notional_usd) == pytest.approx(538.68, abs=0.05)
        pct_of_equity = size.notional_usd / self.EQUITY_USD * dec(100)
        assert dec(40) < pct_of_equity < dec(80)

        # The ratio to his accepted position is exactly the ratio of the risk budgets.
        _e, _d, his_total, his_loss, _pct, _spoken, _v = self.HIS_ATTEMPTS[-1]
        assert float(size.qty / his_total) == pytest.approx(
            float(budget.loss_budget_usd / his_loss), abs=1e-9
        )

    def test_at_his_own_five_point_four_percent_the_bot_reproduces_the_ticket_exactly(
        self, cfg: Config
    ) -> None:
        """Feed the bot the risk percentage he actually used and it prints his ticket.

        This is the end-to-end assertion the fix is judged on: qty **19**, loss **$54**, notional
        **$729**, none of it clamped.  5.4 % is above ``max_loss_pct_swing_hard_cap`` (5.0), so it
        is supplied here as the historical input it is, not as a shipped default.
        """
        his_pct = dec("5.415")          # 54.15 / 1000 x 100 — his "about 5.4%"
        budget = R.SizingBudget(
            equity_usd=self.EQUITY_USD,
            risk_budget_pct=his_pct,
            loss_budget_usd=R.loss_budget_usd(
                cfg, equity_usd=self.EQUITY_USD, risk_pct=his_pct
            ),
            size_multiplier=dec(1),
            notional_ceiling_usd=R.notional_ceiling_usd(
                cfg, equity_usd=self.EQUITY_USD, vehicle=Vehicle.LEVERAGE
            ),
        )
        assert budget.loss_budget_usd == dec("54.15")

        size = PL.solve_size(
            average_entry=self.AVERAGE_ENTRY, stop_price=self.STOP, budget=budget
        )
        assert size.clamped_by_notional is False, size.reasons
        assert size.qty == dec(19)                                  # his 7 + 12
        assert R.money_close(size.loss_at_stop_usd, dec("54.15"))    # his "$54"
        assert float(size.notional_usd) == pytest.approx(729.22, abs=0.01)
        assert float(size.notional_usd / self.EQUITY_USD * dec(100)) == pytest.approx(
            72.9, abs=0.05
        )

    def test_the_ladder_splits_into_his_two_legs(self, cfg: Config) -> None:
        """His 7 + 12 is a two-leg ladder, light first — the CF-18 ordering, Q3's ratio.

        His own split is 7:12 = 36.8/63.2; the shipped ``dca_size_split_2`` is 39/61 (Q3, derived
        from the S6 LINK ladder).  Both put the blend nearer the DCA and neither is 50/50.
        """
        entry_qty, dca_qty, total, _loss, _pct, _spoken, _v = self.HIS_ATTEMPTS[-1]
        his_split = [entry_qty / total, dca_qty / total]
        assert [round(float(x), 3) for x in his_split] == [0.368, 0.632]
        assert his_split[0] < his_split[1]                    # light entry, heavy DCA

        shipped = PL.entry_split(cfg, 2)
        assert shipped == (dec("0.39"), dec("0.61"))
        assert abs(float(shipped[0] - his_split[0])) < 0.03

        blended = PL.blended_entry([
            PL.EntryRung(index=0, price=self.ENTRY_LEG_PRICE, size_fraction=his_split[0],
                         kind="entry", level_id="L0"),
            PL.EntryRung(index=1, price=self.DCA_LEG_PRICE, size_fraction=his_split[1],
                         kind="dca", level_id="L1"),
        ])
        # 38.43 against the 38.38 he reads off the exchange - about 1 % of rounding drift, which
        # is what part2 records and why his stated average is the fixture rather than a recompute.
        assert float(blended) == pytest.approx(38.43, abs=0.01)

    # ------------------------------------------------------------------ the regression itself

    def test_the_old_ten_percent_ceiling_discarded_the_risk_budget(self, cfg: Config) -> None:
        """The defect, pinned. With the ceiling at 10 the same trade risks 0.74 %, not 4 % — 5.4x under.

        ``solve_size`` clamps the notional and then **re-solves quantity from the clamp**, so the
        CF-01 risk budget is silently discarded rather than merely capped.  This is the assertion
        that fails if anyone puts 10.0 back.
        """
        broken = cfg.with_overrides(max_notional_pct_leverage=10.0)
        budget = self._budget(broken, self.EQUITY_USD)
        assert budget.notional_ceiling_usd == dec(100)          # 10 % of $1,000

        size = PL.solve_size(
            average_entry=self.AVERAGE_ENTRY, stop_price=self.STOP, budget=budget
        )
        assert size.clamped_by_notional is True
        assert any("notional_clamped_to_ceiling" in r for r in size.reasons)

        realised_risk_pct = size.loss_at_stop_usd / self.EQUITY_USD * dec(100)
        assert float(realised_risk_pct) == pytest.approx(0.7426, abs=0.0005)
        assert float(dec("4.0") / realised_risk_pct) == pytest.approx(5.39, abs=0.01)

        # ...and with the fix the same trade is not clamped at all.
        fixed = self._budget(cfg, self.EQUITY_USD)
        fixed_size = PL.solve_size(
            average_entry=self.AVERAGE_ENTRY, stop_price=self.STOP, budget=fixed
        )
        assert fixed_size.clamped_by_notional is False
        assert float(fixed_size.loss_at_stop_usd / self.EQUITY_USD * dec(100)) == pytest.approx(
            4.0, abs=1e-9
        )
        assert fixed_size.qty / size.qty > dec(5)

    def test_the_margin_reading_closes_the_s7_arithmetic(self, cfg: Config) -> None:
        """Why 10 % is margin: only the margin reading makes S7's own sentence true.

        S7 ``[00:20:33]``: *"If you go in with like 10% of your portfolio into a play and that
        would cause you to lose like 5% of your portfolio…"*  On $1,000 that is $100 in and $50
        lost — **half of what you put in**.  Under the notional reading that needs a 50 % stop,
        which is absurd against ``max_stop_pct_leverage`` = 9 %.  Under the margin reading at his
        stated ``default_leverage`` of 10x (S2 ``[01:52:12]``, *"I always do 10x"*), $100 margin
        is $1,000 notional and a **5 %** adverse move produces exactly the $50.
        """
        equity = dec(1_000)
        margin = R.margin_ceiling_usd(cfg, equity_usd=equity)
        assert margin == dec(100)                                   # S7's 10 %

        notional = margin * dec(cfg.default_leverage)
        assert notional == dec(1_000)                               # 100 % of equity
        assert notional == R.notional_ceiling_usd(
            cfg, equity_usd=equity, vehicle=Vehicle.LEVERAGE
        )

        adverse_move_pct = dec(50) / notional * dec(100)
        assert adverse_move_pct == dec(5)                           # his 5 %, and it is sane
        assert float(adverse_move_pct) < cfg.max_stop_pct_leverage

        # The notional reading would have required this, which the CF-06 ceiling forbids outright.
        assert float(dec(50) / margin * dec(100)) == 50.0 > cfg.max_stop_pct_leverage

    def test_his_own_position_sits_just_under_the_margin_ceiling(self, cfg: Config) -> None:
        """Cross-check: $729 notional at 10x is $72.9 margin = 7.3 % — just under S7's 10 %."""
        _e, _d, total, _loss, _pct, _spoken, _v = self.HIS_ATTEMPTS[-1]
        notional = total * self.AVERAGE_ENTRY
        margin = notional / dec(cfg.default_leverage)
        assert float(margin / self.EQUITY_USD * dec(100)) == pytest.approx(7.29, abs=0.01)
        assert margin < R.margin_ceiling_usd(cfg, equity_usd=self.EQUITY_USD)


# ---------------------------------------------- GAP 2: correlated-exposure cap (GAPS.md, 2026-09-15)
#
# Entirely OUR engineering idea. The corpus proposes no correlation test anywhere -- CF-35 only
# records that the DXY relationship broke. His own "never more than 2 concurrent positions"
# (risk doc, CONFLICTS.md:2305) is a MARGIN rule: four positions leave nothing to fund the DCA
# legs. Ours is a different rationale that lands near the same number, and the keys say so.


def _corr_series(closes, symbol: str):
    """A minimal Series with the given closes -- enough for rolling_correlation."""
    from datetime import timedelta as _td

    from tbot.models import Series as _Series
    from tbot.models import Timeframe as _Timeframe

    step = _td(minutes=_Timeframe.parse("4H").minutes)
    idx = [NOW + i * step for i in range(len(closes))]
    return _Series.from_arrays(
        idx,
        [float(c) for c in closes], [float(c) + 0.5 for c in closes],
        [float(c) - 0.5 for c in closes], [float(c) for c in closes],
        volume=[1_000.0] * len(closes), tf="4H", symbol=symbol,
    )


_RISING = [100.0 + i for i in range(40)]
_ALSO_RISING = [50.0 + 0.5 * i for i in range(40)]      # corr with _RISING = +1
_FALLING = [200.0 - i for i in range(40)]               # corr with _RISING = -1


def _corr_cfg(**kw):
    base = dict(max_correlated_concurrent_enabled=True, max_correlated_concurrent=2,
                correlation_threshold=0.7, correlation_lookback_bars=90)
    base.update(kw)
    return Config().with_overrides(**base)


def test_correlation_cap_defaults_are_ours_and_off():
    cfg = Config()
    assert cfg.max_correlated_concurrent_enabled is False
    assert cfg.max_correlated_concurrent == 2
    assert cfg.correlation_threshold == 0.7
    assert cfg.correlation_lookback_bars == 90
    from tbot.config import KEY_SPEC_BY_NAME
    for key in ("max_correlated_concurrent_enabled", "max_correlated_concurrent",
                "correlation_threshold", "correlation_lookback_bars"):
        assert "[OUR CHOICE]" in KEY_SPEC_BY_NAME[key].source_id, key


def test_correlation_cap_is_a_no_op_while_disabled():
    """ACCEPTANCE: with the flag off the gate must never refuse anything, whatever the book."""
    series = {"S": _corr_series(_RISING, "S"),
              "C0": _corr_series(_ALSO_RISING, "C0"),
              "C1": _corr_series(_ALSO_RISING, "C1"),
              "C2": _corr_series(_ALSO_RISING, "C2")}
    pf = portfolio(open_slots=(slot(0), slot(1), slot(2)))
    gate = R.correlation_cap_gate(Config(), pf, symbol="S", series_by_symbol=series)
    assert gate.allowed and gate.reasons == ()


def test_correlation_cap_vetoes_once_the_cap_is_reached():
    series = {"S": _corr_series(_RISING, "S"),
              "C0": _corr_series(_ALSO_RISING, "C0"),
              "C1": _corr_series(_ALSO_RISING, "C1")}
    pf = portfolio(open_slots=(slot(0), slot(1)))
    gate = R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol=series)
    assert not gate.allowed
    assert "max_correlated_concurrent_reached (2/2" in gate.reasons[0]
    assert "C0" in gate.reasons[0] and "C1" in gate.reasons[0]


def test_correlation_cap_allows_below_the_cap():
    series = {"S": _corr_series(_RISING, "S"), "C0": _corr_series(_ALSO_RISING, "C0")}
    pf = portfolio(open_slots=(slot(0),))
    assert R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol=series).allowed


def test_correlation_cap_ignores_negatively_correlated_positions():
    """A same-direction position in an anti-correlated asset is a hedge, not concentration.

    The gate measures the SIGNED correlation for exactly this reason; an abs() here would
    veto the one combination that actually reduces risk.
    """
    series = {"S": _corr_series(_RISING, "S"),
              "C0": _corr_series(_FALLING, "C0"),
              "C1": _corr_series(_FALLING, "C1")}
    pf = portfolio(open_slots=(slot(0), slot(1)))
    gate = R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol=series)
    assert gate.allowed


def test_correlation_cap_reports_slots_it_could_not_assess():
    """Nothing is dropped silently (INTERFACES.md 9.6): unassessed slots are named in reasons."""
    series = {"S": _corr_series(_RISING, "S")}          # C0/C1 have no series at all
    pf = portfolio(open_slots=(slot(0), slot(1)))
    gate = R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol=series)
    assert gate.allowed, "an unassessable slot must not be counted as correlated"
    assert gate.reasons and "2 live slot(s) had no usable series" in gate.reasons[0]


def test_correlation_cap_passes_when_the_candidate_has_no_series():
    pf = portfolio(open_slots=(slot(0), slot(1)))
    gate = R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol={})
    assert gate.allowed
    assert "no series for the candidate symbol" in gate.reasons[0]


def test_correlation_cap_skips_the_candidates_own_symbol():
    """Re-entering the same symbol is CF-21's problem, not this gate's."""
    series = {"S": _corr_series(_RISING, "S")}
    same = R.OpenSlot(position_id="P9", account=Account.LEVERAGE_SWING,
                      vehicle=Vehicle.LEVERAGE, trade_class=TradeClass.SWING,
                      state=PositionState.OPEN, notional_usd=dec(500), symbol="S")
    pf = portfolio(open_slots=(same, same))
    gate = R.correlation_cap_gate(_corr_cfg(max_correlated_concurrent=1), pf,
                                  symbol="S", series_by_symbol=series)
    assert gate.allowed and gate.reasons == ()


def test_correlation_cap_counts_only_live_slots():
    series = {"S": _corr_series(_RISING, "S"),
              "C0": _corr_series(_ALSO_RISING, "C0"),
              "C1": _corr_series(_ALSO_RISING, "C1")}
    pf = portfolio(open_slots=(slot(0), slot(1, state=PositionState.CLOSED)))
    gate = R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol=series)
    assert gate.allowed, "a closed position must not consume a correlated slot"


def test_correlation_cap_threshold_is_honoured():
    """Correlation +1 clears 0.7 but not a threshold above it."""
    series = {"S": _corr_series(_RISING, "S"),
              "C0": _corr_series(_ALSO_RISING, "C0"),
              "C1": _corr_series(_ALSO_RISING, "C1")}
    pf = portfolio(open_slots=(slot(0), slot(1)))
    assert not R.correlation_cap_gate(_corr_cfg(correlation_threshold=0.99), pf,
                                      symbol="S", series_by_symbol=series).allowed
    # raise it above what these series can reach and the same book is allowed through
    weak = {"S": _corr_series(_RISING, "S"),
            "C0": _corr_series([100.0 + (i % 7) for i in range(40)], "C0"),
            "C1": _corr_series([100.0 + (i % 5) for i in range(40)], "C1")}
    assert R.correlation_cap_gate(_corr_cfg(), pf, symbol="S", series_by_symbol=weak).allowed


def test_correlation_cap_reuses_the_regime_primitive():
    """GAPS.md GAP 2 says reuse rolling_correlation; assert no second implementation appeared."""
    from pathlib import Path

    src = Path(R.__file__).read_text(encoding="utf-8")
    assert "rolling_correlation" in src, "the gate must call the regime primitive"
    # no second IMPLEMENTATION: risk.py must not compute a correlation of its own.
    for smell in ("corrcoef", "np.cov", "pearson"):
        assert smell not in src, (
            f"risk.py computes its own correlation ({smell}) - reuse regime.rolling_correlation")
