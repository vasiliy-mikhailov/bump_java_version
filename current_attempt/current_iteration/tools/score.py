#!/usr/bin/env python3
"""Scorer for the sealed hop harness (no host deps; runs in python:3-slim over the workspace):
  score.py passet <ws> <out_set_file>            -> write the passing-test set, print its count
  score.py resetgen <ws>                         -> strip generated-source residue (fresh-clone symmetry)
  score.py final  <ws> <pre_set> <from> <to> <comprc> <postrc> <cwe_json> <out_dir>
                                                 -> compute post_set, LOST, effective_target, CWE summary,
                                                    decide the combined-gate verdict, write <out_dir>/result.json
  score.py rescore <out_dir>                     -> RE-DECIDE an already-scored datapoint from its persisted
                                                    pre_set.txt/post_set.txt (workspace reaped), rewrite
                                                    result.json + verdict.txt; raw-count fallback if a set
                                                    file is missing/empty
"""
import sys, os, glob, json, struct, re, shutil
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
                # JUnit5 parametrized/dynamic display names can carry LITERAL newlines/control chars (AoC
                # "Cube(xs=1..2,\n ys=1..2)" cases). The set is line-serialized ("\n".join) and everything
                # downstream (the gate's `pre` rebuild via split("\n"), grep -c pre-counts) treats one line
                # as one test. An embedded newline splits ONE entry across N lines -> the gate compares N
                # fragments against the intact live post-set -> false lost = fragments-entries ->
                # false FAIL_test_conservation (rr_17_57 chalup/advent-of-code, 348 lines / 247 tests). Fold
                # any control char INJECTIVELY (\xNN) so each entry stays one line WITHOUT merging distinct
                # names (a lossy fold to a space collapses `case\tX` and `case X` -> a lost test is hidden -> false PASS).
                key = (cls or tc.get("classname", "")) + "#" + tc.get("name", "")
                s.add(re.sub(r"[\x00-\x1f\x7f]", lambda m: "\\x%02x" % ord(m.group()), key))
    return s

# --- fresh-clone symmetry: strip generated-source residue before the gate build ---
# Some builds run annotation processors that write generated sources INTO the tracked source tree, the
# canonical case being QueryDSL's com.ewerk plugin -> src/main/generated. The gate's build-output clean
# (build/, target/, .gradle/) MISSES these because they live under src/, so on the gate re-compile the
# processor hits its own leftovers -> javac "error: Attempt to recreate a file for type ...QReply" ->
# deterministic false FAIL_build_post. The baseline never sees it (it builds a fresh clone). A repo that
# COMMITS its generated sources cannot reach the gate either -- a fresh-clone baseline would collide the
# same way and be filtered out as NO_BASELINE_NOCOMPILE -- so any generated-source dir present at gate time
# is regenerable residue: remove it to match the baseline's pristine checkout. Runs as root in python:3-slim
# (the gate's PY() container), so it deletes the sealed build's root-owned residue offline, with no git dep.
GEN_DIRS = {"generated", "generated-sources", "generated-src", "generated-java", "generated-test-sources"}
def resetgen(root):
    """Remove generated-source dirs written as a direct child of a source-set dir (src/<set>/generated).
    Returns the removed paths (relative to root). Scoped to the src/<set>/<gendir> shape ON PURPOSE so a
    hand-written package literally named 'generated' (src/main/java/.../generated) is never touched -- cf.
    the full-clean over-match bug that once deleted source packages named 'build'."""
    removed = []
    for dp, dns, _ in os.walk(root):
        # dp is a candidate source-set dir only if its parent is literally 'src' (…/src/main, …/src/test,
        # …/module/src/integrationTest, …). Its 'generated' child is then querydsl-style residue.
        if os.path.basename(os.path.dirname(dp)) != "src":
            continue
        for d in list(dns):
            if d.lower() in GEN_DIRS:
                full = os.path.join(dp, d)
                shutil.rmtree(full, ignore_errors=True)
                removed.append(os.path.relpath(full, root))
                dns.remove(d)  # don't descend into what we just deleted
    return removed

# --- effective bytecode target (feature = major-44); skip build-logic + multi-release ---
MAIN = ("/target/classes/", "/build/classes/java/main/", "/build/classes/kotlin/main/",
        "/build/classes/groovy/main/", "/build/classes/scala/main/", "/out/production/")
