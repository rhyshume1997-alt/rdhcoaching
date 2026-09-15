"""tbot.backtest.metrics — the SPEC.md §12.4 metric set and the §12.5 treatment of the claim.

Everything here is computed from :class:`~tbot.backtest.engine.ClosedTrade` records whose P&L is
already **net of fees, slippage and funding** (§12.3: "no metric may be reported gross").

The metric set itself is **[OUR CHOICE]** — SPEC.md §12.4 says so plainly: the corpus contains no
performance framework beyond a manual win-rate field in a trade log (S2-A24).

§12.5 governs the 77–82 % figure.  It is a **hypothesis this harness exists to test**, never a
target:

* it is printed as a claim, with the measured value and the sample size beside it;
* nothing in this module (or anywhere else in the package) feeds it into sizing, expectancy,
  Kelly or capacity;
* a small sample is reported as "cannot conclude", not rounded toward the claim;
* a measured win rate materially below the claim is a **result**.  It must not trigger parameter
  fitting toward the claim.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from ..models import Timeframe, dec
from .engine import BacktestResult, ClosedTrade, EquityPoint, RejectionRecord

__all__ = [
    "CLAIM_LOW_PCT",
    "CLAIM_HIGH_PCT",
    "MIN_SAMPLE_FOR_CONCLUSION",
    "BREAKEVEN_R_EPSILON",
    "WinRates",
    "RDistribution",
    "Drawdown",
    "Bucket",
    "Attribution",
    "FillQuality",
    "TimeInMarket",
    "ClaimComparison",
    "MetricsReport",
    "compute_metrics",
]

ZERO = Decimal(0)
HUNDRED = Decimal(100)

#: SPEC.md §12.5 — S5 ``[00:38:20]`` / ``[01:15:40]``.  A claim under test, never a target.
CLAIM_LOW_PCT = Decimal("77.0")
CLAIM_HIGH_PCT = Decimal("82.0")

#: Below this many closed trades no win-rate comparison is reported as conclusive.
#: **[OUR CHOICE]** — the corpus gives no sample size at all (CONFLICTS.md: "no sample").
MIN_SAMPLE_FOR_CONCLUSION = 30

#: |R| under which an exit is booked as *break-even* rather than a win or a loss.
#: **[OUR CHOICE]** — S5-A19 flags that "a win" is undefined in the corpus.
BREAKEVEN_R_EPSILON = Decimal("0.05")

_Z95 = 1.959963984540054


# --------------------------------------------------------------------------- small helpers


def _pct(part: int, whole: int) -> Decimal:
    return (Decimal(part) * HUNDRED / Decimal(whole)) if whole else ZERO


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, ZERO) / Decimal(len(values)) if values else ZERO


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile on an already-sorted list (deterministic, no numpy)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def _wilson(successes: int, trials: int, z: float = _Z95) -> tuple[Decimal, Decimal]:
    """Wilson score interval, in percent.  Honest at small n, which is the whole point here."""
    if trials <= 0:
        return ZERO, HUNDRED
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    lo = max(0.0, centre - spread) * 100
    hi = min(1.0, centre + spread) * 100
    return dec(round(lo, 4)), dec(round(hi, 4))


def _classify(trade: ClosedTrade) -> str:
    """``win`` / ``loss`` / ``breakeven`` under the §12.4 primary definition (net of fees)."""
    if abs(trade.r_multiple) <= BREAKEVEN_R_EPSILON:
        return "breakeven"
    return "win" if trade.net_pnl_usd > ZERO else "loss"


# --------------------------------------------------------------------------- metric records


@dataclass(frozen=True, slots=True)
class WinRates:
    """The three win definitions §12.4/§12.5 require, side by side, with their counts.

    ``net_positive_pct`` is the headline definition: closed trades with realised P&L > 0, net of
    fees, over all closed trades.  One plan is **one** trade — a TP1 hit with the residual trailed
    out at break-even is a single record, and a trail-out after TP2 is a win (§12.4, CF-29).
    """

    trades: int
    wins: int
    losses: int
    breakevens: int
    full_ladder_completions: int
    net_positive_pct: Decimal
    full_ladder_pct: Decimal
    excluding_breakeven_pct: Decimal

    @classmethod
    def of(cls, trades: Sequence[ClosedTrade]) -> "WinRates":
        buckets = Counter(_classify(t) for t in trades)
        wins, losses, evens = buckets["win"], buckets["loss"], buckets["breakeven"]
        total = len(trades)
        full = sum(1 for t in trades if t.full_ladder)
        decided = wins + losses
        return cls(
            trades=total, wins=wins, losses=losses, breakevens=evens,
            full_ladder_completions=full,
            net_positive_pct=_pct(wins, total),
            full_ladder_pct=_pct(full, total),
            excluding_breakeven_pct=_pct(wins, decided),
        )


@dataclass(frozen=True, slots=True)
class RDistribution:
    """R-multiple distribution (§12.4).  R is measured from ``average_entry`` against the **initial**
    stop (CF-42, CF-18), so slippage and gaps genuinely can produce outcomes worse than −1R."""

    count: int
    mean: Decimal
    p5: Decimal
    p25: Decimal
    median: Decimal
    p75: Decimal
    p95: Decimal
    worse_than_minus_1r: int
    histogram: tuple[tuple[str, int], ...]

    #: Fixed bin edges keep the histogram comparable across runs.  **[OUR CHOICE]**
    EDGES = (-3.0, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0)

    @classmethod
    def of(cls, trades: Sequence[ClosedTrade]) -> "RDistribution":
        values = sorted(float(t.r_multiple) for t in trades)
        counts: list[tuple[str, int]] = []
        edges = cls.EDGES
        labels = [f"< {edges[0]:+.1f}"]
        labels += [f"[{edges[k]:+.1f}, {edges[k + 1]:+.1f})" for k in range(len(edges) - 1)]
        labels.append(f">= {edges[-1]:+.1f}")
        tally = [0] * len(labels)
        for v in values:
            if v < edges[0]:
                tally[0] += 1
            elif v >= edges[-1]:
                tally[-1] += 1
            else:
                for k in range(len(edges) - 1):
                    if edges[k] <= v < edges[k + 1]:
                        tally[k + 1] += 1
                        break
        counts = tuple(zip(labels, tally))
        return cls(
            count=len(values),
            mean=_mean([t.r_multiple for t in trades]),
            p5=dec(round(_percentile(values, 0.05), 6)),
            p25=dec(round(_percentile(values, 0.25), 6)),
            median=dec(round(_percentile(values, 0.50), 6)),
            p75=dec(round(_percentile(values, 0.75), 6)),
            p95=dec(round(_percentile(values, 0.95), 6)),
            worse_than_minus_1r=sum(1 for v in values if v < -1.0),
            histogram=counts,
        )


@dataclass(frozen=True, slots=True)
class Drawdown:
    """Peak-to-trough on an equity curve, in % and in USD (§12.4)."""

    max_pct: Decimal
    max_usd: Decimal
    peak_index: int
    trough_index: int
    peak_equity: Decimal
    trough_equity: Decimal

    @classmethod
    def of(cls, points: Sequence[tuple[int, Decimal]]) -> "Drawdown":
        peak = None
        peak_i = trough_i = 0
        best_usd = ZERO
        best_pct = ZERO
        best_peak = best_trough = ZERO
        current_peak_i = 0
        for index, equity in points:
            if peak is None or equity > peak:
                peak, current_peak_i = equity, index
            if peak is None:
                continue
            drop = peak - equity
            if drop > best_usd:
                best_usd = drop
                best_pct = (drop * HUNDRED / peak) if peak != ZERO else ZERO
                peak_i, trough_i = current_peak_i, index
                best_peak, best_trough = peak, equity
        return cls(max_pct=best_pct, max_usd=best_usd, peak_index=peak_i, trough_index=trough_i,
                   peak_equity=best_peak, trough_equity=best_trough)


@dataclass(frozen=True, slots=True)
class Bucket:
    """Count / win rate / expectancy / total R for one slice of the trade population."""

    label: str
    trades: int
    wins: int
    win_rate_pct: Decimal
    expectancy_r: Decimal
    total_r: Decimal
    net_pnl_usd: Decimal

    @classmethod
    def of(cls, label: str, trades: Sequence[ClosedTrade]) -> "Bucket":
        wins = sum(1 for t in trades if _classify(t) == "win")
        rs = [t.r_multiple for t in trades]
        return cls(label=label, trades=len(trades), wins=wins,
                   win_rate_pct=_pct(wins, len(trades)), expectancy_r=_mean(rs),
                   total_r=sum(rs, ZERO),
                   net_pnl_usd=sum((t.net_pnl_usd for t in trades), ZERO))


@dataclass(frozen=True, slots=True)
class Attribution:
    """Per-detector attribution (§12.4).

    ``primary`` buckets trades by the **anchoring** object class.  ``marginal`` counts the trades
    where a class was present in the confluence stack but was *not* the anchor — its marginal
    contribution as a confluence member (CF-31, CF-37: disowned modules still score).
    """

    primary: tuple[Bucket, ...]
    marginal: tuple[Bucket, ...]


@dataclass(frozen=True, slots=True)
class FillQuality:
    """Rung fill rate per ladder position and the realised-vs-planned entry gap (§12.4, A7)."""

    rung_fill_rate_pct: tuple[Decimal, ...]
    rung_offered: tuple[int, ...]
    rung_filled: tuple[int, ...]
    mean_entry_slippage: Decimal
    mean_entry_slippage_bps: Decimal
    trades_with_partial_ladder: int


@dataclass(frozen=True, slots=True)
class TimeInMarket:
    """Bars in trade by class, and the same figure in hours for the series' timeframe (§12.4)."""

    tf: Timeframe
    median_bars: Decimal
    mean_bars: Decimal
    median_hours: Decimal
    by_class: tuple[tuple[str, Decimal, Decimal], ...]  # (class, median bars, median hours)


