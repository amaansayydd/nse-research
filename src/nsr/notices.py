"""Board-meeting notices from the daily bundles (`Bm*.txt`), for signals that
need to know when a company's results meeting is.

A notice printed in the bundle for trade date D is usable from the evening of D:
the `known` column is D. Files are opened through `parse.open_pr`, so the holdout
guard applies: only the production run can read holdout-window bundles.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd

from . import parse

# Until 2025-10-10 the company name was padded from the ticker by several spaces; since then NSE
# prints a single space. One or more spaces reads both: on every bundle up to 2025-10-10 it gives
# exactly the records the old two-space rule gave (checked 2026-11-13, 122,539 records).
BM = re.compile(r"^(.{2,150}?)\s+([A-Z0-9&\-\.\*]{1,12})\s*: (\d{2}-[A-Za-z]{3}-\d{4}) : (.*)$")
MAX_TEXT = 700
COLUMNS = ["known", "symbol", "meeting", "purpose"]
# A score may rest on a meeting up to ~62 sessions back, on notices filed up to 60 days before
# it, and on rival notices for meetings within 20 days of it. 240 calendar days covers all three.
LOOKBACK_DAYS = 240


def member(zf, prefix: str) -> str | None:
    for n in zf.namelist():
        base = n.rsplit("/", 1)[-1].lower()
        if base.startswith(prefix) and base.endswith(".txt"):
            return zf.read(n).decode("latin-1")
    return None


def split_records(raw: str, pattern: re.Pattern) -> list[tuple]:
    """A record starts on a line shaped like 'Company Name    SYMBOL : ...'; other lines continue it."""
    out: list[list] = []
    for line in raw.splitlines()[1:]:
        m = pattern.match(line)
        if m:
            out.append(list(m.groups()[1:]))
        elif out and line.strip():
            out[-1][-1] += " " + line.strip()
    return [tuple(r) for r in out]


def bm_records(raw: str | None, d: date) -> list[tuple]:
    return [(d, s, m, " ".join(t.split())[:MAX_TEXT]) for s, m, t in split_records(raw, BM)] if raw else []


def parse_bm(d: date) -> list[tuple]:
    zf = parse.open_pr(d)
    return bm_records(member(zf, "bm"), d) if zf is not None else []


def frame(records: list[tuple]) -> pd.DataFrame:
    bm = pd.DataFrame(records, columns=COLUMNS)
    bm["known"] = pd.to_datetime(bm.known)
    bm["meeting"] = pd.to_datetime(bm.meeting, format="%d-%b-%Y", errors="coerce")
    return bm.dropna(subset=["meeting"]).reset_index(drop=True)


def window(bm: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Notices known by `asof` and filed within the lookback."""
    return bm[(bm.known <= asof) & (bm.known > asof - pd.Timedelta(days=LOOKBACK_DAYS))]


def recent(sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    """Parse the bundles of the sessions inside the lookback that ends at the last session.
    Also returns coverage counts for the run log."""
    asof = sessions[-1]
    days = [d.date() for d in sessions[sessions > asof - pd.Timedelta(days=LOOKBACK_DAYS)]]
    per_day = [parse_bm(d) for d in days]
    bm = frame([r for recs in per_day for r in recs])
    return bm, {"sessions": len(days), "sessions_without_notices": sum(1 for r in per_day if not r), "notices": len(bm)}
