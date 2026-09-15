"""SPEC.md §5.1 support/resistance levels + §5.2 the CF-15 SR flip state machine.

Everything here is built on the primitives (SPEC.md §4): swing detection is P1, level
construction is P3, touch counting is P4 and the tolerance band is P9.  Nothing in this module
re-derives them.

Two public surfaces:

``run_flip_machine``
    the §5.2 state machine on its own — ``support -> sr_pending -> sr_confirmed_resistance``
    and the mirror, with the S2-R4 **deviation** rollback and the ``pending_sr_expiry_bars``
    timeout.  ``ranges.py`` reuses it for the CF-26 range-death test.

``SupportResistanceDetector``
    the stage-3 :class:`~tbot.INTERFACES.Detector`: P3 clusters -> :class:`~tbot.models.Level`
    objects carrying touch counts, the flip state and the S2-R6 quality score.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal, Sequence

from tbot.config import Config
from tbot.models import (
    ConfluenceClass,
    FlipState,
    Level,
    LevelKind,
    Series,
    SwingPoint,
    Timeframe,
    dec,
)
import tbot.primitives as P
from tbot.detectors.base import object_id

__all__ = [
    "FlipTransition",
    "FlipResult",
    "SupportResistanceDetector",
    "extra_confirmation_candles",
    "flip_kind",
    "is_playable",
    "live_levels",
    "role_of_kind",
    "run_flip_machine",
    "touch_decay_multiplier",
    "touch_limit",
]

Side = Literal["support", "resistance"]

_HUNDRED = Decimal(100)

#: The rule IDs the §5.2 machine implements, attached to every level it touches.
FLIP_SOURCE_IDS: tuple[str, ...] = ("CF-15", "S5-R3", "S2-R1", "S2-R2", "S2-R3", "S2-R4", "S8-R41")


# =========================================================================== §5.2 flip machine


@dataclass(frozen=True, slots=True)
class FlipTransition:
    """One edge of the §5.2 table, with the bar it fired on."""

    bar_index: int
    from_state: FlipState
    to_state: FlipState
    event: Literal["break", "retest_confirm", "deviation", "expiry"]
    role: Side                       #: the level's role *after* the transition


@dataclass(frozen=True, slots=True)
class FlipResult:
    """Result of :func:`run_flip_machine` — the level's §5.2 state as of ``end_index``."""

    state: FlipState
    kind: LevelKind
    role: Side                             #: current role: which side price is expected to hold
    role_since_index: int                  #: bar the current role epoch began (touch counters reset here)
    pending_since_index: int | None        #: drives ``pending_sr_expiry_bars`` (CF-15)
    break_index: int | None                #: the most recent body close beyond the level
    retest_index: int | None               #: confirmation candle #2 of the most recent episode
    confirmed_index: int | None            #: bar the flip confirmed
    arm_index: int | None                  #: entry arms at the OPEN of this bar (CF-15)
    break_move_away_pct: Decimal | None    #: S2-R6 quality score of the most recent break
    deviations: int                        #: S2-R4 rollbacks seen in the window
    expiries: int
    transitions: tuple[FlipTransition, ...]

    @property
    def flipped(self) -> bool:
        """True when the level currently sits in a confirmed flipped role."""
        return self.state in (FlipState.CONFIRMED_SUPPORT, FlipState.CONFIRMED_RESISTANCE)


def role_of_kind(kind: LevelKind) -> Side:
    """The side a level role expects price to hold (``range_low`` behaves as support, etc.)."""
    if kind in (LevelKind.SUPPORT, LevelKind.SR_CONFIRMED_SUPPORT, LevelKind.RANGE_LOW):
        return "support"
    if kind in (LevelKind.RESISTANCE, LevelKind.SR_CONFIRMED_RESISTANCE, LevelKind.RANGE_HIGH):
        return "resistance"
    raise ValueError(f"{kind!r} has no support/resistance role")


