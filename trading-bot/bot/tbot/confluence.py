"""SPEC.md §6 — confluence clustering, deduplicated weighted scoring and conviction.

This module is the *only* place that turns detector output into a score.  It does three things
and nothing else:

1. **Adapts** model objects (:class:`~tbot.models.Level`, :class:`~tbot.models.Zone`,
   :class:`~tbot.models.OrderBlock`, :class:`~tbot.models.FibLevel`, pattern/SFP/indicator
   records) into :class:`tbot.primitives.ConfluenceObject`\\ s, at the price each object should
   score at, carrying that object's ``source_ids`` forward.
2. **Clusters** those objects into price stacks and scores each stack with **P14**
   (:func:`tbot.primitives.score_confluence`) — the dedup rules live there and are *not*
   re-implemented here (INTERFACES.md §1.1).
3. **Maps** the resulting score to a :class:`~tbot.models.Conviction` (§6.3).

Dedup, the TBOT1-A4 question ("is an SR point + a supply zone + an order block at one price three
objects or one?"), resolves as **three** (CF-31, §6.2): objects of *different* classes each
contribute once; two objects of the *same* class contribute once, at the higher weight.
``single_class_trade_forbidden`` then forbids the whole stack being one class, regardless of score.

**Q5 (derived, S5 ``[01:05:33]``, S8 ``[00:53:41]``).**  Those three objects are *three*, and the
entry gate counts them — ``confluence_gate_mode = "raw_count"``.  The §6.1 weight map is no longer
the gate; it is kept for **ranking** two candidate stacks against each other and for the §6.3
high-conviction threshold.  As a gate it rejected stacks he demonstrably takes: S5
``[01:05:33]``'s golden pocket + trend-line retest + consolidation point scores 2.75 weighted and
he names "three" as his reason for taking it.

Two things this module deliberately does **not** do:

* **Cross-market context is never an object.** USDT.D / BTC.D / BVOL / a beta parent are a veto at
  weight 0 (TBOT1 §10, CF-35); they belong to :mod:`tbot.regime`, and passing them in here would
  silently turn a gate into a score.
* **``fib_loses_ties_to_sr`` is resolved before this module runs** (S6-R38, INTERFACES.md §8.4).
  That key belongs to ``detectors/fibs.py``; by the time an object list reaches
  :func:`score_at` the losing fib must already be gone.

Config keys read here (owned by ``confluence.py`` per INTERFACES.md §7): ``confluence_merge_atr``
and ``high_conviction_score`` directly; ``confluence_weights``, ``confluence_dedup_same_class``,
``min_confluence_count``, ``single_class_trade_forbidden`` and
``zone_continuation_confluence_bonus`` are read by P14 on our behalf — pass ``config`` through.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Sequence

from tbot.config import Config
from tbot.models import (
    ConfluenceClass,
    Conviction,
    FibLevel,
    Level,
    LevelKind,
    OrderBlock,
    Series,
    Timeframe,
    Zone,
    dec,
)
import tbot.primitives as P

__all__ = [
    "MODULE_SOURCE_IDS",
    "ConfluenceCluster",
    "confluence_class_of",
    "confluence_price_of",
    "to_confluence_object",
    "to_confluence_objects",
    "cluster_prices",
    "score_at",
    "find_clusters",
    "map_conviction",
    "rank_clusters",
    "best_cluster",
]

#: The rules this module implements (INTERFACES.md §6.3 class-level reporting).
MODULE_SOURCE_IDS: tuple[str, ...] = ("CF-31", "CF-10", "S6-R28", "S6-R38", "TBOT1-A4")

_ZERO = Decimal(0)

#: ``LevelKind`` → :class:`~tbot.models.ConfluenceClass` (§6.1).  ``MID_RANGE`` is deliberately
#: absent: the mid-range is the G6 *no-trade band* (CF-25), never a confluence contributor.
_LEVEL_KIND_CLASS: dict[LevelKind, ConfluenceClass] = {
    LevelKind.SUPPORT: ConfluenceClass.SR_LEVEL,
    LevelKind.RESISTANCE: ConfluenceClass.SR_LEVEL,
    LevelKind.SR_PENDING: ConfluenceClass.SR_LEVEL,
    LevelKind.SR_CONFIRMED_SUPPORT: ConfluenceClass.SR_LEVEL,
    LevelKind.SR_CONFIRMED_RESISTANCE: ConfluenceClass.SR_LEVEL,
    LevelKind.RANGE_HIGH: ConfluenceClass.RANGE_BOUNDARY,
    LevelKind.RANGE_LOW: ConfluenceClass.RANGE_BOUNDARY,
    LevelKind.TRENDLINE: ConfluenceClass.TRENDLINE,
}


# --------------------------------------------------------------------------- adapters


def confluence_class_of(obj: Any) -> str:
    """The §6.1 confluence class of a detector object.

    Recognises the model types directly and anything that declares its own class through a
    ``confluence_class`` / ``obj_class`` attribute — which is how pattern, SFP and RSI-divergence
    records from ``tbot/detectors/`` participate without this module importing them.

    Raises ``ValueError`` for objects that have no confluence class (a mid-range level, a swing
    point, cross-market context).
    """
    declared = getattr(obj, "confluence_class", None) or getattr(obj, "obj_class", None)
    if declared is not None:
        return ConfluenceClass(str(declared)).value
    if isinstance(obj, Level):
        if obj.kind is LevelKind.MID_RANGE:
            raise ValueError(
                "mid-range is the CF-25 no-trade band (gate G6), not a confluence contributor"
            )
        return _LEVEL_KIND_CLASS[obj.kind].value
    if isinstance(obj, Zone):
        return ConfluenceClass.ZONE.value
    if isinstance(obj, OrderBlock):
        return ConfluenceClass.ORDER_BLOCK.value
    if isinstance(obj, FibLevel):
        return ConfluenceClass.FIB.value
    raise ValueError(
        f"{type(obj).__name__} has no confluence class; declare one via `confluence_class` "
        f"(one of {[c.value for c in ConfluenceClass]})"
    )


def confluence_price_of(obj: Any, *, bar_index: int | None = None) -> Decimal:
    """The price an object scores at (INTERFACES.md §6.7).

    A zone scores at its ``entry_price_pmt`` (P20) and falls back to its frozen ``midpoint`` when
    the points-of-most-touch price has not been computed; an order block at its ``midpoint``; a
    level at ``price_at(bar_index)`` so a trend line is read on the right bar; everything else at
    its ``price``.
    """
    if isinstance(obj, Level):
        return obj.price_at(bar_index) if bar_index is not None else obj.price
    if isinstance(obj, Zone):
        return obj.entry_price_pmt if obj.entry_price_pmt is not None else obj.midpoint
    if isinstance(obj, OrderBlock):
        return obj.midpoint
    price = getattr(obj, "price", None)
    if price is None:
        raise ValueError(f"{type(obj).__name__} exposes no price to score at")
    return dec(price)


def to_confluence_object(
    obj: Any, *, bar_index: int | None = None, weight: Decimal | None = None
) -> P.ConfluenceObject:
    """Wrap one detector object as a P14 :class:`~tbot.primitives.ConfluenceObject`.

    ``source_ids`` is copied straight off the object, which is the middle link of the
    detector → confluence → plan explanation chain (INTERFACES.md §6.3).  Already-wrapped
    objects pass through untouched.
    """
    if isinstance(obj, P.ConfluenceObject):
        return obj
    return P.ConfluenceObject(
        id=str(getattr(obj, "id")),
        price=confluence_price_of(obj, bar_index=bar_index),
        obj_class=confluence_class_of(obj),
        weight=weight,
        tf=getattr(obj, "tf", None),
        source_ids=tuple(getattr(obj, "source_ids", ())),
    )


def to_confluence_objects(
    objects: Iterable[Any], *, bar_index: int | None = None
) -> list[P.ConfluenceObject]:
    """Adapt a mixed bag of detector output, dropping repeats of an id (first wins).

    Order is preserved, so the caller keeps control of P14's intra-class tie-break
    (INTERFACES.md §8.4) — put the object you want to win first.
    """
    out: list[P.ConfluenceObject] = []
    seen: set[str] = set()
    for obj in objects:
        wrapped = to_confluence_object(obj, bar_index=bar_index)
        if wrapped.id in seen:
            continue
        seen.add(wrapped.id)
        out.append(wrapped)
    return out


# --------------------------------------------------------------------------- clusters


@dataclass(frozen=True, slots=True)
class ConfluenceCluster:
    """One scored price stack: a P14 result plus the §6.3 conviction and the id chain."""

    price: Decimal
    score: Decimal
    classes: frozenset[str]
    contributors: tuple[P.ConfluenceObject, ...]   #: the winning object per class
    merged: tuple[P.ConfluenceObject, ...]         #: everything inside the merge band
    qualified: bool
    conviction: Conviction
    bonus: Decimal
    count: int                                     #: Q5 raw deduplicated object count
    tf: Timeframe | None                           #: highest timeframe among contributors
    unknown_classes: frozenset[str]
    reasons: tuple[str, ...]
    source_ids: tuple[str, ...]

    @property
    def object_ids(self) -> tuple[str, ...]:
        """Contributor ids, for :attr:`tbot.models.Setup.object_ids`."""
        return tuple(o.id for o in self.contributors)

    @property
    def class_count(self) -> int:
        return len(self.classes)


def _chain_source_ids(objects: Sequence[P.ConfluenceObject]) -> tuple[str, ...]:
    """Union of the contributors' rule ids, first-seen order (deterministic, no sets)."""
    out: list[str] = []
    for obj in objects:
        for sid in obj.source_ids:
            if sid not in out:
                out.append(sid)
    return tuple(out)


