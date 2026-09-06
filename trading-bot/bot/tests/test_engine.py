"""Tests for tbot.backtest.engine — no-lookahead first, then the §12.2 fill model.

The single most important test in this file is the lookahead suite: a detector that deliberately
peeks at a future bar must be *caught*, not tolerated.  SPEC.md §12.1 makes that a harness-level
assertion, so the expected outcome is a raised :class:`LookaheadError`, not a warning.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import tbot.primitives as P
from tbot.backtest.engine import (
    BacktestEngine,
    BarWindow,
    DetectionRecord,
    EventKind,
    LookaheadError,
    PipelineOutput,
    RejectionRecord,
    assert_no_future_reference,
    run_backtest,
)
from tbot.config import Config
from tbot.data import synthetic
from tbot.models import (
    CloseReason,
    Conviction,
    Direction,
    EntryFamily,
    EntryRung,
    PositionState,
    Series,
    Setup,
    TakeProfit,
    Timeframe,
    TradeClass,
    TradePlan,
    Vehicle,
    dec,
)

START = datetime(2024, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- helpers


def make_series(bars, tf: Timeframe = Timeframe.H1, symbol: str = "TEST") -> Series:
    """``bars`` is a sequence of ``(open, high, low, close)``; volume is constant."""
    stamps = [START + timedelta(minutes=tf.minutes * k) for k in range(len(bars))]
    return Series.from_arrays(
        stamps,
        [b[0] for b in bars], [b[1] for b in bars], [b[2] for b in bars], [b[3] for b in bars],
        volume=[1_000.0] * len(bars), tf=tf, symbol=symbol,
    )


def flat_series(n: int = 40, price: float = 100.0) -> Series:
    return make_series([(price, price + 1, price - 1, price)] * n)


def make_plan(
    *,
    plan_id: str = "PLAN-1",
    direction: Direction = Direction.LONG,
    entries=((100.0, 1.0),),
    stop: float = 95.0,
    tps=((110.0, 1.0),),
    qty: float = 1.0,
    vehicle: Vehicle = Vehicle.SPOT,
    trade_class: TradeClass = TradeClass.SWING,
    expires_at_index: int | None = None,
    planned_average_entry: float | None = None,
) -> TradePlan:
    rungs = [
        EntryRung(index=k, price=dec(price), size_fraction=dec(frac),
                  kind="entry" if k == 0 else "dca", level_id=f"lvl-{k}")
        for k, (price, frac) in enumerate(entries)
    ]
    takes = [
        TakeProfit(index=k + 1, price=dec(price), size_fraction=dec(frac), level_id=f"tp-lvl-{k}")
        for k, (price, frac) in enumerate(tps)
    ]
    planned = dec(planned_average_entry) if planned_average_entry is not None else dec(
        sum(p * f for p, f in entries))
    return TradePlan(
        id=plan_id, setup_id=f"{plan_id}-setup", symbol="TEST", direction=direction,
        trade_class=trade_class, vehicle=vehicle, leverage=dec(1.0), entries=rungs,
        stop_price=dec(stop), take_profits=takes, qty_total=dec(qty),
        notional_usd=dec(qty * float(planned)), risk_budget_pct=dec(2.0),
        average_entry=dec(0), planned_average_entry=planned, rr_to_tp1=dec(2.0),
        expected_move_pct=dec(10.0), invalidation_level_id="lvl-0",
        expires_at_index=expires_at_index, source_ids=("CF-16", "S5-R20"),
    )


def make_setup(plan: TradePlan, *, family: EntryFamily = EntryFamily.RETEST,
               primary_class: str = "zone", classes=("zone", "sr_level")) -> Setup:
    return Setup(
        id=plan.setup_id, symbol=plan.symbol, direction=plan.direction, trade_tf=Timeframe.H1,
        structure_tf=Timeframe.H4, trade_class=plan.trade_class,
        anchor_price=plan.planned_average_entry, created_index=0,
        confluence_score=dec(3.75), confluence_classes=set(classes), entry_family=family,
        conviction=Conviction.NORMAL, regime_flags={"primary_class": primary_class},
        source_ids=("CF-31", "S5-R15"),
    )


class OneShotProvider:
    """Publishes one plan at ``at_index`` and nothing else, ever."""

    def __init__(self, plan: TradePlan, at_index: int = 0, setup: Setup | None = None) -> None:
        self.plan = plan
        self.at_index = at_index
        self.setup = setup if setup is not None else make_setup(plan)
        self.calls: list[int] = []

    def __call__(self, window: BarWindow, config: Config) -> PipelineOutput:
        self.calls.append(window.now)
        if window.now != self.at_index:
            return PipelineOutput()
        return PipelineOutput(
            plans=(self.plan,), setups=(self.setup,),
            detections=(DetectionRecord(bar_index=window.now, detector="supply_demand_zones",
                                        object_id="zone-1", obj_class="zone",
                                        source_ids=("CF-10", "S5-R15")),),
        )


@pytest.fixture()
def cfg() -> Config:
    return Config.load()


def run(series, cfg, provider, **kwargs):
    kwargs.setdefault("warmup_bars", 0)
    return run_backtest(series, cfg, plan_provider=provider, **kwargs)


# ===========================================================================
# 1. NO LOOKAHEAD — the assertion SPEC.md §12.1 demands
# ===========================================================================


def test_detector_peeking_at_the_next_bar_is_caught(cfg):
    """A detector that reaches for bar ``now + 1`` must raise, not silently succeed."""
    peeked: list[int] = []

    def peeking_provider(window: BarWindow, config: Config) -> PipelineOutput:
        peeked.append(window.now)
        window.candle(window.now + 1)      # <-- the crime
        return PipelineOutput()

    series = flat_series(20)
    with pytest.raises(LookaheadError) as err:
        run(series, cfg, peeking_provider)
    assert "has not closed yet" in str(err.value)
    assert peeked == [0], "the engine must fail on the very first peek, not accumulate them"


def test_peeking_at_the_last_bar_of_the_full_series_is_caught(cfg):
    """The classic bug: reading ``series[-1]`` of the *whole* file instead of the current bar."""
    series = flat_series(30)

    def cheating_provider(window: BarWindow, config: Config) -> PipelineOutput:
        # The full series has 30 bars; asking for bar 29 on bar 3 is lookahead.
        window.price(len(series) - 1, "close")
        return PipelineOutput()

    with pytest.raises(LookaheadError):
        run(series, cfg, cheating_provider)


def test_window_head_cannot_reach_past_now(cfg):
    series = flat_series(15)
    window = BarWindow.at(series, 5)
    assert len(window.head(6)) == 6
    with pytest.raises(LookaheadError):
        window.head(7)


def test_window_is_physically_truncated_not_merely_promised(cfg):
    """The pipeline never receives the future: the Series it gets does not contain those rows."""
    seen: list[tuple[int, int, object]] = []
    series = flat_series(12)

    def recording_provider(window: BarWindow, config: Config) -> PipelineOutput:
        seen.append((window.now, len(window.series), window.series.timestamp(-1)))
        # Even reaching directly into the underlying Series cannot find a later bar.
        with pytest.raises(IndexError):
            window.series.candle(window.now + 1)
        return PipelineOutput()

    run(series, cfg, recording_provider)
    assert [s[0] for s in seen] == list(range(12))
    for now, length, last_ts in seen:
        assert length == now + 1
        assert last_ts == series.timestamp(now)


def test_negative_indices_are_still_the_present(cfg):
    series = flat_series(10)
    window = BarWindow.at(series, 4)
    assert window.candle(-1).close == window.candle(4).close
    assert window.price(-1, "close") == series.price_at(4, "close")


def test_output_audit_catches_an_object_anchored_in_the_future(cfg):
    """A detector that kept the full series and reports a future bar index is caught on output."""
    series = flat_series(20)
    plan = make_plan()

    def future_object_provider(window: BarWindow, config: Config) -> PipelineOutput:
        setup = make_setup(plan)
        setup.created_index = window.now + 3          # <-- reported from a bar that has not closed
        return PipelineOutput(plans=(plan,), setups=(setup,))

    with pytest.raises(LookaheadError) as err:
        run(series, cfg, future_object_provider)
    assert "created_index" in str(err.value)
    assert "standing on bar 0" in str(err.value)


def test_output_audit_walks_into_nested_objects(cfg):
    """A future ``fill_index`` buried on a ladder rung is still caught."""
    plan = make_plan()
    plan.entries[0].fill_index = 99
    with pytest.raises(LookaheadError) as err:
        assert_no_future_reference([plan], 5, path="pipeline.plans")
    assert "fill_index" in str(err.value)


def test_output_audit_allows_a_future_expiry_and_ladder_ordinals(cfg):
    """``expires_at_index`` is legitimately in the future; rung/TP ``index`` are ordinals."""
    plan = make_plan(expires_at_index=500, entries=((100.0, 0.3), (95.0, 0.7)),
                     tps=((110.0, 0.5), (120.0, 0.5)))
    assert_no_future_reference([plan], 0)  # must not raise


def test_detections_are_audited_too(cfg):
    bad = DetectionRecord(bar_index=7, detector="zones", object_id="z", obj_class="zone")
    with pytest.raises(LookaheadError):
        assert_no_future_reference([bad], 3)


def test_atr_is_causal_so_the_cached_array_is_not_lookahead(cfg):
    """The engine caches ATR over the whole series; that is only legitimate if ATR is causal."""
    series = synthetic(seed=7).series
    full = P.atr_array(series, int(cfg.atr_period))
    for i in (0, 1, 13, 14, 15, 60, len(series) - 1):
        head = P.atr_array(series.head(i + 1), int(cfg.atr_period))
        assert head[-1] == pytest.approx(full[i], rel=1e-12), f"ATR at bar {i} is not causal"


def test_a_plan_armed_on_bar_i_cannot_be_filled_by_bar_i(cfg):
    """The bar that produced the plan had not closed when the plan was made: it cannot fill it."""
    # Bar 3 trades right through the limit at 100; the plan is published at the close of bar 3.
    bars = [(100.0, 101.0, 99.0, 100.0)] * 3 + [(100.0, 101.0, 90.0, 100.0)] + \
           [(100.0, 101.0, 99.5, 100.0)] * 6
    series = make_series(bars)
    provider = OneShotProvider(make_plan(entries=((95.0, 1.0),), stop=80.0), at_index=3)
    result = run(series, cfg, provider)
    fills = [e for e in result.events if e.kind is EventKind.FILL]
    assert fills == [], "bar 3 must not fill an order that only existed once bar 3 had closed"


def test_the_next_bar_does_fill_it(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0)] * 4 + [(100.0, 101.0, 90.0, 100.0)] + \
           [(100.0, 101.0, 99.5, 100.0)] * 5
    series = make_series(bars)
    provider = OneShotProvider(make_plan(entries=((95.0, 1.0),), stop=80.0), at_index=3)
    result = run(series, cfg, provider)
    fills = [e for e in result.events if e.kind is EventKind.FILL]
    assert len(fills) == 1 and fills[0].bar_index == 4


def test_pipeline_is_not_called_during_warm_up(cfg):
    series = flat_series(30)
    provider = OneShotProvider(make_plan(), at_index=0)
    run_backtest(series, cfg, plan_provider=provider, warmup_bars=10)
    assert provider.calls == list(range(10, 30))


# ===========================================================================
# 2. THE §12.2 INTRABAR FILL MODEL
# ===========================================================================


def test_a3_limit_needs_a_strict_trade_through(cfg):
    """A bar that merely kisses the limit price does not fill it."""
    touch = [(100.0, 101.0, 99.0, 100.0)] * 2 + [(100.0, 100.5, 95.0, 100.0)] * 4
    series = make_series(touch)
    provider = OneShotProvider(make_plan(entries=((95.0, 1.0),), stop=80.0), at_index=0)
    result = run(series, cfg, provider)
    assert [e for e in result.events if e.kind is EventKind.FILL] == []

    through = [(100.0, 101.0, 99.0, 100.0)] * 2 + [(100.0, 100.5, 94.99, 100.0)] * 4
    result2 = run(make_series(through), cfg,
                  OneShotProvider(make_plan(entries=((95.0, 1.0),), stop=80.0), at_index=0))
    assert len([e for e in result2.events if e.kind is EventKind.FILL]) == 1


def test_a3_can_be_relaxed_by_config(cfg):
    touch = [(100.0, 101.0, 99.0, 100.0)] * 2 + [(100.0, 100.5, 95.0, 100.0)] * 4
    relaxed = cfg.with_overrides(limit_fill_requires_trade_through=False)
    result = run(make_series(touch), relaxed,
                 OneShotProvider(make_plan(entries=((95.0, 1.0),), stop=80.0), at_index=0))
    assert len([e for e in result.events if e.kind is EventKind.FILL]) == 1


def test_a4_maker_fee_on_entry_and_tp_with_no_price_improvement(cfg):
    """Hand-computed: buy 2 @ 95 limit, sell 2 @ 110 limit, maker both sides, no slippage."""
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 90.0, 100.0),     # gaps through the 95 limit -> still fills at 95
            (100.0, 115.0, 99.0, 112.0)]     # trades through TP at 110
    series = make_series(bars)
    plan = make_plan(entries=((95.0, 1.0),), stop=80.0, tps=((110.0, 1.0),), qty=2.0)
    result = run(series, cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]

    assert trade.average_entry == dec(95.0), "A4: a filled limit fills at its own price"
    entry_fee = Decimal("95") * 2 * Decimal("2.0") / 10_000     # 0.038
    exit_fee = Decimal("110") * 2 * Decimal("2.0") / 10_000     # 0.044
    assert trade.fees_usd == entry_fee + exit_fee
    assert trade.gross_pnl_usd == Decimal("30")                 # (110 - 95) * 2
    assert trade.net_pnl_usd == Decimal("30") - entry_fee - exit_fee
    assert trade.close_reason is CloseReason.TP_FINAL


def test_a6_stop_is_market_with_adverse_slippage_and_taker_fee(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),     # fills the 95 entry
            (100.0, 100.5, 89.0, 95.0)]      # takes out the 90 stop
    plan = make_plan(entries=((95.0, 1.0),), stop=90.0, tps=((200.0, 1.0),), qty=1.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]

    # A6: worse of (stop 90, open 100) = 90, then 5.0 bps adverse on a sell.
    expected_exit = Decimal("90") * (Decimal("10000") - Decimal("5.0")) / Decimal("10000")
    assert trade.exit_price == expected_exit
    entry_fee = Decimal("95") * Decimal("2.0") / 10_000
    exit_fee = expected_exit * Decimal("5.5") / 10_000
    assert trade.fees_usd == entry_fee + exit_fee
    assert trade.close_reason is CloseReason.STOP
    assert trade.net_pnl_usd == (expected_exit - Decimal("95")) - entry_fee - exit_fee
    assert trade.r_multiple < Decimal("-1"), "slippage and fees push a stop-out past -1R"


def test_a6_a_gap_through_the_stop_fills_at_the_gapped_open(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),     # entry at 95
            (80.0, 82.0, 78.0, 79.0)]        # gap: opens at 80, far below the 90 stop
    plan = make_plan(entries=((95.0, 1.0),), stop=90.0, tps=((200.0, 1.0),), qty=1.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    expected = Decimal("80") * (Decimal("10000") - Decimal("5.0")) / Decimal("10000")
    assert result.trades[0].exit_price == expected, "no stop is ever honoured better than the market"


def test_a2_same_bar_entry_and_stop_is_a_full_loss(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 85.0, 99.0)]      # one bar trades through the entry AND the stop
    plan = make_plan(entries=((95.0, 1.0),), stop=90.0, tps=((200.0, 1.0),), qty=1.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    assert len(result.trades) == 1, "a same-bar entry-and-stop is a trade, not a skipped setup"
    trade = result.trades[0]
    assert trade.rungs_filled == 1 and trade.close_reason is CloseReason.STOP
    assert trade.net_pnl_usd < Decimal("0")


def test_a1_stop_fills_first_when_one_bar_contains_both_stop_and_tp(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),                 # entry at 95
            (100.0, 130.0, 85.0, 120.0)]                 # contains the 90 stop AND the 110 TP
    plan = make_plan(entries=((95.0, 1.0),), stop=90.0, tps=((110.0, 1.0),), qty=1.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    assert trade.close_reason is CloseReason.STOP, "A1: never assume the favourable order"
    assert trade.tps_hit == 0


def test_a5_trigger_entries_fill_at_the_next_open_with_adverse_slippage(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (103.0, 104.0, 102.0, 103.0),    # the fill bar: opens at 103
            (103.0, 200.0, 102.0, 150.0)]
    plan = make_plan(entries=((95.0, 1.0),), stop=80.0, tps=((150.0, 1.0),), qty=1.0)
    setup = make_setup(plan, family=EntryFamily.TRIGGER)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0, setup=setup))
    trade = result.trades[0]
    expected_entry = Decimal("103") * (Decimal("10000") + Decimal("5.0")) / Decimal("10000")
    assert trade.average_entry == expected_entry
    assert trade.entry_family is EntryFamily.TRIGGER
    entry_fee = expected_entry * Decimal("5.5") / 10_000   # taker
    assert trade.fills[0].fee_usd == entry_fee


def test_a7_an_unfilled_rung_stays_unfilled_and_average_entry_stays_honest(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),     # fills rung 0 at 95, never reaches 90
            (100.0, 130.0, 96.0, 125.0)]     # runs to the TP
    plan = make_plan(entries=((95.0, 0.3), (90.0, 0.7)), stop=85.0, tps=((120.0, 1.0),), qty=10.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    assert trade.rungs_filled == 1 and trade.rungs_planned == 2
    assert trade.qty == dec(10.0) * dec(0.3)
    assert trade.average_entry == dec(95.0), "the unfilled DCA must not move the average"
    assert trade.planned_average_entry != trade.average_entry


def test_the_tp_ladder_trails_to_break_even_then_to_tp1(cfg):
    """CF-29 / S4-R11 / S5-R27: TP1 -> break-even at average entry, TP2 -> TP1's price."""
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),          # entry at 95
            (100.0, 111.0, 100.0, 110.0),         # TP1 at 110 -> stop to break-even (95)
            (111.0, 121.0, 110.5, 120.0),         # TP2 at 120 -> stop to TP1's price (110)
            (120.0, 131.0, 119.0, 130.0)]         # TP3 at 130 -> final, ladder complete
    plan = make_plan(entries=((95.0, 1.0),), stop=90.0,
                     tps=((110.0, 0.4), (120.0, 0.3), (130.0, 0.3)), qty=3.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    assert trade.tps_hit == 3 and trade.full_ladder
    assert trade.close_reason is CloseReason.TP_FINAL
    trails = [e for e in result.events
              if e.kind is EventKind.TRANSITION and "trailed" in e.message]
    assert "break-even at average entry" in trails[0].message
    assert "TP1's price" in trails[1].message


def test_a13_a_trailed_stop_is_live_inside_the_same_bar(cfg):
    """A bar that reaches TP1 and then trades back through break-even books the trail-out."""
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),          # entry at 95
            (100.0, 111.0, 90.0, 96.0)]           # TP1 at 110 and back below 95 in one bar
    plan = make_plan(entries=((95.0, 1.0),), stop=88.0, tps=((110.0, 0.5), (130.0, 0.5)), qty=2.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    assert trade.tps_hit == 1
    assert trade.close_reason is CloseReason.TRAIL_OUT, "a trail-out is a normal, accepted outcome"


def test_a11_funding_is_charged_on_leverage_only(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0)] + [(100.0, 101.0, 99.0, 100.0)] * 30
    series = make_series(bars, tf=Timeframe.H4)
    spot = make_plan(entries=((95.0, 1.0),), stop=50.0, tps=((500.0, 1.0),), qty=1.0,
                     vehicle=Vehicle.SPOT)
    lev = make_plan(plan_id="PLAN-LEV", entries=((95.0, 1.0),), stop=50.0, tps=((500.0, 1.0),),
                    qty=1.0, vehicle=Vehicle.LEVERAGE)
    spot_result = run(series, cfg, OneShotProvider(spot, at_index=0))
    lev_result = run(series, cfg, OneShotProvider(lev, at_index=0))
    assert not [e for e in spot_result.events if e.kind is EventKind.FUNDING]
    funding = [e for e in lev_result.events if e.kind is EventKind.FUNDING]
    assert funding, "a leverage position must accrue funding (A11)"
    assert lev_result.open_at_end[0].unrealised_pnl_usd is not None


