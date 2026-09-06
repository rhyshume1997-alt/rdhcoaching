"""tbot.risk — SPEC.md §10, the risk and portfolio layer.

This module is **pure**.  It never reads a clock, never touches a file and never mutates anything
it is given: portfolio state arrives as a :class:`PortfolioState` snapshot and every function
returns a fresh value object.  It is the leaf of the plan/manage/risk trio — :mod:`tbot.plan` and
:mod:`tbot.manage` import from here, never the other way round.

What lives here (and only here — INTERFACES.md §7 key ownership):

* the CF-01 per-trade risk ladder by trade class (swing / scalp / counter-trend / low conviction)
  and the high-conviction escalation switch;
* the CF-02 notional ceilings, the Q8 margin ceiling and the portfolio-wide spot deployment cap;
* the CF-07 touch-count size decay and the multiplicative composition of §10.8;
* the CF-04 concurrency caps, leverage and spot counted separately;
* the CF-44 daily-loss halt, the compounding challenge goal with stop-on-goal, and the **hard**
  prohibition on ratcheting risk up after a winning streak (S2-R24);
* the S2-R16/R17/R19 allocation buckets for the ``long_term`` book, and the CF-43 account-scoped
  cut rules.

Keys read here that other modules must receive as *arguments* rather than re-read:
``counter_trend_size_multiplier`` and ``bvol_size_multiplier`` are owned by ``qualification.py``
(INTERFACES.md §7), so :func:`compose_size_multipliers` takes them as an ``extra`` sequence.

Money comparisons never use ``==`` on floats.  Everything is :class:`~decimal.Decimal` and the
tolerance helpers :func:`money_close`, :func:`money_ge` and :func:`money_le` are the sanctioned
way to compare two amounts.  They are re-exported by :mod:`tbot.plan` and :mod:`tbot.manage`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Literal, Mapping, Sequence

import tbot.primitives as P
from tbot.config import Config
from tbot.models import (
    Account,
    Conviction,
    PositionState,
    TradeClass,
    Vehicle,
    dec,
)

__all__ = [
    "MONEY_ABS_TOL",
    "MONEY_REL_TOL",
    "money_close",
    "money_ge",
    "money_le",
    "ZERO",
    "ONE",
    "HUNDRED",
    "McapBucket",
    "Gate",
    "OpenSlot",
    "ClosedTrade",
    "PortfolioState",
    "SizingBudget",
    "RiskDecision",
    "AllocationReport",
    "per_trade_risk_pct",
    "touch_decay",
    "compose_size_multipliers",
    "margin_ceiling_usd",
    "notional_ceiling_usd",
    "loss_budget_usd",
    "sizing_budget",
    "concurrency_gate",
    "spot_deployment_gate",
    "is_loss",
    "losses_today",
    "daily_loss_gate",
    "win_streak",
    "ratchet_gate",
    "clamp_requested_risk_pct",
    "challenge_period_goal_usd",
    "next_period_goal_usd",
    "challenge_gate",
    "allocation_targets",
    "allocation_report",
    "allocation_gate",
    "cut_on_level_loss_applies",
    "long_term_exit_mode",
    "derisk_action",
    "spot_rotation_due",
    "hedge_size",
    "equity_restart_target",
    "approve_trade",
]


# --------------------------------------------------------------------------- numerics

ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)

#: Absolute tolerance for money/price equality.  Prices and USD amounts are Decimals with plenty
#: of significant digits; this catches the last-bit dust left by division, never a real
#: difference.  **[OUR CHOICE]** — no spec number exists for a comparison epsilon.
MONEY_ABS_TOL = Decimal("1e-12")
#: Relative tolerance, applied to the larger of the two magnitudes.  **[OUR CHOICE]**
MONEY_REL_TOL = Decimal("1e-12")


def money_close(
    a: Decimal | float | int,
    b: Decimal | float | int,
    *,
    abs_tol: Decimal = MONEY_ABS_TOL,
    rel_tol: Decimal = MONEY_REL_TOL,
) -> bool:
    """``True`` when two money/price amounts are equal to within tolerance.

    The **only** sanctioned way to compare two amounts for equality anywhere in
    :mod:`tbot.plan`, :mod:`tbot.manage` or this module.  Never write ``a == b`` on a price.
    """
    x, y = dec(a), dec(b)
    diff = abs(x - y)
    if diff <= abs_tol:
        return True
    scale = max(abs(x), abs(y))
    return diff <= rel_tol * scale


def money_ge(a: Decimal | float | int, b: Decimal | float | int, **kw: Decimal) -> bool:
    """``a >= b`` up to :func:`money_close` tolerance."""
    return dec(a) >= dec(b) or money_close(a, b, **kw)


def money_le(a: Decimal | float | int, b: Decimal | float | int, **kw: Decimal) -> bool:
    """``a <= b`` up to :func:`money_close` tolerance."""
    return dec(a) <= dec(b) or money_close(a, b, **kw)


# --------------------------------------------------------------------------- state objects

#: SPEC.md §10.6 bucket definitions (S2 §2): large = top 50, mid = 50-100, small = newer names
#: with fundamentals, micro = memecoins.  ``futures`` and ``cash`` are the two non-coin sleeves.
McapBucket = Literal["large", "mid", "small", "micro", "futures", "cash"]

_LEVERAGE_ACCOUNTS = (Account.LEVERAGE_SWING, Account.LEVERAGE_SCALP)


@dataclass(frozen=True, slots=True)
class Gate:
    """One §10 gate verdict.  ``reasons`` are propagated into ``Setup.vetoes`` verbatim."""

    name: str
    allowed: bool
    reasons: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.allowed


@dataclass(frozen=True, slots=True)
class OpenSlot:
    """One live position as the risk layer sees it.

    ``Position`` itself carries neither vehicle nor trade class, so the caller pairs the two.
    Only ``PARTIAL``/``OPEN``/``MANAGING`` count against the CF-04 caps (SPEC.md §9.1).
    """

    position_id: str
    account: Account
    vehicle: Vehicle
    trade_class: TradeClass
    state: PositionState
    notional_usd: Decimal = ZERO
    symbol: str = ""
    mcap_bucket: McapBucket = "large"

    @property
    def is_live(self) -> bool:
        return self.state in (PositionState.PARTIAL, PositionState.OPEN, PositionState.MANAGING)


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    """A settled trade, for the CF-44 daily-loss counter and the win-streak check.

    ``pnl_usd`` is **net of fees** so it matches
    ``loss_definition = "closed_below_average_entry_net_fees"`` directly.
    """

    trade_id: str
    account: Account
    closed_at: datetime
    pnl_usd: Decimal
    was_stop_out: bool = False


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Immutable snapshot handed to every gate.  The risk layer owns no state of its own."""

    equity_usd: Decimal
    now: datetime
    open_slots: tuple[OpenSlot, ...] = ()
    closed_trades: tuple[ClosedTrade, ...] = ()
    #: Balance at the start of the current challenge period; the compounding base (S2-R23).
    period_start_balance_usd: Decimal | None = None
    #: Realised P&L inside the current challenge period (S2-R22 stop-on-goal).
    period_realised_pnl_usd: Decimal = ZERO
    #: Free cash, for the ``alloc_cash_min_pct`` floor (S2-R17, a floor per S2-C5).
    cash_usd: Decimal | None = None
    #: The risk-per-trade actually used most recently, per trade class.  The ratchet baseline.
    baseline_risk_pct: Mapping[str, Decimal] = field(default_factory=dict)

    def live_slots(self) -> tuple[OpenSlot, ...]:
        return tuple(s for s in self.open_slots if s.is_live)


