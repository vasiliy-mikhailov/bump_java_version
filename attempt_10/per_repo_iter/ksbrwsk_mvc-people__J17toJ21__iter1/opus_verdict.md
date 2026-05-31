# Claude+Opus verdict — ksbrwsk_mvc-people__J17toJ21
VERDICT: UNFIXABLE-baseline-broken
- baseline JDK17 mvn compile (jv_from=17) FAILS: [ERROR] Non-resolvable import POM: The following artifacts could not be resolved: io.micrometer:micrometer-bom:pom:2.0.0
- No valid baseline to preserve -> not a migration target; exclude per D4 / relabel BASELINE_DOES_NOT_COMPILE. Rung-1 judgment, no qwen/oh run needed.
