"""SPEC.md §7 — setup qualification: the gate stack a scored confluence must survive.

A :class:`~tbot.models.Setup` becomes a plan only if it passes **every** gate.  Gates run in the
§7.1 order and **the first veto stops evaluation** (INTERFACES.md §9.6); the veto is recorded on
:attr:`tbot.models.Setup.vetoes` and returned as a structured :class:`Rejection`, never as a bare
``False`` — the backtest reports rejection attribution by gate, and a boolean cannot be attributed.

What this module owns
---------------------

* **G1/G2 universe** — the CF-40 tier ladder (high-cap, high-volume, wick-screened; memecoins and
  new listings demoted to spot rather than excluded), BTC excluded from the scalp module, and the
  1–3 concurrent-symbol watchlist cap.
* **G3/G4 calendar** — no leverage inside an event window (FOMC, CPI, war headlines) or across the
  weekend; **spot dip-buying stays permitted** (CF-39, S8-R2).  The calendar is an *injected* list
  of :class:`CalendarEvent`\\ s: nothing here fetches anything (INTERFACES.md §1.8), and
  unscheduled news is explicitly out of scope (TBOT1-A23).
* **G5 confluence / conviction** — the §6 score and class count, plus an optional caller-supplied
  conviction floor.
* **G7 regime** — the :mod:`tbot.regime` verdict: hard veto, or risk-off blocking new alt longs.
* **G9/G10 shorting policy** (CF-41) and **G14/G15** (R:R and expected move).
* **CF-03 counter-trend handling** — a modifier, not a gate: half size, demote to scalp, and a
  ``NEUTRAL`` trend is *not* counter-trend.

Gates whose numbers belong to other modules (G6 mid-range, G8 HTF veto, G11 object liveness,
G12/G13 stop, G16 TP count, G17 portfolio capacity, G18 module switch) are evaluated here **from
verdicts their owners pass in**, so the stack is complete and correctly ordered without this
module reading another module's config keys.

Config keys read here (``qualification.py`` block of INTERFACES.md §7, shared with
:mod:`tbot.regime`): ``leverage_max_mcap_rank``, ``min_daily_volume_usd``, ``memecoin_vehicle``,
``new_listing_days``, ``scalp_excludes_btc``, ``universe_max_symbols``, ``max_median_wick_ratio``
and ``max_wicky_bar_fraction`` (through P18), ``event_blackout_hours``, ``event_blackout_mode``,
``event_resume_requires_range``, ``event_tf_step_up``, ``weekend_mode``, ``shorts_enabled``,
``short_in_price_discovery``, ``net_short_allowed_in_uptrend``, ``min_expected_move_pct``,
``min_rr``, ``rr_measured_from``, ``rr_measured_to``, ``counter_trend_mode``,
``counter_trend_size_multiplier``, ``counter_trend_demote_to_scalp``, ``scalp_tf_floor``,
``scalp_tf_ceiling``, ``swing_tf_floor``.  ``min_confluence_count`` and
``single_class_trade_forbidden`` are re-read at G5 from the :mod:`tbot.confluence` block, because
G5 must be able to veto a setup whose score arrived precomputed.  ``confluence_gate_mode`` (Q5)
is read here too: the gate counts raw objects, the weights only rank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal, Sequence

from tbot.config import Config
from tbot.confluence import ConfluenceCluster
from tbot.models import (
    Conviction,
    Direction,
    FlipState,
    Level,
    LevelKind,
    Series,
    Setup,
    Timeframe,
    TradeClass,
    Trend,
    Vehicle,
    dec,
)
from tbot.regime import RegimeState
import tbot.primitives as P

__all__ = [
    "MODULE_SOURCE_IDS",
    "HIGH_IMPACT_KINDS",
    "CalendarEvent",
    "SymbolProfile",
    "UniverseVerdict",
    "Rejection",
    "QualificationResult",
    "is_btc",
    "trade_class_for_tf",
    "classify_universe",
    "active_events",
    "in_event_window",
    "counter_trend_adjustment",
    "qualify",
]

MODULE_SOURCE_IDS: tuple[str, ...] = (
    "CF-40",
    "CF-39",
    "CF-31",
    "CF-35",
    "CF-41",
    "CF-42",
    "CF-38",
    "CF-03",
)

#: Event kinds treated as high impact unless the caller says otherwise (CF-39, S8-R2, S5-R36).
HIGH_IMPACT_KINDS: frozenset[str] = frozenset(
    {"fomc", "cpi", "nfp", "war", "geopolitical", "conference"}
)

_ONE = Decimal(1)

_CONVICTION_RANK: dict[Conviction, int] = {
    Conviction.LOW: 0,
    Conviction.NORMAL: 1,
    Conviction.HIGH: 2,
}

_QUOTES: tuple[str, ...] = ("USDT", "USDC", "BUSD", "USD", "PERP", "SWAP")


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """One scheduled, machine-readable event (CF-39, gate G3).

    Injected by the caller — this module never fetches a calendar.  ``kind`` is free text; the
    members of :data:`HIGH_IMPACT_KINDS` default to high impact.  Unscheduled news is **not
    implemented** and cannot be (TBOT1-A23): a war headline reaches the bot only as an event
    somebody put on this list.
    """

    name: str
    kind: str
    start: datetime
    end: datetime | None = None
    high_impact: bool | None = None
    source_ids: tuple[str, ...] = ("CF-39",)

    @property
    def is_high_impact(self) -> bool:
        if self.high_impact is not None:
            return self.high_impact
        return self.kind.strip().lower() in HIGH_IMPACT_KINDS

    @property
    def finish(self) -> datetime:
        return self.end if self.end is not None else self.start


@dataclass(frozen=True, slots=True)
class SymbolProfile:
    """The off-chart facts gate G1 needs (CF-40).  Injected: no network, no exchange lookups."""

    symbol: str
    mcap_rank: int | None = None
    median_daily_volume_usd: Decimal | float | None = None
    is_memecoin: bool = False
    listed_days: int | None = None
    is_airdrop_chart: bool = False
    is_barcoding: bool = False


@dataclass(frozen=True, slots=True)
class UniverseVerdict:
    """CF-40 tiering.  Tier C is the *only* exclusion; B is a vehicle demotion, not a ban."""

    symbol: str
    tier: Literal["A", "B", "C"]
    vehicles: tuple[Vehicle, ...]
    reasons: tuple[str, ...]
    screen: P.LiquidityScreen | None = None
    source_ids: tuple[str, ...] = ("CF-40", "P18")

    @property
    def excluded(self) -> bool:
        return self.tier == "C"

    def permits(self, vehicle: Vehicle) -> bool:
        return vehicle in self.vehicles


# --------------------------------------------------------------------------- outputs


@dataclass(frozen=True, slots=True)
class Rejection:
    """A structured veto: which gate, which spec reason, and why in this instance."""

    gate: str            #: "G1" … "G18"
    reason: str          #: the SPEC.md §7.1 veto reason, e.g. ``"event_blackout"``
    detail: str
    source_ids: tuple[str, ...] = ()

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.gate}:{self.reason} ({self.detail})"


@dataclass(frozen=True, slots=True)
class QualificationResult:
    """The outcome of the §7.1 stack for one setup."""

    qualified: bool
    rejections: tuple[Rejection, ...]
    vehicle: Vehicle
    trade_class: TradeClass
    conviction: Conviction
    size_multiplier: Decimal
    universe: UniverseVerdict | None
    counter_trend: bool
    required_structure_tf: Timeframe | None
    notes: tuple[str, ...]
    source_ids: tuple[str, ...]
    flags: dict[str, Any] = field(default_factory=dict)

    @property
    def rejection(self) -> Rejection | None:
        """The first veto — what rejection attribution counts."""
        return self.rejections[0] if self.rejections else None

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(r.reason for r in self.rejections)


# --------------------------------------------------------------------------- helpers


def _base_asset(symbol: str) -> str:
    base = symbol.split(":")[-1].strip().upper().split("/")[0]
    for suffix in (".P", "-PERP", "_PERP", "-SWAP"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    for quote in _QUOTES:
        if base.endswith(quote) and len(base) > len(quote):
            return base[: -len(quote)]
    return base


def is_btc(symbol: str) -> bool:
    """Is this BTC itself?  ``scalp_excludes_btc`` (S8-R32) needs the base asset, not the pair."""
    return _base_asset(symbol) in ("BTC", "XBT")


def trade_class_for_tf(tf: Timeframe, config: Config) -> TradeClass:
    """CF-38 timeframe classes: ``scalp_tf_floor``…``scalp_tf_ceiling`` is a scalp,
    ``swing_tf_floor`` and above is a swing.

    Used to pick the ``min_expected_move_pct`` row (scalp 2.0 / swing 5.0) when the setup carries
    a class that is neither (counter-trend, price discovery).
    """
    scalp_floor = Timeframe.parse(config.scalp_tf_floor)
    scalp_ceiling = Timeframe.parse(config.scalp_tf_ceiling)
    swing_floor = Timeframe.parse(config.swing_tf_floor)
    if scalp_floor.rank <= tf.rank <= scalp_ceiling.rank:
        return TradeClass.SCALP
    if tf.rank >= swing_floor.rank:
        return TradeClass.SWING
    return TradeClass.SCALP


def _move_key(trade_class: TradeClass, tf: Timeframe, config: Config) -> str:
    if trade_class is TradeClass.SCALP:
        return "scalp"
    if trade_class is TradeClass.SWING:
        return "swing"
    return "scalp" if trade_class_for_tf(tf, config) is TradeClass.SCALP else "swing"


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _is_unbroken_support(level: Level) -> bool:
    """CF-41 gate 2: a short is permitted only at a broken-and-flipped level (S4-R9)."""
    if level.flip_state is FlipState.CONFIRMED_RESISTANCE:
        return False
    if level.kind in (
        LevelKind.RESISTANCE,
        LevelKind.SR_CONFIRMED_RESISTANCE,
        LevelKind.RANGE_HIGH,
    ):
        return False
    return level.kind in (
        LevelKind.SUPPORT,
        LevelKind.SR_CONFIRMED_SUPPORT,
        LevelKind.SR_PENDING,
        LevelKind.RANGE_LOW,
    )


# --------------------------------------------------------------------------- G1 universe


def classify_universe(
    profile: SymbolProfile,
    config: Config,
    *,
    series: Series | None = None,
    screen: P.LiquidityScreen | None = None,
) -> UniverseVerdict:
    """CF-40 / §7.3 tiering.

    ``A`` (leverage + spot): rank ≤ ``leverage_max_mcap_rank`` (100) **and** 30-day median USD
    volume ≥ ``min_daily_volume_usd`` (50M) **and** the P18 wick screen passes.
    ``B`` (spot only): passes volume but fails rank, or is a memecoin
    (``memecoin_vehicle = "spot_only"``), or is newly listed (< ``new_listing_days``), or fails
    the wick screen.  ``C`` (excluded): below the volume floor, barcoding, or an airdrop-driven
    chart.

    The meme and new-listing rules are **vehicle** exclusions, not universe exclusions — which is
    why he keeps calling levels on coins he says he does not trade (CF-40, TBOT1-C5, S4-C4).
    """
    reasons: list[str] = []
    volume = (
        dec(profile.median_daily_volume_usd)
        if profile.median_daily_volume_usd is not None
        else None
    )
    if screen is None and series is not None and len(series) > 0:
        screen = P.liquidity_screen(series, config, median_quote_volume_usd=volume)
    if volume is None and screen is not None:
        volume = screen.median_quote_volume_usd

    # --- Tier C: the only true exclusions.
    if volume is None:
        reasons.append("no volume figure supplied; cannot clear the CF-40 volume floor")
        return UniverseVerdict(profile.symbol, "C", (), tuple(reasons), screen)
    if volume < dec(config.min_daily_volume_usd):
        reasons.append(
            f"median daily volume {volume} < min_daily_volume_usd {config.min_daily_volume_usd}"
        )
        return UniverseVerdict(profile.symbol, "C", (), tuple(reasons), screen)
    if profile.is_barcoding:
        reasons.append("barcoding chart (S2-R35)")
        return UniverseVerdict(profile.symbol, "C", (), tuple(reasons), screen)
    if profile.is_airdrop_chart:
        reasons.append("airdrop-driven chart (S8 [01:04:42])")
        return UniverseVerdict(profile.symbol, "C", (), tuple(reasons), screen)
    if profile.is_memecoin and config.memecoin_vehicle == "excluded":
        reasons.append("memecoin and memecoin_vehicle == 'excluded'")
        return UniverseVerdict(profile.symbol, "C", (), tuple(reasons), screen)

    # --- Tier B: vehicle demotions.
    demoted = False
    if profile.mcap_rank is None or profile.mcap_rank > config.leverage_max_mcap_rank:
        demoted = True
        reasons.append(
            f"mcap rank {profile.mcap_rank} > leverage_max_mcap_rank "
            f"{config.leverage_max_mcap_rank}"
        )
    if profile.is_memecoin and config.memecoin_vehicle == "spot_only":
        demoted = True
        reasons.append("memecoin: spot only (S6-R45, S7-R38)")
    if profile.listed_days is not None and profile.listed_days < config.new_listing_days:
        demoted = True
        reasons.append(
            f"listed {profile.listed_days}d < new_listing_days {config.new_listing_days} (S6-R44)"
        )
    if screen is not None and (screen.wick_heavy or not screen.passes):
        demoted = True
        reasons.append("failed the P18 wick screen: " + "; ".join(screen.reasons))

    if demoted:
        return UniverseVerdict(profile.symbol, "B", (Vehicle.SPOT,), tuple(reasons), screen)
    return UniverseVerdict(
        profile.symbol, "A", (Vehicle.SPOT, Vehicle.LEVERAGE), tuple(reasons), screen
    )


# --------------------------------------------------------------------------- G3 calendar


def active_events(
    calendar: Sequence[CalendarEvent], now: datetime, config: Config
) -> tuple[CalendarEvent, ...]:
    """High-impact events whose ``event_blackout_hours`` window contains ``now``.

    The window is ``[start - event_blackout_hours, end + event_blackout_hours]`` (24h either side
    by default — **OUR number**, CF-39).
    """
    moment = _as_utc(now)
    span = timedelta(hours=config.event_blackout_hours)
    hits = [
        e
        for e in calendar
        if e.is_high_impact
        and _as_utc(e.start) - span <= moment <= _as_utc(e.finish) + span
    ]
    return tuple(sorted(hits, key=lambda e: (_as_utc(e.start), e.name)))


def in_event_window(calendar: Sequence[CalendarEvent], now: datetime, config: Config) -> bool:
    """Is ``now`` inside any high-impact event's blackout window?"""
    return bool(active_events(calendar, now, config))


