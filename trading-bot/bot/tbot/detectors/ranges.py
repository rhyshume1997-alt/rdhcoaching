"""SPEC.md §5.4 ranges — construction, death, mid-range and the zone gate.

Built on P8 (:func:`tbot.primitives.check_range`) for validity and staleness, P7
(:func:`tbot.primitives.mid_range`) for the mid — which is **not** the naive 50 % midpoint — P3
for the boundary prices and P9 for "price is at the range highs/lows".  Range death (CF-26)
reuses the §5.2 flip machine from :mod:`tbot.detectors.levels`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import Literal, Sequence

from tbot.config import Config
from tbot.models import (
    ConfluenceClass,
    Direction,
    FlipState,
    Level,
    LevelKind,
    Series,
    Timeframe,
    dec,
)
import tbot.primitives as P
from tbot.detectors.base import object_id
from tbot.detectors.levels import run_flip_machine

__all__ = [
    "DetectedRange",
    "RangeClassification",
    "RangeDetector",
    "RangeZone",
    "classify_price",
]

_ZERO = Decimal(0)


class RangeZone(str, Enum):
    """Where price sits inside a range — the gate CF-25 turns into a trading decision."""

    AT_RANGE_LOW = "at_range_low"
    LOWER_ZONE = "lower_zone"
    MID_RANGE = "mid_range"
    UPPER_ZONE = "upper_zone"
    AT_RANGE_HIGH = "at_range_high"
    ABOVE_RANGE = "above_range"
    BELOW_RANGE = "below_range"


@dataclass(frozen=True, slots=True)
class RangeClassification:
    """Result of :func:`classify_price` — CF-25 made numeric."""

    zone: RangeZone
    price: Decimal
    mid: P.MidRange
    entries_blocked: bool                    #: hard gate G6: price inside the no-trade band
    long_allowed: bool                       #: long the range low, never the range high (S4-R9, S5-R10)
    short_allowed: bool                      #: short the range high, never the range low
    mid_range_limit_allowed: bool            #: S4-R6/R7 limits set at mid from the extremes
    mid_range_limit_direction: Direction | None
    reasons: tuple[str, ...]


@dataclass(slots=True)
class DetectedRange:
    """One range: its boundaries, its confirmation history and its CF-26 death state."""

    id: str
    symbol: str
    tf: Timeframe
    high: Decimal
    low: Decimal
    start_index: int
    end_index: int                           #: last bar of the un-breached window
    check: P.RangeCheck                      #: the P8 measurement
    low_level: Level
    high_level: Level | None                 #: None until the second resistance touch (S4-R4)
    mid_level: Level | None
    mid: P.MidRange | None
    low_confirmed_index: int
    low_confirmation: Literal["flip_then_touch", "second_touch"]
    high_confirmed_index: int | None
    boundary_break_index: int | None         #: first body close beyond a boundary
    broken_side: Literal["high", "low"] | None
    dead: bool
    death_index: int | None
    stale: bool
    source_ids: tuple[str, ...]

    @property
    def provisional(self) -> bool:
        """S4 ``[00:23:37]``: the range low is tradeable before the range high exists."""
        return self.high_confirmed_index is None

    @property
    def confirmed(self) -> bool:
        return self.check.valid and not self.provisional

    @property
    def height(self) -> Decimal:
        return self.high - self.low

    @property
    def bars(self) -> int:
        return self.end_index - self.start_index + 1

    def levels(self) -> list[Level]:
        """The boundary and mid levels this range contributes, low first."""
        out = [self.low_level]
        if self.high_level is not None:
            out.append(self.high_level)
        if self.mid_level is not None:
            out.append(self.mid_level)
        return out


# =========================================================================== CF-25 zone gate


def classify_price(
    rng: DetectedRange,
    series: Series,
    config: Config,
    price: Decimal | float,
    *,
    at_index: int | None = None,
    levels: Sequence[Level] = (),
) -> RangeClassification:
    """**CF-25** — where price sits in ``rng``, and what that permits.

    The band is ``mid ± mid_range_band_pct`` % of range height (P7).  "At" a boundary is the P9
    tolerance band, the same band P4 counts touches with.

    * price **inside** the mid band -> no new entries in either direction, a hard gate
      (S4-R8, S5-R14, S8-R30);
    * price **at the range low** -> longs only ("you always long range lows and only at range
      lows", S5 ``[00:21:13]``; never short a range low, S4-R9);
    * price **at the range high** -> shorts only (never long range highs, S4 exclusions);
    * price at either extreme also permits a **resting limit at mid-range** targeting the
      opposite boundary (S4-R6/R7) when ``mid_range_limits_from_extremes_enabled``, and only
      when ``mid_range_requires_intermediate_stop`` is satisfied by a structural level between
      the mid-range entry and the boundary the stop would otherwise sit at (S5-R13: "if the only
      support is the range low, skip").

    S8-C6 (five live scalps taken during mid-range chop) is recorded as behaviour, not doctrine:
    it lowers conviction elsewhere, it does not open this gate.
    """
    if rng.mid is None:
        raise ValueError(f"range {rng.id} has no mid-range: its high is unconfirmed")
    p = dec(price)
    idx = (len(series) - 1) if at_index is None else at_index
    low_band = P.tolerance_band(series, config, rng.low, idx)
    high_band = P.tolerance_band(series, config, rng.high, idx)
    reasons: list[str] = []

    if P.in_no_trade_band(p, rng.mid):
        zone = RangeZone.MID_RANGE
    elif low_band[0] <= p <= low_band[1]:
        zone = RangeZone.AT_RANGE_LOW
    elif high_band[0] <= p <= high_band[1]:
        zone = RangeZone.AT_RANGE_HIGH
    elif p > high_band[1]:
        zone = RangeZone.ABOVE_RANGE
    elif p < low_band[0]:
        zone = RangeZone.BELOW_RANGE
    elif p < rng.mid.band_low:
        zone = RangeZone.LOWER_ZONE
    else:
        zone = RangeZone.UPPER_ZONE

    entries_blocked = zone is RangeZone.MID_RANGE
    if entries_blocked:
        reasons.append("price inside the mid-range no-trade band (CF-25, S4-R8)")
    long_allowed = zone is RangeZone.AT_RANGE_LOW
    short_allowed = zone is RangeZone.AT_RANGE_HIGH
    if zone in (RangeZone.LOWER_ZONE, RangeZone.UPPER_ZONE):
        reasons.append("price is between the mid-range band and a boundary: no market entry")
    if zone in (RangeZone.ABOVE_RANGE, RangeZone.BELOW_RANGE):
        reasons.append("price is outside the range")

    limit_dir: Direction | None = None
    limit_allowed = False
    if config.mid_range_limits_from_extremes_enabled and zone in (
        RangeZone.AT_RANGE_LOW, RangeZone.AT_RANGE_HIGH
    ):
        # S4-R6: price up at the highs -> rest a LONG limit at mid.  S4-R7 is the mirror.
        limit_dir = Direction.LONG if zone is RangeZone.AT_RANGE_HIGH else Direction.SHORT
        limit_allowed = True
        if config.mid_range_requires_intermediate_stop and not _has_intermediate_stop(
            levels, rng, limit_dir
        ):
            limit_allowed = False
            limit_dir = None
            reasons.append(
                "no structural level between the mid-range entry and the boundary "
                "(mid_range_requires_intermediate_stop, S5-R13)"
            )
    return RangeClassification(
        zone=zone,
        price=p,
        mid=rng.mid,
        entries_blocked=entries_blocked,
        long_allowed=long_allowed and not entries_blocked,
        short_allowed=short_allowed and not entries_blocked,
        mid_range_limit_allowed=limit_allowed,
        mid_range_limit_direction=limit_dir,
        reasons=tuple(reasons),
    )


def _has_intermediate_stop(
    levels: Sequence[Level], rng: DetectedRange, direction: Direction
) -> bool:
    """S5-R13 — is there structure between a mid-range entry and the boundary behind it?"""
    assert rng.mid is not None
    mid = rng.mid.price
    if direction is Direction.LONG:
        return any(rng.low < lv.price < mid for lv in levels)
    return any(mid < lv.price < rng.high for lv in levels)


# =========================================================================== §5.4 detector


class RangeDetector:
    """SPEC.md §5.4 — range detection, mid-range and the CF-26 death test.

    **Boundaries.**  P3 clusters supply the candidate lines ("drawn at the points of most touch
    where two candidate lines compete", S4-R4).  Every ``(lower, upper)`` pair is measured over
    the longest run of bars that closed inside it, then handed to P8.

    **Range low** (S4-R3) is confirmed by the first support touch after the level was broken
    *above* and flipped to support — the §5.2 machine is run on the lower boundary to find that
    flip.  Where no such flip exists the fallback is P8's second support touch.

    **Range high** (S4-R4) is confirmed only by a **second** touch of resistance: a first
    rejection in price discovery does not count.  Until then the range is *provisional* — the
    range low is tradeable before the range high exists (S4 ``[00:23:37]``), so a provisional
    range still emits its ``range_low`` level, and no ``range_high`` or ``mid_range`` level.

    **Mid-range** is P7 and is explicitly **not** the geometric midpoint: it is the
    highest-touch-count P3 level within ``mid_range_search_pct`` % *of range height* around the
    geometric 50 %, falling back to the geometric 50 % only when no level qualifies.

    **Death** (CF-26) is a body close beyond a boundary **followed by** a §5.2 flip confirmation
    in the opposite direction — the strictest of his three usages, chosen because the loose ones
    kill a range on every wick.  ``range_death_mode`` selects the alternatives.  Staleness
    (``range_max_age_bars``, ``range_stale_bars``) is retirement, not death, and comes from P8.

    **Nesting**: within one series, a range whose boundaries sit inside another's is dropped —
    the wider range wins.  Across timeframes the highest timeframe wins (S7-R20), which is the
    pipeline's decision, not this detector's.

    The **Monday range** (S5-R8/R9, CF-45) is emitted alongside: Monday's session high and low,
    keyed off ``day_boundary_utc`` and taken from ``monday_range_source_tf``.
    """

    name = "ranges"
    stage = 5
    source_ids: tuple[str, ...] = (
        "S4-R3", "S4-R4", "CF-25", "CF-26", "CF-07", "S7-R20", "S5-R8", "S5-R9",
    )
    produces: tuple[str, ...] = (ConfluenceClass.RANGE_BOUNDARY.value,)

    def detect(self, series: Series, config: Config) -> list[Level]:
        """Emit range boundary and mid-range :class:`~tbot.models.Level` objects, newest last."""
        out: list[Level] = []
        for rng in self.detect_ranges(series, config):
            out.extend(rng.levels())
        out.extend(self.monday_range_levels(series, config))
        return self._assign_ids(series, out)

    def _assign_ids(self, series: Series, levels: list[Level]) -> list[Level]:
        """INTERFACES.md §6.5: ``symbol:tf:detector:completion_bar`` plus ``:n`` when one bar
        completes several levels — a range boundary completes on its confirming touch."""
        levels.sort(key=lambda lv: (lv.created_index, lv.price, lv.kind.value))
        seen: dict[int, int] = {}
        for lv in levels:
            n = seen.get(lv.created_index, 0)
            seen[lv.created_index] = n + 1
            lv.id = object_id(series, self.name, lv.created_index, n)
        return levels

    # ------------------------------------------------------------------ ranges

    def detect_ranges(self, series: Series, config: Config) -> list[DetectedRange]:
        """Every live range on this series, oldest first.  Dead ranges are not returned."""
        n = len(series)
        if n == 0:
            return []
        now = n - 1
        pivots = P.swing_points(series, config)
        clusters = P.cluster_levels(series, config, pivots, now_index=now)
        if len(clusters) < 2:
            return []
        cluster_levels = self._cluster_levels(series, config, clusters, now)

        found: list[DetectedRange] = []
        for i, lower in enumerate(clusters):
            for upper in clusters[i + 1:]:
                if upper.price <= lower.price:
                    continue
                rng = self._build(series, config, lower.price, upper.price, cluster_levels, now)
                if rng is not None:
                    found.append(rng)
        kept = self._drop_nested(found)
        seen: dict[int, int] = {}
        for rng in kept:
            n = seen.get(rng.end_index, 0)
            seen[rng.end_index] = n + 1
            rng.id = object_id(series, self.name, rng.end_index, n)
        self._assign_ids(series, [lv for r in kept for lv in r.levels()])
        return kept

    def _build(
        self, series: Series, config: Config, low: Decimal, high: Decimal,
        cluster_levels: Sequence[Level], now: int,
    ) -> DetectedRange | None:
        window = _longest_inside_run(series, low, high)
        if window is None:
            return None
        start, end = window
        check = P.check_range(series, config, high, low, start_index=start, end_index=end)
        blocking = [r for r in check.reasons if not r.startswith("upper touches")]
        if blocking:
            return None

        up = P.count_touches(series, config, high, "resistance", start_index=start, end_index=end)
        dn = P.count_touches(series, config, low, "support", start_index=start, end_index=end)
        if dn.count < 2:
            return None
        low_index, low_how = self._confirm_low(series, config, low, dn, start, end)
        high_index = up.history[1][0] if up.count >= 2 else None

        break_index, broken_side = _first_break(series, low, high, start, now)
        dead, death_index = self._death(series, config, low, high, break_index, broken_side, now)
        if dead:
            return None

        source_ids = ["S4-R3", "S4-R4", "P8"]
        if low_how == "flip_then_touch":
            source_ids.append("CF-15")
        if high_index is None:
            source_ids.append("S4 [00:23:37]")
        if break_index is not None:
            source_ids.append("CF-26")
        if check.stale:
            source_ids.append("S4-A16")

        rid = ""            # assigned in detect_ranges, once the surviving set is known
        low_level = self._boundary_level(
            series, config, low, LevelKind.RANGE_LOW, low_index, dn, now,
            tuple(source_ids) + ("S4-R3",),
        )
        high_level = mid_level = None
        mid = None
        if high_index is not None:
            high_level = self._boundary_level(
                series, config, high, LevelKind.RANGE_HIGH, high_index, up, now,
                tuple(source_ids) + ("S4-R4",),
            )
            mid = P.mid_range(config, high, low, cluster_levels)
            mid_level = Level(
                id="",
                symbol=series.symbol,
                tf=series.tf,
                price=mid.price,
                kind=LevelKind.MID_RANGE,
                created_index=high_index,
                touch_count=self._mid_touches(cluster_levels, mid),
                tolerance=_half_band(series, config, mid.price, now),
                source_ids=("CF-25", "CF-26", "S4-A1") + (
                    ("S4-R4",) if mid.source == "level" else ()
                ),
            )
        return DetectedRange(
            id=rid,
            symbol=series.symbol,
            tf=series.tf,
            high=high,
            low=low,
            start_index=start,
            end_index=end,
            check=check,
            low_level=low_level,
            high_level=high_level,
            mid_level=mid_level,
            mid=mid,
            low_confirmed_index=low_index,
            low_confirmation=low_how,
            high_confirmed_index=high_index,
            boundary_break_index=break_index,
            broken_side=broken_side,
            dead=False,
            death_index=death_index,
            stale=check.stale,
            source_ids=tuple(dict.fromkeys(source_ids)),
        )

    # ------------------------------------------------------------------ confirmation

    def _confirm_low(
        self, series: Series, config: Config, low: Decimal, touches: P.TouchCount,
        start: int, end: int,
    ) -> tuple[int, Literal["flip_then_touch", "second_touch"]]:
        """S4-R3 — the first support touch after the level flipped up through resistance.

        Falls back to P8's second support touch when the level has no prior resistance episode
        (which is the common case for a range that formed without a preceding breakout).
        """
        if float(series.close[0]) < float(low):
            flip = run_flip_machine(series, config, low, "resistance", start_index=0, end_index=end)
            if flip.state is FlipState.CONFIRMED_SUPPORT and flip.confirmed_index is not None:
                after = [i for i, _ in touches.history if i >= flip.confirmed_index]
                if after:
                    return after[0], "flip_then_touch"
        second = touches.history[1][0] if len(touches.history) >= 2 else touches.history[0][0]
        return second, "second_touch"

    def _death(
        self, series: Series, config: Config, low: Decimal, high: Decimal,
        break_index: int | None, broken_side: Literal["high", "low"] | None, now: int,
    ) -> tuple[bool, int | None]:
        """**CF-26** range death, per ``range_death_mode``."""
        mode = config.range_death_mode
        if mode == "single_stopout":
            # [OUR CHOICE] mechanisation of "until proven wrong = a stop-out" (S4-A16): the
            # first bar whose wick trades beyond a boundary's tolerance band, i.e. through where
            # a structural stop would sit.
            for i in range(0, now + 1):
                hi_band = P.tolerance_band(series, config, high, i)[1]
                lo_band = P.tolerance_band(series, config, low, i)[0]
                if series.high[i] > float(hi_band) or series.low[i] < float(lo_band):
                    return True, i
            return False, None
        if break_index is None:
            return False, None
        if mode == "close_beyond":
            return True, break_index
        # "close_beyond_plus_flip" (default): the break must be followed by a CF-15 flip
        # confirmation in the opposite direction.
        side: Literal["support", "resistance"] = "resistance" if broken_side == "high" else "support"
        boundary = high if broken_side == "high" else low
        flip = run_flip_machine(series, config, boundary, side,
                                start_index=break_index, end_index=now)
        if flip.flipped and flip.confirmed_index is not None:
            return True, flip.confirmed_index
        return False, None

    # ------------------------------------------------------------------ Monday range

    def monday_range_levels(self, series: Series, config: Config, *,
                            at_index: int | None = None) -> list[Level]:
        """**S5-R8/S5-R9, CF-45** — Monday's high and low, keyed off ``day_boundary_utc``.

        The session is ``[week_start, week_start + 1 day)`` (P16).  Only a *completed* Monday is
        used: while the current bar is still inside Monday the previous week's is returned, so
        nothing repaints.  ``monday_range_source_tf`` is the 1D candle it is read from; a series
        coarser than that cannot express it and yields nothing.
        """
        n = len(series)
        if n == 0:
            return []
        source_tf = Timeframe.parse(config.monday_range_source_tf)
        if series.tf.minutes > source_tf.minutes:
            return []
        now = n - 1 if at_index is None else at_index
        ts = series.timestamp(now)
        week = P.week_start(ts, config)
        if ts < week + timedelta(days=1):
            week -= timedelta(days=7)
        stop = week + timedelta(days=1)
        members = [i for i in range(now + 1) if week <= series.timestamp(i) < stop]
        if not members:
            return []
        first, last = members[0], members[-1]
        hi = dec(max(float(series.high[i]) for i in members))
        lo = dec(min(float(series.low[i]) for i in members))
        ids = ("S5-R8", "S5-R9", "CF-45")
        out = [
            Level(
                id="", symbol=series.symbol, tf=series.tf, price=lo, kind=LevelKind.RANGE_LOW,
                created_index=last, tolerance=_half_band(series, config, lo, now),
                anchor_indices=[first, last], source_ids=ids,
            ),
            Level(
                id="", symbol=series.symbol, tf=series.tf, price=hi, kind=LevelKind.RANGE_HIGH,
                created_index=last, tolerance=_half_band(series, config, hi, now),
                anchor_indices=[first, last], source_ids=ids,
            ),
        ]
        return self._assign_ids(series, out)

    # ------------------------------------------------------------------ helpers

    def _cluster_levels(
        self, series: Series, config: Config, clusters: Sequence[P.LevelCluster], now: int
    ) -> list[Level]:
        """P3 clusters as :class:`~tbot.models.Level` objects, for the P7 mid-range search."""
        out: list[Level] = []
        for c in clusters:
            side: Literal["support", "resistance"] = (
                "resistance" if c.high_members > c.low_members else "support"
            )
            touches = P.count_touches(series, config, c.price, side,
                                      start_index=min(c.bar_indices), end_index=now)
            out.append(Level(
                id=f"{series.symbol}:{series.tf.value}:{self.name}:cluster:{float(c.price):.10g}",
                symbol=series.symbol, tf=series.tf, price=c.price,
                kind=LevelKind.SUPPORT if side == "support" else LevelKind.RESISTANCE,
                created_index=min(max(c.bar_indices), now),
                member_pivot_ids=list(c.member_pivot_ids),
                touch_count=touches.count, touch_history=list(touches.history),
                source_ids=("S4-R4",),
            ))
        return out

    @staticmethod
    def _mid_touches(levels: Sequence[Level], mid: P.MidRange) -> int:
        if mid.source != "level":
            return 0
        for lv in levels:
            if lv.id == mid.level_id:
                return lv.touch_count
        return 0

    def _boundary_level(
        self, series: Series, config: Config, price: Decimal, kind: LevelKind,
        created: int, touches: P.TouchCount, now: int, source_ids: tuple[str, ...],
    ) -> Level:
        return Level(
            id="",
            symbol=series.symbol,
            tf=series.tf,
            price=price,
            kind=kind,
            created_index=created,
            touch_count=touches.count,
            touch_history=list(touches.history),
            tolerance=_half_band(series, config, price, now),
            source_ids=tuple(dict.fromkeys(source_ids + ("CF-07",))),
        )

    @staticmethod
    def _drop_nested(ranges: Sequence[DetectedRange]) -> list[DetectedRange]:
        """Resolve overlapping candidates — S7-R20's nesting rule applied inside one series.

        Two ranges overlap when both their price bands and their bar windows intersect.  Of an
        overlapping set only the dominant range survives, ranked **[OUR CHOICE]** by
        ``(confirmed, bars, height)``: a range whose high is confirmed by a second touch
        (S4-R4) always beats a provisional one, and only then does the wider window win.  Across
        timeframes the highest timeframe wins, which is the pipeline's call, not this one's.
        """
        order = sorted(
            ranges,
            key=lambda r: (r.confirmed, r.bars, r.height, -r.start_index, r.id),
            reverse=True,
        )
        kept: list[DetectedRange] = []
        for rng in order:
            if any(_overlaps(rng, other) for other in kept):
                continue
            kept.append(rng)
        kept.sort(key=lambda r: (r.start_index, r.low))
        return kept

    def to_confluence(
        self, objects: Sequence[Level], config: Config
    ) -> list[P.ConfluenceObject]:
        """INTERFACES.md §6.7 adapter: boundaries and the mid all score as ``range_boundary``."""
        return [
            P.ConfluenceObject(
                id=lv.id,
                price=lv.price,
                obj_class=ConfluenceClass.RANGE_BOUNDARY.value,
                tf=lv.tf,
                source_ids=lv.source_ids,
            )
            for lv in objects
        ]


def _longest_inside_run(series: Series, low: Decimal, high: Decimal) -> tuple[int, int] | None:
    """The longest maximal run of bars that **closed** inside ``[low, high]``.

    P8 rejects any window containing a body close beyond a boundary, so this is the only window
    worth measuring; ties go to the most recent run.
    """
    close = series.close
    lo, hi = float(low), float(high)
    best: tuple[int, int] | None = None
    start: int | None = None
    for i in range(len(series)):
        inside = lo <= close[i] <= hi
        if inside and start is None:
            start = i
        if not inside and start is not None:
            best = _better(best, (start, i - 1))
            start = None
    if start is not None:
        best = _better(best, (start, len(series) - 1))
    return best


def _overlaps(a: DetectedRange, b: DetectedRange) -> bool:
    """Do two ranges cover the same prices over the same bars?"""
    price = a.low <= b.high and b.low <= a.high
    bars = a.start_index <= b.end_index and b.start_index <= a.end_index
    return price and bars


def _better(best: tuple[int, int] | None, run: tuple[int, int]) -> tuple[int, int]:
    if best is None:
        return run
    return run if (run[1] - run[0]) >= (best[1] - best[0]) else best


def _first_break(
    series: Series, low: Decimal, high: Decimal, start: int, now: int
) -> tuple[int | None, Literal["high", "low"] | None]:
    """The first body close beyond either boundary at or after ``start`` (CF-26 first half)."""
    close = series.close
    for i in range(start, now + 1):
        if close[i] > float(high):
            return i, "high"
        if close[i] < float(low):
            return i, "low"
    return None, None


def _half_band(series: Series, config: Config, price: Decimal, at_index: int) -> Decimal:
    low, high = P.tolerance_band(series, config, price, at_index)
    return (high - low) / Decimal(2)
