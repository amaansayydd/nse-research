# Signal registry

Status values: candidate → shadow → champion → decaying → retired. `rejected` = failed Phase 2.
Baselines are known effects kept as yardsticks. They are not discoveries and are never "champion".

| signal | family | status | since | forward IC (rolling) | notes |
|---|---|---|---|---|---|
| `random` v1 | control | baseline | 2026-11-12 | see scoreboard | Must score zero. If it does not, the scorer is leaking. |
| `mom_12_1` v1 | momentum (known) | baseline | 2026-11-12 | see scoreboard | Return over the 231 sessions ending 21 sessions ago. |
| `rev_5` v1 | short-term reversal (known) | baseline | 2026-11-12 | see scoreboard | Minus the last 5 sessions' return. Gross IC is expected; it does not survive delivery costs. |
| `ear_drift_60` (T-0002) | post-earnings drift (known) | candidate | 2026-11-12 | not in the daily run yet | Passed Phase 2 on research data: residual IC t 5.96, top 20 +5.3% a year over the universe after costs. Flat in 2025. Needs board-meeting notices in the production run before it can shadow. |
| `deliv_ret_corr_60` (T-0001) | volume-conditioned continuation | rejected | 2026-11-12 | – | IC without return: a low-volatility tilt. Long-only top 20 lost 6.1% a year to the universe. |
| `order_win` (T-0003) | news drift (text) | rejected | 2026-11-12 | – | No 20-session drift; a significant 5-session give-back instead. |

No champion yet. A challenger must beat the best baseline on forward data under the Phase 3 test.
