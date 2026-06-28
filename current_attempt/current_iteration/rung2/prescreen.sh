#!/bin/bash
# GREEN pre-screen: keep candidates with >= MIN runnable-PASSING tests under FROM (not the static @Test count).
# Args: CANDFILE FROM OUT [MIN=5] [JOBS=4] [LOADCAP=22] [MAXTRY=100000]
CAND=$1; FROM=$2; OUT=$3; MIN=${4:-5}; JOBS=${5:-4}; CAP=${6:-22}; MAXTRY=${7:-100000}; TARGET=${8:-100000}
mkdir -p /tmp/prescreen; RD=/tmp/prescreen/run_$FROM; mkdir -p $RD
load1(){ awk '{print int($1)}' /proc/loadavg; }
screen_one(){
  local REPO=$1 SHA=$2 MIN=$3 FROM=$4 RD=$5
  local SLUG=ps_$(echo $REPO|tr / _)
  ( export SLUG FROM TO=$FROM; . /home/vmihaylov/java_8_11_17_to_java_21/current_attempt/current_iteration/rung2/rung1lib.sh
    r1_clone "$REPO" "$SHA" >/dev/null 2>&1 || { echo "$REPO clone_fail" >$RD/$SLUG.res; exit 0; }
    n=$(r1_baseline 2>/dev/null); case "$n" in ''|*[!0-9]*) n=0;; esac
    if [ "$n" -ge "$MIN" ]; then echo "$REPO $SHA green=$n" >$RD/$SLUG.keep; else echo "$REPO green=$n" >$RD/$SLUG.res; fi
    docker run --rm -v /tmp/bjv_ws:/w alpine rm -rf "/w/$SLUG" >/dev/null 2>&1
    docker run --rm -v /tmp/hoptest:/h alpine rm -rf "/h/$SLUG" >/dev/null 2>&1 )
}
export -f screen_one load1
tried=0
while read -r REPO SHA; do
  [ -z "$REPO" ] && continue
  [ "$tried" -ge "$MAXTRY" ] && break; [ "$(ls $RD/*.keep 2>/dev/null|wc -l)" -ge "$TARGET" ] && break
  SLUG=ps_$(echo $REPO|tr / _); [ -f $RD/$SLUG.keep ] || [ -f $RD/$SLUG.res ] && continue
  while [ "$(load1)" -ge "$CAP" ]; do sleep 15; done
  while [ "$(jobs -rp|wc -l)" -ge "$JOBS" ]; do sleep 5; done
  tried=$((tried+1)); screen_one "$REPO" "$SHA" "$MIN" "$FROM" "$RD" &
  sleep 3
done < "$CAND"
wait
cat $RD/*.keep 2>/dev/null | sort -t= -k2 -rn > $OUT
echo "PRESCREEN_DONE from=$FROM kept=$(cat $RD/*.keep 2>/dev/null|wc -l) screened=$(ls $RD/*.keep $RD/*.res 2>/dev/null|wc -l)"
