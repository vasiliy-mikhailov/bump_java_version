---
name: detect-java-version
description: Detect a Maven/Gradle project's REAL current Java level (by its declared bytecode target, not the build toolchain) and dispatch to the matching one-LTS bump hop (8->11, 11->17, 17->21, 21->25). Use as the entry point: it decides the hop and whether the project should be bumped at all.
---

# Bump a project one Java LTS: two steps: DETECT, then HOP

A project's **build toolchain** (the JDK Gradle/Maven builds *with*) is NOT its **bytecode target** (the Java
version it *emits*). Many libraries deliberately build with a new JDK but pin old bytecode for consumer reach
(OpenTelemetry instrumentation, Gradle plugins, SDKs). Dispatching on the toolchain mislabels these and tries
an impossible/harmful bump. So always detect the real level first.

## Step 1: detect the real current level + bumpability
`detect_java_version.sh <repo> <sha>` -> JSON. It reads, across ALL modules, the declared **bytecode target**
(precedence: `options.release` / `<maven.compiler.release>` > `source/targetCompatibility` / `<source>` /
`jvmTarget` > the toolchain `languageVersion`), and reports:
- `detected`, the MIN bytecode target across modules (the true current Java level).
- `low_target`, TRUE if a bytecode target is pinned BELOW the toolchain, OR modules target different levels
  (multi-target), OR a `java-gradle-plugin` is applied. These are **deliberate-low-target** projects.
- `bumpable`, TRUE only if a clean single target below the latest LTS AND not `low_target`.
- `hop_to`, the next LTS above `detected`.

## Step 2: dispatch
- `bumpable: false` -> **NOT_A_BUMP** (record + stop). Bumping its bytecode would regress its consumers; it
  is not a migration target. Do NOT score it as a failed bump.
- else -> run the matching per-hop skill for `detected`'s LTS bracket: 8->11, 11->17, 17->21, or 21->25
  (build JDKs are the LTS rungs; a non-LTS detected level brackets down, e.g. 14 -> the 11->17 hop).

The orchestrator `run_repo.sh <repo> <sha> <slug>` does both: detect -> NOT_A_BUMP or dispatch.
