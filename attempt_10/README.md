# attempt_10 — Qwen-as-proposer + OpenHands investigator

## Thesis

attempt_9 hit the ceiling of **what Qwen can do from partial information**
(failure-observation tail + library hints + claude-recipes, no source access):
- attempt_8 baseline: **162/202 PASS (80.2%)**
- attempt_9 v3 (full enriched library + claude-recipes + COMPAT_MATRIX gating): **135/187 = 72.2%** — *regression*

The regression is informative: every library entry past a point gives Qwen one
more wrong thing to try when it can't actually see the code. The path forward
isn't "more hints"; it's **letting Qwen see the source for the cited file**.

attempt_10 keeps the attempt_9 proposer surface (same prompt, same library, same
recipes), and adds a delegated investigator that reads the working tree and
returns a bounded structural finding before each chain proposal. The
investigator is OpenHands (ff #11 contract) backed by Qwen 3.6 27B FP8; its
event stream sinks to `/var/log/observe/openhands.jsonl` for ff #7 to compact.

## What attempt_10 inherits

- ff #11 (proposer investigation depth) Contract is in `AGENTS.md` and names
  OpenHands as the investigator runtime + the credential discipline that
  applies to every OpenHands-fronting surface.
- ff #7 (compact observations) Contract is multi-resolution
  (`10s / 60s / 10m / 60m`), captures the OpenHands event stream alongside the
  Vector streams, and reports gauge first/last/min/max + counter deltas so
  adjacent windows actually differ.

## Tools (in `attempt_10/tools/`)

- `oh_event_sink.py` — Conversation callback writing Vector-shape JSONL rows
  to `/var/log/observe/openhands.jsonl`; one row per Event; summaries capped at
  200 chars so the captured stream never inflates the compactor budget.
- `oh_one_live.py` — single-stage investigator harness with live visualizer +
  `LLMSummarizingCondenser` backed by `COMPACTOR_VLLM_*`; installs the event
  sink as a Conversation callback. Per ff #11: investigators have their own
  context window, their own tool budget, and cannot mutate the build.

## Seed runs (manual, watched)

The four manual runs were ff #11 architecture validation, not corpus
measurement; their findings are in `attempt_10/investigator_findings/`:

| slug | wall | events (post-condense) | condenser fired | finding |
|---|---|---|---|---|
| Syzmel_TASKHD__J11toJ21 | 72s | 23 | 0× | SpringFox→SpringDoc recipe stripped deps but left two dead `SpringFox*Configuration.java` |
| BordeauxJUG_bdxjug-api__J8toJ21 | 88s | 23 | 0× | `fix_lombok_plugin_version` tried `1.18.30`; Maven Central ceiling is `1.18.20.0` |
| daxyonis_pdi-fundraising__J11toJ21 | 102s | 36 | 0× | `thymeleaf-layout-dialect` BOM-pinned to 2.x; Jakarta needs 3.x |
| DsTyM_PharmaciesOnDutyAttica__J17toJ21 | 494s | 98 (134 raw) | 3× | SB3 + JDK21 left `javax.persistence.*` in 3 entities + `javax.annotation.PostConstruct` in main app → `contextLoads` cascade-fails 10 tests |

Each finding is the structural detail the proposer could not have inferred from
the failure observation alone. The DsTyM case demonstrates condenser-handles-
deep-investigation working in practice: 134 raw events folded to 98 by
`LLMSummarizingCondenser` across three condensation rounds without losing the
diagnostic thread.

## What's not yet built

- The investigator runs **standalone** today — it produces a finding but
  doesn't yet feed the finding back into the proposer's iter-2 prompt. Closing
  that loop is the next milestone.
- Corpus sweep at attempt_10 contract has not been run. The four manual runs
  are existence proof, not a reward measurement.
- Two of the four manual runs lost their findings to a JSON-extract regex
  bug in `oh_one_live.py` (agent emitted clean JSON; harness regex didn't
  capture it). Findings recovered manually from the log tails. Harness fix
  pending.

## Reward (when measured)

vs attempt_8's 80.2% baseline on the same 202-stage corpus, with the same
proposer prompt and recipe set, and with the investigator added as the only
material difference. Anything ≥80.2% is a win for the architecture; the
target is the long tail of FAIL clusters that ff #11 was designed for
(structural source detail unavailable from observation alone).
