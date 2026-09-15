"""Human wording for the §7.1 gate stack, for the "Rejected" panel.

The point of that panel is not debugging.  It is the one place where a trader can see *which of
his own rules is doing the vetoing* and decide whether it is too strict — so every entry here
answers three questions: what the gate checks, which config keys move it, and what loosening it
would cost.  ``config_keys`` are real key names from the 252 (INTERFACES.md §4), so the Settings
panel can offer exactly the knobs that would change a given rejection group.

Nothing here is a rule.  It is wording over ``tbot.qualify``'s own gate ids and reason strings.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

__all__ = ["GATES", "REASONS", "describe_gate", "describe_reason", "group_rejections"]


def _g(gate: str, title: str, what: str, keys: Sequence[str], loosening: str,
       source_ids: Sequence[str] = ()) -> dict[str, Any]:
    return {"gate": gate, "title": title, "what": what, "config_keys": list(keys),
            "loosening": loosening, "source_ids": list(source_ids)}


#: gate id -> plain-English card.  Ordered as §7.1 evaluates them.
GATES: dict[str, dict[str, Any]] = {row["gate"]: row for row in [
    _g("G0", "Pre-gate — geometry",
       "The setup never got as far as the rule stack: the anchoring object sits on the wrong "
       "side of price, or the plan could not be constructed at all.",
       [], "Nothing to loosen. These are structurally impossible setups, not strict rules.",
       ["SPEC-3.1"]),
    _g("G1", "Universe tier",
       "The coin is outside the tier you trade with leverage — market-cap rank, daily volume, "
       "or the wick/barcode liquidity screen. Memecoins and new listings are demoted to spot "
       "rather than excluded. BTC is excluded from the scalp module.",
       ["leverage_max_mcap_rank", "min_daily_volume_usd", "memecoin_vehicle",
        "new_listing_days", "scalp_excludes_btc", "max_median_wick_ratio",
        "max_wicky_bar_fraction"],
       "Loosening trades into thinner books: worse fills and stops that get wicked.",
       ["CF-40", "P18", "S8-R32"]),
    _g("G2", "Watchlist size",
       "You are already carrying the maximum number of concurrent coins. The cap exists so you "
       "actually learn each coin's levels instead of half-watching ten.",
       ["universe_max_symbols"],
       "Raising it means more setups but less attention on each.",
       ["S8-R33"]),
    _g("G3", "Event blackout",
       "The setup lands inside a scheduled-event window (FOMC, CPI, and similar). Leverage is "
       "blocked; spot dip-buying is still allowed.",
       ["event_blackout_hours", "event_blackout_mode", "event_resume_requires_range",
        "event_tf_step_up"],
       "Shorter windows means trading into scheduled volatility.",
       ["CF-39", "S8-R2"]),
    _g("G4", "Weekend gate",
       "The setup is on a weekend bar. Thin weekend books move stops that weekday books would "
       "not. Leverage-scoped by default.",
       ["weekend_mode"],
       "Set weekend_mode to allow, and weekend liquidity becomes your problem.",
       ["CF-39", "S5-R37", "TBOT1-R24"]),
    _g("G5", "Confluence / conviction",
       "Not enough independent reasons stacked at that price. The gate counts distinct object "
       "classes (support/resistance, zone, order block, fib, ...), the weights only rank them.",
       ["min_confluence_count", "confluence_gate_mode", "single_class_trade_forbidden",
        "confluence_weights", "confluence_merge_atr", "confluence_dedup_same_class"],
       "This is the main strictness dial. Lowering it is the fastest way to more trades and "
       "the fastest way to worse ones.",
       ["CF-31", "P14"]),
    _g("G6", "Mid-range",
       "Price is in the middle of a range — the chop between the edges, where there is no "
       "level to lean on.",
       ["mid_range_band_pct", "range_boundary_touch_limit"],
       "Trading mid-range means entries with no defined invalidation.",
       ["CF-25", "CF-26", "P7"]),
    _g("G7", "Regime / context",
       "The cross-market context vetoed it: BTC or total-market risk-off, a hard context veto, "
       "or a volatility window that blocks new alt longs.",
       ["dxy_gate_min_rolling_corr", "dxy_gate_enabled"],
       "Overriding regime means taking alt longs while the market that drives them is falling.",
       ["SPEC-7.2"]),
    _g("G8", "Higher-timeframe veto",
       "The higher timeframe disagrees with the direction — you would be trading against the "
       "structure that decides where price goes next.",
       ["swing_tf_floor", "scalp_tf_floor", "scalp_tf_ceiling"],
       "Ignoring the HTF is the classic way to be right on the 15m and wrong on the trade.",
       ["CF-24"]),
    _g("G9", "Shorting policy",
       "A short was blocked: shorts disabled, net short in an uptrend, or shorting into price "
       "discovery.",
       ["shorts_enabled", "net_short_allowed_in_uptrend", "short_in_price_discovery"],
       "Enabling shorts in an uptrend means fighting the trend on purpose.",
       ["CF-41"]),
    _g("G10", "Shorting policy (price discovery)",
       "A short into all-time-high price discovery, where there is no overhead structure to "
       "sell into.",
       ["short_in_price_discovery"],
       "There is no resistance above an all-time high, by definition.",
       ["CF-41"]),
    _g("G11", "Object liveness / touch limit",
       "The zone or order block anchoring the setup is dead — filled past its invalidation "
       "percentage — or the level has been touched too many times to still be worth trading.",
       ["zone_fill_invalidation_pct", "ob_fill_invalidation_pct", "line_touch_hard_limit",
        "dead_zone_rescue_max_touches", "zone_touch_uses_fill_rule_not_count", "touch_reset_atr"],
       "A level that has been hit four times is not a level any more; loosening this is how "
       "you end up buying a support that is really a shelf about to break.",
       ["CF-07", "CF-08"]),
    _g("G12", "Stop placement",
       "No valid stop could be placed behind the structure that invalidates the idea.",
       ["stop_buffer_atr", "stop_buffer_zone_fraction"],
       "A stop you cannot place structurally is a trade with no invalidation.",
       ["CF-14"]),
    _g("G13", "Stop too tight",
       "The stop came out on the wrong side of, or too close to, the sizing reference — the "
       "trade would be stopped out by noise before the idea had a chance.",
       ["stop_buffer_atr", "stop_buffer_zone_fraction", "min_zone_depth_atr"],
       "Widening the buffer fixes the geometry but costs R on every trade.",
       ["CF-14", "CF-18"]),
    _g("G14", "Risk:reward",
       "The plan did not reach the minimum R:R from the entry to the take-profit "
       "`rr_measured_to` names — since F9 the FINAL take-profit, which is where his own "
       "position tool's R:R readout measures to. Set it to `tp1` for the stricter old basis.",
       ["min_rr", "rr_measured_from", "rr_measured_to"],
       "This is the second big dial. Dropping min_rr below 2 means your win rate has to carry "
       "the whole system — and four observed trades of his run 2.13-5.00, so 2.0 is a floor "
       "under all of them.",
       ["CF-42"]),
    _g("G15", "Expected move",
       "The move to target is too small for the trade class to be worth the fees, the slippage "
       "and the attention.",
       ["min_expected_move_pct"],
       "Lowering it fills the book with trades whose edge fees eat.",
       ["CF-41", "S3-R15"]),
    _g("G16", "Not enough take-profits",
       "Fewer structural levels above (or below) than the minimum number of take-profits, so "
       "there was nowhere to scale out.",
       ["tp_min_count"],
       "Fewer TPs means more of the position riding to a single target.",
       ["CF-27", "CF-28"]),
    _g("G17", "Portfolio capacity",
       "Concurrency, deployment or daily-loss caps are full. This is the risk layer refusing "
       "to add exposure, not the setup being bad.",
       ["max_concurrent_leverage_swing", "max_concurrent_leverage_scalp",
        "max_concurrent_leverage_global", "max_concurrent_spot"],
       "Raising caps raises correlated drawdown, not expected return.",
       ["CF-04"]),
    _g("G18", "Module switch",
       "The detector family that would have produced this setup is switched off in config.",
       ["module_chart_patterns_enabled", "module_trendline_break_enabled",
        "module_scalp_enabled", "disowned_modules_still_score_confluence"],
       "Switching a disabled module back on re-enables rules that ship off for a reason.",
       ["CF-37"]),
]}

#: reason string -> a sentence.  Reasons come from ``tbot.qualify`` verbatim; anything not
#: listed falls back to the reason with underscores turned into spaces.
REASONS: dict[str, str] = {
    "anchor_beyond_price": "the anchoring object is already on the far side of price",
    "event_blackout": "inside a scheduled-event blackout window",
    "weekend_blocked": "weekend bar, and weekend_mode blocks leverage",
    "insufficient_confluence": "fewer confluence classes than min_confluence_count",
    "single_class_trade": "every confluence object came from one class",
    "low_conviction": "below the conviction floor the caller asked for",
    "mid_range": "price sits in the mid-range band",
    "htf_veto": "the higher timeframe disagrees with this direction",
    "object_dead": "the anchoring zone or order block is filled past its invalidation",
    "touch_limit": "the level is over its touch limit",
    "stop_too_tight": "the stop lands on the wrong side of the sizing reference",
    "stop_unplaceable": "no structural stop could be placed",
    "insufficient_tps": "fewer structural take-profits than tp_min_count",
    "capacity": "concurrency, deployment or daily-loss cap is full",
    "rr_below_min": "risk:reward below min_rr",
    "expected_move_too_small": "expected move below the class minimum",
    "shorts_disabled": "shorts_enabled is false",
    "short_in_uptrend": "net short while the trend is up",
    "short_in_price_discovery": "short into price discovery",
    "scalp_excludes_btc": "BTC is excluded from the scalp module",
    "universe_tier": "outside the leverage universe tier",
    "too_many_symbols": "already at the concurrent-symbol cap",
    "module_disabled": "the detector family is switched off",
    "plan_not_constructible": "the plan could not be built from this geometry",
}


def describe_gate(gate: str) -> dict[str, Any]:
    """Never raises: an unknown gate id still gets a usable card."""
    known = GATES.get(gate)
    if known is not None:
        return dict(known)
    return _g(gate, f"Gate {gate}", "No description registered for this gate id.", [],
              "Unknown gate — check tbot.qualify for its wording.")


def describe_reason(reason: str) -> str:
    return REASONS.get(reason, (reason or "").replace("_", " "))


def group_rejections(rejections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group serialized rejections by gate, then by reason, biggest group first.

    The counts are the point: "G5 killed 31 of 47" is the sentence that tells you a gate is
    doing the work, and "G4 killed 47 of 47" tells you it is simply the weekend.
    """
    by_gate: dict[str, dict[str, Any]] = {}
    for rec in rejections:
        gate = str(rec.get("gate") or "?")
        bucket = by_gate.get(gate)
        if bucket is None:
            bucket = describe_gate(gate)
            bucket.update({"count": 0, "reasons": {}, "examples": []})
            by_gate[gate] = bucket
        bucket["count"] += 1
        reason = str(rec.get("reason") or "")
        reasons = bucket["reasons"]
        entry = reasons.get(reason)
        if entry is None:
            entry = {"reason": reason, "text": describe_reason(reason), "count": 0,
                     "source_ids": [], "examples": []}
            reasons[reason] = entry
        entry["count"] += 1
        if len(entry["examples"]) < 5:
            entry["examples"].append({
                "setup_id": rec.get("setup_id"),
                "symbol": rec.get("symbol"),
                "direction": rec.get("direction"),
                "time": rec.get("time"),
                "detail": rec.get("detail") or "",
                "source_ids": list(rec.get("source_ids") or ())[:14],
            })
        for sid in list(rec.get("source_ids") or ())[:14]:
            if sid not in entry["source_ids"]:
                entry["source_ids"].append(sid)

    out: list[dict[str, Any]] = []
    total = sum(b["count"] for b in by_gate.values()) or 1
    for bucket in by_gate.values():
        bucket["reasons"] = sorted(bucket["reasons"].values(),
                                   key=lambda r: (-r["count"], r["reason"]))
        bucket["share_pct"] = round(bucket["count"] / total * 100.0, 1)
        out.append(bucket)
    out.sort(key=lambda b: (-b["count"], b["gate"]))
    return out
