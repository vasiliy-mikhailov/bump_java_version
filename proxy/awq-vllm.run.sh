#!/usr/bin/env bash
set -euo pipefail
OLD=omega-reptile-vllm-playground
IMG=vllm/vllm-openai:v0.20.0-cu130-ubuntu2404
GPU=GPU-aa391cd3-2b77-0ded-a4cf-b2ee93f9b846   # RTX 5090
MODEL=cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit         # MoE (3B active / 35B), AWQ 4-bit, ~24GB
SERVED=qwen-3.6-35b-a3b-awq                      # endpoint/route suffix matches the served model

# preserve the existing api-key from the running container WITHOUT printing it
APIKEY=$(docker inspect "$OLD" | grep -oE 'sk-[A-Za-z0-9]+' | head -1)
if [ -z "${APIKEY:-}" ]; then echo "ERROR: could not extract api-key"; exit 1; fi
echo "api-key length: ${#APIKEY} (value hidden)"

docker rm -f "$OLD" >/dev/null 2>&1 || true

# Home HF cache (NOT the don't-touch /mnt/steam); vLLM auto-downloads the model here on first run.
docker run -d \
  --name "$OLD" \
  --runtime nvidia \
  --ipc host \
  --restart unless-stopped \
  --network proxy-net \
  -e NVIDIA_VISIBLE_DEVICES="$GPU" \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  -v /home/vmihaylov/.cache/huggingface:/root/.cache/huggingface \
  "$IMG" \
  --model "$MODEL" \
  --served-model-name "$SERVED" \
  --max-model-len 65536 \
  --max-num-batched-tokens 8192 \
  --kv-cache-dtype fp8 \
  --max-num-seqs 128 \
  --enforce-eager \
  --enable-prefix-caching \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --gpu-memory-utilization 0.95 \
  --host 0.0.0.0 --port 8000 \
  --api-key "$APIKEY"

echo "started $OLD serving $MODEL as $SERVED"
