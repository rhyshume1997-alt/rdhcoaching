"""Contract tests for :mod:`tbot.plan` (SPEC.md §8, trade-plan construction).

The load-bearing test is :func:`test_stop_out_loses_exactly_the_capped_percentage`: across a wide
range of stop widths, the quantity solved backwards from the risk budget must make a full
stop-out cost **exactly** the capped percentage of equity.  That identity is the whole point of
CF-01/S6-R12 and it is checked with a tolerance helper, never with ``==`` on money.

Every :class:`~tbot.models.Setup` here is constructed by hand so these tests do not depend on the
detectors, the confluence layer or qualification.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import dataclasses

import pytest

import tbot.plan as PL
import tbot.primitives as P
from tbot.config import Config
from tbot.models import (
    Conviction,
    Direction,
    EntryFamily,
    EntryRung,
    Level,
    LevelKind,
    OrderType,
    Series,
    Setup,
    TakeProfit,
    Timeframe,
    TradeClass,
    TradePlan,
    Vehicle,
    Zone,
    ZoneClass,
    ZoneSide,
    dec,
)
from tbot.risk import PortfolioState, SizingBudget, money_close, sizing_budget

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
EQUITY = dec(10_000)


# --------------------------------------------------------------------------- helpers

def make_series(rows, tf: str = "4H", symbol: str = "T", volumes=None) -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    vols = list(volumes) if volumes is not None else [1.0] * len(rows)
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=vols, tf=tf, symbol=symbol,
    )


def flat_series(n: int = 60, price: float = 100.0):
    """``n`` bars with a constant true range of 1.0, so ``ATR(14) == 1.0`` exactly."""
    return [(price, price + 0.5, price - 0.5, price) for _ in range(n)]


def level(lid: str, price: float, kind: LevelKind = LevelKind.SUPPORT, touches: int = 2) -> Level:
    return Level(
        id=lid, symbol="T", tf=Timeframe.H4, price=dec(price), kind=kind,
        created_index=0, touch_count=touches,
    )


def make_setup(
    *,
    direction: Direction = Direction.LONG,
    trade_class: TradeClass = TradeClass.SWING,
    family: EntryFamily = EntryFamily.RETEST,
    conviction: Conviction = Conviction.NORMAL,
    vetoes=(),
) -> Setup:
    return Setup(
        id="S1", symbol="T", direction=direction, trade_tf=Timeframe.H4,
        structure_tf=Timeframe.D1, trade_class=trade_class, anchor_price=dec(100.0),
        created_index=59, entry_family=family, conviction=conviction,
        vetoes=list(vetoes), source_ids=("CF-10", "S5-R15"),
    )


def make_zone(depth_atr: float) -> Zone:
    return Zone(
        id="Z1", symbol="T", tf=Timeframe.H4, side=ZoneSide.DEMAND,
        zone_class=ZoneClass.CONTINUATION, box_top=dec(100.5), box_bottom=dec(99.0),
        midpoint=dec(99.75), body_count=3, formation_start_index=30, formation_end_index=34,
        breakout_index=36, move_away_pct=dec(6), move_away_atr=dec(5),
        depth_atr=dec(depth_atr),
    )


def big_budget(*, risk_pct: float = 4.0, multiplier: float = 1.0) -> SizingBudget:
    """A budget whose CF-02 ceiling never binds, so the risk cap is the only constraint."""
    return SizingBudget(
        equity_usd=EQUITY,
        risk_budget_pct=dec(risk_pct),
        loss_budget_usd=EQUITY * dec(risk_pct) / dec(100),
        size_multiplier=dec(multiplier),
        notional_ceiling_usd=dec(10**9),
    )


def hand_plan(
    *,
    stop_pct: float,
    budget: SizingBudget,
    direction: Direction = Direction.LONG,
    entries=((100.0, 0.3), (99.0, 0.7)),
    tps=((104.0, 0.5), (112.0, 0.5)),
) -> TradePlan:
    """A plan assembled directly, so the identity under test is isolated from level selection."""
    rungs = [
        EntryRung(index=i, price=dec(p), size_fraction=dec(f), kind="entry" if i == 0 else "dca",
                  level_id=f"L{i}")
        for i, (p, f) in enumerate(entries)
    ]
    avg = PL.blended_entry(rungs)
    gap = avg * dec(stop_pct) / dec(100)
    stop = avg - gap if direction is Direction.LONG else avg + gap
    size = PL.solve_size(average_entry=avg, stop_price=stop, budget=budget)
    tp_objs = [
        TakeProfit(index=i, price=dec(p), size_fraction=dec(f), level_id=f"T{i}")
        for i, (p, f) in enumerate(tps)
    ]
    return TradePlan(
        id="S1:plan", setup_id="S1", symbol="T", direction=direction,
        trade_class=TradeClass.SWING, vehicle=Vehicle.LEVERAGE, leverage=dec(2),
        entries=rungs, stop_price=stop, take_profits=tp_objs, qty_total=size.qty,
        notional_usd=size.notional_usd, risk_budget_pct=budget.risk_budget_pct,
        average_entry=dec(0), planned_average_entry=avg,
        rr_to_tp1=dec(1), expected_move_pct=dec(10), invalidation_level_id="L0",
    )


@pytest.fixture()
def cfg() -> Config:
    return Config.load()


@pytest.fixture()
def uncapped(cfg: Config) -> Config:
    """Defaults with the CF-02 notional ceiling pushed to its maximum, so the CF-01 risk cap is
    the binding constraint end to end (at the shipped 10 % ceiling a stop narrower than 40 %
    clamps first — see :func:`test_notional_clamp_puts_risk_under_budget`)."""
    return cfg.with_overrides(max_notional_pct_leverage=100.0)


# ======================================================================= sizing (CF-01, CF-02)

STOP_WIDTHS = [0.5, 1.0, 2.0, 3.5, 5.0, 7.5, 9.0, 12.0, 20.0, 33.3, 50.0]


@pytest.mark.parametrize("stop_pct", STOP_WIDTHS)
@pytest.mark.parametrize("risk_pct", [1.5, 2.0, 2.5, 4.0, 5.0])
def test_stop_out_loses_exactly_the_capped_percentage(stop_pct: float, risk_pct: float) -> None:
    """SPEC.md §8.8 / S6-R12: ``qty * |stop - average_entry| == risk_pct/100 * equity``.

    Solved backwards, the identity has to hold at **every** stop width — that is what makes the
    cap a cap rather than a coincidence.
    """
    budget = big_budget(risk_pct=risk_pct)
    plan = hand_plan(stop_pct=stop_pct, budget=budget)
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert rep.ok, rep.problems
    assert money_close(rep.loss_at_stop_usd, EQUITY * dec(risk_pct) / dec(100))
    assert money_close(rep.realised_risk_pct, dec(risk_pct))


@pytest.mark.parametrize("stop_pct", STOP_WIDTHS)
def test_stop_out_identity_holds_for_shorts(stop_pct: float) -> None:
    budget = big_budget()
    plan = hand_plan(
        stop_pct=stop_pct, budget=budget, direction=Direction.SHORT,
        entries=((100.0, 0.3), (101.0, 0.7)), tps=((96.0, 0.5), (88.0, 0.5)),
    )
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert rep.ok, rep.problems
    assert money_close(rep.realised_risk_pct, dec(4.0))


@pytest.mark.parametrize("mult", [1.0, 0.66, 0.5, 0.33, 0.25])
def test_size_multipliers_scale_the_loss_proportionally(mult: float) -> None:
    """§10.8 — the CF-07 decay and the CF-03/CF-35 multipliers compose on quantity, so the loss
    scales with them and the cap still binds from above."""
    budget = big_budget(multiplier=mult)
    plan = hand_plan(stop_pct=8.0, budget=budget)
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY, size_multiplier=dec(mult))
    assert rep.ok, rep.problems
    assert money_close(rep.loss_at_stop_usd, dec(400) * dec(mult))


# ------------------------------------------------- entry-ladder monotonicity (regression)
#
# `check_plan_consistency` walked the ladder from the size-weighted AVERAGE instead of from
# rung 0's price.  The average is not a rung; it is a convex combination of all of them, so it
# can sit anywhere inside the ladder.  Latent for months because the old dca_size_split_3 of
# [0.2, 0.3, 0.5] put the average at 97.1 on the fixtures, coincidentally just ABOVE rung 1 at
# 97.0.  Correcting the split to his stated 15/32.5/52.5 moved it to 96.925 and the check
# started rejecting a perfectly valid ladder.
#
# What the bug actually did, established by construction rather than assumed:
#   * FALSE REJECT of a valid ladder whenever the average lands beyond rung 1.  Demonstrated.
#   * MISREPORTS which rung is at fault on an inverted ladder, because only the FIRST
#     comparison used the average; every later one was already rung-to-rung.
#   * It did NOT silently accept an invalid ladder.  An inversion at rung 1 is caught either by
#     its own comparison or by the next rung's, so the plan was still rejected.  The earlier
#     claim that it "could fail in either direction" was wrong and is withdrawn.


def test_consistency_accepts_a_valid_ladder_whose_average_falls_beyond_rung_1() -> None:
    """The regression itself: 100 / 97 / 96 at his stated split, average 96.925.

    A strictly descending long ladder is valid by definition.  The old check compared rung 1
    (97.0) against the average (96.925) and rejected it.
    """
    plan = hand_plan(
        stop_pct=8.0, budget=big_budget(),
        entries=((100.0, 0.15), (97.0, 0.325), (96.0, 0.525)),
    )
    assert PL.blended_entry(plan.entries) == dec("96.925")     # average sits BELOW rung 1
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert rep.ok, rep.problems
    assert not [p for p in rep.problems if "step away" in p]


def test_consistency_still_rejects_an_inverted_ladder() -> None:
    """Guard against over-correcting: rung 1 above rung 0 on a long is still invalid."""
    plan = hand_plan(
        stop_pct=8.0, budget=big_budget(),
        entries=((98.0, 0.15), (99.0, 0.325), (97.0, 0.525)),
    )
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert not rep.ok
    assert any("entry rung 1" in p and "step away" in p for p in rep.problems)


def test_consistency_reports_every_inverted_rung_not_just_the_last() -> None:
    """The under-reporting half.  On 100 / 101 / 102 both DCA rungs are inverted.

    Walking from the average (101.7) surfaced only rung 2; walking from rung 0 surfaces both.
    The fix therefore reports MORE, not differently - the old code hid one of two real
    problems behind the average.  The plan was rejected either way, so nothing bad got
    through, but the diagnostic was lossy as well as wrong.
    """
    plan = hand_plan(
        stop_pct=8.0, budget=big_budget(),
        entries=((100.0, 0.1), (101.0, 0.1), (102.0, 0.8)),
    )
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert not rep.ok
    stepping = [p for p in rep.problems if "step away" in p]
    assert any("entry rung 1" in p for p in stepping), stepping
    assert any("entry rung 2" in p for p in stepping), stepping


def test_consistency_walks_shorts_from_rung_0_too() -> None:
    """Mirror image: a short ladder steps UP, and its average can fall beyond rung 1 the same way."""
    plan = hand_plan(
        stop_pct=8.0, budget=big_budget(), direction=Direction.SHORT,
        entries=((100.0, 0.15), (103.0, 0.325), (104.0, 0.525)),
        tps=((99.0, 0.5), (92.0, 0.5)),                       # a short takes profit DOWNWARD
    )
    assert PL.blended_entry(plan.entries) == dec("103.075")    # average sits ABOVE rung 1
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert rep.ok, rep.problems
    assert not [p for p in rep.problems if "step away" in p]


def test_notional_clamp_puts_risk_under_budget() -> None:
    """CF-02: notional is clamped, qty re-solved, and the realised risk lands **under** budget."""
    budget = SizingBudget(
        equity_usd=EQUITY, risk_budget_pct=dec(4), loss_budget_usd=dec(400),
        size_multiplier=dec(1), notional_ceiling_usd=dec(1000),
    )
    size = PL.solve_size(average_entry=dec(100), stop_price=dec(99), budget=budget)
    assert size.clamped_by_notional
    assert money_close(size.notional_usd, dec(1000))
    assert money_close(size.qty, dec(10))
    assert size.loss_at_stop_usd < budget.loss_budget_usd
    plan = hand_plan(stop_pct=1.0, budget=budget)
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert rep.ok, rep.problems          # under budget is allowed
    rep2 = PL.check_plan_consistency(plan, equity_usd=EQUITY, allow_under_budget=False)
    assert not rep2.ok


def test_solve_size_rejects_a_zero_width_stop() -> None:
    with pytest.raises(PL.PlanError):
        PL.solve_size(average_entry=dec(100), stop_price=dec(100), budget=big_budget())


def test_derive_leverage(cfg: Config) -> None:
    """§8.10 — leverage is derived so a stop-out costs exactly the risk budget; spot is 1.0."""
    budget = big_budget()
    assert PL.derive_leverage(
        vehicle=Vehicle.SPOT, notional_usd=dec(5000), budget=budget
    ) == dec(1)
    lev = PL.derive_leverage(vehicle=Vehicle.LEVERAGE, notional_usd=dec(1000), budget=budget)
    assert money_close(lev, dec(1000) / dec(400))
    capped = PL.derive_leverage(
        vehicle=Vehicle.LEVERAGE, notional_usd=dec(100_000), budget=budget,
        max_leverage=dec(cfg.leverage_downgrade_max_multiple),
    )
    assert money_close(capped, dec(3))


# ======================================================================= consistency guard


def test_assert_plan_consistent_raises_on_a_tampered_plan() -> None:
    plan = hand_plan(stop_pct=8.0, budget=big_budget())
    PL.assert_plan_consistent(plan, equity_usd=EQUITY)
    plan.qty_total = dec(plan.qty_total) * dec(2)
    with pytest.raises(PL.PlanInconsistent):
        PL.assert_plan_consistent(plan, equity_usd=EQUITY)


def test_consistency_catches_a_stop_on_the_wrong_side() -> None:
    plan = hand_plan(stop_pct=8.0, budget=big_budget())
    plan.stop_price = dec(200)
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert not rep.ok
    assert any("not below the blended entry" in p for p in rep.problems)


def test_consistency_catches_a_heavy_first_rung() -> None:
    """S2-R8: the first fill is the lightest, the heaviest sits at the far end of the ladder."""
    plan = hand_plan(stop_pct=8.0, budget=big_budget(), entries=((100.0, 0.7), (99.0, 0.3)))
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert not rep.ok
    assert any("lighter than the first rung" in p for p in rep.problems)


def test_consistency_catches_a_single_take_profit() -> None:
    """S5-R26 is an explicit prohibition on one entry and one TP."""
    plan = hand_plan(stop_pct=8.0, budget=big_budget(), tps=((104.0, 1.0),))
    rep = PL.check_plan_consistency(plan, equity_usd=EQUITY)
    assert not rep.ok
    assert any("tp_min_count" in p for p in rep.problems)


# ======================================================================= entry ladder (CF-17/18)


def test_dca_leg_count_by_play_class(cfg: Config) -> None:
    swing = dict(trade_class=TradeClass.SWING, entry_family=EntryFamily.RETEST)
    assert PL.dca_leg_count(cfg, zone_depth_atr=0.8, **swing) == 1      # default (S6-R16)
    assert PL.dca_leg_count(cfg, zone_depth_atr=2.0, **swing) == 2      # deep zone (S5-R22)
    assert PL.dca_leg_count(cfg, zone_depth_atr=None, **swing) == 1
    # scalp: 1 max, 0 when the zone is tight (S8-R17)
    assert PL.dca_leg_count(
        cfg, trade_class=TradeClass.SCALP, entry_family=EntryFamily.RETEST, zone_depth_atr=2.0
    ) == 1
    # breakdown / trend-line / pattern breakout: single entry (S8-R11)
    assert PL.dca_leg_count(
        cfg, trade_class=TradeClass.SWING, entry_family=EntryFamily.FLIP_PENDING,
        zone_depth_atr=2.0,
    ) == 0
    # SFP: single entry (CF-20)
    assert PL.dca_leg_count(cfg, single_entry_play=True, zone_depth_atr=9.0, **swing) == 0


def test_q10_pre_sr_light_limit_is_off_by_default(cfg: Config) -> None:
    """**Q10** — ``presr_light_limit_enabled``: the entry neither CF-16 family covers.

    CF-16's split survives contact with the transcripts intact — an SR point is *by definition* a
    level that has already changed roles (S3 ``[01:54:12]``), so *"I always enter my positions at
    SR points"* was never a counter-example to S4's *"you're not going to place limit orders at
    the SR line"* (S4 ``[00:55:38]``), which is scoped to a level that has **not** flipped yet.

    But there is an intermediate state CF-16 misses.  A level becomes "an SR" the moment it is
    broken, *before* the retest, and he does sometimes rest a light limit there:

        *"We broke above resistance. This became an SR, right? We came and bounced briefly from
        it. My entry was light there. My DCA came around 57360… But if I was a little more patient
        and awake, then yes, I would have waited for the flip to happen."* — S2 ``[00:27:08]``

    Permitted-but-inferior, in his own words, so it ships **off** and is a sweep pair: the
    trade-off is fill rate against deviation rate at freshly-broken levels.
    """
    pending = dict(trade_class=TradeClass.SWING, entry_family=EntryFamily.FLIP_PENDING)
    assert cfg.presr_light_limit_enabled is False
    assert PL.dca_leg_count(cfg, zone_depth_atr=2.0, **pending) == 0

    on = cfg.with_overrides(presr_light_limit_enabled=True)
    assert PL.dca_leg_count(on, zone_depth_atr=2.0, **pending) == 1

    # ...and the ladder it produces is his: light limit first, heavier at the confirmed flip.
    entry, dca = PL.entry_split(on, 2)
    assert entry < dca

    # A genuine single-entry play (SFP, breakdown) is unaffected — that is a different rule.
    assert PL.dca_leg_count(on, single_entry_play=True, zone_depth_atr=9.0, **pending) == 0


def test_dca_count_never_exceeds_the_global_max(cfg: Config) -> None:
    """S2-R9 / S6 ``[01:01:51]`` — six-leg and SMC-style ladders are hard-forbidden.

    Even a very deep zone cannot push the ladder past ``dca_count_max``, and ``config.py``
    itself refuses a ``dca_count_default`` above it.
    """
    loose = cfg.with_overrides(dca2_min_zone_depth_atr=0.1)
    n = PL.dca_leg_count(
        loose, trade_class=TradeClass.SWING, entry_family=EntryFamily.RETEST, zone_depth_atr=99.0
    )
    assert n == loose.dca_count_max == 2
    tight = cfg.with_overrides(dca_count_max=1, dca_count_default=1)
    assert PL.dca_leg_count(
        tight, trade_class=TradeClass.SWING, entry_family=EntryFamily.RETEST, zone_depth_atr=99.0
    ) == 1


def test_entry_split_ratios(cfg: Config) -> None:
    """**Q3** — the ladder ratios come out of his own worked LINK ladder, not a guess.

    S6 ``[00:38:49]``: entries at 17.28 / 17.858 / 18.181 with quantities *"let's do 35, let's do
    55, and let's do 100"*, average read back as **17.921**.  (35x17.28 + 55x17.858 +
    100x18.181)/190 = 17.9215 — exact, so the quantities are real.  Three legs = 35:55:100 =
    18.4/29.0/52.6, which the shipped [0.20, 0.30, 0.50] matched.

    SUPERSEDED for three legs.  He STATES the ladder in writing three times — Discord
    #class-session-one M2, #class-session-five M8 ("the 15/30-35/50-55% method/rule") and the
    linked risk doc ("15% at entry / 30% at DCA 1 / 50% at DCA 2").  Stated outranks derived, so
    three legs are now his midpoints, 15/32.5/52.5.  The TWO-leg 39/61 is untouched: he never
    states a two-leg split, so the S6 arithmetic remains its best source.

    Two legs are the same ladder with the third rung unfilled: S6 ``[00:48:10]`` reads the average
    back as **17.63** on *"a total of 90 coins"*, and (35x17.28 + 55x17.858)/90 = 17.6332 — exact
    again.  So 35:55 = **39/61**, replacing the guessed 30/70.  It also reproduces his description
    of where the blend lands, *"somewhere in the middle"* (S6 ``[00:46:58]``), which 30/70 does not.

    Wick-heavy is his one stated number: *"you go in very light there, like I'm talking about 20 to
    30%"* (S6 ``[01:54:34]``) — 25/75 is the midpoint of that band, replacing 20/80 at its edge.
    """
    assert PL.entry_split(cfg, 1) == (dec(1),)
    assert PL.entry_split(cfg, 2) == (dec("0.39"), dec("0.61"))
    assert PL.entry_split(cfg, 2, wick_heavy=True) == (dec("0.25"), dec("0.75"))   # S6-R27
    assert PL.entry_split(cfg, 3) == (dec("0.15"), dec("0.325"), dec("0.525"))
    with pytest.raises(PL.PlanError):
        PL.entry_split(cfg, 4)


def test_entry_splits_reproduce_his_worked_link_ladder() -> None:
    """The arithmetic Q3 is derived from, checked against the averages he reads out loud."""
    prices = (dec("17.28"), dec("17.858"), dec("18.181"))
    qty = (dec(35), dec(55), dec(100))

    three = sum(p * q for p, q in zip(prices, qty)) / sum(qty)
    assert float(three) == pytest.approx(17.921, abs=0.001)          # S6 `[00:40:05]`
    assert [round(float(q / sum(qty)), 4) for q in qty] == [0.1842, 0.2895, 0.5263]

    two = sum(p * q for p, q in zip(prices[:2], qty[:2])) / sum(qty[:2])
    assert float(two) == pytest.approx(17.633, abs=0.001)            # S6 `[00:48:10]`
    assert [round(float(q / sum(qty[:2])), 2) for q in qty[:2]] == [0.39, 0.61]


def test_entry_ladder_is_light_first_heavy_last(cfg: Config) -> None:
    rungs, notes = PL.build_entry_ladder(
        cfg, direction=Direction.LONG, entry_price=dec(100), entry_level_id="L0",
        dca_levels=[level("L1", 98.0)], dca_count=1, at_index=59,
    )
    assert [r.price for r in rungs] == [dec(100), dec(98.0)]
    assert [r.kind for r in rungs] == ["entry", "dca"]
    assert rungs[0].size_fraction < rungs[1].size_fraction
    assert PL.blended_entry(rungs) == dec(100) * dec("0.39") + dec(98) * dec("0.61")
    assert notes == ()


def test_entry_ladder_skips_levels_that_are_not_beyond_the_previous_rung(cfg: Config) -> None:
    """DCA prices attach to the next structural level *against* the trade (S2-R10)."""
    rungs, notes = PL.build_entry_ladder(
        cfg, direction=Direction.LONG, entry_price=dec(100), entry_level_id="L0",
        dca_levels=[level("Lup", 101.0), level("Ldn", 97.0)], dca_count=1, at_index=59,
    )
    assert [r.level_id for r in rungs] == ["L0", "Ldn"]
    assert any("not_beyond_previous_rung" in n for n in notes)


def test_entry_ladder_shrinks_and_says_so_when_levels_run_out(cfg: Config) -> None:
    rungs, notes = PL.build_entry_ladder(
        cfg, direction=Direction.LONG, entry_price=dec(100), entry_level_id="L0",
        dca_levels=[], dca_count=2, at_index=59,
    )
    assert len(rungs) == 1 and rungs[0].size_fraction == dec(1)
    assert any("dca_ladder_short" in n for n in notes)


def test_low_conviction_arms_the_dca_but_sizes_it_to_zero(cfg: Config) -> None:
    """TBOT1-C6 / SPEC.md §8.2 — the bot takes the first entry only."""
    rungs, notes = PL.build_entry_ladder(
        cfg, direction=Direction.LONG, entry_price=dec(100), entry_level_id="L0",
        dca_levels=[level("L1", 98.0)], dca_count=1, at_index=59,
        conviction=Conviction.LOW,
    )
    assert [r.size_fraction for r in rungs] == [dec(1), dec(0)]
    assert PL.blended_entry(rungs) == dec(100)
    assert any("sized_to_zero" in n for n in notes)


def test_blended_entry_filled_only_is_the_realised_average(cfg: Config) -> None:
    """CF-18 — every downstream calculation uses the average entry, never entry 1."""
    rungs, _ = PL.build_entry_ladder(
        cfg, direction=Direction.LONG, entry_price=dec(100), entry_level_id="L0",
        dca_levels=[level("L1", 98.0)], dca_count=1, at_index=59,
    )
    assert PL.blended_entry(rungs, filled_only=True) == dec(0)
    rungs[0].filled = True
    rungs[0].fill_price = dec("100.1")
    assert PL.blended_entry(rungs, filled_only=True) == dec("100.1")


# ======================================================================= entry family (CF-16)


def test_order_type_is_limit_except_for_the_trigger_family(cfg: Config) -> None:
    assert PL.order_type_for_family(cfg, EntryFamily.RETEST) is OrderType.LIMIT
    assert PL.order_type_for_family(cfg, EntryFamily.FLIP_PENDING) is OrderType.LIMIT
    assert PL.order_type_for_family(cfg, EntryFamily.TRIGGER) is OrderType.MARKET
    never = cfg.with_overrides(allow_market_orders="never")
    assert PL.order_type_for_family(never, EntryFamily.TRIGGER) is OrderType.LIMIT


def test_disabled_entry_family_yields_no_plan(uncapped: Config) -> None:
    cfg = uncapped.with_overrides(entry_family_retest_enabled=False)
    build = PL.build_plan(_inputs(cfg), cfg)
    assert not build.ok
    assert any("entry_family_disabled" in r for r in build.reasons)


# ======================================================================= stop (CF-14)


def test_stop_anchors_on_the_wick_and_applies_the_buffer(cfg: Config) -> None:
    rows = flat_series(40)
    rows[30] = (100.0, 100.2, 99.4, 100.0)       # a modest lower wick
    s = make_series(rows)
    d = PL.place_stop(
        s, cfg, direction=Direction.LONG, bar_index=30, reference_price=dec(100), at_index=39
    )
    assert not d.anchor.used_body
    assert d.anchor.price == dec("99.4")
    # buffer = stop_buffer_atr * ATR; ATR is not exactly 1.0 here, so compare against P19 itself
    assert money_close(d.buffer, P.stop_buffer(s, cfg, 39))
    assert money_close(d.price, dec("99.4") - d.buffer)


def test_stop_falls_back_to_the_body_on_an_oversized_wick(cfg: Config) -> None:
    """S6-R18 — the rejected $0.60 wick on a ~$17 coin: > ``stop_wick_max_pct`` (3 %)."""
    rows = flat_series(40)
    rows[30] = (100.0, 100.2, 95.0, 100.0)       # a 5 % lower wick
    s = make_series(rows)
    d = PL.place_stop(
        s, cfg, direction=Direction.LONG, bar_index=30, reference_price=dec(100), at_index=39
    )
    assert d.anchor.used_body
    assert d.anchor.price == dec("100.0")        # body_low
    assert any("stop_wick_max_pct" in r for r in d.reasons)


def test_stop_never_anchors_on_a_capitulation_wick(cfg: Config) -> None:
    """P12 / TBOT1-R6, and the TBOT1-C4 split: still a valid *entry* target, never a stop anchor."""
    rows = flat_series(40)
    rows[30] = (100.0, 100.05, 95.0, 100.0)
    vols = [1.0] * 40
    vols[30] = 100.0                              # blows the capitulation volume test open
    s = make_series(rows, volumes=vols)
    loose = cfg.with_overrides(stop_wick_max_pct=99.0)   # isolate the P12 branch
    assert P.is_capitulation_wick(s, loose, 30, "lower")
    d = PL.place_stop(
        s, loose, direction=Direction.LONG, bar_index=30, reference_price=dec(100), at_index=39
    )
    assert d.anchor.used_body
    assert any("capitulation" in r for r in d.reasons)


def test_stop_is_moved_inside_an_independent_opposing_level(cfg: Config) -> None:
    """CF-14 step 3 / S5-R25 / S6-R19 — never straddle a level that is its own trade."""
    rows = flat_series(40)
    rows[30] = (100.0, 100.2, 99.4, 100.0)
    s = make_series(rows)
    opposing = level("OPP", 99.6)
    d = PL.place_stop(
        s, cfg, direction=Direction.LONG, bar_index=30, reference_price=dec(100),
        opposing_levels=[opposing], at_index=39,
    )
    assert d.clipped_to_level_id == "OPP"
    assert d.price > dec("99.6")
    assert any("stop_moved_inside_opposing_level" in r for r in d.reasons)


def test_opposing_level_clip_is_switchable(cfg: Config) -> None:
    rows = flat_series(40)
    rows[30] = (100.0, 100.2, 99.4, 100.0)
    s = make_series(rows)
    off = cfg.with_overrides(stop_never_beyond_opposing_level=False, min_stop_pct=0.0)
    d = PL.place_stop(
        s, off, direction=Direction.LONG, bar_index=30, reference_price=dec(100),
        opposing_levels=[level("OPP", 99.6)], at_index=39,
    )
    assert d.clipped_to_level_id is None


def test_stop_is_widened_to_the_min_stop_pct_floor(cfg: Config) -> None:
    """S7-C8's "too tight" case; the remedy is to widen, never to tighten (S5-R24)."""
    rows = flat_series(40)
    rows[30] = (100.0, 100.5, 99.95, 100.0)
    s = make_series(rows)
    tight = cfg.with_overrides(stop_buffer_atr=0.0)
    d = PL.place_stop(
        s, tight, direction=Direction.LONG, bar_index=30, reference_price=dec(100), at_index=39
    )
    assert d.widened_to_min_stop_pct
    assert money_close(d.stop_pct, dec(tight.min_stop_pct))


