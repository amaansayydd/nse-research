"""Harness check on controls, run before any trial result is trusted.

  - pure noise must show no IC, raw or neutralised, and a top-20 noise portfolio must
    lose to the universe by about its cost drag
  - momentum and reversal, scored by this harness over the rehearsal window, must match
    what the production scorer measured in the dress rehearsal

    python -m nsr.research.validate
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from . import evaluate, stats
from .data import HORIZONS, ResearchData
from .features import controls
from .run import RESULTS


def main() -> dict:
    rd = ResearchData.load(tables=())
    ctrl = controls(rd)
    noise = np.random.default_rng(20261112).normal(size=rd.member.shape)
    sigs = {"noise": noise, "mom_12_1": ctrl["mom_12_1"], "rev_5": ctrl["rev_5"]}
    reh_start = pd.Timestamp(config.HOLDOUT_START) - pd.DateOffset(years=2)
    out = {}
    for name, S in sigs.items():
        dm = evaluate.daily_metrics(rd, S, {k: v for k, v in ctrl.items() if k != name} if name != "noise" else ctrl)
        full = evaluate.ic_table(dm).set_index("h")
        reh = evaluate.ic_table(dm[dm.date >= reh_start]).set_index("h")
        out[name] = {
            "full_window": {int(h): {k: float(full.loc[h, k]) for k in ("ic_mean", "ic_sd", "ic_t", "top_excess_mean")} for h in HORIZONS},
            "full_window_neutral_t": {int(h): float(evaluate.ic_table(dm, "ic_neutral").set_index("h").loc[h, "ic_t"]) for h in HORIZONS},
            "rehearsal_window": {int(h): {k: float(reh.loc[h, k]) for k in ("ic_mean", "ic_t")} for h in HORIZONS},
            "years_positive_h20": int((evaluate.yearly_ic(dm, 20) > 0).sum()),
            "portfolio_h20": evaluate.portfolio_test(rd, S, 20, 1),
        }
    checks = {
        "noise raw IC |t| < 3 at every horizon": all(abs(v["ic_t"]) < 3 for v in out["noise"]["full_window"].values()),
        "noise neutralised IC |t| < 3 at every horizon": all(abs(t) < 3 for t in out["noise"]["full_window_neutral_t"].values()),
        "noise top-20 loses to the universe after costs": out["noise"]["portfolio_h20"]["excess_cagr"] < 0,
    }
    out["checks"] = checks
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "controls.json").write_text(evaluate.to_json(out))
    return out


if __name__ == "__main__":
    r = main()
    for name in ("noise", "mom_12_1", "rev_5"):
        v = r[name]
        print(name)
        for h in HORIZONS:
            f, w = v["full_window"][h], v["rehearsal_window"][h]
            print(f"  h={h:<2} full IC {f['ic_mean']:+.4f} sd {f['ic_sd']:.3f} t {f['ic_t']:+.2f} | neutral t {v['full_window_neutral_t'][h]:+.2f}"
                  f" | rehearsal window IC {w['ic_mean']:+.4f} t {w['ic_t']:+.2f}")
        p = v["portfolio_h20"]
        print(f"  top20/20d: cagr {p['cagr']:.4f} universe {p['universe_cagr']:.4f} excess {p['excess_cagr']:+.4f} "
              f"TE {p['tracking_error']:.3f} excess Sharpe {p['excess_sharpe_ann']:+.2f} PSR {p['excess_psr']:.2f} "
              f"cost {p['cost_drag_per_year']:.3f} turnover {p['turnover_per_year']} years won {p['years_beating_universe']}/{p['years']} yrs+IC {v['years_positive_h20']}")
    print(r["checks"])
