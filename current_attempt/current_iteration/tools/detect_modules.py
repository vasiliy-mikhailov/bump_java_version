#!/usr/bin/env python3
"""detect_modules.py <repo_dir>  -- discover the BUMPABLE modules of a repo and each one's build tool +
current Java version + next-LTS hop. A module is a build file (pom.xml / build.gradle[.kts]) whose directory
has real sources (src/main). Aggregator-only poms (packaging=pom, no src) are skipped. Maven modules inherit
the version from the nearest ancestor pom that declares one. Emits one JSON line per module:
  {"module": <relpath>, "tool": "maven"|"gradle", "from": N, "to": M}
plus a summary. Only modules whose from is a defined hop start (8/11/17/21) and < 25 are bumpable.
"""
import sys, os, re, json

HOP = {8: 11, 11: 17, 17: 21, 21: 25}
def norm(v):
    v = v.strip().strip('"\'').replace("VERSION_", "").replace("JAVA_", "")
    m = re.match(r"^1\.(\d+)$", v)                       # 1.8 -> 8
    if m: return int(m.group(1))
    m = re.match(r"^(\d+)", v)
    return int(m.group(1)) if m else None

# version tokens found anywhere in a build file (repo-agnostic; last-wins is fine, we take the max declared)
MVN_PAT = re.compile(r"<(?:maven\.compiler\.)?(?:source|target|release)>\s*([\d.]+)\s*<|"
                     r"<java\.version>\s*([\d.]+)\s*<", re.I)
GRADLE_PAT = re.compile(r"sourceCompatibility\s*=?\s*[\"']?(?:JavaVersion\.VERSION_)?([\d._]+)|"
                        r"targetCompatibility\s*=?\s*[\"']?(?:JavaVersion\.VERSION_)?([\d._]+)|"
                        r"JavaLanguageVersion\.of\(\s*([\d]+)\s*\)|"
                        r"languageVersion\s*=?\s*JavaLanguageVersion\.of\(\s*([\d]+)\s*\)|"
                        r"jvmToolchain\(\s*([\d]+)\s*\)|"
                        r"(?:kotlinOptions\.)?jvmTarget\s*=?\s*[\"']?([\d.]+)", re.I)

def versions_in(path, gradle):
    try: t = open(path, errors="ignore").read()
    except Exception: return []
    pat = GRADLE_PAT if gradle else MVN_PAT
    out = []
    for m in pat.finditer(t):
        for g in m.groups():
            if g:
                n = norm(g)
                if n: out.append(n)
    return out

def is_aggregator_pom(path):
    try: t = open(path, errors="ignore").read()
    except Exception: return False
    return re.search(r"<packaging>\s*pom\s*</packaging>", t, re.I) is not None

def has_src(d):
    return os.path.isdir(os.path.join(d, "src", "main")) or os.path.isdir(os.path.join(d, "src"))

def main():
    root = sys.argv[1]
    mods = []
    # collect all build files
    builds = []  # (dir, tool, buildfile)
    for dp, dns, fns in os.walk(root):
        if any(x in dp for x in ("/.git", "/build/", "/target/", "/.gradle")): continue
        for f in fns:
            if f == "pom.xml": builds.append((dp, "maven", os.path.join(dp, f)))
            elif f in ("build.gradle", "build.gradle.kts"): builds.append((dp, "gradle", os.path.join(dp, f)))
    # maven ancestor chain (for inheritance): map dir -> pom path, walk up
    pom_by_dir = {d: bf for d, tool, bf in builds if tool == "maven"}
    def mvn_version(d):
        cur = d
        while True:
            bf = pom_by_dir.get(cur)
            if bf:
                vs = versions_in(bf, gradle=False)
                if vs: return max(vs)
            parent = os.path.dirname(cur)
            if parent == cur or len(parent) < len(root): break
            cur = parent
        return None
    for d, tool, bf in builds:
        if not has_src(d):
            continue                                     # aggregator / no sources -> nothing to bump
        if tool == "maven" and is_aggregator_pom(bf) and not has_src(d):
            continue
        frm = max(versions_in(bf, gradle=True)) if tool == "gradle" else None
        if tool == "gradle" and frm is None:
            frm = None                                   # gradle: no toolchain declared here
        if tool == "maven":
            frm = mvn_version(d)
        rel = os.path.relpath(d, root)
        entry = {"module": rel if rel != "." else "(root)", "tool": tool, "from": frm,
                 "to": HOP.get(frm) if frm in HOP else None,
                 "bumpable": (frm in HOP)}
        mods.append(entry)
    for m in mods: print(json.dumps(m))
    bumpable = [m for m in mods if m["bumpable"]]
    hops = sorted({f'{m["from"]}->{m["to"]}' for m in bumpable})
    print(json.dumps({"summary": {"modules": len(mods), "bumpable": len(bumpable),
                                  "tools": sorted({m["tool"] for m in mods}),
                                  "distinct_hops": hops,
                                  "heterogeneous": len(hops) > 1}}))

if __name__ == "__main__":
    main()
