---
name: bump-java-8-to-11
description: Migrate a Maven or Gradle project one Java LTS step from Java 8 to Java 11 — it must compile under JDK 11, conserve every previously-passing test, and raise the effective compiler target to 11, using only standard tools (JDKs, Maven or Gradle, OpenRewrite recipes from Maven Central; no project-specific scripts). Use for an 8→11 Java LTS bump.
---

# Bump Java 8 → 11

Migrate the project in your working directory from Java 8 to Java 11. GOAL: it COMPILES and passes its TESTS under JDK 11, conserving every test that passed under JDK 8, with the effective compiler target raised to 11 (a project that merely compiles under 11 but still targets 8 is NOT a bump). Work autonomously until done.

## Tools — standard only (JDKs 8 and 11, Maven or Gradle, OpenRewrite from Maven Central)
Three operations recur below; run each with the two JDKs — no project-specific scripts:

**FIRST detect the build tool and use ONLY it for every operation:** `pom.xml` present → Maven; otherwise (`build.gradle`/`build.gradle.kts`) → Gradle. **NEVER introduce the other build system** — do NOT create a `pom.xml` in a Gradle project (or a `build.gradle` in a Maven one). The build/test gate compiles whatever build file is present, so adding the wrong one silently breaks dependency resolution (deps declared in the project's real build tool show up as `package … does not exist`).
- **compile under JDK N** — Maven: `JAVA_HOME=<jdkN> mvn -B -ntp -DskipTests compile`; Gradle: `./gradlew -Dorg.gradle.java.home=<jdkN> compileJava` (also `compileKotlin`/`compileTestJava`).
- **test under JDK N** — Maven: `JAVA_HOME=<jdkN> mvn -B -ntp test`; Gradle: `./gradlew -Dorg.gradle.java.home=<jdkN> test`.
- **apply the OpenRewrite program** — write `rewrite.yml` (below), then run it **under JDK 8 with the Java-11 recipe artifacts**:
  - Maven: `JAVA_HOME=<jdk8> mvn -B -ntp -U -Denforcer.skip=true org.openrewrite.maven:rewrite-maven-plugin:6.40.0:run -Drewrite.configLocation=$(pwd)/rewrite.yml -Drewrite.activeRecipes=com.bjv.Bump -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.35.0,org.openrewrite.recipe:rewrite-spring:6.31.0,org.openrewrite.recipe:rewrite-java-dependencies:1.55.0` — the **absolute** `configLocation` (`$(pwd)/rewrite.yml`) is required, else multi-module submodules report `Recipe(s) not found`.
  - Gradle: apply the OpenRewrite plugin through an init-script with `rewrite-migrate-java:3.35.0` / `rewrite-spring:6.31.0` / `rewrite-java-dependencies:1.55.0` on the `rewrite` configuration, then run `rewriteRun`.

CRITICAL — NEVER time-box these builds. Cold Gradle/Maven runs download distributions + the OpenRewrite jars and take MINUTES; let them finish. An apply that was cut off means the recipe was NOT applied (tests may still pass at the OLD Java level, but the bytecode-target check FAILS) — after applying, confirm BUILD SUCCESS and that the build files actually changed.

## How to work (graded on a CORRECT migration that conserves tests — nothing else counts if a test is lost or the bytecode isn't really at 11)
- Prefer the off-the-shelf transforms: the unparametrized meta-recipe + setting the Java version to 11 + (only if needed) the pinned Gradle wrapper are the clean path — use them first.
- Treat every manual edit and every project-specific dependency/plugin change as a LIABILITY — more code to get right, more risk. Make the FEWEST changes that genuinely work; reach for a hand edit or a project-specific recipe only when a real wall demands it.
- Never touch or weaken test code (see FORBIDDEN).

## START HERE — write `rewrite.yml`, then apply it
```
type: specs.openrewrite.org/v1beta/recipe
name: com.bjv.Bump
recipeList:
  - org.openrewrite.java.migrate.Java8toJava11
  - org.openrewrite.java.migrate.UpgradeJavaVersion:
      version: 11
```
Then compile under JDK 11. If it compiles, test under JDK 11. If tests pass and none are lost, you are done.

## Reflect loop — if compile or test under 11 fails, read the error, fix the FIRST wall, re-run (no iteration limit)
Keep going until it passes or you have exhausted real options.
Wall → fix:
- `package javax.xml.bind`/`javax.annotation.Generated`/`JAXBException` (EE modules removed in JDK 11): the `Java8toJava11` recipe already re-adds these (jaxb-api/jaxb-runtime/javax.activation/javax.annotation-api 2.3.1) and floors surefire to 2.22.2 — trust it. ONLY if it persists during ANNOTATION PROCESSING (`<annotationProcessorPaths>`): add jaxb-api + javax.annotation-api as `<path>` entries there too. Remove any leftover `--add-modules java.xml.bind`/`java.se.ee` flag.
- Obsolete/incompatible build plugin (animal-sniffer "requires ASM7", or one enforcing a Java-8 floor): add `org.openrewrite.maven.RemovePlugin` {groupId, artifactId} to rewrite.yml, apply again.
- Dependency too old for JDK 11 (lombok < 1.18.20, byte-buddy < 1.10, mockito < 3): add `org.openrewrite.java.dependencies.UpgradeDependencyVersion` {groupId, artifactId, newVersion}.
- Gradle wrapper: Gradle 5.0+ ALREADY runs on JDK 11 — do NOT bump just for the Java version. Only bump if the apply fails to LOAD on the current wrapper (needs ~Gradle 6.0+). When you must, target **6.9** (NOT 7.x) via the `org.openrewrite.gradle.UpdateGradleWrapper` {version: "6.9"} recipe, or set gradle-wrapper.properties to gradle-6.9 by hand. NEVER jump to Gradle 7.x — it REMOVED `compile`/`testCompile` (breaks old build files: `Could not find method compile()`). NEVER point distributionUrl at a `file://` path. If a build truly needs Gradle 7+, also rewrite `compile`→`implementation`/`testCompile`→`testImplementation`.
- Spring Boot 1.x can't run on 11: add `org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7`.
- RUNTIME `ArrayIndexOutOfBoundsException: Index 1 out of bounds for length 1` from a `<clinit>` (Jadira etc. parsing `java.version` the old `1.x` way): bump the lib (Jadira → `7.0.0.CR1`); no JDK-11 release → bail.
- `package <internal> is not visible` (project uses java.awt.peer / sun.security.* / sun.misc.*): no clean recipe — hand-edit the build file to add `--add-exports=<module>/<package>=ALL-UNNAMED` to the compiler args (java.awt.peer→java.desktop, sun.security.*/sun.misc.*→java.base).
- Multi-module: a JDK bump is per-BUILD, not per-module. `Dependency resolution is looking for a library compatible with JVM runtime version N, but 'project :X' is only compatible with M` = set the SAME target in every module (root `allprojects`/`subprojects`).
- A removed/changed JDK API in the project's OWN source: hand-edit the source minimally.

## General discipline (these stop you chasing non-problems)
- **EDIT HYGIENE:** after EVERY build-file edit, BEFORE rebuilding, validate it — `./gradlew help -q` (Maven `mvn -q validate`). If that fails naming the file you just edited, YOUR edit broke the script: fix/revert it, do not chase it as a migration error. Make minimal, validated edits.
- **NOT YOUR TESTS:** tests needing Docker/Testcontainers/a database/Selenium/the network were already failing in the baseline — NOT in your conserve-set. Only tests that PASSED under 8 must still pass.
- OOM during tests is usually DOWNSTREAM of an earlier real error — fix the FIRST error first.
- Stale generated classes (`ClassAlreadyExistsException`, jsonschema2pojo): `./gradlew clean` / `rm -rf target`, re-run.

## Absolutely forbidden (cheating — fails the run)
Do NOT delete/skip/disable/weaken any test or assertion; no `-DskipTests`/`<skip>true`; do NOT delete test files; do NOT touch test code to make it pass. Conservation of the originally-passing tests is checked independently.

When the project passes its tests under JDK 11 with no tests lost and the effective target is 11, say you are done and summarize what you changed.