def _highest_tf(objects: Sequence[P.ConfluenceObject]) -> Timeframe | None:
    tfs = [o.tf for o in objects if o.tf is not None]
    if not tfs:
        return None
    return max(tfs, key=lambda t: t.rank)


def map_conviction(
    score: Decimal | float,
    config: Config,
    *,
    count: int | None = None,
    adverse_regime: bool = False,
    unclear_price_action: bool = False,
    mid_range_flag: bool = False,
) -> Conviction:
    """SPEC.md §6.3 conviction mapping.  Drives sizing, never eligibility.

    ``high`` needs the **weighted** ``score >= high_conviction_score`` (4.0, **[OUR CHOICE]**)
    *and* no adverse regime flag — that is the ranking use of the §6.1 map that survives Q5.  Any
    adverse-but-non-vetoing regime flag, unclear price action or a mid-range behaviour flag
    (S8-C6) forces ``low`` whatever the score says.

    **Q5**: the ``normal`` floor is the *gate* quantity, so a stack that clears
    ``min_confluence_count`` on raw object count is at least ``normal`` even when its weighted
    score is lower — otherwise the retired weighted gate would come back in through the sizing
    door.  Pass ``count`` (from :attr:`tbot.primitives.ConfluenceResult.count`); omit it and the
    weighted score is used for the floor too, which is the ``"weighted_score"`` behaviour.
    """
    value = dec(score)
    if adverse_regime or unclear_price_action or mid_range_flag:
        return Conviction.LOW
    if value >= dec(config.high_conviction_score):
        return Conviction.HIGH
    floor = value
    if count is not None and config.confluence_gate_mode == "raw_count":
        floor = dec(count)
    if floor >= dec(config.min_confluence_count):
        return Conviction.NORMAL
    return Conviction.LOW


