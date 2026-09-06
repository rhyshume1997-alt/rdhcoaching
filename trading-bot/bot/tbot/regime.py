"""SPEC.md §7.2 — the context / regime layer (CF-35, S3, TBOT1 §10).

Context charts are a **gate, never a signal source** (PL-6).  Everything in this module may only
(a) hard-veto a trade, (b) reduce size, or (c) permit normal size.  Nothing here ever produces an
entry, a stop or a target, and nothing here is ever handed to :mod:`tbot.confluence` as a scoring
object — cross-market context is weight 0 by construction (TBOT1 §10, CF-35).

Three things this module gets right that are easy to get wrong:

* **The dominance charts read inverted, and the inversion is scoped to those tickers.**
  ``USDT.D`` and ``BTC.D`` are traded inverse — at resistance ⇒ risk-**on** for alts, at support
  ⇒ risk-**off** (S3-R8, S3-R9, S3-R32, S3-C4).  :func:`is_dominance_symbol` is the whole of that
  scope; a price chart (``SOLUSDT``, ``BTCUSDT``, ``DXY``) always reads normally.
* **BVOL is the only mechanical signal here.**  A daily candle touching ``bvol_zone``
  (0.81–1.40) raises a volatility-event flag for ``bvol_event_window_hours`` (72) that halves
  leverage size.  It predicts a **large move**, and the corpus is explicit that the **direction
  is unpredictable** (S3-R1, S3-R3) — :attr:`BvolEvent.direction` therefore does not exist.  The
  static zone-touch test is the *only* permitted BVOL operation: no trend, no structure, no
  direction (S3-R2, S3-C1); box relocation is manual and is not automated (S3-A4).
* **Absent context degrades to neutral, out loud.**  A missing symbol never silently reads as
  risk-on: it lands in :attr:`RegimeState.missing`, sets :attr:`RegimeState.degraded` and says so
  in :attr:`RegimeState.notes`.

Priority is ``context_priority`` — ``["USDT.D", "BTC.D", "BVOL"]``, with DXY omitted because its
stated relationship has been broken for months (S3-R10, S3-C8, CF-35).  S3-R11's full order
(USDT.D > DXY > BTC.D > BVOL) is restored when ``dxy_gate_enabled`` is turned on, and DXY is then
still gated on the ``dxy_gate_min_rolling_corr`` check, which is **OUR construct**.

News is **not implemented** (TBOT1-A23): only the scheduled-event calendar is machine-readable,
and it lives in :mod:`tbot.qualify` (gate G3).

Config keys read here (``qualification.py`` block of INTERFACES.md §7, split across this module
and :mod:`tbot.qualify`): ``context_priority``, ``bvol_zone``, ``bvol_event_window_hours``,
``bvol_size_multiplier``, ``dxy_gate_enabled``, ``dxy_gate_min_rolling_corr``,
``all_pairs_at_resistance_veto``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from tbot.config import Config
from tbot.models import (
    Direction,
    Level,
    LevelKind,
    Series,
    Trend,
    Vehicle,
    dec,
)
import tbot.primitives as P

__all__ = [
    "MODULE_SOURCE_IDS",
    "DOMINANCE_SYMBOLS",
    "DXY_SYMBOL",
    "BVOL_SYMBOL",
    "normalise_symbol",
    "is_dominance_symbol",
    "LevelRead",
    "ContextRead",
    "BvolEvent",
    "AllPairsRefs",
    "RegimeState",
    "context_stack",
    "levels_from_series",
    "read_context_chart",
    "bvol_event",
    "rolling_correlation",
    "evaluate_regime",
]

MODULE_SOURCE_IDS: tuple[str, ...] = (
    "CF-35",
    "S3-R1",
    "S3-R2",
    "S3-R3",
    "S3-R5",
    "S3-R7",
    "S3-R8",
    "S3-R9",
    "S3-R11",
    "S3-R32",
    "TBOT1-R19",
    "TBOT1-R20",
)

#: The **only** two tickers whose TA is read inverted (S3-R8, S3-R9, S3-C4).
DOMINANCE_SYMBOLS: frozenset[str] = frozenset({"USDT.D", "BTC.D"})
DXY_SYMBOL = "DXY"
BVOL_SYMBOL = "BVOL"

_ONE = Decimal(1)
_ZERO = Decimal(0)

RegimeLabel = Literal["risk_on", "risk_off", "neutral"]


def normalise_symbol(symbol: str) -> str:
    """Canonical ticker: exchange prefix dropped, upper-cased (``"CRYPTOCAP:usdt.d"`` → ``USDT.D``)."""
    return symbol.split(":")[-1].strip().upper()


def is_dominance_symbol(symbol: str) -> bool:
    """Is the inverted read in scope for this ticker?  True for ``USDT.D`` / ``BTC.D`` only.

    Scope is the point of this function.  ``BTCUSDT``, ``SOLUSDT``, ``DXY`` and ``BVOL`` all read
    normally; applying the dominance inversion to a price chart would invert every long the bot
    ever takes (S3-C4: "strictly scoped to those two charts, never to price charts").
    """
    return normalise_symbol(symbol) in DOMINANCE_SYMBOLS


# --------------------------------------------------------------------------- level reads


@dataclass(frozen=True, slots=True)
class LevelRead:
    """One horizontal on a context chart, reduced to price + role."""

    price: Decimal
    role: Literal["support", "resistance"]
    touches: int = 0
    level_id: str | None = None


def levels_from_series(
    series: Series, config: Config, *, at_index: int | None = None
) -> list[LevelRead]:
    """Derive the context chart's horizontals from the foundation (P1 + P3).

    Context charts have no detector of their own — a dominance chart is not a tradeable symbol —
    so levels come straight from ``swing_points`` and ``cluster_levels``.  Role is taken from the
    cluster's membership: more high pivots than low ⇒ resistance, else support.  Callers that
    already own :class:`~tbot.models.Level` objects for these tickers should inject them instead.
    """
    if len(series) == 0:
        return []
    idx = len(series) - 1 if at_index is None else at_index
    pivots = P.swing_points(series, config)
    clusters = P.cluster_levels(series, config, pivots, now_index=idx)
    reads: list[LevelRead] = []
    for cluster in clusters:
        role: Literal["support", "resistance"] = (
            "resistance" if cluster.high_members >= cluster.low_members else "support"
        )
        reads.append(LevelRead(price=cluster.price, role=role, touches=cluster.touch_seed))
    return reads


def _as_level_reads(levels: Sequence[Any]) -> list[LevelRead]:
    """Accept :class:`LevelRead`\\ s or :class:`~tbot.models.Level`\\ s interchangeably."""
    out: list[LevelRead] = []
    for lvl in levels:
        if isinstance(lvl, LevelRead):
            out.append(lvl)
            continue
        if isinstance(lvl, Level):
            if lvl.kind is LevelKind.MID_RANGE:
                continue
            role: Literal["support", "resistance"] = (
                "resistance"
                if lvl.kind
                in (
                    LevelKind.RESISTANCE,
                    LevelKind.RANGE_HIGH,
                    LevelKind.SR_CONFIRMED_RESISTANCE,
                )
                else "support"
            )
            out.append(
                LevelRead(
                    price=lvl.price, role=role, touches=lvl.touch_count, level_id=lvl.id
                )
            )
            continue
        raise TypeError(f"expected LevelRead or Level, got {type(lvl).__name__}")
    return out


# --------------------------------------------------------------------------- chart reads


@dataclass(frozen=True, slots=True)
class ContextRead:
    """One context chart's verdict.  ``risk_on`` is ``None`` when the chart says nothing."""

    symbol: str
    available: bool
    inverted: bool                       #: dominance inversion applied to *this* chart
    at_resistance: bool
    at_support: bool
    risk_on: bool | None                 #: None = no read; never assume risk-on
    trend: Trend
    price: Decimal | None
    level_price: Decimal | None
    level_id: str | None
    notes: tuple[str, ...]
    source_ids: tuple[str, ...]

    @property
    def adverse(self) -> bool:
        """A definite risk-off read from this chart."""
        return self.risk_on is False


