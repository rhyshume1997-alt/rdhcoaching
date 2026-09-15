"""tbot.backtest.engine — strict, no-lookahead bar-by-bar simulation (SPEC.md §12.1 – §12.3).

The engine walks the execution series **once, forward, one bar at a time**.  On bar ``i`` the
analysis pipeline is handed a :class:`BarWindow` built from ``series.head(i + 1)`` — a *physically
truncated* Series, not the full frame with a promise of good behaviour.  Anything a detector could
learn about bar ``i + 1`` it would have to invent.  Two guards back that up:

1. **Structural** — :meth:`BarWindow.candle` / :meth:`BarWindow.price` / :meth:`BarWindow.head`
   raise :class:`LookaheadError` for any index beyond ``now``, and the sliced series simply does
   not contain the future bars.
2. **Output audit** — every object the pipeline returns is walked and any bar index it carries
   (``bar_index``, ``created_index``, ``confirmed_at_index``, ``breakout_index``, …) that exceeds
   ``now`` raises :class:`LookaheadError`.  A detector that smuggled the full series in through a
   closure still cannot report what it saw without tripping this.

Plans armed at the close of bar ``i`` are first *workable* on bar ``i + 1``.  Orders resting from
earlier bars are processed **before** the pipeline runs, so nothing can be filled by a bar that
had not yet closed when the plan was made.

--------------------------------------------------------------------------------------------
Intrabar fill assumptions (SPEC.md §12.2 — all **[OUR CHOICE]**, all deliberately pessimistic)
--------------------------------------------------------------------------------------------

The corpus contains no execution model.  Every assumption below is ours, is chosen to be the
*worse* of the plausible readings, and is never softened for reporting.

* **A1 — Adverse-first.**  When one bar's range contains both the stop and a take-profit, the
  **stop fills first** (``intrabar_fill_model = "stop_first"``).  The engine evaluates, in order:
  pending trigger entries → resting limit rungs → the stop → take-profits.
* **A2 — Entry then stop.**  A bar that contains both a rung and the stop fills the rung *and
  then* the stop.  A same-bar entry-and-stop is a full loss, never a skipped trade.
* **A3 — Limits need trade-through.**  With ``limit_fill_requires_trade_through = true`` a resting
  limit fills only if the bar trades **strictly through** its price; a bar that merely kisses the
  price does not fill.
* **A4 — Limits fill at their price.**  Exactly at the limit, ``slippage_limit_bps`` (0.0) and
  ``fee_maker_bps``.  Price improvement is never credited, so a gap straight through a buy limit
  still fills at the limit, not at the better open.
* **A5 — Market / trigger fills.**  Trigger-family entries (SFP, MSB retest, flip confirmation)
  fill at the **next bar's open**, moved ``slippage_market_bps`` adverse, with ``fee_taker_bps``.
* **A6 — Stops are market.**  A stop fills at the worse of (stop price, this bar's open), moved
  ``slippage_market_bps`` adverse, with ``fee_taker_bps``.  A gap through the stop fills at the
  gapped open — no stop is ever honoured better than the market.
* **A7 — Partial rungs.**  An unfilled rung is unfilled; nothing is ever rounded "close enough"
  into the ladder.  That is what keeps ``average_entry`` honest.
* **A8 — Spot excess risk.**  A CF-05 close-below-then-flip exit may land far past the synthetic
  stop.  The difference is recorded on the exit :class:`~tbot.models.Fill` as
  ``excess_risk_usd`` and reported separately; it is **not** netted out of the risk statistics.
* **A9 — Duplicate stops.**  Only the first of the CF-05 / S4-R34 duplicate stops is simulated.
* **A10 — No intrabar path.**  Bars are OHLC only.  A1 and A2 govern every ambiguity.
* **A11 — Funding.**  Leverage positions accrue ``funding_bps_per_8h`` against the position,
  charged at the 8-hourly boundaries anchored on ``day_boundary_utc`` (P16).
* **A12 — Liquidation.**  Cross margin.  A position whose open loss exceeds account equity is
  force-closed and flagged loudly: with §8.8 sizing this should never fire, and if it does it is
  a bug in sizing, not a result.
* **A13 — Trailed stops act inside the same bar.**  *(Our extension of A1.)*  After a TP fills and
  CF-29 moves the stop, the **new** stop is re-tested against the same bar's range.  A bar that
  reaches TP1 and then trades back through break-even is booked as TP1 plus a break-even trail-out,
  never as an untouched runner.
* **A14 — Execution timeframe.**  The engine simulates on the timeframe of the series it is given.
  If ``backtest_execution_tf`` names a finer timeframe than that series, a ``NOTE`` event is logged
  saying so: the fill *rules* stay pessimistic, but coarse bars hide intrabar sequencing that only
  A1/A2/A10 then arbitrate.

Fees and slippage (§12.3) are charged inside the P&L **before** any metric is computed.  No metric
in :mod:`tbot.backtest.metrics` is ever gross.

Config ownership (INTERFACES.md §7): this module reads only the eight ``§11.12`` backtest keys —
``backtest_execution_tf``, ``intrabar_fill_model``, ``fee_maker_bps``, ``fee_taker_bps``,
``slippage_limit_bps``, ``slippage_market_bps``, ``funding_bps_per_8h``,
``limit_fill_requires_trade_through`` — plus the foundation keys that the primitives read on its
behalf.  Concurrency caps, position sizing, gates and management overlays belong to ``risk.py``,
``qualification.py`` and ``manager.py``; the harness executes what the pipeline hands it and never
second-guesses those numbers.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Iterator, Mapping, Protocol, Sequence, runtime_checkable

from ..config import Config
from ..models import (
    Account,
    CloseReason,
    Conviction,
    Direction,
    EntryFamily,
    EntryRung,
    Fill,
    FillKind,
    OrderType,
    Position,
    PositionState,
    Series,
    Setup,
    TakeProfit,
    Timeframe,
    TradeClass,
    TradePlan,
    Vehicle,
    dec,
)

__all__ = [
    "LookaheadError",
    "BarWindow",
    "EventKind",
    "Event",
    "EventLog",
    "DetectionRecord",
    "RejectionRecord",
    "PipelineOutput",
    "PlanProvider",
    "ClosedTrade",
    "OpenTrade",
    "EquityPoint",
    "BacktestResult",
    "BacktestEngine",
    "run_backtest",
    "split_backtest",
    "SplitResult",
    "SplitError",
    "default_plan_provider",
    "DEFAULT_IN_SAMPLE_FRACTION",
    "assert_no_future_reference",
    "assert_context_not_ahead",
    "DEFAULT_STARTING_EQUITY",
]

BPS = Decimal(10_000)
ZERO = Decimal(0)
#: Starting equity is not one of the 245 keys (§11.13), so it is an engine argument.
#: **[OUR CHOICE]** — flagged for the sweep list.
DEFAULT_STARTING_EQUITY = dec(10_000.0)
#: Default in-sample share for :func:`split_backtest`.  **[OUR CHOICE]** — a harness
#: convention (2/3 train, 1/3 test), not a SPEC.md §11 key and not one of his rules.
#: He has never been recorded discussing out-of-sample testing at all.
DEFAULT_IN_SAMPLE_FRACTION = 2.0 / 3.0
#: Quantity below which a position is treated as flat (float/Decimal dust).  **[OUR CHOICE]**
_QTY_DUST = Decimal("1e-12")


# --------------------------------------------------------------------------- lookahead guards


class LookaheadError(AssertionError):
    """A detector, plan or emitted object referenced a bar at or beyond the future.

    Deliberately an :class:`AssertionError`: SPEC.md §12.1 makes no-lookahead a *harness-level
    assertion*, not a recoverable condition.  Catching this and continuing would defeat its
    entire purpose.
    """


#: Attributes that are bar indices and must therefore be ``<= now``.
#: ``index`` is excluded on purpose — on ``EntryRung`` / ``TakeProfit`` it is a *ladder ordinal*.
#: ``expires_at_index`` is excluded on purpose — a plan expiry is legitimately in the future.
_BAR_INDEX_ATTRS: tuple[str, ...] = (
    "bar_index",
    "created_index",
    "confirmed_at_index",
    "completion_index",
    "start_index",
    "end_index",
    "breakout_index",
    "fill_index",
    "hit_index",
    "opened_index",
    "closed_index",
    "trigger_index",
    "extreme_index",
    "deepest_index",
    "order_block_index",
    "last_touch_index",
    "break_index",
    "retest_index",
    "sfp_index",
)


def assert_no_future_reference(obj: Any, now: int, *, path: str = "", _depth: int = 0,
                               _seen: set[int] | None = None) -> None:
    """Raise :class:`LookaheadError` if ``obj`` carries any bar index greater than ``now``.

    This is the second half of the SPEC.md §12.1 no-lookahead assertion.  The first half is
    structural (the pipeline only ever receives ``series.head(now + 1)``); this half catches the
    case where a detector kept a reference to a longer series and reported something from it.
    """
    if _depth > 6 or obj is None:
        return
    _seen = set() if _seen is None else _seen
    if isinstance(obj, (str, bytes, int, float, Decimal, bool, datetime, Enum)):
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for n, item in enumerate(obj):
            assert_no_future_reference(item, now, path=f"{path}[{n}]", _depth=_depth + 1, _seen=_seen)
        return
    if isinstance(obj, dict):
        for key, item in obj.items():
            assert_no_future_reference(item, now, path=f"{path}[{key!r}]", _depth=_depth + 1,
                                       _seen=_seen)
        return
    if id(obj) in _seen:
        return
    _seen.add(id(obj))

    label = path or type(obj).__name__
    for attr in _BAR_INDEX_ATTRS:
        value = getattr(obj, attr, None)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if value > now:
            raise LookaheadError(
                f"{label}.{attr} = {value} but the harness is standing on bar {now}: "
                f"an object may only reference bars it could already have seen (SPEC.md §12.1, P1)"
            )

    slots = getattr(type(obj), "__slots__", None)
    names: Sequence[str]
    if slots:
        names = tuple(slots)
    elif hasattr(obj, "__dict__"):
        names = tuple(obj.__dict__.keys())
    else:
        return
    for name in names:
        if name.startswith("_"):
            continue
        child = getattr(obj, name, None)
        if isinstance(child, (list, tuple, dict, set, frozenset)) or hasattr(child, "__slots__"):
            assert_no_future_reference(child, now, path=f"{label}.{name}", _depth=_depth + 1,
                                       _seen=_seen)


def assert_context_not_ahead(context: "Mapping[str, Series] | None", as_of: datetime,
                             *, path: str = "window.context") -> None:
    """Raise :class:`LookaheadError` if any context series carries a bar later than ``as_of``.

    The third half of the SPEC.md §12.1 no-lookahead assertion, and the one a second symbol
    needs.  :func:`assert_no_future_reference` compares **bar indices** against ``now``, which
    is meaningless across symbols: bar 40 of BTC is not bar 40 of SOL, so an index-based check
    would pass a context series that runs a month into the future.  The cross-symbol rule has to
    be stated in **timestamps**.

    A bar stamped exactly ``as_of`` is legal: that is the same closed instant the subject is
    standing on.  Anything after it is the future (GAPS.md GAP 3 A1).
    """
    if not context:
        return
    for name, other in context.items():
        if other is None or len(other) == 0:
            continue
        last = other.timestamp(-1)
        if last > as_of:
            raise LookaheadError(
                f"{path}[{name!r}] runs to {last} while the subject stands on {as_of}: a second "
                f"symbol is a second way to leak the future (SPEC.md §12.1)"
            )


def _truncate_context(context: "Mapping[str, Series] | None",
                      as_of: datetime) -> "Mapping[str, Series]":
    """Cut every context series to the bars at or before ``as_of``.

    By **timestamp**, never by position: a second symbol has its own bar numbering, its own
    listing date and its own gaps, so ``other.head(now + 1)`` would hand over whatever bars
    happened to sit at those offsets.  A series with no bar at or before ``as_of`` is dropped
    rather than handed over empty.
    """
    if not context:
        return {}
    out: dict[str, Series] = {}
    for name, other in context.items():
        if other is None or len(other) == 0:
            continue
        keep = int(other.index.searchsorted(as_of, side="right"))
        if keep <= 0:
            continue
        out[name] = other.head(keep)
    return out


@dataclass(frozen=True, slots=True)
class BarWindow:
    """The pipeline's whole view of the world on bar ``now`` — nothing later exists in it.

    ``series`` is already truncated: ``len(series) == now + 1`` and ``series`` has no rows for any
    later bar.  The accessors below add a *named* error on top of that, so a detector that reaches
    for ``now + 1`` gets :class:`LookaheadError` rather than a bare ``IndexError`` that some
    ``except`` might swallow.
    """

    series: Series
    now: int
    total_bars: int
    symbol: str
    tf: Timeframe
    #: Other symbols as of the same instant, each already truncated to ``series``' last
    #: timestamp — the cross-market context (USDT.D / BTC.D / BVOL) and, once a universe feed
    #: exists, the other tradeable symbols.  Empty when the caller injected nothing.
    #: **Every entry is subject to the same no-lookahead rule as ``series``** (GAPS.md GAP 3 A1).
    context: Mapping[str, Series] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforced on construction rather than only in `at`, so a BarWindow built by hand -- by
        # a test, or by a future caller -- cannot exist in a future-leaking state either.
        if self.context:
            assert_context_not_ahead(self.context, self.series.timestamp(-1))

    @classmethod
    def at(cls, series: Series, index: int,
           context: Mapping[str, Series] | None = None) -> "BarWindow":
        """Build the ``as of bar index`` view of ``series`` and verify the truncation.

        ``context`` is truncated **by timestamp**, not by position: a second symbol does not
        share this one's bar numbering, so slicing it to ``index + 1`` would hand over whatever
        bars happened to sit at those offsets.  Each context series is cut to the bars at or
        before ``series``' current timestamp instead.
        """
        if index < 0 or index >= len(series):
            raise ValueError(f"bar index {index} out of range for a {len(series)}-bar series")
        view = series.head(index + 1)
        if len(view) != index + 1:
            raise LookaheadError(
                f"window truncation failed: asked for bars 0..{index}, got {len(view)}"
            )
        if view.timestamp(-1) != series.timestamp(index):
            raise LookaheadError("window truncation failed: last bar is not the current bar")
        return cls(series=view, now=index, total_bars=len(series), symbol=series.symbol,
                   tf=series.tf, context=_truncate_context(context, view.timestamp(-1)))

    def __len__(self) -> int:
        return self.now + 1

    def _guard(self, i: int) -> int:
        resolved = i if i >= 0 else self.now + 1 + i
        if resolved > self.now:
            raise LookaheadError(
                f"bar {i} requested while standing on bar {self.now}: no detector may read a bar "
                f"that has not closed yet (SPEC.md §12.1, INTERFACES.md §9.1)"
            )
        if resolved < 0:
            raise IndexError(f"bar {i} is before the start of the series")
        return resolved

    def candle(self, i: int):
        """The :class:`~tbot.models.Candle` at ``i``; :class:`LookaheadError` if ``i > now``."""
        return self.series.candle(self._guard(i))

    def price(self, i: int, field_name: str = "close") -> Decimal:
        """One Decimal price at bar ``i``; :class:`LookaheadError` if ``i > now``."""
        return self.series.price_at(self._guard(i), field_name)

    def timestamp(self, i: int) -> datetime:
        return self.series.timestamp(self._guard(i))

    def head(self, n: int) -> Series:
        """``series.head(n)``, refusing any ``n`` that would reach past the current bar."""
        if n > self.now + 1:
            raise LookaheadError(
                f"head({n}) requested while standing on bar {self.now}: the future does not exist yet"
            )
        return self.series.head(n)


# --------------------------------------------------------------------------- event log


class EventKind(str, Enum):
    """Every kind of thing the harness records.  One log explains every trade end to end."""

    NOTE = "note"
    WARMUP = "warmup"
    DETECTION = "detection"
    REJECTION = "rejection"
    PLAN = "plan"
    ARM = "arm"
    FILL = "fill"
    TRANSITION = "transition"
    EXIT = "exit"
    FUNDING = "funding"
    LIQUIDATION = "liquidation"


@dataclass(frozen=True, slots=True)
class Event:
    """One entry in the audit log, tagged with the source rule IDs behind it."""

    seq: int
    bar_index: int
    timestamp: datetime
    kind: EventKind
    message: str
    trade_id: str | None = None
    trade_ref: str | None = None
    plan_id: str | None = None
    setup_id: str | None = None
    source_ids: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        """One human-readable line: ``bar  ts  KIND  ref  message  [rule ids]``."""
        who = f" {self.trade_ref}" if self.trade_ref else ""
        rules = f"  [{', '.join(self.source_ids)}]" if self.source_ids else ""
        stamp = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"#{self.bar_index:<6} {stamp}  {self.kind.value.upper():<12}{who}  {self.message}{rules}"


class EventLog:
    """An append-only, deterministically ordered list of :class:`Event`."""

    __slots__ = ("_events",)

    def __init__(self) -> None:
        self._events: list[Event] = []

    def add(self, bar_index: int, timestamp: datetime, kind: EventKind, message: str, *,
            trade_id: str | None = None, trade_ref: str | None = None, plan_id: str | None = None,
            setup_id: str | None = None, source_ids: Sequence[str] = (),
            **data: Any) -> Event:
        seen: list[str] = []
        for rule in source_ids:                 # de-duplicate, preserving first-seen order
            if rule not in seen:
                seen.append(rule)
        event = Event(seq=len(self._events), bar_index=bar_index, timestamp=timestamp, kind=kind,
                      message=message, trade_id=trade_id, trade_ref=trade_ref, plan_id=plan_id,
                      setup_id=setup_id, source_ids=tuple(seen), data=dict(data))
        self._events.append(event)
        return event

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __getitem__(self, i: int) -> Event:
        return self._events[i]

    def of_kind(self, kind: EventKind) -> tuple[Event, ...]:
        return tuple(e for e in self._events if e.kind is kind)

    def for_trade(self, ident: str) -> tuple[Event, ...]:
        """Every event belonging to one trade, by full id or by short ref (``T0007``)."""
        return tuple(e for e in self._events if ident in (e.trade_id, e.trade_ref))

    def render(self) -> str:
        return "\n".join(e.render() for e in self._events)


# --------------------------------------------------------------------------- pipeline boundary


@dataclass(frozen=True, slots=True)
class DetectionRecord:
    """One object a detector emitted on this bar (§12.4 per-detector attribution)."""

    bar_index: int
    detector: str
    object_id: str
    obj_class: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RejectionRecord:
    """One setup stopped by a §7 gate, with the gate's own wording (INTERFACES.md §9.6)."""

    bar_index: int
    setup_id: str
    gate: str
    reason: str
    symbol: str = ""
    direction: Direction | None = None
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineOutput:
    """What the analysis pipeline returns for one bar.

    ``setups`` may include *vetoed* candidates: the harness derives a rejection record from every
    setup with a non-empty ``vetoes`` list, so the §12.4 veto census is complete without the
    pipeline having to build it (INTERFACES.md §9.6, "vetoes are recorded, not swallowed").
    """

    plans: tuple[TradePlan, ...] = ()
    setups: tuple[Setup, ...] = ()
    detections: tuple[DetectionRecord, ...] = ()
    rejections: tuple[RejectionRecord, ...] = ()


