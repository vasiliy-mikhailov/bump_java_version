#!/bin/bash
# TWO-STEP bump: detect real Java version, then dispatch to the matching hop skill. Args: REPO SHA SLUG
REPO=$1; SHA=$2; SLUG=$3
CI=/home/vmihaylov/bump-java-version/current_attempt/current_iteration
O=/tmp/hoptest/$SLUG; mkdir -p $O
bash $CI/rung2/detect_java_version.sh "$REPO" "$SHA" $O/detect.json
det=$(cat $O/detect.json 2>/dev/null)
detected=$(echo "$det" | sed -n 's/.*"detected": *\([0-9]*\).*/\1/p')
bumpable=$(echo "$det" | grep -oE '"bumpable": *true')
# module-level: reclaim a repo detect_java skipped when ALL its bumpable modules sit on ONE LTS hop (a single-
# hop repo mis-skipped as multi/soft-pin/plugin) -> dispatch that hop; the per-module gate then scores each
# module honestly. Modules that span MULTIPLE hops need the per-module iteration executor (follow-up), so they
# stay NOT_A_BUMP: this never dispatches to a bump-java-$F-to-$T skill that does not exist.
if [ -z "$bumpable" ] && [ -s "$O/modules.jsonl" ]; then
  hops=$(grep -oE '"from": *[0-9]+, *"to": *[0-9]+' $O/modules.jsonl | sort -u); nhops=$(printf '%s\n' "$hops" | grep -c .)
  if [ "${nhops:-0}" = "1" ]; then detected=$(printf '%s' "$hops" | grep -oE '"from": *[0-9]+' | grep -oE '[0-9]+'); bumpable=singlehop; fi
fi
if [ -z "$bumpable" ]; then
  printf '{"slug":"%s","repo":"%s","verdict":"NOT_A_BUMP","detect":%s}\n' "$SLUG" "$REPO" "${det:-null}" > $O/skip.json
  echo "NOT_A_BUMP $REPO :: $det"; exit 0
fi
# bracket the detected level to its LTS hop (build JDKs are LTS: 8/11/17/21)
case $detected in
  8|9|10)            F=8;  T=11;;
  11|12|13|14|15|16) F=11; T=17;;
  17|18|19|20)       F=17; T=21;;
  21|22|23|24)       F=21; T=25;;
  *) printf '{"slug":"%s","repo":"%s","verdict":"NOT_A_BUMP","detect":%s}\n' "$SLUG" "$REPO" "${det:-null}" > $O/skip.json; echo "NOT_A_BUMP (>=25 or unknown) $REPO"; exit 0;;
esac
echo "DISPATCH $REPO  detected=$detected -> hop $F->$T  (bumpable=$bumpable)"
bash $CI/rung2/rung2_one_scored.sh "$REPO" "$SHA" "$SLUG" "$F" "$T"