@dataclass(frozen=True, slots=True)
class SizingBudget:
    """Everything :func:`tbot.plan.solve_size` needs, and nothing it may read from config itself."""

    equity_usd: Decimal
    risk_budget_pct: Decimal        #: the CF-01 cap actually applied
    loss_budget_usd: Decimal        #: ``risk_budget_pct / 100 * equity``
    size_multiplier: Decimal        #: composed §10.8 multipliers, applied to quantity
    notional_ceiling_usd: Decimal   #: CF-02 ceiling, after the portfolio-wide spot cap
    source_ids: tuple[str, ...] = ()

    @property
    def target_loss_usd(self) -> Decimal:
        """The loss a full stop-out is *intended* to produce, multipliers included."""
        return self.loss_budget_usd * self.size_multiplier


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """The §10 verdict for one candidate trade."""

    allowed: bool
    account: Account
    budget: SizingBudget
    gates: tuple[Gate, ...] = ()

    @property
    def reasons(self) -> tuple[str, ...]:
        out: list[str] = []
        for g in self.gates:
            if not g.allowed:
                out.extend(g.reasons)
        return tuple(out)


@dataclass(frozen=True, slots=True)
class AllocationReport:
    """§10.6 allocation of the ``long_term`` book by market-cap bucket."""

    targets_pct: Mapping[str, Decimal]
    current_pct: Mapping[str, Decimal]
    headroom_usd: Mapping[str, Decimal]
    cash_pct: Decimal
    cash_floor_pct: Decimal
    large_cap_count: int
    mid_cap_count: int
    breaches: tuple[str, ...] = ()


# --------------------------------------------------------------------------- CF-01 risk ladder


