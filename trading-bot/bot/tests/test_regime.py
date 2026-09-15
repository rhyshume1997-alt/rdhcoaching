"""Contract tests for tbot.regime (SPEC.md §7.2, CF-35, S3, TBOT1 §10).

Context charts are built by hand and levels are injected as :class:`~tbot.regime.LevelRead`\\ s,
so these tests pin the *reading* rules rather than the level detector's behaviour.  Constant true
range 1.0 ⇒ ``ATR == 1.0`` and the P9 tolerance band is exactly ``level_tolerance_atr`` (0.15).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tbot.config import Config
from tbot.models import Direction, Series, Timeframe, Trend, Vehicle, dec
from tbot.regime import (
    AllPairsRefs,
    BvolEvent,
    LevelRead,
    bvol_event,
    context_stack,
    evaluate_regime,
    is_dominance_symbol,
    levels_from_series,
    normalise_symbol,
    read_context_chart,
)
import tbot.primitives as P

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_series(rows, tf: str = "1H", symbol: str = "T", start: datetime = T0) -> Series:
    step = timedelta(minutes=Timeframe.parse(tf).minutes)
    idx = [start + i * step for i in range(len(rows))]
    return Series.from_arrays(
        idx,
        [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows],
        volume=[1.0] * len(rows), tf=tf, symbol=symbol,
    )


def flat_bars(n: int, price: float = 100.0):
    return [(price, price + 0.5, price - 0.5, price)] * n


def flat_series(price: float = 100.0, n: int = 60, tf: str = "1H", symbol: str = "T") -> Series:
    """A chart whose last close sits exactly at ``price``."""
    return make_series(flat_bars(n, price), tf=tf, symbol=symbol)


def zigzag(turns, bars_per_leg: int = 4):
    """Bars tracing a polyline through ``turns`` — enough shape for P1 to find pivots."""
    rows = []
    for start, stop in zip(turns, turns[1:]):
        for step in range(bars_per_leg):
            o = start + (stop - start) * step / bars_per_leg
            c = start + (stop - start) * (step + 1) / bars_per_leg
            rows.append((o, max(o, c) + 0.1, min(o, c) - 0.1, c))
    return rows


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


def resistance_at(price: float) -> list[LevelRead]:
    return [LevelRead(price=dec(price), role="resistance", touches=3, level_id="R1")]


def support_at(price: float) -> list[LevelRead]:
    return [LevelRead(price=dec(price), role="support", touches=3, level_id="S1")]


# =========================================================================== scope


class TestDominanceScope:
    def test_only_the_two_dominance_tickers_read_inverted(self):
        assert is_dominance_symbol("USDT.D") is True
        assert is_dominance_symbol("BTC.D") is True
        assert is_dominance_symbol("BTCUSDT") is False
        assert is_dominance_symbol("SOLUSDT") is False
        assert is_dominance_symbol("DXY") is False
        assert is_dominance_symbol("BVOL") is False

    def test_exchange_prefixes_and_case_are_normalised(self):
        assert normalise_symbol("CRYPTOCAP:usdt.d") == "USDT.D"
        assert is_dominance_symbol("cryptocap:btc.d") is True


class TestInvertedReads:
    def test_usdt_dominance_at_resistance_is_risk_on(self, cfg):
        read = read_context_chart(
            "USDT.D", flat_series(100.0, symbol="USDT.D"), cfg, levels=resistance_at(100.0)
        )
        assert read.inverted is True and read.at_resistance is True
        assert read.risk_on is True            # inverted: alts bid when USDT.D stalls

    def test_usdt_dominance_at_support_is_risk_off(self, cfg):
        read = read_context_chart(
            "USDT.D", flat_series(100.0, symbol="USDT.D"), cfg, levels=support_at(100.0)
        )
        assert read.at_support is True and read.risk_on is False
        assert read.adverse is True

    def test_btc_dominance_inverts_too(self, cfg):
        read = read_context_chart(
            "BTC.D", flat_series(60.0, symbol="BTC.D"), cfg, levels=resistance_at(60.0)
        )
        assert read.inverted is True and read.risk_on is True

    def test_inversion_is_not_applied_to_a_normal_symbol(self, cfg):
        """S3-C4: the inverse read is scoped to the dominance charts, never to a price chart."""
        read = read_context_chart(
            "SOLUSDT", flat_series(100.0, symbol="SOLUSDT"), cfg, levels=resistance_at(100.0)
        )
        assert read.inverted is False
        assert read.at_resistance is True
        assert read.risk_on is False           # normal TA: resistance is not a buy

        at_support = read_context_chart(
            "SOLUSDT", flat_series(100.0, symbol="SOLUSDT"), cfg, levels=support_at(100.0)
        )
        assert at_support.inverted is False and at_support.risk_on is True

    def test_btc_itself_is_a_price_chart_not_a_dominance_chart(self, cfg):
        read = read_context_chart(
            "BTCUSDT", flat_series(100.0, symbol="BTCUSDT"), cfg, levels=resistance_at(100.0)
        )
        assert read.inverted is False and read.risk_on is False

    def test_price_outside_the_tolerance_band_gives_no_read(self, cfg):
        read = read_context_chart(
            "USDT.D", flat_series(100.0, symbol="USDT.D"), cfg, levels=resistance_at(104.0)
        )
        assert read.at_resistance is False and read.at_support is False
        assert read.risk_on is None

    def test_levels_can_be_derived_from_the_series_when_not_injected(self, cfg):
        series = make_series(zigzag([100, 104, 100, 104, 100, 104, 100]), symbol="USDT.D")
        derived = levels_from_series(series, cfg)
        assert derived, "expected P1+P3 to find at least one cluster"
        read = read_context_chart("USDT.D", series, cfg)
        assert read.available is True


# =========================================================================== degradation


class TestMissingContext:
    def test_absent_symbol_degrades_to_neutral_and_says_so(self, cfg):
        read = read_context_chart("USDT.D", None, cfg)
        assert read.available is False and read.risk_on is None
        assert any("degraded to neutral" in n for n in read.notes)

    def test_empty_context_mapping_is_neutral_never_risk_on(self, cfg):
        state = evaluate_regime({}, cfg, direction=Direction.LONG)
        assert state.state == "neutral"
        assert state.risk_on is False
        assert state.hard_veto is False
        assert state.blocks_new_alt_longs is False
        assert state.size_multiplier == Decimal(1)
        assert state.degraded is True
        assert set(state.missing) == {"USDT.D", "BTC.D", "BVOL"}
        assert any("absent from context" in n for n in state.notes)

    def test_one_missing_chart_still_reads_the_others(self, cfg):
        context = {"BTC.D": flat_series(60.0, symbol="BTC.D")}
        state = evaluate_regime(
            context, cfg, levels={"BTC.D": resistance_at(60.0)}, direction=Direction.LONG
        )
        assert "USDT.D" in state.missing and state.degraded is True
        assert state.state == "risk_on"            # BTC.D at resistance, inverted
        assert state.flags["decided_by"] == "BTC.D"


# =========================================================================== priority


class TestPriorityStack:
    def test_default_stack_omits_dxy(self, cfg):
        assert context_stack(cfg) == ("USDT.D", "BTC.D", "BVOL")

    def test_enabling_dxy_restores_the_s3_r11_order(self, cfg):
        enabled = cfg.with_overrides(dxy_gate_enabled=True)
        assert context_stack(enabled) == ("USDT.D", "DXY", "BTC.D", "BVOL")

    def test_higher_priority_chart_decides_the_state(self, cfg):
        context = {
            "USDT.D": flat_series(100.0, symbol="USDT.D"),
            "BTC.D": flat_series(60.0, symbol="BTC.D"),
        }
        levels = {"USDT.D": support_at(100.0), "BTC.D": resistance_at(60.0)}
        state = evaluate_regime(context, cfg, levels=levels, direction=Direction.LONG)
        assert state.flags["decided_by"] == "USDT.D"
        assert state.state == "risk_off"           # USDT.D at support wins over BTC.D
        assert state.blocks_new_alt_longs is True

    def test_disabled_dxy_is_ignored_even_when_supplied(self, cfg):
        context = {
            "USDT.D": flat_series(100.0, symbol="USDT.D"),
            "DXY": flat_series(105.0, symbol="DXY"),
        }
        state = evaluate_regime(context, cfg, levels={"USDT.D": resistance_at(100.0)})
        assert all(r.symbol != "DXY" for r in state.reads)
        assert any("dxy_gate_enabled is false" in n for n in state.notes)


# =========================================================================== BVOL


class TestBvol:
    def _bvol(self, values, start: datetime = T0) -> Series:
        rows = [(v, v + 0.02, v - 0.02, v) for v in values]
        return make_series(rows, tf="1D", symbol="BVOL", start=start)

    def test_zone_touch_raises_the_event_flag(self, cfg):
        series = self._bvol([0.6, 0.7, 0.85, 0.9])
        event = bvol_event(series, cfg)
        assert event.active is True
        assert event.triggered_index == 3
        assert event.zone_low == dec(0.81) and event.zone_high == dec(1.4)
        assert event.window_hours == 72

    def test_no_touch_means_no_event(self, cfg):
        event = bvol_event(self._bvol([0.5, 0.6, 0.7]), cfg)
        assert event.active is False and event.triggered_index is None

    def test_the_window_expires_after_bvol_event_window_hours(self, cfg):
        series = self._bvol([0.9, 0.5, 0.5, 0.5, 0.5, 0.5])
        inside = bvol_event(series, cfg, now=T0 + timedelta(hours=71))
        outside = bvol_event(series, cfg, now=T0 + timedelta(hours=73))
        assert inside.active is True and inside.hours_remaining > 0
        assert outside.active is False and outside.hours_remaining == Decimal(0)

    def test_the_event_carries_no_direction(self, cfg):
        """S3-R3: it predicts a large move; which way is explicitly unpredictable."""
        event = bvol_event(self._bvol([0.9]), cfg)
        assert not hasattr(event, "direction")
        assert isinstance(event, BvolEvent)

    def test_event_halves_leverage_size_and_leaves_spot_alone(self, cfg):
        context = {"BVOL": self._bvol([0.6, 0.9])}
        state = evaluate_regime(context, cfg)
        assert state.bvol.active is True
        assert state.size_multiplier == dec(cfg.bvol_size_multiplier)
        assert state.multiplier_for(Vehicle.LEVERAGE) == dec(0.5)
        assert state.multiplier_for(Vehicle.SPOT) == Decimal(1)
        assert state.adverse is True and state.hard_veto is False

    def test_missing_bvol_degrades_the_flag_to_off(self, cfg):
        state = evaluate_regime({"USDT.D": flat_series(100.0, symbol="USDT.D")}, cfg)
        assert state.bvol.active is False
        assert "BVOL" in state.missing
        assert state.size_multiplier == Decimal(1)

    def test_a_non_daily_bvol_series_is_flagged_not_silently_accepted(self, cfg):
        rows = [(0.9, 0.92, 0.88, 0.9)] * 3
        event = bvol_event(make_series(rows, tf="4H", symbol="BVOL"), cfg)
        assert any("daily-only" in n for n in event.notes)


# =========================================================================== vetoes


class TestVetoes:
    def test_all_pairs_at_resistance_hard_vetoes_longs(self, cfg):
        context = {
            "SOLUSDT": flat_series(100.0, symbol="SOLUSDT"),
            "SOLBTC": flat_series(0.002, symbol="SOLBTC"),
            "BTCUSDT": flat_series(60000.0, symbol="BTCUSDT"),
        }
        levels = {
            "SOLUSDT": resistance_at(100.0),
            "SOLBTC": [LevelRead(price=dec(0.002), role="resistance")],
            "BTCUSDT": resistance_at(60000.0),
        }
        state = evaluate_regime(
            context, cfg, levels=levels, direction=Direction.LONG,
            all_pairs=AllPairsRefs("SOLUSDT", "SOLBTC", "BTCUSDT"),
        )
        assert state.hard_veto is True
        assert state.veto_reasons == ("all_pairs_at_resistance",)

    def test_all_pairs_veto_does_not_fire_on_shorts(self, cfg):
        context = {
            "SOLUSDT": flat_series(100.0, symbol="SOLUSDT"),
            "SOLBTC": flat_series(0.002, symbol="SOLBTC"),
            "BTCUSDT": flat_series(60000.0, symbol="BTCUSDT"),
        }
        levels = {
            "SOLUSDT": resistance_at(100.0),
            "SOLBTC": [LevelRead(price=dec(0.002), role="resistance")],
            "BTCUSDT": resistance_at(60000.0),
        }
        state = evaluate_regime(
            context, cfg, levels=levels, direction=Direction.SHORT,
            all_pairs=AllPairsRefs("SOLUSDT", "SOLBTC", "BTCUSDT"),
        )
        assert state.hard_veto is False

    def test_all_pairs_veto_is_not_evaluable_without_every_chart(self, cfg):
        context = {"SOLUSDT": flat_series(100.0, symbol="SOLUSDT")}
        state = evaluate_regime(
            context, cfg, levels={"SOLUSDT": resistance_at(100.0)}, direction=Direction.LONG,
            all_pairs=AllPairsRefs("SOLUSDT", "SOLBTC", "BTCUSDT"),
        )
        assert state.hard_veto is False
        assert any("not evaluable" in n for n in state.notes)

    def test_both_dominance_charts_trending_up_is_risk_off_on_alts(self, cfg):
        rising = zigzag([100, 104, 101, 106, 103, 109, 106, 112])
        context = {
            "USDT.D": make_series(rising, symbol="USDT.D"),
            "BTC.D": make_series(rising, symbol="BTC.D"),
        }
        usdt_trend = P.classify_trend(
            P.swing_points(context["USDT.D"], cfg), cfg, at_index=len(context["USDT.D"]) - 1
        )
        assert usdt_trend is Trend.UP, "fixture must trend up for TBOT1-R19"
        state = evaluate_regime(context, cfg, direction=Direction.LONG)
        assert state.state == "risk_off"
        assert state.blocks_new_alt_longs is True
        assert any("TBOT1-R19" in n for n in state.notes)

    def test_beta_parent_adverse_blocks_the_child(self, cfg):
        context = {
            "USDT.D": flat_series(100.0, symbol="USDT.D"),
            "SOLUSDT": flat_series(100.0, symbol="SOLUSDT"),
        }
        levels = {"USDT.D": resistance_at(100.0), "SOLUSDT": resistance_at(100.0)}
        state = evaluate_regime(
            context, cfg, levels=levels, direction=Direction.LONG, beta_parent="SOLUSDT"
        )
        assert state.hard_veto is True
        assert state.veto_reasons == ("beta_parent_adverse",)

    def test_context_never_contributes_a_score(self, cfg):
        """PL-6 / CF-35: the layer emits a gate and a multiplier, never a priced object."""
        state = evaluate_regime({"USDT.D": flat_series(100.0, symbol="USDT.D")}, cfg)
        assert not hasattr(state, "score")
        assert not hasattr(state, "weight")

    def test_evaluation_is_deterministic(self, cfg):
        context = {"USDT.D": flat_series(100.0, symbol="USDT.D")}
        levels = {"USDT.D": resistance_at(100.0)}
        first = evaluate_regime(context, cfg, levels=levels)
        second = evaluate_regime(context, cfg, levels=levels)
        assert first.state == second.state and first.notes == second.notes
        assert first.size_multiplier == second.size_multiplier


# ------------------------------- A1: rolling_correlation date alignment (GAPS.md GAP 3 A1)


def _cosine_closes(n: int, period: int = 8, base: float = 100.0, amp: float = 5.0):
    import math
    return [base + amp * math.cos(2 * math.pi * i / period) for i in range(n)]


def _from_closes(closes, *, symbol: str, start: datetime, tf: str = "1H") -> Series:
    return make_series([(c, c + 0.1, c - 0.1, c) for c in closes],
                       tf=tf, symbol=symbol, start=start)


def test_rolling_correlation_refuses_misaligned_windows():
    """Two series whose positional tails cover different DATES must not be correlated.

    ``rolling_correlation`` took ``a.close[-n:]`` against ``b.close[-n:]`` with no check that
    the two windows describe the same instants. A symbol that listed later, or one with a data
    gap, therefore correlated bar-against-bar at a date offset.

    This is not an approximation error. Here ``b`` carries *exactly* ``a``'s closes stamped 20
    bars later; the price path is a cosine of period 8, so a 20-bar offset is half a period.
    The positional read is +1.0 and the truth over the real overlap is -1.0 -- the sign
    inverts. A gate fed that number does the opposite of what it was asked to do, and
    ``max_correlated_concurrent`` (GAPS.md GAP 2) is built directly on it.

    **Chosen behaviour: return None when the windows cannot be shown to cover the same
    timestamps.** Fail closed. A correlation is a number a gate acts on, and there is no
    conservative direction to round a wrong one towards -- so refusing to answer is the only
    safe answer. Returning None is already this function's documented "not enough overlap"
    signal (CF-35) and every caller handles it. Teaching it to *align* rather than refuse is a
    capability increase, and it lands next, as its own tested unit.
    """
    closes = _cosine_closes(40)
    step = timedelta(minutes=Timeframe.parse("1H").minutes)
    a = _from_closes(closes, symbol="A", start=T0)
    b = _from_closes(closes, symbol="B", start=T0 + 20 * step)   # same path, 20 bars later

    assert a.timestamp(-1) != b.timestamp(-1), "the fixture must actually be misaligned"
    assert P is not None  # keep the import used

    from tbot.regime import rolling_correlation
    assert rolling_correlation(a, b, lookback_bars=90) is None, (
        "misaligned windows were correlated as if they lined up")


def test_rolling_correlation_still_answers_for_aligned_series():
    """The fix must not silence the aligned case it already handled correctly."""
    from tbot.regime import rolling_correlation

    rising = _from_closes([100.0 + i for i in range(40)], symbol="A", start=T0)
    also = _from_closes([50.0 + 0.5 * i for i in range(40)], symbol="B", start=T0)
    corr = rolling_correlation(rising, also, lookback_bars=90)
    assert corr is not None and float(corr) == pytest.approx(1.0, abs=1e-9)


def test_rolling_correlation_uses_the_common_tail_when_lengths_differ():
    """Different lengths but a shared, aligned tail is legitimate and must still answer."""
    from tbot.regime import rolling_correlation

    long_ = _from_closes([100.0 + i for i in range(60)], symbol="A", start=T0)
    step = timedelta(minutes=Timeframe.parse("1H").minutes)
    # starts later, but every bar it does have lines up with long_'s, and both end together
    short = _from_closes([50.0 + 0.5 * (i + 20) for i in range(40)], symbol="B",
                         start=T0 + 20 * step)
    assert long_.timestamp(-1) == short.timestamp(-1)
    corr = rolling_correlation(long_, short, lookback_bars=90)
    assert corr is not None and float(corr) == pytest.approx(1.0, abs=1e-9)
