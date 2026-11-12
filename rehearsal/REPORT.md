# Dress rehearsal report

Replayed 496 sessions, 2023-11-12 to 2025-11-11, through the same predict, log and score
code the live run uses. **This is a pipeline test. Nothing below is evidence of skill**, and none of it
goes on the scoreboard: the baselines are known effects and this window was not held out from their design.

## Result: FAIL

| check | ok |
|---|---|
| every session has predictions from every model | yes |
| about 500 names ranked per model per day | yes |
| no duplicate (date, model, symbol) rows | yes |
| every matured target was scored, none early | yes |
| scores never used a session after the run date | yes |
| log refuses a second write for the same day | yes |
| predictions unchanged when the future is overwritten | yes |
| random model shows no skill (|t| < 3 at every horizon) | yes |
| random model Brier is 0.25 | yes |
| rebuild from raw as of day D reproduces the logged predictions | **NO** |

### Rebuild-from-raw comparison

_skipped_

## Plumbing numbers (not evidence)

### Rank IC

| model | horizon | days | eff_obs | first | last | ic_mean | ic_sd | ic_t | top_excess_mean | top_hit | brier | days needed for t=2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mom_12_1 | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | -0.0031 | 0.1299 | -0.53 | 0.03% | 48.99% | 0.2501 | 7061 |
| mom_12_1 | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0027 | 0.1418 | 0.19 | 0.13% | 49.79% | 0.2502 | 55964 |
| mom_12_1 | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | 0.0022 | 0.1360 | 0.08 | 0.26% | 48.68% | 0.2505 | 296910 |
| random | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | -0.0002 | 0.0439 | -0.11 | -0.00% | 49.57% | 0.2500 | 150392 |
| random | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0018 | 0.0484 | 0.36 | -0.01% | 49.89% | 0.2500 | 14952 |
| random | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | -0.0001 | 0.0445 | -0.01 | 0.02% | 49.91% | 0.2500 | 8512612 |
| rev_5 | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | 0.0315 | 0.1213 | 5.77 | 0.06% | 51.17% | 0.2499 | 59 |
| rev_5 | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0361 | 0.1108 | 3.22 | 0.12% | 50.95% | 0.2498 | 188 |
| rev_5 | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | 0.0094 | 0.1000 | 0.46 | -0.07% | 49.18% | 0.2500 | 9052 |


### Simulated portfolios after costs

| portfolio | hold | total_return | cagr | vol | max_drawdown | turnover_per_year | cost_drag_per_year | unfilled_buys | blocked_sells | total_return_if_silent_holdings_go_to_zero | writeoffs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| universe equal-weight (no costs) | - | 44.59% | 20.65% | 19.74% | -24.59% |  |  |  |  |  |  |
| NIFTYBEES buy and hold (no costs) | - | 35.16% | 16.58% | 11.62% | -15.23% |  |  |  |  |  |  |
| Nifty 50 price index | - | 31.60% | 15.00% | 13.10% | -15.77% |  |  |  |  |  |  |
| random top 20 | 5d | -5.94% | -3.07% | 19.53% | -32.52% | 52.8 | 23.84% | 0.6 | 0.2 | -5.94% | 0.0 |
| random top 20 | 20d | 23.63% | 11.40% | 19.62% | -25.62% | 14.5 | 6.49% | 0.1 | 46.6 | 22.78% | 0.1 |
| mom_12_1 top 20 | 5d | 25.86% | 12.42% | 30.40% | -39.15% | 10.9 | 4.89% | 0.8 | 0.6 | 25.86% | 0.0 |
| mom_12_1 top 20 | 20d | 18.42% | 8.99% | 30.27% | -40.08% | 5.4 | 2.42% | 0.2 | 0.0 | 18.42% | 0.0 |
| rev_5 top 20 | 5d | -9.12% | -4.75% | 24.57% | -33.79% | 48.7 | 22.06% | 1.8 | 2.2 | -9.12% | 0.0 |
| rev_5 top 20 | 20d | 14.18% | 6.98% | 22.12% | -28.38% | 13.3 | 5.99% | 0.6 | 65.5 | 13.09% | 0.2 |


### Calibration at 5 sessions: predicted vs realised chance of beating the median

| model | bin | p_mean | beat_rate | n |
|---|---|---|---|---|
| mom_12_1 | 0.0 | 0.479 | 0.486 | 48029 |
| mom_12_1 | 1.0 | 0.489 | 0.508 | 47814 |
| mom_12_1 | 2.0 | 0.500 | 0.503 | 48262 |
| mom_12_1 | 3.0 | 0.511 | 0.505 | 47824 |
| mom_12_1 | 4.0 | 0.521 | 0.495 | 47595 |
| rev_5 | 0.0 | 0.487 | 0.472 | 48979 |
| rev_5 | 1.0 | 0.493 | 0.493 | 48967 |
| rev_5 | 2.0 | 0.500 | 0.508 | 49469 |
| rev_5 | 3.0 | 0.507 | 0.512 | 48986 |
| rev_5 | 4.0 | 0.513 | 0.514 | 48432 |


### IC standard deviation, for forward planning

| model | horizon | ic_sd |
|---|---|---|
| mom_12_1 | 1 | 0.1299 |
| mom_12_1 | 5 | 0.1418 |
| mom_12_1 | 20 | 0.1360 |
| random | 1 | 0.0439 |
| random | 5 | 0.0484 |
| random | 20 | 0.0445 |
| rev_5 | 1 | 0.1213 |
| rev_5 | 5 | 0.1108 |
| rev_5 | 20 | 0.1000 |