def test_the_widening_flag_survives_onto_the_plan(cfg: Config) -> None:
    """``place_stop`` deciding it is not enough; the plan has to carry the decision forward.

    ``StopDecision.widened_to_min_stop_pct`` and ``.clipped_to_level_id`` were computed correctly
    and then dropped: ``PlanBuild`` held the decision, ``TradePlan`` did not, and nothing in the
    package read either. The cost was not abstract - asking "was this stop inside the CF-06
    floor, and which rule put it there" of 27 saved trades needed an instrumented re-run of the
    whole backtest, because the record could not answer it.

    Both halves are asserted against a build that genuinely sets the flag. An equality check on
    a build where the floor never fires reads ``False == False`` and would pass against a plan
    field hard-coded to ``False``, which is the mistake this docstring exists to stop someone
    repeating: ``min_stop_pct`` is raised to 5.0 here precisely so the flag is **true**.
    """
    wide = cfg.with_overrides(min_stop_pct=5.0)
    build = PL.build_plan(_inputs(wide), wide)
    assert build.stop is not None and build.plan is not None
    assert build.stop.widened_to_min_stop_pct, (
        "fixture must trigger the CF-06 floor or this test proves nothing")

    assert build.plan.stop_widened_to_min_pct is True
    assert build.plan.stop_clipped_to_level_id == build.stop.clipped_to_level_id

    # ...and false when the floor does not fire, so the field tracks the decision rather than
    # being true by construction.
    quiet = PL.build_plan(_inputs(cfg), cfg)
    assert quiet.stop is not None and quiet.plan is not None
    assert quiet.stop.widened_to_min_stop_pct is False
    assert quiet.plan.stop_widened_to_min_pct is False


