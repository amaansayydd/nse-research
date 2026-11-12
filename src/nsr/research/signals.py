"""Signals under test. Each is registered in research_log.md before its first run.

Dense signals return a [session, column] score array (NaN = no opinion); event
signals return a frame with columns i (session the event became known) and col.
Row t may use only rows <= t and table records with known <= session t.
"""
from __future__ import annotations

import re
import warnings

import numpy as np
import pandas as pd

from .data import ResearchData
from .features import roll_corr


# ------------------------------------------------------------------ T-0001
def deliv_ret_corr(rd: ResearchData, window: int = 60, min_obs: int = 40, clip: float = 0.10) -> np.ndarray:
    """Trailing correlation between a stock's daily return and its delivery share, both taken
    relative to that day's cross-sectional median. High = it rises on days when more of its
    volume is taken for delivery and falls on days dominated by intraday trading."""
    f = rd.fields
    with np.errstate(divide="ignore", invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        share = np.clip(f["deliv_qty"] / f["mto_qty"], 0.0, 1.0)
        ret = rd.panel.ret_cc.astype(np.float64)
        x = share - np.nanmedian(share, axis=1, keepdims=True)
        y = np.clip(ret - np.nanmedian(ret, axis=1, keepdims=True), -clip, clip)
    return roll_corr(x, y, window, min_obs)


# ------------------------------------------------------------------ T-0002
RESULTS = re.compile(r"result", re.I)
MAX_LEAD_DAYS, RESCHEDULE_DAYS = 60, 20


def results_meetings(rd: ResearchData) -> pd.DataFrame:
    """Board meetings called to consider financial results: one row per (column, meeting date),
    from notices filed on or before the meeting. A meeting is dropped if a later notice, filed
    on or before that meeting date, names a different date within 20 days (a reschedule)."""
    bm = rd.tables["board_meetings"]
    lead = (bm.meeting - bm.known).dt.days
    bm = bm[bm.purpose.str.contains(RESULTS) & (lead >= 0) & (lead <= MAX_LEAD_DAYS)]
    bm = bm.sort_values("known").drop_duplicates(["symbol", "meeting"])[["known", "symbol", "meeting"]]
    pair = bm.merge(bm, on="symbol", suffixes=("", "_2"))
    gap = (pair.meeting_2 - pair.meeting).dt.days.abs()
    moved = pair[(pair.known_2 > pair.known) & (pair.known_2 <= pair.meeting) & (gap > 0) & (gap <= RESCHEDULE_DAYS)]
    bm = bm.merge(moved[["symbol", "meeting"]].drop_duplicates().assign(moved=True), on=["symbol", "meeting"], how="left")
    bm = bm[bm.moved.isna()].drop(columns="moved")
    bm["col"] = rd.symbol_columns(bm.known, bm.symbol)
    return bm[bm.col >= 0].drop_duplicates(["col", "meeting"]).reset_index(drop=True)


def ear_drift(rd: ResearchData, hold: int = 60, days: int = 2) -> np.ndarray:
    """Most recent results-day reaction: the stock's return minus the universe's mean return,
    summed over the first `days` sessions on or after the board meeting. The score is carried
    for `hold` sessions from the evening the reaction window closes."""
    p = rd.panel
    T = len(p.dates)
    ret = p.ret_cc.astype(np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mkt = np.nanmean(np.where(rd.member & p.traded, ret, np.nan), axis=1)
    ev = results_meetings(rd)
    e1 = np.searchsorted(p.dates, ev.meeting.to_numpy(), side="left")
    last = e1 + days - 1
    keep = last < T
    e1, last, col = e1[keep], last[keep], ev.col.to_numpy()[keep]
    S = np.full(ret.shape, np.nan)
    for k in np.argsort(last, kind="stable"):
        rows = np.arange(e1[k], last[k] + 1)
        r = ret[rows, col[k]]
        if not (p.traded[rows, col[k]].all() and np.isfinite(r).all() and np.isfinite(mkt[rows]).all()):
            continue
        S[last[k]: last[k] + hold, col[k]] = float((r - mkt[rows]).sum())
    return S


# ------------------------------------------------------------------ T-0003
_VERB = r"\b(?:bag\w*|secure[sd]?|securing|receiv\w+|receipt|award\w*|won|wins?|winning|obtain\w*|clinch\w*|grab\w*)\b"
_OBJ = r"(?<!in )\b(?:orders?|contracts?|l\.?o\.?a\.?|letters? of (?:award|intent|acceptance))\b"
ORDER_WIN = re.compile(_VERB + r".{0,80}?" + _OBJ, re.I)
ORDER_EXCLUDE = re.compile(
    r"court|tribunal|\bnclt|\bnclat|\bsebi\b|hon'?ble|arbitra|\btax|\bgst\b|penalt|adjudicat|show cause|assessment"
    r"|appeal|insolvency|liquidat|scheme of|amalgamat|de-?merger|postal ballot|trading window|record date|book closure"
    r"|\besop|allot|debenture|\brating|commissioner|regulatory commission|registrar|\bwrit\b|petition|litigation|dispute"
    r"|order of the|orders? passed|(?<!purchase )(?<!work )(?<!supply )order dated"
    r"|award\w* (?:of )?.{0,40}(?:contracts?|orders?) to (?:m/s|messrs)|clarification|outcome of board|disclosure under",
    re.I)


def is_order_win(text: str) -> bool:
    return bool(ORDER_WIN.search(text)) and not ORDER_EXCLUDE.search(text)


def order_win_events(rd: ResearchData, cooldown: int = 5) -> pd.DataFrame:
    """Announcements that the company has won an order or contract, for universe members.
    One event per stock per session; a stock with an event in the previous `cooldown` sessions is skipped."""
    an = rd.tables["announcements"]
    hit = an[an.text.str.contains(ORDER_WIN) & ~an.text.str.contains(ORDER_EXCLUDE)]
    ev = pd.DataFrame({"i": rd.dates.get_indexer(hit.known), "col": rd.symbol_columns(hit.known, hit.symbol),
                       "symbol": hit.symbol.to_numpy()})
    ev = ev[(ev.i >= 0) & (ev.col >= 0)]
    ev = ev[rd.member[ev.i.to_numpy(), ev.col.to_numpy()] & rd.panel.traded[ev.i.to_numpy(), ev.col.to_numpy()]]
    ev = ev.drop_duplicates(["i", "col"]).sort_values(["col", "i"])
    if cooldown:
        keep, last = [], {}
        for i, c in zip(ev.i.to_numpy(), ev.col.to_numpy()):
            keep.append(i - last.get(c, -10 ** 9) > cooldown)
            if keep[-1]:
                last[c] = i
        ev = ev[np.array(keep, dtype=bool)]
    return ev.sort_values(["i", "col"]).reset_index(drop=True)


def events_matrix(rd: ResearchData, ev: pd.DataFrame) -> np.ndarray:
    """1 where an event was flagged, 0 elsewhere (used by the look-ahead test)."""
    M = np.zeros(rd.member.shape)
    M[ev.i.to_numpy(), ev.col.to_numpy()] = 1.0
    return M
