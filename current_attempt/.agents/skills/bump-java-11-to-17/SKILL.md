---
name: bump-java-11-to-17
description: Emit the rewrite.yml that migrates a Maven or Gradle project from Java 11 to Java 17 — an OpenRewrite declarative composite recipe whose recipeList the harness runs, then scores. Use for an 11→17 Java LTS bump.
---

# Java 11 → 17 — emit a `rewrite.yml`

You output **one executable `rewrite.yml`** — an OpenRewrite declarative composite recipe (`name: com.bjv.Bump`)
whose **`recipeList`** is the ordered recipe sequence the harness runs (one `mvn rewrite:run` / `gradle rewriteRun`),
then scores. You run nothing, edit nothing — and a `rewrite.yml` can only list recipes, so a hand-edit is impossible.

The "intents" are recipes too:
- **set target → 17** → `org.openrewrite.java.migrate.UpgradeJavaVersion` with `version: 17`.
- **bump Gradle wrapper** (only if below the JDK-17 floor 7.3) → `org.openrewrite.gradle.UpdateGradleWrapper` with `version: "7.6"`.

Every recipe FQN you use must be in the catalog and resolvable in the **offline** mirror. **Done** = tests still
pass under 17, effective compiler target == 17, no known CWEs. A wall no recipe covers → emit a **bail** (bottom).

## Default `rewrite.yml`
```yaml
type: specs.openrewrite.org/v1beta/recipe
name: com.bjv.Bump
recipeList:
  - org.openrewrite.gradle.UpdateGradleWrapper:      # ONLY if wrapper < 7.3 (Gradle projects)
      version: "7.6"
  - org.openrewrite.java.migrate.UpgradePluginsForJava17
  - org.openrewrite.java.migrate.UpgradeBuildToJava17
  - org.openrewrite.java.migrate.UpgradeJavaVersion:  # sets source/release/toolchain (+ Kotlin jvmToolchain) to 17
      version: 17
```
Drop `UpdateGradleWrapper` if the wrapper already ≥ 7.3, or for Maven. `UpgradeBuildToJava17` already adds the
test-fork `--add-opens`, the EE deps (if still javax-era), JaCoCo ≥ 0.8.12, surefire ≥ 2.22.2 — don't add ops for those.

## Add to `recipeList` when a wall shows (else bail)
| Symptom | Recipe to add |
|---|---|
| `Unsupported class file major version 61` / ASM / Spring component-scan `SimpleMetadataReader` NPE | `org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3` (or `…boot2.UpgradeSpringBoot_2_7` for SB 2.0–2.4 on the 5.3 ASM floor). On SB ≥ 3.2 it's a *transitive* old ASM no recipe forces → **bail `I_MADE_MANUAL_EDIT`**. |
| Lombok / Mockito / ByteBuddy too old for 17 | covered by `UpgradeBuildToJava17`; if it persists, no unparametrized recipe forces the transitive version → **bail**. |
| `package javax.xml.bind does not exist` while the recipe runs | the harness runs the recipe under jv_from where it still compiles — no action. |

## Bail labels (emit instead of improvising)
- `RECIPE_PATH_UNREACHABLE` — a recipe artifact doesn't resolve in the mirror.
- `CWE_UNFIXABLE_OFFLINE` — a resolved dep has a known CWE and no fixed version is in the mirror.
- `I_MADE_MANUAL_EDIT` — a wall needs a change no catalog recipe provides (forced transitive ByteBuddy/ASM, SB1.x app on SB2-removed APIs, a removed-API source rewrite).
