---
name: bump-java-version
description: Migrate a Maven or Gradle project from one Java LTS to the next (8->11, 11->17, 17->21, 21->25) so it still compiles under the new JDK and previously-passing tests still pass — via OpenRewrite recipes, using only standard tools (JDKs, Maven or Gradle, and OpenRewrite recipes from Maven Central; no project-specific scripts). Use when upgrading or bumping the Java version of a Maven or Gradle project, modernizing to a newer JDK or LTS, or performing the Spring Boot 1->2 / 2->3 and javax->jakarta migration that a Java upgrade requires.
---

# Bumping a Maven or Gradle project one Java LTS step — via OpenRewrite recipes

Migrate a project **one** Java LTS step (8→11, 11→17, 17→21, or 21→25) so it **compiles** under the new
JDK and every test that **passed before still passes**. Uses only standard tools — **JDKs, the project's
build tool (Maven or Gradle), and OpenRewrite** (recipes pulled from Maven Central). No project-specific
scripts.

**Detect the build tool first** — every step below has a **Maven** path and a **Gradle** path:
- a root **`pom.xml`** → **Maven**;
- a **`build.gradle`/`.kts` + `gradlew`** and no `pom.xml` → **Gradle**.

Always use the project's wrapper when present (`./mvnw`, and for Gradle **always** the repo's `./gradlew`,
never a system `gradle`). Do **one** step at a time (8→17 = do 8→11 fully green, then 11→17).

**Discipline — recipes only, never by hand (this governs every step below):**
- **Apply every change with an OpenRewrite recipe.** Prefer the *unparametrized* meta-recipes (`UpgradeBuildToJava<N>`, `UpgradeSpringBoot_<X>`, §3) that bundle the dep/plugin/flag fixes; a recipe you must parametrize is a weaker, less-portable form.
- **Never hand-edit a `pom.xml`/`build.gradle` or improvise source.** The §4/§7 entries below name *what* a wall needs (recognition) — apply each via its recipe; if a needed change has **no** recipe, that is a recipe gap → **bail `I_MADE_MANUAL_EDIT`**, do not hand-apply it. An agent that, cut off from its recipes, fabricates a migration from its own head is producing unauditable fantasy, not a bump.
- **Verify the recipe path first.** Before migrating, confirm the recipe artifacts resolve (Maven Central / the proxy is reachable); if they don't, **bail `RECIPE_PATH_UNREACHABLE`** up front — never fall back to manual edits.

**How to read this:** §0–§5 are the procedure — follow them in order. When a step fails, find your error
in **§7** (grouped by kind) and apply the fix, then re-run the failed step. **§6** (Spring Boot) and **§8**
(when to bail) are entered only when §7 sends you there.

---

## 0. Tools you need (all standard)

- The **two JDKs** — the one the project builds with now (`jv_from`) and the target (`jv_to`).
  e.g. for 8→11 you need JDK 8 **and** JDK 11. Select per command with `JAVA_HOME`.
