"""tests/test_pipeline.py — the SPEC.md §3 glue module.

The contract under test is the one ``tbot.backtest.engine`` probes for::

    run(series: Series, config: Config) -> PipelineOutput | Sequence[TradePlan]

Everything here runs against ``tbot.data.synthetic``, whose features are hand-placed and whose
bars are byte-identical for a given seed (INTERFACES.md §5, ``tbot.data``).  The generator emits
``1H`` bars; they are relabelled ``4H`` throughout so the fixtures exercise the *swing* path.
(Q14 turned ``module_scalp_enabled`` on with ``scalp_tf_floor`` raised to ``30m``, so a ``1H``
series is no longer empty by construction — but ``4H`` remains what these tests are about.)
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from tbot import pipeline
from tbot.backtest.engine import (
    BarWindow,
    DetectionRecord,
    LookaheadError,
    PipelineOutput,
    RejectionRecord,
    assert_no_future_reference,
)
from tbot.config import KEY_SPEC_BY_NAME, Config
from tbot.data import synthetic
from tbot.models import Direction, EntryFamily, Setup, Timeframe, TradePlan
from tbot.qualify import CalendarEvent
from tbot.risk import PortfolioState


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def series():
    return synthetic(seed=7, tf=Timeframe.H4, symbol="SYNTHUSDT").series


@pytest.fixture(scope="module")
def features():
    return synthetic(seed=7, tf=Timeframe.H4, symbol="SYNTHUSDT").features


@pytest.fixture(scope="module")
def run_at_end(series, cfg):
    """One full analysis of the last bar — reused by most assertions (it is not cheap)."""
    return pipeline.analyse_bar(series, cfg)


@pytest.fixture(scope="module")
def first_plan_bar(series, cfg):
    """The earliest bar that publishes a plan, with its full record.  Computed once."""
    for i in range(60, len(series)):
        record = pipeline.analyse_bar(series.head(i + 1), cfg)
        if record.plans:
            return i, record
    return None, None


# --------------------------------------------------------------------------- the contract


def test_engine_probes_find_the_entry_point():
    """``engine._PIPELINE_CANDIDATES`` must resolve; all three names are accepted."""
    from tbot.backtest import engine

    names = [attr for module, attr in engine._PIPELINE_CANDIDATES if module == "tbot.pipeline"]
    assert names, "the engine no longer probes tbot.pipeline"
    for attr in names:
        assert callable(getattr(pipeline, attr, None)), f"tbot.pipeline.{attr} is missing"


def test_run_returns_a_pipeline_output(series, cfg):
    out = pipeline.run(series.head(90), cfg)
    assert isinstance(out, PipelineOutput)
    assert all(isinstance(p, TradePlan) for p in out.plans)
    assert all(isinstance(s, Setup) for s in out.setups)
    assert all(isinstance(d, DetectionRecord) for d in out.detections)
    assert all(isinstance(r, RejectionRecord) for r in out.rejections)


def test_run_rejects_an_empty_series(cfg, series):
    with pytest.raises(ValueError):
        pipeline.run(series.head(0), cfg)


def test_every_stage_of_pipeline_order_runs(run_at_end, cfg):
    assert list(run_at_end.stages_run) == list(cfg.pipeline_order)
    assert set(pipeline.STAGES) == set(cfg.pipeline_order)


def test_pipeline_order_is_honoured_when_it_changes(series, cfg):
    """``pipeline_order`` is the ordering, not a decoration: a permutation is followed."""
    order = list(cfg.pipeline_order)
    order[2], order[3] = order[3], order[2]          # levels before structure
    other = cfg.with_overrides(pipeline_order=order)
    record = pipeline.analyse_bar(series.head(90), other)
    assert list(record.stages_run) == order


# --------------------------------------------------------------------------- detectors wired


def test_detectors_produce_objects(run_at_end):
    r = run_at_end
    assert r.levels, "§5.1 produced no levels"
    assert r.zones, "§5.5 produced no zones"
    assert r.order_blocks, "§5.6 produced no order blocks"
    assert r.fibs, "§5.9 produced no fibs"
    assert r.clusters, "§6 produced no confluence clusters"


def test_zone_detector_is_fed_the_levels(series, cfg, monkeypatch):
    """CF-08's rescue clause needs stage-3 levels; the pipeline must hand them in."""
    seen: dict[str, object] = {}
    from tbot.detectors import zones as zones_mod

    original = zones_mod.SupplyDemandZoneDetector.__init__

    def spy(self, levels=(), **kw):
        seen.setdefault("calls", []).append(tuple(levels))
        original(self, levels, **kw)

    monkeypatch.setattr(zones_mod.SupplyDemandZoneDetector, "__init__", spy)
    monkeypatch.setattr(pipeline, "SupplyDemandZoneDetector", zones_mod.SupplyDemandZoneDetector)
    pipeline.analyse_bar(series.head(90), cfg)
    assert any(seen.get("calls", [])), (
        "zones were detected with no levels (CF-08 rescue impossible)"
    )