def test_short_stop_sits_above_the_entry(cfg: Config) -> None:
    rows = flat_series(40)
    rows[30] = (100.0, 100.6, 99.8, 100.0)
    s = make_series(rows)
    d = PL.place_stop(
        s, cfg, direction=Direction.SHORT, bar_index=30, reference_price=dec(100), at_index=39
    )
    assert d.price > dec(100)
    assert d.anchor.side == "upper"


def test_duplicate_stop_offset_sits_further_out(cfg: Config) -> None:
    """S4-R34 — two orders ``duplicate_stop_offset_bps`` apart; the backtest uses the first."""
    rows = flat_series(40)
    rows[30] = (100.0, 100.2, 99.4, 100.0)
    s = make_series(rows)
    d = PL.place_stop(
        s, cfg, direction=Direction.LONG, bar_index=30, reference_price=dec(100), at_index=39
    )
    assert d.duplicate_price(cfg) < d.price


def test_stop_anchor_index_is_validated(cfg: Config) -> None:
    s = make_series(flat_series(10))
    with pytest.raises(PL.PlanError):
        PL.stop_anchor(s, cfg, direction=Direction.LONG, bar_index=99)


# ======================================================================= wide stop (CF-06)


def _wide_stop(cfg: Config, s: Series, pct: float) -> PL.StopDecision:
    ref = dec(100)
    price = ref * (dec(1) - dec(pct) / dec(100))
    return PL.StopDecision(
        price=price,
        anchor=PL.StopAnchor(price, 30, "lower", False),
        reference_price=ref,
        buffer=dec("0.15"),
    )


