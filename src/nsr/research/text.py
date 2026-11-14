"""Announcement and board-meeting text from the daily bundles.

Each bundle for trade date D carries `An*.txt` (announcements) and `Bm*.txt`
(forthcoming board meetings). A record is usable from the evening of D: the
`known` column is D. Only text is read here; no prices.
"""
from __future__ import annotations

import re
from concurrent.futures import ProcessPoolExecutor
from datetime import date

import pandas as pd

from .. import config, parse
from ..notices import BM as _BM, MAX_TEXT, member as _member, split_records   # one parser for backtest and live
from .data import TEXT_DIR

# Until 2025-10-10 the company name was padded from the ticker by two or more spaces. Since
# 2025-10-13 there is one space, so a record start is 'Name TICKER : text' and the ticker must hold
# a letter (a continuation line such as '... dated 31.12.2024: ...' is not a start). Old files keep
# the old rule, so every record up to 2025-10-10 is unchanged.
_AN = re.compile(r"^(.{2,150}?)\s{2,}([A-Z0-9&\-\.\*]{1,12})\s*: (.*)$")
_AN_NEW = re.compile(r"^(.{2,150}?)\s+((?=[0-9&\-\.\*]*[A-Z])[A-Z0-9&\-\.\*]{1,12})\s*: (.*)$")
_SKIP = re.compile(r"^\s*Declaration of NAV", re.I)


def an_pattern(raw: str) -> re.Pattern:
    """The rule for this file's layout: padded if at least half of the lines that could start a
    record are padded (old files: all of them; new files: about 1 in 500)."""
    lines = raw.splitlines()[1:]
    padded = sum(1 for line in lines if _AN.match(line))
    return _AN if 2 * padded >= sum(1 for line in lines if _AN_NEW.match(line)) else _AN_NEW


def an_records(raw: str | None, d: date) -> list[tuple]:
    if not raw:
        return []
    return [(d, s, " ".join(t.split())[:MAX_TEXT]) for s, t in split_records(raw, an_pattern(raw)) if not _SKIP.match(t)]


def parse_day(d: date) -> tuple[list[tuple], list[tuple]]:
    zf = parse.open_pr(d)
    if zf is None:
        return [], []
    an_raw, bm_raw = _member(zf, "an"), _member(zf, "bm")
    an = an_records(an_raw, d)
    bm = [(d, s, m, " ".join(t.split())[:MAX_TEXT]) for s, m, t in split_records(bm_raw, _BM)] if bm_raw else []
    return an, bm


def build(workers: int = 6) -> dict:
    """Parse every research-window bundle into two parquet tables under data/clean/research_text."""
    px_days = pd.read_parquet(config.CLEAN / "prices.parquet", columns=["date"]).date.drop_duplicates().sort_values()
    days = [x.date() for x in px_days]
    with ProcessPoolExecutor(workers) as ex:
        res = list(ex.map(parse_day, days, chunksize=40))
    an = pd.DataFrame([r for a, _ in res for r in a], columns=["known", "symbol", "text"])
    bm = pd.DataFrame([r for _, b in res for r in b], columns=["known", "symbol", "meeting", "purpose"])
    an["known"], bm["known"] = pd.to_datetime(an.known), pd.to_datetime(bm.known)
    bm["meeting"] = pd.to_datetime(bm.meeting, format="%d-%b-%Y", errors="coerce")
    bm = bm.dropna(subset=["meeting"])
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    an.to_parquet(TEXT_DIR / "announcements.parquet", index=False)
    bm.to_parquet(TEXT_DIR / "board_meetings.parquet", index=False)
    return {"days": len(days), "announcements": len(an), "board_meetings": len(bm),
            "announcements_by_year": an.groupby(an.known.dt.year).size().to_dict(),
            "board_meetings_by_year": bm.groupby(bm.known.dt.year).size().to_dict()}


if __name__ == "__main__":
    import json
    print(json.dumps(build(), indent=1, default=str))
