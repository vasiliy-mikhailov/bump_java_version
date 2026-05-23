# attempt_3 — dataset expansion to 24 per cell (partial / in-flight)

## State at snapshot
Verifier still running on the host. Partial dataset committed reflects the cells / passes so far. 4 cells fully at 24/cell, 4 cells partial, 4 cells not yet started.

| Java | Family | attempted | passed | target |
|-----:|--------|--:|--:|--:|
| 8  | hibernate-5     | 14 | 10 | 24 |
| 8  | jakarta-ee-javax| 30 | **24** ✓ | 24 |
| 8  | junit4-mockito  | 0  | 0  | 24 (queued) |
| 8  | spring-boot-2   | 0  | 0  | 24 (queued) |
| 11 | hibernate-5     | 14 | 10 | 24 |
| 11 | jakarta-ee-javax| 32 | 17 | 24 |
| 11 | junit4-mockito  | 0  | 0  | 24 (queued) |
| 11 | spring-boot-2   | 27 | **24** ✓ | 24 |
| 17 | hibernate-5     | 0  | 0  | 24 (queued) |
| 17 | jakarta-ee-javax| 26 | **24** ✓ | 24 |
| 17 | junit4-mockito  | 18 | 15 | 20 (pool exhausted at 20) |
| 17 | spring-boot-2   | 24 | **24** ✓ | 24 |

**Total verified so far: 148** (vs attempt_2's 96).

## Approach
- Reused attempt_2's history-walk + classified candidate pools (509 + 1823 entries)
- `select_24.py` per-cell smaller-first, distinct-owner, up to 24
- `verify_baselines.py` adapted from attempt_2 with target=24, search-horizon=80
- Bounded semaphore at 4 concurrent docker runs; ThreadPoolExecutor(12) workers (one per cell)

## Why slow
~20 hours of wall-clock so far for 4 fully-verified cells. Each baseline build can take 2-15 minutes on cold-cache repos with multi-module Maven projects. The pool's smaller-first sort puts the fastest at the front but the worker still tries up to 80 candidates per cell looking for 24 passes.

## What to do next
Let the verifier finish (estimated 12-15 more hours). When complete:
1. Re-emit `attempt_3/java21-migration-dataset.json` with all 24/cell verified entries
2. Re-cluster failure patterns at 3x sample size — check which "bespoke" calls from attempt_2 grow proportionally (real common patterns) vs stay small (real tail noise)
3. Re-run the iter-13 champion recipe against the full 288 to measure build_post on a richer corpus

## Reusable artifacts
- `attempt_3/dataset_candidates.json` — 284 candidates pre-verification
- `attempt_3/verify/select_24.py` — selector
- `attempt_3/verify/verify_baselines.py` — verifier (24/cell target, 80 horizon)
- `attempt_3/verify/baseline/<repo>/{metrics.json,run.log}` — per-attempt outcomes
