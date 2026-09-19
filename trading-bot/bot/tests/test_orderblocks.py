"""Contract tests for tbot.detectors.orderblocks (SPEC.md §5.6, CF-09 / CF-08 / CF-12 / CF-13).

Hand-built series put the answer in plain sight: 25 flat warm-up bars give ``ATR(14) == 1.0``, so
``wick_include_max_atr = 0.5`` is a literal 0.5-price-unit boundary and
``min_zone_depth_atr = 0.5`` is a literal 0.5-price-unit minimum body.  The
:func:`tbot.data.synthetic` fixture supplies the cross-check: its ``order_block_index`` names the
last red candle before the embedded impulse, and its demand zone is the CF-09 nesting case.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config
from tbot.data import synthetic
from tbot.models import (
    Direction,
    OBSide,
    Series,
    Timeframe,
    ZoneSide,
    dec,
)
import tbot.primitives as P
from tbot.detectors.base import Detector
from tbot.detectors.orderblocks import (
    OrderBlockDetector,
    OrderBlockRejection,
    S7_LIQUIDITY_THRESHOLD_PCT,
    ob_invalidation_pct,
    link_to_zones,
    ob_zone_side,
)
from tbot.detectors.zones import SupplyDemandZoneDetector, fill_invalidation_pct, min_size_atr

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- helpers

def make_series(rows, tf: str = "1H", symbol: str = "T") -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1_000.0] * len(rows), tf=tf, symbol=symbol,
    )


def warmup(n: int = 25):
    """Flat bars with a true range of 1.0, so ``ATR(14) == 1.0`` before anything happens."""
    return [(100.0, 100.5, 99.5, 100.0) for _ in range(n)]


def bullish_rows(*, body: float = 1.0, upper_wick: float = 0.4, reds: int = 1,
                 rally: int = 6, retrace_to: float | None = None):
    """``reds`` red candles, then a rally: the **last** red one is the bullish order block.

    The block candle opens at 100.0 and closes ``body`` lower, carrying ``upper_wick`` above its
    open — the CF-13 wick test is what decides whether the box keeps it.
    """
    rows = warmup()
    price = 100.0
    for i in range(reds):
        open_ = price
        price = open_ - body
        wick = upper_wick if i == reds - 1 else 0.05
        rows.append((open_, open_ + wick, price - 0.1, price))
    for _ in range(rally):
        open_ = price
        price += 1.0
        rows.append((open_, price + 0.1, open_ - 0.1, price))
    if retrace_to is not None:
        while price > retrace_to:
            open_ = price
            price = max(retrace_to, price - 1.0)
            rows.append((open_, open_ + 0.1, price - 0.1, price))
    return rows


def bearish_rows(*, rally: int = 6):
    """A green candle followed by a fall: the **last green** candle is the bearish OB (S6-R1)."""
    rows = warmup()
    price = 100.0
    open_ = price
    price = open_ + 1.0
    rows.append((open_, price + 0.1, open_ - 0.4, price))
    for _ in range(rally):
        open_ = price
        price -= 1.0
        rows.append((open_, open_ + 0.1, price - 0.1, price))
    return rows


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def syn():
    return synthetic(seed=7)


@pytest.fixture(scope="module")
def detector() -> OrderBlockDetector:
    return OrderBlockDetector()


def only_block(series: Series, config: Config):
    blocks = OrderBlockDetector().detect(series, config)
    assert len(blocks) == 1, [(b.bar_index, b.side.value) for b in blocks]
    return blocks[0]


def block_at(series: Series, config: Config, bar_index: int = 25):
    """The single block on ``bar_index``.

    A series that rallies and then retraces contains a second, **bearish** block at the top of
    the rally — which is correct (S6-R1) but not what the fill tests are about.
    """
    found = [b for b in OrderBlockDetector().detect(series, config) if b.bar_index == bar_index]
    assert len(found) == 1, [(b.bar_index, b.side.value)
                             for b in OrderBlockDetector().detect(series, config)]
    return found[0]


# =========================================================================== protocol


class TestDetectorProtocol:
    def test_satisfies_the_interfaces_protocol(self, detector):
        assert isinstance(detector, Detector)
        assert detector.name == "order_blocks"
        assert detector.stage == 8                       # SPEC.md §3.1 stage table
        assert detector.produces == ("order_block",)
        assert "CF-09" in detector.source_ids

    def test_every_emitted_object_carries_source_ids(self, syn, cfg, detector):
        blocks = detector.detect(syn.series, cfg)
        assert blocks
        for block in blocks:
            assert block.source_ids
            assert "CF-09" in block.source_ids and "S6-R3" in block.source_ids

    def test_ids_are_deterministic_and_collision_free(self, syn, cfg, detector):
        blocks = detector.detect(syn.series, cfg)
        ids = [b.id for b in blocks]
        assert len(ids) == len(set(ids))
        assert all(b.id.startswith(f"{syn.series.symbol}:{syn.series.tf.value}:order_blocks:")
                   for b in blocks)
        assert ids == [b.id for b in detector.detect(syn.series, cfg)]

    def test_detect_is_pure_and_repeatable(self, cfg, detector):
        series = make_series(bullish_rows())
        first = detector.detect(series, cfg)
        second = detector.detect(series, cfg)
        assert [(b.id, b.box_top, b.fill_pct, b.is_dead) for b in first] == \
               [(b.id, b.box_top, b.fill_pct, b.is_dead) for b in second]

    def test_blocks_are_ordered_newest_last(self, syn, cfg, detector):
        blocks = detector.detect(syn.series, cfg)
        completions = [int(b.id.split(":")[3]) for b in blocks]
        assert completions == sorted(completions)

    def test_to_confluence_prices_the_block_at_its_midpoint(self, cfg, detector):
        series = make_series(bullish_rows())
        blocks = detector.detect(series, cfg)
        objects = detector.to_confluence(blocks, cfg)
        assert [o.obj_class for o in objects] == ["order_block"]
        assert objects[0].price == blocks[0].midpoint
        assert objects[0].source_ids == blocks[0].source_ids


# =========================================================================== S6-R1 / S6-R2


class TestColourMapping:
    """S6-R1 / S6-R2, CF-09 — bullish = last **red**, bearish = last **green**.  S7-C4 discarded."""

    def test_bullish_block_is_the_last_red_candle_before_an_up_move(self, cfg):
        series = make_series(bullish_rows())
        block = only_block(series, cfg)
        assert block.side is OBSide.BULLISH
        assert block.bar_index == 25
        assert bool(series.is_green[block.bar_index]) is False       # a red candle
        assert bool(series.is_green[block.bar_index + 1]) is True    # the move starts next bar

    def test_bearish_block_is_the_last_green_candle_before_a_down_move(self, cfg):
        series = make_series(bearish_rows())
        block = only_block(series, cfg)
        assert block.side is OBSide.BEARISH
        assert block.bar_index == 25
        assert bool(series.is_green[block.bar_index]) is True
        assert bool(series.is_green[block.bar_index + 1]) is False

    def test_only_the_last_of_a_run_of_red_candles_qualifies(self, cfg):
        series = make_series(bullish_rows(reds=3))
        block = only_block(series, cfg)
        assert block.bar_index == 27                       # not 25 or 26
        assert bool(series.is_green[26]) is False          # they were red too

    def test_every_emitted_block_obeys_the_colour_rule(self, syn, cfg, detector):
        series = syn.series
        for block in detector.detect(series, cfg):
            is_green = bool(series.is_green[block.bar_index])
            assert is_green is (block.side is OBSide.BEARISH)

    def test_side_maps_to_the_zone_side_the_primitives_speak(self):
        assert ob_zone_side(OBSide.BULLISH) is ZoneSide.DEMAND
        assert ob_zone_side(OBSide.BEARISH) is ZoneSide.SUPPLY

    def test_the_directional_change_is_p2(self, cfg):
        series = make_series(bullish_rows())
        block = only_block(series, cfg)
        change = P.directional_change(series, cfg, block.dir_change_index)
        assert change is not None
        assert change.direction is Direction.LONG
        assert change.order_block_index == block.bar_index
        assert block.dir_change_atr_move == change.move_atr
        assert block.dir_change_atr_move >= dec(cfg.dir_change_atr)


class TestSyntheticOrderBlock:
    def test_finds_the_embedded_order_block(self, syn, cfg, detector):
        blocks = detector.detect(syn.series, cfg)
        found = [b for b in blocks if b.bar_index == syn.features.order_block_index]
        assert len(found) == 1
        assert found[0].side is OBSide.BULLISH
        assert found[0].is_dead is False

    def test_no_lookahead_before_the_directional_change(self, syn, cfg, detector):
        """A block is unknowable until a move away has actually happened after it."""
        target = syn.features.order_block_index
        head = syn.series.head(target + 1)
        assert [b for b in detector.detect(head, cfg) if b.bar_index == target] == []

    def test_a_truncated_series_never_reaches_past_its_last_bar(self, syn, cfg, detector):
        for end in range(60, len(syn.series), 7):
            head = syn.series.head(end + 1)
            for block in detector.detect(head, cfg):
                assert block.bar_index <= end
                assert block.dir_change_index <= end


# =========================================================================== CF-13 box


class TestBoxAndCardinality:
    """CF-13 / S6-R3 / S6-R9 — exactly one candle, body-anchored, small wicks folded in."""

    def test_box_is_the_p5_single_candle_box(self, cfg):
        series = make_series(bullish_rows())
        block = only_block(series, cfg)
        box = P.order_block_box(series, cfg, block.bar_index)
        assert (block.box_top, block.box_bottom) == (box.top, box.bottom)
        assert cfg.ob_max_candles == 1                     # S6-R3, "never two"

    def test_a_small_wick_is_folded_into_the_box(self, cfg):
        series = make_series(bullish_rows(upper_wick=0.4))
        block = only_block(series, cfg)
        assert float(block.box_top) == pytest.approx(100.4)   # body top 100.0 plus the wick

    def test_a_giant_wick_is_left_out(self, cfg):
        series = make_series(bullish_rows(upper_wick=0.6))
        block = only_block(series, cfg)
        assert float(block.box_top) == pytest.approx(100.0)   # the body, not 100.6

    def test_the_wick_boundary_is_the_config_key_not_a_constant(self, cfg):
        series = make_series(bullish_rows(upper_wick=0.6))
        loose = cfg.with_overrides(wick_include_max_atr=1.0)
        assert float(only_block(series, loose).box_top) == pytest.approx(100.6)

    def test_body_only_mode_never_takes_a_wick(self, cfg):
        series = make_series(bullish_rows(upper_wick=0.4))
        bodies = cfg.with_overrides(ob_box_source="body_only")
        block = only_block(series, bodies)
        assert float(block.box_top) == pytest.approx(100.0)
        assert float(block.box_bottom) == pytest.approx(99.0)

    def test_the_mini_zone_alternative_widens_the_box_over_the_run(self, cfg):
        series = make_series(bullish_rows(reds=3))
        single = only_block(series, cfg)
        mini = only_block(series, cfg.with_overrides(ob_max_candles=3))
        assert mini.bar_index == single.bar_index          # still named by the block candle
        assert mini.box_top > single.box_top               # spans the three-candle run


# =========================================================================== CF-12 min size


class TestMinimumSize:
    """CF-12 / S6-R48 / S7-R6 — the spec replaces his raw dollars with ``size_atr``."""

    def test_the_threshold_comes_from_the_zone_module_that_owns_the_key(self, cfg):
        assert min_size_atr(cfg) == dec(cfg.min_zone_depth_atr)

    def test_size_atr_is_the_box_height_in_atr(self, cfg):
        series = make_series(bullish_rows())
        block = only_block(series, cfg)
        atr = P.atr_at(series, cfg, block.bar_index)
        assert block.size_atr == (block.box_top - block.box_bottom) / atr
        assert block.size_atr >= min_size_atr(cfg)

    def test_a_pinky_nail_block_is_rejected(self, cfg):
        series = make_series(bullish_rows(body=0.1, upper_wick=0.0))
        blocks, rejections = OrderBlockDetector().detect_with_rejections(series, cfg)
        assert [b for b in blocks if b.bar_index == 25] == []
        assert any(r.bar_index == 25 and "min_zone_depth_atr" in r.reasons[0]
                   for r in rejections)
        assert all(isinstance(r, OrderBlockRejection) for r in rejections)

    def test_lowering_the_threshold_lets_it_through(self, cfg):
        series = make_series(bullish_rows(body=0.1, upper_wick=0.0))
        loose = cfg.with_overrides(min_zone_depth_atr=0.05)
        assert only_block(series, loose).bar_index == 25

    def test_constructor_override_bypasses_the_config_lookup(self, cfg):
        series = make_series(bullish_rows(body=0.1, upper_wick=0.0))
        detector = OrderBlockDetector(min_size_atr=0.05)
        assert [b.bar_index for b in detector.detect(series, cfg)] == [25]
        assert OrderBlockDetector(min_size_atr=5.0).detect(series, cfg) == []


# =========================================================================== CF-08 invalidation


class TestFillAndDeath:
    """CF-08 / S8-R21 — the same 50 % rule as a zone; "completely filled" ⇒ dead."""

    def test_an_untouched_block_is_alive(self, cfg):
        block = block_at(make_series(bullish_rows()), cfg)
        assert block.fill_pct == Decimal(0)
        assert block.is_dead is False
        assert "CF-08" not in block.source_ids

    def test_a_block_traded_back_through_is_dead(self, cfg):
        block = block_at(make_series(bullish_rows(retrace_to=98.0)), cfg)
        assert float(block.fill_pct) == pytest.approx(100.0)
        assert block.is_dead is True
        assert {"CF-08", "S8-R21"} <= set(block.source_ids)

    def test_a_shallow_return_leaves_it_alive(self, cfg):
        block = block_at(make_series(bullish_rows(retrace_to=100.2)), cfg)
        assert block.fill_pct < dec(cfg.zone_fill_invalidation_pct)
        assert block.is_dead is False

    def test_fill_matches_p6_measured_from_the_move_away_extreme(self, cfg):
        series = make_series(bullish_rows(retrace_to=100.2))
        block = block_at(series, cfg)
        change = P.directional_change(series, cfg, block.dir_change_index)
        assert change is not None
        fill = P.measure_fill(series, cfg, P.order_block_box(series, cfg, block.bar_index),
                              ZoneSide.DEMAND, from_index=change.extreme_index)
        assert block.fill_pct == fill.fill_pct

    def test_the_threshold_is_the_order_block_key_not_the_zone_key(self, cfg):
        """**Q1** — the order block dies on ``ob_fill_invalidation_pct``, not the zone's 50 %.

        This test previously asserted the opposite (``zone_fill_invalidation_pct`` governed and
        P15 only ran when that zone key was raised to 70/80 — a setting nothing shipped, so P15
        was dead code).  He denies the coupling in as many words: *"so this one doesn't have a
        rule where you know 50% has to be taken… so my rule for order blocks are like around
        70 80%"* (S7 ``[00:07:14]``, ``[00:08:54]``).

        box = (98.9, 100.4): a low of 99.4 takes 66.7 % of the liquidity — dead under the old
        50 % zone rule, **alive** under his 75 % order-block rule.
        """
        series = make_series(bullish_rows(retrace_to=99.4))
        block = block_at(series, cfg)
        assert dec(50.0) < block.liquidity_taken_pct < dec(cfg.ob_fill_invalidation_pct)
        assert block.is_dead is False

        strict = cfg.with_overrides(ob_fill_invalidation_pct=60.0)
        assert block_at(series, strict).is_dead is True

        # Moving the *zone* key no longer touches the block at all.
        for zone_pct in (30.0, 95.0):
            moved = cfg.with_overrides(zone_fill_invalidation_pct=zone_pct)
            assert block_at(series, moved).is_dead is False

    def test_a_fifty_percent_filled_block_is_still_playable(self, cfg):
        """S7 ``[00:37:57]`` — *"this has 50% of the order block filled… you can still play it."*

        The passage that makes a single 50 % threshold untenable, and the reason Q1 splits the key.
        """
        series = make_series(bullish_rows(retrace_to=99.75))
        block = block_at(series, cfg)
        assert dec(45) <= block.liquidity_taken_pct <= dec(55)
        assert block.is_dead is False

    def test_a_fully_taken_block_is_dead(self, cfg):
        """S8 ``[00:34:48]`` — *"order block has been completely filled… you don't play it again."*"""
        block = block_at(make_series(bullish_rows(retrace_to=98.0)), cfg)
        assert float(block.liquidity_taken_pct) == pytest.approx(100.0)
        assert block.is_dead is True

    def test_a_dead_block_scores_no_confluence(self, cfg, detector):
        series = make_series(bullish_rows(retrace_to=98.0))
        blocks = detector.detect(series, cfg)
        dead = [b for b in blocks if b.is_dead]
        assert dead
        scored = {o.id for o in detector.to_confluence(blocks, cfg)}
        assert scored.isdisjoint({b.id for b in dead})


class TestQ1OrderBlockLiquidityThreshold:
    """**Q1 / S7-R3 / P15** — the order block's own death rule, at last reachable.

    Before Q1 this class was ``TestS7LiquidityAlternative`` and P15 ran only when
    ``zone_fill_invalidation_pct`` was raised to 70/80 — a setting nothing shipped, so the whole
    liquidity measure was dead code and the contradiction CF-08 papered over was live.
    """

    def test_liquidity_taken_matches_p15(self, cfg):
        series = make_series(bullish_rows(retrace_to=99.8))
        block = block_at(series, cfg)
        change = P.directional_change(series, cfg, block.dir_change_index)
        expected = P.ob_liquidity_taken_pct(
            series, cfg, P.order_block_box(series, cfg, block.bar_index),
            ZoneSide.DEMAND, from_index=change.extreme_index)
        assert block.liquidity_taken_pct == expected

    def test_p15_is_always_the_death_test_now(self, cfg):
        series = make_series(bullish_rows(retrace_to=99.8))
        block = block_at(series, cfg)
        assert ob_invalidation_pct(cfg) == dec(75.0)
        assert block.is_dead is (block.liquidity_taken_pct >= dec(75.0))
        assert {"S7-R3", "P15"} <= set(block.source_ids)

    def test_the_band_is_seventy_to_eighty(self, cfg):
        """His stated band, S7 ``[00:08:54]``: 75 is its midpoint and the shipped default."""
        series = make_series(bullish_rows(retrace_to=99.4))
        taken = block_at(series, cfg).liquidity_taken_pct
        for pct in (70.0, 75.0, 80.0):
            tuned = cfg.with_overrides(ob_fill_invalidation_pct=pct)
            assert block_at(series, tuned).is_dead is (taken >= dec(pct))

    def test_the_wick_measure_wins_over_close_beyond(self, cfg):
        """P15 is always the deepest **wick**; ``zone_fill_measure`` never applies to a block."""
        series = make_series(bullish_rows(retrace_to=99.4))
        closes = cfg.with_overrides(zone_fill_measure="close_beyond")
        block = block_at(series, closes)
        assert block.liquidity_taken_pct > block.fill_pct     # wick deeper than any close
        assert block.is_dead is (block.liquidity_taken_pct >= dec(cfg.ob_fill_invalidation_pct))


class TestQ6ImpulseLegPercentageFloor:
    """**Q6 [INFERRED]** — ``dir_change_uses_sufficient_gap_table``.

    He never attaches a size to "directional change" in the order-block definition, so P2's
    ``dir_change_atr = 2.0`` is **[OUR CHOICE]** and was the only magnitude test an order block
    had.  But the one quantified move-size test he owns is the sufficient-gap-by-timeframe table,
    and in every worked example the order block and the supply/demand zone are marked off the
    **same** impulse leg whose gap he has just checked out loud (S5 ``[00:54:07]``).  His
    threshold is a **percentage that scales with timeframe**, which an ATR multiple cannot
    express: *"Higher time frames need to have a higher move away from that zone"* (S5
    ``[00:36:05]``).

    Supply/demand zones already applied the table as P10; order blocks had nothing.  Now they do,
    and — unlike a filter buried in P2 — the rejection is *reported*, so the veto census still
    adds up.
    """

    def test_the_same_bars_survive_on_1h_and_die_on_1d(self, cfg):
        """A ~7 % impulse: comfortably over the 1H row (4.0), under the daily row (8.0).

        *"Now a four or 3% move on the daily is not a strong move from this breakout point."*
        """
        rows = bullish_rows(rally=6)
        assert OrderBlockDetector().detect(make_series(rows, tf="1H"), cfg)

        daily = make_series(rows, tf="1D")
        blocks, rejections = OrderBlockDetector().detect_with_rejections(daily, cfg)
        assert blocks == []
        assert any("sufficient_gap_pct_by_tf[1D]" in r for rej in rejections for r in rej.reasons)
        assert any("dir_change_uses_sufficient_gap_table" in r
                   for rej in rejections for r in rej.reasons)

    def test_switching_it_off_restores_the_pure_atr_test(self, cfg):
        rows = bullish_rows(rally=6)
        off = cfg.with_overrides(dir_change_uses_sufficient_gap_table=False)
        assert OrderBlockDetector().detect(make_series(rows, tf="1D"), off)

    def test_a_big_enough_leg_clears_the_daily_row(self, cfg):
        """15 % away on the daily: over his "at least 8 to 12%" floor, so the block stands."""
        rows = bullish_rows(rally=15)
        assert OrderBlockDetector().detect(make_series(rows, tf="1D"), cfg)


# =========================================================================== CF-09 nesting


class TestNestingInsideZones:
    """CF-09 / S6-R31 — "more consolidation demand zone over the order block"."""

    @staticmethod
    def _nested(syn, cfg, config=None):
        config = config or cfg
        zones = SupplyDemandZoneDetector().detect(syn.series, config)
        assert len(zones) == 1
        blocks = OrderBlockDetector(zones=zones).detect(syn.series, config)
        inside = [b for b in blocks if b.parent_zone_id is not None]
        return zones[0], blocks, inside

    def test_contained_blocks_point_at_their_zone(self, syn, cfg):
        zone, _blocks, inside = self._nested(syn, cfg)
        assert inside
        for block in inside:
            assert block.parent_zone_id == zone.id
            assert zone.box_bottom <= block.box_bottom and block.box_top <= zone.box_top
            assert {"CF-09", "S6-R31"} <= set(block.source_ids)

    def test_the_zone_records_the_blocks_it_holds(self, syn, cfg):
        zone, _blocks, inside = self._nested(syn, cfg)
        assert zone.contained_ob_ids == [b.id for b in inside]

    def test_zone_wins_hands_the_zone_verdict_to_the_block(self, syn, cfg):
        zone, _blocks, inside = self._nested(syn, cfg)
        assert cfg.ob_inside_zone_precedence == "zone_wins"
        for block in inside:
            assert block.fill_pct == zone.fill_pct
            assert block.is_dead is zone.is_dead

    def test_ob_wins_keeps_the_blocks_own_fill(self, syn, cfg):
        ob_wins = cfg.with_overrides(ob_inside_zone_precedence="ob_wins")
        zone, _blocks, inside = self._nested(syn, cfg, ob_wins)
        assert inside
        assert any(block.fill_pct != zone.fill_pct for block in inside)
        assert all(block.parent_zone_id == zone.id for block in inside)

    def test_blocks_outside_every_zone_stay_unparented(self, syn, cfg):
        zone, blocks, inside = self._nested(syn, cfg)
        outside = [b for b in blocks if b not in inside]
        assert outside
        assert all(b.parent_zone_id is None for b in outside)

    def test_linking_is_a_no_op_without_zones(self, cfg):
        series = make_series(bullish_rows())
        blocks = OrderBlockDetector().detect(series, cfg)
        assert link_to_zones(blocks, [], cfg) == blocks
        assert all(b.parent_zone_id is None for b in blocks)


# =========================================================================== edge cases


class TestEdgeCases:
    def test_empty_and_tiny_series_produce_nothing(self, cfg, detector):
        assert detector.detect(make_series([(1.0, 1.0, 1.0, 1.0)]), cfg) == []
        assert detector.detect(make_series([(1.0, 1.5, 0.5, 1.0)] * 2), cfg) == []

    def test_flat_series_produces_nothing(self, cfg, detector):
        assert detector.detect(make_series(warmup(60)), cfg) == []

    def test_one_block_per_bar_at_most(self, syn, cfg, detector):
        bars = [b.bar_index for b in detector.detect(syn.series, cfg)]
        assert len(bars) == len(set(bars))

    def test_dir_change_max_bars_bounds_the_trigger(self, syn, cfg, detector):
        for block in detector.detect(syn.series, cfg):
            assert block.bar_index <= block.dir_change_index
            assert block.dir_change_index - block.bar_index <= cfg.dir_change_max_bars
