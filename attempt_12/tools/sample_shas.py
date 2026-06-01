"""attempt-12 sha-sampler: repo-list -> per-run randomized baselines.

Dataset is repos.json (repo names only). Each run samples K random commits per repo,
detects jv_from from the pom, and (optionally) keeps only baselines that compile under
jv_from. A different --seed yields different shas, so the eval is a moving target the
skill/recipes must generalize to (anti-overfitting).

Usage: python3 sample_shas.py --seed N [--k 1] [--limit M] [--repos a/b,c/d] [--compile-check]
Output: attempt_12/dataset_seed<N>.json = [{repo, sha, jv_from, jv_to}]
"""
import json, subprocess, sys, os, random
A = "/home/vmihaylov/java_8_11_17_to_java_21/attempt_12"
NEXT = {8: 11, 11: 17, 17: 21}  # one LTS hop; jv_to = next LTS

def arg(name, default=None):
    for a in sys.argv:
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default

SEED = int(arg("--seed", "0"))
K = int(arg("--k", "1"))
LIMIT = arg("--limit")
REPOS_OVERRIDE = arg("--repos")
COMPILE_CHECK = "--compile-check" in sys.argv
rng = random.Random(SEED)

REPOS = REPOS_OVERRIDE.split(",") if REPOS_OVERRIDE else json.load(open(A + "/repos.json"))
if LIMIT:
    REPOS = REPOS[:int(LIMIT)]

def sh(c, to=300):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=to)
    except subprocess.TimeoutExpired:
        class R: returncode = 124; stdout = ""; stderr = ""
        return R()

def detect_jv(wd):
    out = sh("grep -rhoE '<(maven.compiler.release|java.version|maven.compiler.target|release|source)>[0-9]+' "
             + wd + " --include=pom.xml 2>/dev/null | grep -oE '[0-9]+'").stdout.split()
    vs = [int(x) for x in out if x.isdigit() and int(x) in (8, 11, 17, 21)]
    return max(vs) if vs else None

out = []
for repo in REPOS:
    wd = "/tmp/samp_" + repo.replace("/", "_")
    sh("rm -rf " + wd, 60)
    sh(f"git clone -q https://github.com/{repo} {wd}", 600)
    if not os.path.isdir(wd + "/.git"):
        print("CLONE-FAIL", repo, flush=True); continue
    commits = sh(f"git -C {wd} log --pretty=%H", 60).stdout.split()
    if not commits:
        sh("rm -rf " + wd, 60); continue
    for sha in rng.sample(commits, min(K, len(commits))):
        sh(f"git -C {wd} checkout -q {sha} 2>/dev/null", 60)
        if not os.path.isfile(wd + "/pom.xml"):
            print("  no-pom", repo, sha[:8], flush=True); continue
        jv = detect_jv(wd)
        if jv is None or jv not in NEXT:
            print("  skip(jv=%s)" % jv, repo, sha[:8], flush=True); continue
        if COMPILE_CHECK:
            rc = sh(f"export PATH=$HOME/bin:$PATH; cd {wd} && JDK={jv} mvn -q -B -ntp -DskipTests compile", 600).returncode
            if rc != 0:
                print("  baseline-noncompile", repo, sha[:8], "jv", jv, flush=True); continue
        out.append({"repo": repo, "sha": sha, "jv_from": jv, "jv_to": NEXT[jv]})
        print("  OK", repo, sha[:8], f"jv {jv}->{NEXT[jv]}", flush=True)
    sh("rm -rf " + wd, 60)

ds = A + f"/dataset_seed{SEED}.json"
json.dump(out, open(ds, "w"), indent=1)
print(f"\nSEED={SEED} K={K} compile_check={COMPILE_CHECK}: {len(out)} valid baselines -> dataset_seed{SEED}.json")