TEST = ("/target/test-classes/", "/build/classes/java/test/", "/build/classes/kotlin/test/",
        "/build/classes/groovy/test/", "/out/test/")
# Kotlin Multiplatform puts JVM bytecode at build/classes/kotlin/<target>/main|test/ (the target name, e.g.
# `jvm`, sits between kotlin/ and main/test/) -- the fixed tuples miss it, so a KMP build looks like it has
# NO main bytecode (false FAIL_no_main_bytecode / previously a soft-pin false PASS). js/native targets emit
# no .class, so a broad match here is safe (the CAFEBABE check filters them out).
KMP = re.compile(r"/build/classes/kotlin/[^/]+/(main|test)/")
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
        km = KMP.search(pp)
        ismain = any(h in pp for h in MAIN) or (km is not None and km.group(1) == "main")
        istest = any(h in pp for h in TEST) or (km is not None and km.group(1) == "test")
        if not (ismain or istest): continue
        for f in fn:
            if not f.endswith(".class") or f == "module-info.class": continue
            m = _major(os.path.join(dp, f))
            if m: (mains if ismain else tests).append(m)
    pool = mains  # MAIN bytecode only; never derive the target from TEST classes (review score-3)
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
    # strip only CLEARLY-volatile tokens (UUIDs, @hex, long hex runs). The old trailing `|\d+` stripped ALL
    # digits, bucketing distinct numbered tests (testCase1/2/3) together so a dropped one was masked (review score-2).
    VOL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|@[0-9a-f]{6,}|\b[0-9a-f]{6,}\b")
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

# --- combined-gate verdict (extracted for unit-testability; behavior preserved) ---
def decide(pre, comprc, LOST, ETGT, to, modules_ok=None):
    if not pre:        return "NO_BASELINE_NOTESTS"
    if comprc != 0:    return "FAIL_build_post"
    if LOST != 0:      return "FAIL_test_conservation"
    if modules_ok is not None:                          # module-level bump: EVERY module reached ITS jv_to
        return "PASS" if modules_ok else "FAIL_target_not_bumped"
    if ETGT == -1:     return "FAIL_no_main_bytecode"   # build OK but no inspectable main classes: the bump is unverifiable, never silently PASS (review score-4)
    if 0 <= ETGT < to: return "FAIL_target_not_bumped"
    # CWE is REPORTED, not yet gating (threshold TBD) — record but don't fail on it
    return "PASS"

