#!/bin/bash
# triage_bundle.sh <corpus_dir> [out_dir] -- bundle a bounded diagnostic packet for every FAIL slug in a
# scored corpus (default /tmp/hoptest, or an archived run), so the fails can be root-caused in parallel
# (see the triage-fails workflow). Slug -> repo@sha comes from host.log's authoritative
# "clone+baseline <repo> @ <sha> (jv<from>)" line (NOT a grep of agent.log, which carries the agent
# framework's own github URLs). Emits <out>/<slug>.txt bundles + <out>/_index.tsv and a tarball.
set -uo pipefail
CORPUS="${1:-/tmp/hoptest}"
OUT="${2:-/tmp/faildump}"
rm -rf "$OUT"; mkdir -p "$OUT"; : > "$OUT/_index.tsv"
cd "$CORPUS" || { echo "no corpus dir: $CORPUS" >&2; exit 1; }
n=0
for d in rr_* reg_*; do
  [ -d "$d" ] && [ -s "$d/verdict.txt" ] || continue
  grep -aq "VERDICT FAIL" "$d/verdict.txt" || continue
  hop=$(echo "$d" | sed -E 's/(reg_)?rr_([0-9]+)_.*/\2/')
  vsig=$(grep -aoE "FAIL_[a-z_]+ pre [0-9-]+ post [0-9-]+ lost [0-9-]+ target [0-9-]+" "$d/verdict.txt" | head -1)
  cb=$(grep -aoE "clone\+baseline [^ ]+ @ [0-9a-f]+ \(jv[0-9]+\)" "$d/host.log" 2>/dev/null | head -1)
  repo=$(echo "$cb" | awk '{print $2}'); sha=$(echo "$cb" | awk '{print $4}')
  [ -z "$repo" ] && repo="(unknown)"; [ -z "$sha" ] && sha="(unknown)"
  printf "%s\t%s\t%s\t%s\t%s\n" "$d" "$hop" "$repo" "$sha" "$vsig" >> "$OUT/_index.tsv"
  n=$((n+1))
  {
    echo "###### SLUG $d   HOP ${hop}->next   REPO $repo   SHA $sha"
    echo "###### VERDICT.TXT";       cat "$d/verdict.txt" 2>/dev/null
    echo; echo "###### RESULT.JSON"; cat "$d/result.json" 2>/dev/null
    echo; echo "###### SCORE.JSON";  cat "$d/score.json" 2>/dev/null
    echo; echo "###### PARAM.TXT";   cat "$d/param.txt" 2>/dev/null
    echo; echo "###### AGENT.STATUS (finished or bailed? iterations?)"; cat "$d/agent.status" 2>/dev/null
    echo; echo "###### DETECT.JSON (router decision)"; cat "$d/detect.json" 2>/dev/null
    echo; echo "###### REWRITE.YML (recipe the agent chose)"; cat "$d/rewrite.yml" 2>/dev/null
    echo; echo "###### AGENT.DIFF (head 400 -- what the agent changed)"; head -400 "$d/agent.diff" 2>/dev/null
    echo; echo "###### COMPILE.LOG tail (post-bump build; FAIL_build_post signal)"; tail -60 "$d/compile.log" 2>/dev/null
    echo; echo "###### POST.LOG tail (post-bump test run)"; tail -40 "$d/post.log" 2>/dev/null
    echo; echo "###### PRE_BUILD.LOG tail (baseline build)"; tail -20 "$d/pre_build.log" 2>/dev/null
    echo; echo "###### PRE_TEST.LOG tail (baseline test)"; tail -20 "$d/pre_test.log" 2>/dev/null
    echo; echo "###### AGENT.LOG tail 80 (agent trace / last actions)"; tail -80 "$d/agent.log" 2>/dev/null
    echo; echo "###### LOST TESTS (pre-not-in-post, head 50 -- for FAIL_test_conservation)"
    comm -23 <(sort "$d/pre_set.txt" 2>/dev/null) <(sort "$d/post_set.txt" 2>/dev/null) 2>/dev/null | head -50
    echo; echo "###### GAINED TESTS (post-not-in-pre, head 20)"
    comm -13 <(sort "$d/pre_set.txt" 2>/dev/null) <(sort "$d/post_set.txt" 2>/dev/null) 2>/dev/null | head -20
  } > "$OUT/$d.txt" 2>/dev/null
done
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo "bundled $n FAIL slugs from $CORPUS -> $OUT ($(du -h "$OUT.tar.gz" | cut -f1) tar)"
