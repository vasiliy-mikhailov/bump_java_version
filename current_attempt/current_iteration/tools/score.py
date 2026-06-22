#!/usr/bin/env python3
"""Scorer for the sealed hop harness. Two modes (no host deps; runs in python:3-slim over the workspace):
  score.py passet <ws> <out_set_file>            -> write the passing-test set, print its count
  score.py final  <ws> <pre_set> <from> <to> <comprc> <postrc> <cwe_json> <out_dir>
                                                 -> compute post_set, LOST, effective_target, CWE summary,
                                                    decide the combined-gate verdict, write <out_dir>/result.json
"""
import sys, os, glob, json, struct, re
import xml.etree.ElementTree as ET
from collections import Counter

def passet(root):
    s = set()
    for x in glob.glob(root + "/**/TEST-*.xml", recursive=True):
        try: r = ET.parse(x).getroot()
        except Exception as e: sys.stderr.write(f"passet: skipped unparseable {x}: {e}\n"); continue
        # surefire 3.x writes classname=parametrized display-name (not FQCN) -> cross-class
        # param cases collide in the set; the TEST-<FQCN>.xml filename carries the true FQCN.
        base = os.path.basename(x)
        cls = base[5:-4] if base.startswith("TEST-") and base.endswith(".xml") else ""
        for tc in r.iter("testcase"):
            if not any(c.tag in ("failure", "error", "skipped") for c in tc):
                s.add((cls or tc.get("classname", "")) + "#" + tc.get("name", ""))
    return s

# --- effective bytecode target (feature = major-44); skip build-logic + multi-release ---
MAIN = ("/target/classes/", "/build/classes/java/main/", "/build/classes/kotlin/main/",
        "/build/classes/groovy/main/", "/build/classes/scala/main/", "/out/production/")
TEST = ("/target/test-classes/", "/build/classes/java/test/", "/build/classes/kotlin/test/",
        "/build/classes/groovy/test/", "/out/test/")
def _major(p):
    try:
        with open(p, "rb") as f: h = f.read(8)
        if len(h) < 8 or h[:4] != b"\xca\xfe\xba\xbe": return None
        return struct.unpack(">H", h[6:8])[0]
    except Exception as e:
        sys.stderr.write(f"_major: unreadable class {p}: {e}\n"); return None
def efftarget(root):
    mains, tests = [], []
    for dp, _, fn in os.walk(root):
        pp = dp.replace("\\", "/") + "/"
        if "/META-INF/versions/" in pp or "/buildSrc/" in pp or "/build-logic/" in pp: continue
        ismain = any(h in pp for h in MAIN); istest = any(h in pp for h in TEST)
        if not (ismain or istest): continue
        for f in fn:
            if not f.endswith(".class") or f == "module-info.class": continue
            m = _major(os.path.join(dp, f))
            if m: (mains if ismain else tests).append(m)
    pool = mains or tests
    return (min(pool) - 44) if pool else -1

# --- rename-robust conservation: how many pre-pass tests are missing post (lifted from agent_drive_one) ---
def lost(pre, post):
    def norm(line):
        m = line.rsplit("#", 1)[-1]
        return m.split("(")[0].split("[")[0].split("{")[0].strip().lower()
    post_exact = Counter(post); unmatched = []
    for p in pre:
        if post_exact[p] > 0: post_exact[p] -= 1
        else: unmatched.append(p)
    post_norm = Counter()
    for x, c in post_exact.items():
        if c > 0: post_norm[norm(x)] += c
    resid = []
    for p in unmatched:
        k = norm(p)
        if post_norm[k] > 0: post_norm[k] -= 1
        else: resid.append(p)
    VOL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|@[0-9a-f]{6,}|\b[0-9a-f]{6,}\b|\d+")
    post_dig = Counter()
    for x, c in post_norm.items():
        if c > 0: post_dig[VOL.sub("", x)] += c
    n = 0
    for p in resid:
        dk = VOL.sub("", norm(p))
        if post_dig[dk] > 0: post_dig[dk] -= 1
        else: n += 1
    return n