def main():
    mode = sys.argv[1]
    if mode == "passet":
        ws, out = sys.argv[2], sys.argv[3]
        s = passet(ws)
        open(out, "w").write("\n".join(sorted(s)))
        print(len(s))
        return

    if mode == "resetgen":
        ws = sys.argv[2]
        for r in resetgen(ws):
            print("resetgen removed", r)
        return

    if mode == "rescore":
        # Re-decide a completed datapoint from its PERSISTED artifacts (the sealed workspace is reaped after
        # scoring, so passet() over it would return the empty set -> false total loss). Conservation is the
        # rename-robust lost() over pre_set.txt vs post_set.txt read the SAME way -- both are line lists, so
        # a newline-in-name entry fragments identically on both sides and cancels, giving the true loss. Raw
        # pre_pass/post_pass scalars from result.json are used ONLY when a set file is missing/empty. Rewrites
        # result.json + verdict.txt (never the set files) so r2score_one can re-derive score.json/reward.
        out_dir = sys.argv[2]
        res = json.load(open(os.path.join(out_dir, "result.json")))
        def _lines(name):
            p = os.path.join(out_dir, name)
            if not os.path.exists(p): return None
            return [x for x in open(p).read().split("\n") if x.strip()]
        pre_l, post_l = _lines("pre_set.txt"), _lines("post_set.txt")
        if not (pre_l and post_l):
            # the scalar pre_pass-post_pass fallback is NOT rename-robust (it can flip the verdict either way
            # vs the true set-diff), so refuse to guess a verdict from it -- mark unscorable instead.
            open(os.path.join(out_dir, "verdict.txt"), "w").write("VERDICT UNSCORABLE_RESCORE_NO_SETS\n")
            print("UNSCORABLE_RESCORE_NO_SETS (pre_set/post_set missing or empty; refusing rawcount guess)")
            return
        LOST = lost(pre_l, post_l); basis = "setdiff"; pre_for_decide = pre_l
        comprc = int(res.get("compile_rc", 0)); ETGT = int(res.get("effective_target", -1))
        to = int(str(res.get("hop", "0->0")).split("->")[-1] or 0)
        param = int(res.get("parametric_recipes", 0)); edits = int(res.get("edits", 0))
        verdict = decide(pre_for_decide, comprc, LOST, ETGT, to)
        reward = round(0.9 ** (param + edits), 4) if verdict == "PASS" else 0.0
        res.update({"verdict": verdict, "lost": LOST, "reward": reward, "rescored_by": basis})
        json.dump(res, open(os.path.join(out_dir, "result.json"), "w"), indent=1)
        line = ("VERDICT %s pre %s post %s lost %s target %s cwes %s parametric %s edits %s reward %s"
                % (verdict, res.get("pre_pass"), res.get("post_pass"), LOST, ETGT,
                   res.get("dep_cwes", {}).get("vulns"), param, edits, reward))
        open(os.path.join(out_dir, "verdict.txt"), "w").write(line + "\n")
        print(line + "  [rescored:%s]" % basis)
        return

    # mode == final
    ws, pre_f, frm, to, comprc, postrc, cwe_json, out_dir = sys.argv[2:10]
    frm, to, comprc, postrc = int(frm), int(to), int(comprc), int(postrc)
    # reward penalty inputs: model-chosen parametric recipes + manual edits (each ×0.9). Optional, default 0.
    parametric = int(sys.argv[10]) if len(sys.argv) > 10 else 0
    edits = int(sys.argv[11]) if len(sys.argv) > 11 else 0
    modules_file = sys.argv[12] if len(sys.argv) > 12 else ""   # per-module target gate (module-level bump); absent => repo-level
    pre = [x for x in open(pre_f).read().split("\n") if x.strip()] if os.path.exists(pre_f) else []
    post = sorted(passet(ws))
    open(out_dir + "/post_set.txt", "w").write("\n".join(post))
    LOST = lost(pre, post)
    ETGT = efftarget(ws)
    CWE = cwe_summary(cwe_json)

    # module-level bump: if a per-module list was captured at detect time, gate each module's OWN bytecode
    # target against ITS jv_to (repo_reward = product of module gates); else fall back to the repo-level ETGT.
    modules_ok, MODS = None, None
    if modules_file and os.path.exists(modules_file):
        try:
            import score_modules
            mods = [json.loads(l) for l in open(modules_file) if '"module"' in l and '"summary"' not in l]
            if len(mods) >= 2:                               # engage per-module gate ONLY for multi-module repos;
                MODS = score_modules.score_modules(ws, mods) # a single-module repo keeps the proven repo-level ETGT path
                dt = MODS.get("modules") or []
                if dt and all(m["effective_target"] >= m["to"] for m in dt):
                    modules_ok = True                        # every module reached its own target -> genuine repo PASS
                elif any(0 <= m["effective_target"] < m["to"] for m in dt):
                    modules_ok = False                       # a module concretely sits below its target (sibling stuck low)
                # else inconclusive (a module had no inspectable bytecode): leave None -> defer to repo-level ETGT
        except Exception as e:
            sys.stderr.write("module gate skipped: %s\n" % e)

    verdict = decide(pre, comprc, LOST, ETGT, to, modules_ok)
    # reward = gate_pass × 0.9^(parametric recipes + manual edits); 0 if the gate didn't pass
    reward = round(0.9 ** (parametric + edits), 4) if verdict == "PASS" else 0.0
    res = {"slug": os.path.basename(out_dir.rstrip("/")), "hop": f"{frm}->{to}", "verdict": verdict,
           "pre_pass": len(pre), "post_pass": len(post), "lost": LOST,
           "compile_rc": comprc, "test_rc": postrc, "effective_target": ETGT,
           "parametric_recipes": parametric, "edits": edits, "reward": reward,
           "dep_cwes": CWE, "modules": MODS}
    json.dump(res, open(out_dir + "/result.json", "w"), indent=1)
    print("VERDICT", verdict, "pre", len(pre), "post", len(post), "lost", LOST,
          "target", ETGT, "cwes", CWE.get("vulns"), "parametric", parametric, "edits", edits, "reward", reward)

if __name__ == "__main__":
    main()