def flip_kind(state: FlipState, role: Side) -> LevelKind:
    """Map a machine state onto the SPEC.md §2.3 ``Level.kind`` vocabulary."""
    if state is FlipState.PENDING:
        return LevelKind.SR_PENDING
    if state is FlipState.CONFIRMED_SUPPORT:
        return LevelKind.SR_CONFIRMED_SUPPORT
    if state is FlipState.CONFIRMED_RESISTANCE:
        return LevelKind.SR_CONFIRMED_RESISTANCE
    return LevelKind.SUPPORT if role == "support" else LevelKind.RESISTANCE


def extra_confirmation_candles(config: Config, tf: Timeframe | str) -> int:
    """Confirming closes required **after** the retest candle (CF-15, S2-R7).

    ``flip_confirm_candles`` counts the whole sequence: the breaking close is candle #1 and the
    retest close is candle #2, so the default (2) needs no further candles.  S2-R7's extra
    lower-timeframe candle is added when the series timeframe sits strictly below
    ``flip_extra_candle_below_tf`` (``"disabled"`` and the non-ladder aliases switch it off).
    """
    base = max(0, int(config.flip_confirm_candles) - 2)
    label = config.flip_extra_candle_below_tf
    try:
        threshold = Timeframe.parse(label)
    except ValueError:
        return base                     # "disabled", "trade_tf", "structure_tf", "1m", "5m"
    return base + (1 if Timeframe.parse(tf).rank < threshold.rank else 0)


