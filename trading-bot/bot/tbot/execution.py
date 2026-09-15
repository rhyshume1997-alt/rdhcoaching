"""tbot.execution — the SPEC.md §12.6 execution adapter.  Live trading is deliberately absent.

SPEC.md §1.9 and §12.6: **live order execution is out of scope for this build**.  There is no
exchange client here, no API key handling, no endpoint, no signing code and no place to put one.
That is a design decision, not an omission, and it is enforced structurally:

* :class:`ExecutionAdapter` is a :class:`~typing.Protocol` — a shape, with no behaviour.
* :class:`NullAdapter` implements every method by raising :class:`NotImplementedError` with a
  message saying live trading is intentionally not wired up.  It is the *live path*, and it is a
  wall.
* :class:`PaperAdapter` records intended orders in memory and sends nothing anywhere.  It is what
  you use to see what the system *would* have done.
* The third implementation named by §12.6, ``BacktestAdapter``, is
  :class:`tbot.backtest.engine.BacktestEngine` itself: the simulator owns order state internally
  because fills depend on the bar it is standing on, which no adapter interface can express.

If live trading is ever built, it belongs behind this protocol in a separate, separately reviewed
package — with its own credential handling, its own rate limiting, its own reconciliation and its
own kill switch.  Do not add it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence, runtime_checkable

from .models import Account, Direction, EntryRung, TakeProfit, TradePlan, dec

__all__ = [
    "ExecutionAdapter",
    "IntendedOrder",
    "PaperAdapter",
    "NullAdapter",
    "LIVE_TRADING_MESSAGE",
]

LIVE_TRADING_MESSAGE = (
    "live trading is intentionally not wired up in this build: SPEC.md §1.9 and §12.6 put order "
    "execution out of scope, and this package contains no exchange client, credentials or "
    "endpoints by design. Use PaperAdapter to record intended orders, or the backtest harness to "
    "simulate them."
)


@runtime_checkable
class ExecutionAdapter(Protocol):
    """SPEC.md §12.6 — **NOT IMPLEMENTED**.  Live order execution is out of scope for this build.

    The protocol exists so that plan construction and management can be written against a stable
    shape, and so that the absence of a live implementation is *visible in the type system* rather
    than discovered at runtime.  Every price and quantity is a :class:`~decimal.Decimal`
    (INTERFACES.md §1.3).
    """

    def place_limit(self, plan_id: str, rung: EntryRung) -> str:
        """Rest one ladder rung as a limit order.  Returns the venue order id."""
        ...

    def place_stop(self, plan_id: str, price: Decimal, qty: Decimal) -> str:
        """Place the plan's single stop (CF-14; the CF-05 duplicate is not simulated, A9)."""
        ...

    def place_take_profit(self, plan_id: str, tp: TakeProfit) -> str:
        """Place one take-profit leg of the §8.7 ladder."""
        ...

    def amend_stop(self, order_id: str, new_price: Decimal) -> None:
        """Move a resting stop — the CF-29 trailing ladder's only write operation."""
        ...

    def cancel(self, order_id: str) -> None:
        """Cancel one resting order (§9.2 ``ARMED -> CANCELLED``)."""
        ...

    def close_market(self, position_id: str, qty: Decimal) -> str:
        """Market-close ``qty`` of a position (structural-stale and MSB exits, CF-30, CF-22)."""
        ...

    def account_equity(self, account: str) -> Decimal:
        """Current equity for one §10.1 account, for the §10.2 risk budget."""
        ...


@dataclass(frozen=True, slots=True)
class IntendedOrder:
    """One order the system *would* have sent.  Recorded, never transmitted."""

    seq: int
    action: str          #: ``place_limit`` | ``place_stop`` | ``place_take_profit`` | ``amend_stop``
                         #: | ``cancel`` | ``close_market``
    order_id: str
    plan_id: str | None = None
    position_id: str | None = None
    price: Decimal | None = None
    qty: Decimal | None = None
    kind: str = ""
    note: str = ""

    def render(self) -> str:
        bits = [f"#{self.seq:03d}", self.action, self.order_id]
        if self.price is not None:
            bits.append(f"@ {self.price}")
        if self.qty is not None:
            bits.append(f"x {self.qty}")
        if self.note:
            bits.append(f"({self.note})")
        return "  ".join(bits)


