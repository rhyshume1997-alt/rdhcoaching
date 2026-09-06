"""tbot.models — the SPEC.md §2 data model, plus the :class:`Series` OHLCV wrapper.

Everything a detector, plan builder, manager, risk layer or backtester passes around lives here.

Conventions taken from SPEC.md §2:

* **All prices are ``Decimal``.**  Use :func:`dec` to convert a float / numpy scalar; it goes
  through ``repr`` so ``dec(100.5) == Decimal("100.5")`` exactly, with no binary-float dust.
* **All timestamps are timezone-aware UTC.**
* Sizes are base-asset units unless the field name ends in ``_usd`` or ``_pct``.
* ``tf`` is a member of the CF-24 timeframe ladder (:class:`Timeframe`).
* ``bar_index`` is always a **positional** index into the owning :class:`Series` (0-based), never a
  timestamp and never a pandas label.

Immutability: objects that never change after construction are ``frozen=True`` (:class:`Candle`,
:class:`SwingPoint`, :class:`Fill`, :class:`FibLevel`, :class:`Box`).  Objects that a state
machine mutates (:class:`Level`, :class:`Zone`, :class:`OrderBlock`, :class:`Setup`,
:class:`TradePlan`, :class:`EntryRung`, :class:`TakeProfit`, :class:`Position`) are mutable.
Every dataclass uses ``slots=True``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Iterator, Literal, Sequence

import numpy as np
import pandas as pd

__all__ = [
    "dec",
    "Timeframe",
    "TIMEFRAME_ORDER",
    "Direction",
    "SwingKind",
    "LevelKind",
    "FlipState",
    "ZoneSide",
    "ZoneClass",
    "OBSide",
    "TradeClass",
    "EntryFamily",
    "Vehicle",
    "Conviction",
    "PositionState",
    "Account",
    "OrderType",
    "FillKind",
    "CloseReason",
    "Trend",
    "ConfluenceClass",
    "OHLCV_COLUMNS",
    "Series",
    "Candle",
    "Box",
    "SwingPoint",
    "Level",
    "Zone",
    "OrderBlock",
    "FibLevel",
    "Setup",
    "EntryRung",
    "TakeProfit",
    "TradePlan",
    "Position",
    "Fill",
]


# --------------------------------------------------------------------------- numerics

def dec(value: Any) -> Decimal:
    """Canonical float/int/str/numpy -> :class:`Decimal` conversion used everywhere in tbot.

    Floats go through ``repr`` (shortest round-trip form), so ``dec(0.1) == Decimal("0.1")`` and
    price maths stays readable in test assertions.  ``Decimal`` inputs pass through unchanged.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


# --------------------------------------------------------------------------- enums

class Timeframe(str, Enum):
    """The CF-24 timeframe ladder, ascending.  ``str`` subclass, so ``Timeframe.H1 == "1H"``."""

    M15 = "15m"
    M30 = "30m"
    H1 = "1H"
    H2 = "2H"
    H4 = "4H"
    H8 = "8H"
    H12 = "12H"
    D1 = "1D"
    D2 = "2D"
    D3 = "3D"
    W1 = "1W"

    @property
    def rank(self) -> int:
        """Position on the ladder, 0 = ``15m``."""
        return TIMEFRAME_ORDER.index(self)

    @property
    def pandas_freq(self) -> str:
        """The pandas offset alias for :func:`tbot.data.resample`."""
        return _PANDAS_FREQ[self]

    @property
    def minutes(self) -> int:
        """Bar length in minutes."""
        return _TF_MINUTES[self]

    def step(self, offset: int) -> "Timeframe":
        """Move ``offset`` rungs up (positive) or down the ladder, clamped at both ends.

        ``structure_tf = trade_tf.step(config.structure_tf_offset)`` is the CF-24 rule.
        """
        idx = min(max(self.rank + offset, 0), len(TIMEFRAME_ORDER) - 1)
        return TIMEFRAME_ORDER[idx]

    @classmethod
    def parse(cls, label: str | "Timeframe") -> "Timeframe":
        """Parse a ladder label (``"4H"``) into a :class:`Timeframe`; raises ``ValueError``."""
        if isinstance(label, Timeframe):
            return label
        try:
            return cls(label)
        except ValueError as exc:  # pragma: no cover - message clarity only
            raise ValueError(f"{label!r} is not on the CF-24 timeframe ladder "
                             f"({[t.value for t in cls]})") from exc