def cwe_summary(path):
    """parse osv-scanner --format json -> (n_vulns, n_packages, by_severity dict)."""
    try: raw = open(path).read()
    except Exception: raw = ""
    try:
        d = json.loads(raw)
    except Exception:
        # osv emits non-JSON when it cannot scan (e.g. Gradle .kts w/o a lockfile). P16: that is UNKNOWN,
        # NOT "clean" — defaulting unscannable -> 0 vulns would falsely pass the CWE gate once it gates.
        # Strip any preamble; if still unparseable, report UNKNOWN (-1) so the gate can never pass on it.
        # ROOT FIX (tracked stopgap): generate a lockfile so osv scans the resolved/declared deps.
        i, j = raw.find("{"), raw.rfind("}")
        try:
            d = json.loads(raw[i:j+1])
        except Exception:
            note = "no_scannable_sources" if (not raw.strip() or "no package sources" in raw.lower() or "no sources" in raw.lower()) else "scan_unreadable"
            return {"vulns": -1, "packages": -1, "by_severity": {}, "note": note}
    sev = Counter(); ids = set(); pkgs = set()
    for res in d.get("results", []):
        for pkg in res.get("packages", []):
            p = pkg.get("package", {})
            key = f"{p.get('ecosystem')}:{p.get('name')}@{p.get('version')}"
            for v in pkg.get("vulnerabilities", []):
                ids.add(v.get("id"))
                if v.get("id"): pkgs.add(key)
            for g in pkg.get("groups", []):
                mx = g.get("max_severity", "")
                try: score = float(mx)
                except Exception: score = -1
                band = ("critical" if score >= 9 else "high" if score >= 7 else
                        "medium" if score >= 4 else "low" if score >= 0 else "unknown")
                sev[band] += 1
    return {"vulns": len(ids), "packages": len(pkgs), "by_severity": dict(sev)}

mode = sys.argv[1]
if mode == "passet":
    ws, out = sys.argv[2], sys.argv[3]
    s = passet(ws)
    open(out, "w").write("\n".join(sorted(s)))
    print(len(s))
    sys.exit(0)

# mode == final
ws, pre_f, frm, to, comprc, postrc, cwe_json, out_dir = sys.argv[2:10]
frm, to, comprc, postrc = int(frm), int(to), int(comprc), int(postrc)
# reward penalty inputs: model-chosen parametric recipes + manual edits (each ×0.9). Optional, default 0.
parametric = int(sys.argv[10]) if len(sys.argv) > 10 else 0
edits = int(sys.argv[11]) if len(sys.argv) > 11 else 0
pre = [x for x in open(pre_f).read().split("\n") if x.strip()] if os.path.exists(pre_f) else []
post = sorted(passet(ws))
open(out_dir + "/post_set.txt", "w").write("\n".join(post))
LOST = lost(pre, post)
ETGT = efftarget(ws)
CWE = cwe_summary(cwe_json)

# combined gate
if not pre:
    verdict = "NO_BASELINE_NOTESTS"
elif comprc != 0:
    verdict = "FAIL_build_post"
elif LOST != 0:
    verdict = "FAIL_test_conservation"
elif ETGT >= 0 and ETGT < to:
    verdict = "FAIL_target_not_bumped"
else:
    # CWE is REPORTED, not yet gating (threshold TBD) — record but don't fail on it
    verdict = "PASS"
# reward = gate_pass × 0.9^(parametric recipes + manual edits); 0 if the gate didn't pass
reward = round(0.9 ** (parametric + edits), 4) if verdict == "PASS" else 0.0
res = {"slug": os.path.basename(out_dir.rstrip("/")), "hop": f"{frm}->{to}", "verdict": verdict,
       "pre_pass": len(pre), "post_pass": len(post), "lost": LOST,
       "compile_rc": comprc, "test_rc": postrc, "effective_target": ETGT,
       "parametric_recipes": parametric, "edits": edits, "reward": reward,
       "dep_cwes": CWE}
json.dump(res, open(out_dir + "/result.json", "w"), indent=1)
print("VERDICT", verdict, "pre", len(pre), "post", len(post), "lost", LOST,
      "target", ETGT, "cwes", CWE.get("vulns"), "parametric", parametric, "edits", edits, "reward", reward)