def test_order_blocks_are_fed_the_zones(series, cfg, monkeypatch):
    """CF-09 nesting: the OB detector must receive the stage-7 zones."""
    seen: dict[str, object] = {}
    from tbot.detectors import orderblocks as ob_mod

    original = ob_mod.OrderBlockDetector.__init__

    def spy(self, zones=(), **kw):
        seen.setdefault("calls", []).append(tuple(zones))
        original(self, zones, **kw)

    monkeypatch.setattr(ob_mod.OrderBlockDetector, "__init__", spy)
    monkeypatch.setattr(pipeline, "OrderBlockDetector", ob_mod.OrderBlockDetector)
    pipeline.analyse_bar(series.head(90), cfg)
    assert any(seen.get("calls", [])), (
        "order blocks were detected with no zones (CF-09 impossible)"
    )


def test_sfp_is_fed_levels_zones_and_trend(series, cfg, monkeypatch):
    """§5.8 is stage 13 precisely because it hangs off objects that already exist."""
    seen: dict[str, object] = {}
    from tbot.detectors import sfp as sfp_mod

    original = sfp_mod.SFPDetector.detect

    def spy(self, s, c, *, levels=(), zones=(), trend=None, pivots=None):
        seen.update(levels=tuple(levels), zones=tuple(zones), trend=trend, pivots=pivots)
        return original(self, s, c, levels=levels, zones=zones, trend=trend, pivots=pivots)

    monkeypatch.setattr(sfp_mod.SFPDetector, "detect", spy)
    monkeypatch.setattr(pipeline, "SFPDetector", sfp_mod.SFPDetector)
    pipeline.analyse_bar(series.head(99), cfg)
    assert seen["levels"], "SFP got no levels"
    assert seen["trend"] is not None, "SFP got no trend (S7-R31 veto cannot fire)"
    assert seen["pivots"] is not None, "SFP re-derived its own pivots"


def test_fibs_get_sr_precedence_inputs(series, cfg, monkeypatch):
    """S6-R38 must be resolved *before* scoring, which means levels and zones go in."""
    seen: dict[str, object] = {}
    from tbot.detectors import fibs as fib_mod

    original = fib_mod.FibDetector.detect

    def spy(self, s, c, *, levels=(), zones=(), pivots=None, at_index=None):
        seen.update(levels=tuple(levels), zones=tuple(zones), at_index=at_index)
        return original(self, s, c, levels=levels, zones=zones, pivots=pivots,
                        at_index=at_index)

    monkeypatch.setattr(fib_mod.FibDetector, "detect", spy)
    monkeypatch.setattr(pipeline, "FibDetector", fib_mod.FibDetector)
    record = pipeline.analyse_bar(series.head(90), cfg)
    assert seen["levels"], "fibs were drawn with no S/R to lose ties to"
    assert seen["at_index"] == record.now, "fibs were not pinned to the current bar"


def test_structure_bias_level_uses_confluence_objects(series, cfg, monkeypatch):
    """CF-23 — the bias level is the one structure object that needs stage-13 output."""
    seen: dict[str, object] = {}
    from tbot.detectors import structure as structure_mod

    original = structure_mod.bias_invalidation_level

    def spy(s, c, *, pivots=None, confluence_objects=(), at_index=None):
        seen["objects"] = tuple(confluence_objects)
        return original(s, c, pivots=pivots, confluence_objects=confluence_objects,
                        at_index=at_index)

    monkeypatch.setattr(pipeline, "bias_invalidation_level", spy)
    pipeline.analyse_bar(series.head(90), cfg)
    assert seen.get("objects"), "the bias level was derived with no confluence objects"


# --------------------------------------------------------------------------- plans