@runtime_checkable
class PlanProvider(Protocol):
    """The analysis side of the harness.

    Implementations receive a :class:`BarWindow` (bars ``0..now`` only) and return the plans that
    are *newly publishable at the close of that bar*.  Returning the same plan id twice is
    harmless — the harness arms a plan id once.

    ``window.context`` carries other symbols as of the same instant, each truncated by
    timestamp.  It is **optional to consume**: a provider that ignores it behaves exactly as
    before, and :func:`default_plan_provider` only forwards it to entry points that declare a
    ``context`` parameter (GAPS.md GAP 3 A1).
    """

    def __call__(self, window: BarWindow, config: Config) -> PipelineOutput: ...


#: Where :func:`default_plan_provider` looks for the pipeline other modules are building.
#: ``(module, attribute)``, tried in order; the first import that succeeds wins.
#: Only ``tbot.pipeline`` is probed: it is the one module whose contract is stated here, so
#: guessing at another module's entry point cannot call someone else's function wrongly.
_PIPELINE_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("tbot.pipeline", "run"),
    ("tbot.pipeline", "run_pipeline"),
    ("tbot.pipeline", "analyse"),
)


def _supported_injections(entry: Any, window: BarWindow) -> dict[str, Any]:
    """The optional keyword arguments ``entry`` actually declares, filled from ``window``.

    Decided by **signature inspection**, not by ``try/except TypeError`` around the call: that
    would also swallow a ``TypeError`` raised *inside* the pipeline and silently downgrade a real
    bug to "this provider does not accept context".

    When there is nothing to inject this returns ``{}`` and the call is byte-for-byte the two
    argument call it has always been — which is every run that injects no context (GAPS.md
    GAP 3 A1).
    """
    available: dict[str, Any] = {}
    if window.context:
        available["context"] = window.context
    if not available:
        return {}
    try:
        params = inspect.signature(entry).parameters
    except (TypeError, ValueError):  # builtins and C callables have no introspectable signature
        return {}
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return available
    return {k: v for k, v in available.items() if k in params}


