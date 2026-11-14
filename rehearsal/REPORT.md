# Dress rehearsal report

Replayed 496 sessions, 2023-11-12 to 2025-11-11, through the same predict, log and score
code the live run uses. **This is a pipeline test. Nothing below is evidence of skill**, and none of it
goes on the scoreboard: the baselines are known effects and this window was not held out from their design.

## Result: PASS

| check | ok |
|---|---|
| every session has predictions from the control and every baseline | yes |
| about 500 names ranked per baseline per day | yes |
| a challenger never ranks fewer than 100 names | yes |
| no duplicate (date, model, symbol) rows | yes |
| every matured target was scored, none early | yes |
| scores never used a session after the run date | yes |
| log refuses a second write for the same day | yes |
| predictions unchanged when the future is overwritten | yes |
| random model shows no skill (|t| < 3 at every horizon) | yes |
| random model Brier is 0.25 | yes |
| rebuild from raw as of day D reproduces the logged predictions | yes |
| observed tier: one evaluation logged for every session and signal, no failures | yes |
| observed tier: flagged rows equal the evaluation log's counts, no duplicates | yes |
| observed tier: every matured event scored once, none before session t+2+h | yes |
| observed tier: uses no baseline or challenger name | yes |

### Rebuild-from-raw comparison

| date | model | rows_truncated_build | rows_replay | only_in_one | max_abs_score_diff | max_abs_rank_diff |
|---|---|---|---|---|---|---|
| 2023-12-12 | ear_drift_60 | 313 | 313 | 0 | 0.0 | 0.0 |
| 2023-12-12 | ens_mom_ear | 499 | 499 | 0 | 0.0 | 0.0 |
| 2023-12-12 | mom_12_1 | 495 | 495 | 0 | 0.0 | 0.0 |
| 2023-12-12 | random | 500 | 500 | 0 | 0.0 | 0.0 |
| 2023-12-12 | rev_5 | 500 | 500 | 0 | 0.0 | 0.0 |
| 2024-11-08 | ear_drift_60 | 343 | 343 | 0 | 0.0 | 0.0 |
| 2024-11-08 | ens_mom_ear | 499 | 499 | 0 | 0.0 | 0.0 |
| 2024-11-08 | mom_12_1 | 494 | 494 | 0 | 0.0 | 0.0 |
| 2024-11-08 | random | 500 | 500 | 0 | 0.0 | 0.0 |
| 2024-11-08 | rev_5 | 500 | 500 | 0 | 0.0 | 0.0 |
| 2025-10-10 | ear_drift_60 | 478 | 478 | 0 | 0.0 | 0.0 |
| 2025-10-10 | ens_mom_ear | 500 | 500 | 0 | 0.0 | 0.0 |
| 2025-10-10 | mom_12_1 | 487 | 487 | 0 | 0.0 | 0.0 |
| 2025-10-10 | random | 500 | 500 | 0 | 0.0 | 0.0 |
| 2025-10-10 | rev_5 | 500 | 500 | 0 | 0.0 | 0.0 |


## Plumbing numbers (not evidence)

### Rank IC

