"""tbot.config — the complete SPEC.md §11 configuration surface.

Every one of the **245** keys of the tbot configuration surface is a field of :class:`Config`, holding the
documented default.  Each key also has a :class:`KeySpec` row in :data:`KEY_SPECS` carrying its
declared type, its allowed values / numeric range and its **source ID** (the ``CF-nn`` /
``Sn-Rnn`` / ``Pn`` / ``[OUR CHOICE]`` provenance from the spec table).

Design rules honoured here:

* No global mutable state.  :class:`Config` is a frozen, slotted dataclass; ``load`` returns a new
  instance every time and never mutates module state.  Mutable containers (lists / dicts) are
  per-instance copies produced by ``default_factory`` — treat them as read-only.
* Validation reports **every** problem at once through :class:`ConfigError`, never just the first.
* ``Config.describe()`` returns ``(key, value, default, source_id)`` rows for CLI provenance
  printing.

Generated from SPEC.md §11 tables 11.1 – 11.12 (§11.13 = 234) plus the 8 evidence-derived keys of
CHANGELOG_EVIDENCE.md and the 3 frame-derived keys of FRAME_FINDINGS.md (F1 pass 1 ×2, F6 pass 2 ×1),
for 245 in total.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

__all__ = [
    "Config",
    "ConfigError",
    "KeySpec",
    "KEY_SPECS",
    "KEY_SPEC_BY_NAME",
    "TIMEFRAME_LADDER",
    "PIPELINE_STAGES",
    "deep_merge",
    "write_default_yaml",
]

#: The timeframe ladder of SPEC.md §1.2 / CF-24, in ascending order.
TIMEFRAME_LADDER: tuple[str, ...] = (
    "15m", "30m", "1H", "2H", "4H", "8H", "12H", "1D", "2D", "3D", "1W",
)

#: Canonical pipeline stage names (SPEC.md §3.1, stages 0..17) — ``pipeline_order`` must be a
#: permutation of exactly these.
PIPELINE_STAGES: tuple[str, ...] = (
    "universe_calendar_gate", "load_align_candles", "structure", "levels_sr_flips",
    "trend_lines", "ranges_mid_range", "liquidity_map", "supply_demand_zones",
    "order_blocks", "context_regime", "fibs", "chart_patterns", "confluence_scoring",
    "sfp", "rsi_divergence", "ltf_refinement", "setup_qualification",
    "trade_plan_construction",
)


class ConfigError(ValueError):
    """Raised by :meth:`Config.validate` with **all** problems, never only the first.

    ``ConfigError.problems`` is the ordered list of human-readable problem strings; ``str(err)``
    is those problems joined by newlines under a count header.
    """

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems: list[str] = list(problems)
        body = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"{len(self.problems)} configuration problem(s):\n{body}")


@dataclass(frozen=True, slots=True)
class KeySpec:
    """Static metadata for one SPEC.md §11 configuration key."""

    key: str
    default: Any
    spec_type: str          #: the §11 "Type" token, e.g. ``pct``, ``atr``, ``bars``, ``enum``
    py_type: str            #: ``bool`` | ``int`` | ``float`` | ``str`` | ``list`` | ``dict``
    members: tuple[str, ...] | None   #: allowed values for enum/tf keys
    minimum: float | None
    maximum: float | None
    source_id: str          #: provenance, e.g. ``"CF-08; S5-R28, S6-R10"``
    group: str              #: §11 sub-section id, e.g. ``"11.2"``
    note: str = ""
    #: ``(low, high)`` inclusive bracket a parameter sweep should search, when evidence has
    #: bounded one.  ``None`` = no bracket is known and the sweep is open.  Machine-readable on
    #: purpose: a sweep reads the range off the config instead of parsing it out of ``note``
    #: prose.  For list-valued keys the bracket applies to the **first** element.
    sweep_bracket: tuple[float, float] | None = None

    def copy_default(self) -> Any:
        """A fresh copy of the default (containers are copied, scalars returned as-is)."""
        if isinstance(self.default, list):
            return list(self.default)
        if isinstance(self.default, dict):
            return dict(self.default)
        return self.default


KEY_SPECS: tuple[KeySpec, ...] = (
    KeySpec(
        key='max_loss_pct_swing',
        default=4.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-01; S2-R20, S3-R24, S5-R32, S6-R11, S7-R8; F9 corroborates the model',
        group='11.1',
        note='F9 (part B), CORRECTED: the stop-side "Amount" reads 750, but Amount is the account BALANCE at that leg on a $1,000 nominal base, not the money at risk. risk = 1000 - Amount(stop leg) = $250; reward = Amount(target leg) - 1000. Confirmed on five frames across three years: BTC 1H 1792.2, HYPE 4H 2249.04, OM 1H 1741.7, SOL 4H 1531.53, BTC 1D 1651.82 - each Amount-1000 reproduces qty x target distance to within 0.4%, while 750 x R:R misses every one by 18-65%. Independently, qty x stop distance = 250.00 on all EIGHT position-tool frames, 2022-11 to 2025-06. What this corroborates is unchanged: a CONSTANT CASH RISK per trade, which is the risk-first solve of SPEC.md 8.8 (CF-01/CF-02) - quantity comes backwards out of the loss at stop. Corroboration of the MODEL, not of this percentage. The earlier inference that a constant 750 at a 4-5% max loss implies a portfolio of 15,000-18,750 is WITHDRAWN: it was built on the misread field. $250 on the $1,000 nominal base is 25% per trade, which is a teaching template, not a live sizing rule - no frame anywhere shows a real account size. No account-size key is derived from it and none is added. See docs/measurement/CORRECTION-risk-figure-v2.txt.',
    ),
    KeySpec(
        key='max_loss_pct_swing_hard_cap',
        default=5.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-01; S6-R11, TBOT1-R13; F9 corroborates the model',
        group='11.1',
        note='F9 (part B), CORRECTED: the stop-side "Amount" reads 750, but Amount is the account BALANCE at that leg on a $1,000 nominal base, not the money at risk. risk = 1000 - Amount(stop leg) = $250; reward = Amount(target leg) - 1000. Confirmed on five frames across three years: BTC 1H 1792.2, HYPE 4H 2249.04, OM 1H 1741.7, SOL 4H 1531.53, BTC 1D 1651.82 - each Amount-1000 reproduces qty x target distance to within 0.4%, while 750 x R:R misses every one by 18-65%. Independently, qty x stop distance = 250.00 on all EIGHT position-tool frames, 2022-11 to 2025-06. What this corroborates is unchanged: a CONSTANT CASH RISK per trade, which is the risk-first solve of SPEC.md 8.8 (CF-01/CF-02) - quantity comes backwards out of the loss at stop. Corroboration of the MODEL, not of this percentage. The earlier inference that a constant 750 at a 4-5% max loss implies a portfolio of 15,000-18,750 is WITHDRAWN: it was built on the misread field. $250 on the $1,000 nominal base is 25% per trade, which is a teaching template, not a live sizing rule - no frame anywhere shows a real account size. No account-size key is derived from it and none is added. See docs/measurement/CORRECTION-risk-figure-v2.txt.',
    ),
    KeySpec(
        key='max_loss_pct_scalp',
        default=2.5,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-01; S2-R20, S3-R24',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_loss_pct_counter_trend',
        default=2.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-01; Q9 stated 2-3% band, S7 `[00:20:00]`. VIDEO-ONLY, POSSIBLY MISATTRIBUTED. DISCORD CHECK 2026-09-14: absent from the written record — seven session note channels, the linked risk doc, and server-wide `from:arshmeister` search. The written S7 has no risk percentage at all, and 2-3% appears exactly ONCE in the whole written corpus (#class-session-one M3), bound to SCALPS by timeframe (below 4h), not to direction. max_loss_pct_scalp=2.5 already sits inside that band. See CONFLICTS.md.',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_loss_pct_low_conviction',
        default=1.5,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-01; S6-R26',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='high_conviction_loss_pct_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-01; TBOT1-R13',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_notional_pct_leverage',
        default=100.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1000.0,
        source_id='CF-02; Q8 derived, S6 `[00:08:36]`-`[00:11:27]` (was S7-R8, a MARGIN figure)',
        group='11.1',
        note='Q8: notional, not margin. 10% margin x 10x default leverage = 100% of equity. Sweep 73.0 (his accepted worked example) / 155.0 / 200.0 (S3 20% margin at 10x).',
    ),
    KeySpec(
        key='margin_pct_leverage',
        default=10.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-02; Q8 stated, S7 `[00:25:54]` `[00:20:33]`',
        group='11.1',
        note='Q8: the per-trade MARGIN posted on a leverage play. Alternative 20.0 (S3 `[00:04:25]`).',
    ),
    KeySpec(
        key='default_leverage',
        default=10.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=1.0,
        maximum=125.0,
        source_id='CF-02; Q8 stated, S2 `[01:52:12]` ("I always do 10x")',
        group='11.1',
        note='Q8: the leverage assumed when notional/margin does not pin it.',
    ),
    KeySpec(
        key='spot_notional_pct_high_conviction',
        default=12.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-02; S8-R35',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='spot_notional_pct_low_conviction',
        default=6.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-02; S8-R35',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_total_spot_deployment_pct',
        default=70.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-02; S4-R31, S8-R35',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='counter_trend_mode',
        default='size_down_and_demote',
        spec_type='enum',
        py_type='str',
        members=('size_down_and_demote', 'size_down'),
        minimum=None,
        maximum=None,
        source_id='CF-03; Q9 stated, S7 `[00:19:28]` `[00:25:12]` — "veto" struck (it mis-read a pending-order rule, S7 `[00:17:06]`)',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='counter_trend_size_multiplier',
        default=0.5,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1.0,
        source_id='CF-03; Q9 stated, S7 `[00:20:00]` ("use half of your usual amount"); S3-R25, S8-R1',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='counter_trend_demote_to_scalp',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-03; Q9 stated, S7 `[00:25:12]` `[00:26:26]` ("these will be scalp plays")',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_concurrent_leverage_swing',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-04; S4-R30, S2-R32',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_concurrent_leverage_scalp',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-04; S4-R30',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_concurrent_leverage_global',
        default=4,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-04; S4-C8',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_concurrent_spot',
        default=5,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-04; S4-R31',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='spot_exit_mode',
        default='close_below_level_then_flip',
        spec_type='enum',
        py_type='str',
        members=('close_below_level_then_flip', 'close_below_level', 'hard_stop'),
        minimum=None,
        maximum=None,
        source_id='CF-05; S8-R36, TBOT1-R18',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='spot_synthetic_stop_for_sizing',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-05 — our construct',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='spot_invalidation_timeframe',
        default='1D',
        spec_type='tf',
        py_type='str',
        members=('1D', '15m', '30m', '1H', '2H', '4H', '8H', '12H', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='CF-05; TBOT1-R18',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='duplicate_stop_offset_bps',
        default=1.5,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-05; S4-R34',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='max_stop_pct_leverage',
        default=9.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-06; S7-R7, S6 `[00:08:04]`',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='wide_stop_policy',
        default='tighten_then_downgrade_then_skip',
        spec_type='enum',
        py_type='str',
        members=('tighten_then_downgrade_then_skip', 'size_down_only', 'skip'),
        minimum=None,
        maximum=None,
        source_id='CF-06; S4-R16, S5-R24, TBOT1-R7',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='stop_tighten_tf_steps',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-06; S4-R16, S8 `[01:21:46]`',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='min_stop_pct',
        default=0.5,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-06; S7-C8',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='leverage_downgrade_max_multiple',
        default=3.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-06 ("low leverage" unquantified, TBOT1-A7) — [OUR CHOICE]',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='hedge_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='S4-R35 — default is [OUR CHOICE]',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='hedge_size_ratio',
        default=1.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='S4-R35',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='hedge_max_leverage',
        default=3.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='S4-R35',
        group='11.1',
        note='',
    ),
    KeySpec(
        key='line_touch_hard_limit',
        default=3,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-07; Q2 derived, S5 `[00:24:35]` `[00:25:40]` — touches 1-3 play, the 4th is vetoed',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='range_boundary_touch_limit',
        default=6,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-07; Q2 stated, S4 `[00:44:55]` ("five touches, I\'m going to keep taking this trade")',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='touch_size_decay',
        default=[1.0, 1.0, 1.0, 0.66, 0.5],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-07; Q2 inferred — shifted one index right; the only indexed reduction he gives is the 5th touch, S8 `[00:54:14]`',
        group='11.2',
        note='Q2 [INFERRED]: the 3rd touch is "a great area" (S7 `[00:08:22]`), so it must not be cut. Curve shape remains OURS - sweep flat / [1,1,.66,.5,.33] / [1,1,1,.66,.5] / [1,.75,.5,.25,0].',
    ),
    KeySpec(
        key='zone_touch_uses_fill_rule_not_count',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-07; Q2 derived, S6 `[00:52:38]` (same zone played three times, stopped by the fill line)',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='zone_fill_invalidation_pct',
        default=50.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-08; Q1 stated, S5 `[00:38:52]` `[00:41:10]` — multi-candle zones ONLY',
        group='11.2',
        note='Q1: scoped to supply/demand zones. Single-candle order blocks use ob_fill_invalidation_pct (70-80%).',
    ),
    KeySpec(
        key='zone_fill_measure',
        default='wick_touch',
        spec_type='enum',
        py_type='str',
        members=('wick_touch', 'close_beyond'),
        minimum=None,
        maximum=None,
        source_id='CF-08, P6; Q1 inferred (he says "pierced through", S5 `[01:23:02]`; never "wick"/"close")',
        group='11.2',
        note='Q1 [INFERRED]: sweep wick_touch vs close_beyond.',
    ),
    KeySpec(
        key='zone_fill_reference',
        default='as_originally_drawn',
        spec_type='enum',
        py_type='str',
        members=('as_originally_drawn', 'remeasured_after_each_touch'),
        minimum=None,
        maximum=None,
        source_id='CF-08, P6; S5-A11',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='dead_zone_htf_support_rescue',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-08; Q1 stated, S7 `[00:08:22]` (a fully-taken OB is playable on an independent HTF support)',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='dead_zone_rescue_max_touches',
        default=3,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-08; S7-R4',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='ob_max_candles',
        default=1,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='CF-09; S6-R3',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='ob_box_source',
        default='body_with_small_wick',
        spec_type='enum',
        py_type='str',
        members=('body_with_small_wick', 'body_only', 'full_range'),
        minimum=None,
        maximum=None,
        source_id='CF-09, P5; S6-R9',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='ob_inside_zone_precedence',
        default='zone_wins',
        spec_type='enum',
        py_type='str',
        members=('zone_wins', 'ob_wins'),
        minimum=None,
        maximum=None,
        source_id='CF-09; Q5 stated, S6 `[01:07:32]` ("demand zone over the order block")',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='ob_liquidity_measure',
        default='deepest_wick_through_body_range',
        spec_type='enum',
        py_type='str',
        members=('deepest_wick_through_body_range',),
        minimum=None,
        maximum=None,
        source_id='P15; S7-A2 — measure is [OUR CHOICE], the threshold it feeds is stated (ob_fill_invalidation_pct)',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='ob_fill_invalidation_pct',
        default=75.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-08, P15; Q1 stated, S7 `[00:07:14]`-`[00:08:54]` ("my rule for order blocks are like around 70 80%"). VIDEO-ONLY. DISCORD CHECK 2026-09-14: absent from the written record — seven session note channels, the linked risk doc, and server-wide `from:arshmeister` search. #class-session-six defines what an order block IS and where it should sit, and says nothing about what kills one.',
        group='11.2',
        note='Q1: single-candle order blocks die at ~75% of liquidity taken, NOT at the zone 50% line. Measured with ob_liquidity_measure (P15). Band 70-80: sweep 70 / 75 / 80.',
    ),
    KeySpec(
        key='zone_direction_mode',
        default='both',
        spec_type='enum',
        py_type='str',
        members=('both', 'continuation_only', 'reversal_only'),
        minimum=None,
        maximum=None,
        source_id='CF-10; S5-R15, S6-R4/R5, S6-A26',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='zone_continuation_confluence_bonus',
        default=1.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-10 — OUR number',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='sufficient_gap_pct_by_tf',
        default={'15m': 3.0, '30m': 4.0, '1H': 4.0, '2H': 5.0, '4H': 6.0, '8H': 7.0, '12H': 7.5, '1D': 8.0, '2D': 13.0, '3D': 15.0, '1W': 15.0},
        spec_type='map',
        py_type='dict',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-11; Q13 stated rows 15m/30m/1H/1D/2D (S5 `[00:36:38]` `[00:54:07]` `[00:35:30]` `[00:36:05]` `[01:17:59]`); 2H/4H/8H/12H/3D+ [OUR CHOICE]. DISCORD CHECK 2026-09-14: the five "stated" rows are ALSO video-only — no percentage-by-timeframe table exists in writing anywhere. `sufficient` returns four hits server-wide, three being the #class-session-five zone definitions already held. He states the gap criterion three times (S5 M1, S5 M3, S6 M7) and gives a number zero times. Treat every row as a sweep target, not just the missing four.',
        group='11.2',
        note='Q13: HIS rows = 15m 3.0, 30m 4.0 (corrected from 3.5), 1H 4.0, 1D 8.0, 2D 13.0. '
             'INTERPOLATED [OUR CHOICE] rows = 2H 5.0, 4H 6.0, 8H 7.0, 12H 7.5, 3D/1W 15.0 - his '
             '1H->1D and 1D->2D slopes disagree by 3x, so these are not derivable. Sweep them. '
             'F5 NEGATIVE RESULT, do not re-litigate: a full frame pass over the recordings '
             'found NO percentage readout on any 2H, 4H, 8H or 12H chart - every genuine '
             'measure-tool reading sits on 1H or 30m. The one candidate that looks like a clean '
             'threshold, 8.10% at S5 36:05, was measured across a HAND-DRAWN ILLUSTRATION rather '
             'than real candles and MUST NOT be used as evidence for any row. Video is exhausted '
             'as a source here; a backtest sweep is the only remaining route, so no '
             'sweep_bracket is recorded - none is derivable from the corpus (see '
             'CHANGELOG_EVIDENCE.md Q13 for the per-row search sets).',
    ),
    KeySpec(
        key='sufficient_gap_atr_mult',
        default=2.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-11 — OUR number',
        group='11.2',
        note='Q13: on 2H-12H this is the BINDING test - the percentage row there is a guess. Sweep 1.5/2.0/2.5/3.0.',
    ),
    KeySpec(
        key='sufficient_gap_require_both_tests',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-11',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='sufficient_gap_anchor',
        default='breakout_close_to_extreme',
        spec_type='enum',
        py_type='str',
        members=('breakout_close_to_extreme', 'zone_top_to_extreme', 'zone_mid_to_close'),
        minimum=None,
        maximum=None,
        source_id='P10; S5-A1 — [OUR CHOICE]',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='sufficient_gap_retrace_cutoff',
        default=0.5,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1.0,
        source_id='P10 — [OUR CHOICE]',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='min_zone_depth_atr',
        default=0.5,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-12; S6-R48, S7-R6 — normalisation is OURS',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='max_zone_depth_atr',
        default=3.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-12; S8-R23 — normalisation is OURS',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='min_zone_bodies',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='CF-12; S5-R17',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='zone_within_zone_policy',
        default='larger_if_within_max_depth',
        spec_type='enum',
        py_type='str',
        members=('larger_if_within_max_depth', 'always_larger'),
        minimum=None,
        maximum=None,
        source_id='CF-12; S5-R30',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='wick_include_max_pct',
        default=2.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-13, P5; S7-R7',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='wick_include_max_atr',
        default=0.5,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-13, P5 — OUR number',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='zone_box_source',
        default='body_plus_small_wick',
        spec_type='enum',
        py_type='str',
        members=('body_plus_small_wick', 'body_only', 'full_range'),
        minimum=None,
        maximum=None,
        source_id='CF-13; S5-R17, S5-R19, S6-R9',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='zone_wick_band_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='F1 — FRAME_FINDINGS.md F1, S6 frame 52:38 (LINK 1D "Bullish OB"); [SINGLE-FRAME OBSERVATION, needs corroboration]',
        group='11.2',
        note='F1: on one frame he appears to draw TWO nested boxes - an inner box on candle '
             'BODIES and an outer band extended to the WICK extreme. When true a Zone carries '
             'both extents and entries price off the body box while the stop goes beyond the '
             'wick band. Default FALSE, and WEAKENED by the pass-2 frames: the two-box form '
             'appears in roughly ONE FRAME IN FOUR, it is not his standard convention, and the '
             'one clear example (S6 52:38) was measured MID-DRAG, with overlapping fills - the '
             'same drawing re-read at S6 53:46 gives a different band. Two further frames '
             '(S6 54:22, S8 33:56) show a SINGLE box, and the cleanest settled box in the batch '
             '(S8 1:28:33) is a single box on body extremes. What IS consistent across both '
             'passes: every SETTLED box anchors top and bottom to candle BODIES. The flag stays '
             'off and now needs more corroboration than pass 1 assumed.',
    ),
    KeySpec(
        key='zone_wick_band_max_ratio',
        default=1.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='F1 — FRAME_FINDINGS.md F1, S6 frame 52:38; [SINGLE-FRAME OBSERVATION, needs corroboration]',
        group='11.2',
        note='F1: how far the outer wick band may extend past the body box, as a multiple of the '
             'body-box height. 1.0 = the band may be up to 100% of the body-box height before '
             'the wick is treated as an outlier and excluded (the band then collapses back onto '
             'the body edge). Only read when zone_wick_band_enabled is true. NOT A TRUSTWORTHY '
             'NUMBER: the same drawing was read at 0.83 (S6 52:38, pass 1) and at 0.33 '
             '(S6 53:46, pass 2, rectangle mid-drag) - the two readings disagree by a factor of '
             '2.5. Sweep bracket widened to 0.30-1.00 to span both readings up to the '
             'conservative cap.',
        sweep_bracket=(0.30, 1.00),
    ),
    KeySpec(
        key='stop_wick_max_pct',
        default=3.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-14; S6-R18',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='stop_buffer_atr',
        default=0.15,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-14, P19 — OUR number; S2-A8, TBOT1-A14',
        group='11.2',
        note='FALLBACK buffer only, for stops NOT anchored to a zone (levels, SFPs, structure '
             'breaks) and for the CF-06 step-1 LTF re-anchor. A stop placed against a zone uses '
             'stop_buffer_zone_fraction instead (F6): three pass-2 frames show the stop distance '
             'scaling with ZONE HEIGHT, not with price percentage and not with ATR. Still '
             '[OUR CHOICE] where it does apply — he never states a buffer.',
    ),
    KeySpec(
        key='stop_buffer_zone_fraction',
        default=0.5,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='F6 — DISPUTED, see docs/measurement/00-MASTER.txt Part 2. '
                  'FRAME_FINDINGS.md F6 (pass 2); TBOT1 4:11 (BTCUSDT.P 1H Binance), '
                  'TBOT1 1:09:19 (OMUSDT.P 1H Binance), S8 1:28:33 (SOLUSDT.P 4H MEXC). '
                  'The independent measurement pass WITHDREW this rule from the same three '
                  'frames. Treat as [OUR CHOICE] pending a sweep on real data.',
        group='11.2',
        note='F6: when the stop is placed against a ZONE it sits this fraction of the zone '
             'height beyond the zone\'s far edge (below the box bottom for a long, above the box '
             'top for a short). Measured 0.48 / 0.49 / 0.58 across the three frames, mean ~0.52. '
             'The parameterisation still looks right — the SAME three frames give 0.66% / 2.70% '
             '/ 0.81% of entry and no ATR multiple at all — but the NUMBER is disputed and the '
             'default is no longer presented as evidenced. Three reasons, all from the '
             'independent measurement pass in docs/measurement/: (1) it withdrew this rule '
             'because the fraction depends on which band is nominated as "the zone"; the same '
             'frames yield 0.042 to 4.145 under a different nomination. The bot does have a '
             'canonical zone (Zone.box_top/box_bottom, the body box), so that ambiguity is '
             'narrower here than it was there, but the three boxes were still read by eye. '
             '(2) the test that appeared to reproduce the three frames was circular: it built '
             'each box FROM the ratio, so it asserted only that 0.48/0.49/0.58 sit within 0.10 '
             'of 0.5, and passed unchanged with every frame price scaled 10x. Rewritten. '
             '(3) TBOT1 1:09:19 is measured there as OMUSDT.P at $5.18, while the spoken anchor '
             'used for that frame ("Scalp long 524ish. Stop loss 509") is a $524 instrument, so '
             'one of the two identifications is wrong. Read only when the setup hangs off a '
             'zone; otherwise stop_buffer_atr applies. Sweep bracket widened to 0.0-0.60: 0.0 is '
             'the measurement pass\'s own position, snap the stop to the structural level and '
             'model no overshoot.',
        sweep_bracket=(0.0, 0.60),
    ),
    KeySpec(
        key='stop_never_beyond_opposing_level',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-14; S5-R25, S6-R19',
        group='11.2',
        note='',
    ),
    KeySpec(
        key='flip_confirm_candles',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='CF-15; S5-R3, S2-R1/R2/R3',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='flip_extra_candle_below_tf',
        default='4H',
        spec_type='tf',
        py_type='str',
        members=('4H', '15m', '30m', '1H', '2H', '8H', '12H', '1D', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf', 'disabled'),
        minimum=None,
        maximum=None,
        source_id='CF-15; Q10 stated, S2 `[00:26:30]` (was inferred)',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='flip_requires_body_close',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-15; S4-R5, S8-R41',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='pending_sr_expiry_bars',
        default=60,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-15 — OUR number; S2-A15',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='entry_family_retest_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-16; Q10 stated, S3 `[01:54:12]` (an SR point is by definition already flipped)',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='entry_family_flip_pending_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-16; Q10 stated, S4 `[00:55:38]` ("you\'re not going to place limit orders at the SR line")',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='entry_family_trigger_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-16; CF-20, CF-22',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='max_entry_distance_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='[OUR CHOICE] — no such gate exists in the corpus; DISCORD CHECK 2026-09-15 bounds it',
        group='11.3',
        note='OFF by default: today G0 rejects only a retest on the WRONG side of the close '
             '(anchor_beyond_price, pipeline.py). Nothing bounds a right-side entry that is '
             'absurdly far away. Turning this on changes every backtest, so it stays off until a '
             'sweep says otherwise — CHANGELOG_EVIDENCE.md convention for [OUR CHOICE] values.',
    ),
    KeySpec(
        key='max_entry_distance_pct',
        default=15.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='[OUR CHOICE] — bounded by DISCORD CHECK 2026-09-15, never stated by him',
        group='11.3',
        note='How far behind the close a retest entry may sit before G0 stops calling it a '
             'candidate. He states no such gate anywhere, so the VALUE is ours; the RANGE is his. '
             'Ten written entry/DCA ladders (#arshmeister-updates, #arsh-active-calls, '
             '2025-11-06..2026-09-14): first rung below entry median 9.78%, p90 14.89%, max '
             '17.76%; deepest rung median 15.76%, p90 23.74%, max 27.18% (ZEC 1045 -> 761). '
             'Six of the ten entries are explicitly at market ("at CMP", "here at"), so for those '
             'entry == close at post time and the ladder percentages ARE distances below spot — '
             'that is what makes the mapping legal. 15.0 sits on the median deepest rung and just '
             'above the p90 first rung; 27.5 is his observed maximum and the never-seen-wider bound.',
        sweep_bracket=(5.0, 27.5),
    ),
    KeySpec(
        key='presr_light_limit_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-16; Q10 stated-as-inferior, S2 `[00:27:08]`-`[00:27:41]`',
        group='11.3',
        note='Q10: a light first leg resting at a level that is broken but not yet retested. He does it and calls it his own impatience ("if I was a little more patient... I would have waited for the flip"). Default off; sweep on/off, metric = fill rate vs deviation rate.',
    ),
    KeySpec(
        key='allow_market_orders',
        default='trigger_family_only',
        spec_type='enum',
        py_type='str',
        members=('trigger_family_only', 'never', 'always'),
        minimum=None,
        maximum=None,
        source_id='CF-16; Q10 stated, S4 `[02:03:04]` ("I never market into anything. So I always set limits")',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='dca_count_default',
        default=1,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-17; S6-R16',
        group='11.3',
        note='F7 (pass-2 frames) CORROBORATION, no change: entries sit at a zone EDGE, never '
             'mid-box - DOGE 2H short entered at the bottom edge (1.00 of the way down the box), '
             'SOL 4H long at the top edge (0.01). That is the ladder this key already builds: '
             'first entry at the near edge, final DCA at the far edge. Honest limit: none of the '
             'entry lines in the frames is LABELLED, so the frames cannot say which line is the '
             'first entry and which the DCA - only that both sit on edges.',
    ),
    KeySpec(
        key='dca_count_max',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-17; S2-R9, S6 `[01:01:51]`',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='dca_count_scalp_max',
        default=1,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-17; S8-R17',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='dca_count_breakdown',
        default=0,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-17; S8-R11',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='dca2_min_zone_depth_atr',
        default=1.5,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-17 — OUR number; S5-R22',
        group='11.3',
        note='F7 (pass-2 frames) CORROBORATION, no change: the second leg sits at the FAR edge '
             'of the box (DOGE 2H bottom edge, fraction 1.00), which is what a depth-gated '
             'far-edge DCA looks like. The frames do not label the lines, so they corroborate '
             'the geometry and not this threshold, which stays OUR number.',
    ),
    KeySpec(
        key='dca_size_split_2',
        default=[0.39, 0.61],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-18; Q3 derived, S6 `[00:48:10]` — 35:55 of his own LINK ladder (avg 17.6332 reproduces exactly); CORROBORATED by F2 (S6 frame 9:40-10:53, ORDI)',
        group='11.3',
        note='Q3: replaces the guessed [0.30, 0.70]. F2 CORROBORATION, default unchanged: an '
             'INDEPENDENT frame (S6 9:40-10:53, ORDI 1D, on-screen average-cost calculator) '
             'shows 15 units @ 35.51 + 25 units @ 40.11 = 40 units at an average of 38.385, i.e. '
             '37.5 / 62.5 - within 1.5 points of the 39/61 derived from the unrelated LINK '
             'ladder. Two unrelated worked examples agreeing that closely is the strongest '
             'confirmation any parameter in this project has. A third example (his mid-edit '
             'rework at 11:27: 7 @ 35.51 + 15 @ 40.11 = 31.8 / 68.2) puts the OBSERVED RANGE '
             'across three examples at 32-39% on the first leg. Sweep bracket 0.32-0.40 on the '
             'first leg (second leg = 1 - first).',
        sweep_bracket=(0.32, 0.40),
    ),
    KeySpec(
        key='dca_size_split_3',
        default=[0.15, 0.325, 0.525],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-18; Q3 STATED in writing x3 — Discord #class-session-one M2 and '
                  '#class-session-five M8 ("the 15/30-35/50-55% method/rule"), and the linked '
                  'risk-management doc ("15% at entry / 30% at DCA 1 / 50% at DCA 2"). '
                  'SUPERSEDES the derived [0.2,0.3,0.5] from S6 `[00:38:49]`-`[00:40:05]`.',
        group='11.3',
        note='Q3: default is the midpoint of his stated ranges — 15 / 30-35 / 50-55. Stated in '
             'plain words three times across two sessions and a written risk doc, which outranks '
             'the S6 transcript arithmetic that produced the old 20/30/50. UNRESOLVED, see '
             'CONFLICTS.md: whether the percentages apply to CAPITAL or to QUANTITY. His prose '
             'says "15% of my allowed capital", but the only worked example (DOT: 20/50/150 at '
             '29.23/28.48/27.93 -> 220 units at 28.1732, arithmetic exact) was entered into a '
             'contracts-based calculator. That example CANNOT settle the basis: its prices span '
             'only 4.45%, so capital- and quantity-weighting land within 0.6 points of each '
             'other. The same example also runs a 9/23/68 ladder, not his stated one — read as '
             'round teaching numbers, not as an execution.',
        sweep_bracket=(0.10, 0.20),
    ),
    KeySpec(
        key='dca_size_split_wick_heavy_2',
        default=[0.25, 0.75],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-18; Q3 stated, S6 `[01:54:34]` ("very light there, like 20 to 30%")',
        group='11.3',
        note='Q3: midpoint of his stated 20-30% band; sweep 0.20-0.30 on the first leg.',
    ),
    KeySpec(
        key='size_and_stop_computed_from',
        default='average_entry',
        spec_type='enum',
        py_type='str',
        members=('average_entry', 'first_entry'),
        minimum=None,
        maximum=None,
        source_id='CF-18; Q3 stated, S6 `[00:40:40]` ("18.456 minus our average entry")',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='average_up_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-19; S3-R13, S3-A10',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='average_up_trigger_atr',
        default=2.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-19 — OUR number',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='average_up_only_at_sr_point',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-19; S3-R14',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='sfp_entry_price',
        default='confirming_close',
        spec_type='enum',
        py_type='str',
        members=('confirming_close', 'next_open'),
        minimum=None,
        maximum=None,
        source_id='CF-20; S7-R21, S8-R5, S7-C6',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='sfp_standalone_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-20; S7-R30, S7-C5',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='sfp_min_bars_between',
        default=3,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-20; Q6 floor stated at 2, S7 `[01:19:52]` ("candles cannot be next to each other"); the value 3 is OURS',
        group='11.3',
        note='Q6: sweep {2, 3, 5}; SFP win rate stratified by separation.',
    ),
    KeySpec(
        key='sfp_raid_price_source',
        default='wick',
        spec_type='enum',
        py_type='str',
        members=('wick', 'body'),
        minimum=None,
        maximum=None,
        source_id='CF-20, P1; Q6 stated, S7 `[01:14:44]`',
        group='11.3',
        note='Q6: the swing_price_source carve-out. "Swing high points are usually taken by wicks, not by bodies" - the raid level and the stop beyond it are wick prices even though structure is bodies.',
    ),
    KeySpec(
        key='sfp_min_swing_separation_atr',
        default=1.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-20 — OUR number; S7-R28, S8-R4',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='sfp_max_close_distance_atr',
        default=1.5,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-20 — OUR number; S5-R7',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='sfp_trend_veto',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-20; S7-R31',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='sfp_governing_timeframe',
        default='highest_valid',
        spec_type='enum',
        py_type='str',
        members=('trade_structure_tf', '1D', 'highest_valid'),
        minimum=None,
        maximum=None,
        source_id='CF-20; Q7 inferred, S8 `[00:23:06]` `[00:16:46]`, S7 `[01:24:22]` `[01:26:03]`',
        group='11.3',
        note='Q7 [INFERRED]: SFP validity legitimately differs by timeframe; he trades the HIGHEST timeframe on which it is valid and demotes an LTF-only SFP to a scalp. "trade_structure_tf" misses the S8 daily SFP whenever structure resolves to 12H.',
    ),
    KeySpec(
        key='reentry_trigger',
        default='sfp_or_close_reclaim',
        spec_type='enum',
        py_type='str',
        members=('sfp_or_close_reclaim', 'sfp_only', 'close_reclaim_only', 'any'),
        minimum=None,
        maximum=None,
        source_id='CF-21; S2-R13, S6-R24',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='reentry_max_attempts_per_level',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-21 — OUR number; S8-A20',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='reentry_cooldown_bars',
        default=3,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-21 — OUR number',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='reentry_window_bars',
        default=100,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-21 — OUR number',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='reentry_stacked_conditionals_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-21; TBOT1-R26',
        group='11.3',
        note='',
    ),
    KeySpec(
        key='msb_exit_mode',
        default='break_only',
        spec_type='enum',
        py_type='str',
        members=('break_only', 'break_plus_lower_high'),
        minimum=None,
        maximum=None,
        source_id='CF-22; S7-R12, S3-R21, S2-R28',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='msb_entry_requires_retest',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-22; Q11 stated x4, S7 `[00:26:59]` `[00:28:40]`, S8 `[00:25:58]` `[01:17:19]`',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='msb_retest_timeout_bars',
        default=20,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-22 — OUR number; S7-A20',
        group='11.4',
        note='Q11 ABSENT: "next candle or however many candles it takes" (S4 `[00:35:08]`). He refuses to bound it. Value unchanged and still [OUR CHOICE]; sweep {10, 20, 40, 60, disabled} on expectancy per MSB signal. His real invalidation is msb_deviation_invalidates, not a clock.',
    ),
    KeySpec(
        key='msb_deviation_invalidates',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-22; Q11 derived, S2 `[00:25:56]`',
        group='11.4',
        note='Q11: a close back beyond the broken level before the retest means the break was a DEVIATION and the setup is dead. This is his condition-based invalidation, and §11 had no key for it.',
    ),
    KeySpec(
        key='msb_price_source',
        default='body_close',
        spec_type='enum',
        py_type='str',
        members=('body_close', 'wick'),
        minimum=None,
        maximum=None,
        source_id='CF-22; Q7 stated x4, S7 `[00:18:50]` `[01:11:53]`, S5 `[01:25:16]`',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='higher_low_selection',
        default='technical',
        spec_type='enum',
        py_type='str',
        members=('technical', 'confluence_weighted'),
        minimum=None,
        maximum=None,
        source_id='CF-23; S7-R12, S8-C2',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='bias_level_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-23 (spot/long-term only); S8-C2',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='bias_level_min_confluence',
        default=2.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-23 — OUR number',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='bias_level_lookback_bars',
        default=200,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-23 — OUR number',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='structure_tf_offset',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-24 — OUR construct; S7-A8, S7-A9',
        group='11.4',
        note='Q7: [OUR CHOICE], sweep-first. Offset 3 is evidence-favoured (1H -> 8H lands on his stated favourite swing chart, S5 `[01:42:18]`); offset 2 puts structure at the bottom edge of his swing band.',
    ),
    KeySpec(
        key='htf_veto_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-24; Q7 stated, S8 `[00:38:57]` `[00:41:12]` (was inferred)',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='htf_veto_timeframe',
        default='1D',
        spec_type='tf',
        py_type='str',
        members=('1D', '15m', '30m', '1H', '2H', '4H', '8H', '12H', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='CF-24; Q7 stated, S8 `[00:41:12]` ("the daily super bearish")',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='swing_k',
        default=3,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P1 — [OUR CHOICE]; S7-A7; bounded (not fixed) by F4, S7 frame 34:30. NO FRACTAL DEFINITION EXISTS. DISCORD CHECK 2026-09-14: absent from the written record — seven session note channels, the linked risk doc, and server-wide `from:arshmeister` search. Four lines converge: (1) the written sessions define structure RELATIONALLY (HH/HL/LH/LL and which breaks which), never by candle count; (2) S6 `[01:21:06]` "you can take it from many swing low points. It does not matter which one"; (3) no N-bar rule in the eight transcripts (QUESTIONS_FOR_TRADER Q6); (4) he never uses "pivot" as a TA term server-wide — both hits are Federal Reserve pivots. swing_k is OUR scaffolding for finding candidates in code, not his rule. Stop hunting it; sweep it.',
        group='11.4',
        note='Q6 ABSENT: no fractal width, lookback or N-bar rule anywhere in eight sessions. '
             'Stays 3 and stays [OUR CHOICE]. F4 NARROWS THE SWEEP, it does not decide the '
             'value: one readable frame (S7 34:30, 4H, the arrow-tipped swing high) has its 5th '
             'left-hand candle EXCEEDING the marked point, so the left-side width there is at '
             'most 4. That rules out >=5 FOR THAT INSTANCE ONLY; 2, 3 and 4 all remain '
             'admissible and the frame does not distinguish between them. Three of the four '
             'measured right-side counts are floors, not counts, because the live edge truncates '
             'them. Sweep bracket 2-4 (was open) on detected-MSB rate per 1,000 bars, not PnL.',
        sweep_bracket=(2.0, 4.0),
    ),
    KeySpec(
        key='swing_price_source',
        default='body',
        spec_type='enum',
        py_type='str',
        members=('body', 'wick'),
        minimum=None,
        maximum=None,
        source_id='P1; Q6 stated, S7 `[00:18:50]` `[01:10:48]` `[01:11:53]`, S5 `[01:25:16]` (was [OUR CHOICE])',
        group='11.4',
        note='Q6: bodies/line chart for STRUCTURE. Carve-out: the SFP raid level and its stop are read off the WICK (S7 `[01:14:44]`) - see sfp_raid_price_source.',
    ),
    KeySpec(
        key='trend_pivot_count',
        default=4,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P11 — [OUR CHOICE]',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='trend_timeframe',
        default='structure_tf',
        spec_type='enum',
        py_type='str',
        members=('structure_tf', '15m', '30m', '1H', '2H', '4H', '8H', '12H', '1D', '2D', '3D', '1W'),
        minimum=None,
        maximum=None,
        source_id='P11; CF-24',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='dir_change_atr',
        default=2.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P2 — [OUR CHOICE]; S6-A1',
        group='11.4',
        note='Q6: retained as a SECONDARY floor only; the primary test is sufficient_gap_pct_by_tf when dir_change_uses_sufficient_gap_table is true. On its own 2.0 is materially looser than his percentage floors. Sweep {2.0, 3.0, 5.0, 8.0}.',
    ),
    KeySpec(
        key='dir_change_max_bars',
        default=10,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P2 — [OUR CHOICE]',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='dir_change_uses_sufficient_gap_table',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='P2; Q6 inferred, S5 `[00:54:07]` `[00:36:05]` `[00:35:30]`',
        group='11.4',
        note='Q6 [INFERRED]: his only quantified move-size test is the sufficient-gap table, and in every worked example the order block and the zone are marked off the same checked impulse leg. His threshold is a percentage that scales with timeframe, not an ATR multiple.',
    ),
    KeySpec(
        key='level_lookback_bars',
        default=500,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P3 — [OUR CHOICE]; S2-A3',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='level_cluster_atr',
        default=0.25,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P3 — [OUR CHOICE]; S4-A2',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='level_min_touches',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P3; S4-R4, S7 `[00:05:04]`',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='level_tolerance_atr',
        default=0.15,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P4/P9 — [OUR CHOICE]; S2-A2, S3-A8',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='touch_reset_atr',
        default=0.5,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P4 — [OUR CHOICE]; TBOT1-A6',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='capitulation_wick_atr',
        default=3.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P12 — [OUR CHOICE]; TBOT1-A15, S8-A17',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='capitulation_wick_body_ratio',
        default=3.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P12 — [OUR CHOICE]',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='capitulation_volume_mult',
        default=2.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P12 — [OUR CHOICE]',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='consolidation_max_drift_atr',
        default=0.75,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P13 — [OUR CHOICE]; S5-A5, S6-A27',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='consolidation_max_height_atr',
        default=2.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P13 — [OUR CHOICE]',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='consolidation_min_bars',
        default=2,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P13; S5-R17',
        group='11.4',
        note='',
    ),
    KeySpec(
        key='mid_range_band_pct',
        default=15.0,
        spec_type='pct of range height, each side',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-25 — OUR number; S4-A3, S8-A14',
        group='11.5',
        note='Q12 ABSENT: he gates on a STATE ("consolidating at mid-range"), never a distance. Value unchanged and still [OUR CHOICE]; sweep {5, 10, 15, 20} and measure the expectancy of the trades it blocks.',
    ),
    KeySpec(
        key='mid_range_limits_from_extremes_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-25; Q12 stated, S4 `[00:34:02]` ("if price is up here, then yes, you\'re going to set limits at mid-range")',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='mid_range_requires_intermediate_stop',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-25; S5-R13',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='range_death_mode',
        default='close_beyond_plus_flip',
        spec_type='enum',
        py_type='str',
        members=('close_beyond_plus_flip', 'close_beyond', 'single_stopout'),
        minimum=None,
        maximum=None,
        source_id='CF-26; S4-A16',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='mid_range_search_pct',
        default=10.0,
        spec_type='pct of range height',
        py_type='float',
        members=None,
        minimum=0.1,
        maximum=100.0,
        source_id='CF-26, P7; Q12 stated, S4 `[00:17:53]` ("it will usually align with support and resistance")',
        group='11.5',
        note='Q12: the pure-geometric-50% alternative (0) is STRUCK from the allowed set - he rejected it on tape. Sweep {5, 10, 15}.',
    ),
    KeySpec(
        key='range_min_height_atr',
        default=3.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-26, P8 — OUR number; S4-A15',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='range_max_age_bars',
        default=300,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-26, P8 — OUR number',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='range_min_bars',
        default=20,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='P8 — [OUR CHOICE]',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='range_stale_bars',
        default=60,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P8 — [OUR CHOICE]',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='monday_range_source_tf',
        default='1D',
        spec_type='tf',
        py_type='str',
        members=('1D', '15m', '30m', '1H', '2H', '4H', '8H', '12H', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='CF-45; S5-R8, S5-R9',
        group='11.5',
        note='',
    ),
    KeySpec(
        key='tp_count_swing',
        default=3,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-27; S4-R1/R2, S6-R20; CORRECTED by Discord #class-session-one M4 and '
                  'the linked risk doc, both STATED: "TP1 40% TP2 30% TP3 30%"',
        group='11.6',
        note='Was 2. He writes "TP strategy for me - TP1 40% TP2 30% TP3 30%" as his default, '
             'twice in writing, and tp_split_3 already matches that exactly. Also stated: "I am '
             'all out at TP3 if it hits, not leaving runners" — the three splits sum to 1.0, so '
             'no residual arises and tp_residual_policy never engages on a 3-TP swing.',
    ),
    KeySpec(
        key='tp_count_scalp',
        default=3,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-27; S8-R19, TBOT1-R17',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='tp_count_price_discovery_max',
        default=5,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-27; S6-R36',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='tp_min_count',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='CF-27; S5-R26',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='tp_split_2',
        default=[0.5, 0.5],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-28; Q4 stated, S4 `[00:17:53]` `[00:18:27]` ("if it\'s two TPS, then I do 50/50")',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='tp_split_3',
        default=[0.4, 0.3, 0.3],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-28; Q4 stated, S4 `[00:18:27]` ("if it\'s three TPS, I have 40 30 30")',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='tp_split_4',
        default=[0.4, 0.25, 0.2, 0.15],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-28 — OURS',
        group='11.6',
        note='Q4 ABSENT: he never splits 4+ TPs. Value unchanged and still OURS. Sweep plan: replace with a front-loading decay parameter over [0.55, 1.00], metric = realised R on setups with >=4 structural TPs.',
    ),
    KeySpec(
        key='tp_split_5',
        default=[0.35, 0.25, 0.2, 0.12, 0.08],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-28 — OURS',
        group='11.6',
        note='Q4 ABSENT: he never splits 5 TPs. Value unchanged and still OURS. See tp_split_4 sweep plan.',
    ),
    KeySpec(
        key='tp_residual_policy',
        default='trail_out',
        spec_type='enum',
        py_type='str',
        members=('trail_out', 'close_at_last_tp'),
        minimum=None,
        maximum=None,
        source_id='CF-28; Q4 stated, S5 `[00:40:00]` (he accepts being trailed out)',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='trail_on_tp1',
        default='break_even',
        spec_type='enum',
        py_type='str',
        members=('break_even', 'none', 'tp_minus_one_atr'),
        minimum=None,
        maximum=None,
        source_id='CF-29; S4-R11, S5-R27',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='trail_on_tp2',
        default='tp1_price',
        spec_type='enum',
        py_type='str',
        members=('tp1_price', 'break_even'),
        minimum=None,
        maximum=None,
        source_id='CF-29; S4-R11, S5-R27',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='break_even_reference',
        default='average_entry',
        spec_type='enum',
        py_type='str',
        members=('average_entry', 'first_entry'),
        minimum=None,
        maximum=None,
        source_id='CF-29; CF-18',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='stale_exit_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-30; S6-A17',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='stale_exit_bars',
        default=8,
        spec_type='bars',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-30, P17 — OUR number',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='stale_exit_mae_atr',
        default=1.0,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-30, P17 — OUR number',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='reaction_threshold_atr',
        default=0.75,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P17 — [OUR CHOICE]',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='structural_stale_exit_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-30; S6-R22, S6-R23, S7-R39, S8-R9',
        group='11.6',
        note='',
    ),
    KeySpec(
        key='min_confluence_count',
        default=3.0,
        spec_type='count',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-31; Q5 derived, S5 `[01:43:55]` `[01:05:33]`, S8 `[00:53:41]` — RAW object count, not a weighted score',
        group='11.7',
        note='Q5: three is the floor and it is a count of deduplicated objects. Under confluence_gate_mode="raw_count" this is compared to the object count, not to the weighted score. WEAK supporting evidence from the pass-2 frames (F8): ONDO 1D shows 5 overlapping objects at the trade price, BONK 12H shows 2-3 strictly at price and 5-6 within a risk-box height. Two frames, both at or above the floor and neither labelled as a threshold - consistent with 3 but nowhere near enough to move it; default unchanged.',
    ),
    KeySpec(
        key='confluence_gate_mode',
        default='raw_count',
        spec_type='enum',
        py_type='str',
        members=('raw_count', 'weighted_score'),
        minimum=None,
        maximum=None,
        source_id='CF-31; Q5 derived, S5 `[01:05:33]`, S8 `[00:53:41]`',
        group='11.7',
        note='Q5: the entry gate counts raw objects. The §6.1 weight map is demoted to RANKING and conviction only - as a gate it silently rejected three-object stacks he demonstrably takes.',
    ),
    KeySpec(
        key='confluence_weights',
        default={'sr_level': 1.5, 'zone': 1.25, 'order_block': 1.0, 'range_boundary': 1.0, 'fib': 1.0, 'trendline': 0.75, 'pattern': 0.5, 'sfp': 0.5, 'rsi_divergence': 0.5, 'ema200': 0.5, 'cme_gap': 0.5},
        spec_type='map',
        py_type='dict',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-31 — weights are OURS; S6-A15. Q5: ranking + conviction only, never the entry gate',
        group='11.7',
        note='SPEC.md §6.1 map; the numbers are OURS. Q5 demoted this from the gate to ranking (S6 `[01:03:33]` ranks classes, he never scores them).',
    ),
    KeySpec(
        key='confluence_merge_atr',
        default=0.25,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-31, P14 — OUR number; TBOT1-A4',
        group='11.7',
        note='Q5 [OUR CHOICE]: decides what "at the same price" means, which the whole counting rule depends on. Sweep 0.15-0.50.',
    ),
    KeySpec(
        key='confluence_dedup_same_class',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-31, P14',
        group='11.7',
        note='Q5: kept true, but flagged - S8 `[00:53:41]` counts "SR, supply zone, resistance" as three and SR/resistance are one class here. Sweep it.',
    ),
    KeySpec(
        key='single_class_trade_forbidden',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-31; Q5 stated, S6 `[00:45:16]` ("I don\'t take trades based off OBS alone. I need confluence")',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='high_conviction_score',
        default=4.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='§6.3 — [OUR CHOICE]; S6 `[01:35:26]`',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='pipeline_order',
        default=['universe_calendar_gate', 'load_align_candles', 'structure', 'levels_sr_flips', 'trend_lines', 'ranges_mid_range', 'liquidity_map', 'supply_demand_zones', 'order_blocks', 'context_regime', 'fibs', 'chart_patterns', 'confluence_scoring', 'sfp', 'rsi_divergence', 'ltf_refinement', 'setup_qualification', 'trade_plan_construction'],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-32; S6-R28, S6-C2',
        group='11.7',
        note='SPEC.md §3.1 stage sequence, stages 0..17',
    ),
    KeySpec(
        key='fib_loses_ties_to_sr',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-32; S6-R38',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='sfp_evaluated_last',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-32; S7-R30',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='golden_pocket_band',
        default=[0.618, 0.66],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id="CF-33; Q15 stated, S6 `[01:26:22]` `[01:40:01]` — 0.66 is his, 0.65 is other people's and lies inside the band",
        group='11.7',
        note='',
    ),
    KeySpec(
        key='fib_levels_active',
        default=[0.618, 0.66, 0.786],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-33; Q15 stated, S6 `[01:41:14]`-`[01:41:52]` ("I use the three middle ones" of 886/786/66/618/236)',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='fib_886_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-33; Q15 stated, S6 `[01:38:53]` ("I just haven\'t back tested it") — excluded by his own arithmetic',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='fib_entry_level',
        default=[0.618, 0.66],
        spec_type='band',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-33; TBOT1-R5',
        group='11.7',
        note='Q15: read as "the fib level that may coincide with an entry", never "where entries go" - S6 `[01:57:29]`: "my entry is always going to be an SR point or a resistance point".',
    ),
    KeySpec(
        key='fib_dca_level',
        default=0.786,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1.0,
        source_id='CF-33; Q15 stated, S6 `[01:56:54]` ("the 786 fib is usually my DCA point")',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='fib_draw_convention',
        default='s6',
        spec_type='enum',
        py_type='str',
        members=('s6', 'tbot1'),
        minimum=None,
        maximum=None,
        source_id='CF-34; S6-R34, S6-R35, S6-C6, S7-R1',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='fib_anchor_selection',
        default='most_recent_qualifying_swing_pair',
        spec_type='enum',
        py_type='str',
        members=('most_recent_qualifying_swing_pair', 'largest_leg', 'manual'),
        minimum=None,
        maximum=None,
        source_id='CF-34 — [OUR CHOICE]; S6-A16, TBOT1-A2',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='dxy_gate_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-35; S3-C8, S3-A21',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='dxy_gate_min_rolling_corr',
        default=0.4,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=-1.0,
        maximum=1.0,
        source_id='CF-35 — OUR construct',
        group='11.7',
        note='measured over a 90-day rolling window',
    ),
    KeySpec(
        key='context_priority',
        default=['USDT.D', 'BTC.D', 'BVOL'],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-35; S3-R11',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='bvol_zone',
        default=[0.81, 1.4],
        spec_type='list',
        py_type='list',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-35; S3-R7. TICKER IS DEAD: BVOL24H does not resolve on TradingView (checked 2026-09-14 across every asset class; the single BVOL hit is an unrelated Gate perpetual on a DeFi token and must NOT be substituted). regime.py degrades gracefully so the bot still runs, but bvol_event can never fire, so bvol_size_multiplier never halves leverage — a SILENT loss of a size reduction, not a crash. Needs a replacement volatility source or removal',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='bvol_event_window_hours',
        default=72,
        spec_type='int (hours)',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-35; S3-R1, S3-C2. TICKER IS DEAD: BVOL24H does not resolve on TradingView (checked 2026-09-14 across every asset class; the single BVOL hit is an unrelated Gate perpetual on a DeFi token and must NOT be substituted). regime.py degrades gracefully so the bot still runs, but bvol_event can never fire, so bvol_size_multiplier never halves leverage — a SILENT loss of a size reduction, not a crash. Needs a replacement volatility source or removal',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='bvol_size_multiplier',
        default=0.5,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1.0,
        source_id='CF-35; S3-R5. TICKER IS DEAD: BVOL24H does not resolve on TradingView (checked 2026-09-14 across every asset class; the single BVOL hit is an unrelated Gate perpetual on a DeFi token and must NOT be substituted). regime.py degrades gracefully so the bot still runs, but bvol_event can never fire, so bvol_size_multiplier never halves leverage — a SILENT loss of a size reduction, not a crash. Needs a replacement volatility source or removal',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='all_pairs_at_resistance_veto',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-35; TBOT1-R20',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='rsi_divergence_mode',
        default='confluence_only',
        spec_type='enum',
        py_type='str',
        members=('confluence_only', 'off', 'standalone'),
        minimum=None,
        maximum=None,
        source_id='CF-36; S8-C3',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='rsi_period',
        default=14,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='CF-36 — OURS; S8-A19',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='rsi_timeframe',
        default='structure_tf',
        spec_type='enum',
        py_type='str',
        members=('structure_tf', '15m', '30m', '1H', '2H', '4H', '8H', '12H', '1D', '2D', '3D', '1W'),
        minimum=None,
        maximum=None,
        source_id='CF-36 — OURS; S8-A19',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='rsi_oversold',
        default=30,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-36; S8-R40, S8-C4',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='rsi_overbought',
        default=70,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-36; S8-R40, S8-C4',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='ema200_confluence_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-36; S6 `[01:09:27]`',
        group='11.7',
        note='',
    ),
    KeySpec(
        key='module_chart_patterns_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-37; Q14 stated, S4-R38 / S4 `[01:48:29]` — "never on a pattern alone", not a disavowal',
        group='11.8',
        note='Q14: confluence-only is the right outcome, but the rationale is "never alone", not "it does not work". Patterns stay live as confluence and as measured-move TP targets.',
    ),
    KeySpec(
        key='module_trendline_break_enabled',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-37; Q14 stated, S8 `[00:28:52]` `[00:30:37]` — the objection is operational (no hard stop)',
        group='11.8',
        note='Q14: off by default, backtest-selectable. When on, his stated constraints bind: small size, one entry, no DCA (dca_count_breakdown=0), close on reclaim. Trend lines THEMSELVES are not disowned (S6-R28 step 3) - only trendline-breakdown-as-a-trigger.',
    ),
    KeySpec(
        key='module_scalp_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-37; Q14 inferred (REVERSES CF-37), S5 `[01:41:45]` `[01:42:50]`, S8 `[00:44:49]`',
        group='11.8',
        note='Q14 [INFERRED]: what he disowns is 150-trades-a-day sub-15m day trading, not the trade class - he names the 2H as his favourite scalp chart. Floored at scalp_tf_floor=30m. Counter-evidence: his live S8 scalp session went 1 for 3 (S8 `[01:57:24]`).',
    ),
    KeySpec(
        key='disowned_modules_still_score_confluence',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-37; Q14 stated, S4 `[01:48:29]`, S6 `[01:56:54]`',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='swing_tf_floor',
        default='4H',
        spec_type='tf',
        py_type='str',
        members=('4H', '15m', '30m', '1H', '2H', '8H', '12H', '1D', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='CF-38; S5-R34, S6 `[00:57:15]`',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='scalp_tf_ceiling',
        default='2H',
        spec_type='tf',
        py_type='str',
        members=('2H', '15m', '30m', '1H', '4H', '8H', '12H', '1D', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='CF-38; Q14 stated, S5-R34 / S5 `[01:41:45]` ("I prefer a 2 hour than a 30 minute 100% of the time")',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='scalp_tf_floor',
        default='30m',
        spec_type='tf',
        py_type='str',
        members=('15m', '30m', '1H', '2H', '4H', '8H', '12H', '1D', '2D', '3D', '1W', '1m', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='CF-38; Q14 stated, S5-R34 / S5 `[01:41:45]`; S8 `[01:34:48]` on low-timeframe unreliability',
        group='11.8',
        note='Q14: "5m" stays reachable only via counter_trend_demote_to_scalp (S7-R10). Sweep {15m, 30m, 1H}.',
    ),
    KeySpec(
        key='event_blackout_mode',
        default='leverage_only',
        spec_type='enum',
        py_type='str',
        members=('leverage_only', 'all', 'none'),
        minimum=None,
        maximum=None,
        source_id='CF-39; S8-R2',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='event_blackout_hours',
        default=24,
        spec_type='int (hours)',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-39 — OUR number',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='event_resume_requires_range',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-39; S2-R27',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='weekend_mode',
        default='leverage_blocked',
        spec_type='enum',
        py_type='str',
        members=('leverage_blocked', 'block_all', 'normal'),
        minimum=None,
        maximum=None,
        source_id='CF-39; TBOT1-R24, TBOT1-C8',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='event_tf_step_up',
        default=1,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-39; S5-R36',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='leverage_max_mcap_rank',
        default=100,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-40; S2 §2 (large/mid boundary)',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='min_daily_volume_usd',
        default=50000000,
        spec_type='int (USD)',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-40, P18 — floor is OURS; S8-R31',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='new_listing_days',
        default=30,
        spec_type='int (days)',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-40 — OUR number; S6-R44',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='universe_max_symbols',
        default=3,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='CF-40; S8-R33',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='scalp_excludes_btc',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-40; S8-R32',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='memecoin_vehicle',
        default='spot_only',
        spec_type='enum',
        py_type='str',
        members=('spot_only', 'excluded', 'any'),
        minimum=None,
        maximum=None,
        source_id='CF-40; S6-R45, S7-R38',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='max_median_wick_ratio',
        default=0.55,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1.0,
        source_id='P18 — [OUR CHOICE]; S2-R35, S2-A20',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='max_wicky_bar_fraction',
        default=0.4,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=1.0,
        source_id='P18 — [OUR CHOICE]; S7-A24',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='shorts_enabled',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-41; S7-C9',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='net_short_allowed_in_uptrend',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-41; S4-R36',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='short_in_price_discovery',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-41; S3-R28, S6-R37',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='min_expected_move_pct',
        default={'scalp': 2.0, 'swing': 5.0},
        spec_type='map',
        py_type='dict',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-41; S3-R15, S6-R8, S8 `[00:47:58]`',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='cup_handle_floor_pct',
        default=45.0,
        spec_type='pct of cup depth',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='S4-R24, S4-A9 — midpoint is [OUR CHOICE]',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='pattern_pole_anchor',
        default='most_recent_impulse',
        spec_type='enum',
        py_type='str',
        members=('most_recent_impulse', 'first_impulse'),
        minimum=None,
        maximum=None,
        source_id='S4-R17, S4-C6 — [OUR CHOICE]',
        group='11.8',
        note='',
    ),
    KeySpec(
        key='min_rr',
        default=2.0,
        spec_type='decimal',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-42 — OUR number, now corroborated as a floor by F9; S3-R26 (1:1 rejected)',
        group='11.9',
        note='F9: four frames of his own position-tool R:R readout — 3.17 (TBOT1 4:11), '
             '5.00 (TBOT1 22:59), 2.97 (TBOT1 1:09:19), 2.13 (S8 1:28:33). Observed range '
             '2.13-5.00; the lowest trade he took is 2.13, so 2.0 sits just under every '
             'observation rather than being an invented midpoint. Still OUR number in the sense '
             'that he never states a floor (TBOT1-A11: "the best R:R you can get", no number) — '
             'derived-with-support, not stated. Sweep 2.0-2.5.',
        sweep_bracket=(2.0, 2.5),
    ),
    KeySpec(
        key='rr_measured_to',
        default='final_tp',
        spec_type='enum',
        py_type='str',
        members=('tp1', 'final_tp'),
        minimum=None,
        maximum=None,
        source_id='CF-42; F9 — TBOT1 4:11, TBOT1 22:59, TBOT1 1:09:19, S8 1:28:33',
        group='11.9',
        note='F9 changed this from "tp1" to "final_tp". His TradingView position tool shows a '
             'single target line and its R:R readout measures to that line — a FINAL target, not '
             'a first partial. That the tool measures that way is OUR reading of TradingView, '
             'not something he states; the four observed ratios are what is directly evidenced. '
             'The bot ladders 2-5 structural TPs and TP1 is by construction the NEAREST of them '
             '(SPEC.md 8.7), so measuring to TP1 gated at a materially stricter level than he '
             'trades at. Alternative "tp1" recorded, and it is what shipped before F9.',
    ),
    KeySpec(
        key='rr_measured_from',
        default='average_entry',
        spec_type='enum',
        py_type='str',
        members=('average_entry', 'first_entry'),
        minimum=None,
        maximum=None,
        source_id='CF-42; CF-18',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='account_scoped_cut_rules',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-43; S2-C6, S2 `[00:53:58]`',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='long_term_exit_mode',
        default='macro_msb_two_step',
        spec_type='enum',
        py_type='str',
        members=('macro_msb_two_step', 'level_loss'),
        minimum=None,
        maximum=None,
        source_id='CF-43; S3-R21, S7-R36',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='long_term_derisk_multiple',
        default={'full': 3.0, 'partial': 2.0},
        spec_type='map',
        py_type='dict',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-43; S2-R18',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='challenge_goal_pct',
        default=8.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='CF-44; S2-C7',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='challenge_cadence',
        default='weekly',
        spec_type='enum',
        py_type='str',
        members=('weekly', 'daily'),
        minimum=None,
        maximum=None,
        source_id='CF-44; S2-R33',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='challenge_stop_on_goal',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-44; S2-R22',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='daily_loss_count_limit',
        default=2,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='CF-44; S2-R21',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='loss_definition',
        default='closed_below_average_entry_net_fees',
        spec_type='enum',
        py_type='str',
        members=('closed_below_average_entry_net_fees', 'stop_out_only'),
        minimum=None,
        maximum=None,
        source_id='CF-44; S2-A23',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='risk_ratchet_up_allowed',
        default=False,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-44; S2-R24',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='equity_restart_mode',
        default='off',
        spec_type='enum',
        py_type='str',
        members=('off', 'halve_on_drawdown'),
        minimum=None,
        maximum=None,
        source_id='S2-R26 — default is [OUR CHOICE]',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='day_boundary_utc',
        default='00:00',
        spec_type='time',
        py_type='str',
        members=None,
        minimum=None,
        maximum=None,
        source_id='CF-45, P16; S5-R8, S8-R44',
        group='11.9',
        note='',
    ),
    KeySpec(
        key='alloc_futures_pct',
        default=10.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='S2-R16',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='alloc_cash_min_pct',
        default=20.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='S2-R17, S2-C5',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='alloc_large_cap_pct',
        default=35.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=30.0,
        maximum=40.0,
        source_id='S2-R16',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='alloc_mid_cap_pct',
        default=15.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=10.0,
        maximum=20.0,
        source_id='S2-R16',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='alloc_small_cap_pct',
        default=5.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=100.0,
        source_id='S2-R16',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='alloc_micro_cap_pct',
        default=3.0,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=2.0,
        maximum=5.0,
        source_id='S2-R16',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='long_term_max_large_caps',
        default=5,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=4.0,
        maximum=7.0,
        source_id='S2-R19',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='long_term_max_mid_caps',
        default=4,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=3.0,
        maximum=4.0,
        source_id='S2-R19',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='spot_short_term_tp_move_pct',
        default=12.5,
        spec_type='pct',
        py_type='float',
        members=None,
        minimum=10.0,
        maximum=15.0,
        source_id='S2 `[01:15:16]`',
        group='11.10',
        note='',
    ),
    KeySpec(
        key='atr_period',
        default=14,
        spec_type='int',
        py_type='int',
        members=None,
        minimum=1.0,
        maximum=None,
        source_id='ATR(14) is assumed throughout CONFLICTS.md — [OUR CHOICE]',
        group='11.11',
        note='',
    ),
    KeySpec(
        key='pmt_bin_atr',
        default=0.05,
        spec_type='atr',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=None,
        source_id='P20 — [OUR CHOICE]; S5-A15',
        group='11.11',
        note='',
    ),
    KeySpec(
        key='backtest_execution_tf',
        default='1m',
        spec_type='tf',
        py_type='str',
        members=('1m', '15m', '30m', '1H', '2H', '4H', '8H', '12H', '1D', '2D', '3D', '1W', '5m', 'trade_tf', 'structure_tf'),
        minimum=None,
        maximum=None,
        source_id='[OUR CHOICE] — §12.2',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='intrabar_fill_model',
        default='stop_first',
        spec_type='enum',
        py_type='str',
        members=('stop_first', 'tp_first', 'proportional'),
        minimum=None,
        maximum=None,
        source_id='[OUR CHOICE] — §12.2, deliberately pessimistic',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='fee_maker_bps',
        default=2.0,
        spec_type='bps',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=10.0,
        source_id='[OUR CHOICE]',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='fee_taker_bps',
        default=5.5,
        spec_type='bps',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=15.0,
        source_id='[OUR CHOICE]',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='slippage_limit_bps',
        default=0.0,
        spec_type='bps',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=5.0,
        source_id='[OUR CHOICE] — limits fill at price or not at all',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='slippage_market_bps',
        default=5.0,
        spec_type='bps',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=25.0,
        source_id='[OUR CHOICE]',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='funding_bps_per_8h',
        default=1.0,
        spec_type='bps',
        py_type='float',
        members=None,
        minimum=0.0,
        maximum=5.0,
        source_id='[OUR CHOICE] — leverage only',
        group='11.12',
        note='',
    ),
    KeySpec(
        key='limit_fill_requires_trade_through',
        default=True,
        spec_type='bool',
        py_type='bool',
        members=None,
        minimum=None,
        maximum=None,
        source_id='[OUR CHOICE] — §12.2',
        group='11.12',
        note='',
    ),
)


KEY_SPEC_BY_NAME: dict[str, KeySpec] = {spec.key: spec for spec in KEY_SPECS}


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto ``base``, returning a new dict.

    Mappings merge key-by-key; every other value (including lists) is replaced wholesale, so a
    YAML file that sets ``tp_split_3: [0.5, 0.25, 0.25]`` replaces the list rather than
    element-wise patching it.
    """
    out: dict[str, Any] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in override.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = list(v) if isinstance(v, list) else v
    return out


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class Config:
    """Every SPEC.md §11 key, with its documented default.

    Construct with :meth:`load` (defaults, optionally deep-merged with a YAML file) or directly
    with keyword arguments.  The instance is frozen; use :meth:`with_overrides` for a modified
    copy (that is how a backtest parameter sweep should vary keys).
    """


    max_loss_pct_swing: float = 4.0
    max_loss_pct_swing_hard_cap: float = 5.0
    max_loss_pct_scalp: float = 2.5
    max_loss_pct_counter_trend: float = 2.0
    max_loss_pct_low_conviction: float = 1.5
    high_conviction_loss_pct_enabled: bool = False
    max_notional_pct_leverage: float = 100.0
    margin_pct_leverage: float = 10.0
    default_leverage: float = 10.0
    spot_notional_pct_high_conviction: float = 12.0
    spot_notional_pct_low_conviction: float = 6.0
    max_total_spot_deployment_pct: float = 70.0
    counter_trend_mode: str = 'size_down_and_demote'
    counter_trend_size_multiplier: float = 0.5
    counter_trend_demote_to_scalp: bool = True
    max_concurrent_leverage_swing: int = 2
    max_concurrent_leverage_scalp: int = 2
    max_concurrent_leverage_global: int = 4
    max_concurrent_spot: int = 5
    spot_exit_mode: str = 'close_below_level_then_flip'
    spot_synthetic_stop_for_sizing: bool = True
    spot_invalidation_timeframe: str = '1D'
    duplicate_stop_offset_bps: float = 1.5
    max_stop_pct_leverage: float = 9.0
    wide_stop_policy: str = 'tighten_then_downgrade_then_skip'
    stop_tighten_tf_steps: int = 2
    min_stop_pct: float = 0.5
    leverage_downgrade_max_multiple: float = 3.0
    hedge_enabled: bool = False
    hedge_size_ratio: float = 1.0
    hedge_max_leverage: float = 3.0
    line_touch_hard_limit: int = 3
    range_boundary_touch_limit: int = 6
    touch_size_decay: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0, 0.66, 0.5])
    zone_touch_uses_fill_rule_not_count: bool = True
    zone_fill_invalidation_pct: float = 50.0
    zone_fill_measure: str = 'wick_touch'
    zone_fill_reference: str = 'as_originally_drawn'
    dead_zone_htf_support_rescue: bool = True
    dead_zone_rescue_max_touches: int = 3
    ob_max_candles: int = 1
    ob_box_source: str = 'body_with_small_wick'
    ob_inside_zone_precedence: str = 'zone_wins'
    ob_liquidity_measure: str = 'deepest_wick_through_body_range'
    ob_fill_invalidation_pct: float = 75.0
    zone_direction_mode: str = 'both'
    zone_continuation_confluence_bonus: float = 1.0
    sufficient_gap_pct_by_tf: dict[str, float] = field(default_factory=lambda: {'15m': 3.0, '30m': 4.0, '1H': 4.0, '2H': 5.0, '4H': 6.0, '8H': 7.0, '12H': 7.5, '1D': 8.0, '2D': 13.0, '3D': 15.0, '1W': 15.0})
    sufficient_gap_atr_mult: float = 2.0
    sufficient_gap_require_both_tests: bool = True
    sufficient_gap_anchor: str = 'breakout_close_to_extreme'
    sufficient_gap_retrace_cutoff: float = 0.5
    min_zone_depth_atr: float = 0.5
    max_zone_depth_atr: float = 3.0
    min_zone_bodies: int = 2
    zone_within_zone_policy: str = 'larger_if_within_max_depth'
    wick_include_max_pct: float = 2.0
    wick_include_max_atr: float = 0.5
    zone_box_source: str = 'body_plus_small_wick'
    zone_wick_band_enabled: bool = False
    zone_wick_band_max_ratio: float = 1.0
    stop_wick_max_pct: float = 3.0
    stop_buffer_atr: float = 0.15
    stop_buffer_zone_fraction: float = 0.5
    stop_never_beyond_opposing_level: bool = True
    flip_confirm_candles: int = 2
    flip_extra_candle_below_tf: str = '4H'
    flip_requires_body_close: bool = True
    pending_sr_expiry_bars: int = 60
    entry_family_retest_enabled: bool = True
    entry_family_flip_pending_enabled: bool = True
    entry_family_trigger_enabled: bool = True
    max_entry_distance_enabled: bool = False
    max_entry_distance_pct: float = 15.0
    presr_light_limit_enabled: bool = False
    allow_market_orders: str = 'trigger_family_only'
    dca_count_default: int = 1
    dca_count_max: int = 2
    dca_count_scalp_max: int = 1
    dca_count_breakdown: int = 0
    dca2_min_zone_depth_atr: float = 1.5
    dca_size_split_2: list[float] = field(default_factory=lambda: [0.39, 0.61])
    dca_size_split_3: list[float] = field(default_factory=lambda: [0.2, 0.3, 0.5])
    dca_size_split_wick_heavy_2: list[float] = field(default_factory=lambda: [0.25, 0.75])
    size_and_stop_computed_from: str = 'average_entry'
    average_up_enabled: bool = False
    average_up_trigger_atr: float = 2.0
    average_up_only_at_sr_point: bool = True
    sfp_entry_price: str = 'confirming_close'
    sfp_standalone_enabled: bool = False
    sfp_min_bars_between: int = 3
    sfp_raid_price_source: str = 'wick'
    sfp_min_swing_separation_atr: float = 1.0
    sfp_max_close_distance_atr: float = 1.5
    sfp_trend_veto: bool = True
    sfp_governing_timeframe: str = 'highest_valid'
    reentry_trigger: str = 'sfp_or_close_reclaim'
    reentry_max_attempts_per_level: int = 2
    reentry_cooldown_bars: int = 3
    reentry_window_bars: int = 100
    reentry_stacked_conditionals_enabled: bool = True
    msb_exit_mode: str = 'break_only'
    msb_entry_requires_retest: bool = True
    msb_retest_timeout_bars: int = 20
    msb_deviation_invalidates: bool = True
    msb_price_source: str = 'body_close'
    higher_low_selection: str = 'technical'
    bias_level_enabled: bool = True
    bias_level_min_confluence: float = 2.0
    bias_level_lookback_bars: int = 200
    structure_tf_offset: int = 2
    htf_veto_enabled: bool = True
    htf_veto_timeframe: str = '1D'
    swing_k: int = 3
    swing_price_source: str = 'body'
    trend_pivot_count: int = 4
    trend_timeframe: str = 'structure_tf'
    dir_change_atr: float = 2.0
    dir_change_max_bars: int = 10
    dir_change_uses_sufficient_gap_table: bool = True
    level_lookback_bars: int = 500
    level_cluster_atr: float = 0.25
    level_min_touches: int = 2
    level_tolerance_atr: float = 0.15
    touch_reset_atr: float = 0.5
    capitulation_wick_atr: float = 3.0
    capitulation_wick_body_ratio: float = 3.0
    capitulation_volume_mult: float = 2.0
    consolidation_max_drift_atr: float = 0.75
    consolidation_max_height_atr: float = 2.0
    consolidation_min_bars: int = 2
    mid_range_band_pct: float = 15.0
    mid_range_limits_from_extremes_enabled: bool = True
    mid_range_requires_intermediate_stop: bool = True
    range_death_mode: str = 'close_beyond_plus_flip'
    mid_range_search_pct: float = 10.0
    range_min_height_atr: float = 3.0
    range_max_age_bars: int = 300
    range_min_bars: int = 20
    range_stale_bars: int = 60
    monday_range_source_tf: str = '1D'
    tp_count_swing: int = 2
    tp_count_scalp: int = 3
    tp_count_price_discovery_max: int = 5
    tp_min_count: int = 2
    tp_split_2: list[float] = field(default_factory=lambda: [0.5, 0.5])
    tp_split_3: list[float] = field(default_factory=lambda: [0.4, 0.3, 0.3])
    tp_split_4: list[float] = field(default_factory=lambda: [0.4, 0.25, 0.2, 0.15])
    tp_split_5: list[float] = field(default_factory=lambda: [0.35, 0.25, 0.2, 0.12, 0.08])
    tp_residual_policy: str = 'trail_out'
    trail_on_tp1: str = 'break_even'
    trail_on_tp2: str = 'tp1_price'
    break_even_reference: str = 'average_entry'
    stale_exit_enabled: bool = False
    stale_exit_bars: int = 8
    stale_exit_mae_atr: float = 1.0
    reaction_threshold_atr: float = 0.75
    structural_stale_exit_enabled: bool = True
    min_confluence_count: float = 3.0
    confluence_gate_mode: str = 'raw_count'
    confluence_weights: dict[str, float] = field(default_factory=lambda: {'sr_level': 1.5, 'zone': 1.25, 'order_block': 1.0, 'range_boundary': 1.0, 'fib': 1.0, 'trendline': 0.75, 'pattern': 0.5, 'sfp': 0.5, 'rsi_divergence': 0.5, 'ema200': 0.5, 'cme_gap': 0.5})
    confluence_merge_atr: float = 0.25
    confluence_dedup_same_class: bool = True
    single_class_trade_forbidden: bool = True
    high_conviction_score: float = 4.0
    pipeline_order: list[str] = field(default_factory=lambda: ['universe_calendar_gate', 'load_align_candles', 'structure', 'levels_sr_flips', 'trend_lines', 'ranges_mid_range', 'liquidity_map', 'supply_demand_zones', 'order_blocks', 'context_regime', 'fibs', 'chart_patterns', 'confluence_scoring', 'sfp', 'rsi_divergence', 'ltf_refinement', 'setup_qualification', 'trade_plan_construction'])
    fib_loses_ties_to_sr: bool = True
    sfp_evaluated_last: bool = True
    golden_pocket_band: list[float] = field(default_factory=lambda: [0.618, 0.66])
    fib_levels_active: list[float] = field(default_factory=lambda: [0.618, 0.66, 0.786])
    fib_886_enabled: bool = False
    fib_entry_level: list[float] = field(default_factory=lambda: [0.618, 0.66])
    fib_dca_level: float = 0.786
    fib_draw_convention: str = 's6'
    fib_anchor_selection: str = 'most_recent_qualifying_swing_pair'
    dxy_gate_enabled: bool = False
    dxy_gate_min_rolling_corr: float = 0.4
    context_priority: list[str] = field(default_factory=lambda: ['USDT.D', 'BTC.D', 'BVOL'])
    bvol_zone: list[float] = field(default_factory=lambda: [0.81, 1.4])
    bvol_event_window_hours: int = 72
    bvol_size_multiplier: float = 0.5
    all_pairs_at_resistance_veto: bool = True
    rsi_divergence_mode: str = 'confluence_only'
    rsi_period: int = 14
    rsi_timeframe: str = 'structure_tf'
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    ema200_confluence_enabled: bool = False
    module_chart_patterns_enabled: bool = False
    module_trendline_break_enabled: bool = False
    module_scalp_enabled: bool = True
    disowned_modules_still_score_confluence: bool = True
    swing_tf_floor: str = '4H'
    scalp_tf_ceiling: str = '2H'
    scalp_tf_floor: str = '30m'
    event_blackout_mode: str = 'leverage_only'
    event_blackout_hours: int = 24
    event_resume_requires_range: bool = True
    weekend_mode: str = 'leverage_blocked'
    event_tf_step_up: int = 1
    leverage_max_mcap_rank: int = 100
    min_daily_volume_usd: int = 50000000
    new_listing_days: int = 30
    universe_max_symbols: int = 3
    scalp_excludes_btc: bool = True
    memecoin_vehicle: str = 'spot_only'
    max_median_wick_ratio: float = 0.55
    max_wicky_bar_fraction: float = 0.4
    shorts_enabled: bool = True
    net_short_allowed_in_uptrend: bool = False
    short_in_price_discovery: bool = False
    min_expected_move_pct: dict[str, float] = field(default_factory=lambda: {'scalp': 2.0, 'swing': 5.0})
    cup_handle_floor_pct: float = 45.0
    pattern_pole_anchor: str = 'most_recent_impulse'
    min_rr: float = 2.0
    rr_measured_to: str = 'final_tp'
    rr_measured_from: str = 'average_entry'
    account_scoped_cut_rules: bool = True
    long_term_exit_mode: str = 'macro_msb_two_step'
    long_term_derisk_multiple: dict[str, float] = field(default_factory=lambda: {'full': 3.0, 'partial': 2.0})
    challenge_goal_pct: float = 8.0
    challenge_cadence: str = 'weekly'
    challenge_stop_on_goal: bool = True
    daily_loss_count_limit: int = 2
    loss_definition: str = 'closed_below_average_entry_net_fees'
    risk_ratchet_up_allowed: bool = False
    equity_restart_mode: str = 'off'
    day_boundary_utc: str = '00:00'
    alloc_futures_pct: float = 10.0
    alloc_cash_min_pct: float = 20.0
    alloc_large_cap_pct: float = 35.0
    alloc_mid_cap_pct: float = 15.0
    alloc_small_cap_pct: float = 5.0
    alloc_micro_cap_pct: float = 3.0
    long_term_max_large_caps: int = 5
    long_term_max_mid_caps: int = 4
    spot_short_term_tp_move_pct: float = 12.5
    atr_period: int = 14
    pmt_bin_atr: float = 0.05
    backtest_execution_tf: str = '1m'
    intrabar_fill_model: str = 'stop_first'
    fee_maker_bps: float = 2.0
    fee_taker_bps: float = 5.5
    slippage_limit_bps: float = 0.0
    slippage_market_bps: float = 5.0
    funding_bps_per_8h: float = 1.0
    limit_fill_requires_trade_through: bool = True

    # ------------------------------------------------------------------ construction

    @classmethod
    def load(cls, path: str | Path | None = None, *, validate: bool = True) -> "Config":
        """Return defaults when ``path`` is None, else defaults deep-merged with the YAML file.

        The YAML file is a flat mapping of ``key: value`` (nested mappings are only used for the
        ``map``-typed keys such as ``sufficient_gap_pct_by_tf``).  Unknown keys are a validation
        error, not a silent no-op.

        Raises :class:`ConfigError` listing every problem when ``validate`` is true.
        """
        data = cls.defaults_dict()
        problems: list[str] = []
        if path is not None:
            raw = yaml.safe_load(Path(path).read_text()) or {}
            if not isinstance(raw, Mapping):
                raise ConfigError([f"{path}: top level of the config file must be a mapping"])
            unknown = [k for k in raw if k not in KEY_SPEC_BY_NAME]
            problems += [f"unknown config key {k!r} (not in SPEC.md §11)" for k in sorted(unknown)]
            known = {k: v for k, v in raw.items() if k in KEY_SPEC_BY_NAME}
            data = deep_merge(data, known)
        cfg = cls(**data)
        if validate:
            cfg.validate(_extra_problems=problems)
        elif problems:
            raise ConfigError(problems)
        return cfg

    @classmethod
    def defaults_dict(cls) -> dict[str, Any]:
        """A fresh ``{key: default}`` dict for all 245 keys."""
        return {spec.key: spec.copy_default() for spec in KEY_SPECS}

    def with_overrides(self, **overrides: Any) -> "Config":
        """A validated copy with ``overrides`` applied (sweep helper)."""
        unknown = [k for k in overrides if k not in KEY_SPEC_BY_NAME]
        if unknown:
            raise ConfigError([f"unknown config key {k!r} (not in SPEC.md §11)" for k in sorted(unknown)])
        cfg = replace(self, **overrides)
        cfg.validate()
        return cfg

    # ------------------------------------------------------------------ access

    def to_dict(self) -> dict[str, Any]:
        """Flat ``{key: value}`` snapshot (containers copied)."""
        out: dict[str, Any] = {}
        for spec in KEY_SPECS:
            value = getattr(self, spec.key)
            out[spec.key] = list(value) if isinstance(value, list) else (
                dict(value) if isinstance(value, dict) else value
            )
        return out

    def describe(self) -> list[tuple[str, Any, Any, str]]:
        """``[(key, value, default, source_id)]`` in SPEC.md §11 table order, for CLI provenance."""
        return [
            (spec.key, getattr(self, spec.key), spec.copy_default(), spec.source_id)
            for spec in KEY_SPECS
        ]

    def non_default_keys(self) -> list[str]:
        """Keys whose current value differs from the SPEC.md default."""
        return [s.key for s in KEY_SPECS if getattr(self, s.key) != s.default]

    # ------------------------------------------------------------------ validation

    def validate(self, *, _extra_problems: Iterable[str] = ()) -> "Config":
        """Type-check and range-check every key; raise :class:`ConfigError` with **all** problems.

        Checks, in order: python type, enum membership, numeric bounds (from the §11 "Allowed"
        column where it gives one, otherwise the natural bound of the declared type), container
        shape, then the cross-key structural invariants of §8/§11.
        """
        problems: list[str] = list(_extra_problems)
        for spec in KEY_SPECS:
            problems += _check_key(spec, getattr(self, spec.key))
        problems += _cross_checks(self)
        if problems:
            raise ConfigError(problems)
        return self


