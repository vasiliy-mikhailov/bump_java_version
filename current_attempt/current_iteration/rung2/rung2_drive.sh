#!/bin/bash
# rung-2 container entrypoint: run OpenHands+Qwen on the mounted /work project under the new discipline.
# Args: FROM TO. Mounts expected: /work (project), /oh_run.py, /r2bin (verbs), /prompt.txt.
set -uo pipefail
FROM=$1; TO=$2
export BJV_FROM="$FROM"
if [ "$TO" = 25 ]; then export BJV_REWRITE_PLUGIN=6.41.0 BJV_REWRITE_MIGRATE=3.36.0 BJV_REWRITE_DEPS=1.55.3; fi
export PATH=/r2bin:$PATH
export OC_BASE="${OC_BASE:-https://inference.mikhailov.tech/qwen-3.6-27b-fp8/v1}"
export OC_MODEL="${OC_MODEL:-qwen-3.6-27b-fp8}"
# gradle: shared RO dep cache + dists (mirror the host bjv setup) if mounted
[ -d /ro ] && export GRADLE_RO_DEP_CACHE=/ro
[ -d /dists ] && { mkdir -p "$HOME/.gradle/wrapper"; ln -sfn /dists "$HOME/.gradle/wrapper/dists"; }
mkdir -p "$HOME/.gradle"
grep -q installations.paths "$HOME/.gradle/gradle.properties" 2>/dev/null || \
  echo 'org.gradle.java.installations.paths=/opt/jdk/8,/opt/jdk/11,/opt/jdk/17,/opt/jdk/21' >> "$HOME/.gradle/gradle.properties"
cd /work
chmod +x ./gradlew 2>/dev/null || true
# never let git block on an interactive pager (a `git diff`/`log` opening `less` hangs the terminal forever)
export GIT_PAGER=cat PAGER=cat
git config --global core.pager cat 2>/dev/null || true
PROMPT="$(sed "s/__FROM__/$FROM/g; s/__TO__/$TO/g" /prompt.txt)"
# vLLM TCP keepalive: litellm's aiohttp transport gates SO_KEEPALIVE on these (default OFF). Our topology is
# agent -> caddy -> shared busy vLLM; without keepalive a slow-inference idle period gets reaped by the proxy/NAT
# hop into a stalled socket (then 300s wasted before the request timeout fires). KEEPIDLE 60 + KEEPINTVL 30.
export AIOHTTP_SO_KEEPALIVE=true AIOHTTP_TCP_KEEPIDLE=60 AIOHTTP_TCP_KEEPINTVL=30
/opt/ohvenv/bin/python /oh_run.py /work "$PROMPT"
