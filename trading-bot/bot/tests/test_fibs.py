"""Tests for tbot.detectors.fibs (SPEC.md §5.9)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

import pytest

import tbot.primitives as P
from tbot.config import Config
from tbot.data import synthetic
from tbot.detectors.base import Detector
from tbot.detectors.fibs import (
    RATIO_886,
    FibDetector,
    active_ratios,
    apply_sr_precedence,
    build_fibs,
    extension_levels,
    fib_price,
    in_golden_pocket,
    role_of,
    select_anchor,
    sole_basis_veto,
)
from tbot.models import (
    Direction,
    Level,
    LevelKind,
    Series,
    SwingKind,
    Timeframe,
    Zone,
    ZoneClass,
    ZoneSide,
    dec,
)


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


def _leg(start: float, stop: float, step: float) -> list[float]:
    out: list[float] = []
    x = start
    while (step > 0 and x <= stop) or (step < 0 and x >= stop):
        out.append(round(x, 6))
        x += step
    return out


#: down to 100, up to 200, back down to 150, then up — clean low→high and high→low legs.
_SWING = _leg(120, 100, -2) + _leg(105, 200, 5) + _leg(195, 150, -5) + _leg(155, 175, 5)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def series() -> Series:
    return _from_closes(_SWING)


def _level(price: Decimal, series: Series, ident: str = "lvl") -> Level:
    return Level(
        id=ident,
        symbol=series.symbol,
        tf=series.tf,
        price=price,
        kind=LevelKind.SUPPORT,
        created_index=0,
        source_ids=("S4-R4",),
    )


def _zone(top: Decimal, bottom: Decimal, series: Series) -> Zone:
    return Zone(
        id="zone",
        symbol=series.symbol,
        tf=series.tf,
        side=ZoneSide.DEMAND,
        zone_class=ZoneClass.REVERSAL,
        box_top=top,
        box_bottom=bottom,
        midpoint=(top + bottom) / Decimal(2),
        body_count=2,
        formation_start_index=0,
        formation_end_index=1,
        breakout_index=2,
        move_away_pct=dec(5),
        move_away_atr=dec(3),
        depth_atr=dec(1),
        source_ids=("CF-10",),
    )


# --------------------------------------------------------------------------- protocol

def test_detector_satisfies_protocol() -> None:
    det = FibDetector()
    assert isinstance(det, Detector)
    assert det.name == "fibs" and det.stage == 10
    assert det.produces == ("fib",)
    assert det.standalone_forbidden is True


# --------------------------------------------------------------------------- the three levels

def test_only_the_three_tradeable_levels_are_active(cfg: Config) -> None:
    """S6-R32 / S6-R33 / CF-33: the golden pocket pair and the 0.786, nothing else."""
    assert [float(r) for r in active_ratios(cfg)] == [0.618, 0.66, 0.786]


def test_886_is_off_by_default_and_gated_by_its_key(cfg: Config) -> None:
    """S6-A22: in his recommended list but explicitly not back-tested (precedence rule 4)."""
    assert cfg.fib_886_enabled is False
    assert RATIO_886 not in active_ratios(cfg)
    assert RATIO_886 in active_ratios(cfg.with_overrides(fib_886_enabled=True))


def test_golden_pocket_band_and_the_786_are_separate(cfg: Config) -> None:
    """S8 uses them interchangeably; CF-33 says that is a verbal slip."""
    assert in_golden_pocket(dec(0.618), cfg) and in_golden_pocket(dec(0.66), cfg)
    assert not in_golden_pocket(dec(0.786), cfg)
    assert role_of(dec(0.618), cfg) == "entry"
    assert role_of(dec(0.66), cfg) == "entry"
    assert role_of(dec(0.786), cfg) == "dca"
    assert role_of(dec(0.5), cfg) == "none"


def test_no_non_standard_levels_are_ever_emitted(cfg: Config, series: Series) -> None:
    """S6 exclusions: 0.113, 0.13, 2.14, channels, spirals and arcs are all out of scope."""
    allowed = set(active_ratios(cfg))
    for fib in FibDetector().detect(series, cfg):
        assert fib.ratio in allowed


# --------------------------------------------------------------------------- draw convention

def test_bullish_fib_is_drawn_low_to_high(cfg: Config, series: Series) -> None:
    """CF-34 / S6-R34: bullish = swing low → swing high."""
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    assert anchor.low.kind is SwingKind.LOW and anchor.high.kind is SwingKind.HIGH
    assert anchor.drawn_from_index == anchor.low.bar_index
    assert anchor.drawn_to_index == anchor.high.bar_index
    assert anchor.low.bar_index < anchor.high.bar_index


def test_bearish_fib_is_drawn_high_to_low(cfg: Config, series: Series) -> None:
    """CF-34 / S6-R35: bearish = swing high → swing low."""
    anchor = select_anchor(series, cfg, Direction.SHORT)
    assert anchor is not None
    assert anchor.drawn_from_index == anchor.high.bar_index
    assert anchor.drawn_to_index == anchor.low.bar_index
    assert anchor.high.bar_index < anchor.low.bar_index


def test_tbot1_convention_inverts_the_draw(cfg: Config, series: Series) -> None:
    """The TBOT1 inversion is rejected as a narration artefact but kept for the sweep."""
    inverted = cfg.with_overrides(fib_draw_convention="tbot1")
    s6 = select_anchor(series, cfg, Direction.LONG)
    tb = select_anchor(series, inverted, Direction.LONG)
    assert s6 is not None and tb is not None
    assert (s6.drawn_from_index, s6.drawn_to_index) != (tb.drawn_from_index, tb.drawn_to_index)


def test_retracement_prices_come_off_the_right_end(cfg: Config, series: Series) -> None:
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    leg = anchor.leg
    assert fib_price(anchor, dec(0.618)) == anchor.high.price - dec(0.618) * leg
    assert fib_price(anchor, dec(0)) == anchor.high.price
    assert fib_price(anchor, dec(1)) == anchor.low.price

    bear = select_anchor(series, cfg, Direction.SHORT)
    assert bear is not None
    assert fib_price(bear, dec(0.618)) == bear.low.price + dec(0.618) * bear.leg


def test_anchor_selection_modes(cfg: Config, series: Series) -> None:
    assert select_anchor(series, cfg.with_overrides(fib_anchor_selection="manual"), Direction.LONG) is None
    largest = select_anchor(series, cfg.with_overrides(fib_anchor_selection="largest_leg"), Direction.LONG)
    recent = select_anchor(series, cfg, Direction.LONG)
    assert largest is not None and recent is not None
    assert largest.leg >= recent.leg


def test_anchors_respect_no_lookahead(cfg: Config, series: Series) -> None:
    anchor = select_anchor(series, cfg, Direction.LONG, at_index=len(series) - 1)
    assert anchor is not None
    assert anchor.confirmed_at_index <= len(series) - 1
    early = select_anchor(series, cfg, Direction.LONG, at_index=5)
    assert early is None


def test_fibs_on_the_synthetic_series(cfg: Config) -> None:
    syn = synthetic(seed=7)
    fibs = FibDetector().detect(syn.series, cfg)
    assert fibs
    longs = [f for f in fibs if f.direction is Direction.LONG]
    assert len(longs) == 3
    assert [float(f.ratio) for f in longs] == [0.618, 0.66, 0.786]
    for fib in longs:
        assert fib.price < dec(syn.features.sfp_swing_price)


# --------------------------------------------------------------------------- subordination to S/R

def test_fib_loses_the_tie_to_a_drawn_level(cfg: Config, series: Series) -> None:
    """S6-R38 / PL-3: where a fib disagrees with drawn S/R, the S/R wins."""
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    fibs = build_fibs(series, cfg, anchor)
    gp = next(f for f in fibs if f.ratio == dec(0.618))

    nudged = gp.price + dec("0.10")
    resolved = apply_sr_precedence(series, cfg, fibs, levels=[_level(nudged, series)])
    winner = next(f for f in resolved if f.ratio == dec(0.618))
    assert winner.price == nudged, "the drawn level's price wins, not the fib's"
    assert "S6-R38" in winner.source_ids


def test_a_fib_with_no_sr_nearby_is_untouched(cfg: Config, series: Series) -> None:
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    fibs = build_fibs(series, cfg, anchor)
    far = _level(dec(1_000), series)
    resolved = apply_sr_precedence(series, cfg, fibs, levels=[far])
    assert [f.price for f in resolved] == [f.price for f in fibs]
    assert all("S6-R38" not in f.source_ids for f in resolved)


def test_zones_also_win_ties(cfg: Config, series: Series) -> None:
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    fibs = build_fibs(series, cfg, anchor)
    gp = next(f for f in fibs if f.ratio == dec(0.66))
    zone = _zone(gp.price + dec(2), gp.price - dec(2), series)
    resolved = apply_sr_precedence(series, cfg, fibs, zones=[zone])
    winner = next(f for f in resolved if f.ratio == dec(0.66))
    assert winner.price == zone.outer_edge
    assert "S6-R38" in winner.source_ids


def test_precedence_can_be_switched_off(cfg: Config, series: Series) -> None:
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    fibs = build_fibs(series, cfg, anchor)
    gp = next(f for f in fibs if f.ratio == dec(0.618))
    off = cfg.with_overrides(fib_loses_ties_to_sr=False)
    resolved = apply_sr_precedence(series, off, fibs, levels=[_level(gp.price + dec("0.10"), series)])
    assert [f.price for f in resolved] == [f.price for f in fibs]


def test_precedence_is_deterministic_between_competing_levels(cfg: Config, series: Series) -> None:
    anchor = select_anchor(series, cfg, Direction.LONG)
    assert anchor is not None
    fibs = build_fibs(series, cfg, anchor)
    gp = next(f for f in fibs if f.ratio == dec(0.618))
    near = _level(gp.price + dec("0.05"), series, ident="near")
    far = _level(gp.price + dec("0.20"), series, ident="far")
    a = apply_sr_precedence(series, cfg, fibs, levels=[near, far])
    b = apply_sr_precedence(series, cfg, fibs, levels=[far, near])
    assert [f.price for f in a] == [f.price for f in b]
    assert next(f for f in a if f.ratio == dec(0.618)).price == near.price


# --------------------------------------------------------------------------- never the sole basis

def test_a_fib_alone_is_vetoed(cfg: Config, series: Series) -> None:
    """S6-R30: never trade fibs alone."""
    fib = FibDetector().detect(series, cfg)[0]
    only_fibs = [P.ConfluenceObject("other-fib", fib.price, "fib")]
    veto = sole_basis_veto(fib, only_fibs)
    assert veto is not None and "S6-R30" in veto
    assert sole_basis_veto(fib, []) is not None


def test_a_fib_with_real_confluence_is_not_vetoed(cfg: Config, series: Series) -> None:
    fib = FibDetector().detect(series, cfg)[0]
    stack = [
        P.ConfluenceObject("lvl", fib.price, "sr_level"),
        P.ConfluenceObject("zone", fib.price, "zone"),
    ]
    assert sole_basis_veto(fib, stack) is None


def test_fibs_only_ever_produce_the_fib_class(cfg: Config, series: Series) -> None:
    det = FibDetector()
    scored = det.to_confluence(det.detect(series, cfg), cfg)
    assert scored
    assert {o.obj_class for o in scored} == {"fib"}


# --------------------------------------------------------------------------- extensions

def test_extensions_are_price_discovery_only(cfg: Config, series: Series) -> None:
    """S6-R36: low → high (ATH) → new low, all levels used, count supplied by the caller."""
    pivots = P.swing_points(series, cfg)
    low = next(p for p in pivots if p.kind is SwingKind.LOW)
    high = next(p for p in pivots if p.kind is SwingKind.HIGH and p.bar_index > low.bar_index)
    pullback = [p for p in pivots if p.kind is SwingKind.LOW and p.bar_index > high.bar_index]
    pullback_low = pullback[0] if pullback else low

    levels = extension_levels(
        series, cfg, swing_low=low, swing_high=high, pullback_low=pullback_low, count=5
    )
    assert len(levels) == 5
    leg = high.price - low.price
    assert levels[0].price == pullback_low.price + leg
    assert all(b.price > a.price for a, b in zip(levels, levels[1:]))
    assert all("S6-R36" in lv.source_ids for lv in levels)


def test_extensions_reject_a_bad_count(cfg: Config, series: Series) -> None:
    pivots = P.swing_points(series, cfg)
    low = next(p for p in pivots if p.kind is SwingKind.LOW)
    high = next(p for p in pivots if p.kind is SwingKind.HIGH and p.bar_index > low.bar_index)
    with pytest.raises(ValueError):
        extension_levels(series, cfg, swing_low=low, swing_high=high, pullback_low=low, count=0)


# --------------------------------------------------------------------------- hygiene

def test_every_fib_carries_source_ids_and_a_stable_id(cfg: Config, series: Series) -> None:
    fibs = FibDetector().detect(series, cfg)
    assert fibs
    ids = [f.id for f in fibs]
    assert len(ids) == len(set(ids))
    for fib in fibs:
        assert fib.source_ids
        assert fib.id.startswith("TEST:1H:fib:")
        assert fib.in_golden_pocket == in_golden_pocket(fib.ratio, cfg)


def test_detect_is_deterministic(cfg: Config, series: Series) -> None:
    det = FibDetector()
    assert [f.id for f in det.detect(series, cfg)] == [f.id for f in det.detect(series, cfg)]
    assert [f.price for f in det.detect(series, cfg)] == [f.price for f in det.detect(series, cfg)]
