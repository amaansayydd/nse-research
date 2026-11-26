# Scoreboard (forward-only)

Updated 2026-11-26 20:30 IST. Prediction days logged: 10. Days with a matured score: 8.

Only predictions written to `predictions.csv` before their outcome window opened are counted here.
Backtest and dress-rehearsal numbers never appear in this file.

## Rank IC by model and horizon

Target: return from the next session's open to the open h sessions later. `eff_obs` divides the day
count by the horizon because overlapping targets are not independent. An `ic_t` below 2 means nothing
yet. `days needed for t=2` assumes the IC measured so far is the true IC, which early on it is not.

| model | horizon | days | eff_obs | first | last | ic_mean | ic_sd | ic_t | top_excess_mean | top_hit | brier | ic_ex_ref_mean | days needed for t=2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | 1 | 7 | 7.0 | 2026-11-13 | 2026-11-23 | 0.0592 | 0.0713 | 2.20 | 0.13% | 52.53% | 0.2496 | 0.0673 | 6 |
| ear_drift_60 | 5 | 3 | 1.0 | 2026-11-13 | 2026-11-17 | 0.1118 | 0.0182 | 6.13 | 0.68% | 56.78% | 0.2490 | 0.1280 | 1 |
| ens_mom_ear | 1 | 7 | 7.0 | 2026-11-13 | 2026-11-23 | -0.0012 | 0.0952 | -0.03 | -0.26% | 46.57% | 0.2500 | 0.0602 | 24113 |
| ens_mom_ear | 5 | 3 | 1.0 | 2026-11-13 | 2026-11-17 | -0.0363 | 0.0352 | -1.03 | -1.51% | 36.00% | 0.2507 | 0.1122 | 19 |
| mom_12_1 | 1 | 8 | 8.0 | 2026-11-12 | 2026-11-23 | -0.0311 | 0.1173 | -0.75 | -0.48% | 41.58% | 0.2502 |  | 57 |
| mom_12_1 | 5 | 4 | 1.0 | 2026-11-12 | 2026-11-17 | -0.1201 | 0.0744 | -1.61 | -2.19% | 35.20% | 0.2516 |  | 8 |
| random | 1 | 8 | 8.0 | 2026-11-12 | 2026-11-23 | -0.0037 | 0.0390 | -0.27 | 0.01% | 51.50% | 0.2500 | -0.0051 | 441 |
| random | 5 | 4 | 1.0 | 2026-11-12 | 2026-11-17 | 0.0177 | 0.0100 | 1.77 | -0.02% | 50.00% | 0.2500 | 0.0148 | 6 |
| rev_5 | 1 | 8 | 8.0 | 2026-11-12 | 2026-11-23 | -0.0137 | 0.1365 | -0.28 | -0.13% | 48.50% | 0.2501 | -0.0173 | 397 |
| rev_5 | 5 | 4 | 1.0 | 2026-11-12 | 2026-11-17 | -0.0177 | 0.1116 | -0.16 | -1.06% | 39.50% | 0.2503 | -0.0323 | 800 |

`top_excess_mean`: top-decile mean return minus the universe mean, before costs. `top_hit`: share of
top-decile names beating the universe median. `brier`: 0.25 is what a coin flip scores. `ic_ex_ref_mean`:
rank IC left after the reference model's ranks are removed.

## Simulated long-only portfolios after costs

Top 20 names, Rs 1,000,000 paper capital, trades at the next open with 10 bps slippage a side,
full delivery charges, no fill at a locked band. Averaged over every possible start day. Pre-tax, except
`after_tax_total_return`: capital-gains tax paid each financial year (20% short-term, 12.5% long-term above
Rs 1.25 lakh, 4% cess) and the book sold at the end. The funds (NIFTYBEES and the two momentum funds) are
bought once, held and sold the same way, at a stock's charges, which slightly overstates what a fund costs.