| model | horizon | days | eff_obs | first | last | ic_mean | ic_sd | ic_t | top_excess_mean | top_hit | brier | ic_ex_ref_mean | days needed for t=2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | 0.0129 | 0.0692 | 4.15 | 0.04% | 50.48% | 0.2499 | 0.0128 | 115 |
| ear_drift_60 | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0240 | 0.0720 | 3.30 | 0.16% | 51.27% | 0.2498 | 0.0228 | 180 |
| ear_drift_60 | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | 0.0249 | 0.0745 | 1.63 | 0.41% | 52.48% | 0.2498 | 0.0221 | 714 |
| ens_mom_ear | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | 0.0049 | 0.0994 | 1.09 | 0.05% | 50.24% | 0.2500 | 0.0106 | 1666 |
| ens_mom_ear | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0137 | 0.1053 | 1.29 | 0.18% | 50.84% | 0.2500 | 0.0189 | 1186 |
| ens_mom_ear | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | 0.0121 | 0.0982 | 0.60 | 0.45% | 50.94% | 0.2502 | 0.0178 | 5277 |
| mom_12_1 | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | -0.0031 | 0.1299 | -0.53 | 0.03% | 48.99% | 0.2501 |  | 7061 |
| mom_12_1 | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0027 | 0.1418 | 0.19 | 0.13% | 49.79% | 0.2502 |  | 55964 |
| mom_12_1 | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | 0.0022 | 0.1360 | 0.08 | 0.26% | 48.68% | 0.2505 |  | 296910 |
| random | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | 0.0040 | 0.0431 | 2.05 | 0.02% | 50.56% | 0.2500 | 0.0034 | 468 |
| random | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | -0.0004 | 0.0435 | -0.08 | 0.00% | 50.17% | 0.2500 | -0.0004 | 297459 |
| random | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | -0.0008 | 0.0425 | -0.09 | 0.01% | 49.96% | 0.2500 | -0.0002 | 239715 |
| rev_5 | 1 | 494 | 494.0 | 2023-11-12 | 2025-11-07 | 0.0315 | 0.1213 | 5.77 | 0.06% | 51.17% | 0.2499 | 0.0319 | 59 |
| rev_5 | 5 | 490 | 98.0 | 2023-11-12 | 2025-10-31 | 0.0361 | 0.1108 | 3.22 | 0.12% | 50.95% | 0.2498 | 0.0361 | 188 |
| rev_5 | 20 | 475 | 23.8 | 2023-11-12 | 2025-10-09 | 0.0094 | 0.1000 | 0.46 | -0.07% | 49.18% | 0.2500 | 0.0088 | 9052 |


### Simulated portfolios after costs

| portfolio | hold | total_return | after_tax_total_return | cagr | vol | max_drawdown | turnover_per_year | cost_drag_per_year | unfilled_buys | blocked_sells | total_return_if_silent_holdings_go_to_zero | writeoffs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| universe, equal weight, all 500 (after costs) | 21d | 33.14% | 29.41% | 15.69% | 19.95% | -25.29% | 0.6 | 0.56% | 0.3 | 1128.0 |  |  |
| NIFTYBEES buy and hold (no trading costs) | - | 35.16% | 31.72% | 16.58% | 11.62% | -15.23% |  |  |  |  |  |  |
| MOM30IETF buy and hold (Nifty 200 Momentum 30 fund) | - | 33.54% | 30.31% | 15.86% | 19.17% | -31.84% |  |  |  |  |  |  |
| Nifty 50 price index (not investable) | - | 31.60% |  | 15.00% | 13.10% | -15.77% |  |  |  |  |  |  |
| random top 20 | 5d | -6.35% | -7.80% | -3.29% | 19.68% | -32.17% | 51.3 | 23.20% | 0.6 | 54.2 | -7.69% | 0.2 |
| random top 20 | 20d | 21.34% | 16.25% | 10.35% | 19.45% | -26.97% | 14.3 | 6.40% | 0.1 | 26.0 | 20.73% | 0.1 |
| mom_12_1 top 20 | 5d | 25.86% | 20.03% | 12.42% | 30.40% | -39.15% | 10.9 | 4.89% | 0.8 | 0.6 | 25.86% | 0.0 |
| mom_12_1 top 20 | 20d | 18.42% | 14.29% | 8.99% | 30.27% | -40.08% | 5.4 | 2.42% | 0.2 | 0.0 | 18.42% | 0.0 |
| rev_5 top 20 | 5d | -9.12% | -10.04% | -4.75% | 24.57% | -33.79% | 48.7 | 22.06% | 1.8 | 2.2 | -9.12% | 0.0 |
| rev_5 top 20 | 20d | 14.18% | 10.02% | 6.98% | 22.12% | -28.38% | 13.3 | 5.99% | 0.6 | 65.5 | 13.09% | 0.2 |
| ear_drift_60 top 20 | 5d | 50.25% | 38.32% | 23.03% | 22.94% | -28.85% | 9.1 | 4.05% | 1.0 | 0.6 | 50.25% | 0.0 |
| ear_drift_60 top 20 | 20d | 39.97% | 30.82% | 18.67% | 22.62% | -28.61% | 6.6 | 2.95% | 0.2 | 0.2 | 39.97% | 0.0 |
| ens_mom_ear top 20 | 5d | 61.62% | 46.68% | 27.69% | 26.19% | -28.93% | 15.2 | 6.75% | 1.0 | 0.8 | 61.62% | 0.0 |
| ens_mom_ear top 20 | 20d | 41.40% | 31.78% | 19.29% | 25.78% | -29.28% | 8.0 | 3.58% | 0.2 | 0.6 | 41.40% | 0.0 |


