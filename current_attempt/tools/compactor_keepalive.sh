#!/usr/bin/env bash
# P10 frog-eye: keep the observability condenser alive (auto-restart on exit).
COMP=/home/vmihaylov/java_8_11_17_to_java_21/current_attempt/tools/compactor_v3.py
LOG=/var/log/observe/compactor.log
while true; do
  echo "[keepalive] starting compactor at $(date -u +%FT%TZ)" >> "$LOG"
  python3 "$COMP" >> "$LOG" 2>&1
  echo "[keepalive] compactor exited rc=$? at $(date -u +%FT%TZ), restart in 5s" >> "$LOG"
  sleep 5
done