def test_expired_plan_never_becomes_a_trade(cfg):
    series = flat_series(20)
    plan = make_plan(entries=((50.0, 1.0),), stop=40.0, expires_at_index=6)
    result = run(series, cfg, OneShotProvider(plan, at_index=0))
    assert result.trades == ()
    expiries = [e for e in result.events if "EXPIRED" in e.message or "expired" in e.message]
    assert expiries and expiries[0].bar_index == 6


def test_fees_are_charged_before_any_metric(cfg):
    """A trade that is flat on price is a *loss* once fees are paid (§12.3)."""
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),
            (96.0, 96.0, 94.5, 95.5)]
    plan = make_plan(entries=((95.0, 1.0),), stop=80.0, tps=((95.5, 1.0),), qty=1.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    assert trade.gross_pnl_usd > Decimal("0")
    assert trade.fees_usd > Decimal("0")
    assert result.ending_equity == result.starting_equity + trade.net_pnl_usd


def test_zero_fee_zero_slippage_config_is_exact(cfg):
    """With every §11.12 cost keyed to zero, the P&L is pure price difference."""
    free = cfg.with_overrides(fee_maker_bps=0.0, fee_taker_bps=0.0, slippage_market_bps=0.0,
                              slippage_limit_bps=0.0)
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),
            (100.0, 121.0, 99.0, 120.0)]
    plan = make_plan(entries=((95.0, 1.0),), stop=80.0, tps=((120.0, 1.0),), qty=3.0)
    result = run(make_series(bars), free, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    assert trade.fees_usd == Decimal(0)
    assert trade.net_pnl_usd == Decimal("75")           # (120 - 95) * 3
    assert trade.r_multiple == Decimal("75") / (Decimal("15") * 3)


# ===========================================================================
# 3. THE EVENT LOG — every trade must be explainable after the fact
# ===========================================================================


def test_every_trade_has_a_complete_tagged_event_chain(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),
            (100.0, 121.0, 99.0, 120.0)]
    plan = make_plan(entries=((95.0, 1.0),), stop=90.0, tps=((110.0, 0.5), (120.0, 0.5)), qty=2.0)
    result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
    trade = result.trades[0]
    chain = result.events.for_trade(trade.ref)
    kinds = {e.kind for e in chain}
    assert {EventKind.PLAN, EventKind.ARM, EventKind.FILL, EventKind.TRANSITION,
            EventKind.EXIT} <= kinds
    assert all(e.source_ids for e in chain), "every event must name the rules behind it"
    assert any("CF-29" in e.source_ids for e in chain)
    assert any("SPEC-12.2-A4" in e.source_ids for e in chain)
    assert result.events.for_trade(trade.id) == chain