def test_narrow_stop_keeps_leverage(cfg: Config) -> None:
    s = make_series(flat_series(40))
    vd = PL.escalate_wide_stop(
        s, cfg, direction=Direction.LONG, stop=_wide_stop(cfg, s, 5.0),
        preferred_vehicle=Vehicle.LEVERAGE,
    )
    assert vd.vehicle is Vehicle.LEVERAGE and not vd.skip and not vd.downgraded


def test_wide_stop_downgrades_to_spot(cfg: Config) -> None:
    """CF-06 step 2 / TBOT1-R7 — take it on spot rather than cancelling."""
    s = make_series(flat_series(40))
    vd = PL.escalate_wide_stop(
        s, cfg, direction=Direction.LONG, stop=_wide_stop(cfg, s, 18.0),
        preferred_vehicle=Vehicle.LEVERAGE, spot_allowed=True,
    )
    assert vd.vehicle is Vehicle.SPOT and vd.downgraded and not vd.skip
    assert any("max_stop_pct_leverage" in r for r in vd.reasons)


def test_wide_stop_downgrades_to_capped_leverage_when_spot_is_excluded(cfg: Config) -> None:
    s = make_series(flat_series(40))
    vd = PL.escalate_wide_stop(
        s, cfg, direction=Direction.LONG, stop=_wide_stop(cfg, s, 18.0),
        preferred_vehicle=Vehicle.LEVERAGE, spot_allowed=False, leverage_allowed=True,
    )
    assert vd.vehicle is Vehicle.LEVERAGE and vd.downgraded
    assert vd.max_leverage == dec(cfg.leverage_downgrade_max_multiple)


def test_wide_stop_skips_when_nothing_can_be_downgraded(cfg: Config) -> None:
    """CF-06 step 3 — S7-R7's rejected 18 % stop, S7-R26's rejected 17 % SFP stop."""
    s = make_series(flat_series(40))
    skip_only = cfg.with_overrides(wide_stop_policy="skip")
    vd = PL.escalate_wide_stop(
        s, skip_only, direction=Direction.LONG, stop=_wide_stop(cfg, s, 18.0),
        preferred_vehicle=Vehicle.LEVERAGE, spot_allowed=False,
    )
    assert vd.skip


def test_ltf_tightening_runs_before_any_downgrade(cfg: Config) -> None:
    """CF-06 step 1 — drop ``stop_tighten_tf_steps`` and re-anchor (S4-R16, S8 ``[01:21:46]``)."""
    s = make_series(flat_series(40))
    ltf_rows = flat_series(40, price=100.0)
    ltf_rows[30] = (100.0, 100.2, 97.0, 100.0)   # a 3 %-ish anchor on the lower timeframe
    ltf = make_series(ltf_rows, tf="1H")
    vd = PL.escalate_wide_stop(
        s, cfg, direction=Direction.LONG, stop=_wide_stop(cfg, s, 18.0),
        preferred_vehicle=Vehicle.LEVERAGE, ltf_series=ltf, ltf_bar_index=30,
    )
    assert vd.tightened and not vd.downgraded and not vd.skip
    assert vd.stop.stop_pct < dec(cfg.max_stop_pct_leverage)


def test_missing_ltf_series_is_recorded_not_silently_skipped(cfg: Config) -> None:
    s = make_series(flat_series(40))
    vd = PL.escalate_wide_stop(
        s, cfg, direction=Direction.LONG, stop=_wide_stop(cfg, s, 18.0),
        preferred_vehicle=Vehicle.LEVERAGE, spot_allowed=True,
    )
    assert any("ltf_tightening_unavailable" in r for r in vd.reasons)


def test_the_leverage_stop_ceiling_does_not_bind_spot(cfg: Config) -> None:
    """S7-R7 / S6 ``[00:08:04]`` — 9 % is a leverage constraint; spot has no liquidation."""
    s = make_series(flat_series(40))
    vd = PL.escalate_wide_stop(
        s, cfg, direction=Direction.LONG, stop=_wide_stop(cfg, s, 25.0),
        preferred_vehicle=Vehicle.SPOT,
    )
    assert vd.vehicle is Vehicle.SPOT and not vd.skip


# ======================================================================= take-profits (CF-27/28)


def test_tp_count_by_trade_class(cfg: Config) -> None:
    assert PL.tp_count_for(cfg, TradeClass.SWING) == 3    # stated: "TP1 40% TP2 30% TP3 30%"
    assert PL.tp_count_for(cfg, TradeClass.SCALP) == 3
    assert PL.tp_count_for(cfg, TradeClass.COUNTER_TREND) == 3     # a scalp after CF-03
    assert PL.tp_count_for(cfg, TradeClass.PRICE_DISCOVERY) == 5
    # S5-R26 floor: config.py already refuses tp_count_swing < tp_min_count, and tp_count_for
    # re-applies the floor so a hand-built Config cannot slip a 1-TP plan through.
    for tc in TradeClass:
        assert PL.tp_count_for(cfg, tc) >= cfg.tp_min_count == 2


def test_tp_splits_are_front_loaded(cfg: Config) -> None:
    assert PL.tp_split(cfg, 2) == (dec("0.5"), dec("0.5"))
    assert PL.tp_split(cfg, 3) == (dec("0.4"), dec("0.3"), dec("0.3"))
    assert sum(PL.tp_split(cfg, 5)) == dec(1)
    with pytest.raises(PL.PlanError):
        PL.tp_split(cfg, 6)


def test_take_profits_sit_on_structural_levels_in_the_trade_direction(cfg: Config) -> None:
    tps, notes = PL.select_take_profits(
        cfg, direction=Direction.LONG,
        levels=[level("below", 95.0), level("t1", 104.0), level("t2", 110.0),
                level("t3", 120.0)],
        average_entry=dec(100), trade_class=TradeClass.SWING, at_index=59,
    )
    assert [t.price for t in tps] == [dec(104.0), dec(110.0), dec(120.0)]
    assert [t.level_id for t in tps] == ["t1", "t2", "t3"]
    # tp_count_swing is 3 (his stated default), so tp_split_3 applies: 40/30/30
    assert [t.size_fraction for t in tps] == [dec("0.4"), dec("0.3"), dec("0.3")]


def test_take_profits_respect_the_min_separation_and_prefer_touch_count(cfg: Config) -> None:
    """Two levels contending for the same slot: the one with more touches wins (§8.7)."""
    tps, _ = PL.select_take_profits(
        cfg, direction=Direction.LONG,
        levels=[level("thin", 104.0, touches=2), level("thick", 104.1, touches=7),
                level("far", 112.0)],
        average_entry=dec(100), trade_class=TradeClass.SWING, at_index=59,
    )
    assert [t.level_id for t in tps] == ["thick", "far"]


def test_take_profits_are_capped_at_the_measured_move_target(cfg: Config) -> None:
    """S4 ``[00:53:25]`` / S5-R39 — the measured final TP is theoretical."""
    tps, notes = PL.select_take_profits(
        cfg, direction=Direction.LONG,
        levels=[level("t1", 104.0), level("t2", 108.0), level("way_out", 200.0)],
        average_entry=dec(100), trade_class=TradeClass.SWING, at_index=59,
        measured_move_target=dec(110),
    )
    # The rule under test is unchanged: `way_out` at 200 sits beyond the measured move and is
    # dropped.  What changed is tp_count_swing 2 -> 3 (his stated "TP1 40% TP2 30% TP3 30%"):
    # only two structural levels survive the cap, so the measured move itself becomes the third
    # target, explicitly labelled rather than silently invented.
    assert [t.price for t in tps] == [dec(104.0), dec(108.0), dec(110)]
    assert [t.level_id for t in tps] == ["t1", "t2", None]
    assert any("measured_move_target_dropped" in n for n in notes)
    assert any("measured_move_target_used_as_final_tp" in n for n in notes)


def test_too_few_structural_levels_means_no_plan(cfg: Config) -> None:
    """S5-R26 — never one entry and one TP; the plan is abandoned rather than shipped short."""
    tps, notes = PL.select_take_profits(
        cfg, direction=Direction.LONG, levels=[level("t1", 104.0)],
        average_entry=dec(100), trade_class=TradeClass.SWING, at_index=59,
    )
    assert tps == []
    assert any("tp_min_count_not_met" in n for n in notes)


def test_short_take_profits_step_down(cfg: Config) -> None:
    tps, _ = PL.select_take_profits(
        cfg, direction=Direction.SHORT,
        levels=[level("up", 110.0), level("t1", 96.0), level("t2", 90.0)],
        average_entry=dec(100), trade_class=TradeClass.SWING, at_index=59,
    )
    assert [t.price for t in tps] == [dec(96.0), dec(90.0)]


# ======================================================================= build_plan end-to-end


def _inputs(cfg: Config, **kw) -> PL.PlanInputs:
    rows = flat_series(60)
    # The stop anchor must sit below the whole ladder: a 1.6 % lower wick, so the CF-14 wick
    # anchor is used rather than the S6-R18 body fallback.
    rows[50] = (95.5, 95.6, 94.0, 95.5)
    s = make_series(rows)
    pf = PortfolioState(equity_usd=EQUITY, now=T0 + timedelta(days=10))
    budget = kw.pop("budget", None) or sizing_budget(
        cfg, pf, trade_class=TradeClass.SWING, vehicle=Vehicle.LEVERAGE
    )
    defaults = dict(
        setup=make_setup(),
        series=s,
        budget=budget,
        entry_level=level("L0", 100.0),
        stop_anchor_index=50,
        dca_levels=[level("L1", 97.0)],
        tp_levels=[level("T1", 106.0, LevelKind.RESISTANCE, 4),
                   level("T2", 115.0, LevelKind.RESISTANCE, 3)],
        at_index=59,
        zone=make_zone(1.0),
    )
    defaults.update(kw)
    return PL.PlanInputs(**defaults)


def test_build_plan_end_to_end(uncapped: Config) -> None:
    build = PL.build_plan(_inputs(uncapped), uncapped)
    assert build.ok, build.reasons
    plan = build.plan
    assert plan is not None
    assert len(plan.entries) == 2 and plan.entries[0].size_fraction == dec("0.39")
    assert len(plan.take_profits) == 2
    assert plan.stop_price < plan.planned_average_entry
    assert plan.vehicle is Vehicle.LEVERAGE
    assert plan.rr_to_tp1 > 0 and plan.expected_move_pct > 0
    assert plan.invalidation_level_id == "L0"
    assert "CF-14" in plan.source_ids and "CF-18" in plan.source_ids
    assert build.consistency is not None and build.consistency.ok
    assert money_close(build.consistency.realised_risk_pct, dec(uncapped.max_loss_pct_swing))


