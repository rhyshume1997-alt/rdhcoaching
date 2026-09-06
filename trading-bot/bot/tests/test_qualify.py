"""Contract tests for tbot.qualify (SPEC.md §7, CF-39/CF-40/CF-41/CF-42/CF-03).

Every gate must produce its **own** structured rejection reason: the backtest attributes rejected
setups by gate, so "returned False" is a bug, not an answer.  Setups and levels are constructed by
hand — nothing here imports ``tbot.detectors``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config
from tbot.confluence import score_at
from tbot.models import (
    Conviction,
    Direction,
    FlipState,
    Level,
    LevelKind,
    Series,
    Setup,
    Timeframe,
    TradeClass,
    Trend,
    Vehicle,
    dec,
)
from tbot.qualify import (
    CalendarEvent,
    Rejection,
    SymbolProfile,
    active_events,
    classify_universe,
    counter_trend_adjustment,
    in_event_window,
    is_btc,
    qualify,
    trade_class_for_tf,
)
from tbot.regime import AllPairsRefs, LevelRead, evaluate_regime

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)          # a Monday
WEDNESDAY = datetime(2024, 1, 3, 12, 0, tzinfo=timezone.utc)
SATURDAY = datetime(2024, 1, 6, 12, 0, tzinfo=timezone.utc)


def make_series(rows, tf: str = "1H", symbol: str = "T") -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1.0] * len(rows), tf=tf, symbol=symbol,
    )


def flat_series(price: float = 100.0, n: int = 60, symbol: str = "SOLUSDT") -> Series:
    return make_series([(price, price + 0.5, price - 0.5, price)] * n, symbol=symbol)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


def a_setup(
    *,
    symbol: str = "SOLUSDT",
    direction: Direction = Direction.LONG,
    trade_tf: Timeframe = Timeframe.H4,
    trade_class: TradeClass = TradeClass.SWING,
    score: float = 3.75,
    classes=("sr_level", "zone", "order_block"),
) -> Setup:
    return Setup(
        id=f"{symbol}:setup",
        symbol=symbol,
        direction=direction,
        trade_tf=trade_tf,
        structure_tf=trade_tf.step(2),
        trade_class=trade_class,
        anchor_price=dec(100.0),
        created_index=50,
        confluence_score=dec(score),
        confluence_classes=set(classes),
    )


def tier_a() -> SymbolProfile:
    return SymbolProfile(
        symbol="SOLUSDT", mcap_rank=5, median_daily_volume_usd=378_000_000, listed_days=900
    )


def passing_kwargs(**extra):
    """The arguments that make every gate pass, so a test can break exactly one of them."""
    base = dict(
        profile=tier_a(),
        now=WEDNESDAY,
        active_symbols=["SOLUSDT"],
        vehicle=Vehicle.LEVERAGE,
        structure_trend=Trend.UP,
        expected_move_pct=8.0,
        rr=3.0,
    )
    base.update(extra)
    return base


# =========================================================================== helpers


class TestHelpers:
    def test_btc_is_recognised_through_its_pairs(self):
        assert is_btc("BTCUSDT") and is_btc("BTC") and is_btc("BTCUSD")
        assert is_btc("SOLUSDT") is False
        assert is_btc("SOLBTC") is False        # an alt's BTC pair is not BTC
        assert is_btc("BTCDOMUSDT") is False

    def test_timeframe_classes_follow_cf38(self, cfg):
        assert trade_class_for_tf(Timeframe.M15, cfg) is TradeClass.SCALP
        assert trade_class_for_tf(Timeframe.H2, cfg) is TradeClass.SCALP
        assert trade_class_for_tf(Timeframe.H4, cfg) is TradeClass.SWING
        assert trade_class_for_tf(Timeframe.D1, cfg) is TradeClass.SWING


# =========================================================================== G1 universe


class TestUniverse:
    def test_tier_a_is_high_cap_high_volume(self, cfg):
        verdict = classify_universe(tier_a(), cfg)
        assert verdict.tier == "A"
        assert verdict.permits(Vehicle.LEVERAGE) and verdict.permits(Vehicle.SPOT)

    def test_thin_volume_is_tier_c_excluded(self, cfg):
        profile = SymbolProfile("XYZUSDT", mcap_rank=40, median_daily_volume_usd=900_000)
        verdict = classify_universe(profile, cfg)
        assert verdict.tier == "C" and verdict.excluded is True
        assert verdict.vehicles == ()

    def test_low_rank_demotes_to_spot_not_out_of_the_universe(self, cfg):
        profile = SymbolProfile("XYZUSDT", mcap_rank=250, median_daily_volume_usd=90_000_000)
        verdict = classify_universe(profile, cfg)
        assert verdict.tier == "B" and verdict.vehicles == (Vehicle.SPOT,)

    def test_memecoins_and_new_listings_are_vehicle_exclusions(self, cfg):
        meme = classify_universe(
            SymbolProfile("PEPEUSDT", mcap_rank=40, median_daily_volume_usd=300_000_000,
                          is_memecoin=True),
            cfg,
        )
        fresh = classify_universe(
            SymbolProfile("NEWUSDT", mcap_rank=40, median_daily_volume_usd=300_000_000,
                          listed_days=5),
            cfg,
        )
        assert meme.tier == "B" and fresh.tier == "B"
        assert all(v.permits(Vehicle.SPOT) for v in (meme, fresh))

    def test_wick_screen_failure_demotes_rather_than_excludes(self, cfg):
        wicky = make_series([(100.0, 108.0, 92.0, 100.2)] * 60, symbol="WICKUSDT")
        verdict = classify_universe(
            SymbolProfile("WICKUSDT", mcap_rank=40, median_daily_volume_usd=300_000_000),
            cfg, series=wicky,
        )
        assert verdict.tier == "B" and verdict.screen is not None

    def test_gate_g1_rejects_tier_c_with_its_own_reason(self, cfg):
        setup = a_setup()
        result = qualify(
            setup, cfg,
            **passing_kwargs(profile=SymbolProfile("SOLUSDT", 4, 100_000)),
        )
        assert result.qualified is False
        assert result.rejection == Rejection(
            "G1", "universe_tier_c", result.rejection.detail, ("CF-40",)
        )
        assert "universe_tier_c" in setup.vetoes

    def test_tier_b_forces_spot_rather_than_vetoing(self, cfg):
        result = qualify(
            a_setup(), cfg,
            **passing_kwargs(
                profile=SymbolProfile("PEPEUSDT", 40, 300_000_000, is_memecoin=True)
            ),
        )
        assert result.qualified is True and result.vehicle is Vehicle.SPOT

    def test_scalp_excludes_btc(self, cfg):
        result = qualify(
            a_setup(symbol="BTCUSDT", trade_tf=Timeframe.H1, trade_class=TradeClass.SCALP),
            cfg,
            **passing_kwargs(profile=SymbolProfile("BTCUSDT", 1, 20_000_000_000, listed_days=900),
                             expected_move_pct=3.0),
        )
        assert result.rejection.gate == "G1"
        assert result.rejection.reason == "scalp_excludes_btc"


# =========================================================================== G2 watchlist


class TestWatchlist:
    def test_full_watchlist_rejects_a_new_symbol(self, cfg):
        result = qualify(
            a_setup(), cfg,
            **passing_kwargs(active_symbols=["ETHUSDT", "AVAXUSDT", "LINKUSDT"]),
        )
        assert result.rejection.reason == "watchlist_full"
        assert result.rejection.gate == "G2"

    def test_a_symbol_already_held_does_not_count_against_the_cap(self, cfg):
        result = qualify(
            a_setup(), cfg,
            **passing_kwargs(active_symbols=["ETHUSDT", "AVAXUSDT", "SOLUSDT"]),
        )
        assert result.qualified is True

    def test_cap_is_the_config_key_not_a_constant(self, cfg):
        wide = cfg.with_overrides(universe_max_symbols=5)
        result = qualify(
            a_setup(), wide,
            **passing_kwargs(active_symbols=["A", "B", "C"]),
        )
        assert result.qualified is True


# =========================================================================== G3/G4 calendar


class TestCalendar:
    def fomc(self, at: datetime = WEDNESDAY) -> CalendarEvent:
        return CalendarEvent(name="FOMC", kind="fomc", start=at)

    def war(self, at: datetime = WEDNESDAY) -> CalendarEvent:
        return CalendarEvent(name="strike on shipping lane", kind="war", start=at)

    def test_active_events_uses_the_blackout_window(self, cfg):
        events = [self.fomc(WEDNESDAY)]
        assert in_event_window(events, WEDNESDAY, cfg) is True
        assert in_event_window(events, WEDNESDAY + timedelta(hours=23), cfg) is True
        assert in_event_window(events, WEDNESDAY + timedelta(hours=30), cfg) is False
        assert active_events(events, WEDNESDAY, cfg) == tuple(events)

    def test_low_impact_events_do_not_blackout(self, cfg):
        events = [CalendarEvent("random webinar", "other", WEDNESDAY)]
        assert in_event_window(events, WEDNESDAY, cfg) is False

    def test_no_leverage_on_fomc(self, cfg):
        setup = a_setup()
        result = qualify(setup, cfg, **passing_kwargs(calendar=[self.fomc()]))
        assert result.rejection.gate == "G3"
        assert result.rejection.reason == "event_blackout"
        assert "FOMC" in result.rejection.detail
        assert setup.vetoes == ["event_blackout"]

    def test_no_leverage_on_war_news(self, cfg):
        result = qualify(a_setup(), cfg, **passing_kwargs(calendar=[self.war()]))
        assert result.rejection.reason == "event_blackout"

    def test_spot_dip_buying_survives_the_event_window(self, cfg):
        result = qualify(
            a_setup(), cfg,
            **passing_kwargs(vehicle=Vehicle.SPOT, calendar=[self.fomc()]),
        )
        assert result.qualified is True
        assert result.vehicle is Vehicle.SPOT
        assert result.required_structure_tf is Timeframe.parse("1D")   # stepped up, S5-R36

    def test_event_days_reject_the_low_timeframes(self, cfg):
        result = qualify(
            a_setup(trade_tf=Timeframe.H1, trade_class=TradeClass.SCALP), cfg,
            **passing_kwargs(vehicle=Vehicle.SPOT, calendar=[self.fomc()],
                             expected_move_pct=3.0),
        )
        assert result.rejection.reason == "event_tf_too_low"

    def test_blackout_mode_all_blocks_spot_too(self, cfg):
        strict = cfg.with_overrides(event_blackout_mode="all")
        result = qualify(
            a_setup(), strict, **passing_kwargs(vehicle=Vehicle.SPOT, calendar=[self.fomc()])
        )
        assert result.rejection.reason == "event_blackout"

    def test_leverage_rearms_only_after_a_post_event_range(self, cfg):
        past = [self.fomc(WEDNESDAY - timedelta(days=4))]
        blocked = qualify(
            a_setup(), cfg,
            **passing_kwargs(calendar=past, range_formed_since_event=False),
        )
        armed = qualify(
            a_setup(), cfg,
            **passing_kwargs(calendar=past, range_formed_since_event=True),
        )
        assert blocked.rejection.reason == "event_blackout"
        assert "range" in blocked.rejection.detail
        assert armed.qualified is True

    def test_weekend_blocks_leverage_but_not_spot(self, cfg):
        blocked = qualify(a_setup(), cfg, **passing_kwargs(now=SATURDAY))
        allowed = qualify(a_setup(), cfg, **passing_kwargs(now=SATURDAY, vehicle=Vehicle.SPOT))
        assert blocked.rejection.gate == "G4"
        assert blocked.rejection.reason == "weekend_blocked"
        assert allowed.qualified is True

    def test_weekend_mode_block_all_stops_spot_as_well(self, cfg):
        strict = cfg.with_overrides(weekend_mode="block_all")
        result = qualify(a_setup(), strict, **passing_kwargs(now=SATURDAY, vehicle=Vehicle.SPOT))
        assert result.rejection.reason == "weekend_blocked"


# =========================================================================== G5 confluence


class TestConfluenceGate:
    def test_thin_object_count_is_rejected_with_its_own_reason(self, cfg):
        """**Q5** — G5 counts raw objects; a thin *count* is the rejection, not a thin score.

        This test used to feed a 3-class setup a score of 2.5 and expect a veto.  It no longer
        vetoes, and that is the point: three objects is three confluences and he takes it (S5
        ``[01:05:33]``, S8 ``[00:53:41]``).  What G5 now rejects is a stack with fewer than
        ``min_confluence_count`` objects, however heavily the §6.1 map happens to weight them.
        """
        thin = qualify(a_setup(score=6.0, classes=("sr_level", "zone")), cfg, **passing_kwargs())
        assert thin.rejection.gate == "G5"
        assert thin.rejection.reason == "insufficient_confluence"

        # The old weighted gate would have passed that 6.0 and vetoed this 2.5.
        assert qualify(a_setup(score=2.5), cfg, **passing_kwargs()).qualified is True

    def test_the_weighted_gate_is_still_reachable_for_sweeps(self, cfg):
        weighted = cfg.with_overrides(confluence_gate_mode="weighted_score")
        assert qualify(a_setup(score=2.5), weighted, **passing_kwargs()).rejection.reason == (
            "insufficient_confluence"
        )
        assert qualify(
            a_setup(score=6.0, classes=("sr_level", "zone")), weighted, **passing_kwargs()
        ).qualified is True

    def test_single_class_is_its_own_reason(self, cfg):
        """Three objects of one class clear the count gate and die on ``single_class`` instead."""
        series = flat_series()
        objs = [
            Level(id=f"l{i}", symbol="SOLUSDT", tf=Timeframe.H4, price=dec(100.0 + i / 100),
                  kind=LevelKind.SUPPORT, created_index=0, source_ids=("S4-R4",))
            for i in range(3)
        ]
        loose = cfg.with_overrides(confluence_dedup_same_class=False)
        cluster = score_at(series, loose, 100.0, objs, at_index=50)
        assert cluster.count == 3
        result = qualify(a_setup(), loose, confluence=cluster, **passing_kwargs())
        assert result.rejection.reason == "single_class"

    def test_a_scored_cluster_can_be_passed_instead_of_raw_numbers(self, cfg):
        series = flat_series()
        level = Level(id="l", symbol="SOLUSDT", tf=Timeframe.H4, price=dec(100.0),
                      kind=LevelKind.SUPPORT, created_index=0, source_ids=("S4-R4",))
        cluster = score_at(series, cfg, 100.0, [level], at_index=50)
        result = qualify(a_setup(), cfg, confluence=cluster, **passing_kwargs())
        assert result.rejection.reason == "insufficient_confluence"
        assert "S4-R4" in result.source_ids

    def test_conviction_floor_is_an_injected_argument(self, cfg):
        result = qualify(
            a_setup(score=3.5), cfg,
            min_conviction=Conviction.HIGH,
            **passing_kwargs(),
        )
        assert result.rejection.reason == "conviction_below_floor"


# =========================================================================== G7 regime


class TestRegimeGate:
    def _risk_off(self, cfg):
        context = {"USDT.D": flat_series(100.0, symbol="USDT.D")}
        return evaluate_regime(
            context, cfg,
            levels={"USDT.D": [LevelRead(price=dec(100.0), role="support")]},
            direction=Direction.LONG,
        )

    def test_risk_off_blocks_a_new_alt_long(self, cfg):
        result = qualify(a_setup(), cfg, regime=self._risk_off(cfg), **passing_kwargs())
        assert result.rejection.gate == "G7"
        assert result.rejection.reason == "regime_veto"

    def test_hard_veto_from_the_context_layer(self, cfg):
        context = {
            "SOLUSDT": flat_series(100.0, symbol="SOLUSDT"),
            "SOLBTC": flat_series(0.002, symbol="SOLBTC"),
            "BTCUSDT": flat_series(60000.0, symbol="BTCUSDT"),
        }
        levels = {
            "SOLUSDT": [LevelRead(price=dec(100.0), role="resistance")],
            "SOLBTC": [LevelRead(price=dec(0.002), role="resistance")],
            "BTCUSDT": [LevelRead(price=dec(60000.0), role="resistance")],
        }
        regime = evaluate_regime(
            context, cfg, levels=levels, direction=Direction.LONG,
            all_pairs=AllPairsRefs("SOLUSDT", "SOLBTC", "BTCUSDT"),
        )
        result = qualify(a_setup(), cfg, regime=regime, **passing_kwargs())
        assert result.rejection.reason == "regime_veto"
        assert "all_pairs_at_resistance" in result.rejection.detail

    def test_missing_context_degrades_to_neutral_and_still_qualifies(self, cfg):
        regime = evaluate_regime({}, cfg, direction=Direction.LONG)
        setup = a_setup()
        result = qualify(setup, cfg, regime=regime, **passing_kwargs())
        assert regime.degraded is True
        assert result.qualified is True
        assert any("degraded to neutral" in n for n in result.notes)
        assert setup.regime_flags["state"] == "neutral"

    def test_bvol_window_reduces_leverage_size_without_vetoing(self, cfg):
        rows = [(v, v + 0.02, v - 0.02, v) for v in (0.6, 0.9)]
        bvol = Series.from_arrays(
            [T0, T0 + timedelta(days=1)],
            [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows],
            [r[3] for r in rows], volume=[1.0, 1.0], tf="1D", symbol="BVOL",
        )
        regime = evaluate_regime({"BVOL": bvol}, cfg, now=T0 + timedelta(days=1))
        result = qualify(a_setup(), cfg, regime=regime, **passing_kwargs())
        assert result.qualified is True
        assert result.size_multiplier == dec(cfg.bvol_size_multiplier)
        assert result.conviction is Conviction.LOW      # adverse but non-vetoing (§6.3)


# =========================================================================== G9/G10 shorts


class TestShortingPolicy:
    def test_never_short_in_price_discovery(self, cfg):
        result = qualify(
            a_setup(direction=Direction.SHORT), cfg,
            price_discovery=True,
            **passing_kwargs(structure_trend=Trend.DOWN),
        )
        assert result.rejection.gate == "G10"
        assert result.rejection.reason == "short_in_price_discovery"

    def test_never_short_at_unbroken_support(self, cfg):
        support = Level(
            id="sup", symbol="SOLUSDT", tf=Timeframe.H4, price=dec(100.0),
            kind=LevelKind.SUPPORT, created_index=0,
        )
        result = qualify(
            a_setup(direction=Direction.SHORT), cfg,
            anchor_level=support,
            **passing_kwargs(structure_trend=Trend.DOWN),
        )
        assert result.rejection.reason == "short_policy"
        assert "unbroken support" in result.rejection.detail

    def test_a_flipped_level_may_be_shorted(self, cfg):
        flipped = Level(
            id="flip", symbol="SOLUSDT", tf=Timeframe.H4, price=dec(100.0),
            kind=LevelKind.SR_CONFIRMED_RESISTANCE, created_index=0,
            flip_state=FlipState.CONFIRMED_RESISTANCE,
        )
        result = qualify(
            a_setup(direction=Direction.SHORT), cfg,
            anchor_level=flipped,
            **passing_kwargs(structure_trend=Trend.DOWN),
        )
        assert result.qualified is True

    def test_never_net_short_in_an_uptrend(self, cfg):
        result = qualify(
            a_setup(direction=Direction.SHORT), cfg,
            would_be_net_short=True,
            **passing_kwargs(structure_trend=Trend.UP),
        )
        assert result.rejection.reason == "short_policy"
        assert "net short" in result.rejection.detail

    def test_shorts_disabled_has_its_own_reason(self, cfg):
        off = cfg.with_overrides(shorts_enabled=False)
        result = qualify(
            a_setup(direction=Direction.SHORT), off, **passing_kwargs(structure_trend=Trend.DOWN)
        )
        assert result.rejection.reason == "shorts_disabled"


# =========================================================================== G14/G15


class TestRiskRewardAndMove:
    def test_rr_below_min_is_rejected(self, cfg):
        result = qualify(a_setup(), cfg, **passing_kwargs(rr=1.0))
        assert result.rejection.gate == "G14"
        assert result.rejection.reason == "rr_below_min"

    def test_f9_the_gate_names_the_basis_it_measured_on(self, cfg):
        """G14's own wording has to say which target the ratio was measured to (CF-42, F9)."""
        assert cfg.rr_measured_to == "final_tp"
        result = qualify(a_setup(), cfg, **passing_kwargs(rr=1.0))
        assert "final_tp" in result.rejection.detail
        assert "average_entry" in result.rejection.detail
        assert "F9" in result.rejection.source_ids

        strict = qualify(a_setup(), cfg.with_overrides(rr_measured_to="tp1"),
                         **passing_kwargs(rr=1.0))
        assert "tp1" in strict.rejection.detail

    def test_f9_the_floor_itself_did_not_move(self, cfg):
        """F9 re-sourced ``min_rr``; it did not change it.  2.13 was the lowest trade observed,
        so 2.0 still sits just under every frame."""
        assert cfg.min_rr == 2.0
        assert qualify(a_setup(), cfg, **passing_kwargs(rr=2.13)).qualified is True
        assert qualify(a_setup(), cfg, **passing_kwargs(rr=1.99)).rejection.gate == "G14"

    def test_expected_move_floor_is_class_scoped(self, cfg):
        swing = qualify(a_setup(), cfg, **passing_kwargs(expected_move_pct=3.0))
        assert swing.rejection.reason == "move_too_small"
        assert "swing" in swing.rejection.detail

        scalp = qualify(
            a_setup(trade_tf=Timeframe.H1, trade_class=TradeClass.SCALP), cfg,
            **passing_kwargs(expected_move_pct=3.0),
        )
        assert scalp.qualified is True