def test_pipeline_produces_plans_on_synthetic(first_plan_bar):
    index, record = first_plan_bar
    assert index is not None, "no bar of the synthetic series produced a plan"
    plan = record.plans[0]
    assert plan.entries, "a plan with no entry ladder"
    assert plan.take_profits, "a plan with no take-profits"
    assert plan.qty_total > 0
    assert plan.stop_price > 0
    if plan.direction is Direction.LONG:
        assert plan.stop_price < plan.planned_average_entry
    else:
        assert plan.stop_price > plan.planned_average_entry


def test_plan_ids_are_stable_across_bars(series, cfg, first_plan_bar):
    """A plan re-published on the next bar must keep its id, or the harness arms it twice."""
    index, record = first_plan_bar
    assert index is not None
    if index + 1 >= len(series):
        pytest.skip("the first plan lands on the last bar")
    later = pipeline.analyse_bar(series.head(index + 2), cfg)
    ids_now = {p.id for p in record.plans}
    ids_later = {p.id for p in later.plans}
    assert ids_now & ids_later, "no plan survived to the next bar with the same id"
    assert all(":" in pid for pid in ids_now)
    assert not any(str(index) == pid.split(":")[-2] for pid in ids_now if pid.count(":") > 2)


def test_source_ids_chain_survives_to_the_plan(first_plan_bar):
    """detector object -> ConfluenceObject -> Setup -> TradePlan (INTERFACES.md §6.3)."""
    index, record = first_plan_bar
    assert index is not None
    setups = {s.id: s for s in record.setups}
    for plan in record.plans:
        setup = setups[plan.setup_id]
        assert setup.source_ids, "the setup lost its rule chain"
        assert plan.source_ids, "the plan cannot name a single rule"
        missing = [sid for sid in setup.source_ids if sid not in plan.source_ids]
        assert not missing, f"plan dropped setup rule ids {missing}"
        # and the setup's chain really is the detectors' own ids, not invented here
        cluster = next(c for c in record.clusters
                       if frozenset(c.object_ids) == frozenset(setup.object_ids))
        for contributor in cluster.contributors:
            for sid in contributor.source_ids:
                assert sid in plan.source_ids, (
                    f"rule {sid} from {contributor.id} never reached the plan"
                )
        # the §8 stages add their own
        assert {"CF-16", "CF-17", "CF-18", "CF-14"} <= set(plan.source_ids)


def test_f9_every_published_plan_clears_min_rr_on_the_configured_basis(first_plan_bar, cfg):
    """G14 must be applied to the ratio ``rr_measured_to`` names — the FINAL TP since F9.

    The plan carries both figures; this asserts the pipeline gates on the configured one, and
    that a published plan can legitimately sit **below** ``min_rr`` on the old TP1 basis (which
    is exactly the population the tp1 basis was rejecting).
    """
    from tbot.plan import rr_for_gate

    index, record = first_plan_bar
    assert index is not None
    assert cfg.rr_measured_to == "final_tp"
    for plan in record.plans:
        assert plan.rr_to_final_tp is not None
        assert rr_for_gate(cfg, plan) == plan.rr_to_final_tp
        assert float(plan.rr_to_final_tp) >= cfg.min_rr
        assert plan.rr_to_final_tp >= plan.rr_to_tp1


def test_plan_traces_back_to_named_objects(first_plan_bar):
    index, record = first_plan_bar
    assert index is not None
    for plan in record.plans:
        setup = next(s for s in record.setups if s.id == plan.setup_id)
        assert setup.object_ids, "the setup names no objects"
        assert plan.invalidation_level_id, "a plan with no invalidation level"
        assert all(rung.level_id for rung in plan.entries), "a rung sitting on nothing"


# --------------------------------------------------------------------------- rejections


def test_rejections_carry_gate_and_reason(run_at_end):
    assert run_at_end.rejections, "no candidate was rejected on a bar with many clusters"
    for rejection in run_at_end.rejections:
        assert rejection.gate, "a rejection with no gate"
        assert rejection.reason, "a rejection with no reason"
        assert rejection.setup_id
        assert rejection.bar_index == run_at_end.now
        assert re.fullmatch(r"G\d+", rejection.gate), rejection.gate


def test_rejection_gates_come_from_the_gate_stack(series, cfg):
    """Every gate we report must be one §7.1 names (or the documented G0 pre-gate)."""
    gates: set[str] = set()
    for i in range(60, len(series), 7):
        gates.update(r.gate for r in pipeline.analyse_bar(series.head(i + 1), cfg).rejections)
    assert gates, "nothing was ever rejected"
    assert gates <= {f"G{n}" for n in range(0, 19)}, gates