def read_context_chart(
    symbol: str,
    series: Series | None,
    config: Config,
    *,
    levels: Sequence[Any] | None = None,
    at_index: int | None = None,
) -> ContextRead:
    """Read one context chart: is price at support or at resistance, and what does that mean?

    The **inversion is applied here and only here**, and only when
    :func:`is_dominance_symbol` says so:

    ================  ==========================  ==========================
    chart             at resistance               at support
    ================  ==========================  ==========================
    ``USDT.D``        risk-**on** for alts        risk-**off** / take profit
    ``BTC.D``         buy alts (risk-on)          trim alts (risk-off)
    anything else     risk-off for that symbol    risk-on for that symbol
    ================  ==========================  ==========================

    "At" a level means inside the P9 tolerance band of the last close.  An absent or empty series
    degrades to ``available=False`` / ``risk_on=None``, never to a risk-on default.
    """
    canonical = normalise_symbol(symbol)
    inverted = is_dominance_symbol(canonical)
    src: tuple[str, ...] = ("S3-R8", "S3-R9", "S3-R32", "CF-35") if inverted else ("CF-35",)
    if series is None or len(series) == 0:
        return ContextRead(
            symbol=canonical,
            available=False,
            inverted=inverted,
            at_resistance=False,
            at_support=False,
            risk_on=None,
            trend=Trend.NEUTRAL,
            price=None,
            level_price=None,
            level_id=None,
            notes=(f"{canonical}: no series supplied; degraded to neutral",),
            source_ids=src,
        )

    idx = len(series) - 1 if at_index is None else at_index
    close = series.price_at(idx, "close")
    reads = (
        _as_level_reads(levels)
        if levels is not None
        else levels_from_series(series, config, at_index=idx)
    )

    hit_resistance: LevelRead | None = None
    hit_support: LevelRead | None = None
    for lvl in reads:
        if not P.price_at_level(series, config, close, lvl.price, idx):
            continue
        if lvl.role == "resistance":
            if hit_resistance is None or abs(lvl.price - close) < abs(
                hit_resistance.price - close
            ):
                hit_resistance = lvl
        elif hit_support is None or abs(lvl.price - close) < abs(hit_support.price - close):
            hit_support = lvl

    notes: list[str] = []
    if not reads:
        notes.append(f"{canonical}: no levels available; no read")

    at_resistance = hit_resistance is not None
    at_support = hit_support is not None
    if at_resistance and at_support:
        # Both bands cover the close: take the nearer level, ties to resistance (the
        # conservative half of every read in S3).  [OUR CHOICE]
        if abs(hit_support.price - close) < abs(hit_resistance.price - close):
            at_resistance = False
        else:
            at_support = False
        notes.append(f"{canonical}: support and resistance both in band; took the nearer")

    hit = hit_resistance if at_resistance else (hit_support if at_support else None)

    risk_on: bool | None
    if at_resistance:
        risk_on = True if inverted else False
    elif at_support:
        risk_on = False if inverted else True
    else:
        risk_on = None

    pivots = P.swing_points(series, config)
    trend = P.classify_trend(pivots, config, at_index=idx)

    return ContextRead(
        symbol=canonical,
        available=True,
        inverted=inverted,
        at_resistance=at_resistance,
        at_support=at_support,
        risk_on=risk_on,
        trend=trend,
        price=close,
        level_price=hit.price if hit is not None else None,
        level_id=hit.level_id if hit is not None else None,
        notes=tuple(notes),
        source_ids=src,
    )