def run_flip_machine(
    series: Series,
    config: Config,
    level_price: Decimal | float,
    original_side: Side,
    *,
    start_index: int = 0,
    end_index: int | None = None,
) -> FlipResult:
    """**SPEC.md §5.2 / CF-15** — the SR flip state machine, run over ``[start, end]``.

    ==================================  ==========================================  =========================
    from                                event                                       to
    ==================================  ==========================================  =========================
    ``support`` / ``resistance``        body close strictly beyond the level        ``sr_pending``
    ``sr_pending``                      retest inside the P9 band closing on the    ``sr_confirmed_*``
                                        new correct side (+ any extra candles)
    ``sr_pending``                      close back through before any retest        original role (**deviation**)
    ``sr_pending``                      ``pending_sr_expiry_bars`` elapse           original role
    ==================================  ==========================================  =========================

    A wick beyond the level never flips it (S2-R1, S8-R41) while ``flip_requires_body_close``
    holds, and closing *exactly* on the level counts as neither a break nor a confirmation
    (S8-R41).  ``sr_pending -> sr_pending`` is forbidden (S2-R5): the machine only leaves
    ``sr_pending`` through a confirmation, a deviation or the expiry, and the confirmation flips
    the role so the next break is measured against the opposite side.

    Entry arms at the **open of the candle after** the retest (``arm_index``); the S4-R5 third
    candle is that timing, not a third piece of evidence.  ``pending_sr_expiry_bars = 0`` means
    a pending state never expires.
    """
    price = float(level_price)
    price_dec = dec(level_price)
    n = len(series)
    if n == 0:
        raise ValueError("run_flip_machine: empty series")
    lo_i = _norm(series, start_index)
    hi_i = n - 1 if end_index is None else _norm(series, end_index)
    if hi_i < lo_i:
        raise ValueError(f"run_flip_machine: end_index {hi_i} precedes start_index {lo_i}")

    close, high, low = series.close, series.high, series.low
    body_close = bool(config.flip_requires_body_close)
    expiry = int(config.pending_sr_expiry_bars)
    extra_needed = extra_confirmation_candles(config, series.tf)

    role: Side = original_side
    state = FlipState.NONE
    role_since = lo_i
    armed = True                    # the level is holding: a break is possible
    pending_since: int | None = None
    break_index: int | None = None
    retest_index: int | None = None
    confirmed_index: int | None = None
    arm_index: int | None = None
    remaining = 0
    away_extreme: float | None = None
    move_away: Decimal | None = None
    deviations = 0
    expiries = 0
    transitions: list[FlipTransition] = []

    for i in range(lo_i, hi_i + 1):
        if state is FlipState.PENDING:
            assert pending_since is not None
            if expiry > 0 and i - pending_since >= expiry:
                transitions.append(FlipTransition(i, FlipState.PENDING, FlipState.NONE, "expiry", role))
                state, pending_since, retest_index, remaining = FlipState.NONE, None, None, 0
                expiries += 1
                # fall through: the level is live again on this bar
            else:
                # price is beyond the level; "back through" is a close on the ORIGINAL side.
                reclaimed = close[i] > price if role == "support" else close[i] < price
                on_new_side = close[i] < price if role == "support" else close[i] > price
                if away_extreme is not None:
                    away_extreme = (min(away_extreme, low[i]) if role == "support"
                                    else max(away_extreme, high[i]))
                if reclaimed:
                    transitions.append(
                        FlipTransition(i, FlipState.PENDING, FlipState.NONE, "deviation", role))
                    state, pending_since, retest_index, remaining = FlipState.NONE, None, None, 0
                    deviations += 1
                    armed = True          # the reclaim closed on the level's own side again
                    continue
                if retest_index is None:
                    if on_new_side and P.bar_at_level(series, config, price_dec, i):
                        retest_index = i
                        move_away = _move_away_pct(away_extreme, price)
                        remaining = extra_needed
                        if remaining <= 0:
                            state, role, confirmed_index, arm_index, role_since = _confirm(
                                transitions, i, role)
                            pending_since, armed = None, True
                    continue
                if on_new_side:
                    remaining -= 1
                    if remaining <= 0:
                        state, role, confirmed_index, arm_index, role_since = _confirm(
                            transitions, i, role)
                        pending_since, remaining, armed = None, 0, True
                continue

        # NONE / CONFIRMED_*: watch for the next body close beyond the level.
        # A level can only *break* while it is holding: after an expiry the machine waits for
        # price to close back on the level's own side before re-arming, so a level that expired
        # with price stranded beyond it does not re-break on the very next bar.
        if (close[i] > price) if role == "support" else (close[i] < price):
            armed = True
        if body_close:
            broken = close[i] < price if role == "support" else close[i] > price
        else:
            broken = low[i] < price if role == "support" else high[i] > price
        if armed and broken:
            armed = False
            from_state = state
            state = FlipState.PENDING
            pending_since = break_index = i
            retest_index = None
            remaining = 0
            away_extreme = low[i] if role == "support" else high[i]
            move_away = _move_away_pct(away_extreme, price)
            transitions.append(FlipTransition(i, from_state, FlipState.PENDING, "break", role))

    if state is FlipState.PENDING and away_extreme is not None:
        move_away = _move_away_pct(away_extreme, price)

    return FlipResult(
        state=state,
        kind=flip_kind(state, role),
        role=role,
        role_since_index=role_since,
        pending_since_index=pending_since,
        break_index=break_index,
        retest_index=retest_index,
        confirmed_index=confirmed_index,
        arm_index=arm_index,
        break_move_away_pct=move_away,
        deviations=deviations,
        expiries=expiries,
        transitions=tuple(transitions),
    )


def _confirm(
    transitions: list[FlipTransition], i: int, role: Side
) -> tuple[FlipState, Side, int, int, int]:
    """Apply the ``sr_pending -> sr_confirmed_*`` edge; the role flips to its opposite.

    The confirming candle closed on the new correct side, so the level is holding its new role
    from this bar on and the machine is immediately armed for the next break.
    """
    new_role: Side = "resistance" if role == "support" else "support"
    state = (FlipState.CONFIRMED_SUPPORT if new_role == "support"
             else FlipState.CONFIRMED_RESISTANCE)
    transitions.append(FlipTransition(i, FlipState.PENDING, state, "retest_confirm", new_role))
    return state, new_role, i, i + 1, i


def _move_away_pct(extreme: float | None, price: float) -> Decimal | None:
    """S2-R6 — how far price travelled away from the level after the breaking close.

    Measured on the wick extreme reached between the break and the retest (or the last bar seen).
    11 % is a strong SR, ~2 % is "measly", a close at the line is very weak (S2-A4).  The window
    end is **[OUR CHOICE]**: nothing in the corpus bounds it.
    """
    if extreme is None or price == 0:
        return None
    return dec(abs(extreme - price) / abs(price) * 100.0)