# --------------------------------------------------------------------------- CF-03


def counter_trend_adjustment(
    direction: Direction, trend: Trend, config: Config
) -> tuple[bool, Decimal, bool]:
    """CF-03: ``(is_counter_trend, size_multiplier, demote_to_scalp)``.

    Counter-trend is **allowed, not vetoed** — size × ``counter_trend_size_multiplier`` (0.5) and
    reclassified as a scalp when ``counter_trend_demote_to_scalp``.  A ``NEUTRAL`` trend is
    explicitly **not** counter-trend (CF-03 clause 6, P11).
    """
    if trend is Trend.NEUTRAL:
        return False, _ONE, False
    opposing = (direction is Direction.LONG and trend is Trend.DOWN) or (
        direction is Direction.SHORT and trend is Trend.UP
    )
    if not opposing or config.counter_trend_mode == "off":
        return False, _ONE, False
    return (
        True,
        dec(config.counter_trend_size_multiplier),
        bool(config.counter_trend_demote_to_scalp),
    )


# --------------------------------------------------------------------------- the stack


class _FirstVeto(Exception):
    """Internal: unwinds the gate stack at the first veto (§7.1)."""


@dataclass(slots=True)
class _State:
    vehicle: Vehicle
    trade_class: TradeClass
    conviction: Conviction
    size_multiplier: Decimal
    universe: UniverseVerdict | None = None
    counter_trend: bool = False
    required_structure_tf: Timeframe | None = None
    rejections: list[Rejection] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    chain: list[str] = field(default_factory=list)

    def note(self, text: str) -> None:
        self.notes.append(text)

    def extend_chain(self, ids: Sequence[str]) -> None:
        for sid in ids:
            if sid not in self.chain:
                self.chain.append(sid)


