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

from . import config
from .models import HORIZONS, MODELS, VERSION
from .panel import Panel

COLUMNS = ["created_at_ist", "run_id", "asof_date", "model", "model_version", "code_commit",
           "sid", "symbol", "score", "rank_pct", "p_beat_1d", "p_beat_5d", "p_beat_20d"]
CALIBRATION = config.PROJECT / "models" / f"baselines_{VERSION}.json"


class StalePrediction(RuntimeError):
    """The prediction would be written after its outcome window may have started."""


def load_calibration(path: Path = CALIBRATION) -> dict:
    """slope[model][horizon]: p_beat = 0.5 + slope * (rank_pct - 0.5). Zero slope if no file."""
    if path.exists():
        return json.loads(path.read_text())["slopes"]
    return {m: {str(h): 0.0 for h in HORIZONS} for m in MODELS}


def assert_fresh(asof: pd.Timestamp, created_at: datetime) -> None:
    """Entry is at the open of the session after `asof`. The earliest that can be is
    09:00 IST on the next calendar day, so a prediction must exist before then."""
    deadline = datetime.combine(asof.date() + timedelta(days=1), time(9, 0), tzinfo=config.IST)
    if created_at >= deadline:
        raise StalePrediction(f"as-of {asof.date()} can no longer be predicted at {created_at:%Y-%m-%d %H:%M} IST")


def make_predictions(panel: Panel, i: int, created_at: datetime, run_id: str, code_commit: str,
                     slopes: dict | None = None) -> pd.DataFrame:
    slopes = slopes or load_calibration()
    view = panel.view(i)
    cols = panel.members(i)
    cols = cols[panel.traded[i, cols]]          # must have traded today to be ranked
    sym = panel.symbols_on(i)
    frames = []
    for name, fn in MODELS.items():
        s = fn(view)[cols]
        ok = np.isfinite(s)
        c, s = cols[ok], s[ok]
        if len(s) == 0:
            continue
        rank_pct = (pd.Series(s).rank(method="average").to_numpy() - 0.5) / len(s)
        sids = panel.sids[c]
        f = pd.DataFrame({
            "created_at_ist": created_at.strftime("%Y-%m-%d %H:%M:%S"), "run_id": run_id,
            "asof_date": panel.dates[i].strftime("%Y-%m-%d"), "model": name, "model_version": VERSION,
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
