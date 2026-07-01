#!/usr/bin/env python3
# Per-module target verification for the module-level bump gate. The whole-repo gate stays (repo builds +
# tests conserved); the "target raised" check becomes PER-MODULE: each module's own compiled bytecode must
# reach ITS jv_to (from detect_modules). Reclaims heterogeneous multi-module repos and removes the
# min-over-all-classes drag (a bundled dep .class / low sibling no longer sinks the repo).
# Usage: score_modules.py <ws> <modules.jsonl>  -> {"all_modules_reached_target":bool, "modules":[...]}
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score  # _major

def module_target(ws, mpath, tool):
    md = ws if mpath in (".", "(root)") else os.path.join(ws, mpath)
    if tool == "maven":
        bases = [os.path.join(md, "target", "classes")]
    else:
        bases = [os.path.join(md, "build", "classes", l, "main") for l in ("java", "kotlin", "groovy", "scala")]
        bases += glob.glob(os.path.join(md, "build", "classes", "kotlin", "*", "main"))
    majors = []
    for b in bases:
        if not os.path.isdir(b): continue
        for dp, _, fns in os.walk(b):
            for f in fns:
                if f.endswith(".class") and f != "module-info.class":
                    m = score._major(os.path.join(dp, f))
                    if m: majors.append(m)
    return (min(majors) - 44) if majors else -1

def score_modules(ws, modules):
    out = []; all_ok = True
    for m in modules:
        if not m.get("bumpable"): continue
        t = module_target(ws, (m.get("module") or m.get("path")), m["tool"]); ok = (t == m["to"])
        all_ok = all_ok and ok
        out.append({"module": (m.get("module") or m.get("path")), "to": m["to"], "effective_target": t, "ok": ok})
    return {"all_modules_reached_target": all_ok and bool(out), "n": len(out), "modules": out}

if __name__ == "__main__":
    mods = [json.loads(l) for l in open(sys.argv[2]) if '"module"' in l and '"summary"' not in l]
    print(json.dumps(score_modules(sys.argv[1], mods)))