def _check_key(spec: KeySpec, value: Any) -> list[str]:
    problems: list[str] = []
    k = spec.key
    if spec.py_type == "bool":
        if not isinstance(value, bool):
            return [f"{k}: expected bool, got {type(value).__name__} ({value!r})"]
    elif spec.py_type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            if _is_number(value) and float(value).is_integer():
                value = int(value)
            else:
                return [f"{k}: expected int ({spec.spec_type}), got {type(value).__name__} ({value!r})"]
    elif spec.py_type == "float":
        if not _is_number(value):
            return [f"{k}: expected number ({spec.spec_type}), got {type(value).__name__} ({value!r})"]
    elif spec.py_type == "str":
        if not isinstance(value, str):
            return [f"{k}: expected str ({spec.spec_type}), got {type(value).__name__} ({value!r})"]
    elif spec.py_type == "list":
        if not isinstance(value, list):
            return [f"{k}: expected list, got {type(value).__name__} ({value!r})"]
    elif spec.py_type == "dict":
        if not isinstance(value, dict):
            return [f"{k}: expected mapping, got {type(value).__name__} ({value!r})"]

    if spec.members is not None and isinstance(value, str) and value not in spec.members:
        problems.append(f"{k}: {value!r} is not one of {list(spec.members)}")
    if _is_number(value):
        if spec.minimum is not None and float(value) < spec.minimum:
            problems.append(f"{k}: {value!r} is below the minimum {spec.minimum}")
        if spec.maximum is not None and float(value) > spec.maximum:
            problems.append(f"{k}: {value!r} is above the maximum {spec.maximum}")
    if isinstance(value, list) and spec.default and isinstance(spec.default[0], (int, float)):
        bad = [v for v in value if not _is_number(v)]
        if bad:
            problems.append(f"{k}: list must hold numbers, found {bad!r}")
    if isinstance(value, dict):
        bad_keys = [key for key in value if not isinstance(key, str)]
        if bad_keys:
            problems.append(f"{k}: map keys must be strings, found {bad_keys!r}")
    return problems