def per_trade_risk_pct(
    config: Config,
    *,
    trade_class: TradeClass,
    conviction: Conviction = Conviction.NORMAL,
    counter_trend: bool = False,
) -> Decimal:
    """**CF-01** — the risk-budget ladder (SPEC.md §8.8), as a percentage of account equity.

    Precedence, tightest-wins after the class base:

    1. class base — swing ``max_loss_pct_swing`` (4.0), scalp ``max_loss_pct_scalp`` (2.5);
       ``PRICE_DISCOVERY`` is a swing, ``COUNTER_TREND`` is a scalp after the CF-03 demotion;
    2. high-conviction escalation to ``max_loss_pct_swing_hard_cap`` (5.0) — **swing only** and
       only behind ``high_conviction_loss_pct_enabled`` (default false, TBOT1-R13);
    3. counter-trend caps at ``max_loss_pct_counter_trend`` (2.0) — the halving (S7-R9, S3-R25);
    4. low conviction caps at ``max_loss_pct_low_conviction`` (1.5) — S6-R26's 1/3 size;
    5. the swing hard cap (5.0) binds everything, always.

    The CF-03 *notional* multiplier (0.5) is ``qualification.py``'s key and is applied separately
    by :func:`compose_size_multipliers`; what happens here is the **cap** side of counter-trend.
    """
    is_swing = trade_class in (TradeClass.SWING, TradeClass.PRICE_DISCOVERY)
    base = dec(config.max_loss_pct_swing) if is_swing else dec(config.max_loss_pct_scalp)

    if is_swing and conviction is Conviction.HIGH and config.high_conviction_loss_pct_enabled:
        # TBOT1-R13, CF-01 precedence rule 2: an escalation, never the default.
        base = dec(config.max_loss_pct_swing_hard_cap)

    if counter_trend or trade_class is TradeClass.COUNTER_TREND:
        base = min(base, dec(config.max_loss_pct_counter_trend))
    if conviction is Conviction.LOW:
        base = min(base, dec(config.max_loss_pct_low_conviction))

    return min(base, dec(config.max_loss_pct_swing_hard_cap))


def touch_decay(config: Config, touch_index: int) -> Decimal:
    """**CF-07** — ``touch_size_decay[min(touch_index, 5) - 1]``.

    Touch 1 and 2 are full size, 3 is 0.66, 4 is 0.50, 5 and beyond 0.33 (S2-R15, S8-R22,
    TBOT1-R3).  The curve shape is **OURS**; the "weaker every touch" principle is his.
    """
    if touch_index < 1:
        raise ValueError(f"touch_index is 1-based, got {touch_index}")
    curve = config.touch_size_decay
    return dec(curve[min(touch_index, len(curve)) - 1])


def compose_size_multipliers(
    config: Config,
    *,
    touch_index: int = 1,
    extra: Sequence[Decimal | float] = (),
) -> Decimal:
    """**§10.8** — multipliers compose *multiplicatively* on notional. **[OUR CHOICE]** order.

    ``touch_index`` drives the CF-07 decay, which this module owns.  Everything else arrives in
    ``extra`` because the keys belong elsewhere: ``counter_trend_size_multiplier`` (0.5) and
    ``bvol_size_multiplier`` (0.5) are ``qualification.py``'s (INTERFACES.md §7).  The risk cap
    is re-checked afterwards and binds whichever is smaller — see :func:`sizing_budget`.
    """
    m = touch_decay(config, touch_index)
    for x in extra:
        m *= dec(x)
    return m


# --------------------------------------------------------------------------- CF-02 notional


def margin_ceiling_usd(config: Config, *, equity_usd: Decimal | float) -> Decimal:
    """**CF-02 / Q8** — the per-trade **margin** ceiling on a leverage play.

    ``margin_pct_leverage`` (10 %, S7 ``[00:25:54]``: "you enter each play with 10% of your
    portfolio… whatever the leverage is, you calculate that you only lose four to 5% of your
    port").  This is the figure S7 and S3 quote, and it is margin — a 10 % *notional* reading
    would need a 50 % stop to produce his stated 5 % portfolio loss, which is absurd against the
    9 % ``max_stop_pct_leverage`` ceiling.  Spot has no margin: use
    :func:`notional_ceiling_usd`.
    """
    return dec(equity_usd) * dec(config.margin_pct_leverage) / HUNDRED


def notional_ceiling_usd(
    config: Config,
    *,
    equity_usd: Decimal | float,
    vehicle: Vehicle,
    conviction: Conviction = Conviction.NORMAL,
) -> Decimal:
    """**CF-02** — the per-trade notional ceiling (SPEC.md §8.8).

    Leverage ``max_notional_pct_leverage`` (**100 %**, Q8: ``margin_pct_leverage`` 10 % ×
    ``default_leverage`` 10x); spot ``spot_notional_pct_high_conviction`` (12 %) when conviction
    is ``HIGH``, else ``spot_notional_pct_low_conviction`` (6 %).  Notional is a *derived,
    clamped* quantity — never an input (S2-A18, S3-A12).

    **Q8 (derived, S6 ``[00:08:36]``–``[00:11:27]``).**  The leverage row used to hold 10.0, which
    is his *margin* percentage enforced as a *notional* ceiling.  Because :func:`tbot.plan.solve_size`
    re-solves quantity from the clamped notional, that mislabelling silently capped every leverage
    trade at roughly 0.7 % portfolio risk instead of the 4–5 % the CF-01 ladder assigns.  His own
    worked sizing example accepts a **$729 notional on a $1,000 portfolio — 72.9 %** — which a
    10 % notional ceiling cannot produce at all.  Spot really is notional and really is small; only
    the leverage row moved.
    """
    eq = dec(equity_usd)
    if vehicle is Vehicle.LEVERAGE:
        pct = dec(config.max_notional_pct_leverage)
    elif conviction is Conviction.HIGH:
        pct = dec(config.spot_notional_pct_high_conviction)
    else:
        pct = dec(config.spot_notional_pct_low_conviction)
    return eq * pct / HUNDRED


