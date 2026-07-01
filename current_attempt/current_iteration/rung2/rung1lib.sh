# Rung-1 shared harness. Source with:  SLUG=<slug> FROM=8 TO=11 . rung1lib.sh
# Provides: r1_clone <repo> <sha> ; r1_baseline (echoes pre-count or NOCOMPILE) ;
#           r1_apply (runs $BJV_WS/rewrite.yml under jv_from) ; r1_gate <edits> (writes verdict + score)
I=/home/vmihaylov/bump-java-version/current_attempt/current_iteration
export PATH="$I/hoptools:$PATH"
export BJV_WS=/tmp/bjv_ws/$SLUG BJV_FROM=$FROM BJV_TO=$TO BJV_NET=mvn-cache \
  BJV_M2=/home/vmihaylov/.m2-fitness BJV_SETTINGS=/home/vmihaylov/maven-config/settings.xml \
  BJV_GRADLE_RO=/home/vmihaylov/.gradle-fitness BJV_GRADLE_DISTS=/home/vmihaylov/.gradle-dists
export O=/tmp/hoptest/$SLUG; mkdir -p "$O"
PY(){ docker run --rm -v "$BJV_WS:$BJV_WS" -v "$I/tools:/t:ro" -v "$O:$O" python:3-slim python3 /t/score.py "$@"; }
EDIT_ADDEXPORTS(){ docker run --rm -v "$BJV_WS:$BJV_WS" -v "$I/tools:/t:ro" python:3-slim python3 /t/edit_pom_addexports.py "$@"; }
ALPINE(){ docker run --rm -v "$BJV_WS:$BJV_WS" alpine "$@"; }   # for sed/grep edits on the workspace

