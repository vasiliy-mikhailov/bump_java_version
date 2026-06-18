---
name: bump-java-21-to-25
description: Emit the conversion program to migrate a Maven or Gradle project from Java 21 to Java 25 — an ordered list of unparametrized OpenRewrite recipes + predefined intents that the harness applies and scores. Use for a 21→25 Java LTS bump.
---

# Java 21 → 25 — emit a recipe+intent program

You output an **ordered conversion program** (a list of ops); the harness applies and scores it. You run nothing,
edit nothing. Two op types only:
- **`recipe`** — `{env: from|to, fqn}`, one *unparametrized* OpenRewrite recipe FQN from the catalog below.
- **`intent`** — `set_target` (set source/`release`/toolchain → **25**) | `bump_wrapper` (Gradle wrapper → **9.0.0**).

Nothing else is expressible — no hand-edit, no `skipTests`, no test deletion. A wall no recipe/intent covers →
emit a **bail** (bottom). Offline Maven mirror + frozen CWE snapshot; every FQN/version you name must exist in it.
**Done** = previously-passing tests still pass under 25, effective compiler target == 25, no known CWEs.
(The 25 recipes need `rewrite-migrate-java:3.36.0` + `rewrite-maven-plugin:6.41.0` — the harness uses these for jv_to=25.)

## Default program
- **Maven:** `recipe to org.openrewrite.java.migrate.UpgradePluginsForJava25`, then
  `recipe to org.openrewrite.java.migrate.UpgradeBuildToJava25` (sets `release=25` + the fixes below).
- **Gradle:** **`intent bump_wrapper` first** — Gradle 8.x can't even *run* a JDK-25 toolchain (it fails parsing
  the version string), so the **9.0.0** floor is mandatory; then `intent set_target` (→25, Kotlin `jvmToolchain(25)`).

## What `UpgradeBuildToJava25` restores (recognition — the recipe applies it; don't add separate ops)
- Test-fork `--add-opens …=ALL-UNNAMED`; **JaCoCo** ≥ **0.8.13** (v69/ASM wall); **Lombok** ≥ **1.18.40**;
  **Mockito** ≥ 5.18 + **ByteBuddy** ≥ **1.17.6** (v69-capable); Kotlin **≥ 2.2** (older Kotlin caps below JVM 25).

## Walls → the op to add (else bail)
| Symptom | Op to emit |
|---|---|
| `Unsupported class file major version 69` / `ASM ClassReader failed` (ByteBuddy/JaCoCo/Groovy) | the §-recipe floors the common ones; a forced *transitive* ASM/ByteBuddy bump is not an unparametrized recipe → **bail `I_MADE_MANUAL_EDIT`**. |
| Gradle 9 `Failed to apply plugin` naming a removed internal type (`PatternSets$PatternSetFactory`, …) | a build *plugin* predates Gradle 9 → `recipe to org.openrewrite.gradle.plugins.UpgradePluginVersion` (the one parametrized exception — `pluginIdPattern`+`newVersion`); repeat per failing plugin. If none compatible in the mirror → **bail**. |
| `sun.misc.Unsafe` **removed** (not just warned) breaks a dep (jctools/Netty) | a newer dep often doesn't fix it; no unparametrized recipe covers the Unsafe-free path → **bail**. |
| **EasyMock** on JDK 25 (no JDK-25 path) | **bail `I_MADE_MANUAL_EDIT`**. |
| Quarkus: Kotlin pinned by the platform BOM | bump the Quarkus platform via the §-recipe; a raw Kotlin bump is overridden — if the recipe can't, **bail**. |

## Bail labels (emit instead of improvising)
- `RECIPE_PATH_UNREACHABLE` — a named recipe artifact doesn't resolve in the mirror.
- `CWE_UNFIXABLE_OFFLINE` — a resolved dep has a known CWE and no fixed version is in the mirror.
- `I_MADE_MANUAL_EDIT` — a wall needs a change no catalog recipe / intent provides (forced transitive ASM/ByteBuddy, EasyMock, Unsafe-removal, a removed-API source rewrite).