# --------------------------------------------------------------------------- BVOL


@dataclass(frozen=True, slots=True)
class BvolEvent:
    """The volatility-event flag (S3-R1, S3-R3, S3-R5, S3-R7, CF-35).

    There is **no direction field and there never will be**: a BVOL zone touch predicts a large
    move inside ``bvol_event_window_hours`` and the corpus states plainly that the move can go
    either way (S3-R3).  The flag halves *leverage* size (``bvol_size_multiplier``); spot is
    unaffected.
    """

    active: bool
    triggered_index: int | None
    triggered_at: datetime | None
    expires_at: datetime | None
    hours_remaining: Decimal
    zone_low: Decimal
    zone_high: Decimal
    window_hours: int
    notes: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ("S3-R1", "S3-R3", "S3-R5", "S3-R7", "CF-35")


def bvol_event(
    series: Series | None,
    config: Config,
    *,
    now: datetime | None = None,
    at_index: int | None = None,
) -> BvolEvent:
    """The static ``bvol_zone`` touch test — the only permitted BVOL operation (S3-R2, S3-C1).

    A bar "enters the zone" when its ``[low, high]`` intersects ``bvol_zone`` (0.81–1.40).  The
    most recent such bar starts a window of ``bvol_event_window_hours`` (72) hours; ``now``
    defaults to the last bar's timestamp, never to the wall clock (determinism, INTERFACES.md
    §9.9).

    No trend, structure or direction analysis is performed on this series, and the zone is never
    relocated automatically (S3-A4 — box relocation is a manual act).
    """
    low, high = (dec(config.bvol_zone[0]), dec(config.bvol_zone[1]))
    window = int(config.bvol_event_window_hours)
    empty = BvolEvent(
        active=False,
        triggered_index=None,
        triggered_at=None,
        expires_at=None,
        hours_remaining=_ZERO,
        zone_low=low,
        zone_high=high,
        window_hours=window,
    )
    if series is None or len(series) == 0:
        return BvolEvent(**{**_asdict(empty), "notes": ("BVOL: no series supplied",)})

    idx = len(series) - 1 if at_index is None else at_index
    notes: list[str] = []
    if series.tf.value != "1D":
        notes.append(f"BVOL: daily-only chart read on {series.tf.value} (S3-R2)")

    triggered: int | None = None
    for i in range(idx + 1):
        bar_low = series.price_at(i, "low")
        bar_high = series.price_at(i, "high")
        if bar_low <= high and bar_high >= low:
            triggered = i
    if triggered is None:
        return BvolEvent(**{**_asdict(empty), "notes": tuple(notes)})

    triggered_at = series.timestamp(triggered)
    expires_at = triggered_at + timedelta(hours=window)
    reference = now if now is not None else series.timestamp(idx)
    remaining_hours = (expires_at - reference).total_seconds() / 3600.0
    active = remaining_hours > 0
    return BvolEvent(
        active=active,
        triggered_index=triggered,
        triggered_at=triggered_at,
        expires_at=expires_at,
        hours_remaining=dec(max(remaining_hours, 0.0)),
        zone_low=low,
        zone_high=high,
        window_hours=window,
        notes=tuple(notes),
    )


