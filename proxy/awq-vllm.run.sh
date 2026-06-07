#!/usr/bin/env bash
set -euo pipefail
OLD=omega-reptile-vllm-playground
IMG=vllm/vllm-openai:v0.20.0-cu130-ubuntu2404
GPU=GPU-aa391cd3-2b77-0ded-a4cf-b2ee93f9b846   # RTX 5090

# pull the existing api-key from the old container WITHOUT printing it
APIKEY=$(docker inspect "$OLD" | grep -oE 'sk-[A-Za-z0-9]+' | head -1)
if [ -z "${APIKEY:-}" ]; then echo "ERROR: could not extract api-key"; exit 1; fi
echo "api-key length: ${#APIKEY} (value hidden)"

docker rm -f "$OLD" >/dev/null 2>&1 || true

docker run -d \
  --name "$OLD" \
  --runtime nvidia \
  --ipc host \
  --restart unless-stopped \
  --network proxy-net \
  -e NVIDIA_VISIBLE_DEVICES="$GPU" \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  -v /mnt/steam/forge/shared/models:/root/.cache/huggingface \
  "$IMG" \
  --model cyankiwi/Qwen3.6-27B-AWQ-INT4 \
  --served-model-name qwen-3.6-27b-awq \
  --max-model-len 131072 \
  --kv-cache-dtype fp8 \
  --max-num-seqs 256 \
  --enforce-eager \
  --enable-prefix-caching \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --gpu-memory-utilization 0.92 \
  --host 0.0.0.0 --port 8000 \
  --api-key "$APIKEY"

echo "started new $OLD"