def score_at(
    series: Series,
    config: Config,
    candidate_price: Decimal | float,
    objects: Iterable[Any],
    *,
    at_index: int | None = None,
    continuation_zone: bool = False,
    adverse_regime: bool = False,
    unclear_price_action: bool = False,
    mid_range_flag: bool = False,
) -> ConfluenceCluster:
    """Score one candidate price (§6.2 = P14) and attach conviction and the id chain.

    ``continuation_zone`` adds ``zone_continuation_confluence_bonus`` (+1.0, CF-10) — set it when
    the zone anchoring this candidate is :class:`~tbot.models.ZoneClass.CONTINUATION`.
    """
    wrapped = to_confluence_objects(objects, bar_index=at_index)
    result = P.score_confluence(
        series,
        config,
        candidate_price,
        wrapped,
        at_index=at_index,
        continuation_zone=continuation_zone,
    )
    return ConfluenceCluster(
        price=dec(candidate_price),
        score=result.score,
        classes=result.classes,
        contributors=result.contributors,
        merged=result.merged,
        qualified=result.qualified,
        conviction=map_conviction(
            result.score,
            config,
            count=result.count,
            adverse_regime=adverse_regime,
            unclear_price_action=unclear_price_action,
            mid_range_flag=mid_range_flag,
        ),
        bonus=result.bonus,
        count=result.count,
        tf=_highest_tf(result.contributors),
        unknown_classes=result.unknown_classes,
        reasons=result.reasons,
        source_ids=_chain_source_ids(result.contributors),
    )