def test_build_plan_is_deterministic(uncapped: Config) -> None:
    """INTERFACES.md §9 invariant 9 — identical inputs, identical plans."""
    a = PL.build_plan(_inputs(uncapped), uncapped).plan
    b = PL.build_plan(_inputs(uncapped), uncapped).plan
    assert a is not None and b is not None
    assert (a.id, a.stop_price, a.qty_total, a.planned_average_entry) == (
        b.id, b.stop_price, b.qty_total, b.planned_average_entry
    )
    assert [e.price for e in a.entries] == [e.price for e in b.entries]
    assert [t.price for t in a.take_profits] == [t.price for t in b.take_profits]


def test_build_plan_refuses_a_vetoed_setup(uncapped: Config) -> None:
    """INTERFACES.md §9 invariant 5 — never force a setup; an empty result is valid."""
    build = PL.build_plan(_inputs(uncapped, setup=make_setup(vetoes=("htf_veto",))), uncapped)
    assert not build.ok
    assert build.reasons == ("setup_vetoed:htf_veto",)


def test_build_plan_refuses_when_the_tp_ladder_is_too_short(uncapped: Config) -> None:
    build = PL.build_plan(
        _inputs(uncapped, tp_levels=[level("T1", 106.0, LevelKind.RESISTANCE)]), uncapped
    )
    assert not build.ok
    assert any("tp_min_count_not_met" in r for r in build.reasons)


def test_spot_plan_carries_a_synthetic_stop_and_the_close_then_flip_exit(uncapped: Config) -> None:
    """CF-05 — spot has no resting stop; the synthetic one exists only for sizing (**ours**)."""
    build = PL.build_plan(_inputs(uncapped, leverage_allowed=False), uncapped)
    assert build.ok, build.reasons
    plan = build.plan
    assert plan is not None
    assert plan.vehicle is Vehicle.SPOT
    assert plan.stop_is_synthetic
    assert plan.spot_exit_rule == uncapped.spot_exit_mode == "close_below_level_then_flip"
    assert plan.leverage == dec(1)


def test_deep_zone_earns_a_second_dca(uncapped: Config) -> None:
    """S5-R22 / CF-17 — a wide zone gets two DCAs, a tight one gets one."""
    build = PL.build_plan(
        _inputs(
            uncapped,
            zone=make_zone(2.5),
            dca_levels=[level("L1", 97.0), level("L2", 96.0)],
        ),
        uncapped,
    )
    assert build.ok, build.reasons
    assert build.plan is not None
    assert [r.size_fraction for r in build.plan.entries] == [
        dec("0.15"), dec("0.325"), dec("0.525")
    ]


def test_single_entry_play_has_no_dca(uncapped: Config) -> None:
    """S8-R11 — never DCA a trend-line/breakdown play: one entry, one stop, multiple TPs."""
    build = PL.build_plan(_inputs(uncapped, single_entry_play=True), uncapped)
    assert build.ok, build.reasons
    assert build.plan is not None
    assert len(build.plan.entries) == 1
    assert build.plan.entries[0].size_fraction == dec(1)


def test_zone_pmt_price_beats_the_bare_level_price(uncapped: Config) -> None:
    """P20 / S5-R23 — the entry sits at the point of most touch inside the box."""
    zone = make_zone(1.0)
    zone.entry_price_pmt = dec("99.6")
    build = PL.build_plan(_inputs(uncapped, zone=zone), uncapped)
    assert build.ok, build.reasons
    assert build.plan is not None
    assert build.plan.entries[0].price == dec("99.6")


def test_size_and_stop_computed_from_first_entry_alternative(uncapped: Config) -> None:
    """CF-18 — the default measures everything from the blended average; ``"first_entry"`` is the
    recorded alternative and must move the stop reference *and* the size with it."""
    cfg = uncapped
    alt = cfg.with_overrides(size_and_stop_computed_from="first_entry")
    rungs = [
        EntryRung(index=0, price=dec(100), size_fraction=dec("0.3"), kind="entry", level_id="L0"),
        EntryRung(index=1, price=dec(97), size_fraction=dec("0.7"), kind="dca", level_id="L1"),
    ]
    assert PL.sizing_reference(cfg, rungs) == PL.blended_entry(rungs)
    assert PL.sizing_reference(alt, rungs) == dec(100)

    a = PL.build_plan(_inputs(cfg), cfg).plan
    b = PL.build_plan(_inputs(alt), alt).plan
    assert a is not None and b is not None
    assert a.planned_average_entry == b.planned_average_entry     # the field is still the average
    assert b.qty_total != a.qty_total                             # but the size is not


def test_empty_series_is_a_caller_error(uncapped: Config) -> None:
    empty = make_series(flat_series(1)).slice(0, 0)
    with pytest.raises(PL.PlanError):
        PL.build_plan(_inputs(uncapped, series=empty), uncapped)


# ======================================================================= F1 nested zone geometry


def banded_zone(*, band_bottom: float | None = 98.2, pmt: float = 100.2) -> Zone:
    """A demand zone whose **body core** is ``(99.0, 100.5)`` plus the optional F1 outer band.

    ``pmt`` is the P20 point-of-most-touch inside the *body* box — the price the entry ladder is
    supposed to rest on.  ``band_bottom`` is the wick extreme the *stop* is supposed to clear;
    ``None`` reproduces a zone built with ``zone_wick_band_enabled`` off, which is every zone the
    detector builds under the default config.
    """
    zone = make_zone(1.0)
    zone.entry_price_pmt = dec(pmt)
    if band_bottom is not None:
        zone.wick_band_top = zone.box_top          # F1: the band shares the near edge
        zone.wick_band_bottom = dec(band_bottom)
    return zone


def _f1_inputs(cfg: Config, zone: Zone, **kw) -> PL.PlanInputs:
    """Inputs whose CF-14 anchor sits just **inside** the F1 band, so the band actually binds.

    Bar 50 carries a 0.6-wide lower wick to 98.6 — the bottom of the zone's own body core is
    99.0, so without the band the stop lands at 98.45 (98.6 less the 0.15-ATR buffer), which is
    above a band bottom of 98.2.  That is the case the F1 reading has to change.
    """
    rows = flat_series(60)
    rows[50] = (99.2, 99.3, 98.6, 99.2)
    series = make_series(rows)
    defaults = dict(
        setup=make_setup(),
        series=series,
        # The CF-02 notional ceiling is pushed out of the way so the CF-01 risk cap stays the
        # binding constraint: otherwise a clamped notional hides the size change a wider stop
        # is supposed to cause.
        budget=big_budget(),
        entry_level=level("L0", 100.2),
        stop_anchor_index=50,
        dca_levels=[level("L1", 99.4)],
        tp_levels=[level("T1", 106.0, LevelKind.RESISTANCE, 4),
                   level("T2", 115.0, LevelKind.RESISTANCE, 3)],
        at_index=59,
        zone=zone,
    )
    defaults.update(kw)
    return PL.PlanInputs(**defaults)


def test_a_zone_built_under_the_default_config_carries_no_band(uncapped: Config) -> None:
    assert uncapped.zone_wick_band_enabled is False
    zone = banded_zone(band_bottom=None)
    assert not zone.has_wick_band
    assert zone.wick_band_stop_edge is None


def test_plan_is_unchanged_when_the_zone_carries_no_band(uncapped: Config) -> None:
    """F1 off-by-default equivalence at the plan level, not only the detector's.

    ``zone_wick_band_enabled`` is off by default, so no detector-built zone carries a band, and
    the CF-14 band argument is inert when it is not supplied.  The stop the plan then places is
    the **F6** zone-fraction stop (the setup hangs off a zone), not the P19 fallback — that is
    the pass-2 default change, and it is what the equivalence is measured against here.
    """
    zone = banded_zone(band_bottom=None)
    series = _f1_inputs(uncapped, zone).series
    bare = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59)
    nulled = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                           reference_price=dec(100), at_index=59, wick_band_edge=None)
    assert bare.price == nulled.price and bare.reasons == nulled.reasons

    from_zone = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                              reference_price=dec(100), at_index=59,
                              zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth)
    plan = PL.build_plan(_f1_inputs(uncapped, banded_zone(band_bottom=None)), uncapped).plan
    assert plan is not None
    assert "F1" not in plan.source_ids
    assert "F6" in plan.source_ids
    assert plan.stop_price == from_zone.price
    assert from_zone.price != bare.price          # F6 changed the number; F1 did not


def test_entries_come_from_the_body_box_and_the_stop_from_the_wick_band(
    uncapped: Config,
) -> None:
    """**F1** — *"entries price off the body box; the stop goes beyond the wick band."*

    This is the reconciliation the frames buy: *"draw your boxes on candle bodies"* governs where
    the ladder rests, *"usually wicks are going to give you that entry point"* survives as the
    P20 point-of-most-touch **inside that body box**, and the wick extent is a second, outer
    object that only the stop reads.
    """
    zone = banded_zone(band_bottom=98.2, pmt=100.2)
    build = PL.build_plan(_f1_inputs(uncapped, zone), uncapped)
    assert build.ok, build.reasons
    plan = build.plan
    assert plan is not None

    # Entry: the P20 price inside the BODY box, untouched by the band.
    assert plan.entries[0].price == dec("100.2")
    assert zone.box_bottom <= plan.entries[0].price <= zone.box_top

    # Stop: strictly beyond the band's far edge, and beyond where the body box alone put it.
    bare = PL.build_plan(_f1_inputs(uncapped, banded_zone(band_bottom=None)), uncapped).plan
    assert bare is not None
    assert plan.stop_price < dec("98.2") < bare.stop_price
    assert "F1" in plan.source_ids


def test_only_the_stop_moves_when_the_band_appears(uncapped: Config) -> None:
    """Turning F1 on must not disturb the entry ladder — only the stop, and the size that
    follows from it (CF-01: a wider stop buys less quantity)."""
    bare = PL.build_plan(_f1_inputs(uncapped, banded_zone(band_bottom=None)), uncapped).plan
    band = PL.build_plan(_f1_inputs(uncapped, banded_zone(band_bottom=98.2)), uncapped).plan
    assert bare is not None and band is not None
    assert [e.price for e in bare.entries] == [e.price for e in band.entries]
    assert [e.size_fraction for e in bare.entries] == [e.size_fraction for e in band.entries]
    assert bare.planned_average_entry == band.planned_average_entry
    assert band.stop_price < bare.stop_price
    assert band.qty_total < bare.qty_total


def test_the_band_widens_the_stop_and_records_why(uncapped: Config) -> None:
    series = _f1_inputs(uncapped, banded_zone()).series
    without = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                            reference_price=dec(100), at_index=59)
    with_band = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                              reference_price=dec(100), at_index=59,
                              wick_band_edge=dec("98.2"))
    assert with_band.price < without.price < dec("98.6")
    assert with_band.price < dec("98.2")
    assert any("stop_beyond_zone_wick_band" in r for r in with_band.reasons)
    assert not any("stop_beyond_zone_wick_band" in r for r in without.reasons)


