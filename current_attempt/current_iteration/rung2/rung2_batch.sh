#!/bin/bash
# Batch rung-2 with ADAPTIVE concurrency + load gate (headroom, no induced contention).
# Stops once TARGET green-baseline verdicts (score.json) exist. Args: CANDFILE TARGET MAXJOBS LOADCAP MAXTRY
CAND=${1:-/tmp/r2_candidates.txt}
TARGET=${2:-56}
MAXJOBS=${3:-3}
LOADCAP=${4:-21}
MAXTRY=${5:-200}
mkdir -p /tmp/hoptest
verdicts(){ ls /tmp/hoptest/r2b_*/score.json 2>/dev/null | wc -l; }
load1(){ awk '{print int($1)}' /proc/loadavg; }
tried=0
while read -r REPO SHA; do
  [ -z "$REPO" ] && continue
  [ "$(verdicts)" -ge "$TARGET" ] && break
  [ "$tried" -ge "$MAXTRY" ] && break
  # headroom gate: don't start while host load is high (preserve cores for live builds/tests)
  while [ "$(load1)" -ge "$LOADCAP" ]; do sleep 20; done
  # concurrency gate
  while [ "$(jobs -rp | wc -l)" -ge "$MAXJOBS" ]; do sleep 10; done
  tried=$((tried+1)); SLUG="r2b_$(echo "$REPO" | tr '/' '_')"
  { [ -f "/tmp/hoptest/$SLUG/score.json" ] || [ -f "/tmp/hoptest/$SLUG/skip.json" ]; } && continue   # already done/skipped
  echo "[$tried tried, $(verdicts)/$TARGET verdicts, load $(load1)] launch $REPO @ $SHA"
  bash /tmp/rung2_one_scored.sh "$REPO" "$SHA" "$SLUG" &
  sleep 8
done < "$CAND"
wait
echo "RUNG2_BATCH_DONE tried=$tried verdicts=$(verdicts)"