| portfolio | hold | total_return | after_tax_total_return | cagr | vol | max_drawdown | turnover_per_year | cost_drag_per_year | unfilled_buys | blocked_sells | total_return_if_silent_holdings_go_to_zero | writeoffs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| universe, equal weight, all 500 (after costs) | 21d | -0.26% | -0.69% | -7.14% | 2.61% | -0.37% | 6.0 | 2.62% | 0.0 | 0.0 |  |  |
| NIFTYBEES buy and hold (no trading costs) | - | 2.47% | 1.61% | 97.85% | 16.26% | -1.63% |  |  |  |  |  |  |
| MOM30IETF buy and hold (Nifty 200 Momentum 30 fund) | - | -1.35% | -1.77% | -31.69% | 16.77% | -3.59% |  |  |  |  |  |  |
| MOMENTUM50 buy and hold (Nifty 500 Momentum 50 fund) | - | -2.93% | -3.34% | -56.51% | 15.38% | -3.64% |  |  |  |  |  |  |
| Nifty 50 price index (not investable) | - | 2.31% |  | 89.69% | 17.52% | -1.75% |  |  |  |  |  |  |
| random top 20 | 5d | -1.47% | -1.71% | -33.87% | 7.45% | -1.27% | 35.0 | 15.65% | 0.0 | 0.0 | -1.47% | 0.0 |
| random top 20 | 20d | -0.35% | -0.46% | -9.28% | 2.29% | -0.34% | 6.3 | 2.75% | 0.0 | 0.0 | -0.35% | 0.0 |
| mom_12_1 top 20 | 5d | -2.28% | -2.51% | -47.62% | 12.60% | -3.23% | 17.4 | 7.69% | 0.0 | 0.0 | -2.28% | 0.0 |
| mom_12_1 top 20 | 20d | -0.55% | -0.67% | -14.39% | 4.24% | -1.02% | 6.3 | 2.75% | 0.0 | 0.0 | -0.55% | 0.0 |
| rev_5 top 20 | 5d | -3.28% | -3.51% | -60.71% | 13.67% | -4.48% | 34.0 | 15.21% | 0.0 | 0.0 | -3.28% | 0.0 |
| rev_5 top 20 | 20d | -0.77% | -0.89% | -19.50% | 4.40% | -1.26% | 6.3 | 2.75% | 0.0 | 0.0 | -0.77% | 0.0 |
| ear_drift_60 top 20 | 5d | 1.81% | 1.24% | 65.26% | 8.17% | -0.76% | 14.0 | 6.12% | 0.0 | 0.0 | 1.81% | 0.0 |
| ear_drift_60 top 20 | 20d | 0.61% | 0.41% | 18.72% | 2.79% | -0.19% | 5.6 | 2.45% | 0.0 | 0.0 | 0.61% | 0.0 |
| ens_mom_ear top 20 | 5d | -0.27% | -0.56% | -7.37% | 10.94% | -1.86% | 15.4 | 6.75% | 0.0 | 0.0 | -0.27% | 0.0 |
| ens_mom_ear top 20 | 20d | 0.01% | -0.11% | 0.18% | 3.35% | -0.46% | 5.6 | 2.45% | 0.0 | 0.0 | 0.01% | 0.0 |

`random` is the control: any model that cannot beat it has shown nothing. The hurdle for a stock-picking
model is the first row (own the whole universe); the hurdle for bothering at all is NIFTYBEES. A model
that leans on momentum must also beat `MOM30IETF`: a fund that follows a published momentum rule and is
taxed only when sold. Fund rows use the fund's own closing price, which can stray from its holdings' value
on a thin day. Graduation criterion G5 is tested against the better of NIFTYBEES and `MOM30IETF` (criteria v1.1).

## Champion and challengers

Champion: **none (seat empty)**. Reference to beat: `mom_12_1`. Challengers ever started: 2.
A challenger is judged only at 250, 375, 500 ... scored sessions at the 20-session horizon. `ic_beyond_reference`
is its rank IC after the reference's ranks are removed; its t-stat must reach `required_t`, which rises
with every challenger ever started. Meeting the rule earns a holdout check by the owner, not a promotion.

| challenger | reference | scored_sessions | judged_on | ic | ic_t | reference_ic | ic_beyond_reference | beyond_t | top_decile_excess | required_t | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | mom_12_1 | 0 | 0 |  |  |  |  |  |  | 2.24 | too early: 0 of 250 sessions |
| ens_mom_ear | mom_12_1 | 0 | 0 |  |  |  |  |  |  | 2.24 | too early: 0 of 250 sessions |

