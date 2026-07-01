#!/bin/bash
# STEP 1 — detect a repo's real current Java level + bumpability (static, no build). Args: REPO SHA [OUT.json]
REPO=$1; SHA=$2; OUT=${3:-/dev/stdout}
CI=/home/vmihaylov/bump-java-version/current_attempt/current_iteration
WS=/tmp/detect_ws/$(echo $REPO | tr / _)
rm -rf "$WS" 2>/dev/null
mkdir -p $WS
( cd $WS && git init -q && git remote add origin https://github.com/$REPO.git   && ( git fetch -q --depth 1 origin $SHA && git checkout -q FETCH_HEAD        || ( git fetch -q --depth 1 origin HEAD && git checkout -q FETCH_HEAD ) ) ) 2>/dev/null   || { echo '{"error":"clone"}' > $OUT; exit 0; }
docker run --rm -v $WS:$WS -v $CI/rung2/detect_java.py:/d.py:ro python:3-slim python3 /d.py $WS > $OUT 2>/dev/null
[ "$OUT" != /dev/stdout ] && [ ! -s "$OUT" ] && echo '{"error":"detect"}' > $OUT
# module-level: emit the per-module list (tool + from->to per module) beside detect.json
[ "$OUT" != /dev/stdout ] && docker run --rm -v $WS:$WS -v $CI/tools/detect_modules.py:/dm.py:ro python:3-slim python3 /dm.py $WS > "$(dirname "$OUT")/modules.jsonl" 2>/dev/null || true
rm -rf "$WS" 2>/dev/null