def qualify(
    setup: Setup,
    config: Config,
    *,
    confluence: ConfluenceCluster | None = None,
    regime: RegimeState | None = None,
    profile: SymbolProfile | None = None,
    universe: UniverseVerdict | None = None,
    series: Series | None = None,
    calendar: Sequence[CalendarEvent] = (),
    now: datetime | None = None,
    active_symbols: Sequence[str] = (),
    vehicle: Vehicle = Vehicle.LEVERAGE,
    structure_trend: Trend = Trend.NEUTRAL,
    min_conviction: Conviction | None = None,
    is_alt: bool = True,
    price_discovery: bool = False,
    anchor_level: Level | None = None,
    would_be_net_short: bool = False,
    expected_move_pct: Decimal | float | None = None,
    rr: Decimal | float | None = None,
    in_mid_range_band: bool = False,
    htf_opposes: bool = False,
    object_dead: bool = False,
    touch_limit_exceeded: bool = False,
    stop_rejection: str | None = None,
    insufficient_tps: bool = False,
    capacity_available: bool = True,
    module_disabled: bool = False,
    range_formed_since_event: bool | None = None,
    record_on_setup: bool = True,
    collect_all: bool = False,
) -> QualificationResult:
    """Run the §7.1 gate stack over one setup.

    Returns a :class:`QualificationResult` whose :attr:`~QualificationResult.rejection` names the
    gate that stopped it.  With ``collect_all=True`` every gate is evaluated for diagnostics; the
    default follows the spec and stops at the first veto (INTERFACES.md §9.6).

    ``record_on_setup`` appends the veto reasons to ``setup.vetoes`` and writes
    ``setup.conviction`` / ``setup.trade_class`` / ``setup.regime_flags`` — the SPEC.md §2.6
    contract ("gates append to vetoes").  Reasons are never duplicated, so a repeat call is
    idempotent.

    The verdicts ``in_mid_range_band``, ``htf_opposes``, ``object_dead``,
    ``touch_limit_exceeded``, ``stop_rejection``, ``insufficient_tps``, ``capacity_available`` and
    ``module_disabled`` are computed by the modules that own those config keys and are merely
    *ordered* here, so rejection attribution is complete without this module reaching into
    ``ranges.py``, ``structure.py``, ``planner.py`` or ``risk.py``.
    """
    moment = _as_utc(now) if now is not None else None
    state = _State(
        vehicle=vehicle,
        trade_class=setup.trade_class,
        conviction=confluence.conviction if confluence is not None else setup.conviction,
        size_multiplier=_ONE,
        universe=universe,
        chain=list(MODULE_SOURCE_IDS),
    )

    def veto(gate: str, reason: str, detail: str, source_ids: tuple[str, ...] = ()) -> None:
        state.rejections.append(Rejection(gate, reason, detail, source_ids))
        if not collect_all:
            raise _FirstVeto(reason)

    def open_() -> bool:
        """May the next gate run?  (Everything runs under ``collect_all``.)"""
        return collect_all or not state.rejections

    try:
        _gate_universe(setup, config, state, profile, series, veto)
        if open_():
            _gate_watchlist(setup, config, state, active_symbols, veto)
        if open_() and moment is not None:
            _gate_events(setup, config, state, calendar, moment, range_formed_since_event, veto)
        if open_() and moment is not None:
            _gate_weekend(config, state, moment, veto)
        if open_():
            _gate_confluence(setup, config, state, confluence, min_conviction, veto)
        if open_() and in_mid_range_band:
            veto(
                "G6",
                "mid_range_no_trade",
                "price inside the P7 no-trade band (CF-25, S4-R8, S5-R13)",
                ("CF-25",),
            )
        if open_():
            _gate_regime(setup, state, regime, is_alt, veto)
        if open_() and htf_opposes:
            veto(
                "G8",
                "htf_veto",
                f"the higher-timeframe candle opposes {setup.direction.value} "
                f"(S7-R20, S8 [00:38:57])",
                ("CF-24", "S7-R20"),
            )
        if open_() and setup.direction is Direction.SHORT:
            _gate_shorts(
                setup, config, state, price_discovery, anchor_level, would_be_net_short,
                structure_trend, veto,
            )
        if open_():
            _gate_liveness(state, object_dead, touch_limit_exceeded, veto)
        if open_() and stop_rejection is not None:
            veto(
                "G13" if stop_rejection == "stop_too_tight" else "G12",
                stop_rejection,
                "reported by the CF-14 / CF-06 stop layer",
                ("CF-06", "CF-14"),
            )
        if open_() and rr is not None:
            _gate_rr(config, state, rr, veto)
        if open_() and expected_move_pct is not None:
            _gate_expected_move(setup, config, state, expected_move_pct, veto)
        if open_() and insufficient_tps:
            veto("G16", "insufficient_tps", "fewer than tp_min_count structural TPs", ("CF-27",))
        if open_() and not capacity_available:
            veto("G17", "capacity", "§10 concurrency / loss / deployment cap full", ("CF-04",))
        if open_() and module_disabled:
            veto(
                "G18",
                "module_disabled",
                "primary detector belongs to a disabled module; its objects still score "
                "confluence for other setups (CF-37)",
                ("CF-37",),
            )
    except _FirstVeto:
        return _finish(setup, state, regime, record_on_setup)

    # CF-03 counter-trend: a modifier, never a gate — only applied to a surviving setup.
    if not state.rejections:
        is_ct, ct_multiplier, demote = counter_trend_adjustment(
            setup.direction, structure_trend, config
        )
        if is_ct:
            state.counter_trend = True
            state.size_multiplier *= ct_multiplier
            state.extend_chain(("CF-03", "S3-R25", "S7-R9"))
            state.note(
                f"counter-trend against a {structure_trend.value} structure: "
                f"size x{ct_multiplier} (CF-03)"
            )
            if demote:
                state.trade_class = TradeClass.SCALP
                state.note("counter_trend_demote_to_scalp: reclassified as a scalp (S7-R10)")
    return _finish(setup, state, regime, record_on_setup)