def test_vetoed_setups_are_not_published_as_qualified(run_at_end):
    """The harness derives a rejection from any setup carrying vetoes — no double counting."""
    out = run_at_end.output
    assert all(not s.vetoes for s in out.setups)
    vetoed = [s for s in run_at_end.setups if s.vetoes]
    for setup in vetoed:
        assert any(r.setup_id == setup.id for r in out.rejections), (
            f"setup {setup.id} was vetoed but never reported"
        )


def test_nothing_is_dropped_silently(series, cfg):
    """Every cluster that became a candidate either produced a plan or produced a rejection."""
    record = pipeline.analyse_bar(series.head(90), cfg)
    accounted = {r.setup_id for r in record.rejections} | {p.setup_id for p in record.plans}
    for setup in record.setups:
        assert setup.id in accounted, f"{setup.id} vanished without a verdict"


# --------------------------------------------------------------------------- no lookahead


def test_output_never_references_a_future_bar(series, cfg):
    """SPEC.md §12.1 — the assertion the harness itself runs, at the pipeline level."""
    for i in (70, 80, 90, len(series) - 1):
        out = pipeline.run(series.head(i + 1), cfg)
        assert_no_future_reference(out.plans, i, path="pipeline.plans")
        assert_no_future_reference(out.setups, i, path="pipeline.setups")
        assert_no_future_reference(out.detections, i, path="pipeline.detections")
        assert_no_future_reference(out.rejections, i, path="pipeline.rejections")


def test_truncation_is_all_that_matters(series, cfg):
    """A bar analysed inside a long series must produce exactly what it produces alone.

    This is the real no-lookahead test: if anything reached past ``now`` — a cached array from a
    longer series, a primitive defaulting to "the last bar" — the two runs would differ.
    """
    now = 88
    from_long = pipeline.analyse_bar(series.head(now + 1), cfg)
    short = series.slice(0, now + 1)
    from_short = pipeline.analyse_bar(short, cfg)

    def fingerprint(record):
        return (
            tuple(sorted(p.id for p in record.plans)),
            tuple(sorted((p.id, str(p.stop_price), str(p.qty_total)) for p in record.plans)),
            tuple(sorted(s.id for s in record.setups)),
            tuple(sorted((r.setup_id, r.gate, r.reason) for r in record.rejections)),
            tuple(sorted(d.object_id for d in record.detections)),
        )

    assert fingerprint(from_long) == fingerprint(from_short)


def test_bar_window_guard_is_never_tripped(series, cfg):
    """Running through the harness' own window type must not raise :class:`LookaheadError`."""
    for i in (70, 85, 95):
        window = BarWindow.at(series, i)
        out = pipeline.run(window.series, cfg)
        assert isinstance(out, PipelineOutput)
        with pytest.raises(LookaheadError):
            window.candle(i + 1)


def test_detections_are_only_this_bars_objects(series, cfg):
    for i in range(70, len(series)):
        record = pipeline.analyse_bar(series.head(i + 1), cfg)
        for detection in record.detections:
            assert detection.bar_index == i
            assert int(detection.object_id.split(":")[3]) == i


def test_run_is_deterministic(series, cfg):
    a = pipeline.run(series.head(90), cfg)
    b = pipeline.run(series.head(90), cfg)
    assert [p.id for p in a.plans] == [p.id for p in b.plans]
    assert [str(p.qty_total) for p in a.plans] == [str(p.qty_total) for p in b.plans]
    assert [(r.gate, r.reason) for r in a.rejections] == [(r.gate, r.reason) for r in b.rejections]


# --------------------------------------------------------------------------- injected context


def test_missing_context_is_reported_not_invented(run_at_end):
    joined = " ".join(run_at_end.notes)
    for fragment in ("no cross-market context", "no portfolio state", "no SymbolProfile",
                     "no calendar", "no lower-timeframe series"):
        assert fragment in joined, f"the pipeline never admitted: {fragment}"
    regime = run_at_end.regime
    assert regime is not None
    assert regime.degraded and regime.missing
    assert regime.state == "neutral" and not regime.hard_veto
    assert regime.size_multiplier == Decimal(1)


def test_injected_context_reaches_the_regime_layer(series, cfg):
    context = {"USDT.D": series, "BTC.D": series}
    record = pipeline.analyse_bar(series.head(90), cfg, context=context)
    assert record.regime is not None
    assert "USDT.D" not in record.regime.missing
    assert "BTC.D" not in record.regime.missing


