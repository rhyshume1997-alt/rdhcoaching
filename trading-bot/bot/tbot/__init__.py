"""tbot — signal-generation and backtesting foundation for the SPEC.md trading system.

Layers, in dependency order::

    config  -> models -> primitives -> data
                             |
                             +-- detectors / plan builder / manager / risk / backtest
                                 (built by other modules against tbot/INTERFACES.md)

Live order execution is out of scope (SPEC.md §1.9): this package emits analysis and plans and
never talks to an exchange.
"""

from __future__ import annotations

from .config import Config, ConfigError, KEY_SPECS, KeySpec
from .models import Series, Timeframe

__all__ = ["Config", "ConfigError", "KeySpec", "KEY_SPECS", "Series", "Timeframe"]
__version__ = "0.1.0"
