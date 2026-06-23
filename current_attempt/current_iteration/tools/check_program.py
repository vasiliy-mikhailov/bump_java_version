#!/usr/bin/env python3
"""Static analysis of the generated rewrite.yml. NO allow-list / catalog — every OpenRewrite recipe is
permitted. The reward penalizes INJECTED, model-CHOSEN work: a parametric recipe whose args the model picked
for THIS project counts ×0.9 (like a manual edit). FREE = unparametrized meta-recipes + the hop-FIXED intents
(deterministic, auditable, same constant for every repo on the hop): set-target to jv_to (UpgradeJavaVersion,
or per-module ChangePropertyValue of the compiler props), pinned Gradle wrapper, force annotation processing
(maven.compiler.proc=full), and the JDK-pinned tool floors (Lombok / ByteBuddy / Mockito / JaCoCo to the
class-file-version-capable constant). A free intent is credited ONLY when it carries its exact hop-fixed value
(a different value => model-chosen => still parametric), so an arbitrary edit cannot launder through it.
Usage: check_program.py <rewrite.yml> [<ignored>] [<jv_to>]   -> "OK PARAMETRIC=<n>" | "VIOLATION ..."; exit 0/1
"""
import sys, re
y = open(sys.argv[1]).read()
TO = sys.argv[3] if len(sys.argv) > 3 else None
PINNED_WRAPPER = {"11": "7.6", "17": "7.6", "21": "8.10.2", "25": "9.0.0"}
TARGET_KEYS = {"java.version", "maven.compiler.source", "maven.compiler.target", "maven.compiler.release"}
LOMBOK    = {"25": "1.18.46"}
JACOCO    = {"25": "0.8.13", "21": "0.8.12", "17": "0.8.12"}
BYTEBUDDY = {"25": "1.17.6", "21": "1.14.12", "17": "1.14.12"}
MOCKITO   = {"25": "5.18.0"}

v = []
if "specs.openrewrite.org/v1beta/recipe" not in y or "recipeList:" not in y:
    v.append("not a rewrite.yml composite recipe (missing type/recipeList)")

recipes = []; in_list = False
for ln in y.splitlines():
    if re.match(r'^\s*recipeList:\s*$', ln): in_list = True; continue
    if not in_list: continue
    if re.match(r'^[A-Za-z]', ln): in_list = False; continue
    m = re.match(r'^\s*-\s*([A-Za-z][\w.]+\.[A-Z]\w+)\s*:?\s*$', ln)
    if m: recipes.append((m.group(1), {})); continue
    pm = re.match(r'^\s+([\w.]+):\s*(.+?)\s*$', ln)
    if pm and recipes and not ln.lstrip().startswith('#'):
        recipes[-1][1][pm.group(1)] = pm.group(2).strip().strip('"\'')
if not recipes:
    v.append("recipeList has no recipe FQNs")

def is_free(fqn, p):
    name = fqn.rsplit(".", 1)[-1]
    if not p:
        return True
    if name == "UpgradeJavaVersion":
        return p.get("version") == TO
    if name == "UpdateGradleWrapper":
        return p.get("version") == PINNED_WRAPPER.get(TO)
    if name == "ChangePropertyValue":
        k = p.get("key") or p.get("propertyKey") or p.get("propertyName"); nv = p.get("newValue")
        if k in TARGET_KEYS and nv == TO: return True
        if k == "jacoco.version" and nv == JACOCO.get(TO): return True
        return False
    if name == "AddProperty":
        return p.get("key") == "maven.compiler.proc" and p.get("value") == "full"
    if name == "UpgradeDependencyVersion":
        g, a, nv = p.get("groupId"), p.get("artifactId"), p.get("newVersion")
        if (g, a) == ("org.projectlombok", "lombok") and nv == LOMBOK.get(TO): return True
        if g == "net.bytebuddy" and nv == BYTEBUDDY.get(TO): return True
        if g == "org.mockito" and nv == MOCKITO.get(TO): return True
        if g == "org.jacoco" and nv == JACOCO.get(TO): return True
        return False
    return False

for fqn, p in recipes:
    n = fqn.rsplit(".", 1)[-1]
    if n == "UpgradeJavaVersion" and TO and p.get("version") and p.get("version") != TO:
        v.append(f"UpgradeJavaVersion version {p.get('version')} != jv_to {TO}")
    if n == "UpdateGradleWrapper" and TO and p.get("version") and p.get("version") != PINNED_WRAPPER.get(TO):
        v.append(f"UpdateGradleWrapper version {p.get('version')} not the pinned {PINNED_WRAPPER.get(TO)}")

parametric = [fqn for fqn, p in recipes if not is_free(fqn, p)]
if v:
    print("\n".join("VIOLATION " + x for x in v)); sys.exit(1)
print(f"OK PARAMETRIC={len(parametric)}")
sys.exit(0)
