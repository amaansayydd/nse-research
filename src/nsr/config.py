"""Paths, date boundaries and the holdout guard.

Three data regimes, by trade date:

  research : HISTORY_START .. HOLDOUT_START-1   free for backtests and research
  holdout  : HOLDOUT_START .. HOLDOUT_END       LOCKED. Lives outside the project.
  forward  : > HOLDOUT_END                      live data collected by the daily run

The holdout may be read by exactly one caller: the scheduled production run,
and only to compute features for live predictions (owner decision, 2026-11-12).
Everything else must go through `assert_readable`, which raises.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT = Path(__file__).resolve().parents[2]
DATA = PROJECT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"

HOLDOUT_DIR = Path(os.environ.get("NSR_HOLDOUT_DIR", str(Path.home() / "nse_holdout_LOCKED")))
# The production panel contains holdout-window rows, so it also lives outside the project.
PROD_DIR = Path(os.environ.get("NSR_PROD_DIR", str(Path.home() / "nse_production")))
PREDICTIONS = PROJECT / "predictions.csv"
SCORES = PROJECT / "scores.csv"

HISTORY_START = date(2010, 1, 1)
HOLDOUT_START = date(2025, 11, 12)
HOLDOUT_END = date(2026, 11, 11)

IST = ZoneInfo("Asia/Kolkata")

# Historical publication times were never recorded by NSE. We ASSUME every
# end-of-day file for trade date D was public by D 20:00 IST. Live rows carry
# the real fetch timestamp instead. See data/README.md, flaw F1.
ASSUMED_EOD_PUBLISH = time(20, 0)

PRODUCTION_ENV = "NSR_PRODUCTION"


class HoldoutViolation(RuntimeError):
    """Raised when non-production code tries to touch the locked holdout."""


def in_holdout(d: date) -> bool:
    return HOLDOUT_START <= d <= HOLDOUT_END


def is_production() -> bool:
    return os.environ.get(PRODUCTION_ENV) == "1"


def assert_readable(d: date) -> None:
    """Call before parsing any raw file for trade date `d`."""
    if in_holdout(d) and not is_production():
        raise HoldoutViolation(
            f"{d} is inside the locked holdout ({HOLDOUT_START}..{HOLDOUT_END}). "
            "Research code may not read it."
        )


def raw_root(d: date) -> Path:
    """Holdout-dated raw files are stored outside the project."""
    return (HOLDOUT_DIR / "raw") if in_holdout(d) else RAW


def clean_dir() -> Path:
    """Research code sees data/clean (ends before the holdout). Production sees its own panel."""
    return (PROD_DIR / "clean") if is_production() else CLEAN


def assert_production(what: str) -> None:
    if not is_production():
        raise HoldoutViolation(f"{what} is production-only: it contains holdout-window data")


def assumed_available_at(d: date) -> datetime:
    return datetime.combine(d, ASSUMED_EOD_PUBLISH, tzinfo=IST)