class PaperAdapter:
    """Records intended orders in memory and sends nothing, anywhere.

    Deterministic by construction: order ids are ``paper-<n>`` from a per-instance counter, never
    ``uuid4`` and never a wall-clock read (INTERFACES.md §9.9).  ``account_equity`` returns the
    balance this adapter was constructed with — the paper book does not move with the market,
    because nothing here knows what the market did.  Satisfies :class:`ExecutionAdapter`.
    """

    __slots__ = ("_orders", "_seq", "_equity", "_cancelled")

    def __init__(self, equity: Decimal | float = 10_000.0) -> None:
        self._orders: list[IntendedOrder] = []
        self._seq = 0
        self._equity = dec(equity)
        self._cancelled: set[str] = set()

    # -- inspection -------------------------------------------------------

    @property
    def orders(self) -> tuple[IntendedOrder, ...]:
        """Every intended order, in the order it was requested."""
        return tuple(self._orders)

    def live_order_ids(self) -> tuple[str, ...]:
        """Ids that were placed and not subsequently cancelled."""
        placed = [o.order_id for o in self._orders if o.action.startswith("place")]
        return tuple(oid for oid in placed if oid not in self._cancelled)

    def render(self) -> str:
        return "\n".join(o.render() for o in self._orders)

    # -- the protocol -----------------------------------------------------

    def _record(self, action: str, *, plan_id: str | None = None, position_id: str | None = None,
                price: Decimal | None = None, qty: Decimal | None = None, kind: str = "",
                note: str = "", order_id: str | None = None) -> str:
        self._seq += 1
        oid = order_id or f"paper-{self._seq}"
        self._orders.append(IntendedOrder(seq=self._seq, action=action, order_id=oid,
                                          plan_id=plan_id, position_id=position_id, price=price,
                                          qty=qty, kind=kind, note=note))
        return oid

    def place_limit(self, plan_id: str, rung: EntryRung) -> str:
        return self._record("place_limit", plan_id=plan_id, price=rung.price,
                            qty=rung.size_fraction, kind=rung.kind,
                            note=f"rung {rung.index} on level {rung.level_id}")

    def place_stop(self, plan_id: str, price: Decimal, qty: Decimal) -> str:
        return self._record("place_stop", plan_id=plan_id, price=price, qty=qty, kind="stop",
                            note="one stop per plan (CF-14, A9)")

    def place_take_profit(self, plan_id: str, tp: TakeProfit) -> str:
        return self._record("place_take_profit", plan_id=plan_id, price=tp.price,
                            qty=tp.size_fraction, kind="tp", note=f"TP{tp.index}")

    def amend_stop(self, order_id: str, new_price: Decimal) -> None:
        self._record("amend_stop", price=new_price, order_id=order_id, kind="stop",
                     note="CF-29 trail")

    def cancel(self, order_id: str) -> None:
        self._cancelled.add(order_id)
        self._record("cancel", order_id=order_id)

    def close_market(self, position_id: str, qty: Decimal) -> str:
        return self._record("close_market", position_id=position_id, qty=qty, kind="exit")

    def account_equity(self, account: str) -> Decimal:
        return self._equity


class NullAdapter:
    """The live path.  Every method raises :class:`NotImplementedError`, on purpose.

    SPEC.md §12.6 names this adapter explicitly.  It exists so that wiring a live venue is an
    obvious, deliberate act rather than something that can happen by accident: any code path that
    tries to send a real order gets a loud, specific refusal instead of a silent no-op.
    """

    __slots__ = ()

    @staticmethod
    def _refuse(method: str) -> NotImplementedError:
        return NotImplementedError(f"{method}: {LIVE_TRADING_MESSAGE}")

    def place_limit(self, plan_id: str, rung: EntryRung) -> str:
        raise self._refuse("place_limit")

    def place_stop(self, plan_id: str, price: Decimal, qty: Decimal) -> str:
        raise self._refuse("place_stop")

    def place_take_profit(self, plan_id: str, tp: TakeProfit) -> str:
        raise self._refuse("place_take_profit")

    def amend_stop(self, order_id: str, new_price: Decimal) -> None:
        raise self._refuse("amend_stop")

    def cancel(self, order_id: str) -> None:
        raise self._refuse("cancel")

    def close_market(self, position_id: str, qty: Decimal) -> str:
        raise self._refuse("close_market")

    def account_equity(self, account: str) -> Decimal:
        raise self._refuse("account_equity")
