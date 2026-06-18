---
name: bump-java-8-to-11
description: Emit the conversion program to migrate a Maven or Gradle project from Java 8 to Java 11 — an ordered list of unparametrized OpenRewrite recipes + predefined intents that the harness applies and scores. Use for an 8→11 Java LTS bump.
---

# Java 8 → 11 — emit a recipe+intent program

You output an **ordered conversion program** (a list of ops); the harness applies and scores it. You run nothing,
edit nothing. Two op types only:
- **`recipe`** — `{env: from|to, fqn}`, one *unparametrized* OpenRewrite recipe FQN from the catalog below.
- **`intent`** — `set_target` (set source/`release`/toolchain → **11**) | `bump_wrapper` (Gradle wrapper → **7.6**).

Nothing else is expressible — no hand-edit, no `skipTests`, no test deletion. A wall no recipe/intent covers →
emit a **bail** (bottom). Offline Maven mirror + frozen CWE snapshot; every FQN/version you name must exist in it.
**Done** = previously-passing tests still pass under 11, effective compiler target == 11, no known CWEs.

## Default program
- **Maven:** `recipe to org.openrewrite.java.migrate.Java8toJava11` (the single 8→11 meta-recipe — re-adds the
  removed Java-EE modules, floors surefire, bumps build plugins, sets the compiler version).
- **Gradle:** `intent set_target` (→11); add `intent bump_wrapper` only if the wrapper predates **5.0** (JDK-11 floor).

## What `Java8toJava11` restores (recognition — the recipe applies it; don't add separate ops)
- **Java-EE modules removed in JDK 11**: `jaxb-api` + `jaxb-runtime` (2.3.1), `javax.activation` (1.2.0),
  `javax.annotation-api` (1.3.2), `jaxws-api` (2.3.1). And it **removes** any `--add-modules java.xml.bind/java.se.ee/java.activation` stopgap (those modules are gone — the flag fails).
- **`maven-surefire-plugin` ≥ 2.22.2** (≤2.21 NPEs on JDK 9+); old `maven-jar/assembly` plexus-archiver bumped.

## Walls → the op to add (else bail)
| Symptom | Op to emit |
|---|---|
| `EmbeddedServletContainerException` / `spring-context-4.x` / SB 1.x bean failures (1.x can't run on JDK 11) | `recipe from org.openrewrite.java.spring.boot2.UpgradeSpringBoot_2_7` (run under 8 where it still compiles). *App with custom SB-1.x code on SB-2-removed APIs → won't compile on SB2 → bail.* |
| `package javax.xml.bind does not exist` during the recipe run | emit the recipe with `env: from` (compiles under 8), then continue. |
| `com.sun:tools` / `tools.jar` systemPath (removed in JDK 9) | covered by `Java8toJava11`; if code uses `com.sun.tools.javac.*` and no recipe rewrites it → **bail**. |
| `ArrayIndexOutOfBoundsException` from a `<clinit>` (Jadira / a lib's own `java.version` parser, JEP-223) | a fixed lib version must be in the mirror; if none → **bail `ABANDONED_DEP`**. |
| `no Bean Validation provider` (often a benign DEBUG line) | if tests pass it's cosmetic — conserve; else no unparametrized recipe adds an impl → **bail**. |

## Bail labels (emit instead of improvising)
- `RECIPE_PATH_UNREACHABLE` — a named recipe artifact doesn't resolve in the mirror.
- `CWE_UNFIXABLE_OFFLINE` — a resolved dep has a known CWE and no fixed version is in the mirror.
- `I_MADE_MANUAL_EDIT` — a wall needs a change no catalog recipe / intent provides (e.g. SB-1.x app on removed APIs, `com.sun.tools.*` source use, an abandoned dep with no JDK-11 release).