TIMEFRAME_ORDER: tuple[Timeframe, ...] = tuple(Timeframe)

_TF_MINUTES: dict[Timeframe, int] = {
    Timeframe.M15: 15, Timeframe.M30: 30, Timeframe.H1: 60, Timeframe.H2: 120,
    Timeframe.H4: 240, Timeframe.H8: 480, Timeframe.H12: 720, Timeframe.D1: 1440,
    Timeframe.D2: 2880, Timeframe.D3: 4320, Timeframe.W1: 10080,
}
_PANDAS_FREQ: dict[Timeframe, str] = {
    Timeframe.M15: "15min", Timeframe.M30: "30min", Timeframe.H1: "1h", Timeframe.H2: "2h",
    Timeframe.H4: "4h", Timeframe.H8: "8h", Timeframe.H12: "12h", Timeframe.D1: "1D",
    Timeframe.D2: "2D", Timeframe.D3: "3D", Timeframe.W1: "1W",
}


class Direction(str, Enum):
    """Trade direction (SPEC.md §2.6)."""

    LONG = "long"
    SHORT = "short"

    @property
    def sign(self) -> int:
        """``+1`` for long, ``-1`` for short — the multiplier for adverse/favourable maths."""
        return 1 if self is Direction.LONG else -1

    @property
    def opposite(self) -> "Direction":
        return Direction.SHORT if self is Direction.LONG else Direction.LONG


class SwingKind(str, Enum):
    HIGH = "high"
    LOW = "low"


class LevelKind(str, Enum):
    """SPEC.md §2.3 ``Level.kind`` — the S2 state machine roles plus the S4 range roles."""

    SUPPORT = "support"
    RESISTANCE = "resistance"
    SR_PENDING = "sr_pending"
    SR_CONFIRMED_SUPPORT = "sr_confirmed_support"
    SR_CONFIRMED_RESISTANCE = "sr_confirmed_resistance"
    RANGE_HIGH = "range_high"
    RANGE_LOW = "range_low"
    MID_RANGE = "mid_range"
    TRENDLINE = "trendline"


class FlipState(str, Enum):
    """SR flip machine states (SPEC.md §5.2, CF-15)."""

    NONE = "none"
    PENDING = "sr_pending"
    CONFIRMED_SUPPORT = "sr_confirmed_support"
    CONFIRMED_RESISTANCE = "sr_confirmed_resistance"


class ZoneSide(str, Enum):
    DEMAND = "demand"
    SUPPLY = "supply"


class ZoneClass(str, Enum):
    """CF-10: his continuation definition vs the textbook reversal one."""

    CONTINUATION = "continuation"
    REVERSAL = "reversal"


class OBSide(str, Enum):
    """S6-R1 / S6-R2: bullish OB = last **red** candle before an up move, and mirror."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class TradeClass(str, Enum):
    SWING = "swing"
    SCALP = "scalp"
    COUNTER_TREND = "counter_trend"
    PRICE_DISCOVERY = "price_discovery"


class EntryFamily(str, Enum):
    """CF-16 entry families."""

    RETEST = "retest"
    FLIP_PENDING = "flip_pending"
    TRIGGER = "trigger"


class Vehicle(str, Enum):
    SPOT = "spot"
    LEVERAGE = "leverage"


class Conviction(str, Enum):
    """SPEC.md §6.3 conviction mapping."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class PositionState(str, Enum):
    """SPEC.md §9.1 states."""

    DRAFT = "DRAFT"
    ARMED = "ARMED"
    PARTIAL = "PARTIAL"
    OPEN = "OPEN"
    MANAGING = "MANAGING"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class Account(str, Enum):
    """CF-43 / S2-R32 account scoping."""

    LONG_TERM = "long_term"
    SPOT_SHORT = "spot_short"
    LEVERAGE_SWING = "leverage_swing"
    LEVERAGE_SCALP = "leverage_scalp"
    CHALLENGE = "challenge"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class FillKind(str, Enum):
    ENTRY = "entry"
    DCA = "dca"
    TP = "tp"
    STOP = "stop"
    EXIT = "exit"


