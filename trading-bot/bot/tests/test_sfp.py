"""Tests for tbot.detectors.sfp (SPEC.md §5.8).

Every §5.8 filter gets a pair of tests: one series it accepts and one it correctly rejects.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

import pytest

import tbot.primitives as P
from tbot.config import Config
from tbot.data import synthetic
from tbot.detectors.base import Detector
from tbot.detectors.sfp import (
    SFP,
    SFPDetector,
    evaluate,
    find_sfps,
    governing_timeframe,
    raid_price,
    raid_candidates,
)
from tbot.models import (
    Box,
    Direction,
    Level,
    LevelKind,
    Series,
    SwingKind,
    Timeframe,
    Trend,
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


def _bars_from_closes(closes: Sequence[float], wick: float = 0.05) -> list[tuple[float, float, float, float]]:
    opens = [closes[0]] + list(closes[:-1])
    return [(o, max(o, c) + wick, min(o, c) - wick, c) for o, c in zip(opens, closes)]


def _leg(start: float, stop: float, step: float) -> list[float]:
    out: list[float] = []
    x = start
    while (step > 0 and x <= stop) or (step < 0 and x >= stop):
        out.append(round(x, 6))
        x += step
    return out


#: An up-trending zigzag: higher highs and higher lows, so a *bullish* SFP at the last swing low
#: is with the trend and survives ``sfp_trend_veto`` (S7-R31).
_UPTREND = (
    _leg(100, 108, 2)
    + _leg(107, 103, -1)          # the first higher low
    + _leg(105, 120, 3)
    + _leg(118, 112, -2)          # the swing low that will be raided
    + _leg(114, 118, 2)
)


def _sfp_series(
    *,
    raid_low: float = 108.0,
    raid_close: float = 114.0,
    pad: int = 0,
) -> Series:
    """The base fixture: an uptrend, then a candle wicking under the last higher low and closing
    back above it.  ``pad`` inserts flat bars before the raid."""
    closes = list(_UPTREND) + [118.0] * pad
    bars = _bars_from_closes(closes)
    prev = bars[-1][3]
    bars.append((prev, max(prev, raid_close) + 0.05, raid_low, raid_close))
    return _ohlc(bars)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def series() -> Series:
    return _sfp_series()


@pytest.fixture(scope="module")
def swept_low(series: Series, cfg: Config):
    lows = [p for p in P.swing_points(series, cfg) if p.kind is SwingKind.LOW]
    return lows[-1]


def _level_at(price: Decimal, series: Series) -> Level:
    return Level(
        id="pre-marked-level",
        symbol=series.symbol,
        tf=series.tf,
        price=price,
        kind=LevelKind.SUPPORT,
        created_index=0,
        source_ids=("S4-R4",),
    )


def _zone_at(price: Decimal, series: Series) -> Zone:
    box = Box(top=price + dec(1), bottom=price - dec(1), start_index=0, end_index=1)
    return Zone(
        id="pre-marked-zone",
        symbol=series.symbol,
        tf=series.tf,
        side=ZoneSide.DEMAND,
        zone_class=ZoneClass.REVERSAL,
        box_top=box.top,
        box_bottom=box.bottom,
        midpoint=box.midpoint,
        body_count=2,
        formation_start_index=0,
        formation_end_index=1,
        breakout_index=2,
        move_away_pct=dec(5),
        move_away_atr=dec(3),
        depth_atr=dec(1),
        source_ids=("CF-10",),
    )


def _accepted(series: Series, cfg: Config, **kw) -> list[SFP]:
    swing = [p for p in P.swing_points(series, cfg) if p.kind is SwingKind.LOW][-1]
    kw.setdefault("levels", [_level_at(swing.wick_price, series)])
    return find_sfps(series, cfg, **kw)


# --------------------------------------------------------------------------- protocol

def test_detector_satisfies_protocol() -> None:
    det = SFPDetector()
    assert isinstance(det, Detector)
    assert det.name == "swing_failure_pattern" and det.stage == 13
    assert det.produces == ("sfp",)
    assert det.mid_candle_entry_forbidden is True


def test_governing_timeframe_is_the_highest_valid_one(cfg: Config) -> None:
    """**Q7** — CF-20's answer to S8-A3 flips: he trades the *highest* timeframe that validates.

    This test used to assert ``"trade_structure_tf"``, i.e. the SFP is judged on the trade's own
    structure timeframe and nowhere else.  S8 ``[00:23:06]`` is the counter-example the question
    was built from and he resolves it by behaviour: the same sweep is *"automatically a swing
    failure"* on the daily and *"not an SFP"* on the 12-hour, and he takes the daily one — *"on a
    lower time frame, you could definitely take that. But on the daily, it's a missed attempt"*
    (S7 ``[01:24:22]``).  Higher timeframe always takes precedence (S7 ``[00:21:45]``).

    The search is bounded: never below the trade timeframe, never more than one rung above the
    structure timeframe.  With no validation evidence supplied it degrades to the structure
    timeframe, which is the old behaviour.
    """
    assert cfg.sfp_governing_timeframe == "highest_valid"
    assert governing_timeframe(Timeframe.H4, cfg) is Timeframe.H4          # nothing to search

    # Structure on 12H, the SFP validates on the daily -> the daily governs (the S8 case).
    assert governing_timeframe(
        Timeframe.H12, cfg, trade_tf=Timeframe.H4,
        valid_timeframes=[Timeframe.H4, Timeframe.D1],
    ) is Timeframe.D1
    # ...and the 12H itself wins over a merely-4H validation.
    assert governing_timeframe(
        Timeframe.H12, cfg, trade_tf=Timeframe.H4,
        valid_timeframes=[Timeframe.H4, Timeframe.H12],
    ) is Timeframe.H12
    # Out of band above (2D is more than one rung above a 12H structure) -> ignored.
    assert governing_timeframe(
        Timeframe.H12, cfg, trade_tf=Timeframe.H4, valid_timeframes=[Timeframe.D2],
    ) is Timeframe.H12

    pinned = cfg.with_overrides(sfp_governing_timeframe="trade_structure_tf")
    assert governing_timeframe(
        Timeframe.H4, pinned, valid_timeframes=[Timeframe.D1]
    ) is Timeframe.H4
    assert governing_timeframe(Timeframe.H4, cfg.with_overrides(sfp_governing_timeframe="1D")) is Timeframe.D1


def test_the_raid_level_and_stop_are_wick_prices(cfg: Config, series: Series, swept_low) -> None:
    """**Q6 carve-out** — structure is bodies, but the SFP raid and its stop are wicks.

    ``swing_price_source = "body"`` is now sourced rather than [OUR CHOICE] (S7 ``[00:18:50]``,
    ``[01:10:48]``, ``[01:11:53]``, S5 ``[01:25:16]``), and the SFP is the object that does not
    follow it: *"swing high points are usually taken by wicks, not by bodies. Okay, but the candle
    body closes below the swing high point and this wick has taken out all of its liquidity."*
    (S7 ``[01:14:44]``).  ``sfp_raid_price_source`` records that carve-out; the SPEC did not.
    """
    assert cfg.swing_price_source == "body" and cfg.sfp_raid_price_source == "wick"
    assert raid_price(swept_low, cfg) == swept_low.wick_price
    assert raid_price(swept_low, cfg.with_overrides(sfp_raid_price_source="body")) == swept_low.price
    assert swept_low.wick_price != swept_low.price      # the carve-out is not a no-op here

    sfp = _accepted(series, cfg)[0]
    assert sfp.swept_price == swept_low.wick_price
    assert sfp.structure_price == swept_low.price
    # Long SFP: the stop sits below the raiding wick, i.e. below the wick-priced swept level.
    assert sfp.stop_price < sfp.swept_price


def test_baseline_series_yields_exactly_one_sfp(cfg: Config, series: Series, swept_low) -> None:
    sfps = _accepted(series, cfg)
    assert len(sfps) == 1
    sfp = sfps[0]
    assert sfp.direction is Direction.LONG
    assert sfp.bar_index == len(series) - 1
    assert sfp.swing_id == swept_low.id
    assert sfp.raid_extreme < sfp.swept_price       # the wick took the liquidity
    assert sfp.close_price > sfp.structure_price    # the body closed back inside
    assert "CF-20" in sfp.source_ids and "S7-R22" in sfp.source_ids


# --------------------------------------------------------------------------- filter 1: the close

def test_close_back_inside_is_accepted(cfg: Config, series: Series) -> None:
    assert _accepted(series, cfg)


def test_close_beyond_the_level_is_not_an_sfp(cfg: Config, swept_low) -> None:
    """S7-R23 / S8-R3: the candle closes beyond the level ⇒ no trade."""
    beyond = _sfp_series(raid_low=108.0, raid_close=111.0)
    swing = [p for p in P.swing_points(beyond, cfg) if p.kind is SwingKind.LOW][-1]
    assert dec(111.0) < swing.price
    assert find_sfps(beyond, cfg, levels=[_level_at(swing.wick_price, beyond)]) == []
    verdicts = evaluate(beyond, cfg, levels=[_level_at(swing.wick_price, beyond)])
    rejected = [v for v in verdicts if v.bar_index == len(beyond) - 1]
    assert rejected and not rejected[0].accepted
    assert any("S7-R23" in r for r in rejected[0].reasons)


# --------------------------------------------------------------------------- filter 2: no mid-candle entry

def test_entry_is_the_confirming_candles_close(cfg: Config, series: Series) -> None:
    """S7-R24 / CF-20: the reference price is the closed candle's close, never an intrabar price."""
    sfp = _accepted(series, cfg)[0]
    assert sfp.entry_index == sfp.bar_index
    assert sfp.entry_price == dec(series.close[sfp.bar_index])
    assert sfp.entry_price != sfp.raid_extreme
    assert sfp.entry_kind == "confirming_close"


