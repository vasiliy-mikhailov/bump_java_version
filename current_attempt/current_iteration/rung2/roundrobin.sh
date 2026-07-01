#!/bin/bash
# Balanced round-robin over the 4 hop queues: each bite goes to the hop with the FEWEST (completed+inflight)
# datapoints, screens inline (>=MINTESTS green), migrates via the two-step run_repo, scores. Even by hop until
# the small queues exhaust, then continues on the big ones. Args: TARGET [JOBS=4] [LOADCAP=20] [MINTESTS=5]
CI=/home/vmihaylov/bump-java-version/current_attempt/current_iteration
TARGET=${1:-200}; JOBS=${2:-4}; CAP=${3:-20}; export BJV_MIN_TESTS=${4:-5}
declare -A CUR LAUNCHED NEXT
for h in 8 11 17 21; do CUR[$h]=1; LAUNCHED[$h]=0; done
qlen(){ wc -l < /tmp/q/cand_$1.txt 2>/dev/null || echo 0; }
donec(){ ls /tmp/hoptest/rr_$1_*/score.json 2>/dev/null | wc -l; }
finc(){ ls /tmp/hoptest/rr_$1_*/score.json /tmp/hoptest/rr_$1_*/skip.json 2>/dev/null | wc -l; }
totdone(){ ls /tmp/hoptest/rr_*_*/score.json 2>/dev/null | wc -l; }
load1(){ awk '{print int($1)}' /proc/loadavg; }
while true; do
  td=$(totdone); [ "$td" -ge "$TARGET" ] && break
  avail=''; for h in 8 11 17 21; do [ "${CUR[$h]}" -le "$(qlen $h)" ] && avail="$avail $h"; done
  [ -z "$avail" ] && break
  while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do sleep 8; done   # load gate removed (operator request 2026-07-01); JOBS still caps concurrency
  best=''; bestm=999999
  for h in $avail; do m=$(( $(donec $h) + LAUNCHED[$h] - $(finc $h) )); [ "$m" -lt "$bestm" ] && { bestm=$m; best=$h; }; done
  h=$best
  line=$(sed -n "${CUR[$h]}p" /tmp/q/cand_$h.txt); CUR[$h]=$(( CUR[$h] + 1 ))
  repo=${line%% *}; sha=${line##* }; [ -z "$repo" ] && continue
  slug=rr_${h}_${LAUNCHED[$h]}; LAUNCHED[$h]=$(( LAUNCHED[$h] + 1 ))
  { [ -f /tmp/hoptest/$slug/score.json ] || [ -f /tmp/hoptest/$slug/skip.json ]; } && continue   # RESUME GUARD: don't re-run a done candidate
  echo "[$td/$TARGET | jv8=$(donec 8) jv11=$(donec 11) jv17=$(donec 17) jv21=$(donec 21) | load $(load1)] bite jv$h: $repo"
  ( bash $CI/rung2/run_repo.sh "$repo" "$sha" "$slug" >/tmp/rr_logs/$slug.log 2>&1 ) &
  sleep 4
done
wait
echo "ROUNDROBIN_DONE total=$(totdone) jv8=$(donec 8) jv11=$(donec 11) jv17=$(donec 17) jv21=$(donec 21)"
