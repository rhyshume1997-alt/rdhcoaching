"""SPEC.md §5.3 trend lines — three-touch validity, break detection, retest-after-break trigger.

The module **ships disabled** (`module_trendline_break_enabled = false`, CF-37, S8-C1): the
pipeline decides whether its objects may generate trades, but they always score confluence
(`disowned_modules_still_score_confluence`).  Neither switch is read here — `pipeline.py` owns
both.

This detector owns no configuration keys.  It reads `swing_k` / `swing_price_source` through
:func:`tbot.primitives.swing_points` (P1) and `level_tolerance_atr` through
:func:`tbot.primitives.tolerance_band` (P9), and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Sequence

from tbot.config import Config
from tbot.models import (
    ConfluenceClass,
    Level,
    LevelKind,
    Series,
    SwingKind,
    SwingPoint,
    dec,
)
import tbot.primitives as P
from tbot.detectors.base import object_id

__all__ = ["TrendLine", "TrendlineDetector", "line_price_at"]

Side = Literal["support", "resistance"]

#: A line needs this many touches before it is a candidate — unanimous across five sessions
#: (S2-R14, S3-R19, S4-R20, S5-R1, S8-R7).  Not a config key: nothing in SPEC.md §11 tunes it.
MIN_TOUCHES = 3


def line_price_at(anchor_index: int, anchor_price: Decimal, slope_per_bar: Decimal,
                  bar_index: int) -> Decimal:
    """The line's price at ``bar_index`` — the same arithmetic as ``Level.price_at``."""
    return anchor_price + slope_per_bar * Decimal(bar_index - anchor_index)


@dataclass(frozen=True, slots=True)
class TrendLine:
    """One fitted trend line: the emitted :class:`~tbot.models.Level` plus its §5.3 lifecycle."""

    level: Level
    side: Side                        #: diagonal support (uptrend) or resistance (downtrend), S6-R28
    touch_indices: tuple[int, ...]    #: every pivot contact, ascending; >= 3 (S2-R14)
    validated_index: int              #: bar the third touch confirmed — the line becomes a candidate
    span_bars: int                    #: first touch -> last touch
    score: Decimal                    #: ranking key, **[OUR CHOICE]** (S3-C10, S8-A4)
    is_primary: bool                  #: highest-scoring line; the rest stay as confluence objects
    break_index: int | None           #: first body close through the line (TBOT1-R1, S7-R39)
    retest_index: int | None          #: the safer entry: price back at the broken line (S8-R8/R13)
    arm_index: int | None             #: retest entry arms at the open of this bar

    @property
    def intact(self) -> bool:
        """S7-R39 / TBOT1-R1: a line is intact until a candle closes back through it."""
        return self.break_index is None

    def price_at(self, bar_index: int) -> Decimal:
        return self.level.price_at(bar_index)


