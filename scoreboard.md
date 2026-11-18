# Scoreboard (forward-only)

Updated 2026-11-18 22:30 IST. Prediction days logged: 5. Days with a matured score: 3.

Only predictions written to `predictions.csv` before their outcome window opened are counted here.
Backtest and dress-rehearsal numbers never appear in this file.

## Rank IC by model and horizon

Target: return from the next session's open to the open h sessions later. `eff_obs` divides the day
count by the horizon because overlapping targets are not independent. An `ic_t` below 2 means nothing
yet. `days needed for t=2` assumes the IC measured so far is the true IC, which early on it is not.

| model | horizon | days | eff_obs | first | last | ic_mean | ic_sd | ic_t | top_excess_mean | top_hit | brier | ic_ex_ref_mean | days needed for t=2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ear_drift_60 | 1 | 2 | 2.0 | 2026-11-13 | 2026-11-16 | 0.0514 | 0.0763 | 0.95 | -0.19% | 48.87% | 0.2496 | 0.0603 | 9 |
| ens_mom_ear | 1 | 2 | 2.0 | 2026-11-13 | 2026-11-16 | 0.0071 | 0.0350 | 0.29 | -0.09% | 50.00% | 0.2497 | 0.0625 | 97 |
| mom_12_1 | 1 | 3 | 3.0 | 2026-11-12 | 2026-11-16 | 0.0172 | 0.1392 | 0.21 | -0.34% | 44.90% | 0.2498 |  | 263 |
| random | 1 | 3 | 3.0 | 2026-11-12 | 2026-11-16 | -0.0240 | 0.0301 | -1.38 | -0.05% | 46.67% | 0.2500 | -0.0223 | 6 |
| rev_5 | 1 | 3 | 3.0 | 2026-11-12 | 2026-11-16 | 0.0688 | 0.1635 | 0.73 | 0.28% | 54.00% | 0.2498 | 0.0563 | 23 |

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
| universe, equal weight, all 500 (after costs) | 21d | -0.30% | -0.49% | -17.43% | 1.37% | -0.28% | 6.0 | 2.62% | 0.0 | 0.0 |  |  |
| NIFTYBEES buy and hold (no trading costs) | - | -0.11% | -0.54% | -6.96% | 10.20% | -0.59% |  |  |  |  |  |  |
| MOM30IETF buy and hold (Nifty 200 Momentum 30 fund) | - | -2.22% | -2.63% | -75.70% | 13.44% | -2.60% |  |  |  |  |  |  |
| MOMENTUM50 buy and hold (Nifty 500 Momentum 50 fund) | - | -1.98% | -2.40% | -71.71% | 22.57% | -2.71% |  |  |  |  |  |  |
| Nifty 50 price index (not investable) | - | -0.28% |  | -16.31% | 10.19% | -0.63% |  |  |  |  |  |  |
| random top 20 | 5d | -1.45% | -1.63% | -60.12% | 3.87% | -1.25% | 25.2 | 11.02% | 0.0 | 0.0 | -1.45% | 0.0 |
| random top 20 | 20d | -0.36% | -0.41% | -20.43% | 0.96% | -0.31% | 6.3 | 2.75% | 0.0 | 0.0 | -0.36% | 0.0 |
| mom_12_1 top 20 | 5d | -1.73% | -1.92% | -66.74% | 6.99% | -1.62% | 25.2 | 11.02% | 0.0 | 0.0 | -1.73% | 0.0 |
| mom_12_1 top 20 | 20d | -0.43% | -0.48% | -23.92% | 1.74% | -0.40% | 6.3 | 2.75% | 0.0 | 0.0 | -0.43% | 0.0 |
| rev_5 top 20 | 5d | -1.70% | -1.88% | -66.04% | 7.09% | -1.81% | 25.2 | 11.02% | 0.0 | 0.0 | -1.70% | 0.0 |
| rev_5 top 20 | 20d | -0.42% | -0.47% | -23.53% | 1.76% | -0.45% | 6.3 | 2.75% | 0.0 | 0.0 | -0.42% | 0.0 |
| ear_drift_60 top 20 | 5d | -0.76% | -0.90% | -38.32% | 3.86% | -0.76% | 18.9 | 8.26% | 0.0 | 0.0 | -0.76% | 0.0 |
| ear_drift_60 top 20 | 20d | -0.19% | -0.23% | -11.35% | 0.96% | -0.19% | 4.7 | 2.07% | 0.0 | 0.0 | -0.19% | 0.0 |
| ens_mom_ear top 20 | 5d | -0.74% | -0.88% | -37.18% | 5.40% | -0.74% | 18.9 | 8.26% | 0.0 | 0.0 | -0.74% | 0.0 |
| ens_mom_ear top 20 | 20d | -0.18% | -0.22% | -10.94% | 1.35% | -0.18% | 4.7 | 2.07% | 0.0 | 0.0 | -0.18% | 0.0 |

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
| mom_12_1 | 1 | 0.0062 | 3 | 0.0172 | 0.77 | 43.57 | ok | 1064 |  |
| mom_12_1 | 5 | 0.0158 | 0 |  | 0.00 | 19.51 | ok | 1175 |  |
| mom_12_1 | 20 | 0.0256 | 0 |  | 0.00 | 10.22 | ok | 1581 |  |
| rev_5 | 1 | 0.0114 | 3 | 0.0688 | 1.01 | 33.22 | ok | 506 |  |
| rev_5 | 5 | 0.0157 | 0 |  | 0.00 | 17.71 | ok | 898 |  |
| rev_5 | 20 | 0.0044 | 0 |  | 0.00 | 13.15 | ok | 3420 |  |
| ear_drift_60 | 1 | 0.0072 | 2 | 0.0514 | 0.10 | 30.71 | ok | 412 |  |
| ear_drift_60 | 5 | 0.0135 | 0 |  | 0.00 | 15.25 | ok | 605 |  |
| ear_drift_60 | 20 | 0.0205 | 0 |  | 0.00 | 8.25 | ok | 891 |  |
| ens_mom_ear | 1 | 0.0077 | 2 | 0.0071 | 0.00 | 38.71 | ok | 763 |  |
| ens_mom_ear | 5 | 0.0179 | 0 |  | 0.00 | 18.07 | ok | 949 |  |
| ens_mom_ear | 20 | 0.0285 | 0 |  | 0.00 | 9.65 | ok | 1347 |  |

## Graduation (Phase 4)

Graduation is the point at which real capital may be considered. It needs every criterion below on
the forward record, and then the owner's explicit decision. Criteria v1.1: fixed on 2026-11-13, and G5
tightened on 2026-11-14 to the better of NIFTYBEES and the momentum fund, before any forward score existed.

There is no champion, so nothing can graduate. Where each challenger stands on the criteria that can already be measured:

| model | scored_sessions | ic_20 | ic_t | t_needed | ic_5 |
|---|---|---|---|---|---|
| ear_drift_60 | 0 of 500 |  |  | 2.0 |  |
| ens_mom_ear | 0 of 500 |  |  | 2.0 |  |

