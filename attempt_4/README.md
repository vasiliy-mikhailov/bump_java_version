# Fitness spec for attempt_4 — staged migration

Carries items 1-8 from AGENTS.md as of attempt_3 wrap (see `attempt_3/FITNESS.md`), and adds item 9 below to govern attempt_4 specifically.

The motivation: attempt_3 plateaued at **151/271 = 56% build_post** on the single-jump recipe (Java 8/11/17 → 21 in one OpenRewrite pass, all under JDK 21). The dominant residual failure cluster — Lombok < 1.18.30 hitting `JCTree.qualid NoSuchFieldError` on JDK 21 — is a catch-22: OpenRewrite's LST parser needs Lombok to load, and Lombok needs an older JDK to load, so the recipe can never upgrade Lombok before parsing fails. Industry practice (Spring/Hibernate migration guides) is to stage version bumps; this attempt embraces that.

---

9. **Fitness (staged migration):** raise the corpus build-success rate above the single-jump declarative plateau by splitting the migration into per-source-Java-version stages, each running its OpenRewrite pass under a JDK the original source compiles against.
   - **Constraints:** declarative configuration deltas only, but split across N stage recipes (one per intermediate JDK target). Each stage's recipes and dependency versions must be compatible with that stage's Java version. Each stage's pom and source edits persist into the next stage's working tree. No custom Java AST recipes.
   - **Search:** for each stage, select recipes and pin dep versions that this JDK can actually execute. Ground every placement in upstream migration guides (Spring, Hibernate, Lombok release notes, JUnit/Mockito changelogs).
   - **Reward:** real `build_post 0 → 1` flips on the full corpus, net of regressions vs. attempt_3 iter-0 (151/271). A stage that un-breaks a catch-22 without flipping immediately counts only when the downstream stage realises the flip. Per-stage `mvn compile` under that stage's target JDK is the per-stage gate.
   - **Repeat:** stage-by-stage; if a stage's intermediate compile fails on most repos, the stage is too aggressive and must be tightened before the next is built.
