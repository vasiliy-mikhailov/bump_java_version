# Attempt 10 — Java LTS Bump Artifact

A portable, harness-agnostic artifact that migrates a Maven project from one Java LTS to
the next (8→11, 11→17, 17→21) so it still compiles and its tests still pass. The artifact is
`(prompt.md, recipe catalog, bump scripts)`; the production executor is **OpenHands + Qwen
3.6 27B (FP8)**. The research goal is to beat the one-shot OpenRewrite baseline while staying
model-portable.

---

## Results (attempt 10, corpus = 477 datapoints, all J17→J21)

| Metric | Rate | Notes |
|---|---|---|
| Raw OH+Qwen success | **358 / 477 = 75.1%** | reaches pom ≥ jv_to AND conserves the baseline test set |
| **Clean corpus** (junk baselines removed) | **358 / 431 = 83.1%** | ~46 datapoints were unmigratable baselines D4 should never have collected |
| **With hardened artifact + recovery** | **≈ 416 / 431 = 96.5%** | re-running the fixable cohort + recovered baselines through the same OH+Qwen executor |

**The headline finding: most of the "25% failure" was never migration failure.**
It decomposed into three buckets:

1. **~46 bad baselines (corpus bug, now excluded).** The corpus had frozen `sha_from`
   commits that (a) don't compile under jv_from at all, (b) were mislabeled — 5+ were at
   Java 19–24, not 17 — or (c) sat off the main history. None carry migration signal; a
   never-compiling baseline only enters the pipeline as a false `baseline-broken`.
2. **~50 fixable with a better artifact.** Agent-gap (the weak agent wandered instead of
   running the bump), verdict false-positives (plugin-config knobs the verdict couldn't
   see), and the Spring-Boot-2 / Byte-Buddy cohort. Re-running these through the hardened
   prompt + recipe rows passed ~92–95%.
3. **15 recoverable baselines.** For repos whose frozen commit was broken, walking back to
   the nearest *compiling* jv_from ancestor produced a valid baseline; 11 of the 15 then
   migrate to pom = 21 with tests passing. (The other 4 compile but don't migrate — now
   genuine migration signal, not corpus noise.)

What remains as true migration failure is a small tail (~15 of 431).

---

## How to bump a Java version

### Environment

- All JDKs and Maven are reached **only** through the `mvn` command on PATH. It dispatches to
  a Docker container (`j21-fitness`) carrying **JDK 8/11/17/21 + Maven 3.9**, bind-mounting a
  caching Nexus proxy and a per-project `~/.m2-fitness` cache. Do not install `java`/`javac`
  directly; do not run `mvn` outside the wrapper.
- **Switch JDK per command** with the `JDK=<n>` env var, e.g. `JDK=21 mvn test`.
- Bump scripts are on PATH as `bump_<from>_to_<to>.sh <workdir>`:
  `bump_8_to_11.sh`, `bump_11_to_17.sh`, `bump_17_to_21.sh`, plus `sb2_to_sb3.sh`
  (Spring Boot 2 → 3.3) for the SB2 BOM cohort.
- The custom recipe artifact `com.claude.recipes:claude-recipes:1.0.0` lives **only** in the
  local `~/.m2-fitness` cache (Nexus 404s it). Don't clear the cache.

### Basic flow

1. `git init && git add -A && git commit -m baseline`. If there's no root `pom.xml`, the
   project is nested — `find . -name pom.xml -not -path "*/.git/*"`, `cd` into the shallowest
   match, run all later steps there.
2. `JDK=<jv_from> mvn test` → record **`BASELINE_PASS`** = the tests that pass pre-bump
   (parse `**/target/surefire-reports/TEST-*.xml`, not stdout). Tests already erroring in
   baseline (no Docker, missing service) are *not* your responsibility.
3. `bump_<jv_from>_to_<jv_to>.sh .` → runs the OpenRewrite recipe cascade
   (lombok-safe bump → plugins → build → transforms). rc=0 expected.
4. `JDK=<jv_to> mvn compile` → rc=0 expected.
5. Clear `target/` (root-owned: `docker run --rm --entrypoint bash -v $WORK:/work j21-fitness:latest -c "rm -rf /work/target"`),
   then `JDK=<jv_to> mvn test`. **If every test in `BASELINE_PASS` still passes →
   `git commit -am bump` and you're done.**