def loss_budget_usd(config: Config, *, equity_usd: Decimal | float, risk_pct: Decimal) -> Decimal:
    """``risk_pct / 100 * equity`` — risk is always a percentage of *current* equity (S2-R25)."""
    return dec(equity_usd) * dec(risk_pct) / HUNDRED


def spot_deployment_gate(
    config: Config, portfolio: PortfolioState, *, add_notional_usd: Decimal | float
) -> Gate:
    """**CF-02** — portfolio-wide spot cap ``max_total_spot_deployment_pct`` (70 %, S4-R31/S8-R35)."""
    cap = dec(portfolio.equity_usd) * dec(config.max_total_spot_deployment_pct) / HUNDRED
    used = sum((s.notional_usd for s in portfolio.live_slots() if s.vehicle is Vehicle.SPOT), ZERO)
    proposed = used + dec(add_notional_usd)
    if money_le(proposed, cap):
        return Gate("spot_deployment", True, source_ids=("CF-02", "S4-R31", "S8-R35"))
    return Gate(
        "spot_deployment",
        False,
        (f"spot_deployment_exceeds_max_total_spot_deployment_pct "
         f"({proposed} > {cap})",),
        ("CF-02", "S4-R31", "S8-R35"),
    )


def sizing_budget(
    config: Config,
    portfolio: PortfolioState,
    *,
    trade_class: TradeClass,
    vehicle: Vehicle,
    conviction: Conviction = Conviction.NORMAL,
    counter_trend: bool = False,
    touch_index: int = 1,
    extra_multipliers: Sequence[Decimal | float] = (),
) -> SizingBudget:
    """Assemble everything :mod:`tbot.plan` needs to solve quantity backwards (SPEC.md §8.8)."""
    pct = per_trade_risk_pct(
        config, trade_class=trade_class, conviction=conviction, counter_trend=counter_trend
    )
    budget = loss_budget_usd(config, equity_usd=portfolio.equity_usd, risk_pct=pct)
    mult = compose_size_multipliers(config, touch_index=touch_index, extra=extra_multipliers)
    ceiling = notional_ceiling_usd(
        config, equity_usd=portfolio.equity_usd, vehicle=vehicle, conviction=conviction
    )
    if vehicle is Vehicle.LEVERAGE:
        # Q8: the margin ceiling is the figure he actually quotes (10 % of portfolio, S7
        # `[00:25:54]`); the notional ceiling is that margin at ``default_leverage``.  At the
        # shipped defaults the two coincide at 100 % of equity, so this binds only when a sweep
        # moves ``margin_pct_leverage`` or ``default_leverage``.
        implied = (
            margin_ceiling_usd(config, equity_usd=portfolio.equity_usd)
            * dec(config.default_leverage)
        )
        ceiling = min(ceiling, implied)
    if vehicle is Vehicle.SPOT:
        # The portfolio-wide 70 % cap can bite before the per-trade 12 %/6 % ceiling does.
        deployed = sum(
            (s.notional_usd for s in portfolio.live_slots() if s.vehicle is Vehicle.SPOT), ZERO
        )
        room = (
            dec(portfolio.equity_usd) * dec(config.max_total_spot_deployment_pct) / HUNDRED
            - deployed
        )
        ceiling = min(ceiling, max(room, ZERO))
    return SizingBudget(
        equity_usd=dec(portfolio.equity_usd),
        risk_budget_pct=pct,
        loss_budget_usd=budget,
        size_multiplier=mult,
        notional_ceiling_usd=ceiling,
        source_ids=("CF-01", "CF-02", "CF-07", "S6-R11", "S6-R12", "S6 `[00:08:36]`"),
    )


# --------------------------------------------------------------------------- CF-04 concurrency


