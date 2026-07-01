#!/bin/bash
# Sealed-hop driver (one repo). Runs on the orchestrator host (needs docker + the hop tools).
#   hop_drive_one.sh REPO SHA FROM TO SLUG [AGENT=openhands]   ; env: OC_KEY
# Flow: clone -> baseline under sealed jv_from -> agent in the JDK-less controller (skill + bjv tools)
#       -> combined gate under sealed jv_to (build + conserve + target==jv_to + CWE scan).
set -uo pipefail
REPO=$1; SHA=$2; FROM=$3; TO=$4; SLUG=$5; AGENT=${6:-openhands}
ITER=/home/vmihaylov/java_8_11_17_to_java_21/current_attempt/current_iteration
SKILL=/home/vmihaylov/java_8_11_17_to_java_21/current_attempt/.agents/skills/bump-java-version
export PATH="$ITER/hoptools:$PATH"
WS=/tmp/bjv_ws/$SLUG
OUT=${OUT_DIR:-$ITER/out}/$SLUG; mkdir -p "$OUT"
export BJV_WS="$WS" BJV_FROM="$FROM" BJV_TO="$TO" BJV_NET=mvn-cache \
  BJV_M2=/home/vmihaylov/.m2-fitness BJV_SETTINGS=/home/vmihaylov/maven-config/settings.xml \
  BJV_GRADLE_RO=/home/vmihaylov/.gradle-fitness BJV_GRADLE_DISTS=/home/vmihaylov/.gradle-dists
QWEN_BASE="https://inference.mikhailov.tech/qwen-3.6-27b-fp8/v1"; QWEN_MODEL="qwen-3.6-27b-fp8"

PY() { docker run --rm -v "$WS:$WS" -v "$OUT:$OUT" -v "$ITER/tools:/t:ro" python:3-slim python3 /t/score.py "$@"; }
emit_simple() { printf '{\n "slug": "%s",\n "hop": "%s->%s",\n "verdict": "%s"\n}\n' "$SLUG" "$FROM" "$TO" "$1" > "$OUT/result.json"; }

# 1. workspace — reap any prior run via a ROOT container (sealed builds write root-owned build/.gradle),
#    then clone fresh. A host-side rm can't remove root-owned files; a root container can.
docker run --rm -v /tmp/bjv_ws:/wsroot alpine rm -rf "/wsroot/$SLUG" 2>/dev/null || true
mkdir -p "$WS"
git clone -q "https://github.com/$REPO.git" "$WS" 2>>"$OUT/clone.log" || { echo CLONE_FAIL >> "$OUT/clone.log"; emit_simple FETCH_FAIL; exit 0; }
git -C "$WS" checkout -q "$SHA" 2>>"$OUT/clone.log" || { emit_simple FETCH_FAIL; exit 0; }
# sandbox the skill: copy only the manual, read-only FILE (dir stays writable so cleanup works next run)
mkdir -p "$WS/.bump-skill"; cp "$SKILL/SKILL.md" "$WS/.bump-skill/SKILL.md"; chmod a-w "$WS/.bump-skill/SKILL.md"

# 2. baseline under sealed jv_from
bjv from build > "$OUT/pre_build.log" 2>&1 || { emit_simple NO_BASELINE_NOCOMPILE; exit 0; }
bjv from test  > "$OUT/pre_test.log"  2>&1 || true
PRE=$(PY passet "$WS" "$OUT/pre_set.txt" 2>/dev/null | tail -1); PRE=${PRE:-0}
# clear baseline test results so the post run is measured fresh
find "$WS" \( -path '*/target/surefire-reports' -o -path '*/build/test-results/test' \) -type d -exec rm -rf {} + 2>/dev/null || true
if [ "$PRE" = 0 ]; then emit_simple NO_BASELINE_NOTESTS; exit 0; fi

# 3. agent in the JDK-less controller (skill + bjv tools, recipe-or-bail)
PROMPT="Bump this project from Java $FROM to Java $TO by following the manual in .bump-skill/SKILL.md (read it in full first). You have NO java/mvn/gradle directly — use the sealed-env tools ONLY: 'bjv from build|test' (baseline under Java $FROM), 'bjv to build|test' (verify under Java $TO), 'bjv to run \"<cmd>\"' / 'bjv from run \"<cmd>\"' (run an OpenRewrite recipe in that env), 'bjv scan' (offline CWE scan). Apply every change via an unparametrized OpenRewrite recipe or a predefined allowed intent (update the wrapper, set the Java toolchain/release to $TO); never hand-edit source/deps — bail I_MADE_MANUAL_EDIT instead. Done only when: bjv to build succeeds, the baseline-passing tests still pass under Java $TO, the effective compiler target is $TO, and bjv scan is clean. Report the final result."
docker run --rm --network mvn-cache \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WS:$WS" -w "$WS" -v "$ITER/oh_run.py:/oh_run.py:ro" \
  -e BJV_WS="$WS" -e BJV_FROM="$FROM" -e BJV_TO="$TO" -e BJV_NET=mvn-cache \
  -e BJV_M2="$BJV_M2" -e BJV_SETTINGS="$BJV_SETTINGS" -e BJV_GRADLE_RO="$BJV_GRADLE_RO" -e BJV_GRADLE_DISTS="$BJV_GRADLE_DISTS" \
  -e OC_BASE="$QWEN_BASE" -e OC_MODEL="$QWEN_MODEL" -e OC_KEY="$OC_KEY" \
  --entrypoint /opt/ohvenv/bin/python bjv-controller /oh_run.py "$WS" "$PROMPT" > "$OUT/agent.log" 2>&1
echo "agent rc=$?" >> "$OUT/agent.log"

# 4. combined gate under sealed jv_to
bjv to build > "$OUT/compile.log" 2>&1; COMPRC=$?
# reactive fresh-clone symmetry (see rung1lib): strip generated-source residue ONLY if the gate build collided
# with regeneration, so committed sources under a 'generated' dir are never deleted from a repo that builds
# fine. Signature: javac "Attempt to recreate a file" / "duplicate class".
if [ "$COMPRC" != 0 ] && grep -qaE "Attempt to recreate a file|duplicate class" "$OUT/compile.log"; then
  PY resetgen "$WS" > "$OUT/resetgen.log" 2>&1 || true
  bjv to build > "$OUT/compile.log" 2>&1; COMPRC=$?
fi
bjv to test  > "$OUT/post.log"    2>&1; POSTRC=$?
jvm-run "$TO" "osv-scanner scan source --offline-vulnerabilities -r . --format json" > "$OUT/cwe.json" 2>/dev/null || true
PY final "$WS" "$OUT/pre_set.txt" "$FROM" "$TO" "$COMPRC" "$POSTRC" "$OUT/cwe.json" "$OUT"