6. If a step fails, read the `[ERROR]`, look it up in the failure table, apply the fix
   verbatim, commit, re-run from the failed step. If nothing matches, bail with a label.

### Success criterion (reward)

`JDK=<jv_to> mvn compile` succeeds **and** the post-bump passing test set ⊇ `BASELINE_PASS`.
The diff against the baseline commit is the deliverable.

### Failure remedies (recipe catalog + pom fixes)

`mvn rewrite:run` template (substitute the recipe FQN):

```
JDK=<jv_to> mvn -B -ntp org.openrewrite.maven:rewrite-maven-plugin:6.40.0:run \
  -Drewrite.activeRecipes=<RECIPE_FQN> \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.35.0,com.claude.recipes:claude-recipes:1.0.0
```

| Symptom (`[ERROR]`) | Fix |
|---|---|
| `WebSecurityConfigurerAdapter` not found | recipe `com.claude.recipes.RewriteWebSecurityConfigurerAdapterToFilterChain` |
| `HttpStatusCode cannot be converted to HttpStatus` | recipe `com.claude.recipes.WidenHttpStatusToHttpStatusCode` |
| `@WebMvcTest` slice 401/403 with own `SecurityConfig` | recipe `com.claude.recipes.AddSecurityConfigImportForWebMvcTest` |
| OAuth2 login test 302/401 vs configured entry point | recipe `com.claude.recipes.ScopeAuthenticationEntryPointToApiForOAuth2Login` |
| `Java 21 (65) is not supported by the current version of Byte Buddy` | pom: pin `net.bytebuddy:byte-buddy` + `byte-buddy-agent` to `1.14.12` in `<dependencyManagement>` (and as plugin deps if from `hibernate-enhance-maven-plugin`); re-run the bump |
| `ASM ClassReader failed` / `Unsupported class file major version 65` | `git reset --hard`; `sb2_to_sb3.sh .` (Spring Boot 2→3.3); commit; re-run the bump. Else bail `SB2_BOM_NEEDS_SB3_BUMP` |
| `liquibase-hibernate5` not found | pom: rename to `liquibase-hibernate6`, set `liquibase.version=4.27.0` |
| `htmlunit:jar:2.6` unresolved | pom: set `net.sourceforge.htmlunit:htmlunit` to `2.70.0` |
| `springdoc-openapi-ui` not found | pom: rename to `springdoc-openapi-starter-webmvc-ui`, version `2.3.0` |
| `invalid source release: 21 with --enable-preview` | pom: bump hardcoded `<source>/<target>/<release>` in `maven-compiler-plugin` to jv_to; re-run bump. If preview features can't be preserved → bail `PREVIEW_FEATURES_UNPRESERVABLE` |
| `ClassAlreadyExistsException` (jsonschema2pojo) | clear stale `target/` (docker rm), re-run the step |
| `Could not find a valid Docker environment` / Selenium | ignore — pre-existing baseline failure, not a regression |

The full, authoritative version of this flow + table is `prompt.md` in this directory (it is
the artifact the executor actually receives).

---

## Methodology (how the artifact was hardened)

Fixes were searched down a **strong → weak rung ladder**: Claude+Opus (does the fix work at
all / is a new recipe needed?) → Claude+Qwen (is it clear to a weak LLM?) → Claude+OpenHands
+Qwen (does it survive the production agent's tool conventions?). A fix that passes only at a
strong rung is re-validated at the rung below before it's folded into the artifact. Every
per-repo dialogue is preserved under `per_repo_iter/<slug>/`.

The corpus is curated by the dataset Dominanta (D4): each `sha_from` must **compile under
jv_from**; a repo with no compiling jv_from commit is excluded (this attempt added that rule
after finding the ~46 junk baselines).

---

## Next: attempt 11

Attempt 10 hardened the artifact **by hand** (each failure → author a recipe/row → validate →
fold in) and, crucially, produced the substrate the next step needs: a **de-noised corpus**
(a fitness signal that doesn't lie) and a **preserved-dialogue store** (traces to reflect on).
Attempt 11 takes the human out of that loop — automating artifact optimization with reflective
evolution (GEPA on `prompt.md`) and skill/recipe evolution from failed trajectories
(EvoSkills on the recipe catalog), evaluated against the clean 431-repo corpus.
