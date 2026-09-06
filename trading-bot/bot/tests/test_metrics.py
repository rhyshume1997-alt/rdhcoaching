"""Tests for tbot.backtest.metrics — hand-built trades with known outcomes.

Every number asserted here is computed by hand in the test, not read back from the code under
test.  The §12.5 claim handling gets its own section: the 77-82 % figure must always be reported
as a *hypothesis*, must never be reachable as a target, and must be declared inconclusive when the
sample is small.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.backtest.engine import (
    BacktestResult,
    ClosedTrade,
    EquityPoint,
    EventLog,
    RejectionRecord,
)
from tbot.backtest.metrics import (
    BREAKEVEN_R_EPSILON,
    CLAIM_HIGH_PCT,
    CLAIM_LOW_PCT,
    MIN_SAMPLE_FOR_CONCLUSION,
    Bucket,
    ClaimComparison,
    Drawdown,
    RDistribution,
    WinRates,
    compute_metrics,
)
from tbot.config import Config
from tbot.models import (
    Account,
    CloseReason,
    Conviction,
    Direction,
    EntryFamily,
    Timeframe,
    TradeClass,
    Vehicle,
    dec,
)

START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def trade(
    ref: str,
    *,
    r: float,
    pnl: float | None = None,
    tps_hit: int = 1,
    tp_count: int = 2,
    primary_class: str = "zone",
    classes: tuple[str, ...] = ("zone", "sr_level"),
    trade_class: TradeClass = TradeClass.SWING,
    vehicle: Vehicle = Vehicle.SPOT,
    conviction: Conviction = Conviction.NORMAL,
    entry_family: EntryFamily = EntryFamily.RETEST,
    close_reason: CloseReason = CloseReason.TP_FINAL,
    bars: int = 10,
    rungs=(True, False),
    average_entry: float = 100.0,
    planned_average_entry: float = 100.0,
    excess_risk: float = 0.0,
    touch_index: int = 1,
) -> ClosedTrade:
    """One closed trade with an exactly specified outcome.  ``pnl`` defaults to ``r * 100`` USD."""
    net = dec(pnl if pnl is not None else r * 100.0)
    return ClosedTrade(
        id=f"TEST:1H:trade:{ref}", ref=ref, plan_id=f"P-{ref}", setup_id=f"S-{ref}", symbol="TEST",
        tf=Timeframe.H1, direction=Direction.LONG, trade_class=trade_class, vehicle=vehicle,
        conviction=conviction, entry_family=entry_family, account=Account.SPOT_SHORT,
        primary_class=primary_class, confluence_classes=classes, source_ids=("CF-10", "S5-R15"),
        opened_index=0, closed_index=bars, opened_at=START,
        closed_at=START + timedelta(hours=bars), bars_in_trade=bars, qty=dec(1.0),
        average_entry=dec(average_entry), planned_average_entry=dec(planned_average_entry),
        initial_stop=dec(90.0), exit_price=dec(110.0), gross_pnl_usd=net + dec(1.0),
        fees_usd=dec(1.0), funding_usd=dec(0.0), net_pnl_usd=net, initial_risk_usd=dec(100.0),
        r_multiple=dec(r), close_reason=close_reason, tps_hit=tps_hit, tp_count=tp_count,
        rungs_planned=len(rungs), rungs_filled=sum(rungs), rung_fill_flags=tuple(rungs),
        touch_index_at_entry=touch_index, excess_risk_usd=dec(excess_risk), liquidated=False,
        fills=(),
    )


def make_result(trades, *, equity=None, rejections=(), starting=1000.0) -> BacktestResult:
    curve = []
    if equity is not None:
        curve = [
            EquityPoint(bar_index=k, timestamp=START + timedelta(hours=k), equity=dec(value),
                        realised=dec(value) - dec(starting), unrealised=dec(0),
                        by_account={Account.SPOT_SHORT.value: dec(value) - dec(starting)})
            for k, value in enumerate(equity)
        ]
    return BacktestResult(
        symbol="TEST", tf=Timeframe.H1, bars=100, warmup_bars=0, start=START,
        end=START + timedelta(hours=100), starting_equity=dec(starting),
        ending_equity=curve[-1].equity if curve else dec(starting), trades=tuple(trades),
        open_at_end=(), events=EventLog(), detections=(), rejections=tuple(rejections),
        equity_curve=tuple(curve), config=Config.load(),
    )


# ===========================================================================
# Win rates — the three definitions of §12.4 / §12.5
# ===========================================================================


def test_the_three_win_definitions_are_computed_independently():
    """5 trades: 3 net-positive, 1 loss, 1 break-even; 2 of them completed the full TP ladder."""
    trades = [
        trade("T1", r=2.0, tps_hit=2, tp_count=2),          # win, full ladder
        trade("T2", r=1.5, tps_hit=2, tp_count=2),          # win, full ladder
        trade("T3", r=0.4, tps_hit=1, tp_count=2,           # win, trailed out after TP1
              close_reason=CloseReason.TRAIL_OUT),
        trade("T4", r=-1.0, tps_hit=0, tp_count=2, close_reason=CloseReason.STOP),
        trade("T5", r=0.0, pnl=0.0, tps_hit=1, tp_count=2,  # break-even trail-out
              close_reason=CloseReason.TRAIL_OUT),
    ]
    rates = WinRates.of(trades)
    assert (rates.trades, rates.wins, rates.losses, rates.breakevens) == (5, 3, 1, 1)
    assert rates.net_positive_pct == Decimal("60")           # 3/5
    assert rates.full_ladder_pct == Decimal("40")            # 2/5
    assert rates.excluding_breakeven_pct == Decimal("75")    # 3/4 decided


def test_a_trail_out_after_tp1_is_one_trade_and_a_win():
    """§12.4: TP1 with the residual trailed out at break-even is ONE trade, and it is a win."""
    rates = WinRates.of([trade("T1", r=0.6, tps_hit=1, tp_count=3,
                               close_reason=CloseReason.TRAIL_OUT)])
    assert rates.trades == 1 and rates.wins == 1
    assert rates.net_positive_pct == Decimal("100")
    assert rates.full_ladder_pct == Decimal("0")


def test_break_even_epsilon_separates_scratches_from_wins():
    inside = trade("T1", r=float(BREAKEVEN_R_EPSILON) / 2, pnl=0.01)
    outside = trade("T2", r=float(BREAKEVEN_R_EPSILON) * 2, pnl=10.0)
    rates = WinRates.of([inside, outside])
    assert (rates.wins, rates.breakevens) == (1, 1)


def test_empty_trade_list_does_not_divide_by_zero():
    rates = WinRates.of([])
    assert rates.trades == 0
    assert rates.net_positive_pct == Decimal(0)
    assert rates.excluding_breakeven_pct == Decimal(0)


# ===========================================================================
# Expectancy and R distribution
# ===========================================================================


def test_expectancy_is_the_mean_r():
    trades = [trade("T1", r=2.0), trade("T2", r=-1.0), trade("T3", r=-1.0), trade("T4", r=3.0)]
    report = compute_metrics(make_result(trades))
    assert report.expectancy_r == Decimal("0.75")            # (2 - 1 - 1 + 3) / 4
    assert report.expectancy_usd == Decimal("75")            # pnl = r * 100


def test_r_distribution_percentiles_and_sub_minus_one_count():
    values = [-2.5, -1.4, -1.0, -1.0, 0.2, 1.0, 1.8, 2.4, 3.1, 4.0]
    trades = [trade(f"T{k}", r=v) for k, v in enumerate(values)]
    dist = RDistribution.of(trades)
    assert dist.count == 10
    assert dist.median == Decimal("0.6")                     # (0.2 + 1.0) / 2
    assert dist.worse_than_minus_1r == 2                     # -2.5 and -1.4, not the two at -1.0
    assert dist.mean == sum((dec(v) for v in values), Decimal(0)) / Decimal(10)
    assert sum(count for _, count in dist.histogram) == 10


def test_r_distribution_of_a_single_trade_is_that_trade():
    dist = RDistribution.of([trade("T1", r=1.25)])
    assert dist.p5 == dist.median == dist.p95 == Decimal("1.25")


# ===========================================================================
# Drawdown
# ===========================================================================


def test_max_drawdown_is_peak_to_trough():
    curve = [(0, dec(1000)), (1, dec(1200)), (2, dec(900)), (3, dec(1100)), (4, dec(1050))]
    dd = Drawdown.of(curve)
    assert dd.max_usd == Decimal("300")                      # 1200 -> 900
    assert dd.max_pct == Decimal("25")                       # 300 / 1200
    assert (dd.peak_index, dd.trough_index) == (1, 2)


def test_a_monotonically_rising_curve_has_no_drawdown():
    dd = Drawdown.of([(k, dec(1000 + 10 * k)) for k in range(10)])
    assert dd.max_usd == Decimal(0) and dd.max_pct == Decimal(0)


def test_report_drawdown_uses_the_equity_curve():
    report = compute_metrics(make_result([trade("T1", r=1.0)],
                                         equity=[1000, 1500, 750, 900]))
    assert report.drawdown.max_usd == Decimal("750")
    assert report.drawdown.max_pct == Decimal("50")


# ===========================================================================
# Attribution
# ===========================================================================


def test_per_detector_attribution_splits_by_anchor_class():
    trades = [
        trade("T1", r=2.0, primary_class="zone", classes=("zone", "sr_level")),
        trade("T2", r=-1.0, primary_class="zone", classes=("zone", "fib")),
        trade("T3", r=3.0, primary_class="order_block", classes=("order_block", "zone")),
    ]
    report = compute_metrics(make_result(trades))
    by_name = {b.label: b for b in report.attribution.primary}
    assert by_name["zone"].trades == 2
    assert by_name["zone"].win_rate_pct == Decimal("50")
    assert by_name["zone"].total_r == Decimal("1.0")
    assert by_name["zone"].expectancy_r == Decimal("0.5")
    assert by_name["order_block"].trades == 1
    assert by_name["order_block"].total_r == Decimal("3.0")


def test_marginal_confluence_contribution_is_reported_separately():
    """CF-31/CF-37: a class that was in the stack but not the anchor still gets its own row."""
    trades = [
        trade("T1", r=2.0, primary_class="zone", classes=("zone", "sr_level")),
        trade("T2", r=-1.0, primary_class="zone", classes=("zone", "sr_level", "fib")),
    ]
    report = compute_metrics(make_result(trades))
    marginal = {b.label: b for b in report.attribution.marginal}
    assert set(marginal) == {"sr_level", "fib"}
    assert marginal["sr_level"].trades == 2 and marginal["sr_level"].total_r == Decimal("1.0")
    assert marginal["fib"].trades == 1
    assert "zone" not in marginal, "the anchor class is not its own marginal contributor"


def test_per_config_attribution_covers_every_required_dimension():
    trades = [
        trade("T1", r=1.0, trade_class=TradeClass.SWING, vehicle=Vehicle.SPOT,
              conviction=Conviction.HIGH, entry_family=EntryFamily.RETEST, touch_index=1),
        trade("T2", r=-1.0, trade_class=TradeClass.SCALP, vehicle=Vehicle.LEVERAGE,
              conviction=Conviction.LOW, entry_family=EntryFamily.TRIGGER, touch_index=3),
    ]
    report = compute_metrics(make_result(trades))
    assert {b.label for b in report.by_trade_class} == {"swing", "scalp"}
    assert {b.label for b in report.by_vehicle} == {"spot", "leverage"}
    assert {b.label for b in report.by_conviction} == {"high", "low"}
    assert {b.label for b in report.by_entry_family} == {"retest", "trigger"}
    assert {b.label for b in report.by_touch_index} == {"touch 1", "touch 3"}


# ===========================================================================
# Fill quality, excess risk, veto census, time in market
# ===========================================================================


def test_rung_fill_rate_is_per_ladder_position():
    trades = [
        trade("T1", r=1.0, rungs=(True, True)),
        trade("T2", r=1.0, rungs=(True, False)),
        trade("T3", r=1.0, rungs=(True, False)),
        trade("T4", r=1.0, rungs=(True, True)),
    ]
    quality = compute_metrics(make_result(trades)).fill_quality
    assert quality.rung_offered == (4, 4)
    assert quality.rung_filled == (4, 2)
    assert quality.rung_fill_rate_pct == (Decimal("100"), Decimal("50"))
    assert quality.trades_with_partial_ladder == 2


def test_entry_slippage_is_signed_adverse_positive():
    """A long that paid MORE than planned is adverse; the metric must not cancel that out."""
    worse = trade("T1", r=1.0, average_entry=101.0, planned_average_entry=100.0)
    better = trade("T2", r=1.0, average_entry=99.0, planned_average_entry=100.0)
    assert worse.entry_slippage == Decimal("1")
    assert better.entry_slippage == Decimal("-1")
    quality = compute_metrics(make_result([worse])).fill_quality
    assert quality.mean_entry_slippage == Decimal("1")
    assert quality.mean_entry_slippage_bps == Decimal("100")


def test_excess_risk_is_totalled_and_never_netted_into_pnl():
    trades = [trade("T1", r=-1.5, excess_risk=40.0), trade("T2", r=1.0, excess_risk=0.0)]
    report = compute_metrics(make_result(trades))
    assert report.excess_risk_total_usd == Decimal("40")
    assert report.excess_risk_trades == 1
    assert report.expectancy_r == Decimal("-0.25"), "excess risk must not be netted out of R"


def test_veto_census_counts_gates_and_reasons_most_common_first():
    rejections = [
        RejectionRecord(1, "s1", "G4", "mid_range_no_trade_band"),
        RejectionRecord(2, "s2", "G4", "mid_range_no_trade_band"),
        RejectionRecord(3, "s3", "G7", "min_rr not met"),
        RejectionRecord(4, "s4", "G2", "htf_veto"),
        RejectionRecord(5, "s5", "G4", "mid_range_no_trade_band"),
    ]
    report = compute_metrics(make_result([], rejections=rejections))
    assert report.veto_census[0] == ("G4", 3)
    assert dict(report.veto_census) == {"G4": 3, "G7": 1, "G2": 1}
    assert report.veto_reasons[0] == ("mid_range_no_trade_band", 3)


def test_time_in_market_converts_bars_to_hours_on_the_series_timeframe():
    trades = [trade("T1", r=1.0, bars=10, trade_class=TradeClass.SWING),
              trade("T2", r=1.0, bars=20, trade_class=TradeClass.SWING),
              trade("T3", r=1.0, bars=2, trade_class=TradeClass.SCALP)]
    tim = compute_metrics(make_result(trades)).time_in_market
    assert tim.median_bars == Decimal("10")
    assert tim.median_hours == Decimal("10")          # 1H bars
    by_class = {name: (bars, hours) for name, bars, hours in tim.by_class}
    assert by_class["swing"][0] == Decimal("15")
    assert by_class["scalp"][0] == Decimal("2")


# ===========================================================================
# §12.5 — the 77-82 % claim is a hypothesis, never a target
# ===========================================================================


def test_a_small_sample_is_reported_as_inconclusive():
    trades = [trade(f"T{k}", r=2.0) for k in range(8)]
    claim = ClaimComparison.of(WinRates.of(trades))
    assert claim.sample_size == 8
    assert not claim.sample_sufficient
    assert "too small to conclude" in claim.conclusion
    assert claim.measured_pct == Decimal("100")
    assert claim.claim_low_pct == CLAIM_LOW_PCT and claim.claim_high_pct == CLAIM_HIGH_PCT


def test_a_large_sample_well_below_the_claim_is_reported_as_a_result():
    wins = [trade(f"W{k}", r=1.0) for k in range(20)]
    losses = [trade(f"L{k}", r=-1.0) for k in range(30)]
    claim = ClaimComparison.of(WinRates.of(wins + losses))
    assert claim.sample_size == 50 and claim.sample_sufficient
    assert claim.measured_pct == Decimal("40")
    assert "BELOW the claim" in claim.conclusion
    assert "must not trigger fitting toward the claim" in claim.conclusion


def test_a_large_sample_consistent_with_the_claim_says_so_without_confirming_it():
    wins = [trade(f"W{k}", r=1.0) for k in range(79)]
    losses = [trade(f"L{k}", r=-1.0) for k in range(21)]
    claim = ClaimComparison.of(WinRates.of(wins + losses))
    assert claim.measured_pct == Decimal("79")
    assert "overlaps" in claim.conclusion
    assert "not the same as confirming it" in claim.conclusion


def test_the_wilson_interval_brackets_the_measured_value():
    claim = ClaimComparison.of(WinRates.of([trade(f"W{k}", r=1.0) for k in range(10)] +
                                           [trade(f"L{k}", r=-1.0) for k in range(10)]))
    assert claim.ci_low_pct < claim.measured_pct < claim.ci_high_pct


def test_the_claim_note_names_it_as_a_hypothesis_and_forbids_sizing_off_it():
    claim = ClaimComparison.of(WinRates.of([]))
    assert "hypothesis" in claim.note
    assert "NOT usable for sizing" in claim.note
    assert "no sizing, expectancy, kelly" in claim.note.lower()


def test_min_sample_threshold_is_declared_not_hidden():
    assert MIN_SAMPLE_FOR_CONCLUSION == 30


def test_the_rendered_report_shows_claim_and_measurement_side_by_side():
    trades = [trade(f"W{k}", r=1.0) for k in range(3)] + [trade("L0", r=-1.0)]
    text = compute_metrics(make_result(trades, equity=[1000, 1100, 900, 1200])).render()
    assert "77%-82%" in text
    assert "A HYPOTHESIS UNDER TEST" in text
    assert "WIN RATE (three definitions" in text
    assert "1. net P&L > 0 (headline)" in text
    assert "2. full TP-ladder completion" in text
    assert "3. excluding break-even exits" in text
    assert "n = 4" in text
    assert "VETO CENSUS" in text


def test_report_is_json_serialisable_without_losing_precision():
    import json

    report = compute_metrics(make_result([trade("T1", r=1.0)], equity=[1000, 1100]))
    payload = report.to_dict()
    text = json.dumps(payload)
    assert '"expectancy_r": "1"' in text or '"expectancy_r": "1.0"' in text
    assert json.loads(text)["symbol"] == "TEST"


def test_metrics_on_an_empty_run_are_all_zero_and_do_not_raise():
    report = compute_metrics(make_result([]))
    assert report.win_rates.trades == 0
    assert report.expectancy_r == Decimal(0)
    assert report.claim.sample_size == 0
    assert "nothing can be said" in report.claim.conclusion
    assert report.render()