### Challenger comparison as the scoreboard would show it

## Champion and challengers

Champion: **none (seat empty)**. Reference to beat: `mom_12_1`. Challengers ever started: 2.
A challenger is judged only at 250, 375, 500 ... scored sessions at the 20-session horizon. `ic_beyond_reference`
is its rank IC after the reference's ranks are removed; its t-stat must reach `required_t`, which rises
with every challenger ever started. Meeting the rule earns a holdout check by the owner, not a promotion.

| challenger | reference | scored_sessions | judged_on | ic | ic_t | reference_ic | ic_beyond_reference | beyond_t | top_decile_excess | required_t | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | mom_12_1 | 475 | 375 | 0.0366 | 2.06 | -0.0101 | 0.0344 | 1.92 | 0.54% | 2.24 | not met at 375; next checkpoint at 500 |
| ens_mom_ear | mom_12_1 | 475 | 375 | 0.0169 | 0.69 | -0.0101 | 0.0296 | 2.13 | 0.61% | 2.24 | not met at 375; next checkpoint at 500 |


### Decay monitor as the scoreboard would show it

## Decay monitor

One-sided CUSUM on each model's forward rank IC, sampled every h sessions. `expected_ic` is half the
backtest IC; an alarm means the IC has run below that for long enough to look like a change, and
gives the estimated start. `sessions_to_detect_total_loss` is how long an edge that vanished today
would take to raise the alarm: weak signals decay quietly.

| model | horizon | expected_ic | observations | forward_ic | cusum | alarm_at | state | sessions_to_detect_total_loss | retire_rule_met |
|---|---|---|---|---|---|---|---|---|---|
| mom_12_1 | 1 | 0.0062 | 494 | -0.0031 | 30.90 | 43.57 | ok | 1064 |  |
| mom_12_1 | 5 | 0.0158 | 98 | 0.0027 | 7.79 | 19.51 | ok | 1175 |  |
| mom_12_1 | 20 | 0.0256 | 24 | 0.0136 | 2.09 | 10.22 | ok | 1581 |  |
| rev_5 | 1 | 0.0114 | 494 | 0.0315 | 0.07 | 33.22 | ok | 506 |  |
| rev_5 | 5 | 0.0157 | 98 | 0.0276 | 1.71 | 17.71 | ok | 898 |  |
| rev_5 | 20 | 0.0044 | 24 | 0.0043 | 1.64 | 13.15 | ok | 3420 |  |
| ear_drift_60 | 1 | 0.0072 | 494 | 0.0129 | 0.90 | 30.71 | ok | 412 |  |
| ear_drift_60 | 5 | 0.0135 | 98 | 0.0232 | 3.30 | 15.25 | ok | 605 |  |
| ear_drift_60 | 20 | 0.0205 | 24 | 0.0372 | 2.09 | 8.25 | ok | 891 |  |
| ens_mom_ear | 1 | 0.0077 | 494 | 0.0049 | 3.19 | 38.71 | ok | 763 |  |
| ens_mom_ear | 5 | 0.0179 | 98 | 0.0128 | 2.71 | 18.07 | ok | 949 |  |
| ens_mom_ear | 20 | 0.0285 | 24 | 0.0258 | 1.58 | 9.65 | ok | 1347 |  |



### Graduation table as the scoreboard would show it if the ensemble held the seat

## Graduation (Phase 4)

Graduation is the point at which real capital may be considered. It needs every criterion below on
the forward record, and then the owner's explicit decision. Criteria v1.1: fixed on 2026-11-13, and G5
tightened on 2026-11-14 to the better of NIFTYBEES and the momentum fund, before any forward score existed.

Champion `ens_mom_ear`: 2 of 8 measured criteria met.

