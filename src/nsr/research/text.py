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
from .data import TEXT_DIR

_AN = re.compile(r"^(.{2,150}?)\s{2,}([A-Z0-9&\-\.\*]{1,12})\s*: (.*)$")
_BM = re.compile(r"^(.{2,150}?)\s{2,}([A-Z0-9&\-\.\*]{1,12})\s*: (\d{2}-[A-Za-z]{3}-\d{4}) : (.*)$")
_SKIP = re.compile(r"^\s*Declaration of NAV", re.I)
MAX_TEXT = 700


def _member(zf, prefix: str) -> str | None:
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


def parse_day(d: date) -> tuple[list[tuple], list[tuple]]:
    zf = parse.open_pr(d)
    if zf is None:
        return [], []
    an_raw, bm_raw = _member(zf, "an"), _member(zf, "bm")
    an = [(d, s, " ".join(t.split())[:MAX_TEXT]) for s, t in split_records(an_raw, _AN) if not _SKIP.match(t)] if an_raw else []
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
