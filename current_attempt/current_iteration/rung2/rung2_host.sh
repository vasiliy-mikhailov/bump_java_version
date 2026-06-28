#!/bin/bash
# Rung-2 host orchestrator: clone+baseline -> OpenHands+Qwen agent -> diff -> gate.
# Args: REPO SHA SLUG [FROM=8] [TO=11]. Reuses the repo rung1lib.sh. Emits $O/{agent.log,agent.diff,rewrite.yml,verdict.txt,param.txt}
set -uo pipefail
REPO=$1; SHA=$2; SLUG=$3; FROM=${4:-8}; TO=${5:-11}
export SLUG FROM TO
. /home/vmihaylov/java_8_11_17_to_java_21/current_attempt/current_iteration/rung2/rung1lib.sh

echo "=== [1] clone+baseline $REPO @ $SHA (jv$FROM) ==="
BT=$(r1_clone "$REPO" "$SHA") || { echo "CLONE_FAIL"; exit 0; }
echo "$BT"
PRE=$(r1_baseline)
echo "pre_pass=$PRE"
case "$PRE" in ''|*[!0-9]*) echo "RESULT $SLUG NO_GREEN_BASELINE pre=$PRE"; exit 0;; esac
[ "$PRE" -lt ${BJV_MIN_TESTS:-5} ] && { echo "RESULT $SLUG NO_GREEN_BASELINE pre=$PRE<${BJV_MIN_TESTS:-5}"; exit 0; }

echo "=== [2] OpenHands+Qwen agent (no limits) ==="
set -a; . /home/vmihaylov/java_8_11_17_to_java_21/.env; set +a
OHRUN=/home/vmihaylov/java_8_11_17_to_java_21/current_attempt/current_iteration/oh_run.py
AGENT_NAME="bjvagent_${SLUG}_$$"
timeout -k 120 "${BJV_AGENT_GUARD:-14400}" docker run --rm --init --name "$AGENT_NAME" --network mvn-cache -e OC_KEY="$PROPOSER_API_KEY" \
  -v "$BJV_WS:/work" -v "$OHRUN:/oh_run.py:ro" -v /home/vmihaylov/java_8_11_17_to_java_21/current_attempt/current_iteration/rung2/bin:/r2bin:ro \
  -v /home/vmihaylov/java_8_11_17_to_java_21/current_attempt/current_iteration/rung2/rung2_drive.sh:/drive.sh:ro -v /home/vmihaylov/java_8_11_17_to_java_21/current_attempt/.agents/skills/bump-java-${FROM}-to-${TO}/SKILL.md:/skill.md:ro \
  -v /home/vmihaylov/.m2-fitness:/root/.m2 -v /home/vmihaylov/maven-config/settings.xml:/root/.m2/settings.xml:ro \
  -v /home/vmihaylov/.gradle-fitness:/ro:ro -v /home/vmihaylov/.gradle-dists:/dists:ro \
  --entrypoint bash bump-allagents-sweep:latest /drive.sh "$FROM" "$TO" > "$O/agent.log" 2>&1
AGRC=$?
if [ "$AGRC" = 124 ] || [ "$AGRC" = 137 ]; then docker rm -f "$AGENT_NAME" >/dev/null 2>&1 || true; fi
echo "agent rc=$AGRC"

echo "=== [3] capture diff + program ==="
git -C "$BJV_WS" diff -- . ':(exclude)*/target/*' ':(exclude)*/build/*' ':(exclude)*/.gradle/*' > "$O/agent.diff" 2>/dev/null || true
git -C "$BJV_WS" status --short > "$O/agent.status" 2>/dev/null || true
if [ -f "$BJV_WS/rewrite.yml" ]; then
  cp "$BJV_WS/rewrite.yml" "$O/rewrite.yml"
  PARAM=$(docker run --rm -v "$O:$O" -v "$I/tools:/t:ro" python:3-slim python3 /t/check_program.py "$O/rewrite.yml" x "$TO" 2>/dev/null | grep -oE 'PARAMETRIC=[0-9]+' | cut -d= -f2)
else PARAM=0; fi
PARAM=${PARAM:-0}; echo "$PARAM" > "$O/param.txt"
echo "parametric_recipes=$PARAM ; diff_lines=$(wc -l <"$O/agent.diff" 2>/dev/null)"

# Gate the project as its ORIGINAL build tool (P16 structural fix; a prose skill guard can't stop a
# stochastic agent). The pom.xml-based detector (jvmjob/bbuild) flips to Maven if the agent introduced a
# pom.xml in a Gradle project (or vice-versa), breaking the gate (deps live in the real tool). Drop any
# agent-introduced wrong-tool build file before gating.
case "$BT" in
  *gradle) [ -f "$BJV_WS/pom.xml" ] && { echo "gate-fix: dropping agent-introduced pom.xml (project is Gradle)"; rm -f "$BJV_WS/pom.xml"; } ;;
  *maven)  for g in build.gradle build.gradle.kts settings.gradle settings.gradle.kts; do [ -f "$BJV_WS/$g" ] && { echo "gate-fix: dropping agent-introduced $g (project is Maven)"; rm -f "$BJV_WS/$g"; }; done ;;
esac
echo "=== [4] gate (host bjv + score.py) ==="
r1_gate 0   # verdict only; final reward computed after the scoring agent supplies manual-edit count
V=$(grep -aoE 'VERDICT [A-Z_]+' "$O/verdict.txt" | awk '{print $2}')
echo "RESULT $SLUG verdict=$V parametric=$PARAM (edits TBD by scoring agent)"
