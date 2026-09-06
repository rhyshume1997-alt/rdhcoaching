"""Contract tests for tbot.detectors.levels (SPEC.md §5.1 levels, §5.2 the CF-15 flip machine).

Series are hand-built so the right answer is obvious by inspection: a long flat warm-up gives
``ATR(14) == 1.0`` (constant true range), and every retest bar is drawn so its **high or low
lands exactly on the level**, which puts it inside the P9 band whatever the band's width.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config
from tbot.data import synthetic
from tbot.models import ConfluenceClass, FlipState, Level, LevelKind, Series, Timeframe, dec
from tbot.detectors.base import Detector
from tbot.detectors.levels import (
    FlipResult,
    SupportResistanceDetector,
    extra_confirmation_candles,
    flip_kind,
    is_playable,
    role_of_kind,
    run_flip_machine,
    touch_decay_multiplier,
    touch_limit,
)

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
LEVEL = 100.0


# --------------------------------------------------------------------------- helpers

def make_series(rows, tf: str = "4H", symbol: str = "T") -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1_000.0] * len(rows), tf=tf, symbol=symbol,
    )


def warmup(n: int = 25, price: float = 102.0):
    """``n`` bars with a constant true range of 1.0 sitting **above** the level."""
    return [(price, price + 0.5, price - 0.5, price)] * n


def bar(open_: float, high: float, low: float, close: float):
    return (open_, high, low, close)


def from_closes(closes, pad: float = 0.3):
    """Bars whose open is the previous close and whose wicks stick out by ``pad``."""
    rows = []
    prev = closes[0]
    for c in closes:
        rows.append((prev, max(prev, c) + pad, min(prev, c) - pad, c))
        prev = c
    return rows


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def syn():
    return synthetic(seed=7)


def events(flip: FlipResult) -> list[tuple[int, str]]:
    return [(t.bar_index, t.event) for t in flip.transitions]


# =========================================================================== §5.2 flip machine


class TestFlipMachineHappyPath:
    """support -> body close below -> retest that closes below -> confirmed resistance."""

    def series(self):
        rows = warmup()                                  # 0-24 above the level
        rows.append(bar(102.0, 102.5, 97.5, 98.0))       # 25 body close BELOW 100 -> pending
        rows.append(bar(98.0, 99.0, 97.5, 98.5))         # 26 still below, no retest
        rows.append(bar(98.5, 100.0, 98.0, 99.0))        # 27 retest: high == level, closes below
        rows.append(bar(99.0, 99.5, 98.0, 98.5))         # 28 the armed bar
        return make_series(rows)

    def test_breaks_then_confirms_resistance(self, cfg):
        flip = run_flip_machine(self.series(), cfg, LEVEL, "support")
        assert events(flip) == [(25, "break"), (27, "retest_confirm")]
        assert flip.state is FlipState.CONFIRMED_RESISTANCE
        assert flip.kind is LevelKind.SR_CONFIRMED_RESISTANCE
        assert flip.role == "resistance"
        assert (flip.break_index, flip.retest_index, flip.confirmed_index) == (25, 27, 27)
        assert flip.arm_index == 28          # CF-15: entry arms at the OPEN of the next candle
        assert flip.role_since_index == 27   # touch counters reset on the role flip
        assert flip.pending_since_index is None
        assert flip.deviations == 0

    def test_wick_below_the_level_never_flips_it(self, cfg):
        """S2-R1 / S8-R41: only a body close beyond starts the machine."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.0, 101.5))      # deep wick, close still above
        rows.extend(warmup(3))
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert flip.transitions == () and flip.state is FlipState.NONE

    def test_close_exactly_on_the_level_is_not_a_break(self, cfg):
        """S8-R41: "closing exactly on it does not count"."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 99.5, 100.0))
        rows.extend([(100.0, 100.5, 99.5, 100.0)] * 3)
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert flip.state is FlipState.NONE and flip.transitions == ()

    def test_retest_must_close_on_the_new_side(self, cfg):
        """A bar that reaches the band but closes back above is a deviation, not a retest."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))       # 25 break
        rows.append(bar(98.0, 101.5, 97.5, 101.0))       # 26 in the band, closes ABOVE
        rows.extend(warmup(3))
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert events(flip) == [(25, "break"), (26, "deviation")]

    def test_retest_out_of_the_band_does_not_confirm(self, cfg):
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))       # 25 break
        rows.append(bar(98.0, 99.0, 97.5, 98.5))         # 26 nowhere near the band
        rows.append(bar(98.5, 99.2, 98.0, 99.0))         # 27 still short of it
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert events(flip) == [(25, "break")]
        assert flip.state is FlipState.PENDING and flip.pending_since_index == 25


