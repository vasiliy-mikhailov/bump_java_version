# attempt_2 iter-4 — custom composite: +1 honest build_post gain

## Mutation
Composed 6 custom recipe primitives onto the champion to address the diagnosed root causes from iter-0..3 analysis:
1. `UpgradeDependencyVersion` for `org.hibernate:hibernate-core` (+ `.orm`) → 6.x
2. `ChangeDependency` for `hibernate-entitymanager` → `hibernate-core`
3. `ChangeDependency` for `springfox-boot-starter` → `springdoc-openapi-starter-webmvc-ui`
4. `RemoveDependency` for `springfox-swagger2` / `springfox-swagger-ui`
5. `ChangeDependency` + `ChangePackage` for `thymeleaf-spring4` → `thymeleaf-spring6`
6. `AddDependency` for `spring-boot-starter-validation` when `@Valid` is used
7. `UpgradePluginVersion` for `spring-boot-maven-plugin` → 3.3.x
8. Added `WebSecurityConfigurerAdapter` + `UpgradeSpringSecurity_6_0` recipes

## Result vs iter-0 (champion)

| metric | iter-0 | iter-4 | delta |
|--------|------:|------:|------:|
| mean Qwen overall | 3.15 | 3.16 | +0.01 |
| **build_post pass** | **46/96** | **47/96** | **+1** |
| empty diffs | 9 | 9 | 0 |
| recipe_rc=0 | 87 | 87 | 0 |

## Trajectory

| iter | mutation | mean Q | build_post |
|-----:|----------|------:|----------:|
| 0 | champion baseline | 3.15 | 46/96 |
| 1 | + SpringFoxToSpringDoc | 3.11 | 46/96 |
| 2 | + ReplaceSpringFoxDependencies + SpringFoxToSpringDoc | 3.12 | 46/96 |
| 3 | swap MigrateToHibernate62 → 63 | 3.14 | 46/96 |
| 4 | custom composite (6 primitives) | 3.16 | **47/96** |

## The one flip
`spring-boot-2__j8__2` (net-guides/springboot2-crud) went `build_post 0 → 1`. Diff inspection shows the difference: iter-4 added a `<dependency>` block for `spring-boot-starter-validation`, which the `AddDependency.onlyIfUsing: javax.validation.Valid` clause inserted because the source uses `@Valid` annotations. iter-0 produced a clean `javax → jakarta` source migration but never added the validation starter, so the `jakarta.validation` package wasn't on the classpath and the build failed. Iter-4's conditional dep injection fixed it.

That's exactly the diagnosed root cause — and the recipe primitive that targets it works.

## What didn't move and why

The other 5 mutations had effect (recipe_rc=0 same 87/96, diff sizes shifted), but didn't flip any other build_post=0 → 1. Looking at specific failed repos:
- The Hibernate UpgradeDependencyVersion ran where applicable, but `8/hibernate-5__j8__1` etc. don't declare `hibernate-core` directly (they get it transitively via spring-boot-starter-data-jpa), so the primitive had no target.
- The Springfox `RemoveDependency` fires only when `springfox-swagger2` is declared by exact coordinate — many real-world poms use `springfox-boot-starter` or `springfox-spring-web` instead.
- The Thymeleaf swap fires only when `thymeleaf-spring4` is in the pom, but the failing `8/hibernate-5` repos used `thymeleaf` (un-suffixed) with a transitive spring4 binding.
- The `spring-boot-maven-plugin` plugin version is in fact already bumped by `UpgradeSpringBoot_3_3`; the remaining `2.5.6:repackage` failures are projects where Boot's repackage goal fails on the *content* (missing main class or AOT issues), not the plugin version.
- `WebSecurityConfigurerAdapter` recipe fired where applicable (rewrote class bodies in a few repos, modest Qwen lift on 17/jakarta-ee-javax: +0.25) but the cells that depend on it didn't change build_post.

## What this proves
- The Qwen + dataset-baseline-verified design **caught the iter-1/iter-3 fake wins immediately** (empty_diff signal). It also confirms iter-4's gain is real (87/96 recipe_rc=0, real diff growth, exact trace from `@Valid` → `spring-boot-starter-validation`).
- The 50 failures aren't a homogeneous set fixable by catalog or simple-composite recipes. They have repo-specific root causes that would need ~50 distinct OpenRewrite recipes (or hand-patches) to flip.
- The community confirms this honestly — the SpringFoxToSpringDoc recipe page itself says `Docket → OpenAPI is too complex to be adequately handled in a recipe`, and rewrite-hibernate issue #30 acknowledges the same incomplete-rewrite problem I diagnosed.

## Final champion: iter-4
+1 build_post, mean Qwen essentially unchanged. The custom composite is the new champion. Further gains require repo-specific custom recipes (one per still-failing repo's root cause), which is real engineering, not catalog composition.
