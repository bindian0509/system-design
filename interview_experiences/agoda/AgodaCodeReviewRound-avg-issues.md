# AgodaCodeReviewRound average drift cases

Context: 100 sensors call `updateReading` concurrently on one `AgodaCodeReviewRound`. The method does a read-modify-write on separate `float` and `int` fields without synchronization. Each update can interleave, so writes race and some updates are lost. Java makes 32‑bit primitive writes atomic, but without synchronization/volatile the composite operation is not atomic and visibility is weak, so stale reads and lost updates occur.

## Case 1: average drops below 10
- Start: `tempReading = 0`, `readingCount = 0`.
- Thread A and B both read `tempReading` as 0, add 10, and both write back 10 (one addition lost).
- Thread A increments `readingCount` to 1; Thread B reads 1 and writes 2 (both increments kept).
- Result: `tempReading = 10`, `readingCount = 2`, `avg = 10 / 2 = 5` (below 10).
- Root cause: lost write on `tempReading` due to racy read-modify-write, while `readingCount` increments both landed.

## Case 2: average rises above 10
- Start: `tempReading = 0`, `readingCount = 0`.
- Thread A and B both read `tempReading` as 0, add 10 each, but one write arrives after the other so final `tempReading = 20` (both additions kept).
- Thread A increments `readingCount` to 1; Thread B also reads original `readingCount = 0` (stale due to race/visibility) and writes 1, losing an increment.
- Result: `tempReading = 20`, `readingCount = 1`, `avg = 20 / 1 = 20` (above 10).
- Root cause: lost write on `readingCount` while both temperature additions landed.

## Fix
Make updates atomic and reads consistent (e.g., use `DoubleAdder` + `LongAdder`, or synchronize both methods and switch to `double`). This prevents lost updates and visibility issues.