def _asdict(event: BvolEvent) -> dict[str, Any]:
    return {
        "active": event.active,
        "triggered_index": event.triggered_index,
        "triggered_at": event.triggered_at,
        "expires_at": event.expires_at,
        "hours_remaining": event.hours_remaining,
        "zone_low": event.zone_low,
        "zone_high": event.zone_high,
        "window_hours": event.window_hours,
        "notes": event.notes,
    }


# --------------------------------------------------------------------------- DXY


def rolling_correlation(a: Series, b: Series, *, lookback_bars: int = 90) -> Decimal | None:
    """Pearson correlation of the two series' closes over the overlapping tail.

    **OUR construct** (CF-35): the corpus never proposes a correlation test, it just says the DXY
    relationship broke.  ``None`` when there is not enough overlap or either leg is flat.
    """
    n = min(len(a), len(b), lookback_bars)
    if n < 3:
        return None
    x = a.close[-n:]
    y = b.close[-n:]
    if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return dec(float(np.corrcoef(x, y)[0, 1]))


def context_stack(config: Config) -> tuple[str, ...]:
    """The fixed priority stack, canonicalised.

    ``context_priority`` ships as ``["USDT.D", "BTC.D", "BVOL"]``; DXY is omitted because it is
    disabled (CF-35).  With ``dxy_gate_enabled`` on, S3-R11's full order is restored by inserting
    ``DXY`` at rank 2 — USDT.D > DXY > BTC.D > BVOL.
    """
    stack = [normalise_symbol(s) for s in config.context_priority]
    if config.dxy_gate_enabled and DXY_SYMBOL not in stack:
        stack.insert(1 if stack else 0, DXY_SYMBOL)
    elif not config.dxy_gate_enabled and DXY_SYMBOL in stack:
        stack.remove(DXY_SYMBOL)
    return tuple(stack)


# --------------------------------------------------------------------------- aggregate


@dataclass(frozen=True, slots=True)
class AllPairsRefs:
    """Context keys for the TBOT1-R20 all-pairs veto: the coin's USDT pair, its BTC pair, BTC."""

    usdt_pair: str
    btc_pair: str
    btc: str = "BTCUSDT"


@dataclass(frozen=True, slots=True)
class RegimeState:
    """The §7.2 verdict: a gate, a size multiplier, and the reasons for both."""

    state: RegimeLabel
    risk_on: bool
    hard_veto: bool
    blocks_new_alt_longs: bool
    size_multiplier: Decimal              #: applies to **leverage** (BVOL is spot-neutral)
    spot_size_multiplier: Decimal
    veto_reasons: tuple[str, ...]
    reads: tuple[ContextRead, ...]        #: in ``context_stack`` order
    bvol: BvolEvent
    missing: tuple[str, ...]
    degraded: bool                        #: at least one context chart was absent
    adverse: bool                         #: adverse but non-vetoing → §6.3 low conviction
    notes: tuple[str, ...]
    flags: dict[str, Any] = field(default_factory=dict)   #: for ``Setup.regime_flags``
    source_ids: tuple[str, ...] = MODULE_SOURCE_IDS

    def multiplier_for(self, vehicle: Vehicle) -> Decimal:
        """Size multiplier for a vehicle.  Spot is unaffected by the BVOL window (CF-35)."""
        return self.spot_size_multiplier if vehicle is Vehicle.SPOT else self.size_multiplier

    def read(self, symbol: str) -> ContextRead | None:
        canonical = normalise_symbol(symbol)
        for r in self.reads:
            if r.symbol == canonical:
                return r
        return None


