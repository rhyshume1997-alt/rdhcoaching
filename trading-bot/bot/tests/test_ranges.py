"""Contract tests for tbot.detectors.ranges (SPEC.md §5.4, CF-25, CF-26).

Three hand-built series carry most of the weight, all on 4H so the CF-15 machine needs no extra
lower-timeframe confirmation candle:

``oscillator``   100 <-> 108 with turns at 104.5, so the mid-range level is **not** the
                 geometric 104.0 — the whole point of P7.
``double_top``   the range high is rejected once, as a single P4 touch, so the range is
                 provisional until a genuine second touch (S4-R4).
``flipped_low``  the 100 line is resistance, breaks up, flips to support, and only then does
                 the first support touch confirm the range low (S4-R3).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config, ConfigError
from tbot.data import synthetic
from tbot.models import ConfluenceClass, Direction, Level, LevelKind, Series, Timeframe, dec
import tbot.primitives as P
from tbot.detectors.base import Detector
from tbot.detectors.ranges import (
    DetectedRange,
    RangeDetector,
    RangeZone,
    classify_price,
)

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)      # a Monday


# --------------------------------------------------------------------------- helpers

def make_series(rows, tf: str = "4H", symbol: str = "T") -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1_000.0] * len(rows), tf=tf, symbol=symbol,
    )


def from_closes(closes, pad: float = 0.3):
    rows = []
    prev = closes[0]
    for c in closes:
        rows.append((prev, max(prev, c) + pad, min(prev, c) - pad, c))
        prev = c
    return rows


def legs(waypoints, per: int = 4):
    """Linear legs of ``per`` bars between each pair of waypoints."""
    out = []
    for a, b in zip(waypoints, waypoints[1:]):
        for i in range(1, per + 1):
            out.append(a + (b - a) * i / per)
    return out


OSC_WAYPOINTS = [100, 104.5, 100, 108, 100, 104.5, 100, 108, 100, 104.5, 100, 108, 100]


def oscillator(extra=()) -> Series:
    """100 <-> 108, turning at 104.5 often enough to build a P3 level there."""
    closes = [OSC_WAYPOINTS[0]] + legs(OSC_WAYPOINTS)
    return make_series(from_closes(list(closes) + list(extra)))


DOUBLE_TOP_CLOSES = [100, 102, 104, 106, 108, 107.85, 107.8, 107.85, 108, 106, 104, 102, 100,
                     101, 102, 103, 104, 103, 102, 101, 100, 101, 102, 103, 104, 103, 102, 101,
                     100, 101, 102, 103, 104, 103, 102, 101, 100]


def double_top(extra=()) -> Series:
    """One rejection at 108 drawn as two pivots inside the P9 band = a single P4 touch."""
    rows = from_closes(list(DOUBLE_TOP_CLOSES) + list(extra))
    rows[5] = (107.9, 107.95, 107.7, 107.85)
    rows[6] = (107.85, 107.95, 107.7, 107.8)
    rows[7] = (107.8, 107.95, 107.7, 107.85)
    return make_series(rows)


def flipped_low() -> Series:
    """100 is resistance (two pivot highs), breaks up at bar 16, flips on the bar-17 retest."""
    pre = [96, 97.5, 99, 100, 99, 97.5, 96, 97.5, 99, 100, 98, 96.5, 94.5, 96.5, 98, 99]
    post = [102] + legs([102, 100, 108, 100, 108, 100, 108, 100])
    rows = from_closes(pre + post)
    rows[17] = (102.0, 102.3, 100.0, 101.5)      # low == 100, closes above -> confirmed support
    return make_series(rows)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def syn():
    return synthetic(seed=7)


def only(ranges) -> DetectedRange:
    assert len(ranges) == 1, [(float(r.low), float(r.high)) for r in ranges]
    return ranges[0]


# =========================================================================== detection


class TestProtocol:
    def test_surface(self):
        d = RangeDetector()
        assert isinstance(d, Detector)
        assert d.name == "ranges" and d.stage == 5
        assert d.produces == (ConfluenceClass.RANGE_BOUNDARY.value,)
        assert "CF-26" in d.source_ids and "S4-R3" in d.source_ids

    def test_empty_and_featureless_series(self, cfg):
        d = RangeDetector()
        assert d.detect(make_series([]), cfg) == []
        assert d.detect_ranges(make_series([]), cfg) == []
        flat = make_series([(100.0, 100.5, 99.5, 100.0)] * 40)
        assert d.detect_ranges(flat, cfg) == []       # no pivots, no boundaries


class TestRangeConstruction:
    def test_synthetic_range_is_found_with_its_p8_measurements(self, cfg, syn):
        rng = only(RangeDetector().detect_ranges(syn.series, cfg))
        assert (float(rng.low), float(rng.high)) == (syn.features.range_low,
                                                     syn.features.range_high)
        assert rng.start_index == 0 and rng.end_index == syn.features.range_end
        assert rng.check.valid and rng.bars == 60
        assert rng.check.upper_touches == 5 and rng.check.lower_touches >= 2
        assert float(rng.check.height_atr) >= cfg.range_min_height_atr
        assert rng.confirmed and not rng.provisional and not rng.stale

    def test_range_high_needs_a_second_touch(self, cfg):
        """S4-R4: "a first rejection in price discovery does not count"."""
        rng = only(RangeDetector().detect_ranges(double_top(), cfg))
        assert rng.check.upper_touches == 1
        assert rng.high_confirmed_index is None
        assert rng.provisional and not rng.confirmed
        assert rng.high_level is None and rng.mid_level is None and rng.mid is None

    def test_the_range_low_trades_before_the_range_high_exists(self, cfg):
        """S4 ``[00:23:37]`` — the asymmetry: a provisional range still emits its low."""
        rng = only(RangeDetector().detect_ranges(double_top(), cfg))
        assert [lv.kind for lv in rng.levels()] == [LevelKind.RANGE_LOW]
        assert rng.low_level.price == dec(100.0)
        assert rng.low_level.touch_count >= 2
        assert "S4 [00:23:37]" in rng.source_ids

    def test_a_second_touch_confirms_the_high_and_creates_the_mid(self, cfg):
        rng = only(RangeDetector().detect_ranges(
            double_top(extra=[102, 104, 106, 108, 106, 104, 102, 100]), cfg))
        assert rng.high_confirmed_index == 40
        assert rng.confirmed and not rng.provisional
        assert [lv.kind for lv in rng.levels()] == [
            LevelKind.RANGE_LOW, LevelKind.RANGE_HIGH, LevelKind.MID_RANGE]

    def test_range_low_confirmed_by_the_flip_then_the_first_touch(self, cfg):
        """S4-R3: the first support touch after the level broke above and flipped."""
        rng = only(RangeDetector().detect_ranges(flipped_low(), cfg))
        assert (float(rng.low), float(rng.high)) == (100.0, 108.0)
        assert rng.low_confirmation == "flip_then_touch"
        assert rng.low_confirmed_index == 28        # the first touch after the bar-17 flip
        assert "CF-15" in rng.source_ids

    def test_range_low_falls_back_to_the_second_touch(self, cfg, syn):
        rng = only(RangeDetector().detect_ranges(syn.series, cfg))
        assert rng.low_confirmation == "second_touch"

    def test_nested_candidates_resolve_to_one_range(self, cfg, syn):
        """A confirmed range always beats a wider provisional one (S7-R20 within a series)."""
        ranges = RangeDetector().detect_ranges(syn.series, cfg)
        assert len(ranges) == 1 and ranges[0].confirmed

    def test_a_window_shorter_than_range_min_bars_is_not_a_range(self, cfg):
        assert RangeDetector().detect_ranges(oscillator().head(18), cfg) == []


class TestRangeDeath:
    """CF-26 — a body close beyond a boundary is only half of it."""

    def test_close_beyond_alone_does_not_kill_the_range(self, cfg, syn):
        rng = only(RangeDetector().detect_ranges(syn.series, cfg))
        assert rng.boundary_break_index == 60 and rng.broken_side == "high"
        assert not rng.dead and rng.death_index is None
        assert "CF-26" in rng.source_ids

    def test_close_beyond_mode_kills_it_immediately(self, cfg, syn):
        loose = cfg.with_overrides(range_death_mode="close_beyond")
        assert RangeDetector().detect_ranges(syn.series, loose) == []

    def test_close_beyond_plus_a_confirmed_flip_kills_it(self, cfg):
        alive = oscillator(extra=[110.0])
        dead_rows = [(r[0], r[1], r[2], r[3]) for r in
                     alive.frame.itertuples(index=False, name=None)]
        dead_rows.append((110.0, 110.3, 108.0, 109.0))   # retest of 108, closes above -> flip
        assert RangeDetector().detect_ranges(alive, cfg)          # break alone: still alive
        assert RangeDetector().detect_ranges(make_series(dead_rows), cfg) == []

    def test_single_stopout_mode_kills_it_on_a_wick(self, cfg):
        strict = cfg.with_overrides(range_death_mode="single_stopout")
        assert RangeDetector().detect_ranges(oscillator(), cfg)
        assert RangeDetector().detect_ranges(oscillator(), strict) == []


class TestMidRange:
    def test_mid_range_is_not_the_naive_midpoint(self, cfg):
        """P7 / CF-26: the highest-touch level near the geometric 50 % wins."""
        rng = only(RangeDetector().detect_ranges(oscillator(), cfg))
        assert (float(rng.low), float(rng.high)) == (100.0, 108.0)
        assert rng.mid is not None
        assert rng.mid.geometric_mid == dec(104.0)
        assert rng.mid.price == dec(104.5)          # the P3 level, not the midpoint
        assert rng.mid.source == "level"
        assert rng.mid_level is not None and rng.mid_level.kind is LevelKind.MID_RANGE

    def test_mid_range_falls_back_to_geometric(self, cfg, syn):
        rng = only(RangeDetector().detect_ranges(syn.series, cfg))
        assert rng.mid is not None and rng.mid.source == "geometric"
        assert rng.mid.price == rng.mid.geometric_mid == dec(104.0)

    def test_no_trade_band_is_a_percentage_of_range_height(self, cfg):
        rng = only(RangeDetector().detect_ranges(oscillator(), cfg))
        band = dec(cfg.mid_range_band_pct) / Decimal(100) * rng.height
        assert rng.mid.band_low == rng.mid.price - band
        assert rng.mid.band_high == rng.mid.price + band

    def test_search_pct_zero_is_no_longer_an_allowed_setting(self, cfg):
        """**Q12** — the pure-geometric-50 % alternative is struck; he rejected it on tape.

        This test used to assert that ``mid_range_search_pct = 0`` gave the geometric midpoint.
        It does, but he was asked this exact question and answered it: *"Do we mark the mid-range
        at exactly the middle of the range or should it align with support and resistance? Uh,
        good question. **It will usually align with support and resistance.**"* (S4
        ``[00:17:53]``), and *"let's call this our mid-range at this point… even though it's not
        exactly in the middle"* (S4 ``[00:24:12]``).  0 is now below the key's minimum.
        """
        with pytest.raises(ConfigError):
            cfg.with_overrides(mid_range_search_pct=0.0)
        # The geometric midpoint is still the *fallback* when no S/R level is in the search band.
        rng = only(RangeDetector().detect_ranges(oscillator(), cfg))
        assert rng.mid.source in ("geometric", "level")


@pytest.fixture(scope="module")
def setup(cfg):
    """The oscillator series and its single range — the fixture for the CF-25 gate tests."""
    s = oscillator()
    return s, only(RangeDetector().detect_ranges(s, cfg))


class TestZoneClassification:
    def test_zones_across_the_range(self, cfg, setup):
        s, rng = setup
        cases = {
            100.05: RangeZone.AT_RANGE_LOW,
            102.00: RangeZone.LOWER_ZONE,
            104.50: RangeZone.MID_RANGE,
            106.50: RangeZone.UPPER_ZONE,
            107.95: RangeZone.AT_RANGE_HIGH,
            112.00: RangeZone.ABOVE_RANGE,
            97.000: RangeZone.BELOW_RANGE,
        }
        for price, zone in cases.items():
            assert classify_price(rng, s, cfg, price).zone is zone, price

    def test_mid_range_is_a_hard_gate_both_ways(self, cfg, setup):
        """CF-25, S4-R8, S5-R14, S8-R30: no new entries while price is at mid-range."""
        s, rng = setup
        for price in (float(rng.mid.band_low) + 0.01, 104.5, float(rng.mid.band_high) - 0.01):
            c = classify_price(rng, s, cfg, price)
            assert c.entries_blocked and not c.long_allowed and not c.short_allowed
            assert any("mid-range" in r for r in c.reasons)

    def test_long_the_low_short_the_high_and_never_the_reverse(self, cfg, setup):
        s, rng = setup
        low = classify_price(rng, s, cfg, 100.05)
        high = classify_price(rng, s, cfg, 107.95)
        assert (low.long_allowed, low.short_allowed) == (True, False)
        assert (high.long_allowed, high.short_allowed) == (False, True)

    def test_mid_range_limits_from_the_extremes_need_an_intermediate_stop(self, cfg, setup):
        """S4-R6/R7 with the S5-R13 proviso."""
        s, rng = setup
        bare = classify_price(rng, s, cfg, 107.95)
        assert not bare.mid_range_limit_allowed
        assert any("intermediate" in r or "structural" in r for r in bare.reasons)

        structure = [Level(id="mid-support", symbol="T", tf=Timeframe.H4, price=dec(102.0),
                           kind=LevelKind.SUPPORT, created_index=0, touch_count=2)]
        armed = classify_price(rng, s, cfg, 107.95, levels=structure)
        assert armed.mid_range_limit_allowed
        assert armed.mid_range_limit_direction is Direction.LONG   # limit long at mid, S4-R6

        at_low = classify_price(rng, s, cfg, 100.05, levels=[
            Level(id="mid-resistance", symbol="T", tf=Timeframe.H4, price=dec(106.0),
                  kind=LevelKind.RESISTANCE, created_index=0, touch_count=2)])
        assert at_low.mid_range_limit_allowed
        assert at_low.mid_range_limit_direction is Direction.SHORT  # S4-R7

    def test_the_proviso_can_be_switched_off(self, cfg, setup):
        s, rng = setup
        loose = cfg.with_overrides(mid_range_requires_intermediate_stop=False)
        assert classify_price(rng, s, loose, 107.95).mid_range_limit_allowed
        off = cfg.with_overrides(mid_range_limits_from_extremes_enabled=False)
        c = classify_price(rng, s, off, 107.95)
        assert not c.mid_range_limit_allowed and c.mid_range_limit_direction is None

    def test_classification_needs_a_confirmed_high(self, cfg):
        s = double_top()
        rng = only(RangeDetector().detect_ranges(s, cfg))
        with pytest.raises(ValueError, match="mid-range"):
            classify_price(rng, s, cfg, 104.0)


class TestMondayRange:
    def test_monday_high_and_low(self, cfg, syn):
        """S5-R8/R9, CF-45: bars 0-23 of the synthetic series are Monday 2024-01-01 UTC."""
        levels = RangeDetector().monday_range_levels(syn.series, cfg)
        assert [lv.kind for lv in levels] == [LevelKind.RANGE_LOW, LevelKind.RANGE_HIGH]
        monday = range(0, 24)
        assert float(levels[1].price) == pytest.approx(max(syn.series.high[i] for i in monday))
        assert float(levels[0].price) == pytest.approx(min(syn.series.low[i] for i in monday))
        assert levels[0].created_index == 23
        assert all("S5-R8" in lv.source_ids for lv in levels)

    def test_an_incomplete_monday_uses_the_previous_week(self, cfg, syn):
        """Nothing repaints: while Monday is still forming, last week's range is the live one."""
        assert RangeDetector().monday_range_levels(syn.series.head(6), cfg) == []

    def test_a_timeframe_coarser_than_the_source_yields_nothing(self, cfg, syn):
        weekly = make_series([(100.0, 101.0, 99.0, 100.5)] * 5, tf="1W")
        assert RangeDetector().monday_range_levels(weekly, cfg) == []

    def test_monday_levels_reach_detect(self, cfg, syn):
        d = RangeDetector()
        monday = {(lv.kind, lv.price, lv.created_index)
                  for lv in d.monday_range_levels(syn.series, cfg)}
        emitted = {(lv.kind, lv.price, lv.created_index) for lv in d.detect(syn.series, cfg)}
        assert monday and monday <= emitted


