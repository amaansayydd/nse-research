"""Score matured predictions.

Target for a prediction made on session t at horizon h: total return from the
open of session t+1 to the open of session t+1+h. A prediction is "matured"
once session t+1+h is in the panel.

Predictions are matched to the panel by (as-of date, symbol), because security
ids are only stable within one build.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .models import HORIZONS
from .panel import Panel

SCORE_COLUMNS = ["asof_date", "model", "model_version", "horizon", "n", "ic", "top_excess", "top_hit",
                 "brier", "universe_ret", "scored_through"]
TOP = 0.9  # top decile by rank_pct


def _rank(a: np.ndarray) -> np.ndarray:
    return pd.Series(a).rank(method="average").to_numpy()


def score_group(panel: Panel, g: pd.DataFrame, i: int, h: int) -> dict | None:
    """Metrics for one (as-of session, model) group at one horizon."""
    sym_to_sid = pd.Series(panel.symbols_on(i).index, index=panel.symbols_on(i).to_numpy())
    sid = sym_to_sid.reindex(g.symbol.to_numpy()).to_numpy()
    have = ~pd.isna(sid)
    real = np.full(len(g), np.nan)
    real[have] = panel.realized(i, h)[panel.col(sid[have].astype(np.int64))]
    ok = np.isfinite(real)
    if ok.sum() < 20:
        return None
    r, rank_pct, p = real[ok], g.rank_pct.to_numpy()[ok], g[f"p_beat_{h}d"].to_numpy()[ok]
    beat = (r > np.median(r)).astype(float)
    top = rank_pct > TOP
    return {
        "n": int(ok.sum()),
        "ic": float(np.corrcoef(_rank(rank_pct), _rank(r))[0, 1]),
        "top_excess": float(r[top].mean() - r.mean()) if top.any() else np.nan,
        "top_hit": float(beat[top].mean()) if top.any() else np.nan,
        "brier": float(np.mean((p - beat) ** 2)),
        "universe_ret": float(r.mean()),
    }


def score_matured(panel: Panel, preds: pd.DataFrame, done: set[tuple[str, str, int]], upto: int | None = None) -> pd.DataFrame:
    """Score every (date, model, horizon) not in `done` whose window is complete by session `upto`."""
    upto = len(panel.dates) - 1 if upto is None else upto
    rows = []
    for (asof, model), g in preds.groupby(["asof_date", "model"], sort=True):
        i = panel.dates.get_indexer([pd.Timestamp(asof)])[0]
        if i < 0:
            continue
        for h in HORIZONS:
            if (asof, model, h) in done or i + 1 + h > upto:
                continue
            m = score_group(panel, g, int(i), h)
            if m:
                rows.append({"asof_date": asof, "model": model, "model_version": g.model_version.iloc[0],
                             "horizon": h, **m, "scored_through": panel.dates[i + 1 + h].strftime("%Y-%m-%d")})
    return pd.DataFrame(rows, columns=SCORE_COLUMNS)


def append_scores(df: pd.DataFrame, path: Path) -> int:
    if df.empty:
        return 0
    df.round(6).to_csv(path, mode="a", header=not (path.exists() and path.stat().st_size), index=False)
    return len(df)


def done_keys(path: Path) -> set[tuple[str, str, int]]:
    if not (path.exists() and path.stat().st_size):
        return set()
    s = pd.read_csv(path, usecols=["asof_date", "model", "horizon"])
    return set(zip(s.asof_date, s.model, s.horizon.astype(int)))


def summarize(scores: pd.DataFrame) -> pd.DataFrame:
    """Per model and horizon. The t-stat divides the sample by the horizon because
    targets of consecutive days overlap: h-day targets give about N/h independent looks."""
    out = []
    for (model, h), g in scores.groupby(["model", "horizon"]):
        n = len(g)
        n_eff = max(n / h, 1.0)
        sd = g.ic.std(ddof=1) if n > 1 else np.nan
        t = g.ic.mean() / sd * math.sqrt(n_eff) if sd and sd > 0 else np.nan
        need = (2 * sd / abs(g.ic.mean())) ** 2 * h if sd and g.ic.mean() != 0 else np.nan
        out.append({"model": model, "horizon": h, "days": n, "eff_obs": round(n_eff, 1),
                    "first": g.asof_date.min(), "last": g.asof_date.max(),
                    "ic_mean": g.ic.mean(), "ic_sd": sd, "ic_t": t,
                    "top_excess_mean": g.top_excess.mean(), "top_hit": g.top_hit.mean(),
                    "brier": g.brier.mean(), "days_for_t2_at_this_ic": need})
    return pd.DataFrame(out)


def calibration_table(panel: Panel, preds: pd.DataFrame, h: int, bins: int = 5) -> pd.DataFrame:
    """Predicted p_beat versus realised beat frequency, pooled over matured days."""
    rows = []
    for (asof, model), g in preds.groupby(["asof_date", "model"]):
        i = panel.dates.get_indexer([pd.Timestamp(asof)])[0]
        if i < 0 or i + 1 + h >= len(panel.dates):
            continue
        s2s = pd.Series(panel.symbols_on(i).index, index=panel.symbols_on(i).to_numpy())
        sid = s2s.reindex(g.symbol.to_numpy()).to_numpy()
        have = ~pd.isna(sid)
        r = np.full(len(g), np.nan)
        r[have] = panel.realized(i, h)[panel.col(sid[have].astype(np.int64))]
        ok = np.isfinite(r)
        if ok.sum() < 20:
            continue
        rows.append(pd.DataFrame({"model": model, "p": g[f"p_beat_{h}d"].to_numpy()[ok],
                                  "beat": (r[ok] > np.median(r[ok])).astype(float)}))
    if not rows:
        return pd.DataFrame()
    d = pd.concat(rows)
    d["bin"] = d.groupby("model").p.transform(lambda s: pd.qcut(s, bins, labels=False, duplicates="drop"))
    return d.groupby(["model", "bin"]).agg(p_mean=("p", "mean"), beat_rate=("beat", "mean"), n=("beat", "size")).reset_index()
