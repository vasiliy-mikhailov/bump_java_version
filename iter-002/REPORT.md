# Iter-2 report (5-repo smoke)

## Seed change vs iter-1

Two mutations on top of iter-1's seed:
- **ADD** `org.openrewrite.java.migrate.UpgradeJavaVersion` (with `version: 21`) at the head — intent: pull pom `<source>/<target>` up before any other recipe runs.
- **ADD** `org.openrewrite.java.spring.framework.UpgradeSpringFramework_6_1` between `JakartaEE10` and `UpgradeSpringBoot_3_3` — intent: handle the Spring-framework-only repos so the Boot recipe doesn't add Boot-only imports to them.

Bug uncovered on first launch: bare `UpgradeJavaVersion` (no options) NPEs the plugin (`"v" is null`), the recipe never runs, every "win" becomes a compat-flag salvage. Fixed by switching the YAML to object form `UpgradeJavaVersion: {version: 21}` and updating the renderer to `yaml.safe_dump` instead of a manual string join.

## Outcomes (5 repos)

| repo | base | post | rc | applied | diff lines | Qwen.overall | notes |
|------|:---:|:---:|:---:|:---:|---:|:---:|------|
| **hjl-j17-2** (spring-petclinic, J17, mostly-modern) | ✓ | ✓ | 0 | ✓ |   37 | **4** | clean, narrow scope: `<java.version>` bumped to 21, `List.getFirst()` in test asserts |
| **hjl-j8-3** (eladmin, J8 + Hibernate/Lombok) | ✓ | ✗ | 0 | ✓ | **6789** | **4** | huge migration: javax→jakarta, Swagger→OpenAPI 3, text blocks, `String.formatted`, `instanceof` pattern matching, `List.getFirst()`. Build fails on missing Lombok-generated symbols. |
| **jakarta-j17-3-CAVEAT** (spring-framework-petclinic, J17) | ✓ | ✗ | 0 | ✓ | 381 | **4** | same as iter-1: Java 21 + Spring 6.1 + Hibernate 6.5 + JakartaEE10 deps, ctor injection, `SpringJUnitConfig`. Build fails on stray `DependsOnDatabaseInitialization` import added by a Boot sub-recipe |
| **sb2-j11-1** (spring-petclinic-reactive, J11, Boot 2) | ✓ | ✗ | 0 | ✓ | 1351 | **4** | Boot 2.3→3.x, `@Serial`, security DSL lambdas, javax→jakarta. Build fails on Springfox classes not migrated (`Docket`, `ApiInfo`); SpringFox→SpringDoc transform didn't fire. |
| **jakarta-j8-1** (javaee7-samples, J8, source=7 poms) | ✗ | ✓ | 1 | ✓ | **0** | **1 (empty)** | persistent fake-win: source=7 stops baseline; recipe can't parse; post-build "passes" via compat flag |

**Aggregate:** mean Qwen.overall = **4.00** across 4 honest evaluations, 1 fake correctly tagged. `build_post` pass rate among honest: **1/4 = 25 %**.

## What changed vs iter-1 (3 shared repos)

| repo | iter-1 | iter-2 | observation |
|------|--------|--------|------------|
| jakarta-j17-3-CAVEAT | post=0, Qwen 4 | post=0, Qwen 4 | identical 381-line diff. UpgradeJavaVersion + UpgradeSpringFramework_6_1 didn't fix the stray Boot import. |
| sb2-j11-1            | post=0, Qwen 4 | post=0, Qwen 4 | same 1351-line diff. Springfox→SpringDoc still incomplete. |
| jakarta-j8-1         | fake win, Qwen 1 | fake win, Qwen 1 | source=7 still blocks baseline (UpgradeJavaVersion runs *via* maven, so if baseline pom is unparseable, recipe can't fire). |

So **iter-2's two mutations were null effects on the 3 carried-over repos**. The mutations did unlock 2 new honest 4/5s on hjl-j8-3 and hjl-j17-2 (these weren't in iter-1's smoke), but didn't break or fix anything for the shared trio.

## Concrete iter-3 mutations (Claude-reasoned + Qwen-suggested)

Each failing repo has a *specific* missing recipe identified from the build error:

1. **jakarta-j17-3-CAVEAT** — `cannot find DependsOnDatabaseInitialization` (Boot-only class added to a non-Boot project)
   - **ADD** `org.openrewrite.java.spring.boot3.RemoveDependsOnDatabaseInitialization` (if present in `rewrite-spring`).
   - If not present, **REMOVE** `UpgradeSpringBoot_3_3` from non-Boot project paths. Better fix: gate Boot recipes by detected `<spring-boot.version>`.

2. **sb2-j11-1** — `package springfox.documentation does not exist`; `Docket`, `ApiInfo` symbols missing.
   - **ADD** `org.openrewrite.java.spring.doc.MigrateSpringFoxToSpringDoc` (or `org.openrewrite.java.spring.boot3.MigrateSpringFoxToSpringDoc` — exact ID needs verification).

3. **hjl-j8-3** — `cannot find getPort()`, `getName()`, `log` (Lombok-generated symbols vanished on JDK 21).
   - **ADD** `org.openrewrite.java.migrate.lombok.LombokBestPractices` to upgrade Lombok to a JDK-21-compatible version.
   - Already in pool but not in seed; promoting it.

4. **jakarta-j8-1** — pom uses `source=7`; baseline fails before recipe runs.
   - **DROP** from dataset (violates fitness #6 "baseline-buildable in container"). Replace with another EE 7 repo whose poms use source=8+.

## Iter-3 planned seed

```yaml
seed:
  - org.openrewrite.java.migrate.UpgradeJavaVersion: { version: 21 }
  - org.openrewrite.java.migrate.jakarta.JakartaEE10
  - org.openrewrite.java.migrate.lombok.LombokBestPractices       # NEW
  - org.openrewrite.java.spring.framework.UpgradeSpringFramework_6_1
  - org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3
  - org.openrewrite.java.spring.boot3.MigrateSpringFoxToSpringDoc # NEW
  - org.openrewrite.hibernate.MigrateToHibernate62
  - org.openrewrite.java.testing.junit5.JUnit4to5Migration
  - org.openrewrite.java.testing.mockito.MockitoBestPractices
  - org.openrewrite.java.migrate.UpgradeToJava21
  - org.openrewrite.java.RemoveUnusedImports
```

Plus the dataset edit removing `jakarta-j8-1` (or replacing it with a source-8 EE 7 sample).
