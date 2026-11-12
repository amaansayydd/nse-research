# Signal registry

Status values: candidate → shadow → champion → decaying → retired.
Baselines are known effects kept as yardsticks. They are not discoveries and are never "champion".

| signal | family | status | since | forward IC (rolling) | notes |
|---|---|---|---|---|---|
| `random` v1 | control | baseline | 2026-11-12 | see scoreboard | Must score zero. If it does not, the scorer is leaking. |
| `mom_12_1` v1 | momentum (known) | baseline | 2026-11-12 | see scoreboard | Return over the 231 sessions ending 21 sessions ago. |
| `rev_5` v1 | short-term reversal (known) | baseline | 2026-11-12 | see scoreboard | Minus the last 5 sessions' return. Gross IC is expected; it does not survive delivery costs. |

No champion yet. A challenger must beat the best baseline on forward data under the Phase 3 test.