class CloseReason(str, Enum):
    """SPEC.md §2.8 ``Position.close_reason``."""

    STOP = "stop"
    TP_FINAL = "tp_final"
    TRAIL_OUT = "trail_out"
    STRUCTURAL_STALE = "structural_stale"
    TIME_STALE = "time_stale"
    MSB_EXIT = "msb_exit"
    SPOT_FLIP = "spot_flip"
    MANUAL = "manual"


class Trend(str, Enum):
    """P11 output.  ``NEUTRAL`` is explicitly **not** counter-trend (CF-03)."""

    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class ConfluenceClass(str, Enum):
    """The P14 dedup classes; the keys of ``config.confluence_weights`` (SPEC.md §6.1)."""

    SR_LEVEL = "sr_level"
    ZONE = "zone"
    ORDER_BLOCK = "order_block"
    RANGE_BOUNDARY = "range_boundary"
    FIB = "fib"
    TRENDLINE = "trendline"
    PATTERN = "pattern"
    SFP = "sfp"
    RSI_DIVERGENCE = "rsi_divergence"
    EMA200 = "ema200"
    CME_GAP = "cme_gap"


# --------------------------------------------------------------------------- Series

OHLCV_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume", "quote_volume")


class Series:
    """A closed-bar OHLCV frame for one symbol on one timeframe, with typed accessors.

    **Contract** (relied on by every detector and primitive):

    * ``frame`` is a :class:`pandas.DataFrame` with exactly the columns
      ``open, high, low, close, volume, quote_volume`` (float64, in that order).
    * The index is a tz-aware UTC :class:`pandas.DatetimeIndex` of **bar open times**, strictly
      increasing and unique.  It may have gaps (missing bars) — never assume a fixed step.
    * Every row is a **closed** bar (``Candle.is_closed`` is always ``True``).  A live partial bar
      must be dropped by the loader, not carried here: P1 forbids repainting.
    * ``bar_index`` everywhere in tbot means the **positional** offset into this frame.
    * The object is treated as immutable; ``frame`` is stored as a defensive copy and the derived
      numpy arrays are cached.  Slicing returns a new :class:`Series`.
    """

    __slots__ = ("_frame", "tf", "symbol", "venue_kind", "_cache")

    def __init__(
        self,
        frame: pd.DataFrame,
        tf: Timeframe | str,
        symbol: str = "TEST",
        venue_kind: Literal["spot", "perp"] = "spot",
        *,
        validate: bool = True,
        copy: bool = True,
    ) -> None:
        df = frame.copy() if copy else frame
        if "quote_volume" not in df.columns and {"close", "volume"} <= set(df.columns):
            df["quote_volume"] = df["close"] * df["volume"]
        if validate:
            _validate_frame(df)
        self._frame: pd.DataFrame = df.loc[:, list(OHLCV_COLUMNS)].astype("float64")
        self.tf: Timeframe = Timeframe.parse(tf)
        self.symbol: str = symbol
        self.venue_kind: Literal["spot", "perp"] = venue_kind
        self._cache: dict[str, np.ndarray] = {}

    # -- construction -------------------------------------------------------
    @classmethod
    def from_arrays(
        cls,
        timestamps: Sequence[datetime] | pd.DatetimeIndex,
        open_: Sequence[float],
        high: Sequence[float],
        low: Sequence[float],
        close: Sequence[float],
        volume: Sequence[float] | None = None,
        quote_volume: Sequence[float] | None = None,
        tf: Timeframe | str = Timeframe.H1,
        symbol: str = "TEST",
        venue_kind: Literal["spot", "perp"] = "spot",
    ) -> "Series":
        """Build a Series from parallel sequences (the workhorse of the test suite)."""
        idx = pd.DatetimeIndex(pd.to_datetime(list(timestamps), utc=True), name="timestamp")
        vol = list(volume) if volume is not None else [1.0] * len(idx)
        data = {
            "open": list(open_), "high": list(high), "low": list(low), "close": list(close),
            "volume": vol,
            "quote_volume": list(quote_volume) if quote_volume is not None
            else [c * v for c, v in zip(close, vol)],
        }
        return cls(pd.DataFrame(data, index=idx), tf=tf, symbol=symbol, venue_kind=venue_kind)

    # -- frame access -------------------------------------------------------
    @property
    def frame(self) -> pd.DataFrame:
        """The underlying DataFrame (do not mutate it)."""
        return self._frame

    @property
    def index(self) -> pd.DatetimeIndex:
        return self._frame.index  # type: ignore[return-value]

    def __len__(self) -> int:
        return len(self._frame)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Series {self.symbol} {self.tf.value} bars={len(self)}>"

    def _col(self, name: str) -> np.ndarray:
        arr = self._cache.get(name)
        if arr is None:
            arr = self._frame[name].to_numpy(dtype="float64", copy=True)
            arr.setflags(write=False)
            self._cache[name] = arr
        return arr

    # -- raw columns --------------------------------------------------------
    @property
    def open(self) -> np.ndarray: return self._col("open")

    @property
    def high(self) -> np.ndarray: return self._col("high")

    @property
    def low(self) -> np.ndarray: return self._col("low")

    @property
    def close(self) -> np.ndarray: return self._col("close")

    @property
    def volume(self) -> np.ndarray: return self._col("volume")

    @property
    def quote_volume(self) -> np.ndarray: return self._col("quote_volume")

    # -- derived columns (S7-R11 / S5-R44: structure reads bodies) ----------
    def _derived(self, name: str, fn) -> np.ndarray:
        arr = self._cache.get(name)
        if arr is None:
            arr = fn()
            arr.setflags(write=False)
            self._cache[name] = arr
        return arr

    @property
    def body_high(self) -> np.ndarray:
        """``max(open, close)`` per bar."""
        return self._derived("body_high", lambda: np.maximum(self.open, self.close))

    @property
    def body_low(self) -> np.ndarray:
        """``min(open, close)`` per bar."""
        return self._derived("body_low", lambda: np.minimum(self.open, self.close))

    @property
    def body_size(self) -> np.ndarray:
        return self._derived("body_size", lambda: self.body_high - self.body_low)

    @property
    def upper_wick(self) -> np.ndarray:
        return self._derived("upper_wick", lambda: self.high - self.body_high)

    @property
    def lower_wick(self) -> np.ndarray:
        return self._derived("lower_wick", lambda: self.body_low - self.low)

    @property
    def bar_range(self) -> np.ndarray:
        return self._derived("bar_range", lambda: self.high - self.low)

    @property
    def is_green(self) -> np.ndarray:
        """``close > open`` (S6-R1/R2 colour mapping); a doji is **not** green."""
        return self._derived("is_green", lambda: (self.close > self.open))

    @property
    def timestamps(self) -> pd.DatetimeIndex:
        return self.index

    # -- slicing / rows -----------------------------------------------------
    def slice(self, start: int | None = None, stop: int | None = None) -> "Series":
        """Positional slice ``[start:stop)`` as a new Series (same tf/symbol/venue)."""
        return Series(self._frame.iloc[slice(start, stop)], tf=self.tf, symbol=self.symbol,
                      venue_kind=self.venue_kind, validate=False)

    def head(self, n: int) -> "Series":
        """The first ``n`` bars — the backtest's "as of bar n" view (no lookahead)."""
        return self.slice(0, n)

    def candle(self, i: int) -> "Candle":
        """Materialise bar ``i`` as a :class:`Candle` (Decimal prices)."""
        row = self._frame.iloc[i]
        ts = self.index[i].to_pydatetime()
        return Candle(
            symbol=self.symbol,
            tf=self.tf,
            open_time=ts,
            close_time=ts + pd.Timedelta(minutes=self.tf.minutes).to_pytimedelta(),
            open=dec(row["open"]), high=dec(row["high"]), low=dec(row["low"]),
            close=dec(row["close"]), volume=dec(row["volume"]),
            quote_volume=dec(row["quote_volume"]),
            is_closed=True, venue_kind=self.venue_kind,
        )

    def candles(self) -> Iterator["Candle"]:
        for i in range(len(self)):
            yield self.candle(i)

    def timestamp(self, i: int) -> datetime:
        return self.index[i].to_pydatetime()

    def price_at(self, i: int, field_name: str = "close") -> Decimal:
        """One price as a Decimal, e.g. ``series.price_at(4, "body_high")``."""
        return dec(getattr(self, field_name)[i])