def _sum_to_one(name: str, value: Sequence[float], length: int) -> list[str]:
    problems: list[str] = []
    if len(value) != length:
        problems.append(f"{name}: expected {length} fractions, got {len(value)}")
    if value and all(_is_number(v) for v in value):
        if any(v < 0 for v in value):
            problems.append(f"{name}: fractions must be non-negative, got {list(value)}")
        total = float(sum(value))
        if abs(total - 1.0) > 1e-9:
            problems.append(f"{name}: fractions must sum to 1.0, got {total!r}")
    return problems


def _ascending_pair(name: str, value: Sequence[float]) -> list[str]:
    if len(value) != 2:
        return [f"{name}: expected exactly 2 values, got {len(value)}"]
    if all(_is_number(v) for v in value) and not value[0] < value[1]:
        return [f"{name}: must be ascending, got {list(value)}"]
    return []


def _cross_checks(cfg: "Config") -> list[str]:
    p: list[str] = []
    p += _sum_to_one("dca_size_split_2", cfg.dca_size_split_2, 2)
    p += _sum_to_one("dca_size_split_3", cfg.dca_size_split_3, 3)
    p += _sum_to_one("dca_size_split_wick_heavy_2", cfg.dca_size_split_wick_heavy_2, 2)
    p += _sum_to_one("tp_split_2", cfg.tp_split_2, 2)
    p += _sum_to_one("tp_split_3", cfg.tp_split_3, 3)
    p += _sum_to_one("tp_split_4", cfg.tp_split_4, 4)
    p += _sum_to_one("tp_split_5", cfg.tp_split_5, 5)
    p += _ascending_pair("golden_pocket_band", cfg.golden_pocket_band)
    p += _ascending_pair("fib_entry_level", cfg.fib_entry_level)
    p += _ascending_pair("bvol_zone", cfg.bvol_zone)

    if len(cfg.touch_size_decay) != 5:
        p.append(f"touch_size_decay: expected 5 multipliers (touch 1..5), got {len(cfg.touch_size_decay)}")
    if any(_is_number(v) and not 0.0 <= v <= 1.0 for v in cfg.touch_size_decay):
        p.append(f"touch_size_decay: every multiplier must be in [0, 1], got {list(cfg.touch_size_decay)}")

    if not cfg.fib_levels_active:
        p.append("fib_levels_active: must list at least one fib ratio")
    if any(_is_number(v) and not 0.0 < v < 1.0 for v in cfg.fib_levels_active):
        p.append(f"fib_levels_active: ratios must be in (0, 1), got {list(cfg.fib_levels_active)}")
    if not cfg.context_priority:
        p.append("context_priority: must not be empty (CF-35)")

    if sorted(cfg.pipeline_order) != sorted(PIPELINE_STAGES):
        p.append("pipeline_order: must be a permutation of the 18 SPEC.md §3.1 stage names")

    unknown_tf = [tf for tf in cfg.sufficient_gap_pct_by_tf if tf not in TIMEFRAME_LADDER]
    if unknown_tf:
        p.append(f"sufficient_gap_pct_by_tf: keys must be ladder timeframes, found {unknown_tf}")
    missing_tf = [tf for tf in TIMEFRAME_LADDER if tf not in cfg.sufficient_gap_pct_by_tf]
    if missing_tf:
        p.append(f"sufficient_gap_pct_by_tf: missing ladder timeframes {missing_tf}")
    if set(cfg.min_expected_move_pct) != {"scalp", "swing"}:
        p.append("min_expected_move_pct: must map exactly {'scalp', 'swing'} (CF-41)")
    if set(cfg.long_term_derisk_multiple) != {"full", "partial"}:
        p.append("long_term_derisk_multiple: must map exactly {'full', 'partial'} (CF-43)")
    negative_weights = {k: v for k, v in cfg.confluence_weights.items() if _is_number(v) and v < 0}
    if negative_weights:
        p.append(f"confluence_weights: weights must be non-negative, got {negative_weights}")

    if cfg.max_loss_pct_swing > cfg.max_loss_pct_swing_hard_cap:
        p.append("max_loss_pct_swing must not exceed max_loss_pct_swing_hard_cap (CF-01)")
    if cfg.min_zone_depth_atr >= cfg.max_zone_depth_atr:
        p.append("min_zone_depth_atr must be strictly below max_zone_depth_atr (CF-12)")
    if cfg.rsi_oversold >= cfg.rsi_overbought:
        p.append("rsi_oversold must be strictly below rsi_overbought (CF-36)")
    if cfg.dca_count_default > cfg.dca_count_max:
        p.append("dca_count_default must not exceed dca_count_max (CF-17)")
    if cfg.dca_count_scalp_max > cfg.dca_count_max:
        p.append("dca_count_scalp_max must not exceed dca_count_max (CF-17)")
    if cfg.tp_count_swing < cfg.tp_min_count or cfg.tp_count_scalp < cfg.tp_min_count:
        p.append("tp_count_swing and tp_count_scalp must be >= tp_min_count (CF-27)")
    if cfg.tp_count_price_discovery_max < cfg.tp_min_count:
        p.append("tp_count_price_discovery_max must be >= tp_min_count (CF-27)")
    if cfg.high_conviction_score < cfg.min_confluence_count:
        p.append("high_conviction_score must be >= min_confluence_count (§6.3)")
    if cfg.min_stop_pct > cfg.max_stop_pct_leverage:
        p.append("min_stop_pct must not exceed max_stop_pct_leverage (CF-06)")
    if cfg.range_min_bars > cfg.range_max_age_bars:
        p.append("range_min_bars must not exceed range_max_age_bars (P8)")
    if cfg.consolidation_min_bars > cfg.min_zone_bodies + cfg.consolidation_min_bars:
        p.append("consolidation_min_bars is inconsistent with min_zone_bodies (P13, CF-12)")
    if cfg.level_min_touches < 1:
        p.append("level_min_touches must be >= 1 (P3)")

    for lo_key, hi_key in (("scalp_tf_floor", "scalp_tf_ceiling"),):
        lo, hi = getattr(cfg, lo_key), getattr(cfg, hi_key)
        if lo in TIMEFRAME_LADDER and hi in TIMEFRAME_LADDER:
            if TIMEFRAME_LADDER.index(lo) > TIMEFRAME_LADDER.index(hi):
                p.append(f"{lo_key} ({lo}) must not sit above {hi_key} ({hi}) on the ladder (CF-38)")

    alloc = (cfg.alloc_futures_pct + cfg.alloc_large_cap_pct + cfg.alloc_mid_cap_pct
             + cfg.alloc_small_cap_pct + cfg.alloc_micro_cap_pct + cfg.alloc_cash_min_pct)
    if alloc > 100.0 + 1e-9:
        p.append(f"portfolio allocation (alloc_* + cash floor) sums to {alloc}%, above 100% (S2-R16/R17)")

    if ":" in cfg.day_boundary_utc:
        hh, _, mm = cfg.day_boundary_utc.partition(":")
        if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            p.append(f"day_boundary_utc: {cfg.day_boundary_utc!r} is not an HH:MM UTC time (CF-45, P16)")
    else:
        p.append(f"day_boundary_utc: {cfg.day_boundary_utc!r} is not an HH:MM UTC time (CF-45, P16)")
    return p


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_scalar(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_yaml_scalar(v)}" for k, v in value.items()) + "}"
    return repr(value)