def test_no_entry_before_the_candle_closes(cfg: Config, series: Series) -> None:
    """The raid alone is not tradeable: the candle can still close through (S7-R24).

    A series truncated to the bar *before* the raid emits nothing, and the same raid whose candle
    ends up closing beyond the level is rejected outright — which is why mid-candle entry is
    forbidden rather than merely discouraged.
    """
    truncated = series.head(len(series) - 1)
    assert _accepted(truncated, cfg) == []

    swing = [p for p in P.swing_points(series, cfg) if p.kind is SwingKind.LOW][-1]
    closed_through = _sfp_series(raid_low=108.0, raid_close=110.5)
    assert find_sfps(closed_through, cfg, levels=[_level_at(swing.wick_price, closed_through)]) == []


# --------------------------------------------------------------------------- filter 3: adjacency

def test_non_adjacent_raid_is_accepted(cfg: Config, series: Series) -> None:
    sfp = _accepted(series, cfg)[0]
    assert sfp.bars_between >= cfg.sfp_min_bars_between


def test_adjacent_raid_is_rejected(cfg: Config) -> None:
    """S7-R25: the SFP candle may not sit within ``sfp_min_bars_between`` bars of its swing."""
    strict = cfg.with_overrides(sfp_min_bars_between=50)
    swing_series = _sfp_series()
    swing = [p for p in P.swing_points(swing_series, cfg) if p.kind is SwingKind.LOW][-1]
    levels = [_level_at(swing.wick_price, swing_series)]
    assert find_sfps(swing_series, cfg, levels=levels)
    assert find_sfps(swing_series, strict, levels=levels) == []
    rejected = [
        v for v in evaluate(swing_series, strict, levels=levels)
        if v.bar_index == len(swing_series) - 1
    ]
    assert any("S7-R25" in r for r in rejected[0].reasons)