def cluster_prices(
    series: Series,
    config: Config,
    objects: Iterable[Any],
    *,
    at_index: int | None = None,
) -> list[Decimal]:
    """Candidate prices: one per stack of objects sitting at the same price.

    Objects are swept in ascending price and a stack stays open while the next object is within
    ``confluence_merge_atr * ATR`` **of the stack's anchor** — anchored, not single-linked, so a
    long ladder of levels cannot chain into one arbitrarily wide cluster.  The stack's price is
    the price of its **heaviest** object (ties → lowest price, then id), because S/R is drawn
    first and everything else is subordinate to it (PL-1, S6-R28).  **[OUR CHOICE]** — the corpus
    never enumerates candidate prices, it reads them off a chart.
    """
    wrapped = to_confluence_objects(objects, bar_index=at_index)
    if not wrapped:
        return []
    band = float(P.atr_at(series, config, at_index)) * config.confluence_merge_atr
    weights = config.confluence_weights
    ordered = sorted(wrapped, key=lambda o: (float(o.price), o.id))

    prices: list[Decimal] = []
    stack: list[P.ConfluenceObject] = []

    def close_stack() -> None:
        if not stack:
            return
        best = max(
            stack,
            key=lambda o: (
                float(o.weight) if o.weight is not None else float(weights.get(o.obj_class, 0.0)),
                -float(o.price),
            ),
        )
        if best.price not in prices:
            prices.append(best.price)

    for obj in ordered:
        if stack and float(obj.price) - float(stack[0].price) > band:
            close_stack()
            stack = []
        stack.append(obj)
    close_stack()
    return prices


def find_clusters(
    series: Series,
    config: Config,
    objects: Iterable[Any],
    *,
    at_index: int | None = None,
    continuation_zone_ids: Iterable[str] = (),
    adverse_regime: bool = False,
    unclear_price_action: bool = False,
    mid_range_flag: bool = False,
) -> list[ConfluenceCluster]:
    """Cluster *all* objects into price stacks and score every stack (§6.2).

    Each candidate price found by :func:`cluster_prices` is re-scored by P14 against the **full**
    object list, so a stack's membership is always exactly "everything within the merge band of
    the price we would actually bid at".  Stacks with identical contributor sets collapse to the
    highest-scoring one.  Results are returned in :func:`rank_clusters` order.

    ``continuation_zone_ids`` names the zone objects that are
    :class:`~tbot.models.ZoneClass.CONTINUATION`; a stack containing one takes the CF-10 bonus.
    """
    wrapped = to_confluence_objects(objects, bar_index=at_index)
    continuation = frozenset(continuation_zone_ids)
    seen: dict[frozenset[str], ConfluenceCluster] = {}
    for price in cluster_prices(series, config, wrapped, at_index=at_index):
        probe = P.score_confluence(series, config, price, wrapped, at_index=at_index)
        is_continuation = any(o.id in continuation for o in probe.merged)
        cluster = score_at(
            series,
            config,
            price,
            wrapped,
            at_index=at_index,
            continuation_zone=is_continuation,
            adverse_regime=adverse_regime,
            unclear_price_action=unclear_price_action,
            mid_range_flag=mid_range_flag,
        )
        key = frozenset(cluster.object_ids)
        previous = seen.get(key)
        if previous is None or cluster.score > previous.score:
            seen[key] = cluster
    return rank_clusters(seen.values())


def rank_clusters(clusters: Iterable[ConfluenceCluster]) -> list[ConfluenceCluster]:
    """§6.2 tie-break between candidates: higher score first, then the higher timeframe (S7-R20).

    Remaining ties break on price then contributor ids purely so the order is deterministic
    (INTERFACES.md §9.9).
    """
    return sorted(
        clusters,
        key=lambda c: (
            -float(c.score),
            -(c.tf.rank if c.tf is not None else -1),
            float(c.price),
            c.object_ids,
        ),
    )


def best_cluster(clusters: Iterable[ConfluenceCluster]) -> ConfluenceCluster | None:
    """The winning candidate, or ``None`` — never force a setup (PL-9, S6-R46)."""
    ranked = rank_clusters(clusters)
    return ranked[0] if ranked else None
