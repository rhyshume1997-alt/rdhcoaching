"""Tests for tbot.detectors.structure (SPEC.md §5.7)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest

import tbot.primitives as P
from tbot.config import Config
from tbot.data import synthetic
from tbot.detectors.base import Detector
from tbot.detectors.structure import (
    MSB,
    StructureExit,
    StructureReclaim,
    StructureDetector,
    bias_invalidation_level,
    body_close_through,
    find_msbs,
    find_reclaims,
    find_structure_exits,
    htf_veto_reason,
    structure_state,
    structure_tf_for,
)
from tbot.models import Direction, Series, SwingKind, Timeframe, Trend, dec


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


def _from_closes(closes: Sequence[float], wick: float = 0.05, tf: Timeframe = Timeframe.H1) -> Series:
    opens = [closes[0]] + list(closes[:-1])
    bars = [
        (o, max(o, c) + wick, min(o, c) - wick, c) for o, c in zip(opens, closes)
    ]
    return _ohlc(bars, tf=tf)


def _leg(start: float, stop: float, step: float) -> list[float]:
    out: list[float] = []
    x = start
    while (step > 0 and x <= stop) or (step < 0 and x >= stop):
        out.append(round(x, 6))
        x += step
    return out


#: An up-trending zigzag (higher highs, higher lows) that then closes below its last higher low.
UPTREND_THEN_BREAK = (
    _leg(100, 92, -2)          # down to the first low
    + _leg(94, 106, 2)         # up to H1
    + _leg(104, 96, -2)        # down to L2 (higher low)
    + _leg(98, 112, 2)         # up to H2 (higher high)
    + _leg(110, 102, -2)       # down to L3 (higher low)
    + _leg(104, 116, 2)        # up to H3
    + _leg(114, 98, -2)        # the break: closes below L3 = 102
    + _leg(100, 102, 1)        # rally back to retest the broken level
    + _leg(101, 90, -1)        # rejection and continuation down
)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def broken() -> Series:
    return _from_closes(UPTREND_THEN_BREAK)


# --------------------------------------------------------------------------- protocol

def test_detector_satisfies_protocol(cfg: Config) -> None:
    det = StructureDetector()
    assert isinstance(det, Detector)
    assert det.name == "structure" and det.stage == 2
    assert det.produces == ("sr_level",)
    assert det.source_ids


def test_structure_tf_map_is_cf24(cfg: Config) -> None:
    assert structure_tf_for(Timeframe.H1, cfg) is Timeframe.H4
    assert structure_tf_for(Timeframe.H4, cfg) is Timeframe.H12
    assert structure_tf_for(Timeframe.W1, cfg) is Timeframe.W1        # clamped at the top
    assert structure_tf_for(Timeframe.H1, cfg.with_overrides(structure_tf_offset=1)) is Timeframe.H2


# --------------------------------------------------------------------------- trend / state

def test_trend_state_reads_higher_highs_and_higher_lows(cfg: Config, broken: Series) -> None:
    pivots = P.swing_points(broken, cfg)
    highs = [p for p in pivots if p.kind is SwingKind.HIGH]
    lows = [p for p in pivots if p.kind is SwingKind.LOW]
    assert len(highs) >= 2 and len(lows) >= 2

    # as of the last confirmed high of the up-leg the structure is an uptrend
    at = highs[1].confirmed_at_index
    state = structure_state(broken, cfg, pivots=pivots, at_index=at)
    assert state.trend is Trend.UP
    assert state.last_higher_low is not None
    assert state.last_higher_low.price > lows[0].price


def test_trend_state_is_neutral_without_enough_pivots(cfg: Config) -> None:
    flat = _from_closes([100.0] * 12)
    assert structure_state(flat, cfg).trend is Trend.NEUTRAL


def test_synthetic_is_an_uptrend_with_no_structure_break(cfg: Config) -> None:
    series = synthetic(seed=7).series
    det = StructureDetector()
    assert det.state_at(series, cfg).trend is Trend.UP
    assert det.detect(series, cfg) == []


# --------------------------------------------------------------------------- MSB

def test_bearish_msb_fires_on_a_body_close_below_the_last_higher_low(cfg: Config, broken: Series) -> None:
    msbs = find_msbs(broken, cfg)
    bearish = [m for m in msbs if m.direction is Direction.SHORT]
    assert bearish, "the down-leg closes below the last higher low"
    msb = bearish[0]
    state = structure_state(broken, cfg, at_index=msb.break_index - 1)
    assert state.last_higher_low is not None
    assert msb.broken_price == state.last_higher_low.price
    assert msb.close_price < msb.broken_price
    assert msb.broken_swing_index < msb.break_index
    assert "S7-R12" in msb.source_ids and "CF-22" in msb.source_ids


def test_msb_fires_once_per_broken_swing(cfg: Config, broken: Series) -> None:
    msbs = find_msbs(broken, cfg)
    ids = [m.broken_swing_id for m in msbs]
    assert len(ids) == len(set(ids))


def test_msb_uses_the_body_close_not_the_wick(cfg: Config) -> None:
    """A wick through the higher low with the body closing back above is not an MSB (S7-R12)."""
    closes = UPTREND_THEN_BREAK[: len(UPTREND_THEN_BREAK) - 30]
    series = _from_closes(closes)
    state = structure_state(series, cfg)
    assert state.last_higher_low is not None
    level = float(state.last_higher_low.price)

    bars = [
        (b.open, b.high, b.low, b.close)
        for b in (series.candle(i) for i in range(len(series)))
    ]
    bars = [(float(o), float(h), float(l), float(c)) for o, h, l, c in bars]
    # append a bar that wicks well below the level but closes back above it
    prev_close = bars[-1][3]
    bars.append((prev_close, prev_close + 0.1, level - 3.0, level + 1.0))
    wicked = _ohlc(bars)
    assert not [m for m in find_msbs(wicked, cfg) if m.direction is Direction.SHORT]

    # the same bar closing *below* the level is an MSB
    bars[-1] = (prev_close, prev_close + 0.1, level - 3.0, level - 1.0)
    closed = _ohlc(bars)
    assert [m for m in find_msbs(closed, cfg) if m.direction is Direction.SHORT]


#: Two swing lows, the second higher and printed by a GREEN bar whose body low is its open —
#: so the pivot's body price (96) and its line-chart price (its close, 99) differ.
_TIE_BARS = [
    (110.0, 110.2, 109.8, 110.0),
    (110.0, 110.2, 107.8, 108.0),
    (108.0, 108.2, 105.8, 106.0),
    (106.0, 106.2, 89.80, 90.00),     # L1, the lower low
    (90.0, 92.2, 89.8, 92.0),
    (92.0, 94.2, 91.8, 94.0),
    (94.0, 96.2, 93.8, 96.0),
    (96.0, 104.2, 95.8, 104.0),
    (104.0, 106.2, 103.8, 106.0),
    (106.0, 108.2, 105.8, 108.0),
    (108.0, 110.2, 107.8, 110.0),
    (96.0, 99.2, 95.80, 99.00),       # L2, the higher low: body low 96 (its open), close 99
    (99.0, 101.2, 98.8, 101.0),
    (101.0, 103.2, 100.8, 103.0),
    (103.0, 105.2, 102.8, 105.0),
    (105.0, 107.2, 104.8, 107.0),
]


def test_line_chart_tiebreaker_resolves_an_exact_tie(cfg: Config) -> None:
    """S7-R11 / S8-R27: on an exact body tie, the line chart (closes) decides."""
    base = _ohlc(_TIE_BARS)
    pivots = [p for p in P.swing_points(base, cfg) if p.kind is SwingKind.LOW]
    assert [float(p.price) for p in pivots] == [90.0, 96.0]
    higher_low = pivots[-1]
    assert higher_low.price == dec(96.0)
    assert dec(base.close[higher_low.bar_index]) == dec(99.0)   # the line-chart price differs

    # a close landing exactly ON the body level: the strict body test cannot decide it
    tie = _ohlc(_TIE_BARS + [(107.0, 107.2, 95.5, 96.0)])
    assert body_close_through(tie, len(tie) - 1, higher_low.price, Direction.SHORT) == (False, False)

    # switching to the line chart resolves it, and the MSB records that it did
    broke, used_line = body_close_through(
        tie, len(tie) - 1, higher_low.price, Direction.SHORT,
        line_chart_level=dec(tie.close[higher_low.bar_index]),
    )
    assert broke and used_line
    bearish = [m for m in find_msbs(tie, cfg) if m.direction is Direction.SHORT]
    assert bearish and bearish[0].line_chart_tiebreak is True
    assert bearish[0].break_index == len(tie) - 1
    assert "S8-R27" in bearish[0].source_ids


def test_line_chart_tiebreaker_does_not_widen_the_primary_test(cfg: Config) -> None:
    """The tiebreaker only ever fires on an exact tie, and only when the line chart agrees."""
    tie = _ohlc(_TIE_BARS + [(107.0, 107.2, 95.5, 96.0)])
    higher_low = [p for p in P.swing_points(tie, cfg) if p.kind is SwingKind.LOW][-1]

    # a close *above* the level is not a break, tiebreaker or not
    assert body_close_through(
        tie, len(tie) - 1, higher_low.price + dec(1), Direction.SHORT,
        line_chart_level=dec(999),
    ) == (True, False)
    above = _ohlc(_TIE_BARS + [(107.0, 107.2, 95.5, 97.0)])
    assert [m for m in find_msbs(above, cfg) if m.direction is Direction.SHORT] == []

    # a tie whose line-chart price is the same as the body price stays unresolved
    assert body_close_through(
        tie, len(tie) - 1, higher_low.price, Direction.SHORT,
        line_chart_level=higher_low.price,
    ) == (False, True)


def test_no_msb_while_price_holds_above_structure(cfg: Config) -> None:
    holding = _from_closes(
        _leg(100, 92, -2) + _leg(94, 106, 2) + _leg(104, 96, -2) + _leg(98, 112, 2) + _leg(110, 104, -2)
    )
    assert [m for m in find_msbs(holding, cfg) if m.direction is Direction.SHORT] == []


# --------------------------------------------------------------------------- retest

def test_entry_needs_the_retest_not_just_the_break(cfg: Config, broken: Series) -> None:
    msb = [m for m in find_msbs(broken, cfg) if m.direction is Direction.SHORT][0]
    assert msb.retest_required is True
    assert msb.retest_index is not None, "the rally back to the broken level is the retest"
    assert msb.retest_index > msb.break_index
    assert msb.entry_armed is True
    assert msb.entry_price == dec(broken.close[msb.retest_index])
    assert "S7-R16" in msb.source_ids


def test_retest_timeout_disarms_the_entry(cfg: Config, broken: Series) -> None:
    tight = cfg.with_overrides(msb_retest_timeout_bars=1)
    msb = [m for m in find_msbs(broken, tight) if m.direction is Direction.SHORT][0]
    assert msb.retest_index is None
    assert msb.entry_armed is False
    assert msb.reasons and "msb_retest_timeout_bars" in msb.reasons[0]


def test_detection_still_emits_when_the_retest_never_comes(cfg: Config, broken: Series) -> None:
    """CF-22 separates detection from action: the MSB object exists either way."""
    no_retest = cfg.with_overrides(msb_retest_timeout_bars=1)
    assert find_msbs(broken, no_retest)


def test_entry_requires_retest_can_be_switched_off(cfg: Config, broken: Series) -> None:
    relaxed = cfg.with_overrides(msb_entry_requires_retest=False, msb_retest_timeout_bars=1)
    msb = [m for m in find_msbs(broken, relaxed) if m.direction is Direction.SHORT][0]
    assert msb.retest_required is False and msb.entry_armed is True


# --------------------------------------------------------------------------- Q11 deviation

#: The same structure, but after the break price closes *back above* the broken higher low
#: without ever rejecting from it — S2's "deviation".
UPTREND_THEN_DEVIATION = (
    _leg(100, 92, -2)
    + _leg(94, 106, 2)
    + _leg(104, 96, -2)
    + _leg(98, 112, 2)
    + _leg(110, 102, -2)       # L3 = 102
    + _leg(104, 116, 2)
    + _leg(114, 98, -2)        # the break: closes below L3 = 102
    + _leg(100, 115, 3)        # straight back above 102 and away — no rejection, a deviation
    + _leg(113, 105, -2)
)


def test_a_close_back_beyond_the_broken_level_is_a_deviation(cfg: Config) -> None:
    """**Q11** — ``msb_deviation_invalidates``: his real invalidation is a condition, not a clock.

    S2 ``[00:25:56]``: *"if we don't get a retest… and we go back above with no retest, that is a
    deviation."*  §11 had no key for this at all; the only invalidation the MSB carried was
    ``msb_retest_timeout_bars``, an **[OUR CHOICE]** bar count he explicitly declines to give —
    *"next candle or however many candles it takes"* (S4 ``[00:35:08]``).

    Detection still stands: CF-22 separates detection from action, so the MSB object is emitted
    either way.  What the deviation kills is ``entry_armed``.
    """
    assert cfg.msb_deviation_invalidates is True
    series = _from_closes(UPTREND_THEN_DEVIATION)
    bearish = [m for m in find_msbs(series, cfg) if m.direction is Direction.SHORT]
    assert bearish, "the break itself still happened and is still detected"
    msb = bearish[0]

    assert msb.deviated is True
    assert msb.deviation_index is not None and msb.deviation_index > msb.break_index
    assert msb.retest_index is None
    assert msb.entry_armed is False
    assert msb.reasons and "deviation" in msb.reasons[0]
    assert "S2 `[00:25:56]`" in msb.source_ids


def test_the_deviation_rule_can_be_switched_off(cfg: Config) -> None:
    off = cfg.with_overrides(msb_deviation_invalidates=False)
    series = _from_closes(UPTREND_THEN_DEVIATION)
    msb = [m for m in find_msbs(series, off) if m.direction is Direction.SHORT][0]
    assert msb.deviated is False
    assert msb.reasons and "msb_retest_timeout_bars" in msb.reasons[0]


def test_a_genuine_retest_is_not_a_deviation(cfg: Config, broken: Series) -> None:
    """The baseline series rallies back *to* the level and rejects — that is the trade."""
    msb = [m for m in find_msbs(broken, cfg) if m.direction is Direction.SHORT][0]
    assert msb.deviated is False and msb.retest_index is not None and msb.entry_armed is True


# --------------------------------------------------------------------------- exits

def test_break_only_exit_fires_on_the_break(cfg: Config, broken: Series) -> None:
    assert cfg.msb_exit_mode == "break_only"
    msb = [m for m in find_msbs(broken, cfg) if m.direction is Direction.SHORT][0]
    exits = [e for e in find_structure_exits(broken, cfg) if e.msb_id == msb.id]
    assert exits and exits[0].confirmed is True
    assert exits[0].signal_index == msb.break_index


def test_two_step_exit_waits_for_the_confirming_lower_high(cfg: Config, broken: Series) -> None:
    two_step = cfg.with_overrides(msb_exit_mode="break_plus_lower_high")
    msb = [m for m in find_msbs(broken, two_step) if m.direction is Direction.SHORT][0]
    exit_ = [e for e in find_structure_exits(broken, two_step) if e.msb_id == msb.id][0]
    assert exit_.mode == "break_plus_lower_high"
    assert exit_.confirmed is True
    assert exit_.confirm_index is not None and exit_.confirm_index > msb.break_index
    assert exit_.signal_index == exit_.confirm_index
    assert "S3-R21" in exit_.source_ids


def test_two_step_exit_is_unconfirmed_without_a_lower_high(cfg: Config, broken: Series) -> None:
    """Truncating the series before the confirming lower high leaves the exit pending."""
    two_step = cfg.with_overrides(msb_exit_mode="break_plus_lower_high")
    msb = [m for m in find_msbs(broken, two_step) if m.direction is Direction.SHORT][0]
    short = broken.head(msb.break_index + 3)
    exits = [e for e in find_structure_exits(short, two_step) if e.break_index == msb.break_index]
    assert exits and exits[0].confirmed is False
    assert exits[0].confirm_index is None and exits[0].signal_index is None


def test_two_step_exit_costs_a_leg_relative_to_break_only(cfg: Config, broken: Series) -> None:
    one = find_structure_exits(broken, cfg)[0]
    two = find_structure_exits(broken, cfg.with_overrides(msb_exit_mode="break_plus_lower_high"))[0]
    assert two.signal_index is not None and one.signal_index is not None
    assert two.signal_index > one.signal_index


# --------------------------------------------------------------------------- reclaim

def test_reclaim_is_a_body_close_back_through_the_lost_level(cfg: Config) -> None:
    closes = list(UPTREND_THEN_BREAK[: len(UPTREND_THEN_BREAK) - 12]) + _leg(100, 110, 2)
    series = _from_closes(closes)
    msb = [m for m in find_msbs(series, cfg) if m.direction is Direction.SHORT][0]
    reclaims = [r for r in find_reclaims(series, cfg) if r.msb_id == msb.id]
    assert reclaims, "price closed back above the broken higher low"
    reclaim = reclaims[0]
    assert reclaim.direction is Direction.LONG
    assert reclaim.reclaim_index > msb.break_index
    assert reclaim.close_price > reclaim.level_price
    assert "S8-R28" in reclaim.source_ids


def test_reclaim_alone_is_never_enough(cfg: Config) -> None:
    """S8-R28: a reclaim needs the flip; the flip machine is CF-15 in detectors/levels.py."""
    closes = list(UPTREND_THEN_BREAK[: len(UPTREND_THEN_BREAK) - 12]) + _leg(100, 110, 2)
    series = _from_closes(closes)
    for reclaim in find_reclaims(series, cfg):
        assert reclaim.requires_flip_confirmation is True


def test_one_reclaim_per_msb(cfg: Config) -> None:
    closes = list(UPTREND_THEN_BREAK[: len(UPTREND_THEN_BREAK) - 12]) + _leg(100, 110, 2) + _leg(108, 96, -2) + _leg(98, 112, 2)
    series = _from_closes(closes)
    reclaims = find_reclaims(series, cfg)
    assert len(reclaims) == len({r.msb_id for r in reclaims})


def test_no_reclaim_when_price_never_comes_back(cfg: Config, broken: Series) -> None:
    msb = [m for m in find_msbs(broken, cfg) if m.direction is Direction.SHORT][0]
    assert msb.broken_price == dec(102.0)
    assert [r for r in find_reclaims(broken, cfg) if r.msb_id == msb.id] == []


# --------------------------------------------------------------------------- bias level (CF-23)

def test_bias_level_needs_confluence(cfg: Config, broken: Series) -> None:
    assert bias_invalidation_level(broken, cfg) is None, "no objects supplied => no bias level"

    pivots = P.swing_points(broken, cfg)
    low = min((p for p in pivots if p.kind is SwingKind.LOW), key=lambda p: p.price)
    objects = [
        P.ConfluenceObject("lvl", low.price, "sr_level"),
        P.ConfluenceObject("zone", low.price, "zone"),
    ]
    level = bias_invalidation_level(broken, cfg, confluence_objects=objects)
    assert level is not None
    assert level.price == low.price
    assert "CF-23" in level.source_ids


def test_bias_level_respects_its_switch(cfg: Config, broken: Series) -> None:
    pivots = P.swing_points(broken, cfg)
    low = min((p for p in pivots if p.kind is SwingKind.LOW), key=lambda p: p.price)
    objects = [
        P.ConfluenceObject("lvl", low.price, "sr_level"),
        P.ConfluenceObject("zone", low.price, "zone"),
    ]
    off = cfg.with_overrides(bias_level_enabled=False)
    assert bias_invalidation_level(broken, off, confluence_objects=objects) is None


def test_technical_higher_low_still_drives_msb(cfg: Config, broken: Series) -> None:
    """CF-23: the bias level is a *separate* object; ``higher_low_selection`` stays technical."""
    assert cfg.higher_low_selection == "technical"
    msb = [m for m in find_msbs(broken, cfg) if m.direction is Direction.SHORT][0]
    state = structure_state(broken, cfg, at_index=msb.break_index - 1)
    assert state.last_higher_low is not None
    assert msb.broken_swing_id == state.last_higher_low.id


# --------------------------------------------------------------------------- HTF veto

def test_htf_veto_blocks_the_opposing_direction(cfg: Config) -> None:
    up = synthetic(seed=7).series
    assert htf_veto_reason(up, cfg, Direction.SHORT) is not None
    assert htf_veto_reason(up, cfg, Direction.LONG) is None


def test_htf_veto_can_be_disabled(cfg: Config) -> None:
    up = synthetic(seed=7).series
    assert htf_veto_reason(up, cfg.with_overrides(htf_veto_enabled=False), Direction.SHORT) is None


# --------------------------------------------------------------------------- protocol hygiene

def test_every_emitted_object_carries_source_ids(cfg: Config, broken: Series) -> None:
    objects = StructureDetector().detect(broken, cfg)
    assert objects
    for obj in objects:
        assert obj.source_ids, f"{obj.id} has no source_ids"
        assert obj.id.startswith("TEST:1H:")


def test_detect_is_ordered_by_completion_bar(cfg: Config, broken: Series) -> None:
    objects = StructureDetector().detect(broken, cfg)
    keys = []
    for obj in objects:
        if isinstance(obj, MSB):
            keys.append(obj.break_index)
        elif isinstance(obj, StructureExit):
            keys.append(obj.signal_index if obj.signal_index is not None else obj.break_index)
        elif isinstance(obj, StructureReclaim):
            keys.append(obj.reclaim_index)
    assert keys == sorted(keys)


def test_detect_is_deterministic(cfg: Config, broken: Series) -> None:
    det = StructureDetector()
    first = [o.id for o in det.detect(broken, cfg)]
    second = [o.id for o in det.detect(broken, cfg)]
    assert first == second


def test_no_lookahead_bar_by_bar(cfg: Config, broken: Series) -> None:
    """Objects found on a prefix must also be found on the full series, unchanged."""
    det = StructureDetector()
    full = {o.id: o for o in det.detect(broken, cfg)}
    msb = [m for m in find_msbs(broken, cfg) if m.direction is Direction.SHORT][0]
    prefix = det.detect(broken.head(msb.break_index + 1), cfg)
    prefix_msbs = [o for o in prefix if isinstance(o, MSB)]
    assert prefix_msbs, "the break is visible on the bar it happens"
    for obj in prefix_msbs:
        assert obj.id in full
        assert full[obj.id].break_index == obj.break_index


def test_to_confluence_prices_the_broken_level(cfg: Config, broken: Series) -> None:
    det = StructureDetector()
    objects = det.detect(broken, cfg)
    scored = det.to_confluence(objects, cfg)
    assert scored
    for obj in scored:
        assert obj.obj_class in det.produces
        assert obj.source_ids
    msb = next(o for o in objects if isinstance(o, MSB))
    assert any(s.id == msb.id and s.price == msb.broken_price for s in scored)