@dataclass(frozen=True, slots=True)
class ClaimComparison:
    """SPEC.md §12.5 — the 77–82 % claim stated as a hypothesis, measured beside it."""

    claim_low_pct: Decimal
    claim_high_pct: Decimal
    measured_pct: Decimal
    measured_full_ladder_pct: Decimal
    measured_excluding_breakeven_pct: Decimal
    sample_size: int
    ci_low_pct: Decimal
    ci_high_pct: Decimal
    sample_sufficient: bool
    conclusion: str
    note: str = (
        "S5 [00:38:20] / [01:15:40] state a back-tested 77-82% win rate for the supply/demand "
        "method; S4-C2 adds 8/10, 7/10, 10-for-14 and 7-for-7. CONFLICTS.md rules these NOT usable "
        "for sizing or validation - recollections, no sample, no win definition. This harness "
        "reports the claim only as a hypothesis under test. No sizing, expectancy, Kelly fraction "
        "or capacity number anywhere in this package references it, and a measured win rate below "
        "it is a result, not a bug to be fitted away (SPEC.md §12.5)."
    )

    @classmethod
    def of(cls, rates: WinRates) -> "ClaimComparison":
        lo, hi = _wilson(rates.wins, rates.trades)
        enough = rates.trades >= MIN_SAMPLE_FOR_CONCLUSION
        if rates.trades == 0:
            conclusion = "no closed trades: nothing can be said about the claim"
        elif not enough:
            conclusion = (
                f"sample too small to conclude anything: {rates.trades} closed trade(s), "
                f"below the {MIN_SAMPLE_FOR_CONCLUSION}-trade floor [OUR CHOICE]. "
                f"The 95% Wilson interval is {lo:.1f}%-{hi:.1f}%, which is too wide to separate "
                f"any hypothesis from any other."
            )
        elif hi < CLAIM_LOW_PCT:
            conclusion = (
                f"measured win rate is materially BELOW the claim: the 95% interval "
                f"{lo:.1f}%-{hi:.1f}% lies entirely under {CLAIM_LOW_PCT}%. Per §12.5 this is a "
                f"result and must not trigger fitting toward the claim."
            )
        elif lo > CLAIM_HIGH_PCT:
            conclusion = (
                f"measured win rate is ABOVE the claimed band: the 95% interval "
                f"{lo:.1f}%-{hi:.1f}% lies entirely over {CLAIM_HIGH_PCT}%. Check the fill model "
                f"and the win definition before believing it."
            )
        else:
            conclusion = (
                f"the 95% interval {lo:.1f}%-{hi:.1f}% overlaps the claimed "
                f"{CLAIM_LOW_PCT}%-{CLAIM_HIGH_PCT}% band: consistent with the claim, which is not "
                f"the same as confirming it."
            )
        return cls(
            claim_low_pct=CLAIM_LOW_PCT, claim_high_pct=CLAIM_HIGH_PCT,
            measured_pct=rates.net_positive_pct,
            measured_full_ladder_pct=rates.full_ladder_pct,
            measured_excluding_breakeven_pct=rates.excluding_breakeven_pct,
            sample_size=rates.trades, ci_low_pct=lo, ci_high_pct=hi,
            sample_sufficient=enough, conclusion=conclusion,
        )