def concurrency_gate(
    config: Config,
    portfolio: PortfolioState,
    *,
    vehicle: Vehicle,
    trade_class: TradeClass,
    counter_trend: bool = False,
) -> Gate:
    """**CF-04** — per-bucket concurrency caps, leverage and spot counted **separately**.

    ``max_concurrent_leverage_swing`` 2, ``max_concurrent_leverage_scalp`` 2,
    ``max_concurrent_leverage_global`` 4, ``max_concurrent_spot`` 5.  Only live positions
    (``PARTIAL``/``OPEN``/``MANAGING``) count (SPEC.md §9.1).

    §10.7: a counter-trend plan consumes a **scalp** slot after the CF-03 demotion, not a swing
    slot — the caller signals that either by handing in ``TradeClass.SCALP`` or by
    ``counter_trend=True``.
    """
    live = portfolio.live_slots()
    ids = ("CF-04", "S4-R30", "S4-R31", "S4-C8")

    if vehicle is Vehicle.SPOT:
        n = sum(1 for s in live if s.vehicle is Vehicle.SPOT)
        cap = int(config.max_concurrent_spot)
        if n >= cap:
            return Gate("concurrency", False,
                        (f"max_concurrent_spot_reached ({n}/{cap})",), ids)
        return Gate("concurrency", True, source_ids=ids)

    lev = [s for s in live if s.vehicle is Vehicle.LEVERAGE]
    g_cap = int(config.max_concurrent_leverage_global)
    if len(lev) >= g_cap:
        return Gate("concurrency", False,
                    (f"max_concurrent_leverage_global_reached ({len(lev)}/{g_cap})",), ids)

    scalp_side = counter_trend or trade_class in (TradeClass.SCALP, TradeClass.COUNTER_TREND)
    if scalp_side:
        n = sum(1 for s in lev
                if s.trade_class in (TradeClass.SCALP, TradeClass.COUNTER_TREND))
        cap = int(config.max_concurrent_leverage_scalp)
        key = "max_concurrent_leverage_scalp"
    else:
        n = sum(1 for s in lev
                if s.trade_class in (TradeClass.SWING, TradeClass.PRICE_DISCOVERY))
        cap = int(config.max_concurrent_leverage_swing)
        key = "max_concurrent_leverage_swing"
    if n >= cap:
        return Gate("concurrency", False, (f"{key}_reached ({n}/{cap})",), ids)
    return Gate("concurrency", True, source_ids=ids)


# --------------------------------------------------------------------------- CF-44 daily halt


def is_loss(config: Config, trade: ClosedTrade) -> bool:
    """**CF-44** — ``loss_definition``.

    ``"closed_below_average_entry_net_fees"`` (default, S2-A23): any trade whose net P&L is
    negative counts, not only a stop-out.  ``"stop_out_only"`` counts stop-outs alone.
    """
    if config.loss_definition == "stop_out_only":
        return trade.was_stop_out and trade.pnl_usd < ZERO
    return dec(trade.pnl_usd) < ZERO


def losses_today(
    config: Config, portfolio: PortfolioState, *, account: Account | None = None
) -> tuple[ClosedTrade, ...]:
    """Losing trades closed inside the current day (P16 ``day_start``, ``day_boundary_utc``)."""
    start = P.day_start(portfolio.now, config)
    scoped: Iterable[ClosedTrade] = portfolio.closed_trades
    if account is not None and config.account_scoped_cut_rules:
        scoped = (t for t in scoped if t.account is account)
    return tuple(t for t in scoped if t.closed_at >= start and is_loss(config, t))


def daily_loss_gate(
    config: Config, portfolio: PortfolioState, *, account: Account | None = None
) -> Gate:
    """**§10.4** — ``daily_loss_count_limit`` (2) losing trades in one day ends the day (S2-R21).

    Scope is **new entries only**: open positions keep being managed by §9. That scoping is
    **[OUR CHOICE]** — S2-R21 does not say (SPEC.md §10.4).
    """
    losses = losses_today(config, portfolio, account=account)
    cap = int(config.daily_loss_count_limit)
    ids = ("CF-44", "S2-R21", "CF-45")
    if len(losses) >= cap:
        return Gate(
            "daily_loss_halt",
            False,
            (f"daily_loss_count_limit_reached ({len(losses)}/{cap})",),
            ids,
        )
    return Gate("daily_loss_halt", True, source_ids=ids)


# --------------------------------------------------------------------------- S2-R24 ratchet


def win_streak(portfolio: PortfolioState, *, account: Account | None = None) -> int:
    """Consecutive winning closed trades, most recent first.  A break-even trade ends the streak."""
    trades = sorted(portfolio.closed_trades, key=lambda t: t.closed_at, reverse=True)
    n = 0
    for t in trades:
        if account is not None and t.account is not account:
            continue
        if dec(t.pnl_usd) > ZERO:
            n += 1
        else:
            break
    return n


