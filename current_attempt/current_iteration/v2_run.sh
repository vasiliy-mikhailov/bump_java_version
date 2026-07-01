#!/bin/bash
# v2 end-to-end (single-shot): clone -> baseline -> generate_program (LLM -> rewrite.yml) -> check_program
# -> run the rewrite.yml via the OpenRewrite plugin (once, under jv_from) -> combined gate -> score.
#   v2_run.sh REPO SHA FROM TO SLUG ; env: OC_BASE OC_MODEL OC_KEY
set -uo pipefail
REPO=$1; SHA=$2; FROM=$3; TO=$4; SLUG=$5
ITER=/home/vmihaylov/bump-java-version/current_attempt/current_iteration
SK=/home/vmihaylov/bump-java-version/current_attempt/.agents/skills/bump-java-$FROM-to-$TO/SKILL.md
export PATH="$ITER/hoptools:$PATH"
WS=/tmp/bjv_ws/$SLUG
OUT=${OUT_DIR:-$ITER/out}/$SLUG; mkdir -p "$OUT"
YML="$OUT/program.yml"
export BJV_WS="$WS" BJV_FROM="$FROM" BJV_TO="$TO" BJV_NET=mvn-cache \
  BJV_M2=/home/vmihaylov/.m2-fitness BJV_SETTINGS=/home/vmihaylov/maven-config/settings.xml \
  BJV_GRADLE_RO=/home/vmihaylov/.gradle-fitness BJV_GRADLE_DISTS=/home/vmihaylov/.gradle-dists
PY() { docker run --rm -v "$WS:$WS" -v "$OUT:$OUT" -v "$ITER/tools:/t:ro" -v "$ITER/catalog:/cat:ro" python:3-slim python3 "$@"; }
emit() { printf '{\n "slug":"%s",\n "hop":"%s->%s",\n "verdict":"%s"\n}\n' "$SLUG" "$FROM" "$TO" "$1" > "$OUT/result.json"; }

# 1. workspace
docker run --rm -v /tmp/bjv_ws:/wsroot alpine rm -rf "/wsroot/$SLUG" 2>/dev/null || true
mkdir -p "$WS"
git clone -q "https://github.com/$REPO.git" "$WS" 2>>"$OUT/clone.log" || { emit FETCH_FAIL; exit 0; }
git -C "$WS" checkout -q "$SHA" 2>>"$OUT/clone.log" || { emit FETCH_FAIL; exit 0; }
BT=gradle; [ -f "$WS/pom.xml" ] && BT=mvn

# 2. baseline under jv_from
bjv from build > "$OUT/pre_build.log" 2>&1 || { emit NO_BASELINE_NOCOMPILE; exit 0; }
bjv from test  > "$OUT/pre_test.log"  2>&1 || true
PRE=$(PY /t/score.py passet "$WS" "$OUT/pre_set.txt" 2>/dev/null | tail -1); PRE=${PRE:-0}
find "$WS" \( -path '*/target/surefire-reports' -o -path '*/build/test-results/test' \) -type d -exec rm -rf {} + 2>/dev/null || true
[ "$PRE" = 0 ] && { emit NO_BASELINE_NOTESTS; exit 0; }

# 3. generate_program (LLM, per-hop skill) -> rewrite.yml
docker run --rm --network mvn-cache -e OC_BASE -e OC_MODEL -e OC_KEY \
  -v "$WS:$WS" -v "$ITER/tools:/t:ro" -v "$SK:/skill.md:ro" python:3-slim \
  python3 /t/generate_program.py /skill.md "$WS" "$FROM" "$TO" > "$YML" 2>"$OUT/generate.log" \
  || { emit FAIL_GENERATE; tail -3 "$OUT/generate.log"; exit 0; }

# 4. static anti-cheat (rewrite.yml recipeList vs catalog)
CHK=$(docker run --rm -v "$OUT:$OUT" -v "$ITER/tools:/t:ro" -v "$ITER/catalog:/cat:ro" python:3-slim python3 /t/check_program.py "$YML" /cat/recipes.txt "$TO" 2>&1)
echo "$CHK" > "$OUT/check.log"
case "$CHK" in OK*) ;; *) emit FAIL_CHEAT; echo "check: $CHK"; exit 0;; esac
PARAM=$(echo "$CHK" | grep -oE 'PARAMETRIC=[0-9]+' | cut -d= -f2); PARAM=${PARAM:-0}

# 5. run the rewrite.yml via the OpenRewrite plugin ONCE under jv_from (where the project compiles)
cp "$YML" "$WS/rewrite.yml"
RNAME=$(grep -m1 '^name:' "$YML" | awk '{print $2}'); RNAME=${RNAME:-com.bjv.Bump}
PV=6.40.0; MJ=3.35.0; [ "$TO" = 25 ] && { PV=6.41.0; MJ=3.36.0; }
if [ "$BT" = mvn ]; then
  RUN="mvn -B -ntp -U -Denforcer.skip=true org.openrewrite.maven:rewrite-maven-plugin:$PV:run -Drewrite.configLocation=rewrite.yml -Drewrite.activeRecipes=$RNAME -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:$MJ,org.openrewrite.recipe:rewrite-spring:6.31.0"
else
  RUN="printf '%s' 'initscript{repositories{gradlePluginPortal();mavenCentral()};dependencies{classpath(\"org.openrewrite:plugin:latest.release\")}};rootProject{apply plugin: org.openrewrite.gradle.RewritePlugin;dependencies{rewrite(\"org.openrewrite.recipe:rewrite-migrate-java:latest.release\");rewrite(\"org.openrewrite.recipe:rewrite-spring:latest.release\")};rewrite{activeRecipe(\"$RNAME\")}}' > /tmp/rw.init.gradle && ./gradlew --no-daemon --init-script /tmp/rw.init.gradle rewriteRun"
fi
bjv from run "$RUN" > "$OUT/apply.log" 2>&1 || echo "(rewrite rc=$?)" >> "$OUT/apply.log"

# 6. combined gate under jv_to
bjv to build > "$OUT/compile.log" 2>&1; COMPRC=$?
bjv to test  > "$OUT/post.log"    2>&1; POSTRC=$?
bjv to run "osv-scanner scan source --offline-vulnerabilities -r . --format json" > "$OUT/cwe.json" 2>/dev/null || true
# recipe-only path: edits=0 (a rewrite.yml can't hand-edit); PARAM = model-chosen parametric recipes
PY /t/score.py final "$WS" "$OUT/pre_set.txt" "$FROM" "$TO" "$COMPRC" "$POSTRC" "$OUT/cwe.json" "$OUT" "$PARAM" 0
