# nse-research

A self-scoring prediction system for NSE cash equities. Paper predictions only; no real money.

Predictions come from versioned Python code run on a schedule, are logged before outcomes are known,
and are scored against simple baselines after full Indian costs. Backtests screen ideas; only the
forward record decides.

## State

Phase 0 (data) built on 2026-11-12. See `research_log.md` for the reality check and standing rules,
and `data/README.md` for sources and every known data flaw.

## Layout

| Path | What it is |
|---|---|
| `src/nsr/config.py` | Paths, date boundaries, the holdout guard |
| `src/nsr/download.py` | Fetches NSE daily files; holdout dates go straight to the locked folder |
| `src/nsr/parse.py` | Raw file parsers (prices, corporate actions, band hits, delivery, market cap) |
| `src/nsr/corpactions.py` | Corporate-action text to adjustment factors |
| `src/nsr/build.py` | Builds `data/clean/*.parquet` with returns, flags and `available_at` |
| `src/nsr/universe.py` | Point-in-time liquid universe |
| `predictions.csv` | Append-only forecast log |
| `scoreboard.md` | Forward-only performance |
| `trial_ledger.csv` | Every hypothesis, backtest and forward comparison tried |
| `research_log.md` | Pre-registrations and results |
| `signal_registry.md`, `lessons.md`, `changelog.md`, `run_log.md` | Signal status, lessons, champion history, run history |

## Commands

```bash
uv venv --python 3.12 .venv && uv pip install -e '.[dev]'
.venv/bin/python -m nsr.download            # fetch any missing days (2010-01-01 .. holdout end)
.venv/bin/python -m nsr.build               # rebuild data/clean from raw (research window only)
.venv/bin/python -m pytest -q               # tests
```

## The locked holdout

Trade dates 2025-11-12 .. 2026-11-11 live in `~/nse_holdout_LOCKED`, outside this project.
`config.assert_readable` raises `HoldoutViolation` if any code other than the scheduled production
run tries to parse them. Do not copy those files into the project.
