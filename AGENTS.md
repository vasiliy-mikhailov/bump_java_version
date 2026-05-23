# AGENTS.md

**Writing to the agent:** Prefer compact fitness functions and constraints over implementation instructions; the agent is capable of filling the gaps itself because it has tool access, internet search, sandboxed execution, verification, and iterative repair capabilities.

**Per-attempt history:** each `attempt_N/README.md` is a historical snapshot of the AGENTS.md state under which that attempt ran. It is not read by the agent — it exists only for audit.

**Fitness structure:**
- Operational (items 1–3): workdir, containment, access — preconditions every iteration must respect.
- **Recipe** (item 4): the primary fitness — find the OpenRewrite recipe composition that produces the highest-quality Java 21 conversion of the dataset. Ralph-looped at the **coarse** level (whole-recipe mutations / swaps / catalog additions).
- **vLLM spin-up** (item 5): the inference endpoint observables, ralph-looped over container / proxy config until satisfied.
- **Dataset rediscovery** (item 6): the corpus the recipe fitness measures against, ralph-looped over candidate repos.
- **Per-failing-repo refinement** (item 7): a finer-grained ralph loop nested under the recipe fitness. Used when the coarse loop plateaus on the build-success metric.
- **Runner saturation** (item 8): keep the verifier host loaded enough to make progress without thrashing.
- **Staged migration** (item 9): when the coarse single-jump recipe plateaus on the build-success metric due to toolchain catch-22s, split the migration into per-source-Java-version stages, each running its OpenRewrite pass under a JDK the original source compiles against.

1. **Workdir:** `$HOME/java_8_11_17_to_java_21`.
2. **Containment:** all language toolchains (JDK / Maven / Gradle / OpenRewrite) and recipe execution run inside Docker. If a host resource this project needs (port, mount, GPU memory, …) is held by something unrelated, free it in favour of this project. Cache external downloads (Maven, npm, HF weights, …) on a host-side bind mount shared across containers — public registries rate-limit hard, so the first cold sweep needs a settled mirror and the cache must survive across iterations.
3. **Access:** SSH to the work host is multiplexed (ControlMaster + ControlPath + ControlPersist) so every call in a session reuses one TCP + auth handshake instead of dialling out per command.
4. **Fitness (recipe):** find the OpenRewrite recipe composition that produces the highest-quality Java 21 conversion of every repo in `java21-migration-dataset.json` — where "high quality" is whatever the agent reasons it should mean in this domain given all required tools including vLLM Qwen 3.6 27B FP8. Crafted through a ralph loop (apply → check → improve), with trajectory and per-recipe-by-cell contribution as first-class outputs. When this coarse loop plateaus on the corpus build-success metric, refine through item 7 or restructure through item 9.
5. **Fitness (vLLM spin-up):** stand up the endpoint until all five observables hold; arrive there through a ralph loop (try → check → adjust) over container flags, model args, mounts, and reverse-proxy config. An existing Caddy already owns `:443` on this host for other services.
   - `curl https://inference.mikhailov.tech/v1/models` lists `qwen3.6-27b-fp8`.
   - Served with a 128k-token context window (`max_model_len ≈ 131072`).
   - Weights loaded from `/mnt/steam/forge/shared/models`, no re-download.
   - Tool-call ping/pong smoke: a `POST /v1/chat/completions` request offering a single `ping(message: string)` tool, with the user message "say ping via the tool", yields `choices[0].message.tool_calls[0].function.name == "ping"` parsed structurally (vLLM's `--tool-call-parser` must be the one that matches Qwen 3.6's native tool-call output).
   - No access without `VLLM_API_KEY` from `.env`: unauthenticated requests are rejected; requests bearing the key succeed.
6. **Fitness (dataset rediscovery):** curate `java21-migration-dataset.json` as 24 distinct-owner samples per (Java version × dependency family) cell, where Java version ∈ {8, 11, 17} and dependency family ∈ the popular dependencies that OpenRewrite targets as having breaking changes for Java 21 migration. Each entry is clone-and-checkout reproducible from `commit_sha` alone, baseline-buildable inside the runner container on its declared Java version, and genuinely uses the cell's dependency family in source. Prefer smaller repos — single-module or low-module-count, modest LOC — so the wall-cap doesn't strand large multi-module projects. If a Java version cell can't be filled from current-state repos — because the world has migrated past that (Java version × dependency family) intersection — walk pom.xml git history of Java 21 repos and use the older commit_sha at which the file showed the target Java version + family signature. Iterate candidate repos through a ralph loop, balancing the matrix.
7. **Fitness (per-failing-repo refinement):** raise the corpus build-success rate past where coarse recipe mutations plateau, leveraging vLLM Qwen 3.6 27B FP8 and Claude as solution-finder + judges throughout.
   - **Constraints:** declarative configuration deltas only.
   - **Search:** ground each candidate fix in a known community workaround.
   - **Reward:** real `build_post 0 → 1` flips net of regressions on the full corpus.
   - **Repeat:** simplest cluster first; stop when only bespoke engineering remains.
8. **Fitness (runner saturation):** keep the verifier host CPU between 60 % and 80 % of cores *while items 4 / 6 / 7 / 9 are running* — this fitness composes with them rather than standing alone — saturation only counts toward the composite objective when a parent loop is making progress.
   - **Constraints:** any concurrency dial the agent can reach — worker semaphores, docker `--cpus`/`--memory`, parallel Maven / Gradle.
   - **Search:** sample load periodically, ask vLLM Qwen 3.6 27B FP8 what to adjust given the recent action history and which parent loop is active.
   - **Reward:** sustained band hit without thrashing or stalling the parent loop.
   - **Repeat:** continuous, dampened against oscillation; pause when no parent loop is active.
9. **Fitness (staged migration):** raise the corpus build-success rate above the single-jump declarative plateau by splitting the migration into per-source-Java-version stages, each running its OpenRewrite pass under a JDK the original source compiles against.
   - **Constraints:** declarative configuration deltas only, but split across N stage recipes (one per intermediate JDK target). Each stage's recipes and dependency versions must be compatible with that stage's Java version. Each stage's pom and source edits persist into the next stage's working tree. No custom Java AST recipes.
   - **Search:** for each stage, select recipes and pin dep versions that this JDK can actually execute. Ground every placement in upstream migration guides (Spring, Hibernate, Lombok release notes, JUnit/Mockito changelogs).
   - **Reward:** real `build_post 0 → 1` flips on the full corpus, net of regressions vs. the prior attempt's single-jump baseline. A stage that un-breaks a catch-22 without flipping immediately counts only when the downstream stage realises the flip. Per-stage `mvn compile` under that stage's target JDK is the per-stage gate.
   - **Repeat:** stage-by-stage; if a stage's intermediate compile fails on most repos, the stage is too aggressive and must be tightened before the next is built.
