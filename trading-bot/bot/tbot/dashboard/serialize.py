"""``PipelineRun`` -> JSON the browser can draw, with provenance attached to everything.

Two rules run through this module:

1. **Every object carries its ``source_ids``.**  INTERFACES.md §1.6 makes that a property of the
   engine's output; here it becomes a property of the API, so no number can reach the screen
   without the rule chain that produced it travelling alongside it.
2. **Bar indices become timestamps.**  A ``*_index`` is positional in one Series on one
   timeframe (INTERFACES.md §2) and means nothing to a chart.  Every index is mapped through
   ``series.timestamp(i)`` to epoch seconds, and the raw index is kept beside it for the
   expandable detail views.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from tbot.models import Level, LevelKind, OrderBlock, Series, Setup, TradePlan, Zone

__all__ = ["jsonable", "serialize_run", "watchlist_row"]


# --------------------------------------------------------------------------- primitives


def jsonable(value: Any) -> Any:
    """Decimal -> float, Enum -> its value, containers recursively.  Deterministic ordering."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(jsonable(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _f(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


class _Clock:
    """index -> epoch seconds, clamped.  One per serialised run."""

    __slots__ = ("times", "step", "n")

    def __init__(self, series: Series) -> None:
        self.times = [int(ts.timestamp()) for ts in series.timestamps]
        self.n = len(self.times)
        tf_minutes = series.tf.minutes
        self.step = tf_minutes * 60

    def at(self, index: int | None) -> int | None:
        if index is None or self.n == 0:
            return None
        i = int(index)
        if i < 0:
            i = max(0, self.n + i)
        if i < self.n:
            return self.times[i]
        # a future index (a plan expiry, a box extended to the right edge)
        return self.times[-1] + (i - (self.n - 1)) * self.step


# --------------------------------------------------------------------------- objects


def _zone(zone: Zone, clock: _Clock) -> dict[str, Any]:
    return {
        "id": zone.id,
        "kind": "zone",
        "side": zone.side.value,                 # demand | supply
        "zone_class": zone.zone_class.value,     # continuation | reversal
        "top": _f(zone.box_top),
        "bottom": _f(zone.box_bottom),
        "midpoint": _f(zone.midpoint),
        "start_index": zone.formation_start_index,
        "end_index": zone.breakout_index,
        "start_time": clock.at(zone.formation_start_index),
        "breakout_time": clock.at(zone.breakout_index),
        "body_count": zone.body_count,
        "move_away_pct": _f(zone.move_away_pct),
        "move_away_atr": _f(zone.move_away_atr),
        "depth_atr": _f(zone.depth_atr),
        "fill_pct": _f(zone.fill_pct),
        "is_dead": bool(zone.is_dead),
        "rescued_by_level_id": zone.rescued_by_level_id,
        "touch_count": zone.touch_count,
        "contained_ob_ids": list(zone.contained_ob_ids),
        "entry_price_pmt": _f(zone.entry_price_pmt),
        # F1 nested geometry — both null unless ``zone_wick_band_enabled`` is on.
        "wick_band_top": _f(zone.wick_band_top),
        "wick_band_bottom": _f(zone.wick_band_bottom),
        "source_ids": list(zone.source_ids),
    }


def _order_block(ob: OrderBlock, clock: _Clock) -> dict[str, Any]:
    return {
        "id": ob.id,
        "kind": "order_block",
        "side": ob.side.value,                   # bullish | bearish
        "top": _f(ob.box_top),
        "bottom": _f(ob.box_bottom),
        "bar_index": ob.bar_index,
        "start_time": clock.at(ob.bar_index),
        "end_index": ob.dir_change_index,
        "breakout_time": clock.at(ob.dir_change_index),
        "dir_change_atr_move": _f(ob.dir_change_atr_move),
        "liquidity_taken_pct": _f(ob.liquidity_taken_pct),
        "fill_pct": _f(ob.fill_pct),
        "is_dead": bool(ob.is_dead),
        "parent_zone_id": ob.parent_zone_id,
        "size_atr": _f(ob.size_atr),
        "source_ids": list(ob.source_ids),
    }


