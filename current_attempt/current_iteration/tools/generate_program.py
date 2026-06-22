#!/usr/bin/env python3
"""generate_program — per-hop GEPA-optimized module. Given the hop SKILL.md + the project's build files,
calls the LLM and emits the EXECUTABLE conversion program: a single OpenRewrite `rewrite.yml` (a declarative
composite recipe whose `recipeList` is the recipe sequence). It runs/edits nothing. stdlib only (urllib).
  generate_program.py <skill.md> <build_files_dir> <from> <to> [last_failure_log]  -> rewrite.yml on stdout
Env: OC_BASE, OC_MODEL, OC_KEY.
"""
import sys, os, json, glob, urllib.request

skill = open(sys.argv[1]).read()
wsdir, FROM, TO = sys.argv[2], sys.argv[3], sys.argv[4]
fail = open(sys.argv[5]).read()[-6000:] if len(sys.argv) > 5 and os.path.exists(sys.argv[5]) else ""

parts = []
for pat in ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
            "gradle/libs.versions.toml", "gradle/wrapper/gradle-wrapper.properties"):
    for f in glob.glob(os.path.join(wsdir, "**", pat), recursive=True)[:8]:
        try: parts.append(f"### {os.path.relpath(f, wsdir)}\n{open(f, errors='ignore').read()[:6000]}")
        except Exception: pass
build_ctx = "\n\n".join(parts)[:24000] or "(no build files found)"

user = (f"Java {FROM} -> {TO} bump. Build files:\n\n{build_ctx}\n\n"
        + (f"PREVIOUS ATTEMPT FAILED — logs (fix the recipe list accordingly):\n{fail}\n\n" if fail else "")
        + "Output ONLY the rewrite.yml (an OpenRewrite declarative composite recipe named com.bjv.Bump with a "
          "recipeList of the recipes/intents to apply, in order). No prose, no fences.")

body = json.dumps({"model": os.environ["OC_MODEL"], "temperature": 0.0,
                   "messages": [{"role": "system", "content": skill}, {"role": "user", "content": user}]}).encode()
req = urllib.request.Request(os.environ["OC_BASE"].rstrip("/") + "/chat/completions", data=body,
                            headers={"Authorization": "Bearer " + os.environ["OC_KEY"], "Content-Type": "application/json"})
txt = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"]

if "</think>" in txt: txt = txt.split("</think>")[-1]
# strip ``` fences and any preamble before the recipe header
if "```" in txt:
    segs = txt.split("```")
    txt = max((s for s in segs if "recipeList" in s), key=len, default=txt)
    if txt.lstrip().startswith(("yaml", "yml")): txt = txt.split("\n", 1)[1]
i = txt.find("type: specs.openrewrite.org")
if i < 0: i = txt.find("recipeList")
if i > 0: txt = txt[i:]
print(txt.strip())