def ratchet_gate(
    config: Config,
    portfolio: PortfolioState,
    *,
    requested_pct: Decimal | float,
    trade_class: TradeClass,
    account: Account | None = None,
) -> Gate:
    """**S2-R24, hard** — never increase risk-per-trade after a winning streak.

    ``risk_ratchet_up_allowed`` is ``false`` and CF-44 marks it hard.  The baseline is the risk
    percentage last actually used for this trade class
    (``PortfolioState.baseline_risk_pct[trade_class]``); with no baseline recorded there is
    nothing to ratchet *up* from and the gate passes.  De-risking **downward** is always
    permitted — see :func:`clamp_requested_risk_pct`.
    """
    ids = ("CF-44", "S2-R24")
    if config.risk_ratchet_up_allowed:
        return Gate("risk_ratchet", True, source_ids=ids)
    baseline = portfolio.baseline_risk_pct.get(str(trade_class.value))
    if baseline is None:
        return Gate("risk_ratchet", True, source_ids=ids)
    req, base = dec(requested_pct), dec(baseline)
    if req > base and not money_close(req, base):
        streak = win_streak(portfolio, account=account)
        return Gate(
            "risk_ratchet",
            False,
            (f"risk_ratchet_up_forbidden (requested {req}% > baseline {base}%, "
             f"win_streak={streak})",),
            ids,
        )
    return Gate("risk_ratchet", True, source_ids=ids)


def clamp_requested_risk_pct(
    config: Config,
    portfolio: PortfolioState,
    *,
    requested_pct: Decimal | float,
    trade_class: TradeClass,
) -> Decimal:
    """De-risking down is permitted, up is not (S2-R24): clamp to the recorded baseline."""
    if config.risk_ratchet_up_allowed:
        return dec(requested_pct)
    baseline = portfolio.baseline_risk_pct.get(str(trade_class.value))
    if baseline is None:
        return dec(requested_pct)
    return min(dec(requested_pct), dec(baseline))


# --------------------------------------------------------------------------- CF-44 challenge


def challenge_period_goal_usd(config: Config, *, period_start_balance_usd: Decimal | float) -> Decimal:
    """**CF-44 / S2-R23** — the period goal *compounds* off the previous closing balance.

    ``goal_usd = period_start_balance * challenge_goal_pct / 100``.  8 % weekly by default (the
    most conservative published figure, S2 ``[01:20:55]``); alternatives 5, 10, 20.
    """
    return dec(period_start_balance_usd) * dec(config.challenge_goal_pct) / HUNDRED


def next_period_goal_usd(config: Config, *, period_closing_balance_usd: Decimal | float) -> Decimal:
    """The next period's goal, compounded off this period's close.

    Never chase a missed goal into the next period (S2 ``[01:29:52]``) — the next goal is a
    function of the closing balance alone, with no carry-over of the shortfall.
    """
    return challenge_period_goal_usd(
        config, period_start_balance_usd=period_closing_balance_usd
    )


def challenge_gate(config: Config, portfolio: PortfolioState) -> Gate:
    """**S2-R22** — once the period goal is hit, stop trading for the rest of the period."""
    ids = ("CF-44", "S2-R22", "S2-R23")
    if not config.challenge_stop_on_goal:
        return Gate("challenge_goal", True, source_ids=ids)
    start = portfolio.period_start_balance_usd
    if start is None:
        return Gate("challenge_goal", True, source_ids=ids)
    goal = challenge_period_goal_usd(config, period_start_balance_usd=start)
    if money_ge(portfolio.period_realised_pnl_usd, goal):
        return Gate(
            "challenge_goal",
            False,
            (f"challenge_goal_reached ({portfolio.period_realised_pnl_usd} >= {goal}, "
             f"cadence={config.challenge_cadence})",),
            ids,
        )
    return Gate("challenge_goal", True, source_ids=ids)


def equity_restart_target(config: Config, portfolio: PortfolioState) -> Decimal | None:
    """**S2-R26** — halve-the-account-and-restart is recorded, not automated.

    ``equity_restart_mode = "off"`` (**[OUR CHOICE]**) returns ``None``; ``"halve"`` returns the
    target equity so a caller can act on it deliberately.
    """
    if config.equity_restart_mode == "off":
        return None
    return dec(portfolio.equity_usd) / Decimal(2)


# --------------------------------------------------------------------------- §10.6 allocation


def allocation_targets(config: Config) -> dict[str, Decimal]:
    """**S2-R16/R17** — target allocation of the ``long_term`` book, percent of equity."""
    return {
        "large": dec(config.alloc_large_cap_pct),
        "mid": dec(config.alloc_mid_cap_pct),
        "small": dec(config.alloc_small_cap_pct),
        "micro": dec(config.alloc_micro_cap_pct),
        "futures": dec(config.alloc_futures_pct),
        "cash": dec(config.alloc_cash_min_pct),
    }