def _validate_frame(df: pd.DataFrame) -> None:
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Series frame is missing column(s) {missing}; required {list(OHLCV_COLUMNS)}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Series frame index must be a pandas DatetimeIndex of bar open times")
    if len(df) and df.index.tz is None:
        raise ValueError("Series frame index must be timezone-aware UTC (SPEC.md §2)")
    if len(df) > 1 and not df.index.is_monotonic_increasing:
        raise ValueError("Series frame index must be strictly increasing")
    if df.index.has_duplicates:
        raise ValueError("Series frame index must be unique (one row per bar open)")
    if len(df):
        hi, lo = df["high"].to_numpy(), df["low"].to_numpy()
        op, cl = df["open"].to_numpy(), df["close"].to_numpy()
        bad = (hi < lo) | (hi < np.maximum(op, cl) - 1e-12) | (lo > np.minimum(op, cl) + 1e-12)
        if bool(bad.any()):
            raise ValueError(f"Series frame has {int(bad.sum())} bar(s) violating low <= open/close <= high")


# --------------------------------------------------------------------------- candles

@dataclass(frozen=True, slots=True)
class Candle:
    """SPEC.md §2.1.  Derived fields are properties so the dataclass stays a pure record."""

    symbol: str
    tf: Timeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    is_closed: bool = True
    venue_kind: Literal["spot", "perp"] = "spot"

    @property
    def body_high(self) -> Decimal: return max(self.open, self.close)

    @property
    def body_low(self) -> Decimal: return min(self.open, self.close)

    @property
    def upper_wick(self) -> Decimal: return self.high - self.body_high

    @property
    def lower_wick(self) -> Decimal: return self.body_low - self.low

    @property
    def bar_range(self) -> Decimal: return self.high - self.low

    @property
    def is_green(self) -> bool: return self.close > self.open


