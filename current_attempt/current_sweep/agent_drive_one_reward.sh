#!/bin/bash
# Unified per-repo driver for ALL THREE agents (opencode | kilo | openhands). Identical flow,
# skill, env, and scoring — the AGENT (6th arg) is the only variable. No force-apply.
# Args: REPO SHA FROM TO SLUG AGENT ; env: OC_KEY. Emits /out/$SLUG/result.json.
set -uo pipefail
REPO=$1; SHA=$2; FROM=$3; TO=$4; SLUG=$5; AGENT=$6
export HOME=/root
export OPENAI_API_KEY="$OC_KEY"; export QWEN_API_KEY="$OC_KEY"
QWEN_BASE="https://inference.mikhailov.tech/qwen-3.6-27b-fp8/v1"; QWEN_MODEL="qwen-3.6-27b-fp8"
OUT=/out/$SLUG; mkdir -p "$OUT"
# P5: route this build's Gradle through the Nexus proxy (init.d auto-load; per-container home)
mkdir -p "$HOME/.gradle/init.d"
cat > "$HOME/.gradle/init.d/nexus-mirror.gradle" <<'NXEOF'
// P5 Nexus mirror — FAIL-OPEN and Gradle 4.x–9.x compatible.
// Any error here is swallowed: the worst case is "this build resolves directly" (status quo),
// never "this build breaks". Nexus is prepended (preferred); the project's own repos are kept.
def NEXUS = "http://nexus:8081/repository/maven-public/"

def addNexus = { repos ->
    try {
        if (repos.findByName("nexusMirror") != null) return
        def nx = repos.maven { r -> r.name = "nexusMirror"; r.url = NEXUS }
        // Gradle 6+ blocks HTTP repos unless this is set; pre-6 the property doesn't exist (HTTP allowed there).
        try { nx.allowInsecureProtocol = true } catch (ignored) {}
        // prefer Nexus first; on containers where reorder is unsupported it stays appended (still a valid source).
        try { repos.remove(nx); repos.add(0, nx) } catch (ignored) {}
    } catch (ignored) {}
}

try {
    settingsEvaluated { settings ->
        try { settings.pluginManagement.repositories { addNexus(delegate) } } catch (ignored) {}
        try { settings.dependencyResolutionManagement.repositoriesMode.set(RepositoriesMode.PREFER_PROJECT) } catch (ignored) {}
    }
} catch (ignored) {}

try {
    allprojects {
        try { buildscript.repositories { addNexus(delegate) } } catch (ignored) {}
        try { repositories { addNexus(delegate) } } catch (ignored) {}
    }
} catch (ignored) {}
NXEOF


emit() { python3 - "$@" <<'PY'
import sys, json
out, slug, repo, hop, verdict, pre, post, lost, prerc, postrc, comprc = sys.argv[1:12]
json.dump({"slug": slug, "repo": repo, "hop": hop, "verdict": verdict, "pre_pass": int(pre),
           "post_pass": int(post), "lost": int(lost), "prerc": int(prerc), "postrc": int(postrc),
           "compile_rc": int(comprc)}, open(out + "/result.json", "w"), indent=1)
print("VERDICT", verdict, "pre", pre, "post", post, "lost", lost)
PY
}
passet() { python3 - "$1" "$2" <<'PY'
import sys, glob, xml.etree.ElementTree as ET
root, dst = sys.argv[1], sys.argv[2]
s = set()
for x in glob.glob(root + "/**/target/surefire-reports/TEST-*.xml", recursive=True) + glob.glob(root + "/**/build/test-results/test/TEST-*.xml", recursive=True):
    try: r = ET.parse(x).getroot()
    except Exception: continue
    for tc in r.iter("testcase"):
        if not any(c.tag in ("failure", "error", "skipped") for c in tc):
            s.add(tc.get("classname", "") + "#" + tc.get("name", ""))
open(dst, "w").write("\n".join(sorted(s)))
print(len(s))
PY
}