def default_plan_provider(window: BarWindow, config: Config) -> PipelineOutput:
    """Call ``tbot.pipeline`` if it exists yet; otherwise produce nothing, quietly.

    The import is **lazy and per-call** on purpose: the detectors, confluence, qualification and
    plan-builder modules are being written in parallel with this one, and
    ``tbot.backtest.engine`` must import cleanly while they are mid-flight (and keep working if
    they never land).  The contract a pipeline must satisfy to be picked up here is::

        def run(series: Series, config: Config) -> PipelineOutput | Sequence[TradePlan]

    where ``series`` is already truncated to the current bar.  Anything else it returns is
    ignored, loudly, via the harness ``NOTE`` event.
    """
    for module_name, attr in _PIPELINE_CANDIDATES:
        try:
            module = __import__(module_name, fromlist=[attr])
        except Exception:  # pragma: no cover - depends on modules built in parallel
            continue
        entry = getattr(module, attr, None)
        if entry is None:
            continue
        result = entry(window.series, config, **_supported_injections(entry, window))
        return _coerce_pipeline_output(result)
    return PipelineOutput()


def _coerce_pipeline_output(result: Any) -> PipelineOutput:
    """Accept a :class:`PipelineOutput`, a sequence of plans, or something with ``.plans``."""
    if isinstance(result, PipelineOutput):
        return result
    if result is None:
        return PipelineOutput()
    if isinstance(result, (list, tuple)):
        return PipelineOutput(plans=tuple(result))
    plans = tuple(getattr(result, "plans", ()) or ())
    setups = tuple(getattr(result, "setups", ()) or ())
    detections = tuple(getattr(result, "detections", ()) or ())
    rejections = tuple(getattr(result, "rejections", ()) or ())
    return PipelineOutput(plans=plans, setups=setups, detections=detections, rejections=rejections)


# --------------------------------------------------------------------------- trade records


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    """One finished trade — the unit every §12.4 metric is computed over.

    "One trade" means one plan: a trade closed at TP1 with the residual trailed out at break-even
    is **one** trade, not two (§12.4).
    """

    id: str
    ref: str
    plan_id: str
    setup_id: str
    symbol: str
    tf: Timeframe
    direction: Direction
    trade_class: TradeClass
    vehicle: Vehicle
    conviction: Conviction
    entry_family: EntryFamily
    account: Account
    primary_class: str
    confluence_classes: tuple[str, ...]
    source_ids: tuple[str, ...]
    opened_index: int
    closed_index: int
    opened_at: datetime
    closed_at: datetime
    bars_in_trade: int
    qty: Decimal
    average_entry: Decimal
    planned_average_entry: Decimal
    initial_stop: Decimal
    exit_price: Decimal
    gross_pnl_usd: Decimal
    fees_usd: Decimal
    funding_usd: Decimal
    net_pnl_usd: Decimal
    initial_risk_usd: Decimal
    r_multiple: Decimal
    close_reason: CloseReason
    tps_hit: int
    tp_count: int
    rungs_planned: int
    rungs_filled: int
    rung_fill_flags: tuple[bool, ...]
    touch_index_at_entry: int
    excess_risk_usd: Decimal
    liquidated: bool
    fills: tuple[Fill, ...]

    @property
    def full_ladder(self) -> bool:
        """Did every planned take-profit fill?  (§12.4 second win definition.)"""
        return self.tp_count > 0 and self.tps_hit >= self.tp_count

    @property
    def entry_slippage(self) -> Decimal:
        """Realised minus planned average entry, signed **adverse-positive** (§12.4 fill quality)."""
        gap = self.average_entry - self.planned_average_entry
        return gap if self.direction is Direction.LONG else -gap


