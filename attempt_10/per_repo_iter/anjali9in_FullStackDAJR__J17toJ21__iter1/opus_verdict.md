# anjali9in_FullStackDAJR__J17toJ21 — verdict: FIXABLE (PASS at all rungs)

- Opus rung (deterministic sb3_smoke.py): PASS — SB2->SB3.3 + bump -> JDK21 compile+test pass.
- OH+Qwen rung (clean workdir /tmp/anjali_oh, 178.6s, 50 events): PASS. pom 17->21, JDK21 compile rc=0, JDK21 test 1/1 pass (matches BASELINE_PASS contextLoads).
- REAL blocker was NOT the SB2 BOM per se: it was Byte Buddy too old ("Java 21 (65) is not supported by the current version of Byte Buddy") pulled by hibernate-enhance-maven-plugin. Agent fixed it SURGICALLY by adding net.bytebuddy:byte-buddy:1.14.12 + byte-buddy-agent:1.14.12 to that plugins deps. sb2_to_sb3.sh NOT needed for this repo.
- Reclassify: FIXABLE via surgical Byte Buddy pin (lighter than full SB3). SB3 recipe remains valid for genuinely BOM-blocked repos.