# --------------------------------------------------------------------------- filter 4: separation

def test_well_separated_swings_are_accepted(cfg: Config, series: Series) -> None:
    sfp = _accepted(series, cfg)[0]
    assert sfp.swing_separation_atr >= dec(cfg.sfp_min_swing_separation_atr)


def test_swings_too_close_together_are_rejected(cfg: Config, series: Series) -> None:
    """S7-R28 / S8-R4: near-equal swings give weak SFPs."""
    strict = cfg.with_overrides(sfp_min_swing_separation_atr=100.0)
    swing = [p for p in P.swing_points(series, cfg) if p.kind is SwingKind.LOW][-1]
    levels = [_level_at(swing.wick_price, series)]
    assert find_sfps(series, strict, levels=levels) == []
    rejected = [v for v in evaluate(series, strict, levels=levels) if v.bar_index == len(series) - 1]
    assert any("S7-R28" in r for r in rejected[0].reasons)


def test_equal_swing_highs_are_zero_separation(cfg: Config) -> None:
    """The synthetic's range prints equal highs — separation 0 ATR, correctly rejected."""
    syn = synthetic(seed=7)
    verdicts = evaluate(syn.series, cfg)
    weak = [v for v in verdicts if any("S7-R28" in r for r in v.reasons)]
    assert weak, "equal-high raids inside the range must fail the separation filter"