def test_a_band_inside_the_anchor_never_tightens_the_stop(uncapped: Config) -> None:
    """A stop is only ever widened here (S5-R24): a band shallower than the anchor is a no-op."""
    series = _f1_inputs(uncapped, banded_zone()).series
    without = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                            reference_price=dec(100), at_index=59)
    shallow = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                            reference_price=dec(100), at_index=59,
                            wick_band_edge=dec("99.5"))
    assert shallow.price == without.price
    assert not any("stop_beyond_zone_wick_band" in r for r in shallow.reasons)


def test_short_side_band_pushes_the_stop_up(uncapped: Config) -> None:
    rows = flat_series(60)
    rows[50] = (100.8, 101.4, 100.7, 100.8)          # an upper wick for the CF-14 anchor
    series = make_series(rows)
    without = PL.place_stop(series, uncapped, direction=Direction.SHORT, bar_index=50,
                            reference_price=dec(100), at_index=59)
    with_band = PL.place_stop(series, uncapped, direction=Direction.SHORT, bar_index=50,
                              reference_price=dec(100), at_index=59,
                              wick_band_edge=dec("101.8"))
    assert with_band.price > without.price > dec(100)
    assert with_band.price > dec("101.8")
    assert any("stop_beyond_zone_wick_band" in r for r in with_band.reasons)


def test_the_detector_and_the_plan_agree_on_which_edge_is_which() -> None:
    """The two halves of the F1 reading, stated as one assertion on the model."""
    demand = banded_zone(band_bottom=98.2)
    assert demand.outer_edge == demand.box_top                 # entries: the body core
    assert demand.wick_band_stop_edge == dec("98.2")           # stops: the outer band
    supply = make_zone(1.0)
    supply.side = ZoneSide.SUPPLY
    supply.wick_band_top, supply.wick_band_bottom = dec("101.4"), supply.box_bottom
    assert supply.outer_edge == supply.box_bottom
    assert supply.wick_band_stop_edge == dec("101.4")


# =========================================================================== F6 (pass 2)
#
# FRAME_FINDINGS.md **F6** — the stop distance scales with the ZONE HEIGHT, not with a price
# percentage and not with an ATR multiple.  Three independent frames, three pairs, three
# timeframes, two exchanges, each with a position tool and a zone box on screen:
#
#   | frame        | chart                | stop below the box bottom | same, as % of entry |
#   | TBOT1 4:11   | BTCUSDT.P 1H Binance | 0.48 x box height         | 0.66 %              |
#   | TBOT1 1:09:19| OMUSDT.P  1H Binance | 0.49 x box height         | 2.70 %              |
#   | S8 1:28:33   | SOLUSDT.P 4H MEXC    | 0.58 x box height         | 0.81 %              |
#
# The fraction clusters at 0.48-0.58 (mean ~0.52); the percentage spans 0.66-2.70 %.  That is the
# whole argument for ``stop_buffer_zone_fraction`` (0.5) over ``stop_buffer_atr`` for any stop
# that hangs off a zone.
#
# DISPUTED.  The independent measurement pass (docs/measurement/00-MASTER.txt Part 2) WITHDREW
# this rule from these same three frames, on the grounds that the fraction depends on which band
# is nominated as "the zone" - the same frames yield 0.042 to 4.145 under a different nomination.
#
# The frames CANNOT be reproduced under test, and the test that claimed to do so was circular:
# ``Frame`` builds each box FROM the ratio (``height = distance / fraction``), so asserting the
# ratio back is a tautology.  It passed unchanged with every frame price scaled 10x.  Two of the
# three frames have no independent price anchor either - S8 1:28:33's entry is a nominal 140.00
# (measured elsewhere as 170.367) and TBOT1 4:11's entry is back-derived from a spoken round
# number.  The ``Frame`` fixtures below are therefore a SCALE CARRIER for the three ratios and
# nothing more; they are not frame reproductions.  See
# ``test_f6_frames_are_a_scale_carrier_not_a_reproduction``.

class Frame:
    """One frame's geometry, in prices.

    Only two things were *measured* off each frame: the stop's distance below the box bottom as a
    fraction of the box height, and that same distance as a percentage of the entry.  Everything
    below is those two ratios plus one price anchor, so the absolute numbers are only a scale
    carrier — the assertions are all ratio assertions.

    Price anchors, and how honest each one is:

    * **TBOT1 4:11** — ``stop loss below 92K`` is spoken on the frame (TBOT1 ``[00:04:11]``), so
      the observed stop is 92 000 and the entry follows from the two ratios: 93 911.  That entry
      also reproduces the frame's own stop label as **2.04 %** of entry — ``(1 + f) / f`` times
      the 0.66 %.  The rendered label reads *1.84 %*; the middle glyph is not legible at 1080p
      and the arithmetic says 2.04 %, so 2.04 % is what is recorded (FRAME_FINDINGS.md pass 2).
      Cross-check: CONFLICTS.md CF-14 already records this trade from the transcript as
      "BTC 93.5K entry / stop below 92K" (TBOT1-A14) — 0.4 % from this reconstruction.
    * **TBOT1 1:09:19** — ``Scalp long 524ish. Stop loss 509`` is spoken at ``[01:09:17]``, two
      seconds before the frame, and 509 is exactly where the 0.49 x box height lands from a box
      bottom at the entry.  Read as the same trade; that identification is an **inference**.
    * **S8 1:28:33** — no price is readable or spoken (``stop loss somewhere here``), so the
      entry is a nominal 140.00 at SOL's scale.  Only the ratios carry meaning here.
    """

    def __init__(self, name: str, entry: float, fraction: float, pct_of_entry: float,
                 entry_edge: str, observed_stop: float) -> None:
        self.name = name
        self.entry = dec(entry)
        self.fraction = dec(str(fraction))               # measured off the frame
        self.pct_of_entry = dec(str(pct_of_entry))       # measured off the frame
        # distance from the box bottom down to the stop, from the second measurement
        self.distance = self.entry * self.pct_of_entry / dec(100)
        self.height = self.distance / self.fraction      # ... and the first gives the box height
        # F7: the entry sits on a box EDGE — the top edge for these two longs, the bottom edge
        # for the OM scalp (the DOGE 2H short read 1.00 of the way down the box).
        self.box_bottom = self.entry - self.height if entry_edge == "top" else self.entry
        self.box_top = self.box_bottom + self.height
        self.observed_stop = dec(str(observed_stop))


FRAMES = [
    Frame("TBOT1 4:11 BTCUSDT.P 1H Binance", entry=93_911.0, fraction=0.48,
          pct_of_entry=0.66, entry_edge="top", observed_stop=92_000.0),
    Frame("TBOT1 1:09:19 OMUSDT.P 1H Binance", entry=524.0, fraction=0.49,
          pct_of_entry=2.70, entry_edge="bottom", observed_stop=509.0),
    Frame("S8 1:28:33 SOLUSDT.P 4H MEXC", entry=140.0, fraction=0.58,
          pct_of_entry=0.81, entry_edge="top", observed_stop=136.91),
]


def _frame_zone(frame: Frame) -> Zone:
    zone = make_zone(1.0)
    zone.box_top, zone.box_bottom = frame.box_top, frame.box_bottom
    zone.midpoint = (frame.box_top + frame.box_bottom) / dec(2)
    return zone


def _frame_stop(frame: Frame, cfg: Config) -> PL.StopDecision:
    series = make_series(flat_series(60, price=float(frame.entry)))
    zone = _frame_zone(frame)
    return PL.place_stop(
        series, cfg,
        direction=Direction.LONG,
        bar_index=50,
        reference_price=frame.entry,
        at_index=59,
        zone_stop_edge=zone.body_stop_edge,
        zone_height=zone.depth,
    )


@pytest.mark.parametrize("fraction,expected", [
    ("0.0", "99.00"),      # snap to the box edge - the measurement pass's own position
    ("0.25", "98.625"),
    ("0.5", "98.25"),      # current default
    ("0.58", "98.13"),     # deepest of the three disputed readings
])
def test_zone_fraction_rule_places_stop_at_the_configured_fraction(
    fraction: str, expected: str, uncapped: Config,
) -> None:
    """The rule itself, on a box whose coordinates are NOT derived from the fraction.

    ``make_zone(1.0)`` gives a body core of 99.00 .. 100.50, so the height is a fixed 1.50 and
    the expected stop is ``99.00 - fraction * 1.50`` - arithmetic the test states independently
    rather than reconstructing from the answer.  This is what the old
    ``test_f6_frame_is_reproduced_by_the_zone_fraction_rule`` should have been doing; it instead
    built the box from the ratio and so could only ever pass.
    """
    cfg = uncapped.with_overrides(stop_buffer_zone_fraction=float(fraction))
    series = make_series(flat_series(60))
    zone = make_zone(1.0)
    assert (zone.box_top, zone.box_bottom) == (dec("100.5"), dec("99.0"))   # fixture pinned
    stop = PL.place_stop(series, cfg, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59,
                         zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth)
    assert stop.price == dec(expected)
    assert any("stop_from_zone_height" in r for r in stop.reasons)
    assert "F6" in stop.source_ids


def test_f6_frames_are_a_scale_carrier_not_a_reproduction() -> None:
    """Regression guard: do not re-add a circular frame-reproduction test.

    ``Frame`` derives ``height`` from ``distance / fraction`` and ``box_bottom`` from the entry,
    so ``(box_bottom - observed_stop) / height`` returns ``fraction`` by construction, at any
    price scale.  Asserting it proves arithmetic, not geometry.  Demonstrated here by scaling
    every input 10x and showing the implied ratio does not move.
    """
    for frame in FRAMES:
        implied = (frame.box_bottom - frame.observed_stop) / frame.height
        edge = "bottom" if frame.box_bottom == frame.entry else "top"
        scaled = Frame(frame.name, float(frame.entry) * 10, float(frame.fraction),
                       float(frame.pct_of_entry), edge,
                       float(frame.observed_stop) * 10)
        implied_scaled = (scaled.box_bottom - scaled.observed_stop) / scaled.height
        assert abs(implied - implied_scaled) < dec("0.001"), frame.name
        # ... and both sit within 0.04 of the recorded fraction, which is all the old test said
        assert abs(implied - frame.fraction) < dec("0.04"), frame.name


def test_f6_the_atr_parameterisation_does_not_reproduce_the_frames(uncapped: Config) -> None:
    """The counter-test: ``stop_buffer_atr`` cannot land on any of these three stops.

    The ATR buffer is measured from a *candle* anchor, so it is blind to the box the trader drew;
    on every one of the three frames it misses the observed stop by a wide margin.
    """
    for frame in FRAMES:
        series = make_series(flat_series(60, price=float(frame.entry)))
        atr_stop = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                                 reference_price=frame.entry, at_index=59)
        # misses by more than a quarter of a box height, i.e. more than twice the tolerance
        # the zone-fraction rule is held to above
        assert abs(atr_stop.price - frame.observed_stop) > frame.height / dec(4), frame.name


