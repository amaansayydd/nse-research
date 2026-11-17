# Run log

One line per scheduled run: timestamp (IST), outcome, data date, rows written, errors.
Missed or failed days are logged and skipped. Predictions are never backfilled.

| run at (IST) | outcome | data date | predictions written | notes |
|---|---|---|---|---|
| 2026-11-12 | manual | – | 0 | Phase 0 build: historical download + cleaned research dataset. No scheduled runs yet. |
| 2026-11-12 11:55 | NO_NEW_SESSION | 2026-11-11 | 0 | no forward-period session published yet |
| 2026-11-12 20:30 | OK | 2026-11-12 | 1489 |  |
| 2026-11-12 22:30 | ALREADY_DONE | 2026-11-12 | 0 |  |
| 2026-11-12 23:10 | ALREADY_DONE | 2026-11-12 | 0 |  |
| 2026-11-13 07:56 | FAIL | - | 0 | TypeError: ufunc 'isfinite' not supported for the input types, and the inputs could not be safely coerced to any supported types according to the casting rule ''safe'' |
| 2026-11-13 10:21 | ALREADY_DONE | 2026-11-12 | 0 |  |
| 2026-11-13 11:15 | ALREADY_DONE | 2026-11-12 | 0 |  |
| 2026-11-13 20:30 | OK | 2026-11-13 | 2452 |  |
| 2026-11-13 22:30 | ALREADY_DONE | 2026-11-13 | 0 |  |
| 2026-11-14 07:57 | ALREADY_DONE | 2026-11-13 | 0 | pr 2026-11-14: error:ConnectionError; mto 2026-11-14: error:ConnectionError; symbolchange ConnectionError; register refresh failed (ConnectionError); using previous copy |
| 2026-11-14 20:30 | ALREADY_DONE | 2026-11-13 | 0 |  |
| 2026-11-14 22:30 | ALREADY_DONE | 2026-11-13 | 0 |  |
| 2026-11-15 10:47 | ALREADY_DONE | 2026-11-13 | 0 |  |
| 2026-11-15 20:30 | ALREADY_DONE | 2026-11-13 | 0 |  |
| 2026-11-15 22:30 | ALREADY_DONE | 2026-11-13 | 0 |  |
| 2026-11-16 07:46 | ALREADY_DONE | 2026-11-13 | 0 | pr 2026-11-14: error:ConnectionError; mto 2026-11-14: error:ConnectionError; pr 2026-11-15: error:ConnectionError; mto 2026-11-15: error:ConnectionError; pr 2026-11-16: error:ConnectionError; mto 2026-11-16: error:ConnectionError; symbolchange ConnectionError; register refresh failed (ConnectionError); using previous copy |
| 2026-11-16 20:30 | OK | 2026-11-16 | 2472 | scored 3 date-model-horizon results |
| 2026-11-16 22:30 | ALREADY_DONE | 2026-11-16 | 0 |  |
| 2026-11-17 07:56 | ALREADY_DONE | 2026-11-16 | 0 | pr 2026-11-14: error:ConnectionError; mto 2026-11-14: error:ConnectionError; pr 2026-11-15: error:ConnectionError; mto 2026-11-15: error:ConnectionError; pr 2026-11-17: error:ConnectionError; symbolchange ReadTimeout |
| 2026-11-17 20:32 | OK | 2026-11-17 | 2485 | scored 5 date-model-horizon results |
| 2026-11-17 22:30 | ALREADY_DONE | 2026-11-17 | 0 |  |
