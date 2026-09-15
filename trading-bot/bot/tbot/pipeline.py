"""tbot.pipeline — SPEC.md §3, the stage ordering that joins §5 → §6 → §7 → §8.

This is the glue module.  It owns **no rules**: every number it acts on is read by the module
that owns it (INTERFACES.md §7) and handed back as a derived value.  The only configuration keys
read here are the ``pipeline.py`` block of INTERFACES.md §7 — ``pipeline_order``,
``sfp_evaluated_last``, ``disowned_modules_still_score_confluence`` and the three
``module_*_enabled`` switches — plus ``config`` itself, which is passed straight down.

What it does, in ``config.pipeline_order`` order (SPEC.md §3.1, 18 stages):

1.  ``universe_calendar_gate``  — resolve the injected symbol profile / calendar (never fetched).
2.  ``load_align_candles``      — the series the harness handed us, plus the CF-24 structure and
                                  HTF views derived by resampling **completed** bars only.
3.  ``structure``               — P1 pivots, P11 trend, MSBs, structure exits, reclaims.
4.  ``levels_sr_flips``         — §5.1 levels with the §5.2 flip machine attached.
5.  ``trend_lines``             — §5.3 (ships disabled; objects still score, CF-37).
6.  ``ranges_mid_range``        — §5.4 ranges, boundaries, mid-range and the CF-25 gate.
7.  ``liquidity_map``           — P18 liquidity / barcoding screen.
8.  ``supply_demand_zones``     — §5.5, fed the stage-3 levels for the CF-08 rescue.
9.  ``order_blocks``            — §5.6, fed the stage-7 zones for the CF-09 nesting.
10. ``context_regime``          — §7.2 cross-market context from the injected ``context`` map.
11. ``fibs``                    — §5.9, fed levels + zones so S6-R38 precedence is applied.
12. ``chart_patterns``          — §5.10 (ships disabled; objects still score, CF-37).
13. ``confluence_scoring``      — §6 clustering and scoring, plus the CF-23 bias level, which is
                                  the one structure object that needs confluence objects to exist.
14. ``sfp``                     — §5.8, fed levels + zones + trend; re-scores when it fires
                                  (``sfp_evaluated_last``, CF-32).
15. ``rsi_divergence``          — §3.1 stage 14; ``detectors/indicators.py`` does not exist in
                                  this build, so the stage is recorded as unavailable.
16. ``ltf_refinement``          — needs a lower-timeframe series; the harness hands us one
                                  timeframe, so the stage is recorded as unavailable unless one
                                  is injected.
17. ``setup_qualification``     — §7.1 gate stack, once per candidate cluster.
18. ``trade_plan_construction`` — §8 entry ladder → stop → take-profits → size.

**Injected context.**  ``context``, ``calendar``, ``portfolio_state``, ``profile``,
``active_symbols`` and ``ltf_series`` are all optional.  When one is missing the layer that
needs it degrades the way its own module documents, the fact is recorded in
:attr:`PipelineRun.notes` and copied onto every emitted ``Setup.regime_flags["pipeline_notes"]`` —
nothing is invented to fill the gap (SPEC.md §1.9: no network, ever).

**No lookahead.**  ``run`` only ever reads ``series`` — the harness hands it
``series.head(now + 1)`` — and always passes ``at_index=now`` explicitly rather than letting a
primitive default to "the last bar of some longer series".  Nothing is cached between bars: the
function is pure, so two calls with the same arguments produce identical output and no bar can
learn anything from a later one (INTERFACES.md §9.1, §9.9; SPEC.md §12.1).

**Ids are stable across bars.**  A setup is named after the object that anchors it, not after the
bar we happen to be standing on, so re-publishing the same candidate on the next bar produces the
same ``TradePlan.id`` and the harness arms it exactly once.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

import tbot.primitives as P
from tbot.backtest.engine import (
    DEFAULT_STARTING_EQUITY,
    DetectionRecord,
    PipelineOutput,
    RejectionRecord,
)
from tbot.config import Config
from tbot.confluence import ConfluenceCluster, find_clusters
from tbot.data import resample
from tbot.detectors.fibs import FibDetector
from tbot.detectors.levels import SupportResistanceDetector, is_playable
from tbot.detectors.orderblocks import OrderBlockDetector
from tbot.detectors.patterns import Pattern, PatternDetector
from tbot.detectors.ranges import DetectedRange, RangeDetector, classify_price
from tbot.detectors.sfp import SFP, SFPDetector
from tbot.detectors.structure import (
    MSB,
    StructureDetector,
    bias_invalidation_level,
    htf_veto_reason,
    structure_state,
    structure_tf_for,
)
from tbot.detectors.trendlines import TrendlineDetector
from tbot.detectors.zones import SupplyDemandZoneDetector
from tbot.models import (
    Direction,
    EntryFamily,
    FibLevel,
    FlipState,
    Level,
    LevelKind,
    OBSide,
    OrderBlock,
    Series,
    Setup,
    Timeframe,
    TradeClass,
    TradePlan,
    Trend,
    Vehicle,
    Zone,
    ZoneClass,
    ZoneSide,
    dec,
)
from tbot.plan import (
    PlanBuild,
    PlanInputs,
    build_entry_ladder,
    build_plan,
    dca_leg_count,
    place_stop,
    rr_for_gate,
    sizing_reference,
)
from tbot.qualify import (
    CalendarEvent,
    QualificationResult,
    SymbolProfile,
    is_btc,
    qualify,
    trade_class_for_tf,
)
from tbot.regime import RegimeState, evaluate_regime
from tbot.risk import PortfolioState, concurrency_gate, sizing_budget

__all__ = [
    "MODULE_SOURCE_IDS",
    "STAGES",
    "PipelineRun",
    "analyse_bar",
    "run",
    "run_pipeline",
    "analyse",
]

#: The rule IDs this module itself implements — stage ordering and the module switches.
MODULE_SOURCE_IDS: tuple[str, ...] = ("CF-32", "CF-37", "SPEC-3.1")

#: The 18 SPEC.md §3.1 stage names, in the order ``config.pipeline_order`` ships them.
STAGES: tuple[str, ...] = (
    "universe_calendar_gate",
    "load_align_candles",
    "structure",
    "levels_sr_flips",
    "trend_lines",
    "ranges_mid_range",
    "liquidity_map",
    "supply_demand_zones",
    "order_blocks",
    "context_regime",
    "fibs",
    "chart_patterns",
    "confluence_scoring",
    "sfp",
    "rsi_divergence",
    "ltf_refinement",
    "setup_qualification",
    "trade_plan_construction",
)

_ZERO = Decimal(0)

#: Pipeline-level pre-gate: the §7.1 stack starts at G1 and assumes a *candidate* already exists.
#: A cluster that cannot become one (nothing to trade it against, or it sits on the wrong side of
#: price for its own role) is rejected here so the §12.4 census stays complete.  **[OUR CHOICE]** —
#: SPEC.md §7.1 does not name a G0.
_PRE_GATE = "G0"


# =========================================================================== degradation notes


def _note(notes: list[str], text: str) -> None:
    if text not in notes:
        notes.append(text)


# =========================================================================== the run record


@dataclass(slots=True)
class PipelineRun:
    """Everything one bar of analysis produced — the harness only consumes :attr:`output`.

    The extra fields exist so a test, the CLI or a report can see *why* a bar produced what it
    did without re-running anything.
    """

    series: Series
    config: Config
    now: int
    timestamp: datetime
    stages_run: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    pivots: tuple[Any, ...] = ()
    trend: Trend = Trend.NEUTRAL
    structure_trend: Trend = Trend.NEUTRAL
    structure_events: tuple[Any, ...] = ()
    levels: tuple[Level, ...] = ()
    trendlines: tuple[Level, ...] = ()
    ranges: tuple[DetectedRange, ...] = ()
    range_levels: tuple[Level, ...] = ()
    zones: tuple[Zone, ...] = ()
    order_blocks: tuple[OrderBlock, ...] = ()
    fibs: tuple[FibLevel, ...] = ()
    patterns: tuple[Pattern, ...] = ()
    sfps: tuple[SFP, ...] = ()
    clusters: tuple[ConfluenceCluster, ...] = ()
    confluence_objects: tuple[P.ConfluenceObject, ...] = ()
    regime: RegimeState | None = None
    liquidity: P.LiquidityScreen | None = None
    bias_level: Level | None = None
    in_mid_range_band: bool = False
    price_discovery: bool = False

    setups: tuple[Setup, ...] = ()
    qualifications: tuple[tuple[Setup, QualificationResult], ...] = ()
    plan_builds: tuple[tuple[Setup, PlanBuild], ...] = ()
    plans: tuple[TradePlan, ...] = ()
    detections: tuple[DetectionRecord, ...] = ()
    rejections: tuple[RejectionRecord, ...] = ()

    @property
    def output(self) -> PipelineOutput:
        """The §12 harness view: plans, surviving setups, detections, rejections."""
        return PipelineOutput(
            plans=tuple(self.plans),
            setups=tuple(s for s in self.setups if not s.vetoes),
            detections=tuple(self.detections),
            rejections=tuple(self.rejections),
        )


# =========================================================================== internal state


@dataclass(slots=True)
class _Ctx:
    """Mutable working state for one bar.  Never escapes :func:`analyse_bar`."""

    series: Series
    config: Config
    now: int
    timestamp: datetime
    context: Mapping[str, Series]
    calendar: tuple[CalendarEvent, ...]
    portfolio: PortfolioState | None
    profile: SymbolProfile | None
    active_symbols: tuple[str, ...]
    ltf_series: Series | None
    run: PipelineRun
    notes: list[str] = field(default_factory=list)
    detections: list[DetectionRecord] = field(default_factory=list)
    rejections: list[RejectionRecord] = field(default_factory=list)
    stages_run: list[str] = field(default_factory=list)
    #: every emitted object by id, so a cluster contributor can be mapped back to its object
    objects: dict[str, Any] = field(default_factory=dict)
    structure_series: Series | None = None
    htf_series: Series | None = None


# =========================================================================== helpers


def _completion_index(obj: Any) -> int | None:
    """The bar that completed ``obj``, read off its INTERFACES.md §6.5 id.

    Ids are ``symbol:tf:detector:completion_bar[:n]``, so field 3 is the completion bar for every
    detector in the package.  Returns ``None`` when the id does not follow the convention.
    """
    ident = getattr(obj, "id", None)
    if not isinstance(ident, str):
        return None
    parts = ident.split(":")
    if len(parts) < 4:
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


def _record(ctx: _Ctx, detector: str, objects: Sequence[Any], obj_class: str) -> None:
    """Register objects, and emit a :class:`DetectionRecord` for the ones completed *this* bar.

    ``detect`` re-derives a detector's whole live set every bar; recording all of it every bar
    would say "emitted on this bar" about an object that was emitted 400 bars ago.  Only objects
    whose completion bar is the current bar are new detections (§12.4).
    """
    for obj in objects:
        ident = getattr(obj, "id", None)
        if isinstance(ident, str):
            ctx.objects.setdefault(ident, obj)
        if _completion_index(obj) != ctx.now:
            continue
        ctx.detections.append(DetectionRecord(
            bar_index=ctx.now,
            detector=detector,
            object_id=str(ident),
            obj_class=obj_class,
            source_ids=tuple(getattr(obj, "source_ids", ())),
        ))


def _reject(ctx: _Ctx, setup_id: str, gate: str, reason: str, *,
            direction: Direction | None = None, source_ids: Sequence[str] = ()) -> None:
    ctx.rejections.append(RejectionRecord(
        bar_index=ctx.now,
        setup_id=setup_id,
        gate=gate,
        reason=reason,
        symbol=ctx.series.symbol,
        direction=direction,
        source_ids=tuple(source_ids),
    ))


def _higher_view(ctx: _Ctx, target: Timeframe) -> Series | None:
    """``series`` resampled to ``target``, with an **incomplete** final bar dropped.

    Resampling ``series.head(now + 1)`` produces a last bucket that is still forming whenever the
    current bar is not the last bar of that bucket.  Trading off it would be repainting (P1), so
    it is cut.  Returns ``None`` when the target is not above the series' own timeframe.
    """
    series = ctx.series
    if target.rank < series.tf.rank:
        return None
    if target is series.tf:
        return series
    try:
        with warnings.catch_warnings():
            # pandas warns that ``origin`` is inert for non-tick frequencies (1D and up); that is
            # exactly the case ``data.resample`` handles with its own ``day_boundary_utc`` offset,
            # so the warning is noise on every bar of a backtest.
            warnings.simplefilter("ignore", RuntimeWarning)
            view = resample(series, target, ctx.config)
    except Exception:                                     # pragma: no cover - defensive
        return None
    if len(view) == 0:
        return None
    bucket_start = view.timestamp(-1)
    bar_end = series.timestamp(ctx.now).timestamp() + series.tf.minutes * 60
    if bar_end < bucket_start.timestamp() + target.minutes * 60:
        view = view.head(len(view) - 1)
    return view if len(view) > 0 else None


def _module_switches(config: Config) -> dict[str, bool]:
    """CF-37 — the three module switches this module owns."""
    return {
        "chart_patterns": bool(config.module_chart_patterns_enabled),
        "trend_lines": bool(config.module_trendline_break_enabled),
        "scalp": bool(config.module_scalp_enabled),
    }


# =========================================================================== stages


def _stage_universe_calendar_gate(ctx: _Ctx) -> None:
    """Stage 1 — the injected off-chart facts.  This module never fetches any of them."""
    if ctx.profile is None:
        _note(ctx.notes, "no SymbolProfile injected: the CF-40 universe tier (G1) is not "
                         "evaluated and the vehicle is not demoted on rank/volume grounds")
    if not ctx.calendar:
        _note(ctx.notes, "no calendar injected: the CF-39 event blackout (G3) sees an empty "
                         "calendar; unscheduled news cannot reach the bot at all (TBOT1-A23)")
    if not ctx.active_symbols:
        _note(ctx.notes, "no active-symbol list injected: the CF-40 watchlist cap (G2) is "
                         "evaluated against an empty book")


def _stage_load_align_candles(ctx: _Ctx) -> None:
    """Stage 2 — the trade series, plus the CF-24 structure and HTF views."""
    cfg, series = ctx.config, ctx.series
    try:
        structure_tf = structure_tf_for(series.tf, cfg)
    except Exception:                                     # pragma: no cover - defensive
        structure_tf = series.tf
    ctx.structure_series = _higher_view(ctx, structure_tf)
    if ctx.structure_series is None:
        _note(ctx.notes, f"structure timeframe {structure_tf.value} is not reachable from "
                         f"{series.tf.value}: structure is read on the trade timeframe (CF-24)")
        ctx.structure_series = series

    if cfg.htf_veto_enabled:
        try:
            htf_tf = Timeframe.parse(cfg.htf_veto_timeframe)
        except Exception:                                 # pragma: no cover - defensive
            htf_tf = structure_tf
        ctx.htf_series = _higher_view(ctx, htf_tf)
        if ctx.htf_series is None:
            _note(ctx.notes, f"htf_veto_timeframe {cfg.htf_veto_timeframe} is below the trade "
                             f"timeframe {series.tf.value}: the CF-24 HTF veto (G8) is not "
                             f"evaluated")


def _stage_structure(ctx: _Ctx) -> None:
    """Stage 3 — §5.7.  The CF-23 bias level waits for confluence objects (stage 13)."""
    det = StructureDetector()
    series, cfg, now = ctx.series, ctx.config, ctx.now
    pivots = det.swings(series, cfg)
    ctx.run.pivots = tuple(P.confirmed_swings(pivots, now))
    events = det.detect(series, cfg)
    ctx.run.structure_events = tuple(events)
    _record(ctx, det.name, events, "sr_level")
    ctx.run.trend = structure_state(series, cfg, pivots=pivots, at_index=now).trend
    if ctx.structure_series is not None and ctx.structure_series is not series:
        ctx.run.structure_trend = structure_state(ctx.structure_series, cfg).trend
    else:
        ctx.run.structure_trend = ctx.run.trend


def _stage_levels_sr_flips(ctx: _Ctx) -> None:
    """Stage 4 — §5.1 / §5.2."""
    det = SupportResistanceDetector()
    levels = det.detect(ctx.series, ctx.config)
    ctx.run.levels = tuple(levels)
    _record(ctx, det.name, levels, "sr_level")


def _stage_trend_lines(ctx: _Ctx) -> None:
    """Stage 5 — §5.3.  Ships disabled; CF-37 keeps its objects in the confluence stack."""
    cfg = ctx.config
    if not cfg.module_trendline_break_enabled and not cfg.disowned_modules_still_score_confluence:
        _note(ctx.notes, "module_trendline_break_enabled=false and "
                         "disowned_modules_still_score_confluence=false: §5.3 not run (CF-37)")
        return
    det = TrendlineDetector()
    lines = det.detect(ctx.series, cfg)
    ctx.run.trendlines = tuple(lines)
    _record(ctx, det.name, lines, "trendline")


def _stage_ranges_mid_range(ctx: _Ctx) -> None:
    """Stage 6 — §5.4, including the CF-25 mid-range no-trade band."""
    det = RangeDetector()
    series, cfg, now = ctx.series, ctx.config, ctx.now
    ranges = det.detect_ranges(series, cfg)
    levels = det.detect(series, cfg)
    ctx.run.ranges = tuple(ranges)
    ctx.run.range_levels = tuple(levels)
    _record(ctx, det.name, levels, "range_boundary")

    close = dec(float(series.close[now]))
    blocked = False
    for rng in ranges:
        if rng.mid is None:
            continue
        verdict = classify_price(rng, series, cfg, close, at_index=now,
                                 levels=list(ctx.run.levels))
        if verdict.entries_blocked:
            blocked = True
    ctx.run.in_mid_range_band = blocked


def _stage_liquidity_map(ctx: _Ctx) -> None:
    """Stage 7 — P18.  A demotion, never an exclusion, and it feeds the CF-18 split."""
    ctx.run.liquidity = P.liquidity_screen(ctx.series, ctx.config)


def _stage_supply_demand_zones(ctx: _Ctx) -> None:
    """Stage 8 — §5.5.  The stage-4 levels are handed in for the CF-08 rescue clause."""
    det = SupplyDemandZoneDetector(levels=ctx.run.levels)
    zones, rejected = det.detect_with_rejections(ctx.series, ctx.config)
    ctx.run.zones = tuple(zones)
    _record(ctx, det.name, zones, "zone")
    for rej in rejected:
        if rej.breakout_index != ctx.now:
            continue
        # A slug, not a sentence: ``metrics._veto_census`` counts distinct reason strings, so a
        # reason carrying prices would make every rejection its own census row.
        _reject(ctx, f"{ctx.series.symbol}:zone_candidate:{rej.breakout_index}",
                _PRE_GATE, "zone_candidate_rejected",
                source_ids=("CF-11", "CF-12", "CF-13"))


def _stage_order_blocks(ctx: _Ctx) -> None:
    """Stage 9 — §5.6.  The stage-8 zones are handed in for the CF-09 nesting rule."""
    det = OrderBlockDetector(zones=ctx.run.zones)
    blocks, rejected = det.detect_with_rejections(ctx.series, ctx.config)
    ctx.run.order_blocks = tuple(blocks)
    _record(ctx, det.name, blocks, "order_block")
    for rej in rejected:
        if rej.bar_index != ctx.now:
            continue
        _reject(ctx, f"{ctx.series.symbol}:ob_candidate:{rej.bar_index}",
                _PRE_GATE, "order_block_candidate_rejected",
                source_ids=("CF-09", "CF-12"))


def _stage_context_regime(ctx: _Ctx) -> None:
    """Stage 10 — §7.2.  Cross-market context is a veto at weight 0, never a confluence object."""
    if not ctx.context:
        _note(ctx.notes, "no cross-market context injected (USDT.D / BTC.D / BVOL): the §7.2 "
                         "regime layer degrades to neutral and never invents a risk-on read")
    ctx.run.regime = evaluate_regime(
        ctx.context, ctx.config,
        is_alt=not is_btc(ctx.series.symbol),
        now=ctx.timestamp,
    )


def _stage_fibs(ctx: _Ctx) -> None:
    """Stage 11 — §5.9, with S6-R38 precedence resolved before scoring (CF-32)."""
    det = FibDetector()
    fibs = det.detect(
        ctx.series, ctx.config,
        levels=list(ctx.run.levels) + list(ctx.run.range_levels),
        zones=list(ctx.run.zones),
        pivots=list(ctx.run.pivots),
        at_index=ctx.now,
    )
    ctx.run.fibs = tuple(fibs)
    _record(ctx, det.name, fibs, "fib")


def _stage_chart_patterns(ctx: _Ctx) -> None:
    """Stage 12 — §5.10.  Ships disabled; CF-37 keeps its objects in the confluence stack."""
    cfg = ctx.config
    if not cfg.module_chart_patterns_enabled and not cfg.disowned_modules_still_score_confluence:
        _note(ctx.notes, "module_chart_patterns_enabled=false and "
                         "disowned_modules_still_score_confluence=false: §5.10 not run (CF-37)")
        return
    det = PatternDetector()
    patterns = det.detect(ctx.series, cfg, levels=list(ctx.run.levels),
                          pivots=list(ctx.run.pivots))
    ctx.run.patterns = tuple(patterns)
    _record(ctx, det.name, patterns, "pattern")


def _confluence_objects(ctx: _Ctx, *, include_sfp: bool) -> list[P.ConfluenceObject]:
    """Every priced object of stages 3–14, through each detector's own §6.7 adapter."""
    cfg, now = ctx.config, ctx.now
    objs: list[P.ConfluenceObject] = []
    objs.extend(SupportResistanceDetector().to_confluence(list(ctx.run.levels), cfg))
    objs.extend(RangeDetector().to_confluence(list(ctx.run.range_levels), cfg))
    objs.extend(SupplyDemandZoneDetector().to_confluence(list(ctx.run.zones), cfg))
    objs.extend(OrderBlockDetector().to_confluence(list(ctx.run.order_blocks), cfg))
    objs.extend(StructureDetector().to_confluence(list(ctx.run.structure_events), cfg))
    objs.extend(FibDetector().to_confluence(list(ctx.run.fibs), cfg))
    objs.extend(PatternDetector().to_confluence(list(ctx.run.patterns), cfg))
    # A sloped level scores at its price *now*, not at its anchor bar (§5.3 adapter note).
    for line in ctx.run.trendlines:
        objs.append(P.ConfluenceObject(
            id=line.id, price=line.price_at(now), obj_class="trendline", tf=line.tf,
            source_ids=line.source_ids,
        ))
    if include_sfp:
        objs.extend(SFPDetector().to_confluence(list(ctx.run.sfps), cfg))
    return objs


