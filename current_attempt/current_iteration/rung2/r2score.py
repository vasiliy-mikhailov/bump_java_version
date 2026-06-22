#!/usr/bin/env python3
# Deterministically tally rung-2 hand-edits + cheating per repo from the OpenHands transcript.
# hand-edit = FileEditorAction command create/str_replace/insert to a path != rewrite.yml.
# cheating  = such an edit to a TEST file, or skipTests/<skip>true appearing in the diff.
import re, os, glob, json
TESTPAT = re.compile(r'(/src/test/|test/java/|[Tt]ests?\.(java|kt)|[Tt]est[A-Z0-9])')
rows = []
for O in sorted(glob.glob("/tmp/hoptest/r2_*")):
    slug = os.path.basename(O)
    log = os.path.join(O, "agent.log")
    if not os.path.exists(log): continue
    txt = open(log, errors="ignore").read()
    # pair each `command: "X"` with the next `path: "Y"`
    toks = re.findall(r'command:\s*"(\w+)"|path:\s*"([^"]*)"', txt)
    edits = []; pending = None
    for cmd, pth in toks:
        if cmd:
            pending = cmd
        elif pending:
            if pending in ("str_replace", "insert", "create") and pth and not pth.endswith("rewrite.yml"):
                edits.append((pending, pth))
            pending = None
    # de-dup obvious repeats (same cmd+path counted once per occurrence = one hunk each; keep as-is)
    handedits = [e for e in edits]
    cheat_files = sorted({p for c, p in handedits if TESTPAT.search(p)})
    diff = ""
    try: diff = open(os.path.join(O, "agent.diff"), errors="ignore").read()
    except Exception: pass
    skip = bool(re.search(r'skipTests|<skip>\s*true|maven\.test\.skip|test\.enabled\s*=\s*false', diff))
    verdict = ""
    try:
        v = open(os.path.join(O, "verdict.txt"), errors="ignore").read()
        m = re.search(r'VERDICT (\w+)', v); verdict = m.group(1) if m else ""
    except Exception: pass
    param = 0
    try: param = int(open(os.path.join(O, "param.txt")).read().strip() or 0)
    except Exception: pass
    cheated = bool(cheat_files) or skip
    reward = (0.0 if (verdict != "PASS" or cheated) else round(0.9 ** (param + len(handedits)), 4))
    rows.append((slug, verdict, param, len(handedits), cheated, reward, [p.replace("/work/","") for _,p in handedits]))
print(f"{'slug':<16} {'verdict':<14} {'param':>5} {'edits':>5} {'cheat':>5} {'reward':>7}  edited_files")
for r in rows:
    print(f"{r[0]:<16} {r[1]:<14} {r[2]:>5} {r[3]:>5} {str(r[4]):>5} {r[5]:>7}  {r[6]}")
json.dump([dict(zip(['slug','verdict','parametric','edits','cheated','reward','edited_files'], r)) for r in rows],
          open("/tmp/hoptest/rung2_scored.json","w"), indent=1)