def _level(level: Level, clock: _Clock, *, now: int) -> dict[str, Any]:
    sloped = level.kind is LevelKind.TRENDLINE or level.slope_per_bar != 0
    row: dict[str, Any] = {
        "id": level.id,
        "kind": "level",
        "level_kind": level.kind.value,
        "price": _f(level.price),
        "created_index": level.created_index,
        "created_time": clock.at(level.created_index),
        "touch_count": level.touch_count,
        "touch_times": [clock.at(i) for i, _ in level.touch_history],
        "touch_prices": [_f(p) for _, p in level.touch_history],
        "flip_state": level.flip_state.value,
        "pending_since_index": level.pending_since_index,
        "is_untested_sr": bool(level.is_untested_sr),
        "tolerance": _f(level.tolerance),
        "sloped": bool(sloped),
        "member_pivot_ids": list(level.member_pivot_ids),
        "source_ids": list(level.source_ids),
    }
    if sloped:
        anchors = level.anchor_indices or [level.created_index, now]
        a, b = min(anchors), max(max(anchors), now)
        row["from"] = {"time": clock.at(a), "price": _f(level.price_at(a)), "index": a}
        row["to"] = {"time": clock.at(b), "price": _f(level.price_at(b)), "index": b}
    return row


def _fib(fib: Any, clock: _Clock) -> dict[str, Any]:
    return {
        "id": fib.id,
        "kind": "fib",
        "ratio": _f(fib.ratio),
        "price": _f(fib.price),
        "direction": fib.direction.value,
        "in_golden_pocket": bool(fib.in_golden_pocket),
        "anchor_low_time": clock.at(fib.anchor_low_index),
        "anchor_high_time": clock.at(fib.anchor_high_index),
        "source_ids": list(fib.source_ids),
    }


def _range(rng: Any, clock: _Clock) -> dict[str, Any]:
    return {
        "kind": "range",
        "id": rng.id,
        "high": _f(rng.high),
        "low": _f(rng.low),
        "mid": _f(rng.mid.price) if rng.mid is not None else None,
        "mid_band": ([_f(rng.mid.band_low), _f(rng.mid.band_high)]
                     if rng.mid is not None else None),
        "start_index": rng.start_index,
        "end_index": rng.end_index,
        "start_time": clock.at(rng.start_index),
        "end_time": clock.at(rng.end_index),
        "dead": bool(rng.dead),
        "stale": bool(rng.stale),
        "provisional": bool(rng.provisional),
        "broken_side": rng.broken_side,
        "source_ids": list(rng.source_ids),
    }


def _plan(plan: TradePlan, setup: Setup | None, clock: _Clock,
          last_price: float | None) -> dict[str, Any]:
    entries = [{
        "index": r.index,
        "kind": r.kind,
        "price": _f(r.price),
        "size_fraction": _f(r.size_fraction),
        "size_pct": round(float(r.size_fraction) * 100.0, 2),
        "level_id": r.level_id,
        "filled": bool(r.filled),
    } for r in plan.entries]
    tps = [{
        "index": t.index,
        "price": _f(t.price),
        "size_fraction": _f(t.size_fraction),
        "size_pct": round(float(t.size_fraction) * 100.0, 2),
        "level_id": t.level_id,
        "hit": bool(t.hit),
    } for t in plan.take_profits]

    row: dict[str, Any] = {
        "id": plan.id,
        "setup_id": plan.setup_id,
        "symbol": plan.symbol,
        "direction": plan.direction.value,
        "trade_class": plan.trade_class.value,
        "vehicle": plan.vehicle.value,
        "leverage": _f(plan.leverage),
        "entries": entries,
        "stop_price": _f(plan.stop_price),
        "stop_is_synthetic": bool(plan.stop_is_synthetic),
        "spot_exit_rule": plan.spot_exit_rule,
        "take_profits": tps,
        "qty_total": _f(plan.qty_total),
        "notional_usd": _f(plan.notional_usd),
        "risk_budget_pct": _f(plan.risk_budget_pct),
        "average_entry": _f(plan.average_entry),
        "planned_average_entry": _f(plan.planned_average_entry),
        "rr_to_tp1": _f(getattr(plan, "rr_to_tp1", None)),
        # F9: both ratios ship, so the chart can show the one the G14 gate actually reads.
        "rr_to_final_tp": _f(getattr(plan, "rr_to_final_tp", None)),
        "expected_move_pct": _f(plan.expected_move_pct),
        "invalidation_level_id": plan.invalidation_level_id,
        "bias_invalidation_price": _f(plan.bias_invalidation_price),
        "expires_at_index": plan.expires_at_index,
        "expires_at_time": clock.at(plan.expires_at_index),
        "source_ids": list(plan.source_ids),
        "last_price": last_price,
    }
    if setup is not None:
        row["setup"] = _setup(setup, clock)
        row["conviction"] = setup.conviction.value
        row["confluence_score"] = _f(setup.confluence_score)
        row["confluence_classes"] = sorted(setup.confluence_classes)
        row["entry_family"] = setup.entry_family.value
    if last_price and plan.planned_average_entry:
        avg = float(plan.planned_average_entry)
        row["distance_to_entry_pct"] = round((avg - last_price) / last_price * 100.0, 3)
    return row