def _score(ctx: _Ctx, *, include_sfp: bool) -> None:
    objs = _confluence_objects(ctx, include_sfp=include_sfp)
    ctx.run.confluence_objects = tuple(objs)
    continuation = tuple(
        z.id for z in ctx.run.zones if z.zone_class is ZoneClass.CONTINUATION
    )
    regime = ctx.run.regime
    ctx.run.clusters = tuple(find_clusters(
        ctx.series, ctx.config, objs,
        at_index=ctx.now,
        continuation_zone_ids=continuation,
        adverse_regime=bool(regime.adverse) if regime is not None else False,
        mid_range_flag=ctx.run.in_mid_range_band,
    ))


def _stage_confluence_scoring(ctx: _Ctx) -> None:
    """Stage 13 — §6.  Also the one place the CF-23 bias level can be derived."""
    _score(ctx, include_sfp=bool(ctx.run.sfps))
    if ctx.config.bias_level_enabled:
        ctx.run.bias_level = bias_invalidation_level(
            ctx.series, ctx.config,
            pivots=list(ctx.run.pivots),
            confluence_objects=list(ctx.run.confluence_objects),
            at_index=ctx.now,
        )


def _stage_sfp(ctx: _Ctx) -> None:
    """Stage 14 — §5.8, evaluated last (``sfp_evaluated_last``, CF-32, PL-5)."""
    det = SFPDetector()
    sfps = det.detect(
        ctx.series, ctx.config,
        levels=list(ctx.run.levels) + list(ctx.run.range_levels),
        zones=list(ctx.run.zones),
        trend=ctx.run.structure_trend,
        pivots=list(ctx.run.pivots),
    )
    ctx.run.sfps = tuple(sfps)
    _record(ctx, det.name, sfps, "sfp")
    if sfps and ctx.run.clusters:
        # An SFP is second-order confluence on a level that was already scored: fold it in and
        # re-score, which is what "evaluated last" means (CF-32).
        _score(ctx, include_sfp=True)


