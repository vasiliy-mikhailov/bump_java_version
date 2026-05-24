"""Rolling-context anomaly detector per fitness #8.

- Sample host state every 30s; persist raw to /tmp/metrics_frog_raw.jsonl
- Maintain rolling working memory of samples
- Cheap per-sample frog's-eyes diff vs previous → emit alarm on sharp blip
- When buffer ≥ 80% of context budget OR every 30 min: Qwen compacts the history
  into ~20% and surfaces sustained-drift anomalies (multi-minute / multi-hour patterns)
- Output: /tmp/metrics_frog_v2.jsonl (one entry per emit, alarm or compaction)"""
import json, time, subprocess, urllib.request, re, os

RAW = "/tmp/metrics_frog_raw.jsonl"
OUT = "/tmp/metrics_frog_v2.jsonl"
CTX_BUDGET = 128 * 1024  # Qwen max-model-len
COMPACT_AT = int(CTX_BUDGET * 0.80)   # ~100k tokens
RECENT_KEEP = 10                      # keep N recent samples uncompacted
SAMPLE_EVERY_S = 30
DEEP_REVIEW_EVERY_S = 30 * 60         # 30 min

ALARM_SYSTEM = (
    "You compare a fresh host snapshot to the previous snapshot. "
    "Return JSON: {\"alarming\": true|false, \"summary\": \"<one short line>\"}. "
    "Mark alarming=true on: new errors in any log, new exited containers, sharp load change >10, "
    "verifier stall >5min, sudden disk growth. Otherwise alarming=false. No prose, JSON only."
)

COMPACT_SYSTEM = (
    "You receive a rolling trajectory of host snapshots taken every 30 seconds, possibly with an "
    "earlier compacted summary at the top. Return JSON: "
    "{\"compacted_summary\": \"<paragraph compressing the trajectory into ~20% of input size, "
    "preserving notable patterns, sustained anomalies, drifts, recurring failures>\", "
    "\"sustained_anomalies\": [\"<short fact>\", ...]} "
    "Anomalies are patterns the per-sample diff would miss: sustained stall, recurring error, slow drift, "
    "non-recovery after recovery period. Output JSON only."
)