def test_f6_the_fraction_clusters_where_the_price_percentage_does_not() -> None:
    """Why the parameterisation changed, asserted on the readings themselves."""
    fractions = [f.fraction for f in FRAMES]
    percentages = [f.pct_of_entry for f in FRAMES]
    assert max(fractions) - min(fractions) <= dec("0.11")      # 0.48 .. 0.58
    assert max(percentages) - min(percentages) >= dec("2.0")   # 0.66 % .. 2.70 %
    assert min(fractions) <= dec("0.5") <= max(fractions)      # the default sits inside


def test_f6_default_and_sweep_bracket(uncapped: Config) -> None:
    from tbot.config import KEY_SPEC_BY_NAME
    assert uncapped.stop_buffer_zone_fraction == 0.5
    spec = KEY_SPEC_BY_NAME["stop_buffer_zone_fraction"]
    # widened to include 0.0: snap the stop to the structural level and model no overshoot,
    # which is the position of the independent measurement pass that withdrew this rule.
    assert spec.sweep_bracket == (0.0, 0.60)
    assert "F6" in spec.source_id and "TBOT1 4:11" in spec.source_id
    assert "DISPUTED" in spec.source_id


def test_f6_zone_anchored_stop_ignores_the_atr_buffer(uncapped: Config) -> None:
    """A zone-anchored stop must move with the box height and not with ATR."""
    series = make_series(flat_series(60))
    zone = make_zone(1.0)                                  # body core 99.0 .. 100.5
    kw = dict(direction=Direction.LONG, bar_index=50, reference_price=dec(100), at_index=59,
              zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth)
    stop = PL.place_stop(series, uncapped, **kw)
    assert stop.price == dec("99.0") - dec("0.5") * dec("1.5")     # 98.25
    assert stop.buffer == dec("0.75")
    # doubling the ATR buffer changes nothing; halving the fraction changes everything
    assert PL.place_stop(series, uncapped.with_overrides(stop_buffer_atr=0.30),
                         **kw).price == stop.price
    assert PL.place_stop(series, uncapped.with_overrides(stop_buffer_zone_fraction=0.25),
                         **kw).price == dec("99.0") - dec("0.375")


def test_f6_falls_back_to_the_atr_buffer_without_a_zone(uncapped: Config) -> None:
    """Levels, SFPs and structure breaks are not zones: P19 still owns those stops."""
    series = make_series(flat_series(60))
    bare = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59)
    assert bare.price == P.apply_stop_buffer(bare.anchor.price, Direction.LONG,
                                             P.stop_buffer(series, uncapped, 59))
    assert "P19" in bare.source_ids and "F6" not in bare.source_ids
    assert not any("stop_from_zone_height" in r for r in bare.reasons)
    # a zone with no height is not a zone either
    flat = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59,
                         zone_stop_edge=dec(99), zone_height=dec(0))
    assert flat.price == bare.price


def test_f6_short_side_places_the_stop_above_the_box_top(uncapped: Config) -> None:
    rows = flat_series(60)
    rows[50] = (100.8, 101.4, 100.7, 100.8)
    series = make_series(rows)
    zone = make_zone(1.0)
    zone.side = ZoneSide.SUPPLY                         # body core 99.0 .. 100.5, stop above 100.5
    stop = PL.place_stop(series, uncapped, direction=Direction.SHORT, bar_index=50,
                         reference_price=dec(100), at_index=59,
                         zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth)
    assert zone.body_stop_edge == dec("100.5")
    assert stop.price == dec("100.5") + dec("0.75")
    assert "F6" in stop.source_ids


def test_f6_does_not_survive_a_ladder_that_reaches_past_its_own_box(uncapped: Config) -> None:
    """A stop that does not invalidate the whole ladder is not a stop — P19 runs instead."""
    series = make_series(flat_series(60))
    zone = make_zone(1.0)
    stop = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59,
                         zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth,
                         beyond_price=dec(98))            # a DCA leg below the box bottom
    assert "F6" not in stop.source_ids
    assert any("zone_fraction_stop_not_beyond_the_entry_ladder" in r for r in stop.reasons)


def test_f6_keeps_the_opposing_level_clip_and_the_min_stop_floor(uncapped: Config) -> None:
    """Precedence is unchanged: ``stop_never_beyond_opposing_level`` still clips the F6 stop."""
    series = make_series(flat_series(60))
    zone = make_zone(1.0)
    kw = dict(direction=Direction.LONG, bar_index=50, reference_price=dec(100), at_index=59,
              zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth)
    free = PL.place_stop(series, uncapped, **kw)
    clipped = PL.place_stop(series, uncapped, opposing_levels=[level("OPP", 98.5)], **kw)
    assert free.price < dec("98.5") < clipped.price
    assert clipped.clipped_to_level_id == "OPP"
    assert any("stop_moved_inside_opposing_level" in r for r in clipped.reasons)
    # and the clip's nudge stays on the P19 ATR buffer, not on the (much larger) zone buffer
    assert clipped.price == dec("98.5") + P.stop_buffer(series, uncapped, 59)


def test_a_clip_inside_the_floor_reports_both_rules_firing(cfg: Config) -> None:
    """The case where CF-06 and CF-14 step 3 disagree, which neither rule's own test covers.

    The floor widens a too-tight stop out to ``min_stop_pct``; CF-14 step 3 then pulls it back
    toward the entry, to a distance the floor has already judged unusable, and nothing re-checks
    the floor afterwards. Two sourced rules composing into an unsourced outcome.

    ``place_stop`` used to set ``widened_to_min_stop_pct = False`` whenever it clipped, so this
    exact case - the one that matters - reported as though the floor had never fired. The two
    behaviours were each tested in isolation and their interaction was not: the clip test never
    looked at ``widened``, and the floor test passed no opposing levels. This is that test.

    It asserts the composition, not the precedence. The precedence is deliberate and stays:
    step 3 is a hard stated rule and the floor is ``[OUR CHOICE]``.
    """
    rows = flat_series(40)
    rows[30] = (100.0, 100.5, 99.95, 100.0)
    s = make_series(rows)
    tight = cfg.with_overrides(stop_buffer_atr=0.0)
    kw = dict(direction=Direction.LONG, bar_index=30, reference_price=dec(100), at_index=39)

    free = PL.place_stop(s, tight, **kw)
    assert free.widened_to_min_stop_pct, "fixture must trigger the floor or this proves nothing"
    assert money_close(free.stop_pct, dec(tight.min_stop_pct))

    # An opposing support sitting between the entry and the floor-widened stop.
    both = PL.place_stop(s, tight, opposing_levels=[level("OPP", 99.8)], **kw)
    assert both.clipped_to_level_id == "OPP"
    assert both.widened_to_min_stop_pct, (
        "the floor fired and the clip overruled it; the record must say both happened")
    assert both.stop_pct < dec(tight.min_stop_pct), (
        "fixture must leave the final stop inside the floor or it is not this case")
    assert any("stop_widened_to_min_stop_pct" in r for r in both.reasons)
    assert any("stop_moved_inside_opposing_level" in r for r in both.reasons)


def test_f6_is_still_subject_to_the_cf06_wide_stop_ladder(uncapped: Config) -> None:
    """CF-06 runs *after* F6: a zone so deep that its stop is > 9 % still tightens/downgrades."""
    series = make_series(flat_series(60))
    deep = make_zone(1.0)
    deep.box_top, deep.box_bottom = dec(100.5), dec(90.0)          # 10.5 tall
    stop = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59,
                         zone_stop_edge=deep.body_stop_edge, zone_height=deep.depth)
    assert stop.price == dec(90) - dec("5.25")
    assert stop.stop_pct > dec(9)
    vd = PL.escalate_wide_stop(series, uncapped, direction=Direction.LONG, stop=stop,
                               preferred_vehicle=Vehicle.LEVERAGE, spot_allowed=True)
    assert vd.downgraded and vd.vehicle is Vehicle.SPOT
    assert not vd.skip


def test_f6_stop_sits_below_the_bodies_but_not_below_the_capitulation_wick(
    uncapped: Config,
) -> None:
    """The fourth thing the pass-2 frames corroborate, and the spoken rule at TBOT1 22:57.

    In every readable frame the stop is below the candle *bodies* and deliberately **not** below
    the deepest / capitulation wick.  The zone box is body-anchored, so the F6 stop inherits that
    for free: it clears the box bottom by half a box height and still sits above a capitulation
    wick that reaches far below.  No code change — this asserts what the rule already does.
    """
    rows = flat_series(60)
    rows[50] = (99.2, 99.3, 96.5, 99.2)          # a deep capitulation wick to 96.5
    series = make_series(rows)
    zone = make_zone(1.0)                        # body core 99.0 .. 100.5
    stop = PL.place_stop(series, uncapped, direction=Direction.LONG, bar_index=50,
                         reference_price=dec(100), at_index=59,
                         zone_stop_edge=zone.body_stop_edge, zone_height=zone.depth)
    assert stop.price < zone.box_bottom          # below the bodies
    assert stop.price > dec("96.5")              # but not below the deepest wick


# ============================================================= F9 — the R:R measurement basis


def test_f9_a_plan_carries_both_rr_figures(uncapped: Config) -> None:
    """A built plan reports R:R to TP1 **and** to the final TP; only the basis is configurable."""
    plan = PL.build_plan(_inputs(uncapped), uncapped).plan
    assert plan is not None
    assert plan.rr_to_final_tp is not None
    # TP1 is the nearest structural level by construction (§8.7), so it can never be the further
    # of the two.  Here: 106 vs 115 above a 98.17 blended entry and a 93.80 stop.
    assert plan.rr_to_final_tp >= plan.rr_to_tp1
    assert money_close(plan.rr_to_tp1, dec("1.7913"), abs_tol=dec("0.001"))
    assert money_close(plan.rr_to_final_tp, dec("3.8502"), abs_tol=dec("0.001"))


def test_f9_the_gate_reads_the_final_tp_by_default(uncapped: Config) -> None:
    """**The pinned default change.**  ``rr_measured_to`` now names the final TP.

    His TradingView position tool measures R:R to its single **target line** — a final target,
    not a first partial (F9; TBOT1 4:11 / 22:59 / 1:09:19, S8 1:28:33 read 3.17 / 5.00 / 2.97 /
    2.13).  *That the tool measures that way is our reading of TradingView, not something he
    states.*
    """
    plan = PL.build_plan(_inputs(uncapped), uncapped).plan
    assert plan is not None
    assert uncapped.rr_measured_to == "final_tp"
    assert PL.rr_for_gate(uncapped, plan) == plan.rr_to_final_tp
    assert PL.rr_for_gate(uncapped.with_overrides(rr_measured_to="tp1"),
                          plan) == plan.rr_to_tp1


def test_f9_the_old_tp1_basis_would_have_rejected_this_plan(uncapped: Config) -> None:
    """Not a cosmetic re-parameterisation: the two bases disagree across ``min_rr`` here.

    Representative plan: entries 100 / 97 blended to 98.17, stop 93.80, TPs 106 and 115.
    R:R to TP1 is **1.79** — under the 2.0 floor, so the old basis vetoed it at G14 — while
    R:R to the final TP is **3.85**, comfortably inside the 2.13-5.00 band of the four frames.
    """
    plan = PL.build_plan(_inputs(uncapped), uncapped).plan
    assert plan is not None
    floor = dec(uncapped.min_rr)
    assert PL.rr_for_gate(uncapped.with_overrides(rr_measured_to="tp1"), plan) < floor
    assert PL.rr_for_gate(uncapped, plan) > floor


