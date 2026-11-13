# nse-research

A self-scoring prediction system for NSE cash equities. Paper predictions only; no real money.

Predictions come from versioned Python code run on a schedule, are logged before outcomes are known,
and are scored against simple baselines after full Indian costs. Backtests screen ideas; only the
forward record decides.

## State

Phase 0 (data) and Phase 1 (baselines, scoring, automation) built on 2026-11-12; the forward record
started that evening. Phase 2 (discovery loop) has tested four ideas; two passed. Phase 3 (champion
and challengers) was built on 2026-11-13: two challengers predict in shadow, the seat is empty. See `research_log.md` for the standing rules and
frozen definitions, `data/README.md` for sources and every known data flaw, and
`rehearsal/REPORT.md` for the pipeline test.

## Layout

| Path | What it is |
|---|---|
| `src/nsr/config.py` | Paths, date boundaries, the holdout and production guards |
| `src/nsr/download.py`, `api.py` | NSE daily files and the corporate-actions register |
| `src/nsr/parse.py`, `corpactions.py` | Raw file parsers; corporate-action text to adjustment factors |
| `src/nsr/build.py`, `universe.py` | Cleaned panel with returns, flags, `available_at`; point-in-time universe |
| `src/nsr/panel.py` | Session-by-security arrays; models only ever get a view that stops at the as-of day |
| `src/nsr/models.py` | Baselines `random`, `mom_12_1`, `rev_5`; challenger `ear_drift_60`; roles and the 3-slot limit |
| `src/nsr/notices.py`, `ensemble.py` | Board-meeting notices from the bundles; rank-average ensemble with forward-only weights |
| `src/nsr/champion.py`, `monitor.py` | Forward comparison at checkpoints; CUSUM decay monitor |
| `src/nsr/predict.py` | Builds prediction rows; append-only writer; no-backfill rule |
| `src/nsr/score.py`, `costs.py`, `sim.py`, `report.py` | IC and calibration, Indian delivery costs, long-only simulator, scoreboard |
| `src/nsr/daily.py` | The scheduled daily cycle (the only production entry point) |
| `src/nsr/rehearsal.py` | Two-year replay of the daily cycle, and calibration fitting |
| `scripts/` | launchd job, installer, `deploy.sh` (pins the code the job runs) |
| `models/` | Frozen probability slopes (baselines, challengers) and backtest IC expectations for the decay monitor |
| `champion.json`, `void_predictions.csv`, `ensemble_weights.csv` | Champion state; rows struck from scoring; ensemble weights used each day |
| `predictions.csv` | Append-only forecast log |
| `scores.csv`, `scoreboard.md` | Matured results per day; forward-only summary |
| `trial_ledger.csv`, `research_log.md` | Every trial; pre-registrations and results |
| `signal_registry.md`, `lessons.md`, `changelog.md`, `run_log.md` | Signal status, lessons, champion history, run history |

## Commands

```bash
uv venv --python 3.12 .venv && uv pip install -e '.[dev]'
.venv/bin/python -m pytest -q                 # tests
.venv/bin/python -m nsr.download              # fetch any missing research/holdout days
.venv/bin/python -m nsr.build                 # rebuild data/clean (research window only)
.venv/bin/python -m nsr.rehearsal             # replay the last two research years (pipeline test)
.venv/bin/python -m nsr.research.text         # parse announcement and board-meeting text (research window)
.venv/bin/python -m nsr.research.validate     # harness check on noise, momentum and reversal
.venv/bin/python -m nsr.research.run T-0002   # run a pre-registered trial (must be in trial_ledger.csv)
.venv/bin/python -m nsr.research.run --verdicts   # apply the pass rules across all trials so far
.venv/bin/python -m nsr.research.phase3_plan  # size the forward test from backtests (planning only)
.venv/bin/python -m nsr.daily --dry-run       # daily cycle without writing; prints what each model would rank
scripts/deploy.sh                             # copy the committed code to the pinned copy the job runs
scripts/deploy.sh <commit>                    # roll the job back to an earlier commit
scripts/install_schedule.sh                   # install or reinstall the launchd job
```

The scheduled job never runs this folder. It runs `~/nse_production/app/current`, a copy of one
commit with its own Python environment, and writes its records back here. A code change reaches the
live run only through `git commit` and `scripts/deploy.sh`, which runs the tests on the copy first.

The daily job runs at 20:30, 22:30 and 07:45 IST. Each run is idempotent. A run that finds the latest
session can no longer be predicted in time logs it as missed and moves on.

## The locked holdout

Trade dates 2025-11-12 .. 2026-11-11 live in `~/nse_holdout_LOCKED`, outside this project.
`config.assert_readable` raises `HoldoutViolation` if any code other than the scheduled production
run tries to parse them. Do not copy those files into the project. The production panel built from
them lives in `~/nse_production`, also outside the project, and is refused to research code.