def write_default_yaml(path: str | Path) -> Path:
    """Write the full 247-key default set to ``path``, one commented line per key.

    Each key is preceded by a comment giving its §11 group, declared type and **source ID**, so the
    file doubles as the provenance reference for the defaults.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# tbot default configuration — 247 keys: SPEC.md §11 (234) + the 8 evidence-derived",
        "# additions recorded in CHANGELOG_EVIDENCE.md + the 3 frame-derived additions",
        "# (F1 pass 1: zone_wick_band_*; F6 pass 2: stop_buffer_zone_fraction) recorded in",
        "# FRAME_FINDINGS.md + the 2 Discord-derived additions (max_entry_distance_*,",
        "# DISCORD CHECK 2026-09-15).",
        "# Generated by tbot.config.write_default_yaml(); each key carries its source ID.",
        "# Keys whose source says [OUR CHOICE] / OUR number have no basis in the transcripts:",
        "# sweep those first.",
        "",
    ]
    current_group = ""
    for spec in KEY_SPECS:
        if spec.group != current_group:
            current_group = spec.group
            lines += ["", f"# ===== SPEC.md §{current_group} " + "=" * 40, ""]
        note = f" | {spec.note}" if spec.note else ""
        members = f" | one of: {', '.join(spec.members)}" if spec.members else ""
        rng = ""
        if spec.minimum is not None or spec.maximum is not None:
            rng = f" | range: [{spec.minimum}, {spec.maximum if spec.maximum is not None else '+inf'}]"
        sweep = ""
        if spec.sweep_bracket is not None:
            sweep = f" | sweep_bracket: [{spec.sweep_bracket[0]}, {spec.sweep_bracket[1]}]"
        lines.append(f"# [{spec.spec_type}] source: {spec.source_id}{members}{rng}{sweep}{note}")
        lines.append(f"{spec.key}: {_yaml_scalar(spec.default)}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    import sys

    out = write_default_yaml(sys.argv[1] if len(sys.argv) > 1
                             else Path(__file__).resolve().parent.parent / "configs" / "default.yaml")
    print(f"wrote {out} ({len(KEY_SPECS)} keys)")