def _stage_rsi_divergence(ctx: _Ctx) -> None:
    """Stage 15 — CF-36.  ``tbot/detectors/indicators.py`` is not part of this build."""
    if ctx.config.ema200_confluence_enabled or ctx.config.rsi_divergence_mode != "disabled":
        _note(ctx.notes, "detectors/indicators.py (§3.1 stage 14, CF-36) is not implemented in "
                         "this build: the rsi_divergence and ema200 confluence classes are never "
                         "produced, so nothing scores on them")


def _stage_ltf_refinement(ctx: _Ctx) -> None:
    """Stage 16 — CF-06 step 1 needs a lower-timeframe series; the harness hands us one."""
    if ctx.ltf_series is None:
        _note(ctx.notes, f"no lower-timeframe series injected: CF-06 step 1 (tighten the stop "
                         f"{ctx.config.stop_tighten_tf_steps} timeframes down) is unavailable and "
                         f"a wide stop goes straight to the vehicle downgrade")


# =========================================================================== setup formation


def _anchor_of(ctx: _Ctx, cluster: ConfluenceCluster) -> Any | None:
    """The heaviest contributor's real object — the thing the setup hangs off."""
    weights = ctx.config.confluence_weights
    best: tuple[float, str] | None = None
    chosen: Any | None = None
    for obj in cluster.contributors:
        real = ctx.objects.get(obj.id)
        if real is None:
            continue
        weight = float(obj.weight) if obj.weight is not None else float(
            weights.get(obj.obj_class, 0.0))
        key = (weight, obj.id)
        if best is None or key > best:
            best, chosen = key, real
    return chosen


