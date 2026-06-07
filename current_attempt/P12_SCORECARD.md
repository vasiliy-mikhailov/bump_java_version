# P12 scorecard — demand-driven bump PRs

Java-version bump PRs opened in response to open GitHub requests (P12), sourced from `bump_issues.json`.
One row per acted-on request. Each PR was verified with the repo's own CI command (`mvn verify`), not just `mvn test`.
Kept in sync as PRs are opened / merged / bailed.

## Opened PRs

| repo | ★ | issue | hop | what the skill did | tests | PR | status |
|---|---|---|---|---|---|---|---|
| citerus/dddsample-core | 5272 | [#180](https://github.com/citerus/dddsample-core/issues/180) | 17→21 | `java.version` + CI JDK | 128/128 | [#202](https://github.com/citerus/dddsample-core/pull/202) | open |
| carml/carml | 112 | [#193](https://github.com/carml/carml/issues/193) | 11→17 | pom (4 refs) + 4 CI workflows; surefire `--add-opens` + `AllowRedefinitionToAddDeleteMethods` for BlockHound | 336/336 | [#628](https://github.com/carml/carml/pull/628) | open (fork CI green) |
| ontodev/robot | 319 | [#935](https://github.com/ontodev/robot/issues/935) | 8→11 | +`jakarta.annotation-api`, `Paths.get`→`Path.of` (also unblocked the broken Java-8 build) | 171 green | [#1284](https://github.com/ontodev/robot/pull/1284) | open |
| tpiekarski/coupon-engine | 15 | [#5](https://github.com/tpiekarski/coupon-engine/issues/5) | 8→11 | jacoco 0.7.7→0.8.14, +`jakarta.inject-api`, `Path.of` | 40/40 | [#18](https://github.com/tpiekarski/coupon-engine/pull/18) | open |
| Quinimbus/CLI | 1 | [#35](https://github.com/Quinimbus/CLI/issues/35) | 21→25 | `maven.compiler.release` 21→25, maven-compiler-plugin 3.14.1→3.15.0, JDK 25 in 3 CI workflows | green | [#45](https://github.com/Quinimbus/CLI/pull/45) | open |
| simbo1905/shamir | — | [#1](https://github.com/simbo1905/shamir/issues/1) | 17→21 | compiler source/target→21, Guava 27.0.1→29.0-jre | 23/23 | [#3](https://github.com/simbo1905/shamir/pull/3) | open — maintainer running parallel PR #2 (their GraalNode Docker stage fails; our Maven build is green) |
| monodot/hello-java-spring-boot | — | [#6](https://github.com/monodot/hello-java-spring-boot/issues/6) | 11→17 | `java.version` 11→17, Dockerfile base `openjdk:11-jre-slim`→`eclipse-temurin:17-jre-slim` | no test lost | [#10](https://github.com/monodot/hello-java-spring-boot/pull/10) | open |
| ghusta/FakeSMTP | — | [#30](https://github.com/ghusta/FakeSMTP/issues/30) | 17→21 | `java.version` 17→21 + CI JDK | 13/13 | [#50](https://github.com/ghusta/FakeSMTP/pull/50) | open |
| sagar-arora/LogAgent | 5 | [#6](https://github.com/sagar-arora/LogAgent/issues/6) | 11→17 | compiler source/target 11→17 + CI JDK | 1/1 | [#13](https://github.com/sagar-arora/LogAgent/pull/13) | open |
| mars-sim/mars-sim | 164 | [#1956](https://github.com/mars-sim/mars-sim/issues/1956) | 21→25 | `maven.compiler.source`/`target` 21→25 + 4 CI workflows | 721/721 | [#1959](https://github.com/mars-sim/mars-sim/pull/1959) | **✅ MERGED** (maintainer: "thanks for the change") |
| agido-malter/logback-elasticsearch-appender | 24 | [#45](https://github.com/agido-malter/logback-elasticsearch-appender/issues/45) | 8→11 | compiler source/target→`release` 11 + CI JDK (gate=`mvn test`, the repo's CI; `verify` falsely fails on gpg-sign). Java-11 half of #45 | 24/24 | [#48](https://github.com/agido-malter/logback-elasticsearch-appender/pull/48) | open |
| agido-malter/logback-elasticsearch-appender | 24 | [#45](https://github.com/agido-malter/logback-elasticsearch-appender/issues/45) | — (refactor) | **companion to #48, _resolves #45_**: `HttpURLConnection`→`java.net.http.HttpClient` (connection pooling) + AWS SigV4 v1→**SDK v2**. Hand-written, not a bump — validated by new tests (SigV4 known-answer, 4 WireMock transport, userInfo→Basic e2e) | 30/30 | [#49](https://github.com/agido-malter/logback-elasticsearch-appender/pull/49) | open |
| rigd-loxia/builder-generator | 2 | [#36](https://github.com/rigd-loxia/builder-generator/issues/36) | 11→17 | compiler 11→17 (both modules) + maven-compiler-plugin 3.11→3.15 + **enforcer `EnforceBytecodeVersion` maxJdkVersion 11→17** (else it bans the project's own J17 annotations jar) + modernizer 1.11→1.17 | 45/45 | [#61](https://github.com/rigd-loxia/builder-generator/pull/61) | open |
| codeforkjeff/conciliator | 126 | [#34](https://github.com/codeforkjeff/conciliator/issues/34) | **11→17→21 (P14 multi-step)** | chained both hops + **Spring Boot 2.7.3→3.3.13 / javax→jakarta** (`UpgradeSpringBoot_3_3`, version-aligned recipes) + JaCoCo 0.8.8→0.8.12 + Dockerfile both stages 11→21. _resolves #34 fully_ | 39/39 | [#38](https://github.com/codeforkjeff/conciliator/pull/38) | open |
| thelastpickle/cassandra-reaper | 516 | [#1437](https://github.com/thelastpickle/cassandra-reaper/issues/1437) | **11→21 (P14 multi-step)** | compiler `release` 11→21 + enforcer `build.jdk.minimum` 11→21 + JaCoCo 0.8.6→0.8.12 + Mockito 4.4.0→5.14.2 (ByteBuddy/J21) + 2 Dockerfiles corretto 11→21. Dep `io.k8ssandra:datastax-mgmtapi-client-openapi` resolved from **GitHub Packages** (not Central); validated with **full `mvn install` incl. npm/webpack UI** | 516/516 | [#1687](https://github.com/thelastpickle/cassandra-reaper/pull/1687) | open |

## Bailed (no clean PASS → no PR, per P12 discipline)

| repo | issue | hop | reason |
|---|---|---|---|
| jdemetra/jdplus-main | [#863](https://github.com/jdemetra/jdplus-main/issues/863) | 21→25 | `maven-enforcer-plugin` fails even under JDK 21 — no green baseline to conserve |
| datastax/cassandra-data-migrator | — | 11→17 | Spark/**Scala** project — outside the skill's clean Java-Maven scope |
| s4u/api-java-samples | — | — | 0 tests — nothing to conserve |
| UKHomeOffice/MoPat | — | — | university-hosted dep `de.unimuenster.imi:org.cdisc.odm.v132` not resolvable from Central |
| sysprog21/shecc | — | — | author's GitHub-Packages libs (`net.filipvanlaenen:kolektoj`/`tsvgj`) not resolvable |
| nebula-contrib/ngbatis | — | 8→21 | **0 runnable unit tests** (tests need a live Nebula Graph DB) — nothing to conserve |
| ravindraAmbati/pet-clinic | [#96](https://github.com/ravindraAmbati/pet-clinic/issues/96) | 8→11 | `wro4j-maven-plugin` has a disjoint `org.webjars.npm:minimatch` version-range conflict (`[3.0.2,3.1)` vs `[3.1.1,4)`) — fragile web-resource build, not worth forcing for ★1 |

## Tally

- **15 PRs opened** across 14 repos (incl. one hand-written tested HttpClient/AWS-v2 refactor and two **P14 multi-step** PRs: conciliator 11→21 w/ Spring Boot 2→3/jakarta, and cassandra-reaper ★516 11→21 w/ GitHub-Packages dep + full-`mvn install` UI validation), all 4 LTS hops covered, every bump verified green under the repo's own CI command.
- **`detect_jv` finding** (from recovering cassandra-reaper, per the operator's "j11-gift" insight): the feed reads the compiler `source`/`target` (which projects set to an *old* version for bytecode compat) instead of the real build floor (enforcer `requireJavaVersion` / `release` / CI JDK), so multi-step requests can be mis-routed with a phantom extra hop. Fix candidate for P4: honor the enforcer floor when present.
- **1 MERGED** (the primary reward — ground-truth adoption): `mars-sim/mars-sim` #1959 (21→25), merged by the maintainer with thanks. First demand PR landed.
- **5 bailed** on P12 discipline (no green baseline / out of scope / unresolvable deps).
- _Reward = merged PRs (primary)._ The feed's clean, resolvable tail is largely exhausted; re-run `find_bump_issues.py` later for fresh demand rather than grinding low-yield targets.