def sh(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return (r.stdout + b"\n" + r.stderr).decode(errors="replace").strip()
    except Exception as e:
        return f"<err: {e}>"


def collect():
    s = {}
    s["uptime"] = sh("uptime")
    try:
        s["load1"] = float(sh("uptime").split("load average:")[-1].split(",")[0].replace(",","."))
    except: s["load1"] = -1
    s["gpu"] = sh("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>&1 | head -2")
    s["docker_count"] = int(sh("docker ps -q | wc -l") or 0)
    s["running_containers"] = sh("docker ps --format '{{.Names}}' | sort | head -30")
    s["recently_exited"] = sh("docker ps -a --filter status=exited --filter status=dead --format '{{.Names}}|{{.Status}}' | head -10")
    s["fitness4_errors"] = sh("tail -100 /tmp/fitness4.log 2>/dev/null | grep -iE 'error|exception|traceback' | tail -3")
    s["fitness4_tail"] = sh("tail -1 /tmp/fitness4.log 2>/dev/null")
    s["fitness4_progress"] = sh("grep -c '^  \\[' /tmp/fitness4.log 2>/dev/null")
    s["nexus_l2_kb"] = int((sh("du -sk /var/nexus-data 2>/dev/null") or "0").split()[0] or 0)
    return s


def approx_tokens(text):
    return len(text) // 3


def ask_qwen(system, user, max_tokens=2000):
    body = {"model":"qwen3.6-27b-fp8","messages":[
            {"role":"system","content":system},
            {"role":"user","content":user}],
            "temperature":0.0,"max_tokens":max_tokens,"chat_template_kwargs":{"enable_thinking":False}}
    req = urllib.request.Request("http://localhost:8000/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization":"Bearer sk-ef2926520a83b7f6efac7f4dc5b049842b4b2baebfdc18b69b76220f29fdf272","Content-Type":"application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                content = (json.loads(r.read())["choices"][0]["message"].get("content") or "").strip()
            m = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", content, re.DOTALL)
            if m: return json.loads(m.group(0))
            return {"raw": content[:300]}
        except Exception as e:
            if attempt == 2: return {"err": str(e)}
            time.sleep(2 ** attempt)


def main():
    print("metrics_frog_v2: rolling-context compactor with multi-horizon anomaly memory", flush=True)
    buffer = []                  # list of {t, sample_str}
    compacted_summary = None     # earlier compacted history
    last_deep_review = time.time()
    prev_sample = None
    while True:
        cur = collect()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        sample_str = json.dumps({"t": ts, **cur})
        # Always persist raw
        with open(RAW, "a") as f:
            f.write(sample_str + "\n")
        buffer.append({"t": ts, "sample": cur})

        # --- per-sample frog's-eyes (cheap) ---
        alarm = None
        if prev_sample is not None:
            diff_facts = []
            if cur.get("fitness4_errors") and cur["fitness4_errors"] != prev_sample.get("fitness4_errors",""):
                diff_facts.append(f"new fitness4 errors: {cur['fitness4_errors'][:200]}")
            if cur.get("recently_exited","") != prev_sample.get("recently_exited",""):
                ne = set(cur.get("recently_exited","").split("\n")) - set(prev_sample.get("recently_exited","").split("\n"))
                if ne: diff_facts.append(f"new exits: {' | '.join(list(ne)[:3])}")
            if abs(cur.get("load1",0) - prev_sample.get("load1",0)) >= 10:
                diff_facts.append(f"load jump: {prev_sample.get('load1',0):.1f} -> {cur.get('load1',0):.1f}")
            if cur.get("fitness4_tail","") == prev_sample.get("fitness4_tail","") and cur.get("fitness4_tail"):
                # stall — track via counter
                cur["_stall"] = prev_sample.get("_stall", 0) + 1
                if cur["_stall"] in (10, 30, 60):  # ~5m, 15m, 30m
                    diff_facts.append(f"fitness4 stalled {cur['_stall']} cycles")
            else:
                cur["_stall"] = 0
            if diff_facts:
                alarm = "; ".join(diff_facts)[:300]

        if alarm:
            entry = {"t": ts, "kind": "alarm", "facts": alarm}
            with open(OUT, "a") as f: f.write(json.dumps(entry) + "\n")
            print(f"[{ts}] ALARM: {alarm}", flush=True)

        # --- compaction trigger ---
        # Estimate buffer size
        buf_text = "\n".join(json.dumps(b) for b in buffer)
        buf_tokens = approx_tokens((compacted_summary or "") + buf_text)
        force_deep = (time.time() - last_deep_review) >= DEEP_REVIEW_EVERY_S
        if buf_tokens >= COMPACT_AT or (force_deep and len(buffer) >= 5):
            print(f"[{ts}] COMPACTING (buf={buf_tokens} tokens, samples={len(buffer)})...", flush=True)
            user = "(Prior compaction summary:)\n" + (compacted_summary or "(none)") + \
                   "\n\n(Recent trajectory:)\n" + "\n".join(json.dumps(b) for b in buffer)
            resp = ask_qwen(COMPACT_SYSTEM, user, max_tokens=4000)
            compacted_summary = resp.get("compacted_summary", "")
            sustained = resp.get("sustained_anomalies", []) or []
            entry = {"t": ts, "kind": "compaction",
                     "samples_compacted": len(buffer),
                     "input_tokens": buf_tokens,
                     "compacted_summary": compacted_summary,
                     "sustained_anomalies": sustained}
            with open(OUT, "a") as f: f.write(json.dumps(entry) + "\n")
            print(f"[{ts}] COMPACT done. anomalies: {sustained}", flush=True)
            # Keep RECENT_KEEP latest samples
            buffer = buffer[-RECENT_KEEP:]
            last_deep_review = time.time()

        prev_sample = cur
        time.sleep(SAMPLE_EVERY_S)


if __name__ == "__main__":
    main()