# --------------------------------------------------------------------------- the report


@dataclass(frozen=True, slots=True)
class MetricsReport:
    """Every §12.4 metric for one run, plus the §12.5 claim comparison, plus a text renderer."""

    symbol: str
    tf: Timeframe
    bars: int
    warmup_bars: int
    start: datetime | None
    end: datetime | None
    starting_equity: Decimal
    ending_equity: Decimal
    net_pnl_usd: Decimal
    total_fees_usd: Decimal
    total_funding_usd: Decimal
    win_rates: WinRates
    expectancy_r: Decimal
    expectancy_usd: Decimal
    r_distribution: RDistribution
    drawdown: Drawdown
    drawdown_by_account: tuple[tuple[str, Drawdown], ...]
    attribution: Attribution
    by_trade_class: tuple[Bucket, ...]
    by_vehicle: tuple[Bucket, ...]
    by_conviction: tuple[Bucket, ...]
    by_entry_family: tuple[Bucket, ...]
    by_touch_index: tuple[Bucket, ...]
    by_close_reason: tuple[Bucket, ...]
    fill_quality: FillQuality
    time_in_market: TimeInMarket
    excess_risk_total_usd: Decimal
    excess_risk_trades: int
    veto_census: tuple[tuple[str, int], ...]
    veto_reasons: tuple[tuple[str, int], ...]
    claim: ClaimComparison
    open_at_end: int
    liquidations: int
    notes: tuple[str, ...] = ()

    # -- rendering --------------------------------------------------------

    def render(self) -> str:
        """The full human-readable report.  Everything is net of fees, slippage and funding."""
        out: list[str] = []
        add = out.append
        rule = "=" * 78
        add(rule)
        add(f"BACKTEST REPORT  {self.symbol} {self.tf.value}")
        add(rule)
        span = (f"{self.start:%Y-%m-%d %H:%M} -> {self.end:%Y-%m-%d %H:%M}"
                if self.start and self.end else "n/a")
        add(f"  bars {self.bars} (warm-up discarded: {self.warmup_bars})   range {span}")
        add(f"  equity {self.starting_equity:.2f} -> {self.ending_equity:.2f} USD   "
            f"net P&L {self.net_pnl_usd:+.2f}")
        add(f"  fees {self.total_fees_usd:.2f}   funding {self.total_funding_usd:.2f}   "
            f"(all metrics are NET - SPEC.md §12.3)")
        if self.open_at_end:
            add(f"  {self.open_at_end} position(s) still open at the end: excluded from the "
                f"closed-trade metrics")
        if self.liquidations:
            add(f"  !! {self.liquidations} LIQUIDATION(S) - per §12.2 A12 that is a §8.8 sizing "
                f"bug, not a result")
        add("")

        add("-- WIN RATE (three definitions, §12.4 / S5-A19) " + "-" * 30)
        w = self.win_rates
        add(f"  closed trades                    {w.trades}")
        add(f"  1. net P&L > 0 (headline)        {w.net_positive_pct:6.2f}%   "
            f"({w.wins}W / {w.losses}L / {w.breakevens}BE)")
        add(f"  2. full TP-ladder completion     {w.full_ladder_pct:6.2f}%   "
            f"({w.full_ladder_completions} of {w.trades})")
        add(f"  3. excluding break-even exits    {w.excluding_breakeven_pct:6.2f}%   "
            f"({w.wins} of {w.wins + w.losses} decided)")
        add("")

        add("-- THE 77-82% CLAIM: A HYPOTHESIS UNDER TEST (§12.5) " + "-" * 24)
        c = self.claim
        add(f"  claimed (S5, recollection)       {c.claim_low_pct:.0f}%-{c.claim_high_pct:.0f}%")
        add(f"  measured (definition 1)          {c.measured_pct:6.2f}%   n = {c.sample_size}")
        add(f"  95% Wilson interval              {c.ci_low_pct:.1f}% - {c.ci_high_pct:.1f}%")
        add(f"  verdict: {c.conclusion}")
        add(f"  {c.note}")
        add("")

        add("-- EXPECTANCY AND R DISTRIBUTION " + "-" * 44)
        add(f"  expectancy                       {self.expectancy_r:+.4f} R per trade "
            f"({self.expectancy_usd:+.2f} USD)")
        r = self.r_distribution
        add(f"  R: p5 {r.p5:+.2f}  p25 {r.p25:+.2f}  median {r.median:+.2f}  "
            f"p75 {r.p75:+.2f}  p95 {r.p95:+.2f}")
        add(f"  outcomes worse than -1R          {r.worse_than_minus_1r}  "
            f"(gap and slippage losses: §12.2 A2, A6)")
        for label, count in r.histogram:
            if count:
                add(f"      {label:>16}  {'#' * min(count, 40)} {count}")
        add("")

        add("-- DRAWDOWN " + "-" * 65)
        d = self.drawdown
        add(f"  portfolio max drawdown           {d.max_pct:.2f}%  ({d.max_usd:.2f} USD)  "
            f"bar {d.peak_index} -> {d.trough_index}")
        for name, dd in self.drawdown_by_account:
            add(f"    {name:<18} {dd.max_pct:6.2f}%  ({dd.max_usd:.2f} USD)")
        add("")

        add("-- PER-DETECTOR ATTRIBUTION (§12.4, CF-31) " + "-" * 34)
        add(f"  {'anchor class':<22}{'n':>5}{'win%':>9}{'exp R':>9}{'total R':>10}{'net USD':>12}")
        for b in self.attribution.primary:
            add(f"  {b.label:<22}{b.trades:>5}{b.win_rate_pct:>8.1f}%{b.expectancy_r:>9.3f}"
                f"{b.total_r:>10.2f}{b.net_pnl_usd:>12.2f}")
        if self.attribution.marginal:
            add("  marginal contribution as a confluence member (not the anchor):")
            for b in self.attribution.marginal:
                add(f"  {b.label:<22}{b.trades:>5}{b.win_rate_pct:>8.1f}%{b.expectancy_r:>9.3f}"
                    f"{b.total_r:>10.2f}{b.net_pnl_usd:>12.2f}")
        add("")

        for title, buckets in (("trade class", self.by_trade_class), ("vehicle", self.by_vehicle),
                               ("conviction", self.by_conviction),
                               ("entry family", self.by_entry_family),
                               ("touch index at entry", self.by_touch_index),
                               ("close reason", self.by_close_reason)):
            if not buckets:
                continue
            add(f"-- BY {title.upper()} " + "-" * max(2, 70 - len(title)))
            for b in buckets:
                add(f"  {b.label:<22}{b.trades:>5}{b.win_rate_pct:>8.1f}%{b.expectancy_r:>9.3f}"
                    f"{b.total_r:>10.2f}{b.net_pnl_usd:>12.2f}")
            add("")

        add("-- FILL QUALITY (§12.4, A7) " + "-" * 49)
        f = self.fill_quality
        for k, rate in enumerate(f.rung_fill_rate_pct):
            add(f"  rung {k}: filled {f.rung_filled[k]}/{f.rung_offered[k]} = {rate:.1f}%")
        add(f"  realised vs planned average entry: {f.mean_entry_slippage:+.6f} "
            f"({f.mean_entry_slippage_bps:+.2f} bps, adverse-positive)")
        add(f"  trades whose ladder only partly filled: {f.trades_with_partial_ladder}")
        add("")

        add("-- EXCESS RISK (spot exits, §12.2 A8, CF-05) " + "-" * 32)
        add(f"  total {self.excess_risk_total_usd:.2f} USD across {self.excess_risk_trades} "
            f"trade(s); reported separately and NOT netted out of the risk statistics")
        add("")

        add("-- TIME IN MARKET " + "-" * 59)
        t = self.time_in_market
        add(f"  median {t.median_bars:.1f} bars ({t.median_hours:.1f}h), mean {t.mean_bars:.1f} bars")
        for name, bars, hours in t.by_class:
            add(f"    {name:<18} median {bars:.1f} bars ({hours:.1f}h)")
        add("")

        add("-- VETO CENSUS (which §7 gate is actually shaping the strategy) " + "-" * 13)
        if not self.veto_census:
            add("  no rejections recorded")
        for gate, count in self.veto_census:
            add(f"  {gate:<40}{count:>6}")
        if self.veto_reasons:
            add("  most common reasons:")
            for reason, count in self.veto_reasons[:10]:
                add(f"    {reason[:60]:<62}{count:>6}")
        add("")

        if self.notes:
            add("-- NOTES " + "-" * 68)
            for note in self.notes:
                add(f"  * {note}")
            add("")
        add(rule)
        return "\n".join(out)

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready snapshot (Decimals become strings so nothing is silently rounded)."""

        def scrub(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Timeframe):
                return value.value
            if isinstance(value, tuple):
                return [scrub(v) for v in value]
            if isinstance(value, list):
                return [scrub(v) for v in value]
            if isinstance(value, dict):
                return {str(k): scrub(v) for k, v in value.items()}
            if hasattr(value, "__slots__"):
                return {name: scrub(getattr(value, name)) for name in type(value).__slots__
                        if not name.startswith("_")}
            return value

        return {name: scrub(getattr(self, name)) for name in type(self).__slots__
                if not name.startswith("_")}


# --------------------------------------------------------------------------- computation


def _buckets(trades: Sequence[ClosedTrade], key) -> tuple[Bucket, ...]:
    grouped: dict[str, list[ClosedTrade]] = defaultdict(list)
    for trade in trades:
        grouped[str(key(trade))].append(trade)
    return tuple(Bucket.of(label, group) for label, group in sorted(grouped.items()))


def _attribution(trades: Sequence[ClosedTrade]) -> Attribution:
    primary = _buckets(trades, lambda t: t.primary_class)
    marginal_groups: dict[str, list[ClosedTrade]] = defaultdict(list)
    for trade in trades:
        for cls_name in trade.confluence_classes:
            if cls_name != trade.primary_class:
                marginal_groups[cls_name].append(trade)
    marginal = tuple(Bucket.of(name, group) for name, group in sorted(marginal_groups.items()))
    return Attribution(primary=primary, marginal=marginal)


def _fill_quality(trades: Sequence[ClosedTrade]) -> FillQuality:
    width = max((t.rungs_planned for t in trades), default=0)
    offered = [0] * width
    filled = [0] * width
    for trade in trades:
        for k, was_filled in enumerate(trade.rung_fill_flags):
            offered[k] += 1
            if was_filled:
                filled[k] += 1
    gaps = [t.entry_slippage for t in trades]
    bps = [
        (t.entry_slippage / t.planned_average_entry * Decimal(10_000))
        for t in trades if t.planned_average_entry > ZERO
    ]
    return FillQuality(
        rung_fill_rate_pct=tuple(_pct(filled[k], offered[k]) for k in range(width)),
        rung_offered=tuple(offered), rung_filled=tuple(filled),
        mean_entry_slippage=_mean(gaps), mean_entry_slippage_bps=_mean(bps),
        trades_with_partial_ladder=sum(1 for t in trades
                                       if 0 < t.rungs_filled < t.rungs_planned),
    )


def _time_in_market(trades: Sequence[ClosedTrade], tf: Timeframe) -> TimeInMarket:
    hours_per_bar = Decimal(tf.minutes) / Decimal(60)
    all_bars = sorted(float(t.bars_in_trade) for t in trades)
    median = dec(round(_percentile(all_bars, 0.5), 4))
    mean = _mean([Decimal(t.bars_in_trade) for t in trades])
    by_class: list[tuple[str, Decimal, Decimal]] = []
    grouped: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        grouped[trade.trade_class.value].append(float(trade.bars_in_trade))
    for name, values in sorted(grouped.items()):
        med = dec(round(_percentile(sorted(values), 0.5), 4))
        by_class.append((name, med, med * hours_per_bar))
    return TimeInMarket(tf=tf, median_bars=median, mean_bars=mean,
                        median_hours=median * hours_per_bar, by_class=tuple(by_class))


def _account_curves(points: Sequence[EquityPoint],
                    starting_equity: Decimal) -> tuple[tuple[str, Drawdown], ...]:
    """Per-account drawdown, measured on each account's own P&L added to the shared start equity.

    §10.6 splits capital by market-cap bucket, but that allocation belongs to ``risk.py``; the
    harness does not invent a per-account starting balance, so this is a *relative* drawdown on a
    common base and is labelled as such.
    """
    names: list[str] = []
    for point in points:
        for name in point.by_account:
            if name not in names:
                names.append(name)
    out: list[tuple[str, Drawdown]] = []
    for name in sorted(names):
        curve = [(p.bar_index, starting_equity + p.by_account.get(name, ZERO)) for p in points]
        drawdown = Drawdown.of(curve)
        if drawdown.max_usd > ZERO:
            out.append((name, drawdown))
    return tuple(out)


def _veto_census(rejections: Iterable[RejectionRecord]) -> tuple[
        tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]]:
    gates = Counter(r.gate for r in rejections)
    reasons = Counter(r.reason for r in rejections)
    ordered_gates = tuple(sorted(gates.items(), key=lambda kv: (-kv[1], kv[0])))
    ordered_reasons = tuple(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])))
    return ordered_gates, ordered_reasons


def compute_metrics(result: BacktestResult) -> MetricsReport:
    """Compute the full §12.4 metric set for one :class:`~tbot.backtest.engine.BacktestResult`."""
    trades = result.trades
    rates = WinRates.of(trades)
    gates, reasons = _veto_census(result.rejections)
    curve = [(p.bar_index, p.equity) for p in result.equity_curve]
    return MetricsReport(
        symbol=result.symbol, tf=result.tf, bars=result.bars, warmup_bars=result.warmup_bars,
        start=result.start, end=result.end,
        starting_equity=result.starting_equity, ending_equity=result.ending_equity,
        net_pnl_usd=result.ending_equity - result.starting_equity,
        total_fees_usd=sum((t.fees_usd for t in trades), ZERO),
        total_funding_usd=sum((t.funding_usd for t in trades), ZERO),
        win_rates=rates,
        expectancy_r=_mean([t.r_multiple for t in trades]),
        expectancy_usd=_mean([t.net_pnl_usd for t in trades]),
        r_distribution=RDistribution.of(trades),
        drawdown=Drawdown.of(curve),
        drawdown_by_account=_account_curves(result.equity_curve, result.starting_equity),
        attribution=_attribution(trades),
        by_trade_class=_buckets(trades, lambda t: t.trade_class.value),
        by_vehicle=_buckets(trades, lambda t: t.vehicle.value),
        by_conviction=_buckets(trades, lambda t: t.conviction.value),
        by_entry_family=_buckets(trades, lambda t: t.entry_family.value),
        by_touch_index=_buckets(trades, lambda t: f"touch {t.touch_index_at_entry}"),
        by_close_reason=_buckets(trades, lambda t: t.close_reason.value),
        fill_quality=_fill_quality(trades),
        time_in_market=_time_in_market(trades, result.tf),
        excess_risk_total_usd=sum((t.excess_risk_usd for t in trades), ZERO),
        excess_risk_trades=sum(1 for t in trades if t.excess_risk_usd != ZERO),
        veto_census=gates, veto_reasons=reasons,
        claim=ClaimComparison.of(rates),
        open_at_end=len(result.open_at_end),
        liquidations=sum(1 for t in trades if t.liquidated),
        notes=result.notes,
    )
