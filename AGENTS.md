# AGENTS.md

**Per-attempt history:** each `attempt_N/README.md` is a historical snapshot of the AGENTS.md state under which that attempt ran. It is not read by the agent — it exists only for audit.

0. **Fitness (writing this file):** keep AGENTS.md compact and outcome-named so the agent re-derives the *how* every iteration from its tools and the corpus.
   - **Constraints:** no implementation instructions the agent can fill itself, no enumerations that age, no justifications for the rule alongside the rule.
   - **Search:** read → why → intent — when revisiting a clause, ask "why is this here?"; if the answer is implementation detail, enumeration, or justification, strip it back to the rule itself.
   - **Reward:** cuts that lose words without losing the rule.
   - **Repeat:** every editing pass.
1. **Fitness (recipe):** for every repo in `java21-migration-dataset.json`, find an OpenRewrite recipe SEQUENCE of `(label, jdk, recipes)` steps that builds clean on jv_to under `mvn compile` at every step, not just the last. The baseline to beat per repo is the one-shot `UpgradeToJava<jv_to>` recipe. Per-repo search is iterative — run the current chain, on failure feed the proposer the `[ERROR]` block + maven summary and the prior-attempt history, take its mutated chain, retry. A chain identical to one already tried bails. Declarative YAML recipes only. Each step's pom/source edits persist into the next step's working tree. The corpus is processed as a multi-pass round-robin — each pass gives every still-FAILing repo K more attempts continuing its trajectory, then moves on; iterate passes until one yields zero new PASSes. The universal-sequence question (one chain winning across many repos) is answered after per-repo converges, by clustering winning chains.
   - **Contract:** writes per-repo trajectories under `attempt_N/per_repo_iter/<slug>/trajectory.json` (chain attempted, verdict, failure observation, proposer rationale, wall-clock); reads item 2's dataset for the stage list; reads item 4's host paths; consumes items 3, 5, 6 transparently.
   - **Search:** the proposer input must carry real failure signal — per-step log dirs prevent successive same-named phases from overwriting each other; prefer stepped framework upgrades over one-shot leaps; pure JDK upgrades exempt from staging; default slice K=5 — small enough the 90%-convergence point appears in observable time, big enough the proposer can iterate on one root cause before yielding; trajectory state persists between passes so each new attempt picks up prior hypotheses.
   - **Reward:** corpus PASS rate vs the one-shot baseline; tie-breakers — fewer attempts to PASS, less wall-clock to PASS, smaller diff from baseline chain.
   - **Repeat:** continuous round-robin until convergence; restart from cached trajectories whenever the proposer changes materially.
2. **Fitness (dataset rediscovery):** curate `java21-migration-dataset.json` as distinct-owner lineage samples balanced per (oldest-Java-version × dependency family) cell. Each entry is one repo tracked across its Java-version history with a `commit_sha` recorded at every observed version through 21, each commit baseline-buildable in the runner container under its declared JDK. Target corpus size ≥1000 repos, preferring repos with the full J8 → J11 → J17 → J21 lineage (every adjacent step observed) so item 1 can compare leap-vs-stepped on the same project. Iterate candidates through a ralph loop, balancing the matrix.
   - **Contract:** emits `java21-migration-dataset.json`; item 1 reads it for the stage list and excludes any stage whose baseline doesn't build under jv_from.
   - **Search:** distinct-owner sampling; widen under-represented cells; prefer full-lineage repos over partial-lineage when both fit a cell; skip monorepos and giant clones that hang the walker; verify each commit by `mvn compile` inside Docker under the declared JDK.
   - **Reward:** coverage in under-represented cells; corpus size at or above 1000; fraction of entries with full J8→J11→J17→J21 lineage; fraction of entries where every commit is baseline-buildable.
   - **Repeat:** continuous; paused when item 1 is saturated on the current corpus.
3. **Fitness (proxy dependency resolution):** every build's external-artifact resolution goes through a local caching proxy with plural upstream mirrors. The proxy caches every artifact it serves and survives across iterations.
   - **Contract:** consumers (items 1, 2) attribute build failures to code state rather than upstream availability, so an unresolved artifact triggers a proxy widening before that build is counted toward the parent's reward.
   - **Search:** include both live mirrors and archival ones in the upstream set; container builds reach the proxy by container-network DNS, not host IPs; when a build fails on "cannot resolve X", widen the upstream set before treating the failure as code-attributable.
   - **Reward:** per-artifact cache-hit ratio; resolution failures distinguishable from compile failures in the parent loop's classification.
   - **Repeat:** whenever a parent loop's failures cluster on artifact resolution.
4. **Fitness (maintain local environment):** known stable paths and access discipline so iteration outcomes don't drift for reasons unrelated to what's being measured.
   - **Contract:** project workdir at `$HOME/java_8_11_17_to_java_21`; corpus repo-mirror cache at `/var/cache/git-mirrors/<owner>/<repo>.git`; all build toolchains and recipe execution run inside Docker; SSH calls to the work host share one session, not one per command; free host resources held by unrelated work when this project needs them.
   - **Search:** when a pattern repeats and is slow, pin a known location or cache for it; when a pattern risks an external rate-limit, cache the upstream once.
   - **Reward:** zero ban incidents; predictable per-iteration wall-clock; locations re-used across iterations.
   - **Repeat:** whenever a new noisy or slow pattern emerges.
5. **Fitness (vLLM spin-up):** stand up an OpenAI-compatible chat-completion endpoint that the agent can call from inside Docker containers, serving a tool-capable model, with authentication enforced. Arrive there through a ralph loop over container, model, and reverse-proxy config.
   - **Contract:** consumers (item 1's proposer, item 7's compactor) default to thinking mode (`chat_template_kwargs.enable_thinking: true`); fall back to no-thinking only when thinking output is unparseable.
   - **Reward:** consumers report uninterrupted service.
   - **Repeat:** on any consumer reporting degraded service.
6. **Fitness (runner saturation):** keep the verifier host CPU in a healthy utilisation band while any parent loop is making progress — composes with the parent rather than standing alone.
   - **Constraints:** any concurrency dial the agent can reach.
   - **Search:** sample load periodically, decide what to adjust given the recent action history and which parent loop is active.
   - **Reward:** sustained band hit without thrashing or stalling the parent loop.
   - **Repeat:** continuous, dampened against oscillation; pause when no parent loop is active.
7. **Fitness (compact observations):** capture system streams continuously to disk, raw and keyed for retrieval, regardless of whether anyone is reading them; a compacting model processes those streams to produce the orchestrator-visible digest.
   - **Contract:** the compactor is never load-bearing for irreversible decisions without a spot check against the raw source; any fitness execution whose run window overlaps a gap in capture is invalid.
   - **Search:** the snapshot fed to the compactor must surface failure signals when present, not just happy-path state; emit only when state changes materially since the previous snapshot, so a quiet stream stays quiet; on input exceeding the compactor's budget, chunk-and-merge rather than drop; periodically spot-sample raw vs digest to recalibrate trust.
   - **Reward:** balance between compaction rate and anomalies missed; quiet streams stay quiet so emitted entries carry signal.
   - **Repeat:** whenever a new noisy stream enters the loop.