# --------------------------------------------------------------------------- filter 5: trend veto

def test_with_trend_sfp_is_accepted(cfg: Config, series: Series) -> None:
    assert cfg.sfp_trend_veto is True
    sfp = _accepted(series, cfg, trend=Trend.UP)[0]
    assert sfp.direction is Direction.LONG and sfp.trend is Trend.UP


def test_counter_trend_sfp_is_vetoed(cfg: Config, series: Series) -> None:
    """S7-R31: do not take an SFP against the prevailing trend."""
    swing = [p for p in P.swing_points(series, cfg) if p.kind is SwingKind.LOW][-1]
    levels = [_level_at(swing.wick_price, series)]
    assert find_sfps(series, cfg, levels=levels, trend=Trend.DOWN) == []
    rejected = [
        v for v in evaluate(series, cfg, levels=levels, trend=Trend.DOWN)
        if v.bar_index == len(series) - 1
    ]
    assert any("S7-R31" in r for r in rejected[0].reasons)
    # turning the veto off lets it through again
    assert find_sfps(series, cfg.with_overrides(sfp_trend_veto=False), levels=levels, trend=Trend.DOWN)


# --------------------------------------------------------------------------- filter 6: pre-marked level/zone

def test_sfp_at_a_pre_marked_level_is_accepted(cfg: Config, series: Series, swept_low) -> None:
    sfps = find_sfps(series, cfg, levels=[_level_at(swept_low.wick_price, series)])
    assert sfps and sfps[0].level_ids == ("pre-marked-level",)


def test_sfp_at_a_pre_marked_zone_is_accepted(cfg: Config, series: Series, swept_low) -> None:
    sfps = find_sfps(series, cfg, zones=[_zone_at(swept_low.wick_price, series)])
    assert sfps and sfps[0].zone_ids == ("pre-marked-zone",)


def test_sfp_with_nothing_pre_marked_is_banned(cfg: Config, series: Series) -> None:
    """S7-R30 / CF-20: ``sfp_standalone_enabled`` is false, so a bare SFP is not a trade."""
    assert cfg.sfp_standalone_enabled is False
    assert find_sfps(series, cfg) == []
    rejected = [v for v in evaluate(series, cfg) if v.bar_index == len(series) - 1]
    assert any("S7-R30" in r for r in rejected[0].reasons)


def test_a_level_at_the_wrong_price_does_not_count(cfg: Config, series: Series, swept_low) -> None:
    far = _level_at(swept_low.wick_price + dec(25), series)
    assert find_sfps(series, cfg, levels=[far]) == []


def test_standalone_mode_lifts_the_ban(cfg: Config, series: Series) -> None:
    """The flag exists only to backtest S7-C5's claim, which he immediately advises against."""
    standalone = cfg.with_overrides(sfp_standalone_enabled=True)
    assert find_sfps(series, standalone)


# --------------------------------------------------------------------------- filter 7: deep wick / chase cap

def test_close_near_the_swept_level_allows_the_market_entry(cfg: Config, series: Series) -> None:
    sfp = _accepted(series, cfg)[0]
    assert sfp.close_distance_atr <= dec(cfg.sfp_max_close_distance_atr)
    assert sfp.chase_allowed is True
    assert sfp.entry_kind == "confirming_close"
    assert sfp.reasons == ()


def test_deep_wick_bans_the_chase_and_rests_a_limit(cfg: Config, series: Series, swept_low) -> None:
    """S5-R7: a confirming close far from the swept level bans the market entry.

    CF-20's missed-entry rule then applies — rest a limit at the prior swing point with the same
    wick stop (S5-R6, S7-R27, S8-R6) — so the record survives with a different entry mechanic.
    """
    tight = cfg.with_overrides(sfp_max_close_distance_atr=0.01)
    sfps = find_sfps(series, tight, levels=[_level_at(swept_low.wick_price, series)])
    assert sfps
    sfp = sfps[0]
    assert sfp.chase_allowed is False
    assert sfp.entry_kind == "limit_at_swept_level"
    assert sfp.entry_price == sfp.swept_price
    assert any("sfp_max_close_distance_atr" in r for r in sfp.reasons)
    assert "S5-R7" in sfp.source_ids and "S7-R27" in sfp.source_ids