# --------------------------------------------------------------------------- gates


def _gate_universe(setup, config, state, profile, series, veto) -> None:  # type: ignore[no-untyped-def]
    """G1 — universe tier (CF-40, P18) plus the scalp BTC exclusion (S8-R32)."""
    if state.universe is None and profile is not None:
        state.universe = classify_universe(profile, config, series=series)
    if state.universe is None:
        state.note("no symbol profile supplied; G1 universe tier not evaluated")
    else:
        state.extend_chain(state.universe.source_ids)
        if state.universe.excluded:
            veto(
                "G1",
                "universe_tier_c",
                "; ".join(state.universe.reasons) or "tier C",
                ("CF-40",),
            )
        elif not state.universe.permits(state.vehicle):
            state.vehicle = Vehicle.SPOT
            state.note(
                f"universe tier {state.universe.tier}: vehicle forced to spot "
                f"({'; '.join(state.universe.reasons)})"
            )
    if config.scalp_excludes_btc and state.trade_class is TradeClass.SCALP and is_btc(setup.symbol):
        veto("G1", "scalp_excludes_btc", f"{setup.symbol} is BTC (S8-R32)", ("CF-40", "S8-R32"))


def _gate_watchlist(setup, config, state, active_symbols, veto) -> None:  # type: ignore[no-untyped-def]
    """G2 — 1–3 concurrent coins so you learn their levels (``universe_max_symbols``, S8-R33)."""
    held = {s.upper() for s in active_symbols}
    if setup.symbol.upper() in held:
        return
    if len(held) >= config.universe_max_symbols:
        veto(
            "G2",
            "watchlist_full",
            f"{len(held)} active symbols >= universe_max_symbols "
            f"{config.universe_max_symbols} (S8-R33)",
            ("CF-40", "S8-R33"),
        )