# reproducible deps: reuse the dig's read-only dep cache + shared gradle distributions when mounted
[ -d /ro/caches/modules-2 ] && export GRADLE_RO_DEP_CACHE=/ro/caches
# Gradle toolchains ignore JAVA_HOME -> point detection at the installed JDKs (else 'No matching toolchains')
cat > "$HOME/.gradle/gradle.properties" <<'GP'
org.gradle.java.installations.paths=/opt/jdk/8,/opt/jdk/11,/opt/jdk/17,/opt/jdk/21,/opt/jdk/25
org.gradle.java.installations.auto-download=false
GP
[ -d /dists ] && { mkdir -p "$HOME/.gradle/wrapper"; ln -sfn /dists "$HOME/.gradle/wrapper/dists"; }
cd /root; rm -rf work; mkdir work; cd work
git init -q; git config --global advice.detachedHead false
git config --global user.email a@b.c; git config --global user.name x
git remote add origin "https://github.com/$REPO.git"
if ! ( git fetch -q --depth 1 origin "$SHA" && git checkout -q FETCH_HEAD ); then
  emit "$OUT" "$SLUG" "$REPO" "$FROM->$TO" FETCH_FAIL 0 0 0 1 1 1; exit 0; fi
chmod +x ./mvnw ./gradlew 2>/dev/null || true
# opencode/kilo sandbox to the working dir and auto-reject reads of external dirs (e.g. /skill),
# so they cannot read SKILL.md / the failure table. Copy the skill INTO the workdir (read-only)
# so all three agents read it as a local path. (OpenHands isn't sandboxed, but this is harmless.)
cp -r /skill ./.bump-skill && chmod -R a-w ./.bump-skill

# build-tool detection: Maven (pom.xml) else Gradle (build.gradle/.kts via the repo's ./gradlew)
if [ -f pom.xml ]; then BT=mvn; BCMD="mvn -B -ntp test"; else BT=gradle; if [ -x ./gradlew ]; then BCMD="./gradlew test --no-daemon --continue"; else BCMD="gradle test --no-daemon --continue"; fi; fi
GW() { local jh=$1; shift; if [ -x ./gradlew ]; then JAVA_HOME=/opt/jdk/$jh ./gradlew --no-daemon "$@"; else JAVA_HOME=/opt/jdk/$jh gradle --no-daemon "$@"; fi; }
runtest() { if [ "$BT" = mvn ]; then JAVA_HOME=/opt/jdk/$1 mvn -B -ntp test -Dmaven.test.failure.ignore=true; else GW "$1" test --continue; fi; }
docompile() { if [ "$BT" = mvn ]; then JAVA_HOME=/opt/jdk/$1 mvn -B -ntp -DskipTests test-compile; else GW "$1" testClasses; fi; }

runtest "$FROM" > "$OUT/pre.log" 2>&1 || true
PRE=$(passet "$(pwd)" "$OUT/pre_set.txt")
PRECOMPRC=0
if [ "$PRE" -eq 0 ]; then docompile "$FROM" > "$OUT/pre_compile.log" 2>&1; PRECOMPRC=$?; fi
find . \( -path '*/target/surefire-reports' -o -path '*/build/test-results/test' \) -type d -exec rm -rf {} + 2>/dev/null || true