def _norm(series: Series, index: int) -> int:
    n = len(series)
    i = index + n if index < 0 else index
    if not 0 <= i < n:
        raise ValueError(f"index {index} out of range for a {n}-bar series")
    return i


# =========================================================================== CF-07 touch limits


def touch_limit(
    config: Config, *, is_range_boundary: bool = False, is_zone: bool = False
) -> int | None:
    """CF-07 playable-touch ceiling for a level.

    * a **bare S/R line** (no zone, not a range boundary) dies after ``line_touch_hard_limit``
      touches (3) — S4-R14, S5-R2, S3-R18;
    * a **range boundary** is playable to ``range_boundary_touch_limit`` (6) — S4-C1;
    * a **zone or order block** is governed by the CF-08 fill rule instead of by touch count
      when ``zone_touch_uses_fill_rule_not_count`` — the answer is then ``None`` ("no limit
      here; ask the fill rule").
    """
    if is_zone and config.zone_touch_uses_fill_rule_not_count:
        return None
    if is_range_boundary:
        return int(config.range_boundary_touch_limit)
    return int(config.line_touch_hard_limit)


def is_playable(
    level: Level, config: Config, *, is_range_boundary: bool = False, is_zone: bool = False
) -> bool:
    """CF-07 hard veto: is another trade allowed at this level's current touch count?"""
    limit = touch_limit(config, is_range_boundary=is_range_boundary, is_zone=is_zone)
    return True if limit is None else level.touch_count <= limit


def touch_decay_multiplier(touch_index: int, decay_curve: Sequence[float]) -> Decimal:
    """CF-07 size decay by touch number — the curve shape is **OURS** (S2-R15, S8-R22, TBOT1-R3).

    ``touch_index`` is 1-based (the first touch of the level is 1).  ``decay_curve`` is passed
    in, not read from config: ``touch_size_decay`` is owned by ``risk.py`` (INTERFACES.md §7),
    and this module only knows *which* touch a level is on.  Past the end of the curve the last
    entry holds.
    """
    if touch_index < 1:
        raise ValueError(f"touch_index is 1-based, got {touch_index}")
    if not decay_curve:
        raise ValueError("decay_curve must not be empty")
    idx = min(touch_index, len(decay_curve)) - 1
    return dec(decay_curve[idx])


# =========================================================================== §5.1 detector