class TestFlipMachineDeviationRollback:
    """S2-R4 / S3-R17: a close back through with no retest-and-rejection keeps the identity."""

    def rows_with_reclaim_at(self, reclaim_close: float):
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))                       # 25 break below
        rows.append(bar(98.0, 98.5, 97.5, 98.2))                         # 26 sitting below
        rows.append(bar(98.2, reclaim_close + 0.5, 98.0, reclaim_close))  # 27 closes back above
        rows.extend(warmup(4))
        return rows

    def test_reclaim_reverts_the_level_to_support(self, cfg):
        flip = run_flip_machine(make_series(self.rows_with_reclaim_at(101.0)), cfg, LEVEL, "support")
        assert events(flip) == [(25, "break"), (27, "deviation")]
        assert flip.state is FlipState.NONE
        assert flip.kind is LevelKind.SUPPORT          # the level keeps its identity
        assert flip.role == "support"
        assert flip.deviations == 1
        assert flip.pending_since_index is None
        assert flip.confirmed_index is None and flip.arm_index is None

    def test_rollback_re_arms_the_machine_for_the_next_break(self, cfg):
        rows = self.rows_with_reclaim_at(101.0)
        rows.append(bar(102.0, 102.5, 96.5, 97.0))     # 32 a second, real break
        rows.append(bar(97.0, 100.0, 96.5, 98.0))      # 33 retest: high == level, closes below
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert events(flip) == [
            (25, "break"), (27, "deviation"), (32, "break"), (33, "retest_confirm"),
        ]
        assert flip.state is FlipState.CONFIRMED_RESISTANCE and flip.deviations == 1

    def test_the_next_bar_after_a_reclaim_can_break_again(self, cfg):
        """The rollback re-arms immediately: no dead bar between a deviation and a new break."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))      # 25 break
        rows.append(bar(98.0, 101.5, 97.5, 101.0))      # 26 reclaim -> deviation
        rows.append(bar(101.0, 101.5, 96.5, 97.0))      # 27 straight back through
        rows.append(bar(97.0, 100.0, 96.5, 98.0))       # 28 retest -> confirmed resistance
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert events(flip) == [
            (25, "break"), (26, "deviation"), (27, "break"), (28, "retest_confirm"),
        ]

    def test_a_confirmed_level_can_break_on_the_very_next_bar(self, cfg):
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))      # 25 break down
        rows.append(bar(98.0, 100.0, 97.5, 99.0))       # 26 retest -> confirmed resistance
        rows.append(bar(99.0, 102.5, 98.5, 102.0))      # 27 immediately back above
        rows.append(bar(102.0, 102.5, 100.0, 101.0))    # 28 retest -> confirmed support
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert events(flip) == [
            (25, "break"), (26, "retest_confirm"), (27, "break"), (28, "retest_confirm"),
        ]
        assert flip.state is FlipState.CONFIRMED_SUPPORT

    def test_deviation_after_the_retest_but_before_the_extra_candle(self, cfg):
        """With a third confirmation candle required, a reclaim in between still rolls back."""
        three = cfg.with_overrides(flip_confirm_candles=3)
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))     # 25 break
        rows.append(bar(98.0, 100.0, 97.5, 99.0))      # 26 retest, closes below -> needs 1 more
        rows.append(bar(99.0, 101.5, 98.5, 101.0))     # 27 reclaim instead
        rows.extend(warmup(3))
        flip = run_flip_machine(make_series(rows), three, LEVEL, "support")
        assert events(flip) == [(25, "break"), (27, "deviation")]
        assert flip.retest_index is None      # the episode was thrown away with the rollback
        assert flip.state is FlipState.NONE and flip.role == "support"

    def test_the_deviation_edge_is_the_only_way_back_without_a_retest(self, cfg):
        """Sitting below the level forever leaves it pending — never silently confirmed."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))
        rows.extend([(98.0, 98.5, 97.5, 98.0)] * 20)
        flip = run_flip_machine(make_series(rows), cfg.with_overrides(pending_sr_expiry_bars=0),
                                LEVEL, "support")
        assert flip.state is FlipState.PENDING and flip.confirmed_index is None


