"""Estimate the per-jv_to pass-rate lift each candidate recipe addition would yield.

For each suggested recipe + the missed-intent clusters it would address, count:
- stages where any of those clusters appear in only_human
- of those, stages currently NOT FULL_PASS
The second count is the upper-bound impact: addressable failures.
"""
import os, json, collections, re

BASE = "/home/vmihaylov/java_8_11_17_to_java_21/attempt_6"
INTENT = f"{BASE}/intent_samples"
RECIPE = f"{BASE}/recipe_samples"
FF4 = f"{BASE}/ff4_results.json"


def stage_jv(slug):
    m = re.search(r"__J(\d+)toJ(\d+)$", slug)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def kind_sig(atom):
    k = (atom.get("kind") or "").lower()
    return re.sub(r"[_\d]+$", "", k) or "?"


def load_atoms(base, slug):
    p = os.path.join(base, slug, "breaking.json")
    if not os.path.exists(p): return None
    try: d = json.load(open(p))
    except: return None
    return [a for v in (d.get("by_file") or {}).values() for a in v]


# Suggested recipes and the cluster signatures they're expected to address.
# Signatures must match what kind_sig() produces (lowercase, trailing _NN stripped).
SUGGESTIONS = {
    21: [
        {
            "recipe": "org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3",
            "addresses": {"javax_to_jakarta_migration", "javax_to_jakarta_namespace_migration",
                          "spring_boot_upgrade", "dependency_migration",
                          "springfox_to_springdoc", "spring_security_api_migration"},
            "confidence": "high",
        },
        {
            "recipe": "org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta9",
            "addresses": {"javax_to_jakarta_migration", "javax_to_jakarta_namespace_migration"},
            "confidence": "high — overlaps with SB3 but safe to chain",
        },
    ],
    17: [
        {
            "recipe": "org.openrewrite.java.migrate.UpgradeMySQLConnectorJVersion",
            "addresses": {"update_mysql_driver", "mysql_driver_upgrade"},
            "confidence": "medium — exact name unverified",
        },
    ],
    11: [
        {
            "recipe": "io.quarkus.updates.core.quarkus30.RemovedSubstrateTest",
            "addresses": {"replace_deprecated_test_annotation"},
            "confidence": "low — requires adding io.quarkus.updates to recipe coordinates",
        },
    ],
}


def stage_outcome(x):
    """Classify a stage result from ff4_results.json."""
    if x.get("error"): return "error"
    if x.get("build_pre") is False: return "pre_fail"
    if x.get("tests_pre") is False: return "tests_pre_failed"
    if x.get("build_post") is False: return "build_post_failed"
    if x.get("tests_post") is False: return "recipe_broke_tests"
    if x.get("build_post") and (x.get("tests_post") in (True, None)): return "FULL_PASS"
    return "incomplete"


def main():
    # Load ff4 results indexed by (repo, sha_from)
    if not os.path.exists(FF4):
        print("no ff4_results.json yet"); return
    ff4 = json.load(open(FF4))
    by_stage = {}
    for x in ff4:
        slug = x["repo"].replace("/", "_") + f"__J{x['jv_from']}toJ{x['jv_to']}"
        by_stage[slug] = x

    # Per stage, compute only_human breaking signatures
    per_jv_stages = collections.defaultdict(list)  # jv_to -> [(slug, outcome, only_human_sigs)]
    for slug in sorted(os.listdir(INTENT)):
        jv_from, jv_to = stage_jv(slug)
        if jv_to is None: continue
        h = load_atoms(INTENT, slug)
        r = load_atoms(RECIPE, slug)
        if h is None or r is None: continue
        recipe_sigs = {kind_sig(a) for a in r}
        only_human = {kind_sig(a) for a in h if kind_sig(a) not in recipe_sigs}
        x = by_stage.get(slug)
        outcome = stage_outcome(x) if x else "no_ff4"
        per_jv_stages[jv_to].append((slug, outcome, only_human))

    print("=" * 78)
    print("Current pass rate per jv_to (FULL_PASS = build_pre + tests_pre + recipe + build_post + tests_post)")
    print("=" * 78)
    for jv_to in sorted(per_jv_stages):
        stages = per_jv_stages[jv_to]
        full_pass = sum(1 for _, o, _ in stages if o == "FULL_PASS")
        total = len(stages)
        pct = 100 * full_pass / total if total else 0
        outcomes = collections.Counter(o for _, o, _ in stages)
        print(f"  J->{jv_to}: {full_pass}/{total} = {pct:.0f}%  ({dict(outcomes)})")
    print()

    print("=" * 78)
    print("Suggested recipe additions and their potential impact")
    print("=" * 78)
    for jv_to, suggestions in SUGGESTIONS.items():
        if jv_to not in per_jv_stages: continue
        stages = per_jv_stages[jv_to]
        total = len(stages)
        full_pass_now = sum(1 for _, o, _ in stages if o == "FULL_PASS")
        for s in suggestions:
            rec = s["recipe"]
            addr = s["addresses"]
            matching_stages = [(slug, o) for slug, o, missed in stages if missed & addr]
            n_match = len(matching_stages)
            n_match_failing = sum(1 for _, o in matching_stages if o != "FULL_PASS")
            potential_new_pass = full_pass_now + n_match_failing
            lift_pct = 100 * n_match_failing / total if total else 0
            print(f"\n  jv_to=J{jv_to}  {rec}")
            print(f"    confidence: {s['confidence']}")
            print(f"    addresses: {sorted(addr)}")
            print(f"    stages where any addressed cluster is missed: {n_match}/{total}")
            print(f"    of those, currently NOT FULL_PASS:           {n_match_failing}")
            print(f"    potential pass-rate lift: +{lift_pct:.0f}pp  ({full_pass_now}/{total} → {potential_new_pass}/{total} = {100*potential_new_pass/total:.0f}%)")
            if matching_stages[:5]:
                print(f"    example targets:")
                for slug, o in matching_stages[:5]:
                    print(f"      [{o:>20s}] {slug}")


if __name__ == "__main__":
    main()