class SupportResistanceDetector:
    """SPEC.md §5.1 — horizontal support/resistance levels with the §5.2 flip state attached.

    P3 clusters confirmed P1 pivots inside ``level_lookback_bars`` at a
    ``level_cluster_atr`` radius and keeps clusters holding ``level_min_touches`` members
    ("two touches is enough" — S4-R4, S7 ``[00:05:04]``).  The cluster price is the
    volume-weighted mean of its members, which is the machine form of his "points of most
    touch".  For each surviving cluster this detector then:

    1. decides the level's **original role** from where price closed on the bar the cluster
       became knowable (support when price is above it, resistance when below);
    2. runs the §5.2 machine over the rest of the series, so the emitted ``kind`` /
       ``flip_state`` are the level's state *as of the last bar handed in*;
    3. counts P4 touches **inside the current role epoch** — the counter resets on a role flip;
    4. records the S2-R6 ``break_move_away_pct`` quality score and the S6-R39
       ``is_untested_sr`` flag (a level that has flipped and not been touched since is the
       strongest rejection candidate; the flip's own retest is touch #1).

    "Do not draw resistance far above current price action" (S3 ``[00:58:34]``) is satisfied by
    construction: every level is a cluster of pivots price actually printed.
    """

    name = "support_resistance_levels"
    stage = 3
    source_ids: tuple[str, ...] = (
        "S4-R4", "S7-R11", "CF-07", "CF-15", "S2-R6", "S6-R39", "S5-R35", "S6-R7",
    )
    produces: tuple[str, ...] = (ConfluenceClass.SR_LEVEL.value,)

    def detect(self, series: Series, config: Config) -> list[Level]:
        """Emit the live :class:`~tbot.models.Level` set, ordered by the bar that completed each."""
        n = len(series)
        if n == 0:
            return []
        now = n - 1
        pivots = P.swing_points(series, config)
        by_id: dict[str, SwingPoint] = {p.id: p for p in pivots}
        clusters = P.cluster_levels(series, config, pivots, now_index=now)
        if not clusters:
            return []

        close = series.close
        levels: list[Level] = []
        for cluster in clusters:
            members = [by_id[pid] for pid in cluster.member_pivot_ids if pid in by_id]
            if not members:
                continue
            created = min(max(p.confirmed_at_index for p in members), now)
            scan_start = min(cluster.bar_indices)
            side = self._original_side(cluster, float(close[scan_start]))
            flip = run_flip_machine(series, config, cluster.price, side,
                                    start_index=scan_start, end_index=now)
            touches = P.count_touches(
                series, config, cluster.price, flip.role,
                start_index=flip.role_since_index, end_index=now,
            )
            tolerance_low, tolerance_high = P.tolerance_band(series, config, cluster.price, now)
            level = Level(
                id="",                   # assigned below, once the emission order is fixed
                symbol=series.symbol,
                tf=series.tf,
                price=cluster.price,
                kind=flip.kind,
                created_index=created,
                member_pivot_ids=list(cluster.member_pivot_ids),
                touch_count=touches.count,
                touch_history=list(touches.history),
                flip_state=flip.state,
                pending_since_index=flip.pending_since_index,
                break_move_away_pct=flip.break_move_away_pct,
                is_untested_sr=flip.flipped and touches.count <= 1,
                tolerance=(tolerance_high - tolerance_low) / Decimal(2),
                source_ids=self._object_source_ids(flip),
            )
            levels.append(level)

        levels.sort(key=lambda lv: (lv.created_index, lv.price))
        self._assign_ids(series, levels)
        return levels

    def _assign_ids(self, series: Series, levels: Sequence[Level]) -> None:
        """INTERFACES.md §6.5: ``symbol:tf:detector:completion_bar`` plus ``:n`` when one bar
        completes several levels.  Never a uuid, never a call-order counter."""
        seen: dict[int, int] = {}
        for lv in levels:
            n = seen.get(lv.created_index, 0)
            seen[lv.created_index] = n + 1
            lv.id = object_id(series, self.name, lv.created_index, n)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _original_side(cluster: P.LevelCluster, close_at_first_member: float) -> Side:
        """The role the level was born with: a cluster of swing **highs** is resistance, a
        cluster of swing **lows** is support (S4-R4).

        A mixed cluster falls back to where price closed on the bar of its earliest member —
        above the cluster means it was acting as support, below means resistance.  Ties go to
        support so the level is watched for the downside break that starts the flip machine.
        """
        if cluster.high_members > cluster.low_members:
            return "resistance"
        if cluster.low_members > cluster.high_members:
            return "support"
        return "resistance" if close_at_first_member < float(cluster.price) else "support"

    @staticmethod
    def _object_source_ids(flip: FlipResult) -> tuple[str, ...]:
        ids = ["S4-R4", "S7 [00:05:04]"]
        if flip.transitions:
            ids.extend(FLIP_SOURCE_IDS)
        if flip.deviations:
            ids.append("S3-R17")
        if flip.expiries:
            ids.append("S2-A15")
        if flip.break_move_away_pct is not None:
            ids.append("S2-R6")
        return tuple(dict.fromkeys(ids))

    def to_confluence(
        self, objects: Sequence[Level], config: Config
    ) -> list[P.ConfluenceObject]:
        """INTERFACES.md §6.7 adapter: a level scores at its own price, class ``sr_level``."""
        return [
            P.ConfluenceObject(
                id=lv.id,
                price=lv.price,
                obj_class=ConfluenceClass.SR_LEVEL.value,
                tf=lv.tf,
                source_ids=lv.source_ids,
            )
            for lv in objects
        ]


def live_levels(levels: Iterable[Level], config: Config) -> list[Level]:
    """The subset still worth trading: CF-07 touch limits applied to bare lines."""
    return [lv for lv in levels if is_playable(lv, config)]