@dataclass(frozen=True, slots=True)
class Box:
    """A price box: the shared return type of the P5 zone/order-block box constructors."""

    top: Decimal
    bottom: Decimal
    start_index: int
    end_index: int
    included_upper_wick: bool = False
    included_lower_wick: bool = False

    @property
    def height(self) -> Decimal:
        return self.top - self.bottom

    @property
    def midpoint(self) -> Decimal:
        """P6 midpoint — frozen at creation, never re-measured."""
        return (self.top + self.bottom) / Decimal(2)

    def contains(self, price: Decimal) -> bool:
        return self.bottom <= price <= self.top


# --------------------------------------------------------------------------- structure

@dataclass(frozen=True, slots=True)
class SwingPoint:
    """SPEC.md §2.2 / P1.  ``price`` is the **body** extreme; ``wick_price`` the wick extreme."""

    id: str
    symbol: str
    tf: Timeframe
    kind: SwingKind
    bar_index: int
    price: Decimal
    wick_price: Decimal
    confirmed_at_index: int
    k: int

    def is_usable_at(self, bar_index: int) -> bool:
        """P1 no-repainting rule: a pivot may not be read before ``confirmed_at_index``."""
        return bar_index >= self.confirmed_at_index


@dataclass(slots=True)
class Level:
    """SPEC.md §2.3.  Mutable: touch counting and the CF-15 flip machine write to it."""

    id: str
    symbol: str
    tf: Timeframe
    price: Decimal
    kind: LevelKind
    created_index: int
    member_pivot_ids: list[str] = field(default_factory=list)
    touch_count: int = 0
    touch_history: list[tuple[int, Decimal]] = field(default_factory=list)
    flip_state: FlipState = FlipState.NONE
    pending_since_index: int | None = None
    break_move_away_pct: Decimal | None = None
    is_untested_sr: bool = False
    tolerance: Decimal = Decimal(0)
    slope_per_bar: Decimal = Decimal(0)
    anchor_indices: list[int] = field(default_factory=list)
    source_ids: tuple[str, ...] = ()

    @property
    def is_trendline(self) -> bool:
        return self.kind is LevelKind.TRENDLINE

    def price_at(self, bar_index: int) -> Decimal:
        """Level price at ``bar_index`` — constant for horizontals, sloped for trend lines."""
        if self.slope_per_bar == 0:
            return self.price
        return self.price + self.slope_per_bar * Decimal(bar_index - self.created_index)


