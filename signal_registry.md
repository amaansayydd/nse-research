# Signal registry

Status values: candidate → shadow → champion → decaying → retired. `rejected` = failed Phase 2.
Baselines are known effects kept as yardsticks. They are not discoveries and are never "champion".

| signal | family | status | since | forward IC (rolling) | notes |
|---|---|---|---|---|---|
| `random` v1 | control | baseline | 2026-11-12 | see scoreboard | Must score zero. If it does not, the scorer is leaking. |
| `mom_12_1` v1 | momentum (known) | baseline | 2026-11-12 | see scoreboard | Return over the 231 sessions ending 21 sessions ago. |
| `rev_5` v1 | short-term reversal (known) | baseline | 2026-11-12 | see scoreboard | Minus the last 5 sessions' return. Gross IC is expected; it does not survive delivery costs. |
| `ear_drift_60` v1 (T-0002, F-001) | post-earnings drift (known) | shadow | 2026-11-13 | see scoreboard | Backtest: residual IC t 5.96, top 20 +5.3% a year over the universe after costs, flat in 2025. First counted prediction: as-of 2026-11-13. Silent on days it can rank fewer than 100 names. |
| `ens_mom_ear` v1 (T-0004, F-002) | momentum + post-earnings drift (known, combined) | shadow | 2026-11-13 | see scoreboard | Backtest: IC 0.057 (t 4.7), top 20 +16.3% a year over the universe after costs, but 0.90 correlated with momentum and negative in 2025. Weights start equal and move only on forward ICs. Rows for 2026-11-12 are void. |
| `insider_buys` (T-0005) | insider purchases (known family) | candidate | 2026-11-13 | not in the daily run | Passed Phase 2: +1.07% over 20 sessions per event, t 3.4, all 10 years. Thin: larger purchases do worse, gone within days, only 58 events a year now. Not forward-testable alone. Owner decided 2026-11-14 to keep the last shadow slot free. |
| `deliv_ret_corr_60` (T-0001) | volume-conditioned continuation | rejected | 2026-11-12 | – | IC without return: a low-volatility tilt. Long-only top 20 lost 6.1% a year to the universe. |
| `order_win` (T-0003) | news drift (text) | rejected | 2026-11-12 | – | No 20-session drift; a significant 5-session give-back instead. |
| `meet_abnormal_20` (T-0006) | investor-meeting notices (text counts) | rejected | 2026-11-14 | – | IC 0.006 (t 0.7) on six usable years. Nothing after known effects. |
| `results_advance_7` (T-0007) | results calendar (date moved earlier) | rejected | 2026-11-14 | – | +0.42% over 20 sessions (t 1.8), nothing after costs. Post-hoc, in sample: +1.0% over 5 sessions (t 7.5) that reverses after the results. A 5-session version would be a new trial; not registered. |

No champion yet. Reference to beat: `mom_12_1`. Shadow slots used: 2 of 3. Challengers ever started: 2.
The test, its margin and the retirement rules are in `research_log.md`, Phase 3 rules v1.