def _gate_events(setup, config, state, calendar, moment, range_formed_since_event, veto) -> None:  # type: ignore[no-untyped-def]
    """G3 — event blackout (CF-39).  Leverage-scoped by default; spot dip-buying survives."""
    if config.event_blackout_mode == "none":
        return
    hits = active_events(calendar, moment, config)
    if hits:
        names = ", ".join(f"{e.name}({e.kind})" for e in hits)
        state.extend_chain(("CF-39", "S8-R2"))
        if config.event_blackout_mode == "all" or state.vehicle is Vehicle.LEVERAGE:
            veto(
                "G3",
                "event_blackout",
                f"within {config.event_blackout_hours}h of {names}; "
                f"event_blackout_mode={config.event_blackout_mode}",
                ("CF-39", "S8-R2", "S2-R27"),
            )
            return
        state.required_structure_tf = setup.structure_tf.step(config.event_tf_step_up)
        state.note(
            f"event window ({names}): spot permitted, structure timeframe stepped up to "
            f"{state.required_structure_tf.value} (S5-R36, S8-R2)"
        )
        if setup.trade_tf.rank < Timeframe.parse(config.scalp_tf_ceiling).rank:
            veto(
                "G3",
                "event_tf_too_low",
                f"trade_tf {setup.trade_tf.value} below {config.scalp_tf_ceiling} inside an "
                f"event window (S5-R36: on event days trade only higher timeframes)",
                ("CF-39", "S5-R36"),
            )
        return
    # Outside every window: leverage re-arms only once a post-event range has formed (S2-R27).
    if (
        state.vehicle is Vehicle.LEVERAGE
        and config.event_resume_requires_range
        and range_formed_since_event is False
        and any(e.is_high_impact and _as_utc(e.finish) <= moment for e in calendar)
    ):
        veto(
            "G3",
            "event_blackout",
            "post-event: leverage re-arms only once a range has formed "
            "(event_resume_requires_range, S2-R27)",
            ("CF-39", "S2-R27"),
        )


