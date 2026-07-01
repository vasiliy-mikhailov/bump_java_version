#!/bin/bash
# One rung-2 repo for ANY hop: migrate -> gate -> score -> reap. Args: REPO SHA SLUG FROM TO
REPO=$1; SHA=$2; SLUG=$3; FROM=$4; TO=$5
CI=/home/vmihaylov/bump-java-version/current_attempt/current_iteration
O=/tmp/hoptest/$SLUG; mkdir -p "$O"
bash $CI/rung2/rung2_host.sh "$REPO" "$SHA" "$SLUG" "$FROM" "$TO" > "$O/host.log" 2>&1
if [ ! -f "$O/verdict.txt" ]; then
  reason=$(grep -aoE "UNSCORABLE_BUILD_TIMEOUT|UNSCORABLE_TEST_TIMEOUT|UNSCORABLE_SCORER_ERROR|BASELINE_TIMEOUT|NO_GREEN_BASELINE|CLONE_FAIL|NOCOMPILE|FETCH_FAIL" "$O/host.log" | head -1)
  printf '{"slug":"%s","repo":"%s","hop":"%s->%s","verdict":"%s","skipped":true}\n' "$SLUG" "$REPO" "$FROM" "$TO" "${reason:-NO_RESULT}" > "$O/skip.json"
else
  docker run --rm -v /tmp/hoptest:/tmp/hoptest -v "$CI/rung2/r2score_one.py:/s.py:ro" python:3-slim python3 /s.py "$O" "$REPO" >/dev/null 2>&1
fi
docker run --rm -v /tmp/bjv_ws:/w alpine rm -rf "/w/$SLUG" 2>/dev/null || true
echo "DONE $SLUG"
