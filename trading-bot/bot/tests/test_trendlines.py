"""Contract tests for tbot.detectors.trendlines (SPEC.md §5.3).

The workhorse series is a rising channel whose swing lows sit exactly on a ``+0.2``/bar line
(100 at bar 5, 102 at 15, 104 at 25, 106 at 35) and whose swing highs sit on a parallel one
(112 at bar 10 ... 118 at 40), so every touch, slope and line price is checkable by hand.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config
from tbot.data import synthetic
from tbot.models import ConfluenceClass, LevelKind, Series, Timeframe, dec
from tbot.detectors.base import Detector
from tbot.detectors.trendlines import MIN_TOUCHES, TrendlineDetector, line_price_at

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


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


CHANNEL_KEYS = [(0, 110.0), (5, 100.0), (10, 112.0), (15, 102.0), (20, 114.0),
                (25, 104.0), (30, 116.0), (35, 106.0), (40, 118.0)]


def channel_closes(keys=CHANNEL_KEYS):
    out = []
    for (a, pa), (b, pb) in zip(keys, keys[1:]):
        for i in range(a, b):
            out.append(pa + (pb - pa) * (i - a) / (b - a))
    out.append(keys[-1][1])
    return out


def channel(with_break: bool = True) -> Series:
    rows = from_closes(channel_closes())
    if with_break:
        rows += [
            (118.0, 118.3, 111.7, 112.0),      # 41 falling
            (112.0, 112.3, 105.7, 106.0),      # 42 close 106 < line(42) = 107.4 -> break
            (106.0, 107.0, 105.7, 106.5),      # 43
            (106.5, 107.8, 105.7, 106.0),      # 44 high == line(44) = 107.8 -> retest
            (106.0, 106.3, 105.0, 105.5),      # 45
        ]
    return make_series(rows)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def syn():
    return synthetic(seed=7)


def support_line(lines):
    return next(ln for ln in lines if ln.side == "support")


# =========================================================================== detection


class TestProtocol:
    def test_surface(self):
        d = TrendlineDetector()
        assert isinstance(d, Detector)
        assert d.name == "trendlines" and d.stage == 4
        assert d.produces == (ConfluenceClass.TRENDLINE.value,)
        assert "S2-R14" in d.source_ids and "S8-R7" in d.source_ids

    def test_empty_and_tiny_series(self, cfg):
        d = TrendlineDetector()
        assert d.detect(make_series([]), cfg) == []
        assert d.detect(make_series(from_closes([100.0, 101.0, 102.0])), cfg) == []


class TestThreeTouchRule:
    def test_two_touches_are_not_a_line(self, cfg):
        """S2-R14, S3-R19, S4-R20, S5-R1, S8-R7 — three touches minimum, unanimously."""
        assert MIN_TOUCHES == 3
        early = channel(with_break=False).head(24)      # only the lows at 5 and 15 exist
        assert TrendlineDetector().detect(early, cfg) == []

    def test_the_third_touch_validates_the_line(self, cfg):
        s = channel(with_break=False).head(30)
        lines = TrendlineDetector().detect_lines(s, cfg)
        line = support_line(lines)
        assert line.touch_indices == (5, 15, 25)
        assert line.validated_index == 28               # third pivot (25) + swing_k (3)
        assert line.level.created_index == 28

    def test_geometry_of_the_fitted_line(self, cfg):
        line = support_line(TrendlineDetector().detect_lines(channel(), cfg))
        assert line.side == "support"
        assert line.touch_indices == (5, 15, 25, 35)
        assert line.level.slope_per_bar == dec(0.2)
        assert line.level.price == dec(104.6)           # 100 + 0.2 * (28 - 5)
        assert line.level.price_at(35) == dec(106.0)
        assert line.level.kind is LevelKind.TRENDLINE
        assert line.level.anchor_indices == [5, 15, 25, 35]
        assert line.span_bars == 30

    def test_a_line_already_broken_while_forming_is_rejected(self, cfg):
        """TBOT1-R1: a line price has body-closed through was never a valid line."""
        closes = channel_closes()
        closes[22] = 100.0                              # line(22) = 103.4; this closes through it
        s = make_series(from_closes(closes))
        for line in TrendlineDetector().detect_lines(s, cfg):
            assert not {5, 15, 25}.issubset(set(line.touch_indices))

    def test_touches_may_be_wicks_or_bodies(self, cfg):
        """S2-R14: "you can draw it off the wicks or off the bodies"."""
        def series(third_low: float) -> Series:
            # Lows at bar 4 (100.0) and bar 12 (102.0) fix a +0.25/bar line, which sits at
            # 104.25 on bar 21.  Bar 21's *body* low is 106.0 — far outside the P9 band — so
            # only its wick can make the third touch.
            closes = [110.0, 106.0, 103.0, 101.0, 100.0, 101.0, 103.0, 106.0, 109.0,
                      107.0, 105.0, 103.0, 102.0, 103.0, 105.0, 107.0, 109.0, 111.0,
                      109.0, 107.0, 106.5, 106.0, 106.5, 107.0, 109.0, 111.0, 113.0]
            rows = from_closes(closes)
            o, h, _l, c = rows[21]
            rows[21] = (o, h, third_low, c)             # the wick reaches for the line
            return make_series(rows)

        wick_touch = TrendlineDetector().detect_lines(series(104.25), cfg)
        no_touch = TrendlineDetector().detect_lines(series(105.0), cfg)
        assert any(set(ln.touch_indices) >= {4, 12, 21} for ln in wick_touch)
        assert not any(set(ln.touch_indices) >= {4, 12, 21} for ln in no_touch)


class TestBreakAndRetest:
    def test_break_is_a_body_close_through_the_line(self, cfg):
        line = support_line(TrendlineDetector().detect_lines(channel(), cfg))
        assert line.break_index == 42                   # close 106.0 < line(42) = 107.4
        assert line.intact is False

    def test_intact_until_a_close_goes_through(self, cfg):
        line = support_line(TrendlineDetector().detect_lines(channel(with_break=False), cfg))
        assert line.intact and line.break_index is None
        assert line.retest_index is None and line.arm_index is None

    def test_retest_after_break_arms_on_the_next_open(self, cfg):
        """S8-R8/S8-R13: the retest variant is the safer entry; TBOT1-R16."""
        line = support_line(TrendlineDetector().detect_lines(channel(), cfg))
        assert line.retest_index == 44                  # high 107.8 == line(44), closes below
        assert line.arm_index == 45
        assert "S8-R13" in line.level.source_ids

    def test_a_wick_back_through_without_holding_is_not_a_retest(self, cfg):
        rows = list(channel().frame.itertuples(index=False, name=None))
        rows = [(r[0], r[1], r[2], r[3]) for r in rows][:44]
        rows.append((106.5, 108.5, 105.7, 108.2))       # closes back ABOVE the line
        line = support_line(TrendlineDetector().detect_lines(make_series(rows), cfg))
        assert line.break_index == 42 and line.retest_index is None


class TestCompetingLines:
    def test_all_valid_lines_are_kept_and_exactly_one_is_primary(self, cfg):
        lines = TrendlineDetector().detect_lines(channel(), cfg)
        sides = sorted(ln.side for ln in lines)
        assert sides == ["resistance", "support"]
        assert sum(1 for ln in lines if ln.is_primary) == 1
        resistance = next(ln for ln in lines if ln.side == "resistance")
        assert resistance.touch_indices == (10, 20, 30, 40)
        assert resistance.level.slope_per_bar == dec(0.2)
        assert resistance.intact                        # price never closed above it

    def test_duplicate_fits_of_the_same_line_are_collapsed(self, cfg):
        lines = TrendlineDetector().detect_lines(channel(), cfg)
        touch_sets = [ln.touch_indices for ln in lines]
        assert len(touch_sets) == len(set(touch_sets))

    def test_scores_rank_touches_first_then_span(self, cfg):
        lines = TrendlineDetector().detect_lines(channel(), cfg)
        for ln in lines:
            assert ln.score > dec(len(ln.touch_indices))
            assert ln.score < dec(len(ln.touch_indices) + 1)


class TestDeterminismAndEmission:
    def test_ids_are_stable_and_derived_from_the_bar_index(self, cfg):
        d = TrendlineDetector()
        s = channel()
        first, second = d.detect(s, cfg), d.detect(s, cfg)
        assert [lv.id for lv in first] == [lv.id for lv in second]
        assert all(lv.id.startswith("T:4H:trendlines:") for lv in first)
        assert all(lv.source_ids for lv in first)

    def test_ordered_by_completion_bar(self, cfg):
        levels = TrendlineDetector().detect(channel(), cfg)
        assert [lv.created_index for lv in levels] == sorted(lv.created_index for lv in levels)

    def test_no_lookahead(self, cfg, syn):
        d = TrendlineDetector()
        for i in (40, 60, 99):
            for ln in d.detect_lines(syn.series.head(i + 1), cfg):
                assert max(ln.touch_indices) <= i and ln.validated_index <= i
                assert ln.break_index is None or ln.break_index <= i
                assert ln.retest_index is None or ln.retest_index <= i

    def test_horizontal_boundaries_are_found_on_the_synthetic_series(self, cfg, syn):
        """The synthetic range boundaries are (flat) lines with five touches each."""
        lines = TrendlineDetector().detect_lines(syn.series, cfg)
        top = next(ln for ln in lines if ln.side == "resistance")
        assert top.touch_indices == (23, 31, 39, 47, 55)
        assert top.level.slope_per_bar == Decimal(0)
        assert top.break_index == 60                   # the impulse out of the range

    def test_to_confluence_maps_class_and_price(self, cfg):
        d = TrendlineDetector()
        levels = d.detect(channel(), cfg)
        objs = d.to_confluence(levels, cfg)
        assert {o.obj_class for o in objs} == {ConfluenceClass.TRENDLINE.value}
        assert [o.price for o in objs] == [lv.price for lv in levels]
        assert all(o.tf is Timeframe.H4 for o in objs)

    def test_line_price_helper_matches_the_level(self, cfg):
        line = support_line(TrendlineDetector().detect_lines(channel(), cfg))
        for i in (5, 20, 44):
            assert line.price_at(i) == line_price_at(
                line.level.created_index, line.level.price, line.level.slope_per_bar, i)
