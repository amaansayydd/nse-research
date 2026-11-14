"""Observed signals (research_log.md, Phase 3 rules v1.1).

An observed signal is logged forward in the same daily run as the baselines and challengers,
but it holds no shadow slot, cannot become champion and does not count in N. This module is
the whole of that tier: the event model, its rows in predictions.csv, the log of evaluations,
event scoring and the checkpoint status.

Nothing here can stop or change a baseline or a challenger. The daily run calls `step` after
their predictions are written and inside a try block.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import champion, config, predict
from .costs import CostModel
from .models import HORIZONS
from .panel import Panel, View
from .universe import members_asof

RUNS = config.PROJECT / "observed_runs.csv"
EVENT_SCORES = config.PROJECT / "event_scores.csv"
STATE = config.PROJECT / "observed.json"
CALIBRATION = config.CODE / "models" / "observed_v1.json"
RUN_COLUMNS = ["asof_date", "model", "model_version", "flagged", "created_at_ist", "run_id", "code_commit"]
EVENT_COLUMNS = ["asof_date", "model", "model_version", "symbol", "horizon", "ret", "universe_ret", "excess",
                 "excess_late", "mom_tenth_ret", "uni_rank", "scored_through"]
MAX_OBSERVED = 10
MIN_EVENTS = 200                     # an event signal needs this many scored events as well as 250 sessions
COST = CostModel().round_trip_rate(50_000.0)     # one round trip under the Phase 1 cost model
LIQ_BUCKETS = (("rank 1-100", 1, 100), ("rank 101-250", 101, 250), ("rank 251-500", 251, 500))

# ---------------------------------------------------------------- T-0008: early results date
NAME = "results_advance_5d"
NOTICE_TABLE = "board_meetings_long"   # board-meeting notices of the last 520 days
NOTICE_DAYS = 520                      # the base-year notice can be up to 500 days older than this year's
RESULTS = re.compile(r"result", re.I)
MAX_LEAD_DAYS = 60                     # a notice more than this far ahead of the meeting is ignored
MAX_LAG_DAYS = 75                      # a results meeting later than this after the quarter end is not that quarter's
MIN_DAYS = 7                           # days earlier than a year before, after the peer step
MIN_PEERS = 30
_EMPTY = pd.DataFrame({"col": pd.Series(dtype=np.int64), "score": pd.Series(dtype=float)})


def results_calendar(v: View) -> pd.DataFrame:
    """One row per stock and calendar quarter: the first notice of its results board meeting
    (`known`, `lag` = days from quarter end to the date first announced) and `final_lag`, the
    date in the last notice filed for that quarter."""
    bm = v.tables.get(NOTICE_TABLE)
    if bm is None or bm.empty:
        return pd.DataFrame(columns=["col", "qend", "known", "meeting", "lag", "final_lag"])
    lead = (bm.meeting - bm.known).dt.days
    r = bm[bm.purpose.str.contains(RESULTS) & (lead >= 0) & (lead <= MAX_LEAD_DAYS)][["known", "symbol", "meeting"]].copy()
    r["col"] = v.symbol_columns(r.known, r.symbol) if len(r) else np.empty(0, dtype=np.int64)
    r = r[r.col >= 0]
    r["qend"] = r.meeting.dt.to_period("Q").dt.start_time - pd.Timedelta(days=1)
    r["lag"] = (r.meeting - r.qend).dt.days
    r = r[r.lag <= MAX_LAG_DAYS].sort_values(["col", "qend", "known", "meeting"], kind="stable")
    g = r.groupby(["col", "qend"], sort=False)
    out = g.first().reset_index()[["col", "qend", "known", "meeting", "lag"]]
    out["final_lag"] = g.lag.last().to_numpy()
    return out


def results_advance(v: View) -> pd.DataFrame:
    """T-0008. Stocks whose results board meeting was first notified this evening for a date at
    least 7 days earlier in the quarter than a year before, after taking off the median shift of
    the universe members whose notice for the same quarter is known by now (30 or more, the stock
    included). Universe member, traded today, meeting still ahead. Returns the panel column and
    score = days early after the peer step. Same definition as research.signals.results_date_shift."""
    cal = results_calendar(v)
    today = len(v.dates) - 1
    if cal.empty or not (cal.known == v.asof).any():
        return _EMPTY.copy()
    base = cal[["col", "qend", "final_lag"]].assign(qend=lambda d: d.qend + pd.DateOffset(years=1)).rename(columns={"final_lag": "base_lag"})
    base["qend"] = base.qend + pd.offsets.QuarterEnd(0)
    c = cal.merge(base, on=["col", "qend"])
    c = c[c.qend.isin(c.qend[c.known == v.asof])]
    c["i"] = v.dates.get_indexer(c.known)
    c = c[c.i >= 0]
    member = np.zeros(len(c), dtype=bool)
    rows, cols = c.i.to_numpy(), c.col.to_numpy()
    for i in np.unique(rows):
        at = rows == i
        member[at] = v.member_mask(int(i))[cols[at]]
    c = c[member].copy()
    c["shift"] = (c.lag - c.base_lag).astype(float)
    mine = c[c.i == today].sort_values(["qend", "col"], kind="stable")
    out = []
    for q, g in mine.groupby("qend", sort=True):
        seen = c["shift"].to_numpy()[(c.qend == q).to_numpy()]
        if len(seen) < MIN_PEERS:
            continue
        abnormal = g["shift"].to_numpy() - np.median(seen)
        ok = (abnormal <= -MIN_DAYS) & (g.meeting > g.known).to_numpy() & v.traded[today, g.col.to_numpy()]
        out.append(pd.DataFrame({"col": g.col.to_numpy()[ok], "score": -abnormal[ok]}))
    if not out:
        return _EMPTY.copy()
    return pd.concat(out, ignore_index=True).drop_duplicates("col").sort_values("col").reset_index(drop=True)


SIGNALS = {NAME: {"fn": results_advance, "h": 5, "version": "v1", "kind": "event", "trial": "T-0008"}}
assert len(SIGNALS) <= MAX_OBSERVED, "at most 10 observed signals at a time"


# ---------------------------------------------------------------- state and logs
def load_state(path: Path | None = None) -> dict:
    path = path or STATE
    return {"ever_observed": [], "dropped": [], **(json.loads(path.read_text()) if path.exists() else {})}


def load_calibration(path: Path | None = None) -> dict:
    path = path or CALIBRATION
    return json.loads(path.read_text())["p_beat"] if path.exists() else {}


def _read(path: Path, columns: list[str]) -> pd.DataFrame:
    if path.exists() and path.stat().st_size:
        return pd.read_csv(path, dtype={"asof_date": str, "model": str, "symbol": str})
    return pd.DataFrame(columns=columns)


def load_runs(path: Path | None = None) -> pd.DataFrame:
    return _read(path or RUNS, RUN_COLUMNS)


def load_event_scores(path: Path | None = None) -> pd.DataFrame:
    return _read(path or EVENT_SCORES, EVENT_COLUMNS)


def _append(df: pd.DataFrame, path: Path) -> int:
    if df.empty:
        return 0
    df.to_csv(path, mode="a", header=not (path.exists() and path.stat().st_size), index=False)
    return len(df)


# ---------------------------------------------------------------- predictions
def event_rows(panel: Panel, i: int, name: str, flags: pd.DataFrame, created_at: datetime, run_id: str,
               code_commit: str, p_beat: dict | None = None) -> pd.DataFrame:
    """Rows for predictions.csv: one per flagged name. rank_pct is 1 (flagged); p_beat is the
    frozen share of research events that beat the universe median at that horizon."""
    if flags.empty:
        return pd.DataFrame(columns=predict.COLUMNS)
    sids = panel.sids[flags.col.to_numpy()]
    f = pd.DataFrame({
        "created_at_ist": created_at.strftime("%Y-%m-%d %H:%M:%S"), "run_id": run_id,
        "asof_date": panel.dates[i].strftime("%Y-%m-%d"), "model": name, "model_version": SIGNALS[name]["version"],
        "code_commit": code_commit, "sid": sids, "symbol": panel.symbols_on(i).reindex(sids).to_numpy(),
        "score": np.round(flags.score.to_numpy(), 6), "rank_pct": 1.0,
    })
    for h in HORIZONS:
        f[f"p_beat_{h}d"] = round(float((p_beat or {}).get(name, {}).get(str(h), 0.5)), 4)
    return f.sort_values("symbol")[predict.COLUMNS].reset_index(drop=True)


def step(panel: Panel, now: datetime, run_id: str, code_commit: str, notes: list[str], dry_run: bool = False,
         predictions: Path | None = None, runs: Path | None = None, state: dict | None = None, i: int | None = None) -> int:
    """Evaluate every observed signal for the latest session (or session `i` in a replay), once.
    Writes its rows (if any) to predictions.csv and one line to observed_runs.csv, so a session
    with no event is still on record as evaluated. A failure is noted and swallowed. Returns the
    prediction rows written. The caller decides whether the session is in the forward period."""
    predictions, runs = predictions or config.PREDICTIONS, runs or RUNS
    state = state or load_state()
    i = len(panel.dates) - 1 if i is None else i
    key, written = panel.dates[i].strftime("%Y-%m-%d"), 0
    for name, spec in SIGNALS.items():
        if name in state["dropped"]:
            continue
        try:
            flags = spec["fn"](panel.view(i))
            if dry_run:
                notes.append(f"observed {name}: would flag {len(flags)} names")
                continue
            done = load_runs(runs)
            if ((done.asof_date == key) & (done.model == name)).any():
                continue
            predict.assert_fresh(panel.dates[i], now)
            df = event_rows(panel, i, name, flags, now, run_id, code_commit, load_calibration())
            if len(df) and (key, name) not in predict.existing_keys(predictions):
                predict.append_predictions(df, predictions)
                written += len(df)
            _append(pd.DataFrame([{"asof_date": key, "model": name, "model_version": spec["version"], "flagged": len(df),
                                   "created_at_ist": now.strftime("%Y-%m-%d %H:%M:%S"), "run_id": run_id,
                                   "code_commit": code_commit}])[RUN_COLUMNS], runs)
            if len(df):
                notes.append(f"{name} flagged {len(df)}")
        except predict.StalePrediction:
            continue
        except Exception as e:
            notes.append(f"observed {name} failed ({type(e).__name__}: {str(e)[:80]}); nothing logged for it today")
    return written


# ---------------------------------------------------------------- scoring
def done_keys(path: Path | None = None) -> set[tuple[str, str, int]]:
    s = load_event_scores(path)
    return set(zip(s.asof_date, s.model, s.horizon.astype(int))) if len(s) else set()


def score_events(panel: Panel, preds: pd.DataFrame, done: set[tuple[str, str, int]], upto: int | None = None) -> pd.DataFrame:
    """Per flagged name and horizon: return from the open of session t+1 over h sessions, minus
    the equal-weight mean of universe members over the same window. `excess_late` is the same
    for an entry one session later. A (date, signal, horizon) is scored once session t+2+h
    exists, so both numbers are written together. `mom_tenth_ret` is the mean return of the
    names in the same tenth of `mom_12_1` that day (NaN if the name has no momentum rank)."""
    upto = len(panel.dates) - 1 if upto is None else upto
    rows = []
    ev = preds[preds.model.isin(list(SIGNALS))]
    for (asof, model), g in ev.groupby(["asof_date", "model"], sort=True):
        i = panel.dates.get_indexer([pd.Timestamp(asof)])[0]
        if i < 0:
            continue
        on = panel.symbols_on(int(i))
        s2s = pd.Series(on.index, index=on.to_numpy())
        sid = s2s.reindex(g.symbol.to_numpy()).to_numpy()
        have = ~pd.isna(sid)
        col = np.full(len(g), -1, dtype=np.int64)
        col[have] = panel.col(sid[have].astype(np.int64))
        uni = members_asof(panel.uni, panel.dates[i])
        rank = pd.Series(uni["rank"].to_numpy(float), index=panel.col(uni.sid.to_numpy()))
        mom = preds[(preds.asof_date == asof) & (preds.model == "mom_12_1")]
        mom_sid = s2s.reindex(mom.symbol.to_numpy()).to_numpy()
        mok = ~pd.isna(mom_sid)
        mom_col = panel.col(mom_sid[mok].astype(np.int64))
        mom_tenth = np.minimum((mom.rank_pct.to_numpy()[mok] * 10).astype(int), 9)
        tenth_of = dict(zip(mom_col, mom_tenth))
        for h in HORIZONS:
            if (asof, model, h) in done or i + 2 + h > upto:
                continue
            real, late = panel.realized(int(i), h), panel.realized(int(i) + 1, h)
            base = _nanmean(real[panel.members(int(i))])
            base_late = _nanmean(late[panel.members(int(i) + 1)])
            by_tenth = {t: _nanmean(real[mom_col[mom_tenth == t]]) for t in np.unique(mom_tenth)}
            for k, sym in enumerate(g.symbol.to_numpy()):
                c = col[k]
                r = real[c] if c >= 0 else np.nan
                rl = late[c] if c >= 0 else np.nan
                rows.append({"asof_date": asof, "model": model, "model_version": g.model_version.iloc[0], "symbol": sym,
                             "horizon": h, "ret": r, "universe_ret": base, "excess": r - base, "excess_late": rl - base_late,
                             "mom_tenth_ret": by_tenth.get(tenth_of.get(c, -1), np.nan),
                             "uni_rank": rank.get(c, np.nan),
                             "scored_through": panel.dates[i + 2 + h].strftime("%Y-%m-%d")})
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _nanmean(a: np.ndarray) -> float:
    a = a[np.isfinite(a)]
    return float(a.mean()) if len(a) else float("nan")


def append_event_scores(df: pd.DataFrame, path: Path | None = None) -> int:
    return _append(df.round(6), path or EVENT_SCORES)


# ---------------------------------------------------------------- the forward test
def cluster_t(values: np.ndarray, clusters: np.ndarray) -> dict:
    """Mean with a standard error that lets observations in the same cluster (calendar month)
    be arbitrarily correlated. Same formula as research.stats.cluster_t."""
    values, clusters = np.asarray(values, dtype=float), np.asarray(clusters)
    ok = np.isfinite(values)
    values, clusters = values[ok], clusters[ok]
    n = len(values)
    if n < 3:
        return {"n": n, "clusters": 0, "mean": float("nan"), "t": float("nan")}
    mean = float(values.mean())
    _, inv = np.unique(clusters, return_inverse=True)
    resid = np.bincount(inv, weights=values - mean)
    g = len(resid)
    se = math.sqrt(float((resid ** 2).sum()) * g / max(g - 1, 1)) / n
    return {"n": n, "clusters": g, "mean": mean, "t": mean / se if se > 0 else float("nan")}


def _month(asof: pd.Series) -> np.ndarray:
    d = pd.to_datetime(asof)
    return (d.dt.year * 12 + d.dt.month).to_numpy()


def status(name: str, event_scores: pd.DataFrame, runs: pd.DataFrame, scores: pd.DataFrame, m_ever: int,
           matured_through: str) -> dict:
    """Where an observed event signal stands. Sessions = evenings it was evaluated whose scoring
    window has closed (`matured_through` is the last such as-of date). The label is read only at
    250, 375, 500 ... sessions, on the events up to that checkpoint."""
    h = SIGNALS[name]["h"]
    need = champion.threshold(m_ever)
    sess = sorted(runs.asof_date[(runs.model == name) & (runs.asof_date <= matured_through)].unique())
    n_sess, cp = len(sess), champion.checkpoint(len(sess))
    cut = sess[cp - 1] if cp else (sess[-1] if sess else "")
    e = event_scores[(event_scores.model == name) & (event_scores.horizon == h) & (event_scores.asof_date <= cut)]
    e = e.astype({c: float for c in ("excess", "excess_late", "ret", "mom_tenth_ret", "uni_rank")})
    e = e[np.isfinite(e.excess)]
    ct = cluster_t(e.excess.to_numpy(), _month(e.asof_date)) if len(e) else {"n": 0, "clusters": 0, "mean": np.nan, "t": np.nan}
    late = e.excess_late[np.isfinite(e.excess_late)]
    out = {"signal": name, "horizon": h, "sessions": n_sess, "judged_on_sessions": cp or n_sess, "events": int(ct["n"]),
           "mean_excess": ct["mean"], "t": ct["t"], "required_t": need,
           "after_costs": ct["mean"] - COST if ct["n"] else np.nan,
           "after_costs_one_session_later": float(late.mean() - COST) if len(late) else np.nan,
           "hit_rate": float((e.excess > 0).mean()) if len(e) else np.nan,
           "median_excess": float(e.excess.median()) if len(e) else np.nan,
           "mean_minus_momentum_tenth": float((e.ret - e.mom_tenth_ret).mean()) if e.mom_tenth_ret.notna().any() else np.nan}
    for label, a, b in LIQ_BUCKETS:
        out[f"mean_excess_{label.replace(' ', '_')}"] = float(e.excess[(e.uni_rank >= a) & (e.uni_rank <= b)].mean()) if len(e) else np.nan
    if not cp:
        out["status"] = f"too early: {n_sess} of {champion.MIN_SESSIONS} sessions, {ct['n']} of {MIN_EVENTS} events"
        return out
    ctl = scores[(scores.model == "random") & (scores.asof_date <= cut)] if len(scores) else scores
    control_ok = all(not (abs(champion._t(g.ic.to_numpy(), int(hh))) >= 3) for hh, g in ctl.groupby("horizon"))
    met = (ct["n"] >= MIN_EVENTS and ct["t"] >= need and out["after_costs"] > 0 and out["after_costs_one_session_later"] > 0)
    if not control_ok:
        out["status"] = "frozen: the random control shows skill, audit the scorer"
    elif met:
        out["status"] = "CONFIRMED FORWARD at this checkpoint: may be proposed for a use (a new registration)"
    elif cp >= champion.FUTILITY_SESSIONS and not ct["t"] >= champion.FUTILITY_T:
        out["status"] = "futile: drop from the run and write a postmortem"
    elif ct["n"] < MIN_EVENTS:
        out["status"] = f"not met at {cp}: {ct['n']} of {MIN_EVENTS} events; next checkpoint at {cp + champion.CHECK_EVERY}"
    else:
        out["status"] = f"not met at {cp}; next checkpoint at {cp + champion.CHECK_EVERY}"
    return out


def table(panel: Panel, event_scores: pd.DataFrame, runs: pd.DataFrame, scores: pd.DataFrame, state: dict) -> pd.DataFrame:
    """One row per observed signal that is still running."""
    rows, runs = [], predict.drop_void(runs)          # a voided evaluation is not a session
    for name, spec in SIGNALS.items():
        if name in state["dropped"]:
            continue
        last = len(panel.dates) - 3 - spec["h"]           # latest as-of session whose window (late entry included) has closed
        through = panel.dates[last].strftime("%Y-%m-%d") if last >= 0 else ""
        rows.append(status(name, event_scores, runs, scores, len(state["ever_observed"]), through))
    return pd.DataFrame(rows)