def allocation_report(config: Config, portfolio: PortfolioState) -> AllocationReport:
    """Current vs target allocation of the ``long_term`` book (SPEC.md §10.6).

    ``alloc_cash_min_pct`` is a **floor** (S2-C5), not a target: take profit into the cash
    reserve as price rises (S2-R17).  ``long_term_max_large_caps`` (5) and
    ``long_term_max_mid_caps`` (4) cap the name count — do not over-diversify (S2-R19).
    """
    eq = dec(portfolio.equity_usd)
    targets = allocation_targets(config)
    slots = [s for s in portfolio.live_slots() if s.account is Account.LONG_TERM]

    used: dict[str, Decimal] = {k: ZERO for k in targets}
    for s in slots:
        bucket = "futures" if s.vehicle is Vehicle.LEVERAGE else s.mcap_bucket
        used[bucket] = used.get(bucket, ZERO) + dec(s.notional_usd)

    current = {k: (used[k] / eq * HUNDRED if eq > ZERO else ZERO) for k in targets}
    headroom = {
        k: max(eq * targets[k] / HUNDRED - used[k], ZERO)
        for k in targets
        if k != "cash"
    }

    if portfolio.cash_usd is None:
        deployed = sum(used.values(), ZERO)
        cash_pct = (eq - deployed) / eq * HUNDRED if eq > ZERO else ZERO
    else:
        cash_pct = dec(portfolio.cash_usd) / eq * HUNDRED if eq > ZERO else ZERO
    current["cash"] = cash_pct

    n_large = sum(1 for s in slots if s.vehicle is Vehicle.SPOT and s.mcap_bucket == "large")
    n_mid = sum(1 for s in slots if s.vehicle is Vehicle.SPOT and s.mcap_bucket == "mid")

    breaches: list[str] = []
    for k, tgt in targets.items():
        if k == "cash":
            continue
        if current[k] > tgt and not money_close(current[k], tgt):
            breaches.append(f"alloc_{k}_cap_exceeded ({current[k]}% > {tgt}%)")
    floor = dec(config.alloc_cash_min_pct)
    if cash_pct < floor and not money_close(cash_pct, floor):
        breaches.append(f"alloc_cash_min_pct_breached ({cash_pct}% < {floor}%)")
    if n_large > int(config.long_term_max_large_caps):
        breaches.append(
            f"long_term_max_large_caps_exceeded ({n_large}/{config.long_term_max_large_caps})"
        )
    if n_mid > int(config.long_term_max_mid_caps):
        breaches.append(
            f"long_term_max_mid_caps_exceeded ({n_mid}/{config.long_term_max_mid_caps})"
        )

    return AllocationReport(
        targets_pct=targets,
        current_pct=current,
        headroom_usd=headroom,
        cash_pct=cash_pct,
        cash_floor_pct=floor,
        large_cap_count=n_large,
        mid_cap_count=n_mid,
        breaches=tuple(breaches),
    )


def allocation_gate(
    config: Config,
    portfolio: PortfolioState,
    *,
    bucket: McapBucket,
    add_notional_usd: Decimal | float,
    vehicle: Vehicle = Vehicle.SPOT,
) -> Gate:
    """Can the ``long_term`` book absorb ``add_notional_usd`` in ``bucket`` (§10.6)?

    Checks the bucket target, the ``alloc_cash_min_pct`` floor after the buy, and the name
    counts.  Applies to the ``long_term`` account only — the trading accounts are governed by
    CF-02 and CF-04 instead.
    """
    ids = ("S2-R16", "S2-R17", "S2-R19", "S2-C5")
    rep = allocation_report(config, portfolio)
    add = dec(add_notional_usd)
    eq = dec(portfolio.equity_usd)
    key = "futures" if vehicle is Vehicle.LEVERAGE else bucket

    reasons: list[str] = []
    if add > rep.headroom_usd.get(key, ZERO) and not money_close(
        add, rep.headroom_usd.get(key, ZERO)
    ):
        reasons.append(
            f"alloc_{key}_headroom_exceeded ({add} > {rep.headroom_usd.get(key, ZERO)})"
        )
    cash_after = rep.cash_pct - (add / eq * HUNDRED if eq > ZERO else ZERO)
    if cash_after < rep.cash_floor_pct and not money_close(cash_after, rep.cash_floor_pct):
        reasons.append(
            f"alloc_cash_min_pct_would_breach ({cash_after}% < {rep.cash_floor_pct}%)"
        )
    if key == "large" and rep.large_cap_count >= int(config.long_term_max_large_caps):
        reasons.append(
            f"long_term_max_large_caps_reached "
            f"({rep.large_cap_count}/{config.long_term_max_large_caps})"
        )
    if key == "mid" and rep.mid_cap_count >= int(config.long_term_max_mid_caps):
        reasons.append(
            f"long_term_max_mid_caps_reached "
            f"({rep.mid_cap_count}/{config.long_term_max_mid_caps})"
        )
    return Gate("allocation", not reasons, tuple(reasons), ids)


# --------------------------------------------------------------------------- CF-43 accounts