def test_deep_wick_threshold_is_measured_in_atr(cfg: Config, series: Series, swept_low) -> None:
    sfp = _accepted(series, cfg)[0]
    atr = P.atr_at(series, cfg, sfp.bar_index)
    expected = abs(sfp.close_price - sfp.swept_price) / atr
    assert sfp.close_distance_atr == expected


# --------------------------------------------------------------------------- stop

def test_stop_sits_beyond_the_raiding_wick(cfg: Config, series: Series) -> None:
    sfp = _accepted(series, cfg)[0]
    assert sfp.stop_price < sfp.raid_extreme          # long: stop below the wick
    buffer = P.stop_buffer(series, cfg, sfp.bar_index)
    assert sfp.stop_price == P.apply_stop_buffer(sfp.raid_extreme, Direction.LONG, buffer)
    assert sfp.stop_pct > 0


# --------------------------------------------------------------------------- bearish mirror

def test_bearish_sfp_raids_a_swing_high(cfg: Config) -> None:
    """S7-R21: the wick takes out a prior swing high and the body closes back below it."""
    syn = synthetic(seed=7)
    series, features = syn.series, syn.features
    swing = next(
        p for p in P.swing_points(series, cfg)
        if p.kind is SwingKind.HIGH and p.bar_index == features.sfp_swing_index
    )
    levels = [_level_at(swing.wick_price, series)]
    sfps = find_sfps(series, cfg, levels=levels, trend=Trend.NEUTRAL)
    assert [s.bar_index for s in sfps] == [features.sfp_index]
    sfp = sfps[0]
    assert sfp.direction is Direction.SHORT
    assert sfp.raid_extreme > sfp.swept_price
    assert sfp.close_price < sfp.structure_price
    assert sfp.stop_price > sfp.raid_extreme


def test_synthetic_sfp_close_ran_too_far_to_chase(cfg: Config) -> None:
    """The embedded swing failure closes ~5 ATR from the swept level: limit, not market."""
    syn = synthetic(seed=7)
    swing = next(
        p for p in P.swing_points(syn.series, cfg)
        if p.kind is SwingKind.HIGH and p.bar_index == syn.features.sfp_swing_index
    )
    sfp = find_sfps(
        syn.series, cfg, levels=[_level_at(swing.wick_price, syn.series)], trend=Trend.NEUTRAL
    )[0]
    assert sfp.close_distance_atr > dec(cfg.sfp_max_close_distance_atr)
    assert sfp.entry_kind == "limit_at_swept_level"


# --------------------------------------------------------------------------- hygiene

def test_raid_candidates_are_geometry_only(cfg: Config, series: Series) -> None:
    candidates = raid_candidates(series, cfg)
    assert any(i == len(series) - 1 for i, _, _ in candidates)
    for bar_index, swing, _ in candidates:
        assert swing.confirmed_at_index <= bar_index
        assert swing.bar_index < bar_index


def test_detect_is_deterministic(cfg: Config, series: Series, swept_low) -> None:
    det = SFPDetector()
    levels = [_level_at(swept_low.wick_price, series)]
    first = [s.id for s in det.detect(series, cfg, levels=levels)]
    second = [s.id for s in det.detect(series, cfg, levels=levels)]
    assert first == second == ["TEST:1H:sfp:%d" % (len(series) - 1)]


def test_every_sfp_carries_source_ids(cfg: Config, series: Series) -> None:
    for sfp in _accepted(series, cfg):
        assert sfp.source_ids
        assert sfp.id.startswith("TEST:1H:sfp:")


def test_to_confluence_scores_at_the_swept_level(cfg: Config, series: Series) -> None:
    det = SFPDetector()
    sfps = _accepted(series, cfg)
    scored = det.to_confluence(sfps, cfg)
    assert [o.obj_class for o in scored] == ["sfp"]
    assert scored[0].price == sfps[0].swept_price
    assert scored[0].source_ids == sfps[0].source_ids


def test_no_lookahead(cfg: Config, series: Series, swept_low) -> None:
    """The SFP on bar i is visible on bar i and never before it."""
    levels = [_level_at(swept_low.wick_price, series)]
    last = len(series) - 1
    assert find_sfps(series.head(last), cfg, levels=levels) == []
    assert [s.bar_index for s in find_sfps(series.head(last + 1), cfg, levels=levels)] == [last]