def test_f9_a_hand_built_plan_without_the_field_falls_back_to_tp1(uncapped: Config) -> None:
    """``rr_to_final_tp`` is optional on the model, so the gate must not read a missing value
    as zero and veto everything that predates the field."""
    plan = PL.build_plan(_inputs(uncapped), uncapped).plan
    assert plan is not None
    plan.rr_to_final_tp = None
    assert PL.rr_for_gate(uncapped, plan) == plan.rr_to_tp1


# --------------------------------------------------------------------- Q17: ladder vs stop
#
# The CF-14 step-3 clip can pull the stop INSIDE the entry ladder, leaving DCA rungs resting at
# prices the stop says the trade is already dead at.  Measured on 112 real trades that is 26
# trades, -958.95 and zero winners (GAPS.md).  He answers it himself - TBOT1 [00:38:08] declines
# the rung, S6 [01:12:28] re-sites it, S6 [00:23:05] drops it - and the flag ships off.

def _clipped_inside_ladder(cfg: Config) -> PL.PlanInputs:
    """Inputs whose step-3 clip lands the stop ABOVE the 97.0 DCA rung but below the average.

    The opposing level at 97.3 clips the stop to 97.5012.  The ladder is 100.00 / 97.00, so the
    DCA rung - carrying 61 % of the size - rests a full 0.5 below the stop.  A clip further up
    (98.0) instead trips ``assert_plan_consistent``'s "stop is not below the blended entry", which
    is a different failure and not the one under test.
    """
    return _inputs(cfg, opposing_levels=[level("OPP", 97.3)])


def _with(cfg: Config, **kw) -> Config:
    return dataclasses.replace(cfg, **kw)


def test_the_defect_this_rule_exists_for_is_real_while_the_flag_is_off(uncapped: Config) -> None:
    """Guard against a vacuous fixture: OFF must genuinely rest a funded rung beyond the stop."""
    plan = PL.build_plan(_clipped_inside_ladder(uncapped), uncapped).plan
    assert plan is not None
    assert plan.stop_clipped_to_level_id == "OPP"
    beyond = [r for r in plan.entries if r.size_fraction > 0 and r.price <= plan.stop_price]
    assert beyond, "fixture no longer reproduces the defect; the rest of this block proves nothing"
    assert beyond[0].price == dec(97.0)
    assert beyond[0].size_fraction == dec("0.61")


def test_a_funded_rung_the_stop_no_longer_invalidates_is_dropped(uncapped: Config) -> None:
    cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    build = PL.build_plan(_clipped_inside_ladder(cfg), cfg)
    assert build.ok, build.reasons
    plan = build.plan
    assert [r.price for r in plan.entries] == [dec(100.0)]
    assert all(r.price > plan.stop_price for r in plan.entries)
    assert any("entry_rungs_dropped_outside_stop" in n for n in build.notes)


def test_the_surviving_rung_is_resized_to_the_whole_position(uncapped: Config) -> None:
    """Dropping a rung must renormalise, or the trade goes on at 39 % of its intended size."""
    cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    plan = PL.build_plan(_clipped_inside_ladder(cfg), cfg).plan
    assert plan.entries[0].size_fraction == dec(1)
    assert plan.planned_average_entry == dec(100.0)


def _two_rungs_beyond_the_stop(cfg: Config) -> PL.PlanInputs:
    """A THREE-rung ladder where the clip lands the stop above rungs 1 and 2, so two are dropped.

    ``_clipped_inside_ladder`` has exactly two rungs, so it can only ever drop one - which is why
    the note's ``keep + 1`` arithmetic was right by coincidence there and wrong in general.

    Two drops need the stop above rung 1, so the blended entry must exceed rung 1: a wide first
    gap and a narrow second (100 / 95.0 / 94.5 at .15/.325/.525 blends to 95.4875). The opposing
    level at 95.2 then clips the stop to 95.401, above both DCA rungs.
    """
    return _inputs(cfg, opposing_levels=[level("OPP", 95.2)],
                   dca_levels=[level("L1", 95.0), level("L2", 94.5)])


def _three_rung(cfg: Config, **kw) -> Config:
    """``dca_count_default`` ships at 1, so the shipped ladder is two rungs. Ask for three."""
    return _with(cfg, dca_count_default=2, **kw)


def test_the_drop_note_counts_the_whole_original_ladder(uncapped: Config) -> None:
    """The note reports how much of the ladder went, so it must not assume exactly one rung did.

    ``build_entry_ladder`` rebinds ``rungs``, so the original length is gone by the time the note
    is written. Reconstructing it as ``keep + 1`` silently understates every multi-drop: here two
    rungs carrying 85 % of the position are removed and the note claimed one of two kept.
    """
    base = _three_rung(uncapped)
    cfg = _three_rung(uncapped, entry_ladder_must_sit_inside_stop=True)
    off = PL.build_plan(_two_rungs_beyond_the_stop(base), base).plan
    assert [r.price for r in off.entries] == [dec(100.0), dec(95.0), dec(94.5)], (
        "fixture must start with three rungs or this proves nothing")

    build = PL.build_plan(_two_rungs_beyond_the_stop(cfg), cfg)
    assert [r.price for r in build.plan.entries] == [dec(100.0)]
    note = next(n for n in build.notes if "entry_rungs_dropped_outside_stop" in n)
    assert "1_of_3_kept" in note, note


def test_the_stop_is_not_re_placed_after_the_drop(uncapped: Config) -> None:
    """Step 3 keeps the last word on the stop - he takes the tighter stop too (S6 [01:12:28])."""
    off = PL.build_plan(_clipped_inside_ladder(uncapped), uncapped).plan
    cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    on = PL.build_plan(_clipped_inside_ladder(cfg), cfg).plan
    assert on.stop_price == off.stop_price
    assert on.stop_clipped_to_level_id == off.stop_clipped_to_level_id == "OPP"


def test_dropping_moves_the_average_away_from_the_stop_never_toward_it(uncapped: Config) -> None:
    """Why not re-placing the stop is safe: the CF-06 floor can only get further from violation."""
    off = PL.build_plan(_clipped_inside_ladder(uncapped), uncapped).plan
    cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    on = PL.build_plan(_clipped_inside_ladder(cfg), cfg).plan
    assert on.planned_average_entry > off.planned_average_entry      # long: away from a stop below
    assert (on.planned_average_entry - on.stop_price
            > off.planned_average_entry - off.stop_price)


def test_a_ladder_the_stop_still_invalidates_is_untouched(uncapped: Config) -> None:
    cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    build = PL.build_plan(_inputs(cfg), cfg)          # no opposing level, stop at 93.80
    assert [r.price for r in build.plan.entries] == [dec(100.0), dec(97.0)]
    assert not any("entry_rungs_dropped_outside_stop" in n for n in build.notes)


def test_an_unfunded_low_conviction_rung_does_not_count_against_the_ladder(
    uncapped: Config,
) -> None:
    """TBOT1-C6 legs are armed but sized to zero; they buy nothing, so they extend nothing.

    This is the same carve-out ``_ladder_extreme`` already makes, and the engine agrees with it -
    ``_fill_limit_rungs`` skips any rung whose qty is zero.
    """
    cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    inputs = _inputs(cfg, setup=make_setup(conviction=Conviction.LOW),
                     opposing_levels=[level("OPP", 97.3)])
    build = PL.build_plan(inputs, cfg)
    assert build.ok, build.reasons
    rung = [r for r in build.plan.entries if r.price == dec(97.0)]
    assert rung and rung[0].size_fraction == dec(0), "the unfunded leg should still be armed"
    assert not any("entry_rungs_dropped_outside_stop" in n for n in build.notes)


def test_the_ladder_rule_is_bit_identical_while_disabled(uncapped: Config) -> None:
    default = PL.build_plan(_clipped_inside_ladder(uncapped), uncapped).plan
    explicit_cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=False)
    explicit = PL.build_plan(_clipped_inside_ladder(explicit_cfg), explicit_cfg).plan
    for f in dataclasses.fields(default):
        assert getattr(default, f.name) == getattr(explicit, f.name), f.name

    # ...and the equality above is not vacuous: switching it ON does change this very plan.
    on_cfg = _with(uncapped, entry_ladder_must_sit_inside_stop=True)
    on = PL.build_plan(_clipped_inside_ladder(on_cfg), on_cfg).plan
    assert on.entries != default.entries
    assert on.qty_total != default.qty_total


def _rung(i: int, price: float, size: str = "0.5") -> EntryRung:
    return EntryRung(index=i, price=dec(price), size_fraction=dec(size),
                     kind="entry" if i == 0 else "dca", level_id=f"L{i}")


class TestRungsTheStopInvalidates:
    """Direct cover for the Q17 predicate, including the boundary ``build_plan`` cannot reach.

    A rung sitting EXACTLY on the stop is dead: entering there is entering at the price that
    closes the trade.  The clip always adds a buffer, so no end-to-end fixture lands on it, and
    without this class a ``<=`` -> ``<`` mutation survives the whole suite.
    """

    def test_a_long_rung_exactly_on_the_stop_is_dead(self) -> None:
        rungs = [_rung(0, 100.0), _rung(1, 97.0)]
        assert PL.rungs_the_stop_invalidates(rungs, dec(97.0), Direction.LONG) == 1

    def test_a_short_rung_exactly_on_the_stop_is_dead(self) -> None:
        rungs = [_rung(0, 100.0), _rung(1, 103.0)]
        assert PL.rungs_the_stop_invalidates(rungs, dec(103.0), Direction.SHORT) == 1

    def test_a_rung_a_tick_inside_the_stop_survives(self) -> None:
        rungs = [_rung(0, 100.0), _rung(1, 97.0)]
        assert PL.rungs_the_stop_invalidates(rungs, dec("96.99"), Direction.LONG) == 2
        short = [_rung(0, 100.0), _rung(1, 103.0)]
        assert PL.rungs_the_stop_invalidates(short, dec("103.01"), Direction.SHORT) == 2

    def test_it_counts_a_prefix_not_a_total(self) -> None:
        rungs = [_rung(0, 100.0), _rung(1, 97.0), _rung(2, 94.0)]
        assert PL.rungs_the_stop_invalidates(rungs, dec(95.0), Direction.LONG) == 2

    def test_unfunded_rungs_are_transparent(self) -> None:
        rungs = [_rung(0, 100.0, "1"), _rung(1, 97.0, "0"), _rung(2, 94.0, "0")]
        assert PL.rungs_the_stop_invalidates(rungs, dec(98.0), Direction.LONG) == 3

    def test_an_entirely_dead_ladder_counts_zero(self) -> None:
        rungs = [_rung(0, 100.0), _rung(1, 97.0)]
        assert PL.rungs_the_stop_invalidates(rungs, dec(101.0), Direction.LONG) == 0