def _direction_of(anchor: Any, price: Decimal, close: Decimal) -> Direction | None:
    """The direction the anchoring object itself points in (never the chart's mood)."""
    if isinstance(anchor, Zone):
        return Direction.LONG if anchor.side is ZoneSide.DEMAND else Direction.SHORT
    if isinstance(anchor, OrderBlock):
        return Direction.LONG if anchor.side is OBSide.BULLISH else Direction.SHORT
    if isinstance(anchor, SFP):
        return anchor.direction
    if isinstance(anchor, FibLevel):
        return anchor.direction
    if isinstance(anchor, MSB):
        return anchor.direction
    if isinstance(anchor, Pattern):
        return anchor.direction
    if isinstance(anchor, Level):
        if anchor.kind in (LevelKind.SUPPORT, LevelKind.SR_CONFIRMED_SUPPORT,
                           LevelKind.RANGE_LOW):
            return Direction.LONG
        if anchor.kind in (LevelKind.RESISTANCE, LevelKind.SR_CONFIRMED_RESISTANCE,
                           LevelKind.RANGE_HIGH):
            return Direction.SHORT
        return Direction.LONG if price <= close else Direction.SHORT
    return None


def _entry_family(anchor: Any, config: Config) -> EntryFamily:
    """CF-16 — which family this candidate belongs to."""
    if isinstance(anchor, SFP) or isinstance(anchor, MSB):
        return EntryFamily.TRIGGER
    if isinstance(anchor, Level) and anchor.flip_state is FlipState.PENDING:
        return EntryFamily.FLIP_PENDING
    return EntryFamily.RETEST


