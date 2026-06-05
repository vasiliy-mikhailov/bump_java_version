# Bumping a Maven project one Java LTS step — by hand

A practical guide to migrating a Maven project **one** Java LTS step (8→11, 11→17, or 17→21)
so it still **compiles** under the new JDK and every test that **passed before still passes**.

---

## 0. Before you start

You need, on PATH or at known locations:
- **Both JDKs** — the one the project builds with now (`jv_from`) and the target (`jv_to`).
  e.g. for an 8→11 bump you need JDK 8 **and** JDK 11.
- **Maven** — system `mvn`, or the project's own `./mvnw` (Maven wrapper).
- **git** — commit a baseline first so you can `diff`/revert freely.

Pick the JDK per command with `JAVA_HOME`, e.g.:
```bash
JAVA_HOME=/path/to/jdk-11 mvn -B -ntp test
```

Do **one** step at a time. To go 8→17, do 8→11 first, get it fully green, then 11→17.

---

## 1. The procedure (the "happy path")

**Step 1 — Record the baseline (under the OLD JDK).**
```bash
git add -A && git commit -m baseline
JAVA_HOME=<jdk_from> mvn -B -ntp test
```
Record which tests pass. The authoritative source is the XML, not the console:
read every `**/target/surefire-reports/TEST-*.xml` and take the tests with **0 failures/errors**.
That set is your **baseline-pass** set — the contract you must conserve.
> Tests that already error in the baseline (no Docker, missing DB, no network) are **not** your
> responsibility — they fail before and after, so they're not regressions.

**Step 2 — Run the bump.**
```bash
bash scripts/bump_<jv_from>_to_<jv_to>.sh .
```
This is **long-running** (OpenRewrite parses and rewrites the whole project — often several
minutes, longer on multi-module repos). **Do not interrupt it.** It is finished only when it
prints `bump_<jv_from>_to_<jv_to> complete`.

What the script does, in order:
1. **Lombok safe-bump** — pins Lombok to ≥ 1.18.30 (older Lombok crashes javac 17/21).
2. **OpenRewrite migration recipes** — `Java8toJava11`, or `UpgradePluginsForJava17`+`UpgradeBuildToJava17`, etc.
3. **Deterministic compat layer** — re-adds the Java-EE modules the JDK removed (JAXB, activation,
   annotation, JAX-WS), raises JDK-incompatible plugins, floors old surefire/Mockito/JaCoCo, and
   (for 17/21) injects the `--add-opens` the test fork needs.

> No bump script? Do it manually: bump Lombok to 1.18.30, run the OpenRewrite recipe by hand
> (`mvn org.openrewrite.maven:rewrite-maven-plugin:run -Drewrite.activeRecipes=…`), then apply the
> EE-dep / plugin fixes from Troubleshooting as the errors appear.

**Step 3 — Compile under the NEW JDK.**
```bash
JAVA_HOME=<jdk_to> mvn -B -ntp -DskipTests compile
```
Must exit 0. If not → Troubleshooting.

**Step 4 — Test under the NEW JDK and conserve.**
```bash
JAVA_HOME=<jdk_to> mvn -B -ntp test
```
Re-read the surefire XML. **Every test in your baseline-pass set must still pass.** A green
compile with tests unrun or regressed is **not** done.

**Step 5 — On any failure:** read the `[ERROR]` block, find it in Troubleshooting, apply the fix,
`git commit`, and re-run the **failed** step (not the whole thing). Repeat until green.

**You are done when:** it compiles under `jv_to` **and** the baseline-pass set ⊆ the post-bump pass set.

---

## 2. Troubleshooting

Match the **first** real `[ERROR]` (ignore noise like "Could not resolve … from the proxy" if the
build continues). Most of these are deterministic dependency/plugin edits.

