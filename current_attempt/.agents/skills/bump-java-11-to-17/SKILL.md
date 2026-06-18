---
name: bump-java-11-to-17
description: Emit the conversion program to migrate a Maven or Gradle project from Java 11 to Java 17 — an ordered list of unparametrized OpenRewrite recipes + predefined intents that the harness applies and scores. Use for an 11→17 Java LTS bump.
---

# Java 11 → 17 — emit a recipe+intent program

You output an **ordered conversion program** (a list of ops); the harness applies and scores it. You run nothing,
edit nothing. Two op types only:
- **`recipe`** — `{env: from|to, fqn}`, one *unparametrized* OpenRewrite recipe FQN from the catalog below.
- **`intent`** — `set_target` (set source/`release`/toolchain → **17**) | `bump_wrapper` (Gradle wrapper → **7.6**).

Nothing else is expressible — no hand-edit, no `skipTests`, no test deletion. A wall no recipe/intent covers →
emit a **bail** (bottom). Offline Maven mirror + frozen CWE snapshot; every FQN/version you name must exist in it.
**Done** = previously-passing tests still pass under 17, effective compiler target == 17, no known CWEs.

## Default program
- **Maven:** `recipe to org.openrewrite.java.migrate.UpgradePluginsForJava17`, then
  `recipe to org.openrewrite.java.migrate.UpgradeBuildToJava17` (this sets `maven.compiler.release=17` + the §-below fixes).
- **Gradle:** `intent set_target` (→17, incl. Kotlin `jvmToolchain(17)`); add `intent bump_wrapper` only if the
  wrapper predates **7.3** (JDK-17 floor). Then the recipes above via the rewrite-gradle init-script if it still won't build.

## What `UpgradeBuildToJava17` restores (recognition — the recipe applies it; don't add separate ops)
- **Test-fork strong-encapsulation**: `--add-opens java.base/java.lang|java.util|java.lang.reflect|…=ALL-UNNAMED`
  (and `--add-exports` only for compile-time access to a non-exported API). The exception names the exact module/package.
- EE modules removed earlier (only if the project is still javax-era): jaxb-api/runtime, activation, annotation-api.
- **JaCoCo** floored to **0.8.12**; surefire ≥ **2.22.2**.

## Walls → the op to add (else bail)
| Symptom | Op to emit |
|---|---|
| `Unsupported class file major version 61` / `ASM ClassReader failed` / Spring component-scan `SimpleMetadataReader` NPE | **Spring Boot** bump (below). If on SB ≥ 3.2 it's a *transitive* old ASM → no recipe covers a forced transitive bump → **bail `I_MADE_MANUAL_EDIT`**. |
| `Cannot define class using reflection` / `Mockito cannot mock` (old ByteBuddy) | covered by `UpgradeBuildToJava17`; if it persists, no unparametrized recipe forces ByteBuddy → **bail**. |
| Lombok `NoSuchFieldError: JCTree$JCImport.qualid` (too-old Lombok on JDK 17) | `UpgradeBuildToJava17` floors Lombok to 1.18.30+; if not → **bail**. |
| Gradle: `Inconsistent JVM-target … compileJava (17) / compileKotlin (M)` | `intent set_target` already sets `kotlin { jvmToolchain(17) }`. |
| `package javax.xml.bind does not exist` during the recipe run | emit the recipe with `env: from` (project still compiles under 11), then continue. |

## Spring Boot (only when a wall above points here)
- **SB 2.0–2.4 → 2.7** (Spring < 5.3 component-scans with an ASM that can't read v61): `recipe to org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7`. Don't hand-pick an intermediate version.
- **SB 2.x → 3.3** (need Spring 6 / Security 6 / jakarta on 17): `recipe to org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3` (does javax→jakarta + Security 6). SB 1.x must first go to 2.7.

## Bail labels (emit instead of improvising)
- `RECIPE_PATH_UNREACHABLE` — a named recipe artifact doesn't resolve in the mirror.
- `CWE_UNFIXABLE_OFFLINE` — a resolved dep has a known CWE and no fixed version is in the mirror.
- `I_MADE_MANUAL_EDIT` — a wall needs a change no catalog recipe / intent provides (e.g. forced transitive ByteBuddy/ASM, SB1.x app on SB2-removed APIs, a removed-API source rewrite).
