# Champion changelog

No champion yet. Every promotion or rollback is recorded here with the forward evidence that justified it.

## How a promotion is made (Phase 3 rules v1)

1. The scoreboard shows a challenger as ELIGIBLE at a checkpoint (250, 375, 500 ... scored sessions).
2. Portfolio check on the sessions up to that checkpoint: its simulated top 20 after costs is at
   least the reference's and the universe hurdle.
3. The owner runs the holdout check (one of 3 looks) and decides.
4. `champion.json` is edited (champion, reference, former_champions), this file gets an entry with
   the numbers, and `signal_registry.md` is updated. The former champion stays in the daily run.
5. A rollback is the same edit in reverse, with its reason, recorded here.

## Log

| Date | Event | Detail |
|---|---|---|
| 2026-11-13 | Phase 3 started | Seat empty. Reference: `mom_12_1`. Challengers in shadow: `ear_drift_60` (F-001), `ens_mom_ear` (F-002). N = 2, required t 2.24. First counted challenger predictions: as-of 2026-11-13 |
| 2026-11-13 | Rows voided | 489 `ens_mom_ear` rows for as-of 2026-11-12, written at 07:56 by uncommitted code, are excluded from scoring (`void_predictions.csv`). Decided at 10:10, before any outcome was scored. No baseline row affected |
| 2026-11-13 | Deployment changed | The scheduled job runs a pinned copy of committed code (`scripts/deploy.sh`), first release 08be5f6. `code_commit` in the log is now the deployed release |
| 2026-11-14 | Phase 3 rules v1.1 approved | Observation tier added (owner approval on draft 2, commit 75652d5). Rules for challengers and the champion are unchanged: N = 2, required t 2.24, slots 2 of 3 |
| 2026-11-14 | Observed signal started | `results_advance_5d` (T-0008, O-001) runs in the observation tier from release 8343161. M = 1, required t 1.96, 250 sessions and 200 events for the label. No slot taken; challengers' margin stays 2.24. First evaluation that can count: as-of 2026-11-16 |
