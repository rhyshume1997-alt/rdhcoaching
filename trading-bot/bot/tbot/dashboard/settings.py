"""Live-editable dashboard settings: what to watch, and which of the 245 keys to tune.

A settings change is the *other* thing (besides a new closed bar) that may invalidate a cached
pipeline result, so every settings object carries a monotonic :attr:`DashboardSettings.revision`
and that revision is part of the analysis cache key.  Changing a key therefore re-runs the
pipeline without a restart, and cannot silently leave a stale result on screen.

Config overrides go through ``Config.with_overrides``, which validates (INTERFACES.md §4) — a
bad value is rejected with the engine's own ``ConfigError`` wording and the previous settings
stay in force.  The dashboard never mutates a ``Config``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from tbot.config import KEY_SPEC_BY_NAME, Config

from .exchanges import DASHBOARD_TIMEFRAMES, SOURCES, supported_timeframes

__all__ = ["DashboardSettings", "SettingsStore", "TUNABLE_KEYS", "tunable_rows"]

DEFAULT_PAIRS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("4H", "1H")

#: The keys worth putting in front of a non-developer, grouped the way he would think about
#: them.  Everything else is still reachable through the search box in the Settings panel;
#: this is the shortlist, not the limit.
TUNABLE_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("How many reasons a trade needs", (
        "min_confluence_count",
        "confluence_gate_mode",
        "single_class_trade_forbidden",
        "confluence_merge_atr",
        "bias_level_min_confluence",
    )),
    ("Reward and size", (
        "min_rr",
        "rr_measured_from",
        "rr_measured_to",
        "min_expected_move_pct",
        "tp_min_count",
        "max_loss_pct_swing",
        "max_loss_pct_scalp",
    )),
    ("Levels, zones and order blocks", (
        "swing_k",
        "level_min_touches",
        "line_touch_hard_limit",
        "touch_reset_atr",
        "zone_fill_invalidation_pct",
        "ob_fill_invalidation_pct",
        "min_zone_depth_atr",
        "max_zone_depth_atr",
        "dead_zone_rescue_max_touches",
        "zone_wick_band_enabled",
        "zone_wick_band_max_ratio",
    )),
    ("Stops", (
        "stop_buffer_atr",
        "stop_buffer_zone_fraction",
        "dca2_min_zone_depth_atr",
    )),
    ("When not to trade", (
        "weekend_mode",
        "shorts_enabled",
        "net_short_allowed_in_uptrend",
        "short_in_price_discovery",
        "event_blackout_hours",
        "universe_max_symbols",
        "counter_trend_mode",
    )),
)


def _clean_pairs(values: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    for raw in values:
        sym = str(raw).strip().upper().replace("/", "").replace("-", "")
        if not sym or not sym.isalnum():
            raise ValueError(f"{raw!r} is not a usable symbol (letters and digits only)")
        if sym not in out:
            out.append(sym)
    if not out:
        raise ValueError("at least one pair is required")
    if len(out) > 24:
        raise ValueError("at most 24 pairs (each one costs a websocket stream and a cache slot)")
    return tuple(out)


def _clean_timeframes(values: Iterable[str], source: str) -> tuple[str, ...]:
    allowed = set(supported_timeframes(source))
    out: list[str] = []
    for raw in values:
        tf = str(raw).strip()
        if tf not in allowed:
            raise ValueError(
                f"{tf!r} is not a timeframe {source} can serve; "
                f"choose from {', '.join(t for t in DASHBOARD_TIMEFRAMES if t in allowed)}"
            )
        if tf not in out:
            out.append(tf)
    if not out:
        raise ValueError("at least one timeframe is required")
    if len(out) > 4:
        raise ValueError("at most 4 timeframes (pairs x timeframes is the recompute budget)")
    return tuple(out)


@dataclass(frozen=True, slots=True)
class DashboardSettings:
    """An immutable snapshot.  ``revision`` participates in the analysis cache key."""

    pairs: tuple[str, ...] = DEFAULT_PAIRS
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES
    source: str = "binance"
    venue_kind: str = "spot"
    #: bars of history fetched per (pair, timeframe); the engine wants a long warm-up
    history_bars: int = 900
    #: config keys overridden away from the YAML/defaults, key -> value
    overrides: dict[str, Any] = field(default_factory=dict)
    config_path: str | None = None
    revision: int = 0

    # ------------------------------------------------------------------ derived

    def subscriptions(self) -> tuple[tuple[str, str], ...]:
        return tuple((p, tf) for p in self.pairs for tf in self.timeframes)

    def build_config(self) -> Config:
        base = Config.load(self.config_path)
        return base.with_overrides(**self.overrides) if self.overrides else base

    def to_dict(self) -> dict[str, Any]:
        return {
            "pairs": list(self.pairs),
            "timeframes": list(self.timeframes),
            "source": self.source,
            "venue_kind": self.venue_kind,
            "history_bars": self.history_bars,
            "overrides": dict(self.overrides),
            "config_path": self.config_path,
            "revision": self.revision,
            "available_timeframes": list(supported_timeframes(self.source)),
            "available_sources": list(SOURCES),
        }


class SettingsStore:
    """Holds the current settings and applies validated patches.

    ``apply`` is all-or-nothing: if any part of the patch is invalid nothing changes, the caller
    gets the engine's own error text, and the UI keeps showing results that match the settings
    that are actually in force.
    """

    def __init__(self, settings: DashboardSettings | None = None) -> None:
        self._settings = settings or DashboardSettings()
        self._config = self._settings.build_config()
        self._lock = threading.RLock()

    @property
    def settings(self) -> DashboardSettings:
        with self._lock:
            return self._settings

    @property
    def config(self) -> Config:
        with self._lock:
            return self._config

    def apply(self, patch: Mapping[str, Any]) -> DashboardSettings:
        with self._lock:
            current = self._settings
            source = str(patch.get("source", current.source)).lower()
            if source not in SOURCES:
                raise ValueError(f"unknown source {source!r}; expected {', '.join(SOURCES)}")

            pairs = (_clean_pairs(patch["pairs"]) if "pairs" in patch else current.pairs)
            timeframes = _clean_timeframes(
                patch.get("timeframes", current.timeframes), source)

            venue = str(patch.get("venue_kind", current.venue_kind)).lower()
            if venue not in ("spot", "perp"):
                raise ValueError("venue_kind must be 'spot' or 'perp' (S6-R43)")

            history = int(patch.get("history_bars", current.history_bars))
            if not 200 <= history <= 1000:
                raise ValueError("history_bars must be between 200 and 1000 "
                                 "(one REST page; the dashboard does not paginate history)")

            overrides = dict(current.overrides)
            raw_overrides = patch.get("overrides")
            if raw_overrides is not None:
                if not isinstance(raw_overrides, Mapping):
                    raise ValueError("overrides must be an object of key -> value")
                overrides = {}
                for key, value in raw_overrides.items():
                    if key not in KEY_SPEC_BY_NAME:
                        raise ValueError(f"unknown config key {key!r}")
                    if value is None:
                        continue
                    overrides[key] = value

            candidate = replace(
                current, pairs=pairs, timeframes=timeframes, source=source,
                venue_kind=venue, history_bars=history, overrides=overrides,
                revision=current.revision + 1,
            )
            # validate by building: ConfigError propagates with every problem listed
            config = candidate.build_config()
            self._settings = candidate
            self._config = config
            return candidate


def tunable_rows(config: Config, overrides: Mapping[str, Any],
                 keys: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Config rows for the Settings panel: value, default, bounds, and the source rule id."""
    values = config.to_dict()
    names = list(keys) if keys is not None else [
        k for _group, group_keys in TUNABLE_KEYS for k in group_keys]
    rows: list[dict[str, Any]] = []
    for key in names:
        spec = KEY_SPEC_BY_NAME.get(key)
        if spec is None:
            continue
        rows.append({
            "key": key,
            "value": _plain(values.get(key)),
            "default": _plain(spec.default),
            "overridden": key in overrides,
            "type": spec.py_type,
            "spec_type": spec.spec_type,
            "members": list(spec.members) if spec.members else None,
            "minimum": spec.minimum,
            "maximum": spec.maximum,
            "source_id": spec.source_id,
            "group": spec.group,
            "note": spec.note,
        })
    return rows


def _plain(value: Any) -> Any:
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def grouped_tunables(config: Config, overrides: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"group": title, "keys": tunable_rows(config, overrides, keys)}
            for title, keys in TUNABLE_KEYS]
