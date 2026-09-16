"""Contract tests for tbot.primitives (SPEC.md §4, P1–P20), plus the Series and data contracts.

Every series here is built by hand so the expected answer is obvious by inspection, or comes from
:func:`tbot.data.synthetic`, whose feature indices are known exactly.  A helper builds bars with a
**constant true range of 1.0**, which makes ``ATR(14) == 1.0`` at every bar and therefore makes
every ``*_atr`` threshold in the config exact rather than approximate.

Edge cases covered throughout: empty series, single candle, all-equal prices, and gapped indices.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import dataclasses
import numpy as np
import pandas as pd
import pytest

from tbot.config import Config, ConfigError, KEY_SPECS, KEY_SPEC_BY_NAME
from tbot.data import load_csv, resample, synthetic
from tbot.models import (
    Box,
    ConfluenceClass,
    Direction,
    Level,
    LevelKind,
    Series,
    SwingKind,
    SwingPoint,
    Timeframe,
    Trend,
    ZoneSide,
    dec,
)
import tbot.primitives as P

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- helpers

def make_series(rows, tf: str = "1H", symbol: str = "T", volumes=None, start: datetime = T0) -> Series:
    """Build a Series from ``(open, high, low, close)`` rows, one bar per timeframe step."""
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [start + i * step for i in range(len(rows))]
    vols = list(volumes) if volumes is not None else [1.0] * len(rows)
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=vols, tf=tf, symbol=symbol,
    )


def flat_bars(n: int, price: float = 100.0):
    """``n`` bars with a constant true range of 1.0 and close == open == ``price``.

    ``ATR(any period) == 1.0`` at every bar, so ``level_tolerance_atr=0.15`` is a 0.15 band and
    ``touch_reset_atr=0.5`` is a 0.5 reset — exact, not approximate.
    """
    return [(price, price + 0.5, price - 0.5, price)] * n


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def syn():
    return synthetic(seed=7)


# =========================================================================== Series contract


class TestSeriesContract:
    def test_columns_index_and_derived_arrays(self):
        s = make_series([(10.0, 12.0, 9.0, 11.0), (11.0, 11.5, 8.0, 9.0)])
        assert list(s.frame.columns) == ["open", "high", "low", "close", "volume", "quote_volume"]
        assert s.index.tz is not None and str(s.index.tz) == "UTC"
        assert s.index.is_monotonic_increasing
        assert list(s.body_high) == [11.0, 11.0]
        assert list(s.body_low) == [10.0, 9.0]
        assert list(s.upper_wick) == [1.0, 0.5]
        assert list(s.lower_wick) == [1.0, 1.0]
        assert list(s.is_green) == [True, False]
        assert s.tf is Timeframe.H1 and len(s) == 2

    def test_quote_volume_defaults_to_close_times_volume(self):
        s = make_series([(10.0, 12.0, 9.0, 11.0)], volumes=[3.0])
        assert s.quote_volume[0] == pytest.approx(33.0)

    def test_candle_materialises_decimals(self):
        s = make_series([(10.0, 12.0, 9.0, 11.5)])
        c = s.candle(0)
        assert c.close == Decimal("11.5") and c.body_high == Decimal("11.5")
        assert c.is_closed is True and c.tf is Timeframe.H1
        assert c.close_time - c.open_time == timedelta(hours=1)

    def test_slice_and_head_are_new_series(self):
        s = make_series(flat_bars(5))
        assert len(s.head(3)) == 3 and len(s.slice(1, 4)) == 3
        assert len(s) == 5  # original untouched

    def test_rejects_naive_index(self):
        frame = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0],
                              "volume": [1.0]}, index=pd.DatetimeIndex([datetime(2024, 1, 1)]))
        with pytest.raises(ValueError, match="timezone-aware"):
            Series(frame, tf="1H")

    def test_rejects_unsorted_index_and_bad_bars(self):
        idx = pd.DatetimeIndex([T0 + timedelta(hours=1), T0], tz="UTC")
        frame = pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
                              "close": [1.0, 1.0], "volume": [1.0, 1.0]}, index=idx)
        with pytest.raises(ValueError, match="increasing"):
            Series(frame, tf="1H")
        with pytest.raises(ValueError, match="low <= open/close <= high"):
            make_series([(10.0, 9.0, 11.0, 10.0)])

    def test_gapped_index_is_allowed(self):
        idx = [T0, T0 + timedelta(hours=1), T0 + timedelta(hours=9)]
        s = Series.from_arrays(idx, [1, 1, 1], [2, 2, 2], [0, 0, 0], [1, 1, 1], tf="1H")
        assert len(s) == 3

    def test_timeframe_ladder_step_and_parse(self):
        assert Timeframe.parse("1H").step(2) is Timeframe.H4      # CF-24 default offset
        assert Timeframe.W1.step(5) is Timeframe.W1               # clamped at the top
        assert Timeframe.M15.step(-3) is Timeframe.M15            # clamped at the bottom
        with pytest.raises(ValueError):
            Timeframe.parse("3m")


# =========================================================================== ATR


class TestATR:
    def test_constant_true_range_gives_that_atr(self, cfg):
        s = make_series(flat_bars(40))
        assert float(P.atr_at(s, cfg)) == pytest.approx(1.0)
        assert float(P.atr_at(s, cfg, 0)) == pytest.approx(1.0)

    def test_true_range_uses_previous_close(self):
        s = make_series([(10.0, 11.0, 9.0, 10.0), (20.0, 21.0, 19.0, 20.0)])
        tr = P.true_range(s)
        assert tr[0] == pytest.approx(2.0)
        assert tr[1] == pytest.approx(11.0)          # |21 - 10| dominates the bar's own range

    def test_wilder_smoothing_after_the_seed(self, cfg):
        rows = flat_bars(14) + [(100.0, 105.0, 100.0, 105.0)]
        s = make_series(rows)
        atr = P.atr_array(s, 14)
        assert atr[13] == pytest.approx(1.0)
        assert atr[14] == pytest.approx((1.0 * 13 + 5.0) / 14)

    def test_all_equal_prices_give_zero_atr(self, cfg):
        s = make_series([(100.0, 100.0, 100.0, 100.0)] * 30)
        assert float(P.atr_at(s, cfg)) == 0.0

    def test_single_candle_and_empty(self, cfg):
        one = make_series([(10.0, 12.0, 9.0, 11.0)])
        assert float(P.atr_at(one, cfg)) == pytest.approx(3.0)
        empty = make_series([])
        assert len(P.atr_array(empty, 14)) == 0
        with pytest.raises(ValueError):
            P.atr_at(empty, cfg)


# =========================================================================== P1


class TestP1SwingPoints:
    def test_obvious_pivot_high_and_low(self, cfg):
        # a clean peak at bar 3 and a clean trough at bar 9
        closes = [100, 101, 102, 105, 103, 102, 101, 100, 99, 96, 98, 100, 101]
        rows = [(c - 0.5, c + 1.0, c - 1.5, float(c)) for c in closes]
        s = make_series(rows)
        pivots = P.swing_points(s, cfg)
        highs = [p for p in pivots if p.kind is SwingKind.HIGH]
        lows = [p for p in pivots if p.kind is SwingKind.LOW]
        assert [p.bar_index for p in highs] == [3]
        assert [p.bar_index for p in lows] == [9]
        assert highs[0].price == Decimal("105.0")           # body extreme (S7-R11)
        assert highs[0].wick_price == Decimal("106.0")      # wick extreme, for stops
        assert highs[0].confirmed_at_index == 3 + cfg.swing_k
        assert highs[0].k == cfg.swing_k

    def test_pivot_is_unusable_before_confirmation(self, cfg):
        s = synthetic(seed=3).series
        pivots = P.swing_points(s, cfg)
        p = pivots[0]
        assert p.is_usable_at(p.confirmed_at_index) is True
        assert p.is_usable_at(p.confirmed_at_index - 1) is False
        assert P.confirmed_swings(pivots, p.bar_index) == [
            q for q in pivots if q.confirmed_at_index <= p.bar_index
        ]

    def test_ties_break_toward_the_earlier_bar(self, cfg):
        # two equal body highs at bars 3 and 4: only the earlier one is a pivot
        closes = [100, 101, 102, 105, 105, 102, 101, 100]
        rows = [(c - 0.5, c + 0.5, c - 1.0, float(c)) for c in closes]
        s = make_series(rows)
        highs = [p.bar_index for p in P.swing_points(s, cfg, k=2) if p.kind is SwingKind.HIGH]
        assert highs == [3]

    def test_wick_source_override(self, cfg):
        rows = [(100, 100.5, 99.5, 100)] * 3 + [(100, 110.0, 99.5, 100)] + [(100, 100.5, 99.5, 100)] * 3
        s = make_series([(float(a), float(b), float(c), float(d)) for a, b, c, d in rows])
        assert P.swing_points(s, cfg, source="body") == []          # bodies are all equal
        wick_highs = [p.bar_index for p in P.swing_points(s, cfg, source="wick")
                      if p.kind is SwingKind.HIGH]
        assert wick_highs == [3]

    def test_edge_cases(self, cfg):
        assert P.swing_points(make_series([]), cfg) == []
        assert P.swing_points(make_series(flat_bars(1)), cfg) == []
        assert P.swing_points(make_series(flat_bars(6)), cfg) == []   # shorter than 2k+1
        assert P.swing_points(make_series(flat_bars(30)), cfg) == []  # all-equal prices: no pivots
        with pytest.raises(ValueError):
            P.swing_points(make_series(flat_bars(10)), cfg, k=0)


# =========================================================================== P2


class TestP2DirectionalChange:
    def _impulse(self):
        # 12 quiet bars (ATR = 1.0), one red bar, then a clean 8-point rally
        rows = flat_bars(12)
        rows.append((100.0, 100.2, 99.0, 99.2))                       # the red order-block candle
        price = 99.2
        for _ in range(8):
            rows.append((price, price + 1.05, price - 0.05, price + 1.0))
            price += 1.0
        return make_series(rows)

    def test_qualifying_up_move_names_the_order_block(self, cfg):
        s = self._impulse()
        dc = P.directional_change(s, cfg, 12)
        assert dc is not None
        assert dc.direction is Direction.LONG
        assert dc.order_block_index == 12                    # last red candle before the move
        assert float(dc.move) == pytest.approx(8.0, abs=0.1)
        assert float(dc.move_atr) > cfg.dir_change_atr

    def test_move_below_the_atr_threshold_is_not_a_change(self, cfg):
        rows = flat_bars(12) + [(100.0, 100.6, 99.9, 100.5)] * 5
        s = make_series(rows)
        assert P.directional_change(s, cfg, 12) is None

    def test_deep_retrace_before_the_extreme_disqualifies(self, cfg):
        rows = flat_bars(12) + [(100.0, 100.2, 99.0, 99.2)]
        rows += [(99.2, 104.0, 99.0, 103.5), (103.5, 104.0, 96.0, 97.0), (97.0, 108.0, 97.0, 107.5)]
        s = make_series(rows)
        assert P.directional_change(s, cfg, 12) is None

    def test_last_bar_and_empty_series(self, cfg):
        s = self._impulse()
        assert P.directional_change(s, cfg, len(s) - 1) is None
        assert P.find_directional_changes(make_series([]), cfg) == []

    def test_scan_finds_the_impulse(self, cfg):
        s = self._impulse()
        events = P.find_directional_changes(s, cfg)
        assert events and all(e.direction is Direction.LONG for e in events)


# =========================================================================== P3


class TestP3LevelClustering:
    def _pivots(self, prices_and_bars):
        return [
            SwingPoint(id=f"p{i}", symbol="T", tf=Timeframe.H1, kind=SwingKind.LOW,
                       bar_index=b, price=dec(p), wick_price=dec(p), confirmed_at_index=b + 3, k=3)
            for i, (p, b) in enumerate(prices_and_bars)
        ]

    def test_volume_weighted_cluster_price(self, cfg):
        s = make_series(flat_bars(40), volumes=[1.0] * 40)
        frame = s.frame.copy()
        frame.iloc[10, frame.columns.get_loc("volume")] = 3.0        # weight the second pivot 3x
        s = Series(frame, tf="1H")
        clusters = P.cluster_levels(s, cfg, self._pivots([(100.0, 5), (100.2, 10)]), now_index=39)
        assert len(clusters) == 1
        assert float(clusters[0].price) == pytest.approx((100.0 * 1 + 100.2 * 3) / 4)
        assert clusters[0].touch_seed == 2

    def test_far_pivots_form_separate_clusters_and_singletons_are_dropped(self, cfg):
        s = make_series(flat_bars(40))
        pivots = self._pivots([(100.0, 5), (100.1, 8), (105.0, 12)])
        clusters = P.cluster_levels(s, cfg, pivots, now_index=39)
        assert [float(c.price) for c in clusters] == [pytest.approx(100.05)]

    def test_min_touches_and_lookback_window(self, cfg):
        s = make_series(flat_bars(40))
        pivots = self._pivots([(100.0, 5), (100.1, 8)])
        strict = cfg.with_overrides(level_min_touches=3)
        assert P.cluster_levels(s, strict, pivots, now_index=39) == []
        short = cfg.with_overrides(level_lookback_bars=10)
        assert P.cluster_levels(s, short, pivots, now_index=39) == []

    def test_unconfirmed_pivots_are_invisible(self, cfg):
        s = make_series(flat_bars(40))
        pivots = self._pivots([(100.0, 5), (100.1, 30)])
        assert P.cluster_levels(s, cfg, pivots, now_index=31) == []   # pivot 30 confirms at 33
        assert len(P.cluster_levels(s, cfg, pivots, now_index=33)) == 1

    def test_empty_inputs(self, cfg):
        assert P.cluster_levels(make_series([]), cfg, [], now_index=None) == []
        assert P.cluster_levels(make_series(flat_bars(5)), cfg, []) == []


# =========================================================================== P4


class TestP4TouchCounting:
    def _touch_series(self):
        rows = flat_bars(12, 102.0)                                   # away from the level
        rows += [
            (101.0, 101.2, 99.90, 100.05),   # 12: touch #1
            (100.05, 100.30, 99.95, 100.10),  # 13: same touch (consecutive in band)
            (100.10, 101.60, 100.05, 101.50),  # 14: still intersecting the band
            (101.50, 102.20, 101.40, 102.00),  # 15: left the band by > 0.5 ATR -> re-armed
            (102.00, 102.10, 99.95, 100.02),  # 16: touch #2
            (100.02, 100.10, 99.00, 99.20),   # 17: body close through -> flip machine
            (99.20, 99.50, 98.00, 98.50),     # 18: never reached
        ]
        return make_series(rows)

    def test_counts_sequences_not_bars(self, cfg):
        t = P.count_touches(self._touch_series(), cfg, 100.0, "support", start_index=12)
        assert t.count == 2
        assert [i for i, _ in t.history] == [12, 16]
        assert t.last_touch_index == 16

    def test_body_close_through_ends_the_sequence(self, cfg):
        t = P.count_touches(self._touch_series(), cfg, 100.0, "support", start_index=12)
        assert t.broke is True and t.break_index == 17

    def test_resistance_side_is_mirrored(self, cfg):
        rows = flat_bars(12, 98.0)
        rows += [
            (99.0, 100.10, 98.90, 99.95),     # 12: touch #1 under the level
            (99.95, 100.05, 99.90, 99.98),    # 13: same touch
            (99.98, 99.99, 98.50, 98.60),     # 14: leaves the band
            (98.60, 99.20, 98.40, 98.80),     # 15: still away from the level
            (98.80, 100.05, 98.70, 99.90),    # 16: touch #2
            (99.90, 101.00, 99.80, 100.90),   # 17: body close above -> break
        ]
        t = P.count_touches(make_series(rows), cfg, 100.0, "resistance", start_index=12)
        assert t.count == 2 and t.break_index == 17

    def test_range_boundaries_of_the_synthetic_series(self, cfg, syn):
        f = syn.features
        up = P.count_touches(syn.series, cfg, f.range_high, "resistance",
                             start_index=f.range_start, end_index=f.range_end)
        dn = P.count_touches(syn.series, cfg, f.range_low, "support",
                             start_index=f.range_start, end_index=f.range_end)
        assert up.count == 5 and dn.count == 5 and not up.broke and not dn.broke

    def test_edge_cases(self, cfg):
        assert P.count_touches(make_series([]), cfg, 100.0, "support").count == 0
        one = make_series([(100.0, 100.2, 99.9, 100.05)])
        assert P.count_touches(one, cfg, 100.0, "support").count == 1
        flat = make_series([(100.0, 100.0, 100.0, 100.0)] * 5)        # zero ATR, zero band
        assert P.count_touches(flat, cfg, 100.0, "support").count == 1


# =========================================================================== P5


class TestP5ZoneBox:
    def test_bodies_anchor_the_box_and_small_wicks_are_folded_in(self, cfg):
        # bodies span 100.0-101.0; the wicks beyond them are 0.3 each: small on both P5 tests
        rows = flat_bars(20) + [
            (100.0, 101.3, 99.8, 101.0),
            (101.0, 101.1, 99.7, 100.2),
        ]
        s = make_series(rows)
        box = P.zone_box(s, cfg, 20, 21)
        assert box.included_upper_wick and box.included_lower_wick
        assert float(box.top) == pytest.approx(101.3)
        assert float(box.bottom) == pytest.approx(99.7)
        assert float(box.midpoint) == pytest.approx(100.5)

    def test_giant_wick_is_excluded(self, cfg):
        rows = flat_bars(20) + [(100.0, 130.0, 99.9, 101.0), (101.0, 101.1, 99.95, 100.2)]
        s = make_series(rows)
        box = P.zone_box(s, cfg, 20, 21)
        assert box.included_upper_wick is False
        assert float(box.top) == pytest.approx(101.0)                 # bodies only on that side

    def test_body_only_and_full_range_modes(self, cfg):
        rows = flat_bars(20) + [(100.0, 101.3, 99.7, 101.0)]
        s = make_series(rows)
        body = P.zone_box(s, cfg, 20, 20, source="body_only")
        full = P.zone_box(s, cfg, 20, 20, source="full_range")
        assert (float(body.top), float(body.bottom)) == (pytest.approx(101.0), pytest.approx(100.0))
        assert (float(full.top), float(full.bottom)) == (pytest.approx(101.3), pytest.approx(99.7))

    def test_order_block_box_is_one_candle(self, cfg):
        rows = flat_bars(20) + [(100.0, 101.2, 99.8, 101.0)]
        s = make_series(rows)
        ob = P.order_block_box(s, cfg, 20)
        assert ob.start_index == ob.end_index == 20
        assert float(ob.height) > 1.0

    def test_zone_box_of_the_synthetic_consolidation(self, cfg, syn):
        f = syn.features
        box = P.zone_box(syn.series, cfg, f.consolidation_start, f.consolidation_end)
        assert float(box.top) == pytest.approx(f.zone_top, abs=0.1)
        assert float(box.bottom) == pytest.approx(f.zone_bottom, abs=0.1)

    def test_reversed_window_raises(self, cfg):
        s = make_series(flat_bars(5))
        with pytest.raises(ValueError):
            P.zone_box(s, cfg, 3, 1)


# =========================================================================== P6


class TestP6FillMeasurement:
    def _zone_series(self, deepest_low: float):
        """20 quiet bars, a 100-102 box on bar 20, then one bar dipping to ``deepest_low``."""
        rows = flat_bars(20, 105.0) + [(100.0, 102.0, 100.0, 102.0)]
        rows.append((102.0, 102.5, deepest_low, 102.0))
        return make_series(rows)

    def test_midpoint_is_the_geometric_half(self):
        box = Box(dec(102.0), dec(100.0), 20, 20)
        assert P.midpoint_of(box) == Decimal("101")

    def test_half_depth_penetration_is_fifty_percent_and_kills_the_zone(self, cfg):
        s = self._zone_series(101.0)
        fill = P.measure_fill(s, cfg, Box(dec(102.0), dec(100.0), 20, 20), ZoneSide.DEMAND,
                              from_index=20)
        assert float(fill.fill_pct) == pytest.approx(50.0)
        assert fill.is_dead is True and fill.midpoint_hit is True
        assert fill.deepest_index == 21

    def test_shallow_touch_leaves_the_zone_alive(self, cfg):
        s = self._zone_series(101.6)
        fill = P.measure_fill(s, cfg, Box(dec(102.0), dec(100.0), 20, 20), ZoneSide.DEMAND,
                              from_index=20)
        assert float(fill.fill_pct) == pytest.approx(20.0)
        assert fill.is_dead is False and fill.midpoint_hit is False

    def test_full_pass_through_clamps_at_one_hundred(self, cfg):
        s = self._zone_series(90.0)
        fill = P.measure_fill(s, cfg, Box(dec(102.0), dec(100.0), 20, 20), ZoneSide.DEMAND,
                              from_index=20)
        assert float(fill.fill_pct) == 100.0 and fill.is_dead

    def test_supply_side_measures_from_the_bottom_edge(self, cfg):
        rows = flat_bars(20, 95.0) + [(100.0, 102.0, 100.0, 100.0), (100.0, 101.0, 99.5, 100.5)]
        s = make_series(rows)
        fill = P.measure_fill(s, cfg, Box(dec(102.0), dec(100.0), 20, 20), ZoneSide.SUPPLY,
                              from_index=20)
        assert float(fill.fill_pct) == pytest.approx(50.0)

    def test_close_beyond_measure_is_looser_than_wick_touch(self, cfg):
        s = self._zone_series(101.0)
        loose = cfg.with_overrides(zone_fill_measure="close_beyond")
        box = Box(dec(102.0), dec(100.0), 20, 20)
        assert float(P.measure_fill(s, loose, box, ZoneSide.DEMAND, from_index=20).fill_pct) == 0.0
        assert float(P.measure_fill(s, cfg, box, ZoneSide.DEMAND, from_index=20).fill_pct) == 50.0

    def test_no_bars_after_creation_means_no_fill(self, cfg):
        s = self._zone_series(101.0)
        fill = P.measure_fill(s, cfg, Box(dec(102.0), dec(100.0), 20, 20), ZoneSide.DEMAND,
                              from_index=20, to_index=20)
        assert float(fill.fill_pct) == 0.0 and fill.deepest_index is None

    def test_zero_depth_box_is_safe(self, cfg):
        s = self._zone_series(101.0)
        fill = P.measure_fill(s, cfg, Box(dec(100.0), dec(100.0), 20, 20), ZoneSide.DEMAND,
                              from_index=20)
        assert float(fill.fill_pct) == 0.0


# =========================================================================== P7


class TestP7MidRange:
    def test_geometric_mid_when_no_level_is_near(self, cfg):
        mid = P.mid_range(cfg, 110.0, 100.0)
        assert mid.price == Decimal("105") and mid.source == "geometric"
        # band = 15 % of the 10-point height, each side
        assert (float(mid.band_low), float(mid.band_high)) == (pytest.approx(103.5),
                                                               pytest.approx(106.5))

    def test_nearby_level_with_most_touches_wins(self, cfg):
        near = Level(id="a", symbol="T", tf=Timeframe.H1, price=dec(105.5),
                     kind=LevelKind.SUPPORT, created_index=0, touch_count=4)
        weaker = Level(id="b", symbol="T", tf=Timeframe.H1, price=dec(104.8),
                       kind=LevelKind.SUPPORT, created_index=0, touch_count=2)
        far = Level(id="c", symbol="T", tf=Timeframe.H1, price=dec(108.0),
                    kind=LevelKind.SUPPORT, created_index=0, touch_count=9)
        mid = P.mid_range(cfg, 110.0, 100.0, [near, weaker, far])
        assert mid.price == Decimal("105.5") and mid.source == "level" and mid.level_id == "a"

    def test_no_trade_band_membership(self, cfg):
        mid = P.mid_range(cfg, 110.0, 100.0)
        assert P.in_no_trade_band(105.0, mid) is True
        assert P.in_no_trade_band(103.4, mid) is False
        assert mid.contains(Decimal("106.5")) is True

    def test_inverted_range_raises(self, cfg):
        with pytest.raises(ValueError):
            P.mid_range(cfg, 100.0, 110.0)


# =========================================================================== P8


class TestP8Range:
    def test_synthetic_range_is_valid(self, cfg, syn):
        f = syn.features
        r = P.check_range(syn.series, cfg, f.range_high, f.range_low,
                          start_index=f.range_start, end_index=f.range_end)
        assert r.valid is True
        assert r.upper_touches >= 2 and r.lower_touches >= 2
        assert float(r.height_atr) >= cfg.range_min_height_atr
        assert r.body_close_beyond_index is None and r.stale is False

    def test_window_shorter_than_range_min_bars_fails(self, cfg, syn):
        f = syn.features
        r = P.check_range(syn.series, cfg, f.range_high, f.range_low,
                          start_index=f.range_start, end_index=f.range_start + 5)
        assert r.valid is False
        assert any("range_min_bars" in reason for reason in r.reasons)

    def test_height_below_the_atr_floor_fails(self, cfg, syn):
        f = syn.features
        strict = cfg.with_overrides(range_min_height_atr=99.0)
        r = P.check_range(syn.series, strict, f.range_high, f.range_low,
                          start_index=f.range_start, end_index=f.range_end)
        assert r.valid is False and any("range_min_height_atr" in x for x in r.reasons)

    def test_body_close_beyond_a_boundary_invalidates(self, cfg, syn):
        f = syn.features
        r = P.check_range(syn.series, cfg, f.range_high, f.range_low,
                          start_index=f.range_start, end_index=f.breakout_index)
        assert r.valid is False and r.body_close_beyond_index is not None

    def test_staleness_when_no_recent_touch(self, cfg, syn):
        f = syn.features
        quick = cfg.with_overrides(range_stale_bars=2)
        r = P.check_range(syn.series, quick, f.range_high, f.range_low,
                          start_index=f.range_start, end_index=f.range_end)
        assert r.stale is False       # last touch is the final bar of the range
        r2 = P.check_range(syn.series, quick, f.range_high, f.range_low,
                           start_index=f.range_start, end_index=f.range_end + 5)
        assert r2.stale is True

    def test_empty_series_and_inverted_bounds(self, cfg):
        r = P.check_range(make_series([]), cfg, 110.0, 100.0, start_index=0)
        assert r.valid is False and r.stale is True
        with pytest.raises(ValueError):
            P.check_range(make_series(flat_bars(30)), cfg, 100.0, 110.0, start_index=0)


# =========================================================================== P9


class TestP9Tolerance:
    def test_band_is_level_tolerance_atr(self, cfg):
        s = make_series(flat_bars(30))
        low, high = P.tolerance_band(s, cfg, 100.0)
        assert float(low) == pytest.approx(100.0 - 0.15)
        assert float(high) == pytest.approx(100.0 + 0.15)

    def test_bar_and_price_membership(self, cfg):
        rows = flat_bars(20) + [(101.0, 101.2, 100.10, 101.0), (103.0, 103.2, 102.0, 103.0)]
        s = make_series(rows)
        assert P.bar_at_level(s, cfg, 100.0, 20) is True     # low 100.10 is inside +/-0.15
        assert P.bar_at_level(s, cfg, 100.0, 21) is False
        assert P.price_at_level(s, cfg, 100.10, 100.0) is True
        assert P.price_at_level(s, cfg, 100.40, 100.0) is False


# =========================================================================== P10


class TestP10SufficientGap:
    def _breakout(self):
        rows = flat_bars(10)                                  # ATR = 1.0
        rows.append((100.0, 101.0, 100.0, 101.0))             # bar 10: the breakout close
        price = 101.0
        for _ in range(4):                                    # bars 11-14: +1 each, to 105
            rows.append((price, price + 1.0, price, price + 1.0))
            price += 1.0
        rows.append((105.0, 105.0, 101.0, 101.2))             # bar 15: deep give-back
        rows.append((101.2, 108.0, 101.0, 107.5))             # bar 16: never counted
        return make_series(rows)

    def test_anchor_is_the_breakout_close_and_scan_stops_at_the_retrace(self, cfg):
        s = self._breakout()
        g = P.sufficient_gap(s, cfg, 10, Direction.LONG)
        assert float(g.anchor) == pytest.approx(101.0)
        assert float(g.extreme) == pytest.approx(105.0)
        assert g.extreme_index == 14
        assert float(g.gap_pct) == pytest.approx(4.0 / 101.0 * 100.0)
        assert float(g.gap_atr) == pytest.approx(4.0)

    def test_both_tests_must_pass(self, cfg):
        s = self._breakout()
        table = dict(cfg.sufficient_gap_pct_by_tf)
        easy = cfg.with_overrides(sufficient_gap_pct_by_tf={**table, "1H": 3.0})
        assert P.sufficient_gap(s, easy, 10, Direction.LONG).valid is True

        hard_pct = cfg.with_overrides(sufficient_gap_pct_by_tf={**table, "1H": 9.0})
        res = P.sufficient_gap(s, hard_pct, 10, Direction.LONG)
        assert res.valid is False and any("required on 1H" in r for r in res.reasons)

        hard_atr = cfg.with_overrides(sufficient_gap_pct_by_tf={**table, "1H": 3.0},
                                      sufficient_gap_atr_mult=10.0)
        assert P.sufficient_gap(s, hard_atr, 10, Direction.LONG).valid is False

    def test_percentage_only_mode(self, cfg):
        s = self._breakout()
        table = {**cfg.sufficient_gap_pct_by_tf, "1H": 3.0}
        pct_only = cfg.with_overrides(sufficient_gap_pct_by_tf=table,
                                      sufficient_gap_atr_mult=10.0,
                                      sufficient_gap_require_both_tests=False)
        assert P.sufficient_gap(s, pct_only, 10, Direction.LONG).valid is True

    def test_alternative_anchors_need_the_box(self, cfg):
        s = self._breakout()
        alt = cfg.with_overrides(sufficient_gap_anchor="zone_top_to_extreme")
        with pytest.raises(ValueError):
            P.sufficient_gap(s, alt, 10, Direction.LONG)
        g = P.sufficient_gap(s, alt, 10, Direction.LONG, box=Box(dec(100.0), dec(99.0), 9, 10))
        assert float(g.anchor) == pytest.approx(100.0)

    def test_short_side_measures_downward(self, cfg):
        rows = flat_bars(10)
        rows.append((100.0, 100.0, 99.0, 99.0))
        price = 99.0
        for _ in range(4):
            rows.append((price, price, price - 1.0, price - 1.0))
            price -= 1.0
        s = make_series(rows)
        g = P.sufficient_gap(s, cfg, 10, Direction.SHORT)
        assert float(g.extreme) == pytest.approx(95.0)
        assert float(g.gap_atr) == pytest.approx(4.0)


# =========================================================================== P11


class TestP11Trend:
    def _pivot(self, kind, bar, price):
        return SwingPoint(id=f"{kind.value}{bar}", symbol="T", tf=Timeframe.H1, kind=kind,
                          bar_index=bar, price=dec(price), wick_price=dec(price),
                          confirmed_at_index=bar + 3, k=3)

    def test_higher_highs_and_higher_lows_is_an_uptrend(self, cfg):
        pivots = [self._pivot(SwingKind.LOW, 0, 100), self._pivot(SwingKind.HIGH, 5, 110),
                  self._pivot(SwingKind.LOW, 10, 104), self._pivot(SwingKind.HIGH, 15, 118)]
        assert P.classify_trend(pivots, cfg) is Trend.UP

    def test_mirror_is_a_downtrend(self, cfg):
        pivots = [self._pivot(SwingKind.HIGH, 0, 120), self._pivot(SwingKind.LOW, 5, 110),
                  self._pivot(SwingKind.HIGH, 10, 116), self._pivot(SwingKind.LOW, 15, 104)]
        assert P.classify_trend(pivots, cfg) is Trend.DOWN

    def test_mixed_structure_is_neutral_not_counter_trend(self, cfg):
        pivots = [self._pivot(SwingKind.LOW, 0, 100), self._pivot(SwingKind.HIGH, 5, 110),
                  self._pivot(SwingKind.LOW, 10, 98), self._pivot(SwingKind.HIGH, 15, 118)]
        assert P.classify_trend(pivots, cfg) is Trend.NEUTRAL

    def test_too_few_pivots_is_neutral(self, cfg):
        assert P.classify_trend([], cfg) is Trend.NEUTRAL
        assert P.classify_trend([self._pivot(SwingKind.LOW, 0, 100)], cfg) is Trend.NEUTRAL

    def test_unconfirmed_pivots_are_ignored_at_index(self, cfg):
        pivots = [self._pivot(SwingKind.LOW, 0, 100), self._pivot(SwingKind.HIGH, 5, 110),
                  self._pivot(SwingKind.LOW, 10, 104), self._pivot(SwingKind.HIGH, 15, 118)]
        assert P.classify_trend(pivots, cfg, at_index=12) is Trend.NEUTRAL   # only 3 confirmed
        assert P.classify_trend(pivots, cfg, at_index=18) is Trend.UP


# =========================================================================== P12


class TestP12CapitulationWick:
    def _wick_bar(self, low: float, close: float, volume: float, high: float = 100.5):
        rows = flat_bars(20)
        rows.append((100.0, high, low, close))
        return make_series(rows, volumes=[1.0] * 20 + [volume])

    def test_all_three_tests_passing(self, cfg):
        s = self._wick_bar(low=96.0, close=100.25, volume=5.0)
        assert P.is_capitulation_wick(s, cfg, 20, "lower") is True
        assert P.is_capitulation_wick(s, cfg, 20, "upper") is False

    def test_fails_on_volume(self, cfg):
        s = self._wick_bar(low=96.0, close=100.25, volume=1.0)
        assert P.is_capitulation_wick(s, cfg, 20, "lower") is False

    def test_fails_on_body_ratio(self, cfg):
        s = self._wick_bar(low=96.0, close=102.0, high=102.2, volume=5.0)  # body 2.0, wick 4.0
        assert P.is_capitulation_wick(s, cfg, 20, "lower") is False

    def test_fails_on_atr_size(self, cfg):
        s = self._wick_bar(low=99.5, close=100.1, volume=5.0)
        assert P.is_capitulation_wick(s, cfg, 20, "lower") is False

    def test_scan_reports_bar_and_side(self, cfg):
        s = self._wick_bar(low=96.0, close=100.25, volume=5.0)
        assert P.capitulation_wicks(s, cfg) == [(20, "lower")]
        assert P.capitulation_wicks(make_series(flat_bars(5)), cfg) == []


# =========================================================================== P13


class TestP13Consolidation:
    def test_flat_window_is_horizontal(self, cfg):
        rows = flat_bars(20) + [(100.0, 100.4, 99.6, 100.1), (100.1, 100.5, 99.7, 99.95),
                                (99.95, 100.4, 99.6, 100.05), (100.05, 100.4, 99.7, 100.0)]
        s = make_series(rows)
        check = P.check_consolidation(s, cfg, 20, 23)
        assert check.horizontal is True and check.bars == 4
        assert float(check.drift_atr) < cfg.consolidation_max_drift_atr

    def test_down_drifting_window_is_rejected(self, cfg):
        rows = flat_bars(20)
        price = 100.0
        for _ in range(6):
            rows.append((price, price + 0.1, price - 1.1, price - 1.0))
            price -= 1.0
        s = make_series(rows)
        check = P.check_consolidation(s, cfg, 20, 25)
        assert check.horizontal is False
        assert any("drift" in r or "height" in r for r in check.reasons)

    def test_too_tall_window_is_rejected(self, cfg):
        rows = flat_bars(20) + [(100.0, 106.0, 99.0, 100.5), (100.5, 105.5, 94.0, 100.0)]
        s = make_series(rows)
        assert P.is_horizontal_consolidation(s, cfg, 20, 21) is False

    def test_too_few_bars_is_rejected(self, cfg):
        rows = flat_bars(20) + [(100.0, 100.4, 99.7, 100.1)]
        s = make_series(rows)
        strict = cfg.with_overrides(consolidation_min_bars=3)
        assert P.is_horizontal_consolidation(s, strict, 20, 20) is False

    def test_all_equal_prices_report_zero_atr(self, cfg):
        s = make_series([(100.0, 100.0, 100.0, 100.0)] * 10)
        check = P.check_consolidation(s, cfg, 0, 9)
        assert check.horizontal is False and any("ATR is zero" in r for r in check.reasons)

    def test_synthetic_consolidation_is_horizontal(self, cfg, syn):
        f = syn.features
        assert P.is_horizontal_consolidation(syn.series, cfg, f.consolidation_start,
                                             f.consolidation_end) is True
        assert P.is_horizontal_consolidation(syn.series, cfg, f.impulse_start,
                                             f.impulse_end) is False


# =========================================================================== P14


class TestP14Confluence:
    def _objects(self):
        return [
            P.ConfluenceObject("lvl1", dec(100.00), ConfluenceClass.SR_LEVEL.value,
                               source_ids=("S6-R28",)),
            P.ConfluenceObject("lvl2", dec(100.10), ConfluenceClass.SR_LEVEL.value),
            P.ConfluenceObject("zone1", dec(100.20), ConfluenceClass.ZONE.value),
            P.ConfluenceObject("fib_far", dec(105.00), ConfluenceClass.FIB.value),
        ]

    def test_same_class_counts_once(self, cfg):
        s = make_series(flat_bars(30))
        res = P.score_confluence(s, cfg, 100.0, self._objects())
        assert float(res.score) == pytest.approx(1.5 + 1.25)      # not 1.5 + 1.5 + 1.25
        assert res.classes == {"sr_level", "zone"}
        assert {c.id for c in res.contributors} == {"lvl1", "zone1"}
        assert res.qualified is False                              # 2.75 < min_confluence_count

    def test_third_class_qualifies_the_candidate(self, cfg):
        s = make_series(flat_bars(30))
        objs = self._objects() + [P.ConfluenceObject("ob1", dec(100.15),
                                                     ConfluenceClass.ORDER_BLOCK.value)]
        res = P.score_confluence(s, cfg, 100.0, objs)
        assert float(res.score) == pytest.approx(3.75)
        assert len(res.classes) == 3 and res.qualified is True

    def test_merge_band_excludes_distant_objects(self, cfg):
        s = make_series(flat_bars(30))
        res = P.score_confluence(s, cfg, 100.0, self._objects())
        assert "fib_far" not in {o.id for o in res.merged}          # 5 points away, band is 0.25

    def test_single_class_is_forbidden_even_with_a_big_score(self, cfg):
        s = make_series(flat_bars(30))
        objs = [P.ConfluenceObject("l1", dec(100.0), ConfluenceClass.SR_LEVEL.value,
                                   weight=dec(9.0))]
        res = P.score_confluence(s, cfg, 100.0, objs)
        assert float(res.score) == 9.0 and res.qualified is False
        assert any("single_class_trade_forbidden" in r for r in res.reasons)
        # Q5: dropping single_class_trade_forbidden no longer rescues it — one object is one
        # object, and the gate counts objects.  A 9.0 weight cannot buy a third confluence.
        loose = cfg.with_overrides(single_class_trade_forbidden=False)
        assert P.score_confluence(s, loose, 100.0, objs).qualified is False
        weighted = loose.with_overrides(confluence_gate_mode="weighted_score")
        assert P.score_confluence(s, weighted, 100.0, objs).qualified is True

    def test_continuation_bonus(self, cfg):
        """The CF-10 bonus still moves ``score`` — but Q5 means it cannot buy the gate.

        Under ``confluence_gate_mode = "raw_count"`` a two-object stack stays a two-object stack
        however it is weighted.  The bonus survives where it belongs: ranking and the §6.3
        high-conviction threshold.
        """
        s = make_series(flat_bars(30))
        res = P.score_confluence(s, cfg, 100.0, self._objects(), continuation_zone=True)
        assert float(res.bonus) == pytest.approx(cfg.zone_continuation_confluence_bonus)
        assert float(res.score) == pytest.approx(3.75)
        assert res.count == 2 and res.qualified is False
        weighted = cfg.with_overrides(confluence_gate_mode="weighted_score")
        assert P.score_confluence(
            s, weighted, 100.0, self._objects(), continuation_zone=True
        ).qualified is True

    def test_q5_gate_counts_raw_objects_not_weights(self, cfg):
        """**Q5** — three light objects pass; two heavy ones do not.

        The weighted map was silently rejecting stacks he demonstrably takes.  S5 ``[01:05:33]``:
        golden pocket + trend-line retest + a consolidation point — *"so three. That's why I'm
        taking this one here."*  Under the §6.1 weights that stack scores 1.0 + 0.75 + 1.25 = 3.0
        at best and 2.25 on the reading where the third object is a pattern, i.e. at or below the
        gate.  Meanwhile two heavy objects used to sail through at 2.75+bonus without ever being
        three of anything.
        """
        s = make_series(flat_bars(30))
        light = [
            P.ConfluenceObject("f", dec(100.00), ConfluenceClass.FIB.value),
            P.ConfluenceObject("t", dec(100.05), ConfluenceClass.TRENDLINE.value),
            P.ConfluenceObject("p", dec(100.10), ConfluenceClass.PATTERN.value),
        ]
        res = P.score_confluence(s, cfg, 100.0, light)
        assert float(res.score) == pytest.approx(2.25)     # below min_confluence_count 3.0
        assert res.count == 3 and res.qualified is True    # ...but it is three objects

        weighted = cfg.with_overrides(confluence_gate_mode="weighted_score")
        assert P.score_confluence(s, weighted, 100.0, light).qualified is False

    def test_dedup_can_be_switched_off(self, cfg):
        s = make_series(flat_bars(30))
        loose = cfg.with_overrides(confluence_dedup_same_class=False)
        res = P.score_confluence(s, loose, 100.0, self._objects())
        assert float(res.score) == pytest.approx(1.5 + 1.5 + 1.25)

    def test_unknown_class_scores_zero_and_is_reported(self, cfg):
        s = make_series(flat_bars(30))
        objs = self._objects() + [P.ConfluenceObject("x", dec(100.0), "astrology")]
        res = P.score_confluence(s, cfg, 100.0, objs)
        assert res.unknown_classes == {"astrology"}
        assert float(res.score) == pytest.approx(2.75)

    def test_no_objects_at_all(self, cfg):
        s = make_series(flat_bars(30))
        res = P.score_confluence(s, cfg, 100.0, [])
        assert float(res.score) == 0.0 and res.qualified is False


# =========================================================================== P15


class TestP15Liquidity:
    def test_deepest_wick_through_the_body_range(self, cfg):
        rows = flat_bars(20, 105.0) + [(100.0, 102.0, 100.0, 102.0),
                                       (102.0, 102.5, 100.5, 102.0)]
        s = make_series(rows)
        box = Box(dec(102.0), dec(100.0), 20, 20)
        pct = P.ob_liquidity_taken_pct(s, cfg, box, ZoneSide.DEMAND, from_index=20)
        assert float(pct) == pytest.approx(75.0)

    def test_bearish_block_measures_upward(self, cfg):
        rows = flat_bars(20, 95.0) + [(100.0, 102.0, 100.0, 100.0), (100.0, 101.5, 99.5, 101.0)]
        s = make_series(rows)
        box = Box(dec(102.0), dec(100.0), 20, 20)
        pct = P.ob_liquidity_taken_pct(s, cfg, box, ZoneSide.SUPPLY, from_index=20)
        assert float(pct) == pytest.approx(75.0)

    def test_untouched_block_reports_zero(self, cfg):
        rows = flat_bars(20, 105.0) + [(100.0, 102.0, 100.0, 102.0)]
        s = make_series(rows)
        box = Box(dec(102.0), dec(100.0), 20, 20)
        assert float(P.ob_liquidity_taken_pct(s, cfg, box, ZoneSide.DEMAND, from_index=20)) == 0.0


# =========================================================================== P16


class TestP16Sessions:
    def test_day_start_at_midnight_utc(self, cfg):
        ts = datetime(2024, 3, 5, 13, 45, tzinfo=timezone.utc)
        assert P.day_start(ts, cfg) == datetime(2024, 3, 5, tzinfo=timezone.utc)

    def test_day_start_honours_a_shifted_boundary(self, cfg):
        shifted = cfg.with_overrides(day_boundary_utc="01:00")
        ts = datetime(2024, 3, 5, 0, 30, tzinfo=timezone.utc)
        assert P.day_start(ts, shifted) == datetime(2024, 3, 4, 1, 0, tzinfo=timezone.utc)

    def test_week_starts_on_monday(self, cfg):
        ts = datetime(2024, 3, 6, 9, 0, tzinfo=timezone.utc)          # a Wednesday
        assert P.week_start(ts, cfg) == datetime(2024, 3, 4, tzinfo=timezone.utc)

    def test_weekend_window_is_saturday_to_monday(self, cfg):
        assert P.is_weekend(datetime(2024, 3, 8, 23, 0, tzinfo=timezone.utc), cfg) is False  # Fri
        assert P.is_weekend(datetime(2024, 3, 9, 0, 0, tzinfo=timezone.utc), cfg) is True    # Sat
        assert P.is_weekend(datetime(2024, 3, 10, 23, 59, tzinfo=timezone.utc), cfg) is True  # Sun
        assert P.is_weekend(datetime(2024, 3, 11, 0, 1, tzinfo=timezone.utc), cfg) is False  # Mon

    def test_same_session(self, cfg):
        a = datetime(2024, 3, 5, 1, 0, tzinfo=timezone.utc)
        b = datetime(2024, 3, 5, 23, 0, tzinfo=timezone.utc)
        c = datetime(2024, 3, 6, 0, 1, tzinfo=timezone.utc)
        assert P.same_session(a, b, cfg) is True
        assert P.same_session(b, c, cfg) is False

    def test_naive_timestamps_are_rejected(self, cfg):
        with pytest.raises(ValueError):
            P.day_start(datetime(2024, 3, 5), cfg)


# =========================================================================== P17


class TestP17StaleTrade:
    def test_off_by_default(self, cfg):
        assert P.is_stale_trade(cfg, bars_in_trade=99, mfe_atr=0.0, mae_atr=5.0, tps_hit=0) is False

    def test_all_conditions_true_when_enabled(self, cfg):
        on = cfg.with_overrides(stale_exit_enabled=True)
        assert P.is_stale_trade(on, bars_in_trade=8, mfe_atr=0.5, mae_atr=1.0, tps_hit=0) is True

    @pytest.mark.parametrize("kwargs", [
        dict(bars_in_trade=7, mfe_atr=0.5, mae_atr=1.0, tps_hit=0),   # too soon
        dict(bars_in_trade=8, mfe_atr=1.0, mae_atr=1.0, tps_hit=0),   # it did react
        dict(bars_in_trade=8, mfe_atr=0.5, mae_atr=0.5, tps_hit=0),   # no adverse excursion
        dict(bars_in_trade=8, mfe_atr=0.5, mae_atr=1.0, tps_hit=1),   # a TP already hit
    ])
    def test_every_condition_is_necessary(self, cfg, kwargs):
        on = cfg.with_overrides(stale_exit_enabled=True)
        assert P.is_stale_trade(on, **kwargs) is False


# =========================================================================== P18


class TestP18LiquidityScreen:
    def test_clean_liquid_series_is_tier_a(self, cfg, syn):
        screen = P.liquidity_screen(syn.series, cfg)
        assert screen.passes is True and screen.tier == "A" and screen.wick_heavy is False

    def test_thin_volume_demotes_to_spot_only(self, cfg, syn):
        screen = P.liquidity_screen(syn.series, cfg, median_quote_volume_usd=1_000.0)
        assert screen.passes is False and screen.tier == "B"
        assert any("min_daily_volume_usd" in r for r in screen.reasons)
        assert screen.wick_heavy is False          # thin, but not wicky

    def test_wick_heavy_series_is_flagged(self, cfg):
        rows = [(100.0, 106.0, 94.0, 100.2), (100.2, 106.0, 94.0, 100.0)] * 50
        s = make_series(rows, volumes=[1e9] * 100)
        screen = P.liquidity_screen(s, cfg)
        assert screen.wick_heavy is True and screen.tier == "B"
        assert float(screen.median_wick_ratio) > cfg.max_median_wick_ratio

    def test_empty_series_fails_closed(self, cfg):
        screen = P.liquidity_screen(make_series([]), cfg)
        assert screen.passes is False and screen.tier == "B"


# =========================================================================== P19


class TestP19StopBuffer:
    def test_buffer_is_stop_buffer_atr(self, cfg):
        s = make_series(flat_bars(30))
        assert float(P.stop_buffer(s, cfg)) == pytest.approx(0.15)

    def test_buffer_is_applied_beyond_the_anchor(self, cfg):
        assert P.apply_stop_buffer(100.0, Direction.LONG, 0.15) == Decimal("99.85")
        assert P.apply_stop_buffer(100.0, Direction.SHORT, 0.15) == Decimal("100.15")

    def test_zero_atr_series_gives_zero_buffer(self, cfg):
        s = make_series([(100.0, 100.0, 100.0, 100.0)] * 20)
        assert float(P.stop_buffer(s, cfg)) == 0.0


# =========================================================================== P20


class TestP20PointsOfMostTouch:
    def _series_with_overlap(self):
        """20 quiet bars, then 1 bar spanning the whole 100-102 box and 3 bars hugging 101.0-101.2."""
        rows = flat_bars(20, 105.0)
        rows.append((100.1, 102.0, 100.0, 101.9))
        rows += [(101.05, 101.2, 101.0, 101.15)] * 3
        return make_series(rows)

    def test_entry_lands_in_the_most_touched_shelf(self, cfg):
        s = self._series_with_overlap()
        box = Box(dec(102.0), dec(100.0), 20, 20)
        res = P.points_of_most_touch(s, cfg, box, ZoneSide.DEMAND, [(20, 23)])
        assert 100.95 <= float(res.price) <= 101.25
        assert max(res.counts) == 4
        expected = float(P.atr_at(s, cfg)) * cfg.pmt_bin_atr
        assert float(res.bin_width) == pytest.approx(expected, rel=0.25)

    def test_ties_break_toward_the_outer_edge(self, cfg):
        rows = flat_bars(20, 105.0)
        rows.append((100.05, 100.5, 100.0, 100.4))       # lower shelf, one bar
        rows.append((101.6, 102.0, 101.5, 101.9))        # upper shelf, one bar
        s = make_series(rows)
        box = Box(dec(102.0), dec(100.0), 20, 21)
        demand = P.points_of_most_touch(s, cfg, box, ZoneSide.DEMAND, [(20, 21)])
        supply = P.points_of_most_touch(s, cfg, box, ZoneSide.SUPPLY, [(20, 21)])
        assert float(demand.price) > 101.5               # nearest the top edge for demand
        assert float(supply.price) < 100.5               # nearest the bottom edge for supply

    def test_multiple_windows_accumulate(self, cfg):
        s = self._series_with_overlap()
        box = Box(dec(102.0), dec(100.0), 20, 20)
        one = P.points_of_most_touch(s, cfg, box, ZoneSide.DEMAND, [(21, 21)])
        many = P.points_of_most_touch(s, cfg, box, ZoneSide.DEMAND, [(21, 21), (22, 23)])
        assert max(many.counts) == max(one.counts) + 2

    def test_requires_at_least_one_window(self, cfg):
        s = self._series_with_overlap()
        with pytest.raises(ValueError):
            P.points_of_most_touch(s, cfg, Box(dec(102.0), dec(100.0), 20, 20),
                                   ZoneSide.DEMAND, [])


# =========================================================================== config & data


class TestConfig:
    def test_every_spec_key_is_present_with_its_default(self):
        cfg = Config.load()
        assert len(KEY_SPECS) == 254
        assert len(cfg.describe()) == 254
        assert cfg.swing_k == 3 and cfg.min_confluence_count == 3.0
        assert cfg.zone_fill_invalidation_pct == 50.0
        assert cfg.touch_size_decay == [1.0, 1.0, 1.0, 0.66, 0.5]   # Q2

    def test_config_has_exactly_one_set_of_defaults(self):
        """``Config()`` and ``Config.load(None)`` must be the same object in every field.

        There are two declarations of every default: the dataclass field on :class:`Config`, and
        ``default=`` on its :data:`KEY_SPECS` entry, which ``Config.load`` reads through
        ``defaults_dict()``.  Nothing forced them to agree, and they drifted: two keys corrected
        against the corpus (``dca_size_split_3`` to the stated 15/32.5/52.5 split, and
        ``tp_count_swing`` to 3) had the spec updated and the field left on the superseded value.

        The damage was silent and one-sided.  ``tbot backtest`` builds its config through
        ``Config.load`` and got the corrected values; **every test and every in-process script
        that wrote ``Config()`` got the stale ones**, so the corrections went unverified at their
        real settings while two callers measured different bots from the same CSV — 4 closed
        trades against 6 on one 700-bar window, which is what sent a whole session hunting a
        determinism bug that did not exist.

        ``non_default_keys()`` had been reporting it all along: a freshly defaulted config
        listing two non-default keys.  This asserts the invariant that diagnostic implies.
        """
        fresh, loaded = Config(), Config.load(None)
        drifted = [f.name for f in dataclasses.fields(Config)
                   if getattr(fresh, f.name) != getattr(loaded, f.name)]
        assert not drifted, (
            f"dataclass field default disagrees with its KEY_SPEC default: {drifted}. "
            f"KEY_SPEC is authoritative - it carries the source id; fix the field.")
        assert fresh.non_default_keys() == [], (
            "a freshly constructed Config reports non-default keys, so its own fields disagree "
            "with the spec it is checked against")

    def test_frame_derived_keys_are_present_and_default_off(self):
        """F1 — FRAME_FINDINGS.md: the nested-zone geometry ships behind a flag, defaulted off."""
        cfg = Config.load()
        assert cfg.zone_wick_band_enabled is False
        assert cfg.zone_wick_band_max_ratio == 1.0
        spec = KEY_SPEC_BY_NAME["zone_wick_band_enabled"]
        assert spec.source_id.startswith("F1")
        assert "SINGLE-FRAME OBSERVATION" in spec.source_id
        assert "52:38" in spec.source_id                      # the frame it came from
        # pass 2 weakened F1 without flipping anything: the flag is still off, and the note now
        # records that the one clear example was measured mid-drag.
        assert "MID-DRAG" in spec.note.upper()
        assert "ONE FRAME IN FOUR" in spec.note.upper()

    def test_the_pass_two_stop_buffer_key_is_present_and_sourced(self):
        """F6 — stop distance is a fraction of the ZONE HEIGHT.  The NUMBER is disputed.

        The independent measurement pass (docs/measurement/) withdrew this rule from the same
        three frames, so the default is retained as an engineering choice pending a sweep on
        real data, not as an evidenced value.  The bracket now reaches 0.0 — snap the stop to
        the structural level and model no overshoot — which is that pass's own position.
        """
        cfg = Config.load()
        assert cfg.stop_buffer_zone_fraction == 0.5
        assert cfg.stop_buffer_atr == 0.15                    # kept, as the non-zone fallback
        spec = KEY_SPEC_BY_NAME["stop_buffer_zone_fraction"]
        assert spec.source_id.startswith("F6")
        for frame in ("TBOT1 4:11", "TBOT1 1:09:19", "S8 1:28:33"):
            assert frame in spec.source_id                    # three independent frames
        assert spec.sweep_bracket == (0.0, 0.60)
        assert "DISPUTED" in spec.source_id
        assert "FALLBACK" in KEY_SPEC_BY_NAME["stop_buffer_atr"].note.upper()

    def test_f9_rr_is_measured_to_the_final_take_profit(self):
        """F9 — his position tool's R:R reads to its single TARGET line, not to a first partial.

        Four frames of that readout: 3.17 (TBOT1 4:11), 5.00 (TBOT1 22:59), 2.97
        (TBOT1 1:09:19), 2.13 (S8 1:28:33).  The bot ladders 2-5 structural TPs and TP1 is the
        NEAREST of them, so the old ``tp1`` basis gated far above where he trades.
        """
        cfg = Config.load()
        assert cfg.rr_measured_to == "final_tp"
        assert cfg.rr_measured_from == "average_entry"     # CF-18, unchanged
        spec = KEY_SPEC_BY_NAME["rr_measured_to"]
        assert spec.default == "final_tp"
        assert set(spec.members) == {"tp1", "final_tp"}    # the alternative is still recorded
        assert "F9" in spec.source_id
        for frame in ("TBOT1 4:11", "TBOT1 22:59", "TBOT1 1:09:19", "S8 1:28:33"):
            assert frame in spec.source_id
        # Provenance honesty: the measurement convention is OUR reading of TradingView.
        assert "OUR reading of TradingView" in spec.note

    def test_f9_min_rr_is_unchanged_but_no_longer_a_bare_invention(self):
        """The floor stays 2.0; what changes is that four observed trades now stand under it."""
        cfg = Config.load()
        assert cfg.min_rr == 2.0
        spec = KEY_SPEC_BY_NAME["min_rr"]
        assert spec.default == 2.0
        assert "corroborated" in spec.source_id            # no longer a pure [OUR CHOICE]
        assert "F9" in spec.source_id
        for observed in ("2.13", "2.97", "3.17", "5.00"):
            assert observed in spec.note                   # the whole observed range
        assert spec.sweep_bracket == (2.0, 2.5)

    def test_f9_constant_cash_risk_corroborates_the_risk_first_sizing_model(self):
        """F9 part B, CORRECTED — the constant cash risk is **$250**, not $750.

        "Amount" is the account BALANCE at that leg on a $1,000 nominal base, so a stop-leg
        Amount of 750 means $250 of risk.  Five frames confirm it (Amount-1000 reproduces
        qty x target distance) and all eight give qty x stop distance = 250.00.  What is
        corroborated is unchanged: the *model*, solve quantity backwards from the loss at stop,
        never the percentage.  The portfolio inference that rested on $750 is withdrawn.
        """
        for key in ("max_loss_pct_swing", "max_loss_pct_swing_hard_cap"):
            spec = KEY_SPEC_BY_NAME[key]
            assert "F9" in spec.source_id
            assert "CORRECTED" in spec.note
            assert "1000 - Amount(stop leg) = $250" in spec.note
            assert "account size" in spec.note
            # the inference is kept ONLY as an explicit withdrawal, never as a live figure
            assert "15,000-18,750 is WITHDRAWN" in spec.note
        # No account-size key was derived from it then, and none is derived from it now.
        assert len(KEY_SPECS) == 254
        assert not [k for k in KEY_SPEC_BY_NAME if "account_size" in k or "portfolio_size" in k]

    def test_sweep_brackets_are_machine_readable_where_evidence_bounded_them(self):
        """A sweep reads its search range off the config, not out of prose."""
        brackets = {s.key: s.sweep_bracket for s in KEY_SPECS if s.sweep_bracket is not None}
        assert brackets["dca_size_split_2"] == (0.32, 0.40)     # F2, three worked examples
        assert brackets["swing_k"] == (2.0, 4.0)                # F4, S7 frame 34:30 bounds it at 4
        # F1 pass 2: the same drawing re-read at 0.33, so the bracket spans both readings.
        assert brackets["zone_wick_band_max_ratio"] == (0.30, 1.00)
        # F6 pass 2: three frames at 0.48 / 0.49 / 0.58 zone-heights, DISPUTED by the
        # independent measurement pass.  0.0 is that pass's position (snap to the structural
        # level, no overshoot) and has to be reachable by the sweep.
        assert brackets["stop_buffer_zone_fraction"] == (0.0, 0.60)
        # F9: four observed R:R readouts, 2.13-5.00, with 2.13 the lowest trade he took.
        assert brackets["min_rr"] == (2.0, 2.5)
        for key, (low, high) in brackets.items():
            assert low <= high, key
            spec = KEY_SPEC_BY_NAME[key]
            if spec.minimum is not None:
                assert low >= spec.minimum, key
            if spec.maximum is not None:
                assert high <= spec.maximum, key
        # F5 is a negative result: no bracket is derivable, so none is recorded.
        assert KEY_SPEC_BY_NAME["sufficient_gap_pct_by_tf"].sweep_bracket is None
        assert "hand-drawn" in KEY_SPEC_BY_NAME["sufficient_gap_pct_by_tf"].note.lower()

    def test_the_default_value_sits_inside_its_own_sweep_bracket(self):
        """A bracket that excludes the shipped default would mean the default is unreachable."""
        for spec in KEY_SPECS:
            if spec.sweep_bracket is None:
                continue
            low, high = spec.sweep_bracket
            value = spec.default[0] if isinstance(spec.default, list) else spec.default
            assert low <= float(value) <= high, spec.key

    def test_describe_carries_source_ids(self):
        rows = {k: (v, d, src) for k, v, d, src in Config.load().describe()}
        assert "CF-08" in rows["zone_fill_invalidation_pct"][2]
        assert "OUR CHOICE" in rows["swing_k"][2]

    def test_yaml_overrides_are_deep_merged(self, tmp_path):
        path = tmp_path / "over.yaml"
        path.write_text("swing_k: 5\nsufficient_gap_pct_by_tf:\n  1H: 9.5\n")
        cfg = Config.load(path)
        assert cfg.swing_k == 5
        assert cfg.sufficient_gap_pct_by_tf["1H"] == 9.5
        assert cfg.sufficient_gap_pct_by_tf["1D"] == 8.0        # untouched rows survive
        assert cfg.atr_period == 14
        assert cfg.non_default_keys() == ["sufficient_gap_pct_by_tf", "swing_k"] or set(
            cfg.non_default_keys()) == {"swing_k", "sufficient_gap_pct_by_tf"}

    def test_validation_reports_every_problem_at_once(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "swing_k: -1\n"
            "zone_fill_measure: \"telepathy\"\n"
            "max_loss_pct_swing: 400\n"
            "tp_split_2: [0.5, 0.9]\n"
            "not_a_real_key: 1\n"
        )
        with pytest.raises(ConfigError) as err:
            Config.load(path)
        problems = err.value.problems
        assert len(problems) >= 5
        joined = "\n".join(problems)
        for fragment in ("swing_k", "zone_fill_measure", "max_loss_pct_swing", "tp_split_2",
                         "not_a_real_key"):
            assert fragment in joined

    def test_default_yaml_file_round_trips(self):
        from pathlib import Path
        default = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"
        assert Config.load(default).to_dict() == Config.load().to_dict()

    def test_config_is_frozen(self):
        cfg = Config.load()
        with pytest.raises(Exception):
            cfg.swing_k = 9  # type: ignore[misc]


class TestData:
    def test_csv_round_trip(self, tmp_path):
        path = tmp_path / "ohlcv.csv"
        path.write_text(
            "timestamp,open,high,low,close,volume\n"
            "2024-01-01T00:00:00Z,100,101,99,100.5,10\n"
            "2024-01-01T01:00:00Z,100.5,102,100,101.5,12\n"
        )
        s = load_csv(path, tf="1H", symbol="BTCUSDT")
        assert len(s) == 2 and s.symbol == "BTCUSDT"
        assert s.close[-1] == pytest.approx(101.5)
        assert s.quote_volume[0] == pytest.approx(1005.0)

    def test_resample_aggregates_correctly(self, cfg):
        rows = [(float(i), float(i) + 2, float(i) - 1, float(i) + 1) for i in range(8)]
        s = make_series(rows, tf="1H")
        up = resample(s, "4H", cfg)
        assert len(up) == 2
        assert up.open[0] == pytest.approx(0.0)
        assert up.high[0] == pytest.approx(5.0)
        assert up.low[0] == pytest.approx(-1.0)
        assert up.close[0] == pytest.approx(4.0)
        assert up.volume[0] == pytest.approx(4.0)

    def test_resample_refuses_to_go_down_the_ladder(self, cfg):
        s = make_series(flat_bars(4), tf="4H")
        with pytest.raises(ValueError):
            resample(s, "1H", cfg)

    def test_synthetic_is_deterministic(self):
        a, b = synthetic(seed=11), synthetic(seed=11)
        assert np.array_equal(a.series.close, b.series.close)
        assert np.array_equal(a.series.high, b.series.high)
        assert a.features == b.features
        other = synthetic(seed=12)
        assert np.array_equal(a.series.close, other.series.close)      # structure is seed-free
        assert not np.array_equal(a.series.high, other.series.high)    # only the noise moves

    def test_synthetic_embeds_the_advertised_features(self, cfg, syn):
        s, f = syn.series, syn.features
        assert len(s) == f.total_bars

        # the range
        r = P.check_range(s, cfg, f.range_high, f.range_low,
                          start_index=f.range_start, end_index=f.range_end)
        assert r.valid is True

        # impulse -> consolidation -> breakout, i.e. a continuation demand zone
        assert P.is_horizontal_consolidation(s, cfg, f.consolidation_start, f.consolidation_end)
        box = P.zone_box(s, cfg, f.consolidation_start, f.consolidation_end)
        gap = P.sufficient_gap(s, cfg, f.breakout_index, Direction.LONG)
        assert gap.valid is True
        depth_atr = float(box.height) / float(P.atr_at(s, cfg, f.consolidation_end))
        assert cfg.min_zone_depth_atr <= depth_atr <= cfg.max_zone_depth_atr

        # the zone is retested but survives (fill well under the 50 % invalidation)
        fill = P.measure_fill(s, cfg, box, ZoneSide.DEMAND, from_index=f.breakout_index)
        assert 0.0 < float(fill.fill_pct) < cfg.zone_fill_invalidation_pct
        assert fill.is_dead is False

        # the order block: the last red candle before the directional change
        dc = P.directional_change(s, cfg, f.order_block_index)
        assert dc is not None and dc.direction is Direction.LONG
        assert dc.order_block_index == f.order_block_index
        assert bool(s.is_green[f.order_block_index]) is False

        # the swing failure: wick through the prior swing high, body closing back below it
        assert s.high[f.sfp_index] > f.sfp_swing_price
        assert s.close[f.sfp_index] < f.sfp_swing_price


# =========================================================================== INTERFACES.md


class TestInterfacesWorkedExamples:
    """Pins every number printed in the worked examples of ``tbot/INTERFACES.md`` §8.

    If one of these fails, the documentation other agents are coding against is wrong: fix both.
    """

    def test_example_8_1_zone_box_and_fill(self, cfg, syn):
        s, f = syn.series, syn.features
        box = P.zone_box(s, cfg, f.consolidation_start, f.consolidation_end)
        assert float(box.top) == pytest.approx(120.94370385130748)
        assert float(box.bottom) == pytest.approx(119.05193245776317)
        assert float(box.midpoint) == pytest.approx(119.997818154535325)
        fill = P.measure_fill(s, cfg, box, ZoneSide.DEMAND, from_index=f.breakout_index)
        assert float(fill.fill_pct) == pytest.approx(19.96, abs=0.01)
        assert fill.is_dead is False and fill.midpoint_hit is False
        assert fill.deepest_index == 95

    def test_example_8_2_sufficient_gap(self, cfg, syn):
        s, f = syn.series, syn.features
        assert f.breakout_index == 76
        g = P.sufficient_gap(s, cfg, f.breakout_index, Direction.LONG)
        assert float(g.anchor) == pytest.approx(123.1)
        assert float(g.extreme) == pytest.approx(138.544, abs=0.01)
        assert g.extreme_index == 84
        assert float(g.gap_pct) == pytest.approx(12.55, abs=0.01)
        assert float(g.gap_atr) == pytest.approx(7.81, abs=0.01)
        assert float(g.required_pct) == 4.0 and g.valid is True and g.reasons == ()

    def test_example_8_3_touch_counting(self, cfg, syn):
        s, f = syn.series, syn.features
        t = P.count_touches(s, cfg, f.range_high, "resistance",
                            start_index=f.range_start, end_index=f.range_end)
        assert t.count == 5
        assert [i for i, _ in t.history] == [23, 31, 39, 47, 55]
        assert t.break_index is None
        assert P.count_touches(s, cfg, f.range_high, "resistance",
                               start_index=f.range_start).break_index == 60

    def test_example_8_4_confluence(self, cfg, syn):
        s = syn.series
        objs = [
            P.ConfluenceObject("lvl-a", dec(120.90), "sr_level", source_ids=("S4-R4",)),
            P.ConfluenceObject("lvl-b", dec(121.00), "sr_level"),
            P.ConfluenceObject("zone-1", dec(120.80), "zone", source_ids=("CF-10", "S5-R15")),
            P.ConfluenceObject("ob-59", dec(120.95), "order_block"),
            P.ConfluenceObject("fib-gp", dec(133.00), "fib"),
        ]
        r = P.score_confluence(s, cfg, 120.90, objs, at_index=90)
        assert float(r.score) == pytest.approx(3.75)
        assert r.classes == {"sr_level", "zone", "order_block"}
        assert [c.id for c in r.contributors] == ["lvl-a", "zone-1", "ob-59"]
        assert len(r.merged) == 4 and r.qualified is True
        boosted = P.score_confluence(s, cfg, 120.90, objs, at_index=90, continuation_zone=True)
        assert float(boosted.score) == pytest.approx(4.75)
        assert float(boosted.score) >= cfg.high_conviction_score

    def test_example_8_5_points_of_most_touch(self, cfg, syn):
        s, f = syn.series, syn.features
        box = P.zone_box(s, cfg, f.consolidation_start, f.consolidation_end)
        pmt = P.points_of_most_touch(
            s, cfg, box, ZoneSide.DEMAND,
            windows=[(f.consolidation_start, f.consolidation_end),
                     (f.retest_index, f.retest_index + 3)],
            at_index=95,
        )
        assert float(pmt.price) == pytest.approx(120.088, abs=0.001)
        assert float(pmt.bin_width) == pytest.approx(0.0901, abs=0.0001)
        assert len(pmt.counts) == 21 and pmt.winning_bin == 11
        assert float(P.atr_at(s, cfg, 95)) == pytest.approx(1.791, abs=0.001)

    def test_config_ownership_table_covers_every_key(self):
        """The §7 ownership tables must list all 254 keys exactly once."""
        import re
        from pathlib import Path
        doc = (Path(__file__).resolve().parent.parent / "tbot" / "INTERFACES.md").read_text()
        section = doc.split("## 7 Config key ownership by module")[1].split("## 8 Worked")[0]
        listed = re.findall(r"^\| `([a-z0-9_]+)` \|", section, re.M)
        assert len(listed) == len(set(listed)) == 254
        assert set(listed) == {spec.key for spec in KEY_SPECS}


# ------------------------------- A1: align_series, the common bar grid (GAPS.md GAP 3 A1)
#
# Cross-symbol maths needs a shared timestamp index and the package had none. Symbols list on
# different dates and exchanges go down for different hours, so two series of equal LENGTH are
# not two series of equal DATES.


class TestAlignSeries:
    """``tbot.data.align_series`` — a data-layer operation with no config and no thresholds."""

    @staticmethod
    def _closes(n: int, *, symbol: str, offset_bars: int = 0, base: float = 100.0) -> Series:
        step = timedelta(minutes=Timeframe.parse("1H").minutes)
        idx = [T0 + (i + offset_bars) * step for i in range(n)]
        closes = [base + i for i in range(n)]
        return Series.from_arrays(
            idx, closes, [c + 1 for c in closes], [c - 1 for c in closes], closes,
            volume=[1.0] * n, tf="1H", symbol=symbol,
        )

    def test_identical_indices_are_returned_unchanged(self):
        from tbot.data import align_series
        a = self._closes(20, symbol="A")
        b = self._closes(20, symbol="B", base=500.0)
        out = align_series(a, b)
        assert out is not None
        assert len(out[0]) == len(out[1]) == 20
        assert out[0].index.equals(out[1].index)

    def test_partial_overlap_is_cut_to_the_shared_dates(self):
        from tbot.data import align_series
        a = self._closes(20, symbol="A")                       # bars 0..19
        b = self._closes(20, symbol="B", offset_bars=12)       # bars 12..31
        out = align_series(a, b)
        assert out is not None
        assert len(out[0]) == len(out[1]) == 8                 # bars 12..19
        assert out[0].index.equals(out[1].index)
        assert out[0].timestamp(0) == b.timestamp(0)
        assert out[0].timestamp(-1) == a.timestamp(-1)

    def test_disjoint_series_return_none(self):
        from tbot.data import align_series
        a = self._closes(10, symbol="A")
        b = self._closes(10, symbol="B", offset_bars=50)
        assert align_series(a, b) is None

    def test_a_hole_in_one_series_removes_that_bar_from_both(self):
        """The case that made the old positional tail wrong: a gap, not a different start."""
        from tbot.data import align_series
        a = self._closes(10, symbol="A")
        gappy = Series(a.frame.drop(a.index[4]), tf=a.tf, symbol="B",
                       venue_kind=a.venue_kind, validate=False)
        out = align_series(a, gappy)
        assert out is not None
        assert len(out[0]) == len(out[1]) == 9
        assert a.index[4] not in out[0].index

    def test_lookback_keeps_the_last_n_common_bars(self):
        from tbot.data import align_series
        a = self._closes(40, symbol="A")
        b = self._closes(40, symbol="B")
        out = align_series(a, b, lookback_bars=10)
        assert out is not None and len(out[0]) == 10
        assert out[0].timestamp(-1) == a.timestamp(-1)

    def test_three_way_alignment_uses_the_common_intersection(self):
        from tbot.data import align_series
        a = self._closes(30, symbol="A")
        b = self._closes(30, symbol="B", offset_bars=5)
        c = self._closes(30, symbol="C", offset_bars=10)
        out = align_series(a, b, c)
        assert out is not None
        assert len({tuple(x.index) for x in out}) == 1
        assert len(out[0]) == 20                                # bars 10..29

    def test_no_arguments_returns_none(self):
        from tbot.data import align_series
        assert align_series() is None

    def test_alignment_makes_a_previously_unanswerable_correlation_answerable(self):
        """The whole point: aligned legs let rolling_correlation speak, with the right sign."""
        import math

        from tbot.data import align_series
        from tbot.regime import rolling_correlation

        step = timedelta(minutes=Timeframe.parse("1H").minutes)
        vals = [100.0 + 5.0 * math.cos(2 * math.pi * i / 8) for i in range(40)]

        def build(symbol, offset):
            idx = [T0 + (i + offset) * step for i in range(40)]
            return Series.from_arrays(idx, vals, [v + 0.1 for v in vals],
                                      [v - 0.1 for v in vals], vals,
                                      volume=[1.0] * 40, tf="1H", symbol=symbol)

        a, b = build("A", 0), build("B", 20)
        assert rolling_correlation(a, b) is None, "unaligned must still fail closed"

        pair = align_series(a, b)
        assert pair is not None
        corr = rolling_correlation(pair[0], pair[1])
        assert corr is not None
        # 20 bars of offset on a period-8 cosine is half a period: the truth is -1, not +1
        assert float(corr) == pytest.approx(-1.0, abs=1e-9)


class TestAtrValueIsBitExact:
    """``atr_value`` is the float face of ``atr_at``; the two may never disagree.

    The hot path used to do ``float(atr_at(...))`` — a float out of the cached ATR array, boxed
    into a Decimal, then immediately unboxed. ``atr_value`` skips the round-trip. That is only
    safe while the two return the same number, so this pins it rather than trusting the argument.
    """

    def test_atr_value_equals_float_of_atr_at_on_every_bar(self):
        from tbot.data import synthetic
        from tbot.primitives import atr_at, atr_value

        s = synthetic(seed=5, tf=Timeframe.H4, symbol="ATRTEST").series
        cfg = Config()
        for i in range(len(s)):
            assert atr_value(s, cfg, i) == float(atr_at(s, cfg, i)), f"bar {i}"

    def test_atr_value_defaults_to_the_last_bar_like_atr_at(self):
        from tbot.data import synthetic
        from tbot.primitives import atr_at, atr_value

        s = synthetic(seed=5, tf=Timeframe.H4, symbol="ATRTEST").series
        cfg = Config()
        assert atr_value(s, cfg) == float(atr_at(s, cfg))
        assert atr_value(s, cfg) == atr_value(s, cfg, len(s) - 1)

    def test_atr_value_rejects_an_empty_series_the_same_way(self):
        from tbot.models import Series as _S
        from tbot.primitives import atr_value

        empty = _S.from_arrays([], [], [], [], [], volume=[], tf="4H", symbol="E")
        with pytest.raises(ValueError, match="empty series has no ATR"):
            atr_value(empty, Config())

    def test_tolerance_band_is_unchanged_by_the_float_path(self):
        """P9's band is what the hot path actually consumes; prove it moved by zero."""
        from decimal import Decimal

        from tbot.data import synthetic
        from tbot.primitives import atr_array, tolerance_band

        s = synthetic(seed=5, tf=Timeframe.H4, symbol="ATRTEST").series
        cfg = Config()
        for i in range(0, len(s), 7):
            price = Decimal(str(float(s.close[i])))
            low, high = tolerance_band(s, cfg, price, i)
            # the pre-change expression, spelled out
            expected_band = Decimal(str(
                float(Decimal(str(float(atr_array(s, cfg.atr_period)[i]))))
                * cfg.level_tolerance_atr))
            assert high - price == expected_band, f"bar {i}"
            assert price - low == expected_band, f"bar {i}"
