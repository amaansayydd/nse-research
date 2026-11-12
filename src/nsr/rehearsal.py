"""Dress rehearsal: replay the daily cycle over the last two years of research
data, one session at a time, exactly as the live run would have behaved.

This is a PIPELINE TEST. Its numbers are not evidence of skill and never go on
the scoreboard. It writes only under rehearsal/, never to predictions.csv.

Also fits the baselines' probability calibration on data that ends before the
rehearsal window (python -m nsr.rehearsal --calibrate).
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, predict, report, score
from .build import build
from .models import HORIZONS, MODELS, VERSION
from .panel import Panel

OUT = config.PROJECT / "rehearsal"
WINDOW_YEARS = 2


def window(panel: Panel) -> tuple[int, int]:
    first = pd.Timestamp(config.HOLDOUT_START) - pd.DateOffset(years=WINDOW_YEARS)
    return int(np.searchsorted(panel.dates, first)), len(panel.dates) - 1


def calibrate(panel: Panel, step: int = 5) -> dict:
    """Slope of P(beat the median) on rank, per model and horizon, from sessions
    that end well before the rehearsal window. Frozen into models/baselines_v1.json."""
    start, _ = window(panel)
    last = start - max(HORIZONS) - 5
    first = int(np.searchsorted(panel.dates, pd.Timestamp("2012-01-01")))
    acc = {m: {h: [0.0, 0.0] for h in HORIZONS} for m in MODELS}
    now = datetime.now(config.IST)
    zero = {m: {str(h): 0.0 for h in HORIZONS} for m in MODELS}
    for i in range(first, last, step):
        df = predict.make_predictions(panel, i, now, "calibration", "-", zero)
        for model, g in df.groupby("model"):
            cols = panel.col(g.sid.to_numpy())
            x = g.rank_pct.to_numpy() - 0.5
            for h in HORIZONS:
                r = panel.realized(i, h)[cols]
                ok = np.isfinite(r)
                y = (r[ok] > np.median(r[ok])).astype(float) - 0.5
                acc[model][h][0] += float(x[ok] @ y)
                acc[model][h][1] += float(x[ok] @ x[ok])
    slopes = {m: {str(h): (0.0 if m == "random" else round(v[0] / v[1], 4)) for h, v in d.items()} for m, d in acc.items()}
    out = {"version": VERSION, "fit_sessions": [str(panel.dates[first].date()), str(panel.dates[last - 1].date())],
           "every_nth_session": step, "note": "p_beat = 0.5 + slope * (rank_pct - 0.5); random is fixed at 0",
           "slopes": slopes}
    predict.CALIBRATION.parent.mkdir(exist_ok=True)
    predict.CALIBRATION.write_text(json.dumps(out, indent=2))
    return out


def replay(panel: Panel, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = window(panel)
    preds_path, scores_path = out / "predictions.csv", out / "scores.csv"
    for p in (preds_path, scores_path):
        p.unlink(missing_ok=True)
    slopes = predict.load_calibration()
    frames, done = {}, set()
    for i in range(start, end + 1):
        created = datetime.combine(panel.dates[i].date(), time(20, 30), tzinfo=config.IST)
        predict.assert_fresh(panel.dates[i], created)
        df = predict.make_predictions(panel, i, created, f"rehearsal-{panel.dates[i]:%Y%m%d}", "rehearsal", slopes)
        predict.append_predictions(df, preds_path)
        frames[i] = df
        # tonight's scoring step: only what has matured using sessions up to tonight
        recent = pd.concat([frames[j] for j in range(max(start, i - max(HORIZONS) - 2), i + 1)])
        new = score.score_matured(panel, recent, done, upto=i)
        score.append_scores(new, scores_path)
        done |= set(zip(new.asof_date, new.model, new.horizon))
    return pd.read_csv(preds_path), pd.read_csv(scores_path)


def check_truncated_rebuild(panel: Panel, preds: pd.DataFrame, n_dates: int) -> list[dict]:
    """Rebuild the whole dataset from raw files as if the world ended on day D,
    predict from that, and compare with what the replay logged for D."""
    start, end = window(panel)
    picks = np.linspace(start + 20, end - 20, n_dates).astype(int)
    results = []
    for i in picks:
        d = panel.dates[i]
        tmp = Path(tempfile.mkdtemp(prefix="nsr_trunc_"))
        try:
            build(end=d.date(), out_dir=tmp)
            small = Panel.load(tmp)
            assert small.dates[-1] == d
            a = predict.make_predictions(small, len(small.dates) - 1, datetime.now(config.IST), "x", "x")
            b = preds[preds.asof_date == d.strftime("%Y-%m-%d")]
            m = a.merge(b, on=["model", "symbol"], how="outer", suffixes=("_trunc", "_replay"), indicator=True)
            both = m[m._merge == "both"]
            results.append({
                "date": str(d.date()), "rows_truncated_build": len(a), "rows_replay": len(b),
                "only_in_one": int((m._merge != "both").sum()),
                "max_abs_score_diff": float((both.score_trunc - both.score_replay).abs().max()),
                "max_abs_rank_diff": float((both.rank_pct_trunc - both.rank_pct_replay).abs().max()),
            })
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return results


def check_poisoned_future(panel: Panel, preds: pd.DataFrame, n_dates: int = 3) -> bool:
    """Overwrite every row after day D with garbage; predictions for D must not move."""
    start, end = window(panel)
    ok = True
    for i in np.linspace(start + 5, end - 30, n_dates).astype(int):
        saved = [a[i + 1:].copy() for a in (panel.ret_cc, panel.ret_on, panel.ret_id, panel.traded)]
        try:
            panel.ret_cc[i + 1:], panel.ret_on[i + 1:], panel.ret_id[i + 1:] = 7.0, 7.0, 7.0
            panel.traded[i + 1:] = False
            a = predict.make_predictions(panel, i, datetime.now(config.IST), "x", "x")
        finally:
            for arr, s in zip((panel.ret_cc, panel.ret_on, panel.ret_id, panel.traded), saved):
                arr[i + 1:] = s
        b = preds[preds.asof_date == panel.dates[i].strftime("%Y-%m-%d")]
        m = a.merge(b, on=["model", "symbol"], suffixes=("_a", "_b"))
        ok &= len(m) == len(a) == len(b) and bool(np.allclose(m.score_a, m.score_b, atol=1e-6))
    return ok


def run(n_rebuild_checks: int = 3) -> dict:
    panel = Panel.load()
    assert panel.dates[-1] < pd.Timestamp(config.HOLDOUT_START), "rehearsal must not see the holdout"
    OUT.mkdir(exist_ok=True)
    start, end = window(panel)
    preds, scores = replay(panel, OUT)
    summ = score.summarize(scores)

    sessions = [d.strftime("%Y-%m-%d") for d in panel.dates[start: end + 1]]
    per_day = preds.groupby(["asof_date", "model"]).size().unstack()
    expected_scores = sum(max(0, len(sessions) - 1 - h) for h in HORIZONS) * len(MODELS)
    rnd = summ[summ.model == "random"]
    try:
        predict.append_predictions(preds[preds.asof_date == sessions[0]], OUT / "predictions.csv")
        append_guard = False
    except RuntimeError:
        append_guard = True
    rebuild = check_truncated_rebuild(panel, preds, n_rebuild_checks) if n_rebuild_checks else []

    checks = {
        "every session has predictions from every model": bool(per_day.reindex(sessions).notna().all().all()),
        "about 500 names ranked per model per day": bool(per_day.min().min() >= 450 and per_day.max().max() <= 500),
        "no duplicate (date, model, symbol) rows": not bool(preds.duplicated(["asof_date", "model", "symbol"]).any()),
        "every matured target was scored, none early": len(scores) == expected_scores,
        "scores never used a session after the run date": bool((scores.scored_through <= sessions[-1]).all()),
        "log refuses a second write for the same day": append_guard,
        "predictions unchanged when the future is overwritten": check_poisoned_future(panel, preds),
        "random model shows no skill (|t| < 3 at every horizon)": bool((rnd.ic_t.abs() < 3).all()),
        "random model Brier is 0.25": bool(((rnd.brier - 0.25).abs() < 1e-6).all()),
        "rebuild from raw as of day D reproduces the logged predictions":
            bool(rebuild) and all(r["only_in_one"] == 0 and r["max_abs_score_diff"] < 1e-5 for r in rebuild),
    }
    sims = report.run_sims(panel, preds, start, end)
    cal = score.calibration_table(panel, preds, 5)
    passed = all(checks.values())
    lines = [
        "# Dress rehearsal report", "",
        f"Replayed {len(sessions)} sessions, {sessions[0]} to {sessions[-1]}, through the same predict, log and score",
        "code the live run uses. **This is a pipeline test. Nothing below is evidence of skill**, and none of it",
        "goes on the scoreboard: the baselines are known effects and this window was not held out from their design.", "",
        f"## Result: {'PASS' if passed else 'FAIL'}", "",
        "| check | ok |", "|---|---|", *[f"| {k} | {'yes' if v else '**NO**'} |" for k, v in checks.items()], "",
        "### Rebuild-from-raw comparison", "",
        report._fmt(pd.DataFrame(rebuild)) if rebuild else "_skipped_", "",
        "## Plumbing numbers (not evidence)", "",
        "### Rank IC", "", report.ic_table(scores), "",
        "### Simulated portfolios after costs", "", report.sim_table(sims), "",
        "### Calibration at 5 sessions: predicted vs realised chance of beating the median", "",
        report._fmt(cal, dec={"p_mean": 3, "beat_rate": 3}) if len(cal) else "_none_", "",
        "### IC standard deviation, for forward planning", "",
        report._fmt(summ[["model", "horizon", "ic_sd"]], dec={"ic_sd": 4}),
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    return {"passed": passed, "checks": checks, "sessions": len(sessions)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="fit and freeze the baselines' probability slopes")
    ap.add_argument("--rebuild-checks", type=int, default=3)
    a = ap.parse_args()
    if a.calibrate:
        print(json.dumps(calibrate(Panel.load()), indent=2))
    else:
        r = run(a.rebuild_checks)
        print(json.dumps(r, indent=2))
        raise SystemExit(0 if r["passed"] else 1)
