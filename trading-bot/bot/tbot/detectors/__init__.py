"""SPEC.md §5 detectors.

Each module owns one section of §5 and implements the ``Detector`` protocol of
``tbot/INTERFACES.md`` §6: ``name``, ``stage``, ``source_ids``, ``produces``,
``detect(series, config)`` and the ``to_confluence`` adapter.  Detectors are pure and never
call one another — ``pipeline.py`` owns the stage ordering (`config.pipeline_order`).

This package init stays deliberately minimal: one import line per detector module, no registry.
Add your own module's export below without touching anyone else's.
"""

from __future__ import annotations

from tbot.detectors.levels import SupportResistanceDetector
from tbot.detectors.orderblocks import OrderBlockDetector
from tbot.detectors.ranges import RangeDetector
from tbot.detectors.trendlines import TrendlineDetector
from tbot.detectors.zones import SupplyDemandZoneDetector

__all__ = [
    "OrderBlockDetector",
    "RangeDetector",
    "SupportResistanceDetector",
    "SupplyDemandZoneDetector",
    "TrendlineDetector",
]