r1_clone(){ # repo sha
  docker run --rm -v /tmp/bjv_ws:/w alpine rm -rf "/w/$SLUG" 2>/dev/null
  mkdir -p "$BJV_WS"
  git clone -q "https://github.com/$1.git" "$BJV_WS" 2>"$O/clone.log" || { echo FETCH_FAIL; return 1; }
  git -C "$BJV_WS" checkout -q "$2" 2>>"$O/clone.log" || { echo FETCH_FAIL; return 1; }
  [ -f "$BJV_WS/pom.xml" ] && echo "BUILDTOOL=maven" || echo "BUILDTOOL=gradle"
}
r1_baseline(){ # echoes integer pre-pass count, or NOCOMPILE
  find "$BJV_WS" \( -path '*/target/surefire-reports' -o -path '*/build/test-results' \) -type d -exec rm -rf {} + 2>/dev/null  # drop COMMITTED stale test-results so pre_set reflects a REAL baseline run, not checked-in XML (phantom-baseline guard)
  bjv from build >"$O/pre_build.log" 2>&1 || { echo NOCOMPILE; return 1; }
  bjv from test  >"$O/pre_test.log"  2>&1; local PTRC=$?
  if [ "$PTRC" = 124 ] || [ "$PTRC" = 137 ]; then echo BASELINE_TIMEOUT; return 1; fi
  PY passet "$BJV_WS" "$O/pre_set.txt" >/dev/null 2>&1
  local n; n=$(grep -c . "$O/pre_set.txt" 2>/dev/null || echo 0)
  find "$BJV_WS" \( -path '*/target/surefire-reports' -o -path '*/build/test-results/test' \) -type d -exec rm -rf {} + 2>/dev/null
  echo "${n:-0}"
}
r1_apply(){ # applies $BJV_WS/rewrite.yml under jv_from; log -> $O/apply.log
  local RNAME; RNAME=$(grep -m1 '^name:' "$BJV_WS/rewrite.yml"|awk '{print $2}'); RNAME=${RNAME:-com.bjv.Bump}
  if [ -f "$BJV_WS/pom.xml" ]; then
    bjv from run "mvn -B -ntp -U -Denforcer.skip=true org.openrewrite.maven:rewrite-maven-plugin:6.40.0:run -Drewrite.configLocation=rewrite.yml -Drewrite.activeRecipes=$RNAME -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.35.0,org.openrewrite.recipe:rewrite-spring:6.31.0" >"$O/apply.log" 2>&1
  else
    bjv from run "printf '%s' 'initscript{repositories{gradlePluginPortal();mavenCentral()};dependencies{classpath(\"org.openrewrite:plugin:latest.release\")}};rootProject{apply plugin: org.openrewrite.gradle.RewritePlugin;dependencies{rewrite(\"org.openrewrite.recipe:rewrite-migrate-java:latest.release\");rewrite(\"org.openrewrite.recipe:rewrite-spring:latest.release\")};rewrite{activeRecipe(\"'$RNAME'\")}}' > /tmp/rw.init.gradle && GRADLE_OPTS='-Xmx6g -XX:MaxMetaspaceSize=1g' ./gradlew --no-daemon --init-script /tmp/rw.init.gradle rewriteRun" >"$O/apply.log" 2>&1
  fi
  echo "apply rc=$? (see $O/apply.log)"
}
r1_gate(){ # arg1 = number of manual edits made
  local EDITS=${1:-0}
  # force a genuine JDK_to recompile: drop stale class outputs (else incremental skip => gate reads jv_from bytecode)
  ALPINE sh -c "cd $BJV_WS && find . \( -name build.gradle -o -name build.gradle.kts -o -name settings.gradle -o -name settings.gradle.kts \) 2>/dev/null | while read g; do d=\$(dirname \"\$g\"); rm -rf \"\$d/build\" \"\$d/.gradle\"; done; find . -name pom.xml 2>/dev/null | while read p; do d=\$(dirname \"\$p\"); rm -rf \"\$d/target\"; done; rm -rf ./.gradle 2>/dev/null; find . -maxdepth 1 -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -delete 2>/dev/null; find . -type f -name '*.mv.db' -delete 2>/dev/null; true"
  bjv to build >"$O/compile.log" 2>&1; local BRC=$?
  # fresh-clone symmetry, REACTIVE (only on an actual collision, so committed hand-written sources under a
  # dir named 'generated' are NEVER deleted from a repo that builds fine): if the gate build failed because
  # an annotation processor hit generated-source residue the build-output clean missed (it lives under src/),
  # strip that residue and rebuild once. Signature: javac "Attempt to recreate a file" / "duplicate class".
  if [ "$BRC" != 0 ] && grep -qaE "Attempt to recreate a file|duplicate class" "$O/compile.log"; then
    PY resetgen "$BJV_WS" >"$O/resetgen.log" 2>&1 || true
    bjv to build >"$O/compile.log" 2>&1; BRC=$?
  fi
  if [ "$BRC" = 124 ] || [ "$BRC" = 137 ]; then echo "UNSCORABLE_BUILD_TIMEOUT (build_rc=$BRC edits=$EDITS)"; return 0; fi
  bjv to test  >"$O/post.log"    2>&1; local TRC=$?
  if [ "$TRC" = 124 ] || [ "$TRC" = 137 ]; then echo "UNSCORABLE_TEST_TIMEOUT (test_rc=$TRC edits=$EDITS)"; return 0; fi
  jvm-run "$BJV_TO" jvmjob run "cd /work && osv-scanner scan source --offline-vulnerabilities --format json -r ." >"$O/cwe.json" 2>"$O/scan.err" || true
  PY final "$BJV_WS" "$O/pre_set.txt" "$BJV_FROM" "$BJV_TO" "$BRC" "$TRC" "$O/cwe.json" "$O" | tee "$O/verdict.txt"; local PRC=${PIPESTATUS[0]}
  if [ "$PRC" != 0 ] || ! grep -aq "^VERDICT " "$O/verdict.txt"; then rm -f "$O/verdict.txt"; echo "UNSCORABLE_SCORER_ERROR (scorer_rc=$PRC edits=$EDITS)"; return 0; fi
  if grep -aq "VERDICT PASS" "$O/verdict.txt"; then
    docker run --rm python:3-slim python3 -c "print(f'SCORE edits=$EDITS  score={0.9**$EDITS:.3f}')" | tee "$O/score.txt"
  else echo "SCORE gate_fail score=0 (edits=$EDITS)" | tee "$O/score.txt"; fi
}
