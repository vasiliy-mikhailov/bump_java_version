---
name: bump-java-17-to-21
description: Emit the conversion program to migrate a Maven or Gradle project from Java 17 to Java 21 — an ordered list of unparametrized OpenRewrite recipes + predefined intents that the harness applies and scores. Use for a 17→21 Java LTS bump.
---

# Java 17 → 21 — emit a recipe+intent program

You output an **ordered conversion program** (a list of ops); the harness applies and scores it. You run nothing,
edit nothing. Two op types only:
- **`recipe`** — `{env: from|to, fqn}`, one *unparametrized* OpenRewrite recipe FQN from the catalog below.
- **`intent`** — `set_target` (set source/`release`/toolchain → **21**) | `bump_wrapper` (Gradle wrapper → **8.10.2**).

Nothing else is expressible — no hand-edit, no `skipTests`, no test deletion. A wall no recipe/intent covers →
emit a **bail** (bottom). Offline Maven mirror + frozen CWE snapshot; every FQN/version you name must exist in it.
**Done** = previously-passing tests still pass under 21, effective compiler target == 21, no known CWEs.

## Default program
- **Maven:** `recipe to org.openrewrite.java.migrate.UpgradePluginsForJava21`, then
  `recipe to org.openrewrite.java.migrate.UpgradeBuildToJava21` (sets `release=21` + the fixes below).
- **Gradle:** `intent set_target` (→21, incl. Kotlin `jvmToolchain(21)`); add `intent bump_wrapper` only if the
  wrapper predates **8.5** (JDK-21 floor).

## What `UpgradeBuildToJava21` restores (recognition — the recipe applies it; don't add separate ops)
- Test-fork `--add-opens …=ALL-UNNAMED` (the exception names the exact module/package).
- **JaCoCo** ≥ **0.8.12**; **Mockito** ≥ **5.18** (v65-capable ByteBuddy); Kotlin JVM target 21.

## Walls → the op to add (else bail)
| Symptom | Op to emit |
|---|---|
| `Unsupported class file major version 65` / `ASM ClassReader failed` (component-scan / ByteBuddy / Groovy / Spock) | the §-recipe usually floors it; a *forced transitive* ByteBuddy/ASM/Groovy bump is not an unparametrized recipe → **bail `I_MADE_MANUAL_EDIT`**. |
| Spring needs 3.x for 21 (SB 3.0.0's ASM 9.4 can't read v65; need ≥ 3.0.7 / 3.2) | `recipe to org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3`. |
| `WARNING … sun.misc.Unsafe …` from a dep on JDK 24+ | cosmetic on 21 — conserve; do not add an op. |
| Gradle `Inconsistent JVM-target … compileKotlin` | `intent set_target` sets `kotlin { jvmToolchain(21) }`. |

## Bail labels (emit instead of improvising)
- `RECIPE_PATH_UNREACHABLE` — a named recipe artifact doesn't resolve in the mirror.
- `CWE_UNFIXABLE_OFFLINE` — a resolved dep has a known CWE and no fixed version is in the mirror.
- `I_MADE_MANUAL_EDIT` — a wall needs a change no catalog recipe / intent provides (forced transitive ASM/ByteBuddy/Groovy bump, a removed-API source rewrite).