def _gate_weekend(config, state, moment, veto) -> None:  # type: ignore[no-untyped-def]
    """G4 — weekend gate (CF-39, S5-R37, TBOT1-R24).  Leverage-scoped by default."""
    if config.weekend_mode == "normal" or not P.is_weekend(moment, config):
        return
    if config.weekend_mode == "block_all" or state.vehicle is Vehicle.LEVERAGE:
        veto(
            "G4",
            "weekend_blocked",
            f"weekend window, weekend_mode={config.weekend_mode} (CF-39, S5-R37, TBOT1-R24)",
            ("CF-39", "S5-R37", "TBOT1-R24"),
        )
    else:
        state.note("weekend: spot permitted, leverage blocked (CF-39)")


def _gate_confluence(setup, config, state, confluence, min_conviction, veto) -> None:  # type: ignore[no-untyped-def]
    """G5 — score, class count (CF-31, P14) and the caller's optional conviction floor."""
    score = confluence.score if confluence is not None else setup.confluence_score
    classes = (
        confluence.classes if confluence is not None else frozenset(setup.confluence_classes)
    )
    if confluence is not None:
        state.extend_chain(confluence.source_ids)
    # Q5 (derived, S5 `[01:05:33]`, S8 `[00:53:41]`): the gate counts raw deduplicated objects.
    # The §6.1 weight map stays live for ranking and for the §6.3 high-conviction threshold, but
    # it is no longer what decides whether a setup is eligible.
    if config.confluence_gate_mode == "raw_count":
        count = getattr(confluence, "count", None)
        if not count:
            count = len(classes)
        if count < config.min_confluence_count:
            veto(
                "G5",
                "insufficient_confluence",
                f"{count} confluence object(s) < min_confluence_count "
                f"{config.min_confluence_count} (Q5, confluence_gate_mode=raw_count)",
                ("CF-31",),
            )
            return
    elif score < dec(config.min_confluence_count):
        veto(
            "G5",
            "insufficient_confluence",
            f"score {score} < min_confluence_count {config.min_confluence_count}",
            ("CF-31",),
        )
        return
    if config.single_class_trade_forbidden and len(classes) < 2:
        veto(
            "G5",
            "single_class",
            f"only {len(classes)} confluence class(es): {sorted(classes)}; "
            f"single_class_trade_forbidden (S6-R29, S6-R30, S4-R38, S7-R30, S7-R39)",
            ("CF-31",),
        )
        return
    if min_conviction is not None and (
        _CONVICTION_RANK[state.conviction] < _CONVICTION_RANK[min_conviction]
    ):
        veto(
            "G5",
            "conviction_below_floor",
            f"conviction {state.conviction.value} < caller floor {min_conviction.value} "
            f"(§6.3 mapping; the floor is an injected argument, not a config key)",
            ("CF-31",),
        )


