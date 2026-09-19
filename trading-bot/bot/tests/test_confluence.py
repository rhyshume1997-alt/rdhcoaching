"""Contract tests for tbot.confluence (SPEC.md §6, CF-31, CF-10).

Detection objects are constructed **by hand** here — never taken from ``tbot.detectors`` — so
these tests measure the scoring layer and nothing else.  Every series uses the constant-true-range
helper, so ``ATR == 1.0`` at every bar and ``confluence_merge_atr = 0.25`` is exactly a 0.25 band.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tbot.config import Config
from tbot.confluence import (
    ConfluenceCluster,
    best_cluster,
    cluster_prices,
    confluence_class_of,
    confluence_price_of,
    find_clusters,
    map_conviction,
    rank_clusters,
    score_at,
    to_confluence_object,
    to_confluence_objects,
)
from tbot.models import (
    Conviction,
    Direction,
    FibLevel,
    Level,
    LevelKind,
    OrderBlock,
    OBSide,
    Series,
    Timeframe,
    Zone,
    ZoneClass,
    ZoneSide,
    dec,
)

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_series(rows, tf: str = "1H", symbol: str = "T") -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [T0 + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1.0] * len(rows), tf=tf, symbol=symbol,
    )


def flat_bars(n: int, price: float = 100.0):
    """``n`` bars with a constant true range of 1.0 → ``ATR == 1.0`` everywhere."""
    return [(price, price + 0.5, price - 0.5, price)] * n


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def series() -> Series:
    return make_series(flat_bars(60))


def a_level(price: float, *, kind: LevelKind = LevelKind.SUPPORT, ident: str = "lvl",
            tf: Timeframe = Timeframe.H1, source_ids=("S4-R4",)) -> Level:
    return Level(
        id=ident, symbol="T", tf=tf, price=dec(price), kind=kind, created_index=0,
        source_ids=tuple(source_ids),
    )


def a_zone(price: float, *, ident: str = "zone", zone_class: ZoneClass = ZoneClass.REVERSAL,
           tf: Timeframe = Timeframe.H1, source_ids=("CF-10", "S5-R15")) -> Zone:
    return Zone(
        id=ident, symbol="T", tf=tf, side=ZoneSide.DEMAND, zone_class=zone_class,
        box_top=dec(price + 0.4), box_bottom=dec(price - 0.4), midpoint=dec(price),
        body_count=3, formation_start_index=1, formation_end_index=4, breakout_index=5,
        move_away_pct=dec(6), move_away_atr=dec(3), depth_atr=dec(0.8),
        source_ids=tuple(source_ids),
    )


def an_ob(price: float, *, ident: str = "ob", tf: Timeframe = Timeframe.H1,
          source_ids=("S6-R1",)) -> OrderBlock:
    return OrderBlock(
        id=ident, symbol="T", tf=tf, side=OBSide.BULLISH, bar_index=7,
        box_top=dec(price + 0.1), box_bottom=dec(price - 0.1), dir_change_index=9,
        dir_change_atr_move=dec(2.5), source_ids=tuple(source_ids),
    )


def a_fib(price: float, *, ident: str = "fib", tf: Timeframe = Timeframe.H4) -> FibLevel:
    return FibLevel(
        id=ident, symbol="T", tf=tf, ratio=dec(0.618), price=dec(price), anchor_low_index=1,
        anchor_high_index=9, direction=Direction.LONG, in_golden_pocket=True,
        source_ids=("S6-R32",),
    )


# =========================================================================== adapters


class TestAdapters:
    def test_model_types_map_to_their_confluence_class(self):
        assert confluence_class_of(a_level(100.0)) == "sr_level"
        assert confluence_class_of(a_level(100.0, kind=LevelKind.RANGE_HIGH)) == "range_boundary"
        assert confluence_class_of(a_level(100.0, kind=LevelKind.TRENDLINE)) == "trendline"
        assert confluence_class_of(a_zone(100.0)) == "zone"
        assert confluence_class_of(an_ob(100.0)) == "order_block"
        assert confluence_class_of(a_fib(100.0)) == "fib"

    def test_mid_range_is_a_gate_not_a_contributor(self):
        with pytest.raises(ValueError, match="no-trade band"):
            confluence_class_of(a_level(100.0, kind=LevelKind.MID_RANGE))

    def test_duck_typed_records_declare_their_own_class(self):
        class SfpRecord:
            id = "sfp-1"
            price = dec(100.0)
            confluence_class = "sfp"
            tf = Timeframe.H1
            source_ids = ("S7-R30",)

        obj = to_confluence_object(SfpRecord())
        assert obj.obj_class == "sfp" and obj.source_ids == ("S7-R30",)

    def test_zone_scores_at_pmt_then_falls_back_to_midpoint(self):
        zone = a_zone(100.0)
        assert confluence_price_of(zone) == zone.midpoint
        zone.entry_price_pmt = dec(100.2)
        assert confluence_price_of(zone) == dec(100.2)

    def test_order_block_scores_at_its_midpoint(self):
        assert confluence_price_of(an_ob(100.0)) == dec(100.0)

    def test_trendline_price_is_read_on_the_bar(self):
        line = a_level(100.0, kind=LevelKind.TRENDLINE)
        line.slope_per_bar = dec(0.1)
        assert confluence_price_of(line, bar_index=10) == dec(101.0)

    def test_source_ids_survive_the_adapter(self):
        obj = to_confluence_object(a_zone(100.0))
        assert obj.source_ids == ("CF-10", "S5-R15")

    def test_repeated_ids_are_dropped_first_wins(self):
        objs = to_confluence_objects([a_level(100.0, ident="x"), a_level(101.0, ident="x")])
        assert len(objs) == 1 and objs[0].price == dec(100.0)

    def test_swing_points_have_no_confluence_class(self):
        with pytest.raises(ValueError, match="no confluence class"):
            confluence_class_of(object())


# =========================================================================== dedup / scoring


class TestScoring:
    def test_tbot1_a4_three_classes_at_one_price_score_three_times(self, series, cfg):
        """SR point + supply zone + order block at one price = 3 objects, 3 contributions."""
        result = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="lvl"), a_zone(100.05, ident="z"), an_ob(99.95, ident="ob")],
            at_index=50,
        )
        assert result.score == dec(1.5) + dec(1.25) + dec(1.0)
        assert result.classes == frozenset({"sr_level", "zone", "order_block"})
        assert len(result.contributors) == 3
        assert result.qualified is True

    def test_same_class_at_one_price_counts_once_at_the_higher_weight(self, series, cfg):
        result = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="a"), a_level(100.1, ident="b"), a_zone(100.0, ident="z")],
            at_index=50,
        )
        assert result.score == dec(1.5) + dec(1.25)      # not 1.5 + 1.5 + 1.25
        assert result.classes == frozenset({"sr_level", "zone"})
        assert [o.id for o in result.contributors] == ["a", "z"]

    def test_objects_outside_the_merge_band_do_not_contribute(self, series, cfg):
        result = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="near"), a_fib(112.0, ident="far")],
            at_index=50,
        )
        assert [o.id for o in result.merged] == ["near"]
        assert result.classes == frozenset({"sr_level"})

    def test_single_class_stack_is_forbidden_regardless_of_score(self, series, cfg):
        """Never an OB alone, a fib alone, a pattern alone (S6-R29/R30, S4-R38, S7-R30)."""
        objs = [an_ob(100.0, ident=f"ob{i}") for i in range(6)]
        result = score_at(series, cfg, 100.0, objs, at_index=50)
        assert result.qualified is False
        assert any("single_class_trade_forbidden" in r for r in result.reasons)

    def test_below_min_confluence_count_does_not_qualify(self, series, cfg):
        result = score_at(
            series, cfg, 100.0, [a_fib(100.0, ident="f"), an_ob(100.0, ident="o")], at_index=50
        )
        assert result.score == dec(2.0) and result.qualified is False
        assert any("min_confluence_count" in r for r in result.reasons)

    def test_continuation_zone_takes_the_cf10_bonus(self, series, cfg):
        objs = [a_level(100.0, ident="l"), a_zone(100.0, ident="z"), an_ob(100.0, ident="o")]
        plain = score_at(series, cfg, 100.0, objs, at_index=50)
        bonus = score_at(series, cfg, 100.0, objs, at_index=50, continuation_zone=True)
        assert bonus.score - plain.score == dec(cfg.zone_continuation_confluence_bonus)
        assert bonus.bonus == dec(1.0)

    def test_source_ids_chain_is_preserved_in_contributor_order(self, series, cfg):
        result = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="l"), a_zone(100.0, ident="z"), an_ob(100.0, ident="o")],
            at_index=50,
        )
        assert result.source_ids == ("S4-R4", "CF-10", "S5-R15", "S6-R1")
        assert result.object_ids == ("l", "z", "o")

    def test_scoring_is_deterministic(self, series, cfg):
        objs = [a_level(100.0, ident="l"), a_zone(100.0, ident="z"), an_ob(100.0, ident="o")]
        first = score_at(series, cfg, 100.0, objs, at_index=50)
        second = score_at(series, cfg, 100.0, objs, at_index=50)
        assert first == second

    def test_cross_market_context_is_never_a_scoring_object(self, series, cfg):
        """CF-35 / TBOT1 §10: context is weight 0.  It has no ConfluenceClass to be wrapped as."""
        class DominanceRead:
            id = "USDT.D"
            price = dec(100.0)
            confluence_class = "usdt_dominance"

        with pytest.raises(ValueError):
            to_confluence_object(DominanceRead())


# =========================================================================== conviction


class TestConviction:
    def test_high_normal_low_bands(self, cfg):
        assert map_conviction(4.75, cfg) is Conviction.HIGH
        assert map_conviction(4.0, cfg) is Conviction.HIGH
        assert map_conviction(3.75, cfg) is Conviction.NORMAL
        assert map_conviction(3.0, cfg) is Conviction.NORMAL
        assert map_conviction(2.5, cfg) is Conviction.LOW

    def test_adverse_regime_flag_forces_low_however_high_the_score(self, cfg):
        assert map_conviction(6.0, cfg, adverse_regime=True) is Conviction.LOW
        assert map_conviction(6.0, cfg, mid_range_flag=True) is Conviction.LOW
        assert map_conviction(6.0, cfg, unclear_price_action=True) is Conviction.LOW

    def test_cluster_carries_the_conviction(self, series, cfg):
        result = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="l"), a_zone(100.0, ident="z"), an_ob(100.0, ident="o"),
             a_fib(100.0, ident="f")],
            at_index=50,
        )
        assert result.score == dec(4.75) and result.conviction is Conviction.HIGH
        adverse = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="l"), a_zone(100.0, ident="z"), an_ob(100.0, ident="o"),
             a_fib(100.0, ident="f")],
            at_index=50, adverse_regime=True,
        )
        assert adverse.conviction is Conviction.LOW


# =========================================================================== clustering


class TestClustering:
    def test_clusters_split_at_the_merge_band(self, series, cfg):
        objs = [a_level(100.0, ident="a"), a_zone(100.1, ident="b"), a_level(105.0, ident="c")]
        prices = cluster_prices(series, cfg, objs, at_index=50)
        assert prices == [dec(100.0), dec(105.0)]

    def test_a_ladder_of_levels_does_not_chain_into_one_cluster(self, series, cfg):
        """Anchored, not single-linked: 0.2 apart repeatedly must not merge into one stack."""
        objs = [a_level(100.0 + 0.2 * i, ident=f"l{i}") for i in range(5)]
        prices = cluster_prices(series, cfg, objs, at_index=50)
        assert len(prices) > 1

    def test_cluster_price_is_the_heaviest_object(self, series, cfg):
        objs = [an_ob(100.0, ident="ob"), a_level(100.1, ident="lvl")]
        assert cluster_prices(series, cfg, objs, at_index=50) == [dec(100.1)]

    def test_find_clusters_scores_every_stack_and_ranks_them(self, series, cfg):
        objs = [
            a_level(100.0, ident="l1"), a_zone(100.0, ident="z1"), an_ob(100.0, ident="o1"),
            a_level(120.0, ident="l2"), an_ob(120.0, ident="o2"),
        ]
        clusters = find_clusters(series, cfg, objs, at_index=50)
        assert len(clusters) == 2
        assert clusters[0].price == dec(100.0) and clusters[0].qualified is True
        assert clusters[1].price == dec(120.0) and clusters[1].qualified is False
        assert best_cluster(clusters) is clusters[0]

    def test_continuation_zone_ids_apply_the_bonus_to_the_right_stack(self, series, cfg):
        objs = [
            a_level(100.0, ident="l1"),
            a_zone(100.0, ident="z1", zone_class=ZoneClass.CONTINUATION),
            an_ob(100.0, ident="o1"),
        ]
        plain = find_clusters(series, cfg, objs, at_index=50)[0]
        boosted = find_clusters(
            series, cfg, objs, at_index=50, continuation_zone_ids=["z1"]
        )[0]
        assert boosted.score == plain.score + dec(1.0)

    def test_ties_break_to_the_higher_timeframe(self, series, cfg):
        low = score_at(
            series, cfg, 100.0,
            [a_level(100.0, ident="l", tf=Timeframe.H1), a_zone(100.0, ident="z", tf=Timeframe.H1)],
            at_index=50,
        )
        high = score_at(
            series, cfg, 120.0,
            [a_level(120.0, ident="L", tf=Timeframe.D1), a_zone(120.0, ident="Z", tf=Timeframe.H4)],
            at_index=50,
        )
        assert low.score == high.score
        assert rank_clusters([low, high])[0] is high

    def test_empty_input_yields_nothing_never_a_forced_setup(self, series, cfg):
        assert cluster_prices(series, cfg, [], at_index=50) == []
        assert find_clusters(series, cfg, [], at_index=50) == []
        assert best_cluster([]) is None

    def test_result_type_is_a_frozen_cluster(self, series, cfg):
        cluster = score_at(series, cfg, 100.0, [a_level(100.0)], at_index=50)
        assert isinstance(cluster, ConfluenceCluster)
        with pytest.raises(Exception):
            cluster.score = dec(9)  # type: ignore[misc]