def _entry_level_for(anchor: Any, cluster: ConfluenceCluster, ctx: _Ctx,
                     direction: Direction) -> Level | None:
    """The :class:`~tbot.models.Level` the first, lightest rung rests on (S5-R20, S7-R18).

    A real level contributor always wins; when the cluster is anchored on a zone or an order
    block the level is derived **from that object** (same id, same rule chain) rather than
    invented — the plan builder needs a ``Level`` container, not a new structural claim.
    """
    for obj in cluster.contributors:
        real = ctx.objects.get(obj.id)
        if isinstance(real, Level):
            return real
    if isinstance(anchor, Zone):
        kind = LevelKind.SUPPORT if anchor.side is ZoneSide.DEMAND else LevelKind.RESISTANCE
        price = anchor.entry_price_pmt if anchor.entry_price_pmt is not None else anchor.outer_edge
        return Level(id=f"{anchor.id}:edge", symbol=anchor.symbol, tf=anchor.tf, price=price,
                     kind=kind, created_index=anchor.breakout_index,
                     touch_count=anchor.touch_count, source_ids=anchor.source_ids)
    if isinstance(anchor, OrderBlock):
        kind = LevelKind.SUPPORT if anchor.side is OBSide.BULLISH else LevelKind.RESISTANCE
        return Level(id=f"{anchor.id}:mid", symbol=anchor.symbol, tf=anchor.tf,
                     price=anchor.midpoint, kind=kind, created_index=anchor.bar_index,
                     source_ids=anchor.source_ids)
    if isinstance(anchor, (SFP, FibLevel, Pattern, MSB)):
        kind = LevelKind.SUPPORT if direction is Direction.LONG else LevelKind.RESISTANCE
        completion = _completion_index(anchor)
        if completion is None:
            return None
        return Level(id=f"{anchor.id}:level", symbol=ctx.series.symbol, tf=ctx.series.tf,
                     price=cluster.price, kind=kind, created_index=completion,
                     source_ids=tuple(getattr(anchor, "source_ids", ())))
    return None


def _object_window(ctx: _Ctx, obj: Any) -> tuple[int, int]:
    """The bars an object declares as its own.  Never reaches past ``now`` (P1)."""
    now = ctx.now
    window: tuple[int, int] | None = None
    if isinstance(obj, Zone):
        window = (obj.formation_start_index, obj.formation_end_index)
    elif isinstance(obj, OrderBlock):
        window = (obj.bar_index, obj.bar_index)
    elif isinstance(obj, SFP):
        window = (obj.swing_index, obj.bar_index)
    elif isinstance(obj, Level):
        marks = [i for i in list(obj.anchor_indices) +
                 [i for i, _ in obj.touch_history] if 0 <= i <= now]
        window = (min(marks), max(marks)) if marks else (obj.created_index, obj.created_index)
    if window is None:
        completion = _completion_index(obj)
        base = now if completion is None else completion
        window = (base, base)
    start = max(0, min(window[0], now))
    stop = max(start, min(window[1], now))
    return start, stop


def _stop_anchor_index(ctx: _Ctx, obj: Any, direction: Direction) -> int:
    """CF-14 step 1 — the bar carrying the far-edge extreme of ``obj``.

    For a zone that is the deepest formation bar; for an order block its own candle; for a bare
    level the most extreme bar among the touches that drew it.  The object handed in is the one
    the **last funded rung** sits on, not the first: a stop anchored on the near level would sit
    inside a ladder whose blended average is further out, and CF-18 measures the stop from that
    blended average (SPEC.md §8.9).
    """
    series = ctx.series
    low, high = series.low, series.high
    start, stop = _object_window(ctx, obj)
    span = range(start, stop + 1)
    if direction is Direction.LONG:
        return min(span, key=lambda i: (low[i], i))
    return max(span, key=lambda i: (high[i], -i))


def _structural_levels(ctx: _Ctx) -> list[Level]:
    """Every horizontal structural level available to the ladder, deduplicated by id."""
    out: dict[str, Level] = {}
    for lvl in list(ctx.run.levels) + list(ctx.run.range_levels):
        out.setdefault(lvl.id, lvl)
    return list(out.values())


def _ladders(ctx: _Ctx, cluster: ConfluenceCluster, anchor: Any, direction: Direction,
             entry_price: Decimal) -> tuple[list[Level], list[Level], list[Level]]:
    """``(dca_levels, tp_levels, opposing_levels)`` — all nearest-first, all structural.

    ``opposing_levels`` is CF-14 step 3's "independent" S/R: a level that is neither part of this
    setup's confluence cluster nor inside the anchoring object's own box.  Order matters —
    :func:`tbot.plan.place_stop` keeps the **last** clip it makes, so the list runs from the far
    side inwards and the stop ends up just inside the nearest opposing level.
    """
    now = ctx.now
    contributors = {o.id for o in cluster.contributors}
    box: tuple[Decimal, Decimal] | None = None
    if isinstance(anchor, Zone):
        box = (anchor.box_bottom, anchor.box_top)
    elif isinstance(anchor, OrderBlock):
        box = (anchor.box_bottom, anchor.box_top)

    dca: list[tuple[Decimal, Level]] = []
    tps: list[tuple[Decimal, Level]] = []
    opposing: list[tuple[Decimal, Level]] = []
    for lvl in _structural_levels(ctx):
        price = lvl.price_at(now)
        if direction is Direction.LONG:
            beyond, ahead = price < entry_price, price > entry_price
        else:
            beyond, ahead = price > entry_price, price < entry_price
        if beyond:
            dca.append((price, lvl))
            independent = lvl.id not in contributors and not (
                box is not None and box[0] <= price <= box[1]
            )
            if independent:
                opposing.append((price, lvl))
        elif ahead:
            tps.append((price, lvl))

    # nearest first for the ladder, far-to-near for the stop clip
    if direction is Direction.LONG:
        dca.sort(key=lambda pl: -pl[0])
        tps.sort(key=lambda pl: pl[0])
        opposing.sort(key=lambda pl: pl[0])
    else:
        dca.sort(key=lambda pl: pl[0])
        tps.sort(key=lambda pl: -pl[0])
        opposing.sort(key=lambda pl: -pl[0])
    return ([l for _, l in dca], [l for _, l in tps], [l for _, l in opposing])