- **Maven** (`mvn` / `./mvnw`) **or** **Gradle** (the repo's `./gradlew`).
- **Internet** — OpenRewrite recipes and any new deps come from Maven Central.
- **git** — commit a baseline first so you can `diff`/revert.

Versions used below are known-good; newer point releases are fine:
- rewrite-maven-plugin `6.40.0`, `rewrite-migrate-java` `3.35.0`, `rewrite-spring` `6.31.0`.
- For the **21→25** hop use `rewrite-maven-plugin` `6.41.0` + `rewrite-migrate-java` `3.36.0` — these carry the Java-25 recipes (`UpgradeBuildToJava25`, `UpgradePluginsForJava25`).
- Gradle runs the **same** recipes through the `rewrite-gradle-plugin` init-script (§3).

---

## 1. Record the baseline (OLD JDK)

```bash
git add -A && git commit -m baseline
```
- **Maven:** `JAVA_HOME=<jdk_from> mvn -B -ntp test` → read every `**/target/surefire-reports/TEST-*.xml`.
- **Gradle:** `JAVA_HOME=<jdk_from> ./gradlew test` → read every `**/build/test-results/test/TEST-*.xml`.

The tests with **0 failures/errors** are your **baseline-pass set** — the contract to conserve. Tests
already failing in the baseline (no Docker, no DB, no network) are **not** your responsibility.

> **Gradle — the declared toolchain is the *bytecode target*, not the build floor.** A project whose
> toolchain says `of(8)` can still need JDK 11+ to build (a codegen tool like ANTLR may require it).
> Trust what actually compiles in the baseline, not the declared number — that real floor is your true `jv_from`.

---

## 2. Make Lombok safe (if the project uses Lombok)

Old Lombok breaks `javac` on newer JDKs — always the same *too-old-for-this-javac* cause, surfacing as
any of: `NoSuchFieldError: JCTree$JCImport.qualid` (JDK 17/21), `ExceptionInInitializerError:
com.sun.tools.javac.code.TypeTag :: UNKNOWN` (JDK 25), or `Could not initialize class lombok.javac.Javac`.
Floor the Lombok version: **1.18.30+** for JDK 17/21, **1.18.40+** for JDK 25 (a project already on a
1.18.3x release still needs the bump for 25; the `lombok.javac.Javac` init case clears at 1.18.38). Set it
in **Maven** via the `lombok.version` property / dependency; in **Gradle** on the `org.projectlombok:lombok`
dependency (and its `annotationProcessor`). Do this **before** any step under the new JDK.

---

## 3. Bump the build to the new Java version

### Maven — run the official OpenRewrite "migrate to Java N" recipes

From `org.openrewrite.recipe:rewrite-migrate-java`. Invoke the plugin directly (no pom changes needed):

**8 → 11** — one recipe:
```bash
JAVA_HOME=<jdk_to> mvn -B -ntp -U -Denforcer.skip=true \
  org.openrewrite.maven:rewrite-maven-plugin:6.40.0:run \
  -Drewrite.activeRecipes=org.openrewrite.java.migrate.Java8toJava11 \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.35.0
```

**11 → 17** — run **in order** (same command, swap the recipe):
1. `org.openrewrite.java.migrate.UpgradePluginsForJava17`
2. `org.openrewrite.java.migrate.UpgradeBuildToJava17`

**17 → 21** — in order:
1. `org.openrewrite.java.migrate.UpgradePluginsForJava21`
2. `org.openrewrite.java.migrate.UpgradeBuildToJava21`

**21 → 25** — in order; needs the newer artifacts (`rewrite-maven-plugin:6.41.0` + `rewrite-migrate-java:3.36.0`),
run with **JDK 25** as `<jdk_to>`:
1. `org.openrewrite.java.migrate.UpgradePluginsForJava25`
2. `org.openrewrite.java.migrate.UpgradeBuildToJava25`

> **If the OpenRewrite step itself fails to compile** (it type-attributes by compiling, e.g.
> `package javax.xml.bind does not exist`): either apply the **EE-deps fix from §4 first**, or run the
> recipe under the **OLD** JDK (`JAVA_HOME=<jdk_from>`), where the project still compiles — then continue.
> (Projects with `<annotationProcessorPaths>` — MapStruct/JHipster — see §7.)

### Gradle — set the toolchain, then OpenRewrite only if needed

1. **Set `jv_to` in the build script** — usually the whole bump on its own:
   `java { toolchain { languageVersion = JavaLanguageVersion.of(<jv_to>) } }`, or
   `sourceCompatibility`/`targetCompatibility`/`options.release` (Kotlin: also `kotlin { jvmToolchain(<jv_to>) }`, see §4).
   (Verified: a Spring Boot 2.7 / Gradle 8.10 project went 11→17 with only the toolchain edit.)
2. **Bump the Gradle wrapper if it predates `jv_to` — the #1 Gradle wall:** JDK 11 needs Gradle ≥ 5.0, JDK 17 ≥ 7.3,
   JDK 21 ≥ 8.5, JDK 25 ≥ 9.0 — Gradle 8.x can't even *run* a JDK-25 toolchain (it fails parsing the
   version string), so the matching floor is required to build/test **on** `jv_to`, not just to emit its bytecode.
   `./gradlew wrapper --gradle-version <X>` (run under the OLD JDK if the current wrapper won't start on `jv_to`). **Hard gate — do this FIRST on EVERY hop, never skip it:** `JAVA_HOME=/opt/jdk/<jv_to> ./gradlew --version` must succeed before any build; two signatures mean the wrapper itself (not your code) is too old — bump it and re-verify before anything else: `Unsupported class file major version <N>` in `_BuildScript_` / while Gradle *configures*, and `Could not determine java version from '<v>'` (an old wrapper that can't parse the running JDK's version string, e.g. `11.0.31` / `25.0.3`).
3. **If it still won't compile, run the SAME recipes via the `rewrite-gradle-plugin` init-script**
   (no build edits; verified end-to-end):
   ```bash
   cat > /tmp/rw.init.gradle <<'G2'
   initscript {
     repositories { gradlePluginPortal(); mavenCentral() }
     dependencies { classpath("org.openrewrite:plugin:latest.release") }
   }
   rootProject {
     apply plugin: org.openrewrite.gradle.RewritePlugin
     dependencies { rewrite("org.openrewrite.recipe:rewrite-migrate-java:latest.release") }
     rewrite { activeRecipe("org.openrewrite.java.migrate.UpgradeToJava17") }   // or UpgradeBuildToJava21 / UpgradeBuildToJava25
   }
   G2
   JAVA_HOME=<jdk_to> ./gradlew --no-daemon --init-script /tmp/rw.init.gradle rewriteRun
   ```

Review the diff (`git diff`) before continuing; commit it.

---

## 4. JDK-removal fixes — what the §3 recipes apply (recognition, not hand-edits)

The `UpgradeBuildToJava<N>` recipes (§3) apply these. **Do NOT hand-apply them.** The list is recognition — *what* the JDK removed and what a correct migration restores. If a symptom below persists **after** the recipe ran, it is a recipe gap → **bail `I_MADE_MANUAL_EDIT`**, never hand-edit (cases in §7).

**For 8→11 (and 11→17 if still javax-era)** — re-add the Java-EE modules removed in JDK 11.
- **Maven** — into a real top-level `<dependencies>`:
```xml
<dependency><groupId>javax.xml.bind</groupId><artifactId>jaxb-api</artifactId><version>2.3.1</version></dependency>
<dependency><groupId>org.glassfish.jaxb</groupId><artifactId>jaxb-runtime</artifactId><version>2.3.1</version><scope>runtime</scope></dependency>
<dependency><groupId>com.sun.activation</groupId><artifactId>javax.activation</artifactId><version>1.2.0</version><scope>runtime</scope></dependency>
<dependency><groupId>javax.annotation</groupId><artifactId>javax.annotation-api</artifactId><version>1.3.2</version></dependency>
<dependency><groupId>javax.xml.ws</groupId><artifactId>jaxws-api</artifactId><version>2.3.1</version></dependency>
```
  And if the effective `maven-surefire-plugin` is **≤ 2.21** (old Spring Boot parents pin it), floor it:
  `<maven-surefire-plugin.version>2.22.2</maven-surefire-plugin.version>` — it NPEs under JDK 9+ otherwise.
- **Gradle** — the same coordinates in `dependencies {}` (`implementation`, with `runtimeOnly` for the runtime-scoped ones).

> **Also remove any `--add-modules java.xml.bind` / `java.se.ee` / `java.activation`** the project carried as a JDK-9/10 stopgap. JDK 11 **removed** those modules, so the flag fails with `java.lang.module.FindException: Module java.xml.bind not found` — at build *and* at runtime — **even once the jars above are present**. The dependencies replace the flag; the flag must go.

**For 11→17, 17→21, and 21→25** — the test fork needs strong-encapsulation opened, with:
```
--add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.lang.reflect=ALL-UNNAMED
--add-opens java.base/java.util=ALL-UNNAMED --add-opens java.base/java.text=ALL-UNNAMED
--add-opens java.base/java.io=ALL-UNNAMED --add-opens java.base/java.nio=ALL-UNNAMED
--add-opens java.base/java.time=ALL-UNNAMED --add-opens java.base/sun.nio.ch=ALL-UNNAMED
--add-opens java.desktop/java.awt.font=ALL-UNNAMED --add-opens java.management/java.lang.management=ALL-UNNAMED
```
- **Maven:** put them in `maven-surefire-plugin` `<configuration><argLine>` (preserve any existing `<argLine>`, e.g. JaCoCo's `@{argLine}`).
- **Gradle:** `tasks.test { jvmArgs("--add-opens=java.base/java.lang=ALL-UNNAMED", "--add-opens=java.base/java.util=ALL-UNNAMED", …) }` — **one token each, joined with `=`** (a space-joined `"--add-opens java.base/…"` is rejected as one unknown option and the test JVM won't start).

> **This list covers the common cases — it is not exhaustive.** The exception names the exact
> module/package it needs (`module {A} does not "opens {package}" to ...`), so if a library trips one not
> listed (e.g. `java.util.concurrent`, `java.math`, `java.security`), add it in the same form
> `--add-opens {A}/{package}=ALL-UNNAMED`. Use **`--add-opens`** for *deep reflection* (`setAccessible` on
> JDK internals — the usual test case) and **`--add-exports`** only for *compile/link* access to a
> non-exported API. Don't reach for `--illegal-access=permit`: JEP 403 removed it in JDK 17, so it's a
> no-op/error there — `--add-opens` (or the `Add-Opens` JAR-manifest attribute) is the only lever left.

And if JaCoCo is pinned old, bump it to **0.8.12** (JDK 17/21) — or **0.8.13+** for JDK 25 (an ASM-version
wall, see §7-B): Maven `jacoco-maven-plugin`, Gradle the `jacoco { toolVersion }`.

**Gradle + Kotlin:** if the project also has Kotlin (`compileKotlin` task / `kotlin {}` plugin), set the
**Kotlin** JVM target too — `kotlin { jvmToolchain(<jv_to>) }`, not just the Java toolchain — or Gradle
fails *"Inconsistent JVM-target compatibility detected for tasks 'compileJava' (N) and 'compileKotlin' (M)"*.
JVM target **25 needs Kotlin ≥ 2.2** (older Kotlin caps at JVM 21/22); in **Quarkus** the Kotlin version
is pinned by the platform BOM, so bump the **Quarkus platform**, not Kotlin directly (a raw Kotlin bump is overridden).

---

## 5. Compile + test under the NEW JDK, conserve

- **Maven:**
  ```bash
  JAVA_HOME=<jdk_to> mvn -B -ntp -DskipTests compile      # must succeed
  JAVA_HOME=<jdk_to> mvn -B -ntp test                     # baseline-pass set must still pass
  ```
- **Gradle:**
  ```bash
  JAVA_HOME=<jdk_to> ./gradlew testClasses                # must succeed
  JAVA_HOME=<jdk_to> ./gradlew test                       # baseline-pass set must still pass
  ```

On any failure: find the first real error, apply the matching §7 fix, `git commit`, re-run the **failed**
step. **Done when** it compiles under `jv_to` AND baseline-pass ⊆ post-pass.

---

## 6. Spring Boot upgrades (only when §7 points here)

Full upgrades — do them only if §7 sends you here, then re-run §3–§5.

- **Maven** — the OpenRewrite Spring recipes (artifact `org.openrewrite.recipe:rewrite-spring:6.31.0`,
  **kept on the plugin's rewrite line** — 6.x for `rewrite-maven-plugin:6.40.0`; a stale `rewrite-spring`
  5.x/7.x fails with a cryptic `ReplaceStringLiteralValue … is required` NPE, see §7-D):
  - **SB 1.x → 2.7** (1.x can't run on JDK 11) — run under the OLD JDK, recipe
    `org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7`.
  - **SB 2.0–2.4 → 2.7** (Java 17: Spring below 5.3 component-scans with an ASM that can't read v61
    bytecode — the `Unsupported class file major version 61` error) — SAME recipe `UpgradeSpringBoot_2_7`
    (it upgrades any 1.x/2.x). Do **not** hand-pick an intermediate version: anything below SB 2.5
    (Spring 5.3) fails with the *identical* ASM error, which falsely reads as "the bump didn't help".
  - **SB 2.x → 3.3** (SB2 BOM too old for JDK 21 / ASM, or Spring Security 6 needed) — recipe
    `org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3` (also does javax→jakarta + Security 6).
    *If you must stay on the 2.7 line for Java 21*, the floor is **SB 2.7.17+** (earlier 2.7.x bundles an
    ASM that can't read v65 → the component-scan failure in §7-B); but 2.7 is EOL, so prefer 3.x.
- **Gradle** — bump the Spring Boot plugin version (`id 'org.springframework.boot' version '<new>'`).
  Even a **patch** bump can be the fix: SB 3.0.0's Spring 6.0.0 bundles ASM 9.4, which can't parse Java-21
  bytecode (class file v65) during component scan (`@SpringBootTest` contextLoads fails); SB 3.0.7+ ships
  ASM 9.5, and SB 3.2.x fully supports Java 21. **If you're already on SB ≥ 3.2 and still hit the v65 ASM
  error, it isn't Spring Boot** — a *transitive* dependency is shipping an old shaded ASM; find and
  bump/force that one (§7-B), don't keep bumping Spring Boot. For a major SB upgrade, run the same
  `UpgradeSpringBoot_3_3` recipe via the §3 init-script.

---

## 7. Troubleshooting (match the first real error)

> **Governed by the Discipline (top):** each row names *what* the wall needs — apply it via an OpenRewrite recipe (the §3 meta-recipes cover most); where no recipe provides it, **bail `I_MADE_MANUAL_EDIT`**, never hand-edit.

Fixes apply to **both** build tools; where the location differs, Maven uses `<dependencyManagement>`/`<argLine>`,
Gradle uses `dependencies {}`/`tasks.test {}`. Find your error in the group below.

### 7-A. JDK-removed APIs & too-old plugins

| Symptom | Cause | Fix |
|---|---|---|
| `package javax.xml.bind… does not exist`, `XmlTransient`, `JAXBException`, `javax/annotation/Generated` | EE modules removed in JDK 11 | The §4 EE deps. **Maven, if during annotation processing** (`<annotationProcessorPaths>` present): regular deps aren't on the processor path — add `jaxb-api` + `javax.annotation-api` as `<path>` entries inside `<annotationProcessorPaths>` too. |
| `maven-surefire-plugin:2.20/2.21 … NullPointerException` | surefire ≤ 2.21 broken on JDK 9+ | Force surefire **2.22.2+** (pom version, or `<maven-surefire-plugin.version>2.22.2</…>` if BOM-pinned). |
| `Error injecting JarArchiver` / `ExceptionInInitializerError at JarArchiver.<init>` | old `maven-jar/war/assembly` plexus-archiver predates JDK 11 | Bump the plugin (`maven-jar-plugin ≥ 3.4.1`) or dM `org.codehaus.plexus:plexus-archiver:4.2.7`. |
| `com.sun:tools:jar` not found / `tools.jar` systemPath | `tools.jar` removed in JDK 9 | Delete the `com.sun:tools` system-scoped dependency. If code uses `com.sun.tools.javac.*`: add `--add-exports jdk.compiler/com.sun.tools.javac.*=ALL-UNNAMED` to the compiler args **and** the test fork, and use `<source>/<target>` (NOT `<release>`). |
| `no Bean Validation provider could be found` | the validation *implementation* was dropped — and it's often a benign **DEBUG** line, not an error | If tests pass, it's cosmetic — conserve. Otherwise add an impl: in a **Spring Boot** project prefer `spring-boot-starter-validation` (version-managed); else `org.hibernate.validator:hibernate-validator` (6.2.5.Final javax / 8.0.1.Final jakarta). |
| Generated `*Grpc.java` / protobuf stubs: `cannot find symbol: class Generated` at `@javax.annotation.Generated` | grpc/protoc-generated code references `javax.annotation.Generated`, not in the JDK — the dep got lost in the migration (BOM/configuration rework) | Add `compileOnly "javax.annotation:javax.annotation-api:1.3.2"` to the module that compiles generated sources (or move to a grpc/protoc version that emits `jakarta.annotation` and add that api instead). |

### 7-B. Bytecode / ASM version walls

> **The class-file → JDK map:** v52=8, v55=11, **v61=17, v65=21, v69=25**. When a tool that *reads bytecode
> via ASM* is older than the JDK that produced a class, it can't parse it — the symptom is `Unsupported
> class file major version N` / `ASM ClassReader failed to parse` (or a bare `IllegalArgumentException at
> ClassReader.java:N`). **The rule: identify which bytecode-reading tool fired, and bump just that tool.**
> The rows below map the common culprits by where they fire. (`sun.misc.Unsafe` and version-string parsing
> are related "old lib vs new JDK" walls, grouped here too.)

| Symptom | Cause / where it fires | Fix |
|---|---|---|
| `Cannot define class using reflection` / `sun.misc.Unsafe.defineClass` / `MockitoException` (often then `OutOfMemoryError`), or `Mockito cannot mock this class` | old Mockito's shaded ByteBuddy is too old for the JDK | Bump **Mockito** — **JDK 21/25 use ≥ 5.18** (bundles a v69-capable ByteBuddy); old `2.23.4` is JDK 8/11 only and won't mock on 25. Maven: dM `org.mockito:mockito-core` (+ `org.objenesis`) **before** any BOM import; Gradle: `extra["mockito.version"]` (Spring BOM) or bump `mockito-core`. If mocks still fail on 25, **force ByteBuddy** (next row). Quick triage: `-Dnet.bytebuddy.experimental=true` makes mocks work on an unsupported-but-close JDK — if it does, the real fix is the version bump (don't ship the flag). On **JDK 21+** Mockito also warns it *self-attaches* its inline agent (`self-attaching … disallowed in a future release`) — a warning today; silence it durably with `-javaagent:<mockito-core jar>` on the surefire/failsafe fork. |
| `ASM ClassReader failed to parse` / `Unsupported class file major version 61/65/69`, **or** a bare `IllegalArgumentException at ClassReader.java:N` wrapped in `BeanDefinitionStoreException` → `SimpleMetadataReader` (Spring **component-scan** — this variant has **no** "major version" text) | a bytecode-reading tool's bundled ASM is too old for the JDK (see the map above) | Identify the culprit and bump it: **ByteBuddy** — force `net.bytebuddy:byte-buddy(:agent)` **≥ 1.17.6 (JDK 25)**, 1.14.12+ (17/21); a plain bump is often **overridden by a BOM** (Spring Boot pins ~1.14) so force it (Gradle `configurations.all { resolutionStrategy.eachDependency { if (requested.group=="net.bytebuddy") useVersion("1.17.6") } }` or `extra["byte-buddy.version"]`; Maven a `<byte-buddy.version>` property). **JaCoCo** → 0.8.13 (§4). **Hibernate/Quarkus** proxy-gen → bump the framework, or `-Dnet.bytebuddy.experimental=true`. **Groovy** (Spock, `spring-cloud-contract` test-gen, the Gradle build-script decompiler) — 4.0.x can't read v65, bump Groovy / its bundling tool. **Spring component-scan** (Spring 5.2.x / SB 2.0–2.1, or SB 3.0.0 on JDK 21) → **Spring Boot bump** (§6); but on **SB ≥ 3.2** it's a *transitive* ASM dep, not Spring Boot itself. **EasyMock has no JDK-25 path → bail.** |
| `WARNING: … sun.misc.Unsafe::objectFieldOffset`/`arrayBaseOffset … terminally deprecated` from a dependency (jctools, Netty, …) on JDK 24+ — or an outright failure once a JDK removes it | the dep calls `sun.misc.Unsafe` memory-access methods: **JEP 471** deprecated them (JDK 23), **JEP 498** warns at runtime (JDK 24), removal comes later | While it's still only a **warning** and tests pass, it's **cosmetic — conserve** (you can silence it with `--sun-misc-unsafe-memory-access=allow` on the test fork). If a JDK actually fails on it: a newer dep version **often does NOT fix it** (jctools 4.0.5 still calls it; verify the *proposed* version on the target JDK first), so prefer an Unsafe-free path the lib already ships — e.g. jctools `org.jctools.queues.atomic.*` (AtomicFieldUpdater-backed) instead of `org.jctools.queues.*`. |
| `[error] target level should be in '1.1'...'1.8','9'...'N' (or …) or cldc1.1: <jv_to>` — note the format is NOT javac's | an **embedded compiler** (AspectJ `ajc`, Eclipse ECJ) is doing the compiling and its version caps below `jv_to` | Bump the embedded compiler, not the JDK flags: AspectJ `aspectjrt`/`aspectjtools`/plugin ≥ 1.9.8 for Java 17, ≥ 1.9.21 for 21 (+ the matching `aspectj.version` property / Gradle aspectj plugin); ECJ → the JDT line matching the JDK. |
| `ArrayIndexOutOfBoundsException: Index 1 out of bounds for length 1` from a `<clinit>` (Jadira; Hibernate Validator 5.x → "Failed to load ApplicationContext") | the lib's own version parser (e.g. Jadira `JavaVersion`) splits `java.version` expecting the **legacy `1.x`** scheme; **JEP 223** (JDK 9) changed it to `11` / `17.0.x` / `9-ea`, so the split throws — a bare `11` is one element, hence `Index 1 out of bounds for length 1`. Fires with **no `-D` flag** | **Bump or replace the offending lib.** Jadira's JEP-223 fix landed in **`7.0.0.CR1`** — bump to it; but it's only a candidate release and the project is dormant, so if that's unworkable, drop the lib / **bail** (`ABANDONED_DEP`). Hibernate Validator 5.x → `6.2.5.Final`. *(Harness note: never inject `-Djava.version=<bare-major>` — that manufactures the length-1 split.)* |

### 7-C. Gradle build system

| Symptom | Cause | Fix |
|---|---|---|
| Wrapper won't start on the new JDK / `Unsupported class file major version` while *Gradle itself* configures, or `… does not support … toolchain` | Gradle wrapper too old for `jv_to` | §3 Gradle step 2 — bump the wrapper (JDK 17 ≥ 7.3, 21 ≥ 8.5, 25 ≥ 9.0). |
| After a wrapper bump to 9.x: `Failed to apply plugin` naming a Gradle-internal type/property — e.g. `PatternSets$PatternSetFactory`, `No such property: internal for class: …BuildParams` | a build *plugin* predates Gradle 9 (compiled against removed internal APIs) | Bump the **plugin**, not Gradle: each framework ships a Gradle-9 line (nebula `ospackage` ≥ 12.3, OpenSearch `build-tools` ≥ 3.4.0, `com.gradleup.shadow` ≥ 9.x — note its `enableRelocation`→`enableAutoRelocation` rename, `io.freefair.lombok` ≥ 9.x, spotless `googleJavaFormat` ≥ 1.34 for JDK 25, …) — find the failing plugin's Gradle-9 release and bump only it. Repeat per plugin; config-time failures, so each retry is seconds. |
| `Cannot find a Java installation … matching: {languageVersion=N, vendor=…}`, often with a `foojay` resolver timeout | a `toolchain {}` block demands a JDK Gradle can't auto-detect, and the foojay auto-provisioner has no network (common in containers/CI) | Point Gradle at the installed JDKs: `-Porg.gradle.java.installations.paths=<dir1>,<dir2>,…` (or the same key in `gradle.properties`), listing every JDK home the build needs (e.g. `/opt/jdk/21,/opt/jdk/25`); and drop `vendor`/`implementation` pins from `toolchain {}` — `languageVersion` alone is enough. |
| `Inconsistent JVM-target compatibility detected for tasks 'compileJava' (N) and 'compileKotlin' (M)` | Kotlin JVM target not aligned with Java | §4 Gradle+Kotlin: `kotlin { jvmToolchain(<jv_to>) }`. JVM 25 needs Kotlin ≥ 2.2 (Quarkus pins it via the platform BOM — bump the platform). *(Last resort: `kotlin.jvm.target.validation.mode=IGNORE` in `gradle.properties` **bypasses** the check — it hides a real mismatch, so align targets instead unless you only need to unblock.)* |
| Multi-module: `Dependency resolution is looking for a library compatible with JVM runtime version N, but 'project :X' is only compatible with … M or newer` | the bump changed `targetCompatibility`/toolchain in SOME modules but not others — JVM targets now disagree | A JDK bump is per-BUILD, not per-module: set the same target in every module (root `allprojects`/`subprojects` if present); and if the task only asks to *run* on the new JDK (CI/toolchain) while bytecode stays at the old floor, change NO module's target. |
| Tests fail with `ClassNotFoundException`/`NoClassDefFoundError` (often an SLF4J binder warning) for classes a **shaded/relocated** sibling module provides | the shadow module no longer produces/publishes its shaded jar under the new Gradle (its shadow plugin needs the Gradle-9 line + the `enableAutoRelocation` rename — see 7-C above), so consumers lose those classes at test runtime | Fix the PRODUCER: bump the shadow plugin, re-run `gradlew :<shaded-module>:shadowJar`, confirm the jar exists in its `build/libs`, then re-run tests. Never patch the consumer's deps to paper over it. |
| `Entry <path> is a duplicate but no duplicate handling strategy has been set` (after a wrapper bump to 7+) | Gradle 7 made duplicate handling in Copy/Jar/processResources a hard error (older Gradle silently allowed it) | Prefer fixing the duplicate source; otherwise set the strategy explicitly: `tasks.withType(Copy).configureEach { duplicatesStrategy = DuplicatesStrategy.EXCLUDE }` (or on the specific task). One-line, build-file-only. |
| `Could not get unknown property '…'` / `Script compilation error` appearing **right after you edited a build file** | YOUR edit broke the build script (unquoted reference, stray brace, misplaced block) — not a dependency or JDK issue | Validate after every build-file edit, before anything else: `./gradlew help -q` (Maven: `mvn -q validate`). If it fails naming the file you just touched, fix/revert THAT edit first — don't chase it as a migration problem. |

### 7-D. Spring Boot

| Symptom | Cause | Fix |
|---|---|---|
| `EmbeddedServletContainerException` / `spring-context-4.x`, bean-creation failures | Spring Boot 1.x can't run on JDK 11 | Do the **SB 1→2** upgrade (§6), then re-run. *(Apps with custom SB-1.x code on SB-2-removed APIs — e.g. WebGoat — won't compile on SB2; bail.)* |
| `cannot find symbol: class WebSecurityConfigurerAdapter` | Spring Security 6 (only after going to SB3) | Do the **SB 2→3** upgrade (§6), which migrates it. |
| `Recipe validation error … ReplaceStringLiteralValue … is required` / `NullPointerException` during `rewriteRun` (esp. an `UpgradeSpringBoot_3_x`) | `rewrite-spring` version is off the plugin's rewrite line (e.g. rewrite-7.x `rewrite-spring:5.x` against `rewrite-maven-plugin:6.40.0` = rewrite-8.x) | Use a coherent set: `rewrite-spring:6.31.0` with the 6.40.0 plugin. If you also pin `rewrite-migrate-java`, keep both from one `rewrite-recipe-bom`. |

### 7-E. Semantic / environmental (often not a regression)

| Symptom | Cause | Fix |
|---|---|---|
| With **zero dependency/code changes**, the new JDK alone breaks the repo's OWN code: its annotation processor dies (`Fatal error compiling: IllegalStateException: Duplicate key <method>`), or tests assert on `java.beans.Introspector`-derived properties whose discovery semantics changed | a **semantic JDK change** inside the project's source — not a version floor, not your edits | **Bail: `SEMANTIC_JDK_CHANGE`** — the fix is an upstream code change (rewrite the processor's method-keying / drop Introspector reliance), outside build-file vocabulary. **Confirm with a pristine-checkout probe** (it fails the same way under the new JDK) before labelling, so you never mislabel your own breakage as this. |
| `OutOfMemoryError` during tests (JHipster etc.) | **usually downstream** of a context-load failure | Fix the **first** real error first; only raise the test `-Xmx` if it's genuinely heap. |
| `jsonschema2pojo … ClassAlreadyExistsException` | stale generated classes | `rm -rf target` / `mvn clean` (Gradle: `./gradlew clean`), re-run. |
| Docker/Selenium/DB test errors (`Could not find a valid Docker environment`, Testcontainers, MariaDB4j) | needs infra the box lacks — failed in baseline too | Ignore — not a regression. |
| no `pom.xml`/`build.gradle` at root | nested project | find the shallowest build file, `cd` into it, run steps there. |

---

## 8. When to bail (honestly)

After the migration + every matching fix, if it still won't compile or tests still regress, stop and
report the failed step + the unresolved error. Known genuine bails:
- **`RECIPE_PATH_UNREACHABLE`** — the OpenRewrite recipe artifacts don't resolve (no Central/proxy reachability); bail **before** touching the project, never hand-migrate.
- **`I_MADE_MANUAL_EDIT`** — a wall needs a change no recipe provides; bail rather than hand-edit a build file or improvise. The unmet wall is a recipe gap to fill, not a thing to fake.
- **Spring Boot 1.x app whose custom code calls SB-2-removed APIs** (`EmbeddedServletContainerFactory`,
  `actuate.endpoint.mvc`, `thymeleaf.resourceresolver`) — needs a hand-written migration.
- **JHipster-8 app whose OpenRewrite step fails with a cascade** (JAXB → `javax.annotation.Generated`
  → MapStruct/jpamodelgen NPE) — the annotation-processing stack is too old for JDK 11; the real fix is a
  JHipster/Spring-Boot version upgrade, beyond a one-LTS-step bump.
- **Source genuinely uses a removed JDK API** that no recipe can rewrite.
- **A semantic JDK change inside the project's own code** (`SEMANTIC_JDK_CHANGE`, §7-E) — confirmed by a
  pristine-checkout probe failing the same way under the new JDK.
- **An abandoned dependency with no JDK-compatible release** (e.g. Jadira past `7.0.0.CR1`) that no bump fixes.
- **Gradle project with native modules** (CMake/C++ JNI — e.g. Arrow's gandiva/dataset) that don't build
  in a plain JVM environment — can't establish or conserve a full baseline.
- **A request that isn't actually a version bump** — e.g. an umbrella "move the *build toolchain* to JDK N"
  / CI-infrastructure issue where the code already compiles on the new JDK. Out of scope; say so.

An honest bail with the reason beats a green build that hides a dropped test.