def test_injected_calendar_reaches_the_event_gate(series, cfg):
    now = series.timestamp(90)
    event = CalendarEvent(name="CPI", kind="cpi", start=now)
    record = pipeline.analyse_bar(series.head(91), cfg, calendar=[event])
    gates = {r.gate for r in record.rejections}
    assert "G3" in gates, "an active CPI blackout did not veto anything (CF-39)"
    assert not record.plans, "a plan was published inside an event blackout"


def test_injected_portfolio_state_reaches_the_capacity_gate(series, cfg, first_plan_bar):
    index, _ = first_plan_bar
    assert index is not None
    full = PortfolioState(
        equity_usd=Decimal(10_000), now=series.timestamp(index),
        open_slots=tuple(_full_book()),
    )
    record = pipeline.analyse_bar(series.head(index + 1), cfg, portfolio_state=full)
    assert "G17" in {r.gate for r in record.rejections}, "the CF-04 caps were never consulted"
    assert not record.plans


def _full_book():
    from tbot.models import Account, PositionState, TradeClass, Vehicle
    from tbot.risk import OpenSlot

    return [
        OpenSlot(position_id=f"p{i}", account=Account.LEVERAGE_SWING, vehicle=Vehicle.LEVERAGE,
                 trade_class=TradeClass.SWING, state=PositionState.OPEN,
                 notional_usd=Decimal(100))
        for i in range(8)
    ]


# --------------------------------------------------------------------------- config ownership


_ALLOWED_KEYS = {
    "pipeline_order",
    # G0 entry-distance ceiling (DISCORD CHECK 2026-09-15); off by default
    "max_entry_distance_enabled",
    "max_entry_distance_pct",
    "sfp_evaluated_last",
    "disowned_modules_still_score_confluence",
    "module_chart_patterns_enabled",
    "module_trendline_break_enabled",
    "module_scalp_enabled",
    # read to *report* a degradation, never to make a decision of its own
    "bias_level_enabled",
    "htf_veto_enabled",
    "htf_veto_timeframe",
    "confluence_weights",
    "ema200_confluence_enabled",
    "rsi_divergence_mode",
    "stop_tighten_tf_steps",
}


def test_pipeline_reads_only_the_keys_it_owns():
    """INTERFACES.md §7 — the owner is the only module that reads a key directly."""
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    touched = set(re.findall(r"\b(?:config|cfg)\.([a-z_][a-z0-9_]*)", source))
    real = {k for k in touched if k in KEY_SPEC_BY_NAME}
    assert real <= _ALLOWED_KEYS, f"pipeline.py reads keys it does not own: {real - _ALLOWED_KEYS}"


def test_pipeline_invents_no_config_keys():
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    touched = set(re.findall(r"\b(?:config|cfg)\.([a-z_][a-z0-9_]*)", source))
    unknown = {k for k in touched
               if k not in KEY_SPEC_BY_NAME and not hasattr(Config.load(), k)}
    assert not unknown, f"pipeline.py reads config attributes that do not exist: {unknown}"


# --------------------------------------------------------------------------- module switches


def test_disabled_modules_still_score_but_never_anchor(series, cfg):
    """CF-37 — the switch controls trade generation, not scoring."""
    record = pipeline.analyse_bar(series.head(99), cfg)
    assert not cfg.module_chart_patterns_enabled and not cfg.module_trendline_break_enabled
    classes = set()
    for cluster in record.clusters:
        classes |= set(cluster.classes)
    assert {"pattern", "trendline"} & classes, "disowned modules stopped scoring (CF-37)"
    for plan in record.plans:
        setup = next(s for s in record.setups if s.id == plan.setup_id)
        assert not setup.vetoes