### Compilation / "package does not exist" (Java-EE modules removed in JDK 11)
**Symptom:** `package javax.xml.bind… does not exist`, `cannot find symbol: class XmlTransient`,
`NoClassDefFoundError: javax/xml/bind/JAXBException`, `javax/annotation/Generated`.
**Cause:** JAXB / JAX-WS / `javax.annotation` were removed from the JDK in 11.
**Fix:** add these as dependencies (the compat layer normally does this):
```xml
<dependency><groupId>javax.xml.bind</groupId><artifactId>jaxb-api</artifactId><version>2.3.1</version></dependency>
<dependency><groupId>org.glassfish.jaxb</groupId><artifactId>jaxb-runtime</artifactId><version>2.3.1</version><scope>runtime</scope></dependency>
<dependency><groupId>com.sun.activation</groupId><artifactId>javax.activation</artifactId><version>1.2.0</version><scope>runtime</scope></dependency>
<dependency><groupId>javax.annotation</groupId><artifactId>javax.annotation-api</artifactId><version>1.3.2</version></dependency>
```
**If the error happens during *annotation processing*** (you see `<annotationProcessorPaths>` in the
pom, e.g. MapStruct / JPA-metamodel projects, often JHipster): regular `<dependencies>` are **not**
on the processor path. Add the same `jaxb-api` + `javax.annotation-api` as `<path>` entries inside
`<annotationProcessorPaths>` too. (If the processor *itself* then NPEs, the processor is too old for
the JDK — see "Genuinely stuck".)

### maven-surefire NullPointerException on JDK 9+
**Symptom:** `maven-surefire-plugin:2.20.x/2.21.x … NullPointerException` at test start.
**Cause:** surefire ≤ 2.21 has a JDK 9+ bug. Usually pinned by an old `spring-boot-starter-parent` (< 2.2).
**Fix:** force surefire ≥ 2.22.2. If pinned in the pom, change the version; if inherited from a BOM,
add a property: `<maven-surefire-plugin.version>2.22.2</maven-surefire-plugin.version>`.

### Mockito "Cannot define class using reflection" / sun.misc.Unsafe
**Symptom:** `UnsupportedOperationException: Cannot define class using reflection`,
`Could not find sun.misc.Unsafe`, `NoSuchMethodException: sun.misc.Unsafe.defineClass`, `MockitoException`
(often followed by an `OutOfMemoryError` as the cascade).
**Cause:** old Mockito's shaded ByteBuddy used `sun.misc.Unsafe.defineClass`, removed in JDK 11.
**Fix:** bump Mockito (NOT byte-buddy — Mockito shades its own). A property bump won't work if it's
BOM-pinned; add an explicit override **before** the BOM import in `<dependencyManagement>`:
```xml
<dependency><groupId>org.mockito</groupId><artifactId>mockito-core</artifactId><version>2.23.4</version></dependency>
<dependency><groupId>org.objenesis</groupId><artifactId>objenesis</artifactId><version>3.2</version></dependency>
```
(If the project's tests use the Mockito 3/4/5 API, pick the matching newest patch instead of 2.23.4.)

### ASM / "Unsupported class file major version" (JDK 17 = 61, JDK 21 = 65)
**Symptom:** `ASM ClassReader failed to parse class file…`, `Unsupported class file major version 61/65`
(from Hibernate enhance plugin, Mockito, or a Spring Boot 2.x app).
**Cause:** a transitively-pinned ByteBuddy/ASM predates the new JDK.
**Fix (light):** add to `<dependencyManagement>` `net.bytebuddy:byte-buddy:1.14.12` and
`net.bytebuddy:byte-buddy-agent:1.14.12`. **If it's Spring's own component-scan ASM** (Spring 5.2.x,
i.e. Spring Boot 2.0/2.1), that override won't help — run `scripts/sb2_to_sb3.sh .` (Spring Boot 2→3,
which ships a modern ASM) or move Spring Framework to 5.3.latest, then re-run the bump.

### ArrayIndexOutOfBoundsException from a `<clinit>` (version-string parsing)
**Symptom:** `ArrayIndexOutOfBoundsException: Index 1 out of bounds for length 1` thrown from a static
initializer (e.g. `org.jadira.usertype` `JavaVersion.<clinit>`, or old **Hibernate Validator 5.x**
during `Configuration` init → "Failed to load ApplicationContext").
**Cause:** an old library parses `java.version` / `java.specification.version` expecting the legacy
`1.x` shape (`split(".")[1]`); on JDK 11 it's a single token (`11`).
**Fix:** make sure the build is **not** forcing `-Djava.version=<major>` (let the JVM report its real
version). If the culprit is Hibernate Validator 5.x, bump it (e.g. `hibernate-validator` 6.2.5.Final;
note 6.x is Bean Validation 2.0 — fine for Spring Boot 2.x, risky for 1.x).

