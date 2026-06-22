#!/usr/bin/env python3
"""Static analysis of the generated rewrite.yml. NO allow-list / catalog — every OpenRewrite recipe is
permitted. The reward instead penalizes injected work: a model-CHOSEN parametric recipe counts ×0.9 (like a
manual edit), while unparametrized meta-recipes and the hop-FIXED intents (UpgradeJavaVersion{version=to},
UpdateGradleWrapper{version=pinned}) are free. This script validates structure + the two intents' fixed
params, and prints the count of model-chosen parametric recipes for the scorer.
Usage: check_program.py <rewrite.yml> [<ignored_catalog>] [<jv_to>]   -> "OK PARAMETRIC=<n>" | "VIOLATION ..."; exit 0/1
"""
import sys, re
y = open(sys.argv[1]).read()
TO = sys.argv[3] if len(sys.argv) > 3 else None          # argv[2] kept for call-site compat (ignored)
PINNED = {"11": "7.6", "17": "7.6", "21": "8.10.2", "25": "9.0.0"}
FREE_INTENTS = {"UpgradeJavaVersion", "UpdateGradleWrapper"}   # parametric but hop-fixed -> free
v = []
if "specs.openrewrite.org/v1beta/recipe" not in y or "recipeList:" not in y:
    v.append("not a rewrite.yml composite recipe (missing type/recipeList)")
# recipeList items: "- FQN:" => carries params ; "- FQN" => unparametrized
param_items = re.findall(r"^\s*-\s*([A-Za-z][\w.]+\.[A-Z]\w+)\s*:\s*$", y, re.M)
plain_items = re.findall(r"^\s*-\s*([A-Za-z][\w.]+\.[A-Z]\w+)\s*$", y, re.M)
if not (param_items or plain_items):
    v.append("recipeList has no recipe FQNs")
# the two free intents must carry their hop-FIXED value (else they're not the free intent / are just wrong)
for m in re.finditer(r"UpgradeJavaVersion\s*:\s*\n\s*version:\s*['\"]?(\d+)", y):
    if TO and m.group(1) != TO: v.append(f"UpgradeJavaVersion version {m.group(1)} != jv_to {TO}")
for m in re.finditer(r"UpdateGradleWrapper\s*:\s*\n(?:\s+\w+:.*\n)*?\s*version:\s*['\"]?([\d.]+)", y):
    if TO and m.group(1) != PINNED.get(TO): v.append(f"UpdateGradleWrapper version {m.group(1)} not the pinned {PINNED.get(TO)}")
# model-chosen parametric recipes = items with params, minus the hop-fixed free intents
parametric = [f for f in param_items if f.rsplit(".", 1)[-1] not in FREE_INTENTS]
if v:
    print("\n".join("VIOLATION " + x for x in v)); sys.exit(1)
print(f"OK PARAMETRIC={len(parametric)}")
sys.exit(0)
