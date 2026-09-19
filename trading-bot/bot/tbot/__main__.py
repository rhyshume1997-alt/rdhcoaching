"""``python -m tbot`` — the CLI entry point (see :mod:`tbot.cli`)."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