@dataclass(frozen=True, slots=True)
class OpenTrade:
    """A position still live when the data ran out — reported separately, never counted as closed."""

    id: str
    ref: str
    plan_id: str
    symbol: str
    direction: Direction
    account: Account
    opened_index: int
    qty: Decimal
    average_entry: Decimal
    current_stop: Decimal
    mark_price: Decimal
    unrealised_pnl_usd: Decimal
    tps_hit: int


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """One point on the equity curve (§12.4 max drawdown, portfolio-wide and per account)."""

    bar_index: int
    timestamp: datetime
    equity: Decimal
    realised: Decimal
    unrealised: Decimal
    by_account: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Everything one run produced.  Deterministic: identical inputs, identical result."""

    symbol: str
    tf: Timeframe
    bars: int
    warmup_bars: int
    start: datetime | None
    end: datetime | None
    starting_equity: Decimal
    ending_equity: Decimal
    trades: tuple[ClosedTrade, ...]
    open_at_end: tuple[OpenTrade, ...]
    events: EventLog
    detections: tuple[DetectionRecord, ...]
    rejections: tuple[RejectionRecord, ...]
    equity_curve: tuple[EquityPoint, ...]
    config: Config
    notes: tuple[str, ...] = ()

    def trade(self, ident: str) -> ClosedTrade | None:
        """Look a trade up by full id or short ref."""
        for t in self.trades:
            if ident in (t.id, t.ref):
                return t
        return None


# --------------------------------------------------------------------------- internal state


@dataclass(slots=True)
class _LiveTrade:
    id: str
    ref: str
    plan: TradePlan
    setup: Setup | None
    account: Account
    entry_family: EntryFamily
    position: Position
    armed_index: int
    initial_stop: Decimal
    fills: list[Fill] = field(default_factory=list)
    pending_trigger: bool = False
    fees_usd: Decimal = ZERO
    funding_usd: Decimal = ZERO
    excess_risk_usd: Decimal = ZERO
    exit_notional: Decimal = ZERO
    exit_qty: Decimal = ZERO
    entry_notional: Decimal = ZERO
    entry_qty: Decimal = ZERO
    filled_qty_total: Decimal = ZERO
    tp_hit_flags: list[bool] = field(default_factory=list)
    last_funding_ts: datetime | None = None
    liquidated: bool = False
    fill_seq: int = 0


def _fee(price: Decimal, qty: Decimal, bps: Decimal) -> Decimal:
    return abs(price * qty) * bps / BPS


def _slip(price: Decimal, bps: Decimal, side: str) -> Decimal:
    """Move ``price`` adverse by ``bps``: a buy pays up, a sell receives less.  Never favourable."""
    if bps == ZERO:
        return price
    factor = (BPS + bps) / BPS if side == "buy" else (BPS - bps) / BPS
    return price * factor


def _account_for(plan: TradePlan, setup: Setup | None) -> Account:
    """Map a plan onto a §10.1 account.  The pipeline may override via ``setup.regime_flags``."""
    if setup is not None:
        override = setup.regime_flags.get("account")
        if isinstance(override, Account):
            return override
        if isinstance(override, str):
            try:
                return Account(override)
            except ValueError:
                pass
    if plan.vehicle is Vehicle.SPOT:
        return Account.SPOT_SHORT
    if plan.trade_class is TradeClass.SCALP:
        return Account.LEVERAGE_SCALP
    return Account.LEVERAGE_SWING


# --------------------------------------------------------------------------- the engine


class BacktestEngine:
    """The SPEC.md §12.1 simulator.

    ``plan_provider`` is the analysis side; it defaults to :func:`default_plan_provider`, which
    lazily looks for ``tbot.pipeline`` and produces nothing if it is not there yet.  Tests inject
    their own provider, which is also how the lookahead assertion is exercised.
    """

    def __init__(
        self,
        series: Series,
        config: Config,
        *,
        plan_provider: PlanProvider | None = None,
        starting_equity: Decimal | float = DEFAULT_STARTING_EQUITY,
        warmup_bars: int | None = None,
        audit_outputs: bool = True,
        context: Mapping[str, Series] | None = None,
    ) -> None:
        if len(series) == 0:
            raise ValueError("cannot backtest an empty series")
        self.series = series
        self.config = config
        #: Full-length other-symbol series.  Truncated per bar by :meth:`BarWindow.at`; the
        #: engine never hands an untruncated one to the pipeline (GAPS.md GAP 3 A1).
        self.context: Mapping[str, Series] = dict(context or {})
        self.provider: PlanProvider = plan_provider or default_plan_provider
        self.starting_equity = dec(starting_equity)
        self.audit_outputs = audit_outputs
        self.warmup_bars = self._default_warmup() if warmup_bars is None else int(warmup_bars)

        self._log = EventLog()
        self._live: list[_LiveTrade] = []
        self._closed: list[ClosedTrade] = []
        self._detections: list[DetectionRecord] = []
        self._rejections: list[RejectionRecord] = []
        self._equity: list[EquityPoint] = []
        self._notes: list[str] = []
        self._realised: Decimal = ZERO
        self._realised_by_account: dict[str, Decimal] = {a.value: ZERO for a in Account}
        self._armed_plan_ids: set[str] = set()
        self._trade_seq = 0

    # -- setup ---------------------------------------------------------------

    def _default_warmup(self) -> int:
        """§12.1: discard ``max(level_lookback_bars, atr_period, bias_level_lookback_bars)`` bars.

        Those three keys belong to ``detectors/levels.py`` and ``detectors/structure.py``; the
        harness reads them only to size its own warm-up window, which §12.1 assigns to it.
        """
        cfg = self.config
        return max(int(cfg.level_lookback_bars), int(cfg.atr_period),
                   int(cfg.bias_level_lookback_bars))

    # -- main loop -----------------------------------------------------------

    def run(self) -> BacktestResult:
        """Walk every bar once, forward.  Returns the full :class:`BacktestResult`."""
        series = self.series
        n = len(series)
        cfg = self.config
        self._check_execution_tf()

        opens, highs, lows, closes = series.open, series.high, series.low, series.close
        warm = min(self.warmup_bars, n)
        self._log.add(0, series.timestamp(0), EventKind.WARMUP,
                      f"discarding the first {warm} bar(s) of warm-up before any analysis runs",
                      source_ids=("SPEC-12.1",), warmup_bars=warm, total_bars=n)

        for i in range(n):
            ts = series.timestamp(i)
            bar = (dec(opens[i]), dec(highs[i]), dec(lows[i]), dec(closes[i]))

            # 1. Orders resting from earlier bars act first.  Nothing armed on bar i can be filled
            #    by bar i: the plan did not exist until that bar had closed.
            self._process_open_trades(i, ts, bar)

            # 2. Then the pipeline sees bars 0..i and may publish new plans.
            if i >= warm:
                window = BarWindow.at(series, i, self.context)
                output = _coerce_pipeline_output(self.provider(window, cfg))
                if self.audit_outputs:
                    assert_no_future_reference(output.plans, i, path="pipeline.plans")
                    assert_no_future_reference(output.setups, i, path="pipeline.setups")
                    assert_no_future_reference(output.detections, i, path="pipeline.detections")
                self._record_analysis(i, ts, output)

            # 3. Mark to market at the close of the bar.
            self._mark(i, ts, bar[3])

        self._finish(n - 1)
        return self._result(n)

    def _check_execution_tf(self) -> None:
        """A14 — say so, loudly, when the series is coarser than ``backtest_execution_tf``."""
        wanted = self.config.backtest_execution_tf
        if wanted in ("trade_tf", "structure_tf"):
            return
        try:
            target = Timeframe.parse(wanted)
        except Exception:
            return
        if target.rank < self.series.tf.rank:
            note = (
                f"execution timeframe: config asks for {target.value} but the series is "
                f"{self.series.tf.value}; fills are simulated on {self.series.tf.value} bars, so "
                f"intrabar sequencing is arbitrated entirely by assumptions A1/A2/A10 (§12.2)"
            )
            self._notes.append(note)
            self._log.add(0, self.series.timestamp(0), EventKind.NOTE, note,
                          source_ids=("SPEC-12.1", "SPEC-12.2-A10", "SPEC-12.2-A14"))

    # -- analysis side -------------------------------------------------------

    def _record_analysis(self, i: int, ts: datetime, output: PipelineOutput) -> None:
        for detection in output.detections:
            self._detections.append(detection)
            self._log.add(i, ts, EventKind.DETECTION,
                          f"{detection.detector} emitted {detection.object_id} "
                          f"({detection.obj_class})",
                          source_ids=detection.source_ids, detector=detection.detector,
                          object_id=detection.object_id, obj_class=detection.obj_class)

        rejections = list(output.rejections)
        for setup in output.setups:
            if setup.vetoes:
                # §7.1: the first veto stops evaluation, so it is the gate that shaped the outcome.
                rejections.append(RejectionRecord(
                    bar_index=i, setup_id=setup.id, gate=str(setup.vetoes[0]).split(":")[0],
                    reason=str(setup.vetoes[0]), symbol=setup.symbol, direction=setup.direction,
                    source_ids=setup.source_ids,
                ))
        for rejection in rejections:
            self._rejections.append(rejection)
            self._log.add(i, ts, EventKind.REJECTION,
                          f"setup {rejection.setup_id} rejected at gate {rejection.gate}: "
                          f"{rejection.reason}",
                          setup_id=rejection.setup_id, source_ids=rejection.source_ids,
                          gate=rejection.gate, reason=rejection.reason)

        setups_by_id = {s.id: s for s in output.setups}
        for plan in output.plans:
            if plan.id in self._armed_plan_ids:
                continue
            self._arm(i, ts, plan, setups_by_id.get(plan.setup_id))

    def _arm(self, i: int, ts: datetime, plan: TradePlan, setup: Setup | None) -> None:
        self._armed_plan_ids.add(plan.id)
        self._trade_seq += 1
        ref = f"T{self._trade_seq:04d}"
        trade_id = f"{plan.symbol}:{self.series.tf.value}:trade:{i}:{self._trade_seq}"
        family = EntryFamily(setup.entry_family) if setup is not None else EntryFamily.RETEST
        account = _account_for(plan, setup)
        position = Position(
            id=f"{trade_id}:pos", plan_id=plan.id, account=account, state=PositionState.ARMED,
            current_stop=plan.stop_price,
            touch_index_at_entry=int((setup.regime_flags.get("touch_index", 1) if setup else 1) or 1),
        )
        trade = _LiveTrade(
            id=trade_id, ref=ref, plan=plan, setup=setup, account=account, entry_family=family,
            position=position, armed_index=i, initial_stop=plan.stop_price,
            pending_trigger=family is EntryFamily.TRIGGER,
            tp_hit_flags=[False] * len(plan.take_profits),
        )
        self._live.append(trade)

        self._log.add(i, ts, EventKind.PLAN,
                      f"plan {plan.id}: {plan.direction.value} {plan.symbol} "
                      f"{plan.trade_class.value}/{plan.vehicle.value}, "
                      f"{len(plan.entries)} rung(s), stop {plan.stop_price}, "
                      f"{len(plan.take_profits)} TP(s), "
                      f"R:R {plan.rr_to_final_tp} to the final TP (F9)",
                      trade_id=trade_id, trade_ref=ref, plan_id=plan.id, setup_id=plan.setup_id,
                      source_ids=plan.source_ids)
        self._log.add(i, ts, EventKind.ARM,
                      f"armed ({family.value} family, account {account.value}); "
                      f"orders are workable from bar {i + 1}",
                      trade_id=trade_id, trade_ref=ref, plan_id=plan.id, setup_id=plan.setup_id,
                      source_ids=("CF-16", "SPEC-9.2") + plan.source_ids)

    # -- execution side ------------------------------------------------------

    def _process_open_trades(self, i: int, ts: datetime,
                             bar: tuple[Decimal, Decimal, Decimal, Decimal]) -> None:
        open_, high, low, close = bar
        for trade in list(self._live):
            if trade.armed_index >= i:
                continue  # armed at the close of this bar or later: not workable yet
            self._accrue_funding(trade, i, ts)

            # A5 — trigger entries fill at the next bar's open.
            if trade.pending_trigger:
                self._fill_trigger_entries(trade, i, ts, open_)

            # A2/A3/A4 — resting limits.
            if trade.position.state in (PositionState.ARMED, PositionState.PARTIAL):
                self._fill_limit_rungs(trade, i, ts, high, low)

            # Expiry of an untouched plan (CF-15 / CF-22).
            if (trade.position.state is PositionState.ARMED
                    and trade.plan.expires_at_index is not None
                    and i >= trade.plan.expires_at_index):
                self._close_unfilled(trade, i, ts, PositionState.EXPIRED,
                                     "expired without a fill", ("CF-15", "CF-22", "SPEC-9.2"))
                continue

            if trade.position.qty_open <= _QTY_DUST:
                continue

            trade.position.bars_in_trade += 1
            self._update_excursions(trade, i, high, low)

            # A1 — the stop is tested before any take-profit.
            if self._stop_hit(trade, i, ts, open_, high, low):
                continue
            # Then the take-profit ladder, with A13 re-testing the trailed stop in the same bar.
            self._take_profits(trade, i, ts, open_, high, low)
            if trade.position.qty_open > _QTY_DUST:
                self._check_liquidation(trade, i, ts, close)

    def _fill_trigger_entries(self, trade: _LiveTrade, i: int, ts: datetime,
                              open_: Decimal) -> None:
        """A5 — every rung of a trigger-family plan enters at this bar's open, taker, adverse."""
        trade.pending_trigger = False
        side = "buy" if trade.plan.direction is Direction.LONG else "sell"
        price = _slip(open_, dec(self.config.slippage_market_bps), side)
        for rung in trade.plan.entries:
            if rung.filled:
                continue
            qty = trade.plan.qty_total * rung.size_fraction
            if qty <= ZERO:
                continue
            self._book_entry(trade, rung, i, ts, price, qty, OrderType.MARKET,
                             dec(self.config.fee_taker_bps), dec(self.config.slippage_market_bps),
                             ("SPEC-12.2-A5", "CF-16"))

    def _fill_limit_rungs(self, trade: _LiveTrade, i: int, ts: datetime,
                          high: Decimal, low: Decimal) -> None:
        """A3/A4 — a resting limit needs a strict trade-through and fills at its own price."""
        through = bool(self.config.limit_fill_requires_trade_through)
        long = trade.plan.direction is Direction.LONG
        for rung in trade.plan.entries:
            if rung.filled:
                continue
            price = rung.price
            hit = (low < price if through else low <= price) if long else (
                high > price if through else high >= price)
            if not hit:
                continue
            qty = trade.plan.qty_total * rung.size_fraction
            if qty <= ZERO:
                continue
            self._book_entry(trade, rung, i, ts, price, qty, OrderType.LIMIT,
                             dec(self.config.fee_maker_bps), dec(self.config.slippage_limit_bps),
                             ("SPEC-12.2-A3", "SPEC-12.2-A4", "CF-18"))

    def _book_entry(self, trade: _LiveTrade, rung: EntryRung, i: int, ts: datetime,
                    price: Decimal, qty: Decimal, order_type: OrderType, fee_bps: Decimal,
                    slip_bps: Decimal, source_ids: tuple[str, ...]) -> None:
        fee = _fee(price, qty, fee_bps)
        rung.filled = True
        rung.fill_index = i
        rung.fill_price = price
        trade.entry_notional += price * qty
        trade.entry_qty += qty
        trade.filled_qty_total += qty
        trade.fees_usd += fee
        pos = trade.position
        # The entry fee is realised the moment it is paid (§12.3: fees are charged inside the P&L).
        pos.realised_pnl_usd -= fee
        self._realised -= fee
        self._realised_by_account[trade.account.value] -= fee
        pos.qty_open += qty
        pos.average_entry = trade.entry_notional / trade.entry_qty
        if pos.opened_index is None:
            pos.opened_index = i
        fill = self._record_fill(trade, i, ts, FillKind.DCA if rung.kind == "dca" else FillKind.ENTRY,
                                 price, qty, order_type, fee, slip_bps)
        was = pos.state
        all_filled = all(r.filled for r in trade.plan.entries)
        pos.state = PositionState.OPEN if all_filled else PositionState.PARTIAL
        self._log.add(i, ts, EventKind.FILL,
                      f"rung {rung.index} ({rung.kind}) filled {qty} @ {price} "
                      f"[{order_type.value}, fee {fee:.4f}]; average entry now {pos.average_entry}",
                      trade_id=trade.id, trade_ref=trade.ref, plan_id=trade.plan.id,
                      setup_id=trade.plan.setup_id,
                      source_ids=source_ids + trade.plan.source_ids,
                      rung=rung.index, price=str(price), qty=str(qty), fee_usd=str(fee),
                      fill_id=fill.id)
        if pos.state is not was:
            self._transition(trade, i, ts, was, pos.state,
                             "ladder complete" if all_filled else "first rung filled",
                             ("CF-18", "SPEC-9.2"))

    def _stop_hit(self, trade: _LiveTrade, i: int, ts: datetime, open_: Decimal,
                  high: Decimal, low: Decimal) -> bool:
        """A1/A2/A6 — the stop is tested first and fills at the worse of stop and open."""
        pos = trade.position
        stop = pos.current_stop
        long = trade.plan.direction is Direction.LONG
        if long and low > stop:
            return False
        if not long and high < stop:
            return False
        raw = min(stop, open_) if long else max(stop, open_)
        gapped = raw != stop
        price = _slip(raw, dec(self.config.slippage_market_bps), "sell" if long else "buy")
        reason = CloseReason.TRAIL_OUT if pos.tps_hit > 0 else CloseReason.STOP
        rule = ("CF-29", "SPEC-9.2") if pos.tps_hit > 0 else ("CF-14", "SPEC-9.2")
        self._close_out(trade, i, ts, price, pos.qty_open, reason, OrderType.MARKET,
                        dec(self.config.fee_taker_bps), dec(self.config.slippage_market_bps),
                        ("SPEC-12.2-A1", "SPEC-12.2-A2", "SPEC-12.2-A6") + rule,
                        detail=(f"stop {stop} hit{' on a gap through the open' if gapped else ''}, "
                                f"filled {price}"))
        return True

    def _take_profits(self, trade: _LiveTrade, i: int, ts: datetime, open_: Decimal,
                      high: Decimal, low: Decimal) -> None:
        """§9.2/§9.3 TP ladder with CF-29 trailing; A13 re-tests the trailed stop in-bar."""
        pos = trade.position
        plan = trade.plan
        long = plan.direction is Direction.LONG
        through = bool(self.config.limit_fill_requires_trade_through)
        base_qty = trade.filled_qty_total
        for n, tp in enumerate(plan.take_profits):
            if trade.tp_hit_flags[n] or pos.qty_open <= _QTY_DUST:
                continue
            hit = (high > tp.price if through else high >= tp.price) if long else (
                low < tp.price if through else low <= tp.price)
            if not hit:
                continue
            qty = min(base_qty * tp.size_fraction, pos.qty_open)
            final = n == len(plan.take_profits) - 1
            if final:
                qty = pos.qty_open  # CF-28: nothing is left dangling at the top of the ladder
            if qty <= ZERO:
                continue
            trade.tp_hit_flags[n] = True
            tp.hit = True
            tp.hit_index = i
            pos.tps_hit += 1
            reason = CloseReason.TP_FINAL if final else None
            self._partial_exit(trade, i, ts, tp.price, qty, FillKind.TP, OrderType.LIMIT,
                               dec(self.config.fee_maker_bps), dec(self.config.slippage_limit_bps),
                               ("SPEC-12.2-A4", "CF-27", "CF-28"),
                               f"TP{tp.index} hit at {tp.price}, closed {qty}")
            if pos.qty_open <= _QTY_DUST:
                self._finalise(trade, i, ts, reason or CloseReason.TP_FINAL,
                               ("CF-28", "SPEC-9.2"))
                return
            # CF-29 / S4-R11 / S5-R27 trailing ladder.
            new_stop = (pos.average_entry if n == 0 else plan.take_profits[n - 1].price)
            label = "break-even at average entry" if n == 0 else f"TP{n}'s price"
            was = pos.state
            pos.state = PositionState.MANAGING
            pos.current_stop = new_stop
            pos.stop_reason = f"trail_after_tp{n + 1}"
            self._transition(trade, i, ts, was, pos.state,
                             f"TP{n + 1} hit; stop trailed to {label} ({new_stop})",
                             ("CF-29", "S4-R11", "S5-R27", "CF-18"))
            # A13 — the trailed stop is live for the rest of this bar.
            if self._stop_hit(trade, i, ts, open_, high, low):
                return

    def _partial_exit(self, trade: _LiveTrade, i: int, ts: datetime, price: Decimal, qty: Decimal,
                      kind: FillKind, order_type: OrderType, fee_bps: Decimal, slip_bps: Decimal,
                      source_ids: tuple[str, ...], detail: str,
                      excess_risk: Decimal = ZERO) -> None:
        pos = trade.position
        fee = _fee(price, qty, fee_bps)
        sign = Decimal(trade.plan.direction.sign)
        gross = (price - pos.average_entry) * qty * sign
        trade.fees_usd += fee
        trade.excess_risk_usd += excess_risk
        trade.exit_notional += price * qty
        trade.exit_qty += qty
        pos.qty_open -= qty
        if pos.qty_open < _QTY_DUST:
            pos.qty_open = ZERO
        realised = gross - fee
        pos.realised_pnl_usd += realised
        self._realised += realised
        self._realised_by_account[trade.account.value] += realised
        fill = self._record_fill(trade, i, ts, kind, price, qty, order_type, fee, slip_bps,
                                 excess_risk)
        self._log.add(i, ts, EventKind.FILL,
                      f"{detail} [{order_type.value}, fee {fee:.4f}, gross {gross:.4f}]",
                      trade_id=trade.id, trade_ref=trade.ref, plan_id=trade.plan.id,
                      setup_id=trade.plan.setup_id,
                      source_ids=source_ids + trade.plan.source_ids,
                      price=str(price), qty=str(qty), fee_usd=str(fee), gross_pnl=str(gross),
                      fill_id=fill.id)

    def _close_out(self, trade: _LiveTrade, i: int, ts: datetime, price: Decimal, qty: Decimal,
                   reason: CloseReason, order_type: OrderType, fee_bps: Decimal,
                   slip_bps: Decimal, source_ids: tuple[str, ...], detail: str,
                   excess_risk: Decimal = ZERO) -> None:
        self._partial_exit(trade, i, ts, price, qty, FillKind.STOP if reason is CloseReason.STOP
                           else FillKind.EXIT, order_type, fee_bps, slip_bps, source_ids, detail,
                           excess_risk)
        self._finalise(trade, i, ts, reason, source_ids)

    def _record_fill(self, trade: _LiveTrade, i: int, ts: datetime, kind: FillKind,
                     price: Decimal, qty: Decimal, order_type: OrderType, fee: Decimal,
                     slip_bps: Decimal, excess_risk: Decimal = ZERO) -> Fill:
        trade.fill_seq += 1
        fill = Fill(id=f"{trade.id}:fill:{trade.fill_seq}", position_id=trade.position.id,
                    kind=kind, bar_index=i, timestamp=ts, price=price, qty=qty,
                    order_type=order_type, fee_usd=fee, slippage_bps=slip_bps,
                    excess_risk_usd=excess_risk)
        trade.fills.append(fill)
        return fill

    def _transition(self, trade: _LiveTrade, i: int, ts: datetime, was: PositionState,
                    now: PositionState, why: str, source_ids: tuple[str, ...]) -> None:
        self._log.add(i, ts, EventKind.TRANSITION,
                      f"{was.value} -> {now.value}: {why}",
                      trade_id=trade.id, trade_ref=trade.ref, plan_id=trade.plan.id,
                      setup_id=trade.plan.setup_id,
                      source_ids=source_ids + trade.plan.source_ids,
                      from_state=was.value, to_state=now.value)

    def _close_unfilled(self, trade: _LiveTrade, i: int, ts: datetime, state: PositionState,
                        why: str, source_ids: tuple[str, ...]) -> None:
        """An armed plan that never got a fill leaves no trade — only an event."""
        was = trade.position.state
        trade.position.state = state
        trade.position.closed_index = i
        self._transition(trade, i, ts, was, state, why, source_ids)
        self._live.remove(trade)

    def _finalise(self, trade: _LiveTrade, i: int, ts: datetime, reason: CloseReason,
                  source_ids: tuple[str, ...]) -> None:
        pos = trade.position
        was = pos.state
        pos.state = PositionState.CLOSED
        pos.closed_index = i
        pos.close_reason = reason
        pos.qty_open = ZERO
        plan = trade.plan
        # R is measured from ``average_entry`` against the **initial** stop (CF-42, CF-18).
        risk_per_unit = abs(pos.average_entry - trade.initial_stop)
        initial_risk = risk_per_unit * trade.filled_qty_total
        net = pos.realised_pnl_usd - trade.funding_usd
        r_multiple = (net / initial_risk) if initial_risk > ZERO else ZERO
        pos.r_multiple = r_multiple
        gross = net + trade.fees_usd + trade.funding_usd
        setup = trade.setup
        opened = pos.opened_index if pos.opened_index is not None else i
        closed_trade = ClosedTrade(
            id=trade.id, ref=trade.ref, plan_id=plan.id, setup_id=plan.setup_id,
            symbol=plan.symbol, tf=self.series.tf, direction=plan.direction,
            trade_class=plan.trade_class, vehicle=plan.vehicle,
            conviction=setup.conviction if setup is not None else Conviction.NORMAL,
            entry_family=trade.entry_family, account=trade.account,
            primary_class=self._primary_class(setup),
            confluence_classes=tuple(sorted(setup.confluence_classes)) if setup is not None else (),
            source_ids=tuple(plan.source_ids),
            opened_index=opened, closed_index=i,
            opened_at=self.series.timestamp(opened), closed_at=ts,
            bars_in_trade=pos.bars_in_trade, qty=trade.filled_qty_total,
            average_entry=pos.average_entry, planned_average_entry=plan.planned_average_entry,
            initial_stop=trade.initial_stop,
            exit_price=(trade.exit_notional / trade.exit_qty) if trade.exit_qty > ZERO else ZERO,
            gross_pnl_usd=gross, fees_usd=trade.fees_usd, funding_usd=trade.funding_usd,
            net_pnl_usd=net, initial_risk_usd=initial_risk, r_multiple=r_multiple,
            close_reason=reason, tps_hit=pos.tps_hit, tp_count=len(plan.take_profits),
            rungs_planned=len(plan.entries),
            rungs_filled=sum(1 for r in plan.entries if r.filled),
            rung_fill_flags=tuple(r.filled for r in plan.entries),
            touch_index_at_entry=pos.touch_index_at_entry,
            excess_risk_usd=trade.excess_risk_usd, liquidated=trade.liquidated,
            fills=tuple(trade.fills),
        )
        self._closed.append(closed_trade)
        self._transition(trade, i, ts, was, PositionState.CLOSED,
                         f"closed ({reason.value}), net {net:.4f} USD, {r_multiple:.3f}R",
                         source_ids)
        self._log.add(i, ts, EventKind.EXIT,
                      f"closed {reason.value}: net {net:.4f} USD ({r_multiple:.3f}R), "
                      f"fees {trade.fees_usd:.4f}, funding {trade.funding_usd:.4f}, "
                      f"{pos.tps_hit}/{len(plan.take_profits)} TP(s), "
                      f"{closed_trade.rungs_filled}/{closed_trade.rungs_planned} rung(s)",
                      trade_id=trade.id, trade_ref=trade.ref, plan_id=plan.id,
                      setup_id=plan.setup_id,
                      source_ids=source_ids + plan.source_ids,
                      close_reason=reason.value, net_pnl_usd=str(net), r_multiple=str(r_multiple))
        if trade in self._live:
            self._live.remove(trade)

    @staticmethod
    def _primary_class(setup: Setup | None) -> str:
        """The detector class a trade is attributed to (§12.4 per-detector attribution)."""
        if setup is None:
            return "unattributed"
        primary = setup.regime_flags.get("primary_class")
        if isinstance(primary, str) and primary:
            return primary
        if setup.confluence_classes:
            return sorted(setup.confluence_classes)[0]
        return "unattributed"

    # -- per-bar bookkeeping -------------------------------------------------

    def _update_excursions(self, trade: _LiveTrade, i: int, high: Decimal, low: Decimal) -> None:
        atr = self._atr_at(i)
        if atr <= ZERO:
            return
        pos = trade.position
        long = trade.plan.direction is Direction.LONG
        favourable = (high - pos.average_entry) if long else (pos.average_entry - low)
        adverse = (pos.average_entry - low) if long else (high - pos.average_entry)
        pos.mfe_atr = max(pos.mfe_atr, favourable / atr)
        pos.mae_atr = max(pos.mae_atr, adverse / atr)

    def _atr_at(self, i: int) -> Decimal:
        """ATR(atr_period) at bar ``i``.

        Wilder ATR is *causal* — the value at bar ``i`` depends only on bars ``0..i`` — so the
        array may be computed once over the whole series without lookahead.  ``test_engine.py``
        asserts that equivalence rather than assuming it.
        """
        if not hasattr(self, "_atr_cache"):
            import tbot.primitives as P  # lazy: keeps import order flat

            self._atr_cache = P.atr_array(self.series, int(self.config.atr_period))  # type: ignore[attr-defined]
        return dec(float(self._atr_cache[i]))  # type: ignore[attr-defined]

    def _accrue_funding(self, trade: _LiveTrade, i: int, ts: datetime) -> None:
        """A11 — leverage only, charged at the 8-hourly boundaries anchored on ``day_boundary_utc``."""
        if trade.plan.vehicle is not Vehicle.LEVERAGE:
            return
        if trade.position.qty_open <= _QTY_DUST:
            trade.last_funding_ts = ts
            return
        previous = trade.last_funding_ts
        trade.last_funding_ts = ts
        if previous is None:
            return
        periods = _funding_periods_between(previous, ts, self.config)
        if periods <= 0:
            return
        notional = abs(trade.position.average_entry * trade.position.qty_open)
        charge = notional * dec(self.config.funding_bps_per_8h) / BPS * Decimal(periods)
        if charge <= ZERO:
            return
        trade.funding_usd += charge
        self._realised -= charge
        self._realised_by_account[trade.account.value] -= charge
        self._log.add(i, ts, EventKind.FUNDING,
                      f"funding charged {charge:.6f} USD over {periods} 8h period(s) on "
                      f"{notional:.2f} notional",
                      trade_id=trade.id, trade_ref=trade.ref, plan_id=trade.plan.id,
                      source_ids=("SPEC-12.2-A11", "SPEC-12.3"), charge_usd=str(charge),
                      periods=periods)

    def _check_liquidation(self, trade: _LiveTrade, i: int, ts: datetime, close: Decimal) -> None:
        """A12 — this should never fire.  If it does it is a sizing bug, and it is flagged as one."""
        pos = trade.position
        sign = Decimal(trade.plan.direction.sign)
        unrealised = (close - pos.average_entry) * pos.qty_open * sign
        equity = self.starting_equity + self._realised
        if unrealised >= ZERO or -unrealised < equity:
            return
        trade.liquidated = True
        self._log.add(i, ts, EventKind.LIQUIDATION,
                      f"LIQUIDATION: open loss {(-unrealised):.2f} USD exceeds equity "
                      f"{equity:.2f}. Per §12.2 A12 this is a §8.8 sizing bug, not a result.",
                      trade_id=trade.id, trade_ref=trade.ref, plan_id=trade.plan.id,
                      source_ids=("SPEC-12.2-A12",))
        price = _slip(close, dec(self.config.slippage_market_bps),
                      "sell" if trade.plan.direction is Direction.LONG else "buy")
        self._close_out(trade, i, ts, price, pos.qty_open, CloseReason.STOP, OrderType.MARKET,
                        dec(self.config.fee_taker_bps), dec(self.config.slippage_market_bps),
                        ("SPEC-12.2-A12",), detail=f"force-closed at {price}")

    def _mark(self, i: int, ts: datetime, close: Decimal) -> None:
        unrealised = ZERO
        by_account = dict(self._realised_by_account)
        for trade in self._live:
            pos = trade.position
            if pos.qty_open <= _QTY_DUST:
                continue
            sign = Decimal(trade.plan.direction.sign)
            value = (close - pos.average_entry) * pos.qty_open * sign
            pos.unrealised_pnl_usd = value
            unrealised += value
            by_account[trade.account.value] = by_account.get(trade.account.value, ZERO) + value
        equity = self.starting_equity + self._realised + unrealised
        self._equity.append(EquityPoint(bar_index=i, timestamp=ts, equity=equity,
                                        realised=self._realised, unrealised=unrealised,
                                        by_account=by_account))

    def _finish(self, last_index: int) -> None:
        ts = self.series.timestamp(last_index)
        for trade in list(self._live):
            if trade.position.qty_open <= _QTY_DUST:
                self._close_unfilled(trade, last_index, ts, PositionState.CANCELLED,
                                     "data ended while still armed; no fill ever occurred",
                                     ("SPEC-12.1",))
            else:
                self._log.add(last_index, ts, EventKind.NOTE,
                              "still open when the data ended: marked to market and reported "
                              "separately, never counted as a closed trade",
                              trade_id=trade.id, trade_ref=trade.ref, plan_id=trade.plan.id,
                              source_ids=("SPEC-12.4",))

    def _result(self, n: int) -> BacktestResult:
        last_close = dec(self.series.close[n - 1])
        open_at_end = tuple(
            OpenTrade(id=t.id, ref=t.ref, plan_id=t.plan.id, symbol=t.plan.symbol,
                      direction=t.plan.direction, account=t.account,
                      opened_index=t.position.opened_index or t.armed_index,
                      qty=t.position.qty_open, average_entry=t.position.average_entry,
                      current_stop=t.position.current_stop, mark_price=last_close,
                      unrealised_pnl_usd=t.position.unrealised_pnl_usd, tps_hit=t.position.tps_hit)
            for t in self._live if t.position.qty_open > _QTY_DUST
        )
        notes = list(self._notes)
        if not self._detections and not self._closed:
            notes.append(
                "no plans were produced: the analysis pipeline (tbot.pipeline / detectors / "
                "qualification / planner) is not importable or emitted nothing. The harness ran "
                "the full bar loop regardless — an empty plan list is a valid result (PL-9)."
            )
        return BacktestResult(
            symbol=self.series.symbol, tf=self.series.tf, bars=n, warmup_bars=self.warmup_bars,
            start=self.series.timestamp(0), end=self.series.timestamp(n - 1),
            starting_equity=self.starting_equity,
            ending_equity=self._equity[-1].equity if self._equity else self.starting_equity,
            trades=tuple(self._closed), open_at_end=open_at_end, events=self._log,
            detections=tuple(self._detections), rejections=tuple(self._rejections),
            equity_curve=tuple(self._equity), config=self.config, notes=tuple(notes),
        )


