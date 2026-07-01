#!/bin/bash
# run_regression.sh [concurrency] -- re-run the confirmed CRITIC false-fail fixture (regression_false_fails.tsv)
# through the CURRENT-genome harness. Each of these was a correct bump that the critic wrongly scored FAIL and
# a committed fix should now flip to PASS; a row that does NOT pass means a critic regression (or a fix that
# never landed). Deterministic-ish critic guard: run it after any change to the reward code.
# Uses reg_<slug> output dirs so it never collides with a live rr_ sweep (but it DOES add build load; run when
# convenient). Rows tagged status=open are known-not-yet-fixed (expected still FAIL) -- reported, not counted
# against the pass bar.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CI="$(cd "$HERE/.." && pwd)"                 # tools/.. = current_iteration
FIX="$HERE/regression_false_fails.tsv"
J="${1:-2}"
[ -f "$FIX" ] || { echo "missing fixture: $FIX" >&2; exit 1; }

echo "running $(grep -cvE '^#|^[[:space:]]*$' "$FIX") fixture repos through the current genome (concurrency $J)..."
pids=""
while IFS=$'\t' read -r slug repo sha frm to cls status verdict; do
  case "$slug" in \#*|"") continue;; esac
  ( bash "$CI/rung2/run_repo.sh" "$repo" "$sha" "reg_$slug" >"/tmp/hoptest/reg_$slug.launch.log" 2>&1 ) &
  pids="$pids $!"
  while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do sleep 5; done
done < "$FIX"
wait $pids 2>/dev/null

echo
printf "%-11s %-40s %-13s %-8s %-6s %-8s %s\n" slug repo class status expect got RESULT
pass=0; want=0; reg=0
while IFS=$'\t' read -r slug repo sha frm to cls status verdict; do
  case "$slug" in \#*|"") continue;; esac
  got=$(grep -aoE "VERDICT (PASS|FAIL_[a-z_]+|UNSCORABLE_[A-Z_]+|NO_BASELINE[A-Z_]*)" "/tmp/hoptest/reg_$slug/verdict.txt" 2>/dev/null | head -1 | awk '{print $2}')
  [ -z "$got" ] && got="(no-verdict)"
  expect=PASS; [ "$status" = open ] && expect="FAIL(open)"
  res=OK
  if [ "$status" = fixed ]; then
    want=$((want+1))
    if [ "$got" = PASS ]; then pass=$((pass+1)); else res="REGRESSION"; reg=$((reg+1)); fi
  else
    [ "$got" = PASS ] && res="now-passes(promote?)"
  fi
  printf "%-11s %-40s %-13s %-8s %-6s %-8s %s\n" "$slug" "$repo" "$cls" "$status" "$expect" "$got" "$res"
done < "$FIX"
echo
echo "FIXED rows now PASS: $pass/$want   regressions: $reg"
[ "$reg" -eq 0 ] && echo "OK: no critic regression" || { echo "CRITIC REGRESSION: $reg fixed row(s) no longer pass"; exit 1; }
