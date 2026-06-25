---
name: bump-java-21-to-25
description: Migrate a Maven or Gradle project one Java LTS step from Java 21 to Java 25 — it must compile under JDK 25, conserve every previously-passing test, and raise the effective compiler target to 25, using only standard tools (JDKs, Maven or Gradle, OpenRewrite recipes from Maven Central; no project-specific scripts). Use for a 21→25 Java LTS bump.
---

# Bump Java 21 → 25

Migrate the project in your working directory from Java 21 to Java 25. GOAL: it COMPILES and passes its TESTS under JDK 25, conserving every test that passed under JDK 21, with the effective compiler target raised to 25 (a project that merely compiles under 25 but still targets 21 is NOT a bump). Work autonomously until done.

## Tools — standard only (JDKs 21 and 25, Maven or Gradle, OpenRewrite from Maven Central)
Three operations recur below; run each with the two JDKs — no project-specific scripts:

**FIRST detect the build tool and use ONLY it for every operation:** `pom.xml` present → Maven; otherwise (`build.gradle`/`build.gradle.kts`) → Gradle. **NEVER introduce the other build system** — do NOT create a `pom.xml` in a Gradle project (or a `build.gradle` in a Maven one). The build/test gate compiles whatever build file is present, so adding the wrong one silently breaks dependency resolution (deps declared in the project's real build tool show up as `package … does not exist`).
- **compile under JDK N** — Maven: `JAVA_HOME=<jdkN> mvn -B -ntp -DskipTests compile`; Gradle: `./gradlew -Dorg.gradle.java.home=<jdkN> compileJava` (also `compileKotlin`/`compileTestJava`).
- **test under JDK N** — Maven: `JAVA_HOME=<jdkN> mvn -B -ntp test`; Gradle: `./gradlew -Dorg.gradle.java.home=<jdkN> test`.
- **apply the OpenRewrite program** — write `rewrite.yml` (below), then run it **under JDK 21 with the Java-25 recipe artifacts**:
  - Maven: `JAVA_HOME=<jdk21> mvn -B -ntp -U -Denforcer.skip=true org.openrewrite.maven:rewrite-maven-plugin:6.41.0:run -Drewrite.configLocation=$(pwd)/rewrite.yml -Drewrite.activeRecipes=com.bjv.Bump -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.36.0,org.openrewrite.recipe:rewrite-spring:6.31.0,org.openrewrite.recipe:rewrite-java-dependencies:1.55.3` — the **absolute** `configLocation` (`$(pwd)/rewrite.yml`) is required, else multi-module submodules report `Recipe(s) not found`.
  - Gradle: apply the OpenRewrite plugin through an init-script with `rewrite-migrate-java:3.36.0` / `rewrite-spring` / `rewrite-java-dependencies` on the `rewrite` configuration, then run `rewriteRun`.

CRITICAL — NEVER time-box these builds. Cold Gradle/Maven runs download distributions + the OpenRewrite jars and take MINUTES; let them finish. An apply that was cut off means the recipe was NOT applied — after applying, confirm BUILD SUCCESS and that the build files actually changed.

## How to work (graded on a CORRECT migration that conserves tests — nothing else counts if a test is lost or the bytecode isn't really at 25)
- Prefer the off-the-shelf transforms: the unparametrized meta-recipes + setting the Java version to 25 + (only if needed) the pinned Gradle wrapper are the clean path — use them first.
- Treat every manual edit and every project-specific dependency/plugin change as a LIABILITY. Make the FEWEST changes that genuinely work.
- Never touch or weaken test code (see FORBIDDEN).

## Proactive steps — do these BEFORE the first build, gated on what the project USES (not on an error)
- **Lombok (TWO changes, do BOTH up front):** if the build declares Lombok (grep build files for `org.projectlombok`), then as part of the START-HERE recipe: **(1) FLOOR Lombok to 1.18.46** — the JDK-25-capable release; 1.18.3x/1.18.40 PREDATE JDK 25 and silently fail. **(2) FORCE annotation processing** — JDK 23+ no longer auto-runs a processor found only on the classpath, so a plain `lombok` dependency stops generating: for **Maven** set property `maven.compiler.proc=full`; for **Gradle** ensure Lombok is on the processor path (`annotationProcessor`/`testAnnotationProcessor "org.projectlombok:lombok"`, or the `io.freefair.lombok` plugin). Do NOT wait for a compile error — an old or un-run Lombok fails OPEN-ENDEDLY and NEVER names Lombok: `cannot find symbol getX()`/`builder()`/`log`, `constructor … cannot be applied`, different symbols per project, indistinguishable from ordinary API-change errors. The floor alone is NOT enough — without proc=full it still fails; do both.

- **Gradle wrapper floor (run BEFORE the first JDK-25 build; gated on the STRUCTURAL wrapper version, not an error):** if the build tool is **Gradle**, read the wrapper version in `gradle/wrapper/gradle-wrapper.properties` (the `gradle-<N>-bin.zip` in `distributionUrl`). **If it is below 9.1** (the JDK-25 floor), do BOTH of these *before* applying the recipe / building under JDK 25 — never wait for the error: **(1)** set `distributionUrl` to **`gradle-9.1.0-bin.zip`** (the pinned value; via `org.openrewrite.gradle.UpdateGradleWrapper` {version: "9.1.0"} or by editing the line directly — NEVER a `file://` path), and **(2)** ensure the wrapper script is executable (**`chmod +x gradlew`**). Gradle itself runs on the build JDK, and Gradle **8.x cannot run on JDK 25**: it dies during *configuration* with `BUG! ... Unsupported class file major version 69` in `_BuildScript_` while parsing `settings.gradle`/`build.gradle`, before any project code is touched (Gradle 8.5/8.9/8.10 all fail; 9.0.0 also fails; **9.1.0** is the first that runs on JDK 25 — verified). That v69 text is the SAME signature JaCoCo/ByteBuddy/Mockito also emit, so reactive error-matching cannot reliably attribute it to the wrapper — but the **structural trigger (wrapper version < 9.1) is unambiguous**, which is exactly why this is proactive (same test as the Lombok proactive step). The `chmod +x` matters: if `gradlew` is checked in WITHOUT the executable bit, the build silently falls back to a system `gradle` (e.g. 8.10.2) that the `distributionUrl` edit can never influence — so a wrapper bump that “looks applied” still dies on v69 until `gradlew` is made executable. The reactive Troubleshooting row below stays as a back-stop.

## START HERE — write `rewrite.yml`, then apply it
```
type: specs.openrewrite.org/v1beta/recipe
name: com.bjv.Bump
recipeList:
  - org.openrewrite.java.migrate.UpgradePluginsForJava25
  - org.openrewrite.java.migrate.UpgradeBuildToJava25
  - org.openrewrite.java.migrate.UpgradeJavaVersion:
      version: 25
  # PROACTIVE (include ONLY if the project declares Lombok — see Proactive steps):
  - org.openrewrite.java.dependencies.UpgradeDependencyVersion:
      groupId: org.projectlombok
      artifactId: lombok
      newVersion: 1.18.46
  # PROACTIVE (Maven + Lombok only): JDK 23+ won't auto-run a classpath-only processor
  - org.openrewrite.maven.AddProperty:
      key: maven.compiler.proc
      value: full
```
Then compile under JDK 25. If it compiles, test under JDK 25. If tests pass and none are lost, you are done.

## Reflect loop — if compile or test under 25 fails, read the error, fix the FIRST wall, re-run (no iteration limit)
JDK-25 class-file version is **69** — a tool that reads bytecode via ASM must be new enough for v69.
- **Lombok:** handled PROACTIVELY above (floor 1.18.46 + force annotation processing). BACK-STOP: if you still see open-ended `cannot find symbol getX()`/`builder()` / `constructor … cannot be applied` from a Lombok-annotated class, EITHER the floor or proc=full did not take — verify the pom has lombok **1.18.46** AND `<maven.compiler.proc>full</maven.compiler.proc>` (Gradle: lombok on the annotationProcessor path), then re-apply and rebuild.
- **ByteBuddy/Mockito on v69:** `Mockito cannot mock this class` / `Cannot define class using reflection` / `Unsupported class file major version 69`. Mockito needs **≥ 5.18**; and FORCE `net.bytebuddy:byte-buddy(:agent)` ≥ **1.17.6** (a plain bump is overridden by the Spring BOM ~1.14 — force it: Maven `<byte-buddy.version>`, Gradle `resolutionStrategy.eachDependency { if (requested.group=="net.bytebuddy") useVersion("1.17.6") }`). Triage: `-Dnet.bytebuddy.experimental=true` makes mocks work on an unsupported-but-close JDK — if it does, ship the version bump, not the flag.
- **JaCoCo on v69:** `Unsupported class file major version 69` → floor jacoco to **0.8.13** (0.8.12 is 17/21 only).
- **Test fork strong-encapsulation** (`InaccessibleObjectException`): add `--add-opens=<module>/<pkg>=ALL-UNNAMED` per package the error names to the test fork args (one token each; preserve existing argLine).
- **Gradle + Kotlin:** emitting **JVM 25 bytecode needs Kotlin ≥ 2.3.x** (verified: 2.3.20/2.4.0 emit major-69). **Kotlin 2.2.x — INCLUDING 2.2.20 — silently FALLS BACK to JVM 24** logging `does not yet support 25 JDK target, falling back to JVM_24`; that is NOT harmless — it leaves the effective target at 24 and FAILS the target gate. Bump every `kotlin("...")` plugin id to **≥ 2.3.20** and set `kotlin { jvmToolchain(25) }`; do not accept the JVM_24 fallback. Older Kotlin (2.1.x) lacks the `JvmTarget.JVM_25` enum entirely (`Unresolved reference 'JVM_25'` at build-script compile) — same fix. **KSP, if present, is version-locked to Kotlin and uses a UNIFIED version (not `<kotlin>-<ksp>`): for Kotlin 2.3.20 use `com.google.devtools.ksp` and `symbol-processing-api` `2.3.9`** (the KSP2 release that targets Kotlin 2.3.20). Do NOT guess a `<kotlin>-2.1.0`-style suffix (those don't exist); confirm the exact version against the repository's `maven-metadata.xml`. In **Quarkus** the Kotlin version is pinned by the platform BOM — bump the **Quarkus platform**, not Kotlin directly.
- **Gradle wrapper below the JDK-25 floor (9.1):** Gradle 8.x dies during configuration with `BUG! ... Unsupported class file major version 69` in `_BuildScript_` (and can't parse a JDK-25 toolchain version string like `25.0.3`). 9.0.0 ALSO fails — **9.1.0** is the first that runs on JDK 25. Bump via `org.openrewrite.gradle.UpdateGradleWrapper` {version: "9.1.0"}, or set `distributionUrl` to `gradle-9.1.0-bin.zip`, AND make the wrapper executable (`chmod +x gradlew`) — without the exec bit the build silently falls back to a system `gradle` your `distributionUrl` edit cannot influence. Hard-gate: `JAVA_HOME=<jdk25> ./gradlew --version` must succeed FIRST; `Unsupported class file major version 69` in `_BuildScript_` = the wrapper, not your code. NEVER point `distributionUrl` at a `file://` path.
- **After the 9.x wrapper bump:** `Failed to apply plugin` naming a Gradle-internal type → bump the failing *plugin* to its Gradle-9 line (nebula `ospackage` ≥ 12.3, `com.gradleup.shadow` ≥ 9.x with `enableRelocation`→`enableAutoRelocation`, `io.freefair.lombok` ≥ 9.x, spotless `googleJavaFormat` ≥ 1.34). Bump only the failing plugin; repeat per plugin.
- **Multi-module (Gradle):** a JDK bump is per-BUILD, not per-module. `Dependency resolution is looking for a library compatible with JVM runtime version N, but 'project :X' is only compatible with M` = set the SAME target in every module (root `allprojects`/`subprojects`).
- **Multi-module (Maven) — SILENT target miss:** if each submodule redeclares `<java.version>`/`<maven.compiler.source>`/`<maven.compiler.target>` in its own `<properties>`, `UpgradeJavaVersion` bumps ONLY the ROOT pom — the submodules' local props win, so they still compile at 21 and the build SUCCEEDS while the effective target stays < 25 (fails the target gate even though nothing errors). A green build does NOT prove the bump. FIX: force every module's properties to 25 via `org.openrewrite.maven.ChangePropertyValue` — one entry each for `java.version`, `maven.compiler.source`, `maven.compiler.target` (newValue: "25"); these update ALL modules in one run. Verify EACH module's bytecode is at 25, not just that the build passed.
- **`Cannot find a Java installation … matching {languageVersion=N}`** (foojay resolver timeout): point Gradle at the installed JDKs `-Porg.gradle.java.installations.paths=<jdk21>,<jdk25>` and DROP `vendor`/`implementation` pins from `toolchain{}`.
- **`Entry <path> is a duplicate but no duplicate handling strategy has been set`** (Gradle 7+ hard error): `tasks.withType(Copy).configureEach { duplicatesStrategy = DuplicatesStrategy.EXCLUDE }`.
- **`jctools … sun.misc.Unsafe`** failing (not just warning) on 25: use the Unsafe-free path the lib already ships — `org.jctools.queues.atomic.*` instead of `org.jctools.queues.*` (a newer jctools often does NOT fix it). To merely silence the warning on the test fork: `--sun-misc-unsafe-memory-access=allow`.
- **A removed/changed JDK API in the project's OWN source:** hand-edit minimally.

## General discipline (these stop you chasing non-problems)
- **EDIT HYGIENE:** after EVERY build-file edit, BEFORE rebuilding, validate it — `./gradlew help -q` (Maven `mvn -q validate`). If that fails naming the file you just edited, YOUR edit broke the script: fix/revert it, don't chase it as a migration error.
- **NOT YOUR TESTS:** tests needing Docker/Testcontainers/a database/Selenium/the network were already failing in the baseline — NOT in your conserve-set. Only tests that PASSED under 21 must still pass.
- OOM during tests is usually DOWNSTREAM of an earlier real error — fix the FIRST error first.
- Stale generated classes (`ClassAlreadyExistsException`): `./gradlew clean` / `rm -rf target`, re-run.
- `--add-opens` for deep reflection, `--add-exports` only for compile/link to a non-exported API; do NOT use `--illegal-access=permit` (removed in JDK 17). Canonical opens set: `--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.text=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.time=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.desktop/java.awt.font=ALL-UNNAMED --add-opens=java.management/java.lang.management=ALL-UNNAMED`.

## When to bail (report honestly)
- **EasyMock** has no JDK-25 path — bail (its proxy class-injection is broken on 25 and `EasyMockToMockito` is lossy).
- Hibernate/Quarkus proxy-gen ByteBuddy at build time may need a framework bump or `-Dnet.bytebuddy.experimental=true`.
- A **semantic JDK change** in the project's own code (confirm with a pristine-checkout probe).
- An abandoned dependency with no JDK-25 release, or a needed version not present in the repository.
- Native (CMake/JNI) modules.

## Absolutely forbidden (cheating — fails the run)
Do NOT delete/skip/disable/weaken any test or assertion; no `-DskipTests`/`<skip>true`; do NOT delete test files; do NOT touch test code to make it pass. Conservation is checked independently.

When the project passes its tests under JDK 25 with no tests lost and the effective target is 25, say you are done and summarize what you changed.