| criterion | required | forward record | met |
|---|---|---|---|
| G1 standing | champion for 250 scored sessions, not decaying | champion, 227 sessions in the seat | no |
| G2 duration | 500 scored sessions with a 10% market fall in the window, else 750 | 475 sessions; NIFTYBEES worst fall -15.2% | no |
| G3 IC | 20-session IC at least 0.02, 5-session IC positive | 0.0121 and 0.0137 | no |
| G4 t-stat | t of the 20-session IC at least 2.0 | 0.60 | no |
| G5 against the better fund after costs and taxes | at least 3% a year over the better of NIFTYBEES and MOM30IETF, all after tax | 15.1% against NIFTYBEES 15.1% and MOM30IETF 14.4% (if taxed as business income: 13.1%) | no |
| G6 against the universe | beats the universe held after costs, before tax | 19.3% against 15.7% | yes |
| G7 drawdown | no deeper than -25.0%; no deeper than -15% against the universe | -29.3%; -10.8% against the universe | no |
| G8 record integrity | predicted on 95% of sessions, control clean, nothing voided in 250 sessions | 100.0% of sessions; control clean; no recent void | yes |
| G9 owner's checks | contract note matched, tax treatment confirmed, broker API and static IP ready | by hand | by hand |



### Observed signals as the scoreboard would show them (in sample: this window is where the signal was found)

## Observed signals

Logged forward without a shadow slot (Phase 3 rules v1.1). An observed signal cannot become champion and
does not change the challengers' margin. Signals ever observed: 1, which sets `required_t`.
The label "confirmed forward" is read only at 250, 375, 500 ... evaluated sessions and needs 200 scored events,
`t` at least `required_t`, and a mean excess above one round trip of costs, also when entering a session later.
Running numbers between checkpoints decide nothing.

| signal | horizon | sessions | judged_on_sessions | events | mean_excess | t | required_t | after_costs | after_costs_one_session_later | status |
|---|---|---|---|---|---|---|---|---|---|---|
| results_advance_5d | 5 | 489 | 375 | 234 | 1.58% | 4.81 | 1.96 | 1.12% | 1.23% | CONFIRMED FORWARD at this checkpoint: may be proposed for a use (a new registration) |

Reported, not required:

| signal | hit_rate | median_excess | mean_minus_momentum_tenth | mean_excess_rank_1-100 | mean_excess_rank_101-250 | mean_excess_rank_251-500 |
|---|---|---|---|---|---|---|
| results_advance_5d | 54.70% | 0.62% | 1.49% | 1.28% | 1.29% | 1.80% |


Events flagged in the replay: 340 on 128 of 496 sessions. Decision horizons: {'results_advance_5d': 5}.

### Sessions on which a challenger was silent

| model | silent_sessions |
|---|---|
| ear_drift_60 | 0 |
| ens_mom_ear | 0 |


### Calibration at 5 sessions: predicted vs realised chance of beating the median

| model | bin | p_mean | beat_rate | n |
|---|---|---|---|---|
| ear_drift_60 | 0.0 | 0.483 | 0.483 | 40416 |
| ear_drift_60 | 1.0 | 0.492 | 0.490 | 40144 |
| ear_drift_60 | 2.0 | 0.500 | 0.498 | 40611 |
| ear_drift_60 | 3.0 | 0.508 | 0.512 | 40147 |
| ear_drift_60 | 4.0 | 0.517 | 0.514 | 39894 |
| ens_mom_ear | 0.0 | 0.476 | 0.488 | 48961 |
| ens_mom_ear | 1.0 | 0.488 | 0.498 | 48869 |
| ens_mom_ear | 2.0 | 0.500 | 0.497 | 48802 |
| ens_mom_ear | 3.0 | 0.512 | 0.506 | 48864 |
| ens_mom_ear | 4.0 | 0.524 | 0.509 | 48643 |
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
| ear_drift_60 | 1 | 0.0692 |
| ear_drift_60 | 5 | 0.0720 |
| ear_drift_60 | 20 | 0.0745 |
| ens_mom_ear | 1 | 0.0994 |
| ens_mom_ear | 5 | 0.1053 |
| ens_mom_ear | 20 | 0.0982 |
| mom_12_1 | 1 | 0.1299 |
| mom_12_1 | 5 | 0.1418 |
| mom_12_1 | 20 | 0.1360 |
| random | 1 | 0.0431 |
| random | 5 | 0.0435 |
| random | 20 | 0.0425 |
| rev_5 | 1 | 0.1213 |
| rev_5 | 5 | 0.1108 |
| rev_5 | 20 | 0.1000 |