def _gate_regime(setup, state, regime, is_alt, veto) -> None:  # type: ignore[no-untyped-def]
    """G7 — the §7.2 context layer: hard veto, blocked alt longs, or a size multiplier."""
    if regime is None:
        state.note("no regime state supplied; G7 not evaluated (treated as neutral)")
        return
    state.extend_chain(regime.source_ids)
    if regime.degraded:
        state.note(
            "regime degraded to neutral for missing context: " + ", ".join(regime.missing)
        )
    if regime.hard_veto:
        veto(
            "G7",
            "regime_veto",
            "; ".join(regime.veto_reasons) or "context hard veto",
            ("CF-35", "TBOT1-R20"),
        )
        return
    if regime.blocks_new_alt_longs and is_alt and setup.direction is Direction.LONG:
        veto(
            "G7",
            "regime_veto",
            "risk-off on alts blocks new alt longs (S3-R32, TBOT1-R19)",
            ("CF-35", "S3-R32", "TBOT1-R19"),
        )
        return
    state.size_multiplier *= regime.multiplier_for(state.vehicle)
    if regime.size_multiplier != _ONE and state.vehicle is Vehicle.LEVERAGE:
        state.note(f"regime size multiplier {regime.size_multiplier} applied to leverage")
    if regime.adverse and state.conviction is not Conviction.LOW:
        state.conviction = Conviction.LOW
        state.note("adverse but non-vetoing regime flag: conviction demoted to low (§6.3)")