@dataclass(slots=True)
class Zone:
    """SPEC.md §2.4 supply/demand zone.  ``midpoint`` is frozen at creation (P6, CF-08)."""

    id: str
    symbol: str
    tf: Timeframe
    side: ZoneSide
    zone_class: ZoneClass
    box_top: Decimal
    box_bottom: Decimal
    midpoint: Decimal
    body_count: int
    formation_start_index: int
    formation_end_index: int
    breakout_index: int
    move_away_pct: Decimal
    move_away_atr: Decimal
    depth_atr: Decimal
    fill_pct: Decimal = Decimal(0)
    is_dead: bool = False
    rescued_by_level_id: str | None = None
    touch_count: int = 0
    contained_ob_ids: list[str] = field(default_factory=list)
    entry_price_pmt: Decimal | None = None
    source_ids: tuple[str, ...] = ()
    #: **F1** outer wick band (``zone_wick_band_enabled``, default off → both stay ``None``).
    #: ``box_top``/``box_bottom`` remain the **body core**; these two are the outer band the
    #: frames show him drawing to the wick extreme.  See :attr:`wick_band_stop_edge`.
    wick_band_top: Decimal | None = None
    wick_band_bottom: Decimal | None = None

    @property
    def depth(self) -> Decimal:
        return self.box_top - self.box_bottom

    @property
    def outer_edge(self) -> Decimal:
        """The edge price reaches **first**: ``box_top`` for demand, ``box_bottom`` for supply.

        This is the edge P6 fill and P20 points-of-most-touch measure from (SPEC.md §4).
        """
        return self.box_top if self.side is ZoneSide.DEMAND else self.box_bottom

    @property
    def body_stop_edge(self) -> Decimal:
        """**F6** — the body-box edge the *stop* is measured from: the edge price reaches **last**.

        ``box_bottom`` for a demand zone (a long stops below it), ``box_top`` for supply.  The
        mirror of :attr:`outer_edge`, which is the edge the *entries* price off.  The stop then
        sits ``stop_buffer_zone_fraction × depth`` beyond this edge (F6, three pass-2 frames).
        """
        return self.box_bottom if self.side is ZoneSide.DEMAND else self.box_top

    @property
    def has_wick_band(self) -> bool:
        """True when this zone carries the **F1** outer band (``zone_wick_band_enabled``)."""
        return self.wick_band_top is not None and self.wick_band_bottom is not None

    @property
    def wick_band_stop_edge(self) -> Decimal | None:
        """**F1** — the band edge the *stop* goes beyond, or ``None`` when no band is carried.

        The far edge, i.e. the one price reaches **last**: ``wick_band_bottom`` for demand,
        ``wick_band_top`` for supply.  The mirror of :attr:`outer_edge`, which stays on the body
        core because that is where the *entries* are priced (F1, S6 52:38; SPEC.md §8.9).
        """
        if not self.has_wick_band:
            return None
        return self.wick_band_bottom if self.side is ZoneSide.DEMAND else self.wick_band_top

    @property
    def wick_band_depth(self) -> Decimal:
        """How far the band extends past the body core on the stop side (``0`` when no band)."""
        edge = self.wick_band_stop_edge
        if edge is None:
            return Decimal(0)
        core = self.box_bottom if self.side is ZoneSide.DEMAND else self.box_top
        return abs(core - edge)


@dataclass(slots=True)
class OrderBlock:
    """SPEC.md §2.5.  Exactly one candle (S6-R3, ``ob_max_candles = 1``)."""

    id: str
    symbol: str
    tf: Timeframe
    side: OBSide
    bar_index: int
    box_top: Decimal
    box_bottom: Decimal
    dir_change_index: int
    dir_change_atr_move: Decimal
    liquidity_taken_pct: Decimal = Decimal(0)
    fill_pct: Decimal = Decimal(0)
    is_dead: bool = False
    parent_zone_id: str | None = None
    size_atr: Decimal = Decimal(0)
    source_ids: tuple[str, ...] = ()

    @property
    def midpoint(self) -> Decimal:
        return (self.box_top + self.box_bottom) / Decimal(2)


@dataclass(frozen=True, slots=True)
class FibLevel:
    """One drawn fib ratio (SPEC.md §5.9).  Immutable: re-anchoring makes a new object."""

    id: str
    symbol: str
    tf: Timeframe
    ratio: Decimal
    price: Decimal
    anchor_low_index: int
    anchor_high_index: int
    direction: Direction
    in_golden_pocket: bool = False
    source_ids: tuple[str, ...] = ()


# --------------------------------------------------------------------------- setups & plans