def _funding_periods_between(previous: datetime, now: datetime, config: Config) -> int:
    """How many 8-hour funding boundaries fall in ``(previous, now]`` (P16, CF-45)."""
    import tbot.primitives as P  # lazy: foundation import kept out of module import time

    if now <= previous:
        return 0
    anchor = P.day_start(previous, config)
    step = timedelta(hours=8)
    boundary = anchor
    while boundary <= previous:
        boundary += step
    count = 0
    while boundary <= now:
        count += 1
        boundary += step
    return count


def run_backtest(series: Series, config: Config, *, plan_provider: PlanProvider | None = None,
                 starting_equity: Decimal | float = DEFAULT_STARTING_EQUITY,
                 warmup_bars: int | None = None) -> BacktestResult:
    """Convenience wrapper: build a :class:`BacktestEngine` and run it once."""
    return BacktestEngine(series, config, plan_provider=plan_provider,
                          starting_equity=starting_equity, warmup_bars=warmup_bars).run()


# --------------------------------------------------------------------------- §12 out-of-sample


class SplitError(ValueError):
    """Raised when a requested in-sample/out-of-sample split cannot be honoured."""


@dataclass(frozen=True, slots=True)
class SplitResult:
    """One series partitioned chronologically and run as **two independent backtests**.

    The two :class:`BacktestResult` objects are never merged and there is deliberately no
    combined metric on this class.  A single headline number across both segments is exactly
    the thing an out-of-sample split exists to prevent: it lets a fitted in-sample result
    carry an unfitted out-of-sample one, which is the error the split is meant to expose.
    Report them side by side or not at all.

    Both segments start from the same ``starting_equity``.  The out-of-sample run is *not*
    compounded onto the in-sample equity curve — they are two independent evaluations of the
    same parameter set, not one continuous account.
    """

    in_sample: BacktestResult
    out_of_sample: BacktestResult
    #: First bar index belonging to the out-of-sample segment.
    split_index: int
    in_sample_fraction: float

    @property
    def in_sample_bars(self) -> int:
        return self.split_index

    @property
    def out_of_sample_bars(self) -> int:
        return self.out_of_sample.bars - self.split_index


