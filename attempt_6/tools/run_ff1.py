"""ff #1 composer: produces attempt_N/recipe.yaml — a per-jv_to map of recipe lists.

Iteration 0 (current): emits the baseline composition {UpgradeToJava<jv_to>} per jv_to,
which OpenRewrite chains transitively to handle multi-step jumps.

Iteration 1+ (future): reads intent_samples/<slug>/breaking.json (item 3 ground truth)
and recipe_samples/<slug>/breaking.json (item 4 mirror), computes per-stage only_human
sets, proposes additions whose published behaviour matches missed intents.
"""
import os, sys, json, argparse

HERE = "/home/vmihaylov/java_8_11_17_to_java_21"
ATTEMPT_DIR = f"{HERE}/attempt_6"

# OpenRewrite recipe targeting each jv_to. Names verified against
# rewrite-migrate-java:3.12.0 META-INF/rewrite/java-version-*.yml.
BASELINE = {
    11: ["org.openrewrite.java.migrate.Java8toJava11"],
    17: ["org.openrewrite.java.migrate.UpgradeToJava17"],
    21: ["org.openrewrite.java.migrate.UpgradeToJava21"],
}


def iter0_compose():
    """First-iteration baseline: per-jv_to single recipe matching the target version."""
    return BASELINE


def emit_recipe(composition, path):
    """Write composition as YAML to `path`. Format: '<jv_to>:\\n  - <recipe name>' lines."""
    lines = [
        "# Emitted by ff #1 composer.",
        "# Format: per-jv_to list of OpenRewrite recipe class names; ff #4 applies them as one composed recipe per stage.",
        "",
    ]
    for jv_to in sorted(composition):
        lines.append(f"{jv_to}:")
        for r in composition[jv_to]:
            lines.append(f"  - {r}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iter", type=int, default=0, help="Iteration number (0 = baseline)")
    args = parser.parse_args()

    if args.iter != 0:
        print(f"iter {args.iter} composer not implemented yet (needs item 4 recipe_samples).", file=sys.stderr)
        sys.exit(2)

    composition = iter0_compose()
    out = f"{ATTEMPT_DIR}/recipe.yaml"
    emit_recipe(composition, out)
    print(f"emitted {out}")
    print(open(out).read())


if __name__ == "__main__":
    main()