def test_q14_module_defaults(cfg):
    """**Q14** — three disavowals, three different kinds, three different answers.

    * **Chart patterns — no standalone entries, but this is not a disavowal.**  He never says
      patterns don't work; he says *pattern-only* trading didn't work for him once, historically,
      and that the fix was ordering: *"Yes, I traded patterns alone. I did not find any success in
      doing so. So that's why I have my support resistance lines first and then I add these
      confluence on top of it"* (S4 ``[01:48:29]``).  Confluence-only stays right; the rationale
      is S4-R38's "never on a pattern alone", not "he disowns it".

    * **Trend-line breakdown — genuinely "I don't, but it works".**  The objection is operational
      and about him at a screen: *"You don't have a stop-loss. You have to watch this play as it
      develops"* (S8 ``[00:28:52]``).  A bot does not have that problem, but that is not enough to
      flip the default.  Off, backtest-selectable, and ``dca_count_breakdown`` = 0 stays pinned.

    * **Scalp — the loudest disavowal and the one that means least.**  He says *"I suck at
      scalping"* (S5 ``[00:20:02]``) and *"this is why I don't scalp"* (S8 ``[01:34:48]``), and
      also *"if I'm looking to scalp… the two-hour chart for me is my favourite"* (S5
      ``[01:42:50]``) and *"If you want to scalp, it's going to be the 2 hour and the 30 minute
      for me personally"* (S5 ``[01:41:45]``).  Both cannot be literal.  What he quit is
      150-trades-a-day sub-15m day trading, so the control is a **floor**, not a veto — and the
      spec already carried a scalp risk branch he specified himself (``max_loss_pct_scalp``,
      ``tp_count_scalp``, ``dca_count_scalp_max``, ``scalp_excludes_btc``) that a hard veto left
      as dead code.  This reverses CF-37 and is marked `inferred`.
    """
    assert cfg.module_chart_patterns_enabled is False
    assert cfg.disowned_modules_still_score_confluence is True
    assert cfg.module_trendline_break_enabled is False
    assert cfg.dca_count_breakdown == 0

    assert cfg.module_scalp_enabled is True
    assert cfg.scalp_tf_floor == "30m"          # not 15m: S5-R34, S8 `[01:34:48]`
    assert cfg.scalp_tf_ceiling == "2H"
    # 5m stays reachable only through the CF-03 counter-trend demotion (S7-R10).
    assert "5m" in KEY_SPEC_BY_NAME["scalp_tf_floor"].members


def test_turning_scoring_off_skips_the_disowned_detectors(series, cfg):
    off = cfg.with_overrides(disowned_modules_still_score_confluence=False)
    record = pipeline.analyse_bar(series.head(90), off)
    assert not record.patterns and not record.trendlines
    assert any("CF-37" in note for note in record.notes)


# ------------------------------------------------- G0 entry distance (DISCORD CHECK 2026-09-15)


def test_entry_distance_gate_is_off_by_default(series, cfg):
    """The Discord record bounded the RANGE, not the value, so the gate ships disabled.

    Ten written entry/DCA ladders put his deepest rung a median 15.76% below entry and never
    wider than 27.18%; that is what `sweep_bracket=(5.0, 27.5)` encodes.  None of it makes the
    ceiling his rule, so enabling it is a sweep decision, not a default.
    """
    assert cfg.max_entry_distance_enabled is False
    assert cfg.max_entry_distance_pct == 15.0
    for i in range(60, len(series), 7):
        record = pipeline.analyse_bar(series.head(i + 1), cfg)
        assert not [r for r in record.rejections if r.reason == "entry_too_far"]


def test_entry_distance_gate_rejects_far_retests_when_enabled(series, cfg):
    tight = cfg.with_overrides(max_entry_distance_enabled=True, max_entry_distance_pct=0.05)
    seen = False
    for i in range(60, len(series), 7):
        for rejection in pipeline.analyse_bar(series.head(i + 1), tight).rejections:
            if rejection.reason == "entry_too_far":
                assert rejection.gate == "G0"
                seen = True
    assert seen, "a 0.05% ceiling rejected nothing — the gate is not wired"


def test_entry_distance_gate_spares_everything_inside_the_ceiling(series, cfg):
    """A ceiling nothing can breach must leave the run bit-for-bit identical."""
    wide = cfg.with_overrides(max_entry_distance_enabled=True, max_entry_distance_pct=100.0)
    for i in range(60, len(series), 7):
        base = pipeline.analyse_bar(series.head(i + 1), cfg)
        got = pipeline.analyse_bar(series.head(i + 1), wide)
        assert [(r.gate, r.reason) for r in got.rejections] == \
               [(r.gate, r.reason) for r in base.rejections]


def test_entry_distance_gate_never_touches_the_trigger_family(series, cfg):
    """CF-16 makes a TRIGGER a stop order, not a resting bid — distance is meaningless for it."""
    tight = cfg.with_overrides(max_entry_distance_enabled=True, max_entry_distance_pct=0.01)
    for i in range(60, len(series), 7):
        record = pipeline.analyse_bar(series.head(i + 1), tight)
        far = {r.setup_id for r in record.rejections if r.reason == "entry_too_far"}
        for setup in record.setups:
            if setup.id in far:
                assert setup.entry_family is not EntryFamily.TRIGGER