class TrendlineDetector:
    """SPEC.md §5.3 — diagonal support/resistance.

    **Detection.**  Every pair of confirmed P1 pivots of the same kind seeds a line (lows ->
    diagonal support, highs -> diagonal resistance).  A pivot **touches** the line when either
    its body price or its wick price falls inside the P9 tolerance band of the line's price at
    that bar — "you can draw it off the wicks or off the bodies" (S2-R14).  A line becomes a
    candidate at ``MIN_TOUCHES`` (3) contacts and only if no candle body-closed through it
    between the first and the third (TBOT1-R1).

    **Competing lines.**  "There is no wrong way to draw a trend line" (S3-C10): every valid
    line is emitted.  Ranking is ``touch_count + span / len(series)`` — touches first, span as
    the tie-break — and the top line is flagged ``is_primary``.  The ranking function is
    **[OUR CHOICE]** (S8-A4).

    **Break and retest.**  The break is the first body close through the line after validation
    (S7-R39, S8-R9, TBOT1-R28 all cut on the close, not the wick).  The retest trigger is the
    first later bar that comes back inside the band and still closes on the broken side; entry
    arms at the open of the following bar and is the safer of the two entries (S8-R8, S8-R13,
    TBOT1-R16).  There is no retest timeout: ``msb_retest_timeout_bars`` belongs to
    ``structure.py`` and §11 gives this module no equivalent key.

    Never traded alone (S7-R39, `single_class_trade_forbidden`) and never DCA'd
    (S8-R11, `dca_count_breakdown = 0`) — both are enforced downstream, not here.
    """

    name = "trendlines"
    stage = 4
    source_ids: tuple[str, ...] = (
        "S2-R14", "S3-R19", "S4-R20", "S5-R1", "S8-R7", "S6-R28", "TBOT1-R1", "S8-R8", "S8-R13",
    )
    produces: tuple[str, ...] = (ConfluenceClass.TRENDLINE.value,)

    def detect(self, series: Series, config: Config) -> list[Level]:
        """Emit one ``LevelKind.TRENDLINE`` :class:`~tbot.models.Level` per valid line."""
        return [line.level for line in self.detect_lines(series, config)]

    def detect_lines(self, series: Series, config: Config) -> list[TrendLine]:
        """The full §5.3 records, ordered by the bar that validated each line (newest last)."""
        n = len(series)
        if n == 0:
            return []
        now = n - 1
        pivots = P.confirmed_swings(P.swing_points(series, config), now)
        lows = [p for p in pivots if p.kind is SwingKind.LOW]
        highs = [p for p in pivots if p.kind is SwingKind.HIGH]

        candidates: list[TrendLine] = []
        for group, side in ((lows, "support"), (highs, "resistance")):
            candidates.extend(self._fit_group(series, config, group, side, now))

        kept = self._dedupe(candidates)
        if not kept:
            return []
        best = max(kept, key=lambda ln: (ln.score, -ln.validated_index))
        out = [
            TrendLine(**{**_as_dict(ln), "is_primary": ln is best})
            for ln in kept
        ]
        out.sort(key=lambda ln: (ln.validated_index, ln.level.price, ln.touch_indices))
        seen: dict[int, int] = {}
        for line in out:
            n = seen.get(line.validated_index, 0)
            seen[line.validated_index] = n + 1
            line.level.id = object_id(series, self.name, line.validated_index, n)
        return out

    # ------------------------------------------------------------------ fitting

    def _fit_group(
        self, series: Series, config: Config, pivots: Sequence[SwingPoint], side: Side, now: int
    ) -> list[TrendLine]:
        out: list[TrendLine] = []
        seen: set[tuple[int, ...]] = set()
        for a in range(len(pivots)):
            for b in range(a + 1, len(pivots)):
                p0, p1 = pivots[a], pivots[b]
                span = p1.bar_index - p0.bar_index
                if span <= 0:
                    continue
                slope = (p1.price - p0.price) / Decimal(span)
                touches = self._touches(series, config, pivots, p0.bar_index, p0.price, slope, now)
                if len(touches) < MIN_TOUCHES:
                    continue
                key = tuple(touches)
                if key in seen:
                    continue
                seen.add(key)
                validated = self._validated_index(pivots, touches)
                if validated is None or validated > now:
                    continue
                if self._closed_through(series, side, p0.bar_index, p0.price, slope,
                                        touches[0], validated):
                    continue                      # the line was already broken while forming
                line = self._build(series, config, side, p0.bar_index, p0.price, slope,
                                   touches, validated, now)
                out.append(line)
        return out

    @staticmethod
    def _touches(
        series: Series, config: Config, pivots: Sequence[SwingPoint], anchor_index: int,
        anchor_price: Decimal, slope: Decimal, now: int,
    ) -> tuple[int, ...]:
        """Pivot contacts with the line, body **or** wick inside the P9 band (S2-R14).

        Touch counting against a *sloped* level cannot use P4: :func:`count_touches` takes a
        scalar price.  Anchoring touches on confirmed P1 pivots sidesteps the P4 sequencing
        rules entirely — pivots are ``swing_k`` bars apart, so no two contacts can be
        consecutive bars and there is nothing to de-duplicate.
        """
        hits: list[int] = []
        for p in pivots:
            if p.bar_index > now:
                continue
            price = line_price_at(anchor_index, anchor_price, slope, p.bar_index)
            low, high = P.tolerance_band(series, config, price, p.bar_index)
            if (low <= p.price <= high) or (low <= p.wick_price <= high):
                hits.append(p.bar_index)
        return tuple(sorted(set(hits)))

    @staticmethod
    def _validated_index(pivots: Sequence[SwingPoint], touches: Sequence[int]) -> int | None:
        """The bar the third touch became usable — its pivot's ``confirmed_at_index`` (P1)."""
        third = touches[MIN_TOUCHES - 1]
        confirmations = [p.confirmed_at_index for p in pivots if p.bar_index == third]
        return min(confirmations) if confirmations else None

    @staticmethod
    def _closed_through(
        series: Series, side: Side, anchor_index: int, anchor_price: Decimal, slope: Decimal,
        start: int, end: int,
    ) -> bool:
        close = series.close
        for i in range(start, end + 1):
            price = float(line_price_at(anchor_index, anchor_price, slope, i))
            if (close[i] < price) if side == "support" else (close[i] > price):
                return True
        return False

    def _build(
        self, series: Series, config: Config, side: Side, anchor_index: int,
        anchor_price: Decimal, slope: Decimal, touches: tuple[int, ...], validated: int, now: int,
    ) -> TrendLine:
        close = series.close
        break_index: int | None = None
        for i in range(validated + 1, now + 1):
            price = float(line_price_at(anchor_index, anchor_price, slope, i))
            if (close[i] < price) if side == "support" else (close[i] > price):
                break_index = i
                break

        retest_index: int | None = None
        if break_index is not None:
            for i in range(break_index + 1, now + 1):
                price = line_price_at(anchor_index, anchor_price, slope, i)
                low, high = P.tolerance_band(series, config, price, i)
                intersects = series.low[i] <= float(high) and series.high[i] >= float(low)
                held = (close[i] < float(price)) if side == "support" else (close[i] > float(price))
                if intersects and held:
                    retest_index = i
                    break

        span = touches[-1] - touches[0]
        score = dec(len(touches)) + dec(span) / dec(max(len(series), 1))
        source_ids = ["S2-R14", "S3-R19", "S4-R20", "S5-R1", "S8-R7", "S6-R28"]
        if break_index is not None:
            source_ids.append("TBOT1-R1")
            source_ids.append("S7-R39")
        if retest_index is not None:
            source_ids.extend(("S8-R8", "S8-R13", "TBOT1-R16"))
        level = Level(
            id="",                        # assigned in detect_lines, once the order is fixed
            symbol=series.symbol,
            tf=series.tf,
            price=line_price_at(anchor_index, anchor_price, slope, validated),
            kind=LevelKind.TRENDLINE,
            created_index=validated,
            touch_count=len(touches),
            touch_history=[(i, dec(close[i])) for i in touches],
            slope_per_bar=slope,
            anchor_indices=list(touches),
            tolerance=_half_band(series, config, anchor_index, anchor_price, slope, now),
            source_ids=tuple(dict.fromkeys(source_ids)),
        )
        return TrendLine(
            level=level,
            side=side,
            touch_indices=touches,
            validated_index=validated,
            span_bars=span,
            score=score,
            is_primary=False,
            break_index=break_index,
            retest_index=retest_index,
            arm_index=None if retest_index is None else retest_index + 1,
        )

    @staticmethod
    def _dedupe(lines: Sequence[TrendLine]) -> list[TrendLine]:
        """Keep maximal touch sets: a line whose touches are a subset of another's is the same
        line drawn worse."""
        sets = [(set(ln.touch_indices), ln) for ln in lines]
        kept: list[TrendLine] = []
        for touches, line in sets:
            if any(other is not line and touches < others for others, other in sets):
                continue
            if any(set(k.touch_indices) == touches and k.side == line.side for k in kept):
                continue
            kept.append(line)
        return kept

    def to_confluence(
        self, objects: Sequence[Level], config: Config
    ) -> list[P.ConfluenceObject]:
        """INTERFACES.md §6.7 adapter.  A sloped level scores at its price on its **anchor bar**;
        the caller re-prices it with ``Level.price_at(now)`` when scoring a later bar."""
        return [
            P.ConfluenceObject(
                id=lv.id,
                price=lv.price,
                obj_class=ConfluenceClass.TRENDLINE.value,
                tf=lv.tf,
                source_ids=lv.source_ids,
            )
            for lv in objects
        ]


def _half_band(series: Series, config: Config, anchor_index: int, anchor_price: Decimal,
               slope: Decimal, at_index: int) -> Decimal:
    price = line_price_at(anchor_index, anchor_price, slope, at_index)
    low, high = P.tolerance_band(series, config, price, at_index)
    return (high - low) / Decimal(2)


def _as_dict(line: TrendLine) -> dict[str, object]:
    return {f: getattr(line, f) for f in TrendLine.__slots__}