def _setup(setup: Setup, clock: _Clock) -> dict[str, Any]:
    return {
        "id": setup.id,
        "symbol": setup.symbol,
        "direction": setup.direction.value,
        "trade_tf": setup.trade_tf.value,
        "structure_tf": setup.structure_tf.value,
        "trade_class": setup.trade_class.value,
        "anchor_price": _f(setup.anchor_price),
        "created_index": setup.created_index,
        "created_time": clock.at(setup.created_index),
        "object_ids": list(setup.object_ids),
        "confluence_score": _f(setup.confluence_score),
        "confluence_classes": sorted(setup.confluence_classes),
        "entry_family": setup.entry_family.value,
        "conviction": setup.conviction.value,
        "vetoes": list(setup.vetoes),
        "qualified": not setup.vetoes,
        "regime_flags": jsonable(setup.regime_flags),
        "source_ids": list(setup.source_ids),
    }


def _cluster(cluster: Any) -> dict[str, Any]:
    return {
        "price": _f(cluster.price),
        "score": _f(cluster.score),
        "count": cluster.count,
        "classes": sorted(cluster.classes),
        "conviction": cluster.conviction.value,
        "qualified": bool(cluster.qualified),
        "bonus": _f(cluster.bonus),
        "tf": cluster.tf.value if cluster.tf is not None else None,
        "reasons": list(cluster.reasons),
        "contributors": [
            {"id": o.id, "price": _f(o.price), "class": o.obj_class,
             "weight": _f(o.weight), "tf": o.tf.value if o.tf is not None else None,
             "source_ids": list(o.source_ids)}
            for o in cluster.contributors
        ],
        "source_ids": list(cluster.source_ids),
    }


def _regime(regime: Any) -> dict[str, Any] | None:
    if regime is None:
        return None
    return {
        "state": jsonable(regime.state),
        "risk_on": bool(regime.risk_on),
        "hard_veto": bool(regime.hard_veto),
        "blocks_new_alt_longs": bool(regime.blocks_new_alt_longs),
        "size_multiplier": _f(regime.size_multiplier),
        "spot_size_multiplier": _f(regime.spot_size_multiplier),
        "veto_reasons": list(regime.veto_reasons),
        "degraded": bool(regime.degraded),
        "adverse": bool(regime.adverse),
        "missing": list(regime.missing),
        "notes": list(regime.notes),
        "source_ids": list(regime.source_ids),
    }


# --------------------------------------------------------------------------- the run


def serialize_run(run: Any, *, last_price: float | None = None,
                  candle_limit: int = 600) -> dict[str, Any]:
    """The whole analysis of one closed bar, as JSON.

    ``run`` is a :class:`tbot.pipeline.PipelineRun`.  The chart draws ``overlays`` and the
    panels read ``plans`` / ``setups`` / ``rejections``; ``meta`` carries the bar the analysis
    stands on so the UI can prove to itself that what it shows matches what it drew.
    """
    series: Series = run.series
    clock = _Clock(series)
    setups_by_id = {s.id: s for s in run.setups}
    first_visible = max(0, len(series) - int(candle_limit))

    zones = [_zone(z, clock) for z in run.zones]
    obs = [_order_block(o, clock) for o in run.order_blocks]
    levels = [_level(l, clock, now=run.now) for l in run.levels]
    trendlines = [_level(l, clock, now=run.now) for l in run.trendlines]
    range_levels = [_level(l, clock, now=run.now) for l in run.range_levels]

    plans = [_plan(p, setups_by_id.get(p.setup_id), clock, last_price) for p in run.plans]

    rejections = [{
        "bar_index": r.bar_index,
        "time": clock.at(r.bar_index),
        "setup_id": r.setup_id,
        "gate": r.gate,
        "reason": r.reason,
        "symbol": r.symbol or series.symbol,
        "direction": r.direction.value if r.direction is not None else None,
        "source_ids": list(r.source_ids),
        "detail": _veto_detail(setups_by_id.get(r.setup_id)),
    } for r in run.rejections]

    detections = [{
        "bar_index": d.bar_index, "time": clock.at(d.bar_index), "detector": d.detector,
        "object_id": d.object_id, "obj_class": d.obj_class, "source_ids": list(d.source_ids),
    } for d in run.detections]

    return {
        "symbol": series.symbol,
        "timeframe": series.tf.value,
        "meta": {
            "bars": len(series),
            "now_index": run.now,
            "bar_time": clock.at(run.now),
            "bar_iso": run.timestamp.isoformat(),
            "last_close": float(series.close[-1]),
            "last_price": last_price,
            "first_visible_time": clock.at(first_visible),
            "stages_run": list(run.stages_run),
            "notes": list(run.notes),
            "price_discovery": bool(run.price_discovery),
            "in_mid_range_band": bool(run.in_mid_range_band),
        },
        "trend": jsonable(run.trend),
        "structure_trend": jsonable(run.structure_trend),
        "regime": _regime(run.regime),
        "liquidity": ({
            "passes": bool(run.liquidity.passes), "tier": run.liquidity.tier,
            "wick_heavy": bool(run.liquidity.wick_heavy),
            "median_quote_volume_usd": _f(run.liquidity.median_quote_volume_usd),
            "reasons": list(run.liquidity.reasons),
        } if run.liquidity is not None else None),
        "bias_level": (_level(run.bias_level, clock, now=run.now)
                       if run.bias_level is not None else None),
        "overlays": {
            "zones": zones,
            "order_blocks": obs,
            "levels": levels,
            "trendlines": trendlines,
            "range_levels": range_levels,
            "fibs": [_fib(f, clock) for f in run.fibs],
            "ranges": [_range(r, clock) for r in run.ranges],
        },
        "plans": plans,
        "setups": [_setup(s, clock) for s in run.setups],
        "clusters": [_cluster(c) for c in run.clusters],
        "rejections": rejections,
        "detections": detections,
    }