def _trade_class(ctx: _Ctx, direction: Direction) -> TradeClass:
    """CF-38 timeframe class, with price discovery recognised for longs (S6-R36)."""
    if ctx.run.price_discovery and direction is Direction.LONG:
        return TradeClass.PRICE_DISCOVERY
    return trade_class_for_tf(ctx.series.tf, ctx.config)


def _make_setup(ctx: _Ctx, cluster: ConfluenceCluster, anchor: Any,
                direction: Direction) -> Setup:
    """One §2.6 candidate.  The id names the *anchor*, never the bar we are standing on."""
    series = ctx.series
    try:
        structure_tf = structure_tf_for(series.tf, ctx.config)
    except Exception:                                     # pragma: no cover - defensive
        structure_tf = series.tf
    return Setup(
        id=f"setup:{getattr(anchor, 'id', 'unknown')}:{direction.value}",
        symbol=series.symbol,
        direction=direction,
        trade_tf=series.tf,
        structure_tf=structure_tf,
        trade_class=_trade_class(ctx, direction),
        anchor_price=cluster.price,
        created_index=ctx.now,
        object_ids=list(cluster.object_ids),
        confluence_score=cluster.score,
        confluence_classes=set(cluster.classes),
        entry_family=_entry_family(anchor, ctx.config),
        conviction=cluster.conviction,
        source_ids=tuple(dict.fromkeys(MODULE_SOURCE_IDS + cluster.source_ids)),
    )


# =========================================================================== §7 + §8


def _qualify_once(ctx: _Ctx, setup: Setup, cluster: ConfluenceCluster, anchor: Any,
                  entry_level: Level, *, rr: Decimal | None = None,
                  expected_move_pct: Decimal | None = None,
                  stop_rejection: str | None = None,
                  insufficient_tps: bool = False,
                  record_on_setup: bool = False) -> QualificationResult:
    """Run the §7.1 stack.  Every verdict below is computed by the module that owns its key."""
    cfg, series, now = ctx.config, ctx.series, ctx.now
    switches = _module_switches(cfg)

    module_disabled = False
    if isinstance(anchor, Pattern) and not switches["chart_patterns"]:
        module_disabled = True
    if isinstance(anchor, Level) and anchor.is_trendline and not switches["trend_lines"]:
        module_disabled = True
    if setup.trade_class is TradeClass.SCALP and not switches["scalp"]:
        module_disabled = True

    object_dead = False
    if isinstance(anchor, Zone):
        object_dead = anchor.is_dead and anchor.rescued_by_level_id is None
    elif isinstance(anchor, OrderBlock):
        object_dead = anchor.is_dead

    touch_limit_exceeded = False
    if isinstance(anchor, Level) and not is_playable(anchor, cfg):
        touch_limit_exceeded = True

    htf_opposes = False
    if ctx.htf_series is not None:
        htf_opposes = htf_veto_reason(
            ctx.htf_series, cfg, setup.direction
        ) is not None

    capacity = True
    if ctx.portfolio is not None:
        gate = concurrency_gate(
            cfg, ctx.portfolio,
            vehicle=Vehicle.LEVERAGE, trade_class=setup.trade_class,
        )
        capacity = gate.allowed

    return qualify(
        setup, cfg,
        confluence=cluster,
        regime=ctx.run.regime,
        profile=ctx.profile,
        series=series,
        calendar=ctx.calendar,
        now=ctx.timestamp,
        active_symbols=ctx.active_symbols,
        vehicle=Vehicle.LEVERAGE,
        structure_trend=ctx.run.structure_trend,
        is_alt=not is_btc(series.symbol),
        price_discovery=ctx.run.price_discovery,
        anchor_level=entry_level if isinstance(anchor, Level) else None,
        expected_move_pct=expected_move_pct,
        rr=rr,
        in_mid_range_band=ctx.run.in_mid_range_band,
        htf_opposes=htf_opposes,
        object_dead=object_dead,
        touch_limit_exceeded=touch_limit_exceeded,
        stop_rejection=stop_rejection,
        insufficient_tps=insufficient_tps,
        capacity_available=capacity,
        module_disabled=module_disabled,
        record_on_setup=record_on_setup,
    )


def _budget(ctx: _Ctx, setup: Setup, verdict: QualificationResult, touch_index: int):
    """The §10 budget.  ``portfolio_state`` is injected; without one the harness default is used."""
    portfolio = ctx.portfolio
    if portfolio is None:
        portfolio = PortfolioState(equity_usd=DEFAULT_STARTING_EQUITY, now=ctx.timestamp)
    return sizing_budget(
        ctx.config, portfolio,
        trade_class=verdict.trade_class,
        vehicle=verdict.vehicle,
        conviction=verdict.conviction,
        counter_trend=verdict.counter_trend,
        touch_index=touch_index,
        extra_multipliers=(verdict.size_multiplier,),
    )


def _stop_rejection_from(build: PlanBuild) -> tuple[str | None, bool]:
    """Map §8's own refusal reasons onto the §7.1 gates that own them (G12/G13, G16)."""
    text = " ".join(build.reasons)
    if "tp_min_count" in text or "no_structural_take_profit_levels" in text:
        return None, True
    if "stop_too_wide" in text or "cannot_downgrade" in text:
        return "stop_too_wide", False
    if "stop_too_tight" in text:
        return "stop_too_tight", False
    return None, False


