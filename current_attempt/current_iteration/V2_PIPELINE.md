# Bump-java v2 — GEPA-optimized program-synthesis pipeline

Replaces the interactive agentic bumper (which thrashed/rabbit-holed) with a pipeline that
**emits a declarative conversion program, runs it deterministically, and scores it with the combined gate.**
GEPA optimizes the one LLM module that matters (`generate_program`).

REUSED unchanged (the execution + reward backend, already built & validated):
- Sealed single-JDK images `bjv-jvm{8,11,17,21,25}` (JDK + mvn + gradle + osv-scanner + frozen OSV DB).
- `jvmjob` (in-image build/test/scan), offline substrate (Nexus mirror, gradle dists pinned both classifiers).
- The combined gate + scorer (`tools/score.py`): build + rename-robust conserve + bytecode `effective_target` + CWE.
REPLACED: the JDK-less interactive controller + `oh_run` bumper → the pipeline below. The agent NEVER gets bash/docker.

---

## 1. The program grammar (what `generate_program` emits)

A **declarative, ordered list of ops** from a FIXED vocabulary. The harness APPLIES it (recipes AND intents are
harness-applied, never agent-applied) — so purity is structural: a hand-edit is not expressible.

```jsonc
{ "program": [
    { "op": "intent", "name": "bump_wrapper" },                 // gradle wrapper -> pinned staged version
    { "op": "intent", "name": "set_target" },                   // source/release/toolchain -> jv_to
    { "op": "recipe", "env": "to",   "fqn": "org.openrewrite.java.migrate.UpgradePluginsForJava17" },
    { "op": "recipe", "env": "to",   "fqn": "org.openrewrite.java.migrate.UpgradeBuildToJava17" },
    { "op": "recipe", "env": "from", "fqn": "org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7" }
  ],
  "rationale": "…one line why this sequence…" }
```

- **`recipe`** — run one OpenRewrite recipe by FQN at stock defaults, in the `from` or `to` sealed env. `fqn` MUST be
  in the **allowed recipe catalog** (`catalog/recipes.txt`, operator+GEPA grow it freely; artifact coords are fixed per catalog entry).
- **`intent`** — one of the **N predefined intents** (operator-gated allow-list): `set_target`, `bump_wrapper`
  (today's two). Parametrized only by the fixed `jv_to`. Harness-applied, deterministic, auditable.
- No other `op` type exists → no hand-edit, no `skipTests`, no test deletion can be expressed.

## 2. The four tools (orchestrator's ONLY affordances — no bash, no docker)

```
detect_version(repo, sha) -> { from:int, build_tool:"maven"|"gradle" }
    Deterministic: parse pom.xml / build.gradle / toolchain. (Corpus gives `from`; this confirms + gets build_tool.)

generate_program(from, to, build_tool, build_files, last_failure_log?) -> { program:[op], rationale:str }
    THE GEPA-OPTIMIZED MODULE. One LLM call. Emits the op list from the grammar above.
    `last_failure_log` is set on a reflect retry; absent on the first call.

check_program(program) -> { ok:bool, violations:[str] }
    Static gate: every op.op in {recipe,intent}; every recipe.fqn in catalog; every intent.name in allow-list.
    Anything else -> ok=false (the structural anti-cheat). Optional LLM judge for subtle abuse later.

run_and_score(repo, sha, from, to, program) -> { verdict, pre_pass, post_pass, lost, effective_target, dep_cwes, logs }
    Reuses the sealed harness: clone -> baseline (jvmjob build/test under jv_from) -> APPLY program (recipes via the
    rewrite plugin/init-script, intents via deterministic harness edits, each in its op.env) -> combined gate
    (build/test/conserve under jv_to + effective_target==jv_to + osv scan) -> verdict + logs.
```

## 3. Orchestrator = OpenHands with ONLY these 4 tools (NO default preset)

Fixed, dumb prompt (NOT GEPA-optimized):
```
Bump {repo}@{sha} from Java {from} to {to}.
1. call detect_version (confirm from / build_tool).
2. call generate_program.
3. call check_program. If not ok, call generate_program again passing the violations as last_failure_log; repeat.
4. call run_and_score.
5. If verdict != PASS, call generate_program again with the run logs as last_failure_log, then check_program, then
   run_and_score. Stop when verdict==PASS, OR generate_program returns the same program / an empty program (it has
   nothing new to try — an honest bail). There is NO step budget; you stop on convergence or PASS, not a count.
6. Report the final verdict.
Use ONLY these four tools. You have no shell, no docker, no file access.
```
The reflect loop terminates by **convergence** (generator stops improving) or PASS — never a step cap (RLVR: no budgets).

## 4. Where GEPA plugs in

- **Module optimized:** `generate_program`'s prompt (+ the recipe catalog it draws from). Nothing else.
- **Metric (per example):** the combined-gate result from `run_and_score`. Graded to guide search:
  `1.0` PASS; partial credit `0.4*(build&conserve) + 0.3*(target==to) + 0.3*(cwe_clean)`; `0` on NO_BASELINE/error.
- **Train/val set:** corpus baselines (`baselines_peryear.json.jsonl`) across hops 8→11/11→17/17→21/21→25.
- **Reflective feedback:** `run_and_score.logs` + `check_program.violations` — GEPA reads them to mutate the prompt
  (e.g. "Java-17 component-scan ASM wall → add `UpgradeSpringBoot_2_7`").
- **Pareto:** across repos/hops, so a fix that helps one family but regresses another isn't kept (anti-overfit).
- **Catalog growth:** GEPA may add recipe FQNs to `catalog/recipes.txt` freely (auditable); new **intents** stay operator-gated.

## 5. Why this fixes what v1 hit

- Thrashing/convergence → gone: one LLM call emits a plan; deterministic execution; reflect loop bounded by convergence.
- Docker/harness leak → gone: orchestrator has 4 high-level tools, no shell/docker; the generator is a pure text call.
- Purity (no manual edits) → structural: not expressible in the grammar; `check_program` enforces the catalog.
- Cheat-resistance → `check_program` (static) + the gate (`run_and_score`).
- Auditable/reproducible: the program IS the artifact; same program → same result (offline substrate).