def _veto_detail(setup: Setup | None) -> str:
    if setup is None or not setup.vetoes:
        return ""
    return str(setup.vetoes[0])


# --------------------------------------------------------------------------- watchlist


def watchlist_row(symbol: str, tf: str, payload: Mapping[str, Any] | None, *,
                  last_price: float | None, status: str, error: str = "") -> dict[str, Any]:
    """One row of the watchlist: regime, trend, nearest zone, distance, live setup.

    Distances are signed percentages **from the last price to the zone's outer edge** — the
    edge price reaches first (``Zone.outer_edge``, INTERFACES.md §3), which is the number a
    trader actually waits for, not the midpoint.
    """
    row: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": tf,
        "status": status,
        "error": error,
        "last_price": last_price,
        "trend": None,
        "structure_trend": None,
        "regime": None,
        "regime_risk_on": None,
        "nearest_zone": None,
        "distance_pct": None,
        "live_setups": 0,
        "qualified_setups": 0,
        "rejections": 0,
        "best_conviction": None,
        "bar_time": None,
    }
    if not payload:
        return row

    row["trend"] = payload.get("trend")
    row["structure_trend"] = payload.get("structure_trend")
    regime = payload.get("regime")
    if regime:
        row["regime"] = regime.get("state")
        row["regime_risk_on"] = regime.get("risk_on")
    row["bar_time"] = (payload.get("meta") or {}).get("bar_time")

    plans = payload.get("plans") or []
    row["live_setups"] = len(plans)
    row["qualified_setups"] = len([s for s in payload.get("setups") or [] if s.get("qualified")])
    row["rejections"] = len(payload.get("rejections") or [])
    order = {"high": 3, "normal": 2, "low": 1}
    if plans:
        row["best_conviction"] = max(
            (p.get("conviction") for p in plans if p.get("conviction")),
            key=lambda c: order.get(str(c), 0), default=None)

    price = last_price if last_price is not None else (payload.get("meta") or {}).get("last_close")
    zones = [z for z in (payload.get("overlays") or {}).get("zones", []) if not z.get("is_dead")]
    if price and zones:
        def edge(z: Mapping[str, Any]) -> float:
            # the edge price reaches first: top for demand (approached from above),
            # bottom for supply (approached from below)
            return float(z["top"] if z["side"] == "demand" else z["bottom"])

        nearest = min(zones, key=lambda z: abs(edge(z) - price))
        e = edge(nearest)
        row["nearest_zone"] = {
            "id": nearest["id"], "side": nearest["side"], "zone_class": nearest["zone_class"],
            "edge": e, "top": nearest["top"], "bottom": nearest["bottom"],
            "fill_pct": nearest["fill_pct"], "touch_count": nearest["touch_count"],
            "source_ids": nearest["source_ids"],
        }
        row["distance_pct"] = round((e - price) / price * 100.0, 3)
    return row
