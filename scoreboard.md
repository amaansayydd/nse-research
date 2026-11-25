# Scoreboard (forward-only)

Updated 2026-11-25 20:30 IST. Prediction days logged: 9. Days with a matured score: 7.

Only predictions written to `predictions.csv` before their outcome window opened are counted here.
Backtest and dress-rehearsal numbers never appear in this file.

## Rank IC by model and horizon

Target: return from the next session's open to the open h sessions later. `eff_obs` divides the day
count by the horizon because overlapping targets are not independent. An `ic_t` below 2 means nothing
yet. `days needed for t=2` assumes the IC measured so far is the true IC, which early on it is not.

| model | horizon | days | eff_obs | first | last | ic_mean | ic_sd | ic_t | top_excess_mean | top_hit | brier | ic_ex_ref_mean | days needed for t=2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | 1 | 6 | 6.0 | 2026-11-13 | 2026-11-20 | 0.0607 | 0.0780 | 1.91 | 0.14% | 52.62% | 0.2496 | 0.0679 | 7 |
| ear_drift_60 | 5 | 2 | 1.0 | 2026-11-13 | 2026-11-16 | 0.1050 | 0.0197 | 5.33 | 0.36% | 55.16% | 0.2491 | 0.1170 | 1 |
| ens_mom_ear | 1 | 6 | 6.0 | 2026-11-13 | 2026-11-20 | 0.0043 | 0.1030 | 0.10 | -0.25% | 47.33% | 0.2499 | 0.0635 | 2284 |
| ens_mom_ear | 5 | 2 | 1.0 | 2026-11-13 | 2026-11-16 | -0.0316 | 0.0485 | -0.65 | -1.44% | 38.00% | 0.2505 | 0.1051 | 47 |
| mom_12_1 | 1 | 7 | 7.0 | 2026-11-12 | 2026-11-20 | -0.0246 | 0.1251 | -0.52 | -0.45% | 43.15% | 0.2501 |  | 104 |
| mom_12_1 | 5 | 3 | 1.0 | 2026-11-12 | 2026-11-16 | -0.1021 | 0.0797 | -1.28 | -2.00% | 37.41% | 0.2513 |  | 12 |
| random | 1 | 7 | 7.0 | 2026-11-12 | 2026-11-20 | -0.0016 | 0.0416 | -0.10 | -0.03% | 52.00% | 0.2500 | -0.0020 | 2566 |
| random | 5 | 3 | 1.0 | 2026-11-12 | 2026-11-16 | 0.0198 | 0.0112 | 1.78 | -0.02% | 48.00% | 0.2500 | 0.0206 | 6 |
| rev_5 | 1 | 7 | 7.0 | 2026-11-12 | 2026-11-20 | 0.0006 | 0.1409 | 0.01 | -0.10% | 48.57% | 0.2500 | -0.0055 | 225955 |
| rev_5 | 5 | 3 | 1.0 | 2026-11-12 | 2026-11-16 | 0.0022 | 0.1278 | 0.02 | -1.12% | 38.00% | 0.2502 | -0.0134 | 68844 |

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
| universe, equal weight, all 500 (after costs) | 21d | -0.40% | -0.78% | -11.85% | 2.58% | -0.37% | 6.0 | 2.62% | 0.0 | 0.0 |  |  |
| NIFTYBEES buy and hold (no trading costs) | - | 2.03% | 1.27% | 88.32% | 17.36% | -1.63% |  |  |  |  |  |  |
| MOM30IETF buy and hold (Nifty 200 Momentum 30 fund) | - | -3.22% | -3.63% | -64.32% | 12.12% | -3.59% |  |  |  |  |  |  |
| MOMENTUM50 buy and hold (Nifty 500 Momentum 50 fund) | - | -2.37% | -2.79% | -53.08% | 16.36% | -3.09% |  |  |  |  |  |  |
| Nifty 50 price index (not investable) | - | 2.05% |  | 89.79% | 18.73% | -1.75% |  |  |  |  |  |  |
| random top 20 | 5d | -1.41% | -1.64% | -36.09% | 7.94% | -1.27% | 33.0 | 14.74% | 0.0 | 0.0 | -1.41% | 0.0 |
| random top 20 | 20d | -0.37% | -0.46% | -10.93% | 2.42% | -0.34% | 6.3 | 2.75% | 0.0 | 0.0 | -0.37% | 0.0 |
| mom_12_1 top 20 | 5d | -3.34% | -3.57% | -65.74% | 10.36% | -3.23% | 18.7 | 8.25% | 0.0 | 0.0 | -3.34% | 0.0 |
| mom_12_1 top 20 | 20d | -1.05% | -1.14% | -28.27% | 2.78% | -1.02% | 6.3 | 2.75% | 0.0 | 0.0 | -1.05% | 0.0 |
| rev_5 top 20 | 5d | -4.38% | -4.60% | -75.60% | 10.98% | -4.48% | 33.3 | 14.87% | 0.0 | 0.0 | -4.38% | 0.0 |
| rev_5 top 20 | 20d | -1.23% | -1.32% | -32.33% | 3.12% | -1.26% | 6.3 | 2.75% | 0.0 | 0.0 | -1.23% | 0.0 |
| ear_drift_60 top 20 | 5d | 0.61% | 0.25% | 21.10% | 6.03% | -0.76% | 15.8 | 6.89% | 0.0 | 0.0 | 0.61% | 0.0 |
| ear_drift_60 top 20 | 20d | 0.15% | 0.04% | 4.76% | 1.57% | -0.19% | 5.5 | 2.41% | 0.0 | 0.0 | 0.15% | 0.0 |
| ens_mom_ear top 20 | 5d | -1.38% | -1.61% | -35.47% | 9.12% | -1.86% | 17.0 | 7.45% | 0.0 | 0.0 | -1.38% | 0.0 |
| ens_mom_ear top 20 | 20d | -0.42% | -0.50% | -12.30% | 2.36% | -0.46% | 5.5 | 2.41% | 0.0 | 0.0 | -0.42% | 0.0 |

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
| results_advance_5d | 5 | 0 | 0 | 0 |  |  | 1.96 |  |  | too early: 0 of 250 sessions, 0 of 200 events |

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
| mom_12_1 | 1 | 0.0062 | 7 | -0.0246 | 2.71 | 43.57 | ok | 1064 |  |
| mom_12_1 | 5 | 0.0158 | 1 | -0.0209 | 0.19 | 19.51 | ok | 1175 |  |
| mom_12_1 | 20 | 0.0256 | 0 |  | 0.00 | 10.22 | ok | 1581 |  |
| rev_5 | 1 | 0.0114 | 7 | 0.0006 | 2.91 | 33.22 | ok | 506 |  |
| rev_5 | 5 | 0.0157 | 1 | 0.0093 | 0.00 | 17.71 | ok | 898 |  |
| rev_5 | 20 | 0.0044 | 0 |  | 0.00 | 13.15 | ok | 3420 |  |
| ear_drift_60 | 1 | 0.0072 | 6 | 0.0607 | 0.00 | 30.71 | ok | 412 |  |
| ear_drift_60 | 5 | 0.0135 | 1 | 0.0911 | 0.00 | 15.25 | ok | 605 |  |
| ear_drift_60 | 20 | 0.0205 | 0 |  | 0.00 | 8.25 | ok | 891 |  |
| ens_mom_ear | 1 | 0.0077 | 6 | 0.0043 | 0.81 | 38.71 | ok | 763 |  |
| ens_mom_ear | 5 | 0.0179 | 1 | -0.0659 | 0.53 | 18.07 | ok | 949 |  |
| ens_mom_ear | 20 | 0.0285 | 0 |  | 0.00 | 9.65 | ok | 1347 |  |

## Graduation (Phase 4)

Graduation is the point at which real capital may be considered. It needs every criterion below on
the forward record, and then the owner's explicit decision. Criteria v1.1: fixed on 2026-11-13, and G5
tightened on 2026-11-14 to the better of NIFTYBEES and the momentum fund, before any forward score existed.

There is no champion, so nothing can graduate. Where each challenger stands on the criteria that can already be measured:

| model | scored_sessions | ic_20 | ic_t | t_needed | ic_5 |
|---|---|---|---|---|---|
| ear_drift_60 | 0 of 500 |  |  | 2.0 | 0.1050 |
| ens_mom_ear | 0 of 500 |  |  | 2.0 | -0.0316 |

