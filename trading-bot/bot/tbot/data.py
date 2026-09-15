"""tbot.data — OHLCV loading, timeframe resampling and the deterministic synthetic generator.

No network access, ever (SPEC.md §1.9: nothing in this build may call an exchange API).  A live
feed, if one is ever added, must arrive through the unimplemented ``ExecutionAdapter`` of §12.6.

Three entry points:

* :func:`load_csv` — read a ``timestamp,open,high,low,close,volume`` CSV into a
  :class:`~tbot.models.Series` (``quote_volume`` optional; derived when absent).
* :func:`resample` — aggregate a Series up the CF-24 ladder, cutting daily and larger bars at
  ``day_boundary_utc`` (P16, CF-45).
* :func:`synthetic` — a seeded generator producing a series with **known embedded features**:
  a range, an impulse → consolidation → breakout demand zone, an order block and a swing failure.
  It returns the feature index map alongside the series, so tests assert against exact bars.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
import pandas as pd

from .config import Config
from .models import OHLCV_COLUMNS, Series, Timeframe

__all__ = [
    "load_csv",
    "frame_from_records",
    "resample",
    "align_series",
    "SyntheticFeatures",
    "SyntheticSeries",
    "synthetic",
]

_TIMESTAMP_ALIASES = ("timestamp", "time", "open_time", "date", "datetime")


# --------------------------------------------------------------------------- loading

def load_csv(
    path: str | Path,
    tf: Timeframe | str,
    symbol: str = "UNKNOWN",
    venue_kind: Literal["spot", "perp"] = "spot",
) -> Series:
    """Load an OHLCV CSV into a :class:`~tbot.models.Series`.

    Expected columns: ``timestamp, open, high, low, close, volume`` (``quote_volume`` optional).
    The timestamp column may be ISO-8601 text or epoch seconds / milliseconds; it is parsed to
    tz-aware UTC.  Rows are sorted by timestamp and de-duplicated (last row wins), because the
    :class:`Series` contract demands a strictly increasing, unique index.

    Only closed bars belong in the file — P1 forbids repainting, so a partially formed final bar
    must be dropped before it reaches a detector.
    """
    df = pd.read_csv(path)
    lowered = {c.lower(): c for c in df.columns}
    ts_col = next((lowered[a] for a in _TIMESTAMP_ALIASES if a in lowered), None)
    if ts_col is None:
        raise ValueError(f"{path}: no timestamp column (looked for {list(_TIMESTAMP_ALIASES)})")
    missing = [c for c in ("open", "high", "low", "close", "volume") if c not in lowered]
    if missing:
        raise ValueError(f"{path}: missing column(s) {missing}")

    ts = df[ts_col]
    if pd.api.types.is_numeric_dtype(ts):
        unit = "ms" if float(ts.iloc[0]) > 1e11 else "s"
        index = pd.to_datetime(ts, unit=unit, utc=True)
    else:
        index = pd.to_datetime(ts, utc=True, format="mixed")

    data = {name: pd.to_numeric(df[lowered[name]], errors="raise").astype("float64")
            for name in ("open", "high", "low", "close", "volume")}
    if "quote_volume" in lowered:
        data["quote_volume"] = pd.to_numeric(df[lowered["quote_volume"]]).astype("float64")
    frame = pd.DataFrame(data)
    frame.index = pd.DatetimeIndex(index, name="timestamp")
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return Series(frame, tf=tf, symbol=symbol, venue_kind=venue_kind)


def frame_from_records(
    records: Sequence[tuple[datetime, float, float, float, float, float]],
) -> pd.DataFrame:
    """Build an OHLCV frame from ``(timestamp, open, high, low, close, volume)`` tuples."""
    idx = pd.DatetimeIndex([r[0] for r in records], name="timestamp")
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    frame = pd.DataFrame(
        {
            "open": [r[1] for r in records],
            "high": [r[2] for r in records],
            "low": [r[3] for r in records],
            "close": [r[4] for r in records],
            "volume": [r[5] for r in records],
        },
        index=idx,
    ).astype("float64")
    frame["quote_volume"] = frame["close"] * frame["volume"]
    return frame


# --------------------------------------------------------------------------- resampling

def align_series(*series: Series, lookback_bars: int | None = None) -> tuple[Series, ...] | None:
    """Restrict every input to the timestamps **all** of them share.

    Cross-symbol maths needs a common bar grid and the package had none: symbols list on
    different dates, exchanges go down for different hours, and two series of equal length are
    not therefore two series of equal dates.  Before this, the only cross-symbol consumer
    (:func:`tbot.regime.rolling_correlation`) took a *positional* tail of each leg and compared
    bar-against-bar at whatever date offset happened to exist.

    Returns one restricted :class:`Series` per input, in argument order, sharing an identical
    index; or ``None`` when the intersection is empty.  ``lookback_bars`` keeps only the last
    *n* common bars.

    **Why this is a separate unit and not folded into ``rolling_correlation``.**  Auto-aligning
    inside the correlation would trade one silent wrongness for another: a caller asking for 90
    bars would get a number computed over whatever overlap existed — possibly three bars —
    with nothing in the return value to say so.  Aligning is the *caller's* decision because
    only the caller knows whether a short overlap is acceptable.  ``rolling_correlation`` keeps
    its fail-closed timestamp check as the backstop for callers that forget (GAPS.md GAP 3 A1).

    No configuration and no thresholds: this is a data-layer operation, not a rule.
    """
    if not series:
        return None
    index = series[0].index
    for other in series[1:]:
        index = index.intersection(other.index)
    if len(index) == 0:
        return None
    if lookback_bars is not None and lookback_bars > 0:
        index = index[-int(lookback_bars):]
    return tuple(
        Series(s.frame.loc[index], tf=s.tf, symbol=s.symbol, venue_kind=s.venue_kind,
               validate=False, copy=False)
        for s in series
    )


def resample(series: Series, tf: Timeframe | str, config: Config | None = None) -> Series:
    """Aggregate ``series`` up to timeframe ``tf`` (CF-24 ladder).

    ``open`` = first, ``high`` = max, ``low`` = min, ``close`` = last, volumes summed.  Buckets
    with no source bars are dropped, so the result keeps the "gaps allowed" part of the
    :class:`Series` contract.  Daily and larger bars are cut at ``config.day_boundary_utc``
    (P16, CF-45) — pass a :class:`~tbot.config.Config` to honour a non-midnight boundary.

    Downsampling (to a *lower* timeframe) is impossible and raises ``ValueError``.
    """
    target = Timeframe.parse(tf)
    if target.rank < series.tf.rank:
        raise ValueError(f"cannot resample {series.tf.value} down to {target.value}")
    if target is series.tf:
        return series

    offset = timedelta(0)
    if config is not None and target.minutes >= Timeframe.D1.minutes:
        hh, _, mm = config.day_boundary_utc.partition(":")
        offset = timedelta(hours=int(hh), minutes=int(mm))

    frame = series.frame
    shifted = frame.copy()
    shifted.index = shifted.index - offset
    agg = shifted.resample(target.pandas_freq, label="left", closed="left", origin="epoch").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum", "quote_volume": "sum"}
    ).dropna(subset=["open"])
    agg.index = agg.index + offset
    return Series(agg.loc[:, list(OHLCV_COLUMNS)], tf=target, symbol=series.symbol,
                  venue_kind=series.venue_kind)


# --------------------------------------------------------------------------- synthetic

@dataclass(frozen=True, slots=True)
class SyntheticFeatures:
    """Exact bar indices of the features :func:`synthetic` embeds.

    Every index is positional into the returned :class:`~tbot.models.Series`.
    """

    range_start: int
    range_end: int
    range_high: float
    range_low: float
    impulse_start: int
    impulse_end: int
    consolidation_start: int
    consolidation_end: int
    breakout_index: int
    zone_top: float
    zone_bottom: float
    order_block_index: int
    ob_dir_change_index: int
    sfp_index: int
    sfp_swing_index: int
    sfp_swing_price: float
    retest_index: int
    total_bars: int


@dataclass(frozen=True, slots=True)
class SyntheticSeries:
    """A :func:`synthetic` result: the series plus the map of what was embedded where."""

    series: Series
    features: SyntheticFeatures


def synthetic(
    *,
    seed: int = 7,
    tf: Timeframe | str = Timeframe.H1,
    symbol: str = "SYNTH",
    base_price: float = 100.0,
    noise: float = 0.05,
    start: datetime | None = None,
) -> SyntheticSeries:
    """Deterministic OHLCV series with known, hand-placed features.

    Layout (all indices reported in :class:`SyntheticFeatures`):

    ===== ============================================================================
    bars  content
    ===== ============================================================================
    0-19  warm-up drift, so ATR is meaningful before anything interesting happens
    20-59 a **range**: five clean rejections at ``range_high`` and bounces at ``range_low``
    60-67 an **up impulse** out of the range top (the P2 directional change)
    68-75 a horizontal **consolidation** — the demand zone box (P13 + P5)
    76-83 the **breakout** and move away, giving the P10 sufficient gap
    84-95 a pullback that retests the zone, filling well under 50 % of it (P6)
    96-99 a **swing failure**: a wick through the prior swing high, body closing back below
    ===== ============================================================================

    The **order block** is the last red candle before the impulse (S6-R1/R2), reported as
    ``order_block_index``.  Noise is drawn from ``numpy.random.Generator(PCG64(seed))``, so the
    same ``seed`` always yields byte-identical bars — nothing here is time- or environment-
    dependent.  ``noise`` is the wick/close jitter in price units.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    tfe = Timeframe.parse(tf)
    t0 = start or datetime(2024, 1, 1, tzinfo=timezone.utc)
    step = timedelta(minutes=tfe.minutes)

    closes: list[float] = []
    volumes: list[float] = []

    def push(price: float, vol: float = 1_000_000.0) -> None:
        closes.append(price)
        volumes.append(vol)

    # 0-19 warm-up drift ---------------------------------------------------
    for i in range(20):
        push(base_price + 0.05 * i)

    range_low = base_price
    range_high = base_price + 8.0
    range_start = len(closes)
    # 20-59 range: five oscillations, one clean touch of each boundary per cycle ------
    cycle = (range_low + 2.0, range_low + 4.0, range_low + 6.0, range_high,
             range_low + 6.0, range_low + 4.0, range_low + 2.0, range_low)
    for _ in range(5):
        for target in cycle:
            push(target)
    range_end = len(closes) - 1

    # 60-67 impulse up out of the range ------------------------------------
    impulse_start = len(closes)
    ob_index = impulse_start - 1          # the last red candle before the move
    for i in range(8):
        push(range_high + 1.5 * (i + 1), vol=1_800_000.0)
    impulse_end = len(closes) - 1
    ob_dir_change_index = impulse_end

    # 68-75 horizontal consolidation = the demand zone ---------------------
    cons_start = len(closes)
    zone_mid = closes[-1]
    for i in range(8):
        push(zone_mid + (0.90 if i % 2 else -0.90))
    cons_end = len(closes) - 1
    zone_top = max(closes[cons_start:cons_end + 1]) 
    zone_bottom = min(closes[cons_start:cons_end + 1])

    # 76-83 breakout and move away (the P10 sufficient gap) ----------------
    breakout_index = len(closes)
    for i in range(8):
        push(zone_top + 2.2 * (i + 1), vol=2_200_000.0)
    peak = closes[-1]

    # 84-95 pullback that retests the zone top without filling 50 % --------
    retest_index = len(closes) + 6
    pull = np.linspace(peak, zone_top - 0.3, 12)
    for price in pull:
        push(float(price))

    # 96-99 swing failure through the prior swing high ---------------------
    sfp_swing_index = int(np.argmax(np.array(closes[:breakout_index + 8])))
    sfp_swing_price = peak
    sfp_index = len(closes) + 2
    push(zone_top + 2.0)
    push(zone_top + 4.0)
    push(zone_top + 3.0, vol=3_000_000.0)     # the SFP bar itself (wick added below)
    push(zone_top + 1.0)

    n = len(closes)
    close_arr = np.array(closes, dtype="float64")
    open_arr = np.empty(n, dtype="float64")
    open_arr[0] = base_price
    open_arr[1:] = close_arr[:-1]

    jitter = rng.uniform(0.0, noise, size=n)
    high = np.maximum(open_arr, close_arr) + jitter
    low = np.minimum(open_arr, close_arr) - rng.uniform(0.0, noise, size=n)

    # the SFP: wick strictly above the prior swing high, body closing back below it
    high[sfp_index] = sfp_swing_price + 1.5
    low[sfp_index] = min(low[sfp_index], close_arr[sfp_index] - 0.2)

    idx = pd.DatetimeIndex([t0 + i * step for i in range(n)], name="timestamp")
    frame = pd.DataFrame(
        {"open": open_arr, "high": high, "low": low, "close": close_arr,
         "volume": np.array(volumes, dtype="float64")},
        index=idx,
    )
    frame["quote_volume"] = frame["close"] * frame["volume"]
    series = Series(frame, tf=tfe, symbol=symbol)

    features = SyntheticFeatures(
        range_start=range_start,
        range_end=range_end,
        range_high=range_high,
        range_low=range_low,
        impulse_start=impulse_start,
        impulse_end=impulse_end,
        consolidation_start=cons_start,
        consolidation_end=cons_end,
        breakout_index=breakout_index,
        zone_top=zone_top,
        zone_bottom=zone_bottom,
        order_block_index=ob_index,
        ob_dir_change_index=ob_dir_change_index,
        sfp_index=sfp_index,
        sfp_swing_index=sfp_swing_index,
        sfp_swing_price=sfp_swing_price,
        retest_index=retest_index,
        total_bars=n,
    )
    return SyntheticSeries(series=series, features=features)