def _gate_shorts(  # type: ignore[no-untyped-def]
    setup, config, state, price_discovery, anchor_level, would_be_net_short, structure_trend, veto
) -> None:
    """G9/G10 — the four hard shorting gates (CF-41)."""
    state.extend_chain(("CF-41",))
    if not config.shorts_enabled:
        veto("G9", "shorts_disabled", "shorts_enabled is false", ("CF-41",))
        return
    if price_discovery and not config.short_in_price_discovery:
        veto(
            "G10",
            "short_in_price_discovery",
            "never short in price discovery (S3-R28, S6-R37)",
            ("CF-41", "S3-R28", "S6-R37"),
        )
        return
    if anchor_level is not None and _is_unbroken_support(anchor_level):
        veto(
            "G9",
            "short_policy",
            f"anchor level {anchor_level.id} is unbroken support; only a broken-and-flipped "
            f"level may be shorted (S4-R9)",
            ("CF-41", "S4-R9"),
        )
        return
    if (
        would_be_net_short
        and not config.net_short_allowed_in_uptrend
        and structure_trend is Trend.UP
    ):
        veto(
            "G9",
            "short_policy",
            "would be net short while the structure timeframe is in an uptrend "
            "(net_short_allowed_in_uptrend=false, S4-R36, TBOT1-R12)",
            ("CF-41", "S4-R36"),
        )


def _gate_liveness(state, object_dead, touch_limit_exceeded, veto) -> None:  # type: ignore[no-untyped-def]
    """G11 — the anchoring object is alive (CF-08) and under its touch limit (CF-07)."""
    if object_dead:
        veto("G11", "object_dead", "the anchoring zone/OB is dead and unrescued (CF-08)", ("CF-08",))
        return
    if touch_limit_exceeded:
        veto("G11", "touch_limit", "the level is over its CF-07 touch limit", ("CF-07",))


def _gate_rr(config, state, rr_value, veto) -> None:  # type: ignore[no-untyped-def]
    """G14 — ``min_rr`` (2.0) from ``rr_measured_from`` to ``rr_measured_to`` (CF-42).

    The caller measures the ratio; :func:`tbot.plan.rr_for_gate` is what picks the target that
    ``rr_measured_to`` names.  Since **F9** that is the **final** TP by default, which is where
    his own position tool's R:R readout measures to.
    """
    rr = dec(rr_value)
    if rr < dec(config.min_rr):
        veto(
            "G14",
            "rr_below_min",
            f"R:R {rr} from {config.rr_measured_from} to {config.rr_measured_to} < min_rr "
            f"{config.min_rr} (S3-R26 rejects 1:1; floor corroborated by F9, lowest observed 2.13)",
            ("CF-42", "F9"),
        )


def _gate_expected_move(setup, config, state, expected_move_pct, veto) -> None:  # type: ignore[no-untyped-def]
    """G15 — ``min_expected_move_pct`` for the class (scalp 2.0 / swing 5.0, CF-41, S3-R15).

    This is also where "volatile enough to be worth trading" is enforced: the corpus rejects a
    1–2 % expected move rather than naming a volatility statistic, and §11 has no volatility key.
    """
    key = _move_key(state.trade_class, setup.trade_tf, config)
    floor = dec(config.min_expected_move_pct[key])
    move = dec(expected_move_pct)
    if move < floor:
        veto(
            "G15",
            "move_too_small",
            f"expected move {move}% < min_expected_move_pct[{key}] {floor}% (S3-R15, S6-R8)",
            ("CF-41", "S3-R15"),
        )


# --------------------------------------------------------------------------- finish


def _finish(
    setup: Setup,
    state: _State,
    regime: RegimeState | None,
    record_on_setup: bool,
) -> QualificationResult:
    result = QualificationResult(
        qualified=not state.rejections,
        rejections=tuple(state.rejections),
        vehicle=state.vehicle,
        trade_class=state.trade_class,
        conviction=state.conviction,
        size_multiplier=state.size_multiplier,
        universe=state.universe,
        counter_trend=state.counter_trend,
        required_structure_tf=state.required_structure_tf,
        notes=tuple(state.notes),
        source_ids=tuple(state.chain),
        flags={
            "gate": state.rejections[0].gate if state.rejections else None,
            "reason": state.rejections[0].reason if state.rejections else None,
            "vehicle": state.vehicle.value,
            "trade_class": state.trade_class.value,
            "counter_trend": state.counter_trend,
        },
    )
    if record_on_setup:
        for rejection in result.rejections:
            if rejection.reason not in setup.vetoes:
                setup.vetoes.append(rejection.reason)
        setup.conviction = state.conviction
        setup.trade_class = state.trade_class
        if regime is not None:
            setup.regime_flags = dict(regime.flags)
    return result