def cut_on_level_loss_applies(config: Config, account: Account) -> bool:
    """**CF-43** — ``account_scoped_cut_rules``: the ``long_term`` book is **never** cut on a
    level loss ("if you are an investor, this does not apply to you", S2 ``[00:53:58]``, S2-C6).

    Encoded explicitly, or the bot liquidates the investment book on a 4H support break.
    """
    if not config.account_scoped_cut_rules:
        return True
    return account is not Account.LONG_TERM


def long_term_exit_mode(config: Config) -> str:
    """**CF-43** — ``"macro_msb_two_step"``: HTF close below the last higher low, then a lower
    high; sell into the retest, accepting 20-30 % off the top (S3-R21, S7-R36)."""
    return str(config.long_term_exit_mode)


def derisk_action(
    config: Config, *, average_entry: Decimal | float, price: Decimal | float
) -> Literal["full", "partial"] | None:
    """**S2-R18** — withdraw initial capital at 3x, partial de-risk at 2x (``long_term`` only)."""
    entry, now = dec(average_entry), dec(price)
    if entry <= ZERO:
        raise ValueError("average_entry must be positive")
    mult = now / entry
    thresholds = config.long_term_derisk_multiple
    full, partial = dec(thresholds["full"]), dec(thresholds["partial"])
    if money_ge(mult, full):
        return "full"
    if money_ge(mult, partial):
        return "partial"
    return None


def spot_rotation_due(
    config: Config, *, average_entry: Decimal | float, price: Decimal | float
) -> bool:
    """**S2 ``[01:15:16]``** — rotate the short-term spot book after a
    ``spot_short_term_tp_move_pct`` (12.5 %) move."""
    entry, now = dec(average_entry), dec(price)
    if entry <= ZERO:
        raise ValueError("average_entry must be positive")
    move = abs(now - entry) / entry * HUNDRED
    return money_ge(move, dec(config.spot_short_term_tp_move_pct))


def hedge_size(
    config: Config, *, position_notional_usd: Decimal | float
) -> tuple[Decimal, Decimal] | None:
    """**S4-R35** — a 1:1 spot short at <= 2-3x, **off by default** (``hedge_enabled = false``,
    **[OUR CHOICE]**: hedging is a portfolio operation, not a signal).

    Returns ``(notional_usd, max_leverage)`` or ``None`` when disabled.
    """
    if not config.hedge_enabled:
        return None
    return (
        dec(position_notional_usd) * dec(config.hedge_size_ratio),
        dec(config.hedge_max_leverage),
    )


# --------------------------------------------------------------------------- top level


def approve_trade(
    config: Config,
    portfolio: PortfolioState,
    *,
    account: Account,
    trade_class: TradeClass,
    vehicle: Vehicle,
    conviction: Conviction = Conviction.NORMAL,
    counter_trend: bool = False,
    touch_index: int = 1,
    extra_multipliers: Sequence[Decimal | float] = (),
    mcap_bucket: McapBucket = "large",
) -> RiskDecision:
    """Run the whole §10 stack for one candidate trade and return the sizing budget.

    Gate order: daily-loss halt (§10.4) -> challenge stop-on-goal (§10.5) -> concurrency (CF-04)
    -> risk ratchet (S2-R24) -> allocation (§10.6, ``long_term`` only).  Every gate runs so the
    caller sees **all** the reasons, but ``allowed`` is the conjunction.

    The returned :class:`SizingBudget` is valid even when ``allowed`` is ``False`` — a rejected
    trade still reports what it *would* have risked, which is what the CLI prints.
    """
    budget = sizing_budget(
        config,
        portfolio,
        trade_class=trade_class,
        vehicle=vehicle,
        conviction=conviction,
        counter_trend=counter_trend,
        touch_index=touch_index,
        extra_multipliers=extra_multipliers,
    )

    gates: list[Gate] = [
        daily_loss_gate(config, portfolio, account=account),
    ]
    if account is Account.CHALLENGE:
        gates.append(challenge_gate(config, portfolio))
    gates.append(
        concurrency_gate(
            config,
            portfolio,
            vehicle=vehicle,
            trade_class=trade_class,
            counter_trend=counter_trend,
        )
    )
    gates.append(
        ratchet_gate(
            config,
            portfolio,
            requested_pct=budget.risk_budget_pct,
            trade_class=trade_class,
            account=account,
        )
    )
    if account is Account.LONG_TERM:
        gates.append(
            allocation_gate(
                config,
                portfolio,
                bucket=mcap_bucket,
                add_notional_usd=budget.notional_ceiling_usd,
                vehicle=vehicle,
            )
        )
    elif vehicle is Vehicle.SPOT:
        gates.append(
            spot_deployment_gate(
                config, portfolio, add_notional_usd=budget.notional_ceiling_usd
            )
        )

    return RiskDecision(
        allowed=all(g.allowed for g in gates),
        account=account,
        budget=budget,
        gates=tuple(gates),
    )