### "Error injecting JarArchiver" / ExceptionInInitializerError at JarArchiver.<init>
**Symptom:** a Guice/Plexus provisioning error from `maven-jar/war/assembly` during a JDK-11 build.
**Cause:** an old build plugin's bundled `plexus-archiver` predates JDK 11.
**Fix:** bump the plugin (e.g. `maven-jar-plugin` ≥ 3.4.1), or add `org.codehaus.plexus:plexus-archiver:4.2.7`
to `<dependencyManagement>`.

### `com.sun:tools:jar` not found / `tools.jar` systemPath
**Symptom:** `Could not find artifact com.sun:tools:jar…`, or a `<systemPath>…/lib/tools.jar</systemPath>`
that no longer resolves under JDK 9+.
**Cause:** `tools.jar` was removed in JDK 9 (compiler APIs moved to the `jdk.compiler` module).
**Fix:** delete the `<dependency>` with `<artifactId>tools</artifactId>` + `<scope>system</scope>`.
If the code actually calls `com.sun.tools.javac.*` (e.g. google-java-format), instead add
`--add-exports jdk.compiler/com.sun.tools.javac.<pkg>=ALL-UNNAMED` to `maven-compiler-plugin`
`<compilerArgs>` **and** the surefire `<argLine>`, and use `<source>/<target>` (NOT `<release>`,
which forbids `--add-exports` to JDK-internal packages).

### Bean Validation: "no Bean Validation provider could be found"
**Symptom:** `javax.validation.ValidationException: Unable to create a Configuration, because no Bean
Validation provider could be found`.
**Cause:** the validation API is present but the provider (Hibernate Validator) was dropped.
**Fix:** add `org.hibernate.validator:hibernate-validator` (6.2.5.Final for javax-era; 8.0.1.Final for jakarta/SB3).

### OutOfMemoryError during tests
**Symptom:** `OutOfMemoryError: Java heap space`, many tests erroring (common in JHipster).
**Important:** this is **usually a downstream symptom**, not the cause — a repeated context-load
failure (e.g. the Mockito one above) leaks memory until the fork OOMs. **Fix the first real error in
the log first.** Only if it's genuinely heap (the context loads but the suite is large) raise the test
fork heap (`-Xmx`) in the surefire `<argLine>`.

### Spring Boot 1.x runtime won't start under JDK 11
**Symptom:** `EmbeddedServletContainerException`, `spring-boot-1.x` / `spring-context-4.x` in the stack,
bean-creation failures under the new JDK.
**Cause:** Spring Boot 1.x / Spring 4.x can't run on JDK 11.
**Fix:** `scripts/sb1_to_sb2.sh .` (Spring Boot 1.x → 2.7), commit, re-run the bump. **Caveat:** apps
with custom SB-1.x code that calls SB-2-removed APIs (e.g. WebGoat: `EmbeddedServletContainerFactory`,
`actuator.endpoint.mvc`, `thymeleaf.resourceresolver`) won't compile on SB2 — those need manual work (bail).

### Tests need Docker / Selenium / a real DB
**Symptom:** `Could not find a valid Docker environment`, Testcontainers/MariaDB4j/Selenium errors.
**Cause:** the test needs infra the box doesn't have. It **failed in the baseline too** → not a
regression. Ignore it; it's not in your baseline-pass set.

### Nested project (no `pom.xml` at the root)
The project is in a subdirectory. Run `find . -name pom.xml -not -path '*/target/*'`, `cd` into the
shallowest match, and run every step from there.

---

## 3. When to give up (bail honestly)

After running the bump and applying **every** matching fix, if it still won't compile or tests still
regress, stop and report which step failed + the unresolved `[ERROR]`. Known genuine bails:
- **Spring Boot 1.x app with custom code on SB-2-removed APIs** — needs a hand-written SB1→2 migration.
- **JHipster-8 app, recipe step fails with a cascade** (JAXB → `@Generated` → MapStruct/jpamodelgen
  NPE) — the annotation-processing stack is too old for JDK 11; the real fix is a JHipster/Spring Boot
  version upgrade, which is more than a one-LTS-step bump.
- **Source genuinely uses an API the JDK removed** that no recipe can rewrite.

Don't invent edits beyond the patterns above — an honest bail with the reason is more useful than a
green build that hides a dropped test.
