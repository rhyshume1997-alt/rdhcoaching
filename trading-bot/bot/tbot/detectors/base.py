"""tbot.detectors.base — the detector protocol of ``tbot/INTERFACES.md`` §6.

Every stage-3…stage-14 detector of SPEC.md §5 is a class satisfying :class:`Detector`.  The
protocol is **structural** (``runtime_checkable``), so a detector never has to inherit from it;
``isinstance(det, Detector)`` is a shape check used by the tests.

Nothing in this module reads configuration, holds state or imports a sibling detector: a detector
must never call another detector (``pipeline.py`` owns stage ordering, SPEC.md §3.1).
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from ..config import Config
from ..models import Series
from ..primitives import ConfluenceObject

__all__ = ["Detector", "object_id"]


@runtime_checkable
class Detector(Protocol):
    """SPEC.md §5 detector.  Pure: same ``(series, config)`` in, same objects out."""

    name: str                      #: stable snake_case id, e.g. ``"supply_demand_zones"``
    stage: int                     #: SPEC.md §3.1 stage number (levels=3, zones=7, obs=8, …)
    source_ids: tuple[str, ...]    #: the rule IDs this detector implements
    produces: tuple[str, ...]      #: ``ConfluenceClass`` values it can emit

    def detect(self, series: Series, config: Config) -> list[Any]:
        """Objects completed within ``series``, **newest last**, ordered by completion bar."""
        ...

    def to_confluence(
        self, objects: Sequence[Any], config: Config
    ) -> list[ConfluenceObject]:
        """Map emitted objects onto the price they should score at (P14 adapter)."""
        ...


def object_id(series: Series, detector_name: str, completion_index: int, ordinal: int = 0) -> str:
    """The INTERFACES.md §6.5 deterministic id: ``symbol:tf:detector:completion_bar[:n]``.

    Collision-free and call-order independent — never ``uuid4``, never ``id()``, never a running
    counter (INTERFACES.md §9.9).
    """
    base = f"{series.symbol}:{series.tf.value}:{detector_name}:{completion_index}"
    return base if ordinal == 0 else f"{base}:{ordinal}"
