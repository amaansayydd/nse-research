"""Generate predictions and append them to the log.

One row per (as-of session, model, security). The score is horizon-free; the
three p_beat columns are the model's probability that the stock beats the
universe median over the next 1, 5 and 20 sessions (open to open, entering at
the next session's open).

predictions.csv is append-only: rows are only ever added, and a (date, model)
pair can be written once.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, ensemble
from .models import ALL_MODELS, ENSEMBLES, HORIZONS, MIN_NAMES, MODELS, ROLES, VERSION, VERSIONS
from .panel import Panel

COLUMNS = ["created_at_ist", "run_id", "asof_date", "model", "model_version", "code_commit",
           "sid", "symbol", "score", "rank_pct", "p_beat_1d", "p_beat_5d", "p_beat_20d"]
CALIBRATION = config.CODE / "models" / f"baselines_{VERSION}.json"
CHALLENGER_CALIBRATION = config.CODE / "models" / "challengers_v1.json"
VOIDS = config.PROJECT / "void_predictions.csv"


class StalePrediction(RuntimeError):
    """The prediction would be written after its outcome window may have started."""


def load_calibration(paths: tuple[Path, ...] | Path | None = None) -> dict:
    """slope[model][horizon]: p_beat = 0.5 + slope * (rank_pct - 0.5). Zero slope if not fitted."""
    paths = (CALIBRATION, CHALLENGER_CALIBRATION) if paths is None else ((paths,) if isinstance(paths, Path) else paths)
    slopes = {m: {str(h): 0.0 for h in HORIZONS} for m in ALL_MODELS}
    for path in paths:
        if path.exists():
            slopes.update(json.loads(path.read_text())["slopes"])
    return slopes


def assert_fresh(asof: pd.Timestamp, created_at: datetime) -> None:
    """Entry is at the open of the session after `asof`. The earliest that can be is
    09:00 IST on the next calendar day, so a prediction must exist before then."""
    deadline = datetime.combine(asof.date() + timedelta(days=1), time(9, 0), tzinfo=config.IST)
    if created_at >= deadline:
        raise StalePrediction(f"as-of {asof.date()} can no longer be predicted at {created_at:%Y-%m-%d %H:%M} IST")


def make_predictions(panel: Panel, i: int, created_at: datetime, run_id: str, code_commit: str,
                     slopes: dict | None = None, only: set[str] | None = None,
                     weights: dict[str, float] | None = None, notes: list[str] | None = None) -> pd.DataFrame:
    """Rows for every model (or just those in `only`) for as-of session i.

    A baseline that fails stops the run. A challenger that fails, or that can rank fewer than
    MIN_NAMES names, is left out for the day with a note: shadow models must never cost the
    baselines their record. `weights` are the ensemble's component weights (equal if None)."""
    slopes = slopes or load_calibration()
    notes = notes if notes is not None else []
    view = panel.view(i)
    cols = panel.members(i)
    cols = cols[panel.traded[i, cols]]          # must have traded today to be ranked
    eligible = np.zeros(len(panel.sids), dtype=bool)
    eligible[cols] = True
    sym = panel.symbols_on(i)

    raw: dict[str, np.ndarray] = {}             # model -> score per column (NaN = no opinion)
    for name, fn in MODELS.items():
        try:
            raw[name] = fn(view)
        except Exception as e:
            if ROLES[name] != "challenger":
                raise
            notes.append(f"{name} failed ({type(e).__name__}: {str(e)[:80]}); no predictions from it today")
    for name, parts in ENSEMBLES.items():
        if only is not None and name not in only:
            continue
        if any(k not in raw for k in parts):
            notes.append(f"{name} skipped: a component is missing")
            continue
        w = weights or ensemble.weights({}, {}, parts)
        raw[name] = ensemble.combine({k: ensemble.rank_pct(raw[k], eligible) for k in parts}, w)

    frames = []
    for name in ALL_MODELS:
        if name not in raw or (only is not None and name not in only):
            continue
        s = raw[name][cols]
        ok = np.isfinite(s)
        c, s = cols[ok], s[ok]
        if len(s) == 0 or (ROLES[name] == "challenger" and len(s) < MIN_NAMES):
            if ROLES[name] == "challenger":
                notes.append(f"{name} silent: only {len(s)} names scored")
            continue
        rank_pct = (pd.Series(s).rank(method="average").to_numpy() - 0.5) / len(s)
        sids = panel.sids[c]
        f = pd.DataFrame({
            "created_at_ist": created_at.strftime("%Y-%m-%d %H:%M:%S"), "run_id": run_id,
            "asof_date": panel.dates[i].strftime("%Y-%m-%d"), "model": name, "model_version": VERSIONS[name],
            "code_commit": code_commit, "sid": sids, "symbol": sym.reindex(sids).to_numpy(),
            "score": np.round(s, 6), "rank_pct": np.round(rank_pct, 5),
        })
        for h in HORIZONS:
            k = float(slopes.get(name, {}).get(str(h), 0.0))
            f[f"p_beat_{h}d"] = np.round(np.clip(0.5 + k * (rank_pct - 0.5), 0.01, 0.99), 4)
        frames.append(f.sort_values("symbol"))
    return pd.concat(frames, ignore_index=True)[COLUMNS] if frames else pd.DataFrame(columns=COLUMNS)


def existing_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    with path.open() as f:
        r = csv.DictReader(f)
        return {(row["asof_date"], row["model"]) for row in r}


def append_predictions(df: pd.DataFrame, path: Path = config.PREDICTIONS) -> int:
    """Append rows. Refuses to write a (date, model) that is already logged, or a changed header."""
    if df.empty:
        return 0
    if path.exists() and path.stat().st_size:
        header = path.open().readline().strip().split(",")
        if header != COLUMNS:
            raise RuntimeError(f"{path.name} header does not match the frozen schema")
        clash = existing_keys(path) & set(zip(df.asof_date, df.model))
        if clash:
            raise RuntimeError(f"predictions already logged for {sorted(clash)[:3]}; the log is append-only")
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        df.to_csv(path, index=False)
    return len(df)


def drop_void(preds: pd.DataFrame, path: Path | None = None) -> pd.DataFrame:
    """Predictions that count. A (date, model) listed in void_predictions.csv stays in the log,
    because the log is append-only, but is never scored or simulated. Rows may be voided only
    for a process failure and only before any outcome for them has been scored (Phase 3 rules)."""
    path = path or VOIDS
    if not path.exists() or preds.empty:
        return preds
    void = set(map(tuple, pd.read_csv(path, dtype=str)[["asof_date", "model"]].to_numpy()))
    keep = [k not in void for k in zip(preds.asof_date, preds.model)]
    return preds[keep]
