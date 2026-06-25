---
name: bump-java-17-to-21
description: Migrate a Maven or Gradle project one Java LTS step from Java 17 to Java 21 — it must compile under JDK 21, conserve every previously-passing test, and raise the effective compiler target to 21, using only standard tools (JDKs, Maven or Gradle, OpenRewrite recipes from Maven Central; no project-specific scripts). Use for a 17→21 Java LTS bump.
---

# Bump Java 17 → 21

Migrate the project in your working directory from Java 17 to Java 21. GOAL: it COMPILES and passes its TESTS under JDK 21, conserving every test that passed under JDK 17, with the effective compiler target raised to 21 (a project that merely compiles under 21 but still targets 17 is NOT a bump). Work autonomously until done.

## Tools — standard only (JDKs 17 and 21, Maven or Gradle, OpenRewrite from Maven Central)
Three operations recur below; run each with the two JDKs — no project-specific scripts:

**FIRST detect the build tool and use ONLY it for every operation:** `pom.xml` present → Maven; otherwise (`build.gradle`/`build.gradle.kts`) → Gradle. **NEVER introduce the other build system** — do NOT create a `pom.xml` in a Gradle project (or a `build.gradle` in a Maven one). The build/test gate compiles whatever build file is present, so adding the wrong one silently breaks dependency resolution (deps declared in the project's real build tool show up as `package … does not exist`).
- **compile under JDK N** — Maven: `JAVA_HOME=<jdkN> mvn -B -ntp -DskipTests compile`; Gradle: `./gradlew -Dorg.gradle.java.home=<jdkN> compileJava` (also `compileKotlin`/`compileTestJava`).
- **test under JDK N** — Maven: `JAVA_HOME=<jdkN> mvn -B -ntp test`; Gradle: `./gradlew -Dorg.gradle.java.home=<jdkN> test`.
- **apply the OpenRewrite program** — write `rewrite.yml` (below), then run it **under JDK 17 with the Java-21 recipe artifacts**:
  - Maven: `JAVA_HOME=<jdk17> mvn -B -ntp -U -Denforcer.skip=true org.openrewrite.maven:rewrite-maven-plugin:6.40.0:run -Drewrite.configLocation=$(pwd)/rewrite.yml -Drewrite.activeRecipes=com.bjv.Bump -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.35.0,org.openrewrite.recipe:rewrite-spring:6.31.0,org.openrewrite.recipe:rewrite-java-dependencies:1.55.0` — the **absolute** `configLocation` (`$(pwd)/rewrite.yml`) is required, else multi-module submodules report `Recipe(s) not found`.
  - Gradle: apply the OpenRewrite plugin through an init-script with `rewrite-migrate-java:3.35.0` / `rewrite-spring:6.31.0` / `rewrite-java-dependencies:1.55.0` on the `rewrite` configuration, then run `rewriteRun`.

CRITICAL — NEVER time-box these builds. Cold Gradle/Maven runs download distributions + the OpenRewrite jars and can take several MINUTES; let them finish. An apply that was cut off means the recipe was NOT applied — after applying, confirm BUILD SUCCESS and that the build files actually changed.

## How to work (graded on a CORRECT migration that conserves tests — nothing else counts if a test is lost or the bytecode isn't really at 21)
- Prefer the off-the-shelf transforms: the unparametrized meta-recipes + setting the Java version to 21 + (only if needed) the pinned Gradle wrapper are the clean path — use them first.
- Treat every manual edit and every project-specific dependency/plugin change as a LIABILITY. Make the FEWEST changes that genuinely work.
- Never touch or weaken test code (see FORBIDDEN).

## Proactive step — Gradle Kotlin/Java toolchain target (verify the bump actually landed; gated on a structural signal, not an error)
On **Gradle** projects the `UpgradeJavaVersion` recipe frequently does NOT touch a Kotlin-DSL toolchain block — `java { toolchain { languageVersion.set(JavaLanguageVersion.of(N)) } }` (or the Groovy `JavaLanguageVersion.of(N)`). The build then **compiles cleanly but to the OLD bytecode** (effective target stays 17), so there is NO error to react to — it silently scores `FAIL_target_not_bumped`. So after applying the recipe, **grep the build files for `JavaLanguageVersion.of(`**: if any still names a version **< 21**, hand-edit it to `JavaLanguageVersion.of(21)` *before* the JDK-21 build. This is proactive precisely because the failure is silent — the structural trigger (a `JavaLanguageVersion.of(<21)` left in a build file) is unambiguous. For a **Kotlin** project this Java toolchain is enough: the Kotlin plugin derives `jvmTarget` from it, so bytecode goes to 21 with no separate `kotlinOptions.jvmTarget`/`jvmToolchain` change (add those only if you later hit the `Inconsistent JVM-target compatibility` wall below). Note the Gradle wrapper version is a *separate* axis — Gradle 7.5.1 still provisions a JDK-21 toolchain to compile, so a `<8.5` wrapper does NOT by itself block this hop (see the wrapper Troubleshooting row for when it genuinely does). Counts as a **free hop-fixed intent**, like setting the target.

## START HERE — write `rewrite.yml`, then apply it
```
type: specs.openrewrite.org/v1beta/recipe
name: com.bjv.Bump
recipeList:
  - org.openrewrite.java.migrate.UpgradePluginsForJava21
  - org.openrewrite.java.migrate.UpgradeBuildToJava21
  - org.openrewrite.java.migrate.UpgradeJavaVersion:
      version: 21
```
Then compile under JDK 21. If it compiles, test under JDK 21. If tests pass and none are lost, you are done.

## Reflect loop — if compile or test under 21 fails, read the error, fix the FIRST wall, re-run (no iteration limit)
JDK-21 class-file version is **65** — a tool that reads bytecode via ASM must be new enough for v65.
- **Test fork strong-encapsulation** (`InaccessibleObjectException` / `module {A} does not "opens {pkg}"`): hand-edit the test fork args (Maven surefire `<argLine>`, Gradle `tasks.test { jvmArgs(...) }`) adding `--add-opens=<module>/<pkg>=ALL-UNNAMED` per package the error names (one token each, joined with `=`; preserve existing argLine like JaCoCo's `@{argLine}`). Whole block = ONE edit.
- **ByteBuddy/Mockito on v65:** `Cannot define class using reflection` / `Mockito cannot mock this class` / `Unsupported class file major version 65`. Mockito needs **≥ 5.18** for JDK 21; and force `net.bytebuddy:byte-buddy(:agent)` ≥ **1.14.12** (a plain bump is overridden by the Spring BOM ~1.14 — force it: Maven `<byte-buddy.version>` property, Gradle `configurations.all { resolutionStrategy.eachDependency { if (requested.group=="net.bytebuddy") useVersion("1.14.12") } }`). UpgradeDependencyVersion.
- **JaCoCo on v65:** `Unsupported class file major version 65` → floor jacoco to **0.8.12**.
- **Spring component-scan** `Unsupported class file major version 65` / `SimpleMetadataReader` `BeanDefinitionStoreException`: the SB2 BOM is too old for v65. Prefer `org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3` (also does javax→jakarta + Spring Security 6). If you must stay on the 2.7 line, the floor is **SB 2.7.17+** (earlier 2.7.x ships an ASM that can't read v65) — but 2.7 is EOL, prefer 3.x. For Gradle, even a patch bump can fix it (SB 3.0.0's ASM 9.4 can't parse v65; **3.0.7+** ships ASM 9.5; 3.2.x fully supports 21). If already on SB ≥ 3.2 and STILL hitting v65 ASM, it's a *transitive* old shaded ASM — find and force that dep, don't keep bumping Spring Boot.
- **`cannot find symbol: WebSecurityConfigurerAdapter`** (removed in Spring Security 6): do the SB 2→3 upgrade (`UpgradeSpringBoot_3_3`), which migrates it.
- **Gradle wrapper below the JDK-21 floor (8.5):** bump via `org.openrewrite.gradle.UpdateGradleWrapper` {version: "8.10.2"} (the pinned value), or by hand. Signatures: `Unsupported class file major version N` while Gradle CONFIGURES, or `Could not determine java version from '21.0.x'`. NEVER point distributionUrl at a `file://` path.
- **After a wrapper bump to 9.x:** `Failed to apply plugin` naming a Gradle-internal type (`PatternSets$PatternSetFactory`, `No such property: internal for BuildParams`) → bump the failing *plugin* to its Gradle-9 line, not Gradle.
- **Gradle + Kotlin:** `Inconsistent JVM-target compatibility` → `kotlin { jvmToolchain(21) }`.
- **`sun.misc.Unsafe … terminally deprecated`** WARNING from a dep (jctools/Netty): while only a warning and tests pass, it's cosmetic — conserve.
- **Multi-module:** a JDK bump is per-BUILD, not per-module. `Dependency resolution is looking for a library compatible with JVM runtime version N, but 'project :X' is only compatible with M` = some modules' target wasn't set — set the SAME target in every module (root `allprojects`/`subprojects`).
- **`Cannot find a Java installation … matching {languageVersion=N}`** (foojay resolver timeout, no network): point Gradle at the installed JDKs `-Porg.gradle.java.installations.paths=<jdk17>,<jdk21>` and DROP `vendor`/`implementation` pins from `toolchain{}` — `languageVersion` alone is enough.
- **`Entry <path> is a duplicate but no duplicate handling strategy has been set`** (Gradle 7+ hard error): `tasks.withType(Copy).configureEach { duplicatesStrategy = DuplicatesStrategy.EXCLUDE }`.
- **A removed/changed JDK API in the project's OWN source:** hand-edit minimally.

## General discipline (these stop you chasing non-problems)
- **VERIFY THE TARGET LANDED:** a clean JDK-21 build is NOT proof of a real bump — Gradle Kotlin-DSL `JavaLanguageVersion.of(N)` toolchains (and soft-pinned Maven `source`/`target`/`release`) can leave bytecode at 17 with zero errors. After the build, confirm no build file still has `JavaLanguageVersion.of(<21)` (see the proactive step). If nothing forced an edit, the recipe under-applied — fix the version declaration by hand.
- **EDIT HYGIENE:** after EVERY build-file edit, BEFORE rebuilding, validate it — `./gradlew help -q` (Maven `mvn -q validate`). If that fails naming the file you just edited, YOUR edit broke the script: fix/revert it, do not chase it as a migration error. Make minimal, validated edits.
- **NOT YOUR TESTS:** tests needing Docker/Testcontainers/a database/Selenium/the network were already failing in the baseline — NOT in your conserve-set. Only tests that PASSED under 17 must still pass.
- OOM during tests is usually DOWNSTREAM of an earlier real error — fix the FIRST error; only raise `-Xmx` if it's genuinely heap.
- Stale generated classes (`ClassAlreadyExistsException`): `./gradlew clean` / `rm -rf target`, re-run.
- `--add-opens` for deep reflection, `--add-exports` only for compile/link to a non-exported API; do NOT use `--illegal-access=permit` (removed in JDK 17). Canonical opens set: `--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.text=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.time=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.desktop/java.awt.font=ALL-UNNAMED --add-opens=java.management/java.lang.management=ALL-UNNAMED`.

## When to bail (report honestly)
- **EasyMock** has no clean JDK-21+ mocking path (`ClassProxyFactory` define fails) — bail.
- A **semantic JDK change** in the project's own code (confirm with a pristine-checkout probe).
- An abandoned dependency with no JDK-21 release.
- Native (CMake/JNI) modules.

## Absolutely forbidden (cheating — fails the run)
Do NOT delete/skip/disable/weaken any test or assertion; no `-DskipTests`/`<skip>true`; do NOT delete test files; do NOT touch test code to make it pass. Conservation is checked independently.

When the project passes its tests under JDK 21 with no tests lost and the effective target is 21, say you are done and summarize what you changed.