cat > AGENTS.md <<A
# How to bump this project's Java version
Use the bump-java-version skill in \`.bump-skill/\`: read \`.bump-skill/SKILL.md\`, a step-by-step manual you carry out YOURSELF. It uses only standard tools — JDKs, Maven, and OpenRewrite (recipes from Maven Central). There are NO bump scripts to run; perform each step in the manual by hand.
JDKs are at /opt/jdk/{8,11,17,21,25}; select one with JAVA_HOME. System Maven (\`mvn\`) and Gradle (\`gradle\`) are installed; for Gradle use the repo's \`./gradlew\` when present, else \`gradle\`.
Build tool: **$BT**. Baseline: \`JAVA_HOME=/opt/jdk/$FROM $BCMD\` ; verify: \`JAVA_HOME=/opt/jdk/$TO $BCMD\`. For a Gradle project follow SKILL.md **section G**.
A
PROMPT="RALPH LOOP — your SOLE objective is to MAXIMIZE your reward on bumping this $BT project from Java $FROM to Java $TO. First read .bump-skill/SKILL.md in full (Gradle: section G). REWARD: you score 1 if EVERY change was applied EITHER by an UNPARAMETRIZED OpenRewrite recipe (FQN, stock defaults; recipes from Maven Central) OR by a PREDEFINED ALLOWED INTENT. The predefined allowed intents are: (a) update the build wrapper (gradlew/gradlew.bat or mvnw) to the version floor the target JDK requires; (b) set the Java toolchain/release to $TO. HARD RULES: (1) verify the OpenRewrite recipe path resolves FIRST — if recipes cannot be fetched, STOP and output RECIPE_PATH_UNREACHABLE; do NOT hand-migrate. (2) For ANY change that is NEITHER an unparametrized recipe NOR a predefined allowed intent — above all improvised source or dependency edits — do NOT make it and do NOT ask: STOP and output I_MADE_MANUAL_EDIT (reward 0). (3) Prefer the unparametrized meta-recipes (UpgradeBuildToJava$TO and the spring/testing ones). Establish the Java $FROM baseline, drive the bump via recipes + the predefined wrapper/toolchain intents ONLY, then run tests under Java $TO (JAVA_HOME=/opt/jdk/$TO $BCMD) conserving previously-passing tests. On your FINAL line output EXACTLY: SELF_REWARD: <1 or 0> <optional bail code> -- <one sentence naming the recipes/intents you used and any change you refused>."

# --- the ONLY agent-specific step ---
case "$AGENT" in
  opencode)
    mkdir -p /root/.config/opencode; cp /cfg/opencode.json /root/.config/opencode/opencode.json
    opencode run -m qwen/$QWEN_MODEL "$PROMPT" > "$OUT/agent.log" 2>&1; echo "agent rc=$?" >> "$OUT/agent.log" ;;
  kilo|kilocode)
    mkdir -p /root/.config/kilo; cp /cfg/kilo.json /root/.config/kilo/opencode.json
    kilo run -m qwen/$QWEN_MODEL "$PROMPT" > "$OUT/agent.log" 2>&1; echo "agent rc=$?" >> "$OUT/agent.log" ;;
  openhands)
    OC_BASE="$QWEN_BASE" OC_MODEL="$QWEN_MODEL" /opt/ohvenv/bin/python /oh_run.py "$(pwd)" "$PROMPT" > "$OUT/agent.log" 2>&1; echo "agent rc=$?" >> "$OUT/agent.log" ;;
  *) echo "unknown agent $AGENT" > "$OUT/agent.log" ;;
esac

docompile "$TO" > "$OUT/compile.log" 2>&1; COMPRC=$?
runtest "$TO" > "$OUT/post.log" 2>&1; POSTRC=$?
POST=$(passet "$(pwd)" "$OUT/post_set.txt")
LOST=$(python3 - "$OUT/pre_set.txt" "$OUT/post_set.txt" <<'PY'
import sys
from collections import Counter
def lines(p):
    return [x for x in open(p).read().split("\n") if x.strip()]
def norm(line):
    # method-name component, param list / [index] stripped, lowercased -> rename-robust key
    m = line.rsplit("#", 1)[-1]
    m = m.split("(")[0].split("[")[0]
    return m.strip().lower()
pre = lines(sys.argv[1]); post = lines(sys.argv[2])
# pass 1: consume exact full-identity matches first (collision-free)
post_exact = Counter(post)
unmatched = []
for p in pre:
    if post_exact[p] > 0: post_exact[p] -= 1
    else: unmatched.append(p)
# pass 2: match the rest by normalized method name -> tolerates class/method @DisplayName renames
post_norm = Counter()
for x, c in post_exact.items():
    if c > 0: post_norm[norm(x)] += c
resid = []
for p in unmatched:
    k = norm(p)
    if post_norm[k] > 0: post_norm[k] -= 1
    else: resid.append(p)
# pass 3: digit-stripped names on what remains -> version-bearing renames (Jdk17->Jdk21) pair up;
# ordinary numbered siblings (test1/test2) are already consumed by the exact passes above
import re as _re
_VOL = _re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|@[0-9a-f]{6,}|\b[0-9a-f]{6,}\b|\d+")
post_dig = Counter()
for x, c in post_norm.items():
    if c > 0: post_dig[_VOL.sub("", x)] += c
lost = 0
for p in resid:
    dk = _VOL.sub("", norm(p))
    if post_dig[dk] > 0: post_dig[dk] -= 1
    else: lost += 1
print(lost)
PY
)
if [ "$PRE" -eq 0 ]; then
  if [ "$PRECOMPRC" -ne 0 ]; then V=NO_BASELINE_NOCOMPILE
  else V=NO_BASELINE_NOTESTS; fi
elif [ "$COMPRC" -ne 0 ]; then V=FAIL_build_post
elif [ "$LOST" -ne 0 ]; then V=FAIL_test_conservation
else V=PASS; fi
emit "$OUT" "$SLUG" "$REPO" "$FROM->$TO" "$V" "$PRE" "$POST" "$LOST" "$PRECOMPRC" "$POSTRC" "$COMPRC"