class TestFlipMachineExpiryAndForbiddenEdges:
    def test_pending_expires_back_to_the_original_role(self, cfg):
        short = cfg.with_overrides(pending_sr_expiry_bars=4)
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))     # 25 break
        rows.extend([(98.0, 98.5, 97.5, 98.0)] * 8)    # 26-33 no retest, no reclaim
        flip = run_flip_machine(make_series(rows), short, LEVEL, "support")
        assert events(flip) == [(25, "break"), (29, "expiry")]
        assert flip.state is FlipState.NONE and flip.kind is LevelKind.SUPPORT
        assert flip.expiries == 1

    def test_zero_expiry_means_never_expires(self, cfg):
        never = cfg.with_overrides(pending_sr_expiry_bars=0)
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))
        rows.extend([(98.0, 98.5, 97.5, 98.0)] * 200)
        flip = run_flip_machine(make_series(rows), never, LEVEL, "support")
        assert events(flip) == [(25, "break")] and flip.state is FlipState.PENDING

    def test_pending_to_pending_is_forbidden(self, cfg):
        """S2-R5: deeper closes while pending must not raise a second break event."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))     # 25 break
        rows.append(bar(98.0, 98.5, 96.5, 97.0))       # 26 deeper
        rows.append(bar(97.0, 97.5, 95.5, 96.0))       # 27 deeper still
        flip = run_flip_machine(make_series(rows), cfg.with_overrides(pending_sr_expiry_bars=0),
                                LEVEL, "support")
        assert [e for _, e in events(flip)] == ["break"]


class TestFlipMachineReverseChain:
    """The mirror: resistance -> broken above -> retested -> confirmed support, and back again."""

    def test_resistance_flips_to_support(self, cfg):
        rows = [(98.0, 98.5, 97.5, 98.0)] * 25         # below the level
        rows.append(bar(98.0, 102.5, 97.5, 102.0))     # 25 body close ABOVE 100
        rows.append(bar(102.0, 102.5, 100.0, 101.0))   # 26 retest: low == level, closes above
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "resistance")
        assert events(flip) == [(25, "break"), (26, "retest_confirm")]
        assert flip.state is FlipState.CONFIRMED_SUPPORT
        assert flip.kind is LevelKind.SR_CONFIRMED_SUPPORT and flip.role == "support"

    def test_full_round_trip_support_to_resistance_to_support(self, cfg):
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))     # 25 break down
        rows.append(bar(98.0, 100.0, 97.5, 99.0))      # 26 retest -> confirmed resistance
        rows.extend([(99.0, 99.5, 98.5, 99.0)] * 4)    # 27-30 below the new resistance
        rows.append(bar(99.0, 102.5, 98.5, 102.0))     # 31 break back up
        rows.append(bar(102.0, 102.5, 100.0, 101.0))   # 32 retest -> confirmed support again
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert events(flip) == [
            (25, "break"), (26, "retest_confirm"), (31, "break"), (32, "retest_confirm"),
        ]
        assert flip.state is FlipState.CONFIRMED_SUPPORT and flip.role == "support"
        assert flip.role_since_index == 32 and flip.arm_index == 33


class TestExtraConfirmationCandle:
    """S2-R7: below ``flip_extra_candle_below_tf`` one more candle is required."""

    def rows(self):
        rows = warmup()
        rows.append(bar(102.0, 102.5, 97.5, 98.0))     # 25 break
        rows.append(bar(98.0, 100.0, 97.5, 99.0))      # 26 retest, closes below
        rows.append(bar(99.0, 99.5, 98.0, 98.5))       # 27 extra confirming close
        return rows

    def test_counts_by_timeframe(self, cfg):
        assert extra_confirmation_candles(cfg, Timeframe.H1) == 1
        assert extra_confirmation_candles(cfg, Timeframe.H4) == 0
        assert extra_confirmation_candles(cfg, Timeframe.D1) == 0
        assert extra_confirmation_candles(cfg.with_overrides(flip_confirm_candles=3),
                                          Timeframe.H4) == 1
        assert extra_confirmation_candles(cfg.with_overrides(
            flip_extra_candle_below_tf="disabled"), Timeframe.M15) == 0

    def test_lower_timeframe_needs_the_extra_candle(self, cfg):
        h4 = run_flip_machine(make_series(self.rows(), tf="4H"), cfg, LEVEL, "support")
        h1 = run_flip_machine(make_series(self.rows(), tf="1H"), cfg, LEVEL, "support")
        assert h4.confirmed_index == 26 and h4.arm_index == 27
        assert h1.confirmed_index == 27 and h1.arm_index == 28

    def test_lower_timeframe_without_the_extra_candle_stays_pending(self, cfg):
        rows = self.rows()[:-1]
        h1 = run_flip_machine(make_series(rows, tf="1H"), cfg, LEVEL, "support")
        assert h1.state is FlipState.PENDING and h1.retest_index == 26


class TestFlipMachineMisc:
    def test_break_move_away_pct_scores_the_break(self, cfg):
        """S2-R6: the distance price travelled away from the level after the breaking close."""
        rows = warmup()
        rows.append(bar(102.0, 102.5, 89.0, 90.0))     # 25 break, wick to 89 == 11 % away
        rows.append(bar(90.0, 100.0, 89.5, 99.0))      # 26 retest
        flip = run_flip_machine(make_series(rows), cfg, LEVEL, "support")
        assert flip.break_move_away_pct == pytest.approx(Decimal("11.0"))

    def test_wick_break_when_body_close_is_not_required(self, cfg):
        loose = cfg.with_overrides(flip_requires_body_close=False)
        rows = warmup()
        rows.append(bar(102.0, 102.5, 99.0, 101.5))    # wick below only
        rows.extend(warmup(3))
        assert run_flip_machine(make_series(rows), loose, LEVEL, "support").break_index == 25
        assert run_flip_machine(make_series(rows), cfg, LEVEL, "support").break_index is None

    def test_windows_and_bad_arguments(self, cfg):
        s = make_series(warmup(30))
        assert run_flip_machine(s, cfg, LEVEL, "support", start_index=5, end_index=9).state \
            is FlipState.NONE
        with pytest.raises(ValueError):
            run_flip_machine(s, cfg, LEVEL, "support", start_index=10, end_index=5)
        with pytest.raises(ValueError):
            run_flip_machine(make_series([]), cfg, LEVEL, "support")

    def test_role_and_kind_helpers(self):
        assert role_of_kind(LevelKind.RANGE_LOW) == "support"
        assert role_of_kind(LevelKind.SR_CONFIRMED_RESISTANCE) == "resistance"
        assert flip_kind(FlipState.PENDING, "support") is LevelKind.SR_PENDING
        assert flip_kind(FlipState.NONE, "resistance") is LevelKind.RESISTANCE
        with pytest.raises(ValueError):
            role_of_kind(LevelKind.MID_RANGE)


# =========================================================================== CF-07 limits


class TestTouchLimitsAndDecay:
    def test_touch_limit_by_object_kind(self, cfg):
        assert touch_limit(cfg) == 3                                   # bare line, S4-R14
        assert touch_limit(cfg, is_range_boundary=True) == 6           # S4-C1
        assert touch_limit(cfg, is_zone=True) is None                  # the fill rule governs
        assert touch_limit(cfg.with_overrides(zone_touch_uses_fill_rule_not_count=False),
                           is_zone=True) == 3

    def test_is_playable_applies_the_hard_veto(self, cfg):
        lv = Level(id="x", symbol="T", tf=Timeframe.H4, price=dec(100), kind=LevelKind.SUPPORT,
                   created_index=0, touch_count=3)
        assert is_playable(lv, cfg)
        lv.touch_count = 4
        assert not is_playable(lv, cfg)
        assert is_playable(lv, cfg, is_range_boundary=True)
        lv.touch_count = 7
        assert not is_playable(lv, cfg, is_range_boundary=True)
        assert is_playable(lv, cfg, is_zone=True)

    def test_decay_curve_is_indexed_by_touch_number(self, cfg):
        curve = cfg.touch_size_decay          # owned by risk.py; passed in, never read here
        assert touch_decay_multiplier(1, curve) == dec(1.0)
        assert touch_decay_multiplier(2, curve) == dec(1.0)
        assert touch_decay_multiplier(3, curve) == dec(1.0)      # Q2: the 3rd touch is full size
        assert touch_decay_multiplier(4, curve) == dec(0.66)
        assert touch_decay_multiplier(5, curve) == dec(0.5)       # Q2: S8 `[00:54:14]`
        assert touch_decay_multiplier(9, curve) == dec(0.5)      # past the end, the last holds
        with pytest.raises(ValueError):
            touch_decay_multiplier(0, curve)
        with pytest.raises(ValueError):
            touch_decay_multiplier(1, [])


# =========================================================================== §5.1 detector


class TestDetectorContract:
    def test_protocol_surface(self):
        d = SupportResistanceDetector()
        assert isinstance(d, Detector)
        assert d.name == "support_resistance_levels" and d.stage == 3
        assert d.produces == (ConfluenceClass.SR_LEVEL.value,)
        assert "S4-R4" in d.source_ids and "CF-15" in d.source_ids

    def test_empty_and_tiny_series(self, cfg):
        d = SupportResistanceDetector()
        assert d.detect(make_series([]), cfg) == []
        assert d.detect(make_series(warmup(3)), cfg) == []

    def test_every_object_carries_source_ids_and_a_deterministic_id(self, cfg, syn):
        d = SupportResistanceDetector()
        first = d.detect(syn.series, cfg)
        second = d.detect(syn.series, cfg)
        assert [lv.id for lv in first] == [lv.id for lv in second]
        assert [lv.price for lv in first] == [lv.price for lv in second]
        assert first and all(lv.source_ids for lv in first)
        assert all(lv.id.startswith("SYNTH:1H:support_resistance_levels:") for lv in first)
        assert all("uuid" not in lv.id for lv in first)

    def test_ordered_by_completion_bar(self, cfg, syn):
        levels = SupportResistanceDetector().detect(syn.series, cfg)
        assert [lv.created_index for lv in levels] == sorted(lv.created_index for lv in levels)

    def test_finds_the_synthetic_range_boundaries(self, cfg, syn):
        levels = SupportResistanceDetector().detect(syn.series, cfg)
        prices = [float(lv.price) for lv in levels]
        assert any(abs(p - syn.features.range_high) < 0.2 for p in prices)
        assert any(abs(p - syn.features.range_low) < 0.2 for p in prices)

    def test_touch_history_matches_the_p4_contract(self, cfg, syn):
        """INTERFACES.md §8.3 documents five touches of ``range_high`` at bars 23/31/39/47/55."""
        levels = SupportResistanceDetector().detect(syn.series, cfg)
        top = next(lv for lv in levels if abs(float(lv.price) - syn.features.range_high) < 0.2)
        assert top.touch_count == 5
        assert [i for i, _ in top.touch_history] == [23, 31, 39, 47, 55]
        assert top.kind is LevelKind.SR_PENDING       # broken at bar 60, never retested
        assert top.flip_state is FlipState.PENDING
        assert top.pending_since_index == 60
        assert not is_playable(top, cfg)              # CF-07: five touches on a bare line

    def test_no_lookahead(self, cfg, syn):
        """A detector standing on bar i may only reference bars <= i."""
        d = SupportResistanceDetector()
        for i in (40, 60, 80, 99):
            for lv in d.detect(syn.series.head(i + 1), cfg):
                assert lv.created_index <= i
                assert all(b <= i for b, _ in lv.touch_history)
                if lv.pending_since_index is not None:
                    assert lv.pending_since_index <= i

    def test_history_is_a_prefix_as_bars_arrive(self, cfg, syn):
        """Growing the series must not rewrite what an earlier bar already saw (no repainting)."""
        d = SupportResistanceDetector()
        early = {lv.price: lv.touch_history for lv in d.detect(syn.series.head(56), cfg)}
        later = {lv.price: lv.touch_history for lv in d.detect(syn.series.head(60), cfg)}
        for price, hist in early.items():
            if price in later:
                assert later[price][:len(hist)] == hist

    def flip_series(self):
        """Two clean swing lows at 100, then a break below and a retest that closes below."""
        closes = [104.0] * 4
        for _ in range(2):
            closes += [103.0, 102.0, 101.0, 100.0, 101.0, 102.0, 103.0, 104.0]
        rows = from_closes(closes)
        rows.append(bar(104.0, 104.3, 96.7, 97.0))       # 20 body close below 100
        rows.append(bar(97.0, 100.0, 96.7, 98.0))        # 21 retest: high == level, closes below
        rows.extend([(98.0, 98.3, 97.7, 98.0)] * 6)      # 22-27 holding below
        return make_series(rows, tf="4H")

    def test_flip_state_reaches_the_level_object(self, cfg):
        s = self.flip_series()
        levels = SupportResistanceDetector().detect(s, cfg)
        flipped = [lv for lv in levels if lv.flip_state is FlipState.CONFIRMED_RESISTANCE]
        assert flipped, [(float(lv.price), lv.kind.value, lv.flip_state.value) for lv in levels]
        lv = flipped[0]
        assert lv.price == dec(100.0)
        assert lv.kind is LevelKind.SR_CONFIRMED_RESISTANCE
        assert lv.pending_since_index is None
        assert lv.break_move_away_pct is not None and float(lv.break_move_away_pct) > 3.0
        assert lv.is_untested_sr is True          # S6-R39: flipped and not touched since
        assert "CF-15" in lv.source_ids

    def test_a_second_touch_after_the_flip_clears_untested(self, cfg):
        rows = list(self.flip_series().frame.itertuples(index=False, name=None))
        rows = [(r[0], r[1], r[2], r[3]) for r in rows]
        rows.append(bar(98.0, 100.0, 97.7, 99.0))        # a fresh rejection at the flipped level
        rows.extend([(99.0, 99.3, 98.7, 99.0)] * 4)
        s = make_series(rows, tf="4H")
        lv = next(l for l in SupportResistanceDetector().detect(s, cfg)
                  if l.flip_state is FlipState.CONFIRMED_RESISTANCE)
        assert lv.touch_count == 2 and lv.is_untested_sr is False

    def test_to_confluence_maps_price_and_class(self, cfg, syn):
        d = SupportResistanceDetector()
        levels = d.detect(syn.series, cfg)
        objs = d.to_confluence(levels, cfg)
        assert len(objs) == len(levels)
        assert {o.obj_class for o in objs} == {ConfluenceClass.SR_LEVEL.value}
        assert [o.price for o in objs] == [lv.price for lv in levels]
        assert all(o.source_ids == lv.source_ids for o, lv in zip(objs, levels))
        assert all(o.tf is Timeframe.H1 for o in objs)