class TestEmissionContract:
    def test_deterministic_ids_and_source_ids(self, cfg, syn):
        d = RangeDetector()
        first, second = d.detect(syn.series, cfg), d.detect(syn.series, cfg)
        assert [lv.id for lv in first] == [lv.id for lv in second]
        assert [lv.price for lv in first] == [lv.price for lv in second]
        assert first and all(lv.source_ids for lv in first)
        assert all(lv.id.startswith("SYNTH:1H:ranges:") for lv in first)

    def test_ordered_by_completion_bar(self, cfg, syn):
        levels = RangeDetector().detect(syn.series, cfg)
        assert [lv.created_index for lv in levels] == sorted(lv.created_index for lv in levels)

    def test_no_lookahead(self, cfg, syn):
        d = RangeDetector()
        for i in (40, 59, 70, 99):
            for lv in d.detect(syn.series.head(i + 1), cfg):
                assert lv.created_index <= i
                assert all(b <= i for b, _ in lv.touch_history)
            for rng in d.detect_ranges(syn.series.head(i + 1), cfg):
                assert rng.end_index <= i and rng.low_confirmed_index <= i
                assert rng.boundary_break_index is None or rng.boundary_break_index <= i

    def test_boundary_levels_carry_touch_counts_for_cf_07(self, cfg, syn):
        rng = only(RangeDetector().detect_ranges(syn.series, cfg))
        assert rng.high_level is not None
        assert rng.high_level.touch_count == 5
        assert rng.high_level.touch_count <= cfg.range_boundary_touch_limit
        assert "CF-07" in rng.high_level.source_ids

    def test_to_confluence_maps_every_level_to_range_boundary(self, cfg, syn):
        d = RangeDetector()
        levels = d.detect(syn.series, cfg)
        objs = d.to_confluence(levels, cfg)
        assert {o.obj_class for o in objs} == {ConfluenceClass.RANGE_BOUNDARY.value}
        assert [o.price for o in objs] == [lv.price for lv in levels]
        assert all(o.tf is Timeframe.H1 for o in objs)

    def test_boundaries_are_p3_prices_not_raw_extremes(self, cfg, syn):
        """S4-R4: boundaries are drawn at the points of most touch, i.e. the cluster price."""
        rng = only(RangeDetector().detect_ranges(syn.series, cfg))
        pivots = P.swing_points(syn.series, cfg)
        clusters = P.cluster_levels(syn.series, cfg, pivots, now_index=len(syn.series) - 1)
        prices = {c.price for c in clusters}
        assert rng.low in prices and rng.high in prices
