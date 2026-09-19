"""Tests for tbot.detectors.patterns (SPEC.md §5.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

import pytest

import tbot.primitives as P
from tbot.config import Config
from tbot.detectors.base import Detector
from tbot.detectors.patterns import (
    NOT_IMPLEMENTED_PATTERNS,
    WEDGE_CONVERGENCE_RATIO,
    WEDGE_MAX_PIVOTS,
    PatternDetector,
    classify_consolidation,
    confirm_breakout_retest,
    find_cup_and_handle,
    find_double_tops_bottoms,
    find_flags,
    find_head_and_shoulders,
    find_quasimodo,
    find_wedges_and_channels,
)
from tbot.models import Direction, Level, LevelKind, Series, Timeframe, dec


# --------------------------------------------------------------------------- builders

def _ohlc(bars: Sequence[tuple[float, float, float, float]], tf: Timeframe = Timeframe.H1) -> Series:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ts = [t0 + timedelta(minutes=tf.minutes * i) for i in range(len(bars))]
    return Series.from_arrays(
        ts,
        [b[0] for b in bars],
        [b[1] for b in bars],
        [b[2] for b in bars],
        [b[3] for b in bars],
        tf=tf,
        symbol="TEST",
    )


def _from_closes(closes: Sequence[float], wick: float = 0.05) -> Series:
    opens = [closes[0]] + list(closes[:-1])
    return _ohlc([(o, max(o, c) + wick, min(o, c) - wick, c) for o, c in zip(opens, closes)])


def _zig(points: Sequence[float], per: int = 5) -> list[float]:
    """Straight-line interpolation between turning points, ``per`` bars per leg."""
    out = [float(points[0])]
    for a, b in zip(points, points[1:]):
        for i in range(1, per + 1):
            out.append(round(a + (b - a) * i / per, 4))
    return out


#: impulse 100 → 130, then a tight slightly-down-drifting flag, breakout, retest.
_BULL_FLAG_CLOSES = (
    [104.0, 103.0, 102.0, 101.0, 100.0, 101.0, 102.0, 103.0]
    + _zig([103, 130], per=10)[1:]
    + [129.5, 129.8, 129.2, 129.5, 128.9, 129.2, 128.6, 128.9]
    + _zig([128.9, 140], per=6)[1:]
    + [136.0, 132.0, 130.0, 131.0, 133.0, 136.0, 138.0]
)

#: impulse 100 → 140, then a steep, converging, lower-lows-and-lower-highs pullback.
_FALLING_WEDGE_CLOSES = (
    [104.0, 103.0, 102.0, 101.0, 100.0]
    + _zig([100, 140], per=10)[1:]
    + _zig([140, 100, 124, 98, 112, 97, 104], per=5)[1:]
)

#: a parallel rising channel: constant width, so it is a channel and not a wedge.
_CHANNEL_CLOSES = _zig([100, 110, 105, 115, 110, 120, 115, 125], per=5)
#: the same channel reached by a down impulse, so the detector has a pole to start from.
_CHANNEL_SERIES_CLOSES = _zig([120, 140, 100, 110, 105, 115, 110, 120, 115, 125], per=5)

#: a down impulse into a rising, converging wedge entered from below.
_RISING_WEDGE_POINTS = [120, 140, 100, 112, 104, 114, 108, 115, 111, 116, 113, 100, 106, 101, 104]
#: the same shape entered from *above* — S4-R22 rejects it.
_RISING_WEDGE_FROM_ABOVE = [120, 140, 103, 112, 104, 114, 108, 115, 111, 116, 113, 100, 106, 101, 104]


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def bull_flag() -> Series:
    return _from_closes(_BULL_FLAG_CLOSES)


@pytest.fixture(scope="module")
def falling_wedge() -> Series:
    return _from_closes(_FALLING_WEDGE_CLOSES)


# --------------------------------------------------------------------------- protocol

def test_detector_satisfies_protocol() -> None:
    det = PatternDetector()
    assert isinstance(det, Detector)
    assert det.name == "chart_patterns" and det.stage == 11
    assert det.produces == ("pattern",)
    assert det.standalone_forbidden is True


def test_trendline_inverse_hs_is_never_emitted(cfg: Config, bull_flag: Series) -> None:
    """S5-R41: he does not play them at all, so the module ships without them."""
    assert "trendline_inverse_head_and_shoulders" in NOT_IMPLEMENTED_PATTERNS
    kinds = {p.kind for p in PatternDetector().detect(bull_flag, cfg)}
    assert not kinds & set(NOT_IMPLEMENTED_PATTERNS)


# ------------------------------------------- S4-R23: falling wedge vs bull flag vs channel

def test_tight_no_structure_break_is_a_bull_flag(cfg: Config, bull_flag: Series) -> None:
    """"Tight consolidation with no structure break = bull flag" — S4-R23, via P13."""
    verdict = classify_consolidation(bull_flag, cfg, 18, 24, impulse=Direction.LONG)
    assert verdict.kind == "flag"
    assert verdict.tight is True
    assert verdict.steep is False
    assert verdict.structure_break is False


def test_steep_with_structure_break_and_convergence_is_a_wedge(cfg: Config, falling_wedge: Series) -> None:
    """"Steep + break of market structure (lower lows / lower highs) = falling wedge" — S4-R23."""
    verdict = classify_consolidation(
        falling_wedge, cfg, 15, len(falling_wedge) - 1, impulse=Direction.LONG
    )
    assert verdict.kind == "wedge"
    assert verdict.tight is False
    assert verdict.steep is True
    assert verdict.structure_break is True
    assert verdict.converging is True
    assert verdict.width_end <= WEDGE_CONVERGENCE_RATIO * verdict.width_start


def test_parallel_lines_are_a_channel_not_a_wedge(cfg: Config) -> None:
    """"Parallel (non-converging) lines = channel, not a wedge" — S4-R23."""
    series = _from_closes(_CHANNEL_CLOSES)
    verdict = classify_consolidation(series, cfg, 0, len(series) - 1, impulse=Direction.SHORT)
    assert verdict.kind == "channel"
    assert verdict.converging is False and verdict.parallel is True
    assert verdict.width_end > WEDGE_CONVERGENCE_RATIO * verdict.width_start
    assert any("channel, not a wedge" in r for r in verdict.reasons)


def test_the_two_classifications_are_mutually_exclusive(cfg: Config, bull_flag: Series, falling_wedge: Series) -> None:
    flag = classify_consolidation(bull_flag, cfg, 18, 24, impulse=Direction.LONG)
    wedge = classify_consolidation(falling_wedge, cfg, 15, len(falling_wedge) - 1, impulse=Direction.LONG)
    assert flag.kind != wedge.kind
    assert flag.tight and not wedge.tight
    assert wedge.steep and not flag.steep


def test_a_window_too_small_for_a_pattern_is_plain_sr(cfg: Config, bull_flag: Series) -> None:
    """S4 ``[01:03:29]`` / S4-A17: a consolidation too small is treated as S/R instead."""
    verdict = classify_consolidation(bull_flag, cfg, 18, 18, impulse=Direction.LONG)
    assert verdict.kind == "too_small"
    assert any("plain S/R" in r for r in verdict.reasons)


def test_convergence_ratio_is_a_declared_our_choice() -> None:
    assert isinstance(WEDGE_CONVERGENCE_RATIO, Decimal)
    assert Decimal(0) < WEDGE_CONVERGENCE_RATIO < Decimal(1)
    assert WEDGE_MAX_PIVOTS >= 4


# --------------------------------------------------------------------------- the trigger

def test_breakout_plus_retest_confirms(cfg: Config, bull_flag: Series) -> None:
    """S4-R19: breakout → retest → close/hold, stop just beyond the flipped level."""
    flags = find_flags(bull_flag, cfg)
    assert flags and flags[0].kind == "bull_flag"
    flag = flags[0]
    assert flag.breakout_index is not None
    assert flag.retest_index is not None and flag.retest_index > flag.breakout_index
    assert flag.confirmed is True
    assert flag.entry_price == dec(bull_flag.close[flag.retest_index])
    buffer = P.stop_buffer(bull_flag, cfg, flag.retest_index)
    assert flag.stop_price == P.apply_stop_buffer(flag.trigger_price, Direction.LONG, buffer)


def test_naked_breakout_is_not_a_trade(cfg: Config) -> None:
    """A breakout with no holding retest never confirms — naked breakouts are excluded."""
    closes = list(_BULL_FLAG_CLOSES[:32]) + _zig([128.9, 160], per=10)[1:]
    series = _from_closes(closes)
    flags = find_flags(series, cfg)
    assert flags
    flag = flags[0]
    assert flag.breakout_index is not None
    assert flag.retest_index is None
    assert flag.confirmed is False
    assert flag.entry_price is None and flag.stop_price is None
    assert any("naked breakouts are excluded" in r for r in flag.reasons)


def test_no_breakout_at_all(cfg: Config, bull_flag: Series) -> None:
    result = confirm_breakout_retest(bull_flag, cfg, dec(10_000), Direction.LONG, 0)
    assert result.breakout_index is None and result.confirmed is False
    assert any("no body close through" in r for r in result.reasons)


def test_retest_timeout_is_optional_and_bounded(cfg: Config, bull_flag: Series) -> None:
    flag = find_flags(bull_flag, cfg)[0]
    assert flag.retest_index is not None
    impatient = find_flags(bull_flag, cfg, retest_timeout_bars=1)
    assert impatient and impatient[0].retest_index is None
    assert impatient[0].confirmed is False


# --------------------------------------------------------------------------- flags

def test_bull_flag_measures_the_pole_from_the_flag_base(cfg: Config, bull_flag: Series) -> None:
    """S4-R17: the pole copied to the base of the flag."""
    flag = find_flags(bull_flag, cfg)[0]
    assert flag.kind == "bull_flag" and flag.direction is Direction.LONG
    assert flag.measured_move == dec(30.0)                    # 100 -> 130
    base = dec(bull_flag.low[flag.start_index:flag.end_index + 1].min())
    flag_base = dec(bull_flag.low[flag.end_index - 6:flag.end_index + 1].min())
    assert flag.measured_target == flag_base + flag.measured_move
    assert flag.measured_target > flag.trigger_price
    assert flag.measured_target_is_theoretical is True
    assert base <= flag_base


def test_bear_flag_mirrors_the_bull_flag(cfg: Config) -> None:
    """S4-R18: the pole copied to the top of the flag and projected down."""
    closes = (
        [96.0, 97.0, 98.0, 99.0, 100.0, 99.0, 98.0, 97.0]
        + _zig([97, 70], per=10)[1:]
        + [70.5, 70.2, 70.8, 70.5, 71.1, 70.8, 71.4, 71.1]
        + _zig([71.1, 60], per=6)[1:]
        + [64.0, 68.0, 70.0, 69.0, 67.0, 64.0, 62.0]
    )
    series = _from_closes(closes)
    bears = [p for p in find_flags(series, cfg) if p.kind == "bear_flag"]
    assert bears
    flag = bears[0]
    assert flag.direction is Direction.SHORT
    assert flag.measured_target is not None and flag.measured_move is not None
    assert flag.measured_target < flag.trigger_price
    assert "S4-R18" in flag.source_ids


def test_pole_anchor_key_is_honoured(cfg: Config, bull_flag: Series) -> None:
    recent = find_flags(bull_flag, cfg)
    first = find_flags(bull_flag, cfg.with_overrides(pattern_pole_anchor="first_impulse"))
    assert recent and first
    assert "pattern_pole_anchor=most_recent_impulse" in recent[0].source_ids
    assert "pattern_pole_anchor=first_impulse" in first[0].source_ids


# --------------------------------------------------------------------------- wedges

def test_falling_wedge_measures_the_width_at_its_origin(cfg: Config) -> None:
    """S4-R21: bottom line → top line at the wedge origin, placed at the breakout point."""
    series = _from_closes(_FALLING_WEDGE_CLOSES)
    wedges = [p for p in find_wedges_and_channels(series, cfg) if p.kind == "falling_wedge"]
    assert wedges
    wedge = wedges[0]
    assert wedge.direction is Direction.LONG
    assert wedge.measured_move is not None and wedge.measured_move > 0
    assert wedge.measured_target is not None
    assert wedge.measured_target > wedge.trigger_price
    assert "S4-R21" in wedge.source_ids


def test_rising_wedge_must_be_entered_from_below(cfg: Config) -> None:
    """S4-R22: valid only if price arrived into the wedge from below."""
    from_below = _from_closes(_zig(_RISING_WEDGE_POINTS, per=5))
    kinds = [p.kind for p in find_wedges_and_channels(from_below, cfg)]
    assert "rising_wedge" in kinds

    from_above = _from_closes(_zig(_RISING_WEDGE_FROM_ABOVE, per=5))
    assert "rising_wedge" not in [p.kind for p in find_wedges_and_channels(from_above, cfg)]


def test_rising_wedge_projects_the_width_downward(cfg: Config) -> None:
    series = _from_closes(_zig(_RISING_WEDGE_POINTS, per=5))
    wedge = next(p for p in find_wedges_and_channels(series, cfg) if p.kind == "rising_wedge")
    assert wedge.direction is Direction.SHORT
    assert wedge.measured_target is not None and wedge.measured_move is not None
    assert wedge.measured_target < wedge.trigger_price
    assert "S4-R22" in wedge.source_ids


def test_rising_channel_is_neutral_with_no_target(cfg: Config) -> None:
    """S8 ``[01:11:44]``: a rising parallel channel is neither bullish nor bearish."""
    series = _from_closes(_CHANNEL_SERIES_CLOSES)
    channels = [p for p in find_wedges_and_channels(series, cfg) if p.kind == "rising_channel"]
    assert channels
    channel = channels[0]
    assert channel.direction is None
    assert channel.measured_move is None and channel.measured_target is None
    assert channel.confirmed is False and channel.entry_price is None


# --------------------------------------------------------------------------- double top / bottom

def test_double_bottom_geometry_and_measured_move(cfg: Config) -> None:
    """S7-R32/R33/R34: bodies close to each other, neckline break + retest, projected target."""
    series = _from_closes(_zig([120, 100, 112, 100.3, 118, 110, 116], per=5))
    patterns = [p for p in find_double_tops_bottoms(series, cfg) if p.kind == "double_bottom"]
    assert patterns
    db = patterns[0]
    assert db.direction is Direction.LONG
    assert db.trigger_price == dec(112.0)                   # the neckline
    assert db.measured_move == dec(12.0)                    # neckline - bottom
    assert db.measured_target == dec(124.0)                 # projected above the neckline
    assert db.confirmed is True
    assert db.invalidation_price == dec(100.0)
    assert "S7-R34" in db.source_ids


def test_second_bottom_must_be_close_to_the_first(cfg: Config) -> None:
    """The two bodies must sit inside the P9 band; far apart is not a double bottom."""
    apart = _from_closes(_zig([120, 100, 112, 106.0, 118, 110, 116], per=5))
    assert [p for p in find_double_tops_bottoms(apart, cfg) if p.kind == "double_bottom"] == []


def test_double_top_mirrors(cfg: Config) -> None:
    series = _from_closes(_zig([100, 120, 108, 119.8, 102, 110, 104], per=5))
    tops = [p for p in find_double_tops_bottoms(series, cfg) if p.kind == "double_top"]
    assert tops
    assert tops[0].direction is Direction.SHORT
    assert tops[0].measured_target is not None
    assert tops[0].measured_target < tops[0].trigger_price


# --------------------------------------------------------------------------- cup and handle

def test_cup_and_handle_respects_the_depth_floor(cfg: Config) -> None:
    """S4-R24 / S4-A9: the handle must not retrace below ``cup_handle_floor_pct`` of the cup."""
    shallow = _from_closes(_zig([100, 120, 90, 119.8, 112, 130, 120.2, 126], per=5))
    cups = find_cup_and_handle(shallow, cfg)
    assert cups
    cup = cups[0]
    assert cup.trigger_price == dec(120.0)
    assert cup.measured_move == dec(30.0)                    # neckline - cup base
    assert cup.measured_target == dec(150.0)
    assert cup.confirmed is True
    assert "S4-R24" in cup.source_ids

    deep = _from_closes(_zig([100, 120, 90, 119.8, 95, 130, 120.2, 126], per=5))
    assert find_cup_and_handle(deep, cfg) == []


def test_cup_handle_floor_is_configurable(cfg: Config) -> None:
    deep = _from_closes(_zig([100, 120, 90, 119.8, 95, 130, 120.2, 126], per=5))
    assert find_cup_and_handle(deep, cfg.with_overrides(cup_handle_floor_pct=95.0))


# --------------------------------------------------------------------------- head and shoulders

def test_head_and_shoulders_never_shorts_the_right_shoulder(cfg: Config) -> None:
    """S4-R26: the entry is the neckline breakdown + retest + rejection, never the shoulder."""
    series = _from_closes(_zig([80, 110, 95, 130, 96, 111, 90, 95, 92, 85], per=5))
    hs = [p for p in find_head_and_shoulders(series, cfg) if p.kind == "head_and_shoulders"]
    assert hs
    pattern = hs[0]
    assert pattern.direction is Direction.SHORT
    assert pattern.pivot_indices[2] < pattern.end_index         # head sits between the shoulders
    assert pattern.measured_target is not None
    assert pattern.measured_target == pattern.trigger_price - pattern.measured_move
    assert pattern.retest_index is not None and pattern.retest_index > pattern.pivot_indices[-1]
    assert any("never short the right shoulder" in r for r in pattern.reasons)
    assert "S4-R26" in pattern.source_ids


def test_head_must_be_above_both_shoulders(cfg: Config) -> None:
    flat = _from_closes(_zig([80, 110, 95, 105, 96, 100, 90, 95, 92, 85], per=5))
    assert [p for p in find_head_and_shoulders(flat, cfg) if p.kind == "head_and_shoulders"] == []


def test_inverse_head_and_shoulders_hard_geometric_filter(cfg: Config) -> None:
    """S4-R25 / S5-R40: head below both shoulders, right peak no higher than the left."""
    series = _from_closes(_zig([140, 110, 125, 90, 124.8, 111, 120, 126, 120.5, 128], per=5))
    inv = [p for p in find_head_and_shoulders(series, cfg) if p.kind == "inverse_head_and_shoulders"]
    assert inv
    pattern = inv[0]
    assert pattern.direction is Direction.LONG
    assert pattern.measured_target == pattern.trigger_price + pattern.measured_move
    assert "S4-R25" in pattern.source_ids and "S5-R40" in pattern.source_ids

    not_lowest = _from_closes(_zig([140, 110, 125, 112, 124.8, 111, 120, 126, 120.5, 128], per=5))
    assert [
        p for p in find_head_and_shoulders(not_lowest, cfg)
        if p.kind == "inverse_head_and_shoulders"
    ] == []


# --------------------------------------------------------------------------- quasimodo

def test_bearish_quasimodo_needs_horizontal_resistance(cfg: Config) -> None:
    """S4-R27 + S6-R50: the lower high must coincide with drawn horizontal resistance."""
    series = _from_closes(_zig([90, 110, 100, 125, 95, 124.8, 100], per=5))
    assert find_quasimodo(series, cfg) == [], "no levels supplied => nothing to coincide with"

    level = Level(
        id="res",
        symbol="TEST",
        tf=Timeframe.H1,
        price=dec(124.8),
        kind=LevelKind.RESISTANCE,
        created_index=0,
        source_ids=("S4-R4",),
    )
    found = find_quasimodo(series, cfg, levels=[level])
    assert found
    quasi = found[0]
    assert quasi.direction is Direction.SHORT
    assert quasi.measured_move is None and quasi.measured_target is None
    assert quasi.confirmed is True
    assert quasi.stop_price is not None and quasi.stop_price > quasi.trigger_price
    assert any("S6-R50" in r for r in quasi.reasons)


def test_quasimodo_needs_the_lower_low_after_the_final_higher_high(cfg: Config) -> None:
    level = Level(
        id="res", symbol="TEST", tf=Timeframe.H1, price=dec(124.8),
        kind=LevelKind.RESISTANCE, created_index=0,
    )
    no_lower_low = _from_closes(_zig([90, 110, 100, 125, 105, 124.8, 110], per=5))
    assert find_quasimodo(no_lower_low, cfg, levels=[level]) == []


# --------------------------------------------------------------------------- hygiene

def test_every_pattern_carries_source_ids_and_a_stable_id(cfg: Config, bull_flag: Series) -> None:
    patterns = PatternDetector().detect(bull_flag, cfg)
    assert patterns
    ids = [p.id for p in patterns]
    assert len(ids) == len(set(ids))
    for pattern in patterns:
        assert pattern.source_ids
        assert pattern.id.startswith("TEST:1H:")
        assert pattern.measured_target_is_theoretical is True


def test_detect_is_ordered_and_deterministic(cfg: Config, bull_flag: Series) -> None:
    det = PatternDetector()
    first = det.detect(bull_flag, cfg)
    second = det.detect(bull_flag, cfg)
    assert [p.id for p in first] == [p.id for p in second]
    assert [p.completion_index for p in first] == sorted(p.completion_index for p in first)


def test_to_confluence_is_pattern_class_only(cfg: Config, bull_flag: Series) -> None:
    det = PatternDetector()
    patterns = det.detect(bull_flag, cfg)
    scored = det.to_confluence(patterns, cfg)
    assert scored
    assert {o.obj_class for o in scored} == {"pattern"}
    assert scored[0].price == patterns[0].trigger_price
    # weight 0.5 in §6.1 — one class only, so a pattern can never satisfy the two-class rule
    assert cfg.confluence_weights["pattern"] == 0.5


def test_no_lookahead(cfg: Config, bull_flag: Series) -> None:
    det = PatternDetector()
    flag = find_flags(bull_flag, cfg)[0]
    assert flag.retest_index is not None
    before = det.detect(bull_flag.head(flag.retest_index), cfg)
    assert all(not (p.kind == "bull_flag" and p.confirmed) for p in before)
    after = det.detect(bull_flag.head(flag.retest_index + 1), cfg)
    assert any(p.kind == "bull_flag" and p.confirmed for p in after)
