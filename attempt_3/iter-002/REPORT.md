# attempt_3 iter-2: null result, deferred to attempt_4 (staged)

## Approach attempted

Added section 9 to recipe: `UpgradeDependencyVersion` for org.projectlombok:lombok and org.mapstruct:mapstruct(-processor) targeting JDK 21 compatibility.

Patched `scripts/run_one_repo.sh` to:
- pre-bump hardcoded Lombok versions via sed before mvn invocation
- pass `-Dmaven.compiler.proc=none` to rewrite:run so OpenRewrites LST parser wouldnt invoke Lombok annotation processing.

## Smoke result

3 known Lombok-broken repos (hibernate-5__j11__15, jakarta-ee-javax__j11__23, spring-boot-2__j17__20): 0/3 flipped. JCTree.qualid NoSuchFieldError still hit during the rewrite:run phase even with `-Dmaven.compiler.proc=none`. Either OpenRewrites parser ignores that flag or the LST scanner spawns its own javac context that loads Lombok regardless.

## Why this doesnt cleanly work in a single-image setup

OpenRewrites LST construction phase needs to load source through javac to build type bindings. Annotation processors in the projects build classpath get loaded into javacs ProcessingEnvironment automatically. `maven.compiler.proc=none` is a maven-compiler-plugin property that doesnt propagate to the OpenRewrite plugin invocation.

Real workarounds documented online require either:
- Excluding Lombok from the OpenRewrite plugin classpath (only fixes Lombok-only issue, leaves source unparseable)
- Running OpenRewrite on JDK 17 first (Lombok 1.18.20 works there) then re-running source-level recipes on JDK 21 — the staged path.

Reverted runner patches; iter-2 closed as null.

## Pivot

Per user direction: staged migration (J8/11 -> J17 -> J21) becomes attempt_4 — three docker images, three sequential rewrite passes, each on a JDK the original source can compile under. Realistic target: 75-85% build_post.
