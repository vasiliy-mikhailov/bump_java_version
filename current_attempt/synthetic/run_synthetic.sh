#!/bin/bash
# P17 synthetic regression fortress runner (PARALLEL, deterministic): per situation -> copy repo, baseline
# under jv_from, apply the situation's canonical rewrite.yml via the real bapply, gate under jv_to with the
# fixed score.py, compare verdict to the expected outcome. Reward = (unique situations) * 0.9^(duplicates).
# Situations are independent -> run them concurrently (JOBS). No CWE scan (the fortress never checks CWE).
set -uo pipefail
P=/home/vmihaylov/bump-java-version
S=$P/current_attempt/synthetic
I=$P/current_attempt/current_iteration
R=$I/rung2
JOBS=${JOBS:-8}
export PATH="$I/hoptools:$PATH"
export BJV_NET=mvn-cache BJV_M2=/home/vmihaylov/.m2-fitness BJV_SETTINGS=/home/vmihaylov/maven-config/settings.xml \
  BJV_GRADLE_RO=/home/vmihaylov/.gradle-fitness BJV_GRADLE_DISTS=/home/vmihaylov/.gradle-dists
OUT=/tmp/synthetic_out; rm -rf "$OUT"; mkdir -p "$OUT"

run_one() {  # $1=situation $2=dir $3=kind $4=from $5=to $6=expected
  local SIT=$1 DIR=$2 KIND=$3 FROM=$4 TO=$5 EXPECT=$6
  local SLUG=syn_$SIT
  local O=$OUT/$SLUG; mkdir -p "$O"
  local BJV_WS=/tmp/bjv_ws/$SLUG
  export BJV_WS BJV_FROM=$FROM BJV_TO=$TO
  local PYscore="docker run --rm -v $BJV_WS:$BJV_WS -v $I/tools:/t:ro -v $O:$O python:3-slim python3 /t/score.py"
  if [ "$KIND" = router ]; then
    local DET BUMP V
    DET=$(docker run --rm -v "$S/$DIR:/r:ro" -v "$I/rung2/detect_java.py:/d.py:ro" python:3-slim python3 /d.py /r 2>/dev/null)
    BUMP=$(echo "$DET" | python3 -c "import sys,json;print(json.load(sys.stdin).get('bumpable'))" 2>/dev/null)
    V=NOT_A_BUMP; [ "$BUMP" = "True" ] && V="BUMPABLE"
    [ "$V" = "$EXPECT" ] && echo -e "$SIT\t$V\t$EXPECT\tok" > "$O/result.line" || echo -e "$SIT\t$V\t$EXPECT\tFAIL" > "$O/result.line"
    return
  fi
  docker run --rm -v /tmp/bjv_ws:/w alpine rm -rf "/w/$SLUG" 2>/dev/null; mkdir -p "$BJV_WS"
  cp -r "$S/$DIR/." "$BJV_WS/"
  if ! bjv from build >"$O/pre_build.log" 2>&1; then echo -e "$SIT\tBASELINE_NOCOMPILE\t$EXPECT\tFAIL" > "$O/result.line"; return; fi
  bjv from test >"$O/pre_test.log" 2>&1 || true
  $PYscore passet "$BJV_WS" "$O/pre_set.txt" >/dev/null 2>&1
  find "$BJV_WS" -path '*/target/surefire-reports' -type d -exec rm -rf {} + 2>/dev/null || true
  local PV MJ DP; if [ "$TO" = 25 ]; then PV=6.41.0 MJ=3.36.0 DP=1.55.3; else PV=6.40.0 MJ=3.35.0 DP=1.55.0; fi
  docker run --rm --network mvn-cache -e HOME=/root -e BJV_FROM="$FROM" \
    -e BJV_REWRITE_PLUGIN=$PV -e BJV_REWRITE_MIGRATE=$MJ -e BJV_REWRITE_DEPS=$DP \
    -v "$BJV_WS:/work" -w /work -v /home/vmihaylov/.m2-fitness:/root/.m2 \
    -v /home/vmihaylov/maven-config/settings.xml:/root/.m2/settings.xml:ro -v "$R/bin:/r2bin:ro" \
    bjv-alljdk /r2bin/bapply >"$O/apply.log" 2>&1 || true
  docker run --rm -v "$BJV_WS:/w" alpine sh -c "cd /w && find . -type d \( -path '*/target/classes' -o -path '*/target/test-classes' \) -exec rm -rf {} + 2>/dev/null; true"
  bjv to build >"$O/compile.log" 2>&1; local BRC=$?
  bjv to test  >"$O/post.log"    2>&1; local TRC=$?
  # no CWE scan: the fortress never gates on CWE, so pass a nonexistent json (score.py -> CWE unknown, non-gating)
  $PYscore final "$BJV_WS" "$O/pre_set.txt" "$BJV_FROM" "$BJV_TO" "$BRC" "$TRC" "$O/none.json" "$O" >"$O/verdict.txt" 2>&1 || true
  local V; V=$(grep -aoE 'VERDICT [A-Za-z_]+' "$O/verdict.txt" | awk '{print $2}' | head -1); V=${V:-NO_VERDICT}
  [ "$V" = "$EXPECT" ] && echo -e "$SIT\t$V\t$EXPECT\tok" > "$O/result.line" || echo -e "$SIT\t$V\t$EXPECT\tFAIL" > "$O/result.line"
  docker run --rm -v /tmp/bjv_ws:/w alpine rm -rf "/w/$SLUG" 2>/dev/null || true
}

mapfile -t ROWS < <(python3 -c '
import json, sys
for r in json.load(open(sys.argv[1])):
    print(r["situation"], r["dir"], r["kind"], r["from"], r["to"], r["expected"])
' "$S/manifest.json")
echo "running ${#ROWS[@]} situations, up to $JOBS in parallel ..."
for row in "${ROWS[@]}"; do
  while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do sleep 2; done
  read -r SIT DIR KIND FROM TO EXPECT <<< "$row"
  run_one "$SIT" "$DIR" "$KIND" "$FROM" "$TO" "$EXPECT" &
done
wait

results="$OUT/results.tsv"; cat "$OUT"/syn_*/result.line 2>/dev/null | sort > "$results"
echo "===== FORTRESS SUMMARY ====="
column -t -s $'\t' "$results" 2>/dev/null || cat "$results"
python3 - "$S/manifest.json" "$results" <<'PY'
import sys, json
mani = json.load(open(sys.argv[1])); ids = [r["situation"] for r in mani]
uniq = len(set(ids)); dupes = len(ids) - uniq
rows = [l.split("\t") for l in open(sys.argv[2]).read().splitlines() if l.strip()]
oks = sum(1 for r in rows if len(r) >= 4 and r[3] == "ok")
print(f"\nsituations in suite: {len(ids)}  unique: {uniq}  duplicates: {dupes}")
print(f"matched expected outcome: {oks}/{len(rows)}")
print(f"P17 reward (unique x 0.9^duplicates): {uniq * (0.9 ** dupes):.4f}")
print("REGRESSIONS:", [r[0] for r in rows if len(r) >= 4 and r[3] != "ok"] or "none")
PY