def _stage_setup_qualification_and_plans(ctx: _Ctx) -> None:
    """Stages 17 + 18 — the §7.1 stack, then §8 construction for whatever survived it."""
    cfg, series, now = ctx.config, ctx.series, ctx.now
    close = dec(float(series.close[now]))
    setups: list[Setup] = []
    quals: list[tuple[Setup, QualificationResult]] = []
    builds: list[tuple[Setup, PlanBuild]] = []
    plans: list[TradePlan] = []
    seen_setup_ids: set[str] = set()
    liquidity = ctx.run.liquidity
    wick_heavy = bool(liquidity.wick_heavy) if liquidity is not None else False

    for cluster in ctx.run.clusters:
        anchor = _anchor_of(ctx, cluster)
        if anchor is None:
            continue
        direction = _direction_of(anchor, cluster.price, close)
        if direction is None:
            continue
        entry_level = _entry_level_for(anchor, cluster, ctx, direction)
        if entry_level is None:
            continue

        setup = _make_setup(ctx, cluster, anchor, direction)
        if setup.id in seen_setup_ids:
            # Two price stacks resolved onto the same anchor; clusters arrive in rank order, so
            # the first one is the better candidate (§6.2 tie-break) and the second is noise.
            continue
        seen_setup_ids.add(setup.id)
        entry_price = entry_level.price_at(now)
        if isinstance(anchor, Zone) and anchor.entry_price_pmt is not None:
            entry_price = anchor.entry_price_pmt

        # --- G0: is this even a candidate?  A retest is bid *behind* price, never chased.
        if setup.entry_family is not EntryFamily.TRIGGER:
            wrong_side = (entry_price > close) if direction is Direction.LONG else (
                entry_price < close)
            if wrong_side:
                setup.vetoes.append(
                    f"{_PRE_GATE}:anchor_beyond_price (a {direction.value} retest at "
                    f"{entry_price} would chase the close {close}; CF-16 makes a retest a "
                    f"limit order, never a chase)"
                )
                _reject(ctx, setup.id, _PRE_GATE, "anchor_beyond_price",
                        direction=direction, source_ids=("CF-16",))
                continue

            # Right side of the close, but is it within reach?  He never states a ceiling, so this
            # is off unless a sweep turns it on (DISCORD CHECK 2026-09-15 bounds the range, not the
            # value).  Distance is measured off the close, the same reference the dashboard's
            # `distance_pct` column reports.
            if cfg.max_entry_distance_enabled and close > 0:
                distance_pct = abs(close - entry_price) / close * dec(100)
                if distance_pct > dec(cfg.max_entry_distance_pct):
                    setup.vetoes.append(
                        f"{_PRE_GATE}:entry_too_far (a {direction.value} retest at {entry_price} "
                        f"sits {distance_pct:.2f}% off the close {close}, past the "
                        f"{cfg.max_entry_distance_pct}% ceiling [OUR CHOICE])"
                    )
                    _reject(ctx, setup.id, _PRE_GATE, "entry_too_far", direction=direction)
                    continue

        # --- §7.1 pass 1: everything knowable before the plan exists.
        verdict = _qualify_once(ctx, setup, cluster, anchor, entry_level)
        if not verdict.qualified:
            rej = verdict.rejection
            assert rej is not None
            setup.vetoes.append(str(rej))
            setups.append(setup)
            quals.append((setup, verdict))
            _reject(ctx, setup.id, rej.gate, rej.reason, direction=direction,
                    source_ids=tuple(dict.fromkeys(setup.source_ids + rej.source_ids)))
            continue

        # --- §8 construction.
        touch_index = max(1, int(getattr(anchor, "touch_count", 0)) + 1)
        dca_levels, tp_levels, opposing = _ladders(ctx, cluster, anchor, direction, entry_price)

        # CF-14 step 1 anchors on the far edge of the *whole* ladder, so the rungs have to be
        # known first.  ``build_entry_ladder`` / ``dca_leg_count`` are ``plan.py``'s own
        # functions and ``build_plan`` re-runs them with identical arguments, so this is the same
        # ladder, not a second opinion about it.
        n_dca = dca_leg_count(
            cfg,
            trade_class=setup.trade_class,
            entry_family=setup.entry_family,
            zone_depth_atr=anchor.depth_atr if isinstance(anchor, Zone) else None,
            single_entry_play=isinstance(anchor, (SFP, Pattern)),
        )
        rungs, _ladder_notes = build_entry_ladder(
            cfg,
            direction=direction,
            entry_price=entry_price,
            entry_level_id=entry_level.id,
            dca_levels=dca_levels,
            dca_count=n_dca,
            at_index=now,
            wick_heavy=wick_heavy,
            conviction=setup.conviction,
        )
        by_id = {lvl.id: lvl for lvl in dca_levels}
        by_id[entry_level.id] = entry_level
        funded = [r for r in rungs if r.size_fraction > _ZERO] or list(rungs)
        far_level = by_id.get(funded[-1].level_id, entry_level)
        far_object = anchor if funded[-1].level_id == entry_level.id else far_level
        stop_bar = _stop_anchor_index(ctx, far_object, direction)

        # CF-18: the stop is measured from ``size_and_stop_computed_from``.  A stop that does not
        # end up beyond that reference is degenerate, and G13 is the gate that owns it.
        reference = sizing_reference(cfg, rungs)
        # F6: probe with the same parameterisation ``build_plan`` will use, or G13 would be
        # judging a stop the plan never places — the zone-anchored stop is a fraction of the box
        # height, not an ATR multiple.
        probe = place_stop(series, cfg, direction=direction, bar_index=stop_bar,
                           reference_price=reference, opposing_levels=opposing, at_index=now,
                           zone_stop_edge=anchor.body_stop_edge if isinstance(anchor, Zone) else None,
                           zone_height=anchor.depth if isinstance(anchor, Zone) else None,
                           beyond_price=funded[-1].price if funded else None)
        degenerate = (probe.price >= reference) if direction is Direction.LONG else (
            probe.price <= reference)
        if degenerate:
            final = _qualify_once(ctx, setup, cluster, anchor, entry_level,
                                  stop_rejection="stop_too_tight", record_on_setup=True)
            rej = final.rejection
            gate = rej.gate if rej is not None else "G13"
            reason = rej.reason if rej is not None else "stop_too_tight"
            if rej is None:                                   # pragma: no cover - defensive
                setup.vetoes.append(f"{gate}:{reason}")
            setups.append(setup)
            quals.append((setup, final))
            _reject(ctx, setup.id, gate, reason, direction=direction,
                    source_ids=tuple(dict.fromkeys(setup.source_ids + ("CF-14", "CF-18"))))
            continue

        inputs = PlanInputs(
            setup=setup,
            series=series,
            budget=_budget(ctx, setup, verdict, touch_index),
            entry_level=entry_level,
            stop_anchor_index=stop_bar,
            dca_levels=dca_levels,
            tp_levels=tp_levels,
            opposing_levels=opposing,
            zone=anchor if isinstance(anchor, Zone) else None,
            at_index=now,
            ltf_series=ctx.ltf_series,
            ltf_stop_anchor_index=None,
            wick_heavy=wick_heavy,
            spot_allowed=verdict.universe.permits(Vehicle.SPOT) if verdict.universe else True,
            leverage_allowed=(verdict.universe.permits(Vehicle.LEVERAGE)
                              if verdict.universe else True),
            invalidation_level_id=entry_level.id,
            bias_invalidation_price=(ctx.run.bias_level.price
                                     if ctx.run.bias_level is not None else None),
            expires_at_index=(anchor.retest_deadline_index
                              if isinstance(anchor, MSB) else None),
            single_entry_play=isinstance(anchor, (SFP, Pattern)),
        )
        build = build_plan(inputs, cfg)
        builds.append((setup, build))

        if build.plan is None:
            stop_rejection, insufficient_tps = _stop_rejection_from(build)
            final = _qualify_once(ctx, setup, cluster, anchor, entry_level,
                                  stop_rejection=stop_rejection,
                                  insufficient_tps=insufficient_tps,
                                  record_on_setup=True)
            rej = final.rejection
            gate = rej.gate if rej is not None else _PRE_GATE
            reason = rej.reason if rej is not None else "plan_not_constructible"
            detail = "; ".join(build.reasons) or reason
            if rej is None:
                setup.vetoes.append(f"{gate}:{reason} ({detail})")
            setups.append(setup)
            quals.append((setup, final))
            _reject(ctx, setup.id, gate, reason, direction=direction,
                    source_ids=tuple(dict.fromkeys(setup.source_ids + ("CF-06", "CF-14",
                                                                       "CF-27"))))
            continue

        # --- §7.1 pass 2: G14 (R:R) and G15 (expected move) need the finished plan.
        # CF-42 / F9: ``rr_for_gate`` picks TP1 or the final TP per ``rr_measured_to``.
        final = _qualify_once(ctx, setup, cluster, anchor, entry_level,
                              rr=rr_for_gate(cfg, build.plan),
                              expected_move_pct=build.plan.expected_move_pct,
                              record_on_setup=True)
        setups.append(setup)
        quals.append((setup, final))
        if not final.qualified:
            rej = final.rejection
            assert rej is not None
            _reject(ctx, setup.id, rej.gate, rej.reason, direction=direction,
                    source_ids=tuple(dict.fromkeys(setup.source_ids + rej.source_ids)))
            continue

        setup.regime_flags = dict(setup.regime_flags)
        setup.regime_flags.update({
            "touch_index": touch_index,
            "vehicle": build.plan.vehicle.value,
            "counter_trend": final.counter_trend,
            "pipeline_notes": tuple(ctx.notes),
        })
        plans.append(build.plan)

    ctx.run.setups = tuple(setups)
    ctx.run.qualifications = tuple(quals)
    ctx.run.plan_builds = tuple(builds)
    ctx.run.plans = tuple(plans)


