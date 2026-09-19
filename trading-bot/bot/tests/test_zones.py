"""Contract tests for tbot.detectors.zones (SPEC.md §5.5, CF-08 / CF-10 / CF-11 / CF-12 / CF-13).

Two kinds of fixture:

* :func:`tbot.data.synthetic` — its :class:`~tbot.data.SyntheticFeatures` names the exact bars of
  the embedded impulse → consolidation → breakout demand zone, so the detector's output is
  checked against known indices rather than against itself;
* hand-built series (:func:`demand_series` and friends) whose every number is chosen so the
  answer is obvious by inspection: 25 flat warm-up bars give ``ATR(14) == 1.0``, the
  consolidation carries **no wicks** so the P5 box is exactly ``(103.6, 104.4)`` with midpoint
  ``104.0``, and the move away lands at 4.857 % — deliberately between the 1H row of the CF-11
  table (4.0 %) and the 2H row (5.0 %).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config
from tbot.data import synthetic
from tbot.models import (
    Box,
    Direction,
    FlipState,
    Level,
    LevelKind,
    Series,
    Timeframe,
    Zone,
    ZoneClass,
    ZoneSide,
    dec,
)
import tbot.primitives as P
from tbot.detectors.base import Detector
from tbot.detectors.zones import (
    SupplyDemandZoneDetector,
    ZoneRejection,
    count_bodies,
    death_index,
    fill_invalidation_pct,
    max_size_atr,
    min_size_atr,
    rescue_dead_zones,
    zone_strength,
    zone_touch_windows,
)
from tbot.detectors import zones as Z

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- helpers

def make_series(rows, tf: str = "1H", symbol: str = "T") -> Series:
    """Build a Series from ``(open, high, low, close)`` rows, one bar per timeframe step."""
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1_000.0] * len(rows), tf=tf, symbol=symbol,
    )


def demand_rows(
    *,
    consolidation=(104.4, 103.6, 104.4, 103.6),
    away_bars: int = 5,
    retest: tuple[float, float] | None = None,
    second_retest: tuple[float, float] | None = None,
):
    """Up-impulse → horizontal consolidation → up breakout: a CF-10 **continuation demand** zone.

    * bars 0-24  — flat warm-up, true range 1.0, so ``ATR(14) == 1.0``;
    * bars 25-28 — the impulse, +1.0 a bar (the P2 directional change);
    * the consolidation — closes given by ``consolidation``, drawn **without wicks** so the P5
      box is exactly the bodies;
    * one breakout bar closing at 105.0, then ``away_bars`` bars of +1.0 (the P10 move away);
    * optionally a walk back down to the zone ending in a ``(low, close)`` retest bar.
    """
    rows = [(100.0, 100.5, 99.5, 100.0) for _ in range(25)]
    price = 100.0
    for _ in range(4):
        open_ = price
        price += 1.0
        rows.append((open_, price + 0.1, open_ - 0.1, price))
    for close in consolidation:
        open_ = price
        price = close
        rows.append((open_, max(open_, close), min(open_, close), close))
    open_, price = price, 105.0
    rows.append((open_, price + 0.1, open_ - 0.1, price))
    for _ in range(away_bars):
        open_ = price
        price += 1.0
        rows.append((open_, price + 0.1, open_ - 0.1, price))
    for probe in (retest, second_retest):
        if probe is None:
            continue
        while price > 105.0:                      # walk back down, stopping just above the box
            open_ = price
            price = max(105.0, price - 1.0)
            rows.append((open_, open_ + 0.1, price - 0.1, price))
        low, close = probe
        rows.append((price, max(price, close) + 0.05, low, close))
        price = close
        while price < 108.0:                      # leave the zone again before the next probe
            open_ = price
            price += 1.0
            rows.append((open_, price + 0.1, open_ - 0.1, price))
    return rows


def supply_rows(*, away_bars: int = 5):
    """The mirror of :func:`demand_rows`: down-impulse → consolidation → down breakout."""
    rows = [(100.0, 100.5, 99.5, 100.0) for _ in range(25)]
    price = 100.0
    for _ in range(4):
        open_ = price
        price -= 1.0
        rows.append((open_, open_ + 0.1, price - 0.1, price))
    for close in (95.6, 96.4, 95.6, 96.4):
        open_ = price
        price = close
        rows.append((open_, max(open_, close), min(open_, close), close))
    open_, price = price, 95.0
    rows.append((open_, open_ + 0.1, price - 0.1, price))
    for _ in range(away_bars):
        open_ = price
        price -= 1.0
        rows.append((open_, open_ + 0.1, price - 0.1, price))
    return rows


def reversal_rows():
    """Down-impulse → consolidation → **up** breakout: the textbook (CF-10 ``reversal``) demand."""
    rows = [(100.0, 100.5, 99.5, 100.0) for _ in range(25)]
    price = 100.0
    for _ in range(4):
        open_ = price
        price -= 1.0
        rows.append((open_, open_ + 0.1, price - 0.1, price))
    for close in (96.4, 95.6, 96.4, 95.6):
        open_ = price
        price = close
        rows.append((open_, max(open_, close), min(open_, close), close))
    open_, price = price, 97.0
    rows.append((open_, price + 0.1, open_ - 0.1, price))
    for _ in range(6):
        open_ = price
        price += 1.0
        rows.append((open_, price + 0.1, open_ - 0.1, price))
    return rows


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def syn():
    return synthetic(seed=7)


@pytest.fixture(scope="module")
def detector() -> SupplyDemandZoneDetector:
    return SupplyDemandZoneDetector()


def only_zone(series: Series, config: Config) -> Zone:
    zones = SupplyDemandZoneDetector().detect(series, config)
    assert len(zones) == 1, [(z.formation_start_index, z.formation_end_index) for z in zones]
    return zones[0]


def reasons_for(series: Series, config: Config) -> list[str]:
    _zones, rejections = SupplyDemandZoneDetector().detect_with_rejections(series, config)
    return [reason for rejection in rejections for reason in rejection.reasons]


# =========================================================================== protocol


class TestDetectorProtocol:
    def test_satisfies_the_interfaces_protocol(self, detector):
        assert isinstance(detector, Detector)
        assert detector.name == "supply_demand_zones"
        assert detector.stage == 7                      # SPEC.md §3.1 stage table
        assert detector.produces == ("zone",)
        assert "CF-10" in detector.source_ids and "CF-11" in detector.source_ids

    def test_every_emitted_object_carries_source_ids(self, syn, cfg, detector):
        zones = detector.detect(syn.series, cfg)
        assert zones
        for zone in zones:
            assert zone.source_ids
            assert all(isinstance(sid, str) and sid for sid in zone.source_ids)

    def test_ids_are_deterministic_and_collision_free(self, syn, cfg, detector):
        zones = detector.detect(syn.series, cfg)
        ids = [z.id for z in zones]
        assert len(ids) == len(set(ids))
        for zone in zones:
            assert zone.id.startswith(f"{syn.series.symbol}:{syn.series.tf.value}"
                                      f":supply_demand_zones:")
        assert ids == [z.id for z in detector.detect(syn.series, cfg)]

    def test_detect_is_pure_and_repeatable(self, cfg, detector):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        first = detector.detect(series, cfg)
        second = detector.detect(series, cfg)
        assert [(z.id, z.box_top, z.fill_pct, z.is_dead) for z in first] == \
               [(z.id, z.box_top, z.fill_pct, z.is_dead) for z in second]
        assert synthetic(seed=7).series.close.tolist() == synthetic(seed=7).series.close.tolist()

    def test_to_confluence_prices_the_zone_at_its_pmt_entry(self, syn, cfg, detector):
        zones = detector.detect(syn.series, cfg)
        objects = detector.to_confluence(zones, cfg)
        assert [o.obj_class for o in objects] == ["zone"] * len(zones)
        assert [o.price for o in objects] == [z.entry_price_pmt for z in zones]
        assert objects[0].source_ids == zones[0].source_ids
        assert objects[0].tf is syn.series.tf


# =========================================================================== synthetic fixture


class TestSyntheticZone:
    def test_finds_the_embedded_zone_and_nothing_else(self, syn, cfg, detector):
        zones = detector.detect(syn.series, cfg)
        assert len(zones) == 1
        zone = zones[0]
        assert zone.formation_start_index == syn.features.consolidation_start
        assert zone.formation_end_index == syn.features.consolidation_end
        assert zone.breakout_index == syn.features.breakout_index
        assert zone.side is ZoneSide.DEMAND
        assert zone.zone_class is ZoneClass.CONTINUATION

    def test_box_is_the_p5_box_and_the_midpoint_is_frozen(self, syn, cfg, detector):
        zone = detector.detect(syn.series, cfg)[0]
        box = P.zone_box(syn.series, cfg, syn.features.consolidation_start,
                         syn.features.consolidation_end)
        assert (zone.box_top, zone.box_bottom) == (box.top, box.bottom)
        assert zone.midpoint == box.midpoint == P.midpoint_of(box)

    def test_fill_matches_p6_measured_from_the_breakout(self, syn, cfg, detector):
        zone = detector.detect(syn.series, cfg)[0]
        box = Box(zone.box_top, zone.box_bottom, zone.formation_start_index,
                  zone.formation_end_index)
        fill = P.measure_fill(syn.series, cfg, box, ZoneSide.DEMAND,
                              from_index=zone.breakout_index)
        assert zone.fill_pct == fill.fill_pct
        assert zone.is_dead is fill.is_dead is False        # the retest fills ~20 %

    def test_gap_matches_p10_on_the_series_own_timeframe(self, syn, cfg, detector):
        zone = detector.detect(syn.series, cfg)[0]
        gap = P.sufficient_gap(syn.series, cfg, syn.features.breakout_index, Direction.LONG,
                               tf=syn.series.tf)
        assert gap.valid
        assert (zone.move_away_pct, zone.move_away_atr) == (gap.gap_pct, gap.gap_atr)

    def test_entry_price_sits_inside_the_box(self, syn, cfg, detector):
        zone = detector.detect(syn.series, cfg)[0]
        assert zone.entry_price_pmt is not None
        assert zone.box_bottom <= zone.entry_price_pmt <= zone.box_top

    def test_depth_is_inside_the_cf12_band(self, syn, cfg, detector):
        zone = detector.detect(syn.series, cfg)[0]
        assert min_size_atr(cfg) <= zone.depth_atr <= max_size_atr(cfg)


class TestNoLookahead:
    """INTERFACES.md §9.1 — a detector standing on bar ``i`` sees only ``series.head(i + 1)``."""

    def test_zone_does_not_exist_before_its_breakout(self, syn, cfg, detector):
        head = syn.series.head(syn.features.breakout_index + 1)
        assert detector.detect(head, cfg) == []

    def test_zone_appears_once_the_move_away_is_large_enough(self, syn, cfg, detector):
        first_seen = next(
            i for i in range(syn.features.breakout_index, len(syn.series))
            if detector.detect(syn.series.head(i + 1), cfg)
        )
        assert first_seen > syn.features.breakout_index
        zone = detector.detect(syn.series.head(first_seen + 1), cfg)[0]
        assert zone.formation_start_index == syn.features.consolidation_start
        assert zone.breakout_index == syn.features.breakout_index

    def test_a_growing_window_never_changes_the_frozen_midpoint(self, syn, cfg, detector):
        seen: set[Decimal] = set()
        for i in range(syn.features.breakout_index, len(syn.series)):
            for zone in detector.detect(syn.series.head(i + 1), cfg):
                seen.add(zone.midpoint)
        assert len(seen) == 1                            # CF-08 / S5-A11: frozen at creation


# =========================================================================== S5-R17 body count


class TestBodyCountAndHalfCandles:
    """S5-R17 — at least two **full** candle bodies; two halves make one full."""

    def test_full_half_outside_and_engulfing(self, cfg):
        # box is 100.0 .. 102.0; bar bodies chosen so each scoring branch fires exactly once.
        series = make_series([
            (100.5, 101.6, 100.4, 101.5),   # 0 both ends inside      -> 1.0
            (101.5, 103.1, 101.4, 103.0),   # 1 opens inside, closes out -> 0.5
            (98.0, 99.6, 97.9, 99.5),       # 2 wholly below the box  -> 0
            (99.5, 103.1, 99.4, 103.0),     # 3 engulfs the whole box -> 0
            (103.0, 103.1, 100.9, 101.0),   # 4 closes inside         -> 0.5
        ])
        box = Box(dec(102.0), dec(100.0), 0, 4)
        assert count_bodies(series, cfg, box, 0, 4) == Decimal("2.0")

    def test_two_halves_make_one_full_candle(self, cfg):
        series = make_series([
            (99.0, 100.6, 98.9, 100.5),     # closes inside  -> 0.5
            (100.5, 101.6, 100.4, 101.5),   # fully inside   -> 1.0
            (101.5, 103.1, 101.4, 103.0),   # opens inside   -> 0.5
        ])
        box = Box(dec(102.0), dec(100.0), 0, 2)
        assert count_bodies(series, cfg, box, 1, 1) == Decimal("2.0")

    def test_one_and_a_half_candles_is_not_valid(self, cfg):
        # A price gap puts the preceding body wholly outside the box, so the window scores
        # 1.0 + 0.5 = 1.5 and cannot clear min_zone_bodies = 2 (S5-R17, "1.5 is not valid").
        series = make_series([
            (97.0, 97.6, 96.9, 97.5),       # gapped away below the box -> 0
            (100.5, 101.6, 100.4, 101.5),   # fully inside              -> 1.0
            (101.5, 103.1, 101.4, 103.0),   # opens inside              -> 0.5
        ])
        box = Box(dec(102.0), dec(100.0), 1, 1)
        total = count_bodies(series, cfg, box, 1, 1)
        assert total == Decimal("1.5")
        assert total < dec(cfg.min_zone_bodies)

    def test_wicks_never_count(self, cfg):
        """CF-13 / S5-R17: only candle bodies count, however far the wick reaches."""
        series = make_series([
            (99.0, 101.9, 96.0, 99.2),      # a huge upper wick reaches into the box
        ])
        box = Box(dec(102.0), dec(100.0), 0, 0)
        assert count_bodies(series, cfg, box, 0, 0) == Decimal(0)

    def test_emitted_body_count_is_the_floor_of_the_half_count(self, cfg):
        series = make_series(demand_rows())
        zone = only_zone(series, cfg)
        box = Box(zone.box_top, zone.box_bottom, zone.formation_start_index,
                  zone.formation_end_index)
        total = count_bodies(series, cfg, box, zone.formation_start_index,
                             zone.formation_end_index)
        assert total == Decimal("5.0")          # half + four full + half
        assert zone.body_count == int(total) == 5

    def test_min_zone_bodies_rejects_a_short_consolidation(self, cfg):
        series = make_series(demand_rows())
        strict = cfg.with_overrides(min_zone_bodies=6)
        assert SupplyDemandZoneDetector().detect(series, strict) == []
        assert any("min_zone_bodies" in reason for reason in reasons_for(series, strict))

    def test_default_two_body_minimum_lets_the_zone_through(self, cfg):
        series = make_series(demand_rows())
        assert cfg.min_zone_bodies == 2                  # S5-R17, the only hard number
        assert only_zone(series, cfg).body_count >= cfg.min_zone_bodies


# =========================================================================== CF-11 gap


class TestSufficientGap:
    """CF-11 / S5-R16 — the per-timeframe table plus the ATR multiple; **both** must pass."""

    def test_the_shipped_table_matches_the_spec_rows(self, cfg):
        """Q13 — his rows are 15m/30m/1H/1D/2D; the rest are interpolated **[OUR CHOICE]**.

        The 30m row was **3.5 and wrong**: SPEC §5.5 and CF-11 both cite S5-R16 for it, but
        S5-R16's own params say "30m: 4% sufficient" and S5 ``[00:54:07]`` says *"sufficient gap
        30 minutes 4%. That's sufficient enough."*  3.5 came from smoothing the ladder into a
        rising staircase; 4.0 is what he said, and it makes the <=1H rows read the way he speaks —
        a flat 3-5% band with 4% as the operating point.
        """
        table = cfg.sufficient_gap_pct_by_tf
        his = {"15m": 3.0, "30m": 4.0, "1H": 4.0, "1D": 8.0, "2D": 13.0}
        assert {tf: table[tf] for tf in his} == his
        ours = {"2H": 5.0, "4H": 6.0, "8H": 7.0, "12H": 7.5, "3D": 15.0, "1W": 15.0}
        assert {tf: table[tf] for tf in ours} == ours     # interpolated, [OUR CHOICE]

    def test_same_bars_pass_on_1h_and_fail_on_2h(self, cfg):
        """A 4.857 % move away: above the 1H row (4.0), below the 2H row (5.0)."""
        rows = demand_rows()
        hourly = only_zone(make_series(rows, tf="1H"), cfg)
        assert hourly.move_away_pct > dec(cfg.sufficient_gap_pct_by_tf["1H"])
        assert hourly.move_away_pct < dec(cfg.sufficient_gap_pct_by_tf["2H"])

        two_hourly = make_series(rows, tf="2H")
        assert SupplyDemandZoneDetector().detect(two_hourly, cfg) == []
        assert any("required on 2H" in reason for reason in reasons_for(two_hourly, cfg))

    def test_the_rejection_wording_comes_from_p10(self, cfg):
        series = make_series(demand_rows(), tf="2H")
        gap = P.sufficient_gap(series, cfg, 33, Direction.LONG, tf=Timeframe.H2)
        assert not gap.valid
        assert set(gap.reasons).issubset(set(reasons_for(series, cfg)))

    def test_atr_multiple_is_the_second_gate(self, cfg):
        series = make_series(demand_rows())
        assert only_zone(series, cfg).move_away_atr >= dec(cfg.sufficient_gap_atr_mult)
        strict = cfg.with_overrides(sufficient_gap_atr_mult=25.0)
        assert SupplyDemandZoneDetector().detect(series, strict) == []
        assert any("sufficient_gap_atr_mult" in reason for reason in reasons_for(series, strict))

    def test_percentage_only_mode_drops_the_atr_test(self, cfg):
        series = make_series(demand_rows())
        loose = cfg.with_overrides(sufficient_gap_atr_mult=25.0,
                                   sufficient_gap_require_both_tests=False)
        assert len(SupplyDemandZoneDetector().detect(series, loose)) == 1

    def test_a_short_move_away_is_rejected(self, cfg):
        series = make_series(demand_rows(away_bars=2))
        assert SupplyDemandZoneDetector().detect(series, cfg) == []
        assert any("required on 1H" in reason for reason in reasons_for(series, cfg))


# =========================================================================== CF-08 fill


class TestFiftyPercentFillInvalidation:
    """CF-08 / S5-R28 / S6-R10 — 50 % of depth, on the zone as originally drawn."""

    def test_wick_through_the_midpoint_kills_the_zone(self, cfg):
        # box = (103.6, 104.4), midpoint 104.0: a low of 103.9 is 62.5 % of the depth.
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        zone = only_zone(series, cfg)
        assert cfg.zone_fill_measure == "wick_touch"
        assert zone.midpoint == dec(104.0)
        assert float(zone.fill_pct) == pytest.approx(62.5)
        assert zone.is_dead is True

    def test_the_same_bar_leaves_it_alive_under_close_beyond(self, cfg):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        closes = cfg.with_overrides(zone_fill_measure="close_beyond")
        zone = only_zone(series, closes)
        assert float(zone.fill_pct) == pytest.approx(25.0)   # 104.4 -> 104.2 of a 0.8 depth
        assert zone.is_dead is False
        assert zone.midpoint == dec(104.0)                # frozen either way

    def test_threshold_is_the_config_key_not_a_constant(self, cfg):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        assert only_zone(series, cfg).is_dead is True
        lenient = cfg.with_overrides(zone_fill_invalidation_pct=70.0)
        assert only_zone(series, lenient).is_dead is False
        assert fill_invalidation_pct(lenient) == dec(70.0)

    def test_a_shallow_retest_leaves_the_zone_replayable(self, cfg):
        series = make_series(demand_rows(retest=(104.3, 104.35)))
        zone = only_zone(series, cfg)
        assert zone.is_dead is False
        assert zone.fill_pct < dec(cfg.zone_fill_invalidation_pct)
        assert zone.touch_count >= 1                       # S5-R28: re-takeable while alive
        assert "S5-R28" in zone.source_ids and "S6-R25" in zone.source_ids

    def test_replay_counts_each_return_while_the_zone_lives(self, cfg):
        one = only_zone(make_series(demand_rows(retest=(104.3, 104.35))), cfg)
        two = only_zone(
            make_series(demand_rows(retest=(104.3, 104.35), second_retest=(104.3, 104.35))), cfg)
        assert two.touch_count == one.touch_count + 1
        assert two.is_dead is False

    def test_touches_stop_being_counted_once_the_zone_is_dead(self, cfg):
        alive = only_zone(make_series(demand_rows(retest=(104.3, 104.35),
                                                  second_retest=(104.3, 104.35))), cfg)
        dead = only_zone(make_series(demand_rows(retest=(103.9, 104.2),
                                                 second_retest=(104.3, 104.35))), cfg)
        assert alive.touch_count == 2
        assert dead.is_dead is True
        assert dead.touch_count == 1                       # the post-mortem return is not a replay

    def test_death_index_is_the_first_bar_past_the_threshold(self, cfg):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        zone = only_zone(series, cfg)
        box = Box(zone.box_top, zone.box_bottom, zone.formation_start_index,
                  zone.formation_end_index)
        died = death_index(series, cfg, box, ZoneSide.DEMAND, from_index=zone.breakout_index)
        assert died is not None
        assert not P.measure_fill(series, cfg, box, ZoneSide.DEMAND,
                                  from_index=zone.breakout_index, to_index=died - 1).is_dead
        assert P.measure_fill(series, cfg, box, ZoneSide.DEMAND,
                              from_index=zone.breakout_index, to_index=died).is_dead

    def test_a_dead_zone_scores_no_confluence(self, cfg, detector):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        zones = detector.detect(series, cfg)
        assert zones[0].is_dead is True
        assert detector.to_confluence(zones, cfg) == []

    def test_dead_zone_records_the_cf08_rule_ids(self, cfg):
        zone = only_zone(make_series(demand_rows(retest=(103.9, 104.2))), cfg)
        assert {"CF-08", "S5-R28", "S6-R10"} <= set(zone.source_ids)


class TestTouchWindows:
    def test_consecutive_in_zone_bars_are_one_touch(self, cfg):
        series = make_series([
            (100.0, 100.5, 99.5, 100.0),   # 0  outside (below the box)
            (100.0, 103.0, 100.0, 102.5),  # 1  in the box
            (102.5, 103.0, 102.0, 102.5),  # 2  in the box, same touch
            (102.5, 105.5, 102.5, 105.0),  # 3  in the box on the way out
            (105.0, 106.0, 105.0, 105.5),  # 4  outside (above)
            (105.5, 106.0, 102.5, 103.0),  # 5  back in the box: a second touch
        ])
        box = Box(dec(104.0), dec(102.0), 1, 2)
        assert zone_touch_windows(series, box, from_index=0) == ((1, 3), (5, 5))


# =========================================================================== CF-12 depth


class TestDepthBand:
    """CF-12 — depth in ``[min_zone_depth_atr, max_zone_depth_atr]``; **the ATR normalisation
    is ours**, his figures are raw dollars (S6-R48, S8-R23)."""

    def test_accessors_expose_the_owned_keys(self, cfg):
        assert min_size_atr(cfg) == dec(cfg.min_zone_depth_atr) == dec(0.5)
        assert max_size_atr(cfg) == dec(cfg.max_zone_depth_atr) == dec(3.0)

    def test_too_shallow_is_rejected(self, cfg):
        series = make_series(demand_rows())
        strict = cfg.with_overrides(min_zone_depth_atr=2.0)
        assert SupplyDemandZoneDetector().detect(series, strict) == []
        assert any("min_zone_depth_atr" in reason for reason in reasons_for(series, strict))

    def test_too_wide_is_rejected(self, cfg):
        series = make_series(demand_rows())
        strict = cfg.with_overrides(min_zone_depth_atr=0.1, max_zone_depth_atr=0.2)
        assert SupplyDemandZoneDetector().detect(series, strict) == []
        assert any("max_zone_depth_atr" in reason for reason in reasons_for(series, strict))


class TestZoneWithinZone:
    """CF-12 / S5-R30 — the larger consolidation wins, subject to ``max_zone_depth_atr``."""

    @staticmethod
    def _candidate(start, end, bottom, top):
        return Z._Candidate(
            formation_start=start,
            formation_end=end,
            breakout_index=end + 1,
            side=ZoneSide.DEMAND,
            zone_class=ZoneClass.CONTINUATION,
            box=Box(dec(top), dec(bottom), start, end),
            impulse_index=start - 1,
            impulse_move_atr=dec(3),
        )

    def test_nesting_and_larger_are_pure_geometry(self):
        outer = self._candidate(10, 20, 100.0, 110.0)
        inner = self._candidate(14, 18, 102.0, 108.0)
        apart = self._candidate(40, 44, 102.0, 108.0)
        assert Z._nested(outer, inner) and Z._nested(inner, outer)
        assert not Z._nested(outer, apart)
        assert Z._is_larger(outer, inner) and not Z._is_larger(inner, outer)

    def test_larger_wins_when_it_still_fits_the_depth_cap(self, cfg):
        detector = SupplyDemandZoneDetector()
        outer = (self._candidate(10, 20, 100.0, 110.0), None, dec(2.0), dec(9))
        inner = (self._candidate(14, 18, 102.0, 108.0), None, dec(1.0), dec(5))
        kept, dropped = detector._resolve_nesting([outer, inner], cfg)
        assert [k[0].formation_start for k in kept] == [10]
        assert dropped and "zone within zone" in dropped[0].reasons[0]

    def test_inner_wins_when_the_larger_is_too_wide(self, cfg):
        detector = SupplyDemandZoneDetector()
        outer = (self._candidate(10, 20, 100.0, 110.0), None, dec(4.0), dec(9))
        inner = (self._candidate(14, 18, 102.0, 108.0), None, dec(1.0), dec(5))
        kept, dropped = detector._resolve_nesting([outer, inner], cfg)
        assert [k[0].formation_start for k in kept] == [14]
        assert any("max_zone_depth_atr" in r for rej in dropped for r in rej.reasons)

    def test_always_larger_keeps_the_over_wide_outer_zone(self, cfg):
        detector = SupplyDemandZoneDetector()
        literal = cfg.with_overrides(zone_within_zone_policy="always_larger")
        outer = (self._candidate(10, 20, 100.0, 110.0), None, dec(4.0), dec(9))
        inner = (self._candidate(14, 18, 102.0, 108.0), None, dec(1.0), dec(5))
        kept, _dropped = detector._resolve_nesting([outer, inner], literal)
        assert [k[0].formation_start for k in kept] == [10]


# =========================================================================== CF-10 classes


class TestZoneClasses:
    def test_supply_continuation_is_down_consolidate_down(self, cfg):
        zone = only_zone(make_series(supply_rows()), cfg)
        assert zone.side is ZoneSide.SUPPLY
        assert zone.zone_class is ZoneClass.CONTINUATION
        assert "S6-R4" in zone.source_ids           # not the S6-C1 misspeak
        assert zone.outer_edge == zone.box_bottom

    def test_demand_continuation_is_up_consolidate_up(self, cfg):
        zone = only_zone(make_series(demand_rows()), cfg)
        assert zone.side is ZoneSide.DEMAND
        assert zone.zone_class is ZoneClass.CONTINUATION
        assert {"CF-10", "S5-R15", "S6-R5"} <= set(zone.source_ids)
        assert zone.outer_edge == zone.box_top

    def test_textbook_reversal_is_labelled_not_discarded(self, cfg):
        zone = only_zone(make_series(reversal_rows()), cfg)
        assert zone.side is ZoneSide.DEMAND
        assert zone.zone_class is ZoneClass.REVERSAL

    def test_zone_direction_mode_filters_by_class(self, cfg):
        continuation = make_series(demand_rows())
        reversal = make_series(reversal_rows())
        only_cont = cfg.with_overrides(zone_direction_mode="continuation_only")
        only_rev = cfg.with_overrides(zone_direction_mode="reversal_only")
        assert len(SupplyDemandZoneDetector().detect(continuation, only_cont)) == 1
        assert SupplyDemandZoneDetector().detect(reversal, only_cont) == []
        assert len(SupplyDemandZoneDetector().detect(reversal, only_rev)) == 1
        assert SupplyDemandZoneDetector().detect(continuation, only_rev) == []


# =========================================================================== CF-08 rescue


class TestDeadZoneRescue:
    @staticmethod
    def _level(price: float, touches: int, tf: str = "1H", ident: str = "lvl") -> Level:
        return Level(
            id=ident, symbol="T", tf=Timeframe.parse(tf), price=dec(price),
            kind=LevelKind.SUPPORT, created_index=0, touch_count=touches,
            flip_state=FlipState.NONE, source_ids=("S4-R4",),
        )

    def _dead(self, cfg):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        zone = only_zone(series, cfg)
        assert zone.is_dead is True
        return series, zone

    def test_level_in_the_remaining_half_rearms_the_zone(self, cfg):
        series, zone = self._dead(cfg)
        level = self._level(103.8, touches=2)       # between box_bottom 103.6 and midpoint 104.0
        rescue_dead_zones([zone], [level], cfg, series)
        assert zone.rescued_by_level_id == "lvl"
        assert {"CF-08", "S7-R4"} <= set(zone.source_ids)

    def test_too_many_touches_is_not_a_rescue(self, cfg):
        series, zone = self._dead(cfg)
        level = self._level(103.8, touches=cfg.dead_zone_rescue_max_touches + 1)
        rescue_dead_zones([zone], [level], cfg, series)
        assert zone.rescued_by_level_id is None

    def test_a_level_outside_the_remaining_half_is_not_a_rescue(self, cfg):
        series, zone = self._dead(cfg)
        level = self._level(104.3, touches=1)       # above the midpoint: the filled half
        rescue_dead_zones([zone], [level], cfg, series)
        assert zone.rescued_by_level_id is None

    def test_a_lower_timeframe_level_is_not_a_rescue(self, cfg):
        series, zone = self._dead(cfg)
        level = self._level(103.8, touches=1, tf="15m")
        rescue_dead_zones([zone], [level], cfg, series)
        assert zone.rescued_by_level_id is None

    def test_the_switch_turns_the_clause_off(self, cfg):
        series, zone = self._dead(cfg)
        level = self._level(103.8, touches=2)
        rescue_dead_zones([zone], [level], cfg.with_overrides(dead_zone_htf_support_rescue=False),
                          series)
        assert zone.rescued_by_level_id is None

    def test_the_detector_applies_the_clause_when_levels_are_supplied(self, cfg):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        level = self._level(103.8, touches=2)
        zones = SupplyDemandZoneDetector(levels=[level]).detect(series, cfg)
        assert zones[0].is_dead is True
        assert zones[0].rescued_by_level_id == "lvl"

    def test_a_rescued_zone_scores_again(self, cfg, detector):
        series = make_series(demand_rows(retest=(103.9, 104.2)))
        level = self._level(103.8, touches=2)
        rescued = SupplyDemandZoneDetector(levels=[level])
        zones = rescued.detect(series, cfg)
        assert len(rescued.to_confluence(zones, cfg)) == 1

    def test_ties_break_on_touch_count_then_distance_then_id(self, cfg):
        series, zone = self._dead(cfg)
        far = self._level(103.95, touches=1, ident="far")
        near = self._level(103.65, touches=1, ident="near")
        rescue_dead_zones([zone], [far, near], cfg, series)
        assert zone.rescued_by_level_id == "near"       # nearest the far edge (box_bottom)


# =========================================================================== strength


class TestZoneStrength:
    """S5-R18 / S6-R6 / S6-R7 / S6-R8 — proportional to bodies, timeframe and the move away."""

    @staticmethod
    def _zone(*, bodies=4, tf=Timeframe.H1, move_atr=4.0) -> Zone:
        return Zone(
            id="z", symbol="T", tf=tf, side=ZoneSide.DEMAND, zone_class=ZoneClass.CONTINUATION,
            box_top=dec(104.4), box_bottom=dec(103.6), midpoint=dec(104.0), body_count=bodies,
            formation_start_index=29, formation_end_index=32, breakout_index=33,
            move_away_pct=dec(5.0), move_away_atr=dec(move_atr), depth_atr=dec(0.8),
        )

    def test_rises_with_the_consolidation_candle_count(self, cfg):
        assert zone_strength(self._zone(bodies=8), cfg) > zone_strength(self._zone(bodies=4), cfg)

    def test_rises_with_the_timeframe(self, cfg):
        assert zone_strength(self._zone(tf=Timeframe.D1), cfg) > \
               zone_strength(self._zone(tf=Timeframe.H1), cfg)

    def test_rises_with_the_size_of_the_move_away(self, cfg):
        assert zone_strength(self._zone(move_atr=9.0), cfg) > \
               zone_strength(self._zone(move_atr=3.0), cfg)

    def test_a_barely_valid_zone_scores_about_one(self, cfg):
        barely = self._zone(bodies=cfg.min_zone_bodies, tf=Timeframe.H1,
                            move_atr=cfg.sufficient_gap_atr_mult)
        assert zone_strength(barely, cfg) == Decimal(1)


# =========================================================================== edge cases


class TestEdgeCases:
    def test_empty_and_tiny_series_produce_nothing(self, cfg, detector):
        assert detector.detect(make_series([(1.0, 1.0, 1.0, 1.0)]), cfg) == []
        assert detector.detect(make_series([(1.0, 1.5, 0.5, 1.0)] * 2), cfg) == []

    def test_flat_series_produces_nothing(self, cfg, detector):
        assert detector.detect(make_series([(100.0, 100.5, 99.5, 100.0)] * 60), cfg) == []

    def test_rejections_carry_the_candidate_window(self, cfg):
        series = make_series(demand_rows(), tf="2H")
        _zones, rejections = SupplyDemandZoneDetector().detect_with_rejections(series, cfg)
        assert rejections
        assert all(isinstance(r, ZoneRejection) for r in rejections)
        assert all(r.formation_start_index <= r.formation_end_index < r.breakout_index
                   for r in rejections)

    def test_zones_are_ordered_newest_last(self, cfg, detector):
        series = make_series(demand_rows(retest=(104.3, 104.35)))
        zones = detector.detect(series, cfg)
        assert [z.breakout_index for z in zones] == sorted(z.breakout_index for z in zones)


# =========================================================================== F1 wick band


def with_lower_wick(low: float, *, bar: int = 32):
    """:func:`demand_rows` with a lower wick hung off one consolidation bar.

    The consolidation is bars 29–32 and its bodies span ``(103.6, 104.4)``, so the P5 body box is
    ``0.8`` deep against an ``ATR(14)`` of exactly ``1.0``.  Dropping the *low* of bar ``bar``
    leaves the bodies — and therefore the box, the body count and every gap measurement — alone,
    which is what makes this fixture able to isolate the F1 band.
    """
    rows = demand_rows()
    open_, high, _low, close = rows[bar]
    rows[bar] = (open_, high, low, close)
    return rows


def with_upper_wick(high: float, *, bar: int = 32):
    """The supply mirror of :func:`with_lower_wick`: bodies span ``(95.6, 96.4)``."""
    rows = supply_rows()
    open_, _high, low, close = rows[bar]
    rows[bar] = (open_, high, low, close)
    return rows


def zone_fields(zone: Zone) -> dict:
    """Every field of a zone **except** the F1 band and the source-id list."""
    return {
        name: getattr(zone, name)
        for name in (
            "id", "symbol", "tf", "side", "zone_class", "box_top", "box_bottom", "midpoint",
            "body_count", "formation_start_index", "formation_end_index", "breakout_index",
            "move_away_pct", "move_away_atr", "depth_atr", "fill_pct", "is_dead",
            "rescued_by_level_id", "touch_count", "contained_ob_ids", "entry_price_pmt",
        )
    }


@pytest.fixture(scope="module")
def cfg_band(cfg) -> Config:
    return cfg.with_overrides(zone_wick_band_enabled=True)


class TestWickBandOffByDefault:
    """F1 ships **off**.  With the flag down nothing about a zone may differ from before."""

    def test_the_flag_and_its_ratio_carry_the_documented_defaults(self, cfg):
        assert cfg.zone_wick_band_enabled is False
        assert cfg.zone_wick_band_max_ratio == 1.0

    @pytest.mark.parametrize("rows", [
        demand_rows(),
        with_lower_wick(103.0),
        with_lower_wick(102.5),
        supply_rows(),
        with_upper_wick(97.0),
        reversal_rows(),
        demand_rows(retest=(104.3, 104.35)),
    ])
    def test_no_zone_carries_a_band(self, rows, cfg, detector):
        for zone in detector.detect(make_series(rows), cfg):
            assert zone.wick_band_top is None and zone.wick_band_bottom is None
            assert zone.has_wick_band is False
            assert zone.wick_band_stop_edge is None
            assert zone.wick_band_depth == Decimal(0)
            assert "F1" not in zone.source_ids

    def test_the_helper_itself_returns_none_while_the_flag_is_down(self, cfg):
        series = make_series(with_lower_wick(103.0))
        box = P.zone_box(series, cfg, 29, 32)
        assert Z.wick_band(series, cfg, box, ZoneSide.DEMAND, 29, 32) is None

    @pytest.mark.parametrize("rows", [
        demand_rows(),
        with_lower_wick(103.0),
        with_lower_wick(102.5),
        supply_rows(),
        with_upper_wick(97.0),
        reversal_rows(),
        demand_rows(retest=(104.3, 104.35)),
    ])
    def test_switching_the_flag_on_changes_the_band_and_nothing_else(
        self, rows, cfg, cfg_band, detector
    ):
        """The flag is additive: turning it on may only *add* the band and the ``F1`` id.

        Run the other way round this is the off-by-default equivalence proof — every field the
        rest of the bot reads (box, midpoint, depth, fill, death, touch count and the P20 entry
        price) is bit-for-bit the same whichever way the flag is set.
        """
        series = make_series(rows)
        off = detector.detect(series, cfg)
        on = detector.detect(series, cfg_band)
        assert len(off) == len(on)
        for a, b in zip(off, on):
            assert zone_fields(a) == zone_fields(b)
            assert [i for i in b.source_ids if i != "F1"] == list(a.source_ids)

    def test_a_synthetic_run_is_identical_with_the_flag_down(self, syn, cfg, detector):
        expected = [zone_fields(z) for z in detector.detect(syn.series, cfg)]
        again = [zone_fields(z) for z in detector.detect(syn.series, cfg.with_overrides(
            zone_wick_band_enabled=False))]
        assert expected == again


class TestWickBandGeometry:
    """F1, S6 frame 52:38 — inner box on the bodies, outer band out to the wick extreme."""

    def test_demand_band_shares_the_near_edge_and_extends_to_the_wick_low(self, cfg_band):
        zone = only_zone(make_series(with_lower_wick(103.0)), cfg_band)
        assert (zone.box_top, zone.box_bottom) == (dec(104.4), dec(103.6))   # body core, as before
        assert zone.wick_band_top == zone.box_top                            # same top edge
        assert zone.wick_band_bottom == dec(103.0)                           # out to the wick low
        assert zone.has_wick_band and "F1" in zone.source_ids

    def test_the_stop_edge_is_the_far_edge_and_the_entry_edge_stays_on_the_core(self, cfg_band):
        zone = only_zone(make_series(with_lower_wick(103.0)), cfg_band)
        assert zone.wick_band_stop_edge == dec(103.0)
        assert zone.outer_edge == zone.box_top == dec(104.4)   # entries still price off the body
        assert zone.wick_band_depth == dec("0.6")

    def test_the_measured_frame_ratio_is_admitted_by_the_default_cap(self, cfg_band):
        """S6 52:38 measured the band at ~83 % of the body box; here it is 0.6 / 0.8 = 75 %."""
        zone = only_zone(make_series(with_lower_wick(103.0)), cfg_band)
        ratio = zone.wick_band_depth / zone.depth
        assert Decimal("0.5") < ratio < dec(cfg_band.zone_wick_band_max_ratio)

    def test_supply_band_extends_up_to_the_wick_high(self, cfg_band):
        zone = only_zone(make_series(with_upper_wick(97.0)), cfg_band)
        assert zone.side is ZoneSide.SUPPLY
        assert (zone.box_top, zone.box_bottom) == (dec(96.4), dec(95.6))
        assert zone.wick_band_top == dec(97.0)
        assert zone.wick_band_bottom == zone.box_bottom
        assert zone.wick_band_stop_edge == dec(97.0)
        assert zone.outer_edge == zone.box_bottom                # entries off the body core

    def test_a_wick_longer_than_the_body_box_is_an_outlier_and_excluded(self, cfg_band):
        """Extension 1.1 against a 0.8 body box is 137 % — beyond the 100 % cap, so dropped."""
        zone = only_zone(make_series(with_lower_wick(102.5)), cfg_band)
        assert zone.wick_band_bottom == zone.box_bottom == dec(103.6)
        assert zone.wick_band_depth == Decimal(0)

    def test_raising_the_ratio_admits_the_outlier(self, cfg_band):
        loose = cfg_band.with_overrides(zone_wick_band_max_ratio=1.5)
        zone = only_zone(make_series(with_lower_wick(102.5)), loose)
        assert zone.wick_band_bottom == dec(102.5)

    def test_a_wick_small_enough_for_p5_is_already_in_the_box_so_the_band_adds_nothing(
        self, cfg_band
    ):
        """CF-13 folds a <=0.5-ATR wick into the box itself; F1 then has nothing left to add."""
        zone = only_zone(make_series(with_lower_wick(103.2)), cfg_band)
        assert zone.box_bottom == dec(103.2)                     # P5 already absorbed it
        assert zone.wick_band_bottom == zone.box_bottom
        assert zone.wick_band_depth == Decimal(0)

    def test_a_consolidation_with_no_wick_at_all_produces_a_degenerate_band(self, cfg_band):
        zone = only_zone(make_series(demand_rows()), cfg_band)
        assert zone.wick_band_top == zone.box_top
        assert zone.wick_band_bottom == zone.box_bottom
