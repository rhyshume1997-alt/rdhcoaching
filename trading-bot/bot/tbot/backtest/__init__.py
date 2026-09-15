"""tbot.backtest — the SPEC.md §12 harness: strict bar-by-bar simulation plus metrics.

Two modules:

* :mod:`tbot.backtest.engine` — the no-lookahead simulator (§12.1), the intrabar fill model
  (§12.2), fees/slippage/funding (§12.3) and the full event log.
* :mod:`tbot.backtest.metrics` — the §12.4 metric set and the §12.5 treatment of the 77–82 %
  claim as a *hypothesis under test*.

Nothing here touches the network (SPEC.md §1.9).  Live execution lives behind the deliberately
unimplemented :class:`tbot.execution.ExecutionAdapter`.
"""

from __future__ import annotations

from .engine import (
    BacktestEngine,
    BacktestResult,
    BarWindow,
    ClosedTrade,
    DetectionRecord,
    Event,
    EventKind,
    EventLog,
    LookaheadError,
    OpenTrade,
    PipelineOutput,
    RejectionRecord,
    SplitError,
    SplitResult,
    DEFAULT_IN_SAMPLE_FRACTION,
    run_backtest,
    split_backtest,
)
from .metrics import MetricsReport, compute_metrics

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "BarWindow",
    "ClosedTrade",
    "DetectionRecord",
    "Event",
    "EventKind",
    "EventLog",
    "LookaheadError",
    "OpenTrade",
    "PipelineOutput",
    "RejectionRecord",
    "run_backtest",
    "split_backtest",
    "SplitResult",
    "SplitError",
    "DEFAULT_IN_SAMPLE_FRACTION",
    "MetricsReport",
    "compute_metrics",
]
