---
name: bump-java-8-to-11
description: Emit the rewrite.yml that migrates a Maven or Gradle project from Java 8 to Java 11 — an OpenRewrite declarative composite recipe whose recipeList the harness runs, then scores. Use for an 8→11 Java LTS bump.
---

# Java 8 → 11 — emit a `rewrite.yml`

You output **one executable `rewrite.yml`** — an OpenRewrite declarative composite recipe (`name: com.bjv.Bump`)
whose **`recipeList`** is the ordered recipe sequence the harness runs (one `mvn rewrite:run` / `gradle rewriteRun`),
then scores. You run nothing, edit nothing — a `rewrite.yml` can only list recipes, so a hand-edit is impossible.

The "intents" are recipes too:
- **set target → 11** → `org.openrewrite.java.migrate.UpgradeJavaVersion` with `version: 11`.
- **bump Gradle wrapper** (only if below the JDK-11 floor 5.0) → `org.openrewrite.gradle.UpdateGradleWrapper` with `version: "7.6"`.

Every recipe FQN must be in the catalog and resolvable in the **offline** mirror. **Done** = tests still pass under
11, effective compiler target == 11, no known CWEs. A wall no recipe covers → emit a **bail** (bottom).

## Default `rewrite.yml`
```yaml
type: specs.openrewrite.org/v1beta/recipe
name: com.bjv.Bump
recipeList:
  - org.openrewrite.java.migrate.Java8toJava11        # the 8→11 meta: EE re-adds, surefire/plugin bumps, compiler level
  - org.openrewrite.java.migrate.UpgradeJavaVersion:  # force source/target/<java.version> = 11 (parent-property safe)
      version: 11
```
`Java8toJava11` re-adds the EE modules removed in JDK 11 (`jaxb-api`/`jaxb-runtime` 2.3.1, `javax.activation` 1.2.0,
`javax.annotation-api` 1.3.2, `jaxws-api`), removes any `--add-modules java.xml.bind/java.se.ee` stopgap, floors
surefire ≥ 2.22.2, and bumps old `maven-jar/assembly` plexus-archiver — don't add ops for those.

## Add to `recipeList` (or bail) when the build reveals a wall — the package/version comes from the error
| Symptom (at build under 11) | What to add |
|---|---|
| `EmbeddedServletContainerException` / `spring-context-4.x` (Spring Boot **1.x** can't run on 11) | `org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7`. *Custom SB-1.x code on SB-2-removed APIs → won't compile → bail.* |
| `package <internal> is not visible` — the project's OWN source imports a JDK-internal package encapsulated in JDK 9+ (`java.awt.peer`, `sun.security.x509`, `sun.security.tools.keytool`, `sun.misc.*`, …) | needs `--add-exports <module>/<package>=ALL-UNNAMED` per package (map: `java.awt.peer→java.desktop`, `sun.security.*`/`sun.misc.*→java.base`). **No clean OpenRewrite recipe adds a compiler `--add-exports`** → **bail `I_MADE_MANUAL_EDIT`** unless the operator has added an `add_exports` intent. |
| `com.sun.tools.javac.*` source use (compiler internals) | no recipe rewrites this → **bail `I_MADE_MANUAL_EDIT`**. |
| `ArrayIndexOutOfBoundsException` from a `<clinit>` (Jadira / a lib's `java.version` parser, JEP-223) | a fixed lib version in the mirror → `UpgradeDependencyVersion`; if none → **bail `ABANDONED_DEP`**. |

## Bail labels (emit instead of improvising)
- `RECIPE_PATH_UNREACHABLE` — a recipe artifact doesn't resolve in the mirror.
- `CWE_UNFIXABLE_OFFLINE` — a resolved dep has a known CWE and no fixed version is in the mirror.
- `I_MADE_MANUAL_EDIT` — a wall needs a change no catalog recipe provides (compiler `--add-exports` for internal-package use, `com.sun.tools.javac.*` source, an abandoned dep with no JDK-11 release).