# =========================================================================== other gates


class TestDelegatedGates:
    @pytest.mark.parametrize(
        "kwargs, gate, reason",
        [
            ({"in_mid_range_band": True}, "G6", "mid_range_no_trade"),
            ({"htf_opposes": True}, "G8", "htf_veto"),
            ({"object_dead": True}, "G11", "object_dead"),
            ({"touch_limit_exceeded": True}, "G11", "touch_limit"),
            ({"stop_rejection": "no_stop_anchor"}, "G12", "no_stop_anchor"),
            ({"stop_rejection": "stop_too_wide"}, "G12", "stop_too_wide"),
            ({"stop_rejection": "stop_too_tight"}, "G13", "stop_too_tight"),
            ({"insufficient_tps": True}, "G16", "insufficient_tps"),
            ({"capacity_available": False}, "G17", "capacity"),
            ({"module_disabled": True}, "G18", "module_disabled"),
        ],
    )
    def test_each_gate_has_its_own_structured_reason(self, cfg, kwargs, gate, reason):
        result = qualify(a_setup(), cfg, **kwargs, **passing_kwargs())
        assert result.qualified is False
        assert result.rejection.gate == gate
        assert result.rejection.reason == reason
        assert result.rejection.detail


# =========================================================================== ordering


class TestGateOrdering:
    def test_the_first_veto_stops_evaluation(self, cfg):
        setup = a_setup(score=1.0)
        result = qualify(
            setup, cfg,
            **passing_kwargs(
                profile=SymbolProfile("SOLUSDT", 4, 1_000),      # G1
                active_symbols=["A", "B", "C"],                  # G2
                rr=0.5,                                   # G14
            ),
        )
        assert len(result.rejections) == 1
        assert result.rejection.gate == "G1"
        assert setup.vetoes == ["universe_tier_c"]

    def test_collect_all_reports_every_failing_gate(self, cfg):
        result = qualify(
            a_setup(score=1.0, classes=("sr_level",)), cfg, collect_all=True,
            **passing_kwargs(
                profile=SymbolProfile("SOLUSDT", 4, 1_000),
                active_symbols=["A", "B", "C"],
                rr=0.5,
            ),
        )
        gates = [r.gate for r in result.rejections]
        assert gates == sorted(gates, key=lambda g: int(g[1:]))
        assert {"G1", "G2", "G5", "G14"} <= set(gates)

    def test_a_clean_setup_qualifies_and_records_nothing(self, cfg):
        setup = a_setup()
        result = qualify(setup, cfg, **passing_kwargs())
        assert result.qualified is True
        assert result.rejections == () and setup.vetoes == []
        assert setup.qualified is True
        assert result.size_multiplier == Decimal(1)

    def test_recording_on_the_setup_is_idempotent(self, cfg):
        setup = a_setup(score=1.0, classes=("sr_level",))
        qualify(setup, cfg, **passing_kwargs())
        qualify(setup, cfg, **passing_kwargs())
        assert setup.vetoes == ["insufficient_confluence"]

    def test_record_on_setup_can_be_switched_off(self, cfg):
        setup = a_setup(score=1.0, classes=("sr_level",))
        result = qualify(setup, cfg, record_on_setup=False, **passing_kwargs())
        assert result.qualified is False and setup.vetoes == []


# =========================================================================== CF-03


class TestCounterTrend:
    def test_counter_trend_is_sized_down_and_demoted_never_vetoed(self, cfg):
        setup = a_setup(direction=Direction.LONG)
        result = qualify(setup, cfg, **passing_kwargs(structure_trend=Trend.DOWN))
        assert result.qualified is True
        assert result.counter_trend is True
        assert result.size_multiplier == dec(cfg.counter_trend_size_multiplier)
        assert result.trade_class is TradeClass.SCALP
        assert setup.trade_class is TradeClass.SCALP

    def test_a_neutral_trend_is_not_counter_trend(self, cfg):
        is_ct, multiplier, demote = counter_trend_adjustment(
            Direction.LONG, Trend.NEUTRAL, cfg
        )
        assert is_ct is False and multiplier == Decimal(1) and demote is False
        result = qualify(a_setup(), cfg, **passing_kwargs(structure_trend=Trend.NEUTRAL))
        assert result.counter_trend is False and result.size_multiplier == Decimal(1)

    def test_with_the_trend_takes_no_reduction(self, cfg):
        result = qualify(a_setup(), cfg, **passing_kwargs(structure_trend=Trend.UP))
        assert result.counter_trend is False and result.size_multiplier == Decimal(1)