def split_backtest(
    series: Series,
    config: Config,
    *,
    plan_provider: PlanProvider | None = None,
    starting_equity: Decimal | float = DEFAULT_STARTING_EQUITY,
    warmup_bars: int | None = None,
    in_sample_fraction: float = DEFAULT_IN_SAMPLE_FRACTION,
) -> SplitResult:
    """Run ``series`` twice: once on the first ``in_sample_fraction``, once on the remainder.

    The split is **chronological** — the out-of-sample segment is strictly later than the
    in-sample one, which is the only split that means anything for a time series.

    How the out-of-sample run avoids both contamination and a cold start: it is handed the
    **whole** series with ``warmup_bars`` set to the split index.  The §12.1 loop already
    treats warm-up bars as history that detectors may look back over but on which no analysis
    runs (``engine.run``: ``if i >= warm``), so the out-of-sample segment gets the same warmed
    detector state a live run would have, while opening no trade before the split.  No bar
    ``> i`` is ever visible at bar ``i``, so the lookahead guarantee is unchanged.

    :raises SplitError: if the fraction is out of range, or either segment would contain no
        analysable bar once warm-up is accounted for.  Failing loudly beats silently reporting
        a segment that never ran.
    """
    if not 0.0 < in_sample_fraction < 1.0:
        raise SplitError(
            f"in_sample_fraction must lie strictly between 0 and 1, got {in_sample_fraction}")

    n = len(series)
    split = int(n * in_sample_fraction)

    # The in-sample engine decides the warm-up; ask it rather than re-deriving §12.1 here.
    in_engine = BacktestEngine(series.head(split) if split else series, config,
                               plan_provider=plan_provider, starting_equity=starting_equity,
                               warmup_bars=warmup_bars)
    warm = in_engine.warmup_bars

    if split <= warm:
        raise SplitError(
            f"in-sample segment is {split} bar(s) but warm-up alone needs {warm}: "
            f"nothing would be analysed. Use a longer series or a larger --split fraction.")
    if split >= n:
        raise SplitError(
            f"out-of-sample segment is empty (split index {split} of {n} bars)")

    out_engine = BacktestEngine(series, config, plan_provider=plan_provider,
                                starting_equity=starting_equity, warmup_bars=split)
    return SplitResult(
        in_sample=in_engine.run(),
        out_of_sample=out_engine.run(),
        split_index=split,
        in_sample_fraction=in_sample_fraction,
    )
