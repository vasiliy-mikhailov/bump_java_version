#!/usr/bin/env python3
# Detect a project's REAL current Java level — by its declared BYTECODE target (options.release / source /
# <maven.compiler.release>), NOT the build toolchain — and whether it's a valid bump target at all.
# Usage: detect_java.py <workspace_dir>  -> one JSON line.
import sys, os, re, json, glob
ws = sys.argv[1]
def norm(s):
    s = s.strip().strip('"\'')
    s = s.replace("JavaVersion.VERSION_", "").replace("VERSION_", "")
    if s.startswith("1."): s = s[2:]      # 1.8 -> 8
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None
release, source, toolchain = [], [], []
is_plugin = False
gfiles = glob.glob(ws + "/**/*.gradle", recursive=True) + glob.glob(ws + "/**/*.gradle.kts", recursive=True)
for f in gfiles:
    if "/build/" in f or "/.gradle/" in f: continue
    t = open(f, errors="ignore").read()
    if re.search(r"`?java-gradle-plugin`?|\bgradlePlugin\s*\{|`?java-library`?.*plugin", t): is_plugin = is_plugin or ("java-gradle-plugin" in t or "gradlePlugin {" in t)
    for m in re.finditer(r"options\.release(?:\.set)?\s*[=(]\s*(\d+)", t): release.append(int(m.group(1)))
    for m in re.finditer(r"\brelease\.set\(\s*(\d+)\s*\)", t): release.append(int(m.group(1)))
    for m in re.finditer(r"(?:source|target)Compatibility\s*=?\s*(?:JavaVersion\.VERSION_)?[\"']?([\d._]+)", t):
        v = norm(m.group(1));  release.append(v) if False else (source.append(v) if v else None)
    for m in re.finditer(r"languageVersion(?:\.set)?\s*[=(]\s*JavaLanguageVersion\.of\(\s*(\d+)\s*\)", t): toolchain.append(int(m.group(1)))
    for m in re.finditer(r"jvmTarget\s*[=(]\s*[\"']?(?:JVM_)?([\d._]+)", t):
        v = norm(m.group(1));  source.append(v) if v else None
for f in glob.glob(ws + "/**/pom.xml", recursive=True):
    if "/target/" in f: continue
    t = open(f, errors="ignore").read()
    for tag in ("maven.compiler.release", "maven.compiler.source", "maven.compiler.target", "java.version"):
        for m in re.finditer(r"<%s>\s*([\d.]+)\s*</%s>" % (tag, tag), t):
            v = norm(m.group(1))
            if v: (release if "release" in tag else source).append(v)
    for m in re.finditer(r"<release>\s*(\d+)\s*</release>", t): release.append(int(m.group(1)))
    for m in re.finditer(r"<(?:source|target)>\s*([\d.]+)\s*</(?:source|target)>", t):
        v = norm(m.group(1));  source.append(v) if v else None
release = sorted({x for x in release if x}); source = sorted({x for x in source if x}); toolchain = sorted({x for x in toolchain if x})
# the bytecode target = explicit release if set, else source/target settings, else the toolchain
targets = release or source or toolchain
detected = min(targets) if targets else None
tmax = max(toolchain) if toolchain else None
multi = len(set(targets)) > 1 if targets else False
# deliberate-low-target = a bytecode pin BELOW the build toolchain, OR multiple targets, OR a Gradle plugin
low_target = bool((detected is not None and tmax is not None and detected < tmax) or multi or is_plugin)
LTS = [11, 17, 21, 25]
hop_to = next((L for L in LTS if detected is not None and L > detected), None)
bumpable = bool(detected is not None and hop_to is not None and not low_target)
print(json.dumps({"detected": detected, "release": release, "source": source, "toolchain": toolchain,
                  "multi_target": multi, "is_gradle_plugin": is_plugin, "low_target": low_target,
                  "hop_to": hop_to, "bumpable": bumpable}))