Ensemble weights for the latest prediction: `mom_12_1` 0.500, `ear_drift_60` 0.500. They start equal and move only on matured forward 20-session ICs.

## Observed signals

Logged forward without a shadow slot (Phase 3 rules v1.1). An observed signal cannot become champion and
does not change the challengers' margin. Signals ever observed: 1, which sets `required_t`.
The label "confirmed forward" is read only at 250, 375, 500 ... evaluated sessions and needs 200 scored events,
`t` at least `required_t`, and a mean excess above one round trip of costs, also when entering a session later.
Running numbers between checkpoints decide nothing.

| signal | horizon | sessions | judged_on_sessions | events | mean_excess | t | required_t | after_costs | after_costs_one_session_later | status |
|---|---|---|---|---|---|---|---|---|---|---|
| results_advance_5d | 5 | 1 | 1 | 0 |  |  | 1.96 |  |  | too early: 1 of 250 sessions, 0 of 200 events |

Reported, not required:

| signal | hit_rate | median_excess | mean_minus_momentum_tenth | mean_excess_rank_1-100 | mean_excess_rank_101-250 | mean_excess_rank_251-500 |
|---|---|---|---|---|---|---|
| results_advance_5d |  |  |  |  |  |  |

## Decay monitor

One-sided CUSUM on each model's forward rank IC, sampled every h sessions. `expected_ic` is half the
backtest IC; an alarm means the IC has run below that for long enough to look like a change, and
gives the estimated start. `sessions_to_detect_total_loss` is how long an edge that vanished today
would take to raise the alarm: weak signals decay quietly.

| model | horizon | expected_ic | observations | forward_ic | cusum | alarm_at | state | sessions_to_detect_total_loss | retire_rule_met |
|---|---|---|---|---|---|---|---|---|---|
| mom_12_1 | 1 | 0.0062 | 8 | -0.0311 | 3.37 | 43.57 | ok | 1064 |  |
| mom_12_1 | 5 | 0.0158 | 1 | -0.0209 | 0.19 | 19.51 | ok | 1175 |  |
| mom_12_1 | 20 | 0.0256 | 0 |  | 0.00 | 10.22 | ok | 1581 |  |
| rev_5 | 1 | 0.0114 | 8 | -0.0137 | 3.93 | 33.22 | ok | 506 |  |
| rev_5 | 5 | 0.0157 | 1 | 0.0093 | 0.00 | 17.71 | ok | 898 |  |
| rev_5 | 20 | 0.0044 | 0 |  | 0.00 | 13.15 | ok | 3420 |  |
| ear_drift_60 | 1 | 0.0072 | 7 | 0.0592 | 0.00 | 30.71 | ok | 412 |  |
| ear_drift_60 | 5 | 0.0135 | 1 | 0.0911 | 0.00 | 15.25 | ok | 605 |  |
| ear_drift_60 | 20 | 0.0205 | 0 |  | 0.00 | 8.25 | ok | 891 |  |
| ens_mom_ear | 1 | 0.0077 | 7 | -0.0012 | 1.15 | 38.71 | ok | 763 |  |
| ens_mom_ear | 5 | 0.0179 | 1 | -0.0659 | 0.53 | 18.07 | ok | 949 |  |
| ens_mom_ear | 20 | 0.0285 | 0 |  | 0.00 | 9.65 | ok | 1347 |  |

## Graduation (Phase 4)

Graduation is the point at which real capital may be considered. It needs every criterion below on
the forward record, and then the owner's explicit decision. Criteria v1.1: fixed on 2026-11-13, and G5
tightened on 2026-11-14 to the better of NIFTYBEES and the momentum fund, before any forward score existed.

There is no champion, so nothing can graduate. Where each challenger stands on the criteria that can already be measured:

| model | scored_sessions | ic_20 | ic_t | t_needed | ic_5 |
|---|---|---|---|---|---|
| ear_drift_60 | 0 of 500 |  |  | 2.0 | 0.1118 |
| ens_mom_ear | 0 of 500 |  |  | 2.0 | -0.0363 |