_STAGE_HANDLERS: dict[str, Callable[[_Ctx], None]] = {
    "universe_calendar_gate": _stage_universe_calendar_gate,
    "load_align_candles": _stage_load_align_candles,
    "structure": _stage_structure,
    "levels_sr_flips": _stage_levels_sr_flips,
    "trend_lines": _stage_trend_lines,
    "ranges_mid_range": _stage_ranges_mid_range,
    "liquidity_map": _stage_liquidity_map,
    "supply_demand_zones": _stage_supply_demand_zones,
    "order_blocks": _stage_order_blocks,
    "context_regime": _stage_context_regime,
    "fibs": _stage_fibs,
    "chart_patterns": _stage_chart_patterns,
    "confluence_scoring": _stage_confluence_scoring,
    "sfp": _stage_sfp,
    "rsi_divergence": _stage_rsi_divergence,
    "ltf_refinement": _stage_ltf_refinement,
    "setup_qualification": _stage_setup_qualification_and_plans,
    "trade_plan_construction": lambda ctx: None,   # run with stage 17: G14/G15 need the plan
}


# =========================================================================== entry points


def analyse_bar(
    series: Series,
    config: Config,
    *,
    context: Mapping[str, Series] | None = None,
    calendar: Sequence[CalendarEvent] | None = None,
    portfolio_state: PortfolioState | None = None,
    profile: SymbolProfile | None = None,
    active_symbols: Sequence[str] = (),
    ltf_series: Series | None = None,
) -> PipelineRun:
    """Run every §3.1 stage over ``series`` as of its **last** bar and return the full record.

    ``series`` is the truncated view the harness built with ``series.head(now + 1)``; the current
    bar is ``len(series) - 1`` and no later bar exists to be read.
    """
    if len(series) == 0:
        raise ValueError("cannot analyse an empty series")
    now = len(series) - 1
    run_record = PipelineRun(
        series=series, config=config, now=now, timestamp=series.timestamp(now)
    )
    ctx = _Ctx(
        series=series,
        config=config,
        now=now,
        timestamp=run_record.timestamp,
        context=dict(context) if context else {},
        calendar=tuple(calendar) if calendar else (),
        portfolio=portfolio_state,
        profile=profile,
        active_symbols=tuple(active_symbols),
        ltf_series=ltf_series,
        run=run_record,
    )
    if portfolio_state is None:
        _note(ctx.notes, "no portfolio state injected: the §10 concurrency, deployment and "
                         "daily-loss gates (G17) are not evaluated and sizing assumes the "
                         "harness default starting equity")

    highs = series.high
    ctx.run.price_discovery = bool(now > 0 and float(highs[now]) >= float(highs[:now].max()))

    for stage in config.pipeline_order:
        handler = _STAGE_HANDLERS.get(stage)
        if handler is None:
            _note(ctx.notes, f"unknown pipeline stage {stage!r}: skipped")
            continue
        handler(ctx)
        ctx.stages_run.append(stage)

    run_record.stages_run = tuple(ctx.stages_run)
    run_record.notes = tuple(ctx.notes)
    run_record.detections = tuple(ctx.detections)
    run_record.rejections = tuple(ctx.rejections)
    return run_record


def run(
    series: Series,
    config: Config,
    *,
    context: Mapping[str, Series] | None = None,
    calendar: Sequence[CalendarEvent] | None = None,
    portfolio_state: PortfolioState | None = None,
    profile: SymbolProfile | None = None,
    active_symbols: Sequence[str] = (),
    ltf_series: Series | None = None,
) -> PipelineOutput:
    """The contract ``tbot.backtest.engine`` probes for::

        run(series: Series, config: Config) -> PipelineOutput | Sequence[TradePlan]

    ``series`` is already truncated to the bar being analysed.  Returns the plans newly
    publishable at that close, the setups that survived §7, every detection completed on that bar
    and every rejection with the gate that made it.
    """
    return analyse_bar(
        series, config,
        context=context, calendar=calendar, portfolio_state=portfolio_state,
        profile=profile, active_symbols=active_symbols, ltf_series=ltf_series,
    ).output


#: Aliases for the other names ``engine._PIPELINE_CANDIDATES`` will accept.
run_pipeline = run
analyse = run
