import re, os, sys, json
# Score one rung-2 datapoint. reward = gate_pass x 0.9^(parametric recipes + manual edits), 0 if cheated.
# KEY: a hand-edit whose ENTIRE diff is Java-target declarations (sourceCompatibility/targetCompatibility/
# release/jvmTarget/languageVersion/<java.version>/<maven.compiler.*>) is the FREE "set-target" intent applied
# by hand (because UpgradeJavaVersion under-fired on that style) — it does NOT count as a penalized edit.
TESTPAT = re.compile(r'(/src/test/|test/java/|[Tt]ests?\.(java|kt)|[Tt]est[A-Z0-9])')
TARGETPAT = re.compile(r'(sourceCompatibility|targetCompatibility|kotlinOptions\.jvmTarget|\bjvmTarget\b'
                       r'|languageVersion|JavaLanguageVersion\.of|JavaVersion\.VERSION_|\.release\.set'
                       r'|<maven\.compiler\.(source|target|release)>|<java\.version>|<(source|target|release)>\s*\d)', re.I)
O = sys.argv[1]; repo = sys.argv[2] if len(sys.argv) > 2 else ""
slug = os.path.basename(O.rstrip('/'))
def rd(p):
    try: return open(p, errors='ignore').read()
    except Exception: return ""
# hand-edited files (FileEditorAction create/str_replace/insert), excluding the rewrite.yml program
toks = re.findall(r'command:\s*"(\w+)"|path:\s*"([^"]*)"', rd(os.path.join(O, 'agent.log')))
hand_files = []; pending = None
for cmd, pth in toks:
    if cmd: pending = cmd
    elif pending:
        if pending in ('str_replace', 'insert', 'create') and pth and not pth.endswith('rewrite.yml'):
            f = pth.replace('/work/', '')
            if f not in hand_files: hand_files.append(f)
        pending = None
# per-file changed (+/-) lines from the diff
diff = rd(os.path.join(O, 'agent.diff')); filelines = {}; curf = None
for ln in diff.splitlines():
    m = re.match(r'diff --git a/(\S+)', ln)
    if m: curf = m.group(1); filelines.setdefault(curf, []); continue
    if curf and ln[:1] in '+-' and not ln.startswith('+++') and not ln.startswith('---'):
        s = ln[1:].strip()
        if s: filelines[curf].append(s)
def pure_target(f):
    lines = filelines.get(f, [])
    return bool(lines) and all(TARGETPAT.search(l) for l in lines)
edits = [f for f in hand_files if not pure_target(f)]
free_target = [f for f in hand_files if pure_target(f)]
cheat = [f for f in hand_files if TESTPAT.search(f)]
skip = bool(re.search(r'skipTests|<skip>\s*true|maven\.test\.skip|\.enabled\s*=\s*false', diff))
m = re.search(r'VERDICT (\w+)', rd(os.path.join(O, 'verdict.txt'))); v = m.group(1) if m else ""
try: param = int((rd(os.path.join(O, 'param.txt')) or "0").strip() or 0)
except Exception: param = 0
cheated = bool(cheat) or skip
reward = 0.0 if (v != 'PASS' or cheated) else round(0.9 ** (param + len(edits)), 4)
out = {'slug': slug, 'repo': repo, 'verdict': v, 'parametric': param, 'edits': len(edits), 'cheated': cheated,
       'reward': reward, 'edited_files': edits, 'free_target_sets': free_target}
open(os.path.join(O, 'score.json'), 'w').write(json.dumps(out))
print(json.dumps(out))