@dataclass(slots=True)
class Setup:
    """SPEC.md §2.6 — a scored candidate before qualification.  Gates append to ``vetoes``."""

    id: str
    symbol: str
    direction: Direction
    trade_tf: Timeframe
    structure_tf: Timeframe
    trade_class: TradeClass
    anchor_price: Decimal
    created_index: int
    object_ids: list[str] = field(default_factory=list)
    confluence_score: Decimal = Decimal(0)
    confluence_classes: set[str] = field(default_factory=set)
    entry_family: EntryFamily = EntryFamily.RETEST
    regime_flags: dict[str, Any] = field(default_factory=dict)
    vetoes: list[str] = field(default_factory=list)
    conviction: Conviction = Conviction.NORMAL
    source_ids: tuple[str, ...] = ()

    @property
    def qualified(self) -> bool:
        """A setup with any veto never becomes a plan (SPEC.md §7)."""
        return not self.vetoes


@dataclass(slots=True)
class EntryRung:
    """SPEC.md §2.7 ``EntryRung`` — one ladder rung (CF-17, CF-18).  DCA prices sit on levels."""

    index: int
    price: Decimal
    size_fraction: Decimal
    kind: Literal["entry", "dca"]
    level_id: str
    filled: bool = False
    fill_index: int | None = None
    fill_price: Decimal | None = None


@dataclass(slots=True)
class TakeProfit:
    """SPEC.md §2.7 ``TakeProfit`` — TPs sit on structural levels (S6-R20, S8-R12)."""

    index: int
    price: Decimal
    size_fraction: Decimal
    level_id: str | None = None
    hit: bool = False
    hit_index: int | None = None


@dataclass(slots=True)
class TradePlan:
    """SPEC.md §2.7 — a fully specified plan: entries, one stop, 2–5 TPs, size, vehicle."""

    id: str
    setup_id: str
    symbol: str
    direction: Direction
    trade_class: TradeClass
    vehicle: Vehicle
    leverage: Decimal
    entries: list[EntryRung]
    stop_price: Decimal
    take_profits: list[TakeProfit]
    qty_total: Decimal
    notional_usd: Decimal
    risk_budget_pct: Decimal
    average_entry: Decimal
    planned_average_entry: Decimal
    rr_to_tp1: Decimal
    expected_move_pct: Decimal
    invalidation_level_id: str
    stop_is_synthetic: bool = False
    spot_exit_rule: str | None = None
    bias_invalidation_price: Decimal | None = None
    expires_at_index: int | None = None
    source_ids: tuple[str, ...] = ()
    #: **F9** — R:R measured from the same reference to the **final** TP rather than to TP1.
    #: TradingView's position tool measures to its single target line, which is a final target,
    #: not a first partial; ``rr_measured_to`` selects which of the two the G14 gate reads.
    #: ``None`` only on hand-built plans in tests that predate the field.
    rr_to_final_tp: Decimal | None = None


@dataclass(slots=True)
class Position:
    """SPEC.md §2.8 — live state of a plan under the §9 state machine."""

    id: str
    plan_id: str
    account: Account
    state: PositionState
    qty_open: Decimal = Decimal(0)
    average_entry: Decimal = Decimal(0)
    current_stop: Decimal = Decimal(0)
    stop_reason: str = "initial"
    tps_hit: int = 0
    realised_pnl_usd: Decimal = Decimal(0)
    unrealised_pnl_usd: Decimal = Decimal(0)
    mae_atr: Decimal = Decimal(0)
    mfe_atr: Decimal = Decimal(0)
    bars_in_trade: int = 0
    opened_index: int | None = None
    closed_index: int | None = None
    close_reason: CloseReason | None = None
    touch_index_at_entry: int = 1
    r_multiple: Decimal | None = None

    @property
    def is_live(self) -> bool:
        """``PARTIAL`` and ``OPEN`` (and ``MANAGING``) count against the §10 concurrency caps."""
        return self.state in (PositionState.PARTIAL, PositionState.OPEN, PositionState.MANAGING)


@dataclass(frozen=True, slots=True)
class Fill:
    """SPEC.md §2.9 — one execution event.  Immutable audit record."""

    id: str
    position_id: str
    kind: FillKind
    bar_index: int
    timestamp: datetime
    price: Decimal
    qty: Decimal
    order_type: OrderType
    fee_usd: Decimal = Decimal(0)
    slippage_bps: Decimal = Decimal(0)
    excess_risk_usd: Decimal = Decimal(0)


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Small helper for tests and loaders: a tz-aware UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