def test_detections_and_rejections_are_logged_with_their_reasons(cfg):
    series = flat_series(6)
    plan = make_plan()

    def provider(window: BarWindow, config: Config) -> PipelineOutput:
        if window.now != 2:
            return PipelineOutput()
        vetoed = make_setup(plan)
        vetoed.id = "setup-vetoed"
        vetoed.vetoes.append("G4: mid_range_no_trade_band")
        return PipelineOutput(
            setups=(vetoed,),
            detections=(DetectionRecord(2, "levels", "lvl-9", "sr_level", ("S4-R4",)),),
            rejections=(RejectionRecord(2, "setup-b", "G7", "min_rr not met: 1.4 < 2.0",
                                        source_ids=("CF-42",)),),
        )

    result = run(series, cfg, provider)
    assert len(result.detections) == 1
    assert len(result.rejections) == 2
    gates = {r.gate for r in result.rejections}
    assert gates == {"G4", "G7"}
    assert any("mid_range_no_trade_band" in r.reason for r in result.rejections)
    logged = [e for e in result.events if e.kind is EventKind.REJECTION]
    assert len(logged) == 2 and all(e.source_ids for e in logged)


def test_run_is_deterministic(cfg):
    bars = [(100.0, 101.0, 99.0, 100.0),
            (100.0, 100.5, 94.0, 100.0),
            (100.0, 121.0, 99.0, 120.0)]
    def snapshot():
        plan = make_plan(entries=((95.0, 1.0),), stop=90.0, tps=((110.0, 0.5), (120.0, 0.5)),
                         qty=2.0)
        result = run(make_series(bars), cfg, OneShotProvider(plan, at_index=0))
        return ([(t.id, str(t.net_pnl_usd), str(t.r_multiple)) for t in result.trades],
                [e.render() for e in result.events])

    assert snapshot() == snapshot()


def test_engine_runs_on_the_synthetic_series_with_no_pipeline(cfg):
    """The harness must complete a full pass even when the analysis side produces nothing."""
    series = synthetic(seed=7).series
    result = run_backtest(series, cfg, plan_provider=lambda w, c: PipelineOutput())
    assert result.bars == len(series)
    assert result.trades == ()
    assert result.ending_equity == result.starting_equity
    assert len(result.equity_curve) == len(series)


def test_empty_series_is_refused(cfg):
    with pytest.raises(ValueError):
        BacktestEngine(flat_series(4).slice(0, 0), cfg)