def evaluate_regime(
    context: Mapping[str, Series],
    config: Config,
    *,
    direction: Direction | None = None,
    is_alt: bool = True,
    levels: Mapping[str, Sequence[Any]] | None = None,
    all_pairs: AllPairsRefs | None = None,
    beta_parent: str | None = None,
    now: datetime | None = None,
) -> RegimeState:
    """Walk the priority stack and produce the risk state, the size multiplier and any veto.

    ``context`` maps ticker → :class:`~tbot.models.Series`; **absent tickers degrade to neutral**
    and are named in :attr:`RegimeState.missing` / :attr:`RegimeState.notes`.  With no context at
    all the result is ``state="neutral"``, ``size_multiplier=1``, ``hard_veto=False`` — the layer
    never invents a risk-on regime it cannot see.

    Rules applied, in order:

    1. **Priority stack** (``context_stack``): the first chart with a definite read sets the risk
       state.  Later charts still contribute their vetoes and multipliers, but never overrule the
       higher-priority read (S3-R11, S3-R12).
    2. **TBOT1-R19**: while ``BTC.D`` *and* ``USDT.D`` are both trending up, stay risk-off on
       alts — new alt longs are blocked until USDT.D rejects its next level.
    3. **TBOT1-R20** (``all_pairs_at_resistance_veto``): the coin's USDT pair, its BTC pair and
       BTC itself all at resistance simultaneously ⇒ **hard veto** on longs.
    4. **Beta parent** (S6-R42, TBOT1-R21): no plan while the parent is adverse.  The parent map
       is injected — the corpus names pairs but §11 has no key for them.
    5. **BVOL**: an active event window multiplies leverage size by ``bvol_size_multiplier``.
    6. **DXY**: read only when ``dxy_gate_enabled`` *and* the rolling-correlation check passes;
       otherwise noted and ignored (S3-C8).
    """
    stack = context_stack(config)
    normalised: dict[str, Series] = {normalise_symbol(k): v for k, v in context.items()}
    level_map: dict[str, Sequence[Any]] = (
        {normalise_symbol(k): v for k, v in levels.items()} if levels else {}
    )

    reads: list[ContextRead] = []
    missing: list[str] = []
    notes: list[str] = []
    veto_reasons: list[str] = []

    if DXY_SYMBOL in normalised and DXY_SYMBOL not in stack:
        notes.append(
            "DXY supplied but dxy_gate_enabled is false; ignored — the stated relationship has "
            "been broken for months (S3-R10, S3-C8, CF-35)"
        )

    for symbol in stack:
        if symbol == BVOL_SYMBOL:
            continue
        series = normalised.get(symbol)
        if series is None:
            missing.append(symbol)
            notes.append(f"{symbol} absent from context; that chart degrades to neutral")
            reads.append(read_context_chart(symbol, None, config))
            continue
        reads.append(
            read_context_chart(symbol, series, config, levels=level_map.get(symbol))
        )

    # DXY correlation gate — OUR construct (CF-35).
    dxy_read = next((r for r in reads if r.symbol == DXY_SYMBOL), None)
    if dxy_read is not None and dxy_read.available:
        subject = next(
            (
                s
                for k, s in normalised.items()
                if k not in DOMINANCE_SYMBOLS and k not in (DXY_SYMBOL, BVOL_SYMBOL)
            ),
            None,
        )
        corr = (
            rolling_correlation(normalised[DXY_SYMBOL], subject)
            if subject is not None
            else None
        )
        if corr is None or abs(corr) < dec(config.dxy_gate_min_rolling_corr):
            notes.append(
                f"DXY rolling correlation {corr if corr is not None else 'unavailable'} "
                f"< dxy_gate_min_rolling_corr {config.dxy_gate_min_rolling_corr}; DXY ignored"
            )
            reads = [r for r in reads if r.symbol != DXY_SYMBOL]

    bvol = bvol_event(normalised.get(BVOL_SYMBOL), config, now=now)
    if BVOL_SYMBOL in stack and BVOL_SYMBOL not in normalised:
        missing.append(BVOL_SYMBOL)
        notes.append("BVOL absent from context; volatility-event flag degrades to off")

    # 1 — priority stack.
    state: RegimeLabel = "neutral"
    risk_on = False
    decided_by: str | None = None
    for read in reads:
        if read.risk_on is None:
            continue
        state = "risk_on" if read.risk_on else "risk_off"
        risk_on = bool(read.risk_on)
        decided_by = read.symbol
        break
    if decided_by is not None:
        notes.append(f"risk state set by {decided_by} (priority stack {list(stack)})")
    else:
        notes.append("no context chart gave a definite read; neutral")

    blocks_new_alt_longs = state == "risk_off" and is_alt

    # 2 — TBOT1-R19 dominance-trend override.
    usdt = next((r for r in reads if r.symbol == "USDT.D"), None)
    btcd = next((r for r in reads if r.symbol == "BTC.D"), None)
    if (
        usdt is not None
        and btcd is not None
        and usdt.available
        and btcd.available
        and usdt.trend is Trend.UP
        and btcd.trend is Trend.UP
    ):
        state = "risk_off"
        risk_on = False
        if is_alt:
            blocks_new_alt_longs = True
        notes.append("BTC.D and USDT.D both trending up; risk-off on alts (TBOT1-R19)")

    # 3 — TBOT1-R20 all-pairs veto.
    hard_veto = False
    if all_pairs is not None and config.all_pairs_at_resistance_veto:
        pair_reads = []
        for key in (all_pairs.usdt_pair, all_pairs.btc_pair, all_pairs.btc):
            canonical = normalise_symbol(key)
            series = normalised.get(canonical)
            pair_reads.append(
                read_context_chart(
                    canonical, series, config, levels=level_map.get(canonical)
                )
            )
        if all(r.available and r.at_resistance for r in pair_reads):
            if direction is None or direction is Direction.LONG:
                hard_veto = True
                veto_reasons.append("all_pairs_at_resistance")
                notes.append(
                    "USDT pair, BTC pair and BTC all at resistance; longs vetoed (TBOT1-R20)"
                )
        else:
            unavailable = [r.symbol for r in pair_reads if not r.available]
            if unavailable:
                notes.append(
                    f"all-pairs veto not evaluable: {unavailable} absent from context"
                )

    # 4 — beta parent (S6-R42, TBOT1-R21).  Parent map is injected: §11 has no key for it.
    if beta_parent is not None:
        parent = read_context_chart(
            beta_parent,
            normalised.get(normalise_symbol(beta_parent)),
            config,
            levels=level_map.get(normalise_symbol(beta_parent)),
        )
        reads.append(parent)
        if not parent.available:
            missing.append(parent.symbol)
            notes.append(f"beta parent {parent.symbol} absent; gate degrades to neutral")
        elif parent.risk_on is False and (direction is None or direction is Direction.LONG):
            hard_veto = True
            veto_reasons.append("beta_parent_adverse")
            notes.append(
                f"beta parent {parent.symbol} adverse; no plan while the parent is adverse "
                f"(S6-R42, TBOT1-R21)"
            )

    # 5 — BVOL size multiplier (leverage only).
    size_multiplier = _ONE
    if bvol.active:
        size_multiplier = dec(config.bvol_size_multiplier)
        notes.append(
            f"BVOL event active until {bvol.expires_at}; leverage size x"
            f"{config.bvol_size_multiplier} — direction is unpredictable (S3-R3)"
        )

    adverse = (not hard_veto) and (state == "risk_off" or bvol.active)

    flags: dict[str, Any] = {
        "state": state,
        "risk_on": risk_on,
        "blocks_new_alt_longs": blocks_new_alt_longs,
        "bvol_event": bvol.active,
        "hard_veto": hard_veto,
        "degraded": bool(missing),
        "decided_by": decided_by,
    }

    return RegimeState(
        state=state,
        risk_on=risk_on,
        hard_veto=hard_veto,
        blocks_new_alt_longs=blocks_new_alt_longs,
        size_multiplier=size_multiplier,
        spot_size_multiplier=_ONE,
        veto_reasons=tuple(veto_reasons),
        reads=tuple(reads),
        bvol=bvol,
        missing=tuple(dict.fromkeys(missing)),
        degraded=bool(missing),
        adverse=adverse,
        notes=tuple(notes),
        flags=flags,
    )
